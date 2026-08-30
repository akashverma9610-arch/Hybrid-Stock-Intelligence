from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api.fundamentals_query import RepositoryFundamentalsQueryService
from app.api.main import create_app
from app.data_sources.models import DataFamily, FundamentalFactKind, SourceReadinessStatus
from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
from app.filings.models import CorporateFiling, FilingTextAvailability, FilingType, FinancialResultMetadata, PrimarySourceQuality
from app.fundamentals.models import (FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope, StructuredFinancialRecord)
from app.fundamentals.service import FinancialDerivationService, FinancialFactNormalizationService
from app.fundamentals.store import FinancialFactWriteOutcome, PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings

T=datetime(2026,8,27,10,tzinfo=UTC)
def inst(symbol="ALPHA"): return InstrumentIdentity("NSE:"+symbol,Exchange.NSE,symbol,symbol,None,None,InstrumentType.NSE_EQUITY,symbol)
def filing(identifier="f",published=T,received=T,revision=None):
    p=MarketDataProvenance("fixture",identifier,None,None,received,"fixture-v1","req",identifier)
    return CorporateFiling(identifier,inst(),Exchange.NSE,"fixture",PrimarySourceQuality.PRIMARY_EXCHANGE,FilingType.FINANCIAL_RESULTS,None,"results",published,received,identifier,None,p,period_end=published-timedelta(days=30),text_availability=FilingTextAvailability.DOCUMENT_ONLY,revision_of_filing_id=revision,financial_result=FinancialResultMetadata(published-timedelta(days=30),"CONSOLIDATED","QUARTERLY",revision is not None))
def structured(metric=FinancialMetric.REVENUE,value=Decimal("100"),quarter=1,year=2026,published=T,received=T,scope=StatementScope.CONSOLIDATED,basis=FinancialValueBasis.QUARTER_ONLY,ptype=FinancialPeriodType.QUARTERLY,filing_id="f",source_ref="r"):
    end=datetime(year,quarter*3 if quarter else 12,28,tzinfo=UTC)
    return StructuredFinancialRecord(inst(),metric,value,"INR","INR",NumericScale.CRORES,ptype,basis,None,end,year,quarter,scope,"fixture",filing_id,published,received,source_ref,"attachment")
def fact(**kwargs):
    raw=structured(**kwargs); return FinancialFactNormalizationService().normalize(raw,filing(raw.filing_id,raw.published_at,raw.received_at))

def test_fact_model_precision_identity_metadata_and_filing_lineage():
    value=fact(value=Decimal("100.123456789")); assert value.value==Decimal("100.123456789") and value.filing_id=="f" and value.scale is NumericScale.CRORES
    with pytest.raises(ValueError): FinancialFactNormalizationService().normalize(structured(filing_id="wrong"),filing())
    assert value.fact_kind is FundamentalFactKind.REPORTED and value.available_at==T

def test_sqlite_dedup_conflict_revision_queries_scope_and_pit(tmp_path):
    store=SQLiteFinancialFactStore(tmp_path/"facts.sqlite"); old=fact(); assert store.save(old) is FinancialFactWriteOutcome.INSERTED and store.save(old) is FinancialFactWriteOutcome.IDENTICAL
    changed=old.__class__(old.fact_id,old.instrument,old.metric,Decimal("101"),old.currency,old.unit,old.scale,old.period_type,old.value_basis,old.period_start,old.period_end,old.fiscal_year,old.fiscal_quarter,old.statement_scope,old.fact_kind,old.source,old.filing_id,old.source_reference,old.published_at,old.received_at,old.normalization_version,old.provenance,old.parent_fact_ids,old.revision_of_fact_id,old.quality_flags);assert store.save(changed) is FinancialFactWriteOutcome.CONFLICT
    revised=fact(value=Decimal("102"),filing_id="f-revised",source_ref="r-revised",published=T+timedelta(days=3),received=T+timedelta(days=3));assert store.save(revised) is FinancialFactWriteOutcome.INSERTED
    standalone=fact(scope=StatementScope.STANDALONE,filing_id="standalone",source_ref="standalone");assert store.save(standalone) is FinancialFactWriteOutcome.INSERTED
    assert store.series("NSE:ALPHA",FinancialMetric.REVENUE,scope=StatementScope.CONSOLIDATED,as_of=T)==(old,)
    assert revised not in store.series("NSE:ALPHA",FinancialMetric.REVENUE,as_of=T) and len(store.series("NSE:ALPHA",FinancialMetric.REVENUE,scope=StatementScope.STANDALONE))==1

