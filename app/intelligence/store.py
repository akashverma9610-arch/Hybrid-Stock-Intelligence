"""Immutable persistence adapter for intelligence records; no migration needed."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository

class IntelligenceSnapshotStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save(self, *, record_id: str, family: CoreApiSnapshotFamily, value: object, created_at: datetime) -> None:
        self._repository.save_snapshot(CoreApiSnapshot("intelligence:" + family.value + ":" + record_id, family, "v1", "economic-intelligence-v1", sha256(repr(value).encode()).hexdigest(), created_at, value))
    def get(self, *, record_id: str, family: CoreApiSnapshotFamily):
        record = self._repository.get_snapshot("intelligence:" + family.value + ":" + record_id)
        return record.payload if record else None
