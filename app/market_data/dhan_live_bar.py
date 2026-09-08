"""Prospective, Dhan-v2 quote-derived one-minute market-bar evidence.

This module deliberately sits *before* canonical intraday technical inputs.  It
uses the existing Dhan credential and WebSocket boundary, but it neither starts
a background feed nor wires a reader, strategy, API, UI, portfolio, order, or
broker surface.  Callers inject received times and session evidence explicitly;
there is no hidden historical clock or retrospective bar construction.

Only final, fully observed one-minute receipts are eligible for durable
retention.  Raw packet retention is intentionally outside this contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
import struct
from typing import Callable, Iterable, Protocol
from zoneinfo import ZoneInfo

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    CalendarResolutionReason,
    SessionPhaseType,
    TradingDayState,
)
from app.market_data.dhan import DHAN_PROVIDER, DhanAuthError, DhanCredentialService
from app.market_data.dhan_live import (
    DhanLiveConnectDiagnostic,
    diagnose_dhan_live_failure,
    dhan_live_websocket_url,
    open_dhan_live_transport,
    parse_dhan_disconnect_packet,
)
from app.market_data.models import AdjustmentStatus, Exchange
from app.market_data.technical_bar_contract import TechnicalTradingPeriod
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "prospective-dhan-live-bar-foundation"
CONTRACT_VERSION = "v1"
DHAN_V2_LIVE_FEED_DOCUMENTATION = "https://dhanhq.co/docs/v2/live-market-feed/"
DHAN_V2_INSTRUMENT_DOCUMENTATION = "https://dhanhq.co/docs/v2/instruments/"
DHAN_V2_ANNEXURE_DOCUMENTATION = "https://dhanhq.co/docs/v2/annexure/"
DHAN_QUOTE_SUBSCRIBE = 17
DHAN_QUOTE_PACKET = 4
# The official layout is an 8-byte header plus a 42-byte Quote payload
# (4 + 2 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4 + 4).  The documentation's
# byte labels use an inclusive convention, but the documented field sizes make
# the actual wire length 50; the parser follows field sizes, not labels.
DHAN_QUOTE_PACKET_LENGTH = 50
DHAN_DISCONNECT_REQUEST = 12
DHAN_MAX_CONNECTIONS_PER_USER = 5
DHAN_MAX_INSTRUMENTS_PER_CONNECTION = 5000
DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION = 100
_IST = ZoneInfo("Asia/Kolkata")
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_ISIN = re.compile(r"[A-Z0-9]{12}\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class DhanLiveBarError(ValueError):
    """Stable, fail-closed error for prospective live-bar evidence."""


class DhanLiveFeedMode(StrEnum):
    TICKER = "TICKER"
    QUOTE = "QUOTE"
    FULL = "FULL"


class DhanLiveBarConnectionState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    SUBSCRIBED = "SUBSCRIBED"
    DEGRADED = "DEGRADED"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"


class DhanProspectiveEventQuality(StrEnum):
    ACCEPTED = "ACCEPTED"


class DhanSessionBindingState(StrEnum):
    BOUND_REGULAR_SESSION = "BOUND_REGULAR_SESSION"
    OUTSIDE_REGULAR_SESSION = "OUTSIDE_REGULAR_SESSION"
    SESSION_UNAVAILABLE = "SESSION_UNAVAILABLE"


class DhanSessionBindingReason(StrEnum):
    PRE_OPEN_OR_POST_CLOSE_EXCLUDED = "PRE_OPEN_OR_POST_CLOSE_EXCLUDED"
    NON_REGULAR_TRADING_DAY_EXCLUDED = "NON_REGULAR_TRADING_DAY_EXCLUDED"
    SESSION_CALENDAR_UNAVAILABLE = "SESSION_CALENDAR_UNAVAILABLE"
    SESSION_PHASE_UNAVAILABLE = "SESSION_PHASE_UNAVAILABLE"
    SESSION_EVIDENCE_CONFLICTED = "SESSION_EVIDENCE_CONFLICTED"


class DhanProspectiveBarState(StrEnum):
    CLOSED = "CLOSED"
    INCOMPLETE = "INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NO_TRADE_OBSERVED = "NO_TRADE_OBSERVED"


class DhanProspectiveBarReason(StrEnum):
    MID_INTERVAL_START = "MID_INTERVAL_START"
    PROVIDER_GAP = "PROVIDER_GAP"
    VOLUME_BASELINE_UNAVAILABLE = "VOLUME_BASELINE_UNAVAILABLE"
    CUMULATIVE_VOLUME_REGRESSION = "CUMULATIVE_VOLUME_REGRESSION"
    SAME_EVENT_TIME_ORDER_UNRESOLVED = "SAME_EVENT_TIME_ORDER_UNRESOLVED"
    LATE_EVENT_AFTER_FINALIZATION = "LATE_EVENT_AFTER_FINALIZATION"
    NO_TRADE_OBSERVED = "NO_TRADE_OBSERVED"


class DhanProspectiveBarWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class DhanV2LiveProviderContract:
    """Versioned, documentation-backed capability receipt; it has no transport."""

    provider: str
    version: str
    websocket_documentation: str
    instrument_documentation: str
    annexure_documentation: str
    max_connections_per_user: int
    max_instruments_per_connection: int
    max_instruments_per_subscription: int
    request_encoding: str
    response_encoding: str
    endianness: str
    ping_interval_seconds: int
    pong_timeout_seconds: int
    supported_feed_modes: tuple[DhanLiveFeedMode, ...]
    quote_subscribe_request_code: int
    quote_response_code: int
    quote_packet_length: int
    fingerprint: str

    def __post_init__(self) -> None:
        values = _provider_contract_values(self)
        if (
            self.provider != DHAN_PROVIDER
            or self.version != "v2"
            or not all(_https_url(value) for value in (self.websocket_documentation, self.instrument_documentation, self.annexure_documentation))
            or (self.max_connections_per_user, self.max_instruments_per_connection, self.max_instruments_per_subscription) != (5, 5000, 100)
            or (self.request_encoding, self.response_encoding, self.endianness) != ("JSON", "BINARY", "LITTLE_ENDIAN")
            or (self.ping_interval_seconds, self.pong_timeout_seconds) != (10, 40)
            or self.supported_feed_modes != (
                DhanLiveFeedMode.TICKER,
                DhanLiveFeedMode.QUOTE,
                DhanLiveFeedMode.FULL,
            )
            or (self.quote_subscribe_request_code, self.quote_response_code, self.quote_packet_length) != (17, 4, 50)
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("DHAN_V2_LIVE_PROVIDER_CONTRACT_INVALID")


def dhan_v2_live_provider_contract() -> DhanV2LiveProviderContract:
    values = dict(
        provider=DHAN_PROVIDER,
        version="v2",
        websocket_documentation=DHAN_V2_LIVE_FEED_DOCUMENTATION,
        instrument_documentation=DHAN_V2_INSTRUMENT_DOCUMENTATION,
        annexure_documentation=DHAN_V2_ANNEXURE_DOCUMENTATION,
        max_connections_per_user=DHAN_MAX_CONNECTIONS_PER_USER,
        max_instruments_per_connection=DHAN_MAX_INSTRUMENTS_PER_CONNECTION,
        max_instruments_per_subscription=DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION,
        request_encoding="JSON",
        response_encoding="BINARY",
        endianness="LITTLE_ENDIAN",
        ping_interval_seconds=10,
        pong_timeout_seconds=40,
        supported_feed_modes=(
            DhanLiveFeedMode.TICKER,
            DhanLiveFeedMode.QUOTE,
            DhanLiveFeedMode.FULL,
        ),
        quote_subscribe_request_code=DHAN_QUOTE_SUBSCRIBE,
        quote_response_code=DHAN_QUOTE_PACKET,
        quote_packet_length=DHAN_QUOTE_PACKET_LENGTH,
    )
    return DhanV2LiveProviderContract(**values, fingerprint=_digest(_provider_contract_values(values)))


@dataclass(frozen=True, slots=True)
class DhanProspectiveInstrumentIdentity:
    """Exact, ISIN-backed address of one ordinary NSE equity in Dhan V2."""

    canonical_security_id: str
    isin: str
    provider_security_id: int
    exchange_segment: str
    series: str
    master_fingerprint: str
    provider_version: str = "dhan-v2-detailed-master"

    def __post_init__(self) -> None:
        if (
            not _identifier(self.canonical_security_id)
            or not isinstance(self.isin, str)
            or _ISIN.fullmatch(self.isin) is None
            or self.provider_security_id <= 0
            or self.exchange_segment != "NSE_EQ"
            or self.series != "EQ"
            or not _fingerprint(self.master_fingerprint)
            or self.provider_version != "dhan-v2-detailed-master"
        ):
            raise DhanLiveBarError("DHAN_PROSPECTIVE_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class DhanQuotePacket:
    """Only officially documented fields from an exact Dhan v2 Quote packet."""

    exchange_segment_code: int
    security_id: int
    latest_traded_price: Decimal
    last_traded_quantity: int | None
    last_trade_time: datetime
    average_trade_price: Decimal | None
    cumulative_session_volume: int | None
    day_open: Decimal | None
    day_close: Decimal | None
    day_high: Decimal | None
    day_low: Decimal | None

    def __post_init__(self) -> None:
        if (
            self.exchange_segment_code != 1
            or self.security_id <= 0
            or self.latest_traded_price <= 0
            or (self.last_traded_quantity is not None and self.last_traded_quantity < 0)
            or not _aware(self.last_trade_time)
            or self.last_trade_time.tzinfo is not UTC
            or (self.cumulative_session_volume is not None and self.cumulative_session_volume < 0)
        ):
            raise DhanLiveBarError("DHAN_QUOTE_PACKET_INVALID")


def parse_dhan_quote_packets(frame: bytes) -> tuple[DhanQuotePacket, ...]:
    """Parse concatenated documented Quote packets, strictly little-endian."""
    if not isinstance(frame, bytes) or not frame:
        raise DhanLiveBarError("DHAN_QUOTE_PACKET_MALFORMED")
    result: list[DhanQuotePacket] = []
    offset = 0
    while offset < len(frame):
        if len(frame) - offset < 8:
            raise DhanLiveBarError("DHAN_QUOTE_PACKET_TRUNCATED")
        response_code, length, segment, security_id = struct.unpack_from("<BhBi", frame, offset)
        if response_code != DHAN_QUOTE_PACKET:
            raise DhanLiveBarError("DHAN_QUOTE_PACKET_UNSUPPORTED")
        if length != DHAN_QUOTE_PACKET_LENGTH or len(frame) - offset < length:
            raise DhanLiveBarError("DHAN_QUOTE_PACKET_LENGTH_INVALID")
        values = struct.unpack_from("<fhifiiiffff", frame, offset + 8)
        (
            ltp, last_quantity, event_epoch, atp, volume,
            _total_sell, _total_buy, day_open, day_close, day_high, day_low,
        ) = values
        if ltp <= 0 or event_epoch <= 0 or last_quantity < 0 or volume < 0:
            raise DhanLiveBarError("DHAN_QUOTE_PACKET_VALUE_INVALID")
        result.append(DhanQuotePacket(
            segment, security_id, Decimal(str(ltp)), last_quantity,
            datetime.fromtimestamp(event_epoch, UTC), _positive_decimal(atp), volume,
            _positive_decimal(day_open), _positive_decimal(day_close),
            _positive_decimal(day_high), _positive_decimal(day_low),
        ))
        offset += length
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DhanProspectiveMarketEvent:
    """Provider-neutral prospective observation preserving event and receipt time."""

    canonical_security_id: str
    isin: str
    provider: str
    provider_security_id: int
    exchange_segment: str
    series: str
    packet_type: str
    last_traded_price: Decimal
    event_time: datetime
    received_at: datetime
    cumulative_session_volume: int | None
    last_traded_quantity: int | None
    connection_id: str
    provider_version: str
    master_fingerprint: str
    quality: DhanProspectiveEventQuality
    event_identity: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _event_values(self)
        if (
            not _identifier(self.canonical_security_id)
            or _ISIN.fullmatch(self.isin) is None
            or self.provider != DHAN_PROVIDER
            or self.provider_security_id <= 0
            or self.exchange_segment != "NSE_EQ"
            or self.series != "EQ"
            or self.packet_type != "QUOTE"
            or self.last_traded_price <= 0
            or not _aware(self.event_time)
            or not _aware(self.received_at)
            or self.event_time.tzinfo is not UTC
            or self.received_at.tzinfo is not UTC
            or _utc(self.event_time) > _utc(self.received_at)
            or (self.cumulative_session_volume is not None and self.cumulative_session_volume < 0)
            or (self.last_traded_quantity is not None and self.last_traded_quantity < 0)
            or not _identifier(self.connection_id)
            or self.provider_version != "dhan-v2-live-quote"
            or not _fingerprint(self.master_fingerprint)
            or self.quality is not DhanProspectiveEventQuality.ACCEPTED
            or self.event_identity != _event_identity(values)
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("DHAN_PROSPECTIVE_EVENT_INVALID")


def normalize_dhan_quote_packet(
    packet: DhanQuotePacket,
    *,
    identity: DhanProspectiveInstrumentIdentity,
    received_at: datetime,
    connection_id: str,
) -> DhanProspectiveMarketEvent:
    """Normalize one exact-mapped Quote packet without retaining credentials."""
    if not isinstance(packet, DhanQuotePacket) or not isinstance(identity, DhanProspectiveInstrumentIdentity):
        raise DhanLiveBarError("DHAN_QUOTE_NORMALIZATION_INPUT_INVALID")
    if packet.exchange_segment_code != 1 or packet.security_id != identity.provider_security_id:
        raise DhanLiveBarError("DHAN_QUOTE_EXACT_IDENTITY_REQUIRED")
    values = dict(
        canonical_security_id=identity.canonical_security_id,
        isin=identity.isin.upper(),
        provider=DHAN_PROVIDER,
        provider_security_id=identity.provider_security_id,
        exchange_segment=identity.exchange_segment,
        series=identity.series,
        packet_type="QUOTE",
        last_traded_price=packet.latest_traded_price,
        event_time=_utc(packet.last_trade_time),
        received_at=_utc_required(received_at),
        cumulative_session_volume=packet.cumulative_session_volume,
        last_traded_quantity=packet.last_traded_quantity,
        connection_id=connection_id,
        provider_version="dhan-v2-live-quote",
        master_fingerprint=identity.master_fingerprint,
        quality=DhanProspectiveEventQuality.ACCEPTED,
    )
    values["event_identity"] = _event_identity(values)
    return DhanProspectiveMarketEvent(**values, fingerprint=_digest(_event_values(values)))


def quote_subscription_messages(identities: tuple[DhanProspectiveInstrumentIdentity, ...]) -> tuple[str, ...]:
    """Deterministic Quote-mode batches within the official single-connection limit."""
    identities = _canonical_identity_set(identities)
    if len(identities) > DHAN_MAX_INSTRUMENTS_PER_CONNECTION:
        raise DhanLiveBarError("DHAN_CONNECTION_CAPACITY_EXCEEDED")
    messages: list[str] = []
    for start in range(0, len(identities), DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION):
        batch = identities[start:start + DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION]
        messages.append(json.dumps({
            "RequestCode": DHAN_QUOTE_SUBSCRIBE,
            "InstrumentCount": len(batch),
            "InstrumentList": [
                {"ExchangeSegment": item.exchange_segment, "SecurityId": str(item.provider_security_id)}
                for item in batch
            ],
        }, sort_keys=True, separators=(",", ":")))
    return tuple(messages)


@dataclass(frozen=True, slots=True)
class DhanQuoteSubscriptionPlan:
    mapped_instrument_count: int
    messages_required: int
    single_connection_capacity: int
    fits_one_connection: bool
    fingerprint: str

    def __post_init__(self) -> None:
        values = dict(
            mapped_instrument_count=self.mapped_instrument_count,
            messages_required=self.messages_required,
            single_connection_capacity=self.single_connection_capacity,
            fits_one_connection=self.fits_one_connection,
        )
        expected_messages = (self.mapped_instrument_count + DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION - 1) // DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION
        if (
            self.mapped_instrument_count < 0
            or self.messages_required != expected_messages
            or self.single_connection_capacity != DHAN_MAX_INSTRUMENTS_PER_CONNECTION
            or self.fits_one_connection != (self.mapped_instrument_count <= DHAN_MAX_INSTRUMENTS_PER_CONNECTION)
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("DHAN_QUOTE_SUBSCRIPTION_PLAN_INVALID")


def plan_dhan_quote_subscription(identities: tuple[DhanProspectiveInstrumentIdentity, ...]) -> DhanQuoteSubscriptionPlan:
    identities = _canonical_identity_set(identities)
    values = dict(
        mapped_instrument_count=len(identities),
        messages_required=(len(identities) + DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION - 1) // DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION,
        single_connection_capacity=DHAN_MAX_INSTRUMENTS_PER_CONNECTION,
        fits_one_connection=len(identities) <= DHAN_MAX_INSTRUMENTS_PER_CONNECTION,
    )
    return DhanQuoteSubscriptionPlan(**values, fingerprint=_digest(values))


@dataclass(frozen=True, slots=True)
class DhanRegularMinuteBinding:
    state: DhanSessionBindingState
    reason: DhanSessionBindingReason | None
    period: TechnicalTradingPeriod | None
    session_id: str | None
    interval_start: datetime | None
    interval_end: datetime | None
    fingerprint: str

    def __post_init__(self) -> None:
        values = _binding_values(self)
        bound = self.state is DhanSessionBindingState.BOUND_REGULAR_SESSION
        if (
            not isinstance(self.state, DhanSessionBindingState)
            or (bound and (self.reason is not None or self.period is None or not _identifier(self.session_id or "") or not _aware(self.interval_start) or not _aware(self.interval_end) or self.interval_end - self.interval_start != timedelta(minutes=1)))
            or (not bound and (self.reason is None or self.period is not None or self.session_id is not None or self.interval_start is not None or self.interval_end is not None))
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("DHAN_REGULAR_MINUTE_BINDING_INVALID")


def bind_dhan_event_to_regular_minute(
    event: DhanProspectiveMarketEvent,
    *,
    calendar: CanonicalMarketSessionCalendar,
) -> DhanRegularMinuteBinding:
    """Bind only a source-backed ordinary NSE regular-session minute.

    The calendar is resolved at ``received_at``.  It therefore never grants
    retrospective knowledge to a historical event based on a later calendar
    retrieval, and it never uses Dhan's market-status packets as exchange
    session authority.
    """
    if not isinstance(event, DhanProspectiveMarketEvent) or not isinstance(calendar, CanonicalMarketSessionCalendar):
        raise DhanLiveBarError("DHAN_REGULAR_MINUTE_BINDING_INPUT_INVALID")
    local_event = _utc(event.event_time).astimezone(_IST)
    day = calendar.resolve_trading_day(local_event.date(), as_of=event.received_at)
    if day.state is TradingDayState.UNKNOWN:
        reason = (
            DhanSessionBindingReason.SESSION_EVIDENCE_CONFLICTED
            if CalendarResolutionReason.EVIDENCE_CONFLICTED in day.reasons
            else DhanSessionBindingReason.SESSION_CALENDAR_UNAVAILABLE
        )
        return _unbound_binding(DhanSessionBindingState.SESSION_UNAVAILABLE, reason)
    if day.state is not TradingDayState.REGULAR_TRADING_DAY:
        return _unbound_binding(DhanSessionBindingState.OUTSIDE_REGULAR_SESSION, DhanSessionBindingReason.NON_REGULAR_TRADING_DAY_EXCLUDED)
    phases = tuple(value for value in calendar.phases_for(local_event.date(), as_of=event.received_at) if value.phase_type is SessionPhaseType.REGULAR_CONTINUOUS)
    if len(phases) != 1:
        reason = DhanSessionBindingReason.SESSION_EVIDENCE_CONFLICTED if len(phases) > 1 else DhanSessionBindingReason.SESSION_PHASE_UNAVAILABLE
        return _unbound_binding(DhanSessionBindingState.SESSION_UNAVAILABLE, reason)
    phase = phases[0]
    if not phase.starts_at <= local_event < phase.ends_at:
        return _unbound_binding(DhanSessionBindingState.OUTSIDE_REGULAR_SESSION, DhanSessionBindingReason.PRE_OPEN_OR_POST_CLOSE_EXCLUDED)
    local_start = local_event.replace(second=0, microsecond=0)
    local_end = local_start + timedelta(minutes=1)
    if local_end > phase.ends_at:
        return _unbound_binding(DhanSessionBindingState.OUTSIDE_REGULAR_SESSION, DhanSessionBindingReason.PRE_OPEN_OR_POST_CLOSE_EXCLUDED)
    # ``TechnicalTradingPeriod`` intentionally stores parallel, de-duplicated
    # source-id and fingerprint sequences.  The canonical calendar fingerprint
    # retains the selected regular phase.  Retaining the day decision's source
    # sequences here avoids representing one source id twice with two different
    # calendar-level fingerprints, which that contract correctly rejects.
    sources_ids = tuple(sorted(set(day.source_ids)))
    source_fingerprints = tuple(sorted(set(day.source_fingerprints)))
    period_id = f"nse-regular-1m:{local_event.date().isoformat()}:{phase.timing_id}:{local_start.strftime('%H%M')}"
    period = TechnicalTradingPeriod(
        venue=Exchange.NSE,
        segment="CAPITAL_MARKET",
        period_id=period_id,
        session_dates=(local_event.date(),),
        starts_at=local_start,
        ends_at=local_end,
        timezone_id="Asia/Kolkata",
        calendar_id=calendar.calendar_id,
        calendar_fingerprint=calendar.fingerprint,
        session_source_ids=sources_ids,
        session_source_fingerprints=source_fingerprints,
    )
    values = dict(
        state=DhanSessionBindingState.BOUND_REGULAR_SESSION,
        reason=None,
        period=period,
        session_id=f"nse-regular:{local_event.date().isoformat()}:{phase.timing_id}",
        interval_start=_utc(local_start),
        interval_end=_utc(local_end),
    )
    return DhanRegularMinuteBinding(**values, fingerprint=_digest(_binding_values(values)))


@dataclass(frozen=True, slots=True)
class ProspectiveDhanOneMinuteBar:
    """A completed prospective raw-as-traded minute, not an active technical input."""

    bar_id: str
    instrument: DhanProspectiveInstrumentIdentity
    session_id: str
    period: TechnicalTradingPeriod
    interval_start: datetime
    interval_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    event_count: int
    first_event_time: datetime
    last_event_time: datetime
    first_received_at: datetime
    last_received_at: datetime
    known_at: datetime
    event_set_fingerprint: str
    source_basis: str
    adjustment_status: AdjustmentStatus
    fingerprint: str

    def __post_init__(self) -> None:
        values = _bar_values(self)
        if (
            not _identifier(self.bar_id)
            or not isinstance(self.instrument, DhanProspectiveInstrumentIdentity)
            or not _identifier(self.session_id)
            or not isinstance(self.period, TechnicalTradingPeriod)
            or not all(_aware(value) for value in (self.interval_start, self.interval_end, self.first_event_time, self.last_event_time, self.first_received_at, self.last_received_at, self.known_at))
            or self.interval_end - self.interval_start != timedelta(minutes=1)
            or (self.period.starts_at.astimezone(UTC), self.period.ends_at.astimezone(UTC)) != (_utc(self.interval_start), _utc(self.interval_end))
            or self.event_count < 1
            or self.volume <= 0
            or self.open <= 0 or self.low <= 0 or self.high <= 0 or self.close <= 0
            or self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high
            or self.first_event_time > self.last_event_time
            or self.first_received_at > self.last_received_at
            or self.known_at < self.interval_end or self.known_at < self.last_received_at
            or not _fingerprint(self.event_set_fingerprint)
            or self.source_basis != "RAW_AS_TRADED"
            or self.adjustment_status is not AdjustmentStatus.RAW
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("PROSPECTIVE_DHAN_ONE_MINUTE_BAR_INVALID")


@dataclass(frozen=True, slots=True)
class ProspectiveDhanMinuteReceipt:
    """Durable immutable minute result; incomplete receipts never carry a bar."""

    receipt_id: str
    instrument: DhanProspectiveInstrumentIdentity
    session_id: str
    period: TechnicalTradingPeriod
    interval_start: datetime
    interval_end: datetime
    state: DhanProspectiveBarState
    reasons: tuple[DhanProspectiveBarReason, ...]
    observed_event_count: int
    known_at: datetime
    bar: ProspectiveDhanOneMinuteBar | None
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reasons), key=lambda value: value.value))
        values = _receipt_values(self, reasons=reasons)
        closed = self.state is DhanProspectiveBarState.CLOSED
        if (
            not _identifier(self.receipt_id)
            or not isinstance(self.instrument, DhanProspectiveInstrumentIdentity)
            or not _identifier(self.session_id)
            or not isinstance(self.period, TechnicalTradingPeriod)
            or not _aware(self.interval_start) or not _aware(self.interval_end) or not _aware(self.known_at)
            or self.interval_end - self.interval_start != timedelta(minutes=1)
            or self.known_at < self.interval_end
            or self.observed_event_count < 0
            or self.reasons != reasons
            or any(not isinstance(value, DhanProspectiveBarReason) for value in reasons)
            or (closed and (self.bar is None or reasons or self.observed_event_count != self.bar.event_count or self.receipt_id != self.bar.bar_id or self.known_at != self.bar.known_at))
            or (not closed and self.bar is not None)
            or (self.state is DhanProspectiveBarState.NO_TRADE_OBSERVED and (self.observed_event_count != 0 or reasons != (DhanProspectiveBarReason.NO_TRADE_OBSERVED,)))
            or (self.state is not DhanProspectiveBarState.NO_TRADE_OBSERVED and not closed and not reasons)
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class ProspectiveDhanMinuteConflict:
    conflict_id: str
    receipt_id: str
    stored_fingerprint: str
    incoming_fingerprint: str
    detected_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        values = dict(
            conflict_id=self.conflict_id,
            receipt_id=self.receipt_id,
            stored_fingerprint=self.stored_fingerprint,
            incoming_fingerprint=self.incoming_fingerprint,
            detected_at=_utc(self.detected_at) if _aware(self.detected_at) else self.detected_at,
        )
        if (
            not _identifier(self.conflict_id)
            or not _identifier(self.receipt_id)
            or not _fingerprint(self.stored_fingerprint)
            or not _fingerprint(self.incoming_fingerprint)
            or self.stored_fingerprint == self.incoming_fingerprint
            or not _aware(self.detected_at)
            or self.fingerprint != _digest(values)
        ):
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_CONFLICT_INVALID")


class ProspectiveDhanMinuteStore:
    """Append-only persistence over existing immutable core snapshots only."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, receipt: ProspectiveDhanMinuteReceipt, *, detected_at: datetime) -> DhanProspectiveBarWriteOutcome:
        if not isinstance(receipt, ProspectiveDhanMinuteReceipt) or receipt.state is DhanProspectiveBarState.NO_TRADE_OBSERVED:
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_PERSISTENCE_INPUT_INVALID")
        _utc_required(detected_at)
        snapshot_id = f"prospective-dhan-one-minute:{receipt.receipt_id}"
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is None:
            self._repository.save_snapshot(CoreApiSnapshot(
                snapshot_id, CoreApiSnapshotFamily.PROSPECTIVE_DHAN_ONE_MINUTE_BAR,
                "v1", "prospective-dhan-one-minute-receipt-v1", receipt.fingerprint,
                receipt.known_at, receipt,
            ))
            return DhanProspectiveBarWriteOutcome.INSERTED
        if not isinstance(existing.payload, ProspectiveDhanMinuteReceipt):
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_STORAGE_TYPE_INVALID")
        if existing.payload == receipt:
            return DhanProspectiveBarWriteOutcome.ALREADY_PRESENT
        conflict = _minute_conflict(existing.payload, receipt, detected_at=detected_at)
        conflict_snapshot_id = f"prospective-dhan-one-minute-conflict:{conflict.conflict_id}"
        retained = self._repository.get_snapshot(conflict_snapshot_id)
        if retained is None:
            self._repository.save_snapshot(CoreApiSnapshot(
                conflict_snapshot_id, CoreApiSnapshotFamily.PROSPECTIVE_DHAN_ONE_MINUTE_CONFLICT,
                "v1", "prospective-dhan-one-minute-conflict-v1", conflict.fingerprint,
                conflict.detected_at, conflict,
            ))
        elif retained.payload != conflict:
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_CONFLICT_IMMUTABLE_COLLISION")
        return DhanProspectiveBarWriteOutcome.CONFLICT

    def get(self, receipt_id: str) -> ProspectiveDhanMinuteReceipt | None:
        value = self._repository.get_snapshot(f"prospective-dhan-one-minute:{receipt_id}")
        if value is None:
            return None
        if not isinstance(value.payload, ProspectiveDhanMinuteReceipt):
            raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_STORAGE_TYPE_INVALID")
        return value.payload


