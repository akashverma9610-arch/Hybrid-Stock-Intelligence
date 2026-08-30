from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import copy
import inspect

import pytest

import app.fundamentals.financial_research_observation_bundle_schema as contract
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionMode,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import (
    FinancialMetricObservationMaterializationReason,
    FinancialMetricObservationMaterializationStatus,
    materialize_financial_metric_observation,
)
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricPeriodIdentityStrength,
)
from app.fundamentals.financial_research_observation_bundle_builder import (
    build_financial_research_observation_bundle,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
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
OBS_SCHEMA = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA
SCHEMA = CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA


def _instrument(identifier: str = "NSE:ALPHA") -> InstrumentIdentity:
    return InstrumentIdentity(identifier, Exchange.NSE, identifier.split(":")[-1], "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(
    identifier: str,
    *,
    metric: FinancialMetric = FinancialMetric.REVENUE,
    period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC),
    period_start: datetime | None = datetime(2026, 4, 1, tzinfo=UTC),
    year: int | None = 2027,
    quarter: int | None = 1,
    instrument: InstrumentIdentity | None = None,
    published: datetime = T - timedelta(days=3),
) -> FinancialFact:
    return FinancialFact(
        identifier, instrument or _instrument(), metric, Decimal("100"), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, period_start, period_end, year, quarter,
        StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "filing-" + identifier,
        "reference-" + identifier, published, published + timedelta(days=1), "financial-facts-v1",
        ("OFFICIAL",), (), None, (FinancialQualityFlag.COMPLETE,),
    )


def _observation(fact: FinancialFact):
    selection = select_financial_fact_vintages((fact,), canonical_instrument_id=fact.instrument.instrument_id, as_of=T, policy=POLICY).selections[0]
    result = materialize_financial_metric_observation(fact, selection=selection, schema=OBS_SCHEMA)
    assert result.observation is not None
    return result.observation, selection


def _attestation(observation, selection, *, selection_as_of: datetime = T, source_fact_id: str | None = None):
    values = dict(
        observation_fingerprint=observation.fingerprint,
        source_fact_id=source_fact_id or observation.source_fact_id,
        selection_result_fingerprint=selection.fingerprint,
        selection_as_of=selection_as_of,
        selector_policy_id=selection.policy_id,
        selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=observation.schema_id,
        observation_schema_version=observation.schema_version,
        observation_schema_fingerprint=observation.schema_fingerprint,
    )
    return FinancialResearchObservationAttestation(
        **values, fingerprint=contract.manifest_fingerprint(**contract._semantic_values(values))
    )


def _selection_failure(*, key, status=FinancialFactVintageSelectionStatus.UNAVAILABLE, reason=FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT, as_of: datetime = T):
    values = dict(
        canonical_instrument_id="NSE:ALPHA", semantic_key=key,
        stage=FinancialResearchInputFailureStage.SELECTION, selection_as_of=as_of,
        selection_status=status, materialization_status=None, reason_codes=(reason,), source_fact_id=None,
        selection_result_fingerprint="selection-failure-" + status.value,
        materialization_result_fingerprint=None, selector_policy_id=POLICY.policy_id,
        selector_policy_version=POLICY.version, selector_policy_fingerprint=POLICY.fingerprint,
        observation_schema_id=OBS_SCHEMA.schema_id, observation_schema_version=OBS_SCHEMA.version,
        observation_schema_fingerprint=OBS_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values, fingerprint=contract.manifest_fingerprint(**contract._semantic_values(values))
    )


def _materialization_failure(*, key, source_fact_id: str, selection_fingerprint: str):
    values = dict(
        canonical_instrument_id="NSE:ALPHA", semantic_key=key,
        stage=FinancialResearchInputFailureStage.MATERIALIZATION, selection_as_of=T,
        selection_status=FinancialFactVintageSelectionStatus.SELECTED,
        materialization_status=FinancialMetricObservationMaterializationStatus.REJECTED,
        reason_codes=(FinancialMetricObservationMaterializationReason.REPRESENTATION_REQUIRED,),
        source_fact_id=source_fact_id, selection_result_fingerprint=selection_fingerprint,
        materialization_result_fingerprint="materialization-rejected", selector_policy_id=POLICY.policy_id,
        selector_policy_version=POLICY.version, selector_policy_fingerprint=POLICY.fingerprint,
        observation_schema_id=OBS_SCHEMA.schema_id, observation_schema_version=OBS_SCHEMA.version,
        observation_schema_fingerprint=OBS_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values, fingerprint=contract.manifest_fingerprint(**contract._semantic_values(values))
    )


