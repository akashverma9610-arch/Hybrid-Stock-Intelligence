from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import copy
import inspect

import pytest

import app.fundamentals.financial_research_observation_bundle_schema as bundle_contract
import app.fundamentals.financial_research_observation_wrapper as wrapper_module
from app.data_sources.models import FundamentalFactKind
from app.domain.models import FreshnessStatus
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import materialize_financial_metric_observation
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricPeriodIdentityStrength,
)
from app.fundamentals.financial_research_observation_bundle_builder import build_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
)
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialQualityFlag,
    FinancialValueBasis,
    NumericScale,
    StatementScope,
)
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
)
from app.intelligence.brain_research_comparison_state import (
    build_brain_research_comparison_state,
    research_metric_observation_fingerprint,
)
from app.intelligence.research_state_delta import (
    ResearchMetricChangeKind,
    compare_brain_research_states,
    research_observation_slot_key,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceStateCompleteness,
    create_unified_intelligence_state,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T1 = datetime(2026, 8, 1, 10, tzinfo=UTC)
T2 = T1 + timedelta(days=1)
POLICY = CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY
OBS_SCHEMA = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA
WRAPPER_SCHEMA = CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ALPHA")


def _fact(identifier: str, *, value: str = "100", metric: FinancialMetric = FinancialMetric.REVENUE, period_end: datetime = datetime(2026, 6, 30, tzinfo=UTC), period_start: datetime | None = datetime(2026, 4, 1, tzinfo=UTC), year: int | None = 2027, quarter: int | None = 1, as_of: datetime = T1) -> FinancialFact:
    return FinancialFact(
        identifier, _instrument(), metric, Decimal(value), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, FinancialValueBasis.QUARTER_ONLY, period_start, period_end, year, quarter,
        StatementScope.CONSOLIDATED, FundamentalFactKind.REPORTED, "BSE_OFFICIAL", "filing-" + identifier,
        "reference-" + identifier, as_of - timedelta(days=3), as_of - timedelta(days=2), "financial-facts-v1",
        ("OFFICIAL",), (), None, (FinancialQualityFlag.COMPLETE,),
    )


def _observation(fact: FinancialFact, *, as_of: datetime):
    selection = select_financial_fact_vintages((fact,), canonical_instrument_id="NSE:ALPHA", as_of=as_of, policy=POLICY).selections[0]
    result = materialize_financial_metric_observation(fact, selection=selection, schema=OBS_SCHEMA)
    assert result.observation is not None
    return result.observation, selection


def _attestation(observation, selection, *, as_of: datetime):
    values = dict(
        observation_fingerprint=observation.fingerprint, source_fact_id=observation.source_fact_id,
        selection_result_fingerprint=selection.fingerprint, selection_as_of=as_of,
        selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint, observation_schema_id=observation.schema_id,
        observation_schema_version=observation.schema_version, observation_schema_fingerprint=observation.schema_fingerprint,
    )
    return FinancialResearchObservationAttestation(
        **values, fingerprint=bundle_contract.manifest_fingerprint(**bundle_contract._semantic_values(values))
    )


def _failure(*, as_of: datetime):
    future = _fact("future", metric=FinancialMetric.PAT, as_of=as_of + timedelta(days=2))
    selection = select_financial_fact_vintages((future,), canonical_instrument_id="NSE:ALPHA", as_of=as_of, policy=POLICY).selections[0]
    values = dict(
        canonical_instrument_id="NSE:ALPHA", semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.SELECTION, selection_as_of=as_of,
        selection_status=FinancialFactVintageSelectionStatus.UNAVAILABLE, materialization_status=None,
        reason_codes=(FinancialFactVintageSelectionReason.NO_PIT_ELIGIBLE_FACT,), source_fact_id=None,
        selection_result_fingerprint=selection.fingerprint, materialization_result_fingerprint=None,
        selector_policy_id=POLICY.policy_id, selector_policy_version=POLICY.version,
        selector_policy_fingerprint=POLICY.fingerprint, observation_schema_id=OBS_SCHEMA.schema_id,
        observation_schema_version=OBS_SCHEMA.version, observation_schema_fingerprint=OBS_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values, fingerprint=bundle_contract.manifest_fingerprint(**bundle_contract._semantic_values(values))
    )


def _bundle(*items, as_of: datetime, failures=()):
    observations, selections = zip(*items) if items else ((), ())
    return build_financial_research_observation_bundle(
        canonical_instrument_id="NSE:ALPHA", as_of=as_of, observations=tuple(observations),
        attestations=tuple(_attestation(observation, selection, as_of=as_of) for observation, selection in zip(observations, selections)),
        failures=tuple(failures), schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    )


def _state(at: datetime, observation):
    reference = IntelligenceEvidenceReference(
        domain=IntelligenceEvidenceDomain.FUNDAMENTALS, availability=IntelligenceEvidenceAvailability.AVAILABLE,
        artifact_ids=("financial-evidence",), artifact_fingerprints=("financial-evidence-fingerprint",),
        evidence_as_of=at, observed_at=at, freshness_status=FreshnessStatus.UNKNOWN,
        freshness_policy_reference="freshness-v1", source_provenance_fingerprint="source-fingerprint",
        historical_integrity_reference=None, warnings=(),
    )
    return build_brain_research_comparison_state(
        create_unified_intelligence_state(
            canonical_instrument_id="NSE:ALPHA", as_of=at, evaluation_session=at,
            state_schema_version="unified-v1", intelligence_contract_version="shared-brain-v1",
            evidence_references=(reference,), completeness=IntelligenceStateCompleteness.PARTIAL,
        ), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY, explicit_observations=(observation,),
    )


def test_adapter_maps_every_successful_observation_losslessly_and_deterministically() -> None:
    observation, selection = _observation(_fact("q1", as_of=T1), as_of=T1)
    bundle = _bundle((observation, selection), as_of=T1)
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA)
    assert isinstance(wrappers, tuple) and len(wrappers) == len(bundle.observations) == 1
    wrapper = wrappers[0]
    assert wrapper.dimension is ResearchComparabilityDomain.FINANCIAL_RAW
    assert wrapper.metric_id == observation.metric.value and wrapper.value == observation.value
    assert wrapper.unit == observation.unit and wrapper.scale == observation.scale.value
    assert wrapper.scope == observation.statement_scope.value and wrapper.basis == observation.period_identity.value_basis.value
    assert wrapper.source_artifact_type == "FINANCIAL_METRIC_OBSERVATION"
    assert wrapper.source_artifact_fingerprint == observation.fingerprint
    assert wrapper.identity_components == tuple(sorted(wrapper.identity_components))
    assert wrapper.lineage_components == tuple(sorted(wrapper.lineage_components))
    assert dict(wrapper.identity_components)["financial_source_role"] == FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION.value
    assert dict(wrapper.lineage_components)["financial_source_fact_id"] == observation.source_fact_id
    assert dict(wrapper.lineage_components)["financial_bundle_fingerprint"] == bundle.fingerprint
    assert wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA) == wrappers