@dataclass(frozen=True, slots=True)
class DhanQuoteFeedProbe:
    state: DhanLiveBarConnectionState
    requested_instruments: int
    subscribed_messages: int
    normalized_events: tuple[DhanProspectiveMarketEvent, ...]
    diagnostic: DhanLiveConnectDiagnostic


class _QuoteTransport(Protocol):
    def send(self, payload: str) -> None: ...
    def recv(self) -> bytes: ...
    def close(self) -> None: ...


class DhanProspectiveQuoteFeedAdapter:
    """A bounded, non-trading Quote subscription adapter with injected clock.

    It performs no persistence.  The caller may pass normalized observations to
    the bar builder only after separately binding them to canonical NSE session
    evidence.  Credentials remain inside the existing credential service and
    are never returned in this model or in its diagnostics.
    """

    def __init__(
        self,
        credentials: DhanCredentialService,
        *,
        identities: tuple[DhanProspectiveInstrumentIdentity, ...],
        clock: Callable[[], datetime],
        transport_factory: Callable[[str], _QuoteTransport] | None = None,
    ) -> None:
        identities = _canonical_identity_set(identities)
        self._credentials = credentials
        self._identities = identities
        self._clock = clock
        self._transport_factory = transport_factory or (lambda url: open_dhan_live_transport(url, timeout_seconds=15))

    def bounded_probe(self, *, connection_id: str, max_frames: int = 1) -> DhanQuoteFeedProbe:
        if not _identifier(connection_id) or max_frames < 0:
            raise DhanLiveBarError("DHAN_QUOTE_PROBE_INPUT_INVALID")
        try:
            credentials = dict(self._credentials.access_credentials())
        except DhanAuthError:
            return DhanQuoteFeedProbe(
                DhanLiveBarConnectionState.FAILED, len(self._identities), 0, (),
                DhanLiveConnectDiagnostic(False, "AUTH", "REAUTH_REQUIRED"),
            )
        transport: _QuoteTransport | None = None
        messages = quote_subscription_messages(self._identities)
        lookup = {item.provider_security_id: item for item in self._identities}
        events: list[DhanProspectiveMarketEvent] = []
        try:
            transport = self._transport_factory(dhan_live_websocket_url(credentials))
            for message in messages:
                transport.send(message)
            for _ in range(max_frames):
                frame = transport.recv()
                disconnect = parse_dhan_disconnect_packet(frame)
                if disconnect is not None:
                    return DhanQuoteFeedProbe(DhanLiveBarConnectionState.DEGRADED, len(self._identities), len(messages), tuple(events), disconnect)
                # Quote subscriptions may also emit documented previous-close,
                # OI, or market-status packets.  They are not prospective
                # trade/volume observations, so this quote-only adapter ignores
                # them rather than misparsing or promoting them.
                if not frame or frame[0] != DHAN_QUOTE_PACKET:
                    continue
                received_at = _utc_required(self._clock())
                for packet in parse_dhan_quote_packets(frame):
                    identity = lookup.get(packet.security_id)
                    if identity is not None:
                        events.append(normalize_dhan_quote_packet(packet, identity=identity, received_at=received_at, connection_id=connection_id))
            return DhanQuoteFeedProbe(
                DhanLiveBarConnectionState.SUBSCRIBED, len(self._identities), len(messages), tuple(events),
                DhanLiveConnectDiagnostic(True, "SUBSCRIBED", "CONNECTED"),
            )
        except Exception as error:
            return DhanQuoteFeedProbe(
                DhanLiveBarConnectionState.FAILED, len(self._identities), len(messages), tuple(events),
                diagnose_dhan_live_failure(error),
            )
        finally:
            if transport is not None:
                try:
                    transport.send(json.dumps({"RequestCode": DHAN_DISCONNECT_REQUEST}, separators=(",", ":")))
                except Exception:
                    pass
                transport.close()


