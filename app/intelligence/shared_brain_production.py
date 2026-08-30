"""Pure Production-v1 assembly of the existing one Shared Brain.

The module composes validated artifacts only.  It neither reads stores nor
providers, derives a thesis, evaluates materiality, changes a score, or creates
an action.  All trajectory arithmetic and metric-local orientation are reused
from their frozen upstream builders.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.fundamentals.financial_metric_observation_schema import FinancialMetricPeriodIdentityStrength
from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectory,
    FinancialMetricTrajectoryRequest,
    build_financial_metric_trajectory,
    financial_metric_trajectory_fingerprint,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY,
    FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus,
    FrozenFinancialMetricTrajectoryPolicy,
    financial_metric_trajectory_policy_fingerprint,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    FinancialResearchInputFailure,
    FinancialResearchObservationBundle,
    financial_research_input_failure_fingerprint,
    financial_research_observation_bundle_fingerprint,
)
from app.fundamentals.models import FinancialMetric, FinancialPeriodType, FinancialValueBasis
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import FrozenBrainResearchComparabilityPolicy
from app.intelligence.brain_research_comparison_state import BrainResearchComparisonState, ResearchMetricObservation
from app.intelligence.brain_research_comparison_state_v2 import build_brain_research_comparison_state_v2
from app.intelligence.research_metric_directionality import (
    ResearchMetricDirectionalityInterpretation,
    interpret_research_metric_directionality,
    research_metric_directionality_interpretation_fingerprint,
)
from app.intelligence.research_metric_directionality_policy import (
    CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY,
    ResearchMetricDirectionalityPolicy,
    research_metric_directionality_policy_fingerprint,
)
from app.intelligence.research_semantic_materiality_policy import (
    CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY,
    ResearchSemanticMaterialityPolicy,
    research_semantic_materiality_policy_fingerprint,
)
from app.intelligence.unified_state import BrainOutputContext, UnifiedIntelligenceState


class SharedBrainMaterialityCalibrationStatus(StrEnum):
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


@dataclass(frozen=True, slots=True)
class SharedBrainProductionSnapshot:
    """One immutable, rebuildable production view of the existing Shared Brain."""

    canonical_instrument_id: str
    as_of: datetime
    unified_state: UnifiedIntelligenceState
    brain_research_state_v2: BrainResearchComparisonState
    financial_bundle: FinancialResearchObservationBundle
    financial_failures: tuple[FinancialResearchInputFailure, ...]
    financial_trajectories: tuple[FinancialMetricTrajectory, ...]
    directionality_interpretations: tuple[ResearchMetricDirectionalityInterpretation, ...]
    trajectory_policy_id: str
    trajectory_policy_version: str
    trajectory_policy_fingerprint: str
    directionality_policy_id: str
    directionality_policy_version: str
    directionality_policy_fingerprint: str
    materiality_policy_id: str
    materiality_policy_version: str
    materiality_policy_fingerprint: str
    materiality_calibration_status: SharedBrainMaterialityCalibrationStatus
    dependency_manifest: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.as_of):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_SCOPE_REQUIRED")
        if self.unified_state.canonical_instrument_id != self.canonical_instrument_id or self.unified_state.as_of != self.as_of:
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_UNIFIED_STATE_MISMATCH")
        brain = self.brain_research_state_v2
        if (brain.canonical_instrument_id, brain.as_of, brain.source_unified_state_fingerprint) != (
            self.canonical_instrument_id, self.as_of, self.unified_state.fingerprint,
        ):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_BRAIN_V2_MISMATCH")
        if (self.financial_bundle.canonical_instrument_id, self.financial_bundle.as_of) != (self.canonical_instrument_id, self.as_of):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_FINANCIAL_BUNDLE_MISMATCH")
        if self.financial_failures != self.financial_bundle.failures:
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_FAILURE_BINDING_INVALID")
        if self.financial_trajectories != tuple(sorted(self.financial_trajectories, key=_trajectory_key)):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_TRAJECTORIES_NONCANONICAL")
        if self.directionality_interpretations != tuple(sorted(self.directionality_interpretations, key=_directionality_key)):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_DIRECTIONALITY_NONCANONICAL")
        if (self.trajectory_policy_id, self.trajectory_policy_version, self.trajectory_policy_fingerprint) != _trajectory_identity():
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_TRAJECTORY_POLICY_REQUIRED")
        if (self.directionality_policy_id, self.directionality_policy_version, self.directionality_policy_fingerprint) != _directionality_identity():
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_DIRECTIONALITY_POLICY_REQUIRED")
        if (self.materiality_policy_id, self.materiality_policy_version, self.materiality_policy_fingerprint) != _materiality_identity():
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_MATERIALITY_POLICY_REQUIRED")
        if self.materiality_calibration_status is not SharedBrainMaterialityCalibrationStatus.CALIBRATION_REQUIRED:
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_MATERIALITY_STATUS_REQUIRED")
        if self.dependency_manifest != tuple(sorted(set(self.dependency_manifest))):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_DEPENDENCIES_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_WARNINGS_NONCANONICAL")
        trajectory_by_fingerprint = {value.fingerprint: value for value in self.financial_trajectories}
        for value in self.financial_trajectories:
            if financial_metric_trajectory_fingerprint(value) != value.fingerprint:
                raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_TRAJECTORY_TAMPERED")
            if (value.canonical_instrument_id, value.bundle_as_of) != (self.canonical_instrument_id, self.as_of):
                raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_TRAJECTORY_SCOPE_MISMATCH")
        for value in self.directionality_interpretations:
            if research_metric_directionality_interpretation_fingerprint(value) != value.fingerprint:
                raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_DIRECTIONALITY_TAMPERED")
            trajectory = trajectory_by_fingerprint.get(value.source_trajectory_fingerprint)
            if trajectory is None or trajectory.status is not FinancialMetricTrajectoryStatus.AVAILABLE:
                raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_DIRECTIONALITY_BINDING_INVALID")
        if self.fingerprint != shared_brain_production_snapshot_fingerprint(self):
            raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class SharedBrainProductionContextProjection:
    """One read-only context view referencing the same production snapshot."""

    canonical_instrument_id: str
    as_of: datetime
    output_context: BrainOutputContext
    shared_brain_snapshot_fingerprint: str
    unified_state_fingerprint: str
    brain_research_state_v2_fingerprint: str
    financial_semantic_section_fingerprint: str
    trajectory_fingerprints: tuple[str, ...]
    directionality_fingerprints: tuple[str, ...]
    financial_failure_fingerprints: tuple[str, ...]
    materiality_calibration_status: SharedBrainMaterialityCalibrationStatus
    materiality_policy_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.canonical_instrument_id, self.shared_brain_snapshot_fingerprint, self.unified_state_fingerprint, self.brain_research_state_v2_fingerprint, self.financial_semantic_section_fingerprint, self.materiality_policy_fingerprint)) or not _aware(self.as_of):
            raise ValueError("SHARED_BRAIN_PRODUCTION_CONTEXT_REQUIRED_FIELD")
        for values, code in (
            (self.trajectory_fingerprints, "TRAJECTORIES"),
            (self.directionality_fingerprints, "DIRECTIONALITY"),
            (self.financial_failure_fingerprints, "FAILURES"),
        ):
            if values != tuple(sorted(set(values))):
                raise ValueError(f"SHARED_BRAIN_PRODUCTION_CONTEXT_{code}_NONCANONICAL")
        if self.materiality_calibration_status is not SharedBrainMaterialityCalibrationStatus.CALIBRATION_REQUIRED:
            raise ValueError("SHARED_BRAIN_PRODUCTION_CONTEXT_MATERIALITY_REQUIRED")
        if self.fingerprint != shared_brain_production_context_projection_fingerprint(self):
            raise ValueError("SHARED_BRAIN_PRODUCTION_CONTEXT_FINGERPRINT_MISMATCH")


def build_shared_brain_production_snapshot(
    unified_state: UnifiedIntelligenceState,
    *,
    comparability_policy: FrozenBrainResearchComparabilityPolicy,
    financial_bundle: FinancialResearchObservationBundle,
    financial_wrappers: tuple[ResearchMetricObservation, ...],
    financial_failures: tuple[FinancialResearchInputFailure, ...],
    trajectory_policy: FrozenFinancialMetricTrajectoryPolicy,
    directionality_policy: ResearchMetricDirectionalityPolicy,
    materiality_policy: ResearchSemanticMaterialityPolicy,
) -> SharedBrainProductionSnapshot:
    """Compose one exact-as-of shared snapshot from supplied immutable inputs."""
    _validate_policies(trajectory_policy, directionality_policy, materiality_policy)
    brain = build_brain_research_comparison_state_v2(
        unified_state,
        comparability_policy=comparability_policy,
        financial_bundle=financial_bundle,
        financial_wrappers=financial_wrappers,
        financial_failures=financial_bundle.failures,
    )
    requests = enumerate_financial_trajectory_requests(financial_bundle, policy=trajectory_policy)
    trajectories = tuple(sorted((
        build_financial_metric_trajectory(financial_bundle, request=request, policy=trajectory_policy)
        for request in requests
    ), key=_trajectory_key))
    interpretations = tuple(sorted((
        interpret_research_metric_directionality(value, policy=directionality_policy)
        for value in trajectories if value.status is FinancialMetricTrajectoryStatus.AVAILABLE
    ), key=_directionality_key))
    warnings = tuple(sorted({
        *(reason.value for failure in financial_bundle.failures for reason in failure.reason_codes),
        *(blocker for trajectory in trajectories for blocker in trajectory.blockers),
    }))
    values = dict(
        canonical_instrument_id=unified_state.canonical_instrument_id,
        as_of=unified_state.as_of,
        unified_state=unified_state,
        brain_research_state_v2=brain,
        financial_bundle=financial_bundle,
        financial_failures=financial_failures,
        financial_trajectories=trajectories,
        directionality_interpretations=interpretations,
        trajectory_policy_id=trajectory_policy.policy_id,
        trajectory_policy_version=trajectory_policy.version,
        trajectory_policy_fingerprint=trajectory_policy.fingerprint,
        directionality_policy_id=directionality_policy.policy_id,
        directionality_policy_version=directionality_policy.version,
        directionality_policy_fingerprint=directionality_policy.fingerprint,
        materiality_policy_id=materiality_policy.policy_id,
        materiality_policy_version=materiality_policy.version,
        materiality_policy_fingerprint=materiality_policy.fingerprint,
        materiality_calibration_status=SharedBrainMaterialityCalibrationStatus.CALIBRATION_REQUIRED,
        dependency_manifest=tuple(sorted((
            ("brain_research_state_v2", brain.fingerprint),
            ("directionality_policy", directionality_policy.fingerprint),
            ("financial_bundle", financial_bundle.fingerprint),
            ("materiality_policy", materiality_policy.fingerprint),
            ("trajectory_policy", trajectory_policy.fingerprint),
            ("unified_state", unified_state.fingerprint),
        ))),
        warnings=warnings,
    )
    return SharedBrainProductionSnapshot(
        **values, fingerprint=_snapshot_fingerprint_values(values),
    )


def enumerate_financial_trajectory_requests(
    bundle: FinancialResearchObservationBundle,
    *, policy: FrozenFinancialMetricTrajectoryPolicy,
) -> tuple[FinancialMetricTrajectoryRequest, ...]:
    """Enumerate only bounded, proven pairs and verify each through the builder."""
    _validate_trajectory_policy(policy)
    if not isinstance(bundle, FinancialResearchObservationBundle):
        raise ValueError("SHARED_BRAIN_PRODUCTION_FINANCIAL_BUNDLE_REQUIRED")
    if financial_research_observation_bundle_fingerprint(bundle) != bundle.fingerprint:
        raise ValueError("SHARED_BRAIN_PRODUCTION_FINANCIAL_BUNDLE_TAMPERED")
    candidates: set[tuple[FinancialMetric, FinancialMetricTrajectoryBasis, str, str]] = set()
    groups: dict[tuple, list] = {}
    for observation in bundle.observations:
        period = observation.period_identity
        if period.strength is not FinancialMetricPeriodIdentityStrength.COMPLETE:
            continue
        groups.setdefault(_representation_key(observation), []).append(observation)
    for values in groups.values():
        ordered = tuple(sorted(values, key=_economic_key))
        metric = ordered[0].metric
        period_type = ordered[0].period_identity.period_type
        if period_type is FinancialPeriodType.QUARTERLY:
            _quarterly_candidates(candidates, metric, ordered)
        elif period_type is FinancialPeriodType.ANNUAL:
            _annual_candidates(candidates, metric, ordered)
        elif period_type is FinancialPeriodType.POINT_IN_TIME:
            _point_in_time_candidates(candidates, metric, ordered)
    requests = tuple(sorted((
        FinancialMetricTrajectoryRequest(metric, basis, previous, current)
        for metric, basis, previous, current in candidates
        if _available_request(bundle, metric, basis, previous, current, policy)
    ), key=_request_key))
    return requests


def project_shared_brain_production_snapshot(
    snapshot: SharedBrainProductionSnapshot,
    *, output_context: BrainOutputContext,
) -> SharedBrainProductionContextProjection:
    """Expose one identical semantic section through any existing Brain context."""
    if not isinstance(snapshot, SharedBrainProductionSnapshot):
        raise ValueError("SHARED_BRAIN_PRODUCTION_SNAPSHOT_REQUIRED")
    snapshot.__post_init__()
    trajectories = tuple(sorted(value.fingerprint for value in snapshot.financial_trajectories))
    interpretations = tuple(sorted(value.fingerprint for value in snapshot.directionality_interpretations))
    failures = tuple(sorted(value.fingerprint for value in snapshot.financial_failures))
    section_values = dict(
        shared_brain_snapshot_fingerprint=snapshot.fingerprint,
        financial_bundle_fingerprint=snapshot.financial_bundle.fingerprint,
        trajectory_fingerprints=trajectories,
        directionality_fingerprints=interpretations,
        financial_failure_fingerprints=failures,
        materiality_policy_fingerprint=snapshot.materiality_policy_fingerprint,
        materiality_calibration_status=snapshot.materiality_calibration_status,
    )
    section_fingerprint = manifest_fingerprint(**_convert_values(section_values))
    values = dict(
        canonical_instrument_id=snapshot.canonical_instrument_id,
        as_of=snapshot.as_of,
        output_context=output_context,
        shared_brain_snapshot_fingerprint=snapshot.fingerprint,
        unified_state_fingerprint=snapshot.unified_state.fingerprint,
        brain_research_state_v2_fingerprint=snapshot.brain_research_state_v2.fingerprint,
        financial_semantic_section_fingerprint=section_fingerprint,
        trajectory_fingerprints=trajectories,
        directionality_fingerprints=interpretations,
        financial_failure_fingerprints=failures,
        materiality_calibration_status=snapshot.materiality_calibration_status,
        materiality_policy_fingerprint=snapshot.materiality_policy_fingerprint,
    )
    return SharedBrainProductionContextProjection(
        **values, fingerprint=_context_projection_fingerprint_values(values),
    )


def shared_brain_production_snapshot_fingerprint(value: SharedBrainProductionSnapshot) -> str:
    return _snapshot_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def shared_brain_production_context_projection_fingerprint(value: SharedBrainProductionContextProjection) -> str:
    return _context_projection_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _quarterly_candidates(candidates, metric, values) -> None:
    quarters = {
        (value.period_identity.fiscal_year, value.period_identity.fiscal_quarter): value
        for value in values
        if value.period_identity.value_basis is FinancialValueBasis.QUARTER_ONLY
    }
    for (year, quarter), previous in quarters.items():
        if year is None or quarter is None:
            continue
        next_key = (year, quarter + 1) if quarter < 4 else (year + 1, 1)
        current = quarters.get(next_key)
        if current is not None:
            candidates.add((metric, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, previous.fingerprint, current.fingerprint))
        current = quarters.get((year + 1, quarter))
        if current is not None:
            candidates.add((metric, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER, previous.fingerprint, current.fingerprint))


def _annual_candidates(candidates, metric, values) -> None:
    years = {
        value.period_identity.fiscal_year: value
        for value in values
        if value.period_identity.value_basis is FinancialValueBasis.FULL_YEAR and value.period_identity.fiscal_year is not None
    }
    for year, previous in years.items():
        current = years.get(year + 1)
        if current is not None:
            candidates.add((metric, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL, previous.fingerprint, current.fingerprint))


def _point_in_time_candidates(candidates, metric, values) -> None:
    stock_metrics = {
        FinancialMetric.TOTAL_ASSETS, FinancialMetric.TOTAL_LIABILITIES, FinancialMetric.TOTAL_EQUITY,
        FinancialMetric.NET_WORTH, FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS,
        FinancialMetric.CURRENT_ASSETS, FinancialMetric.CURRENT_LIABILITIES, FinancialMetric.INVENTORY,
        FinancialMetric.RECEIVABLES, FinancialMetric.PAYABLES, FinancialMetric.SHARES_OUTSTANDING,
        FinancialMetric.FACE_VALUE,
    }
    if metric not in stock_metrics:
        return
    ordered = tuple(sorted(values, key=_economic_key))
    for previous, current in zip(ordered, ordered[1:]):
        candidates.add((metric, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL, previous.fingerprint, current.fingerprint))


def _available_request(bundle, metric, basis, previous, current, policy) -> bool:
    result = build_financial_metric_trajectory(
        bundle,
        request=FinancialMetricTrajectoryRequest(metric, basis, previous, current),
        policy=policy,
    )
    return result.status is FinancialMetricTrajectoryStatus.AVAILABLE


def _validate_policies(trajectory, directionality, materiality) -> None:
    _validate_trajectory_policy(trajectory)
    if not isinstance(directionality, ResearchMetricDirectionalityPolicy) or research_metric_directionality_policy_fingerprint(directionality) != directionality.fingerprint or directionality != CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY:
        raise ValueError("SHARED_BRAIN_PRODUCTION_DIRECTIONALITY_POLICY_REQUIRED")
    if not isinstance(materiality, ResearchSemanticMaterialityPolicy) or research_semantic_materiality_policy_fingerprint(materiality) != materiality.fingerprint or materiality != CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY:
        raise ValueError("SHARED_BRAIN_PRODUCTION_MATERIALITY_POLICY_REQUIRED")


def _validate_trajectory_policy(policy) -> None:
    if not isinstance(policy, FrozenFinancialMetricTrajectoryPolicy) or financial_metric_trajectory_policy_fingerprint(policy) != policy.fingerprint or policy != CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY:
        raise ValueError("SHARED_BRAIN_PRODUCTION_TRAJECTORY_POLICY_REQUIRED")


def _representation_key(value) -> tuple:
    period = value.period_identity
    return (
        value.metric, value.fact_kind, value.statement_scope, value.currency, value.unit, value.scale,
        value.normalization_version, value.schema_id, value.schema_version, value.schema_fingerprint,
        period.period_type, period.value_basis, period.value_dimension,
    )


def _economic_key(value) -> tuple:
    period = value.period_identity
    return (
        _time(period.period_end), period.fiscal_year or -1, period.fiscal_quarter or -1,
        period.fingerprint, value.fingerprint,
    )


def _request_key(value: FinancialMetricTrajectoryRequest) -> tuple:
    return (value.metric.value, value.basis.value, value.current_observation_fingerprint or "", value.previous_observation_fingerprint or "")


def _trajectory_key(value: FinancialMetricTrajectory) -> tuple:
    return (value.metric.value, value.basis.value, value.current_period_fingerprint or "", value.previous_period_fingerprint or "", value.fingerprint)


def _directionality_key(value: ResearchMetricDirectionalityInterpretation) -> tuple:
    return (value.metric, value.trajectory_basis, value.source_trajectory_fingerprint, value.fingerprint)


def _trajectory_identity() -> tuple[str, str, str]:
    policy = CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY
    return policy.policy_id, policy.version, policy.fingerprint


def _directionality_identity() -> tuple[str, str, str]:
    policy = CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY
    return policy.policy_id, policy.version, policy.fingerprint


def _materiality_identity() -> tuple[str, str, str]:
    policy = CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY
    return policy.policy_id, policy.version, policy.fingerprint


def _snapshot_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_convert_values(values))


def _context_projection_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_convert_values(values))


def _convert_values(values: dict) -> dict:
    return {key: _convert(value) for key, value in sorted(values.items())}


def _convert(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, tuple):
        return tuple(_convert(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field: _convert(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


def _time(value: datetime | None) -> str:
    return "" if value is None else value.astimezone(UTC).isoformat()


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "SharedBrainMaterialityCalibrationStatus", "SharedBrainProductionContextProjection",
    "SharedBrainProductionSnapshot", "build_shared_brain_production_snapshot",
    "enumerate_financial_trajectory_requests", "project_shared_brain_production_snapshot",
    "shared_brain_production_context_projection_fingerprint", "shared_brain_production_snapshot_fingerprint",
)
