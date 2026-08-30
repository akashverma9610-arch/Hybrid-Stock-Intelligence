"""Two-stage deterministic scanner boundary; it does not perform deep research itself."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CheapScanCandidate:
    instrument_id: str
    universe_eligible: bool
    liquidity_available: bool
    trend_available: bool
    relative_strength_available: bool
    volume_available: bool
    basic_integrity_available: bool
    prefilter_rank: Decimal | None


@dataclass(frozen=True, slots=True)
class CheapScanResult:
    shortlisted_instrument_ids: tuple[str, ...]
    excluded_instrument_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class TwoStageScanner:
    def shortlist(self, candidates: tuple[CheapScanCandidate, ...], *, limit: int) -> CheapScanResult:
        if limit < 1: raise ValueError("Shortlist limit must be positive.")
        eligible = tuple(item for item in candidates if item.universe_eligible and item.liquidity_available and item.trend_available and item.relative_strength_available and item.volume_available and item.basic_integrity_available and item.prefilter_rank is not None)
        ranked = tuple(sorted(eligible, key=lambda item: (-item.prefilter_rank, item.instrument_id)))
        return CheapScanResult(tuple(item.instrument_id for item in ranked[:limit]), tuple(sorted(item.instrument_id for item in candidates if item not in eligible)), ("SHORTLIST_ONLY_NO_FINAL_CAPITAL_DECISION",))