@dataclass(slots=True)
class _OpenMinute:
    binding: DhanRegularMinuteBinding
    connection_started_at: datetime
    events: list[DhanProspectiveMarketEvent]
    semantic_event_ids: set[str]
    reasons: set[DhanProspectiveBarReason]


class ProspectiveDhanOneMinuteBarBuilder:
    """Deterministically constructs only complete, continuously observed minutes."""

    def __init__(self) -> None:
        self._connections: dict[str, datetime] = {}
        self._gaps: list[tuple[str, datetime, datetime]] = []
        self._open: dict[str, _OpenMinute] = {}
        self._events_by_security_session: dict[tuple[str, str], list[DhanProspectiveMarketEvent]] = {}
        self._finalized: set[str] = set()

    def begin_connection(self, *, connection_id: str, observed_at: datetime) -> None:
        moment = _utc_required(observed_at)
        if not _identifier(connection_id) or connection_id in self._connections:
            raise DhanLiveBarError("DHAN_PROSPECTIVE_CONNECTION_INVALID")
        self._connections[connection_id] = moment

    def record_gap(self, *, connection_id: str, disconnected_at: datetime, reconnected_at: datetime) -> None:
        start, end = _utc_required(disconnected_at), _utc_required(reconnected_at)
        if connection_id not in self._connections or end <= start:
            raise DhanLiveBarError("DHAN_PROSPECTIVE_GAP_INVALID")
        self._gaps.append((connection_id, start, end))

    def observe(self, event: DhanProspectiveMarketEvent, *, binding: DhanRegularMinuteBinding) -> str:
        if not isinstance(event, DhanProspectiveMarketEvent) or not isinstance(binding, DhanRegularMinuteBinding):
            raise DhanLiveBarError("DHAN_PROSPECTIVE_OBSERVATION_INPUT_INVALID")
        if binding.state is not DhanSessionBindingState.BOUND_REGULAR_SESSION:
            return "SESSION_EXCLUDED"
        assert binding.interval_start is not None and binding.interval_end is not None and binding.period is not None and binding.session_id is not None
        if event.connection_id not in self._connections or event.received_at < self._connections[event.connection_id]:
            raise DhanLiveBarError("DHAN_PROSPECTIVE_CONNECTION_UNOBSERVED")
        if not binding.interval_start <= event.event_time < binding.interval_end:
            raise DhanLiveBarError("DHAN_PROSPECTIVE_EVENT_INTERVAL_MISMATCH")
        receipt_id = prospective_dhan_minute_identity(event.canonical_security_id, binding.session_id, binding.interval_start, binding.interval_end)
        if receipt_id in self._finalized:
            return DhanProspectiveBarReason.LATE_EVENT_AFTER_FINALIZATION.value
        entry = self._open.get(receipt_id)
        if entry is None:
            entry = _OpenMinute(binding, self._connections[event.connection_id], [], set(), set())
            self._open[receipt_id] = entry
        if event.event_identity in entry.semantic_event_ids:
            return "DUPLICATE"
        entry.semantic_event_ids.add(event.event_identity)
        entry.events.append(event)
        if entry.connection_started_at > binding.interval_start:
            entry.reasons.add(DhanProspectiveBarReason.MID_INTERVAL_START)
        if any(
            gap_connection_id == event.connection_id
            and _overlaps(binding.interval_start, binding.interval_end, start, end)
            for gap_connection_id, start, end in self._gaps
        ):
            entry.reasons.add(DhanProspectiveBarReason.PROVIDER_GAP)
        self._events_by_security_session.setdefault((event.canonical_security_id, binding.session_id), []).append(event)
        return "ACCEPTED"

    def finalize_through(self, *, known_at: datetime) -> tuple[ProspectiveDhanMinuteReceipt, ...]:
        cutoff = _utc_required(known_at)
        values: list[ProspectiveDhanMinuteReceipt] = []
        for receipt_id, entry in sorted(tuple(self._open.items())):
            assert entry.binding.interval_end is not None
            if entry.binding.interval_end <= cutoff:
                values.append(self._finalize(receipt_id, entry, known_at=cutoff))
                del self._open[receipt_id]
                self._finalized.add(receipt_id)
        return tuple(values)

    def no_trade_receipt(self, *, identity: DhanProspectiveInstrumentIdentity, binding: DhanRegularMinuteBinding, known_at: datetime) -> ProspectiveDhanMinuteReceipt:
        """Represent a proven no-trade interval without fabricating a zero-price bar.

        This helper does not persist the receipt; broad no-trade retention needs
        its own policy before it can become a whole-market storage operation.
        """
        cutoff = _utc_required(known_at)
        if binding.state is not DhanSessionBindingState.BOUND_REGULAR_SESSION or binding.interval_start is None or binding.interval_end is None or binding.period is None or binding.session_id is None or cutoff < binding.interval_end:
            raise DhanLiveBarError("DHAN_NO_TRADE_RECEIPT_INPUT_INVALID")
        receipt_id = prospective_dhan_minute_identity(identity.canonical_security_id, binding.session_id, binding.interval_start, binding.interval_end)
        values = dict(
            receipt_id=receipt_id, instrument=identity, session_id=binding.session_id, period=binding.period,
            interval_start=binding.interval_start, interval_end=binding.interval_end,
            state=DhanProspectiveBarState.NO_TRADE_OBSERVED,
            reasons=(DhanProspectiveBarReason.NO_TRADE_OBSERVED,), observed_event_count=0,
            known_at=cutoff, bar=None,
        )
        return ProspectiveDhanMinuteReceipt(**values, fingerprint=_digest(_receipt_values(values)))

    def _finalize(self, receipt_id: str, entry: _OpenMinute, *, known_at: datetime) -> ProspectiveDhanMinuteReceipt:
        binding = entry.binding
        assert binding.period is not None and binding.session_id is not None and binding.interval_start is not None and binding.interval_end is not None
        reasons = set(entry.reasons)
        events = tuple(sorted(entry.events, key=_event_order_key))
        if any(_same_timestamp_price_conflict(left, right) for left, right in zip(events, events[1:])):
            reasons.add(DhanProspectiveBarReason.SAME_EVENT_TIME_ORDER_UNRESOLVED)
        baseline = self._volume_baseline(events[0], binding.interval_start, binding.session_id)
        if baseline is None:
            reasons.add(DhanProspectiveBarReason.VOLUME_BASELINE_UNAVAILABLE)
        elif _volume_regresses(events, baseline):
            reasons.add(DhanProspectiveBarReason.CUMULATIVE_VOLUME_REGRESSION)
        if reasons:
            state = DhanProspectiveBarState.EVIDENCE_CONFLICTED if DhanProspectiveBarReason.SAME_EVENT_TIME_ORDER_UNRESOLVED in reasons or DhanProspectiveBarReason.CUMULATIVE_VOLUME_REGRESSION in reasons else DhanProspectiveBarState.INCOMPLETE
            return _incomplete_receipt(
                receipt_id=receipt_id, instrument=events[0], binding=binding, state=state,
                reasons=reasons, event_count=len(events), known_at=known_at,
            )
        assert baseline is not None
        volume = events[-1].cumulative_session_volume - baseline
        if volume <= 0:
            return _incomplete_receipt(
                receipt_id=receipt_id, instrument=events[0], binding=binding, state=DhanProspectiveBarState.INCOMPLETE,
                reasons={DhanProspectiveBarReason.VOLUME_BASELINE_UNAVAILABLE}, event_count=len(events), known_at=known_at,
            )
        first, last = events[0], events[-1]
        if known_at < max(item.received_at for item in events):
            raise DhanLiveBarError("DHAN_PROSPECTIVE_FINALIZATION_BEFORE_RECEIPT")
        identity = _identity_from_event(first)
        bar_values = dict(
            bar_id=receipt_id, instrument=identity, session_id=binding.session_id, period=binding.period,
            interval_start=binding.interval_start, interval_end=binding.interval_end,
            open=first.last_traded_price,
            high=max(item.last_traded_price for item in events),
            low=min(item.last_traded_price for item in events),
            close=last.last_traded_price,
            volume=volume,
            event_count=len(events),
            first_event_time=first.event_time,
            last_event_time=last.event_time,
            first_received_at=min(item.received_at for item in events),
            last_received_at=max(item.received_at for item in events),
            known_at=known_at,
            event_set_fingerprint=_digest([_event_semantic_values(item) for item in events]),
            source_basis="RAW_AS_TRADED",
            adjustment_status=AdjustmentStatus.RAW,
        )
        bar = ProspectiveDhanOneMinuteBar(**bar_values, fingerprint=_digest(_bar_values(bar_values)))
        receipt_values = dict(
            receipt_id=receipt_id, instrument=identity, session_id=binding.session_id, period=binding.period,
            interval_start=binding.interval_start, interval_end=binding.interval_end,
            state=DhanProspectiveBarState.CLOSED, reasons=(), observed_event_count=len(events),
            known_at=bar.known_at, bar=bar,
        )
        return ProspectiveDhanMinuteReceipt(**receipt_values, fingerprint=_digest(_receipt_values(receipt_values)))

    def _volume_baseline(self, event: DhanProspectiveMarketEvent, interval_start: datetime, session_id: str) -> int | None:
        # A reconnect changes the observation continuity boundary.  Borrowing
        # a cumulative-volume observation from an earlier connection could
        # smuggle missed reconnect-period volume into this minute, so only a
        # baseline from this exact continuously observed connection is valid.
        prior = tuple(
            item
            for item in self._events_by_security_session.get((event.canonical_security_id, session_id), ())
            if (
                item.connection_id == event.connection_id
                and item.event_time < interval_start
                and item.cumulative_session_volume is not None
            )
        )
        if not prior:
            return None
        return _event_order_key(max(prior, key=_event_order_key))[1]


