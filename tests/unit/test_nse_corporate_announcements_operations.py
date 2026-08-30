from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.settings import APISettings
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.data_operations.nse_news import NseCorporateAnnouncementsRefreshJob
from app.data_operations.service import DataOperationsService
from app.data_operations.store import DataOperationsStore
from app.intelligence.macro_news_evidence import NewsCatalystEvidenceAdapter
from app.intelligence.unified_state import IntelligenceEvidenceAvailability
from app.news.models import NewsEventCategory, NewsSourceQuality
from app.news.nse_official import (
    NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT, NseAnnouncementSourceError,
    NseCorporateAnnouncementsSource,
)
from app.news.store import SQLiteNewsEvidenceStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot


T = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _record(*, symbol="ALPHA", sequence="111", subject="Board Meeting", date="30-Aug-2026 09:30:00", isin="INE000A01001"):
    return {
        "symbol": symbol, "seq_id": sequence, "desc": subject, "an_dt": date,
        "sort_date": date, "sm_name": "Alpha Limited", "sm_isin": isin, "attchmntFile": "/corporate/alpha.pdf",
        "attchmntText": "Official exchange announcement", "hasXbrl": False,
    }


class _Response:
    def __init__(self, status, payload): self.status_code, self._payload, self.headers = status, payload, {"content-type": "application/json"}
    def json(self): return self._payload


class _Session:
    def __init__(self, payload, *, status=200): self.payload, self.status, self.calls = payload, status, []
    def get(self, url, *, headers, timeout):
        self.calls.append((url, headers, timeout))
        return _Response(403 if url != NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT else self.status, self.payload)


class _Source:
    def __init__(self, values=(), *, failure=None): self.values, self.failure, self.calls = values, failure, 0
    def fetch(self):
        self.calls += 1
        if self.failure: raise NseAnnouncementSourceError(self.failure)
        return self.values, T


class _Universe:
    def __init__(self):
        self.instrument = NseEquityInstrument("NSE:ALPHA", "ALPHA", "INE000A01001", "SOFTWARE", None, "LISTED", None, True, T, "NSE_OFFICIAL", company_name="Alpha Limited")
        self.snapshot = UniverseSnapshot("universe", T, "NSE_OFFICIAL", 1, 1, 0, (), "v1", "checksum", (self.instrument.instrument_id,))
    def latest_universe_snapshot(self): return self.snapshot
    def instruments_as_of(self, at): return (self.instrument,)


def _request():
    return EvidenceRefreshRequest("news-run", EvidenceDataFamily.NEWS, EvidenceRefreshMode.INCREMENTAL, T, T, None, 0)


def test_source_uses_only_official_endpoint_session_headers_and_real_schema():
    session = _Session([_record()])
    source = NseCorporateAnnouncementsSource(session_factory=lambda: session, received_at=lambda: T)
    values, received = source.fetch()
    assert len(values) == 1 and received == T
    value = values[0]
    assert value.symbol == "ALPHA" and value.source_sequence_id == "111"
    assert value.published_at == datetime(2026, 8, 30, 4, 0, tzinfo=UTC)
    assert value.attachment_url == "https://www.nseindia.com/corporate/alpha.pdf"
    assert [item[0] for item in session.calls] == ["https://www.nseindia.com/", NSE_CORPORATE_ANNOUNCEMENTS_ENDPOINT]
    assert session.calls[1][1]["Accept"] == "application/json" and session.calls[1][1]["Referer"] == "https://www.nseindia.com/"


def test_source_fails_closed_for_network_http_and_invalid_payloads():
    with pytest.raises(NseAnnouncementSourceError, match="HTTP_ERROR"):
        NseCorporateAnnouncementsSource(session_factory=lambda: _Session([], status=500)).fetch()
    with pytest.raises(NseAnnouncementSourceError, match="PARSE_ERROR"):
        NseCorporateAnnouncementsSource(session_factory=lambda: _Session([{"symbol": "ALPHA"}])).fetch()


def test_news_job_maps_exact_symbol_preserves_primary_facts_and_is_idempotent(tmp_path):
    source = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T)
    store = SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite")
    job = NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=store, source=source)
    first, second = job.refresh(_request()), job.refresh(_request())
    evidence = store.list(instrument_id="NSE:ALPHA", as_of=T + timedelta(days=1))[0]
    assert (first.status, first.accepted_count, first.duplicate_count) == (EvidenceRefreshStatus.COMPLETE, 1, 0)
    assert (second.status, second.accepted_count, second.duplicate_count) == (EvidenceRefreshStatus.NO_CHANGE, 0, 1)
    assert evidence.source_quality is NewsSourceQuality.PRIMARY_EXCHANGE
    assert evidence.event_category is NewsEventCategory.UNCLASSIFIED
    assert evidence.company_name == "Alpha Limited"
    assert evidence.provenance.source_reference.startswith("111:")
    assert "NO_SENTIMENT_OR_IMPACT_INTERPRETATION" in evidence.warnings


def test_repeat_source_event_retains_first_observed_receipt_time(tmp_path):
    store = SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite")
    first = NseCorporateAnnouncementsRefreshJob(
        universe=_Universe(), news=store,
        source=NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T),
    )
    later = NseCorporateAnnouncementsRefreshJob(
        universe=_Universe(), news=store,
        source=NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T + timedelta(minutes=3)),
    )
    assert first.refresh(_request()).accepted_count == 1
    repeat = later.refresh(_request())
    evidence = store.list(instrument_id="NSE:ALPHA", as_of=T + timedelta(days=1))[0]
    assert repeat.duplicate_count == 1 and repeat.conflict_count == 0
    assert evidence.received_at == T


