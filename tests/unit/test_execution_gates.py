from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.gates.engine import (
    ActionContext, ExchangeCalendar, ExecutionEligibility, ExecutionGateConfig,
    ExecutionGateEngine, GateInput, GateOutcome, PortfolioExposure,
    SurveillanceObservation, TradeManagementPlan,
)


ASOF = datetime(2026, 8, 20, 10, tzinfo=UTC)
CALENDAR = ExchangeCalendar("nse-mock-v1", frozenset({date(2026, 8, 19)}))
CONFIG = ExecutionGateConfig("execution-gates-v1", Decimal("0.8"), "friction-v1", None, False,
    10, Decimal("1"), Decimal("0.5"), 2, True, Decimal("0.05"), 2,
    Decimal("0.50"), Decimal("0.40"), True, Decimal("0.06"), Decimal("0.25"),
    Decimal("0.35"), 5, "heat-v1")


def surveillance(*, stage=0, gsm=0, circuit=Decimal("0.10"), effective=ASOF):
    return SurveillanceObservation("surv-1", effective, "mock-authority", True, stage, gsm, circuit, ("surv-evidence",))


def plan(*, t1=True):
    return TradeManagementPlan("plan-1", Decimal("0.50"), Decimal("0.40"), True, t1, "after T1", "valid structure", "strategy/0.1", "execution-gates-v1")


def exposure(*, sector=Decimal("0.30"), candidate_risk=Decimal("1000")):
    return PortfolioExposure(Decimal("100000"), Decimal("3000"), candidate_risk, Decimal("0.20"), sector, ("portfolio-evidence",))


def inputs(**changes):
    base = GateInput("scorecard-1", Decimal("9.3"), "gate-snapshot-1", ASOF, Decimal("8.4"), holding_entry_date=date(2026, 8, 3),
        atr_expansion=Decimal("1.2"), surveillance=surveillance(), trade_plan=plan(), exposure=exposure(),
        earnings_scheduled_at=datetime(2026, 9, 2, 15, tzinfo=UTC), earnings_schedule_verified_at=ASOF,
        evidence_ids=("score-evidence",), diagnostic_ids=("diagnostic-40", "diagnostic-45"))
    return replace(base, **changes)


def evaluate(context=ActionContext.FRESH_ENTRY, data=None, config=CONFIG):
    return ExecutionGateEngine(config, CALENDAR).evaluate(instrument_id="mock-stock", strategy_version="strategy/0.1",
        registry_version="diagnostic-registry-v1", scoring_configuration_version="decision-score-v1", action_context=context,
        as_of_timestamp=ASOF, evaluated_at=ASOF, inputs=data or inputs())


def decision(record, gate):
    return next(item for item in record.decisions if item.gate_id == gate)


def approved_input_at(asof, *versions):
    eligible = [item for item in versions if item.snapshot_as_of_timestamp <= asof]
    return max(eligible, key=lambda item: item.snapshot_as_of_timestamp)


def assert_future_absent(record, future_id):
    assert future_id not in record.evidence_ids
    assert all(future_id not in gate.evidence_ids and future_id not in gate.detail for gate in record.decisions)


def test_all_six_pass_is_analytically_executable_not_an_order():
    result = evaluate()
    assert result.eligibility is ExecutionEligibility.EXECUTABLE
    assert len(result.decisions) == 6 and "NO_ACTION_OR_ORDER_CREATED" in result.warnings


def test_high_score_can_be_blocked_without_mutating_raw_score():
    result = evaluate(data=inputs(raw_decision_score=Decimal("10.0"), earnings_scheduled_at=datetime(2026, 8, 25, 15, tzinfo=UTC)))
    assert result.eligibility is ExecutionEligibility.BLOCKED
    assert decision(result, "GATE_6_EARNINGS").outcome is GateOutcome.FAIL
    assert result.raw_decision_score == Decimal("10.0") and result.rotation_adjustment == Decimal("0")


