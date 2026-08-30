from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ImportStatus(StrEnum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class SymbolResolutionStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


@dataclass(frozen=True, slots=True)
class UploadedScreenshot:
    """Ephemeral upload passed to an extractor only; never persisted."""

    image_index: int
    filename: str
    content_type: str
    content: bytes


@dataclass(frozen=True, slots=True)
class ExtractedHoldingCandidate:
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
    resolution_status: SymbolResolutionStatus = SymbolResolutionStatus.UNMATCHED
    instrument_id: str | None = None


@dataclass(frozen=True, slots=True)
class PortfolioImportDraft:
    import_id: str
    status: ImportStatus
    created_at: datetime
    expires_at: datetime
    image_count: int
    warnings: tuple[str, ...]
    holdings: tuple[ExtractedHoldingCandidate, ...]


@dataclass(frozen=True, slots=True)
class ReviewedHolding:
    row_id: str
    instrument_id: str | None
    symbol: str | None
    quantity: Decimal | None
    average_price: Decimal | None
    include: bool = True


@dataclass(frozen=True, slots=True)
class PortfolioImportConfirmation:
    status: ImportStatus
    portfolio_id: str
    portfolio_snapshot_id: str
    holdings_imported: int
    warnings: tuple[str, ...]
    data_as_of: datetime


def resolved(candidate: ExtractedHoldingCandidate, *, instrument_id: str | None, status: SymbolResolutionStatus) -> ExtractedHoldingCandidate:
    return replace(candidate, instrument_id=instrument_id, resolution_status=status)
