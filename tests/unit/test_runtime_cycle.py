from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect
import pytest
from app.domain.models import DataQuality
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.market_data.aggregation import MarketUniverse
from app.market_data.models import CanonicalQuote, Exchange, FreshnessAssessment, FreshnessState, InstrumentIdentity, InstrumentType, MarketDataProvenance, MarketSessionState
from app.market_data.store import InMemoryMarketDataStore
from app.runtime.cycle import RuntimeCycleCoordinator, RuntimeCycleStatus, RuntimeMode, RuntimeStage
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
T=datetime(2026,8,24,10,tzinfo=UTC)
def q(identifier,price="101",previous="100",fresh=True):
 i=InstrumentIdentity(identifier,Exchange.NSE,identifier,None,None,None,InstrumentType.NSE_EQUITY,identifier)
 p=MarketDataProvenance("FIXTURE",None,T,T,T,"v1")
 return CanonicalQuote(f"q-{identifier}",i,Decimal(price),Decimal(previous),None,None,None,100,None,None,None,None,None,None,None,p,FreshnessAssessment(FreshnessState.FRESH if fresh else FreshnessState.STALE,T,T,timedelta(),timedelta(minutes=1),MarketSessionState.OPEN),DataQuality.HIGH)
def universe(): return MarketUniverse("BROAD_5","v1",tuple(UniverseMembership(f"m-{x}",x,"BROAD_5",T-timedelta(days=1),None,T-timedelta(days=1),"fixture","fixture",InstrumentLifecycle.ACTIVE) for x in "ABCDE"))
def coordinator(tmp_path,*,quotes=True):
 store=InMemoryMarketDataStore()
 if quotes:
  for item in (q("A"),q("B","99"),q("C","100"),q("D",fresh=False)):store.save_quote(item)
 return RuntimeCycleCoordinator(store,universe(),SQLiteCoreApiSnapshotRepository(tmp_path/"snapshots.sqlite"),clock=lambda:T)
def test_cycle_modes_stages_quality_partial_publication_and_idempotency(tmp_path):
 c=coordinator(tmp_path); first=c.run_cycle(mode=RuntimeMode.STORED_DATA,cycle_id="cycle-a"); second=c.run_cycle(mode=RuntimeMode.MOCK,cycle_id="cycle-a")
 assert first.overall_status is RuntimeCycleStatus.PARTIAL and first.data_confidence.quote_coverage==.8 and first.snapshots_written==("runtime:cycle-a",)
 assert second.snapshots_written==("runtime:cycle-a",) and {x.stage for x in first.stage_results}==set(RuntimeStage)
 assert all(x.status is RuntimeCycleStatus.SKIPPED for x in first.stage_results if x.stage in {RuntimeStage.REGIME,RuntimeStage.EXTREMES,RuntimeStage.SECTOR,RuntimeStage.STOCK})
 payload=c.snapshots.get_snapshot("runtime:cycle-a").payload
 assert payload["cycle_id"]=="cycle-a" and payload["overall_status"]=="PARTIAL" and payload["warnings"]==first.warnings
def test_dry_run_no_universe_and_empty_data_are_safe(tmp_path):
 c=coordinator(tmp_path); dry=c.run_cycle(publish=False); assert dry.snapshots_written==() and dry.stage_results[-1].status is RuntimeCycleStatus.SKIPPED
 empty=RuntimeCycleCoordinator(InMemoryMarketDataStore(),MarketUniverse("EMPTY","v1",()),SQLiteCoreApiSnapshotRepository(tmp_path/"empty.sqlite"),clock=lambda:T)
 with pytest.raises(ValueError,match="explicit non-empty"):empty.run_cycle()
 failed=coordinator(tmp_path,quotes=False).run_cycle(cycle_id="empty-data"); assert failed.overall_status is RuntimeCycleStatus.PARTIAL
def test_runtime_has_no_network_trading_governance_or_phase9b_side_effects():
 import app.runtime.cycle as cycle
 source=inspect.getsource(cycle).lower();assert not any(x in source for x in ("kotak","websocket","requests.","place_order","holdings","demat","activate","promotion","self_improvement"))
