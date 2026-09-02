"""Lifecycle-owned, provider-neutral Dhan live-state runtime.

The runtime owns no persistence and has no execution surface.  It exists so a
single host process can share one :class:`LiveMarketStateStore` between its
feed and read APIs; standalone CLI processes intentionally cannot do that.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from threading import Event, Thread
from typing import Callable

from app.market_data.dhan import DhanLtpTarget
from app.market_data.dhan_live import (
    DhanLiveFeedHealth, DhanLiveFeedService, LiveMarketState,
    LiveMarketStateStore, LivePortfolioValuation, PersistedSetupLevels,
    SetupProximityState, live_portfolio_valuations, setup_proximity,
)


@dataclass(frozen=True, slots=True)
class DhanLiveRuntimeHealth:
    enabled: bool
    state: str
    health: DhanLiveFeedHealth
    requested_targets: int
    subscribed_targets: int
    mapped_packets: int
    rejected_packets: int
    last_packet_at: datetime | None
    token_state: str
    reconnect_count: int


@dataclass(frozen=True, slots=True)
class DhanLiveTargetView:
    canonical_instrument_id: str
    symbol: str
    ltp: Decimal | None
    freshness: str
    received_at: datetime | None
    provider_trade_timestamp: datetime | None


@dataclass(frozen=True, slots=True)
class DhanLiveSetupMonitor:
    canonical_instrument_id: str
    symbol: str
    entry: Decimal | None
    stop: Decimal | None
    target: Decimal | None
    maximum_entry: Decimal | None
    state: SetupProximityState


class DhanLiveMarketRuntime:
    """One explicitly enabled, bounded in-memory feed per application."""

    def __init__(
        self, *, enabled: bool, feed: DhanLiveFeedService,
        target_loader: Callable[[], tuple[DhanLtpTarget, ...]], transport_factory: Callable[[str], object],
        portfolio_snapshot_loader: Callable[[], object] | None = None,
        symbol_loader: Callable[[], dict[str, str]] | None = None,
        setup_levels_loader: Callable[[], tuple[PersistedSetupLevels, ...]] | None = None,
    ) -> None:
        self._enabled, self._feed, self._target_loader, self._transport_factory = enabled, feed, target_loader, transport_factory
        self._portfolio_snapshot_loader = portfolio_snapshot_loader
        self._symbol_loader = symbol_loader or (lambda: {})
        self._setup_levels_loader = setup_levels_loader or (lambda: ())
        self._stop, self._thread, self._targets, self._startup_failed = Event(), None, (), False

    @property
    def state(self) -> LiveMarketStateStore:
        return self._feed.state

    def start(self) -> None:
        if not self._enabled or self._thread is not None:
            return
        try:
            self._targets = self._target_loader()
        except Exception:
            self._startup_failed = True
            return
        if not self._targets:
            return
        self._thread = Thread(target=self._run, name="dhan-live-market", daemon=True)
        self._thread.start()

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout_seconds)

    def health(self) -> DhanLiveRuntimeHealth:
        status = self._feed.status
        if not self._enabled:
            return DhanLiveRuntimeHealth(False, "LIVE_MARKET_DISABLED", DhanLiveFeedHealth.DISCONNECTED, 0, 0, 0, 0, None, "NOT_REQUESTED", 0)
        state = "LIVE_MARKET_CONNECTED" if status.health is DhanLiveFeedHealth.LIVE else "LIVE_MARKET_DEGRADED"
        if self._startup_failed:
            state = "LIVE_MARKET_DEGRADED"
        return DhanLiveRuntimeHealth(
            True, state, status.health, status.requested_targets,
            status.subscribed_targets, status.mapped_packets, status.rejected_packets,
            status.newest_received_at,
            "VALID" if status.health is not DhanLiveFeedHealth.REAUTH_REQUIRED else "REAUTH_REQUIRED",
            status.reconnect_count,
        )

    def quotes(self, *, now: datetime | None = None) -> tuple[LiveMarketState, ...]:
        return self._feed.state.values(now=now or datetime.now(UTC))

    def quote(self, canonical_instrument_id: str, *, now: datetime | None = None) -> LiveMarketState | None:
        return next((item for item in self.quotes(now=now) if item.canonical_instrument_id == canonical_instrument_id), None)

    def targets(self, *, now: datetime | None = None) -> tuple[DhanLiveTargetView, ...]:
        symbols = self._symbol_loader()
        observations = {item.canonical_instrument_id: item for item in self.quotes(now=now)}
        return tuple(
            DhanLiveTargetView(
                target.canonical_instrument_id, symbols.get(target.canonical_instrument_id, target.canonical_instrument_id),
                None if (item := observations.get(target.canonical_instrument_id)) is None else item.ltp,
                "UNAVAILABLE" if item is None else item.freshness.value,
                None if item is None else item.received_at,
                None if item is None else item.provider_trade_timestamp,
            )
            for target in self._targets
        )

    def portfolio_valuations(self, *, now: datetime | None = None) -> tuple[LivePortfolioValuation, ...]:
        if self._portfolio_snapshot_loader is None:
            return ()
        return live_portfolio_valuations(
            self._portfolio_snapshot_loader(), self._feed.state,
            now=now or datetime.now(UTC), symbols=self._symbol_loader(),
        )

    def setup_monitors(self, *, now: datetime | None = None) -> tuple[DhanLiveSetupMonitor, ...]:
        symbols = self._symbol_loader()
        values = {item.canonical_instrument_id: item for item in self.quotes(now=now)}
        return tuple(
            DhanLiveSetupMonitor(
                level.canonical_instrument_id, symbols.get(level.canonical_instrument_id, level.canonical_instrument_id),
                level.entry, level.stop, level.t1, level.e_max,
                setup_proximity(level, None if values.get(level.canonical_instrument_id) is None else values[level.canonical_instrument_id].ltp),
            )
            for level in self._setup_levels_loader()
        )

    def _run(self) -> None:
        try:
            self._feed.run_forever(
                targets=self._targets, transport_factory=self._transport_factory,
                stop_requested=self._stop.is_set, sleeper=self._stop.wait,
            )
        except Exception:
            # DhanLiveFeedService already exposes a safe failed/reauth state;
            # an observational feed must not take down unrelated API reads.
            return
