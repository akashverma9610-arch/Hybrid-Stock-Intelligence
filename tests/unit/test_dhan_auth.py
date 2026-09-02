from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Thread
from urllib.request import urlopen

import pytest

from app.connections.credentials import InMemoryCredentialStore
from app.market_data.dhan import (
    DHAN_CONNECTION_ID,
    DHAN_REAUTH_REQUIRED,
    DhanAuthClient,
    DhanAuthError,
    DhanConsent,
    DhanCredentialService,
    DhanCredentialState,
    DhanLoopbackTokenReceiver,
    DhanLtpTarget,
    DhanMarketDataClient,
    DhanMarketDataEndpoint,
    DhanInstrumentRecord,
    LiveMarketObservation,
    dhan_consent_browser_url,
    parse_dhan_instrument_master,
    resolve_dhan_nse_equity,
)
from app.runtime.cli import main


NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
SYNTHETIC = {"dhan_client_id": "1000000001", "api_key": "synthetic-dhan-api-key", "api_secret": "synthetic-dhan-api-secret"}


class Response:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self.payload


def service(values: dict[str, str] | None = None) -> tuple[InMemoryCredentialStore, DhanCredentialService]:
    store = InMemoryCredentialStore(values={DHAN_CONNECTION_ID: dict(values or SYNTHETIC)})
    return store, DhanCredentialService(store, clock=lambda: NOW)


def test_status_detects_key_and_secret_presence_without_rendering_values() -> None:
    _, value = service()
    status = value.status()
    assert status.api_key_present and status.api_secret_present and status.client_id_present
    assert not status.access_token_present and status.token_state is DhanCredentialState.REAUTH_REQUIRED
    assert "synthetic-dhan-api-key" not in repr(status)


def test_base_credential_reconfiguration_uses_secure_store_and_invalidates_stale_token() -> None:
    store, credentials = service({**SYNTHETIC, "access_token": "stale-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat()})
    credentials.configure_base_credentials(**SYNTHETIC)
    assert store.load(DHAN_CONNECTION_ID) == SYNTHETIC
    assert credentials.status().token_state is DhanCredentialState.REAUTH_REQUIRED


def test_generate_consent_uses_exact_official_request_shape() -> None:
    _, credentials = service(); calls = []
    client = DhanAuthClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({"consentAppId": "consent-1"}))
    consent = client.generate_consent()
    assert consent.browser_url == "https://auth.dhan.co/login/consentApp-login?consentAppId=consent-1"
    assert calls == [{"method": "POST", "url": "https://auth.dhan.co/app/generate-consent?client_id=1000000001", "headers": {"app_id": "synthetic-dhan-api-key", "app_secret": "synthetic-dhan-api-secret"}, "timeout": 15}]


def test_browser_url_is_encoded_and_contains_only_consent_id() -> None:
    assert dhan_consent_browser_url("consent id") == "https://auth.dhan.co/login/consentApp-login?consentAppId=consent+id"


def test_consume_consent_parses_expiry_and_persists_only_to_secure_store() -> None:
    store, credentials = service(); calls = []
    client = DhanAuthClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({"dhanClientId": "1000000001", "accessToken": "synthetic-access-token", "expiryTime": "2026-09-01T18:00:00"}))
    grant = client.consume_consent("synthetic-token-id")
    assert grant.expiry_time == datetime(2026, 9, 1, 12, 30, tzinfo=UTC)
    assert calls[0]["url"] == "https://auth.dhan.co/app/consumeApp-consent?tokenId=synthetic-token-id"
    assert store.load(DHAN_CONNECTION_ID)["access_token"] == "synthetic-access-token"
    assert credentials.status().token_state is DhanCredentialState.VALID


@pytest.mark.parametrize(("expiry, expected"), [
    ("2026-09-01T18:00:00+05:30", DhanCredentialState.VALID),
    ("2026-09-01T12:10:00+00:00", DhanCredentialState.EXPIRING),
    ("2026-09-01T11:59:00+00:00", DhanCredentialState.EXPIRED),
    (None, DhanCredentialState.REAUTH_REQUIRED),
])
def test_access_token_lifecycle_uses_returned_expiry_time(expiry: str | None, expected: DhanCredentialState) -> None:
    values = {**SYNTHETIC, "access_token": "synthetic-access-token"}
    if expiry is not None:
        values["access_token_expiry"] = expiry
    _, credentials = service(values)
    assert credentials.status().token_state is expected


def test_expired_token_fails_closed_before_any_market_request() -> None:
    _, credentials = service({**SYNTHETIC, "access_token": "synthetic-access-token", "access_token_expiry": "2026-09-01T11:59:00+00:00"})
    calls = []
    client = DhanMarketDataClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({}))
    with pytest.raises(DhanAuthError, match=DHAN_REAUTH_REQUIRED):
        client.ltp(DhanLtpTarget("NSE:INE090A01021", "NSE_EQ", 4963))
    assert calls == []


