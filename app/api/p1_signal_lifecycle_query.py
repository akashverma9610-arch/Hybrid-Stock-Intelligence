"""Per-request, read-only journal service. No migration or source activation."""
from app.api.errors import APIRequestError
from app.api.schemas.p1_signal_lifecycle import (
    P1LifecycleQuery, P1LifecycleResponse, P1LifecycleTransitionResponse,
    P1ObservationReferenceResponse,
)
from app.intelligence.p1_signal_lifecycle import Outcome
from app.storage.database import DatabaseSettings, DatabaseStorageMode
from app.storage.readonly_p1_signal_lifecycle import P1ReadUnavailable, ReadOnlyP1SignalLifecycleReader


class P1SignalLifecycleQueryService:
    def __init__(self, database: DatabaseSettings):
        self.database = database

    def read(self, query: P1LifecycleQuery) -> P1LifecycleResponse:
        if self.database.storage_mode is not DatabaseStorageMode.PERSISTENT_SQLITE:
            raise APIRequestError(status_code=503, code="P1_LIFECYCLE_STORE_UNAVAILABLE",
                                  message="P1 lifecycle persistent read storage is unavailable.")
        try:
            reader = ReadOnlyP1SignalLifecycleReader(self.database.url.removeprefix("sqlite:///"))
            try:
                view = reader.read(query.canonical_instrument_id, as_of=query.as_of)
            finally:
                reader.close()
        except P1ReadUnavailable as error:
            raise APIRequestError(status_code=503, code=error.code,
                                  message="P1 lifecycle history could not be verified; no activation was performed.") from None
        transition = None
        if view.last_transition is not None:
            transition = P1LifecycleTransitionResponse.model_validate(view.last_transition, from_attributes=True)
        availability = "CONFLICTED" if view.outcome is Outcome.CONFLICTED else "VERIFIED_HISTORY" if transition else "NO_HISTORY"
        return P1LifecycleResponse(
            canonical_instrument_id=query.canonical_instrument_id, as_of=query.as_of,
            availability=availability, outcome=view.outcome, reason=view.reason,
            last_transition=transition, transition_ids=view.transition_ids,
            observation_references=tuple(P1ObservationReferenceResponse(signal_id=i, fingerprint=f)
                                         for i, f in view.observation_references),
        )
