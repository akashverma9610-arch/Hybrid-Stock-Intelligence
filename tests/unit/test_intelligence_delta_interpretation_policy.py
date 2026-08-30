from __future__ import annotations

from dataclasses import replace

import pytest

import app.intelligence.intelligence_delta_interpretation_policy as policy_module
from app.intelligence.intelligence_delta_interpretation_policy import (
    CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY,
    IntelligenceDeltaInterpretationPolicyApprovalStatus,
    ObjectiveDeltaInterpretationCondition,
    ObjectiveDeltaInterpretationDimension,
    ObjectiveDeltaInterpretationExclusion,
    ObjectiveDeltaInterpretationKind,
    ObjectiveDeltaInterpretationNonComparableCase,
    objective_delta_interpretation_policy_fingerprint,
)


POLICY = CURRENT_FROZEN_OBJECTIVE_INTELLIGENCE_DELTA_INTERPRETATION_POLICY


def _rules(dimension: ObjectiveDeltaInterpretationDimension):
    return tuple(value for value in POLICY.rules if value.dimension is dimension)


def test_frozen_policy_identity_approval_lineage_and_inactive_state_are_exact() -> None:
    assert (POLICY.policy_id, POLICY.version) == ("intelligence-delta-interpretation-policy", "v1-approved")
    assert (POLICY.proposal_policy_id, POLICY.proposal_version) == ("intelligence-delta-interpretation-policy", "v1-proposed")
    assert POLICY.approval_status is IntelligenceDeltaInterpretationPolicyApprovalStatus.APPROVED
    assert POLICY.approved_by == "human:Akash-Verma"
    assert not POLICY.selected_for_future_interpreter and not POLICY.active


def test_frozen_policy_fingerprint_is_deterministic_and_tamper_closed() -> None:
    assert objective_delta_interpretation_policy_fingerprint(POLICY) == POLICY.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(POLICY, version="v1-tampered")


def test_freshness_and_availability_rules_are_exact_and_narrow() -> None:
    assert {
        (rule.previous_state, rule.current_state, rule.interpretation)
        for rule in _rules(ObjectiveDeltaInterpretationDimension.FRESHNESS)
    } == {
        ("FRESH", "STALE", ObjectiveDeltaInterpretationKind.FRESHNESS_DEGRADED),
        ("STALE", "FRESH", ObjectiveDeltaInterpretationKind.FRESHNESS_IMPROVED),
    }
    assert {
        (rule.previous_state, rule.current_state, rule.interpretation)
        for rule in _rules(ObjectiveDeltaInterpretationDimension.INTELLIGENCE_AVAILABILITY)
    } == {
        ("UNAVAILABLE", "AVAILABLE", ObjectiveDeltaInterpretationKind.INTELLIGENCE_AVAILABILITY_IMPROVED),
        ("AVAILABLE", "UNAVAILABLE", ObjectiveDeltaInterpretationKind.INTELLIGENCE_AVAILABILITY_DEGRADED),
    }
    assert POLICY.identical_state_interpretation is ObjectiveDeltaInterpretationKind.NO_DIRECTIONAL_CHANGE
    assert POLICY.evidence_presence_only_interpretation is ObjectiveDeltaInterpretationKind.NON_COMPARABLE


def test_reliability_rules_require_typed_route_evidence_and_protect_composite_states() -> None:
    rules = _rules(ObjectiveDeltaInterpretationDimension.RELIABILITY)
    assert {(rule.previous_state, rule.current_state, rule.interpretation) for rule in rules} >= {
        ("READY", "DEGRADED", ObjectiveDeltaInterpretationKind.RELIABILITY_DEGRADED),
        ("DEGRADED", "READY", ObjectiveDeltaInterpretationKind.RELIABILITY_IMPROVED),
    }
    route_rules = tuple(rule for rule in rules if "SELECTED_USABLE_ROUTE" in {rule.previous_state, rule.current_state})
    assert len(route_rules) == 4
    assert {
        condition for rule in route_rules for condition in rule.required_conditions
    } == {
        ObjectiveDeltaInterpretationCondition.PREVIOUS_SELECTED_USABLE_ROUTE,
        ObjectiveDeltaInterpretationCondition.CURRENT_SELECTED_USABLE_ROUTE,
    }
    protected = set(POLICY.non_comparable_cases)
    assert {
        ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_CONFLICTED,
        ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_FALLBACK_OR_LAST_KNOWN_GOOD,
        ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_MIXED_DIMENSION,
        ObjectiveDeltaInterpretationNonComparableCase.RELIABILITY_ROUTE_CAUSE_ONLY,
    }.issubset(protected)
    assert not any(
        {rule.previous_state, rule.current_state}.intersection({"CONFLICTED", "FALLBACK_USED", "LAST_KNOWN_GOOD"})
        for rule in rules
    )


def test_historical_integrity_rules_are_exact_and_unavailable_or_projected_conflict_is_noncomparable() -> None:
    assert {
        (rule.previous_state, rule.current_state, rule.interpretation)
        for rule in _rules(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY)
    } == {
        ("VALID", "PARTIAL", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
        ("VALID", "INVALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
        ("PARTIAL", "VALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
        ("INVALID", "VALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
        ("PARTIAL", "INVALID", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_DEGRADED),
        ("INVALID", "PARTIAL", ObjectiveDeltaInterpretationKind.HISTORICAL_INTEGRITY_IMPROVED),
    }
    protected = set(POLICY.non_comparable_cases)
    assert {
        ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_NATIVE_UNAVAILABLE,
        ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_PROJECTED_CONFLICTED,
        ObjectiveDeltaInterpretationNonComparableCase.HISTORICAL_INTEGRITY_FINGERPRINT_ONLY,
    }.issubset(protected)
    assert not any("UNAVAILABLE" in {rule.previous_state, rule.current_state} for rule in _rules(ObjectiveDeltaInterpretationDimension.HISTORICAL_INTEGRITY))


def test_policy_excludes_global_direction_and_has_no_runtime_interpreter() -> None:
    assert set(POLICY.exclusions) == set(ObjectiveDeltaInterpretationExclusion)
    assert POLICY.unsupported_transition_interpretation is ObjectiveDeltaInterpretationKind.NON_COMPARABLE
    assert not hasattr(policy_module, "interpret_intelligence_delta")
    assert not hasattr(policy_module, "interpret_delta")
