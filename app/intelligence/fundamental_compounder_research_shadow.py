"""Read-only Fundamental Compounder Research Shadow V1 state propagation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC
from enum import StrEnum
import hashlib
import json

from app.intelligence.long_term_thesis_research_shadow import LongTermResearchShadowState, LongTermThesisResearchShadow
from app.intelligence.long_term_thesis_review import LongTermThesisFamily

CONTRACT_VERSION="fundamental-compounder-research-shadow/v1"
class FundamentalCompounderResearchShadowError(ValueError): pass
class FundamentalCompounderBusinessBranch(StrEnum):
    NON_FINANCIAL_CORPORATE="NON_FINANCIAL_CORPORATE"; BANK="BANK"; NBFC="NBFC"; INSURER="INSURER"; STRUCTURALLY_NON_COMPARABLE="STRUCTURALLY_NON_COMPARABLE"; UNKNOWN="UNKNOWN"
class FundamentalCompounderState(StrEnum):
    SHADOW_CANDIDATE="SHADOW_CANDIDATE"; SHADOW_NOT_QUALIFIED="SHADOW_NOT_QUALIFIED"; DATA_INSUFFICIENT="DATA_INSUFFICIENT"; EVIDENCE_CONFLICTED="EVIDENCE_CONFLICTED"; POLICY_PARAMETER_UNAVAILABLE="POLICY_PARAMETER_UNAVAILABLE"; NOT_APPLICABLE="NOT_APPLICABLE"
class FundamentalCompounderReason(StrEnum):
    SOURCE_RECEIPT_UNVERIFIABLE="SOURCE_RECEIPT_UNVERIFIABLE"; SOURCE_RECEIPT_TEMPORALLY_INVALID="SOURCE_RECEIPT_TEMPORALLY_INVALID"; SOURCE_EVIDENCE_CONFLICTED="SOURCE_EVIDENCE_CONFLICTED"; SOURCE_DATA_INSUFFICIENT="SOURCE_DATA_INSUFFICIENT"; FINANCIAL_SECTOR_POLICY_UNAVAILABLE="FINANCIAL_SECTOR_POLICY_UNAVAILABLE"; BUSINESS_CLASSIFICATION_UNAVAILABLE="BUSINESS_CLASSIFICATION_UNAVAILABLE"; GROWTH_CONSISTENCY_PARAMETER_UNAVAILABLE="GROWTH_CONSISTENCY_PARAMETER_UNAVAILABLE"; MARGIN_CASH_WORKING_CAPITAL_UNAVAILABLE="MARGIN_CASH_WORKING_CAPITAL_UNAVAILABLE"; DEBT_DILUTION_POLICY_UNAVAILABLE="DEBT_DILUTION_POLICY_UNAVAILABLE"; LIFECYCLE_CALIBRATION_UNAVAILABLE="LIFECYCLE_CALIBRATION_UNAVAILABLE"

@dataclass(frozen=True,slots=True)
class FundamentalCompounderResearchShadow:
    source_receipt:LongTermThesisResearchShadow; business_branch:FundamentalCompounderBusinessBranch; state:FundamentalCompounderState; reasons:tuple[FundamentalCompounderReason,...]
    result_id:str=field(init=False); fingerprint:str=field(init=False); contract_version:str=CONTRACT_VERSION; actionability:str="WATCH_ONLY"; execution_status:str="NON_EXECUTABLE"; research_status:str="RESEARCH_SHADOW_V1"
    def __post_init__(self):
        _validate(self); object.__setattr__(self,"result_id","fundamental-compounder:"+_hash(_identity(self))[:24]); object.__setattr__(self,"fingerprint","sha256:"+_hash(_payload(self)))
    def verify(self):
        _validate(self)
        if self.result_id!="fundamental-compounder:"+_hash(_identity(self))[:24]: raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_IDENTITY_MISMATCH")
        if self.fingerprint!="sha256:"+_hash(_payload(self)): raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_FINGERPRINT_MISMATCH")

def evaluate_fundamental_compounder_research_shadow(source_receipt:LongTermThesisResearchShadow,business_branch:FundamentalCompounderBusinessBranch)->FundamentalCompounderResearchShadow:
    if not isinstance(source_receipt,LongTermThesisResearchShadow) or not isinstance(business_branch,FundamentalCompounderBusinessBranch): raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_INPUT_INVALID")
    try: source_receipt.verify()
    except ValueError: return _result(source_receipt,business_branch,FundamentalCompounderState.DATA_INSUFFICIENT,(FundamentalCompounderReason.SOURCE_RECEIPT_UNVERIFIABLE,))
    if source_receipt.source_review.family is not LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER: raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_SOURCE_FAMILY_INVALID")
    if business_branch is not FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE:
        reason=FundamentalCompounderReason.BUSINESS_CLASSIFICATION_UNAVAILABLE if business_branch in {FundamentalCompounderBusinessBranch.UNKNOWN,FundamentalCompounderBusinessBranch.STRUCTURALLY_NON_COMPARABLE} else FundamentalCompounderReason.FINANCIAL_SECTOR_POLICY_UNAVAILABLE
        return _result(source_receipt,business_branch,FundamentalCompounderState.NOT_APPLICABLE,(reason,))
    if source_receipt.state is LongTermResearchShadowState.CONFLICTED: return _result(source_receipt,business_branch,FundamentalCompounderState.EVIDENCE_CONFLICTED,(FundamentalCompounderReason.SOURCE_EVIDENCE_CONFLICTED,))
    if source_receipt.state is LongTermResearchShadowState.TEMPORALLY_INVALID: return _result(source_receipt,business_branch,FundamentalCompounderState.DATA_INSUFFICIENT,(FundamentalCompounderReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,))
    if source_receipt.state in {LongTermResearchShadowState.DATA_INSUFFICIENT,LongTermResearchShadowState.UNVERIFIABLE}: return _result(source_receipt,business_branch,FundamentalCompounderState.DATA_INSUFFICIENT,(FundamentalCompounderReason.SOURCE_DATA_INSUFFICIENT,))
    return _result(source_receipt,business_branch,FundamentalCompounderState.POLICY_PARAMETER_UNAVAILABLE,(FundamentalCompounderReason.DEBT_DILUTION_POLICY_UNAVAILABLE,FundamentalCompounderReason.GROWTH_CONSISTENCY_PARAMETER_UNAVAILABLE,FundamentalCompounderReason.LIFECYCLE_CALIBRATION_UNAVAILABLE,FundamentalCompounderReason.MARGIN_CASH_WORKING_CAPITAL_UNAVAILABLE))
def fundamental_compounder_payload(value:FundamentalCompounderResearchShadow)->dict[str,object]: value.verify(); return _payload(value)|{"fingerprint":value.fingerprint}
def serialize_fundamental_compounder(value:FundamentalCompounderResearchShadow)->str: return json.dumps(fundamental_compounder_payload(value),sort_keys=True,separators=(",",":"),ensure_ascii=True)
def _result(s,b,state,reasons): return FundamentalCompounderResearchShadow(s,b,state,tuple(sorted(set(reasons),key=lambda x:x.value)))
def _validate(v):
    if not isinstance(v.source_receipt,LongTermThesisResearchShadow) or not isinstance(v.business_branch,FundamentalCompounderBusinessBranch) or not isinstance(v.state,FundamentalCompounderState): raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_CONTRACT_INVALID")
    if v.reasons!=tuple(sorted(set(v.reasons),key=lambda x:x.value)) or not all(isinstance(x,FundamentalCompounderReason) for x in v.reasons): raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_REASONS_NONCANONICAL")
    if v.contract_version!=CONTRACT_VERSION or (v.actionability,v.execution_status,v.research_status)!=("WATCH_ONLY","NON_EXECUTABLE","RESEARCH_SHADOW_V1"): raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_BOUNDARY_INVALID")
    if v.state in {FundamentalCompounderState.SHADOW_CANDIDATE,FundamentalCompounderState.SHADOW_NOT_QUALIFIED}: raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_V1_POSITIVE_STATE_FORBIDDEN")
    if v.state is FundamentalCompounderState.NOT_APPLICABLE and v.business_branch is FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE: raise FundamentalCompounderResearchShadowError("FUNDAMENTAL_COMPOUNDER_BRANCH_STATE_CONTRADICTION")
def _identity(v):
    s=v.source_receipt; return {"contract":v.contract_version,"family":"LONG_TERM_FUNDAMENTAL_COMPOUNDER","instrument":s.source_review.canonical_instrument_id,"as_of":s.source_review.context.as_of.astimezone(UTC).isoformat(),"receipt_id":s.receipt_id,"receipt_fingerprint":s.fingerprint,"branch":v.business_branch.value}
def _payload(v): return _identity(v)|{"state":v.state.value,"reasons":tuple(x.value for x in v.reasons),"result_id":v.result_id,"actionability":v.actionability,"execution_status":v.execution_status,"research_status":v.research_status}
def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
