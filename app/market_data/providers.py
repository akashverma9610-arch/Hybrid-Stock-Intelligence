"""Provider protocol, registry, and deterministic static local/test adapter."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping, Protocol

from app.market_data.models import (
    BatchQuotesResult,
    CanonicalOHLCVBar,
    CanonicalQuote,
    CapabilityState,
    ErrorCode,
    HistoricalBarsRequest,
    IndexMarketObservation,
    InstrumentIdentity,
    MarketBreadthObservation,
    MarketDataError,
    MarketSessionObservation,
    ProviderCapabilities,
    RetryDisposition,
)


class MarketDataProvider(Protocol):
    """Only canonical facts cross this boundary; implementations may be partial."""

    def capabilities(self) -> ProviderCapabilities: ...
    def resolve_instrument(self, query: str) -> InstrumentIdentity | None: ...
    def get_quote(self, instrument: InstrumentIdentity) -> CanonicalQuote: ...
    def get_quotes(self, instruments: tuple[InstrumentIdentity, ...]) -> BatchQuotesResult: ...
    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]: ...
    def get_latest_bar(self, instrument: InstrumentIdentity, timeframe: object) -> CanonicalOHLCVBar | None: ...
    def get_index_observation(self, instrument: InstrumentIdentity) -> IndexMarketObservation | None: ...
    def get_market_breadth(self, universe_reference: str) -> MarketBreadthObservation | None: ...
    def get_market_status(self, exchange: object) -> MarketSessionObservation | None: ...


class MarketDataProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {}

    def register(self, name: str, provider: MarketDataProvider) -> None:
        normalized = name.strip().lower()
        if not normalized:
            raise ValueError("Provider name is required.")
        if normalized in self._providers:
            raise ValueError("A provider name may only be registered once.")
        self._providers[normalized] = provider

    def create(self, configured_name: str) -> MarketDataProvider:
        try:
            return self._providers[configured_name.strip().lower()]
        except KeyError as error:
            raise MarketDataError(ErrorCode.CONFIGURATION_ERROR, "Configured market-data provider is unavailable.") from error


def configured_market_data_provider(
    provider_name: str,
    *,
    static_provider: MarketDataProvider | None = None,
    kotak_credentials: object | None = None,
    kotak_transport: object | None = None,
    gdfl_access_key: str | None = None,
    gdfl_transport: object | None = None,
    upstox_access_token: str | None = None,
    upstox_transport: object | None = None,
    yfinance_loader: object | None = None,
) -> MarketDataProvider:
    """Small composition point; unknown names never fall back to mock."""
    normalized = provider_name.strip().lower()
    if normalized == "mock":
        return static_provider or StaticMarketDataProvider(())
    if normalized == "kotak_neo":
        from app.market_data.kotak_neo import KotakNeoCredentials, KotakNeoMarketDataProvider
        credentials = kotak_credentials if isinstance(kotak_credentials, KotakNeoCredentials) else KotakNeoCredentials.from_environment()
        return KotakNeoMarketDataProvider(credentials, transport=kotak_transport)  # type: ignore[arg-type]
    if normalized == "global_datafeeds":
        from app.market_data.global_datafeeds import GlobalDatafeedsHistoricalProvider
        return GlobalDatafeedsHistoricalProvider(gdfl_access_key, transport=gdfl_transport)  # type: ignore[arg-type]
    if normalized == "upstox":
        from app.market_data.upstox import UpstoxHistoricalProvider
        return UpstoxHistoricalProvider(upstox_access_token, transport=upstox_transport)  # type: ignore[arg-type]
    if normalized == "yfinance":
        from app.market_data.yfinance import YahooHistoricalDataProvider
        return YahooHistoricalDataProvider(history_loader=yfinance_loader)  # type: ignore[arg-type]
    raise MarketDataError(ErrorCode.CONFIGURATION_ERROR, "Configured market-data provider is unavailable.")


@dataclass(frozen=True, slots=True)
class StaticMarketDataProvider:
    """A deterministic provider for tests/local composition; it never performs I/O."""

    instruments: tuple[InstrumentIdentity, ...]
    quotes: Mapping[str, CanonicalQuote] = field(default_factory=dict)
    bars: Mapping[str, tuple[CanonicalOHLCVBar, ...]] = field(default_factory=dict)
    indices: Mapping[str, IndexMarketObservation] = field(default_factory=dict)
    breadth: Mapping[str, MarketBreadthObservation] = field(default_factory=dict)
    sessions: Mapping[str, MarketSessionObservation] = field(default_factory=dict)
    provider_capabilities: ProviderCapabilities = field(default_factory=lambda: ProviderCapabilities(
        current_quotes=CapabilityState.SUPPORTED, batch_quotes=CapabilityState.SUPPORTED,
        historical_candles=CapabilityState.SUPPORTED, index_data=CapabilityState.SUPPORTED,
        vix=CapabilityState.SUPPORTED, breadth=CapabilityState.SUPPORTED,
        instrument_master=CapabilityState.SUPPORTED, market_status=CapabilityState.SUPPORTED,
    ))

    def capabilities(self) -> ProviderCapabilities:
        return self.provider_capabilities

    def resolve_instrument(self, query: str) -> InstrumentIdentity | None:
        needle = query.strip().upper()
        return next((item for item in self.instruments if needle in {item.instrument_id.upper(), item.symbol.upper(), (item.trading_symbol or "").upper()}), None)

    def get_quote(self, instrument: InstrumentIdentity) -> CanonicalQuote:
        self._require(self.provider_capabilities.current_quotes)
        try:
            return self.quotes[instrument.instrument_id]
        except KeyError as error:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Requested instrument quote is unavailable.") from error

    def get_quotes(self, instruments: tuple[InstrumentIdentity, ...]) -> BatchQuotesResult:
        self._require(self.provider_capabilities.batch_quotes)
        successful: list[CanonicalQuote] = []
        failures: dict[str, MarketDataError] = {}
        for instrument in instruments:
            try:
                successful.append(self.get_quote(instrument))
            except MarketDataError as error:
                failures[instrument.instrument_id] = error
        warnings = ("one or more requested quotes were unavailable",) if failures else ()
        return BatchQuotesResult(tuple(successful), failures, warnings)

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        self._require(self.provider_capabilities.historical_candles)
        if request.timeframe not in self.provider_capabilities.supported_timeframes:
            raise MarketDataError(ErrorCode.UNSUPPORTED_TIMEFRAME, "Requested timeframe is unsupported.")
        result = tuple(item for item in self.bars.get(request.instrument.instrument_id, ()) if item.timeframe is request.timeframe and request.start <= item.end_time <= request.end)
        if not result:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Requested historical bars are unavailable.")
        return result

    def get_latest_bar(self, instrument: InstrumentIdentity, timeframe: object) -> CanonicalOHLCVBar | None:
        if not hasattr(timeframe, "value"):
            raise MarketDataError(ErrorCode.UNSUPPORTED_TIMEFRAME, "Requested timeframe is unsupported.")
        matching = tuple(item for item in self.bars.get(instrument.instrument_id, ()) if item.timeframe is timeframe)
        return matching[-1] if matching else None

    def get_index_observation(self, instrument: InstrumentIdentity) -> IndexMarketObservation | None:
        self._require(self.provider_capabilities.index_data)
        return self.indices.get(instrument.instrument_id)

    def get_market_breadth(self, universe_reference: str) -> MarketBreadthObservation | None:
        self._require(self.provider_capabilities.breadth)
        return self.breadth.get(universe_reference)

    def get_market_status(self, exchange: object) -> MarketSessionObservation | None:
        self._require(self.provider_capabilities.market_status)
        value = getattr(exchange, "value", str(exchange))
        return self.sessions.get(value)

    @staticmethod
    def _require(capability: CapabilityState) -> None:
        if capability is not CapabilityState.SUPPORTED:
            raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Provider capability is unsupported.", RetryDisposition.NON_RETRYABLE)
