from __future__ import annotations

from datetime import UTC, date, datetime
import gzip
from types import SimpleNamespace

import pytest

from app.historical.nse_mii_security_master import (
    NseMiiAvailabilitySemantics, NseMiiIngestionStatus, NseMiiSecurityMasterError,
    NseMiiSecurityMasterEvidenceStore, NseMiiSecurityMasterHttpResponse,
    NseOfficialMiiSecurityMasterTransport, exact_bse_delisted_isin_overlaps,
    extract_nse_mii_security_master, nse_mii_security_master_url,
    rows_not_after_report_date, same_isin_symbol_changes,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 4, 6, 0, tzinfo=UTC)
D = date(2025, 12, 29)
HEADERS = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,"
    "ListgDt,RmvlDt,FinInstrmTp,SctyTp,Ignored\n"
)


def _csv(*rows: str) -> bytes:
    return gzip.compress((HEADERS + "\n".join(rows) + "\n").encode())


def _response(*, report_date: date = D, body: bytes | None = None, content_type: str | None = "application/x-gzip"):
    return NseMiiSecurityMasterHttpResponse(
        requested_date=report_date, source_reference=nse_mii_security_master_url(report_date),
        content_type=content_type, body=body or _csv(
            "100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY,",
            "101,RENAMED,EQ,Renamed Ltd,INE000A01002,6,200,0,EQ,EQUITY,",
            "102,BAD,EQ,Bad Ltd,INVALID,6,0,0,EQ,EQUITY,",
        ), document_observed_at=T,
    )


def test_request_is_fixed_official_date_path_and_transport_is_bounded():
    assert nse_mii_security_master_url(D) == "https://nsearchives.nseindia.com/content/cm/NSE_CM_security_29122025.csv.gz"

    class Session:
        def get(self, url, *, headers, timeout):
            assert url == nse_mii_security_master_url(D) and timeout == 15
            assert headers["Referer"] == "https://www.nseindia.com/all-reports"
            return SimpleNamespace(status_code=200, headers={"Content-Type": "application/x-gzip"}, content=_response().body)

    value = NseOfficialMiiSecurityMasterTransport(session=Session(), timeout_seconds=15).fetch(D)
    assert value.source_reference == nse_mii_security_master_url(D)


def test_unavailable_date_and_html_or_gzip_fail_closed():
    class MissingSession:
        def get(self, *_args, **_kwargs): return SimpleNamespace(status_code=404, headers={}, content=b"")
    with pytest.raises(NseMiiSecurityMasterError, match="REPORT_UNAVAILABLE"):
        NseOfficialMiiSecurityMasterTransport(session=MissingSession()).fetch(D)
    with pytest.raises(NseMiiSecurityMasterError, match="CONTENT_TYPE_INVALID"):
        extract_nse_mii_security_master(_response(body=b"<html>not a report</html>", content_type="text/html"))
    with pytest.raises(NseMiiSecurityMasterError, match="GZIP_REQUIRED"):
        extract_nse_mii_security_master(_response(body=b"not gzip", content_type="application/octet-stream"))


def test_required_columns_and_date_filename_parity_are_strict():
    bad = gzip.compress(b"TckrSymb,ISIN\nEXACT,INE000A01001\n")
    with pytest.raises(NseMiiSecurityMasterError, match="REQUIRED_COLUMNS_MISSING"):
        extract_nse_mii_security_master(_response(body=bad))
    with pytest.raises(NseMiiSecurityMasterError, match="RESPONSE_INVALID"):
        NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(date(2025, 12, 30)), "application/x-gzip", _csv(), T)


def test_exact_fields_are_preserved_with_date_only_availability_and_no_identity_promotion():
    extraction = extract_nse_mii_security_master(_response())
    assert extraction.snapshot.report_date == D
    assert extraction.snapshot.historical_known_at is None
    assert extraction.snapshot.availability_semantics is NseMiiAvailabilitySemantics.DOCUMENTED_PRE_TRADING_DATE_ONLY
    assert extraction.invalid_identity_rows == 1
    row = extraction.rows[0]
    assert (row.symbol, row.isin, row.series, row.security_code, row.security_name) == ("EXACT", "INE000A01001", "EQ", "100", "Exact Ltd")
    assert (row.normal_market_status_raw, row.financial_instrument_type_raw, row.security_type_raw) == ("6", "EQ", "EQUITY")
    assert row.listing_date_raw == "100" and row.removal_date_raw == "0"
    assert row.historical_known_at is None
    assert not hasattr(row, "canonical_instrument_id") and not hasattr(row, "listed_from")


