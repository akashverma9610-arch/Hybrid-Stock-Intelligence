"""Upstox Historical Candle V3 adapter; historical OHLCV only.

The adapter deliberately accepts a small injectable transport.  Production
composition may opt in to the documented HTTPS transport, while tests and all
analysis paths remain network-free.  Upstox does not document an adjustment
guarantee for V3 candles, so every normalised bar is retained as ``UNKNOWN``
adjustment status rather than being represented as fully adjusted.
"""
from __future__ import annotations

import json
import gzip
import requests
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from app.domain.models import DataQuality
from app.market_data.models import (
    AdjustmentStatus, CapabilityState, CanonicalOHLCVBar, ErrorCode,
    HistoricalBarsRequest, InstrumentIdentity, InstrumentType, MarketDataError,
    MarketDataProvenance, ProviderCapabilities, ProviderInstrumentMapping,
    RetryDisposition, Timeframe,
)


UPSTOX_PROVIDER = "upstox"
_V3_DAILY = ("days", "1")
_V3_ENDPOINT = "https://api.upstox.com/v3/historical-candle"
# Official documented NSE BOD instrument JSON.  It is public metadata, not a
# credential-bearing endpoint.  Only an explicitly requested bounded cohort is
# ever persisted from this master.
UPSTOX_NSE_BOD_URL = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"


@dataclass(frozen=True, slots=True)
class UpstoxHistoricalRequest:
    """The documented V3 request shape without retaining a credential."""

    url: str
    headers: Mapping[str, str]
    instrument_key: str
    unit: str
    interval: str
    from_date: str
    to_date: str


@dataclass(frozen=True, slots=True)
class UpstoxInstrumentRecord:
    """Minimal official BOD-instrument fields required for safe mapping."""

    instrument_key: str
    segment: str
    exchange: str
    instrument_type: str | None
    isin: str | None
    trading_symbol: str | None
    name: str | None = None
    security_type: str | None = None


@dataclass(frozen=True, slots=True)
class UpstoxInstrumentMaster:
    """Sanitised official BOD master metadata plus parseable records."""

    source_url: str
    checksum: str
    records: tuple[UpstoxInstrumentRecord, ...]


def parse_upstox_instrument_records(payload: object) -> tuple[UpstoxInstrumentRecord, ...]:
    """Parse the official BOD JSON format; malformed rows are not mappings."""
    rows = payload.get("data") if isinstance(payload, dict) and isinstance(payload.get("data"), list) else payload
    if not isinstance(rows, list):
        raise ValueError("Upstox instrument-master payload must be a JSON array.")
    records: list[UpstoxInstrumentRecord] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        key, segment, exchange = row.get("instrument_key"), row.get("segment"), row.get("exchange")
        if not all(isinstance(value, str) and value.strip() for value in (key, segment, exchange)):
            continue
        records.append(UpstoxInstrumentRecord(
            key.strip(), segment.strip().upper(), exchange.strip().upper(),
            _text(row.get("instrument_type")), _text(row.get("isin")), _text(row.get("trading_symbol")),
            _text(row.get("name")), _text(row.get("security_type")),
        ))
    return tuple(records)


