from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from app.data_sources.models import SourceRecordProvenance

class PrimaryMarketIssueType(StrEnum): MAINBOARD_IPO="MAINBOARD_IPO"; SME_IPO="SME_IPO"; FPO="FPO"; OFS="OFS"; RIGHTS_ISSUE="RIGHTS_ISSUE"; OTHER="OTHER"
class SubscriptionCategory(StrEnum): RETAIL="RETAIL"; NII_HNI="NII_HNI"; QIB="QIB"; EMPLOYEE="EMPLOYEE"; SHAREHOLDER="SHAREHOLDER"; TOTAL="TOTAL"; OTHER="OTHER"
class SubscriptionSemantic(StrEnum): BID_POSITION="BID_POSITION"; CONFIRMED_BID="CONFIRMED_BID"; FINAL_SUBSCRIPTION="FINAL_SUBSCRIPTION"; UNKNOWN="UNKNOWN"
class PrimaryMarketIssueStatus(StrEnum): UPCOMING="UPCOMING"; OPEN="OPEN"; CLOSED="CLOSED"; LISTED="LISTED"; UNKNOWN="UNKNOWN"
@dataclass(frozen=True,slots=True)
class PrimaryMarketIssue:
 issue_id:str; issuer_name:str; instrument_id:str|None; future_symbol:str|None; exchange:str; issue_type:PrimaryMarketIssueType; security_type:str|None; sector:str|None; issue_open_date:datetime|None; issue_close_date:datetime|None; listing_date:datetime|None; price_band_low:Decimal|None; price_band_high:Decimal|None; issue_price:Decimal|None; lot_size:int|None; total_issue_size:Decimal|None; fresh_issue_amount:Decimal|None; ofs_amount:Decimal|None; shares_offered:Decimal|None; currency:str; size_unit:str; source:str; published_at:datetime; received_at:datetime; provenance:SourceRecordProvenance; selling_shareholder_references:tuple[str,...]=(); document_references:tuple[str,...]=(); normalization_version:str="primary-market-v1"; warnings:tuple[str,...]=()
 def __post_init__(self):
  if not self.issue_id or not self.issuer_name.strip() or self.published_at.tzinfo is None or self.received_at.tzinfo is None:raise ValueError("Primary-market issue identity/timestamps are required.")
  if self.received_at<self.published_at:raise ValueError("Primary-market receipt cannot precede publication.")
  if any(v is not None and v<0 for v in (self.total_issue_size,self.fresh_issue_amount,self.ofs_amount,self.shares_offered,self.issue_price,self.price_band_low,self.price_band_high)):raise ValueError("Primary-market amounts cannot be negative.")
 @property
 def fresh_issue_percentage(self):return self.fresh_issue_amount/self.total_issue_size if self.fresh_issue_amount is not None and self.total_issue_size not in {None,Decimal("0")} else None
 @property
 def ofs_percentage(self):return self.ofs_amount/self.total_issue_size if self.ofs_amount is not None and self.total_issue_size not in {None,Decimal("0")} else None
 def eligible_as_of(self,as_of):return self.published_at<=as_of and self.received_at<=as_of
@dataclass(frozen=True,slots=True)
class IssueSubscriptionSnapshot:
 snapshot_id:str; issue_id:str; observed_at:datetime; category:SubscriptionCategory; offered_quantity:Decimal|None; bid_quantity:Decimal|None; subscription_multiple:Decimal|None; semantic:SubscriptionSemantic; source:str; received_at:datetime; provenance:SourceRecordProvenance; warnings:tuple[str,...]=()
 def __post_init__(self):
  if not self.snapshot_id or self.observed_at.tzinfo is None or self.received_at.tzinfo is None:raise ValueError("Subscription identity/timestamps are required.")
  if self.received_at<self.observed_at:raise ValueError("Subscription receipt cannot precede observation.")
  if self.subscription_multiple is None and self.offered_quantity not in {None,Decimal("0")} and self.bid_quantity is not None:object.__setattr__(self,"subscription_multiple",self.bid_quantity/self.offered_quantity)
 def eligible_as_of(self,as_of):return self.observed_at<=as_of and self.received_at<=as_of
@dataclass(frozen=True,slots=True)
class ListingOutcome:
 issue_id:str; observed_at:datetime; issue_price:Decimal|None; listing_open:Decimal|None; listing_high:Decimal|None; listing_low:Decimal|None; listing_close:Decimal|None; first_day_return:Decimal|None; provenance_ids:tuple[str,...]; warnings:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class PrimaryMarketAggregate:
 aggregate_id:str; start:datetime; end:datetime; data_as_of:datetime; issue_count:int; total_issue_size:Decimal; total_fresh_issue:Decimal; total_ofs:Decimal; mainboard_count:int; sme_count:int; median_subscription:Decimal|None; median_listing_premium:Decimal|None; positive_listing_ratio:Decimal|None; sector_counts:tuple[tuple[str,int],...]; subscription_coverage:float; listing_coverage:float; warnings:tuple[str,...]; provenance_ids:tuple[str,...]
