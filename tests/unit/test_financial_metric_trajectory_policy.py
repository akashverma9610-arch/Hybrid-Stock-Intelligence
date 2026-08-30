from __future__ import annotations

from dataclasses import replace
import inspect
import pytest

import app.fundamentals.financial_metric_trajectory_policy as module
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY as POLICY,
    FinancialMetricSignTransition, FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus, financial_metric_trajectory_policy_fingerprint,
)


def test_identity_approval_determinism_and_passive_governance() -> None:
    assert (POLICY.policy_id, POLICY.version, POLICY.proposal_version) == ("financial-metric-trajectory-policy", "v1-approved", "v1-proposed")
    assert POLICY.approved_by == "human:Akash-Verma" and not POLICY.selected and not POLICY.active
    assert financial_metric_trajectory_policy_fingerprint(POLICY) == POLICY.fingerprint
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(POLICY, provenance=tuple(sorted((*POLICY.provenance, ("tamper", "true")))))


def test_bases_parity_revision_and_arithmetic_rules_are_frozen() -> None:
    assert POLICY.bases == tuple(FinancialMetricTrajectoryBasis)
    assert POLICY.canonical_input == "FinancialResearchObservationBundle"
    assert POLICY.same_knowledge_cutoff_required and POLICY.same_period_revision_excluded
    assert POLICY.complete_period_required and POLICY.exact_representation_parity_required
    assert POLICY.fiscal_adjacency_required and POLICY.q4_to_q1_metadata_proof_required
    assert POLICY.cashflow_quarter_only_required and POLICY.annual_cashflow_allowed
    assert POLICY.eps_share_basis_proof_required
    assert POLICY.absolute_delta_formula == "current_value - previous_value"
    assert POLICY.positive_prior_relative_delta_formula == "(current_value - previous_value) / previous_value"
    assert POLICY.zero_or_negative_prior_relative_delta_unavailable


def test_numeric_status_and_sign_vocabularies_are_neutral_and_complete() -> None:
    assert POLICY.statuses == tuple(FinancialMetricTrajectoryStatus)
    assert POLICY.sign_transitions == tuple(FinancialMetricSignTransition)
    assert {"POSITIVE_TO_NEGATIVE", "NEGATIVE_TO_POSITIVE", "ZERO_TO_ZERO"} <= {value.value for value in POLICY.sign_transitions}
    assert not {"IMPROVED", "DEGRADED"}.intersection(value.value for value in POLICY.statuses)


def test_policy_has_no_builder_or_runtime_surface() -> None:
    source = inspect.getsource(module)
    assert "def build_financial_metric_trajectory" not in source
    assert not any(token in source for token in ("ResearchStateDelta(", "build_brain_research", "requests.", "urlopen", "CREATE TABLE", "INSERT INTO"))
