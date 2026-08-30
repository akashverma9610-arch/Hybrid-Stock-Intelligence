"""U15 integration tests for one read-only Production-v1 Shared Brain."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from decimal import Decimal
import ast
import copy
import inspect

import pytest

import test_brain_research_comparison_state_v2 as v2_helpers
import test_financial_metric_trajectory as facts
import app.intelligence.shared_brain_production as module
from app.domain.models import FreshnessStatus
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY as TRAJECTORY_POLICY,
    FinancialMetricTrajectoryBasis as Basis,
)
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA as WRAPPER_SCHEMA,
)
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis
from app.intelligence.brain_research_comparability_policy import FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2
from app.intelligence.research_metric_directionality import ResearchMetricDirectionalityOrientation as Orientation
from app.intelligence.research_metric_directionality_policy import CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY as DIRECTIONALITY_POLICY
from app.intelligence.research_semantic_materiality_policy import CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY as MATERIALITY_POLICY
from app.intelligence.shared_brain_production import (
    SharedBrainMaterialityCalibrationStatus as CalibrationStatus,
    build_shared_brain_production_snapshot,
    enumerate_financial_trajectory_requests,
    project_shared_brain_production_snapshot,
    shared_brain_production_snapshot_fingerprint,
)
from app.intelligence.unified_state import (
    BrainOutputContext, IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference, IntelligenceStateCompleteness, create_unified_intelligence_state,
)


T = facts.T


def _prepared(fact):
    return v2_helpers._prepared(fact, as_of=T)


def _bundle(*items, failures=()):
    return v2_helpers._bundle(*items, as_of=T, failures=failures)


def _unified(*, as_of=T):
    reference = IntelligenceEvidenceReference(
        domain=IntelligenceEvidenceDomain.FUNDAMENTALS,
        availability=IntelligenceEvidenceAvailability.AVAILABLE,
        artifact_ids=("fundamental-reference",), artifact_fingerprints=("fundamental-reference-fingerprint",),
        evidence_as_of=as_of, observed_at=as_of, freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source-fingerprint",
        historical_integrity_reference=None, warnings=(),
    )
    return create_unified_intelligence_state(
        canonical_instrument_id="NSE:ALPHA", as_of=as_of, evaluation_session=as_of,
        state_schema_version="unified-v1", intelligence_contract_version="shared-brain-v1",
        evidence_references=(reference,), completeness=IntelligenceStateCompleteness.PARTIAL,
    )


def _snapshot(bundle, *, failures=None):
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA)
    return build_shared_brain_production_snapshot(
        _unified(), comparability_policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
        financial_bundle=bundle, financial_wrappers=wrappers,
        financial_failures=bundle.failures if failures is None else failures,
        trajectory_policy=TRAJECTORY_POLICY, directionality_policy=DIRECTIONALITY_POLICY,
        materiality_policy=MATERIALITY_POLICY,
    )


def _quarter(identifier, *, metric=FinancialMetric.REVENUE, value="100", year=2026, quarter=1, start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2025, 6, 30, tzinfo=UTC)):
    return facts._fact(identifier, metric=metric, value=value, year=year, quarter=quarter, start=start, end=end)


def _rich_bundle():
    values = (
        _prepared(_quarter("revenue-q1-25", value="80", year=2025, quarter=1, start=datetime(2024, 4, 1, tzinfo=UTC), end=datetime(2024, 6, 30, tzinfo=UTC))),
        _prepared(_quarter("revenue-q2-25", value="100", year=2025, quarter=2, start=datetime(2024, 7, 1, tzinfo=UTC), end=datetime(2024, 9, 30, tzinfo=UTC))),
        _prepared(_quarter("revenue-q4-25", value="120", year=2025, quarter=4, start=datetime(2025, 1, 1, tzinfo=UTC), end=datetime(2025, 3, 31, tzinfo=UTC))),
        _prepared(_quarter("revenue-q1-26", value="130", year=2026, quarter=1, start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2025, 6, 30, tzinfo=UTC))),
        _prepared(_quarter("revenue-q2-26", value="150", year=2026, quarter=2, start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC))),
        _prepared(_quarter("pat-q2-25", metric=FinancialMetric.PAT, value="-100", year=2025, quarter=2, start=datetime(2024, 7, 1, tzinfo=UTC), end=datetime(2024, 9, 30, tzinfo=UTC))),
        _prepared(_quarter("pat-q2-26", metric=FinancialMetric.PAT, value="-50", year=2026, quarter=2, start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC))),
        _prepared(_quarter("cfi-q1", metric=FinancialMetric.CFI, value="-100", year=2026, quarter=1, start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2025, 6, 30, tzinfo=UTC))),
        _prepared(_quarter("cfi-q2", metric=FinancialMetric.CFI, value="20", year=2026, quarter=2, start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC))),
        _prepared(facts._fact("annual-25", value="500", year=2025, quarter=None, start=datetime(2023, 4, 1, tzinfo=UTC), end=datetime(2024, 3, 31, tzinfo=UTC), period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR)),
        _prepared(facts._fact("annual-26", value="600", year=2026, quarter=None, start=datetime(2024, 4, 1, tzinfo=UTC), end=datetime(2025, 3, 31, tzinfo=UTC), period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR)),
        _prepared(facts._fact("debt-25", metric=FinancialMetric.TOTAL_DEBT, value="1000", year=None, quarter=None, start=None, end=datetime(2025, 3, 31, tzinfo=UTC), period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY)),
        _prepared(facts._fact("debt-26", metric=FinancialMetric.TOTAL_DEBT, value="700", year=None, quarter=None, start=None, end=datetime(2026, 3, 31, tzinfo=UTC), period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY)),
    )
    return _bundle(*values)


def _request_pairs(bundle):
    observations = {value.fingerprint: value for value in bundle.observations}
    return {
        (request.metric, request.basis, observations[request.previous_observation_fingerprint].source_fact_id, observations[request.current_observation_fingerprint].source_fact_id)
        for request in enumerate_financial_trajectory_requests(bundle, policy=TRAJECTORY_POLICY)
    }


def test_snapshot_is_immutable_deterministic_and_preserves_exact_as_of_lineage():
    bundle = _rich_bundle()
    first, second = _snapshot(bundle), _snapshot(bundle)
    assert first == second and first.fingerprint == shared_brain_production_snapshot_fingerprint(first)
    assert (first.canonical_instrument_id, first.as_of) == ("NSE:ALPHA", T)
    assert first.unified_state.fingerprint == first.brain_research_state_v2.source_unified_state_fingerprint
    assert first.financial_bundle.fingerprint == bundle.fingerprint
    with pytest.raises(FrozenInstanceError):
        first.materiality_calibration_status = CalibrationStatus.CALIBRATION_REQUIRED


def test_bounded_enumeration_covers_proven_quarterly_yoy_annual_and_point_in_time_pairs():
    pairs = _request_pairs(_rich_bundle())
    assert (FinancialMetric.REVENUE, Basis.SEQUENTIAL_QUARTER, "revenue-q1-25", "revenue-q2-25") in pairs
    assert (FinancialMetric.REVENUE, Basis.SEQUENTIAL_QUARTER, "revenue-q4-25", "revenue-q1-26") in pairs
    assert (FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_QUARTER, "revenue-q2-25", "revenue-q2-26") in pairs
    assert (FinancialMetric.REVENUE, Basis.YEAR_OVER_YEAR_ANNUAL, "annual-25", "annual-26") in pairs
    assert (FinancialMetric.TOTAL_DEBT, Basis.POINT_IN_TIME_SEQUENTIAL, "debt-25", "debt-26") in pairs
    assert not any(previous == "revenue-q2-25" and current == "revenue-q4-25" for _, _, previous, current in pairs)


def test_snapshot_reuses_existing_trajectory_and_directionality_artifacts_without_aggregation():
    snapshot = _snapshot(_rich_bundle())
    by_pair = {(item.metric, item.trajectory_basis): item for item in snapshot.directionality_interpretations}
    assert by_pair[("REVENUE", "YEAR_OVER_YEAR_QUARTER")].orientation is Orientation.POTENTIALLY_FAVORABLE
    assert by_pair[("REVENUE", "SEQUENTIAL_QUARTER")].orientation is Orientation.CONTEXT_DEPENDENT
    assert by_pair[("PAT", "YEAR_OVER_YEAR_QUARTER")].orientation is Orientation.POTENTIALLY_FAVORABLE
    assert by_pair[("TOTAL_DEBT", "POINT_IN_TIME_SEQUENTIAL")].orientation is Orientation.CONTEXT_DEPENDENT
    assert by_pair[("CFI", "SEQUENTIAL_QUARTER")].orientation is Orientation.NON_DIRECTIONAL
    assert all(item.absolute_delta is not None for item in snapshot.financial_trajectories)
    assert not hasattr(snapshot, "financials_improved")


def test_materiality_is_lineage_only_and_never_classifies_a_movement():
    snapshot = _snapshot(_rich_bundle())
    assert snapshot.materiality_calibration_status is CalibrationStatus.CALIBRATION_REQUIRED
    assert snapshot.materiality_policy_fingerprint == MATERIALITY_POLICY.fingerprint
    assert not any("MATERIAL" in field or "IMMATERIAL" in field for field in snapshot.__dataclass_fields__)


@pytest.mark.parametrize("context", tuple(BrainOutputContext))
def test_all_existing_contexts_reference_the_same_financial_semantic_section(context):
    snapshot = _snapshot(_rich_bundle())
    projection = project_shared_brain_production_snapshot(snapshot, output_context=context)
    assert projection.output_context is context
    assert projection.shared_brain_snapshot_fingerprint == snapshot.fingerprint
    assert projection.trajectory_fingerprints == tuple(sorted(value.fingerprint for value in snapshot.financial_trajectories))
    assert projection.directionality_fingerprints == tuple(sorted(value.fingerprint for value in snapshot.directionality_interpretations))


def test_context_views_have_different_view_fingerprints_but_identical_semantic_artifact_fingerprints():
    snapshot = _snapshot(_rich_bundle())
    deep = project_shared_brain_production_snapshot(snapshot, output_context=BrainOutputContext.DEEP_ANALYSIS)
    portfolio = project_shared_brain_production_snapshot(snapshot, output_context=BrainOutputContext.PORTFOLIO_REVIEW)
    sell = project_shared_brain_production_snapshot(snapshot, output_context=BrainOutputContext.SELL_TRIM_REVIEW)
    opportunity = project_shared_brain_production_snapshot(snapshot, output_context=BrainOutputContext.OPPORTUNITY_DISCOVERY)
    assert len({deep.fingerprint, portfolio.fingerprint, sell.fingerprint, opportunity.fingerprint}) == 4
    assert {value.financial_semantic_section_fingerprint for value in (deep, portfolio, sell, opportunity)} == {deep.financial_semantic_section_fingerprint}
    assert {value.directionality_fingerprints for value in (deep, portfolio, sell, opportunity)} == {deep.directionality_fingerprints}


def test_failures_remain_dimension_local_and_empty_financial_semantics_remain_valid():
    failure = v2_helpers._failure(as_of=T)
    failed_bundle = _bundle(failures=(failure,))
    failed = _snapshot(failed_bundle)
    assert not failed.financial_trajectories and not failed.directionality_interpretations
    assert failed.financial_failures == (failure,)
    assert "NO_PIT_ELIGIBLE_FACT" in failed.warnings


def test_shuffled_bundle_input_and_tampered_policy_or_mixed_as_of_fail_closed():
    bundle = _rich_bundle()
    q1 = _prepared(_quarter("canonical-q1", value="100", year=2026, quarter=1))
    q2 = _prepared(_quarter("canonical-q2", value="120", year=2026, quarter=2, start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC)))
    first, reversed_bundle = _bundle(q1, q2), _bundle(q2, q1)
    assert enumerate_financial_trajectory_requests(first, policy=TRAJECTORY_POLICY) == enumerate_financial_trajectory_requests(reversed_bundle, policy=TRAJECTORY_POLICY)
    changed = copy.copy(MATERIALITY_POLICY); object.__setattr__(changed, "version", "v2-approved")
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA)
    with pytest.raises(ValueError, match="MATERIALITY_POLICY_REQUIRED"):
        build_shared_brain_production_snapshot(_unified(), comparability_policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2, financial_bundle=bundle, financial_wrappers=wrappers, financial_failures=bundle.failures, trajectory_policy=TRAJECTORY_POLICY, directionality_policy=DIRECTIONALITY_POLICY, materiality_policy=changed)
    foreign_state = _unified(as_of=datetime(2026, 8, 30, 10, tzinfo=UTC))
    with pytest.raises(Exception, match="AS_OF_MISMATCH"):
        build_shared_brain_production_snapshot(foreign_state, comparability_policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2, financial_bundle=bundle, financial_wrappers=wrappers, financial_failures=bundle.failures, trajectory_policy=TRAJECTORY_POLICY, directionality_policy=DIRECTIONALITY_POLICY, materiality_policy=MATERIALITY_POLICY)


def test_module_is_pure_and_does_not_introduce_a_second_brain_or_action_surface():
    source = inspect.getsource(module)
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    assert not imports & {"sqlite3", "requests", "urllib", "app.scoring.engine", "app.intelligence.research_state_delta"}
    for forbidden in ("FinancialBrain", "ScannerBrain", "PortfolioBrain", "DirectionalityBrain", "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "recommendation", "order(", "paper_trade", "FastAPI", "APIRouter", "datetime.now", "utcnow"):
        assert forbidden not in source
