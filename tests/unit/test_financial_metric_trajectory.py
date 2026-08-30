from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import copy

import pytest

import app.fundamentals.financial_research_observation_bundle_schema as bundle_contract
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY as SELECTOR_POLICY,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA as OBS_SCHEMA,
)
from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectoryRequest,
    build_financial_metric_trajectory,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY as POLICY,
    FinancialMetricNumericDomain,
    FinancialMetricSignTransition,
    FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus,
)
from app.fundamentals.financial_research_observation_bundle_builder import build_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA as BUNDLE_SCHEMA,
    FinancialResearchObservationAttestation,
)
from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag,
    FinancialValueBasis, NumericScale, StatementScope,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T = datetime(2026, 8, 29, 10, tzinfo=UTC)


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(identifier: str, *, metric=FinancialMetric.REVENUE, value="100", start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 6, 30, tzinfo=UTC), year=2027, quarter=1, period_type=FinancialPeriodType.QUARTERLY, basis=FinancialValueBasis.QUARTER_ONLY, scope=StatementScope.CONSOLIDATED, currency="INR", unit="INR", scale=NumericScale.CRORES, normalization="financial-facts-v1") -> FinancialFact:
    return FinancialFact(identifier, _instrument(), metric, Decimal(value), currency, unit, scale, period_type, basis,
                         start, end, year, quarter, scope, FundamentalFactKind.REPORTED, "BSE_OFFICIAL",
                         "filing-" + identifier, "reference-" + identifier, T - timedelta(days=4),
                         T - timedelta(days=3), normalization, ("OFFICIAL",), (), None,
                         (FinancialQualityFlag.COMPLETE,))


