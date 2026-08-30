from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

import app.fundamentals.financial_research_observation_bundle_schema as bundle_module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionMode,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricPeriodIdentityStrength,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
    FinancialResearchObservationBundle,
    FinancialResearchObservationBundleSchemaApprovalStatus,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
    financial_research_observation_bundle_fingerprint,
    financial_research_observation_bundle_schema_fingerprint,
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


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(identifier: str, *, metric: FinancialMetric = FinancialMetric.REVENUE, period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC), period_start: datetime | None = datetime(2026, 4, 1, tzinfo=UTC), year: int | None = 2027, quarter: int | None = 1, published: datetime = T - timedelta(days=3)) -> FinancialFact:
    return FinancialFact(identifier, _instrument(), metric, Decimal("100"), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, period_start, period_end, year, quarter,
        StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "filing-" + identifier,
        "reference-" + identifier, published, published + timedelta(days=1), "financial-facts-v1",
        ("OFFICIAL",), (), None, (FinancialQualityFlag.COMPLETE,))


def _selection(fact: FinancialFact):
    return select_financial_fact_vintages((fact,), canonical_instrument_id="NSE:ALPHA", as_of=T, policy=POLICY).selections[0]


def _observation(fact: FinancialFact):
    selection = _selection(fact)
    result = materialize_financial_metric_observation(fact, selection=selection, schema=OBS_SCHEMA)
    assert result.observation is not None
    return result.observation, selection


def _attestation(observation, selection, *, selection_as_of: datetime = T):
    values = dict(observation_fingerprint=observation.fingerprint, source_fact_id=observation.source_fact_id,
        selection_result_fingerprint=selection.fingerprint, selection_as_of=selection_as_of,
        selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint, observation_schema_id=observation.schema_id,
        observation_schema_version=observation.schema_version, observation_schema_fingerprint=observation.schema_fingerprint)
    return FinancialResearchObservationAttestation(**values, fingerprint=bundle_module.manifest_fingerprint(**bundle_module._semantic_values(values)))


def _bundle(observations=(), attestations=(), failures=()):
    values = dict(canonical_instrument_id="NSE:ALPHA", as_of=T,
        knowledge_mode=FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME,
        observation_schema_id=OBS_SCHEMA.schema_id, observation_schema_version=OBS_SCHEMA.version,
        observation_schema_fingerprint=OBS_SCHEMA.fingerprint, selector_policy_id=POLICY.policy_id,
        selector_policy_version=POLICY.version, selector_policy_fingerprint=POLICY.fingerprint,
        bundle_schema_id=SCHEMA.schema_id, bundle_schema_version=SCHEMA.version,
        bundle_schema_fingerprint=SCHEMA.fingerprint,
        observations=tuple(sorted(observations, key=bundle_module._observation_key)),
        attestations=tuple(sorted(attestations, key=lambda item: item.observation_fingerprint)),
        failures=tuple(sorted(failures, key=bundle_module._failure_key)))
    return FinancialResearchObservationBundle(**values, fingerprint=bundle_module.manifest_fingerprint(**bundle_module._semantic_values(values)))


def test_frozen_schema_identity_governance_lineage_and_determinism() -> None:
    assert (SCHEMA.schema_id, SCHEMA.version) == ("financial-research-observation-bundle-schema", "v1-approved")
    assert (SCHEMA.proposal_schema_id, SCHEMA.proposal_version) == ("financial-research-observation-bundle-schema", "v1-proposed")
    assert SCHEMA.approval_status is FinancialResearchObservationBundleSchemaApprovalStatus.APPROVED
    assert SCHEMA.approved_by == "human:Akash-Verma"
    assert not SCHEMA.selected_for_future_bundle and not SCHEMA.active
    assert financial_research_observation_bundle_schema_fingerprint(SCHEMA) == SCHEMA.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(SCHEMA, version="v2")