def test_row_and_snapshot_fingerprints_are_deterministic_and_observation_time_does_not_change_identity():
    one = extract_nse_mii_security_master(_response())
    two = extract_nse_mii_security_master(_response())
    later = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(D, nse_mii_security_master_url(D), "application/x-gzip", _response().body, T.replace(hour=7)))
    assert one.fingerprint == two.fingerprint and one.snapshot.snapshot_id == later.snapshot.snapshot_id
    assert [row.row_id for row in one.rows] == [row.row_id for row in later.rows]
    assert one.rows[0].fingerprint != later.rows[0].fingerprint  # provenance includes observation, identity does not


def test_append_only_replay_and_snapshot_serialization_round_trip(tmp_path):
    extraction = extract_nse_mii_security_master(_response())
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "history.sqlite")
    store = NseMiiSecurityMasterEvidenceStore(repo)
    first, replay = store.save(extraction), store.save(extraction)
    assert first.status is NseMiiIngestionStatus.INSERTED and first.rows_inserted == 2
    assert replay.status is NseMiiIngestionStatus.ALREADY_PRESENT and replay.rows_inserted == 0 and replay.rows_already_present == 2
    stored = store.snapshot(extraction.snapshot.snapshot_id)
    assert stored == extraction.snapshot
    values = repo.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT, limit=10)
    assert len(values) == 3 and {type(value.payload).__name__ for value in values} == {"NseMiiSecurityMasterSnapshot", "NseMiiSecurityMasterRow"}


def test_bounded_row_page_resumes_without_duplicate_snapshot_or_rows(tmp_path):
    extraction = extract_nse_mii_security_master(_response())
    store = NseMiiSecurityMasterEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "page.sqlite"))
    first = store.save_rows(extraction, offset=0, limit=1)
    second = store.save_rows(extraction, offset=1, limit=1)
    replay = store.save_rows(extraction, offset=0, limit=1)
    assert (first.rows_inserted, second.rows_inserted, replay.rows_already_present) == (1, 1, 1)
    with pytest.raises(NseMiiSecurityMasterError, match="ROW_PAGE_INVALID"):
        store.save_rows(extraction, offset=2, limit=1)


def test_no_fuzzy_linkage_only_exact_isin_cross_reference_and_changed_symbol_observation():
    first = extract_nse_mii_security_master(_response())
    next_date = date(2026, 8, 20)
    second = extract_nse_mii_security_master(_response(
        report_date=next_date,
        body=_csv("110,NEWNAME,EQ,Renamed Ltd,INE000A01002,6,200,0,EQ,EQUITY,"),
    ))
    assert same_isin_symbol_changes((*first.rows, *second.rows)) == (("INE000A01002", ("NEWNAME", "RENAMED")),)
    assert exact_bse_delisted_isin_overlaps((*first.rows, *second.rows), bse_delisted_isins=("INE000A01002", "ine000a01002", "unrelated")) == ("INE000A01002",)
    assert exact_bse_delisted_isin_overlaps(first.rows, bse_delisted_isins=("Exact Ltd",)) == ()


def test_future_snapshot_is_excluded_from_earlier_descriptive_date_boundary():
    older = extract_nse_mii_security_master(_response(report_date=date(2025, 12, 29)))
    future = extract_nse_mii_security_master(_response(report_date=date(2026, 8, 20)))
    assert rows_not_after_report_date((*older.rows, *future.rows), as_of_date=date(2025, 12, 29)) == older.rows


def test_static_boundaries_exclude_identity_promotion_fuzzy_company_type_and_execution():
    import app.historical.nse_mii_security_master as module
    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in (
        "HistoricalSecurityIdentity", "app.signals", "app.portfolio", "app.broker", "app.orders",
        "app.api", "app.runtime", "sqlite3", "Compounder", "company_type", "fuzzy", "place_order",
    ):
        assert forbidden not in source
