from dataclasses import replace
from datetime import timedelta

import pytest

from app.backtest.engine import BacktestReplayEngine
from app.backtest.experiments import CandidateSelectionPolicy, CandidateSelectionResult, CandidateSelectionStatus, ExperimentBudget, ExperimentStatus, StrategyExperiment
from app.backtest.walk_forward import WalkForwardStatus, WalkForwardWindow
from app.historical.guard import manifest_fingerprint
from app.self_improvement.future_oos import FutureOOSExecutionService
from app.self_improvement.models import FutureOOSAssignment, FutureOOSAssignmentPolicy, FutureOOSAssignmentStatus, FutureOOSCandidateQueueEntry, FutureOOSQueueStatus, future_oos_assignment_fingerprint, future_oos_assignment_policy_fingerprint
from app.services.audit_reconstruction_service import AuditReconstructionService
from tests.integration.test_walk_forward_execution import CALENDAR, T, frozen_objects, oos_run, policy, schedule


def _frozen_assignment(repo, plan, candidate, window):
    budget=ExperimentBudget("future-budget","1",1,1,{},1,"v1",manifest_fingerprint(budget="future")); repo.save_experiment_budget(budget)
    experiment=StrategyExperiment("future-experiment","future","frozen research",candidate.candidate_id,(),plan.dataset_id,plan.dataset_version,(),(),budget.budget_id,"v1",T,ExperimentStatus.PLANNED,(),manifest_fingerprint(experiment="future")); repo.save_strategy_experiment(experiment)
    selection_policy=CandidateSelectionPolicy("future-selection-policy","1",0,__import__("decimal").Decimal("0"),__import__("decimal").Decimal("0"),__import__("decimal").Decimal("1"),__import__("decimal").Decimal("1"),__import__("decimal").Decimal("0"),None,"v1",manifest_fingerprint(policy="future")); repo.save_candidate_selection_policy(selection_policy)
    selected_at=window.test.start-timedelta(days=1)
    selection=CandidateSelectionResult("future-selection",experiment.experiment_id,candidate.candidate_id,(candidate.candidate_id,),(),(),selection_policy.policy_id,selection_policy.version,candidate.candidate_id,CandidateSelectionStatus.CANDIDATE_SELECTED,("FROZEN",),(),selected_at,manifest_fingerprint(selection="future")); repo.save_candidate_selection_result(selection)
    queue=FutureOOSCandidateQueueEntry("future-queue",selection.selection_id,candidate.candidate_id,plan.plan_id,"future-family",window.test.start,selected_at,candidate.fingerprint,FutureOOSQueueStatus.QUEUED,(),manifest_fingerprint(queue="future")); repo.save_future_oos_candidate_queue_entry(queue)
    policy_value=FutureOOSAssignmentPolicy("future-assignment-policy","1",3600,(plan.plan_id,),False,1,None,"v1",""); policy_value=replace(policy_value,fingerprint=future_oos_assignment_policy_fingerprint(policy_value)); repo.save_future_oos_assignment_policy(policy_value)
    assignment=FutureOOSAssignment("future-assignment",queue.queue_id,selection.selection_id,candidate.candidate_id,plan.plan_id,window.window_id,window.test.partition_id,window.test.start-timedelta(hours=2),window.test.start,window.test.end,candidate.fingerprint,policy_value.policy_id,policy_value.version,FutureOOSAssignmentStatus.ASSIGNED,(),"")
    assignment=replace(assignment,fingerprint=future_oos_assignment_fingerprint(assignment)); repo.save_future_oos_assignment(assignment)
    return assignment,selection