def prospective_dhan_minute_identity(canonical_security_id: str, session_id: str, interval_start: datetime, interval_end: datetime) -> str:
    values = dict(
        canonical_security_id=canonical_security_id,
        session_id=session_id,
        interval_start=_utc_required(interval_start),
        interval_end=_utc_required(interval_end),
        provider=DHAN_PROVIDER,
        contract_id=CONTRACT_ID,
        contract_version=CONTRACT_VERSION,
    )
    if not _identifier(canonical_security_id) or not _identifier(session_id) or values["interval_end"] - values["interval_start"] != timedelta(minutes=1):
        raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_IDENTITY_INVALID")
    return "dhan-1m:" + _digest(values).removeprefix("sha256:")[:32]


def _unbound_binding(state: DhanSessionBindingState, reason: DhanSessionBindingReason) -> DhanRegularMinuteBinding:
    values = dict(state=state, reason=reason, period=None, session_id=None, interval_start=None, interval_end=None)
    return DhanRegularMinuteBinding(**values, fingerprint=_digest(_binding_values(values)))


def _incomplete_receipt(
    *, receipt_id: str, instrument: DhanProspectiveMarketEvent, binding: DhanRegularMinuteBinding,
    state: DhanProspectiveBarState, reasons: set[DhanProspectiveBarReason], event_count: int, known_at: datetime,
) -> ProspectiveDhanMinuteReceipt:
    assert binding.period is not None and binding.session_id is not None and binding.interval_start is not None and binding.interval_end is not None
    values = dict(
        receipt_id=receipt_id, instrument=_identity_from_event(instrument), session_id=binding.session_id,
        period=binding.period, interval_start=binding.interval_start, interval_end=binding.interval_end,
        state=state, reasons=tuple(sorted(reasons, key=lambda value: value.value)), observed_event_count=event_count,
        known_at=max(known_at, binding.interval_end), bar=None,
    )
    return ProspectiveDhanMinuteReceipt(**values, fingerprint=_digest(_receipt_values(values)))


