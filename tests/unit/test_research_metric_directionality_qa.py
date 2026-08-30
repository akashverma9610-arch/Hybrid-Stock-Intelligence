"""U14D-7B end-to-end QA for frozen metric-local directionality only."""
from __future__ import annotations

import ast
import copy
import inspect
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal

import pytest

import test_financial_metric_trajectory as helpers
import app.intelligence.research_metric_directionality as interpreter_module
from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectoryRequest,
    build_financial_metric_trajectory,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY as TRAJECTORY_POLICY,
    FinancialMetricTrajectoryBasis as Basis,
    FinancialMetricTrajectoryStatus as TrajectoryStatus,
)
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis
from app.intelligence.research_metric_directionality import (
    ResearchMetricDirectionalityOrientation as Orientation,
    interpret_research_metric_directionality,
)
from app.intelligence.research_metric_directionality_policy import (
    CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY as POLICY,
    ResearchMetricDirectionalityDisposition as Disposition,
)


def _flow(
    metric: FinancialMetric = FinancialMetric.REVENUE, *, previous: str = "100",
    current: str = "120", basis: Basis = Basis.YEAR_OVER_YEAR_QUARTER,
):
    if basis is Basis.YEAR_OVER_YEAR_ANNUAL:
        old = helpers._prepared(helpers._fact(
            "old", metric=metric, value=previous, start=datetime(2024, 4, 1, tzinfo=UTC),
            end=datetime(2025, 3, 31, tzinfo=UTC), year=2025, quarter=None,
            period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR,
        ))
        new = helpers._prepared(helpers._fact(
            "new", metric=metric, value=current, start=datetime(2025, 4, 1, tzinfo=UTC),
            end=datetime(2026, 3, 31, tzinfo=UTC), year=2026, quarter=None,
            period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR,
        ))
    elif basis is Basis.YEAR_OVER_YEAR_QUARTER:
        old = helpers._prepared(helpers._fact(
            "old", metric=metric, value=previous, start=datetime(2025, 7, 1, tzinfo=UTC),
            end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2,
        ))
        new = helpers._prepared(helpers._fact(
            "new", metric=metric, value=current, start=datetime(2026, 7, 1, tzinfo=UTC),
            end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2,
        ))
    else:
        old = helpers._prepared(helpers._fact("old", metric=metric, value=previous))
        new = helpers._prepared(helpers._fact(
            "new", metric=metric, value=current, start=datetime(2026, 7, 1, tzinfo=UTC),
            end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2,
        ))
    bundle = helpers._bundle(old, new)
    return build_financial_metric_trajectory(
        bundle,
        request=FinancialMetricTrajectoryRequest(metric, basis, old[0].fingerprint, new[0].fingerprint),
        policy=TRAJECTORY_POLICY,
    )


def _stock(metric: FinancialMetric, *, previous: str = "100", current: str = "80"):
    old = helpers._prepared(helpers._fact(
        "old", metric=metric, value=previous, start=None, end=datetime(2025, 3, 31, tzinfo=UTC),
        year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME,
        basis=FinancialValueBasis.QUARTER_ONLY,
    ))
    new = helpers._prepared(helpers._fact(
        "new", metric=metric, value=current, start=None, end=datetime(2026, 3, 31, tzinfo=UTC),
        year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME,
        basis=FinancialValueBasis.QUARTER_ONLY,
    ))
    bundle = helpers._bundle(old, new)
    return build_financial_metric_trajectory(
        bundle,
        request=FinancialMetricTrajectoryRequest(metric, Basis.POINT_IN_TIME_SEQUENTIAL, old[0].fingerprint, new[0].fingerprint),
        policy=TRAJECTORY_POLICY,
    )


def _interpret(trajectory):
    assert trajectory.status is TrajectoryStatus.AVAILABLE
    return interpret_research_metric_directionality(trajectory, policy=POLICY)


@pytest.mark.parametrize(("previous", "current", "orientation"), [
    ("-100", "-50", Orientation.POTENTIALLY_FAVORABLE),
    ("-100", "20", Orientation.POTENTIALLY_FAVORABLE),
    ("100", "90", Orientation.POTENTIALLY_UNFAVORABLE),
    ("20", "-100", Orientation.POTENTIALLY_UNFAVORABLE),
    ("100", "100", Orientation.NO_DIRECTIONAL_CHANGE),
])
def test_pat_yoy_loss_narrowing_sign_crossings_and_zero_are_policy_local(previous, current, orientation) -> None:
    trajectory = _flow(FinancialMetric.PAT, previous=previous, current=current)
    assert trajectory.absolute_delta == Decimal(current) - Decimal(previous)
    assert _interpret(trajectory).orientation is orientation


