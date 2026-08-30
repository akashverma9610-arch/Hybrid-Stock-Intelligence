from datetime import UTC, datetime, timedelta

import pytest

from app.market_data.kotak_neo_streaming import (
    KotakNeoLiveStreamingTransport,
    KotakNeoStreamingQuoteAdapter,
    KotakNeoStreamingSettings,
)
from app.market_data.models import (
    ErrorCode,
    Exchange,
    InstrumentIdentity,
    InstrumentType,
    MarketDataError,
)
from app.market_data.store import InMemoryMarketDataStore, MarketDataSnapshotWriter
from app.market_data.streaming import (
    FeedConnectionState,
    FeedHealthState,
    MarketDataStreamRuntime,
    ReconnectPolicy,
    StreamingSubscription,
)


T = datetime(2026, 8, 23, 10, tzinfo=UTC)


class FakeFeedTransport:
    def __init__(self, *, fail_connect: bool = False) -> None:
        self.fail_connect = fail_connect
        self.calls: list[str] = []

    def connect(self) -> None:
        self.calls.append("connect")
        if self.fail_connect:
            raise OSError("offline fixture")

    def close(self) -> None: self.calls.append("close")
    def subscribe(self, subscription) -> None: self.calls.append(f"subscribe:{subscription.subscription_id}")
    def unsubscribe(self, subscription) -> None: self.calls.append(f"unsubscribe:{subscription.subscription_id}")
    def heartbeat(self) -> None: self.calls.append("heartbeat")


def instrument() -> InstrumentIdentity:
    return InstrumentIdentity("nse:RELIANCE", Exchange.NSE, "RELIANCE", "RELIANCE-EQ", None, "EQ", InstrumentType.NSE_EQUITY, "Reliance")


def runtime(*, transport=None, policy=ReconnectPolicy(), clock=lambda: T):
    store = InMemoryMarketDataStore()
    adapter = KotakNeoStreamingQuoteAdapter({"nse:RELIANCE": instrument()})
    value = MarketDataStreamRuntime(transport or FakeFeedTransport(), adapter, MarketDataSnapshotWriter(store), reconnect_policy=policy, clock=clock)
    value.subscribe(StreamingSubscription("sub-reliance", "nse:RELIANCE", "7383", "nse_cm"))
    return value, store


def payload(*, sequence=1, last_price="1400.25", at=T):
    return {"instrument_token": "7383", "sequence": sequence, "last_price": last_price, "previous_close": "1395", "open": "1396", "high": "1402", "low": "1390", "last_volume": 100, "exchange_timestamp": at}


def test_mock_kotak_feed_subscribes_normalizes_and_writes_existing_canonical_store() -> None:
    transport = FakeFeedTransport()
    value, store = runtime(transport=transport)
    value.start()
    quote = value.receive("sub-reliance", payload())
    assert transport.calls == ["connect", "subscribe:sub-reliance"]
    assert quote.quote_id == "kotak-stream:7383:1"
    assert quote.provenance.provider == "KOTAK_NEO" and quote.last_price is not None
    assert store.latest_quote("nse:RELIANCE") == quote


def test_subscription_management_is_idempotent_and_rejects_rebinding_or_duplicate_instrument() -> None:
    value, _store = runtime()
    original = value.subscriptions()[0]
    value.subscribe(original)
    with pytest.raises(ValueError, match="rebound"):
        value.subscribe(StreamingSubscription("sub-reliance", "nse:OTHER", "other"))
    with pytest.raises(ValueError, match="already"):
        value.subscribe(StreamingSubscription("second", "nse:RELIANCE", "other"))
    value.start()
    value.unsubscribe("sub-reliance")
    assert value.subscriptions() == ()


def test_reconnect_backoff_is_explicit_and_never_sleeps_or_schedules_itself() -> None:
    transport = FakeFeedTransport(fail_connect=True)
    value, _store = runtime(transport=transport, policy=ReconnectPolicy(initial_delay=timedelta(seconds=2), maximum_delay=timedelta(seconds=4), maximum_attempts=2, heartbeat_timeout=timedelta(seconds=5)))
    with pytest.raises(MarketDataError, match="unavailable"):
        value.start()
    health = value.health(at=T)
    assert (value.state, health.state, health.next_retry_at) == (FeedConnectionState.RECONNECTING, FeedHealthState.UNKNOWN, T + timedelta(seconds=2))
    with pytest.raises(MarketDataError, match="not due"):
        value.retry(at=T + timedelta(seconds=1))
    transport.fail_connect = False
    value.retry(at=T + timedelta(seconds=2))
    assert value.state is FeedConnectionState.CONNECTED


def test_heartbeat_health_detects_staleness_without_a_background_worker() -> None:
    value, _store = runtime(policy=ReconnectPolicy(heartbeat_timeout=timedelta(seconds=5)))
    value.start()
    value.heartbeat(at=T)
    assert value.health(at=T + timedelta(seconds=4)).state is FeedHealthState.HEALTHY
    assert value.health(at=T + timedelta(seconds=6)).state is FeedHealthState.STALE


def test_adapter_rejects_wrong_subscription_and_malformed_frames_without_writing_facts() -> None:
    value, store = runtime()
    value.start()
    bad_reference = dict(payload())
    bad_reference["instrument_token"] = "unexpected"
    with pytest.raises(MarketDataError) as wrong:
        value.receive("sub-reliance", bad_reference)
    with pytest.raises(MarketDataError) as malformed:
        value.receive("sub-reliance", {"instrument_token": "7383", "sequence": 1, "last_price": "1400"})
    assert wrong.value.code is ErrorCode.INSTRUMENT_NOT_FOUND
    assert malformed.value.code is ErrorCode.MALFORMED_RESPONSE
    assert store.latest_quote("nse:RELIANCE") is None


def test_live_kotak_transport_is_explicit_opt_in_and_makes_no_network_call() -> None:
    transport = KotakNeoLiveStreamingTransport()
    with pytest.raises(MarketDataError) as disabled:
        transport.connect()
    with pytest.raises(MarketDataError) as pending:
        KotakNeoLiveStreamingTransport(KotakNeoStreamingSettings(live_streaming_enabled=True)).connect()
    assert disabled.value.code is ErrorCode.CONFIGURATION_ERROR
    assert pending.value.code is ErrorCode.UNSUPPORTED_CAPABILITY


def test_streaming_boundary_has_no_order_account_or_scheduler_path() -> None:
    import inspect
    import app.market_data.kotak_neo_streaming as kotak_streaming
    import app.market_data.streaming as streaming

    source = inspect.getsource(streaming) + inspect.getsource(kotak_streaming)
    assert not any(token in source.lower() for token in ("place_order", "modify_order", "cancel_order", "holdings", "positions", "demat", "websocket-client", "requests."))
