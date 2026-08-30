from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from app.historical.guard import manifest_fingerprint


class ObservationSource(str, Enum):
    HISTORICAL_BACKTEST = "HISTORICAL_BACKTEST"
    WALK_FORWARD_OOS = "WALK_FORWARD_OOS"
    PAPER_FORWARD_TEST = "PAPER_FORWARD_TEST"
    OTHER_GOVERNED_RESEARCH = "OTHER_GOVERNED_RESEARCH"


class AttributionStrength(str, Enum):
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    LIKELY_CONTRIBUTOR = "LIKELY_CONTRIBUTOR"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ErrorCategory(str, Enum):
    ENTRY_TOO_EARLY = "ENTRY_TOO_EARLY"; ENTRY_TOO_LATE = "ENTRY_TOO_LATE"; FALSE_BREAKOUT = "FALSE_BREAKOUT"; HIGH_SCORE_FAILURE = "HIGH_SCORE_FAILURE"
    WEAK_RELATIVE_STRENGTH = "WEAK_RELATIVE_STRENGTH"; SECTOR_MISALIGNMENT = "SECTOR_MISALIGNMENT"; REGIME_MISMATCH = "REGIME_MISMATCH"
    LOW_REWARD_TO_RISK = "LOW_REWARD_TO_RISK"; VOLUME_CONFIRMATION_FAILURE = "VOLUME_CONFIRMATION_FAILURE"; STOP_TOO_TIGHT = "STOP_TOO_TIGHT"; STOP_TOO_LOOSE = "STOP_TOO_LOOSE"
    EXCESSIVE_FRICTION = "EXCESSIVE_FRICTION"; LOW_CAPITAL_VELOCITY = "LOW_CAPITAL_VELOCITY"; CAPITAL_ROTATION_TOO_EARLY = "CAPITAL_ROTATION_TOO_EARLY"; CAPITAL_ROTATION_TOO_LATE = "CAPITAL_ROTATION_TOO_LATE"
    INVALIDATION_MISSED = "INVALIDATION_MISSED"; TIME_STOP_FAILURE = "TIME_STOP_FAILURE"; DATA_QUALITY_FAILURE = "DATA_QUALITY_FAILURE"; INSUFFICIENT_DATA = "INSUFFICIENT_DATA"; NO_ERROR_IDENTIFIED = "NO_ERROR_IDENTIFIED"


class SuccessCategory(str, Enum):
    HIGH_RS_BREAKOUT_SUCCESS = "HIGH_RS_BREAKOUT_SUCCESS"; EARNINGS_ACCELERATION_SUCCESS = "EARNINGS_ACCELERATION_SUCCESS"; SECTOR_ROTATION_ALIGNMENT = "SECTOR_ROTATION_ALIGNMENT"
    VOLUME_CONFIRMATION_SUCCESS = "VOLUME_CONFIRMATION_SUCCESS"; CATALYST_FOLLOW_THROUGH = "CATALYST_FOLLOW_THROUGH"; STRONG_RR_SUCCESS = "STRONG_RR_SUCCESS"; FAST_CAPITAL_VELOCITY = "FAST_CAPITAL_VELOCITY"
    MULTI_FACTOR_ALIGNMENT = "MULTI_FACTOR_ALIGNMENT"; REGIME_MATCH_SUCCESS = "REGIME_MATCH_SUCCESS"; STRICT_EXECUTABLE_FALSE_NEGATIVE = "STRICT_EXECUTABLE_FALSE_NEGATIVE"; CAPITAL_CONSTRAINT_MISS = "CAPITAL_CONSTRAINT_MISS"


