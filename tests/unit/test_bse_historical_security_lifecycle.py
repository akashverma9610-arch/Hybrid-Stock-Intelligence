from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import sys

import pytest

from app.fundamentals.bse_collector import BSE_OFFICIAL_NOTICE_URL, BseOfficialHttpResponse, BseOfficialHttpTransport
from app.historical.bse_lifecycle import (
    BseLifecycleEventType, BseLifecycleReceiptStatus, BsePrimaryLifecycleEvidence,
    BsePrimaryLifecycleEvidenceStore, BsePrimaryLifecycleIngestor, ExactCanonicalSecurityLink,
    extract_compulsory_delisted_pdf, parse_bse_lifecycle_notice, parse_compulsory_delisted_list_text,
    resolve_delisted_row_exact_isin, BseDelistedRowLinkStatus,
)
from app.historical.security_identity_selector import HistoricalSecurityIdentityResolutionStatus, resolve_historical_security_identity
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityMasterStore, HistoricalSecurityStatus
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2025, 6, 20, tzinfo=UTC)
LINK = ExactCanonicalSecurityLink("NSE:INE000A01001", "500001", "INE000A01001", "BSE_OFFICIAL_SCRIP_MASTER")


def _notice(*, kind=BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE, effective=T + timedelta(days=6), code="500001", isin="INE000A01001"):
    return BsePrimaryLifecycleEvidence(
        notice_id="20250620-7", source_reference="https://www.bseindia.com/markets/MarketInfo/DispNewNoticesCirculars.aspx?page=20250620-7",
        content_fingerprint="sha256:" + "a" * 64, published_at=T, effective_at=effective, event_type=kind,
        bse_scrip_code=code, isin=isin, symbol_before="OLDCO" if kind is BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE else None,
        symbol_after="NEWCO" if kind is BseLifecycleEventType.NAME_OR_SCRIP_ID_CHANGE else None, company_name="Synthetic Company",
    )


def _stores(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "lifecycle.sqlite")
    return repo, HistoricalSecurityMasterStore(repo), BsePrimaryLifecycleEvidenceStore(repo)


def test_notice_preserves_known_and_future_effective_time_and_exact_change_continuity(tmp_path):
    repo, identities, evidence = _stores(tmp_path)
    receipt = BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities).ingest(_notice(), links=(LINK,))
    assert receipt.status is BseLifecycleReceiptStatus.INSERTED
    values = tuple(item.payload for item in repo.list_snapshots(__import__("app.storage.core_api_snapshot_repository", fromlist=["CoreApiSnapshotFamily"]).CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY))
    assert len(values) == 2 and all(item.as_of == T and item.exchange_security_code == "500001" for item in values)
    before = resolve_historical_security_identity(values, canonical_instrument_id=LINK.canonical_instrument_id, as_of=T + timedelta(days=2))
    after = resolve_historical_security_identity(values, canonical_instrument_id=LINK.canonical_instrument_id, as_of=T + timedelta(days=7))
    assert before.status is HistoricalSecurityIdentityResolutionStatus.RESOLVED and before.symbol == "OLDCO"
    assert after.status is HistoricalSecurityIdentityResolutionStatus.RESOLVED and after.symbol == "NEWCO"
    assert before.identity_id != after.identity_id


def test_future_known_notice_is_excluded_and_current_symbol_never_substitutes_backward(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    value = _notice()
    BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities).ingest(value, links=(LINK,))
    snapshots = tuple(item.payload for item in identities._all(__import__("app.storage.core_api_snapshot_repository", fromlist=["CoreApiSnapshotFamily"]).CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY))
    result = resolve_historical_security_identity(snapshots, canonical_instrument_id=LINK.canonical_instrument_id, as_of=T - timedelta(microseconds=1))
    assert result.status is HistoricalSecurityIdentityResolutionStatus.DATA_UNAVAILABLE


def test_delisting_is_distinct_and_only_excludes_after_effective_time(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    active = HistoricalSecurityIdentity("prior", LINK.canonical_instrument_id, LINK.isin, "BSE", "OLDCO", None, None, None, T - timedelta(days=5), None, T - timedelta(days=5), None, HistoricalSecurityStatus.ACTIVE, "BSE_NOTICE", T - timedelta(days=5), "v1")
    identities.save_identity(active)
    event = _notice(kind=BseLifecycleEventType.DELISTING)
    BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities).ingest(event, links=(LINK,))
    snapshots = tuple(item.payload for item in identities._all(__import__("app.storage.core_api_snapshot_repository", fromlist=["CoreApiSnapshotFamily"]).CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY))
    assert resolve_historical_security_identity(snapshots, canonical_instrument_id=LINK.canonical_instrument_id, as_of=event.effective_at - timedelta(microseconds=1)).status is HistoricalSecurityIdentityResolutionStatus.RESOLVED
    assert resolve_historical_security_identity(snapshots, canonical_instrument_id=LINK.canonical_instrument_id, as_of=event.effective_at).status is HistoricalSecurityIdentityResolutionStatus.NOT_LISTED


