from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.backtest.execution_timing import HistoricalExecutionTimingAdapter
from app.backtest.models import ExecutionTimingPolicy, ExecutionTimingStatus
from app.gates.engine import ExchangeCalendar
from app.paper.engine import PaperTradingEngine
from app.paper.models import InvalidationPolicy, PaperBar, PaperTradeState, SameBarPolicy
from app.signals.engine import SignalOrchestrator
from app.signals.models import RevalidationInput, SignalStatus, TriggerObservation
from tests.unit.test_paper_trading import CFG
from tests.unit.test_signal_lifecycle import CONFIG, create, plan


T = datetime(2026, 8, 20, 16, tzinfo=UTC)  # Thursday
CALENDAR = ExchangeCalendar("nse", frozenset())


def bar(identifier, at, opening, high, low, close, *, valid=True, stale=False):
    return PaperBar(identifier, at, at, Decimal(opening), Decimal(high), Decimal(low), Decimal(close), "daily", valid, stale)


def through_timing(*, bars, replay_at, config=CFG, policy=ExecutionTimingPolicy.NEXT_BAR_OPEN):
    signal, _ = create()
    trigger = TriggerObservation("matrix-trigger", Decimal("106"), T, T, "daily", True)
    run = type("Run", (), {"backtest_run_id": "matrix-run", "fingerprint": "matrix-run-v1"})()
    resolved = HistoricalExecutionTimingAdapter(CALENDAR).resolve(run=run, policy=policy, signal=signal, plan=plan(), trigger=trigger,
        bars=tuple(bars), replay_timestamp=replay_at, replay_step_number=5)
    if resolved.context.status is not ExecutionTimingStatus.ELIGIBLE:
        return signal, resolved, None, (), (), None
    triggered = replace(signal, status=SignalStatus.TRIGGERED_ANALYTICALLY)
    engine = PaperTradingEngine(config, CALENDAR)
    trade = engine.create(triggered, plan(), instrument_id="stock", generated_at=replay_at)
    events, fills, outcome = engine.simulate(trade, resolved.entry_and_management_bars, replay_at)
    return signal, resolved, trade, events, fills, outcome


def test_waiting_expiry_cancellation_and_pre_entry_invalidation_are_append_only_and_terminal():
    signal, created = create(); engine = SignalOrchestrator(CONFIG, CALENDAR)
    waiting = engine.revalidate(signal, plan(), (created,), RevalidationInput(T, T, "EXECUTABLE"), ())
    expired = engine.revalidate(signal, plan(), (created, waiting), RevalidationInput(T + timedelta(days=8), T + timedelta(days=8), "EXECUTABLE"), ())
    cancelled = engine.revalidate(signal, plan(), (created,), RevalidationInput(T + timedelta(days=1), T + timedelta(days=1), "EXECUTABLE", catalyst_cancelled=True), ())
    invalidated = engine.revalidate(signal, plan(), (created,), RevalidationInput(T + timedelta(days=1), T + timedelta(days=1), "EXECUTABLE", invalidation_triggered=True), ())
    assert waiting.resulting_status is SignalStatus.WAITING_FOR_TRIGGER
    assert expired.resulting_status is SignalStatus.EXPIRED
    assert cancelled.resulting_status is SignalStatus.CANCELLED
    assert invalidated.resulting_status is SignalStatus.INVALIDATED
    assert signal.status is SignalStatus.WAITING_FOR_TRIGGER and created.event_timestamp == signal.generated_at


def test_profitable_t1_t2_path_keeps_exact_timing_window_and_excursions_after_fill_only():
    entry = bar("entry", T + timedelta(days=1), "106", "108", "105", "106")
    t1 = bar("t1", T + timedelta(days=4), "106", "126", "105", "124")
    t2 = bar("t2", T + timedelta(days=5), "124", "136", "120", "135")
    post_close = bar("post-close", T + timedelta(days=6), "135", "999", "1", "500")
    signal, resolved, trade, events, fills, outcome = through_timing(bars=(bar("trigger", T, "100", "140", "90", "106"), entry, t1, t2, post_close), replay_at=post_close.timestamp)
    assert resolved.context.selected_fill_bar_id == "entry" and fills[0].timestamp == entry.timestamp
    assert [event.event_type.value for event in events] == ["CREATED", "TRIGGERED", "FILLED", "T1", "T2"]
    assert outcome.state is PaperTradeState.CLOSED_TARGET and outcome.t1_reached and outcome.t2_reached
    assert outcome.entry_timestamp == entry.timestamp and outcome.final_exit_timestamp == t2.timestamp
    assert outcome.mfe == Decimal("30") and outcome.mae == Decimal("-1")
    assert outcome.entry_timestamp - T == timedelta(days=1) and t1.timestamp - outcome.entry_timestamp == timedelta(days=3)
    assert signal.status is SignalStatus.WAITING_FOR_TRIGGER and trade.planned_entry == Decimal("105")


