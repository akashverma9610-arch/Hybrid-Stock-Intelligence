from __future__ import annotations

from hashlib import sha256
from app.data_coverage.models import DataCoverageRecord, DataCoverageSummary
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class DataCoverageSnapshotStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save_record(self, value: DataCoverageRecord) -> None: self._save(CoreApiSnapshotFamily.DATA_COVERAGE_RECORD, "data-coverage:" + value.coverage_id, value, value.as_of)
    def save_summary(self, value: DataCoverageSummary) -> None: self._save(CoreApiSnapshotFamily.DATA_COVERAGE_SUMMARY, "data-coverage-summary:" + value.summary_id, value, value.as_of)
    def get_record(self, coverage_id: str) -> DataCoverageRecord | None:
        value = self._repository.get_snapshot("data-coverage:" + coverage_id)
        return value.payload if value is not None and isinstance(value.payload, DataCoverageRecord) else None
    def get_summary(self, summary_id: str) -> DataCoverageSummary | None:
        value = self._repository.get_snapshot("data-coverage-summary:" + summary_id)
        return value.payload if value is not None and isinstance(value.payload, DataCoverageSummary) else None
    def _save(self, family, snapshot_id, value, created_at) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, family, "v1", "data-coverage-v1", sha256(repr(value).encode()).hexdigest(), created_at, value))
