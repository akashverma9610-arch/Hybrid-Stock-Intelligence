"""Pure adapter from governed Pre-Breakout opportunity to shared Brain intake."""
from __future__ import annotations

from app.strategies.common.models import CandidateStatus
from app.strategies.pre_breakout.candidate_assembly import (
    PreBreakoutCandidate,
    PreBreakoutCandidateAssemblyError,
    PreBreakoutCandidateResearchStatus,
    PreBreakoutCandidateRole,
    prebreakout_candidate_fingerprint,
)
from app.research.handoff import (
    BrainResearchHandoff,
    BrainResearchOriginType,
    create_brain_research_handoff,
)


def candidate_to_brain_research_handoff(candidate: PreBreakoutCandidate) -> BrainResearchHandoff:
    """Adapt one valid opportunity artifact without recalculation or execution."""
    if not isinstance(candidate, PreBreakoutCandidate):
        raise PreBreakoutCandidateAssemblyError("BRAIN_RESEARCH_HANDOFF_CANDIDATE_REQUIRED")
    if candidate.fingerprint != prebreakout_candidate_fingerprint(candidate):
        raise PreBreakoutCandidateAssemblyError("BRAIN_RESEARCH_HANDOFF_CANDIDATE_FINGERPRINT_MISMATCH")
    if (
        candidate.candidate_role is not PreBreakoutCandidateRole.OPPORTUNITY_CANDIDATE
        or candidate.candidate_status is not CandidateStatus.CANDIDATE_GENERATED
        or candidate.research_status is not PreBreakoutCandidateResearchStatus.RESEARCH_PENDING
        or not candidate.brain_evaluation_required
        or candidate.formation_blockers
        or candidate.actual_execution_price is not None
        or candidate.actual_execution_status != "NOT_EVALUATED_AT_SCAN"
    ):
        raise PreBreakoutCandidateAssemblyError("BRAIN_RESEARCH_HANDOFF_CANDIDATE_INCONSISTENT")
    return create_brain_research_handoff(
        canonical_instrument_id=candidate.instrument_id,
        origin_type=BrainResearchOriginType.PRE_BREAKOUT_OPPORTUNITY,
        origin_artifact_id=candidate.candidate_id,
        origin_artifact_fingerprint=candidate.fingerprint,
        evaluation_as_of=candidate.evaluation_as_of,
        evaluation_session=candidate.evaluation_session,
        created_from_governed_artifact=True,
        origin_lineage=(
            ("assessment_fingerprint", candidate.assessment_fingerprint),
            ("candidate_id", candidate.candidate_id),
            ("candidate_fingerprint", candidate.fingerprint),
            ("policy_fingerprint", candidate.policy_fingerprint),
            ("selection_id", candidate.selection_id),
            ("selection_fingerprint", candidate.selection_fingerprint),
        ),
        sector=candidate.sector,
        setup_family=candidate.strategy_family.value,
        horizon="PRE_BREAKOUT",
        reference_facts=(
            ("breakout_confirmation_trigger", str(candidate.breakout_confirmation_trigger)),
            ("entry_reference_price", str(candidate.entry_reference_price)),
            ("final_structural_stop", str(candidate.final_structural_stop)),
            ("maximum_executable_entry_price", str(candidate.maximum_executable_entry_price)),
            ("measured_move_target", str(candidate.measured_move_target)),
            ("reference_reward_risk", str(candidate.reference_reward_risk)),
        ),
        warnings=candidate.warnings,
    )


def validate_prebreakout_handoff_origin(
    handoff: BrainResearchHandoff,
    candidate: PreBreakoutCandidate,
) -> BrainResearchHandoff:
    """Reconstruct exact candidate-origin lineage without rerunning any assessment."""
    if handoff.origin_type is not BrainResearchOriginType.PRE_BREAKOUT_OPPORTUNITY:
        raise PreBreakoutCandidateAssemblyError("BRAIN_RESEARCH_HANDOFF_ORIGIN_TYPE_INVALID")
    reconstructed = candidate_to_brain_research_handoff(candidate)
    if reconstructed != handoff:
        raise PreBreakoutCandidateAssemblyError("BRAIN_RESEARCH_HANDOFF_ORIGIN_RECONSTRUCTION_MISMATCH")
    return reconstructed
