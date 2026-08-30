"""Redacted local/private connection-management HTTP contracts."""

from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr


class CredentialDefinitionResponse(BaseModel):
    field: str
    label: str
    sensitivity: str
    secret: bool
    required_for: tuple[str, ...]
    description: str


class ConnectionProfileResponse(BaseModel):
    connection_id: str
    provider: str
    display_name: str
    enabled: bool
    status: str
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None
    last_success_at: datetime | None
    last_error_code: str | None
    capabilities: tuple[str, ...]
    credential_fields_configured: dict[str, bool]
    tradeapi_access_token_configured: bool | None = None
    market_data_configured: bool | None = None
    session_configured: bool | None = None
    credential_store_available: bool
    credential_store_backend: str
    credential_store_message: str | None
    warnings: tuple[str, ...]
    credential_definitions: tuple[CredentialDefinitionResponse, ...] = ()


class ConnectionListResponse(BaseModel):
    items: tuple[ConnectionProfileResponse, ...]


class KotakConnectionUpdateRequest(BaseModel):
    """Inbound secrets are deliberately excluded from every response model."""

    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    enabled: bool | None = None
    tradeapi_access_token: SecretStr | None = None
    mobile_number: SecretStr | None = None
    ucc: SecretStr | None = None
    mpin: SecretStr | None = None

    def credential_values(self) -> dict[str, str]:
        return {
            field: value.get_secret_value()
            for field in ("tradeapi_access_token", "mobile_number", "ucc", "mpin")
            if (value := getattr(self, field)) is not None
        }

class GlobalDatafeedsConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_key: SecretStr | None = None
    def credential_values(self) -> dict[str,str]: return {"access_key":self.access_key.get_secret_value()} if self.access_key is not None else {}

class UpstoxConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_token: SecretStr | None = None
    def credential_values(self) -> dict[str,str]: return {"access_token":self.access_token.get_secret_value()} if self.access_token is not None else {}

class GNewsConnectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr | None = None
    def credential_values(self) -> dict[str,str]: return {"api_key":self.api_key.get_secret_value()} if self.api_key is not None else {}


class ConnectionTestResponse(BaseModel):
    provider: str
    connection_id: str
    status: str
    quote_access: str
    session_read_access: str
    instrument_resolution: str
    tested_at: datetime
    mode: str
    test_symbol: str | None
    canonical_normalization: str
    freshness: str | None
    warnings: tuple[str, ...]
    error_code: str | None
    message: str | None
    market_data_auth: str = "NOT_TESTED"
    session_totp_login: str = "NOT_TESTED"
    session_mpin_validation: str = "NOT_TESTED"
    ip_configuration: str = "NOT_TESTED"
    validation_flow: dict[str, str] | None = None


class UpstoxAnalyticsEndpointResponse(BaseModel):
    endpoint: str
    method: str = "GET"
    safe_url: str = ""
    safe_query_params: dict[str, str] = {}
    http_status: int | None
    content_type: str | None = None
    status: str
    upstox_status: str | None = None
    summary: dict[str, Any]
    top_level_schema: tuple[str, ...] = ()
    data_schema_summary: dict[str, Any] = {}
    record_count: int = 0
    periods: tuple[str, ...] = ()
    units: str | None = None
    statement_type: str | None = None
    time_period: str | None = None
    full_statement_present: bool | None = None
    timestamp_fields_detected: tuple[dict[str, str], ...] = ()
    pit_quality: str = "OBSERVED_AT_FETCH_ONLY"
    error_code: str | None = None
    error_message: str | None = None


class UpstoxAnalyticsFeasibilityResponse(BaseModel):
    """Sanitised output of the local, APOLLOHOSP-only live feasibility probe."""

    isin: str
    symbol: str | None = None
    instrument_key: str
    credential_accepted: bool
    endpoints: tuple[UpstoxAnalyticsEndpointResponse, ...]
    reconciliation: tuple[dict[str, Any], ...]
    pit_timestamp_fields: tuple[str, ...]
    stopped_early: bool = False
    stop_reason: str | None = None


class UpstoxAnalyticsAnchorsResponse(BaseModel):
    """Local-only U04 three-anchor structural evidence."""

    anchors: tuple[UpstoxAnalyticsFeasibilityResponse, ...]


class UpstoxPreparedRequestResponse(BaseModel):
    name: str
    method: str
    url: str
    headers: dict[str, str]
    body: None = None


class UpstoxRequestCallResponse(BaseModel):
    status_code: int | None
    content_type: str | None
    response_headers: dict[str, str]
    body: Any
    error: str | None = None


class UpstoxRequestForensicsResponse(BaseModel):
    """Redacted, local-only comparison of direct and production V3 requests."""

    token_audit: dict[str, bool]
    raw_instrument_key: str
    encoded_instrument_key: str
    production: UpstoxPreparedRequestResponse
    direct: UpstoxPreparedRequestResponse
    differences: tuple[str, ...]
    direct_result: UpstoxRequestCallResponse | None
    production_result: UpstoxRequestCallResponse | None


class KotakSessionTestRequest(BaseModel):
    """A live authenticator code is accepted once and never persisted."""

    model_config = ConfigDict(extra="forbid")
    current_totp: SecretStr = Field(min_length=6, max_length=6)

    def totp_value(self) -> str:
        value = self.current_totp.get_secret_value()
        if not value.isdigit():
            raise ValueError("Current authenticator TOTP must contain six digits.")
        return value


class KotakMarketDataTestRequest(BaseModel):
    """Optional non-secret symbol for the bounded quote-only check."""

    model_config = ConfigDict(extra="forbid")
    test_symbol: str | None = Field(default=None, min_length=1, max_length=32)
