from datetime import timedelta

from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import DiagnosticResult, ObservationKind
from app.services.audit_reconstruction_service import AuditReconstructionService
from app.services.foundation_service import FoundationService
from app.services.strategy_governance_service import StrategyGovernanceService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.governance_records import GOVERNANCE_TIME, evidence, gate_decision, scorecard, strategy_definition
from tests.fixtures.mock_observations import EVALUATION_TIME, valid_observation


def test_evidence_diagnostic_scorecard_gate_and_deterministic_audit_reconstruction(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "audit.db")
    foundation = FoundationService(
        repository,
        ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=1)}, timedelta(days=7)))),
    )
    foundation.ingest(valid_observation(), evaluated_timestamp=EVALUATION_TIME)
    snapshot = foundation.build_as_of_snapshot(as_of_timestamp=EVALUATION_TIME)

    governance = StrategyGovernanceService(repository)
    strategy = governance.create(strategy_definition())
    item_evidence = evidence()
    repository.save_evidence(item_evidence)
    diagnostic = DiagnosticResult(
        id="diagnostic-1", instrument_id="mock-reliance", rule_id="rule-structure-only",
        strategy_version=strategy.reference, result="not_implemented", score=None, confidence=None,
        evidence_ids=(item_evidence.id,), input_observation_ids=("mock-reliance-0900",),
        evaluated_at=GOVERNANCE_TIME, as_of_timestamp=snapshot.as_of_timestamp,
    )
    repository.save_diagnostic_result(diagnostic)
    item_scorecard = scorecard(strategy.reference, snapshot.as_of_timestamp)
    item_gate = gate_decision(strategy.reference, snapshot.as_of_timestamp)
    repository.save_scorecard(item_scorecard)
    repository.save_gate_decision(item_gate)

    reconstruction_service = AuditReconstructionService(repository)
    first = reconstruction_service.reconstruct(
        strategy_version=strategy.reference, snapshot_id=snapshot.id, scorecard_id=item_scorecard.id
    )
    second = reconstruction_service.reconstruct(
        strategy_version=strategy.reference, snapshot_id=snapshot.id, scorecard_id=item_scorecard.id
    )

    assert repository.get_evidence((item_evidence.id,))[0] == item_evidence
    assert repository.list_diagnostic_results(strategy.reference, snapshot.as_of_timestamp) == (diagnostic,)
    assert repository.get_scorecard(item_scorecard.id) == item_scorecard
    assert repository.list_gate_decisions(strategy.reference, snapshot.as_of_timestamp) == (item_gate,)
    assert first.id == second.id
    assert first.fingerprint == second.fingerprint
    assert first.evidence[0].evidence_type.value == "data"
    assert first.diagnostics[0].strategy_version == strategy.reference
    assert first.gate_decisions[0].outcome.value == "insufficient_data"
    repository.close()


def test_historical_records_remain_linked_to_the_original_strategy_version(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "historical.db")
    governance = StrategyGovernanceService(repository)
    original = governance.create(strategy_definition("0.1"))
    diagnostic = DiagnosticResult(
        "diagnostic-original", "mock-reliance", "rule-structure-only", original.reference,
        "not_implemented", None, None, (), (), GOVERNANCE_TIME, GOVERNANCE_TIME,
    )
    repository.save_diagnostic_result(diagnostic)
    successor = governance.create_next_version(strategy_definition("0.2", original.reference))

    assert repository.list_diagnostic_results(original.reference, GOVERNANCE_TIME) == (diagnostic,)
    assert repository.list_diagnostic_results(successor.reference, GOVERNANCE_TIME) == ()
    repository.close()
