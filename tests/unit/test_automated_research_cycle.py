from datetime import UTC, datetime, timedelta
from dataclasses import replace
from decimal import Decimal

import pytest

from app.backtest.experiments import CandidateEvaluationEvidence, CandidateSelectionPolicy, ExperimentBudget, ExperimentStatus, StrategyCandidateDelta, StrategyExperiment
from app.backtest.promotion import ApprovedStrategyStatus, ApprovedStrategyVersion, PromotionProposalStatus, ReviewDecision, StrategyPromotionProposal, StrategyPromotionReview
from app.backtest.walk_forward import StrategyCandidate
from app.historical.guard import manifest_fingerprint
from app.historical.models import HistoricalPartition, PartitionType
from app.self_improvement.automated_research import AutomatedResearchCycleService
from app.self_improvement.models import *
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository

T=datetime(2026,11,1,tzinfo=UTC)

def setup(repository):
    run=SelfImprovementRun("research-source","strategy-2.1",T,T+timedelta(days=20),(),(),(),(),(),"v1",T,"COMPLETE",(),manifest_fingerprint(run="source")); repository.save_self_improvement_run(run)
    generation=HypothesisGenerationPolicy("generation","1",Decimal("1"),1,1,False,"v1",manifest_fingerprint(generation="1")); repository.save_hypothesis_generation_policy(generation)
    proposal=StrategyPromotionProposal("proposal","candidate","strategy","2.1","experiment","selection",(),(),(),(),(),"",T,PromotionProposalStatus.READY_FOR_REVIEW,(),manifest_fingerprint(proposal="1")); review=StrategyPromotionReview("promotion-review",proposal.proposal_id,"human:promoter",T,ReviewDecision.APPROVE,"",(),"1","",manifest_fingerprint(review="1")); target=ApprovedStrategyVersion("approved","strategy","2.1",None,proposal.proposal_id,review.review_id,"candidate",(),T,T,ApprovedStrategyStatus.APPROVED,(),manifest_fingerprint(target="1")); repository.save_strategy_promotion_proposal(proposal); repository.save_strategy_promotion_review(review); repository.save_approved_strategy_version(target)
    hypothesis=StrategyImprovementHypothesis("hypothesis",run.run_id,target.approved_id,target.version,"Volume threshold","",(),("a1",),(),"FALSE_BREAKOUT",HypothesisType.THRESHOLD_ADJUSTMENT,ConfigurableTargetDomain.SIGNAL,"volume_confirmation_threshold","STRICTER","mechanism","benefit","downside",(),(),PatternEvidenceStatus.ELIGIBLE,"MODERATE","LOW",T,(),"evidence",generation.policy_id,generation.version,manifest_fingerprint(hypothesis="1")); repository.save_strategy_improvement_hypothesis(hypothesis)
    human=HypothesisReview("human-review",hypothesis.hypothesis_id,"human:owner",T,HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT,"EXPERIMENT_VALUE=1.2",hypothesis.evidence_fingerprint,(),""); human=__import__("dataclasses").replace(human,fingerprint=hypothesis_review_fingerprint(human)); repository.save_hypothesis_review(human)
    budget=ExperimentBudget("budget","1",1,1,{"volume_confirmation_threshold":(Decimal(".5"),Decimal("2"))},2,"v1",manifest_fingerprint(budget="1")); repository.save_experiment_budget(budget)
    baseline=StrategyCandidate("baseline","strategy-2.1","r","s","g","rot","sig","paper","alloc","perf",manifest_fingerprint(candidate="base")); variant=__import__("dataclasses").replace(baseline,candidate_id="variant",fingerprint=manifest_fingerprint(candidate="variant")); repository.save_strategy_candidate(baseline); repository.save_strategy_candidate(variant)
    experiment=StrategyExperiment("experiment","volume","HYPOTHESIS_ID:hypothesis",baseline.candidate_id,(variant.candidate_id,),"dataset","1",("train","validation"),("test",),budget.budget_id,"v1",T,ExperimentStatus.PLANNED,(),manifest_fingerprint(experiment="1")); delta=StrategyCandidateDelta("delta",variant.candidate_id,"volume_confirmation_threshold","1.0","1.2","mechanism",manifest_fingerprint(delta="1"),experiment.experiment_id); repository.save_strategy_experiment(experiment); repository.save_strategy_candidate_delta(delta)
    link=HypothesisExperimentLink("link",run.run_id,hypothesis.hypothesis_id,human.review_id,experiment.experiment_id,(delta.delta_id,),baseline.candidate_id,target.approved_id,target.version,budget.budget_id,budget.version,T,(),manifest_fingerprint(link="1")); repository.save_hypothesis_experiment_link(link)
    policy=CandidateSelectionPolicy("selection","1",1,Decimal(".1"),Decimal(".1"),Decimal("1"),Decimal("10"),Decimal(".1"),None,"v1",manifest_fingerprint(policy="1"))
    train=HistoricalPartition("train","dataset",PartitionType.TRAIN,T,T+timedelta(days=4),0,0,"train",T); validation=HistoricalPartition("validation","dataset",PartitionType.VALIDATION,T+timedelta(days=5),T+timedelta(days=9),0,0,"validation",T); test=HistoricalPartition("test","dataset",PartitionType.TEST,T+timedelta(days=10),T+timedelta(days=15),0,0,"test",T)
    return target,experiment,link,policy,train,validation,test

