from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import app.portfolio.sell_side_policy as module
from app.portfolio.sell_side_policy import (
    CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY as POLICY,
    CapitalEfficiencyState, SellSideDecision, SellSidePriorityStage,
    SellSideThesisState, TrimAuthorizationStatus, portfolio_sell_side_policy_fingerprint,
)


def test_approved_identity_lineage_reviewer_and_fingerprint_are_frozen() -> None:
    assert (POLICY.policy_id, POLICY.version, POLICY.proposal_version) == (
        "portfolio-sell-side-decision-policy", "v1-approved", "v1-proposed",
    )
    assert POLICY.proposal_fingerprint == "a11e84973ca19f4e0e23a4afc1ca989a9cfe4add1e8451750f333327651d6253"
    assert POLICY.approved_by == "human:Akash-Verma"
    assert not POLICY.selected and not POLICY.active
    assert portfolio_sell_side_policy_fingerprint(POLICY) == POLICY.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(POLICY, provenance=(*POLICY.provenance, ("tamper", "true")))


def test_approved_decisions_and_thesis_states_are_exact_and_trim_is_unauthorized() -> None:
    assert POLICY.thesis_states == tuple(SellSideThesisState)
    assert POLICY.decisions == tuple(SellSideDecision)
    assert "TRIM" not in {value.value for value in POLICY.decisions}
    assert POLICY.trim_status is TrimAuthorizationStatus.TRIM_NOT_AUTHORIZED_V1
    assert not POLICY.trim_priority_enabled
    assert POLICY.priority_order[3] is SellSidePriorityStage.FUTURE_TRIM_RULE_UNAVAILABLE


def test_exit_hold_review_rotation_and_capital_efficiency_boundaries_are_frozen() -> None:
    assert POLICY.exit_guards == (
        "CURRENT_EVIDENCE", "SUFFICIENT_EVIDENCE", "NO_MATERIAL_UNRESOLVED_CONFLICT",
        "INVALIDATED_THESIS", "NO_ELIGIBLE_GOVERNED_REPLACEMENT",
    )
    assert POLICY.hold_guards == (
        "INTACT_THESIS", "CURRENT_SUFFICIENT_EVIDENCE", "NO_GOVERNED_INVALIDATION",
        "NO_AUTHORIZED_RISK_REDUCTION", "NO_VALID_ROTATION",
    )
    assert POLICY.rotation_authority == "EXISTING_GOVERNED_CAPITAL_ROTATION_ENGINE"
    assert POLICY.capital_efficiency_state is CapitalEfficiencyState.CAPITAL_INEFFICIENT
    assert POLICY.capital_efficiency_descriptive_only
    assert POLICY.review_required_conditions == tuple(sorted(POLICY.review_required_conditions))


def test_forward_paper_is_descriptive_only_and_cannot_authorize_a_decision() -> None:
    assert POLICY.forward_paper_descriptive_only
    assert POLICY.forward_paper_prohibited_effects == (
        "ALTER_THESIS_STATE", "AUTHORIZE_EXIT", "AUTHORIZE_ROTATE", "AUTHORIZE_TRIM",
        "ALTER_THRESHOLDS", "MUTATE_POLICY",
    )


def test_policy_has_no_runtime_action_persistence_or_network_surface() -> None:
    source = inspect.getsource(module)
    assert not any(token in source for token in (
        "PortfolioEngine(", "CapitalRotationEngine(", "DecisionAuditStore(", "requests.",
        "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "APIRouter", "def evaluate",
        "def produce", "def execute", "broker", "order(",
    ))
