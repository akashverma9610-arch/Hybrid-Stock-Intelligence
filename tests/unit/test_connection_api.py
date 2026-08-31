from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.dependencies import get_backend_local_real_portfolio_ohlcv_activation
from app.connections.credentials import (
    CredentialStoreBackendStatus,
    CredentialStoreUnavailableError,
    InMemoryCredentialStore,
    WindowsCredentialStore,
    WindowsDPAPICredentialStore,
)
from app.connections.repository import SQLiteConnectionProfileRepository
from app.connections.service import ProviderConnectionService
from app.connections.models import AccessState, ConnectionStatus, ConnectionTestResult
from app.market_data.kotak_neo import KOTAK_NEO_PROVIDER
from app.market_data.upstox_forensics import CallResult, execute_forensics
from app.market_data.upstox_analytics import UpstoxAnalyticsFeasibilityTester
from app.data_operations.backend_local_upstox import (
    BackendLocalOhlcvActivationResult, BackendLocalOhlcvTargetRun, REAL_PORTFOLIO_OHLCV_TARGETS,
)


T = datetime(2026, 8, 29, 10, tzinfo=UTC)


class QuoteTester:
    def test(self, profile, credentials):
        return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.CONNECTED, AccessState.AVAILABLE, AccessState.NOT_TESTED, "PASS", T)


class FailedTester:
    def test(self, profile, credentials):
        return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.AUTH_FAILED, AccessState.UNAVAILABLE, AccessState.NOT_TESTED, "FAIL", T, error_code="AUTHENTICATION_FAILED", message="Kotak Neo authentication failed.")


class UpstoxTester:
    def test(self, profile, credentials):
        assert credentials == {"access_token": "upstox-secret"}
        return ConnectionTestResult("upstox", profile.connection_id, ConnectionStatus.CONNECTED, AccessState.AVAILABLE, AccessState.NOT_TESTED, "PASS", T, canonical_normalization="PASS")


class UpstoxValidationFlowTester:
    def __init__(self, *, error_message: str | None = None) -> None:
        self._error_message = error_message

    def test(self, profile, credentials):
        assert credentials == {"access_token": "upstox-secret"}
        return ConnectionTestResult(
            "upstox", profile.connection_id, ConnectionStatus.CONNECTED,
            AccessState.AVAILABLE, AccessState.NOT_TESTED, "VALIDATED", T,
            canonical_normalization="VALIDATED",
            validation_flow={
                "credentials": "VALIDATED",
                "instrument_resolution": "VALIDATED",
                "historical_access": "VALIDATED",
                "normalization": "VALIDATED",
                "persistence": "VALIDATED",
                "last_tested_timestamp": T.isoformat(),
                "error_message": self._error_message,
            },
        )


class BackendLocalActivation:
    def run_twice(self):
        runs = tuple(
            BackendLocalOhlcvTargetRun(identifier, "EXACT_MAPPING_AVAILABLE", 252, 252, T, 0, 2, 0, "OHLCV_READY", None)
            for identifier in REAL_PORTFOLIO_OHLCV_TARGETS
        )
        return BackendLocalOhlcvActivationResult(T, runs, runs)


def test_hidden_backend_local_upstox_activation_has_fixed_targets_and_no_secret_input_or_output() -> None:
    application = create_app()
    application.dependency_overrides[get_backend_local_real_portfolio_ohlcv_activation] = BackendLocalActivation
    secret = "upstox-secret"
    with TestClient(application) as client:
        response = client.post("/api/v1/connections/upstox/real-portfolio-ohlcv/refresh")
    assert response.status_code == 200
    body = response.json()
    assert [item["canonical_instrument_id"] for item in body["first_run"]] == list(REAL_PORTFOLIO_OHLCV_TARGETS)
    assert body["first_run"] == body["second_run"]
    assert secret not in response.text and "access_token" not in response.text


def test_upstox_local_connection_route_redacts_token_tests_and_clears() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {"upstox": UpstoxTester()}, clock=lambda: T)
    with TestClient(create_app(connection_service=service)) as client:
        initial = client.get("/api/v1/connections/upstox")
        saved = client.put("/api/v1/connections/upstox", json={"access_token": "upstox-secret"})
        tested = client.post("/api/v1/connections/upstox/test")
        cleared = client.delete("/api/v1/connections/upstox/credentials")
    assert initial.status_code == saved.status_code == tested.status_code == cleared.status_code == 200
    assert initial.json()["credential_fields_configured"] == {"access_token": False}
    assert saved.json()["credential_fields_configured"] == {"access_token": True}
    assert tested.json()["status"] == "CONNECTED" and tested.json()["canonical_normalization"] == "PASS"
    assert "upstox-secret" not in saved.text + tested.text + cleared.text
    assert cleared.json()["credential_fields_configured"] == {"access_token": False} and store.load("upstox") == {}


