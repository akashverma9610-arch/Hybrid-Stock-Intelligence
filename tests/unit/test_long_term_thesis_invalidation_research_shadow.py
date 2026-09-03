from datetime import UTC,datetime,timedelta
from dataclasses import FrozenInstanceError
import pytest
from app.intelligence.long_term_thesis_review import *
from app.intelligence.long_term_thesis_research_shadow import *
from app.intelligence.fundamental_compounder_research_shadow import *
from app.intelligence.fundamental_inflection_research_shadow import *
from app.intelligence.long_term_policy_transmission_research_shadow import *
from app.intelligence.external_intelligence import *
from app.intelligence.long_term_thesis_invalidation_research_shadow import *
T=datetime(2026,9,3,10,tzinfo=UTC);FP="sha256:"+"a"*64;I="NSE:INE000000001"
def source(family,state=ResearchShadowCoverageState.AVAILABLE):
 r=ThesisLineageReference("diagnostic:1",FP,T-timedelta(minutes=2));c=deep_analysis_dossier_candidate(canonical_instrument_id=I,dossier_id="dossier:1",dossier_fingerprint=FP,source_policy_version="brain-output-v1",dossier_as_of=T-timedelta(minutes=3),available_at=T-timedelta(minutes=2),evidence_state=DossierEvidenceState.AVAILABLE,diagnostic_lineage=(r,),evidence_lineage=(ThesisLineageReference("evidence:1",FP,T-timedelta(minutes=2)),));review=review_long_term_thesis(LongTermThesisReviewContext(T,"brain-output-v1","long-term-thesis-review/sha256/v1"),family,c);return review_long_term_research_shadow(review,tuple(LongTermCoverageObservation(d,state,"coverage:"+d.value.lower(),FP,T-timedelta(minutes=1)) for d in required_coverage_domains(family)))
def shadows(state=ResearchShadowCoverageState.AVAILABLE):
 c=evaluate_fundamental_compounder_research_shadow(source(LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER,state),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE)
 i=evaluate_fundamental_inflection_research_shadow(source(LongTermThesisFamily.FUNDAMENTAL_INFLECTION,state),FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE)
 return (c,i)
def test_missing_structured_assumptions_cannot_invalidate():
 values=shadows();v=review_long_term_thesis_invalidation(values);assert v.state is LongTermThesisLifecycleState.POLICY_DEFINITION_MISSING;assert LongTermThesisLifecycleReason.INVALIDATION_CONDITION_UNAVAILABLE in v.reasons
def test_missing_data_and_conflict_are_not_negative():
 assert review_long_term_thesis_invalidation(shadows(ResearchShadowCoverageState.UNAVAILABLE)).state is LongTermThesisLifecycleState.DATA_INSUFFICIENT
 assert review_long_term_thesis_invalidation(shadows(ResearchShadowCoverageState.CONFLICTED)).state is LongTermThesisLifecycleState.EVIDENCE_CONFLICTED
def test_deterministic_immutable_and_no_execution_surface():
 a=review_long_term_thesis_invalidation(shadows());b=review_long_term_thesis_invalidation(tuple(reversed(shadows())));assert a.lifecycle_id==b.lifecycle_id and serialize_long_term_thesis_lifecycle(a)==serialize_long_term_thesis_lifecycle(b)
 with pytest.raises(FrozenInstanceError):a.state=LongTermThesisLifecycleState.DATA_INSUFFICIENT
 assert not {"BUY","SELL","HOLD","INVALIDATION_CONFIRMED"}&{x.value for x in LongTermThesisLifecycleState}
def test_duplicate_and_malformed_inputs_fail_closed():
 with pytest.raises(LongTermThesisInvalidationResearchShadowError):review_long_term_thesis_invalidation((shadows()[0],shadows()[0]))
 with pytest.raises(LongTermThesisInvalidationResearchShadowError):review_long_term_thesis_invalidation(())
