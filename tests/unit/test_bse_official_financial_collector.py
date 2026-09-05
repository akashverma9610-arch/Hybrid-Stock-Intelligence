from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.bse_collector import (
    BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL, BSE_OFFICIAL_RESULTS_ARCHIVE_URL, BSE_OFFICIAL_SCRIP_MASTER_URL, COMPOUNDER_NON_FINANCIAL_BSE_HISTORICAL_TARGETS, REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS,
    BseArchiveSnapshot, BseBoundedXbrlRecoveryReceipt, BseCollectorError, BseFilingDisposition, BseMappingStatus, BseOfficialArchiveSnapshotStore, BseOfficialBoundedXbrlAcquirer, BseOfficialFinancialCollector,
    BseOfficialFinancialCollectorSettings, BseOfficialFinancialCollectorWorker,
    BseOfficialHttpResponse, BseOfficialHttpTransport, BseOfficialIciciBoundedXbrlRecovery, BseOfficialSecurityMaster,
    BseOfficialXbrlStaging, BseXbrlStreamingPolicy, _historical_annual_metadata,
    BseOfficialXbrlStaging, BseStageDisposition,
)
from app.fundamentals.bse_official import (
    BSE_RESULT_ARCHIVE, BSE_RESULT_PAGE, BSEOfficialFinancialResultsArchiveProvider, BSEOfficialLocalXbrlIngestionService,
    BSEOfficialFinancialResultsProvider, BseOfficialError,
)
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 8, 25, 12, tzinfo=UTC)
ISIN = "INE372A01015"
CODE = "532259"
TARGET = "NSE:" + ISIN
PAGE = BSE_RESULT_PAGE.format(security_code=CODE)
XBRL = "https://www.bseindia.com/XBRLFILES/apar-jun-2026.xml"
ARCHIVE = BSE_RESULT_ARCHIVE.format(security_code=CODE)


def _lookup(*, duplicate: bool = False) -> bytes:
    values = [
        "<li class='quotemenu quotemenuselect' ng-click=\"liclick('532259','APAR INDUSTRIES LTD')\"><a>APAR INDUSTRIES LTD<br /><span>APARINDS&nbsp;&nbsp;&nbsp;<strong>" + ISIN + "</strong>&nbsp;&nbsp;&nbsp;532259</span></a></li>",
    ]
    if duplicate:
        values.append("<li class='quotemenu quotemenuselect' ng-click=\"liclick('532260','APAR INDUSTRIES LTD')\"><a>APAR INDUSTRIES LTD<br /><span>APARINDS-B&nbsp;&nbsp;&nbsp;<strong>" + ISIN + "</strong>&nbsp;&nbsp;&nbsp;532260</span></a></li>")
    return json.dumps("".join(values)).encode()


def _page() -> str:
    return """<table><tr><th>Financial Year</th><th>Quarter</th><th>Type</th><th>Status</th><th>Filing Date Time</th><th>Revised Date Time</th><th>Revision_Reason</th><th>Standalone XBRL</th><th>Consolidate XBRL</th></tr>
    <tr><td>2026-2027</td><td>Standalone-Jun-26</td><td>Quarter</td><td>New</td><td>01-08-2026 10:00:00</td><td>--</td><td>--</td><td><a href=\"/XBRLFILES/apar-jun-2026.xml\">x</a></td><td></td></tr></table>"""


def _archive(*, include_history: bool = True) -> bytes:
    current = "2026-2027,\"Standalone-Jun-26;JQ2026-2027;130.00;D\",Quarter,New,\"7/24/2026 6:31:40 PM\",-,-,/XBRLFILES/apar-jun-2026.xml,-\n"
    history = (
        "2025-2026,\"Standalone-Mar-26;JQ2025-2026;130.00;D\",Quarter,New,\"5/28/2026 6:31:40 PM\",-,-,/XBRLFILES/apar-mar-2026.xml,-\n"
        "2025-2026,\"Standalone-Mar-26;JY2025-2026;130.00;D\",Year,New,\"5/28/2026 6:31:40 PM\",-,-,/XBRLFILES/apar-mar-2026.xml,-\n"
    ) if include_history else ""
    return ("Financial Year,Quarter,Type,Status,Filing Date Time,Revised Date Time,Revision_Reason,Standalone XBRL,Consolidate XBRL\n" + current + history).encode()


