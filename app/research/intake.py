"""Derived, strategy-agnostic read/intake boundary for the shared Brain.

``BrainResearchIntake`` is a validated request/context artifact.  It is not a
ResearchSnapshot, diagnostic result, score, queue item, or a future Unified
Continuous Intelligence State projection.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.research.handoff import (
    BrainResearchHandoff,
    BrainResearchHandoffError,
    BrainResearchHandoffStatus,
    BrainResearchOriginType,
    BrainResearchStage,
)
from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.governance_repository import StrategyGovernanceRepository


class BrainResearchIntakeError(ValueError):
    pass


class BrainResearchIntakeContextKind(StrEnum):
    """Explicitly labels bounded origin facts as context, not research evidence."""

    ORIGIN_CONTEXT = "ORIGIN_CONTEXT"


@dataclass(frozen=True, slots=True)
class BrainResearchIntake:
    """Immutable, derived context for a later shared-Brain research execution."""

    intake_id: str
    handoff_id: str
    handoff_fingerprint: str
    canonical_instrument_id: str
    origin_type: BrainResearchOriginType
    origin_artifact_id: str
    origin_artifact_fingerprint: str
    evaluation_as_of: datetime
    evaluation_session: datetime | None
    requested_brain_stage: BrainResearchStage
    research_status: BrainResearchHandoffStatus
    created_from_governed_artifact: bool
    origin_lineage: tuple[tuple[str, str], ...]
    context_kind: BrainResearchIntakeContextKind
    origin_context: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.intake_id, self.handoff_id, self.handoff_fingerprint, self.canonical_instrument_id)):
            raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_REQUIRED_FIELD")
        if self.requested_brain_stage is not BrainResearchStage.RESEARCH_DIAGNOSTIC:
            raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_STAGE_INVALID")
        if self.research_status is not BrainResearchHandoffStatus.PENDING_RESEARCH:
            raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_STATUS_UNSUPPORTED")
        if self.context_kind is not BrainResearchIntakeContextKind.ORIGIN_CONTEXT:
            raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_CONTEXT_INVALID")
        if self.fingerprint != brain_research_intake_fingerprint(self):
            raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_FINGERPRINT_MISMATCH")


def create_brain_research_intake(handoff: BrainResearchHandoff) -> BrainResearchIntake:
    """Derive one deterministic request from one audit-valid persisted handoff."""
    if not isinstance(handoff, BrainResearchHandoff):
        raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_HANDOFF_REQUIRED")
    try:
        # Re-run the domain integrity check; derived intake never trusts a mutable object.
        BrainResearchHandoff(**{field: getattr(handoff, field) for field in handoff.__dataclass_fields__})
    except BrainResearchHandoffError as error:
        raise BrainResearchIntakeError(str(error)) from error
    if handoff.research_status is not BrainResearchHandoffStatus.PENDING_RESEARCH:
        raise BrainResearchIntakeError("BRAIN_RESEARCH_INTAKE_STATUS_UNSUPPORTED")
    context = _origin_context(handoff)
    seed = manifest_fingerprint(
        handoff_id=handoff.handoff_id,
        handoff_fingerprint=handoff.fingerprint,
        canonical_instrument_id=handoff.canonical_instrument_id,
        requested_brain_stage=handoff.requested_brain_stage.value,
    )
    values = dict(
        intake_id=f"brain-research-intake-{seed[:24]}",
        handoff_id=handoff.handoff_id,
        handoff_fingerprint=handoff.fingerprint,
        canonical_instrument_id=handoff.canonical_instrument_id,
        origin_type=handoff.origin_type,
        origin_artifact_id=handoff.origin_artifact_id,
        origin_artifact_fingerprint=handoff.origin_artifact_fingerprint,
        evaluation_as_of=handoff.evaluation_as_of,
        evaluation_session=handoff.evaluation_session,
        requested_brain_stage=handoff.requested_brain_stage,
        research_status=handoff.research_status,
        created_from_governed_artifact=handoff.created_from_governed_artifact,
        origin_lineage=handoff.origin_lineage,
        context_kind=BrainResearchIntakeContextKind.ORIGIN_CONTEXT,
        origin_context=context,
    )
    return BrainResearchIntake(**values, fingerprint=brain_research_intake_fingerprint_values(values))


def brain_research_intake_fingerprint(value: BrainResearchIntake) -> str:
    return brain_research_intake_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_research_intake_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**{
        field: _semantic_value(value) for field, value in sorted(values.items()) if field != "fingerprint"
    })


class BrainResearchIntakeService:
    """Read one handoff, audit it, and derive context without consuming or executing it."""

    def __init__(
        self,
        repository: StrategyGovernanceRepository,
        *,
        audit_service: AuditReconstructionService | None = None,
    ) -> None:
        self._repository = repository
        self._audit = audit_service or AuditReconstructionService(repository)

    def get_research_intake(self, handoff_id: str) -> BrainResearchIntake | None:
        """Return a deterministic intake for one persisted pending handoff only."""
        if self._repository.get_brain_research_handoff(handoff_id) is None:
            return None
        handoff = self._audit.reconstruct_brain_research_handoff(handoff_id)
        return create_brain_research_intake(handoff)


def _origin_context(handoff: BrainResearchHandoff) -> tuple[tuple[str, str], ...]:
    values = list(handoff.reference_facts)
    for key, value in (
        ("sector", handoff.sector),
        ("setup_family", handoff.setup_family),
        ("horizon", handoff.horizon),
    ):
        if value is not None:
            values.append((key, value))
    return tuple(sorted(set(values)))


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    return value