def test_pat_loss_narrowing_requires_no_relative_delta_or_turnaround_semantic() -> None:
    result = _interpret(_flow(FinancialMetric.PAT, previous="-100", current="-50"))
    assert result.orientation is Orientation.POTENTIALLY_FAVORABLE
    assert _flow(FinancialMetric.PAT, previous="-100", current="-50").relative_delta is None
    assert "TURNAROUND" not in result.rationale_code and "RECOVERY" not in result.rationale_code


@pytest.mark.parametrize("metric", (
    FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT,
    FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC, FinancialMetric.EPS_DILUTED,
))
@pytest.mark.parametrize("basis", (Basis.YEAR_OVER_YEAR_QUARTER, Basis.YEAR_OVER_YEAR_ANNUAL))
def test_all_and_only_approved_yoy_higher_rules_map_delta(metric, basis) -> None:
    assert _interpret(_flow(metric, previous="100", current="120", basis=basis)).orientation is Orientation.POTENTIALLY_FAVORABLE
    assert _interpret(_flow(metric, previous="120", current="100", basis=basis)).orientation is Orientation.POTENTIALLY_UNFAVORABLE
    assert _interpret(_flow(metric, previous="100", current="100", basis=basis)).orientation is Orientation.NO_DIRECTIONAL_CHANGE


def test_revenue_sequential_quarter_seasonality_firewall_including_zero() -> None:
    assert _interpret(_flow(previous="100", current="150", basis=Basis.SEQUENTIAL_QUARTER)).orientation is Orientation.CONTEXT_DEPENDENT
    assert _interpret(_flow(previous="100", current="100", basis=Basis.SEQUENTIAL_QUARTER)).orientation is Orientation.CONTEXT_DEPENDENT


def test_revenue_q4_to_q1_stays_context_dependent_after_valid_fiscal_adjacency() -> None:
    q4 = helpers._prepared(helpers._fact(
        "q4", value="100", start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 3, 31, tzinfo=UTC), year=2026, quarter=4,
    ))
    q1 = helpers._prepared(helpers._fact(
        "q1", value="150", start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 6, 30, tzinfo=UTC), year=2027, quarter=1,
    ))
    trajectory = build_financial_metric_trajectory(
        helpers._bundle(q4, q1),
        request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, Basis.SEQUENTIAL_QUARTER, q4[0].fingerprint, q1[0].fingerprint),
        policy=TRAJECTORY_POLICY,
    )
    assert trajectory.status is TrajectoryStatus.AVAILABLE
    assert _interpret(trajectory).orientation is Orientation.CONTEXT_DEPENDENT


@pytest.mark.parametrize("metric", (
    FinancialMetric.PBT, FinancialMetric.CFO, FinancialMetric.FREE_CASH_FLOW,
    FinancialMetric.OTHER_INCOME, FinancialMetric.FINANCE_COST, FinancialMetric.TAX,
    FinancialMetric.DEPRECIATION, FinancialMetric.MINORITY_INTEREST, FinancialMetric.CAPEX,
))
@pytest.mark.parametrize(("previous", "current"), (("100", "200"), ("200", "100")))
def test_flow_context_metrics_never_inherit_profit_or_cash_heuristics(metric, previous, current) -> None:
    assert _interpret(_flow(metric, previous=previous, current=current)).orientation is Orientation.CONTEXT_DEPENDENT


@pytest.mark.parametrize("metric", (
    FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS,
    FinancialMetric.RECEIVABLES, FinancialMetric.INVENTORY, FinancialMetric.PAYABLES,
))
@pytest.mark.parametrize(("previous", "current"), (("1000", "700"), ("700", "1000")))
def test_stock_context_metrics_never_inherit_balance_sheet_heuristics(metric, previous, current) -> None:
    assert _interpret(_stock(metric, previous=previous, current=current)).orientation is Orientation.CONTEXT_DEPENDENT


