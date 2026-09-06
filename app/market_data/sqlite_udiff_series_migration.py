"""Explicit v1 source-series migration. No acquisition or implicit startup DDL.

The old table and every original column are retained verbatim. An archive
verifier is mandatory for each UDiFF row; provenance alone is not sufficient.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Callable

from app.market_data.historical import _bar_from_mapping, sqlite_series_aware_historical_bars_schema
from app.market_data.models import CanonicalOHLCVBar
from app.market_data.nse_udiff_source_identity import observation_key
from app.market_data.sqlite_provider_versioned_migration import inspect_sqlite_historical_bars_schema

VERSION = "nse-udiff-series-storage-v1"
RETAINED = "historical_bars_pre_udiff_series_v1"
KEY = ("instrument_id", "timeframe", "start_time", "end_time", "provider_identity")


def migrate(database: Path, backup: Path, *, verify_archive: Callable[[CanonicalOHLCVBar], None],
            before_swap: Callable[[], None] | None = None,
            progress: Callable[[int], None] | None = None) -> dict[str, object]:
    if not database.is_file() or database.resolve() == backup.resolve():
        raise ValueError("UDIFF_MIGRATION_DATABASE_REQUIRED")
    with closing(sqlite3.connect(database, timeout=30)) as c:
        c.row_factory = sqlite3.Row
        schema = inspect_sqlite_historical_bars_schema(c)
        if schema.primary_key == (*KEY, "source_observation_identity"):
            return {"version": VERSION, "status": "ALREADY_CURRENT"}
        if schema.primary_key != KEY or len(schema.columns) != 18:
            raise ValueError("UDIFF_MIGRATION_UNEXPECTED_SCHEMA")
        if c.execute("SELECT name FROM sqlite_master WHERE name IN (?,?)", (RETAINED, "historical_bars_udiff_v1_new")).fetchone():
            raise ValueError("UDIFF_MIGRATION_EXISTING_RECOVERY_TABLE")
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or c.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("UDIFF_MIGRATION_DATABASE_INTEGRITY_FAILED")
        # Renaming a referenced table could retarget a FK/view. Refuse that scope.
        for name, kind, sql in c.execute("SELECT name,type,sql FROM sqlite_master WHERE type IN ('table','view','trigger')"):
            if kind in ("view", "trigger") and sql and "historical_bars" in sql.lower():
                raise ValueError("UDIFF_MIGRATION_DEPENDENT_OBJECT")
            if kind == "table" and any(r[2] == "historical_bars" for r in c.execute('PRAGMA foreign_key_list("' + name.replace('"', '""') + '")')):
                raise ValueError("UDIFF_MIGRATION_DEPENDENT_FOREIGN_KEY")
        # Exclusive file creation prevents accidental replacement of a backup.
        backup.parent.mkdir(parents=True, exist_ok=True)
        with backup.open("xb"):
            pass
        with closing(sqlite3.connect(backup)) as destination:
            c.backup(destination)
            if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("UDIFF_MIGRATION_BACKUP_INVALID")
        columns = ",".join(schema.columns)
        count = c.execute("SELECT count(*) FROM historical_bars").fetchone()[0]
        try:
            c.execute("BEGIN IMMEDIATE")
            # No DROP/REPLACE: a leftover candidate is an explicit blocker.
            c.execute(sqlite_series_aware_historical_bars_schema("historical_bars_udiff_v1_new"))
            c.execute(f"INSERT INTO historical_bars_udiff_v1_new SELECT {columns},'' FROM historical_bars WHERE provider_identity <> 'nse_udiff_official'")
            verified = 0
            cursor = c.execute("SELECT * FROM historical_bars WHERE provider_identity='nse_udiff_official' ORDER BY start_time,instrument_id")
            while rows := cursor.fetchmany(1000):
                additions = []
                for row in rows:
                    bar = _bar_from_mapping(row)
                    verify_archive(bar)
                    additions.append((*tuple(row), observation_key(bar)))
                c.executemany("INSERT INTO historical_bars_udiff_v1_new VALUES (" + ",".join("?" for _ in range(19)) + ")", additions)
                verified += len(rows)
                if progress and verified % 50000 == 0:
                    progress(verified)
            after = c.execute("SELECT count(*) FROM historical_bars_udiff_v1_new").fetchone()[0]
            if after != count:
                raise ValueError("UDIFF_MIGRATION_ROW_COUNT_CHANGED")
            # Exact SQL value preservation, not a count-only or recomputed ID check.
            if c.execute(f"SELECT {columns} FROM historical_bars EXCEPT SELECT {columns} FROM historical_bars_udiff_v1_new LIMIT 1").fetchone():
                raise ValueError("UDIFF_MIGRATION_EVIDENCE_CHANGED")
            if before_swap:
                before_swap()
            c.execute(f"ALTER TABLE historical_bars RENAME TO {RETAINED}")
            c.execute("ALTER TABLE historical_bars_udiff_v1_new RENAME TO historical_bars")
            c.execute("CREATE INDEX historical_bars_udiff_v1_time_idx ON historical_bars(instrument_id,timeframe,start_time,end_time)")
            for operation in ("INSERT", "UPDATE", "DELETE"):
                c.execute(f"CREATE TRIGGER retained_udiff_v1_{operation.lower()} BEFORE {operation} ON {RETAINED} BEGIN SELECT RAISE(ABORT,'IMMUTABLE_PRE_MIGRATION_EVIDENCE'); END")
            if c.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("UDIFF_MIGRATION_FOREIGN_KEY_FAILED")
            c.commit()
        except Exception:
            c.rollback()
            raise
        return {"version": VERSION, "status": "MIGRATED", "before": count, "after": after,
                "archive_verified": verified, "retained_table": RETAINED, "backup": str(backup)}
