"""Strict DhanHQ V2 authentication and read-only market-data boundary.

This module deliberately has no generic HTTP escape hatch and no trading,
portfolio, funds, IP-management, or order capability.  Secrets are supplied
only by the existing operating-system credential store and are never logged.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import re
import csv
from io import StringIO
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from secrets import token_urlsafe
from threading import Event, Thread
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

import requests

from app.connections.credentials import CredentialStore, CredentialStoreUnavailableError


DHAN_CONNECTION_ID = "dhan"
DHAN_AUTH_BASE_URL = "https://auth.dhan.co"
DHAN_API_BASE_URL = "https://api.dhan.co"
DHAN_REAUTH_REQUIRED = "DHAN_REAUTH_REQUIRED"
DHAN_PROVIDER = "DHAN"
DHAN_INSTRUMENT_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
_EXPIRING_WITHIN = timedelta(minutes=15)


class DhanCredentialState(StrEnum):
    MISSING = "MISSING"
    VALID = "VALID"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"


class DhanMarketDataEndpoint(StrEnum):
    """The complete provider allowlist for this foundation slice."""

    PROFILE = "/v2/profile"
    LTP = "/v2/marketfeed/ltp"
    OHLC = "/v2/marketfeed/ohlc"
    QUOTE = "/v2/marketfeed/quote"
    INSTRUMENT_MASTER = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
    LIVE_MARKET_FEED_WEBSOCKET = "wss://api-feed.dhan.co"


class DhanAuthError(RuntimeError):
    """A stable, secret-free operational error."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class DhanProviderError(DhanAuthError):
    """Safe provider rejection detail: never request, header, or token data."""

    def __init__(self, operation: str, *, http_status: int, error_type: str | None, error_code: str | None, message: str | None, classification: str) -> None:
        super().__init__(operation)
        fields = [operation, f"http_status={http_status}", f"classification={classification}"]
        if error_code:
            fields.append(f"error_code={error_code}")
        if error_type:
            fields.append(f"error_type={error_type}")
        if message:
            fields.append(f"message={message}")
        self.safe_message = " ".join(fields)

    def __str__(self) -> str:
        return self.safe_message


class _HttpResponse(Protocol):
    status_code: int

    def json(self) -> object: ...


HttpRequester = Callable[..., _HttpResponse]


@dataclass(frozen=True, slots=True)
class DhanAuthStatus:
    configured: bool
    api_key_present: bool
    api_secret_present: bool
    access_token_present: bool
    client_id_present: bool
    token_state: DhanCredentialState
    expiry_time: datetime | None


@dataclass(frozen=True, slots=True)
class DhanConsent:
    consent_app_id: str
    browser_url: str


@dataclass(frozen=True, slots=True)
class DhanAccessTokenGrant:
    dhan_client_id: str
    expiry_time: datetime


@dataclass(frozen=True, slots=True)
class DhanLtpTarget:
    """An exact Dhan instrument mapping supplied by a later instrument task."""

    canonical_instrument_id: str
    exchange_segment: str
    security_id: int


@dataclass(frozen=True, slots=True)
class DhanInstrumentRecord:
    """Raw Dhan detailed-master row plus the fields required for normalization.

    ``instrument_type`` is retained for compatibility with the first Dhan
    slice; it contains the raw ``INSTRUMENT`` value.  The distinct raw
    ``INSTRUMENT_TYPE`` field is retained in ``raw_instrument_type``.
    """
    security_id: int
    exchange: str
    segment: str
    isin: str | None
    trading_symbol: str | None
    instrument_type: str | None
    name: str | None
    raw_instrument_type: str | None = None
    series: str | None = None
    display_name: str | None = None

    @property
    def instrument(self) -> str | None:
        return self.instrument_type


