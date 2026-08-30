from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from app.historical.guard import manifest_fingerprint
from app.rotation.engine import CapitalRotationEngine
from app.rotation.models import RotationCandidate, RotationEvaluationContext, RotationHoldingState, RotationDecisionState, RotationStance
from .models import BacktestEvent, BacktestEventType, HistoricalRotationEvaluation


class HistoricalCapitalRotationReplayService:
    """Frozen historical adapter for the Phase 6B capital-rotation engine only."""
    def __init__(self, repository): self.repository = repository

    def evaluate(self, *, run, replay_step_number: int, evaluation_timestamp: datetime,
                 backtest_portfolio_state_id: str, candidate_context_ids: tuple[str, ...],
                 holding_context_ids: tuple[str, ...], rotation_history_ids: tuple[str, ...], rotation_config):
        if run.rotation_config_version != rotation_config.version:
            raise ValueError("Frozen backtest run rotation configuration does not match.")
        state = self.repository.get_backtest_portfolio_state(backtest_portfolio_state_id)
        if state is None or state.evaluation_timestamp > evaluation_timestamp:
            raise ValueError("Future or missing frozen portfolio state is ineligible.")
        candidates = tuple(self.repository.get_historical_rotation_candidate_context(x) for x in candidate_context_ids)
        holdings = tuple(self.repository.get_historical_holding_gate_context(x) for x in holding_context_ids)
        history = tuple(self.repository.get_historical_rotation_history(x) for x in rotation_history_ids)
        if any(x is None for x in candidates + holdings + history):
            raise ValueError("Frozen rotation context reference is missing.")
        if any(x.occurred_at > evaluation_timestamp or (x.cooldown_anchor and x.cooldown_anchor > evaluation_timestamp) for x in history):
            raise ValueError("Future rotation confirmation or cooldown history is ineligible.")
        for candidate_context in candidates:
            gate_record=self.repository.get_historical_portfolio_gate_evaluation(candidate_context.contextual_gate_evaluation_id)
            if gate_record is None or gate_record.backtest_portfolio_state_id != backtest_portfolio_state_id:
                raise ValueError("Candidate contextual gate does not match the frozen portfolio state.")
        result = self.evaluate_frozen(run=run, evaluation_timestamp=evaluation_timestamp, state=state,
            candidate_contexts=candidates, holding_contexts=holdings, history=history, rotation_config=rotation_config)
        fingerprint = manifest_fingerprint(run=run.fingerprint, state=backtest_portfolio_state_id,
            candidates=candidate_context_ids, holdings=holding_context_ids, history=rotation_history_ids,
            config=rotation_config.version)
        record = HistoricalRotationEvaluation(f"historical-rotation-{fingerprint[:24]}", run.backtest_run_id,
            replay_step_number, evaluation_timestamp, backtest_portfolio_state_id, tuple(candidate_context_ids),
            tuple(holding_context_ids), tuple(rotation_history_ids), rotation_config.version, result.evaluation_id,
            tuple(x.candidate.instrument_id for x in result.ranked_candidates), result.weakest_holding_id,
            result.decision.value, result.stance.value, result.preferred_candidate_id, result.warnings, fingerprint)
        self.repository.save_historical_rotation_evaluation(record)
        common_refs=(record.rotation_evaluation_id, backtest_portfolio_state_id, *candidate_context_ids, *holding_context_ids)
        sequence=len(self.repository.list_backtest_events(run.backtest_run_id))+1
        self.repository.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:{sequence:06d}", run.backtest_run_id,
            BacktestEventType.ROTATION_EVALUATED, evaluation_timestamp, replay_step_number, evaluation_timestamp,
            common_refs, "Historical rotation evaluated", {"weakest_holding_id": result.weakest_holding_id, "rotation_source_id": result.evaluation_id}, evaluation_timestamp))
        if result.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
            event_type = BacktestEventType.ROTATION_APPROVED_ANALYTICALLY
        elif result.decision is RotationDecisionState.CASH_PREFERRED:
            event_type = BacktestEventType.CASH_SELECTED
        else:
            event_type = BacktestEventType.ROTATION_REJECTED
        sequence=len(self.repository.list_backtest_events(run.backtest_run_id))+1
        self.repository.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:{sequence:06d}", run.backtest_run_id,
            event_type, evaluation_timestamp, replay_step_number, evaluation_timestamp,
            common_refs,
            result.decision.value, {"weakest_holding_id": result.weakest_holding_id, "rotation_source_id": result.evaluation_id}, evaluation_timestamp))
        return record, result

    def evaluate_frozen(self, *, run, evaluation_timestamp, state, candidate_contexts, holding_contexts, history, rotation_config):
        if any(x.occurred_at > evaluation_timestamp or (x.cooldown_anchor and x.cooldown_anchor > evaluation_timestamp) for x in history):
            raise ValueError("Future rotation confirmation or cooldown history is ineligible.")
        candidates = tuple(self._candidate(x, evaluation_timestamp) for x in candidate_contexts)
        holdings = tuple(self._holding(x, evaluation_timestamp, state) for x in holding_contexts)
        last_rotation = max((x.cooldown_anchor or x.occurred_at for x in history if x.occurred_at <= evaluation_timestamp), default=None)
        context = RotationEvaluationContext(state.snapshot.snapshot_id, run.strategy_version, run.registry_version,
            run.scoring_config_version, run.gate_config_version, evaluation_timestamp, holdings,
            state.snapshot.cash.amount, candidates, rotation_config.friction_model_version, last_rotation)
        return CapitalRotationEngine(rotation_config).evaluate(context, evaluation_timestamp)

    def _candidate(self, context, at):
        evaluation=self.repository.get_historical_analytical_evaluation(context.historical_analytical_evaluation_id)
        gates=self.repository.get_historical_portfolio_gate_evaluation(context.contextual_gate_evaluation_id)
        if evaluation is None or gates is None or evaluation.evaluation_timestamp > at or context.known_at > at:
            raise ValueError("Future or missing candidate analytical/gate context is ineligible.")
        scorecard=self.repository.get_decision_scorecard(evaluation.decision_scorecard_id)
        gate=self.repository.get_execution_gate_evaluation(gates.resulting_execution_gate_evaluation_id)
        if (scorecard is None or gate is None or gates.evaluation_timestamp > at or
                gates.historical_analytical_evaluation_id != evaluation.evaluation_id or
                gates.backtest_portfolio_state_id is None):
            raise ValueError("Candidate scorecard or contextual gate is missing or future.")
        return RotationCandidate(evaluation.instrument_id, evaluation.evaluation_timestamp, context.known_at,
            scorecard.id, scorecard.final_score, scorecard.score_status, scorecard.data_confidence, gate.id,
            gate.eligibility.value, context.sector, context.sector_supportive, None, None, None,
            Decimal(context.structural_risk_reward) if context.structural_risk_reward else None,
            context.entry_valid, context.stop_valid, context.invalidation_valid, None, context.warnings,
            False, None, gate.eligibility.value == "EXECUTABLE", False,
            Decimal(context.modeled_switching_friction) if context.modeled_switching_friction else None,
            Decimal(context.expected_incremental_benefit) if context.expected_incremental_benefit else None,
            context.confirmation_count, ())

    def _holding(self, context, at, state):
        evaluation=self.repository.get_historical_analytical_evaluation(context.historical_analytical_evaluation_id) if context.historical_analytical_evaluation_id else None
        if evaluation is not None and evaluation.evaluation_timestamp > at: raise ValueError("Future holding analytical context is ineligible.")
        holding=next((x for x in state.snapshot.holdings if x.instrument_id == context.instrument_id), None)
        return RotationHoldingState(context.instrument_id, evaluation.evaluation_timestamp if evaluation else at,
            evaluation.evaluation_timestamp if evaluation else at, Decimal(context.raw_score) if context.raw_score else None,
            context.data_confidence, None, context.sector, None, None, None, None,
            Decimal(context.forward_risk_reward) if context.forward_risk_reward else None,
            Decimal(context.forward_risk_reward) if context.forward_risk_reward else None,
            None, None, None, Decimal(context.gate_2_adjustment) if context.gate_2_adjustment else Decimal("0"),
            holding.market_value if holding else None, holding.unrealized_pnl if holding else None,
            holding.analytics.structural_stop if holding and holding.analytics else None, context.warnings, ())
