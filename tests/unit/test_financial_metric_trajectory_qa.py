"""U14D-6Y end-to-end factual QA for the frozen trajectory v1 boundary."""
from __future__ import annotations

import ast
import copy
import inspect
from datetime import UTC, datetime
from decimal import Decimal

import pytest

import test_financial_metric_trajectory as helpers
from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectoryRequest,
    build_financial_metric_trajectory,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY as POLICY,
    FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus,
)
from app.fundamentals.financial_research_observation_bundle_builder import build_financial_research_observation_bundle
from app.fundamentals.models import (
    FinancialMetric, FinancialPeriodType, FinancialValueBasis,
)


def _result(bundle, metric, basis, previous, current):
    return build_financial_metric_trajectory(
        bundle,
        request=FinancialMetricTrajectoryRequest(metric, basis, previous.fingerprint, current.fingerprint),
        policy=POLICY,
    )


def test_revision_is_rejected_at_the_same_as_of_bundle_boundary_not_reinterpreted_as_a_trajectory() -> None:
    original = helpers._prepared(helpers._fact("original", value="100"))
    revised = helpers._prepared(helpers._fact("revised", value="95"))
    with pytest.raises(ValueError, match="SEMANTIC_COLLISION"):
        helpers._bundle(original, revised)


def test_end_to_end_same_bundle_multi_metric_fixture_is_independently_factual() -> None:
    revenue_q2_25 = helpers._prepared(helpers._fact("revenue-q2-25", value="80", start=datetime(2024, 7, 1, tzinfo=UTC), end=datetime(2024, 9, 30, tzinfo=UTC), year=2025, quarter=2))
    revenue_q1_26 = helpers._prepared(helpers._fact("revenue-q1-26", value="90", start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2025, 6, 30, tzinfo=UTC), year=2026, quarter=1))
    revenue_q2_26 = helpers._prepared(helpers._fact("revenue-q2-26", value="100", start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2))
    pat_q1 = helpers._prepared(helpers._fact("pat-q1", metric=FinancialMetric.PAT, value="10"))
    pat_q2 = helpers._prepared(helpers._fact("pat-q2", metric=FinancialMetric.PAT, value="15", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    debt_old = helpers._prepared(helpers._fact("debt-old", metric=FinancialMetric.TOTAL_DEBT, value="200", start=None, end=datetime(2025, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    debt_new = helpers._prepared(helpers._fact("debt-new", metric=FinancialMetric.TOTAL_DEBT, value="180", start=None, end=datetime(2026, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    bundle = helpers._bundle(revenue_q2_25, revenue_q1_26, revenue_q2_26, pat_q1, pat_q2, debt_old, debt_new)
    revenue_yoy = _result(bundle, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER, revenue_q2_25[0], revenue_q2_26[0])
    revenue_qoq = _result(bundle, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, revenue_q1_26[0], revenue_q2_26[0])
    pat_qoq = _result(bundle, FinancialMetric.PAT, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, pat_q1[0], pat_q2[0])
    debt = _result(bundle, FinancialMetric.TOTAL_DEBT, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, debt_old[0], debt_new[0])
    assert [item.status for item in (revenue_yoy, revenue_qoq, pat_qoq, debt)] == [FinancialMetricTrajectoryStatus.AVAILABLE] * 4
    assert [item.absolute_delta for item in (revenue_yoy, revenue_qoq, pat_qoq, debt)] == [Decimal("20"), Decimal("10"), Decimal("5"), Decimal("-20")]
    assert {item.bundle_as_of for item in (revenue_yoy, revenue_qoq, pat_qoq, debt)} == {helpers.T}


def test_publication_order_does_not_override_point_in_time_economic_period_end() -> None:
    later_economic = helpers._prepared(helpers._fact("later", metric=FinancialMetric.TOTAL_ASSETS, value="120", start=None, end=datetime(2026, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    earlier_economic = helpers._prepared(helpers._fact("earlier", metric=FinancialMetric.TOTAL_ASSETS, value="100", start=None, end=datetime(2025, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    bundle = helpers._bundle(later_economic, earlier_economic)
    assert _result(bundle, FinancialMetric.TOTAL_ASSETS, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, earlier_economic[0], later_economic[0]).status is FinancialMetricTrajectoryStatus.AVAILABLE
    assert _result(bundle, FinancialMetric.TOTAL_ASSETS, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, later_economic[0], earlier_economic[0]).status is FinancialMetricTrajectoryStatus.NOT_APPLICABLE


def test_cumulative_cashflow_ttm_and_cross_period_requests_cannot_create_new_v1_trajectories() -> None:
    q1 = helpers._prepared(helpers._fact("q1", metric=FinancialMetric.CFO, value="10"))
    h1 = helpers._prepared(helpers._fact("h1", metric=FinancialMetric.CFO, value="25", basis=FinancialValueBasis.YEAR_TO_DATE, start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    result = _result(helpers._bundle(q1, h1), FinancialMetric.CFO, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], h1[0])
    assert result.status is FinancialMetricTrajectoryStatus.NON_COMPARABLE and result.absolute_delta is None
    with pytest.raises(ValueError, match="TYPE_REQUIRED"):
        FinancialMetricTrajectoryRequest(FinancialMetric.CFO, "TRAILING_TWELVE_MONTHS")  # type: ignore[arg-type]


def test_explicit_pairs_wrong_fingerprints_and_all_statuses_fail_closed_or_remain_factual() -> None:
    q1 = helpers._prepared(helpers._fact("q1")); q2 = helpers._prepared(helpers._fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    bundle = helpers._bundle(q1, q2)
    assert _result(bundle, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], q2[0]).status is FinancialMetricTrajectoryStatus.AVAILABLE
    missing = build_financial_metric_trajectory(bundle, request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, "missing-a", "missing-b"), policy=POLICY)
    assert missing.status is FinancialMetricTrajectoryStatus.INSUFFICIENT
    assert _result(bundle, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, q1[0], q2[0]).status is FinancialMetricTrajectoryStatus.NOT_APPLICABLE
    standalone = helpers._prepared(helpers._fact("standalone", scope=helpers.StatementScope.STANDALONE, start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    assert _result(helpers._bundle(q1, standalone), FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], standalone[0]).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE


def test_policy_and_artifact_tampering_fail_closed_and_observation_order_is_deterministic() -> None:
    q1 = helpers._prepared(helpers._fact("q1")); q2 = helpers._prepared(helpers._fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    first, second = helpers._bundle(q1, q2), helpers._bundle(q2, q1)
    assert _result(first, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], q2[0]) == _result(second, FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], q2[0])
    changed = copy.copy(POLICY); object.__setattr__(changed, "policy_id", "other")
    with pytest.raises(ValueError, match="POLICY_TAMPERED|EXACT_POLICY_REQUIRED"):
        build_financial_metric_trajectory(first, request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER), policy=changed)
    object.__setattr__(first.observations[0], "fingerprint", "0" * 64)
    with pytest.raises(ValueError, match="BUNDLE_TAMPERED|OBSERVATION_TAMPERED"):
        build_financial_metric_trajectory(first, request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER), policy=POLICY)


def test_tiny_movement_is_available_without_materiality_and_no_semantic_runtime_dependencies_exist() -> None:
    q1 = helpers._prepared(helpers._fact("q1", value="100")); q2 = helpers._prepared(helpers._fact("q2", value="100.0001", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    assert _result(helpers._bundle(q1, q2), FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0], q2[0]).status is FinancialMetricTrajectoryStatus.AVAILABLE
    source = inspect.getsource(__import__("app.fundamentals.financial_metric_trajectory", fromlist=["*"]))
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden = {"app.fundamentals.financial_fact_vintage_selector", "app.fundamentals.financial_metric_observation_materializer", "app.fundamentals.financial_research_observation_bundle_builder", "app.fundamentals.financial_research_observation_wrapper", "app.intelligence.brain_research_comparison_state_v2", "app.intelligence.research_state_delta"}
    assert not imports & forbidden
    for forbidden_term in ("IMPROVED", "DEGRADED", "FAVORABLE", "UNFAVORABLE", "THESIS_STRENGTHENED", "OPPORTUNITY_IMPROVED", "BUY", "SELL", "TTM", "acceleration"):
        assert forbidden_term not in source
