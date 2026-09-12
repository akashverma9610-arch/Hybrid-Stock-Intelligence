from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json

import pytest

from app.backtest.models import HistoricalRotationCandidateContext, HistoricalRotationHistory
from app.backtest.rotation import HistoricalCapitalRotationReplayService
from app.backtest.portfolio import BacktestPortfolioReplayEngine
from app.backtest.models import HistoricalPortfolioGateEvaluation
from app.gates.engine import ExecutionGateEngine, GateInput, PortfolioExposure, SurveillanceObservation, TradeManagementPlan
from app.rotation.models import RotationConfig, RotationDecisionState
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.backtest.serialization import dump as backtest_dump
from tests.integration.test_historical_portfolio_gates import _context, _evaluate, _fixture
from tests.integration.test_historical_analytical_replay import GATE_CONFIG


ROTATION_CONFIG = RotationConfig("rotation-v1", Decimal(".8"), .7, Decimal("2"), True, True, False, "friction-v1", 1, 0)


def persisted_rotation(tmp_path):
    repo, run, candidate, original, scorecard, state = _fixture(tmp_path)
    incumbent = _context(repo, "rotation-incumbent", "7.0")
    gate_record, _gate_result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (incumbent,), candidate_sector="TECH",
        candidate_risk_amount=Decimal("1000"), candidate_allocation=Decimal(".20"))
    candidate_context = HistoricalRotationCandidateContext("rotation-candidate", candidate.evaluation_id,
        gate_record.portfolio_gate_evaluation_id, "TECH", True, "2.5", True, True, True, "1.0", None, 1,
        candidate.evaluation_timestamp, ("CONTEXTUAL_GATE_REQUIRED",))
    history = HistoricalRotationHistory("rotation-history", run.backtest_run_id, candidate.instrument_id, "NO_ACTION",
        candidate.evaluation_timestamp, 1, None, ROTATION_CONFIG.version, ())
    repo.save_historical_rotation_candidate_context(candidate_context); repo.save_historical_rotation_history(history)
    record, result = HistoricalCapitalRotationReplayService(repo).evaluate(run=run, replay_step_number=1,
        evaluation_timestamp=candidate.evaluation_timestamp, backtest_portfolio_state_id=state.backtest_portfolio_state_id,
        candidate_context_ids=(candidate_context.context_id,), holding_context_ids=(incumbent.context_id,),
        rotation_history_ids=(history.history_id,), rotation_config=ROTATION_CONFIG)
    return repo, run, candidate, scorecard, state, gate_record, incumbent, candidate_context, history, record, result


def test_historical_rotation_replay_reuses_canonical_engine_and_is_immutable(tmp_path):
    repo, run, candidate, scorecard, state, gate_record, incumbent, candidate_context, history, record, result = persisted_rotation(tmp_path)
    # The contextual gate is frozen and insufficient, so the canonical engine rejects it;
    # the adapter does not weaken eligibility or produce a capital movement.
    assert result.decision is RotationDecisionState.NO_ACTION
    assert record.decision == result.decision.value
    assert repo.get_historical_rotation_evaluation(record.rotation_evaluation_id) == record
    assert repo.get_decision_scorecard(scorecard.id).final_score == scorecard.final_score
    rebuilt = AuditReconstructionService(repo).reconstruct_historical_rotation_evaluation(record.rotation_evaluation_id, ROTATION_CONFIG)
    assert rebuilt[-1] == result
    with pytest.raises(ValueError, match="immutable"):
        repo.save_historical_rotation_evaluation(record)
    with pytest.raises(ValueError, match="configuration"):
        HistoricalCapitalRotationReplayService(repo).evaluate(run=run, replay_step_number=1,
            evaluation_timestamp=candidate.evaluation_timestamp, backtest_portfolio_state_id=state.backtest_portfolio_state_id,
            candidate_context_ids=(candidate_context.context_id,), holding_context_ids=(incumbent.context_id,),
            rotation_history_ids=(history.history_id,), rotation_config=RotationConfig("rotation-v2", Decimal(".8"), .7, Decimal("2"), True, True, False, "friction-v1", 1, 0))


