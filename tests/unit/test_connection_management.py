from __future__ import annotations

import logging
import inspect
from datetime import UTC, datetime

import pytest

from app.connections.credentials import (
    CredentialStoreBackendStatus,
    CredentialStoreUnavailableError,
    InMemoryCredentialStore,
    KeyringCredentialStore,
    WindowsCredentialStore,
    WindowsDPAPICredentialStore,
    resolve_kotak_credentials,
)
from app.connections.models import AccessState, ConnectionMode, ConnectionStatus, ConnectionTestResult, KOTAK_NEO_CREDENTIAL_DEFINITIONS
from app.connections.repository import SQLiteConnectionProfileRepository
from app.connections.service import KOTAK_NEO_CONNECTION_ID, KotakNeoConnectionTester, ProviderConnectionService
from app.market_data.kotak_neo import KOTAK_NEO_PROVIDER
from app.market_data.models import ErrorCode, MarketDataError


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
SECRETS = {"tradeapi_access_token": "consumer-very-secret", "mobile_number": "+919999999999", "ucc": "UCC-123", "mpin": "123456"}


class SuccessfulTester:
    def test(self, profile, credentials):
        assert credentials.tradeapi_access_token == SECRETS["tradeapi_access_token"]
        return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.CONNECTED, AccessState.AVAILABLE, AccessState.NOT_TESTED, "PASS", T)


class FailingTester:
    def test(self, profile, credentials):
        return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.AUTH_FAILED, AccessState.UNAVAILABLE, AccessState.UNAVAILABLE, "FAIL", T, error_code="AUTHENTICATION_FAILED", message="Kotak Neo authentication failed.")


def service(*, tester=None):
    return ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester or SuccessfulTester()}, clock=lambda: T)


def test_kotak_metadata_is_provider_neutral_and_capability_specific() -> None:
    value = service()
    definitions = value.credential_definitions(KOTAK_NEO_PROVIDER)
    assert tuple(item.field for item in definitions) == tuple(SECRETS)
    assert tuple(item.field for item in definitions if ConnectionMode.QUOTE_ONLY in item.required_for) == ("tradeapi_access_token",)
    assert {item.field for item in definitions if ConnectionMode.SESSION_READ in item.required_for} == set(SECRETS)
    assert all(item.sensitivity.value in {"SECRET", "SENSITIVE_IDENTIFIER", "NON_SECRET"} for item in definitions)


def test_profile_round_trip_is_secret_free_and_partial_update_never_overwrites_omitted_values(tmp_path) -> None:
    database = tmp_path / "profiles.sqlite"
    repository = SQLiteConnectionProfileRepository(str(database))
    store = InMemoryCredentialStore()
    value = ProviderConnectionService(repository, store, {KOTAK_NEO_PROVIDER: SuccessfulTester()}, clock=lambda: T)
    configured = value.update_kotak(SECRETS)
    restored = repository.get_profile(KOTAK_NEO_CONNECTION_ID)
    assert restored == configured and restored is not None
    assert all(secret not in repr(restored) for secret in SECRETS.values())
    assert all(secret.encode() not in database.read_bytes() for secret in SECRETS.values())
    value.update_kotak({"tradeapi_access_token": "new-consumer-secret"})
    assert store.load(KOTAK_NEO_CONNECTION_ID)["mpin"] == SECRETS["mpin"]
    with pytest.raises(ValueError, match="placeholder"):
        value.update_kotak({"mpin": "********"})
    assert store.load(KOTAK_NEO_CONNECTION_ID)["mpin"] == SECRETS["mpin"]


def test_configured_is_not_connected_and_clear_removes_all_credentials() -> None:
    value = service()
    configured = value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert configured.status is ConnectionStatus.CONFIGURED
    assert value.clear_kotak_credentials().status is ConnectionStatus.NOT_CONFIGURED
    assert value.kotak_profile().credential_fields_configured == {item.field: False for item in KOTAK_NEO_CREDENTIAL_DEFINITIONS}


def test_token_only_configuration_supports_market_data_but_not_optional_session() -> None:
    value = ProviderConnectionService(
        SQLiteConnectionProfileRepository(),
        InMemoryCredentialStore(),
        {KOTAK_NEO_PROVIDER: KotakNeoConnectionTester()},
        clock=lambda: T,
    )
    profile = value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert profile.status is ConnectionStatus.CONFIGURED
    session = value.test_kotak_session(current_totp="123456")
    assert (session.status, session.error_code) == (ConnectionStatus.NOT_CONFIGURED, "MISSING_SESSION_CONFIGURATION")


