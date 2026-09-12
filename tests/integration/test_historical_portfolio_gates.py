from dataclasses import replace
from datetime import UTC, timedelta
from decimal import Decimal
import json

import pytest
from tests.fixtures.gate_provenance import fixture_gate_composition


@pytest.fixture(autouse=True)
def isolated_portfolio_gate_arithmetic():
    with fixture_gate_composition():
        yield

from app.backtest.engine import backtest_run_fingerprint
from app.backtest.models import BacktestEvent, BacktestEventType, BacktestRunStatus, HistoricalHoldingGateContext
from app.backtest.portfolio import BacktestPortfolioLedgerEvent, BacktestPortfolioLedgerType, BacktestPortfolioReplayEngine
from app.backtest.portfolio_gates import HistoricalPortfolioGateReplayService
from app.gates.engine import ExecutionGateConfig, GateOutcome
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.portfolio.models import PriceReference
from tests.integration.test_historical_analytical_replay import CALENDAR, GATE_CONFIG, T, setup


def _gate(result, identifier):
    return next(item for item in result.decisions if item.gate_id == identifier)


@fixture_gate_composition()
def _fixture(tmp_path, *, raw_score=Decimal("8.5"), config=GATE_CONFIG):
    """Seed only frozen prerequisites; the contextual service remains the evaluator path."""
    from app.backtest.analytical import HistoricalAnalyticalReplayService
    from app.backtest.engine import BacktestReplayEngine

    repo, _manifest, schedule, gap, source_run, analytical = setup(tmp_path)
    BacktestReplayEngine(repo).run_analytical(source_run, schedule, CALENDAR, gap, HistoricalAnalyticalReplayService(repo, analytical))
    source = repo.list_historical_analytical_evaluations(source_run.backtest_run_id, 1)[0]
    scorecard = repo.get_decision_scorecard(source.decision_scorecard_id)
    original = repo.get_execution_gate_evaluation(source.execution_gate_evaluation_id)
    assert scorecard is not None and original is not None
    run = replace(source_run, backtest_run_id=f"context-{raw_score}-{config.version}", gate_config_version=config.version,
                  status=BacktestRunStatus.CREATED, completed_at=None, fingerprint="")
    run = replace(run, fingerprint=backtest_run_fingerprint(run))
    repo.save_backtest_run(run)
    cloned_score = replace(scorecard, id=f"{run.backtest_run_id}-score", final_score=raw_score, score_status="COMPLETE")
    repo.save_decision_scorecard(cloned_score)
    candidate = replace(source, evaluation_id=f"{run.backtest_run_id}-candidate", decision_scorecard_id=cloned_score.id,
                        execution_gate_evaluation_id=original.id)
    repo.save_historical_analytical_evaluation(candidate)
    repo.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:000001", run.backtest_run_id,
        BacktestEventType.REPLAY_STARTED, candidate.evaluation_timestamp, 1, candidate.evaluation_timestamp, (), "replay started", {}, candidate.evaluation_timestamp))
    buy = BacktestPortfolioLedgerEvent(f"{run.backtest_run_id}-buy", run.backtest_run_id, BacktestPortfolioLedgerType.HYPOTHETICAL_BUY,
        candidate.evaluation_timestamp, candidate.evaluation_timestamp, "fixture", "fixture", "incumbent", Decimal("100"), Decimal("100"),
        Decimal("10000"), Decimal("0"), Decimal("0"), Decimal("-10000"), None, "UNKNOWN", Decimal("90"))
    repo.append_backtest_portfolio_ledger_event(buy)
    mark = PriceReference(f"{run.backtest_run_id}-mark", "incumbent", Decimal("100"), candidate.evaluation_timestamp, candidate.evaluation_timestamp)
    state = BacktestPortfolioReplayEngine(CALENDAR).reconstruct(run_id=run.backtest_run_id, step_number=1, at=candidate.evaluation_timestamp,
        starting_capital=Decimal("100000"), events=(buy,), prices=(mark,))
    repo.save_backtest_portfolio_state(state)
    return repo, run, candidate, original, cloned_score, state


