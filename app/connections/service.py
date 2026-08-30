"""Provider-neutral connection configuration and safe read-only testing."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import os
from typing import Callable, Mapping, Protocol
from uuid import uuid4

from app.connections.credentials import CredentialStore, CredentialStoreBackendStatus, CredentialStoreUnavailableError, resolve_kotak_credentials
from app.connections.models import (
    AccessState, ConnectionAuditEvent, ConnectionMode, ConnectionProfile, ConnectionStatus,
    ConnectionTestResult, KOTAK_NEO_CREDENTIAL_DEFINITIONS, GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS, UPSTOX_CREDENTIAL_DEFINITIONS, GNEWS_CREDENTIAL_DEFINITIONS, requirements_for,
)
from app.connections.repository import SQLiteConnectionProfileRepository
from app.market_data.kotak_neo import KOTAK_NEO_PROVIDER, KotakNeoAuthenticationError, KotakNeoInstrumentMaster, KotakNeoInstrumentRecord, KotakNeoMarketDataProvider
from app.market_data.historical import HistoricalIngestionService
from app.market_data.models import AdjustmentStatus, ErrorCode, Exchange, HistoricalBarsRequest, InstrumentIdentity, InstrumentType, MarketDataError, ProviderInstrumentMapping, Timeframe
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider, load_upstox_nse_bod_instrument_master
from app.market_data.upstox_population import resolve_upstox_equity_mapping
from app.news.models import NewsSearchRequest
from app.news.providers import GNewsResearchProvider


KOTAK_NEO_CONNECTION_ID = "kotak-neo"
GLOBAL_DATAFEEDS_CONNECTION_ID = "global-datafeeds"
GNEWS_CONNECTION_ID = "gnews"
UPSTOX_CONNECTION_ID = "upstox"
_PLACEHOLDERS = {"********", "******", "<redacted>", "redacted"}


class ConnectionTester(Protocol):
    def test(self, profile: ConnectionProfile, credentials) -> ConnectionTestResult: ...


class KotakNeoConnectionTester:
    """Uses only existing Kotak market-data quote/session reads, never account APIs."""

    def __init__(
        self,
        provider_factory: Callable[..., KotakNeoMarketDataProvider] = KotakNeoMarketDataProvider,
        quote_test_target: KotakNeoInstrumentRecord | None = None,
        universe_symbols_provider: Callable[[], tuple[str, ...]] = lambda: (),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._provider_factory, self._target, self._universe_symbols, self._clock = provider_factory, quote_test_target, universe_symbols_provider, clock

    @classmethod
    def from_environment(cls, *, universe_symbols_provider: Callable[[], tuple[str, ...]] = lambda: (), clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> "KotakNeoConnectionTester":
        """Use only a server-side non-secret test mapping; never ask a UI user for a token."""
        segment, token, symbol = (os.environ.get("KOTAK_NEO_TEST_EXCHANGE_SEGMENT"), os.environ.get("KOTAK_NEO_TEST_INSTRUMENT_TOKEN"), os.environ.get("KOTAK_NEO_TEST_SYMBOL"))
        target = KotakNeoInstrumentRecord(segment, token, symbol, symbol) if all((segment, token, symbol)) else None
        return cls(quote_test_target=target, universe_symbols_provider=universe_symbols_provider, clock=clock)

    def test(self, profile: ConnectionProfile, credentials) -> ConnectionTestResult:
        """Backward-compatible name for the normal quote-only product test."""
        return self.test_market_data(profile, credentials)

    def test_market_data(self, profile: ConnectionProfile, credentials, *, test_symbol: str | None = None) -> ConnectionTestResult:
        now = self._clock()
        if not credentials.tradeapi_access_token:
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.NOT_CONFIGURED, AccessState.NOT_CONFIGURED, AccessState.NOT_TESTED, "NOT_TESTED", now, error_code="ACCESS_TOKEN_REQUIRED", message="Kotak Neo TradeAPI Access Token is required for quote validation.", market_data_auth="NOT_CONFIGURED")
        instrument = None
        stage = "instrument_resolution"
        try:
            provider = self._provider_factory(credentials=credentials, clock=self._clock)
            if self._target is not None:
                instrument = KotakNeoInstrumentMaster((self._target,)).resolve(self._target.symbol)
            else:
                master = provider.load_instrument_master()
                instrument = master.resolve(test_symbol.strip().upper()) if test_symbol else _automatic_test_instrument(master, self._universe_symbols())
            stage = "quote"
            quote = provider.get_quote(instrument)
            return ConnectionTestResult(
                KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.CONNECTED,
                AccessState.AVAILABLE, AccessState.NOT_TESTED, "VALIDATED", now,
                mode=ConnectionMode.QUOTE_ONLY, test_symbol=instrument.symbol,
                canonical_normalization="VALIDATED", freshness=quote.freshness.state.value,
                market_data_auth="VALIDATED", ip_configuration="NOT_TESTED",
            )
        except MarketDataError as error:
            status = ConnectionStatus.AUTH_FAILED if error.code is ErrorCode.AUTHENTICATION_REQUIRED else ConnectionStatus.UNAVAILABLE if error.code is ErrorCode.PROVIDER_UNAVAILABLE else ConnectionStatus.DEGRADED
            # This path has not started a TOTP/MPIN session.  A provider 401/403
            # therefore concerns the quote-only TradeAPI Access Token, not a
            # generic session-authentication failure.
            code = error.category if isinstance(error, KotakNeoAuthenticationError) else "ACCESS_TOKEN_REJECTED" if error.code is ErrorCode.AUTHENTICATION_REQUIRED else _test_error_code(error.code)
            if stage == "instrument_resolution" and code == "NORMALIZATION_FAILED":
                # This malformed payload came from scrip-master/master-file
                # composition, before a quote request or normalizer existed.
                code = "INSTRUMENT_RESOLUTION_FAILED"
            resolution = "FAIL" if code == "INSTRUMENT_RESOLUTION_FAILED" else "VALIDATED" if instrument is not None else "NOT_TESTED"
            normalization = "FAIL" if stage == "quote" and code in {"NORMALIZATION_FAILED", "QUALITY_FAILED"} else "NOT_TESTED"
            # A malformed/invalid canonical field can only occur after the
            # quote endpoint supplied a response. Keep the access and
            # resolved-instrument stages truthful instead of collapsing them
            # into the later normalization failure.
            quote_access = AccessState.AVAILABLE if stage == "quote" and instrument is not None and normalization == "FAIL" else AccessState.UNAVAILABLE
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, status, quote_access, AccessState.NOT_TESTED, resolution, now, mode=ConnectionMode.QUOTE_ONLY, canonical_normalization=normalization, error_code=code, message=_safe_message(status), market_data_auth="FAILED" if code == "ACCESS_TOKEN_REJECTED" else "VALIDATED")
        except Exception:
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.UNAVAILABLE, AccessState.UNAVAILABLE, AccessState.NOT_TESTED, "FAIL", now, mode=ConnectionMode.QUOTE_ONLY, error_code="PROVIDER_UNAVAILABLE", message=_safe_message(ConnectionStatus.UNAVAILABLE), market_data_auth="FAILED")

    def test_session(self, profile: ConnectionProfile, credentials, *, current_totp: str) -> ConnectionTestResult:
        now = self._clock()
        missing = tuple(field for field in requirements_for(ConnectionMode.SESSION_READ) if not getattr(credentials, field, None))
        if missing:
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.NOT_CONFIGURED, AccessState.NOT_TESTED, AccessState.NOT_CONFIGURED, "NOT_TESTED", now, mode=ConnectionMode.SESSION_READ, error_code="MISSING_SESSION_CONFIGURATION", message="TradeAPI Access Token, mobile number, UCC, and MPIN are required for session validation.", session_totp_login="BLOCKED", session_mpin_validation="BLOCKED", ip_configuration="NOT_TESTED")
        try:
            provider = self._provider_factory(credentials=credentials, clock=self._clock)
            provider.establish_session(current_totp=current_totp)
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.CONNECTED, AccessState.NOT_TESTED, AccessState.AVAILABLE, "NOT_TESTED", now, mode=ConnectionMode.SESSION_READ, session_totp_login="VALIDATED", session_mpin_validation="VALIDATED", ip_configuration="NOT_TESTED")
        except MarketDataError as error:
            code = error.category if isinstance(error, KotakNeoAuthenticationError) else _test_error_code(error.code)
            totp = "FAILED" if code in {"ACCESS_TOKEN_REJECTED", "INVALID_MOBILE_OR_UCC", "INVALID_TOTP", "TOTP_LOGIN_FAILED", "IP_NOT_ALLOWED"} else "NOT_TESTED"
            mpin = "FAILED" if code == "MPIN_VALIDATION_FAILED" else "NOT_TESTED"
            ip = "IP_ALLOWLIST_REQUIRED" if code == "IP_NOT_ALLOWED" else "NOT_TESTED"
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.AUTH_FAILED if error.code is ErrorCode.AUTHENTICATION_REQUIRED else ConnectionStatus.UNAVAILABLE, AccessState.NOT_TESTED, AccessState.UNAVAILABLE, "NOT_TESTED", now, mode=ConnectionMode.SESSION_READ, error_code=code, message=_safe_message(ConnectionStatus.AUTH_FAILED), session_totp_login=totp, session_mpin_validation=mpin, ip_configuration=ip)
        except Exception:
            return ConnectionTestResult(
                KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.UNAVAILABLE,
                AccessState.NOT_TESTED, AccessState.UNAVAILABLE, "NOT_TESTED", now,
                mode=ConnectionMode.SESSION_READ, error_code="PROVIDER_UNAVAILABLE",
                message="Kotak Neo session validation is unavailable.",
                session_totp_login="NOT_TESTED", session_mpin_validation="NOT_TESTED",
                ip_configuration="NOT_TESTED",
            )


class GNewsConnectionTester:
    """A bounded metadata-only validation; no publisher URL is opened."""
    def __init__(self, provider_factory=GNewsResearchProvider, *, clock=lambda: datetime.now(UTC)) -> None: self._factory,self._clock=provider_factory,clock
    def test(self, profile: ConnectionProfile, credentials) -> ConnectionTestResult:
        now=self._clock(); key=credentials.get("api_key") if hasattr(credentials,"get") else None
        if not key: return ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.NOT_CONFIGURED,AccessState.NOT_CONFIGURED,AccessState.NOT_TESTED,"NOT_TESTED",now,error_code="MISSING_REQUIRED_CREDENTIAL",message="GNews API key is required for validation.")
        try:
            self._factory(key).search_news(NewsSearchRequest("NSE",maximum=1))
            return ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.CONNECTED,AccessState.AVAILABLE,AccessState.NOT_TESTED,"PASS",now,mode=ConnectionMode.QUOTE_ONLY,canonical_normalization="PASS",warnings=("OPTIONAL_SECONDARY_EVIDENCE",))
        except MarketDataError as error:
            status=ConnectionStatus.AUTH_FAILED if error.code is ErrorCode.AUTHENTICATION_REQUIRED else ConnectionStatus.DEGRADED if error.code is ErrorCode.RATE_LIMITED else ConnectionStatus.UNAVAILABLE
            return ConnectionTestResult("gnews",profile.connection_id,status,AccessState.UNAVAILABLE,AccessState.NOT_TESTED,"FAIL",now,error_code=_test_error_code(error.code),message="GNews metadata validation failed.")
        except Exception:
            return ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.UNAVAILABLE,AccessState.UNAVAILABLE,AccessState.NOT_TESTED,"FAIL",now,error_code="PROVIDER_UNAVAILABLE",message="GNews metadata validation failed.")


class UpstoxHistoricalConnectionTester:
    """One bounded V3 daily-history read. It never places orders or scans."""
    def __init__(
        self,
        provider_factory=UpstoxHistoricalProvider,
        *,
        universe_store_provider: Callable[[], object] | None = None,
        historical_store_provider: Callable[[], object] | None = None,
        instrument_master_loader=load_upstox_nse_bod_instrument_master,
        clock=lambda: datetime.now(UTC),
    ) -> None:
        self._provider_factory = provider_factory
        self._universe_store_provider = universe_store_provider
        self._historical_store_provider = historical_store_provider
        self._instrument_master_loader = instrument_master_loader
        self._clock = clock

    def test(self, profile: ConnectionProfile, credentials) -> ConnectionTestResult:
        now = self._clock()
        token = credentials.get("access_token") if hasattr(credentials, "get") else None
        if not token:
            return _upstox_test_result(
                profile, now, ConnectionStatus.NOT_CONFIGURED, AccessState.NOT_CONFIGURED,
                "NOT_TESTED", "FAILED", "NOT_TESTED", "NOT_TESTED",
                error_code="MISSING_CONFIGURATION", message="Upstox Analytics Token is not configured.",
            )
        if self._universe_store_provider is None or self._historical_store_provider is None:
            return _upstox_test_result(
                profile, now, ConnectionStatus.UNAVAILABLE, AccessState.NOT_TESTED,
                "UNAVAILABLE", "VALIDATED", "NOT_TESTED", "NOT_TESTED",
                error_code="INSTRUMENT_MASTER_UNAVAILABLE", message="Upstox historical validation composition is unavailable.",
            )

        # The Settings flow deliberately never consumes UPSTOX_TEST_INSTRUMENT_KEY.
        # It maps one deterministic existing local NSE equity against the official
        # BOD master, then performs exactly one bounded V3 request.
        try:
            master = self._instrument_master_loader()
        except MarketDataError:
            return _upstox_test_result(
                profile, now, ConnectionStatus.UNAVAILABLE, AccessState.NOT_TESTED,
                "FAILED", "VALIDATED", "NOT_TESTED", "NOT_TESTED",
                error_code="INSTRUMENT_MASTER_UNAVAILABLE", message="Upstox NSE instrument master is unavailable.",
            )

        store = self._universe_store_provider()
        resolved = _automatic_upstox_test_instrument(store, master.records, as_of=now)
        if resolved is None:
            return _upstox_test_result(
                profile, now, ConnectionStatus.DEGRADED, AccessState.NOT_TESTED,
                "FAILED", "VALIDATED", "NOT_TESTED", "NOT_TESTED",
                error_code="INSTRUMENT_RESOLUTION_FAILED", message="No unambiguous Upstox NSE equity mapping matches the local universe.",
            )
        instrument, mapping_method = resolved
        try:
            existing = store.provider_mapping(
                canonical_instrument_id=instrument.instrument_id, provider=UPSTOX_PROVIDER, as_of=now,
            )
            mapping = instrument.provider_mappings[0]
            if existing is None or existing.provider_instrument_reference != mapping.provider_instrument_reference:
                store.capture_provider_mapping(
                    instrument, provider=UPSTOX_PROVIDER, effective_as_of=now,
                    source_reference=master.source_url, source_checksum=master.checksum,
                )
            historical = self._historical_store_provider()
            request = HistoricalBarsRequest(
                instrument, Timeframe.DAILY, now - timedelta(days=6), now - timedelta(days=1),
                AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER,
            )
            # No chunk policy is supplied: this is exactly one bounded provider request.
            try:
                report = HistoricalIngestionService(self._provider_factory(token), historical, clock=self._clock).ingest(request)
            finally:
                close = getattr(historical, "close", None)
                if callable(close):
                    close()
            if report.received_count < 1:
                raise MarketDataError(
                    _upstox_ingestion_error_code(report.warnings),
                    "Upstox returned no canonical daily candles.",
                )
            if report.accepted_count + report.duplicate_count < 1:
                raise MarketDataError(ErrorCode.MALFORMED_RESPONSE, "Upstox candles could not be persisted canonically.")
            return _upstox_test_result(
                profile, now, ConnectionStatus.CONNECTED, AccessState.AVAILABLE,
                "VALIDATED", "VALIDATED", "VALIDATED", "VALIDATED",
                test_symbol=instrument.symbol,
                warnings=("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED", f"UPSTOX_MAPPING_{mapping_method}"),
            )
        except MarketDataError as error:
            status = ConnectionStatus.AUTH_FAILED if error.code is ErrorCode.AUTHENTICATION_REQUIRED else ConnectionStatus.DEGRADED if error.code in {ErrorCode.RATE_LIMITED, ErrorCode.MALFORMED_RESPONSE} else ConnectionStatus.UNAVAILABLE
            code = (
                "ACCESS_TOKEN_REJECTED" if error.code is ErrorCode.AUTHENTICATION_REQUIRED else
                "HISTORICAL_ACCESS_FAILED" if error.code is ErrorCode.AUTHORIZATION_FAILURE else
                _test_error_code(error.code)
            )
            response_received = error.code is ErrorCode.MALFORMED_RESPONSE
            return _upstox_test_result(
                profile, now, status, AccessState.AVAILABLE if response_received else AccessState.UNAVAILABLE,
                "VALIDATED", "FAILED" if error.code is ErrorCode.AUTHENTICATION_REQUIRED else "VALIDATED",
                "FAILED" if response_received else "NOT_TESTED", "NOT_TESTED",
                test_symbol=instrument.symbol, error_code=code, message=_upstox_safe_message(code),
                warnings=("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED", f"UPSTOX_MAPPING_{mapping_method}"),
            )


def _automatic_upstox_test_instrument(store, master_records, *, as_of: datetime) -> tuple[InstrumentIdentity, str] | None:
    """Resolve exactly one local NSE equity, never a provider-side universe scan."""
    identities = tuple(
        InstrumentIdentity(
            item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin,
            None, InstrumentType.NSE_EQUITY, item.company_name,
        )
        for item in sorted(store.instruments_as_of(as_of), key=lambda value: (value.symbol, value.instrument_id))
    )
    # ISIN matches are privileged across the whole local-universe intersection,
    # not merely within whichever duplicate symbol happens to sort first.
    for identities_for_stage, method_name in (
        (tuple(item for item in identities if item.isin), "EXACT_ISIN_NSE_CASH"),
        (identities, "EXACT_SYMBOL_NSE_CASH"),
    ):
        for identity in identities_for_stage:
            mapping, status, method = resolve_upstox_equity_mapping(identity, master_records)
            if status == "MATCHED" and mapping is not None and method == method_name:
                return replace(identity, provider_mappings=(mapping,)), method
    return None


def _upstox_test_result(
    profile: ConnectionProfile,
    now: datetime,
    status: ConnectionStatus,
    historical_access: AccessState,
    instrument_resolution: str,
    credentials: str,
    normalization: str,
    persistence: str,
    *,
    test_symbol: str | None = None,
    warnings: tuple[str, ...] = (),
    error_code: str | None = None,
    message: str | None = None,
) -> ConnectionTestResult:
    return ConnectionTestResult(
        UPSTOX_PROVIDER, profile.connection_id, status, historical_access,
        AccessState.NOT_TESTED, instrument_resolution, now,
        mode=ConnectionMode.HISTORICAL_OHLCV, test_symbol=test_symbol,
        canonical_normalization=normalization, warnings=warnings,
        error_code=error_code, message=message,
        market_data_auth=credentials,
        validation_flow={
            "credentials": credentials,
            "instrument_resolution": instrument_resolution,
            "historical_access": (
                "VALIDATED" if historical_access is AccessState.AVAILABLE else
                "NOT_TESTED" if historical_access is AccessState.NOT_TESTED else
                "UNAVAILABLE" if historical_access is AccessState.NOT_CONFIGURED else
                "FAILED"
            ),
            "normalization": normalization,
            "persistence": persistence,
            "last_tested_timestamp": now.isoformat(),
            "error_message": message,
        },
    )


def _upstox_safe_message(code: str) -> str:
    messages = {
        "ACCESS_TOKEN_REJECTED": "Upstox access token was rejected.",
        "HISTORICAL_ACCESS_FAILED": "Upstox historical access is not authorized.",
        "INSTRUMENT_RESOLUTION_FAILED": "Upstox could not resolve the selected NSE equity.",
        "NORMALIZATION_FAILED": "Upstox historical data could not be normalized.",
        "RATE_LIMITED": "Upstox historical validation is rate limited.",
        "PROVIDER_UNAVAILABLE": "Upstox historical service is unavailable.",
        "QUOTE_FAILED": "Upstox historical access failed.",
    }
    return messages.get(code, "Upstox historical validation failed.")


def _upstox_ingestion_error_code(warnings: tuple[str, ...]) -> ErrorCode:
    """Retain the provider failure recorded by existing ingestion instead of masking it."""
    for warning in warnings:
        if warning.startswith("CHUNK_"):
            try:
                return ErrorCode(warning.removeprefix("CHUNK_"))
            except ValueError:
                continue
    return ErrorCode.MALFORMED_RESPONSE


class ProviderConnectionService:
    """Configures profile metadata plus a secure credential source; no analysis is invoked."""

    def __init__(
        self,
        profiles: SQLiteConnectionProfileRepository,
        credentials: CredentialStore,
        testers: Mapping[str, ConnectionTester] | None = None,
        universe_symbols_provider: Callable[[], tuple[str, ...]] = lambda: (),
        upstox_universe_store_provider: Callable[[], object] | None = None,
        upstox_historical_store_provider: Callable[[], object] | None = None,
        upstox_instrument_master_loader=load_upstox_nse_bod_instrument_master,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._profiles, self._credentials, self._testers, self._clock = profiles, credentials, dict(testers or {
            KOTAK_NEO_PROVIDER: KotakNeoConnectionTester(universe_symbols_provider=universe_symbols_provider, clock=clock),
            UPSTOX_PROVIDER: UpstoxHistoricalConnectionTester(
                universe_store_provider=upstox_universe_store_provider,
                historical_store_provider=upstox_historical_store_provider,
                instrument_master_loader=upstox_instrument_master_loader,
                clock=clock,
            ),
            "gnews": GNewsConnectionTester(clock=clock),
        }), clock

    def list_profiles(self) -> tuple[ConnectionProfile, ...]:
        self._ensure_kotak_profile()
        self._ensure_gdfl_profile()
        self._ensure_upstox_profile()
        self._ensure_gnews_profile()
        return self._profiles.list_profiles()

    def kotak_profile(self) -> ConnectionProfile:
        return self._ensure_kotak_profile()

    def credential_definitions(self, provider: str) -> tuple:
        if provider == KOTAK_NEO_PROVIDER:return KOTAK_NEO_CREDENTIAL_DEFINITIONS
        if provider == "global_datafeeds":return GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS
        if provider == UPSTOX_PROVIDER:return UPSTOX_CREDENTIAL_DEFINITIONS
        if provider == "gnews": return GNEWS_CREDENTIAL_DEFINITIONS
        raise KeyError(provider)
    def global_datafeeds_profile(self) -> ConnectionProfile:return self._ensure_gdfl_profile()
    def update_global_datafeeds(self, values: Mapping[str,str]) -> ConnectionProfile:
        profile=self._ensure_gdfl_profile(); _validate_update(values, GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS)
        if values:self._credentials.save(profile.connection_id,values)
        fields=self._configured_fields(profile.connection_id,GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS); updated=replace(profile,status=ConnectionStatus.CONFIGURED if fields["access_key"] else ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=fields);self._profiles.save_profile(updated);return updated
    def clear_global_datafeeds_credentials(self)->ConnectionProfile:
        profile=self._ensure_gdfl_profile();self._credentials.clear(profile.connection_id);updated=replace(profile,status=ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=self._configured_fields(profile.connection_id,GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS));self._profiles.save_profile(updated);return updated
    def upstox_profile(self) -> ConnectionProfile:return self._ensure_upstox_profile()
    def update_upstox(self, values: Mapping[str,str]) -> ConnectionProfile:
        profile=self._ensure_upstox_profile(); _validate_update(values, UPSTOX_CREDENTIAL_DEFINITIONS)
        if values:self._credentials.save(profile.connection_id,values)
        fields=self._configured_fields(profile.connection_id,UPSTOX_CREDENTIAL_DEFINITIONS); updated=replace(profile,status=ConnectionStatus.CONFIGURED if fields["access_token"] else ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=fields);self._profiles.save_profile(updated);self._audit(updated,"UPSTOX_CONNECTION_CONFIGURED",True);return updated
    def clear_upstox_credentials(self)->ConnectionProfile:
        profile=self._ensure_upstox_profile();self._credentials.clear(profile.connection_id);updated=replace(profile,status=ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=self._configured_fields(profile.connection_id,UPSTOX_CREDENTIAL_DEFINITIONS));self._profiles.save_profile(updated);self._audit(updated,"UPSTOX_CONNECTION_CREDENTIALS_CLEARED",True);return updated
    def test_upstox(self) -> ConnectionTestResult:
        profile=self._ensure_upstox_profile();now=self._clock()
        try:result=self._testers[UPSTOX_PROVIDER].test(profile,self._credentials.load(profile.connection_id))
        except CredentialStoreUnavailableError:result=ConnectionTestResult(UPSTOX_PROVIDER,profile.connection_id,ConnectionStatus.UNAVAILABLE,AccessState.UNAVAILABLE,AccessState.NOT_TESTED,"FAIL",now,error_code="CREDENTIAL_STORE_UNAVAILABLE",message="Secure credential storage is unavailable.")
        completed=replace(profile,status=result.status,updated_at=now,last_tested_at=result.tested_at,last_success_at=result.tested_at if result.status is ConnectionStatus.CONNECTED else profile.last_success_at,last_error_code=result.error_code,credential_fields_configured=self._configured_fields(profile.connection_id,UPSTOX_CREDENTIAL_DEFINITIONS),warnings=result.warnings);self._profiles.save_profile(completed);self._audit(completed,"UPSTOX_CONNECTION_TESTED" if result.status is ConnectionStatus.CONNECTED else "UPSTOX_CONNECTION_TEST_FAILED",result.status is ConnectionStatus.CONNECTED,result.error_code);return result

    def test_upstox_analytics_feasibility(self, *, bse_facts=()):
        """Run the explicitly approved, read-only APOLLOHOSP Analytics probe.

        This deliberately has no profile/audit mutation and passes the secure
        credential only to the bounded provider transport.
        """
        from app.market_data.upstox_analytics import UpstoxAnalyticsFeasibilityTester

        return UpstoxAnalyticsFeasibilityTester(
            self._credentials.load(UPSTOX_CONNECTION_ID).get("access_token"),
            bse_facts=bse_facts,
            clock=self._clock,
        ).run()

    def probe_upstox_analytics_fundamentals(self, *, bse_facts=(), isin=None, symbol=None):
        """Run one U04 read-only Fundamentals probe and save redacted evidence.

        This deliberately bypasses profile/audit mutation and has no route to
        canonical stores.  The report contains structural summaries only.
        """
        from pathlib import Path

        from app.market_data.upstox_analytics import (
            APOLLOHOSP_ISIN, APOLLOHOSP_SYMBOL, UpstoxAnalyticsFeasibilityTester,
            write_fundamentals_probe_report,
        )

        result = UpstoxAnalyticsFeasibilityTester(
            self._credentials.load(UPSTOX_CONNECTION_ID).get("access_token"),
            isin=isin or APOLLOHOSP_ISIN, symbol=symbol or APOLLOHOSP_SYMBOL,
            bse_facts=bse_facts, clock=self._clock,
        ).run()
        suffix = "apollohosp" if (isin or APOLLOHOSP_ISIN) == APOLLOHOSP_ISIN else (symbol or "anchor").lower()
        write_fundamentals_probe_report(
            result,
            Path("reports") / f"upstox_analytics_fundamentals_probe_{suffix}.json",
            Path("reports") / f"upstox_analytics_fundamentals_probe_{suffix}.md",
        )
        return result

    def probe_upstox_analytics_fundamentals_anchors(self, subjects):
        """U04 conditional 3×9 anchor probe; callers supply canonical ISINs."""
        from pathlib import Path

        from app.market_data.upstox_analytics import (
            UpstoxAnalyticsFeasibilityTester, write_fundamentals_anchor_report,
        )

        token = self._credentials.load(UPSTOX_CONNECTION_ID).get("access_token")
        results = tuple(
            UpstoxAnalyticsFeasibilityTester(token, isin=isin, symbol=symbol, bse_facts=facts, clock=self._clock).run()
            for symbol, isin, facts in subjects
        )
        write_fundamentals_anchor_report(
            results,
            Path("reports") / "upstox_analytics_fundamentals_probe_anchors.json",
            Path("reports") / "upstox_analytics_fundamentals_probe_anchors.md",
        )
        return results

    def diagnose_upstox_historical_request(self):
        """Run the one authorised, redacted direct-vs-production V3 comparison.

        This has no profile/audit/data write.  The only file written is the
        explicitly requested support report, after its secret-safety scan.
        """
        from pathlib import Path

        from app.market_data.upstox_forensics import execute_forensics, write_support_report

        token = self._credentials.load(UPSTOX_CONNECTION_ID).get("access_token")
        result = execute_forensics(token, now=self._clock())
        write_support_report(result, Path("reports") / "upstox_analytics_request_diagnostic.md", access_token=token or "")
        return result

    def probe_upstox_historical_request(self):
        """One local-only production V3 verification request; no data writes."""
        from app.market_data.upstox_forensics import execute_production_probe

        token = self._credentials.load(UPSTOX_CONNECTION_ID).get("access_token")
        return execute_production_probe(token, now=self._clock())
    def gnews_profile(self) -> ConnectionProfile: return self._ensure_gnews_profile()
    def update_gnews(self, values: Mapping[str,str]) -> ConnectionProfile:
        profile=self._ensure_gnews_profile(); _validate_update(values,GNEWS_CREDENTIAL_DEFINITIONS)
        if values: self._credentials.save(profile.connection_id,values)
        fields=self._configured_fields(profile.connection_id,GNEWS_CREDENTIAL_DEFINITIONS); updated=replace(profile,status=ConnectionStatus.CONFIGURED if fields["api_key"] else ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=fields); self._profiles.save_profile(updated); return updated
    def clear_gnews_credentials(self) -> ConnectionProfile:
        profile=self._ensure_gnews_profile(); self._credentials.clear(profile.connection_id); updated=replace(profile,status=ConnectionStatus.NOT_CONFIGURED,updated_at=self._clock(),credential_fields_configured=self._configured_fields(profile.connection_id,GNEWS_CREDENTIAL_DEFINITIONS)); self._profiles.save_profile(updated); return updated
    def test_gnews(self) -> ConnectionTestResult:
        profile=self._ensure_gnews_profile(); now=self._clock()
        try: result=self._testers["gnews"].test(profile,self._credentials.load(profile.connection_id))
        except CredentialStoreUnavailableError: result=ConnectionTestResult("gnews",profile.connection_id,ConnectionStatus.UNAVAILABLE,AccessState.UNAVAILABLE,AccessState.NOT_TESTED,"NOT_TESTED",now,error_code="CREDENTIAL_STORE_UNAVAILABLE",message="Secure credential storage is unavailable.")
        completed=replace(profile,status=result.status,updated_at=now,last_tested_at=result.tested_at,last_success_at=result.tested_at if result.status is ConnectionStatus.CONNECTED else profile.last_success_at,last_error_code=result.error_code,credential_fields_configured=self._configured_fields(profile.connection_id,GNEWS_CREDENTIAL_DEFINITIONS),warnings=result.warnings)
        self._profiles.save_profile(completed); self._audit(completed,"GNEWS_CONNECTION_TESTED" if result.status is ConnectionStatus.CONNECTED else "GNEWS_CONNECTION_TEST_FAILED",result.status is ConnectionStatus.CONNECTED,result.error_code); return result

    def credential_store_status(self) -> CredentialStoreBackendStatus:
        status = getattr(self._credentials, "backend_status", None)
        return status() if callable(status) else CredentialStoreBackendStatus(True, "SECURE_STORE")

    def update_kotak(self, values: Mapping[str, str], *, display_name: str | None = None, enabled: bool | None = None) -> ConnectionProfile:
        profile = self._ensure_kotak_profile()
        _validate_update(values)
        if values:
            try:
                self._credentials.save(profile.connection_id, values)
            except CredentialStoreUnavailableError:
                raise
            except Exception:
                raise CredentialStoreUnavailableError("Secure credential storage is unavailable.") from None
        fields = self._configured_fields(profile.connection_id)
        status = ConnectionStatus.CONFIGURED if fields["tradeapi_access_token"] else ConnectionStatus.NOT_CONFIGURED
        updated = replace(profile, display_name=display_name or profile.display_name, enabled=profile.enabled if enabled is None else enabled, status=ConnectionStatus.DISABLED if enabled is False else status, updated_at=self._clock(), last_error_code=None, credential_fields_configured=fields)
        self._profiles.save_profile(updated)
        self._audit(profile, "KOTAK_CONNECTION_CONFIGURED", True)
        return updated

    def clear_kotak_credentials(self) -> ConnectionProfile:
        profile = self._ensure_kotak_profile()
        try:
            self._credentials.clear(profile.connection_id)
        except CredentialStoreUnavailableError:
            raise
        except Exception:
            raise CredentialStoreUnavailableError("Secure credential storage is unavailable.") from None
        updated = replace(profile, status=ConnectionStatus.NOT_CONFIGURED, updated_at=self._clock(), last_error_code=None, credential_fields_configured=self._configured_fields(profile.connection_id))
        self._profiles.save_profile(updated)
        self._audit(profile, "KOTAK_CONNECTION_CREDENTIALS_CLEARED", True)
        return updated

    def test_kotak(self, *, test_symbol: str | None = None) -> ConnectionTestResult:
        profile = self._ensure_kotak_profile()
        if not profile.enabled:
            result = ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.DISABLED, AccessState.NOT_TESTED, AccessState.NOT_TESTED, "NOT_TESTED", self._clock(), message="Connection is disabled.")
        else:
            testing = replace(profile, status=ConnectionStatus.TESTING, updated_at=self._clock())
            self._profiles.save_profile(testing)
            try:
                credentials, _source = resolve_kotak_credentials(self._credentials, profile.connection_id)
                if not credentials.tradeapi_access_token:
                    result = ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.NOT_CONFIGURED, AccessState.NOT_CONFIGURED, AccessState.NOT_CONFIGURED, "NOT_TESTED", self._clock(), error_code="ACCESS_TOKEN_REQUIRED", message="Kotak Neo TradeAPI Access Token is required for read-only validation.")
                else:
                    tester = self._testers[KOTAK_NEO_PROVIDER]
                    result = tester.test_market_data(testing, credentials, test_symbol=test_symbol) if isinstance(tester, KotakNeoConnectionTester) else tester.test(testing, credentials)
            except CredentialStoreUnavailableError:
                result = ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.UNAVAILABLE, AccessState.UNAVAILABLE, AccessState.UNAVAILABLE, "NOT_TESTED", self._clock(), error_code="CREDENTIAL_STORE_UNAVAILABLE", message="Secure credential storage is unavailable.")
        completed = replace(profile, status=result.status, updated_at=self._clock(), last_tested_at=result.tested_at, last_success_at=result.tested_at if result.status is ConnectionStatus.CONNECTED else profile.last_success_at, last_error_code=result.error_code, credential_fields_configured=self._configured_fields(profile.connection_id), warnings=result.warnings)
        self._profiles.save_profile(completed)
        self._audit(completed, "KOTAK_CONNECTION_TESTED" if result.status is ConnectionStatus.CONNECTED else "KOTAK_CONNECTION_TEST_FAILED", result.status is ConnectionStatus.CONNECTED, result.error_code)
        return result

    def test_kotak_session(self, *, current_totp: str) -> ConnectionTestResult:
        """Run the optional TOTP/MPIN session test without changing quote readiness."""
        profile = self._ensure_kotak_profile()
        if not profile.enabled:
            return ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.DISABLED, AccessState.NOT_TESTED, AccessState.NOT_TESTED, "NOT_TESTED", self._clock(), mode=ConnectionMode.SESSION_READ, message="Connection is disabled.")
        try:
            credentials, _source = resolve_kotak_credentials(self._credentials, profile.connection_id)
            missing = tuple(field for field in requirements_for(ConnectionMode.SESSION_READ) if not getattr(credentials, field, None))
            if missing:
                result = ConnectionTestResult(
                    KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.NOT_CONFIGURED,
                    AccessState.NOT_TESTED, AccessState.NOT_CONFIGURED, "NOT_TESTED", self._clock(),
                    mode=ConnectionMode.SESSION_READ, error_code="MISSING_SESSION_CONFIGURATION",
                    message="TradeAPI Access Token, mobile number, UCC, and MPIN are required for session validation.",
                    session_totp_login="BLOCKED", session_mpin_validation="BLOCKED", ip_configuration="NOT_TESTED",
                )
            else:
                tester = self._testers[KOTAK_NEO_PROVIDER]
                if not isinstance(tester, KotakNeoConnectionTester):
                    result = ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.UNAVAILABLE, AccessState.NOT_TESTED, AccessState.UNAVAILABLE, "NOT_TESTED", self._clock(), mode=ConnectionMode.SESSION_READ, error_code="SESSION_TEST_UNAVAILABLE", message="Kotak session validation is unavailable.")
                else:
                    result = tester.test_session(profile, credentials, current_totp=current_totp)
        except CredentialStoreUnavailableError:
            result = ConnectionTestResult(KOTAK_NEO_PROVIDER, profile.connection_id, ConnectionStatus.UNAVAILABLE, AccessState.NOT_TESTED, AccessState.UNAVAILABLE, "NOT_TESTED", self._clock(), mode=ConnectionMode.SESSION_READ, error_code="CREDENTIAL_STORE_UNAVAILABLE", message="Secure credential storage is unavailable.")
        # A failed optional session must never erase a previously validated
        # quote-only connection.  Persist only safe session-test metadata.
        completed = replace(profile, updated_at=self._clock(), last_tested_at=result.tested_at, last_error_code=result.error_code, credential_fields_configured=self._configured_fields(profile.connection_id))
        self._profiles.save_profile(completed)
        self._audit(completed, "KOTAK_SESSION_TESTED" if result.status is ConnectionStatus.CONNECTED else "KOTAK_SESSION_TEST_FAILED", result.status is ConnectionStatus.CONNECTED, result.error_code)
        return result

    def audit_events(self, connection_id: str) -> tuple[ConnectionAuditEvent, ...]:
        return self._profiles.audit_events(connection_id)

    def _ensure_kotak_profile(self) -> ConnectionProfile:
        existing = self._profiles.get_profile(KOTAK_NEO_CONNECTION_ID)
        if existing:
            # Profile metadata from older versions can contain legacy field
            # names even though the secure reader deliberately never loads
            # them. Refresh only the non-secret configured flags so UI/runtime
            # state matches the canonical secure-store contract.
            fields = self._configured_fields(KOTAK_NEO_CONNECTION_ID)
            existing_fields = dict(existing.credential_fields_configured)
            canonical_names = set(fields)
            legacy_schema = set(existing_fields) != canonical_names
            # A status from a current canonical profile records the last real
            # capability check; do not turn CONNECTED/AUTH_FAILED into merely
            # CONFIGURED on a harmless GET. Only obsolete field schemas need a
            # status reset because they could never prove the canonical token.
            status = (ConnectionStatus.DISABLED if not existing.enabled else ConnectionStatus.CONFIGURED if fields["tradeapi_access_token"] else ConnectionStatus.NOT_CONFIGURED) if legacy_schema else existing.status
            if existing_fields != fields or existing.status is not status:
                existing = replace(existing, status=status, updated_at=self._clock(), credential_fields_configured=fields)
                self._profiles.save_profile(existing)
            return existing
        now = self._clock()
        fields = self._configured_fields(KOTAK_NEO_CONNECTION_ID)
        profile = ConnectionProfile(KOTAK_NEO_CONNECTION_ID, KOTAK_NEO_PROVIDER, "Kotak Neo", True, ConnectionStatus.CONFIGURED if fields["tradeapi_access_token"] else ConnectionStatus.NOT_CONFIGURED, now, now, capabilities=(ConnectionMode.QUOTE_ONLY, ConnectionMode.SESSION_READ), credential_fields_configured=fields)
        self._profiles.save_profile(profile)
        return profile
    def _ensure_gdfl_profile(self)->ConnectionProfile:
        existing=self._profiles.get_profile(GLOBAL_DATAFEEDS_CONNECTION_ID)
        if existing:return existing
        now=self._clock();fields=self._configured_fields(GLOBAL_DATAFEEDS_CONNECTION_ID,GLOBAL_DATAFEEDS_CREDENTIAL_DEFINITIONS);profile=ConnectionProfile(GLOBAL_DATAFEEDS_CONNECTION_ID,"global_datafeeds","Global Datafeeds",True,ConnectionStatus.CONFIGURED if fields["access_key"] else ConnectionStatus.NOT_CONFIGURED,now,now,capabilities=(ConnectionMode.QUOTE_ONLY,),credential_fields_configured=fields);self._profiles.save_profile(profile);return profile
    def _ensure_upstox_profile(self)->ConnectionProfile:
        existing=self._profiles.get_profile(UPSTOX_CONNECTION_ID)
        if existing:
            capabilities = (ConnectionMode.HISTORICAL_OHLCV,)
            if existing.capabilities != capabilities:
                existing = replace(existing, capabilities=capabilities, updated_at=self._clock())
                self._profiles.save_profile(existing)
            return existing
        now=self._clock();fields=self._configured_fields(UPSTOX_CONNECTION_ID,UPSTOX_CREDENTIAL_DEFINITIONS);profile=ConnectionProfile(UPSTOX_CONNECTION_ID,UPSTOX_PROVIDER,"Upstox Historical",True,ConnectionStatus.CONFIGURED if fields["access_token"] else ConnectionStatus.NOT_CONFIGURED,now,now,capabilities=(ConnectionMode.HISTORICAL_OHLCV,),credential_fields_configured=fields,warnings=("HISTORICAL_ONLY", "ADJUSTMENT_SEMANTICS_UNDOCUMENTED"));self._profiles.save_profile(profile);return profile
    def _ensure_gnews_profile(self)->ConnectionProfile:
        existing=self._profiles.get_profile(GNEWS_CONNECTION_ID)
        if existing:return existing
        now=self._clock();fields=self._configured_fields(GNEWS_CONNECTION_ID,GNEWS_CREDENTIAL_DEFINITIONS);profile=ConnectionProfile(GNEWS_CONNECTION_ID,"gnews","GNews",True,ConnectionStatus.CONFIGURED if fields["api_key"] else ConnectionStatus.NOT_CONFIGURED,now,now,capabilities=(ConnectionMode.QUOTE_ONLY,),credential_fields_configured=fields,warnings=("OPTIONAL_SECONDARY_NEWS_PROVIDER",));self._profiles.save_profile(profile);return profile

    def _configured_fields(self, connection_id: str, definitions=KOTAK_NEO_CREDENTIAL_DEFINITIONS) -> dict[str, bool]:
        try:
            values = self._credentials.load(connection_id)
        except CredentialStoreUnavailableError:
            raise
        except Exception:
            raise CredentialStoreUnavailableError("Secure credential storage is unavailable.") from None
        return {definition.field: bool(values.get(definition.field)) for definition in definitions}

    def _audit(self, profile: ConnectionProfile, event_type: str, success: bool | None, error_code: str | None = None) -> None:
        self._profiles.append_audit(ConnectionAuditEvent(uuid4().hex, profile.connection_id, profile.provider, event_type, self._clock(), success, error_code))


def _validate_update(values: Mapping[str, str], definitions=KOTAK_NEO_CREDENTIAL_DEFINITIONS) -> None:
    known = {definition.field for definition in definitions}
    unknown = set(values) - known
    if unknown:
        raise ValueError("Unknown credential field.")
    if any(not value.strip() or value.strip().lower() in _PLACEHOLDERS for value in values.values()):
        raise ValueError("Credential updates cannot use empty or placeholder values.")
    mobile = values.get("mobile_number")
    if mobile is not None:
        digits = mobile.removeprefix("+")
        if not digits.isdigit() or not 10 <= len(digits) <= 15:
            raise ValueError("Mobile number must contain 10 to 15 digits.")
    ucc = values.get("ucc")
    if ucc is not None and (not 3 <= len(ucc) <= 32 or not all(character.isalnum() or character in "-_" for character in ucc)):
        raise ValueError("UCC / Client ID format is invalid.")
    mpin = values.get("mpin")
    if mpin is not None and (not mpin.isdigit() or not 4 <= len(mpin) <= 8):
        raise ValueError("MPIN must contain 4 to 8 digits.")


def _safe_message(status: ConnectionStatus) -> str:
    if status is ConnectionStatus.AUTH_FAILED:
        return "Kotak Neo authentication failed."
    if status is ConnectionStatus.UNAVAILABLE:
        return "Kotak Neo market-data provider is unavailable."
    return "Kotak Neo connection test failed."


def _test_error_code(error_code: ErrorCode) -> str:
    if error_code is ErrorCode.AUTHENTICATION_REQUIRED:
        return "AUTHENTICATION_FAILED"
    if error_code is ErrorCode.PROVIDER_UNAVAILABLE:
        return "PROVIDER_UNAVAILABLE"
    if error_code is ErrorCode.RATE_LIMITED:
        return "RATE_LIMITED"
    if error_code in {ErrorCode.INSTRUMENT_NOT_FOUND, ErrorCode.AMBIGUOUS_INSTRUMENT}:
        return "INSTRUMENT_RESOLUTION_FAILED"
    if error_code is ErrorCode.MALFORMED_RESPONSE:
        return "NORMALIZATION_FAILED"
    return "QUOTE_FAILED"


def _automatic_test_instrument(master: KotakNeoInstrumentMaster, universe_symbols: tuple[str, ...]) -> InstrumentIdentity:
    """Pick one deterministic NSE equity from the immutable local universe/master intersection."""
    allowed = {item.strip().upper() for item in universe_symbols if item.strip()}
    if not allowed:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "No local NSE universe is available for Kotak Neo validation.")
    candidates = tuple(
        item for item in master.identities
        if item.exchange is Exchange.NSE and item.instrument_type is InstrumentType.NSE_EQUITY
        and item.symbol.strip().upper() in allowed
    )
    if not candidates:
        raise MarketDataError(ErrorCode.INSTRUMENT_NOT_FOUND, "No Kotak Neo NSE equity mapping matches the local universe.")
    return min(candidates, key=lambda item: (item.symbol.upper(), item.instrument_id))
