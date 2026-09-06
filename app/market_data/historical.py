"""Provider-neutral historical OHLCV ingestion and dedicated bar storage."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Mapping, Protocol

from app.domain.models import DataQuality
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, ErrorCode, HistoricalBarsRequest,
    InstrumentIdentity, MarketDataError, MarketDataProvenance,
    MarketDataQualityError, MarketDataQualityValidator, ProviderInstrumentMapping,
    Timeframe,
)
from app.market_data.providers import MarketDataProvider
from app.reliability import market_bar_source_priority
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory
from app.market_data.nse_udiff_source_identity import is_udiff, observation_key


class HistoricalCoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class BarWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"


class MarketBarReconciliationStatus(StrEnum):
    MATCH = "MATCH"
    ROUNDING_DIFFERENCE = "ROUNDING_DIFFERENCE"
    VOLUME_DIFFERENCE = "VOLUME_DIFFERENCE"
    ADJUSTMENT_BASIS_DIFFERENT = "ADJUSTMENT_BASIS_DIFFERENT"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    PROVIDER_OBSERVATION_MISSING = "PROVIDER_OBSERVATION_MISSING"
    SOURCE_SERIES_SELECTION_REQUIRED = "SOURCE_SERIES_SELECTION_REQUIRED"


class GapStatus(StrEnum):
    NONE = "NONE"
    POSSIBLE_GAP = "POSSIBLE_GAP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class HistoricalBarCoverage:
    status: HistoricalCoverageStatus
    requested_start: datetime
    requested_end: datetime
    earliest_available: datetime | None
    latest_available: datetime | None
    count: int
    gap_status: GapStatus
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalIngestionReport:
    provider: str
    instrument_id: str
    timeframe: Timeframe
    requested_start: datetime
    requested_end: datetime
    received_count: int
    accepted_count: int
    duplicate_count: int
    conflict_count: int
    rejected_count: int
    gap_count: int
    earliest_bar: datetime | None
    latest_bar: datetime | None
    adjustment_status: AdjustmentStatus
    coverage: HistoricalCoverageStatus
    warnings: tuple[str, ...]
    provenance_references: tuple[str, ...]
    started_at: datetime
    completed_at: datetime


@dataclass(frozen=True, slots=True)
class HistoricalRequestChunk:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class MarketBarReconciliation:
    instrument_id: str
    timeframe: Timeframe
    session_end: datetime
    preferred_provider: str | None
    secondary_provider: str | None
    status: MarketBarReconciliationStatus
    ohlc_difference: tuple[str, ...] = ()
    volume_difference: bool = False


_CONFLICT_VALUE_FIELDS = (
    "open", "high", "low", "close", "volume", "turnover", "trade_count", "adjustment_status",
)


@dataclass(frozen=True, slots=True)
class HistoricalBarNormalizedValues:
    """The complete normalized value set used for same-provider equality."""

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    turnover: Decimal | None
    trade_count: int | None
    adjustment_status: AdjustmentStatus

    @classmethod
    def from_bar(cls, value: CanonicalOHLCVBar) -> "HistoricalBarNormalizedValues":
        return cls(
            value.open, value.high, value.low, value.close, value.volume,
            value.turnover, value.trade_count, value.adjustment_status,
        )


@dataclass(frozen=True, slots=True)
class HistoricalBarLineage:
    """Provider and normalization lineage retained for each side of a conflict."""

    provider_identity: str
    provider_version: str | None
    mapping_version: str | None
    normalizer_version: str | None
    source_identity: str | None
    provider_instrument_reference: str | None
    source_observation_identity: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_identity.strip():
            raise ValueError("Historical conflict lineage requires provider identity.")
        if self.source_observation_identity is not None:
            import re
            if self.provider_identity != "nse_udiff_official" or not re.fullmatch(r"nse-udiff-source-row:[a-f0-9]{64}", self.source_observation_identity):
                raise ValueError("Historical conflict source observation identity is invalid.")


@dataclass(frozen=True, slots=True)
class HistoricalBarConflictArtifact:
    """Immutable evidence of a differing same-provider normalized bar.

    The artifact deliberately records both normalized values but does not make
    either value canonical.  ``detected_at`` and ``ingestion_run_id`` describe
    first observation of a semantic conflict and are not part of its stable
    conflict fingerprint, so a later identical reconciliation is idempotent.
    """

    conflict_fingerprint: str
    canonical_instrument_id: str
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    stored_bar_fingerprint: str
    incoming_bar_fingerprint: str
    stored_values: HistoricalBarNormalizedValues
    incoming_values: HistoricalBarNormalizedValues
    differing_fields: tuple[str, ...]
    stored_lineage: HistoricalBarLineage
    incoming_lineage: HistoricalBarLineage
    detected_at: datetime
    ingestion_run_id: str | None = None

    @classmethod
    def from_bars(
        cls,
        stored: CanonicalOHLCVBar,
        incoming: CanonicalOHLCVBar,
        *,
        detected_at: datetime,
        ingestion_run_id: str | None = None,
    ) -> "HistoricalBarConflictArtifact":
        if _provider_identity(stored) != _provider_identity(incoming):
            raise ValueError("Historical conflict artifacts require the same provider identity.")
        if _bar_key(stored) != _bar_key(incoming):
            raise ValueError("Historical conflict artifacts require the same bar key.")
        if (is_udiff(stored) or is_udiff(incoming)) and observation_key(stored) != observation_key(incoming):
            raise ValueError("UDIFF_DISTINCT_SOURCE_IDENTITIES_ARE_NOT_VALUE_CONFLICTS")
        stored_values = HistoricalBarNormalizedValues.from_bar(stored)
        incoming_values = HistoricalBarNormalizedValues.from_bar(incoming)
        differing = _conflict_differing_fields(stored_values, incoming_values)
        if not differing:
            raise ValueError("Historical conflict artifacts require differing normalized values.")
        stored_lineage = _bar_lineage(stored)
        incoming_lineage = _bar_lineage(incoming)
        stored_fingerprint = _normalized_bar_fingerprint(stored)
        incoming_fingerprint = _normalized_bar_fingerprint(incoming)
        fingerprint = _historical_conflict_fingerprint(
            canonical_instrument_id=stored.instrument.instrument_id,
            timeframe=stored.timeframe,
            start_time=stored.start_time,
            end_time=stored.end_time,
            stored_bar_fingerprint=stored_fingerprint,
            incoming_bar_fingerprint=incoming_fingerprint,
            differing_fields=differing,
            stored_lineage=stored_lineage,
            incoming_lineage=incoming_lineage,
        )
        return cls(
            fingerprint, stored.instrument.instrument_id, stored.timeframe, stored.start_time, stored.end_time,
            stored_fingerprint, incoming_fingerprint, stored_values, incoming_values, differing,
            stored_lineage, incoming_lineage, detected_at, ingestion_run_id,
        )

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id.strip() or not self.conflict_fingerprint.strip():
            raise ValueError("Historical conflict artifact identity is required.")
        _require_aware(self.start_time, "start_time")
        _require_aware(self.end_time, "end_time")
        _require_aware(self.detected_at, "detected_at")
        if self.end_time < self.start_time:
            raise ValueError("Historical conflict artifact cannot end before it starts.")
        if not self.differing_fields or len(set(self.differing_fields)) != len(self.differing_fields):
            raise ValueError("Historical conflict differing fields must be canonical and non-empty.")
        if any(value not in _CONFLICT_VALUE_FIELDS for value in self.differing_fields):
            raise ValueError("Historical conflict artifact has an unsupported differing field.")
        if self.stored_lineage.provider_identity != self.incoming_lineage.provider_identity:
            raise ValueError("Historical conflict artifact provider identities must match.")
        if _conflict_differing_fields(self.stored_values, self.incoming_values) != self.differing_fields:
            raise ValueError("Historical conflict artifact differing fields do not match values.")
        expected = _historical_conflict_fingerprint(
            canonical_instrument_id=self.canonical_instrument_id,
            timeframe=self.timeframe,
            start_time=self.start_time,
            end_time=self.end_time,
            stored_bar_fingerprint=self.stored_bar_fingerprint,
            incoming_bar_fingerprint=self.incoming_bar_fingerprint,
            differing_fields=self.differing_fields,
            stored_lineage=self.stored_lineage,
            incoming_lineage=self.incoming_lineage,
        )
        if self.conflict_fingerprint != expected:
            raise ValueError("Historical conflict artifact fingerprint mismatch.")


@dataclass(frozen=True, slots=True)
class HistoricalChunkPolicy:
    maximum_span: timedelta

    def __post_init__(self) -> None:
        if self.maximum_span <= timedelta():
            raise ValueError("Historical chunk span must be positive.")


class HistoricalBarStore(Protocol):
    def upsert(self, bar: CanonicalOHLCVBar) -> BarWriteOutcome: ...
    def same_provider_bar(self, bar: CanonicalOHLCVBar) -> CanonicalOHLCVBar | None: ...
    def save_conflict_artifact(self, value: HistoricalBarConflictArtifact) -> bool: ...
    def list_conflict_artifacts(self, *, instrument_id: str | None = None) -> tuple[HistoricalBarConflictArtifact, ...]: ...
    def has_conflict_artifact(self, instrument_id: str) -> bool: ...
    def range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]: ...
    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]: ...
    def coverage(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> HistoricalBarCoverage: ...
    def count(self, instrument_id: str, timeframe: Timeframe) -> int: ...
    def raw_count(self, instrument_id: str, timeframe: Timeframe) -> int: ...
    def raw_range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]: ...
    def readiness_evidence(self, instrument_ids: tuple[str, ...], timeframe: Timeframe, *, as_of: datetime | None = None) -> Mapping[str, tuple[int, datetime | None]]: ...


SQLITE_HISTORICAL_BAR_TABLE = "historical_bars"
SQLITE_HISTORICAL_BAR_CONFLICT_TABLE = "historical_bar_conflicts"
SQLITE_PROVIDER_IDENTITY = "provider_identity"
SQLITE_UNKNOWN_EXISTING_SOURCE = "unknown_existing_source"


def sqlite_provider_versioned_historical_bars_schema(table: str = SQLITE_HISTORICAL_BAR_TABLE) -> str:
    """Return the sole local SQLite schema used for raw historical evidence."""
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            instrument_id TEXT NOT NULL, timeframe TEXT NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
            provider_identity TEXT NOT NULL, bar_id TEXT NOT NULL, open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
            volume INTEGER, turnover TEXT, trade_count INTEGER, adjustment_status TEXT NOT NULL,
            instrument_json TEXT NOT NULL, provenance_json TEXT NOT NULL, quality TEXT NOT NULL, warnings_json TEXT NOT NULL,
            PRIMARY KEY (instrument_id, timeframe, start_time, end_time, provider_identity)
        );
    """


