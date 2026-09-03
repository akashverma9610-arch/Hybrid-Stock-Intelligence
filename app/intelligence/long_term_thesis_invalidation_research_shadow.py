"""Read-only Long-Term Thesis invalidation-readiness lifecycle V1."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import UTC
from enum import StrEnum
import hashlib, json

from app.intelligence.fundamental_compounder_research_shadow import FundamentalCompounderResearchShadow
from app.intelligence.fundamental_inflection_research_shadow import FundamentalInflectionResearchShadow
from app.intelligence.long_term_policy_transmission_research_shadow import PolicyTransmissionResearchShadow

CONTRACT_VERSION = "long-term-thesis-invalidation-research-shadow/v1"
_SHADOWS = (FundamentalCompounderResearchShadow, FundamentalInflectionResearchShadow, PolicyTransmissionResearchShadow)

class LongTermThesisInvalidationResearchShadowError(ValueError): pass
class LongTermThesisLifecycleState(StrEnum): DATA_INSUFFICIENT="DATA_INSUFFICIENT"; EVIDENCE_CONFLICTED="EVIDENCE_CONFLICTED"; POLICY_DEFINITION_MISSING="POLICY_DEFINITION_MISSING"; NOT_APPLICABLE="NOT_APPLICABLE"
class LongTermThesisLifecycleReason(StrEnum):
    SHADOW_RECEIPT_UNVERIFIABLE="SHADOW_RECEIPT_UNVERIFIABLE"; SHADOW_RECEIPT_TEMPORALLY_INVALID="SHADOW_RECEIPT_TEMPORALLY_INVALID"; SHADOW_EVIDENCE_CONFLICTED="SHADOW_EVIDENCE_CONFLICTED"; SHADOW_DATA_INSUFFICIENT="SHADOW_DATA_INSUFFICIENT"; SHADOW_NOT_APPLICABLE="SHADOW_NOT_APPLICABLE"; STRUCTURED_THESIS_ASSUMPTIONS_UNAVAILABLE="STRUCTURED_THESIS_ASSUMPTIONS_UNAVAILABLE"; INVALIDATION_CONDITION_UNAVAILABLE="INVALIDATION_CONDITION_UNAVAILABLE"; REVIEW_CADENCE_UNDEFINED="REVIEW_CADENCE_UNDEFINED"; EVIDENCE_FRESHNESS_POLICY_UNDEFINED="EVIDENCE_FRESHNESS_POLICY_UNDEFINED"; ASSUMPTION_MATERIALITY_UNDEFINED="ASSUMPTION_MATERIALITY_UNDEFINED"; CONFLICT_RESOLUTION_POLICY_UNDEFINED="CONFLICT_RESOLUTION_POLICY_UNDEFINED"; RECOVERY_REVALIDATION_POLICY_UNDEFINED="RECOVERY_REVALIDATION_POLICY_UNDEFINED"; THESIS_SUPERSESSION_POLICY_UNDEFINED="THESIS_SUPERSESSION_POLICY_UNDEFINED"; TEMPORARY_VS_STRUCTURAL_DEFINITION_UNDEFINED="TEMPORARY_VS_STRUCTURAL_DEFINITION_UNDEFINED"

@dataclass(frozen=True,slots=True)
class LongTermThesisInvalidationResearchShadow:
    shadows:tuple[object,...]; state:LongTermThesisLifecycleState; reasons:tuple[LongTermThesisLifecycleReason,...]
    lifecycle_id:str=field(init=False); fingerprint:str=field(init=False); contract_version:str=CONTRACT_VERSION; actionability:str="WATCH_ONLY"; execution_status:str="NON_EXECUTABLE"; research_status:str="RESEARCH_SHADOW_V1"
    def __post_init__(self):
        _validate(self); object.__setattr__(self,"lifecycle_id","long-term-thesis-lifecycle:"+_hash(_identity(self))[:24]); object.__setattr__(self,"fingerprint","sha256:"+_hash(_payload(self)))
    def verify(self):
        _validate(self)
        if self.lifecycle_id!="long-term-thesis-lifecycle:"+_hash(_identity(self))[:24]: raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_IDENTITY_MISMATCH")
        if self.fingerprint!="sha256:"+_hash(_payload(self)): raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_FINGERPRINT_MISMATCH")

def review_long_term_thesis_invalidation(shadows:tuple[object,...])->LongTermThesisInvalidationResearchShadow:
    canonical=_canonical(shadows)
    invalid=[]
    for value in canonical:
        try:value.verify()
        except ValueError: invalid.append(value)
    if invalid:return _result(canonical,LongTermThesisLifecycleState.DATA_INSUFFICIENT,(LongTermThesisLifecycleReason.SHADOW_RECEIPT_UNVERIFIABLE,))
    instruments={value.source_receipt.source_review.canonical_instrument_id for value in canonical}; asofs={value.source_receipt.source_review.context.as_of.astimezone(UTC) for value in canonical}
    if len(instruments)!=1 or len(asofs)!=1:raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_LINEAGE_MISMATCH")
    states={value.state.value for value in canonical}
    if "EVIDENCE_CONFLICTED" in states:return _result(canonical,LongTermThesisLifecycleState.EVIDENCE_CONFLICTED,(LongTermThesisLifecycleReason.SHADOW_EVIDENCE_CONFLICTED,))
    if any(value in {"DATA_INSUFFICIENT","TEMPORALLY_INVALID","UNVERIFIABLE"} for value in states):return _result(canonical,LongTermThesisLifecycleState.DATA_INSUFFICIENT,(LongTermThesisLifecycleReason.SHADOW_DATA_INSUFFICIENT,))
    if states=={"NOT_APPLICABLE"}:return _result(canonical,LongTermThesisLifecycleState.NOT_APPLICABLE,(LongTermThesisLifecycleReason.SHADOW_NOT_APPLICABLE,))
    return _result(canonical,LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING,(
        LongTermThesisLifecycleReason.ASSUMPTION_MATERIALITY_UNDEFINED,LongTermThesisLifecycleReason.CONFLICT_RESOLUTION_POLICY_UNDEFINED,LongTermThesisLifecycleReason.EVIDENCE_FRESHNESS_POLICY_UNDEFINED,LongTermThesisLifecycleReason.INVALIDATION_CONDITION_UNAVAILABLE,LongTermThesisLifecycleReason.RECOVERY_REVALIDATION_POLICY_UNDEFINED,LongTermThesisLifecycleReason.REVIEW_CADENCE_UNDEFINED,LongTermThesisLifecycleReason.STRUCTURED_THESIS_ASSUMPTIONS_UNAVAILABLE,LongTermThesisLifecycleReason.TEMPORARY_VS_STRUCTURAL_DEFINITION_UNDEFINED,LongTermThesisLifecycleReason.THESIS_SUPERSESSION_POLICY_UNDEFINED))

def lifecycle_payload(value):value.verify();return _payload(value)|{"fingerprint":value.fingerprint}
def serialize_long_term_thesis_lifecycle(value):return json.dumps(lifecycle_payload(value),sort_keys=True,separators=(",",":"),ensure_ascii=True)
def _result(s,state,reasons):return LongTermThesisInvalidationResearchShadow(s,state,tuple(sorted(set(reasons),key=lambda x:x.value)))
def _canonical(values):
    if not values or not all(isinstance(x,_SHADOWS) for x in values):raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_SHADOWS_INVALID")
    if len({type(x) for x in values})!=len(values):raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_FAMILY_DUPLICATE")
    return tuple(sorted(values,key=lambda x:(x.source_receipt.source_review.family.value,x.result_id,x.fingerprint)))
def _validate(v):
    if not isinstance(v.state,LongTermThesisLifecycleState) or v.shadows!=_canonical(v.shadows):raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_CONTRACT_INVALID")
    if v.reasons!=tuple(sorted(set(v.reasons),key=lambda x:x.value)) or not all(isinstance(x,LongTermThesisLifecycleReason) for x in v.reasons):raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_REASONS_INVALID")
    if (v.contract_version,v.actionability,v.execution_status,v.research_status)!=(CONTRACT_VERSION,"WATCH_ONLY","NON_EXECUTABLE","RESEARCH_SHADOW_V1"):raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_BOUNDARY_INVALID")
    if v.state is LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING and LongTermThesisLifecycleReason.INVALIDATION_CONDITION_UNAVAILABLE not in v.reasons:raise LongTermThesisInvalidationResearchShadowError("THESIS_LIFECYCLE_STATE_REASON_CONTRADICTION")
def _identity(v):
    first=v.shadows[0].source_receipt.source_review
    return {"contract":v.contract_version,"instrument":first.canonical_instrument_id,"as_of":first.context.as_of.astimezone(UTC).isoformat(),"shadows":tuple({"family":x.source_receipt.source_review.family.value,"id":x.result_id,"fingerprint":x.fingerprint} for x in v.shadows)}
def _payload(v):return _identity(v)|{"state":v.state.value,"reasons":tuple(x.value for x in v.reasons),"lifecycle_id":v.lifecycle_id,"actionability":v.actionability,"execution_status":v.execution_status,"research_status":v.research_status}
def _hash(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
