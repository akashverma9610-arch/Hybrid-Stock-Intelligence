from datetime import UTC, datetime
import inspect
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.market_data.models import MarketSessionState
from app.runtime.cycle import RuntimeCycleStatus, RuntimeMode
from app.runtime.scheduler import (
    RuntimeHealthService,
    RuntimeScheduler,
    RuntimeSchedulerEventType,
    RuntimeSchedulerSettings,
)


T = datetime(2026, 8, 24, 10, tzinfo=UTC)


class CycleCoordinator:
    def __init__(self, *, failure: bool = False) -> None:
        self.failure = failure
        self.calls: list[RuntimeMode] = []

    def run_cycle(self, *, mode: RuntimeMode = RuntimeMode.STORED_DATA):
        self.calls.append(mode)
        if self.failure:
            raise RuntimeError("deterministic fixture failure")
        return SimpleNamespace(
            cycle_id=f"cycle-{len(self.calls)}",
            overall_status=RuntimeCycleStatus.PARTIAL,
            completed_at=T,
            data_as_of=T,
            warnings=("PARTIAL_SOURCE_COVERAGE",),
        )


def scheduler(coordinator: CycleCoordinator | None = None, **kwargs) -> RuntimeScheduler:
    return RuntimeScheduler(coordinator or CycleCoordinator(), clock=lambda: T, **kwargs)


def test_default_settings_are_disabled_and_environment_is_typed():
    assert RuntimeSchedulerSettings() == RuntimeSchedulerSettings(enabled=False, interval_seconds=300)
    parsed = RuntimeSchedulerSettings.from_environment({
        "RUNTIME_SCHEDULER_ENABLED": "true",
        "RUNTIME_CYCLE_INTERVAL_SECONDS": "60",
        "RUNTIME_MODE": "mock",
        "RUNTIME_UNIVERSE_ID": "NIFTY_50",
    })
    assert parsed == RuntimeSchedulerSettings(True, 60, RuntimeMode.MOCK, "NIFTY_50")
    with pytest.raises(ValueError, match="positive"):
        RuntimeSchedulerSettings.from_environment({"RUNTIME_CYCLE_INTERVAL_SECONDS": "0"})
    with pytest.raises(ValueError, match="boolean"):
        RuntimeSchedulerSettings.from_environment({"RUNTIME_SCHEDULER_ENABLED": "maybe"})


def test_run_once_is_manual_when_disabled_and_updates_read_only_health():
    runner = CycleCoordinator()
    value = scheduler(runner).run_once()
    assert value.cycle_id == "cycle-1" and runner.calls == [RuntimeMode.STORED_DATA]
    health = RuntimeHealthService(scheduler(runner)).status()
    assert health.scheduler_enabled is False and health.scheduler_running is False
    completed_health = RuntimeScheduler(runner, clock=lambda: T)
    completed_health.run_once()
    assert completed_health.status().last_cycle_id == "cycle-2"
    assert completed_health.status().last_cycle_status is RuntimeCycleStatus.PARTIAL
    assert completed_health.status().last_success_at == T


def test_start_stop_is_opt_in_idempotent_and_records_safe_events():
    runner = scheduler(settings=RuntimeSchedulerSettings(enabled=True))
    assert runner.start() is True and runner.start() is False
    assert runner.status().scheduler_running is True
    assert runner.stop() is True and runner.stop() is False
    assert [event.event_type for event in runner.events()] == [
        RuntimeSchedulerEventType.SCHEDULER_STARTED,
        RuntimeSchedulerEventType.SCHEDULER_STOPPED,
    ]
    assert scheduler().start() is False


def test_closed_session_skips_without_failure_and_post_close_remains_explicitly_safe():
    closed_coordinator = CycleCoordinator()
    closed = scheduler(closed_coordinator, session=lambda: MarketSessionState.CLOSED)
    assert closed.run_once() is None and closed_coordinator.calls == []
    assert closed.status().consecutive_failures == 0 and closed.status().warnings == ("MARKET_CLOSED",)
    assert closed.events()[-1].event_type is RuntimeSchedulerEventType.SCHEDULER_CYCLE_SKIPPED
    post_close_coordinator = CycleCoordinator()
    assert scheduler(post_close_coordinator, session=lambda: MarketSessionState.POST_CLOSE).run_once().cycle_id == "cycle-1"


def test_failure_is_bounded_then_success_resets_failure_counter_without_retry_loop():
    failing = CycleCoordinator(failure=True)
    runner = scheduler(failing)
    assert runner.run_once() is None and failing.calls == [RuntimeMode.STORED_DATA]
    assert runner.status().consecutive_failures == 1 and runner.status().last_failure_at == T
    assert runner.events()[-1].event_type is RuntimeSchedulerEventType.SCHEDULER_CYCLE_FAILED
    failing.failure = False
    assert runner.run_once().cycle_id == "cycle-2"
    assert runner.status().consecutive_failures == 0 and runner.status().last_success_at == T


def test_overlapping_cycle_is_denied_without_calling_coordinator():
    coordinator = CycleCoordinator()
    runner = scheduler(coordinator)
    assert runner._cycle_lock.acquire(blocking=False) is True
    try:
        assert runner.run_once() is None
    finally:
        runner._cycle_lock.release()
    assert coordinator.calls == [] and runner.status().warnings == ("CYCLE_ALREADY_RUNNING",)


def test_fastapi_startup_does_not_create_or_start_a_runtime_scheduler_by_default():
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert not hasattr(client.app.state, "runtime_scheduler")
    import app.api.main as main
    assert "RuntimeWorker" not in inspect.getsource(main)


def test_scheduler_has_no_provider_broker_or_governance_side_effects():
    import app.runtime.scheduler as scheduler_module
    source = inspect.getsource(scheduler_module).lower()
    assert not any(token in source for token in ("kotak", "websocket", "requests.", "place_order", "demat", "promotion", "activation", "self_improvement"))