def _context(repo, identifier, score=None, *, candidate_id=None, config=GATE_CONFIG):
    if score is not None and candidate_id is None:
        # Explicit isolated incumbent artifacts replace the formerly unlinked
        # raw string. Preserve every original comparison value/outcome.
        from app.domain.models import Instrument
        repo.save_instrument(Instrument("incumbent", "INCUMBENT", "MOCK"))
        source = repo.list_historical_analytical_evaluations("history-run", 1)[0]
        card = replace(repo.get_decision_scorecard(source.decision_scorecard_id),
            id=identifier+"-card", instrument_id="incumbent", final_score=Decimal(score), score_status="COMPLETE")
        repo.save_decision_scorecard(card)
        result = replace(repo.get_execution_gate_evaluation(source.execution_gate_evaluation_id),
            id=identifier+"-gate", instrument_id="incumbent", scorecard_id=card.id,
            raw_decision_score=card.final_score, comparison_score=card.final_score,
            rotation_adjustment=Decimal("0"), gate_configuration_version=config.version)
        repo.save_execution_gate_evaluation(result)
        source = replace(source, evaluation_id=identifier+"-analytics", instrument_id="incumbent",
            decision_scorecard_id=card.id, execution_gate_evaluation_id=result.id, gate_config_version=config.version)
        repo.save_historical_analytical_evaluation(source)
        candidate_id = source.evaluation_id
    context = HistoricalHoldingGateContext(identifier, "incumbent", candidate_id, score or "7.0", score, .82,
        "2.1", "0", "TECH", ("MISSING_STOP",) if score is None else ())
    repo.save_historical_holding_gate_context(context)
    return context


@fixture_gate_composition()
def _evaluate(repo, run, candidate, original, state, config, contexts=(), at=None, **inputs):
    return HistoricalPortfolioGateReplayService(repo, CALENDAR).evaluate(run=run, replay_step_number=1,
        evaluation_timestamp=at or candidate.evaluation_timestamp, historical_analytical_evaluation_id=candidate.evaluation_id,
        original_execution_gate_evaluation_id=original.id, backtest_portfolio_state_id=state.backtest_portfolio_state_id,
        holding_context_ids=tuple(context.context_id for context in contexts), gate_config=config, **inputs)


def test_portfolio_context_gate_one_and_gate_five_canonical_semantics(tmp_path):
    repo, run, candidate, original, scorecard, state = _fixture(tmp_path)
    missing, result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG)
    assert _gate(result, "GATE_1_ROTATION").outcome is GateOutcome.INSUFFICIENT_DATA
    assert result.raw_decision_score == scorecard.final_score and repo.get_historical_portfolio_gate_evaluation(missing.portfolio_gate_evaluation_id) == missing

    below_context = _context(repo, "below", "8.0")
    _below, result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (below_context,), candidate_sector="TECH",
        candidate_risk_amount=Decimal("1000"), candidate_allocation=Decimal(".20"))
    assert _gate(result, "GATE_1_ROTATION").outcome is GateOutcome.FAIL
    assert _gate(result, "GATE_1_ROTATION").parameters["advantage"] == "0.5"
    assert _gate(result, "GATE_5_HEAT").outcome is GateOutcome.PASS

    above_context = _context(repo, "above", "7.0")
    _above, result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (above_context,), candidate_sector="TECH",
        candidate_risk_amount=Decimal("1000"), candidate_allocation=Decimal(".20"))
    assert _gate(result, "GATE_1_ROTATION").outcome is GateOutcome.PASS
    strict = replace(GATE_CONFIG, version="gates-strict", require_economic_hurdle=True, net_economic_hurdle=Decimal(".05"))
    strict_run = replace(run, backtest_run_id="context-strict", gate_config_version=strict.version, fingerprint="")
    strict_run = replace(strict_run, fingerprint=backtest_run_fingerprint(strict_run)); repo.save_backtest_run(strict_run)
    repo.append_backtest_event(BacktestEvent("context-strict:event:000001", strict_run.backtest_run_id, BacktestEventType.REPLAY_STARTED, candidate.evaluation_timestamp, 1, candidate.evaluation_timestamp, (), "started", {}, candidate.evaluation_timestamp))
    strict_state = replace(state, backtest_portfolio_state_id="context-strict-state", backtest_run_id=strict_run.backtest_run_id); repo.save_backtest_portfolio_state(strict_state)
    strict_context = _context(repo, "strict-source", "7.0", config=strict)
    _strict, result = _evaluate(repo, strict_run, candidate, original, strict_state, strict, (strict_context,))
    assert _gate(result, "GATE_1_ROTATION").outcome is GateOutcome.INSUFFICIENT_DATA
    assert repo.get_execution_gate_evaluation(original.id) == original and repo.get_decision_scorecard(scorecard.id) == scorecard


