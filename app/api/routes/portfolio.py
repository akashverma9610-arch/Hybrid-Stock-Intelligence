from fastapi import APIRouter, Depends

from app.api.errors import APIRequestError
from app.api.schemas.sell_side import SellSideHoldingDecisionResponse, SellSidePortfolioResponse
from app.portfolio.sell_side_policy import CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY
from app.portfolio.sell_side_runtime import PortfolioSellSideDecision
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily

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


@router.get("/sell-side", response_model=SellSidePortfolioResponse)
def sell_side(service: PortfolioQueryService = Depends(get_portfolio_query_service)) -> SellSidePortfolioResponse:
    """Read persisted sell-side decisions only; no evaluation or mutation occurs here."""
    try:
        snapshot = service.get_snapshot()
    except APIRequestError:
        return SellSidePortfolioResponse(
            status="NO_CURRENT_CANONICAL_PORTFOLIO", portfolio_snapshot_id=None,
            policy_fingerprint=CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY.fingerprint,
            decisions=(), warnings=("NO_CURRENT_CANONICAL_PORTFOLIO",),
        )
    repository = getattr(service, "_repository", None)
    decisions = ()
    if repository is not None:
        decisions = tuple(
            item.payload for item in repository.list_snapshots(CoreApiSnapshotFamily.SELL_SIDE_DECISION)
            if isinstance(item.payload, PortfolioSellSideDecision) and item.payload.portfolio_snapshot_id == snapshot.snapshot_id
        )
    return SellSidePortfolioResponse(
        status="READY" if decisions else "NO_PERSISTED_SELL_SIDE_DECISIONS",
        portfolio_snapshot_id=snapshot.snapshot_id,
        policy_fingerprint=CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY.fingerprint,
        decisions=tuple(SellSideHoldingDecisionResponse(
            holding_id=item.canonical_holding_id, as_of=item.as_of, action=item.action.value,
            thesis_state=item.thesis_state.value,
            capital_efficiency_state=None if item.capital_efficiency_state is None else item.capital_efficiency_state.value,
            rotation_state=None if item.rotation_state is None else item.rotation_state.value,
            reasons=item.reasons, blockers=item.blockers, evidence_freshness=item.evidence_freshness.value,
            policy_fingerprint=item.policy_fingerprint,
        ) for item in decisions),
        warnings=() if decisions else ("SELL_SIDE_DECISIONS_UNAVAILABLE",),
    )
