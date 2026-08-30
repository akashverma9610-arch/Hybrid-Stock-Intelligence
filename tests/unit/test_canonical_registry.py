from dataclasses import replace
from decimal import Decimal

from app.registry.canonical import (
    BENCHMARKS, DATA_CONFIDENCE_POLICY, DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES,
    EXECUTION_GATES, EXECUTION_GATE_REGISTRY_VERSION, MISSING_DATA_POLICY, SCORING_POLICY,
    SCORING_POLICY_VERSION,
)
from app.registry.models import DiagnosticState, MissingDataTreatment, ScoreEligibility
from app.services.strategy_governance_service import StrategyGovernanceService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.governance_records import strategy_definition


def test_registry_has_exactly_61_unique_contiguous_rule_ids_and_complete_metadata() -> None:
    assert len(DIAGNOSTIC_RULES) == 61
    assert [rule.rule_id for rule in DIAGNOSTIC_RULES] == list(range(1, 62))
    assert len({rule.canonical_name for rule in DIAGNOSTIC_RULES}) == 61
    for rule in DIAGNOSTIC_RULES:
        assert all((rule.canonical_name, rule.category, rule.purpose, rule.required_inputs, rule.output_type,
                    rule.possible_statuses, rule.minimum_data_requirements, rule.missing_data_behavior,
                    rule.confidence_policy, rule.allowed_evidence_types, rule.calculation_version,
                    rule.notes_limitations))


def test_diagnostic_registry_is_not_a_decision_score() -> None:
    assert not hasattr(SCORING_POLICY, "diagnostic_count")
    assert SCORING_POLICY.total_weight_percent == Decimal("100")
    assert len(SCORING_POLICY.components) == 10
    assert all(component.component_minimum == Decimal("0.0") and component.component_maximum == Decimal("10.0") for component in SCORING_POLICY.components)


def test_data_confidence_and_missing_data_policy_are_separate_from_decision_score() -> None:
    assert DATA_CONFIDENCE_POLICY.decision_score_transformation == "NOT_DEFINED"
    assert DATA_CONFIDENCE_POLICY.crowd_data_confidence_is_separate is True
    assert MISSING_DATA_POLICY.default_weight_renormalization_allowed is False
    assert MissingDataTreatment.NO_SILENT_WEIGHT_RENORMALIZATION in MISSING_DATA_POLICY.treatments
    eligibility = MISSING_DATA_POLICY.score_eligibility({"market_regime": DiagnosticState.INSUFFICIENT_DATA})
    assert eligibility is ScoreEligibility.INELIGIBLE_MISSING_REQUIRED_COMPONENT


def test_exactly_six_canonical_gates_and_eight_benchmarks_exist() -> None:
    assert [gate.gate_id for gate in EXECUTION_GATES] == [1, 2, 3, 4, 5, 6]
    assert len(BENCHMARKS) == 8
    assert all(gate.missing_data_behavior.startswith("INSUFFICIENT_DATA") for gate in EXECUTION_GATES)


def test_immutable_strategy_versions_retain_registry_and_policy_references(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "registry-reference.db")
    service = StrategyGovernanceService(repository)
    original = replace(
        strategy_definition("0.1"), rule_definition_version=DIAGNOSTIC_REGISTRY_VERSION,
        scoring_configuration_version=SCORING_POLICY_VERSION,
        execution_gate_configuration_version=EXECUTION_GATE_REGISTRY_VERSION,
    )
    service.create(original)
    successor = replace(
        strategy_definition("0.2", original.reference), rule_definition_version="diagnostic-registry-v2",
        scoring_configuration_version="decision-score-policy-v2",
        execution_gate_configuration_version="execution-gate-registry-v2",
    )
    service.create_next_version(successor)

    restored_original = repository.get_strategy_definition(original.reference)
    restored_successor = repository.get_strategy_definition(successor.reference)
    assert restored_original is not None and restored_successor is not None
    assert restored_original.rule_definition_version == DIAGNOSTIC_REGISTRY_VERSION
    assert restored_original.scoring_configuration_version == SCORING_POLICY_VERSION
    assert restored_successor.rule_definition_version == "diagnostic-registry-v2"
    repository.close()
