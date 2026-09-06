"""Immutable, provider-neutral market-data facts and validation contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from app.domain.models import DataQuality


class Exchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"
    INDEX = "INDEX"
    UNKNOWN = "UNKNOWN"


class InstrumentType(StrEnum):
    NSE_EQUITY = "NSE_EQUITY"
    BSE_EQUITY = "BSE_EQUITY"
    BROAD_INDEX = "BROAD_INDEX"
    SECTOR_INDEX = "SECTOR_INDEX"
    VOLATILITY_INDEX = "VOLATILITY_INDEX"
    OTHER = "OTHER"


class Timeframe(StrEnum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    SIXTY_MINUTES = "60m"
    DAILY = "1D"
    WEEKLY = "1W"


class AdjustmentStatus(StrEnum):
    RAW = "RAW"
    ADJUSTED = "ADJUSTED"
    UNKNOWN = "UNKNOWN"


class MarketSessionState(StrEnum):
    PRE_OPEN = "PRE_OPEN"
    OPEN = "OPEN"
    POST_CLOSE = "POST_CLOSE"
    CLOSED = "CLOSED"
    HALTED = "HALTED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class FreshnessState(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    VERY_STALE = "VERY_STALE"
    UNKNOWN = "UNKNOWN"


class CapabilityState(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class ErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    AUTHORIZATION_FAILURE = "AUTHORIZATION_FAILURE"
    RATE_LIMITED = "RATE_LIMITED"
    INSTRUMENT_NOT_FOUND = "INSTRUMENT_NOT_FOUND"
    AMBIGUOUS_INSTRUMENT = "AMBIGUOUS_INSTRUMENT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    UNSUPPORTED_TIMEFRAME = "UNSUPPORTED_TIMEFRAME"
    MALFORMED_RESPONSE = "MALFORMED_RESPONSE"
    FRESHNESS_FAILURE = "FRESHNESS_FAILURE"
    QUALITY_FAILURE = "QUALITY_FAILURE"
    PARTIAL_BATCH_FAILURE = "PARTIAL_BATCH_FAILURE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"


class RetryDisposition(StrEnum):
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"


@dataclass(frozen=True, slots=True)
class ProviderInstrumentMapping:
    """A provider token lives here, never in canonical analytical facts."""

    provider: str
    provider_instrument_reference: str
    provider_symbol: str | None = None
    mapping_version: str = "v1"
    provider_exchange_segment: str | None = None

    def __post_init__(self) -> None:
        _required(self.provider, "provider")
        _required(self.provider_instrument_reference, "provider_instrument_reference")


@dataclass(frozen=True, slots=True)
class InstrumentIdentity:
    instrument_id: str
    exchange: Exchange
    symbol: str
    trading_symbol: str | None
    isin: str | None
    series: str | None
    instrument_type: InstrumentType
    name: str | None
    currency: str = "INR"
    provider_mappings: tuple[ProviderInstrumentMapping, ...] = ()

    def __post_init__(self) -> None:
        _required(self.instrument_id, "instrument_id")
        _required(self.symbol, "symbol")
        _required(self.currency, "currency")


@dataclass(frozen=True, slots=True)
class MarketDataProvenance:
    provider: str
    provider_instrument_reference: str | None
    exchange_timestamp: datetime | None
    provider_timestamp: datetime | None
    received_at: datetime
    normalization_version: str
    request_reference: str | None = None
    source_reference: str | None = None
    schema_version: str = "v1"

    def __post_init__(self) -> None:
        _required(self.provider, "provider")
        _required(self.normalization_version, "normalization_version")
        _aware(self.received_at, "received_at")
        for name in ("exchange_timestamp", "provider_timestamp"):
            value = getattr(self, name)
            if value is not None:
                _aware(value, name)


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    state: FreshnessState
    observed_at: datetime | None
    evaluated_at: datetime
    age: timedelta | None
    threshold: timedelta | None
    session_state: MarketSessionState
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalQuote:
    quote_id: str
    instrument: InstrumentIdentity
    last_price: Decimal | None
    previous_close: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    volume: int | None
    turnover: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    bid: Decimal | None
    ask: Decimal | None
    bid_quantity: int | None
    ask_quantity: int | None
    provenance: MarketDataProvenance
    freshness: FreshnessAssessment
    quality: DataQuality = DataQuality.UNKNOWN
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.quote_id, "quote_id")


@dataclass(frozen=True, slots=True)
class CanonicalOHLCVBar:
    bar_id: str
    instrument: InstrumentIdentity
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int | None
    turnover: Decimal | None
    trade_count: int | None
    adjustment_status: AdjustmentStatus
    provenance: MarketDataProvenance
    quality: DataQuality = DataQuality.UNKNOWN
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.bar_id, "bar_id")
        _aware(self.start_time, "start_time")
        _aware(self.end_time, "end_time")
        if self.end_time < self.start_time:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bar end time cannot precede start time.")

    @property
    def source_observation_identity(self) -> str:
        from app.market_data.nse_udiff_source_identity import observation_key
        return observation_key(self)


@dataclass(frozen=True, slots=True)
class IndexMarketObservation:
    observation_id: str
    instrument: InstrumentIdentity
    value: Decimal | None
    previous_close: Decimal | None
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    change: Decimal | None
    change_percent: Decimal | None
    observed_at: datetime
    provenance: MarketDataProvenance
    freshness: FreshnessAssessment
    quality: DataQuality = DataQuality.UNKNOWN
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.observation_id, "observation_id")
        _aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class MarketBreadthObservation:
    observation_id: str
    universe_reference: str
    advances: int | None
    declines: int | None
    unchanged: int | None
    new_highs: int | None
    new_lows: int | None
    percent_above_reference: Decimal | None
    percent_below_reference: Decimal | None
    up_volume: int | None
    down_volume: int | None
    total_constituents: int | None
    coverage_count: int | None
    observed_at: datetime
    provenance: MarketDataProvenance
    freshness: FreshnessAssessment
    quality: DataQuality = DataQuality.UNKNOWN
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.observation_id, "observation_id")
        _required(self.universe_reference, "universe_reference")
        _aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class ParticipationLiquidityObservation:
    observation_id: str
    instrument: InstrumentIdentity
    turnover: Decimal | None
    traded_value: Decimal | None
    trade_count: int | None
    spread: Decimal | None
    bid_depth: int | None
    ask_depth: int | None
    delivery_proxy: Decimal | None
    liquidity_status: str | None
    unusual_participation_flags: tuple[str, ...]
    observed_at: datetime
    provenance: MarketDataProvenance
    freshness: FreshnessAssessment
    quality: DataQuality = DataQuality.UNKNOWN
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketSessionObservation:
    observation_id: str
    exchange: Exchange
    state: MarketSessionState
    observed_at: datetime
    provenance: MarketDataProvenance
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _required(self.observation_id, "observation_id")
        _aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class HistoricalBarsRequest:
    instrument: InstrumentIdentity
    timeframe: Timeframe
    start: datetime
    end: datetime
    adjustment_preference: AdjustmentStatus = AdjustmentStatus.UNKNOWN
    provider_preference: str | None = None

    def __post_init__(self) -> None:
        _aware(self.start, "start")
        _aware(self.end, "end")
        if self.start > self.end:
            raise ValueError("Historical-bar request start cannot follow end.")


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    current_quotes: CapabilityState = CapabilityState.UNKNOWN
    batch_quotes: CapabilityState = CapabilityState.UNKNOWN
    historical_candles: CapabilityState = CapabilityState.UNKNOWN
    supported_timeframes: frozenset[Timeframe] = frozenset()
    index_data: CapabilityState = CapabilityState.UNKNOWN
    vix: CapabilityState = CapabilityState.UNKNOWN
    breadth: CapabilityState = CapabilityState.UNKNOWN
    depth: CapabilityState = CapabilityState.UNKNOWN
    instrument_master: CapabilityState = CapabilityState.UNKNOWN
    websocket: CapabilityState = CapabilityState.UNSUPPORTED
    corporate_actions: CapabilityState = CapabilityState.UNKNOWN
    market_status: CapabilityState = CapabilityState.UNKNOWN
    rate_limit_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_timeframes", frozenset(self.supported_timeframes))
        object.__setattr__(self, "rate_limit_metadata", MappingProxyType(dict(self.rate_limit_metadata)))


@dataclass(frozen=True, slots=True)
class BatchQuotesResult:
    quotes: tuple[CanonicalQuote, ...]
    failures: Mapping[str, "MarketDataError"] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "failures", MappingProxyType(dict(self.failures)))


@dataclass(frozen=True, slots=True)
class MarketDataError(Exception):
    code: ErrorCode
    message: str
    retry: RetryDisposition = RetryDisposition.NON_RETRYABLE

    def __str__(self) -> str:
        return self.message


class MarketDataQualityError(MarketDataError):
    pass


@dataclass(frozen=True, slots=True)
class FreshnessThresholds:
    quote: timedelta
    intraday_bar: timedelta
    daily_bar: timedelta
    index: timedelta
    breadth: timedelta
    closed_session_multiplier: int = 48

    def threshold_for(self, kind: str, timeframe: Timeframe | None = None) -> timedelta:
        if kind == "bar":
            return self.daily_bar if timeframe in {Timeframe.DAILY, Timeframe.WEEKLY} else self.intraday_bar
        return getattr(self, kind)


class SessionAwareFreshnessEvaluator:
    """Classifies age only; it does not infer exchange calendars or availability."""

    def __init__(self, thresholds: FreshnessThresholds) -> None:
        self._thresholds = thresholds

    def evaluate(
        self,
        *,
        observed_at: datetime | None,
        evaluated_at: datetime,
        kind: str,
        session_state: MarketSessionState = MarketSessionState.UNKNOWN,
        timeframe: Timeframe | None = None,
    ) -> FreshnessAssessment:
        _aware(evaluated_at, "evaluated_at")
        if observed_at is None or not _is_aware(observed_at):
            return FreshnessAssessment(FreshnessState.UNKNOWN, observed_at, evaluated_at, None, None, session_state, ("observation timestamp unavailable",))
        threshold = self._thresholds.threshold_for(kind, timeframe)
        if session_state in {MarketSessionState.CLOSED, MarketSessionState.POST_CLOSE, MarketSessionState.PRE_OPEN}:
            threshold *= self._thresholds.closed_session_multiplier
        age = evaluated_at - observed_at
        if age.total_seconds() < 0:
            return FreshnessAssessment(FreshnessState.UNKNOWN, observed_at, evaluated_at, age, threshold, session_state, ("observation timestamp is in the future",))
        if age <= threshold:
            state = FreshnessState.FRESH
        elif age <= threshold * 2:
            state = FreshnessState.STALE
        else:
            state = FreshnessState.VERY_STALE
        warnings = ("feed/session is degraded",) if session_state is MarketSessionState.DEGRADED else ()
        return FreshnessAssessment(state, observed_at, evaluated_at, age, threshold, session_state, warnings)


class MarketDataQualityValidator:
    """Rejects material corruption without repairing provider data."""

    @staticmethod
    def validate_quote(value: CanonicalQuote) -> None:
        for name in ("last_price", "previous_close", "open", "high", "low", "bid", "ask"):
            amount = getattr(value, name)
            if amount is not None and amount <= 0:
                raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, f"Quote {name} must be positive.")
        if value.volume is not None and value.volume < 0:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Quote volume cannot be negative.")
        if value.bid is not None and value.ask is not None and value.bid > value.ask:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Quote bid cannot exceed ask.")
        if value.high is not None and value.low is not None and value.high < value.low:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Quote high cannot be below low.")

    @staticmethod
    def validate_bar(value: CanonicalOHLCVBar) -> None:
        if min(value.open, value.high, value.low, value.close) <= 0:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "OHLC prices must be positive.")
        if value.high < value.low:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bar high cannot be below low.")
        if value.open < value.low or value.open > value.high or value.close < value.low or value.close > value.high:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bar open/close must lie within high/low.")
        if value.volume is not None and value.volume < 0:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bar volume cannot be negative.")
        if value.trade_count is not None and value.trade_count < 0:
            raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bar trade count cannot be negative.")

    @classmethod
    def validate_bar_collection(cls, values: tuple[CanonicalOHLCVBar, ...]) -> None:
        ids: set[str] = set()
        logical_keys: set[tuple[str, Timeframe, datetime]] = set()
        previous: CanonicalOHLCVBar | None = None
        for value in values:
            cls.validate_bar(value)
            if value.bar_id in ids:
                raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Duplicate bar ID.")
            logical_key = (value.instrument.instrument_id, value.timeframe, value.end_time)
            if logical_key in logical_keys:
                raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Duplicate bar timeframe/end timestamp.")
            if previous is not None and value.end_time < previous.end_time:
                raise MarketDataQualityError(ErrorCode.QUALITY_FAILURE, "Bars are out of chronological order.")
            ids.add(value.bar_id)
            logical_keys.add(logical_key)
            previous = value


def _required(value: str | None, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required.")


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _aware(value: object, name: str) -> None:
    if not _is_aware(value):
        raise ValueError(f"{name} must be timezone-aware.")
