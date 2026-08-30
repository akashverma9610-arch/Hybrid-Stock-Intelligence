from datetime import UTC, datetime
import inspect

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.data_sources.models import (
    DataFamily, DataRequirement, PointInTimeCapability, SourceReadinessStatus,
    SourceValidationState,
)
from app.data_sources.service import (
    DataSourceCompositionService, DataSourceRegistry, SourceCompositionSettings,
    standard_source_definitions,
)
from app.runtime.cycle import RuntimeMode


T = datetime(2026, 8, 26, 10, tzinfo=UTC)


def service(priorities=(), states=()):
    registry = DataSourceRegistry(standard_source_definitions())
    for family, values in priorities:
        registry.set_priority(family, values)
    return DataSourceCompositionService(registry, dict(states), clock=lambda: T)


def test_capability_catalog_includes_each_data_family_and_kotak_has_no_historical_claim():
    definitions = {value.source_id: value for value in standard_source_definitions()}
    assert all(isinstance(family, DataFamily) for family in DataFamily)
    kotak = definitions["kotak_neo"]
    historical = kotak.capability_for(DataFamily.HISTORICAL_OHLCV)
    assert historical.point_in_time is PointInTimeCapability.UNSUPPORTED
    assert "NO_DOCUMENTED_KOTAK_HISTORICAL_CONTRACT" in historical.warnings
    assert kotak.capability_for(DataFamily.CURRENT_QUOTES) is not None


def test_priority_is_explicit_and_never_chooses_mock_when_not_listed():
    value = service(
        ((DataFamily.CURRENT_QUOTES, ("kotak_neo", "mock")),),
        (("kotak_neo", SourceValidationState(configured=True, validated=False)), ("mock", SourceValidationState(configured=True, validated=True))),
    )
    report = value.readiness(mode=RuntimeMode.MOCK)
    rows = report.for_family(DataFamily.CURRENT_QUOTES)
    assert [(row.source_id, row.priority, row.status) for row in rows] == [
        ("kotak_neo", 1, SourceReadinessStatus.CONFIGURED_NOT_VALIDATED),
        ("mock", 2, SourceReadinessStatus.READY),
    ]
    no_mock = service(((DataFamily.CURRENT_QUOTES, ("kotak_neo",)),), (("kotak_neo", SourceValidationState(configured=False)),)).readiness()
    assert [row.source_id for row in no_mock.for_family(DataFamily.CURRENT_QUOTES)] == ["kotak_neo"]


def test_readiness_states_stored_data_and_provenance_are_retained_without_fetching():
    value = service(
        ((DataFamily.HISTORICAL_OHLCV, ("stored_data",)), (DataFamily.INDEX_DATA, ("kotak_neo",))),
        (("stored_data", SourceValidationState(configured=True, validated=True)), ("kotak_neo", SourceValidationState(configured=True, validated=True, degraded=True, warnings=("STALE_VALIDATION",)))),
    )
    report = value.readiness()
    historical = report.primary(DataFamily.HISTORICAL_OHLCV)
    index = report.primary(DataFamily.INDEX_DATA)
    assert historical.status is SourceReadinessStatus.READY and historical.provider == "local_store"
    assert historical.provenance.family is DataFamily.HISTORICAL_OHLCV
    assert historical.freshness_policy.basis.value == "COMPLETED_SESSION"
    assert index.status is SourceReadinessStatus.DEGRADED and index.last_success_at is None


def test_unavailable_source_retains_safe_failure_classification():
    value = service(
        ((DataFamily.CURRENT_QUOTES, ("kotak_neo",)),),
        (("kotak_neo", SourceValidationState(configured=True, validated=True, unavailable=True, last_failure_classification="AUTHENTICATION_UNAVAILABLE")),),
    )
    row = value.readiness().primary(DataFamily.CURRENT_QUOTES)
    assert row.status is SourceReadinessStatus.UNAVAILABLE
    assert row.last_failure_classification == "AUTHENTICATION_UNAVAILABLE"


def test_missing_optional_sources_remain_visible_and_runtime_composition_fails_closed_for_critical_inputs():
    value = service()
    report = value.readiness()
    assert report.primary(DataFamily.FUNDAMENTALS).status is SourceReadinessStatus.MISSING_CONFIGURATION
    assert report.primary(DataFamily.NEWS_RESEARCH).requirement is DataRequirement.OPTIONAL
    runtime = value.runtime_readiness(mode=RuntimeMode.STORED_DATA)
    assert runtime.executable is False
    assert set(runtime.critical_unavailable) == {DataFamily.CURRENT_QUOTES, DataFamily.UNIVERSE_MEMBERSHIP}
    assert DataFamily.FUNDAMENTALS in runtime.optional_unavailable


def test_environment_settings_keep_mock_explicit_and_kotak_unvalidated_until_external_validation():
    mock = DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER": "mock"}), clock=lambda: T).readiness(mode=RuntimeMode.MOCK)
    assert mock.primary(DataFamily.CURRENT_QUOTES).status is SourceReadinessStatus.READY
    assert mock.warnings == ("MOCK_MODE_IS_EXPLICIT",)
    stored = DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER": "mock"}), clock=lambda: T).readiness(mode=RuntimeMode.STORED_DATA)
    assert stored.primary(DataFamily.CURRENT_QUOTES).status is SourceReadinessStatus.UNAVAILABLE
    assert "MOCK_SOURCE_REQUIRES_MOCK_MODE" in stored.primary(DataFamily.CURRENT_QUOTES).warnings
    kotak = DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER": "kotak_neo"}), clock=lambda: T).readiness()
    assert kotak.primary(DataFamily.CURRENT_QUOTES).status is SourceReadinessStatus.CONFIGURED_NOT_VALIDATED
    assert kotak.primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.UNSUPPORTED


def test_read_only_api_status_is_sanitized_and_has_no_control_or_network_side_effects():
    value = service(((DataFamily.CURRENT_QUOTES, ("kotak_neo",)),), (("kotak_neo", SourceValidationState(True, False, warnings=("VALIDATION_PENDING",))),))
    with TestClient(create_app(data_source_composition_service=value)) as client:
        result = client.get("/api/v1/data-sources/status")
        control = client.post("/api/v1/data-sources/status")
    assert result.status_code == 200 and result.json()["items"][0]["source_id"] == "kotak_neo"
    assert "consumer_key" not in result.text.lower() and control.status_code == 405
    import app.data_sources.service as module
    source = inspect.getsource(module).lower()
    assert not any(token in source for token in ("requests.", "websocket", "place_order", "demat", "promotion", "activation"))
