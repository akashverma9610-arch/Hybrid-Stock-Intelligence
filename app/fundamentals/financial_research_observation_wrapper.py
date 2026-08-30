"""Pure lossless adaptation from a validated financial bundle to generic facts.

This module maps only already-materialized financial observations.  It does
not select, materialize, persist, integrate a Brain state, or interpret the
mapped values.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.domain.models import FreshnessStatus
from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricObservation,
    financial_metric_observation_fingerprint,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    FinancialResearchObservationBundle,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
    financial_research_observation_bundle_fingerprint,
)
from app.fundamentals.financial_research_observation_wrapper_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
    FrozenFinancialResearchObservationWrapperSchema,
    financial_research_observation_wrapper_schema_fingerprint,
)
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import ResearchSourceEligibility
from app.intelligence.brain_research_comparison_state import (
    ResearchMetricObservation,
    ResearchMetricValueType,
    research_metric_observation_fingerprint,
)
from app.intelligence.research_state_delta import research_observation_slot_key


_NONE = "<NONE>"


def wrap_financial_research_observation_bundle(
    bundle: FinancialResearchObservationBundle,
    *,
    wrapper_schema: FrozenFinancialResearchObservationWrapperSchema,
) -> tuple[ResearchMetricObservation, ...]:
    """Create exactly one generic factual wrapper for each bundle observation."""
    _validate_wrapper_schema(wrapper_schema)
    _validate_bundle(bundle)
    wrappers = tuple(_wrap_observation(observation, bundle, wrapper_schema) for observation in bundle.observations)
    if len(wrappers) != len(bundle.observations):
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_OUTPUT_COUNT_INVALID")
    return tuple(sorted(wrappers, key=_wrapper_order_key))


def _validate_wrapper_schema(schema: FrozenFinancialResearchObservationWrapperSchema) -> None:
    if not isinstance(schema, FrozenFinancialResearchObservationWrapperSchema):
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_REQUIRED")
    if financial_research_observation_wrapper_schema_fingerprint(schema) != schema.fingerprint:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_TAMPERED")
    if schema != CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_EXACT_SCHEMA_REQUIRED")


def _validate_bundle(bundle: FinancialResearchObservationBundle) -> None:
    if not isinstance(bundle, FinancialResearchObservationBundle):
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_BUNDLE_REQUIRED")
    try:
        bundle.__post_init__()
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_BUNDLE_INVALID") from error
    if financial_research_observation_bundle_fingerprint(bundle) != bundle.fingerprint:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_BUNDLE_TAMPERED")
    for observation in bundle.observations:
        if not isinstance(observation, FinancialMetricObservation) or financial_metric_observation_fingerprint(observation) != observation.fingerprint:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_OBSERVATION_TAMPERED")
    for attestation in bundle.attestations:
        if financial_research_observation_attestation_fingerprint(attestation) != attestation.fingerprint:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_ATTESTATION_TAMPERED")
    for failure in bundle.failures:
        if financial_research_input_failure_fingerprint(failure) != failure.fingerprint:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_FAILURE_TAMPERED")


def _wrap_observation(
    observation: FinancialMetricObservation,
    bundle: FinancialResearchObservationBundle,
    schema: FrozenFinancialResearchObservationWrapperSchema,
) -> ResearchMetricObservation:
    period = observation.period_identity
    slot = tuple(sorted({
        "financial_currency": observation.currency,
        "financial_fact_kind": observation.fact_kind.value,
        "financial_fiscal_quarter": _optional(period.fiscal_quarter),
        "financial_fiscal_year": _optional(period.fiscal_year),
        "financial_normalization_identity": observation.normalization_version,
        "financial_observation_schema_identity": _canonical_sequence((observation.schema_id, observation.schema_version, observation.schema_fingerprint)),
        "financial_period_basis": period.value_basis.value,
        "financial_period_end": _time(period.period_end),
        "financial_period_fingerprint": period.fingerprint,
        "financial_period_start": _optional_time(period.period_start),
        "financial_period_strength": period.strength.value,
        "financial_period_type": period.period_type.value,
        "financial_source_role": schema.source_role.value,
        "financial_value_dimension": period.value_dimension.value,
    }.items()))
    if tuple(key for key, _ in slot) != schema.slot_identity_component_keys:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SLOT_MAPPING_INVALID")

    lineage = tuple(sorted({
        "financial_bundle_as_of": _time(bundle.as_of),
        "financial_bundle_fingerprint": bundle.fingerprint,
        "financial_bundle_schema_fingerprint": bundle.bundle_schema_fingerprint,
        "financial_bundle_schema_id": bundle.bundle_schema_id,
        "financial_bundle_schema_version": bundle.bundle_schema_version,
        "financial_filing_id": _optional(observation.filing_id),
        "financial_parent_fact_ids": _canonical_sequence(observation.parent_fact_ids),
        "financial_provenance": _canonical_sequence(observation.provenance),
        "financial_quality_flags": _canonical_sequence(tuple(value.value for value in observation.quality_flags)),
        "financial_received_at": _time(observation.received_at),
        "financial_revision_of_fact_id": _optional(observation.revision_of_fact_id),
        "financial_selection_as_of": _selection_as_of(observation, bundle),
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
    if tuple(key for key, _ in lineage) != schema.non_slot_lineage_keys:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_LINEAGE_MAPPING_INVALID")

    return ResearchMetricObservation(
        dimension=schema.generic_dimension,
        metric_id=observation.metric.value,
        value_type=ResearchMetricValueType.FACTUAL_VALUE,
        value=observation.value,
        unit=observation.unit,
        scale=observation.scale.value,
        basis=period.value_basis.value,
        scope=observation.statement_scope.value,
        period_identity=period.fingerprint,
        effective_at=period.period_end,
        published_at=observation.published_at,
        lookback_or_window=None,
        benchmark=None,
        methodology_id=schema.schema_id,
        methodology_version=schema.version,
        source_artifact_type=schema.source_artifact_type,
        source_artifact_fingerprint=observation.fingerprint,
        dependency_manifest_fingerprint=schema.fingerprint,
        source_eligibility=ResearchSourceEligibility.PIT_REBUILDABLE,
        freshness_status=FreshnessStatus.UNKNOWN,
        reliability_lineage=None,
        historical_integrity_lineage=None,
        identity_components=slot,
        lineage_components=lineage,
    )


def _selection_as_of(
    observation: FinancialMetricObservation,
    bundle: FinancialResearchObservationBundle,
) -> str:
    matching = tuple(item for item in bundle.attestations if item.observation_fingerprint == observation.fingerprint)
    if len(matching) != 1:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_ATTESTATION_BINDING_INVALID")
    attestation = matching[0]
    if (attestation.source_fact_id, attestation.selection_result_fingerprint, attestation.selection_as_of) != (
        observation.source_fact_id, observation.selection_result_fingerprint, bundle.as_of,
    ):
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_ATTESTATION_BINDING_INVALID")
    return _time(attestation.selection_as_of)


def _wrapper_order_key(value: ResearchMetricObservation) -> tuple[str, str, str]:
    slot_fingerprint = manifest_fingerprint(slot=research_observation_slot_key(value))
    return value.metric_id, slot_fingerprint, research_metric_observation_fingerprint(value)


def _optional(value: object | None) -> str:
    return _NONE if value is None else str(value)


def _time(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FINANCIAL_RESEARCH_WRAPPER_TIMEZONE_REQUIRED")
    return value.astimezone(UTC).isoformat()


def _optional_time(value: datetime | None) -> str:
    return _NONE if value is None else _time(value)


def _canonical_sequence(values: tuple[object, ...]) -> str:
    return json.dumps(tuple(str(value) for value in values), ensure_ascii=True, separators=(",", ":"))


__all__ = ("wrap_financial_research_observation_bundle",)
