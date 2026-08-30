from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.domain.models import FreshnessStatus, StrategyVersionReference
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.decision_score_evidence import DecisionScoreEvidenceStoredSource
from app.intelligence.output_evaluation_context import (
    OUTPUT_CONTEXT_REQUIREMENTS,
    OutputEvaluationBlocker,
    OutputEvaluationMatchStatus,
    create_brain_output_evaluation_context,
    output_context_requirement,
)
from app.intelligence.six_gates_evidence import SixGatesEvidenceStoredSource
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
from app.brain_output_requirement_policy import (
    CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY,
    create_brain_output_requirement_policy,
)


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
I = "NSE:INE000A01001"
REFERENCE = StrategyVersionReference("shared-brain", "v1")


class _Core:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id, domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id=f"instrument:{canonical_instrument_id}", artifact_fingerprint="identity",
            availability=IntelligenceEvidenceAvailability.AVAILABLE, evidence_as_of=as_of, observed_at=as_of,
            available_at=as_of, freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=None,
            source_provenance_fingerprint=None, historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


@dataclass(frozen=True)
class _Decision:
    gate_id: str = "GATE_5_HEAT"
    outcome: str = "PASS"
    evidence_ids: tuple[str, ...] = ("evidence:heat",)


@dataclass(frozen=True)
class _Gate:
    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    scorecard_id: str
    input_snapshot_id: str | None
    action_context: str
    as_of_timestamp: datetime
    evaluated_at: datetime
    decisions: tuple[_Decision, ...]
    eligibility: str
    failed_gate_ids: tuple[str, ...]
    insufficient_gate_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    configuration_parameters: tuple[tuple[str, str], ...]


class _Scores:
    def __init__(self, values): self.values = tuple(values)
    def list_stored_decision_scorecards(self, canonical_instrument_id, *, as_of): return self.values


class _Gates:
    def __init__(self, values): self.values = tuple(values)
    def list_stored_six_gates_evaluations(self, canonical_instrument_id, *, as_of): return self.values


def _score(*, instrument=I, at=T - timedelta(days=1), evaluated=None, ident="score:1", config="score-config-v1"):
    return DecisionScorecard(
        ident, instrument, REFERENCE, "diagnostic-registry-v1", config, at, evaluated or at,
        (ScoredComponent("market_regime", "COMPLETE", Decimal("9"), Decimal("1"), Decimal("9"),
                         (1,), (), ("diagnostic:1",), ("evidence:1",), 0.9, ()),),
        Decimal("9"), "COMPLETE", 0.9, (),
    )


def _gate(*, score=None, instrument=I, at=T - timedelta(days=1), evaluated=None, ident="gate:1", snapshot="snapshot:1", action="FRESH_ENTRY", config="gate-config-v1"):
    score = score or _score()
    return _Gate(ident, instrument, REFERENCE, "diagnostic-registry-v1", score.configuration_version, config,
                 score.id, snapshot, action, at, evaluated or at, (_Decision(),), "EXECUTABLE", (), (), (),
                 ("evidence:heat",), ("diagnostic:1",), (("max_total_heat", "0.10"),))


def _state(*, score=None, gate=None, as_of=T):
    sources = [_Core()]
    if score is not None: sources.append(DecisionScoreEvidenceStoredSource(_Scores((score,))))
    if gate is not None: sources.append(SixGatesEvidenceStoredSource(_Gates((gate,))))
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(*sources)).build(I, as_of=as_of)


def _request(state, context=BrainOutputContext.ENTRY_SETUP_REVIEW, portfolio="snapshot:1"):
    return create_brain_output_request(
        state, output_context=context,
        portfolio_context=PortfolioContextRef("portfolio:1", portfolio, "portfolio-fingerprint") if portfolio else None,
    )


def test_exact_entry_lineage_context_and_portfolio_match_is_ready_without_action():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    value = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    assert value.ready_for_output_decision is True
    assert value.gate_context_match_status is OutputEvaluationMatchStatus.MATCHED
    assert value.portfolio_context_match_status is OutputEvaluationMatchStatus.MATCHED
    assert not hasattr(value, "recommendation") and not hasattr(value, "action")


def test_instrument_and_state_fingerprint_mismatches_fail_closed():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    other_state = _state(score=score, gate=gate, as_of=T + timedelta(hours=1))
    state_mismatch = create_brain_output_evaluation_context(other_state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    wrong_score = _score(instrument="NSE:OTHER", ident="score:other")
    instrument_mismatch = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=wrong_score, gate_evaluation=gate)
    assert OutputEvaluationBlocker.STATE_MISMATCH in state_mismatch.blockers
    assert {OutputEvaluationBlocker.SCORECARD_MISMATCH, OutputEvaluationBlocker.INSTRUMENT_MISMATCH}.issubset(instrument_mismatch.blockers)


