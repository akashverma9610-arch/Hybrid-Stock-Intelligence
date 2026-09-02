"""Dhan V2 ticker-feed adapter: live observation only, never execution.

The adapter intentionally has no order, portfolio, or generic HTTP surface.
It maps only persisted exact Dhan provider mappings into a bounded in-memory
latest-price state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
import json
import struct
from typing import Callable, Protocol
from urllib.parse import urlencode

from app.market_data.dhan import DHAN_PROVIDER, DhanAuthError, DhanCredentialService, DhanLtpTarget

DHAN_LIVE_FEED_URL = "wss://api-feed.dhan.co"
DHAN_TICKER_SUBSCRIBE = 15
DHAN_TICKER_PACKET = 2
DHAN_SUBSCRIPTION_LIMIT = 100
DHAN_TICKER_PACKET_LENGTH = 16


class DhanLiveFeedHealth(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    LIVE = "LIVE"
    STALE = "STALE"
    RECONNECTING = "RECONNECTING"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class DhanBinaryHeader:
    response_code: int
    message_length: int
    exchange_segment: int
    security_id: int


@dataclass(frozen=True, slots=True)
class DhanTickerPacket:
    header: DhanBinaryHeader
    ltp: Decimal
    last_trade_time: datetime


@dataclass(frozen=True, slots=True)
class LiveMarketState:
    canonical_instrument_id: str
    provider: str
    provider_security_id: str
    ltp: Decimal
    provider_trade_timestamp: datetime
    received_at: datetime
    freshness: DhanLiveFeedHealth


@dataclass(frozen=True, slots=True)
class DhanLiveFeedStatus:
    health: DhanLiveFeedHealth
    requested_targets: int
    subscribed_targets: int
    mapped_packets: int
    rejected_packets: int
    oldest_received_at: datetime | None
    newest_received_at: datetime | None
    reconnect_count: int = 0

@dataclass(frozen=True, slots=True)
class DhanLiveConnectDiagnostic:
    ok: bool; stage: str; classification: str; exception_class: str | None = None
    http_status: int | None = None; provider_disconnect_code: int | None = None

class LiveValueState(StrEnum):
    FRESH = "FRESH"; STALE = "STALE"; UNAVAILABLE = "UNAVAILABLE"

@dataclass(frozen=True, slots=True)
class LivePortfolioValuation:
    canonical_instrument_id: str; symbol: str; quantity: Decimal; average_price: Decimal
    ltp: Decimal | None; market_value: Decimal | None; unrealized_pnl: Decimal | None
    provider_timestamp: datetime | None; received_at: datetime | None; state: LiveValueState
    blocker: str | None = None

class SetupProximityState(StrEnum):
    NO_ACTIVE_SETUP = "NO_ACTIVE_SETUP"; BELOW_ENTRY = "BELOW_ENTRY"; SETUP_TRIGGER_STATE_CHANGED = "SETUP_TRIGGER_STATE_CHANGED"
    STOP_LEVEL_REACHED = "STOP_LEVEL_REACHED"; T1_REACHED = "T1_REACHED"; T2_REACHED = "T2_REACHED"; EXTENDED_TARGET_REACHED = "EXTENDED_TARGET_REACHED"; ABOVE_E_MAX = "ABOVE_E_MAX"

@dataclass(frozen=True, slots=True)
class PersistedSetupLevels:
    canonical_instrument_id: str; entry: Decimal | None = None; stop: Decimal | None = None; t1: Decimal | None = None; t2: Decimal | None = None; extended_target: Decimal | None = None; e_max: Decimal | None = None

def live_portfolio_valuations(snapshot, states: LiveMarketStateStore, *, now: datetime, symbols: dict[str, str]) -> tuple[LivePortfolioValuation, ...]:
    """Read immutable holding data and bounded memory only; never persists."""
    by_id = {item.canonical_instrument_id: item for item in states.values(now=now)}
    values=[]
    for holding in snapshot.holdings:
        state=by_id.get(holding.instrument_id); symbol=symbols.get(holding.instrument_id, holding.instrument_id)
        if state is None: values.append(LivePortfolioValuation(holding.instrument_id,symbol,holding.quantity,holding.average_cost,None,None,None,None,None,LiveValueState.UNAVAILABLE,"LIVE_PRICE_UNAVAILABLE")); continue
        if state.freshness is DhanLiveFeedHealth.STALE: values.append(LivePortfolioValuation(holding.instrument_id,symbol,holding.quantity,holding.average_cost,state.ltp,None,None,state.provider_trade_timestamp,state.received_at,LiveValueState.STALE,"LIVE_PRICE_STALE")); continue
        value=holding.quantity*state.ltp; values.append(LivePortfolioValuation(holding.instrument_id,symbol,holding.quantity,holding.average_cost,state.ltp,value,value-holding.quantity*holding.average_cost,state.provider_trade_timestamp,state.received_at,LiveValueState.FRESH))
    return tuple(values)

def setup_proximity(levels: PersistedSetupLevels | None, ltp: Decimal | None) -> SetupProximityState:
    """Exact reached/crossed comparisons only: no unapproved 'near' buffer."""
    if levels is None or ltp is None: return SetupProximityState.NO_ACTIVE_SETUP
    if levels.stop is not None and ltp <= levels.stop: return SetupProximityState.STOP_LEVEL_REACHED
    if levels.e_max is not None and ltp >= levels.e_max: return SetupProximityState.ABOVE_E_MAX
    if levels.extended_target is not None and ltp >= levels.extended_target: return SetupProximityState.EXTENDED_TARGET_REACHED
    if levels.t2 is not None and ltp >= levels.t2: return SetupProximityState.T2_REACHED
    if levels.t1 is not None and ltp >= levels.t1: return SetupProximityState.T1_REACHED
    if levels.entry is not None and ltp >= levels.entry: return SetupProximityState.SETUP_TRIGGER_STATE_CHANGED
    return SetupProximityState.BELOW_ENTRY


class _Transport(Protocol):
    def send(self, payload: str) -> None: ...
    def recv(self) -> bytes: ...
    def close(self) -> None: ...


def open_dhan_live_transport(url: str, *, timeout_seconds: int) -> _Transport:
    """Construct the provider socket only inside the market-data adapter."""
    import websocket
    return websocket.create_connection(url, timeout=timeout_seconds)


def dhan_live_websocket_url(credentials: dict[str, str] | object) -> str:
    values = credentials if isinstance(credentials, dict) else dict(credentials)  # type: ignore[arg-type]
    return f"{DHAN_LIVE_FEED_URL}?{urlencode({'version': '2', 'token': values['access_token'], 'clientId': values['dhan_client_id'], 'authType': '2'})}"


def redact_dhan_live_websocket_url(_url: str) -> str:
    """Never return query credentials in operational output or exceptions."""
    return f"{DHAN_LIVE_FEED_URL}?version=2&token=REDACTED&clientId=REDACTED&authType=2"

def diagnose_dhan_live_failure(error: Exception) -> DhanLiveConnectDiagnostic:
    """Classify known connect failures without ever returning exception text."""
    name=type(error).__name__.lower(); status=getattr(error,"status_code",None) or getattr(error,"status",None)
    if isinstance(status,int): return DhanLiveConnectDiagnostic(False,"HANDSHAKE","HTTP_REJECTED",type(error).__name__,status)
    if "timeout" in name: return DhanLiveConnectDiagnostic(False,"CONNECT","TIMEOUT",type(error).__name__)
    if "ssl" in name or "certificate" in name: return DhanLiveConnectDiagnostic(False,"TLS","TLS_VERIFICATION_FAILED",type(error).__name__)
    if "proxy" in name: return DhanLiveConnectDiagnostic(False,"CONNECT","PROXY_CONNECT_FAILED",type(error).__name__)
    if "gai" in name or "dns" in name: return DhanLiveConnectDiagnostic(False,"CONNECT","DNS_FAILED",type(error).__name__)
    if "connection" in name or "socket" in name or "refused" in name: return DhanLiveConnectDiagnostic(False,"CONNECT","TCP_CONNECT_FAILED",type(error).__name__)
    return DhanLiveConnectDiagnostic(False,"CONNECT","UNKNOWN_CONNECT_FAILURE",type(error).__name__)

def parse_dhan_disconnect_packet(frame: bytes) -> DhanLiveConnectDiagnostic | None:
    if len(frame) != 10: return None
    code,length,_segment,_security=struct.unpack_from("<BhBi",frame)
    if code != 50 or length != 10: return None
    reason=struct.unpack_from("<h",frame,8)[0]
    classification="CONNECTION_LIMIT" if reason == 805 else "PROVIDER_DISCONNECT"
    return DhanLiveConnectDiagnostic(False,"PROVIDER","%s" % classification,provider_disconnect_code=reason)


def ticker_subscription_messages(targets: tuple[DhanLtpTarget, ...]) -> tuple[str, ...]:
    if len({item.canonical_instrument_id for item in targets}) != len(targets) or any(item.exchange_segment != "NSE_EQ" or item.security_id <= 0 for item in targets):
        raise ValueError("DHAN_EXACT_INSTRUMENT_MAPPING_REQUIRED")
    messages = []
    for offset in range(0, len(targets), DHAN_SUBSCRIPTION_LIMIT):
        batch = targets[offset:offset + DHAN_SUBSCRIPTION_LIMIT]
        messages.append(json.dumps({
            "RequestCode": DHAN_TICKER_SUBSCRIBE,
            "InstrumentCount": len(batch),
            "InstrumentList": [{"ExchangeSegment": "NSE_EQ", "SecurityId": item.security_id} for item in batch],
        }, separators=(",", ":")))
    return tuple(messages)


def parse_dhan_ticker_packets(frame: bytes) -> tuple[DhanTickerPacket, ...]:
    """Parse only documented V2 ticker packets, little-endian and exact-sized."""
    if not isinstance(frame, bytes) or not frame:
        raise ValueError("DHAN_LIVE_PACKET_MALFORMED")
    values: list[DhanTickerPacket] = []
    offset = 0
    while offset < len(frame):
        if len(frame) - offset < 8:
            raise ValueError("DHAN_LIVE_PACKET_TRUNCATED")
        code, length, segment, security_id = struct.unpack_from("<BhBi", frame, offset)
        if length != DHAN_TICKER_PACKET_LENGTH or len(frame) - offset < length:
            raise ValueError("DHAN_LIVE_PACKET_LENGTH_INVALID")
        if code != DHAN_TICKER_PACKET:
            raise ValueError("DHAN_LIVE_PACKET_UNSUPPORTED")
        ltp, epoch = struct.unpack_from("<fi", frame, offset + 8)
        if ltp <= 0 or epoch <= 0:
            raise ValueError("DHAN_LIVE_PACKET_INVALID")
        values.append(DhanTickerPacket(DhanBinaryHeader(code, length, segment, security_id), Decimal(str(ltp)), datetime.fromtimestamp(epoch, UTC)))
        offset += length
    return tuple(values)


class LiveMarketStateStore:
    """Bounded in-memory replacement store; it has no database dependency."""
    def __init__(self, *, stale_after: timedelta = timedelta(seconds=40)) -> None:
        self._values: dict[str, LiveMarketState] = {}
        self._stale_after = stale_after

    def replace(self, value: LiveMarketState) -> None:
        current = self._values.get(value.canonical_instrument_id)
        if current is None or value.received_at >= current.received_at:
            self._values[value.canonical_instrument_id] = value

    def values(self, *, now: datetime) -> tuple[LiveMarketState, ...]:
        result = []
        for value in self._values.values():
            freshness = DhanLiveFeedHealth.STALE if now - value.received_at > self._stale_after else DhanLiveFeedHealth.LIVE
            result.append(LiveMarketState(value.canonical_instrument_id, value.provider, value.provider_security_id, value.ltp, value.provider_trade_timestamp, value.received_at, freshness))
        return tuple(sorted(result, key=lambda item: item.canonical_instrument_id))


class DhanLiveFeedService:
    def __init__(self, credentials: DhanCredentialService, *, state: LiveMarketStateStore | None = None, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._credentials, self._state, self._clock = credentials, state or LiveMarketStateStore(), clock
        self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.DISCONNECTED, 0, 0, 0, 0, None, None)

    @property
    def status(self) -> DhanLiveFeedStatus: return self._status

    @property
    def state(self) -> LiveMarketStateStore: return self._state

    def diagnose(self, *, targets: tuple[DhanLtpTarget,...], transport_factory: Callable[[str],_Transport]) -> DhanLiveConnectDiagnostic:
        """One bounded connect and one five-target ticker subscription only."""
        try: credentials=dict(self._credentials.access_credentials())
        except DhanAuthError: return DhanLiveConnectDiagnostic(False,"AUTH","REAUTH_REQUIRED")
        transport=None
        try:
            transport=transport_factory(dhan_live_websocket_url(credentials))
            for message in ticker_subscription_messages(targets[:5]): transport.send(message)
            return DhanLiveConnectDiagnostic(True,"SUBSCRIBED","CONNECTED")
        except Exception as error: return diagnose_dhan_live_failure(error)
        finally:
            if transport is not None: transport.close()

    def canary(self, *, targets: tuple[DhanLtpTarget, ...], transport_factory: Callable[[str], _Transport], max_packets: int = 1) -> DhanLiveFeedStatus:
        """One bounded connection; library ping/pong handling is left enabled."""
        try:
            credentials = dict(self._credentials.access_credentials())
        except DhanAuthError as error:
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.REAUTH_REQUIRED, len(targets), 0, 0, 0, None, None)
            raise error
        self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.CONNECTING, len(targets), 0, 0, 0, None, None)
        mapping = {item.security_id: item.canonical_instrument_id for item in targets}
        transport: _Transport | None = None
        try:
            transport = transport_factory(dhan_live_websocket_url(credentials))
            messages = ticker_subscription_messages(targets)
            for message in messages: transport.send(message)
            mapped = rejected = 0; received: list[datetime] = []
            for _ in range(max_packets):
                for packet in parse_dhan_ticker_packets(transport.recv()):
                    identifier = mapping.get(packet.header.security_id)
                    if identifier is None:
                        rejected += 1; continue
                    now = self._clock()
                    self._state.replace(LiveMarketState(identifier, DHAN_PROVIDER, str(packet.header.security_id), packet.ltp, packet.last_trade_time, now, DhanLiveFeedHealth.LIVE))
                    mapped += 1; received.append(now)
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.LIVE, len(targets), len(targets), mapped, rejected, min(received, default=None), max(received, default=None))
            return self._status
        except DhanAuthError:
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.REAUTH_REQUIRED, len(targets), 0, 0, 0, None, None)
            raise
        except Exception:
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.FAILED, len(targets), 0, 0, 0, None, None)
            raise DhanAuthError("DHAN_LIVE_FEED_FAILED") from None
        finally:
            if transport is not None: transport.close()

    def run_with_reconnect(self, *, targets: tuple[DhanLtpTarget, ...], transport_factory: Callable[[str], _Transport], max_attempts: int = 3, sleeper: Callable[[float], None] = lambda _seconds: None) -> DhanLiveFeedStatus:
        """Bounded reconnect that rechecks credentials before every attempt.

        Every successful connection uses ``canary`` and therefore replays the
        one exact subscription set.  There is no symbol resolution or mapping
        mutation in this loop.
        """
        if max_attempts < 1:
            raise ValueError("DHAN_LIVE_RECONNECT_ATTEMPTS_INVALID")
        last_error: DhanAuthError | None = None
        for attempt in range(max_attempts):
            try:
                return self.canary(targets=targets, transport_factory=transport_factory)
            except DhanAuthError as error:
                if error.code == "DHAN_REAUTH_REQUIRED":
                    raise
                last_error = error
                if attempt + 1 < max_attempts:
                    self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.RECONNECTING, len(targets), 0, 0, 0, None, None)
                    sleeper(min(2 ** attempt, 8))
        raise last_error or DhanAuthError("DHAN_LIVE_FEED_FAILED")

    def run_forever(self, *, targets: tuple[DhanLtpTarget, ...], transport_factory: Callable[[str], _Transport], stop_requested: Callable[[], bool], sleeper: Callable[[float], None] = lambda _seconds: None) -> DhanLiveFeedStatus:
        """Keep one subscribed socket open until a real error or shutdown.

        ``canary`` intentionally closes after its bounded receive.  This
        production path must not call it: a normal packet is not a disconnect.
        """
        reconnect_attempt = 0
        reconnect_count = 0
        while not stop_requested():
            try:
                self._receive_session(targets=targets, transport_factory=transport_factory, stop_requested=stop_requested, reconnect_count=reconnect_count)
            except DhanAuthError as error:
                if error.code == "DHAN_REAUTH_REQUIRED":
                    self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.REAUTH_REQUIRED, len(targets), 0, 0, 0, None, None)
                    return self._status
                if stop_requested():
                    break
                reconnect_count += 1
                self._status = DhanLiveFeedStatus(
                    DhanLiveFeedHealth.RECONNECTING, len(targets), 0,
                    self._status.mapped_packets, self._status.rejected_packets,
                    self._status.oldest_received_at, self._status.newest_received_at, reconnect_count,
                )
                sleeper(min(2 ** reconnect_attempt, 8)); reconnect_attempt = min(reconnect_attempt + 1, 3)
        self._status = DhanLiveFeedStatus(
            DhanLiveFeedHealth.DISCONNECTED, len(targets), 0,
            self._status.mapped_packets, self._status.rejected_packets,
            self._status.oldest_received_at, self._status.newest_received_at, reconnect_count,
        )
        return self._status

    def _receive_session(self, *, targets: tuple[DhanLtpTarget, ...], transport_factory: Callable[[str], _Transport], stop_requested: Callable[[], bool], reconnect_count: int) -> None:
        try:
            credentials = dict(self._credentials.access_credentials())
        except DhanAuthError:
            raise
        mapping = {item.security_id: item.canonical_instrument_id for item in targets}
        transport: _Transport | None = None
        mapped = rejected = 0; first: datetime | None = None; newest: datetime | None = None
        self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.CONNECTING, len(targets), 0, 0, 0, None, None, reconnect_count)
        try:
            transport = transport_factory(dhan_live_websocket_url(credentials))
            for message in ticker_subscription_messages(targets): transport.send(message)
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.LIVE, len(targets), len(targets), 0, 0, None, None, reconnect_count)
            while not stop_requested():
                frame = transport.recv()
                for packet in parse_dhan_ticker_packets(frame):
                    identifier = mapping.get(packet.header.security_id)
                    if identifier is None:
                        rejected += 1; continue
                    now = self._clock()
                    self._state.replace(LiveMarketState(identifier, DHAN_PROVIDER, str(packet.header.security_id), packet.ltp, packet.last_trade_time, now, DhanLiveFeedHealth.LIVE))
                    mapped += 1; first = first or now; newest = now
                self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.LIVE, len(targets), len(targets), mapped, rejected, first, newest, reconnect_count)
        except DhanAuthError:
            raise
        except Exception:
            self._status = DhanLiveFeedStatus(DhanLiveFeedHealth.FAILED, len(targets), 0, mapped, rejected, first, newest, reconnect_count)
            raise DhanAuthError("DHAN_LIVE_FEED_FAILED") from None
        finally:
            if transport is not None: transport.close()


def target_set_diff(previous: tuple[DhanLtpTarget, ...], current: tuple[DhanLtpTarget, ...]) -> tuple[tuple[DhanLtpTarget, ...], tuple[DhanLtpTarget, ...]]:
    """Return exact additions/removals; unchanged maps never reconnect."""
    before = {(item.exchange_segment, item.security_id): item for item in previous}
    after = {(item.exchange_segment, item.security_id): item for item in current}
    return tuple(after[key] for key in sorted(after.keys() - before.keys())), tuple(before[key] for key in sorted(before.keys() - after.keys()))
