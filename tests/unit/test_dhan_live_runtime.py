from fastapi.testclient import TestClient
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.api.main import create_app
from app.connections.credentials import InMemoryCredentialStore
from app.market_data.dhan import DHAN_CONNECTION_ID, DhanCredentialService, DhanLtpTarget
from app.market_data.dhan_live import DhanLiveFeedHealth, DhanLiveFeedService, LiveMarketState, PersistedSetupLevels
from app.market_data.dhan_live_runtime import DhanLiveMarketRuntime


def test_live_market_api_is_disabled_by_default_and_never_starts_a_feed(monkeypatch):
    monkeypatch.delenv("DHAN_LIVE_MARKET_ENABLED", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/live-market/health")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    assert body["state"] == "LIVE_MARKET_DISABLED"
    assert body["requested_targets"] == body["mapped_packets"] == 0


def _runtime() -> DhanLiveMarketRuntime:
    now = datetime(2026, 9, 2, 10, tzinfo=UTC)
    credentials = DhanCredentialService(InMemoryCredentialStore(values={DHAN_CONNECTION_ID: {
        "dhan_client_id": "synthetic-client", "api_key": "synthetic-key", "api_secret": "synthetic-secret",
        "access_token": "synthetic-token", "access_token_expiry": "2026-09-02T12:00:00+00:00",
    }}), clock=lambda: now)
    feed = DhanLiveFeedService(credentials, clock=lambda: now)
    feed.state.replace(LiveMarketState("NSE:ONE", "DHAN", "1001", Decimal("125"), now, now, DhanLiveFeedHealth.LIVE))
    snapshot = SimpleNamespace(holdings=(
        SimpleNamespace(instrument_id="NSE:ONE", quantity=Decimal("2"), average_cost=Decimal("100")),
        SimpleNamespace(instrument_id="NSE:TWO", quantity=Decimal("1"), average_cost=Decimal("50")),
    ))
    return DhanLiveMarketRuntime(
        enabled=True, feed=feed, target_loader=lambda: (DhanLtpTarget("NSE:ONE", "NSE_EQ", 1001),),
        transport_factory=lambda _url: None, portfolio_snapshot_loader=lambda: snapshot,
        symbol_loader=lambda: {"NSE:ONE": "ONE", "NSE:TWO": "TWO"},
        setup_levels_loader=lambda: (PersistedSetupLevels("NSE:ONE", entry=Decimal("120"), stop=Decimal("95"), t1=Decimal("140"), e_max=Decimal("130")),),
    )


def test_live_runtime_read_models_are_in_memory_only_and_truthful_about_unavailable_quotes():
    runtime = _runtime()
    valuations = runtime.portfolio_valuations(now=datetime(2026, 9, 2, 10, tzinfo=UTC))
    assert valuations[0].market_value == Decimal("250") and valuations[0].unrealized_pnl == Decimal("50")
    assert valuations[1].state.value == "UNAVAILABLE" and valuations[1].blocker == "LIVE_PRICE_UNAVAILABLE"
    monitor = runtime.setup_monitors(now=datetime(2026, 9, 2, 10, tzinfo=UTC))[0]
    assert monitor.state.value == "SETUP_TRIGGER_STATE_CHANGED"
    assert runtime.quote("NSE:TWO", now=datetime(2026, 9, 2, 10, tzinfo=UTC)) is None


def test_live_market_overview_and_exact_stock_read_model_are_safe_when_disabled(monkeypatch):
    monkeypatch.delenv("DHAN_LIVE_MARKET_ENABLED", raising=False)
    with TestClient(create_app()) as client:
        overview = client.get("/api/v1/live-market")
        stock = client.get("/api/v1/stocks/NSE:ONE/live-market")
        invalid = client.get("/api/v1/stocks/ONE/live-market")
    assert overview.status_code == stock.status_code == 200 and invalid.status_code == 422
    assert overview.json()["setup_state"] == "NO_ACTIVE_SETUP"
    assert stock.json()["quote"] is None and stock.json()["health"]["enabled"] is False
    assert "synthetic-token" not in str(overview.json()) and "synthetic-client" not in str(stock.json())
