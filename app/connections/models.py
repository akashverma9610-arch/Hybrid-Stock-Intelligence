"""Secret-free connection domain records and field metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class ConnectionStatus(StrEnum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    CONFIGURED = "CONFIGURED"
    TESTING = "TESTING"
    CONNECTED = "CONNECTED"
    AUTH_FAILED = "AUTH_FAILED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


class ConnectionMode(StrEnum):
    QUOTE_ONLY = "QUOTE_ONLY"
    HISTORICAL_OHLCV = "HISTORICAL_OHLCV"
    SESSION_READ = "SESSION_READ"


class CredentialSensitivity(StrEnum):
    SECRET = "SECRET"
    SENSITIVE_IDENTIFIER = "SENSITIVE_IDENTIFIER"
    NON_SECRET = "NON_SECRET"


class AccessState(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    NOT_TESTED = "NOT_TESTED"


@dataclass(frozen=True, slots=True)
class CredentialDefinition:
    field: str
    label: str
    sensitivity: CredentialSensitivity
    required_for: tuple[ConnectionMode, ...]
    description: str

    @property
    def secret(self) -> bool:
        return self.sensitivity is CredentialSensitivity.SECRET


@dataclass(frozen=True, slots=True)
class ConnectionProfile:
    """Persistable profile metadata only; credential values live outside this model."""

    connection_id: str
    provider: str
    display_name: str
    enabled: bool
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error_code: str | None = None
    capabilities: tuple[ConnectionMode, ...] = ()
    credential_fields_configured: Mapping[str, bool] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConnectionAuditEvent:
    event_id: str
    connection_id: str
    provider: str
    event_type: str
    occurred_at: datetime
    success: bool | None = None
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    provider: str
    connection_id: str
    status: ConnectionStatus
    quote_access: AccessState
    session_read_access: AccessState
    instrument_resolution: str
    tested_at: datetime
    mode: ConnectionMode = ConnectionMode.QUOTE_ONLY
    test_symbol: str | None = None
    canonical_normalization: str = "NOT_TESTED"
    freshness: str | None = None
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    message: str | None = None
    market_data_auth: str = "NOT_TESTED"
    session_totp_login: str = "NOT_TESTED"
    session_mpin_validation: str = "NOT_TESTED"
    ip_configuration: str = "NOT_TESTED"
    validation_flow: Mapping[str, str | None] | None = None


KOTAK_NEO_CREDENTIAL_DEFINITIONS: tuple[CredentialDefinition, ...] = (
    CredentialDefinition("tradeapi_access_token", "TradeAPI Access Token", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY, ConnectionMode.SESSION_READ), "Token issued in the Neo App Trade API area; sent only as the documented Authorization header."),
    CredentialDefinition("mobile_number", "Mobile Number", CredentialSensitivity.SENSITIVE_IDENTIFIER, (ConnectionMode.SESSION_READ,), "Required only for a Kotak Neo read session."),
    CredentialDefinition("ucc", "UCC / Client ID", CredentialSensitivity.SENSITIVE_IDENTIFIER, (ConnectionMode.SESSION_READ,), "Required only for a Kotak Neo read session."),
    CredentialDefinition("mpin", "MPIN", CredentialSensitivity.SECRET, (ConnectionMode.SESSION_READ,), "Required only for a Kotak Neo read session."),
)
GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS: tuple[CredentialDefinition, ...] = (CredentialDefinition("access_key", "Access Key", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY,), "Required for Global Datafeeds historical REST requests."),)
UPSTOX_CREDENTIAL_DEFINITIONS: tuple[CredentialDefinition, ...] = (CredentialDefinition("access_token", "Analytics Access Token", CredentialSensitivity.SECRET, (ConnectionMode.HISTORICAL_OHLCV,), "Required for authenticated Upstox Historical Candle V3 requests."),)
GNEWS_CREDENTIAL_DEFINITIONS: tuple[CredentialDefinition, ...] = (CredentialDefinition("api_key", "API Key", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY,), "Required for GNews machine-readable Search API requests."),)
DHAN_CREDENTIAL_DEFINITIONS: tuple[CredentialDefinition, ...] = (
    CredentialDefinition("dhan_client_id", "Dhan Client ID", CredentialSensitivity.SENSITIVE_IDENTIFIER, (ConnectionMode.QUOTE_ONLY,), "Dhan-issued client identifier used only with the documented market-data authentication headers."),
    CredentialDefinition("api_key", "Dhan API Key", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY,), "Twelve-month Dhan API-key credential used only to start the documented consent flow."),
    CredentialDefinition("api_secret", "Dhan API Secret", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY,), "Twelve-month Dhan API-secret credential used only to start or consume the documented consent flow."),
    CredentialDefinition("access_token", "Dhan Access Token", CredentialSensitivity.SECRET, (ConnectionMode.QUOTE_ONLY,), "Expiring Dhan access token used only with explicit read-only Dhan endpoints."),
    CredentialDefinition("access_token_expiry", "Dhan Access Token Expiry", CredentialSensitivity.NON_SECRET, (ConnectionMode.QUOTE_ONLY,), "ISO-8601 expiry returned by Dhan; retained outside normal application tables so known-expired tokens fail closed."),
)


def requirements_for(mode: ConnectionMode) -> tuple[str, ...]:
    return tuple(item.field for item in KOTAK_NEO_CREDENTIAL_DEFINITIONS if mode in item.required_for)