def _identity_from_event(value: DhanProspectiveMarketEvent) -> DhanProspectiveInstrumentIdentity:
    return DhanProspectiveInstrumentIdentity(
        value.canonical_security_id, value.isin, value.provider_security_id, value.exchange_segment,
        value.series, value.master_fingerprint,
    )


def _minute_conflict(stored: ProspectiveDhanMinuteReceipt, incoming: ProspectiveDhanMinuteReceipt, *, detected_at: datetime) -> ProspectiveDhanMinuteConflict:
    if stored.receipt_id != incoming.receipt_id:
        raise DhanLiveBarError("PROSPECTIVE_DHAN_MINUTE_CONFLICT_IDENTITY_INVALID")
    values = dict(
        receipt_id=stored.receipt_id,
        stored_fingerprint=stored.fingerprint,
        incoming_fingerprint=incoming.fingerprint,
    )
    conflict_id = "dhan-1m-conflict:" + _digest(values).removeprefix("sha256:")[:32]
    full = dict(conflict_id=conflict_id, **values, detected_at=_utc_required(detected_at))
    return ProspectiveDhanMinuteConflict(**full, fingerprint=_digest(full))


def _canonical_identity_set(
    values: tuple[DhanProspectiveInstrumentIdentity, ...],
) -> tuple[DhanProspectiveInstrumentIdentity, ...]:
    keys = tuple((value.canonical_security_id, value.provider_security_id) for value in values)
    if (
        not values
        or len(set(keys)) != len(keys)
        or len({value.canonical_security_id for value in values}) != len(values)
        or len({value.provider_security_id for value in values}) != len(values)
    ):
        raise DhanLiveBarError("DHAN_PROSPECTIVE_IDENTITY_SET_INVALID")
    return tuple(sorted(values, key=lambda value: (value.canonical_security_id, value.provider_security_id)))


