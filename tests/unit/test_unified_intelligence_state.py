from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceDependencyReference,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    IntelligenceStateCompleteness,
    PortfolioContextRef,
    UnifiedIntelligenceStateError,
    create_brain_output_request,
    create_unified_intelligence_state,
)


T = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _reference(
    domain: IntelligenceEvidenceDomain = IntelligenceEvidenceDomain.MARKET_DATA,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    freshness: FreshnessStatus = FreshnessStatus.FRESH,
    fingerprint: str = "market-fingerprint",
) -> IntelligenceEvidenceReference:
    return IntelligenceEvidenceReference(
        domain=domain, availability=availability, artifact_ids=(f"{domain.value}:artifact",),
        artifact_fingerprints=(fingerprint,), evidence_as_of=T, observed_at=T,
        freshness_status=freshness, freshness_policy_reference="existing-policy-v1",
        source_provenance_fingerprint="provenance-fingerprint",
        historical_integrity_reference="integrity-reference", warnings=(),
    )


def _state(*, references=None, as_of=T, completeness=IntelligenceStateCompleteness.PARTIAL):
    return create_unified_intelligence_state(
        canonical_instrument_id="NSE:STATE", as_of=as_of, evaluation_session=as_of,
        state_schema_version="unified-intelligence-state-v1", intelligence_contract_version="shared-brain-v1",
        evidence_references=references or (_reference(), _reference(IntelligenceEvidenceDomain.FUNDAMENTALS, IntelligenceEvidenceAvailability.PARTIAL, fingerprint="fundamentals-fingerprint")),
        completeness=completeness, blocking_domains=(IntelligenceEvidenceDomain.EARNINGS,),
        degraded_domains=(IntelligenceEvidenceDomain.FUNDAMENTALS,),
        dependency_lineage=(IntelligenceDependencyReference(IntelligenceInvalidationDomain.PRICE, "price-artifact", "price-fingerprint"),),
        origin_lineage=(("handoff_id", "brain-research-handoff-1"), ("policy_fingerprint", "policy-fingerprint")),
    )


def test_state_is_immutable_requires_canonical_instrument_and_timezone_aware_as_of() -> None:
    state = _state()
    with pytest.raises(FrozenInstanceError):
        state.canonical_instrument_id = "NSE:OTHER"  # type: ignore[misc]
    with pytest.raises(UnifiedIntelligenceStateError, match="REQUIRED_FIELD"):
        create_unified_intelligence_state(canonical_instrument_id="", as_of=T, evaluation_session=None, state_schema_version="v1", intelligence_contract_version="v1", evidence_references=(), completeness=IntelligenceStateCompleteness.UNAVAILABLE)
    with pytest.raises(UnifiedIntelligenceStateError, match="TIMEZONE_REQUIRED"):
        _state(as_of=datetime(2026, 8, 28, 12))


def test_state_identity_and_fingerprint_are_deterministic_and_cover_semantic_lineage() -> None:
    first, same = _state(), _state()
    changed_artifact = _state(references=(_reference(fingerprint="changed"),))
    changed_freshness = _state(references=(_reference(freshness=FreshnessStatus.STALE),))
    changed_as_of = _state(as_of=T + timedelta(days=1))
    assert first == same and (first.state_id, first.fingerprint) == (same.state_id, same.fingerprint)
    assert changed_artifact.fingerprint != first.fingerprint
    assert changed_freshness.fingerprint != first.fingerprint
    assert changed_as_of.fingerprint != first.fingerprint


@pytest.mark.parametrize("availability", tuple(IntelligenceEvidenceAvailability))
def test_explicit_evidence_availability_and_freshness_provenance_lineage_are_retained(availability) -> None:
    reference = _reference(availability=availability, freshness=FreshnessStatus.STALE)
    state = _state(references=(reference,), completeness=IntelligenceStateCompleteness.PARTIAL)
    stored = state.evidence_references[0]
    assert stored.availability is availability
    assert stored.freshness_status is FreshnessStatus.STALE
    assert stored.artifact_ids == ("MARKET_DATA:artifact",)
    assert stored.artifact_fingerprints == ("market-fingerprint",)
    assert stored.source_provenance_fingerprint == "provenance-fingerprint"
    assert stored.historical_integrity_reference == "integrity-reference"


def test_state_can_be_partial_without_action_or_raw_evidence_payloads() -> None:
    state = _state()
    assert state.completeness is IntelligenceStateCompleteness.PARTIAL
    assert state.blocking_domains == (IntelligenceEvidenceDomain.EARNINGS,)
    assert state.degraded_domains == (IntelligenceEvidenceDomain.FUNDAMENTALS,)
    assert not any(hasattr(state, name) for name in ("buy", "sell", "hold", "trim", "rotate", "score", "quantity", "average_cost", "raw_payload", "candles", "filings", "articles"))


def test_dependency_and_origin_lineage_are_immutable_and_support_future_delta_comparison() -> None:
    state = _state()
    assert state.dependency_lineage[0].invalidation_domain is IntelligenceInvalidationDomain.PRICE
    successor = create_unified_intelligence_state(
        canonical_instrument_id=state.canonical_instrument_id, as_of=T + timedelta(days=1), evaluation_session=T + timedelta(days=1),
        state_schema_version=state.state_schema_version, intelligence_contract_version=state.intelligence_contract_version,
        evidence_references=state.evidence_references, completeness=state.completeness,
        previous_state_fingerprint=state.fingerprint,
    )
    assert successor.previous_state_fingerprint == state.fingerprint and successor.fingerprint != state.fingerprint


@pytest.mark.parametrize("context", tuple(BrainOutputContext))
def test_same_state_supports_each_output_context_without_creating_a_second_state(context) -> None:
    state = _state()
    request = create_brain_output_request(state, output_context=context)
    assert request.intelligence_state_id == state.state_id
    assert request.intelligence_state_fingerprint == state.fingerprint
    assert request.output_context is context
    assert state.fingerprint == _state().fingerprint


def test_output_request_is_deterministic_and_portfolio_context_changes_request_not_state() -> None:
    state = _state()
    plain = create_brain_output_request(state, output_context=BrainOutputContext.PORTFOLIO_REVIEW)
    same = create_brain_output_request(state, output_context=BrainOutputContext.PORTFOLIO_REVIEW)
    context = PortfolioContextRef("portfolio-context-1", "snapshot-1", "portfolio-context-fingerprint")
    contextual = create_brain_output_request(state, output_context=BrainOutputContext.PORTFOLIO_REVIEW, portfolio_context=context)
    deep = create_brain_output_request(state, output_context=BrainOutputContext.DEEP_ANALYSIS)
    assert plain == same
    assert contextual.fingerprint != plain.fingerprint and deep.fingerprint != plain.fingerprint
    assert state.fingerprint == _state().fingerprint
    assert not any(hasattr(context, name) for name in ("quantity", "average_cost", "unrealized_pnl", "portfolio_heat"))


def test_state_is_separate_from_candidate_and_research_intake_contracts() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "unified_state.py").read_text(encoding="utf-8")
    assert "strategies.pre_breakout" not in source and "PreBreakoutCandidate" not in source and "BrainResearchIntake" not in source
    assert "sqlite" not in source.casefold() and "repository" not in source.casefold()


def test_contract_has_no_builder_provider_diagnostics_scoring_gate_or_trading_execution() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "unified_state.py").read_text(encoding="utf-8")
    assert not any(term in source for term in ("build_current_state", "requests.", "urlopen", "DecisionScore", "SixGate", "DiagnosticResult", "Signal", "PaperTrade", "order("))
