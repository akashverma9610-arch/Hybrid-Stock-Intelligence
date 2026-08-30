from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
    IntelligenceStateCompleteness,
    UnifiedIntelligenceStateError,
    create_unified_intelligence_state,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder


T = datetime(2026, 8, 28, 12, tzinfo=UTC)


class _StoredSource:
    def __init__(self, values=()): self.values = tuple(values)
    def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
        return tuple(item for item in self.values if item.canonical_instrument_id == canonical_instrument_id)


def _artifact(
    domain: IntelligenceEvidenceDomain,
    identifier: str | None = None,
    *,
    availability=IntelligenceEvidenceAvailability.AVAILABLE,
    freshness=FreshnessStatus.FRESH,
    available_at=T,
    evidence_as_of=T,
    fingerprint: str | None = None,
) -> StoredIntelligenceArtifact:
    invalidation = {
        IntelligenceEvidenceDomain.MARKET_DATA: IntelligenceInvalidationDomain.PRICE,
        IntelligenceEvidenceDomain.FUNDAMENTALS: IntelligenceInvalidationDomain.FUNDAMENTALS,
        IntelligenceEvidenceDomain.EARNINGS: IntelligenceInvalidationDomain.EARNINGS,
        IntelligenceEvidenceDomain.NEWS_CATALYSTS: IntelligenceInvalidationDomain.NEWS,
        IntelligenceEvidenceDomain.SECTOR: IntelligenceInvalidationDomain.SECTOR,
    }.get(domain, IntelligenceInvalidationDomain.REFERENCE_DATA)
    token = identifier or domain.value.lower()
    return StoredIntelligenceArtifact(
        canonical_instrument_id="NSE:BUILDER", domain=domain, artifact_id=f"{token}:id",
        artifact_fingerprint=fingerprint or f"{token}:fingerprint", availability=availability,
        evidence_as_of=evidence_as_of, observed_at=evidence_as_of, available_at=available_at,
        freshness_status=freshness, freshness_policy_reference="existing-freshness-policy",
        source_provenance_fingerprint=f"{token}:provenance", historical_integrity_reference=f"{token}:integrity",
        invalidation_domain=invalidation,
    )


def _builder(*values): return UnifiedIntelligenceStateBuilder(_StoredSource(values))
def _core(*extra): return (_artifact(IntelligenceEvidenceDomain.REFERENCE_DATA), _artifact(IntelligenceEvidenceDomain.MARKET_DATA), *extra)


def test_builder_requires_canonical_instrument_and_explicit_timezone_aware_as_of() -> None:
    builder = _builder(*_core())
    with pytest.raises(UnifiedIntelligenceStateError, match="CANONICAL_INSTRUMENT_REQUIRED"):
        builder.build("", as_of=T)
    with pytest.raises(UnifiedIntelligenceStateError, match="AS_OF_TIMEZONE_REQUIRED"):
        builder.build("NSE:BUILDER", as_of=datetime(2026, 8, 28, 12))


def test_builder_returns_deterministic_partial_state_with_explicit_absent_research_decision_and_gates() -> None:
    builder = _builder(*_core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS)))
    first, rebuilt = builder.build("NSE:BUILDER", as_of=T), builder.build("NSE:BUILDER", as_of=T)
    assert first == rebuilt and first.completeness is IntelligenceStateCompleteness.PARTIAL
    by_domain = {value.domain: value for value in first.evidence_references}
    assert by_domain[IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS].availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert by_domain[IntelligenceEvidenceDomain.DECISION_SCORE].availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert by_domain[IntelligenceEvidenceDomain.SIX_GATES].availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS in first.degraded_domains
    assert first.blocking_domains == ()


def test_complete_synthetic_state_is_possible_only_when_every_schema_domain_has_available_evidence() -> None:
    state = _builder(*(_artifact(domain) for domain in IntelligenceEvidenceDomain)).build("NSE:BUILDER", as_of=T)
    assert state.completeness is IntelligenceStateCompleteness.COMPLETE
    assert state.blocking_domains == () and state.degraded_domains == ()


