"""Public read projection: deliberately excludes raw setup/evidence payloads."""
from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.intelligence.p1_signal_lifecycle import Outcome, Reason, State, slot_key, utc


class P1LifecycleQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    canonical_instrument_id: str = Field(min_length=1, max_length=128)
    as_of: AwareDatetime

    @field_validator("canonical_instrument_id")
    @classmethod
    def canonical_identity(cls, value: str) -> str:
        slot_key(value)
        return value

    @field_validator("as_of")
    @classmethod
    def normalize_cutoff(cls, value: datetime) -> datetime:
        return utc(value)


class P1LifecycleTransitionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    lifetime_id: str
    transition_id: str
    fingerprint: str
    prior_state: State | None
    next_state: State
    reason_code: str
    transition_as_of: AwareDatetime
    known_at: AwareDatetime
    initial_as_of: AwareDatetime
    previous_transition_id: str | None
    previous_transition_fingerprint: str | None
    predecessor_terminal_id: str | None
    replacement_lifetime_id: str | None


class P1ObservationReferenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    signal_id: str
    fingerprint: str


class P1LifecycleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["p1-lifecycle-query/v1"] = "p1-lifecycle-query/v1"
    canonical_instrument_id: str
    as_of: AwareDatetime
    availability: Literal["VERIFIED_HISTORY", "NO_HISTORY", "CONFLICTED"]
    outcome: Outcome
    reason: Reason | None
    last_transition: P1LifecycleTransitionResponse | None
    transition_ids: tuple[str, ...]
    observation_references: tuple[P1ObservationReferenceResponse, ...]
    actionability: Literal["WATCH_ONLY"] = "WATCH_ONLY"
    execution_status: Literal["NON_EXECUTABLE"] = "NON_EXECUTABLE"
    expiry: Literal["EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"] = "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"
