from __future__ import annotations
import sqlite3
from pathlib import Path
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_json, snapshot_json_from


class SQLiteCoreApiSnapshotRepository:
    """SQLite local/test implementation of immutable API read snapshots."""
    def __init__(self, database_path: str | Path = ":memory:") -> None:
        # FastAPI executes synchronous route handlers in its worker pool.  This
        # local read-model repository therefore intentionally permits the
        # single SQLite connection to be used by those worker threads.
        path = Path(database_path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("""CREATE TABLE IF NOT EXISTS core_api_snapshots (
            snapshot_id TEXT PRIMARY KEY, family TEXT NOT NULL, schema_version TEXT NOT NULL,
            record_type TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL,
            payload_json TEXT NOT NULL, UNIQUE(family, fingerprint))""")
        self._connection.execute("CREATE INDEX IF NOT EXISTS core_api_snapshots_family_created_idx ON core_api_snapshots(family, created_at, snapshot_id)")
        # The prospective canonical 15m reader must never scan every security's
        # snapshots to serve one exact canonical security.  These expressions
        # address only the existing immutable receipt payload fields; they do
        # not change snapshot content, identity, or retention semantics.
        self._connection.execute("CREATE INDEX IF NOT EXISTS core_api_snapshots_15m_security_interval_idx ON core_api_snapshots(family, json_extract(payload_json, '$.payload.fields.canonical_security_id'), json_extract(payload_json, '$.payload.fields.partition.fields.interval_start.value'), snapshot_id)")
        self._connection.execute("CREATE INDEX IF NOT EXISTS core_api_snapshots_15m_conflict_receipt_idx ON core_api_snapshots(family, json_extract(payload_json, '$.payload.fields.receipt_id'), snapshot_id)")
        self._connection.commit()
    def close(self) -> None: self._connection.close()
    def save_snapshot(self, value: CoreApiSnapshot) -> None:
        try:
            self._connection.execute("INSERT INTO core_api_snapshots VALUES (?,?,?,?,?,?,?)", (value.snapshot_id, value.family.value, value.schema_version, value.record_type, value.fingerprint, value.created_at.isoformat(), snapshot_json(value)))
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("Core API snapshots are immutable and cannot be overwritten.") from error
    def get_snapshot(self, snapshot_id: str) -> CoreApiSnapshot | None:
        row=self._connection.execute("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        return snapshot_json_from(row["payload_json"]) if row else None
    def list_snapshots(self, family: CoreApiSnapshotFamily, *, limit: int=100, offset: int=0) -> tuple[CoreApiSnapshot,...]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("Snapshot pagination is invalid.")
        rows=self._connection.execute("SELECT payload_json FROM core_api_snapshots WHERE family=? ORDER BY created_at,snapshot_id LIMIT ? OFFSET ?", (family.value,limit,offset)).fetchall()
        return tuple(snapshot_json_from(row["payload_json"]) for row in rows)
    def list_canonical_prospective_fifteen_minute_snapshots(self, canonical_security_id: str, *, known_at_lte: str | None, limit: int) -> tuple[CoreApiSnapshot,...]:
        if not canonical_security_id or not 1 <= limit <= 100: raise ValueError("Prospective 15m snapshot query is invalid.")
        query = "SELECT payload_json FROM core_api_snapshots WHERE family=? AND json_extract(payload_json, '$.payload.fields.canonical_security_id')=?"
        parameters: list[object] = [CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR.value, canonical_security_id]
        if known_at_lte is not None:
            query += " AND json_extract(payload_json, '$.payload.fields.known_at.value')<=?"
            parameters.append(known_at_lte)
        query += " ORDER BY json_extract(payload_json, '$.payload.fields.partition.fields.interval_start.value') DESC, snapshot_id DESC LIMIT ?"
        parameters.append(limit)
        rows=self._connection.execute(query, tuple(parameters)).fetchall()
        return tuple(snapshot_json_from(row["payload_json"]) for row in rows)
    def list_canonical_prospective_fifteen_minute_conflicts(self, receipt_ids: tuple[str, ...], *, detected_at_lte: str | None) -> tuple[CoreApiSnapshot,...]:
        if not receipt_ids or len(receipt_ids) > 100 or any(not value for value in receipt_ids): return ()
        placeholders = ",".join("?" for _ in receipt_ids)
        query = f"SELECT payload_json FROM core_api_snapshots WHERE family=? AND json_extract(payload_json, '$.payload.fields.receipt_id') IN ({placeholders})"
        parameters: list[object] = [CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT.value, *receipt_ids]
        if detected_at_lte is not None:
            query += " AND json_extract(payload_json, '$.payload.fields.detected_at.value')<=?"
            parameters.append(detected_at_lte)
        rows=self._connection.execute(query + " ORDER BY snapshot_id", tuple(parameters)).fetchall()
        return tuple(snapshot_json_from(row["payload_json"]) for row in rows)