def test_changed_market_fundamental_and_freshness_lineage_change_state_fingerprint() -> None:
    base = _builder(*_core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS))).build("NSE:BUILDER", as_of=T)
    market_changed = _builder(*_core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS), _artifact(IntelligenceEvidenceDomain.MARKET_DATA, "market-revision", fingerprint="market-revision-fingerprint"))).build("NSE:BUILDER", as_of=T)
    fundamental_changed = _builder(*_core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS, fingerprint="new-fundamentals"))).build("NSE:BUILDER", as_of=T)
    stale = _builder(*_core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS, freshness=FreshnessStatus.STALE))).build("NSE:BUILDER", as_of=T)
    assert {market_changed.fingerprint, fundamental_changed.fingerprint, stale.fingerprint}.isdisjoint({base.fingerprint})
    stale_reference = next(item for item in stale.evidence_references if item.domain is IntelligenceEvidenceDomain.FUNDAMENTALS)
    assert stale_reference.availability is IntelligenceEvidenceAvailability.STALE


def test_future_or_first_observed_after_as_of_is_excluded_without_backdating() -> None:
    future = _artifact(IntelligenceEvidenceDomain.FUNDAMENTALS, available_at=T + timedelta(days=1), evidence_as_of=T - timedelta(days=30))
    builder = _builder(*_core(), future)
    early = builder.build("NSE:BUILDER", as_of=T)
    later = builder.build("NSE:BUILDER", as_of=T + timedelta(days=1))
    early_ref = next(item for item in early.evidence_references if item.domain is IntelligenceEvidenceDomain.FUNDAMENTALS)
    later_ref = next(item for item in later.evidence_references if item.domain is IntelligenceEvidenceDomain.FUNDAMENTALS)
    assert early_ref.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert later_ref.availability is IntelligenceEvidenceAvailability.AVAILABLE


def test_all_evidence_domains_are_materialized_once_even_when_not_yet_computed() -> None:
    state = _builder(*_core()).build("NSE:BUILDER", as_of=T)
    assert tuple(item.domain for item in state.evidence_references) == tuple(sorted(IntelligenceEvidenceDomain, key=lambda item: item.value))
    assert all(item.warnings == ("NOT_YET_COMPUTED",) for item in state.evidence_references if item.availability is IntelligenceEvidenceAvailability.UNAVAILABLE)


def test_stored_reference_preserves_pit_freshness_provenance_and_integrity_metadata() -> None:
    observed = T - timedelta(minutes=5)
    state = _builder(*_core(_artifact(IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY, "integrity", evidence_as_of=observed, available_at=observed))).build("NSE:BUILDER", as_of=T)
    reference = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY)
    assert reference.evidence_as_of == observed and reference.observed_at == observed
    assert reference.freshness_status is FreshnessStatus.FRESH
    assert reference.source_provenance_fingerprint and reference.historical_integrity_reference


def test_source_instrument_mismatch_fails_closed() -> None:
    wrong = StoredIntelligenceArtifact(
        canonical_instrument_id="NSE:OTHER", domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
        artifact_id="other", artifact_fingerprint="other-fingerprint",
        availability=IntelligenceEvidenceAvailability.AVAILABLE, evidence_as_of=T,
        observed_at=T, available_at=T, freshness_status=FreshnessStatus.FRESH,
        freshness_policy_reference=None, source_provenance_fingerprint=None,
        historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
    )
    class _BadSource:
        def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
            return (wrong,)
    with pytest.raises(UnifiedIntelligenceStateError, match="INSTRUMENT_MISMATCH"):
        UnifiedIntelligenceStateBuilder(_BadSource()).build("NSE:BUILDER", as_of=T)


def test_previous_state_fingerprint_is_optional_lineage_not_automatic_delta_or_cache() -> None:
    baseline = _builder(*_core()).build("NSE:BUILDER", as_of=T)
    successor = _builder(*_core()).build("NSE:BUILDER", as_of=T, previous_state_fingerprint=baseline.fingerprint)
    assert successor.previous_state_fingerprint == baseline.fingerprint
    assert successor.fingerprint != baseline.fingerprint
    assert not hasattr(successor, "delta") and not hasattr(successor, "cache_key")


@pytest.mark.parametrize("domain", (
    IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,
    IntelligenceEvidenceDomain.DECISION_SCORE,
    IntelligenceEvidenceDomain.SIX_GATES,
))
def test_optional_output_domain_can_be_referenced_without_turning_the_builder_into_an_executor(domain: IntelligenceEvidenceDomain) -> None:
    state = _builder(*_core(_artifact(domain, domain.value.lower()))).build("NSE:BUILDER", as_of=T)
    reference = next(item for item in state.evidence_references if item.domain is domain)
    assert reference.availability is IntelligenceEvidenceAvailability.AVAILABLE