@pytest.mark.parametrize("metric", (FinancialMetric.CFI, FinancialMetric.CFF))
@pytest.mark.parametrize(("previous", "current"), (("-100", "-200"), ("-100", "20"), ("20", "-100"), ("0", "0")))
def test_investing_and_financing_cashflows_are_non_directional_for_any_sign(metric, previous, current) -> None:
    assert _interpret(_flow(metric, previous=previous, current=current)).orientation is Orientation.NON_DIRECTIONAL


@pytest.mark.parametrize("metric", (FinancialMetric.SHARES_OUTSTANDING, FinancialMetric.FACE_VALUE))
@pytest.mark.parametrize(("previous", "current"), (("100", "120"), ("120", "100"), ("100", "100")))
def test_share_and_face_value_are_non_directional(metric, previous, current) -> None:
    assert _interpret(_stock(metric, previous=previous, current=current)).orientation is Orientation.NON_DIRECTIONAL


def test_relative_and_sign_transition_are_descriptive_not_orientation_authority() -> None:
    pat = _flow(FinancialMetric.PAT, previous="-100", current="20")
    cfi = _flow(FinancialMetric.CFI, previous="-100", current="20")
    assert pat.sign_transition is cfi.sign_transition
    assert pat.relative_delta is cfi.relative_delta is None
    assert _interpret(pat).orientation is Orientation.POTENTIALLY_FAVORABLE
    assert _interpret(cfi).orientation is Orientation.NON_DIRECTIONAL


def test_tiny_delta_has_orientation_without_materiality_or_strength() -> None:
    up = _interpret(_flow(previous="100", current="100.000001", basis=Basis.YEAR_OVER_YEAR_ANNUAL))
    down = _interpret(_flow(previous="100", current="99.999999", basis=Basis.YEAR_OVER_YEAR_ANNUAL))
    assert (up.orientation, down.orientation) == (Orientation.POTENTIALLY_FAVORABLE, Orientation.POTENTIALLY_UNFAVORABLE)
    assert not any("MATERIAL" in field or "SIGNIFIC" in field or "STRONG" in field or "WEAK" in field for field in up.__dataclass_fields__)


