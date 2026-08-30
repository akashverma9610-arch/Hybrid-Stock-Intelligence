from __future__ import annotations

import json
from datetime import datetime

from app.domain.models import AsOfSnapshot, MarketObservation, ValidationResult
from app.storage.repository import MarketDataRepository
from app.storage.sqlite_repository import deterministic_snapshot_id
from app.validation.observation_validator import ObservationValidator


SNAPSHOT_INCLUSION_POLICY = "validation=valid;market_timestamp<=as_of;retrieved_timestamp<=as_of"


class FoundationService:
    """The deterministic data → validation → storage → snapshot pipeline."""

    def __init__(self, repository: MarketDataRepository, validator: ObservationValidator) -> None:
        self._repository = repository
        self._validator = validator

    def ingest(self, observation: MarketObservation, *, evaluated_timestamp: datetime) -> ValidationResult:
        validation = self._validator.validate(
            observation,
            evaluated_timestamp=evaluated_timestamp,
            existing_observation_ids=self._repository.observation_ids(),
        )
        validated_observation = observation.with_validation(validation)
        self._repository.save_instrument(observation.instrument)
        self._repository.save_observation(validated_observation)
        self._repository.append_audit_event(
            "observation.accepted" if validation.eligible_for_analysis else "observation.rejected",
            evaluated_timestamp,
            json.dumps({"observation_id": observation.id, "status": validation.status.value}, sort_keys=True),
        )
        return validation

    def build_as_of_snapshot(self, *, as_of_timestamp: datetime) -> AsOfSnapshot:
        eligible_records = self._repository.eligible_observations_as_of(as_of_timestamp)
        eligible_records = tuple((key, observation) for key, observation in eligible_records if _available_at(observation, as_of_timestamp))
        observations = tuple(observation for _, observation in eligible_records)
        snapshot = AsOfSnapshot(
            id=deterministic_snapshot_id(as_of_timestamp, observations, SNAPSHOT_INCLUSION_POLICY),
            as_of_timestamp=as_of_timestamp,
            # Logical snapshot creation time is the as-of time. This keeps the
            # snapshot content and identity deterministic for replays/backtests.
            created_timestamp=as_of_timestamp,
            inclusion_policy=SNAPSHOT_INCLUSION_POLICY,
            observations=observations,
        )
        self._repository.save_snapshot(snapshot, tuple(record_key for record_key, _ in eligible_records))
        self._repository.append_audit_event(
            "snapshot.built",
            as_of_timestamp,
            json.dumps({"snapshot_id": snapshot.id, "observation_count": len(observations)}, sort_keys=True),
        )
        return snapshot


def _available_at(observation: MarketObservation, as_of_timestamp: datetime) -> bool:
    """Financial period end is not knowledge time: publication controls availability."""
    if str(observation.kind) != "fundamental":
        return True
    published = observation.payload.get("publication_timestamp") if isinstance(observation.payload, dict) else None
    if isinstance(published, str):
        try:
            published = datetime.fromisoformat(published)
        except ValueError:
            return False
    return isinstance(published, datetime) and published <= as_of_timestamp
