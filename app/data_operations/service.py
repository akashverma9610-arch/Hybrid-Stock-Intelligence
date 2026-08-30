"""One testable orchestration layer for immutable evidence refresh jobs."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import os
from threading import Event, Lock, Thread
from typing import Callable, Mapping, Protocol
from uuid import uuid4

from app.data_operations.models import (
    DataOperationCadence,
    DataOperationsFamilyHealth,
    DataOperationsHealth,
    DataOperationsHealthStatus,
    EvidenceDataFamily,
    EvidenceReconciliationFinding,
    EvidenceRefreshFailureKind,
    EvidenceRefreshMode,
    EvidenceRefreshOutcome,
    EvidenceRefreshRequest,
    EvidenceRefreshRun,
    EvidenceRefreshStatus,
    EvidenceRefreshWatermark,
    ReconciliationStatus,
)
from app.data_operations.store import DataOperationsStore


class EvidenceRefreshJob(Protocol):
    """Family adapter that invokes existing ingestion; it owns no scheduler."""

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome: ...


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    maximum_attempts: int = 2

    def __post_init__(self) -> None:
        if self.maximum_attempts < 1:
            raise ValueError("Retry policy needs at least one attempt.")


@dataclass(frozen=True, slots=True)
class DataOperationsSettings:
    """Non-secret opt-in worker settings; disabled unless explicitly enabled."""

    enabled: bool = False
    poll_seconds: int = 300

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> "DataOperationsSettings":
        values = os.environ if environ is None else environ
        raw_enabled = values.get("DATA_OPERATIONS_ENABLED", "false").strip().lower()
        accepted = {"true": True, "1": True, "yes": True, "on": True, "false": False, "0": False, "no": False, "off": False}
        if raw_enabled not in accepted:
            raise ValueError("DATA_OPERATIONS_ENABLED must be a boolean value.")
        try:
            poll_seconds = int(values.get("DATA_OPERATIONS_POLL_SECONDS", "300"))
        except ValueError as error:
            raise ValueError("DATA_OPERATIONS_POLL_SECONDS must be an integer.") from error
        if poll_seconds < 1:
            raise ValueError("DATA_OPERATIONS_POLL_SECONDS must be positive.")
        return cls(accepted[raw_enabled], poll_seconds)


DEFAULT_CADENCES: tuple[DataOperationCadence, ...] = (
    DataOperationCadence(EvidenceDataFamily.OHLCV, timedelta(days=1), overlap_sessions=2),
    DataOperationCadence(EvidenceDataFamily.DELIVERY, timedelta(days=1)),
    DataOperationCadence(EvidenceDataFamily.INDEX_BARS, timedelta(days=1), overlap_sessions=2),
    DataOperationCadence(EvidenceDataFamily.INDEX_MEMBERSHIP, timedelta(days=7)),
    DataOperationCadence(EvidenceDataFamily.CORPORATE_ACTIONS, timedelta(days=1)),
    DataOperationCadence(EvidenceDataFamily.FINANCIAL_RESULTS, timedelta(days=1)),
    DataOperationCadence(EvidenceDataFamily.SHAREHOLDING, timedelta(days=7)),
    DataOperationCadence(EvidenceDataFamily.TAXONOMY_REFERENCE, timedelta(days=30)),
    DataOperationCadence(EvidenceDataFamily.MACRO, timedelta(days=1)),
    DataOperationCadence(EvidenceDataFamily.NEWS, timedelta(hours=1)),
)


class DataOperationsService:
    """Runs registered source adapters with bounded retry and durable receipts.

    The service never fetches data itself.  A job receives its store-verified
    prior watermark and delegates to the existing canonical ingestion boundary.
    It may only append/reconcile through that boundary.
    """

    def __init__(
        self,
        store: DataOperationsStore,
        jobs: Mapping[EvidenceDataFamily, EvidenceRefreshJob] | None = None,
        cadences: tuple[DataOperationCadence, ...] = DEFAULT_CADENCES,
        *,
        retry_policy: RetryPolicy = RetryPolicy(),
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        run_id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        by_family = {item.family: item for item in cadences}
        if set(by_family) != set(EvidenceDataFamily) or len(by_family) != len(cadences):
            raise ValueError("A cadence is required exactly once for every evidence family.")
        self._store = store
        self._jobs = dict(jobs or {})
        self._cadences = by_family
        self._retry_policy = retry_policy
        self._clock = clock
        self._run_id_factory = run_id_factory
        self._locks = {item: Lock() for item in EvidenceDataFamily}

    @property
    def cadences(self) -> tuple[DataOperationCadence, ...]:
        return tuple(self._cadences[item] for item in EvidenceDataFamily)

    @property
    def registered_families(self) -> tuple[EvidenceDataFamily, ...]:
        return tuple(item for item in EvidenceDataFamily if item in self._jobs)

    def latest_findings(self, family: EvidenceDataFamily) -> tuple[EvidenceReconciliationFinding, ...]:
        """Return immutable findings from the latest run for one family."""
        latest = self._store.latest_run(family)
        return () if latest is None else self._store.findings(latest.run_id)

    def latest_conflict_findings(self, family: EvidenceDataFamily) -> tuple[EvidenceReconciliationFinding, ...]:
        """Find the latest family receipt that actually named conflict subjects."""
        for run in reversed(self._store.runs(family)):
            findings = tuple(
                item for item in self._store.findings(run.run_id)
                if item.status is ReconciliationStatus.CONFLICT_FOUND
            )
            if findings:
                return findings
        return ()

    def run(
        self,
        family: EvidenceDataFamily,
        *,
        mode: EvidenceRefreshMode = EvidenceRefreshMode.INCREMENTAL,
        requested_as_of: datetime | None = None,
        run_id: str | None = None,
    ) -> EvidenceRefreshRun:
        now = self._clock()
        cutoff = requested_as_of or now
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("requested_as_of must be timezone-aware.")
        identifier = run_id or f"evidence-refresh:{family.value.lower()}:{self._run_id_factory()}"
        lock = self._locks[family]
        if not lock.acquire(blocking=False):
            run = EvidenceRefreshRun(
                identifier, family, mode, EvidenceRefreshStatus.FAILED, now, now, cutoff, "OPERATIONS",
                error_summary="RUN_ALREADY_ACTIVE", warnings=("RUN_ALREADY_ACTIVE",),
            )
            self._store.save_run(run)
            return run
        try:
            return self._run_locked(family, mode, cutoff, identifier, now)
        finally:
            lock.release()

    def _run_locked(
        self,
        family: EvidenceDataFamily,
        mode: EvidenceRefreshMode,
        cutoff: datetime,
        run_id: str,
        started: datetime,
    ) -> EvidenceRefreshRun:
        job = self._jobs.get(family)
        if job is None:
            run = EvidenceRefreshRun(
                run_id, family, mode, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, started, self._clock(), cutoff,
                "UNCONFIGURED", error_summary="SOURCE_NOT_CONFIGURED", warnings=("SOURCE_NOT_CONFIGURED",),
            )
            self._store.save_run(run)
            return run
        prior = self._store.latest_watermark(family)
        attempts = 0
        outcome: EvidenceRefreshOutcome | None = None
        while attempts < self._retry_policy.maximum_attempts:
            attempts += 1
            request = EvidenceRefreshRequest(run_id, family, mode, cutoff, started, prior, self._cadences[family].overlap_sessions)
            try:
                outcome = job.refresh(request)
            except ValueError:
                outcome = EvidenceRefreshOutcome(
                    EvidenceRefreshStatus.INVALID_EVIDENCE, "JOB_VALIDATION", failure_kind=EvidenceRefreshFailureKind.VALIDATION,
                    error_summary="REFRESH_JOB_VALIDATION_FAILED", warnings=("REFRESH_JOB_VALIDATION_FAILED",),
                )
            except Exception:
                outcome = EvidenceRefreshOutcome(
                    EvidenceRefreshStatus.FAILED, "JOB_EXCEPTION", failure_kind=EvidenceRefreshFailureKind.TRANSIENT,
                    error_summary="REFRESH_JOB_EXCEPTION", warnings=("REFRESH_JOB_EXCEPTION",),
                )
            if outcome.failure_kind is not EvidenceRefreshFailureKind.TRANSIENT:
                break
        assert outcome is not None
        completed = self._clock()
        run = EvidenceRefreshRun(
            run_id, family, mode, outcome.status, started, completed, cutoff, outcome.provider,
            outcome.discovered_count, outcome.accepted_count, outcome.duplicate_count, outcome.conflict_count,
            outcome.rejected_count, outcome.gap_count, attempts - 1, None, outcome.error_summary,
            outcome.warnings, outcome.source_references,
        )
        self._store.save_run(run)
        if outcome.verified_from_store and outcome.accepted_through is not None:
            watermark = EvidenceRefreshWatermark(
                f"evidence-watermark:{family.value.lower()}:{run_id}", family, outcome.provider, "DEFAULT",
                outcome.accepted_through, completed, run_id, outcome.source_fingerprint, True,
            )
            self._store.save_watermark(watermark)
        for index, (status, subject, reason) in enumerate(outcome.findings):
            self._store.save_finding(EvidenceReconciliationFinding(
                f"evidence-reconciliation:{run_id}:{index}", run_id, family, status, subject,
                completed, reason, outcome.provider,
            ))
        return run

    def health(self, *, now: datetime | None = None) -> DataOperationsHealth:
        generated = now or self._clock()
        if generated.tzinfo is None or generated.utcoffset() is None:
            raise ValueError("Operational health timestamp must be timezone-aware.")
        values = []
        for family in EvidenceDataFamily:
            cadence = self._cadences[family]
            last = self._store.latest_run(family)
            next_due = last.completed_at + cadence.interval if last is not None else generated
            if last is None:
                status, reasons = DataOperationsHealthStatus.NEVER_RUN, ("NEVER_RUN",)
            elif last.status in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, EvidenceRefreshStatus.INVALID_EVIDENCE}:
                status, reasons = DataOperationsHealthStatus.FAILED, (last.error_summary or last.status.value,)
            elif last.status in {EvidenceRefreshStatus.PARTIAL, EvidenceRefreshStatus.GAP_FOUND, EvidenceRefreshStatus.CONFLICT_FOUND} or next_due < generated:
                status = DataOperationsHealthStatus.DEGRADED
                reasons = tuple(sorted(set((last.status.value,) + (("REFRESH_OVERDUE",) if next_due < generated else ()))))
            else:
                status, reasons = DataOperationsHealthStatus.HEALTHY, ()
            values.append(DataOperationsFamilyHealth(family, status, last, next_due, reasons))
        return DataOperationsHealth(tuple(values), generated)

    def due_families(self, *, now: datetime | None = None) -> tuple[EvidenceDataFamily, ...]:
        generated = now or self._clock()
        return tuple(
            item.family for item in self.health(now=generated).families
            if item.family in self._jobs and self._cadences[item.family].enabled and item.next_due_at is not None and item.next_due_at <= generated
        )


class DataOperationsScheduler:
    """Clock-injected dispatcher; hosts decide whether and how to call it."""

    def __init__(self, service: DataOperationsService, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._service = service
        self._clock = clock

    def run_due(self, *, requested_as_of: datetime | None = None) -> tuple[EvidenceRefreshRun, ...]:
        now = requested_as_of or self._clock()
        return tuple(self._service.run(family, requested_as_of=now) for family in self._service.due_families(now=now))


class DataOperationsWorker:
    """One optional local timer loop; never created by FastAPI startup."""

    def __init__(
        self,
        scheduler: DataOperationsScheduler,
        settings: DataOperationsSettings,
        *,
        wait: Callable[[float], bool] | None = None,
        thread_factory: Callable[..., Thread] = Thread,
    ) -> None:
        self._scheduler = scheduler
        self._settings = settings
        self._stop = Event()
        self._wait = wait or self._stop.wait
        self._thread_factory = thread_factory
        self._thread: Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        if not self._settings.enabled or self.running:
            return False
        self._stop.clear()
        self._thread = self._thread_factory(target=self.run_forever, name="data-operations-worker", daemon=True)
        self._thread.start()
        return True

    def stop(self, *, join_timeout: float = 2.0) -> bool:
        if not self.running:
            return False
        self._stop.set()
        self._thread.join(join_timeout)
        return True

    def run_forever(self, *, max_ticks: int | None = None) -> bool:
        if not self._settings.enabled:
            return False
        ticks = 0
        while not self._stop.is_set():
            self._scheduler.run_due()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            if self._wait(self._settings.poll_seconds):
                break
        return True
