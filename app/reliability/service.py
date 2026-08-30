"""Thin, deterministic facade over readiness facts; it has no provider side effects."""
from __future__ import annotations

from app.data_sources.models import DataFamily, SourceReadinessStatus

from .models import DataAvailability, ReliabilityDecision, ReliabilityStatus, SourceHealth


# One declared market-history source ordering, shared by the historical-bar
# resolver.  It is intentionally a routing policy rather than an analytical
# rule: callers still reject unusable/incomplete observations for the contract
# they requested.
_MARKET_BAR_SOURCE_TIERS = {
    "nse_official": 1,
    "nse": 1,
    "bse_official": 1,
    "bse": 1,
    "upstox": 2,
    "global_datafeeds": 2,
    "gdfl": 2,
    "yfinance": 3,
    "yahoo_finance": 3,
    "yahoo": 3,
}


def market_bar_source_priority(provider: str | None) -> int:
    """Return the one deterministic source tier for canonical market bars.

    Unknown legacy provenance remains available only after known sources; it
    is never guessed to be an official or licensed provider.
    """
    return _MARKET_BAR_SOURCE_TIERS.get(str(provider or "").strip().casefold(), 99)


class DataReliabilityService:
    """Select the first usable declared source or explicitly return unavailable.

    A fallback may be selected only from caller-provided, approved health facts.
    The service returns no market payload and therefore cannot synthesize data.
    """

    _USABLE = {SourceReadinessStatus.READY, SourceReadinessStatus.DEGRADED}

    def decide(self, family: DataFamily, sources: tuple[SourceHealth, ...], *, allow_last_known_good: bool = True) -> ReliabilityDecision:
        candidates = tuple(sorted((item for item in sources if item.family is family), key=lambda item: (item.tier, item.source_id)))
        usable = tuple(item for item in candidates if item.data_available and item.readiness in self._USABLE)
        conflicts = _conflicts(usable)
        if conflicts:
            return self._unavailable(family, ReliabilityStatus.CONFLICTED, ("SOURCE_VALUE_CONFLICT",))
        if usable:
            selected = usable[0]
            is_fallback = selected.tier > 1
            status = (
                ReliabilityStatus.FALLBACK_USED if is_fallback else
                ReliabilityStatus.STALE if selected.freshness is ReliabilityStatus.STALE else
                ReliabilityStatus.DEGRADED if selected.readiness is SourceReadinessStatus.DEGRADED else
                ReliabilityStatus.READY
            )
            warnings = tuple((*selected.warnings, *("PRIMARY_UNAVAILABLE" for _ in [0] if is_fallback)))
            availability = DataAvailability(family, status, selected.source_id, selected.tier, selected.observed_at, warnings)
            return ReliabilityDecision(family, availability, selected.source_id, selected.tier, is_fallback, False, False, warnings)
        if allow_last_known_good:
            lkg = next((item for item in candidates if item.data_available and item.freshness is ReliabilityStatus.LAST_KNOWN_GOOD), None)
            if lkg is not None:
                warnings = tuple((*lkg.warnings, "LAST_KNOWN_GOOD_NOT_FRESH"))
                availability = DataAvailability(family, ReliabilityStatus.LAST_KNOWN_GOOD, lkg.source_id, lkg.tier, lkg.observed_at, warnings)
                return ReliabilityDecision(family, availability, lkg.source_id, lkg.tier, lkg.tier > 1, True, False, warnings)
        status = ReliabilityStatus.PRIMARY_UNAVAILABLE if candidates else ReliabilityStatus.UNAVAILABLE
        return self._unavailable(family, status, ("NO_USABLE_DECLARED_SOURCE",))

    @staticmethod
    def _unavailable(family: DataFamily, status: ReliabilityStatus, warnings: tuple[str, ...]) -> ReliabilityDecision:
        availability = DataAvailability(family, status, None, None, None, warnings)
        return ReliabilityDecision(family, availability, None, None, False, False, status is ReliabilityStatus.CONFLICTED, warnings)


def _conflicts(values: tuple[SourceHealth, ...]) -> bool:
    fingerprints = {item.value_fingerprint for item in values if item.value_fingerprint is not None}
    return len(fingerprints) > 1
