from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
import ast
import copy
import inspect

import pytest

import test_financial_metric_trajectory as helpers
import app.intelligence.research_metric_directionality as module
from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryBasis, FinancialMetricTrajectoryStatus
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis
from app.intelligence.research_metric_directionality import (
    ResearchMetricDirectionalityOrientation as Orientation,
    interpret_research_metric_directionality,
    research_metric_directionality_interpretation_fingerprint,
)
from app.intelligence.research_metric_directionality_policy import (
    CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY as POLICY,
    ResearchMetricDirectionalityDisposition as Disposition,
)


def _flow(metric=FinancialMetric.REVENUE, *, previous="100", current="120", basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER):
    if basis is FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL:
        old = helpers._prepared(helpers._fact("old", metric=metric, value=previous, start=datetime(2024, 4, 1, tzinfo=UTC), end=datetime(2025, 3, 31, tzinfo=UTC), year=2025, quarter=None, period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR))
        new = helpers._prepared(helpers._fact("new", metric=metric, value=current, start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2026, 3, 31, tzinfo=UTC), year=2026, quarter=None, period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR))
    elif basis is FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER:
        old = helpers._prepared(helpers._fact("old", metric=metric, value=previous, start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2))
        new = helpers._prepared(helpers._fact("new", metric=metric, value=current, start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    else:
        old = helpers._prepared(helpers._fact("old", metric=metric, value=previous))
        new = helpers._prepared(helpers._fact("new", metric=metric, value=current, start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    return helpers._trajectory(helpers._bundle(old, new), metric=metric, basis=basis, previous=old[0].fingerprint, current=new[0].fingerprint)


def _stock(metric, *, previous="100", current="80"):
    old = helpers._prepared(helpers._fact("old", metric=metric, value=previous, start=None, end=datetime(2025, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    new = helpers._prepared(helpers._fact("new", metric=metric, value=current, start=None, end=datetime(2026, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    return helpers._trajectory(helpers._bundle(old, new), metric=metric, basis=FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, previous=old[0].fingerprint, current=new[0].fingerprint)


def _interpret(trajectory):
    assert trajectory.status is FinancialMetricTrajectoryStatus.AVAILABLE
    return interpret_research_metric_directionality(trajectory, policy=POLICY)


@pytest.mark.parametrize(("previous", "current", "orientation"), [("100", "120", Orientation.POTENTIALLY_FAVORABLE), ("120", "100", Orientation.POTENTIALLY_UNFAVORABLE), ("100", "100", Orientation.NO_DIRECTIONAL_CHANGE)])
def test_revenue_yoy_maps_only_exact_absolute_delta_ordering(previous, current, orientation) -> None:
    result = _interpret(_flow(previous=previous, current=current))
    assert result.orientation is orientation
    assert result.disposition is Disposition.HIGHER_POTENTIALLY_FAVORABLE
    assert result.fingerprint == research_metric_directionality_interpretation_fingerprint(result)
    with pytest.raises(FrozenInstanceError): result.orientation = Orientation.CONTEXT_DEPENDENT


@pytest.mark.parametrize("metric", (FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT, FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC, FinancialMetric.EPS_DILUTED))
@pytest.mark.parametrize("basis", (FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL))
def test_all_approved_higher_favorable_rules_map_upward_movement(metric, basis) -> None:
    assert _interpret(_flow(metric, basis=basis)).orientation is Orientation.POTENTIALLY_FAVORABLE


def test_sequential_context_rules_and_balance_sheet_movements_cannot_be_overridden_by_sign() -> None:
    assert _interpret(_flow(FinancialMetric.REVENUE, basis=FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER)).orientation is Orientation.CONTEXT_DEPENDENT
    for metric in (FinancialMetric.PBT, FinancialMetric.CFO, FinancialMetric.FREE_CASH_FLOW):
        assert _interpret(_flow(metric)).orientation is Orientation.CONTEXT_DEPENDENT
    for metric in (FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS, FinancialMetric.RECEIVABLES, FinancialMetric.INVENTORY, FinancialMetric.PAYABLES):
        assert _interpret(_stock(metric)).orientation is Orientation.CONTEXT_DEPENDENT


def test_non_directional_rules_ignore_sign_and_zero_movement() -> None:
    for metric in (FinancialMetric.CFI, FinancialMetric.CFF):
        assert _interpret(_flow(metric, previous="-100", current="20")).orientation is Orientation.NON_DIRECTIONAL
    for metric in (FinancialMetric.SHARES_OUTSTANDING, FinancialMetric.FACE_VALUE):
        assert _interpret(_stock(metric, previous="100", current="100")).orientation is Orientation.NON_DIRECTIONAL


def test_pat_directionality_uses_absolute_delta_not_relative_or_sign_transition() -> None:
    assert _flow(FinancialMetric.PAT, previous="-100", current="-50", basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL).relative_delta is None
    assert _interpret(_flow(FinancialMetric.PAT, previous="-100", current="-50", basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL)).orientation is Orientation.POTENTIALLY_FAVORABLE
    assert _interpret(_flow(FinancialMetric.PAT, previous="-100", current="20", basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL)).orientation is Orientation.POTENTIALLY_FAVORABLE
    assert _interpret(_flow(FinancialMetric.PAT, previous="20", current="-100", basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL)).orientation is Orientation.POTENTIALLY_UNFAVORABLE


def test_tiny_change_has_no_materiality_layer() -> None:
    result = _interpret(_flow(previous="100", current="100.000001"))
    assert result.orientation is Orientation.POTENTIALLY_FAVORABLE
    assert not hasattr(result, "materiality")


def test_non_available_or_nontrajectory_input_is_rejected() -> None:
    partial = helpers._prepared(helpers._fact("partial", start=None, year=None, quarter=None))
    q2 = helpers._prepared(helpers._fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    blocked = helpers._trajectory(helpers._bundle(partial, q2), previous=partial[0].fingerprint, current=q2[0].fingerprint)
    assert blocked.status is FinancialMetricTrajectoryStatus.INSUFFICIENT
    with pytest.raises(ValueError, match="AVAILABLE_TRAJECTORY_REQUIRED"):
        interpret_research_metric_directionality(blocked, policy=POLICY)
    with pytest.raises(ValueError, match="TRAJECTORY_REQUIRED"):
        interpret_research_metric_directionality(object(), policy=POLICY)


def test_policy_and_trajectory_tampering_or_missing_rule_fail_closed() -> None:
    trajectory = _flow()
    changed = copy.copy(POLICY); object.__setattr__(changed, "version", "v2-approved")
    with pytest.raises(ValueError, match="POLICY_TAMPERED|EXACT_POLICY_REQUIRED"):
        interpret_research_metric_directionality(trajectory, policy=changed)
    object.__setattr__(trajectory, "fingerprint", "0" * 64)
    with pytest.raises(ValueError, match="TRAJECTORY_TAMPERED"):
        _interpret(trajectory)
    assert not [rule for rule in POLICY.rules if rule.disposition is Disposition.LOWER_POTENTIALLY_FAVORABLE]


def test_interpreter_has_no_upstream_or_runtime_dependency_and_no_aggregation_api() -> None:
    source = inspect.getsource(module)
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden = {"app.fundamentals.financial_fact_vintage_selector", "app.fundamentals.financial_metric_observation_materializer", "app.fundamentals.financial_research_observation_bundle_builder", "app.fundamentals.financial_research_observation_wrapper", "app.intelligence.brain_research_comparison_state_v2", "app.intelligence.research_state_delta"}
    assert not imports & forbidden
    functions = {name for name, value in vars(module).items() if inspect.isfunction(value) and value.__module__ == module.__name__}
    assert functions == {"interpret_research_metric_directionality", "research_metric_directionality_interpretation_fingerprint", "_require_trajectory", "_require_policy", "_exact_rule", "_orientation", "_interpretation_fingerprint_values", "_aware"}
    for forbidden_term in ("sqlite3", "requests", "urllib", "FastAPI", "APIRouter", "DecisionScore", "SixGate", "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "alert", "recommendation", "acceleration"):
        assert forbidden_term not in source
