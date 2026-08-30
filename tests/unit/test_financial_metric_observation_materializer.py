from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

import app.fundamentals.financial_metric_observation_materializer as materializer_module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import (
    FinancialMetricObservationMaterializationReason,
    FinancialMetricObservationMaterializationStatus,
    financial_metric_observation_materialization_result_fingerprint,
    materialize_financial_metric_observation,
)
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricPeriodIdentityStrength,
    create_frozen_financial_metric_observation_schema,
)
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialQualityFlag,
    FinancialValueBasis,
    NumericScale,
    StatementScope,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T = datetime(2026, 8, 29, 10, tzinfo=UTC)
POLICY = CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY
SCHEMA = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(
    identifier: str = "fact-1",
    *,
    metric: FinancialMetric = FinancialMetric.REVENUE,
    value: Decimal = Decimal("100.123456789"),
    period_type: FinancialPeriodType = FinancialPeriodType.QUARTERLY,
    basis: FinancialValueBasis = FinancialValueBasis.QUARTER_ONLY,
    period_start: datetime | None = datetime(2026, 4, 1, tzinfo=UTC),
    period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC),
    fiscal_year: int | None = 2027,
    fiscal_quarter: int | None = 1,
    scope: StatementScope = StatementScope.CONSOLIDATED,
    published: datetime = T - timedelta(days=3),
    received: datetime | None = None,
    revision_of_fact_id: str | None = None,
    quality_flags: tuple[FinancialQualityFlag, ...] = (FinancialQualityFlag.COMPLETE,),
) -> FinancialFact:
    return FinancialFact(
        identifier, _instrument(), metric, value, "INR", "INR", NumericScale.CRORES,
        period_type, basis, period_start, period_end, fiscal_year, fiscal_quarter, scope,
        FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "filing-" + identifier,
        "reference-" + identifier, published, received or published,
        "financial-facts-v1", ("OFFICIAL",), (), revision_of_fact_id, quality_flags,
    )


def _selection(fact: FinancialFact, *, as_of: datetime = T):
    return select_financial_fact_vintages(
        (fact,), canonical_instrument_id="NSE:ALPHA", as_of=as_of, policy=POLICY,
    ).selections[0]


def _materialize(fact: FinancialFact, *, as_of: datetime = T):
    return materialize_financial_metric_observation(fact, selection=_selection(fact, as_of=as_of), schema=SCHEMA)


def test_selected_fact_materializes_immutably_and_deterministically() -> None:
    fact = _fact()
    first, second = _materialize(fact), _materialize(fact)
    assert first == second
    assert first.status is FinancialMetricObservationMaterializationStatus.MATERIALIZED
    assert first.observation is not None
    assert first.fingerprint == financial_metric_observation_materialization_result_fingerprint(first)
    assert first.observation.value == Decimal("100.123456789")
    with pytest.raises(FrozenInstanceError):
        first.status = FinancialMetricObservationMaterializationStatus.REJECTED
    with pytest.raises(FrozenInstanceError):
        first.observation.value = Decimal("0")  # type: ignore[union-attr]


def test_exact_frozen_schema_is_required_but_its_inactive_state_is_valid() -> None:
    fact = _fact()
    assert not SCHEMA.active and not SCHEMA.selected_for_future_materializer
    different = create_frozen_financial_metric_observation_schema(
        schema_id="financial-metric-observation-schema", version="v2-approved",
        proposal_schema_id="financial-metric-observation-schema", proposal_version="v1-proposed",
        approved_by="human:Akash-Verma", provenance=(("scope", "different"),),
    )
    result = materialize_financial_metric_observation(fact, selection=_selection(fact), schema=different)
    assert result.status is FinancialMetricObservationMaterializationStatus.REJECTED
    assert result.reasons == (FinancialMetricObservationMaterializationReason.SCHEMA_UNSUPPORTED,)


def test_selection_status_id_semantic_key_and_pit_binding_fail_closed() -> None:
    fact = _fact()
    unselected = _selection(_fact("future", published=T + timedelta(days=1)))
    result = materialize_financial_metric_observation(fact, selection=unselected, schema=SCHEMA)
    assert result.reasons == (FinancialMetricObservationMaterializationReason.SELECTION_NOT_SELECTED,)

    other = _fact("other", metric=FinancialMetric.PAT)
    mismatch = materialize_financial_metric_observation(other, selection=_selection(fact), schema=SCHEMA)
    assert mismatch.reasons == (FinancialMetricObservationMaterializationReason.SELECTED_FACT_ID_MISMATCH,)

    selection = _selection(fact)
    object.__setattr__(selection, "selected_fact_id", fact.fact_id)
    object.__setattr__(fact, "currency", "USD")
    semantic = materialize_financial_metric_observation(fact, selection=selection, schema=SCHEMA)
    assert semantic.reasons == (FinancialMetricObservationMaterializationReason.SELECTION_SEMANTIC_KEY_MISMATCH,)