def test_upstox_successful_validation_flow_serializes_nullable_absent_error_without_exposing_token() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(
        SQLiteConnectionProfileRepository(), store,
        {"upstox": UpstoxValidationFlowTester()}, clock=lambda: T,
    )
    secret = "upstox-secret"
    with TestClient(create_app(connection_service=service)) as client:
        client.put("/api/v1/connections/upstox", json={"access_token": secret})
        response = client.post("/api/v1/connections/upstox/test")
    assert response.status_code == 200
    assert response.json()["validation_flow"]["error_message"] is None
    assert response.json()["status"] == "CONNECTED"
    assert secret not in response.text


def test_upstox_validation_flow_preserves_safe_provider_error_message() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(
        SQLiteConnectionProfileRepository(), store,
        {"upstox": UpstoxValidationFlowTester(error_message="Upstox historical access is not authorized.")},
        clock=lambda: T,
    )
    with TestClient(create_app(connection_service=service)) as client:
        client.put("/api/v1/connections/upstox", json={"access_token": "upstox-secret"})
        response = client.post("/api/v1/connections/upstox/test")
    assert response.status_code == 200
    assert response.json()["validation_flow"]["error_message"] == "Upstox historical access is not authorized."


def test_upstox_rejects_noncanonical_token_field_without_reporting_saved() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {"upstox": UpstoxTester()}, clock=lambda: T)
    synthetic = "synthetic-analytics-token"
    with TestClient(create_app(connection_service=service)) as client:
        rejected = client.put("/api/v1/connections/upstox", json={"analytics_token": synthetic})
        profile = client.get("/api/v1/connections/upstox")
    assert rejected.status_code == 422
    assert synthetic not in rejected.text + profile.text
    assert profile.json()["credential_fields_configured"] == {"access_token": False}
    assert store.load("upstox") == {}


def test_upstox_request_forensics_route_is_local_only_redacted_and_does_not_mutate_connection_state(monkeypatch) -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {"upstox": UpstoxTester()}, clock=lambda: T)
    secret = "synthetic-analytics-token"
    forensic = execute_forensics(
        secret,
        now=T,
        direct_sender=lambda _: CallResult(403, "application/json", {"content-type": "application/json"}, {"code": "UDAPI403"}),
        production_sender=lambda _: CallResult(403, "application/json", {"content-type": "application/json"}, {"code": "UDAPI403"}),
    )
    monkeypatch.setattr(service, "diagnose_upstox_historical_request", lambda: forensic)
    with TestClient(create_app(connection_service=service)) as client:
        response = client.post("/api/v1/connections/upstox/analytics-request-diagnostic/apollohosp")
        profile = client.get("/api/v1/connections/upstox")
    assert response.status_code == 200
    assert response.json()["production"]["headers"]["Authorization"] == "Bearer <ANALYTICS_TOKEN_MASKED>"
    assert response.json()["encoded_instrument_key"] == "NSE_EQ%7CINE437A01024"
    assert secret not in response.text
    assert profile.json()["credential_fields_configured"] == {"access_token": False}
    assert store.load("upstox") == {}


def test_u04_fundamentals_route_returns_structural_evidence_without_secret_or_connection_mutation(monkeypatch) -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {"upstox": UpstoxTester()}, clock=lambda: T)
    secret = "synthetic-u04-token"

    def transport(url, _headers):
        if "income-statement" in url:
            data = {"type": "consolidated", "time_period": "quarterly", "units_in": "crore", "income_statement": [], "full_statement": []}
        else:
            data = {"history": [], "full_statement": []}
        return 200, {"status": "success", "data": data}

    result = UpstoxAnalyticsFeasibilityTester(secret, transport=transport, clock=lambda: T).run()
    monkeypatch.setattr(service, "probe_upstox_analytics_fundamentals", lambda **_: result)
    with TestClient(create_app(connection_service=service)) as client:
        response = client.post("/api/v1/connections/upstox/analytics-fundamentals-probe/apollohosp")
        profile = client.get("/api/v1/connections/upstox")
    assert response.status_code == 200
    body = response.json()
    assert len(body["endpoints"]) == 9
    assert body["endpoints"][1]["safe_query_params"] == {"type": "consolidated", "time_period": "quarterly", "fs": "false"}
    assert secret not in response.text
    assert profile.json()["credential_fields_configured"] == {"access_token": False}
    assert store.load("upstox") == {}