def test_adapter_preserves_period_slot_identity_and_non_slot_lineage() -> None:
    q1, q1_selection = _observation(_fact("q1", as_of=T1), as_of=T1)
    q2, q2_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC), as_of=T1), as_of=T1)
    wrappers = wrap_financial_research_observation_bundle(_bundle((q2, q2_selection), (q1, q1_selection), as_of=T1), wrapper_schema=WRAPPER_SCHEMA)
    assert tuple(item.metric_id for item in wrappers) == ("REVENUE", "REVENUE")
    assert research_observation_slot_key(wrappers[0]) != research_observation_slot_key(wrappers[1])
    identity = dict(wrappers[0].identity_components)
    assert {"financial_currency", "financial_fact_kind", "financial_period_fingerprint", "financial_period_strength", "financial_normalization_identity"} <= set(identity)
    lineage = dict(wrappers[0].lineage_components)
    assert {"financial_selection_as_of", "financial_selector_policy_fingerprint", "financial_bundle_as_of", "financial_visible_as_of", "financial_source_semantic_fingerprint", "financial_quality_flags", "financial_provenance"} <= set(lineage)


def test_adapter_allows_partial_excludes_failures_and_rejects_wrong_schema() -> None:
    partial, partial_selection = _observation(_fact("partial", period_start=None, year=None, quarter=None, as_of=T1), as_of=T1)
    assert partial.period_identity.strength is FinancialMetricPeriodIdentityStrength.PARTIAL
    bundle = _bundle((partial, partial_selection), as_of=T1, failures=(_failure(as_of=T1),))
    wrappers = wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA)
    assert len(wrappers) == 1 and dict(wrappers[0].identity_components)["financial_period_strength"] == "PARTIAL"
    assert all("FAILURE" not in item.metric_id for item in wrappers)
    bad = copy.copy(WRAPPER_SCHEMA)
    object.__setattr__(bad, "fingerprint", "0" * 64)
    with pytest.raises(ValueError, match="SCHEMA_TAMPERED|EXACT_SCHEMA_REQUIRED"):
        wrap_financial_research_observation_bundle(bundle, wrapper_schema=bad)


