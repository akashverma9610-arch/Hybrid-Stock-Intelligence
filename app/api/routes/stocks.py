from datetime import datetime
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_dhan_live_market_runtime, get_shared_brain_application_service, get_stock_analysis_query_service
from app.api.errors import APIRequestError
from app.api.schemas.stocks import StockAnalysisResponse, StockListResponse
from app.api.schemas.shared_brain import SharedBrainAnalysisResponse
from app.api.schemas.decision_trust import DecisionTrustEnvelopeResponse
from app.api.schemas.dhan_live import DhanLiveHealthResponse, DhanLiveQuoteResponse, DhanStockLiveMarketResponse
from app.api.shared_brain_query import shared_brain_analysis_response
from app.api.stock_query import StockAnalysisQueryService, normalize_stock_symbol, stock_analysis_response, stock_list_response
from app.intelligence.shared_brain_application import SharedBrainApplicationError, SharedBrainApplicationService
from app.intelligence.unified_state import BrainOutputContext
from app.intelligence.decision_trust_envelope import decision_trust_envelope_from_shared_brain
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore


router = APIRouter(prefix="/stocks", tags=["stocks"])


@dataclass(frozen=True, slots=True)
class _HoldingAnalyticsTrustRead:
    analytics: object
    blockers: tuple[str, ...] = ()


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


@router.get("/{symbol}/live-market", response_model=DhanStockLiveMarketResponse)
def stock_live_market(symbol: str, runtime=Depends(get_dhan_live_market_runtime)) -> DhanStockLiveMarketResponse:
    """Read one exact canonical live observation; no alias resolution occurs here."""
    if ":" not in symbol:
        raise APIRequestError(status_code=422, code="LIVE_CANONICAL_ID_REQUIRED", message="A canonical instrument ID is required for live market observations.")
    value = runtime.quote(symbol)
    return DhanStockLiveMarketResponse(
        canonical_instrument_id=symbol,
        health=DhanLiveHealthResponse.model_validate(runtime.health(), from_attributes=True),
        quote=None if value is None else DhanLiveQuoteResponse.model_validate(value, from_attributes=True),
    )


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


@router.get("/{symbol}/decision-trust-envelope", response_model=DecisionTrustEnvelopeResponse)
def decision_trust_envelope(
    symbol: str,
    request: Request,
    context: BrainOutputContext = BrainOutputContext.DEEP_ANALYSIS,
    as_of: datetime | None = None,
    service: SharedBrainApplicationService = Depends(get_shared_brain_application_service),
):
    """Read stored decision artifacts only; this route has no execution authority."""
    try:
        brain = service.analyze_stock(symbol, context=context, as_of=as_of)
        governance = getattr(request.app.state, "decision_score_governance_repository", None)
        score = _latest_score(governance, brain.canonical_instrument_id, brain.as_of)
        gates = _latest_gates(governance, brain.canonical_instrument_id, brain.as_of)
        policy = None if governance is None else governance.selected_six_gates_production_policy(as_of=brain.as_of)
        repository = getattr(request.app.state, "core_api_snapshot_repository", None)
        setup = _latest_setup(repository, brain.canonical_instrument_id, brain.as_of)
        holding_intelligence = _holding_intelligence(request, brain.canonical_instrument_id, brain.as_of)
        value = decision_trust_envelope_from_shared_brain(
            brain,
            decision_scorecard=score,
            setup_opportunity=setup,
            six_gates_evaluation=gates,
            six_gates_policy=policy,
            holding_intelligence=holding_intelligence,
        )
        return DecisionTrustEnvelopeResponse.model_validate(value, from_attributes=True)
    except SharedBrainApplicationError as error:
        status = 404 if error.code == "SHARED_BRAIN_INSTRUMENT_NOT_FOUND" else 503
        raise APIRequestError(status_code=status, code=error.code, message=error.message) from error


def _latest_score(governance, instrument_id: str, as_of: datetime):
    if governance is None:
        return None
    values = tuple(
        item for item in governance.list_canonical_decision_scorecards(instrument_id)
        if item.as_of_timestamp <= as_of and item.evaluated_at <= as_of
    )
    return max(values, key=lambda item: (item.as_of_timestamp, item.evaluated_at, item.id), default=None)


def _latest_gates(governance, instrument_id: str, as_of: datetime):
    if governance is None:
        return None
    values = tuple(
        item for item in governance.list_canonical_execution_gate_evaluations(instrument_id)
        if item.as_of_timestamp <= as_of and item.evaluated_at <= as_of
    )
    return max(values, key=lambda item: (item.as_of_timestamp, item.evaluated_at, item.id), default=None)


def _latest_setup(repository, instrument_id: str, as_of: datetime):
    if repository is None:
        return None
    values = CanonicalSetupOpportunityStore(repository).list(
        as_of=as_of, canonical_instrument_id=instrument_id,
    )
    return max(values, key=lambda item: (item.decision_as_of, item.opportunity_id), default=None)


def _holding_intelligence(request: Request, instrument_id: str, as_of: datetime):
    """Expose only existing PIT-eligible holding analytics, never recomposition."""
    service = getattr(request.app.state, "portfolio_query_service", None)
    if service is None:
        return None
    try:
        snapshot = service.get_snapshot()
    except APIRequestError:
        return None
    if snapshot.as_of_timestamp > as_of:
        return None
    holding = next((item for item in snapshot.holdings if item.instrument_id == instrument_id), None)
    if holding is None or holding.analytics is None or holding.analytics.known_at > as_of:
        return None
    return _HoldingAnalyticsTrustRead(analytics=holding.analytics)
