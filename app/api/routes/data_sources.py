from fastapi import APIRouter, Depends

from app.api.dependencies import get_data_source_composition_service
from app.api.schemas.data_sources import DataSourceFreshnessResponse, DataSourceReadinessResponse, DataSourceStatusResponse
from app.data_sources.service import DataSourceCompositionService
from app.runtime.cycle import RuntimeMode


router = APIRouter(tags=["data sources"])


@router.get("/data-sources/status", response_model=DataSourceStatusResponse)
def data_source_status(service: DataSourceCompositionService = Depends(get_data_source_composition_service)) -> DataSourceStatusResponse:
    report = service.readiness(mode=RuntimeMode.STORED_DATA)
    return DataSourceStatusResponse(
        generated_at=report.generated_at,
        mode=report.mode,
        warnings=report.warnings,
        items=tuple(
            DataSourceReadinessResponse(
                source_id=item.source_id, provider=item.provider, family=item.family.value,
                requirement=item.requirement.value, priority=item.priority, status=item.status.value,
                configured=item.configured, validated=item.validated,
                last_success_at=item.last_success_at, last_failure_classification=item.last_failure_classification,
                freshness=DataSourceFreshnessResponse(
                    basis=item.freshness_policy.basis.value,
                    maximum_age_seconds=item.freshness_policy.maximum_age.total_seconds() if item.freshness_policy.maximum_age else None,
                    policy_version=item.freshness_policy.policy_version,
                ),
                point_in_time=item.point_in_time.value, adjustment=item.adjustment.value,
                warnings=item.warnings,
            ) for item in report.items
        ),
    )