class AttributionKind(str, Enum): ERROR = "ERROR"; SUCCESS = "SUCCESS"
class PatternEvidenceStatus(str, Enum): ANECDOTAL = "ANECDOTAL"; ELIGIBLE = "ELIGIBLE"; MIXED = "MIXED"; INCONCLUSIVE = "INCONCLUSIVE"; INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
class HypothesisType(str, Enum): WEIGHT_ADJUSTMENT="WEIGHT_ADJUSTMENT"; THRESHOLD_ADJUSTMENT="THRESHOLD_ADJUSTMENT"; GATE_PARAMETER_CHANGE="GATE_PARAMETER_CHANGE"; ROTATION_PARAMETER_CHANGE="ROTATION_PARAMETER_CHANGE"; SIGNAL_PARAMETER_CHANGE="SIGNAL_PARAMETER_CHANGE"; EXIT_PARAMETER_CHANGE="EXIT_PARAMETER_CHANGE"; SIZING_PARAMETER_CHANGE="SIZING_PARAMETER_CHANGE"; DATA_QUALITY_CHANGE="DATA_QUALITY_CHANGE"; NO_CHANGE_RECOMMENDED="NO_CHANGE_RECOMMENDED"; REQUEST_MORE_EVIDENCE="REQUEST_MORE_EVIDENCE"
class ConfigurableTargetDomain(str, Enum): DECISION_SCORE="DECISION_SCORE"; CONFIDENCE="CONFIDENCE"; EXECUTION_GATE="EXECUTION_GATE"; ROTATION="ROTATION"; SIGNAL="SIGNAL"; EXIT="EXIT"; SIZING="SIZING"; PAPER_EXECUTION="PAPER_EXECUTION"; DATA_QUALITY_INFRASTRUCTURE="DATA_QUALITY_INFRASTRUCTURE"; NONE="NONE"
class HypothesisReviewDecision(str, Enum): APPROVE_FOR_EXPERIMENT="APPROVE_FOR_EXPERIMENT"; REJECT="REJECT"; REQUEST_MORE_EVIDENCE="REQUEST_MORE_EVIDENCE"
class AutomatedResearchRunStatus(str, Enum): PLANNED="PLANNED"; RUNNING="RUNNING"; COMPLETED="COMPLETED"; COMPLETED_WITH_WARNINGS="COMPLETED_WITH_WARNINGS"; INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE"; FAILED="FAILED"; FAILED_AUDIT="FAILED_AUDIT"
class FutureOOSQueueStatus(str, Enum): QUEUED="QUEUED"; ASSIGNED_TO_FUTURE_TEST="ASSIGNED_TO_FUTURE_TEST"; EXPIRED="EXPIRED"; STALE="STALE"; CANCELLED="CANCELLED"
class FutureOOSAssignmentStatus(str, Enum): QUEUED="QUEUED"; ASSIGNED="ASSIGNED"; EXECUTING="EXECUTING"; COMPLETED="COMPLETED"; INSUFFICIENT="INSUFFICIENT"; FAILED="FAILED"; STALE="STALE"; CANCELLED="CANCELLED"
class FutureOOSExecutionStatus(str, Enum): COMPLETED="COMPLETED"; COMPLETED_WITH_WARNINGS="COMPLETED_WITH_WARNINGS"; INSUFFICIENT="INSUFFICIENT"; FAILED="FAILED"
class OOSCoverageStatus(str, Enum): OOS_EVIDENCE_ACCUMULATING="OOS_EVIDENCE_ACCUMULATING"; OOS_EVIDENCE_SUFFICIENT_FOR_GOVERNANCE_REVIEW="OOS_EVIDENCE_SUFFICIENT_FOR_GOVERNANCE_REVIEW"; OOS_EVIDENCE_INSUFFICIENT="OOS_EVIDENCE_INSUFFICIENT"; OOS_EVIDENCE_DEGRADED="OOS_EVIDENCE_DEGRADED"; OOS_EVIDENCE_FAILED_AUDIT="OOS_EVIDENCE_FAILED_AUDIT"


@dataclass(frozen=True, slots=True)
class SelfImprovementRun:
    run_id: str; strategy_version: str; analysis_start: datetime; analysis_end: datetime; backtest_run_ids: tuple[str, ...]; walk_forward_run_ids: tuple[str, ...]; aggregate_result_ids: tuple[str, ...]; paper_trade_ids: tuple[str, ...]; benchmark_ids: tuple[str, ...]; methodology_version: str; created_at: datetime; status: str; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class SelfImprovementObservation:
    observation_id: str; run_id: str; source: ObservationSource; source_artifact_id: str; occurred_at: datetime; strategy_version: str; fields: dict; provenance_ids: tuple[str, ...]; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class SelfImprovementEvidencePolicy:
    policy_id: str; version: str; minimum_observations: int; minimum_oos_observations: int; methodology_version: str; fingerprint: str
    permitted_sources: tuple[str, ...] = tuple(source.value for source in ObservationSource); recurrence_threshold: int | None = None; minimum_evidence_quality: str = "AUDITABLE"; minimum_regime_breadth: int = 1; minimum_sector_breadth: int = 1
    source_weights: tuple[tuple[str, Decimal], ...] = (("HISTORICAL_BACKTEST", Decimal("1")), ("WALK_FORWARD_OOS", Decimal("3")), ("PAPER_FORWARD_TEST", Decimal("3")), ("OTHER_GOVERNED_RESEARCH", Decimal("1")))

