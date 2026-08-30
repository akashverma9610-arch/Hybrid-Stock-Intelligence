from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from decimal import Decimal
import inspect

import pytest

import app.fundamentals.financial_metric_observation_schema as schema_module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricObservation,
    FinancialMetricObservationSchemaApprovalStatus,
    FinancialMetricPeriodIdentity,
    FinancialMetricPeriodIdentityStrength,
    financial_metric_observation_fingerprint,
    financial_metric_observation_schema_fingerprint,
    financial_metric_period_identity_fingerprint,
    financial_metric_source_fact_semantic_fingerprint_values,
)
from app.fundamentals.models import (
    FinancialMetric,
    FinancialPeriodType,
    FinancialQualityFlag,
    FinancialValueBasis,
    FinancialValueDimension,
    NumericScale,
    StatementScope,
)


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
SCHEMA = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA


def _period(
    *,
    strength: FinancialMetricPeriodIdentityStrength = FinancialMetricPeriodIdentityStrength.COMPLETE,
    metric_dimension: FinancialValueDimension = FinancialValueDimension.MONETARY,
    scope: StatementScope = StatementScope.CONSOLIDATED,
    period_type: FinancialPeriodType = FinancialPeriodType.QUARTERLY,
    basis: FinancialValueBasis = FinancialValueBasis.QUARTER_ONLY,
    period_start: datetime | None = datetime(2026, 4, 1, tzinfo=UTC),
    period_end: datetime | None = datetime(2026, 6, 30, tzinfo=UTC),
    fiscal_year: int | None = 2027,
    fiscal_quarter: int | None = 1,
    currency: str = "INR",
    unit: str = "INR",
    scale: NumericScale = NumericScale.CRORES,
) -> FinancialMetricPeriodIdentity:
    values = dict(
        period_type=period_type,
        value_basis=basis,
        period_start=period_start,
        period_end=period_end,
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
        statement_scope=scope,
        value_dimension=metric_dimension,
        currency=currency,
        unit=unit,
        scale=scale,
        normalization_version="financial-facts-v1",
        strength=strength,
    )
    return FinancialMetricPeriodIdentity(
        **values,
        fingerprint=schema_module.financial_metric_period_identity_fingerprint_values(values),
    )


def _observation(
    *,
    source_fact_id: str = "fact-1",
    metric: FinancialMetric = FinancialMetric.REVENUE,
    value: Decimal = Decimal("100.123456789"),
    period: FinancialMetricPeriodIdentity | None = None,
    scope: StatementScope = StatementScope.CONSOLIDATED,
    currency: str = "INR",
    unit: str = "INR",
    scale: NumericScale = NumericScale.CRORES,
    quality_flags: tuple[FinancialQualityFlag, ...] = (FinancialQualityFlag.COMPLETE,),
) -> FinancialMetricObservation:
    identity = period or _period(scope=scope, currency=currency, unit=unit, scale=scale)
    source_values = dict(
        canonical_instrument_id="NSE:ALPHA",
        metric=metric,
        fact_kind=FundamentalFactKind.REPORTED,
        value=value,
        currency=currency,
        unit=unit,
        scale=scale,
        statement_scope=scope,
        period_identity=identity,
        source="BSE_OFFICIAL",
        filing_id="filing-1",
        source_reference="document-1",
        published_at=T,
        received_at=T,
        revision_of_fact_id=None,
        parent_fact_ids=(),
        quality_flags=quality_flags,
        provenance=("OFFICIAL",),
        normalization_version="financial-facts-v1",
    )
    values = dict(
        **source_values,
        visible_as_of=T,
        source_fact_id=source_fact_id,
        selection_policy_id="financial-fact-vintage-selection-policy",
        selection_policy_version="v1-approved",
        selection_policy_fingerprint="862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13",
        selection_result_fingerprint="selection-result-1",
        source_fact_semantic_fingerprint=financial_metric_source_fact_semantic_fingerprint_values(source_values),
        schema_id=SCHEMA.schema_id,
        schema_version=SCHEMA.version,
        schema_fingerprint=SCHEMA.fingerprint,
    )
    return FinancialMetricObservation(
        **values,
        fingerprint=schema_module.financial_metric_observation_fingerprint_values(values),
    )


def test_schema_identity_lineage_inactive_state_and_fingerprint_are_exact() -> None:
    assert (SCHEMA.schema_id, SCHEMA.version) == ("financial-metric-observation-schema", "v1-approved")
    assert (SCHEMA.proposal_schema_id, SCHEMA.proposal_version) == ("financial-metric-observation-schema", "v1-proposed")
    assert SCHEMA.approval_status is FinancialMetricObservationSchemaApprovalStatus.APPROVED
    assert SCHEMA.approved_by == "human:Akash-Verma"
    assert not SCHEMA.active and not SCHEMA.selected_for_future_materializer
    assert financial_metric_observation_schema_fingerprint(SCHEMA) == SCHEMA.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(SCHEMA, version="v1-tampered")