def _build(observations=(), attestations=(), failures=(), *, as_of: datetime = T, schema=SCHEMA):
    return build_financial_research_observation_bundle(
        canonical_instrument_id="NSE:ALPHA", as_of=as_of, observations=tuple(observations),
        attestations=tuple(attestations), failures=tuple(failures), schema=schema,
    )


def test_builder_returns_immutable_canonical_bundle_with_exact_frozen_lineage() -> None:
    observation, selection = _observation(_fact("q1"))
    bundle = _build((observation,), (_attestation(observation, selection),))
    assert bundle.canonical_instrument_id == "NSE:ALPHA"
    assert bundle.as_of == T
    assert bundle.knowledge_mode is FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME
    assert bundle.bundle_schema_fingerprint == SCHEMA.fingerprint
    with pytest.raises(FrozenInstanceError):
        bundle.as_of = T + timedelta(days=1)


def test_builder_is_input_order_independent_for_observations_attestations_and_failures() -> None:
    first, first_selection = _observation(_fact("q1"))
    second, second_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC)))
    future = _fact("future", metric=FinancialMetric.PAT, published=T + timedelta(days=1))
    future_selection = select_financial_fact_vintages((future,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY).selections[0]
    failure = _selection_failure(key=future_selection.semantic_key)
    forward = _build((first, second), (_attestation(first, first_selection), _attestation(second, second_selection)), (failure,))
    reverse = _build((second, first), (_attestation(second, second_selection), _attestation(first, first_selection)), (failure,))
    assert reverse == forward
    assert reverse.fingerprint == forward.fingerprint
    assert tuple(item.fingerprint for item in reverse.observations) == tuple(
        item.fingerprint for item in sorted((first, second), key=contract._observation_key)
    )


def test_exact_schema_is_required_while_frozen_inactive_state_is_accepted() -> None:
    assert not SCHEMA.selected_for_future_bundle and not SCHEMA.active
    assert _build().bundle_schema_fingerprint == SCHEMA.fingerprint
    altered = copy.copy(SCHEMA)
    object.__setattr__(altered, "version", "v2-approved")
    with pytest.raises(ValueError, match="EXACT_SCHEMA_REQUIRED|SCHEMA_TAMPERED"):
        _build(schema=altered)


def test_instrument_as_of_visibility_and_lineage_rules_fail_closed() -> None:
    observation, selection = _observation(_fact("q1"))
    attestation = _attestation(observation, selection)
    assert _build((observation,), (attestation,)).observations[0].visible_as_of < T
    with pytest.raises(ValueError, match="BUNDLE_AS_OF_TIMEZONE_REQUIRED"):
        _build((observation,), (attestation,), as_of=datetime(2026, 8, 29, 10))
    with pytest.raises(ValueError, match="ATTESTATION_BINDING_INVALID"):
        _build((observation,), (_attestation(observation, selection, selection_as_of=T - timedelta(seconds=1)),))
    foreign, foreign_selection = _observation(_fact("foreign", instrument=_instrument("NSE:BETA")))
    with pytest.raises(ValueError, match="OBSERVATION_SCOPE_INVALID"):
        _build((foreign,), (_attestation(foreign, foreign_selection),))
    object.__setattr__(observation, "visible_as_of", T + timedelta(seconds=1))
    with pytest.raises(ValueError, match="OBSERVATION_TAMPERED"):
        _build((observation,), (attestation,))


def test_one_to_one_attestation_binding_rejects_missing_orphan_duplicate_and_wrong_source() -> None:
    observation, selection = _observation(_fact("q1"))
    attestation = _attestation(observation, selection)
    with pytest.raises(ValueError, match="ATTESTATION_COVERAGE_INVALID"):
        _build((observation,), ())
    with pytest.raises(ValueError, match="DUPLICATE_ATTESTATION"):
        _build((observation,), (attestation, attestation))
    wrong_source = _attestation(observation, selection, source_fact_id="other")
    with pytest.raises(ValueError, match="ATTESTATION_BINDING_INVALID"):
        _build((observation,), (wrong_source,))
    other, other_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC)))
    with pytest.raises(ValueError, match="ATTESTATION_COVERAGE_INVALID"):
        _build((observation,), (_attestation(other, other_selection),))


