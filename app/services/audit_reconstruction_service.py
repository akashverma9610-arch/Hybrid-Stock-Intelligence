from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Callable

from app.domain.models import AnalyticalDecisionReconstruction, StrategyVersionReference
from app.storage.governance_repository import StrategyGovernanceRepository
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import build_scorecard
from app.backtest.engine import ExchangeCalendarProtocol, ReplayClock, backtest_run_fingerprint, validate_event_sequence
from app.backtest.models import BacktestAuditReconstruction
from app.backtest.portfolio import BacktestFrozenPriceMark, BacktestPortfolioReplayEngine
from app.portfolio.models import PriceReference
from app.backtest.walk_forward import OOSStartingCapitalMethodology, WalkForwardWindowResultStatus
from app.backtest.oos_aggregation import WalkForwardAggregationService
from app.self_improvement.attribution import SelfImprovementAttributionService
from app.self_improvement.hypotheses import SelfImprovementHypothesisService
from app.self_improvement.models import hypothesis_review_fingerprint, future_oos_assignment_fingerprint, future_oos_execution_fingerprint
from app.self_improvement.experiment_bridge import SelfImprovementExperimentBridge
from app.self_improvement.oos_evidence import FutureOOSEvidencePackagingService
from app.backtest.experiments import ControlledCandidateExperimentService, ExperimentStatus
from app.historical.guard import manifest_fingerprint
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.policy import PreBreakoutPolicyDraft
from app.research.handoff import BrainResearchHandoff


class AuditReconstructionError(ValueError):
    pass


