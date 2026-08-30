from datetime import UTC, datetime
from threading import Event
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.runtime.cli import main
from app.runtime.cycle import RuntimeCycleStatus, RuntimeMode
from app.runtime.scheduler import RuntimeHealthService, RuntimeScheduler, RuntimeSchedulerEventType, RuntimeSchedulerSettings, RuntimeWorker


T = datetime(2026, 8, 25, 10, tzinfo=UTC)


class Coordinator:
    def __init__(self, *, status: RuntimeCycleStatus = RuntimeCycleStatus.SUCCESS, fail: bool = False) -> None:
        self.status, self.fail, self.calls, self.publishes = status, fail, [], []

    def run_cycle(self, *, mode=RuntimeMode.STORED_DATA, publish=True):
        self.calls.append(mode)
        self.publishes.append(publish)
        if self.fail:
            raise RuntimeError("fixture failure")
        return SimpleNamespace(
            cycle_id="cycle-cli", overall_status=self.status, completed_at=T, data_as_of=T,
            warnings=(), mode=mode, universe_id="BROAD_5", snapshots_written=("snapshot-1",) if publish else (), stage_results=(),
        )


def runtime_scheduler(coordinator=None, *, enabled=False):
    return RuntimeScheduler(coordinator or Coordinator(), RuntimeSchedulerSettings(enabled=enabled, interval_seconds=5, universe_id="BROAD_5"), clock=lambda: T)


def test_cli_run_once_success_partial_failure_dry_run_and_safe_output(monkeypatch):
    monkeypatch.setenv("RUNTIME_UNIVERSE_ID", "BROAD_5")
    monkeypatch.setenv("KOTAK_NEO_TRADEAPI_ACCESS_TOKEN", "never-print-this")
    messages: list[str] = []
    successful = Coordinator()
    assert main(["run-once"], scheduler_factory=lambda settings: RuntimeScheduler(successful, settings, clock=lambda: T), output=messages.append) == 0
    assert successful.publishes == [True] and "never-print-this" not in "\n".join(messages)
    partial = Coordinator(status=RuntimeCycleStatus.PARTIAL)
    assert main(["run-once", "--dry-run", "--mode", "mock"], scheduler_factory=lambda settings: RuntimeScheduler(partial, settings, clock=lambda: T), output=lambda _: None) == 2
    assert partial.calls == [RuntimeMode.MOCK] and partial.publishes == [False]
    failed = Coordinator(fail=True)
    assert main(["run-once"], scheduler_factory=lambda settings: RuntimeScheduler(failed, settings, clock=lambda: T), output=lambda _: None) == 1


def test_cli_status_does_not_create_or_execute_a_cycle_and_invalid_config_is_safe(monkeypatch):
    monkeypatch.delenv("RUNTIME_UNIVERSE_ID", raising=False)
    messages: list[str] = []
    assert main(["status"], scheduler_factory=lambda _: (_ for _ in ()).throw(AssertionError("factory must not run")), output=messages.append) == 0
    assert "scheduler_enabled=False" in messages[0]
    monkeypatch.setenv("RUNTIME_CYCLE_INTERVAL_SECONDS", "invalid")
    assert main(["validate-config"], output=messages.append) == 1
    assert messages[-1] == "RUNTIME CONFIGURATION ERROR"


def test_worker_repeats_through_interval_abstraction_stops_cleanly_and_records_events():
    coordinator = Coordinator()
    scheduler = runtime_scheduler(coordinator, enabled=True)
    waits: list[float] = []
    worker = RuntimeWorker(scheduler, interval_seconds=5, wait=lambda seconds: waits.append(seconds) or False)
    assert worker.run_forever(max_cycles=3) is True
    assert coordinator.calls == [RuntimeMode.STORED_DATA] * 3 and waits == [5, 5]
    assert scheduler.status().scheduler_running is False
    assert [event.event_type for event in worker.events()] == [RuntimeSchedulerEventType.WORKER_STARTED, RuntimeSchedulerEventType.WORKER_STOPPED]


def test_worker_stop_is_cooperative_and_disabled_worker_fails_without_a_cycle():
    disabled = RuntimeWorker(runtime_scheduler(enabled=False), interval_seconds=5, wait=lambda _: True)
    assert disabled.run_forever() is False
    assert disabled.events()[-1].event_type is RuntimeSchedulerEventType.WORKER_CONFIG_ERROR
    called = Event()
    coordinator = Coordinator()
    original = coordinator.run_cycle

    def cycle(**kwargs):
        called.set()
        return original(**kwargs)

    coordinator.run_cycle = cycle
    worker = RuntimeWorker(runtime_scheduler(coordinator, enabled=True), interval_seconds=60)
    assert worker.start() is True
    assert called.wait(1) is True
    assert worker.stop() is True
    assert worker.running is False and len(coordinator.calls) == 1


def test_worker_failure_waits_normally_and_enabled_fastapi_startup_stays_passive(monkeypatch):
    failed = Coordinator(fail=True)
    waits: list[float] = []
    worker = RuntimeWorker(runtime_scheduler(failed, enabled=True), interval_seconds=5, wait=lambda seconds: waits.append(seconds) or True, clock=lambda: T)
    assert worker.run_forever() is True
    assert failed.calls == [RuntimeMode.STORED_DATA] and waits == [5]
    assert worker.events()[0].occurred_at == T
    monkeypatch.setenv("RUNTIME_SCHEDULER_ENABLED", "true")
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/runtime/status").json()["scheduler_enabled"] is True
        assert not hasattr(client.app.state, "runtime_scheduler")


def test_runtime_status_is_read_only_safe_and_independent_from_process_health():
    coordinator = Coordinator(status=RuntimeCycleStatus.PARTIAL)
    scheduler = runtime_scheduler(coordinator)
    scheduler.run_once()
    app = create_app(runtime_health_service=RuntimeHealthService(scheduler))
    with TestClient(app) as client:
        status = client.get("/api/v1/runtime/status")
        health = client.get("/health")
        control = client.post("/api/v1/runtime/run")
    assert status.status_code == 200 and status.json()["last_cycle_status"] == "PARTIAL"
    assert "never-print-this" not in status.text and health.status_code == 200 and control.status_code == 404


def test_runtime_cli_worker_and_api_paths_have_no_broker_governance_or_provider_side_effects():
    import inspect
    import app.runtime.cli as cli
    import app.runtime.scheduler as scheduler_module
    for source in (inspect.getsource(cli).lower(), inspect.getsource(scheduler_module).lower()):
        assert not any(token in source for token in ("kotak", "websocket", "requests.", "place_order", "demat", "promotion", "activation", "self_improvement"))
