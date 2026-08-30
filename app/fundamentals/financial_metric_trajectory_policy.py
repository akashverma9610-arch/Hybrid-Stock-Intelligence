"""Frozen passive governance for a future factual financial trajectory builder.

No trajectory, pairing, arithmetic, persistence, or Brain integration is
implemented here.  This module records the approved v1 contract only.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class FinancialMetricTrajectoryPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialMetricTrajectoryBasis(StrEnum):
    SEQUENTIAL_QUARTER = "SEQUENTIAL_QUARTER"
    YEAR_OVER_YEAR_QUARTER = "YEAR_OVER_YEAR_QUARTER"
    YEAR_OVER_YEAR_ANNUAL = "YEAR_OVER_YEAR_ANNUAL"
    POINT_IN_TIME_SEQUENTIAL = "POINT_IN_TIME_SEQUENTIAL"


class FinancialMetricTrajectoryStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"
    NON_COMPARABLE = "NON_COMPARABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FinancialMetricNumericDomain(StrEnum):
    POSITIVE_PRIOR_BASE = "POSITIVE_PRIOR_BASE"
    ZERO_PRIOR_BASE = "ZERO_PRIOR_BASE"
    NEGATIVE_PRIOR_BASE = "NEGATIVE_PRIOR_BASE"
    SIGN_CROSSING = "SIGN_CROSSING"
    FINITE_VALID_DOMAIN = "FINITE_VALID_DOMAIN"


class FinancialMetricSignTransition(StrEnum):
    POSITIVE_TO_POSITIVE = "POSITIVE_TO_POSITIVE"
    POSITIVE_TO_ZERO = "POSITIVE_TO_ZERO"
    POSITIVE_TO_NEGATIVE = "POSITIVE_TO_NEGATIVE"
    ZERO_TO_POSITIVE = "ZERO_TO_POSITIVE"
    ZERO_TO_ZERO = "ZERO_TO_ZERO"
    ZERO_TO_NEGATIVE = "ZERO_TO_NEGATIVE"
    NEGATIVE_TO_POSITIVE = "NEGATIVE_TO_POSITIVE"
    NEGATIVE_TO_ZERO = "NEGATIVE_TO_ZERO"
    NEGATIVE_TO_NEGATIVE = "NEGATIVE_TO_NEGATIVE"


class FinancialMetricTrajectoryExclusion(StrEnum):
    TRAJECTORY_BUILDER = "TRAJECTORY_BUILDER"
    PAIRING_ENGINE = "PAIRING_ENGINE"
    BRAIN_OR_DELTA_CHANGE = "BRAIN_OR_DELTA_CHANGE"
    TTM_OR_CUMULATIVE_RECONSTRUCTION = "TTM_OR_CUMULATIVE_RECONSTRUCTION"
    MATERIALITY_OR_PERSISTENCE = "MATERIALITY_OR_PERSISTENCE"
    DIRECTIONALITY = "DIRECTIONALITY"
    THESIS_OR_OPPORTUNITY = "THESIS_OR_OPPORTUNITY"
    ALERT_RECOMMENDATION_OR_ACTION = "ALERT_RECOMMENDATION_OR_ACTION"
    PERSISTENCE_OR_RUNTIME = "PERSISTENCE_OR_RUNTIME"


@dataclass(frozen=True, slots=True)
class FrozenFinancialMetricTrajectoryPolicy:
    policy_id: str
    version: str
    proposal_version: str
    approval_status: FinancialMetricTrajectoryPolicyApprovalStatus
    approved_by: str
    selected: bool
    active: bool
    canonical_input: str
    same_knowledge_cutoff_required: bool
    same_period_revision_excluded: bool
    bases: tuple[FinancialMetricTrajectoryBasis, ...]
    complete_period_required: bool
    exact_representation_parity_required: bool
    fiscal_adjacency_required: bool
    q4_to_q1_metadata_proof_required: bool
    point_in_time_uses_period_end: bool
    cashflow_quarter_only_required: bool
    annual_cashflow_allowed: bool
    eps_share_basis_proof_required: bool
    absolute_delta_formula: str
    positive_prior_relative_delta_formula: str
    zero_or_negative_prior_relative_delta_unavailable: bool
    statuses: tuple[FinancialMetricTrajectoryStatus, ...]
    numeric_domains: tuple[FinancialMetricNumericDomain, ...]
    sign_transitions: tuple[FinancialMetricSignTransition, ...]
    exclusions: tuple[FinancialMetricTrajectoryExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.policy_id, self.version, self.proposal_version, self.approved_by, self.canonical_input)):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_REQUIRED_FIELD")
        if self.approval_status is not FinancialMetricTrajectoryPolicyApprovalStatus.APPROVED or not self.approved_by.startswith("human:"):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.selected or self.active:
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_MUST_NOT_BE_ACTIVE")
        if self.canonical_input != "FinancialResearchObservationBundle":
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_INPUT_REQUIRED")
        if self.bases != tuple(FinancialMetricTrajectoryBasis):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_BASES_REQUIRED")
        if not all((self.same_knowledge_cutoff_required, self.same_period_revision_excluded,
                    self.complete_period_required, self.exact_representation_parity_required,
                    self.fiscal_adjacency_required, self.q4_to_q1_metadata_proof_required,
                    self.point_in_time_uses_period_end, self.cashflow_quarter_only_required,
                    self.annual_cashflow_allowed, self.eps_share_basis_proof_required,
                    self.zero_or_negative_prior_relative_delta_unavailable)):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_SAFETY_RULE_REQUIRED")
        if self.absolute_delta_formula != "current_value - previous_value":
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_ABSOLUTE_FORMULA_REQUIRED")
        if self.positive_prior_relative_delta_formula != "(current_value - previous_value) / previous_value":
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_RELATIVE_FORMULA_REQUIRED")
        if self.statuses != tuple(FinancialMetricTrajectoryStatus) or self.numeric_domains != tuple(FinancialMetricNumericDomain) or self.sign_transitions != tuple(FinancialMetricSignTransition) or self.exclusions != tuple(FinancialMetricTrajectoryExclusion):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_VOCABULARY_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != financial_metric_trajectory_policy_fingerprint(self):
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_FINGERPRINT_MISMATCH")


def financial_metric_trajectory_policy_fingerprint(value: FrozenFinancialMetricTrajectoryPolicy) -> str:
    return _fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _fingerprint_values(values: dict) -> str:
    def scalar(item):
        if isinstance(item, StrEnum): return item.value
        if isinstance(item, tuple): return tuple(scalar(value) for value in item)
        return item
    return manifest_fingerprint(**{key: scalar(value) for key, value in values.items()})


def create_frozen_financial_metric_trajectory_policy() -> FrozenFinancialMetricTrajectoryPolicy:
    values = dict(
        policy_id="financial-metric-trajectory-policy", version="v1-approved", proposal_version="v1-proposed",
        approval_status=FinancialMetricTrajectoryPolicyApprovalStatus.APPROVED,
        approved_by="human:Akash-Verma", selected=False, active=False,
        canonical_input="FinancialResearchObservationBundle", same_knowledge_cutoff_required=True,
        same_period_revision_excluded=True, bases=tuple(FinancialMetricTrajectoryBasis),
        complete_period_required=True, exact_representation_parity_required=True,
        fiscal_adjacency_required=True, q4_to_q1_metadata_proof_required=True,
        point_in_time_uses_period_end=True, cashflow_quarter_only_required=True,
        annual_cashflow_allowed=True, eps_share_basis_proof_required=True,
        absolute_delta_formula="current_value - previous_value",
        positive_prior_relative_delta_formula="(current_value - previous_value) / previous_value",
        zero_or_negative_prior_relative_delta_unavailable=True,
        statuses=tuple(FinancialMetricTrajectoryStatus), numeric_domains=tuple(FinancialMetricNumericDomain),
        sign_transitions=tuple(FinancialMetricSignTransition), exclusions=tuple(FinancialMetricTrajectoryExclusion),
        provenance=(
            ("governance_approval", "U14D-6W"),
            ("proposal_policy", "financial-metric-trajectory-policy/v1-proposed"),
            ("readiness", "U14D-6V_READY_FOR_TRAJECTORY_GOVERNANCE"),
            ("scope", "PASSIVE_FACTUAL_PERIOD_TO_PERIOD_POLICY_ONLY"),
        ),
    )
    return FrozenFinancialMetricTrajectoryPolicy(**values, fingerprint=_fingerprint_values(values))


CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY = create_frozen_financial_metric_trajectory_policy()


__all__ = (
    "CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY", "FinancialMetricNumericDomain",
    "FinancialMetricSignTransition", "FinancialMetricTrajectoryBasis", "FinancialMetricTrajectoryExclusion",
    "FinancialMetricTrajectoryPolicyApprovalStatus", "FinancialMetricTrajectoryStatus",
    "FrozenFinancialMetricTrajectoryPolicy", "financial_metric_trajectory_policy_fingerprint",
)
