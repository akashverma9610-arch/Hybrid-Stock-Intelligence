"""Fail-closed Fundamental Inflection Research Shadow V1 evidence projection."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC
from enum import StrEnum
import hashlib, json
from app.intelligence.long_term_thesis_research_shadow import LongTermResearchShadowState, LongTermThesisResearchShadow
from app.intelligence.long_term_thesis_review import LongTermThesisFamily

CONTRACT_VERSION="fundamental-inflection-research-shadow/v1"
class FundamentalInflectionResearchShadowError(ValueError): pass
class FundamentalInflectionBusinessBranch(StrEnum):
    NON_FINANCIAL_CORPORATE="NON_FINANCIAL_CORPORATE"; BANK="BANK"; NBFC="NBFC"; INSURER="INSURER"; STRUCTURALLY_NON_COMPARABLE="STRUCTURALLY_NON_COMPARABLE"; UNKNOWN="UNKNOWN"
class FundamentalInflectionState(StrEnum): DATA_INSUFFICIENT="DATA_INSUFFICIENT"; EVIDENCE_CONFLICTED="EVIDENCE_CONFLICTED"; POLICY_DEFINITION_MISSING="POLICY_DEFINITION_MISSING"; NOT_APPLICABLE="NOT_APPLICABLE"
class FundamentalInflectionReason(StrEnum):
    SOURCE_RECEIPT_UNVERIFIABLE="SOURCE_RECEIPT_UNVERIFIABLE"; SOURCE_RECEIPT_TEMPORALLY_INVALID="SOURCE_RECEIPT_TEMPORALLY_INVALID"; SOURCE_EVIDENCE_CONFLICTED="SOURCE_EVIDENCE_CONFLICTED"; SOURCE_DATA_INSUFFICIENT="SOURCE_DATA_INSUFFICIENT"; FINANCIAL_SECTOR_POLICY_UNAVAILABLE="FINANCIAL_SECTOR_POLICY_UNAVAILABLE"; BUSINESS_CLASSIFICATION_UNAVAILABLE="BUSINESS_CLASSIFICATION_UNAVAILABLE"; MOMENTUM_ACCELERATION_DEFINITION_MISSING="MOMENTUM_ACCELERATION_DEFINITION_MISSING"; SURPRISE_CONSENSUS_DEFINITION_MISSING="SURPRISE_CONSENSUS_DEFINITION_MISSING"; CONFIRMATION_BASE_EFFECT_DEFINITION_MISSING="CONFIRMATION_BASE_EFFECT_DEFINITION_MISSING"; REVISION_GUIDANCE_DEFINITION_MISSING="REVISION_GUIDANCE_DEFINITION_MISSING"; EVENT_REACTION_DEFINITION_MISSING="EVENT_REACTION_DEFINITION_MISSING"
@dataclass(frozen=True,slots=True)
class FundamentalInflectionResearchShadow:
    source_receipt:LongTermThesisResearchShadow; business_branch:FundamentalInflectionBusinessBranch; state:FundamentalInflectionState; reasons:tuple[FundamentalInflectionReason,...]
    result_id:str=field(init=False);fingerprint:str=field(init=False);contract_version:str=CONTRACT_VERSION;actionability:str="WATCH_ONLY";execution_status:str="NON_EXECUTABLE";research_status:str="RESEARCH_SHADOW_V1"
    def __post_init__(self): _validate(self);object.__setattr__(self,"result_id","fundamental-inflection:"+_hash(_identity(self))[:24]);object.__setattr__(self,"fingerprint","sha256:"+_hash(_payload(self)))
    def verify(self):
        _validate(self)
        if self.result_id!="fundamental-inflection:"+_hash(_identity(self))[:24]:raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_IDENTITY_MISMATCH")
        if self.fingerprint!="sha256:"+_hash(_payload(self)):raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_FINGERPRINT_MISMATCH")
def evaluate_fundamental_inflection_research_shadow(source_receipt:LongTermThesisResearchShadow,business_branch:FundamentalInflectionBusinessBranch)->FundamentalInflectionResearchShadow:
    if not isinstance(source_receipt,LongTermThesisResearchShadow) or not isinstance(business_branch,FundamentalInflectionBusinessBranch):raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_INPUT_INVALID")
    try:source_receipt.verify()
    except ValueError:return _result(source_receipt,business_branch,FundamentalInflectionState.DATA_INSUFFICIENT,(FundamentalInflectionReason.SOURCE_RECEIPT_UNVERIFIABLE,))
    if source_receipt.source_review.family is not LongTermThesisFamily.FUNDAMENTAL_INFLECTION:raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_SOURCE_FAMILY_INVALID")
    if business_branch is not FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE:
        r=FundamentalInflectionReason.BUSINESS_CLASSIFICATION_UNAVAILABLE if business_branch in {FundamentalInflectionBusinessBranch.UNKNOWN,FundamentalInflectionBusinessBranch.STRUCTURALLY_NON_COMPARABLE} else FundamentalInflectionReason.FINANCIAL_SECTOR_POLICY_UNAVAILABLE;return _result(source_receipt,business_branch,FundamentalInflectionState.NOT_APPLICABLE,(r,))
    if source_receipt.state is LongTermResearchShadowState.CONFLICTED:return _result(source_receipt,business_branch,FundamentalInflectionState.EVIDENCE_CONFLICTED,(FundamentalInflectionReason.SOURCE_EVIDENCE_CONFLICTED,))
    if source_receipt.state is LongTermResearchShadowState.TEMPORALLY_INVALID:return _result(source_receipt,business_branch,FundamentalInflectionState.DATA_INSUFFICIENT,(FundamentalInflectionReason.SOURCE_RECEIPT_TEMPORALLY_INVALID,))
    if source_receipt.state in {LongTermResearchShadowState.DATA_INSUFFICIENT,LongTermResearchShadowState.UNVERIFIABLE}:return _result(source_receipt,business_branch,FundamentalInflectionState.DATA_INSUFFICIENT,(FundamentalInflectionReason.SOURCE_DATA_INSUFFICIENT,))
    return _result(source_receipt,business_branch,FundamentalInflectionState.POLICY_DEFINITION_MISSING,(FundamentalInflectionReason.CONFIRMATION_BASE_EFFECT_DEFINITION_MISSING,FundamentalInflectionReason.EVENT_REACTION_DEFINITION_MISSING,FundamentalInflectionReason.MOMENTUM_ACCELERATION_DEFINITION_MISSING,FundamentalInflectionReason.REVISION_GUIDANCE_DEFINITION_MISSING,FundamentalInflectionReason.SURPRISE_CONSENSUS_DEFINITION_MISSING))
def fundamental_inflection_payload(v):v.verify();return _payload(v)|{"fingerprint":v.fingerprint}
def serialize_fundamental_inflection(v):return json.dumps(fundamental_inflection_payload(v),sort_keys=True,separators=(",",":"),ensure_ascii=True)
def _result(s,b,state,reasons):return FundamentalInflectionResearchShadow(s,b,state,tuple(sorted(set(reasons),key=lambda x:x.value)))
def _validate(v):
    if not isinstance(v.source_receipt,LongTermThesisResearchShadow) or not isinstance(v.business_branch,FundamentalInflectionBusinessBranch) or not isinstance(v.state,FundamentalInflectionState):raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_CONTRACT_INVALID")
    if v.reasons!=tuple(sorted(set(v.reasons),key=lambda x:x.value)) or not all(isinstance(x,FundamentalInflectionReason) for x in v.reasons):raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_REASONS_NONCANONICAL")
    if v.contract_version!=CONTRACT_VERSION or (v.actionability,v.execution_status,v.research_status)!=("WATCH_ONLY","NON_EXECUTABLE","RESEARCH_SHADOW_V1"):raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_BOUNDARY_INVALID")
    if v.state is FundamentalInflectionState.NOT_APPLICABLE and v.business_branch is FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE:raise FundamentalInflectionResearchShadowError("FUNDAMENTAL_INFLECTION_BRANCH_STATE_CONTRADICTION")
def _identity(v):
    s=v.source_receipt;return {"contract":v.contract_version,"family":"LONG_TERM_FUNDAMENTAL_INFLECTION","instrument":s.source_review.canonical_instrument_id,"as_of":s.source_review.context.as_of.astimezone(UTC).isoformat(),"receipt_id":s.receipt_id,"receipt_fingerprint":s.fingerprint,"branch":v.business_branch.value}
def _payload(v):return _identity(v)|{"state":v.state.value,"reasons":tuple(x.value for x in v.reasons),"result_id":v.result_id,"actionability":v.actionability,"execution_status":v.execution_status,"research_status":v.research_status}
def _hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
