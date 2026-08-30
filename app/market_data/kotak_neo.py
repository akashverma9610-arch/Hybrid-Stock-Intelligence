"""Read-only Kotak Neo adapter for the current Neo API stack.

Only documented market-data paths are present.  This module intentionally has
no order, portfolio, account, WebSocket, or scheduler capability.
"""
from __future__ import annotations

import csv
import io
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Protocol, Sequence
from urllib.parse import urljoin, urlparse

from app.domain.models import DataQuality
from app.market_data.models import (
    BatchQuotesResult,
    CanonicalOHLCVBar,
    CanonicalQuote,
    CapabilityState,
    ErrorCode,
    Exchange,
    FreshnessAssessment,
    FreshnessThresholds,
    HistoricalBarsRequest,
    IndexMarketObservation,
    InstrumentIdentity,
    InstrumentType,
    MarketBreadthObservation,
    MarketDataError,
    MarketDataProvenance,
    MarketDataQualityValidator,
    MarketSessionObservation,
    ProviderCapabilities,
    ProviderInstrumentMapping,
    RetryDisposition,
    SessionAwareFreshnessEvaluator,
    Timeframe,
)
from app.market_data.normalization import MarketDataNormalizer


KOTAK_NEO_PROVIDER = "KOTAK_NEO"
KOTAK_NEO_LOGIN_URL = "https://mis.kotaksecurities.com/login/1.0/tradeApiLogin"
KOTAK_NEO_VALIDATE_URL = "https://mis.kotaksecurities.com/login/1.0/tradeApiValidate"
KOTAK_NEO_MARKET_DATA_BASE_URL = "https://mis.kotaksecurities.com"
KOTAK_NEO_QUOTES_PATH = "/script-details/1.0/quotes/neosymbol/{tokens}/all"
KOTAK_NEO_SCRIP_MASTER_PATHS = "/script-details/1.0/masterscrip/file-paths"
KOTAK_NEO_MASTER_FILE_MAX_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class KotakNeoCredentials:
    """Required current-Neo credential names; values are always redacted."""

    tradeapi_access_token: str | None
    mobile_number: str | None = None
    ucc: str | None = None
    mpin: str | None = None

    def __repr__(self) -> str:
        return "KotakNeoCredentials(tradeapi_access_token=<redacted>, mobile_number=<redacted>, ucc=<redacted>, mpin=<redacted>)"

    __str__ = __repr__

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "KotakNeoCredentials":
        source = os.environ if environ is None else environ
        return cls(
            tradeapi_access_token=source.get("KOTAK_NEO_TRADEAPI_ACCESS_TOKEN"),
            mobile_number=source.get("KOTAK_NEO_MOBILE_NUMBER"),
            ucc=source.get("KOTAK_NEO_UCC"),
            mpin=source.get("KOTAK_NEO_MPIN"),
        )

    def require_tradeapi_access_token(self) -> str:
        if not self.tradeapi_access_token:
            raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo TradeAPI Access Token is required.")
        return self.tradeapi_access_token

    def require_interactive_login(self) -> tuple[str, str, str, str]:
        access_token = self.require_tradeapi_access_token()
        if not all((self.mobile_number, self.ucc, self.mpin)):
            raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo TOTP session credentials are incomplete.")
        return access_token, self.mobile_number or "", self.ucc or "", self.mpin or ""


@dataclass(frozen=True, slots=True, repr=False)
class KotakNeoSession:
    session_token: str
    session_id: str | None
    base_url: str
    established_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.session_token or not self.base_url.startswith("https://"):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo session response is incomplete.")
        if self.established_at.tzinfo is None or self.established_at.utcoffset() is None:
            raise ValueError("Kotak Neo session timestamp must be timezone-aware.")

    def __repr__(self) -> str:
        return "KotakNeoSession(session_token=<redacted>, session_id=<redacted>, base_url=<dynamic>, established_at=<timestamp>)"

    __str__ = __repr__

    def expired(self, now: datetime) -> bool:
        return self.expires_at is not None and now >= self.expires_at


@dataclass(frozen=True, slots=True)
class KotakNeoHttpResponse:
    status_code: int
    payload: Any
    headers: Mapping[str, str] = field(default_factory=dict)
    content: bytes | None = None


class KotakNeoHttpTransport(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        json_body: Mapping[str, Any] | None,
        timeout_seconds: float,
    ) -> KotakNeoHttpResponse: ...