def sqlite_historical_bar_conflicts_schema(table: str = SQLITE_HISTORICAL_BAR_CONFLICT_TABLE) -> str:
    """Append-only SQLite ledger for rejected same-provider bar revisions."""
    return f"""
        CREATE TABLE IF NOT EXISTS {table} (
            conflict_fingerprint TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL
        );
    """


def sqlite_series_aware_historical_bars_schema(table: str = SQLITE_HISTORICAL_BAR_TABLE) -> str:
    return sqlite_provider_versioned_historical_bars_schema(table).replace(
        "PRIMARY KEY (instrument_id, timeframe, start_time, end_time, provider_identity)",
        "source_observation_identity TEXT NOT NULL DEFAULT '',\n"
        "            PRIMARY KEY (instrument_id, timeframe, start_time, end_time, provider_identity, source_observation_identity)",
    )


def plan_historical_chunks(request: HistoricalBarsRequest, policy: HistoricalChunkPolicy) -> tuple[HistoricalRequestChunk, ...]:
    """Stable inclusive chunks whose next start follows the canonical timeframe."""
    step = _timeframe_delta(request.timeframe)
    chunks: list[HistoricalRequestChunk] = []
    start = request.start
    while start <= request.end:
        end = min(start + policy.maximum_span, request.end)
        chunks.append(HistoricalRequestChunk(start, end))
        start = end + step
    return tuple(chunks)


