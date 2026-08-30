"""Read-only signal and simulated paper-trade HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_paper_trade_query_service, get_signal_query_service
from app.api.schemas.signals import (
    PaperTradeListResponse,
    PaperTradePerformanceResponse,
    PaperTradeResponse,
    SignalListResponse,
    SignalResponse,
)
from app.api.signal_paper_query import (
    PaperTradeQueryService,
    SignalQueryService,
    paper_performance_response,
    paper_trade_response,
    signal_response,
)


router = APIRouter(tags=["signals", "paper-trades"])
_Limit = Annotated[int, Query(ge=1, le=100)]
_Offset = Annotated[int, Query(ge=0)]


@router.get("/signals", response_model=SignalListResponse)
def signals(symbol: str | None = None, status: str | None = None, strategy_version: str | None = None, limit: _Limit = 50, offset: _Offset = 0, service: SignalQueryService = Depends(get_signal_query_service)) -> SignalListResponse:
    values = service.list_signals(symbol=symbol, status=status, strategy_version=strategy_version)
    return SignalListResponse(items=tuple(signal_response(value) for value in values[offset:offset + limit]), total=len(values), limit=limit, offset=offset)


@router.get("/signals/{signal_id}", response_model=SignalResponse)
def signal_detail(signal_id: str, service: SignalQueryService = Depends(get_signal_query_service)) -> SignalResponse:
    return signal_response(service.get_signal(signal_id))


@router.get("/paper-trades/performance", response_model=PaperTradePerformanceResponse)
def paper_trade_performance(strategy_version: str | None = None, service: PaperTradeQueryService = Depends(get_paper_trade_query_service)) -> PaperTradePerformanceResponse:
    return paper_performance_response(service.get_performance(strategy_version=strategy_version))


@router.get("/paper-trades", response_model=PaperTradeListResponse)
def paper_trades(symbol: str | None = None, status: str | None = None, strategy_version: str | None = None, limit: _Limit = 50, offset: _Offset = 0, service: PaperTradeQueryService = Depends(get_paper_trade_query_service)) -> PaperTradeListResponse:
    values = service.list_paper_trades(symbol=symbol, status=status, strategy_version=strategy_version)
    return PaperTradeListResponse(items=tuple(paper_trade_response(value) for value in values[offset:offset + limit]), total=len(values), limit=limit, offset=offset)


@router.get("/paper-trades/{trade_id}", response_model=PaperTradeResponse)
def paper_trade_detail(trade_id: str, service: PaperTradeQueryService = Depends(get_paper_trade_query_service)) -> PaperTradeResponse:
    return paper_trade_response(service.get_paper_trade(trade_id))
