from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from app.fundamentals.bse_official import BSEOfficialLocalXbrlIngestionService
from app.fundamentals.store import FinancialFactWriteOutcome, SQLiteFinancialFactStore
from app.filings.store import SQLiteCorporateFilingsStore
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.real_brain.fundamental_probe import FundamentalBrainProbeService, FundamentalBrainProbeStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore, build_universe_snapshot


BEFORE = datetime(2026, 8, 24, 20, 38, 50, tzinfo=UTC)
OBSERVED = datetime(2026, 8, 25, 14, 48, 27, tzinfo=UTC)
AFTER = datetime(2026, 8, 25, 14, 48, 28, tzinfo=UTC)
_COHORT = (
    ("NSE:INE437A01024", "APOLLOHOSP", "INE437A01024", "508869"),
    ("NSE:INE429E01023", "SAFARI", "INE429E01023", "523025"),
    ("NSE:INE0PPK01015", "ORIENTTECH", "INE0PPK01015", "544235"),
)


def _xml(*, symbol: str, isin: str, code: str) -> str:
    return f"""<?xml version=\"1.0\"?><xbrli:xbrl xmlns:xbrli=\"http://www.xbrl.org/2003/instance\" xmlns:in-capmkt=\"http://www.sebi.gov.in/xbrl\">
    <xbrli:context id=\"quarter\"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>{code}</in-capmkt:ScripCode><in-capmkt:ISIN>{isin}</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>{symbol}</in-capmkt:NameOfTheCompany>
    <in-capmkt:DateOfStartOfReportingPeriod>2026-04-01</in-capmkt:DateOfStartOfReportingPeriod><in-capmkt:DateOfEndOfReportingPeriod>2026-06-30</in-capmkt:DateOfEndOfReportingPeriod><in-capmkt:TypeOfReportingPeriod>Quarterly</in-capmkt:TypeOfReportingPeriod>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Lakhs</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated><in-capmkt:WhetherResultsAreAuditedOrUnaudited>Unaudited</in-capmkt:WhetherResultsAreAuditedOrUnaudited>
    <in-capmkt:RevenueFromOperations contextRef=\"quarter\">100</in-capmkt:RevenueFromOperations><in-capmkt:OtherIncome contextRef=\"quarter\">2</in-capmkt:OtherIncome><in-capmkt:ProfitLossBeforeTax contextRef=\"quarter\">20</in-capmkt:ProfitLossBeforeTax><in-capmkt:ProfitLossForPeriod contextRef=\"quarter\">15</in-capmkt:ProfitLossForPeriod><in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations contextRef=\"quarter\">5</in-capmkt:BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations><in-capmkt:FinanceCosts contextRef=\"quarter\">3</in-capmkt:FinanceCosts><in-capmkt:DepreciationAndAmortisationExpense contextRef=\"quarter\">2</in-capmkt:DepreciationAndAmortisationExpense></xbrli:xbrl>"""


def _identity(item) -> InstrumentIdentity:
    instrument_id, symbol, isin, _code = item
    return InstrumentIdentity(instrument_id, Exchange.NSE, symbol, symbol, isin, "EQ", InstrumentType.NSE_EQUITY, symbol)


def test_three_stock_bse_probe_keeps_first_observed_pit_and_reuses_only_canonical_stored_boundaries(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    instruments = tuple(
        NseEquityInstrument(instrument_id, symbol, isin, None, None, "ACTIVE", None, True, BEFORE, "NSE_OFFICIAL_EXPORT")
        for instrument_id, symbol, isin, _code in _COHORT
    )
    for instrument in instruments:
        universe.save_instrument(instrument)
    source_snapshot = build_universe_snapshot(
        snapshot_id="nse-universe:before-bse", as_of=BEFORE, source="NSE_OFFICIAL_EXPORT", instruments=instruments,
    )
    universe.save_universe_snapshot(source_snapshot)
    filings = SQLiteCorporateFilingsStore(tmp_path / "fundamentals.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "fundamentals.sqlite")
    importer = BSEOfficialLocalXbrlIngestionService(filings, facts, clock=lambda: OBSERVED)
    for item in _COHORT:
        path = tmp_path / f"{item[1]}.xml"; path.write_text(_xml(symbol=item[1], isin=item[2], code=item[3]), encoding="utf-8")
        importer.ingest(_identity(item), item[3], path)
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    probe = FundamentalBrainProbeService(
        repository=repository, historical=history, facts=facts, filings=filings, clock=lambda: AFTER,
    ).run(source_snapshot=source_snapshot, as_of=AFTER, cohort_instrument_ids=tuple(item[0] for item in _COHORT))

    assert probe.provider_calls == 0
    assert probe.cohort_instrument_ids == tuple(item[0] for item in _COHORT)
    assert probe.current_universe_snapshot_id != source_snapshot.snapshot_id
    assert probe.universe_checksum == source_snapshot.checksum
    assert len(probe.filing_ids) == 3 and len(probe.fact_ids) == 21
    assert probe.diagnostic_registry_version == "diagnostic-registry-v1"
    assert probe.analysis_engine_version == "canonical-61-runner-v1"
    assert FundamentalBrainProbeStore(repository).get(probe.probe_id) == probe
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.FUNDAMENTAL_BRAIN_PROBE, limit=10)) == 1
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.UNIVERSE_SNAPSHOT, limit=10)) == 2
    for row in probe.results:
        assert row.first_observed_at == OBSERVED
        assert not facts.facts(row.instrument_id, as_of=BEFORE, limit=100)
        assert len(facts.facts(row.instrument_id, as_of=AFTER, limit=100)) == 7
        assert row.before_coverage.filings == "MISSING"
        assert row.after_coverage.filings == "READY"
        assert row.before_coverage.fundamentals == "INSUFFICIENT"
        assert row.after_coverage.fundamentals == "PARTIAL"
        assert row.after_coverage.earnings == "PARTIAL"
        assert row.consolidated_selected_after
        assert {"EBITDA", "CASH_FLOW", "BALANCE_SHEET"}.issubset(row.unsupported_metrics_missing)
        assert row.after_decision_score_status == "UNAVAILABLE"
        assert row.after_confidence_status == "UNAVAILABLE"
        assert row.before_diagnostic_evaluated + row.before_diagnostic_missing == 61
        assert row.after_diagnostic_evaluated + row.after_diagnostic_missing == 61
    original = facts.get(probe.fact_ids[0])
    assert original is not None
    assert facts.save(replace(original, published_at=AFTER, received_at=AFTER)) is FinancialFactWriteOutcome.CONFLICT
    protected = {
        CoreApiSnapshotFamily.PROMOTION_PROPOSAL, CoreApiSnapshotFamily.PROMOTION_ELIGIBILITY,
        CoreApiSnapshotFamily.PROMOTION_REVIEW, CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION,
        CoreApiSnapshotFamily.STRATEGY_ACTIVATION, CoreApiSnapshotFamily.PAPER_TRADE,
    }
    assert all(not repository.list_snapshots(family, limit=1) for family in protected)
    history.close()