def test_unmapped_symbol_is_typed_and_never_fuzzy_matched(tmp_path):
    source = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record(symbol="ALPHAH")]), received_at=lambda: T)
    job = NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite"), source=source)
    result = job.refresh(_request())
    assert result.status is EvidenceRefreshStatus.PARTIAL and result.gap_count == 1
    assert result.findings == ((result.findings[0][0], "ALPHAH", "NSE_ANNOUNCEMENT_EXACT_SYMBOL_UNRESOLVED"),)


def test_identical_universe_snapshot_copies_do_not_create_false_symbol_ambiguity(tmp_path):
    universe = _Universe()
    original = universe.instruments_as_of
    universe.instruments_as_of = lambda at: original(at) + original(at)
    job = NseCorporateAnnouncementsRefreshJob(
        universe=universe, news=SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite"),
        source=NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T),
    )
    assert job.refresh(_request()).accepted_count == 1


def test_source_isin_disambiguates_multiple_canonical_ids_for_the_same_symbol(tmp_path):
    universe = _Universe()
    older = NseEquityInstrument("NSE:LEGACY-ALPHA", "ALPHA", "INE999A01001", "SOFTWARE", None, "LISTED", None, True, T, "NSE_OFFICIAL")
    universe.instruments_as_of = lambda at: (universe.instrument, older)
    job = NseCorporateAnnouncementsRefreshJob(
        universe=universe, news=SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite"),
        source=NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T),
    )
    assert job.refresh(_request()).accepted_count == 1


def test_source_failure_retains_no_synthetic_evidence(tmp_path):
    job = NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite"), source=_Source(failure="RATE_LIMITED"))
    result = job.refresh(_request())
    assert result.status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE
    assert result.error_summary == "RATE_LIMITED" and result.accepted_count == result.discovered_count == 0


def test_pit_visibility_is_before_after_publication_only(tmp_path):
    source = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T)
    store = SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite")
    NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=store, source=source).refresh(_request())
    before = datetime(2026, 8, 30, 9, 29, tzinfo=UTC)
    after = datetime(2026, 8, 30, 10, 1, tzinfo=UTC)
    assert store.list(instrument_id="NSE:ALPHA", as_of=before) == ()
    assert len(store.list(instrument_id="NSE:ALPHA", as_of=after)) == 1


def test_rebroadcasted_source_record_is_preserved_as_a_distinct_immutable_version(tmp_path):
    store = SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite")
    universe = _Universe()
    first = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record(subject="First")]), received_at=lambda: T)
    second = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record(subject="Corrected")]), received_at=lambda: T + timedelta(minutes=1))
    assert NseCorporateAnnouncementsRefreshJob(universe=universe, news=store, source=first).refresh(_request()).accepted_count == 1
    assert NseCorporateAnnouncementsRefreshJob(universe=universe, news=store, source=second).refresh(_request()).accepted_count == 1
    assert len(store.list(instrument_id="NSE:ALPHA", as_of=T + timedelta(days=1))) == 2


def test_u17_run_writes_factual_watermark_and_primary_news_is_visible_to_shared_brain(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    source = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T)
    store = SQLiteNewsEvidenceStore(tmp_path / "evidence.sqlite")
    operations = DataOperationsService(DataOperationsStore(repository), {EvidenceDataFamily.NEWS: NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=store, source=source)}, clock=lambda: T)
    run = operations.run(EvidenceDataFamily.NEWS, run_id="news-run")
    assert run.status is EvidenceRefreshStatus.COMPLETE
    watermark = operations._store.latest_watermark(EvidenceDataFamily.NEWS)
    assert watermark is not None and watermark.accepted_through == datetime(2026, 8, 30, 4, 0, tzinfo=UTC)
    artifacts = NewsCatalystEvidenceAdapter(news=store).artifacts("NSE:ALPHA", as_of=T + timedelta(days=1))
    assert artifacts[0].availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert "OFFICIAL_EXCHANGE_DISCLOSURE" in artifacts[0].warnings


def test_persistent_api_composes_the_existing_read_only_news_store(tmp_path):
    path = tmp_path / "persistent.sqlite"
    source = NseCorporateAnnouncementsSource(session_factory=lambda: _Session([_record()]), received_at=lambda: T)
    store = SQLiteNewsEvidenceStore(path)
    NseCorporateAnnouncementsRefreshJob(universe=_Universe(), news=store, source=source).refresh(_request())
    settings = APISettings(database=DatabaseSettings(DatabaseBackend.SQLITE, "sqlite:///" + path.as_posix()))
    with TestClient(create_app(api_settings=settings)) as client:
        response = client.get("/api/v1/news", params={"symbol": "NSE:ALPHA"})
    assert response.status_code == 200 and response.json()["items"][0]["source_provider"] == "NSE_OFFICIAL"


def test_production_code_has_no_synthetic_gemini_or_sentiment_path():
    source = ("app/news/nse_official.py", "app/data_operations/nse_news.py")
    names = {
        node.id.casefold() for path in source for node in ast.walk(ast.parse(open(path, encoding="utf-8").read()))
        if isinstance(node, ast.Name)
    }
    assert not names.intersection({"gemini", "synthetic", "bullish", "bearish", "impact", "relevance", "express"})
