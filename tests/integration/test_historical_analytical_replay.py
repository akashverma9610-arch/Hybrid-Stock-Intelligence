from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import json
import pytest
from tests.fixtures.gate_provenance import fixture_gate_composition


@pytest.fixture(autouse=True)
def isolated_historical_gate_arithmetic():
    # These synthetic calendar/surveillance observations have no live source
    # authority. Test frozen replay mechanics through explicit test composition.
    with fixture_gate_composition():
        yield

from app.backtest.analytical import HistoricalAnalyticalReplayConfig, HistoricalAnalyticalReplayService
from app.backtest.engine import BacktestReplayEngine, backtest_run_fingerprint
from app.backtest.models import *
from app.domain.models import DataQuality, Instrument, MarketObservation, ObservationKind, Provenance, StrategyVersionReference, ValidationResult, ValidationStatus
from app.gates.engine import ActionContext, ExchangeCalendar, ExecutionGateConfig, GateOutcome
from app.historical.models import DatasetQuality, HistoricalDatasetManifest, InstrumentLifecycle, UniverseMembership
from app.services.audit_reconstruction_service import AuditReconstructionService
from app.backtest.serialization import dump as backtest_dump
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.governance_records import strategy_definition


T = datetime(2026, 1, 2, 16, tzinfo=UTC)
CALENDAR = ExchangeCalendar("nse-history-v1", frozenset())
STRATEGY = StrategyVersionReference("nse-manager", "0.1")
GATE_CONFIG = ExecutionGateConfig("gates-history-v1", Decimal("0.8"), "friction-v1", None, False, 10, Decimal("1"), Decimal(".5"), 2, True, Decimal(".05"), 2, Decimal(".5"), Decimal(".4"), True, Decimal(".06"), Decimal(".25"), Decimal(".35"), 5, "heat-v1")


def observation(identifier, instrument, value, at):
    return MarketObservation(identifier, Instrument(instrument, instrument.upper(), "MOCK"), ObservationKind.PRICE_BAR,
        {"open": value, "high": value + 1, "low": value - 1, "close": value, "volume": 1000},
        Provenance("fixture", identifier, at, at, DataQuality.HIGH), ValidationResult(ValidationStatus.VALID, at))


def metadata_observation(identifier, instrument, kind, payload, at):
    return MarketObservation(identifier, Instrument(instrument, instrument.upper(), "MOCK"), kind, payload,
        Provenance("fixture", identifier, at, at, DataQuality.HIGH), ValidationResult(ValidationStatus.VALID, at))


def setup(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "historical-replay.db")
    repo.save_strategy_definition(strategy_definition())
    manifest = HistoricalDatasetManifest("history-v1", "1", T, T - timedelta(days=10), T + timedelta(days=10), CALENDAR.calendar_id,
        "nifty-history", {"market": ["bars-v1"]}, {"source": "fixture"}, DatasetQuality.HIGH_QUALITY, (), "raw", __import__("app.historical.models", fromlist=["SurvivorshipStatus"]).SurvivorshipStatus.POINT_IN_TIME_UNIVERSE, "FULL", (), "fingerprint-v1")
    repo.save_historical_manifest(manifest)
    repo.save_universe_membership(UniverseMembership("candidate-member", "candidate", "nifty-history", T - timedelta(days=10), None, T - timedelta(days=10), "fixture", "fixture", InstrumentLifecycle.ACTIVE))
    repo.save_universe_membership(UniverseMembership("later-member", "later", "nifty-history", T + timedelta(days=1), None, T + timedelta(days=1), "fixture", "fixture", InstrumentLifecycle.ACTIVE))
    for instrument, values in (("candidate", (10,11,12,13,14,15)), ("benchmark", (10,10.5,11,11.5,12,12.5))):
        for index, value in enumerate(values):
            item = observation(f"{instrument}-{index}", instrument, value, T - timedelta(days=6-index))
            repo.save_instrument(item.instrument); repo.save_observation(item)
    future = observation("candidate-future", "candidate", 100, T + timedelta(days=1))
    repo.save_instrument(future.instrument); repo.save_observation(future)
    schedule_item = metadata_observation("earnings-original", "candidate", ObservationKind.CORPORATE_EVENT,
        {"earnings_scheduled_at": (T + timedelta(days=2)).isoformat(), "earnings_schedule_verified_at": (T - timedelta(days=1)).isoformat()}, T - timedelta(days=1))
    repo.save_instrument(schedule_item.instrument); repo.save_observation(schedule_item)
    schedule = ReplaySchedule("history-schedule", "1", ReplayFrequency.DAILY_CLOSE, "UTC", CALENDAR.calendar_id, "SESSION_CLOSE", ExecutionTimingPolicy.NEXT_ELIGIBLE_BAR, T.replace(hour=0), T.replace(hour=23, minute=59))
    gap = BacktestDataGapPolicy("history-gap", "1", BacktestDataGapBehavior.MARK_INSUFFICIENT_DATA)
    run = BacktestRun("history-run", manifest.dataset_id, manifest.dataset_version, manifest.fingerprint, None, "nse-manager:0.1", "diagnostic-registry-v1", "score-history-v1", GATE_CONFIG.version, "rotation-v1", "signal-v1", "paper-v1", "performance-v1", "backtest-v1", schedule.schedule_id, schedule.version, gap.policy_id, gap.version, CALENDAR.calendar_id, "1", schedule.start, schedule.end, Decimal("100000"), "cost-v1", "slippage-v1", "nifty-history", (), BacktestRunStatus.CREATED, DatasetQuality.HIGH_QUALITY, EvaluationLabel.IN_SAMPLE, (), (), "", T)
    run = replace(run, fingerprint=backtest_run_fingerprint(run))
    config = HistoricalAnalyticalReplayConfig(STRATEGY, "benchmark", GATE_CONFIG, CALENDAR, ActionContext.ROTATE_IN)
    return repo, manifest, schedule, gap, run, config


