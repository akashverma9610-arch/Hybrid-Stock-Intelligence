from __future__ import annotations

from dataclasses import replace

import pytest

import app.intelligence.brain_research_comparability_policy as policy_module
from app.intelligence.brain_research_comparability_policy import (
    BrainResearchComparabilityPolicyApprovalStatus,
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    ResearchComparabilityDomain,
    ResearchComparabilityExclusion,
    ResearchComparabilityStatus,
    ResearchComparisonMode,
    ResearchEvidencePrecondition,
    ResearchNonComparableCase,
    ResearchSourceEligibility,
    brain_research_comparability_policy_fingerprint,
)


POLICY = CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY


def _source(domain: ResearchComparabilityDomain):
    return next(value for value in POLICY.source_rules if value.domain is domain)


def _domain(domain: ResearchComparabilityDomain):
    return next(value for value in POLICY.domain_rules if value.domain is domain)


def test_exact_approved_identity_lineage_human_approval_and_inactive_state() -> None:
    assert (POLICY.policy_id, POLICY.version) == ("brain-research-comparability-policy", "v1-approved")
    assert (POLICY.proposal_policy_id, POLICY.proposal_version) == ("brain-research-comparability-policy", "v1-proposed")
    assert POLICY.approval_status is BrainResearchComparabilityPolicyApprovalStatus.APPROVED
    assert POLICY.approved_by == "human:Akash-Verma"
    assert not POLICY.selected_for_future_comparator and not POLICY.active
    assert ("proposal_policy", "brain-research-comparability-policy/v1-proposed") in POLICY.provenance


def test_policy_fingerprint_is_deterministic_and_tamper_closed() -> None:
    assert brain_research_comparability_policy_fingerprint(POLICY) == POLICY.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(POLICY, version="v1-tampered")


def test_exact_vocabulary_and_knowledge_at_time_safety_are_frozen() -> None:
    assert POLICY.source_eligibility_vocabulary == tuple(ResearchSourceEligibility)
    assert POLICY.comparability_status_vocabulary == tuple(ResearchComparabilityStatus)
    assert POLICY.comparison_mode is ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME
    assert not POLICY.restated_history_enabled
    assert POLICY.dimension_local_failure
    assert POLICY.no_cross_version_equivalence
    assert POLICY.native_typed_lineage_required
    assert POLICY.missing_is_not_zero


def test_source_eligibility_protects_current_only_and_unsupported_boundaries() -> None:
    assert _source(ResearchComparabilityDomain.FINANCIAL_RAW).eligibility is ResearchSourceEligibility.PIT_REBUILDABLE
    assert _source(ResearchComparabilityDomain.MARKET_PRICE).eligibility is ResearchSourceEligibility.PIT_REBUILDABLE
    assert _source(ResearchComparabilityDomain.PRE_BREAKOUT_SETUP).eligibility is ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY
    assert _source(ResearchComparabilityDomain.DECISION_SCORE).eligibility is ResearchSourceEligibility.DURABLE_ARTIFACT_ONLY
    assert _source(ResearchComparabilityDomain.CORPORATE_ACTION_REFERENCE).eligibility is ResearchSourceEligibility.REFERENCE_ONLY
    for domain in (
        ResearchComparabilityDomain.SECTOR_RS,
        ResearchComparabilityDomain.SECTOR_BREADTH,
        ResearchComparabilityDomain.SECTOR_RANK,
        ResearchComparabilityDomain.SECTOR_TOP3,
        ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION,
    ):
        assert _source(domain).eligibility is ResearchSourceEligibility.CURRENT_ONLY
    assert _source(ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE).eligibility is ResearchSourceEligibility.UNSUPPORTED
    assert _source(ResearchComparabilityDomain.VALUATION).eligibility is ResearchSourceEligibility.UNSUPPORTED


def test_frozen_noncomparable_safety_cases_cover_financial_setup_reliability_and_integrity() -> None:
    cases = set(POLICY.non_comparable_cases)
    assert {
        ResearchNonComparableCase.FINANCIAL_SCOPE_MISMATCH,
        ResearchNonComparableCase.FINANCIAL_PERIOD_OR_BASIS_MISMATCH,
        ResearchNonComparableCase.UNSUPPORTED_FINANCIAL_CONVERSION,
        ResearchNonComparableCase.REQUIRED_VERSION_OR_METHODOLOGY_MISMATCH,
        ResearchNonComparableCase.SETUP_POLICY_FINGERPRINT_MISMATCH,
        ResearchNonComparableCase.CONFLICTED_RELIABILITY,
        ResearchNonComparableCase.HISTORICAL_INTEGRITY_INVALID,
    }.issubset(cases)
    financial = _domain(ResearchComparabilityDomain.FINANCIAL_RAW)
    assert {"STATEMENT_SCOPE", "PERIOD_TYPE", "VALUE_BASIS", "UNIT", "SCALE", "PIT"}.issubset(financial.required_identity)
    setup = _domain(ResearchComparabilityDomain.PRE_BREAKOUT_SETUP)
    assert {"POLICY_ID", "POLICY_VERSION", "POLICY_FINGERPRINT", "TICK_RESOLUTION"}.issubset(setup.required_identity)


def test_evidence_preconditions_fail_closed_without_enabling_a_stale_exception() -> None:
    rules = {value.condition: value for value in POLICY.evidence_preconditions}
    assert rules[ResearchEvidencePrecondition.RELIABILITY_CONFLICTED].status is ResearchComparabilityStatus.NON_COMPARABLE
    assert rules[ResearchEvidencePrecondition.HISTORICAL_INTEGRITY_INVALID].status is ResearchComparabilityStatus.NON_COMPARABLE
    assert rules[ResearchEvidencePrecondition.REQUIRED_EVIDENCE_UNAVAILABLE].status is ResearchComparabilityStatus.INSUFFICIENT
    stale = rules[ResearchEvidencePrecondition.EVIDENCE_STALE]
    assert stale.status is ResearchComparabilityStatus.INSUFFICIENT
    assert stale.domain_specific_rule_required


def test_policy_has_no_semantic_or_runtime_comparison_surface() -> None:
    assert set(POLICY.exclusions) == set(ResearchComparabilityExclusion)
    forbidden = ("compare_brain_research_states", "compare_research_states", "interpret_thesis", "interpret_opportunity")
    assert not any(hasattr(policy_module, name) for name in forbidden)
    serialized = repr(POLICY)
    assert "THESIS_STRENGTHENED" not in serialized
    assert "OPPORTUNITY_IMPROVED" not in serialized
    assert ResearchComparabilityExclusion.BUY_HOLD_SELL_TRIM_ROTATE in POLICY.exclusions
