from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.domain.models import FreshnessStatus, StrategyVersionReference
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.six_gates_evidence import (
    SixGatesEvidenceStoredSource,
    StrategyGovernanceSixGatesEvaluationSource,
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


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
I = "NSE:INE000A01001"
REFERENCE = StrategyVersionReference("shared-brain", "gates-v1")
SUCCESSOR = StrategyVersionReference("shared-brain", "gates-v2")


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


@dataclass(frozen=True)
class _Decision:
    gate_id: str = "GATE_5_HEAT"
    outcome: str = "PASS"
    evidence_ids: tuple[str, ...] = ("evidence:heat",)


@dataclass(frozen=True)
class _Evaluation:
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


class _Evaluations:
    def __init__(self, values): self.values = tuple(values)
    def list_stored_six_gates_evaluations(self, canonical_instrument_id, *, as_of): return self.values


def _evaluation(*, at=T - timedelta(days=1), evaluated=None, instrument=I, reference=REFERENCE, ident=None, snapshot="snapshot:portfolio-a", context="FRESH_ENTRY"):
    return _Evaluation(
        ident or f"gates:{reference.version}:{at.date().isoformat()}:{snapshot}", instrument, reference,
        "diagnostic-registry-v1", "score-config-v1", f"gates-config:{reference.version}", "scorecard:1",
        snapshot, context, at, evaluated or at, (_Decision(),), "EXECUTABLE", (), (), (),
        ("evidence:heat",), ("diagnostic:1",), (("max_total_heat", "0.10"),),
    )


def _builder(values=None):
    return UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(
        _CoreSource(), SixGatesEvidenceStoredSource(_Evaluations(values) if values is not None else None),
    ))


def _reference(state):
    return next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.SIX_GATES)


def test_missing_gate_boundary_and_not_yet_computed_are_explicit():
    missing = _reference(_builder().build(I, as_of=T))
    absent = _reference(_builder(()).build(I, as_of=T))
    assert missing.warnings == ("SIX_GATES_DURABLE_READ_BOUNDARY_MISSING",)
    assert absent.warnings == ("SIX_GATES_NOT_YET_COMPUTED",)


def test_durable_gate_artifact_is_bounded_and_explicitly_context_dependent():
    state = _builder((_evaluation(),)).build(I, as_of=T)
    reference = _reference(state)
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert reference.artifact_ids == (_evaluation().id,)
    assert {"SIX_GATES_CONTEXT_DEPENDENT", "SIX_GATES_RESULT_DOWNSTREAM_ONLY"}.issubset(reference.warnings)
    assert "GATE_5_HEAT" not in repr(state)
    dependency = next(item for item in state.dependency_lineage if item.artifact_id == _evaluation().id)
    assert dependency.invalidation_domain is IntelligenceInvalidationDomain.POLICY


def test_future_and_first_observed_later_gate_artifacts_do_not_backdate():
    future = _evaluation(at=T + timedelta(days=1), ident="gates:future")
    observed_later = _evaluation(at=T - timedelta(days=1), evaluated=T + timedelta(days=1), ident="gates:later")
    builder = _builder((future, observed_later))
    before = _reference(builder.build(I, as_of=T))
    after = _reference(builder.build(I, as_of=T + timedelta(days=1)))
    assert before.availability is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert after.availability is IntelligenceEvidenceAvailability.PARTIAL


def test_policy_history_and_selection_are_deterministic_without_context_conflict():
    old = _evaluation(at=T - timedelta(days=2), reference=REFERENCE, snapshot="snapshot:old")
    latest_a = _evaluation(at=T - timedelta(days=1), reference=SUCCESSOR, snapshot="snapshot:a")
    latest_b = _evaluation(at=T - timedelta(days=1), reference=SUCCESSOR, snapshot="snapshot:b")
    old_reference = _reference(_builder((latest_b, old, latest_a)).build(I, as_of=old.as_of_timestamp))
    selected = _reference(_builder((latest_b, old, latest_a)).build(I, as_of=T))
    reverse = _reference(_builder((latest_a, old, latest_b)).build(I, as_of=T))
    assert old_reference.artifact_ids == (old.id,)
    assert selected == reverse
    assert selected.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert "CONFLICT" not in " ".join(selected.warnings)


def test_exact_identity_scorecard_and_portfolio_lineage_are_not_copied_or_interpreted():
    valid = _evaluation(ident="gates:valid")
    wrong = _evaluation(instrument="NSE:OTHER", ident="gates:other")
    state = _builder((valid, wrong)).build(I, as_of=T)
    reference = _reference(state)
    assert reference.artifact_ids == (valid.id,)
    assert reference.source_provenance_fingerprint is not None
    assert "snapshot:portfolio-a" not in repr(state)
    assert "scorecard:1" not in repr(state)


def test_same_core_state_is_shared_across_output_and_portfolio_requests():
    state = _builder((_evaluation(),)).build(I, as_of=T)
    entry = create_brain_output_request(state, output_context=BrainOutputContext.ENTRY_SETUP_REVIEW)
    sell = create_brain_output_request(
        state, output_context=BrainOutputContext.SELL_TRIM_REVIEW,
        portfolio_context=PortfolioContextRef("portfolio:other", "snapshot:other", "portfolio-fingerprint"),
    )
    assert entry.intelligence_state_fingerprint == sell.intelligence_state_fingerprint == state.fingerprint


def test_existing_repository_read_path_is_exact_evaluation_id_only():
    evaluation = _evaluation()
    class _Repository:
        def __init__(self): self.calls = []
        def get_execution_gate_evaluation(self, evaluation_id): self.calls.append(evaluation_id); return evaluation
    repository = _Repository()
    source = StrategyGovernanceSixGatesEvaluationSource(repository, evaluation_id=evaluation.id)
    assert source.list_stored_six_gates_evaluations(I, as_of=T) == (evaluation,)
    assert repository.calls == [evaluation.id]


def test_adapter_is_stored_only_and_excludes_gate_execution_scoring_actions_and_persistence():
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "six_gates_evidence.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "app.gates", "build_scorecard", "Canonical61DiagnosticRunner", "requests.", "urlopen", "httpx",
        "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "BUY", "HOLD", "SELL", "TRIM", "ROTATE", "order(",
    ))