class HistoricalIngestionService:
    """Fetches canonical bars, validates them, and persists without analysing them."""

    def __init__(self, provider: MarketDataProvider, store: HistoricalBarStore, *, chunk_policy: HistoricalChunkPolicy | None = None, clock=lambda: datetime.now(UTC)) -> None:
        self._provider, self._store, self._chunk_policy, self._clock = provider, store, chunk_policy, clock

    def ingest(
        self,
        request: HistoricalBarsRequest,
        *,
        ingestion_run_id: str | None = None,
    ) -> HistoricalIngestionReport:
        started = self._clock()
        chunks = plan_historical_chunks(request, self._chunk_policy) if self._chunk_policy else (HistoricalRequestChunk(request.start, request.end),)
        received: list[CanonicalOHLCVBar] = []
        warnings: list[str] = []
        unavailable_chunks = 0
        for chunk in chunks:
            chunk_request = HistoricalBarsRequest(request.instrument, request.timeframe, chunk.start, chunk.end, request.adjustment_preference, request.provider_preference)
            try:
                received.extend(self._provider.get_historical_bars(chunk_request))
            except MarketDataError as error:
                unavailable_chunks += 1
                warnings.append(f"CHUNK_{error.code.value}")
        received_count = len(received)
        accepted = duplicates = conflicts = rejected = 0
        seen: dict[tuple[str, Timeframe, datetime, datetime, str], CanonicalOHLCVBar] = {}
        ordered = sorted(received, key=lambda bar: (bar.start_time, bar.end_time, _bar_content_key(bar), bar.bar_id))
        previous: CanonicalOHLCVBar | None = None
        for bar in ordered:
            key = (*_bar_key(bar), observation_key(bar))
            if bar.instrument.instrument_id != request.instrument.instrument_id or bar.timeframe is not request.timeframe:
                rejected += 1; warnings.append("BAR_REQUEST_MISMATCH"); continue
            if bar.end_time > self._clock():
                rejected += 1; warnings.append("FUTURE_BAR_REJECTED"); continue
            try:
                MarketDataQualityValidator.validate_bar(bar)
            except MarketDataError:
                rejected += 1; warnings.append("BAR_QUALITY_REJECTED"); continue
            duplicate = seen.get(key)
            if duplicate is not None:
                if _same_bar_content(duplicate, bar): duplicates += 1
                else:
                    conflicts += 1
                    warnings.extend(("PROVIDER_BAR_CONFLICT", "PROVIDER_REVISION_CONFLICT"))
                    self._persist_same_provider_conflict(bar, detected_at=self._clock(), ingestion_run_id=ingestion_run_id)
                continue
            if previous is not None and bar.start_time < previous.end_time and not (is_udiff(bar) and is_udiff(previous) and observation_key(bar) != observation_key(previous)):
                rejected += 1; warnings.append("BAR_QUALITY_REJECTED"); continue
            seen[key] = bar
            outcome = self._store.upsert(bar)
            if outcome is BarWriteOutcome.INSERTED: accepted += 1
            elif outcome is BarWriteOutcome.IDENTICAL: duplicates += 1
            else:
                # Store conflicts can only arise for the same provider/session
                # identity.  The prior raw observation remains immutable;
                # callers receive an auditable revision conflict rather than a
                # silent correction.
                conflicts += 1
                warnings.extend(("STORED_BAR_CONFLICT", "PROVIDER_REVISION_CONFLICT"))
                self._persist_same_provider_conflict(bar, detected_at=self._clock(), ingestion_run_id=ingestion_run_id)
            previous = bar
        stored = self._store.range(request.instrument.instrument_id, request.timeframe, request.start, request.end)
        coverage = self._store.coverage(request.instrument.instrument_id, request.timeframe, request.start, request.end)
        if unavailable_chunks == len(chunks): state = HistoricalCoverageStatus.UNAVAILABLE
        elif unavailable_chunks or coverage.status is HistoricalCoverageStatus.PARTIAL: state = HistoricalCoverageStatus.PARTIAL
        elif stored: state = HistoricalCoverageStatus.COMPLETE
        else: state = HistoricalCoverageStatus.UNAVAILABLE
        adjustment = _adjustment_status(stored, request.adjustment_preference)
        return HistoricalIngestionReport(
            provider=request.provider_preference or "PROVIDER_NEUTRAL", instrument_id=request.instrument.instrument_id,
            timeframe=request.timeframe, requested_start=request.start, requested_end=request.end,
            received_count=received_count, accepted_count=accepted, duplicate_count=duplicates,
            conflict_count=conflicts, rejected_count=rejected, gap_count=1 if coverage.gap_status is GapStatus.POSSIBLE_GAP else 0,
            earliest_bar=stored[0].start_time if stored else None, latest_bar=stored[-1].end_time if stored else None,
            adjustment_status=adjustment, coverage=state, warnings=tuple(sorted(set(warnings + list(coverage.warnings)))),
            provenance_references=tuple(sorted({bar.provenance.source_reference or bar.provenance.provider for bar in stored})),
            started_at=started, completed_at=self._clock(),
        )

    def _persist_same_provider_conflict(
        self,
        incoming: CanonicalOHLCVBar,
        *,
        detected_at: datetime,
        ingestion_run_id: str | None,
    ) -> None:
        """Record a conflict only when a persisted same-provider bar exists.

        Cross-provider observations deliberately coexist as separate raw rows,
        and malformed/unknown legacy rows are never reclassified here.
        """
        stored = self._store.same_provider_bar(incoming)
        if stored is None:
            raise RuntimeError("HISTORICAL_CONFLICT_STORED_BAR_UNAVAILABLE")
        if _provider_identity(stored) != _provider_identity(incoming):
            return
        self._store.save_conflict_artifact(
            HistoricalBarConflictArtifact.from_bars(
                stored,
                incoming,
                detected_at=detected_at,
                ingestion_run_id=ingestion_run_id,
            )
        )


