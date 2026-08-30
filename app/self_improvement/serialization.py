from datetime import datetime
from decimal import Decimal

from app.backtest.serialization import dump
from .models import *


def _tuples(value, *keys):
    value = dict(value)
    for key in keys: value[key] = tuple(value.get(key, ()))
    return value


def _decimal(value, *keys):
    for key in keys:
        if value.get(key) is not None: value[key] = Decimal(value[key])
    return value


def run_from(value):
    value = _tuples(value, "backtest_run_ids", "walk_forward_run_ids", "aggregate_result_ids", "paper_trade_ids", "benchmark_ids", "warnings")
    value["analysis_start"] = datetime.fromisoformat(value["analysis_start"]); value["analysis_end"] = datetime.fromisoformat(value["analysis_end"]); value["created_at"] = datetime.fromisoformat(value["created_at"])
    return SelfImprovementRun(**value)


def observation_from(value):
    value = _tuples(value, "provenance_ids", "warnings"); value["source"] = ObservationSource(value["source"]); value["occurred_at"] = datetime.fromisoformat(value["occurred_at"])
    return SelfImprovementObservation(**value)


def evidence_policy_from(value):
    value = _tuples(value, "permitted_sources")
    value["source_weights"] = tuple((source, Decimal(weight)) for source, weight in value.get("source_weights", SelfImprovementEvidencePolicy.source_weights))
    return SelfImprovementEvidencePolicy(**value)


def rule_set_from(value):
    return AttributionRuleSet(**_decimal(dict(value), "high_score_threshold", "low_rr_threshold", "minimum_adverse_r", "minimum_favorable_r", "max_entry_delay_pct", "max_cost_to_gross_ratio"))


def error_from(value):
    value = _tuples(value, "evidence_ids", "contributing_diagnostic_ids", "warnings"); value["category"] = ErrorCategory(value["category"]); value["strength"] = AttributionStrength(value["strength"]); value["source"] = ObservationSource(value.get("source", ObservationSource.OTHER_GOVERNED_RESEARCH.value))
    return StrategyErrorAttribution(**value)


def success_from(value):
    value = _tuples(value, "evidence_ids", "warnings"); value["category"] = SuccessCategory(value["category"]); value["strength"] = AttributionStrength(value["strength"]); value["source"] = ObservationSource(value.get("source", ObservationSource.OTHER_GOVERNED_RESEARCH.value))
    return StrategySuccessAttribution(**value)


def pattern_from(value):
    value = _tuples(value, "supporting_attribution_ids", "regimes", "sectors", "score_bands", "confidence_bands", "warnings")
    value["source_type_split"] = tuple((name, int(count)) for name, count in value["source_type_split"])
    value["attribution_kind"] = AttributionKind(value["attribution_kind"]); value["evidence_status"] = PatternEvidenceStatus(value["evidence_status"])
    return RecurringStrategyPattern(**_decimal(value, "weighted_evidence_count", "estimated_total_r_impact", "estimated_cost_impact"))


def _summary_from(value, model):
    value = _tuples(value, "warnings")
    for key in ("source_type_split", "regime_split", "sector_split"): value[key] = tuple((name, int(count)) for name, count in value[key])
    value["analysis_groups"] = tuple((name, tuple((label, int(count)) for label, count in values)) for name, values in value.get("analysis_groups", ()))
    return model(**_decimal(value, "weighted_count", "total_r_impact", "total_cost_impact"))


def error_summary_from(value): return _summary_from(value, StrategyErrorSummary)
def success_summary_from(value): return _summary_from(value, StrategySuccessSummary)
def hypothesis_from(value): return ImprovementHypothesis(**_tuples(value, "source_attribution_ids", "warnings"))
def ranking_policy_from(value): return HypothesisRankingPolicy(**dict(value))
def proposal_budget_from(value): return HypothesisProposalBudget(**dict(value))
def generation_policy_from(value):
    value=dict(value); value["minimum_evidence_score"]=Decimal(value["minimum_evidence_score"]); return HypothesisGenerationPolicy(**value)