def test_automated_research_uses_only_train_validation_and_queues_future_oos(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"research.db"); target,experiment,link,policy,train,validation,test=setup(repository)
    def executor(candidate,partition,exp):
        better=candidate.candidate_id=="variant"; return CandidateEvaluationEvidence(f"e-{candidate.candidate_id}-{partition.partition_id}",exp.experiment_id,candidate.candidate_id,partition.partition_type,partition.partition_id,f"backtest-{candidate.candidate_id}-{partition.partition_id}",f"report-{candidate.candidate_id}-{partition.partition_id}",None,partition.end,2,Decimal(".2"),Decimal("-.1"),Decimal(".8") if better else Decimal(".4"),Decimal(".8") if better else Decimal(".4"),Decimal(".8") if better else Decimal(".2"),Decimal("2"),Decimal("1"),"COMPLETED",(),manifest_fingerprint(candidate=candidate.candidate_id,partition=partition.partition_id))
    service=AutomatedResearchCycleService(repository,executor)
    research,evidence,robustness,selection,queue,cycle=service.execute(experiment_id=experiment.experiment_id,link_id=link.link_id,selection_policy=policy,train_partitions=(train,),validation_partitions=(validation,),current_approved_strategy_id=target.approved_id,started_at=T,completed_at=T+timedelta(days=10),target_plan_id="future-plan",target_window_family="future-family",earliest_test_timestamp=T+timedelta(days=11))
    assert len(evidence)==4 and all(item.partition_type is not PartitionType.TEST for item in evidence)
    assert selection.selected_candidate_id=="variant" and queue is not None and queue.earliest_test_timestamp>selection.selection_timestamp
    assert repository.get_automated_research_run(research.research_run_id)==research and repository.get_automated_research_cycle_result(cycle.cycle_result_id)==cycle
    with pytest.raises(ValueError,match="TEST"):
        service.execute(experiment_id=experiment.experiment_id,link_id=link.link_id,selection_policy=policy,train_partitions=(test,),validation_partitions=(validation,),current_approved_strategy_id=target.approved_id,started_at=T,completed_at=T+timedelta(days=10))


def _queued_candidate(repository):
    target,experiment,link,policy,train,validation,_=setup(repository)
    def executor(candidate,partition,exp):
        better=candidate.candidate_id=="variant"; return CandidateEvaluationEvidence(f"e-{candidate.candidate_id}-{partition.partition_id}",exp.experiment_id,candidate.candidate_id,partition.partition_type,partition.partition_id,f"backtest-{candidate.candidate_id}-{partition.partition_id}",f"report-{candidate.candidate_id}-{partition.partition_id}",None,partition.end,2,Decimal(".2"),Decimal("-.1"),Decimal(".8") if better else Decimal(".4"),Decimal(".8") if better else Decimal(".4"),Decimal(".8") if better else Decimal(".2"),Decimal("2"),Decimal("1"),"COMPLETED",(),manifest_fingerprint(candidate=candidate.candidate_id,partition=partition.partition_id))
    _,_,_,selection,queue,_=AutomatedResearchCycleService(repository,executor).execute(experiment_id=experiment.experiment_id,link_id=link.link_id,selection_policy=policy,train_partitions=(train,),validation_partitions=(validation,),current_approved_strategy_id=target.approved_id,started_at=T,completed_at=T+timedelta(days=10),target_plan_id="future-plan",target_window_family="future-family",earliest_test_timestamp=T+timedelta(days=11))
    assert queue is not None
    return target,selection,queue


def _assignment_policy(identifier="assignment-policy", *, expiration_seconds=None, allow_multiple_windows=False, maximum_concurrent_assignments=1):
    value=FutureOOSAssignmentPolicy(identifier,"1",3600,("future-plan",),allow_multiple_windows,maximum_concurrent_assignments,expiration_seconds,"future-oos-assignment-v1","")
    return replace(value,fingerprint=future_oos_assignment_policy_fingerprint(value))


def _assignment(queue, policy, *, identifier="assignment", assigned_at=None, test_start=None, candidate_fingerprint=None):
    assigned_at=assigned_at or queue.selection_timestamp+timedelta(hours=1)
    test_start=test_start or queue.earliest_test_timestamp
    value=FutureOOSAssignment(identifier,queue.queue_id,queue.selection_id,queue.selected_candidate_id,"future-plan","window-1","test-1",assigned_at,test_start,test_start+timedelta(days=5),candidate_fingerprint or queue.candidate_fingerprint,policy.policy_id,policy.version,FutureOOSAssignmentStatus.ASSIGNED,(),"")
    return replace(value,fingerprint=future_oos_assignment_fingerprint(value))


