"""Authenticated pilot-only canonical read facade; no runtime work is started."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import AwareDatetime

from app.api.errors import APIRequestError
from app.api.pilot_canonical_query import CanonicalQueryResponse, PilotCanonicalQueryService


router = APIRouter(prefix="/api/v1/pilot/canonical", tags=["pilot-canonical"])


def _read(request, response, surface, as_of, instrument_id=None):
    now = datetime.now(UTC)
    cutoff = as_of or now
    if cutoff > now:
        raise APIRequestError(status_code=422, code="CANONICAL_FUTURE_CUTOFF_REJECTED", message="A future query cutoff is not permitted.")
    service = PilotCanonicalQueryService(request.app.state.core_api_snapshot_repository)
    value = service.read(surface, as_of=cutoff, instrument_id=instrument_id)
    if value.status == "UNAVAILABLE":
        response.status_code = 503
    return value


@router.get("/{surface}", response_model=CanonicalQueryResponse)
def shared(surface: Literal["market", "sectors", "opportunities"], request: Request,
           response: Response, as_of: AwareDatetime | None = None):
    return _read(request, response, surface, as_of)


@router.get("/stocks/{instrument_id}", response_model=CanonicalQueryResponse)
def stock(instrument_id: str, request: Request, response: Response, as_of: AwareDatetime | None = None):
    if not instrument_id.startswith("NSE:") or len(instrument_id) > 128:
        raise APIRequestError(status_code=422, code="CANONICAL_INSTRUMENT_ID_REQUIRED", message="An exact canonical NSE instrument ID is required.")
    return _read(request, response, "stocks", as_of, instrument_id)