def _xbrl(*, isin: str = ISIN, code: str = CODE, pat: str = "10") -> bytes:
    return f"""<?xml version=\"1.0\"?><xbrli:xbrl xmlns:xbrli=\"http://www.xbrl.org/2003/instance\" xmlns:in-capmkt=\"http://www.sebi.gov.in/xbrl\">
    <xbrli:context id=\"quarter\"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>{code}</in-capmkt:ScripCode><in-capmkt:ISIN>{isin}</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>APAR Industries</in-capmkt:NameOfTheCompany><in-capmkt:DateOfStartOfReportingPeriod>2026-04-01</in-capmkt:DateOfStartOfReportingPeriod><in-capmkt:DateOfEndOfReportingPeriod>2026-06-30</in-capmkt:DateOfEndOfReportingPeriod><in-capmkt:TypeOfReportingPeriod>Quarterly</in-capmkt:TypeOfReportingPeriod>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Lakhs</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>Standalone</in-capmkt:NatureOfReportStandaloneConsolidated><in-capmkt:WhetherResultsAreAuditedOrUnaudited>Unaudited</in-capmkt:WhetherResultsAreAuditedOrUnaudited>
    <in-capmkt:RevenueFromOperations contextRef=\"quarter\">100</in-capmkt:RevenueFromOperations><in-capmkt:ProfitLossBeforeTax contextRef=\"quarter\">20</in-capmkt:ProfitLossBeforeTax><in-capmkt:ProfitLoss contextRef=\"quarter\">{pat}</in-capmkt:ProfitLoss><in-capmkt:BasicEarningsPerShare contextRef=\"quarter\">5.5</in-capmkt:BasicEarningsPerShare></xbrli:xbrl>""".encode()


class _Universe:
    def __init__(self, items: tuple[NseEquityInstrument, ...]) -> None:
        self.items, self.captured = items, []

    def instruments_as_of(self, _as_of: datetime):
        return self.items

    def capture_provider_mapping(self, *args, **kwargs):
        self.captured.append((args, kwargs))


def _instrument() -> NseEquityInstrument:
    return NseEquityInstrument(TARGET, "APARINDS", ISIN, None, None, "ACTIVE", None, True, T, "FIXTURE", company_name="APAR Industries")


def _transport(*, lookup: bytes | None = None, xml: bytes | None = None, archive: bytes | None = None) -> BseOfficialHttpTransport:
    values = {
        BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL.format(isin=ISIN): BseOfficialHttpResponse(BSE_OFFICIAL_EXACT_ISIN_LOOKUP_URL.format(isin=ISIN), "application/json", lookup or _lookup(), T),
        PAGE: BseOfficialHttpResponse(PAGE, "text/html", _page().encode(), T),
        ARCHIVE: BseOfficialHttpResponse(ARCHIVE, "text/csv", archive or _archive(), T),
        XBRL: BseOfficialHttpResponse(XBRL, "application/xml", xml or _xbrl(), T),
    }
    return BseOfficialHttpTransport(fetch=lambda url, _maximum: values[url], clock=lambda: T)


def _collector(tmp_path, *, transport: BseOfficialHttpTransport | None = None, archive: bool = False, clock=lambda: T):
    transport = transport or _transport()
    universe = _Universe((_instrument(),))
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    return BseOfficialFinancialCollector(
        universe=universe, filings=filings, facts=facts,
        security_master=BseOfficialSecurityMaster(transport),
        provider=(BSEOfficialFinancialResultsArchiveProvider(fetch_csv=transport.fetch_results_archive)
                  if archive else BSEOfficialFinancialResultsProvider(fetch_text=transport.fetch_text, clock=clock)),
        transport=transport, staging=BseOfficialXbrlStaging(tmp_path / "staging"), clock=clock,
    ), universe, filings, facts


class _StreamHeaders(dict):
    def get_content_type(self):
        return self.get("Content-Type", "application/xml").split(";", 1)[0]


class _StreamResponse:
    def __init__(self, url: str, body: bytes, *, content_type: str = "application/xml", status: int = 200) -> None:
        self.url, self._body, self.status = url, body, status
        self.headers, self.offset, self.read_sizes = _StreamHeaders({"Content-Type": content_type}), 0, []

    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def geturl(self): return self.url
    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        value = self._body[self.offset:self.offset + size]
        self.offset += len(value)
        return value


