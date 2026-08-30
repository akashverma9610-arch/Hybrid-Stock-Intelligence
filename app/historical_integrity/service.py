"""Facade that delegates eligibility to the existing backtest look-ahead guard."""
from __future__ import annotations

from app.historical.guard import BacktestLookaheadGuard
from app.historical.models import Eligibility, HistoricalFact, UniverseMembership

from .models import HistoricalIntegrityDecision, HistoricalIntegrityStatus, UniverseMembershipAsOf


class HistoricalIntegrityService:
    def __init__(self, guard: BacktestLookaheadGuard | None = None) -> None:
        self._guard = guard or BacktestLookaheadGuard()

    def membership_as_of(self, membership: UniverseMembership | None, *, as_of) -> UniverseMembershipAsOf:
        if membership is None:
            return UniverseMembershipAsOf("", "", as_of, Eligibility.INSUFFICIENT_METADATA, None, None, ("HISTORICAL_UNIVERSE_MEMBERSHIP_MISSING",))
        eligibility = self._guard.membership(membership, as_of)
        warnings = () if eligibility is Eligibility.ELIGIBLE else ("UNIVERSE_MEMBERSHIP_NOT_ELIGIBLE_AS_OF",)
        return UniverseMembershipAsOf(membership.instrument_id, membership.universe_id, as_of, eligibility, membership.status, membership.membership_id, warnings)

    def assess(self, fact: HistoricalFact | None, *, as_of, membership: UniverseMembership | None = None, require_membership: bool = False) -> HistoricalIntegrityDecision:
        if fact is None:
            return HistoricalIntegrityDecision(HistoricalIntegrityStatus.UNAVAILABLE, as_of, None, None, None, ("HISTORICAL_FACT_MISSING",))
        eligibility = self._guard.evaluate(fact, as_of)
        if eligibility is not Eligibility.ELIGIBLE:
            status = HistoricalIntegrityStatus.UNAVAILABLE if eligibility is Eligibility.INSUFFICIENT_METADATA else HistoricalIntegrityStatus.INVALID
            return HistoricalIntegrityDecision(status, as_of, fact.fact_id, eligibility, None, (f"FACT_{eligibility.value}",))
        membership_as_of = self.membership_as_of(membership, as_of=as_of) if (membership is not None or require_membership) else None
        if membership_as_of is None:
            return HistoricalIntegrityDecision(HistoricalIntegrityStatus.VALID, as_of, fact.fact_id, eligibility, None)
        if membership_as_of.eligibility is Eligibility.ELIGIBLE:
            return HistoricalIntegrityDecision(HistoricalIntegrityStatus.VALID, as_of, fact.fact_id, eligibility, membership_as_of)
        status = HistoricalIntegrityStatus.PARTIAL if membership_as_of.eligibility is Eligibility.INSUFFICIENT_METADATA else HistoricalIntegrityStatus.INVALID
        return HistoricalIntegrityDecision(status, as_of, fact.fact_id, eligibility, membership_as_of, membership_as_of.warnings)
