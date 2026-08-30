"""U14D-6T passive State-v2 financial-integration contract tests."""
from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

import app.intelligence.brain_research_comparison_state_v2_schema as module
from app.intelligence.brain_research_comparison_state_v2_schema import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA,
    BrainResearchComparisonStateV2SchemaApprovalStatus,
    FinancialDimensionAvailabilityRule,
    brain_research_comparison_state_v2_schema_fingerprint,
)
from app.intelligence.brain_research_comparability_policy import (
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
    ResearchComparisonMode,
)


SCHEMA = CURRENT_FROZEN_BRAIN_RESEARCH_COMPARISON_STATE_V2_SCHEMA


def test_v2_schema_identity_is_deterministic_approved_unselected_and_inactive() -> None:
    assert (SCHEMA.schema_id, SCHEMA.version) == ("brain-research-comparison-state-schema", "v2-approved")
    assert (SCHEMA.proposal_schema_id, SCHEMA.proposal_version) == ("brain-research-comparison-state-schema", "v2-proposed")
    assert (SCHEMA.state_schema_id, SCHEMA.state_schema_version) == ("brain-research-comparison-state", "v2")
    assert (SCHEMA.research_methodology_id, SCHEMA.research_methodology_version) == ("shared-brain-research-comparison", "v2")
    assert SCHEMA.approval_status is BrainResearchComparisonStateV2SchemaApprovalStatus.APPROVED
    assert SCHEMA.approved_by == "human:Akash-Verma"
    assert not SCHEMA.selected_for_future_builder and not SCHEMA.active
    assert SCHEMA.comparison_mode is ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME
    assert brain_research_comparison_state_v2_schema_fingerprint(SCHEMA) == SCHEMA.fingerprint


def test_v2_schema_binds_only_the_frozen_v2_policy_and_financial_lineage() -> None:
    assert (SCHEMA.comparability_policy_id, SCHEMA.comparability_policy_version, SCHEMA.comparability_policy_fingerprint) == (
        "brain-research-comparability-policy", "v2-approved",
        "1e6926fd84dcf82958a831674701afb28bf3a76a15e9fe19bbfe5d5f28df79d3",
    )
    assert (SCHEMA.bundle_schema_id, SCHEMA.bundle_schema_version) == ("financial-research-observation-bundle-schema", "v1-approved")
    assert (SCHEMA.observation_schema_id, SCHEMA.observation_schema_version) == ("financial-metric-observation-schema", "v1-approved")
    assert (SCHEMA.wrapper_schema_id, SCHEMA.wrapper_schema_version) == ("financial-research-observation-wrapper-schema", "v1-approved")
    assert (SCHEMA.selector_policy_id, SCHEMA.selector_policy_version) == ("financial-fact-vintage-selection-policy", "v1-approved")
    with pytest.raises(ValueError, match="POLICY_LINEAGE_REQUIRED"):
        replace(SCHEMA, comparability_policy_version="v1-approved")


def test_v2_schema_freezes_explicit_same_as_of_one_to_one_input_boundary() -> None:
    assert SCHEMA.future_builder_api == "build_brain_research_comparison_state_v2"
    assert SCHEMA.financial_bundle_required and SCHEMA.financial_wrappers_required
    assert SCHEMA.typed_financial_failures_required and SCHEMA.explicit_upstream_inputs_required
    assert SCHEMA.exact_instrument_parity_required and SCHEMA.exact_as_of_parity_required
    assert SCHEMA.wrapper_visible_as_of_not_after_state_as_of
    assert SCHEMA.wrapper_bundle_one_to_one_required and SCHEMA.duplicate_full_slot_rejected
    assert SCHEMA.no_alternate_financial_input_path
    assert SCHEMA.failure_only_bundle_allowed and SCHEMA.empty_wrapper_set_allowed_only_for_empty_bundle


def test_v2_schema_preserves_financial_raw_roles_periods_failures_and_multiple_slots() -> None:
    assert SCHEMA.financial_dimension is ResearchComparabilityDomain.FINANCIAL_RAW
    assert SCHEMA.numeric_source_role is FinancialObservationSourceRole.FINANCIAL_NUMERIC_OBSERVATION
    assert SCHEMA.retained_reference_source_role is FinancialObservationSourceRole.FINANCIAL_EVIDENCE_REFERENCE
    assert SCHEMA.reference_numeric_pairing_prohibited
    assert SCHEMA.double_count_semantic_aggregation_prohibited
    assert tuple(item.value for item in SCHEMA.admitted_period_strengths) == ("COMPLETE", "PARTIAL")
    assert tuple(item.value for item in SCHEMA.financial_failure_stages) == ("SELECTION", "MATERIALIZATION")
    assert SCHEMA.failures_are_dimension_local
    assert SCHEMA.availability_rules == tuple(FinancialDimensionAvailabilityRule)
    assert SCHEMA.wrapper_ordering == "GENERIC_FULL_OBSERVATION_SLOT_IDENTITY"


def test_v2_schema_freezes_cross_version_firewall_fingerprint_ordering_and_tamper_closure() -> None:
    assert SCHEMA.v1_v2_foundationally_non_comparable and SCHEMA.v2_dimension_local_failure
    assert set(SCHEMA.state_fingerprint_components) == {
        "COMPARABILITY_POLICY_V2", "DIMENSIONS", "FINANCIAL_BUNDLE_LINEAGE",
        "FINANCIAL_FAILURE_LINEAGE", "FINANCIAL_NUMERIC_WRAPPERS",
        "METHODOLOGY_SCHEMA", "SOURCE_UNIFIED_STATE_LINEAGE",
    }
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(
            SCHEMA,
            provenance=tuple(sorted((*SCHEMA.provenance, ("tamper", "true")))),
        )


def test_v2_schema_is_passive_and_does_not_add_runtime_or_delta_surface() -> None:
    source = inspect.getsource(module)
    assert "def build_brain_research_comparison_state_v2" not in source
    assert "wrap_financial_research_observation_bundle(" not in source
    assert "build_financial_research_observation_bundle(" not in source
    assert not any(token in source for token in (
        "ResearchStateDelta(", "requests.", "urlopen", "CREATE TABLE", "INSERT INTO",
    ))
