from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.backtest.engine import (
    BacktestReplayEngine, ReplayDataGap, ReplayLookaheadRejected, ReplayStepHandlerResult,
    ReplayClock, backtest_run_fingerprint,
)
from app.backtest.models import *
from app.gates.engine import ExchangeCalendar
from app.historical.models import *
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


START = datetime(2026, 1, 2, 0, tzinfo=UTC)  # Friday
END = datetime(2026, 1, 7, 23, 59, tzinfo=UTC)  # Wednesday; Tuesday is a holiday
CALENDAR = ExchangeCalendar("nse-test-v1", frozenset({datetime(2026, 1, 6).date()}))


def manifest(identifier="dataset-v1", version="1", fingerprint="dataset-fingerprint"):
    return HistoricalDatasetManifest(
        identifier, version, START, START, END, CALENDAR.calendar_id, "nifty-500-v1",
        {"market": ["stock-bars-v1", "index-bars-v1"], "sector": ["sector-bars-v1"]},
        {"source": "deterministic-fixture"}, DatasetQuality.HIGH_QUALITY, (), "raw-v1",
        SurvivorshipStatus.POINT_IN_TIME_UNIVERSE, "FULL", (), fingerprint,
    )


def schedule():
    return ReplaySchedule("daily-close", "1", ReplayFrequency.DAILY_CLOSE, "UTC", CALENDAR.calendar_id,
                          "TRADING_SESSION_CLOSE", ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR, START, END,
                          ("No intraday replay is implemented.",))


def policy(behavior=BacktestDataGapBehavior.FAIL_RUN):
    return BacktestDataGapPolicy(f"gap-{behavior.value.lower()}", "1", behavior, ("No forward fill.",))


def run(identifier, data_manifest, gap, partition=None):
    value = BacktestRun(
        identifier, data_manifest.dataset_id, data_manifest.dataset_version, data_manifest.fingerprint,
        partition.partition_id if partition else None, "strategy-v1", "registry-v1", "scoring-v1", "gates-v1",
        "rotation-v1", "signals-v1", "paper-v1", "performance-v1", "backtest-v1", schedule().schedule_id,
        schedule().version, gap.policy_id, gap.version, CALENDAR.calendar_id, "calendar-v1", START, END,
        Decimal("1000000"), "cost-v1", "slippage-v1", "nifty-500-v1", (41, 99), BacktestRunStatus.CREATED,
        DatasetQuality.HIGH_QUALITY, EvaluationLabel.IN_SAMPLE, (), ("No diagnostic or trading integration.",), "", START,
    )
    return replace(value, fingerprint=backtest_run_fingerprint(value))


def repository(tmp_path, data_manifest=None):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "backtest.db")
    data_manifest = data_manifest or manifest()
    repo.save_historical_manifest(data_manifest)
    return repo, data_manifest


def test_daily_close_clock_excludes_weekend_and_holiday_and_is_monotonic():
    timestamps = ReplayClock(schedule(), CALENDAR).timestamps()
    assert [value.date().isoformat() for value in timestamps] == ["2026-01-02", "2026-01-05", "2026-01-07"]
    assert timestamps == tuple(sorted(timestamps))


def test_partition_clock_stays_inside_train_window(tmp_path):
    repo, data_manifest = repository(tmp_path)
    partition = HistoricalPartition("train", data_manifest.dataset_id, PartitionType.TRAIN, START,
                                    datetime(2026, 1, 5, 23, 59, tzinfo=UTC), 2, 1, "training only", START)
    repo.save_historical_partition(partition)
    result = BacktestReplayEngine(repo).run(run("run-train", data_manifest, policy(), partition), schedule(), CALENDAR,
                                             policy(), partition)
    assert [value.date().isoformat() for value in result.timestamps] == ["2026-01-02", "2026-01-05"]
    assert all(partition.start <= value <= partition.end for value in result.timestamps)
    assert result.status is BacktestRunStatus.COMPLETED


