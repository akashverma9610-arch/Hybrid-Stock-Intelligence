"""Pure construction of a same-as-of financial research observation bundle.

The inputs to this module are already-materialized immutable artifacts.  It
does not select fact vintages, materialize observations, or access any runtime
dependency.  The frozen bundle contract remains the authority for structural
and semantic validation.
"""
from __future__ import annotations

from datetime import datetime

import app.fundamentals.financial_research_observation_bundle_schema as _bundle_contract
from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricObservation,
    financial_metric_observation_fingerprint,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchObservationAttestation,
    FinancialResearchObservationBundle,
    FrozenFinancialResearchObservationBundleSchema,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
    financial_research_observation_bundle_schema_fingerprint,
)


def build_financial_research_observation_bundle(
    *,
    canonical_instrument_id: str,
    as_of: datetime,
    observations: tuple[FinancialMetricObservation, ...] = (),
    attestations: tuple[FinancialResearchObservationAttestation, ...] = (),
    failures: tuple[FinancialResearchInputFailure, ...] = (),
    schema: FrozenFinancialResearchObservationBundleSchema,
) -> FinancialResearchObservationBundle:
    """Bind supplied same-as-of artifacts into one immutable factual bundle.

    No upstream operation is accepted or performed here: callers must supply
    already-created observations, their attestations, and typed upstream
    failures.  Invalid construction inputs fail closed rather than being
    reduced, repaired, or converted into an upstream failure entry.
    """
    _require_exact_schema(schema)
    _require_artifact_types(observations, attestations, failures)
    _validate_artifact_fingerprints(observations, attestations, failures)

    values = dict(
        canonical_instrument_id=canonical_instrument_id,
        as_of=as_of,
        knowledge_mode=schema.knowledge_mode,
        observation_schema_id=schema.observation_schema_id,
        observation_schema_version=schema.observation_schema_version,
        observation_schema_fingerprint=schema.observation_schema_fingerprint,
        selector_policy_id=schema.selector_policy_id,
        selector_policy_version=schema.selector_policy_version,
        selector_policy_fingerprint=schema.selector_policy_fingerprint,
        bundle_schema_id=schema.schema_id,
        bundle_schema_version=schema.version,
        bundle_schema_fingerprint=schema.fingerprint,
        observations=tuple(sorted(observations, key=_bundle_contract._observation_key)),
        attestations=tuple(sorted(attestations, key=lambda value: value.observation_fingerprint)),
        failures=tuple(sorted(failures, key=_bundle_contract._failure_key)),
    )
    return FinancialResearchObservationBundle(
        **values,
        fingerprint=_bundle_contract.manifest_fingerprint(
            **_bundle_contract._semantic_values(values)
        ),
    )


def _require_exact_schema(schema: FrozenFinancialResearchObservationBundleSchema) -> None:
    if not isinstance(schema, FrozenFinancialResearchObservationBundleSchema):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_SCHEMA_REQUIRED")
    if financial_research_observation_bundle_schema_fingerprint(schema) != schema.fingerprint:
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_SCHEMA_TAMPERED")
    if schema != CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA:
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_EXACT_SCHEMA_REQUIRED")


def _require_artifact_types(
    observations: tuple[FinancialMetricObservation, ...],
    attestations: tuple[FinancialResearchObservationAttestation, ...],
    failures: tuple[FinancialResearchInputFailure, ...],
) -> None:
    if not all(isinstance(value, FinancialMetricObservation) for value in observations):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_OBSERVATION_TYPE_REQUIRED")
    if not all(isinstance(value, FinancialResearchObservationAttestation) for value in attestations):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_ATTESTATION_TYPE_REQUIRED")
    if not all(isinstance(value, FinancialResearchInputFailure) for value in failures):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_FAILURE_TYPE_REQUIRED")


def _validate_artifact_fingerprints(
    observations: tuple[FinancialMetricObservation, ...],
    attestations: tuple[FinancialResearchObservationAttestation, ...],
    failures: tuple[FinancialResearchInputFailure, ...],
) -> None:
    if any(financial_metric_observation_fingerprint(value) != value.fingerprint for value in observations):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_OBSERVATION_TAMPERED")
    if any(financial_research_observation_attestation_fingerprint(value) != value.fingerprint for value in attestations):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_ATTESTATION_TAMPERED")
    if any(financial_research_input_failure_fingerprint(value) != value.fingerprint for value in failures):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_BUILDER_FAILURE_TAMPERED")


__all__ = ("build_financial_research_observation_bundle",)