class KotakNeoSdkClient(Protocol):
    """The small, read-only subset of the official ``NeoAPI`` client we use."""

    def scrip_master(self, exchange_segment: str | None = None) -> dict[str, Any]: ...
    def quotes(self, instrument_tokens: list[dict[str, str]] | None = None, quote_type: str | None = None) -> dict[str, Any]: ...
    def totp_login(self, mobile_number: str | None = None, ucc: str | None = None, totp: str | None = None) -> dict[str, Any]: ...
    def totp_validate(self, mpin: str | None = None) -> dict[str, Any]: ...


def _official_sdk(*, consumer_key: str, environment: str) -> KotakNeoSdkClient:
    """Import the official SDK lazily; construction itself makes no request."""
    from neo_api_client import NeoAPI
    return NeoAPI(consumer_key=consumer_key, environment=environment)


class HttpxKotakNeoTransport:
    """Lazy httpx transport; construction and imports never make a request."""

    def request(self, *, method: str, url: str, headers: Mapping[str, str], json_body: Mapping[str, Any] | None, timeout_seconds: float) -> KotakNeoHttpResponse:
        try:
            import httpx
            with httpx.Client(timeout=timeout_seconds, http2=True) as client:
                response = client.request(method, url, headers=dict(headers), json=json_body)
        except Exception as error:
            if error.__class__.__name__ in {"TimeoutException", "ConnectTimeout", "ReadTimeout"}:
                raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Kotak Neo market-data request timed out.", RetryDisposition.RETRYABLE) from None
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Kotak Neo market-data provider is unavailable.", RetryDisposition.RETRYABLE) from None
        try:
            payload = response.json()
        except ValueError:
            payload = None
        return KotakNeoHttpResponse(response.status_code, payload, dict(response.headers), response.content)

    def download_master_file(self, *, url: str, timeout_seconds: float, max_bytes: int = KOTAK_NEO_MASTER_FILE_MAX_BYTES) -> KotakNeoHttpResponse:
        """Bounded public-file download matching the official SDK's CSV path."""
        try:
            import httpx
            with httpx.Client(timeout=timeout_seconds, http2=True, follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    declared_size = response.headers.get("content-length")
                    if declared_size and int(declared_size) > max_bytes:
                        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo instrument master exceeds the configured size limit.")
                    chunks: list[bytes] = []
                    received = 0
                    for chunk in response.iter_bytes():
                        received += len(chunk)
                        if received > max_bytes:
                            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo instrument master exceeds the configured size limit.")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    try:
                        payload = json.loads(content)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        payload = None
                    return KotakNeoHttpResponse(response.status_code, payload, dict(response.headers), content)
        except MarketDataError:
            raise
        except Exception as error:
            if error.__class__.__name__ in {"TimeoutException", "ConnectTimeout", "ReadTimeout"}:
                raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Kotak Neo instrument-master request timed out.", RetryDisposition.RETRYABLE) from None
            raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Kotak Neo instrument-master provider is unavailable.", RetryDisposition.RETRYABLE) from None


def kotak_error_from_response(response: KotakNeoHttpResponse) -> MarketDataError:
    code = response.status_code
    if code == 429:
        return MarketDataError(ErrorCode.RATE_LIMITED, "Kotak Neo rate limit reached.", RetryDisposition.RETRYABLE)
    if code in {401, 403}:
        return MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo authentication is required.")
    if code in {502, 503, 504} or code >= 500:
        return MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "Kotak Neo market-data provider is unavailable.", RetryDisposition.RETRYABLE)
    return MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo returned an unsuccessful response.")


@dataclass(frozen=True, slots=True)
class KotakNeoAuthenticationError(MarketDataError):
    """Sanitized authentication-stage failure; provider payloads are never exposed."""

    category: str = "PROVIDER_UNAVAILABLE"
    http_status: int | None = None


