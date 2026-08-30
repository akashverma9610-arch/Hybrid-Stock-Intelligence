from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from statistics import pstdev

from app.historical.guard import manifest_fingerprint
from app.historical.models import PartitionType


class ExperimentStatus(str, Enum): PLANNED="PLANNED"; RUNNING="RUNNING"; COMPLETED="COMPLETED"; INCONCLUSIVE="INCONCLUSIVE"; INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE"; FAILED_AUDIT="FAILED_AUDIT"
class CandidateSelectionStatus(str, Enum): BASELINE_RETAINED="BASELINE_RETAINED"; CANDIDATE_SELECTED="CANDIDATE_SELECTED"; INCONCLUSIVE="INCONCLUSIVE"; INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE"
class RobustnessStatus(str, Enum): ROBUST="ROBUST"; FRAGILE="FRAGILE"; INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE"

@dataclass(frozen=True, slots=True)
class ExperimentBudget:
    budget_id:str; version:str; maximum_candidate_count:int; maximum_changed_parameters:int; permitted_ranges:dict[str,tuple[Decimal,Decimal]]; maximum_repeated_evaluations:int; methodology_version:str; fingerprint:str
@dataclass(frozen=True, slots=True)
class StrategyCandidateDelta:
    delta_id:str; candidate_id:str; changed_field:str; baseline_value:str; experimental_value:str; rationale:str; fingerprint:str; experiment_id:str=""
@dataclass(frozen=True, slots=True)
class StrategyExperiment:
    experiment_id:str; name:str; hypothesis:str; baseline_candidate_id:str; experimental_candidate_ids:tuple[str,...]; dataset_id:str; dataset_version:str; permitted_partition_ids:tuple[str,...]; forbidden_test_partition_ids:tuple[str,...]; budget_id:str; methodology_version:str; created_at:datetime; status:ExperimentStatus; warnings:tuple[str,...]; fingerprint:str
@dataclass(frozen=True, slots=True)
class CandidateEvaluationEvidence:
    evidence_id:str; experiment_id:str; candidate_id:str; partition_type:PartitionType; partition_id:str; backtest_run_id:str; performance_report_id:str; benchmark_comparison_id:str|None; evaluated_at:datetime; trade_count:int; return_value:Decimal|None; drawdown:Decimal|None; sharpe:Decimal|None; sortino:Decimal|None; expectancy:Decimal|None; profit_factor:Decimal|None; costs:Decimal|None; status:str; warnings:tuple[str,...]; fingerprint:str
@dataclass(frozen=True, slots=True)
class CandidateRobustnessResult:
    robustness_id:str; experiment_id:str; candidate_id:str; neighboring_candidate_ids:tuple[str,...]; evidence_ids:tuple[str,...]; metric_dispersion:Decimal|None; sensitivity_direction:str; regime_stability:dict; subperiod_stability:dict; warnings:tuple[str,...]; status:RobustnessStatus; fingerprint:str
@dataclass(frozen=True, slots=True)
class CandidateSelectionPolicy:
    policy_id:str; version:str; minimum_validation_trades:int; minimum_expectancy_improvement:Decimal; minimum_sharpe_improvement:Decimal; maximum_drawdown_worsening:Decimal; maximum_cost_worsening:Decimal; complexity_penalty_per_changed_parameter:Decimal; knife_edge_dispersion:Decimal|None; methodology_version:str; fingerprint:str
@dataclass(frozen=True, slots=True)
class CandidateSelectionResult:
    selection_id:str; experiment_id:str; baseline_candidate_id:str; candidate_ids:tuple[str,...]; evidence_ids:tuple[str,...]; robustness_result_ids:tuple[str,...]; policy_id:str; policy_version:str; selected_candidate_id:str|None; status:CandidateSelectionStatus; reasons:tuple[str,...]; warnings:tuple[str,...]; selection_timestamp:datetime; fingerprint:str