def test_same_period_revisions_keep_slot_and_remain_delta_compatible() -> None:
    original, original_selection = _observation(_fact("original", value="100", as_of=T1), as_of=T1)
    revised, revised_selection = _observation(_fact("revised", value="95", as_of=T2), as_of=T2)
    original_wrapper = wrap_financial_research_observation_bundle(_bundle((original, original_selection), as_of=T1), wrapper_schema=WRAPPER_SCHEMA)[0]
    revised_wrapper = wrap_financial_research_observation_bundle(_bundle((revised, revised_selection), as_of=T2), wrapper_schema=WRAPPER_SCHEMA)[0]
    assert research_observation_slot_key(original_wrapper) == research_observation_slot_key(revised_wrapper)
    assert original_wrapper.value != revised_wrapper.value
    assert original_wrapper.lineage_components != revised_wrapper.lineage_components
    assert research_metric_observation_fingerprint(original_wrapper) != research_metric_observation_fingerprint(revised_wrapper)
    delta = compare_brain_research_states(_state(T1, original_wrapper), _state(T2, revised_wrapper), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    financial = next(item for item in delta.dimension_deltas if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)
    assert financial.observation_deltas[-1].change_kind is ResearchMetricChangeKind.VALUE_CHANGED

    lineage_only, lineage_only_selection = _observation(_fact("lineage-only", value="100", as_of=T2), as_of=T2)
    lineage_only_wrapper = wrap_financial_research_observation_bundle(_bundle((lineage_only, lineage_only_selection), as_of=T2), wrapper_schema=WRAPPER_SCHEMA)[0]
    assert research_observation_slot_key(original_wrapper) == research_observation_slot_key(lineage_only_wrapper)
    lineage_delta = compare_brain_research_states(_state(T1, original_wrapper), _state(T2, lineage_only_wrapper), policy=CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY)
    lineage_financial = next(item for item in lineage_delta.dimension_deltas if item.dimension is ResearchComparabilityDomain.FINANCIAL_RAW)
    assert lineage_financial.observation_deltas[-1].change_kind is ResearchMetricChangeKind.LINEAGE_CHANGED


def test_different_period_and_reference_role_never_share_a_numeric_wrapper_slot() -> None:
    q1, q1_selection = _observation(_fact("q1", as_of=T1), as_of=T1)
    q2, q2_selection = _observation(_fact("q2", period_end=datetime(2026, 9, 30, tzinfo=UTC), as_of=T1), as_of=T1)
    q1_wrapper, q2_wrapper = wrap_financial_research_observation_bundle(_bundle((q1, q1_selection), (q2, q2_selection), as_of=T1), wrapper_schema=WRAPPER_SCHEMA)
    assert research_observation_slot_key(q1_wrapper) != research_observation_slot_key(q2_wrapper)
    reference = replace(
        q1_wrapper,
        source_artifact_type="FINANCIAL_EVIDENCE_REFERENCE",
        identity_components=tuple(sorted(
            (*(item for item in q1_wrapper.identity_components if item[0] != "financial_source_role"),
             ("financial_source_role", FinancialObservationSourceRole.FINANCIAL_EVIDENCE_REFERENCE.value))
        )),
    )
    assert research_observation_slot_key(q1_wrapper) != research_observation_slot_key(reference)


def test_adapter_fails_closed_for_tampered_bundle_and_has_no_runtime_dependencies() -> None:
    observation, selection = _observation(_fact("q1", as_of=T1), as_of=T1)
    bundle = _bundle((observation, selection), as_of=T1)
    object.__setattr__(bundle, "fingerprint", "0" * 64)
    with pytest.raises(ValueError, match="BUNDLE_INVALID|BUNDLE_TAMPERED"):
        wrap_financial_research_observation_bundle(bundle, wrapper_schema=WRAPPER_SCHEMA)
    source = inspect.getsource(wrapper_module)
    for forbidden in (
        "FinancialFact", "select_financial_fact_vintages", "materialize_financial_metric_observation",
        "build_financial_research_observation_bundle", "sqlite3", "requests", "urllib", "FastAPI",
        "BrainResearchComparisonState", "FinancialMetricTrajectory", "QoQ", "YoY", "TTM",
        "THESIS_", "OPPORTUNITY_", "BUY", "SELL", "datetime.now",
    ):
        assert forbidden not in source