def test_attestation_is_immutable_deterministic_and_retains_exact_lineage() -> None:
    observation, selection = _observation(_fact("one"))
    value = _attestation(observation, selection)
    assert value.selection_as_of == T and value.observation_fingerprint == observation.fingerprint
    assert value.selection_result_fingerprint == selection.fingerprint
    assert financial_research_observation_attestation_fingerprint(value) == value.fingerprint
    with pytest.raises(FrozenInstanceError):
        value.source_fact_id = "changed"


def test_failure_stage_status_reasons_and_fingerprints_are_typed() -> None:
    future = _fact("future", published=T + timedelta(days=1))
    selection = _selection(future)
    values = dict(canonical_instrument_id="NSE:ALPHA", semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.SELECTION, selection_as_of=T,
        selection_status=selection.status, materialization_status=None,
        reason_codes=selection.reasons, source_fact_id=None, selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=None, selector_policy_id=selection.policy_id,
        selector_policy_version=selection.policy_version, selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=OBS_SCHEMA.schema_id, observation_schema_version=OBS_SCHEMA.version,
        observation_schema_fingerprint=OBS_SCHEMA.fingerprint)
    failure = FinancialResearchInputFailure(**values, fingerprint=bundle_module.manifest_fingerprint(**bundle_module._semantic_values(values)))
    assert failure.stage is FinancialResearchInputFailureStage.SELECTION
    assert financial_research_input_failure_fingerprint(failure) == failure.fingerprint
    with pytest.raises(FrozenInstanceError):
        failure.stage = FinancialResearchInputFailureStage.MATERIALIZATION


def test_bundle_is_immutable_same_as_of_and_preserves_visibility() -> None:
    observation, selection = _observation(_fact("one"))
    bundle = _bundle((observation,), (_attestation(observation, selection),))
    assert bundle.as_of == T and bundle.knowledge_mode is FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME
    assert observation.visible_as_of < bundle.as_of
    assert financial_research_observation_bundle_fingerprint(bundle) == bundle.fingerprint
    with pytest.raises(FrozenInstanceError):
        bundle.as_of = T


def test_multiple_periods_complete_and_partial_are_preserved_without_horizon() -> None:
    first, first_selection = _observation(_fact("q1"))
    second, second_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC), period_start=None, year=None, quarter=None))
    bundle = _bundle((first, second), (_attestation(first, first_selection), _attestation(second, second_selection)))
    assert len(bundle.observations) == 2
    assert {value.period_identity.strength for value in bundle.observations} == {FinancialMetricPeriodIdentityStrength.COMPLETE, FinancialMetricPeriodIdentityStrength.PARTIAL}


def test_same_as_of_duplicate_foreign_and_semantic_collision_fail_closed() -> None:
    observation, selection = _observation(_fact("one"))
    attestation = _attestation(observation, selection)
    with pytest.raises(ValueError, match="DUPLICATE_OBSERVATION"):
        _bundle((observation, observation), (attestation,))
    bad_attestation = _attestation(observation, selection, selection_as_of=T - timedelta(days=1))
    with pytest.raises(ValueError, match="ATTESTATION_BINDING_INVALID"):
        _bundle((observation,), (bad_attestation,))

    collision, collision_selection = _observation(_fact("two"))
    object.__setattr__(collision, "source_fact_id", "two")
    with pytest.raises(ValueError):
        _bundle((observation, collision), (attestation, _attestation(collision, collision_selection)))


def test_passive_contract_has_no_builder_or_runtime_dependency() -> None:
    source = inspect.getsource(bundle_module)
    for forbidden in (
        "build_financial_research_observation_bundle", "select_financial_fact_vintages",
        "materialize_financial_metric_observation", "BrainResearchComparisonState", "ResearchStateDelta",
        "SQLite", "PostgreSQL", "sqlite3", "requests", "urllib", "FastAPI", "APIRouter",
        "FinancialMetricTrajectory", "QoQ", "YoY", "TTM", "THESIS_", "OPPORTUNITY_", "BUY", "SELL",
    ):
        assert forbidden not in source
