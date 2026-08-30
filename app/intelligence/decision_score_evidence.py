"""Stored-only Decision Score lineage for ``UnifiedIntelligenceState``.

The canonical immutable ``DecisionScorecard`` is already persisted by the
governance repository.  This module projects its bounded lineage only; it
does not build a scorecard, inspect gate results, or make an action decision.
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


class StoredDecisionScorecard(Protocol):
    """Bounded structural contract for an already-persisted scorecard."""

    id: str
    instrument_id: str
    strategy_version: object
    registry_version: str
    configuration_version: str
    as_of_timestamp: datetime
    evaluated_at: datetime
    components: tuple[object, ...]
    final_score: object | None
    score_status: str
    data_confidence: float | None
    warnings: tuple[str, ...]


class StoredDecisionScorecardSource(Protocol):
    """Read-only boundary for existing immutable scorecard artifacts."""

    def list_stored_decision_scorecards(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredDecisionScorecard, ...]: ...


class StrategyGovernanceDecisionScorecardSource:
    """Expose one known persisted scorecard without inventing a broad query API."""

    def __init__(self, repository: StrategyGovernanceRepository, *, scorecard_id: str) -> None:
        self._repository = repository
        self._scorecard_id = scorecard_id

    def list_stored_decision_scorecards(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredDecisionScorecard, ...]:
        value = self._repository.get_decision_scorecard(self._scorecard_id)
        if value is None or value.instrument_id != canonical_instrument_id:
            return ()
        return (value,)


class DecisionScoreEvidenceAdapter:
    """Project an already-computed scorecard as bounded DECISION_SCORE evidence."""

    def __init__(self, scorecards: StoredDecisionScorecardSource | None = None) -> None:
        self._scorecards = scorecards

    def artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        if self._scorecards is None:
            return (_unavailable(canonical_instrument_id, "DECISION_SCORE_DURABLE_READ_BOUNDARY_MISSING"),)
        values = tuple(
            value
            for value in self._scorecards.list_stored_decision_scorecards(canonical_instrument_id, as_of=as_of)
            if _eligible(value, canonical_instrument_id, as_of)
        )
        if not values:
            return (_unavailable(canonical_instrument_id, "DECISION_SCORE_NOT_YET_COMPUTED"),)
        selected = max(values, key=lambda value: (
            value.as_of_timestamp,
            value.evaluated_at,
            value.configuration_version,
            value.id,
        ))
        return (_artifact(selected),)


class DecisionScoreEvidenceStoredSource:
    """U14B-3E2 source for normal ``CompositeStoredIntelligenceSource`` wiring."""

    def __init__(self, scorecards: StoredDecisionScorecardSource | None = None) -> None:
        self._adapter = DecisionScoreEvidenceAdapter(scorecards)

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        return self._adapter.artifacts(canonical_instrument_id, as_of=as_of)


def _artifact(value: StoredDecisionScorecard) -> StoredIntelligenceArtifact:
    components = tuple(sorted(value.components, key=lambda item: item.component_id))
    diagnostic_ids = tuple(sorted({item_id for item in components for item_id in item.diagnostic_ids}))
    evidence_ids = tuple(sorted({item_id for item in components for item_id in item.evidence_ids}))
    complete = value.score_status == "COMPLETE"
    warnings = set(value.warnings)
    if not complete:
        warnings.add("DECISION_SCORE_PARTIAL")
    # Score configuration is the existing closest invalidation contract.  A
    # distinct score domain would overlap the established POLICY vocabulary.
    warnings.add("DECISION_SCORE_INVALIDATION_POLICY")
    return StoredIntelligenceArtifact(
        canonical_instrument_id=value.instrument_id,
        domain=IntelligenceEvidenceDomain.DECISION_SCORE,
        artifact_id=value.id,
        artifact_fingerprint=decision_scorecard_artifact_fingerprint(value),
        availability=(
            IntelligenceEvidenceAvailability.AVAILABLE
            if complete else IntelligenceEvidenceAvailability.PARTIAL
        ),
        evidence_as_of=value.as_of_timestamp,
        observed_at=value.evaluated_at,
        available_at=value.evaluated_at,
        freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference=value.configuration_version,
        source_provenance_fingerprint=manifest_fingerprint(
            strategy_id=value.strategy_version.strategy_id,
            strategy_version=value.strategy_version.version,
            registry_version=value.registry_version,
            configuration_version=value.configuration_version,
            diagnostic_ids=diagnostic_ids,
            evidence_ids=evidence_ids,
        ),
        historical_integrity_reference=None,
        invalidation_domain=IntelligenceInvalidationDomain.POLICY,
        warnings=tuple(sorted(warnings)),
    )


def decision_scorecard_artifact_fingerprint(value: StoredDecisionScorecard) -> str:
    """Canonical bounded identity of an already-stored scorecard."""
    components = tuple(sorted(value.components, key=lambda item: item.component_id))
    return manifest_fingerprint(
        scorecard_id=value.id,
        instrument_id=value.instrument_id,
        strategy_id=value.strategy_version.strategy_id,
        strategy_version=value.strategy_version.version,
        registry_version=value.registry_version,
        configuration_version=value.configuration_version,
        as_of_timestamp=value.as_of_timestamp,
        evaluated_at=value.evaluated_at,
        final_score=value.final_score,
        score_status=value.score_status,
        data_confidence=value.data_confidence,
        components=tuple(
            (
                item.component_id, item.status, item.score, item.weight,
                item.weighted_contribution, item.available_rules,
                item.missing_rules, item.diagnostic_ids, item.evidence_ids,
                item.confidence, item.contradictions,
            )
            for item in components
        ),
        warnings=tuple(sorted(value.warnings)),
    )


def _unavailable(canonical_instrument_id: str, warning: str) -> StoredIntelligenceArtifact:
    return StoredIntelligenceArtifact(
        canonical_instrument_id=canonical_instrument_id,
        domain=IntelligenceEvidenceDomain.DECISION_SCORE,
        artifact_id="decision-score:unavailable",
        artifact_fingerprint=manifest_fingerprint(
            domain=IntelligenceEvidenceDomain.DECISION_SCORE.value, warning=warning,
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


def _eligible(value: StoredDecisionScorecard, canonical_instrument_id: str, as_of: datetime) -> bool:
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
    "DecisionScoreEvidenceAdapter", "DecisionScoreEvidenceStoredSource", "decision_scorecard_artifact_fingerprint",
    "StoredDecisionScorecard", "StoredDecisionScorecardSource", "StrategyGovernanceDecisionScorecardSource",
)
