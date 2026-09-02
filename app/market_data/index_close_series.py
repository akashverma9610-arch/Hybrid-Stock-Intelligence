"""Immutable, provider-neutral daily index close-series evidence.

This module is intentionally narrower than ``historical.py``.  It preserves
official close-only index observations without pretending that absent OHLC
fields are valid price bars.  Consumers can use it only where a close series
is sufficient (currently sector relative strength).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable, Protocol, Sequence
from zoneinfo import ZoneInfo

import requests

from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


NSE_INDICES_OFFICIAL = "NSE_INDICES_OFFICIAL"
NSE_INDICES_HISTORICAL_URL = "https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString"
NSE_INDICES_HISTORICAL_PAGE = "https://www.niftyindices.com/reports/historical-data"
PARSER_VERSION = "nse-indices-historical-close-v1"
_IST = ZoneInfo("Asia/Kolkata")
_NSE_CLOSE = time(15, 30)


class IndexCloseWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class CanonicalIndexCloseObservation:
    """One official index close, with no synthetic OHLC fields."""

    observation_id: str
    canonical_index_id: str
    official_index_name: str
    session: datetime
    close: Decimal
    provider: str
    source_reference: str
    retrieved_at: datetime
    raw_artifact_sha256: str
    parser_version: str
    evidence_fingerprint: str
    raw_unavailable_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.observation_id, self.canonical_index_id, self.official_index_name, self.provider, self.source_reference, self.raw_artifact_sha256, self.parser_version, self.evidence_fingerprint)):
            raise ValueError("INDEX_CLOSE_OBSERVATION_IDENTITY_REQUIRED")
        if self.close <= 0:
            raise ValueError("INDEX_CLOSE_OBSERVATION_CLOSE_MUST_BE_POSITIVE")
        if not _aware(self.session) or not _aware(self.retrieved_at):
            raise ValueError("INDEX_CLOSE_OBSERVATION_TIMESTAMP_MUST_BE_AWARE")
        if self.raw_unavailable_fields != tuple(sorted(set(self.raw_unavailable_fields))):
            raise ValueError("INDEX_CLOSE_OBSERVATION_RAW_FIELDS_NONCANONICAL")
        values = _evidence_values(
            self.canonical_index_id, self.official_index_name, self.session, self.close,
            self.provider, self.source_reference, self.parser_version,
        )
        if self.evidence_fingerprint != _fingerprint(values):
            raise ValueError("INDEX_CLOSE_OBSERVATION_FINGERPRINT_MISMATCH")

    @classmethod
    def create(
        cls, *, canonical_index_id: str, official_index_name: str, session: datetime,
        close: Decimal, retrieved_at: datetime, raw_artifact_sha256: str,
        source_reference: str = NSE_INDICES_HISTORICAL_PAGE,
        raw_unavailable_fields: Sequence[str] = (),
    ) -> "CanonicalIndexCloseObservation":
        values = _evidence_values(
            canonical_index_id, official_index_name, session, close,
            NSE_INDICES_OFFICIAL, source_reference, PARSER_VERSION,
        )
        evidence = _fingerprint(values)
        return cls(
            observation_id=f"canonical-index-close:{evidence[:32]}",
            canonical_index_id=canonical_index_id,
            official_index_name=official_index_name,
            session=session.astimezone(UTC), close=close,
            provider=NSE_INDICES_OFFICIAL, source_reference=source_reference,
            retrieved_at=retrieved_at.astimezone(UTC), raw_artifact_sha256=raw_artifact_sha256,
            parser_version=PARSER_VERSION, evidence_fingerprint=evidence,
            raw_unavailable_fields=tuple(sorted(set(raw_unavailable_fields))),
        )

    def eligible_as_of(self, value: datetime) -> bool:
        """No close is visible before its session close *and* retrieval."""
        return self.session <= value and self.retrieved_at <= value


@dataclass(frozen=True, slots=True)
class OfficialIndexCloseRetrievalArtifact:
    artifact_id: str
    canonical_index_id: str
    official_index_name: str
    source_url: str
    requested_start: str
    requested_end: str
    retrieved_at: datetime
    raw_artifact_sha256: str
    row_count: int
    earliest_session: datetime | None
    latest_session: datetime | None
    parser_version: str
    raw_unavailable_field_counts: tuple[tuple[str, int], ...]
    local_path: str

    def __post_init__(self) -> None:
        if not all((self.artifact_id, self.canonical_index_id, self.official_index_name, self.source_url, self.raw_artifact_sha256, self.parser_version, self.local_path)):
            raise ValueError("INDEX_CLOSE_ARTIFACT_IDENTITY_REQUIRED")
        if not _aware(self.retrieved_at):
            raise ValueError("INDEX_CLOSE_ARTIFACT_RETRIEVED_AT_REQUIRED")


@dataclass(frozen=True, slots=True)
class CloseSeriesPoint:
    """The sole cross-source interface consumed by sector RS."""

    session: datetime
    close: Decimal
    evidence_id: str
    provider: str


@dataclass(frozen=True, slots=True)
class OfficialIndexCloseTargetRun:
    canonical_index_id: str
    official_index_name: str
    sessions_before: int
    sessions_after: int
    earliest_session: datetime | None
    latest_session: datetime | None
    inserted_count: int
    duplicate_count: int
    conflict_count: int
    raw_artifact_sha256: str
    blocker: str | None = None


@dataclass(frozen=True, slots=True)
class OfficialIndexCloseActivationResult:
    requested_at: datetime
    completed_at: datetime
    first_run: tuple[OfficialIndexCloseTargetRun, ...]
    second_run: tuple[OfficialIndexCloseTargetRun, ...]


class IndexCloseSeriesStore(Protocol):
    def save_observation(self, value: CanonicalIndexCloseObservation) -> IndexCloseWriteOutcome: ...
    def save_artifact(self, value: OfficialIndexCloseRetrievalArtifact) -> bool: ...
    def range(self, canonical_index_id: str, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalIndexCloseObservation, ...]: ...


class CoreSnapshotIndexCloseStore:
    """Append-only durable close-series repository using core snapshots."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_artifact(self, value: OfficialIndexCloseRetrievalArtifact) -> bool:
        existing = self._repository.get_snapshot(value.artifact_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("OFFICIAL_INDEX_CLOSE_ARTIFACT_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.artifact_id, CoreApiSnapshotFamily.OFFICIAL_INDEX_CLOSE_ARTIFACT,
            "v1", type(value).__name__, value.raw_artifact_sha256, value.retrieved_at, value,
        ))
        return True

    def save_observation(self, value: CanonicalIndexCloseObservation) -> IndexCloseWriteOutcome:
        peers = tuple(item for item in self._all(CoreApiSnapshotFamily.CANONICAL_INDEX_CLOSE_OBSERVATION)
                      if isinstance(item, CanonicalIndexCloseObservation)
                      and item.canonical_index_id == value.canonical_index_id
                      and item.session == value.session
                      and item.provider == value.provider)
        if not peers:
            self._repository.save_snapshot(CoreApiSnapshot(
                value.observation_id, CoreApiSnapshotFamily.CANONICAL_INDEX_CLOSE_OBSERVATION,
                "v1", type(value).__name__, value.evidence_fingerprint, value.retrieved_at, value,
            ))
            return IndexCloseWriteOutcome.INSERTED
        if any(item.evidence_fingerprint == value.evidence_fingerprint for item in peers):
            return IndexCloseWriteOutcome.IDENTICAL
        return IndexCloseWriteOutcome.CONFLICT

    def range(self, canonical_index_id: str, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalIndexCloseObservation, ...]:
        values = tuple(
            item for item in self._all(CoreApiSnapshotFamily.CANONICAL_INDEX_CLOSE_OBSERVATION)
            if isinstance(item, CanonicalIndexCloseObservation)
            and item.canonical_index_id == canonical_index_id
            and start <= item.session <= end
            and (as_of is None or item.eligible_as_of(as_of))
        )
        # Same-provider session conflicts are deliberately absent from the
        # canonical close view; a caller receives the original observation and
        # the activation reports the conflict explicitly.
        return tuple(sorted(values, key=lambda item: (item.session, item.observation_id)))

    def _all(self, family: CoreApiSnapshotFamily) -> tuple[object, ...]:
        values: list[object] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(item.payload for item in page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


class NseIndicesOfficialCloseClient:
    """Exact official Historical Data client; accepts close-only rows."""

    def __init__(self, *, session: requests.Session | None = None, timeout_seconds: int = 45) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout_seconds

    def fetch(
        self, *, canonical_index_id: str, official_index_name: str,
        requested_start: date, requested_end: date, retrieved_at: datetime,
        artifact_directory: Path,
    ) -> tuple[OfficialIndexCloseRetrievalArtifact, tuple[CanonicalIndexCloseObservation, ...]]:
        if (requested_end - requested_start).days > 365:
            raise ValueError("NSE_INDICES_HISTORICAL_MAXIMUM_RANGE_EXCEEDED")
        cinfo = "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (
            official_index_name.upper(), requested_start.isoformat(), requested_end.isoformat(), official_index_name,
        )
        response = self._session.post(
            NSE_INDICES_HISTORICAL_URL, json={"cinfo": cinfo}, timeout=self._timeout,
            headers={"Accept": "application/json", "User-Agent": "HSI-NSE-Stock-Manager/1.0"},
        )
        response.raise_for_status()
        raw = response.content
        raw_hash = sha256(raw).hexdigest()
        rows = _parse_official_response(raw, official_index_name)
        artifact_path = _archive_raw_response(artifact_directory, canonical_index_id, raw_hash, raw)
        unavailable_counts = tuple((field, sum(field in row[2] for row in rows)) for field in ("OPEN", "HIGH", "LOW"))
        artifact = OfficialIndexCloseRetrievalArtifact(
            artifact_id=f"official-index-close-artifact:{raw_hash}", canonical_index_id=canonical_index_id,
            official_index_name=official_index_name, source_url=NSE_INDICES_HISTORICAL_URL,
            requested_start=requested_start.isoformat(), requested_end=requested_end.isoformat(),
            retrieved_at=retrieved_at.astimezone(UTC), raw_artifact_sha256=raw_hash,
            row_count=len(rows), earliest_session=rows[0][0] if rows else None,
            latest_session=rows[-1][0] if rows else None, parser_version=PARSER_VERSION,
            raw_unavailable_field_counts=unavailable_counts, local_path=str(artifact_path),
        )
        observations = tuple(CanonicalIndexCloseObservation.create(
            canonical_index_id=canonical_index_id, official_index_name=official_index_name,
            session=session, close=close, retrieved_at=retrieved_at, raw_artifact_sha256=raw_hash,
            raw_unavailable_fields=unavailable,
        ) for session, close, unavailable in rows)
        return artifact, observations


