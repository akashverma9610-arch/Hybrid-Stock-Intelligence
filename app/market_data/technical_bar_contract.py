"""Immutable temporal/readiness contract layered over existing canonical OHLCV.

The contract carries no provider transport, store, clock, strategy, diagnostic,
portfolio, broker, or execution dependency.  It deliberately wraps rather
than replaces ``CanonicalOHLCVBar`` wherever that existing bar model can carry
the interval.  Intervals not yet represented by the stored OHLCV enum (notably
4H and 1M) can still be represented by a readiness receipt, but cannot be
silently materialised as canonical market evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, Timeframe


CONTRACT_ID = "canonical-technical-bar-timeframe-and-completeness"
CONTRACT_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class TechnicalBarContractError(ValueError):
    """Stable fail-closed error for malformed temporal technical-bar facts."""


class TechnicalIntervalUnit(StrEnum):
    MINUTE = "MINUTE"
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"


class TechnicalIntervalSemantics(StrEnum):
    DEFINED = "DEFINED"
    FOUR_HOUR_SEMANTICS_UNRESOLVED = "FOUR_HOUR_SEMANTICS_UNRESOLVED"


class TechnicalBarOrigin(StrEnum):
    NATIVE_SOURCE_BAR = "NATIVE_SOURCE_BAR"
    DERIVED_RESAMPLED_BAR = "DERIVED_RESAMPLED_BAR"


class TechnicalBarCompletenessState(StrEnum):
    CLOSED = "CLOSED"
    IN_PROGRESS = "IN_PROGRESS"
    INCOMPLETE = "INCOMPLETE"
    DATA_MISSING = "DATA_MISSING"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class TechnicalBarReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"
    SEMANTICS_UNRESOLVED = "SEMANTICS_UNRESOLVED"


class TechnicalVolumeReadiness(StrEnum):
    READY = "READY"
    VOLUME_NOT_READY = "VOLUME_NOT_READY"


class TechnicalBarReason(StrEnum):
    SESSION_ANCHOR_UNAVAILABLE = "SESSION_ANCHOR_UNAVAILABLE"
    INTERVAL_SEMANTICS_UNRESOLVED = "INTERVAL_SEMANTICS_UNRESOLVED"
    BAR_NOT_CLOSED = "BAR_NOT_CLOSED"
    BAR_KNOWN_AT_UNAVAILABLE = "BAR_KNOWN_AT_UNAVAILABLE"
    SOURCE_BAR_MISSING = "SOURCE_BAR_MISSING"
    SOURCE_BAR_NOT_CLOSED = "SOURCE_BAR_NOT_CLOSED"
    SOURCE_KNOWN_AT_UNAVAILABLE = "SOURCE_KNOWN_AT_UNAVAILABLE"
    SOURCE_INTERVAL_INCOMPATIBLE = "SOURCE_INTERVAL_INCOMPATIBLE"
    SOURCE_ADJUSTMENT_INCOMPATIBLE = "SOURCE_ADJUSTMENT_INCOMPATIBLE"
    SOURCE_VOLUME_INCOMPATIBLE = "SOURCE_VOLUME_INCOMPATIBLE"
    SOURCE_LINEAGE_CONFLICTED = "SOURCE_LINEAGE_CONFLICTED"
    PROVIDER_EVIDENCE_CONFLICTED = "PROVIDER_EVIDENCE_CONFLICTED"
    CORPORATE_ACTION_CONTINUITY_UNAVAILABLE = "CORPORATE_ACTION_CONTINUITY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CanonicalTechnicalInterval:
    """Typed interval identity; 4H is representable but deliberately unresolved."""

    unit: TechnicalIntervalUnit
    multiplier: int
    semantics: TechnicalIntervalSemantics = TechnicalIntervalSemantics.DEFINED

    def __post_init__(self) -> None:
        if self.multiplier < 1:
            raise TechnicalBarContractError("TECHNICAL_INTERVAL_MULTIPLIER_INVALID")
        four_hour = self.unit is TechnicalIntervalUnit.HOUR and self.multiplier == 4
        if four_hour != (self.semantics is TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED):
            raise TechnicalBarContractError("TECHNICAL_INTERVAL_SEMANTICS_INVALID")

    @property
    def interval_id(self) -> str:
        suffix = {
            TechnicalIntervalUnit.MINUTE: "m", TechnicalIntervalUnit.HOUR: "H",
            TechnicalIntervalUnit.DAY: "D", TechnicalIntervalUnit.WEEK: "W", TechnicalIntervalUnit.MONTH: "M",
        }[self.unit]
        return f"{self.multiplier}{suffix}"

    @property
    def stored_timeframe(self) -> Timeframe | None:
        values = {
            (TechnicalIntervalUnit.MINUTE, 1): Timeframe.ONE_MINUTE,
            (TechnicalIntervalUnit.MINUTE, 5): Timeframe.FIVE_MINUTES,
            (TechnicalIntervalUnit.MINUTE, 15): Timeframe.FIFTEEN_MINUTES,
            (TechnicalIntervalUnit.MINUTE, 30): Timeframe.THIRTY_MINUTES,
            (TechnicalIntervalUnit.HOUR, 1): Timeframe.SIXTY_MINUTES,
            (TechnicalIntervalUnit.DAY, 1): Timeframe.DAILY,
            (TechnicalIntervalUnit.WEEK, 1): Timeframe.WEEKLY,
        }
        return values.get((self.unit, self.multiplier))


def interval_from_timeframe(value: Timeframe) -> CanonicalTechnicalInterval:
    values = {
        Timeframe.ONE_MINUTE: (TechnicalIntervalUnit.MINUTE, 1),
        Timeframe.FIVE_MINUTES: (TechnicalIntervalUnit.MINUTE, 5),
        Timeframe.FIFTEEN_MINUTES: (TechnicalIntervalUnit.MINUTE, 15),
        Timeframe.THIRTY_MINUTES: (TechnicalIntervalUnit.MINUTE, 30),
        Timeframe.SIXTY_MINUTES: (TechnicalIntervalUnit.HOUR, 1),
        Timeframe.DAILY: (TechnicalIntervalUnit.DAY, 1),
        Timeframe.WEEKLY: (TechnicalIntervalUnit.WEEK, 1),
    }
    unit, multiplier = values[value]
    return CanonicalTechnicalInterval(unit, multiplier)


@dataclass(frozen=True, slots=True)
class ProviderIntervalRepresentation:
    provider: str
    source_interval: str

    def __post_init__(self) -> None:
        if not _identifier(self.provider) or not self.source_interval.strip():
            raise TechnicalBarContractError("TECHNICAL_PROVIDER_INTERVAL_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalTradingPeriod:
    """Caller-supplied session/period fact derived from the existing calendar contract."""

    venue: Exchange
    segment: str
    period_id: str
    session_dates: tuple[date, ...]
    starts_at: datetime
    ends_at: datetime
    timezone_id: str
    calendar_id: str
    calendar_fingerprint: str
    session_source_ids: tuple[str, ...]
    session_source_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            self.venue is Exchange.UNKNOWN or not self.segment.strip() or not _identifier(self.period_id)
            or self.session_dates != tuple(sorted(set(self.session_dates)) or not self.session_dates)
            or not _aware(self.starts_at) or not _aware(self.ends_at) or self.starts_at >= self.ends_at
            or not self.timezone_id.strip() or not _identifier(self.calendar_id)
            or not _fingerprint(self.calendar_fingerprint)
            or self.session_source_ids != tuple(sorted(set(self.session_source_ids)))
            or self.session_source_fingerprints != tuple(sorted(set(self.session_source_fingerprints)))
            or len(self.session_source_ids) != len(self.session_source_fingerprints)
            or any(not _identifier(value) for value in self.session_source_ids)
            or any(not _fingerprint(value) for value in self.session_source_fingerprints)
        ):
            raise TechnicalBarContractError("TECHNICAL_TRADING_PERIOD_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalBarSourceLineage:
    source_bar_id: str
    source_bar_fingerprint: str
    interval: CanonicalTechnicalInterval
    known_at: datetime | None

    def __post_init__(self) -> None:
        if not _identifier(self.source_bar_id) or not _fingerprint(self.source_bar_fingerprint) or (self.known_at is not None and not _aware(self.known_at)):
            raise TechnicalBarContractError("TECHNICAL_SOURCE_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalBarCompletenessReceipt:
    """Read-only deterministic readiness fact; it is not a persistence record."""

    canonical_bar_id: str
    interval: CanonicalTechnicalInterval
    period: TechnicalTradingPeriod | None
    state: TechnicalBarCompletenessState
    readiness: TechnicalBarReadiness
    expected_source_bar_ids: tuple[str, ...]
    observed_source_lineage: tuple[TechnicalBarSourceLineage, ...]
    missing_source_bar_count: int
    known_at: datetime | None
    adjustment_status: AdjustmentStatus
    volume_readiness: TechnicalVolumeReadiness
    reasons: tuple[TechnicalBarReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        expected = tuple(sorted(set(self.expected_source_bar_ids)))
        observed = tuple(sorted(self.observed_source_lineage, key=lambda value: (value.source_bar_id, value.source_bar_fingerprint)))
        observed_keys = tuple((value.source_bar_id, value.source_bar_fingerprint) for value in observed)
        expected_fingerprint = _receipt_fingerprint_values(
            self.canonical_bar_id, self.interval, self.period, self.state, self.readiness, expected,
            observed, self.missing_source_bar_count, self.known_at, self.adjustment_status,
            self.volume_readiness, tuple(sorted(set(self.reasons), key=lambda value: value.value)),
        )
        if (
            not _identifier(self.canonical_bar_id) or self.expected_source_bar_ids != expected
            or any(not _identifier(value) for value in expected)
            or self.observed_source_lineage != observed or self.missing_source_bar_count < 0
            or len(set(observed_keys)) != len(observed_keys)
            or (self.known_at is not None and not _aware(self.known_at))
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value))
            or not self.reasons and self.state is not TechnicalBarCompletenessState.CLOSED
            or self.fingerprint != expected_fingerprint
        ):
            raise TechnicalBarContractError("TECHNICAL_BAR_RECEIPT_INVALID")
        if self.state is TechnicalBarCompletenessState.CLOSED:
            if self.period is None or self.known_at is None or self.known_at < self.period.ends_at or self.missing_source_bar_count:
                raise TechnicalBarContractError("TECHNICAL_CLOSED_BAR_COMPLETENESS_INVALID")
            if self.interval.semantics is TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED:
                raise TechnicalBarContractError("TECHNICAL_FOUR_HOUR_CANNOT_BE_CLOSED")
        if self.readiness is TechnicalBarReadiness.READY and self.state is not TechnicalBarCompletenessState.CLOSED:
            raise TechnicalBarContractError("TECHNICAL_BAR_READINESS_INVALID")


def make_bar_receipt(
    *, canonical_bar_id: str, interval: CanonicalTechnicalInterval, period: TechnicalTradingPeriod | None,
    state: TechnicalBarCompletenessState, readiness: TechnicalBarReadiness,
    expected_source_bar_ids: Iterable[str] = (), observed_source_lineage: Iterable[TechnicalBarSourceLineage] = (),
    missing_source_bar_count: int = 0, known_at: datetime | None = None,
    adjustment_status: AdjustmentStatus = AdjustmentStatus.UNKNOWN,
    volume_readiness: TechnicalVolumeReadiness = TechnicalVolumeReadiness.VOLUME_NOT_READY,
    reasons: Iterable[TechnicalBarReason] = (),
) -> TechnicalBarCompletenessReceipt:
    expected = tuple(sorted(set(expected_source_bar_ids)))
    observed = tuple(sorted(observed_source_lineage, key=lambda value: (value.source_bar_id, value.source_bar_fingerprint)))
    actual_reasons = tuple(sorted(set(reasons), key=lambda value: value.value))
    values = (canonical_bar_id, interval, period, state, readiness, expected, observed, missing_source_bar_count,
              _utc(known_at) if known_at else None, adjustment_status, volume_readiness, actual_reasons)
    return TechnicalBarCompletenessReceipt(*values, _receipt_fingerprint_values(*values))


@dataclass(frozen=True, slots=True)
class CanonicalTechnicalBar:
    """Temporal overlay around an existing canonical OHLCV bar; no duplicate store."""

    canonical_bar_id: str
    market_bar: CanonicalOHLCVBar
    interval: CanonicalTechnicalInterval
    origin: TechnicalBarOrigin
    provider_interval: ProviderIntervalRepresentation | None
    receipt: TechnicalBarCompletenessReceipt
    source_lineage: tuple[TechnicalBarSourceLineage, ...]
    aggregation_policy_id: str | None
    aggregation_policy_version: str | None
    corporate_action_ids: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        lineage = tuple(sorted(self.source_lineage, key=lambda value: (value.source_bar_id, value.source_bar_fingerprint)))
        action_ids = tuple(sorted(set(self.corporate_action_ids)))
        expected = _bar_fingerprint_values(
            self.canonical_bar_id, self.market_bar, self.interval, self.origin, self.provider_interval,
            self.receipt, lineage, self.aggregation_policy_id, self.aggregation_policy_version, action_ids,
        )
        if (
            not _identifier(self.canonical_bar_id) or self.interval.stored_timeframe is not self.market_bar.timeframe
            or self.receipt.canonical_bar_id != self.canonical_bar_id or self.receipt.interval != self.interval
            or self.source_lineage != lineage or self.corporate_action_ids != action_ids
            or any(not _identifier(value) for value in action_ids) or self.fingerprint != expected
        ):
            raise TechnicalBarContractError("CANONICAL_TECHNICAL_BAR_INVALID")
        if self.origin is TechnicalBarOrigin.NATIVE_SOURCE_BAR:
            if self.provider_interval is None or self.source_lineage or self.aggregation_policy_id is not None or self.aggregation_policy_version is not None:
                raise TechnicalBarContractError("TECHNICAL_NATIVE_BAR_LINEAGE_INVALID")
        else:
            if self.provider_interval is not None or not self.source_lineage or not _identifier(self.aggregation_policy_id or "") or not _identifier(self.aggregation_policy_version or ""):
                raise TechnicalBarContractError("TECHNICAL_DERIVED_BAR_LINEAGE_INVALID")
            if len({value.source_bar_id for value in self.source_lineage}) != len(self.source_lineage):
                raise TechnicalBarContractError("TECHNICAL_DERIVED_SOURCE_DUPLICATE")
            if self.receipt.known_at is None or any(value.known_at is None or value.known_at > self.receipt.known_at for value in self.source_lineage):
                raise TechnicalBarContractError("TECHNICAL_DERIVED_KNOWN_AT_INVALID")


def make_native_technical_bar(
    *, market_bar: CanonicalOHLCVBar, period: TechnicalTradingPeriod | None,
    state: TechnicalBarCompletenessState, readiness: TechnicalBarReadiness, known_at: datetime | None,
    provider_interval: ProviderIntervalRepresentation, reasons: Iterable[TechnicalBarReason] = (),
    volume_readiness: TechnicalVolumeReadiness | None = None, corporate_action_ids: Iterable[str] = (),
) -> CanonicalTechnicalBar:
    interval = interval_from_timeframe(market_bar.timeframe)
    identifier = canonical_bar_identity(market_bar.instrument.instrument_id, market_bar.instrument.exchange, market_bar.instrument.series or "", interval, period, market_bar.start_time, market_bar.end_time)
    receipt = make_bar_receipt(
        canonical_bar_id=identifier, interval=interval, period=period, state=state, readiness=readiness,
        known_at=known_at, adjustment_status=market_bar.adjustment_status,
        volume_readiness=volume_readiness or _volume_readiness((market_bar,)), reasons=reasons,
    )
    values = (identifier, market_bar, interval, TechnicalBarOrigin.NATIVE_SOURCE_BAR, provider_interval, receipt, (), None, None, tuple(sorted(set(corporate_action_ids))))
    return CanonicalTechnicalBar(*values, _bar_fingerprint_values(*values))


@dataclass(frozen=True, slots=True)
class DerivedTechnicalBarAggregation:
    """Pure aggregation result.  It does not write, replace, or activate a bar."""

    canonical_bar_id: str
    interval: CanonicalTechnicalInterval
    period: TechnicalTradingPeriod
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    adjustment_status: AdjustmentStatus
    source_lineage: tuple[TechnicalBarSourceLineage, ...]
    known_at: datetime
    volume_readiness: TechnicalVolumeReadiness
    fingerprint: str

    def __post_init__(self) -> None:
        expected = _derived_fingerprint_values(self.canonical_bar_id, self.interval, self.period, self.open, self.high, self.low, self.close, self.volume, self.adjustment_status, self.source_lineage, self.known_at, self.volume_readiness)
        if (
            not _identifier(self.canonical_bar_id) or self.interval.semantics is TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED
            or not _aware(self.known_at) or self.known_at < self.period.ends_at or self.high < max(self.open, self.close, self.low)
            or self.low > min(self.open, self.close, self.high) or self.volume is not None and self.volume < 0
            or not self.source_lineage or self.source_lineage != tuple(sorted(self.source_lineage, key=lambda value: (value.source_bar_id, value.source_bar_fingerprint)))
            or self.fingerprint != expected
        ):
            raise TechnicalBarContractError("DERIVED_TECHNICAL_BAR_INVALID")


def derive_closed_bar(
    *, interval: CanonicalTechnicalInterval, period: TechnicalTradingPeriod,
    expected_source_bar_ids: Iterable[str], source_bars: Iterable[CanonicalTechnicalBar],
) -> DerivedTechnicalBarAggregation:
    """Aggregate exact closed compatible source bars; gaps/conflicts fail closed."""
    expected = tuple(sorted(set(expected_source_bar_ids)))
    values = tuple(sorted(source_bars, key=lambda value: (value.market_bar.start_time, value.canonical_bar_id)))
    if interval.semantics is TechnicalIntervalSemantics.FOUR_HOUR_SEMANTICS_UNRESOLVED:
        raise TechnicalBarContractError("FOUR_HOUR_SEMANTICS_UNRESOLVED")
    actual_ids = tuple(value.canonical_bar_id for value in values)
    if not expected or set(actual_ids) != set(expected) or len(actual_ids) != len(expected):
        raise TechnicalBarContractError("TECHNICAL_SOURCE_COVERAGE_INCOMPLETE")
    if any(value.receipt.state is not TechnicalBarCompletenessState.CLOSED or value.receipt.known_at is None for value in values):
        raise TechnicalBarContractError("TECHNICAL_SOURCE_BAR_NOT_CLOSED")
    if any(value.receipt.period is None or value.receipt.period.calendar_fingerprint != period.calendar_fingerprint or value.receipt.period.venue is not period.venue or value.receipt.period.segment != period.segment for value in values):
        raise TechnicalBarContractError("TECHNICAL_SOURCE_SESSION_INCOMPATIBLE")
    if len({value.market_bar.instrument.instrument_id for value in values}) != 1 or len({value.market_bar.adjustment_status for value in values}) != 1:
        raise TechnicalBarContractError("TECHNICAL_SOURCE_ADJUSTMENT_INCOMPATIBLE")
    if any(value.market_bar.start_time < period.starts_at or value.market_bar.end_time > period.ends_at for value in values):
        raise TechnicalBarContractError("TECHNICAL_SOURCE_PERIOD_MISMATCH")
    lineage = tuple(sorted((TechnicalBarSourceLineage(value.canonical_bar_id, value.fingerprint, value.interval, value.receipt.known_at) for value in values), key=lambda value: (value.source_bar_id, value.source_bar_fingerprint)))
    known_at = max(value.receipt.known_at for value in values if value.receipt.known_at is not None)
    first, last = values[0].market_bar, values[-1].market_bar
    volume_ready = _volume_readiness(tuple(value.market_bar for value in values))
    volume = sum(value.market_bar.volume or 0 for value in values) if volume_ready is TechnicalVolumeReadiness.READY else None
    identifier = canonical_bar_identity(first.instrument.instrument_id, first.instrument.exchange, first.instrument.series or "", interval, period, period.starts_at, period.ends_at)
    values_for_fingerprint = (identifier, interval, period, first.open, max(value.market_bar.high for value in values), min(value.market_bar.low for value in values), last.close, volume, first.adjustment_status, lineage, known_at, volume_ready)
    return DerivedTechnicalBarAggregation(*values_for_fingerprint, _derived_fingerprint_values(*values_for_fingerprint))


def canonical_bar_identity(instrument_id: str, exchange: Exchange, segment: str, interval: CanonicalTechnicalInterval, period: TechnicalTradingPeriod | None, start_time: datetime, end_time: datetime) -> str:
    if not _identifier(instrument_id) or exchange is Exchange.UNKNOWN or not _aware(start_time) or not _aware(end_time) or end_time < start_time:
        raise TechnicalBarContractError("TECHNICAL_BAR_IDENTITY_INPUT_INVALID")
    values = {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "instrument_id": instrument_id,
        "exchange": exchange.value, "segment": segment, "interval": interval.interval_id,
        "period_id": period.period_id if period else None, "period_fingerprint": period.calendar_fingerprint if period else None,
        "start_time": _utc(start_time).isoformat(), "end_time": _utc(end_time).isoformat(),
    }
    return "technical-bar:" + sha256(_canonical(values).encode()).hexdigest()[:32]


def serialize_technical_bar_receipt(value: TechnicalBarCompletenessReceipt) -> str:
    value.__post_init__()
    return _canonical(_receipt_payload(value) | {"fingerprint": value.fingerprint})


def serialize_derived_technical_bar(value: DerivedTechnicalBarAggregation) -> str:
    value.__post_init__()
    return _canonical(_derived_payload(value) | {"fingerprint": value.fingerprint})


def _volume_readiness(values: tuple[CanonicalOHLCVBar, ...]) -> TechnicalVolumeReadiness:
    return TechnicalVolumeReadiness.READY if values and all(value.volume is not None and value.volume > 0 for value in values) else TechnicalVolumeReadiness.VOLUME_NOT_READY


def _receipt_fingerprint_values(*values: object) -> str:
    return _fingerprint_value(_receipt_payload_values(*values))


def _bar_fingerprint_values(*values: object) -> str:
    return _fingerprint_value(_bar_payload_values(*values))


def _derived_fingerprint_values(*values: object) -> str:
    return _fingerprint_value(_derived_payload_values(*values))


def _receipt_payload(value: TechnicalBarCompletenessReceipt) -> dict[str, object]:
    return _receipt_payload_values(value.canonical_bar_id, value.interval, value.period, value.state, value.readiness, value.expected_source_bar_ids, value.observed_source_lineage, value.missing_source_bar_count, value.known_at, value.adjustment_status, value.volume_readiness, value.reasons)


def _receipt_payload_values(canonical_bar_id: object, interval: object, period: object, state: object, readiness: object, expected: object, observed: object, missing: object, known_at: object, adjustment: object, volume: object, reasons: object) -> dict[str, object]:
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "canonical_bar_id": canonical_bar_id, "interval": _interval_payload(interval), "period": _period_payload(period), "state": _enum(state), "readiness": _enum(readiness), "expected_source_bar_ids": list(expected), "observed_source_lineage": [_lineage_payload(item) for item in observed], "missing_source_bar_count": missing, "known_at": _time(known_at), "adjustment_status": _enum(adjustment), "volume_readiness": _enum(volume), "reasons": [_enum(item) for item in reasons]}


def _bar_payload_values(canonical_bar_id: object, market_bar: object, interval: object, origin: object, provider_interval: object, receipt: object, lineage: object, policy_id: object, policy_version: object, corporate_actions: object) -> dict[str, object]:
    assert isinstance(market_bar, CanonicalOHLCVBar)
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "canonical_bar_id": canonical_bar_id, "market_bar": {"bar_id": market_bar.bar_id, "instrument_id": market_bar.instrument.instrument_id, "timeframe": market_bar.timeframe.value, "start_time": _time(market_bar.start_time), "end_time": _time(market_bar.end_time), "open": str(market_bar.open), "high": str(market_bar.high), "low": str(market_bar.low), "close": str(market_bar.close), "volume": market_bar.volume, "turnover": str(market_bar.turnover) if market_bar.turnover is not None else None, "trade_count": market_bar.trade_count, "adjustment_status": market_bar.adjustment_status.value, "provider": market_bar.provenance.provider, "provider_reference": market_bar.provenance.provider_instrument_reference, "normalization_version": market_bar.provenance.normalization_version}, "interval": _interval_payload(interval), "origin": _enum(origin), "provider_interval": None if provider_interval is None else {"provider": provider_interval.provider, "source_interval": provider_interval.source_interval}, "receipt_fingerprint": receipt.fingerprint, "source_lineage": [_lineage_payload(item) for item in lineage], "aggregation_policy_id": policy_id, "aggregation_policy_version": policy_version, "corporate_action_ids": list(corporate_actions)}


def _derived_payload(value: DerivedTechnicalBarAggregation) -> dict[str, object]:
    return _derived_payload_values(value.canonical_bar_id, value.interval, value.period, value.open, value.high, value.low, value.close, value.volume, value.adjustment_status, value.source_lineage, value.known_at, value.volume_readiness)


def _derived_payload_values(canonical_bar_id: object, interval: object, period: object, open_: object, high: object, low: object, close: object, volume: object, adjustment: object, lineage: object, known_at: object, volume_readiness: object) -> dict[str, object]:
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "canonical_bar_id": canonical_bar_id, "interval": _interval_payload(interval), "period": _period_payload(period), "open": str(open_), "high": str(high), "low": str(low), "close": str(close), "volume": volume, "adjustment_status": _enum(adjustment), "source_lineage": [_lineage_payload(item) for item in lineage], "known_at": _time(known_at), "volume_readiness": _enum(volume_readiness)}


def _interval_payload(value: object) -> dict[str, object]:
    assert isinstance(value, CanonicalTechnicalInterval)
    return {"unit": value.unit.value, "multiplier": value.multiplier, "interval_id": value.interval_id, "semantics": value.semantics.value}


def _period_payload(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    assert isinstance(value, TechnicalTradingPeriod)
    return {"venue": value.venue.value, "segment": value.segment, "period_id": value.period_id, "session_dates": [item.isoformat() for item in value.session_dates], "starts_at": _time(value.starts_at), "ends_at": _time(value.ends_at), "timezone_id": value.timezone_id, "calendar_id": value.calendar_id, "calendar_fingerprint": value.calendar_fingerprint, "session_source_ids": list(value.session_source_ids), "session_source_fingerprints": list(value.session_source_fingerprints)}


def _lineage_payload(value: object) -> dict[str, object]:
    assert isinstance(value, TechnicalBarSourceLineage)
    return {"source_bar_id": value.source_bar_id, "source_bar_fingerprint": value.source_bar_fingerprint, "interval": _interval_payload(value.interval), "known_at": _time(value.known_at)}


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint_value(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode()).hexdigest()


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_FINGERPRINT.fullmatch(value))


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise TechnicalBarContractError("TECHNICAL_BAR_TIMESTAMP_MUST_BE_AWARE")
    return value.astimezone(UTC)


def _time(value: object) -> str | None:
    return _utc(value).isoformat() if isinstance(value, datetime) else None


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)