class ControlledCandidateExperimentService:
    """Selection is deliberately TRAIN/VALIDATION-only and never changes a strategy."""
    def __init__(self, repository) -> None:self.repository=repository
    def validate_experiment(self, experiment:StrategyExperiment, budget:ExperimentBudget, deltas:tuple[StrategyCandidateDelta,...])->None:
        if not experiment.hypothesis.strip():raise ValueError("An experiment requires an explicit hypothesis.")
        if not experiment.experimental_candidate_ids:raise ValueError("A candidate comparison requires the baseline plus at least one explicit experimental candidate.")
        ids=(experiment.baseline_candidate_id,*experiment.experimental_candidate_ids)
        if len(set(ids))!=len(ids) or len(experiment.experimental_candidate_ids)>budget.maximum_candidate_count:raise ValueError("Experiment exceeds its frozen candidate budget.")
        if any(self.repository.get_strategy_candidate(identifier) is None for identifier in ids):raise ValueError("Experiment requires complete persisted candidate snapshots.")
        if any(delta.candidate_id not in experiment.experimental_candidate_ids for delta in deltas):raise ValueError("Candidate delta is outside the experiment candidate set.")
        if any(any(token in delta.changed_field.upper() for token in {"PIT","LOOKAHEAD","SIX_GATE","AUDIT","IMMUTABLE","REAL_ACCOUNT"}) for delta in deltas):raise ValueError("Experiments cannot alter hard strategy invariants.")
        counts={identifier:0 for identifier in experiment.experimental_candidate_ids}
        for delta in deltas:counts[delta.candidate_id]+=1
        if any(count>budget.maximum_changed_parameters for count in counts.values()):raise ValueError("Candidate exceeds the frozen changed-parameter budget.")
        for delta in deltas:
            if delta.changed_field.startswith("score_weight:"):
                value=Decimal(delta.experimental_value)
                if value<0:raise ValueError("Decision Score weights cannot be negative.")
            if delta.changed_field in budget.permitted_ranges:
                value=Decimal(delta.experimental_value); lower,upper=budget.permitted_ranges[delta.changed_field]
                if not lower<=value<=upper:raise ValueError("Candidate parameter change is outside the frozen permitted range.")
    def select(self, *, experiment_id:str, policy:CandidateSelectionPolicy, selection_timestamp:datetime, robustness_results:tuple[CandidateRobustnessResult,...]=())->CandidateSelectionResult:
        experiment=self.repository.get_strategy_experiment(experiment_id); budget=self.repository.get_experiment_budget(experiment.budget_id) if experiment else None
        if experiment is None or budget is None:raise ValueError("Selection requires a persisted experiment and budget.")
        candidates=(experiment.baseline_candidate_id,*experiment.experimental_candidate_ids); evidence=self.repository.list_candidate_evaluation_evidence(experiment_id)
        if any(item.partition_type is PartitionType.TEST for item in evidence):raise ValueError("TEST evidence is forbidden during experiment selection.")
        if any(sum(item.candidate_id==candidate_id for item in evidence)>budget.maximum_repeated_evaluations for candidate_id in candidates):raise ValueError("Experiment exceeds its frozen repeated-evaluation budget.")
        if any(item.evaluated_at>selection_timestamp for item in evidence):raise ValueError("Future evidence cannot participate in frozen selection.")
        if any(item.partition_id not in experiment.permitted_partition_ids for item in evidence):raise ValueError("Evidence partition is not permitted by this experiment.")
        baseline=self._validation(evidence,experiment.baseline_candidate_id)
        reasons=[];warnings=[];chosen=None;status=CandidateSelectionStatus.BASELINE_RETAINED
        if baseline is None or baseline.trade_count<policy.minimum_validation_trades:
            status=CandidateSelectionStatus.INSUFFICIENT_EVIDENCE;reasons.append("BASELINE_VALIDATION_SAMPLE_INSUFFICIENT")
        else:
            winners=[]
            for candidate_id in experiment.experimental_candidate_ids:
                item=self._validation(evidence,candidate_id); complexity=sum(delta.candidate_id==candidate_id for delta in self.repository.list_strategy_candidate_deltas(experiment_id))
                robust=next((item for item in robustness_results if item.candidate_id==candidate_id),None)
                if item is None or item.trade_count<policy.minimum_validation_trades: warnings.append(f"INSUFFICIENT_VALIDATION_SAMPLE:{candidate_id}");continue
                if robust and robust.status is RobustnessStatus.FRAGILE:warnings.append(f"FRAGILE_PARAMETER_SENSITIVITY:{candidate_id}");continue
                expectancy=(item.expectancy or Decimal("0"))-(baseline.expectancy or Decimal("0"));sharpe=(item.sharpe or Decimal("0"))-(baseline.sharpe or Decimal("0"));dd=(item.drawdown or Decimal("0"))-(baseline.drawdown or Decimal("0"));cost=(item.costs or Decimal("0"))-(baseline.costs or Decimal("0"))
                score=expectancy+sharpe-policy.complexity_penalty_per_changed_parameter*complexity
                if expectancy>=policy.minimum_expectancy_improvement and sharpe>=policy.minimum_sharpe_improvement and dd>=-policy.maximum_drawdown_worsening and cost<=policy.maximum_cost_worsening:winners.append((score,candidate_id))
                else:reasons.append(f"HURDLE_NOT_MET:{candidate_id}")
            if len(winners)==1:chosen=winners[0][1];status=CandidateSelectionStatus.CANDIDATE_SELECTED;reasons.append("VALIDATION_MULTI_FACTOR_HURDLES_MET")
            elif len(winners)>1:status=CandidateSelectionStatus.INCONCLUSIVE;reasons.append("PARETO_TRADE_OFF_INCONCLUSIVE")
            else:reasons.append("BASELINE_RETAINED")
        result=CandidateSelectionResult("candidate-selection-"+manifest_fingerprint(experiment=experiment.fingerprint,policy=policy.fingerprint,evidence=[item.fingerprint for item in evidence],at=selection_timestamp)[:24],experiment_id,experiment.baseline_candidate_id,candidates,tuple(item.evidence_id for item in evidence),tuple(item.robustness_id for item in robustness_results),policy.policy_id,policy.version,chosen,status,tuple(reasons),tuple(sorted(set(warnings))),selection_timestamp,manifest_fingerprint(experiment=experiment.fingerprint,policy=policy.fingerprint,candidates=candidates,evidence=[item.fingerprint for item in evidence],selected=chosen,status=status.value))
        self.repository.save_candidate_selection_policy(policy) if self.repository.get_candidate_selection_policy(policy.policy_id) is None else None
        self.repository.save_candidate_selection_result(result);return result
    def robustness(self, *, experiment_id:str,candidate_id:str,neighboring_candidate_ids:tuple[str,...],evidence:tuple[CandidateEvaluationEvidence,...],knife_edge:Decimal|None)->CandidateRobustnessResult:
        values=[item.return_value for item in evidence if item.return_value is not None];dispersion=Decimal(str(pstdev([float(item) for item in values]))) if len(values)>1 else None;fragile=knife_edge is not None and dispersion is not None and dispersion>knife_edge
        return CandidateRobustnessResult("candidate-robustness-"+manifest_fingerprint(experiment=experiment_id,candidate=candidate_id,evidence=[item.fingerprint for item in evidence])[:24],experiment_id,candidate_id,neighboring_candidate_ids,tuple(item.evidence_id for item in evidence),dispersion,"LOCAL_PERTURBATION",{}, {},("KNIFE_EDGE_PARAMETER_SENSITIVITY",) if fragile else (),RobustnessStatus.FRAGILE if fragile else RobustnessStatus.ROBUST if values else RobustnessStatus.INSUFFICIENT_EVIDENCE,manifest_fingerprint(candidate=candidate_id,neighbors=neighboring_candidate_ids,dispersion=dispersion))
    @staticmethod
    def _validation(evidence,candidate_id):return next((item for item in evidence if item.candidate_id==candidate_id and item.partition_type is PartitionType.VALIDATION),None)
