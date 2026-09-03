from datetime import UTC,datetime,timedelta
from dataclasses import FrozenInstanceError
import pytest
from app.intelligence.fundamental_inflection_research_shadow import *
from app.intelligence.long_term_thesis_research_shadow import *
from app.intelligence.long_term_thesis_review import *
T=datetime(2026,9,3,10,tzinfo=UTC);FP="sha256:"+"a"*64
def receipt(state=ResearchShadowCoverageState.AVAILABLE):
 r=ThesisLineageReference("diagnostic:1",FP,T-timedelta(minutes=2));c=deep_analysis_dossier_candidate(canonical_instrument_id="NSE:INE000000001",dossier_id="brain-output:1",dossier_fingerprint=FP,source_policy_version="brain-output-v1",dossier_as_of=T-timedelta(minutes=3),available_at=T-timedelta(minutes=2),evidence_state=DossierEvidenceState.AVAILABLE,diagnostic_lineage=(r,),evidence_lineage=(ThesisLineageReference("evidence:1",FP,T-timedelta(minutes=2)),));review=review_long_term_thesis(LongTermThesisReviewContext(T,"brain-output-v1",FINGERPRINT_SCHEME),LongTermThesisFamily.FUNDAMENTAL_INFLECTION,c);return review_long_term_research_shadow(review,tuple(LongTermCoverageObservation(d,state,"coverage:"+d.value.lower(),FP,T-timedelta(minutes=1)) for d in required_coverage_domains(review.family)))
def test_valid_nonfinancial_is_policy_definition_missing():
 v=evaluate_fundamental_inflection_research_shadow(receipt(),FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE);assert v.state is FundamentalInflectionState.POLICY_DEFINITION_MISSING;assert v.actionability=="WATCH_ONLY" and v.execution_status=="NON_EXECUTABLE";assert len(v.reasons)==5
@pytest.mark.parametrize("b",tuple(x for x in FundamentalInflectionBusinessBranch if x is not FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE))
def test_nonindustrial_branches_not_applicable(b):assert evaluate_fundamental_inflection_research_shadow(receipt(),b).state is FundamentalInflectionState.NOT_APPLICABLE
@pytest.mark.parametrize(("s","out"),((ResearchShadowCoverageState.UNAVAILABLE,FundamentalInflectionState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.STALE,FundamentalInflectionState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.NON_COMPARABLE,FundamentalInflectionState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.CONFLICTED,FundamentalInflectionState.EVIDENCE_CONFLICTED)))
def test_evidence_states_fail_closed(s,out):assert evaluate_fundamental_inflection_research_shadow(receipt(s),FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE).state is out
def test_determinism_and_no_qualification_vocabulary():
 a=evaluate_fundamental_inflection_research_shadow(receipt(),FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE);b=evaluate_fundamental_inflection_research_shadow(receipt(),FundamentalInflectionBusinessBranch.NON_FINANCIAL_CORPORATE);assert a.result_id==b.result_id and serialize_fundamental_inflection(a)==serialize_fundamental_inflection(b)
 with pytest.raises(FrozenInstanceError):a.state=FundamentalInflectionState.DATA_INSUFFICIENT
 assert not {"SHADOW_CANDIDATE","SHADOW_NOT_QUALIFIED"}&{x.value for x in FundamentalInflectionState}
