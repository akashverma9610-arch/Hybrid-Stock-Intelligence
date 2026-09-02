"""Pure V1B1 external-intelligence contracts; no transport or persistence."""
from __future__ import annotations
import hashlib, json, re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum

class EventType(StrEnum): GOVERNMENT_POLICY='GOVERNMENT_POLICY'; REGULATORY='REGULATORY'; MONETARY_POLICY='MONETARY_POLICY'; MACRO_DATA='MACRO_DATA'; GEOPOLITICAL='GEOPOLITICAL'; COMMODITY='COMMODITY'; SECTOR='SECTOR'; CORPORATE_DISCLOSURE='CORPORATE_DISCLOSURE'; ORDER_WIN='ORDER_WIN'; CAPEX='CAPEX'; M_AND_A='M_AND_A'; GUIDANCE='GUIDANCE'; EARNINGS='EARNINGS'; GOVERNANCE='GOVERNANCE'; SUPPLY_CHAIN='SUPPLY_CHAIN'; OTHER_MATERIAL='OTHER_MATERIAL'
class Materiality(StrEnum): CRITICAL='CRITICAL'; HIGH='HIGH'; MEDIUM='MEDIUM'; LOW='LOW'; NOISE='NOISE'
class PolicyStage(StrEnum): RUMOUR='RUMOUR'; STATEMENT='STATEMENT'; POLICY_INTENT='POLICY_INTENT'; CONSULTATION='CONSULTATION'; DRAFT='DRAFT'; CABINET_APPROVED='CABINET_APPROVED'; BILL_INTRODUCED='BILL_INTRODUCED'; BILL_PASSED='BILL_PASSED'; ACT_ENACTED='ACT_ENACTED'; NOTIFIED='NOTIFIED'; RULES_ISSUED='RULES_ISSUED'; IMPLEMENTATION='IMPLEMENTATION'; TENDER='TENDER'; ORDER='ORDER'
class ReevaluationState(StrEnum): PENDING='PENDING'; PROCESSING='PROCESSING'; COMPLETED='COMPLETED'; FAILED='FAILED'
class IdentityDisposition(StrEnum): NEW_EVENT='NEW_EVENT'; SAME_EVENT_SAME_EVIDENCE='SAME_EVENT_SAME_EVIDENCE'; SAME_EVENT_NEW_EVIDENCE='SAME_EVENT_NEW_EVIDENCE'; CONFLICTING_EVENT_IDENTITY='CONFLICTING_EVENT_IDENTITY'
class ExposureType(StrEnum): DIRECT='DIRECT'; SUPPLY_CHAIN='SUPPLY_CHAIN'; SECOND_ORDER='SECOND_ORDER'; THEMATIC='THEMATIC'; UNCERTAIN='UNCERTAIN'; NONE='NONE'

def _aware(value):
 if value.tzinfo is None or value.utcoffset() is None: raise ValueError('timezone-aware timestamp required')
def _confidence(value):
 if not 0<=value<=1: raise ValueError('confidence must be within 0.0-1.0')
def canonical(value):
 def convert(v):
  if isinstance(v,datetime): _aware(v); return v.isoformat()
  if isinstance(v,StrEnum): return v.value
  if hasattr(v,'__dataclass_fields__'): return {k:convert(getattr(v,k)) for k in v.__dataclass_fields__}
  if isinstance(v,tuple): return [convert(x) for x in v]
  return v
 return json.dumps(convert(value),sort_keys=True,separators=(',',':'))
def digest(value): return 'sha256:'+hashlib.sha256(canonical(value).encode()).hexdigest()
def _id(kind,value): return kind+':'+hashlib.sha256(canonical(value).encode()).hexdigest()[:24]

@dataclass(frozen=True,slots=True)
class SourceEvidence:
 source_name:str; source_type:str; source_reference:str|None; source_confidence:float
 def __post_init__(self):
  if not self.source_name or not self.source_type: raise ValueError('source fields required')
  _confidence(self.source_confidence)
@dataclass(frozen=True,slots=True)
class Fact:
 content:str; source_references:tuple[str,...]; confidence:float
 def __post_init__(self): _confidence(self.confidence)
@dataclass(frozen=True,slots=True)
class DataPoint: name:str; value:str; unit:str|None; period:str|None; source_references:tuple[str,...]
@dataclass(frozen=True,slots=True)
class Interpretation:
 content:str; confidence:float
 def __post_init__(self): _confidence(self.confidence)
