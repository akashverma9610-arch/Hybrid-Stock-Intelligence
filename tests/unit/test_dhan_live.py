from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import struct
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.connections.credentials import InMemoryCredentialStore
from app.market_data.dhan import DHAN_CONNECTION_ID, DhanCredentialService, DhanLtpTarget
from app.market_data.dhan_live import (
    DHAN_LIVE_FEED_URL, DhanLiveFeedHealth, DhanLiveFeedService, LiveMarketStateStore,
    parse_dhan_ticker_packets, redact_dhan_live_websocket_url, target_set_diff, ticker_subscription_messages,
    live_portfolio_valuations, PersistedSetupLevels, setup_proximity, SetupProximityState, LiveMarketState,
    diagnose_dhan_live_failure, parse_dhan_disconnect_packet,
)


NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
TARGETS = tuple(DhanLtpTarget(f"NSE:{index}", "NSE_EQ", index + 1000) for index in range(48))


def _credentials() -> DhanCredentialService:
    return DhanCredentialService(InMemoryCredentialStore(values={DHAN_CONNECTION_ID: {
        "dhan_client_id": "synthetic-client", "api_key": "synthetic-key", "api_secret": "synthetic-secret",
        "access_token": "synthetic-access-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat(),
    }}), clock=lambda: NOW)


def _packet(security_id: int = 1000, *, ltp: float = 123.5, epoch: int = 1_725_192_000) -> bytes:
    return struct.pack("<BhBifi", 2, 16, 1, security_id, ltp, epoch)


def test_dhan_ticker_parser_is_little_endian_exact_and_rejects_malformed() -> None:
    value = parse_dhan_ticker_packets(_packet())[0]
    assert value.header.response_code == 2 and value.header.message_length == 16 and value.header.security_id == 1000
    assert str(value.ltp) == "123.5" and value.last_trade_time.tzinfo is UTC
    with pytest.raises(ValueError, match="LENGTH_INVALID"):
        parse_dhan_ticker_packets(_packet()[:-1])
    with pytest.raises(ValueError, match="UNSUPPORTED"):
        parse_dhan_ticker_packets(struct.pack("<BhBifi", 4, 16, 1, 1000, 123.5, 1_725_192_000))


def test_subscription_is_exact_nse_eq_and_bounded_to_100() -> None:
    messages = ticker_subscription_messages(TARGETS)
    assert len(messages) == 1
    body = json.loads(messages[0])
    assert body["RequestCode"] == 15 and body["InstrumentCount"] == 48
    assert {item["ExchangeSegment"] for item in body["InstrumentList"]} == {"NSE_EQ"}
    many = tuple(DhanLtpTarget(f"NSE:M{index}", "NSE_EQ", index + 2000) for index in range(101))
    assert len(ticker_subscription_messages(many)) == 2


def test_live_state_is_in_memory_mapped_and_unknown_security_is_rejected_without_secrets() -> None:
    class Transport:
        def __init__(self): self.sent=[]; self.closed=False
        def send(self, payload): self.sent.append(payload)
        def recv(self): return _packet(1000) + _packet(999999)
        def close(self): self.closed=True
    transport = Transport(); service = DhanLiveFeedService(_credentials(), clock=lambda: NOW)
    status = service.canary(targets=TARGETS, transport_factory=lambda url: (assert_url(url), transport)[1])
    assert status.health is DhanLiveFeedHealth.LIVE and status.mapped_packets == 1 and status.rejected_packets == 1
    assert transport.closed and len(transport.sent) == 1
    state = service.state.values(now=NOW)[0]
    assert state.canonical_instrument_id == "NSE:0" and state.provider_security_id == "1000"
    assert "synthetic" not in redact_dhan_live_websocket_url(DHAN_LIVE_FEED_URL)


def assert_url(url: str) -> None:
    assert url.startswith(DHAN_LIVE_FEED_URL) and "synthetic-access-token" in url


def test_live_state_stales_without_creating_eod_or_signal() -> None:
    store = LiveMarketStateStore(stale_after=timedelta(seconds=1))
    from app.market_data.dhan_live import LiveMarketState
    from decimal import Decimal
    store.replace(LiveMarketState("NSE:X", "DHAN", "1", Decimal("1"), NOW, NOW, DhanLiveFeedHealth.LIVE))
    assert store.values(now=NOW + timedelta(seconds=2))[0].freshness is DhanLiveFeedHealth.STALE


