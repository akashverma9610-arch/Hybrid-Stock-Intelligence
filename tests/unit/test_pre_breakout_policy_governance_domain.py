from datetime import UTC, datetime, timedelta
import pytest
from app.strategies.pre_breakout.policy import *
from app.strategies.pre_breakout.policy_serialization import *

T=datetime(2026,8,28,tzinfo=UTC)
def approval(**over):
 d=dict(approval_id='a1',policy_id='p',policy_version='v1',draft_policy_fingerprint='draft',approved_policy_fingerprint='policy',approved_values_fingerprint='values',reviewer_id='human:owner',reviewed_at=T,decision=PreBreakoutPolicyApprovalDecision.APPROVE,created_at=T,warnings=())
 d.update(over); d['fingerprint']=prebreakout_policy_approval_fingerprint(**{k:(v.value if hasattr(v,'value') else v.isoformat() if isinstance(v,datetime) else v) for k,v in d.items() if k!='fingerprint'}); return PreBreakoutPolicyApproval(**d)
def selection(**over):
 d=dict(selection_id='s1',approval_id='a1',policy_id='p',policy_version='v1',policy_fingerprint='policy',selection_context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,selected_by='human:owner',selected_at=T,effective_from=T,warnings=())
 d.update(over); d['fingerprint']=prebreakout_policy_selection_fingerprint(**{k:(v.value if hasattr(v,'value') else v.isoformat() if isinstance(v,datetime) else v) for k,v in d.items() if k!='fingerprint'}); return PreBreakoutPolicySelection(**d)
def test_approval_and_selection_round_trip_and_determinism():
 a=approval(); s=selection(); assert approval().fingerprint==a.fingerprint and selection().fingerprint==s.fingerprint
 assert approval_from(approval_to(a))==a and selection_from(selection_to(s))==s
 assert isinstance(approval_from(approval_to(a)).decision,PreBreakoutPolicyApprovalDecision)
 assert isinstance(selection_from(selection_to(s)).selection_context,PreBreakoutPolicySelectionContext)
def test_semantic_changes_change_fingerprints(): assert approval(warnings=('x',)).fingerprint!=approval().fingerprint and selection(warnings=('x',)).fingerprint!=selection().fingerprint
@pytest.mark.parametrize('factory,kwargs,code',[(approval,{'reviewer_id':'automation:x'},'HUMAN_REVIEWER_REQUIRED'),(approval,{'reviewed_at':datetime(2026,8,28)},'NAIVE'),(approval,{'created_at':T-timedelta(seconds=1)},'CHRONOLOGY'),(selection,{'selected_by':''},'HUMAN_REVIEWER_REQUIRED'),(selection,{'effective_from':T-timedelta(seconds=1)},'CHRONOLOGY')])
def test_validation_fails_closed(factory,kwargs,code):
 with pytest.raises(ValueError,match=code): factory(**kwargs)
def test_tampering_and_malformed_payload_fail_closed():
 a=approval_to(approval()); a['policy_id']='tampered'
 with pytest.raises(ValueError,match='FINGERPRINT'): approval_from(a)
 s=selection_to(selection()); s['selection_context']='BAD'
 with pytest.raises(ValueError): selection_from(s)
 a=approval_to(approval()); a.pop('approval_id')
 with pytest.raises(ValueError,match='SERIALIZATION_INVALID'): approval_from(a)
