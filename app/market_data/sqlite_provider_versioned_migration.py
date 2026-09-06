"""Explicit, local-only SQLite migration for provider-versioned OHLCV bars.

This is deliberately independent of Alembic: local development uses persistent
SQLite while production migrations target PostgreSQL.  It never opens a
provider, credential store, or network client.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
import sqlite3
from typing import Callable

from app.market_data.historical import (
    SQLITE_HISTORICAL_BAR_TABLE,
    SQLITE_PROVIDER_IDENTITY,
    SQLITE_UNKNOWN_EXISTING_SOURCE,
    sqlite_provider_versioned_historical_bars_schema,
)


class SQLiteProviderVersionedMigrationStatus(StrEnum):
    MIGRATED = "MIGRATED"
    ALREADY_CURRENT = "ALREADY_CURRENT"
    FAILED_ROLLED_BACK = "FAILED_ROLLED_BACK"


@dataclass(frozen=True, slots=True)
class SQLiteHistoricalBarsSchema:
    columns: tuple[str, ...]
    primary_key: tuple[str, ...]
    indexes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SQLiteProviderVersionedMigrationReport:
    database_path: str
    backup_path: str | None
    schema_before: SQLiteHistoricalBarsSchema
    schema_after: SQLiteHistoricalBarsSchema
    rows_before: int
    rows_after: int
    legacy_rows_tagged_unknown_existing_source: int
    migration_status: SQLiteProviderVersionedMigrationStatus
    error: str | None = None

    def json_dict(self) -> dict[str, object]:
        return asdict(self)


def inspect_sqlite_historical_bars_schema(connection: sqlite3.Connection) -> SQLiteHistoricalBarsSchema:
    columns = tuple(str(row[1]) for row in connection.execute(f"PRAGMA table_info({SQLITE_HISTORICAL_BAR_TABLE})"))
    primary_key = tuple(
        str(row[1])
        for row in sorted(
            (row for row in connection.execute(f"PRAGMA table_info({SQLITE_HISTORICAL_BAR_TABLE})") if int(row[5]) > 0),
            key=lambda row: int(row[5]),
        )
    )
    indexes = tuple(sorted(str(row[1]) for row in connection.execute(f"PRAGMA index_list({SQLITE_HISTORICAL_BAR_TABLE})")))
    return SQLiteHistoricalBarsSchema(columns, primary_key, indexes)


def is_provider_versioned_schema(schema: SQLiteHistoricalBarsSchema) -> bool:
    key = ("instrument_id", "timeframe", "start_time", "end_time", SQLITE_PROVIDER_IDENTITY)
    return SQLITE_PROVIDER_IDENTITY in schema.columns and schema.primary_key in (
        key, (*key, "source_observation_identity"),
    )


def migrate_sqlite_provider_versioned_historical_bars(
    database_path: str | Path,
    *,
    backup_directory: str | Path | None = None,
    report_path: str | Path | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    before_copy: Callable[[sqlite3.Connection], None] | None = None,
) -> SQLiteProviderVersionedMigrationReport:
    """Rebuild the old four-column-key table inside one SQLite transaction.

    ``before_copy`` is a test-only fault seam used to prove DDL rollback.  It
    is not exposed by the runtime command.
    """
    path = Path(database_path)
    if str(path) == ":memory:" or not path.is_file():
        raise ValueError("PERSISTENT_SQLITE_HISTORICAL_DATABASE_REQUIRED")

    connection = sqlite3.connect(path)
    try:
        integrity = _integrity_check(connection)
        schema_before = inspect_sqlite_historical_bars_schema(connection)
        if integrity.lower() != "ok":
            report = SQLiteProviderVersionedMigrationReport(
                str(path), None, schema_before, schema_before, 0, 0, 0,
                SQLiteProviderVersionedMigrationStatus.FAILED_ROLLED_BACK, "SQLITE_INTEGRITY_CHECK_FAILED",
            )
            _write_report(report, report_path)
            return report
        if not schema_before.columns:
            raise ValueError("HISTORICAL_BARS_TABLE_REQUIRED")
        rows_before = _row_count(connection)
        if is_provider_versioned_schema(schema_before):
            report = SQLiteProviderVersionedMigrationReport(
                str(path), None, schema_before, schema_before, rows_before, rows_before, 0,
                SQLiteProviderVersionedMigrationStatus.ALREADY_CURRENT,
            )
            _write_report(report, report_path)
            return report

        backup = _create_backup(connection, path, backup_directory, clock())
        connection.isolation_level = None
        try:
            connection.execute("BEGIN IMMEDIATE")
            temporary = f"{SQLITE_HISTORICAL_BAR_TABLE}_u06r_new"
            connection.execute(f"DROP TABLE IF EXISTS {temporary}")
            connection.execute(sqlite_provider_versioned_historical_bars_schema(temporary))
            if before_copy is not None:
                before_copy(connection)
            connection.execute(f"""
                INSERT INTO {temporary} (
                    instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,
                    adjustment_status,instrument_json,provenance_json,quality,warnings_json
                )
                SELECT instrument_id,timeframe,start_time,end_time,?,bar_id,open,high,low,close,volume,turnover,trade_count,
                    adjustment_status,instrument_json,provenance_json,quality,warnings_json
                FROM {SQLITE_HISTORICAL_BAR_TABLE}
            """, (SQLITE_UNKNOWN_EXISTING_SOURCE,))
            rows_after_copy = int(connection.execute(f"SELECT COUNT(*) FROM {temporary}").fetchone()[0])
            if rows_after_copy != rows_before:
                raise RuntimeError("SQLITE_PROVIDER_VERSIONED_ROW_COUNT_MISMATCH")
            connection.execute(f"DROP TABLE {SQLITE_HISTORICAL_BAR_TABLE}")
            connection.execute(f"ALTER TABLE {temporary} RENAME TO {SQLITE_HISTORICAL_BAR_TABLE}")
            connection.execute(
                "CREATE INDEX historical_bars_instrument_time_start_idx "
                "ON historical_bars (instrument_id, timeframe, start_time, end_time)"
            )
            integrity_after = _integrity_check(connection)
            schema_after = inspect_sqlite_historical_bars_schema(connection)
            rows_after = _row_count(connection)
            if integrity_after.lower() != "ok" or rows_after != rows_before or not is_provider_versioned_schema(schema_after):
                raise RuntimeError("SQLITE_PROVIDER_VERSIONED_POST_MIGRATION_VERIFICATION_FAILED")
            connection.execute("COMMIT")
        except Exception as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            schema_after = inspect_sqlite_historical_bars_schema(connection)
            report = SQLiteProviderVersionedMigrationReport(
                str(path), str(backup), schema_before, schema_after, rows_before, _row_count(connection), 0,
                SQLiteProviderVersionedMigrationStatus.FAILED_ROLLED_BACK, type(error).__name__,
            )
            _write_report(report, report_path)
            return report

        report = SQLiteProviderVersionedMigrationReport(
            str(path), str(backup), schema_before, schema_after, rows_before, rows_after, rows_before,
            SQLiteProviderVersionedMigrationStatus.MIGRATED,
        )
        _write_report(report, report_path)
        return report
    finally:
        connection.close()


def _row_count(connection: sqlite3.Connection) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {SQLITE_HISTORICAL_BAR_TABLE}").fetchone()[0])


def _integrity_check(connection: sqlite3.Connection) -> str:
    return str(connection.execute("PRAGMA integrity_check").fetchone()[0])


def _create_backup(connection: sqlite3.Connection, database_path: Path, directory: str | Path | None, timestamp: datetime) -> Path:
    target_directory = Path(directory) if directory is not None else database_path.parent / "backups"
    target_directory.mkdir(parents=True, exist_ok=True)
    target = target_directory / f"{database_path.stem}.pre_u06r.{timestamp.astimezone(UTC):%Y%m%dT%H%M%SZ}.db"
    if target.exists():
        raise FileExistsError("SQLITE_PROVIDER_VERSIONED_BACKUP_ALREADY_EXISTS")
    destination = sqlite3.connect(target)
    try:
        connection.backup(destination)
    finally:
        destination.close()
    return target


def _write_report(report: SQLiteProviderVersionedMigrationReport, report_path: str | Path | None) -> None:
    if report_path is None:
        return
    target = Path(report_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report.json_dict(), sort_keys=True, indent=2), encoding="utf-8")
