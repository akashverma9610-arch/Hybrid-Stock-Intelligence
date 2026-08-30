"""Strategy-agnostic immutable intake artifacts for the shared Brain.

The handoff is lineage for a future canonical research consumer.  It is not a
queue, a permanent intelligence snapshot, a score, or an instruction to run
research automatically.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class BrainResearchOriginType(StrEnum):
    PRE_BREAKOUT_OPPORTUNITY = "PRE_BREAKOUT_OPPORTUNITY"
    UNIVERSE_OPPORTUNITY = "UNIVERSE_OPPORTUNITY"
    MANUAL_DEEP_ANALYSIS = "MANUAL_DEEP_ANALYSIS"
    PORTFOLIO_HOLDING_REVIEW = "PORTFOLIO_HOLDING_REVIEW"
    SELL_EXIT_WATCH = "SELL_EXIT_WATCH"
    ROTATION_CHALLENGER = "ROTATION_CHALLENGER"
    CATALYST_REANALYSIS = "CATALYST_REANALYSIS"


class BrainResearchStage(StrEnum):
    RESEARCH_DIAGNOSTIC = "RESEARCH_DIAGNOSTIC"


class BrainResearchHandoffStatus(StrEnum):
    PENDING_RESEARCH = "PENDING_RESEARCH"


class BrainResearchHandoffError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BrainResearchHandoff:
    """A pure immutable request for a later shared-Brain consumer."""

    handoff_id: str
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
    sector: str | None
    setup_family: str | None
    horizon: str | None
    reference_facts: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.handoff_id, self.canonical_instrument_id, self.origin_artifact_id, self.origin_artifact_fingerprint)):
            raise BrainResearchHandoffError("BRAIN_RESEARCH_HANDOFF_REQUIRED_FIELD")
        if self.requested_brain_stage is not BrainResearchStage.RESEARCH_DIAGNOSTIC:
            raise BrainResearchHandoffError("BRAIN_RESEARCH_HANDOFF_STAGE_INVALID")
        if self.research_status is not BrainResearchHandoffStatus.PENDING_RESEARCH:
            raise BrainResearchHandoffError("BRAIN_RESEARCH_HANDOFF_STATUS_INVALID")
        if self.fingerprint != brain_research_handoff_fingerprint(self):
            raise BrainResearchHandoffError("BRAIN_RESEARCH_HANDOFF_FINGERPRINT_MISMATCH")


def create_brain_research_handoff(
    *,
    canonical_instrument_id: str,
    origin_type: BrainResearchOriginType,
    origin_artifact_id: str,
    origin_artifact_fingerprint: str,
    evaluation_as_of: datetime,
    evaluation_session: datetime | None,
    created_from_governed_artifact: bool,
    origin_lineage: tuple[tuple[str, str], ...] = (),
    sector: str | None = None,
    setup_family: str | None = None,
    horizon: str | None = None,
    reference_facts: tuple[tuple[str, str], ...] = (),
    warnings: tuple[str, ...] = (),
) -> BrainResearchHandoff:
    """Construct deterministic lineage only; this never invokes the Brain."""
    values = dict(
        canonical_instrument_id=canonical_instrument_id,
        origin_type=origin_type,
        origin_artifact_id=origin_artifact_id,
        origin_artifact_fingerprint=origin_artifact_fingerprint,
        evaluation_as_of=evaluation_as_of,
        evaluation_session=evaluation_session,
        requested_brain_stage=BrainResearchStage.RESEARCH_DIAGNOSTIC,
        research_status=BrainResearchHandoffStatus.PENDING_RESEARCH,
        created_from_governed_artifact=created_from_governed_artifact,
        origin_lineage=tuple(sorted(set(origin_lineage))),
        sector=sector,
        setup_family=setup_family,
        horizon=horizon,
        reference_facts=tuple(sorted(set(reference_facts))),
        warnings=tuple(sorted(set(warnings))),
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["handoff_id"] = f"brain-research-handoff-{seed[:24]}"
    return BrainResearchHandoff(**values, fingerprint=brain_research_handoff_fingerprint_values(values))


def brain_research_handoff_fingerprint(value: BrainResearchHandoff) -> str:
    return brain_research_handoff_fingerprint_values({
        field: getattr(value, field)
        for field in value.__dataclass_fields__
        if field != "fingerprint"
    })


def brain_research_handoff_fingerprint_values(value: dict) -> str:
    return manifest_fingerprint(**_semantic_values({
        field: item for field, item in value.items() if field != "fingerprint"
    }))


def _semantic_values(values: dict) -> dict:
    return {field: _semantic_value(value) for field, value in sorted(values.items())}


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    return value