def test_historical_analytical_replay_is_as_of_frozen_and_persists_artifacts(tmp_path):
    repo, _manifest, schedule, gap, run, config = setup(tmp_path)
    result = BacktestReplayEngine(repo).run_analytical(run, schedule, CALENDAR, gap, HistoricalAnalyticalReplayService(repo, config))
    assert result.status is BacktestRunStatus.COMPLETED
    evaluations = repo.list_historical_analytical_evaluations(run.backtest_run_id, 1)
    assert [item.instrument_id for item in evaluations] == ["candidate"]
    evaluation = evaluations[0]; snapshot = repo.get_historical_analytical_snapshot(evaluation.historical_snapshot_id)
    assert snapshot is not None and "candidate-future" not in snapshot.selected_input_ids
    assert len(evaluation.diagnostic_result_ids) == 61
    assert repo.get_historical_analytical_evaluation(evaluation.evaluation_id) == evaluation
    gates = repo.get_execution_gate_evaluation(evaluation.execution_gate_evaluation_id)
    assert gates is not None and next(x for x in gates.decisions if x.gate_id == "GATE_1_ROTATION").outcome is GateOutcome.INSUFFICIENT_DATA
    assert next(x for x in gates.decisions if x.gate_id == "GATE_5_HEAT").outcome is GateOutcome.INSUFFICIENT_DATA
    assert any(event.event_type is BacktestEventType.DIAGNOSTICS_EVALUATED for event in result.events)
    rebuilt = AuditReconstructionService(repo).reconstruct_historical_analytical_evaluation(evaluation.evaluation_id)
    assert rebuilt[0] == evaluation and len(rebuilt[3]) == 61


def test_future_observation_does_not_change_earlier_snapshot_selection(tmp_path):
    repo, _manifest, schedule, gap, run, config = setup(tmp_path)
    BacktestReplayEngine(repo).run_analytical(run, schedule, CALENDAR, gap, HistoricalAnalyticalReplayService(repo, config))
    before = repo.list_historical_analytical_evaluations(run.backtest_run_id, 1)[0]
    snapshot = repo.get_historical_analytical_snapshot(before.historical_snapshot_id)
    assert "candidate-future" not in snapshot.latest_eligible_input_ids
    assert before.status is HistoricalAnalyticalStatus.INSUFFICIENT_DATA


