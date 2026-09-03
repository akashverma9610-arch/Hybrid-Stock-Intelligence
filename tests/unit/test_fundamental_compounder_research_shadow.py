from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
import ast, inspect
from pathlib import Path
import pytest
import app.intelligence.fundamental_compounder_research_shadow as module
from app.intelligence.fundamental_compounder_research_shadow import *
from app.intelligence.long_term_thesis_research_shadow import *
from app.intelligence.long_term_thesis_review import *
T=datetime(2026,9,3,10,tzinfo=UTC); FP="sha256:"+"a"*64
def receipt(state=ResearchShadowCoverageState.AVAILABLE):
 r=ThesisLineageReference("diagnostic:1",FP,T-timedelta(minutes=2)); c=deep_analysis_dossier_candidate(canonical_instrument_id="NSE:INE000000001",dossier_id="brain-output:1",dossier_fingerprint=FP,source_policy_version="brain-output-v1",dossier_as_of=T-timedelta(minutes=3),available_at=T-timedelta(minutes=2),evidence_state=DossierEvidenceState.AVAILABLE,diagnostic_lineage=(r,),evidence_lineage=(ThesisLineageReference("evidence:1",FP,T-timedelta(minutes=2)),)); review=review_long_term_thesis(LongTermThesisReviewContext(T,"brain-output-v1",FINGERPRINT_SCHEME),LongTermThesisFamily.FUNDAMENTAL_COMPOUNDER,c); return review_long_term_research_shadow(review,tuple(LongTermCoverageObservation(d,state,"coverage:"+d.value.lower(),FP,T-timedelta(minutes=1)) for d in required_coverage_domains(review.family)))
def test_valid_nonfinancial_is_parameter_unavailable():
 v=evaluate_fundamental_compounder_research_shadow(receipt(),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE);assert v.state is FundamentalCompounderState.POLICY_PARAMETER_UNAVAILABLE;assert v.actionability=="WATCH_ONLY" and v.execution_status=="NON_EXECUTABLE"
@pytest.mark.parametrize("b",tuple(x for x in FundamentalCompounderBusinessBranch if x is not FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE))
def test_other_branches_are_not_applicable(b): assert evaluate_fundamental_compounder_research_shadow(receipt(),b).state is FundamentalCompounderState.NOT_APPLICABLE
@pytest.mark.parametrize(("s","out"),((ResearchShadowCoverageState.UNAVAILABLE,FundamentalCompounderState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.STALE,FundamentalCompounderState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.NON_COMPARABLE,FundamentalCompounderState.DATA_INSUFFICIENT),(ResearchShadowCoverageState.CONFLICTED,FundamentalCompounderState.EVIDENCE_CONFLICTED)))
def test_evidence_fails_closed(s,out): assert evaluate_fundamental_compounder_research_shadow(receipt(s),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE).state is out
def test_identity_serialization_immutability_and_positive_rejection():
 a=evaluate_fundamental_compounder_research_shadow(receipt(),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE);b=evaluate_fundamental_compounder_research_shadow(receipt(),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE);assert a.result_id==b.result_id and serialize_fundamental_compounder(a)==serialize_fundamental_compounder(b)
 with pytest.raises(FrozenInstanceError): a.state=FundamentalCompounderState.SHADOW_CANDIDATE
 with pytest.raises(FundamentalCompounderResearchShadowError,match="POSITIVE_STATE_FORBIDDEN"): FundamentalCompounderResearchShadow(receipt(),FundamentalCompounderBusinessBranch.NON_FINANCIAL_CORPORATE,FundamentalCompounderState.SHADOW_CANDIDATE,())
def test_no_forbidden_dependencies_or_fields():
 s=Path(inspect.getfile(module)).read_text();imports={x.name for n in ast.walk(ast.parse(s)) if isinstance(n,ast.Import) for x in n.names}|{n.module or "" for n in ast.walk(ast.parse(s)) if isinstance(n,ast.ImportFrom)};assert not any(x.startswith(p) for x in imports for p in ("app.portfolio","app.storage","app.api","app.broker","app.orders","app.signals"));assert "datetime.now" not in s and not(set(FundamentalCompounderResearchShadow.__dataclass_fields__)&{"price","quantity","allocation","portfolio","order","broker","score","forecast"})