class SQLiteHistoricalBarStore:
    """Provider-versioned immutable OHLCV observations with a canonical view.

    Persistent SQLite uses the same provider-versioned raw table as the local
    migration command.  A legacy table remains read-compatible until the
    explicit migration is run, but refuses new writes rather than silently
    coalescing providers under its former four-column primary key.
    """

    _TABLE = SQLITE_HISTORICAL_BAR_TABLE

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        # FastAPI dispatches synchronous read routes through worker threads.
        # This persistent store is already the shared local read boundary, so
        # retain SQLite's normal locking while allowing that one composed store
        # to serve a read in the route's worker thread.
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._legacy_schema = self._has_legacy_schema()
        if not self._legacy_schema:
            self._connection.executescript(sqlite_series_aware_historical_bars_schema(self._TABLE))
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS historical_bars_instrument_time_start_idx "
                "ON historical_bars (instrument_id, timeframe, start_time, end_time)"
            )
        self._connection.executescript(sqlite_historical_bar_conflicts_schema())
        self._connection.commit()
        self._series_schema = "source_observation_identity" in {str(row[1]) for row in self._connection.execute(f"PRAGMA table_info({self._TABLE})")}

    def _has_legacy_schema(self) -> bool:
        columns = self._connection.execute(f"PRAGMA table_info({self._TABLE})").fetchall()
        return bool(columns) and SQLITE_PROVIDER_IDENTITY not in {str(column[1]) for column in columns}

    def _require_provider_versioned_schema(self) -> None:
        if self._legacy_schema:
            raise RuntimeError("SQLITE_PROVIDER_VERSIONED_MIGRATION_REQUIRED")

    def close(self) -> None: self._connection.close()

    def upsert(self, bar: CanonicalOHLCVBar) -> BarWriteOutcome:
        self._require_provider_versioned_schema()
        outcome = self._upsert_without_commit(bar)
        if outcome is BarWriteOutcome.INSERTED:
            self._connection.commit()
        return outcome

    def upsert_many(self, bars: Iterable[CanonicalOHLCVBar]) -> tuple[BarWriteOutcome, ...]:
        """Atomically write independent provider-versioned observations.

        This is a narrowly scoped throughput helper for bounded official-source
        imports.  It intentionally uses the same primary key and content
        comparison as :meth:`upsert`; it neither selects a provider nor
        suppresses a same-provider revision conflict.  Conflict artifacts
        remain the caller's responsibility because they need the ingestion
        receipt's detected-at lineage.
        """
        self._require_provider_versioned_schema()
        outcomes: list[BarWriteOutcome] = []
        try:
            self._connection.execute("BEGIN")
            for bar in bars:
                outcomes.append(self._upsert_without_commit(bar))
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return tuple(outcomes)

    def _upsert_without_commit(self, bar: CanonicalOHLCVBar) -> BarWriteOutcome:
        provider = _provider_identity(bar)
        source_key = observation_key(bar)
        if source_key and not self._series_schema:
            raise RuntimeError("NSE_UDIFF_SERIES_MIGRATION_REQUIRED")
        query = f"SELECT * FROM {self._TABLE} WHERE instrument_id=? AND timeframe=? AND start_time=? AND end_time=? AND provider_identity=?"
        params = (*_key_values(_bar_key(bar)), provider)
        if self._series_schema:
            query += " AND source_observation_identity=?"
            params = (*params, source_key)
        existing = self._connection.execute(query, params).fetchone()
        if existing is not None:
            return BarWriteOutcome.IDENTICAL if _same_bar_content(_bar_from_row(existing), bar) else BarWriteOutcome.CONFLICT
        values = _provider_bar_values(bar, provider)
        if self._series_schema:
            values = (*values, source_key)
        self._connection.execute(f"INSERT INTO {self._TABLE} VALUES ({','.join('?' for _ in values)})", values)
        return BarWriteOutcome.INSERTED

    def same_provider_bar(self, bar: CanonicalOHLCVBar) -> CanonicalOHLCVBar | None:
        self._require_provider_versioned_schema()
        provider = _provider_identity(bar)
        query = f"SELECT * FROM {self._TABLE} WHERE instrument_id=? AND timeframe=? AND start_time=? AND end_time=? AND provider_identity=?"
        params = (*_key_values(_bar_key(bar)), provider)
        if self._series_schema:
            query += " AND source_observation_identity=?"
            params = (*params, observation_key(bar))
        elif is_udiff(bar):
            raise RuntimeError("NSE_UDIFF_SERIES_MIGRATION_REQUIRED")
        row = self._connection.execute(
            query, params,
        ).fetchone()
        return _bar_from_row(row) if row is not None else None

    def save_conflict_artifact(self, value: HistoricalBarConflictArtifact) -> bool:
        existing = self._connection.execute(
            f"SELECT payload_json FROM {SQLITE_HISTORICAL_BAR_CONFLICT_TABLE} WHERE conflict_fingerprint=?",
            (value.conflict_fingerprint,),
        ).fetchone()
        if existing is not None:
            _conflict_artifact_from_payload(str(existing["payload_json"]))
            return False
        self._connection.execute(
            f"INSERT INTO {SQLITE_HISTORICAL_BAR_CONFLICT_TABLE} (conflict_fingerprint,payload_json) VALUES (?,?)",
            (value.conflict_fingerprint, _conflict_artifact_payload(value)),
        )
        self._connection.commit()
        return True

    def list_conflict_artifacts(self, *, instrument_id: str | None = None) -> tuple[HistoricalBarConflictArtifact, ...]:
        rows = self._connection.execute(
            f"SELECT payload_json FROM {SQLITE_HISTORICAL_BAR_CONFLICT_TABLE} ORDER BY conflict_fingerprint"
        ).fetchall()
        values = tuple(_conflict_artifact_from_payload(str(row["payload_json"])) for row in rows)
        return tuple(
            sorted(
                (value for value in values if instrument_id is None or value.canonical_instrument_id == instrument_id),
                key=lambda value: (value.canonical_instrument_id, value.end_time, value.conflict_fingerprint),
            )
        )

    def has_conflict_artifact(self, instrument_id: str) -> bool:
        return bool(self.list_conflict_artifacts(instrument_id=instrument_id))

    def raw_range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        query = f"SELECT * FROM {self._TABLE} WHERE instrument_id=? AND timeframe=? AND start_time>=? AND end_time<=?"
        params: list[str] = [instrument_id, timeframe.value, _timestamp(start), _timestamp(end)]
        if as_of is not None:
            query += " AND end_time<=? AND json_extract(provenance_json, '$.received_at')<=?"; params.extend((_timestamp(as_of), _timestamp(as_of)))
        provider_order = ",provider_identity" if not self._legacy_schema else ""
        rows = self._connection.execute(query + f" ORDER BY start_time,end_time{provider_order},bar_id", params).fetchall()
        return tuple(_bar_from_row(row) for row in rows)

    def range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        return _canonicalise(self.raw_range(instrument_id, timeframe, start, end, as_of=as_of))

    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        if count < 1: raise ValueError("Latest-bar count must be positive.")
        return self.range(instrument_id, timeframe, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC), as_of=as_of)[-count:]

    def coverage(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> HistoricalBarCoverage:
        bars = self.range(instrument_id, timeframe, start, end, as_of=as_of)
        if not bars:
            return HistoricalBarCoverage(HistoricalCoverageStatus.UNAVAILABLE, start, end, None, None, 0, GapStatus.UNKNOWN, ("NO_HISTORICAL_BARS",))
        gap = _detect_gap(bars, timeframe)
        complete = bars[0].start_time <= start and bars[-1].end_time >= end and gap is GapStatus.NONE
        state = HistoricalCoverageStatus.COMPLETE if complete else HistoricalCoverageStatus.PARTIAL
        warning = ("POSSIBLE_SESSION_AWARE_GAP",) if gap is GapStatus.POSSIBLE_GAP else ()
        return HistoricalBarCoverage(state, start, end, bars[0].start_time, bars[-1].end_time, len(bars), gap, warning)

    def count(self, instrument_id: str, timeframe: Timeframe) -> int:
        return len(self.range(instrument_id, timeframe, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)))

    def raw_count(self, instrument_id: str, timeframe: Timeframe) -> int:
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {self._TABLE} WHERE instrument_id=? AND timeframe=?", (instrument_id, timeframe.value)).fetchone()[0])

    def range_many(self, instrument_ids: tuple[str, ...], timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> Mapping[str, tuple[CanonicalOHLCVBar, ...]]:
        return {instrument_id: self.range(instrument_id, timeframe, start, end, as_of=as_of) for instrument_id in instrument_ids}

    def readiness_evidence(self, instrument_ids: tuple[str, ...], timeframe: Timeframe, *, as_of: datetime | None = None) -> Mapping[str, tuple[int, datetime | None]]:
        """Return count/latest facts in one query for stored readiness only.

        Count distinct eligible session ends without materialising all bars.
        UDiFF intervals are excluded pending a governed series-selection policy,
        including implicit fallback observations for those same intervals.
        """
        values = tuple(sorted(set(instrument_ids)))
        if not values:
            return {}
        placeholders = ",".join("?" for _ in values)
        query = f"SELECT instrument_id,end_time FROM {self._TABLE} WHERE timeframe=? AND instrument_id IN ({placeholders})"
        params: list[object] = [timeframe.value, *values]
        if as_of is not None:
            query += " AND end_time<=? AND json_extract(provenance_json, '$.received_at')<=?"
            params.extend((_timestamp(as_of), _timestamp(as_of)))
        query += " GROUP BY instrument_id,start_time,end_time"
        if not self._legacy_schema:
            query += " HAVING MAX(CASE WHEN provider_identity='nse_udiff_official' THEN 1 ELSE 0 END)=0"
        query = "SELECT instrument_id,COUNT(DISTINCT end_time) AS session_count,MAX(end_time) AS latest_end FROM (" + query + ") GROUP BY instrument_id"
        rows = self._connection.execute(query, params).fetchall()
        return {str(row["instrument_id"]): (int(row["session_count"]), datetime.fromisoformat(str(row["latest_end"]))) for row in rows}


class PostgreSQLHistoricalBarStore:
    """PostgreSQL implementation using NUMERIC and timezone-aware timestamps."""

    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL:
            raise ValueError("PostgreSQL historical bars require DATABASE_BACKEND=postgresql.")
        self._connections = connections

    def upsert(self, bar: CanonicalOHLCVBar) -> BarWriteOutcome:
        provider = _provider_identity(bar)
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json,source_observation_identity FROM historical_bar_observations WHERE instrument_id=%s AND timeframe=%s AND start_time=%s AND end_time=%s AND provider_identity=%s AND source_observation_identity=%s", (*_key_values(_bar_key(bar)), provider, observation_key(bar)))
                row = cursor.fetchone()
                if row: return BarWriteOutcome.IDENTICAL if _same_bar_content(_bar_from_pg_row(row), bar) else BarWriteOutcome.CONFLICT
                cursor.execute("""INSERT INTO historical_bar_observations (instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json,source_observation_identity) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s)""", (*_provider_bar_values(bar, provider, postgresql=True), observation_key(bar)))
        return BarWriteOutcome.INSERTED

    def same_provider_bar(self, bar: CanonicalOHLCVBar) -> CanonicalOHLCVBar | None:
        provider = _provider_identity(bar)
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json,source_observation_identity FROM historical_bar_observations WHERE instrument_id=%s AND timeframe=%s AND start_time=%s AND end_time=%s AND provider_identity=%s AND source_observation_identity=%s",
                    (*_key_values(_bar_key(bar)), provider, observation_key(bar)),
                )
                row = cursor.fetchone()
        return _bar_from_pg_row(row) if row is not None else None

    def save_conflict_artifact(self, value: HistoricalBarConflictArtifact) -> bool:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO historical_bar_conflicts (conflict_fingerprint,payload_json) VALUES (%s,%s::jsonb) ON CONFLICT (conflict_fingerprint) DO NOTHING RETURNING conflict_fingerprint",
                    (value.conflict_fingerprint, _conflict_artifact_payload(value)),
                )
                return cursor.fetchone() is not None

    def list_conflict_artifacts(self, *, instrument_id: str | None = None) -> tuple[HistoricalBarConflictArtifact, ...]:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM historical_bar_conflicts ORDER BY conflict_fingerprint")
                rows = cursor.fetchall()
        values = tuple(_conflict_artifact_from_payload(row[0]) for row in rows)
        return tuple(
            sorted(
                (value for value in values if instrument_id is None or value.canonical_instrument_id == instrument_id),
                key=lambda value: (value.canonical_instrument_id, value.end_time, value.conflict_fingerprint),
            )
        )

    def has_conflict_artifact(self, instrument_id: str) -> bool:
        return bool(self.list_conflict_artifacts(instrument_id=instrument_id))

    def raw_range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        query="SELECT instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json,source_observation_identity FROM historical_bar_observations WHERE instrument_id=%s AND timeframe=%s AND start_time>=%s AND end_time<=%s"; params:list[object]=[instrument_id,timeframe.value,start,end]
        if as_of is not None: query+=" AND end_time<=%s AND (provenance_json->>'received_at')::timestamptz<=%s";params.extend((as_of,as_of))
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute(query+" ORDER BY start_time,end_time,provider_identity,bar_id",params);rows=cursor.fetchall()
        return tuple(_bar_from_pg_row(row) for row in rows)

    def range(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        return _canonicalise(self.raw_range(instrument_id, timeframe, start, end, as_of=as_of))

    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None) -> tuple[CanonicalOHLCVBar, ...]:
        if count < 1: raise ValueError("Latest-bar count must be positive.")
        values=self.range(instrument_id,timeframe,datetime.min.replace(tzinfo=UTC),datetime.max.replace(tzinfo=UTC),as_of=as_of)
        return values[-count:]

    def coverage(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None) -> HistoricalBarCoverage:
        bars=self.range(instrument_id,timeframe,start,end,as_of=as_of)
        if not bars: return HistoricalBarCoverage(HistoricalCoverageStatus.UNAVAILABLE,start,end,None,None,0,GapStatus.UNKNOWN,("NO_HISTORICAL_BARS",))
        gap=_detect_gap(bars,timeframe); return HistoricalBarCoverage(HistoricalCoverageStatus.COMPLETE if bars[0].start_time<=start and bars[-1].end_time>=end and gap is GapStatus.NONE else HistoricalCoverageStatus.PARTIAL,start,end,bars[0].start_time,bars[-1].end_time,len(bars),gap,("POSSIBLE_SESSION_AWARE_GAP",) if gap is GapStatus.POSSIBLE_GAP else ())

    def count(self, instrument_id: str, timeframe: Timeframe) -> int:
        return len(self.range(instrument_id, timeframe, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)))

    def raw_count(self, instrument_id: str, timeframe: Timeframe) -> int:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM historical_bar_observations WHERE instrument_id=%s AND timeframe=%s", (instrument_id, timeframe.value))
                return int(cursor.fetchone()[0])

    def readiness_evidence(self, instrument_ids: tuple[str, ...], timeframe: Timeframe, *, as_of: datetime | None = None) -> Mapping[str, tuple[int, datetime | None]]:
        values = tuple(sorted(set(instrument_ids)))
        if not values:
            return {}
        query = "SELECT instrument_id,end_time FROM historical_bar_observations WHERE timeframe=%s AND instrument_id = ANY(%s)"
        params: list[object] = [timeframe.value, list(values)]
        if as_of is not None:
            query += " AND end_time<=%s AND (provenance_json->>'received_at')::timestamptz<=%s"
            params.extend((as_of, as_of))
        query += " GROUP BY instrument_id,start_time,end_time HAVING MAX(CASE WHEN provider_identity='nse_udiff_official' THEN 1 ELSE 0 END)=0"
        query = "SELECT instrument_id,COUNT(DISTINCT end_time),MAX(end_time) FROM (" + query + ") AS eligible GROUP BY instrument_id"
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
        return {str(row[0]): (int(row[1]), row[2]) for row in rows}


