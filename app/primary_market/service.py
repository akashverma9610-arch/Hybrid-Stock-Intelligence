from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from statistics import median
from app.crisis.models import IPOIntensityObservation,MarketExtremeLevel
from app.primary_market.models import *
from app.market_data.models import Timeframe
class ListingOutcomeDerivationService:
 """Uses only canonical stored OHLCV facts; it never fetches a separate listing feed."""
 def __init__(self,bars,store):self.bars,self.store=bars,store
 def derive(self,issue,*,as_of):
  if not issue.instrument_id or not issue.listing_date or issue.listing_date>as_of:return None
  values=self.bars.range(issue.instrument_id,Timeframe.DAILY,issue.listing_date,as_of,as_of=as_of)
  if not values:return None
  first=values[0];price=issue.issue_price;premium=(first.close-price)/price if price not in {None,Decimal("0")} else None
  value=ListingOutcome(issue.issue_id,first.end_time,price,first.open,first.high,first.low,first.close,premium,(first.bar_id,),())
  self.store.save_listing_outcome(value);return value
 def post_listing_return(self,issue,*,as_of,sessions=1,relative_to="issue_price"):
  outcome=self.derive(issue,as_of=as_of)
  if outcome is None or not issue.instrument_id:return None
  bars=self.bars.range(issue.instrument_id,Timeframe.DAILY,issue.listing_date,as_of,as_of=as_of)
  if len(bars)<=sessions:return None
  base=issue.issue_price if relative_to=="issue_price" else outcome.listing_open
  return (bars[sessions].close-base)/base if base not in {None,Decimal("0")} else None
class PrimaryMarketAggregationService:
 def __init__(self,store):self.store=store
 def aggregate(self,*,end,days=30,sector=None):
  start=end-timedelta(days=days);issues=self.store.list_issues(start=start,end=end,sector=sector,as_of=end,limit=200);subs=[];premiums=[];provenance=[];sector_counts={}
  for issue in issues:
   provenance.append(issue.issue_id);sector_counts[issue.sector or "UNKNOWN"]=sector_counts.get(issue.sector or "UNKNOWN",0)+1
   values=[v.subscription_multiple for v in self.store.subscriptions(issue.issue_id,as_of=end) if v.semantic is SubscriptionSemantic.FINAL_SUBSCRIPTION and v.subscription_multiple is not None]
   if values:subs.append(values[-1])
   outcome=self.store.get_listing_outcome(issue.issue_id,as_of=end)
   if outcome and outcome.first_day_return is not None:premiums.append(outcome.first_day_return)
  count=len(issues);warn=[]
  if not count:warn.append("NO_PRIMARY_MARKET_ISSUES")
  if count and len(subs)/count<.5:warn.append("LOW_SUBSCRIPTION_COVERAGE")
  if count and len(premiums)/count<.5:warn.append("LOW_LISTING_OUTCOME_COVERAGE")
  return PrimaryMarketAggregate("ipo:"+sha256(f"{start}:{end}:{sector}".encode()).hexdigest()[:20],start,end,end,count,sum((x.total_issue_size or Decimal("0") for x in issues),Decimal("0")),sum((x.fresh_issue_amount or Decimal("0") for x in issues),Decimal("0")),sum((x.ofs_amount or Decimal("0") for x in issues),Decimal("0")),sum(x.issue_type is PrimaryMarketIssueType.MAINBOARD_IPO for x in issues),sum(x.issue_type is PrimaryMarketIssueType.SME_IPO for x in issues),Decimal(str(median(subs))) if subs else None,Decimal(str(median(premiums))) if premiums else None,Decimal(sum(x>0 for x in premiums))/Decimal(len(premiums)) if premiums else None,tuple(sorted(sector_counts.items())),len(subs)/count if count else 0.0,len(premiums)/count if count else 0.0,tuple(warn),tuple(provenance))
class PrimaryMarketExtremesInputBuilder:
 """Maps immutable factual coverage to the existing IPOIntensityObservation only."""
 def __init__(self,aggregates):self.aggregates=aggregates
 def build(self,*,level:MarketExtremeLevel,entity_id:str,as_of,days=30):
  value=self.aggregates.aggregate(end=as_of,days=days,sector=None);eligible=[x for x in self.aggregates.store.list_issues(start=value.start,end=value.end,as_of=as_of,limit=200)]
  final={}
  for issue in eligible:
   for item in self.aggregates.store.subscriptions(issue.issue_id,as_of=as_of):
    if item.semantic is SubscriptionSemantic.FINAL_SUBSCRIPTION and item.subscription_multiple is not None:final[item.category]=item.subscription_multiple
  coverage=(value.subscription_coverage+value.listing_coverage)/2
  return IPOIntensityObservation(value.aggregate_id,level,entity_id,as_of,as_of,value.issue_count,None,value.total_issue_size,value.total_fresh_issue/value.total_issue_size if value.total_issue_size else None,value.total_ofs/value.total_issue_size if value.total_issue_size else None,final.get(SubscriptionCategory.RETAIL),final.get(SubscriptionCategory.NII_HNI),final.get(SubscriptionCategory.QIB),value.median_listing_premium,None,coverage,value.provenance_ids)
