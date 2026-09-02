from datetime import datetime

from pydantic import BaseModel


class RuntimeStatusResponse(BaseModel):
    scheduler_enabled: bool
    scheduler_running: bool
    runtime_mode: str
    universe_id: str | None
    last_cycle_id: str | None
    last_cycle_status: str | None
    last_started_at: datetime | None
    last_completed_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_data_as_of: datetime | None
    consecutive_failures: int
    warnings: tuple[str, ...]


class LocalRuntimeReadinessResponse(BaseModel):
    database_backend: str
    storage_mode: str
    database_path: str | None
    sqlite_integrity: str | None
    foreign_key_violations: int | None
    financial_facts: int | None
    corporate_filings: int | None
    portfolio_snapshots: int | None
    bse_receipts: int | None
    bse_plan_id: str | None
    bse_status: str
    market_wide_watch_status: str
    warnings: tuple[str, ...]