def _bar_key(bar: CanonicalOHLCVBar) -> tuple[str, Timeframe, datetime, datetime]: return bar.instrument.instrument_id, bar.timeframe, bar.start_time, bar.end_time
def _key_values(key: tuple[str, Timeframe, datetime, datetime]) -> tuple[str, str, str, str]: return key[0],key[1].value,_timestamp(key[2]),_timestamp(key[3])
def _timestamp(value: datetime) -> str: return value.astimezone(UTC).isoformat()
def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"Historical conflict {field} must be timezone-aware.")
def _timeframe_delta(timeframe: Timeframe) -> timedelta: return {Timeframe.ONE_MINUTE:timedelta(minutes=1),Timeframe.FIVE_MINUTES:timedelta(minutes=5),Timeframe.FIFTEEN_MINUTES:timedelta(minutes=15),Timeframe.THIRTY_MINUTES:timedelta(minutes=30),Timeframe.SIXTY_MINUTES:timedelta(hours=1),Timeframe.DAILY:timedelta(days=1),Timeframe.WEEKLY:timedelta(days=7)}[timeframe]
def _bar_content_key(value: CanonicalOHLCVBar) -> tuple[str, ...]: return tuple(str(item) for item in (value.open,value.high,value.low,value.close,value.volume,value.turnover,value.trade_count,value.adjustment_status.value))
def _same_bar_content(left: CanonicalOHLCVBar, right: CanonicalOHLCVBar) -> bool:
    if is_udiff(left) or is_udiff(right):
        return (is_udiff(left) and is_udiff(right) and observation_key(left) == observation_key(right)
                and HistoricalBarNormalizedValues.from_bar(left) == HistoricalBarNormalizedValues.from_bar(right)
                and left.provenance.source_reference == right.provenance.source_reference
                and left.provenance.normalization_version == right.provenance.normalization_version
                and tuple(w for w in left.warnings if not w.startswith("NSE_UDIFF_ARTIFACT:"))
                == tuple(w for w in right.warnings if not w.startswith("NSE_UDIFF_ARTIFACT:")))
    return _bar_content_key(left) == _bar_content_key(right)


