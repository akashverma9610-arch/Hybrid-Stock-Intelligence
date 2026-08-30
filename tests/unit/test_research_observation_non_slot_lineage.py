from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

import app.intelligence.brain_research_comparison_state as state_module
from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
    ResearchSourceEligibility,
)
from app.intelligence.brain_research_comparison_state import (
    BrainResearchComparisonStateError,
    ResearchMetricObservation,
    ResearchMetricValueType,
    build_brain_research_comparison_state,
    research_metric_observation_fingerprint,
)
from app.intelligence.research_state_delta import (
    ResearchMetricChangeKind,
    compare_brain_research_states,
    research_observation_slot_key,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)


T1 = datetime(2026, 8, 29, 10, tzinfo=UTC)
T2 = T1 + timedelta(days=1)


def _observation(*, value: str = "100", period: str = "period-q1", lineage=(), role: FinancialObservationSourceRole = FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION) -> ResearchMetricObservation:
    return ResearchMetricObservation(
        dimension=ResearchComparabilityDomain.FINANCIAL_RAW,
        metric_id="REVENUE", value_type=ResearchMetricValueType.FACTUAL_VALUE,
        value=Decimal(value), unit="INR", scale="CRORES", basis="QUARTER_ONLY",
        scope="CONSOLIDATED", period_identity=period, effective_at=T1 - timedelta(days=60),
        published_at=T1 - timedelta(days=3), lookback_or_window=None, benchmark=None,
        methodology_id="financial-research-observation-wrapper-schema", methodology_version="v1-approved",
        source_artifact_type="FINANCIAL_METRIC_OBSERVATION",
        source_artifact_fingerprint="financial-observation-fingerprint",
        dependency_manifest_fingerprint="financial-contract-lineage",
        source_eligibility=ResearchSourceEligibility.PIT_REBUILDABLE,
        freshness_status=FreshnessStatus.UNKNOWN, reliability_lineage=None,
        historical_integrity_lineage=None,
        identity_components=(
            ("financial_currency", "INR"),
            ("financial_fact_kind", "REPORTED"),
            ("financial_observation_schema_identity", "financial-metric-observation-schema:v1-approved"),
            ("financial_period_fingerprint", period),
            ("financial_source_role", role.value),
            ("financial_value_dimension", "MONETARY"),
        ),
        lineage_components=tuple(lineage),
    )


def _state(at: datetime, observation: ResearchMetricObservation):
    reference = IntelligenceEvidenceReference(
        domain=IntelligenceEvidenceDomain.FUNDAMENTALS,
        availability=IntelligenceEvidenceAvailability.AVAILABLE,
        artifact_ids=("financial-evidence",), artifact_fingerprints=("financial-evidence-fingerprint",),
        evidence_as_of=at, observed_at=at, freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source-fingerprint",
        historical_integrity_reference=None, warnings=(),
    )
    unified = create_unified_intelligence_state(
        canonical_instrument_id="NSE:ALPHA", as_of=at, evaluation_session=at,
        state_schema_version="unified-v1", intelligence_contract_version="shared-brain-v1",
        evidence_references=(reference,), completeness=IntelligenceStateCompleteness.PARTIAL,
    )
    return build_brain_research_comparison_state(
        unified, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
        explicit_observations=(observation,),
    )


def _financial_delta(delta):
    return next(value for value in delta.dimension_deltas if value.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)


def test_non_slot_lineage_is_immutable_canonical_and_backward_compatible() -> None:
    empty = _observation()
    assert empty.lineage_components == ()
    old_shape = {
        field: state_module._semantic_value(getattr(empty, field))
        for field in empty.__dataclass_fields__ if field != "lineage_components"
    }
    assert research_metric_observation_fingerprint(empty) == manifest_fingerprint(**old_shape)
    ordered = _observation(lineage=(("financial_source_fact_id", "fact-1"), ("financial_visible_as_of", "2026-08-01T00:00:00+00:00")))
    assert ordered.lineage_components[0][0] == "financial_source_fact_id"
    with pytest.raises(FrozenInstanceError):
        ordered.lineage_components = ()  # type: ignore[misc]
    with pytest.raises(BrainResearchComparisonStateError, match="LINEAGE_NONCANONICAL"):
        _observation(lineage=(("z", "1"), ("a", "2")))
    with pytest.raises(BrainResearchComparisonStateError, match="LINEAGE_KEYS_DUPLICATE"):
        _observation(lineage=(("a", "1"), ("a", "2")))


def test_lineage_changes_artifact_fingerprint_but_not_full_observation_slot() -> None:
    first = _observation(lineage=(("financial_source_fact_id", "fact-1"),))
    second = _observation(lineage=(("financial_source_fact_id", "fact-2"),))
    assert research_observation_slot_key(first) == research_observation_slot_key(second)
    assert research_metric_observation_fingerprint(first) != research_metric_observation_fingerprint(second)
    assert research_observation_slot_key(first) == research_observation_slot_key(replace(first, value=Decimal("95")))
    assert research_observation_slot_key(first) != research_observation_slot_key(replace(first, period_identity="period-q2"))
    reference = replace(
        first, source_artifact_type="FINANCIAL_EVIDENCE_REFERENCE",
        identity_components=tuple(sorted(
            (*(item for item in first.identity_components if item[0] != "financial_source_role"),
             ("financial_source_role", FinancialObservationSourceRole.FINANCIAL_EVIDENCE_REFERENCE.value))
        )),
    )
    assert research_observation_slot_key(first) != research_observation_slot_key(reference)


def test_delta_reports_lineage_change_without_added_removed_and_value_change_remains_primary_kind() -> None:
    first = _observation(value="100", lineage=(("financial_source_fact_id", "fact-1"),))
    revised = _observation(value="100", lineage=(("financial_source_fact_id", "fact-2"),))
    lineage_delta = _financial_delta(compare_brain_research_states(
        _state(T1, first), _state(T2, revised), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )).observation_deltas[-1]
    assert lineage_delta.change_kind is ResearchMetricChangeKind.LINEAGE_CHANGED
    assert lineage_delta.previous_observation_fingerprint != lineage_delta.current_observation_fingerprint

    value_and_lineage = _financial_delta(compare_brain_research_states(
        _state(T1, first), _state(T2, _observation(value="95", lineage=(("financial_source_fact_id", "fact-2"),))),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )).observation_deltas[-1]
    assert value_and_lineage.change_kind is ResearchMetricChangeKind.VALUE_CHANGED
    assert {value_and_lineage.previous_observation_fingerprint, value_and_lineage.current_observation_fingerprint} == {
        research_metric_observation_fingerprint(first),
        research_metric_observation_fingerprint(_observation(value="95", lineage=(("financial_source_fact_id", "fact-2"),))),
    }


def test_non_slot_lineage_has_no_wrapper_or_operational_dependency() -> None:
    source = inspect.getsource(state_module)
    for forbidden in (
        "wrap_financial_research_observation_bundle", "FinancialFactVintageSelection",
        "materialize_financial_metric_observation", "sqlite3", "requests", "urllib", "FastAPI",
        "FinancialMetricTrajectory", "QoQ", "YoY", "THESIS_", "OPPORTUNITY_", "BUY", "SELL",
    ):
        assert forbidden not in source
