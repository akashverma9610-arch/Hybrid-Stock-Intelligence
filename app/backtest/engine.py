from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Protocol
from zoneinfo import ZoneInfo

from app.historical.guard import BacktestLookaheadGuard, manifest_fingerprint
from app.historical.models import Eligibility, HistoricalFact, HistoricalPartition
from app.storage.governance_repository import StrategyGovernanceRepository

from .models import (
    BacktestDataGapBehavior, BacktestDataGapPolicy, BacktestEvent, BacktestEventType,
    BacktestReplayResult, BacktestReplayStep, BacktestRun, BacktestRunStatus,
    ReplayFrequency, ReplaySchedule, ReplayStepStatus,
)


class ReplayConfigurationError(ValueError):
    pass


class ReplayLookaheadRejected(ValueError):
    pass


class ReplayDataGap(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReplayStepHandlerResult:
    warnings: tuple[str, ...] = ()
    snapshot_references: tuple[str, ...] = ()
    cancel: bool = False


class ReplayStepContext:
    """The only data-eligibility boundary exposed to the V1 placeholder handler."""

    def __init__(self, *, evaluation_timestamp: datetime, guard: BacktestLookaheadGuard,
                 backtest_run_id: str | None = None, step_number: int = 0) -> None:
        self.evaluation_timestamp = evaluation_timestamp
        self._guard = guard
        self.backtest_run_id = backtest_run_id
        self.step_number = step_number

    def require_eligible(self, fact: HistoricalFact) -> HistoricalFact:
        outcome = self._guard.evaluate(fact, self.evaluation_timestamp)
        if outcome is not Eligibility.ELIGIBLE:
            raise ReplayLookaheadRejected(f"{fact.fact_id}: {outcome.value}")
        return fact

    def data_gap(self, message: str) -> None:
        raise ReplayDataGap(message)


ReplayStepHandler = Callable[[ReplayStepContext], ReplayStepHandlerResult | None]


class ExchangeCalendarProtocol(Protocol):
    """Minimal calendar boundary; replay orchestration does not depend on execution gates."""

    calendar_id: str

    def is_trading_day(self, value: date) -> bool: ...


class ReplayClock:
    """Converts a frozen schedule and exchange calendar into evaluation instants only."""

    def __init__(self, schedule: ReplaySchedule, calendar: ExchangeCalendarProtocol) -> None:
        if schedule.exchange_calendar_reference != calendar.calendar_id:
            raise ReplayConfigurationError("Replay schedule and exchange calendar reference do not match.")
        self.schedule = schedule
        self.calendar = calendar

    def timestamps(self, *, start: datetime | None = None, end: datetime | None = None) -> tuple[datetime, ...]:
        if self.schedule.frequency is not ReplayFrequency.DAILY_CLOSE:
            raise ReplayConfigurationError("Only DAILY_CLOSE replay is implemented by this foundation.")
        zone = ZoneInfo(self.schedule.timezone)
        lower = (start or self.schedule.start).astimezone(zone)
        upper = (end or self.schedule.end).astimezone(zone)
        if lower > upper:
            raise ReplayConfigurationError("Replay window start must not be after end.")
        current = lower.date()
        timestamps: list[datetime] = []
        while current <= upper.date():
            if self.calendar.is_trading_day(current):
                value = datetime.combine(current, self.schedule.daily_close_time, tzinfo=zone)
                if lower <= value <= upper:
                    timestamps.append(value)
            current += timedelta(days=1)
        return tuple(timestamps)


def backtest_run_fingerprint(run: BacktestRun) -> str:
    """Hash frozen analytical inputs, intentionally excluding status and runtime timestamps."""
    return manifest_fingerprint(
        dataset=[run.dataset_manifest_id, run.dataset_manifest_version, run.dataset_fingerprint],
        partition_id=run.partition_id,
        versions=[run.strategy_version, run.registry_version, run.scoring_config_version,
                  run.gate_config_version, run.rotation_config_version, run.signal_config_version,
                  run.paper_config_version, run.performance_config_version, run.backtest_config_version],
        schedule=[run.replay_schedule_id, run.replay_schedule_version, run.calendar_reference,
                  run.calendar_version, run.evaluation_start, run.evaluation_end],
        policies=[run.data_gap_policy_id, run.data_gap_policy_version],
        capital=str(run.initial_paper_capital), cost_model=run.cost_model_reference,
        slippage_model=run.slippage_model_reference, universe=run.universe_definition,
        random_seeds=run.random_seeds,
    )


def derive_run_status(initial: BacktestRunStatus, events: tuple[BacktestEvent, ...]) -> BacktestRunStatus:
    status = initial
    for event in events:
        if event.event_type is BacktestEventType.REPLAY_STARTED:
            if status not in (BacktestRunStatus.CREATED, BacktestRunStatus.READY):
                raise ReplayConfigurationError("Replay start is not a valid lifecycle transition.")
            status = BacktestRunStatus.RUNNING
        elif event.event_type is BacktestEventType.REPLAY_COMPLETED:
            if status is not BacktestRunStatus.RUNNING:
                raise ReplayConfigurationError("Replay completion is not a valid lifecycle transition.")
            status = BacktestRunStatus.COMPLETED
        elif event.event_type is BacktestEventType.REPLAY_FAILED:
            if status is not BacktestRunStatus.RUNNING:
                raise ReplayConfigurationError("Replay failure is not a valid lifecycle transition.")
            status = BacktestRunStatus.FAILED
        elif event.event_type is BacktestEventType.REPLAY_CANCELLED:
            if status not in (BacktestRunStatus.CREATED, BacktestRunStatus.READY, BacktestRunStatus.RUNNING):
                raise ReplayConfigurationError("Replay cancellation is not a valid lifecycle transition.")
            status = BacktestRunStatus.CANCELLED
        elif event.event_type is BacktestEventType.DATA_INSUFFICIENT and bool(event.metadata.get("terminal", False)):
            if status is not BacktestRunStatus.RUNNING:
                raise ReplayConfigurationError("Insufficient-data terminal state requires a running replay.")
            status = BacktestRunStatus.INSUFFICIENT_DATA
        if status in (BacktestRunStatus.COMPLETED, BacktestRunStatus.FAILED,
                      BacktestRunStatus.CANCELLED, BacktestRunStatus.INSUFFICIENT_DATA) and event is not events[-1]:
            raise ReplayConfigurationError("No event may follow a terminal replay lifecycle state.")
    return status


def validate_event_sequence(events: tuple[BacktestEvent, ...], initial: BacktestRunStatus) -> BacktestRunStatus:
    previous_step = -1
    previous_event_time: datetime | None = None
    previous_evaluation: datetime | None = None
    for index, event in enumerate(events):
        if event.replay_step_number < previous_step:
            raise ReplayConfigurationError("Replay event step numbers must not move backward.")
        if previous_event_time is not None and event.event_timestamp < previous_event_time:
            raise ReplayConfigurationError("Replay event timestamps must not move backward.")
        if previous_evaluation is not None and event.evaluation_timestamp < previous_evaluation:
            raise ReplayConfigurationError("Replay evaluation timestamps must not move backward.")
        if index == 0 and event.event_type is not BacktestEventType.REPLAY_STARTED:
            raise ReplayConfigurationError("The first replay event must be REPLAY_STARTED.")
        previous_step, previous_event_time, previous_evaluation = (
            event.replay_step_number, event.event_timestamp, event.evaluation_timestamp,
        )
    return derive_run_status(initial, events)


class BacktestReplayEngine:
    """V1 coordinator. It schedules and records placeholder steps; it performs no analysis or trading."""

    def __init__(self, repository: StrategyGovernanceRepository, guard: BacktestLookaheadGuard | None = None) -> None:
        self._repository = repository
        self._guard = guard or BacktestLookaheadGuard()

    def run(
        self, run: BacktestRun, schedule: ReplaySchedule, calendar: ExchangeCalendarProtocol,
        gap_policy: BacktestDataGapPolicy, partition: HistoricalPartition | None = None,
        handler: ReplayStepHandler | None = None,
    ) -> BacktestReplayResult:
        self._validate_configuration(run, schedule, gap_policy, partition)
        stored_schedule = self._repository.get_replay_schedule(schedule.schedule_id)
        if stored_schedule is None:
            self._repository.save_replay_schedule(schedule)
        elif stored_schedule != schedule:
            raise ReplayConfigurationError("A replay schedule ID already refers to different immutable content.")
        stored_policy = self._repository.get_backtest_data_gap_policy(gap_policy.policy_id)
        if stored_policy is None:
            self._repository.save_backtest_data_gap_policy(gap_policy)
        elif stored_policy != gap_policy:
            raise ReplayConfigurationError("A data-gap policy ID already refers to different immutable content.")
        self._repository.save_backtest_run(run)
        clock = ReplayClock(schedule, calendar)
        timestamps = clock.timestamps(start=partition.start if partition else run.evaluation_start,
                                      end=partition.end if partition else run.evaluation_end)
        if partition and any(value < partition.start or value > partition.end for value in timestamps):
            raise ReplayConfigurationError("Replay clock generated a timestamp outside the supplied partition.")
        event_timestamp = timestamps[0] if timestamps else run.evaluation_start
        self._append_event(run, BacktestEventType.REPLAY_STARTED, event_timestamp, 0, event_timestamp, "Replay started")
        completed_steps: list[BacktestReplayStep] = []
        step_handler = handler or (lambda _context: ReplayStepHandlerResult())
        for step_number, evaluation_timestamp in enumerate(timestamps, start=1):
            self._append_event(run, BacktestEventType.REPLAY_STEP_STARTED, evaluation_timestamp, step_number,
                               evaluation_timestamp, "Replay step started")
            try:
                result = step_handler(ReplayStepContext(evaluation_timestamp=evaluation_timestamp, guard=self._guard,
                                                        backtest_run_id=run.backtest_run_id, step_number=step_number))
                result = result or ReplayStepHandlerResult()
                if result.cancel:
                    step = self._step(run, step_number, evaluation_timestamp, ReplayStepStatus.SKIPPED,
                                      result.snapshot_references, result.warnings, "Replay cancelled by handler")
                    self._repository.save_backtest_replay_step(step)
                    completed_steps.append(step)
                    self._append_event(run, BacktestEventType.REPLAY_CANCELLED, evaluation_timestamp, step_number,
                                       evaluation_timestamp, "Replay cancelled by handler")
                    return self._result(run, timestamps, completed_steps)
                step = self._step(run, step_number, evaluation_timestamp, ReplayStepStatus.COMPLETED,
                                  result.snapshot_references, result.warnings, None)
                self._repository.save_backtest_replay_step(step)
                completed_steps.append(step)
                self._append_event(run, BacktestEventType.REPLAY_STEP_COMPLETED, evaluation_timestamp, step_number,
                                   evaluation_timestamp, "Replay step completed")
            except ReplayDataGap as error:
                outcome = self._handle_gap(run, gap_policy, step_number, evaluation_timestamp, str(error), completed_steps)
                if outcome is not None:
                    return self._result(run, timestamps, completed_steps)
            except ReplayLookaheadRejected as error:
                step = self._step(run, step_number, evaluation_timestamp, ReplayStepStatus.FAILED, (), (), str(error))
                self._repository.save_backtest_replay_step(step)
                completed_steps.append(step)
                self._append_event(run, BacktestEventType.LOOKAHEAD_REJECTED, evaluation_timestamp, step_number,
                                   evaluation_timestamp, str(error))
                self._append_event(run, BacktestEventType.REPLAY_FAILED, evaluation_timestamp, step_number,
                                   evaluation_timestamp, "Replay failed closed after look-ahead rejection")
                return self._result(run, timestamps, completed_steps)
            except Exception as error:
                step = self._step(run, step_number, evaluation_timestamp, ReplayStepStatus.FAILED, (), (), str(error))
                self._repository.save_backtest_replay_step(step)
                completed_steps.append(step)
                self._append_event(run, BacktestEventType.REPLAY_FAILED, evaluation_timestamp, step_number,
                                   evaluation_timestamp, f"Replay failed: {error}")
                return self._result(run, timestamps, completed_steps)
        final_time = timestamps[-1] if timestamps else event_timestamp
        self._append_event(run, BacktestEventType.REPLAY_COMPLETED, final_time, len(timestamps), final_time, "Replay completed")
        return self._result(run, timestamps, completed_steps)

    def cancel(self, run_id: str, timestamp: datetime, reason: str = "Manual cancellation") -> BacktestReplayResult:
        run = self._repository.get_backtest_run(run_id)
        if run is None:
            raise ReplayConfigurationError("Backtest run does not exist.")
        events = self._repository.list_backtest_events(run_id)
        status = validate_event_sequence(events, run.status)
        if status not in (BacktestRunStatus.CREATED, BacktestRunStatus.READY, BacktestRunStatus.RUNNING):
            raise ReplayConfigurationError("Terminal backtest runs cannot be cancelled.")
        step_number = events[-1].replay_step_number if events else 0
        self._append_event(run, BacktestEventType.REPLAY_CANCELLED, timestamp, step_number, timestamp, reason)
        return self._result(run, (), list(self._repository.list_backtest_replay_steps(run_id)))

    def run_analytical(self, run, schedule, calendar, gap_policy, analytical_service, partition=None) -> BacktestReplayResult:
        """Run the Phase 8A.3 adapter through the ordinary replay-step lifecycle."""
        return self.run(run, schedule, calendar, gap_policy, partition,
                        handler=lambda context: analytical_service.evaluate_step(run, context))

    def _handle_gap(self, run, policy, step_number, timestamp, reason, completed_steps):
        terminal = policy.behavior is BacktestDataGapBehavior.MARK_INSUFFICIENT_DATA
        self._append_event(run, BacktestEventType.DATA_INSUFFICIENT, timestamp, step_number, timestamp, reason,
                           metadata={"policy": policy.behavior.value, "terminal": terminal})
        if policy.behavior is BacktestDataGapBehavior.FAIL_RUN:
            step = self._step(run, step_number, timestamp, ReplayStepStatus.FAILED, (), (), reason)
            self._repository.save_backtest_replay_step(step); completed_steps.append(step)
            self._append_event(run, BacktestEventType.REPLAY_FAILED, timestamp, step_number, timestamp, "Replay failed due to data gap")
            return True
        status = ReplayStepStatus.SKIPPED if policy.behavior is BacktestDataGapBehavior.SKIP_STEP else ReplayStepStatus.INSUFFICIENT_DATA
        step = self._step(run, step_number, timestamp, status, (), (), reason)
        self._repository.save_backtest_replay_step(step); completed_steps.append(step)
        if policy.behavior is BacktestDataGapBehavior.SKIP_STEP:
            self._append_event(run, BacktestEventType.REPLAY_STEP_COMPLETED, timestamp, step_number, timestamp,
                               "Replay step skipped due to data gap")
            return None
        return True

    def _validate_configuration(self, run, schedule, policy, partition):
        if run.status is not BacktestRunStatus.CREATED:
            raise ReplayConfigurationError("A replay must start from an immutable CREATED run definition.")
        if run.fingerprint != backtest_run_fingerprint(run):
            raise ReplayConfigurationError("Backtest run fingerprint does not match frozen inputs.")
        if (run.replay_schedule_id, run.replay_schedule_version) != (schedule.schedule_id, schedule.version):
            raise ReplayConfigurationError("Run and replay schedule reference do not match.")
        if (run.data_gap_policy_id, run.data_gap_policy_version) != (policy.policy_id, policy.version):
            raise ReplayConfigurationError("Run and data-gap policy reference do not match.")
        if run.calendar_reference != schedule.exchange_calendar_reference:
            raise ReplayConfigurationError("Run and replay schedule calendar reference do not match.")
        manifest = self._repository.get_historical_manifest(run.dataset_manifest_id)
        if manifest is None or manifest.dataset_version != run.dataset_manifest_version or manifest.fingerprint != run.dataset_fingerprint:
            raise ReplayConfigurationError("Backtest run must reference its exact persisted dataset manifest.")
        if partition is not None:
            if run.partition_id != partition.partition_id or partition.dataset_id != run.dataset_manifest_id:
                raise ReplayConfigurationError("Backtest run partition does not match its dataset.")
            if partition.start < run.evaluation_start or partition.end > run.evaluation_end:
                raise ReplayConfigurationError("Partition must be contained by the run evaluation window.")

    def _append_event(self, run, event_type, timestamp, step_number, evaluation_timestamp, message, metadata=None):
        event = BacktestEvent(
            event_id=f"{run.backtest_run_id}:event:{len(self._repository.list_backtest_events(run.backtest_run_id)) + 1:06d}",
            backtest_run_id=run.backtest_run_id, event_type=event_type, event_timestamp=timestamp,
            replay_step_number=step_number, evaluation_timestamp=evaluation_timestamp,
            referenced_artifact_ids=(), message=message, metadata=metadata or {}, created_at=timestamp,
        )
        self._repository.append_backtest_event(event)

    @staticmethod
    def _step(run, number, timestamp, status, snapshots, warnings, failure):
        return BacktestReplayStep(f"{run.backtest_run_id}:step:{number:06d}", run.backtest_run_id, number,
                                  timestamp, timestamp.date().isoformat(), status, snapshots, warnings, failure)

    def _result(self, run, timestamps, steps):
        events = self._repository.list_backtest_events(run.backtest_run_id)
        return BacktestReplayResult(run.backtest_run_id, validate_event_sequence(events, run.status), tuple(timestamps),
                                    tuple(steps), events)