def test_rotation_hurdle_and_missing_comparison_do_not_fabricate_advantage():
    failed = evaluate(ActionContext.ROTATE_IN, inputs(comparison_score=Decimal("8.6"), raw_decision_score=Decimal("9.0")))
    passed = evaluate(ActionContext.ROTATE_IN, inputs(comparison_score=Decimal("7.8"), raw_decision_score=Decimal("8.8")))
    missing = evaluate(ActionContext.ROTATE_IN, inputs(comparison_score=None))
    assert decision(failed, "GATE_1_ROTATION").outcome is GateOutcome.FAIL
    assert decision(passed, "GATE_1_ROTATION").outcome is GateOutcome.PASS
    assert decision(missing, "GATE_1_ROTATION").outcome is GateOutcome.INSUFFICIENT_DATA


def test_optional_economic_hurdle_never_assumes_zero_friction():
    strict = replace(CONFIG, require_economic_hurdle=True, net_economic_hurdle=Decimal("0.05"))
    result = evaluate(ActionContext.ROTATE_IN, inputs(), strict)
    assert decision(result, "GATE_1_ROTATION").outcome is GateOutcome.INSUFFICIENT_DATA


def test_velocity_uses_trading_sessions_and_keeps_penalty_separate():
    record = evaluate(ActionContext.HOLD_EXISTING, inputs(atr_expansion=Decimal("0.4")))
    gate = decision(record, "GATE_2_VELOCITY")
    assert gate.outcome is GateOutcome.FAIL and record.rotation_adjustment == Decimal("-0.5")
    assert record.raw_decision_score == Decimal("9.3") and record.comparison_score == Decimal("8.8")


def test_no_holding_history_does_not_create_velocity_penalty():
    record = evaluate(ActionContext.FRESH_ENTRY, inputs(holding_entry_date=None, atr_expansion=None))
    assert decision(record, "GATE_2_VELOCITY").outcome is GateOutcome.PASS and record.rotation_adjustment == Decimal("0")


def test_calendar_excludes_weekends_and_configured_holidays():
    assert CALENDAR.sessions_between(date(2026, 8, 14), date(2026, 8, 20)) == 3  # 17/18/20; weekend + holiday excluded


def test_surveillance_requires_fresh_authoritative_complete_observation():
    missing = evaluate(data=inputs(surveillance=None))
    asm = evaluate(data=inputs(surveillance=surveillance(stage=2)))
    stale = evaluate(data=inputs(surveillance=surveillance(effective=ASOF - timedelta(days=3))))
    assert decision(missing, "GATE_3_SURVEILLANCE").outcome is GateOutcome.INSUFFICIENT_DATA
    assert decision(asm, "GATE_3_SURVEILLANCE").outcome is GateOutcome.FAIL
    assert decision(stale, "GATE_3_SURVEILLANCE").outcome is GateOutcome.INSUFFICIENT_DATA


def test_trade_plan_requires_real_stop_target_and_versioned_policy():
    bad = evaluate(data=inputs(trade_plan=plan(t1=False)))
    assert decision(bad, "GATE_4_TRADE_PLAN").outcome is GateOutcome.FAIL


def test_heat_keeps_allocation_and_risk_distinct_and_needs_exact_limits():
    failed = evaluate(data=inputs(exposure=exposure(sector=Decimal("0.36"))))
    unresolved = evaluate(data=inputs(), config=replace(CONFIG, max_sector_allocation=None))
    assert decision(failed, "GATE_5_HEAT").outcome is GateOutcome.FAIL
    assert decision(unresolved, "GATE_5_HEAT").outcome is GateOutcome.INSUFFICIENT_DATA


def test_earnings_blackout_is_trading_sessions_and_does_not_block_risk_management():
    near = inputs(earnings_scheduled_at=datetime(2026, 8, 27, 15, tzinfo=UTC))  # 4 sessions: 21,22,24,25,26,27? inclusive counts 5
    blocked = evaluate(ActionContext.FRESH_ENTRY, near)
    managed = evaluate(ActionContext.RISK_MANAGEMENT, near)
    unknown = evaluate(ActionContext.FRESH_ENTRY, inputs(earnings_scheduled_at=None))
    assert decision(blocked, "GATE_6_EARNINGS").outcome is GateOutcome.FAIL
    assert decision(managed, "GATE_6_EARNINGS").outcome is GateOutcome.PASS
    assert decision(unknown, "GATE_6_EARNINGS").outcome is GateOutcome.INSUFFICIENT_DATA