@dataclass(frozen=True, slots=True)
class AttributionRuleSet:
    rule_set_id: str; version: str; short_horizon_sessions: int; high_score_threshold: Decimal; low_rr_threshold: Decimal; minimum_adverse_r: Decimal; minimum_favorable_r: Decimal; max_entry_delay_pct: Decimal; max_cost_to_gross_ratio: Decimal; low_velocity_sessions: int; methodology_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class StrategyErrorAttribution:
    attribution_id: str; run_id: str; source_observation_id: str; strategy_version: str; category: ErrorCategory; strength: AttributionStrength; severity: str; evidence_ids: tuple[str, ...]; contributing_diagnostic_ids: tuple[str, ...]; counterfactual_notes: str | None; warnings: tuple[str, ...]; fingerprint: str; source: ObservationSource = ObservationSource.OTHER_GOVERNED_RESEARCH; rule_set_id: str = ""

@dataclass(frozen=True, slots=True)
class StrategySuccessAttribution:
    attribution_id: str; run_id: str; source_observation_id: str; strategy_version: str; category: SuccessCategory; strength: AttributionStrength; severity: str; evidence_ids: tuple[str, ...]; warnings: tuple[str, ...]; fingerprint: str; source: ObservationSource = ObservationSource.OTHER_GOVERNED_RESEARCH; rule_set_id: str = ""

@dataclass(frozen=True, slots=True)
class RecurringStrategyPattern:
    pattern_id: str; run_id: str; category: str; attribution_kind: AttributionKind; supporting_attribution_ids: tuple[str, ...]; occurrence_count: int; weighted_evidence_count: Decimal; oos_occurrence_count: int; historical_occurrence_count: int; paper_forward_occurrence_count: int; source_type_split: tuple[tuple[str, int], ...]; regimes: tuple[str, ...]; sectors: tuple[str, ...]; score_bands: tuple[str, ...]; confidence_bands: tuple[str, ...]; estimated_total_r_impact: Decimal | None; estimated_cost_impact: Decimal | None; evidence_status: PatternEvidenceStatus; warnings: tuple[str, ...]; policy_id: str; policy_version: str; rule_set_id: str; rule_set_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class StrategyErrorSummary:
    summary_id: str; run_id: str; category: str; count: int; weighted_count: Decimal; source_type_split: tuple[tuple[str, int], ...]; regime_split: tuple[tuple[str, int], ...]; sector_split: tuple[tuple[str, int], ...]; total_r_impact: Decimal | None; total_cost_impact: Decimal | None; warnings: tuple[str, ...]; rule_set_id: str; fingerprint: str; analysis_groups: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = ()

@dataclass(frozen=True, slots=True)
class StrategySuccessSummary:
    summary_id: str; run_id: str; category: str; count: int; weighted_count: Decimal; source_type_split: tuple[tuple[str, int], ...]; regime_split: tuple[tuple[str, int], ...]; sector_split: tuple[tuple[str, int], ...]; total_r_impact: Decimal | None; total_cost_impact: Decimal | None; warnings: tuple[str, ...]; rule_set_id: str; fingerprint: str; analysis_groups: tuple[tuple[str, tuple[tuple[str, int], ...]], ...] = ()

