"""Frozen research-selection handoff to the existing clean TEST executor."""
from dataclasses import replace
from datetime import datetime, timedelta

from app.backtest.walk_forward import WalkForwardExecutionService, WalkForwardWindowResultStatus
from app.historical.guard import manifest_fingerprint
from .models import FutureOOSExecutionResult, FutureOOSExecutionStatus, future_oos_execution_fingerprint


class FutureOOSExecutionService:
    """Assigns no new candidate and delegates TEST execution to Phase 8A machinery."""

    def __init__(self, repository): self.repository=repository

    def execute(self, *, assignment_id: str, walk_forward_run_id: str, test_run, executed_at: datetime, phase8_executor, post_replay_performance_integrator=None):
        assignment=self.repository.get_future_oos_assignment(assignment_id)
        if assignment is None: raise ValueError("Future OOS assignment does not exist.")
        queue=self.repository.get_future_oos_candidate_queue_entry(assignment.queue_id); policy=self.repository.get_future_oos_assignment_policy(assignment.policy_id); selection=self.repository.get_candidate_selection_result(assignment.selection_id); candidate=self.repository.get_strategy_candidate(assignment.selected_candidate_id); run=self.repository.get_walk_forward_run(walk_forward_run_id); window=self.repository.get_walk_forward_window(assignment.window_id)
        if queue is None or policy is None or selection is None or candidate is None or run is None or window is None: raise ValueError("Future OOS execution has missing frozen assignment provenance.")
        if assignment.status.value!="ASSIGNED" or queue.status.value!="QUEUED" or selection.selected_candidate_id!=candidate.candidate_id or candidate.fingerprint!=assignment.candidate_fingerprint or queue.candidate_fingerprint!=assignment.candidate_fingerprint:
            raise ValueError("Future OOS execution requires an intact queued frozen candidate selection.")
        if window.plan_id!=assignment.plan_id or window.window_id!=assignment.window_id or window.test.partition_id!=assignment.test_partition_id or window.test.start!=assignment.test_start or window.test.end!=assignment.test_end or window.selected_candidate_id!=candidate.candidate_id or window.candidate_selection_result_id!=selection.selection_id or window.selection_timestamp!=selection.selection_timestamp or window.selected_candidate_fingerprint!=candidate.fingerprint:
            raise ValueError("Future OOS execution TEST window does not exactly match its frozen assignment.")
        if assignment.assigned_at>=window.test.start or selection.selection_timestamp>=window.test.start or test_run.evaluation_start!=window.test.start or test_run.evaluation_end!=window.test.end:
            raise ValueError("Future OOS execution cannot attach selection or work to a started TEST window.")
        if policy.version!=assignment.policy_version or policy.expiration_seconds is not None and executed_at>selection.selection_timestamp+timedelta(seconds=policy.expiration_seconds):
            raise ValueError("Expired or policy-mismatched future OOS assignment cannot be executed.")
        result=WalkForwardExecutionService(self.repository).execute_window(run=run,window=window,candidate=candidate,selected_at=selection.selection_timestamp,test_run=test_run,phase8_executor=phase8_executor,selection_evidence_ids=selection.evidence_ids,post_replay_performance_integrator=post_replay_performance_integrator)
        status={WalkForwardWindowResultStatus.COMPLETED:FutureOOSExecutionStatus.COMPLETED,WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS:FutureOOSExecutionStatus.COMPLETED_WITH_WARNINGS,WalkForwardWindowResultStatus.INSUFFICIENT:FutureOOSExecutionStatus.INSUFFICIENT,WalkForwardWindowResultStatus.FAILED:FutureOOSExecutionStatus.FAILED,WalkForwardWindowResultStatus.FAILED_AUDIT:FutureOOSExecutionStatus.FAILED}[result.status]
        value=FutureOOSExecutionResult("future-oos-execution-"+manifest_fingerprint(assignment=assignment.fingerprint,window_result=result.fingerprint)[:24],assignment.assignment_id,result.test_backtest_run_id,result.result_id,result.performance_report_id,result.benchmark_comparison_id,status,result.warnings,executed_at,"")
        value=replace(value,fingerprint=future_oos_execution_fingerprint(value)); self.repository.save_future_oos_execution_result(value)
        return value,result
