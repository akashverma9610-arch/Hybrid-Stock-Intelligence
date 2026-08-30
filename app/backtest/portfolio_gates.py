from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from app.gates.engine import ActionContext, ExecutionGateConfig, ExecutionGateEngine, GateInput, PortfolioExposure
from app.historical.guard import manifest_fingerprint
from .models import BacktestEvent, BacktestEventType, HistoricalPortfolioGateEvaluation


class HistoricalPortfolioGateReplayService:
    """Immutable adapter from frozen replay artifacts to the existing six-gate engine."""
    def __init__(self, repository, calendar): self.repository,self.calendar=repository,calendar

    def evaluate(self, *, run, replay_step_number, evaluation_timestamp, historical_analytical_evaluation_id,
                 original_execution_gate_evaluation_id, backtest_portfolio_state_id, holding_context_ids,
                 gate_config: ExecutionGateConfig, candidate_sector: str | None = None,
                 candidate_risk_amount: Decimal | None = None, candidate_allocation: Decimal | None = None,
                 expected_incremental_return: Decimal | None = None, modeled_switching_friction: Decimal | None = None):
        candidate=self.repository.get_historical_analytical_evaluation(historical_analytical_evaluation_id)
        original=self.repository.get_execution_gate_evaluation(original_execution_gate_evaluation_id)
        state=self.repository.get_backtest_portfolio_state(backtest_portfolio_state_id)
        if candidate is None or original is None or state is None: raise ValueError("Portfolio-context gates require frozen candidate, original gate, and portfolio state.")
        if candidate.evaluation_timestamp>evaluation_timestamp or state.evaluation_timestamp>evaluation_timestamp: raise ValueError("Future candidate or portfolio state is ineligible.")
        if run.gate_config_version != gate_config.version: raise ValueError("Frozen backtest run gate configuration does not match.")
        contexts=tuple(self.repository.get_historical_holding_gate_context(x) for x in holding_context_ids)
        if any(x is None for x in contexts): raise ValueError("Frozen holding context is missing.")
        for context in contexts:
            if context.historical_analytical_evaluation_id:
                evaluation=self.repository.get_historical_analytical_evaluation(context.historical_analytical_evaluation_id)
                if evaluation is None or evaluation.evaluation_timestamp>evaluation_timestamp: raise ValueError("Future or missing holding analytics are ineligible.")
        result=self.evaluate_frozen(run=run, evaluation_timestamp=evaluation_timestamp, candidate=candidate,
            original=original, state=state, contexts=contexts, gate_config=gate_config,
            candidate_sector=candidate_sector, candidate_risk_amount=candidate_risk_amount,
            candidate_allocation=candidate_allocation, expected_incremental_return=expected_incremental_return,
            modeled_switching_friction=modeled_switching_friction)
        fingerprint=manifest_fingerprint(run=run.fingerprint,candidate=historical_analytical_evaluation_id,
            original_gate=original_execution_gate_evaluation_id,state=backtest_portfolio_state_id,
            contexts=holding_context_ids,config=gate_config.version,sector=candidate_sector,
            candidate_risk=str(candidate_risk_amount),candidate_allocation=str(candidate_allocation),
            expected_return=str(expected_incremental_return),switching_friction=str(modeled_switching_friction))
        # Existing storage requires a unique ID and exact persisted scorecard.  The ID
        # incorporates every frozen contextual input, rather than an evaluator's generic ID.
        result=replace(result,id=f"{run.backtest_run_id}|portfolio-context|{fingerprint[:24]}")
        self.repository.save_execution_gate_evaluation(result)
        status="INSUFFICIENT_DATA" if result.insufficient_gate_ids else "COMPLETED"
        record=HistoricalPortfolioGateEvaluation(f"portfolio-gates-{fingerprint[:24]}",run.backtest_run_id,replay_step_number,evaluation_timestamp,historical_analytical_evaluation_id,original_execution_gate_evaluation_id,backtest_portfolio_state_id,gate_config.version,tuple(holding_context_ids),result.id,status,result.warnings,fingerprint,candidate_sector,
            str(candidate_risk_amount) if candidate_risk_amount is not None else None,
            str(candidate_allocation) if candidate_allocation is not None else None,
            str(expected_incremental_return) if expected_incremental_return is not None else None,
            str(modeled_switching_friction) if modeled_switching_friction is not None else None)
        self.repository.save_historical_portfolio_gate_evaluation(record)
        event_type=BacktestEventType.PORTFOLIO_GATES_INSUFFICIENT if status=="INSUFFICIENT_DATA" else BacktestEventType.PORTFOLIO_GATES_EVALUATED
        sequence=len(self.repository.list_backtest_events(run.backtest_run_id))+1
        self.repository.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:{sequence:06d}",run.backtest_run_id,event_type,evaluation_timestamp,replay_step_number,evaluation_timestamp,(record.portfolio_gate_evaluation_id,backtest_portfolio_state_id,historical_analytical_evaluation_id),status,{"original_gate_id":original_execution_gate_evaluation_id},evaluation_timestamp))
        return record,result

    def evaluate_frozen(self, *, run, evaluation_timestamp, candidate, original, state, contexts,
                        gate_config, candidate_sector=None, candidate_risk_amount=None,
                        candidate_allocation=None, expected_incremental_return=None,
                        modeled_switching_friction=None):
        """Pure canonical gate evaluation from already-resolved immutable artifacts."""
        scorecard=self.repository.get_decision_scorecard(candidate.decision_scorecard_id)
        if scorecard is None: raise ValueError("Candidate historical evaluation requires its frozen scorecard.")
        incumbent=next((x for x in contexts if x.comparison_score is not None),None)
        comparison=Decimal(incumbent.comparison_score) if incumbent else None
        exposure=self._exposure(state,candidate_sector,candidate_risk_amount,candidate_allocation)
        inputs=GateInput(scorecard.id,scorecard.final_score,state.snapshot.snapshot_id,evaluation_timestamp,comparison_score=comparison,
            expected_incremental_return=expected_incremental_return,modeled_switching_friction=modeled_switching_friction,
            exposure=exposure,evidence_ids=original.evidence_ids,diagnostic_ids=original.diagnostic_ids)
        return ExecutionGateEngine(gate_config,self.calendar).evaluate(instrument_id=candidate.instrument_id,
            strategy_version=scorecard.strategy_version,registry_version=run.registry_version,
            scoring_configuration_version=run.scoring_config_version,action_context=ActionContext.ROTATE_IN,
            as_of_timestamp=evaluation_timestamp,evaluated_at=evaluation_timestamp,inputs=inputs)

    @staticmethod
    def _exposure(state, candidate_sector, candidate_risk, candidate_allocation):
        snapshot=state.snapshot; equity=snapshot.portfolio_equity
        if equity is None or candidate_risk is None or candidate_allocation is None: return None
        existing=(snapshot.risk.total_heat or Decimal("0"))*equity if snapshot.risk.total_heat is not None else None
        # A known candidate sector with no current holdings has a genuine zero
        # sector allocation; it is not missing risk data.  Unknown/missing
        # candidate sector remains explicitly grouped under UNKNOWN.
        sector_fraction=snapshot.exposure.sector_exposure.get(candidate_sector or "UNKNOWN", Decimal("0"))
        sector=sector_fraction * equity if sector_fraction is not None else None
        return PortfolioExposure(equity,existing,candidate_risk,candidate_allocation,sector,tuple(state.price_reference_ids))