def load_upstox_nse_bod_instrument_master(
    *,
    url: str = UPSTOX_NSE_BOD_URL,
    timeout_seconds: float = 20.0,
    maximum_bytes: int = 30 * 1024 * 1024,
    downloader: Callable[[str, float], bytes] | None = None,
) -> UpstoxInstrumentMaster:
    """Load the documented compressed NSE BOD JSON with bounded resource use.

    The caller owns the decision to make this public metadata request.  This
    function never uses access tokens and never persists the full master.
    """
    if maximum_bytes < 1:
        raise ValueError("Upstox instrument-master size limit must be positive.")
    try:
        raw = (downloader or _download_bod)(url, timeout_seconds)
        if len(raw) > maximum_bytes:
            raise ValueError("Upstox instrument-master exceeded the configured size limit.")
        decoded = gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
        payload = json.loads(decoded.decode("utf-8"))
        records = parse_upstox_instrument_records(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox NSE instrument master is malformed.") from error
    if not records:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox NSE instrument master contains no usable records.")
    return UpstoxInstrumentMaster(url, sha256(raw).hexdigest(), records)


def exact_upstox_mapping(instrument: InstrumentIdentity, records: Sequence[UpstoxInstrumentRecord]) -> ProviderInstrumentMapping | None:
    """Resolve only exact ISIN+segment mappings (or exact index identity)."""
    if instrument.instrument_type is InstrumentType.NSE_EQUITY:
        if not instrument.isin:
            return None
        matches = tuple(item for item in records if item.segment == "NSE_EQ" and item.isin and item.isin.upper() == instrument.isin.upper())
    elif instrument.instrument_type is InstrumentType.BROAD_INDEX:
        symbol = (instrument.trading_symbol or instrument.symbol).strip().upper()
        matches = tuple(item for item in records if item.segment == "NSE_INDEX" and (item.trading_symbol or "").strip().upper() == symbol)
    else:
        return None
    if len(matches) != 1:
        return None
    match = matches[0]
    return ProviderInstrumentMapping(UPSTOX_PROVIDER, match.instrument_key, match.trading_symbol, "upstox-v3", match.segment)


def _download_bod(url: str, timeout_seconds: float) -> bytes:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}, method="GET"), timeout=timeout_seconds) as response:  # nosec B310: documented public BOD metadata
            return response.read()
    except (HTTPError, URLError, OSError) as error:
        raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox NSE instrument master is unavailable.", RetryDisposition.RETRYABLE) from error


class UpstoxHistoricalProvider:
    """Official Upstox V3 daily-history adapter, with no quote/trading methods."""

    def __init__(
        self,
        access_token: str | None = None,
        *,
        transport: Callable[[UpstoxHistoricalRequest], object] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        timeout_seconds: float = 20.0,
    ) -> None:
        self._token, self._transport, self._clock, self._timeout = _bearer_token(access_token), transport, clock, timeout_seconds

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            historical_candles=CapabilityState.SUPPORTED,
            supported_timeframes=frozenset({Timeframe.DAILY}),
            current_quotes=CapabilityState.UNSUPPORTED,
            batch_quotes=CapabilityState.UNSUPPORTED,
            # Historical Candle V3 accepts persisted NSE_INDEX mappings.  It
            # is historical index data only; this does not imply live quotes
            # or a provider-native breadth capability.
            index_data=CapabilityState.SUPPORTED,
            instrument_master=CapabilityState.SUPPORTED,
        )

    def request_parameters(self, request: HistoricalBarsRequest) -> UpstoxHistoricalRequest:
        if not self._token:
            raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Upstox Analytics Token is required for historical access.")
        if request.timeframe is not Timeframe.DAILY:
            raise MarketDataError(ErrorCode.UNSUPPORTED_TIMEFRAME, "Upstox V3 adapter currently supports daily candles only.")
        mapping = _mapping(request.instrument)
        instrument_key = quote(mapping.provider_instrument_reference, safe="")
        unit, interval = _V3_DAILY
        # The official V3 contract is .../{to_date}/{from_date}.
        url = f"{_V3_ENDPOINT}/{instrument_key}/{unit}/{interval}/{request.end.date().isoformat()}/{request.start.date().isoformat()}"
        return UpstoxHistoricalRequest(
            url=url,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
            },
            instrument_key=mapping.provider_instrument_reference,
            unit=unit,
            interval=interval,
            from_date=request.start.date().isoformat(),
            to_date=request.end.date().isoformat(),
        )

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        outbound = self.request_parameters(request)
        try:
            payload = (self._transport or self._https_transport)(outbound)
        except MarketDataError:
            raise
        except TimeoutError as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical request timed out.", RetryDisposition.RETRYABLE) from error
        except Exception as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical request failed.", RetryDisposition.RETRYABLE) from error
        rows = _candles(payload)
        received = self._clock()
        mapping = _mapping(request.instrument)
        bars = tuple(_bar_from_candle(request, mapping, row, received) for row in rows)
        return tuple(sorted(bars, key=lambda item: (item.start_time, item.end_time, item.bar_id)))

    def _https_transport(self, request: UpstoxHistoricalRequest) -> object:
        try:
            response = requests.get(request.url, headers=dict(request.headers), timeout=self._timeout)
            status = response.status_code
            if status == 401:
                raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Upstox access token was rejected.")
            if status == 403:
                raise MarketDataError(ErrorCode.AUTHORIZATION_FAILURE, "Upstox historical access is not authorized.")
            if status == 404:
                raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Upstox instrument history is unavailable.")
            if status == 429:
                raise MarketDataError(ErrorCode.RATE_LIMITED, "Upstox historical rate limit reached.", RetryDisposition.RETRYABLE)
            if status >= 400:
                raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical service is unavailable.", RetryDisposition.RETRYABLE)
            return json.loads(response.content.decode("utf-8"))
        except requests.RequestException as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical service is unavailable.", RetryDisposition.RETRYABLE) from error
        except json.JSONDecodeError as error:
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical service is unavailable.", RetryDisposition.RETRYABLE) from error


