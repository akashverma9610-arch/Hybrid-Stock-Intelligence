from fastapi import APIRouter, Depends, Query

from app.api.capital_rotation_query import CapitalRotationQueryService
from app.api.dependencies import get_capital_rotation_query_service
from app.api.schemas.capital_rotation import CapitalRotationResponse


router = APIRouter(prefix="/capital-rotation", tags=["capital-rotation"])


@router.get("", response_model=CapitalRotationResponse)
def capital_rotation(
    holding_symbol: str | None = Query(default=None, min_length=1),
    candidate_symbol: str | None = Query(default=None, min_length=1),
    limit: int | None = Query(default=None, ge=1, le=100),
    service: CapitalRotationQueryService = Depends(get_capital_rotation_query_service),
) -> CapitalRotationResponse:
    """Return an existing distilled analytical comparison; it has no execution path."""
    return service.get_rotation(holding_symbol=holding_symbol, candidate_symbol=candidate_symbol, limit=limit)
