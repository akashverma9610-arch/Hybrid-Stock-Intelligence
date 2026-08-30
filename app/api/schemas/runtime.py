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
