"""Immutable ownership repositories implemented with existing core snapshots."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from app.ownership.models import (
    OwnershipCategory, OwnershipComparison, OwnershipNormalizedUnit, OwnershipObservation,
    OwnershipRawFact,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


class OwnershipWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"


class OwnershipObservationStore:
    """Append-only raw facts and observations with closed conflict handling."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_raw_fact(self, value: OwnershipRawFact) -> OwnershipWriteOutcome:
        existing = self.get_raw_fact(value.fact_id)
        if existing is not None:
            if existing == value:
                return OwnershipWriteOutcome.IDENTICAL
            raise ValueError("Ownership raw facts are immutable and cannot be overwritten.")
        if any(self._raw_logical_key(item) == self._raw_logical_key(value) and item.fingerprint != value.fingerprint
               for item in self.list_raw_facts(instrument_id=value.canonical_instrument_id, limit=500)):
            raise ValueError("OWNERSHIP_RAW_FACT_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.fact_id, CoreApiSnapshotFamily.OWNERSHIP_RAW_FACT, "v1",
            "nse-reg31-ownership-raw-fact-v1", value.fingerprint, value.received_at, value,
        ))
        return OwnershipWriteOutcome.INSERTED

    def save_observation(self, value: OwnershipObservation) -> OwnershipWriteOutcome:
        existing = self.get(value.observation_id)
        if existing is not None:
            if existing == value:
                return OwnershipWriteOutcome.IDENTICAL
            raise ValueError("Ownership observations are immutable and cannot be overwritten.")
        if any(self._observation_logical_key(item) == self._observation_logical_key(value) and item.fingerprint != value.fingerprint
               for item in self.list_by_instrument(value.canonical_instrument_id, limit=500)):
            raise ValueError("OWNERSHIP_OBSERVATION_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(
            value.observation_id, CoreApiSnapshotFamily.OWNERSHIP_OBSERVATION, "v1",
            "nse-reg31-ownership-observation-v1", value.fingerprint, value.received_at, value,
        ))
        return OwnershipWriteOutcome.INSERTED

    def get_raw_fact(self, fact_id: str) -> OwnershipRawFact | None:
        snapshot = self._repository.get_snapshot(fact_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, OwnershipRawFact) else None

    def get(self, observation_id: str) -> OwnershipObservation | None:
        snapshot = self._repository.get_snapshot(observation_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, OwnershipObservation) else None

    def list_raw_facts(self, *, instrument_id: str | None = None, as_of: datetime | None = None,
                       limit: int = 500) -> tuple[OwnershipRawFact, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Ownership raw-fact limit must be between 1 and 500.")
        values = tuple(item for item in self._all(CoreApiSnapshotFamily.OWNERSHIP_RAW_FACT)
                       if isinstance(item, OwnershipRawFact)
                       and (instrument_id is None or item.canonical_instrument_id == instrument_id)
                       and (as_of is None or (item.published_at <= as_of and item.received_at <= as_of)))
        return tuple(sorted(values, key=lambda item: (item.reporting_period, item.published_at, item.fact_id), reverse=True))[:limit]

    def list_by_instrument(self, instrument_id: str, *, as_of: datetime | None = None,
                           limit: int = 500) -> tuple[OwnershipObservation, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("Ownership observation limit must be between 1 and 500.")
        values = tuple(item for item in self._all(CoreApiSnapshotFamily.OWNERSHIP_OBSERVATION)
                       if isinstance(item, OwnershipObservation) and item.canonical_instrument_id == instrument_id
                       and (as_of is None or (item.published_at <= as_of and item.received_at <= as_of)))
        return tuple(sorted(values, key=lambda item: (item.reporting_period, item.published_at, item.observation_id), reverse=True))[:limit]

    def latest_comparable(self, instrument_id: str, category: OwnershipCategory, *, as_of: datetime) -> OwnershipComparison:
        values = tuple(item for item in self.list_by_instrument(instrument_id, as_of=as_of, limit=500)
                       if item.category is category)
        if not values:
            return OwnershipComparison("INSUFFICIENT_DATA", category, None, None, None, "OWNERSHIP_CATEGORY_UNAVAILABLE")
        current = values[0]
        if current.normalized_unit is not OwnershipNormalizedUnit.PERCENTAGE_POINTS or current.normalized_value is None:
            return OwnershipComparison("NON_COMPARABLE", category, current.observation_id, None, None, "OWNERSHIP_NORMALIZED_PERCENTAGE_REQUIRED")
        prior = next((item for item in values[1:] if item.normalized_unit is current.normalized_unit
                      and item.scope == current.scope and item.category_relationship is current.category_relationship
                      and item.normalized_value is not None), None)
        if prior is None:
            return OwnershipComparison("NON_COMPARABLE", category, current.observation_id, None, None, "OWNERSHIP_COMPARABLE_PRIOR_PERIOD_UNAVAILABLE")
        return OwnershipComparison("COMPARABLE", category, current.observation_id, prior.observation_id,
                                   current.normalized_value - prior.normalized_value, None)

    def _all(self, family: CoreApiSnapshotFamily):
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            if not page:
                return
            yield from (item.payload for item in page)
            if len(page) < 100:
                return
            offset += len(page)

    @staticmethod
    def _raw_logical_key(value: OwnershipRawFact) -> tuple[object, ...]:
        return (value.canonical_instrument_id, value.reporting_period, value.raw_concept,
                value.source_context_reference, value.scope)

    @staticmethod
    def _observation_logical_key(value: OwnershipObservation) -> tuple[object, ...]:
        return (value.canonical_instrument_id, value.reporting_period, value.category,
                value.category_relationship, value.scope)