@dataclass(frozen=True, slots=True)
class ImprovementHypothesis:
    hypothesis_id: str; run_id: str; title: str; statement: str; source_attribution_ids: tuple[str, ...]; proposed_change_scope: str; confidence: str; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class HypothesisRankingPolicy:
    policy_id: str; version: str; maximum_hypotheses: int; methodology_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class HypothesisProposalBudget:
    budget_id: str; version: str; maximum_experiment_proposals: int; methodology_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class HypothesisGenerationPolicy:
    policy_id: str; version: str; minimum_evidence_score: Decimal; maximum_actionable_hypotheses: int; maximum_per_target_domain: int; allow_low_priority_mixed: bool; methodology_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class StrategyImprovementHypothesis:
    hypothesis_id: str; run_id: str; target_approved_strategy_id: str; target_strategy_version: str; title: str; description: str; originating_pattern_ids: tuple[str, ...]; supporting_attribution_ids: tuple[str, ...]; counterevidence_ids: tuple[str, ...]; problem_category: str; hypothesis_type: HypothesisType; target_domain: ConfigurableTargetDomain; target_field: str | None; proposed_direction: str; expected_mechanism: str; expected_benefit: str; potential_downside: str; applicable_regimes: tuple[str, ...]; applicable_sectors: tuple[str, ...]; evidence_status: PatternEvidenceStatus; confidence: str; complexity_estimate: str; created_at: datetime; warnings: tuple[str, ...]; evidence_fingerprint: str; generation_policy_id: str; generation_policy_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class StrategyHypothesisRanking:
    ranking_id: str; run_id: str; ordered_hypothesis_ids: tuple[str, ...]; factor_values: tuple[tuple[str, tuple[tuple[str, Decimal], ...]], ...]; excluded_hypothesis_reasons: tuple[tuple[str, str], ...]; methodology_version: str; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class HypothesisReview:
    review_id: str; hypothesis_id: str; reviewer_id: str; reviewed_at: datetime; decision: HypothesisReviewDecision; comments: str; evidence_fingerprint: str; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class HypothesisExperimentLink:
    link_id: str; run_id: str; hypothesis_id: str; review_id: str; experiment_id: str; candidate_delta_ids: tuple[str, ...]; baseline_candidate_id: str; target_approved_strategy_id: str; target_strategy_version: str; experiment_budget_id: str; experiment_budget_version: str; created_at: datetime; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class AutomatedResearchRun:
    research_run_id: str; experiment_id: str; hypothesis_experiment_link_id: str; baseline_candidate_id: str; experimental_candidate_ids: tuple[str, ...]; train_partition_ids: tuple[str, ...]; validation_partition_ids: tuple[str, ...]; forbidden_test_partition_ids: tuple[str, ...]; experiment_budget_id: str; experiment_budget_version: str; candidate_selection_policy_id: str; candidate_selection_policy_version: str; methodology_version: str; started_at: datetime; completed_at: datetime | None; status: AutomatedResearchRunStatus; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class FutureOOSCandidateQueueEntry:
    queue_id: str; selection_id: str; selected_candidate_id: str; target_plan_id: str; target_window_family: str; earliest_test_timestamp: datetime; selection_timestamp: datetime; candidate_fingerprint: str; status: FutureOOSQueueStatus; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class AutomatedResearchCycleResult:
    cycle_result_id: str; research_run_id: str; train_evidence_ids: tuple[str, ...]; validation_evidence_ids: tuple[str, ...]; robustness_result_ids: tuple[str, ...]; selection_id: str; queue_id: str | None; status: AutomatedResearchRunStatus; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class FutureOOSAssignmentPolicy:
    policy_id: str; version: str; minimum_lead_seconds: int; allowed_plan_ids: tuple[str, ...]; allow_multiple_windows: bool; maximum_concurrent_assignments: int; expiration_seconds: int | None; methodology_version: str; fingerprint: str

@dataclass(frozen=True, slots=True)
class FutureOOSAssignment:
    assignment_id: str; queue_id: str; selection_id: str; selected_candidate_id: str; plan_id: str; window_id: str; test_partition_id: str; assigned_at: datetime; test_start: datetime; test_end: datetime; candidate_fingerprint: str; policy_id: str; policy_version: str; status: FutureOOSAssignmentStatus; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class FutureOOSExecutionResult:
    execution_result_id: str; assignment_id: str; test_backtest_run_id: str | None; walk_forward_window_result_id: str; performance_report_id: str | None; benchmark_comparison_id: str | None; status: FutureOOSExecutionStatus; warnings: tuple[str, ...]; executed_at: datetime; fingerprint: str

