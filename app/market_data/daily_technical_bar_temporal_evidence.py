"""Pure, fail-closed daily-bar temporal evidence.

This module deliberately does not reinterpret retained provider timestamps or
write temporal receipts.  A caller must supply source-backed session and
availability semantics before a daily OHLCV bar becomes strict PIT evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar, CanonicalSessionPhase, CanonicalTradingDay,
    SessionPhaseType, TradingDayState,
)
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Timeframe
from app.market_data.technical_bar_contract import TechnicalVolumeReadiness


CONTRACT_ID = "canonical-daily-technical-bar-known-at-and-completeness-evidence"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class DailyTemporalEvidenceError(ValueError):
    """Stable fail-closed error for malformed temporal evidence."""


class DailySourceAvailabilitySemantics(StrEnum):
    EXPLICIT_PUBLICATION_TIMESTAMP = "EXPLICIT_PUBLICATION_TIMESTAMP"
    PROVIDER_CONTRACT_AFTER_SESSION_CLOSE = "PROVIDER_CONTRACT_AFTER_SESSION_CLOSE"
    UNRESOLVED = "UNRESOLVED"


class DailySessionIdentityState(StrEnum):
    RESOLVED = "RESOLVED"
    SESSION_UNRESOLVED = "SESSION_UNRESOLVED"
    NON_TRADING_SESSION = "NON_TRADING_SESSION"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class DailyCompletenessState(StrEnum):
    CLOSED = "CLOSED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETENESS_UNRESOLVED = "COMPLETENESS_UNRESOLVED"
    DATA_INCOMPLETE = "DATA_INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class DailyKnownAtState(StrEnum):
    RESOLVED_EXPLICIT = "RESOLVED_EXPLICIT"
    RESOLVED_SESSION_CLOSE = "RESOLVED_SESSION_CLOSE"
    SOURCE_TIMING_UNRESOLVED = "SOURCE_TIMING_UNRESOLVED"


class DailyStrictPitUsability(StrEnum):
    USABLE = "USABLE"
    BLOCKED = "BLOCKED"


class DailyTemporalReason(StrEnum):
    SOURCE_SESSION_DATE_UNRESOLVED = "SOURCE_SESSION_DATE_UNRESOLVED"
    SESSION_CALENDAR_UNRESOLVED = "SESSION_CALENDAR_UNRESOLVED"
    SESSION_EVIDENCE_CONFLICTED = "SESSION_EVIDENCE_CONFLICTED"
    BAR_ON_NON_TRADING_SESSION = "BAR_ON_NON_TRADING_SESSION"
    SESSION_CLOSE_UNRESOLVED = "SESSION_CLOSE_UNRESOLVED"
    SOURCE_TIMING_UNRESOLVED = "SOURCE_TIMING_UNRESOLVED"
    SOURCE_PUBLICATION_PRECEDES_SESSION_CLOSE = "SOURCE_PUBLICATION_PRECEDES_SESSION_CLOSE"
    CURRENT_SESSION_IN_PROGRESS = "CURRENT_SESSION_IN_PROGRESS"
    KNOWN_AT_AFTER_EVALUATION_AS_OF = "KNOWN_AT_AFTER_EVALUATION_AS_OF"
    VOLUME_NOT_READY = "VOLUME_NOT_READY"


@dataclass(frozen=True, slots=True)
class DailyBarSourceTimingEvidence:
    """Source-backed facts only; ``received_at`` is intentionally absent."""

    provider: str
    session_date: date | None
    availability_semantics: DailySourceAvailabilitySemantics
    explicit_known_at: datetime | None
    evidence_id: str | None
    evidence_fingerprint: str | None

    def __post_init__(self) -> None:
        if (
            not _ID.fullmatch(self.provider)
            or not isinstance(self.availability_semantics, DailySourceAvailabilitySemantics)
            or (self.session_date is not None and not isinstance(self.session_date, date))
            or (self.explicit_known_at is not None and not _aware(self.explicit_known_at))
            or ((self.evidence_id is None) != (self.evidence_fingerprint is None))
            or (self.evidence_id is not None and (not _ID.fullmatch(self.evidence_id) or not _FP.fullmatch(self.evidence_fingerprint or "")))
            or (self.availability_semantics is DailySourceAvailabilitySemantics.EXPLICIT_PUBLICATION_TIMESTAMP and self.explicit_known_at is None)
            or (self.availability_semantics is DailySourceAvailabilitySemantics.PROVIDER_CONTRACT_AFTER_SESSION_CLOSE and self.explicit_known_at is not None)
            or (self.availability_semantics is not DailySourceAvailabilitySemantics.UNRESOLVED and self.evidence_id is None)
        ):
            raise DailyTemporalEvidenceError("DAILY_SOURCE_TIMING_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class DailyTechnicalBarTemporalReceipt:
    canonical_bar_id: str
    canonical_instrument_id: str
    provider: str
    source_bar_id: str
    session_date: date | None
    session_identity: DailySessionIdentityState
    trading_day: CanonicalTradingDay | None
    regular_session_close: datetime | None
    session_evidence_id: str | None
    session_evidence_fingerprint: str | None
    source_timing: DailyBarSourceTimingEvidence
    completeness: DailyCompletenessState
    known_at_state: DailyKnownAtState
    known_at: datetime | None
    strict_pit_usability: DailyStrictPitUsability
    source_exchange_timestamp: datetime | None
    source_provider_timestamp: datetime | None
    source_received_at: datetime
    adjustment_status: AdjustmentStatus
    volume_readiness: TechnicalVolumeReadiness
    reasons: tuple[DailyTemporalReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reasons), key=lambda value: value.value))
        expected = _fingerprint(_payload_values(self, reasons))
        if (
            not _ID.fullmatch(self.canonical_bar_id) or not _ID.fullmatch(self.canonical_instrument_id)
            or not _ID.fullmatch(self.provider) or not _ID.fullmatch(self.source_bar_id)
            or self.reasons != reasons or not isinstance(self.source_timing, DailyBarSourceTimingEvidence)
            or not _aware(self.source_received_at) or (self.known_at is not None and not _aware(self.known_at))
            or ((self.session_evidence_id is None) != (self.session_evidence_fingerprint is None))
            or (self.session_evidence_id is not None and (not _ID.fullmatch(self.session_evidence_id) or not _FP.fullmatch(self.session_evidence_fingerprint or "")))
            or self.fingerprint != expected
        ):
            raise DailyTemporalEvidenceError("DAILY_TEMPORAL_RECEIPT_INVALID")
        resolved = self.known_at_state in {DailyKnownAtState.RESOLVED_EXPLICIT, DailyKnownAtState.RESOLVED_SESSION_CLOSE}
        if resolved != (self.known_at is not None):
            raise DailyTemporalEvidenceError("DAILY_KNOWN_AT_STATE_INVALID")
        if self.strict_pit_usability is DailyStrictPitUsability.USABLE and not (
            self.session_identity is DailySessionIdentityState.RESOLVED
            and self.completeness is DailyCompletenessState.CLOSED
            and resolved
        ):
            raise DailyTemporalEvidenceError("DAILY_STRICT_PIT_STATE_INVALID")


def resolve_daily_technical_bar_temporal_evidence(
    *, canonical_bar_id: str, bar: CanonicalOHLCVBar,
    calendar: CanonicalMarketSessionCalendar, evaluation_as_of: datetime,
    source_timing: DailyBarSourceTimingEvidence,
) -> DailyTechnicalBarTemporalReceipt:
    """Resolve only retained/source-injected facts at the supplied PIT cutoff."""
    if bar.timeframe is not Timeframe.DAILY or not _aware(evaluation_as_of) or source_timing.provider != bar.provenance.provider:
        raise DailyTemporalEvidenceError("DAILY_TEMPORAL_RESOLUTION_INPUT_INVALID")
    session_date = source_timing.session_date
    reasons: list[DailyTemporalReason] = []
    day: CanonicalTradingDay | None = None
    close: datetime | None = None
    session_identity = DailySessionIdentityState.SESSION_UNRESOLVED
    session_id = session_fp = None
    if session_date is None:
        reasons.append(DailyTemporalReason.SOURCE_SESSION_DATE_UNRESOLVED)
    else:
        day = calendar.resolve_trading_day(session_date, as_of=evaluation_as_of)
        session_id = day.source_ids[0] if len(day.source_ids) == 1 else None
        session_fp = day.source_fingerprints[0] if len(day.source_fingerprints) == 1 else None
        if day.state is TradingDayState.UNKNOWN:
            session_identity = DailySessionIdentityState.EVIDENCE_CONFLICTED if any(reason.value == "EVIDENCE_CONFLICTED" for reason in day.reasons) else DailySessionIdentityState.SESSION_UNRESOLVED
            reasons.append(DailyTemporalReason.SESSION_EVIDENCE_CONFLICTED if session_identity is DailySessionIdentityState.EVIDENCE_CONFLICTED else DailyTemporalReason.SESSION_CALENDAR_UNRESOLVED)
        elif day.state in {TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING}:
            session_identity = DailySessionIdentityState.NON_TRADING_SESSION
            reasons.append(DailyTemporalReason.BAR_ON_NON_TRADING_SESSION)
        else:
            session_identity = DailySessionIdentityState.RESOLVED
            phases = tuple(item for item in calendar.phases_for(session_date, as_of=evaluation_as_of) if item.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
            if len(phases) == 1:
                close = phases[0].ends_at.astimezone(UTC)
            else:
                reasons.append(DailyTemporalReason.SESSION_CLOSE_UNRESOLVED)
    completeness = DailyCompletenessState.COMPLETENESS_UNRESOLVED
    known_state = DailyKnownAtState.SOURCE_TIMING_UNRESOLVED
    known_at: datetime | None = None
    if session_identity is DailySessionIdentityState.NON_TRADING_SESSION:
        completeness = DailyCompletenessState.EVIDENCE_CONFLICTED
    elif session_identity is DailySessionIdentityState.EVIDENCE_CONFLICTED:
        completeness = DailyCompletenessState.EVIDENCE_CONFLICTED
    elif session_identity is DailySessionIdentityState.RESOLVED and close is not None:
        if _utc(evaluation_as_of) < close:
            completeness = DailyCompletenessState.IN_PROGRESS
            reasons.append(DailyTemporalReason.CURRENT_SESSION_IN_PROGRESS)
        elif source_timing.availability_semantics is DailySourceAvailabilitySemantics.EXPLICIT_PUBLICATION_TIMESTAMP:
            assert source_timing.explicit_known_at is not None
            if _utc(source_timing.explicit_known_at) < close:
                reasons.append(DailyTemporalReason.SOURCE_PUBLICATION_PRECEDES_SESSION_CLOSE)
            else:
                known_at, known_state, completeness = _utc(source_timing.explicit_known_at), DailyKnownAtState.RESOLVED_EXPLICIT, DailyCompletenessState.CLOSED
        elif source_timing.availability_semantics is DailySourceAvailabilitySemantics.PROVIDER_CONTRACT_AFTER_SESSION_CLOSE:
            known_at, known_state, completeness = close, DailyKnownAtState.RESOLVED_SESSION_CLOSE, DailyCompletenessState.CLOSED
        else:
            reasons.append(DailyTemporalReason.SOURCE_TIMING_UNRESOLVED)
    elif session_identity is DailySessionIdentityState.RESOLVED:
        reasons.append(DailyTemporalReason.SESSION_CLOSE_UNRESOLVED)
    volume = TechnicalVolumeReadiness.READY if bar.volume is not None and bar.volume > 0 else TechnicalVolumeReadiness.VOLUME_NOT_READY
    if volume is TechnicalVolumeReadiness.VOLUME_NOT_READY:
        reasons.append(DailyTemporalReason.VOLUME_NOT_READY)
    usable = completeness is DailyCompletenessState.CLOSED and known_at is not None and known_at <= _utc(evaluation_as_of)
    if completeness is DailyCompletenessState.CLOSED and not usable:
        reasons.append(DailyTemporalReason.KNOWN_AT_AFTER_EVALUATION_AS_OF)
    actual_reasons = tuple(sorted(set(reasons), key=lambda value: value.value))
    values = dict(canonical_bar_id=canonical_bar_id, canonical_instrument_id=bar.instrument.instrument_id, provider=bar.provenance.provider, source_bar_id=bar.bar_id, session_date=session_date, session_identity=session_identity, trading_day=day, regular_session_close=close, session_evidence_id=session_id, session_evidence_fingerprint=session_fp, source_timing=source_timing, completeness=completeness, known_at_state=known_state, known_at=known_at, strict_pit_usability=DailyStrictPitUsability.USABLE if usable else DailyStrictPitUsability.BLOCKED, source_exchange_timestamp=bar.provenance.exchange_timestamp, source_provider_timestamp=bar.provenance.provider_timestamp, source_received_at=bar.provenance.received_at, adjustment_status=bar.adjustment_status, volume_readiness=volume, reasons=actual_reasons)
    return DailyTechnicalBarTemporalReceipt(**values, fingerprint=_fingerprint(_payload_values_dict(values)))


def serialize_daily_technical_bar_temporal_receipt(value: DailyTechnicalBarTemporalReceipt) -> str:
    value.__post_init__()
    return _canonical(_payload_values(value, value.reasons) | {"fingerprint": value.fingerprint})


def _payload_values(value: DailyTechnicalBarTemporalReceipt, reasons: tuple[DailyTemporalReason, ...]) -> dict[str, object]:
    return _payload_values_dict({name: getattr(value, name) for name in DailyTechnicalBarTemporalReceipt.__dataclass_fields__ if name != "fingerprint"} | {"reasons": reasons})


def _payload_values_dict(value: dict[str, object]) -> dict[str, object]:
    day = value["trading_day"]
    source = value["source_timing"]
    assert day is None or isinstance(day, CanonicalTradingDay)
    assert isinstance(source, DailyBarSourceTimingEvidence)
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "canonical_bar_id": value["canonical_bar_id"], "canonical_instrument_id": value["canonical_instrument_id"], "provider": value["provider"], "source_bar_id": value["source_bar_id"], "session_date": _date(value["session_date"]), "session_identity": _enum(value["session_identity"]), "trading_day_fingerprint": None if day is None else day.fingerprint, "regular_session_close": _time(value["regular_session_close"]), "session_evidence_id": value["session_evidence_id"], "session_evidence_fingerprint": value["session_evidence_fingerprint"], "source_timing": {"provider": source.provider, "session_date": _date(source.session_date), "availability_semantics": source.availability_semantics.value, "explicit_known_at": _time(source.explicit_known_at), "evidence_id": source.evidence_id, "evidence_fingerprint": source.evidence_fingerprint}, "completeness": _enum(value["completeness"]), "known_at_state": _enum(value["known_at_state"]), "known_at": _time(value["known_at"]), "strict_pit_usability": _enum(value["strict_pit_usability"]), "source_exchange_timestamp": _time(value["source_exchange_timestamp"]), "source_provider_timestamp": _time(value["source_provider_timestamp"]), "source_received_at": _time(value["source_received_at"]), "adjustment_status": _enum(value["adjustment_status"]), "volume_readiness": _enum(value["volume_readiness"]), "reasons": [_enum(item) for item in value["reasons"]]}


def _canonical(value: object) -> str: return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
def _fingerprint(value: object) -> str: return "sha256:" + sha256(_canonical(value).encode()).hexdigest()
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise DailyTemporalEvidenceError("DAILY_TEMPORAL_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)
def _time(value: object) -> str | None: return _utc(value).isoformat() if isinstance(value, datetime) else None
def _date(value: object) -> str | None: return value.isoformat() if isinstance(value, date) else None
def _enum(value: object) -> str: return value.value if isinstance(value, StrEnum) else str(value)


__all__ = ("CONTRACT_ID", "CONTRACT_VERSION", "DailyBarSourceTimingEvidence", "DailyCompletenessState", "DailyKnownAtState", "DailySessionIdentityState", "DailySourceAvailabilitySemantics", "DailyStrictPitUsability", "DailyTechnicalBarTemporalReceipt", "DailyTemporalEvidenceError", "DailyTemporalReason", "resolve_daily_technical_bar_temporal_evidence", "serialize_daily_technical_bar_temporal_receipt")