def _streaming_target():
    mapping = BseOfficialSecurityMaster(_transport()).resolve(canonical_instrument_id=TARGET, isin=ISIN)
    metadata = BSEOfficialFinancialResultsProvider(fetch_text=lambda _url: _page(), clock=lambda: T).result_metadata(CODE)[0]
    return mapping, metadata


def test_official_exact_isin_lookup_mapping_is_exact_and_ambiguous_is_closed(tmp_path):
    resolver = BseOfficialSecurityMaster(_transport())
    exact = resolver.resolve(canonical_instrument_id=TARGET, isin=ISIN)
    assert exact.status is BseMappingStatus.EXACT and exact.security_code == CODE
    assert exact.security_id == "APARINDS" and exact.security_name == "APAR INDUSTRIES LTD"
    assert exact.source_type == "BSE_EXACT_ISIN_LOOKUP" and exact.source_master_date is None
    assert exact.fingerprint == resolver.resolve(canonical_instrument_id=TARGET, isin=ISIN).fingerprint
    ambiguous = BseOfficialSecurityMaster(_transport(lookup=_lookup(duplicate=True))).resolve(canonical_instrument_id=TARGET, isin=ISIN)
    assert ambiguous.status is BseMappingStatus.AMBIGUOUS and ambiguous.security_code is None


def test_unavailable_master_and_invalid_or_html_lookup_responses_fail_closed():
    unavailable = BseOfficialHttpTransport(fetch=lambda _url, _maximum: BseOfficialHttpResponse(BSE_OFFICIAL_SCRIP_MASTER_URL, "text/html", b"<html>404</html>", T))
    with pytest.raises(BseCollectorError, match="CONTENT_TYPE_REJECTED"):
        unavailable.fetch_master()
    malformed = BseOfficialHttpTransport(fetch=lambda url, _maximum: BseOfficialHttpResponse(url, "application/json", b"<html>not json</html>", T))
    with pytest.raises(BseCollectorError, match="RESPONSE_INVALID"):
        BseOfficialSecurityMaster(malformed).resolve(canonical_instrument_id=TARGET, isin=ISIN)


def test_results_archive_provider_preserves_quarter_year_aliases_with_one_preferred_legacy_view():
    transport = _transport()
    provider = BSEOfficialFinancialResultsArchiveProvider(fetch_csv=transport.fetch_results_archive)
    aliases = provider.result_metadata_aliases(CODE)
    result = provider.result_metadata(CODE)
    assert [item.period_type.value for item in result] == ["ANNUAL", "QUARTERLY"]
    assert result[-1].scope.value == "STANDALONE"
    assert result[-1].filing_at.isoformat() == "2026-07-24T13:01:40+00:00"
    assert result[-1].xbrl_url == XBRL
    assert result[-1].source_page == ARCHIVE
    assert result[-1].raw_filing_timestamp == "7/24/2026 6:31:40 PM"
    assert result[-1].raw_filing_timestamp_field_path == "BSE_RESULT_ARCHIVE.CSV.filing_date_time"
    shared = next(item for item in aliases if item.document_url.endswith("apar-mar-2026.xml"))
    assert [item.period_type.value for item in shared.aliases] == ["ANNUAL", "QUARTERLY"]
    assert shared.preferred.period_type.value == "ANNUAL"


def test_historical_annual_selection_keeps_five_periods_per_scope_and_all_selected_vintages() -> None:
    provider = BSEOfficialFinancialResultsArchiveProvider(fetch_csv=lambda _url: _archive().decode())
    base = next(value for value in provider.result_metadata(CODE) if value.period_type is FinancialPeriodType.ANNUAL)
    values = []
    for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE):
        for year in range(2021, 2027):
            values.append(replace(
                base, scope=scope, period_end=datetime(year, 3, 31, tzinfo=UTC),
                filing_at=datetime(year, 5, 1, tzinfo=UTC),
                financial_year=f"{year - 1}-{year}", quarter_label=f"{scope.value}-Mar-{year}",
                xbrl_url=f"https://www.bseindia.com/XBRLFILES/{scope.value.lower()}-{year}.xml",
                period_type=FinancialPeriodType.ANNUAL, value_basis=FinancialValueBasis.FULL_YEAR,
            ))
    revision = replace(
        values[3], filing_at=datetime(2025, 6, 1, tzinfo=UTC), status="Revised",
        revised_at=datetime(2025, 6, 1, tzinfo=UTC),
        xbrl_url="https://www.bseindia.com/XBRLFILES/consolidated-2024-revised.xml",
    )
    future = replace(values[-1], filing_at=datetime(2027, 5, 1, tzinfo=UTC))
    selected = _historical_annual_metadata(tuple(values) + (revision, future), datetime(2026, 9, 3, tzinfo=UTC))
    for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE):
        scoped = [value for value in selected if value.scope is scope]
        assert {value.period_end.year for value in scoped} == {2022, 2023, 2024, 2025, 2026}
    assert revision in selected
    assert future not in selected
    assert selected == tuple(sorted(selected, key=lambda value: (
        value.period_end, value.scope.value, value.filing_at, value.xbrl_url,
    )))
    assert COMPOUNDER_NON_FINANCIAL_BSE_HISTORICAL_TARGETS == (
        "NSE:INE372A01015", "NSE:INE955D01029", "NSE:INE068V01023", "NSE:INE0FHS01024",
    )


