from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.historical.models import Eligibility, InstrumentLifecycle


class HistoricalIntegrityStatus(StrEnum):
    VALID = "VALID"
    PARTIAL = "PARTIAL"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class UniverseMembershipAsOf:
    instrument_id: str
    universe_id: str
    as_of: datetime
    eligibility: Eligibility
    lifecycle: InstrumentLifecycle | None
    membership_id: str | None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalIntegrityDecision:
    status: HistoricalIntegrityStatus
    as_of: datetime
    fact_id: str | None
    fact_eligibility: Eligibility | None
    membership: UniverseMembershipAsOf | None
    warnings: tuple[str, ...] = ()