def test_stop_gap_same_bar_and_breakeven_residual_paths_use_canonical_paper_engine():
    entry = bar("entry", T + timedelta(days=1), "106", "108", "105", "106")
    gap_stop = bar("gap-stop", T + timedelta(days=4), "90", "96", "89", "92")
    _, _, _, _, _, stopped = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), entry, gap_stop), replay_at=gap_stop.timestamp)
    assert stopped.state is PaperTradeState.CLOSED_STOP and stopped.final_exit_price == Decimal("90") and stopped.stop_hit
    both = bar("both", T + timedelta(days=4), "106", "126", "94", "110")
    _, _, _, _, _, conservative = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), entry, both), replay_at=both.timestamp)
    unresolved_cfg = replace(CFG, same_bar_policy=SameBarPolicy.UNRESOLVED)
    _, _, _, _, _, unresolved = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), entry, both), replay_at=both.timestamp, config=unresolved_cfg)
    assert conservative.state is PaperTradeState.CLOSED_STOP and unresolved.state is PaperTradeState.INSUFFICIENT_DATA
    t1 = bar("t1", T + timedelta(days=4), "106", "126", "105", "124")
    breakeven = bar("breakeven", T + timedelta(days=5), "106", "107", "105", "106")
    original_plan = plan()
    _, _, trade, events, _, outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), entry, t1, breakeven), replay_at=breakeven.timestamp)
    assert any(event.event_type.value == "T1" for event in events) and outcome.final_exit_price == Decimal("106") and outcome.stop_hit
    assert trade.structural_stop == original_plan.structural_stop and original_plan.structural_stop == Decimal("95")


def test_post_entry_invalidation_record_only_and_time_stop_follow_frozen_policy():
    entry = bar("entry", T + timedelta(days=1), "106", "108", "105", "106")
    invalid = bar("invalid", T + timedelta(days=4), "107", "110", "105", "108")
    base_bars = (bar("trigger", T, "100", "106", "99", "106"), entry, invalid)
    _, _, _, events, _, exited = through_timing(bars=base_bars, replay_at=invalid.timestamp)
    # No invalidation was supplied: an ordinary outcome remains open.
    assert exited.state is PaperTradeState.OPEN
    signal, resolved, trade, _, _, _ = through_timing(bars=base_bars, replay_at=invalid.timestamp)
    engine = PaperTradingEngine(CFG, CALENDAR)
    _, _, invalidated = engine.simulate(trade, resolved.entry_and_management_bars, invalid.timestamp, invalidation_at=invalid.timestamp)
    record_only = PaperTradingEngine(replace(CFG, invalidation_policy=InvalidationPolicy.RECORD_ONLY), CALENDAR)
    _, _, retained = record_only.simulate(trade, resolved.entry_and_management_bars, invalid.timestamp, invalidation_at=invalid.timestamp)
    assert invalidated.state is PaperTradeState.CLOSED_INVALIDATION and invalidated.final_exit_timestamp == invalid.timestamp
    assert retained.state is PaperTradeState.OPEN
    final = bar("time-stop", T + timedelta(days=11), "107", "110", "105", "108")
    _, _, _, time_events, _, time_outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), entry, final), replay_at=final.timestamp)
    assert time_outcome.state is PaperTradeState.CLOSED_EXPIRY and time_events[-1].timestamp == final.timestamp


def test_stale_missing_and_future_bars_fail_closed_without_rewriting_earlier_result():
    stale = bar("stale-next", T + timedelta(days=1), "106", "108", "105", "106", stale=True)
    signal, stale_resolved, trade, events, fills, outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), stale), replay_at=stale.timestamp)
    assert stale_resolved.context.status is ExecutionTimingStatus.NON_TRADABLE and trade is None and outcome is None
    future = bar("future-target", T + timedelta(days=4), "106", "140", "105", "135")
    _, early, early_trade, _, _, early_outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), future), replay_at=T)
    assert early.context.status is ExecutionTimingStatus.WAITING_FOR_NEXT_BAR and early_trade is None and early_outcome is None
    missing = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), future), replay_at=future.timestamp)
    assert missing[1].context.status is ExecutionTimingStatus.INSUFFICIENT_DATA


def test_gap_entry_and_invalid_or_suspended_bar_boundaries_never_fabricate_prices_or_updates():
    gap_entry = bar("gap-entry", T + timedelta(days=1), "112", "114", "111", "112")
    _, resolved, _, _, fills, outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), gap_entry), replay_at=gap_entry.timestamp)
    assert resolved.context.selected_fill_bar_id == "gap-entry" and fills[0].price == Decimal("112") and outcome.entry_price != Decimal("105")
    invalid = bar("invalid-next", T + timedelta(days=1), "106", "108", "105", "106", valid=False)
    suspended = bar("suspended-next", T + timedelta(days=1), "106", "108", "105", "106", stale=True)
    for candidate in (invalid, suspended):
        _, context, trade, events, fills, outcome = through_timing(bars=(bar("trigger", T, "100", "106", "99", "106"), candidate), replay_at=candidate.timestamp)
        assert context.context.status is ExecutionTimingStatus.NON_TRADABLE and trade is None and not fills and outcome is None
