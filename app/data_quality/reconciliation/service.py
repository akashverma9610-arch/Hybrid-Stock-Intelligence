"""Deterministic comparison of already-normalized facts from independent sources."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.market_data.models import CanonicalOHLCVBar, CanonicalQuote, FreshnessState


class ReconciliationStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    MINOR_VARIANCE = "MINOR_VARIANCE"
    MATERIAL_CONFLICT = "MATERIAL_CONFLICT"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    UNVERIFIABLE = "UNVERIFIABLE"


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    reconciliation_id: str
    subject_id: str
    source_a: str
    source_b: str
    as_of: datetime
    retrieved_at: datetime
    normalization_versions: tuple[str, str]
    status: ReconciliationStatus
    conflicts: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def reliability_downgraded(self) -> bool:
        return self.status in {ReconciliationStatus.MATERIAL_CONFLICT, ReconciliationStatus.STALE, ReconciliationStatus.INCOMPLETE, ReconciliationStatus.UNVERIFIABLE}


class ReconciliationService:
    """Reports disagreements exactly; it never averages or repairs source values."""
    def reconcile_bars(self, left: CanonicalOHLCVBar | None, right: CanonicalOHLCVBar | None, *, as_of: datetime, retrieved_at: datetime) -> ReconciliationResult:
        if left is None or right is None:
            return self._result(left, right, as_of, retrieved_at, ReconciliationStatus.INCOMPLETE, ("MISSING_BAR",))
        conflicts: list[str] = []
        if left.instrument.instrument_id != right.instrument.instrument_id or left.instrument.isin != right.instrument.isin:
            conflicts.append("SYMBOL_OR_ISIN_MISMATCH")
        if left.timeframe != right.timeframe or left.start_time != right.start_time or left.end_time != right.end_time:
            conflicts.append("TIMESTAMP_OR_TIMEZONE_MISMATCH")
        if left.adjustment_status != right.adjustment_status:
            conflicts.append("ADJUSTMENT_POLICY_MISMATCH")
        if (left.open, left.high, left.low, left.close) != (right.open, right.high, right.low, right.close):
            conflicts.append("OHLC_MISMATCH")
        if left.volume != right.volume:
            conflicts.append("VOLUME_MISMATCH")
        if left.bar_id == right.bar_id and left.provenance.provider != right.provenance.provider:
            conflicts.append("DUPLICATE_BAR_ID_ACROSS_SOURCES")
        status = ReconciliationStatus.MATERIAL_CONFLICT if conflicts else ReconciliationStatus.CONSISTENT
        return self._result(left, right, as_of, retrieved_at, status, tuple(conflicts))

    def reconcile_quotes(self, left: CanonicalQuote | None, right: CanonicalQuote | None, *, as_of: datetime, retrieved_at: datetime) -> ReconciliationResult:
        if left is None or right is None:
            return self._quote_result(left, right, as_of, retrieved_at, ReconciliationStatus.INCOMPLETE, ("MISSING_QUOTE",))
        if left.freshness.state is not FreshnessState.FRESH or right.freshness.state is not FreshnessState.FRESH:
            return self._quote_result(left, right, as_of, retrieved_at, ReconciliationStatus.STALE, ("STALE_QUOTE",))
        conflicts: list[str] = []
        if left.instrument.instrument_id != right.instrument.instrument_id or left.instrument.isin != right.instrument.isin:
            conflicts.append("SYMBOL_OR_ISIN_MISMATCH")
        if left.last_price is None or right.last_price is None:
            conflicts.append("MISSING_LAST_PRICE")
        elif left.last_price != right.last_price:
            conflicts.append("LAST_PRICE_MISMATCH")
        if left.last_price is not None and left.last_price <= 0 or right.last_price is not None and right.last_price <= 0:
            conflicts.append("SUSPICIOUS_ZERO_OR_NEGATIVE_PRICE")
        status = ReconciliationStatus.MATERIAL_CONFLICT if conflicts else ReconciliationStatus.CONSISTENT
        return self._quote_result(left, right, as_of, retrieved_at, status, tuple(conflicts))

    @staticmethod
    def _result(left, right, as_of, retrieved_at, status, conflicts):
        subject = left.instrument.instrument_id if left else right.instrument.instrument_id if right else "unknown"
        return ReconciliationResult("reconcile-bar:" + subject + ":" + as_of.isoformat(), subject, left.provenance.provider if left else "missing", right.provenance.provider if right else "missing", as_of, retrieved_at, (left.provenance.normalization_version if left else "unknown", right.provenance.normalization_version if right else "unknown"), status, conflicts)

    @staticmethod
    def _quote_result(left, right, as_of, retrieved_at, status, conflicts):
        subject = left.instrument.instrument_id if left else right.instrument.instrument_id if right else "unknown"
        return ReconciliationResult("reconcile-quote:" + subject + ":" + as_of.isoformat(), subject, left.provenance.provider if left else "missing", right.provenance.provider if right else "missing", as_of, retrieved_at, (left.provenance.normalization_version if left else "unknown", right.provenance.normalization_version if right else "unknown"), status, conflicts)