def test_real_bundle_to_trajectory_to_interpretation_keeps_metrics_independent() -> None:
    revenue_old = helpers._prepared(helpers._fact("revenue-old", value="100", start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2))
    revenue_new = helpers._prepared(helpers._fact("revenue-new", value="120", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    pat_old = helpers._prepared(helpers._fact("pat-old", metric=FinancialMetric.PAT, value="-100", start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2))
    pat_new = helpers._prepared(helpers._fact("pat-new", metric=FinancialMetric.PAT, value="-50", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    debt_old = helpers._prepared(helpers._fact("debt-old", metric=FinancialMetric.TOTAL_DEBT, value="1000", start=None, end=datetime(2025, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    debt_new = helpers._prepared(helpers._fact("debt-new", metric=FinancialMetric.TOTAL_DEBT, value="700", start=None, end=datetime(2026, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    cff_old = helpers._prepared(helpers._fact("cff-old", metric=FinancialMetric.CFF, value="-100"))
    cff_new = helpers._prepared(helpers._fact("cff-new", metric=FinancialMetric.CFF, value="20", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    bundle = helpers._bundle(revenue_old, revenue_new, pat_old, pat_new, debt_old, debt_new, cff_old, cff_new)
    pairs = (
        (FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER, revenue_old[0], revenue_new[0]),
        (FinancialMetric.PAT, Basis.YEAR_OVER_YEAR_QUARTER, pat_old[0], pat_new[0]),
        (FinancialMetric.TOTAL_DEBT, Basis.POINT_IN_TIME_SEQUENTIAL, debt_old[0], debt_new[0]),
        (FinancialMetric.CFF, Basis.SEQUENTIAL_QUARTER, cff_old[0], cff_new[0]),
    )
    results = tuple(_interpret(build_financial_metric_trajectory(
        bundle, request=FinancialMetricTrajectoryRequest(metric, basis, old.fingerprint, new.fingerprint), policy=TRAJECTORY_POLICY,
    )) for metric, basis, old, new in pairs)
    assert tuple(item.orientation for item in results) == (
        Orientation.POTENTIALLY_FAVORABLE, Orientation.POTENTIALLY_FAVORABLE,
        Orientation.CONTEXT_DEPENDENT, Orientation.NON_DIRECTIONAL,
    )
    assert not hasattr(results, "financials_improved")


def test_available_only_and_exact_policy_lineages_fail_closed() -> None:
    partial = helpers._prepared(helpers._fact("partial", start=None, year=None, quarter=None))
    q2 = helpers._prepared(helpers._fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    blocked = build_financial_metric_trajectory(
        helpers._bundle(partial, q2), request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER, partial[0].fingerprint, q2[0].fingerprint), policy=TRAJECTORY_POLICY,
    )
    assert blocked.status is TrajectoryStatus.INSUFFICIENT
    with pytest.raises(ValueError, match="AVAILABLE_TRAJECTORY_REQUIRED"):
        interpret_research_metric_directionality(blocked, policy=POLICY)
    trajectory = _flow()
    object.__setattr__(trajectory, "policy_version", "v2")
    with pytest.raises(ValueError, match="TRAJECTORY_TAMPERED|TRAJECTORY_POLICY_REQUIRED"):
        interpret_research_metric_directionality(trajectory, policy=POLICY)
    changed = copy.copy(POLICY); object.__setattr__(changed, "version", "v2-approved")
    with pytest.raises(ValueError, match="POLICY_TAMPERED|EXACT_POLICY_REQUIRED"):
        interpret_research_metric_directionality(_flow(), policy=changed)


def test_policy_matrix_is_complete_exact_and_has_no_lower_favorable_rule() -> None:
    expected = {(metric, basis) for metric in FinancialMetric for basis in Basis}
    assert len(POLICY.rules) == 124
    assert {(rule.metric, rule.basis) for rule in POLICY.rules} == expected
    assert not [rule for rule in POLICY.rules if rule.disposition is Disposition.LOWER_POTENTIALLY_FAVORABLE]
    assert POLICY.selected is False and POLICY.active is False


def test_missing_duplicate_or_tampered_rule_never_defaults_to_context() -> None:
    missing = copy.copy(POLICY)
    object.__setattr__(missing, "rules", tuple(rule for rule in POLICY.rules if rule.metric is not FinancialMetric.REVENUE or rule.basis is not Basis.YEAR_OVER_YEAR_QUARTER))
    with pytest.raises(ValueError, match="POLICY_TAMPERED"):
        interpret_research_metric_directionality(_flow(), policy=missing)
    duplicate = copy.copy(POLICY)
    object.__setattr__(duplicate, "rules", POLICY.rules + (POLICY.rule_for(FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER),))
    with pytest.raises(ValueError, match="POLICY_TAMPERED"):
        interpret_research_metric_directionality(_flow(), policy=duplicate)
    target = POLICY.rule_for(FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER)
    altered = copy.copy(target); object.__setattr__(altered, "rationale_code", "OTHER")
    rules = tuple(altered if rule is target else rule for rule in POLICY.rules)
    with pytest.raises(ValueError, match="RULE_TAMPERED"):
        interpreter_module._exact_rule(type("Policy", (), {"rules": rules})(), _flow())


def test_determinism_and_input_immutability() -> None:
    trajectory = _flow(FinancialMetric.REVENUE, previous="100", current="120")
    first, second = _interpret(trajectory), _interpret(trajectory)
    assert first == second and first.fingerprint == second.fingerprint
    with pytest.raises(FrozenInstanceError):
        first.orientation = Orientation.NON_DIRECTIONAL
    assert trajectory.absolute_delta == Decimal("20")
    assert POLICY.rule_for(FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER).disposition is Disposition.HIGHER_POTENTIALLY_FAVORABLE


def test_pure_dependency_and_operational_firewall_audit() -> None:
    source = inspect.getsource(interpreter_module)
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden_imports = {
        "app.fundamentals.financial_fact_vintage_selector", "app.fundamentals.financial_metric_observation_materializer",
        "app.fundamentals.financial_research_observation_bundle_builder", "app.fundamentals.financial_research_observation_wrapper",
        "app.intelligence.brain_research_comparison_state_v2", "app.intelligence.research_state_delta",
    }
    assert not imports & forbidden_imports
    for forbidden in ("sqlite3", "requests", "urllib", "FastAPI", "APIRouter", "DecisionScore", "SixGate", "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "alert", "recommendation", "acceleration", "materiality"):
        assert forbidden not in source
    public = {name for name in interpreter_module.__all__}
    assert public == {
        "ResearchMetricDirectionalityInterpretation", "ResearchMetricDirectionalityOrientation",
        "interpret_research_metric_directionality", "research_metric_directionality_interpretation_fingerprint",
    }