def test_period_identity_is_complete_or_partial_without_inference() -> None:
    complete = _materialize(_fact())
    assert complete.observation is not None
    assert complete.observation.period_identity.strength is FinancialMetricPeriodIdentityStrength.COMPLETE
    assert complete.observation.period_identity.period_end == datetime(2026, 6, 30, tzinfo=UTC)

    partial_fact = _fact("partial", period_start=None, fiscal_year=None, fiscal_quarter=None, scope=StatementScope.UNKNOWN)
    partial = _materialize(partial_fact)
    assert partial.observation is not None
    assert partial.observation.period_identity.strength is FinancialMetricPeriodIdentityStrength.PARTIAL
    assert partial.observation.period_identity.statement_scope is StatementScope.UNKNOWN

    point = _materialize(_fact("point", period_type=FinancialPeriodType.POINT_IN_TIME, basis=FinancialValueBasis.UNKNOWN, period_start=None, fiscal_year=None, fiscal_quarter=None))
    assert point.observation is not None
    assert point.observation.period_identity.period_end == datetime(2026, 6, 30, tzinfo=UTC)


def test_visible_as_of_and_lineage_preserve_source_fact_not_selection_time() -> None:
    fact = _fact(received=T - timedelta(days=1))
    result = _materialize(fact, as_of=T)
    assert result.observation is not None
    observation = result.observation
    assert observation.visible_as_of == fact.available_at == T - timedelta(days=1)
    assert observation.published_at == fact.published_at
    assert observation.source == "BSE_OFFICIAL" and observation.filing_id == "filing-fact-1"
    assert observation.selection_result_fingerprint == _selection(fact).fingerprint


@pytest.mark.parametrize("value", (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")))
def test_nonfinite_decimal_is_rejected_without_substitution(value: Decimal) -> None:
    fact = _fact()
    selection = _selection(fact)
    object.__setattr__(fact, "value", value)
    result = materialize_financial_metric_observation(fact, selection=selection, schema=SCHEMA)
    assert result.status is FinancialMetricObservationMaterializationStatus.REJECTED
    assert result.reasons == (FinancialMetricObservationMaterializationReason.NONFINITE_DECIMAL,)


def test_schema_owned_semantic_fingerprint_excludes_storage_id_but_observation_does_not() -> None:
    first, second = _materialize(_fact("first")), _materialize(_fact("second"))
    assert first.observation is not None and second.observation is not None
    assert first.observation.source_fact_semantic_fingerprint != second.observation.source_fact_semantic_fingerprint
    # Filing/source reference are source semantics. With equal factual contents
    # apart from storage identity, the schema fingerprint excludes that identity.
    duplicate = _fact("third")
    original = _fact("fourth")
    object.__setattr__(duplicate, "filing_id", original.filing_id)
    object.__setattr__(duplicate, "source_reference", original.source_reference)
    a, b = _materialize(original), _materialize(duplicate)
    assert a.observation is not None and b.observation is not None
    assert a.observation.source_fact_semantic_fingerprint == b.observation.source_fact_semantic_fingerprint
    assert a.observation.fingerprint != b.observation.fingerprint


@pytest.mark.parametrize(
    ("metric", "basis"),
    (
        (FinancialMetric.CFO, FinancialValueBasis.QUARTER_ONLY),
        (FinancialMetric.CFO, FinancialValueBasis.YEAR_TO_DATE),
        (FinancialMetric.CFO, FinancialValueBasis.FULL_YEAR),
        (FinancialMetric.EPS_BASIC, FinancialValueBasis.QUARTER_ONLY),
        (FinancialMetric.FACE_VALUE, FinancialValueBasis.QUARTER_ONLY),
        (FinancialMetric.SHARES_OUTSTANDING, FinancialValueBasis.QUARTER_ONLY),
    ),
)
def test_cashflow_and_per_share_representations_are_preserved(metric: FinancialMetric, basis: FinancialValueBasis) -> None:
    result = _materialize(_fact(metric=metric, basis=basis))
    assert result.observation is not None
    assert result.observation.metric is metric
    assert result.observation.period_identity.value_basis is basis
    assert result.observation.value == Decimal("100.123456789")


def test_materializer_has_no_selector_store_runtime_or_interpretation_dependency() -> None:
    source = inspect.getsource(materializer_module)
    for forbidden in (
        "select_financial_fact_vintages",
        "SQLite", "PostgreSQL", "sqlite3", "requests", "urllib", "FastAPI", "APIRouter",
        "FinancialMetricTrajectory", "ResearchStateDelta", "QoQ", "YoY", "TTM",
        "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "recommendation",
    ):
        assert forbidden not in source
