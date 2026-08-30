from datetime import datetime

from fastapi import APIRouter, Depends

from app.api.dependencies import get_shared_brain_application_service, get_stock_analysis_query_service
from app.api.errors import APIRequestError
from app.api.schemas.stocks import StockAnalysisResponse, StockListResponse
from app.api.schemas.shared_brain import SharedBrainAnalysisResponse
from app.api.shared_brain_query import shared_brain_analysis_response
from app.api.stock_query import StockAnalysisQueryService, normalize_stock_symbol, stock_analysis_response, stock_list_response
from app.intelligence.shared_brain_application import SharedBrainApplicationError, SharedBrainApplicationService
from app.intelligence.unified_state import BrainOutputContext


router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("", response_model=StockListResponse)
def stocks(service: StockAnalysisQueryService = Depends(get_stock_analysis_query_service)) -> StockListResponse:
    """Read existing persisted stock-analysis summaries only; no scan or analysis run."""
    return stock_list_response(service.list_analysis())


@router.get("/{symbol}/analysis", response_model=StockAnalysisResponse)
def stock_analysis(
    symbol: str,
    service: StockAnalysisQueryService = Depends(get_stock_analysis_query_service),
) -> StockAnalysisResponse:
    return stock_analysis_response(service.get_analysis(normalize_stock_symbol(symbol)))


@router.get("/{symbol}/shared-brain", response_model=SharedBrainAnalysisResponse)
def shared_brain_analysis(
    symbol: str,
    context: BrainOutputContext = BrainOutputContext.DEEP_ANALYSIS,
    as_of: datetime | None = None,
    service: SharedBrainApplicationService = Depends(get_shared_brain_application_service),
) -> SharedBrainAnalysisResponse:
    """Read one stored-evidence Shared Brain projection; no scan, write, or provider call."""
    try:
        return shared_brain_analysis_response(service.analyze_stock(symbol, context=context, as_of=as_of))
    except SharedBrainApplicationError as error:
        status = 404 if error.code == "SHARED_BRAIN_INSTRUMENT_NOT_FOUND" else 422 if error.code.endswith("REQUIRED") or error.code.endswith("INVALID") else 503
        raise APIRequestError(status_code=status, code=error.code, message=error.message) from error
