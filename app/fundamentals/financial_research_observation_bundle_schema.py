"""Frozen passive contracts for a same-as-of financial research handoff.

This module provides immutable artifacts only.  It has no bundle construction
API and performs no selection, materialization, Shared-Brain integration,
comparison, trajectory, persistence, or runtime work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.fundamentals.financial_fact_vintage_selection_policy import (
    FinancialFactVintageSelectionMode,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import FinancialFactSemanticKey
from app.fundamentals.financial_metric_observation_materializer import (
    FinancialMetricObservationMaterializationReason,
    FinancialMetricObservationMaterializationStatus,
)
from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricObservation,
    FinancialMetricPeriodIdentityStrength,
    financial_metric_observation_fingerprint,
)
from app.historical.guard import manifest_fingerprint


_SCHEMA_ID = "financial-research-observation-bundle-schema"
_SCHEMA_VERSION = "v1-approved"
_OBSERVATION_SCHEMA_ID = "financial-metric-observation-schema"
_OBSERVATION_SCHEMA_VERSION = "v1-approved"
_OBSERVATION_SCHEMA_FINGERPRINT = "6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf"
_SELECTION_POLICY_ID = "financial-fact-vintage-selection-policy"
_SELECTION_POLICY_VERSION = "v1-approved"
_SELECTION_POLICY_FINGERPRINT = "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13"


class FinancialResearchObservationBundleSchemaApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialResearchInputFailureStage(StrEnum):
    SELECTION = "SELECTION"
    MATERIALIZATION = "MATERIALIZATION"


@dataclass(frozen=True, slots=True)
class FrozenFinancialResearchObservationBundleSchema:
    schema_id: str
    version: str
    proposal_schema_id: str
    proposal_version: str
    approval_status: FinancialResearchObservationBundleSchemaApprovalStatus
    approved_by: str
    selected_for_future_bundle: bool
    active: bool
    knowledge_mode: FinancialFactVintageSelectionMode
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    failure_stages: tuple[FinancialResearchInputFailureStage, ...]
    admitted_period_strengths: tuple[FinancialMetricPeriodIdentityStrength, ...]
    duplicate_observation_input_rejected: bool
    top_level_status_absent: bool
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.schema_id, self.version, self.proposal_schema_id, self.proposal_version, self.approved_by)):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not FinancialResearchObservationBundleSchemaApprovalStatus.APPROVED:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_APPROVAL_REQUIRED")
        if self.selected_for_future_bundle or self.active:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_MUST_NOT_BE_ACTIVE")
        if self.knowledge_mode is not FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_MODE_REQUIRED")
        if (self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint) != (_OBSERVATION_SCHEMA_ID, _OBSERVATION_SCHEMA_VERSION, _OBSERVATION_SCHEMA_FINGERPRINT):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_OBSERVATION_LINEAGE_REQUIRED")
        if (self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint) != (_SELECTION_POLICY_ID, _SELECTION_POLICY_VERSION, _SELECTION_POLICY_FINGERPRINT):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_SELECTOR_LINEAGE_REQUIRED")
        if self.failure_stages != tuple(FinancialResearchInputFailureStage):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_FAILURE_STAGES_REQUIRED")
        if self.admitted_period_strengths != (FinancialMetricPeriodIdentityStrength.COMPLETE, FinancialMetricPeriodIdentityStrength.PARTIAL):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_PERIOD_STRENGTHS_REQUIRED")
        if not self.duplicate_observation_input_rejected or not self.top_level_status_absent:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_STRUCTURAL_RULES_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_PROVENANCE_NONCANONICAL")
        if self.fingerprint != financial_research_observation_bundle_schema_fingerprint(self):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialResearchObservationAttestation:
    observation_fingerprint: str
    source_fact_id: str
    selection_result_fingerprint: str
    selection_as_of: datetime
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.observation_fingerprint, self.source_fact_id, self.selection_result_fingerprint)):
            raise ValueError("FINANCIAL_RESEARCH_ATTESTATION_REQUIRED_FIELD")
        _aware(self.selection_as_of, "ATTESTATION_SELECTION_AS_OF")
        _validate_lineage(self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint, self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint)
        if self.fingerprint != financial_research_observation_attestation_fingerprint(self):
            raise ValueError("FINANCIAL_RESEARCH_ATTESTATION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialResearchInputFailure:
    canonical_instrument_id: str
    semantic_key: FinancialFactSemanticKey | None
    stage: FinancialResearchInputFailureStage
    selection_as_of: datetime
    selection_status: FinancialFactVintageSelectionStatus | None
    materialization_status: FinancialMetricObservationMaterializationStatus | None
    reason_codes: tuple[FinancialFactVintageSelectionReason | FinancialMetricObservationMaterializationReason, ...]
    source_fact_id: str | None
    selection_result_fingerprint: str | None
    materialization_result_fingerprint: str | None
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id or not self.reason_codes:
            raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_REQUIRED_FIELD")
        _aware(self.selection_as_of, "FAILURE_SELECTION_AS_OF")
        _validate_lineage(self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint, self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint)
        if self.semantic_key is not None and self.semantic_key.canonical_instrument_id != self.canonical_instrument_id:
            raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_INSTRUMENT_MISMATCH")
        if self.reason_codes != tuple(sorted(set(self.reason_codes), key=lambda value: value.value)):
            raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_REASONS_NONCANONICAL")
        if self.stage is FinancialResearchInputFailureStage.SELECTION:
            if self.selection_status not in {FinancialFactVintageSelectionStatus.UNAVAILABLE, FinancialFactVintageSelectionStatus.CONFLICTED, FinancialFactVintageSelectionStatus.INVALID_LINEAGE, FinancialFactVintageSelectionStatus.INSUFFICIENT_IDENTITY} or self.materialization_status is not None or not self.selection_result_fingerprint or self.materialization_result_fingerprint is not None or any(not isinstance(value, FinancialFactVintageSelectionReason) for value in self.reason_codes):
                raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_SELECTION_CONTRACT_INVALID")
        elif self.stage is FinancialResearchInputFailureStage.MATERIALIZATION:
            if self.selection_status is not FinancialFactVintageSelectionStatus.SELECTED or self.materialization_status is not FinancialMetricObservationMaterializationStatus.REJECTED or not all((self.source_fact_id, self.selection_result_fingerprint, self.materialization_result_fingerprint)) or any(not isinstance(value, FinancialMetricObservationMaterializationReason) for value in self.reason_codes):
                raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_MATERIALIZATION_CONTRACT_INVALID")
        if self.fingerprint != financial_research_input_failure_fingerprint(self):
            raise ValueError("FINANCIAL_RESEARCH_INPUT_FAILURE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialResearchObservationBundle:
    canonical_instrument_id: str
    as_of: datetime
    knowledge_mode: FinancialFactVintageSelectionMode
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    bundle_schema_id: str
    bundle_schema_version: str
    bundle_schema_fingerprint: str
    observations: tuple[FinancialMetricObservation, ...]
    attestations: tuple[FinancialResearchObservationAttestation, ...]
    failures: tuple[FinancialResearchInputFailure, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.canonical_instrument_id:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_CANONICAL_INSTRUMENT_REQUIRED")
        _aware(self.as_of, "BUNDLE_AS_OF")
        if self.knowledge_mode is not FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_MODE_REQUIRED")
        _validate_lineage(self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint, self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint)
        if (self.bundle_schema_id, self.bundle_schema_version, self.bundle_schema_fingerprint) != (_SCHEMA_ID, _SCHEMA_VERSION, _CURRENT_SCHEMA_FINGERPRINT):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SCHEMA_LINEAGE_REQUIRED")
        if self.observations != tuple(sorted(self.observations, key=_observation_key)):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_OBSERVATIONS_NONCANONICAL")
        if self.attestations != tuple(sorted(self.attestations, key=lambda value: value.observation_fingerprint)):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_ATTESTATIONS_NONCANONICAL")
        if self.failures != tuple(sorted(self.failures, key=_failure_key)):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_FAILURES_NONCANONICAL")
        if len({value.fingerprint for value in self.observations}) != len(self.observations):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_DUPLICATE_OBSERVATION")
        if len({value.observation_fingerprint for value in self.attestations}) != len(self.attestations):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_DUPLICATE_ATTESTATION")
        if len({value.fingerprint for value in self.failures}) != len(self.failures):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_DUPLICATE_FAILURE")
        observation_keys: dict[tuple, FinancialMetricObservation] = {}
        expected_attestations: dict[str, FinancialMetricObservation] = {}
        for observation in self.observations:
            if financial_metric_observation_fingerprint(observation) != observation.fingerprint:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_OBSERVATION_TAMPERED")
            if observation.canonical_instrument_id != self.canonical_instrument_id or observation.visible_as_of > self.as_of:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_OBSERVATION_SCOPE_INVALID")
            if observation.period_identity.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_PERIOD_IDENTITY_INSUFFICIENT")
            _validate_lineage(observation.selection_policy_id, observation.selection_policy_version, observation.selection_policy_fingerprint, observation.schema_id, observation.schema_version, observation.schema_fingerprint)
            key = _observation_semantic_key(observation)
            if key in observation_keys:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SEMANTIC_COLLISION")
            observation_keys[key] = observation
            expected_attestations[observation.fingerprint] = observation
        if set(expected_attestations) != {value.observation_fingerprint for value in self.attestations}:
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_ATTESTATION_COVERAGE_INVALID")
        for attestation in self.attestations:
            observation = expected_attestations[attestation.observation_fingerprint]
            if (attestation.source_fact_id, attestation.selection_result_fingerprint, attestation.selection_as_of) != (observation.source_fact_id, observation.selection_result_fingerprint, self.as_of):
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_ATTESTATION_BINDING_INVALID")
        for failure in self.failures:
            if failure.canonical_instrument_id != self.canonical_instrument_id or failure.selection_as_of != self.as_of:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_FAILURE_SCOPE_INVALID")
            if failure.semantic_key is not None and failure.semantic_key.ordering_key() in { _semantic_key_order(value) for value in self.observations }:
                raise ValueError("FINANCIAL_RESEARCH_BUNDLE_OBSERVATION_FAILURE_CONTRADICTION")
        if self.fingerprint != financial_research_observation_bundle_fingerprint(self):
            raise ValueError("FINANCIAL_RESEARCH_BUNDLE_FINGERPRINT_MISMATCH")


def create_frozen_financial_research_observation_bundle_schema(
    *, schema_id: str, version: str, proposal_schema_id: str, proposal_version: str,
    approved_by: str, provenance: tuple[tuple[str, str], ...],
) -> FrozenFinancialResearchObservationBundleSchema:
    values = dict(
        schema_id=schema_id, version=version, proposal_schema_id=proposal_schema_id, proposal_version=proposal_version,
        approval_status=FinancialResearchObservationBundleSchemaApprovalStatus.APPROVED,
        approved_by=approved_by, selected_for_future_bundle=False, active=False,
        knowledge_mode=FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME,
        observation_schema_id=_OBSERVATION_SCHEMA_ID, observation_schema_version=_OBSERVATION_SCHEMA_VERSION,
        observation_schema_fingerprint=_OBSERVATION_SCHEMA_FINGERPRINT,
        selector_policy_id=_SELECTION_POLICY_ID, selector_policy_version=_SELECTION_POLICY_VERSION,
        selector_policy_fingerprint=_SELECTION_POLICY_FINGERPRINT,
        failure_stages=tuple(FinancialResearchInputFailureStage),
        admitted_period_strengths=(FinancialMetricPeriodIdentityStrength.COMPLETE, FinancialMetricPeriodIdentityStrength.PARTIAL),
        duplicate_observation_input_rejected=True, top_level_status_absent=True,
        provenance=tuple(sorted(set(provenance))),
    )
    return FrozenFinancialResearchObservationBundleSchema(
        **values, fingerprint=financial_research_observation_bundle_schema_fingerprint_values(values),
    )


def financial_research_observation_bundle_schema_fingerprint(value: FrozenFinancialResearchObservationBundleSchema) -> str:
    return financial_research_observation_bundle_schema_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def financial_research_observation_bundle_schema_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def financial_research_observation_attestation_fingerprint(value: FinancialResearchObservationAttestation) -> str:
    return manifest_fingerprint(**_semantic_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}))


def financial_research_input_failure_fingerprint(value: FinancialResearchInputFailure) -> str:
    return manifest_fingerprint(**_semantic_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}))


def financial_research_observation_bundle_fingerprint(value: FinancialResearchObservationBundle) -> str:
    return manifest_fingerprint(**_semantic_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}))


def _validate_lineage(selector_id: str, selector_version: str, selector_fingerprint: str, observation_id: str, observation_version: str, observation_fingerprint: str) -> None:
    if (selector_id, selector_version, selector_fingerprint) != (_SELECTION_POLICY_ID, _SELECTION_POLICY_VERSION, _SELECTION_POLICY_FINGERPRINT):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_SELECTOR_LINEAGE_REQUIRED")
    if (observation_id, observation_version, observation_fingerprint) != (_OBSERVATION_SCHEMA_ID, _OBSERVATION_SCHEMA_VERSION, _OBSERVATION_SCHEMA_FINGERPRINT):
        raise ValueError("FINANCIAL_RESEARCH_BUNDLE_OBSERVATION_LINEAGE_REQUIRED")


def _aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"FINANCIAL_RESEARCH_BUNDLE_{label}_TIMEZONE_REQUIRED")


def _observation_key(value: FinancialMetricObservation) -> tuple:
    period = value.period_identity
    return (
        value.fact_kind.value, value.metric.value, value.statement_scope.value,
        period.period_type.value, period.value_basis.value, _time(period.period_end), _time(period.period_start),
        "" if period.fiscal_year is None else str(period.fiscal_year), "" if period.fiscal_quarter is None else str(period.fiscal_quarter),
        period.fingerprint, value.fingerprint,
    )


def _observation_semantic_key(value: FinancialMetricObservation) -> tuple:
    return value.fact_kind.value, value.metric.value, value.period_identity.fingerprint


def _semantic_key_order(value: FinancialMetricObservation) -> tuple[str, ...]:
    period = value.period_identity
    return (
        value.canonical_instrument_id, value.metric.value, value.fact_kind.value, value.statement_scope.value,
        period.period_type.value, period.value_basis.value, _time(period.period_start) or "", _time(period.period_end) or "",
        "" if period.fiscal_year is None else str(period.fiscal_year), "" if period.fiscal_quarter is None else str(period.fiscal_quarter),
        period.value_dimension.value, value.currency, value.unit, value.scale.value, value.normalization_version,
    )


def _failure_key(value: FinancialResearchInputFailure) -> tuple:
    return (
        "" if value.semantic_key is None else "|".join(value.semantic_key.ordering_key()), value.stage.value,
        "" if value.selection_status is None else value.selection_status.value,
        "" if value.materialization_status is None else value.materialization_status.value,
        tuple(reason.value for reason in value.reason_codes), value.fingerprint,
    )


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


def _semantic_values(values: dict) -> dict:
    def convert(value):
        if isinstance(value, StrEnum): return value.value
        if isinstance(value, datetime): return _time(value)
        if isinstance(value, tuple): return tuple(convert(item) for item in value)
        if hasattr(value, "__dataclass_fields__"): return {field: convert(getattr(value, field)) for field in value.__dataclass_fields__}
        return value
    return {key: convert(value) for key, value in sorted(values.items())}


CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA = create_frozen_financial_research_observation_bundle_schema(
    schema_id=_SCHEMA_ID, version=_SCHEMA_VERSION,
    proposal_schema_id="financial-research-observation-bundle-schema", proposal_version="v1-proposed",
    approved_by="human:Akash-Verma",
    provenance=(
        ("governance_approval", "U14D-6L"),
        ("proposal_schema", "financial-research-observation-bundle-schema/v1-proposed"),
        ("scope", "PASSIVE_SAME_AS_OF_FINANCIAL_HANDOFF_ONLY"),
    ),
)
_CURRENT_SCHEMA_FINGERPRINT = CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA.fingerprint


__all__ = (
    "CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA",
    "FinancialResearchInputFailure",
    "FinancialResearchInputFailureStage",
    "FinancialResearchObservationAttestation",
    "FinancialResearchObservationBundle",
    "FinancialResearchObservationBundleSchemaApprovalStatus",
    "FrozenFinancialResearchObservationBundleSchema",
    "create_frozen_financial_research_observation_bundle_schema",
    "financial_research_input_failure_fingerprint",
    "financial_research_observation_attestation_fingerprint",
    "financial_research_observation_bundle_fingerprint",
    "financial_research_observation_bundle_schema_fingerprint",
)