def _conflict_differing_fields(
    stored: HistoricalBarNormalizedValues,
    incoming: HistoricalBarNormalizedValues,
) -> tuple[str, ...]:
    return tuple(
        field for field in _CONFLICT_VALUE_FIELDS
        if getattr(stored, field) != getattr(incoming, field)
    )


def _bar_lineage(value: CanonicalOHLCVBar) -> HistoricalBarLineage:
    provider = _provider_identity(value)
    mappings = tuple(
        item for item in value.instrument.provider_mappings
        if item.provider.casefold() == provider
    )
    mapping = mappings[0] if len(mappings) == 1 else None
    return HistoricalBarLineage(
        provider_identity=provider,
        provider_version=value.provenance.schema_version or None,
        mapping_version=mapping.mapping_version if mapping else None,
        normalizer_version=value.provenance.normalization_version or None,
        source_identity=value.provenance.source_reference or value.provenance.request_reference or None,
        provider_instrument_reference=value.provenance.provider_instrument_reference or None,
        source_observation_identity=observation_key(value) or None,
    )


def _normalized_values_payload(value: HistoricalBarNormalizedValues) -> dict[str, object]:
    return {
        "open": str(value.open), "high": str(value.high), "low": str(value.low), "close": str(value.close),
        "volume": value.volume, "turnover": str(value.turnover) if value.turnover is not None else None,
        "trade_count": value.trade_count, "adjustment_status": value.adjustment_status.value,
    }


def _lineage_payload(value: HistoricalBarLineage) -> dict[str, object]:
    payload = {
        "provider_identity": value.provider_identity,
        "provider_version": value.provider_version,
        "mapping_version": value.mapping_version,
        "normalizer_version": value.normalizer_version,
        "source_identity": value.source_identity,
        "provider_instrument_reference": value.provider_instrument_reference,
    }
    # Absence preserves every legacy artifact's exact fingerprint/payload.
    if value.source_observation_identity is not None:
        payload["source_observation_identity"] = value.source_observation_identity
    return payload


