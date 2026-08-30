from fastapi import APIRouter, Depends

from app.api.dependencies import get_breadth_query_service, get_crisis_query_service, get_market_extremes_query_service, get_market_regime_query_service, get_sector_query_service
from app.api.market_context_query import BreadthQueryService, CrisisQueryService, MarketExtremesQueryService, breadth_response, crisis_response, extremes_response
from app.api.market_query import (
    MarketRegimeQueryService,
    SectorQueryService,
    market_regime_response,
    sector_response,
)
from app.api.schemas.market import BreadthResponse, CrisisResponse, MarketExtremesResponse, MarketRegimeResponse, SectorListResponse, SectorResponse


market_router = APIRouter(prefix="/market", tags=["market"])
sector_router = APIRouter(prefix="/sectors", tags=["sectors"])


@market_router.get("/regime", response_model=MarketRegimeResponse)
def market_regime(service: MarketRegimeQueryService = Depends(get_market_regime_query_service)) -> MarketRegimeResponse:
    return market_regime_response(service.get_market_regime())


@market_router.get("/breadth", response_model=BreadthResponse)
def market_breadth(service: BreadthQueryService = Depends(get_breadth_query_service)) -> BreadthResponse:
    return breadth_response(service.get_breadth())


@market_router.get("/extremes", response_model=MarketExtremesResponse)
def market_extremes(service: MarketExtremesQueryService = Depends(get_market_extremes_query_service)) -> MarketExtremesResponse:
    return extremes_response(service.get_extremes())


@market_router.get("/crisis", response_model=CrisisResponse)
def market_crisis(service: CrisisQueryService = Depends(get_crisis_query_service)) -> CrisisResponse:
    return crisis_response(service.get_crisis())


@sector_router.get("", response_model=SectorListResponse)
def sectors(service: SectorQueryService = Depends(get_sector_query_service)) -> SectorListResponse:
    return SectorListResponse(sectors=tuple(sector_response(value) for value in service.list_sectors()))


@sector_router.get("/{sector_id}", response_model=SectorResponse)
def sector_detail(sector_id: str, service: SectorQueryService = Depends(get_sector_query_service)) -> SectorResponse:
    return sector_response(service.get_sector(sector_id))