def test_models_round_trip_and_duplicate_ids_are_immutable(tmp_path):
    repo, data_manifest = repository(tmp_path)
    gap = policy()
    replay_schedule = schedule()
    backtest_run = run("run-round-trip", data_manifest, gap)
    step = BacktestReplayStep("step-round-trip", backtest_run.backtest_run_id, 1, datetime(2026, 1, 2, 15, 30, tzinfo=UTC),
                               "2026-01-02", ReplayStepStatus.COMPLETED, ("snapshot-later",), ("fixture",))
    event = BacktestEvent("event-round-trip", backtest_run.backtest_run_id, BacktestEventType.REPLAY_STARTED,
                          step.evaluation_timestamp, 0, step.evaluation_timestamp, ("manifest-1",), "started", {"v": 1}, step.evaluation_timestamp)
    repo.save_replay_schedule(replay_schedule); repo.save_backtest_data_gap_policy(gap); repo.save_backtest_run(backtest_run)
    repo.save_backtest_replay_step(step); repo.append_backtest_event(event)
    assert repo.get_replay_schedule(replay_schedule.schedule_id) == replay_schedule
    assert repo.get_backtest_data_gap_policy(gap.policy_id) == gap
    assert repo.get_backtest_run(backtest_run.backtest_run_id) == backtest_run
    assert repo.get_backtest_replay_step(step.replay_step_id) == step
    assert repo.get_backtest_event(event.event_id) == event
    assert repo.list_backtest_replay_steps(backtest_run.backtest_run_id) == (step,)
    assert repo.list_backtest_events(backtest_run.backtest_run_id) == (event,)
    for save, value in ((repo.save_replay_schedule, replay_schedule), (repo.save_backtest_data_gap_policy, gap),
                        (repo.save_backtest_run, backtest_run), (repo.save_backtest_replay_step, step),
                        (repo.append_backtest_event, event)):
        with pytest.raises(ValueError):
            save(value)


def test_event_lifecycle_rejects_backward_order_and_terminal_rewrites(tmp_path):
    repo, data_manifest = repository(tmp_path)
    gap = policy(); replay_schedule = schedule(); backtest_run = run("run-event-order", data_manifest, gap)
    repo.save_replay_schedule(replay_schedule); repo.save_backtest_data_gap_policy(gap); repo.save_backtest_run(backtest_run)
    first = ReplayClock(replay_schedule, CALENDAR).timestamps()[0]
    repo.append_backtest_event(BacktestEvent("started", backtest_run.backtest_run_id, BacktestEventType.REPLAY_STARTED,
                                             first, 0, first, (), "started", {}, first))
    with pytest.raises(ValueError, match="timestamps must not move backward"):
        repo.append_backtest_event(BacktestEvent("backward", backtest_run.backtest_run_id, BacktestEventType.REPLAY_STEP_STARTED,
                                                 START, 1, START, (), "invalid", {}, START))
    repo.append_backtest_event(BacktestEvent("completed", backtest_run.backtest_run_id, BacktestEventType.REPLAY_COMPLETED,
                                             first, 0, first, (), "complete", {}, first))
    with pytest.raises(ValueError, match="terminal"):
        repo.append_backtest_event(BacktestEvent("rewrite", backtest_run.backtest_run_id, BacktestEventType.REPLAY_FAILED,
                                                 first, 0, first, (), "invalid rewrite", {}, first))


@pytest.mark.parametrize("behavior,expected_status,expected_step", [
    (BacktestDataGapBehavior.FAIL_RUN, BacktestRunStatus.FAILED, ReplayStepStatus.FAILED),
    (BacktestDataGapBehavior.SKIP_STEP, BacktestRunStatus.COMPLETED, ReplayStepStatus.SKIPPED),
    (BacktestDataGapBehavior.MARK_INSUFFICIENT_DATA, BacktestRunStatus.INSUFFICIENT_DATA, ReplayStepStatus.INSUFFICIENT_DATA),
])
def test_data_gap_policy_is_explicit_and_never_fabricates_inputs(tmp_path, behavior, expected_status, expected_step):
    repo, data_manifest = repository(tmp_path)
    gap = policy(behavior)
    calls = 0

    def handler(_context):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ReplayDataGap("missing stock bar")
        return ReplayStepHandlerResult()

    result = BacktestReplayEngine(repo).run(run(f"run-gap-{behavior.value}", data_manifest, gap), schedule(), CALENDAR, gap, handler=handler)
    assert result.status is expected_status
    assert result.steps[0].status is expected_step
    assert any(event.event_type is BacktestEventType.DATA_INSUFFICIENT for event in result.events)
    if behavior is BacktestDataGapBehavior.SKIP_STEP:
        assert len(result.steps) == 3 and result.steps[-1].status is ReplayStepStatus.COMPLETED


def test_placeholder_handler_cannot_bypass_existing_lookahead_guard(tmp_path):
    repo, data_manifest = repository(tmp_path)
    gap = policy()

    def future_reader(context):
        future = HistoricalFact("future-stock-bar", "stock_bar", context.evaluation_timestamp.replace(day=3),
                                context.evaluation_timestamp.replace(day=3), context.evaluation_timestamp.replace(day=3))
        context.require_eligible(future)
        raise AssertionError("Future observation must not be consumed.")

    result = BacktestReplayEngine(repo).run(run("run-lookahead", data_manifest, gap), schedule(), CALENDAR, gap, handler=future_reader)
    assert result.status is BacktestRunStatus.FAILED
    assert {event.event_type for event in result.events} >= {BacktestEventType.LOOKAHEAD_REJECTED, BacktestEventType.REPLAY_FAILED}
    assert "future-stock-bar" in result.steps[0].failure_reason


