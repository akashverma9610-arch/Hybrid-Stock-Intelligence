"""Frozen passive contract for a future financial-integrated Brain state v2.

This module deliberately defines *only* immutable governance metadata.  It
does not construct a Brain state, invoke any upstream financial function,
access stores/providers, or compare states.  In particular, the existing v1
``build_brain_research_comparison_state`` remains the only state builder.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.fundamentals.financial_metric_observation_schema import (
    FinancialMetricPeriodIdentityStrength,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    FinancialResearchInputFailureStage,
)
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
    ResearchComparisonMode,
)


_STATE_SCHEMA = ("brain-research-comparison-state", "v2")
_METHODOLOGY = ("shared-brain-research-comparison", "v2")
_COMPARABILITY_POLICY = (
    "brain-research-comparability-policy", "v2-approved",
    "1e6926fd84dcf82958a831674701afb28bf3a76a15e9fe19bbfe5d5f28df79d3",
)
_BUNDLE_SCHEMA = (
    "financial-research-observation-bundle-schema", "v1-approved",
    "aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89",
)
_OBSERVATION_SCHEMA = (
    "financial-metric-observation-schema", "v1-approved",
    "6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf",
)
_WRAPPER_SCHEMA = (
    "financial-research-observation-wrapper-schema", "v1-approved",
    "62ce6dc13dab80a3a468307f24b88d888a8d42226a7506c671d00c86e1b4f95c",
)
_SELECTOR_POLICY = (
    "financial-fact-vintage-selection-policy", "v1-approved",
    "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13",
)


class BrainResearchComparisonStateV2SchemaApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialDimensionAvailabilityRule(StrEnum):
    """Factual availability cases; none is an investment-quality judgment."""

    NUMERIC_WRAPPERS_PRESENT = "NUMERIC_WRAPPERS_PRESENT"
    REFERENCES_ONLY = "REFERENCES_ONLY"
    FAILURES_ONLY = "FAILURES_ONLY"
    NO_SELECTED_FACTS = "NO_SELECTED_FACTS"


class BrainResearchComparisonStateV2Exclusion(StrEnum):
    STATE_V2_BUILDER_IMPLEMENTATION = "STATE_V2_BUILDER_IMPLEMENTATION"
    FINANCIAL_RUNTIME_INTEGRATION = "FINANCIAL_RUNTIME_INTEGRATION"
    WRAPPER_EXECUTION = "WRAPPER_EXECUTION"
    SELECTOR_OR_MATERIALIZER_EXECUTION = "SELECTOR_OR_MATERIALIZER_EXECUTION"
    RESEARCH_STATE_DELTA_CHANGE = "RESEARCH_STATE_DELTA_CHANGE"
    TRAJECTORY = "TRAJECTORY"
    DIRECTIONALITY = "DIRECTIONALITY"
    THESIS_OR_OPPORTUNITY = "THESIS_OR_OPPORTUNITY"
    ALERT_RECOMMENDATION_OR_ACTION = "ALERT_RECOMMENDATION_OR_ACTION"
    PERSISTENCE_OR_RUNTIME = "PERSISTENCE_OR_RUNTIME"


@dataclass(frozen=True, slots=True)
class FrozenBrainResearchComparisonStateV2Schema:
    """Approved future-state contract; intentionally not a state runtime type."""

    schema_id: str
    version: str
    proposal_schema_id: str
    proposal_version: str
    approval_status: BrainResearchComparisonStateV2SchemaApprovalStatus
    approved_by: str
    selected_for_future_builder: bool
    active: bool
    state_schema_id: str
    state_schema_version: str
    research_methodology_id: str
    research_methodology_version: str
    comparison_mode: ResearchComparisonMode
    comparability_policy_id: str
    comparability_policy_version: str
    comparability_policy_fingerprint: str
    bundle_schema_id: str
    bundle_schema_version: str
    bundle_schema_fingerprint: str
    observation_schema_id: str
    observation_schema_version: str
    observation_schema_fingerprint: str
    wrapper_schema_id: str
    wrapper_schema_version: str
    wrapper_schema_fingerprint: str
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    future_builder_api: str
    financial_bundle_required: bool
    financial_wrappers_required: bool
    typed_financial_failures_required: bool
    explicit_upstream_inputs_required: bool
    exact_instrument_parity_required: bool
    exact_as_of_parity_required: bool
    wrapper_visible_as_of_not_after_state_as_of: bool
    wrapper_bundle_one_to_one_required: bool
    duplicate_full_slot_rejected: bool
    no_alternate_financial_input_path: bool
    financial_dimension: ResearchComparabilityDomain
    numeric_source_role: FinancialObservationSourceRole
    retained_reference_source_role: FinancialObservationSourceRole
    reference_numeric_pairing_prohibited: bool
    double_count_semantic_aggregation_prohibited: bool
    admitted_period_strengths: tuple[FinancialMetricPeriodIdentityStrength, ...]
    financial_failure_stages: tuple[FinancialResearchInputFailureStage, ...]
    failures_are_dimension_local: bool
    failure_only_bundle_allowed: bool
    empty_wrapper_set_allowed_only_for_empty_bundle: bool
    availability_rules: tuple[FinancialDimensionAvailabilityRule, ...]
    wrapper_ordering: str
    failure_ordering: str
    state_fingerprint_components: tuple[str, ...]
    v1_v2_foundationally_non_comparable: bool
    v2_dimension_local_failure: bool
    exclusions: tuple[BrainResearchComparisonStateV2Exclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        required = (
            self.schema_id, self.version, self.proposal_schema_id, self.proposal_version,
            self.approved_by, self.state_schema_id, self.state_schema_version,
            self.research_methodology_id, self.research_methodology_version,
            self.comparability_policy_id, self.comparability_policy_version,
            self.comparability_policy_fingerprint, self.bundle_schema_id,
            self.bundle_schema_version, self.bundle_schema_fingerprint,
            self.observation_schema_id, self.observation_schema_version,
            self.observation_schema_fingerprint, self.wrapper_schema_id,
            self.wrapper_schema_version, self.wrapper_schema_fingerprint,
            self.selector_policy_id, self.selector_policy_version,
            self.selector_policy_fingerprint, self.future_builder_api,
            self.wrapper_ordering, self.failure_ordering,
        )
        if not all(required):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not BrainResearchComparisonStateV2SchemaApprovalStatus.APPROVED:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_APPROVAL_REQUIRED")
        if self.selected_for_future_builder or self.active:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_MUST_NOT_BE_ACTIVE")
        if (self.state_schema_id, self.state_schema_version) != _STATE_SCHEMA:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_IDENTITY_REQUIRED")
        if (self.research_methodology_id, self.research_methodology_version) != _METHODOLOGY:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_METHODOLOGY_REQUIRED")
        if self.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_MODE_REQUIRED")
        if (self.comparability_policy_id, self.comparability_policy_version, self.comparability_policy_fingerprint) != _COMPARABILITY_POLICY:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_POLICY_LINEAGE_REQUIRED")
        if (self.bundle_schema_id, self.bundle_schema_version, self.bundle_schema_fingerprint) != _BUNDLE_SCHEMA:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_BUNDLE_LINEAGE_REQUIRED")
        if (self.observation_schema_id, self.observation_schema_version, self.observation_schema_fingerprint) != _OBSERVATION_SCHEMA:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_OBSERVATION_LINEAGE_REQUIRED")
        if (self.wrapper_schema_id, self.wrapper_schema_version, self.wrapper_schema_fingerprint) != _WRAPPER_SCHEMA:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_WRAPPER_LINEAGE_REQUIRED")
        if (self.selector_policy_id, self.selector_policy_version, self.selector_policy_fingerprint) != _SELECTOR_POLICY:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_SELECTOR_LINEAGE_REQUIRED")
        if self.future_builder_api != "build_brain_research_comparison_state_v2":
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_BUILDER_API_REQUIRED")
        if not all((
            self.financial_bundle_required, self.financial_wrappers_required,
            self.typed_financial_failures_required, self.explicit_upstream_inputs_required,
            self.exact_instrument_parity_required, self.exact_as_of_parity_required,
            self.wrapper_visible_as_of_not_after_state_as_of,
            self.wrapper_bundle_one_to_one_required, self.duplicate_full_slot_rejected,
            self.no_alternate_financial_input_path,
        )):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_INPUT_BOUNDARY_REQUIRED")
        if self.financial_dimension is not ResearchComparabilityDomain.FINANCIAL_RAW:
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_FINANCIAL_DOMAIN_REQUIRED")
        if (
            self.numeric_source_role is not FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION
            or self.retained_reference_source_role is not FinancialObservationSourceRole.FINANCIAL_EVIDENCE_REFERENCE
            or not self.reference_numeric_pairing_prohibited
            or not self.double_count_semantic_aggregation_prohibited
        ):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_SOURCE_ROLE_FIREWALL_REQUIRED")
        if self.admitted_period_strengths != (
            FinancialMetricPeriodIdentityStrength.COMPLETE,
            FinancialMetricPeriodIdentityStrength.PARTIAL,
        ):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_PERIOD_STRENGTH_REQUIRED")
        if self.financial_failure_stages != tuple(FinancialResearchInputFailureStage):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_FAILURE_STAGES_REQUIRED")
        if not all((
            self.failures_are_dimension_local, self.failure_only_bundle_allowed,
            self.empty_wrapper_set_allowed_only_for_empty_bundle,
            self.v1_v2_foundationally_non_comparable, self.v2_dimension_local_failure,
        )):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_FAILURE_BOUNDARY_REQUIRED")
        if self.availability_rules != tuple(FinancialDimensionAvailabilityRule):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_AVAILABILITY_RULES_REQUIRED")
        if self.wrapper_ordering != "GENERIC_FULL_OBSERVATION_SLOT_IDENTITY":
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_WRAPPER_ORDERING_REQUIRED")
        if self.failure_ordering != "SEMANTIC_KEY_STAGE_STATUS_REASONS_UPSTREAM_FINGERPRINT":
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_FAILURE_ORDERING_REQUIRED")
        _canonical_strings(self.state_fingerprint_components, "BRAIN_RESEARCH_STATE_V2_SCHEMA_FINGERPRINT_COMPONENTS_NONCANONICAL")
        if self.exclusions != tuple(BrainResearchComparisonStateV2Exclusion):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_EXCLUSIONS_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_PROVENANCE_NONCANONICAL")
        if self.fingerprint != brain_research_comparison_state_v2_schema_fingerprint(self):
            raise ValueError("BRAIN_RESEARCH_STATE_V2_SCHEMA_FINGERPRINT_MISMATCH")


def create_frozen_brain_research_comparison_state_v2_schema(
    *, schema_id: str, version: str, proposal_schema_id: str, proposal_version: str,
    approved_by: str, provenance: tuple[tuple[str, str], ...],
) -> FrozenBrainResearchComparisonStateV2Schema:
    """Create immutable metadata only; this is not a v2 builder."""
    values = dict(
        schema_id=schema_id, version=version,
        proposal_schema_id=proposal_schema_id, proposal_version=proposal_version,
        approval_status=BrainResearchComparisonStateV2SchemaApprovalStatus.APPROVED,
        approved_by=approved_by, selected_for_future_builder=False, active=False,
        state_schema_id=_STATE_SCHEMA[0], state_schema_version=_STATE_SCHEMA[1],
        research_methodology_id=_METHODOLOGY[0], research_methodology_version=_METHODOLOGY[1],
        comparison_mode=ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME,
        comparability_policy_id=_COMPARABILITY_POLICY[0], comparability_policy_version=_COMPARABILITY_POLICY[1], comparability_policy_fingerprint=_COMPARABILITY_POLICY[2],
        bundle_schema_id=_BUNDLE_SCHEMA[0], bundle_schema_version=_BUNDLE_SCHEMA[1], bundle_schema_fingerprint=_BUNDLE_SCHEMA[2],
        observation_schema_id=_OBSERVATION_SCHEMA[0], observation_schema_version=_OBSERVATION_SCHEMA[1], observation_schema_fingerprint=_OBSERVATION_SCHEMA[2],
        wrapper_schema_id=_WRAPPER_SCHEMA[0], wrapper_schema_version=_WRAPPER_SCHEMA[1], wrapper_schema_fingerprint=_WRAPPER_SCHEMA[2],
        selector_policy_id=_SELECTOR_POLICY[0], selector_policy_version=_SELECTOR_POLICY[1], selector_policy_fingerprint=_SELECTOR_POLICY[2],
        future_builder_api="build_brain_research_comparison_state_v2",
        financial_bundle_required=True, financial_wrappers_required=True,
        typed_financial_failures_required=True, explicit_upstream_inputs_required=True,
        exact_instrument_parity_required=True, exact_as_of_parity_required=True,
        wrapper_visible_as_of_not_after_state_as_of=True,
        wrapper_bundle_one_to_one_required=True, duplicate_full_slot_rejected=True,
        no_alternate_financial_input_path=True,
        financial_dimension=ResearchComparabilityDomain.FINANCIAL_RAW,
        numeric_source_role=FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION,
        retained_reference_source_role=FinancialObservationSourceRole.FINANCIAL_EVIDENCE_REFERENCE,
        reference_numeric_pairing_prohibited=True,
        double_count_semantic_aggregation_prohibited=True,
        admitted_period_strengths=(
            FinancialMetricPeriodIdentityStrength.COMPLETE,
            FinancialMetricPeriodIdentityStrength.PARTIAL,
        ),
        financial_failure_stages=tuple(FinancialResearchInputFailureStage),
        failures_are_dimension_local=True, failure_only_bundle_allowed=True,
        empty_wrapper_set_allowed_only_for_empty_bundle=True,
        availability_rules=tuple(FinancialDimensionAvailabilityRule),
        wrapper_ordering="GENERIC_FULL_OBSERVATION_SLOT_IDENTITY",
        failure_ordering="SEMANTIC_KEY_STAGE_STATUS_REASONS_UPSTREAM_FINGERPRINT",
        state_fingerprint_components=(
            "COMPARABILITY_POLICY_V2", "DIMENSIONS", "FINANCIAL_BUNDLE_LINEAGE",
            "FINANCIAL_FAILURE_LINEAGE", "FINANCIAL_NUMERIC_WRAPPERS",
            "METHODOLOGY_SCHEMA", "SOURCE_UNIFIED_STATE_LINEAGE",
        ),
        v1_v2_foundationally_non_comparable=True, v2_dimension_local_failure=True,
        exclusions=tuple(BrainResearchComparisonStateV2Exclusion),
        provenance=tuple(sorted(set(provenance))),
    )
    return FrozenBrainResearchComparisonStateV2Schema(
        **values, fingerprint=brain_research_comparison_state_v2_schema_fingerprint_values(values),
    )


def brain_research_comparison_state_v2_schema_fingerprint(
    value: FrozenBrainResearchComparisonStateV2Schema,
) -> str:
    return brain_research_comparison_state_v2_schema_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_research_comparison_state_v2_schema_fingerprint_values(values: dict) -> str:
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


CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA = (
    create_frozen_brain_research_comparison_state_v2_schema(
        schema_id="brain-research-comparison-state-schema",
        version="v2-approved",
        proposal_schema_id="brain-research-comparison-state-schema",
        proposal_version="v2-proposed",
        approved_by="human:Akash-Verma",
        provenance=(
            ("governance_approval", "U14D-6T"),
            ("comparability_policy", "brain-research-comparability-policy/v2-approved"),
            ("proposal_schema", "brain-research-comparison-state-schema/v2-proposed"),
            ("scope", "PASSIVE_FINANCIAL_INTEGRATION_CONTRACT_ONLY"),
        ),
    )
)


__all__ = (
    "BrainResearchComparisonStateV2Exclusion",
    "BrainResearchComparisonStateV2SchemaApprovalStatus",
    "CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA",
    "FinancialDimensionAvailabilityRule",
    "FrozenBrainResearchComparisonStateV2Schema",
    "brain_research_comparison_state_v2_schema_fingerprint",
    "create_frozen_brain_research_comparison_state_v2_schema",
)
