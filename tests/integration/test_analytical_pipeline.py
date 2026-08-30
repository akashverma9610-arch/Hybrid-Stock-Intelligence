from dataclasses import replace
from datetime import timedelta

from app.analysis.audit import AnalysisAuditService
from app.analysis.technical import TechnicalAnalysisEngine
from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind
from app.services.audit_reconstruction_service import AuditReconstructionService
from app.services.foundation_service import FoundationService
from app.services.strategy_governance_service import StrategyGovernanceService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars
from tests.fixtures.governance_records import strategy_definition


def test_analysis_evidence_and_audit_reconstruction_respect_as_of_boundary(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "analysis-audit.db")
    foundation = FoundationService(
        repository,
        ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.PRICE_BAR: timedelta(days=30)}, timedelta(days=30)))),
    )
    historical = bars("stock", [10, 11, 12, 13, 14], start=ANALYSIS_TIME - timedelta(days=5))
    future = replace(bars("stock", [100], start=ANALYSIS_TIME + timedelta(days=1))[0], id="stock-future")
    for item in (*historical, future):
        foundation.ingest(item, evaluated_timestamp=ANALYSIS_TIME + timedelta(days=2))
    as_of_snapshot = foundation.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME)
    replayed_snapshot = foundation.build_as_of_snapshot(as_of_timestamp=ANALYSIS_TIME)

    strategy = StrategyGovernanceService(repository).create(strategy_definition())
    result = TechnicalAnalysisEngine().sma(as_of_snapshot, instrument_id="stock", strategy_version=strategy.reference,
                                           period=3, evaluated_at=ANALYSIS_TIME)
    diagnostic = AnalysisAuditService(repository).persist(result)
    reconstruction = AuditReconstructionService(repository).reconstruct(strategy_version=strategy.reference, snapshot_id=as_of_snapshot.id)

    assert as_of_snapshot.id == replayed_snapshot.id
    assert "stock-future" not in result.input_observation_ids
    assert result.value == 13.0
    assert diagnostic.evidence_ids == result.evidence_ids
    assert reconstruction.diagnostics == (diagnostic,)
    assert {item.evidence_type.value for item in result.evidence} == {"data", "interpretation"}
    repository.close()