class KotakNeoAuthClient:
    """Explicit current-Neo TOTP → MPIN → dynamic-baseUrl session flow."""

    def __init__(self, transport: KotakNeoHttpTransport, *, timeout_seconds: float, clock: Callable[[], datetime]) -> None:
        self._transport, self._timeout_seconds, self._clock = transport, timeout_seconds, clock

    def authenticate(self, credentials: KotakNeoCredentials, *, current_totp: str) -> KotakNeoSession:
        access_token, mobile, ucc, mpin = credentials.require_interactive_login()
        if not current_totp.isdigit() or len(current_totp) != 6:
            raise KotakNeoAuthenticationError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo current authenticator TOTP is invalid.", RetryDisposition.NON_RETRYABLE, "INVALID_TOTP")
        try:
            login = self._request(
                "POST", KOTAK_NEO_LOGIN_URL,
                {"Authorization": access_token, "neo-fin-key": "neotradeapi", "Content-Type": "application/json"},
                {"mobileNumber": mobile, "ucc": ucc, "totp": current_totp},
                stage="login",
            )
            login_data = _data(login)
            view_token = _text(login_data, "token")
            session_id = _text(login_data, "sid")
        except KotakNeoAuthenticationError:
            raise
        except MarketDataError as error:
            raise self._authentication_error("login", error) from None
        try:
            validate = self._request(
                "POST", KOTAK_NEO_VALIDATE_URL,
                {"Authorization": access_token, "neo-fin-key": "neotradeapi", "sid": session_id, "Auth": view_token, "Content-Type": "application/json"},
                {"mpin": mpin},
                stage="mpin",
            )
            data = _data(validate)
            base_url = _optional_text_any(data, "baseUrl", "base_url")
            if not base_url:
                raise KotakNeoAuthenticationError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo session base URL is missing.", RetryDisposition.NON_RETRYABLE, "SESSION_BASE_URL_MISSING")
            session_token = _text_any(data, "token", "sessionToken", "session_token")
        except KotakNeoAuthenticationError:
            raise
        except MarketDataError as error:
            raise self._authentication_error("mpin", error) from None
        try:
            return KotakNeoSession(session_token, _optional_text_any(data, "sid", "sessionId", "session_id") or session_id, base_url.rstrip("/"), self._clock(), _expiry(data))
        except MarketDataError as error:
            raise KotakNeoAuthenticationError(error.code, error.message, error.retry, "SESSION_BASE_URL_MISSING") from None

    @staticmethod
    def _authentication_error(stage: str, error: MarketDataError) -> KotakNeoAuthenticationError:
        if error.code is ErrorCode.PROVIDER_UNAVAILABLE:
            category = "PROVIDER_UNAVAILABLE"
        elif stage == "login":
            category = "TOTP_LOGIN_FAILED"
        else:
            category = "MPIN_VALIDATION_FAILED"
        return KotakNeoAuthenticationError(error.code, error.message, error.retry, category)

    def _request(self, method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any], *, stage: str | None = None) -> Any:
        response = self._transport.request(method=method, url=url, headers=headers, json_body=body, timeout_seconds=self._timeout_seconds)
        if not 200 <= response.status_code < 300:
            error = kotak_error_from_response(response)
            if stage is not None:
                raise KotakNeoAuthenticationError(error.code, error.message, error.retry, _authentication_category(stage, response))
            raise error
        if not isinstance(response.payload, Mapping):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo returned a malformed response.")
        return response.payload


def _authentication_category(stage: str, response: KotakNeoHttpResponse) -> str:
    if response.status_code >= 500:
        return "PROVIDER_UNAVAILABLE"
    text = _safe_provider_error_text(response.payload).lower()
    if any(marker in text for marker in ("ip not", "ip allow", "allowlist", "whitelist")):
        return "IP_NOT_ALLOWED"
    if stage == "login" and any(marker in text for marker in ("access token", "authorization", "api token", "token invalid")):
        return "ACCESS_TOKEN_REJECTED"
    if stage == "login" and any(marker in text for marker in ("mobile", "ucc", "client code")):
        return "INVALID_MOBILE_OR_UCC"
    if stage == "login" and "totp" in text:
        return "INVALID_TOTP"
    return "TOTP_LOGIN_FAILED" if stage == "login" else "MPIN_VALIDATION_FAILED"


def _safe_provider_error_text(payload: Any) -> str:
    """Use only error labels internally for category selection; never return them."""
    if not isinstance(payload, Mapping):
        return ""
    nested = payload.get("error")
    nested_values = tuple(
        item.get(key)
        for item in nested
        if isinstance(item, Mapping)
        for key in ("code", "message")
    ) if isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)) else ()
    values = (payload.get("errorCode"), payload.get("code"), payload.get("message"), payload.get("status"), *nested_values)
    return " ".join(str(value) for value in values if isinstance(value, (str, int)))


@dataclass(frozen=True, slots=True)
class KotakNeoInstrumentRecord:
    exchange_segment: str
    instrument_token: str
    symbol: str
    trading_symbol: str | None = None
    instrument_type: str | None = None
    isin: str | None = None
    series: str | None = None
    name: str | None = None


