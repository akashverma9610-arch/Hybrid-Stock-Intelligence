"""Internal decision audit facade over existing immutable snapshot persistence."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


@dataclass(frozen=True, slots=True)
class DecisionAuditRecord:
    audit_id: str
    instrument_id: str
    as_of: datetime
    portfolio_snapshot_id: str | None
    universe_snapshot_id: str | None
    market_context_snapshot_id: str | None
    data_snapshot_ids: tuple[str, ...]
    source_summary: tuple[str, ...]
    diagnostic_registry_version: str
    decision_score_version: str
    confidence_version: str
    gate_policy_version: str
    rotation_policy_version: str
    engine_version: str
    final_public_decision: str
    internal_evidence_ids: tuple[str, ...]
    created_at: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DecisionOutcomeLink:
    link_id: str
    audit_id: str
    outcome_type: str
    outcome_id: str
    linked_at: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DecisionAuditBundle:
    record: DecisionAuditRecord
    outcomes: tuple[DecisionOutcomeLink, ...]


class DecisionAuditStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_record(self, value: DecisionAuditRecord) -> None:
        self._repository.save_snapshot(CoreApiSnapshot("decision-audit:" + value.audit_id, CoreApiSnapshotFamily.DECISION_AUDIT_RECORD, "v1", "decision-audit-v1", value.fingerprint, value.created_at, value))

    def get_record(self, audit_id: str) -> DecisionAuditRecord | None:
        snapshot = self._repository.get_snapshot("decision-audit:" + audit_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, DecisionAuditRecord) else None

    def save_outcome(self, value: DecisionOutcomeLink) -> None:
        self._repository.save_snapshot(CoreApiSnapshot("decision-outcome:" + value.link_id, CoreApiSnapshotFamily.DECISION_OUTCOME_LINK, "v1", "decision-outcome-link-v1", value.fingerprint, value.linked_at, value))

    def outcomes_for(self, audit_id: str) -> tuple[DecisionOutcomeLink, ...]:
        results: list[DecisionOutcomeLink] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.DECISION_OUTCOME_LINK, limit=100, offset=offset)
            results.extend(item.payload for item in page if isinstance(item.payload, DecisionOutcomeLink) and item.payload.audit_id == audit_id)
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(sorted(results, key=lambda item: (item.linked_at, item.link_id)))


class DecisionAuditService:
    """Internal reconstruction reads frozen references; it never re-runs today’s inputs."""
    def __init__(self, store: DecisionAuditStore) -> None:
        self._store = store

    def reconstruct_decision(self, audit_id: str) -> DecisionAuditBundle:
        record = self._store.get_record(audit_id)
        if record is None:
            raise ValueError("Decision audit record does not exist.")
        if record.fingerprint != decision_audit_fingerprint(record):
            raise ValueError("Decision audit record fingerprint mismatch.")
        outcomes = self._store.outcomes_for(audit_id)
        if any(item.fingerprint != decision_outcome_fingerprint(item) for item in outcomes):
            raise ValueError("Decision outcome linkage fingerprint mismatch.")
        return DecisionAuditBundle(record, outcomes)


def decision_audit_fingerprint(value: DecisionAuditRecord) -> str:
    return manifest_fingerprint(
        instrument=value.instrument_id, as_of=value.as_of, portfolio=value.portfolio_snapshot_id,
        universe=value.universe_snapshot_id, context=value.market_context_snapshot_id,
        data=value.data_snapshot_ids, source=value.source_summary,
        versions=(value.diagnostic_registry_version, value.decision_score_version, value.confidence_version, value.gate_policy_version, value.rotation_policy_version, value.engine_version),
        decision=value.final_public_decision, evidence=value.internal_evidence_ids,
    )


def decision_outcome_fingerprint(value: DecisionOutcomeLink) -> str:
    return manifest_fingerprint(audit=value.audit_id, type=value.outcome_type, outcome=value.outcome_id, linked_at=value.linked_at)
