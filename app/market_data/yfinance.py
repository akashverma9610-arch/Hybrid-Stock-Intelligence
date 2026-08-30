"""Secondary, research-only Yahoo Finance daily OHLCV adapter.

The adapter deliberately asks yfinance for *raw* OHLC (``auto_adjust=False``
and ``back_adjust=False``).  Yahoo's adjusted-close column is not substituted
for canonical close and Yahoo corporate-action data is never treated as an
authoritative security-master source.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Callable, Mapping, Sequence

from app.domain.models import DataQuality
from app.market_data.models import (
    AdjustmentStatus, CapabilityState, CanonicalOHLCVBar, ErrorCode,
    HistoricalBarsRequest, InstrumentIdentity, InstrumentType, MarketDataError,
    MarketDataProvenance, ProviderCapabilities, ProviderInstrumentMapping,
    RetryDisposition, Timeframe,
)


YFINANCE_PROVIDER = "yfinance"
YFINANCE_MAPPING_VERSION = "yfinance-nse-v1"


@dataclass(frozen=True, slots=True)
class YahooHistoryRequest:
    symbol: str
    start: datetime
    end: datetime
    interval: str = "1d"
    auto_adjust: bool = False
    back_adjust: bool = False
    actions: bool = False


@dataclass(frozen=True, slots=True)
class YahooHistoryPayload:
    """Provider-neutral representation kept on the adapter side only."""
    rows: tuple[Mapping[str, object], ...]
    metadata: Mapping[str, object]


def yahoo_nse_mapping(instrument: InstrumentIdentity) -> ProviderInstrumentMapping | None:
    """Create the one controlled NSE-equity ``.NS`` mapping.

    The mapping is deterministic rather than a fuzzy company-name lookup.  A
    caller must still persist it through the canonical mapping store before a
    subsequent history request can use it.
    """
    if instrument.instrument_type is not InstrumentType.NSE_EQUITY or instrument.exchange.value != "NSE":
        return None
    symbol = (instrument.trading_symbol or instrument.symbol).strip().upper()
    if not symbol or not all(character.isalnum() or character in {"-", "_"} for character in symbol):
        return None
    yahoo_symbol = f"{symbol}.NS"
    return ProviderInstrumentMapping(
        YFINANCE_PROVIDER, yahoo_symbol, yahoo_symbol, YFINANCE_MAPPING_VERSION, "NSE",
    )


def yahoo_nifty500_candidate_mapping(instrument: InstrumentIdentity) -> ProviderInstrumentMapping | None:
    """Return an explicitly *unverified* Yahoo candidate for NIFTY 500.

    The caller must validate provider metadata and history before using this
    mapping.  It is intentionally not a NIFTY 50 substitution.
    """
    if instrument.instrument_type is not InstrumentType.BROAD_INDEX or instrument.instrument_id != "NIFTY_500":
        return None
    return ProviderInstrumentMapping(YFINANCE_PROVIDER, "^CRSLDX", "^CRSLDX", YFINANCE_MAPPING_VERSION, "NSE_INDEX")


class YahooHistoricalDataProvider:
    """Optional yfinance-backed daily history; it exposes no quote/trading APIs."""

    def __init__(
        self,
        *,
        history_loader: Callable[[YahooHistoryRequest], YahooHistoryPayload] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 20.0,
    ) -> None:
        self._loader, self._clock, self._timeout = history_loader, clock, timeout_seconds

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            historical_candles=CapabilityState.SUPPORTED,
            supported_timeframes=frozenset({Timeframe.DAILY}),
            current_quotes=CapabilityState.UNSUPPORTED,
            batch_quotes=CapabilityState.UNSUPPORTED,
            index_data=CapabilityState.UNSUPPORTED,
            corporate_actions=CapabilityState.UNSUPPORTED,
            instrument_master=CapabilityState.UNSUPPORTED,
            rate_limit_metadata={"classification": "SECONDARY_RESEARCH_NON_AUTHORITATIVE"},
        )

    def request_parameters(self, request: HistoricalBarsRequest) -> YahooHistoryRequest:
        if request.timeframe is not Timeframe.DAILY:
            raise MarketDataError(ErrorCode.UNSUPPORTED_TIMEFRAME, "yfinance adapter currently supports daily bars only.")
        mapping = _mapping(request.instrument)
        # yfinance's end is exclusive. Include the requested final session.
        return YahooHistoryRequest(mapping.provider_instrument_reference, request.start, request.end + timedelta(days=1))

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        outbound = self.request_parameters(request)
        try:
            payload = (self._loader or self._yfinance_history)(outbound)
        except MarketDataError:
            raise
        except Exception as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Yahoo historical request failed.", RetryDisposition.RETRYABLE) from error
        _verify_identity(request.instrument, outbound.symbol, payload.metadata)
        received = self._clock().astimezone(UTC)
        mapping = _mapping(request.instrument)
        accepted: list[CanonicalOHLCVBar] = []
        rejected = 0
        for row in payload.rows:
            try:
                accepted.append(_bar_from_row(request, mapping, row, received))
            except MarketDataError as error:
                if error.code is not ErrorCode.MALFORMED_RESPONSE:
                    raise
                rejected += 1
        values = tuple(accepted)
        if not values:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE if payload.rows else ErrorCode.INSTRUMENT_NOT_FOUND, "Yahoo returned no usable daily history for the mapped NSE equity.")
        if rejected:
            values = tuple(replace(value, warnings=(*value.warnings, f"YFINANCE_REJECTED_MALFORMED_ROWS:{rejected}")) for value in values)
        return tuple(sorted(values, key=lambda item: (item.start_time, item.end_time, item.bar_id)))

    def _yfinance_history(self, request: YahooHistoryRequest) -> YahooHistoryPayload:
        try:
            import yfinance as yf
        except ImportError as error:  # pragma: no cover - dependency contract test covers installed package
            raise MarketDataError(ErrorCode.CONFIGURATION_ERROR, "yfinance dependency is not installed.") from error
        ticker = yf.Ticker(request.symbol)
        frame = ticker.history(
            start=request.start.date().isoformat(), end=request.end.date().isoformat(),
            interval=request.interval, auto_adjust=request.auto_adjust,
            back_adjust=request.back_adjust, actions=request.actions, repair=False,
            raise_errors=True, timeout=self._timeout,
        )
        if frame is None or getattr(frame, "empty", True):
            return YahooHistoryPayload((), dict(getattr(ticker, "history_metadata", {}) or {}))
        rows: list[Mapping[str, object]] = []
        for index, row in frame.iterrows():
            values = {str(key): value for key, value in row.to_dict().items()}
            values["Date"] = index
            rows.append(values)
        return YahooHistoryPayload(tuple(rows), dict(getattr(ticker, "history_metadata", {}) or {}))


def _mapping(instrument: InstrumentIdentity) -> ProviderInstrumentMapping:
    matches = tuple(item for item in instrument.provider_mappings if item.provider.lower() == YFINANCE_PROVIDER)
    if len(matches) != 1:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "yfinance NSE mapping is required.")
    return matches[0]


def _verify_identity(instrument: InstrumentIdentity, expected_symbol: str, metadata: Mapping[str, object]) -> None:
    """Fail closed only for a contradictory provider identity response.

    Yahoo does not guarantee metadata for every historical response.  An absent
    metadata field is recorded as a warning on bars; a present contradictory
    symbol/exchange/type is an identity failure.
    """
    symbol = metadata.get("symbol") or metadata.get("ticker")
    if isinstance(symbol, str) and symbol.strip().upper() != expected_symbol.upper():
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Yahoo returned history for a different symbol.")
    exchange = metadata.get("exchangeName") or metadata.get("exchange")
    accepted_exchanges = {"NSE", "NSI", "NATIONAL STOCK EXCHANGE"} if instrument.instrument_type is InstrumentType.NSE_EQUITY else {"NSE", "NSI", "NSE INDEX", "INDEX"}
    if isinstance(exchange, str) and exchange.strip().upper() not in accepted_exchanges:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Yahoo returned history outside the NSE equity exchange.")
    quote_type = metadata.get("instrumentType") or metadata.get("quoteType")
    expected_types = {"EQUITY", "STOCK"} if instrument.instrument_type is InstrumentType.NSE_EQUITY else {"INDEX"}
    if isinstance(quote_type, str) and quote_type.strip().upper() not in expected_types:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Yahoo returned history with an incompatible instrument type.")
    if instrument.instrument_id == "NIFTY_500":
        name = metadata.get("shortName") or metadata.get("longName")
        if isinstance(name, str) and "NIFTY 500" not in name.upper():
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Yahoo benchmark candidate is not NIFTY 500.")


def _bar_from_row(
    request: HistoricalBarsRequest, mapping: ProviderInstrumentMapping, row: Mapping[str, object], received: datetime,
) -> CanonicalOHLCVBar:
    try:
        start = _timestamp(row.get("Date"))
        open_, high, low, close = (_decimal(row.get(key)) for key in ("Open", "High", "Low", "Close"))
        volume = _optional_integer(row.get("Volume"))
        if min(open_, high, low, close) <= 0 or high < max(open_, low, close) or low > min(open_, high, close) or (volume is not None and volume < 0):
            raise ValueError()
    except (ValueError, TypeError, InvalidOperation):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Yahoo daily OHLCV row is malformed.") from None
    key = f"{request.instrument.instrument_id}:{request.timeframe.value}:{start.isoformat()}"
    warnings = ["YFINANCE_SECONDARY_RESEARCH_NON_AUTHORITATIVE", "YFINANCE_RAW_OHLC_AUTO_ADJUST_FALSE"]
    if row.get("Adj Close") is not None:
        warnings.append("YFINANCE_ADJ_CLOSE_NOT_SUBSTITUTED")
    return CanonicalOHLCVBar(
        f"yfinance:{sha256(key.encode()).hexdigest()[:24]}", request.instrument, request.timeframe,
        start, start + timedelta(days=1), open_, high, low, close, volume, None, None,
        AdjustmentStatus.RAW,
        MarketDataProvenance(
            YFINANCE_PROVIDER, mapping.provider_instrument_reference, start, start, received,
            "yfinance-history-v1", "yfinance.Ticker.history", "yfinance-secondary-research",
        ),
        DataQuality.HIGH, tuple(warnings),
    )


def _timestamp(value: object) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()  # pandas Timestamp without importing its type
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    # A daily Yahoo date without timezone is a session label, not an instant.
    return (result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC))


def _decimal(value: object) -> Decimal:
    if value is None or isinstance(value, bool):
        raise ValueError()
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError()
    return result


def _integer(value: object) -> int:
    result = _decimal(value)
    if result != result.to_integral_value():
        raise ValueError()
    return int(result)


def _optional_integer(value: object) -> int | None:
    if value is None:
        return None
    try:
        return _integer(value)
    except (ValueError, InvalidOperation):
        # Yahoo occasionally emits a non-finite/missing volume for an
        # otherwise valid daily price bar. Volume is optional in the existing
        # canonical contract, so retain the price fact without fabricating 0.
        return None


__all__ = (
    "YFINANCE_PROVIDER", "YFINANCE_MAPPING_VERSION", "YahooHistoricalDataProvider",
    "YahooHistoryPayload", "YahooHistoryRequest", "yahoo_nse_mapping", "yahoo_nifty500_candidate_mapping",
)
