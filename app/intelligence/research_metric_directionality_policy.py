"""Frozen passive governance for future financial metric directionality.

This module is a complete metric-by-trajectory-basis policy registry only. It
does not interpret a trajectory or access facts, bundles, stores, providers,
Brain state, scores, or runtime services.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryBasis
from app.fundamentals.models import FinancialMetric
from app.historical.guard import manifest_fingerprint


_TRAJECTORY_POLICY = (
    "financial-metric-trajectory-policy", "v1-approved",
    "15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7",
)


class ResearchMetricDirectionalityPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class ResearchMetricDirectionalityDisposition(StrEnum):
    HIGHER_POTENTIALLY_FAVORABLE = "HIGHER_POTENTIALLY_FAVORABLE"
    LOWER_POTENTIALLY_FAVORABLE = "LOWER_POTENTIALLY_FAVORABLE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    NON_DIRECTIONAL = "NON_DIRECTIONAL"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ResearchMetricDirectionalityRule:
    """Passive policy mapping; it deliberately has no evaluation method."""

    metric: FinancialMetric
    basis: FinancialMetricTrajectoryBasis
    disposition: ResearchMetricDirectionalityDisposition
    rationale_code: str
    required_trajectory_policy_id: str
    required_trajectory_policy_version: str
    required_trajectory_policy_fingerprint: str
    policy_id: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.rationale_code or (self.required_trajectory_policy_id, self.required_trajectory_policy_version, self.required_trajectory_policy_fingerprint) != _TRAJECTORY_POLICY:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_RULE_LINEAGE_REQUIRED")
        if (self.policy_id, self.policy_version) != ("research-metric-directionality-policy", "v1-approved"):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_RULE_POLICY_IDENTITY_REQUIRED")
        if self.fingerprint != research_metric_directionality_rule_fingerprint(self):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_RULE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class ResearchMetricDirectionalityPolicy:
    policy_id: str
    version: str
    proposal_version: str
    approval_status: ResearchMetricDirectionalityPolicyApprovalStatus
    approved_by: str
    selected: bool
    active: bool
    required_trajectory_policy_id: str
    required_trajectory_policy_version: str
    required_trajectory_policy_fingerprint: str
    rules: tuple[ResearchMetricDirectionalityRule, ...]
    unsupported_derived_metrics: tuple[str, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (self.policy_id, self.version, self.proposal_version) != ("research-metric-directionality-policy", "v1-approved", "v1-proposed"):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_IDENTITY_REQUIRED")
        if self.approval_status is not ResearchMetricDirectionalityPolicyApprovalStatus.APPROVED or self.approved_by != "human:Akash-Verma":
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.selected or self.active:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_MUST_NOT_BE_ACTIVE")
        if (self.required_trajectory_policy_id, self.required_trajectory_policy_version, self.required_trajectory_policy_fingerprint) != _TRAJECTORY_POLICY:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_TRAJECTORY_LINEAGE_REQUIRED")
        expected = {(metric, basis) for metric in FinancialMetric for basis in FinancialMetricTrajectoryBasis}
        actual = {(rule.metric, rule.basis) for rule in self.rules}
        if len(self.rules) != len(actual) or actual != expected:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_COMPLETE_MATRIX_REQUIRED")
        if self.rules != tuple(sorted(self.rules, key=lambda rule: (rule.metric.value, rule.basis.value))):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_RULES_NONCANONICAL")
        if self.unsupported_derived_metrics != tuple(sorted(set(self.unsupported_derived_metrics))):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_UNSUPPORTED_NONCANONICAL")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != research_metric_directionality_policy_fingerprint(self):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_FINGERPRINT_MISMATCH")

    def rule_for(self, metric: FinancialMetric, basis: FinancialMetricTrajectoryBasis) -> ResearchMetricDirectionalityRule:
        """Return policy metadata only; this is not a runtime interpreter."""
        return next(rule for rule in self.rules if rule.metric is metric and rule.basis is basis)


_STOCK_METRICS = frozenset({
    FinancialMetric.TOTAL_ASSETS, FinancialMetric.TOTAL_LIABILITIES,
    FinancialMetric.TOTAL_EQUITY, FinancialMetric.NET_WORTH,
    FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS,
    FinancialMetric.CURRENT_ASSETS, FinancialMetric.CURRENT_LIABILITIES,
    FinancialMetric.INVENTORY, FinancialMetric.RECEIVABLES,
    FinancialMetric.PAYABLES, FinancialMetric.SHARES_OUTSTANDING,
    FinancialMetric.FACE_VALUE,
})
_HIGHER_YOY_METRICS = frozenset({
    FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT,
    FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC,
    FinancialMetric.EPS_DILUTED,
})
_NON_DIRECTIONAL_FLOW_METRICS = frozenset({FinancialMetric.CFI, FinancialMetric.CFF})
_NON_DIRECTIONAL_STOCK_METRICS = frozenset({FinancialMetric.SHARES_OUTSTANDING, FinancialMetric.FACE_VALUE})


def create_research_metric_directionality_policy() -> ResearchMetricDirectionalityPolicy:
    rules = tuple(sorted((_rule(metric, basis) for metric in FinancialMetric for basis in FinancialMetricTrajectoryBasis), key=lambda rule: (rule.metric.value, rule.basis.value)))
    values = dict(
        policy_id="research-metric-directionality-policy", version="v1-approved", proposal_version="v1-proposed",
        approval_status=ResearchMetricDirectionalityPolicyApprovalStatus.APPROVED,
        approved_by="human:Akash-Verma", selected=False, active=False,
        required_trajectory_policy_id=_TRAJECTORY_POLICY[0], required_trajectory_policy_version=_TRAJECTORY_POLICY[1],
        required_trajectory_policy_fingerprint=_TRAJECTORY_POLICY[2], rules=rules,
        unsupported_derived_metrics=("CAGR", "DEBT_TO_EQUITY", "EBITDA_MARGIN", "EBIT_MARGIN", "INTEREST_COVERAGE", "PAT_MARGIN", "PEG", "ROCE", "ROE"),
        provenance=(
            ("factual_prerequisite", "U14D-6W-U14D-6Y_FINANCIAL_TRAJECTORY_VALIDATED"),
            ("governance_approval", "U14D-6Z"),
            ("proposal", "research-metric-directionality-policy/v1-proposed"),
            ("scope", "PASSIVE_METRIC_LOCAL_DIRECTIONALITY_POLICY_ONLY"),
        ),
    )
    return ResearchMetricDirectionalityPolicy(**values, fingerprint=_policy_fingerprint_values(values))


def research_metric_directionality_rule_fingerprint(value: ResearchMetricDirectionalityRule) -> str:
    return _rule_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def research_metric_directionality_policy_fingerprint(value: ResearchMetricDirectionalityPolicy) -> str:
    return _policy_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _rule(metric: FinancialMetric, basis: FinancialMetricTrajectoryBasis) -> ResearchMetricDirectionalityRule:
    disposition, rationale = _disposition(metric, basis)
    values = dict(metric=metric, basis=basis, disposition=disposition, rationale_code=rationale,
                  required_trajectory_policy_id=_TRAJECTORY_POLICY[0], required_trajectory_policy_version=_TRAJECTORY_POLICY[1],
                  required_trajectory_policy_fingerprint=_TRAJECTORY_POLICY[2],
                  policy_id="research-metric-directionality-policy", policy_version="v1-approved")
    return ResearchMetricDirectionalityRule(**values, fingerprint=_rule_fingerprint_values(values))


def _disposition(metric: FinancialMetric, basis: FinancialMetricTrajectoryBasis) -> tuple[ResearchMetricDirectionalityDisposition, str]:
    if metric in _STOCK_METRICS:
        if basis is not FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL:
            return ResearchMetricDirectionalityDisposition.NOT_APPLICABLE, "STOCK_METRIC_REQUIRES_POINT_IN_TIME_TRAJECTORY"
        if metric in _NON_DIRECTIONAL_STOCK_METRICS:
            return ResearchMetricDirectionalityDisposition.NON_DIRECTIONAL, "CORPORATE_ACTION_OR_DENOMINATOR_REPRESENTATION"
        return ResearchMetricDirectionalityDisposition.CONTEXT_DEPENDENT, "BALANCE_SHEET_MOVEMENT_REQUIRES_CONTEXT"
    if basis is FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL:
        return ResearchMetricDirectionalityDisposition.NOT_APPLICABLE, "FLOW_METRIC_REQUIRES_FLOW_TRAJECTORY"
    if basis is FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER:
        if metric in _NON_DIRECTIONAL_FLOW_METRICS:
            return ResearchMetricDirectionalityDisposition.NON_DIRECTIONAL, "RAW_INVESTING_OR_FINANCING_CASHFLOW_NON_DIRECTIONAL"
        return ResearchMetricDirectionalityDisposition.CONTEXT_DEPENDENT, "SEASONALITY_NOT_GOVERNED"
    if metric in _HIGHER_YOY_METRICS:
        return ResearchMetricDirectionalityDisposition.HIGHER_POTENTIALLY_FAVORABLE, "COMPARABLE_OPERATING_OR_EARNINGS_TRAJECTORY"
    if metric in _NON_DIRECTIONAL_FLOW_METRICS:
        return ResearchMetricDirectionalityDisposition.NON_DIRECTIONAL, "RAW_INVESTING_OR_FINANCING_CASHFLOW_NON_DIRECTIONAL"
    return ResearchMetricDirectionalityDisposition.CONTEXT_DEPENDENT, "METRIC_LOCAL_CONTEXT_REQUIRED"


def _rule_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**{key: _convert(value) for key, value in values.items()})


def _policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**{key: _convert(value) for key, value in values.items()})


def _convert(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, tuple):
        return tuple(_convert(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field: _convert(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY = create_research_metric_directionality_policy()


__all__ = (
    "CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY",
    "ResearchMetricDirectionalityDisposition", "ResearchMetricDirectionalityPolicy",
    "ResearchMetricDirectionalityPolicyApprovalStatus", "ResearchMetricDirectionalityRule",
    "create_research_metric_directionality_policy", "research_metric_directionality_policy_fingerprint",
    "research_metric_directionality_rule_fingerprint",
)