def test_existing_legacy_profile_metadata_is_refreshed_without_loading_legacy_token_fields() -> None:
    repository = SQLiteConnectionProfileRepository()
    store = InMemoryCredentialStore()
    now = T
    from app.connections.models import ConnectionProfile
    repository.save_profile(ConnectionProfile(KOTAK_NEO_CONNECTION_ID, KOTAK_NEO_PROVIDER, "Kotak Neo", True, ConnectionStatus.CONFIGURED, now, now, credential_fields_configured={"consumer_key": True, "totp_secret": True, "mpin": True}))
    value = ProviderConnectionService(repository, store, {KOTAK_NEO_PROVIDER: SuccessfulTester()}, clock=lambda: T)
    profile = value.kotak_profile()
    assert profile.status is ConnectionStatus.NOT_CONFIGURED
    assert profile.credential_fields_configured == {item.field: False for item in KOTAK_NEO_CREDENTIAL_DEFINITIONS}


def test_connection_test_is_sanitized_audited_and_never_exposes_credentials(caplog) -> None:
    value = service(tester=FailingTester())
    value.update_kotak(SECRETS)
    with caplog.at_level(logging.INFO):
        result = value.test_kotak()
    assert result.status is ConnectionStatus.AUTH_FAILED and result.error_code == "AUTHENTICATION_FAILED"
    text = repr(result) + "\n".join(record.getMessage() for record in caplog.records) + repr(value.audit_events(KOTAK_NEO_CONNECTION_ID))
    assert all(secret not in text for secret in SECRETS.values())
    assert value.kotak_profile().status is ConnectionStatus.AUTH_FAILED
    assert value.audit_events(KOTAK_NEO_CONNECTION_ID)[-1].event_type == "KOTAK_CONNECTION_TEST_FAILED"


