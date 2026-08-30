from fastapi.testclient import TestClient

from app.api.dependencies import get_feature_settings
from app.api.main import app, create_app
from app.api.schemas.system import HealthResponse, SystemStatusResponse, SystemVersionResponse
from app.api.settings import APISettings
from app.feature_settings import FeatureSettings


def test_application_factory_and_module_entry_point_are_lightweight():
    created = create_app()

    assert created.title == "NSE Stock Manager"
    assert app.title == "NSE Stock Manager"
    assert created.state.feature_settings.automated_self_improvement_research_enabled is False


def test_health_status_version_and_openapi_responses_are_typed_and_side_effect_free():
    application = create_app()
    with TestClient(application) as client:
        health = client.get("/health")
        status = client.get("/api/v1/system/status")
        version = client.get("/api/v1/system/version")
        openapi = client.get("/openapi.json")

    assert health.status_code == 200
    assert HealthResponse.model_validate(health.json()).status == "ok"
    assert status.status_code == 200
    response = SystemStatusResponse.model_validate(status.json())
    capability = response.feature_capabilities["automated_self_improvement_research"]
    assert (capability.enabled, capability.maturity, capability.status, capability.production_blocking) == (
        False, "EXPERIMENTAL", "DEFERRED", False,
    )
    assert version.status_code == 200
    assert SystemVersionResponse.model_validate(version.json()).api_version == "v1"
    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "NSE Stock Manager"


def test_feature_settings_dependency_can_be_overridden_without_running_research():
    application = create_app()
    application.dependency_overrides[get_feature_settings] = lambda: FeatureSettings(True)

    with TestClient(application) as client:
        response = client.get("/api/v1/system/status")

    assert response.status_code == 200
    assert response.json()["feature_capabilities"]["automated_self_improvement_research"]["enabled"] is True


def test_request_id_safe_error_envelope_and_unknown_route_behavior():
    application = create_app()

    def failing_route():
        raise RuntimeError(r"C:\sensitive\local-path")

    application.add_api_route("/_test/failing", failing_route)
    with TestClient(application, raise_server_exceptions=False) as client:
        supplied = client.get("/health", headers={"X-Request-ID": "known-request-1"})
        generated = client.get("/health", headers={"X-Request-ID": "unsafe space"})
        failure = client.get("/_test/failing")
        missing = client.get("/not-a-route")

    assert supplied.headers["x-request-id"] == "known-request-1"
    assert generated.headers["x-request-id"] != "unsafe space"
    assert failure.status_code == 500
    assert failure.json()["error"]["code"] == "INTERNAL_ERROR"
    assert r"C:\sensitive\local-path" not in failure.text
    assert failure.headers["x-request-id"] == failure.json()["error"]["request_id"]
    assert missing.status_code == 404


def test_configured_cors_allows_only_explicit_origin():
    application = create_app(api_settings=APISettings())
    with TestClient(application) as client:
        allowed = client.options(
            "/api/v1/system/status",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected = client.options(
            "/api/v1/system/status",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        loopback = client.options(
            "/api/v1/system/status",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert loopback.status_code == 200
    assert loopback.headers["access-control-allow-origin"] == "http://127.0.0.1:3000"
    assert "access-control-allow-credentials" not in loopback.headers
    assert rejected.status_code == 400


def test_settings_parse_explicit_environment_values_without_wildcard_default():
    settings = APISettings.from_environment(
        {
            "APP_ENV": "production",
            "APP_NAME": "NSE API",
            "API_VERSION": "v1",
            "CORS_ORIGINS": "https://app.example, https://ops.example",
        }
    )

    assert settings.environment == "production"
    assert settings.application_name == "NSE API"
    assert settings.cors_origins == ("https://app.example", "https://ops.example")
