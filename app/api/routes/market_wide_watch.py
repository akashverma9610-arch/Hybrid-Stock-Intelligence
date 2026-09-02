from fastapi import APIRouter, Depends

from app.api.dependencies import get_market_wide_watch_service
from app.api.errors import APIRequestError
from app.api.schemas.market_wide_watch import MarketWideWatchResponse


router = APIRouter(prefix="/market-wide-watch", tags=["market-wide-watch"])


@router.get("", response_model=MarketWideWatchResponse)
def latest_market_wide_watch(service=Depends(get_market_wide_watch_service)) -> MarketWideWatchResponse:
    """Read the latest immutable discovery snapshot; never starts a scan."""
    value = service.latest()
    if value is None:
        raise APIRequestError(
            status_code=503,
            code="MARKET_WIDE_WATCH_UNAVAILABLE",
            message="No Market-Wide Watch snapshot has been materialized.",
        )
    return MarketWideWatchResponse.model_validate(value, from_attributes=True)
