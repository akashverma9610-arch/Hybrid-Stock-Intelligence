"""U14D-5F factual comparison tests; no investment interpretation surface."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    ResearchComparabilityDomain,
    ResearchComparabilityStatus,
    ResearchSourceEligibility,
)
from app.intelligence.brain_research_comparison_state import (
    BrainResearchComparisonStateError,
    ResearchMetricObservation,
    ResearchMetricValueType,
    build_brain_research_comparison_state,
)
from app.intelligence.research_state_delta import (
    ResearchMetricChangeKind,
    ResearchStateDeltaError,
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


T1 = datetime(2026, 8, 1, tzinfo=timezone.utc)
T2 = T1 + timedelta(days=1)
I = "NSE:APOLLOHOSP"


def _reference(domain, at, *, availability=IntelligenceEvidenceAvailability.AVAILABLE, artifact=None):
    return IntelligenceEvidenceReference(
        domain=domain, availability=availability,
        artifact_ids=(artifact or f"{domain.value.lower()}:{at.date().isoformat()}",),
        artifact_fingerprints=(f"{domain.value.lower()}-fp:{at.date().isoformat()}",),
        evidence_as_of=at, observed_at=at, freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source-fp",
        historical_integrity_reference="integrity-fp", warnings=(),
    )


def _state(at, *, instrument=I, references=(), observations=()):
    unified = create_unified_intelligence_state(
        canonical_instrument_id=instrument, as_of=at, evaluation_session=at,
        state_schema_version="unified-v1", intelligence_contract_version="shared-brain-v1",
        evidence_references=tuple(sorted(references, key=lambda item: item.domain.value)),
        completeness=IntelligenceStateCompleteness.PARTIAL,
    )
    return build_brain_research_comparison_state(
        unified, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
        explicit_observations=tuple(sorted(observations, key=lambda item: (
            item.dimension.value, item.metric_id, item.value_type.value, item.source_artifact_fingerprint or "",
        ))),
    )


def _financial(value, *, scope="CONSOLIDATED", period="2026-Q1", unit="INR", scale="1", method="v1", revision="rev-1"):
    return ResearchMetricObservation(
        dimension=ResearchComparabilityDomain.FINANCIAL_RAW, metric_id="revenue",
        value_type=ResearchMetricValueType.FACTUAL_VALUE, value=Decimal(value),
        unit=unit, scale=scale, basis="REPORTED", scope=scope, period_identity=period,
        effective_at=T1 - timedelta(days=1), published_at=T1,
        lookback_or_window=None, benchmark=None, methodology_id="financial-normalization",
        methodology_version=method, source_artifact_type="FinancialFact",
        source_artifact_fingerprint="financial-fp", dependency_manifest_fingerprint=revision,
        source_eligibility=ResearchSourceEligibility.PIT_REBUILDABLE,
        freshness_status=FreshnessStatus.UNKNOWN, reliability_lineage=None,
        historical_integrity_lineage=None,
        identity_components=(("currency", "INR"),),
    )


def _dimension(delta, domain):
    return next(value for value in delta.dimension_deltas if value.dimension is domain)


def test_deterministic_immutable_factual_value_pairing_and_lineage():
    previous = _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(_financial("10"),))
    current = _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(_financial("12"),))
    first = compare_brain_research_states(previous, current, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    second = compare_brain_research_states(previous, current, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    financial = _dimension(first, ResearchComparabilityDomain.FINANCIAL_RAW)

    assert first == second and first.fingerprint == second.fingerprint
    assert first.previous_state_fingerprint == previous.fingerprint
    assert first.current_state_fingerprint == current.fingerprint
    assert financial.comparison_status is ResearchComparabilityStatus.COMPARABLE
    assert financial.observation_deltas[-1].change_kind is ResearchMetricChangeKind.VALUE_CHANGED
    with pytest.raises(FrozenInstanceError):
        first.delta_id = "replacement"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        financial.observation_deltas[-1].metric_id = "replacement"  # type: ignore[misc]


def test_identical_added_removed_and_same_label_incompatible_identity_are_factual():
    reference_1 = _reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1)
    reference_2 = _reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2)
    unchanged = compare_brain_research_states(
        _state(T1, references=(reference_1,), observations=(_financial("10"),)),
        _state(T2, references=(reference_2,), observations=(_financial("10"),)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    assert _dimension(unchanged, ResearchComparabilityDomain.FINANCIAL_RAW).observation_deltas[-1].change_kind is ResearchMetricChangeKind.UNCHANGED

    added = compare_brain_research_states(
        _state(T1, references=(reference_1,)),
        _state(T2, references=(reference_2,), observations=(_financial("10"),)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    assert _dimension(added, ResearchComparabilityDomain.FINANCIAL_RAW).observation_deltas[-1].change_kind is ResearchMetricChangeKind.ADDED

    removed = compare_brain_research_states(
        _state(T1, references=(reference_1,), observations=(_financial("10"),)),
        _state(T2, references=(reference_2,)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    assert _dimension(removed, ResearchComparabilityDomain.FINANCIAL_RAW).observation_deltas[-1].change_kind is ResearchMetricChangeKind.REMOVED

    mismatch = compare_brain_research_states(
        _state(T1, references=(reference_1,), observations=(_financial("10", scope="CONSOLIDATED"),)),
        _state(T2, references=(reference_2,), observations=(_financial("12", scope="STANDALONE"),)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    financial_mismatch = _dimension(mismatch, ResearchComparabilityDomain.FINANCIAL_RAW)
    assert financial_mismatch.comparison_status is ResearchComparabilityStatus.COMPARABLE
    assert {item.change_kind for item in financial_mismatch.observation_deltas if item.metric_id == "revenue"} == {
        ResearchMetricChangeKind.ADDED, ResearchMetricChangeKind.REMOVED,
    }


@pytest.mark.parametrize("field,value", (("scope", "STANDALONE"), ("period_identity", "2026-ANNUAL"), ("unit", "USD"), ("scale", "1000000")))
def test_different_financial_slots_are_added_removed_without_same_label_fallback(field, value):
    old = _financial("10")
    values = {name: getattr(old, name) for name in old.__dataclass_fields__}
    values[field] = value
    new = ResearchMetricObservation(**values)
    delta = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(old,)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(new,)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    financial = _dimension(delta, ResearchComparabilityDomain.FINANCIAL_RAW)
    assert financial.comparison_status is ResearchComparabilityStatus.COMPARABLE
    assert {item.change_kind for item in financial.observation_deltas if item.metric_id == "revenue"} == {
        ResearchMetricChangeKind.ADDED, ResearchMetricChangeKind.REMOVED,
    }


@pytest.mark.parametrize("field,value", (("methodology_version", "v2"), ("dependency_manifest_fingerprint", "rev-2")))
def test_same_slot_methodology_or_dependency_drift_remains_non_comparable(field, value):
    old = _financial("10")
    values = {name: getattr(old, name) for name in old.__dataclass_fields__}
    values[field] = value
    new = ResearchMetricObservation(**values)
    delta = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(old,)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(new,)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    assert _dimension(delta, ResearchComparabilityDomain.FINANCIAL_RAW).comparison_status is ResearchComparabilityStatus.NON_COMPARABLE


def test_full_slot_is_value_and_lineage_independent_but_preserves_role_and_components():
    base = _financial("100")
    revision = replace(base, value=Decimal("95"), source_artifact_fingerprint="revised-source")
    assert research_observation_slot_key(base) == research_observation_slot_key(revision)

    different_role = replace(
        base,
        source_artifact_type="FinancialNumericObservation",
        identity_components=(("currency", "INR"), ("source_role", "FINANCIAL_NUMERIC_OBSERVATION")),
    )
    assert research_observation_slot_key(base) != research_observation_slot_key(different_role)


def test_same_metric_multi_periods_match_by_full_slot_without_zip_fallback():
    q4 = replace(_financial("90", period="2025-Q4"), source_artifact_fingerprint="q4")
    q1 = replace(_financial("100", period="2026-Q1"), source_artifact_fingerprint="q1")
    revised_q1 = replace(q1, value=Decimal("95"), source_artifact_fingerprint="q1-revised")
    q2 = _financial("110", period="2026-Q2")
    delta = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(q1, q4)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(q2, revised_q1, q4)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    metrics = tuple(item for item in _dimension(delta, ResearchComparabilityDomain.FINANCIAL_RAW).observation_deltas if item.metric_id == "revenue")
    by_period = {
        (item.current_observation or item.previous_observation).period_identity: item
        for item in metrics
    }
    assert by_period["2025-Q4"].change_kind is ResearchMetricChangeKind.UNCHANGED
    assert by_period["2026-Q1"].change_kind is ResearchMetricChangeKind.VALUE_CHANGED
    assert by_period["2026-Q2"].change_kind is ResearchMetricChangeKind.ADDED
    assert len({item.semantic_slot_fingerprint for item in metrics}) == 3


def test_same_metric_removed_period_and_same_value_lineage_change_are_independent():
    q1 = replace(_financial("100", period="2026-Q1"), source_artifact_fingerprint="q1")
    q2 = replace(_financial("110", period="2026-Q2"), source_artifact_fingerprint="q2")
    revised_q2 = replace(q2, source_artifact_fingerprint="q2-revised")
    delta = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(q1, q2)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(revised_q2,)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    by_period = {
        (item.current_observation or item.previous_observation).period_identity: item
        for item in _dimension(delta, ResearchComparabilityDomain.FINANCIAL_RAW).observation_deltas
    }
    assert by_period["2026-Q1"].change_kind is ResearchMetricChangeKind.REMOVED
    assert by_period["2026-Q2"].change_kind is ResearchMetricChangeKind.LINEAGE_CHANGED


def test_duplicate_full_slot_and_duplicate_identity_component_keys_fail_closed():
    q1 = _financial("100", period="2026-Q1")
    duplicate_slot = replace(q1, source_artifact_fingerprint="same-slot-other-lineage")
    with pytest.raises(ResearchStateDeltaError, match="DUPLICATE_OBSERVATION_SLOT"):
        compare_brain_research_states(
            _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(q1, duplicate_slot)),
            _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),)),
            policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
        )

    duplicate_component_key = replace(q1, identity_components=(("scope", "A"), ("scope", "B")))
    with pytest.raises(ResearchStateDeltaError, match="IDENTITY_COMPONENT_KEYS_DUPLICATE"):
        research_observation_slot_key(duplicate_component_key)


def test_shuffled_multi_period_input_produces_identical_delta_and_slot_ordering():
    q4 = replace(_financial("90", period="2025-Q4"), source_artifact_fingerprint="q4")
    q1 = replace(_financial("100", period="2026-Q1"), source_artifact_fingerprint="q1")
    q2 = replace(_financial("110", period="2026-Q2"), source_artifact_fingerprint="q2")
    first = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(q1, q4)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(q2, q1, q4)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    second = compare_brain_research_states(
        _state(T1, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T1),), observations=(q4, q1)),
        _state(T2, references=(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS, T2),), observations=(q4, q1, q2)),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    )
    assert first == second
    financial = _dimension(first, ResearchComparabilityDomain.FINANCIAL_RAW)
    assert financial.observation_deltas == tuple(sorted(
        financial.observation_deltas,
        key=lambda item: (item.metric_id, item.semantic_slot_fingerprint, item.change_kind.value),
    ))


def test_unsupported_current_only_stale_conflicted_and_unavailable_dimensions_remain_local():
    previous = _state(T1, references=(
        _reference(IntelligenceEvidenceDomain.OWNERSHIP, T1),
        _reference(IntelligenceEvidenceDomain.TECHNICAL, T1),
        _reference(IntelligenceEvidenceDomain.MARKET_DATA, T1, availability=IntelligenceEvidenceAvailability.STALE),
        _reference(IntelligenceEvidenceDomain.RELIABILITY, T1, availability=IntelligenceEvidenceAvailability.CONFLICTED),
    ))
    current = _state(T2, references=(
        _reference(IntelligenceEvidenceDomain.OWNERSHIP, T2),
        _reference(IntelligenceEvidenceDomain.TECHNICAL, T2),
        _reference(IntelligenceEvidenceDomain.MARKET_DATA, T2, availability=IntelligenceEvidenceAvailability.STALE),
        _reference(IntelligenceEvidenceDomain.RELIABILITY, T2, availability=IntelligenceEvidenceAvailability.CONFLICTED),
    ))
    delta = compare_brain_research_states(previous, current, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    assert _dimension(delta, ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE).comparison_status is ResearchComparabilityStatus.NOT_APPLICABLE
    assert _dimension(delta, ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION).comparison_status is ResearchComparabilityStatus.INSUFFICIENT
    assert _dimension(delta, ResearchComparabilityDomain.MARKET_PRICE).comparison_status is ResearchComparabilityStatus.INSUFFICIENT
    assert _dimension(delta, ResearchComparabilityDomain.RELIABILITY).comparison_status is ResearchComparabilityStatus.NON_COMPARABLE
    assert _dimension(delta, ResearchComparabilityDomain.FINANCIAL_RAW).comparison_status is ResearchComparabilityStatus.INSUFFICIENT


def test_prebreakout_score_diagnostic_and_news_reference_deltas_remain_factual_only():
    previous = _state(T1, references=(
        _reference(IntelligenceEvidenceDomain.SETUP_OPPORTUNITY, T1, artifact="setup"),
        _reference(IntelligenceEvidenceDomain.DECISION_SCORE, T1, artifact="score"),
        _reference(IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS, T1, artifact="diagnostic"),
        _reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS, T1, artifact="news-old"),
    ))
    current = _state(T2, references=(
        _reference(IntelligenceEvidenceDomain.SETUP_OPPORTUNITY, T2, artifact="setup"),
        _reference(IntelligenceEvidenceDomain.DECISION_SCORE, T2, artifact="score"),
        _reference(IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS, T2, artifact="diagnostic"),
        _reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS, T2, artifact="news-new"),
    ))
    delta = compare_brain_research_states(previous, current, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    assert _dimension(delta, ResearchComparabilityDomain.PRE_BREAKOUT_CANDIDATE).comparison_status is ResearchComparabilityStatus.COMPARABLE
    assert _dimension(delta, ResearchComparabilityDomain.DECISION_SCORE).comparison_status is ResearchComparabilityStatus.COMPARABLE
    assert _dimension(delta, ResearchComparabilityDomain.DIAGNOSTIC).comparison_status is ResearchComparabilityStatus.COMPARABLE
    news_kinds = {item.change_kind for item in _dimension(delta, ResearchComparabilityDomain.NEWS_CATALYST).observation_deltas}
    assert news_kinds == {ResearchMetricChangeKind.ADDED, ResearchMetricChangeKind.REMOVED}
    assert not any(hasattr(delta, name) for name in ("thesis", "opportunity", "recommendation", "action", "alert", "portfolio_context"))


def test_foundational_state_and_policy_mismatches_fail_closed():
    previous = _state(T1)
    with pytest.raises(ResearchStateDeltaError, match="INSTRUMENT_MISMATCH"):
        compare_brain_research_states(previous, _state(T2, instrument="NSE:OTHER"), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    with pytest.raises(ResearchStateDeltaError, match="CHRONOLOGY_REQUIRED"):
        compare_brain_research_states(previous, _state(T1), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    with pytest.raises(ResearchStateDeltaError, match="POLICY_REQUIRED"):
        compare_brain_research_states(previous, _state(T2), policy=object())  # type: ignore[arg-type]

    bad = object.__new__(type(CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY))
    for name in CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.__dataclass_fields__:
        object.__setattr__(bad, name, getattr(CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY, name))
    object.__setattr__(bad, "fingerprint", "0" * 64)
    with pytest.raises(ResearchStateDeltaError, match="POLICY_IDENTITY_INVALID"):
        compare_brain_research_states(previous, _state(T2), policy=bad)


def test_no_database_network_api_gate_or_interpretation_surface():
    import app.intelligence.research_state_delta as module

    source = open(module.__file__, encoding="utf-8").read()
    assert not any(token in source for token in (
        "requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "project_brain_output(",
        "evaluate_six_gates", "scheduler", "worker", "listener", "recommend(", "ThesisInterpretation",
        "OpportunityInterpretation", "THESIS_STRENGTHENED", "OPPORTUNITY_IMPROVED",
    ))
