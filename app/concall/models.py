"""Immutable, point-in-time safe earnings-call contracts (no IO)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256

from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType,
    FinancialValueBasis, NumericScale, StatementScope,
)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class GuidanceMatchStatus(StrEnum):
    MATCHED = "MATCHED"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass(frozen=True, slots=True)
class ConcallDocument:
    instrument_id: str
    filing_id: str
    source_reference: str
    checksum: str
    published_at: datetime
    received_at: datetime
    fiscal_year: int
    fiscal_quarter: int
    version: str = "v1"

    def __post_init__(self) -> None:
        if not all((self.instrument_id, self.filing_id, self.source_reference, self.version)):
            raise ValueError("CONCALL_IDENTITY_REQUIRED")
        if len(self.checksum) != 64 or any(c not in "0123456789abcdef" for c in self.checksum):
            raise ValueError("CONCALL_CHECKSUM_INVALID")
        if not _aware(self.published_at) or not _aware(self.received_at) or self.received_at < self.published_at:
            raise ValueError("CONCALL_TIMESTAMP_INVALID")
        if self.fiscal_year <= 0 or self.fiscal_quarter not in (1, 2, 3, 4):
            raise ValueError("CONCALL_FISCAL_PERIOD_INVALID")

    @property
    def document_id(self) -> str:
        return sha256("|".join((self.instrument_id, self.filing_id, self.checksum, self.version)).encode()).hexdigest()

    def visible_at(self, as_of: datetime) -> bool:
        if not _aware(as_of):
            raise ValueError("CONCALL_AS_OF_TIMEZONE_REQUIRED")
        return self.published_at <= as_of and self.received_at <= as_of


@dataclass(frozen=True, slots=True)
class ConcallSegment:
    document_id: str
    index: int
    speaker: str
    text: str
    page: int | None = None

    def __post_init__(self) -> None:
        if not self.document_id or self.index < 0 or not self.speaker.strip() or not self.text.strip():
            raise ValueError("CONCALL_SEGMENT_INVALID")
        if self.page is not None and self.page < 1:
            raise ValueError("CONCALL_PAGE_INVALID")


@dataclass(frozen=True, slots=True)
class ConcallGuidance:
    document_id: str
    segment_index: int
    metric: FinancialMetric
    target: Decimal
    period_end: datetime
    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    statement_scope: StatementScope
    currency: str
    unit: str
    scale: NumericScale

    def __post_init__(self) -> None:
        if not self.document_id or self.segment_index < 0 or not self.target.is_finite():
            raise ValueError("CONCALL_GUIDANCE_INVALID")
        if not _aware(self.period_end) or not self.currency or not self.unit:
            raise ValueError("CONCALL_GUIDANCE_PERIOD_INVALID")


@dataclass(frozen=True, slots=True)
class GuidanceMatch:
    status: GuidanceMatchStatus
    actual_fact_id: str | None = None
    difference: Decimal | None = None
    reason: str | None = None


def reconcile_guidance(guidance: ConcallGuidance, actual: FinancialFact | None, *, as_of: datetime) -> GuidanceMatch:
    """Exact comparable fact only. No implicit unit conversion or future knowledge."""
    if not _aware(as_of):
        raise ValueError("CONCALL_AS_OF_TIMEZONE_REQUIRED")
    if actual is None or actual.available_at > as_of:
        return GuidanceMatch(GuidanceMatchStatus.NOT_AVAILABLE, reason="NO_VISIBLE_ACTUAL")
    if (
        actual.metric != guidance.metric
        or actual.period_end != guidance.period_end
        or actual.period_type != guidance.period_type
        or actual.value_basis != guidance.value_basis
        or actual.statement_scope != guidance.statement_scope
        or actual.statement_scope is StatementScope.UNKNOWN
        or actual.currency != guidance.currency
        or actual.unit != guidance.unit
        or actual.scale != guidance.scale
    ):
        return GuidanceMatch(GuidanceMatchStatus.NOT_COMPARABLE, reason="METRIC_PERIOD_SCOPE_OR_UNIT_MISMATCH")
    return GuidanceMatch(GuidanceMatchStatus.MATCHED, actual_fact_id=actual.fact_id, difference=actual.value - guidance.target)