def test_period_identity_preserves_accounting_period_not_publication_time() -> None:
    identity = _period()
    assert identity.period_type is FinancialPeriodType.QUARTERLY
    assert identity.value_basis is FinancialValueBasis.QUARTER_ONLY
    assert identity.period_start == datetime(2026, 4, 1, tzinfo=UTC)
    assert identity.period_end == datetime(2026, 6, 30, tzinfo=UTC)
    assert identity.fiscal_year == 2027 and identity.fiscal_quarter == 1
    assert identity.statement_scope is StatementScope.CONSOLIDATED
    assert financial_metric_period_identity_fingerprint(identity) == identity.fingerprint
    with pytest.raises(FrozenInstanceError):
        identity.period_end = T


def test_complete_partial_and_insufficient_period_identity_semantics_are_explicit() -> None:
    partial = _period(
        strength=FinancialMetricPeriodIdentityStrength.PARTIAL,
        period_start=None,
        fiscal_year=None,
        fiscal_quarter=None,
    )
    insufficient = _period(
        strength=FinancialMetricPeriodIdentityStrength.INSUFFICIENT,
        period_end=None,
        period_start=None,
        fiscal_year=None,
        fiscal_quarter=None,
    )
    assert partial.strength is FinancialMetricPeriodIdentityStrength.PARTIAL
    assert insufficient.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT
    with pytest.raises(ValueError, match="COMPLETE_FIELDS"):
        _period(period_start=None)


def test_observation_is_immutable_and_preserves_decimal_scope_pit_and_lineage() -> None:
    observation = _observation()
    assert observation.value == Decimal("100.123456789")
    assert observation.visible_as_of == max(observation.published_at, observation.received_at)
    assert observation.source_fact_id == "fact-1"
    assert observation.source == "BSE_OFFICIAL" and observation.filing_id == "filing-1"
    assert observation.statement_scope is StatementScope.CONSOLIDATED
    assert observation.period_identity.strength is FinancialMetricPeriodIdentityStrength.COMPLETE
    assert financial_metric_observation_fingerprint(observation) == observation.fingerprint
    with pytest.raises(FrozenInstanceError):
        observation.value = Decimal("1")


def test_source_fact_fingerprint_is_semantic_not_storage_row_identity() -> None:
    first = _observation(source_fact_id="fact-1")
    second = _observation(source_fact_id="fact-2")
    changed = _observation(value=Decimal("100.123456790"))
    assert first.source_fact_semantic_fingerprint == second.source_fact_semantic_fingerprint
    assert first.fingerprint != second.fingerprint
    assert first.source_fact_semantic_fingerprint != changed.source_fact_semantic_fingerprint


def test_unknown_scope_partial_identity_and_visible_as_of_remain_factual() -> None:
    period = _period(
        strength=FinancialMetricPeriodIdentityStrength.PARTIAL,
        scope=StatementScope.UNKNOWN,
        period_start=None,
        fiscal_year=None,
        fiscal_quarter=None,
    )
    observation = _observation(period=period, scope=StatementScope.UNKNOWN)
    assert observation.statement_scope is StatementScope.UNKNOWN
    assert observation.period_identity.statement_scope is StatementScope.UNKNOWN
    assert observation.visible_as_of == T


def test_insufficient_identity_and_nonfinite_decimal_fail_observation_admission() -> None:
    with pytest.raises(ValueError, match="PERIOD_IDENTITY_INSUFFICIENT"):
        _observation(period=_period(
            strength=FinancialMetricPeriodIdentityStrength.INSUFFICIENT,
            period_end=None,
            period_start=None,
            fiscal_year=None,
            fiscal_quarter=None,
        ))
    with pytest.raises(ValueError, match="FINITE_DECIMAL"):
        _observation(value=Decimal("NaN"))


def test_eps_cashflow_shares_and_face_value_remain_exact_factual_metrics() -> None:
    per_share = _period(metric_dimension=FinancialValueDimension.PER_SHARE)
    eps = _observation(metric=FinancialMetric.EPS_BASIC, value=Decimal("12.34"), period=per_share)
    face = _observation(metric=FinancialMetric.FACE_VALUE, value=Decimal("10"), period=per_share)
    count = _period(metric_dimension=FinancialValueDimension.COUNT)
    shares = _observation(metric=FinancialMetric.SHARES_OUTSTANDING, value=Decimal("123456"), period=count)
    q_cash = _period()
    ytd_cash = _period(basis=FinancialValueBasis.YEAR_TO_DATE)
    assert eps.value == Decimal("12.34") and face.value == Decimal("10") and shares.value == Decimal("123456")
    assert q_cash.value_basis is FinancialValueBasis.QUARTER_ONLY
    assert ytd_cash.value_basis is FinancialValueBasis.YEAR_TO_DATE
    assert q_cash.fingerprint != ytd_cash.fingerprint
    with pytest.raises(ValueError, match="VALUE_DIMENSION_MISMATCH"):
        _observation(metric=FinancialMetric.EPS_BASIC)


def test_schema_contract_has_no_selector_materializer_trajectory_or_runtime_wiring() -> None:
    source = inspect.getsource(schema_module)
    for forbidden in (
        "select_financial_fact_vintages",
        "materialize_financial_metric_observation",
        "FinancialMetricTrajectory",
        "ResearchStateDelta",
        "SQLite",
        "PostgreSQL",
        "sqlite3",
        "requests",
        "urllib",
        "FastAPI",
        "APIRouter",
    ):
        assert forbidden not in source
