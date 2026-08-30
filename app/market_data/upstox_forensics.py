"""Local-only, redacted Upstox Historical Candle V3 request forensics.

This module exists solely to compare one documented direct request with the
existing production adapter request.  It never persists credentials or market
data, and every public representation replaces the bearer credential with a
fixed marker before it can be returned or written to the support report.
"""
from __future__ import annotations

import json
import platform
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping

from app.market_data.models import (
    Exchange,
    HistoricalBarsRequest,
    InstrumentIdentity,
    InstrumentType,
    ProviderInstrumentMapping,
    Timeframe,
)
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider


APOLLOHOSP_INSTRUMENT_KEY = "NSE_EQ|INE437A01024"
_MASK = "<ANALYTICS_TOKEN_MASKED>"
_SAFE_RESPONSE_HEADERS = frozenset({
    "content-type", "date", "server", "x-request-id", "request-id",
    "x-correlation-id", "correlation-id",
})
_SECRET_MARKERS = ("authorization", "token", "cookie", "secret", "api-key", "api_key")


@dataclass(frozen=True, slots=True)
class TokenAudit:
    present: bool
    leading_whitespace_present: bool
    trailing_whitespace_present: bool
    embedded_newline_present: bool
    surrounding_quotes_present: bool
    already_has_bearer_prefix: bool
    normalized: bool


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    name: str
    method: str
    url: str
    headers: Mapping[str, str]
    body: None = None


@dataclass(frozen=True, slots=True)
class CallResult:
    status_code: int | None
    content_type: str | None
    response_headers: Mapping[str, str]
    body: object
    error: str | None = None


@dataclass(frozen=True, slots=True)
class UpstoxRequestForensics:
    token_audit: TokenAudit
    raw_instrument_key: str
    encoded_instrument_key: str
    production: PreparedRequest
    direct: PreparedRequest
    differences: tuple[str, ...]
    direct_result: CallResult | None = None
    production_result: CallResult | None = None


Sender = Callable[[PreparedRequest], CallResult]


def prepare_forensics(
    access_token: str | None,
    *,
    now: datetime | None = None,
) -> UpstoxRequestForensics:
    """Prepare both requests without sending one or retaining a token."""
    raw = access_token if isinstance(access_token, str) else ""
    token_audit = _token_audit(raw)
    when = (now or datetime.now(UTC)).astimezone(UTC)
    start = when - timedelta(days=10)
    instrument = _apollohosp_instrument()
    historical = HistoricalBarsRequest(
        instrument=instrument,
        timeframe=Timeframe.DAILY,
        start=start,
        end=when,
        provider_preference=UPSTOX_PROVIDER,
    )
    production_parameters = UpstoxHistoricalProvider(raw).request_parameters(historical)
    production = _redacted_prepared(
        "production_upstox_provider",
        "GET",
        production_parameters.url,
        production_parameters.headers,
    )
    direct = _redacted_prepared(
        "direct_documented_request",
        "GET",
        production_parameters.url,
        {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {_MASK}",
        },
    )
    encoded = production_parameters.url.split("/historical-candle/", 1)[1].split("/", 1)[0]
    differences = _differences(direct, production)
    return UpstoxRequestForensics(
        token_audit=token_audit,
        raw_instrument_key=production_parameters.instrument_key,
        encoded_instrument_key=encoded,
        production=production,
        direct=direct,
        differences=differences,
    )


def execute_forensics(
    access_token: str | None,
    *,
    now: datetime | None = None,
    direct_sender: Sender | None = None,
    production_sender: Sender | None = None,
) -> UpstoxRequestForensics:
    """Make exactly one direct and one production-equivalent V3 request."""
    prepared = prepare_forensics(access_token, now=now)
    if not prepared.token_audit.present:
        raise ValueError("Upstox Analytics Token is not configured.")
    raw = access_token if isinstance(access_token, str) else ""
    # Both calls use the identical normalized token.  The display objects above
    # are redacted copies and are never passed to either transport.
    normalized = _normalized_token(raw)
    direct = _with_actual_authorization(prepared.direct, normalized)
    production = _with_actual_authorization(prepared.production, normalized)
    direct_result = (direct_sender or _requests_sender)(direct)
    production_result = (production_sender or _production_requests_sender)(production)
    return UpstoxRequestForensics(
        token_audit=prepared.token_audit,
        raw_instrument_key=prepared.raw_instrument_key,
        encoded_instrument_key=prepared.encoded_instrument_key,
        production=prepared.production,
        direct=prepared.direct,
        differences=prepared.differences,
        direct_result=direct_result,
        production_result=production_result,
    )


