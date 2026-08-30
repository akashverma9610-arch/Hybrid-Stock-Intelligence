"""Event-centric catalyst context; good news is not an action recommendation."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.news.hardening import NewsEventCluster
from app.news.models import NewsSourceQuality


class CatalystType(StrEnum):
    ORDER_WIN="ORDER_WIN"; ORDER_CANCELLATION="ORDER_CANCELLATION"; CAPACITY_EXPANSION="CAPACITY_EXPANSION"; PLANT_COMMISSIONING="PLANT_COMMISSIONING"; CAPEX="CAPEX"; M_AND_A="M_AND_A"; DEMERGER="DEMERGER"; BUYBACK="BUYBACK"; FUNDRAISE="FUNDRAISE"; QIP="QIP"; PROMOTER_BUY="PROMOTER_BUY"; PROMOTER_SELL="PROMOTER_SELL"; PLEDGE_CHANGE="PLEDGE_CHANGE"; CREDIT_RATING="CREDIT_RATING"; REGULATORY_APPROVAL="REGULATORY_APPROVAL"; REGULATORY_ACTION="REGULATORY_ACTION"; PLI_INCENTIVE="PLI_INCENTIVE"; GOVERNMENT_POLICY="GOVERNMENT_POLICY"; INDEX_INCLUSION="INDEX_INCLUSION"; INDEX_EXCLUSION="INDEX_EXCLUSION"; RESULT="RESULT"; GUIDANCE="GUIDANCE"; MANAGEMENT_CHANGE="MANAGEMENT_CHANGE"; CUSTOMER_WIN="CUSTOMER_WIN"; CUSTOMER_LOSS="CUSTOMER_LOSS"; LITIGATION="LITIGATION"; CORPORATE_ACTION="CORPORATE_ACTION"
class PolicyImplementationStage(StrEnum): ANNOUNCED="ANNOUNCED"; APPROVED="APPROVED"; BUDGET_ALLOCATION="BUDGET_ALLOCATION"; TENDER_ISSUED="TENDER_ISSUED"; ORDER_AWARDED="ORDER_AWARDED"; DISBURSEMENT="DISBURSEMENT"; PROJECT_EXECUTION="PROJECT_EXECUTION"
class PricedInState(StrEnum): UNKNOWN="UNKNOWN"; NOT_ASSESSED="NOT_ASSESSED"

@dataclass(frozen=True, slots=True)
class CatalystEvent:
    event_id: str
    event_type: CatalystType
    company_id: str | None
    sector: str | None
    event_date: datetime
    publication_date: datetime
    retrieved_at: datetime
    source_quality: NewsSourceQuality
    primary_source_confirmation: bool
    exchange_filing_match: bool
    expected_financial_impact: str
    expected_time_horizon: str | None
    already_priced_in: PricedInState
    confidence: float | None
    cluster_id: str | None
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class CatalystMateriality:
    event_id: str
    order_value: Decimal | None
    ttm_revenue: Decimal | None
    order_to_revenue: Decimal | None
    status: str
    warnings: tuple[str, ...] = ()

class CatalystService:
    def from_cluster(self, *, event_id: str, cluster: NewsEventCluster, event_type: CatalystType, company_id: str | None, sector: str | None, publication_date: datetime, retrieved_at: datetime, source_quality: NewsSourceQuality) -> CatalystEvent:
        return CatalystEvent(event_id, event_type, company_id, sector, cluster.original_event_at, publication_date, retrieved_at, source_quality, cluster.company_confirmed, bool(cluster.filing_ids), "UNCERTAIN", None, PricedInState.UNKNOWN, None, cluster.cluster_id, cluster.article_ids, cluster.warnings)
    def order_materiality(self, *, event_id: str, order_value: Decimal | None, ttm_revenue: Decimal | None) -> CatalystMateriality:
        if order_value is None or ttm_revenue is None or ttm_revenue <= 0:
            return CatalystMateriality(event_id, order_value, ttm_revenue, None, "UNAVAILABLE", ("ORDER_OR_REVENUE_UNAVAILABLE",))
        return CatalystMateriality(event_id, order_value, ttm_revenue, order_value / ttm_revenue, "OBSERVED")
    @staticmethod
    def policy_realized(stage: PolicyImplementationStage) -> bool:
        return stage is PolicyImplementationStage.PROJECT_EXECUTION
