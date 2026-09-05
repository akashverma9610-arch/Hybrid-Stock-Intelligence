from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.bse_official import (
    BSE_OFFICIAL_PROVIDER, BSE_RESULT_PAGE, BSEOfficialFinancialResultsIngestionService,
    BSEOfficialFinancialResultsProvider, BSEOfficialLocalXbrlIngestionService,
    BseOfficialError, BsePublicationAvailability, BseResultMetadata, BseTimestampStatus, parse_bse_xbrl,
)
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis, NumericScale, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T = datetime(2026, 8, 25, 12, tzinfo=UTC)
CODE = "508869"
ISIN = "INE437A01024"
PAGE = BSE_RESULT_PAGE.format(security_code=CODE)


def _instrument(isin: str = ISIN) -> InstrumentIdentity:
    return InstrumentIdentity("NSE:" + isin, Exchange.NSE, "APOLLOHOSP", "APOLLOHOSP", isin, "EQ", InstrumentType.NSE_EQUITY, "Apollo Hospitals")


def _page() -> str:
    return """<table><tr><th>Financial Year</th><th>Quarter</th><th>Type</th><th>Status</th><th>Filing Date Time</th><th>Revised Date Time</th><th>Revision_Reason</th><th>Standalone XBRL</th><th>Consolidate XBRL</th></tr>
    <tr><td>2026-2027</td><td>Standalone-Jun-26</td><td>Quarter</td><td>New</td><td>01-08-2026 10:00:00</td><td>--</td><td>--</td><td><a href=\"/XBRLFILES/original.xml\">x</a></td><td></td></tr>
    <tr><td>2026-2027</td><td>Standalone-Jun-26</td><td>Quarter</td><td>Revised</td><td>--</td><td>05-08-2026 10:00:00</td><td>Board correction</td><td><a href=\"/XBRLFILES/revised.xml\">x</a></td><td></td></tr>
    <tr><td>2026-2027</td><td>Consolidated-Jun-26</td><td>Quarter</td><td>New</td><td>02-08-2026 10:00:00</td><td>--</td><td>--</td><td></td><td><a href=\"/XBRLFILES/consolidated.xml\">x</a></td></tr></table>"""


def _bse_application_shell() -> str:
    """Representative current BSE HTML shell, deliberately without result rows."""
    return """<!DOCTYPE html><html lang=\"en\"><head><title>BSE</title></head>
    <body><app-root></app-root><script src=\"main.js\"></script></body></html>"""


def _xbrl(*, pat: str, scope: str, isin: str = ISIN, code: str = CODE) -> str:
    return f"""<?xml version=\"1.0\"?><xbrli:xbrl xmlns:xbrli=\"http://www.xbrl.org/2003/instance\" xmlns:in-capmkt=\"http://www.sebi.gov.in/xbrl\">
    <!--IFIndAs V2.1--><xbrli:context id=\"quarter\"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id=\"previous\"><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2025-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>{code}</in-capmkt:ScripCode><in-capmkt:ISIN>{isin}</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>Apollo Hospitals</in-capmkt:NameOfTheCompany><in-capmkt:DateOfStartOfReportingPeriod>2026-04-01</in-capmkt:DateOfStartOfReportingPeriod><in-capmkt:DateOfEndOfReportingPeriod>2026-06-30</in-capmkt:DateOfEndOfReportingPeriod><in-capmkt:TypeOfReportingPeriod>Quarterly</in-capmkt:TypeOfReportingPeriod>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Lakhs</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>{scope}</in-capmkt:NatureOfReportStandaloneConsolidated><in-capmkt:WhetherResultsAreAuditedOrUnaudited>Unaudited</in-capmkt:WhetherResultsAreAuditedOrUnaudited>
    <in-capmkt:RevenueFromOperations contextRef=\"previous\">90</in-capmkt:RevenueFromOperations><in-capmkt:RevenueFromOperations contextRef=\"quarter\">100</in-capmkt:RevenueFromOperations><in-capmkt:ProfitLossBeforeTax contextRef=\"quarter\">20</in-capmkt:ProfitLossBeforeTax><in-capmkt:ProfitLoss contextRef=\"quarter\">{pat}</in-capmkt:ProfitLoss><in-capmkt:BasicEarningsPerShare contextRef=\"quarter\">5.5</in-capmkt:BasicEarningsPerShare><in-capmkt:FinanceCosts contextRef=\"quarter\">3</in-capmkt:FinanceCosts><in-capmkt:DepreciationAndAmortisationExpense contextRef=\"quarter\">2</in-capmkt:DepreciationAndAmortisationExpense><in-capmkt:Assets contextRef=\"quarter\">1000</in-capmkt:Assets><in-capmkt:Liabilities contextRef=\"quarter\">400</in-capmkt:Liabilities></xbrli:xbrl>"""


