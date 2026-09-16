"""Factual reported-open context, using the existing certified Daily reader.

This is current-descriptive evidence, not proof of availability at the open.
Strict historical requests retain the native reader's fail-closed result.
No LTP/first-minute fallback, provider acquisition, prediction or execution.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, date, datetime
from decimal import Context, Decimal, localcontext
from enum import StrEnum
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from app.domain.models import FreshnessStatus
from app.historical.canonical_market_session_event_time import CanonicalMarketSessionCalendar, TradingDayState
from app.intelligence.unified_state import IntelligenceEvidenceAvailability as Availability
from app.intelligence.unified_state import IntelligenceEvidenceDomain as Domain, IntelligenceInvalidationDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.market_data.models import Exchange, InstrumentType
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffCertifiedDailyTechnicalRead, NseUdiffDailyTechnicalReadEvidence,
    NseUdiffDailyTechnicalReadRequest, NseUdiffDailyTechnicalReadState,
    read_certified_daily_technical_bars, serialize_nse_udiff_certified_daily_technical_read,
)


CONTRACT = "opening-gap-overnight/v1"
_LIMITS = (
    "CURRENT_DESCRIPTIVE_NOT_OPEN_TIME_PROOF", "PREOPEN_SOURCE_NOT_READY",
    "VOLATILITY_NORMALIZATION_NOT_AVAILABLE", "BENCHMARK_SECTOR_OPEN_SOURCE_NOT_READY",
    "MATERIALITY_POLICY_UNAVAILABLE", "CAUSAL_ATTRIBUTION_UNSUPPORTED",
    "TRADABILITY_NOT_INFERRED", "FRESHNESS_POLICY_UNAVAILABLE",
)


class OpeningGapStatus(StrEnum):
    GAP_UP = "GAP_UP"
    GAP_DOWN = "GAP_DOWN"
    FLAT = "FLAT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICTED = "CONFLICTED"


@dataclass(frozen=True, slots=True)
class OpeningOvernightState:
    daily_read: NseUdiffCertifiedDailyTechnicalRead
    calendar: CanonicalMarketSessionCalendar
    previous_session: date | None
    prior_decision_cutoff: datetime
    event_window_end: datetime
    status: OpeningGapStatus
    previous_close: Decimal | None
    current_open: Decimal | None
    gap_inr: Decimal | None
    gap_pct: Decimal | None
    event_references: tuple[StoredIntelligenceArtifact, ...]
    blockers: tuple[str, ...]
    fingerprint: str
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    @property
    def artifact_id(self) -> str:
        return "opening-overnight:" + self.fingerprint.removeprefix("sha256:")

    def verify(self) -> None:
        if not isinstance(self.status, OpeningGapStatus):
            raise ValueError("OPENING_OVERNIGHT_STATUS_INVALID")
        self.daily_read.request.__post_init__()
        self.daily_read.__post_init__()
        self.calendar.__post_init__()
        expected = _values(self.daily_read, self.calendar, self.prior_decision_cutoff,
                           self.event_window_end, self.event_references)
        for key, value in expected.items():
            if getattr(self, key) != value:
                raise ValueError("OPENING_OVERNIGHT_STATE_INVALID")
        if (self.actionability, self.execution_status) != ("WATCH_ONLY", "NON_EXECUTABLE"):
            raise ValueError("OPENING_OVERNIGHT_AUTHORITY_INVALID")
        if self.fingerprint != _fingerprint(_payload(self)):
            raise ValueError("OPENING_OVERNIGHT_FINGERPRINT_INVALID")

    def __post_init__(self) -> None:
        self.verify()


def build_opening_overnight(
    *, request: NseUdiffDailyTechnicalReadRequest, evidence: NseUdiffDailyTechnicalReadEvidence | None,
    calendar: CanonicalMarketSessionCalendar, prior_decision_cutoff: datetime,
    event_window_end: datetime, event_references: tuple[StoredIntelligenceArtifact, ...] = (),
) -> OpeningOvernightState:
    """Project retained certified bars and exact known-at event references only."""
    calendar.__post_init__()
    read = read_certified_daily_technical_bars(request=request, evidence=evidence)
    values = _values(read, calendar, prior_decision_cutoff, event_window_end, event_references)
    payload = dict(daily_read=read, calendar=calendar, **values,
                   actionability="WATCH_ONLY", execution_status="NON_EXECUTABLE")
    return OpeningOvernightState(**payload, fingerprint=_fingerprint(_payload_values(payload)))


def _values(read, calendar, prior_cutoff, event_end, references):
    read.__post_init__()
    as_of = _utc(read.request.evaluation_as_of)
    lower, upper = _utc(prior_cutoff), _utc(event_end)
    current = read.request.end_session
    previous = calendar.adjacent_trading_session(current, as_of=as_of, direction=-1)
    zone = ZoneInfo(calendar.timezone_id)
    if not lower < upper <= as_of:
        raise ValueError("OPENING_OVERNIGHT_WINDOW_INVALID")
    if upper.astimezone(zone).date() != current:
        raise ValueError("OPENING_OVERNIGHT_CURRENT_CUTOFF_SESSION_MISMATCH")
    reasons = list(_LIMITS)
    if previous is None:
        reasons.append("PREVIOUS_CANONICAL_SESSION_UNAVAILABLE")
    elif lower.astimezone(zone).date() != previous:
        raise ValueError("OPENING_OVERNIGHT_PRIOR_CUTOFF_SESSION_MISMATCH")
    day = calendar.resolve_trading_day(current, as_of=as_of)
    valid_day = day.state in {TradingDayState.REGULAR_TRADING_DAY,
                              TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}
    ready = read.state is NseUdiffDailyTechnicalReadState.READY
    if not valid_day:
        reasons.append("CURRENT_CANONICAL_TRADING_SESSION_UNAVAILABLE")
    if not ready:
        reasons.extend(read.reasons)
    aligned = (previous is not None and read.request.start_session == previous and len(read.bars) == 2
               and read.certification is not None and read.certification.expected_sessions == (previous, current))
    if ready and not aligned:
        reasons.append("EXACT_ADJACENT_DAILY_PAIR_REQUIRED")
    visible = {}
    for ref in references:
        ref.__post_init__()
        if (ref.domain is not Domain.NEWS_CATALYSTS or not isinstance(ref.availability, Availability)
                or ref.canonical_instrument_id != read.request.canonical_instrument_id):
            raise ValueError("OPENING_OVERNIGHT_EVENT_IDENTITY_INVALID")
        if ref.available_at is None or ref.observed_at is None or ref.evidence_as_of is None:
            raise ValueError("OPENING_OVERNIGHT_EVENT_KNOWN_AT_UNAVAILABLE")
        if not lower < _utc(ref.available_at) <= upper:
            continue
        if max(_utc(ref.observed_at), _utc(ref.evidence_as_of)) > upper:
            continue
        key = (ref.artifact_id, ref.artifact_fingerprint)
        if key in visible and visible[key] != ref:
            raise ValueError("OPENING_OVERNIGHT_EVENT_LINEAGE_CONFLICT")
        visible[key] = ref
    ordered = tuple(visible[key] for key in sorted(visible))
    if any(ref.availability is Availability.CONFLICTED for ref in ordered) or len({r.artifact_id for r in ordered}) != len(ordered):
        reasons.append("OVERNIGHT_EVENT_EVIDENCE_CONFLICTED")
    if not ordered:
        reasons.append("NO_ELIGIBLE_OVERNIGHT_EVENT_REFERENCES_NOT_A_NO_NEWS_CLAIM")
    close = opening = gap = percent = None
    status = OpeningGapStatus.INSUFFICIENT_DATA
    if ready and aligned and valid_day:
        bars = read.bars
        if any(b.instrument.instrument_type is not InstrumentType.NSE_EQUITY
               or b.instrument.exchange is not Exchange.NSE or b.instrument.currency != "INR" for b in bars):
            reasons.append("EXACT_NSE_EQUITY_INR_PAIR_REQUIRED")
        elif any(max(_utc(b.provenance.received_at), _utc(b.end_time)) > as_of for b in bars):
            reasons.append("DAILY_PRICE_EVIDENCE_AFTER_AS_OF")
        elif any(b.volume is None or b.volume <= 0 for b in bars):
            reasons.append("OPEN_OR_PRIOR_SESSION_NO_TRADE")
        elif any(not x.is_finite() or x <= 0 for x in (bars[0].close, bars[1].open)):
            reasons.append("INVALID_OPEN_OR_PRIOR_CLOSE")
        else:
            close, opening = bars[0].close, bars[1].open
            with localcontext(Context(prec=34)):
                gap = opening - close
                percent = (opening / close - Decimal(1)) * Decimal(100)
            status = OpeningGapStatus.GAP_UP if gap > 0 else OpeningGapStatus.GAP_DOWN if gap < 0 else OpeningGapStatus.FLAT
    if status is OpeningGapStatus.INSUFFICIENT_DATA and any("CONFLICT" in reason or "AMBIGUOUS" in reason for reason in reasons):
        status = OpeningGapStatus.CONFLICTED
    return dict(previous_session=previous, prior_decision_cutoff=lower, event_window_end=upper,
                status=status, previous_close=close, current_open=opening, gap_inr=gap, gap_pct=percent,
                event_references=ordered, blockers=tuple(sorted(set(reasons))))


@dataclass(frozen=True, slots=True)
class OpeningOvernightEvidenceSource:
    """Existing Brain source interface; no new store, domain, or runtime job.

    Only the exact evaluated cutoff is exposed. A caller rebuilds the pure
    projection for another cutoff; this adapter cannot backdate an artifact.
    """
    value: OpeningOvernightState

    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime):
        value = self.value
        value.verify()
        request = value.daily_read.request
        if canonical_instrument_id != request.canonical_instrument_id or _utc(as_of) != _utc(request.evaluation_as_of):
            return ()
        availability = Availability.PARTIAL if value.gap_inr is not None else Availability.UNAVAILABLE
        if value.status is OpeningGapStatus.CONFLICTED or "OVERNIGHT_EVENT_EVIDENCE_CONFLICTED" in value.blockers:
            availability = Availability.CONFLICTED
        return (StoredIntelligenceArtifact(
            canonical_instrument_id, Domain.MARKET_DATA, value.artifact_id, value.fingerprint,
            availability, _utc(as_of), _utc(as_of), _utc(as_of), FreshnessStatus.UNKNOWN, None,
            value.daily_read.fingerprint, value.calendar.fingerprint, IntelligenceInvalidationDomain.PRICE,
            value.blockers,
        ),)


def serialize_opening_overnight(value: OpeningOvernightState) -> str:
    value.verify()
    return _json(_payload(value) | {"fingerprint": value.fingerprint})


def _payload(value):
    return _payload_values({f.name: getattr(value, f.name) for f in fields(value) if f.name != "fingerprint"})


def _payload_values(values):
    return {"contract": CONTRACT, **{k: (json.loads(serialize_nse_udiff_certified_daily_technical_read(v))
             if k == "daily_read" else v.fingerprint if k == "calendar" else _scalar(v)) for k, v in values.items()}}


def _scalar(value):
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, tuple):
        return [_scalar(v) for v in value]
    if is_dataclass(value):
        return {f.name: _scalar(getattr(value, f.name)) for f in fields(value)}
    return value


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("OPENING_OVERNIGHT_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value):
    return "sha256:" + sha256(_json(value).encode()).hexdigest()
