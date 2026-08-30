from datetime import UTC, datetime, timedelta
from decimal import Decimal
import pytest

from app.backtest.promotion import *
from app.historical.guard import manifest_fingerprint
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository

T=datetime(2026,1,1,tzinfo=UTC)
def records():
 p=StrategyPromotionPolicy("policy","1",2,Decimal(".6"),10,Decimal(".2"),Decimal("0"),Decimal(".1"),None,("VALID",),True,2,Decimal(".01"),True,"v1",manifest_fingerprint(x="p"))
 q=StrategyPromotionProposal("proposal","candidate","strategy","2.1","experiment","selection",("wf",),("aggregate",),("bench",),("robust",),("candidate-fp",),"hypothesis",T,PromotionProposalStatus.READY_FOR_REVIEW,("warning",),manifest_fingerprint(x="q"))
 e=PromotionEligibilityResult("eligibility",q.proposal_id,p.policy_id,p.version,PromotionEligibilityStatus.ELIGIBLE_FOR_REVIEW,("OOS_OK",),(),T,manifest_fingerprint(x="e"))
 r=StrategyPromotionReview("review",q.proposal_id,"human:reviewer",T,ReviewDecision.APPROVE,"approved",(),p.version,"evidence-fp",manifest_fingerprint(x="r"))
 v=ApprovedStrategyVersion("approved","strategy","2.2",None,q.proposal_id,r.review_id,"candidate",("candidate-fp",),T,T+timedelta(days=1),ApprovedStrategyStatus.APPROVED,("explicit",),manifest_fingerprint(x="v"))
 a=StrategyActivation("activation",v.approved_id,"prior",r.review_id,T+timedelta(days=1),"human activation",manifest_fingerprint(x="a"))
 return p,q,e,r,v,a
def test_promotion_records_round_trip_and_are_insert_only(tmp_path):
 repo=SQLiteStrategyGovernanceRepository(tmp_path/'promotion.db'); values=records()
 actions=((repo.save_strategy_promotion_policy,repo.get_strategy_promotion_policy,values[0].policy_id,values[0]),(repo.save_strategy_promotion_proposal,repo.get_strategy_promotion_proposal,values[1].proposal_id,values[1]),(repo.save_promotion_eligibility_result,repo.get_promotion_eligibility_result,values[2].eligibility_id,values[2]),(repo.save_strategy_promotion_review,repo.get_strategy_promotion_review,values[3].review_id,values[3]),(repo.save_approved_strategy_version,repo.get_approved_strategy_version,values[4].approved_id,values[4]),(repo.save_strategy_activation,repo.get_strategy_activation,values[5].activation_id,values[5]))
 for save,get,identifier,value in actions: save(value);assert get(identifier)==value
 for save,_get,_identifier,value in actions:
  with pytest.raises(ValueError,match="immutable"):save(value)
 # An unrelated later record cannot rewrite an earlier typed value.
 later=StrategyPromotionPolicy("policy-v2","2",2,Decimal(".7"),10,Decimal(".2"),Decimal("0"),Decimal(".1"),None,("VALID",),True,2,Decimal(".01"),True,"v2",manifest_fingerprint(x="p2"));repo.save_strategy_promotion_policy(later)
 assert repo.get_strategy_promotion_policy("policy")==values[0] and repo.get_strategy_promotion_policy("policy-v2")==later

def test_human_review_and_activation_chains_fail_closed(tmp_path):
 repo=SQLiteStrategyGovernanceRepository(tmp_path/'governance.db');p,q,e,r,v,a=records();repo.save_strategy_promotion_policy(p);repo.save_strategy_promotion_proposal(q);repo.save_promotion_eligibility_result(e)
 # No review, non-human review, rejected review, and activation without an approved version are all blocked.
 with pytest.raises(ValueError,match="human APPROVE"):repo.save_approved_strategy_version(v)
 with pytest.raises(ValueError,match="human reviewer"):repo.save_strategy_promotion_review(__import__('dataclasses').replace(r,reviewer_id='system:worker'))
 repo.save_strategy_promotion_review(__import__('dataclasses').replace(r,decision=ReviewDecision.REJECT))
 with pytest.raises(ValueError,match="human APPROVE"):repo.save_approved_strategy_version(v)
 # A valid immutable review/version still does not activate automatically.
 valid=__import__('dataclasses').replace(r,review_id='approved-review');repo.save_strategy_promotion_review(valid);version=__import__('dataclasses').replace(v,review_id=valid.review_id);repo.save_approved_strategy_version(version)
 with pytest.raises(ValueError,match="prospective"):repo.save_strategy_activation(__import__('dataclasses').replace(a,review_id=valid.review_id,approved_id=version.approved_id,effective_at=T))
 repo.save_strategy_activation(__import__('dataclasses').replace(a,review_id=valid.review_id,approved_id=version.approved_id))