@dataclass(frozen=True, slots=True)
class DhanInstrumentMaster:
    source_url: str
    fingerprint: str
    records: tuple[DhanInstrumentRecord, ...]
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class LiveMarketObservation:
    canonical_instrument_id: str
    provider: str
    provider_instrument_id: str
    ltp: Decimal
    provider_timestamp: datetime | None
    received_at: datetime
    evidence_id: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not self.provider_instrument_id or self.ltp <= 0:
            raise ValueError("DHAN_LIVE_OBSERVATION_INVALID")
        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("DHAN_LIVE_OBSERVATION_TIMESTAMP_NAIVE")


def parse_dhan_instrument_master(payload: str) -> tuple[DhanInstrumentRecord, ...]:
    """Parse Dhan's official detailed CSV; malformed rows never become mappings."""
    records: list[DhanInstrumentRecord] = []
    for row in csv.DictReader(StringIO(payload)):
        security = _column(row, "SEM_SMST_SECURITY_ID", "SECURITY_ID")
        exchange = _column(row, "SEM_EXM_EXCH_ID", "EXCH_ID")
        segment = _column(row, "SEM_SEGMENT", "SEGMENT")
        try:
            security_id = int(security or "")
        except ValueError:
            continue
        if security_id <= 0 or not exchange or not segment:
            continue
        records.append(DhanInstrumentRecord(
            security_id, exchange.upper(), segment.upper(), _column(row, "SEM_ISIN", "ISIN"),
            _column(row, "SEM_TRADING_SYMBOL", "TRADING_SYMBOL"),
            _column(row, "SEM_INSTRUMENT_NAME", "INSTRUMENT"),
            _column(row, "SM_SYMBOL_NAME", "SYMBOL_NAME", "SEM_CUSTOM_SYMBOL"),
            _column(row, "SEM_INSTRUMENT_TYPE", "INSTRUMENT_TYPE"), _column(row, "SEM_SERIES", "SERIES"),
            _column(row, "DISPLAY_NAME", "SEM_DISPLAY_NAME"),
        ))
    return tuple(records)


def load_dhan_instrument_master(*, downloader: Callable[[str], str] | None = None) -> DhanInstrumentMaster:
    if downloader is None:
        try:
            response = requests.get(DHAN_INSTRUMENT_MASTER_URL, timeout=20)
            response.raise_for_status()
            payload = response.text
        except requests.RequestException:
            raise DhanAuthError("DHAN_INSTRUMENT_MASTER_FETCH_FAILED") from None
    else:
        payload = downloader(DHAN_INSTRUMENT_MASTER_URL)
    records = parse_dhan_instrument_master(payload)
    if not records:
        raise DhanAuthError("DHAN_INSTRUMENT_MASTER_INVALID")
    return DhanInstrumentMaster(
        DHAN_INSTRUMENT_MASTER_URL, sha256(payload.encode("utf-8")).hexdigest(), records, datetime.now(UTC),
    )


def resolve_dhan_nse_equity(instrument, records: tuple[DhanInstrumentRecord, ...]) -> DhanLtpTarget:
    """ISIN-first NSE equity mapping; symbol is corroboration, never fallback."""
    isin = getattr(instrument, "isin", None)
    if not isin:
        raise DhanAuthError("DHAN_INSTRUMENT_MAPPING_UNRESOLVED")
    matches = tuple(item for item in records if item.exchange == "NSE" and item.segment in {"EQ", "NSE_EQ"} and item.isin and item.isin.upper() == isin.upper())
    if len(matches) != 1:
        raise DhanAuthError("DHAN_INSTRUMENT_MAPPING_AMBIGUOUS" if len(matches) > 1 else "DHAN_INSTRUMENT_MAPPING_UNRESOLVED")
    record = matches[0]
    expected_symbol = (getattr(instrument, "trading_symbol", None) or getattr(instrument, "symbol", "")).upper()
    if expected_symbol and record.trading_symbol and record.trading_symbol.upper() != expected_symbol:
        raise DhanAuthError("DHAN_INSTRUMENT_MAPPING_SYMBOL_CONFLICT")
    return DhanLtpTarget(getattr(instrument, "instrument_id"), "NSE_EQ", record.security_id)


