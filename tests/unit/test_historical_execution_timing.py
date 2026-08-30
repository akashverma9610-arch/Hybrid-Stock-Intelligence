from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.execution_timing import HistoricalExecutionTimingAdapter
from app.backtest.models import BacktestEvent, BacktestEventType, ExecutionTimingPolicy, ExecutionTimingStatus
from app.backtest.signal_paper import HistoricalSignalPaperReplayService
from app.gates.engine import ExchangeCalendar
from app.paper.engine import PaperTradingEngine
from app.paper.models import PaperBar
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.signals.models import RevalidationInput, TriggerObservation
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.integration.test_historical_analytical_replay import setup
from tests.unit.test_paper_trading import CFG
from tests.unit.test_signal_lifecycle import create, plan


T = datetime(2026, 8, 20, 16, tzinfo=UTC)


def bar(identifier, at, close="106", *, known_at=None, valid=True, stale=False):
    close = Decimal(close)
    return PaperBar(identifier, at, known_at or at, close - 1, close + 1, close - 2, close, "daily", valid, stale)


def resolve(policy, *, trigger_at=T, trigger_known=None, bars=(), replay_at=None, calendar=None):
    signal, _ = create()
    trigger = TriggerObservation("trigger-observation", Decimal("106"), trigger_at, trigger_known or trigger_at, "daily", True)
    run = type("Run", (), {"backtest_run_id": "timing-run", "fingerprint": "timing-run-fingerprint"})()
    return HistoricalExecutionTimingAdapter(calendar or ExchangeCalendar("nse", frozenset())).resolve(
        run=run, policy=policy, signal=signal, plan=plan(), trigger=trigger, bars=tuple(bars),
        replay_timestamp=replay_at or trigger_at, replay_step_number=7,
    )


def test_generation_and_trigger_are_distinct_and_next_bar_open_excludes_trigger_bar():
    trigger_at = T + timedelta(days=3)
    result = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, trigger_at=trigger_at,
        bars=(bar("trigger-bar", trigger_at), bar("next-bar", trigger_at + timedelta(days=1))), replay_at=trigger_at + timedelta(days=1))
    assert result.trigger.trigger_timestamp == trigger_at and result.trigger.signal_id.startswith("signal-")
    assert result.context.status is ExecutionTimingStatus.ELIGIBLE
    assert result.context.selected_fill_bar_id == "next-bar"
    assert [item.bar_id for item in result.entry_and_management_bars] == ["next-bar"]


def test_next_bar_open_respects_weekend_and_holiday_calendar():
    friday = datetime(2026, 8, 21, 16, tzinfo=UTC)
    tuesday = datetime(2026, 8, 25, 16, tzinfo=UTC)
    calendar = ExchangeCalendar("nse", frozenset({date(2026, 8, 24)}))
    result = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, trigger_at=friday, calendar=calendar,
        bars=(bar("fri", friday), bar("tue", tuesday)), replay_at=tuesday)
    assert result.context.selected_fill_bar_id == "tue"
    assert {"2026-08-22", "2026-08-23", "2026-08-24"} <= set(result.context.skipped_session_dates)


def test_next_eligible_skips_stale_or_suspended_bars_but_next_open_fails_closed():
    trigger_at = T
    stale = bar("stale", T + timedelta(days=1), stale=True)
    good = bar("good", T + timedelta(days=4))
    eligible = resolve(ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR, bars=(bar("trigger", T), stale, good), replay_at=good.timestamp)
    strict = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, bars=(bar("trigger", T), stale, good), replay_at=good.timestamp)
    assert eligible.context.selected_fill_bar_id == "good" and eligible.context.skipped_bar_ids == ("stale",)
    assert strict.context.status is ExecutionTimingStatus.NON_TRADABLE and strict.context.selected_fill_bar_id is None


