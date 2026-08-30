from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PortfolioHoldingResponse(BaseModel):
    instrument_id: str
    symbol: str | None = None
    exchange: str | None = None
    quantity: Decimal
    average_price: Decimal
    market_price: Decimal | None
    invested_value: Decimal
    current_value: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    weight: Decimal | None
    sector: str | None
    data_as_of: datetime
    warnings: tuple[str, ...]


class PortfolioResponse(BaseModel):
    portfolio_id: str
    as_of: datetime
    invested_value: Decimal
    marked_value: Decimal | None
    cash: Decimal
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal
    total_equity: Decimal | None
    portfolio_heat: Decimal | None
    holding_count: int
    data_status: str
    warnings: tuple[str, ...]


class LargestPositionResponse(BaseModel):
    instrument_id: str
    weight: Decimal | None


class LargestSectorResponse(BaseModel):
    sector: str
    weight: Decimal | None


class PortfolioSummaryResponse(PortfolioResponse):
    largest_position: LargestPositionResponse | None
    largest_sector_exposure: LargestSectorResponse | None
