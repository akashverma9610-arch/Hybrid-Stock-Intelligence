from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

import pytest

from app.domain.models import DataQuality
from app.market_data.historical import (
    BarWriteOutcome, SQLITE_UNKNOWN_EXISTING_SOURCE, SQLiteHistoricalBarStore,
    _bar_values,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.market_data.sqlite_provider_versioned_migration import (
    SQLiteProviderVersionedMigrationStatus, inspect_sqlite_historical_bars_schema,
    migrate_sqlite_provider_versioned_historical_bars,
)
from app.runtime.cli import RuntimeCompositionError, main, migrate_sqlite_provider_versioned_bars_factory


T = datetime(2026, 8, 28, tzinfo=UTC)
I = InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01000", "EQ", InstrumentType.NSE_EQUITY, "Alpha")


def _bar(provider: str, *, close: str = "100") -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(
        f"{provider}-bar", I, Timeframe.DAILY, T - timedelta(days=1), T,
        Decimal("99"), Decimal("101"), Decimal("98"), Decimal(close), 1000, None, None,
        AdjustmentStatus.RAW,
        MarketDataProvenance(provider, f"{provider}:alpha", T, T, T, "v1", source_reference=provider),
        DataQuality.HIGH,
    )


def _create_legacy_database(path: Path, bars: tuple[CanonicalOHLCVBar, ...] = (_bar("yfinance"),)) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("""CREATE TABLE historical_bars (
            instrument_id TEXT NOT NULL, timeframe TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            bar_id TEXT NOT NULL, open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
            volume INTEGER, turnover TEXT, trade_count INTEGER, adjustment_status TEXT NOT NULL,
            instrument_json TEXT NOT NULL, provenance_json TEXT NOT NULL, quality TEXT NOT NULL, warnings_json TEXT NOT NULL,
            PRIMARY KEY (instrument_id,timeframe,start_time,end_time)
        )""")
        connection.executemany("INSERT INTO historical_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", tuple(_bar_values(bar) for bar in bars))
        connection.commit()
    finally:
        connection.close()


def test_legacy_sqlite_rebuild_creates_backup_preserves_rows_and_tags_unknown_source(tmp_path) -> None:
    path = tmp_path / "nse_stock_manager.db"
    legacy = _bar("yfinance")
    _create_legacy_database(path, (legacy,))

    report = migrate_sqlite_provider_versioned_historical_bars(
        path, backup_directory=tmp_path / "backups", report_path=tmp_path / "report.json",
        clock=lambda: T,
    )

    assert report.migration_status is SQLiteProviderVersionedMigrationStatus.MIGRATED
    assert Path(report.backup_path or "").is_file()
    assert report.rows_before == report.rows_after == report.legacy_rows_tagged_unknown_existing_source == 1
    assert report.schema_before.primary_key == ("instrument_id", "timeframe", "start_time", "end_time")
    assert report.schema_after.primary_key == ("instrument_id", "timeframe", "start_time", "end_time", "provider_identity")
    assert (tmp_path / "report.json").is_file()
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        row = connection.execute("SELECT provider_identity,provenance_json FROM historical_bars").fetchone()
        assert row[0] == SQLITE_UNKNOWN_EXISTING_SOURCE
        assert json.loads(row[1])["provider"] == "yfinance"
    finally:
        connection.close()
    store = SQLiteHistoricalBarStore(path)
    migrated = store.range(I.instrument_id, Timeframe.DAILY, legacy.start_time, legacy.end_time)
    assert len(migrated) == 1 and migrated[0].close == legacy.close
    assert migrated[0].provenance.provider == SQLITE_UNKNOWN_EXISTING_SOURCE


def test_migrated_sqlite_allows_cross_provider_rows_but_rejects_same_provider_revision(tmp_path) -> None:
    path = tmp_path / "nse_stock_manager.db"
    legacy = _bar("yfinance")
    _create_legacy_database(path)
    migrate_sqlite_provider_versioned_historical_bars(path, backup_directory=tmp_path / "backups", clock=lambda: T)
    store = SQLiteHistoricalBarStore(path)
    yahoo = replace(legacy, bar_id="yahoo-current")
    upstox = _bar("upstox", close="101")
    assert store.upsert(yahoo) is BarWriteOutcome.INSERTED
    assert store.upsert(upstox) is BarWriteOutcome.INSERTED
    assert store.upsert(upstox) is BarWriteOutcome.IDENTICAL
    assert store.upsert(replace(upstox, close=Decimal("102"))) is BarWriteOutcome.CONFLICT
    assert store.raw_count(I.instrument_id, Timeframe.DAILY) == 3
    assert store.range(I.instrument_id, Timeframe.DAILY, T - timedelta(days=1), T) == (upstox,)


def test_repeated_sqlite_migration_is_idempotent_without_second_backup(tmp_path) -> None:
    path = tmp_path / "nse_stock_manager.db"
    _create_legacy_database(path)
    migrated = migrate_sqlite_provider_versioned_historical_bars(path, backup_directory=tmp_path / "backups", clock=lambda: T)
    current = migrate_sqlite_provider_versioned_historical_bars(path, backup_directory=tmp_path / "backups", clock=lambda: T)
    assert migrated.migration_status is SQLiteProviderVersionedMigrationStatus.MIGRATED
    assert current.migration_status is SQLiteProviderVersionedMigrationStatus.ALREADY_CURRENT
    assert current.backup_path is None
    assert len(tuple((tmp_path / "backups").glob("*.db"))) == 1


def test_integrity_failure_aborts_before_backup_or_table_mutation(tmp_path, monkeypatch) -> None:
    path = tmp_path / "nse_stock_manager.db"
    _create_legacy_database(path)
    import app.market_data.sqlite_provider_versioned_migration as migration
    monkeypatch.setattr(migration, "_integrity_check", lambda _: "not ok")
    report = migration.migrate_sqlite_provider_versioned_historical_bars(path, backup_directory=tmp_path / "backups")
    assert report.migration_status is SQLiteProviderVersionedMigrationStatus.FAILED_ROLLED_BACK
    assert report.backup_path is None
    connection = sqlite3.connect(path)
    try:
        assert inspect_sqlite_historical_bars_schema(connection).primary_key == ("instrument_id", "timeframe", "start_time", "end_time")
    finally:
        connection.close()


def test_copy_failure_rolls_back_without_losing_legacy_table(tmp_path) -> None:
    path = tmp_path / "nse_stock_manager.db"
    _create_legacy_database(path)
    report = migrate_sqlite_provider_versioned_historical_bars(
        path, backup_directory=tmp_path / "backups", before_copy=lambda _: (_ for _ in ()).throw(RuntimeError("forced copy failure")),
    )
    assert report.migration_status is SQLiteProviderVersionedMigrationStatus.FAILED_ROLLED_BACK
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM historical_bars").fetchone()[0] == 1
        assert inspect_sqlite_historical_bars_schema(connection).primary_key == ("instrument_id", "timeframe", "start_time", "end_time")
    finally:
        connection.close()


def test_local_migration_factory_refuses_postgresql_and_in_memory(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost/test")
    with pytest.raises(RuntimeCompositionError, match="REFUSES_POSTGRESQL"):
        migrate_sqlite_provider_versioned_bars_factory()
    monkeypatch.delenv("DATABASE_BACKEND")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    with pytest.raises(RuntimeCompositionError, match="REQUIRES_PERSISTENT_SQLITE"):
        migrate_sqlite_provider_versioned_bars_factory()


def test_explicit_cli_migrates_only_persistent_sqlite_and_reports_safe_outcome(tmp_path, monkeypatch) -> None:
    path = tmp_path / "nse_stock_manager.db"
    _create_legacy_database(path)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{path.as_posix()}")
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)
    monkeypatch.chdir(tmp_path)
    output: list[str] = []

    assert main(["migrate-sqlite-provider-versioned-bars"], output=output.append) == 0

    assert any("migration_status=MIGRATED" in line for line in output)
    assert any("legacy_rows_tagged_unknown_existing_source=1" in line for line in output)
    assert (tmp_path / "reports" / "sqlite_provider_versioned_migration.json").is_file()