@dataclass(frozen=True,slots=True)
class Inference:
 conclusion:str; confidence:float; verification_status:str='UNVERIFIED_INFERENCE'
 def __post_init__(self): _confidence(self.confidence)
@dataclass(frozen=True,slots=True)
class CompanyExposure:
 canonical_instrument_id:str|None; external_company_name:str|None; exposure_type:ExposureType; confidence:float; verification_status:str='UNVERIFIED_INFERENCE'
 def __post_init__(self):
  _confidence(self.confidence)
  if not self.canonical_instrument_id and not self.external_company_name: raise ValueError('company exposure requires an identity')
  if self.verification_status=='VERIFIED' and not self.canonical_instrument_id: raise ValueError('verified exposure requires canonical identity')
@dataclass(frozen=True,slots=True)
class ExternalEvent:
 producer_id:str; producer_event_id:str; event_type:EventType; title:str; country:str; domain:str; materiality:Materiality; first_received_at:datetime; policy_stage:PolicyStage|None=None; schema_version:str='hsi-external-intelligence-event/v1'
 def __post_init__(self):
  if self.schema_version!='hsi-external-intelligence-event/v1' or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}',self.producer_event_id): raise ValueError('invalid event identity')
  _aware(self.first_received_at)
 @property
 def fingerprint(self): return digest((self.producer_id,self.producer_event_id,self.schema_version,self.event_type,self.country,self.domain))
 @property
 def canonical_event_id(self): return _id('external-event',(self.producer_id,self.producer_event_id,self.fingerprint))
@dataclass(frozen=True,slots=True)
class EvidenceVersion:
 event:ExternalEvent; received_at:datetime; published_at:datetime; discovered_at:datetime; summary:str; what_changed:str; primary_source:SourceEvidence; facts:tuple[Fact,...]=(); data_points:tuple[DataPoint,...]=(); interpretation:tuple[Interpretation,...]=(); inferences:tuple[Inference,...]=(); supporting_sources:tuple[SourceEvidence,...]=(); company_exposures:tuple[CompanyExposure,...]=(); event_confidence:float|None=None; exposure_confidence:float|None=None; time_horizon:str|None=None; risks:tuple[str,...]=(); counter_evidence:tuple[str,...]=(); why_hsi_should_care:str|None=None; effective_at:datetime|None=None; affected_sectors:tuple[str,...]=(); affected_industries:tuple[str,...]=()
 def __post_init__(self):
  for x in (self.received_at,self.published_at,self.discovered_at): _aware(x)
  if self.effective_at is not None: _aware(self.effective_at)
  if self.event_confidence is not None: _confidence(self.event_confidence)
  if self.exposure_confidence is not None: _confidence(self.exposure_confidence)
  if self.discovered_at<self.published_at: raise ValueError('discovered_at precedes published_at')
 @property
 def fingerprint(self): return digest((self.event.canonical_event_id,self.published_at,self.discovered_at,self.summary,self.what_changed,self.primary_source,self.facts,self.data_points,self.interpretation,self.inferences,self.supporting_sources,self.company_exposures,self.event_confidence,self.exposure_confidence,self.time_horizon,self.risks,self.counter_evidence,self.why_hsi_should_care,self.effective_at,self.affected_sectors,self.affected_industries))
 @property
 def evidence_version_id(self): return _id('external-evidence',(self.event.canonical_event_id,self.fingerprint))
@dataclass(frozen=True,slots=True)
class ReevaluationRequest:
 canonical_event_id:str; evidence_version_id:str; materiality:Materiality; requested_at:datetime; affected_canonical_instruments:tuple[str,...]=(); affected_sectors:tuple[str,...]=(); affected_industries:tuple[str,...]=(); processing_state:ReevaluationState=ReevaluationState.PENDING; blocker:str|None=None
 def __post_init__(self): _aware(self.requested_at)
 @property
 def request_id(self): return _id('intelligence-reevaluation',(self.canonical_event_id,self.evidence_version_id,self.materiality))
def classify(existing:ExternalEvent|None,evidence_fingerprint:str,event:ExternalEvent)->IdentityDisposition:
 if existing is None:return IdentityDisposition.NEW_EVENT
 if existing.fingerprint!=event.fingerprint:return IdentityDisposition.CONFLICTING_EVENT_IDENTITY
 return IdentityDisposition.SAME_EVENT_SAME_EVIDENCE if evidence_fingerprint=='' else IdentityDisposition.SAME_EVENT_NEW_EVIDENCE