def test_results_archive_accepts_only_its_governed_24_hour_month_day_timestamp_format():
    archive = _archive(include_history=False).replace(b"7/24/2026 6:31:40 PM", b"8/13/2026 17:20:23")
    result = BSEOfficialFinancialResultsArchiveProvider(fetch_csv=lambda _url: archive.decode()).result_metadata(CODE)
    assert result[0].filing_at.isoformat() == "2026-08-13T11:50:23+00:00"
    with pytest.raises(BseOfficialError, match="timestamp"):
        BSEOfficialFinancialResultsProvider(
            fetch_text=lambda _url: _page().replace("01-08-2026 10:00:00", "8/13/2026 17:20:23"), clock=lambda: T,
        ).result_metadata(CODE)


def test_archive_snapshot_is_append_only_and_fingerprinted(tmp_path):
    mapping = BseOfficialSecurityMaster(_transport()).resolve(canonical_instrument_id=TARGET, isin=ISIN)
    response = BseOfficialHttpResponse(ARCHIVE, "text/csv", _archive(), T)
    snapshots = BseOfficialArchiveSnapshotStore(tmp_path / "archive-audit")
    first = snapshots.capture(mapping=mapping, response=response)
    second = snapshots.capture(mapping=mapping, response=response)
    assert isinstance(first, BseArchiveSnapshot)
    assert first.snapshot_id == second.snapshot_id and first.path.read_bytes() == response.body
    assert first.raw_sha256.startswith("sha256:") and first.parsed_row_count == 3
    assert "token" not in first.sidecar_path.read_text(encoding="utf-8").lower()


def test_results_archive_rejects_non_csv_and_malformed_schema():
    wrong_content = BseOfficialHttpTransport(fetch=lambda url, _maximum: BseOfficialHttpResponse(url, "text/html", b"<html />", T))
    with pytest.raises(BseCollectorError, match="CONTENT_TYPE_REJECTED"):
        wrong_content.fetch_results_archive(ARCHIVE)
    with pytest.raises(BseOfficialError, match="unrecognised schema"):
        BSEOfficialFinancialResultsArchiveProvider(fetch_csv=lambda _url: "unexpected,columns\n1,2\n").result_metadata(CODE)
    with pytest.raises(BseCollectorError, match="URL_PATH_REJECTED"):
        _transport().fetch_results_archive(BSE_OFFICIAL_RESULTS_ARCHIVE_URL.format(security_code="12345"))


def test_staging_rejects_non_bse_or_wrong_issuer_before_writing(tmp_path):
    transport = _transport(xml=_xbrl(isin="INE000000001"))
    collector, _universe, _filings, _facts = _collector(tmp_path, transport=transport)
    receipt = collector.run().receipts[0]
    assert receipt.mapping.status is BseMappingStatus.EXACT
    assert receipt.import_attempts == 0 and receipt.blockers == ("XBRL_IDENTITY_MISMATCH",)
    assert receipt.filing_dispositions[0].disposition is BseFilingDisposition.XBRL_IDENTITY_MISMATCH
    assert not tuple((tmp_path / "staging").glob("*.xml"))
    with pytest.raises(BseCollectorError, match="HOST_REJECTED"):
        transport.fetch_xbrl("https://example.invalid/XBRLFILES/not-bse.xml")