def _mixed_march_xbrl() -> str:
    return f'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
    <xbrli:context id="quarter"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="year"><xbrli:period><xbrli:startDate>2025-04-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period></xbrli:context>
    <xbrli:context id="instant"><xbrli:period><xbrli:instant>2026-03-31</xbrli:instant></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>{CODE}</in-capmkt:ScripCode><in-capmkt:ISIN>{ISIN}</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>Apollo Hospitals</in-capmkt:NameOfTheCompany>
    <in-capmkt:DateOfStartOfReportingPeriod>2026-01-01</in-capmkt:DateOfStartOfReportingPeriod><in-capmkt:DateOfEndOfReportingPeriod>2026-03-31</in-capmkt:DateOfEndOfReportingPeriod><in-capmkt:TypeOfReportingPeriod>Quarterly</in-capmkt:TypeOfReportingPeriod>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Lakhs</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>Standalone</in-capmkt:NatureOfReportStandaloneConsolidated>
    <in-capmkt:RevenueFromOperations contextRef="quarter">100</in-capmkt:RevenueFromOperations><in-capmkt:RevenueFromOperations contextRef="year">400</in-capmkt:RevenueFromOperations><in-capmkt:ProfitLoss contextRef="quarter">10</in-capmkt:ProfitLoss><in-capmkt:ProfitLoss contextRef="year">40</in-capmkt:ProfitLoss><in-capmkt:Assets contextRef="instant">1000</in-capmkt:Assets></xbrli:xbrl>'''


class _MappingStore:
    def __init__(self) -> None: self.values = []
    def capture_provider_mapping(self, *args, **kwargs): self.values.append((args, kwargs))


def _service(tmp_path, *, isin: str = ISIN):
    source = {
        PAGE: _page(),
        "https://www.bseindia.com/XBRLFILES/original.xml": _xbrl(pat="10", scope="Standalone"),
        "https://www.bseindia.com/XBRLFILES/revised.xml": _xbrl(pat="12", scope="Standalone"),
        "https://www.bseindia.com/XBRLFILES/consolidated.xml": _xbrl(pat="20", scope="Consolidated"),
    }
    provider = BSEOfficialFinancialResultsProvider(fetch_text=lambda url: source[url], clock=lambda: T)
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    mappings = _MappingStore()
    return BSEOfficialFinancialResultsIngestionService(provider, filings, facts, mapping_store=mappings, clock=lambda: T), filings, facts, mappings, _instrument(isin)


def test_bse_xbrl_exact_isin_mapping_metric_scope_scale_revision_and_pit(tmp_path):
    service, filings, facts, mappings, instrument = _service(tmp_path)
    report = service.ingest(instrument, CODE)
    assert report.rejected == 0 and report.filings_inserted == 3 and report.facts_inserted == 24
    assert report.revisions == 1 and len(mappings.values) == 1
    mapped = mappings.values[0][1]
    assert mapped["provider"] == BSE_OFFICIAL_PROVIDER and mapped["resolved_instrument"].provider_mappings[-1].provider_instrument_reference == CODE
    standalone = facts.series(instrument.instrument_id, FinancialMetric.PAT, scope=StatementScope.STANDALONE, limit=10)
    assert [item.value for item in standalone] == [__import__("decimal").Decimal("10"), __import__("decimal").Decimal("12")]
    assert standalone[-1].revision_of_fact_id == standalone[0].fact_id
    assert not facts.series(instrument.instrument_id, FinancialMetric.EBITDA, limit=10)
    assert not facts.series(instrument.instrument_id, FinancialMetric.CFO, limit=10)
    assert facts.series(instrument.instrument_id, FinancialMetric.TOTAL_LIABILITIES, scope=StatementScope.CONSOLIDATED, limit=10)[0].value == __import__("decimal").Decimal("400")
    retained = tuple(item.timestamp_evidence for item in filings.list(limit=10))
    assert all(item is not None for item in retained)
    assert {item.raw_timestamp_field_path for item in retained if item} == {"BSE_RESULT_PAGE.HTML.filing_date_time", "BSE_RESULT_PAGE.HTML.revised_date_time"}
    before = datetime(2026, 8, 1, 4, 29, 59, tzinfo=UTC)
    after_original = datetime(2026, 8, 1, 4, 30, 1, tzinfo=UTC)
    after_revision = datetime(2026, 8, 5, 4, 30, 1, tzinfo=UTC)
    assert not facts.series(instrument.instrument_id, FinancialMetric.PAT, scope=StatementScope.STANDALONE, as_of=before, limit=10)
    assert [x.value for x in facts.series(instrument.instrument_id, FinancialMetric.PAT, scope=StatementScope.STANDALONE, as_of=after_original, limit=10)] == [__import__("decimal").Decimal("10")]
    assert [x.value for x in facts.series(instrument.instrument_id, FinancialMetric.PAT, scope=StatementScope.STANDALONE, as_of=after_revision, limit=10)] == [__import__("decimal").Decimal("10"), __import__("decimal").Decimal("12")]
    latest = FundamentalsEngineAdapter(facts, filings).build(instrument.instrument_id, as_of=T)
    assert latest.statement_scope is StatementScope.CONSOLIDATED
    assert latest.snapshot.observations[-1].payload["pat"] == 20.0


def test_bse_xbrl_rejects_identity_mismatch_unknown_timezone_and_unknown_scale(tmp_path):
    service, _filings, _facts, _mappings, instrument = _service(tmp_path, isin="INE000000001")
    report = service.ingest(instrument, CODE)
    assert report.filings_inserted == report.facts_inserted == 0 and report.rejected == 3
    with pytest.raises(BseOfficialError, match="timezone"):
        BSEOfficialFinancialResultsProvider(timestamp_status=BseTimestampStatus.UNKNOWN, fetch_text=lambda _: _page()).result_metadata(CODE)
    malformed_scale = _xbrl(pat="10", scope="Standalone").replace("Lakhs", "Mystery")
    with pytest.raises(BseOfficialError, match="currency or scale"):
        parse_bse_xbrl(malformed_scale, "https://www.bseindia.com/XBRLFILES/bad.xml", period_end=datetime(2026, 6, 30, tzinfo=UTC))


def test_bse_results_application_shell_fails_closed_without_xbrl_discovery():
    provider = BSEOfficialFinancialResultsProvider(fetch_text=lambda _: _bse_application_shell(), clock=lambda: T)
    with pytest.raises(BseOfficialError, match="BSE_PUBLIC_RESULTS_INTERFACE_UNAVAILABLE"):
        provider.result_metadata(CODE)


def test_bse_adapter_uses_only_structured_xbrl_and_brain_build_has_no_provider_calls(tmp_path):
    calls = []
    xml = _xbrl(pat="10", scope="Standalone")
    document = parse_bse_xbrl(xml, "https://www.bseindia.com/XBRLFILES/value.xml", period_end=datetime(2026, 6, 30, tzinfo=UTC))
    assert document.facts and "RevenueFromOperations" in document.raw_concepts
    assert all(metric not in {FinancialMetric.EBITDA, FinancialMetric.CFO} for metric, _ in document.facts)
    service, filings, facts, _mappings, instrument = _service(tmp_path)
    service.ingest(instrument, CODE)
    before = tuple(calls)
    FundamentalsEngineAdapter(facts, filings).build(instrument.instrument_id, as_of=T)
    assert calls == list(before)


def test_local_bse_xbrl_uses_system_first_observed_for_pit_not_a_fabricated_publication_time(tmp_path):
    local = tmp_path / "official.xml"; local.write_text(_xbrl(pat="10", scope="Consolidated"), encoding="utf-8")
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    observed = datetime(2026, 8, 25, 12, tzinfo=UTC)
    service = BSEOfficialLocalXbrlIngestionService(filings, facts, clock=lambda: observed)
    result = service.ingest(_instrument(), CODE, local)
    assert result.filing_outcome.value == "INSERTED" and result.facts_inserted == 8
    assert result.publication_availability is BsePublicationAvailability.SYSTEM_FIRST_OBSERVED
    stored = filings.get(next(iter(filings.list(limit=10))).filing_id)
    assert stored.provenance.exchange_timestamp is None and "SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN" in stored.warnings
    assert not facts.series(_instrument().instrument_id, FinancialMetric.PAT, as_of=observed - timedelta(microseconds=1), limit=10)
    stored_pat = facts.series(_instrument().instrument_id, FinancialMetric.PAT, as_of=observed, limit=10)[0]
    assert stored_pat.value == __import__("decimal").Decimal("10")
    assert stored_pat.scale is NumericScale.UNITS
    assert "SOURCE_LEVEL_OF_ROUNDING_LAKHS" in stored_pat.provenance and "RAW_XBRL_UNIT_VALUE" in stored_pat.provenance
    repeated = service.ingest(_instrument(), CODE, local)
    assert repeated.filing_outcome.value == "IDENTICAL" and repeated.facts_inserted == 0 and repeated.facts_duplicate == 8


def test_staged_march_xbrl_uses_actual_contexts_not_the_year_archive_alias(tmp_path):
    path = tmp_path / "mixed-march.xml"
    path.write_text(_mixed_march_xbrl(), encoding="utf-8")
    metadata = BseResultMetadata(
        CODE, "2025-2026", "Standalone-Mar-26", "Year", "New", T, None, None,
        StatementScope.STANDALONE, datetime(2026, 3, 31, tzinfo=UTC),
        FinancialPeriodType.ANNUAL, FinancialValueBasis.FULL_YEAR,
        "https://www.bseindia.com/XBRLFILES/mixed-march.xml", PAGE, BseTimestampStatus.DOCUMENTED,
    )
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    service = BSEOfficialLocalXbrlIngestionService(filings, facts, clock=lambda: T)
    first = service.ingest_official_staged(_instrument(), CODE, path, metadata=metadata)
    assert first.facts_inserted == 5 and first.facts_conflicted == 0
    revenue = facts.series(_instrument().instrument_id, FinancialMetric.REVENUE, scope=StatementScope.STANDALONE, limit=10)
    assert {(item.period_type, item.value_basis, item.period_start.date(), item.value) for item in revenue} == {
        (FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, datetime(2026, 1, 1, tzinfo=UTC).date(), __import__("decimal").Decimal("100")),
        (FinancialPeriodType.ANNUAL, FinancialValueBasis.FULL_YEAR, datetime(2025, 4, 1, tzinfo=UTC).date(), __import__("decimal").Decimal("400")),
    }
    assets = facts.series(_instrument().instrument_id, FinancialMetric.TOTAL_ASSETS, scope=StatementScope.STANDALONE, limit=10)
    assert assets[0].period_type is FinancialPeriodType.POINT_IN_TIME and assets[0].period_start is None
    assert not facts.series(_instrument().instrument_id, FinancialMetric.REVENUE, as_of=T - timedelta(microseconds=1), limit=10)
    second = service.ingest_official_staged(_instrument(), CODE, path, metadata=metadata)
    assert second.filing_outcome.value == "IDENTICAL" and second.facts_inserted == 0 and second.facts_duplicate == 5
