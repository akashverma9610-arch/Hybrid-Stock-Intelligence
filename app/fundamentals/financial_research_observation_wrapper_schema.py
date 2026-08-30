"""Frozen passive mapping contract for a future financial research wrapper.

This module describes a future lossless adapter only.  It never creates a
generic observation, accesses a bundle, or integrates with Shared Brain.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
)


_SCHEMA_ID = "financial-research-observation-wrapper-schema"
_VERSION = "v1-approved"
_OBSERVATION_SCHEMA = (
    "financial-metric-observation-schema", "v1-approved",
    "6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf",
)
_BUNDLE_SCHEMA = (
    "financial-research-observation-bundle-schema", "v1-approved",
    "aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89",
)
_SELECTOR_POLICY = (
    "financial-fact-vintage-selection-policy", "v1-approved",
    "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13",
)


class FinancialResearchObservationWrapperSchemaApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialResearchObservationWrapperExclusion(StrEnum):
    WRAPPER_EXECUTION = "WRAPPER_EXECUTION"
    BRAIN_STATE_INTEGRATION = "BRAIN_STATE_INTEGRATION"
    TRAJECTORY = "TRAJECTORY"
    DIRECTIONALITY = "DIRECTIONALITY"
    THESIS_OR_OPPORTUNITY = "THESIS_OR_OPPORTUNITY"
    ALERT_OR_RECOMMENDATION = "ALERT_OR_RECOMMENDATION"
    EXECUTION = "EXECUTION"


@dataclass(frozen=True, slots=True)
class FrozenFinancialResearchObservationWrapperSchema:
    schema_id: str
    version: str
    proposal_schema_id: str
    proposal_version: str
    approval_status: FinancialResearchObservationWrapperSchemaApprovalStatus
    approved_by: str
    selected_for_future_wrapper: bool
    active: bool
    generic_dimension: ResearchComparabilityDomain
    source_role: FinancialObservationSourceRole
    source_artifact_type: str
    metric_id_mapping: str
    exact_decimal_value_required: bool
    source_artifact_fingerprint_mapping: str
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    bundle_schema_id: str
    bundle_schema_version: str
    bundle_schema_fingerprint: str
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    slot_identity_component_keys: tuple[str, ...]
    non_slot_lineage_keys: tuple[str, ...]
    exclusions: tuple[FinancialResearchObservationWrapperExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.schema_id, self.version, self.proposal_schema_id, self.proposal_version, self.approved_by, self.source_artifact_type, self.metric_id_mapping, self.source_artifact_fingerprint_mapping)):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not FinancialResearchObservationWrapperSchemaApprovalStatus.APPROVED:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_APPROVAL_REQUIRED")
        if self.selected_for_future_wrapper or self.active:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_MUST_NOT_BE_ACTIVE")
        if self.generic_dimension is not ResearchComparabilityDomain.FINANCIAL_RAW:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_FINANCIAL_DOMAIN_REQUIRED")
        if self.source_role is not FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_SOURCE_ROLE_REQUIRED")
        if self.source_artifact_type != "FINANCIAL_METRIC_OBSERVATION":
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_ARTIFACT_TYPE_REQUIRED")
        if self.metric_id_mapping != "FINANCIAL_METRIC_VALUE" or not self.exact_decimal_value_required:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_VALUE_MAPPING_REQUIRED")
        if self.source_artifact_fingerprint_mapping != "FINANCIAL_METRIC_OBSERVATION_FINGERPRINT":
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_ARTIFACT_FINGERPRINT_REQUIRED")
        if (self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint) != _OBSERVATION_SCHEMA:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_OBSERVATION_LINEAGE_REQUIRED")
        if (self.bundle_schema_id, self.bundle_schema_version, self.bundle_schema_fingerprint) != _BUNDLE_SCHEMA:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_BUNDLE_LINEAGE_REQUIRED")
        if (self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint) != _SELECTOR_POLICY:
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_SELECTOR_LINEAGE_REQUIRED")
        _canonical_strings(self.slot_identity_component_keys, "FINANCIAL_RESEARCH_WRAPPER_SCHEMA_SLOT_KEYS_NONCANONICAL")
        _canonical_strings(self.non_slot_lineage_keys, "FINANCIAL_RESEARCH_WRAPPER_SCHEMA_LINEAGE_KEYS_NONCANONICAL")
        if set(self.slot_identity_component_keys).intersection(self.non_slot_lineage_keys):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_SLOT_LINEAGE_OVERLAP")
        if self.exclusions != tuple(FinancialResearchObservationWrapperExclusion):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_EXCLUSIONS_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_PROVENANCE_NONCANONICAL")
        if self.fingerprint != financial_research_observation_wrapper_schema_fingerprint(self):
            raise ValueError("FINANCIAL_RESEARCH_WRAPPER_SCHEMA_FINGERPRINT_MISMATCH")


def create_frozen_financial_research_observation_wrapper_schema(
    *, schema_id: str, version: str, proposal_schema_id: str, proposal_version: str,
    approved_by: str, provenance: tuple[tuple[str, str], ...],
) -> FrozenFinancialResearchObservationWrapperSchema:
    values = dict(
        schema_id=schema_id, version=version, proposal_schema_id=proposal_schema_id, proposal_version=proposal_version,
        approval_status=FinancialResearchObservationWrapperSchemaApprovalStatus.APPROVED,
        approved_by=approved_by, selected_for_future_wrapper=False, active=False,
        generic_dimension=ResearchComparabilityDomain.FINANCIAL_RAW,
        source_role=FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION,
        source_artifact_type="FINANCIAL_METRIC_OBSERVATION", metric_id_mapping="FINANCIAL_METRIC_VALUE",
        exact_decimal_value_required=True, source_artifact_fingerprint_mapping="FINANCIAL_METRIC_OBSERVATION_FINGERPRINT",
        observation_schema_id=_OBSERVATION_SCHEMA[0], observation_schema_version=_OBSERVATION_SCHEMA[1], observation_schema_fingerprint=_OBSERVATION_SCHEMA[2],
        bundle_schema_id=_BUNDLE_SCHEMA[0], bundle_schema_version=_BUNDLE_SCHEMA[1], bundle_schema_fingerprint=_BUNDLE_SCHEMA[2],
        selector_policy_id=_SELECTOR_POLICY[0], selector_policy_version=_SELECTOR_POLICY[1], selector_policy_fingerprint=_SELECTOR_POLICY[2],
        slot_identity_component_keys=(
            "financial_currency", "financial_fact_kind", "financial_fiscal_quarter", "financial_fiscal_year",
            "financial_normalization_identity", "financial_observation_schema_identity", "financial_period_basis",
            "financial_period_end", "financial_period_fingerprint", "financial_period_start", "financial_period_strength",
            "financial_period_type", "financial_source_role", "financial_value_dimension",
        ),
        non_slot_lineage_keys=(
            "financial_bundle_as_of", "financial_bundle_fingerprint", "financial_bundle_schema_fingerprint",
            "financial_bundle_schema_id", "financial_bundle_schema_version", "financial_filing_id",
            "financial_parent_fact_ids", "financial_provenance", "financial_quality_flags", "financial_received_at",
            "financial_revision_of_fact_id", "financial_selection_as_of", "financial_selection_result_fingerprint",
            "financial_selector_policy_fingerprint", "financial_selector_policy_id", "financial_selector_policy_version",
            "financial_source_fact_id", "financial_source_name", "financial_source_reference",
            "financial_source_semantic_fingerprint", "financial_visible_as_of",
        ),
        exclusions=tuple(FinancialResearchObservationWrapperExclusion), provenance=tuple(sorted(set(provenance))),
    )
    return FrozenFinancialResearchObservationWrapperSchema(
        **values, fingerprint=financial_research_observation_wrapper_schema_fingerprint_values(values),
    )


def financial_research_observation_wrapper_schema_fingerprint(value: FrozenFinancialResearchObservationWrapperSchema) -> str:
    return financial_research_observation_wrapper_schema_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_research_observation_wrapper_schema_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def _canonical_strings(values: tuple[str, ...], code: str) -> None:
    if values != tuple(sorted(set(values))) or any(not value for value in values):
        raise ValueError(code)


def _semantic_values(values: dict) -> dict:
    def convert(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, tuple):
            return tuple(convert(item) for item in value)
        if hasattr(value, "__dataclass_fields__"):
            return {field: convert(getattr(value, field)) for field in value.__dataclass_fields__}
        return value
    return {key: convert(value) for key, value in sorted(values.items())}


CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA = create_frozen_financial_research_observation_wrapper_schema(
    schema_id=_SCHEMA_ID, version=_VERSION,
    proposal_schema_id="financial-research-observation-wrapper-schema", proposal_version="v1-proposed",
    approved_by="human:Akash-Verma",
    provenance=(
        ("governance_approval", "U14D-6R"),
        ("proposal_schema", "financial-research-observation-wrapper-schema/v1-proposed"),
        ("scope", "PASSIVE_LOSSLESS_FINANCIAL_TO_GENERIC_MAPPING_ONLY"),
    ),
)


__all__ = (
    "CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA",
    "FinancialResearchObservationWrapperExclusion",
    "FinancialResearchObservationWrapperSchemaApprovalStatus",
    "FrozenFinancialResearchObservationWrapperSchema",
    "create_frozen_financial_research_observation_wrapper_schema",
    "financial_research_observation_wrapper_schema_fingerprint",
)