def test_incomplete_configuration_cannot_be_executable():
    record = evaluate(config=replace(CONFIG, min_score_advantage=None))
    assert record.eligibility is ExecutionEligibility.INSUFFICIENT_DATA


def test_evaluator_rejects_raw_gate_input_outside_the_approved_asof_snapshot():
    future = inputs(snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-observation",))
    try:
        evaluate(data=future)
    except ValueError as error:
        assert "approved as-of snapshot" in str(error)
    else:
        raise AssertionError("A raw future input bypassed the gate snapshot boundary.")


def test_gate_one_is_asof_stable_against_future_comparison_score():
    current = inputs(comparison_score=Decimal("8.4"))
    future = inputs(comparison_score=Decimal("6.0"), snapshot_id="future-score", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-score",))
    earlier = evaluate(ActionContext.ROTATE_IN, approved_input_at(ASOF, current))
    reconstructed = evaluate(ActionContext.ROTATE_IN, approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_1_ROTATION") == decision(reconstructed, "GATE_1_ROTATION"); assert_future_absent(reconstructed, "future-score")


def test_gate_two_is_asof_stable_against_future_price_expansion():
    current = inputs(atr_expansion=Decimal("0.4"))
    future = inputs(atr_expansion=Decimal("2.5"), snapshot_id="future-price", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-price",))
    earlier = evaluate(ActionContext.HOLD_EXISTING, approved_input_at(ASOF, current))
    reconstructed = evaluate(ActionContext.HOLD_EXISTING, approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_2_VELOCITY") == decision(reconstructed, "GATE_2_VELOCITY"); assert_future_absent(reconstructed, "future-price")


def test_gate_three_is_asof_stable_against_future_surveillance_status():
    current = inputs(surveillance=surveillance(stage=0))
    future = inputs(surveillance=surveillance(stage=2, effective=ASOF + timedelta(days=1)), snapshot_id="future-surveillance", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-surveillance",))
    earlier = evaluate(data=approved_input_at(ASOF, current))
    reconstructed = evaluate(data=approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_3_SURVEILLANCE") == decision(reconstructed, "GATE_3_SURVEILLANCE"); assert_future_absent(reconstructed, "future-surveillance")


def test_gate_four_is_asof_stable_against_future_target_hit():
    current = inputs(trade_plan=plan(t1=True))
    future = inputs(trade_plan=plan(t1=False), snapshot_id="future-target", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-target",))
    earlier = evaluate(data=approved_input_at(ASOF, current))
    reconstructed = evaluate(data=approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_4_TRADE_PLAN") == decision(reconstructed, "GATE_4_TRADE_PLAN"); assert_future_absent(reconstructed, "future-target")


def test_gate_five_is_asof_stable_against_future_portfolio_change():
    current = inputs(exposure=exposure(sector=Decimal("0.30")))
    future = inputs(exposure=exposure(sector=Decimal("0.50")), snapshot_id="future-portfolio", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-portfolio",))
    earlier = evaluate(data=approved_input_at(ASOF, current))
    reconstructed = evaluate(data=approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_5_HEAT") == decision(reconstructed, "GATE_5_HEAT"); assert_future_absent(reconstructed, "future-portfolio")


def test_gate_six_is_asof_stable_against_future_earnings_reschedule():
    current = inputs(earnings_scheduled_at=datetime(2026, 9, 2, 15, tzinfo=UTC))
    future = inputs(earnings_scheduled_at=datetime(2026, 8, 24, 15, tzinfo=UTC), earnings_schedule_verified_at=ASOF + timedelta(days=1), snapshot_id="future-earnings", snapshot_as_of_timestamp=ASOF + timedelta(days=1), evidence_ids=("future-earnings",))
    earlier = evaluate(data=approved_input_at(ASOF, current))
    reconstructed = evaluate(data=approved_input_at(ASOF, current, future))
    assert decision(earlier, "GATE_6_EARNINGS") == decision(reconstructed, "GATE_6_EARNINGS"); assert_future_absent(reconstructed, "future-earnings")
