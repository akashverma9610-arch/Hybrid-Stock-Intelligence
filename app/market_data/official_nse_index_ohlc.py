"""Immutable official NSE Indices Daily price-return OHLC evidence.

Calculated index levels are intentionally not ``CanonicalOHLCVBar`` values:
the official historical report supplies index open/high/low/close, but not
traded volume, delivery, VWAP, or equity corporate-action semantics.  This
compact Core-snapshot store is the canonical current-descriptive input for
existing benchmark/sector technical diagnostics only.  It never makes a
historical PIT availability claim.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from time import sleep
from typing import Callable, Protocol, Sequence
from zoneinfo import ZoneInfo

import requests

from app.market_data.index_close_series import (
    NSE_INDICES_HISTORICAL_PAGE,
    NSE_INDICES_HISTORICAL_URL,
    NSE_INDICES_OFFICIAL,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


PARSER_VERSION = "nse-indices-historical-ohlc-v1"
INDEX_LEVEL_BASIS = "OFFICIAL_INDEX_LEVEL_OHLC"
INDEX_RETURN_FAMILY = "PRICE_RETURN_INDEX"
_IST = ZoneInfo("Asia/Kolkata")
_NSE_CLOSE = time(15, 30)


class IndexOhlcWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class CanonicalOfficialIndexOhlcObservation:
    """One exact official price-return index level; no synthetic fields."""

    observation_id: str
    canonical_index_id: str
    official_index_name: str
    session: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    provider: str
    source_reference: str
    index_level_basis: str
    index_return_family: str
    retrieved_at: datetime
    raw_artifact_sha256: str
    parser_version: str
    evidence_fingerprint: str

    def __post_init__(self) -> None:
        if not all((
            self.observation_id, self.canonical_index_id, self.official_index_name,
            self.provider, self.source_reference, self.raw_artifact_sha256,
            self.parser_version, self.evidence_fingerprint,
        )):
            raise ValueError("OFFICIAL_INDEX_OHLC_IDENTITY_REQUIRED")
        if (
            self.provider != NSE_INDICES_OFFICIAL
            or self.index_level_basis != INDEX_LEVEL_BASIS
            or self.index_return_family != INDEX_RETURN_FAMILY
            or not _aware(self.session)
            or not _aware(self.retrieved_at)
            or min(self.open, self.high, self.low, self.close) <= 0
            or self.high < max(self.open, self.close)
            or self.low > min(self.open, self.close)
        ):
            raise ValueError("OFFICIAL_INDEX_OHLC_SEMANTICS_INVALID")
        if len(self.raw_artifact_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.raw_artifact_sha256):
            raise ValueError("OFFICIAL_INDEX_OHLC_ARTIFACT_HASH_INVALID")
        semantic = _fingerprint(_observation_values(
            self.canonical_index_id, self.official_index_name, self.session,
            self.open, self.high, self.low, self.close, self.provider,
            self.source_reference, self.index_level_basis,
            self.index_return_family, self.parser_version,
        ))
        expected = _fingerprint({"semantic": semantic, "raw_artifact_sha256": self.raw_artifact_sha256})
        if self.evidence_fingerprint != expected:
            raise ValueError("OFFICIAL_INDEX_OHLC_FINGERPRINT_MISMATCH")
        # The observation identity is economic/session identity.  A later
        # official retrieval that repeats the exact values is idempotent, but
        # its immutable raw artifact still remains independently retained.
        if self.observation_id != f"official-index-ohlc:{semantic[:32]}":
            raise ValueError("OFFICIAL_INDEX_OHLC_IDENTITY_MISMATCH")

    @classmethod
    def create(
        cls, *, canonical_index_id: str, official_index_name: str,
        session: datetime, open: Decimal, high: Decimal, low: Decimal,
        close: Decimal, retrieved_at: datetime, raw_artifact_sha256: str,
        source_reference: str = NSE_INDICES_HISTORICAL_PAGE,
    ) -> "CanonicalOfficialIndexOhlcObservation":
        values = _observation_values(
            canonical_index_id, official_index_name, session, open, high, low,
            close, NSE_INDICES_OFFICIAL, source_reference, INDEX_LEVEL_BASIS,
            INDEX_RETURN_FAMILY, PARSER_VERSION,
        )
        semantic = _fingerprint(values)
        fingerprint = _fingerprint({"semantic": semantic, "raw_artifact_sha256": raw_artifact_sha256})
        return cls(
            f"official-index-ohlc:{semantic[:32]}", canonical_index_id,
            official_index_name, session.astimezone(UTC), open, high, low,
            close, NSE_INDICES_OFFICIAL, source_reference, INDEX_LEVEL_BASIS,
            INDEX_RETURN_FAMILY, retrieved_at.astimezone(UTC),
            raw_artifact_sha256, PARSER_VERSION, fingerprint,
        )

    def eligible_as_of(self, value: datetime) -> bool:
        return self.session <= value and self.retrieved_at <= value


@dataclass(frozen=True, slots=True)
class OfficialIndexOhlcRetrievalArtifact:
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
    index_level_basis: str
    index_return_family: str
    local_path: str

    def __post_init__(self) -> None:
        if not all((
            self.artifact_id, self.canonical_index_id, self.official_index_name,
            self.source_url, self.raw_artifact_sha256, self.parser_version,
            self.index_level_basis, self.index_return_family, self.local_path,
        )) or not _aware(self.retrieved_at) or self.parser_version != PARSER_VERSION or (
            self.index_level_basis, self.index_return_family,
        ) != (INDEX_LEVEL_BASIS, INDEX_RETURN_FAMILY):
            raise ValueError("OFFICIAL_INDEX_OHLC_ARTIFACT_INVALID")
        if (
            len(self.raw_artifact_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.raw_artifact_sha256)
            or self.artifact_id != f"official-index-ohlc-artifact:{self.raw_artifact_sha256}"
        ):
            raise ValueError("OFFICIAL_INDEX_OHLC_ARTIFACT_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class OfficialIndexOhlcTargetRun:
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
class OfficialIndexOhlcActivationResult:
    requested_at: datetime
    completed_at: datetime
    first_run: tuple[OfficialIndexOhlcTargetRun, ...]
    second_run: tuple[OfficialIndexOhlcTargetRun, ...]


class OfficialIndexOhlcStore(Protocol):
    def save_observation(self, value: CanonicalOfficialIndexOhlcObservation) -> IndexOhlcWriteOutcome: ...
    def save_artifact(self, value: OfficialIndexOhlcRetrievalArtifact) -> bool: ...
    def range(self, canonical_index_id: str, start: datetime, end: datetime, *, as_of: datetime | None = None) -> tuple[CanonicalOfficialIndexOhlcObservation, ...]: ...


class CoreSnapshotOfficialIndexOhlcStore:
    """Append-only index-level evidence, separated from equity bar storage."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_artifact(self, value: OfficialIndexOhlcRetrievalArtifact) -> bool:
        existing = self._repository.get_snapshot(value.artifact_id)
        if existing is not None:
            if not isinstance(existing.payload, OfficialIndexOhlcRetrievalArtifact) or not _same_artifact(existing.payload, value):
                raise ValueError("OFFICIAL_INDEX_OHLC_ARTIFACT_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.artifact_id, CoreApiSnapshotFamily.OFFICIAL_INDEX_OHLC_ARTIFACT,
            "v1", type(value).__name__, value.raw_artifact_sha256,
            value.retrieved_at, value,
        ))
        return True

    def save_observation(self, value: CanonicalOfficialIndexOhlcObservation) -> IndexOhlcWriteOutcome:
        peers = tuple(
            item for item in self._all(CoreApiSnapshotFamily.CANONICAL_INDEX_OHLC_OBSERVATION)
            if isinstance(item, CanonicalOfficialIndexOhlcObservation)
            and item.canonical_index_id == value.canonical_index_id
            and item.session == value.session and item.provider == value.provider
            and item.index_return_family == value.index_return_family
        )
        if not peers:
            self._repository.save_snapshot(CoreApiSnapshot(
                value.observation_id, CoreApiSnapshotFamily.CANONICAL_INDEX_OHLC_OBSERVATION,
                "v1", type(value).__name__, value.evidence_fingerprint,
                value.retrieved_at, value,
            ))
            return IndexOhlcWriteOutcome.INSERTED
        if any(item.observation_id == value.observation_id for item in peers):
            return IndexOhlcWriteOutcome.IDENTICAL
        return IndexOhlcWriteOutcome.CONFLICT

    def range(
        self, canonical_index_id: str, start: datetime, end: datetime,
        *, as_of: datetime | None = None,
    ) -> tuple[CanonicalOfficialIndexOhlcObservation, ...]:
        return tuple(sorted((
            item for item in self._all(CoreApiSnapshotFamily.CANONICAL_INDEX_OHLC_OBSERVATION)
            if isinstance(item, CanonicalOfficialIndexOhlcObservation)
            and item.canonical_index_id == canonical_index_id
            and start <= item.session <= end
            and (as_of is None or item.eligible_as_of(as_of))
        ), key=lambda item: (item.session, item.observation_id)))

    def _all(self, family: CoreApiSnapshotFamily) -> tuple[object, ...]:
        values: list[object] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(item.payload for item in page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


class NseIndicesOfficialOhlcClient:
    """Bounded first-party NSE Indices Historical Data reader."""

    def __init__(self, *, session: requests.Session | None = None, timeout_seconds: int = 45) -> None:
        self._session = session or requests.Session()
        self._timeout = timeout_seconds

    def fetch(
        self, *, canonical_index_id: str, official_index_name: str,
        requested_start: date, requested_end: date, retrieved_at: datetime,
        artifact_directory: Path,
    ) -> tuple[OfficialIndexOhlcRetrievalArtifact, tuple[CanonicalOfficialIndexOhlcObservation, ...]]:
        if (requested_end - requested_start).days > 365:
            raise ValueError("NSE_INDICES_HISTORICAL_MAXIMUM_RANGE_EXCEEDED")
        cinfo = "{'name':'%s','startDate':'%s','endDate':'%s','indexName':'%s'}" % (
            official_index_name.upper(), requested_start.isoformat(),
            requested_end.isoformat(), official_index_name,
        )
        response = self._session.post(
            NSE_INDICES_HISTORICAL_URL, json={"cinfo": cinfo}, timeout=self._timeout,
            headers={"Accept": "application/json", "User-Agent": "HSI-NSE-Stock-Manager/1.0"},
        )
        response.raise_for_status()
        raw = response.content
        raw_hash = sha256(raw).hexdigest()
        rows = parse_official_nse_index_ohlc_response(raw, official_index_name)
        artifact_path = _archive_raw_response(artifact_directory, canonical_index_id, raw_hash, raw)
        artifact = OfficialIndexOhlcRetrievalArtifact(
            f"official-index-ohlc-artifact:{raw_hash}", canonical_index_id,
            official_index_name, NSE_INDICES_HISTORICAL_URL,
            requested_start.isoformat(), requested_end.isoformat(),
            retrieved_at.astimezone(UTC), raw_hash, len(rows),
            rows[0][0] if rows else None, rows[-1][0] if rows else None,
            PARSER_VERSION, INDEX_LEVEL_BASIS, INDEX_RETURN_FAMILY,
            str(artifact_path),
        )
        observations = tuple(CanonicalOfficialIndexOhlcObservation.create(
            canonical_index_id=canonical_index_id, official_index_name=official_index_name,
            session=session, open=open_value, high=high, low=low, close=close,
            retrieved_at=retrieved_at, raw_artifact_sha256=raw_hash,
        ) for session, open_value, high, low, close in rows)
        return artifact, observations


class OfficialNseIndexOhlcSeriesRefresh:
    """Fixed exact targets, compact persistence, and replay proof."""

    def __init__(
        self, *, store: OfficialIndexOhlcStore,
        targets: Sequence[tuple[str, str]], artifact_directory: Path,
        client: NseIndicesOfficialOhlcClient | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        request_interval_seconds: float = 1.0,
        sleeper: Callable[[float], None] = sleep,
    ) -> None:
        targets = tuple(targets)
        if not targets or targets != tuple(sorted(set(targets))):
            raise ValueError("OFFICIAL_INDEX_OHLC_TARGETS_MUST_BE_DETERMINISTIC")
        if request_interval_seconds < 0:
            raise ValueError("OFFICIAL_INDEX_OHLC_REQUEST_INTERVAL_INVALID")
        self._store, self._targets, self._directory = store, targets, artifact_directory
        self._client, self._clock = client or NseIndicesOfficialOhlcClient(), clock
        self._request_interval_seconds, self._sleeper = request_interval_seconds, sleeper

    def run_twice(self) -> OfficialIndexOhlcActivationResult:
        requested_at = _utc(self._clock())
        first = self._run(requested_at)
        second = self._run(_utc(self._clock()))
        return OfficialIndexOhlcActivationResult(requested_at, _utc(self._clock()), first, second)

    def _run(self, retrieved_at: datetime) -> tuple[OfficialIndexOhlcTargetRun, ...]:
        local_now = retrieved_at.astimezone(_IST)
        latest_completed = (
            local_now.date() if local_now.timetz().replace(tzinfo=None) >= _NSE_CLOSE
            else local_now.date() - timedelta(days=1)
        )
        start = latest_completed - timedelta(days=365)
        result: list[OfficialIndexOhlcTargetRun] = []
        for target_number, (canonical_index_id, official_index_name) in enumerate(self._targets):
            if target_number:
                # A bounded first-party acquisition must remain polite even
                # when a prior exact target was close-only or unavailable.
                self._sleeper(self._request_interval_seconds)
            before = len(self._store.range(
                canonical_index_id, datetime(1970, 1, 1, tzinfo=UTC),
                retrieved_at, as_of=retrieved_at,
            ))
            try:
                artifact, observations = self._client.fetch(
                    canonical_index_id=canonical_index_id,
                    official_index_name=official_index_name,
                    requested_start=start, requested_end=latest_completed,
                    retrieved_at=retrieved_at, artifact_directory=self._directory,
                )
            except ValueError as error:
                # An official close-only/empty response is a per-index data
                # limitation, not a license to synthesize OHLC or discard the
                # rest of the governed exact target set.
                result.append(OfficialIndexOhlcTargetRun(
                    canonical_index_id, official_index_name, before, before,
                    None, None, 0, 0, 0, "", str(error),
                ))
                continue
            self._store.save_artifact(artifact)
            inserted = duplicates = conflicts = 0
            for observation in observations:
                outcome = self._store.save_observation(observation)
                if outcome is IndexOhlcWriteOutcome.INSERTED:
                    inserted += 1
                elif outcome is IndexOhlcWriteOutcome.IDENTICAL:
                    duplicates += 1
                else:
                    conflicts += 1
            values = self._store.range(
                canonical_index_id, datetime(1970, 1, 1, tzinfo=UTC),
                retrieved_at, as_of=retrieved_at,
            )
            result.append(OfficialIndexOhlcTargetRun(
                canonical_index_id, official_index_name, before, len(values),
                values[0].session if values else None,
                values[-1].session if values else None, inserted, duplicates,
                conflicts, artifact.raw_artifact_sha256,
                "OFFICIAL_INDEX_OHLC_CONFLICT" if conflicts else None,
            ))
        return tuple(result)


def parse_official_nse_index_ohlc_response(
    raw: bytes, official_index_name: str,
) -> tuple[tuple[datetime, Decimal, Decimal, Decimal, Decimal], ...]:
    """Parse only exact index identity and fully supplied official OHLC."""
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
        if isinstance(payload, str):
            payload = json.loads(payload)
        if isinstance(payload, dict) and isinstance(payload.get("d"), str):
            payload = json.loads(payload["d"])
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("NSE_INDICES_HISTORICAL_RESPONSE_MALFORMED") from error
    if not isinstance(payload, list) or not payload:
        raise ValueError("NSE_INDICES_HISTORICAL_RESPONSE_SCHEMA_UNSUPPORTED")
    rows: dict[datetime, tuple[Decimal, Decimal, Decimal, Decimal]] = {}
    for value in payload:
        if not isinstance(value, dict) or str(value.get("INDEX_NAME", "")).casefold() != official_index_name.casefold():
            raise ValueError("NSE_INDICES_HISTORICAL_EXACT_INDEX_IDENTITY_REQUIRED")
        try:
            session = datetime.combine(
                datetime.strptime(str(value["HistoricalDate"]), "%d %b %Y").date(),
                _NSE_CLOSE, _IST,
            ).astimezone(UTC)
            open_value, high, low, close = (
                Decimal(str(value[field]).replace(",", ""))
                for field in ("OPEN", "HIGH", "LOW", "CLOSE")
            )
        except (KeyError, ValueError, InvalidOperation) as error:
            raise ValueError("NSE_INDICES_HISTORICAL_OHLC_UNAVAILABLE") from error
        if (
            min(open_value, high, low, close) <= 0
            or high < max(open_value, close) or low > min(open_value, close)
        ):
            raise ValueError("NSE_INDICES_HISTORICAL_OHLC_UNAVAILABLE")
        prior = rows.get(session)
        current = (open_value, high, low, close)
        if prior is not None and prior != current:
            raise ValueError("NSE_INDICES_HISTORICAL_DUPLICATE_SESSION_CONFLICT")
        rows[session] = current
    return tuple((session, *values) for session, values in sorted(rows.items()))


def _archive_raw_response(directory: Path, canonical_index_id: str, raw_hash: str, raw: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (canonical_index_id.replace(":", "_").lower() + "-" + raw_hash + ".json")
    if path.exists():
        if sha256(path.read_bytes()).hexdigest() != raw_hash:
            raise ValueError("NSE_INDICES_HISTORICAL_ARTIFACT_HASH_CONFLICT")
    else:
        path.write_bytes(raw)
    return path


def _observation_values(
    canonical_index_id: str, official_index_name: str, session: datetime,
    open_value: Decimal, high: Decimal, low: Decimal, close: Decimal,
    provider: str, source_reference: str, index_level_basis: str,
    index_return_family: str, parser_version: str,
) -> dict[str, str]:
    return {
        "canonical_index_id": canonical_index_id,
        "official_index_name": official_index_name,
        "session": _utc(session).isoformat(),
        "open": str(open_value), "high": str(high), "low": str(low),
        "close": str(close), "provider": provider,
        "source_reference": source_reference,
        "index_level_basis": index_level_basis,
        "index_return_family": index_return_family,
        "parser_version": parser_version,
    }


def _fingerprint(values: dict[str, str]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _same_artifact(
    left: OfficialIndexOhlcRetrievalArtifact,
    right: OfficialIndexOhlcRetrievalArtifact,
) -> bool:
    """A content-addressed raw artifact is replay-equivalent across runs.

    Retrieval wall-clock time and archive location are operational metadata,
    not a reason to reject an otherwise identical immutable artifact.
    """
    return (
        left.artifact_id == right.artifact_id
        and left.canonical_index_id == right.canonical_index_id
        and left.official_index_name == right.official_index_name
        and left.source_url == right.source_url
        and left.raw_artifact_sha256 == right.raw_artifact_sha256
        and left.row_count == right.row_count
        and left.earliest_session == right.earliest_session
        and left.latest_session == right.latest_session
        and left.parser_version == right.parser_version
        and left.index_level_basis == right.index_level_basis
        and left.index_return_family == right.index_return_family
    )


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise ValueError("OFFICIAL_INDEX_OHLC_TIMESTAMP_MUST_BE_AWARE")
    return value.astimezone(UTC)


__all__ = (
    "CanonicalOfficialIndexOhlcObservation",
    "CoreSnapshotOfficialIndexOhlcStore",
    "INDEX_LEVEL_BASIS", "INDEX_RETURN_FAMILY", "IndexOhlcWriteOutcome",
    "NseIndicesOfficialOhlcClient", "OfficialIndexOhlcActivationResult",
    "OfficialIndexOhlcRetrievalArtifact", "OfficialNseIndexOhlcSeriesRefresh",
    "parse_official_nse_index_ohlc_response",
)