def _mapping(instrument: InstrumentIdentity) -> ProviderInstrumentMapping:
    matches = tuple(item for item in instrument.provider_mappings if item.provider.lower() == UPSTOX_PROVIDER)
    if len(matches) != 1:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Upstox instrument mapping is required.")
    return matches[0]


def _candles(payload: object) -> list[object]:
    if not isinstance(payload, Mapping):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox historical response is malformed.")
    if payload.get("status") not in {"success", "SUCCESS", None}:
        raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Upstox historical request was not successful.")
    data = payload.get("data")
    rows = data.get("candles") if isinstance(data, Mapping) else None
    if not isinstance(rows, list):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox historical response has no candles array.")
    return rows


def _bar_from_candle(request: HistoricalBarsRequest, mapping: ProviderInstrumentMapping, row: object, received: datetime) -> CanonicalOHLCVBar:
    if not isinstance(row, (list, tuple)) or len(row) < 6:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox candle row is malformed.")
    try:
        end = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00")).astimezone(UTC)
        open_, high, low, close = (Decimal(str(value)) for value in row[1:5])
        # V3 index candles can legitimately omit volume.  Canonical OHLCV
        # represents that absence as ``None`` rather than inventing zero or
        # rejecting otherwise valid index price history.
        volume = _optional_integer(row[5])
        if min(open_, high, low, close) < 0 or high < max(open_, low, close) or low > min(open_, high, close) or (volume is not None and volume < 0):
            raise ValueError()
    except (ValueError, TypeError, InvalidOperation):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox candle OHLCV values are malformed.") from None
    # V3 emits OI as the seventh array element.  The existing canonical OHLCV
    # contract has no OI field, so it remains non-required/non-analytical and
    # is explicitly surfaced as an availability warning rather than invented.
    oi_warning = ("UPSTOX_OPEN_INTEREST_NOT_IN_CANONICAL_OHLCV_CONTRACT",) if len(row) > 6 and row[6] is not None else ()
    key = f"{request.instrument.instrument_id}:{request.timeframe.value}:{end.isoformat()}"
    provenance = MarketDataProvenance(
        UPSTOX_PROVIDER, mapping.provider_instrument_reference, end, end, received,
        "upstox-history-v3", "Historical Candle V3", "upstox-v3-historical-candle",
    )
    return CanonicalOHLCVBar(
        f"upstox:{sha256(key.encode()).hexdigest()[:24]}", request.instrument, request.timeframe,
        end - timedelta(days=1), end, open_, high, low, close, volume, None, None,
        AdjustmentStatus.UNKNOWN, provenance, DataQuality.HIGH,
        ("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED", *oi_warning),
    )


def _integer(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError()
    converted = int(str(value))
    if Decimal(str(value)) != Decimal(converted):
        raise ValueError()
    return converted


def _optional_integer(value: object) -> int | None:
    return None if value is None or (isinstance(value, str) and not value.strip()) else _integer(value)


def _bearer_token(value: str | None) -> str | None:
    """Normalise a securely stored raw or accidentally-prefixed bearer token."""
    token = value.strip() if isinstance(value, str) else ""
    while token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = (
    "UPSTOX_PROVIDER", "UpstoxHistoricalProvider", "UpstoxHistoricalRequest",
    "UPSTOX_NSE_BOD_URL", "UpstoxInstrumentMaster", "UpstoxInstrumentRecord",
    "exact_upstox_mapping", "load_upstox_nse_bod_instrument_master", "parse_upstox_instrument_records",
)
