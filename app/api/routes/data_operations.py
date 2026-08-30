"""Read-only operational evidence health; this route never starts a refresh."""
from fastapi import APIRouter, Depends

from app.api.dependencies import get_data_operations_service
from app.api.schemas.data_operations import DataOperationsFamilyHealthResponse, DataOperationsHealthResponse, DataOperationsRunResponse
from app.data_operations.service import DataOperationsService


router = APIRouter(tags=["data-operations"])


def _run(value) -> DataOperationsRunResponse | None:
    if value is None:
        return None
    return DataOperationsRunResponse(
        run_id=value.run_id, family=value.family.value, mode=value.mode.value, status=value.status.value,
        completed_at=value.completed_at, accepted_count=value.accepted_count, duplicate_count=value.duplicate_count,
        conflict_count=value.conflict_count, rejected_count=value.rejected_count, gap_count=value.gap_count,
        warnings=value.warnings,
    )


@router.get("/data-operations/health", response_model=DataOperationsHealthResponse)
def data_operations_health(service: DataOperationsService = Depends(get_data_operations_service)) -> DataOperationsHealthResponse:
    value = service.health()
    return DataOperationsHealthResponse(
        generated_at=value.generated_at,
        families=tuple(
            DataOperationsFamilyHealthResponse(
                family=item.family.value, status=item.status.value, last_run=_run(item.last_run),
                next_due_at=item.next_due_at, reasons=item.reasons,
            ) for item in value.families
        ),
    )
