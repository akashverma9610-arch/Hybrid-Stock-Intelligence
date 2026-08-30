from datetime import datetime

from pydantic import BaseModel


class DataSourceFreshnessResponse(BaseModel):
    basis: str
    maximum_age_seconds: float | None
    policy_version: str


class DataSourceReadinessResponse(BaseModel):
    source_id: str | None
    provider: str | None
    family: str
    requirement: str
    priority: int | None
    status: str
    configured: bool
    validated: bool
    last_success_at: datetime | None
    last_failure_classification: str | None
    freshness: DataSourceFreshnessResponse
    point_in_time: str
    adjustment: str
    warnings: tuple[str, ...]


class DataSourceStatusResponse(BaseModel):
    generated_at: datetime
    mode: str
    warnings: tuple[str, ...]
    items: tuple[DataSourceReadinessResponse, ...]
