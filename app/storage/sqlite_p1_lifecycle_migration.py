"""Explicit SQLite provisioning, not prospective recorder activation.

Reuse the existing P1 DDL without replaying unrelated Alembic migrations on
constructor-managed SQLite databases. No signal, start marker or source is
fabricated. The SQLite backup API and exclusive backup creation follow the
existing sqlite_udiff_series_migration safety pattern.
"""
from contextlib import closing
from pathlib import Path
import sqlite3

from app.storage.sqlite_p1_signal_lifecycle import SCHEMA


TABLES = ("p1_signal_lifecycle_batch_index", "p1_signal_lifecycle_heads")
VERSION = "p1-lifecycle-sqlite-provision/v1"
FAMILY = "P1_SIGNAL_LIFECYCLE_BATCH"


def _objects(connection):
    return dict(connection.execute(
        "SELECT name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"
    ))


def _check_integrity(connection):
    if list(connection.execute("PRAGMA integrity_check")) != [("ok",)]:
        raise ValueError("P1_MIGRATION_INTEGRITY_FAILED")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("P1_MIGRATION_FOREIGN_KEY_FAILED")


def _shape(connection, table):
    columns = tuple(connection.execute(f"PRAGMA table_info({table})"))
    foreign_keys = tuple(connection.execute(f"PRAGMA foreign_key_list({table})"))
    unique = []
    for row in connection.execute(f"PRAGMA index_list({table})"):
        if row[2]:
            name = row[1].replace('"', '""')
            unique.append(tuple(r[2] for r in connection.execute(f'PRAGMA index_info("{name}")')))
    return columns, foreign_keys, tuple(sorted(unique))


def _verify_schema(connection):
    with closing(sqlite3.connect(":memory:")) as expected:
        for statement in SCHEMA:
            expected.execute(statement)
        if any(_shape(connection, table) != _shape(expected, table) for table in TABLES):
            raise ValueError("P1_MIGRATION_SCHEMA_CONFLICT")


def provision(database: Path, backup: Path) -> dict[str, str | None]:
    """Backup + provision only; no scheduler, producer, or historical admission.

    Refuse partial schema and pre-existing P1 payloads without indexes. Existing
    matching schema is a read-only no-op. A writer lock protects the whole backup
    and DDL interval; callers should use an operator maintenance window.
    """
    database, backup = Path(database).resolve(), Path(backup).resolve()
    if not database.is_file() or database == backup:
        raise ValueError("P1_MIGRATION_DATABASE_REQUIRED")
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True, timeout=2)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        before = _objects(connection)
        present = set(TABLES).intersection(before)
        if present:
            if present != set(TABLES):
                raise ValueError("P1_MIGRATION_SCHEMA_CONFLICT")
            _verify_schema(connection)
            return {"version": VERSION, "status": "ALREADY_PROVISIONED", "prospective_start": None}
        if "core_api_snapshots" not in before:
            raise ValueError("P1_MIGRATION_CORE_SCHEMA_REQUIRED")
        if connection.execute("SELECT 1 FROM core_api_snapshots WHERE family=? LIMIT 1", (FAMILY,)).fetchone():
            raise ValueError("P1_MIGRATION_EXISTING_HISTORY_REQUIRES_REVIEW")
        if backup.exists():
            raise ValueError("P1_MIGRATION_BACKUP_EXISTS")
        _check_integrity(connection)
        connection.execute("BEGIN IMMEDIATE")
        try:
            # Recheck after acquiring the lock; never overwrite racing DDL/data.
            if _objects(connection) != before or connection.execute(
                "SELECT 1 FROM core_api_snapshots WHERE family=? LIMIT 1", (FAMILY,)
            ).fetchone():
                raise ValueError("P1_MIGRATION_CONCURRENT_CHANGE")
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("xb"):
                pass
            # Backup from a separate read connection: backing up the connection
            # holding BEGIN IMMEDIATE would deadlock the SQLite backup API.
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as source:
                with closing(sqlite3.connect(backup)) as destination:
                    source.backup(destination)
                    _check_integrity(destination)
                    if _objects(destination) != before:
                        raise ValueError("P1_MIGRATION_BACKUP_SCHEMA_CONFLICT")
            for statement in SCHEMA:
                connection.execute(statement)
            _verify_schema(connection)
            after = _objects(connection)
            if {k: v for k, v in after.items() if k not in TABLES} != before:
                raise ValueError("P1_MIGRATION_UNRELATED_SCHEMA_CHANGE")
            if connection.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("P1_MIGRATION_FOREIGN_KEY_FAILED")
            connection.commit()
        except Exception:
            connection.rollback()
            # Keep any backup for operator inspection; never delete/reuse it.
            raise
        _check_integrity(connection)
        return {"version": VERSION, "status": "PROVISIONED_NOT_ACTIVE", "prospective_start": None}
