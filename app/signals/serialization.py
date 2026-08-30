from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.portfolio.serialization import dumps
from .models import *


def signal_from(value: dict) -> SignalRecord:
    value = dict(value)
    for key in ("as_of_timestamp", "generated_at"): value[key] = _time(value[key])
    for key in ("diagnostic_ids", "evidence_ids", "warnings", "rationale_references"): value[key] = tuple(value[key])
    value["signal_type"] = SignalType(value["signal_type"]); value["status"] = SignalStatus(value["status"])
    return SignalRecord(**value)


def event_from(value: dict) -> SignalLifecycleEvent:
    value = dict(value)
    for key in ("event_timestamp", "as_of_timestamp"): value[key] = _time(value[key])
    for key in ("evidence_ids", "diagnostic_ids"): value[key] = tuple(value[key])
    value["event_type"] = SignalEventType(value["event_type"]); value["resulting_status"] = SignalStatus(value["resulting_status"])
    return SignalLifecycleEvent(**value)


def plan_from(value: dict) -> TradePlan:
    value = dict(value)
    for key in ("entry_price", "entry_zone_low", "entry_zone_high", "structural_stop", "target_1", "target_2", "extended_target", "risk_reward_t1", "risk_reward_t2"): value[key] = _decimal(value[key])
    value["setup_type"] = SignalType(value["setup_type"]); value["entry_type"] = EntryType(value["entry_type"]) if value["entry_type"] else None
    value["trigger_conditions"] = tuple(condition_from(x) for x in value["trigger_conditions"]); value["key_risks"] = tuple(value["key_risks"])
    return TradePlan(**value)


def condition_from(value: dict) -> TriggerCondition:
    return TriggerCondition(value["condition_id"], TriggerType(value["trigger_type"]), TriggerComparison(value["comparison"]), _decimal(value["threshold"]), _decimal(value["zone_low"]), _decimal(value["zone_high"]), value["timeframe"], value["confirmation_required"], value["input_reference"], value["version"])


def _decimal(value): return Decimal(value) if value is not None else None
def _time(value): return datetime.fromisoformat(value)