def test_rotation_round_trips_duplicate_ids_events_and_frozen_future_inputs(tmp_path):
    repo, run, candidate, scorecard, state, gate_record, incumbent, candidate_context, history, record, result = persisted_rotation(tmp_path)
    assert repo.get_historical_rotation_candidate_context(candidate_context.context_id) == candidate_context
    assert repo.get_historical_rotation_history(history.history_id) == history
    assert repo.get_historical_rotation_evaluation(record.rotation_evaluation_id) == record
    for saver, value in ((repo.save_historical_rotation_candidate_context, candidate_context), (repo.save_historical_rotation_history, history), (repo.save_historical_rotation_evaluation, record)):
        with pytest.raises(ValueError, match="immutable"): saver(value)
    events=repo.list_backtest_events(run.backtest_run_id)
    assert [item.event_type.value for item in events[-2:]] == ["ROTATION_EVALUATED", "ROTATION_REJECTED"]
    assert all(record.rotation_evaluation_id in item.referenced_artifact_ids for item in events[-2:])
    before=(repo.get_historical_rotation_evaluation(record.rotation_evaluation_id), AuditReconstructionService(repo).reconstruct_historical_rotation_evaluation(record.rotation_evaluation_id, ROTATION_CONFIG)[-1])
    # Later contexts are persisted separately and cannot be selected by the frozen record.
    future_context=replace(candidate_context, context_id="future-candidate-context", known_at=candidate.evaluation_timestamp+timedelta(days=1))
    repo.save_historical_rotation_candidate_context(future_context)
    future_state=replace(state, backtest_portfolio_state_id="future-state", evaluation_timestamp=candidate.evaluation_timestamp+timedelta(days=1))
    repo.save_backtest_portfolio_state(future_state)
    assert repo.get_historical_rotation_evaluation(record.rotation_evaluation_id) == before[0]
    assert AuditReconstructionService(repo).reconstruct_historical_rotation_evaluation(record.rotation_evaluation_id, ROTATION_CONFIG)[-1] == before[1]
    assert "future-" not in json.dumps(backtest_dump(record), sort_keys=True)
    assert repo.get_decision_scorecard(scorecard.id) == scorecard and repo.get_backtest_portfolio_state(state.backtest_portfolio_state_id) == state


