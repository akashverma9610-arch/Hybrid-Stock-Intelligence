"""Immutable SQLite persistence for the V1B external-intelligence boundary."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.intelligence.external_intelligence import (
    EvidenceVersion,
    ExternalEvent,
    ReevaluationRequest,
    canonical,
    digest,
)
from app.intelligence.external_intelligence_serialization import (
    event_from_canonical_payload,
    evidence_version_from_canonical_payload,
    reevaluation_request_from_canonical_payload,
)
from app.storage.sqlite_repository import SQLiteMarketDataRepository, _timestamp


class SQLiteExternalIntelligenceRepository(SQLiteMarketDataRepository):
    """Append-only V1B2 records, isolated from News, Brain, and trading flows."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        super().__init__(database_path)
        self._transaction_depth = 0
        self._create_external_intelligence_schema()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Compose immutable writes atomically without exposing update operations."""
        outermost = self._transaction_depth == 0
        if outermost:
            self._connection.execute("BEGIN")
        self._transaction_depth += 1
        try:
            yield
        except Exception:
            if outermost:
                self._connection.rollback()
            raise
        else:
            if outermost:
                self._connection.commit()
        finally:
            self._transaction_depth -= 1

    def save_event(self, value: ExternalEvent) -> ExternalEvent:
        payload = canonical(value)
        existing = self.get_event(value.canonical_event_id)
        if existing is not None:
            return self._same_or_conflict(existing, payload, "Canonical external-intelligence events are immutable.")
        producer_match = self.get_event_by_producer_identity(value.producer_id, value.producer_event_id)
        if producer_match is not None:
            raise ValueError("Producer event identity cannot map to multiple canonical events.")
        try:
            self._connection.execute(
                """INSERT INTO external_intelligence_events (
                   canonical_event_id, producer_id, producer_event_id, schema_version,
                   stable_event_fingerprint, canonical_payload_json, first_received_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (value.canonical_event_id, value.producer_id, value.producer_event_id, value.schema_version,
                 value.fingerprint, payload, _timestamp(value.first_received_at)),
            )
            self._commit_if_not_in_transaction()
        except sqlite3.IntegrityError as error:
            self._rollback_if_not_in_transaction()
            raise ValueError("Canonical external-intelligence events are immutable.") from error
        return value

    def get_event(self, canonical_event_id: str) -> ExternalEvent | None:
        row = self._connection.execute(
            "SELECT * FROM external_intelligence_events WHERE canonical_event_id = ?", (canonical_event_id,),
        ).fetchone()
        return self._event_from_row(row) if row is not None else None

    def get_event_by_producer_identity(self, producer_id: str, producer_event_id: str) -> ExternalEvent | None:
        row = self._connection.execute(
            """SELECT * FROM external_intelligence_events
               WHERE producer_id = ? AND producer_event_id = ?""",
            (producer_id, producer_event_id),
        ).fetchone()
        return self._event_from_row(row) if row is not None else None

    def save_evidence_version(self, value: EvidenceVersion) -> EvidenceVersion:
        payload = canonical(value)
        existing = self.get_evidence_version(value.evidence_version_id)
        if existing is not None:
            return self._same_or_conflict(existing, payload, "External-intelligence evidence versions are immutable.")
        event = self.get_event(value.event.canonical_event_id)
        if event is None:
            raise ValueError("External-intelligence evidence requires a persisted canonical event.")
        if canonical(event) != canonical(value.event):
            raise ValueError("External-intelligence evidence must reference the exact persisted event.")
        try:
            self._connection.execute(
                """INSERT INTO external_intelligence_evidence_versions (
                   evidence_version_id, canonical_event_id, evidence_fingerprint, payload_fingerprint,
                   received_at, published_at, discovered_at, canonical_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (value.evidence_version_id, value.event.canonical_event_id, value.fingerprint, digest(value),
                 _timestamp(value.received_at), _timestamp(value.published_at), _timestamp(value.discovered_at), payload),
            )
            self._commit_if_not_in_transaction()
        except sqlite3.IntegrityError as error:
            self._rollback_if_not_in_transaction()
            raise ValueError("External-intelligence evidence versions are append-only.") from error
        return value

    def get_evidence_version(self, evidence_version_id: str) -> EvidenceVersion | None:
        row = self._connection.execute(
            "SELECT * FROM external_intelligence_evidence_versions WHERE evidence_version_id = ?", (evidence_version_id,),
        ).fetchone()
        return self._evidence_from_row(row) if row is not None else None

    def list_evidence_versions(self, canonical_event_id: str) -> tuple[EvidenceVersion, ...]:
        rows = self._connection.execute(
            """SELECT * FROM external_intelligence_evidence_versions
               WHERE canonical_event_id = ? ORDER BY received_at, evidence_version_id""",
            (canonical_event_id,),
        ).fetchall()
        return tuple(self._evidence_from_row(row) for row in rows)

    def list_all_evidence_versions(self) -> tuple[EvidenceVersion, ...]:
        """Read immutable evidence in stable PIT order; performs no projection."""
        rows = self._connection.execute(
            "SELECT * FROM external_intelligence_evidence_versions ORDER BY received_at, evidence_version_id",
        ).fetchall()
        return tuple(self._evidence_from_row(row) for row in rows)

    def save_reevaluation_request(self, value: ReevaluationRequest) -> ReevaluationRequest:
        payload = canonical(value)
        existing = self.get_reevaluation_request(value.request_id)
        if existing is not None:
            return self._same_or_conflict(existing, payload, "External-intelligence reevaluation requests are immutable.")
        if self.get_event(value.canonical_event_id) is None:
            raise ValueError("External-intelligence reevaluation requires a persisted canonical event.")
        evidence = self.get_evidence_version(value.evidence_version_id)
        if evidence is None:
            raise ValueError("External-intelligence reevaluation requires a persisted evidence version.")
        if evidence.event.canonical_event_id != value.canonical_event_id:
            raise ValueError("External-intelligence reevaluation evidence must belong to its event.")
        try:
            self._connection.execute(
                """INSERT INTO external_intelligence_reevaluation_requests (
                   request_id, canonical_event_id, evidence_version_id, requested_at,
                   processing_state, canonical_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (value.request_id, value.canonical_event_id, value.evidence_version_id,
                 _timestamp(value.requested_at), value.processing_state.value, payload),
            )
            self._commit_if_not_in_transaction()
        except sqlite3.IntegrityError as error:
            self._rollback_if_not_in_transaction()
            raise ValueError("External-intelligence reevaluation requests are immutable.") from error
        return value

    def get_reevaluation_request(self, request_id: str) -> ReevaluationRequest | None:
        row = self._connection.execute(
            "SELECT * FROM external_intelligence_reevaluation_requests WHERE request_id = ?", (request_id,),
        ).fetchone()
        return self._request_from_row(row) if row is not None else None

    def list_reevaluation_requests(
        self, *, canonical_event_id: str | None = None, evidence_version_id: str | None = None,
    ) -> tuple[ReevaluationRequest, ...]:
        clauses: list[str] = []
        values: list[str] = []
        if canonical_event_id is not None:
            clauses.append("canonical_event_id = ?")
            values.append(canonical_event_id)
        if evidence_version_id is not None:
            clauses.append("evidence_version_id = ?")
            values.append(evidence_version_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"SELECT * FROM external_intelligence_reevaluation_requests{where} ORDER BY requested_at, request_id", values,
        ).fetchall()
        return tuple(self._request_from_row(row) for row in rows)

    def external_intelligence_row_counts(self) -> dict[str, int]:
        return {
            "events": int(self._connection.execute("SELECT COUNT(*) FROM external_intelligence_events").fetchone()[0]),
            "evidence_versions": int(self._connection.execute("SELECT COUNT(*) FROM external_intelligence_evidence_versions").fetchone()[0]),
            "reevaluation_requests": int(self._connection.execute("SELECT COUNT(*) FROM external_intelligence_reevaluation_requests").fetchone()[0]),
        }

    def foreign_key_violations(self) -> tuple[sqlite3.Row, ...]:
        return tuple(self._connection.execute("PRAGMA foreign_key_check").fetchall())

    def sqlite_integrity(self) -> str:
        return str(self._connection.execute("PRAGMA integrity_check").fetchone()[0])

    @staticmethod
    def _same_or_conflict(existing: object, incoming_payload: str, message: str):
        if canonical(existing) != incoming_payload:
            raise ValueError(message)
        return existing

    def _commit_if_not_in_transaction(self) -> None:
        if self._transaction_depth == 0:
            self._connection.commit()

    def _rollback_if_not_in_transaction(self) -> None:
        if self._transaction_depth == 0:
            self._connection.rollback()

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> ExternalEvent:
        value = event_from_canonical_payload(row["canonical_payload_json"])
        if (value.canonical_event_id != row["canonical_event_id"]
                or value.fingerprint != row["stable_event_fingerprint"]
                or canonical(value) != row["canonical_payload_json"]
                or _timestamp(value.first_received_at) != row["first_received_at"]):
            raise ValueError("Stored external-intelligence event failed immutable integrity verification.")
        return value

    @staticmethod
    def _evidence_from_row(row: sqlite3.Row) -> EvidenceVersion:
        value = evidence_version_from_canonical_payload(row["canonical_payload_json"])
        if (value.evidence_version_id != row["evidence_version_id"]
                or value.event.canonical_event_id != row["canonical_event_id"]
                or value.fingerprint != row["evidence_fingerprint"]
                or digest(value) != row["payload_fingerprint"]
                or canonical(value) != row["canonical_payload_json"]
                or _timestamp(value.received_at) != row["received_at"]
                or _timestamp(value.published_at) != row["published_at"]
                or _timestamp(value.discovered_at) != row["discovered_at"]):
            raise ValueError("Stored external-intelligence evidence failed immutable integrity verification.")
        return value

    @staticmethod
    def _request_from_row(row: sqlite3.Row) -> ReevaluationRequest:
        value = reevaluation_request_from_canonical_payload(row["canonical_payload_json"])
        if (value.request_id != row["request_id"]
                or value.canonical_event_id != row["canonical_event_id"]
                or value.evidence_version_id != row["evidence_version_id"]
                or canonical(value) != row["canonical_payload_json"]
                or _timestamp(value.requested_at) != row["requested_at"]
                or value.processing_state.value != row["processing_state"]):
            raise ValueError("Stored external-intelligence reevaluation request failed immutable integrity verification.")
        return value

    def _create_external_intelligence_schema(self) -> None:
        self._connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS external_intelligence_events (
                canonical_event_id TEXT PRIMARY KEY,
                producer_id TEXT NOT NULL,
                producer_event_id TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                stable_event_fingerprint TEXT NOT NULL,
                canonical_payload_json TEXT NOT NULL,
                first_received_at TEXT NOT NULL,
                UNIQUE (producer_id, producer_event_id)
            );
            CREATE TABLE IF NOT EXISTS external_intelligence_evidence_versions (
                evidence_version_id TEXT PRIMARY KEY,
                canonical_event_id TEXT NOT NULL,
                evidence_fingerprint TEXT NOT NULL,
                payload_fingerprint TEXT NOT NULL,
                received_at TEXT NOT NULL,
                published_at TEXT NOT NULL,
                discovered_at TEXT NOT NULL,
                canonical_payload_json TEXT NOT NULL,
                FOREIGN KEY (canonical_event_id) REFERENCES external_intelligence_events(canonical_event_id)
            );
            CREATE TABLE IF NOT EXISTS external_intelligence_reevaluation_requests (
                request_id TEXT PRIMARY KEY,
                canonical_event_id TEXT NOT NULL,
                evidence_version_id TEXT NOT NULL,
                requested_at TEXT NOT NULL,
                processing_state TEXT NOT NULL,
                canonical_payload_json TEXT NOT NULL,
                FOREIGN KEY (canonical_event_id) REFERENCES external_intelligence_events(canonical_event_id),
                FOREIGN KEY (evidence_version_id) REFERENCES external_intelligence_evidence_versions(evidence_version_id)
            );
            """
        )
        self._connection.commit()
