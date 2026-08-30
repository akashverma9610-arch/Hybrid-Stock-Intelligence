from fastapi import APIRouter, Depends

from app.api.dependencies import get_portfolio_query_service
from app.api.portfolio_query import (
    PortfolioQueryService,
    holding_response,
    portfolio_response,
    portfolio_summary_response,
)
from app.api.schemas.portfolio import (
    PortfolioHoldingResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
)


router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioResponse)
def portfolio(service: PortfolioQueryService = Depends(get_portfolio_query_service)) -> PortfolioResponse:
    return portfolio_response(service.get_snapshot())


@router.get("/holdings", response_model=list[PortfolioHoldingResponse])
def holdings(service: PortfolioQueryService = Depends(get_portfolio_query_service)) -> list[PortfolioHoldingResponse]:
    snapshot = service.get_snapshot()
    return [holding_response(snapshot, holding) for holding in snapshot.holdings]


@router.get("/summary", response_model=PortfolioSummaryResponse)
def summary(service: PortfolioQueryService = Depends(get_portfolio_query_service)) -> PortfolioSummaryResponse:
    return portfolio_summary_response(service.get_snapshot())
