from __future__ import annotations

import copy
import inspect

import pytest

import app.intelligence.research_metric_directionality_policy as module
from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryBasis
from app.fundamentals.models import FinancialMetric
from app.intelligence.research_metric_directionality_policy import (
    CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY as POLICY,
    ResearchMetricDirectionalityDisposition as Disposition,
    research_metric_directionality_policy_fingerprint,
)


def _rule(metric, basis):
    return POLICY.rule_for(metric, basis).disposition


def test_frozen_identity_governance_and_fingerprint_are_exact_and_immutable() -> None:
    assert (POLICY.policy_id, POLICY.version, POLICY.proposal_version) == ("research-metric-directionality-policy", "v1-approved", "v1-proposed")
    assert POLICY.approved_by == "human:Akash-Verma"
    assert POLICY.approval_status.value == "APPROVED" and not POLICY.selected and not POLICY.active
    assert POLICY.fingerprint == research_metric_directionality_policy_fingerprint(POLICY)
    changed = copy.copy(POLICY); object.__setattr__(changed, "version", "v2-approved")
    assert research_metric_directionality_policy_fingerprint(changed) != POLICY.fingerprint


def test_matrix_is_complete_duplicate_free_and_future_enum_safety_is_explicit() -> None:
    expected = {
        (metric, basis)
        for metric in FinancialMetric
        if metric not in {
            FinancialMetric.CURRENT_BORROWINGS,
            FinancialMetric.NONCURRENT_BORROWINGS,
            FinancialMetric.OTHER_BANK_BALANCES,
            FinancialMetric.PURCHASE_OF_PROPERTY_PLANT_EQUIPMENT,
            FinancialMetric.PURCHASE_OF_INTANGIBLE_ASSETS,
        }
        for basis in FinancialMetricTrajectoryBasis
    }
    actual = {(rule.metric, rule.basis) for rule in POLICY.rules}
    assert len(POLICY.rules) == len(expected) == len(actual)
    assert all(rule.required_trajectory_policy_fingerprint == "15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7" for rule in POLICY.rules)
    assert "ROCE" in POLICY.unsupported_derived_metrics and "DEBT_TO_EQUITY" in POLICY.unsupported_derived_metrics


@pytest.mark.parametrize("metric", (FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT, FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC, FinancialMetric.EPS_DILUTED))
def test_selected_operating_and_earnings_metrics_are_conservative_sequential_and_narrow_yoy(metric) -> None:
    assert _rule(metric, FinancialMetricTrajectoryBasis.SEQUENTIAL_QUARTER) is Disposition.CONTEXT_DEPENDENT
    assert _rule(metric, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER) is Disposition.HIGHER_POTENTIALLY_FAVORABLE
    assert _rule(metric, FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_ANNUAL) is Disposition.HIGHER_POTENTIALLY_FAVORABLE
    assert _rule(metric, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL) is Disposition.NOT_APPLICABLE


def test_context_dependent_non_directional_and_empty_lower_sets_are_explicit() -> None:
    for metric in (FinancialMetric.PBT, FinancialMetric.CFO, FinancialMetric.FREE_CASH_FLOW, FinancialMetric.OTHER_INCOME, FinancialMetric.FINANCE_COST, FinancialMetric.TAX, FinancialMetric.CAPEX):
        assert all(_rule(metric, basis) is Disposition.CONTEXT_DEPENDENT for basis in FinancialMetricTrajectoryBasis if basis is not FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL)
    for metric in (FinancialMetric.CFI, FinancialMetric.CFF):
        assert all(_rule(metric, basis) is Disposition.NON_DIRECTIONAL for basis in FinancialMetricTrajectoryBasis if basis is not FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL)
    assert not [rule for rule in POLICY.rules if rule.disposition is Disposition.LOWER_POTENTIALLY_FAVORABLE]


def test_balance_sheet_and_representation_metrics_remain_conservative() -> None:
    for metric in (FinancialMetric.TOTAL_DEBT, FinancialMetric.CASH_AND_EQUIVALENTS, FinancialMetric.RECEIVABLES, FinancialMetric.INVENTORY, FinancialMetric.PAYABLES, FinancialMetric.TOTAL_ASSETS):
        assert _rule(metric, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL) is Disposition.CONTEXT_DEPENDENT
        assert all(_rule(metric, basis) is Disposition.NOT_APPLICABLE for basis in FinancialMetricTrajectoryBasis if basis is not FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL)
    for metric in (FinancialMetric.SHARES_OUTSTANDING, FinancialMetric.FACE_VALUE):
        assert _rule(metric, FinancialMetricTrajectoryBasis.POINT_IN_TIME_SEQUENTIAL) is Disposition.NON_DIRECTIONAL


def test_context_dependent_non_directional_and_unsupported_are_distinct_passive_concepts() -> None:
    assert Disposition.CONTEXT_DEPENDENT is not Disposition.NON_DIRECTIONAL
    assert Disposition.CONTEXT_DEPENDENT is not Disposition.UNSUPPORTED
    assert Disposition.NON_DIRECTIONAL is not Disposition.UNSUPPORTED
    assert {"ROCE", "ROE", "EBITDA_MARGIN", "PAT_MARGIN", "INTEREST_COVERAGE"} <= set(POLICY.unsupported_derived_metrics)


def test_policy_has_no_interpreter_or_runtime_brain_score_store_provider_surface() -> None:
    source = inspect.getsource(module)
    functions = {name for name, value in vars(module).items() if inspect.isfunction(value)}
    assert not {"interpret_research_metric_directionality", "evaluate_directionality", "build_financial_metric_trajectory"} & functions
    for forbidden in ("sqlite3", "requests", "urllib", "FastAPI", "APIRouter", "BrainResearchComparisonState", "ResearchStateDelta", "DecisionScore", "SixGate", "BUY", "SELL", "alert", "recommendation"):
        assert forbidden not in source