def _volume_regresses(events: tuple[DhanProspectiveMarketEvent, ...], baseline: int) -> bool:
    prior = baseline
    for event in events:
        if event.cumulative_session_volume is None or event.cumulative_session_volume < prior:
            return True
        prior = event.cumulative_session_volume
    return False


def _same_timestamp_price_conflict(left: DhanProspectiveMarketEvent, right: DhanProspectiveMarketEvent) -> bool:
    return (
        left.event_time == right.event_time
        and left.cumulative_session_volume == right.cumulative_session_volume
        and left.last_traded_price != right.last_traded_price
    )


def _event_order_key(value: DhanProspectiveMarketEvent) -> tuple[datetime, int, Decimal, str]:
    return (_utc(value.event_time), value.cumulative_session_volume if value.cumulative_session_volume is not None else -1, value.last_traded_price, value.event_identity)


def _event_semantic_values(value: DhanProspectiveMarketEvent) -> dict[str, object]:
    return {
        "canonical_security_id": value.canonical_security_id,
        "isin": value.isin,
        "provider": value.provider,
        "provider_security_id": value.provider_security_id,
        "exchange_segment": value.exchange_segment,
        "series": value.series,
        "packet_type": value.packet_type,
        "last_traded_price": value.last_traded_price,
        "event_time": value.event_time,
        "cumulative_session_volume": value.cumulative_session_volume,
        "last_traded_quantity": value.last_traded_quantity,
        "provider_version": value.provider_version,
        "master_fingerprint": value.master_fingerprint,
    }


