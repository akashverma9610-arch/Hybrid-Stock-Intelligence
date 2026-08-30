from datetime import UTC,datetime,timedelta
from decimal import Decimal
import pytest
from app.market_data.global_datafeeds import GlobalDatafeedsHistoricalProvider
from app.market_data.models import *
T=datetime(2026,9,4,10,tzinfo=UTC)
def instrument():return InstrumentIdentity("NSE:RELIANCE",Exchange.NSE,"RELIANCE","RELIANCE",None,None,InstrumentType.NSE_EQUITY,"Reliance",provider_mappings=(ProviderInstrumentMapping("global_datafeeds","RELIANCE",provider_exchange_segment="NSE"),))
def test_documented_request_mapping_decimal_timezone_and_adjustment():
 seen=[];p=GlobalDatafeedsHistoricalProvider("secret",transport=lambda q:seen.append(q) or {"Result":[{"LastTradeTime":int(T.timestamp()),"Open":"100.01","High":"102","Low":"99","Close":"101.99","TradedQty":10}]},clock=lambda:T)
 r=HistoricalBarsRequest(instrument(),Timeframe.FIVE_MINUTES,T-timedelta(minutes=5),T,AdjustmentStatus.RAW);bars=p.get_historical_bars(r)
 assert seen[0]["periodicity"]=="MINUTE" and seen[0]["period"]=="5" and seen[0]["AdjustSplits"]=="false" and seen[0]["accessKey"]=="secret" and bars[0].close==Decimal("101.99") and bars[0].end_time.tzinfo is not None and bars[0].adjustment_status is AdjustmentStatus.RAW
@pytest.mark.parametrize("timeframe,periodicity,period",[(Timeframe.ONE_MINUTE,"MINUTE",1),(Timeframe.FIFTEEN_MINUTES,"MINUTE",15),(Timeframe.THIRTY_MINUTES,"MINUTE",30),(Timeframe.SIXTY_MINUTES,"HOUR",1),(Timeframe.DAILY,"DAY",1),(Timeframe.WEEKLY,"WEEK",1)])
def test_timeframes(timeframe,periodicity,period):
 p=GlobalDatafeedsHistoricalProvider("key");q=p.request_parameters(HistoricalBarsRequest(instrument(),timeframe,T,T));assert (q["periodicity"],q["period"])==(periodicity,str(period))
def test_missing_mapping_secret_and_malformed_payload_fail_closed():
 p=GlobalDatafeedsHistoricalProvider(None); 
 with pytest.raises(MarketDataError):p.request_parameters(HistoricalBarsRequest(instrument(),Timeframe.DAILY,T,T))
 bad=GlobalDatafeedsHistoricalProvider("key",transport=lambda q:{"Result":[{}]})
 with pytest.raises(MarketDataError):bad.get_historical_bars(HistoricalBarsRequest(instrument(),Timeframe.DAILY,T,T))
def test_ingestion_store_and_provider_isolation(tmp_path):
 from app.market_data.historical import HistoricalIngestionService,SQLiteHistoricalBarStore
 p=GlobalDatafeedsHistoricalProvider("key",transport=lambda q:{"Result":[{"LastTradeTime":int(T.timestamp()),"Open":"1.0001","High":"2","Low":"1","Close":"1.5","TradedQty":10}]},clock=lambda:T)
 r=HistoricalBarsRequest(instrument(),Timeframe.DAILY,T-timedelta(days=1),T,provider_preference="global_datafeeds");store=SQLiteHistoricalBarStore(tmp_path/"bars.sqlite");report=HistoricalIngestionService(p,store,clock=lambda:T+timedelta(days=1)).ingest(r)
 assert report.accepted_count==1 and report.coverage.value in {"COMPLETE","PARTIAL"} and store.latest("NSE:RELIANCE",Timeframe.DAILY,1)[0].provenance.provider=="global_datafeeds"
 import inspect,app.analysis.series as technical,app.analysis.relative_strength as rs,app.crisis as crisis
 assert "global_datafeeds" not in (inspect.getsource(technical)+inspect.getsource(rs)+inspect.getsource(crisis)).lower()
def test_kotak_quotes_and_gdfl_historical_selection_coexist():
 from app.data_sources.service import SourceCompositionSettings,DataSourceCompositionService
 s=SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER":"kotak_neo","HISTORICAL_DATA_PROVIDER":"global_datafeeds"});r=DataSourceCompositionService.from_settings(s).readiness()
 assert r.primary(__import__("app.data_sources.models",fromlist=["DataFamily"]).DataFamily.CURRENT_QUOTES).source_id=="kotak_neo" and r.primary(__import__("app.data_sources.models",fromlist=["DataFamily"]).DataFamily.HISTORICAL_OHLCV).source_id=="global_datafeeds"
def test_gdfl_readiness_transition_is_explicit_and_never_false_ready():
 from app.data_sources.models import DataFamily,SourceValidationState,SourceReadinessStatus
 from app.data_sources.service import SourceCompositionSettings,DataSourceCompositionService
 settings=SourceCompositionSettings.from_environment({"HISTORICAL_DATA_PROVIDER":"global_datafeeds"})
 assert DataSourceCompositionService.from_settings(settings,states={"global_datafeeds":SourceValidationState(False)}).readiness().primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.MISSING_CONFIGURATION
 assert DataSourceCompositionService.from_settings(settings,states={"global_datafeeds":SourceValidationState(True,False)}).readiness().primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.CONFIGURED_NOT_VALIDATED
 assert DataSourceCompositionService.from_settings(settings,states={"global_datafeeds":SourceValidationState(True,True)}).readiness().primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.READY
 assert DataSourceCompositionService.from_settings(settings,states={"global_datafeeds":SourceValidationState(True,False,unavailable=True)}).readiness().primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.UNAVAILABLE
