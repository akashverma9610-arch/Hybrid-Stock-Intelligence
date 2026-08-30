from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Mapping


class SignalType(str, Enum):
    FRESH_ENTRY_SETUP = "FRESH_ENTRY_SETUP"
    ROTATION_ENTRY_SETUP = "ROTATION_ENTRY_SETUP"
    ADD_SETUP = "ADD_SETUP"
    HOLD_SETUP = "HOLD_SETUP"
    REDUCE_SETUP = "REDUCE_SETUP"
    EXIT_SETUP = "EXIT_SETUP"
    WAIT_SETUP = "WAIT_SETUP"
    CASH_SETUP = "CASH_SETUP"


class SignalStatus(str, Enum):
    DRAFT = "DRAFT"
    ELIGIBLE = "ELIGIBLE"
    WAITING_FOR_TRIGGER = "WAITING_FOR_TRIGGER"
    TRIGGERED_ANALYTICALLY = "TRIGGERED_ANALYTICALLY"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EntryType(str, Enum):
    AGGRESSIVE = "AGGRESSIVE"
    CONFIRMATION = "CONFIRMATION"
    PULLBACK_RETEST = "PULLBACK_RETEST"


class TriggerType(str, Enum):
    PRICE_CLOSE = "PRICE_CLOSE"
    PRICE_ZONE = "PRICE_ZONE"
    RECLAIM = "RECLAIM"
    VOLUME = "VOLUME"


class TriggerComparison(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    WITHIN = "WITHIN"


class SignalEventType(str, Enum):
    SIGNAL_CREATED = "SIGNAL_CREATED"
    REVALIDATED = "REVALIDATED"
    TRIGGER_CONDITION_MET = "TRIGGER_CONDITION_MET"
    TRIGGER_CONDITION_LOST = "TRIGGER_CONDITION_LOST"
    GATE_BLOCKED = "GATE_BLOCKED"
    THESIS_INVALIDATED = "THESIS_INVALIDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class SignalConfig:
    version: str
    minimum_score: Decimal | None
    minimum_confidence: float | None
    allowed_entry_types: tuple[EntryType, ...] | None
    minimum_risk_reward: Decimal | None
    required_gate_status: str | None
    require_rotation_for_rotation_entry: bool | None
    expiry_sessions: int | None
    minimum_setup_confirmations: int | None
    cooldown_after_invalidation_days: int | None

    def unresolved(self) -> tuple[str, ...]:
        data = {"minimum_score": self.minimum_score, "minimum_confidence": self.minimum_confidence,
                "allowed_entry_types": self.allowed_entry_types, "minimum_risk_reward": self.minimum_risk_reward,
                "required_gate_status": self.required_gate_status, "require_rotation_for_rotation_entry": self.require_rotation_for_rotation_entry,
                "expiry_sessions": self.expiry_sessions, "minimum_setup_confirmations": self.minimum_setup_confirmations,
                "cooldown_after_invalidation_days": self.cooldown_after_invalidation_days}
        return tuple(key for key, value in data.items() if value is None)


@dataclass(frozen=True, slots=True)
class TriggerCondition:
    condition_id: str
    trigger_type: TriggerType
    comparison: TriggerComparison
    threshold: Decimal | None
    zone_low: Decimal | None
    zone_high: Decimal | None
    timeframe: str
    confirmation_required: bool
    input_reference: str
    version: str


@dataclass(frozen=True, slots=True)
class TradePlan:
    plan_id: str
    setup_type: SignalType
    entry_type: EntryType | None
    entry_rule_id: int | None
    entry_price: Decimal | None
    entry_zone_low: Decimal | None
    entry_zone_high: Decimal | None
    trigger_conditions: tuple[TriggerCondition, ...]
    confirmation_condition: str | None
    structural_stop: Decimal | None
    exact_invalidation: str | None
    target_1: Decimal | None
    target_2: Decimal | None
    extended_target: Decimal | None
    risk_reward_t1: Decimal | None
    risk_reward_t2: Decimal | None
    catalyst: str | None
    catalyst_clock: str | None
    thesis_reference: str | None
    key_risks: tuple[str, ...]
    management_plan_reference: str | None
    expiry_condition: str | None
    time_horizon: str | None

    @property
    def complete_entry_plan(self) -> bool:
        return self.entry_type is not None and self.entry_rule_id in {40, 41, 42} and self.structural_stop is not None and self.exact_invalidation is not None and self.target_1 is not None and bool(self.trigger_conditions)


@dataclass(frozen=True, slots=True)
class SignalRequest:
    instrument_id: str | None
    portfolio_id: str | None
    portfolio_snapshot_id: str | None
    strategy_version: object
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    rotation_configuration_version: str | None
    as_of_timestamp: datetime
    scorecard_id: str | None
    raw_decision_score: Decimal | None
    score_status: str | None
    data_confidence: float | None
    gate_evaluation_id: str | None
    gate_status: str | None
    rotation_evaluation_id: str | None
    rotation_stance: str | None
    signal_type: SignalType
    trade_plan: TradePlan | None
    diagnostic_ids: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    setup_confirmations: int = 0
    invalidation_triggered: bool = False


@dataclass(frozen=True, slots=True)
class SignalRecord:
    signal_id: str
    instrument_id: str | None
    portfolio_id: str | None
    strategy_version: object
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    rotation_configuration_version: str | None
    as_of_timestamp: datetime
    generated_at: datetime
    signal_type: SignalType
    status: SignalStatus
    portfolio_snapshot_id: str | None
    decision_scorecard_id: str | None
    execution_gate_evaluation_id: str | None
    portfolio_rotation_evaluation_id: str | None
    trade_plan_id: str | None
    diagnostic_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    data_confidence: float | None
    signal_confidence: float | None
    warnings: tuple[str, ...]
    rationale_references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SignalLifecycleEvent:
    event_id: str
    signal_id: str
    event_type: SignalEventType
    event_timestamp: datetime
    as_of_timestamp: datetime
    resulting_status: SignalStatus
    reason: str
    evidence_ids: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    scorecard_id: str | None
    gate_evaluation_id: str | None
    rotation_evaluation_id: str | None


@dataclass(frozen=True, slots=True)
class TriggerObservation:
    observation_id: str
    price: Decimal
    observed_at: datetime
    known_at: datetime
    timeframe: str
    confirmed: bool


@dataclass(frozen=True, slots=True)
class RevalidationInput:
    as_of_timestamp: datetime
    known_at: datetime
    gate_status: str | None
    rotation_stance: str | None = None
    earnings_blackout: bool = False
    invalidation_triggered: bool = False
    catalyst_cancelled: bool = False
    score: Decimal | None = None
    evidence_ids: tuple[str, ...] = ()
