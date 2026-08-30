from datetime import UTC,datetime
from app.data_sources.models import DataFamily
from app.data_sources.service import DataSourceCompositionService,SourceCompositionSettings
from app.runtime.cycle import RuntimeCycleCoordinator,RuntimeStage
from app.market_data.store import InMemoryMarketDataStore
from app.market_data.aggregation import MarketUniverse
from app.historical.models import UniverseMembership,InstrumentLifecycle
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.crisis.models import IPOIntensityObservation,MarketExtremeLevel
def test_primary_market_store_readiness_is_not_live_provider_ready():
 settings=SourceCompositionSettings.from_environment({"PRIMARY_MARKET_DATA_AVAILABLE":"true"});report=DataSourceCompositionService.from_settings(settings).readiness();items=report.for_family(DataFamily.IPO_PRIMARY_MARKET)
 assert items[0].provider=="local_store" and items[0].status.value=="READY" and "NO_LIVE_IPO_PROVIDER" in "|".join(items[0].warnings)
 assert items[1].provider=="unconfigured" and items[1].status.value=="MISSING_CONFIGURATION"
def test_runtime_passes_stored_primary_market_fact_to_existing_extremes_input_boundary(tmp_path):
 t=datetime(2026,8,23,tzinfo=UTC);seen=[]
 class Builder:
  def build(self,**kwargs):return IPOIntensityObservation("ipo",MarketExtremeLevel.MARKET,kwargs["entity_id"],t,t,1,None,None,None,None,None,None,None,None,None,1.0,("issue",))
 universe=MarketUniverse("NIFTY","v1",(UniverseMembership("m","NSE:ALPHA","NIFTY",t,None,t,"NSE","fixture",InstrumentLifecycle.ACTIVE),))
 result=RuntimeCycleCoordinator(InMemoryMarketDataStore(),universe,SQLiteCoreApiSnapshotRepository(tmp_path/"snap.sqlite"),primary_market_extremes_builder=Builder(),market_extremes_input_consumer=seen.append,clock=lambda:t).run_cycle(publish=False)
 assert seen[0].observation_id=="ipo" and next(x for x in result.stage_results if x.stage is RuntimeStage.EXTREMES).status.value=="SUCCESS"
