from datetime import UTC, datetime

from app.data_sources.models import SourceReadinessStatus
from app.runtime.data_readiness import LocalDataReadinessService
from app.storage.database import DatabaseBackend, DatabaseSettings, DatabaseStorageMode
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.importer import OfficialNseUniverseImporter
from app.universe_analysis.readiness import FullScanStatus, ProviderMappingStatus
from app.universe_analysis.service import CoreUniverseAnalysisStore

T = datetime(2026, 8, 23, 10, tzinfo=UTC)


def _csv(tmp_path):
    file = tmp_path / "official-nse.csv"
    file.write_text(
        "SYMBOL,ISIN,SECTOR,INDUSTRY,MAIN_BOARD,SECURITY_TYPE,EXCHANGE\n"
        "ALPHA,INE000A01000,Industrials,Engineering,true,EQUITY,NSE\n"
        "ALPHA,INE000A01000,Industrials,Engineering,true,EQUITY,NSE\n"
        ",INE000A01001,,,true,EQUITY,NSE\n"
        "ETF1,BAD,,,false,ETF,NSE\n",
        encoding="utf-8",
    )
    return file


def _store(path):
    return CoreUniverseAnalysisStore(create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{path.as_posix()}")))


def test_local_runtime_database_defaults_to_persistent_relative_path_and_keeps_test_default_isolated():
    runtime = DatabaseSettings.local_runtime({})
    assert runtime.storage_mode is DatabaseStorageMode.PERSISTENT_SQLITE
    assert runtime.url == "sqlite:///data/nse_stock_manager.db"
    assert DatabaseSettings.from_environment({}).storage_mode is DatabaseStorageMode.IN_MEMORY_SQLITE


def test_universe_import_refuses_an_explicit_in_memory_database(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    from app.runtime.cli import RuntimeCompositionError, build_nse_universe_importer
    try:
        build_nse_universe_importer()
    except RuntimeCompositionError as error:
        assert "not durable" in str(error)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("in-memory universe import was unexpectedly allowed")


def test_official_import_persists_across_reopen_and_is_checksum_idempotent(tmp_path):
    path, database = _csv(tmp_path), tmp_path / "data" / "nse.db"
    first_store = _store(database)
    importer = OfficialNseUniverseImporter(first_store)
    dry = importer.import_csv(path, as_of=T, snapshot_id="dry", dry_run=True)
    assert first_store.get_universe_snapshot("dry") is None
    assert dry.raw_records == 4 and dry.duplicates == 1 and dry.missing_symbol_count == 1 and dry.malformed_isin_count == 1
    first = importer.import_csv(path, as_of=T, snapshot_id="v1")
    assert first.snapshot.eligible_security_count == 1 and first.excluded == 1 and first.identical is False
    first_store._repository.close()
    reopened = _store(database)
    assert reopened.get_universe_snapshot("v1") == first.snapshot
    repeated = OfficialNseUniverseImporter(reopened).import_csv(path, as_of=T.replace(hour=11), snapshot_id="v2")
    assert repeated.identical is True and repeated.snapshot == first.snapshot and reopened.get_universe_snapshot("v2") is None
    reopened._repository.close()


def test_identical_official_content_can_create_a_forward_only_immutable_as_of_snapshot(tmp_path):
    path, database = _csv(tmp_path), tmp_path / "data" / "nse.db"
    store = _store(database)
    original = OfficialNseUniverseImporter(store).import_csv(path, as_of=T, snapshot_id="v1").snapshot
    refreshed_at = T.replace(day=24)
    refreshed = OfficialNseUniverseImporter(store).import_csv(
        path, as_of=refreshed_at, snapshot_id="v2", refresh_identical_as_of=True,
    ).snapshot
    assert refreshed.snapshot_id == "v2"
    assert refreshed.checksum == original.checksum
    assert refreshed.as_of == refreshed_at
    assert f"IDENTICAL_CONTENT_REFRESH_OF:{original.snapshot_id}" in refreshed.warnings
    assert store.get_universe_snapshot(original.snapshot_id) == original
    assert store.latest_universe_snapshot() == refreshed
    # Refreshing at a non-forward timestamp cannot backdate or replace history.
    repeat = OfficialNseUniverseImporter(store).import_csv(
        path, as_of=refreshed_at, snapshot_id="v3", refresh_identical_as_of=True,
    )
    assert repeat.identical and repeat.snapshot == refreshed and store.get_universe_snapshot("v3") is None
    store._repository.close()


def test_persistent_readiness_reopens_universe_and_reports_truthful_mapping_gaps(tmp_path, monkeypatch):
    path, database = _csv(tmp_path), tmp_path / "data" / "nse.db"
    store = _store(database)
    snapshot = OfficialNseUniverseImporter(store).import_csv(path, as_of=T, snapshot_id="v1").snapshot
    store._repository.close()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    report = LocalDataReadinessService(DatabaseSettings.local_runtime(), clock=lambda: T).report()
    assert report.database.ready and report.database.storage_mode is DatabaseStorageMode.PERSISTENT_SQLITE
    assert report.universe.universe_snapshot_id == snapshot.snapshot_id
    assert report.universe.eligible_equities == 1
    assert all(item.status is ProviderMappingStatus.UNMATCHED for item in report.universe.mapping_statuses)
    assert "MAPPING_SOURCE_UNAVAILABLE" in report.universe.warnings
    assert report.universe.full_scan.status is FullScanStatus.NOT_READY_FOR_FULL_SCAN
    assert any(status is SourceReadinessStatus.MISSING_CONFIGURATION for _, status in report.universe.provider_statuses)


def test_cli_import_then_fresh_universe_status_reads_the_persistent_snapshot(tmp_path, monkeypatch):
    file, database = _csv(tmp_path), tmp_path / "data" / "nse.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    from app.runtime.cli import main
    imported: list[str] = []
    assert main(["import-nse-universe", str(file)], output=imported.append) == 0
    assert "status=IMPORTED" in imported[0] and "eligible_equities=1" in imported[0]
    # A fresh CLI composition reopens the file rather than reusing the importer.
    status: list[str] = []
    assert main(["universe-status"], output=status.append) == 0
    assert any("universe_snapshot=nse-universe:" in value and "eligible=1" in value for value in status)


def test_official_equity_l_spacing_is_normalized_at_the_import_boundary(tmp_path):
    file = tmp_path / "EQUITY_L.csv"
    file.write_text("SYMBOL,NAME OF COMPANY, SERIES, ISIN NUMBER\nALPHA,Alpha Ltd,EQ,INE000A01000\n", encoding="utf-8")
    store = CoreUniverseAnalysisStore(create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{(tmp_path / 'nse.db').as_posix()}")))
    result = OfficialNseUniverseImporter(store).import_csv(file, as_of=T, snapshot_id="official")
    assert result.snapshot.instrument_ids == ("NSE:INE000A01000",)
