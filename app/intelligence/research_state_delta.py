"""Pure factual pairwise deltas for ``BrainResearchComparisonState``.

The module compares only explicitly supplied immutable state artifacts.  It
does not read stores, call providers, re-run research, or translate any factual
difference into thesis, opportunity, risk, recommendation, alert, gate, or
execution meaning.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    FrozenBrainResearchComparabilityPolicy,
    ResearchComparabilityDomain,
    ResearchComparabilityStatus,
    ResearchComparisonMode,
    ResearchSourceEligibility,
)
from app.intelligence.brain_research_comparison_state import (
    BrainResearchComparisonState,
    ResearchDimensionState,
    ResearchMetricObservation,
    ResearchMetricValueType,
    brain_research_comparison_state_fingerprint,
    research_metric_observation_fingerprint,
)
from app.intelligence.unified_state import IntelligenceEvidenceAvailability


class ResearchStateDeltaError(ValueError):
    """A foundational state/policy condition prevents factual comparison."""


class ResearchMetricChangeKind(StrEnum):
    UNCHANGED = "UNCHANGED"
    VALUE_CHANGED = "VALUE_CHANGED"
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    LINEAGE_CHANGED = "LINEAGE_CHANGED"
    METHODOLOGY_CHANGED = "METHODOLOGY_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    SOURCE_ELIGIBILITY_CHANGED = "SOURCE_ELIGIBILITY_CHANGED"


@dataclass(frozen=True, slots=True)
class ResearchMetricDelta:
    """One factual observation pairing, addition, or removal."""

    dimension: ResearchComparabilityDomain
    metric_id: str
    semantic_slot_fingerprint: str
    previous_observation: ResearchMetricObservation | None
    current_observation: ResearchMetricObservation | None
    previous_observation_fingerprint: str | None
    current_observation_fingerprint: str | None
    comparison_status: ResearchComparabilityStatus
    change_kind: ResearchMetricChangeKind
    reason_codes: tuple[str, ...]
    methodology_parity: bool | None
    dependency_parity: bool | None
    previous_source_eligibility: ResearchSourceEligibility | None
    current_source_eligibility: ResearchSourceEligibility | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.metric_id or not self.semantic_slot_fingerprint:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRIC_ID_REQUIRED")
        if self.previous_observation is None and self.current_observation is None:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRIC_PAIR_REQUIRED")
        if self.previous_observation is not None and self.previous_observation.dimension is not self.dimension:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_PREVIOUS_METRIC_DIMENSION_MISMATCH")
        if self.current_observation is not None and self.current_observation.dimension is not self.dimension:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_CURRENT_METRIC_DIMENSION_MISMATCH")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRIC_REASONS_NONCANONICAL")
        if self.fingerprint != research_metric_delta_fingerprint(self):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRIC_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class ResearchDimensionDelta:
    """Dimension-local factual comparability result."""

    dimension: ResearchComparabilityDomain
    previous_dimension_fingerprint: str
    current_dimension_fingerprint: str
    comparison_status: ResearchComparabilityStatus
    observation_deltas: tuple[ResearchMetricDelta, ...]
    reason_codes: tuple[str, ...]
    previous_methodology_lineage: tuple[tuple[str, str], ...]
    current_methodology_lineage: tuple[tuple[str, str], ...]
    previous_dependency_lineage: tuple[tuple[str, str], ...]
    current_dependency_lineage: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.previous_dimension_fingerprint or not self.current_dimension_fingerprint:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSION_LINEAGE_REQUIRED")
        if self.observation_deltas != tuple(sorted(self.observation_deltas, key=_metric_delta_key)):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRICS_NONCANONICAL")
        if any(value.dimension is not self.dimension for value in self.observation_deltas):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_METRIC_DIMENSION_MISMATCH")
        if self.reason_codes != tuple(sorted(set(self.reason_codes))):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSION_REASONS_NONCANONICAL")
        for value in (
            self.previous_methodology_lineage, self.current_methodology_lineage,
            self.previous_dependency_lineage, self.current_dependency_lineage,
        ):
            if value != tuple(sorted(set(value))):
                raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSION_LINEAGE_NONCANONICAL")
        if self.fingerprint != research_dimension_delta_fingerprint(self):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class ResearchStateDelta:
    """Immutable portfolio-independent factual comparison of two research states."""

    delta_id: str
    canonical_instrument_id: str
    previous_state_id: str
    previous_state_fingerprint: str
    previous_as_of: datetime
    current_state_id: str
    current_state_fingerprint: str
    current_as_of: datetime
    comparability_policy_id: str
    comparability_policy_version: str
    comparability_policy_fingerprint: str
    comparison_mode: ResearchComparisonMode
    dimension_deltas: tuple[ResearchDimensionDelta, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.delta_id, self.canonical_instrument_id, self.previous_state_id,
                    self.previous_state_fingerprint, self.current_state_id,
                    self.current_state_fingerprint, self.comparability_policy_id,
                    self.comparability_policy_version, self.comparability_policy_fingerprint)):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_REQUIRED_FIELD")
        _aware(self.previous_as_of, "PREVIOUS_AS_OF")
        _aware(self.current_as_of, "CURRENT_AS_OF")
        if self.previous_as_of >= self.current_as_of:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_CHRONOLOGY_REQUIRED")
        if self.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_COMPARISON_MODE_UNSUPPORTED")
        if self.dimension_deltas != tuple(sorted(self.dimension_deltas, key=lambda value: value.dimension.value)):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSIONS_NONCANONICAL")
        if tuple(value.dimension for value in self.dimension_deltas) != tuple(sorted(ResearchComparabilityDomain, key=lambda value: value.value)):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DIMENSION_COVERAGE_REQUIRED")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_BLOCKERS_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_WARNINGS_NONCANONICAL")
        if self.fingerprint != research_state_delta_fingerprint(self):
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_FINGERPRINT_MISMATCH")


def compare_brain_research_states(
    previous_state: BrainResearchComparisonState,
    current_state: BrainResearchComparisonState,
    *,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> ResearchStateDelta:
    """Compare two supplied factual research states; never query or execute work."""
    _validate_policy(policy)
    if _state_methodology_identity(previous_state) != _state_methodology_identity(current_state):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_CROSS_VERSION_NON_COMPARABLE")
    _validate_state(previous_state, policy)
    _validate_state(current_state, policy)
    if previous_state.canonical_instrument_id != current_state.canonical_instrument_id:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_INSTRUMENT_MISMATCH")
    if previous_state.as_of >= current_state.as_of:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_CHRONOLOGY_REQUIRED")
    if previous_state.comparison_mode is not current_state.comparison_mode:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_COMPARISON_MODE_MISMATCH")

    previous = {item.dimension: item for item in previous_state.dimensions}
    current = {item.dimension: item for item in current_state.dimensions}
    dimensions = tuple(
        _compare_dimension(domain, previous[domain], current[domain], policy)
        for domain in sorted(ResearchComparabilityDomain, key=lambda value: value.value)
    )
    blockers = tuple(sorted({
        reason for dimension in dimensions for reason in dimension.reason_codes
        if dimension.comparison_status in {
            ResearchComparabilityStatus.INSUFFICIENT,
            ResearchComparabilityStatus.NON_COMPARABLE,
        }
    }))
    warnings = tuple(sorted({
        "RESEARCH_STATE_DELTA_DIMENSION_LOCAL_LIMITATIONS"
        for dimension in dimensions
        if dimension.comparison_status is not ResearchComparabilityStatus.COMPARABLE
    }))
    values = dict(
        canonical_instrument_id=previous_state.canonical_instrument_id,
        previous_state_id=previous_state.state_id,
        previous_state_fingerprint=previous_state.fingerprint,
        previous_as_of=previous_state.as_of,
        current_state_id=current_state.state_id,
        current_state_fingerprint=current_state.fingerprint,
        current_as_of=current_state.as_of,
        comparability_policy_id=policy.policy_id,
        comparability_policy_version=policy.version,
        comparability_policy_fingerprint=policy.fingerprint,
        comparison_mode=policy.comparison_mode,
        dimension_deltas=dimensions,
        blockers=blockers,
        warnings=warnings,
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["delta_id"] = f"research-state-delta-{seed[:24]}"
    return ResearchStateDelta(**values, fingerprint=research_state_delta_fingerprint_values(values))


def _compare_dimension(
    domain: ResearchComparabilityDomain,
    previous: ResearchDimensionState,
    current: ResearchDimensionState,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> ResearchDimensionDelta:
    status, reasons = _dimension_status(previous, current)
    deltas = _compare_observations(domain, previous, current, status, policy)
    if status is ResearchComparabilityStatus.COMPARABLE and any(
        item.comparison_status is ResearchComparabilityStatus.NON_COMPARABLE for item in deltas
    ):
        status = ResearchComparabilityStatus.NON_COMPARABLE
        reasons.add("OBSERVATION_SEMANTIC_PARITY_UNPROVEN")
    values = dict(
        dimension=domain,
        previous_dimension_fingerprint=previous.fingerprint,
        current_dimension_fingerprint=current.fingerprint,
        comparison_status=status,
        observation_deltas=deltas,
        reason_codes=tuple(sorted(reasons)),
        previous_methodology_lineage=previous.methodology_lineage,
        current_methodology_lineage=current.methodology_lineage,
        previous_dependency_lineage=previous.dependency_lineage,
        current_dependency_lineage=current.dependency_lineage,
    )
    return ResearchDimensionDelta(**values, fingerprint=research_dimension_delta_fingerprint_values(values))


def _dimension_status(
    previous: ResearchDimensionState,
    current: ResearchDimensionState,
) -> tuple[ResearchComparabilityStatus, set[str]]:
    if previous.source_eligibility is ResearchSourceEligibility.UNSUPPORTED or current.source_eligibility is ResearchSourceEligibility.UNSUPPORTED:
        return ResearchComparabilityStatus.NOT_APPLICABLE, {"SOURCE_ELIGIBILITY_UNSUPPORTED"}
    if previous.source_eligibility is not current.source_eligibility:
        return ResearchComparabilityStatus.NON_COMPARABLE, {"SOURCE_ELIGIBILITY_CHANGED"}
    if previous.source_eligibility is ResearchSourceEligibility.CURRENT_ONLY:
        return ResearchComparabilityStatus.INSUFFICIENT, {"CURRENT_ONLY_HISTORICAL_COMPARISON_UNAUTHORIZED"}
    availability = {previous.availability, current.availability}
    if IntelligenceEvidenceAvailability.CONFLICTED in availability:
        return ResearchComparabilityStatus.NON_COMPARABLE, {"RELIABILITY_OR_INTEGRITY_CONFLICTED"}
    if IntelligenceEvidenceAvailability.STALE in availability:
        return ResearchComparabilityStatus.INSUFFICIENT, {"EVIDENCE_STALE"}
    if IntelligenceEvidenceAvailability.UNAVAILABLE in availability or IntelligenceEvidenceAvailability.PARTIAL in availability:
        return ResearchComparabilityStatus.INSUFFICIENT, {"REQUIRED_EVIDENCE_UNAVAILABLE"}
    if previous.methodology_lineage != current.methodology_lineage:
        return ResearchComparabilityStatus.NON_COMPARABLE, {"METHODOLOGY_LINEAGE_MISMATCH"}
    if previous.dependency_lineage != current.dependency_lineage:
        return ResearchComparabilityStatus.NON_COMPARABLE, {"DEPENDENCY_LINEAGE_MISMATCH"}
    return ResearchComparabilityStatus.COMPARABLE, set()


def _compare_observations(
    domain: ResearchComparabilityDomain,
    previous: ResearchDimensionState,
    current: ResearchDimensionState,
    dimension_status: ResearchComparabilityStatus,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> tuple[ResearchMetricDelta, ...]:
    old = _observations_by_slot(previous.observations)
    new = _observations_by_slot(current.observations)
    values: list[ResearchMetricDelta] = []
    for slot in sorted(set(old).union(new), key=_slot_fingerprint):
        old_value, new_value = old.get(slot), new.get(slot)
        metric_id = old_value.metric_id if old_value is not None else new_value.metric_id
        values.append(_metric_delta(domain, metric_id, old_value, new_value, dimension_status, slot, policy))
    return tuple(sorted(values, key=_metric_delta_key))


def _metric_delta(
    domain: ResearchComparabilityDomain,
    metric_id: str,
    previous: ResearchMetricObservation | None,
    current: ResearchMetricObservation | None,
    dimension_status: ResearchComparabilityStatus,
    slot: tuple,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> ResearchMetricDelta:
    if previous is None:
        status = ResearchComparabilityStatus.INSUFFICIENT if dimension_status is ResearchComparabilityStatus.COMPARABLE else dimension_status
        kind, reasons, method, dependency = ResearchMetricChangeKind.ADDED, {"OBSERVATION_ADDED"}, None, None
    elif current is None:
        status = ResearchComparabilityStatus.INSUFFICIENT if dimension_status is ResearchComparabilityStatus.COMPARABLE else dimension_status
        kind, reasons, method, dependency = ResearchMetricChangeKind.REMOVED, {"OBSERVATION_REMOVED"}, None, None
    else:
        status, kind, reasons, method, dependency = _paired_metric_result(
            previous, current, dimension_status, domain, policy,
        )
    values = dict(
        dimension=domain,
        metric_id=metric_id,
        semantic_slot_fingerprint=_slot_fingerprint(slot),
        previous_observation=previous,
        current_observation=current,
        previous_observation_fingerprint=_observation_fingerprint(previous),
        current_observation_fingerprint=_observation_fingerprint(current),
        comparison_status=status,
        change_kind=kind,
        reason_codes=tuple(sorted(reasons)),
        methodology_parity=method,
        dependency_parity=dependency,
        previous_source_eligibility=None if previous is None else previous.source_eligibility,
        current_source_eligibility=None if current is None else current.source_eligibility,
    )
    return ResearchMetricDelta(**values, fingerprint=research_metric_delta_fingerprint_values(values))


def _paired_metric_result(
    previous: ResearchMetricObservation,
    current: ResearchMetricObservation,
    dimension_status: ResearchComparabilityStatus,
    domain: ResearchComparabilityDomain,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> tuple[ResearchComparabilityStatus, ResearchMetricChangeKind, set[str], bool | None, bool | None]:
    methodology = (previous.methodology_id, previous.methodology_version) == (current.methodology_id, current.methodology_version)
    dependency = previous.dependency_manifest_fingerprint == current.dependency_manifest_fingerprint
    if previous.source_eligibility is not current.source_eligibility:
        return ResearchComparabilityStatus.NON_COMPARABLE, ResearchMetricChangeKind.SOURCE_ELIGIBILITY_CHANGED, {"SOURCE_ELIGIBILITY_CHANGED"}, methodology, dependency
    if dimension_status is not ResearchComparabilityStatus.COMPARABLE:
        return dimension_status, _limited_kind(previous, current), {"DIMENSION_COMPARISON_LIMITED"}, methodology, dependency
    if _partial_financial_period(domain, previous, current, policy):
        return ResearchComparabilityStatus.INSUFFICIENT, _limited_kind(previous, current), {"FINANCIAL_PARTIAL_PERIOD_NUMERIC_COMPARISON_INSUFFICIENT"}, methodology, dependency
    identity_changed = research_observation_slot_key(previous) != research_observation_slot_key(current)
    if not methodology:
        return ResearchComparabilityStatus.NON_COMPARABLE, ResearchMetricChangeKind.METHODOLOGY_CHANGED, {"METHODOLOGY_IDENTITY_MISMATCH"}, methodology, dependency
    if not dependency:
        return ResearchComparabilityStatus.NON_COMPARABLE, ResearchMetricChangeKind.DEPENDENCY_CHANGED, {"DEPENDENCY_MANIFEST_MISMATCH"}, methodology, dependency
    if identity_changed:
        return ResearchComparabilityStatus.NON_COMPARABLE, ResearchMetricChangeKind.LINEAGE_CHANGED, {"SEMANTIC_IDENTITY_MISMATCH"}, methodology, dependency
    if previous.value != current.value:
        return ResearchComparabilityStatus.COMPARABLE, ResearchMetricChangeKind.VALUE_CHANGED, (), methodology, dependency
    if _lineage_identity(previous) != _lineage_identity(current):
        return ResearchComparabilityStatus.COMPARABLE, ResearchMetricChangeKind.LINEAGE_CHANGED, {"SOURCE_LINEAGE_CHANGED"}, methodology, dependency
    return ResearchComparabilityStatus.COMPARABLE, ResearchMetricChangeKind.UNCHANGED, (), methodology, dependency


def _partial_financial_period(
    domain: ResearchComparabilityDomain,
    previous: ResearchMetricObservation,
    current: ResearchMetricObservation,
    policy: FrozenBrainResearchComparabilityPolicy,
) -> bool:
    """Apply the frozen v2 PARTIAL disposition without finance-specific pairing."""
    if domain is not ResearchComparabilityDomain.FINANCIAL_RAW or policy.financial_observation_rule is None:
        return False
    strengths = {
        dict(value.identity_components).get("financial_period_strength")
        for value in (previous, current)
    }
    return "PARTIAL" in strengths


def _limited_kind(previous: ResearchMetricObservation, current: ResearchMetricObservation) -> ResearchMetricChangeKind:
    if previous.source_eligibility is not current.source_eligibility:
        return ResearchMetricChangeKind.SOURCE_ELIGIBILITY_CHANGED
    if (previous.methodology_id, previous.methodology_version) != (current.methodology_id, current.methodology_version):
        return ResearchMetricChangeKind.METHODOLOGY_CHANGED
    if previous.dependency_manifest_fingerprint != current.dependency_manifest_fingerprint:
        return ResearchMetricChangeKind.DEPENDENCY_CHANGED
    return ResearchMetricChangeKind.LINEAGE_CHANGED if previous != current else ResearchMetricChangeKind.UNCHANGED


def _observations_by_slot(values: tuple[ResearchMetricObservation, ...]) -> dict[tuple, ResearchMetricObservation]:
    grouped: dict[tuple, ResearchMetricObservation] = {}
    for value in values:
        slot = research_observation_slot_key(value)
        if slot in grouped:
            raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_DUPLICATE_OBSERVATION_SLOT")
        grouped[slot] = value
    return grouped


def research_observation_slot_key(value: ResearchMetricObservation) -> tuple:
    """Deterministic generic slot identity; value and mutable lineage excluded.

    Methodology and dependency retain their existing role as pairwise parity
    checks. A changed methodology therefore becomes an explicit
    ``NON_COMPARABLE`` paired result instead of a metric-label fallback.
    """
    keys = tuple(key for key, _ in value.identity_components)
    if len(keys) != len(set(keys)):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_IDENTITY_COMPONENT_KEYS_DUPLICATE")
    return (
        value.dimension.value, value.metric_id, value.value_type.value,
        value.source_artifact_type, value.unit, value.scale, value.basis, value.scope,
        # Event/evidence timestamps and artifact fingerprints are lineage, not
        # observation-slot fields. Period identity remains explicit.
        value.period_identity, value.lookback_or_window, value.benchmark,
        # ``lineage_components`` is deliberately omitted: it records how an
        # artifact was sourced, not which factual observation slot it is.
        value.identity_components,
    )


def _lineage_identity(value: ResearchMetricObservation) -> tuple:
    return (
        value.value_type.value, value.source_artifact_type, value.source_artifact_fingerprint,
        value.dependency_manifest_fingerprint, value.freshness_status.value,
        value.reliability_lineage, value.historical_integrity_lineage,
        value.lineage_components, value.warnings, value.blockers,
    )


def _validate_policy(policy: FrozenBrainResearchComparabilityPolicy) -> None:
    if not isinstance(policy, FrozenBrainResearchComparabilityPolicy):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_POLICY_REQUIRED")
    approved = (
        CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
        FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    )
    if (policy.policy_id, policy.version, policy.fingerprint) not in {
        (value.policy_id, value.version, value.fingerprint) for value in approved
    }:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_POLICY_IDENTITY_INVALID")
    if policy.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_POLICY_MODE_UNSUPPORTED")
    if policy.selected_for_future_comparator or policy.active:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_POLICY_ACTIVATION_INVALID")


def _validate_state(value: BrainResearchComparisonState, policy: FrozenBrainResearchComparabilityPolicy) -> None:
    if not isinstance(value, BrainResearchComparisonState):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_STATE_REQUIRED")
    _aware(value.as_of, "STATE_AS_OF")
    if value.evaluation_session is not None:
        _aware(value.evaluation_session, "STATE_EVALUATION_SESSION")
    if not all((value.source_unified_state_id, value.source_unified_state_fingerprint,
                value.state_schema_version, value.research_methodology_id, value.research_methodology_version)):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_STATE_LINEAGE_INVALID")
    if value.fingerprint != brain_research_comparison_state_fingerprint(value):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_STATE_FINGERPRINT_INVALID")
    if (value.comparability_policy_id, value.comparability_policy_version, value.comparability_policy_fingerprint) != (
        policy.policy_id, policy.version, policy.fingerprint,
    ):
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_STATE_POLICY_MISMATCH")
    if value.comparison_mode is not policy.comparison_mode:
        raise ResearchStateDeltaError("RESEARCH_STATE_DELTA_COMPARISON_MODE_MISMATCH")


def _state_methodology_identity(value: BrainResearchComparisonState) -> tuple[str, str, str, str, str]:
    return (
        value.state_schema_version,
        value.research_methodology_id,
        value.research_methodology_version,
        value.comparability_policy_version,
        value.comparability_policy_fingerprint,
    )


def research_metric_delta_fingerprint(value: ResearchMetricDelta) -> str:
    return research_metric_delta_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def research_metric_delta_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def research_dimension_delta_fingerprint(value: ResearchDimensionDelta) -> str:
    return research_dimension_delta_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def research_dimension_delta_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def research_state_delta_fingerprint(value: ResearchStateDelta) -> str:
    return research_state_delta_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def research_state_delta_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({key: value for key, value in values.items() if key != "fingerprint"}))


def _observation_fingerprint(value: ResearchMetricObservation | None) -> str | None:
    if value is None:
        return None
    return research_metric_observation_fingerprint(value)


def _observation_key(value: ResearchMetricObservation) -> tuple:
    return research_observation_slot_key(value), value.source_artifact_fingerprint or "", repr(_semantic_value(value.value))


def _metric_delta_key(value: ResearchMetricDelta) -> tuple:
    return value.dimension.value, value.metric_id, value.semantic_slot_fingerprint, value.change_kind.value, value.previous_observation_fingerprint or "", value.current_observation_fingerprint or ""


def _slot_fingerprint(value: tuple) -> str:
    return manifest_fingerprint(slot=_semantic_value(value))


def _aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ResearchStateDeltaError(f"RESEARCH_STATE_DELTA_{name}_TIMEZONE_REQUIRED")


def _semantic_values(values: dict) -> dict:
    return {key: _semantic_value(value) for key, value in sorted(values.items())}


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if isinstance(value, ResearchMetricObservation):
        return {
            field: _semantic_value(getattr(value, field))
            for field in value.__dataclass_fields__
            if field != "lineage_components" or value.lineage_components
        }
    if hasattr(value, "__dataclass_fields__"):
        return {field: _semantic_value(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


__all__ = (
    "ResearchDimensionDelta", "ResearchMetricChangeKind", "ResearchMetricDelta",
    "ResearchStateDelta", "ResearchStateDeltaError", "compare_brain_research_states",
    "research_observation_slot_key",
    "research_dimension_delta_fingerprint", "research_metric_delta_fingerprint",
    "research_state_delta_fingerprint",
)