def execute_production_probe(
    access_token: str | None,
    *,
    now: datetime | None = None,
    production_sender: Sender | None = None,
) -> UpstoxRequestForensics:
    """Make one production-equivalent APOLLOHOSP V3 request, and no direct call."""
    prepared = prepare_forensics(access_token, now=now)
    if not prepared.token_audit.present:
        raise ValueError("Upstox Analytics Token is not configured.")
    raw = access_token if isinstance(access_token, str) else ""
    production = _with_actual_authorization(prepared.production, _normalized_token(raw))
    result = (production_sender or _production_requests_sender)(production)
    return UpstoxRequestForensics(
        token_audit=prepared.token_audit,
        raw_instrument_key=prepared.raw_instrument_key,
        encoded_instrument_key=prepared.encoded_instrument_key,
        production=prepared.production,
        direct=prepared.direct,
        differences=prepared.differences,
        production_result=result,
    )


def write_support_report(forensics: UpstoxRequestForensics, path: Path, *, access_token: str) -> None:
    """Write a shareable report and reject any accidental credential leakage."""
    report = _support_report(forensics)
    _assert_safe_report(report, access_token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def _apollohosp_instrument() -> InstrumentIdentity:
    return InstrumentIdentity(
        instrument_id="NSE:INE437A01024",
        exchange=Exchange.NSE,
        symbol="APOLLOHOSP",
        trading_symbol="APOLLOHOSP",
        isin="INE437A01024",
        series="EQ",
        instrument_type=InstrumentType.NSE_EQUITY,
        name="Apollo Hospitals Enterprise Ltd.",
        provider_mappings=(
            ProviderInstrumentMapping(
                UPSTOX_PROVIDER,
                APOLLOHOSP_INSTRUMENT_KEY,
                "APOLLOHOSP",
                "upstox-v3",
                "NSE_EQ",
            ),
        ),
    )


def _token_audit(value: str) -> TokenAudit:
    stripped = value.strip()
    return TokenAudit(
        present=bool(stripped),
        leading_whitespace_present=bool(value) and value != value.lstrip(),
        trailing_whitespace_present=bool(value) and value != value.rstrip(),
        embedded_newline_present="\n" in value or "\r" in value,
        surrounding_quotes_present=len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'},
        already_has_bearer_prefix=stripped.lower().startswith("bearer "),
        normalized=stripped != value or stripped.lower().startswith("bearer "),
    )


def _normalized_token(value: str) -> str:
    """Use the exact existing adapter normalisation without exposing output."""
    candidate = value.strip()
    while candidate.lower().startswith("bearer "):
        candidate = candidate[7:].strip()
    if not candidate:
        raise ValueError("Upstox Analytics Token is not configured.")
    return candidate


def _redacted_prepared(name: str, method: str, url: str, headers: Mapping[str, str]) -> PreparedRequest:
    return PreparedRequest(name, method, url, _redact_headers(headers))


def _with_actual_authorization(prepared: PreparedRequest, token: str) -> PreparedRequest:
    headers = dict(prepared.headers)
    headers["Authorization"] = f"Bearer {token}"
    return PreparedRequest(prepared.name, prepared.method, prepared.url, headers, prepared.body)


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        str(key): f"Bearer {_MASK}" if str(key).lower() == "authorization" else _MASK if _is_secret_key(str(key)) else str(value)
        for key, value in headers.items()
    }


def _is_secret_key(key: str) -> bool:
    lower = key.lower()
    return any(marker in lower for marker in _SECRET_MARKERS)


def _differences(direct: PreparedRequest, production: PreparedRequest) -> tuple[str, ...]:
    differences: list[str] = []
    if direct.method != production.method:
        differences.append(f"method: direct={direct.method}, production={production.method}")
    if direct.url != production.url:
        differences.append("url differs")
    for key in sorted(set(direct.headers) | set(production.headers), key=str.lower):
        left = direct.headers.get(key)
        right = production.headers.get(key)
        if left != right:
            differences.append(f"header {key}: direct={left!r}, production={right!r}")
    return tuple(differences) or ("MATCH",)


def _requests_sender(prepared: PreparedRequest) -> CallResult:
    """Minimal requests.get equivalent to Upstox's published Python sample."""
    try:
        import requests

        response = requests.get(
            prepared.url,
            headers=dict(prepared.headers),
            timeout=20.0,
            allow_redirects=True,
        )
        return _result_from_response(
            response.status_code,
            response.headers,
            response.content,
            secrets=_request_secrets(prepared),
        )
    except Exception as error:
        return CallResult(None, None, {}, {}, _safe_exception(error, _request_secrets(prepared)))


def _production_requests_sender(prepared: PreparedRequest) -> CallResult:
    """Production-equivalent requests transport using the adapter's exact headers."""
    return _requests_sender(prepared)


def _result_from_response(status: int, headers: Mapping[str, str], body: bytes, *, secrets: tuple[str, ...]) -> CallResult:
    response_headers = {
        key: value
        for key, value in headers.items()
        if key.lower() in _SAFE_RESPONSE_HEADERS
    }
    content_type = next((value for key, value in response_headers.items() if key.lower() == "content-type"), None)
    return CallResult(status, content_type, response_headers, _safe_body(body, secrets))


