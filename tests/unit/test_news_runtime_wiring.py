from datetime import UTC,datetime
from app.runtime.cycle import RuntimeCycleCoordinator
from app.market_data.aggregation import MarketUniverse
from app.market_data.store import InMemoryMarketDataStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository

T=datetime(2026,8,23,tzinfo=UTC)
class Fundamentals:
 def build(self,instrument_id,*,as_of): return (instrument_id,as_of)
class News:
 def __init__(self):self.calls=[]
 def build(self,instrument_id,*,as_of):self.calls.append((instrument_id,as_of));return ("research",instrument_id,as_of)
def test_runtime_news_wiring_is_opt_in_stored_input_only_and_never_network(tmp_path):
 # The empty explicit universe fails before any provider, broker, or news call.
 news=News();coordinator=RuntimeCycleCoordinator(InMemoryMarketDataStore(),MarketUniverse("empty","v1",()),SQLiteCoreApiSnapshotRepository(tmp_path/"snapshots.sqlite"),fundamentals_adapter=Fundamentals(),stock_analysis_builder=lambda value:value,news_research_builder=news,stock_input_enricher=lambda fundamentals,research:(fundamentals,research),clock=lambda:T)
 try: coordinator.run_cycle()
 except ValueError as error: assert "explicit non-empty universe" in str(error)
 assert news.calls == []
