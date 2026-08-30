"""U14D-6U pure v2 Shared-Brain financial integration tests."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

import app.intelligence.brain_research_comparison_state_v2 as module
from app.data_sources.models import FundamentalFactKind
from app.domain.models import FreshnessStatus
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_metric_observation_schema import CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA
from app.fundamentals.financial_research_observation_bundle_builder import build_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
)
import app.fundamentals.financial_research_observation_bundle_schema as bundle_contract
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA
from app.fundamentals.models import (
    FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag,
    FinancialValueBasis, NumericScale, StatementScope,
)
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    ResearchComparabilityDomain,
)
from app.intelligence.brain_research_comparison_state import build_brain_research_comparison_state
from app.intelligence.brain_research_comparison_state_v2 import build_brain_research_comparison_state_v2
from app.intelligence.research_state_delta import (
    ResearchMetricChangeKind, ResearchStateDeltaError, compare_brain_research_states,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference, IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T1 = datetime(2026, 8, 1, 10, tzinfo=UTC)
T2 = T1 + timedelta(days=1)


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(identifier: str, *, value: str = "100", period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC), as_of: datetime = T1, partial: bool = False) -> FinancialFact:
    return FinancialFact(
        identifier, _instrument(), FinancialMetric.REVENUE, Decimal(value), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY,
        None if partial else datetime(2026, 4, 1, tzinfo=UTC), period_end,
        None if partial else 2027, None if partial else (1 if period_end.month == 6 else 2),
        StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL", f"filing-{identifier}",
        f"ref-{identifier}", as_of - timedelta(days=3), as_of - timedelta(days=2), "financial-facts-v1",
        ("OFFICIAL",), (), None, (FinancialQualityFlag.COMPLETE,),
    )


def _prepared(fact: FinancialFact, *, as_of: datetime):
    selection = select_financial_fact_vintages(
        (fact,), canonical_instrument_id="NSE:ALPHA", as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    ).selections[0]
    result = materialize_financial_metric_observation(
        fact, selection=selection, schema=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    )
    assert result.observation is not None
    return result.observation, selection


def _bundle(*items, as_of: datetime, failures=()):
    observations, selections = zip(*items) if items else ((), ())
    attestations = tuple(
        FinancialResearchObservationAttestation(
            observation_fingerprint=o.fingerprint, source_fact_id=o.source_fact_id,
            selection_result_fingerprint=s.fingerprint, selection_as_of=as_of,
            selector_policy_id=s.policy_id, selector_policy_version=s.policy_version,
            selector_policy_fingerprint=s.policy_fingerprint, observation_schema_id=o.schema_id,
            observation_schema_version=o.schema_version, observation_schema_fingerprint=o.schema_fingerprint,
            fingerprint=bundle_contract.manifest_fingerprint(**bundle_contract._semantic_values({
                "observation_fingerprint": o.fingerprint, "source_fact_id": o.source_fact_id,
                "selection_result_fingerprint": s.fingerprint, "selection_as_of": as_of,
                "selector_policy_id": s.policy_id, "selector_policy_version": s.policy_version,
                "selector_policy_fingerprint": s.policy_fingerprint, "observation_schema_id": o.schema_id,
                "observation_schema_version": o.schema_version, "observation_schema_fingerprint": o.schema_fingerprint,
            })),
        ) for o, s in zip(observations, selections)
    )
    return build_financial_research_observation_bundle(
        canonical_instrument_id="NSE:ALPHA", as_of=as_of, observations=tuple(observations),
        attestations=attestations, failures=tuple(failures),
        schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    )


def _failure(*, as_of: datetime) -> FinancialResearchInputFailure:
    future = _fact("future", as_of=as_of + timedelta(days=2))
    selection = select_financial_fact_vintages(
        (future,), canonical_instrument_id="NSE:ALPHA", as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    ).selections[0]
    values = dict(
        canonical_instrument_id="NSE:ALPHA", semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.SELECTION,
        selection_as_of=as_of, selection_status=FinancialFactVintageSelectionStatus.UNAVAILABLE,
        materialization_status=None, reason_codes=(FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT,),
        source_fact_id=None, selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=None,
        selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.schema_id,
        observation_schema_version=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.version,
        observation_schema_fingerprint=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values,
        fingerprint=bundle_contract.manifest_fingerprint(**bundle_contract._semantic_values(values)),
    )


def _unified(as_of: datetime, *, reference: bool = True):
    references = ()
    if reference:
        references = (IntelligenceEvidenceReference(
            domain=IntelligenceEvidenceDomain.FUNDAMENTALS,
            availability=IntelligenceEvidenceAvailability.AVAILABLE,
            artifact_ids=("financial-reference",), artifact_fingerprints=("financial-reference-fp",),
            evidence_as_of=as_of, observed_at=as_of, freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source-fp",
            historical_integrity_reference=None, warnings=(),
        ),)
    return create_unified_intelligence_state(
        canonical_instrument_id="NSE:ALPHA", as_of=as_of, evaluation_session=as_of,
        state_schema_version="unified-v1", intelligence_contract_version="shared-brain-v1",
        evidence_references=references, completeness=IntelligenceStateCompleteness.PARTIAL,
    )


def _v2(bundle, wrappers, *, as_of: datetime, failures=None, reference: bool = True):
    return build_brain_research_comparison_state_v2(
        _unified(as_of, reference=reference), comparability_policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
        financial_bundle=bundle, financial_wrappers=wrappers,
        financial_failures=bundle.failures if failures is None else failures,
    )


def _financial(state):
    return next(value for value in state.dimensions if value.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)


def test_v2_builder_is_immutable_deterministic_and_retains_reference_plus_numeric_wrapper() -> None:
    observation, selection = _prepared(_fact("q1"), as_of=T1)
    bundle = _bundle((observation, selection), as_of=T1)
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)
    first = _v2(bundle, wrappers, as_of=T1)
    second = _v2(bundle, tuple(reversed(wrappers)), as_of=T1)
    assert first == second and first.fingerprint == second.fingerprint
    assert (first.state_schema_version, first.research_methodology_id, first.research_methodology_version) == (
        "brain-research-comparison-state-v2", "shared-brain-research-comparison", "v2",
    )
    financial = _financial(first)
    assert wrappers[0] in financial.observations
    assert any(item.value_type.value == "ARTIFACT_REFERENCE" for item in financial.observations)
    with pytest.raises(FrozenInstanceError):
        first.state_id = "replacement"  # type: ignore[misc]


def test_v2_requires_exact_bundle_wrapper_failure_instrument_and_as_of_binding() -> None:
    observation, selection = _prepared(_fact("q1"), as_of=T1)
    bundle = _bundle((observation, selection), as_of=T1)
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)
    with pytest.raises(Exception, match="WRAPPER_COUNT_INVALID"):
        _v2(bundle, (), as_of=T1)
    with pytest.raises(Exception, match="FAILURE_BINDING_INVALID"):
        _v2(bundle, wrappers, as_of=T1, failures=(_failure(as_of=T1),))
    with pytest.raises(Exception, match="AS_OF_MISMATCH"):
        _v2(bundle, wrappers, as_of=T2)
    foreign = object.__new__(type(bundle))
    for name in bundle.__dataclass_fields__:
        object.__setattr__(foreign, name, getattr(bundle, name))
    object.__setattr__(foreign, "canonical_instrument_id", "NSE:OTHER")
    with pytest.raises(Exception, match="BUNDLE_INVALID|INSTRUMENT_MISMATCH"):
        _v2(foreign, wrappers, as_of=T1)


def test_v2_multiple_periods_and_failure_only_bundle_are_factual_and_dimension_local() -> None:
    q1, s1 = _prepared(_fact("q1"), as_of=T1)
    q2, s2 = _prepared(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC)), as_of=T1)
    bundle = _bundle((q2, s2), (q1, s1), as_of=T1)
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)
    state = _v2(bundle, tuple(reversed(wrappers)), as_of=T1)
    numeric = [item for item in _financial(state).observations if item.value_type.value == "FACTUAL_VALUE"]
    assert len(numeric) == 2 and {item.metric_id for item in numeric} == {"REVENUE"}

    failure = _failure(as_of=T1)
    failed_bundle = _bundle(as_of=T1, failures=(failure,))
    failed = _v2(failed_bundle, (), as_of=T1, failures=(failure,), reference=False)
    dim = _financial(failed)
    assert dim.availability is IntelligenceEvidenceAvailability.PARTIAL
    assert not [item for item in dim.observations if item.value_type.value == "FACTUAL_VALUE"]
    assert "FINANCIAL_INPUT_SELECTION_UNAVAILABLE" in dim.blockers
    assert "FINANCIAL_INPUT_SELECTION_UNAVAILABLE" not in failed.blockers


def test_v2_validates_exact_wrapper_mapping_and_duplicate_full_slots() -> None:
    observation, selection = _prepared(_fact("q1"), as_of=T1)
    bundle = _bundle((observation, selection), as_of=T1)
    wrapper = wrap_financial_research_observation_bundle(bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA)[0]
    with pytest.raises(Exception, match="WRAPPER_BINDING_INVALID|WRAPPER_MAPPING_INVALID"):
        _v2(bundle, (replace(wrapper, value=Decimal("101")),), as_of=T1)
    with pytest.raises(Exception, match="WRAPPER_COUNT_INVALID"):
        _v2(bundle, (wrapper, wrapper), as_of=T1)


def test_v2_states_use_existing_generic_delta_and_reject_cross_version() -> None:
    original, s1 = _prepared(_fact("q1", value="100", as_of=T1), as_of=T1)
    revised, s2 = _prepared(_fact("revised", value="95", as_of=T2), as_of=T2)
    first_bundle = _bundle((original, s1), as_of=T1)
    second_bundle = _bundle((revised, s2), as_of=T2)
    first = _v2(first_bundle, wrap_financial_research_observation_bundle(first_bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA), as_of=T1)
    second = _v2(second_bundle, wrap_financial_research_observation_bundle(second_bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA), as_of=T2)
    delta = compare_brain_research_states(first, second, policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2)
    financial = next(item for item in delta.dimension_deltas if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)
    assert any(item.change_kind is ResearchMetricChangeKind.VALUE_CHANGED for item in financial.observation_deltas)
    v1 = build_brain_research_comparison_state(_unified(T1), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    with pytest.raises(ResearchStateDeltaError, match="CROSS_VERSION_NON_COMPARABLE"):
        compare_brain_research_states(v1, second, policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2)


def test_v2_partial_financial_periods_remain_factual_but_numeric_delta_is_insufficient() -> None:
    first_observation, s1 = _prepared(_fact("partial-1", as_of=T1, partial=True), as_of=T1)
    second_observation, s2 = _prepared(_fact("partial-2", as_of=T2, partial=True), as_of=T2)
    first_bundle = _bundle((first_observation, s1), as_of=T1)
    second_bundle = _bundle((second_observation, s2), as_of=T2)
    first = _v2(first_bundle, wrap_financial_research_observation_bundle(first_bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA), as_of=T1)
    second = _v2(second_bundle, wrap_financial_research_observation_bundle(second_bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA), as_of=T2)
    delta = compare_brain_research_states(first, second, policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2)
    financial = next(item for item in delta.dimension_deltas if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)
    assert any(item.comparison_status.value == "INSUFFICIENT" for item in financial.observation_deltas)


def test_v2_module_is_pure_and_never_calls_upstream_financial_engines() -> None:
    source = inspect.getsource(module)
    for forbidden in (
        "wrap_financial_research_observation_bundle(", "build_financial_research_observation_bundle(",
        "select_financial_fact_vintages(", "materialize_financial_metric_observation(",
        "sqlite3", "requests", "urlopen", "datetime.now", "FinancialMetricTrajectory", "QoQ", "YoY", "TTM",
        "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "CREATE TABLE",
    ):
        assert forbidden not in source
