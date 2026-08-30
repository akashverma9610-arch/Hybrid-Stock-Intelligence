"""Immutable, non-promoting package of frozen future-OOS evidence."""
from dataclasses import replace
from datetime import datetime

from app.backtest.walk_forward import WalkForwardWindowResultStatus
from app.historical.guard import manifest_fingerprint
from .models import OOSCoverageStatus, PromotionEvidencePackage, ResearchCandidateOOSRecord, promotion_evidence_package_fingerprint


class FutureOOSEvidencePackagingService:
    methodology_version="future-oos-evidence-package-v1"
    def __init__(self, repository): self.repository=repository

    def package(self, *, selection_id: str, generated_at: datetime, aggregate_result_id: str | None=None, persist: bool=True):
        selection=self.repository.get_candidate_selection_result(selection_id); assignments=self.repository.list_future_oos_assignments(selection_id); executions=self.repository.list_future_oos_execution_results(selection_id)
        if selection is None or selection.selected_candidate_id is None or not assignments or len(assignments)!=len(executions): raise ValueError("Evidence package requires every queued assignment to have one terminal frozen execution result.")
        candidate=self.repository.get_strategy_candidate(selection.selected_candidate_id); experiment=self.repository.get_strategy_experiment(selection.experiment_id)
        if candidate is None or experiment is None or any(item.selected_candidate_id!=candidate.candidate_id or item.candidate_fingerprint!=candidate.fingerprint for item in assignments): raise ValueError("Evidence package candidate lineage is incomplete or inconsistent.")
        results=tuple(self.repository.get_walk_forward_window_result(item.walk_forward_window_result_id) for item in executions)
        if any(item is None for item in results): raise ValueError("Evidence package has a missing canonical OOS window result.")
        results=tuple(results)
        if any(item.selected_candidate_id!=candidate.candidate_id or item.selected_candidate_fingerprint!=candidate.fingerprint for item in results): raise ValueError("Evidence package mixes candidate or configuration histories.")
        if any(current.test_start<=prior.test_end for prior,current in zip(results,results[1:])): raise ValueError("Evidence package cannot double-count overlapping OOS TEST windows.")
        run=next((item for item in self.repository.list_automated_research_runs() if item.experiment_id==experiment.experiment_id),None)
        if run is None: raise ValueError("Evidence package is missing the frozen automated research run.")
        link=self.repository.get_hypothesis_experiment_link(run.hypothesis_experiment_link_id); hypothesis=self.repository.get_strategy_improvement_hypothesis(link.hypothesis_id) if link else None; review=self.repository.get_hypothesis_review(link.review_id) if link else None; source_run=self.repository.get_self_improvement_run(link.run_id) if link else None; baseline=self.repository.get_strategy_candidate(experiment.baseline_candidate_id)
        if None in (link,hypothesis,review,source_run,baseline) or link.experiment_id!=experiment.experiment_id: raise ValueError("Evidence package research provenance is incomplete.")
        robustness=tuple(selection.robustness_result_ids); status=self._coverage(results); benchmark=tuple(item.benchmark_comparison_id for item in results if item.benchmark_comparison_id is not None)
        record=ResearchCandidateOOSRecord("research-candidate-oos-"+manifest_fingerprint(selection=selection.fingerprint,assignments=[item.fingerprint for item in assignments])[:24],selection.selection_id,candidate.candidate_id,candidate.fingerprint,tuple(item.assignment_id for item in assignments),tuple(item.execution_result_id for item in executions),tuple(item.result_id for item in results),aggregate_result_id,len(assignments),len(executions),sum(item.status in {WalkForwardWindowResultStatus.COMPLETED,WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS} for item in results),sum(item.status is WalkForwardWindowResultStatus.INSUFFICIENT for item in results),sum(item.status in {WalkForwardWindowResultStatus.FAILED,WalkForwardWindowResultStatus.FAILED_AUDIT} for item in results),len(benchmark),status,tuple(sorted({warning for item in results for warning in item.warnings})),manifest_fingerprint(selection=selection.fingerprint,results=[item.fingerprint for item in results],aggregate=aggregate_result_id,status=status.value))
        package=PromotionEvidencePackage("promotion-evidence-"+manifest_fingerprint(record=record.fingerprint,run=run.fingerprint)[:24],candidate.candidate_id,baseline.candidate_id,baseline.fingerprint,source_run.run_id,hypothesis.hypothesis_id,review.review_id,link.link_id,experiment.experiment_id,run.research_run_id,selection.selection_id,tuple(item.queue_id for item in assignments),record.assignment_ids,record.execution_result_ids,record.window_result_ids,aggregate_result_id,robustness,benchmark,candidate.fingerprint,status,record.warnings,generated_at,self.methodology_version,"")
        package=replace(package,fingerprint=promotion_evidence_package_fingerprint(package))
        if persist:
            self.repository.save_research_candidate_oos_record(record); self.repository.save_promotion_evidence_package(package)
        return record,package

    @staticmethod
    def _coverage(results):
        if any(item.status is WalkForwardWindowResultStatus.FAILED_AUDIT for item in results): return OOSCoverageStatus.OOS_EVIDENCE_FAILED_AUDIT
        if any(item.status is WalkForwardWindowResultStatus.FAILED for item in results): return OOSCoverageStatus.OOS_EVIDENCE_DEGRADED
        if not any(item.status in {WalkForwardWindowResultStatus.COMPLETED,WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS} for item in results): return OOSCoverageStatus.OOS_EVIDENCE_INSUFFICIENT
        return OOSCoverageStatus.OOS_EVIDENCE_ACCUMULATING
