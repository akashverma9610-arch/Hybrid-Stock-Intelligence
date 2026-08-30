from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PortfolioAnalysisJobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class DiagnosticCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class PortfolioAnalysisJob:
    job_id: str
    revision: int
    portfolio_snapshot_id: str
    status: PortfolioAnalysisJobStatus
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    data_as_of: datetime
    holdings_total: int
    holdings_completed: int
    analysis_completeness: DiagnosticCompleteness
    warnings: tuple[str, ...]
    result_availability: str
    input_version: str = "portfolio-analysis-job-v1"


@dataclass(frozen=True, slots=True)
class PortfolioAnalysisRunResult:
    completed_instrument_ids: tuple[str, ...]
    unavailable_instrument_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    stock_results_published: bool = False
    candidate_universe_available: bool = False
    diagnostic_completeness: DiagnosticCompleteness = DiagnosticCompleteness.UNAVAILABLE
