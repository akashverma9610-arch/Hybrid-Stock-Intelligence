from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.backtest.models import HistoricalHoldingGateContext, HistoricalRotationCandidateContext, HistoricalRotationHistory
from app.backtest.rotation import HistoricalCapitalRotationReplayService
from app.rotation.models import RotationConfig, RotationDecisionState, RotationStance


T = datetime(2026, 3, 2, 15, 30, tzinfo=UTC)
CONFIG = RotationConfig("rotation-history-v1", Decimal(".8"), .7, Decimal("2"), True, True, True, "friction-v1", 1, 3)


class Repo:
    def __init__(self, candidate_score=Decimal("9"), confidence=.8, gate="EXECUTABLE", candidate_at=T):
        self.scorecards={"candidate-score": SimpleNamespace(id="candidate-score", final_score=candidate_score, score_status="COMPLETE", data_confidence=confidence)}
        self.evaluations={"candidate-eval": SimpleNamespace(evaluation_id="candidate-eval", instrument_id="candidate", decision_scorecard_id="candidate-score", evaluation_timestamp=candidate_at)}
        self.gates={"gate-result": SimpleNamespace(id="gate-result", eligibility=SimpleNamespace(value=gate))}
        self.portfolio_gates={"contextual-gate": SimpleNamespace(historical_analytical_evaluation_id="candidate-eval", backtest_portfolio_state_id="state", resulting_execution_gate_evaluation_id="gate-result", evaluation_timestamp=T)}
    def get_historical_analytical_evaluation(self, key): return self.evaluations.get(key)
    def get_historical_portfolio_gate_evaluation(self, key): return self.portfolio_gates.get(key)
    def get_execution_gate_evaluation(self, key): return self.gates.get(key)
    def get_decision_scorecard(self, key): return self.scorecards.get(key)


def candidate(*, rr="2.5", sector=True, friction=".2", benefit="1", confirmations=1):
    return HistoricalRotationCandidateContext("candidate-context", "candidate-eval", "contextual-gate", "TECH", sector, rr, True, True, True, benefit, friction, confirmations, T)


def holding(identifier="holding", *, raw="8", adjustment="0", confidence=.8, rr="2.2", pnl=Decimal("0")):
    return HistoricalHoldingGateContext(identifier, identifier, None, raw, str(Decimal(raw)+Decimal(adjustment)), confidence, rr, adjustment, "TECH", ())


def state(*, holdings=(holding(),), cash=Decimal("1000")):
    items=tuple(SimpleNamespace(instrument_id=x.instrument_id, market_value=Decimal("10000"), unrealized_pnl=Decimal("0"), analytics=None) for x in holdings)
    return SimpleNamespace(snapshot=SimpleNamespace(snapshot_id="snapshot", cash=SimpleNamespace(amount=cash), holdings=items))


def run(): return SimpleNamespace(strategy_version="strategy:1", registry_version="registry", scoring_config_version="score", gate_config_version="gates", rotation_config_version=CONFIG.version)


def evaluate(repo=None, *, candidates=(candidate(),), holdings=(holding(),), history=(), config=CONFIG, at=T, portfolio=None):
    return HistoricalCapitalRotationReplayService(repo or Repo()).evaluate_frozen(run=run(), evaluation_timestamp=at,
        state=portfolio or state(holdings=holdings), candidate_contexts=candidates, holding_contexts=holdings, history=history, rotation_config=config)


def test_historical_adapter_hurdle_and_canonical_candidate_failures():
    below=evaluate(Repo(candidate_score=Decimal("8.7")))
    above=evaluate()
    assert below.decision is RotationDecisionState.NO_ACTION and below.comparisons[0].hurdle == Decimal(".8")
    assert above.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    for args in ((candidate(rr="1.5"), Repo()), (candidate(sector=False), Repo()), (candidate(friction="2", benefit="1"), Repo()), (candidate(), Repo(confidence=.5)), (candidate(), Repo(gate="BLOCKED"))):
        result=evaluate(args[1], candidates=(args[0],))
        assert result.decision is RotationDecisionState.NO_ACTION and result.blocked_candidate_ids == ("candidate",)


def test_historical_adapter_weakest_loss_cash_and_deterministic_ranking():
    strong_loss=holding("A", raw="9", rr="3")
    weak_gain=holding("B", raw="7", rr="2")
    result=evaluate(holdings=(strong_loss, weak_gain))
    assert result.weakest_holding_id == "B"  # P&L is not a ranking input.
    cash=evaluate(holdings=(), portfolio=state(holdings=(), cash=Decimal("100000")))
    assert cash.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED and cash.preferred_candidate_id == "candidate"
    repo=Repo(); repo.evaluations.update({"b-eval": SimpleNamespace(evaluation_id="b-eval", instrument_id="B", decision_scorecard_id="b-score", evaluation_timestamp=T), "a-eval": SimpleNamespace(evaluation_id="a-eval", instrument_id="A", decision_scorecard_id="a-score", evaluation_timestamp=T)})
    repo.scorecards.update({"b-score": SimpleNamespace(id="b-score", final_score=Decimal("9"), score_status="COMPLETE", data_confidence=.8), "a-score": SimpleNamespace(id="a-score", final_score=Decimal("9"), score_status="COMPLETE", data_confidence=.8)})
    for key, ev in (("a-gate", "a-eval"), ("b-gate", "b-eval")):
        repo.portfolio_gates[key]=SimpleNamespace(historical_analytical_evaluation_id=ev, backtest_portfolio_state_id="state", resulting_execution_gate_evaluation_id="gate-result", evaluation_timestamp=T)
    ranked=(HistoricalRotationCandidateContext("b", "b-eval", "b-gate", "TECH", True, "2.5", True, True, True, "1", ".2", 1, T), HistoricalRotationCandidateContext("a", "a-eval", "a-gate", "TECH", True, "2.5", True, True, True, "1", ".2", 1, T), candidate())
    assert [x.candidate.instrument_id for x in evaluate(repo, candidates=ranked).ranked_candidates] == ["A", "B", "candidate"]


def test_historical_adapter_raw_scores_confirmation_cooldown_and_future_rejection():
    adjusted=holding(raw="8", adjustment="-.5")
    result=evaluate(holdings=(adjusted,))
    assert adjusted.raw_score == "8" and result.comparisons[0].holding_comparison_score == Decimal("7.5")
    strict=RotationConfig("rotation-history-v1", Decimal(".8"), .7, Decimal("2"), True, True, True, "friction-v1", 2, 3)
    assert evaluate(candidates=(candidate(confirmations=1),), config=strict).decision is RotationDecisionState.NO_ACTION
    cooldown=(HistoricalRotationHistory("recent", "run", "candidate", "ROTATE_CANDIDATE_PREFERRED", T-timedelta(days=1), 2, T-timedelta(days=1), strict.version),)
    assert evaluate(candidates=(candidate(confirmations=2),), history=cooldown, config=strict).stance is RotationStance.NO_ROTATION
    with pytest.raises(ValueError, match="Future"):
        evaluate(Repo(candidate_at=T+timedelta(days=1)))
    future_history=(HistoricalRotationHistory("future", "run", "candidate", "NO_ACTION", T+timedelta(days=1), 2, None, CONFIG.version),)
    with pytest.raises(ValueError, match="Future rotation confirmation"):
        evaluate(history=future_history)
