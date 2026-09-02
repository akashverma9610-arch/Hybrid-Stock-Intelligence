"""Stored-only, context-aware Six Gates lineage for ``UnifiedIntelligenceState``.

Persisted gate evaluations include action and possible portfolio-snapshot
context.  They are not universal stock truth.  The core state therefore keeps
only a bounded, explicitly context-dependent lineage reference and leaves
evaluation interpretation to a future output-context layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.storage.governance_repository import StrategyGovernanceRepository


class StoredGateDecision(Protocol):
    gate_id: str
    outcome: object
    evidence_ids: tuple[str, ...]


class StoredSixGatesEvaluation(Protocol):
    id: str
    instrument_id: str
    strategy_version: object
    registry_version: str
    scoring_configuration_version: str
    gate_configuration_version: str
    scorecard_id: str
    input_snapshot_id: str | None
    action_context: object
    as_of_timestamp: datetime
    evaluated_at: datetime
    decisions: tuple[StoredGateDecision, ...]
    eligibility: object
    failed_gate_ids: tuple[str, ...]
    insufficient_gate_ids: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    configuration_parameters: object


class StoredSixGatesEvaluationSource(Protocol):
    """Read-only boundary for existing immutable gate evaluation artifacts."""

    def list_stored_six_gates_evaluations(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredSixGatesEvaluation, ...]: ...


class StrategyGovernanceSixGatesEvaluationSource:
    """Expose one known persisted evaluation without adding a broad repository query."""

    def __init__(self, repository: StrategyGovernanceRepository, *, evaluation_id: str) -> None:
        self._repository = repository
        self._evaluation_id = evaluation_id

    def list_stored_six_gates_evaluations(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredSixGatesEvaluation, ...]:
        value = self._repository.get_execution_gate_evaluation(self._evaluation_id)
        if value is None or value.instrument_id != canonical_instrument_id:
            return ()
        return (value,)


class CanonicalSixGatesEvaluationSource:
    """Read canonical gate artifacts without creating generic score anchors."""

    def __init__(self, repository: StrategyGovernanceRepository) -> None:
        self._repository = repository

    def list_stored_six_gates_evaluations(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredSixGatesEvaluation, ...]:
        return tuple(
            value
            for value in self._repository.list_canonical_execution_gate_evaluations(canonical_instrument_id)
            if value.as_of_timestamp <= as_of and value.evaluated_at <= as_of
        )


class SixGatesEvidenceAdapter:
    """Project stored Six Gates lineage without making an execution conclusion."""

    def __init__(self, evaluations: StoredSixGatesEvaluationSource | None = None) -> None:
        self._evaluations = evaluations

    def artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        if self._evaluations is None:
            return (_unavailable(canonical_instrument_id, "SIX_GATES_DURABLE_READ_BOUNDARY_MISSING"),)
        values = tuple(
            value
            for value in self._evaluations.list_stored_six_gates_evaluations(canonical_instrument_id, as_of=as_of)
            if _eligible(value, canonical_instrument_id, as_of)
        )
        if not values:
            return (_unavailable(canonical_instrument_id, "SIX_GATES_NOT_YET_COMPUTED"),)
        selected = max(values, key=lambda value: (
            value.as_of_timestamp,
            value.evaluated_at,
            value.gate_configuration_version,
            value.id,
        ))
        return (_context_dependent_artifact(selected),)


class SixGatesEvidenceStoredSource:
    """U14B-3E3 source for normal ``CompositeStoredIntelligenceSource`` wiring."""

    def __init__(self, evaluations: StoredSixGatesEvaluationSource | None = None) -> None:
        self._adapter = SixGatesEvidenceAdapter(evaluations)

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        return self._adapter.artifacts(canonical_instrument_id, as_of=as_of)


def _context_dependent_artifact(value: StoredSixGatesEvaluation) -> StoredIntelligenceArtifact:
    decisions = tuple(sorted(
        ((item.gate_id, _enum_value(item.outcome), tuple(sorted(item.evidence_ids))) for item in value.decisions),
        key=lambda item: item[0],
    ))
    source_lineage = manifest_fingerprint(
        strategy_id=value.strategy_version.strategy_id,
        strategy_version=value.strategy_version.version,
        registry_version=value.registry_version,
        score_configuration_version=value.scoring_configuration_version,
        gate_configuration_version=value.gate_configuration_version,
        scorecard_id=value.scorecard_id,
        input_snapshot_id=value.input_snapshot_id,
        action_context=_enum_value(value.action_context),
        diagnostic_ids=tuple(sorted(value.diagnostic_ids)),
        evidence_ids=tuple(sorted(value.evidence_ids)),
    )
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.instrument_id,
        domain=IntelligenceEvidenceDomain.SIX_GATES,
        artifact_id=value.id,
        artifact_fingerprint=six_gates_evaluation_artifact_fingerprint(value),
        availability=IntelligenceEvidenceAvailability.PARTIAL,
        evidence_as_of=value.as_of_timestamp,
        observed_at=value.evaluated_at,
        available_at=value.evaluated_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=value.gate_configuration_version,
        source_provenance_fingerprint=source_lineage,
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.POLICY,
        warnings=tuple(sorted(set(value.warnings) | {
            "SIX_GATES_CONTEXT_DEPENDENT",
            "SIX_GATES_RESULT_DOWNSTREAM_ONLY",
            "SIX_GATES_INVALIDATION_POLICY",
        })),
    )


def six_gates_evaluation_artifact_fingerprint(value: StoredSixGatesEvaluation) -> str:
    """Canonical bounded identity of an already-persisted gates evaluation."""
    decisions = tuple(sorted(
        ((item.gate_id, _enum_value(item.outcome), tuple(sorted(item.evidence_ids))) for item in value.decisions),
        key=lambda item: item[0],
    ))
    return manifest_fingerprint(
            evaluation_id=value.id,
            instrument_id=value.instrument_id,
            strategy_id=value.strategy_version.strategy_id,
            strategy_version=value.strategy_version.version,
            registry_version=value.registry_version,
            score_configuration_version=value.scoring_configuration_version,
            gate_configuration_version=value.gate_configuration_version,
            scorecard_id=value.scorecard_id,
            input_snapshot_id=value.input_snapshot_id,
            action_context=_enum_value(value.action_context),
            as_of_timestamp=value.as_of_timestamp,
            evaluated_at=value.evaluated_at,
            decisions=decisions,
            eligibility=_enum_value(value.eligibility),
            failed_gate_ids=tuple(sorted(value.failed_gate_ids)),
            insufficient_gate_ids=tuple(sorted(value.insufficient_gate_ids)),
            warnings=tuple(sorted(value.warnings)),
            configuration_parameters=value.configuration_parameters,
    )


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _unavailable(canonical_instrument_id: str, warning: str) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.SIX_GATES,
        artifact_id="six-gates:unavailable",
        artifact_fingerprint=manifest_fingerprint(
            domain=IntelligenceEvidenceDomain.SIX_GATES.value, warning=warning,
        ),
        availability=IntelligenceEvidenceAvailability.UNAVAILABLE,
        evidence_as_of=None,
        observed_at=None,
        available_at=None,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=None,
        source_provenance_fingerprint=None,
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.POLICY,
        warnings=(warning,),
    )


def _eligible(value: StoredSixGatesEvaluation, canonical_instrument_id: str, as_of: datetime) -> bool:
    return (
        value.instrument_id == canonical_instrument_id
        and _aware(value.as_of_timestamp)
        and _aware(value.evaluated_at)
        and value.as_of_timestamp <= as_of
        and value.evaluated_at <= as_of
    )


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "SixGatesEvidenceAdapter", "SixGatesEvidenceStoredSource", "StoredGateDecision",
    "StoredSixGatesEvaluation", "StoredSixGatesEvaluationSource",
    "StrategyGovernanceSixGatesEvaluationSource", "six_gates_evaluation_artifact_fingerprint",
    "CanonicalSixGatesEvaluationSource",
)
