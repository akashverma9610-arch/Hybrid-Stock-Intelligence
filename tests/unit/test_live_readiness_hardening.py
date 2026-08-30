from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.ai_containment import StructuredAIOutputValidator
from app.calibration import CalibrationService, DiagnosticRedundancyService, RegimeValidationService
from app.data_quality.reconciliation import ReconciliationService, ReconciliationStatus
from app.data_sources.models import SourceRecordProvenance
from app.evidence_coverage import EvidenceCoverageService, EvidenceCoverageState, EvidenceDomain
from app.execution_simulation import ExecutionFeasibilityService, ExecutionSimulationConfig, ExecutionSimulationService
from app.live_readiness import EmergencyDefensiveMode, EmergencyDefensivePolicy, FactorExposureService, FailurePropagationService, LiveReadinessSnapshotStore, RotationHurdleService
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, FreshnessAssessment, FreshnessState,
    InstrumentIdentity, InstrumentType, MarketDataProvenance, MarketSessionState, Timeframe,
)
from app.news.hardening import NewsEventClusteringService
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.rotation.models import RotationDecisionState
from app.scanning import CheapScanCandidate, TwoStageScanner
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 25, 10, tzinfo=UTC)


def _identity(): return InstrumentIdentity("stock-1", Exchange.NSE, "ABC", "ABC", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "ABC")
def _prov(source): return MarketDataProvenance(source, "token", T, T, T, "normalizer-v1")
def _bar(source, adjustment, close=Decimal("11"), volume=100):
    return CanonicalOHLCVBar("bar-" + source, _identity(), Timeframe.DAILY, T - timedelta(days=1), T, Decimal("10"), Decimal("12"), Decimal("9"), close, volume, None, None, adjustment, _prov(source))


def test_reconciliation_detects_adjustment_conflict_without_averaging_and_persists(tmp_path):
    result = ReconciliationService().reconcile_bars(_bar("a", AdjustmentStatus.RAW), _bar("b", AdjustmentStatus.ADJUSTED), as_of=T, retrieved_at=T)
    assert result.status is ReconciliationStatus.MATERIAL_CONFLICT
    assert "ADJUSTMENT_POLICY_MISMATCH" in result.conflicts and result.reliability_downgraded
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'quality.db'}"))
    store = LiveReadinessSnapshotStore(repository)
    store.save(record_id="reconcile-1", family=CoreApiSnapshotFamily.RECONCILIATION_RESULT, value=result, created_at=T)
    assert store.get(record_id="reconcile-1", family=CoreApiSnapshotFamily.RECONCILIATION_RESULT) == result
    with pytest.raises(ValueError, match="immutable"): store.save(record_id="reconcile-1", family=CoreApiSnapshotFamily.RECONCILIATION_RESULT, value=result, created_at=T)


def test_coverage_is_separate_from_confidence_and_insufficient_is_research_incomplete():
    service = EvidenceCoverageService()
    coverage = service.assess(subject_id="stock-1", required_domains=(EvidenceDomain.PRICE_HISTORY, EvidenceDomain.FINANCIALS), available_domains=())
    assert coverage.state is EvidenceCoverageState.INSUFFICIENT
    assert service.public_actionability(coverage=coverage, confidence=0.99, proposed_action="BUY") == "RESEARCH_INCOMPLETE"


def test_provider_conflict_propagates_to_data_unreliable_without_changing_a_score():
    reconciliation = ReconciliationService().reconcile_bars(_bar("a", AdjustmentStatus.RAW), _bar("b", AdjustmentStatus.ADJUSTED), as_of=T, retrieved_at=T)
    coverage = EvidenceCoverageService().assess(subject_id="stock-1", required_domains=(EvidenceDomain.PRICE_HISTORY,), available_domains=(EvidenceDomain.PRICE_HISTORY,))
    result = FailurePropagationService().decide(reconciliation=reconciliation, coverage=coverage, confidence=0.99, proposed_action="BUY")
    assert result.reliability.value == "DEGRADED" and result.public_action == "DATA_UNRELIABLE"


