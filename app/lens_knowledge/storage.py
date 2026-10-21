"""Persist immutable non-active lens coverage using existing snapshot storage."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
import json
import re

from app.lens_knowledge.universe import UniverseLensCoverageBatch
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository

_FAMILY = CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE


def _hash(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _identity(batch: UniverseLensCoverageBatch) -> str:
    # Content changes for the same page/cutoff are conflicts, not silent updates.
    return "draft-lens-coverage:" + _hash((batch.universe_snapshot_id, batch.universe_checksum,
        batch.catalog_fingerprint, batch.as_of.astimezone(UTC).isoformat(),
        batch.input_basis, batch.start, batch.next_cursor))


def _validate(batch: UniverseLensCoverageBatch) -> None:
    if batch.input_basis == "CANONICAL_CURRENT_DESCRIPTIVE":
        if (tuple(x[0] for x in batch.canonical_input_fingerprints)
                != tuple(x.instrument_id for x in batch.securities)
                or any(not re.fullmatch(r"sha256:[0-9a-f]{64}", fp) for _, fp in batch.canonical_input_fingerprints)
                or any(not isinstance(fp, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", fp)
                    for fp in (batch.canonical_strategy_fingerprint, batch.canonical_limitations_fingerprint))):
            raise ValueError("LENS_CANONICAL_PROVENANCE_REQUIRED")
    elif (batch.input_basis != "SUPPLIED_UNVERIFIED" or batch.canonical_input_fingerprints
            or batch.canonical_strategy_fingerprint is not None or batch.canonical_limitations_fingerprint is not None):
        raise ValueError("LENS_COVERAGE_BASIS_INVALID")
    if (batch.as_of.tzinfo is None or batch.as_of.utcoffset() is None
            or not batch.universe_snapshot_id or not batch.universe_checksum
            or len(batch.catalog_fingerprint) != 64 or not 0 <= batch.start <= batch.next_cursor <= batch.universe_count
            or batch.next_cursor - batch.start != len(batch.securities)
            or batch.completed != (batch.next_cursor == batch.universe_count)
            or len({row.instrument_id for row in batch.securities}) != len(batch.securities)):
        raise ValueError("Invalid draft lens coverage batch")
    supplied = sum(row.diagnostic_source_state == "SUPPLIED" for row in batch.securities)
    if supplied != batch.securities_with_results or len(batch.securities) - supplied != batch.securities_without_results:
        raise ValueError("Lens coverage counts disagree")
    for row in batch.securities:
        if (row.diagnostic_source_state not in {"SUPPLIED", "UNAVAILABLE"}
                or (row.diagnostic_source_state == "SUPPLIED") != (row.diagnostics_fingerprint is not None)
                or len(row.assessments) != 35 or len({x.lens_id for x in row.assessments}) != 35
                or any(x.status != "UNKNOWN" or x.instrument_id != row.instrument_id or x.as_of != batch.as_of for x in row.assessments)):
            raise ValueError("Invalid security lens coverage")


class DraftLensCoverageStore:
    """Idempotent exact replay; divergent same-page writes fail closed."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, batch: UniverseLensCoverageBatch, *, recorded_at: datetime) -> str:
        _validate(batch)
        if (recorded_at.tzinfo is None or recorded_at.utcoffset() is None or recorded_at < batch.as_of):
            raise ValueError("LENS_RETENTION_TIME_INVALID")
        snapshot_id = _identity(batch)
        fingerprint = _hash((asdict(batch), recorded_at.astimezone(UTC).isoformat()))
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if self.get(snapshot_id) != batch:
                raise ValueError("DRAFT_LENS_COVERAGE_CONFLICT")
            return snapshot_id
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, _FAMILY, "v1",
            "UniverseLensCoverageBatch", fingerprint, recorded_at.astimezone(UTC), batch))
        return snapshot_id

    def get(self, snapshot_id: str) -> UniverseLensCoverageBatch | None:
        snapshot = self._repository.get_snapshot(snapshot_id)
        if snapshot is None:
            return None
        if (snapshot.family != _FAMILY or snapshot.schema_version != "v1"
                or snapshot.record_type != "UniverseLensCoverageBatch"
                or not isinstance(snapshot.payload, UniverseLensCoverageBatch)):
            raise ValueError("Invalid lens coverage snapshot")
        batch = snapshot.payload
        _validate(batch)
        if (_identity(batch) != snapshot.snapshot_id or snapshot.created_at.tzinfo is None
                or snapshot.created_at.utcoffset() is None or snapshot.created_at < batch.as_of
                or _hash((asdict(batch), snapshot.created_at.astimezone(UTC).isoformat())) != snapshot.fingerprint):
            raise ValueError("Lens coverage snapshot integrity failure")
        return batch