class DhanCredentialService:
    """Credential lifecycle facade backed only by the existing secure store."""

    def __init__(self, store: CredentialStore, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._store = store
        self._clock = clock

    def status(self) -> DhanAuthStatus:
        values = self._load()
        expiry = _parse_expiry(values.get("access_token_expiry"))
        key = bool(values.get("api_key")); secret = bool(values.get("api_secret"))
        token = bool(values.get("access_token")); client = bool(values.get("dhan_client_id"))
        if not token and not any((key, secret, client)):
            state = DhanCredentialState.MISSING
        elif not token or expiry is None:
            state = DhanCredentialState.REAUTH_REQUIRED
        elif expiry <= self._now():
            state = DhanCredentialState.EXPIRED
        elif expiry - self._now() <= _EXPIRING_WITHIN:
            state = DhanCredentialState.EXPIRING
        else:
            state = DhanCredentialState.VALID
        return DhanAuthStatus(key and secret and client, key, secret, token, client, state, expiry)

    def configure_base_credentials(self, *, dhan_client_id: str, api_key: str, api_secret: str) -> None:
        """Replace only via the secure store and invalidate any prior token."""
        if not all((dhan_client_id, api_key, api_secret)):
            raise DhanAuthError("DHAN_CREDENTIALS_MISSING")
        self._store.clear(DHAN_CONNECTION_ID)
        self._store.save(DHAN_CONNECTION_ID, {
            "dhan_client_id": dhan_client_id,
            "api_key": api_key,
            "api_secret": api_secret,
        })

    def credentials_for_consent(self) -> Mapping[str, str]:
        values = self._load()
        if not all(values.get(item) for item in ("dhan_client_id", "api_key", "api_secret")):
            raise DhanAuthError("DHAN_CREDENTIALS_MISSING")
        return values

    def access_credentials(self) -> Mapping[str, str]:
        values = self.credentials_for_consent()
        status = self.status()
        if status.token_state in {DhanCredentialState.EXPIRED, DhanCredentialState.REAUTH_REQUIRED, DhanCredentialState.MISSING}:
            raise DhanAuthError(DHAN_REAUTH_REQUIRED)
        if not values.get("access_token"):
            raise DhanAuthError(DHAN_REAUTH_REQUIRED)
        return values

    def save_grant(self, *, dhan_client_id: str, access_token: str, expiry_time: datetime) -> DhanAccessTokenGrant:
        configured = self.credentials_for_consent()
        if dhan_client_id != configured["dhan_client_id"] or not access_token:
            raise DhanAuthError("DHAN_CONSENT_RESPONSE_INVALID")
        self._store.save(DHAN_CONNECTION_ID, {
            "access_token": access_token,
            "access_token_expiry": expiry_time.astimezone(UTC).isoformat(),
        })
        return DhanAccessTokenGrant(dhan_client_id, expiry_time)

    def _load(self) -> Mapping[str, str]:
        try:
            return self._store.load(DHAN_CONNECTION_ID)
        except CredentialStoreUnavailableError:
            raise
        except Exception:
            raise DhanAuthError("DHAN_CREDENTIAL_STORE_UNAVAILABLE") from None

    def _now(self) -> datetime:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("DHAN_CLOCK_NAIVE")
        return now.astimezone(UTC)


class DhanAuthClient:
    """Official individual-user consent flow; response errors are redacted."""

    def __init__(self, credentials: DhanCredentialService, *, request: HttpRequester | None = None) -> None:
        self._credentials = credentials
        self._request = request or _requests_request

    def generate_consent(self) -> DhanConsent:
        values = self._credentials.credentials_for_consent()
        response = self._request(
            method="POST",
            url=f"{DHAN_AUTH_BASE_URL}/app/generate-consent?{urlencode({'client_id': values['dhan_client_id']})}",
            headers={"app_id": values["api_key"], "app_secret": values["api_secret"]},
            timeout=15,
        )
        payload = _success_json(response, "DHAN_GENERATE_CONSENT_FAILED", redactions=tuple(values.values()))
        consent_id = payload.get("consentAppId")
        if not isinstance(consent_id, str) or not consent_id:
            raise DhanAuthError("DHAN_GENERATE_CONSENT_INVALID_RESPONSE")
        return DhanConsent(consent_id, dhan_consent_browser_url(consent_id))

    def consume_consent(self, token_id: str) -> DhanAccessTokenGrant:
        if not token_id:
            raise DhanAuthError("DHAN_TOKEN_ID_MISSING")
        values = self._credentials.credentials_for_consent()
        response = self._request(
            method="GET",
            url=f"{DHAN_AUTH_BASE_URL}/app/consumeApp-consent?{urlencode({'tokenId': token_id})}",
            headers={"app_id": values["api_key"], "app_secret": values["api_secret"]},
            timeout=15,
        )
        payload = _success_json(response, "DHAN_CONSUME_CONSENT_FAILED", redactions=(*values.values(), token_id))
        client_id, access_token, expiry = payload.get("dhanClientId"), payload.get("accessToken"), payload.get("expiryTime")
        if not isinstance(client_id, str) or not isinstance(access_token, str):
            raise DhanAuthError("DHAN_CONSENT_RESPONSE_INVALID")
        return self._credentials.save_grant(
            dhan_client_id=client_id, access_token=access_token, expiry_time=_parse_required_expiry(expiry),
        )

    def profile_canary(self) -> Mapping[str, object]:
        """Dhan's documented read-only authentication canary, never a trading call."""
        values = self._credentials.access_credentials()
        response = self._request(
            method="GET", url=f"{DHAN_API_BASE_URL}{DhanMarketDataEndpoint.PROFILE.value}",
            headers={"access-token": values["access_token"]}, timeout=15,
        )
        return _success_json(response, "DHAN_PROFILE_CANARY_FAILED", redactions=tuple(values.values()))


class DhanMarketDataClient:
    """Typed read-only market-data client with no arbitrary endpoint method."""

    def __init__(self, credentials: DhanCredentialService, *, request: HttpRequester | None = None) -> None:
        self._credentials = credentials
        self._request = request or _requests_request

    def ltp(self, target: DhanLtpTarget) -> Mapping[str, object]:
        if not target.canonical_instrument_id or target.security_id <= 0:
            raise ValueError("DHAN_EXACT_INSTRUMENT_MAPPING_REQUIRED")
        return self._quote(DhanMarketDataEndpoint.LTP, {target.exchange_segment: [target.security_id]})

    def ltp_batch(self, targets: tuple[DhanLtpTarget, ...]) -> tuple[LiveMarketObservation, ...]:
        if not targets or len({item.canonical_instrument_id for item in targets}) != len(targets) or any(item.exchange_segment != "NSE_EQ" for item in targets):
            raise ValueError("DHAN_EXACT_INSTRUMENT_MAPPING_REQUIRED")
        payload = self._quote(DhanMarketDataEndpoint.LTP, {"NSE_EQ": [item.security_id for item in targets]})
        rows = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
        quotes = rows.get("NSE_EQ") if isinstance(rows, Mapping) and isinstance(rows.get("NSE_EQ"), Mapping) else {}
        received = datetime.now(UTC)
        result: list[LiveMarketObservation] = []
        for target in targets:
            row = quotes.get(str(target.security_id)) if isinstance(quotes, Mapping) else None
            value = row.get("last_price") if isinstance(row, Mapping) else None
            try:
                price = Decimal(str(value))
            except (InvalidOperation, ValueError):
                raise DhanAuthError("DHAN_LTP_RESPONSE_INVALID") from None
            if price <= 0:
                raise DhanAuthError("DHAN_LTP_RESPONSE_INVALID")
            evidence = sha256(f"{target.canonical_instrument_id}|{target.security_id}|{price}|{received.isoformat()}".encode()).hexdigest()
            result.append(LiveMarketObservation(target.canonical_instrument_id, DHAN_PROVIDER, str(target.security_id), price, None, received, f"dhan-ltp:{evidence[:24]}"))
        return tuple(result)

    def ohlc(self, *, exchange_segment: str, security_ids: tuple[int, ...]) -> Mapping[str, object]:
        return self._quote(DhanMarketDataEndpoint.OHLC, _quote_body(exchange_segment, security_ids))

    def quote(self, *, exchange_segment: str, security_ids: tuple[int, ...]) -> Mapping[str, object]:
        return self._quote(DhanMarketDataEndpoint.QUOTE, _quote_body(exchange_segment, security_ids))

    def _quote(self, endpoint: DhanMarketDataEndpoint, body: Mapping[str, object]) -> Mapping[str, object]:
        values = self._credentials.access_credentials()
        response = self._request(
            method="POST", url=f"{DHAN_API_BASE_URL}{endpoint.value}",
            headers={"Accept": "application/json", "Content-Type": "application/json", "access-token": values["access_token"], "client-id": values["dhan_client_id"]},
            json=body, timeout=15,
        )
        return _success_json(response, "DHAN_MARKET_DATA_REQUEST_FAILED", redactions=tuple(values.values()))


class DhanLoopbackTokenReceiver:
    """Bounded local-only receiver for a registered Dhan redirect URL.

    Dhan's documented individual consent redirect carries only ``tokenId``.
    It does not document an OAuth state echo, so state verification is enabled
    only when a redirect integration explicitly supplies one.
    """

    def __init__(self, *, port: int, callback_path: str = "/dhan/callback", expected_state: str | None = None) -> None:
        self.callback_path = callback_path
        self.expected_state = expected_state
        self._token_id: str | None = None
        self._received = Event()
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query, keep_blank_values=True)
                valid = parsed.path == receiver.callback_path and len(query.get("tokenId", ())) == 1 and bool(query["tokenId"][0])
                if receiver.expected_state is not None:
                    valid = valid and query.get("state") == [receiver.expected_state]
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Dhan authorization received. You may close this window." if valid else b"Invalid Dhan authorization callback.")
                if valid:
                    receiver._token_id = query["tokenId"][0]
                    receiver._received.set()

            def log_message(self, _format: str, *_args: object) -> None:
                return  # Query strings can contain tokenId: never log them.

        self._server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self._thread: Thread | None = None

    @property
    def redirect_url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}{self.callback_path}"

    def receive(self, *, timeout_seconds: float) -> str | None:
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        try:
            return self._token_id if self._received.wait(timeout_seconds) else None
        finally:
            self._server.shutdown(); self._server.server_close()
            if self._thread is not None:
                self._thread.join(timeout=1)


