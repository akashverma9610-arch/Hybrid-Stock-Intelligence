"""Read-only public projections over persisted breadth and market-risk models.

The HTTP boundary deliberately does not invoke aggregation, crisis, or upside
excess engines. It only formats immutable values supplied by runtime snapshots
or explicitly injected query services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.api.errors import APIRequestError
from app.api.schemas.market import BreadthResponse, CrisisResponse, MarketExtremesResponse
from app.crisis.models import CrisisAssessment, UpsideExcessAssessment
from app.market_data.aggregation import MarketParticipationSnapshot
from app.market_data.models import MarketBreadthObservation


@dataclass(frozen=True, slots=True)
class BreadthQueryRecord:
    breadth: MarketBreadthObservation
    participation: MarketParticipationSnapshot | None = None
    generated_at: datetime | None = None
    cycle_reference: str | None = None


class BreadthQueryService(Protocol):
    def get_breadth(self) -> BreadthQueryRecord: ...


class MarketExtremesQueryService(Protocol):
    def get_extremes(self) -> UpsideExcessAssessment: ...


class CrisisQueryService(Protocol):
    def get_crisis(self) -> CrisisAssessment: ...


class UnavailableBreadthQueryService:
    def get_breadth(self) -> BreadthQueryRecord:
        raise _unavailable("MARKET_BREADTH_UNAVAILABLE", "Market breadth is not available.")


class UnavailableMarketExtremesQueryService:
    def get_extremes(self) -> UpsideExcessAssessment:
        raise _unavailable("MARKET_EXTREMES_UNAVAILABLE", "Market extremes are not available.")


class UnavailableCrisisQueryService:
    def get_crisis(self) -> CrisisAssessment:
        raise _unavailable("MARKET_CRISIS_UNAVAILABLE", "Market crisis state is not available.")


class SnapshotBreadthQueryService:
    def __init__(self, value: BreadthQueryRecord | None) -> None: self._value = value
    def get_breadth(self) -> BreadthQueryRecord:
        if self._value is None: raise _unavailable("MARKET_BREADTH_UNAVAILABLE", "Market breadth is not available.")
        return self._value


class SnapshotMarketExtremesQueryService:
    def __init__(self, value: UpsideExcessAssessment | None) -> None: self._value = value
    def get_extremes(self) -> UpsideExcessAssessment:
        if self._value is None: raise _unavailable("MARKET_EXTREMES_UNAVAILABLE", "Market extremes are not available.")
        return self._value


class SnapshotCrisisQueryService:
    def __init__(self, value: CrisisAssessment | None) -> None: self._value = value
    def get_crisis(self) -> CrisisAssessment:
        if self._value is None: raise _unavailable("MARKET_CRISIS_UNAVAILABLE", "Market crisis state is not available.")
        return self._value


def breadth_response(value: BreadthQueryRecord) -> BreadthResponse:
    breadth, participation = value.breadth, value.participation
    status = participation.coverage.value if participation is not None else breadth.quality.value
    warnings = (*breadth.warnings, *(participation.warnings if participation is not None else ()))
    return BreadthResponse(
        status=status, generated_at=value.generated_at or breadth.observed_at,
        data_as_of=breadth.observed_at, freshness=breadth.freshness.state.value,
        universe_reference=breadth.universe_reference, participation_state=participation.coverage.value if participation else None,
        advances=breadth.advances, declines=breadth.declines, unchanged=breadth.unchanged,
        advance_decline_ratio=_ratio(breadth.advances, breadth.declines),
        new_highs=breadth.new_highs, new_lows=breadth.new_lows,
        percent_above_reference=breadth.percent_above_reference,
        leadership_concentration=participation.leadership_concentration if participation else None,
        coverage_percent=participation.coverage_percent if participation else None,
        warnings=tuple(dict.fromkeys(warnings)), cycle_reference=value.cycle_reference,
    )


def extremes_response(value: UpsideExcessAssessment) -> MarketExtremesResponse:
    return MarketExtremesResponse(
        status="READY", generated_at=value.assessed_at, data_as_of=value.data_as_of,
        market_state=value.excess_state.value, cycle_stage=value.cycle_stage.value,
        top_confirmed=value.top_confirmed, distribution_risk=value.distribution_risk.value,
        leadership_quality=value.leadership_quality.value,
        price_earnings_divergence=value.price_earnings_divergence.value,
        rationale=value.transition_reason, warnings=value.warnings,
    )


def crisis_response(value: CrisisAssessment) -> CrisisResponse:
    return CrisisResponse(
        status="READY", generated_at=value.assessed_at, data_as_of=value.data_as_of,
        state=value.crisis_state.value, risk_posture=None, rationale=value.transition_reason,
        warnings=value.warnings,
    )


def _ratio(numerator: int | None, denominator: int | None) -> Decimal | None:
    return Decimal(numerator) / Decimal(denominator) if numerator is not None and denominator not in (None, 0) else None


def _unavailable(code: str, message: str) -> APIRequestError:
    return APIRequestError(status_code=503, code=code, message=message)
