"""Isolated local/private configuration routes; no analytical or trading actions."""

from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.api.dependencies import get_api_settings, get_backend_local_real_portfolio_ohlcv_activation, get_connection_service
from app.api.errors import APIRequestError
from app.api.schemas.connections import (
    BackendLocalOhlcvActivationResponse, BackendLocalOhlcvTargetResponse, ConnectionListResponse, ConnectionProfileResponse, ConnectionTestResponse,
    CredentialDefinitionResponse, KotakConnectionUpdateRequest, KotakMarketDataTestRequest, KotakSessionTestRequest, GlobalDatafeedsConnectionUpdateRequest, UpstoxConnectionUpdateRequest, GNewsConnectionUpdateRequest, UpstoxAnalyticsEndpointResponse, UpstoxAnalyticsFeasibilityResponse, UpstoxAnalyticsAnchorsResponse, UpstoxRequestForensicsResponse, UpstoxPreparedRequestResponse, UpstoxRequestCallResponse,
)
from app.api.settings import APISettings
from app.connections.models import ConnectionProfile, ConnectionTestResult
from app.connections.credentials import CredentialStoreUnavailableError
from app.connections.service import ProviderConnectionService


router = APIRouter(tags=["connections"])


def _require_local(settings: APISettings) -> None:
    if not settings.connection_management_available:
        raise APIRequestError(status_code=403, code="CONNECTION_MANAGEMENT_DISABLED", message="Connection management is limited to local/private deployments.")