def test_next_bar_open_fails_closed_for_a_missing_normal_session_while_next_eligible_records_it():
    monday = datetime(2026, 8, 24, 16, tzinfo=UTC)
    wednesday = datetime(2026, 8, 26, 16, tzinfo=UTC)
    strict = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, trigger_at=monday,
        bars=(bar("mon", monday), bar("wed", wednesday)), replay_at=wednesday)
    eligible = resolve(ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR, trigger_at=monday,
        bars=(bar("mon", monday), bar("wed", wednesday)), replay_at=wednesday)
    assert strict.context.status is ExecutionTimingStatus.INSUFFICIENT_DATA and strict.context.selected_fill_bar_id is None
    assert eligible.context.selected_fill_bar_id == "wed" and "2026-08-25" in eligible.context.skipped_session_dates


def test_close_confirmation_is_a_signal_requirement_before_timing_can_begin():
    signal, _ = create()
    from app.signals.engine import SignalOrchestrator
    engine = SignalOrchestrator(__import__("tests.unit.test_signal_lifecycle", fromlist=["CONFIG"]).CONFIG, ExchangeCalendar("nse", frozenset()))
    intraday_only = TriggerObservation("intraday-cross", Decimal("106"), T, T, "daily", False)
    confirmed = TriggerObservation("close-confirmed", Decimal("106"), T + timedelta(days=1), T + timedelta(days=1), "daily", True)
    waiting = engine.revalidate(signal, plan(), (), RevalidationInput(T, T, "EXECUTABLE"), (intraday_only,))
    triggered = engine.revalidate(signal, plan(), (), RevalidationInput(T + timedelta(days=1), T + timedelta(days=1), "EXECUTABLE"), (confirmed,))
    assert waiting.resulting_status.value == "WAITING_FOR_TRIGGER"
    assert triggered.resulting_status.value == "TRIGGERED_ANALYTICALLY"


def test_signal_close_requires_knowledge_at_the_close_and_paper_engine_only_gets_legal_entry_window():
    legal = resolve(ExecutionTimingPolicy.SIGNAL_CLOSE, bars=(bar("close", T, "106"),), replay_at=T)
    illegal = resolve(ExecutionTimingPolicy.SIGNAL_CLOSE, trigger_known=T + timedelta(seconds=1), bars=(bar("close", T, "106", known_at=T),), replay_at=T + timedelta(seconds=1))
    assert legal.context.selected_fill_bar_id == "close" and legal.context.status is ExecutionTimingStatus.ELIGIBLE
    assert illegal.context.status is ExecutionTimingStatus.INVALID_TIMING and not illegal.entry_and_management_bars
    signal, _ = create(); trade = PaperTradingEngine(CFG, ExchangeCalendar("nse", frozenset())).create(signal, plan(), instrument_id="stock", generated_at=T)
    _, fills, _ = PaperTradingEngine(CFG, ExchangeCalendar("nse", frozenset())).simulate(trade, legal.entry_and_management_bars, T)
    assert fills and fills[0].source_bar_ids == ("close",)


def test_future_bar_is_not_eligible_until_replay_reaches_it():
    future = bar("future", T + timedelta(days=1))
    waiting = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, bars=(bar("trigger", T), future), replay_at=T)
    later = resolve(ExecutionTimingPolicy.NEXT_BAR_OPEN, bars=(bar("trigger", T), future), replay_at=future.timestamp)
    assert waiting.context.status is ExecutionTimingStatus.WAITING_FOR_NEXT_BAR and waiting.context.selected_fill_bar_id is None
    assert later.context.selected_fill_bar_id == "future"


