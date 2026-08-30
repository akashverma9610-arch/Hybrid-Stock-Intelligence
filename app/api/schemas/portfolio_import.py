from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ExtractedHoldingCandidateResponse(BaseModel):
    row_id: str
    symbol: str | None
    instrument_name: str | None
    quantity: Decimal | None
    average_price: Decimal | None
    current_price: Decimal | None
    invested_value: Decimal | None
    current_value: Decimal | None
    pnl: Decimal | None
    pnl_percent: Decimal | None
    extraction_confidence: Decimal | None
    field_warnings: tuple[str, ...]
    source_image_index: int
    resolution_status: str
    instrument_id: str | None


class PortfolioScreenshotImportResponse(BaseModel):
    import_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    image_count: int
    warnings: tuple[str, ...]
    holdings: tuple[ExtractedHoldingCandidateResponse, ...]


class ReviewedHoldingRequest(BaseModel):
    row_id: str
    instrument_id: str | None = None
    symbol: str | None = None
    quantity: Decimal | None = None
    average_price: Decimal | None = None
    include: bool = True


class PortfolioImportConfirmRequest(BaseModel):
    mode: str = Field(pattern="^(REPLACE|MERGE)$")
    holdings: tuple[ReviewedHoldingRequest, ...]


class PortfolioImportConfirmationResponse(BaseModel):
    status: str
    portfolio_id: str
    portfolio_snapshot_id: str
    holdings_imported: int
    warnings: tuple[str, ...]
    data_as_of: datetime