class OfficialNseIndexCloseSeriesRefresh:
    """Bounded, fixed-target official close acquisition with two-run proof."""

    def __init__(
        self, *, store: IndexCloseSeriesStore, targets: Sequence[tuple[str, str]],
        artifact_directory: Path, client: NseIndicesOfficialCloseClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if tuple(targets) != tuple(sorted(targets)):
            raise ValueError("OFFICIAL_INDEX_CLOSE_TARGETS_MUST_BE_DETERMINISTIC")
        self._store, self._targets, self._directory = store, tuple(targets), artifact_directory
        self._client, self._clock = client or NseIndicesOfficialCloseClient(), clock

    def run_twice(self) -> OfficialIndexCloseActivationResult:
        requested_at = self._clock().astimezone(UTC)
        first = self._run(requested_at)
        second = self._run(self._clock().astimezone(UTC))
        return OfficialIndexCloseActivationResult(requested_at, self._clock().astimezone(UTC), first, second)

    def _run(self, retrieved_at: datetime) -> tuple[OfficialIndexCloseTargetRun, ...]:
        local_now = retrieved_at.astimezone(_IST)
        latest_completed = local_now.date() if local_now.timetz().replace(tzinfo=None) >= _NSE_CLOSE else local_now.date() - timedelta(days=1)
        start = latest_completed - timedelta(days=365)
        results = []
        for canonical_index_id, official_index_name in self._targets:
            before = len(self._store.range(canonical_index_id, datetime(1970, 1, 1, tzinfo=UTC), retrieved_at, as_of=retrieved_at))
            artifact, observations = self._client.fetch(
                canonical_index_id=canonical_index_id, official_index_name=official_index_name,
                requested_start=start, requested_end=latest_completed, retrieved_at=retrieved_at,
                artifact_directory=self._directory,
            )
            self._store.save_artifact(artifact)
            inserted = duplicates = conflicts = 0
            for observation in observations:
                outcome = self._store.save_observation(observation)
                if outcome is IndexCloseWriteOutcome.INSERTED:
                    inserted += 1
                elif outcome is IndexCloseWriteOutcome.IDENTICAL:
                    duplicates += 1
                else:
                    conflicts += 1
            values = self._store.range(canonical_index_id, datetime(1970, 1, 1, tzinfo=UTC), retrieved_at, as_of=retrieved_at)
            results.append(OfficialIndexCloseTargetRun(
                canonical_index_id, official_index_name, before, len(values),
                values[0].session if values else None, values[-1].session if values else None,
                inserted, duplicates, conflicts, artifact.raw_artifact_sha256,
                "OFFICIAL_INDEX_CLOSE_CONFLICT" if conflicts else None,
            ))
        return tuple(results)


def close_series_from_bars(values: Iterable[object]) -> tuple[CloseSeriesPoint, ...]:
    """Adapt valid canonical bars for close-only consumers without mutation."""
    return tuple(CloseSeriesPoint(item.end_time, item.close, item.bar_id, item.provenance.provider) for item in values)


def close_series_from_observations(values: Iterable[CanonicalIndexCloseObservation]) -> tuple[CloseSeriesPoint, ...]:
    return tuple(CloseSeriesPoint(item.session, item.close, item.observation_id, item.provider) for item in values)


def _parse_official_response(raw: bytes, official_index_name: str) -> tuple[tuple[datetime, Decimal, tuple[str, ...]], ...]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and isinstance(payload.get("d"), str):
            payload = json.loads(payload["d"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("NSE_INDICES_HISTORICAL_RESPONSE_MALFORMED") from error
    if not isinstance(payload, list):
        raise ValueError("NSE_INDICES_HISTORICAL_RESPONSE_SCHEMA_UNSUPPORTED")
    rows: dict[datetime, tuple[Decimal, tuple[str, ...]]] = {}
    for value in payload:
        if not isinstance(value, dict) or str(value.get("INDEX_NAME", "")).casefold() != official_index_name.casefold():
            raise ValueError("NSE_INDICES_HISTORICAL_EXACT_INDEX_IDENTITY_REQUIRED")
        try:
            session = datetime.combine(datetime.strptime(str(value["HistoricalDate"]), "%d %b %Y").date(), _NSE_CLOSE, _IST).astimezone(UTC)
            close = Decimal(str(value["CLOSE"]).replace(",", ""))
        except (KeyError, ValueError, InvalidOperation) as error:
            raise ValueError("NSE_INDICES_HISTORICAL_CLOSE_UNAVAILABLE") from error
        if close <= 0:
            raise ValueError("NSE_INDICES_HISTORICAL_CLOSE_UNAVAILABLE")
        unavailable = tuple(sorted(field for field in ("OPEN", "HIGH", "LOW") if str(value.get(field, "")).strip() == "-"))
        prior = rows.get(session)
        if prior is not None and prior != (close, unavailable):
            raise ValueError("NSE_INDICES_HISTORICAL_DUPLICATE_SESSION_CONFLICT")
        rows[session] = (close, unavailable)
    return tuple((session, close, unavailable) for session, (close, unavailable) in sorted(rows.items()))


def _archive_raw_response(directory: Path, canonical_index_id: str, raw_hash: str, raw: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    filename = canonical_index_id.replace(":", "_").lower() + "-" + raw_hash + ".json"
    path = directory / filename
    if path.exists():
        if sha256(path.read_bytes()).hexdigest() != raw_hash:
            raise ValueError("NSE_INDICES_HISTORICAL_ARTIFACT_HASH_CONFLICT")
    else:
        path.write_bytes(raw)
    return path


def _evidence_values(canonical_index_id: str, official_index_name: str, session: datetime, close: Decimal, provider: str, source_reference: str, parser_version: str) -> dict[str, str]:
    return {
        "canonical_index_id": canonical_index_id, "official_index_name": official_index_name,
        "session": session.astimezone(UTC).isoformat(), "close": str(close),
        "provider": provider, "source_reference": source_reference, "parser_version": parser_version,
    }


def _fingerprint(values: dict[str, str]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "CanonicalIndexCloseObservation", "CloseSeriesPoint", "CoreSnapshotIndexCloseStore",
    "IndexCloseSeriesStore", "IndexCloseWriteOutcome", "NSE_INDICES_OFFICIAL",
    "NseIndicesOfficialCloseClient", "OfficialIndexCloseActivationResult",
    "OfficialIndexCloseRetrievalArtifact", "OfficialNseIndexCloseSeriesRefresh",
    "close_series_from_bars", "close_series_from_observations",
)
