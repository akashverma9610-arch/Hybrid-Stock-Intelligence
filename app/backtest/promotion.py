from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from app.historical.guard import manifest_fingerprint
from app.backtest.oos_aggregation import AggregateValidationStatus

class PromotionProposalStatus(str,Enum): DRAFT="DRAFT";READY_FOR_REVIEW="READY_FOR_REVIEW";BLOCKED="BLOCKED";APPROVED="APPROVED";REJECTED="REJECTED";EXPIRED="EXPIRED";SUPERSEDED="SUPERSEDED"
class PromotionEligibilityStatus(str,Enum): ELIGIBLE_FOR_REVIEW="ELIGIBLE_FOR_REVIEW";INSUFFICIENT_EVIDENCE="INSUFFICIENT_EVIDENCE";BLOCKED_BY_RISK="BLOCKED_BY_RISK";BLOCKED_BY_ROBUSTNESS="BLOCKED_BY_ROBUSTNESS";BLOCKED_BY_BENCHMARK="BLOCKED_BY_BENCHMARK";BLOCKED_BY_AUDIT="BLOCKED_BY_AUDIT";BLOCKED_BY_COMPLEXITY="BLOCKED_BY_COMPLEXITY"
class ReviewDecision(str,Enum): APPROVE="APPROVE";REJECT="REJECT";REQUEST_MORE_EVIDENCE="REQUEST_MORE_EVIDENCE"
class ApprovedStrategyStatus(str,Enum): APPROVED="APPROVED";SUSPENDED="SUSPENDED"
@dataclass(frozen=True,slots=True)
class StrategyPromotionPolicy:
 policy_id:str;version:str;minimum_valid_oos_windows:int;minimum_oos_coverage:Decimal;minimum_oos_trades:int;maximum_drawdown:Decimal;minimum_expectancy:Decimal;minimum_sharpe:Decimal;minimum_benchmark_coverage:Decimal|None;allowed_statuses:tuple[str,...];require_robust:bool;maximum_complexity:int;minimum_return_improvement:Decimal;required_human_approval:bool;methodology_version:str;fingerprint:str
@dataclass(frozen=True,slots=True)
class StrategyPromotionProposal:
 proposal_id:str;candidate_id:str;baseline_strategy_id:str;baseline_version:str;experiment_id:str;selection_id:str;walk_forward_run_ids:tuple[str,...];aggregate_result_ids:tuple[str,...];benchmark_comparison_ids:tuple[str,...];robustness_result_ids:tuple[str,...];proposed_config_fingerprints:tuple[str,...];reason:str;created_at:datetime;status:PromotionProposalStatus;warnings:tuple[str,...];fingerprint:str
@dataclass(frozen=True,slots=True)
class PromotionEligibilityResult:
 eligibility_id:str;proposal_id:str;policy_id:str;policy_version:str;status:PromotionEligibilityStatus;reasons:tuple[str,...];warnings:tuple[str,...];evaluated_at:datetime;fingerprint:str
@dataclass(frozen=True,slots=True)
class StrategyPromotionReview:
 review_id:str;proposal_id:str;reviewer_id:str;reviewed_at:datetime;decision:ReviewDecision;comments:str;exceptions:tuple[str,...];policy_version:str;evidence_fingerprint:str;fingerprint:str
@dataclass(frozen=True,slots=True)
class ApprovedStrategyVersion:
 approved_id:str;strategy_id:str;version:str;parent_approved_id:str|None;proposal_id:str;review_id:str;candidate_id:str;config_fingerprints:tuple[str,...];approved_at:datetime;effective_from:datetime;status:ApprovedStrategyStatus;methodology_notes:tuple[str,...];fingerprint:str
@dataclass(frozen=True,slots=True)
class StrategyActivation:
 activation_id:str;approved_id:str;previous_approved_id:str|None;review_id:str;effective_at:datetime;reason:str;fingerprint:str
@dataclass(frozen=True,slots=True)
class StrategyRollback:
 rollback_id:str;from_approved_id:str;to_approved_id:str;review_id:str;activation_id:str;requested_at:datetime;reason:str;fingerprint:str

class StrategyPromotionService:
 def __init__(self,repository):self.repository=repository
 def eligibility(self,proposal,policy,at):
  aggregates=tuple(self.repository.get_walk_forward_aggregate_result(i) for i in proposal.aggregate_result_ids)
  reasons=[];status=PromotionEligibilityStatus.ELIGIBLE_FOR_REVIEW
  if not aggregates or any(x is None for x in aggregates):status=PromotionEligibilityStatus.INSUFFICIENT_EVIDENCE;reasons.append("MISSING_GENUINE_OOS_EVIDENCE")
  else:
   evidence=aggregates[-1]
   if evidence.status.value not in policy.allowed_statuses:status=PromotionEligibilityStatus.INSUFFICIENT_EVIDENCE;reasons.append("OOS_STATUS_DISALLOWED")
   elif evidence.valid_window_count<policy.minimum_valid_oos_windows or evidence.coverage_ratio<policy.minimum_oos_coverage or evidence.trade_count<policy.minimum_oos_trades:status=PromotionEligibilityStatus.INSUFFICIENT_EVIDENCE;reasons.append("OOS_COVERAGE_OR_SAMPLE_INSUFFICIENT")
   elif evidence.maximum_drawdown is not None and evidence.maximum_drawdown < -policy.maximum_drawdown:status=PromotionEligibilityStatus.BLOCKED_BY_RISK;reasons.append("MAX_DRAWDOWN_EXCEEDED")
   elif evidence.expectancy is None or evidence.expectancy<policy.minimum_expectancy or evidence.sharpe is None or evidence.sharpe<policy.minimum_sharpe:status=PromotionEligibilityStatus.INSUFFICIENT_EVIDENCE;reasons.append("RISK_ADJUSTED_HURDLE_NOT_MET")
   elif policy.minimum_benchmark_coverage is not None and Decimal(evidence.benchmark_covered_window_count)/evidence.total_planned_window_count<policy.minimum_benchmark_coverage:status=PromotionEligibilityStatus.BLOCKED_BY_BENCHMARK;reasons.append("BENCHMARK_COVERAGE_INSUFFICIENT")
  return PromotionEligibilityResult("promotion-eligibility-"+manifest_fingerprint(proposal=proposal.fingerprint,policy=policy.fingerprint)[:24],proposal.proposal_id,policy.policy_id,policy.version,status,tuple(reasons),(),at,manifest_fingerprint(proposal=proposal.fingerprint,policy=policy.fingerprint,status=status.value,reasons=reasons))
 def is_stale(self,proposal,active):
  return active is not None and (active.strategy_id!=proposal.baseline_strategy_id or active.version!=proposal.baseline_version)