class AuditReconstructionService:
    """Rebuilds a decision from immutable records without recalculating any analysis."""

    def __init__(self, repository: StrategyGovernanceRepository) -> None:
        self._repository = repository

    def reconstruct(
        self, *, strategy_version: StrategyVersionReference, snapshot_id: str,
        scorecard_id: str | None = None,
    ) -> AnalyticalDecisionReconstruction:
        if self._repository.get_strategy_definition(strategy_version) is None:
            raise AuditReconstructionError("Strategy version does not exist.")
        snapshot = self._repository.get_snapshot(snapshot_id)
        if snapshot is None:
            raise AuditReconstructionError("As-of snapshot does not exist.")
        scorecard = self._repository.get_scorecard(scorecard_id) if scorecard_id else None
        if scorecard and (scorecard.strategy_version != strategy_version or scorecard.as_of_timestamp != snapshot.as_of_timestamp):
            raise AuditReconstructionError("Scorecard does not match the requested strategy version and snapshot time.")

        diagnostics = self._repository.list_diagnostic_results(strategy_version, snapshot.as_of_timestamp)
        gates = self._repository.list_gate_decisions(strategy_version, snapshot.as_of_timestamp)
        evidence_ids = {
            evidence_id for result in diagnostics for evidence_id in result.evidence_ids
        } | {
            evidence_id for gate in gates for evidence_id in gate.evidence_ids
        }
        if scorecard:
            evidence_ids.update(
                evidence_id for component in scorecard.components for evidence_id in component.evidence_ids
            )
        evidence_ids = sorted(evidence_ids)
        evidence = self._repository.get_evidence(tuple(evidence_ids))
        if {item.id for item in evidence} != set(evidence_ids):
            raise AuditReconstructionError("A referenced evidence record is missing.")

        fingerprint_payload = {
            "strategy_version": [strategy_version.strategy_id, strategy_version.version],
            "snapshot_id": snapshot.id,
            "evidence_ids": sorted(item.id for item in evidence),
            "diagnostic_ids": sorted(item.id for item in diagnostics),
            "scorecard_id": scorecard.id if scorecard else None,
            "gate_ids": sorted(item.id for item in gates),
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        reconstruction = AnalyticalDecisionReconstruction(
            id=f"decision-{fingerprint[:16]}", strategy_version=strategy_version,
            snapshot_id=snapshot.id, evidence=tuple(sorted(evidence, key=lambda item: item.id)),
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.id)), scorecard=scorecard,
            gate_decisions=tuple(sorted(gates, key=lambda item: item.id)), fingerprint=fingerprint,
        )
        self._repository.append_audit_event(
            "decision.reconstructed", snapshot.as_of_timestamp,
            json.dumps({"decision_id": reconstruction.id, "snapshot_id": snapshot.id}, sort_keys=True),
        )
        return reconstruction

    def reconstruct_decision_scorecard(self, scorecard_id: str):
        """Recompute from exact persisted diagnostics without changing historical data."""
        stored=self._repository.get_decision_scorecard(scorecard_id)
        if stored is None: raise AuditReconstructionError("Decision scorecard does not exist.")
        diagnostics=self._repository.list_diagnostic_results(stored.strategy_version,stored.as_of_timestamp)
        wrapped=tuple(EvaluatedDiagnostic(x,int(x.rule_id),DIAGNOSTIC_REGISTRY_VERSION,EvaluationEligibility.ELIGIBLE,(),()) for x in diagnostics)
        rebuilt=build_scorecard(instrument_id=stored.instrument_id,strategy_version=stored.strategy_version,registry_version=stored.registry_version,as_of_timestamp=stored.as_of_timestamp,evaluated_at=stored.evaluated_at,diagnostics=wrapped,configuration_version=stored.configuration_version)
        if rebuilt.components!=stored.components or rebuilt.final_score!=stored.final_score or rebuilt.score_status!=stored.score_status: raise AuditReconstructionError("Decision scorecard reconstruction mismatch; stored history was not changed.")
        return stored

    def reconstruct_execution_gate_evaluation(self, evaluation_id: str):
        """Recover the immutable eligibility decision and its scorecard dependency."""
        evaluation = self._repository.get_execution_gate_evaluation(evaluation_id)
        if evaluation is None:
            raise AuditReconstructionError("Execution gate evaluation does not exist.")
        scorecard = self.reconstruct_decision_scorecard(evaluation.scorecard_id)
        if scorecard.instrument_id != evaluation.instrument_id or scorecard.strategy_version != evaluation.strategy_version or scorecard.as_of_timestamp != evaluation.as_of_timestamp:
            raise AuditReconstructionError("Execution gate evaluation has an invalid scorecard dependency.")
        if len(evaluation.decisions) != 6:
            raise AuditReconstructionError("Historical execution gate evaluation does not contain six decisions.")
        self._repository.append_audit_event("execution_gate_evaluation.reconstructed", evaluation.as_of_timestamp,
            json.dumps({"evaluation_id": evaluation.id, "scorecard_id": evaluation.scorecard_id}, sort_keys=True))
        return evaluation

    def reconstruct_portfolio_snapshot(self, snapshot_id: str):
        """Retrieve the immutable historical portfolio state and its eligible ledger window."""
        snapshot = self._repository.get_portfolio_snapshot(snapshot_id)
        if snapshot is None:
            raise AuditReconstructionError("Portfolio snapshot does not exist.")
        if self._repository.get_portfolio(snapshot.portfolio_id) is None:
            raise AuditReconstructionError("Portfolio snapshot references a missing portfolio.")
        transactions = self._repository.list_portfolio_transactions_as_of(snapshot.portfolio_id, snapshot.source_transaction_cutoff)
        actions = self._repository.list_corporate_actions_as_of(snapshot.portfolio_id, snapshot.source_transaction_cutoff)
        self._repository.append_audit_event("portfolio_snapshot.reconstructed", snapshot.as_of_timestamp,
            json.dumps({"snapshot_id": snapshot.id if hasattr(snapshot, "id") else snapshot.snapshot_id,
                        "transaction_ids": [x.transaction_id for x in transactions], "corporate_action_ids": [x.action_id for x in actions]}, sort_keys=True))
        return snapshot

    def reconstruct_portfolio_rotation_evaluation(self, evaluation_id: str):
        """Recover the immutable snapshot, as-of comparisons, ranking, and analytical stance."""
        evaluation = self._repository.get_portfolio_rotation_evaluation(evaluation_id)
        if evaluation is None:
            raise AuditReconstructionError("Portfolio rotation evaluation does not exist.")
        snapshot = self.reconstruct_portfolio_snapshot(evaluation.context.portfolio_snapshot_id)
        if snapshot.as_of_timestamp != evaluation.context.as_of_timestamp:
            raise AuditReconstructionError("Rotation evaluation does not match its historical portfolio snapshot.")
        self._repository.append_audit_event("portfolio_rotation_evaluation.reconstructed", evaluation.context.as_of_timestamp,
            json.dumps({"evaluation_id": evaluation.evaluation_id, "snapshot_id": snapshot.snapshot_id,
                        "candidate_ids": [x.candidate.instrument_id for x in evaluation.ranked_candidates]}, sort_keys=True))
        return evaluation

    def reconstruct_signal(self, signal_id: str):
        """Recover original analytical setup plus append-only lifecycle evidence without rewriting it."""
        signal = self._repository.get_signal(signal_id)
        if signal is None:
            raise AuditReconstructionError("Signal does not exist.")
        plan = self._repository.get_trade_plan(signal.trade_plan_id) if signal.trade_plan_id else None
        events = self._repository.list_signal_events(signal_id)
        self._repository.append_audit_event("signal.reconstructed", signal.as_of_timestamp,
            json.dumps({"signal_id": signal.signal_id, "trade_plan_id": signal.trade_plan_id,
                        "event_ids": [x.event_id for x in events]}, sort_keys=True))
        return signal, plan, events

    def reconstruct_performance_report(self, report_id: str):
        report=self._repository.get_performance_report(report_id)
        if report is None: raise AuditReconstructionError("Performance report does not exist.")
        dataset=self._repository.get_performance_dataset_for_report(report_id)
        if dataset is None or tuple(report.trade_ids)!=tuple(dataset.paper_trade_ids): raise AuditReconstructionError("Performance report frozen dataset mismatch.")
        run_note=next((note for note in report.methodology_notes if note.startswith("BACKTEST_RUN:")), None)
        if run_note:
            run=self._repository.get_backtest_run(run_note.split(":",1)[1])
            if run is None or run.status.value != "COMPLETED" or report.config_version != dataset.evaluation_version:
                raise AuditReconstructionError("Historical performance report frozen run or configuration mismatch.")
            for trade_id in dataset.paper_trade_ids:
                trade=self._repository.get_paper_trade(trade_id); outcome=self._repository.get_paper_outcome(trade_id)
                if trade is None or outcome is None or trade.paper_trade_id != trade_id:
                    raise AuditReconstructionError("Historical performance report has a missing frozen paper artifact.")
        runs=self._repository.list_benchmark_runs(report_id); comparisons=self._repository.list_benchmark_comparisons(report_id)
        self._repository.append_audit_event("performance_report.reconstructed",report.end,json.dumps({"report_id":report_id,"dataset_id":dataset.dataset_id,"runs":len(runs),"comparisons":len(comparisons)},sort_keys=True))
        return report,dataset,runs,comparisons

    def reconstruct_backtest_run(self, backtest_run_id: str, calendar: ExchangeCalendarProtocol) -> BacktestAuditReconstruction:
        """Rebuild the V1 orchestration history without invoking any strategy component."""
        run = self._repository.get_backtest_run(backtest_run_id)
        if run is None:
            raise AuditReconstructionError("Backtest run does not exist.")
        manifest = self._repository.get_historical_manifest(run.dataset_manifest_id)
        schedule = self._repository.get_replay_schedule(run.replay_schedule_id)
        policy = self._repository.get_backtest_data_gap_policy(run.data_gap_policy_id)
        if manifest is None or schedule is None or policy is None:
            raise AuditReconstructionError("Backtest run has missing immutable configuration dependencies.")
        if (manifest.dataset_version != run.dataset_manifest_version or manifest.fingerprint != run.dataset_fingerprint or
                schedule.version != run.replay_schedule_version or policy.version != run.data_gap_policy_version):
            raise AuditReconstructionError("Backtest run metadata does not match its persisted dependencies.")
        if run.fingerprint != backtest_run_fingerprint(run):
            raise AuditReconstructionError("Backtest run fingerprint does not match frozen inputs.")
        partition = self._repository.get_historical_partition(run.partition_id) if run.partition_id else None
        if run.partition_id and (partition is None or partition.dataset_id != run.dataset_manifest_id):
            raise AuditReconstructionError("Backtest run partition dependency is invalid.")
        timestamps = ReplayClock(schedule, calendar).timestamps(
            start=partition.start if partition else run.evaluation_start,
            end=partition.end if partition else run.evaluation_end,
        )
        steps = self._repository.list_backtest_replay_steps(backtest_run_id)
        events = self._repository.list_backtest_events(backtest_run_id)
        try:
            final_status = validate_event_sequence(events, run.status)
        except ValueError as error:
            raise AuditReconstructionError(f"Backtest event ordering/lifecycle mismatch: {error}") from error
        for expected_number, step in enumerate(steps, start=1):
            if step.backtest_run_id != backtest_run_id or step.step_number != expected_number:
                raise AuditReconstructionError("Backtest replay steps are not contiguous append-only history.")
            if expected_number > len(timestamps) or step.evaluation_timestamp != timestamps[expected_number - 1]:
                raise AuditReconstructionError("Backtest replay step does not match the frozen replay clock.")
        expected_times = set(timestamps)
        if any(event.evaluation_timestamp not in expected_times for event in events) and timestamps:
            raise AuditReconstructionError("Backtest event does not match a frozen replay-clock timestamp.")
        if final_status.name == "COMPLETED" and len(steps) != len(timestamps):
            raise AuditReconstructionError("Completed backtest is missing replay steps.")
        self._repository.append_audit_event(
            "backtest_run.reconstructed", run.evaluation_end,
            json.dumps({"backtest_run_id": backtest_run_id, "steps": len(steps), "events": len(events),
                        "final_status": final_status.value}, sort_keys=True),
        )
        return BacktestAuditReconstruction(run, schedule, timestamps, steps, events, final_status)

    def reconstruct_historical_analytical_evaluation(self, evaluation_id: str):
        """Explain a frozen replay result from persisted references without recalculating it."""
        evaluation = self._repository.get_historical_analytical_evaluation(evaluation_id)
        if evaluation is None:
            raise AuditReconstructionError("Historical analytical evaluation does not exist.")
        run = self._repository.get_backtest_run(evaluation.backtest_run_id)
        snapshot_reference = self._repository.get_historical_analytical_snapshot(evaluation.historical_snapshot_id)
        if run is None or snapshot_reference is None:
            raise AuditReconstructionError("Historical analytical evaluation has missing run or snapshot history.")
        if (snapshot_reference.backtest_run_id != run.backtest_run_id or
                snapshot_reference.replay_step_number != evaluation.replay_step_number or
                snapshot_reference.evaluation_timestamp != evaluation.evaluation_timestamp or
                snapshot_reference.instrument_id != evaluation.instrument_id):
            raise AuditReconstructionError("Historical analytical snapshot reference mismatch.")
        source_snapshot = self._repository.get_snapshot(snapshot_reference.source_snapshot_id)
        if source_snapshot is None or tuple(item.id for item in source_snapshot.observations) != snapshot_reference.selected_input_ids:
            raise AuditReconstructionError("Historical analytical snapshot inputs no longer match frozen provenance.")
        diagnostics = self._repository.list_diagnostic_results(
            StrategyVersionReference(*evaluation.strategy_version.split(":", 1)), evaluation.evaluation_timestamp
        )
        diagnostic_ids = {item.id for item in diagnostics}
        if not set(evaluation.diagnostic_result_ids).issubset(diagnostic_ids):
            raise AuditReconstructionError("Historical analytical diagnostic references are missing.")
        scorecard = self._repository.get_decision_scorecard(evaluation.decision_scorecard_id)
        gates = self._repository.get_execution_gate_evaluation(evaluation.execution_gate_evaluation_id)
        if scorecard is None or gates is None or scorecard.instrument_id != evaluation.instrument_id or gates.instrument_id != evaluation.instrument_id:
            raise AuditReconstructionError("Historical scorecard or gate evaluation reference mismatch.")
        if scorecard.data_confidence != evaluation.data_confidence or gates.scorecard_id != scorecard.id:
            raise AuditReconstructionError("Historical analytical values do not match persisted references.")
        self._repository.append_audit_event("historical_analytical_evaluation.reconstructed", evaluation.evaluation_timestamp,
            json.dumps({"evaluation_id": evaluation_id, "snapshot_id": snapshot_reference.historical_snapshot_id,
                        "diagnostic_count": len(evaluation.diagnostic_result_ids), "scorecard_id": scorecard.id,
                        "gate_evaluation_id": gates.id}, sort_keys=True))
        return evaluation, run, snapshot_reference, tuple(x for x in diagnostics if x.id in evaluation.diagnostic_result_ids), scorecard, gates

    def reconstruct_backtest_portfolio_state(self, state_id: str, calendar: ExchangeCalendarProtocol):
        state = self._repository.get_backtest_portfolio_state(state_id)
        if state is None: raise AuditReconstructionError("Backtest portfolio state does not exist.")
        if self._repository.get_backtest_run(state.backtest_run_id) is None: raise AuditReconstructionError("Backtest portfolio state references a missing run.")
        all_events = self._repository.list_backtest_portfolio_ledger_events(state.backtest_run_id)
        event_by_id = {x.ledger_event_id: x for x in all_events}
        if set(state.source_ledger_ids) - set(event_by_id): raise AuditReconstructionError("Frozen backtest portfolio ledger reference is missing.")
        events = tuple(event_by_id[x] for x in state.source_ledger_ids)
        prices = tuple(PriceReference(x.observation_id,x.instrument_id,x.price,x.observed_at,x.known_at) for x in state.frozen_price_marks)
        rebuilt = BacktestPortfolioReplayEngine(calendar).reconstruct(run_id=state.backtest_run_id,step_number=state.replay_step_number,at=state.evaluation_timestamp,starting_capital=state.starting_capital,events=events,prices=prices,initialization_policy=state.initialization_policy)
        if rebuilt.snapshot != state.snapshot or rebuilt.source_ledger_ids != state.source_ledger_ids or rebuilt.price_reference_ids != state.price_reference_ids:
            raise AuditReconstructionError("Backtest portfolio reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("backtest_portfolio_state.reconstructed", state.evaluation_timestamp, json.dumps({"state_id":state_id,"ledger_ids":list(state.source_ledger_ids),"price_ids":list(state.price_reference_ids)},sort_keys=True))
        return state

    def reconstruct_historical_portfolio_gate_evaluation(self, evaluation_id: str, gate_config, calendar):
        """Validate the immutable contextual-gate dependency chain without consulting newer artifacts."""
        record=self._repository.get_historical_portfolio_gate_evaluation(evaluation_id)
        if record is None: raise AuditReconstructionError("Historical portfolio gate evaluation does not exist.")
        run=self._repository.get_backtest_run(record.backtest_run_id)
        candidate=self._repository.get_historical_analytical_evaluation(record.historical_analytical_evaluation_id)
        original=self._repository.get_execution_gate_evaluation(record.original_execution_gate_evaluation_id)
        state=self._repository.get_backtest_portfolio_state(record.backtest_portfolio_state_id)
        result=self._repository.get_execution_gate_evaluation(record.resulting_execution_gate_evaluation_id)
        if None in (run,candidate,original,state,result): raise AuditReconstructionError("Portfolio-context gate evaluation has a missing frozen dependency.")
        if (candidate.evaluation_timestamp>record.evaluation_timestamp or state.evaluation_timestamp>record.evaluation_timestamp or
            run.gate_config_version!=record.gate_config_version or gate_config.version!=record.gate_config_version):
            raise AuditReconstructionError("Portfolio-context gate evaluation violates as-of or frozen-config integrity.")
        contexts=tuple(self._repository.get_historical_holding_gate_context(x) for x in record.holding_context_ids)
        if any(x is None for x in contexts): raise AuditReconstructionError("Portfolio-context gate evaluation has a missing holding context.")
        for context in contexts:
            if context.historical_analytical_evaluation_id:
                holding=self._repository.get_historical_analytical_evaluation(context.historical_analytical_evaluation_id)
                if holding is None or holding.evaluation_timestamp>record.evaluation_timestamp: raise AuditReconstructionError("Portfolio-context gate holding analytics are invalid as-of context.")
        if result.gate_configuration_version!=record.gate_config_version or result.as_of_timestamp!=record.evaluation_timestamp:
            raise AuditReconstructionError("Persisted contextual gate output does not match frozen metadata.")
        from app.backtest.portfolio_gates import HistoricalPortfolioGateReplayService
        # The gate configuration itself is frozen by version.  Reconstruct with the same
        # canonical engine path, never through a current/latest configuration lookup.
        replay = HistoricalPortfolioGateReplayService(self._repository, calendar)
        rebuilt = replay.evaluate_frozen(run=run, evaluation_timestamp=record.evaluation_timestamp,
            candidate=candidate, original=original, state=state, contexts=contexts, gate_config=gate_config,
            candidate_sector=record.candidate_sector,
            candidate_risk_amount=__import__("decimal").Decimal(record.candidate_risk_amount) if record.candidate_risk_amount else None,
            candidate_allocation=__import__("decimal").Decimal(record.candidate_allocation) if record.candidate_allocation else None,
            expected_incremental_return=__import__("decimal").Decimal(record.expected_incremental_return) if record.expected_incremental_return else None,
            modeled_switching_friction=__import__("decimal").Decimal(record.modeled_switching_friction) if record.modeled_switching_friction else None)
        rebuilt = __import__("dataclasses").replace(rebuilt, id=result.id)
        if rebuilt != result:
            raise AuditReconstructionError("Portfolio-context gate reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("historical_portfolio_gate_evaluation.reconstructed",record.evaluation_timestamp,json.dumps({"evaluation_id":evaluation_id,"candidate":candidate.evaluation_id,"state":state.backtest_portfolio_state_id,"contexts":list(record.holding_context_ids)},sort_keys=True))
        return record,run,candidate,original,state,contexts,result

    def reconstruct_historical_rotation_evaluation(self, evaluation_id: str, rotation_config):
        record=self._repository.get_historical_rotation_evaluation(evaluation_id)
        if record is None: raise AuditReconstructionError("Historical rotation evaluation does not exist.")
        run=self._repository.get_backtest_run(record.backtest_run_id)
        state=self._repository.get_backtest_portfolio_state(record.backtest_portfolio_state_id)
        if run is None or state is None or run.rotation_config_version != record.rotation_config_version or rotation_config.version != record.rotation_config_version:
            raise AuditReconstructionError("Historical rotation has a missing or mismatched frozen run, state, or configuration.")
        if state.evaluation_timestamp > record.evaluation_timestamp: raise AuditReconstructionError("Historical rotation portfolio state is future data.")
        candidates=tuple(self._repository.get_historical_rotation_candidate_context(x) for x in record.candidate_context_ids)
        holdings=tuple(self._repository.get_historical_holding_gate_context(x) for x in record.holding_context_ids)
        history=tuple(self._repository.get_historical_rotation_history(x) for x in record.rotation_history_ids)
        if any(x is None for x in candidates + holdings + history): raise AuditReconstructionError("Historical rotation has a missing frozen context reference.")
        from app.backtest.rotation import HistoricalCapitalRotationReplayService
        try:
            rebuilt=HistoricalCapitalRotationReplayService(self._repository).evaluate_frozen(run=run,evaluation_timestamp=record.evaluation_timestamp,state=state,candidate_contexts=candidates,holding_contexts=holdings,history=history,rotation_config=rotation_config)
        except ValueError as error:
            raise AuditReconstructionError(f"Historical rotation frozen dependency is invalid: {error}") from error
        if (rebuilt.evaluation_id != record.source_rotation_evaluation_id or tuple(x.candidate.instrument_id for x in rebuilt.ranked_candidates) != record.ranked_candidate_ids or
            rebuilt.weakest_holding_id != record.weakest_holding_id or rebuilt.decision.value != record.decision or rebuilt.stance.value != record.stance or rebuilt.preferred_candidate_id != record.preferred_candidate_id or rebuilt.warnings != record.warnings):
            raise AuditReconstructionError("Historical rotation reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("historical_rotation_evaluation.reconstructed",record.evaluation_timestamp,json.dumps({"evaluation_id":evaluation_id,"state":state.backtest_portfolio_state_id,"candidates":list(record.candidate_context_ids)},sort_keys=True))
        return record,run,state,candidates,holdings,history,rebuilt

    def reconstruct_historical_signal_replay_reference(self, reference_id: str):
        ref=self._repository.get_historical_signal_replay_reference(reference_id)
        if ref is None: raise AuditReconstructionError("Historical signal replay reference does not exist.")
        run=self._repository.get_backtest_run(ref.backtest_run_id); analytical=self._repository.get_historical_analytical_evaluation(ref.historical_analytical_evaluation_id)
        gate=self._repository.get_historical_portfolio_gate_evaluation(ref.historical_portfolio_gate_evaluation_id); state=self._repository.get_backtest_portfolio_state(ref.backtest_portfolio_state_id)
        rotation=self._repository.get_historical_rotation_evaluation(ref.historical_rotation_evaluation_id) if ref.historical_rotation_evaluation_id else None
        signal=self._repository.get_signal(ref.signal_id); plan=self._repository.get_trade_plan(ref.trade_plan_id)
        if None in (run,analytical,gate,state,signal,plan) or (ref.historical_rotation_evaluation_id and rotation is None): raise AuditReconstructionError("Historical signal replay has a missing frozen dependency.")
        config=self._repository.get_signal_config_snapshot(ref.signal_config_snapshot_id) if ref.signal_config_snapshot_id else None
        if config is None: raise AuditReconstructionError("LEGACY_CONFIG_REFERENCE_INSUFFICIENT: signal config snapshot is absent.")
        if (config.config.version != ref.signal_config_version or config.fingerprint != ref.signal_config_fingerprint or run.signal_config_version != ref.signal_config_version or analytical.evaluation_timestamp > ref.generation_timestamp or gate.evaluation_timestamp > ref.generation_timestamp or state.evaluation_timestamp > ref.generation_timestamp or signal.as_of_timestamp != ref.generation_timestamp or signal.trade_plan_id != plan.plan_id): raise AuditReconstructionError("Historical signal replay frozen dependency mismatch.")
        events=self._repository.list_signal_events(signal.signal_id)
        if any(x.as_of_timestamp < signal.as_of_timestamp for x in events): raise AuditReconstructionError("Signal lifecycle chronology is invalid.")
        self._repository.append_audit_event("historical_signal_replay.reconstructed",ref.generation_timestamp,json.dumps({"reference_id":reference_id,"signal_id":signal.signal_id,"events":len(events)},sort_keys=True))
        return ref,run,analytical,gate,rotation,state,signal,plan,events

    def reconstruct_historical_paper_replay_reference(self, reference_id: str):
        ref=self._repository.get_historical_paper_replay_reference(reference_id)
        if ref is None: raise AuditReconstructionError("Historical paper replay reference does not exist.")
        run=self._repository.get_backtest_run(ref.backtest_run_id); signal=self._repository.get_signal(ref.signal_id); trade=self._repository.get_paper_trade(ref.paper_trade_id); outcome=self._repository.get_paper_outcome(ref.paper_trade_id)
        if None in (run,signal,trade) or (ref.paper_outcome_id and outcome is None): raise AuditReconstructionError("Historical paper replay has a missing frozen dependency.")
        config=self._repository.get_paper_config_snapshot(ref.paper_config_snapshot_id) if ref.paper_config_snapshot_id else None
        if config is None: raise AuditReconstructionError("LEGACY_CONFIG_REFERENCE_INSUFFICIENT: paper config snapshot is absent.")
        if (config.config.version != ref.paper_config_version or config.fingerprint != ref.paper_config_fingerprint or config.config.cost_model_version != ref.cost_model_version or config.config.fill_method.value != ref.fill_policy or config.config.same_bar_policy.value != ref.same_bar_policy or config.config.gap_policy.value != ref.gap_policy or run.paper_config_version != ref.paper_config_version or trade.source_signal_id != signal.signal_id or (outcome and outcome.paper_trade_id != trade.paper_trade_id) or (ref.paper_outcome_id and ref.paper_outcome_id != trade.paper_trade_id)): raise AuditReconstructionError("Historical paper replay frozen configuration or source mismatch.")
        if outcome and tuple(outcome.price_bar_ids) != ref.frozen_bar_ids: raise AuditReconstructionError("Historical paper replay frozen bar reference mismatch.")
        self._repository.append_audit_event("historical_paper_replay.reconstructed",trade.as_of_timestamp,json.dumps({"reference_id":reference_id,"trade_id":trade.paper_trade_id,"bars":list(ref.frozen_bar_ids)},sort_keys=True))
        return ref,run,signal,trade,outcome

    def reconstruct_historical_execution_timing_context(self, context_id: str, *, bars, calendar):
        """Re-select the persisted entry boundary; never consult a latest bar."""
        context=self._repository.get_historical_execution_timing_context(context_id)
        if context is None: raise AuditReconstructionError("Historical execution timing context does not exist.")
        trigger=self._repository.get_historical_trigger_timing_context(context.trigger_context_id)
        run=self._repository.get_backtest_run(context.backtest_run_id)
        signal=self._repository.get_signal(context.signal_id)
        schedule=self._repository.get_replay_schedule(run.replay_schedule_id) if run else None
        if None in (trigger,run,signal,schedule) or schedule.execution_timing_policy != context.execution_timing_policy or context.calendar_reference != calendar.calendar_id:
            raise AuditReconstructionError("Historical execution timing has a missing or mismatched frozen dependency.")
        from app.backtest.execution_timing import HistoricalExecutionTimingAdapter
        from app.paper.models import PaperBar
        # Selection itself does not use price; retaining this constructed trigger
        # ensures audit replays exactly the frozen market/knowledge timestamps.
        adapter = HistoricalExecutionTimingAdapter(calendar)
        selected, skipped, sessions, status, reason = adapter._select(
            context.execution_timing_policy,
            type("FrozenTrigger", (), {"observed_at": trigger.trigger_timestamp, "known_at": trigger.trigger_known_at})(),
            next((bar for bar in bars if bar.bar_id == trigger.trigger_bar_id), None),
            adapter._historically_eligible_bars(tuple(bars), context.replay_timestamp),
        )
        if (selected.bar_id if selected else None) != context.selected_fill_bar_id or tuple(bar.bar_id for bar in skipped) != context.skipped_bar_ids or tuple(sessions) != context.skipped_session_dates or status != context.status or reason != context.eligibility_reason:
            raise AuditReconstructionError("Historical execution timing reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("historical_execution_timing.reconstructed",context.replay_timestamp,json.dumps({"context_id":context_id,"selected":context.selected_fill_bar_id},sort_keys=True))
        return context,trigger,run,signal

    def reconstruct_historical_capital_allocation(self, allocation_id: str, *, allocation_policy_version: str):
        allocation=self._repository.get_historical_capital_allocation(allocation_id)
        if allocation is None: raise AuditReconstructionError("Historical capital allocation does not exist.")
        run=self._repository.get_backtest_run(allocation.backtest_run_id)
        if run is None or allocation.allocation_policy_version != allocation_policy_version:
            raise AuditReconstructionError("Historical capital allocation has a missing or mismatched frozen policy.")
        expected_order=tuple(sorted(allocation.candidate_signal_ids, key=lambda signal: (-__import__("decimal").Decimal(allocation.ranking_inputs[signal][0]), -__import__("decimal").Decimal(allocation.ranking_inputs[signal][1]), -__import__("decimal").Decimal(allocation.ranking_inputs[signal][2]), signal)))
        if expected_order != allocation.candidate_signal_ids:
            raise AuditReconstructionError("Historical capital allocation ranking order was tampered.")
        links=tuple(self._repository.get_historical_paper_ledger_link(link_id) for link_id in allocation.paper_ledger_link_ids)
        if any(link is None for link in links) or any(link.backtest_run_id != run.backtest_run_id or link.signal_id not in allocation.selected_signal_ids for link in links):
            raise AuditReconstructionError("Historical capital allocation link reference is invalid.")
        entries=tuple(self._repository.get_backtest_portfolio_ledger_event(link.entry_ledger_event_id) for link in links)
        if any(entry is None or entry.event_type.value != "HYPOTHETICAL_BUY" for entry in entries):
            raise AuditReconstructionError("Historical capital allocation entry ledger reference is invalid.")
        reserved=sum((-entry.net_cash_impact for entry in entries), __import__("decimal").Decimal("0"))
        if reserved != allocation.reserved_capital or reserved > allocation.available_cash_before:
            raise AuditReconstructionError("Historical capital allocation cash reconciliation mismatch; stored history was not changed.")
        self._repository.append_audit_event("historical_capital_allocation.reconstructed",allocation.evaluation_timestamp,json.dumps({"allocation_id":allocation_id,"selected":list(allocation.selected_signal_ids),"reserved":str(reserved)},sort_keys=True))
        return allocation,run,links,entries

    def reconstruct_historical_paper_ledger_link(self, link_id: str):
        link=self._repository.get_historical_paper_ledger_link(link_id)
        if link is None: raise AuditReconstructionError("Historical paper ledger link does not exist.")
        trade=self._repository.get_paper_trade(link.paper_trade_id); entry=self._repository.get_backtest_portfolio_ledger_event(link.entry_ledger_event_id) if link.entry_ledger_event_id else None
        snapshot=self._repository.get_paper_config_snapshot(link.sizing_config_snapshot_id) if link.sizing_config_snapshot_id else None
        if trade is None or entry is None or entry.price is None or entry.quantity is None: raise AuditReconstructionError("Historical paper ledger link has missing frozen fill dependencies.")
        from decimal import Decimal, ROUND_FLOOR
        if link.sizing_basis == "UNIT_BASIS": raw=quantity=Decimal("1")
        else:
            if snapshot is None or snapshot.sizing_specification is None or snapshot.sizing_specification.fingerprint != link.sizing_config_fingerprint or snapshot.sizing_specification.sizing_basis != link.sizing_basis:
                raise AuditReconstructionError("Historical paper ledger link sizing snapshot mismatch.")
            spec=snapshot.sizing_specification
            if spec.quantity_rounding_policy != "FLOOR_INTEGER" or spec.fractional_shares_allowed: raise AuditReconstructionError("Historical paper ledger link sizing policy is unsupported.")
            if link.sizing_basis == "FIXED_NOTIONAL":
                if spec.fixed_notional_amount is None or spec.fixed_notional_amount <= 0: raise AuditReconstructionError("Historical paper ledger link lacks fixed notional capital.")
                raw=spec.fixed_notional_amount / entry.price
            elif link.sizing_basis in {"FIXED_R_R", "FIXED_RISK_R"}:
                if spec.fixed_risk_capital_amount is None or spec.fixed_risk_capital_amount <= 0 or trade.structural_stop is None: raise AuditReconstructionError("Historical paper ledger link lacks fixed risk capital or structural stop.")
                risk=abs(entry.price-trade.structural_stop)
                if risk <= 0: raise AuditReconstructionError("Historical paper ledger link has invalid per-unit risk.")
                raw=spec.fixed_risk_capital_amount/risk
            else: raise AuditReconstructionError("Historical paper ledger link has unsupported sizing basis.")
            quantity=raw.to_integral_value(rounding=ROUND_FLOOR)
        required=entry.price*quantity+entry.fees
        if quantity != link.quantity or entry.quantity != link.quantity or link.raw_quantity != raw or link.required_cash != required:
            raise AuditReconstructionError("Historical paper ledger link sizing reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("historical_paper_ledger_link.reconstructed",entry.effective_at,json.dumps({"link_id":link_id,"quantity":str(quantity)},sort_keys=True))
        return link,trade,entry,snapshot

    def reconstruct_historical_equity_series(self, series_id: str):
        series=self._repository.get_historical_equity_series(series_id)
        if series is None: raise AuditReconstructionError("Historical equity series does not exist.")
        run=self._repository.get_backtest_run(series.backtest_run_id)
        points=tuple(self._repository.get_historical_equity_point(point_id) for point_id in series.point_ids)
        if run is None or any(point is None for point in points): raise AuditReconstructionError("Historical equity series has missing frozen dependencies.")
        previous=None
        for point in points:
            state=self._repository.get_backtest_portfolio_state(point.backtest_portfolio_state_id)
            if state is None or state.backtest_run_id != run.backtest_run_id or state.evaluation_timestamp != point.evaluation_timestamp:
                raise AuditReconstructionError("Historical equity point state reference mismatch.")
            snapshot=state.snapshot; holdings=sum((holding.market_value or __import__("decimal").Decimal("0") for holding in snapshot.holdings),__import__("decimal").Decimal("0")); equity=snapshot.portfolio_equity if snapshot.portfolio_equity is not None else snapshot.cash.amount+holdings
            if point.cash != snapshot.cash.amount or point.holdings_market_value != holdings or point.equity != equity or point.frozen_mark_ids != tuple(sorted(set(state.price_reference_ids))):
                raise AuditReconstructionError("Historical equity point reconstruction mismatch; stored history was not changed.")
            if previous is not None and point.evaluation_timestamp <= previous: raise AuditReconstructionError("Historical equity series point ordering is invalid.")
            previous=point.evaluation_timestamp
        self._repository.append_audit_event("historical_equity_series.reconstructed",series.end,json.dumps({"series_id":series_id,"points":len(points)},sort_keys=True))
        return series,run,points

    def reconstruct_walk_forward_run(self, run_id: str):
        """Verify the immutable plan, candidate set, and logical window order."""
        run=self._repository.get_walk_forward_run(run_id)
        if run is None: raise AuditReconstructionError("Walk-forward run does not exist.")
        plan=self._repository.get_walk_forward_plan(run.plan_id)
        if plan is None: raise AuditReconstructionError("Walk-forward run has a missing frozen plan.")
        windows=tuple(self._repository.get_walk_forward_window(window_id) for window_id in run.ordered_window_ids)
        candidates=tuple(self._repository.get_strategy_candidate(candidate_id) for candidate_id in run.candidate_ids)
        if any(window is None for window in windows) or any(candidate is None for candidate in candidates):
            raise AuditReconstructionError("Walk-forward run has missing frozen windows or candidates.")
        if tuple(window.plan_id for window in windows) != tuple(plan.plan_id for _ in windows):
            raise AuditReconstructionError("Walk-forward window plan reference mismatch.")
        if tuple(window.ordinal for window in windows) != tuple(range(1, len(windows)+1)):
            raise AuditReconstructionError("Walk-forward logical window ordering mismatch.")
        if any(window.selected_candidate_id not in run.candidate_ids for window in windows):
            raise AuditReconstructionError("Walk-forward window selected a candidate outside the frozen run set.")
        if any(window.test.start < plan.generated_at and window.test.end < plan.generated_at for window in windows):
            raise AuditReconstructionError("Walk-forward window has invalid frozen TEST timing.")
        self._repository.append_audit_event("walk_forward_run.reconstructed",run.started_at,json.dumps({"run_id":run_id,"plan_id":plan.plan_id,"windows":list(run.ordered_window_ids)},sort_keys=True))
        return run,plan,windows,candidates

    def reconstruct_walk_forward_window_result(self, result_id: str):
        """Check that stored OOS metrics still exactly match frozen canonical output."""
        result=self._repository.get_walk_forward_window_result(result_id)
        if result is None: raise AuditReconstructionError("Walk-forward window result does not exist.")
        run, _plan, windows, candidates=self.reconstruct_walk_forward_run(result.walk_forward_run_id)
        window=next((item for item in windows if item.window_id==result.walk_forward_window_id),None)
        candidate=next((item for item in candidates if item.candidate_id==result.selected_candidate_id),None)
        if window is None or candidate is None or candidate.fingerprint != result.selected_candidate_fingerprint:
            raise AuditReconstructionError("Walk-forward result candidate/window reference mismatch.")
        if result.selection_policy != run.selection_policy or result.selection_policy_version != run.selection_policy_version:
            raise AuditReconstructionError("Walk-forward result selection-policy mismatch.")
        if result.selection_timestamp > window.test.start or result.oos_starting_capital_methodology is not OOSStartingCapitalMethodology.INDEPENDENT_WINDOW_CAPITAL:
            raise AuditReconstructionError("Walk-forward result violates candidate freeze or OOS capital policy.")
        if (result.test_start,result.test_end)!=(window.test.start,window.test.end):
            raise AuditReconstructionError("Walk-forward result TEST interval mismatch.")
        if result.test_backtest_run_id is None:
            if result.status not in {WalkForwardWindowResultStatus.INSUFFICIENT,WalkForwardWindowResultStatus.FAILED,WalkForwardWindowResultStatus.FAILED_AUDIT}:
                raise AuditReconstructionError("Completed walk-forward result lacks its TEST backtest run.")
            return result
        test_run=self._repository.get_backtest_run(result.test_backtest_run_id)
        if test_run is None or test_run.partition_id != window.test.partition_id or (test_run.evaluation_start,test_run.evaluation_end)!=(window.test.start,window.test.end):
            raise AuditReconstructionError("Walk-forward TEST backtest run is not exactly scoped to the frozen TEST partition.")
        versions=(test_run.strategy_version,test_run.registry_version,test_run.scoring_config_version,test_run.gate_config_version,test_run.rotation_config_version,test_run.signal_config_version,test_run.paper_config_version,test_run.performance_config_version)
        expected=(candidate.strategy_version,candidate.registry_version,candidate.scoring_version,candidate.gate_version,candidate.rotation_version,candidate.signal_config_snapshot_id,candidate.paper_config_snapshot_id,candidate.performance_config_version)
        if versions != expected or "INDEPENDENT_WINDOW_CAPITAL" not in test_run.methodology_notes:
            raise AuditReconstructionError("Walk-forward TEST run does not use the selected frozen candidate.")
        if result.performance_report_id is not None:
            report=self._repository.get_performance_report(result.performance_report_id)
            if report is None or f"BACKTEST_RUN:{test_run.backtest_run_id}" not in report.methodology_notes:
                raise AuditReconstructionError("Walk-forward result performance report reference mismatch.")
            metrics=report.metrics
            expected_metrics=(metrics.get("ending_equity"),metrics.get("portfolio_return"),metrics.get("max_drawdown"),metrics.get("sharpe"),metrics.get("sortino"),metrics.get("expectancy"),metrics.get("profit_factor"),metrics.get("win_rate"),int(metrics.get("trade_count",0)),metrics.get("total_costs"))
            actual_metrics=(result.ending_equity,result.absolute_return,result.max_drawdown,result.sharpe,result.sortino,result.expectancy,result.profit_factor,result.win_rate,result.trade_count,result.total_costs)
            if expected_metrics != actual_metrics:
                raise AuditReconstructionError("Walk-forward result metrics mismatch; stored history was not changed.")
            if result.benchmark_comparison_id is not None and not self._repository.list_benchmark_comparisons(report.report_id):
                raise AuditReconstructionError("Walk-forward benchmark comparison reference is missing.")
        elif any(value is not None for value in (result.ending_equity,result.absolute_return,result.max_drawdown,result.sharpe,result.sortino,result.expectancy,result.profit_factor,result.win_rate,result.total_costs)) or result.trade_count != 0:
            raise AuditReconstructionError("Walk-forward result has analytical metrics without a frozen performance report.")
        self._repository.append_audit_event("walk_forward_window_result.reconstructed",result.test_end,json.dumps({"result_id":result_id,"run_id":run.run_id},sort_keys=True))
        return result

    def reconstruct_walk_forward_aggregate_result(self, aggregate_result_id: str):
        """Rebuild TEST-only OOS stitching and reject any altered aggregate history."""
        stored=self._repository.get_walk_forward_aggregate_result(aggregate_result_id)
        if stored is None: raise AuditReconstructionError("Walk-forward aggregate result does not exist.")
        config=self._repository.get_walk_forward_validation_config(stored.validation_config_id)
        series=self._repository.get_walk_forward_oos_equity_series(stored.oos_equity_series_id)
        if config is None or series is None: raise AuditReconstructionError("Walk-forward aggregate has missing frozen config or equity series.")
        if any(self._repository.get_walk_forward_window_result(result_id) is None for result_id in stored.ordered_window_result_ids):
            raise AuditReconstructionError("Walk-forward aggregate has a missing frozen window result.")
        observations=tuple(self._repository.get_oos_stitched_equity_observation(identifier) for identifier in series.observation_ids)
        if any(item is None for item in observations): raise AuditReconstructionError("Walk-forward OOS equity series has missing observations.")
        if tuple(item.window_result_id for item in observations if item.window_result_id not in ()):
            previous=None
            for item in observations:
                if previous is not None and item.timestamp<=previous: raise AuditReconstructionError("Walk-forward OOS equity observation ordering mismatch.")
                previous=item.timestamp
        # Rebuild from the stored frozen config and only pre-TEST degradation references.
        degradation_inputs={}
        for identifier in stored.degradation_analysis_ids:
            analysis=self._repository.get_validation_degradation_analysis(identifier)
            if analysis is None: raise AuditReconstructionError("Walk-forward degradation reference is missing.")
            if analysis.pre_test_end>analysis.test_start: raise AuditReconstructionError("Walk-forward degradation used future evidence.")
            degradation_inputs[analysis.window_result_id]=analysis.pre_test_report_id
        rebuilt, rebuilt_series, rebuilt_points, rebuilt_degradations=WalkForwardAggregationService(self._repository).build(run_id=stored.walk_forward_run_id,config=config,generated_at=stored.oos_end or stored.oos_start,pre_test_report_ids=degradation_inputs)
        if rebuilt != stored or rebuilt_series != series or tuple(rebuilt_points) != observations or tuple(rebuilt_degradations[i].analysis_id for i in range(len(rebuilt_degradations))) != stored.degradation_analysis_ids:
            raise AuditReconstructionError("Walk-forward aggregate reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("walk_forward_aggregate.reconstructed",stored.oos_end or stored.oos_start,json.dumps({"aggregate_result_id":aggregate_result_id,"windows":len(stored.ordered_window_result_ids)},sort_keys=True))
        return stored

    def reconstruct_candidate_selection_result(self, selection_id: str):
        """Audit the bounded TRAIN/VALIDATION-only candidate decision chain."""
        selection=self._repository.get_candidate_selection_result(selection_id)
        if selection is None: raise AuditReconstructionError("Candidate selection result does not exist.")
        experiment=self._repository.get_strategy_experiment(selection.experiment_id); policy=self._repository.get_candidate_selection_policy(selection.policy_id)
        if experiment is None or policy is None or selection.baseline_candidate_id!=experiment.baseline_candidate_id or selection.policy_version!=policy.version:
            raise AuditReconstructionError("Candidate selection has invalid frozen experiment or policy references.")
        evidence=self._repository.list_candidate_evaluation_evidence(experiment.experiment_id)
        if tuple(item.evidence_id for item in evidence)!=selection.evidence_ids or any(item.partition_type.value=="TEST" or item.evaluated_at>selection.selection_timestamp for item in evidence):
            raise AuditReconstructionError("Candidate selection evidence violates immutable TRAIN/VALIDATION chronology.")
        deltas=self._repository.list_strategy_candidate_deltas(experiment.experiment_id)
        for delta in deltas:
            if self._repository.get_strategy_candidate(delta.candidate_id) is None: raise AuditReconstructionError("Candidate selection delta references a missing full candidate snapshot.")
        if selection.selected_candidate_id is not None and selection.selected_candidate_id not in selection.candidate_ids:
            raise AuditReconstructionError("Candidate selection selected a candidate outside its frozen set.")
        if any(self._repository.get_candidate_robustness_result(identifier) is None for identifier in selection.robustness_result_ids):
            raise AuditReconstructionError("Candidate selection robustness reference is missing.")
        self._repository.append_audit_event("candidate_selection.reconstructed",selection.selection_timestamp,json.dumps({"selection_id":selection_id,"experiment_id":experiment.experiment_id},sort_keys=True))
        return selection,experiment,policy,evidence,deltas

    def reconstruct_strategy_promotion(self, proposal_id: str, *, eligibility_id: str, review_id: str | None = None, approved_id: str | None = None, activation_id: str | None = None, rollback_id: str | None = None):
        proposal=self._repository.get_strategy_promotion_proposal(proposal_id);eligibility=self._repository.get_promotion_eligibility_result(eligibility_id)
        if proposal is None or eligibility is None or eligibility.proposal_id!=proposal.proposal_id:raise AuditReconstructionError("Promotion proposal or eligibility linkage mismatch.")
        policy=self._repository.get_strategy_promotion_policy(eligibility.policy_id);selection=self._repository.get_candidate_selection_result(proposal.selection_id)
        if policy is None or policy.version!=eligibility.policy_version or selection is None or selection.experiment_id!=proposal.experiment_id or selection.selected_candidate_id!=proposal.candidate_id:raise AuditReconstructionError("Promotion frozen policy or candidate-selection linkage mismatch.")
        aggregates=tuple(self._repository.get_walk_forward_aggregate_result(i) for i in proposal.aggregate_result_ids)
        if not aggregates or any(item is None for item in aggregates):raise AuditReconstructionError("Promotion lacks frozen auditable OOS evidence.")
        review=approved=activation=rollback=None
        if review_id is not None:
            review=self._repository.get_strategy_promotion_review(review_id)
            if review is None or review.proposal_id!=proposal_id or review.policy_version!=policy.version:raise AuditReconstructionError("Promotion human-review linkage mismatch.")
        if approved_id is not None:
            approved=self._repository.get_approved_strategy_version(approved_id)
            if approved is None or review is None or approved.proposal_id!=proposal_id or approved.review_id!=review.review_id or approved.candidate_id!=proposal.candidate_id or approved.approved_at<review.reviewed_at or approved.effective_from<approved.approved_at:raise AuditReconstructionError("Approved strategy lineage/effective-from mismatch.")
            if approved.parent_approved_id is not None:
                parent=self._repository.get_approved_strategy_version(approved.parent_approved_id)
                if parent is None or parent.strategy_id!=approved.strategy_id or parent.effective_from>approved.effective_from:raise AuditReconstructionError("Approved strategy parent lineage mismatch.")
        if activation_id is not None:
            activation=self._repository.get_strategy_activation(activation_id)
            if activation is None or approved is None or activation.approved_id!=approved.approved_id or activation.review_id!=approved.review_id or activation.effective_at<approved.effective_from:raise AuditReconstructionError("Strategy activation linkage/effective timestamp mismatch.")
        if rollback_id is not None:
            rollback=self._repository.get_strategy_rollback(rollback_id)
            if rollback is None or activation is None or rollback.activation_id!=activation.activation_id or rollback.to_approved_id!=activation.approved_id or rollback.review_id!=activation.review_id or self._repository.get_approved_strategy_version(rollback.from_approved_id) is None:raise AuditReconstructionError("Rollback governance linkage mismatch.")
        self._repository.append_audit_event("strategy_promotion.reconstructed",proposal.created_at,json.dumps({"proposal_id":proposal_id,"eligibility_id":eligibility_id,"review_id":review_id,"approved_id":approved_id,"activation_id":activation_id,"rollback_id":rollback_id},sort_keys=True))
        return proposal,eligibility,policy,selection,aggregates,review,approved,activation,rollback

    def reconstruct_self_improvement(self, run_id: str, *, policy_id: str, rule_set_id: str):
        """Rebuild deterministic associations from frozen observations only."""
        run=self._repository.get_self_improvement_run(run_id)
        policy=self._repository.get_self_improvement_evidence_policy(policy_id)
        rules=self._repository.get_attribution_rule_set(rule_set_id)
        if run is None or policy is None or rules is None:
            raise AuditReconstructionError("Self-improvement audit has missing frozen run, policy, or rule set.")
        expected=SelfImprovementAttributionService(self._repository).analyze(run_id,policy_id,rule_set_id,persist=False)
        stored=(self._repository.list_strategy_error_attributions(run_id),self._repository.list_strategy_success_attributions(run_id),self._repository.list_recurring_strategy_patterns(run_id),self._repository.list_strategy_error_summaries(run_id),self._repository.list_strategy_success_summaries(run_id))
        normalized_expected=(tuple(sorted(expected[0],key=lambda value:value.attribution_id)),tuple(sorted(expected[1],key=lambda value:value.attribution_id)),tuple(sorted(expected[2],key=lambda value:value.pattern_id)),tuple(sorted(expected[3],key=lambda value:value.summary_id)),tuple(sorted(expected[4],key=lambda value:value.summary_id)))
        if stored!=normalized_expected:
            raise AuditReconstructionError("Self-improvement frozen attribution reconstruction mismatch; stored history was not changed.")
        self._repository.append_audit_event("self_improvement.reconstructed",run.analysis_end,json.dumps({"run_id":run_id,"policy_id":policy_id,"rule_set_id":rule_set_id},sort_keys=True))
        return (run,policy,rules,*stored)

    def reconstruct_self_improvement_hypotheses(self, run_id: str, *, evidence_policy_id: str, rule_set_id: str, generation_policy_id: str, budget_id: str, target_approved_strategy_id: str, ranking_id: str, review_id: str | None = None):
        run, *_ = self.reconstruct_self_improvement(run_id,policy_id=evidence_policy_id,rule_set_id=rule_set_id)
        policy=self._repository.get_hypothesis_generation_policy(generation_policy_id);budget=self._repository.get_hypothesis_proposal_budget(budget_id);target=self._repository.get_approved_strategy_version(target_approved_strategy_id);ranking=self._repository.get_strategy_hypothesis_ranking(ranking_id)
        if policy is None or budget is None or target is None or ranking is None:
            raise AuditReconstructionError("Hypothesis audit has missing frozen generation policy, budget, target, or ranking.")
        stored=self._repository.list_strategy_improvement_hypotheses(run_id)
        generated_at=stored[0].created_at if stored else run.analysis_end
        expected_hypotheses,expected_ranking=SelfImprovementHypothesisService(self._repository).generate(run_id=run_id,evidence_policy_id=evidence_policy_id,generation_policy_id=generation_policy_id,budget_id=budget_id,target_approved_strategy_id=target_approved_strategy_id,created_at=generated_at,persist=False)
        if stored!=tuple(sorted(expected_hypotheses,key=lambda value:value.hypothesis_id)) or ranking!=expected_ranking:
            raise AuditReconstructionError("Self-improvement hypothesis reconstruction mismatch; stored history was not changed.")
        if review_id is not None:
            review=self._repository.get_hypothesis_review(review_id);hypothesis=self._repository.get_strategy_improvement_hypothesis(review.hypothesis_id) if review is not None else None
            if review is None or hypothesis is None or review.evidence_fingerprint!=hypothesis.evidence_fingerprint or review.reviewed_at<hypothesis.created_at or not review.reviewer_id.startswith("human:") or review.fingerprint!=hypothesis_review_fingerprint(review):
                raise AuditReconstructionError("Hypothesis human-review linkage or chronology mismatch.")
        self._repository.append_audit_event("self_improvement_hypotheses.reconstructed",run.analysis_end,json.dumps({"run_id":run_id,"ranking_id":ranking_id,"review_id":review_id},sort_keys=True))
        return run,stored,ranking

    def reconstruct_hypothesis_experiment_link(self, link_id: str, *, evidence_policy_id: str, rule_set_id: str, generation_policy_id: str, hypothesis_budget_id: str, ranking_id: str):
        link=self._repository.get_hypothesis_experiment_link(link_id)
        if link is None: raise AuditReconstructionError("Hypothesis experiment link does not exist.")
        hypothesis=self._repository.get_strategy_improvement_hypothesis(link.hypothesis_id);review=self._repository.get_hypothesis_review(link.review_id);experiment=self._repository.get_strategy_experiment(link.experiment_id);budget=self._repository.get_experiment_budget(link.experiment_budget_id);baseline=self._repository.get_strategy_candidate(link.baseline_candidate_id)
        if None in (hypothesis,review,experiment,budget,baseline): raise AuditReconstructionError("Hypothesis experiment link has missing frozen references.")
        self.reconstruct_self_improvement_hypotheses(link.run_id,evidence_policy_id=evidence_policy_id,rule_set_id=rule_set_id,generation_policy_id=generation_policy_id,budget_id=hypothesis_budget_id,target_approved_strategy_id=link.target_approved_strategy_id,ranking_id=ranking_id,review_id=review.review_id)
        deltas=self._repository.list_strategy_candidate_deltas(experiment.experiment_id)
        if review.decision.value!="APPROVE_FOR_EXPERIMENT" or not review.reviewer_id.startswith("human:") or review.evidence_fingerprint!=hypothesis.evidence_fingerprint or hypothesis.target_approved_strategy_id!=link.target_approved_strategy_id or hypothesis.target_strategy_version!=link.target_strategy_version: raise AuditReconstructionError("Hypothesis experiment approval or target linkage mismatch.")
        if experiment.status is not ExperimentStatus.PLANNED or experiment.baseline_candidate_id!=baseline.candidate_id or len(deltas)!=1 or tuple(delta.delta_id for delta in deltas)!=link.candidate_delta_ids or deltas[0].changed_field!=hypothesis.target_field or deltas[0].experimental_value!=SelfImprovementExperimentBridge._reviewed_value(review.comments) or f"HYPOTHESIS_ID:{hypothesis.hypothesis_id}" not in experiment.hypothesis: raise AuditReconstructionError("Hypothesis experiment frozen draft reconstruction mismatch.")
        candidate=self._repository.get_strategy_candidate(experiment.experimental_candidate_ids[0]) if experiment.experimental_candidate_ids else None
        if candidate is None: raise AuditReconstructionError("Hypothesis experiment lacks its complete experimental candidate.")
        delta=deltas[0]
        seed=manifest_fingerprint(hypothesis=hypothesis.fingerprint,review=review.fingerprint,budget=budget.fingerprint,baseline=baseline.fingerprint,value=delta.experimental_value,dataset=(experiment.dataset_id,experiment.dataset_version),partitions=experiment.permitted_partition_ids)
        if (link.link_id,experiment.experiment_id,delta.delta_id,candidate.candidate_id)!=("hypothesis-experiment-link-"+seed[:24],"hypothesis-experiment-"+seed[:24],"hypothesis-delta-"+seed[:24],"hypothesis-candidate-"+seed[:24]) or candidate.fingerprint!=manifest_fingerprint(baseline=baseline.fingerprint,hypothesis=hypothesis.fingerprint,review=review.fingerprint,value=delta.experimental_value) or delta.fingerprint!=manifest_fingerprint(seed=seed,delta=hypothesis.target_field) or experiment.fingerprint!=manifest_fingerprint(seed=seed,experiment="v1") or link.fingerprint!=manifest_fingerprint(seed=seed,link="v1"):
            raise AuditReconstructionError("Hypothesis experiment identity or frozen complete-candidate fingerprint mismatch.")
        try: ControlledCandidateExperimentService(self._repository).validate_experiment(experiment,budget,deltas)
        except ValueError as error: raise AuditReconstructionError(str(error)) from error
        self._repository.append_audit_event("hypothesis_experiment_link.reconstructed",link.created_at,json.dumps({"link_id":link_id,"experiment_id":experiment.experiment_id},sort_keys=True))
        return link,experiment,deltas,candidate

    def reconstruct_automated_research_cycle(self, cycle_result_id: str):
        cycle=self._repository.get_automated_research_cycle_result(cycle_result_id)
        if cycle is None: raise AuditReconstructionError("Automated research cycle does not exist.")
        run=self._repository.get_automated_research_run(cycle.research_run_id);experiment=self._repository.get_strategy_experiment(run.experiment_id) if run else None;link=self._repository.get_hypothesis_experiment_link(run.hypothesis_experiment_link_id) if run else None;selection=self._repository.get_candidate_selection_result(cycle.selection_id)
        if run is None or experiment is None or link is None or selection is None or run.status.value not in {"COMPLETED","COMPLETED_WITH_WARNINGS","INSUFFICIENT_EVIDENCE"} or experiment.status is not ExperimentStatus.PLANNED or link.experiment_id!=experiment.experiment_id: raise AuditReconstructionError("Automated research run linkage/status mismatch.")
        evidence=tuple(self._repository.list_candidate_evaluation_evidence(experiment.experiment_id)); ids={value.evidence_id for value in evidence}
        if any(value.partition_type.value=="TEST" for value in evidence) or not set(cycle.train_evidence_ids).issubset(ids) or not set(cycle.validation_evidence_ids).issubset(ids) or tuple(selection.evidence_ids)!=tuple(value.evidence_id for value in evidence): raise AuditReconstructionError("Automated research evidence contains TEST leakage or frozen-selection mismatch.")
        if cycle.queue_id is not None:
            queue=self._repository.get_future_oos_candidate_queue_entry(cycle.queue_id)
            if queue is None or queue.selection_id!=selection.selection_id or selection.selected_candidate_id!=queue.selected_candidate_id or queue.earliest_test_timestamp<=queue.selection_timestamp: raise AuditReconstructionError("Future OOS queue linkage/timestamp mismatch.")
        self._repository.append_audit_event("automated_research_cycle.reconstructed",run.completed_at or run.started_at,json.dumps({"cycle_result_id":cycle_result_id,"run_id":run.research_run_id},sort_keys=True))
        return cycle,run,evidence,selection

    def reconstruct_future_oos_execution(self, execution_result_id: str):
        result=self._repository.get_future_oos_execution_result(execution_result_id)
        if result is None: raise AuditReconstructionError("Future OOS execution result does not exist.")
        assignment=self._repository.get_future_oos_assignment(result.assignment_id); window_result=self._repository.get_walk_forward_window_result(result.walk_forward_window_result_id)
        if assignment is None or window_result is None or result.fingerprint!=future_oos_execution_fingerprint(result): raise AuditReconstructionError("Future OOS execution result fingerprint or frozen linkage mismatch.")
        policy=self._repository.get_future_oos_assignment_policy(assignment.policy_id); queue=self._repository.get_future_oos_candidate_queue_entry(assignment.queue_id); selection=self._repository.get_candidate_selection_result(assignment.selection_id); candidate=self._repository.get_strategy_candidate(assignment.selected_candidate_id); window=self._repository.get_walk_forward_window(assignment.window_id)
        if policy is None or queue is None or selection is None or candidate is None or window is None or assignment.fingerprint!=future_oos_assignment_fingerprint(assignment): raise AuditReconstructionError("Future OOS assignment has missing or tampered frozen provenance.")
        if policy.version!=assignment.policy_version or queue.status.value!="QUEUED" or queue.selection_id!=selection.selection_id or queue.selected_candidate_id!=candidate.candidate_id or queue.candidate_fingerprint!=candidate.fingerprint or assignment.candidate_fingerprint!=candidate.fingerprint or assignment.assigned_at>=assignment.test_start or selection.selection_timestamp>=assignment.test_start or assignment.test_start<queue.earliest_test_timestamp or assignment.test_start-assignment.assigned_at<timedelta(seconds=policy.minimum_lead_seconds) or policy.allowed_plan_ids and assignment.plan_id not in policy.allowed_plan_ids:
            raise AuditReconstructionError("Future OOS selection, candidate, policy, or chronology mismatch.")
        if window.window_id!=assignment.window_id or window.plan_id!=assignment.plan_id or window.test.partition_id!=assignment.test_partition_id or (window.test.start,window.test.end)!=(assignment.test_start,assignment.test_end) or window.candidate_selection_result_id!=selection.selection_id or window.selection_timestamp!=selection.selection_timestamp or window.selected_candidate_fingerprint!=candidate.fingerprint:
            raise AuditReconstructionError("Future OOS TEST window linkage mismatch.")
        rebuilt=self.reconstruct_walk_forward_window_result(window_result.result_id)
        expected_status={"COMPLETED":"COMPLETED","COMPLETED_WITH_WARNINGS":"COMPLETED_WITH_WARNINGS","INSUFFICIENT":"INSUFFICIENT","FAILED":"FAILED","FAILED_AUDIT":"FAILED"}[window_result.status.value]
        if rebuilt!=window_result or result.status.value!=expected_status or policy.expiration_seconds is not None and result.executed_at>selection.selection_timestamp+timedelta(seconds=policy.expiration_seconds) or (result.test_backtest_run_id,result.performance_report_id,result.benchmark_comparison_id)!=(window_result.test_backtest_run_id,window_result.performance_report_id,window_result.benchmark_comparison_id): raise AuditReconstructionError("Future OOS canonical TEST result mismatch.")
        self._repository.append_audit_event("future_oos_execution.reconstructed",result.executed_at,json.dumps({"execution_result_id":result.execution_result_id,"assignment_id":assignment.assignment_id},sort_keys=True))
        return assignment,window_result,result

    def reconstruct_promotion_evidence_package(self, package_id: str):
        package=self._repository.get_promotion_evidence_package(package_id)
        if package is None: raise AuditReconstructionError("Promotion evidence package does not exist.")
        try:
            expected_record,expected_package=FutureOOSEvidencePackagingService(self._repository).package(selection_id=package.selection_id,generated_at=package.generated_at,aggregate_result_id=package.aggregate_result_id,persist=False)
        except ValueError as error: raise AuditReconstructionError(str(error)) from error
        stored_record=self._repository.get_research_candidate_oos_record(expected_record.record_id)
        if stored_record!=expected_record or package!=expected_package:
            raise AuditReconstructionError("Promotion evidence package or OOS coverage reconstruction mismatch.")
        if package.aggregate_result_id is not None:
            aggregate=self._repository.get_walk_forward_aggregate_result(package.aggregate_result_id)
            if aggregate is None or tuple(aggregate.ordered_window_result_ids)!=package.window_result_ids:
                raise AuditReconstructionError("Promotion evidence package aggregate linkage mismatch.")
        for execution_id in package.execution_result_ids: self.reconstruct_future_oos_execution(execution_id)
        self._repository.append_audit_event("promotion_evidence_package.reconstructed",package.generated_at,json.dumps({"package_id":package_id,"selection_id":package.selection_id},sort_keys=True))
        return stored_record,package

    def reconstruct_prebreakout_policy_approval(
        self,
        approval_id: str,
        *,
        drafts: tuple[PreBreakoutPolicyDraft, ...] = (PreBreakoutPolicyDraft(),),
    ):
        """Audit immutable draft-to-human-approval lineage without changing governance state."""
        try:
            approval = self._repository.get_prebreakout_policy_approval(approval_id)
            if approval is None:
                raise ValueError("PREBREAKOUT_POLICY_APPROVAL_NOT_FOUND")
            view = PreBreakoutPolicyGovernanceService(
                self._repository,
                drafts=drafts,
            ).validate_approval(approval)
        except ValueError as error:
            raise AuditReconstructionError(str(error)) from error
        self._repository.append_audit_event(
            "prebreakout_policy_approval.reconstructed",
            view.approval.created_at,
            json.dumps({"approval_id": approval_id, "policy_id": view.policy.policy_id}, sort_keys=True),
        )
        return view

    def reconstruct_prebreakout_policy_selection(
        self,
        selection_id: str,
        *,
        drafts: tuple[PreBreakoutPolicyDraft, ...] = (PreBreakoutPolicyDraft(),),
    ):
        """Audit immutable approval-to-selected-for-scan lineage only."""
        try:
            selection = self._repository.get_prebreakout_policy_selection(selection_id)
            if selection is None:
                raise ValueError("PREBREAKOUT_POLICY_SELECTION_NOT_FOUND")
            view = PreBreakoutPolicyGovernanceService(
                self._repository,
                drafts=drafts,
            ).validate_selection(selection)
        except ValueError as error:
            raise AuditReconstructionError(str(error)) from error
        self._repository.append_audit_event(
            "prebreakout_policy_selection.reconstructed",
            view.selection.selected_at,
            json.dumps({"selection_id": selection_id, "approval_id": view.approval.approval_id}, sort_keys=True),
        )
        return view

    def reconstruct_brain_research_handoff(
        self,
        handoff_id: str,
        *,
        origin_validator: Callable[[BrainResearchHandoff], BrainResearchHandoff] | None = None,
    ) -> BrainResearchHandoff:
        """Read and validate immutable handoff lineage without consuming it."""
        try:
            handoff = self._repository.get_brain_research_handoff(handoff_id)
            if handoff is None:
                raise ValueError("BRAIN_RESEARCH_HANDOFF_NOT_FOUND")
            if origin_validator is not None and origin_validator(handoff) != handoff:
                raise ValueError("BRAIN_RESEARCH_HANDOFF_ORIGIN_RECONSTRUCTION_MISMATCH")
        except ValueError as error:
            raise AuditReconstructionError(str(error)) from error
        self._repository.append_audit_event(
            "brain_research_handoff.reconstructed",
            handoff.evaluation_as_of,
            json.dumps({"handoff_id": handoff.handoff_id, "origin_type": handoff.origin_type.value}, sort_keys=True),
        )
        return handoff