def dhan_consent_browser_url(consent_app_id: str) -> str:
    if not consent_app_id:
        raise ValueError("DHAN_CONSENT_APP_ID_MISSING")
    return f"{DHAN_AUTH_BASE_URL}/login/consentApp-login?{urlencode({'consentAppId': consent_app_id})}"


def new_loopback_state() -> str:
    return token_urlsafe(32)


def _quote_body(exchange_segment: str, security_ids: tuple[int, ...]) -> Mapping[str, object]:
    if not exchange_segment or not security_ids or any(item <= 0 for item in security_ids):
        raise ValueError("DHAN_EXACT_INSTRUMENT_MAPPING_REQUIRED")
    return {exchange_segment: list(security_ids)}


def _parse_expiry(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return parsed.astimezone(UTC)


def _parse_required_expiry(value: object) -> datetime:
    parsed = _parse_expiry(value)
    if parsed is None:
        raise DhanAuthError("DHAN_EXPIRY_TIME_INVALID")
    return parsed


def _success_json(response: _HttpResponse, error_code: str, *, redactions: tuple[str, ...] = ()) -> Mapping[str, object]:
    if not 200 <= response.status_code < 300:
        raise _provider_error(response, error_code, redactions=redactions)
    try:
        payload = response.json()
    except Exception:
        raise DhanAuthError(error_code) from None
    if not isinstance(payload, dict):
        raise DhanAuthError(error_code)
    return payload


def _provider_error(response: _HttpResponse, operation: str, *, redactions: tuple[str, ...]) -> DhanProviderError:
    try:
        payload = response.json()
    except Exception:
        payload = {}
    values = payload if isinstance(payload, dict) else {}
    error_type = _safe_provider_field(values.get("errorType"), redactions)
    error_code = _safe_provider_field(values.get("errorCode"), redactions)
    message = _safe_provider_field(values.get("errorMessage"), redactions)
    return DhanProviderError(
        operation,
        http_status=response.status_code,
        error_type=error_type,
        error_code=error_code,
        message=message,
        classification=_classify_provider_error(response.status_code, error_type, error_code, message),
    )


def _safe_provider_field(value: object, redactions: tuple[str, ...]) -> str | None:
    if not isinstance(value, str):
        return None
    sanitized = " ".join(value.split())[:240]
    for secret in redactions:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    sanitized = re.sub(r"(?i)\b(client_id|app_id|app_secret|access[-_ ]?token|token_?id)\s*=\s*[^&\s]+", r"\1=[REDACTED]", sanitized)
    sanitized = re.sub(r"(?i)\b(authorization)\s*[:=]\s*bearer\s+[^\s]+", r"\1=[REDACTED]", sanitized)
    sanitized = re.sub(r"(?i)\bbearer\s+[^\s]+", "Bearer [REDACTED]", sanitized)
    sanitized = re.sub(r"(?i)\b(authorization)\s*[:=]\s*[^\s]+", r"\1=[REDACTED]", sanitized)
    return sanitized or None


def _classify_provider_error(http_status: int, error_type: str | None, error_code: str | None, message: str | None) -> str:
    if http_status == 429:
        return "RATE_LIMIT"
    if http_status >= 500:
        return "PROVIDER_INTERNAL_ERROR"
    detail = " ".join(item.casefold() for item in (error_type, error_code, message) if item)
    if "client" in detail and ("invalid" in detail or "not found" in detail):
        return "INVALID_CLIENT_ID"
    if any(item in detail for item in ("api key", "app_id", "app secret", "app_secret")) and any(item in detail for item in ("invalid", "unauthorized", "authentication")):
        return "INVALID_API_KEY_OR_SECRET"
    if any(item in detail for item in ("inactive", "revoked", "deactivated")) and "app" in detail:
        return "APP_INACTIVE_OR_REVOKED"
    if any(item in detail for item in ("access denied", "forbidden", "permission denied")):
        return "PROVIDER_ACCESS_DENIED"
    return "UNKNOWN_PROVIDER_ERROR"


def _requests_request(**kwargs: Any) -> _HttpResponse:
    return requests.request(**kwargs)


def _column(row: Mapping[str, str | None], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


__all__ = (
    "DHAN_CONNECTION_ID", "DHAN_REAUTH_REQUIRED", "DHAN_PROVIDER", "DHAN_INSTRUMENT_MASTER_URL", "DhanAccessTokenGrant", "DhanAuthClient", "DhanAuthError", "DhanProviderError",
    "DhanAuthStatus", "DhanConsent", "DhanCredentialService", "DhanCredentialState", "DhanLoopbackTokenReceiver",
    "DhanLtpTarget", "DhanInstrumentRecord", "DhanInstrumentMaster", "DhanMarketDataClient", "DhanMarketDataEndpoint", "LiveMarketObservation", "dhan_consent_browser_url", "load_dhan_instrument_master", "new_loopback_state", "parse_dhan_instrument_master", "resolve_dhan_nse_equity",
)
