"""Generic immutable storage for #035 internal records using Core snapshots."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class LiveReadinessSnapshotStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save(self, *, record_id: str, family: CoreApiSnapshotFamily, value: object, created_at: datetime) -> None:
        self._repository.save_snapshot(CoreApiSnapshot("live-readiness:" + family.value + ":" + record_id, family, "v1", "live-readiness-v1", sha256(repr(value).encode()).hexdigest(), created_at, value))
    def get(self, *, record_id: str, family: CoreApiSnapshotFamily):
        snapshot = self._repository.get_snapshot("live-readiness:" + family.value + ":" + record_id)
        return snapshot.payload if snapshot else None
