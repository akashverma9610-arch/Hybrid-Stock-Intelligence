from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Callable, Protocol
from uuid import uuid4

from app.portfolio.models import PortfolioSnapshot
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository

from .models import DiagnosticCompleteness, PortfolioAnalysisJob, PortfolioAnalysisJobStatus, PortfolioAnalysisRunResult


class PortfolioAnalysisError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


class PortfolioSnapshotSource(Protocol):
    def get_snapshot(self, snapshot_id: str | None = None) -> PortfolioSnapshot: ...


class PortfolioHoldingAnalysisRunner(Protocol):
    """Adapter to the existing canonical runtime/stock-analysis pipeline."""
    def run(self, snapshot: PortfolioSnapshot) -> PortfolioAnalysisRunResult: ...


class UnavailablePortfolioHoldingAnalysisRunner:
    def run(self, snapshot: PortfolioSnapshot) -> PortfolioAnalysisRunResult:
        return PortfolioAnalysisRunResult((), tuple(item.instrument_id for item in snapshot.holdings), ("CANONICAL_ANALYSIS_PIPELINE_UNAVAILABLE",), False, False, DiagnosticCompleteness.UNAVAILABLE)


class QueryPortfolioSnapshotSource:
    """Pins an API request to the exact current persisted query snapshot."""
    def __init__(self, get_query_service: Callable[[], object]) -> None:
        self._get_query_service = get_query_service

    def get_snapshot(self, snapshot_id: str | None = None) -> PortfolioSnapshot:
        snapshot = self._get_query_service().get_snapshot()
        if snapshot_id is not None and snapshot.snapshot_id != snapshot_id:
            raise PortfolioAnalysisError("PORTFOLIO_SNAPSHOT_NOT_FOUND", "The requested portfolio snapshot is not available.")
        return snapshot


class CoreSnapshotPortfolioAnalysisJobStore:
    """Append-only job revisions using the existing immutable core snapshot store."""
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, job: PortfolioAnalysisJob) -> None:
        payload = f"{job.job_id}|{job.revision}|{job.portfolio_snapshot_id}|{job.status.value}|{job.holdings_completed}|{job.analysis_completeness.value}|{'|'.join(job.warnings)}"
        self._repository.save_snapshot(CoreApiSnapshot(
            f"portfolio-analysis-job:{job.job_id}:{job.revision}", CoreApiSnapshotFamily.PORTFOLIO_ANALYSIS_JOB, "v1",
            "portfolio-analysis-job-v1", sha256(payload.encode()).hexdigest(), job.requested_at, job,
        ))

    def get(self, job_id: str) -> PortfolioAnalysisJob | None:
        values = [item.payload for item in self._repository.list_snapshots(CoreApiSnapshotFamily.PORTFOLIO_ANALYSIS_JOB) if isinstance(item.payload, PortfolioAnalysisJob) and item.payload.job_id == job_id]
        return max(values, key=lambda value: value.revision) if values else None

    def list(self) -> tuple[PortfolioAnalysisJob, ...]:
        latest: dict[str, PortfolioAnalysisJob] = {}
        for item in self._repository.list_snapshots(CoreApiSnapshotFamily.PORTFOLIO_ANALYSIS_JOB):
            if isinstance(item.payload, PortfolioAnalysisJob) and (item.payload.job_id not in latest or latest[item.payload.job_id].revision < item.payload.revision):
                latest[item.payload.job_id] = item.payload
        return tuple(sorted(latest.values(), key=lambda value: (value.requested_at, value.job_id), reverse=True))

    def active_for(self, snapshot_id: str) -> PortfolioAnalysisJob | None:
        return next((job for job in self.list() if job.portfolio_snapshot_id == snapshot_id and job.status in {PortfolioAnalysisJobStatus.QUEUED, PortfolioAnalysisJobStatus.RUNNING}), None)