def test_friction_partial_fill_and_execution_feasibility_are_measurement_only():
    config = ExecutionSimulationConfig("friction-v1", Decimal(".001"), Decimal(".001"), Decimal(".001"), Decimal(".001"), Decimal(".001"), Decimal(".002"), Decimal(".002"))
    result = ExecutionSimulationService().simulate(entry_price=Decimal("100"), exit_price=Decimal("101"), requested_quantity=Decimal("10"), fill_fraction=Decimal(".5"), config=config)
    assert result.status == "PARTIAL_FILL" and result.net_pnl < result.gross_pnl
    rejected = ExecutionFeasibilityService().assess(expected_spread=Decimal(".1"), expected_slippage=Decimal(".2"), position_value=Decimal("100"), average_daily_value=Decimal("1000"), circuit_risk=True, fill_fraction=Decimal("1"))
    assert rejected.status.value == "SETUP_VALID_EXECUTION_REJECTED"


def test_calibration_redundancy_ablation_and_regime_validation_are_research_only():
    calibration = CalibrationService().calibrate((), regime="RISK_ON")
    assert all(item.status == "INSUFFICIENT" for item in calibration)
    redundancy = DiagnosticRedundancyService().correlate(left_factor="trend", left=(Decimal("1"), Decimal("2")), right_factor="momentum", right=(Decimal("1"), Decimal("2")))
    assert redundancy.status == "POSSIBLE_FACTOR_REDUNDANCY"
    ablation = CalibrationService().ablate(factor="trend", full_metric=Decimal("1.2"), ablated_metric=Decimal(".8"))
    assert ablation.delta == Decimal(".4")
    regime = RegimeValidationService().validate(predicted_regime="RISK_ON", outcomes=((Decimal(".1"), Decimal("-.02"), Decimal(".3")),))
    assert regime.status == "OBSERVED"


def test_rotation_hurdle_factor_exposure_and_emergency_mode_do_not_change_rotation_engine():
    trivial = RotationHurdleService().assess(candidate_advantage=Decimal(".2"), switching_friction=Decimal(".1"), uncertainty_buffer=Decimal(".1"), existing_minimum_superiority=Decimal(".1"))
    assert trivial.status.value == "REJECTED"
    missing = RotationHurdleService().assess(candidate_advantage=Decimal("1"), switching_friction=None, uncertainty_buffer=None, existing_minimum_superiority=None)
    assert missing.status.value == "NOT_CONFIGURED"
    exposures = FactorExposureService().aggregate(portfolio_id="p", holding_exposures=(("a", "MOMENTUM", Decimal(".4")), ("b", "MOMENTUM", Decimal(".3"))))
    assert exposures[0].exposure == Decimal(".7") and "HIDDEN_CORRELATED_BET" in exposures[0].warnings
    policy = EmergencyDefensivePolicy("mode-1", EmergencyDefensiveMode.FREEZE_NEW_ENTRIES, "provider conflict", T)
    assert policy.mode is EmergencyDefensiveMode.FREEZE_NEW_ENTRIES
    assert RotationDecisionState.CASH_PREFERRED.value == "CASH_PREFERRED"


def test_news_clustering_preserves_original_event_time_and_llm_malformed_output_fails_closed():
    provenance = SourceRecordProvenance("gnews", "gnews", "url", T, T, T, None, None, __import__("app.data_sources.models", fromlist=["DataFamily"]).DataFamily.NEWS_RESEARCH, "v1", "v1")
    article = lambda identifier, published, received: NewsArticleEvidence(identifier, "gnews", "publisher", None, "https://example.com/" + identifier, "Result", None, published, received, "en", "in", ("stock-1",), (), (), NewsSourceQuality.REPUTABLE_NEWS, provenance, NewsEventCategory.EARNINGS_RESULTS, "filing-1")
    clusters = NewsEventClusteringService().cluster((article("a", T - timedelta(days=2), T - timedelta(days=2)), article("b", T - timedelta(days=2), T)))
    assert len(clusters) == 1 and clusters[0].original_event_at == T - timedelta(days=2) and len(clusters[0].article_ids) == 2
    with pytest.raises(ValueError, match="REJECTED"): StructuredAIOutputValidator().parse("not-json", required_keys=("summary",))
    assert StructuredAIOutputValidator().parse('{"summary":"bounded"}', required_keys=("summary",))["summary"] == "bounded"


def test_two_stage_scan_shortlists_only_and_has_no_final_action():
    result = TwoStageScanner().shortlist((
        CheapScanCandidate("eligible", True, True, True, True, True, True, Decimal("5")),
        CheapScanCandidate("incomplete", True, False, True, True, True, True, Decimal("9")),
    ), limit=5)
    assert result.shortlisted_instrument_ids == ("eligible",)
    assert "SHORTLIST_ONLY_NO_FINAL_CAPITAL_DECISION" in result.warnings