def test_future_score_or_gate_cannot_attach():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    future_score = _score(at=T + timedelta(days=1), evaluated=T + timedelta(days=1), ident="score:future")
    future_gate = _gate(score=score, at=T + timedelta(days=1), evaluated=T + timedelta(days=1), ident="gate:future")
    for candidate_score, candidate_gate in ((future_score, gate), (score, future_gate)):
        value = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=candidate_score, gate_evaluation=candidate_gate)
        assert OutputEvaluationBlocker.FUTURE_ARTIFACT in value.blockers
        assert value.ready_for_output_decision is False


def test_scorecard_id_fingerprint_and_gate_config_mismatch_fail_closed():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    wrong_score = _score(ident="score:other")
    wrong_config_gate = _gate(score=score, config="gate-config-v2")
    score_value = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=wrong_score, gate_evaluation=gate)
    gate_value = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=wrong_config_gate)
    assert OutputEvaluationBlocker.SCORECARD_MISMATCH in score_value.blockers
    assert OutputEvaluationBlocker.GATE_CONFIG_MISMATCH in gate_value.blockers


def test_gate_action_context_is_exact_and_entry_cannot_serve_sell_trim():
    score = _score(); entry_gate = _gate(score=score); state = _state(score=score, gate=entry_gate)
    wrong_action = replace(entry_gate, action_context="REDUCE_EXISTING")
    mismatch = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=wrong_action)
    sell = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.SELL_TRIM_REVIEW), decision_scorecard=score, gate_evaluation=entry_gate)
    assert OutputEvaluationBlocker.GATE_CONTEXT_MISMATCH in mismatch.blockers
    assert sell.ready_for_output_decision is True
    assert sell.execution_gate_evaluation_id is None


def test_portfolio_snapshot_must_match_and_required_context_cannot_be_absent():
    score = _score(); gate = _gate(score=score, action="ROTATE_IN"); state = _state(score=score, gate=gate)
    wrong = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.ROTATION_REVIEW, portfolio="snapshot:other"), decision_scorecard=score, gate_evaluation=gate)
    missing = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.ROTATION_REVIEW, portfolio=None), decision_scorecard=score, gate_evaluation=gate)
    assert OutputEvaluationBlocker.PORTFOLIO_CONTEXT_MISMATCH in wrong.blockers
    assert OutputEvaluationBlocker.REQUIRED_PORTFOLIO_CONTEXT_MISSING in missing.blockers


def test_deep_analysis_is_informational_and_entry_requires_score_and_gate():
    state = _state()
    deep = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.DEEP_ANALYSIS, portfolio=None))
    entry = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.ENTRY_SETUP_REVIEW, portfolio=None))
    assert deep.ready_for_output_decision is True
    assert {OutputEvaluationBlocker.REQUIRED_SCORE_MISSING, OutputEvaluationBlocker.REQUIRED_GATE_MISSING}.issubset(entry.blockers)


def test_requirement_matrix_and_context_fingerprints_are_deterministic():
    assert {item.output_context for item in OUTPUT_CONTEXT_REQUIREMENTS} == set(BrainOutputContext)
    assert output_context_requirement(BrainOutputContext.ENTRY_SETUP_REVIEW).required_action_context.value == "FRESH_ENTRY"
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    entry = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    rotation_gate = _gate(score=score, action="ROTATE_IN", snapshot="snapshot:1", ident="gate:rotation")
    rotation_state = _state(score=score, gate=rotation_gate)
    rotation = create_brain_output_evaluation_context(rotation_state, _request(rotation_state, BrainOutputContext.ROTATION_REVIEW), decision_scorecard=score, gate_evaluation=rotation_gate)
    assert entry.fingerprint != rotation.fingerprint
    assert rotation.ready_for_output_decision is True


def test_same_state_can_support_multiple_contexts_and_reconstruction_is_deterministic():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    first = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    repeated = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    deep = create_brain_output_evaluation_context(state, _request(state, BrainOutputContext.DEEP_ANALYSIS, portfolio=None))
    assert first == repeated and first.unified_state_fingerprint == deep.unified_state_fingerprint


def test_builder_consumes_injected_versioned_requirement_policy_in_its_identity():
    score = _score(); gate = _gate(score=score); state = _state(score=score, gate=gate)
    alternative = create_brain_output_requirement_policy(
        policy_id=CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY.policy_id,
        version="v2-test",
        requirements=CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY.requirements,
    )
    current = create_brain_output_evaluation_context(state, _request(state), decision_scorecard=score, gate_evaluation=gate)
    governed = create_brain_output_evaluation_context(
        state, _request(state), decision_scorecard=score, gate_evaluation=gate,
        requirement_policy=alternative,
    )
    assert governed.requirement_policy_version == "v2-test"
    assert governed.requirement_policy_fingerprint == alternative.fingerprint
    assert governed.fingerprint != current.fingerprint


def test_contract_has_no_engines_actions_network_or_persistence():
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "output_evaluation_context.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "app.gates", "app.scoring.engine", "build_scorecard", "Canonical61DiagnosticRunner", "requests.", "urlopen", "httpx",
        "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "order(",
    ))
