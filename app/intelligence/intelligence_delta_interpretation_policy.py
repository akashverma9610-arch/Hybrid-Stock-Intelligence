"""Frozen, objective-only governance policy for future delta interpretation.

This module is deliberately policy metadata only.  It does not accept an
``IntelligenceDelta`` and does not produce an interpreted outcome.  A later,
separately approved slice would need to add a bounded interpreter and prove
that its input contains the typed lineage required by these rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class IntelligenceDeltaInterpretationPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class ObjectiveDeltaInterpretationDimension(StrEnum):
    FRESHNESS = "FRESHNESS"
    INTELLIGENCE_AVAILABILITY = "INTELLIGENCE_AVAILABILITY"
    RELIABILITY = "RELIABILITY"
    HISTORICAL_INTEGRITY = "HISTORICAL_INTEGRITY"


class ObjectiveDeltaInterpretationKind(StrEnum):
    FRESHNESS_IMPROVED = "FRESHNESS_IMPROVED"
    FRESHNESS_DEGRADED = "FRESHNESS_DEGRADED"
    INTELLIGENCE_AVAILABILITY_IMPROVED = "INTELLIGENCE_AVAILABILITY_IMPROVED"
    INTELLIGENCE_AVAILABILITY_DEGRADED = "INTELLIGENCE_AVAILABILITY_DEGRADED"
    RELIABILITY_IMPROVED = "RELIABILITY_IMPROVED"
    RELIABILITY_DEGRADED = "RELIABILITY_DEGRADED"
    HISTORICAL_INTEGRITY_IMPROVED = "HISTORICAL_INTEGRITY_IMPROVED"
    HISTORICAL_INTEGRITY_DEGRADED = "HISTORICAL_INTEGRITY_DEGRADED"
    NON_COMPARABLE = "NON_COMPARABLE"
    NO_DIRECTIONAL_CHANGE = "NO_DIRECTIONAL_CHANGE"


class ObjectiveDeltaInterpretationCondition(StrEnum):
    PREVIOUS_SELECTED_USABLE_ROUTE = "PREVIOUS_SELECTED_USABLE_ROUTE"
    CURRENT_SELECTED_USABLE_ROUTE = "CURRENT_SELECTED_USABLE_ROUTE"


class ObjectiveDeltaInterpretationNonComparableCase(StrEnum):
    UNSUPPORTED_OR_MIXED_FRESHNESS = "UNSUPPORTED_OR_MIXED_FRESHNESS"
    UNSUPPORTED_AVAILABILITY = "UNSUPPORTED_AVAILABILITY"
    EVIDENCE_ADDED_OR_REMOVED_ONLY = "EVIDENCE_ADDED_OR_REMOVED_ONLY"
    RELIABILITY_CONFLICTED = "RELIABILITY_CONFLICTED"
    RELIABILITY_FALLBACK_OR_LAST_KNOWN_GOOD = "RELIABILITY_FALLBACK_OR_LAST_KNOWN_GOOD"
    RELIABILITY_MIXED_DIMENSION = "RELIABILITY_MIXED_DIMENSION"
    RELIABILITY_ROUTE_CAUSE_ONLY = "RELIABILITY_ROUTE_CAUSE_ONLY"
    HISTORICAL_INTEGRITY_NATIVE_UNAVAILABLE = "HISTORICAL_INTEGRITY_NATIVE_UNAVAILABLE"
    HISTORICAL_INTEGRITY_PROJECTED_CONFLICTED = "HISTORICAL_INTEGRITY_PROJECTED_CONFLICTED"
    HISTORICAL_INTEGRITY_FINGERPRINT_ONLY = "HISTORICAL_INTEGRITY_FINGERPRINT_ONLY"


class ObjectiveDeltaInterpretationExclusion(StrEnum):
    THESIS_DIRECTION = "THESIS_DIRECTION"
    OPPORTUNITY_DIRECTION = "OPPORTUNITY_DIRECTION"
    GENERIC_INVESTMENT_RISK_DIRECTION = "GENERIC_INVESTMENT_RISK_DIRECTION"
    BULLISH_BEARISH = "BULLISH_BEARISH"
    RECOMMENDATION = "RECOMMENDATION"
    EXECUTION = "EXECUTION"
    DECISION_SCORE_DIRECTION = "DECISION_SCORE_DIRECTION"
    NEWS_CATALYST_DIRECTION = "NEWS_CATALYST_DIRECTION"
    SIX_GATES_DIRECTION = "SIX_GATES_DIRECTION"


@dataclass(frozen=True, slots=True)
class ObjectiveDeltaInterpretationRule:
    """One approved directional transition, without an evaluation mechanism."""

    dimension: ObjectiveDeltaInterpretationDimension
    previous_state: str
    current_state: str
    interpretation: ObjectiveDeltaInterpretationKind
    required_conditions: tuple[ObjectiveDeltaInterpretationCondition, ...] = ()

    def __post_init__(self) -> None:
        if not self.previous_state or not self.current_state:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_RULE_STATE_REQUIRED")
        if self.interpretation in {
            ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
            ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
        }:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_RULE_DIRECTION_REQUIRED")
        if self.required_conditions != tuple(sorted(set(self.required_conditions), key=lambda value: value.value)):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_RULE_CONDITIONS_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class FrozenObjectiveIntelligenceDeltaInterpretationPolicy:
    """Immutable approved semantics; intentionally not selected or active."""

    policy_id: str
    version: str
    proposal_policy_id: str
    proposal_version: str
    approval_status: IntelligenceDeltaInterpretationPolicyApprovalStatus
    approved_by: str
    selected_for_future_interpreter: bool
    active: bool
    identical_state_interpretation: ObjectiveDeltaInterpretationKind
    unsupported_transition_interpretation: ObjectiveDeltaInterpretationKind
    evidence_presence_only_interpretation: ObjectiveDeltaInterpretationKind
    rules: tuple[ObjectiveDeltaInterpretationRule, ...]
    non_comparable_cases: tuple[ObjectiveDeltaInterpretationNonComparableCase, ...]
    exclusions: tuple[ObjectiveDeltaInterpretationExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.policy_id, self.version, self.proposal_policy_id, self.proposal_version, self.approved_by)):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not IntelligenceDeltaInterpretationPolicyApprovalStatus.APPROVED:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_APPROVAL_REQUIRED")
        if self.selected_for_future_interpreter or self.active:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_MUST_NOT_BE_ACTIVE")
        if self.identical_state_interpretation is not ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_IDENTICAL_STATE_REQUIRED")
        if self.unsupported_transition_interpretation is not ObjectiveDeltaInterpretationKind.NON_COMPARABLE:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_UNSUPPORTED_NONCOMPARABLE_REQUIRED")
        if self.evidence_presence_only_interpretation is not ObjectiveDeltaInterpretationKind.NON_COMPARABLE:
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_EVIDENCE_PRESENCE_NONCOMPARABLE_REQUIRED")
        if self.rules != tuple(sorted(set(self.rules), key=_rule_key)):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_RULES_NONCANONICAL")
        if self.non_comparable_cases != tuple(sorted(set(self.non_comparable_cases), key=lambda value: value.value)):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_NONCOMPARABLE_NONCANONICAL")
        if self.exclusions != tuple(sorted(set(self.exclusions), key=lambda value: value.value)):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_EXCLUSIONS_NONCANONICAL")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != objective_delta_interpretation_policy_fingerprint(self):
            raise ValueError("OBJECTIVE_DELTA_INTERPRETATION_POLICY_FINGERPRINT_MISMATCH")


def _rule_key(value: ObjectiveDeltaInterpretationRule) -> tuple[str, str, str, str, tuple[str, ...]]:
    return (
        value.dimension.value,
        value.previous_state,
        value.current_state,
        value.interpretation.value,
        tuple(item.value for item in value.required_conditions),
    )


def create_frozen_objective_intelligence_delta_interpretation_policy(
    *,
    policy_id: str,
    version: str,
    proposal_policy_id: str,
    proposal_version: str,
    approved_by: str,
    rules: tuple[ObjectiveDeltaInterpretationRule, ...],
    non_comparable_cases: tuple[ObjectiveDeltaInterpretationNonComparableCase, ...],
    exclusions: tuple[ObjectiveDeltaInterpretationExclusion, ...],
    provenance: tuple[tuple[str, str], ...],
) -> FrozenObjectiveIntelligenceDeltaInterpretationPolicy:
    values = dict(
        policy_id=policy_id,
        version=version,
        proposal_policy_id=proposal_policy_id,
        proposal_version=proposal_version,
        approval_status=IntelligenceDeltaInterpretationPolicyApprovalStatus.APPROVED,
        approved_by=approved_by,
        selected_for_future_interpreter=False,
        active=False,
        identical_state_interpretation=ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE,
        unsupported_transition_interpretation=ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
        evidence_presence_only_interpretation=ObjectiveDeltaInterpretationKind.NON_COMPARABLE,
        rules=tuple(sorted(set(rules), key=_rule_key)),
        non_comparable_cases=tuple(sorted(set(non_comparable_cases), key=lambda value: value.value)),
        exclusions=tuple(sorted(set(exclusions), key=lambda value: value.value)),
        provenance=tuple(sorted(set(provenance))),
    )
    return FrozenObjectiveIntelligenceDeltaInterpretationPolicy(
        **values,
        fingerprint=objective_delta_interpretation_policy_fingerprint_values(values),
    )


def objective_delta_interpretation_policy_fingerprint(
    value: FrozenObjectiveIntelligenceDeltaInterpretationPolicy,
) -> str:
    return objective_delta_interpretation_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def objective_delta_interpretation_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"],
        version=values["version"],
        proposal_policy_id=values["proposal_policy_id"],
        proposal_version=values["proposal_version"],
        approval_status=values["approval_status"].value,
        approved_by=values["approved_by"],
        selected_for_future_interpreter=values["selected_for_future_interpreter"],
        active=values["active"],
        identical_state_interpretation=values["identical_state_interpretation"].value,
        unsupported_transition_interpretation=values["unsupported_transition_interpretation"].value,
        evidence_presence_only_interpretation=values["evidence_presence_only_interpretation"].value,
        rules=tuple(
            (
                item.dimension.value,
                item.previous_state,
                item.current_state,
                item.interpretation.value,
                tuple(condition.value for condition in item.required_conditions),
            )
            for item in values["rules"]
        ),
        non_comparable_cases=tuple(item.value for item in values["non_comparable_cases"]),
        exclusions=tuple(item.value for item in values["exclusions"]),
        provenance=values["provenance"],
    )


_RULES = (
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.FRESHNESS, "FRESH", "STALE", ObjectiveDeltaInterpretationKind.FRESHNESS_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.FRESHNESS, "STALE", "FRESH", ObjectiveDeltaInterpretationKind.FRESHNESS_IMPROVED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.INTELLIGENCE_AVAILABILITY, "UNAVAILABLE", "AVAILABLE", ObjectiveDeltaInterpretationKind.INTELLIGENCE_AVAILABILITY_IMPROVED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.INTELLIGENCE_AVAILABILITY, "AVAILABLE", "UNAVAILABLE", ObjectiveDeltaInterpretationKind.INTELLIGENCE_AVAILABILITY_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "READY", "DEGRADED", ObjectiveDeltaInterpretationKind.RELIABILITY_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "DEGRADED", "READY", ObjectiveDeltaInterpretationKind.RELIABILITY_IMPROVED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "SELECTED_USABLE_ROUTE", "PRIMARY_UNAVAILABLE", ObjectiveDeltaInterpretationKind.RELIABILITY_DEGRADED, (ObjectiveDeltaInterpretationCondition.PREVIOUS_SELECTED_USABLE_ROUTE,)),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "SELECTED_USABLE_ROUTE", "UNAVAILABLE", ObjectiveDeltaInterpretationKind.RELIABILITY_DEGRADED, (ObjectiveDeltaInterpretationCondition.PREVIOUS_SELECTED_USABLE_ROUTE,)),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "PRIMARY_UNAVAILABLE", "SELECTED_USABLE_ROUTE", ObjectiveDeltaInterpretationKind.RELIABILITY_IMPROVED, (ObjectiveDeltaInterpretationCondition.CURRENT_SELECTED_USABLE_ROUTE,)),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.RELIABILITY, "UNAVAILABLE", "SELECTED_USABLE_ROUTE", ObjectiveDeltaInterpretationKind.RELIABILITY_IMPROVED, (ObjectiveDeltaInterpretationCondition.CURRENT_SELECTED_USABLE_ROUTE,)),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "VALID", "PARTIAL", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "VALID", "INVALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "PARTIAL", "VALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "INVALID", "VALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "PARTIAL", "INVALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
    ObjectiveDeltaInterpretationRule(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY, "INVALID", "PARTIAL", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
)


CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY = (
    create_frozen_objective_intelligence_delta_interpretation_policy(
        policy_id="intelligence-delta-interpretation-policy",
        version="v1-approved",
        proposal_policy_id="intelligence-delta-interpretation-policy",
        proposal_version="v1-proposed",
        approved_by="human:Akash-Verma",
        rules=_RULES,
        non_comparable_cases=(
            ObjectiveDeltaInterpretationNonComparableCase.UNSUPPORTED_OR_MIXED_FRESHNESS,
            ObjectiveDeltaInterpretationNonComparableCase.UNSUPPORTED_AVAILABILITY,
            ObjectiveDeltaInterpretationNonComparableCase.EVIDENCE_ADDED_OR_REMOVED_ONLY,
            ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_CONFLICTED,
            ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_FALLBACK_OR_LAST_KNOWN_GOOD,
            ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_MIXED_DIMENSION,
            ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_ROUTE_CAUSE_ONLY,
            ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_NATIVE_UNAVAILABLE,
            ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_PROJECTED_CONFLICTED,
            ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_FINGERPRINT_ONLY,
        ),
        exclusions=(
            ObjectiveDeltaInterpretationExclusion.THESIS_DIRECTION,
            ObjectiveDeltaInterpretationExclusion.OPPORTUNITY_DIRECTION,
            ObjectiveDeltaInterpretationExclusion.GENERIC_INVESTMENT_RISK_DIRECTION,
            ObjectiveDeltaInterpretationExclusion.BULLISH_BEARISH,
            ObjectiveDeltaInterpretationExclusion.RECOMMENDATION,
            ObjectiveDeltaInterpretationExclusion.EXECUTION,
            ObjectiveDeltaInterpretationExclusion.DECISION_SCORE_DIRECTION,
            ObjectiveDeltaInterpretationExclusion.NEWS_CATALYST_DIRECTION,
            ObjectiveDeltaInterpretationExclusion.SIX_GATES_DIRECTION,
        ),
        provenance=(
            ("governance_approval", "U14D-4A"),
            ("proposal_policy", "intelligence-delta-interpretation-policy/v1-proposed"),
            ("scope", "OBJECTIVE_ONLY"),
        ),
    )
)


__all__ = (
    "CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY",
    "FrozenObjectiveIntelligenceDeltaInterpretationPolicy",
    "IntelligenceDeltaInterpretationPolicyApprovalStatus",
    "ObjectiveDeltaInterpretationCondition",
    "ObjectiveDeltaInterpretationDimension",
    "ObjectiveDeltaInterpretationExclusion",
    "ObjectiveDeltaInterpretationKind",
    "ObjectiveDeltaInterpretationNonComparableCase",
    "ObjectiveDeltaInterpretationRule",
    "create_frozen_objective_intelligence_delta_interpretation_policy",
    "objective_delta_interpretation_policy_fingerprint",
)
