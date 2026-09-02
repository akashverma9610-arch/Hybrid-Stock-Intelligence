from datetime import UTC, datetime
import pytest
from app.intelligence.external_intelligence import *

T=datetime(2026,1,2,tzinfo=UTC)
def event(title='TEST_RBI_POLICY_EVENT'):
 return ExternalEvent('HSI_EXTERNAL_INTELLIGENCE_DESK','test-rbi-1',EventType.MONETARY_POLICY,title,'IN','MACRO',Materiality.HIGH,T,PolicyStage.STATEMENT)
def evidence(value='first'):
 return EvidenceVersion(event(),T,T,T,value,'change',SourceEvidence('Synthetic','TEST','https://invalid.test',.9),(Fact('fact',('source',),.9),),(DataPoint('repo','25','bps','Q1',('source',)),),(Interpretation('meaning',.7),),(Inference('possible',.4),))
def test_synthetic_contracts_are_deterministic_and_distinct():
 a,b=evidence(),evidence(); assert a.event.canonical_event_id==b.event.canonical_event_id and a.evidence_version_id==b.evidence_version_id
 assert evidence('second').evidence_version_id!=a.evidence_version_id
 r=ReevaluationRequest(a.event.canonical_event_id,a.evidence_version_id,Materiality.HIGH,T); assert r.request_id==ReevaluationRequest(a.event.canonical_event_id,a.evidence_version_id,Materiality.HIGH,T).request_id
 assert 'inferences' in canonical(a) and 'facts' in canonical(a)
def test_domain_fails_closed_for_confidence_time_and_company_identity():
 with pytest.raises(ValueError): SourceEvidence('x','y',None,1.1)
 with pytest.raises(ValueError): ExternalEvent('p','id',EventType.MACRO_DATA,'t','IN','M',Materiality.LOW,datetime(2026,1,1))
 with pytest.raises(ValueError): CompanyExposure(None,None,ExposureType.DIRECT,.5)
 with pytest.raises(ValueError): CompanyExposure(None,'name',ExposureType.DIRECT,.5,'VERIFIED')
