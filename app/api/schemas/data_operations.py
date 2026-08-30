"""Public-safe read-only operational health DTOs."""
from datetime import datetime

from pydantic import BaseModel


class DataOperationsRunResponse(BaseModel):
    run_id: str
    family: str
    mode: str
    status: str
    completed_at: datetime
    accepted_count: int
    duplicate_count: int
    conflict_count: int
    rejected_count: int
    gap_count: int
    warnings: tuple[str, ...]


class DataOperationsFamilyHealthResponse(BaseModel):
    family: str
    status: str
    last_run: DataOperationsRunResponse | None
    next_due_at: datetime | None
    reasons: tuple[str, ...]


class DataOperationsHealthResponse(BaseModel):
    generated_at: datetime
    families: tuple[DataOperationsFamilyHealthResponse, ...]