def _safe_body(body: bytes, secrets: tuple[str, ...]) -> object:
    text = body.decode("utf-8", errors="replace")[:4000]
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        return _redact_value(text, secrets)
    return _redact_value(decoded, secrets)


def _redact_value(value: object, secrets: tuple[str, ...]) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _MASK if _is_secret_key(str(key)) else _redact_value(item, secrets)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item, secrets) for item in value]
    if isinstance(value, str):
        return _redact_text(value, secrets)
    return value


def _safe_exception(error: Exception, secrets: tuple[str, ...]) -> str:
    # urllib/requests exceptions can echo URLs, never headers.  Keep the
    # exception class and a bounded message but remove any accidental bearer.
    message = _redact_text(str(error), secrets)[:500]
    return f"{error.__class__.__name__}: {message}"


def _request_secrets(prepared: PreparedRequest) -> tuple[str, ...]:
    authorization = prepared.headers.get("Authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    return tuple(item for item in (authorization, token) if item and item != f"Bearer {_MASK}")


def _redact_text(value: str, secrets: tuple[str, ...]) -> str:
    result = value
    for secret in secrets:
        result = result.replace(secret, _MASK)
    return result


def _support_report(forensics: UpstoxRequestForensics) -> str:
    lines = [
        "# Upstox Analytics Token Request Diagnostic",
        "",
        "## Environment",
        "- Windows user context: HANUMAN\\Acer (interactive local backend expected)",
        f"- Python HTTP library/version: requests + urllib.request; Python {platform.python_version()}",
        "- Upstox client implementation: `app/market_data/upstox.py:UpstoxHistoricalProvider`",
        "",
        "## Token loading",
        "- source: WINDOWS_CREDENTIAL_MANAGER via `ProviderConnectionService` → `CredentialStore.load('upstox')['access_token']`.",
        f"- token_present: {str(forensics.token_audit.present).lower()}",
        f"- leading_whitespace_present: {str(forensics.token_audit.leading_whitespace_present).lower()}",
        f"- trailing_whitespace_present: {str(forensics.token_audit.trailing_whitespace_present).lower()}",
        f"- embedded_newline_present: {str(forensics.token_audit.embedded_newline_present).lower()}",
        f"- surrounding_quotes_present: {str(forensics.token_audit.surrounding_quotes_present).lower()}",
        f"- already_has_bearer_prefix: {str(forensics.token_audit.already_has_bearer_prefix).lower()}",
        "",
        "## URL construction",
        f"- raw_instrument_key: `{forensics.raw_instrument_key}`",
        f"- encoded_instrument_key: `{forensics.encoded_instrument_key}`",
        "",
        "## Prepared request — direct documented request",
        *_render_prepared(forensics.direct),
        "",
        "## Prepared request — production Upstox client",
        *_render_prepared(forensics.production),
        "",
        "## Differences discovered",
        *(f"- {item}" for item in forensics.differences),
        "",
        "## A/B result",
        *_render_result("Minimal direct request", forensics.direct_result),
        *_render_result("Production client", forensics.production_result),
    ]
    return "\n".join(lines) + "\n"


def _render_prepared(prepared: PreparedRequest) -> tuple[str, ...]:
    lines = [f"`{prepared.method} {prepared.url}`"]
    lines.extend(f"- {key}: {value}" for key, value in prepared.headers.items())
    lines.append("- body: none")
    return tuple(lines)


def _render_result(name: str, result: CallResult | None) -> tuple[str, ...]:
    if result is None:
        return (f"- {name}: NOT_EXECUTED",)
    return (
        f"- {name}: HTTP {result.status_code if result.status_code is not None else 'NO_RESPONSE'}",
        f"  - content_type: {result.content_type or 'unknown'}",
        f"  - response_headers: {json.dumps(dict(result.response_headers), sort_keys=True)}",
        f"  - safe_body: {json.dumps(result.body, sort_keys=True, default=str)}",
        *( (f"  - error: {result.error}",) if result.error else () ),
    )


def _assert_safe_report(report: str, access_token: str) -> None:
    if _MASK not in report:
        raise ValueError("Diagnostic report did not contain the required authorization mask.")
    if "Authorization: Bearer <ANALYTICS_TOKEN_MASKED>" not in report:
        raise ValueError("Diagnostic report authorization was not redacted.")
    # Scan before writing.  The raw token is intentionally used only as an
    # in-memory comparator and never appears in the report or an exception.
    candidates = {access_token, access_token.strip(), _normalized_token(access_token)}
    if any(candidate and candidate in report for candidate in candidates):
        raise ValueError("Diagnostic report secret-safety scan failed.")


__all__ = (
    "APOLLOHOSP_INSTRUMENT_KEY",
    "CallResult",
    "PreparedRequest",
    "TokenAudit",
    "UpstoxRequestForensics",
    "execute_forensics",
    "execute_production_probe",
    "prepare_forensics",
    "write_support_report",
)
