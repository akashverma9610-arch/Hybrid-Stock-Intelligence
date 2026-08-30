from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.domain.models import AsOfSnapshot, Evidence, Instrument, MarketObservation


class MarketDataRepository(ABC):
    """Storage boundary; future PostgreSQL implementations conform to this API."""

    @abstractmethod
    def save_instrument(self, instrument: Instrument) -> None: ...

    @abstractmethod
    def observation_ids(self) -> set[str]: ...

    @abstractmethod
    def save_observation(self, observation: MarketObservation) -> int: ...

    @abstractmethod
    def eligible_observations_as_of(self, as_of_timestamp: datetime) -> tuple[tuple[int, MarketObservation], ...]: ...

    @abstractmethod
    def save_evidence(self, evidence: Evidence) -> None: ...

    @abstractmethod
    def save_snapshot(self, snapshot: AsOfSnapshot, record_keys: tuple[int, ...]) -> None: ...

    @abstractmethod
    def get_snapshot(self, snapshot_id: str) -> AsOfSnapshot | None: ...

    @abstractmethod
    def append_audit_event(self, event_type: str, occurred_timestamp: datetime, details: str) -> None: ...
