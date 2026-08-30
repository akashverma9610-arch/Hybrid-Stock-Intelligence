"""Stored-only, per-instrument historical OHLCV readiness.

This module intentionally makes no provider request and never selects a
replacement bar.  A durable same-provider conflict is an instrument-local
blocker until separately adjudicated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Callable, Protocol

from app.data_operations.upstox import MINIMUM_REQUIRED_DAILY_SESSIONS
from app.market_data.models import Timeframe


class OhlcvReadinessStatus(StrEnum):
    READY = "OHLCV_READY"
    CONFLICTED = "OHLCV_CONFLICTED"
    INSUFFICIENT_HISTORY = "OHLCV_INSUFFICIENT_HISTORY"
    STALE = "OHLCV_STALE"
    UNAVAILABLE = "OHLCV_UNAVAILABLE"
    MAPPING_UNAVAILABLE = "OHLCV_MAPPING_UNAVAILABLE"


class _HistoricalReadinessStore(Protocol):
    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None): ...
    def has_conflict_artifact(self, instrument_id: str) -> bool: ...
    def list_conflict_artifacts(self, *, instrument_id: str | None = None): ...


@dataclass(frozen=True, slots=True)
class OhlcvInstrumentReadiness:
    canonical_instrument_id: str
    status: OhlcvReadinessStatus
    mapping_available: bool
    session_count: int
    required_sessions: int
    latest_bar_at: datetime | None
    required_latest_at: datetime | None
    conflict_fingerprints: tuple[str, ...]
    reason: str

    @property
    def ready(self) -> bool:
        return self.status is OhlcvReadinessStatus.READY


@dataclass(frozen=True, slots=True)
class OhlcvReadinessCoverage:
    total: int
    mapped: int
    sufficient: int
    current: int
    stale: int
    conflicted: int
    healthy_ready: int
    insufficient: int
    unavailable: int
    unmapped: int


class OhlcvReadinessService:
    """Evaluate canonical stored evidence without widening consumer scope.

    ``required_latest_at`` is supplied from the existing U17 OHLCV watermark.
    It is deliberately not a new clock or freshness threshold: a bar is stale
    only when it falls behind that already-persisted accepted-through marker.
    """

    def __init__(self, historical: _HistoricalReadinessStore, *, required_sessions: int = MINIMUM_REQUIRED_DAILY_SESSIONS) -> None:
        if required_sessions < 1:
            raise ValueError("OHLCV_REQUIRED_SESSION_COUNT_INVALID")
        self._historical = historical
        self._required = required_sessions

    def assess(
        self,
        canonical_instrument_id: str,
        *,
        as_of: datetime | None = None,
        mapping_available: bool = True,
        required_latest_at: datetime | None = None,
    ) -> OhlcvInstrumentReadiness:
        if not canonical_instrument_id:
            raise ValueError("OHLCV_CANONICAL_INSTRUMENT_REQUIRED")
        if as_of is not None and (as_of.tzinfo is None or as_of.utcoffset() is None):
            raise ValueError("OHLCV_READINESS_AS_OF_TIMEZONE_REQUIRED")
        if required_latest_at is not None and (required_latest_at.tzinfo is None or required_latest_at.utcoffset() is None):
            raise ValueError("OHLCV_READINESS_WATERMARK_TIMEZONE_REQUIRED")
        artifacts = self._historical.list_conflict_artifacts(instrument_id=canonical_instrument_id)
        fingerprints = tuple(item.conflict_fingerprint for item in artifacts)
        bars = self._historical.latest(canonical_instrument_id, Timeframe.DAILY, self._required, as_of=as_of)
        session_count = len(bars)
        latest = bars[-1].end_time if bars else None
        # The safe initial policy is intentionally range-independent: any
        # durable unresolved conflict blocks this instrument rather than
        # silently declaring an older conflict irrelevant.
        if fingerprints:
            return self._result(canonical_instrument_id, OhlcvReadinessStatus.CONFLICTED, mapping_available, session_count, latest, required_latest_at, fingerprints, "UNRESOLVED_HISTORICAL_BAR_CONFLICT")
        if not mapping_available:
            return self._result(canonical_instrument_id, OhlcvReadinessStatus.MAPPING_UNAVAILABLE, False, 0, None, required_latest_at, (), "EXACT_PROVIDER_MAPPING_UNAVAILABLE")
        if not bars:
            return self._result(canonical_instrument_id, OhlcvReadinessStatus.UNAVAILABLE, True, 0, None, required_latest_at, (), "NO_CANONICAL_HISTORICAL_BARS")
        if session_count < self._required:
            return self._result(canonical_instrument_id, OhlcvReadinessStatus.INSUFFICIENT_HISTORY, True, session_count, latest, required_latest_at, (), "INSUFFICIENT_CANONICAL_SESSIONS")
        if required_latest_at is not None and latest < required_latest_at:
            return self._result(canonical_instrument_id, OhlcvReadinessStatus.STALE, True, session_count, latest, required_latest_at, (), "LATEST_BAR_BEHIND_OHLCV_WATERMARK")
        return self._result(canonical_instrument_id, OhlcvReadinessStatus.READY, True, session_count, latest, required_latest_at, (), "CURRENT_SUFFICIENT_NONCONFLICTED_HISTORY")

    def coverage(
        self,
        instrument_ids: tuple[str, ...],
        *,
        as_of: datetime | None = None,
        mapping_available: Callable[[str], bool] | None = None,
        required_latest_at: datetime | None = None,
    ) -> tuple[OhlcvReadinessCoverage, tuple[OhlcvInstrumentReadiness, ...]]:
        identifiers = tuple(sorted(set(instrument_ids)))
        bulk = getattr(self._historical, "readiness_evidence", None)
        evidence = bulk(identifiers, Timeframe.DAILY, as_of=as_of) if bulk is not None else {}
        values = tuple(
            self._assess_with_evidence(
                instrument_id,
                mapping_available=True if mapping_available is None else mapping_available(instrument_id),
                required_latest_at=required_latest_at,
                evidence=evidence.get(instrument_id),
                as_of=as_of,
            )
            for instrument_id in identifiers
        )
        statuses = [item.status for item in values]
        coverage = OhlcvReadinessCoverage(
            total=len(values), mapped=sum(item.mapping_available for item in values),
            sufficient=sum(item.session_count >= self._required for item in values),
            current=sum(item.latest_bar_at is not None and (required_latest_at is None or item.latest_bar_at >= required_latest_at) for item in values),
            stale=statuses.count(OhlcvReadinessStatus.STALE), conflicted=statuses.count(OhlcvReadinessStatus.CONFLICTED),
            healthy_ready=statuses.count(OhlcvReadinessStatus.READY),
            insufficient=statuses.count(OhlcvReadinessStatus.INSUFFICIENT_HISTORY),
            unavailable=statuses.count(OhlcvReadinessStatus.UNAVAILABLE),
            unmapped=statuses.count(OhlcvReadinessStatus.MAPPING_UNAVAILABLE),
        )
        return coverage, values

    def _assess_with_evidence(self, instrument_id, *, mapping_available, required_latest_at, evidence, as_of):
        if evidence is None:
            return self.assess(
                instrument_id, as_of=as_of, mapping_available=mapping_available,
                required_latest_at=required_latest_at,
            )
        artifacts = self._historical.list_conflict_artifacts(instrument_id=instrument_id)
        fingerprints = tuple(item.conflict_fingerprint for item in artifacts)
        session_count, latest = evidence
        if fingerprints:
            return self._result(instrument_id, OhlcvReadinessStatus.CONFLICTED, mapping_available, session_count, latest, required_latest_at, fingerprints, "UNRESOLVED_HISTORICAL_BAR_CONFLICT")
        if not mapping_available:
            return self._result(instrument_id, OhlcvReadinessStatus.MAPPING_UNAVAILABLE, False, 0, None, required_latest_at, (), "EXACT_PROVIDER_MAPPING_UNAVAILABLE")
        if session_count == 0 or latest is None:
            return self._result(instrument_id, OhlcvReadinessStatus.UNAVAILABLE, True, 0, None, required_latest_at, (), "NO_CANONICAL_HISTORICAL_BARS")
        if session_count < self._required:
            return self._result(instrument_id, OhlcvReadinessStatus.INSUFFICIENT_HISTORY, True, session_count, latest, required_latest_at, (), "INSUFFICIENT_CANONICAL_SESSIONS")
        if required_latest_at is not None and latest < required_latest_at:
            return self._result(instrument_id, OhlcvReadinessStatus.STALE, True, session_count, latest, required_latest_at, (), "LATEST_BAR_BEHIND_OHLCV_WATERMARK")
        return self._result(instrument_id, OhlcvReadinessStatus.READY, True, session_count, latest, required_latest_at, (), "CURRENT_SUFFICIENT_NONCONFLICTED_HISTORY")

    def _result(self, instrument_id, status, mapping_available, session_count, latest, required_latest_at, fingerprints, reason):
        return OhlcvInstrumentReadiness(
            instrument_id, status, mapping_available, session_count, self._required,
            latest, required_latest_at, fingerprints, reason,
        )


__all__ = (
    "OhlcvInstrumentReadiness", "OhlcvReadinessCoverage", "OhlcvReadinessService", "OhlcvReadinessStatus",
)
