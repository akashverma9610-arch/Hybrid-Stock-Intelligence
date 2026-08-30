"""SQLite persistence for immutable NSE tick-reference observations only."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .repository import TickSizeObservationRepository
from .tick_size import NseTickSizeObservation, TickSizeSourceClass
from .tick_size_serialization import (
    nse_tick_size_observation_from_dict,
    nse_tick_size_observation_to_dict,
)


class SQLiteTickSizeObservationRepository(TickSizeObservationRepository):
    """Durable, insert-only reference-data evidence storage.

    This adapter stores evidence only.  It does not parse source files, select
    authoritative observations, or resolve a tick size for a requested date.
    """

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute(
            """CREATE TABLE IF NOT EXISTS nse_tick_size_observations (
                id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL
            )"""
        )
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def save_tick_size_observation(self, value: NseTickSizeObservation) -> None:
        payload_json = _json(nse_tick_size_observation_to_dict(value))
        try:
            self._connection.execute(
                "INSERT INTO nse_tick_size_observations (id, payload_json) VALUES (?, ?)",
                (value.record_id, payload_json),
            )
            self._connection.commit()
        except sqlite3.IntegrityError as error:
            raise ValueError("NSE tick-size observations are immutable and cannot be overwritten.") from error

    def get_tick_size_observation(self, record_id: str) -> NseTickSizeObservation | None:
        row = self._connection.execute(
            "SELECT payload_json FROM nse_tick_size_observations WHERE id = ?", (record_id,)
        ).fetchone()
        return _from_row(row) if row else None

    def list_tick_size_observations(
        self,
        canonical_instrument_id: str | None = None,
        source_class: TickSizeSourceClass | None = None,
    ) -> tuple[NseTickSizeObservation, ...]:
        rows = self._connection.execute(
            "SELECT payload_json FROM nse_tick_size_observations"
        ).fetchall()
        values = tuple(_from_row(row) for row in rows)
        filtered = (
            value
            for value in values
            if (canonical_instrument_id is None or value.canonical_instrument_id == canonical_instrument_id)
            and (source_class is None or value.source_class is source_class)
        )
        return tuple(sorted(filtered, key=lambda value: (value.eligible_from, value.observed_at, value.record_id)))


def _json(value: dict[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _from_row(row: sqlite3.Row) -> NseTickSizeObservation:
    payload = json.loads(row["payload_json"])
    if not isinstance(payload, dict):
        raise ValueError("NSE_TICK_SERIALIZATION_INVALID")
    return nse_tick_size_observation_from_dict(payload)
