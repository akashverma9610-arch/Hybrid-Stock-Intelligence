from datetime import UTC,datetime,timedelta
from decimal import Decimal
import pytest
from app.crisis.models import MarketExtremeLevel
from app.data_sources.models import DataFamily,SourceRecordProvenance
from app.primary_market.models import *
from app.primary_market.service import PrimaryMarketAggregationService,PrimaryMarketExtremesInputBuilder
from app.primary_market.store import SQLitePrimaryMarketStore,PostgreSQLPrimaryMarketStore
from app.storage.database import DatabaseBackend,DatabaseConnectionFactory,DatabaseSettings
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import CanonicalOHLCVBar,Exchange,InstrumentIdentity,InstrumentType,MarketDataProvenance,Timeframe,AdjustmentStatus
from app.domain.models import DataQuality
from app.primary_market.service import ListingOutcomeDerivationService
T=datetime(2026,8,23,tzinfo=UTC)
def issue(i="issue-1",*,ofs="20",fresh="80",listing=True):
 p=SourceRecordProvenance(i,"NSE",i,T,T,T,None,None,DataFamily.IPO_PRIMARY_MARKET,"v1","v1")
 return PrimaryMarketIssue(i,"Alpha Engineering",None,"ALPHA","NSE",PrimaryMarketIssueType.MAINBOARD_IPO,"EQUITY","Engineering",T-timedelta(days=10),T-timedelta(days=7),T-timedelta(days=5) if listing else None,Decimal("90"),Decimal("100"),Decimal("100"),10,Decimal("100"),Decimal(fresh),Decimal(ofs),Decimal("1000"),"INR","CRORE","NSE",T-timedelta(days=11),T-timedelta(days=11),p,("promoter A",),("https://nse.test/rhp",))
def sub(i="issue-1",semantic=SubscriptionSemantic.FINAL_SUBSCRIPTION,value="4"):
 p=SourceRecordProvenance("sub","NSE","sub",T,T,T,None,None,DataFamily.IPO_PRIMARY_MARKET,"v1","v1");return IssueSubscriptionSnapshot("sub-"+semantic.value,i,T-timedelta(days=7),SubscriptionCategory.RETAIL,Decimal("10"),Decimal("40"),Decimal(value),semantic,"NSE",T-timedelta(days=7),p)
def test_issue_subscription_pit_dedup_conflict_and_fresh_ofs_facts(tmp_path):
 s=SQLitePrimaryMarketStore(tmp_path/"pm.sqlite");a=issue();assert s.save_issue(a) and not s.save_issue(a) and a.fresh_issue_percentage==Decimal(".8") and a.ofs_percentage==Decimal(".2")
 with pytest.raises(ValueError):s.save_issue(issue("issue-1",fresh="70"))
 bid=sub(semantic=SubscriptionSemantic.BID_POSITION);final=sub();assert s.save_subscription(bid) and s.save_subscription(final)
 assert [x.semantic for x in s.subscriptions("issue-1",as_of=T-timedelta(days=8))]==[]
 assert s.subscriptions("issue-1",as_of=T)[0].semantic is SubscriptionSemantic.BID_POSITION
def test_aggregate_sector_coverage_and_existing_euphoria_input_only(tmp_path):
 s=SQLitePrimaryMarketStore(tmp_path/"pm.sqlite");s.save_issue(issue());s.save_issue(issue("issue-2",ofs="90",fresh="10",listing=False));s.save_subscription(sub());s.save_listing_outcome(ListingOutcome("issue-1",T-timedelta(days=5),Decimal("100"),Decimal("110"),Decimal("120"),Decimal("95"),Decimal("115"),Decimal(".15"),("bar-1",)))
 aggregates=PrimaryMarketAggregationService(s);a=aggregates.aggregate(end=T,days=30);assert a.issue_count==2 and a.total_fresh_issue==Decimal("90") and a.total_ofs==Decimal("110") and a.subscription_coverage==.5 and a.listing_coverage==.5
 observation=PrimaryMarketExtremesInputBuilder(aggregates).build(level=MarketExtremeLevel.MARKET,entity_id="NIFTY",as_of=T);assert observation.rolling_ipo_count==2 and observation.listing_premium==Decimal(".15") and observation.retail_subscription==Decimal("4")
def test_listing_cannot_exist_before_listing_and_post_listing_is_factual(tmp_path):
 s=SQLitePrimaryMarketStore(tmp_path/"pm.sqlite");a=issue(listing=False);s.save_issue(a);assert s.get_listing_outcome(a.issue_id,as_of=T) is None
 s.save_listing_outcome(ListingOutcome(a.issue_id,T,Decimal("100"),Decimal("105"),Decimal("120"),Decimal("95"),Decimal("110"),Decimal(".10"),("bar",)))
 assert s.get_listing_outcome(a.issue_id,as_of=T-timedelta(days=1)) is None and s.get_listing_outcome(a.issue_id,as_of=T).first_day_return==Decimal(".10")
def test_postgres_adapter_requires_explicit_backend():
 with pytest.raises(ValueError):PostgreSQLPrimaryMarketStore(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.SQLITE,"sqlite:///:memory:")))
def test_listing_and_post_listing_use_only_canonical_historical_bars_with_pit(tmp_path):
 s=SQLitePrimaryMarketStore(tmp_path/"pm.sqlite");i=issue();instrument=InstrumentIdentity("NSE:ALPHA",Exchange.NSE,"ALPHA",None,None,None,InstrumentType.NSE_EQUITY,"Alpha");i=__import__("dataclasses").replace(i,instrument_id=instrument.instrument_id,listing_date=T-timedelta(days=4));s.save_issue(i);bars=SQLiteHistoricalBarStore(tmp_path/"bars.sqlite")
 for n,close in enumerate(("110","120","130")):
  end=i.listing_date+timedelta(days=n+1);bars.upsert(CanonicalOHLCVBar(f"bar-{n}",instrument,Timeframe.DAILY,end-timedelta(days=1),end,Decimal("105"),Decimal("135"),Decimal("100"),Decimal(close),1,None,None,AdjustmentStatus.RAW,MarketDataProvenance("stored",None,end,end,end,"v1","test"),DataQuality.HIGH))
 service=ListingOutcomeDerivationService(bars,s);assert service.derive(i,as_of=i.listing_date) is None
 outcome=service.derive(i,as_of=T);assert outcome.first_day_return==Decimal(".1") and outcome.observed_at.tzinfo is not None
 assert service.post_listing_return(i,as_of=T,sessions=1)==Decimal(".2") and service.post_listing_return(i,as_of=i.listing_date+timedelta(days=1),sessions=5) is None
