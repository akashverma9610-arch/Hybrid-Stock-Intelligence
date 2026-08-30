"""Pure, immutable Pre-Breakout opportunity-candidate assembly.

Candidate formation consumes an already governed setup assessment.  It never
queries evidence, reruns setup logic, assigns a score, or creates an execution
artifact.  Shared-Brain research handoff remains a later explicit boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.strategies.common.models import CandidateStatus, StrategyFamily
from app.strategies.pre_breakout.materialization import PreBreakoutStructuralStatus
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment,
    PreBreakoutSetupAssessmentStatus,
    prebreakout_setup_assessment_fingerprint as _setup_assessment_fingerprint,
)


class PreBreakoutCandidateRole(StrEnum):
    OPPORTUNITY_CANDIDATE = "OPPORTUNITY_CANDIDATE"


class PreBreakoutCandidateResearchStatus(StrEnum):
    RESEARCH_PENDING = "RESEARCH_PENDING"


class PreBreakoutCandidateAssemblyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreBreakoutCandidate:
    """A governed opportunity for later shared-Brain research, never a trade."""

    candidate_id: str
    candidate_role: PreBreakoutCandidateRole
    strategy_family: StrategyFamily
    candidate_status: CandidateStatus
    research_status: PreBreakoutCandidateResearchStatus
    brain_evaluation_required: bool
    assessment_fingerprint: str
    instrument_id: str
    evaluation_as_of: datetime
    evaluation_session: datetime
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    selection_id: str
    selection_fingerprint: str
    sector: str
    sector_rotation_as_of: datetime
    top3_sector_membership: bool
    bbw_percentile: Decimal
    bbw_pass: bool
    current_atr14: Decimal
    atr_contraction_pass: bool
    current_volume: int
    volume_dry_up_pass: bool
    official_delivery_pct: Decimal
    delivery_pass: bool
    high_252: Decimal
    distance_below_high_pct: Decimal
    distance_from_high_pass: bool
    rsi14: Decimal
    rsi_pass: bool
    base_start: datetime
    base_end: datetime
    base_duration: int
    base_top: Decimal
    resistance: Decimal
    breakout_confirmation_trigger: Decimal
    structural_support: Decimal
    final_structural_stop: Decimal
    measured_move_target: Decimal
    tick_record_id: str
    tick_size: Decimal
    entry_reference_price: Decimal
    maximum_acceptable_entry_price: Decimal
    maximum_executable_entry_price: Decimal
    reference_reward_risk: Decimal
    actual_execution_price: Decimal | None
    actual_execution_status: str
    formation_blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.assessment_fingerprint:
            raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_REQUIRED_FIELD")
        if self.candidate_role is not PreBreakoutCandidateRole.OPPORTUNITY_CANDIDATE:
            raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_ROLE_INVALID")
        if self.candidate_status is not CandidateStatus.CANDIDATE_GENERATED:
            raise PreBreakoutCandidateAssemblyError("PRE_BREAK_OUT_CANDIDATE_STATUS_INVALID")
        if self.research_status is not PreBreakoutCandidateResearchStatus.RESEARCH_PENDING or not self.brain_evaluation_required:
            raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_RESEARCH_BOUNDARY_INVALID")
        if self.formation_blockers:
            raise PreBreakoutCandidateAssemblyError("PRE_BREAK_OUT_CANDIDATE_BLOCKERS_PRESENT")
        if self.actual_execution_price is not None or self.actual_execution_status != "NOT_EVALUATED_AT_SCAN":
            raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_EXECUTION_BOUNDARY_INVALID")
        if self.fingerprint != prebreakout_candidate_fingerprint(self):
            raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_FINGERPRINT_MISMATCH")


def assemble_prebreakout_candidate(
    assessment: GovernedPreBreakoutSetupAssessment,
) -> PreBreakoutCandidate:
    """Form exactly one immutable candidate from one already eligible assessment."""
    if not isinstance(assessment, GovernedPreBreakoutSetupAssessment):
        raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_ASSESSMENT_REQUIRED")
    if (
        not assessment.candidate_formation_eligible
        or assessment.status is not PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE
        or assessment.blockers
    ):
        raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_NOT_ELIGIBLE")
    technical, structural = assessment.technical_inputs, assessment.structural
    if (
        structural.status is not PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY
        or structural.actual_execution_price is not None
        or structural.actual_execution_status != "NOT_EVALUATED_AT_SCAN"
    ):
        raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_ASSESSMENT_INCONSISTENT")
    required = (
        assessment.evaluation_session, assessment.policy_id, assessment.policy_version,
        assessment.policy_fingerprint, assessment.selection_id, assessment.selection_fingerprint,
        assessment.sector, assessment.sector_rotation_as_of, technical.bbw_percentile,
        technical.current_atr14, technical.current_volume, technical.official_delivery_pct,
        technical.high_252, technical.distance_below_high_pct, technical.rsi14,
        structural.selected_base, structural.resistance, structural.breakout_confirmation_trigger,
        structural.structural_support, structural.final_stop, structural.target, structural.tick_record_id,
        structural.tick_size, structural.entry_reference_price, structural.maximum_acceptable_entry_price,
        structural.maximum_executable_entry_price, structural.entry_reference_rr,
    )
    if any(value is None for value in required) or assessment.top3_sector_membership is not True:
        raise PreBreakoutCandidateAssemblyError("PRE_BREAKOUT_CANDIDATE_ASSESSMENT_INCONSISTENT")
    assessment_fingerprint = prebreakout_setup_assessment_fingerprint(assessment)
    candidate_id = f"prebreakout-candidate-{assessment_fingerprint[:24]}"
    values = dict(
        candidate_id=candidate_id,
        candidate_role=PreBreakoutCandidateRole.OPPORTUNITY_CANDIDATE,
        strategy_family=StrategyFamily.PRE_BREAKOUT,
        candidate_status=CandidateStatus.CANDIDATE_GENERATED,
        research_status=PreBreakoutCandidateResearchStatus.RESEARCH_PENDING,
        brain_evaluation_required=True,
        assessment_fingerprint=assessment_fingerprint,
        instrument_id=assessment.instrument_id,
        evaluation_as_of=assessment.evaluation_as_of,
        evaluation_session=assessment.evaluation_session,
        policy_id=assessment.policy_id,
        policy_version=assessment.policy_version,
        policy_fingerprint=assessment.policy_fingerprint,
        selection_id=assessment.selection_id,
        selection_fingerprint=assessment.selection_fingerprint,
        sector=assessment.sector,
        sector_rotation_as_of=assessment.sector_rotation_as_of,
        top3_sector_membership=assessment.top3_sector_membership,
        bbw_percentile=technical.bbw_percentile,
        bbw_pass=technical.bbw_pass,
        current_atr14=technical.current_atr14,
        atr_contraction_pass=technical.atr_contraction_pass,
        current_volume=technical.current_volume,
        volume_dry_up_pass=technical.volume_dry_up_pass,
        official_delivery_pct=technical.official_delivery_pct,
        delivery_pass=technical.delivery_pass,
        high_252=technical.high_252,
        distance_below_high_pct=technical.distance_below_high_pct,
        distance_from_high_pass=technical.distance_from_high_pass,
        rsi14=technical.rsi14,
        rsi_pass=technical.rsi_pass,
        base_start=structural.selected_base.start,
        base_end=structural.selected_base.end,
        base_duration=structural.selected_base.duration,
        base_top=structural.selected_base.base_top,
        resistance=structural.resistance,
        breakout_confirmation_trigger=structural.breakout_confirmation_trigger,
        structural_support=structural.structural_support,
        final_structural_stop=structural.final_stop,
        measured_move_target=structural.target,
        tick_record_id=structural.tick_record_id,
        tick_size=structural.tick_size,
        entry_reference_price=structural.entry_reference_price,
        maximum_acceptable_entry_price=structural.maximum_acceptable_entry_price,
        maximum_executable_entry_price=structural.maximum_executable_entry_price,
        reference_reward_risk=structural.entry_reference_rr,
        actual_execution_price=None,
        actual_execution_status=structural.actual_execution_status,
        formation_blockers=(),
        warnings=tuple(sorted(set(assessment.warnings))),
    )
    return PreBreakoutCandidate(**values, fingerprint=prebreakout_candidate_fingerprint_values(values))


def prebreakout_setup_assessment_fingerprint(value: GovernedPreBreakoutSetupAssessment) -> str:
    """Compatibility facade for the assessment's canonical full semantic fingerprint."""
    return _setup_assessment_fingerprint(value)


def prebreakout_candidate_fingerprint(value: PreBreakoutCandidate) -> str:
    return prebreakout_candidate_fingerprint_values({
        name: getattr(value, name)
        for name in value.__dataclass_fields__
        if name != "fingerprint"
    })


def prebreakout_candidate_fingerprint_values(value: dict) -> str:
    """Fingerprint every candidate-semantic field except the stored fingerprint."""
    return manifest_fingerprint(**{
        name: _semantic_value(item)
        for name, item in sorted(value.items())
        if name != "fingerprint"
    })


def _base_tuple(value) -> tuple[object, ...] | None:
    if value is None:
        return None
    return (value.start.isoformat(), value.end.isoformat(), value.duration, value.base_top)


def _timestamp(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    return value
