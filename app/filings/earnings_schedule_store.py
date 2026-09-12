"""Dedicated append-only schedule evidence; no production wiring or admission.

Generic BoardMeetingMetadata requires a datetime and cannot preserve DATE_ONLY.
Core API snapshot families have no schedule family. These versioned tables are
therefore deliberately separate, and are created only on explicit construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import sqlite3
from pathlib import Path

from app.filings.earnings_schedule_source import RawSchedule, utc
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.official_earnings_schedule_candidate import (
    CandidateIdentityState, CandidateVerificationState, OfficialEarningsScheduleCandidate,
    PurposeClassification, ReconciliationState, ScheduleEventType, ScheduleLifecycleState,
    SchedulePrecision, SourceExchange, SourceInstrumentIdentifierKind,
    reconcile_visible_schedule_candidates,
)


def _encode(candidate: OfficialEarningsScheduleCandidate) -> str:
    return canonical_json(json.loads(candidate.to_json()) | {"fingerprint": candidate.fingerprint})


def _decode(payload: str) -> OfficialEarningsScheduleCandidate:
    body = json.loads(payload)
    for name, kind in {
        "source_exchange": SourceExchange, "event_type": ScheduleEventType,
        "source_instrument_identifier_kind": SourceInstrumentIdentifierKind,
        "purpose_classification": PurposeClassification, "schedule_precision": SchedulePrecision,
        "revision_state": ScheduleLifecycleState, "verification_state": CandidateVerificationState,
        "identity_state": CandidateIdentityState,
    }.items():
        body[name] = kind(body[name])
    body["scheduled_date"] = date.fromisoformat(body["scheduled_date"])
    for name in ("known_at", "exchange_received_at", "exchange_disseminated_at", "hsi_received_at"):
        body[name] = datetime.fromisoformat(body[name]) if body[name] is not None else None
    return OfficialEarningsScheduleCandidate(**body)


@dataclass(frozen=True, slots=True)
class EffectiveSchedule:
    instrument: str
    as_of: datetime
    state: str
    candidates: tuple[OfficialEarningsScheduleCandidate, ...]
    lineage_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    gate_eligible: bool = False

    def __post_init__(self):
        if self.gate_eligible is not False:
            raise ValueError("EARNINGS_SCHEDULE_GATE_ADMISSION_FORBIDDEN")

    def to_json(self) -> str:
        body = {"instrument": self.instrument, "as_of": self.as_of, "state": self.state,
                "candidates": tuple(_encode(c) for c in self.candidates),
                "lineage_ids": self.lineage_ids, "conflict_ids": self.conflict_ids, "gate_eligible": False}
        return canonical_json(body | {"fingerprint": content_fingerprint(body)})


class SQLiteEarningsScheduleStore:
    def __init__(self, path: str | Path):
        self._connection = sqlite3.connect(path)
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS earnings_schedule_candidates_v1 (
                schedule_id TEXT PRIMARY KEY, instrument TEXT NOT NULL,
                exchange TEXT NOT NULL, filing_id TEXT NOT NULL,
                known_at TEXT NOT NULL, payload TEXT NOT NULL, raw_payload TEXT NOT NULL,
                UNIQUE(exchange, filing_id));
            CREATE TABLE IF NOT EXISTS earnings_schedule_conflicts_v1 (
                conflict_id TEXT PRIMARY KEY, original_id TEXT NOT NULL
                    REFERENCES earnings_schedule_candidates_v1(schedule_id),
                known_at TEXT NOT NULL, payload TEXT NOT NULL, raw_payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS earnings_schedule_coverage_v1 (
                fingerprint TEXT PRIMARY KEY, payload TEXT NOT NULL);
        """)

    def close(self):
        self._connection.close()

    def get(self, schedule_id: str) -> OfficialEarningsScheduleCandidate | None:
        row = self._connection.execute("SELECT payload,raw_payload FROM earnings_schedule_candidates_v1 WHERE schedule_id=?", (schedule_id,)).fetchone()
        if row is None:
            return None
        value = _decode(row[0])
        source = self._raw(row[1])
        self._verify_source(value, source)
        if value.schedule_id != schedule_id:
            raise ValueError("EARNINGS_STORAGE_IDENTITY_TAMPERED")
        return value

    @staticmethod
    def _raw(payload: str) -> RawSchedule:
        body = json.loads(payload)
        return RawSchedule(SourceExchange(body["exchange"]), body["reference"],
                           tuple(tuple(x) for x in body["raw"]), body["parser_version"])

    @staticmethod
    def _verify_source(value, source):
        value.__post_init__()
        source.__post_init__()
        if (value.source_fingerprint != source.fingerprint or value.source_exchange != source.exchange
                or value.source_reference != source.reference
                or value.source_filing_identity != (source.field("filing_identity") or source.field("link") or source.reference)):
            raise ValueError("EARNINGS_SOURCE_LINEAGE_MISMATCH")
        if value.revision_state != ScheduleLifecycleState.ANNOUNCED:
            if (value.revision_state == ScheduleLifecycleState.COMPLETED
                    or source.field("revision_of_schedule_id") != value.revision_of_schedule_id
                    or source.field("lifecycle") != value.revision_state.value):
                raise ValueError("REVISION_LINEAGE_UNRESOLVED")

    def save(self, value: OfficialEarningsScheduleCandidate, *, source: RawSchedule) -> str:
        """Retain first observation; replay ignores only HSI retrieval time.

        A conflicting filing identity is quarantined as immutable incoming
        evidence. It blocks the old record from conflict observation onward.
        It never replaces or repairs either source record.
        """
        self._verify_source(value, source)
        payload, raw = _encode(value), canonical_json(source)
        with self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            old = self._connection.execute("SELECT schedule_id FROM earnings_schedule_candidates_v1 WHERE exchange=? AND filing_id=?", (value.source_exchange.value, value.source_filing_identity)).fetchone()
            if old:
                original = self.get(old[0])
                old_body, new_body = json.loads(_encode(original)), json.loads(payload)
                for name in ("hsi_received_at", "fingerprint"):
                    old_body.pop(name)
                    new_body.pop(name)
                if old_body == new_body:
                    return "IDENTICAL"
                # Operational conflict discovery is not backdated to a changed
                # source's claimed announcement time.
                conflict_id = content_fingerprint({"original": old[0], "incoming": new_body})
                self._connection.execute("INSERT OR IGNORE INTO earnings_schedule_conflicts_v1 VALUES (?,?,?,?,?)", (conflict_id, old[0], value.hsi_received_at.isoformat(), payload, raw))
                return "EVIDENCE_CONFLICTED"
            if value.revision_of_schedule_id:
                parent = self.get(value.revision_of_schedule_id)
                if (parent is None or parent.canonical_instrument_id != value.canonical_instrument_id
                        or parent.source_exchange != value.source_exchange or parent.known_at >= value.known_at
                        or parent.revision_state in {ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED}):
                    raise ValueError("REVISION_LINEAGE_UNRESOLVED")
            self._connection.execute("INSERT INTO earnings_schedule_candidates_v1 VALUES (?,?,?,?,?,?,?)",
                                     (value.schedule_id, value.canonical_instrument_id, value.source_exchange.value,
                                      value.source_filing_identity, value.known_at.isoformat(), payload, raw))
        return "INSERTED"

    def save_coverage(self, receipt: str) -> str:
        body = json.loads(receipt)
        supplied = body.pop("fingerprint")
        if supplied != content_fingerprint(body) or body.get("gate6_clearance") is not False:
            raise ValueError("EARNINGS_COVERAGE_FINGERPRINT_INVALID")
        encoded = canonical_json(body | {"fingerprint": supplied})
        with self._connection:
            existing = self._connection.execute("SELECT payload FROM earnings_schedule_coverage_v1 WHERE fingerprint=?", (supplied,)).fetchone()
            if existing:
                if existing[0] != encoded:
                    raise ValueError("EARNINGS_COVERAGE_TAMPERED")
                return "IDENTICAL"
            self._connection.execute("INSERT INTO earnings_schedule_coverage_v1 VALUES (?,?)", (supplied, encoded))
        return "INSERTED"

    def effective_schedule_as_of(self, instrument: str, as_of: datetime) -> EffectiveSchedule:
        point = utc(as_of)
        rows = self._connection.execute("SELECT schedule_id FROM earnings_schedule_candidates_v1 WHERE instrument=? AND known_at<=? ORDER BY schedule_id", (instrument, point.isoformat())).fetchall()
        values = tuple(self.get(row[0]) for row in rows)
        if any(v.canonical_instrument_id != instrument or not v.visible_at(point) for v in values):
            raise ValueError("EARNINGS_STORAGE_INDEX_TAMPERED")
        ids = {v.schedule_id for v in values}
        children = {}
        for value in values:
            if value.revision_of_schedule_id:
                if value.revision_of_schedule_id not in ids:
                    raise ValueError("REVISION_LINEAGE_UNRESOLVED")
                children.setdefault(value.revision_of_schedule_id, []).append(value.schedule_id)
        conflicts = []
        for conflict_id, original_id, payload, raw in self._connection.execute(
                "SELECT conflict_id,original_id,payload,raw_payload FROM earnings_schedule_conflicts_v1 WHERE known_at<=? ORDER BY conflict_id", (point.isoformat(),)):
            if original_id in ids:
                incoming = _decode(payload)
                self._verify_source(incoming, self._raw(raw))
                body = json.loads(_encode(incoming))
                body.pop("hsi_received_at")
                body.pop("fingerprint")
                if conflict_id != content_fingerprint({"original": original_id, "incoming": body}):
                    raise ValueError("EARNINGS_CONFLICT_TAMPERED")
                conflicts.append(conflict_id)
        effective = tuple(v for v in values if v.schedule_id not in children)
        view = reconcile_visible_schedule_candidates(effective, as_of=point)
        state = view.state.value
        if conflicts or any(len(x) > 1 for x in children.values()):
            state = ReconciliationState.EVIDENCE_CONFLICTED.value
        elif effective and all(v.revision_state == ScheduleLifecycleState.CANCELLED for v in effective):
            state = "CANCELLED_CANDIDATE"
        elif any(v.revision_state == ScheduleLifecycleState.SUPERSEDED for v in effective):
            state = "REVISION_LINEAGE_UNRESOLVED"
        return EffectiveSchedule(instrument, point, state, effective, tuple(sorted(ids)), tuple(conflicts))