def test_lookalike_o_isin_remains_an_identity_mismatch_without_global_normalization(tmp_path):
    transport = _transport(xml=_xbrl(isin="INEOFHS01024"))
    collector, _universe, _filings, _facts = _collector(tmp_path, transport=transport)
    receipt = collector.run().receipts[0]
    assert receipt.blockers == ("XBRL_IDENTITY_MISMATCH",)
    assert receipt.filing_dispositions[0].disposition is BseFilingDisposition.XBRL_IDENTITY_MISMATCH


def test_five_mebibyte_xbrl_limit_is_enforced_and_has_a_typed_receipt_disposition(tmp_path):
    oversized = _xbrl() + b" " * (5 * 1024 * 1024)
    transport = _transport(xml=oversized)
    collector, _universe, _filings, _facts = _collector(tmp_path, transport=transport)
    receipt = collector.run().receipts[0]
    assert receipt.import_attempts == 0 and receipt.blockers == ("XBRL_DOCUMENT_TOO_LARGE",)
    assert receipt.filing_dispositions[0].disposition is BseFilingDisposition.XBRL_DOCUMENT_TOO_LARGE


def test_all_five_immutable_archives_are_deterministic_and_make_no_network_calls():
    root = Path(__file__).resolve().parents[2] / "data" / "official_sources" / "bse_financial_results" / "archive_audit"
    codes = ("532259", "543288", "530343", "543245", "532174")
    for code in codes:
        snapshot = next(root.glob(f"bse-archive-{code}-*.csv"))
        raw = snapshot.read_text(encoding="utf-8-sig")
        calls: list[str] = []
        provider = BSEOfficialFinancialResultsArchiveProvider(
            fetch_csv=lambda url, raw=raw: calls.append(url) or raw,
        )
        first = provider.result_metadata(code)[-12:]
        second = provider.result_metadata(code)[-12:]
        assert first == second and len(first) == 12
        assert calls == [BSE_RESULT_ARCHIVE.format(security_code=code)] * 2


def test_bse_streaming_quarantines_then_promotes_large_valid_xbrl_idempotently(tmp_path):
    mapping, metadata = _streaming_target()
    body = _xbrl() + b" " * (5 * 1024 * 1024)
    responses = []
    def open_stream(url):
        response = _StreamResponse(url, body); responses.append(response); return response
    staging = BseOfficialXbrlStaging(tmp_path / "staging")
    acquirer = BseOfficialBoundedXbrlAcquirer(quarantine_root=staging.quarantine_root, open_stream=open_stream, clock=lambda: T)
    first = acquirer.acquire(mapping=mapping, metadata=metadata)
    assert first.byte_length == len(body) and first.sha256 == sha256(body).hexdigest()
    assert first.path.parent == staging.quarantine_root and not tuple((tmp_path / "staging").glob("bse-*.xml"))
    staged = staging.promote_quarantine(mapping=mapping, metadata=metadata, value=first)
    assert staged.disposition.value == "NEW" and staged.path.exists() and not first.path.exists()
    second = acquirer.acquire(mapping=mapping, metadata=metadata)
    rerun = staging.promote_quarantine(mapping=mapping, metadata=metadata, value=second)
    assert rerun.disposition.value == "EXISTING_UNCHANGED" and rerun.path == staged.path
    assert all(size == 64 * 1024 for response in responses for size in response.read_sizes)


def test_bse_streaming_enforces_its_hard_cap_and_cleans_incomplete_quarantine(tmp_path):
    mapping, metadata = _streaming_target()
    body = _xbrl() + b" " * (5 * 1024 * 1024)
    acquirer = BseOfficialBoundedXbrlAcquirer(
        quarantine_root=tmp_path / "quarantine",
        policy=BseXbrlStreamingPolicy(5 * 1024 * 1024, 7 * 1024 * 1024, 64 * 1024),
        open_stream=lambda url: _StreamResponse(url, body), clock=lambda: T,
    )
    with pytest.raises(BseCollectorError, match="RESPONSE_TOO_LARGE"):
        acquirer.acquire(mapping=mapping, metadata=metadata)
    assert not tuple((tmp_path / "quarantine").glob("*.part"))


