from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.walk_forward import OOSStartingCapitalMethodology, WalkForwardMode, WalkForwardPlan, WalkForwardRun, WalkForwardRunStatus, WalkForwardStatus, WalkForwardWindow, WalkForwardWindowResult, WalkForwardWindowResultStatus
from app.historical.guard import manifest_fingerprint
from app.historical.models import HistoricalPartition, PartitionType
from app.self_improvement.models import FutureOOSAssignment, FutureOOSAssignmentPolicy, FutureOOSAssignmentStatus, FutureOOSExecutionResult, FutureOOSExecutionStatus, future_oos_assignment_fingerprint, future_oos_assignment_policy_fingerprint, future_oos_execution_fingerprint
from app.self_improvement.oos_evidence import FutureOOSEvidencePackagingService
from app.backtest.oos_aggregation import WalkForwardAggregationService, WalkForwardValidationConfig
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.integration.test_walk_forward_execution import manifest, repository
from tests.unit.test_automated_research_cycle import T, _queued_candidate


def packaged_fixture(tmp_path):
    data=manifest("package-data","1","package-data-fingerprint"); repo,data=repository(tmp_path,data); _,selection,queue=_queued_candidate(repo); candidate=repo.get_strategy_candidate(selection.selected_candidate_id)
    test=HistoricalPartition("package-test",data.dataset_id,PartitionType.TEST,T+timedelta(days=12),T+timedelta(days=16),0,0,"future test",T)
    train=HistoricalPartition("package-train",data.dataset_id,PartitionType.TRAIN,T,T+timedelta(days=4),0,0,"train",T)
    validation=HistoricalPartition("package-validation",data.dataset_id,PartitionType.VALIDATION,T+timedelta(days=5),T+timedelta(days=9),0,0,"validation",T)
    plan=WalkForwardPlan("future-plan",data.dataset_id,data.dataset_version,"nse","v1",WalkForwardMode.ROLLING,5,2,5,12,0,0,1,"calendar",T,(),manifest_fingerprint(plan="package")); repo.save_walk_forward_plan(plan)
    window=WalkForwardWindow("package-window",plan.plan_id,1,train,validation,test,candidate.candidate_id,WalkForwardStatus.PLANNED,(),manifest_fingerprint(window="package"),selection.selection_id,selection.selection_timestamp,candidate.fingerprint); repo.save_walk_forward_window(window)
    run=WalkForwardRun("package-run",plan.plan_id,(window.window_id,),(candidate.candidate_id,),"research","1","v1",WalkForwardRunStatus.PLANNED,T,None,(),manifest_fingerprint(run="package")); repo.save_walk_forward_run(run)
    policy=FutureOOSAssignmentPolicy("package-policy","1",3600,(plan.plan_id,),False,1,None,"v1",""); policy=replace(policy,fingerprint=future_oos_assignment_policy_fingerprint(policy)); repo.save_future_oos_assignment_policy(policy)
    assignment=FutureOOSAssignment("package-assignment",queue.queue_id,selection.selection_id,candidate.candidate_id,plan.plan_id,window.window_id,test.partition_id,T+timedelta(days=10,hours=1),test.start,test.end,candidate.fingerprint,policy.policy_id,policy.version,FutureOOSAssignmentStatus.ASSIGNED,(),""); assignment=replace(assignment,fingerprint=future_oos_assignment_fingerprint(assignment)); repo.save_future_oos_assignment(assignment)
    result=WalkForwardWindowResult("package-window-result",run.run_id,window.window_id,candidate.candidate_id,candidate.fingerprint,selection.evidence_ids,selection.selection_timestamp,"research","1",OOSStartingCapitalMethodology.INDEPENDENT_WINDOW_CAPITAL,None,None,None,test.start,test.end,Decimal("1000"),Decimal("1000"),Decimal("0"),None,None,None,None,None,None,0,Decimal("0"),WalkForwardWindowResultStatus.COMPLETED,("BENCHMARK_UNAVAILABLE","ZERO_TRADES"),manifest_fingerprint(result="package")); repo.save_walk_forward_window_result(result)
    execution=FutureOOSExecutionResult("package-execution",assignment.assignment_id,None,result.result_id,None,None,FutureOOSExecutionStatus.COMPLETED_WITH_WARNINGS,result.warnings,test.end,""); execution=replace(execution,fingerprint=future_oos_execution_fingerprint(execution)); repo.save_future_oos_execution_result(execution)
    return repo,selection,assignment,result,execution