@pytest.mark.parametrize("target", ["candidate", "holding", "portfolio", "gate", "history", "config"])
def test_rotation_audit_tamper_matrix_fails_closed(tmp_path, target):
    repo, _run, _candidate, _scorecard, _state, _gate, _holding, context, _history, record, _result = persisted_rotation(tmp_path)
    if target == "candidate": tampered=replace(record, candidate_context_ids=("missing-candidate",))
    elif target == "holding": tampered=replace(record, holding_context_ids=("missing-holding",))
    elif target == "portfolio": tampered=replace(record, backtest_portfolio_state_id="missing-state")
    elif target == "history": tampered=replace(record, rotation_history_ids=("missing-history",))
    elif target == "config": tampered=replace(record, rotation_config_version="rotation-v2")
    else:
        tampered_context=replace(context, contextual_gate_evaluation_id="missing-contextual-gate")
        repo._connection.execute("UPDATE historical_rotation_candidate_contexts SET payload_json=? WHERE id=?", (json.dumps(backtest_dump(tampered_context), sort_keys=True), context.context_id)); repo._connection.commit(); tampered=record
    if target != "gate":
        repo._connection.execute("UPDATE historical_rotation_evaluations SET payload_json=? WHERE id=?", (json.dumps(backtest_dump(tampered), sort_keys=True), record.rotation_evaluation_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError):
        AuditReconstructionService(repo).reconstruct_historical_rotation_evaluation(record.rotation_evaluation_id, ROTATION_CONFIG)


def test_rotation_approved_and_cash_deployment_event_paths_are_append_only(tmp_path):
    repo, run, candidate, original, scorecard, state = _fixture(tmp_path, raw_score=Decimal("9"))
    # This positive event-path fixture already supplies a synthetic score.
    # Supply its confidence explicitly as well: unmapped real diagnostic text
    # must not manufacture confidence via the removed five-point fallback.
    incomplete_score_id = scorecard.id
    assert scorecard.data_confidence is None
    scorecard = replace(scorecard, id=scorecard.id + "-explicit-confidence", data_confidence=.8)
    repo.save_decision_scorecard(scorecard)
    candidate = replace(candidate, evaluation_id=candidate.evaluation_id + "-explicit-confidence",
                        decision_scorecard_id=scorecard.id)
    repo.save_historical_analytical_evaluation(candidate)
    assert repo.get_decision_scorecard(incomplete_score_id).data_confidence is None
    at=candidate.evaluation_timestamp
    from tests.fixtures.gate_provenance import synthetic_evaluate
    from app.gates.score_provenance import score_evidence
    gate=synthetic_evaluate(ExecutionGateEngine(GATE_CONFIG, __import__("tests.integration.test_historical_analytical_replay", fromlist=["CALENDAR"]).CALENDAR),
        candidate_score_evidence=score_evidence(scorecard),
        instrument_id=candidate.instrument_id, strategy_version=scorecard.strategy_version, registry_version=run.registry_version,
        scoring_configuration_version=run.scoring_config_version, action_context=__import__("app.gates.engine", fromlist=["ActionContext"]).ActionContext.ROTATE_IN,
        as_of_timestamp=at, evaluated_at=at, inputs=GateInput(scorecard.id, scorecard.final_score, state.snapshot.snapshot_id, at, Decimal("7"),
            surveillance=SurveillanceObservation("surv", at, "fixture", True, 0, 0, Decimal(".1")),
            trade_plan=TradeManagementPlan("plan", Decimal(".5"), Decimal(".4"), True, True, "after T1", "valid", "strategy", GATE_CONFIG.version),
            exposure=PortfolioExposure(Decimal("100000"), Decimal("1000"), Decimal("1000"), Decimal(".2"), Decimal(".1")),
            earnings_scheduled_at=at+timedelta(days=20), earnings_schedule_verified_at=at))
    repo.save_execution_gate_evaluation(gate)
    gate_record=HistoricalPortfolioGateEvaluation("eligible-gate", run.backtest_run_id, 1, at, candidate.evaluation_id, original.id,
        state.backtest_portfolio_state_id, GATE_CONFIG.version, (), gate.id, "COMPLETED", (), "eligible-gate-fingerprint")
    repo.save_historical_portfolio_gate_evaluation(gate_record)
    context=HistoricalRotationCandidateContext("eligible-rotation-candidate", candidate.evaluation_id, gate_record.portfolio_gate_evaluation_id,
        "TECH", True, "2.5", True, True, True, "1", None, 1, at)
    repo.save_historical_rotation_candidate_context(context)
    incumbent=_context(repo, "eligible-incumbent", "7")
    ledger_ids=tuple(x.ledger_event_id for x in repo.list_backtest_portfolio_ledger_events(run.backtest_run_id))
    record,result=HistoricalCapitalRotationReplayService(repo).evaluate(run=run,replay_step_number=1,evaluation_timestamp=at,
        backtest_portfolio_state_id=state.backtest_portfolio_state_id,candidate_context_ids=(context.context_id,),holding_context_ids=(incumbent.context_id,),rotation_history_ids=(),rotation_config=ROTATION_CONFIG)
    events=repo.list_backtest_events(run.backtest_run_id)[-2:]
    assert result.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    assert [x.event_type.value for x in events] == ["ROTATION_EVALUATED", "ROTATION_APPROVED_ANALYTICALLY"]
    assert all(x.backtest_run_id == run.backtest_run_id and x.replay_step_number == 1 and x.evaluation_timestamp == at and record.rotation_evaluation_id in x.referenced_artifact_ids for x in events)
    assert tuple(x.ledger_event_id for x in repo.list_backtest_portfolio_ledger_events(run.backtest_run_id)) == ledger_ids

    cash=BacktestPortfolioReplayEngine(__import__("tests.integration.test_historical_analytical_replay", fromlist=["CALENDAR"]).CALENDAR).reconstruct(run_id=run.backtest_run_id,step_number=2,at=at,starting_capital=Decimal("100000"),events=(),prices=())
    cash=replace(cash, backtest_portfolio_state_id="cash-only-state"); repo.save_backtest_portfolio_state(cash)
    cash_gate=replace(gate_record, portfolio_gate_evaluation_id="cash-eligible-gate", backtest_portfolio_state_id=cash.backtest_portfolio_state_id); repo.save_historical_portfolio_gate_evaluation(cash_gate)
    cash_context=replace(context, context_id="cash-candidate", contextual_gate_evaluation_id=cash_gate.portfolio_gate_evaluation_id); repo.save_historical_rotation_candidate_context(cash_context)
    cash_record,cash_result=HistoricalCapitalRotationReplayService(repo).evaluate(run=run,replay_step_number=2,evaluation_timestamp=at,
        backtest_portfolio_state_id=cash.backtest_portfolio_state_id,candidate_context_ids=(cash_context.context_id,),holding_context_ids=(),rotation_history_ids=(),rotation_config=ROTATION_CONFIG)
    assert cash_result.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    assert [x.event_type.value for x in repo.list_backtest_events(run.backtest_run_id)[-2:]] == ["ROTATION_EVALUATED", "ROTATION_APPROVED_ANALYTICALLY"]
    assert cash_record.preferred_candidate_id == candidate.instrument_id