def test_domain_attack_matrix_and_reschedule_do_not_rewrite_earlier_evaluation(tmp_path):
    repo, manifest, schedule, gap, run, config = setup(tmp_path)
    engine = BacktestReplayEngine(repo); service = HistoricalAnalyticalReplayService(repo, config)
    engine.run_analytical(run, schedule, CALENDAR, gap, service)
    prior = repo.list_historical_analytical_evaluations(run.backtest_run_id, 1)[0]
    prior_snapshot = repo.get_historical_analytical_snapshot(prior.historical_snapshot_id)
    prior_score = repo.get_decision_scorecard(prior.decision_scorecard_id)
    prior_gates = repo.get_execution_gate_evaluation(prior.execution_gate_evaluation_id)
    assert next(x for x in prior_gates.decisions if x.gate_id == "GATE_6_EARNINGS").outcome is GateOutcome.FAIL
    future = T + timedelta(days=3)
    attacks = (
        ("future-index", "benchmark", ObservationKind.INDEX, {"close": 999}),
        ("future-sector", "sector", ObservationKind.SECTOR, {"close": 999}),
        ("future-financial", "candidate", ObservationKind.FUNDAMENTAL, {"publication_timestamp": future.isoformat(), "pat": 999}),
        ("future-restatement", "candidate", ObservationKind.FUNDAMENTAL, {"publication_timestamp": future.isoformat(), "pat": 1000, "supersedes": "original"}),
        ("future-research", "candidate", ObservationKind.RESEARCH, {"claim": "strong moat and catalyst"}),
        ("future-crowd", "candidate", ObservationKind.RESEARCH, {"crowd_sentiment": "extreme bullish"}),
        ("future-surveillance", "candidate", ObservationKind.CORPORATE_EVENT, {"asm_stage": 4, "gsm_stage": 1, "circuit_limit": ".02", "authoritative": True}),
        ("earnings-rescheduled", "candidate", ObservationKind.CORPORATE_EVENT, {"earnings_scheduled_at": (T + timedelta(days=12)).isoformat(), "earnings_schedule_verified_at": future.isoformat()}),
    )
    for identifier, instrument, kind, payload in attacks:
        item = metadata_observation(identifier, instrument, kind, payload, future)
        repo.save_instrument(item.instrument); repo.save_observation(item)
    repo.save_universe_membership(UniverseMembership("future-universe-member", "future-stock", "nifty-history", future, None, future, "fixture", "fixture", InstrumentLifecycle.ACTIVE))
    v2 = HistoricalDatasetManifest("history-v2", "2", future, manifest.coverage_start, manifest.coverage_end, manifest.calendar_reference, manifest.universe_reference, {"market": ["bars-v2"]}, manifest.source_metadata, manifest.quality, manifest.known_gaps, manifest.adjustment_methodology, manifest.survivorship, manifest.point_in_time_capability, (), "fingerprint-v2")
    repo.save_historical_manifest(v2)
    run_b = replace(run, backtest_run_id="history-run-v2", dataset_manifest_id=v2.dataset_id, dataset_manifest_version=v2.dataset_version, dataset_fingerprint=v2.fingerprint, fingerprint="")
    run_b = replace(run_b, fingerprint=backtest_run_fingerprint(run_b))
    engine.run_analytical(run_b, schedule, CALENDAR, gap, service)
    later_same_t = repo.list_historical_analytical_evaluations(run_b.backtest_run_id, 1)[0]
    later_snapshot = repo.get_historical_analytical_snapshot(later_same_t.historical_snapshot_id)
    later_score = repo.get_decision_scorecard(later_same_t.decision_scorecard_id)
    later_gates = repo.get_execution_gate_evaluation(later_same_t.execution_gate_evaluation_id)
    assert prior_snapshot.selected_input_ids == later_snapshot.selected_input_ids
    assert prior_score.final_score == later_score.final_score and prior_score.data_confidence == later_score.data_confidence and prior_score.score_status == later_score.score_status
    assert [(x.gate_id, x.outcome, x.detail) for x in prior_gates.decisions] == [(x.gate_id, x.outcome, x.detail) for x in later_gates.decisions]
    assert repo.get_historical_analytical_evaluation(prior.evaluation_id) == prior
    later_schedule = replace(schedule, schedule_id="history-schedule-after-reschedule", start=future.replace(hour=0), end=future.replace(hour=23, minute=59))
    run_c = replace(run_b, backtest_run_id="history-run-after-reschedule", replay_schedule_id=later_schedule.schedule_id,
                    evaluation_start=later_schedule.start, evaluation_end=later_schedule.end, fingerprint="")
    run_c = replace(run_c, fingerprint=backtest_run_fingerprint(run_c))
    engine.run_analytical(run_c, later_schedule, CALENDAR, gap, service)
    after = repo.list_historical_analytical_evaluations(run_c.backtest_run_id, 1)[0]
    after_gates = repo.get_execution_gate_evaluation(after.execution_gate_evaluation_id)
    assert next(x for x in after_gates.decisions if x.gate_id == "GATE_6_EARNINGS").outcome is GateOutcome.PASS


def test_audit_rejects_tampered_frozen_snapshot_reference(tmp_path):
    repo, _manifest, schedule, gap, run, config = setup(tmp_path)
    BacktestReplayEngine(repo).run_analytical(run, schedule, CALENDAR, gap, HistoricalAnalyticalReplayService(repo, config))
    evaluation = repo.list_historical_analytical_evaluations(run.backtest_run_id, 1)[0]
    snapshot = repo.get_historical_analytical_snapshot(evaluation.historical_snapshot_id)
    tampered = replace(snapshot, selected_input_ids=("tampered-future-id",))
    repo._connection.execute("UPDATE historical_analytical_snapshots SET payload_json=? WHERE id=?", (json.dumps(backtest_dump(tampered), sort_keys=True), snapshot.historical_snapshot_id))
    repo._connection.commit()
    from app.services.audit_reconstruction_service import AuditReconstructionError
    with pytest.raises(AuditReconstructionError, match="inputs no longer match"):
        AuditReconstructionService(repo).reconstruct_historical_analytical_evaluation(evaluation.evaluation_id)
