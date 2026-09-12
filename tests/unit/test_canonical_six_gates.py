from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

import pytest
from tests.fixtures.gate_provenance import synthetic_evaluate
from app.gates.score_provenance import score_evidence

from app.gates.engine import (
    ActionContext, ExchangeCalendar, ExecutionGateConfig, ExecutionGateEngine, GateInput,
    PortfolioExposure, SurveillanceObservation, TradeManagementPlan,
)
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.six_gates_evidence import (
    CanonicalSixGatesEvaluationSource, SixGatesEvidenceStoredSource,
)
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.intelligence.unified_state_builder import UnifiedIntelligenceStateBuilder
from app.portfolio.canonical_six_gates import canonical_execution_gate_evaluation_from
from app.portfolio.canonical_six_gates_activation import CanonicalPortfolioSixGatesActivator
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository

from tests.unit.test_canonical_decision_score_activation import T, _Core, _activate, _repository


def _config() -> ExecutionGateConfig:
    return ExecutionGateConfig(
        "isolated-six-gates-v1", Decimal("0.10"), "isolated-friction-v1", Decimal("0.01"), True,
        20, Decimal("0.10"), Decimal("0.05"), 1, True, Decimal("0.02"), 5,
        Decimal("0.25"), Decimal("0.50"), True, Decimal("0.10"), Decimal("0.20"),
        Decimal("0.30"), 5, "isolated-heat-v1",
    )


def _evaluation(score):
    inputs = GateInput(
        scorecard_id=score.id, raw_decision_score=score.final_score,
        snapshot_id="isolated-pit-snapshot", snapshot_as_of_timestamp=T,
        surveillance=SurveillanceObservation("surveillance:isolated", T, "NSE", True, 0, 0, Decimal("0.20"), ("evidence:surveillance",)),
        trade_plan=TradeManagementPlan("plan:isolated", Decimal("0.25"), Decimal("0.50"), True, True, "after T1", "isolated", "canonical-universe-analysis", "v1"),
        exposure=PortfolioExposure(Decimal("100"), Decimal("1"), Decimal("1"), Decimal("0.10"), Decimal("0.10"), ("evidence:portfolio",)),
        earnings_scheduled_at=T + timedelta(days=20), earnings_schedule_verified_at=T,
        evidence_ids=("evidence:input",), diagnostic_ids=("diagnostic:lineage",),
    )
    return synthetic_evaluate(ExecutionGateEngine(_config(), ExchangeCalendar("NSE")),
        instrument_id=score.instrument_id, strategy_version=score.strategy_version,
        registry_version="diagnostic-registry-v1", scoring_configuration_version=score.configuration_version,
        action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=T, evaluated_at=T, inputs=inputs,
        candidate_score_evidence=score_evidence(score),
    )


def test_canonical_six_gates_persist_reopen_and_remain_idempotent(tmp_path) -> None:
    repository = _repository(tmp_path)
    score_id = _activate(repository).outcomes[0].score_id
    score = repository.get_canonical_decision_scorecard(score_id)
    value = canonical_execution_gate_evaluation_from(_evaluation(score), score=score)
    assert repository.save_canonical_execution_gate_evaluation(value) == value
    assert repository.save_canonical_execution_gate_evaluation(value) == value
    assert repository._connection.execute("SELECT COUNT(*) FROM canonical_execution_gate_decisions").fetchone()[0] == 6
    assert repository._connection.execute("SELECT COUNT(*) FROM strategy_versions").fetchone()[0] == 0
    assert repository._connection.execute("SELECT COUNT(*) FROM decision_scorecards").fetchone()[0] == 0
    assert repository._connection.execute("SELECT COUNT(*) FROM execution_gate_evaluations").fetchone()[0] == 0
    foreign_keys = repository._connection.execute("PRAGMA foreign_key_list(canonical_execution_gate_evaluations)").fetchall()
    assert {(row[2], row[3], row[4]) for row in foreign_keys} == {
        ("canonical_diagnostic_strategy_definitions", "strategy_id", "strategy_id"),
        ("canonical_diagnostic_strategy_definitions", "strategy_version", "strategy_version"),
        ("canonical_decision_scorecards", "scorecard_id", "id"),
    }
    repository.close()
    reopened = SQLiteStrategyGovernanceRepository(tmp_path / "canonical-score.db")
    assert reopened.get_canonical_execution_gate_evaluation(value.evaluation.id) == value
    reopened.close()


def test_canonical_six_gates_rejects_tampering_and_generic_score_anchor(tmp_path) -> None:
    repository = _repository(tmp_path)
    score = repository.get_canonical_decision_scorecard(_activate(repository).outcomes[0].score_id)
    value = canonical_execution_gate_evaluation_from(_evaluation(score), score=score)
    with pytest.raises(ValueError, match="fingerprint"):
        repository.save_canonical_execution_gate_evaluation(
            replace(value, artifact_fingerprint="tampered"),
        )
    repository.close()


def test_canonical_six_gates_projects_to_shared_brain_as_context_dependent(tmp_path) -> None:
    repository = _repository(tmp_path)
    score = repository.get_canonical_decision_scorecard(_activate(repository).outcomes[0].score_id)
    value = canonical_execution_gate_evaluation_from(_evaluation(score), score=score)
    repository.save_canonical_execution_gate_evaluation(value)
    source = SixGatesEvidenceStoredSource(CanonicalSixGatesEvaluationSource(repository))
    state = UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_Core(), source)).build(
        score.instrument_id, as_of=T,
    )
    reference = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.SIX_GATES)
    assert reference.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert reference.artifact_ids == (value.evaluation.id,)
    repository.close()


def test_activation_fails_closed_without_an_approved_gate_configuration(tmp_path) -> None:
    repository = _repository(tmp_path, missing={"NSE:INE955D01029": (45,)})
    _activate(repository)
    run = CanonicalPortfolioSixGatesActivator(governance=repository, engine=None).materialize(
        execution_as_of=T,
    )
    by_instrument = {item.instrument_id: item for item in run.outcomes}
    assert by_instrument["NSE:INE372A01015"].status == "NOT_EVALUATED"
    assert "UNRESOLVED_CONFIG:min_score_advantage" in by_instrument["NSE:INE372A01015"].blockers
    assert by_instrument["NSE:INE955D01029"].blockers == ("DECISION_SCORE_NOT_YET_COMPUTED",)
    assert repository.list_canonical_execution_gate_evaluations() == ()
    repository.close()
