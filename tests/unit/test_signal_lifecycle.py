from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.gates.engine import ExchangeCalendar
from app.signals.engine import SignalOrchestrator
from app.signals.models import (
    EntryType, RevalidationInput, SignalConfig, SignalEventType, SignalStatus, SignalType,
    SignalRequest, TradePlan, TriggerComparison, TriggerCondition, TriggerObservation, TriggerType,
)


ASOF = datetime(2026, 8, 20, 10, tzinfo=UTC)
CONFIG = SignalConfig("signals-v1", Decimal("8"), .7, (EntryType.CONFIRMATION, EntryType.PULLBACK_RETEST), Decimal("2"), "EXECUTABLE", True, 5, 1, 2)
ORCHESTRATOR = SignalOrchestrator(CONFIG, ExchangeCalendar("nse-mock-v1", frozenset({date(2026, 8, 19)})))


def condition(): return TriggerCondition("trigger-1", TriggerType.PRICE_CLOSE, TriggerComparison.ABOVE, Decimal("105"), None, None, "daily", True, "rule-40", "trigger-v1")
def plan(**changes):
    data = TradePlan("plan-1", SignalType.FRESH_ENTRY_SETUP, EntryType.CONFIRMATION, 40, Decimal("105"), None, None, (condition(),), "close above pivot", Decimal("95"), "close below 95", Decimal("125"), Decimal("135"), None, Decimal("2"), Decimal("3"), "results", "Q2", "thesis-1", ("gap risk",), "management-v1", "5 sessions", "swing")
    return replace(data, **changes)
def request(**changes):
    data = SignalRequest("stock", "portfolio", "portfolio-snapshot", "strategy/0.1", "registry-v1", "score-v1", "gates-v1", "rotation-v1", ASOF,
        "score-1", Decimal("9"), "COMPLETE", .9, "gate-1", "EXECUTABLE", "rotation-1", "ROTATION_OPPORTUNITY", SignalType.FRESH_ENTRY_SETUP, plan(), ("40", "46"), ("evidence-1",))
    return replace(data, **changes)
def create(data=None): return ORCHESTRATOR.create(data or request(), ASOF)


def test_high_score_complete_setup_waits_until_trigger_without_order_or_mutation():
    signal, event = create()
    assert signal.status is SignalStatus.WAITING_FOR_TRIGGER and event.event_type is SignalEventType.SIGNAL_CREATED
    assert "NO_ORDER_OR_PORTFOLIO_MUTATION_CREATED" in signal.warnings and not hasattr(signal, "order_id")


def test_later_eligible_breakout_creates_trigger_event_only():
    signal, _ = create()
    observation = TriggerObservation("breakout", Decimal("106"), ASOF + timedelta(days=1), ASOF + timedelta(days=1), "daily", True)
    event = ORCHESTRATOR.revalidate(signal, plan(), (), RevalidationInput(ASOF + timedelta(days=1), ASOF + timedelta(days=1), "EXECUTABLE"), (observation,))
    assert event.resulting_status is SignalStatus.TRIGGERED_ANALYTICALLY and event.event_type is SignalEventType.TRIGGER_CONDITION_MET


def test_gate_failure_rotation_missing_invalid_plan_and_low_rr_fail_closed():
    gate, _ = create(request(gate_status="BLOCKED"))
    rotation, _ = create(request(signal_type=SignalType.ROTATION_ENTRY_SETUP, rotation_stance="NO_ROTATION"))
    missing, _ = create(request(trade_plan=None))
    low_rr, _ = create(request(trade_plan=plan(risk_reward_t1=Decimal("1.4"))))
    assert gate.status is SignalStatus.BLOCKED and rotation.status is SignalStatus.BLOCKED
    assert missing.status is SignalStatus.INSUFFICIENT_DATA and low_rr.status is SignalStatus.BLOCKED


def test_invalidation_expiry_and_revalidation_are_append_only_events():
    signal, _ = create()
    invalid = ORCHESTRATOR.revalidate(signal, plan(), (), RevalidationInput(ASOF + timedelta(days=1), ASOF + timedelta(days=1), "EXECUTABLE", invalidation_triggered=True), ())
    expired = ORCHESTRATOR.revalidate(signal, plan(), (), RevalidationInput(ASOF + timedelta(days=8), ASOF + timedelta(days=8), "EXECUTABLE"), ())
    assert invalid.resulting_status is SignalStatus.INVALIDATED and expired.resulting_status is SignalStatus.EXPIRED
    assert signal.status is SignalStatus.WAITING_FOR_TRIGGER


def test_wait_cash_and_exit_setups_do_not_force_stock_entry_or_sell_on_loss():
    wait, _ = create(request(instrument_id=None, signal_type=SignalType.WAIT_SETUP, trade_plan=None))
    cash, _ = create(request(instrument_id=None, signal_type=SignalType.CASH_SETUP, trade_plan=None))
    loss_exit, _ = create(request(signal_type=SignalType.EXIT_SETUP, trade_plan=None, warnings=("UNREALIZED_LOSS",)))
    assert wait.status is SignalStatus.WAITING_FOR_TRIGGER and cash.status is SignalStatus.WAITING_FOR_TRIGGER
    assert loss_exit.status is SignalStatus.INSUFFICIENT_DATA


def test_future_trigger_score_gate_rotation_earnings_catalyst_and_invalidation_cannot_change_history():
    signal, _ = create(); future = ASOF + timedelta(days=1)
    future_trigger = TriggerObservation("future-trigger", Decimal("106"), future, future, "daily", True)
    earlier = ORCHESTRATOR.revalidate(signal, plan(), (), RevalidationInput(ASOF, ASOF, "EXECUTABLE"), (future_trigger,))
    future_invalidation = RevalidationInput(future, future, "BLOCKED", "NO_ROTATION", True, True, True, Decimal("1"), ("future-invalidation",))
    assert earlier.resulting_status is SignalStatus.WAITING_FOR_TRIGGER and "future" not in str(earlier)
    later = ORCHESTRATOR.revalidate(signal, plan(), (), future_invalidation, (future_trigger,))
    assert future_invalidation.as_of_timestamp > ASOF and later.resulting_status is SignalStatus.INVALIDATED
    assert signal.status is SignalStatus.WAITING_FOR_TRIGGER and "future" not in str(signal)


def test_signal_config_has_no_silent_defaults_and_entry_condition_is_machine_testable():
    incomplete = replace(CONFIG, minimum_score=None)
    signal, _ = SignalOrchestrator(incomplete, ORCHESTRATOR.calendar).create(request(), ASOF)
    assert signal.status is SignalStatus.INSUFFICIENT_DATA
    assert plan().trigger_conditions[0].comparison is TriggerComparison.ABOVE
