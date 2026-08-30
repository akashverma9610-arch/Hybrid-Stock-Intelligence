"""Small SQLite metadata repository.  It intentionally persists no credentials."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime

from app.connections.models import ConnectionAuditEvent, ConnectionMode, ConnectionProfile, ConnectionStatus


class SQLiteConnectionProfileRepository:
    def __init__(self, path: str = ":memory:") -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("CREATE TABLE IF NOT EXISTS connection_profiles (connection_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL)")
        self._connection.execute("CREATE TABLE IF NOT EXISTS connection_audit_events (event_id TEXT PRIMARY KEY, connection_id TEXT NOT NULL, event_json TEXT NOT NULL)")
        self._connection.commit()

    def save_profile(self, profile: ConnectionProfile) -> None:
        data = asdict(profile)
        data["status"] = profile.status.value
        data["capabilities"] = [item.value for item in profile.capabilities]
        for name in ("created_at", "updated_at", "last_tested_at", "last_success_at"):
            data[name] = data[name].isoformat() if data[name] is not None else None
        self._connection.execute("INSERT INTO connection_profiles(connection_id, profile_json) VALUES (?, ?) ON CONFLICT(connection_id) DO UPDATE SET profile_json=excluded.profile_json", (profile.connection_id, json.dumps(data, sort_keys=True)))
        self._connection.commit()

    def get_profile(self, connection_id: str) -> ConnectionProfile | None:
        row = self._connection.execute("SELECT profile_json FROM connection_profiles WHERE connection_id = ?", (connection_id,)).fetchone()
        return _profile(json.loads(row["profile_json"])) if row else None

    def list_profiles(self) -> tuple[ConnectionProfile, ...]:
        return tuple(_profile(json.loads(row["profile_json"])) for row in self._connection.execute("SELECT profile_json FROM connection_profiles ORDER BY connection_id"))

    def append_audit(self, event: ConnectionAuditEvent) -> None:
        data = asdict(event)
        data["occurred_at"] = event.occurred_at.isoformat()
        try:
            self._connection.execute("INSERT INTO connection_audit_events(event_id, connection_id, event_json) VALUES (?, ?, ?)", (event.event_id, event.connection_id, json.dumps(data, sort_keys=True)))
        except sqlite3.IntegrityError as error:
            raise ValueError("Connection audit event IDs are immutable.") from error
        self._connection.commit()

    def audit_events(self, connection_id: str) -> tuple[ConnectionAuditEvent, ...]:
        return tuple(_event(json.loads(row["event_json"])) for row in self._connection.execute("SELECT event_json FROM connection_audit_events WHERE connection_id = ? ORDER BY rowid", (connection_id,)))

    def close(self) -> None:
        self._connection.close()


def _profile(data: dict) -> ConnectionProfile:
    return ConnectionProfile(
        **{**data, "status": ConnectionStatus(data["status"]), "capabilities": tuple(ConnectionMode(item) for item in data["capabilities"]),
           "created_at": datetime.fromisoformat(data["created_at"]), "updated_at": datetime.fromisoformat(data["updated_at"]),
           "last_tested_at": datetime.fromisoformat(data["last_tested_at"]) if data["last_tested_at"] else None,
           "last_success_at": datetime.fromisoformat(data["last_success_at"]) if data["last_success_at"] else None,
           "warnings": tuple(data["warnings"])}
    )


def _event(data: dict) -> ConnectionAuditEvent:
    return ConnectionAuditEvent(**{**data, "occurred_at": datetime.fromisoformat(data["occurred_at"])})