def test_complete_partial_and_multiple_periods_are_preserved_without_latest_reduction() -> None:
    complete, complete_selection = _observation(_fact("q1"))
    partial, partial_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC), period_start=None, year=None, quarter=None))
    bundle = _build((complete, partial), (_attestation(complete, complete_selection), _attestation(partial, partial_selection)))
    assert {item.period_identity.strength for item in bundle.observations} == {
        FinancialMetricPeriodIdentityStrength.COMPLETE, FinancialMetricPeriodIdentityStrength.PARTIAL,
    }
    assert len(bundle.observations) == 2


def test_duplicate_semantic_collision_and_observation_failure_contradiction_fail_closed() -> None:
    observation, selection = _observation(_fact("q1"))
    attestation = _attestation(observation, selection)
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION"):
        _build((observation, observation), (attestation,))
    collision, collision_selection = _observation(_fact("different-source"))
    object.__setattr__(collision, "source_fact_id", "other")
    with pytest.raises(ValueError, match="OBSERVATION_TAMPERED"):
        _build((observation, collision), (attestation, _attestation(collision, collision_selection)))
    conflicting = _selection_failure(
        key=selection.semantic_key,
        status=FinancialFactVintageSelectionStatus.CONFLICTED,
        reason=FinancialFactVintageSelectionReason.UNRESOLVED_FACT_CONFLICT,
    )
    with pytest.raises(ValueError, match="OBSERVATION_FAILURE_CONTRADICTION"):
        _build((observation,), (attestation,), (conflicting,))
    rejected = _materialization_failure(key=selection.semantic_key, source_fact_id=observation.source_fact_id, selection_fingerprint=selection.fingerprint)
    with pytest.raises(ValueError, match="OBSERVATION_FAILURE_CONTRADICTION"):
        _build((observation,), (attestation,), (rejected,))


def test_typed_upstream_failures_are_preserved_and_nonconflicting_entries_coexist() -> None:
    observation, selection = _observation(_fact("revenue"))
    unavailable = _selection_failure(
        key=select_financial_fact_vintages((_fact("pat", metric=FinancialMetric.PAT, published=T + timedelta(days=1)),), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY).selections[0].semantic_key
    )
    bundle = _build((observation,), (_attestation(observation, selection),), (unavailable,))
    assert bundle.failures == (unavailable,)
    assert bundle.failures[0].stage is FinancialResearchInputFailureStage.SELECTION
    assert bundle.failures[0].selection_status is FinancialFactVintageSelectionStatus.UNAVAILABLE
    assert bundle.failures[0].reason_codes == (FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT,)


def test_duplicate_failure_and_tampered_attestation_or_failure_fail_closed() -> None:
    future = _fact("future", published=T + timedelta(days=1))
    selection = select_financial_fact_vintages((future,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY).selections[0]
    failure = _selection_failure(key=selection.semantic_key)
    with pytest.raises(ValueError, match="DUPLICATE_FAILURE"):
        _build(failures=(failure, failure))
    object.__setattr__(failure, "selection_result_fingerprint", "tampered")
    with pytest.raises(ValueError, match="FAILURE_TAMPERED"):
        _build(failures=(failure,))


def test_builder_accepts_only_derived_artifacts_and_has_no_operational_dependencies() -> None:
    source = inspect.getsource(__import__("app.fundamentals.financial_research_observation_bundle_builder", fromlist=["*"]))
    for forbidden in (
        "FinancialFact", "select_financial_fact_vintages", "materialize_financial_metric_observation",
        "BrainResearchComparisonState", "ResearchStateDelta", "SQLite", "PostgreSQL", "sqlite3",
        "requests", "urllib", "FastAPI", "APIRouter", "FinancialMetricTrajectory", "QoQ", "YoY",
        "TTM", "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "datetime.now", "time.time",
    ):
        assert forbidden not in source
    with pytest.raises(ValueError, match="OBSERVATION_TYPE_REQUIRED"):
        _build(observations=(object(),))
    with pytest.raises(ValueError, match="ATTESTATION_TYPE_REQUIRED"):
        _build(attestations=(object(),))
    with pytest.raises(ValueError, match="FAILURE_TYPE_REQUIRED"):
        _build(failures=(object(),))
