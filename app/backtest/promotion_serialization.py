from datetime import datetime
from decimal import Decimal
from app.backtest.serialization import dump
from .promotion import *
def _tuple(v):return tuple(v)
def policy_from(v):
 v=dict(v)
 for k in ('minimum_oos_coverage','maximum_drawdown','minimum_expectancy','minimum_sharpe','minimum_benchmark_coverage','minimum_return_improvement'):v[k]=Decimal(v[k]) if v[k] is not None else None
 v['allowed_statuses']=tuple(v['allowed_statuses']);return StrategyPromotionPolicy(**v)
def proposal_from(v):
 v=dict(v);v['created_at']=datetime.fromisoformat(v['created_at']);v['status']=PromotionProposalStatus(v['status'])
 for k in ('walk_forward_run_ids','aggregate_result_ids','benchmark_comparison_ids','robustness_result_ids','proposed_config_fingerprints','warnings'):v[k]=tuple(v[k])
 return StrategyPromotionProposal(**v)
def eligibility_from(v):
 v=dict(v);v['status']=PromotionEligibilityStatus(v['status']);v['reasons']=tuple(v['reasons']);v['warnings']=tuple(v['warnings']);v['evaluated_at']=datetime.fromisoformat(v['evaluated_at']);return PromotionEligibilityResult(**v)
def review_from(v):
 v=dict(v);v['reviewed_at']=datetime.fromisoformat(v['reviewed_at']);v['decision']=ReviewDecision(v['decision']);v['exceptions']=tuple(v['exceptions']);return StrategyPromotionReview(**v)
def approved_from(v):
 v=dict(v);v['approved_at']=datetime.fromisoformat(v['approved_at']);v['effective_from']=datetime.fromisoformat(v['effective_from']);v['status']=ApprovedStrategyStatus(v['status']);v['config_fingerprints']=tuple(v['config_fingerprints']);v['methodology_notes']=tuple(v['methodology_notes']);return ApprovedStrategyVersion(**v)
def activation_from(v):
 v=dict(v);v['effective_at']=datetime.fromisoformat(v['effective_at']);return StrategyActivation(**v)
def rollback_from(v):
 v=dict(v);v['requested_at']=datetime.fromisoformat(v['requested_at']);return StrategyRollback(**v)
