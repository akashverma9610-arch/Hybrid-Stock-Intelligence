"""Frozen approval metadata for future portfolio sell-side decisions.

This module is passive: no holding evaluation, persistence, alerts, signals, or
portfolio mutation is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


PROPOSAL_FINGERPRINT = "a11e84973ca19f4e0e23a4afc1ca989a9cfe4add1e8451750f333327651d6253"


class SellSidePolicyApprovalStatus(StrEnum):
    APPROVED = "APPROVED"


class SellSideThesisState(StrEnum):
    INTACT = "INTACT"
    WEAKENED = "WEAKENED"
    INVALIDATED = "INVALIDATED"
    INSUFFICIENT = "INSUFFICIENT"


class SellSideDecision(StrEnum):
    HOLD = "HOLD"
    EXIT_TO_CASH = "EXIT_TO_CASH"
    ROTATE = "ROTATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_ACTION = "NO_ACTION"


class TrimAuthorizationStatus(StrEnum):
    TRIM_NOT_AUTHORIZED_V1 = "TRIM_NOT_AUTHORIZED_V1"


class CapitalEfficiencyState(StrEnum):
    CAPITAL_INEFFICIENT = "CAPITAL_INEFFICIENT"


class SellSidePriorityStage(StrEnum):
    REVIEW_REQUIRED = "1:REVIEW_REQUIRED"
    INVALIDATED_WITH_ELIGIBLE_REPLACEMENT = "2:INVALIDATED_WITH_ELIGIBLE_REPLACEMENT_TO_ROTATE"
    INVALIDATED_WITHOUT_ELIGIBLE_REPLACEMENT = "3:INVALIDATED_WITHOUT_ELIGIBLE_REPLACEMENT_TO_EXIT_TO_CASH"
    FUTURE_TRIM_RULE_UNAVAILABLE = "4:FUTURE_TRIM_RULE_UNAVAILABLE"
    VALID_GOVERNED_ROTATION = "5:VALID_GOVERNED_ROTATION_TO_ROTATE"
    INTACT_THESIS = "6:INTACT_THESIS_TO_HOLD"
    OTHERWISE = "7:OTHERWISE_NO_ACTION"


_ROTATION_REQUIREMENTS = (
    "CONFIRMATION_AND_COOLDOWN", "CONFIDENCE", "ENTRY_STOP_INVALIDATION",
    "EXECUTABLE_GATES", "FRICTION_AND_TAX", "PORTFOLIO_CONSTRAINTS",
    "REPLACEMENT_EDGE", "RISK_REWARD", "SECTOR_POLICY",
)
_REVIEW_REQUIRED_CONDITIONS = (
    "CONFLICTED_EVIDENCE", "INCOMPLETE_REQUIRED_PORTFOLIO_CONTEXT",
    "INSUFFICIENT_THESIS_EVIDENCE", "MISSING_REQUIRED_EVIDENCE",
    "NON_COMPARABLE_EVIDENCE", "STALE_EVIDENCE", "UNRESOLVED_REPLACEMENT_EVIDENCE",
)


@dataclass(frozen=True, slots=True)
class FrozenPortfolioSellSideDecisionPolicy:
    """Immutable approved contract, deliberately without an action evaluator."""

    policy_id: str
    version: str
    proposal_version: str
    proposal_fingerprint: str
    approval_status: SellSidePolicyApprovalStatus
    approved_by: str
    selected: bool
    active: bool
    thesis_states: tuple[SellSideThesisState, ...]
    decisions: tuple[SellSideDecision, ...]
    trim_status: TrimAuthorizationStatus
    capital_efficiency_state: CapitalEfficiencyState
    capital_efficiency_descriptive_only: bool
    rotation_authority: str
    rotation_requirements: tuple[str, ...]
    exit_guards: tuple[str, ...]
    review_required_conditions: tuple[str, ...]
    hold_guards: tuple[str, ...]
    pnl_is_not_an_action_rule: bool
    priority_order: tuple[SellSidePriorityStage, ...]
    trim_priority_enabled: bool
    forward_paper_descriptive_only: bool
    forward_paper_prohibited_effects: tuple[str, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (self.policy_id, self.version, self.proposal_version) != (
            "portfolio-sell-side-decision-policy", "v1-approved", "v1-proposed",
        ):
            raise ValueError("SELL_SIDE_POLICY_IDENTITY_REQUIRED")
        if self.proposal_fingerprint != PROPOSAL_FINGERPRINT:
            raise ValueError("SELL_SIDE_POLICY_PROPOSAL_LINEAGE_REQUIRED")
        if self.approval_status is not SellSidePolicyApprovalStatus.APPROVED or self.approved_by != "human:Akash-Verma":
            raise ValueError("SELL_SIDE_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.selected or self.active:
            raise ValueError("SELL_SIDE_POLICY_MUST_NOT_BE_ACTIVE")
        if self.thesis_states != tuple(SellSideThesisState) or self.decisions != tuple(SellSideDecision):
            raise ValueError("SELL_SIDE_POLICY_VOCABULARY_REQUIRED")
        if self.trim_status is not TrimAuthorizationStatus.TRIM_NOT_AUTHORIZED_V1 or self.trim_priority_enabled:
            raise ValueError("SELL_SIDE_POLICY_TRIM_UNAUTHORIZED_REQUIRED")
        if self.capital_efficiency_state is not CapitalEfficiencyState.CAPITAL_INEFFICIENT or not self.capital_efficiency_descriptive_only:
            raise ValueError("SELL_SIDE_POLICY_CAPITAL_EFFICIENCY_BOUNDARY_REQUIRED")
        if self.rotation_authority != "EXISTING_GOVERNED_CAPITAL_ROTATION_ENGINE" or self.rotation_requirements != _ROTATION_REQUIREMENTS:
            raise ValueError("SELL_SIDE_POLICY_ROTATION_GOVERNANCE_REQUIRED")
        if self.exit_guards != (
            "CURRENT_EVIDENCE", "SUFFICIENT_EVIDENCE", "NO_MATERIAL_UNRESOLVED_CONFLICT",
            "INVALIDATED_THESIS", "NO_ELIGIBLE_GOVERNED_REPLACEMENT",
        ):
            raise ValueError("SELL_SIDE_POLICY_EXIT_GUARDS_REQUIRED")
        if self.review_required_conditions != _REVIEW_REQUIRED_CONDITIONS:
            raise ValueError("SELL_SIDE_POLICY_REVIEW_FAIL_CLOSED_REQUIRED")
        if self.hold_guards != (
            "INTACT_THESIS", "CURRENT_SUFFICIENT_EVIDENCE", "NO_GOVERNED_INVALIDATION",
            "NO_AUTHORIZED_RISK_REDUCTION", "NO_VALID_ROTATION",
        ) or not self.pnl_is_not_an_action_rule:
            raise ValueError("SELL_SIDE_POLICY_HOLD_GUARDS_REQUIRED")
        if self.priority_order != tuple(SellSidePriorityStage):
            raise ValueError("SELL_SIDE_POLICY_PRIORITY_REQUIRED")
        if not self.forward_paper_descriptive_only or self.forward_paper_prohibited_effects != (
            "ALTER_THESIS_STATE", "AUTHORIZE_EXIT", "AUTHORIZE_ROTATE", "AUTHORIZE_TRIM",
            "ALTER_THRESHOLDS", "MUTATE_POLICY",
        ):
            raise ValueError("SELL_SIDE_POLICY_FORWARD_PAPER_FIREWALL_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("SELL_SIDE_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != portfolio_sell_side_policy_fingerprint(self):
            raise ValueError("SELL_SIDE_POLICY_FINGERPRINT_MISMATCH")


def _scalar(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_scalar(item) for item in value)
    return value


def portfolio_sell_side_policy_fingerprint(value: FrozenPortfolioSellSideDecisionPolicy) -> str:
    return manifest_fingerprint(**{
        field: _scalar(getattr(value, field))
        for field in value.__dataclass_fields__
        if field != "fingerprint"
    })


def create_frozen_portfolio_sell_side_decision_policy() -> FrozenPortfolioSellSideDecisionPolicy:
    values = dict(
        policy_id="portfolio-sell-side-decision-policy", version="v1-approved",
        proposal_version="v1-proposed", proposal_fingerprint=PROPOSAL_FINGERPRINT,
        approval_status=SellSidePolicyApprovalStatus.APPROVED, approved_by="human:Akash-Verma",
        selected=False, active=False, thesis_states=tuple(SellSideThesisState),
        decisions=tuple(SellSideDecision), trim_status=TrimAuthorizationStatus.TRIM_NOT_AUTHORIZED_V1,
        capital_efficiency_state=CapitalEfficiencyState.CAPITAL_INEFFICIENT,
        capital_efficiency_descriptive_only=True,
        rotation_authority="EXISTING_GOVERNED_CAPITAL_ROTATION_ENGINE",
        rotation_requirements=_ROTATION_REQUIREMENTS,
        exit_guards=(
            "CURRENT_EVIDENCE", "SUFFICIENT_EVIDENCE", "NO_MATERIAL_UNRESOLVED_CONFLICT",
            "INVALIDATED_THESIS", "NO_ELIGIBLE_GOVERNED_REPLACEMENT",
        ),
        review_required_conditions=_REVIEW_REQUIRED_CONDITIONS,
        hold_guards=(
            "INTACT_THESIS", "CURRENT_SUFFICIENT_EVIDENCE", "NO_GOVERNED_INVALIDATION",
            "NO_AUTHORIZED_RISK_REDUCTION", "NO_VALID_ROTATION",
        ),
        pnl_is_not_an_action_rule=True, priority_order=tuple(SellSidePriorityStage),
        trim_priority_enabled=False, forward_paper_descriptive_only=True,
        forward_paper_prohibited_effects=(
            "ALTER_THESIS_STATE", "AUTHORIZE_EXIT", "AUTHORIZE_ROTATE", "AUTHORIZE_TRIM",
            "ALTER_THRESHOLDS", "MUTATE_POLICY",
        ),
        provenance=(
            ("approval", "SELL_SIDE_POLICY_V1_HUMAN_APPROVAL"),
            ("proposal", "portfolio-sell-side-decision-policy/v1-proposed"),
            ("proposal_fingerprint", PROPOSAL_FINGERPRINT),
            ("scope", "PASSIVE_GOVERNANCE_ONLY_NO_ACTION_PRODUCER"),
        ),
    )
    return FrozenPortfolioSellSideDecisionPolicy(
        **values, fingerprint=manifest_fingerprint(**{key: _scalar(value) for key, value in values.items()}),
    )


CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY = create_frozen_portfolio_sell_side_decision_policy()


__all__ = (
    "CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY", "CapitalEfficiencyState",
    "FrozenPortfolioSellSideDecisionPolicy", "PROPOSAL_FINGERPRINT", "SellSideDecision",
    "SellSidePolicyApprovalStatus", "SellSidePriorityStage", "SellSideThesisState",
    "TrimAuthorizationStatus", "create_frozen_portfolio_sell_side_decision_policy",
    "portfolio_sell_side_policy_fingerprint",
)

