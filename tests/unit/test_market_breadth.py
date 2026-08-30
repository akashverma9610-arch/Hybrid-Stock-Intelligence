from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import DataQuality
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.market_data.aggregation import BreadthAggregator, BreadthCoverageStatus, IndexObservationService, MarketUniverse
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import (CanonicalQuote, Exchange, FreshnessAssessment, FreshnessState, IndexMarketObservation, InstrumentIdentity, InstrumentType, MarketDataProvenance, MarketSessionState, Timeframe)
from app.market_data.store import InMemoryMarketDataStore

T=datetime(2026,8,23,10,tzinfo=UTC)
def inst(name,kind=InstrumentType.NSE_EQUITY): return InstrumentIdentity(name,Exchange.INDEX if kind is not InstrumentType.NSE_EQUITY else Exchange.NSE,name,None,None,None,kind,name)
def prov(): return MarketDataProvenance("FIXTURE",None,T,T,T,"v1","aggregate","fixture")
def quote(name,price,previous,*,volume=100,fresh=True): return CanonicalQuote(f"q-{name}",inst(name),Decimal(price),Decimal(previous),None,None,None,volume,None,None,None,None,None,None,None,prov(),FreshnessAssessment(FreshnessState.FRESH if fresh else FreshnessState.STALE,T,T,timedelta(),timedelta(minutes=1),MarketSessionState.OPEN),DataQuality.HIGH)
def universe(*names,pit=True): return MarketUniverse("BROAD_5","v1",tuple(UniverseMembership(f"m-{name}",name,"BROAD_5",T-timedelta(days=1),None,T-timedelta(days=1),"fixture","fixture",InstrumentLifecycle.ACTIVE) for name in names),pit)

def test_breadth_uses_explicit_pit_universe_and_preserves_mixed_advance_decline_volume():
    value, summary=BreadthAggregator().aggregate(universe("A","B","C"),{"A":quote("A","101","100",volume=10),"B":quote("B","99","100",volume=20),"C":quote("C","100","100",volume=30)},data_as_of=T,provenance=prov())
    assert (value.advances,value.declines,value.unchanged,value.up_volume,value.down_volume)==(1,1,1,10,20)
    assert summary.coverage is BreadthCoverageStatus.COMPLETE and summary.coverage_percent==Decimal("1")

def test_missing_stale_and_missing_previous_close_reduce_coverage_without_guessing():
    unavailable=quote("C","101","100",fresh=False)
    value,summary=BreadthAggregator().aggregate(universe("A","B","C"),{"A":quote("A","101","100"),"C":unavailable},data_as_of=T,provenance=prov())
    assert value.coverage_count==1 and summary.missing_constituents==1 and summary.stale_constituents==1
    assert summary.coverage is BreadthCoverageStatus.INSUFFICIENT and "STALE_CONSTITUENTS_EXCLUDED" in summary.warnings

def test_index_vix_and_historical_index_access_are_provider_neutral(tmp_path):
    store=InMemoryMarketDataStore(); index=inst("NIFTY50",InstrumentType.BROAD_INDEX); vix=inst("INDIA_VIX",InstrumentType.VOLATILITY_INDEX)
    observation=IndexMarketObservation("nifty",index,Decimal("25000"),Decimal("24900"),None,None,None,Decimal("100"),Decimal("0.4"),T,prov(),FreshnessAssessment(FreshnessState.FRESH,T,T,timedelta(),timedelta(minutes=1),MarketSessionState.OPEN),DataQuality.HIGH)
    vix_observation=IndexMarketObservation("vix",vix,Decimal("14"),Decimal("13"),None,None,None,Decimal("1"),Decimal("7"),T,prov(),FreshnessAssessment(FreshnessState.FRESH,T,T,timedelta(),timedelta(minutes=1),MarketSessionState.OPEN),DataQuality.HIGH)
    store.save_index(observation);store.save_index(vix_observation)
    service=IndexObservationService(store,SQLiteHistoricalBarStore(tmp_path/"bars.sqlite"))
    assert service.latest("NIFTY50")==observation and service.vix(vix)==vix_observation and service.history("NIFTY50",Timeframe.DAILY,T-timedelta(days=1),T)==()

def test_breadth_output_is_deterministic_and_has_no_provider_or_trading_dependency():
    import inspect,app.market_data.aggregation as aggregation
    args=(universe("A","B"),{"A":quote("A","101","100"),"B":quote("B","99","100")})
    assert BreadthAggregator().aggregate(*args,data_as_of=T,provenance=prov())==BreadthAggregator().aggregate(*args,data_as_of=T,provenance=prov())
    source=inspect.getsource(aggregation).lower();assert not any(token in source for token in ("kotak","requests.","place_order","holdings","demat","scheduler"))
