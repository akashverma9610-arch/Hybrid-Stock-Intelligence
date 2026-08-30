from datetime import timedelta

import pytest

from app.domain.models import DiagnosticResult, StrategyValidationStatus
from app.services.strategy_governance_service import StrategyGovernanceError, StrategyGovernanceService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.governance_records import GOVERNANCE_TIME, strategy_definition


def test_strategy_creation_and_immutable_persistence(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "governance.db")
    service = StrategyGovernanceService(repository)
    definition = strategy_definition()
    service.create(definition)

    stored = repository.get_strategy_definition(definition.reference)
    assert stored == definition
    with pytest.raises(StrategyGovernanceError, match="immutable"):
        service.create(definition)
    with pytest.raises(ValueError, match="append-only"):
        repository.append_strategy_lifecycle_event(repository.latest_strategy_lifecycle_event(definition.reference))  # type: ignore[arg-type]
    repository.close()


def test_strategy_configuration_is_immutable_and_undecided_values_are_explicit() -> None:
    definition = strategy_definition()
    assert definition.configuration.rotation_threshold.value == "REQUIRES_APPROVAL"
    with pytest.raises(TypeError):
        definition.configuration.scoring_weights["new_weight"] = 0.1  # type: ignore[index]


def test_versioning_requires_existing_parent_and_preserves_parent(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "versioning.db")
    service = StrategyGovernanceService(repository)
    parent = service.create(strategy_definition("0.1"))
    successor = service.create_next_version(strategy_definition("0.2", parent.reference))

    assert repository.get_strategy_definition(parent.reference) == parent
    assert successor.parent_strategy_version == parent.reference
    repository.close()


def test_activation_requires_approval_and_passed_validation(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "approval.db")
    service = StrategyGovernanceService(repository)
    definition = service.create(strategy_definition())

    with pytest.raises(StrategyGovernanceError, match="cannot become active"):
        service.activate(definition.reference, effective_from=GOVERNANCE_TIME, actor_id="reviewer-1", rationale="no approval", event_id="activate-denied")

    service.record_validation(definition.reference, status=StrategyValidationStatus.PASSED,
                              occurred_at=GOVERNANCE_TIME + timedelta(minutes=1), actor_id="validator-1",
                              rationale="Fixture validation completed.", event_id="validation-passed")
    service.approve(definition.reference, occurred_at=GOVERNANCE_TIME + timedelta(minutes=2), actor_id="reviewer-1",
                    rationale="Fixture review approved.", event_id="approved")
    active = service.activate(definition.reference, effective_from=GOVERNANCE_TIME + timedelta(minutes=3),
                              actor_id="reviewer-1", rationale="Fixture activation.", event_id="active")
    assert active.status.value == "active"
    repository.close()


def test_analytical_records_require_a_strategy_version_and_as_of_timestamp(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "required-context.db")
    result = DiagnosticResult("diagnostic-without-version", "mock-reliance", "rule-1", None, "not_run", None, None, (), (), GOVERNANCE_TIME, GOVERNANCE_TIME)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="strategy version"):
        repository.save_diagnostic_result(result)
    strategy = StrategyGovernanceService(repository).create(strategy_definition())
    missing_as_of = DiagnosticResult("diagnostic-without-as-of", "mock-reliance", "rule-1", strategy.reference, "not_run", None, None, (), (), GOVERNANCE_TIME, None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="as-of timestamp"):
        repository.save_diagnostic_result(missing_as_of)
    repository.close()