def test_suspension_listing_relisting_and_merger_keep_distinct_statuses(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    ingestor = BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities)
    for index, kind in enumerate((BseLifecycleEventType.SUSPENSION, BseLifecycleEventType.LISTING, BseLifecycleEventType.RELISTING, BseLifecycleEventType.MERGER_OR_CESSATION)):
        event = _notice(kind=kind, effective=T + timedelta(days=index), code=f"50000{index + 1}", isin=f"INE000A0100{index + 1}")
        link = ExactCanonicalSecurityLink(f"NSE:INE000A0100{index + 1}", event.bse_scrip_code, event.isin, "BSE_MASTER")
        assert ingestor.ingest(event, links=(link,)).status is BseLifecycleReceiptStatus.INSERTED
    values = tuple(item.payload for item in identities._all(__import__("app.storage.core_api_snapshot_repository", fromlist=["CoreApiSnapshotFamily"]).CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY))
    assert {item.status for item in values} == {HistoricalSecurityStatus.SUSPENDED, HistoricalSecurityStatus.ACTIVE, HistoricalSecurityStatus.RELISTED, HistoricalSecurityStatus.MERGED}
    relisted = next(item for item in values if item.status is HistoricalSecurityStatus.RELISTED)
    assert resolve_historical_security_identity(values, canonical_instrument_id=relisted.canonical_instrument_id, as_of=relisted.symbol_effective_from).status is HistoricalSecurityIdentityResolutionStatus.RESOLVED


def test_exact_bse_or_isin_link_is_allowed_but_fuzzy_name_is_rejected(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    ingestor = BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities)
    exact = ingestor.ingest(_notice(), links=(LINK,))
    assert exact.status is BseLifecycleReceiptStatus.INSERTED
    other = _notice(code="500002", isin="INE000A01002")
    fuzzy = ExactCanonicalSecurityLink("NSE:INE000A01001", "500003", "INE000A01003", "BSE_MASTER")
    assert ingestor.ingest(other, links=(fuzzy,)).status is BseLifecycleReceiptStatus.STAGED_UNRESOLVED
    isin_only = _notice(code=None, isin="INE000A01002")
    assert ingestor.ingest(isin_only, links=(ExactCanonicalSecurityLink("NSE:INE000A01002", None, "INE000A01002", "BSE_MASTER"),)).status is BseLifecycleReceiptStatus.INSERTED
    assert not identities.identities_as_of(T + timedelta(days=10)) == ()


def test_unresolved_compiled_delisted_rows_are_preserved_without_name_linking(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    rows = parse_compulsory_delisted_list_text(text="Example Delisted Ltd | INE000A01002 | March 10, 2023", source_reference="https://www.bseindia.com/downloads1/comp_delisted_cos_db.pdf", published_at=T)
    receipt = BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities).ingest(rows[0], links=())
    assert receipt.status is BseLifecycleReceiptStatus.STAGED_UNRESOLVED
    assert receipt.reason_codes == ("EXACT_CANONICAL_LINK_REQUIRED",)


def test_replay_is_idempotent_and_conflicting_exact_links_fail_closed(tmp_path):
    _, identities, evidence = _stores(tmp_path)
    ingestor = BsePrimaryLifecycleIngestor(evidence_store=evidence, identity_store=identities)
    event = _notice()
    assert ingestor.ingest(event, links=(LINK,)).status is BseLifecycleReceiptStatus.INSERTED
    assert ingestor.ingest(event, links=(LINK,)).status is BseLifecycleReceiptStatus.ALREADY_PRESENT
    conflicting = ExactCanonicalSecurityLink("NSE:INE999A01001", LINK.bse_scrip_code, LINK.isin, "BSE_MASTER")
    assert ingestor.ingest(_notice(code="500001", isin="INE000A01001"), links=(LINK, conflicting)).status is BseLifecycleReceiptStatus.EVIDENCE_CONFLICTED


