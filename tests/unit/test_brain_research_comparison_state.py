"""U14D-5E single-state contract tests: no comparison or interpretation."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    ResearchComparabilityDomain,
    ResearchSourceEligibility,
)
from app.intelligence.brain_research_comparison_state import (
    BrainResearchComparisonStateError,
    ResearchMetricObservation,
    ResearchMetricValueType,
    build_brain_research_comparison_state,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)


T = datetime(2026, 8, 29, 9, 15, tzinfo=timezone.utc)
I = "NSE:APOLLOHOSP"


def _reference(
    domain: IntelligenceEvidenceDomain,
    *,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    observed_at: datetime | None = T,
    warnings: tuple[str, ...] = (),
) -> IntelligenceEvidenceReference:
    return IntelligenceEvidenceReference(
        domain=domain,
        availability=availability,
        artifact_ids=(f"{domain.value.lower()}-artifact",),
        artifact_fingerprints=(f"{domain.value.lower()}-fp",),
        evidence_as_of=T,
        observed_at=observed_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference="freshness-v1",
        source_provenance_fingerprint=f"{domain.value.lower()}-provenance",
        historical_integrity_reference="integrity-fp",
        warnings=warnings,
    )


def _state(*references: IntelligenceEvidenceReference):
    return create_unified_intelligence_state(
        canonical_instrument_id=I,
        as_of=T,
        evaluation_session=T,
        state_schema_version="unified-v1",
        intelligence_contract_version="shared-brain-v1",
        evidence_references=tuple(sorted(references, key=lambda item: item.domain.value)),
        completeness=IntelligenceStateCompleteness.PARTIAL,
    )


def _build(*references: IntelligenceEvidenceReference, observations=()):
    return build_brain_research_comparison_state(
        _state(*references),
        policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
        explicit_observations=tuple(sorted(observations, key=lambda item: (
            item.dimension.value, item.metric_id, item.value_type.value, item.source_artifact_fingerprint or "",
        ))),
    )


def _dimension(state, domain: ResearchComparabilityDomain):
    return next(item for item in state.dimensions if item.dimension is domain)


def test_single_state_is_deterministic_immutable_and_preserves_unified_lineage():
    source = _state(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS))
    first = build_brain_research_comparison_state(source, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    second = build_brain_research_comparison_state(source, policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)

    assert first == second
    assert first.fingerprint == second.fingerprint
    assert first.canonical_instrument_id == I
    assert first.as_of == T
    assert first.source_unified_state_id == source.state_id
    assert first.source_unified_state_fingerprint == source.fingerprint
    with pytest.raises(FrozenInstanceError):
        first.state_id = "replacement"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.dimensions[0].availability = IntelligenceEvidenceAvailability.AVAILABLE  # type: ignore[misc]


def test_exact_frozen_inactive_policy_is_required_without_global_fallback():
    source = _state()
    with pytest.raises(BrainResearchComparisonStateError, match="POLICY_REQUIRED"):
        build_brain_research_comparison_state(source, policy=object())  # type: ignore[arg-type]
    for field, value in (("policy_id", "wrong"), ("version", "v2"), ("fingerprint", "0" * 64)):
        policy = object.__new__(type(CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY))
        for name in CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.__dataclass_fields__:
            object.__setattr__(policy, name, getattr(CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY, name))
        object.__setattr__(policy, field, value)
        with pytest.raises(BrainResearchComparisonStateError, match="POLICY_IDENTITY_INVALID"):
            build_brain_research_comparison_state(source, policy=policy)
    assert CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.active is False
    assert CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY.selected_for_future_comparator is False

def test_all_policy_dimensions_are_explicit_and_policy_limited_dimensions_are_not_omitted():
    state = _build(_reference(IntelligenceEvidenceDomain.OWNERSHIP))
    assert tuple(item.dimension for item in state.dimensions) == tuple(sorted(ResearchComparabilityDomain, key=lambda item: item.value))
    ownership = _dimension(state, ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE)
    valuation = _dimension(state, ResearchComparabilityDomain.VALUATION)
    assert ownership.source_eligibility is ResearchSourceEligibility.UNSUPPORTED
    assert ownership.availability is IntelligenceEvidenceAvailability.NOT_APPLICABLE
    assert "OWNERSHIP_PERCENTAGES_UNSUPPORTED" in ownership.blockers
    assert valuation.source_eligibility is ResearchSourceEligibility.UNSUPPORTED
    assert "VALUATION_COMPARISON_UNSUPPORTED" in valuation.blockers


def test_reference_and_explicit_factual_observations_preserve_typed_non_directional_lineage():
    observation = ResearchMetricObservation(
        dimension=ResearchComparabilityDomain.FINANCIAL_RAW,
        metric_id="revenue-q1",
        value_type=ResearchMetricValueType.FACTUAL_VALUE,
        value=Decimal("70435000000"),
        unit="INR", scale="1", basis="REPORTED", scope="CONSOLIDATED",
        period_identity="2026-Q1", effective_at=T - timedelta(days=1), published_at=T,
        lookback_or_window=None, benchmark=None,
        methodology_id="financial-fact", methodology_version="v1",
        source_artifact_type="FinancialFact", source_artifact_fingerprint="financial-fp",
        dependency_manifest_fingerprint="filing-fp",
        source_eligibility=ResearchSourceEligibility.PIT_REBUILDABLE,
        freshness_status=FreshnessStatus.UNKNOWN,
        reliability_lineage=None, historical_integrity_lineage=None,
        identity_components=(("currency", "INR"), ("scope", "CONSOLIDATED")),
    )
    state = _build(_reference(IntelligenceEvidenceDomain.FUNDAMENTALS), observations=(observation,))
    financial = _dimension(state, ResearchComparabilityDomain.FINANCIAL_RAW)
    assert observation in financial.observations
    assert financial.descriptor.source_eligibility is ResearchSourceEligibility.PIT_REBUILDABLE
    assert not hasattr(financial, "comparability_status")
    assert "improved" not in repr(state).lower()


def test_future_evidence_and_explicit_later_observations_fail_closed_instead_of_backdating():
    future = _reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS, observed_at=T + timedelta(seconds=1))
    with pytest.raises(BrainResearchComparisonStateError, match="SOURCE_EVIDENCE_AFTER_AS_OF"):
        _build(future)

    later = ResearchMetricObservation(
        dimension=ResearchComparabilityDomain.NEWS_CATALYST,
        metric_id="later-event", value_type=ResearchMetricValueType.FACTUAL_VALUE,
        value="event", unit=None, scale=None, basis=None, scope=None, period_identity=None,
        effective_at=None, published_at=T + timedelta(seconds=1), lookback_or_window=None, benchmark=None,
        methodology_id=None, methodology_version=None, source_artifact_type="News", source_artifact_fingerprint="news-fp",
        dependency_manifest_fingerprint=None, source_eligibility=ResearchSourceEligibility.PIT_REBUILDABLE,
        freshness_status=FreshnessStatus.UNKNOWN, reliability_lineage=None, historical_integrity_lineage=None,
    )
    with pytest.raises(BrainResearchComparisonStateError, match="OBSERVATION_AFTER_AS_OF"):
        _build(observations=(later,))


def test_current_only_stale_conflicted_and_invalid_lineage_remain_explicit_limitations():
    state = _build(
        _reference(IntelligenceEvidenceDomain.TECHNICAL),
        _reference(IntelligenceEvidenceDomain.RELIABILITY, availability=IntelligenceEvidenceAvailability.CONFLICTED),
        _reference(IntelligenceEvidenceDomain.MARKET_DATA, availability=IntelligenceEvidenceAvailability.STALE),
    )
    technical = _dimension(state, ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION)
    price = _dimension(state, ResearchComparabilityDomain.MARKET_PRICE)
    reliability = _dimension(state, ResearchComparabilityDomain.RELIABILITY)
    assert technical.source_eligibility is ResearchSourceEligibility.CURRENT_ONLY
    assert "CURRENT_ONLY_EVIDENCE_NOT_HISTORICALLY_RETROJECTED" in technical.warnings
    assert price.availability is IntelligenceEvidenceAvailability.STALE
    assert "EVIDENCE_STALE" in price.blockers
    assert reliability.availability is IntelligenceEvidenceAvailability.CONFLICTED
    assert "RELIABILITY_OR_INTEGRITY_CONFLICTED" in reliability.blockers


def test_native_integrity_reference_is_retained_without_reverse_engineering_a_status():
    state = _build(_reference(IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY, availability=IntelligenceEvidenceAvailability.CONFLICTED))
    price = _dimension(state, ResearchComparabilityDomain.MARKET_PRICE)
    assert any(item.source_artifact_type == IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY.value for item in price.observations)
    assert price.availability is IntelligenceEvidenceAvailability.CONFLICTED
    assert not any(item.metric_id == "historical_integrity_status" for item in price.observations)


def test_diagnostic_score_and_setup_are_only_retained_as_existing_artifact_lineage():
    state = _build(
        _reference(IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS),
        _reference(IntelligenceEvidenceDomain.DECISION_SCORE),
        _reference(IntelligenceEvidenceDomain.SETUP_OPPORTUNITY),
    )
    for domain in (
        ResearchComparabilityDomain.DIAGNOSTIC,
        ResearchComparabilityDomain.DECISION_SCORE,
        ResearchComparabilityDomain.PRE_BREAKOUT_CANDIDATE,
    ):
        dimension = _dimension(state, domain)
        assert dimension.source_eligibility is ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY
        assert dimension.observations
        assert all(item.value_type is ResearchMetricValueType.ARTIFACT_REFERENCE for item in dimension.observations)


def test_module_exposes_no_comparator_delta_portfolio_gate_or_action_surface():
    import app.intelligence.brain_research_comparison_state as module

    forbidden = {"compare_brain_research_states", "ResearchStateDelta", "BUY", "SELL", "THESIS_STRENGTHENED"}
    assert not any(hasattr(module, name) for name in forbidden)
    assert "PortfolioContextRef" not in module.__dict__
