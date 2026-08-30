from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PortfolioAnalysisJobRequest(BaseModel):
    portfolio_snapshot_id: str | None = None


class PortfolioAnalysisJobResponse(BaseModel):
    job_id: str
    portfolio_reference: str
    status: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    data_as_of: datetime
    holdings_total: int
    holdings_completed: int
    analysis_completeness: str
    progress: str
    warnings: tuple[str, ...]
    result_availability: str


class PortfolioAnalysisJobListResponse(BaseModel):
    items: tuple[PortfolioAnalysisJobResponse, ...]
    total: int