def test_timing_context_persistence_round_trip_immutability_and_audit(tmp_path):
    repo, _manifest, schedule, _gap, run, _config = setup(tmp_path)
    schedule = replace(schedule, execution_timing_policy=ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR)
    repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    signal, created = create(); repo.save_signal(signal); repo.append_signal_event(created)
    trigger_at = T
    trigger = TriggerObservation("audit-trigger", Decimal("106"), trigger_at, trigger_at, "daily", True)
    bars = (bar("audit-trigger-bar", trigger_at), bar("audit-next", trigger_at + timedelta(days=1)))
    result = HistoricalExecutionTimingAdapter(ExchangeCalendar(schedule.exchange_calendar_reference, frozenset())).resolve(
        run=run, policy=schedule.execution_timing_policy, signal=signal, plan=plan(), trigger=trigger, bars=bars,
        replay_timestamp=trigger_at + timedelta(days=1), replay_step_number=3)
    repo.save_historical_trigger_timing_context(result.trigger); repo.save_historical_execution_timing_context(result.context)
    assert repo.get_historical_trigger_timing_context(result.trigger.trigger_context_id) == result.trigger
    assert repo.get_historical_execution_timing_context(result.context.context_id) == result.context
    with pytest.raises(ValueError, match="immutable"): repo.save_historical_execution_timing_context(result.context)
    with pytest.raises(ValueError, match="immutable"): repo.save_historical_trigger_timing_context(result.trigger)
    assert AuditReconstructionService(repo).reconstruct_historical_execution_timing_context(result.context.context_id, bars=bars, calendar=ExchangeCalendar(schedule.exchange_calendar_reference, frozenset()))[0] == result.context
    tampered = replace(result.context, selected_fill_bar_id="audit-trigger-bar")
    repo._connection.execute("UPDATE historical_execution_timing_contexts SET payload_json=? WHERE id=?", (__import__("json").dumps(__import__("app.backtest.serialization", fromlist=["dump"]).dump(tampered)), result.context.context_id))
    with pytest.raises(AuditReconstructionError, match="mismatch"):
        AuditReconstructionService(repo).reconstruct_historical_execution_timing_context(result.context.context_id, bars=bars, calendar=ExchangeCalendar(schedule.exchange_calendar_reference, frozenset()))


def test_service_passes_only_timing_approved_entry_and_management_window_to_paper_engine(tmp_path):
    repo, _manifest, schedule, _gap, run, _config = setup(tmp_path)
    schedule = replace(schedule, execution_timing_policy=ExecutionTimingPolicy.NEXT_BAR_OPEN)
    repo.save_replay_schedule(schedule); repo.save_backtest_run(run)
    repo.append_backtest_event(BacktestEvent("timing-start", run.backtest_run_id, BacktestEventType.REPLAY_STARTED, T, 0, T, (), "start", {}, T))
    signal, created = create(); repo.save_signal(signal); repo.append_signal_event(created); repo.save_trade_plan(plan())
    service = HistoricalSignalPaperReplayService(repo, ExchangeCalendar(schedule.exchange_calendar_reference, frozenset()), __import__("tests.unit.test_signal_lifecycle", fromlist=["CONFIG"]).CONFIG, CFG)
    trigger = TriggerObservation("service-trigger", Decimal("106"), T, T, "daily", True)
    next_bar = bar("service-next", T + timedelta(days=1), "112")
    event, trade, outcome = service.replay_signal(signal_id=signal.signal_id, at=next_bar.timestamp,
        revalidation=RevalidationInput(next_bar.timestamp, next_bar.timestamp, "EXECUTABLE"), triggers=(trigger,),
        bars=(bar("service-trigger-bar", T), next_bar), run=run, replay_step_number=4)
    context = service.last_execution_timing_context
    assert event.resulting_status.value == "TRIGGERED_ANALYTICALLY"
    assert context is not None and context.selected_fill_bar_id == "service-next"
    assert trade is not None and outcome is not None and outcome.entry_timestamp == next_bar.timestamp
    events = repo.list_backtest_events(run.backtest_run_id)
    assert [event.event_type.value for event in events[-3:]] == ["EXECUTION_TIMING_RESOLVED", "PAPER_TRADE_CREATED", "PAPER_TRADE_OPENED"]
