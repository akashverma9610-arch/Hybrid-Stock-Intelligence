from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.stock_query import DiagnosticCoverageQueryRecord, StockAnalysisQueryResult
from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.market_data.aggregation import MarketUniverse
from app.market_data.models import CanonicalQuote, Exchange, FreshnessAssessment, FreshnessState, InstrumentIdentity, InstrumentType, MarketDataProvenance, MarketSessionState
from app.market_data.store import InMemoryMarketDataStore
from app.runtime.cycle import RuntimeCycleCoordinator, RuntimeCycleStatus, RuntimeMode, RuntimeStage
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
T=datetime(2026,9,2,10,tzinfo=UTC)
def instrument():return InstrumentIdentity("NSE:ALPHA",Exchange.NSE,"ALPHA","ALPHA",None,None,InstrumentType.NSE_EQUITY,"Alpha")
def add(facts,filings,identifier,metric,value,end):
 filing=CorporateFiling(identifier,instrument(),Exchange.NSE,"fixture",PrimarySourceQuality.PRIMARY_EXCHANGE,FilingType.FINANCIAL_RESULTS,None,identifier,T-timedelta(days=1),T-timedelta(days=1),identifier,None,MarketDataProvenance("fixture",identifier,None,None,T-timedelta(days=1),"v1","r",identifier));filings.save(filing)
 facts.save(FinancialFact(identifier,instrument(),metric,Decimal(str(value)),"INR","INR",NumericScale.CRORES,FinancialPeriodType.QUARTERLY,FinancialValueBasis.QUARTER_ONLY,None,end,end.year,((end.month-1)//3)+1,StatementScope.CONSOLIDATED,FundamentalFactKind.REPORTED,"fixture",identifier,identifier,T-timedelta(days=1),T-timedelta(days=1),"v1",(),(),None,(FinancialQualityFlag.COMPLETE,)))
def test_stored_data_facts_flow_through_adapter_existing_builder_runtime_snapshot_and_api(tmp_path):
 facts=SQLiteFinancialFactStore(tmp_path/"facts.sqlite");filings=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
 for q in range(5):
  end=datetime(2025+(q//4),((q%4)+1)*3,28,tzinfo=UTC)
  for metric,value in ((FinancialMetric.REVENUE,100+q*20),(FinancialMetric.EBITDA,20+q*4),(FinancialMetric.PAT,10+q),(FinancialMetric.EPS_BASIC,5+q)):add(facts,filings,f"{metric.value}-{q}",metric,value,end)
 store=InMemoryMarketDataStore();p=MarketDataProvenance("fixture",None,T,T,T,"v1");store.save_quote(CanonicalQuote("quote",instrument(),Decimal("100"),Decimal("99"),None,None,None,1,None,None,None,None,None,None,None,p,FreshnessAssessment(FreshnessState.FRESH,T,T,timedelta(),timedelta(minutes=1),MarketSessionState.OPEN)))
 universe=MarketUniverse("U","v1",(UniverseMembership("u","NSE:ALPHA","U",T-timedelta(days=1),None,T-timedelta(days=1),"fixture","fixture",InstrumentLifecycle.ACTIVE),));snapshots=SQLiteCoreApiSnapshotRepository(tmp_path/"snapshots.sqlite")
 captured=[]
 def builder(value):
  captured.append(value);return StockAnalysisQueryResult("ALPHA","NSE","Alpha",None,None,T,T,"PARTIAL",None,None,None,DiagnosticCoverageQueryRecord(0,0,0,0,0,()),None,None,warnings=value.warnings,provenance_ids=value.fact_ids)
 cycle=RuntimeCycleCoordinator(store,universe,snapshots,fundamentals_adapter=FundamentalsEngineAdapter(facts,filings),stock_analysis_builder=builder,clock=lambda:T).run_cycle(mode=RuntimeMode.STORED_DATA,cycle_id="facts")
 assert captured and captured[0].completeness=="COMPLETE" and next(x for x in cycle.stage_results if x.stage is RuntimeStage.STOCK).status is RuntimeCycleStatus.SUCCESS
 assert "runtime:facts:stock:ALPHA" in cycle.snapshots_written
 with TestClient(create_app(core_api_snapshot_repository=snapshots)) as client: response=client.get("/api/v1/stocks/ALPHA/analysis")
 assert response.status_code==200 and response.json()["data"]["status"]=="PARTIAL"
