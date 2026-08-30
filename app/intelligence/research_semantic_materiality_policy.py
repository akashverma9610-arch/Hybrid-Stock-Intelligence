"""Frozen passive governance for future metric-local semantic materiality.

This code-only policy names eligible directionality pairs and the evidence they
would require.  It deliberately contains neither thresholds nor a runtime
interpreter, and cannot classify any financial movement as material.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryBasis
from app.fundamentals.models import FinancialMetric
from app.historical.guard import manifest_fingerprint
from app.intelligence.research_metric_directionality import ResearchMetricDirectionalityOrientation


_TRAJECTORY_POLICY = (
    "financial-metric-trajectory-policy", "v1-approved",
    "15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7",
)
_DIRECTIONALITY_POLICY = (
    "research-metric-directionality-policy", "v1-approved",
    "0b4bcb46b00ec04c6c50610be0b5062237e39f2373e6df435ac788617db5a1dc",
)
_POLICY_IDENTITY = ("research-semantic-materiality-policy", "v1-approved")
_ELIGIBLE_METRICS = (
    FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT,
    FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC,
    FinancialMetric.EPS_DILUTED,
)
_ELIGIBLE_BASES = (
    FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER,
    FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL,
)
_ELIGIBLE_ORIENTATIONS = (
    ResearchMetricDirectionalityOrientation.POTENTIALLY_FAVORABLE,
    ResearchMetricDirectionalityOrientation.POTENTIALLY_UNFAVORABLE,
)
_NOT_APPLICABLE_ORIENTATIONS = (
    ResearchMetricDirectionalityOrientation.NO_DIRECTIONAL_CHANGE,
    ResearchMetricDirectionalityOrientation.CONTEXT_DEPENDENT,
    ResearchMetricDirectionalityOrientation.NON_DIRECTIONAL,
    ResearchMetricDirectionalityOrientation.NOT_APPLICABLE,
)


class ResearchSemanticMaterialityPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class ResearchMetricMaterialityMethodDisposition(StrEnum):
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"


class ResearchSemanticMaterialityResult(StrEnum):
    MATERIAL = "MATERIAL"
    IMMATERIAL = "IMMATERIAL"
    UNDETERMINED = "UNDETERMINED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ResearchMetricMaterialityRule:
    """Passive calibration requirement for one exact metric and basis pair."""

    metric: FinancialMetric
    basis: FinancialMetricTrajectoryBasis
    eligible_directionality_orientations: tuple[ResearchMetricDirectionalityOrientation, ...]
    method_disposition: ResearchMetricMaterialityMethodDisposition
    threshold_specification: None
    rationale_code: str
    required_trajectory_policy_id: str
    required_trajectory_policy_version: str
    required_trajectory_policy_fingerprint: str
    required_directionality_policy_id: str
    required_directionality_policy_version: str
    required_directionality_policy_fingerprint: str
    policy_id: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.metric, FinancialMetric) or not isinstance(self.basis, FinancialMetricTrajectoryBasis):
            raise ValueError("RESEARCH_MATERIALITY_RULE_TYPE_REQUIRED")
        if self.eligible_directionality_orientations != _ELIGIBLE_ORIENTATIONS:
            raise ValueError("RESEARCH_MATERIALITY_RULE_DIRECTIONALITY_ELIGIBILITY_REQUIRED")
        if self.method_disposition is not ResearchMetricMaterialityMethodDisposition.CALIBRATION_REQUIRED:
            raise ValueError("RESEARCH_MATERIALITY_RULE_CALIBRATION_REQUIRED")
        if self.threshold_specification is not None or not self.rationale_code:
            raise ValueError("RESEARCH_MATERIALITY_RULE_THRESHOLD_FORBIDDEN")
        if (self.required_trajectory_policy_id, self.required_trajectory_policy_version, self.required_trajectory_policy_fingerprint) != _TRAJECTORY_POLICY:
            raise ValueError("RESEARCH_MATERIALITY_RULE_TRAJECTORY_LINEAGE_REQUIRED")
        if (self.required_directionality_policy_id, self.required_directionality_policy_version, self.required_directionality_policy_fingerprint) != _DIRECTIONALITY_POLICY:
            raise ValueError("RESEARCH_MATERIALITY_RULE_DIRECTIONALITY_LINEAGE_REQUIRED")
        if (self.policy_id, self.policy_version) != _POLICY_IDENTITY:
            raise ValueError("RESEARCH_MATERIALITY_RULE_POLICY_IDENTITY_REQUIRED")
        if self.fingerprint != research_metric_materiality_rule_fingerprint(self):
            raise ValueError("RESEARCH_MATERIALITY_RULE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class ResearchSemanticMaterialityPolicy:
    """Approved but unselected calibration-gated materiality governance only."""

    policy_id: str
    version: str
    proposal_version: str
    approval_status: ResearchSemanticMaterialityPolicyApprovalStatus
    approved_by: str
    selected: bool
    active: bool
    required_trajectory_policy_id: str
    required_trajectory_policy_version: str
    required_trajectory_policy_fingerprint: str
    required_directionality_policy_id: str
    required_directionality_policy_version: str
    required_directionality_policy_fingerprint: str
    rules: tuple[ResearchMetricMaterialityRule, ...]
    not_applicable_orientations: tuple[ResearchMetricDirectionalityOrientation, ...]
    calibration_required_result: ResearchSemanticMaterialityResult
    not_applicable_result: ResearchSemanticMaterialityResult
    calibration_evidence_requirements: tuple[str, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (self.policy_id, self.version, self.proposal_version) != (*_POLICY_IDENTITY, "v1-proposed"):
            raise ValueError("RESEARCH_MATERIALITY_POLICY_IDENTITY_REQUIRED")
        if self.approval_status is not ResearchSemanticMaterialityPolicyApprovalStatus.APPROVED or self.approved_by != "human:Akash-Verma":
            raise ValueError("RESEARCH_MATERIALITY_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.selected or self.active:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_MUST_NOT_BE_ACTIVE")
        if (self.required_trajectory_policy_id, self.required_trajectory_policy_version, self.required_trajectory_policy_fingerprint) != _TRAJECTORY_POLICY:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_TRAJECTORY_LINEAGE_REQUIRED")
        if (self.required_directionality_policy_id, self.required_directionality_policy_version, self.required_directionality_policy_fingerprint) != _DIRECTIONALITY_POLICY:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_DIRECTIONALITY_LINEAGE_REQUIRED")
        expected = {(metric, basis) for metric in _ELIGIBLE_METRICS for basis in _ELIGIBLE_BASES}
        actual = {(rule.metric, rule.basis) for rule in self.rules}
        if len(self.rules) != len(actual) or actual != expected:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_EXACT_ELIGIBLE_MATRIX_REQUIRED")
        if self.rules != tuple(sorted(self.rules, key=lambda rule: (rule.metric.value, rule.basis.value))):
            raise ValueError("RESEARCH_MATERIALITY_POLICY_RULES_NONCANONICAL")
        if self.not_applicable_orientations != _NOT_APPLICABLE_ORIENTATIONS:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_NOT_APPLICABLE_ORIENTATIONS_REQUIRED")
        if self.calibration_required_result is not ResearchSemanticMaterialityResult.UNDETERMINED or self.not_applicable_result is not ResearchSemanticMaterialityResult.NOT_APPLICABLE:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_RESULT_SEMANTICS_REQUIRED")
        if self.calibration_evidence_requirements != tuple(sorted(set(self.calibration_evidence_requirements))) or not self.calibration_evidence_requirements:
            raise ValueError("RESEARCH_MATERIALITY_POLICY_CALIBRATION_EVIDENCE_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("RESEARCH_MATERIALITY_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != research_semantic_materiality_policy_fingerprint(self):
            raise ValueError("RESEARCH_MATERIALITY_POLICY_FINGERPRINT_MISMATCH")

    def rule_for(self, metric: FinancialMetric, basis: FinancialMetricTrajectoryBasis) -> ResearchMetricMaterialityRule:
        """Return policy metadata only; this module has no materiality evaluator."""
        return next(rule for rule in self.rules if rule.metric is metric and rule.basis is basis)


def create_research_semantic_materiality_policy() -> ResearchSemanticMaterialityPolicy:
    rules = tuple(sorted((_rule(metric, basis) for metric in _ELIGIBLE_METRICS for basis in _ELIGIBLE_BASES), key=lambda rule: (rule.metric.value, rule.basis.value)))
    values = dict(
        policy_id=_POLICY_IDENTITY[0], version=_POLICY_IDENTITY[1], proposal_version="v1-proposed",
        approval_status=ResearchSemanticMaterialityPolicyApprovalStatus.APPROVED,
        approved_by="human:Akash-Verma", selected=False, active=False,
        required_trajectory_policy_id=_TRAJECTORY_POLICY[0], required_trajectory_policy_version=_TRAJECTORY_POLICY[1],
        required_trajectory_policy_fingerprint=_TRAJECTORY_POLICY[2],
        required_directionality_policy_id=_DIRECTIONALITY_POLICY[0], required_directionality_policy_version=_DIRECTIONALITY_POLICY[1],
        required_directionality_policy_fingerprint=_DIRECTIONALITY_POLICY[2],
        rules=rules, not_applicable_orientations=_NOT_APPLICABLE_ORIENTATIONS,
        calibration_required_result=ResearchSemanticMaterialityResult.UNDETERMINED,
        not_applicable_result=ResearchSemanticMaterialityResult.NOT_APPLICABLE,
        calibration_evidence_requirements=tuple(sorted((
            "APPROVED_HUMAN_GOVERNANCE", "COMPANY_SCALE_EFFECTS", "EXACT_METRIC_AND_TRAJECTORY_BASIS",
            "FALSE_POSITIVE_NEGATIVE_TRADEOFF", "HISTORICAL_PIT_VALID_OBSERVATION_POPULATION",
            "METHODOLOGY_FINGERPRINT", "OUTLIER_POLICY", "REVISION_AND_RESTATEMENT_TREATMENT",
            "SAMPLE_PERIOD_AND_DISTRIBUTION_STATISTICS",
        ))),
        provenance=(
            ("directionality_readiness", "U14D-7B_READY_FOR_MATERIALITY_GOVERNANCE"),
            ("governance_approval", "U14D-7C"),
            ("proposal", "research-semantic-materiality-policy/v1-proposed"),
            ("scope", "PASSIVE_CALIBRATION_GATED_METRIC_LOCAL_MATERIALITY_POLICY_ONLY"),
        ),
    )
    return ResearchSemanticMaterialityPolicy(**values, fingerprint=_policy_fingerprint_values(values))


def research_metric_materiality_rule_fingerprint(value: ResearchMetricMaterialityRule) -> str:
    return _rule_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def research_semantic_materiality_policy_fingerprint(value: ResearchSemanticMaterialityPolicy) -> str:
    return _policy_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _rule(metric: FinancialMetric, basis: FinancialMetricTrajectoryBasis) -> ResearchMetricMaterialityRule:
    values = dict(
        metric=metric, basis=basis, eligible_directionality_orientations=_ELIGIBLE_ORIENTATIONS,
        method_disposition=ResearchMetricMaterialityMethodDisposition.CALIBRATION_REQUIRED,
        threshold_specification=None, rationale_code="NO_EMPIRICALLY_GOVERNED_MATERIALITY_CALIBRATION",
        required_trajectory_policy_id=_TRAJECTORY_POLICY[0], required_trajectory_policy_version=_TRAJECTORY_POLICY[1],
        required_trajectory_policy_fingerprint=_TRAJECTORY_POLICY[2],
        required_directionality_policy_id=_DIRECTIONALITY_POLICY[0], required_directionality_policy_version=_DIRECTIONALITY_POLICY[1],
        required_directionality_policy_fingerprint=_DIRECTIONALITY_POLICY[2],
        policy_id=_POLICY_IDENTITY[0], policy_version=_POLICY_IDENTITY[1],
    )
    return ResearchMetricMaterialityRule(**values, fingerprint=_rule_fingerprint_values(values))


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


CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY = create_research_semantic_materiality_policy()


__all__ = (
    "CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY", "ResearchMetricMaterialityMethodDisposition",
    "ResearchMetricMaterialityRule", "ResearchSemanticMaterialityPolicy",
    "ResearchSemanticMaterialityPolicyApprovalStatus", "ResearchSemanticMaterialityResult",
    "create_research_semantic_materiality_policy", "research_metric_materiality_rule_fingerprint",
    "research_semantic_materiality_policy_fingerprint",
)