def future_oos_context(tmp_path, *, suffix=""):
    repo,data,candidate,plan,windows,run=frozen_objects(tmp_path); plan=replace(plan,plan_id=f"future-plan{suffix}",fingerprint=manifest_fingerprint(plan=f"future{suffix}")); repo.save_walk_forward_plan(plan); base=windows[0]
    window=WalkForwardWindow(f"future-window{suffix}",plan.plan_id,1,base.train,base.validation,base.test,candidate.candidate_id,WalkForwardStatus.PLANNED,(),manifest_fingerprint(window=f"future{suffix}"),"future-selection",base.test.start-timedelta(days=1),candidate.fingerprint)
    repo.save_walk_forward_window(window); run=replace(run,run_id=f"future-run{suffix}",plan_id=plan.plan_id,ordered_window_ids=(window.window_id,),fingerprint=manifest_fingerprint(run=f"future{suffix}")); repo.save_walk_forward_run(run); assignment,selection=_frozen_assignment(repo,plan,candidate,window)
    return repo,data,candidate,window,run,assignment,selection


def test_future_oos_execution_reuses_clean_test_executor_and_retains_evidence_only(tmp_path):
    repo,data,candidate,window,run,assignment,selection=future_oos_context(tmp_path)
    test_run=oos_run("future-test-run",data,candidate,window)
    execution,result=FutureOOSExecutionService(repo).execute(assignment_id=assignment.assignment_id,walk_forward_run_id=run.run_id,test_run=test_run,executed_at=window.test.end,phase8_executor=lambda value, partition: BacktestReplayEngine(repo).run(value,schedule(),CALENDAR,policy(),partition))
    assert execution.assignment_id==assignment.assignment_id and execution.walk_forward_window_result_id==result.result_id
    assert repo.get_future_oos_execution_result(execution.execution_result_id)==execution
    assert AuditReconstructionService(repo).reconstruct_future_oos_execution(execution.execution_result_id)==(assignment,result,execution)
    assert result.selection_timestamp==selection.selection_timestamp and result.selected_candidate_fingerprint==candidate.fingerprint
    assert "BENCHMARK_UNAVAILABLE" in execution.warnings
    with pytest.raises(ValueError,match="immutable"):
        repo.save_future_oos_execution_result(execution)
    assert repo.get_strategy_promotion_proposal("never-created") is None


def test_future_oos_execution_rejects_changed_window_or_retroactive_assignment(tmp_path):
    repo,data,candidate,window,run,assignment,_=future_oos_context(tmp_path,suffix="-guard")
    bad=replace(assignment,test_end=assignment.test_end+timedelta(days=1),fingerprint="tampered")
    repo._connection.execute("UPDATE future_oos_assignments SET payload_json=? WHERE id=?", (__import__("json").dumps(__import__("app.self_improvement.serialization",fromlist=["dump"]).dump(bad)), assignment.assignment_id)); repo._connection.commit()
    with pytest.raises(ValueError,match="TEST window"):
        FutureOOSExecutionService(repo).execute(assignment_id=assignment.assignment_id,walk_forward_run_id=run.run_id,test_run=oos_run("guard-run",data,candidate,window),executed_at=window.test.end,phase8_executor=lambda *_: None)


@pytest.mark.parametrize("callback",(lambda _run: type("Wrong",(),{"report_id":"report-for-other-run"})(),lambda _run: (_ for _ in ()).throw(RuntimeError("integration failure"))))
def test_post_replay_callback_wrong_run_or_failure_fails_safe(tmp_path,callback):
    repo,data,candidate,window,run,assignment,_=future_oos_context(tmp_path,suffix="-callback")
    frozen=(assignment, candidate.fingerprint)
    execution,result=FutureOOSExecutionService(repo).execute(assignment_id=assignment.assignment_id,walk_forward_run_id=run.run_id,test_run=oos_run("callback-test",data,candidate,window),executed_at=window.test.end,phase8_executor=lambda value,partition: BacktestReplayEngine(repo).run(value,schedule(),CALENDAR,policy(),partition),post_replay_performance_integrator=callback)
    assert execution.status.value=="FAILED" and result.status.value=="FAILED"
    assert repo.get_future_oos_assignment(assignment.assignment_id)==frozen[0] and repo.get_strategy_candidate(candidate.candidate_id).fingerprint==frozen[1]
    assert repo.get_strategy_promotion_proposal("not-created") is None
