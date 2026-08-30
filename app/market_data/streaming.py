"""Provider-neutral, explicitly driven quote-feed runtime.

This module contains no network client, scheduler, account API, or order path.
Providers inject a transport and a payload-to-canonical adapter; callers drive
connect, receive, heartbeat, and retry steps deliberately.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, Callable, Mapping, Protocol

from app.market_data.models import CanonicalQuote, ErrorCode, MarketDataError
from app.market_data.store import MarketDataSnapshotWriter


class FeedConnectionState(StrEnum):
    STOPPED = "STOPPED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DEGRADED = "DEGRADED"


class FeedHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    STALE = "STALE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ReconnectPolicy:
    initial_delay: timedelta = timedelta(seconds=1)
    maximum_delay: timedelta = timedelta(seconds=30)
    maximum_attempts: int = 3
    heartbeat_timeout: timedelta = timedelta(seconds=15)

    def __post_init__(self) -> None:
        if self.initial_delay <= timedelta() or self.maximum_delay < self.initial_delay:
            raise ValueError("Reconnect delays must be positive and ordered.")
        if self.maximum_attempts < 1 or self.heartbeat_timeout <= timedelta():
            raise ValueError("Reconnect attempts and heartbeat timeout must be positive.")


@dataclass(frozen=True, slots=True)
class StreamingSubscription:
    subscription_id: str
    instrument_id: str
    provider_instrument_reference: str
    provider_exchange_segment: str | None = None

    def __post_init__(self) -> None:
        if not all((self.subscription_id.strip(), self.instrument_id.strip(), self.provider_instrument_reference.strip())):
            raise ValueError("Streaming subscription identifiers are required.")


@dataclass(frozen=True, slots=True)
class FeedHealth:
    state: FeedHealthState
    connection_state: FeedConnectionState
    evaluated_at: datetime
    last_heartbeat_at: datetime | None
    reconnect_attempts: int
    next_retry_at: datetime | None
    warnings: tuple[str, ...] = ()


class QuoteFeedTransport(Protocol):
    """Minimal injected transport; production networking remains outside this module."""

    def connect(self) -> None: ...
    def close(self) -> None: ...
    def subscribe(self, subscription: StreamingSubscription) -> None: ...
    def unsubscribe(self, subscription: StreamingSubscription) -> None: ...
    def heartbeat(self) -> None: ...


class StreamingQuoteAdapter(Protocol):
    def normalize(self, payload: Mapping[str, Any], subscription: StreamingSubscription, received_at: datetime) -> CanonicalQuote: ...


class MarketDataStreamRuntime:
    """Synchronous state machine for a provider feed; it never self-schedules."""

    def __init__(
        self,
        transport: QuoteFeedTransport,
        adapter: StreamingQuoteAdapter,
        writer: MarketDataSnapshotWriter,
        *,
        reconnect_policy: ReconnectPolicy = ReconnectPolicy(),
        clock: Callable[[], datetime],
    ) -> None:
        self._transport, self._adapter, self._writer = transport, adapter, writer
        self._policy, self._clock = reconnect_policy, clock
        self._subscriptions: dict[str, StreamingSubscription] = {}
        self._state = FeedConnectionState.STOPPED
        self._last_heartbeat_at: datetime | None = None
        self._reconnect_attempts = 0
        self._next_retry_at: datetime | None = None

    @property
    def state(self) -> FeedConnectionState:
        return self._state

    def subscriptions(self) -> tuple[StreamingSubscription, ...]:
        return tuple(sorted(self._subscriptions.values(), key=lambda item: item.subscription_id))

    def subscribe(self, subscription: StreamingSubscription) -> None:
        existing = self._subscriptions.get(subscription.subscription_id)
        if existing is not None and existing != subscription:
            raise ValueError("Subscription ID cannot be rebound to another instrument.")
        if existing is not None:
            return
        if any(item.instrument_id == subscription.instrument_id for item in self._subscriptions.values()):
            raise ValueError("Instrument already has an active stream subscription.")
        self._subscriptions[subscription.subscription_id] = subscription
        if self._state is FeedConnectionState.CONNECTED:
            self._transport.subscribe(subscription)

    def unsubscribe(self, subscription_id: str) -> None:
        subscription = self._subscriptions.pop(subscription_id, None)
        if subscription is not None and self._state is FeedConnectionState.CONNECTED:
            self._transport.unsubscribe(subscription)

    def start(self) -> None:
        if self._state is FeedConnectionState.CONNECTED:
            return
        self._state = FeedConnectionState.CONNECTING
        try:
            self._transport.connect()
            for subscription in self.subscriptions():
                self._transport.subscribe(subscription)
        except Exception as error:
            self._record_disconnect(self._clock(), error)
            raise _safe_feed_error(error) from None
        self._state = FeedConnectionState.CONNECTED
        self._reconnect_attempts, self._next_retry_at = 0, None
        self._last_heartbeat_at = self._clock()

    def stop(self) -> None:
        if self._state is not FeedConnectionState.STOPPED:
            self._transport.close()
        self._state, self._next_retry_at = FeedConnectionState.STOPPED, None

    def receive(self, subscription_id: str, payload: Mapping[str, Any], *, received_at: datetime | None = None) -> CanonicalQuote:
        if self._state is not FeedConnectionState.CONNECTED:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Market-data feed is not connected.")
        subscription = self._subscriptions.get(subscription_id)
        if subscription is None:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Feed payload has no active subscription.")
        at = received_at or self._clock()
        quote = self._adapter.normalize(payload, subscription, at)
        self._writer.write(quote)
        return quote

    def heartbeat(self, *, at: datetime | None = None) -> None:
        if self._state is not FeedConnectionState.CONNECTED:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Market-data feed is not connected.")
        self._transport.heartbeat()
        self._last_heartbeat_at = at or self._clock()

    def disconnected(self, *, at: datetime | None = None, reason: Exception | None = None) -> FeedHealth:
        self._record_disconnect(at or self._clock(), reason)
        return self.health(at=at)

    def retry(self, *, at: datetime | None = None) -> None:
        now = at or self._clock()
        if self._state is not FeedConnectionState.RECONNECTING or self._next_retry_at is None or now < self._next_retry_at:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Market-data feed retry is not due.")
        self.start()

    def health(self, *, at: datetime | None = None) -> FeedHealth:
        now = at or self._clock()
        if self._state is FeedConnectionState.DEGRADED:
            state, warnings = FeedHealthState.DEGRADED, ("RECONNECT_ATTEMPTS_EXHAUSTED",)
        elif self._state is FeedConnectionState.CONNECTED and self._last_heartbeat_at is not None and now - self._last_heartbeat_at > self._policy.heartbeat_timeout:
            state, warnings = FeedHealthState.STALE, ("HEARTBEAT_STALE",)
        elif self._state is FeedConnectionState.CONNECTED:
            state, warnings = FeedHealthState.HEALTHY, ()
        else:
            state, warnings = FeedHealthState.UNKNOWN, ("FEED_NOT_CONNECTED",)
        return FeedHealth(state, self._state, now, self._last_heartbeat_at, self._reconnect_attempts, self._next_retry_at, warnings)

    def _record_disconnect(self, at: datetime, _reason: Exception | None) -> None:
        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._policy.maximum_attempts:
            self._state, self._next_retry_at = FeedConnectionState.DEGRADED, None
            return
        delay = min(self._policy.initial_delay * (2 ** (self._reconnect_attempts - 1)), self._policy.maximum_delay)
        self._state, self._next_retry_at = FeedConnectionState.RECONNECTING, at + delay


def _safe_feed_error(error: Exception) -> MarketDataError:
    if isinstance(error, MarketDataError):
        return error
    return MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Market-data feed is unavailable.")