@pytest.mark.parametrize("kind,allocation,risk,expected", [
    ("stock", Decimal(".26"), Decimal("1000"), GateOutcome.FAIL),
    ("sector", Decimal(".20"), Decimal("1000"), GateOutcome.FAIL),
    ("heat", Decimal(".20"), Decimal("7000"), GateOutcome.FAIL),
    ("missing", None, None, GateOutcome.INSUFFICIENT_DATA),
])
def test_portfolio_context_gate_five_caps_and_missing_risk(tmp_path, kind, allocation, risk, expected):
    repo, run, candidate, original, _scorecard, state = _fixture(tmp_path)
    if kind == "sector":
        exposure = replace(state.snapshot.exposure, sector_exposure={"TECH": Decimal(".36"), "UNKNOWN": Decimal(".10")})
        state = replace(state, backtest_portfolio_state_id="sector-cap-state", snapshot=replace(state.snapshot, exposure=exposure))
        repo.save_backtest_portfolio_state(state)
    context = _context(repo, f"context-{kind}", "7.0")
    _record, result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (context,), candidate_sector="TECH",
        candidate_risk_amount=risk, candidate_allocation=allocation)
    assert _gate(result, "GATE_5_HEAT").outcome is expected


def test_contextual_gate_round_trip_audit_and_integrity_rejection(tmp_path):
    repo, run, candidate, original, _scorecard, state = _fixture(tmp_path)
    context = _context(repo, "round-trip", "7.0")
    record, result = _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (context,), candidate_sector="TECH",
        candidate_risk_amount=Decimal("1000"), candidate_allocation=Decimal(".20"))
    assert repo.get_historical_holding_gate_context(context.context_id) == context
    assert repo.get_historical_portfolio_gate_evaluation(record.portfolio_gate_evaluation_id) == record
    rebuilt = AuditReconstructionService(repo).reconstruct_historical_portfolio_gate_evaluation(record.portfolio_gate_evaluation_id, GATE_CONFIG, CALENDAR)
    assert rebuilt[-1] == result
    with pytest.raises(ValueError, match="immutable"):
        repo.save_historical_holding_gate_context(context)
    with pytest.raises(ValueError, match="immutable"):
        repo.save_historical_portfolio_gate_evaluation(record)

    future_candidate = replace(candidate, evaluation_id="future-candidate", evaluation_timestamp=candidate.evaluation_timestamp + timedelta(days=1))
    repo.save_historical_analytical_evaluation(future_candidate)
    with pytest.raises(ValueError, match="Future candidate"):
        _evaluate(repo, run, future_candidate, original, state, GATE_CONFIG, at=candidate.evaluation_timestamp)
    future_context = _context(repo, "future-holding", "7.0", candidate_id=future_candidate.evaluation_id)
    with pytest.raises(ValueError, match="Future or missing holding"):
        _evaluate(repo, run, candidate, original, state, GATE_CONFIG, (future_context,))
    future_state = replace(state, backtest_portfolio_state_id="future-state", evaluation_timestamp=candidate.evaluation_timestamp + timedelta(days=1))
    repo.save_backtest_portfolio_state(future_state)
    with pytest.raises(ValueError, match="Future candidate or portfolio"):
        _evaluate(repo, run, candidate, original, future_state, GATE_CONFIG)
    with pytest.raises(ValueError, match="configuration"):
        _evaluate(repo, run, candidate, original, state, replace(GATE_CONFIG, version="future-config"))
    contextual_events = repo.list_backtest_events(run.backtest_run_id)[1:]
    assert all(event.event_type in {BacktestEventType.PORTFOLIO_GATES_EVALUATED, BacktestEventType.PORTFOLIO_GATES_INSUFFICIENT} for event in contextual_events)
    assert [event.event_id for event in contextual_events] == sorted(event.event_id for event in contextual_events)

    tampered = replace(state, evaluation_timestamp=candidate.evaluation_timestamp + timedelta(days=1))
    repo._connection.execute("UPDATE backtest_portfolio_states SET payload_json=? WHERE id=?", (json.dumps(__import__("app.backtest.portfolio", fromlist=["state_dump"]).state_dump(tampered), sort_keys=True), state.backtest_portfolio_state_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError, match="as-of"):
        AuditReconstructionService(repo).reconstruct_historical_portfolio_gate_evaluation(record.portfolio_gate_evaluation_id, GATE_CONFIG, CALENDAR)
