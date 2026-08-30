from __future__ import annotations

from datetime import datetime

from app.gates.engine import ExchangeCalendar
from app.paper.engine import PaperTradingEngine
from app.signals.engine import SignalOrchestrator
from app.signals.models import RevalidationInput, SignalRequest, SignalType, TradePlan, TriggerObservation
from app.historical.guard import manifest_fingerprint
from .execution_timing import HistoricalExecutionTimingAdapter
from .models import BacktestEvent, BacktestEventType, ExecutionTimingStatus, HistoricalSignalReplayReference, HistoricalPaperReplayReference


class HistoricalSignalPaperReplayService:
    """Point-in-time coordinator over the canonical signal and paper engines.

    This adapter deliberately creates no real portfolio, broker, or order artifact.
    Paper outcomes and lifecycle events remain separate immutable records.
    """
    def __init__(self, repository, calendar: ExchangeCalendar, signal_config, paper_config, *, signal_config_snapshot_id=None, paper_config_snapshot_id=None):
        self.repository, self.calendar = repository, calendar
        self.signal_engine, self.paper_engine = SignalOrchestrator(signal_config, calendar), PaperTradingEngine(paper_config, calendar)
        self.signal_config, self.paper_config = signal_config, paper_config
        self.signal_config_snapshot_id, self.paper_config_snapshot_id = signal_config_snapshot_id, paper_config_snapshot_id
        self.timing_adapter = HistoricalExecutionTimingAdapter(calendar)
        self.last_execution_timing_context = None

    def create_from_rotation(self, *, run, replay_step_number: int, generation_timestamp: datetime,
                             analytical_evaluation_id: str, contextual_gate_evaluation_id: str,
                             historical_rotation_evaluation_id: str, trade_plan: TradePlan):
        if run.signal_config_version != self.signal_config.version or run.paper_config_version != self.paper_config.version:
            raise ValueError("Historical signal/paper configuration version does not match the frozen backtest run.")
        analytical=self.repository.get_historical_analytical_evaluation(analytical_evaluation_id)
        gate_record=self.repository.get_historical_portfolio_gate_evaluation(contextual_gate_evaluation_id)
        rotation=self.repository.get_historical_rotation_evaluation(historical_rotation_evaluation_id)
        if analytical is None or gate_record is None or rotation is None:
            raise ValueError("Historical signal requires frozen analytical, gate, and rotation records.")
        if any(x.evaluation_timestamp > generation_timestamp for x in (analytical, gate_record, rotation)):
            raise ValueError("Future historical decision cannot create a signal.")
        if rotation.decision != "ROTATE_CANDIDATE_PREFERRED" or rotation.preferred_candidate_id != analytical.instrument_id:
            return None
        if gate_record.historical_analytical_evaluation_id != analytical.evaluation_id:
            raise ValueError("Historical signal gate does not match the candidate analytical evaluation.")
        scorecard=self.repository.get_decision_scorecard(analytical.decision_scorecard_id)
        gate=self.repository.get_execution_gate_evaluation(gate_record.resulting_execution_gate_evaluation_id)
        state=self.repository.get_backtest_portfolio_state(rotation.backtest_portfolio_state_id)
        if scorecard is None or gate is None or state is None or state.evaluation_timestamp > generation_timestamp:
            raise ValueError("Historical signal has missing or future frozen dependencies.")
        request=SignalRequest(analytical.instrument_id, f"backtest:{run.backtest_run_id}", state.snapshot.snapshot_id,
            scorecard.strategy_version, run.registry_version, run.scoring_config_version, run.gate_config_version,
            run.rotation_config_version, generation_timestamp, scorecard.id, scorecard.final_score, scorecard.score_status,
            scorecard.data_confidence, gate.id, gate.eligibility.value, rotation.rotation_evaluation_id, rotation.stance,
            SignalType.ROTATION_ENTRY_SETUP, trade_plan, analytical.diagnostic_result_ids, gate.evidence_ids,
            (), 1, False)
        signal, created=self.signal_engine.create(request, generation_timestamp)
        self.repository.save_trade_plan(trade_plan); self.repository.save_signal(signal); self.repository.append_signal_event(created)
        fingerprint=manifest_fingerprint(run=run.fingerprint,analytical=analytical_evaluation_id,gate=contextual_gate_evaluation_id,rotation=historical_rotation_evaluation_id,state=state.backtest_portfolio_state_id,signal=signal.signal_id,config=self.signal_config.version,plan=trade_plan.plan_id)
        snapshot=self.repository.get_signal_config_snapshot(self.signal_config_snapshot_id) if self.signal_config_snapshot_id else None
        reference=HistoricalSignalReplayReference(f"historical-signal-{fingerprint[:24]}",run.backtest_run_id,replay_step_number,generation_timestamp,analytical_evaluation_id,contextual_gate_evaluation_id,historical_rotation_evaluation_id,state.backtest_portfolio_state_id,signal.signal_id,self.signal_config.version,trade_plan.plan_id,"canonical-signal-plan-v1",signal.status.value,None,signal.warnings,fingerprint,self.signal_config_snapshot_id,snapshot.fingerprint if snapshot else None)
        self.repository.save_historical_signal_replay_reference(reference)
        self._backtest_event(run,replay_step_number,generation_timestamp,BacktestEventType.SIGNAL_CREATED,(reference.reference_id,signal.signal_id),signal.status.value)
        return signal,reference

    def replay_signal(self, *, signal_id: str, at: datetime, revalidation: RevalidationInput,
                      triggers: tuple[TriggerObservation, ...], bars=(), run=None, replay_step_number=0, signal_reference=None):
        signal=self.repository.get_signal(signal_id)
        if signal is None: raise ValueError("Historical signal does not exist.")
        if signal.as_of_timestamp > at or revalidation.known_at > at:
            raise ValueError("Future signal input is ineligible.")
        plan=self.repository.get_trade_plan(signal.trade_plan_id) if signal.trade_plan_id else None
        event=self.signal_engine.revalidate(signal, plan, self.repository.list_signal_events(signal_id), revalidation, triggers)
        if event:
            self.repository.append_signal_event(event)
            if run is not None:
                mapping={"TRIGGERED_ANALYTICALLY":BacktestEventType.SIGNAL_TRIGGERED,"INVALIDATED":BacktestEventType.SIGNAL_INVALIDATED,"EXPIRED":BacktestEventType.SIGNAL_EXPIRED,"CANCELLED":BacktestEventType.SIGNAL_CANCELLED}
                if event.resulting_status.value in mapping: self._backtest_event(run,replay_step_number,at,mapping[event.resulting_status.value],(signal_id,signal_reference.reference_id if signal_reference else signal_id),event.reason)
        if event is None or event.resulting_status.value != "TRIGGERED_ANALYTICALLY" or plan is None:
            return event, None, None
        simulation_bars = tuple(bars)
        if run is not None:
            schedule = self.repository.get_replay_schedule(run.replay_schedule_id)
            if schedule is None or schedule.version != run.replay_schedule_version or schedule.exchange_calendar_reference != self.calendar.calendar_id:
                raise ValueError("Historical execution timing requires the frozen replay schedule and calendar.")
            trigger = next((item for condition in plan.trigger_conditions for item in triggers if self.signal_engine._trigger_matches(condition, item, at)), None)
            if trigger is None:
                raise ValueError("Triggered historical signal has no eligible frozen trigger observation.")
            resolved = self.timing_adapter.resolve(run=run, policy=schedule.execution_timing_policy, signal=signal, plan=plan,
                                                   trigger=trigger, bars=tuple(bars), replay_timestamp=at,
                                                   replay_step_number=replay_step_number)
            self.repository.save_historical_trigger_timing_context(resolved.trigger)
            self.repository.save_historical_execution_timing_context(resolved.context)
            self.last_execution_timing_context = resolved.context
            timing_event = BacktestEventType.EXECUTION_TIMING_RESOLVED if resolved.context.status is ExecutionTimingStatus.ELIGIBLE else (BacktestEventType.EXECUTION_INSUFFICIENT if resolved.context.status is ExecutionTimingStatus.INSUFFICIENT_DATA else BacktestEventType.EXECUTION_WAITING)
            self._backtest_event(run, replay_step_number, at, timing_event, (resolved.context.context_id, resolved.trigger.trigger_context_id, *( (resolved.context.selected_fill_bar_id,) if resolved.context.selected_fill_bar_id else () )), resolved.context.eligibility_reason)
            if resolved.context.status is not ExecutionTimingStatus.ELIGIBLE:
                return event, None, None
            simulation_bars = resolved.entry_and_management_bars
        triggered_signal=__import__("dataclasses").replace(signal, status=event.resulting_status)
        trade=self.paper_engine.create(triggered_signal, plan, instrument_id=signal.instrument_id, generated_at=at)
        self.repository.save_paper_trade(trade)
        events, fills, outcome=self.paper_engine.simulate(trade, simulation_bars, at)
        for fill in fills: self.repository.append_paper_fill(fill)
        for paper_event in events: self.repository.append_paper_lifecycle_event(paper_event)
        self.repository.save_paper_outcome(outcome)
        if run is not None:
            fingerprint=manifest_fingerprint(run=run.fingerprint,signal=signal_id,trade=trade.paper_trade_id,outcome=outcome.paper_trade_id,bars=outcome.price_bar_ids,config=self.paper_config.version)
            snapshot=self.repository.get_paper_config_snapshot(self.paper_config_snapshot_id) if self.paper_config_snapshot_id else None
            reference=HistoricalPaperReplayReference(f"historical-paper-{fingerprint[:24]}",run.backtest_run_id,signal_id,trade.paper_trade_id,outcome.paper_trade_id,(replay_step_number,),outcome.price_bar_ids,self.paper_config.version,self.paper_config.cost_model_version,self.paper_config.fill_method.value,self.paper_config.same_bar_policy.value,self.paper_config.gap_policy.value,outcome.state.value,(),fingerprint,self.paper_config_snapshot_id,snapshot.fingerprint if snapshot else None)
            self.repository.save_historical_paper_replay_reference(reference)
            self._backtest_event(run,replay_step_number,at,BacktestEventType.PAPER_TRADE_CREATED,(reference.reference_id,trade.paper_trade_id),outcome.state.value)
            mapping={"OPEN":BacktestEventType.PAPER_TRADE_OPENED,"PARTIALLY_EXITED":BacktestEventType.PAPER_TRADE_PARTIAL_EXIT,"INSUFFICIENT_DATA":BacktestEventType.PAPER_TRADE_INSUFFICIENT}
            self._backtest_event(run,replay_step_number,at,mapping.get(outcome.state.value,BacktestEventType.PAPER_TRADE_CLOSED),(reference.reference_id,trade.paper_trade_id,outcome.paper_trade_id),outcome.state.value)
        return event, trade, outcome

    def _backtest_event(self, run, step, at, kind, references, reason):
        sequence=len(self.repository.list_backtest_events(run.backtest_run_id))+1
        self.repository.append_backtest_event(BacktestEvent(f"{run.backtest_run_id}:event:{sequence:06d}",run.backtest_run_id,kind,at,step,at,tuple(references),reason,{"reason":reason},at))