def test_reconnect_rechecks_and_resubscribes_the_exact_targets() -> None:
    class Transport:
        def __init__(self): self.sent=[]
        def send(self, value): self.sent.append(value)
        def recv(self): return _packet()
        def close(self): pass
    attempts=[]; delays=[]
    def factory(_url):
        attempts.append(1)
        if len(attempts) == 1: raise OSError("network")
        return Transport()
    result = DhanLiveFeedService(_credentials(), clock=lambda: NOW).run_with_reconnect(
        targets=TARGETS, transport_factory=factory, max_attempts=2, sleeper=delays.append,
    )
    assert result.health is DhanLiveFeedHealth.LIVE and len(attempts) == 2 and delays == [1]
    added, removed = target_set_diff(TARGETS[:2], TARGETS[1:3])
    assert added == (TARGETS[2],) and removed == (TARGETS[0],)


def test_read_only_valuation_and_exact_setup_proximity_have_no_near_policy() -> None:
    store=LiveMarketStateStore(); store.replace(LiveMarketState("NSE:0","DHAN","1000",Decimal("120"),NOW,NOW,DhanLiveFeedHealth.LIVE))
    snapshot=SimpleNamespace(holdings=(SimpleNamespace(instrument_id="NSE:0",quantity=Decimal("2"),average_cost=Decimal("100")), SimpleNamespace(instrument_id="NSE:1",quantity=Decimal("1"),average_cost=Decimal("50"))))
    values=live_portfolio_valuations(snapshot,store,now=NOW,symbols={"NSE:0":"ZERO"})
    assert values[0].market_value == Decimal("240") and values[0].unrealized_pnl == Decimal("40")
    assert values[1].state.value == "UNAVAILABLE" and snapshot.holdings[0].average_cost == Decimal("100")
    levels=PersistedSetupLevels("NSE:0",entry=Decimal("110"),stop=Decimal("90"),t1=Decimal("130"),t2=Decimal("140"),extended_target=Decimal("150"),e_max=Decimal("160"))
    assert setup_proximity(None,Decimal("120")) is SetupProximityState.NO_ACTIVE_SETUP
    assert setup_proximity(levels,Decimal("110")) is SetupProximityState.SETUP_TRIGGER_STATE_CHANGED
    assert setup_proximity(levels,Decimal("160")) is SetupProximityState.ABOVE_E_MAX
    assert setup_proximity(levels,Decimal("90")) is SetupProximityState.STOP_LEVEL_REACHED


def test_long_run_requested_shutdown_starts_no_connection_and_leaves_clean_status() -> None:
    service=DhanLiveFeedService(_credentials(), clock=lambda: NOW)
    status=service.run_forever(targets=TARGETS, transport_factory=lambda _url: pytest.fail("must not connect after shutdown"), stop_requested=lambda: True)
    assert status.health is DhanLiveFeedHealth.DISCONNECTED and status.requested_targets == 48


def test_continuous_receive_keeps_one_socket_and_one_subscription_for_multiple_packets() -> None:
    class Transport:
        def __init__(self): self.sent=[]; self.closed=False; self.receives=0
        def send(self, value): self.sent.append(value)
        def recv(self):
            self.receives += 1
            if self.receives > 2: raise OSError("remote-close")
            return _packet(1000, ltp=100 + self.receives)
        def close(self): self.closed=True
    transport=Transport(); connections=[]; delays=[]
    service=DhanLiveFeedService(_credentials(), clock=lambda: NOW)
    status=service.run_forever(
        targets=TARGETS, transport_factory=lambda _url: (connections.append(1), transport)[1],
        stop_requested=lambda: transport.closed, sleeper=delays.append,
    )
    assert len(connections) == 1 and len(transport.sent) == 1
    assert service.state.values(now=NOW)[0].ltp == Decimal("102.0")
    assert status.health is DhanLiveFeedHealth.DISCONNECTED


def test_continuous_receive_reconnect_wait_is_bounded_and_never_busy_loops() -> None:
    service = DhanLiveFeedService(_credentials(), clock=lambda: NOW)
    delays = []
    stopped = [False]
    def wait(seconds):
        delays.append(seconds)
        stopped[0] = True
    status = service.run_forever(
        targets=TARGETS, transport_factory=lambda _url: (_ for _ in ()).throw(OSError("network")),
        stop_requested=lambda: stopped[0], sleeper=wait,
    )
    assert delays == [1]
    assert status.health is DhanLiveFeedHealth.DISCONNECTED and status.reconnect_count == 1


def test_safe_connect_diagnostics_classify_without_leaking_values() -> None:
    class Handshake(Exception):
        status_code=403
    value=diagnose_dhan_live_failure(Handshake("wss://token:secret@example"))
    assert value.stage == "HANDSHAKE" and value.http_status == 403 and "token" not in repr(value).lower()
    packet=struct.pack("<BhBih",50,10,1,1000,805)
    assert parse_dhan_disconnect_packet(packet).classification == "CONNECTION_LIMIT"