def test_local_connection_routes_redact_secrets_support_partial_update_test_and_clear() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    secret = "api-consumer-secret"
    with TestClient(create_app(connection_service=service)) as client:
        saved = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": secret, "mpin": "123456"})
        listed = client.get("/api/v1/connections")
        tested = client.post("/api/v1/connections/kotak-neo/test")
        cleared = client.delete("/api/v1/connections/kotak-neo/credentials")
    assert saved.status_code == listed.status_code == tested.status_code == cleared.status_code == 200
    assert secret not in saved.text and "123456" not in saved.text
    assert saved.json()["credential_fields_configured"]["tradeapi_access_token"] is True
    assert tested.json()["status"] == "CONNECTED" and tested.json()["quote_access"] == "AVAILABLE"
    assert cleared.json()["credential_fields_configured"]["tradeapi_access_token"] is False
    assert store.load("kotak-neo") == {}


def test_complete_kotak_configuration_returns_presence_flags_only_and_never_persists_values_in_sqlite(tmp_path) -> None:
    profile_database = tmp_path / "profiles.sqlite"
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(str(profile_database)), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    values = {
        "tradeapi_access_token": "tradeapi-access-token-value", "mobile_number": "+919999999999",
        "ucc": "UCC-123", "mpin": "123456",
    }
    with TestClient(create_app(connection_service=service)) as client:
        saved = client.put("/api/v1/connections/kotak-neo", json=values)
        profile = client.get("/api/v1/connections/kotak-neo")
        page = client.get("/setup/kotak-neo")
    assert saved.status_code == profile.status_code == page.status_code == 200
    assert profile.json()["credential_fields_configured"] == {field: True for field in values}
    assert profile.json()["tradeapi_access_token_configured"] is True
    public_text = saved.text + profile.text + page.text
    assert all(value not in public_text for value in values.values())
    assert all(value.encode() not in profile_database.read_bytes() for value in values.values())
    assert store.load("kotak-neo") == values


def test_token_only_kotak_save_is_market_data_configured_but_not_session_configured() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    with TestClient(create_app(connection_service=service)) as client:
        saved = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": "token-only"})
        session = client.post("/api/v1/connections/kotak-neo/session/test", json={"current_totp": "123456"})
    assert saved.status_code == session.status_code == 200
    body = saved.json()
    assert body["market_data_configured"] is True
    assert body["session_configured"] is False
    assert session.json()["error_code"] == "MISSING_SESSION_CONFIGURATION"
    assert "token-only" not in saved.text + session.text


def test_connection_mutation_routes_are_disabled_outside_local_private_boundary() -> None:
    from app.api.settings import APISettings
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    with TestClient(create_app(api_settings=APISettings(environment="production"), connection_service=service)) as client:
        response = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": "not-returned"})
    assert response.status_code == 403 and response.json()["error"]["code"] == "CONNECTION_MANAGEMENT_DISABLED"


def test_legacy_consumer_key_field_is_rejected_and_never_treated_as_tradeapi_access_token() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    with TestClient(create_app(connection_service=service)) as client:
        response = client.put("/api/v1/connections/kotak-neo", json={"consumer_key": "legacy-key"})
        profile = client.get("/api/v1/connections/kotak-neo")
    assert response.status_code == 422
    assert "legacy-key" not in response.text
    assert profile.json()["credential_fields_configured"]["tradeapi_access_token"] is False
    assert store.load("kotak-neo") == {}


def test_server_rendered_kotak_setup_page_uses_password_input_and_existing_redacted_api_flow() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    secret = "browser-consumer-key"
    with TestClient(create_app(connection_service=service)) as client:
        page = client.get("/setup/kotak-neo")
        saved = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": secret})
        tested = client.post("/api/v1/connections/kotak-neo/test")
        cleared = client.delete("/api/v1/connections/kotak-neo/credentials")
    assert page.status_code == 200 and 'type="password"' in page.text and secret not in page.text
    for field in ("tradeapi_access_token", "mobile_number", "ucc", "mpin", "current_totp"):
        assert f'name="{field}"' in page.text
    assert "totp_secret" not in page.text
    assert page.text.count('type="password"') >= 3
    assert saved.status_code == tested.status_code == cleared.status_code == 200
    assert secret not in saved.text + tested.text + cleared.text
    assert tested.json()["status"] == "CONNECTED" and cleared.json()["status"] == "NOT_CONFIGURED"
    assert store.load("kotak-neo") == {}


