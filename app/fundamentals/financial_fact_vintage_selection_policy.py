"""Frozen governance policy for future PIT financial fact-vintage selection.

This module is immutable policy metadata only. It deliberately does not inspect
FinancialFact values, query a store, traverse a revision graph, select a fact,
or materialize an observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class FinancialFactVintageSelectionPolicyApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialFactVintageSelectionMode(StrEnum):
    KNOWLEDGE_AT_THE_TIME = "KNOWLEDGE_AT_THE_TIME"


class FinancialFactVintageAvailabilityRule(StrEnum):
    MAX_PUBLISHED_AT_RECEIVED_AT = "MAX_PUBLISHED_AT_RECEIVED_AT"


class FinancialFactVintageSemanticKeyDimension(StrEnum):
    CANONICAL_INSTRUMENT = "CANONICAL_INSTRUMENT"
    FINANCIAL_METRIC = "FINANCIAL_METRIC"
    FACT_KIND = "FACT_KIND"
    STATEMENT_SCOPE = "STATEMENT_SCOPE"
    PERIOD_TYPE = "PERIOD_TYPE"
    VALUE_BASIS = "VALUE_BASIS"
    PERIOD_END = "PERIOD_END"
    PERIOD_START_WHERE_SUPPLIED = "PERIOD_START_WHERE_SUPPLIED"
    FISCAL_YEAR_WHERE_SUPPLIED = "FISCAL_YEAR_WHERE_SUPPLIED"
    FISCAL_QUARTER_WHERE_SUPPLIED = "FISCAL_QUARTER_WHERE_SUPPLIED"
    VALUE_DIMENSION = "VALUE_DIMENSION"
    CURRENCY = "CURRENCY"
    UNIT = "UNIT"
    SCALE = "SCALE"
    NORMALIZATION_VERSION = "NORMALIZATION_VERSION"


class FinancialFactVintageRevisionRequirement(StrEnum):
    EXPLICIT_PARENT_LINK = "EXPLICIT_PARENT_LINK"
    SAME_SEMANTIC_KEY = "SAME_SEMANTIC_KEY"
    PARENT_PRESENT = "PARENT_PRESENT"
    ACYCLIC = "ACYCLIC"
    LINEAR_OR_EXPLICITLY_RESOLVED = "LINEAR_OR_EXPLICITLY_RESOLVED"
    CHILD_AVAILABLE_AT_NOT_EARLIER_THAN_PARENT = "CHILD_AVAILABLE_AT_NOT_EARLIER_THAN_PARENT"
    UNIQUE_TERMINAL_ELIGIBLE_CANDIDATE = "UNIQUE_TERMINAL_ELIGIBLE_CANDIDATE"


class FinancialFactVintageDuplicateRequirement(StrEnum):
    SAME_UNDERLYING_FILING_OR_SOURCE_IDENTITY = "SAME_UNDERLYING_FILING_OR_SOURCE_IDENTITY"
    SAME_SEMANTIC_KEY = "SAME_SEMANTIC_KEY"
    SAME_DECIMAL_VALUE = "SAME_DECIMAL_VALUE"
    SAME_REPRESENTATION = "SAME_REPRESENTATION"
    COMPATIBLE_PIT_LINEAGE = "COMPATIBLE_PIT_LINEAGE"
    AUDITABLE_PROVENANCE_RETAINED = "AUDITABLE_PROVENANCE_RETAINED"


class FinancialFactVintageSelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    UNAVAILABLE = "UNAVAILABLE"
    CONFLICTED = "CONFLICTED"
    INVALID_LINEAGE = "INVALID_LINEAGE"
    INSUFFICIENT_IDENTITY = "INSUFFICIENT_IDENTITY"


class FinancialFactVintageSelectionReason(StrEnum):
    NO_PIT_ELIGIBLE_FACT = "NO_PIT_ELIGIBLE_FACT"
    UNRESOLVED_FACT_CONFLICT = "UNRESOLVED_FACT_CONFLICT"
    REVISION_PARENT_MISSING = "REVISION_PARENT_MISSING"
    CROSS_SEMANTIC_REVISION = "CROSS_SEMANTIC_REVISION"
    INVALID_REVISION_CHRONOLOGY = "INVALID_REVISION_CHRONOLOGY"
    REVISION_BRANCH_CONFLICT = "REVISION_BRANCH_CONFLICT"
    REVISION_CYCLE = "REVISION_CYCLE"
    AMBIGUOUS_SEMANTIC_KEY = "AMBIGUOUS_SEMANTIC_KEY"
    INVALID_SELECTOR_INPUT = "INVALID_SELECTOR_INPUT"


class FinancialFactVintageSelectionWarning(StrEnum):
    REVISED_WITHOUT_EXPLICIT_PARENT = "REVISED_WITHOUT_EXPLICIT_PARENT"


class FinancialFactVintageFoundationalFailure(StrEnum):
    INVALID_CANONICAL_INSTRUMENT_REQUEST = "INVALID_CANONICAL_INSTRUMENT_REQUEST"
    TIMEZONE_NAIVE_AS_OF = "TIMEZONE_NAIVE_AS_OF"
    MALFORMED_OR_TAMPERED_POLICY = "MALFORMED_OR_TAMPERED_POLICY"
    UNSUPPORTED_SELECTION_MODE = "UNSUPPORTED_SELECTION_MODE"
    INVALID_SOURCE_COLLECTION_CONTRACT = "INVALID_SOURCE_COLLECTION_CONTRACT"


class FinancialFactVintageFactFingerprintOwner(StrEnum):
    FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA = "FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA"


class FinancialFactVintageSelectionExclusion(StrEnum):
    OBSERVATION_MATERIALIZATION = "OBSERVATION_MATERIALIZATION"
    TRAJECTORY_CALCULATION = "TRAJECTORY_CALCULATION"
    FINANCIAL_DIRECTIONALITY = "FINANCIAL_DIRECTIONALITY"
    MATERIALITY_OR_CONFIRMATION = "MATERIALITY_OR_CONFIRMATION"
    THESIS_OR_OPPORTUNITY_INTERPRETATION = "THESIS_OR_OPPORTUNITY_INTERPRETATION"
    ALERT_OR_RECOMMENDATION = "ALERT_OR_RECOMMENDATION"
    BUY_HOLD_SELL_TRIM_ROTATE = "BUY_HOLD_SELL_TRIM_ROTATE"
    EXECUTION = "EXECUTION"


@dataclass(frozen=True, slots=True)
class FrozenFinancialFactVintageSelectionPolicy:
    """Approved factual selection governance; intentionally not selected or active."""

    policy_id: str
    version: str
    proposal_policy_id: str
    proposal_version: str
    approval_status: FinancialFactVintageSelectionPolicyApprovalStatus
    approved_by: str
    selected_for_future_selector: bool
    active: bool
    selection_mode: FinancialFactVintageSelectionMode
    availability_rule: FinancialFactVintageAvailabilityRule
    timezone_aware_timestamps_required: bool
    first_observed_visibility_for_unknown_publication: bool
    future_facts_excluded: bool
    restated_history_enabled: bool
    semantic_key_dimensions: tuple[FinancialFactVintageSemanticKeyDimension, ...]
    unknown_scope_is_distinct: bool
    scope_preference_enabled: bool
    representation_conversion_enabled: bool
    revision_requirements: tuple[FinancialFactVintageRevisionRequirement, ...]
    exact_duplicate_requirements: tuple[FinancialFactVintageDuplicateRequirement, ...]
    revised_without_parent_warning: FinancialFactVintageSelectionWarning
    status_vocabulary: tuple[FinancialFactVintageSelectionStatus, ...]
    reason_vocabulary: tuple[FinancialFactVintageSelectionReason, ...]
    dimension_local_failure: bool
    foundational_failures: tuple[FinancialFactVintageFoundationalFailure, ...]
    deterministic_ordering_required: bool
    provider_priority_enabled: bool
    latest_timestamp_shortcut_enabled: bool
    fact_fingerprint_owner: FinancialFactVintageFactFingerprintOwner
    exclusions: tuple[FinancialFactVintageSelectionExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.policy_id, self.version, self.proposal_policy_id, self.proposal_version, self.approved_by)):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not FinancialFactVintageSelectionPolicyApprovalStatus.APPROVED:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_APPROVAL_REQUIRED")
        if self.selected_for_future_selector or self.active:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_MUST_NOT_BE_ACTIVE")
        if self.selection_mode is not FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME or self.restated_history_enabled:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_KNOWLEDGE_AT_TIME_REQUIRED")
        if self.availability_rule is not FinancialFactVintageAvailabilityRule.MAX_PUBLISHED_AT_RECEIVED_AT:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_AVAILABLE_AT_RULE_REQUIRED")
        if not all((
            self.timezone_aware_timestamps_required,
            self.first_observed_visibility_for_unknown_publication,
            self.future_facts_excluded,
            self.unknown_scope_is_distinct,
            self.dimension_local_failure,
            self.deterministic_ordering_required,
        )):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_CORE_SAFETY_REQUIRED")
        if self.scope_preference_enabled or self.representation_conversion_enabled:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_SCOPE_OR_CONVERSION_FORBIDDEN")
        if self.provider_priority_enabled or self.latest_timestamp_shortcut_enabled:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_SHORTCUT_FORBIDDEN")
        if self.semantic_key_dimensions != tuple(FinancialFactVintageSemanticKeyDimension):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_KEY_DIMENSIONS_REQUIRED")
        if self.revision_requirements != tuple(FinancialFactVintageRevisionRequirement):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_REVISION_REQUIREMENTS_REQUIRED")
        if self.exact_duplicate_requirements != tuple(FinancialFactVintageDuplicateRequirement):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_DUPLICATE_REQUIREMENTS_REQUIRED")
        if self.status_vocabulary != tuple(FinancialFactVintageSelectionStatus):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_STATUS_VOCABULARY_REQUIRED")
        if self.reason_vocabulary != tuple(FinancialFactVintageSelectionReason):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_REASON_VOCABULARY_REQUIRED")
        if self.foundational_failures != tuple(FinancialFactVintageFoundationalFailure):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_FOUNDATIONAL_FAILURES_REQUIRED")
        if self.fact_fingerprint_owner is not FinancialFactVintageFactFingerprintOwner.FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA:
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_FINGERPRINT_OWNERSHIP_REQUIRED")
        if self.exclusions != tuple(FinancialFactVintageSelectionExclusion):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_EXCLUSIONS_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_PROVENANCE_NONCANONICAL")
        if self.fingerprint != financial_fact_vintage_selection_policy_fingerprint(self):
            raise ValueError("FINANCIAL_FACT_VINTAGE_SELECTION_POLICY_FINGERPRINT_MISMATCH")


def create_frozen_financial_fact_vintage_selection_policy(
    *, policy_id: str, version: str, proposal_policy_id: str, proposal_version: str,
    approved_by: str, provenance: tuple[tuple[str, str], ...],
) -> FrozenFinancialFactVintageSelectionPolicy:
    values = dict(
        policy_id=policy_id,
        version=version,
        proposal_policy_id=proposal_policy_id,
        proposal_version=proposal_version,
        approval_status=FinancialFactVintageSelectionPolicyApprovalStatus.APPROVED,
        approved_by=approved_by,
        selected_for_future_selector=False,
        active=False,
        selection_mode=FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME,
        availability_rule=FinancialFactVintageAvailabilityRule.MAX_PUBLISHED_AT_RECEIVED_AT,
        timezone_aware_timestamps_required=True,
        first_observed_visibility_for_unknown_publication=True,
        future_facts_excluded=True,
        restated_history_enabled=False,
        semantic_key_dimensions=tuple(FinancialFactVintageSemanticKeyDimension),
        unknown_scope_is_distinct=True,
        scope_preference_enabled=False,
        representation_conversion_enabled=False,
        revision_requirements=tuple(FinancialFactVintageRevisionRequirement),
        exact_duplicate_requirements=tuple(FinancialFactVintageDuplicateRequirement),
        revised_without_parent_warning=FinancialFactVintageSelectionWarning.REVISED_WITHOUT_EXPLICIT_PARENT,
        status_vocabulary=tuple(FinancialFactVintageSelectionStatus),
        reason_vocabulary=tuple(FinancialFactVintageSelectionReason),
        dimension_local_failure=True,
        foundational_failures=tuple(FinancialFactVintageFoundationalFailure),
        deterministic_ordering_required=True,
        provider_priority_enabled=False,
        latest_timestamp_shortcut_enabled=False,
        fact_fingerprint_owner=FinancialFactVintageFactFingerprintOwner.FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
        exclusions=tuple(FinancialFactVintageSelectionExclusion),
        provenance=tuple(sorted(set(provenance))),
    )
    return FrozenFinancialFactVintageSelectionPolicy(
        **values,
        fingerprint=financial_fact_vintage_selection_policy_fingerprint_values(values),
    )


def financial_fact_vintage_selection_policy_fingerprint(
    value: FrozenFinancialFactVintageSelectionPolicy,
) -> str:
    return financial_fact_vintage_selection_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_fact_vintage_selection_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"],
        version=values["version"],
        proposal_policy_id=values["proposal_policy_id"],
        proposal_version=values["proposal_version"],
        approval_status=values["approval_status"].value,
        approved_by=values["approved_by"],
        selected_for_future_selector=values["selected_for_future_selector"],
        active=values["active"],
        selection_mode=values["selection_mode"].value,
        availability_rule=values["availability_rule"].value,
        timezone_aware_timestamps_required=values["timezone_aware_timestamps_required"],
        first_observed_visibility_for_unknown_publication=values["first_observed_visibility_for_unknown_publication"],
        future_facts_excluded=values["future_facts_excluded"],
        restated_history_enabled=values["restated_history_enabled"],
        semantic_key_dimensions=tuple(item.value for item in values["semantic_key_dimensions"]),
        unknown_scope_is_distinct=values["unknown_scope_is_distinct"],
        scope_preference_enabled=values["scope_preference_enabled"],
        representation_conversion_enabled=values["representation_conversion_enabled"],
        revision_requirements=tuple(item.value for item in values["revision_requirements"]),
        exact_duplicate_requirements=tuple(item.value for item in values["exact_duplicate_requirements"]),
        revised_without_parent_warning=values["revised_without_parent_warning"].value,
        status_vocabulary=tuple(item.value for item in values["status_vocabulary"]),
        reason_vocabulary=tuple(item.value for item in values["reason_vocabulary"]),
        dimension_local_failure=values["dimension_local_failure"],
        foundational_failures=tuple(item.value for item in values["foundational_failures"]),
        deterministic_ordering_required=values["deterministic_ordering_required"],
        provider_priority_enabled=values["provider_priority_enabled"],
        latest_timestamp_shortcut_enabled=values["latest_timestamp_shortcut_enabled"],
        fact_fingerprint_owner=values["fact_fingerprint_owner"].value,
        exclusions=tuple(item.value for item in values["exclusions"]),
        provenance=values["provenance"],
    )


CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY = (
    create_frozen_financial_fact_vintage_selection_policy(
        policy_id="financial-fact-vintage-selection-policy",
        version="v1-approved",
        proposal_policy_id="financial-fact-vintage-selection-policy",
        proposal_version="v1-proposed",
        approved_by="human:Akash-Verma",
        provenance=(
            ("governance_approval", "U14D-6E"),
            ("proposal_policy", "financial-fact-vintage-selection-policy/v1-proposed"),
            ("scope", "FACTUAL_PIT_SELECTION_ONLY"),
        ),
    )
)


__all__ = (
    "CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY",
    "FinancialFactVintageAvailabilityRule",
    "FinancialFactVintageDuplicateRequirement",
    "FinancialFactVintageFactFingerprintOwner",
    "FinancialFactVintageFoundationalFailure",
    "FinancialFactVintageRevisionRequirement",
    "FinancialFactVintageSelectionExclusion",
    "FinancialFactVintageSelectionMode",
    "FinancialFactVintageSelectionPolicyApprovalStatus",
    "FinancialFactVintageSelectionReason",
    "FinancialFactVintageSelectionStatus",
    "FinancialFactVintageSelectionWarning",
    "FinancialFactVintageSemanticKeyDimension",
    "FrozenFinancialFactVintageSelectionPolicy",
    "create_frozen_financial_fact_vintage_selection_policy",
    "financial_fact_vintage_selection_policy_fingerprint",
)

