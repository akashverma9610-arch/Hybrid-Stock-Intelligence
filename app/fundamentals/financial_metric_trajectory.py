"""Pure factual financial period-pair trajectory construction.

This module accepts one already-valid same-as-of
``FinancialResearchObservationBundle`` and the explicitly frozen trajectory
policy.  It neither selects facts nor materializes observations, and it has no
store, provider, runtime, Brain, wrapper, or delta dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricObservation,
    FinancialMetricPeriodIdentityStrength,
    financial_metric_observation_fingerprint,
    financial_metric_period_identity_fingerprint,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY,
    FinancialMetricNumericDomain,
    FinancialMetricSignTransition,
    FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus,
    FrozenFinancialMetricTrajectoryPolicy,
    financial_metric_trajectory_policy_fingerprint,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    FinancialResearchObservationBundle,
    financial_research_observation_bundle_fingerprint,
)
from app.fundamentals.models import (
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
)
from app.historical.guard import manifest_fingerprint


_CASH_FLOW_METRICS = frozenset({
    FinancialMetric.CFO, FinancialMetric.CFI, FinancialMetric.CFF,
    FinancialMetric.CAPEX, FinancialMetric.FREE_CASH_FLOW,
})
_STOCK_METRICS = frozenset({
    FinancialMetric.TOTAL_ASSETS, FinancialMetric.TOTAL_LIABILITIES,
    FinancialMetric.TOTAL_EQUITY, FinancialMetric.NET_WORTH,
    FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS,
    FinancialMetric.CURRENT_ASSETS, FinancialMetric.CURRENT_LIABILITIES,
    FinancialMetric.INVENTORY, FinancialMetric.RECEIVABLES,
    FinancialMetric.PAYABLES, FinancialMetric.SHARES_OUTSTANDING,
    FinancialMetric.FACE_VALUE,
})


@dataclass(frozen=True, slots=True)
class FinancialMetricTrajectoryRequest:
    """Explicit pair target; neither period selection nor latest reduction is implicit."""

    metric: FinancialMetric
    basis: FinancialMetricTrajectoryBasis
    previous_observation_fingerprint: str | None = None
    current_observation_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.metric, FinancialMetric) or not isinstance(self.basis, FinancialMetricTrajectoryBasis):
            raise ValueError("FINANCIAL_TRAJECTORY_REQUEST_TYPE_REQUIRED")
        if bool(self.previous_observation_fingerprint) != bool(self.current_observation_fingerprint):
            raise ValueError("FINANCIAL_TRAJECTORY_REQUEST_PAIR_TARGET_REQUIRED")
        if self.previous_observation_fingerprint == "" or self.current_observation_fingerprint == "":
            raise ValueError("FINANCIAL_TRAJECTORY_REQUEST_FINGERPRINT_INVALID")
        if self.previous_observation_fingerprint == self.current_observation_fingerprint and self.previous_observation_fingerprint:
            raise ValueError("FINANCIAL_TRAJECTORY_REQUEST_SELF_PAIR_INVALID")


@dataclass(frozen=True, slots=True)
class FinancialMetricTrajectory:
    """Immutable factual result for one explicitly determined accounting pair."""

    canonical_instrument_id: str
    bundle_as_of: datetime
    metric: FinancialMetric
    basis: FinancialMetricTrajectoryBasis
    fact_kind: FundamentalFactKind | None
    previous_observation_fingerprint: str | None
    current_observation_fingerprint: str | None
    previous_period_fingerprint: str | None
    current_period_fingerprint: str | None
    previous_value: Decimal | None
    current_value: Decimal | None
    absolute_delta: Decimal | None
    relative_delta: Decimal | None
    numeric_domain: FinancialMetricNumericDomain | None
    sign_transition: FinancialMetricSignTransition | None
    status: FinancialMetricTrajectoryStatus
    blockers: tuple[str, ...]
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not _aware(self.bundle_as_of):
            raise ValueError("FINANCIAL_TRAJECTORY_SCOPE_REQUIRED")
        if self.blockers != tuple(sorted(set(self.blockers))):
            raise ValueError("FINANCIAL_TRAJECTORY_BLOCKERS_NONCANONICAL")
        if (self.policy_id, self.policy_version, self.policy_fingerprint) != _policy_identity():
            raise ValueError("FINANCIAL_TRAJECTORY_POLICY_LINEAGE_REQUIRED")
        if self.status is FinancialMetricTrajectoryStatus.AVAILABLE:
            if any(value is None for value in (
                self.fact_kind, self.previous_observation_fingerprint, self.current_observation_fingerprint,
                self.previous_period_fingerprint, self.current_period_fingerprint, self.previous_value,
                self.current_value, self.absolute_delta, self.numeric_domain, self.sign_transition,
            )) or self.blockers:
                raise ValueError("FINANCIAL_TRAJECTORY_AVAILABLE_FIELDS_REQUIRED")
        if self.relative_delta is not None and self.previous_value is not None and self.previous_value <= 0:
            raise ValueError("FINANCIAL_TRAJECTORY_RELATIVE_DELTA_PRIOR_BASE_INVALID")
        if self.fingerprint != financial_metric_trajectory_fingerprint(self):
            raise ValueError("FINANCIAL_TRAJECTORY_FINGERPRINT_MISMATCH")


def build_financial_metric_trajectory(
    bundle: FinancialResearchObservationBundle,
    *,
    request: FinancialMetricTrajectoryRequest,
    policy: FrozenFinancialMetricTrajectoryPolicy,
) -> FinancialMetricTrajectory:
    """Build one deterministic factual trajectory from an already-built bundle."""
    _require_bundle(bundle)
    _require_policy(policy)
    observations = _metric_observations(bundle, request.metric)
    previous, current, selection_blocker = _select_pair(observations, request)
    if selection_blocker is not None:
        return _blocked(bundle, request, selection_blocker[0], selection_blocker[1])
    assert previous is not None and current is not None
    return _evaluate(bundle, request, previous, current)


def financial_metric_trajectory_fingerprint(value: FinancialMetricTrajectory) -> str:
    return _trajectory_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def _require_policy(policy: FrozenFinancialMetricTrajectoryPolicy) -> None:
    if not isinstance(policy, FrozenFinancialMetricTrajectoryPolicy):
        raise ValueError("FINANCIAL_TRAJECTORY_POLICY_REQUIRED")
    if financial_metric_trajectory_policy_fingerprint(policy) != policy.fingerprint:
        raise ValueError("FINANCIAL_TRAJECTORY_POLICY_TAMPERED")
    if policy != CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY:
        raise ValueError("FINANCIAL_TRAJECTORY_EXACT_POLICY_REQUIRED")


def _require_bundle(bundle: FinancialResearchObservationBundle) -> None:
    if not isinstance(bundle, FinancialResearchObservationBundle):
        raise ValueError("FINANCIAL_TRAJECTORY_BUNDLE_REQUIRED")
    if financial_research_observation_bundle_fingerprint(bundle) != bundle.fingerprint:
        raise ValueError("FINANCIAL_TRAJECTORY_BUNDLE_TAMPERED")
    if not _aware(bundle.as_of):
        raise ValueError("FINANCIAL_TRAJECTORY_BUNDLE_AS_OF_TIMEZONE_REQUIRED")
    for observation in bundle.observations:
        if financial_metric_observation_fingerprint(observation) != observation.fingerprint:
            raise ValueError("FINANCIAL_TRAJECTORY_OBSERVATION_TAMPERED")
        if financial_metric_period_identity_fingerprint(observation.period_identity) != observation.period_identity.fingerprint:
            raise ValueError("FINANCIAL_TRAJECTORY_PERIOD_TAMPERED")
        if observation.canonical_instrument_id != bundle.canonical_instrument_id or observation.visible_as_of > bundle.as_of:
            raise ValueError("FINANCIAL_TRAJECTORY_BUNDLE_SCOPE_INVALID")


def _metric_observations(bundle: FinancialResearchObservationBundle, metric: FinancialMetric) -> tuple[FinancialMetricObservation, ...]:
    return tuple(sorted(
        (value for value in bundle.observations if value.metric is metric),
        key=lambda value: (_time(value.period_identity.period_end) or "", value.period_identity.fingerprint, value.fingerprint),
    ))


def _select_pair(
    observations: tuple[FinancialMetricObservation, ...], request: FinancialMetricTrajectoryRequest,
) -> tuple[FinancialMetricObservation | None, FinancialMetricObservation | None, tuple[FinancialMetricTrajectoryStatus, str] | None]:
    if request.previous_observation_fingerprint:
        by_fingerprint = {value.fingerprint: value for value in observations}
        previous = by_fingerprint.get(request.previous_observation_fingerprint)
        current = by_fingerprint.get(request.current_observation_fingerprint)
        if previous is None or current is None:
            return None, None, (FinancialMetricTrajectoryStatus.INSUFFICIENT, "REQUESTED_OBSERVATION_UNAVAILABLE")
        return previous, current, None
    if len(observations) < 2:
        return None, None, (FinancialMetricTrajectoryStatus.INSUFFICIENT, "PAIR_UNAVAILABLE")
    if len(observations) != 2:
        return None, None, (FinancialMetricTrajectoryStatus.INSUFFICIENT, "AMBIGUOUS_PAIR_TARGET_REQUIRED")
    return observations[0], observations[1], None


def _evaluate(
    bundle: FinancialResearchObservationBundle, request: FinancialMetricTrajectoryRequest,
              previous: FinancialMetricObservation, current: FinancialMetricObservation) -> FinancialMetricTrajectory:
    previous_period, current_period = previous.period_identity, current.period_identity
    common = _common_pair_status(previous, current)
    if common is not None:
        return _blocked(bundle, request, *common, previous=previous, current=current)
    if previous_period.fingerprint == current_period.fingerprint:
        return _blocked(bundle, request, FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "SAME_ACCOUNTING_PERIOD", previous=previous, current=current)
    basis_status = _basis_status(request.basis, previous, current)
    if basis_status is not None:
        return _blocked(bundle, request, *basis_status, previous=previous, current=current)
    absolute = current.value - previous.value
    numeric_domain = _numeric_domain(previous.value, current.value)
    relative = absolute / previous.value if previous.value > 0 else None
    values = dict(
        canonical_instrument_id=bundle.canonical_instrument_id, bundle_as_of=bundle.as_of,
        metric=request.metric, basis=request.basis, fact_kind=previous.fact_kind,
        previous_observation_fingerprint=previous.fingerprint, current_observation_fingerprint=current.fingerprint,
        previous_period_fingerprint=previous_period.fingerprint, current_period_fingerprint=current_period.fingerprint,
        previous_value=previous.value, current_value=current.value, absolute_delta=absolute,
        relative_delta=relative, numeric_domain=numeric_domain,
        sign_transition=_sign_transition(previous.value, current.value),
        status=FinancialMetricTrajectoryStatus.AVAILABLE, blockers=(),
        policy_id=_policy_identity()[0], policy_version=_policy_identity()[1], policy_fingerprint=_policy_identity()[2],
    )
    return FinancialMetricTrajectory(**values, fingerprint=_trajectory_fingerprint_values(values))


def _common_pair_status(previous: FinancialMetricObservation, current: FinancialMetricObservation) -> tuple[FinancialMetricTrajectoryStatus, str] | None:
    if previous.period_identity.strength is FinancialMetricPeriodIdentityStrength.PARTIAL or current.period_identity.strength is FinancialMetricPeriodIdentityStrength.PARTIAL:
        return FinancialMetricTrajectoryStatus.INSUFFICIENT, "COMPLETE_PERIOD_IDENTITY_REQUIRED"
    if previous.period_identity.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT or current.period_identity.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT:
        return FinancialMetricTrajectoryStatus.INSUFFICIENT, "INSUFFICIENT_PERIOD_IDENTITY"
    if not previous.value.is_finite() or not current.value.is_finite():
        return FinancialMetricTrajectoryStatus.INSUFFICIENT, "FINITE_DECIMAL_REQUIRED"
    for name in ("canonical_instrument_id", "metric", "fact_kind", "statement_scope", "currency", "unit", "scale", "normalization_version"):
        if getattr(previous, name) != getattr(current, name):
            return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "EXACT_REPRESENTATION_PARITY_REQUIRED"
    left, right = previous.period_identity, current.period_identity
    for name in ("value_dimension", "statement_scope", "currency", "unit", "scale", "normalization_version", "value_basis"):
        if getattr(left, name) != getattr(right, name):
            return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "PERIOD_REPRESENTATION_PARITY_REQUIRED"
    if (previous.schema_id, previous.schema_version, previous.schema_fingerprint) != (current.schema_id, current.schema_version, current.schema_fingerprint):
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "OBSERVATION_SCHEMA_PARITY_REQUIRED"
    return None


def _basis_status(basis: FinancialMetricTrajectoryBasis, previous: FinancialMetricObservation, current: FinancialMetricObservation) -> tuple[FinancialMetricTrajectoryStatus, str] | None:
    if basis not in CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY.bases:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "TRAJECTORY_BASIS_UNSUPPORTED"
    if basis is FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL:
        if previous.metric not in _STOCK_METRICS:
            return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "FLOW_METRIC_POINT_IN_TIME_UNSUPPORTED"
        if previous.period_identity.period_type is not FinancialPeriodType.POINT_IN_TIME or current.period_identity.period_type is not FinancialPeriodType.POINT_IN_TIME:
            return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "POINT_IN_TIME_PERIOD_TYPE_REQUIRED"
        if previous.period_identity.period_end >= current.period_identity.period_end:
            return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "ECONOMIC_PERIOD_ORDER_REQUIRED"
        return None
    if previous.metric in _STOCK_METRICS:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "STOCK_METRIC_FLOW_BASIS_UNSUPPORTED"
    if basis is FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER:
        return _sequential_quarter_status(previous, current)
    if basis is FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER:
        return _yoy_quarter_status(previous, current)
    if basis is FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL:
        return _yoy_annual_status(previous, current)
    return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "TRAJECTORY_BASIS_UNSUPPORTED"


def _sequential_quarter_status(previous: FinancialMetricObservation, current: FinancialMetricObservation) -> tuple[FinancialMetricTrajectoryStatus, str] | None:
    left, right = previous.period_identity, current.period_identity
    if left.period_type is not FinancialPeriodType.QUARTERLY or right.period_type is not FinancialPeriodType.QUARTERLY:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "QUARTERLY_PERIOD_REQUIRED"
    if left.value_basis is not FinancialValueBasis.QUARTER_ONLY:
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "QUARTER_ONLY_BASIS_REQUIRED"
    if not _compatible_month_duration(left.period_start, left.period_end, right.period_start, right.period_end, expected_month_span=2):
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "QUARTER_DURATION_NON_COMPARABLE"
    if not _fiscal_next(left.fiscal_year, left.fiscal_quarter, right.fiscal_year, right.fiscal_quarter):
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "FISCAL_QUARTER_ADJACENCY_REQUIRED"
    if left.period_end >= right.period_start:
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "OVERLAPPING_PERIODS_UNSUPPORTED"
    return None


def _yoy_quarter_status(previous: FinancialMetricObservation, current: FinancialMetricObservation) -> tuple[FinancialMetricTrajectoryStatus, str] | None:
    left, right = previous.period_identity, current.period_identity
    if left.period_type is not FinancialPeriodType.QUARTERLY or right.period_type is not FinancialPeriodType.QUARTERLY:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "QUARTERLY_PERIOD_REQUIRED"
    if previous.metric in _CASH_FLOW_METRICS and left.value_basis is not FinancialValueBasis.QUARTER_ONLY:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "CASHFLOW_QUARTER_ONLY_REQUIRED"
    if left.fiscal_quarter != right.fiscal_quarter or right.fiscal_year != left.fiscal_year + 1:
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "YEAR_OVER_YEAR_QUARTER_IDENTITY_REQUIRED"
    if not _compatible_month_duration(left.period_start, left.period_end, right.period_start, right.period_end, expected_month_span=2):
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "QUARTER_DURATION_NON_COMPARABLE"
    return None


def _yoy_annual_status(previous: FinancialMetricObservation, current: FinancialMetricObservation) -> tuple[FinancialMetricTrajectoryStatus, str] | None:
    left, right = previous.period_identity, current.period_identity
    if left.period_type is not FinancialPeriodType.ANNUAL or right.period_type is not FinancialPeriodType.ANNUAL:
        return FinancialMetricTrajectoryStatus.NOT_APPLICABLE, "ANNUAL_PERIOD_REQUIRED"
    if left.value_basis is not FinancialValueBasis.FULL_YEAR:
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "FULL_YEAR_BASIS_REQUIRED"
    if right.fiscal_year != left.fiscal_year + 1:
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "CONSECUTIVE_FISCAL_YEAR_REQUIRED"
    if not _compatible_month_duration(left.period_start, left.period_end, right.period_start, right.period_end, expected_month_span=11):
        return FinancialMetricTrajectoryStatus.NON_COMPARABLE, "ANNUAL_DURATION_NON_COMPARABLE"
    return None


def _blocked(bundle: FinancialResearchObservationBundle, request: FinancialMetricTrajectoryRequest,
             status: FinancialMetricTrajectoryStatus, blocker: str,
             previous: FinancialMetricObservation | None = None, current: FinancialMetricObservation | None = None) -> FinancialMetricTrajectory:
    values = dict(
        canonical_instrument_id=bundle.canonical_instrument_id, bundle_as_of=bundle.as_of,
        metric=request.metric, basis=request.basis,
        fact_kind=None if previous is None else previous.fact_kind,
        previous_observation_fingerprint=None if previous is None else previous.fingerprint,
        current_observation_fingerprint=None if current is None else current.fingerprint,
        previous_period_fingerprint=None if previous is None else previous.period_identity.fingerprint,
        current_period_fingerprint=None if current is None else current.period_identity.fingerprint,
        previous_value=None if previous is None else previous.value,
        current_value=None if current is None else current.value,
        absolute_delta=None, relative_delta=None, numeric_domain=None, sign_transition=None,
        status=status, blockers=(blocker,),
        policy_id=_policy_identity()[0], policy_version=_policy_identity()[1], policy_fingerprint=_policy_identity()[2],
    )
    return FinancialMetricTrajectory(**values, fingerprint=_trajectory_fingerprint_values(values))


def _fiscal_next(previous_year: int | None, previous_quarter: int | None, current_year: int | None, current_quarter: int | None) -> bool:
    if None in {previous_year, previous_quarter, current_year, current_quarter}:
        return False
    if previous_quarter in {1, 2, 3}:
        return current_year == previous_year and current_quarter == previous_quarter + 1
    return previous_quarter == 4 and current_year == previous_year + 1 and current_quarter == 1


def _compatible_month_duration(previous_start: datetime | None, previous_end: datetime | None,
                               current_start: datetime | None, current_end: datetime | None,
                               *, expected_month_span: int) -> bool:
    if None in {previous_start, previous_end, current_start, current_end}:
        return False
    def months(start: datetime, end: datetime) -> int:
        return (end.year - start.year) * 12 + end.month - start.month
    return months(previous_start, previous_end) == expected_month_span and months(current_start, current_end) == expected_month_span


def _numeric_domain(previous: Decimal, current: Decimal) -> FinancialMetricNumericDomain:
    if (previous < 0 < current) or (previous > 0 > current):
        return FinancialMetricNumericDomain.SIGN_CROSSING
    if previous > 0:
        return FinancialMetricNumericDomain.POSITIVE_PRIOR_BASE
    if previous == 0:
        return FinancialMetricNumericDomain.ZERO_PRIOR_BASE
    return FinancialMetricNumericDomain.NEGATIVE_PRIOR_BASE


def _sign_transition(previous: Decimal, current: Decimal) -> FinancialMetricSignTransition:
    def sign(value: Decimal) -> str:
        return "POSITIVE" if value > 0 else "NEGATIVE" if value < 0 else "ZERO"
    return FinancialMetricSignTransition(f"{sign(previous)}_TO_{sign(current)}")


def _policy_identity() -> tuple[str, str, str]:
    policy = CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY
    return policy.policy_id, policy.version, policy.fingerprint


def _trajectory_fingerprint_values(values: dict) -> str:
    def convert(value):
        if isinstance(value, (FinancialMetricTrajectoryBasis, FinancialMetricTrajectoryStatus, FinancialMetricNumericDomain, FinancialMetricSignTransition, FinancialMetric, FundamentalFactKind)):
            return value.value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return _time(value)
        if isinstance(value, tuple):
            return tuple(convert(item) for item in value)
        return value
    return manifest_fingerprint(**{key: convert(value) for key, value in values.items()})


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


__all__ = (
    "FinancialMetricTrajectory", "FinancialMetricTrajectoryRequest",
    "build_financial_metric_trajectory", "financial_metric_trajectory_fingerprint",
)
