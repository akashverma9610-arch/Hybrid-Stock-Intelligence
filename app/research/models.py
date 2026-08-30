from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.models import EvidenceType


class ResearchSourceType(StrEnum):
    EXCHANGE_FILING="exchange_filing"; REGULATORY_FILING="regulatory_filing"; ANNUAL_REPORT="annual_report"; RESULTS_RELEASE="results_release"; INVESTOR_PRESENTATION="investor_presentation"; EARNINGS_CALL="earnings_call"; MANAGEMENT_GUIDANCE="management_guidance"; AUDITOR_REPORT="auditor_report"; CREDIT_RATING="credit_rating"; FINANCIAL_NEWS="financial_news"; INDUSTRY_RESEARCH="industry_research"; COMPETITOR="competitor"; SOCIAL="social"
class SourceTier(StrEnum):
    TIER_1_PRIMARY="tier_1_primary"; TIER_2_COMPANY="tier_2_company"; TIER_3_HIGH_QUALITY_SECONDARY="tier_3_high_quality_secondary"; TIER_4_SECONDARY="tier_4_secondary"; TIER_5_SENTIMENT="tier_5_sentiment"
class ClaimResolution(StrEnum):
    UNRESOLVED="unresolved"; SUPPORTED="supported"; CONTRADICTED="contradicted"; SUPERSEDED="superseded"; PARTIALLY_SUPPORTED="partially_supported"
class CatalystClock(StrEnum): IMMEDIATE="immediate"; NEAR_TERM="near_term"; MEDIUM_TERM="medium_term"

@dataclass(frozen=True, slots=True)
class ResearchDocument:
    research_item_id:str; instrument_id:str; source_type:ResearchSourceType; source_name:str; source_identifier:str; publication_timestamp:datetime; retrieval_timestamp:datetime; title:str; content_reference:str; tier:SourceTier; validation_eligible:bool=True; effective_timestamp:datetime|None=None; supersedes_research_item_id:str|None=None
@dataclass(frozen=True, slots=True)
class ResearchClaim:
    claim_id:str; research_item_id:str; subject:str; predicate:str; reference:str; evidence_class:EvidenceType; tier:SourceTier; confidence:float|None; publication_timestamp:datetime; extracted_at:datetime; applicable_period:str|None=None; supporting_observation_ids:tuple[str,...]=(); contradicts_claim_id:str|None=None; supersedes_claim_id:str|None=None; resolution:ClaimResolution=ClaimResolution.UNRESOLVED
    def __post_init__(self):
        if not self.reference: raise ValueError("A claim requires a source/reference.")
        if self.predicate == "management_guidance" and self.evidence_class is EvidenceType.FACT: raise ValueError("Management guidance is commentary, not audited FACT.")
@dataclass(frozen=True, slots=True)
class GuidanceItem:
    guidance_id:str; research_item_id:str; metric:str; expected:float; period:str; publication_timestamp:datetime; wording:str; confidence:float|None; actual:float|None=None; actual_claim_id:str|None=None
@dataclass(frozen=True, slots=True)
class Catalyst:
    catalyst_id:str; research_item_id:str; category:str; description:str; announcement_timestamp:datetime; clock:CatalystClock; confidence:float|None; materiality:str; expected_business_impact:str; expected_earnings_impact:str; conditions:tuple[str,...]=(); occurred:bool=False; cancelled:bool=False
@dataclass(frozen=True, slots=True)
class ExpectationActual:
    expectation_id:str; actual_claim_id:str|None; expected:float; actual:float|None; metric:str; period:str; outcome:str
@dataclass(frozen=True, slots=True)
class ResearchSnapshot:
    as_of_timestamp:datetime; documents:tuple[ResearchDocument,...]; claims:tuple[ResearchClaim,...]; guidance:tuple[GuidanceItem,...]=(); catalysts:tuple[Catalyst,...]=()