@router.get("/connections", response_model=ConnectionListResponse)
def connections(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionListResponse:
    _require_local(settings)
    return ConnectionListResponse(items=tuple(_profile(item, service) for item in service.list_profiles()))


@router.get("/connections/kotak-neo", response_model=ConnectionProfileResponse)
def kotak_connection(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionProfileResponse:
    _require_local(settings)
    return _profile(service.kotak_profile(), service)


@router.put("/connections/kotak-neo", response_model=ConnectionProfileResponse)
def update_kotak_connection(request: KotakConnectionUpdateRequest, settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionProfileResponse:
    _require_local(settings)
    try:
        return _profile(service.update_kotak(request.credential_values(), display_name=request.display_name, enabled=request.enabled), service)
    except ValueError as error:
        raise APIRequestError(status_code=422, code="INVALID_CONNECTION_CONFIGURATION", message=str(error)) from None
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None


@router.post("/connections/kotak-neo/test", response_model=ConnectionTestResponse)
def test_kotak_connection(request: KotakMarketDataTestRequest | None = None, settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionTestResponse:
    _require_local(settings)
    return _result(service.test_kotak(test_symbol=request.test_symbol if request else None))


@router.post("/connections/kotak-neo/session/test", response_model=ConnectionTestResponse)
def test_kotak_session(request: KotakSessionTestRequest, settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionTestResponse:
    _require_local(settings)
    try:
        try:
            return _result(service.test_kotak_session(current_totp=request.totp_value()))
        except ValueError:
            raise APIRequestError(status_code=422, code="INVALID_TOTP", message="Current authenticator TOTP must contain six digits.") from None
    finally:
        # The request object and its SecretStr go out of scope immediately; no
        # credential-store, profile, audit, or response record receives it.
        del request


@router.delete("/connections/kotak-neo/credentials", response_model=ConnectionProfileResponse)
def clear_kotak_connection_credentials(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> ConnectionProfileResponse:
    _require_local(settings)
    try:
        return _profile(service.clear_kotak_credentials(), service)
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None

@router.get("/connections/global-datafeeds",response_model=ConnectionProfileResponse)
def global_datafeeds_connection(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)): _require_local(settings);return _profile(service.global_datafeeds_profile(),service)
@router.put("/connections/global-datafeeds",response_model=ConnectionProfileResponse)
def update_global_datafeeds_connection(request:GlobalDatafeedsConnectionUpdateRequest,settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.update_global_datafeeds(request.credential_values()),service)
@router.delete("/connections/global-datafeeds/credentials",response_model=ConnectionProfileResponse)
def clear_global_datafeeds_connection_credentials(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.clear_global_datafeeds_credentials(),service)

@router.get("/connections/upstox",response_model=ConnectionProfileResponse)
def upstox_connection(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)): _require_local(settings);return _profile(service.upstox_profile(),service)
@router.put("/connections/upstox",response_model=ConnectionProfileResponse)
def update_upstox_connection(request:UpstoxConnectionUpdateRequest,settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.update_upstox(request.credential_values()),service)
@router.post("/connections/upstox/test",response_model=ConnectionTestResponse)
def test_upstox_connection(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _result(service.test_upstox())


@router.post("/connections/upstox/real-portfolio-ohlcv/refresh", response_model=BackendLocalOhlcvActivationResponse, include_in_schema=False)
def refresh_real_portfolio_upstox_ohlcv(
    settings: APISettings = Depends(get_api_settings),
    service = Depends(get_backend_local_real_portfolio_ohlcv_activation),
) -> BackendLocalOhlcvActivationResponse:
    """Local-only, fixed-target evidence activation; it accepts no request body."""
    _require_local(settings)
    result = service.run_twice()
    return BackendLocalOhlcvActivationResponse(
        requested_at=result.requested_at,
        first_run=tuple(BackendLocalOhlcvTargetResponse(**asdict(item)) for item in result.first_run),
        second_run=tuple(BackendLocalOhlcvTargetResponse(**asdict(item)) for item in result.second_run),
    )


@router.post("/connections/upstox/analytics-feasibility/apollohosp", response_model=UpstoxAnalyticsFeasibilityResponse, include_in_schema=False)
def test_upstox_analytics_feasibility(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> UpstoxAnalyticsFeasibilityResponse:
    """One local-only, read-only proof; it neither persists nor runs analysis."""
    _require_local(settings)
    try:
        result = service.test_upstox_analytics_feasibility(bse_facts=_apollohosp_bse_facts(settings))
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None
    return _upstox_feasibility_response(result)


@router.post("/connections/upstox/analytics-fundamentals-probe/apollohosp", response_model=UpstoxAnalyticsFeasibilityResponse, include_in_schema=False)
def probe_upstox_analytics_fundamentals(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> UpstoxAnalyticsFeasibilityResponse:
    """U04: exactly nine sequential, documented Fundamentals calls only."""
    _require_local(settings)
    try:
        result = service.probe_upstox_analytics_fundamentals(bse_facts=_apollohosp_bse_facts(settings))
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None
    return _upstox_feasibility_response(result)


@router.post("/connections/upstox/analytics-fundamentals-probe/anchors", response_model=UpstoxAnalyticsAnchorsResponse, include_in_schema=False)
def probe_upstox_analytics_fundamentals_anchors(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> UpstoxAnalyticsAnchorsResponse:
    """U04's optional three-anchor pass, gated by the APOLLO core report."""
    _require_local(settings)
    if not _apollohosp_core_probe_succeeded():
        raise APIRequestError(status_code=409, code="APOLLOHOSP_CORE_PROBE_REQUIRED", message="Run the successful APOLLOHOSP Fundamentals probe before the three-anchor pass.")
    subjects = _upstox_anchor_subjects(settings)
    if len(subjects) != 3:
        raise APIRequestError(status_code=409, code="CANONICAL_ANCHOR_IDENTITIES_REQUIRED", message="Exact canonical BSE-backed identities for all three anchors are required.")
    try:
        values = service.probe_upstox_analytics_fundamentals_anchors(subjects)
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None
    return UpstoxAnalyticsAnchorsResponse(anchors=tuple(_upstox_feasibility_response(item) for item in values))


@router.post("/connections/upstox/analytics-request-diagnostic/apollohosp", response_model=UpstoxRequestForensicsResponse, include_in_schema=False)
def diagnose_upstox_historical_request(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> UpstoxRequestForensicsResponse:
    """Local-only, two-call forensic check.  Its response is fully redacted."""
    _require_local(settings)
    try:
        result = service.diagnose_upstox_historical_request()
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None
    except ValueError as error:
        raise APIRequestError(status_code=422, code="MISSING_CONFIGURATION", message=str(error)) from None
    return UpstoxRequestForensicsResponse(
        token_audit={
            "present": result.token_audit.present,
            "leading_whitespace_present": result.token_audit.leading_whitespace_present,
            "trailing_whitespace_present": result.token_audit.trailing_whitespace_present,
            "embedded_newline_present": result.token_audit.embedded_newline_present,
            "surrounding_quotes_present": result.token_audit.surrounding_quotes_present,
            "already_has_bearer_prefix": result.token_audit.already_has_bearer_prefix,
            "normalized": result.token_audit.normalized,
        },
        raw_instrument_key=result.raw_instrument_key,
        encoded_instrument_key=result.encoded_instrument_key,
        production=UpstoxPreparedRequestResponse(
            name=result.production.name, method=result.production.method, url=result.production.url,
            headers=dict(result.production.headers), body=result.production.body,
        ),
        direct=UpstoxPreparedRequestResponse(
            name=result.direct.name, method=result.direct.method, url=result.direct.url,
            headers=dict(result.direct.headers), body=result.direct.body,
        ),
        differences=result.differences,
        direct_result=_upstox_request_call(result.direct_result),
        production_result=_upstox_request_call(result.production_result),
    )


@router.post("/connections/upstox/analytics-production-probe/apollohosp", response_model=UpstoxRequestForensicsResponse, include_in_schema=False)
def probe_upstox_historical_request(settings: APISettings = Depends(get_api_settings), service: ProviderConnectionService = Depends(get_connection_service)) -> UpstoxRequestForensicsResponse:
    """Local-only single production request, intended only for U02 verification."""
    _require_local(settings)
    try:
        result = service.probe_upstox_historical_request()
    except CredentialStoreUnavailableError as error:
        raise APIRequestError(status_code=503, code="CREDENTIAL_STORE_UNAVAILABLE", message=str(error)) from None
    except ValueError as error:
        raise APIRequestError(status_code=422, code="MISSING_CONFIGURATION", message=str(error)) from None
    return UpstoxRequestForensicsResponse(
        token_audit={
            "present": result.token_audit.present,
            "leading_whitespace_present": result.token_audit.leading_whitespace_present,
            "trailing_whitespace_present": result.token_audit.trailing_whitespace_present,
            "embedded_newline_present": result.token_audit.embedded_newline_present,
            "surrounding_quotes_present": result.token_audit.surrounding_quotes_present,
            "already_has_bearer_prefix": result.token_audit.already_has_bearer_prefix,
            "normalized": result.token_audit.normalized,
        },
        raw_instrument_key=result.raw_instrument_key,
        encoded_instrument_key=result.encoded_instrument_key,
        production=UpstoxPreparedRequestResponse(
            name=result.production.name, method=result.production.method, url=result.production.url,
            headers=dict(result.production.headers), body=result.production.body,
        ),
        direct=UpstoxPreparedRequestResponse(
            name=result.direct.name, method=result.direct.method, url=result.direct.url,
            headers=dict(result.direct.headers), body=result.direct.body,
        ),
        differences=result.differences,
        direct_result=None,
        production_result=_upstox_request_call(result.production_result),
    )
@router.delete("/connections/upstox/credentials",response_model=ConnectionProfileResponse)
def clear_upstox_connection_credentials(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.clear_upstox_credentials(),service)


def _upstox_request_call(result) -> UpstoxRequestCallResponse | None:
    if result is None:
        return None
    return UpstoxRequestCallResponse(
        status_code=result.status_code,
        content_type=result.content_type,
        response_headers=dict(result.response_headers),
        body=result.body,
        error=result.error,
    )


def _upstox_feasibility_response(result) -> UpstoxAnalyticsFeasibilityResponse:
    return UpstoxAnalyticsFeasibilityResponse(
        isin=result.isin,
        symbol=result.symbol,
        instrument_key=result.instrument_key or "",
        credential_accepted=result.credential_accepted,
        endpoints=tuple(UpstoxAnalyticsEndpointResponse(
            endpoint=item.endpoint, method=item.method, safe_url=item.safe_url,
            safe_query_params=dict(item.safe_query_params), http_status=item.http_status,
            content_type=item.content_type, status=item.status, upstox_status=item.upstox_status,
            summary=dict(item.summary), top_level_schema=item.top_level_schema,
            data_schema_summary=dict(item.data_schema_summary), record_count=item.record_count,
            periods=item.periods, units=item.units, statement_type=item.statement_type,
            time_period=item.time_period, full_statement_present=item.full_statement_present,
            timestamp_fields_detected=tuple(dict(value) for value in item.timestamp_fields_detected),
            pit_quality=item.pit_quality, error_code=item.error_code, error_message=item.error_message,
        ) for item in result.endpoints),
        reconciliation=tuple(dict(item) for item in result.reconciliation),
        pit_timestamp_fields=result.pit_timestamp_fields,
        stopped_early=result.stopped_early,
        stop_reason=result.stop_reason,
    )


def _apollohosp_bse_facts(settings: APISettings):
    """Read existing local BSE facts only; no feeder, network, or DB writes."""
    import sqlite3

    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.storage.database import DatabaseBackend, DatabaseSettings

    database = settings.database
    if database.storage_mode.value == "IN_MEMORY_SQLITE":
        database = DatabaseSettings.local_runtime()
    if database.backend is not DatabaseBackend.SQLITE:
        return ()
    path = database.url.removeprefix("sqlite:///")
    # The immutable facts themselves remain the typed source of truth.  This
    # narrow lookup merely finds the known APOLLOHOSP identity in a persistent
    # database that may have a different API snapshot composition.
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            "SELECT fact_id FROM financial_facts WHERE payload_json LIKE ?",
            ('%"symbol":"APOLLOHOSP"%',),
        ).fetchall()
    finally:
        connection.close()
    facts = SQLiteFinancialFactStore(path)
    return tuple(
        item for row in rows if (item := facts.get(row[0])) is not None and item.source.lower().startswith("bse")
    )


def _apollohosp_core_probe_succeeded() -> bool:
    """Gate the 27-call anchor pass on the secret-safe Phase 1 report."""
    import json
    from pathlib import Path

    path = Path("reports") / "upstox_analytics_fundamentals_probe_apollohosp.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    endpoints = {str(item.get("endpoint")): item for item in payload.get("endpoints", ()) if isinstance(item, dict)}
    return all(endpoints.get(name, {}).get("http_status") == 200 for name in ("income_statement_quarterly", "income_statement_yearly_full", "balance_sheet", "cash_flow"))


def _upstox_anchor_subjects(settings: APISettings):
    """Read only exact stored BSE-backed identities; never guess an ISIN."""
    import sqlite3

    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.storage.database import DatabaseBackend, DatabaseSettings

    database = settings.database
    if database.storage_mode.value == "IN_MEMORY_SQLITE":
        database = DatabaseSettings.local_runtime()
    if database.backend is not DatabaseBackend.SQLITE:
        return ()
    path = database.url.removeprefix("sqlite:///")
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute("SELECT fact_id FROM financial_facts").fetchall()
    except sqlite3.Error:
        return ()
    finally:
        connection.close()
    facts = SQLiteFinancialFactStore(path)
    by_symbol = {}
    for row in rows:
        fact = facts.get(row[0])
        if fact is None or not fact.source.lower().startswith("bse"):
            continue
        symbol, isin = fact.instrument.symbol, fact.instrument.isin
        if symbol in {"APOLLOHOSP", "SAFARI", "ORIENTTECH"} and isin:
            bucket = by_symbol.setdefault(symbol, [isin, []])
            if bucket[0] != isin:
                return ()
            bucket[1].append(fact)
    ordered = []
    for symbol in ("APOLLOHOSP", "SAFARI", "ORIENTTECH"):
        if symbol not in by_symbol:
            return ()
        isin, values = by_symbol[symbol]
        ordered.append((symbol, isin, tuple(values)))
    return tuple(ordered)

@router.get("/connections/gnews",response_model=ConnectionProfileResponse)
def gnews_connection(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)): _require_local(settings);return _profile(service.gnews_profile(),service)
@router.put("/connections/gnews",response_model=ConnectionProfileResponse)
def update_gnews_connection(request:GNewsConnectionUpdateRequest,settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.update_gnews(request.credential_values()),service)
@router.post("/connections/gnews/test",response_model=ConnectionTestResponse)
def test_gnews_connection(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _result(service.test_gnews())
@router.delete("/connections/gnews/credentials",response_model=ConnectionProfileResponse)
def clear_gnews_connection_credentials(settings:APISettings=Depends(get_api_settings),service:ProviderConnectionService=Depends(get_connection_service)):
    _require_local(settings);return _profile(service.clear_gnews_credentials(),service)


def _profile(profile: ConnectionProfile, service: ProviderConnectionService) -> ConnectionProfileResponse:
    definitions = tuple(CredentialDefinitionResponse(field=item.field, label=item.label, sensitivity=item.sensitivity.value, secret=item.secret, required_for=tuple(mode.value for mode in item.required_for), description=item.description) for item in service.credential_definitions(profile.provider))
    store = service.credential_store_status()
    configured = dict(profile.credential_fields_configured)
    market_data_configured = configured.get("tradeapi_access_token") if profile.provider == "KOTAK_NEO" else None
    session_configured = (
        all(configured.get(field, False) for field in ("tradeapi_access_token", "mobile_number", "ucc", "mpin"))
        if profile.provider == "KOTAK_NEO" else None
    )
    return ConnectionProfileResponse(
        connection_id=profile.connection_id, provider=profile.provider, display_name=profile.display_name, enabled=profile.enabled,
        status=profile.status.value, created_at=profile.created_at, updated_at=profile.updated_at, last_tested_at=profile.last_tested_at,
        last_success_at=profile.last_success_at, last_error_code=profile.last_error_code,
        capabilities=tuple(item.value for item in profile.capabilities), credential_fields_configured=configured,
        tradeapi_access_token_configured=market_data_configured,
        market_data_configured=market_data_configured,
        session_configured=session_configured,
        credential_store_available=store.available, credential_store_backend=store.backend, credential_store_message=store.message,
        warnings=profile.warnings, credential_definitions=definitions,
    )


def _result(result: ConnectionTestResult) -> ConnectionTestResponse:
    return ConnectionTestResponse(provider=result.provider, connection_id=result.connection_id, status=result.status.value, quote_access=result.quote_access.value, session_read_access=result.session_read_access.value, instrument_resolution=result.instrument_resolution, tested_at=result.tested_at, mode=result.mode.value, test_symbol=result.test_symbol, canonical_normalization=result.canonical_normalization, freshness=result.freshness, warnings=result.warnings, error_code=result.error_code, message=result.message, market_data_auth=result.market_data_auth, session_totp_login=result.session_totp_login, session_mpin_validation=result.session_mpin_validation, ip_configuration=result.ip_configuration, validation_flow=dict(result.validation_flow) if result.validation_flow else None)