def test_quarterly_annual_ytd_q4_ttm_growth_margins_ratios_and_cashflow():
    derive=FinancialDerivationService(); qs=[fact(value=Decimal(str(100+i*10)),quarter=i+1,year=2025 if i<3 else 2026,filing_id=f"q{i}",source_ref=f"q{i}") for i in range(4)]
    ttm=derive.ttm(qs);assert ttm and ttm.fact_kind is FundamentalFactKind.DERIVED and ttm.value==sum(x.value for x in qs)
    assert derive.ttm(qs[:3]) is None
    annual=fact(value=Decimal("500"),ptype=FinancialPeriodType.ANNUAL,basis=FinancialValueBasis.FULL_YEAR,quarter=None,filing_id="fy",source_ref="fy")
    ytd=fact(value=Decimal("390"),basis=FinancialValueBasis.YEAR_TO_DATE,quarter=3,filing_id="9m",source_ref="9m")
    q4=derive.derive_q4(annual,ytd);assert q4 and q4.value==Decimal("110") and q4.fiscal_quarter==4
    revenue=fact(value=Decimal("200"),filing_id="rev",source_ref="rev");pat=fact(metric=FinancialMetric.PAT,value=Decimal("20"),filing_id="pat",source_ref="pat")
    assert derive.margin(pat,revenue,"PAT_MARGIN").value==Decimal("0.1")
    assert derive.growth(qs[-1],qs[0],"YOY").value is not None
    debt=fact(metric=FinancialMetric.TOTAL_DEBT,value=Decimal("50"),filing_id="debt",source_ref="debt");cash=fact(metric=FinancialMetric.CASH_AND_EQUIVALENTS,value=Decimal("10"),filing_id="cash",source_ref="cash")
    assert derive.balance("NET_DEBT",debt,cash,"subtract").value==Decimal("40")
    cfo=fact(metric=FinancialMetric.CFO,value=Decimal("30"),filing_id="cfo",source_ref="cfo");capex=fact(metric=FinancialMetric.CAPEX,value=Decimal("-12"),filing_id="capex",source_ref="capex")
    assert derive.free_cash_flow(cfo,capex).value==Decimal("18") and derive.free_cash_flow(cfo,replace_value(capex,Decimal("12"))).value is None

def replace_value(value,new): return value.__class__(value.fact_id+"x",value.instrument,value.metric,new,value.currency,value.unit,value.scale,value.period_type,value.value_basis,value.period_start,value.period_end,value.fiscal_year,value.fiscal_quarter,value.statement_scope,value.fact_kind,value.source,value.filing_id,value.source_reference,value.published_at,value.received_at,value.normalization_version,value.provenance,value.parent_fact_ids,value.revision_of_fact_id,value.quality_flags)

def test_snapshot_api_readiness_and_no_estimate_mixing(tmp_path):
    store=SQLiteFinancialFactStore(tmp_path/"a.sqlite"); values=(fact(),fact(metric=FinancialMetric.PAT,value=Decimal("5"),filing_id="pat",source_ref="pat"))
    for value in values: assert store.save(value) is FinancialFactWriteOutcome.INSERTED
    app=create_app(fundamentals_query_service=RepositoryFundamentalsQueryService(store))
    with TestClient(app) as client:
        one=client.get("/api/v1/fundamentals/NSE:ALPHA",params={"as_of":T.isoformat()}); series=client.get("/api/v1/fundamentals/NSE:ALPHA/series",params={"metric":"REVENUE","as_of":T.isoformat()}); mutation=client.post("/api/v1/fundamentals/NSE:ALPHA")
    assert one.status_code==series.status_code==200 and mutation.status_code==405 and series.json()["items"][0]["fact_kind"]=="REPORTED"
    readiness=DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment({"DATA_SOURCE_FUNDAMENTALS_PRIORITY":"stored_data"})).readiness();assert readiness.primary(DataFamily.FUNDAMENTALS).status is SourceReadinessStatus.READY
    with pytest.raises(ValueError): PostgreSQLFinancialFactStore(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.SQLITE,"sqlite:///:memory:")))