def strategy_hypothesis_from(value):
    value=_tuples(value,"originating_pattern_ids","supporting_attribution_ids","counterevidence_ids","applicable_regimes","applicable_sectors","warnings")
    value["hypothesis_type"]=HypothesisType(value["hypothesis_type"]); value["target_domain"]=ConfigurableTargetDomain(value["target_domain"]); value["evidence_status"]=PatternEvidenceStatus(value["evidence_status"]); value["created_at"]=datetime.fromisoformat(value["created_at"])
    return StrategyImprovementHypothesis(**value)
def ranking_from(value):
    value=dict(value); value["ordered_hypothesis_ids"]=tuple(value["ordered_hypothesis_ids"]); value["factor_values"]=tuple((identifier,tuple((name,Decimal(score)) for name,score in factors)) for identifier,factors in value["factor_values"]); value["excluded_hypothesis_reasons"]=tuple((identifier,reason) for identifier,reason in value["excluded_hypothesis_reasons"]); value["warnings"]=tuple(value["warnings"]); return StrategyHypothesisRanking(**value)
def hypothesis_review_from(value):
    value=_tuples(value,"warnings"); value["decision"]=HypothesisReviewDecision(value["decision"]); value["reviewed_at"]=datetime.fromisoformat(value["reviewed_at"]); return HypothesisReview(**value)
def hypothesis_experiment_link_from(value):
    value=_tuples(value,"candidate_delta_ids","warnings"); value["created_at"]=datetime.fromisoformat(value["created_at"]); return HypothesisExperimentLink(**value)
def automated_research_run_from(value):
    value=_tuples(value,"experimental_candidate_ids","train_partition_ids","validation_partition_ids","forbidden_test_partition_ids","warnings"); value["started_at"]=datetime.fromisoformat(value["started_at"]); value["completed_at"]=datetime.fromisoformat(value["completed_at"]) if value["completed_at"] else None; value["status"]=AutomatedResearchRunStatus(value["status"]); return AutomatedResearchRun(**value)
def future_oos_queue_from(value):
    value=_tuples(value,"warnings"); value["earliest_test_timestamp"]=datetime.fromisoformat(value["earliest_test_timestamp"]); value["selection_timestamp"]=datetime.fromisoformat(value["selection_timestamp"]); value["status"]=FutureOOSQueueStatus(value["status"]); return FutureOOSCandidateQueueEntry(**value)
def automated_research_cycle_from(value):
    value=_tuples(value,"train_evidence_ids","validation_evidence_ids","robustness_result_ids","warnings"); value["status"]=AutomatedResearchRunStatus(value["status"]); return AutomatedResearchCycleResult(**value)
def future_oos_assignment_policy_from(value):
    value=_tuples(value,"allowed_plan_ids"); return FutureOOSAssignmentPolicy(**value)
def future_oos_assignment_from(value):
    value=_tuples(value,"warnings"); value["assigned_at"]=datetime.fromisoformat(value["assigned_at"]); value["test_start"]=datetime.fromisoformat(value["test_start"]); value["test_end"]=datetime.fromisoformat(value["test_end"]); value["status"]=FutureOOSAssignmentStatus(value["status"]); return FutureOOSAssignment(**value)
def future_oos_execution_from(value):
    value=_tuples(value,"warnings"); value["executed_at"]=datetime.fromisoformat(value["executed_at"]); value["status"]=FutureOOSExecutionStatus(value["status"]); return FutureOOSExecutionResult(**value)
def research_candidate_oos_from(value):
    value=_tuples(value,"assignment_ids","execution_result_ids","window_result_ids","warnings"); value["coverage_status"]=OOSCoverageStatus(value["coverage_status"]); return ResearchCandidateOOSRecord(**value)
def promotion_evidence_package_from(value):
    value=_tuples(value,"queue_ids","assignment_ids","execution_result_ids","window_result_ids","robustness_result_ids","benchmark_comparison_ids","warnings"); value["coverage_status"]=OOSCoverageStatus(value["coverage_status"]); value["generated_at"]=datetime.fromisoformat(value["generated_at"]); return PromotionEvidencePackage(**value)
