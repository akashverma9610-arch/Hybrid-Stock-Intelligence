"""Read-only portfolio query facade for the HTTP boundary."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from app.api.errors import APIRequestError
from app.api.schemas.portfolio import (
    LargestPositionResponse,
    LargestSectorResponse,
    PortfolioHoldingResponse,
    PortfolioResponse,
    PortfolioSummaryResponse,
)
from app.portfolio.models import PortfolioDataStatus, PortfolioSnapshot


class PortfolioQueryService(Protocol):
    """Application-facing read model; implementations must not mutate state."""

    def get_snapshot(self) -> PortfolioSnapshot: ...


class UnavailablePortfolioQueryService:
    """Safe default until a local application state source is configured."""

    def get_snapshot(self) -> PortfolioSnapshot:
        raise APIRequestError(
            status_code=503,
            code="PORTFOLIO_UNAVAILABLE",
            message="Portfolio data is not available.",
        )


class SnapshotPortfolioQueryService:
    """Read-only adapter for an existing immutable portfolio snapshot."""

    def __init__(self, snapshot: PortfolioSnapshot) -> None:
        self._snapshot = snapshot

    def get_snapshot(self) -> PortfolioSnapshot:
        return self._snapshot


def holding_response(snapshot: PortfolioSnapshot, holding) -> PortfolioHoldingResponse:
    warnings: list[str] = []
    if holding.market_value is None:
        warnings.append("MARK_UNAVAILABLE")
    if holding.sector == "UNKNOWN":
        warnings.append("SECTOR_UNKNOWN")
    return PortfolioHoldingResponse(
        instrument_id=holding.instrument_id,
        quantity=holding.quantity,
        average_price=holding.average_cost,
        market_price=holding.current_price,
        invested_value=holding.cost_basis,
        current_value=holding.market_value,
        unrealized_pnl=holding.unrealized_pnl,
        realized_pnl=holding.realized_pnl,
        weight=snapshot.exposure.position_allocations.get(holding.instrument_id),
        sector=holding.sector,
        data_as_of=snapshot.as_of_timestamp,
        warnings=tuple(warnings),
    )


def portfolio_response(snapshot: PortfolioSnapshot) -> PortfolioResponse:
    invested = sum((holding.cost_basis for holding in snapshot.holdings), Decimal("0"))
    marked_values = tuple(holding.market_value for holding in snapshot.holdings)
    marked = (
        sum((value for value in marked_values if value is not None), Decimal("0"))
        if all(value is not None for value in marked_values)
        else None
    )
    warnings = _snapshot_warnings(snapshot)
    return PortfolioResponse(
        portfolio_id=snapshot.portfolio_id,
        as_of=snapshot.as_of_timestamp,
        invested_value=invested,
        marked_value=marked,
        cash=snapshot.cash.amount,
        cash_status=snapshot.cash.cash_state.value,
        unrealized_pnl=snapshot.unrealized_pnl,
        realized_pnl=snapshot.realized_pnl,
        total_equity=snapshot.portfolio_equity,
        portfolio_heat=snapshot.risk.total_heat,
        holding_count=len(snapshot.holdings),
        data_status=snapshot.data_status.value,
        warnings=warnings,
    )


def portfolio_summary_response(snapshot: PortfolioSnapshot) -> PortfolioSummaryResponse:
    base = portfolio_response(snapshot)
    allocations = {
        instrument: weight
        for instrument, weight in snapshot.exposure.position_allocations.items()
        if weight is not None
    }
    sectors = {
        sector: weight
        for sector, weight in snapshot.exposure.sector_exposure.items()
        if weight is not None
    }
    largest_position = (
        LargestPositionResponse(instrument_id=max(allocations, key=allocations.__getitem__), weight=max(allocations.values()))
        if allocations else None
    )
    largest_sector = (
        LargestSectorResponse(sector=max(sectors, key=sectors.__getitem__), weight=max(sectors.values()))
        if sectors else None
    )
    return PortfolioSummaryResponse(
        **base.model_dump(),
        largest_position=largest_position,
        largest_sector_exposure=largest_sector,
    )


def _snapshot_warnings(snapshot: PortfolioSnapshot) -> tuple[str, ...]:
    warnings: list[str] = []
    if snapshot.data_status is not PortfolioDataStatus.COMPLETE:
        warnings.append(f"PORTFOLIO_DATA_STATUS:{snapshot.data_status.value}")
    if snapshot.risk.total_heat is None:
        warnings.append("PORTFOLIO_HEAT_UNAVAILABLE")
    if snapshot.cash.amount is None:
        warnings.append("CASH_UNKNOWN")
    if any(holding.market_value is None for holding in snapshot.holdings):
        warnings.append("MARK_DATA_PARTIAL")
    return tuple(warnings)
