"""Read-only risk evidence utilities; none alters models, holdings, or orders."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class RotationHurdleStatus(StrEnum):
    PASS = "PASS"
    REJECTED = "REJECTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class RotationHurdle:
    candidate_advantage: Decimal | None
    switching_friction: Decimal | None
    uncertainty_buffer: Decimal | None
    existing_minimum_superiority: Decimal | None
    status: RotationHurdleStatus
    reason: str


class RotationHurdleService:
    def assess(self, *, candidate_advantage: Decimal | None, switching_friction: Decimal | None, uncertainty_buffer: Decimal | None, existing_minimum_superiority: Decimal | None) -> RotationHurdle:
        if None in (candidate_advantage, switching_friction, uncertainty_buffer, existing_minimum_superiority):
            return RotationHurdle(candidate_advantage, switching_friction, uncertainty_buffer, existing_minimum_superiority, RotationHurdleStatus.NOT_CONFIGURED, "RESEARCH_REQUIRED_NO_NUMERIC_CONSTANT_INVENTED")
        hurdle = switching_friction + uncertainty_buffer + existing_minimum_superiority
        return RotationHurdle(candidate_advantage, switching_friction, uncertainty_buffer, existing_minimum_superiority, RotationHurdleStatus.PASS if candidate_advantage > hurdle else RotationHurdleStatus.REJECTED, "ADVANTAGE_EXCEEDS_ALL_FROZEN_HURDLES" if candidate_advantage > hurdle else "TRIVIAL_OR_FRICTION_NEGATIVE_ADVANTAGE")


@dataclass(frozen=True, slots=True)
class RotationHistoryRecord:
    rotation_id: str
    from_instrument_id: str
    to_instrument_id: str
    occurred_at: datetime
    switching_loss: Decimal | None


@dataclass(frozen=True, slots=True)
class PortfolioFactorExposure:
    portfolio_id: str
    factor: str
    exposure: Decimal
    holding_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class FactorExposureService:
    def aggregate(self, *, portfolio_id: str, holding_exposures: tuple[tuple[str, str, Decimal], ...]) -> tuple[PortfolioFactorExposure, ...]:
        grouped: dict[str, list[tuple[str, Decimal]]] = {}
        for holding_id, factor, exposure in holding_exposures: grouped.setdefault(factor, []).append((holding_id, exposure))
        return tuple(PortfolioFactorExposure(portfolio_id, factor, sum((v for _, v in values), Decimal("0")), tuple(identifier for identifier, _ in values), ("HIDDEN_CORRELATED_BET",) if len(values) > 1 else ()) for factor, values in sorted(grouped.items()))


class EmergencyDefensiveMode(StrEnum):
    NORMAL = "NORMAL"
    FREEZE_NEW_ENTRIES = "FREEZE_NEW_ENTRIES"
    REDUCE_SIGNAL_CONFIDENCE = "REDUCE_SIGNAL_CONFIDENCE"
    REQUIRE_MANUAL_REVIEW = "REQUIRE_MANUAL_REVIEW"
    DISABLE_ROTATION = "DISABLE_ROTATION"
    MARK_DATA_DEGRADED = "MARK_DATA_DEGRADED"


@dataclass(frozen=True, slots=True)
class EmergencyDefensivePolicy:
    policy_id: str
    mode: EmergencyDefensiveMode
    reason: str
    activated_at: datetime
    pre_authorized: bool = True

    def __post_init__(self) -> None:
        if not self.pre_authorized:
            raise ValueError("Emergency restriction must be explicitly pre-authorized.")
