from __future__ import annotations

from dataclasses import dataclass
from app.analysis.models import AnalysisStatus
from app.domain.models import EvidenceType
from app.research.models import ResearchSnapshot, SourceTier

@dataclass(frozen=True, slots=True)
class ResearchAnalysis:
    state:str; details:tuple[tuple[str,str],...]; input_ids:tuple[str,...]; status:AnalysisStatus; confidence:float|None

def as_of(snapshot:ResearchSnapshot, timestamp):
    docs=tuple(x for x in snapshot.documents if x.validation_eligible and x.publication_timestamp<=timestamp and x.retrieval_timestamp<=timestamp)
    doc_ids={x.research_item_id for x in docs}
    claims=tuple(x for x in snapshot.claims if x.research_item_id in doc_ids and x.publication_timestamp<=timestamp and x.extracted_at<=timestamp and x.reference)
    return ResearchSnapshot(timestamp,docs,claims,tuple(x for x in snapshot.guidance if x.research_item_id in doc_ids and x.publication_timestamp<=timestamp),tuple(x for x in snapshot.catalysts if x.research_item_id in doc_ids and x.announcement_timestamp<=timestamp))

def eligible_claims(snapshot:ResearchSnapshot):
    docs={x.research_item_id:x for x in snapshot.documents}; out=[]
    for claim in snapshot.claims:
        doc=docs.get(claim.research_item_id)
        if doc and doc.tier==claim.tier and claim.reference: out.append(claim)
    return tuple(out)

def _result(state, details, claims, confidence=1.0): return ResearchAnalysis(state,tuple(details),tuple(x.claim_id for x in claims),AnalysisStatus.VALID,confidence)
def _insufficient(): return ResearchAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INSUFFICIENT_DATA,None)

def moat(snapshot):
    claims=eligible_claims(snapshot); relevant=[x for x in claims if x.predicate in {"business_model","switching_cost","network_effect","brand","cost_advantage","regulatory_advantage","distribution","ip","market_share","customer_concentration","competitive_risk"}]
    if not relevant:return _insufficient()
    positive=[x for x in relevant if x.predicate not in {"customer_concentration","competitive_risk"} and x.tier in {SourceTier.TIER_1_PRIMARY,SourceTier.TIER_2_COMPANY}]
    negative=[x for x in relevant if x.predicate in {"customer_concentration","competitive_risk"}]
    state="STRONG" if len(positive)>=2 and not negative else "WEAK" if negative and not positive else "MODERATE" if positive else "UNCLEAR"
    return _result(state,tuple((x.predicate,x.reference) for x in relevant),relevant,.9 if positive else .6)

def governance(snapshot):
    claims=eligible_claims(snapshot); serious=[x for x in claims if x.predicate in {"auditor_qualification","auditor_resignation","regulatory_action","material_restatement"} and x.tier==SourceTier.TIER_1_PRIMARY]
    watch=[x for x in claims if x.predicate in {"auditor_change","related_party_issue","pledge"}]
    if not claims:return _insufficient()
    return _result("SEVERE_CONCERN" if any(x.predicate in {"auditor_resignation","regulatory_action"} for x in serious) else "CONCERN" if serious else "WATCH" if watch else "CLEAN",tuple((x.predicate,x.reference) for x in serious+watch),serious+watch,.95 if serious else .7)

def guidance_delivery(snapshot):
    items=snapshot.guidance
    completed=[x for x in items if x.actual is not None]
    if not completed:return _insufficient()
    outcomes=["EXCEEDED" if x.actual>x.expected else "MET" if x.actual==x.expected else "MISSED" for x in completed]
    state="REPEATEDLY_MISSED" if outcomes.count("MISSED")>=2 else "MIXED" if len(set(outcomes))>1 else outcomes[-1]
    return ResearchAnalysis(state,tuple((x.metric,f"expected={x.expected};actual={x.actual};period={x.period}") for x in completed),tuple(x.guidance_id for x in completed),AnalysisStatus.VALID,1.0)

def catalysts(snapshot):
    active=[x for x in snapshot.catalysts if not x.cancelled]
    if not active:return _insufficient()
    return ResearchAnalysis("ACTIVE_CATALYST" if any(not x.occurred for x in active) else "OCCURRED",tuple((x.category,f"{x.clock.value}:{x.description}") for x in active),tuple(x.catalyst_id for x in active),AnalysisStatus.VALID,1.0)