def _normalized_bar_fingerprint(value: CanonicalOHLCVBar) -> str:
    payload = {
        "instrument_id": value.instrument.instrument_id,
        "timeframe": value.timeframe.value,
        "start_time": _timestamp(value.start_time),
        "end_time": _timestamp(value.end_time),
        "values": _normalized_values_payload(HistoricalBarNormalizedValues.from_bar(value)),
    }
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _historical_conflict_fingerprint(
    *,
    canonical_instrument_id: str,
    timeframe: Timeframe,
    start_time: datetime,
    end_time: datetime,
    stored_bar_fingerprint: str,
    incoming_bar_fingerprint: str,
    differing_fields: tuple[str, ...],
    stored_lineage: HistoricalBarLineage,
    incoming_lineage: HistoricalBarLineage,
) -> str:
    return sha256(_canonical_json({
        "canonical_instrument_id": canonical_instrument_id,
        "timeframe": timeframe.value,
        "start_time": _timestamp(start_time),
        "end_time": _timestamp(end_time),
        "stored_bar_fingerprint": stored_bar_fingerprint,
        "incoming_bar_fingerprint": incoming_bar_fingerprint,
        "differing_fields": list(differing_fields),
        "stored_lineage": _lineage_payload(stored_lineage),
        "incoming_lineage": _lineage_payload(incoming_lineage),
    }).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _conflict_artifact_payload(value: HistoricalBarConflictArtifact) -> str:
    return _canonical_json({
        "conflict_fingerprint": value.conflict_fingerprint,
        "canonical_instrument_id": value.canonical_instrument_id,
        "timeframe": value.timeframe.value,
        "start_time": _timestamp(value.start_time),
        "end_time": _timestamp(value.end_time),
        "stored_bar_fingerprint": value.stored_bar_fingerprint,
        "incoming_bar_fingerprint": value.incoming_bar_fingerprint,
        "stored_values": _normalized_values_payload(value.stored_values),
        "incoming_values": _normalized_values_payload(value.incoming_values),
        "differing_fields": list(value.differing_fields),
        "stored_lineage": _lineage_payload(value.stored_lineage),
        "incoming_lineage": _lineage_payload(value.incoming_lineage),
        "detected_at": _timestamp(value.detected_at),
        "ingestion_run_id": value.ingestion_run_id,
    })


def _conflict_artifact_from_payload(value: str | Mapping[str, object]) -> HistoricalBarConflictArtifact:
    try:
        payload = json.loads(value) if isinstance(value, str) else dict(value)
        def values(name: str) -> HistoricalBarNormalizedValues:
            item = payload[name]
            if not isinstance(item, Mapping): raise ValueError(name)
            return HistoricalBarNormalizedValues(
                Decimal(str(item["open"])), Decimal(str(item["high"])), Decimal(str(item["low"])), Decimal(str(item["close"])),
                int(item["volume"]) if item["volume"] is not None else None,
                Decimal(str(item["turnover"])) if item["turnover"] is not None else None,
                int(item["trade_count"]) if item["trade_count"] is not None else None,
                AdjustmentStatus(str(item["adjustment_status"])),
            )
        def lineage(name: str) -> HistoricalBarLineage:
            item = payload[name]
            if not isinstance(item, Mapping): raise ValueError(name)
            return HistoricalBarLineage(
                str(item["provider_identity"]),
                str(item["provider_version"]) if item["provider_version"] is not None else None,
                str(item["mapping_version"]) if item["mapping_version"] is not None else None,
                str(item["normalizer_version"]) if item["normalizer_version"] is not None else None,
                str(item["source_identity"]) if item["source_identity"] is not None else None,
                str(item["provider_instrument_reference"]) if item["provider_instrument_reference"] is not None else None,
                str(item["source_observation_identity"]) if item.get("source_observation_identity") is not None else None,
            )
        return HistoricalBarConflictArtifact(
            str(payload["conflict_fingerprint"]), str(payload["canonical_instrument_id"]), Timeframe(str(payload["timeframe"])),
            datetime.fromisoformat(str(payload["start_time"])), datetime.fromisoformat(str(payload["end_time"])),
            str(payload["stored_bar_fingerprint"]), str(payload["incoming_bar_fingerprint"]),
            values("stored_values"), values("incoming_values"), tuple(str(item) for item in payload["differing_fields"]),
            lineage("stored_lineage"), lineage("incoming_lineage"),
            datetime.fromisoformat(str(payload["detected_at"])),
            str(payload["ingestion_run_id"]) if payload.get("ingestion_run_id") is not None else None,
        )
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ValueError("HISTORICAL_CONFLICT_ARTIFACT_INVALID") from error
def _adjustment_status(bars: Iterable[CanonicalOHLCVBar], fallback: AdjustmentStatus) -> AdjustmentStatus:
    states={bar.adjustment_status for bar in bars}; return next(iter(states)) if len(states)==1 else AdjustmentStatus.UNKNOWN if states else fallback
def _detect_gap(bars: tuple[CanonicalOHLCVBar, ...], timeframe: Timeframe) -> GapStatus:
    step=_timeframe_delta(timeframe)
    for previous,current in zip(bars,bars[1:]):
        # Weekend/overnight gaps are deliberately uncertain, not automatically corrupt.
        if current.start_time.date()==previous.end_time.date() and current.start_time-previous.end_time > timedelta(): return GapStatus.POSSIBLE_GAP
    return GapStatus.NONE
def _instrument_json(value: InstrumentIdentity) -> str: return json.dumps({"instrument_id":value.instrument_id,"exchange":value.exchange.value,"symbol":value.symbol,"trading_symbol":value.trading_symbol,"isin":value.isin,"series":value.series,"instrument_type":value.instrument_type.value,"name":value.name,"currency":value.currency,"provider_mappings":[{"provider":item.provider,"provider_instrument_reference":item.provider_instrument_reference,"provider_symbol":item.provider_symbol,"mapping_version":item.mapping_version,"provider_exchange_segment":item.provider_exchange_segment} for item in value.provider_mappings]},sort_keys=True,separators=(",",":"))
def _provenance_json(value: MarketDataProvenance) -> str: return json.dumps({"provider":value.provider,"provider_instrument_reference":value.provider_instrument_reference,"exchange_timestamp":_timestamp(value.exchange_timestamp) if value.exchange_timestamp else None,"provider_timestamp":_timestamp(value.provider_timestamp) if value.provider_timestamp else None,"received_at":_timestamp(value.received_at),"normalization_version":value.normalization_version,"request_reference":value.request_reference,"source_reference":value.source_reference,"schema_version":value.schema_version},sort_keys=True,separators=(",",":"))
def _bar_values(bar: CanonicalOHLCVBar, *, postgresql: bool=False) -> tuple[object,...]:
    timestamps=(bar.start_time,bar.end_time) if postgresql else (_timestamp(bar.start_time),_timestamp(bar.end_time)); return (bar.instrument.instrument_id,bar.timeframe.value,*timestamps,bar.bar_id,str(bar.open),str(bar.high),str(bar.low),str(bar.close),bar.volume,str(bar.turnover) if bar.turnover is not None else None,bar.trade_count,bar.adjustment_status.value,_instrument_json(bar.instrument),_provenance_json(bar.provenance),bar.quality.value,json.dumps(bar.warnings,separators=(",",":")))
def _provider_bar_values(bar: CanonicalOHLCVBar, provider: str, *, postgresql: bool=False) -> tuple[object,...]:
    values = _bar_values(bar, postgresql=postgresql)
    return (*values[:4], provider, *values[4:])
def _bar_from_row(row: Mapping[str, object]) -> CanonicalOHLCVBar: return _bar_from_mapping(row)
def _bar_from_pg_row(row: object) -> CanonicalOHLCVBar:
    names=("instrument_id","timeframe","start_time","end_time","provider_identity","bar_id","open","high","low","close","volume","turnover","trade_count","adjustment_status","instrument_json","provenance_json","quality","warnings_json","source_observation_identity")
    return _bar_from_mapping(dict(zip(names,row)))
def _bar_from_mapping(row: Mapping[str, object]) -> CanonicalOHLCVBar:
    instrument_data=_json_object(row["instrument_json"]); provenance_data=_json_object(row["provenance_json"]);
    instrument=InstrumentIdentity(instrument_data["instrument_id"],__import__("app.market_data.models",fromlist=["Exchange"]).Exchange(instrument_data["exchange"]),instrument_data["symbol"],instrument_data["trading_symbol"],instrument_data["isin"],instrument_data["series"],__import__("app.market_data.models",fromlist=["InstrumentType"]).InstrumentType(instrument_data["instrument_type"]),instrument_data["name"],instrument_data["currency"],tuple(ProviderInstrumentMapping(**item) for item in instrument_data["provider_mappings"]))
    parse=lambda value: datetime.fromisoformat(str(value)) if value else None
    # The provider-versioned primary key is authoritative for source selection.
    # A local pre-U06R row retains its original provenance JSON for audit, but
    # is exposed as ``unknown_existing_source`` until it is independently
    # re-ingested; legacy provenance was not a source-authority assertion.
    row_keys = row.keys() if hasattr(row, "keys") else ()
    provider_identity = str(row[SQLITE_PROVIDER_IDENTITY]) if SQLITE_PROVIDER_IDENTITY in row_keys else provenance_data["provider"]
    provider = SQLITE_UNKNOWN_EXISTING_SOURCE if provider_identity == SQLITE_UNKNOWN_EXISTING_SOURCE else provenance_data["provider"]
    provenance=MarketDataProvenance(provider,provenance_data["provider_instrument_reference"],parse(provenance_data["exchange_timestamp"]),parse(provenance_data["provider_timestamp"]),parse(provenance_data["received_at"]),provenance_data["normalization_version"],provenance_data["request_reference"],provenance_data["source_reference"],provenance_data["schema_version"])
    bar = CanonicalOHLCVBar(str(row["bar_id"]),instrument,Timeframe(str(row["timeframe"])),parse(row["start_time"]),parse(row["end_time"]),Decimal(str(row["open"])),Decimal(str(row["high"])),Decimal(str(row["low"])),Decimal(str(row["close"])),int(row["volume"]) if row["volume"] is not None else None,Decimal(str(row["turnover"])) if row["turnover"] is not None else None,int(row["trade_count"]) if row["trade_count"] is not None else None,AdjustmentStatus(str(row["adjustment_status"])),provenance,DataQuality(str(row["quality"])),tuple(_json_value(row["warnings_json"])))
    if "source_observation_identity" in row_keys and row["source_observation_identity"] != observation_key(bar):
        raise ValueError("HISTORICAL_SOURCE_OBSERVATION_IDENTITY_MISMATCH")
    return bar
def _json_value(value: object): return value if isinstance(value,(dict,list,tuple)) else json.loads(str(value))
def _json_object(value: object) -> dict: 
    result=_json_value(value)
    if not isinstance(result,dict): raise ValueError("Stored historical metadata is malformed.")
    return result


def _provider_identity(value: CanonicalOHLCVBar) -> str:
    provider = value.provenance.provider.strip().casefold() if value.provenance.provider else ""
    return provider or "unknown_existing_source"


def resolve_market_bar(values: Iterable[CanonicalOHLCVBar], *, require_volume: bool = False) -> CanonicalOHLCVBar | None:
    """Select one valid, PIT-filtered raw observation via central source policy.

    The function does not modify raw observations.  A provider is ranked only
    after basic bar validity and the requesting contract's completeness checks
    are met; an index bar with no volume therefore remains eligible for a
    close-only technical consumer but not a volume-required consumer.
    """
    values = tuple(values)
    # There is no activated UDiFF technical-series selection policy. Returning
    # another provider here would hide that insufficiency as an implicit fallback.
    if any(is_udiff(value) for value in values):
        return None
    usable: list[CanonicalOHLCVBar] = []
    for value in values:
        try:
            MarketDataQualityValidator.validate_bar(value)
        except MarketDataQualityError:
            continue
        if require_volume and value.volume is None:
            continue
        usable.append(value)
    if not usable:
        return None
    quality = {DataQuality.HIGH: 0, DataQuality.MEDIUM: 1, DataQuality.LOW: 2, DataQuality.UNKNOWN: 3}
    return min(usable, key=lambda item: (
        market_bar_source_priority(item.provenance.provider), quality.get(item.quality, 4),
        item.provenance.received_at, item.bar_id,
    ))


def _canonicalise(values: Iterable[CanonicalOHLCVBar]) -> tuple[CanonicalOHLCVBar, ...]:
    grouped: dict[tuple[str, Timeframe, datetime, datetime], list[CanonicalOHLCVBar]] = {}
    for value in values:
        grouped.setdefault(_bar_key(value), []).append(value)
    selected = (resolve_market_bar(group) for _, group in sorted(grouped.items(), key=lambda item: item[0][2:]))
    return tuple(item for item in selected if item is not None)


def reconcile_market_bars(values: Iterable[CanonicalOHLCVBar]) -> tuple[MarketBarReconciliation, ...]:
    """Produce informational cross-provider comparison records without writes."""
    grouped: dict[tuple[str, Timeframe, datetime], list[CanonicalOHLCVBar]] = {}
    for value in values:
        grouped.setdefault((value.instrument.instrument_id, value.timeframe, value.end_time), []).append(value)
    results: list[MarketBarReconciliation] = []
    for (instrument_id, timeframe, end), group in sorted(grouped.items(), key=lambda item: item[0]):
        if any(is_udiff(item) for item in group):
            results.append(MarketBarReconciliation(instrument_id, timeframe, end, None, None, MarketBarReconciliationStatus.SOURCE_SERIES_SELECTION_REQUIRED))
            continue
        ordered = sorted(group, key=lambda item: (market_bar_source_priority(item.provenance.provider), item.provenance.provider.casefold(), item.bar_id))
        preferred = ordered[0] if ordered else None
        secondary = next((item for item in ordered[1:] if item.provenance.provider.casefold() != preferred.provenance.provider.casefold()), None) if preferred else None
        if preferred is None or secondary is None:
            results.append(MarketBarReconciliation(instrument_id, timeframe, end, preferred.provenance.provider if preferred else None, None, MarketBarReconciliationStatus.PROVIDER_OBSERVATION_MISSING))
            continue
        differences = tuple(name for name in ("open", "high", "low", "close") if getattr(preferred, name) != getattr(secondary, name))
        if preferred.adjustment_status != secondary.adjustment_status:
            status = MarketBarReconciliationStatus.ADJUSTMENT_BASIS_DIFFERENT
        elif not differences and preferred.volume == secondary.volume:
            status = MarketBarReconciliationStatus.MATCH
        elif not differences:
            status = MarketBarReconciliationStatus.VOLUME_DIFFERENCE
        elif _rounding_equivalent(preferred, secondary):
            status = MarketBarReconciliationStatus.ROUNDING_DIFFERENCE
        else:
            status = MarketBarReconciliationStatus.VALUE_MISMATCH
        results.append(MarketBarReconciliation(instrument_id, timeframe, end, preferred.provenance.provider, secondary.provenance.provider, status, differences, preferred.volume != secondary.volume))
    return tuple(results)


def _rounding_equivalent(left: CanonicalOHLCVBar, right: CanonicalOHLCVBar) -> bool:
    # The bounded one-paise tolerance is informational only.  It never changes
    # a bar and does not turn a documented adjustment difference into a match.
    return all(abs(getattr(left, name) - getattr(right, name)) <= Decimal("0.01") for name in ("open", "high", "low", "close"))
