from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.fundamentals import FundamentalRules, earnings_acceleration, latest_quarter
from app.data_sources.models import FundamentalFactKind
from app.domain.models import DataQuality
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance

T=datetime(2026,9,1,tzinfo=UTC); RULES=FundamentalRules(.1,-.1,.12,1.5,2,.02)
def instrument():return InstrumentIdentity("NSE:ALPHA",Exchange.NSE,"ALPHA","ALPHA",None,None,InstrumentType.NSE_EQUITY,"Alpha")
def filing(identifier,published,revision=None,kind=FilingType.FINANCIAL_RESULTS):
 return CorporateFiling(identifier,instrument(),Exchange.NSE,"fixture",PrimarySourceQuality.PRIMARY_EXCHANGE,kind,None,identifier,published,published,identifier,None,MarketDataProvenance("fixture",identifier,None,None,published,"v1","r",identifier),revision_of_filing_id=revision)
def fact(identifier,metric,value,end,published,*,scope=StatementScope.CONSOLIDATED,filing_id=None,revision=None):
 return FinancialFact(identifier,instrument(),metric,Decimal(str(value)),"INR","INR",NumericScale.CRORES,FinancialPeriodType.QUARTERLY,FinancialValueBasis.QUARTER_ONLY,None,end,end.year,((end.month-1)//3)+1,scope,FundamentalFactKind.REPORTED,"fixture",filing_id or identifier,identifier,published,published,"v1",(),(),revision,(FinancialQualityFlag.COMPLETE,))
def seed(tmp_path):
 facts=SQLiteFinancialFactStore(tmp_path/"facts.sqlite"); filings=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
 for quarter in range(5):
  end=datetime(2025+(quarter//4),((quarter%4)+1)*3,28,tzinfo=UTC);published=T-timedelta(days=30-quarter)
  f=filing(f"f{quarter}",published);filings.save(f)
  for metric,value in ((FinancialMetric.REVENUE,100+quarter*20),(FinancialMetric.EBITDA,20+quarter*4),(FinancialMetric.PAT,12+quarter*2),(FinancialMetric.EPS_BASIC,6+quarter)):
   facts.save(fact(f"{metric.value}-{quarter}",metric,value,end,published,filing_id=f.filing_id))
 return facts,filings

def test_adapter_reuses_existing_observation_contract_and_earnings_acceleration(tmp_path):
 facts,filings=seed(tmp_path); value=FundamentalsEngineAdapter(facts,filings).build("NSE:ALPHA",as_of=T)
 assert value.statement_scope is StatementScope.CONSOLIDATED and value.completeness=="COMPLETE" and value.filing_context.latest_financial_result_filing_id
 assert len(value.snapshot.observations)==5 and all(x.payload["statement_scope"]=="CONSOLIDATED" for x in value.snapshot.observations)
 assert earnings_acceleration(value.snapshot,"NSE:ALPHA",RULES).state=="ACCELERATING" and latest_quarter(value.snapshot,"NSE:ALPHA",RULES).state=="REPORTED"
 assert all(item.filing_id for item in (facts.get(x) for x in value.fact_ids))

def test_adapter_pit_revision_scope_and_conflict_fail_closed(tmp_path):
 facts,filings=seed(tmp_path); adapter=FundamentalsEngineAdapter(facts,filings); end=datetime(2026,6,28,tzinfo=UTC)
 original=fact("original",FinancialMetric.REVENUE,200,end,T-timedelta(days=2),filing_id="original"); revision=fact("revision",FinancialMetric.REVENUE,250,end,T+timedelta(days=2),filing_id="revision",revision="original")
 filings.save(filing("original",original.published_at));filings.save(filing("revision",revision.published_at,"original"));facts.save(original);facts.save(revision)
 before=adapter.build("NSE:ALPHA",as_of=T);after=adapter.build("NSE:ALPHA",as_of=T+timedelta(days=2))
 assert "original" in before.fact_ids and "revision" not in before.fact_ids and "revision" in after.fact_ids
 standalone=fact("standalone",FinancialMetric.REVENUE,999,datetime(2026,9,28,tzinfo=UTC),T-timedelta(days=1),scope=StatementScope.STANDALONE,filing_id="standalone");filings.save(filing("standalone",standalone.published_at));facts.save(standalone)
 assert adapter.build("NSE:ALPHA",as_of=T).statement_scope is StatementScope.CONSOLIDATED
 conflict=fact("conflict",FinancialMetric.PAT,999,datetime(2026,3,28,tzinfo=UTC),T-timedelta(days=1),filing_id="conflict");filings.save(filing("conflict",conflict.published_at));facts.save(conflict)
 conflicted=adapter.build("NSE:ALPHA",as_of=T);assert any(x.startswith("UNRESOLVED_FINANCIAL_FACT_CONFLICT:PAT") for x in conflicted.warnings)

def test_adapter_missing_data_never_fabricates_values_or_uses_future_filing(tmp_path):
 facts,filings=seed(tmp_path); future=fact("future",FinancialMetric.REVENUE,999,datetime(2027,3,28,tzinfo=UTC),T+timedelta(days=1),filing_id="future");filings.save(filing("future",future.published_at));facts.save(future)
 value=FundamentalsEngineAdapter(facts,filings).build("NSE:ALPHA",as_of=T)
 assert "future" not in value.fact_ids and all(x.payload.get("revenue")!=999 for x in value.snapshot.observations)
 empty=FundamentalsEngineAdapter(SQLiteFinancialFactStore(),SQLiteCorporateFilingsStore()).build("NSE:MISSING",as_of=T)
 assert empty.completeness=="INSUFFICIENT" and empty.snapshot.observations==() and "FUNDAMENTALS_UNAVAILABLE" in empty.warnings