def test_failure_and_cancellation_preserve_prior_event_history(tmp_path):
    repo, data_manifest = repository(tmp_path)
    gap = policy()
    result = BacktestReplayEngine(repo).run(run("run-failure", data_manifest, gap), schedule(), CALENDAR, gap,
                                             handler=lambda _context: (_ for _ in ()).throw(RuntimeError("fixture failure")))
    assert result.status is BacktestRunStatus.FAILED
    before = repo.list_backtest_events("run-failure")
    with pytest.raises(ValueError):
        BacktestReplayEngine(repo).cancel("run-failure", END)
    assert repo.list_backtest_events("run-failure") == before

    cancelled = BacktestReplayEngine(repo).run(run("run-cancel", data_manifest, gap), schedule(), CALENDAR, gap,
                                                handler=lambda _context: ReplayStepHandlerResult(cancel=True))
    assert cancelled.status is BacktestRunStatus.CANCELLED
    assert cancelled.events[-1].event_type is BacktestEventType.REPLAY_CANCELLED


def test_audit_reconstructs_frozen_run_and_detects_step_mismatch(tmp_path):
    repo, data_manifest = repository(tmp_path)
    gap = policy()
    completed = BacktestReplayEngine(repo).run(run("run-audit", data_manifest, gap), schedule(), CALENDAR, gap)
    reconstruction = AuditReconstructionService(repo).reconstruct_backtest_run("run-audit", CALENDAR)
    assert reconstruction.final_status is BacktestRunStatus.COMPLETED
    assert reconstruction.timestamps == completed.timestamps
    assert reconstruction.steps == completed.steps
    bad_run = run("run-audit-bad", data_manifest, gap)
    repo.save_replay_schedule(schedule()) if repo.get_replay_schedule(schedule().schedule_id) is None else None
    repo.save_backtest_data_gap_policy(gap) if repo.get_backtest_data_gap_policy(gap.policy_id) is None else None
    repo.save_backtest_run(bad_run)
    first = ReplayClock(schedule(), CALENDAR).timestamps()[0]
    repo.append_backtest_event(BacktestEvent("bad-start", bad_run.backtest_run_id, BacktestEventType.REPLAY_STARTED, first, 0, first, (), "start", {}, first))
    repo.save_backtest_replay_step(BacktestReplayStep("bad-step", bad_run.backtest_run_id, 1, END, "2026-01-07", ReplayStepStatus.COMPLETED))
    with pytest.raises(AuditReconstructionError, match="does not match"):
        AuditReconstructionService(repo).reconstruct_backtest_run("run-audit-bad", CALENDAR)
    assert repo.get_backtest_replay_step("bad-step").evaluation_timestamp == END


def test_run_a_and_b_are_frozen_and_replay_is_reproducible(tmp_path):
    repo, v1 = repository(tmp_path)
    gap = policy()
    engine = BacktestReplayEngine(repo)
    a = engine.run(run("run-a", v1, gap), schedule(), CALENDAR, gap)
    stored_a = repo.get_backtest_run("run-a"); events_a = repo.list_backtest_events("run-a")
    same_inputs = engine.run(run("run-same-inputs", v1, gap), schedule(), CALENDAR, gap)
    v2 = manifest("dataset-v2", "2", "dataset-fingerprint-v2")
    repo.save_historical_manifest(v2)
    b = engine.run(run("run-b", v2, gap), schedule(), CALENDAR, gap)
    assert stored_a.dataset_manifest_id == v1.dataset_id and stored_a.dataset_fingerprint == v1.fingerprint
    assert repo.list_backtest_events("run-a") == events_a
    assert a.timestamps == same_inputs.timestamps == b.timestamps
    assert [(event.event_type, event.event_timestamp, event.replay_step_number, event.evaluation_timestamp,
             event.message, event.metadata) for event in a.events] == [
        (event.event_type, event.event_timestamp, event.replay_step_number, event.evaluation_timestamp,
         event.message, event.metadata) for event in same_inputs.events
    ]
    assert a.events != same_inputs.events  # immutable IDs retain their distinct run identity
    assert repo.get_backtest_run("run-b").dataset_manifest_id == v2.dataset_id
    assert stored_a.fingerprint != repo.get_backtest_run("run-b").fingerprint