def test_bse_streaming_rejects_external_or_arbitrary_urls_html_identity_and_scope(tmp_path):
    mapping, metadata = _streaming_target()
    acquirer = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "quarantine", open_stream=lambda url: _StreamResponse(url, _xbrl()), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="URL_PATH_REJECTED"):
        acquirer.acquire(mapping=mapping, metadata=replace(metadata, xbrl_url="https://www.bseindia.com/not-xbrl.xml"))
    with pytest.raises(BseCollectorError, match="HOST_REJECTED"):
        acquirer.acquire(mapping=mapping, metadata=replace(metadata, xbrl_url="https://example.invalid/XBRLFILES/x.xml"))
    external = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "external", open_stream=lambda _url: _StreamResponse("https://example.invalid/XBRLFILES/x.xml", _xbrl()), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="HOST_REJECTED"):
        external.acquire(mapping=mapping, metadata=metadata)
    html = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "html", open_stream=lambda url: _StreamResponse(url, b"<html>error</html>", content_type="text/html"), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="CONTENT_TYPE_REJECTED"):
        html.acquire(mapping=mapping, metadata=metadata)
    disguised_html = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "disguised-html", open_stream=lambda url: _StreamResponse(url, b"<html>error</html>"), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="XBRL_SIGNATURE_INVALID"):
        disguised_html.acquire(mapping=mapping, metadata=metadata)
    wrong_identity = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "identity", open_stream=lambda url: _StreamResponse(url, _xbrl(isin="INEOFHS01024")), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="IDENTITY_MISMATCH"):
        wrong_identity.acquire(mapping=mapping, metadata=metadata)
    wrong_scope = BseOfficialBoundedXbrlAcquirer(quarantine_root=tmp_path / "scope", open_stream=lambda url: _StreamResponse(url, _xbrl()), clock=lambda: T)
    with pytest.raises(BseCollectorError, match="SCOPE_MISMATCH"):
        wrong_scope.acquire(mapping=mapping, metadata=replace(metadata, scope=StatementScope.CONSOLIDATED))


def test_fixed_icici_recovery_accepts_only_approved_targets_and_never_imports(tmp_path):
    mapping, metadata = _streaming_target()
    staging = BseOfficialXbrlStaging(tmp_path / "staging")
    recovery = BseOfficialIciciBoundedXbrlRecovery(
        BseOfficialBoundedXbrlAcquirer(quarantine_root=staging.quarantine_root, open_stream=lambda url: _StreamResponse(url, _xbrl()), clock=lambda: T), staging,
    )
    with pytest.raises(BseCollectorError, match="RECOVERY_TARGET_REJECTED"):
        recovery.audit(mapping=mapping, metadata=metadata)
    assert not hasattr(recovery, "trade") and BseBoundedXbrlRecoveryReceipt.__name__


def test_only_official_staged_ingestion_uses_the_finite_eight_mebibyte_gate(tmp_path):
    _mapping, metadata = _streaming_target()
    path = tmp_path / "validated-bse.xml"
    path.write_bytes(_xbrl() + b" " * (5 * 1024 * 1024))
    service = BSEOfficialLocalXbrlIngestionService(
        SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite"), SQLiteFinancialFactStore(tmp_path / "facts.sqlite"), clock=lambda: T,
    )
    with pytest.raises(BseOfficialError, match="bounded adapter limit"):
        service.inspect(path)
    report = service.ingest_official_staged(
        InstrumentIdentity(TARGET, Exchange.NSE, "APARINDS", "APARINDS", ISIN, None, InstrumentType.NSE_EQUITY, "APAR Industries"),
        CODE, path, metadata=metadata,
    )
    assert report.facts_inserted == 4


def test_staging_retains_hash_versions_and_never_records_credentials(tmp_path):
    transport = _transport()
    mapping = BseOfficialSecurityMaster(transport).resolve(canonical_instrument_id=TARGET, isin=ISIN)
    metadata = BSEOfficialFinancialResultsProvider(fetch_text=transport.fetch_text, clock=lambda: T).result_metadata(CODE)[0]
    staging = BseOfficialXbrlStaging(tmp_path / "staging")
    first = staging.stage(mapping=mapping, metadata=metadata, response=transport.fetch_xbrl(XBRL))
    unchanged = staging.stage(mapping=mapping, metadata=metadata, response=transport.fetch_xbrl(XBRL))
    changed = staging.stage(
        mapping=mapping, metadata=metadata,
        response=BseOfficialHttpResponse(XBRL, "application/xml", _xbrl(pat="11"), T),
    )
    assert first.disposition is BseStageDisposition.NEW
    assert unchanged.disposition is BseStageDisposition.EXISTING_UNCHANGED
    assert changed.disposition is BseStageDisposition.NEW_VERSION and changed.path != first.path
    assert "token" not in changed.sidecar_path.read_text(encoding="utf-8").lower()


