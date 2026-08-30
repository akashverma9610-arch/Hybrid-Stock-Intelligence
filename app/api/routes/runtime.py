from fastapi import APIRouter, Depends

from app.api.dependencies import get_runtime_health_service
from app.api.schemas.runtime import RuntimeStatusResponse
from app.runtime.scheduler import RuntimeHealthService


router = APIRouter(tags=["runtime"])


@router.get("/runtime/status", response_model=RuntimeStatusResponse)
def runtime_status(service: RuntimeHealthService = Depends(get_runtime_health_service)) -> RuntimeStatusResponse:
    value = service.status()
    return RuntimeStatusResponse(
        scheduler_enabled=value.scheduler_enabled,
        scheduler_running=value.scheduler_running,
        runtime_mode=value.runtime_mode.value,
        universe_id=value.universe_id,
        last_cycle_id=value.last_cycle_id,
        last_cycle_status=value.last_cycle_status.value if value.last_cycle_status else None,
        last_started_at=value.last_started_at,
        last_completed_at=value.last_completed_at,
        last_success_at=value.last_success_at,
        last_failure_at=value.last_failure_at,
        last_data_as_of=value.last_data_as_of,
        consecutive_failures=value.consecutive_failures,
        warnings=value.warnings,
    )
