from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest
from fastapi.testclient import TestClient

from app.api.filings_query import RepositoryFilingsQueryService
from app.api.main import create_app
from app.data_sources.models import DataFamily, SourceReadinessStatus
from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
from app.filings.models import (AttachmentParseStatus, BoardMeetingMetadata, CorporateActionDisclosure, FilingAttachment, FilingTextAvailability, FilingType, FinancialResultMetadata, PrimarySourceFilingRecord)
from app.filings.providers import BSECorporateFilingsAdapter, MockPrimarySourceFilingsProvider, NSECorporateFilingsAdapter, normalize_primary_filing
from app.filings.service import CorporateFilingsIngestionService
from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings


T = datetime(2026, 8, 26, 10, tzinfo=UTC)

def instrument(symbol="ALPHA", exchange=Exchange.NSE): return InstrumentIdentity(f"{exchange.value}:{symbol}", exchange, symbol, symbol, None, None, InstrumentType.NSE_EQUITY if exchange is Exchange.NSE else InstrumentType.BSE_EQUITY, symbol)
def attachment(identifier="a-1"): return FilingAttachment(identifier,"PDF","Results","results.pdf",f"doc://{identifier}","application/pdf",T,parse_status=AttachmentParseStatus.NOT_FETCHED,is_xbrl=False)
def record(identifier, *, source="nse", exchange=Exchange.NSE, symbol="ALPHA", category="Financial Results", announced=T, received=T, revision=None, action=None, financial=None, board=None, reporting=None):
    return PrimarySourceFilingRecord(source,exchange,instrument(symbol,exchange),identifier,category,f"{category} {identifier}",announced,received,f"doc://{identifier}",period_end=financial.period_end if financial else None,text_availability=FilingTextAvailability.DOCUMENT_ONLY,attachments=(attachment(identifier),),revision_of_filing_id=revision,action=action,financial_result=financial,board_meeting=board,reporting_as_of=reporting)

def fixture_records():
    result = record("nse-result", financial=FinancialResultMetadata(T-timedelta(days=90),"CONSOLIDATED","QUARTERLY"))
    board = record("nse-board", category="Board Meeting", board=BoardMeetingMetadata(T+timedelta(days=7),"Results consideration"))
    presentation = record("nse-presentation", category="Investor Presentation")
    dividend = record("nse-dividend", category="Dividend", action=CorporateActionDisclosure(FilingType.DIVIDEND,record_date=T+timedelta(days=10),amount=Decimal("2.5")))
    holding = record("nse-holding", category="Shareholding Pattern", reporting=T-timedelta(days=30))
    acquisition = record("nse-acquisition", category="Acquisition Update")
    revision = record("nse-result-rev", category="Financial Results", announced=T+timedelta(days=1), received=T+timedelta(days=1), revision=normalize_primary_filing(result).filing_id, financial=FinancialResultMetadata(T-timedelta(days=90),"CONSOLIDATED","QUARTERLY",True))
    bse_equivalent = record("bse-result", source="bse", exchange=Exchange.BSE, category="Financial Results")
    beta = record("nse-beta", symbol="BETA", category="Investor Presentation")
    return (result,board,presentation,dividend,holding,acquisition,revision,result,bse_equivalent,beta)

def ingest(tmp_path):
    store=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
    report=CorporateFilingsIngestionService(MockPrimarySourceFilingsProvider(fixture_records()),store,clock=lambda:T).ingest(instrument_id=None,start=T-timedelta(days=2),end=T+timedelta(days=2))
    return store,report

def test_taxonomy_adapter_normalization_deterministic_identity_and_metadata():
    raw=fixture_records()[0]; nse=NSECorporateFilingsAdapter().normalize(raw)
    assert nse.filing_type is FilingType.FINANCIAL_RESULTS and nse.financial_result.result_scope=="CONSOLIDATED"
    assert nse == normalize_primary_filing(raw) and nse.attachments[0].source_reference.startswith("doc://")
    with pytest.raises(ValueError): NSECorporateFilingsAdapter().normalize(fixture_records()[-2])
    assert BSECorporateFilingsAdapter().normalize(fixture_records()[-2]).exchange is Exchange.BSE

def test_sqlite_ingestion_dedup_revisions_cross_exchange_filters_and_pit(tmp_path):
    store,report=ingest(tmp_path)
    assert (report.received_count,report.accepted_count,report.duplicate_count,report.revision_count,report.rejected_count)==(10,9,1,1,0)
    assert report.attachment_count==10 and store.get("nse:NSE:nse-result") is not None
    original=store.get("nse:NSE:nse-result")
    assert len(store.revisions(original.filing_id))==1
    assert len(store.list(instrument_id="NSE:ALPHA",limit=20))==7
    assert len(store.list(filing_type=FilingType.INVESTOR_PRESENTATION,limit=20))==2
    assert len(store.list(exchange=Exchange.BSE,limit=20))==1
    assert len(store.list(start=T,end=T,limit=20))==8
    future_received=record("received-later",announced=T,received=T+timedelta(hours=2))
    assert CorporateFilingsIngestionService(MockPrimarySourceFilingsProvider((future_received,)),store,clock=lambda:T).ingest(instrument_id=None,start=T,end=T).accepted_count==1
    assert all(item.filing_id!="nse:NSE:received-later" for item in store.list(as_of=T+timedelta(hours=1),limit=20))
    assert store.get("bse:BSE:bse-result") is not None

def test_action_board_shareholding_postgres_selection_and_primary_readiness(tmp_path):
    store,_=ingest(tmp_path)
    dividend=store.get("nse:NSE:nse-dividend"); board=store.get("nse:NSE:nse-board"); holding=store.get("nse:NSE:nse-holding")
    assert dividend.action.action_type is FilingType.DIVIDEND and dividend.action.amount==Decimal("2.5")
    assert board.board_meeting.meeting_date>T and holding.reporting_as_of==T-timedelta(days=30)
    with pytest.raises(ValueError,match="PostgreSQL"):
        PostgreSQLCorporateFilingsStore(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.SQLITE,"sqlite:///:memory:")))
    readiness=DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment({"DATA_SOURCE_CORPORATE_FILINGS_PRIORITY":"nse_filings,bse_filings"}),clock=lambda:T).readiness()
    assert [item.status for item in readiness.for_family(DataFamily.CORPORATE_FILINGS)]==[SourceReadinessStatus.CONFIGURED_NOT_VALIDATED,SourceReadinessStatus.CONFIGURED_NOT_VALIDATED]

def test_read_only_filings_api_has_bounded_filters_and_no_ingestion_side_effects(tmp_path):
    store,_=ingest(tmp_path); app=create_app(filings_query_service=RepositoryFilingsQueryService(store))
    with TestClient(app) as client:
        listed=client.get("/api/v1/filings",params={"symbol":"NSE:ALPHA","type":"FINANCIAL_RESULTS","limit":10})
        detail=client.get("/api/v1/filings/nse:NSE:nse-result")
        missing=client.get("/api/v1/filings/missing")
        mutation=client.post("/api/v1/filings")
    assert listed.status_code==detail.status_code==200 and len(listed.json()["items"])==2
    assert detail.json()["attachments"][0]["source_reference"]=="doc://nse-result" and missing.status_code==404 and mutation.status_code==405
    import app.filings.providers as providers
    source=inspect.getsource(providers).lower()
    assert not any(token in source for token in ("requests.","httpx","selenium","playwright","websocket","place_order","demat","promotion"))