def test_staging_preserves_quarter_year_aliases_for_one_immutable_document(tmp_path):
    transport = _transport()
    mapping = BseOfficialSecurityMaster(transport).resolve(canonical_instrument_id=TARGET, isin=ISIN)
    provider = BSEOfficialFinancialResultsArchiveProvider(fetch_csv=transport.fetch_results_archive)
    group = next(item for item in provider.result_metadata_aliases(CODE) if item.document_url.endswith("apar-mar-2026.xml"))
    staging = BseOfficialXbrlStaging(tmp_path / "staging")
    staged = staging.stage(
        mapping=mapping, metadata=group.preferred,
        response=BseOfficialHttpResponse(group.document_url, "application/xml", _xbrl(), T),
    )
    manifest = staging.preserve_archive_aliases(staged=staged, mapping=mapping, aliases=group)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["content_sha256"] == staged.sha256
    assert [item["period_type"] for item in payload["aliases"]] == ["ANNUAL", "QUARTERLY"]
    assert staging.preserve_archive_aliases(staged=staged, mapping=mapping, aliases=group) == manifest


def test_collector_is_idempotent_and_pit_receipt_is_not_backdated(tmp_path):
    collector, universe, filings, facts = _collector(tmp_path)
    first = collector.run()
    target = first.receipts[0]
    assert target.new_filings == 1 and target.canonical_facts_accepted == 4 and not target.blockers
    assert len(universe.captured) == 1
    before_received = T - timedelta(microseconds=1)
    assert not facts.series(TARGET, FinancialMetric.PAT, as_of=before_received, limit=10)
    stored = facts.series(TARGET, FinancialMetric.PAT, as_of=T, limit=10)
    assert [item.value for item in stored] == [__import__("decimal").Decimal("10")]
    filing = filings.list(limit=1)[0]
    assert filing.announced_at < filing.received_at == T
    second = collector.run()
    assert second.receipts[0].unchanged_filings == 1
    assert second.receipts[0].canonical_facts_accepted == 0
    assert second.receipts[0].canonical_facts_unchanged == 4
    assert len(facts.series(TARGET, FinancialMetric.PAT, limit=10)) == 1
    assert {item.canonical_instrument_id for item in first.receipts} == set(REAL_PORTFOLIO_BSE_FINANCIAL_TARGETS)


def test_collector_can_discover_and_import_from_the_structured_results_archive(tmp_path):
    collector, _universe, filings, facts = _collector(tmp_path, transport=_transport(archive=_archive(include_history=False)), archive=True)
    first = collector.run()
    receipt = first.receipts[0]
    assert receipt.filings_discovered == 1
    assert receipt.new_filings == 1 and receipt.canonical_facts_accepted == 4
    second = collector.run()
    assert second.receipts[0].unchanged_filings == 1
    assert len(filings.list(limit=10)) == 1
    assert len(facts.series(TARGET, FinancialMetric.PAT, limit=10)) == 1


def test_structured_archive_rerun_uses_immutable_filing_receipt_timestamp(tmp_path):
    transport = _transport(archive=_archive(include_history=False))
    first, _universe, _filings, _facts = _collector(tmp_path, transport=transport, archive=True)
    assert first.run().receipts[0].new_filings == 1
    second, _universe, _filings, _facts = _collector(
        tmp_path, transport=transport, archive=True, clock=lambda: T + timedelta(minutes=1),
    )
    receipt = second.run().receipts[0]
    assert receipt.unchanged_filings == 1
    assert receipt.canonical_facts_unchanged == 4
    assert not receipt.blockers


def test_worker_is_off_without_explicit_configuration(monkeypatch, tmp_path):
    settings = BseOfficialFinancialCollectorSettings.from_environment()
    assert not settings.enabled
    collector, _universe, _filings, _facts = _collector(tmp_path)
    assert not BseOfficialFinancialCollectorWorker(collector, settings).start()
    monkeypatch.setenv("BSE_OFFICIAL_FINANCIAL_COLLECTOR_ENABLED", "true")
    monkeypatch.setenv("BSE_OFFICIAL_FINANCIAL_COLLECTOR_INTERVAL_SECONDS", "30")
    enabled = BseOfficialFinancialCollectorSettings.from_environment()
    assert enabled.enabled and enabled.interval == timedelta(seconds=30)
