"""Stored-only projection of durable governed Pre-Breakout setup evidence."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.domain.models import FreshnessStatus
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStoredSource
from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessment


# The candidate and handoff are deterministic derivatives of this durable evidence.
CANDIDATE_PERSISTENCE_REQUIRED = False


class GovernedSetupAssessmentReadRepository(Protocol):
    def list_prebreakout_setup_assessments(
        self, canonical_instrument_id: str | None = None, policy_fingerprint: str | None = None,
    ) -> tuple[GovernedPreBreakoutSetupAssessment, ...]: ...


class GovernedSetupEvidenceStoredSource:
    """Reads persisted assessment evidence only; it never invokes setup materialization."""

    def __init__(self, repository: GovernedSetupAssessmentReadRepository) -> None:
        self._repository = repository

    def list_stored_intelligence_artifacts(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> tuple[StoredIntelligenceArtifact, ...]:
        assessments = tuple(item for item in self._repository.list_prebreakout_setup_assessments(
            canonical_instrument_id=canonical_instrument_id,
        ) if item.evaluation_as_of <= as_of)
        if not assessments:
            return ()
        value = max(assessments, key=lambda item: (item.evaluation_as_of, item.assessment_id))
        artifact = StoredIntelligenceArtifact(
            canonical_instrument_id=value.instrument_id,
            domain=IntelligenceEvidenceDomain.TECHNICAL,
            artifact_id=value.assessment_id,
            artifact_fingerprint=value.fingerprint,
            availability=IntelligenceEvidenceAvailability.AVAILABLE,
            evidence_as_of=value.evaluation_as_of,
            observed_at=value.evaluation_session,
            available_at=value.evaluation_as_of,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=value.policy_fingerprint,
            source_provenance_fingerprint=value.selection_fingerprint,
            historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.POLICY,
            warnings=tuple(sorted({value.status.value, *value.warnings})),
        )
        if not value.candidate_formation_eligible:
            return (artifact,)
        opportunity = StoredIntelligenceArtifact(
            canonical_instrument_id=value.instrument_id,
            domain=IntelligenceEvidenceDomain.SETUP_OPPORTUNITY,
            artifact_id=f"candidate-reconstructible:{value.assessment_id}",
            artifact_fingerprint=value.fingerprint,
            availability=IntelligenceEvidenceAvailability.PARTIAL,
            evidence_as_of=value.evaluation_as_of,
            observed_at=value.evaluation_session,
            available_at=value.evaluation_as_of,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=value.policy_fingerprint,
            source_provenance_fingerprint=value.selection_fingerprint,
            historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.POLICY,
            warnings=("CANDIDATE_RECONSTRUCTIBLE_NOT_PERSISTED",),
        )
        return (artifact, opportunity)
