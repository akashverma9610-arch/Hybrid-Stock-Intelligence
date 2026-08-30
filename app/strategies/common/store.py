"""Append-only persistence using the existing Core snapshot architecture."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class StrategySnapshotStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, *, record_id: str, family: CoreApiSnapshotFamily, value: object, created_at: datetime) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(
            f"strategy:{family.value}:{record_id}", family, "v1", "strategy-candidate-v1",
            sha256(repr(value).encode()).hexdigest(), created_at, value,
        ))

    def get(self, *, record_id: str, family: CoreApiSnapshotFamily):
        value = self._repository.get_snapshot(f"strategy:{family.value}:{record_id}")
        return value.payload if value else None