def test_canonical_identity_or_market_conflict_fails_closed_while_optional_conflict_is_visible() -> None:
    with pytest.raises(UnifiedIntelligenceStateError, match="CANONICAL_IDENTITY_CONFLICT"):
        _builder(_artifact(IntelligenceEvidenceDomain.REFERENCE_DATA, availability=IntelligenceEvidenceAvailability.CONFLICTED), _artifact(IntelligenceEvidenceDomain.MARKET_DATA)).build("NSE:BUILDER", as_of=T)
    with pytest.raises(UnifiedIntelligenceStateError, match="MARKET_CONFLICT"):
        _builder(*_core(_artifact(IntelligenceEvidenceDomain.MARKET_DATA, "market-conflict", availability=IntelligenceEvidenceAvailability.CONFLICTED))).build("NSE:BUILDER", as_of=T)
    state = _builder(*_core(_artifact(IntelligenceEvidenceDomain.NEWS_CATALYSTS, availability=IntelligenceEvidenceAvailability.CONFLICTED))).build("NSE:BUILDER", as_of=T)
    assert IntelligenceEvidenceDomain.NEWS_CATALYSTS in state.degraded_domains


def test_builder_state_needs_no_candidate_origin_or_portfolio_context() -> None:
    state = _builder(*_core()).build("NSE:BUILDER", as_of=T)
    assert all(item.domain is not IntelligenceEvidenceDomain.SETUP_OPPORTUNITY or item.availability is IntelligenceEvidenceAvailability.UNAVAILABLE for item in state.evidence_references)
    assert not any(hasattr(state, field) for field in ("candidate", "portfolio", "quantity", "average_cost", "origin"))


def test_existing_opportunity_reference_is_bounded_and_does_not_become_state() -> None:
    state = _builder(*_core(_artifact(IntelligenceEvidenceDomain.SETUP_OPPORTUNITY, "prebreakout-candidate"))).build("NSE:BUILDER", as_of=T)
    reference = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.SETUP_OPPORTUNITY)
    assert reference.artifact_ids == ("prebreakout-candidate:id",)
    assert not hasattr(state, "candidate_id")


def test_dependency_invalidation_order_and_reconstruction_are_deterministic_across_source_order() -> None:
    values = _core(_artifact(IntelligenceEvidenceDomain.FUNDAMENTALS), _artifact(IntelligenceEvidenceDomain.NEWS_CATALYSTS))
    first = _builder(*values).build("NSE:BUILDER", as_of=T)
    second_builder = _builder(*reversed(values))
    second = second_builder.build("NSE:BUILDER", as_of=T)
    assert first == second
    assert second_builder.reconstruct("NSE:BUILDER", as_of=T, expected_state=first) == first
    actual = tuple((item.invalidation_domain, item.artifact_id) for item in first.dependency_lineage)
    expected = tuple(sorted(actual, key=lambda item: (item[0].value, item[1])))
    assert actual == expected


def test_reconstruction_mismatch_fails_closed_and_origin_lineage_is_nonsemantic() -> None:
    builder = _builder(*_core())
    state = builder.build("NSE:BUILDER", as_of=T)
    with_other_origin = create_unified_intelligence_state(
        canonical_instrument_id=state.canonical_instrument_id, as_of=state.as_of,
        evaluation_session=state.evaluation_session, state_schema_version=state.state_schema_version,
        intelligence_contract_version=state.intelligence_contract_version,
        evidence_references=state.evidence_references, completeness=state.completeness,
        blocking_domains=state.blocking_domains, degraded_domains=state.degraded_domains,
        dependency_lineage=state.dependency_lineage,
        origin_lineage=(("output_request", "different-context"),),
        previous_state_fingerprint=state.previous_state_fingerprint,
    )
    assert (with_other_origin.state_id, with_other_origin.fingerprint) == (state.state_id, state.fingerprint)
    assert builder.reconstruct("NSE:BUILDER", as_of=T, expected_state=state) == state
    changed_builder = _builder(*_core(_artifact(IntelligenceEvidenceDomain.MARKET_DATA, "later-revision")))
    with pytest.raises(UnifiedIntelligenceStateError, match="RECONSTRUCTION_MISMATCH"):
        changed_builder.reconstruct("NSE:BUILDER", as_of=T, expected_state=state)


def test_builder_contract_has_no_persistence_cache_provider_research_scoring_gate_or_action_execution() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "unified_state_builder.py").read_text(encoding="utf-8")
    assert not any(term in source for term in ("CREATE TABLE", "INSERT INTO", "sqlite3", "requests.", "urlopen", "DecisionScore", "SixGate", "Signal", "PaperTrade", "order("))
