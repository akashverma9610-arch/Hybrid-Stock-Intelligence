"""Durable, append-only raw macro evidence on the existing snapshot repository."""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.macro.service import MacroEvidence
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


class MacroEvidenceWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    DUPLICATE = "DUPLICATE"


def macro_evidence_fingerprint(value: MacroEvidence) -> str:
    """Fingerprint every factual field, including source and vintage lineage."""
    return manifest_fingerprint(**_manifest_values(value))


class MacroEvidenceStore:
    """Snapshot-backed raw evidence store with insert-only source lineage."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: MacroEvidence) -> MacroEvidenceWriteOutcome:
        _validate(value)
        snapshot_id = _snapshot_id(value.evidence_id)
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.MACRO_EVIDENCE and existing.payload == value:
                return MacroEvidenceWriteOutcome.DUPLICATE
            raise ValueError("Macro evidence is immutable and cannot be overwritten.")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id=snapshot_id,
            family=CoreApiSnapshotFamily.MACRO_EVIDENCE,
            schema_version="v1",
            record_type="macro-evidence-v1",
            fingerprint=macro_evidence_fingerprint(value),
            created_at=value.available_at,
            payload=value,
        ))
        return MacroEvidenceWriteOutcome.INSERTED

    def get(self, evidence_id: str) -> MacroEvidence | None:
        snapshot = self._repository.get_snapshot(_snapshot_id(evidence_id))
        if snapshot is None:
            return None
        if snapshot.family is not CoreApiSnapshotFamily.MACRO_EVIDENCE or not isinstance(snapshot.payload, MacroEvidence):
            raise ValueError("Stored macro evidence payload is invalid.")
        _validate(snapshot.payload)
        if snapshot.fingerprint != macro_evidence_fingerprint(snapshot.payload):
            raise ValueError("Stored macro evidence fingerprint is invalid.")
        return snapshot.payload

    def list_stored_macro_evidence(self, *, as_of: datetime) -> tuple[MacroEvidence, ...]:
        _aware(as_of, "as_of")
        values: list[MacroEvidence] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.MACRO_EVIDENCE, limit=100, offset=offset)
            for snapshot in page:
                value = self.get(snapshot.snapshot_id.removeprefix("macro-evidence:"))
                if value is not None and value.eligible_as_of(as_of):
                    values.append(value)
            if len(page) < 100:
                return tuple(sorted(values, key=_key))
            offset += len(page)

    def list_all(self) -> tuple[MacroEvidence, ...]:
        # Used only by a source job to preserve first-observed receipt time and
        # to establish explicit revision lineage for changed official values.
        return self.list_stored_macro_evidence(as_of=datetime.max.replace(tzinfo=UTC))


def _snapshot_id(evidence_id: str) -> str:
    return "macro-evidence:" + evidence_id


def _validate(value: MacroEvidence) -> None:
    if not value.evidence_id.strip() or not value.component.strip() or not value.source_reference.strip():
        raise ValueError("Macro evidence identity is required.")
    _aware(value.available_at, "available_at")
    for field in ("observed_at", "published_at", "effective_at", "received_at"):
        item = getattr(value, field)
        if item is not None:
            _aware(item, field)
    if value.value is not None and not value.unit:
        raise ValueError("Macro evidence value unit is required.")
    if value.value is not None and value.frequency is None:
        raise ValueError("Macro evidence frequency is required.")
    if tuple(sorted(set(value.warnings))) != value.warnings:
        raise ValueError("Macro evidence warnings must be canonical.")


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"Macro evidence {name} must be timezone-aware.")


def _manifest_values(value: MacroEvidence) -> dict:
    values = asdict(value)
    return {
        key: (
            item.value if isinstance(item, StrEnum) else
            item.astimezone(UTC).isoformat() if isinstance(item, datetime) else
            item
        )
        for key, item in values.items()
    }


def _key(value: MacroEvidence) -> tuple:
    return (
        value.available_at.astimezone(UTC), value.family.value, value.component,
        value.observed_at.astimezone(UTC) if value.observed_at else datetime.min.replace(tzinfo=UTC),
        value.evidence_id,
    )


__all__ = ("MacroEvidenceStore", "MacroEvidenceWriteOutcome", "macro_evidence_fingerprint")
