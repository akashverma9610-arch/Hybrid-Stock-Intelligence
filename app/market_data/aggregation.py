"""Provider-neutral index, VIX, and market-breadth aggregation from canonical facts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Mapping

from app.domain.models import DataQuality
from app.historical.models import UniverseMembership
from app.market_data.historical import HistoricalBarStore
from app.market_data.models import (
    CanonicalQuote, FreshnessAssessment, FreshnessState, IndexMarketObservation,
    InstrumentIdentity, InstrumentType, MarketBreadthObservation, MarketDataProvenance,
    MarketSessionState, Timeframe,
)
from app.market_data.store import MarketDataStore


class BreadthCoverageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class MarketUniverse:
    universe_id: str
    version: str
    memberships: tuple[UniverseMembership, ...]
    pit_available: bool = True

    def constituents_as_of(self, at: datetime) -> tuple[str, ...]:
        values = [item.instrument_id for item in self.memberships if item.known_at <= at and item.effective_from <= at and (item.effective_to is None or at < item.effective_to)]
        return tuple(sorted(set(values)))


@dataclass(frozen=True, slots=True)
class MarketParticipationSnapshot:
    snapshot_id: str
    universe_id: str
    data_as_of: datetime
    total_constituents: int
    observed_constituents: int
    classified_constituents: int
    coverage_percent: Decimal
    stale_constituents: int
    missing_constituents: int
    breadth_ratio: Decimal | None
    advance_decline_ratio: Decimal | None
    up_down_volume_ratio: Decimal | None
    high_low_ratio: Decimal | None
    leadership_concentration: Decimal | None
    coverage: BreadthCoverageStatus
    warnings: tuple[str, ...]
    provenance: MarketDataProvenance


@dataclass(frozen=True, slots=True)
class MarketStateInputBundle:
    data_as_of: datetime
    indices: Mapping[str, IndexMarketObservation]
    vix: IndexMarketObservation | None
    breadth: MarketBreadthObservation | None
    participation: MarketParticipationSnapshot | None
    warnings: tuple[str, ...] = ()


class IndexObservationService:
    def __init__(self, store: MarketDataStore, bars: HistoricalBarStore | None = None) -> None:
        self._store, self._bars = store, bars

    def latest(self, instrument_id: str) -> IndexMarketObservation | None:
        return self._store.latest_index(instrument_id)

    def vix(self, instrument: InstrumentIdentity) -> IndexMarketObservation | None:
        if instrument.instrument_type is not InstrumentType.VOLATILITY_INDEX:
            raise ValueError("VIX access requires a volatility-index identity.")
        return self.latest(instrument.instrument_id)

    def history(self, instrument_id: str, timeframe: Timeframe, start: datetime, end: datetime, *, as_of: datetime | None = None):
        if self._bars is None: return ()
        return self._bars.range(instrument_id, timeframe, start, end, as_of=as_of)


class BreadthAggregator:
    """Makes only source-data facts; it does not assign regime, crisis, or euphoria."""
    def __init__(self, *, minimum_coverage: Decimal = Decimal("0.6"), new_high_lookback: int = 20) -> None:
        self._minimum_coverage, self._new_high_lookback = minimum_coverage, new_high_lookback

    def aggregate(self, universe: MarketUniverse, quotes: Mapping[str, CanonicalQuote], *, data_as_of: datetime, provenance: MarketDataProvenance, bars: HistoricalBarStore | None = None) -> tuple[MarketBreadthObservation, MarketParticipationSnapshot]:
        members = universe.constituents_as_of(data_as_of)
        warnings: list[str] = []
        if not universe.pit_available: warnings.append("POINT_IN_TIME_UNIVERSE_UNAVAILABLE")
        advances = declines = unchanged = stale = missing = up_volume = down_volume = 0
        volume_complete = True; highs = lows = 0; high_low_available = bars is not None
        returns: list[Decimal] = []
        for member in members:
            quote = quotes.get(member)
            if quote is None: missing += 1; continue
            if quote.freshness.state is not FreshnessState.FRESH: stale += 1; continue
            if quote.last_price is None or quote.previous_close is None: continue
            delta = quote.last_price - quote.previous_close
            if delta > 0: advances += 1
            elif delta < 0: declines += 1
            else: unchanged += 1
            if quote.volume is None: volume_complete = False
            elif delta > 0: up_volume += quote.volume
            elif delta < 0: down_volume += quote.volume
            returns.append(delta / quote.previous_close)
            if bars is not None:
                history = bars.latest(member, Timeframe.DAILY, self._new_high_lookback, as_of=data_as_of)
                if len(history) < self._new_high_lookback: high_low_available = False
                elif quote.last_price >= max(item.high for item in history): highs += 1
                elif quote.last_price <= min(item.low for item in history): lows += 1
        total = len(members); classified = advances + declines + unchanged; observed = total - missing
        coverage_percent = Decimal(classified) / Decimal(total) if total else Decimal("0")
        coverage = BreadthCoverageStatus.UNAVAILABLE if not total else BreadthCoverageStatus.INSUFFICIENT if coverage_percent < self._minimum_coverage else BreadthCoverageStatus.PARTIAL if missing or stale or classified < total else BreadthCoverageStatus.COMPLETE
        if stale: warnings.append("STALE_CONSTITUENTS_EXCLUDED")
        if missing: warnings.append("MISSING_CONSTITUENTS")
        if not volume_complete: warnings.append("VOLUME_COVERAGE_PARTIAL")
        if not high_low_available: warnings.append("NEW_HIGH_LOW_LOOKBACK_INSUFFICIENT")
        freshness = FreshnessAssessment(FreshnessState.FRESH if coverage is BreadthCoverageStatus.COMPLETE else FreshnessState.STALE if classified else FreshnessState.UNKNOWN, data_as_of, data_as_of, None, None, MarketSessionState.OPEN, tuple(warnings))
        observation = MarketBreadthObservation(
            f"breadth:{universe.universe_id}:{data_as_of.isoformat()}", universe.universe_id, advances or None, declines or None, unchanged or None,
            highs if high_low_available else None, lows if high_low_available else None, None, None,
            up_volume if volume_complete else None, down_volume if volume_complete else None, total, classified, data_as_of, provenance, freshness,
            DataQuality.HIGH if coverage is BreadthCoverageStatus.COMPLETE else DataQuality.MEDIUM if classified else DataQuality.LOW, tuple(warnings),
        )
        positive = sorted((value for value in returns if value > 0), reverse=True)
        concentration = sum(positive[:3], Decimal("0")) / sum(positive, Decimal("0")) if positive else None
        participation = MarketParticipationSnapshot(
            observation.observation_id, universe.universe_id, data_as_of, total, observed, classified, coverage_percent, stale, missing,
            Decimal(advances - declines) / Decimal(classified) if classified else None,
            Decimal(advances) / Decimal(declines) if declines else None,
            Decimal(up_volume) / Decimal(down_volume) if volume_complete and down_volume else None,
            Decimal(highs) / Decimal(lows) if high_low_available and lows else None, concentration, coverage, tuple(warnings), provenance,
        )
        return observation, participation