def test_single_window_evidence_package_is_frozen_and_has_no_governance_side_effect(tmp_path):
    repo,selection,assignment,result,execution=packaged_fixture(tmp_path)
    record,package=FutureOOSEvidencePackagingService(repo).package(selection_id=selection.selection_id,generated_at=T+timedelta(days=20))
    assert record.assignment_ids==(assignment.assignment_id,) and record.execution_result_ids==(execution.execution_result_id,) and record.window_result_ids==(result.result_id,)
    assert record.completed_window_count==1 and record.valid_window_count==1 and record.insufficient_window_count==0 and record.failed_window_count==0
    assert repo.get_promotion_evidence_package(package.package_id)==package and repo.get_research_candidate_oos_record(record.record_id)==record
    assert repo.get_strategy_promotion_proposal("not-created") is None
    with pytest.raises(ValueError): repo.save_promotion_evidence_package(package)


def test_package_audit_fails_closed_when_frozen_assignment_linkage_is_tampered(tmp_path):
    repo,selection,assignment,result,execution=packaged_fixture(tmp_path); _,package=FutureOOSEvidencePackagingService(repo).package(selection_id=selection.selection_id,generated_at=T+timedelta(days=20))
    payload=repo._connection.execute("SELECT payload_json FROM future_oos_assignments WHERE id=?",(assignment.assignment_id,)).fetchone()["payload_json"].replace('"candidate_fingerprint":"'+assignment.candidate_fingerprint+'"','"candidate_fingerprint":"tampered"')
    repo._connection.execute("UPDATE future_oos_assignments SET payload_json=? WHERE id=?",(payload,assignment.assignment_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_promotion_evidence_package(package.package_id)


@pytest.mark.parametrize("field,replacement",[("candidate_fingerprint","tampered"),("assignment_ids","[]"),("coverage_status","OOS_EVIDENCE_FAILED_AUDIT")])
def test_package_tamper_matrix_fails_closed(tmp_path,field,replacement):
    repo,selection,_,_,_=packaged_fixture(tmp_path); _,package=FutureOOSEvidencePackagingService(repo).package(selection_id=selection.selection_id,generated_at=T+timedelta(days=20))
    payload=repo._connection.execute("SELECT payload_json FROM promotion_evidence_packages WHERE id=?",(package.package_id,)).fetchone()["payload_json"]
    import json
    changed=json.loads(payload); changed[field]=json.loads(replacement) if replacement.startswith("[") else replacement
    repo._connection.execute("UPDATE promotion_evidence_packages SET payload_json=? WHERE id=?",(json.dumps(changed),package.package_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_promotion_evidence_package(package.package_id)


def test_future_policy_and_selection_leak_cannot_rewrite_existing_package(tmp_path):
    repo,selection,_,_,_=packaged_fixture(tmp_path); _,package=FutureOOSEvidencePackagingService(repo).package(selection_id=selection.selection_id,generated_at=T+timedelta(days=20)); frozen=repo.get_promotion_evidence_package(package.package_id)
    later=FutureOOSAssignmentPolicy("package-policy-v2","2",7200,("future-plan",),False,1,None,"v2",""); later=replace(later,fingerprint=future_oos_assignment_policy_fingerprint(later)); repo.save_future_oos_assignment_policy(later)
    assert repo.get_promotion_evidence_package(package.package_id)==frozen
    payload=repo._connection.execute("SELECT payload_json FROM candidate_selection_results WHERE id=?",(selection.selection_id,)).fetchone()["payload_json"].replace('"evidence_ids":[','"evidence_ids":["future-oos-result",')
    repo._connection.execute("UPDATE candidate_selection_results SET payload_json=? WHERE id=?",(payload,selection.selection_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError): AuditReconstructionService(repo).reconstruct_promotion_evidence_package(package.package_id)


def test_sequential_positive_negative_windows_use_canonical_aggregate_and_remain_packaged(tmp_path):
    repo,selection,assignment,first,first_execution=packaged_fixture(tmp_path); candidate=repo.get_strategy_candidate(selection.selected_candidate_id); plan=repo.get_walk_forward_plan("future-plan")
    second_test=HistoricalPartition("package-test-2",plan.dataset_id,PartitionType.TEST,first.test_end+timedelta(days=1),first.test_end+timedelta(days=5),0,0,"future test 2",T)
    second_window=WalkForwardWindow("package-window-2",plan.plan_id,2,repo.get_walk_forward_window(first.walk_forward_window_id).train,repo.get_walk_forward_window(first.walk_forward_window_id).validation,second_test,candidate.candidate_id,WalkForwardStatus.PLANNED,(),manifest_fingerprint(window="package-2"),selection.selection_id,selection.selection_timestamp,candidate.fingerprint); repo.save_walk_forward_window(second_window)
    old_run=repo.get_walk_forward_run("package-run"); run=replace(old_run,run_id="package-run-2",ordered_window_ids=(first.walk_forward_window_id,second_window.window_id),fingerprint=manifest_fingerprint(run="package-2")); repo.save_walk_forward_run(run)
    first_for_run=replace(first,result_id="package-window-result-1",walk_forward_run_id=run.run_id,absolute_return=Decimal(".10"),fingerprint=manifest_fingerprint(result="package-1")); repo.save_walk_forward_window_result(first_for_run)
    first_execution=replace(first_execution,walk_forward_window_result_id=first_for_run.result_id); first_execution=replace(first_execution,fingerprint=future_oos_execution_fingerprint(first_execution)); import json; from app.self_improvement.serialization import dump; repo._connection.execute("UPDATE future_oos_execution_results SET payload_json=? WHERE id=?",(json.dumps(dump(first_execution)),first_execution.execution_result_id)); repo._connection.commit()
    policy=FutureOOSAssignmentPolicy("package-policy-multi","1",3600,(plan.plan_id,),True,2,None,"v1",""); policy=replace(policy,fingerprint=future_oos_assignment_policy_fingerprint(policy)); repo.save_future_oos_assignment_policy(policy)
    second_assignment=FutureOOSAssignment("package-assignment-2",assignment.queue_id,selection.selection_id,candidate.candidate_id,plan.plan_id,second_window.window_id,second_test.partition_id,T+timedelta(days=10,hours=1),second_test.start,second_test.end,candidate.fingerprint,policy.policy_id,policy.version,FutureOOSAssignmentStatus.ASSIGNED,(),""); second_assignment=replace(second_assignment,fingerprint=future_oos_assignment_fingerprint(second_assignment)); repo.save_future_oos_assignment(second_assignment)
    second_result=replace(first_for_run,result_id="package-window-result-2",walk_forward_window_id=second_window.window_id,test_start=second_test.start,test_end=second_test.end,absolute_return=Decimal("-.10"),fingerprint=manifest_fingerprint(result="package-2")); repo.save_walk_forward_window_result(second_result)
    execution=FutureOOSExecutionResult("package-execution-2",second_assignment.assignment_id,None,second_result.result_id,None,None,FutureOOSExecutionStatus.COMPLETED,(),second_test.end,""); execution=replace(execution,fingerprint=future_oos_execution_fingerprint(execution)); repo.save_future_oos_execution_result(execution)
    config=WalkForwardValidationConfig("package-aggregate-config","1",1,1,Decimal(".5"),1,0,None,None,None,None,"v1",manifest_fingerprint(config="package")); aggregate=WalkForwardAggregationService(repo).aggregate(run_id=run.run_id,config=config,generated_at=T+timedelta(days=30))
    record,package=FutureOOSEvidencePackagingService(repo).package(selection_id=selection.selection_id,generated_at=T+timedelta(days=31),aggregate_result_id=aggregate.aggregate_result_id)
    assert record.window_result_ids==(first_for_run.result_id,second_result.result_id) and aggregate.ordered_window_result_ids==record.window_result_ids and package.aggregate_result_id==aggregate.aggregate_result_id
    assert first_for_run.absolute_return>0 and second_result.absolute_return<0 and repo.get_walk_forward_window_result(first_for_run.result_id)==first_for_run
