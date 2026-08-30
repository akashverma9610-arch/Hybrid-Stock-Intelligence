"""Pure metric-local orientation for one governed financial trajectory.

The explicit policy supplied by the caller is the sole rule source. This module
does not build trajectories, access upstream artifacts, or invoke any runtime,
Brain, score, persistence, provider, or action capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectory,
    financial_metric_trajectory_fingerprint,
)
from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.research_metric_directionality_policy import (
    ResearchMetricDirectionalityDisposition,
    ResearchMetricDirectionalityPolicy,
    ResearchMetricDirectionalityRule,
    research_metric_directionality_policy_fingerprint,
    research_metric_directionality_rule_fingerprint,
)


_DIRECTIONALITY_POLICY = (
    "research-metric-directionality-policy", "v1-approved",
    "0b4bcb46b00ec04c6c50610be0b5062237e39f2373e6df435ac788617db5a1dc",
)
_TRAJECTORY_POLICY = (
    "financial-metric-trajectory-policy", "v1-approved",
    "15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7",
)


class ResearchMetricDirectionalityOrientation(StrEnum):
    POTENTIALLY_FAVORABLE = "POTENTIALLY_FAVORABLE"
    POTENTIALLY_UNFAVORABLE = "POTENTIALLY_UNFAVORABLE"
    NO_DIRECTIONAL_CHANGE = "NO_DIRECTIONAL_CHANGE"
    CONTEXT_DEPENDENT = "CONTEXT_DEPENDENT"
    NON_DIRECTIONAL = "NON_DIRECTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class ResearchMetricDirectionalityInterpretation:
    """Immutable metric-local result; it has no thesis or action semantics."""

    canonical_instrument_id: str
    as_of: datetime
    metric: str
    trajectory_basis: str
    source_trajectory_fingerprint: str
    source_trajectory_policy_id: str
    source_trajectory_policy_version: str
    source_trajectory_policy_fingerprint: str
    directionality_policy_id: str
    directionality_policy_version: str
    directionality_policy_fingerprint: str
    rule_fingerprint: str
    disposition: ResearchMetricDirectionalityDisposition
    orientation: ResearchMetricDirectionalityOrientation
    rationale_code: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.canonical_instrument_id, self.metric, self.trajectory_basis, self.source_trajectory_fingerprint, self.rule_fingerprint, self.rationale_code)) or not _aware(self.as_of):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_INTERPRETATION_REQUIRED_FIELD")
        if (self.source_trajectory_policy_id, self.source_trajectory_policy_version, self.source_trajectory_policy_fingerprint) != _TRAJECTORY_POLICY:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_INTERPRETATION_TRAJECTORY_LINEAGE_REQUIRED")
        if (self.directionality_policy_id, self.directionality_policy_version, self.directionality_policy_fingerprint) != _DIRECTIONALITY_POLICY:
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_INTERPRETATION_POLICY_LINEAGE_REQUIRED")
        if self.fingerprint != research_metric_directionality_interpretation_fingerprint(self):
            raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_INTERPRETATION_FINGERPRINT_MISMATCH")


def interpret_research_metric_directionality(
    trajectory: FinancialMetricTrajectory,
    *,
    policy: ResearchMetricDirectionalityPolicy,
) -> ResearchMetricDirectionalityInterpretation:
    """Map one AVAILABLE trajectory using one explicit frozen policy only."""
    _require_trajectory(trajectory)
    _require_policy(policy)
    rule = _exact_rule(policy, trajectory)
    orientation = _orientation(rule, trajectory)
    values = dict(
        canonical_instrument_id=trajectory.canonical_instrument_id, as_of=trajectory.bundle_as_of,
        metric=trajectory.metric.value, trajectory_basis=trajectory.basis.value,
        source_trajectory_fingerprint=trajectory.fingerprint,
        source_trajectory_policy_id=trajectory.policy_id,
        source_trajectory_policy_version=trajectory.policy_version,
        source_trajectory_policy_fingerprint=trajectory.policy_fingerprint,
        directionality_policy_id=policy.policy_id,
        directionality_policy_version=policy.version,
        directionality_policy_fingerprint=policy.fingerprint,
        rule_fingerprint=rule.fingerprint, disposition=rule.disposition,
        orientation=orientation, rationale_code=rule.rationale_code,
    )
    return ResearchMetricDirectionalityInterpretation(
        **values, fingerprint=_interpretation_fingerprint_values(values),
    )


def research_metric_directionality_interpretation_fingerprint(value: ResearchMetricDirectionalityInterpretation) -> str:
    return _interpretation_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _require_trajectory(trajectory: FinancialMetricTrajectory) -> None:
    if not isinstance(trajectory, FinancialMetricTrajectory):
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_TRAJECTORY_REQUIRED")
    if financial_metric_trajectory_fingerprint(trajectory) != trajectory.fingerprint:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_TRAJECTORY_TAMPERED")
    if trajectory.status is not FinancialMetricTrajectoryStatus.AVAILABLE:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_AVAILABLE_TRAJECTORY_REQUIRED")
    if (trajectory.policy_id, trajectory.policy_version, trajectory.policy_fingerprint) != _TRAJECTORY_POLICY:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_TRAJECTORY_POLICY_REQUIRED")


def _require_policy(policy: ResearchMetricDirectionalityPolicy) -> None:
    if not isinstance(policy, ResearchMetricDirectionalityPolicy):
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_REQUIRED")
    if research_metric_directionality_policy_fingerprint(policy) != policy.fingerprint:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_POLICY_TAMPERED")
    if (policy.policy_id, policy.version, policy.fingerprint) != _DIRECTIONALITY_POLICY:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_EXACT_POLICY_REQUIRED")


def _exact_rule(policy: ResearchMetricDirectionalityPolicy, trajectory: FinancialMetricTrajectory) -> ResearchMetricDirectionalityRule:
    rules = tuple(rule for rule in policy.rules if rule.metric is trajectory.metric and rule.basis is trajectory.basis)
    if len(rules) != 1:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_EXACT_RULE_REQUIRED")
    rule = rules[0]
    if research_metric_directionality_rule_fingerprint(rule) != rule.fingerprint:
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_RULE_TAMPERED")
    if (rule.required_trajectory_policy_id, rule.required_trajectory_policy_version, rule.required_trajectory_policy_fingerprint) != (trajectory.policy_id, trajectory.policy_version, trajectory.policy_fingerprint):
        raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_RULE_TRAJECTORY_CONTRADICTION")
    return rule


def _orientation(rule: ResearchMetricDirectionalityRule, trajectory: FinancialMetricTrajectory) -> ResearchMetricDirectionalityOrientation:
    if rule.disposition is ResearchMetricDirectionalityDisposition.CONTEXT_DEPENDENT:
        return ResearchMetricDirectionalityOrientation.CONTEXT_DEPENDENT
    if rule.disposition is ResearchMetricDirectionalityDisposition.NON_DIRECTIONAL:
        return ResearchMetricDirectionalityOrientation.NON_DIRECTIONAL
    if rule.disposition in {ResearchMetricDirectionalityDisposition.NOT_APPLICABLE, ResearchMetricDirectionalityDisposition.UNSUPPORTED}:
        return ResearchMetricDirectionalityOrientation.NOT_APPLICABLE
    assert trajectory.absolute_delta is not None
    if trajectory.absolute_delta == 0:
        return ResearchMetricDirectionalityOrientation.NO_DIRECTIONAL_CHANGE
    if rule.disposition is ResearchMetricDirectionalityDisposition.HIGHER_POTENTIALLY_FAVORABLE:
        return ResearchMetricDirectionalityOrientation.POTENTIALLY_FAVORABLE if trajectory.absolute_delta > 0 else ResearchMetricDirectionalityOrientation.POTENTIALLY_UNFAVORABLE
    if rule.disposition is ResearchMetricDirectionalityDisposition.LOWER_POTENTIALLY_FAVORABLE:
        return ResearchMetricDirectionalityOrientation.POTENTIALLY_FAVORABLE if trajectory.absolute_delta < 0 else ResearchMetricDirectionalityOrientation.POTENTIALLY_UNFAVORABLE
    raise ValueError("RESEARCH_METRIC_DIRECTIONALITY_DISPOSITION_UNSUPPORTED")


def _interpretation_fingerprint_values(values: dict) -> str:
    def convert(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        return value
    return manifest_fingerprint(**{key: convert(value) for key, value in values.items()})


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "ResearchMetricDirectionalityInterpretation", "ResearchMetricDirectionalityOrientation",
    "interpret_research_metric_directionality", "research_metric_directionality_interpretation_fingerprint",
)
