"""U14D-7C governance tests for calibration-gated materiality policy only."""
from __future__ import annotations

import ast
import copy
import inspect

import pytest

import app.intelligence.research_semantic_materiality_policy as module
from app.fundamentals.financial_metric_trajectory_policy import FinancialMetricTrajectoryBasis as Basis
from app.fundamentals.models import FinancialMetric
from app.intelligence.research_metric_directionality import ResearchMetricDirectionalityOrientation as Orientation
from app.intelligence.research_semantic_materiality_policy import (
    CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY as POLICY,
    ResearchMetricMaterialityMethodDisposition as Method,
    ResearchSemanticMaterialityPolicy,
    ResearchSemanticMaterialityPolicyApprovalStatus as ApprovalStatus,
    ResearchSemanticMaterialityResult as Result,
    create_research_semantic_materiality_policy,
    research_metric_materiality_rule_fingerprint,
    research_semantic_materiality_policy_fingerprint,
)


ELIGIBLE_METRICS = (
    FinancialMetric.REVENUE, FinancialMetric.EBITDA, FinancialMetric.OPERATING_PROFIT,
    FinancialMetric.EBIT, FinancialMetric.PAT, FinancialMetric.EPS_BASIC,
    FinancialMetric.EPS_DILUTED,
)
ELIGIBLE_BASES = (Basis.YEAR_OVER_YEAR_QUARTER, Basis.YEAR_OVER_YEAR_ANNUAL)


def test_policy_identity_approval_and_deterministic_fingerprint() -> None:
    repeated = create_research_semantic_materiality_policy()
    assert POLICY == repeated
    assert (POLICY.policy_id, POLICY.version, POLICY.proposal_version) == (
        "research-semantic-materiality-policy", "v1-approved", "v1-proposed",
    )
    assert POLICY.approval_status is ApprovalStatus.APPROVED
    assert POLICY.approved_by == "human:Akash-Verma"
    assert POLICY.selected is False and POLICY.active is False
    assert POLICY.fingerprint == "7eceb06f9c99e496953188e6e0fce71987663600ffa5ab371978333f2fb9921a"
    assert POLICY.fingerprint == research_semantic_materiality_policy_fingerprint(POLICY)


def test_exact_upstream_policy_bindings_are_frozen() -> None:
    assert (POLICY.required_trajectory_policy_id, POLICY.required_trajectory_policy_version, POLICY.required_trajectory_policy_fingerprint) == (
        "financial-metric-trajectory-policy", "v1-approved", "15c73f130f99cd690ddb9241a616bb0c4a1604daf14e3b59c4cefad8e41d66a7",
    )
    assert (POLICY.required_directionality_policy_id, POLICY.required_directionality_policy_version, POLICY.required_directionality_policy_fingerprint) == (
        "research-metric-directionality-policy", "v1-approved", "0b4bcb46b00ec04c6c50610be0b5062237e39f2373e6df435ac788617db5a1dc",
    )


def test_exactly_fourteen_directionally_eligible_pairs_are_complete_and_unique() -> None:
    expected = {(metric, basis) for metric in ELIGIBLE_METRICS for basis in ELIGIBLE_BASES}
    assert len(POLICY.rules) == 14
    assert {(rule.metric, rule.basis) for rule in POLICY.rules} == expected
    assert POLICY.rules == tuple(sorted(POLICY.rules, key=lambda rule: (rule.metric.value, rule.basis.value)))


@pytest.mark.parametrize("metric", ELIGIBLE_METRICS)
@pytest.mark.parametrize("basis", ELIGIBLE_BASES)
def test_each_eligible_pair_is_calibration_required_with_no_threshold(metric, basis) -> None:
    rule = POLICY.rule_for(metric, basis)
    assert rule.method_disposition is Method.CALIBRATION_REQUIRED
    assert rule.threshold_specification is None
    assert rule.eligible_directionality_orientations == (
        Orientation.POTENTIALLY_FAVORABLE, Orientation.POTENTIALLY_UNFAVORABLE,
    )
    assert rule.fingerprint == research_metric_materiality_rule_fingerprint(rule)


def test_only_directional_orientations_are_eligible_and_every_other_orientation_is_not_applicable() -> None:
    assert POLICY.not_applicable_orientations == (
        Orientation.NO_DIRECTIONAL_CHANGE, Orientation.CONTEXT_DEPENDENT,
        Orientation.NON_DIRECTIONAL, Orientation.NOT_APPLICABLE,
    )
    assert POLICY.calibration_required_result is Result.UNDETERMINED
    assert POLICY.not_applicable_result is Result.NOT_APPLICABLE


