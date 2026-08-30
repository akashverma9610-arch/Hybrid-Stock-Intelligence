from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel


class OpportunityItemResponse(BaseModel):
    symbol: str
    sector: str | None
    score: Decimal | None
    confidence: float | None
    risk_reward: str | None
    execution_status: str
    candidate_status: str
    catalyst_summary: str | None
    freshness: str
    warnings: tuple[str, ...]


class OpportunitySnapshotResponse(BaseModel):
    as_of: datetime
    universe_count: int
    eligible_count: int
    analyzed_count: int
    complete_count: int
    partial_count: int
    unavailable_count: int
    qualified_candidate_count: int
    warnings: tuple[str, ...]
    freshness: str
    coverage_status: str
    opportunities: tuple[OpportunityItemResponse, ...]


class UniverseAnalysisJobResponse(BaseModel):
    job_id: str
    status: str
    stage: str
    requested_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    universe_as_of: datetime
    as_of: datetime
    eligible_total: int
    processed: int
    complete_count: int
    partial_count: int
    unavailable_count: int
    failed_count: int
    coverage_ready_count: int
    coverage_partial_count: int
    coverage_missing_count: int
    warnings: tuple[str, ...]
