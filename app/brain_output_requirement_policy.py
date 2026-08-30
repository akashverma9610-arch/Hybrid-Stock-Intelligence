"""Versioned governance policy for shared-Brain output-context requirements.

The policy identifies required immutable inputs; it never calculates those
inputs and never produces an action, recommendation, or execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.gates.engine import ActionContext
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import BrainOutputContext


@dataclass(frozen=True, slots=True)
class BrainOutputContextRequirement:
    output_context: BrainOutputContext
    requires_unified_state: bool
    requires_decision_score: bool
    requires_six_gates: bool
    requires_portfolio_context: bool
    requires_action_context: bool
    required_action_context: ActionContext | None
    informational_only: bool
    output_decision_capable: bool

    def __post_init__(self) -> None:
        if not self.requires_unified_state:
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_UNIFIED_STATE_REQUIRED")
        if self.requires_action_context != (self.required_action_context is not None):
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_ACTION_CONTEXT_INCONSISTENT")
        if self.requires_six_gates != self.requires_action_context:
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_GATE_ACTION_INCONSISTENT")
        if self.informational_only and self.output_decision_capable:
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_INFORMATIONAL_ACTION_CONFLICT")


@dataclass(frozen=True, slots=True)
class BrainOutputRequirementPolicy:
    policy_id: str
    version: str
    requirements: tuple[BrainOutputContextRequirement, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.policy_id or not self.version:
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_POLICY_REQUIRED_FIELD")
        contexts = tuple(value.output_context for value in self.requirements)
        if contexts != tuple(sorted(contexts, key=lambda value: value.value)):
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_POLICY_NONCANONICAL")
        if set(contexts) != set(BrainOutputContext) or len(contexts) != len(BrainOutputContext):
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_POLICY_CONTEXT_COVERAGE_REQUIRED")
        if self.fingerprint != brain_output_requirement_policy_fingerprint(self):
            raise ValueError("BRAIN_OUTPUT_REQUIREMENT_POLICY_FINGERPRINT_MISMATCH")

    def requirement_for(self, context: BrainOutputContext) -> BrainOutputContextRequirement:
        try:
            return next(value for value in self.requirements if value.output_context is context)
        except StopIteration as error:
            raise ValueError("OUTPUT_CONTEXT_REQUIREMENT_UNDEFINED") from error


def create_brain_output_requirement_policy(
    *, policy_id: str, version: str, requirements: tuple[BrainOutputContextRequirement, ...],
) -> BrainOutputRequirementPolicy:
    values = dict(policy_id=policy_id, version=version, requirements=tuple(sorted(requirements, key=lambda value: value.output_context.value)))
    return BrainOutputRequirementPolicy(**values, fingerprint=brain_output_requirement_policy_fingerprint_values(values))


def brain_output_requirement_policy_fingerprint(value: BrainOutputRequirementPolicy) -> str:
    return brain_output_requirement_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_output_requirement_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"], version=values["version"],
        requirements=tuple(
            (
                item.output_context.value, item.requires_unified_state, item.requires_decision_score,
                item.requires_six_gates, item.requires_portfolio_context,
                item.requires_action_context,
                None if item.required_action_context is None else item.required_action_context.value,
                item.informational_only, item.output_decision_capable,
            )
            for item in values["requirements"]
        ),
    )


CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY = create_brain_output_requirement_policy(
    policy_id="brain-output-context-requirements",
    version="v1",
    requirements=(
        # Discovery is shared-Brain-qualified but not a recommendation.  The
        # existing universe path creates FRESH_ENTRY gate evidence alongside a
        # persisted scorecard before materializing a qualified opportunity.
        BrainOutputContextRequirement(BrainOutputContext.OPPORTUNITY_DISCOVERY, True, True, True, False, True, ActionContext.FRESH_ENTRY, False, True),
        BrainOutputContextRequirement(BrainOutputContext.DEEP_ANALYSIS, True, False, False, False, False, None, True, False),
        # Broad portfolio and sell/trim reviews are intentionally not collapsed
        # onto HOLD/REDUCE/EXIT.  Their later concrete action subcontexts need
        # their own governed mapping.
        BrainOutputContextRequirement(BrainOutputContext.PORTFOLIO_REVIEW, True, False, False, True, False, None, True, False),
        BrainOutputContextRequirement(BrainOutputContext.SELL_TRIM_REVIEW, True, False, False, True, False, None, True, False),
        BrainOutputContextRequirement(BrainOutputContext.ROTATION_REVIEW, True, True, True, True, True, ActionContext.ROTATE_IN, False, True),
        BrainOutputContextRequirement(BrainOutputContext.ENTRY_SETUP_REVIEW, True, True, True, False, True, ActionContext.FRESH_ENTRY, False, True),
        # Generic alerts are heterogeneous.  Specific actionable alerts must
        # later reference a governed concrete output/action context.
        BrainOutputContextRequirement(BrainOutputContext.ALERT_REVIEW, True, False, False, False, False, None, True, False),
    ),
)


__all__ = (
    "BrainOutputContextRequirement", "BrainOutputRequirementPolicy",
    "CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY", "brain_output_requirement_policy_fingerprint",
    "create_brain_output_requirement_policy",
)
