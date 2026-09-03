"""Immutable, read-only provenance review over a Core Deep Analysis dossier."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re

CONTRACT_VERSION = "long-term-thesis-review/v1"
FINGERPRINT_SCHEME = "long-term-thesis-review/sha256/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_FP = re.compile(r"sha256:[0-9a-f]{64}")

class LongTermThesisReviewError(ValueError): pass
class LongTermThesisFamily(StrEnum):
    QUALITY_FAIR_VALUE="LONG_TERM_QUALITY_FAIR_VALUE"; FUNDAMENTAL_COMPOUNDER="LONG_TERM_FUNDAMENTAL_COMPOUNDER"
    FUNDAMENTAL_INFLECTION="LONG_TERM_FUNDAMENTAL_INFLECTION"; POLICY_TRANSMISSION="LONG_TERM_POLICY_TRANSMISSION"
    ASYMMETRIC_EMERGING_COMPOUNDER="LONG_TERM_ASYMMETRIC_EMERGING_COMPOUNDER"
class DossierEvidenceState(StrEnum): AVAILABLE="AVAILABLE"; UNAVAILABLE="UNAVAILABLE"; STALE="STALE"; CONFLICTED="CONFLICTED"; NON_COMPARABLE="NON_COMPARABLE"
class ThesisReviewState(StrEnum): DOSSIER_OBSERVED="DOSSIER_OBSERVED"; DATA_INSUFFICIENT="DATA_INSUFFICIENT"; CONFLICTED="CONFLICTED"; TEMPORALLY_INVALID="TEMPORALLY_INVALID"; UNVERIFIABLE="UNVERIFIABLE"
class ThesisPolicyAvailability(StrEnum): POLICY_UNAVAILABLE="POLICY_UNAVAILABLE"; NOT_EVALUATED="NOT_EVALUATED"
class ThesisReason(StrEnum):
    DOSSIER_UNVERIFIABLE="DOSSIER_UNVERIFIABLE"; DOSSIER_AFTER_AS_OF="DOSSIER_AFTER_AS_OF"; LINEAGE_AFTER_AS_OF="LINEAGE_AFTER_AS_OF"
    LINEAGE_CONFLICTED="LINEAGE_CONFLICTED"; EVIDENCE_UNAVAILABLE="EVIDENCE_UNAVAILABLE"; EVIDENCE_STALE="EVIDENCE_STALE"; EVIDENCE_NON_COMPARABLE="EVIDENCE_NON_COMPARABLE"
    FAMILY_POLICY_UNAVAILABLE="FAMILY_POLICY_UNAVAILABLE"

@dataclass(frozen=True, slots=True)
class ThesisLineageReference:
    reference_id: str; fingerprint: str; available_at: datetime
    def __post_init__(self): _id(self.reference_id,"THESIS_LINEAGE_ID_INVALID"); _fp(self.fingerprint,"THESIS_LINEAGE_FINGERPRINT_INVALID"); _aware(self.available_at,"THESIS_LINEAGE_TIMESTAMP_INVALID")

@dataclass(frozen=True, slots=True)
class DeepAnalysisDossierCandidate:
    canonical_instrument_id: str; dossier_id: str; dossier_fingerprint: str; source_policy_version: str
    dossier_as_of: datetime; available_at: datetime; evidence_state: DossierEvidenceState
    diagnostic_lineage: tuple[ThesisLineageReference,...]; evidence_lineage: tuple[ThesisLineageReference,...]
    stored_fingerprint: str; fingerprint_scheme: str=FINGERPRINT_SCHEME
    def __post_init__(self):
        for value,code in ((self.canonical_instrument_id,"THESIS_INSTRUMENT_ID_INVALID"),(self.dossier_id,"THESIS_DOSSIER_ID_INVALID")): _id(value,code)
        _fp(self.dossier_fingerprint,"THESIS_DOSSIER_FINGERPRINT_INVALID"); _text(self.source_policy_version,"THESIS_POLICY_VERSION_INVALID")
        _aware(self.dossier_as_of,"THESIS_DOSSIER_TIMESTAMP_INVALID"); _aware(self.available_at,"THESIS_DOSSIER_TIMESTAMP_INVALID")
        if not isinstance(self.evidence_state,DossierEvidenceState): raise LongTermThesisReviewError("THESIS_EVIDENCE_STATE_INVALID")
        _lineage(self.diagnostic_lineage,"THESIS_DIAGNOSTIC_LINEAGE"); _lineage(self.evidence_lineage,"THESIS_EVIDENCE_LINEAGE")
        _fp(self.stored_fingerprint,"THESIS_STORED_FINGERPRINT_INVALID"); _text(self.fingerprint_scheme,"THESIS_FINGERPRINT_SCHEME_INVALID")

def deep_analysis_dossier_candidate(**values) -> DeepAnalysisDossierCandidate:
    values={**values,"dossier_as_of":_utc(values["dossier_as_of"]),"available_at":_utc(values["available_at"]),"diagnostic_lineage":_canon(values["diagnostic_lineage"],"THESIS_DIAGNOSTIC_LINEAGE"),"evidence_lineage":_canon(values["evidence_lineage"],"THESIS_EVIDENCE_LINEAGE"),"stored_fingerprint":"sha256:"+"0"*64}
    result=DeepAnalysisDossierCandidate(**values); return DeepAnalysisDossierCandidate(**{**{name:getattr(result,name) for name in result.__dataclass_fields__},"stored_fingerprint":"sha256:"+_hash(_candidate_payload(result))})

@dataclass(frozen=True, slots=True)
class LongTermThesisReviewContext:
    as_of: datetime; expected_source_policy_version: str; expected_fingerprint_scheme: str=FINGERPRINT_SCHEME
    def __post_init__(self): _aware(self.as_of,"THESIS_CONTEXT_TIMESTAMP_INVALID"); _text(self.expected_source_policy_version,"THESIS_CONTEXT_POLICY_VERSION_INVALID"); _text(self.expected_fingerprint_scheme,"THESIS_CONTEXT_FINGERPRINT_SCHEME_INVALID")

@dataclass(frozen=True, slots=True)
class LongTermThesisReview:
    context: LongTermThesisReviewContext; family: LongTermThesisFamily; review_state: ThesisReviewState; policy_availability: ThesisPolicyAvailability
    canonical_instrument_id: str; dossier_id: str; dossier_fingerprint: str; dossier_as_of: datetime
    diagnostic_lineage: tuple[ThesisLineageReference,...]; evidence_lineage: tuple[ThesisLineageReference,...]; blockers: tuple[ThesisReason,...]
    review_id: str=field(init=False); fingerprint: str=field(init=False); contract_version: str=CONTRACT_VERSION
    def __post_init__(self):
        _validate(self); object.__setattr__(self,"review_id","long-term-thesis:"+_hash(_identity(self))[:24]); object.__setattr__(self,"fingerprint","sha256:"+_hash(_payload(self)))
    def verify(self):
        _validate(self)
        if self.review_id != "long-term-thesis:"+_hash(_identity(self))[:24]: raise LongTermThesisReviewError("THESIS_REVIEW_IDENTITY_MISMATCH")
        if self.fingerprint != "sha256:"+_hash(_payload(self)): raise LongTermThesisReviewError("THESIS_REVIEW_FINGERPRINT_MISMATCH")

def review_long_term_thesis(context: LongTermThesisReviewContext, family: LongTermThesisFamily, candidate: DeepAnalysisDossierCandidate) -> LongTermThesisReview:
    if not isinstance(context,LongTermThesisReviewContext) or not isinstance(family,LongTermThesisFamily) or not isinstance(candidate,DeepAnalysisDossierCandidate): raise LongTermThesisReviewError("THESIS_REVIEW_INPUT_INVALID")
    reasons=[]
    if candidate.fingerprint_scheme!=context.expected_fingerprint_scheme or candidate.source_policy_version!=context.expected_source_policy_version or candidate.stored_fingerprint!="sha256:"+_hash(_candidate_payload(candidate)): reasons=[ThesisReason.DOSSIER_UNVERIFIABLE]
    elif candidate.dossier_as_of>context.as_of or candidate.available_at>context.as_of: reasons=[ThesisReason.DOSSIER_AFTER_AS_OF]
    elif any(x.available_at>context.as_of for x in (*candidate.diagnostic_lineage,*candidate.evidence_lineage)): reasons=[ThesisReason.LINEAGE_AFTER_AS_OF]
    elif candidate.evidence_state is DossierEvidenceState.CONFLICTED: reasons=[ThesisReason.LINEAGE_CONFLICTED]
    elif candidate.evidence_state is DossierEvidenceState.UNAVAILABLE: reasons=[ThesisReason.EVIDENCE_UNAVAILABLE]
    elif candidate.evidence_state is DossierEvidenceState.STALE: reasons=[ThesisReason.EVIDENCE_STALE]
    elif candidate.evidence_state is DossierEvidenceState.NON_COMPARABLE: reasons=[ThesisReason.EVIDENCE_NON_COMPARABLE]
    state=ThesisReviewState.DOSSIER_OBSERVED if not reasons else (ThesisReviewState.UNVERIFIABLE if reasons[0] is ThesisReason.DOSSIER_UNVERIFIABLE else ThesisReviewState.TEMPORALLY_INVALID if reasons[0] in {ThesisReason.DOSSIER_AFTER_AS_OF,ThesisReason.LINEAGE_AFTER_AS_OF} else ThesisReviewState.CONFLICTED if reasons[0] is ThesisReason.LINEAGE_CONFLICTED else ThesisReviewState.DATA_INSUFFICIENT)
    policy=ThesisPolicyAvailability.POLICY_UNAVAILABLE if state is ThesisReviewState.DOSSIER_OBSERVED else ThesisPolicyAvailability.NOT_EVALUATED
    return LongTermThesisReview(context,family,state,policy,candidate.canonical_instrument_id,candidate.dossier_id,candidate.dossier_fingerprint,candidate.dossier_as_of,candidate.diagnostic_lineage,candidate.evidence_lineage,tuple(sorted((*reasons,*( (ThesisReason.FAMILY_POLICY_UNAVAILABLE,) if policy is ThesisPolicyAvailability.POLICY_UNAVAILABLE else ())),key=lambda x:x.value)))

def thesis_review_payload(value: LongTermThesisReview)->dict[str,object]: value.verify(); return _payload(value)|{"fingerprint":value.fingerprint}
def serialize_thesis_review(value: LongTermThesisReview)->str: return json.dumps(thesis_review_payload(value),sort_keys=True,separators=(",",":"),ensure_ascii=True)
def _validate(value):
    if value.contract_version!=CONTRACT_VERSION or not all(isinstance(x,t) for x,t in ((value.context,LongTermThesisReviewContext),(value.family,LongTermThesisFamily),(value.review_state,ThesisReviewState),(value.policy_availability,ThesisPolicyAvailability))): raise LongTermThesisReviewError("THESIS_REVIEW_CONTRACT_INVALID")
    _id(value.canonical_instrument_id,"THESIS_INSTRUMENT_ID_INVALID"); _id(value.dossier_id,"THESIS_DOSSIER_ID_INVALID"); _fp(value.dossier_fingerprint,"THESIS_DOSSIER_FINGERPRINT_INVALID"); _aware(value.dossier_as_of,"THESIS_DOSSIER_TIMESTAMP_INVALID")
    _lineage(value.diagnostic_lineage,"THESIS_DIAGNOSTIC_LINEAGE"); _lineage(value.evidence_lineage,"THESIS_EVIDENCE_LINEAGE")
    if value.blockers!=tuple(sorted(set(value.blockers),key=lambda x:x.value)) or not all(isinstance(x,ThesisReason) for x in value.blockers): raise LongTermThesisReviewError("THESIS_BLOCKERS_NONCANONICAL")
    if value.review_state is ThesisReviewState.DOSSIER_OBSERVED:
        if value.policy_availability is not ThesisPolicyAvailability.POLICY_UNAVAILABLE or value.blockers!=(ThesisReason.FAMILY_POLICY_UNAVAILABLE,): raise LongTermThesisReviewError("THESIS_POLICY_AVAILABILITY_CONTRADICTION")
    elif value.policy_availability is not ThesisPolicyAvailability.NOT_EVALUATED or ThesisReason.FAMILY_POLICY_UNAVAILABLE in value.blockers: raise LongTermThesisReviewError("THESIS_POLICY_AVAILABILITY_CONTRADICTION")
def _candidate_payload(v): return {"instrument":v.canonical_instrument_id,"dossier":v.dossier_id,"dossier_fingerprint":v.dossier_fingerprint,"source_policy":v.source_policy_version,"as_of":_time(v.dossier_as_of),"available_at":_time(v.available_at),"state":v.evidence_state.value,"diagnostics":tuple(_ref(x) for x in v.diagnostic_lineage),"evidence":tuple(_ref(x) for x in v.evidence_lineage),"scheme":v.fingerprint_scheme}
def _identity(v): return {"contract":v.contract_version,"instrument":v.canonical_instrument_id,"family":v.family.value,"as_of":_time(v.context.as_of),"dossier":v.dossier_id,"dossier_fingerprint":v.dossier_fingerprint,"source_policy":v.context.expected_source_policy_version}
def _payload(v): return _identity(v)|{"state":v.review_state.value,"policy":v.policy_availability.value,"dossier_as_of":_time(v.dossier_as_of),"diagnostics":tuple(_ref(x) for x in v.diagnostic_lineage),"evidence":tuple(_ref(x) for x in v.evidence_lineage),"blockers":tuple(x.value for x in v.blockers),"review_id":v.review_id}
def _ref(v): return {"id":v.reference_id,"fingerprint":v.fingerprint,"available_at":_time(v.available_at)}
def _canon(values,code):
    if not values or not all(isinstance(x,ThesisLineageReference) for x in values) or len({x.reference_id for x in values})!=len(values): raise LongTermThesisReviewError(code+"_INVALID")
    return tuple(sorted(values,key=lambda x:(x.reference_id,x.fingerprint,_time(x.available_at))))
def _lineage(values,code):
    if not values or not all(isinstance(x,ThesisLineageReference) for x in values) or len({x.reference_id for x in values})!=len(values): raise LongTermThesisReviewError(code+"_INVALID")
    if tuple(values)!=tuple(sorted(values,key=lambda x:(x.reference_id,x.fingerprint,_time(x.available_at)))): raise LongTermThesisReviewError(code+"_NONCANONICAL")
def _id(v,c):
    if not isinstance(v,str) or not _ID.fullmatch(v): raise LongTermThesisReviewError(c)
def _fp(v,c):
    if not isinstance(v,str) or not _FP.fullmatch(v): raise LongTermThesisReviewError(c)
def _text(v,c):
    if not isinstance(v,str) or not v.strip() or v!=v.strip(): raise LongTermThesisReviewError(c)
def _aware(v,c):
    if not isinstance(v,datetime) or v.tzinfo is None or v.utcoffset() is None: raise LongTermThesisReviewError(c)
def _utc(v): _aware(v,"THESIS_TIMESTAMP_INVALID"); return v.astimezone(UTC)
def _time(v): return _utc(v).isoformat()
def _hash(v): return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
