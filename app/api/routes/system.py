from fastapi import APIRouter, Depends

from app.api.dependencies import get_api_settings, get_feature_settings
from app.api.schemas.system import (
    FeatureCapabilityResponse,
    HealthResponse,
    SystemStatusResponse,
    SystemVersionResponse,
)
from app.api.settings import APISettings
from app.feature_settings import FeatureSettings


health_router = APIRouter()
router = APIRouter(tags=["system"])


@health_router.get("/health", response_model=HealthResponse, include_in_schema=False)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status(
    api_settings: APISettings = Depends(get_api_settings),
    feature_settings: FeatureSettings = Depends(get_feature_settings),
) -> SystemStatusResponse:
    capabilities = {
        key: FeatureCapabilityResponse(
            enabled=value.enabled,
            maturity=value.maturity.value,
            status=value.lifecycle_status.value,
            production_blocking=value.production_blocking,
        )
        for key, value in feature_settings.capability_statuses().items()
    }
    return SystemStatusResponse(
        application_status="ok",
        application_name=api_settings.application_name,
        environment=api_settings.environment,
        api_version=api_settings.api_version,
        feature_capabilities=capabilities,
    )


@router.get("/system/version", response_model=SystemVersionResponse)
def system_version(api_settings: APISettings = Depends(get_api_settings)) -> SystemVersionResponse:
    return SystemVersionResponse(
        application_name=api_settings.application_name,
        api_version=api_settings.api_version,
        application_version=api_settings.application_version,
        environment=api_settings.environment,
    )