class KotakNeoInstrumentMaster:
    """Immutable, explicitly loaded master; no loose symbol selection."""

    def __init__(self, records: Sequence[KotakNeoInstrumentRecord] = ()) -> None:
        self._identities = tuple(_identity(item) for item in records)

    def resolve(self, query: str) -> InstrumentIdentity:
        normalized = query.strip().upper()
        exact = tuple(item for item in self._identities if normalized in {
            item.instrument_id.upper(), item.symbol.upper(), (item.trading_symbol or "").upper(),
        })
        if not exact:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Kotak Neo instrument was not found.")
        if len(exact) != 1:
            raise MarketDataError(ErrorCode.AMBIGUOUS_INSTRUMENT, "Kotak Neo instrument symbol is ambiguous.")
        return exact[0]

    @property
    def identities(self) -> tuple[InstrumentIdentity, ...]:
        return self._identities


class KotakNeoMarketDataProvider:
    """Current Kotak Neo read-only quote/instrument adapter.

    Current official Neo material documents quote and scrip-master support, but
    not a stable historical candle REST contract. Historical/intraday therefore
    fail closed until Kotak publishes an approved current contract.
    """

    def __init__(
        self,
        credentials: KotakNeoCredentials,
        transport: KotakNeoHttpTransport | None = None,
        *,
        instrument_master: KotakNeoInstrumentMaster | None = None,
        freshness: SessionAwareFreshnessEvaluator | None = None,
        timeout_seconds: float = 10.0,
        clock: Callable[[], datetime] | None = None,
        market_data_base_url: str = KOTAK_NEO_MARKET_DATA_BASE_URL,
        sdk_factory: Callable[..., KotakNeoSdkClient] | None = None,
    ) -> None:
        self._credentials = credentials
        self._transport = transport or HttpxKotakNeoTransport()
        self._master = instrument_master or KotakNeoInstrumentMaster()
        self._freshness = freshness or SessionAwareFreshnessEvaluator(FreshnessThresholds(timedelta(minutes=1), timedelta(minutes=5), timedelta(days=1), timedelta(minutes=5), timedelta(minutes=5)))
        self._timeout_seconds = timeout_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._market_data_base_url = market_data_base_url.rstrip("/")
        self._auth = KotakNeoAuthClient(self._transport, timeout_seconds=timeout_seconds, clock=self._clock)
        self._session: KotakNeoSession | None = None
        # Explicit test transports retain the deterministic REST fixtures. In
        # normal runtime the official SDK is the sole market-data client.
        use_sdk = sdk_factory is not None or transport is None
        self._sdk = (sdk_factory or _official_sdk)(consumer_key=credentials.require_tradeapi_access_token(), environment="prod") if use_sdk else None

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            current_quotes=CapabilityState.SUPPORTED, batch_quotes=CapabilityState.SUPPORTED,
            historical_candles=CapabilityState.UNSUPPORTED, supported_timeframes=frozenset(),
            index_data=CapabilityState.SUPPORTED, vix=CapabilityState.SUPPORTED,
            breadth=CapabilityState.UNSUPPORTED, depth=CapabilityState.SUPPORTED,
            instrument_master=CapabilityState.SUPPORTED, websocket=CapabilityState.UNSUPPORTED,
            corporate_actions=CapabilityState.UNKNOWN, market_status=CapabilityState.UNSUPPORTED,
            rate_limit_metadata={},
        )

    @property
    def session(self) -> KotakNeoSession | None:
        return self._session

    def establish_session(self, *, current_totp: str) -> KotakNeoSession:
        self._session = self._sdk_session(current_totp=current_totp) if self._sdk is not None else self._auth.authenticate(self._credentials, current_totp=current_totp)
        return self._session

    def master_file_paths(self) -> tuple[str, ...]:
        """Use the documented consumer-key-only scrip-master capability.

        Kotak's current SDK explicitly documents that scrip-master discovery is
        available without a completed TOTP/MPIN session.  It is therefore the
        canonical quote-only resolution path; no dynamic session base URL is
        needed here.
        """
        if self._sdk is not None:
            response = self._sdk.scrip_master(exchange_segment="nse_cm")
            if isinstance(response, str):
                return (response,)
            paths = _sdk_paths(response)
        else:
            access_token = self._credentials.require_tradeapi_access_token()
            response = self._request("GET", f"{self._market_data_base_url}{KOTAK_NEO_SCRIP_MASTER_PATHS}", {"Authorization": access_token, "neo-fin-key": "neotradeapi", "Accept": "application/json"}, None)
            paths = response.get("data", response) if isinstance(response, Mapping) else response
        if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo scrip-master response is malformed.")
        return tuple(item for item in paths if isinstance(item, str))

    def load_instrument_master(self) -> KotakNeoInstrumentMaster:
        """Load only the token-authorized NSE cash master needed for one safe test."""
        paths = self.master_file_paths()
        path = next((item for item in paths if "nse_cm" in item.lower()), None)
        if path is None:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Kotak Neo NSE equity instrument master is unavailable.")
        response = self._download_master_file(_master_file_url(path, self._market_data_base_url))
        if not 200 <= response.status_code < 300:
            raise kotak_error_from_response(response)
        records = _master_records(response)
        if not records:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo NSE equity instrument master is malformed.")
        self._master = KotakNeoInstrumentMaster(records)
        return self._master

    def _download_master_file(self, url: str) -> KotakNeoHttpResponse:
        downloader = getattr(self._transport, "download_master_file", None)
        if callable(downloader):
            return downloader(url=url, timeout_seconds=self._timeout_seconds, max_bytes=KOTAK_NEO_MASTER_FILE_MAX_BYTES)
        # Deterministic test transports use the same public-file contract. The
        # returned master URL is not a credential endpoint, so no secret
        # header is sent to it.
        response = self._transport.request(method="GET", url=url, headers={}, json_body=None, timeout_seconds=self._timeout_seconds)
        if response.content is not None and len(response.content) > KOTAK_NEO_MASTER_FILE_MAX_BYTES:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo instrument master exceeds the configured size limit.")
        return response

    def resolve_instrument(self, query: str) -> InstrumentIdentity | None:
        return self._master.resolve(query)

    def get_quote(self, instrument: InstrumentIdentity) -> CanonicalQuote:
        result = self.get_quotes((instrument,))
        if result.quotes:
            return result.quotes[0]
        raise result.failures.get(instrument.instrument_id, MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Kotak Neo quote is unavailable."))

    def get_quotes(self, instruments: tuple[InstrumentIdentity, ...]) -> BatchQuotesResult:
        if not instruments:
            return BatchQuotesResult(())
        access_token = self._credentials.require_tradeapi_access_token()
        requests: list[tuple[InstrumentIdentity, ProviderInstrumentMapping]] = []
        failures: dict[str, MarketDataError] = {}
        for instrument in instruments:
            try:
                requests.append((instrument, _kotak_mapping(instrument)))
            except MarketDataError as error:
                failures[instrument.instrument_id] = error
        if not requests:
            return BatchQuotesResult((), failures, ("no requested instrument has a Kotak Neo mapping",))
        tokens = ",".join(f"{mapping.provider_exchange_segment}|{mapping.provider_instrument_reference}" for _, mapping in requests)
        response = self._sdk.quotes(
            instrument_tokens=[{"exchange_segment": mapping.provider_exchange_segment or "", "instrument_token": mapping.provider_instrument_reference} for _, mapping in requests],
            quote_type="all",
        ) if self._sdk is not None else self._request("GET", f"{self._market_data_base_url}{KOTAK_NEO_QUOTES_PATH.format(tokens=tokens)}", {"Authorization": access_token, "neo-fin-key": "neotradeapi"}, None)
        _raise_sdk_error(response)
        rows = _quote_rows(response)
        by_provider_key = {(str(row.get("exchange", "")).lower(), str(row.get("exchange_token", ""))): row for row in rows}
        quotes: list[CanonicalQuote] = []
        for instrument, mapping in requests:
            row = by_provider_key.get(((mapping.provider_exchange_segment or "").lower(), mapping.provider_instrument_reference))
            if row is None:
                failures[instrument.instrument_id] = MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Kotak Neo quote is unavailable for a requested instrument.")
                continue
            try:
                quotes.append(self._normalize_quote(instrument, mapping, row))
            except MarketDataError as error:
                failures[instrument.instrument_id] = error
        warnings = ("one or more Kotak Neo quote records were unavailable",) if failures else ()
        return BatchQuotesResult(tuple(quotes), failures, warnings)

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        del request
        raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo historical OHLCV is not implemented without a current documented contract.")

    def get_latest_bar(self, instrument: InstrumentIdentity, timeframe: Timeframe) -> CanonicalOHLCVBar | None:
        del instrument, timeframe
        raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo intraday bars are not implemented without a current documented contract.")

    def get_index_observation(self, instrument: InstrumentIdentity) -> IndexMarketObservation | None:
        if instrument.instrument_type not in {InstrumentType.BROAD_INDEX, InstrumentType.SECTOR_INDEX, InstrumentType.VOLATILITY_INDEX}:
            raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Requested instrument is not an index mapping.")
        quote = self.get_quote(instrument)
        return IndexMarketObservation(
            observation_id=f"kotak-neo-index:{instrument.instrument_id}:{quote.provenance.received_at.isoformat()}",
            instrument=instrument, value=quote.last_price, previous_close=quote.previous_close,
            open=quote.open, high=quote.high, low=quote.low, change=quote.change,
            change_percent=quote.change_percent, observed_at=quote.provenance.exchange_timestamp or quote.provenance.provider_timestamp or quote.provenance.received_at,
            provenance=quote.provenance, freshness=quote.freshness, quality=quote.quality, warnings=quote.warnings,
        )

    def get_market_breadth(self, universe_reference: str) -> MarketBreadthObservation | None:
        del universe_reference
        raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo direct market breadth is not implemented.")

    def get_market_status(self, exchange: object) -> MarketSessionObservation | None:
        del exchange
        raise MarketDataError(ErrorCode.UNSUPPORTED_CAPABILITY, "Kotak Neo market status is not implemented.")

    def _normalize_quote(self, instrument: InstrumentIdentity, mapping: ProviderInstrumentMapping, row: Mapping[str, Any]) -> CanonicalQuote:
        received_at = self._clock()
        provider_timestamp, timestamp_warning = _optional_provider_timestamp(row.get("lstup_time"))
        exchange_timestamp = _timestamp(row.get("exchange_timestamp")) or provider_timestamp
        observed_at = exchange_timestamp or provider_timestamp
        quote = MarketDataNormalizer().quote(
            {
                "last_price": row.get("ltp"), "previous_close": _mapping(row.get("ohlc")).get("close"),
                "open": _mapping(row.get("ohlc")).get("open"), "high": _mapping(row.get("ohlc")).get("high"), "low": _mapping(row.get("ohlc")).get("low"),
                "volume": _integer_from_text(row.get("last_volume")), "turnover": row.get("turnover"),
                "change": row.get("change"), "change_percent": row.get("per_change"),
                "bid": _optional_depth_price(row.get("depth"), "buy"), "ask": _optional_depth_price(row.get("depth"), "sell"),
                "bid_quantity": _depth_value(row.get("depth"), "buy", "quantity", integer=True), "ask_quantity": _depth_value(row.get("depth"), "sell", "quantity", integer=True),
                "warnings": (timestamp_warning,) if timestamp_warning else (),
            },
            quote_id=f"kotak-neo-quote:{instrument.instrument_id}:{(observed_at or received_at).isoformat()}", instrument=instrument,
            provenance=MarketDataProvenance(KOTAK_NEO_PROVIDER, mapping.provider_instrument_reference, exchange_timestamp, provider_timestamp, received_at, "kotak-neo-v1", "quotes", "script-details-quotes"),
            freshness=self._freshness.evaluate(observed_at=observed_at, evaluated_at=received_at, kind="quote"), quality=DataQuality.HIGH,
        )
        MarketDataQualityValidator.validate_quote(quote)
        return quote

    def _request(self, method: str, url: str, headers: Mapping[str, str], body: Mapping[str, Any] | None) -> Any:
        response = self._transport.request(method=method, url=url, headers=headers, json_body=body, timeout_seconds=self._timeout_seconds)
        if not 200 <= response.status_code < 300:
            raise kotak_error_from_response(response)
        if not isinstance(response.payload, (Mapping, list)):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo returned a malformed response.")
        return response.payload

    def _sdk_session(self, *, current_totp: str) -> KotakNeoSession:
        _access_token, mobile, ucc, mpin = self._credentials.require_interactive_login()
        if not current_totp.isdigit() or len(current_totp) != 6:
            raise KotakNeoAuthenticationError(ErrorCode.AUTHENTICATION_REQUIRED, "Kotak Neo current authenticator TOTP is invalid.", RetryDisposition.NON_RETRYABLE, "INVALID_TOTP")
        try:
            login = self._sdk.totp_login(mobile_number=mobile, ucc=ucc, totp=current_totp)  # type: ignore[union-attr]
            _raise_sdk_error(login, stage="login")
            login_data = _data(login)
            session_id = _text(login_data, "sid")
            validate = self._sdk.totp_validate(mpin=mpin)  # type: ignore[union-attr]
            _raise_sdk_error(validate, stage="mpin")
            data = _data(validate)
            base_url = _optional_text_any(data, "baseUrl", "base_url")
            if not base_url:
                raise KotakNeoAuthenticationError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo session base URL is missing.", RetryDisposition.NON_RETRYABLE, "SESSION_BASE_URL_MISSING")
            session_token = _text_any(data, "token", "sessionToken", "session_token")
            return KotakNeoSession(session_token, _optional_text_any(data, "sid", "sessionId", "session_id") or session_id, base_url.rstrip("/"), self._clock(), _expiry(data))
        except KotakNeoAuthenticationError:
            raise
        except MarketDataError as error:
            raise KotakNeoAuthenticationError(error.code, error.message, error.retry, "TOTP_LOGIN_FAILED") from None


def _identity(record: KotakNeoInstrumentRecord) -> InstrumentIdentity:
    segment = record.exchange_segment.lower()
    if segment == "nse_cm": exchange, instrument_type, prefix = Exchange.NSE, InstrumentType.NSE_EQUITY, "NSE"
    elif segment == "bse_cm": exchange, instrument_type, prefix = Exchange.BSE, InstrumentType.BSE_EQUITY, "BSE"
    else: exchange, instrument_type, prefix = Exchange.INDEX, InstrumentType.OTHER, "INDEX"
    type_text = (record.instrument_type or "").lower()
    symbol = record.symbol.strip()
    if "index" in type_text or symbol.upper() in {"NIFTY 50", "NIFTY 500", "NIFTY BANK", "INDIA VIX"}:
        exchange, instrument_type, prefix = Exchange.INDEX, InstrumentType.BROAD_INDEX, "INDEX"
    if symbol.upper() == "INDIA VIX": instrument_type = InstrumentType.VOLATILITY_INDEX
    if "sector" in type_text: instrument_type = InstrumentType.SECTOR_INDEX
    trading_symbol = record.trading_symbol or symbol
    return InstrumentIdentity(
        f"{prefix}:{trading_symbol}", exchange, symbol, trading_symbol, record.isin, record.series,
        instrument_type, record.name or symbol, "INR",
        (ProviderInstrumentMapping(KOTAK_NEO_PROVIDER, record.instrument_token, trading_symbol, "kotak-neo-v1", segment),),
    )


def _kotak_mapping(instrument: InstrumentIdentity) -> ProviderInstrumentMapping:
    mappings = tuple(item for item in instrument.provider_mappings if item.provider.upper() == KOTAK_NEO_PROVIDER)
    if len(mappings) != 1 or not mappings[0].provider_exchange_segment:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "Instrument has no unambiguous Kotak Neo mapping.")
    return mappings[0]


