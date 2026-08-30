"""Immutable, recommendation-only model-governance drift facade."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class DriftSeverity(StrEnum):
    NONE = "NONE"
    WATCH = "WATCH"
    MATERIAL = "MATERIAL"
    CRITICAL = "CRITICAL"


class GovernanceHealth(StrEnum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    DISABLE_RECOMMENDED = "DISABLE_RECOMMENDED"
    DISABLED = "DISABLED"
    RESEARCH_ONLY = "RESEARCH_ONLY"


@dataclass(frozen=True, slots=True)
class ModelVersionPerformance:
    record_id: str
    strategy_id: str
    strategy_version: str
    metric: str
    value: Decimal
    window_start: datetime
    window_end: datetime
    regime: str | None
    evidence_ids: tuple[str, ...]
    created_at: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DriftObservation:
    observation_id: str
    strategy_id: str
    strategy_version: str
    metric: str
    baseline_record_id: str
    current_record_id: str
    delta: Decimal
    threshold: Decimal
    severity: DriftSeverity
    regime: str | None
    created_at: datetime
    fingerprint: str


@dataclass(frozen=True, slots=True)
class GovernanceAssessment:
    assessment_id: str
    strategy_id: str
    strategy_version: str
    drift_observation_ids: tuple[str, ...]
    health: GovernanceHealth
    recommendation: str
    created_at: datetime
    fingerprint: str


class GovernanceDriftStore:
    """Append-only storage using the pre-existing core snapshot repository."""
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_observation(self, value: DriftObservation) -> None:
        self._save("governance-drift:" + value.observation_id, CoreApiSnapshotFamily.GOVERNANCE_DRIFT_OBSERVATION, value.created_at, value.fingerprint, value)

    def get_observation(self, observation_id: str) -> DriftObservation | None:
        snapshot = self._repository.get_snapshot("governance-drift:" + observation_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, DriftObservation) else None

    def save_assessment(self, value: GovernanceAssessment) -> None:
        self._save("governance-assessment:" + value.assessment_id, CoreApiSnapshotFamily.GOVERNANCE_ASSESSMENT, value.created_at, value.fingerprint, value)

    def get_assessment(self, assessment_id: str) -> GovernanceAssessment | None:
        snapshot = self._repository.get_snapshot("governance-assessment:" + assessment_id)
        return snapshot.payload if snapshot and isinstance(snapshot.payload, GovernanceAssessment) else None

    def _save(self, snapshot_id: str, family: CoreApiSnapshotFamily, created_at: datetime, fingerprint: str, payload: object) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, family, "v1", "governance-drift-v1", fingerprint, created_at, payload))


class GovernanceDriftService:
    """Produces a recommendation only; it has no promotion or activation dependency."""
    def observe(self, *, baseline: ModelVersionPerformance, current: ModelVersionPerformance, threshold: Decimal, created_at: datetime) -> DriftObservation:
        if (baseline.strategy_id, baseline.strategy_version, baseline.metric) != (current.strategy_id, current.strategy_version, current.metric):
            raise ValueError("Drift comparison requires the same strategy version and metric.")
        delta = current.value - baseline.value
        severity = DriftSeverity.CRITICAL if delta <= -abs(threshold) * Decimal("2") else DriftSeverity.MATERIAL if delta <= -abs(threshold) else DriftSeverity.WATCH if delta < 0 else DriftSeverity.NONE
        seed = manifest_fingerprint(baseline=baseline.fingerprint, current=current.fingerprint, threshold=str(threshold), severity=severity.value)
        return DriftObservation("drift-" + seed[:24], current.strategy_id, current.strategy_version, current.metric, baseline.record_id, current.record_id, delta, threshold, severity, current.regime, created_at, seed)

    def assess(self, *, observations: tuple[DriftObservation, ...], strategy_id: str, strategy_version: str, created_at: datetime) -> GovernanceAssessment:
        if any(item.strategy_id != strategy_id or item.strategy_version != strategy_version for item in observations):
            raise ValueError("Governance assessment references a different strategy version.")
        highest = max((item.severity for item in observations), default=DriftSeverity.NONE, key=lambda value: (DriftSeverity.NONE, DriftSeverity.WATCH, DriftSeverity.MATERIAL, DriftSeverity.CRITICAL).index(value))
        health = {DriftSeverity.NONE: GovernanceHealth.HEALTHY, DriftSeverity.WATCH: GovernanceHealth.WATCH, DriftSeverity.MATERIAL: GovernanceHealth.DEGRADED, DriftSeverity.CRITICAL: GovernanceHealth.DISABLE_RECOMMENDED}[highest]
        recommendation = "REVIEW_REQUIRED_NO_AUTOMATIC_DEPLOYMENT" if health is not GovernanceHealth.HEALTHY else "CONTINUE_OBSERVATION"
        seed = manifest_fingerprint(strategy=(strategy_id, strategy_version), observations=[item.fingerprint for item in observations], health=health.value)
        return GovernanceAssessment("governance-" + seed[:24], strategy_id, strategy_version, tuple(item.observation_id for item in observations), health, recommendation, created_at, seed)
