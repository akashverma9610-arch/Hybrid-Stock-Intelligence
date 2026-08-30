"""Pure financial integration into the one Shared-Brain research state.

The v2 entry point accepts only an already validated Unified State, financial
bundle, generic numeric wrappers, and typed input failures.  It deliberately
does not select facts, materialize observations, build a bundle, or run the
wrapper adapter.  Existing v1 construction remains unchanged.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.domain.models import FreshnessStatus
from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricObservation,
    FinancialMetricPeriodIdentityStrength,
    financial_metric_observation_fingerprint,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationBundle,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
    financial_research_observation_bundle_fingerprint,
)
from app.fundamentals.financial_research_observation_wrapper_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
)
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    FinancialObservationSourceRole,
    FrozenBrainResearchComparabilityPolicy,
    ResearchComparabilityDomain,
    ResearchComparisonMode,
    ResearchSourceEligibility,
)
from app.intelligence.brain_research_comparison_state import (
    BrainResearchComparisonState,
    BrainResearchComparisonStateError,
    ResearchDimensionState,
    ResearchMetricObservation,
    ResearchMetricValueType,
    _UNIFIED_DOMAIN_MAP,
    _build_dimension,
    _observation_key,
    _semantic_values,
    _validate_source_state,
    brain_research_comparison_state_fingerprint_values,
    research_dimension_state_fingerprint_values,
    research_metric_observation_fingerprint,
)
from app.intelligence.brain_research_comparison_state_v2_schema import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA,
    FrozenBrainResearchComparisonStateV2Schema,
    brain_research_comparison_state_v2_schema_fingerprint,
)
from app.intelligence.research_state_delta import research_observation_slot_key
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    UnifiedIntelligenceState,
)


_NONE = "<NONE>"


def build_brain_research_comparison_state_v2(
    unified_state: UnifiedIntelligenceState,
    *,
    comparability_policy: FrozenBrainResearchComparabilityPolicy,
    financial_bundle: FinancialResearchObservationBundle,
    financial_wrappers: tuple[ResearchMetricObservation, ...],
    financial_failures: tuple[FinancialResearchInputFailure, ...],
) -> BrainResearchComparisonState:
    """Build one deterministic v2 factual state from explicit prepared inputs."""
    _validate_schema(CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA)
    _validate_unified_state(unified_state)
    _validate_policy(comparability_policy)
    _validate_bundle(financial_bundle, unified_state)
    failures = _validate_failures(financial_failures, financial_bundle)
    wrappers = _validate_wrappers(financial_wrappers, financial_bundle, unified_state.as_of)

    references = {value.domain: value for value in unified_state.evidence_references}
    dimensions: list[ResearchDimensionState] = []
    for domain in sorted(ResearchComparabilityDomain, key=lambda item: item.value):
        explicit = list(wrappers) if domain is ResearchComparabilityDomain.FINANCIAL_RAW else []
        dimension = _build_dimension(domain, references, explicit, comparability_policy)
        if domain is ResearchComparabilityDomain.FINANCIAL_RAW:
            dimension = _financial_dimension(
                dimension, financial_bundle=financial_bundle, wrappers=wrappers, failures=failures,
            )
        dimensions.append(dimension)
    canonical_dimensions = tuple(dimensions)
    warnings = tuple(sorted({
        warning for dimension in canonical_dimensions for warning in dimension.warnings
        if not warning.startswith("FINANCIAL_INPUT_")
    }))
    blockers = tuple(sorted({
        blocker for dimension in canonical_dimensions for blocker in dimension.blockers
        if not blocker.startswith("FINANCIAL_INPUT_")
    }))
    schema = CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA
    values = dict(
        canonical_instrument_id=unified_state.canonical_instrument_id,
        as_of=unified_state.as_of,
        evaluation_session=unified_state.evaluation_session,
        source_unified_state_id=unified_state.state_id,
        source_unified_state_fingerprint=unified_state.fingerprint,
        source_state_schema_version=unified_state.state_schema_version,
        source_intelligence_contract_version=unified_state.intelligence_contract_version,
        state_schema_version=f"{schema.state_schema_id}-{schema.state_schema_version}",
        research_methodology_id=schema.research_methodology_id,
        research_methodology_version=schema.research_methodology_version,
        comparability_policy_id=comparability_policy.policy_id,
        comparability_policy_version=comparability_policy.version,
        comparability_policy_fingerprint=comparability_policy.fingerprint,
        comparison_mode=comparability_policy.comparison_mode,
        dimensions=canonical_dimensions,
        warnings=warnings,
        blockers=blockers,
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["state_id"] = f"brain-research-comparison-state-{seed[:24]}"
    return BrainResearchComparisonState(
        **values, fingerprint=brain_research_comparison_state_fingerprint_values(values),
    )


def _validate_schema(schema: FrozenBrainResearchComparisonStateV2Schema) -> None:
    if not isinstance(schema, FrozenBrainResearchComparisonStateV2Schema):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_SCHEMA_REQUIRED")
    if brain_research_comparison_state_v2_schema_fingerprint(schema) != schema.fingerprint:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_SCHEMA_TAMPERED")
    if schema != CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_EXACT_SCHEMA_REQUIRED")


def _validate_unified_state(unified_state: UnifiedIntelligenceState) -> None:
    if not isinstance(unified_state, UnifiedIntelligenceState):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_UNIFIED_STATE_REQUIRED")
    _validate_source_state(unified_state)


def _validate_policy(policy: FrozenBrainResearchComparabilityPolicy) -> None:
    expected = FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2
    if not isinstance(policy, FrozenBrainResearchComparabilityPolicy):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_COMPARABILITY_POLICY_REQUIRED")
    if (policy.policy_id, policy.version, policy.fingerprint) != (
        expected.policy_id, expected.version, expected.fingerprint,
    ):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_COMPARABILITY_POLICY_IDENTITY_INVALID")
    if policy.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_COMPARABILITY_POLICY_MODE_INVALID")


def _validate_bundle(bundle: FinancialResearchObservationBundle, unified_state: UnifiedIntelligenceState) -> None:
    if not isinstance(bundle, FinancialResearchObservationBundle):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_BUNDLE_REQUIRED")
    try:
        bundle.__post_init__()
    except (AttributeError, TypeError, ValueError) as error:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_BUNDLE_INVALID") from error
    if financial_research_observation_bundle_fingerprint(bundle) != bundle.fingerprint:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_BUNDLE_TAMPERED")
    if bundle.canonical_instrument_id != unified_state.canonical_instrument_id:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_INSTRUMENT_MISMATCH")
    if bundle.as_of != unified_state.as_of:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_AS_OF_MISMATCH")
    for attestation in bundle.attestations:
        if financial_research_observation_attestation_fingerprint(attestation) != attestation.fingerprint:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_ATTESTATION_TAMPERED")


def _validate_failures(
    values: tuple[FinancialResearchInputFailure, ...], bundle: FinancialResearchObservationBundle,
) -> tuple[FinancialResearchInputFailure, ...]:
    if not isinstance(values, tuple):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_FAILURES_TUPLE_REQUIRED")
    for value in values:
        if not isinstance(value, FinancialResearchInputFailure):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_FAILURE_TYPE_INVALID")
        try:
            value.__post_init__()
        except (AttributeError, TypeError, ValueError) as error:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_FAILURE_INVALID") from error
        if financial_research_input_failure_fingerprint(value) != value.fingerprint:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_FAILURE_TAMPERED")
    expected = {value.fingerprint for value in bundle.failures}
    supplied = {value.fingerprint for value in values}
    if len(values) != len(supplied) or expected != supplied:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_FAILURE_BINDING_INVALID")
    return tuple(sorted(values, key=_failure_key))


def _validate_wrappers(
    values: tuple[ResearchMetricObservation, ...], bundle: FinancialResearchObservationBundle, as_of: datetime,
) -> tuple[ResearchMetricObservation, ...]:
    if not isinstance(values, tuple):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPERS_TUPLE_REQUIRED")
    if len(values) != len(bundle.observations):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_COUNT_INVALID")
    expected = {value.fingerprint: value for value in bundle.observations}
    bound: set[str] = set()
    slots: set[tuple] = set()
    for wrapper in values:
        if not isinstance(wrapper, ResearchMetricObservation):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_TYPE_INVALID")
        try:
            wrapper.__post_init__()
        except (AttributeError, TypeError, ValueError) as error:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_INVALID") from error
        observation = expected.get(wrapper.source_artifact_fingerprint or "")
        if observation is None or observation.fingerprint in bound:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_BINDING_INVALID")
        _validate_wrapper_binding(wrapper, observation, bundle, as_of)
        slot = research_observation_slot_key(wrapper)
        if slot in slots:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_SLOT_DUPLICATE")
        slots.add(slot)
        bound.add(observation.fingerprint)
    if bound != set(expected):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_BINDING_INVALID")
    return tuple(sorted(values, key=_observation_key))


def _validate_wrapper_binding(
    wrapper: ResearchMetricObservation,
    observation: FinancialMetricObservation,
    bundle: FinancialResearchObservationBundle,
    as_of: datetime,
) -> None:
    schema = CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA
    period = observation.period_identity
    if observation.visible_as_of > as_of:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_VISIBLE_AFTER_AS_OF")
    if observation.period_identity.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_PERIOD_INSUFFICIENT")
    expected_scalars = (
        wrapper.dimension is ResearchComparabilityDomain.FINANCIAL_RAW,
        wrapper.value_type is ResearchMetricValueType.FACTUAL_VALUE,
        wrapper.metric_id == observation.metric.value,
        wrapper.value == observation.value,
        wrapper.unit == observation.unit,
        wrapper.scale == observation.scale.value,
        wrapper.basis == period.value_basis.value,
        wrapper.scope == observation.statement_scope.value,
        wrapper.period_identity == period.fingerprint,
        wrapper.effective_at == period.period_end,
        wrapper.published_at == observation.published_at,
        wrapper.methodology_id == schema.schema_id,
        wrapper.methodology_version == schema.version,
        wrapper.source_artifact_type == schema.source_artifact_type,
        wrapper.source_artifact_fingerprint == observation.fingerprint,
        wrapper.dependency_manifest_fingerprint == schema.fingerprint,
        wrapper.source_eligibility is ResearchSourceEligibility.PIT_REBUILDABLE,
        wrapper.freshness_status is FreshnessStatus.UNKNOWN,
        wrapper.reliability_lineage is None,
        wrapper.historical_integrity_lineage is None,
        not wrapper.warnings,
        not wrapper.blockers,
    )
    if not all(expected_scalars):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_MAPPING_INVALID")
    expected_identity = tuple(sorted({
        "financial_currency": observation.currency,
        "financial_fact_kind": observation.fact_kind.value,
        "financial_fiscal_quarter": _optional(period.fiscal_quarter),
        "financial_fiscal_year": _optional(period.fiscal_year),
        "financial_normalization_identity": observation.normalization_version,
        "financial_observation_schema_identity": _sequence((observation.schema_id, observation.schema_version, observation.schema_fingerprint)),
        "financial_period_basis": period.value_basis.value,
        "financial_period_end": _time(period.period_end),
        "financial_period_fingerprint": period.fingerprint,
        "financial_period_start": _optional_time(period.period_start),
        "financial_period_strength": period.strength.value,
        "financial_period_type": period.period_type.value,
        "financial_source_role": FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION.value,
        "financial_value_dimension": period.value_dimension.value,
    }.items()))
    expected_lineage = tuple(sorted({
        "financial_bundle_as_of": _time(bundle.as_of),
        "financial_bundle_fingerprint": bundle.fingerprint,
        "financial_bundle_schema_fingerprint": bundle.bundle_schema_fingerprint,
        "financial_bundle_schema_id": bundle.bundle_schema_id,
        "financial_bundle_schema_version": bundle.bundle_schema_version,
        "financial_filing_id": _optional(observation.filing_id),
        "financial_parent_fact_ids": _sequence(observation.parent_fact_ids),
        "financial_provenance": _sequence(observation.provenance),
        "financial_quality_flags": _sequence(tuple(item.value for item in observation.quality_flags)),
        "financial_received_at": _time(observation.received_at),
        "financial_revision_of_fact_id": _optional(observation.revision_of_fact_id),
        "financial_selection_as_of": _time(bundle.as_of),
        "financial_selection_result_fingerprint": observation.selection_result_fingerprint,
        "financial_selector_policy_fingerprint": observation.selection_policy_fingerprint,
        "financial_selector_policy_id": observation.selection_policy_id,
        "financial_selector_policy_version": observation.selection_policy_version,
        "financial_source_fact_id": observation.source_fact_id,
        "financial_source_name": observation.source,
        "financial_source_reference": _optional(observation.source_reference),
        "financial_source_semantic_fingerprint": observation.source_fact_semantic_fingerprint,
        "financial_visible_as_of": _time(observation.visible_as_of),
    }.items()))
    if wrapper.identity_components != expected_identity or wrapper.lineage_components != expected_lineage:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_WRAPPER_LINEAGE_INVALID")
    # Compute the generic artifact identity as a final invariant check.  It is
    # not stored separately, so no value is regenerated or substituted here.
    research_metric_observation_fingerprint(wrapper)


def _financial_dimension(
    base: ResearchDimensionState,
    *,
    financial_bundle: FinancialResearchObservationBundle,
    wrappers: tuple[ResearchMetricObservation, ...],
    failures: tuple[FinancialResearchInputFailure, ...],
) -> ResearchDimensionState:
    availability = base.availability
    if wrappers and availability is IntelligenceEvidenceAvailability.UNAVAILABLE:
        availability = IntelligenceEvidenceAvailability.AVAILABLE
    elif failures and not wrappers and availability is IntelligenceEvidenceAvailability.UNAVAILABLE:
        availability = IntelligenceEvidenceAvailability.PARTIAL
    failure_codes = _failure_codes(failures)
    methodology_lineage = tuple(sorted({
        *base.methodology_lineage,
        ("financial_bundle_schema", financial_bundle.bundle_schema_fingerprint),
        ("financial_observation_schema", financial_bundle.observation_schema_fingerprint),
        ("financial_selector_policy", financial_bundle.selector_policy_fingerprint),
        ("financial_wrapper_schema", CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA.fingerprint),
        ("state_v2_schema", CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA.fingerprint),
    }))
    # A particular bundle/wrapper fingerprint is evidence lineage, not a
    # methodology dependency.  Treating it as a dependency would make a valid
    # same-slot revision non-comparable before generic delta matching runs.
    dependency_lineage = base.dependency_lineage
    evidence_lineage = tuple(sorted({
        *base.evidence_lineage,
        ("financial_bundle", financial_bundle.fingerprint),
        *( (f"financial_failure:{value.fingerprint}", value.fingerprint) for value in failures ),
    }))
    values = dict(
        dimension=base.dimension,
        source_eligibility=base.source_eligibility,
        availability=availability,
        observations=base.observations,
        descriptor=base.descriptor,
        methodology_lineage=methodology_lineage,
        dependency_lineage=dependency_lineage,
        evidence_lineage=evidence_lineage,
        warnings=tuple(sorted({*base.warnings, *failure_codes})),
        blockers=tuple(sorted({*base.blockers, *failure_codes})),
    )
    return ResearchDimensionState(
        **values, fingerprint=research_dimension_state_fingerprint_values(values),
    )


def _failure_codes(values: tuple[FinancialResearchInputFailure, ...]) -> set[str]:
    codes: set[str] = set()
    for value in values:
        status = value.selection_status or value.materialization_status
        assert status is not None
        codes.add(f"FINANCIAL_INPUT_{value.stage.value}_{status.value}")
        codes.update(f"FINANCIAL_INPUT_REASON_{reason.value}" for reason in value.reason_codes)
    return codes


def _failure_key(value: FinancialResearchInputFailure) -> tuple:
    return (
        "" if value.semantic_key is None else "|".join(value.semantic_key.ordering_key()),
        value.stage.value,
        "" if value.selection_status is None else value.selection_status.value,
        "" if value.materialization_status is None else value.materialization_status.value,
        tuple(reason.value for reason in value.reason_codes),
        value.fingerprint,
    )


def _time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_V2_FINANCIAL_TIMEZONE_REQUIRED")
    return value.astimezone(UTC).isoformat()


def _optional_time(value: datetime | None) -> str:
    return _NONE if value is None else _time(value)


def _optional(value: object | None) -> str:
    return _NONE if value is None else str(value)


def _sequence(values: tuple[object, ...]) -> str:
    return json.dumps(tuple(str(value) for value in values), ensure_ascii=True, separators=(",", ":"))


__all__ = ("build_brain_research_comparison_state_v2",)
