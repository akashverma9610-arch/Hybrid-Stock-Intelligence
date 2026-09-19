"""Separate P1 read endpoint; legacy /signals remains unchanged."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.api.p1_signal_lifecycle_query import P1SignalLifecycleQueryService
from app.api.schemas.p1_signal_lifecycle import P1LifecycleQuery, P1LifecycleResponse


router = APIRouter(prefix="/p1-signals", tags=["p1-signal-lifecycle"])


def get_p1_lifecycle_query_service(request: Request) -> P1SignalLifecycleQueryService:
    return P1SignalLifecycleQueryService(request.app.state.database_settings)


@router.get("/lifecycle", response_model=P1LifecycleResponse)
def lifecycle(
    query: Annotated[P1LifecycleQuery, Query()],
    service: Annotated[P1SignalLifecycleQueryService, Depends(get_p1_lifecycle_query_service)],
) -> P1LifecycleResponse:
    """Explicit PIT cutoff; CURRENT is last confirmed, not executable or live."""
    return service.read(query)