def test_setup_page_market_data_test_uses_saved_token_without_session_configuration() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    with TestClient(create_app(connection_service=service)) as client:
        saved = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": "saved-token"})
        tested = client.post("/api/v1/connections/kotak-neo/test")
        page = client.get("/setup/kotak-neo")
    assert saved.status_code == tested.status_code == page.status_code == 200
    assert tested.json()["quote_access"] == "AVAILABLE"
    assert tested.json()["session_read_access"] == "NOT_TESTED"
    assert "saveMarketTokenIfProvided" in page.text
    assert "statusState = {marketDataStatus: null, sessionStatus: null}" in page.text
    market_handler = page.text.split("document.getElementById('test-market-data')", 1)[1].split("document.getElementById('test-session')", 1)[0]
    assert "/api/v1/connections/kotak-neo/test" in market_handler
    assert "/api/v1/connections/kotak-neo/session/test" not in market_handler


def test_server_rendered_setup_failure_displays_only_safe_connection_result() -> None:
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: FailedTester()}, clock=lambda: T)
    secret = "not-echoed-on-failure"
    with TestClient(create_app(connection_service=service)) as client:
        client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": secret})
        result = client.post("/api/v1/connections/kotak-neo/test")
    assert result.status_code == 200
    assert result.json()["status"] == "AUTH_FAILED" and result.json()["error_code"] == "AUTHENTICATION_FAILED"
    assert secret not in result.text


def test_current_totp_session_request_is_transient_and_never_echoed_or_persisted() -> None:
    store = InMemoryCredentialStore()
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    current_totp = "654321"
    with TestClient(create_app(connection_service=service)) as client:
        client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": "token", "mobile_number": "+919999999999", "ucc": "UCC-123", "mpin": "123456"})
        response = client.post("/api/v1/connections/kotak-neo/session/test", json={"current_totp": current_totp})
    assert response.status_code == 200
    assert current_totp not in response.text
    assert current_totp not in store.load("kotak-neo").values()


def test_setup_page_uses_selected_windows_dpapi_store_without_returning_the_secret(tmp_path) -> None:
    class NativeWinVault1312:
        def backend_status(self):
            return CredentialStoreBackendStatus(True, "WINDOWS_CREDENTIAL_MANAGER")
        def load(self, connection_id):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)
        def save(self, connection_id, values):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)
        def clear(self, connection_id):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)

    class SyntheticDPAPI:
        @staticmethod
        def CryptProtectData(value, description, entropy, reserved, prompt, flags):
            return description, b"protected:" + value[::-1]
        @staticmethod
        def CryptUnprotectData(value, description, entropy, reserved, flags):
            return description, value.removeprefix(b"protected:")[::-1]

    dpapi = WindowsDPAPICredentialStore(base_directory=tmp_path / "app-data" / "credentials")
    dpapi._win32crypt = lambda: SyntheticDPAPI  # type: ignore[method-assign]
    store = WindowsCredentialStore(native=NativeWinVault1312(), dpapi=dpapi)
    service = ProviderConnectionService(SQLiteConnectionProfileRepository(str(tmp_path / "profiles.sqlite")), store, {KOTAK_NEO_PROVIDER: QuoteTester()}, clock=lambda: T)
    secret = "dpapi-browser-secret"
    with TestClient(create_app(connection_service=service)) as client:
        saved = client.put("/api/v1/connections/kotak-neo", json={"tradeapi_access_token": secret})
        tested = client.post("/api/v1/connections/kotak-neo/test")
        cleared = client.delete("/api/v1/connections/kotak-neo/credentials")
    content = saved.text + tested.text + cleared.text
    assert saved.status_code == tested.status_code == cleared.status_code == 200
    assert saved.json()["credential_store_backend"] == "WINDOWS_DPAPI"
    assert tested.json()["status"] == "CONNECTED"
    assert secret not in content and secret.encode() not in (tmp_path / "profiles.sqlite").read_bytes()
    assert dpapi.load("kotak-neo") == {}
