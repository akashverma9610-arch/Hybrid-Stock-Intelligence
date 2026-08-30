from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.models import (
    AsOfSnapshot,
    DataQuality,
    DerivedObservationMetadata,
    Evidence,
    Freshness,
    FreshnessStatus,
    Instrument,
    MarketObservation,
    ObservationKind,
    Provenance,
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)
from app.storage.repository import MarketDataRepository


class SQLiteMarketDataRepository(MarketDataRepository):
    """SQLite local-development adapter. Business rules stay outside this class."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        # API route handlers may execute in a worker thread while the local
        # application composition creates its repository on the startup thread.
        # SQLite remains the same local connection and all immutable write
        # checks stay in the repository; this only makes that composition safe.
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._create_schema()

    def close(self) -> None:
        self._connection.close()

    def save_instrument(self, instrument: Instrument) -> None:
        self._connection.execute(
            """INSERT INTO instruments (id, symbol, exchange, isin) VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET symbol=excluded.symbol, exchange=excluded.exchange, isin=excluded.isin""",
            (instrument.id, instrument.symbol, instrument.exchange, instrument.isin),
        )
        self._connection.commit()

    def observation_ids(self) -> set[str]:
        return {row["observation_id"] for row in self._connection.execute("SELECT observation_id FROM observations")}

    def save_observation(self, observation: MarketObservation) -> int:
        if observation.validation is None:
            raise ValueError("An observation must have an explicit validation result before persistence.")
        cursor = self._connection.execute(
            """INSERT INTO observations
               (observation_id, instrument_id, kind, payload_json, provenance_json, derivation_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                observation.id,
                observation.instrument.id,
                str(observation.kind),
                _json_dumps(dict(observation.payload)),
                _json_dumps(_provenance_to_dict(observation.provenance)),
                _json_dumps(_derivation_to_dict(observation.derivation)) if observation.derivation else None,
            ),
        )
        record_key = int(cursor.lastrowid)
        validation = observation.validation
        self._connection.execute(
            """INSERT INTO validation_results
               (observation_record_key, status, validated_timestamp, freshness_json, issues_json)
               VALUES (?, ?, ?, ?, ?)""",
            (
                record_key,
                str(validation.status),
                _timestamp(validation.validated_timestamp),
                _json_dumps(_freshness_to_dict(validation.freshness)) if validation.freshness else None,
                _json_dumps([{"field": issue.field, "message": issue.message} for issue in validation.issues]),
            ),
        )
        self._connection.commit()
        return record_key

    def eligible_observations_as_of(self, as_of_timestamp: datetime) -> tuple[tuple[int, MarketObservation], ...]:
        rows = self._connection.execute(
            """SELECT o.*, v.status, v.validated_timestamp, v.freshness_json, v.issues_json, i.symbol, i.exchange, i.isin
               FROM observations o
               JOIN validation_results v ON v.observation_record_key = o.record_key
               JOIN instruments i ON i.id = o.instrument_id
               WHERE v.status = ?
                 AND json_extract(o.provenance_json, '$.market_timestamp') <= ?
                 AND json_extract(o.provenance_json, '$.retrieved_timestamp') <= ?
               ORDER BY i.symbol, json_extract(o.provenance_json, '$.market_timestamp'), o.observation_id, o.record_key""",
            (ValidationStatus.VALID.value, _timestamp(as_of_timestamp), _timestamp(as_of_timestamp)),
        ).fetchall()
        return tuple((int(row["record_key"]), self._observation_from_row(row)) for row in rows)

    def save_evidence(self, evidence: Evidence) -> None:
        self._connection.execute(
            """INSERT INTO evidence (id, observation_references_json, source, captured_timestamp, description)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET observation_references_json=excluded.observation_references_json,
                 source=excluded.source, captured_timestamp=excluded.captured_timestamp, description=excluded.description""",
            (evidence.id, _json_dumps(list(evidence.observation_references)), evidence.source, _timestamp(evidence.captured_timestamp), evidence.description),
        )
        self._connection.commit()

    def save_snapshot(self, snapshot: AsOfSnapshot, record_keys: tuple[int, ...]) -> None:
        self._connection.execute(
            """INSERT INTO snapshots (id, as_of_timestamp, created_timestamp, inclusion_policy)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET as_of_timestamp=excluded.as_of_timestamp,
                 created_timestamp=excluded.created_timestamp, inclusion_policy=excluded.inclusion_policy""",
            (snapshot.id, _timestamp(snapshot.as_of_timestamp), _timestamp(snapshot.created_timestamp), snapshot.inclusion_policy),
        )
        self._connection.execute("DELETE FROM snapshot_observations WHERE snapshot_id = ?", (snapshot.id,))
        self._connection.executemany(
            "INSERT INTO snapshot_observations (snapshot_id, observation_record_key) VALUES (?, ?)",
            ((snapshot.id, record_key) for record_key in record_keys),
        )
        self._connection.commit()

    def get_snapshot(self, snapshot_id: str) -> AsOfSnapshot | None:
        snapshot = self._connection.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
        if snapshot is None:
            return None
        rows = self._connection.execute(
            """SELECT o.*, v.status, v.validated_timestamp, v.freshness_json, v.issues_json, i.symbol, i.exchange, i.isin
               FROM snapshot_observations so
               JOIN observations o ON o.record_key = so.observation_record_key
               JOIN validation_results v ON v.observation_record_key = o.record_key
               JOIN instruments i ON i.id = o.instrument_id
               WHERE so.snapshot_id = ?
               ORDER BY i.symbol, json_extract(o.provenance_json, '$.market_timestamp'), o.observation_id, o.record_key""",
            (snapshot_id,),
        ).fetchall()
        return AsOfSnapshot(
            id=snapshot["id"],
            as_of_timestamp=_parse_timestamp(snapshot["as_of_timestamp"]),
            created_timestamp=_parse_timestamp(snapshot["created_timestamp"]),
            inclusion_policy=snapshot["inclusion_policy"],
            observations=tuple(self._observation_from_row(row) for row in rows),
        )

    def append_audit_event(self, event_type: str, occurred_timestamp: datetime, details: str) -> None:
        self._connection.execute(
            "INSERT INTO audit_events (event_type, occurred_timestamp, details) VALUES (?, ?, ?)",
            (event_type, _timestamp(occurred_timestamp), details),
        )
        self._connection.commit()

    def audit_event_count(self) -> int:
        return int(self._connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0])

    def _observation_from_row(self, row: sqlite3.Row) -> MarketObservation:
        provenance_data = json.loads(row["provenance_json"])
        freshness_data = json.loads(row["freshness_json"]) if row["freshness_json"] else None
        issues_data = json.loads(row["issues_json"])
        validation = ValidationResult(
            status=ValidationStatus(row["status"]),
            validated_timestamp=_parse_timestamp(row["validated_timestamp"]),
            freshness=_freshness_from_dict(freshness_data) if freshness_data else None,
            issues=tuple(ValidationIssue(**issue) for issue in issues_data),
        )
        derivation_data = json.loads(row["derivation_json"]) if row["derivation_json"] else None
        derivation = _derivation_from_dict(derivation_data) if derivation_data else None
        return MarketObservation(
            id=row["observation_id"],
            instrument=Instrument(row["instrument_id"], row["symbol"], row["exchange"], row["isin"]),
            kind=ObservationKind(row["kind"]),
            payload=json.loads(row["payload_json"]),
            provenance=_provenance_from_dict(provenance_data),
            validation=validation,
            derivation=derivation,
        )

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS instruments (
                id TEXT PRIMARY KEY, symbol TEXT NOT NULL, exchange TEXT NOT NULL, isin TEXT
            );
            CREATE TABLE IF NOT EXISTS observations (
                record_key INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id TEXT NOT NULL, instrument_id TEXT NOT NULL,
                kind TEXT NOT NULL, payload_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
                derivation_json TEXT, FOREIGN KEY (instrument_id) REFERENCES instruments(id)
            );
            CREATE TABLE IF NOT EXISTS validation_results (
                observation_record_key INTEGER PRIMARY KEY, status TEXT NOT NULL,
                validated_timestamp TEXT NOT NULL, freshness_json TEXT, issues_json TEXT NOT NULL,
                FOREIGN KEY (observation_record_key) REFERENCES observations(record_key)
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id TEXT PRIMARY KEY, observation_references_json TEXT NOT NULL,
                source TEXT NOT NULL, captured_timestamp TEXT NOT NULL, description TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshots (
                id TEXT PRIMARY KEY, as_of_timestamp TEXT NOT NULL,
                created_timestamp TEXT NOT NULL, inclusion_policy TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshot_observations (
                snapshot_id TEXT NOT NULL, observation_record_key INTEGER NOT NULL,
                PRIMARY KEY(snapshot_id, observation_record_key),
                FOREIGN KEY(snapshot_id) REFERENCES snapshots(id),
                FOREIGN KEY(observation_record_key) REFERENCES observations(record_key)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL,
                occurred_timestamp TEXT NOT NULL, details TEXT NOT NULL
            );
            """
        )
        self._connection.commit()


def deterministic_snapshot_id(as_of_timestamp: datetime, observations: tuple[MarketObservation, ...], policy: str) -> str:
    fingerprint = "|".join(
        [
            _timestamp(as_of_timestamp),
            policy,
            *[
                f"{item.id}:{_timestamp(item.provenance.market_timestamp)}:{_timestamp(item.provenance.retrieved_timestamp)}"
                for item in observations
            ],
        ]
    )
    return f"snapshot-{hashlib.sha256(fingerprint.encode()).hexdigest()[:16]}"


def _timestamp(value: datetime | object) -> str:
    if not isinstance(value, datetime):
        raise TypeError("Only validated timezone-aware timestamps may be persisted.")
    return value.isoformat()


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _freshness_to_dict(value: Freshness) -> dict[str, Any]:
    return {
        "status": value.status.value,
        "observed_timestamp": _timestamp(value.observed_timestamp) if value.observed_timestamp else None,
        "evaluated_timestamp": _timestamp(value.evaluated_timestamp),
        "age_seconds": value.age_seconds,
        "maximum_age_seconds": value.maximum_age_seconds,
    }


def _freshness_from_dict(value: dict[str, Any]) -> Freshness:
    return Freshness(
        FreshnessStatus(value["status"]),
        _parse_timestamp(value["observed_timestamp"]) if value["observed_timestamp"] else None,
        _parse_timestamp(value["evaluated_timestamp"]),
        value["age_seconds"],
        value["maximum_age_seconds"],
    )


def _provenance_to_dict(value: Provenance) -> dict[str, Any]:
    return {
        "source": value.source,
        "source_identifier": value.source_identifier,
        "market_timestamp": _timestamp(value.market_timestamp),
        "retrieved_timestamp": _timestamp(value.retrieved_timestamp),
        "data_quality": value.data_quality.value,
        "original_record": value.original_record,
    }


def _provenance_from_dict(value: dict[str, Any]) -> Provenance:
    return Provenance(
        source=value["source"], source_identifier=value["source_identifier"],
        market_timestamp=_parse_timestamp(value["market_timestamp"]),
        retrieved_timestamp=_parse_timestamp(value["retrieved_timestamp"]),
        data_quality=DataQuality(value["data_quality"]), original_record=value.get("original_record"),
    )


def _derivation_to_dict(value: DerivedObservationMetadata) -> dict[str, Any]:
    return {
        "input_references": list(value.input_references), "calculation_name": value.calculation_name,
        "parameters": dict(value.parameters), "calculation_version": value.calculation_version,
        "derived_timestamp": _timestamp(value.derived_timestamp),
    }


def _derivation_from_dict(value: dict[str, Any]) -> DerivedObservationMetadata:
    return DerivedObservationMetadata(
        tuple(value["input_references"]), value["calculation_name"], value["parameters"],
        value["calculation_version"], _parse_timestamp(value["derived_timestamp"]),
    )
