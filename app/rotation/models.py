from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping


class RotationDecisionState(str, Enum):
    KEEP_EXISTING = "KEEP_EXISTING"
    ROTATE_CANDIDATE_PREFERRED = "ROTATE_CANDIDATE_PREFERRED"
    CASH_PREFERRED = "CASH_PREFERRED"
    NO_ACTION = "NO_ACTION"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    COMPARISON_AVAILABLE_EXECUTION_BLOCKED = "COMPARISON_AVAILABLE_EXECUTION_BLOCKED"


class RotationStance(str, Enum):
    NO_ROTATION = "NO_ROTATION"
    ROTATION_OPPORTUNITY = "ROTATION_OPPORTUNITY"
    DEFENSIVE_CASH = "DEFENSIVE_CASH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RotationComparisonStatus(str, Enum):
    NO_ELIGIBLE_REPLACEMENT = "NO_ELIGIBLE_REPLACEMENT"
    COMPARISON_AVAILABLE = "COMPARISON_AVAILABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RotationExecutionEligibility(str, Enum):
    EXECUTION_ELIGIBLE = "EXECUTION_ELIGIBLE"
    EXECUTION_BLOCKED_CASH_UNKNOWN = "EXECUTION_BLOCKED_CASH_UNKNOWN"


@dataclass(frozen=True, slots=True)
class RotationConfig:
    version: str
    min_score_advantage: Decimal | None
    minimum_confidence: float | None
    minimum_risk_reward: Decimal | None
    require_entry_stop_invalidation: bool | None
    require_supportive_sector: bool | None
    require_friction_check: bool | None
    friction_model_version: str | None
    min_confirmations: int | None
    cooldown_days: int | None
    candidate_ranking_version: str = "score-confidence-rr-instrument-v1"
    holding_tiebreak_version: str = "score-confidence-rr-instrument-v1"

    def unresolved(self) -> tuple[str, ...]:
        required = {"min_score_advantage": self.min_score_advantage, "minimum_confidence": self.minimum_confidence,
                    "minimum_risk_reward": self.minimum_risk_reward, "require_entry_stop_invalidation": self.require_entry_stop_invalidation,
                    "require_supportive_sector": self.require_supportive_sector, "require_friction_check": self.require_friction_check,
                    "friction_model_version": self.friction_model_version, "min_confirmations": self.min_confirmations,
                    "cooldown_days": self.cooldown_days}
        return tuple(key for key, value in required.items() if value is None)


@dataclass(frozen=True, slots=True)
class RotationCandidate:
    instrument_id: str
    as_of_timestamp: datetime
    known_at: datetime
    decision_scorecard_id: str | None
    raw_decision_score: Decimal | None
    score_status: str | None
    data_confidence: float | None
    gate_evaluation_id: str | None
    gate_status: str | None
    sector: str | None
    sector_supportive: bool | None
    risk_state: str | None
    trading_thesis_status: str | None
    investment_thesis_status: str | None
    structural_risk_reward: Decimal | None
    entry_valid: bool | None
    stop_valid: bool | None
    invalidation_valid: bool | None
    catalyst_timing: str | None
    warnings: tuple[str, ...] = ()
    blocking_warning: bool = False
    liquidity_trap_context: str | None = None
    portfolio_constraints_ok: bool | None = None
    currently_owned: bool = False
    modeled_switching_friction: Decimal | None = None
    expected_incremental_benefit: Decimal | None = None
    confirmation_count: int = 0
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RotationHoldingState:
    instrument_id: str
    as_of_timestamp: datetime
    known_at: datetime
    raw_decision_score: Decimal | None
    data_confidence: float | None
    gate_status: str | None
    sector: str | None
    sector_supportive: bool | None
    trading_thesis_status: str | None
    investment_thesis_status: str | None
    invalidation_status: str | None
    structural_risk_reward: Decimal | None
    current_forward_risk_reward: Decimal | None
    allocation: Decimal | None
    heat: Decimal | None
    holding_sessions: int | None
    capital_velocity_adjustment: Decimal = Decimal("0")
    current_market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    structural_stop: Decimal | None = None
    warnings: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @property
    def comparison_score(self) -> Decimal | None:
        return self.raw_decision_score + self.capital_velocity_adjustment if self.raw_decision_score is not None else None

    @property
    def invalidated(self) -> bool:
        return self.invalidation_status in {"TRIGGERED", "BROKEN", "SEVERE_CONCERN"} or self.trading_thesis_status == "BROKEN"


@dataclass(frozen=True, slots=True)
class RotationComparison:
    holding_instrument_id: str | None
    candidate_instrument_id: str
    holding_comparison_score: Decimal | None
    candidate_score: Decimal | None
    score_gap: Decimal | None
    hurdle: Decimal | None
    holding_sector: str | None
    candidate_sector: str | None
    holding_forward_risk_reward: Decimal | None
    candidate_risk_reward: Decimal | None
    holding_confidence: float | None
    candidate_confidence: float | None
    holding_invalidated: bool | None
    gate_status: str | None
    friction_status: str
    result: RotationDecisionState
    reasons_for: tuple[str, ...]
    reasons_against: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    candidate: RotationCandidate
    rank: int
    ranking_inputs: Mapping[str, str]
    tie_break_reason: str


@dataclass(frozen=True, slots=True)
class RotationEvaluationContext:
    portfolio_snapshot_id: str
    strategy_version: object
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    as_of_timestamp: datetime
    holdings: tuple[RotationHoldingState, ...]
    cash_amount: Decimal | None
    candidates: tuple[RotationCandidate, ...]
    transaction_friction_model_version: str | None
    last_rotation_at: datetime | None = None
    cash_state: str = "KNOWN"


@dataclass(frozen=True, slots=True)
class PortfolioRotationEvaluation:
    evaluation_id: str
    context: RotationEvaluationContext
    rotation_configuration_version: str
    ranked_holdings: tuple[RotationHoldingState, ...]
    ranked_candidates: tuple[RankedCandidate, ...]
    blocked_candidate_ids: tuple[str, ...]
    weakest_holding_id: str | None
    strongest_holding_id: str | None
    comparisons: tuple[RotationComparison, ...]
    stance: RotationStance
    preferred_candidate_id: str | None
    decision: RotationDecisionState
    warnings: tuple[str, ...]
    comparison_status: RotationComparisonStatus = RotationComparisonStatus.NO_ELIGIBLE_REPLACEMENT
    execution_eligibility: RotationExecutionEligibility = RotationExecutionEligibility.EXECUTION_ELIGIBLE
