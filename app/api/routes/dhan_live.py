from fastapi import APIRouter, Depends
from app.api.dependencies import get_dhan_live_market_runtime
from app.api.errors import APIRequestError
from app.api.schemas.dhan_live import (
    DhanLiveHealthResponse, DhanLiveOverviewResponse, DhanLiveQuoteResponse,
    DhanLiveSetupMonitorResponse, DhanLiveTargetResponse,
)

router = APIRouter(prefix="/live-market", tags=["live-market"])

@router.get("/health", response_model=DhanLiveHealthResponse)
def health(runtime=Depends(get_dhan_live_market_runtime)):
    return DhanLiveHealthResponse.model_validate(runtime.health(), from_attributes=True)


@router.get("", response_model=DhanLiveOverviewResponse)
def overview(runtime=Depends(get_dhan_live_market_runtime)):
    monitors = runtime.setup_monitors()
    return DhanLiveOverviewResponse(
        health=DhanLiveHealthResponse.model_validate(runtime.health(), from_attributes=True),
        targets=tuple(DhanLiveTargetResponse.model_validate(item, from_attributes=True) for item in runtime.targets()),
        setup_monitoring=tuple(
            DhanLiveSetupMonitorResponse.model_validate(item, from_attributes=True)
            for item in monitors
        ),
        setup_state="NO_ACTIVE_SETUP" if not monitors else "ACTIVE_SETUP_MONITORING",
    )

@router.get("/quotes/{canonical_instrument_id}", response_model=DhanLiveQuoteResponse)
def quote(canonical_instrument_id: str, runtime=Depends(get_dhan_live_market_runtime)):
    value = runtime.quote(canonical_instrument_id)
    if value is None:
        raise APIRequestError(status_code=404, code="LIVE_QUOTE_UNAVAILABLE", message="No fresh or stale live quote is available for this canonical instrument.")
    return DhanLiveQuoteResponse.model_validate(value, from_attributes=True)