def test_reauth_required_when_token_is_absent() -> None:
    _, credentials = service()
    with pytest.raises(DhanAuthError, match=DHAN_REAUTH_REQUIRED):
        credentials.access_credentials()


def test_market_data_client_has_only_typed_read_only_quote_calls() -> None:
    _, credentials = service({**SYNTHETIC, "access_token": "synthetic-access-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat()})
    calls = []
    client = DhanMarketDataClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({"status": "success", "data": {}}))
    assert client.ltp(DhanLtpTarget("NSE:INE090A01021", "NSE_EQ", 4963))["status"] == "success"
    assert calls[0]["url"] == "https://api.dhan.co/v2/marketfeed/ltp"
    assert calls[0]["json"] == {"NSE_EQ": [4963]}
    assert "/v2/orders" not in {item.value for item in DhanMarketDataEndpoint}


def test_exact_mapping_is_required_for_ltp() -> None:
    _, credentials = service({**SYNTHETIC, "access_token": "synthetic-access-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat()})
    with pytest.raises(ValueError, match="DHAN_EXACT_INSTRUMENT_MAPPING_REQUIRED"):
        DhanMarketDataClient(credentials).ltp(DhanLtpTarget("", "NSE_EQ", 0))


def test_profile_canary_is_read_only_and_never_renders_token() -> None:
    _, credentials = service({**SYNTHETIC, "access_token": "synthetic-access-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat()})
    calls = []
    result = DhanAuthClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({"dhanClientId": "1000000001", "dataPlan": "Active"})).profile_canary()
    assert result["dataPlan"] == "Active" and calls[0]["url"] == "https://api.dhan.co/v2/profile"
    assert "synthetic-access-token" not in repr(result)


def test_error_messages_and_status_cli_redact_all_synthetic_secrets() -> None:
    _, credentials = service()
    with pytest.raises(DhanAuthError) as caught:
        DhanAuthClient(credentials, request=lambda **_kwargs: Response({}, 401)).generate_consent()
    assert str(caught.value).startswith("DHAN_GENERATE_CONSENT_FAILED http_status=401 classification=UNKNOWN_PROVIDER_ERROR")
    output: list[str] = []
    assert main(["dhan-auth-status"], credential_store_factory=lambda: InMemoryCredentialStore(values={DHAN_CONNECTION_ID: dict(SYNTHETIC)}), output=output.append) == 0
    assert not any(secret in "\n".join(output) for secret in SYNTHETIC.values())


@pytest.mark.parametrize(("status, payload, classification"), [
    (400, {"errorType": "VALIDATION", "errorCode": "INVALID_CLIENT_ID", "errorMessage": "Invalid client id"}, "INVALID_CLIENT_ID"),
    (401, {"errorType": "AUTH", "errorCode": "INVALID_API_KEY", "errorMessage": "Invalid API key"}, "INVALID_API_KEY_OR_SECRET"),
    (403, {"errorType": "ACCESS", "errorCode": "ACCESS_DENIED", "errorMessage": "Access denied"}, "PROVIDER_ACCESS_DENIED"),
])
def test_generate_consent_exposes_only_safe_dhan_error_fields(status: int, payload: dict[str, str], classification: str) -> None:
    _, credentials = service()
    with pytest.raises(DhanAuthError) as caught:
        DhanAuthClient(credentials, request=lambda **_kwargs: Response(payload, status)).generate_consent()
    rendered = str(caught.value)
    assert f"http_status={status}" in rendered and f"classification={classification}" in rendered
    assert "error_code=" in rendered and "error_type=" in rendered and "message=" in rendered
    assert not any(secret in rendered for secret in SYNTHETIC.values())
    assert "headers=" not in rendered and "https://auth.dhan.co" not in rendered


def test_provider_message_redacts_credentials_tokens_and_query_values() -> None:
    _, credentials = service()
    message = "bad client_id=1000000001 app_id=synthetic-dhan-api-key app_secret=synthetic-dhan-api-secret tokenId=synthetic-token-id Authorization: Bearer synthetic-access-token"
    with pytest.raises(DhanAuthError) as caught:
        DhanAuthClient(credentials, request=lambda **_kwargs: Response({"errorMessage": message}, 401)).generate_consent()
    rendered = str(caught.value)
    assert "[REDACTED]" in rendered
    assert not any(value in rendered for value in (*SYNTHETIC.values(), "synthetic-token-id", "synthetic-access-token"))


def test_malformed_provider_error_is_safe_and_classified_without_guessing() -> None:
    _, credentials = service()
    with pytest.raises(DhanAuthError) as caught:
        DhanAuthClient(credentials, request=lambda **_kwargs: Response("<html>failure</html>", 502)).generate_consent()
    assert str(caught.value) == "DHAN_GENERATE_CONSENT_FAILED http_status=502 classification=PROVIDER_INTERNAL_ERROR"


def test_generate_consent_diagnostic_success_never_prints_consent_id(monkeypatch) -> None:
    import app.market_data.dhan as dhan

    class SuccessfulAuth:
        def __init__(self, _credentials) -> None: pass
        def generate_consent(self) -> DhanConsent:
            return DhanConsent("synthetic-consent-id", "https://example.invalid")

    monkeypatch.setattr(dhan, "DhanAuthClient", SuccessfulAuth)
    output: list[str] = []
    assert main(["dhan-auth-diagnose"], credential_store_factory=lambda: InMemoryCredentialStore(values={DHAN_CONNECTION_ID: dict(SYNTHETIC)}), output=output.append) == 0
    assert output == ["DHAN_GENERATE_CONSENT_OK"]


def test_successful_generate_consent_and_existing_auth_flow_remain_unchanged() -> None:
    _, credentials = service()
    consent = DhanAuthClient(credentials, request=lambda **_kwargs: Response({"consentAppId": "synthetic-consent-id"})).generate_consent()
    assert consent.consent_app_id == "synthetic-consent-id"


def test_official_dhan_master_parse_and_isin_first_mapping_fail_closed() -> None:
    records = parse_dhan_instrument_master("SEM_SMST_SECURITY_ID,SEM_EXM_EXCH_ID,SEM_SEGMENT,SEM_ISIN,SEM_TRADING_SYMBOL,SEM_INSTRUMENT_NAME\n4963,NSE,EQ,INE090A01021,ICICIBANK,EQUITY\n")
    identity = type("Identity", (), {"instrument_id": "NSE:INE090A01021", "isin": "INE090A01021", "symbol": "ICICIBANK", "trading_symbol": "ICICIBANK"})()
    assert resolve_dhan_nse_equity(identity, records).security_id == 4963
    bad = type("Identity", (), {"instrument_id": "NSE:INE090A01021", "isin": "INE090A01021", "symbol": "OTHER", "trading_symbol": "OTHER"})()
    with pytest.raises(DhanAuthError, match="SYMBOL_CONFLICT"):
        resolve_dhan_nse_equity(bad, records)


def test_dhan_ltp_batch_validates_all_returned_security_ids_and_stays_live_only() -> None:
    _, credentials = service({**SYNTHETIC, "access_token": "synthetic-access-token", "access_token_expiry": (NOW + timedelta(hours=1)).isoformat()})
    calls = []
    client = DhanMarketDataClient(credentials, request=lambda **kwargs: calls.append(kwargs) or Response({"data": {"NSE_EQ": {"4963": {"last_price": 1234.5}, "999": {"last_price": 10}}}}))
    observations = client.ltp_batch((DhanLtpTarget("NSE:INE090A01021", "NSE_EQ", 4963),))
    assert calls[0]["json"] == {"NSE_EQ": [4963]}
    assert isinstance(observations[0], LiveMarketObservation) and observations[0].ltp == Decimal("1234.5")
    assert observations[0].provider_timestamp is None and observations[0].received_at.tzinfo is not None


def test_loopback_receiver_binds_only_loopback_and_accepts_only_token_id() -> None:
    receiver = DhanLoopbackTokenReceiver(port=0)
    assert receiver._server.server_address[0] == "127.0.0.1"
    result: list[str | None] = []
    thread = Thread(target=lambda: result.append(receiver.receive(timeout_seconds=2)), daemon=True)
    thread.start()
    with urlopen(f"{receiver.redirect_url}?tokenId=synthetic-token-id", timeout=1) as response:
        assert response.status == 200
    thread.join(timeout=3)
    assert result == ["synthetic-token-id"]


def test_loopback_rejects_invalid_state_without_logging_token_id() -> None:
    receiver = DhanLoopbackTokenReceiver(port=0, expected_state="expected")
    result: list[str | None] = []
    thread = Thread(target=lambda: result.append(receiver.receive(timeout_seconds=0.2)), daemon=True)
    thread.start()
    with pytest.raises(Exception):
        urlopen(f"{receiver.redirect_url}?tokenId=synthetic-token-id", timeout=1)
    thread.join(timeout=2)
    assert result == [None]


def test_invalid_expiry_or_client_mismatch_never_persists_access_token() -> None:
    store, credentials = service()
    client = DhanAuthClient(credentials, request=lambda **_kwargs: Response({"dhanClientId": "different", "accessToken": "synthetic-access-token", "expiryTime": "invalid"}))
    with pytest.raises(DhanAuthError):
        client.consume_consent("synthetic-token-id")
    assert "access_token" not in store.load(DHAN_CONNECTION_ID)