def test_quote_normalization_failure_retains_resolved_and_quote_access_stages() -> None:
    class NormalizationFailureProvider:
        def load_instrument_master(self):
            from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord
            return KotakNeoInstrumentMaster((KotakNeoInstrumentRecord("nse_cm", "2885", "RELIANCE", "RELIANCE-EQ", "Equity"),))
        def get_quote(self, instrument):
            del instrument
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Malformed quote field.")

    tester = KotakNeoConnectionTester(lambda *, credentials, clock: NormalizationFailureProvider(), universe_symbols_provider=lambda: ("RELIANCE",), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert (result.instrument_resolution, result.quote_access, result.canonical_normalization, result.error_code) == ("VALIDATED", AccessState.AVAILABLE, "FAIL", "NORMALIZATION_FAILED")


def test_malformed_instrument_master_is_not_misreported_as_quote_normalization() -> None:
    class MalformedMasterProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self):
            raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Malformed instrument master.")

    tester = KotakNeoConnectionTester(MalformedMasterProvider, universe_symbols_provider=lambda: ("RELIANCE",), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert (result.instrument_resolution, result.quote_access, result.canonical_normalization, result.error_code) == ("FAIL", AccessState.UNAVAILABLE, "NOT_TESTED", "INSTRUMENT_RESOLUTION_FAILED")


def test_secure_store_has_priority_without_mixing_with_environment_fallback() -> None:
    store = InMemoryCredentialStore()
    store.save(KOTAK_NEO_CONNECTION_ID, {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    credentials, source = resolve_kotak_credentials(store, KOTAK_NEO_CONNECTION_ID, {"KOTAK_NEO_MPIN": "environment-mpin"})
    assert source == "SECURE_STORE" and credentials.tradeapi_access_token == SECRETS["tradeapi_access_token"] and credentials.mpin is None
    store.clear(KOTAK_NEO_CONNECTION_ID)
    credentials, source = resolve_kotak_credentials(store, KOTAK_NEO_CONNECTION_ID, {"KOTAK_NEO_TRADEAPI_ACCESS_TOKEN": "environment-consumer"})
    assert source == "ENVIRONMENT" and credentials.tradeapi_access_token == "environment-consumer"


def test_canonical_tradeapi_token_secure_store_round_trip_and_explicit_delete() -> None:
    store = InMemoryCredentialStore()
    synthetic = "synthetic-tradeapi-token"
    store.save(KOTAK_NEO_CONNECTION_ID, {"tradeapi_access_token": synthetic})
    assert store.load(KOTAK_NEO_CONNECTION_ID) == {"tradeapi_access_token": synthetic}
    store.clear(KOTAK_NEO_CONNECTION_ID)
    assert store.load(KOTAK_NEO_CONNECTION_ID) == {}


def test_os_keyring_adapter_uses_keyring_without_normal_database_storage(monkeypatch) -> None:
    import keyring
    values: dict[tuple[str, str], str] = {}
    monkeypatch.setattr(keyring, "set_password", lambda service, account, value: values.__setitem__((service, account), value))
    monkeypatch.setattr(keyring, "get_password", lambda service, account: values.get((service, account)))
    monkeypatch.setattr(keyring, "delete_password", lambda service, account: values.pop((service, account), None))
    store = KeyringCredentialStore("unit-test-keyring")
    store.save("profile", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert store.load("profile") == {"tradeapi_access_token": SECRETS["tradeapi_access_token"]}
    store.clear("profile")
    assert store.load("profile") == {}


def test_windows_keyring_failure_fails_closed_with_a_safe_actionable_message(monkeypatch) -> None:
    import keyring
    monkeypatch.setattr(keyring, "set_password", lambda *args: (_ for _ in ()).throw(OSError(1312, "logon session missing")))
    store = KeyringCredentialStore("unit-test-keyring")
    with pytest.raises(CredentialStoreUnavailableError) as caught:
        store.save("profile", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert "Windows Credential Manager" in str(caught.value)
    assert SECRETS["tradeapi_access_token"] not in str(caught.value)


def test_keyring_backend_status_is_safe_and_does_not_access_credentials() -> None:
    status = KeyringCredentialStore().backend_status()
    assert status.backend in {"WINDOWS_CREDENTIAL_MANAGER", "OS_KEYRING", "UNAVAILABLE"}
    assert "consumer" not in repr(status).lower()


class _SyntheticDPAPI:
    """Test-only stand-in for pywin32; production always imports win32crypt."""

    @staticmethod
    def CryptProtectData(value, description, entropy, reserved, prompt, flags):
        return description, b"protected:" + value[::-1]

    @staticmethod
    def CryptUnprotectData(value, description, entropy, reserved, flags):
        return description, value.removeprefix(b"protected:")[::-1]


def _dpapi_store(tmp_path) -> WindowsDPAPICredentialStore:
    store = WindowsDPAPICredentialStore(base_directory=tmp_path / "local-app-data" / "credentials")
    store._win32crypt = lambda: _SyntheticDPAPI  # type: ignore[method-assign]
    return store


def test_windows_dpapi_store_encrypts_synthetic_values_and_preserves_partial_updates(tmp_path) -> None:
    store = _dpapi_store(tmp_path)
    store.save("kotak-neo", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    store.save("kotak-neo", {"mpin": SECRETS["mpin"]})
    encrypted_files = tuple((tmp_path / "local-app-data" / "credentials").glob("*.dpapi"))
    assert store.load("kotak-neo") == {"tradeapi_access_token": SECRETS["tradeapi_access_token"], "mpin": SECRETS["mpin"]}
    assert all(secret.encode() not in b"".join(path.read_bytes() for path in encrypted_files) for secret in SECRETS.values())
    assert store.has_secret("kotak-neo", "tradeapi_access_token")
    store.clear("kotak-neo")
    assert store.load("kotak-neo") == {} and not store.has_secret("kotak-neo", "tradeapi_access_token")


def test_windows_credential_selector_uses_dpapi_only_for_known_winvault_failure(tmp_path) -> None:
    class BrokenWinVault:
        def backend_status(self):
            return CredentialStoreBackendStatus(True, "WINDOWS_CREDENTIAL_MANAGER")
        def load(self, connection_id):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)
        def save(self, connection_id, values):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)
        def clear(self, connection_id):
            raise CredentialStoreUnavailableError("Windows Credential Manager is unavailable to this process.", dpapi_fallback_eligible=True)

    dpapi = _dpapi_store(tmp_path)
    store = WindowsCredentialStore(native=BrokenWinVault(), dpapi=dpapi)
    store.save("kotak-neo", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert store.load("kotak-neo") == {"tradeapi_access_token": SECRETS["tradeapi_access_token"]}
    assert store.backend_status().backend == "WINDOWS_DPAPI"


def test_windows_credential_selector_prefers_a_functional_native_store_without_copying_to_dpapi(tmp_path) -> None:
    class WorkingWinVault(InMemoryCredentialStore):
        def backend_status(self):
            return CredentialStoreBackendStatus(True, "WINDOWS_CREDENTIAL_MANAGER")

    native, dpapi = WorkingWinVault(), _dpapi_store(tmp_path)
    store = WindowsCredentialStore(native=native, dpapi=dpapi)
    store.save("kotak-neo", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert native.load("kotak-neo") == {"tradeapi_access_token": SECRETS["tradeapi_access_token"]}
    assert dpapi.load("kotak-neo") == {} and not dpapi.is_activated()
    assert store.backend_status().backend == "WINDOWS_CREDENTIAL_MANAGER"


def test_windows_credential_selector_does_not_hide_arbitrary_programming_errors(tmp_path) -> None:
    class BrokenCode:
        def backend_status(self):
            return CredentialStoreBackendStatus(True, "WINDOWS_CREDENTIAL_MANAGER")
        def load(self, connection_id):
            raise RuntimeError("programming error")
        def save(self, connection_id, values):
            raise RuntimeError("programming error")
        def clear(self, connection_id):
            raise RuntimeError("programming error")

    dpapi = _dpapi_store(tmp_path)
    store = WindowsCredentialStore(native=BrokenCode(), dpapi=dpapi)
    with pytest.raises(RuntimeError, match="programming error"):
        store.save("kotak-neo", {"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    assert not dpapi.is_activated() and dpapi.load("kotak-neo") == {}


def test_kotak_connection_tester_performs_only_a_quote_validation_when_target_is_available() -> None:
    calls: list[str] = []

    class FakeProvider:
        def __init__(self, *, credentials, clock):
            assert credentials.tradeapi_access_token == SECRETS["tradeapi_access_token"]
        def get_quote(self, instrument):
            calls.append("quote")
            return type("Quote", (), {"freshness": type("Freshness", (), {"state": type("State", (), {"value": "FRESH"})()})()})()
        def establish_session(self):
            calls.append("session")
            return object()

    from app.market_data.kotak_neo import KotakNeoInstrumentRecord
    tester = KotakNeoConnectionTester(FakeProvider, quote_test_target=KotakNeoInstrumentRecord("nse_cm", "runtime-token", "RELIANCE", "RELIANCE-EQ", "Equity"), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert result.status is ConnectionStatus.CONNECTED and result.quote_access is AccessState.AVAILABLE
    assert calls == ["quote"]


def test_product_connection_flow_uses_token_only_master_and_universe_intersection_without_env_target() -> None:
    calls: list[str] = []

    class AutoProvider:
        def __init__(self, *, credentials, clock):
            assert credentials.tradeapi_access_token == SECRETS["tradeapi_access_token"]
        def load_instrument_master(self):
            calls.append("master")
            return KotakNeoInstrumentMaster((
                KotakNeoInstrumentRecord("nse_cm", "2", "ZETA", "ZETA-EQ", "Equity"),
                KotakNeoInstrumentRecord("nse_cm", "1", "ALPHA", "ALPHA-EQ", "Equity"),
                KotakNeoInstrumentRecord("bse_cm", "3", "ALPHA", "ALPHA", "Equity"),
            ))
        def get_quote(self, instrument):
            calls.append(f"quote:{instrument.symbol}")
            return type("Quote", (), {"freshness": type("Freshness", (), {"state": type("State", (), {"value": "STALE"})()})()})()

    from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord
    store = InMemoryCredentialStore()
    tester = KotakNeoConnectionTester(AutoProvider, universe_symbols_provider=lambda: ("ZETA", "ALPHA"), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak(SECRETS)
    result = value.test_kotak()
    assert (result.status, result.mode, result.session_read_access, result.quote_access) == (ConnectionStatus.CONNECTED, ConnectionMode.QUOTE_ONLY, AccessState.NOT_TESTED, AccessState.AVAILABLE)
    assert (result.test_symbol, result.instrument_resolution, result.canonical_normalization) == ("ALPHA", "VALIDATED", "VALIDATED")
    assert calls == ["master", "quote:ALPHA"]


def test_market_data_validation_is_not_blocked_by_missing_session_configuration_without_env_target() -> None:
    from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord
    class QuoteOnlyProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self):
            return KotakNeoInstrumentMaster((KotakNeoInstrumentRecord("nse_cm", "1", "ALPHA", "ALPHA-EQ", "Equity"),))
        def get_quote(self, instrument):
            return type("Quote", (), {"freshness": type("Freshness", (), {"state": type("State", (), {"value": "FRESH"})()})()})()
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: KotakNeoConnectionTester(QuoteOnlyProvider, universe_symbols_provider=lambda: ("ALPHA",), clock=lambda: T)}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert (result.status, result.error_code, result.session_read_access, result.quote_access) == (ConnectionStatus.CONNECTED, None, AccessState.NOT_TESTED, AccessState.AVAILABLE)


def test_optional_session_uses_transient_current_totp_and_never_persists_it() -> None:
    from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord
    calls: list[str] = []

    class SessionProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self):
            return KotakNeoInstrumentMaster((KotakNeoInstrumentRecord("nse_cm", "1", "ALPHA", "ALPHA-EQ", "Equity"),))
        def get_quote(self, instrument):
            return type("Quote", (), {"freshness": type("Freshness", (), {"state": type("State", (), {"value": "FRESH"})()})()})()
        def establish_session(self, *, current_totp):
            assert current_totp == "654321"
            calls.append("session")

    store = InMemoryCredentialStore()
    tester = KotakNeoConnectionTester(SessionProvider, universe_symbols_provider=lambda: ("ALPHA",), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), store, {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak(SECRETS)
    assert value.test_kotak().status is ConnectionStatus.CONNECTED
    session = value.test_kotak_session(current_totp="654321")
    assert (session.status, session.session_totp_login, session.session_mpin_validation) == (ConnectionStatus.CONNECTED, "VALIDATED", "VALIDATED")
    assert calls == ["session"]
    assert "654321" not in store.load(KOTAK_NEO_CONNECTION_ID).values()
    assert value.kotak_profile().status is ConnectionStatus.CONNECTED


def test_failed_optional_session_does_not_downgrade_a_validated_quote_connection() -> None:
    from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord
    class SessionFailureProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self):
            return KotakNeoInstrumentMaster((KotakNeoInstrumentRecord("nse_cm", "1", "ALPHA", "ALPHA-EQ", "Equity"),))
        def get_quote(self, instrument):
            return type("Quote", (), {"freshness": type("Freshness", (), {"state": type("State", (), {"value": "FRESH"})()})()})()
        def establish_session(self, *, current_totp):
            raise MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "provider detail must not escape")

    tester = KotakNeoConnectionTester(SessionFailureProvider, universe_symbols_provider=lambda: ("ALPHA",), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak(SECRETS)
    assert value.test_kotak().status is ConnectionStatus.CONNECTED
    session = value.test_kotak_session(current_totp="123456")
    assert (session.status, session.error_code) == (ConnectionStatus.AUTH_FAILED, "AUTHENTICATION_FAILED")
    assert value.kotak_profile().status is ConnectionStatus.CONNECTED


def test_product_connection_service_does_not_use_developer_test_mapping_environment(monkeypatch) -> None:
    monkeypatch.setenv("KOTAK_NEO_TEST_EXCHANGE_SEGMENT", "nse_cm")
    monkeypatch.setenv("KOTAK_NEO_TEST_INSTRUMENT_TOKEN", "developer-token")
    monkeypatch.setenv("KOTAK_NEO_TEST_SYMBOL", "RELIANCE")
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), clock=lambda: T)
    assert value._testers[KOTAK_NEO_PROVIDER]._target is None


@pytest.mark.parametrize(
    ("failure_stage", "error", "expected_code", "expected_resolution", "expected_normalization"),
    (
        ("authentication", MarketDataError(ErrorCode.AUTHENTICATION_REQUIRED, "secret never returned"), "ACCESS_TOKEN_REJECTED", "NOT_TESTED", "NOT_TESTED"),
        ("master", MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "secret never returned"), "PROVIDER_UNAVAILABLE", "NOT_TESTED", "NOT_TESTED"),
        ("quote", MarketDataError(ErrorCode.MALFORMED_RESPONSE, "secret never returned"), "NORMALIZATION_FAILED", "VALIDATED", "FAIL"),
    ),
)
def test_product_connection_stage_failures_are_sanitized_and_fail_closed(failure_stage, error, expected_code, expected_resolution, expected_normalization) -> None:
    from app.market_data.kotak_neo import KotakNeoInstrumentMaster, KotakNeoInstrumentRecord

    class FailingStageProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self):
            if failure_stage in {"authentication", "master"}: raise error
            return KotakNeoInstrumentMaster((KotakNeoInstrumentRecord("nse_cm", "1", "ALPHA", "ALPHA-EQ", "Equity"),))
        def get_quote(self, instrument):
            if failure_stage == "quote": raise error
            raise AssertionError("unexpected stage")

    tester = KotakNeoConnectionTester(FailingStageProvider, universe_symbols_provider=lambda: ("ALPHA",), clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak(SECRETS)
    result = value.test_kotak()
    assert result.status in {ConnectionStatus.AUTH_FAILED, ConnectionStatus.UNAVAILABLE, ConnectionStatus.DEGRADED}
    assert (result.error_code, result.instrument_resolution, result.canonical_normalization) == (expected_code, expected_resolution, expected_normalization)
    assert "secret never returned" not in (result.message or "")


def test_missing_credentials_and_provider_unavailability_are_safe_and_never_run_domain_or_account_paths() -> None:
    value = service()
    missing = value.test_kotak()
    assert missing.status is ConnectionStatus.NOT_CONFIGURED and missing.error_code == "ACCESS_TOKEN_REQUIRED"

    class UnavailableProvider:
        def __init__(self, *, credentials, clock): pass
        def load_instrument_master(self, records): raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "provider detail must not escape")

    tester = KotakNeoConnectionTester(UnavailableProvider, quote_test_target=type("Target", (), {"symbol": "RELIANCE"})(), clock=lambda: T)
    unavailable = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    unavailable.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = unavailable.test_kotak()
    assert (result.status, result.error_code, result.message) == (ConnectionStatus.UNAVAILABLE, "PROVIDER_UNAVAILABLE", "Kotak Neo market-data provider is unavailable.")
    source = inspect.getsource(ProviderConnectionService) + inspect.getsource(KotakNeoConnectionTester)
    assert not any(token in source.lower() for token in ("place_order", "modify_order", "cancel_order", "funds", "holdings", "positions"))


def test_quote_only_canonical_quote_validation_retains_mapping_normalization_and_closed_market_freshness() -> None:
    from app.market_data.kotak_neo import KotakNeoHttpResponse, KotakNeoInstrumentRecord, KotakNeoMarketDataProvider

    class Transport:
        def request(self, **kwargs):
            assert kwargs["headers"]["Authorization"] == SECRETS["tradeapi_access_token"]
            return KotakNeoHttpResponse(200, {"data": [{"exchange_token": "runtime-token", "exchange": "nse_cm", "lstup_time": str(int((T.replace(hour=4)).timestamp())), "ltp": "1400.25", "last_volume": "100", "ohlc": {"open": "1399", "high": "1405", "low": "1390", "close": "1395"}}]})

    target = KotakNeoInstrumentRecord("nse_cm", "runtime-token", "RELIANCE", "RELIANCE-EQ", "Equity")
    tester = KotakNeoConnectionTester(lambda *, credentials, clock: KotakNeoMarketDataProvider(credentials, transport=Transport(), clock=clock), quote_test_target=target, clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert (result.status, result.mode, result.test_symbol, result.instrument_resolution, result.canonical_normalization) == (ConnectionStatus.CONNECTED, ConnectionMode.QUOTE_ONLY, "RELIANCE", "VALIDATED", "VALIDATED")
    assert result.freshness in {"FRESH", "STALE", "VERY_STALE", "UNKNOWN"}


def test_quote_connection_reports_instrument_and_normalization_failures_without_provider_details() -> None:
    from app.market_data.kotak_neo import KotakNeoInstrumentRecord
    class BadProvider:
        def __init__(self, *, credentials, clock): pass
        def get_quote(self, instrument): raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "raw provider token must not escape")

    target = KotakNeoInstrumentRecord("nse_cm", "runtime-token", "RELIANCE", "RELIANCE-EQ", "Equity")
    tester = KotakNeoConnectionTester(BadProvider, quote_test_target=target, clock=lambda: T)
    value = ProviderConnectionService(SQLiteConnectionProfileRepository(), InMemoryCredentialStore(), {KOTAK_NEO_PROVIDER: tester}, clock=lambda: T)
    value.update_kotak({"tradeapi_access_token": SECRETS["tradeapi_access_token"]})
    result = value.test_kotak()
    assert (result.status, result.error_code, result.instrument_resolution) == (ConnectionStatus.DEGRADED, "INSTRUMENT_RESOLUTION_FAILED", "FAIL")
    assert "raw provider token" not in (result.message or "")
