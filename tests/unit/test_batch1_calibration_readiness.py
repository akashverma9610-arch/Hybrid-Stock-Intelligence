from datetime import UTC, datetime, timedelta
import pytest

from app.intelligence.batch1_calibration_readiness import CalibrationInsufficiencyCode, CalibrationReadinessState, MarketCalibrationCoverage, assess_batch1_calibration_readiness
from app.intelligence.external_intelligence import CompanyExposure, EvidenceVersion, EventType, ExposureType, ExternalEvent, Materiality, SourceEvidence


T = datetime(2026, 1, 1, tzinfo=UTC)


def evidence(*, verified=False):
    event = ExternalEvent("desk", "event-1", EventType.CAPEX, "title", "IN", "domain", Materiality.HIGH, T)
    exposure = (CompanyExposure("instrument-1" if verified else None, "Company", ExposureType.DIRECT, .9, "VERIFIED" if verified else "UNVERIFIED_INFERENCE"),)
    return EvidenceVersion(event, T, T, T, "summary", "changed", SourceEvidence("issuer", "PRIMARY", "ref", .9), company_exposures=exposure)


def market(**changes):
    value = MarketCalibrationCoverage({"NIFTY_50": (T,), "NIFTY_500": (T,)}, (), False, 0, False, 0, ())
    return MarketCalibrationCoverage(**{name: getattr(value, name) for name in value.__dataclass_fields__} | changes)


def test_assessment_is_read_only_and_reports_exact_event_and_market_blockers():
    result = assess_batch1_calibration_readiness((evidence(),), market(), primary_source_types=frozenset({"PRIMARY"}))
    assert result.event_catalyst.state is CalibrationReadinessState.INSUFFICIENT_FOR_CALIBRATION
    assert result.event_catalyst.verified_company_exposures == 0
    assert CalibrationInsufficiencyCode.VERIFIED_EXPOSURE_MISSING in result.event_catalyst.insufficiency_codes
    assert CalibrationInsufficiencyCode.HISTORICAL_BREADTH_MISSING in result.market_red.insufficiency_codes
    assert result.market_red.benchmark_session_coverage[0][0] == "NIFTY_50"


def test_verified_exposure_and_completed_sessions_make_forward_windows_observable_without_selecting_a_parameter():
    sessions = tuple(T + timedelta(days=index) for index in range(1, 11))
    coverage = MarketCalibrationCoverage({"NIFTY_50": sessions, "NIFTY_500": sessions}, sessions, True, 1, True, 1, sessions)
    result = assess_batch1_calibration_readiness((evidence(verified=True),), coverage, primary_source_types=frozenset({"PRIMARY"}), typed_lifecycle_event_ids=frozenset({evidence(verified=True).event.canonical_event_id}), stock_completed_sessions={"instrument-1": sessions})
    assert result.event_catalyst.forward_observable_by_window == ((1, 1), (2, 1), (3, 1), (5, 1), (10, 1))
    assert result.event_catalyst.state is CalibrationReadinessState.READY_FOR_RESEARCH
    assert result.market_red.state is CalibrationReadinessState.READY_FOR_RESEARCH


def test_future_sessions_and_untyped_lifecycle_fail_closed_deterministically():
    result = assess_batch1_calibration_readiness((evidence(verified=True),), market(), primary_source_types=frozenset({"PRIMARY"}), stock_completed_sessions={"instrument-1": (T - timedelta(days=1),)})
    assert result.event_catalyst.forward_observable_by_window == ((1, 0), (2, 0), (3, 0), (5, 0), (10, 0))
    assert CalibrationInsufficiencyCode.EVENT_LIFECYCLE_UNTYPED in result.event_catalyst.insufficiency_codes
    assert CalibrationInsufficiencyCode.FORWARD_COMPLETED_SESSIONS_MISSING in result.event_catalyst.insufficiency_codes


def test_duplicate_completed_sessions_are_rejected_not_silently_canonicalised():
    with pytest.raises(ValueError, match="CALIBRATION_SESSION_DUPLICATE"):
        MarketCalibrationCoverage({"NIFTY_50": (T, T)}, (), False, 0, False, 0, ())