def test_parser_accepts_only_explicit_bse_notice_metadata_and_fixed_transport_path():
    html = b"<html>Notice No. 20230303-49 Notice Date 03 Mar 2023 Category Company related Subject Voluntary Delisting of Synthetic (Scrip Code: 502742) Further the above scrip will be delisted from the records of the Exchange w.e.f. Friday, March 10, 2023.</html>"
    response = BseOfficialHttpResponse(BSE_OFFICIAL_NOTICE_URL.format(notice_id="20230303-49"), "text/html", html, T)
    parsed = parse_bse_lifecycle_notice(response)
    assert parsed.notice_id == "20230303-49" and parsed.event_type is BseLifecycleEventType.DELISTING
    assert parsed.published_at == datetime(2023, 3, 3, tzinfo=UTC) and parsed.effective_at == datetime(2023, 3, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="EXACT_KEY"):
        parse_bse_lifecycle_notice(BseOfficialHttpResponse(response.url, "text/html", b"Notice No. 20230303-49 Notice Date 03 Mar 2023 Subject Delisting w.e.f. March 10, 2023", T))
    transport = BseOfficialHttpTransport(fetch=lambda url, _max: response)
    assert transport.fetch_lifecycle_notice("20230303-49").url == response.url
    with pytest.raises(ValueError, match="IDENTIFIER_INVALID"):
        transport.fetch_lifecycle_notice("../../not-a-notice")


def test_forbidden_boundaries_are_static():
    import app.historical.bse_lifecycle as module
    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "sqlite3", "datetime.now"):
        assert forbidden not in source


def test_compulsory_delisted_pdf_extraction_is_deterministic_and_preserves_exact_row_boundaries(monkeypatch):
    class Page:
        def extract_tables(self):
            return [[
                ["Sr. No.", "Name", "Lot", "ISIN", "Face", "Demat", "Date"],
                ["1", "Exact Delisted Ltd", "100", "INE814B01014", "10", "D", "August 17, 2016"],
                ["2", "No Isin Ltd", "1", "Not Available", "10", "P", "August 17, 2016"],
                ["3", "Bad Isin Ltd", "1", "BAD", "10", "D", "August 17, 2016"],
                ["4", "Bad Date Ltd", "1", "INE504C01019", "10", "D", "never"],
            ]]
        def extract_text(self): return ""
    class Document:
        pages = [Page()]
        def __enter__(self): return self
        def __exit__(self, *_): return False
    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _source: Document()))
    response = BseOfficialHttpResponse("https://www.bseindia.com/downloads1/comp_delisted_cos_db.pdf", "application/pdf", b"synthetic-pdf", T)
    one, two = extract_compulsory_delisted_pdf(response), extract_compulsory_delisted_pdf(response)
    assert [(item.row_number, item.isin, item.delisted_at) for item in one.rows] == [(1, "INE814B01014", datetime(2016, 8, 17, tzinfo=UTC)), (2, None, datetime(2016, 8, 17, tzinfo=UTC))]
    assert one.rejected_rows == 2 and one.invalid_isin_rows == 1 and one.invalid_date_rows == 1
    assert one.fingerprint == two.fingerprint and all(item.historical_known_at is None for item in one.rows)


def test_compulsory_delisted_rows_link_by_exact_isin_only_and_are_idempotently_stored(monkeypatch, tmp_path):
    class Page:
        def extract_tables(self): return [[["1", "Exact Delisted Ltd", "100", "INE814B01014", "10", "D", "August 17, 2016"]]]
        def extract_text(self): return ""
    class Document:
        pages = [Page()]
        def __enter__(self): return self
        def __exit__(self, *_): return False
    monkeypatch.setitem(sys.modules, "pdfplumber", SimpleNamespace(open=lambda _source: Document()))
    row = extract_compulsory_delisted_pdf(BseOfficialHttpResponse("https://www.bseindia.com/downloads1/comp_delisted_cos_db.pdf", "application/pdf", b"pdf", T)).rows[0]
    exact = ExactCanonicalSecurityLink("NSE:INE814B01014", None, "INE814B01014", "BSE_MASTER")
    linked = resolve_delisted_row_exact_isin(row, links=(exact,))
    assert linked.status is BseDelistedRowLinkStatus.EXACT_CANONICAL_LINKED and linked.canonical_instrument_id == exact.canonical_instrument_id
    assert resolve_delisted_row_exact_isin(row, links=()).status is BseDelistedRowLinkStatus.UNRESOLVED
    ambiguous = ExactCanonicalSecurityLink("NSE:OTHER", None, exact.isin, "BSE_MASTER")
    assert resolve_delisted_row_exact_isin(row, links=(exact, ambiguous)).status is BseDelistedRowLinkStatus.EVIDENCE_CONFLICTED
    repo, identities, evidence = _stores(tmp_path)
    replay = extract_compulsory_delisted_pdf(BseOfficialHttpResponse("https://www.bseindia.com/downloads1/comp_delisted_cos_db.pdf", "application/pdf", b"pdf", T + timedelta(days=1))).rows[0]
    assert row.row_id == replay.row_id and evidence.save_delisted_row(row) is True and evidence.save_delisted_row(replay) is False
    assert not identities.identities_as_of(T)
