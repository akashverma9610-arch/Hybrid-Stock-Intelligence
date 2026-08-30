from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.data_sources.models import (
    AdjustmentCapability, DataFamily, DataFreshnessPolicy, DataRequirement,
    DataSourceReadiness, DataSourceReadinessReport, FreshnessBasis,
    PointInTimeCapability, SourceReadinessStatus,
)
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.importer import OfficialNseUniverseImporter
from app.universe_analysis.models import (
    CoverageDomain, CoverageDomainRecord, CoverageDomainStatus,
    NseEquityInstrument, UniverseInstrumentCoverage,
)
from app.universe_analysis.readiness import (
    DataReadinessService, FullScanStatus, ProviderMappingReadiness,
    ProviderMappingStatus,
)
from app.universe_analysis.service import CoreUniverseAnalysisStore

T = datetime(2026, 8, 23, 10, tzinfo=UTC)


def instrument(symbol: str = "ALPHA") -> NseEquityInstrument:
    return NseEquityInstrument(f"NSE:{symbol}", symbol, None, "INDUSTRIALS", "ENGINEERING", "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT", security_type="EQUITY", exchange="NSE", main_board=True)


def bar(item: NseEquityInstrument, stamp: datetime) -> CanonicalOHLCVBar:
    identity = InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, None, InstrumentType.NSE_EQUITY, item.symbol)
    return CanonicalOHLCVBar(f"bar:{item.instrument_id}:{stamp.date()}", identity, Timeframe.DAILY, stamp, stamp + timedelta(days=1), Decimal("10"), Decimal("11"), Decimal("9"), Decimal("10"), 100, None, None, AdjustmentStatus.RAW, MarketDataProvenance("fixture", None, stamp, stamp, T, "fixture-v1"), __import__("app.domain.models", fromlist=["DataQuality"]).DataQuality.HIGH)


def coverage(item: NseEquityInstrument, status: CoverageDomainStatus = CoverageDomainStatus.READY) -> UniverseInstrumentCoverage:
    return UniverseInstrumentCoverage(f"coverage:{item.instrument_id}", "snapshot", "job", item.instrument_id, T, tuple(CoverageDomainRecord(domain, status, T, "FRESH") for domain in CoverageDomain))


def source_report(status: SourceReadinessStatus = SourceReadinessStatus.READY) -> DataSourceReadinessReport:
    policy = DataFreshnessPolicy(DataFamily.CURRENT_QUOTES, FreshnessBasis.WALL_CLOCK, timedelta(minutes=1))
    item = DataSourceReadiness("kotak_neo", "kotak_neo", DataFamily.CURRENT_QUOTES, DataRequirement.OPTIONAL, 1, status, status is not SourceReadinessStatus.MISSING_CONFIGURATION, status is SourceReadinessStatus.READY, None, None, policy, PointInTimeCapability.LIMITED, AdjustmentCapability.NOT_APPLICABLE, (), None)
    return DataSourceReadinessReport(T, "STORED_DATA", (item,))


def test_official_universe_dry_run_is_local_only_and_does_not_persist(tmp_path):
    path = tmp_path / "nse.csv"
    path.write_text("SYMBOL,ISIN,SECTOR,INDUSTRY,MAIN_BOARD,SECURITY_TYPE,EXCHANGE\nALPHA,INE1,Industrials,Engineering,true,EQUITY,NSE\nALPHA,INE1,Industrials,Engineering,true,EQUITY,NSE\nETF1,INE2,,,false,ETF,NSE\n", encoding="utf-8")
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite"))
    report = OfficialNseUniverseImporter(store).import_csv(path, as_of=T, snapshot_id="snapshot", dry_run=True)
    assert report.raw_records == 3 and report.duplicates == 1 and report.snapshot.eligible_security_count == 1
    assert store.get_universe_snapshot("snapshot") is None
    persisted = OfficialNseUniverseImporter(store).import_csv(path, as_of=T, snapshot_id="persisted")
    assert persisted.snapshot.excluded_count == 1 and store.get_universe_snapshot("persisted") == persisted.snapshot


def test_readiness_aggregates_stored_coverage_and_blocks_without_mappings(tmp_path):
    item = instrument()
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    for offset in range(6):
        stamp = T - timedelta(days=offset + 1)
        store.upsert(bar(item, stamp))
    snapshot = __import__("app.universe_analysis.service", fromlist=["build_universe_snapshot"]).build_universe_snapshot(snapshot_id="snapshot", as_of=T, source="NSE", instruments=(item,))
    service = DataReadinessService(historical_bars=store, source_report=source_report(), clock=lambda: T)
    report = service.assess(snapshot=snapshot, instruments=(item,), as_of=T, coverage_records=(coverage(item),))
    assert report.historical.enough_lookback == 1
    assert all(value.ready == 1 for value in report.coverage)
    assert report.full_scan.status is FullScanStatus.NOT_READY_FOR_FULL_SCAN
    assert "SYMBOL_MAPPING_LOW" in report.full_scan.blockers
    sample = service.deterministic_sample(snapshot=snapshot, instruments=(item,), limit=1)
    assert sample == (item,)


def test_readiness_preserves_mapping_states_and_never_claims_unvalidated_provider_ready():
    item = instrument()
    snapshot = __import__("app.universe_analysis.service", fromlist=["build_universe_snapshot"]).build_universe_snapshot(snapshot_id="snapshot", as_of=T, source="NSE", instruments=(item,))
    mapping = {(item.instrument_id, "kotak_neo"): ProviderMappingReadiness(item.instrument_id, "kotak_neo", ProviderMappingStatus.MATCHED, "token")}
    report = DataReadinessService(source_report=source_report(SourceReadinessStatus.CONFIGURED_NOT_VALIDATED), mapping_registry=mapping, clock=lambda: T).assess(snapshot=snapshot, instruments=(item,), as_of=T)
    assert next(value for value in report.mapping_statuses if value.provider == "kotak_neo").status is ProviderMappingStatus.MATCHED
    assert ("kotak_neo", SourceReadinessStatus.CONFIGURED_NOT_VALIDATED) in report.provider_statuses
    assert "PROVIDER_UNVALIDATED" in report.full_scan.blockers


def test_cli_universe_import_and_readiness_are_non_network_and_secret_free(tmp_path):
    path = tmp_path / "nse.csv"; path.write_text("SYMBOL,MAIN_BOARD,SECURITY_TYPE,EXCHANGE\nALPHA,true,EQUITY,NSE\n", encoding="utf-8")
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite"))
    output: list[str] = []
    from app.runtime.cli import main
    assert main(["import-nse-universe", str(path), "--dry-run"], universe_importer_factory=lambda: OfficialNseUniverseImporter(store), output=output.append) == 0
    assert "dry_run=True" in output[0] and "access_key" not in output[0]
    output.clear()
    class Sources:
        def readiness(self, **_): return source_report(SourceReadinessStatus.MISSING_CONFIGURATION)
    assert main(["data-readiness"], data_readiness_factory=lambda: Sources(), output=output.append) == 0
    assert "MISSING_CONFIGURATION" in output[0] and "secret" not in output[0].lower()