def _event_identity(values: object) -> str:
    if isinstance(values, DhanProspectiveMarketEvent):
        values = _event_semantic_values(values)
    elif isinstance(values, dict):
        values = {key: value for key, value in values.items() if key not in {"received_at", "connection_id", "quality", "event_identity", "fingerprint"}}
    return "dhan-event:" + _digest(values).removeprefix("sha256:")[:32]


def _provider_contract_values(value: DhanV2LiveProviderContract | dict[str, object]) -> dict[str, object]:
    source = value if isinstance(value, dict) else {
        "provider": value.provider, "version": value.version,
        "websocket_documentation": value.websocket_documentation, "instrument_documentation": value.instrument_documentation,
        "annexure_documentation": value.annexure_documentation, "max_connections_per_user": value.max_connections_per_user,
        "max_instruments_per_connection": value.max_instruments_per_connection,
        "max_instruments_per_subscription": value.max_instruments_per_subscription, "request_encoding": value.request_encoding,
        "response_encoding": value.response_encoding, "endianness": value.endianness,
        "ping_interval_seconds": value.ping_interval_seconds, "pong_timeout_seconds": value.pong_timeout_seconds,
        "supported_feed_modes": value.supported_feed_modes, "quote_subscribe_request_code": value.quote_subscribe_request_code,
        "quote_response_code": value.quote_response_code, "quote_packet_length": value.quote_packet_length,
    }
    return dict(source)