def _prepared(fact: FinancialFact):
    selection = select_financial_fact_vintages((fact,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=SELECTOR_POLICY).selections[0]
    result = materialize_financial_metric_observation(fact, selection=selection, schema=OBS_SCHEMA)
    assert result.observation is not None
    return result.observation, selection


def _bundle(*pairs):
    observations = tuple(pair[0] for pair in pairs)
    attestations = []
    for observation, selection in pairs:
        values = dict(observation_fingerprint=observation.fingerprint, source_fact_id=observation.source_fact_id,
                      selection_result_fingerprint=selection.fingerprint, selection_as_of=T,
                      selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
                      selector_policy_fingerprint=selection.policy_fingerprint, observation_schema_id=observation.schema_id,
                      observation_schema_version=observation.schema_version, observation_schema_fingerprint=observation.schema_fingerprint)
        attestations.append(FinancialResearchObservationAttestation(**values, fingerprint=bundle_contract.manifest_fingerprint(**bundle_contract._semantic_values(values))))
    return build_financial_research_observation_bundle(canonical_instrument_id="NSE:ALPHA", as_of=T,
        observations=observations, attestations=tuple(attestations), schema=BUNDLE_SCHEMA)


def _trajectory(bundle, metric=FinancialMetric.REVENUE, basis=FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, previous=None, current=None):
    return build_financial_metric_trajectory(bundle, request=FinancialMetricTrajectoryRequest(metric, basis, previous, current), policy=POLICY)


def test_sequential_quarter_is_exact_decimal_immutable_and_deterministic() -> None:
    q1 = _prepared(_fact("q1", value="100.10"))
    q2 = _prepared(_fact("q2", value="120.20", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    bundle = _bundle(q2, q1)
    result = _trajectory(bundle, previous=q1[0].fingerprint, current=q2[0].fingerprint)
    assert result.status is FinancialMetricTrajectoryStatus.AVAILABLE
    assert result.absolute_delta == Decimal("20.10")
    assert result.relative_delta == Decimal("20.10") / Decimal("100.10")
    assert result.numeric_domain is FinancialMetricNumericDomain.POSITIVE_PRIOR_BASE
    assert result.sign_transition is FinancialMetricSignTransition.POSITIVE_TO_POSITIVE
    assert result == _trajectory(bundle, previous=q1[0].fingerprint, current=q2[0].fingerprint)
    with pytest.raises(FrozenInstanceError): result.status = FinancialMetricTrajectoryStatus.INSUFFICIENT


def test_exact_frozen_policy_and_valid_bundle_are_required_but_inactive_policy_is_allowed() -> None:
    q1, q2 = _prepared(_fact("q1")), _prepared(_fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    bundle = _bundle(q1, q2)
    assert not POLICY.selected and not POLICY.active
    altered = copy.copy(POLICY); object.__setattr__(altered, "version", "v2-approved")
    with pytest.raises(ValueError, match="POLICY_TAMPERED|EXACT_POLICY_REQUIRED"):
        build_financial_metric_trajectory(bundle, request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER), policy=altered)
    object.__setattr__(bundle, "fingerprint", "0" * 64)
    with pytest.raises(ValueError, match="BUNDLE_TAMPERED"):
        _trajectory(bundle)


def test_partial_and_ambiguous_period_requests_fail_closed_without_guessing() -> None:
    partial = _prepared(_fact("partial", start=None, year=None, quarter=None))
    q2 = _prepared(_fact("q2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    result = _trajectory(_bundle(partial, q2), previous=partial[0].fingerprint, current=q2[0].fingerprint)
    assert result.status is FinancialMetricTrajectoryStatus.INSUFFICIENT
    assert result.blockers == ("COMPLETE_PERIOD_IDENTITY_REQUIRED",)
    q1 = _prepared(_fact("q1")); q3 = _prepared(_fact("q3", start=datetime(2026, 10, 1, tzinfo=UTC), end=datetime(2026, 12, 31, tzinfo=UTC), quarter=3))
    assert _trajectory(_bundle(q1, q2, q3)).blockers == ("AMBIGUOUS_PAIR_TARGET_REQUIRED",)


def test_same_period_self_pair_is_rejected_before_any_trajectory() -> None:
    q1 = _prepared(_fact("q1"))
    with pytest.raises(ValueError, match="SELF_PAIR_INVALID"):
        FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, q1[0].fingerprint, q1[0].fingerprint)


def test_q4_to_q1_requires_fiscal_metadata_and_sequential_proof() -> None:
    q4 = _prepared(_fact("q4", start=datetime(2026, 1, 1, tzinfo=UTC), end=datetime(2026, 3, 31, tzinfo=UTC), year=2026, quarter=4))
    q1 = _prepared(_fact("q1", start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 6, 30, tzinfo=UTC), year=2027, quarter=1))
    assert _trajectory(_bundle(q4, q1)).status is FinancialMetricTrajectoryStatus.AVAILABLE
    q3 = _prepared(_fact("q3", start=datetime(2025, 10, 1, tzinfo=UTC), end=datetime(2025, 12, 31, tzinfo=UTC), year=2026, quarter=3))
    assert _trajectory(_bundle(q3, q1), previous=q3[0].fingerprint, current=q1[0].fingerprint).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE


def test_yoy_quarter_and_annual_require_exact_fiscal_and_duration_parity() -> None:
    old = _prepared(_fact("old", start=datetime(2025, 7, 1, tzinfo=UTC), end=datetime(2025, 9, 30, tzinfo=UTC), year=2026, quarter=2))
    new = _prepared(_fact("new", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), year=2027, quarter=2))
    assert _trajectory(_bundle(old, new), basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER).status is FinancialMetricTrajectoryStatus.AVAILABLE
    bad = _prepared(_fact("bad", start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 6, 30, tzinfo=UTC), year=2027, quarter=1))
    assert _trajectory(_bundle(old, bad), basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE
    fy25 = _prepared(_fact("fy25", start=datetime(2024, 4, 1, tzinfo=UTC), end=datetime(2025, 3, 31, tzinfo=UTC), year=2025, quarter=None, period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR))
    fy26 = _prepared(_fact("fy26", start=datetime(2025, 4, 1, tzinfo=UTC), end=datetime(2026, 3, 31, tzinfo=UTC), year=2026, quarter=None, period_type=FinancialPeriodType.ANNUAL, basis=FinancialValueBasis.FULL_YEAR))
    assert _trajectory(_bundle(fy25, fy26), basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL).status is FinancialMetricTrajectoryStatus.AVAILABLE


def test_point_in_time_uses_period_end_and_rejects_flow_metrics() -> None:
    first = _prepared(_fact("a", metric=FinancialMetric.TOTAL_ASSETS, start=None, end=datetime(2025, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    second = _prepared(_fact("b", metric=FinancialMetric.TOTAL_ASSETS, start=None, end=datetime(2026, 3, 31, tzinfo=UTC), year=None, quarter=None, period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.QUARTER_ONLY))
    assert _trajectory(_bundle(first, second), metric=FinancialMetric.TOTAL_ASSETS, basis=FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL).status is FinancialMetricTrajectoryStatus.AVAILABLE
    flow = _prepared(_fact("flow", end=datetime(2025, 3, 31, tzinfo=UTC)))
    flow2 = _prepared(_fact("flow2", end=datetime(2026, 3, 31, tzinfo=UTC)))
    assert _trajectory(_bundle(flow, flow2), basis=FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL).status is FinancialMetricTrajectoryStatus.NOT_APPLICABLE


def test_cashflow_and_eps_safeguards_are_factual_and_fail_closed() -> None:
    c1 = _prepared(_fact("c1", metric=FinancialMetric.CFO, value="10"))
    c2 = _prepared(_fact("c2", metric=FinancialMetric.CFO, value="20", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    assert _trajectory(_bundle(c1, c2), metric=FinancialMetric.CFO).status is FinancialMetricTrajectoryStatus.AVAILABLE
    ytd = _prepared(_fact("ytd", metric=FinancialMetric.CFO, basis=FinancialValueBasis.YEAR_TO_DATE, start=datetime(2026, 4, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    assert _trajectory(_bundle(c1, ytd), metric=FinancialMetric.CFO, previous=c1[0].fingerprint, current=ytd[0].fingerprint).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE
    eps1 = _prepared(_fact("eps1", metric=FinancialMetric.EPS_BASIC))
    eps2 = _prepared(_fact("eps2", metric=FinancialMetric.EPS_BASIC, normalization="financial-facts-v2", start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    assert _trajectory(_bundle(eps1, eps2), metric=FinancialMetric.EPS_BASIC).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE


@pytest.mark.parametrize("field,value", [("scope", StatementScope.STANDALONE), ("currency", "USD"), ("unit", "USD"), ("scale", NumericScale.MILLIONS), ("normalization", "financial-facts-v2")])
def test_representation_mismatches_are_non_comparable(field, value) -> None:
    q1 = _prepared(_fact("q1")); kwargs = {field: value, "start": datetime(2026, 7, 1, tzinfo=UTC), "end": datetime(2026, 9, 30, tzinfo=UTC), "quarter": 2}
    q2 = _prepared(_fact("q2", **kwargs))
    assert _trajectory(_bundle(q1, q2)).status is FinancialMetricTrajectoryStatus.NON_COMPARABLE


@pytest.mark.parametrize(("previous", "current", "domain", "transition", "relative"), [
    ("2", "3", FinancialMetricNumericDomain.POSITIVE_PRIOR_BASE, FinancialMetricSignTransition.POSITIVE_TO_POSITIVE, Decimal("0.5")),
    ("2", "0", FinancialMetricNumericDomain.POSITIVE_PRIOR_BASE, FinancialMetricSignTransition.POSITIVE_TO_ZERO, Decimal("-1")),
    ("2", "-3", FinancialMetricNumericDomain.SIGN_CROSSING, FinancialMetricSignTransition.POSITIVE_TO_NEGATIVE, Decimal("-2.5")),
    ("0", "3", FinancialMetricNumericDomain.ZERO_PRIOR_BASE, FinancialMetricSignTransition.ZERO_TO_POSITIVE, None),
    ("0", "0", FinancialMetricNumericDomain.ZERO_PRIOR_BASE, FinancialMetricSignTransition.ZERO_TO_ZERO, None),
    ("0", "-3", FinancialMetricNumericDomain.ZERO_PRIOR_BASE, FinancialMetricSignTransition.ZERO_TO_NEGATIVE, None),
    ("-2", "3", FinancialMetricNumericDomain.SIGN_CROSSING, FinancialMetricSignTransition.NEGATIVE_TO_POSITIVE, None),
    ("-2", "0", FinancialMetricNumericDomain.NEGATIVE_PRIOR_BASE, FinancialMetricSignTransition.NEGATIVE_TO_ZERO, None),
    ("-2", "-3", FinancialMetricNumericDomain.NEGATIVE_PRIOR_BASE, FinancialMetricSignTransition.NEGATIVE_TO_NEGATIVE, None),
])
def test_all_sign_transitions_and_prior_base_arithmetic(previous, current, domain, transition, relative) -> None:
    q1 = _prepared(_fact("q1", value=previous)); q2 = _prepared(_fact("q2", value=current, start=datetime(2026, 7, 1, tzinfo=UTC), end=datetime(2026, 9, 30, tzinfo=UTC), quarter=2))
    result = _trajectory(_bundle(q1, q2))
    assert (result.numeric_domain, result.sign_transition, result.relative_delta) == (domain, transition, relative)
    assert result.absolute_delta == Decimal(current) - Decimal(previous)


def test_builder_never_accepts_raw_or_generic_nonbundle_inputs() -> None:
    with pytest.raises(ValueError, match="BUNDLE_REQUIRED"):
        build_financial_metric_trajectory(object(), request=FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER), policy=POLICY)
    with pytest.raises(ValueError, match="PAIR_TARGET_REQUIRED"):
        FinancialMetricTrajectoryRequest(FinancialMetric.REVENUE, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER, "one", None)
