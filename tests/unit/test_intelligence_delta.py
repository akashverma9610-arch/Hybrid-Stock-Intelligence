from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.intelligence_delta import (
    CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY,
    IntelligenceDeltaChangeKind,
    IntelligenceDeltaError,
    IntelligenceDeltaStatus,
    compare_intelligence_states,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceDependencyReference,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
I = "NSE:INE000A01001"


def _reference(domain, *, availability=IntelligenceEvidenceAvailability.AVAILABLE, artifact="artifact:1",
               fingerprint="fingerprint:1", freshness=FreshnessStatus.UNKNOWN, provenance="source:1",
               integrity="integrity:1", warnings=(), at=T):
    return IntelligenceEvidenceReference(
        domain=domain, availability=availability, artifact_ids=(artifact,), artifact_fingerprints=(fingerprint,),
        evidence_as_of=at, observed_at=at, freshness_status=freshness,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint=provenance,
        historical_integrity_reference=integrity, warnings=warnings,
    )


def _state(*, at=T, instrument=I, references=(), completeness=IntelligenceStateCompleteness.COMPLETE,
           blocking=(), degraded=(), dependencies=(), origin=(), schema="state-v1", contract="intelligence-v1"):
    return create_unified_intelligence_state(
        canonical_instrument_id=instrument, as_of=at, evaluation_session=None,
        state_schema_version=schema, intelligence_contract_version=contract,
        evidence_references=tuple(references), completeness=completeness,
        blocking_domains=tuple(blocking), degraded_domains=tuple(degraded),
        dependency_lineage=tuple(dependencies), origin_lineage=tuple(origin),
    )


def _pair(previous_references=(), current_references=(), **kwargs):
    return (
        _state(references=previous_references, **kwargs),
        _state(at=T + timedelta(days=1), references=current_references, **kwargs),
    )


def test_same_instrument_and_strict_chronology_are_required():
    previous = _state()
    with pytest.raises(IntelligenceDeltaError, match="INSTRUMENT_MISMATCH"):
        compare_intelligence_states(previous, _state(at=T + timedelta(days=1), instrument="NSE:OTHER"))
    with pytest.raises(IntelligenceDeltaError, match="CHRONOLOGY_REQUIRED"):
        compare_intelligence_states(previous, _state(at=T))


def test_same_semantic_references_at_later_as_of_are_explicit_no_change():
    reference = _reference(IntelligenceEvidenceDomain.MARKET_DATA)
    previous, current = _pair((reference,), (replace(reference, observed_at=T + timedelta(days=1)),))
    delta = compare_intelligence_states(previous, current)
    assert delta.status is IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE
    assert not delta.domain_deltas and not delta.change_kinds
    assert delta.previous_state_fingerprint != delta.current_state_fingerprint


@pytest.mark.parametrize("domain", (
    IntelligenceEvidenceDomain.MARKET_DATA, IntelligenceEvidenceDomain.EARNINGS,
    IntelligenceEvidenceDomain.NEWS_CATALYSTS, IntelligenceEvidenceDomain.SECTOR,
    IntelligenceEvidenceDomain.TECHNICAL, IntelligenceEvidenceDomain.REFERENCE_DATA,
    IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS, IntelligenceEvidenceDomain.DECISION_SCORE,
    IntelligenceEvidenceDomain.SIX_GATES,
))
def test_domain_evidence_addition_is_bounded_and_deterministic(domain):
    previous, current = _pair((), (_reference(domain),))
    delta = compare_intelligence_states(previous, current)
    domain_delta = delta.domain_deltas[0]
    assert domain_delta.domain is domain
    assert domain_delta.change_kinds == (IntelligenceDeltaChangeKind.EVIDENCE_ADDED,)
    assert domain_delta.previous_reference is None and domain_delta.current_reference is not None
    assert delta == compare_intelligence_states(previous, current)


def test_replaced_availability_freshness_reliability_and_integrity_changes_are_exact():
    previous = _reference(IntelligenceEvidenceDomain.RELIABILITY, fingerprint="old", freshness=FreshnessStatus.FRESH, integrity="valid")
    current = _reference(
        IntelligenceEvidenceDomain.RELIABILITY, availability=IntelligenceEvidenceAvailability.CONFLICTED,
        fingerprint="new", freshness=FreshnessStatus.STALE, integrity="partial",
    )
    before, after = _pair((previous,), (current,))
    kinds = set(compare_intelligence_states(before, after).domain_deltas[0].change_kinds)
    assert {IntelligenceDeltaChangeKind.EVIDENCE_REPLACED, IntelligenceDeltaChangeKind.STATUS_CHANGED,
            IntelligenceDeltaChangeKind.FRESHNESS_CHANGED, IntelligenceDeltaChangeKind.RELIABILITY_CHANGED,
            IntelligenceDeltaChangeKind.INTEGRITY_CHANGED}.issubset(kinds)


def test_removed_evidence_and_blocking_degraded_completeness_transitions_are_preserved():
    reference = _reference(IntelligenceEvidenceDomain.FUNDAMENTALS)
    previous = _state(
        references=(reference,), completeness=IntelligenceStateCompleteness.COMPLETE,
        blocking=(), degraded=(),
    )
    current = _state(
        at=T + timedelta(days=1), references=(), completeness=IntelligenceStateCompleteness.PARTIAL,
        blocking=(IntelligenceEvidenceDomain.FUNDAMENTALS,), degraded=(IntelligenceEvidenceDomain.RELIABILITY,),
    )
    delta = compare_intelligence_states(previous, current)
    assert delta.domain_deltas[0].change_kinds == (IntelligenceDeltaChangeKind.EVIDENCE_REMOVED,)
    assert delta.added_blocking_domains == (IntelligenceEvidenceDomain.FUNDAMENTALS,)
    assert delta.added_degraded_domains == (IntelligenceEvidenceDomain.RELIABILITY,)
    assert IntelligenceDeltaChangeKind.COMPLETENESS_CHANGED in delta.change_kinds


def test_dependency_and_version_lineage_changes_are_bounded_and_action_free():
    dependency = IntelligenceDependencyReference(IntelligenceInvalidationDomain.PRICE, "bar:1", "fp:1")
    previous = _state(dependencies=())
    current = _state(at=T + timedelta(days=1), dependencies=(dependency,), schema="state-v2")
    delta = compare_intelligence_states(previous, current)
    assert delta.added_dependencies == (dependency,)
    assert {IntelligenceDeltaChangeKind.DEPENDENCY_CHANGED, IntelligenceDeltaChangeKind.VERSION_CHANGED}.issubset(delta.change_kinds)
    assert set(delta.affected_output_contexts) == set(BrainOutputContext)
    assert "INTELLIGENCE_DELTA_VERSION_LINEAGE_CHANGED" in delta.warnings


def test_domain_impact_policy_routes_news_sector_score_and_gates_without_action_meaning():
    assert CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY.contexts_for(IntelligenceEvidenceDomain.NEWS_CATALYSTS) == (
        BrainOutputContext.ALERT_REVIEW, BrainOutputContext.DEEP_ANALYSIS,
        BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.SELL_TRIM_REVIEW,
    )
    sector = CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY.contexts_for(IntelligenceEvidenceDomain.SECTOR)
    score = CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY.contexts_for(IntelligenceEvidenceDomain.DECISION_SCORE)
    gates = CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY.contexts_for(IntelligenceEvidenceDomain.SIX_GATES)
    assert BrainOutputContext.ROTATION_REVIEW in sector
    assert score == gates == (
        BrainOutputContext.ENTRY_SETUP_REVIEW, BrainOutputContext.OPPORTUNITY_DISCOVERY,
        BrainOutputContext.ROTATION_REVIEW,
    )


def test_origin_is_nonsemantic_and_portfolio_is_not_part_of_state_delta():
    reference = _reference(IntelligenceEvidenceDomain.TECHNICAL)
    previous = _state(references=(reference,), origin=(("origin", "scanner"),))
    current = _state(at=T + timedelta(days=1), references=(reference,), origin=(("origin", "portfolio"),))
    assert compare_intelligence_states(previous, current).status is IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE


def test_delta_is_immutable_and_has_no_recommendation_or_trade_surface():
    previous, current = _pair((), (_reference(IntelligenceEvidenceDomain.NEWS_CATALYSTS),))
    delta = compare_intelligence_states(previous, current)
    with pytest.raises(FrozenInstanceError):
        delta.status = IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE
    assert not any(hasattr(delta, field) for field in (
        "recommendation", "action", "buy", "sell", "hold", "trim", "rotate", "alert", "signal", "order", "paper_trade",
    ))


def test_contract_has_no_persistence_network_engine_or_worker_surface():
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "intelligence_delta.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "requests.", "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "build_scorecard",
        "evaluate_six_gates", "Canonical61DiagnosticRunner", "project_brain_output(", "scheduler", "worker", "listener",
        "Signal", "PaperTrade", "order(", "recommend(",
    ))
