from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.decision_score_evidence import (
    DecisionScoreEvidenceStoredSource,
    StrategyGovernanceDecisionScorecardSource,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
    PortfolioContextRef,
    create_brain_output_request,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.scoring.engine import DecisionScorecard, ScoredComponent
from app.domain.models import FreshnessStatus, StrategyVersionReference


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
I = "NSE:INE000A01001"
REFERENCE = StrategyVersionReference("shared-brain", "score-v1")
SUCCESSOR = StrategyVersionReference("shared-brain", "score-v2")


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id=f"instrument:{canonical_instrument_id}", artifact_fingerprint="identity-fingerprint",
            availability=IntelligenceEvidenceAvailability.AVAILABLE, evidence_as_of=as_of,
            observed_at=as_of, available_at=as_of, freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None, source_provenance_fingerprint=None,
            historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


class _Scores:
    def __init__(self, values): self.values = tuple(values)
    def list_stored_decision_scorecards(self, canonical_instrument_id, *, as_of): return self.values


def _card(*, at=T - timedelta(days=1), evaluated=None, instrument=I, reference=REFERENCE, ident=None, status="COMPLETE"):
    ident = ident or f"score:{reference.version}:{at.date().isoformat()}:{instrument}"
    return DecisionScorecard(
        ident, instrument, reference, "diagnostic-registry-v1", f"config:{reference.version}", at,
        evaluated or at, (
            ScoredComponent("market_regime", "COMPLETE", Decimal("9"), Decimal("1"), Decimal("9"),
                            (1,), (), ("diagnostic:1",), ("evidence:1",), 0.9, ()),
        ), Decimal("9") if status == "COMPLETE" else None, status, 0.9, (),
    )


def _builder(values=None):
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(
        _CoreSource(), DecisionScoreEvidenceStoredSource(_Scores(values) if values is not None else None),
    ))


def _reference(state):
    return next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.DECISION_SCORE)


def test_missing_score_boundary_and_not_yet_computed_are_explicit():
    missing = _reference(_builder().build(I, as_of=T))
    absent = _reference(_builder(()).build(I, as_of=T))
    assert missing.warnings == ("DECISION_SCORE_DURABLE_READ_BOUNDARY_MISSING",)
    assert absent.warnings == ("DECISION_SCORE_NOT_YET_COMPUTED",)


def test_durable_score_is_bounded_available_and_has_diagnostic_lineage():
    state = _builder((_card(),)).build(I, as_of=T)
    reference = _reference(state)
    assert reference.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert reference.artifact_ids == (_card().id,)
    assert "diagnostic:1" not in repr(state)
    dependency = next(item for item in state.dependency_lineage if item.artifact_id == _card().id)
    assert dependency.invalidation_domain is IntelligenceInvalidationDomain.POLICY


def test_future_and_first_observed_later_scores_do_not_backdate():
    future = _card(at=T + timedelta(days=1))
    observed_later = _card(at=T - timedelta(days=1), evaluated=T + timedelta(days=1), ident="score:later")
    builder = _builder((future, observed_later))
    before = _reference(builder.build(I, as_of=T))
    after = _reference(builder.build(I, as_of=T + timedelta(days=1)))
    assert before.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert after.availability is IntelligenceEvidenceAvailability.AVAILABLE


def test_history_version_latest_selection_and_insertion_order_are_deterministic():
    old = _card(at=T - timedelta(days=2), reference=REFERENCE)
    new = _card(at=T - timedelta(days=1), reference=SUCCESSOR)
    old_reference = _reference(_builder((new, old)).build(I, as_of=old.as_of_timestamp))
    new_reference = _reference(_builder((new, old)).build(I, as_of=T))
    reverse_reference = _reference(_builder((old, new)).build(I, as_of=T))
    assert old_reference.artifact_ids == (old.id,)
    assert new_reference == reverse_reference
    assert new_reference.artifact_ids == (new.id,)


def test_exact_identity_partial_status_and_new_eligible_score_change_state_only_when_eligible():
    valid = _card()
    wrong = _card(instrument="NSE:OTHER", ident="score:other")
    partial = _card(at=T, ident="score:partial", status="SCORE_INCOMPLETE")
    before = _builder((valid, wrong)).build(I, as_of=T)
    after = _builder((valid, partial)).build(I, as_of=T)
    future = _builder((valid, _card(at=T + timedelta(days=1)))).build(I, as_of=T)
    assert _reference(before).artifact_ids == (valid.id,)
    assert before.fingerprint != after.fingerprint
    assert before.fingerprint == future.fingerprint
    assert _reference(after).availability is IntelligenceEvidenceAvailability.PARTIAL


def test_score_configuration_and_diagnostic_lineage_are_bounded_in_artifact_identity():
    base = _card()
    changed_config = replace(base, configuration_version="config:score-v2")
    changed_diagnostic = replace(
        base,
        components=(replace(base.components[0], diagnostic_ids=("diagnostic:successor",)),),
    )
    base_reference = _reference(_builder((base,)).build(I, as_of=T))
    config_reference = _reference(_builder((changed_config,)).build(I, as_of=T))
    diagnostic_reference = _reference(_builder((changed_diagnostic,)).build(I, as_of=T))
    assert base_reference.freshness_policy_reference == "config:score-v1"
    assert base_reference.artifact_fingerprints != config_reference.artifact_fingerprints
    assert base_reference.source_provenance_fingerprint != diagnostic_reference.source_provenance_fingerprint


def test_score_evidence_is_shared_across_output_contexts_and_portfolio_independent():
    state = _builder((_card(),)).build(I, as_of=T)
    opportunity = create_brain_output_request(state, output_context=BrainOutputContext.OPPORTUNITY_DISCOVERY)
    portfolio = create_brain_output_request(
        state,
        output_context=BrainOutputContext.PORTFOLIO_REVIEW,
        portfolio_context=PortfolioContextRef("portfolio:1", "snapshot:1", "portfolio-fingerprint"),
    )
    assert opportunity.intelligence_state_fingerprint == portfolio.intelligence_state_fingerprint == state.fingerprint
    assert _reference(state).artifact_ids == (_card().id,)


def test_existing_repository_read_path_is_exact_scorecard_id_only():
    card = _card()
    class _Repository:
        def __init__(self): self.calls = []
        def get_decision_scorecard(self, scorecard_id): self.calls.append(scorecard_id); return card
    repository = _Repository()
    source = StrategyGovernanceDecisionScorecardSource(repository, scorecard_id=card.id)
    assert source.list_stored_decision_scorecards(I, as_of=T) == (card,)
    assert repository.calls == [card.id]


def test_adapter_is_stored_only_and_excludes_calculation_gates_actions_and_persistence():
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "decision_score_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "build_scorecard", "Canonical61DiagnosticRunner", "SixGate", "requests.", "urlopen", "httpx",
        "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "BUY", "HOLD", "SELL", "order(",
    ))