def test_no_arbitrary_percentage_absolute_or_sign_transition_rule_exists() -> None:
    source = inspect.getsource(module)
    assert all(rule.threshold_specification is None for rule in POLICY.rules)
    for forbidden in ("abs(delta)", "relative_delta >=", "SIGN_CROSSING_MATERIAL", "NON_ZERO_IS_MATERIAL"):
        assert forbidden not in source


def test_calibration_evidence_contract_requires_empirical_and_human_governance_evidence() -> None:
    required = set(POLICY.calibration_evidence_requirements)
    assert {
        "EXACT_METRIC_AND_TRAJECTORY_BASIS", "HISTORICAL_PIT_VALID_OBSERVATION_POPULATION",
        "SAMPLE_PERIOD_AND_DISTRIBUTION_STATISTICS", "OUTLIER_POLICY", "COMPANY_SCALE_EFFECTS",
        "FALSE_POSITIVE_NEGATIVE_TRADEOFF", "METHODOLOGY_FINGERPRINT", "APPROVED_HUMAN_GOVERNANCE",
    } <= required
    assert not any(item.startswith("MINIMUM_SAMPLE_SIZE_") for item in required)


def test_policy_fingerprint_covers_rule_and_calibration_contract_mutation() -> None:
    changed = copy.copy(POLICY)
    object.__setattr__(changed, "calibration_evidence_requirements", POLICY.calibration_evidence_requirements[:-1])
    assert research_semantic_materiality_policy_fingerprint(changed) != POLICY.fingerprint
    changed_rule = copy.copy(POLICY.rules[0])
    object.__setattr__(changed_rule, "rationale_code", "OTHER")
    assert research_metric_materiality_rule_fingerprint(changed_rule) != POLICY.rules[0].fingerprint


def test_policy_constructor_fails_closed_for_missing_duplicate_or_extra_eligible_pairs() -> None:
    values = {field: getattr(POLICY, field) for field in POLICY.__dataclass_fields__}
    values["rules"] = POLICY.rules[:-1]
    values["fingerprint"] = module._policy_fingerprint_values({field: value for field, value in values.items() if field != "fingerprint"})
    with pytest.raises(ValueError, match="EXACT_ELIGIBLE_MATRIX_REQUIRED"):
        ResearchSemanticMaterialityPolicy(**values)
    values = {field: getattr(POLICY, field) for field in POLICY.__dataclass_fields__}
    values["rules"] = POLICY.rules + (POLICY.rules[0],)
    values["fingerprint"] = module._policy_fingerprint_values({field: value for field, value in values.items() if field != "fingerprint"})
    with pytest.raises(ValueError, match="EXACT_ELIGIBLE_MATRIX_REQUIRED"):
        ResearchSemanticMaterialityPolicy(**values)


def test_policy_constructor_fails_closed_for_another_directionality_lineage_or_activation() -> None:
    values = {field: getattr(POLICY, field) for field in POLICY.__dataclass_fields__}
    values["required_directionality_policy_version"] = "v2-approved"
    values["fingerprint"] = module._policy_fingerprint_values({field: value for field, value in values.items() if field != "fingerprint"})
    with pytest.raises(ValueError, match="DIRECTIONALITY_LINEAGE_REQUIRED"):
        ResearchSemanticMaterialityPolicy(**values)
    values = {field: getattr(POLICY, field) for field in POLICY.__dataclass_fields__}
    values["active"] = True
    values["fingerprint"] = module._policy_fingerprint_values({field: value for field, value in values.items() if field != "fingerprint"})
    with pytest.raises(ValueError, match="MUST_NOT_BE_ACTIVE"):
        ResearchSemanticMaterialityPolicy(**values)


def test_policy_module_has_no_runtime_interpreter_or_operational_dependency() -> None:
    source = inspect.getsource(module)
    imports = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom) and node.module}
    forbidden_imports = {
        "app.fundamentals.financial_metric_trajectory", "app.intelligence.research_state_delta",
        "app.intelligence.brain_research_comparison_state_v2", "app.scoring.engine",
    }
    assert not imports & forbidden_imports
    for forbidden in ("interpret_research_semantic_materiality", "sqlite3", "requests", "urllib", "FastAPI", "APIRouter", "BUY", "SELL", "alert", "recommendation", "acceleration"):
        assert forbidden not in source
    assert set(module.__all__) == {
        "CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY", "ResearchMetricMaterialityMethodDisposition",
        "ResearchMetricMaterialityRule", "ResearchSemanticMaterialityPolicy",
        "ResearchSemanticMaterialityPolicyApprovalStatus", "ResearchSemanticMaterialityResult",
        "create_research_semantic_materiality_policy", "research_metric_materiality_rule_fingerprint",
        "research_semantic_materiality_policy_fingerprint",
    }
