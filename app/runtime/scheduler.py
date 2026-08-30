"""Opt-in in-process scheduling around the explicit runtime-cycle boundary.

This module owns no timer, worker, provider, or application-startup hook.  A
future host may invoke :meth:`RuntimeScheduler.run_once` at an explicit cadence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
import os
from threading import Event, Lock, Thread
from typing import Callable, Mapping, Protocol

from app.market_data.models import MarketSessionState
from app.runtime.cycle import RuntimeCycleResult, RuntimeCycleStatus, RuntimeMode


class RuntimeCycleRunner(Protocol):
    def run_cycle(self, *, mode: RuntimeMode = RuntimeMode.STORED_DATA) -> RuntimeCycleResult: ...


class RuntimeSchedulerEventType(StrEnum):
    SCHEDULER_STARTED = "SCHEDULER_STARTED"
    SCHEDULER_STOPPED = "SCHEDULER_STOPPED"
    SCHEDULER_CYCLE_SKIPPED = "SCHEDULER_CYCLE_SKIPPED"
    SCHEDULER_CYCLE_FAILED = "SCHEDULER_CYCLE_FAILED"
    WORKER_STARTED = "WORKER_STARTED"
    WORKER_STOPPED = "WORKER_STOPPED"
    WORKER_CONFIG_ERROR = "WORKER_CONFIG_ERROR"


@dataclass(frozen=True, slots=True)
class RuntimeSchedulerEvent:
    event_type: RuntimeSchedulerEventType
    occurred_at: datetime
    warning: str | None = None
    cycle_id: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeSchedulerSettings:
    """Non-secret process settings. Scheduling remains disabled by default."""

    enabled: bool = False
    interval_seconds: int = 300
    mode: RuntimeMode = RuntimeMode.STORED_DATA
    universe_id: str | None = None

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "RuntimeSchedulerSettings":
        values = os.environ if environ is None else environ
        raw_enabled = values.get("RUNTIME_SCHEDULER_ENABLED", "false").strip().lower()
        accepted = {"true": True, "1": True, "yes": True, "on": True, "false": False, "0": False, "no": False, "off": False}
        if raw_enabled not in accepted:
            raise ValueError("RUNTIME_SCHEDULER_ENABLED must be a boolean value.")
        try:
            interval_seconds = int(values.get("RUNTIME_CYCLE_INTERVAL_SECONDS", "300"))
        except ValueError as error:
            raise ValueError("RUNTIME_CYCLE_INTERVAL_SECONDS must be an integer.") from error
        if interval_seconds < 1:
            raise ValueError("RUNTIME_CYCLE_INTERVAL_SECONDS must be positive.")
        try:
            mode = RuntimeMode(values.get("RUNTIME_MODE", RuntimeMode.STORED_DATA.value).upper())
        except ValueError as error:
            raise ValueError("RUNTIME_MODE must be STORED_DATA or MOCK.") from error
        return cls(accepted[raw_enabled], interval_seconds, mode, values.get("RUNTIME_UNIVERSE_ID") or None)


@dataclass(frozen=True, slots=True)
class RuntimeHealth:
    scheduler_enabled: bool
    scheduler_running: bool
    runtime_mode: RuntimeMode
    universe_id: str | None
    last_cycle_id: str | None = None
    last_cycle_status: RuntimeCycleStatus | None = None
    last_started_at: datetime | None = None
    last_completed_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    last_data_as_of: datetime | None = None
    consecutive_failures: int = 0
    warnings: tuple[str, ...] = ()


class RuntimeHealthService:
    """Read-only operational status facade, independent from HTTP process health."""

    def __init__(self, scheduler: "RuntimeScheduler" | None = None, settings: RuntimeSchedulerSettings | None = None) -> None:
        self._scheduler = scheduler
        configured = settings or RuntimeSchedulerSettings()
        self._static_status = RuntimeHealth(configured.enabled, False, configured.mode, configured.universe_id)

    def status(self) -> RuntimeHealth:
        return self._scheduler.status() if self._scheduler is not None else self._static_status


class RuntimeScheduler:
    """A synchronous one-cycle gate with in-instance overlap prevention.

    ``start`` only records intent. It never creates background work, so a failed
    cycle cannot result in an immediate retry loop or FastAPI startup activity.
    """

    def __init__(
        self,
        coordinator: RuntimeCycleRunner,
        settings: RuntimeSchedulerSettings | None = None,
        *,
        session: Callable[[], MarketSessionState | str] = lambda: MarketSessionState.OPEN,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._coordinator = coordinator
        self._settings = settings or RuntimeSchedulerSettings()
        self._session = session
        self._clock = clock
        self._running = False
        self._cycle_lock = Lock()
        self._health = RuntimeHealth(self._settings.enabled, False, self._settings.mode, self._settings.universe_id)
        self._events: list[RuntimeSchedulerEvent] = []

    def status(self) -> RuntimeHealth:
        return self._health

    def events(self) -> tuple[RuntimeSchedulerEvent, ...]:
        return tuple(self._events)

    def start(self) -> bool:
        if not self._settings.enabled or self._running:
            return False
        self._running = True
        self._health = replace(self._health, scheduler_running=True)
        self._record(RuntimeSchedulerEventType.SCHEDULER_STARTED)
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        self._running = False
        self._health = replace(self._health, scheduler_running=False)
        self._record(RuntimeSchedulerEventType.SCHEDULER_STOPPED)
        return True

    def run_once(self, *, dry_run: bool = False) -> RuntimeCycleResult | None:
        """Run exactly one existing coordinator cycle, even while scheduling is off."""
        now = self._clock()
        if self._session_value() == MarketSessionState.CLOSED.value:
            self._health = replace(self._health, warnings=("MARKET_CLOSED",))
            self._record(RuntimeSchedulerEventType.SCHEDULER_CYCLE_SKIPPED, now, "MARKET_CLOSED")
            return None
        if not self._cycle_lock.acquire(blocking=False):
            self._health = replace(self._health, warnings=("CYCLE_ALREADY_RUNNING",))
            self._record(RuntimeSchedulerEventType.SCHEDULER_CYCLE_SKIPPED, now, "CYCLE_ALREADY_RUNNING")
            return None
        try:
            result = self._coordinator.run_cycle(mode=self._settings.mode, publish=False) if dry_run else self._coordinator.run_cycle(mode=self._settings.mode)
        except Exception:
            self._health = replace(
                self._health,
                last_started_at=now,
                last_failure_at=now,
                consecutive_failures=self._health.consecutive_failures + 1,
                warnings=("RUNTIME_CYCLE_FAILED",),
            )
            self._record(RuntimeSchedulerEventType.SCHEDULER_CYCLE_FAILED, now, "RUNTIME_CYCLE_FAILED")
            return None
        finally:
            self._cycle_lock.release()

        success_at = result.completed_at if result.overall_status in {RuntimeCycleStatus.SUCCESS, RuntimeCycleStatus.PARTIAL} else None
        self._health = replace(
            self._health,
            last_cycle_id=result.cycle_id,
            last_cycle_status=result.overall_status,
            last_started_at=now,
            last_completed_at=result.completed_at,
            last_success_at=success_at,
            last_data_as_of=result.data_as_of,
            consecutive_failures=0,
            warnings=result.warnings,
        )
        return result

    def _record(self, event_type: RuntimeSchedulerEventType, occurred_at: datetime | None = None, warning: str | None = None, cycle_id: str | None = None) -> None:
        self._events.append(RuntimeSchedulerEvent(event_type, occurred_at or self._clock(), warning, cycle_id))

    def _session_value(self) -> str:
        value = self._session()
        return value.value if isinstance(value, MarketSessionState) else str(value).upper()


class RuntimeWorker:
    """One optional local timer loop with cooperative, bounded shutdown.

    It owns one daemon thread at most. Each loop waits *after* its synchronous
    scheduler cycle, so a slow cycle cannot overlap the next interval.
    """

    def __init__(
        self,
        scheduler: RuntimeScheduler,
        *,
        interval_seconds: int,
        wait: Callable[[float], bool] | None = None,
        thread_factory: Callable[..., Thread] = Thread,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if interval_seconds < 1:
            raise ValueError("Runtime worker interval must be positive.")
        self._scheduler = scheduler
        self._interval_seconds = interval_seconds
        self._stop_event = Event()
        self._wait = wait or self._stop_event.wait
        self._thread_factory = thread_factory
        self._clock = clock
        self._thread: Thread | None = None
        self._events: list[RuntimeSchedulerEvent] = []

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def events(self) -> tuple[RuntimeSchedulerEvent, ...]:
        return tuple(self._events)

    def start(self) -> bool:
        if self.running:
            return False
        self._stop_event.clear()
        thread = self._thread_factory(target=self.run_forever, name="runtime-worker", daemon=True)
        self._thread = thread
        thread.start()
        return True

    def stop(self, *, join_timeout: float = 2.0) -> bool:
        if not self.running:
            return False
        self._stop_event.set()
        self._thread.join(join_timeout)
        return True

    def run_forever(self, *, max_cycles: int | None = None) -> bool:
        if not self._scheduler.start():
            self._record(RuntimeSchedulerEventType.WORKER_CONFIG_ERROR, "SCHEDULER_DISABLED_OR_RUNNING")
            return False
        self._record(RuntimeSchedulerEventType.WORKER_STARTED)
        completed_cycles = 0
        try:
            while not self._stop_event.is_set():
                self._scheduler.run_once()
                completed_cycles += 1
                if max_cycles is not None and completed_cycles >= max_cycles:
                    break
                if self._wait(self._interval_seconds):
                    break
        finally:
            self._scheduler.stop()
            self._record(RuntimeSchedulerEventType.WORKER_STOPPED)
        return True

    def _record(self, event_type: RuntimeSchedulerEventType, warning: str | None = None) -> None:
        self._events.append(RuntimeSchedulerEvent(event_type, self._clock(), warning))