def _event_values(value: DhanProspectiveMarketEvent | dict[str, object]) -> dict[str, object]:
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key not in {"event_identity", "fingerprint"}}
    return {
        "canonical_security_id": value.canonical_security_id, "provider": value.provider,
        "isin": value.isin,
        "provider_security_id": value.provider_security_id, "exchange_segment": value.exchange_segment,
        "series": value.series, "packet_type": value.packet_type, "last_traded_price": value.last_traded_price,
        "event_time": value.event_time, "received_at": value.received_at,
        "cumulative_session_volume": value.cumulative_session_volume, "last_traded_quantity": value.last_traded_quantity,
        "connection_id": value.connection_id, "provider_version": value.provider_version,
        "master_fingerprint": value.master_fingerprint, "quality": value.quality,
    }


def _binding_values(value: DhanRegularMinuteBinding | dict[str, object]) -> dict[str, object]:
    if isinstance(value, dict):
        return dict(value)
    return {
        "state": value.state, "reason": value.reason, "period": _period_values(value.period),
        "session_id": value.session_id, "interval_start": value.interval_start, "interval_end": value.interval_end,
    }


def _period_values(value: TechnicalTradingPeriod | None) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "venue": value.venue, "segment": value.segment, "period_id": value.period_id,
        "session_dates": value.session_dates, "starts_at": value.starts_at, "ends_at": value.ends_at,
        "timezone_id": value.timezone_id, "calendar_id": value.calendar_id,
        "calendar_fingerprint": value.calendar_fingerprint, "session_source_ids": value.session_source_ids,
        "session_source_fingerprints": value.session_source_fingerprints,
    }


def _bar_values(value: ProspectiveDhanOneMinuteBar | dict[str, object]) -> dict[str, object]:
    if isinstance(value, dict):
        return {key: item for key, item in value.items() if key != "fingerprint"}
    return {
        "bar_id": value.bar_id, "instrument": _instrument_values(value.instrument), "session_id": value.session_id,
        "period": _period_values(value.period), "interval_start": value.interval_start, "interval_end": value.interval_end,
        "open": value.open, "high": value.high, "low": value.low, "close": value.close,
        "volume": value.volume, "event_count": value.event_count, "first_event_time": value.first_event_time,
        "last_event_time": value.last_event_time, "first_received_at": value.first_received_at,
        "last_received_at": value.last_received_at, "known_at": value.known_at,
        "event_set_fingerprint": value.event_set_fingerprint, "source_basis": value.source_basis,
        "adjustment_status": value.adjustment_status,
    }


def _receipt_values(value: ProspectiveDhanMinuteReceipt | dict[str, object], *, reasons: tuple[DhanProspectiveBarReason, ...] | None = None) -> dict[str, object]:
    if isinstance(value, dict):
        source = value
        actual_reasons = reasons if reasons is not None else tuple(source["reasons"])  # type: ignore[index]
        return {
            "receipt_id": source["receipt_id"],
            "instrument": _instrument_values(source["instrument"]) if isinstance(source["instrument"], DhanProspectiveInstrumentIdentity) else source["instrument"],
            "session_id": source["session_id"],
            "period": _period_values(source["period"]) if isinstance(source["period"], TechnicalTradingPeriod) else source["period"],
            "interval_start": source["interval_start"],
            "interval_end": source["interval_end"],
            "state": source["state"],
            "reasons": actual_reasons,
            "observed_event_count": source["observed_event_count"],
            "known_at": source["known_at"],
            "bar": _bar_values(source["bar"]) if isinstance(source["bar"], ProspectiveDhanOneMinuteBar) else source["bar"],
        }
    return {
        "receipt_id": value.receipt_id, "instrument": _instrument_values(value.instrument), "session_id": value.session_id,
        "period": _period_values(value.period), "interval_start": value.interval_start, "interval_end": value.interval_end,
        "state": value.state, "reasons": reasons if reasons is not None else value.reasons,
        "observed_event_count": value.observed_event_count, "known_at": value.known_at,
        "bar": None if value.bar is None else _bar_values(value.bar),
    }


def _instrument_values(value: DhanProspectiveInstrumentIdentity) -> dict[str, object]:
    return {
        "canonical_security_id": value.canonical_security_id, "isin": value.isin,
        "provider_security_id": value.provider_security_id, "exchange_segment": value.exchange_segment,
        "series": value.series, "master_fingerprint": value.master_fingerprint, "provider_version": value.provider_version,
    }


def _digest(value: object) -> str:
    return "sha256:" + sha256(json.dumps(_scalar(value), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scalar(value: object) -> object:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple) or isinstance(value, list):
        return [_scalar(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _scalar(item) for key, item in value.items()}
    if isinstance(value, TechnicalTradingPeriod):
        return _scalar(_period_values(value))
    if isinstance(value, DhanProspectiveInstrumentIdentity):
        return _scalar(_instrument_values(value))
    return value


def _positive_decimal(value: float) -> Decimal | None:
    result = Decimal(str(value))
    return result if result > 0 else None


def _https_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("https://") and "/" in value[8:]


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FINGERPRINT.fullmatch(value) is not None


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc_required(value: datetime) -> datetime:
    if not _aware(value):
        raise DhanLiveBarError("DHAN_PROSPECTIVE_TIMESTAMP_NAIVE")
    return _utc(value)


def _utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def _overlaps(left_start: datetime, left_end: datetime, right_start: datetime, right_end: datetime) -> bool:
    return _utc(left_start) < _utc(right_end) and _utc(right_start) < _utc(left_end)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "DHAN_MAX_CONNECTIONS_PER_USER", "DHAN_MAX_INSTRUMENTS_PER_CONNECTION",
    "DHAN_MAX_INSTRUMENTS_PER_SUBSCRIPTION", "DHAN_QUOTE_PACKET", "DHAN_QUOTE_PACKET_LENGTH", "DHAN_QUOTE_SUBSCRIBE",
    "DhanLiveBarConnectionState", "DhanLiveBarError", "DhanProspectiveBarReason", "DhanProspectiveBarState",
    "DhanProspectiveBarWriteOutcome", "DhanProspectiveEventQuality", "DhanProspectiveInstrumentIdentity",
    "DhanProspectiveMarketEvent", "DhanProspectiveQuoteFeedAdapter", "DhanLiveFeedMode", "DhanQuoteFeedProbe",
    "DhanQuotePacket", "DhanQuoteSubscriptionPlan", "DhanRegularMinuteBinding", "DhanSessionBindingReason",
    "DhanSessionBindingState", "DhanV2LiveProviderContract", "ProspectiveDhanMinuteConflict", "ProspectiveDhanMinuteReceipt",
    "ProspectiveDhanMinuteStore", "ProspectiveDhanOneMinuteBar", "ProspectiveDhanOneMinuteBarBuilder",
    "bind_dhan_event_to_regular_minute", "dhan_v2_live_provider_contract", "normalize_dhan_quote_packet",
    "parse_dhan_quote_packets", "plan_dhan_quote_subscription", "prospective_dhan_minute_identity", "quote_subscription_messages",
)