def test_future_oos_assignment_policy_and_assignment_round_trip_are_insert_only(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"future-oos.db"); target,_,queue=_queued_candidate(repository)
    policy=_assignment_policy(); repository.save_future_oos_assignment_policy(policy)
    assignment=_assignment(queue,policy); repository.save_future_oos_assignment(assignment)
    assert repository.get_future_oos_assignment_policy(policy.policy_id)==policy
    assert repository.get_future_oos_assignment(assignment.assignment_id)==assignment
    with pytest.raises(ValueError): repository.save_future_oos_assignment_policy(replace(policy,methodology_version="changed"))
    with pytest.raises(ValueError): repository.save_future_oos_assignment(replace(assignment,warnings=("changed",),fingerprint="bad"))
    repository.save_future_oos_assignment_policy(_assignment_policy("assignment-policy-v2"))
    assert repository.get_future_oos_assignment(assignment.assignment_id)==assignment
    assert repository.get_approved_strategy_version(target.approved_id)==target


def test_future_oos_assignment_fails_closed_for_chronology_expiration_and_frozen_candidate(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"future-oos-guards.db"); _,_,queue=_queued_candidate(repository)
    policy=_assignment_policy("guard-policy",expiration_seconds=60); repository.save_future_oos_assignment_policy(policy)
    with pytest.raises(ValueError,match="chronology"):
        repository.save_future_oos_assignment(_assignment(queue,policy,identifier="same-time",assigned_at=queue.earliest_test_timestamp))
    with pytest.raises(ValueError,match="chronology"):
        repository.save_future_oos_assignment(_assignment(queue,policy,identifier="too-early",test_start=queue.earliest_test_timestamp-timedelta(seconds=1)))
    with pytest.raises(ValueError,match="expired"):
        repository.save_future_oos_assignment(_assignment(queue,policy,identifier="expired",assigned_at=queue.selection_timestamp+timedelta(hours=2)))
    with pytest.raises(ValueError,match="frozen queue"):
        repository.save_future_oos_assignment(_assignment(queue,policy,identifier="wrong-candidate",candidate_fingerprint="not-the-frozen-config"))
    stale=replace(queue,queue_id="stale-queue",status=FutureOOSQueueStatus.STALE); repository.save_future_oos_candidate_queue_entry(stale)
    with pytest.raises(ValueError,match="frozen queue"):
        repository.save_future_oos_assignment(_assignment(stale,policy,identifier="stale"))


def test_future_oos_assignment_allows_only_policy_permitted_distinct_future_windows(tmp_path):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"future-oos-multiple.db"); _,_,queue=_queued_candidate(repository)
    policy=_assignment_policy("multi-policy",allow_multiple_windows=True,maximum_concurrent_assignments=2); repository.save_future_oos_assignment_policy(policy)
    first=_assignment(queue,policy,identifier="window-one"); repository.save_future_oos_assignment(first)
    second=_assignment(queue,policy,identifier="window-two",test_start=queue.earliest_test_timestamp+timedelta(days=7)); second=replace(second,window_id="window-2",test_partition_id="test-2"); second=replace(second,fingerprint=future_oos_assignment_fingerprint(second)); repository.save_future_oos_assignment(second)
    assert repository.get_future_oos_assignment(first.assignment_id)==first and repository.get_future_oos_assignment(second.assignment_id)==second
    duplicate=replace(second,assignment_id="same-window"); duplicate=replace(duplicate,fingerprint=future_oos_assignment_fingerprint(duplicate))
    with pytest.raises(ValueError,match="maximum concurrent|active assignment path"):
        repository.save_future_oos_assignment(duplicate)


@pytest.mark.parametrize("status",(FutureOOSQueueStatus.EXPIRED,FutureOOSQueueStatus.STALE,FutureOOSQueueStatus.CANCELLED))
def test_non_queued_future_oos_lifecycle_entries_cannot_be_assigned_or_revived(tmp_path,status):
    repository=SQLiteStrategyGovernanceRepository(tmp_path/"future-oos-lifecycle.db"); _,_,queue=_queued_candidate(repository); policy=_assignment_policy("lifecycle-policy"); repository.save_future_oos_assignment_policy(policy)
    terminal=replace(queue,queue_id=f"{status.value}-queue",status=status); repository.save_future_oos_candidate_queue_entry(terminal)
    value=_assignment(terminal,policy,identifier=f"{status.value}-assignment")
    with pytest.raises(ValueError,match="frozen queue"):
        repository.save_future_oos_assignment(value)
    assert repository.get_future_oos_candidate_queue_entry(terminal.queue_id)==terminal
