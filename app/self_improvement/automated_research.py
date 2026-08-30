"""Non-OOS automated research over already human-approved experiment drafts."""
from datetime import datetime

from app.backtest.experiments import CandidateSelectionPolicy, ControlledCandidateExperimentService, ExperimentStatus
from app.historical.guard import manifest_fingerprint
from app.historical.models import PartitionType
from .models import AutomatedResearchCycleResult, AutomatedResearchRun, AutomatedResearchRunStatus, FutureOOSCandidateQueueEntry, FutureOOSQueueStatus, HypothesisReviewDecision


class AutomatedResearchCycleService:
    """Executes only injected canonical TRAIN/VALIDATION adapters; never TEST/OOS."""
    def __init__(self, repository, executor): self.repository=repository; self.executor=executor

    def execute(self, *, experiment_id: str, link_id: str, selection_policy: CandidateSelectionPolicy, train_partitions: tuple, validation_partitions: tuple, current_approved_strategy_id: str, started_at: datetime, completed_at: datetime, target_plan_id: str | None = None, target_window_family: str | None = None, earliest_test_timestamp: datetime | None = None):
        experiment=self.repository.get_strategy_experiment(experiment_id); link=self.repository.get_hypothesis_experiment_link(link_id); budget=self.repository.get_experiment_budget(experiment.budget_id) if experiment else None
        if experiment is None or link is None or budget is None or experiment.status is not ExperimentStatus.PLANNED or link.experiment_id!=experiment_id: raise ValueError("Automated research requires an existing human-approved PLANNED experiment and frozen bridge link.")
        hypothesis=self.repository.get_strategy_improvement_hypothesis(link.hypothesis_id);review=self.repository.get_hypothesis_review(link.review_id)
        if hypothesis is None or review is None or review.decision is not HypothesisReviewDecision.APPROVE_FOR_EXPERIMENT or not review.reviewer_id.startswith("human:") or review.evidence_fingerprint!=hypothesis.evidence_fingerprint or link.target_approved_strategy_id!=current_approved_strategy_id: raise ValueError("Automated research experiment is stale or lacks exact human approval.")
        if not train_partitions or not validation_partitions or any(partition.partition_type is PartitionType.TEST for partition in (*train_partitions,*validation_partitions)) or any(partition.partition_id not in experiment.permitted_partition_ids for partition in (*train_partitions,*validation_partitions)) or any(partition.partition_id in experiment.forbidden_test_partition_ids for partition in (*train_partitions,*validation_partitions)):
            raise ValueError("Automated research accepts only explicitly permitted TRAIN and VALIDATION partitions; TEST is forbidden.")
        if any(partition.partition_type is not PartitionType.TRAIN for partition in train_partitions) or any(partition.partition_type is not PartitionType.VALIDATION for partition in validation_partitions) or max(partition.end for partition in train_partitions)>=min(partition.start for partition in validation_partitions): raise ValueError("Research partitions violate frozen TRAIN/VALIDATION chronology.")
        self.repository.save_candidate_selection_policy(selection_policy) if self.repository.get_candidate_selection_policy(selection_policy.policy_id) is None else None
        candidates=tuple(self.repository.get_strategy_candidate(identifier) for identifier in (experiment.baseline_candidate_id,*experiment.experimental_candidate_ids))
        if any(candidate is None for candidate in candidates): raise ValueError("Automated research requires complete frozen candidate snapshots.")
        seed=manifest_fingerprint(experiment=experiment.fingerprint,link=link.fingerprint,policy=selection_policy.fingerprint,train=[partition.partition_id for partition in train_partitions],validation=[partition.partition_id for partition in validation_partitions],started=started_at)
        run=AutomatedResearchRun("automated-research-"+seed[:24],experiment.experiment_id,link.link_id,experiment.baseline_candidate_id,experiment.experimental_candidate_ids,tuple(partition.partition_id for partition in train_partitions),tuple(partition.partition_id for partition in validation_partitions),experiment.forbidden_test_partition_ids,budget.budget_id,budget.version,selection_policy.policy_id,selection_policy.version,"automated-research-v1",started_at,completed_at,AutomatedResearchRunStatus.COMPLETED,(),manifest_fingerprint(seed=seed,status="COMPLETED"))
        evidence=[]
        for partition in (*train_partitions,*validation_partitions):
            for candidate in candidates:
                item=self.executor(candidate,partition,experiment)
                if item.experiment_id!=experiment.experiment_id or item.candidate_id!=candidate.candidate_id or item.partition_id!=partition.partition_id or item.partition_type is PartitionType.TEST or item.partition_type is not partition.partition_type: raise ValueError("Canonical research executor returned invalid or TEST evidence.")
                existing=next((value for value in self.repository.list_candidate_evaluation_evidence(experiment.experiment_id) if value.evidence_id==item.evidence_id),None)
                if existing is None:self.repository.save_candidate_evaluation_evidence(item)
                elif existing!=item:raise ValueError("Frozen candidate evidence cannot be overwritten.")
                evidence.append(item)
        robustness=[]
        engine=ControlledCandidateExperimentService(self.repository)
        for candidate in candidates:
            values=tuple(value for value in evidence if value.candidate_id==candidate.candidate_id)
            result=engine.robustness(experiment_id=experiment.experiment_id,candidate_id=candidate.candidate_id,neighboring_candidate_ids=tuple(value.candidate_id for value in candidates if value.candidate_id!=candidate.candidate_id),evidence=values,knife_edge=None)
            self.repository.save_candidate_robustness_result(result) if self.repository.get_candidate_robustness_result(result.robustness_id) is None else None; robustness.append(result)
        self.repository.save_automated_research_run(run)
        selection=engine.select(experiment_id=experiment.experiment_id,policy=selection_policy,selection_timestamp=completed_at,robustness_results=tuple(robustness))
        queue=None
        if selection.selected_candidate_id is not None:
            if target_plan_id is None or target_window_family is None or earliest_test_timestamp is None or earliest_test_timestamp<=completed_at: raise ValueError("Selected research candidate requires a strictly future OOS queue target.")
            candidate=self.repository.get_strategy_candidate(selection.selected_candidate_id); queue_seed=manifest_fingerprint(selection=selection.fingerprint,candidate=candidate.fingerprint,plan=target_plan_id,family=target_window_family,test=earliest_test_timestamp)
            queue=FutureOOSCandidateQueueEntry("future-oos-queue-"+queue_seed[:24],selection.selection_id,selection.selected_candidate_id,target_plan_id,target_window_family,earliest_test_timestamp,selection.selection_timestamp,candidate.fingerprint,FutureOOSQueueStatus.QUEUED,(),queue_seed)
            self.repository.save_future_oos_candidate_queue_entry(queue)
        cycle=AutomatedResearchCycleResult("automated-research-cycle-"+seed[:24],run.research_run_id,tuple(value.evidence_id for value in evidence if value.partition_type is PartitionType.TRAIN),tuple(value.evidence_id for value in evidence if value.partition_type is PartitionType.VALIDATION),tuple(value.robustness_id for value in robustness),selection.selection_id,queue.queue_id if queue else None,run.status,(),manifest_fingerprint(seed=seed,evidence=[value.fingerprint for value in evidence],robustness=[value.fingerprint for value in robustness],selection=selection.fingerprint,queue=queue.fingerprint if queue else None))
        self.repository.save_automated_research_cycle_result(cycle)
        return run,tuple(evidence),tuple(robustness),selection,queue,cycle
