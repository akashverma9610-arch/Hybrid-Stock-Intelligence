from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import app.fundamentals.financial_fact_vintage_selection_policy as policy_module
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageAvailabilityRule,
    FinancialFactVintageDuplicateRequirement,
    FinancialFactVintageFactFingerprintOwner,
    FinancialFactVintageFoundationalFailure,
    FinancialFactVintageRevisionRequirement,
    FinancialFactVintageSelectionExclusion,
    FinancialFactVintageSelectionMode,
    FinancialFactVintageSelectionPolicyApprovalStatus,
    FinancialFactVintageSelectionReason,
    FinancialFactVintageSelectionStatus,
    FinancialFactVintageSelectionWarning,
    FinancialFactVintageSemanticKeyDimension,
    financial_fact_vintage_selection_policy_fingerprint,
)


POLICY = CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY


def test_frozen_policy_identity_lineage_and_inactive_state_are_exact() -> None:
    assert (POLICY.policy_id, POLICY.version) == ("financial-fact-vintage-selection-policy", "v1-approved")
    assert (POLICY.proposal_policy_id, POLICY.proposal_version) == ("financial-fact-vintage-selection-policy", "v1-proposed")
    assert POLICY.approval_status is FinancialFactVintageSelectionPolicyApprovalStatus.APPROVED
    assert POLICY.approved_by == "human:Akash-Verma"
    assert not POLICY.selected_for_future_selector
    assert not POLICY.active
    assert POLICY.selection_mode is FinancialFactVintageSelectionMode.KNOWLEDGE_AT_THE_TIME


def test_fingerprint_is_deterministic_and_tamper_closed() -> None:
    assert financial_fact_vintage_selection_policy_fingerprint(POLICY) == POLICY.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(POLICY, version="v1-tampered")


def test_pit_first_observed_and_no_backdating_semantics_are_frozen() -> None:
    assert POLICY.availability_rule is FinancialFactVintageAvailabilityRule.MAX_PUBLISHED_AT_RECEIVED_AT
    assert POLICY.timezone_aware_timestamps_required
    assert POLICY.first_observed_visibility_for_unknown_publication
    assert POLICY.future_facts_excluded
    assert not POLICY.restated_history_enabled


def test_semantic_key_protects_scope_period_and_representation_without_provider_priority() -> None:
    assert POLICY.semantic_key_dimensions == tuple(FinancialFactVintageSemanticKeyDimension)
    assert {
        FinancialFactVintageSemanticKeyDimension.STATEMENT_SCOPE,
        FinancialFactVintageSemanticKeyDimension.PERIOD_TYPE,
        FinancialFactVintageSemanticKeyDimension.VALUE_BASIS,
        FinancialFactVintageSemanticKeyDimension.CURRENCY,
        FinancialFactVintageSemanticKeyDimension.UNIT,
        FinancialFactVintageSemanticKeyDimension.SCALE,
        FinancialFactVintageSemanticKeyDimension.NORMALIZATION_VERSION,
    }.issubset(POLICY.semantic_key_dimensions)
    assert POLICY.unknown_scope_is_distinct
    assert not POLICY.scope_preference_enabled
    assert not POLICY.representation_conversion_enabled
    assert not POLICY.provider_priority_enabled


def test_revision_duplicate_and_conflict_guards_are_exact() -> None:
    assert POLICY.revision_requirements == tuple(FinancialFactVintageRevisionRequirement)
    assert POLICY.exact_duplicate_requirements == tuple(FinancialFactVintageDuplicateRequirement)
    assert POLICY.revised_without_parent_warning is FinancialFactVintageSelectionWarning.REVISED_WITHOUT_EXPLICIT_PARENT
    assert not POLICY.latest_timestamp_shortcut_enabled
    assert {
        FinancialFactVintageSelectionReason.REVISION_PARENT_MISSING,
        FinancialFactVintageSelectionReason.CROSS_SEMANTIC_REVISION,
        FinancialFactVintageSelectionReason.INVALID_REVISION_CHRONOLOGY,
        FinancialFactVintageSelectionReason.REVISION_BRANCH_CONFLICT,
        FinancialFactVintageSelectionReason.REVISION_CYCLE,
        FinancialFactVintageSelectionReason.UNRESOLVED_FACT_CONFLICT,
    }.issubset(POLICY.reason_vocabulary)


def test_status_reason_batch_and_fingerprint_boundaries_are_frozen() -> None:
    assert POLICY.status_vocabulary == tuple(FinancialFactVintageSelectionStatus)
    assert POLICY.reason_vocabulary == tuple(FinancialFactVintageSelectionReason)
    assert POLICY.dimension_local_failure
    assert POLICY.foundational_failures == tuple(FinancialFactVintageFoundationalFailure)
    assert POLICY.deterministic_ordering_required
    assert POLICY.fact_fingerprint_owner is FinancialFactVintageFactFingerprintOwner.FUTURE_FINANCIAL_METRIC_OBSERVATION_SCHEMA


def test_explicit_revision_and_duplicate_requirements_prevent_shortcuts() -> None:
    assert {
        FinancialFactVintageRevisionRequirement.EXPLICIT_PARENT_LINK,
        FinancialFactVintageRevisionRequirement.SAME_SEMANTIC_KEY,
        FinancialFactVintageRevisionRequirement.PARENT_PRESENT,
        FinancialFactVintageRevisionRequirement.ACYCLIC,
        FinancialFactVintageRevisionRequirement.LINEAR_OR_EXPLICITLY_RESOLVED,
        FinancialFactVintageRevisionRequirement.CHILD_AVAILABLE_AT_NOT_EARLIER_THAN_PARENT,
        FinancialFactVintageRevisionRequirement.UNIQUE_TERMINAL_ELIGIBLE_CANDIDATE,
    } == set(POLICY.revision_requirements)
    assert {
        FinancialFactVintageDuplicateRequirement.SAME_UNDERLYING_FILING_OR_SOURCE_IDENTITY,
        FinancialFactVintageDuplicateRequirement.SAME_DECIMAL_VALUE,
        FinancialFactVintageDuplicateRequirement.AUDITABLE_PROVENANCE_RETAINED,
    }.issubset(POLICY.exact_duplicate_requirements)


def test_policy_has_no_runtime_selector_or_action_layer() -> None:
    assert not hasattr(policy_module, "select_financial_fact_vintage")
    assert not hasattr(policy_module, "select_financial_fact_vintages")
    assert not hasattr(policy_module, "materialize_financial_metric_observation")
    assert not hasattr(policy_module, "build_financial_metric_trajectory")
    assert set(POLICY.exclusions) == set(FinancialFactVintageSelectionExclusion)


def test_policy_module_has_no_store_network_or_api_wiring() -> None:
    source = inspect.getsource(policy_module)
    for forbidden in (
        "FinancialFactStore",
        "SQLiteFinancialFactStore",
        "PostgreSQLFinancialFactStore",
        "sqlite3",
        "requests",
        "urllib",
        "FastAPI",
        "APIRouter",
    ):
        assert forbidden not in source
