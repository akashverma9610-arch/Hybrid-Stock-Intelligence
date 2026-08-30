from datetime import UTC, datetime, timedelta

import pytest

from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import EvidenceType
from app.research.engine import as_of, eligible_claims
from app.research.models import Catalyst, CatalystClock, GuidanceItem, ResearchClaim, ResearchDocument, ResearchSnapshot, ResearchSourceType, SourceTier
from tests.fixtures.analytical_observations import STRATEGY_REFERENCE

T=datetime(2026,8,5,tzinfo=UTC)
def doc(i,tier=SourceTier.TIER_1_PRIMARY,when=T-timedelta(days=1)):
    return ResearchDocument(i,"stock",ResearchSourceType.EXCHANGE_FILING,"mock",i,when,when,"mock",f"ref://{i}",tier)
def claim(i,document,predicate,tier=None):
    return ResearchClaim(i,document.research_item_id,"stock",predicate,f"claim://{i}",EvidenceType.DATA,tier or document.tier,.9,document.publication_timestamp,document.publication_timestamp)
def base():
    filing=doc("filing"); mgmt=doc("management",SourceTier.TIER_2_COMPANY)
    return ResearchSnapshot(T,(filing,mgmt),(claim("switch",filing,"switching_cost"),claim("brand",mgmt,"brand")),(GuidanceItem("guide","management","revenue",100,"FY26",T-timedelta(days=1),"expects 100",.8,110,"actual"),),(Catalyst("win","filing","order_win","order win",T-timedelta(days=1),CatalystClock.NEAR_TERM,.8,"high","growth","positive"),))
def evaluate(rule,s):
    e=DeterministicDiagnosticEvaluators(); return {15:e.business_model_moat,23:e.corporate_governance,28:e.management_guidance,30:e.fundamental_catalysts}[rule](s,"stock",STRATEGY_REFERENCE,T)

@pytest.mark.parametrize("rule",(15,23,28,30))
def test_each_qualitative_rule_is_as_of_deterministic_and_excludes_future_material_research(rule):
    before=base(); future_doc=doc("future",when=T+timedelta(days=3)); future_claim=claim("future-concern",future_doc,"auditor_resignation")
    contaminated=ResearchSnapshot(T,before.documents+(future_doc,),before.claims+(future_claim,),before.guidance,before.catalysts)
    first,second=evaluate(rule,as_of(before,T)),evaluate(rule,as_of(contaminated,T))
    assert first==second and "future" not in repr(first)

def test_tier_one_filing_overrides_lower_tier_claim_but_keeps_it_as_contradiction_evidence():
    filing=doc("filing"); social=doc("social",SourceTier.TIER_5_SENTIMENT)
    snapshot=ResearchSnapshot(T,(filing,social),(claim("clean",filing,"auditor_clean"),claim("rumour",social,"regulatory_action",SourceTier.TIER_5_SENTIMENT)))
    result=evaluate(23,as_of(snapshot,T))
    assert result.record.result=="CLEAN" and {x.claim_id for x in eligible_claims(as_of(snapshot,T))}=={"clean","rumour"}

def test_unsupported_and_llm_style_claims_without_attributable_document_are_ineligible():
    snapshot=ResearchSnapshot(T,(),(ResearchClaim("unsupported","missing","stock","brand","ref://claim",EvidenceType.INFERENCE,SourceTier.TIER_2_COMPANY,.5,T,T),))
    assert evaluate(15,as_of(snapshot,T)).eligibility.value == "ineligible_missing_data"

def test_management_guidance_cannot_be_stored_as_a_fact():
    with pytest.raises(ValueError): ResearchClaim("bad","doc","stock","management_guidance","ref",EvidenceType.FACT,SourceTier.TIER_2_COMPANY,.5,T,T)
