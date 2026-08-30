"""Immutable durable operations metadata backed by the existing snapshot store."""
from __future__ import annotations

from hashlib import sha256

from app.data_operations.models import EvidenceDataFamily, EvidenceReconciliationFinding, EvidenceRefreshRun, EvidenceRefreshWatermark
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


def _fingerprint(value: object) -> str:
    return sha256(repr(value).encode("utf-8")).hexdigest()


class DataOperationsStore:
    """Append-only operational record store.

    Watermarks are historical observations, rather than mutable pointers; the
    latest value is a convenience query and never replaces evidence or prior
    run records.
    """

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_run(self, value: EvidenceRefreshRun) -> None:
        self._save(CoreApiSnapshotFamily.EVIDENCE_REFRESH_RUN, value.run_id, value, value.completed_at)

    def get_run(self, run_id: str) -> EvidenceRefreshRun | None:
        snapshot = self._repository.get_snapshot(run_id)
        return snapshot.payload if snapshot is not None and snapshot.family is CoreApiSnapshotFamily.EVIDENCE_REFRESH_RUN and isinstance(snapshot.payload, EvidenceRefreshRun) else None

    def runs(self, family: EvidenceDataFamily | None = None) -> tuple[EvidenceRefreshRun, ...]:
        values = tuple(item.payload for item in self._all(CoreApiSnapshotFamily.EVIDENCE_REFRESH_RUN) if isinstance(item.payload, EvidenceRefreshRun))
        filtered = tuple(item for item in values if family is None or item.family is family)
        return tuple(sorted(filtered, key=lambda item: (item.completed_at, item.run_id)))

    def latest_run(self, family: EvidenceDataFamily) -> EvidenceRefreshRun | None:
        values = self.runs(family)
        return values[-1] if values else None

    def save_watermark(self, value: EvidenceRefreshWatermark) -> None:
        self._save(CoreApiSnapshotFamily.EVIDENCE_REFRESH_WATERMARK, value.watermark_id, value, value.observed_at)

    def latest_watermark(self, family: EvidenceDataFamily, *, provider: str | None = None, scope: str | None = None) -> EvidenceRefreshWatermark | None:
        values = tuple(
            item.payload for item in self._all(CoreApiSnapshotFamily.EVIDENCE_REFRESH_WATERMARK)
            if isinstance(item.payload, EvidenceRefreshWatermark)
            and item.payload.family is family
            and (provider is None or item.payload.provider == provider)
            and (scope is None or item.payload.scope == scope)
        )
        return max(values, key=lambda item: (item.observed_at, item.watermark_id)) if values else None

    def save_finding(self, value: EvidenceReconciliationFinding) -> None:
        self._save(CoreApiSnapshotFamily.EVIDENCE_RECONCILIATION_FINDING, value.finding_id, value, value.observed_at)

    def findings(self, run_id: str | None = None) -> tuple[EvidenceReconciliationFinding, ...]:
        values = tuple(item.payload for item in self._all(CoreApiSnapshotFamily.EVIDENCE_RECONCILIATION_FINDING) if isinstance(item.payload, EvidenceReconciliationFinding))
        return tuple(sorted((item for item in values if run_id is None or item.run_id == run_id), key=lambda item: (item.observed_at, item.finding_id)))

    def _save(self, family: CoreApiSnapshotFamily, identifier: str, value: object, created_at) -> None:
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.family is family and existing.payload == value:
                return
            raise ValueError("Data operations records are immutable and cannot be overwritten.")
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", type(value).__name__, _fingerprint(value), created_at, value))

    def _all(self, family: CoreApiSnapshotFamily):
        values = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)