def _master_file_url(path: str, base_url: str) -> str:
    """Accept only the authenticated Kotak file location or a relative path."""
    parsed = urlparse(path)
    if parsed.scheme:
        if parsed.scheme != "https" or not parsed.hostname:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo instrument-master location is invalid.")
        return path
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _master_records(response: KotakNeoHttpResponse) -> tuple[KotakNeoInstrumentRecord, ...]:
    rows: Sequence[Mapping[str, Any]]
    if response.content:
        try:
            rows = tuple(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        except (UnicodeDecodeError, csv.Error):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo NSE equity instrument master is malformed.") from None
    elif isinstance(response.payload, list) and all(isinstance(item, Mapping) for item in response.payload):
        rows = tuple(response.payload)
    elif isinstance(response.payload, Mapping) and isinstance(response.payload.get("data"), list):
        values = response.payload["data"]
        rows = tuple(item for item in values if isinstance(item, Mapping))
    else:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo NSE equity instrument master is malformed.")
    records: list[KotakNeoInstrumentRecord] = []
    for row in rows:
        normalized = {"".join(character for character in str(key).lower() if character.isalnum()): value for key, value in row.items()}
        segment = _row_text(normalized, "exchangesegment", "exchangeseg", "pexchseg", "exchange", "pexchange")
        # Neo's documented CSV uses pSymbol as the instrument token; the
        # canonical NSE symbol is pSymbolName / pTrdSymbol.
        token = _row_text(normalized, "instrumenttoken", "token", "ptoken", "psymbol", "exchangetoken", "pexchangetoken")
        symbol = _row_text(normalized, "symbolname", "psymbolname", "tradingsymbol", "ptradingsymbol", "ptrdsymbol")
        if (segment or "").lower() != "nse_cm" or not token or not symbol:
            continue
        records.append(KotakNeoInstrumentRecord(
            segment, token, symbol,
            _row_text(normalized, "tradingsymbol", "ptradingsymbol", "ptrdsymbol") or symbol,
            _row_text(normalized, "instrumenttype", "pinsttype", "pinstrumentname", "instrumentname"),
            _row_text(normalized, "isin", "pisin", "isinnumber"),
            _row_text(normalized, "series", "pseries"),
            _row_text(normalized, "name", "companyname", "pcompanyname"),
        ))
    return tuple(records)


def _row_text(row: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _data(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo returned a malformed response.")
    data = value.get("data", value)
    if not isinstance(data, Mapping):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo returned a malformed response.")
    return data


def _sdk_paths(value: Any) -> tuple[str, ...]:
    _raise_sdk_error(value)
    if not isinstance(value, Mapping):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo scrip-master response is malformed.")
    data = value.get("data", value)
    if isinstance(data, Mapping):
        paths = data.get("filesPaths", data.get("filePaths", ()))
    else:
        paths = data
    if isinstance(paths, str):
        return (paths,)
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo scrip-master response is malformed.")
    return tuple(item for item in paths if isinstance(item, str))


def _raise_sdk_error(value: Any, *, stage: str | None = None) -> None:
    """Turn SDK error dictionaries into redacted canonical failures."""
    if not isinstance(value, Mapping) or not any(key in value for key in ("error", "Error", "Error Message")):
        return
    text = _safe_provider_error_text(value).lower()
    if any(marker in text for marker in ("access token", "authorization", "consumer key", "token invalid")):
        category = "ACCESS_TOKEN_REJECTED"
    elif any(marker in text for marker in ("ip not", "ip allow", "allowlist", "whitelist")):
        category = "IP_NOT_ALLOWED"
    elif stage == "login":
        category = "TOTP_LOGIN_FAILED"
    elif stage == "mpin":
        category = "MPIN_VALIDATION_FAILED"
    else:
        category = "PROVIDER_UNAVAILABLE"
    code = ErrorCode.AUTHENTICATION_REQUIRED if category in {"ACCESS_TOKEN_REJECTED", "IP_NOT_ALLOWED", "TOTP_LOGIN_FAILED", "MPIN_VALIDATION_FAILED"} else ErrorCode.PROVIDER_UNAVAILABLE
    raise KotakNeoAuthenticationError(code, "Kotak Neo SDK returned an unsuccessful response.", RetryDisposition.NON_RETRYABLE, category)


def _quote_rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, list): rows = value
    elif isinstance(value, Mapping): rows = value.get("data", value.get("quotes"))
    else: rows = None
    if not isinstance(rows, list) or not all(isinstance(item, Mapping) for item in rows):
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo quote response is malformed.")
    return tuple(rows)


def _text(value: Mapping[str, Any], key: str) -> str:
    return _text_any(value, key)


def _text_any(value: Mapping[str, Any], *keys: str) -> str:
    result = _optional_text_any(value, *keys)
    if not result:
        raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo session response is incomplete.")
    return result


def _optional_text(value: Mapping[str, Any], key: str) -> str | None:
    return _optional_text_any(value, key)


def _optional_text_any(value: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _expiry(value: Mapping[str, Any]) -> datetime | None:
    return _timestamp(value.get("expiresAt") or value.get("expires_at"))


def _timestamp(value: Any) -> datetime | None:
    if value is None: return None
    if isinstance(value, (int, float)) or isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(int(value), tz=UTC)
    if isinstance(value, str):
        candidate = value.replace("Z", "+00:00")
        try: parsed = datetime.fromisoformat(candidate)
        except ValueError as error: raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo timestamp is malformed.") from error
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo timestamp lacks timezone information.")
        return parsed
    raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo timestamp is malformed.")


def _optional_provider_timestamp(value: Any) -> tuple[datetime | None, str | None]:
    """Keep an unparseable optional provider timestamp from invalidating price data.

    The raw time is not guessed or replaced: canonical provenance records no
    provider timestamp and freshness is assessed from the received time, with
    an explicit warning for downstream consumers.
    """
    if value is None or value == "":
        return None, None
    try:
        return _timestamp(value), None
    except MarketDataError:
        return None, "KOTAK_PROVIDER_TIMESTAMP_UNPARSEABLE"


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _integer_from_text(value: Any) -> int | None:
    if value is None: return None
    if isinstance(value, bool): raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo numeric field is malformed.")
    try: return int(value)
    except (TypeError, ValueError) as error: raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Kotak Neo numeric field is malformed.") from error


def _depth_value(depth: Any, side: str, field: str, *, integer: bool = False) -> Any:
    rows = _mapping(depth).get(side)
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], Mapping): return None
    value = rows[0].get(field)
    return _integer_from_text(value) if integer else value


def _optional_depth_price(depth: Any, side: str) -> Any:
    """Treat zero/negative order-book prices as unavailable optional depth.

    Kotak can return placeholder zero prices when an order-book side is not
    available.  A bid/ask is optional in the canonical quote contract, so the
    placeholder must not be promoted to a real price or poison an otherwise
    valid last-traded quote.
    """
    value = _depth_value(depth, side, "price")
    if value is None:
        return None
    try:
        return None if Decimal(str(value)) <= 0 else value
    except (InvalidOperation, ValueError):
        return value