@dataclass(frozen=True, slots=True)
class ResearchCandidateOOSRecord:
    record_id: str; selection_id: str; selected_candidate_id: str; candidate_fingerprint: str; assignment_ids: tuple[str, ...]; execution_result_ids: tuple[str, ...]; window_result_ids: tuple[str, ...]; aggregate_result_id: str | None; planned_window_count: int; completed_window_count: int; valid_window_count: int; insufficient_window_count: int; failed_window_count: int; benchmark_covered_window_count: int; coverage_status: OOSCoverageStatus; warnings: tuple[str, ...]; fingerprint: str

@dataclass(frozen=True, slots=True)
class PromotionEvidencePackage:
    package_id: str; selected_candidate_id: str; baseline_candidate_id: str; baseline_candidate_fingerprint: str; source_self_improvement_run_id: str; hypothesis_id: str; hypothesis_review_id: str; hypothesis_experiment_link_id: str; experiment_id: str; automated_research_run_id: str; selection_id: str; queue_ids: tuple[str, ...]; assignment_ids: tuple[str, ...]; execution_result_ids: tuple[str, ...]; window_result_ids: tuple[str, ...]; aggregate_result_id: str | None; robustness_result_ids: tuple[str, ...]; benchmark_comparison_ids: tuple[str, ...]; candidate_fingerprint: str; coverage_status: OOSCoverageStatus; warnings: tuple[str, ...]; generated_at: datetime; methodology_version: str; fingerprint: str

def future_oos_assignment_policy_fingerprint(value: FutureOOSAssignmentPolicy) -> str:
    return manifest_fingerprint(policy_id=value.policy_id,version=value.version,minimum_lead_seconds=value.minimum_lead_seconds,allowed_plan_ids=value.allowed_plan_ids,allow_multiple_windows=value.allow_multiple_windows,maximum_concurrent_assignments=value.maximum_concurrent_assignments,expiration_seconds=value.expiration_seconds,methodology_version=value.methodology_version)

def future_oos_assignment_fingerprint(value: FutureOOSAssignment) -> str:
    return manifest_fingerprint(assignment_id=value.assignment_id,queue_id=value.queue_id,selection_id=value.selection_id,selected_candidate_id=value.selected_candidate_id,plan_id=value.plan_id,window_id=value.window_id,test_partition_id=value.test_partition_id,assigned_at=value.assigned_at,test_start=value.test_start,test_end=value.test_end,candidate_fingerprint=value.candidate_fingerprint,policy_id=value.policy_id,policy_version=value.policy_version,status=value.status.value,warnings=value.warnings)

def future_oos_execution_fingerprint(value: FutureOOSExecutionResult) -> str:
    return manifest_fingerprint(execution_result_id=value.execution_result_id,assignment_id=value.assignment_id,test_backtest_run_id=value.test_backtest_run_id,window_result_id=value.walk_forward_window_result_id,performance_report_id=value.performance_report_id,benchmark_comparison_id=value.benchmark_comparison_id,status=value.status.value,warnings=value.warnings,executed_at=value.executed_at)

def promotion_evidence_package_fingerprint(value: PromotionEvidencePackage) -> str:
    return manifest_fingerprint(package_id=value.package_id,candidate=value.selected_candidate_id,baseline=value.baseline_candidate_id,baseline_fingerprint=value.baseline_candidate_fingerprint,source_run=value.source_self_improvement_run_id,hypothesis=value.hypothesis_id,review=value.hypothesis_review_id,link=value.hypothesis_experiment_link_id,experiment=value.experiment_id,research_run=value.automated_research_run_id,selection=value.selection_id,queues=value.queue_ids,assignments=value.assignment_ids,executions=value.execution_result_ids,window_results=value.window_result_ids,aggregate=value.aggregate_result_id,robustness=value.robustness_result_ids,benchmarks=value.benchmark_comparison_ids,candidate_fingerprint=value.candidate_fingerprint,coverage=value.coverage_status.value,warnings=value.warnings,generated_at=value.generated_at,methodology=value.methodology_version)

def hypothesis_review_fingerprint(value: HypothesisReview) -> str:
    return manifest_fingerprint(review_id=value.review_id,hypothesis_id=value.hypothesis_id,reviewer=value.reviewer_id,reviewed_at=value.reviewed_at,decision=value.decision.value,comments=value.comments,evidence=value.evidence_fingerprint,warnings=value.warnings)
