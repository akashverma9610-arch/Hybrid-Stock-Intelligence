"""Deterministic, append-only local market-data store and snapshot writer."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from app.market_data.models import (
    CanonicalOHLCVBar,
    CanonicalQuote,
    ErrorCode,
    IndexMarketObservation,
    MarketBreadthObservation,
    MarketDataQualityError,
    MarketDataQualityValidator,
    MarketSessionObservation,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class MarketDataStore(Protocol):
    def save_quote(self, value: CanonicalQuote) -> None: ...
    def latest_quote(self, instrument_id: str) -> CanonicalQuote | None: ...
    def save_bar(self, value: CanonicalOHLCVBar) -> None: ...
    def historical_bars(self, instrument_id: str) -> tuple[CanonicalOHLCVBar, ...]: ...
    def save_index(self, value: IndexMarketObservation) -> None: ...
    def latest_index(self, instrument_id: str) -> IndexMarketObservation | None: ...
    def save_breadth(self, value: MarketBreadthObservation) -> None: ...
    def latest_breadth(self, universe_reference: str) -> MarketBreadthObservation | None: ...
    def save_session(self, value: MarketSessionObservation) -> None: ...
    def latest_session(self, exchange: str) -> MarketSessionObservation | None: ...


@dataclass(slots=True)
class InMemoryMarketDataStore:
    """Local/test append-only store. High-volume durable bar storage is deferred."""

    _quotes: dict[str, CanonicalQuote]
    _bars: dict[str, list[CanonicalOHLCVBar]]
    _indices: dict[str, IndexMarketObservation]
    _breadth: dict[str, MarketBreadthObservation]
    _sessions: dict[str, MarketSessionObservation]

    def __init__(self) -> None:
        self._quotes = {}
        self._bars = defaultdict(list)
        self._indices = {}
        self._breadth = {}
        self._sessions = {}

    def save_quote(self, value: CanonicalQuote) -> None:
        MarketDataQualityValidator.validate_quote(value)
        if value.quote_id in self._quotes:
            raise ValueError("Canonical quotes are immutable and cannot be overwritten.")
        self._quotes[value.quote_id] = value

    def latest_quote(self, instrument_id: str) -> CanonicalQuote | None:
        values = [value for value in self._quotes.values() if value.instrument.instrument_id == instrument_id]
        return max(values, key=lambda item: (item.provenance.exchange_timestamp or item.provenance.provider_timestamp or item.provenance.received_at, item.quote_id)) if values else None

    def save_bar(self, value: CanonicalOHLCVBar) -> None:
        MarketDataQualityValidator.validate_bar(value)
        values = self._bars[value.instrument.instrument_id]
        if any(item.bar_id == value.bar_id for item in values):
            raise ValueError("Canonical bars are immutable and cannot be overwritten.")
        if any(item.timeframe is value.timeframe and item.end_time == value.end_time for item in values):
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Duplicate bar timeframe/end timestamp.")
        values.append(value)
        values.sort(key=lambda item: (item.end_time, item.bar_id))

    def historical_bars(self, instrument_id: str) -> tuple[CanonicalOHLCVBar, ...]:
        return tuple(self._bars.get(instrument_id, ()))

    def save_index(self, value: IndexMarketObservation) -> None:
        if value.observation_id in self._indices:
            raise ValueError("Canonical index observations are immutable and cannot be overwritten.")
        self._indices[value.observation_id] = value

    def latest_index(self, instrument_id: str) -> IndexMarketObservation | None:
        values = [value for value in self._indices.values() if value.instrument.instrument_id == instrument_id]
        return max(values, key=lambda item: (item.observed_at, item.observation_id)) if values else None

    def save_breadth(self, value: MarketBreadthObservation) -> None:
        if value.observation_id in self._breadth:
            raise ValueError("Canonical breadth observations are immutable and cannot be overwritten.")
        self._breadth[value.observation_id] = value

    def latest_breadth(self, universe_reference: str) -> MarketBreadthObservation | None:
        values = [value for value in self._breadth.values() if value.universe_reference == universe_reference]
        return max(values, key=lambda item: (item.observed_at, item.observation_id)) if values else None

    def save_session(self, value: MarketSessionObservation) -> None:
        if value.observation_id in self._sessions:
            raise ValueError("Canonical session observations are immutable and cannot be overwritten.")
        self._sessions[value.observation_id] = value

    def latest_session(self, exchange: str) -> MarketSessionObservation | None:
        values = [value for value in self._sessions.values() if value.exchange.value == exchange]
        return max(values, key=lambda item: (item.observed_at, item.observation_id)) if values else None


class CoreSnapshotQuoteStore:
    """Durable append-only canonical quote storage via the existing core repository.

    This is a persistence adapter only: it never calls a provider, chooses an
    instrument, or exposes provider references through an API route.
    """

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_quote(self, value: CanonicalQuote) -> None:
        MarketDataQualityValidator.validate_quote(value)
        fingerprint = sha256(repr(value).encode()).hexdigest()
        self._repository.save_snapshot(CoreApiSnapshot(
            f"canonical-quote:{value.quote_id}", CoreApiSnapshotFamily.CANONICAL_QUOTE,
            "v1", "canonical-quote-v1", fingerprint, value.provenance.received_at, value,
        ))

    def latest_quote(self, instrument_id: str) -> CanonicalQuote | None:
        values: list[CanonicalQuote] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.CANONICAL_QUOTE, limit=100, offset=offset)
            values.extend(
                item.payload for item in page
                if isinstance(item.payload, CanonicalQuote) and item.payload.instrument.instrument_id == instrument_id
            )
            if len(page) < 100:
                break
            offset += len(page)
        return max(
            values,
            key=lambda item: (item.provenance.exchange_timestamp or item.provenance.provider_timestamp or item.provenance.received_at, item.quote_id),
        ) if values else None


class MarketDataSnapshotWriter:
    """Writes validated canonical facts only; it does not initiate collection."""

    def __init__(self, store: MarketDataStore) -> None:
        self._store = store

    def write(self, value: CanonicalQuote | CanonicalOHLCVBar | IndexMarketObservation | MarketBreadthObservation | MarketSessionObservation) -> None:
        if isinstance(value, CanonicalQuote): self._store.save_quote(value)
        elif isinstance(value, CanonicalOHLCVBar): self._store.save_bar(value)
        elif isinstance(value, IndexMarketObservation): self._store.save_index(value)
        elif isinstance(value, MarketBreadthObservation): self._store.save_breadth(value)
        elif isinstance(value, MarketSessionObservation): self._store.save_session(value)
        else: raise TypeError("Only canonical normalized market-data records may be written.")
