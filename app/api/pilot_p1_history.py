"""Authenticated unarmed P1 history read; no public producer or activation API."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from app.api.errors import APIRequestError
from app.api.schemas.p1_signal_lifecycle import P1LifecycleQuery
from app.storage.database import DatabaseSettings, DatabaseStorageMode
from app.storage.readonly_p1_signal_lifecycle import P1ReadUnavailable, ReadOnlyP1SignalLifecycleReader


class PilotP1EmptyHistory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["pilot-p1-unarmed-history/v1"] = "pilot-p1-unarmed-history/v1"
    canonical_instrument_id: str
    as_of: datetime
    availability: Literal["NO_HISTORY"] = "NO_HISTORY"
    recorder_state: Literal["NOT_ACTIVE"] = "NOT_ACTIVE"
    prospective_start: None = None
    source_readiness: Literal["SOURCE_BLOCKED"] = "SOURCE_BLOCKED"
    warnings: tuple[Literal["SOURCE_KNOWN_AT_ADAPTER_UNAVAILABLE", "PROSPECTIVE_START_UNSET"], ...] = (
        "SOURCE_KNOWN_AT_ADAPTER_UNAVAILABLE", "PROSPECTIVE_START_UNSET")
    observations: tuple[()] = ()
    transitions: tuple[()] = ()
    actionability: Literal["WATCH_ONLY"] = "WATCH_ONLY"
    execution_status: Literal["NON_EXECUTABLE"] = "NON_EXECUTABLE"


def read_unarmed_history(database: DatabaseSettings, query: P1LifecycleQuery) -> PilotP1EmptyHistory:
    if database.storage_mode is not DatabaseStorageMode.PERSISTENT_SQLITE:
        raise P1ReadUnavailable("P1_LIFECYCLE_STORE_UNAVAILABLE")
    reader = ReadOnlyP1SignalLifecycleReader(database.url.removeprefix("sqlite:///"))
    try:
        reader.verify_unarmed_empty_store()
    finally:
        reader.close()
    return PilotP1EmptyHistory(canonical_instrument_id=query.canonical_instrument_id, as_of=query.as_of)


router = APIRouter(prefix="/api/v1/pilot", tags=["pilot-p1-history"])


@router.get("/p1-history", response_model=PilotP1EmptyHistory)
def history(request: Request):
    # Strict query parsing rejects attempted user/role/origin authority hints.
    try:
        if any(len(request.query_params.getlist(k)) != 1 for k in request.query_params):
            raise ValueError("duplicate query")
        query = P1LifecycleQuery.model_validate(dict(request.query_params))
        if query.as_of > datetime.now(UTC):
            raise ValueError("future cutoff")
    except ValueError:
        raise APIRequestError(status_code=422, code="P1_HISTORY_QUERY_INVALID", message="Supply one exact instrument and non-future as-of cutoff.") from None
    try:
        return read_unarmed_history(request.app.state.database_settings, query)
    except P1ReadUnavailable as error:
        raise APIRequestError(status_code=503, code=error.code, message="Prospective history cannot be verified; no activation was performed.") from None
