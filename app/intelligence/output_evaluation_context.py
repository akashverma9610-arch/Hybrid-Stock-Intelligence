"""Pure validation contract for attaching contextual gate lineage downstream.

This module validates only immutable, already-computed references.  It does
not calculate a score, execute gates, decide an action, or persist anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.brain_output_requirement_policy import (
    BrainOutputContextRequirement,
    BrainOutputRequirementPolicy,
    CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY,
)
from app.historical.guard import manifest_fingerprint
from app.intelligence.decision_score_evidence import (
    StoredDecisionScorecard,
    decision_scorecard_artifact_fingerprint,
)
from app.intelligence.six_gates_evidence import (
    StoredSixGatesEvaluation,
    six_gates_evaluation_artifact_fingerprint,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    BrainOutputRequest,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    PortfolioContextRef,
    UnifiedIntelligenceState,
)


class OutputEvaluationMatchStatus(StrEnum):
    MATCHED = "MATCHED"
    NOT_REQUIRED = "NOT_REQUIRED"
    MISSING = "MISSING"
    MISMATCH = "MISMATCH"
    FUTURE = "FUTURE"
    UNDEFINED = "UNDEFINED"


class OutputEvaluationBlocker(StrEnum):
    STATE_MISMATCH = "STATE_MISMATCH"
    INSTRUMENT_MISMATCH = "INSTRUMENT_MISMATCH"
    FUTURE_ARTIFACT = "FUTURE_ARTIFACT"
    SCORECARD_MISMATCH = "SCORECARD_MISMATCH"
    GATE_CONTEXT_MISMATCH = "GATE_CONTEXT_MISMATCH"
    PORTFOLIO_CONTEXT_MISMATCH = "PORTFOLIO_CONTEXT_MISMATCH"
    GATE_CONFIG_MISMATCH = "GATE_CONFIG_MISMATCH"
    REQUIRED_GATE_MISSING = "REQUIRED_GATE_MISSING"
    REQUIRED_SCORE_MISSING = "REQUIRED_SCORE_MISSING"
    REQUIRED_PORTFOLIO_CONTEXT_MISSING = "REQUIRED_PORTFOLIO_CONTEXT_MISSING"
    OUTPUT_CONTEXT_REQUIREMENT_UNDEFINED = "OUTPUT_CONTEXT_REQUIREMENT_UNDEFINED"


OutputContextRequirement = BrainOutputContextRequirement
OUTPUT_CONTEXT_REQUIREMENTS = CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY.requirements


@dataclass(frozen=True, slots=True)
class BrainOutputEvaluationContext:
    """Validated inputs for a future output decision; it contains no decision."""

    evaluation_context_id: str
    canonical_instrument_id: str
    requested_as_of: datetime
    output_context: BrainOutputContext
    requirement_policy_id: str
    requirement_policy_version: str
    requirement_policy_fingerprint: str
    unified_state_id: str
    unified_state_fingerprint: str
    state_completeness: IntelligenceStateCompleteness
    evidence_references: tuple[IntelligenceEvidenceReference, ...]
    state_blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    state_degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    state_origin_lineage: tuple[tuple[str, str], ...]
    portfolio_context_ref: PortfolioContextRef | None
    decision_scorecard_id: str | None
    decision_scorecard_fingerprint: str | None
    execution_gate_evaluation_id: str | None
    execution_gate_evaluation_fingerprint: str | None
    requirement_status: OutputEvaluationMatchStatus
    state_match_status: OutputEvaluationMatchStatus
    score_lineage_match_status: OutputEvaluationMatchStatus
    gate_context_match_status: OutputEvaluationMatchStatus
    portfolio_context_match_status: OutputEvaluationMatchStatus
    temporal_match_status: OutputEvaluationMatchStatus
    ready_for_output_decision: bool
    blockers: tuple[OutputEvaluationBlocker, ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((
            self.evaluation_context_id, self.canonical_instrument_id, self.unified_state_id,
            self.unified_state_fingerprint, self.requirement_policy_id,
            self.requirement_policy_version, self.requirement_policy_fingerprint,
        )):
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_REQUIRED_FIELD")
        if self.requested_as_of.tzinfo is None or self.requested_as_of.utcoffset() is None:
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_TIMEZONE_REQUIRED")
        if tuple(value.domain for value in self.evidence_references) != tuple(
            sorted((value.domain for value in self.evidence_references), key=lambda value: value.value)
        ):
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_EVIDENCE_NONCANONICAL")
        if self.blockers != tuple(sorted(set(self.blockers), key=lambda value: value.value)):
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_BLOCKERS_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_WARNINGS_NONCANONICAL")
        if self.fingerprint != brain_output_evaluation_context_fingerprint(self):
            raise ValueError("BRAIN_OUTPUT_EVALUATION_CONTEXT_FINGERPRINT_MISMATCH")


def output_context_requirement(context: BrainOutputContext) -> BrainOutputContextRequirement:
    """Compatibility read for the current governed policy."""
    return CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY.requirement_for(context)


def create_brain_output_evaluation_context(
    state: UnifiedIntelligenceState,
    request: BrainOutputRequest,
    *,
    decision_scorecard: StoredDecisionScorecard | None = None,
    gate_evaluation: StoredSixGatesEvaluation | None = None,
    requirement_policy: BrainOutputRequirementPolicy = CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY,
) -> BrainOutputEvaluationContext:
    """Fail-closed attachment validation over supplied immutable artifacts."""
    requirement = requirement_policy.requirement_for(request.output_context)
    blockers: set[OutputEvaluationBlocker] = set()
    warnings: set[str] = set()
    state_status = _state_status(state, request, blockers)
    temporal_status = _temporal_status(
        state,
        request,
        decision_scorecard if requirement.requires_decision_score else None,
        gate_evaluation if requirement.requires_six_gates else None,
        blockers,
    )
    score_status, score_id, score_fingerprint = _score_status(
        state, request, decision_scorecard, requirement, blockers,
    )
    gate_status, gate_id, gate_fingerprint = _gate_status(
        state, request, gate_evaluation, requirement, blockers,
    )
    portfolio_status = _portfolio_status(
        request.portfolio_context,
        gate_evaluation if requirement.requires_six_gates else None,
        requirement,
        blockers,
        warnings,
    )
    ready = not blockers
    values = dict(
        canonical_instrument_id=state.canonical_instrument_id,
        requested_as_of=request.requested_as_of,
        output_context=request.output_context,
        requirement_policy_id=requirement_policy.policy_id,
        requirement_policy_version=requirement_policy.version,
        requirement_policy_fingerprint=requirement_policy.fingerprint,
        unified_state_id=state.state_id,
        unified_state_fingerprint=state.fingerprint,
        state_completeness=state.completeness,
        evidence_references=state.evidence_references,
        state_blocking_domains=state.blocking_domains,
        state_degraded_domains=state.degraded_domains,
        state_origin_lineage=state.origin_lineage,
        portfolio_context_ref=request.portfolio_context,
        decision_scorecard_id=score_id,
        decision_scorecard_fingerprint=score_fingerprint,
        execution_gate_evaluation_id=gate_id,
        execution_gate_evaluation_fingerprint=gate_fingerprint,
        requirement_status=OutputEvaluationMatchStatus.MATCHED,
        state_match_status=state_status,
        score_lineage_match_status=score_status,
        gate_context_match_status=gate_status,
        portfolio_context_match_status=portfolio_status,
        temporal_match_status=temporal_status,
        ready_for_output_decision=ready,
        blockers=tuple(sorted(blockers, key=lambda value: value.value)),
        warnings=tuple(sorted(warnings)),
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["evaluation_context_id"] = f"brain-output-evaluation-context-{seed[:24]}"
    return BrainOutputEvaluationContext(**values, fingerprint=brain_output_evaluation_context_fingerprint_values(values))


def brain_output_evaluation_context_fingerprint(value: BrainOutputEvaluationContext) -> str:
    return brain_output_evaluation_context_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_output_evaluation_context_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({key: value for key, value in values.items() if key != "fingerprint"}))


def _state_status(state, request, blockers) -> OutputEvaluationMatchStatus:
    if (
        request.canonical_instrument_id != state.canonical_instrument_id
        or request.intelligence_state_id != state.state_id
        or request.intelligence_state_fingerprint != state.fingerprint
    ):
        blockers.add(OutputEvaluationBlocker.STATE_MISMATCH)
        if request.canonical_instrument_id != state.canonical_instrument_id:
            blockers.add(OutputEvaluationBlocker.INSTRUMENT_MISMATCH)
        return OutputEvaluationMatchStatus.MISMATCH
    return OutputEvaluationMatchStatus.MATCHED


def _temporal_status(state, request, score, gate, blockers) -> OutputEvaluationMatchStatus:
    timestamps = (state.as_of, *(value for artifact in (score, gate) if artifact is not None for value in (artifact.as_of_timestamp, artifact.evaluated_at)))
    if any(not _aware(value) or value > request.requested_as_of for value in timestamps):
        blockers.add(OutputEvaluationBlocker.FUTURE_ARTIFACT)
        return OutputEvaluationMatchStatus.FUTURE
    return OutputEvaluationMatchStatus.MATCHED


def _score_status(state, request, score, requirement, blockers):
    if not requirement.requires_decision_score:
        # Informational/review contexts do not attach irrelevant score lineage.
        return OutputEvaluationMatchStatus.NOT_REQUIRED, None, None
    if score is None:
        if requirement.requires_decision_score:
            blockers.add(OutputEvaluationBlocker.REQUIRED_SCORE_MISSING)
            return OutputEvaluationMatchStatus.MISSING, None, None
        return OutputEvaluationMatchStatus.NOT_REQUIRED, None, None
    fingerprint = decision_scorecard_artifact_fingerprint(score)
    reference = _reference(state, IntelligenceEvidenceDomain.DECISION_SCORE)
    matched = (
        score.instrument_id == state.canonical_instrument_id == request.canonical_instrument_id
        and reference is not None and score.id in reference.artifact_ids
        and fingerprint in reference.artifact_fingerprints
    )
    if not matched:
        blockers.add(OutputEvaluationBlocker.SCORECARD_MISMATCH)
        if score.instrument_id != state.canonical_instrument_id:
            blockers.add(OutputEvaluationBlocker.INSTRUMENT_MISMATCH)
        return OutputEvaluationMatchStatus.MISMATCH, score.id, fingerprint
    return OutputEvaluationMatchStatus.MATCHED, score.id, fingerprint


def _gate_status(state, request, gate, requirement, blockers):
    if not requirement.requires_six_gates:
        # Irrelevant gate lineage is deliberately not validated, attached, or
        # fingerprinted for informational/review contexts.
        return OutputEvaluationMatchStatus.NOT_REQUIRED, None, None
    if gate is None:
        blockers.add(OutputEvaluationBlocker.REQUIRED_GATE_MISSING)
        return OutputEvaluationMatchStatus.MISSING, None, None
    fingerprint = six_gates_evaluation_artifact_fingerprint(gate)
    reference = _reference(state, IntelligenceEvidenceDomain.SIX_GATES)
    lineage_matches = (
        gate.instrument_id == state.canonical_instrument_id == request.canonical_instrument_id
        and reference is not None and gate.id in reference.artifact_ids
        and fingerprint in reference.artifact_fingerprints
        and reference.freshness_policy_reference == gate.gate_configuration_version
    )
    action_matches = (
        requirement.required_action_context is not None
        and _enum_value(gate.action_context) == requirement.required_action_context.value
    )
    if not lineage_matches:
        blockers.add(OutputEvaluationBlocker.GATE_CONFIG_MISMATCH)
        if gate.instrument_id != state.canonical_instrument_id:
            blockers.add(OutputEvaluationBlocker.INSTRUMENT_MISMATCH)
    if not action_matches:
        blockers.add(OutputEvaluationBlocker.GATE_CONTEXT_MISMATCH)
    return (OutputEvaluationMatchStatus.MATCHED if lineage_matches and action_matches else OutputEvaluationMatchStatus.MISMATCH), gate.id, fingerprint


def _portfolio_status(portfolio, gate, requirement, blockers, warnings):
    # Entry Setup is generally instrument-centric, but a concrete stored gate
    # may identify an exact portfolio input snapshot.  That lineage cannot be
    # discarded merely because the base policy does not require a portfolio.
    needs_portfolio = requirement.requires_portfolio_context or (
        gate is not None and gate.input_snapshot_id is not None
    )
    if not needs_portfolio:
        return OutputEvaluationMatchStatus.NOT_REQUIRED
    if portfolio is None:
        blockers.add(OutputEvaluationBlocker.REQUIRED_PORTFOLIO_CONTEXT_MISSING)
        return OutputEvaluationMatchStatus.MISSING
    if gate is not None and gate.input_snapshot_id is not None and portfolio.portfolio_snapshot_id != gate.input_snapshot_id:
        blockers.add(OutputEvaluationBlocker.PORTFOLIO_CONTEXT_MISMATCH)
        return OutputEvaluationMatchStatus.MISMATCH
    if gate is not None and gate.input_snapshot_id is not None:
        warnings.add("PORTFOLIO_CONTEXT_MATCHED_BY_SNAPSHOT_ID")
    else:
        warnings.add("PORTFOLIO_CONTEXT_REQUIRED_GATE_LINEAGE_UNAVAILABLE")
    return OutputEvaluationMatchStatus.MATCHED


def _reference(state: UnifiedIntelligenceState, domain: IntelligenceEvidenceDomain):
    return next((value for value in state.evidence_references if value.domain is domain), None)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _semantic_values(values: dict) -> dict:
    return {key: _semantic_value(value) for key, value in sorted(values.items())}


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field: _semantic_value(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


__all__ = (
    "BrainOutputEvaluationContext", "OutputContextRequirement", "OutputEvaluationBlocker",
    "OutputEvaluationMatchStatus", "OUTPUT_CONTEXT_REQUIREMENTS", "brain_output_evaluation_context_fingerprint",
    "create_brain_output_evaluation_context", "output_context_requirement",
)