class PortfolioAnalysisJobService:
    """Explicit queue plus cooperative `run_next`; no threads or HTTP execution."""
    def __init__(self, *, snapshots: PortfolioSnapshotSource, store: CoreSnapshotPortfolioAnalysisJobStore,
                 runner: PortfolioHoldingAnalysisRunner | None = None, clock=lambda: datetime.now(UTC)) -> None:
        self._snapshots, self._store, self._runner, self._clock = snapshots, store, runner or UnavailablePortfolioHoldingAnalysisRunner(), clock

    def request(self, snapshot_id: str | None = None) -> PortfolioAnalysisJob:
        try:
            snapshot = self._snapshots.get_snapshot(snapshot_id)
        except PortfolioAnalysisError:
            raise
        except Exception as error:
            raise PortfolioAnalysisError("PORTFOLIO_SNAPSHOT_UNAVAILABLE", "Portfolio snapshot is not available for analysis.") from error
        if not snapshot.holdings:
            raise PortfolioAnalysisError("PORTFOLIO_EMPTY", "Portfolio analysis requires at least one confirmed holding.")
        active = self._store.active_for(snapshot.snapshot_id)
        if active is not None:
            return active
        now = self._clock()
        job = PortfolioAnalysisJob(f"portfolio-analysis-{uuid4().hex}", 1, snapshot.snapshot_id, PortfolioAnalysisJobStatus.QUEUED,
            now, None, None, snapshot.as_of_timestamp, len(snapshot.holdings), 0, DiagnosticCompleteness.UNAVAILABLE,
            (), "PENDING")
        self._store.save(job)
        return job

    def get(self, job_id: str) -> PortfolioAnalysisJob:
        job = self._store.get(job_id)
        if job is None:
            raise PortfolioAnalysisError("ANALYSIS_JOB_NOT_FOUND", "Portfolio analysis job was not found.")
        return job

    def list(self) -> tuple[PortfolioAnalysisJob, ...]:
        return self._store.list()

    def run_next(self) -> PortfolioAnalysisJob | None:
        queued = next((job for job in reversed(self._store.list()) if job.status is PortfolioAnalysisJobStatus.QUEUED), None)
        if queued is None:
            return None
        started = PortfolioAnalysisJob(**{**_job_fields(queued), "revision": queued.revision + 1, "status": PortfolioAnalysisJobStatus.RUNNING, "started_at": self._clock()})
        self._store.save(started)
        try:
            snapshot = self._snapshots.get_snapshot(started.portfolio_snapshot_id)
            output = self._runner.run(snapshot)
            completed = len(set(output.completed_instrument_ids) & {item.instrument_id for item in snapshot.holdings})
            partial = completed < started.holdings_total or bool(output.unavailable_instrument_ids)
            warnings = set(output.warnings)
            if output.diagnostic_completeness is not DiagnosticCompleteness.COMPLETE:
                warnings.add("ANALYSIS_PARTIAL")
            if not output.candidate_universe_available:
                warnings.add("CANDIDATE_UNIVERSE_NOT_ANALYZED")
            status = PortfolioAnalysisJobStatus.PARTIAL if partial else PortfolioAnalysisJobStatus.COMPLETED
            result = PortfolioAnalysisJob(**{**_job_fields(started), "revision": started.revision + 1, "status": status, "completed_at": self._clock(), "holdings_completed": completed, "analysis_completeness": output.diagnostic_completeness, "warnings": tuple(sorted(warnings)), "result_availability": "AVAILABLE" if output.stock_results_published else "PARTIAL"})
        except Exception:
            result = PortfolioAnalysisJob(**{**_job_fields(started), "revision": started.revision + 1, "status": PortfolioAnalysisJobStatus.FAILED, "completed_at": self._clock(), "warnings": ("ANALYSIS_JOB_FAILED",), "result_availability": "UNAVAILABLE"})
        self._store.save(result)
        return result


def _job_fields(job: PortfolioAnalysisJob) -> dict:
    return {field: getattr(job, field) for field in job.__dataclass_fields__}
