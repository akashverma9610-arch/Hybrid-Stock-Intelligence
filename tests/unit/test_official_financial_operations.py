from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.data_operations.models import (
    EvidenceDataFamily,
    EvidenceRefreshMode,
    EvidenceRefreshRequest,
    EvidenceRefreshStatus,
)
from app.data_operations.official_financials import (
    BseLegacyScaleReconciliation,
    BseLocalFinancialResultsRefreshJob,
    NseReg31ShareholdingRefreshJob,
    _nonrevision_conflict_reason,
)
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.bse_official import BSEOfficialLocalXbrlIngestionService
from app.fundamentals.models import FinancialMetric, NumericScale
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.nse_import.service import ImportRunStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 30, 10, tzinfo=UTC)
ISIN = "INE437A01024"


def _request(family: EvidenceDataFamily = EvidenceDataFamily.FINANCIAL_RESULTS) -> EvidenceRefreshRequest:
    return EvidenceRefreshRequest("run", family, EvidenceRefreshMode.INCREMENTAL, T, T, None, 0)


def _xbrl() -> str:
    return f'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:in-capmkt="http://www.sebi.gov.in/xbrl">
    <!--IFIndAs V2.1--><xbrli:context id="quarter"><xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period></xbrli:context>
    <in-capmkt:ScripCode>508869</in-capmkt:ScripCode><in-capmkt:ISIN>{ISIN}</in-capmkt:ISIN><in-capmkt:NameOfTheCompany>Apollo Hospitals</in-capmkt:NameOfTheCompany><in-capmkt:DateOfStartOfReportingPeriod>2026-04-01</in-capmkt:DateOfStartOfReportingPeriod><in-capmkt:DateOfEndOfReportingPeriod>2026-06-30</in-capmkt:DateOfEndOfReportingPeriod><in-capmkt:TypeOfReportingPeriod>Quarterly</in-capmkt:TypeOfReportingPeriod>
    <in-capmkt:DescriptionOfPresentationCurrency>INR</in-capmkt:DescriptionOfPresentationCurrency><in-capmkt:LevelOfRounding>Lakhs</in-capmkt:LevelOfRounding><in-capmkt:NatureOfReportStandaloneConsolidated>Consolidated</in-capmkt:NatureOfReportStandaloneConsolidated><in-capmkt:WhetherResultsAreAuditedOrUnaudited>Unaudited</in-capmkt:WhetherResultsAreAuditedOrUnaudited>
    <in-capmkt:RevenueFromOperations contextRef="quarter">100</in-capmkt:RevenueFromOperations><in-capmkt:ProfitLossBeforeTax contextRef="quarter">20</in-capmkt:ProfitLossBeforeTax><in-capmkt:ProfitLoss contextRef="quarter">10</in-capmkt:ProfitLoss><in-capmkt:BasicEarningsPerShare contextRef="quarter">5.5</in-capmkt:BasicEarningsPerShare></xbrli:xbrl>'''


def _universe(path: Path) -> tuple[SQLiteCoreApiSnapshotRepository, CoreUniverseAnalysisStore, InstrumentIdentity]:
    repository = SQLiteCoreApiSnapshotRepository(path / "core.sqlite")
    store = CoreUniverseAnalysisStore(repository)
    item = NseEquityInstrument("NSE:APOLLOHOSP", "APOLLOHOSP", ISIN, None, None, "ACTIVE", None, True, T - timedelta(days=1), "fixture", company_name="Apollo Hospitals")
    snapshot = UniverseSnapshot("snapshot", T - timedelta(days=1), "fixture", 1, 1, 0, (), "v1", "hash", (item.instrument_id,))
    store.save_universe_snapshot(snapshot); store.save_instrument(item)
    identity = InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, "EQ", InstrumentType.NSE_EQUITY, item.company_name)
    return repository, store, identity


def test_local_bse_job_uses_canonical_importer_preserves_pit_and_is_idempotent(tmp_path: Path) -> None:
    repository, universe, identity = _universe(tmp_path)
    source = tmp_path / "bse"; source.mkdir(); (source / "apollo.xml").write_text(_xbrl(), encoding="utf-8")
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.sqlite")
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    job = BseLocalFinancialResultsRefreshJob(repository=repository, universe=universe, filings=filings, facts=facts, source_directory=source)

    first = job.refresh(_request())
    second = job.refresh(_request())
    stored = facts.series(identity.instrument_id, FinancialMetric.PAT, as_of=T, limit=10)

    assert first.status is EvidenceRefreshStatus.COMPLETE and first.accepted_count == 1
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == 1
    assert stored[0].value == Decimal("10") and stored[0].available_at == T
    assert stored[0].scale is NumericScale.UNITS
    assert not facts.series(identity.instrument_id, FinancialMetric.PAT, as_of=T - timedelta(microseconds=1), limit=10)


def test_bse_job_records_immutable_legacy_display_scale_compatibility(tmp_path: Path) -> None:
    repository, universe, identity = _universe(tmp_path)
    source = tmp_path / "bse"; source.mkdir(); (source / "apollo.xml").write_text(_xbrl(), encoding="utf-8")
    baseline_filings = SQLiteCorporateFilingsStore(tmp_path / "baseline-filings.sqlite")
    baseline_facts = SQLiteFinancialFactStore(tmp_path / "baseline-facts.sqlite")
    service = BSEOfficialLocalXbrlIngestionService(baseline_filings, baseline_facts, clock=lambda: T)
    inspection = service.inspect(source / "apollo.xml")
    service.ingest(identity, inspection.document.security_code, source / "apollo.xml")
    facts = SQLiteFinancialFactStore(tmp_path / "legacy-facts.sqlite")
    for metric in (FinancialMetric.REVENUE, FinancialMetric.PBT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC):
        current = baseline_facts.series(identity.instrument_id, metric, limit=10)[0]
        assert facts.save(replace(current, scale=NumericScale.MILLIONS)).value == "INSERTED"
    job = BseLocalFinancialResultsRefreshJob(
        repository=repository, universe=universe, filings=SimpleNamespace(), facts=facts, source_directory=source,
    )

    first = job.refresh(_request())
    second = job.refresh(_request())
    artifact = repository.get_snapshot("bse-legacy-scale-reconciliation:" + inspection.checksum)

    assert first.status is EvidenceRefreshStatus.COMPLETE and first.accepted_count == 1
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == 1
    assert facts.series(identity.instrument_id, FinancialMetric.PAT, limit=10)[0].scale is NumericScale.MILLIONS
    assert artifact is not None and artifact.family is CoreApiSnapshotFamily.RECONCILIATION_RESULT
    assert isinstance(artifact.payload, BseLegacyScaleReconciliation)
    assert all(item.official_raw_scale is NumericScale.UNITS for item in artifact.payload.compatibilities)
    assert artifact.payload.known_at == T


def test_nonrevision_value_conflict_remains_distinct_from_representation_conflict() -> None:
    document = SimpleNamespace(
        facts=((FinancialMetric.PAT, Decimal("10")),), scale=NumericScale.LAKHS,
        scope=SimpleNamespace(),
    )
    inspection = SimpleNamespace(document=document, period_type=SimpleNamespace(), period_end=datetime(2026, 6, 30, tzinfo=UTC))
    store = SimpleNamespace(series=lambda *_args, **_kwargs: (SimpleNamespace(period_end=inspection.period_end, value=Decimal("9"), scale=NumericScale.UNITS),))

    assert _nonrevision_conflict_reason(store, "NSE:APOLLOHOSP", inspection) == "BSE_LOCAL_XBRL_NONREVISION_VALUE_CONFLICT"


def test_bse_legacy_representation_requires_complete_attestable_document_match(tmp_path: Path) -> None:
    repository, universe, _identity = _universe(tmp_path)
    source = tmp_path / "bse"; source.mkdir(); (source / "apollo.xml").write_text(_xbrl(), encoding="utf-8")
    # One metric has a display-scale mismatch but the remaining official facts
    # are absent: accepting it would hide an unresolved partial document.
    legacy = SimpleNamespace(
        period_end=datetime(2026, 6, 30, tzinfo=UTC), value=Decimal("10"), scale=NumericScale.MILLIONS,
        fact_id="legacy", currency="INR", unit="INR", available_at=T, published_at=T, received_at=T,
    )
    facts = SimpleNamespace(series=lambda _instrument_id, metric, **_kwargs: (legacy,) if metric is FinancialMetric.PAT else ())
    job = BseLocalFinancialResultsRefreshJob(repository=repository, universe=universe, filings=SimpleNamespace(), facts=facts, source_directory=source)

    report = job.refresh(_request())

    assert report.status is EvidenceRefreshStatus.PARTIAL and report.conflict_count == 1
    assert report.findings[0][2] == "BSE_LOCAL_XBRL_LEGACY_REPRESENTATION_MIXED_OR_INCOMPLETE"
    assert repository.list_snapshots(CoreApiSnapshotFamily.RECONCILIATION_RESULT) == ()


def test_shareholding_job_requires_an_official_regulation_31_artifact_and_never_falls_back(tmp_path: Path) -> None:
    repository, universe, _identity = _universe(tmp_path)
    job = NseReg31ShareholdingRefreshJob(
        repository=repository, universe=universe, filings=SimpleNamespace(), facts=SimpleNamespace(),
        runs=ImportRunStore(tmp_path / "imports.sqlite"), source_directory=tmp_path / "missing-reg31",
    )

    report = job.refresh(_request(EvidenceDataFamily.SHAREHOLDING))

    assert report.status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE
    assert report.error_summary == "NSE_REG31_SHAREHOLDING_EXPORT_REQUIRED"
