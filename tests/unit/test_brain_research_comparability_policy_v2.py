"""U14D-6N static v2 governance tests; no matcher or Brain integration."""
from __future__ import annotations

from dataclasses import replace

import pytest

import app.intelligence.brain_research_comparability_policy as policy_module
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
    FinancialObservationLineageOnlyField,
    FinancialObservationMatchingRequirement,
    FinancialObservationPeriodDisposition,
    FinancialObservationSlotIdentityComponent,
    FinancialObservationSourceRole,
    ResearchComparabilityDomain,
    ResearchComparabilityStatus,
    ResearchComparisonMode,
    brain_research_comparability_policy_fingerprint,
)


V1 = CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY
V2 = FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2
RULE = V2.financial_observation_rule


def test_v2_identity_approval_inactive_mode_lineage_and_deterministic_fingerprint() -> None:
    assert (V2.policy_id, V2.version) == ("brain-research-comparability-policy", "v2-approved")
    assert (V2.proposal_policy_id, V2.proposal_version) == ("brain-research-comparability-policy", "v2-proposed")
    assert V2.approved_by == "human:Akash-Verma"
    assert not V2.selected_for_future_comparator and not V2.active
    assert V2.comparison_mode is ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME
    assert (V2.predecessor_policy_id, V2.predecessor_policy_version, V2.predecessor_policy_fingerprint) == (
        V1.policy_id, V1.version, V1.fingerprint,
    )
    assert brain_research_comparability_policy_fingerprint(V2) == V2.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(
            V2,
            financial_observation_rule=replace(
                RULE, contradictory_selector_attestation_disposition="TAMPERED"
            ),
        )


def test_v2_retains_every_v1_manifest_rule_and_frozen_safety_boundary() -> None:
    assert V2.source_rules == V1.source_rules
    assert V2.domain_rules == V1.domain_rules
    assert V2.evidence_preconditions == V1.evidence_preconditions
    assert V2.non_comparable_cases == V1.non_comparable_cases
    assert V2.exclusions == V1.exclusions
    assert V2.dimension_local_failure and V2.no_cross_version_equivalence
    assert V2.native_typed_lineage_required and V2.missing_is_not_zero


def test_v2_freezes_exact_bundle_observation_and_selector_lineage() -> None:
    assert RULE is not None
    assert RULE.domain is ResearchComparabilityDomain.FINANCIAL_RAW
    assert (RULE.bundle_schema_id, RULE.bundle_schema_version, RULE.bundle_schema_fingerprint) == (
        "financial-research-observation-bundle-schema", "v1-approved",
        "aba6123afc78781b4ac011fe048ed10d91b7e8af3f10944f25558be5f2036a89",
    )
    assert (RULE.observation_schema_id, RULE.observation_schema_version, RULE.observation_schema_fingerprint) == (
        "financial-metric-observation-schema", "v1-approved",
        "6d55e73ee78f0074789165952a287d9b8b6ec801ce98703e9a136603f3da3caf",
    )
    assert (RULE.selector_policy_id, RULE.selector_policy_version, RULE.selector_policy_fingerprint) == (
        "financial-fact-vintage-selection-policy", "v1-approved",
        "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13",
    )
    assert RULE.knowledge_mode is ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME


def test_v2_freezes_same_as_of_visible_as_of_and_partial_dispositions() -> None:
    assert RULE is not None
    assert RULE.selector_as_of_exact_required
    assert RULE.visible_as_of_must_not_exceed_state_as_of
    assert RULE.missing_selector_attestation_status is ResearchComparabilityStatus.INSUFFICIENT
    assert RULE.contradictory_selector_attestation_disposition == "INVALID_FINANCIAL_DIMENSION_INPUT"
    assert RULE.period_dispositions == tuple(FinancialObservationPeriodDisposition)


def test_v2_slot_key_is_complete_and_lineage_identifiers_are_not_slot_fields() -> None:
    assert RULE is not None
    assert RULE.slot_identity_components == tuple(FinancialObservationSlotIdentityComponent)
    assert RULE.lineage_only_fields == tuple(FinancialObservationLineageOnlyField)
    assert {
        FinancialObservationSlotIdentityComponent.CANONICAL_INSTRUMENT,
        FinancialObservationSlotIdentityComponent.FACT_KIND,
        FinancialObservationSlotIdentityComponent.METRIC,
        FinancialObservationSlotIdentityComponent.STATEMENT_SCOPE,
        FinancialObservationSlotIdentityComponent.PERIOD_TYPE,
        FinancialObservationSlotIdentityComponent.VALUE_BASIS,
        FinancialObservationSlotIdentityComponent.PERIOD_START,
        FinancialObservationSlotIdentityComponent.PERIOD_END,
        FinancialObservationSlotIdentityComponent.FISCAL_YEAR,
        FinancialObservationSlotIdentityComponent.FISCAL_QUARTER,
        FinancialObservationSlotIdentityComponent.VALUE_DIMENSION,
        FinancialObservationSlotIdentityComponent.CURRENCY,
        FinancialObservationSlotIdentityComponent.UNIT,
        FinancialObservationSlotIdentityComponent.SCALE,
        FinancialObservationSlotIdentityComponent.NORMALIZATION_IDENTITY,
        FinancialObservationSlotIdentityComponent.PERIOD_FINGERPRINT,
        FinancialObservationSlotIdentityComponent.SOURCE_ROLE,
        FinancialObservationSlotIdentityComponent.OBSERVATION_SCHEMA_IDENTITY,
    } == set(RULE.slot_identity_components)


def test_v2_freezes_multiple_period_added_removed_revision_and_duplicate_requirements() -> None:
    assert RULE is not None
    assert RULE.matching_requirements == tuple(FinancialObservationMatchingRequirement)
    assert {
        FinancialObservationMatchingRequirement.FULL_SEMANTIC_SLOT_KEY,
        FinancialObservationMatchingRequirement.EXACT_KEY_PAIRING,
        FinancialObservationMatchingRequirement.PREVIOUS_ONLY_REMOVED,
        FinancialObservationMatchingRequirement.CURRENT_ONLY_ADDED,
        FinancialObservationMatchingRequirement.NO_METRIC_LABEL_FALLBACK,
        FinancialObservationMatchingRequirement.NO_SAME_LABEL_ZIP_FALLBACK,
        FinancialObservationMatchingRequirement.DUPLICATE_FULL_SLOT_FAIL_CLOSED,
    } == set(RULE.matching_requirements)


def test_v2_freezes_reference_numeric_role_separation_without_runtime_surface() -> None:
    assert RULE is not None
    assert RULE.source_roles == tuple(FinancialObservationSourceRole)
    assert RULE.reference_numeric_pairing_prohibited
    source = open(policy_module.__file__, encoding="utf-8").read()
    assert not any(token in source for token in (
        "compare_brain_research_states(", "ResearchStateDelta(", "build_brain_research_comparison_state(",
        "requests.", "urlopen", "CREATE TABLE", "INSERT INTO", "trajectory", "recommend(",
    ))
