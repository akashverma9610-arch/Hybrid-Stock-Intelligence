from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtest.engine import BacktestReplayEngine, backtest_run_fingerprint
from app.backtest.models import BacktestRun, BacktestRunStatus, EvaluationLabel
from app.backtest.walk_forward import (
    StrategyCandidate, WalkForwardExecutionService, WalkForwardMode, WalkForwardPlan,
    WalkForwardRun, WalkForwardRunStatus, WalkForwardWindowGenerator,
    WalkForwardWindowResultStatus,
)
from app.historical.guard import manifest_fingerprint
from app.historical.models import DatasetQuality
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.unit.test_backtest_replay_foundation import CALENDAR, manifest, policy, repository, schedule


T = datetime(2026, 1, 2, tzinfo=UTC)


def frozen_objects(tmp_path):
    data = manifest("wf-dataset", "1", "wf-dataset-fingerprint")
    data = replace(data, coverage_end=T + timedelta(days=40))
    repo, data = repository(tmp_path, data)
    candidate = StrategyCandidate("fixed-v21", "strategy-v2.1", "registry-v1", "scoring-v1", "gates-v1", "rotation-v1", "signal-v1", "paper-v1", "allocation-v1", "performance-v1", manifest_fingerprint(candidate="fixed-v21"))
    plan = WalkForwardPlan("wf-plan", data.dataset_id, data.dataset_version, "nse", "wf-v1", WalkForwardMode.ROLLING, 5, 2, 3, 9, 1, 1, 10, CALENDAR.calendar_id, T, (), manifest_fingerprint(plan="wf-plan"))
    windows = WalkForwardWindowGenerator().generate(plan=plan, sessions=tuple(T + timedelta(days=i) for i in range(35)), candidate=candidate)
    assert len(windows) >= 2
    repo.save_walk_forward_plan(plan); repo.save_strategy_candidate(candidate)
    for window in windows:
        repo.save_walk_forward_window(window)
    run = WalkForwardRun("wf-run", plan.plan_id, tuple(window.window_id for window in windows), (candidate.candidate_id,), "FIXED_STRATEGY", "fixed-v1", "oos-v1", WalkForwardRunStatus.PLANNED, T, None, (), manifest_fingerprint(run="wf-run", windows=[w.fingerprint for w in windows]))
    repo.save_walk_forward_run(run)
    return repo, data, candidate, plan, windows, run


def oos_run(identifier, data, candidate, window):
    value = BacktestRun(
        identifier, data.dataset_id, data.dataset_version, data.fingerprint, window.test.partition_id,
        candidate.strategy_version, candidate.registry_version, candidate.scoring_version, candidate.gate_version,
        candidate.rotation_version, candidate.signal_config_snapshot_id, candidate.paper_config_snapshot_id,
        candidate.performance_config_version, "backtest-v1", schedule().schedule_id, schedule().version,
        policy().policy_id, policy().version, CALENDAR.calendar_id, "calendar-v1", window.test.start, window.test.end,
        Decimal("1000"), "cost-v1", "slippage-v1", "nifty-500-v1", (), BacktestRunStatus.CREATED,
        DatasetQuality.HIGH_QUALITY, EvaluationLabel.OUT_OF_SAMPLE_TEST, (), ("INDEPENDENT_WINDOW_CAPITAL", "CLEAN_OOS_NO_TRAIN_STATE"), "", T,
    )
    return replace(value, fingerprint=backtest_run_fingerprint(value))


def test_walk_forward_records_round_trip_are_immutable_and_preserve_order(tmp_path):
    repo, _data, candidate, plan, windows, run = frozen_objects(tmp_path)
    assert repo.get_walk_forward_plan(plan.plan_id) == plan
    assert repo.get_strategy_candidate(candidate.candidate_id) == candidate
    assert repo.list_walk_forward_windows(plan.plan_id) == windows
    assert repo.get_walk_forward_run(run.run_id) == run
    for save, value in ((repo.save_walk_forward_plan, plan), (repo.save_strategy_candidate, candidate), (repo.save_walk_forward_window, windows[0]), (repo.save_walk_forward_run, run)):
        with pytest.raises(ValueError, match="immutable"):
            save(value)
    second = replace(plan, plan_id="wf-plan-v2", fingerprint=manifest_fingerprint(plan="wf-plan-v2"))
    repo.save_walk_forward_plan(second)
    assert repo.get_walk_forward_plan(plan.plan_id) == plan and repo.get_walk_forward_plan(second.plan_id) == second


def test_clean_oos_execution_uses_only_test_run_and_retains_benchmark_warning(tmp_path):
    repo, data, candidate, _plan, windows, run = frozen_objects(tmp_path)
    window = windows[0]; test_run = oos_run("wf-test-a", data, candidate, window)
    service = WalkForwardExecutionService(repo)
    result = service.execute_window(
        run=run, window=window, candidate=candidate, selected_at=window.train.end,
        test_run=test_run,
        phase8_executor=lambda value, partition: BacktestReplayEngine(repo).run(value, schedule(), CALENDAR, policy(), partition),
    )
    assert result.status is WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS
    assert result.test_backtest_run_id == test_run.backtest_run_id
    assert result.starting_equity == Decimal("1000") and "BENCHMARK_UNAVAILABLE" in result.warnings
    persisted = repo.get_walk_forward_window_result(result.result_id)
    assert persisted == result
    with pytest.raises(ValueError, match="immutable"):
        repo.save_walk_forward_window_result(result)
    stored = repo.get_backtest_run(test_run.backtest_run_id)
    assert (stored.evaluation_start, stored.evaluation_end, stored.partition_id) == (window.test.start, window.test.end, window.test.partition_id)
    assert AuditReconstructionService(repo).reconstruct_walk_forward_window_result(result.result_id) == result
    coverage = service.coverage(run.run_id)
    assert coverage.planned_windows == len(windows) and coverage.completed_valid_windows == 1


def test_selection_and_test_boundary_fail_closed_without_train_state_inheritance(tmp_path):
    repo, data, candidate, _plan, windows, run = frozen_objects(tmp_path)
    window = windows[0]; service = WalkForwardExecutionService(repo)
    with pytest.raises(ValueError, match="TEST artifacts"):
        service.freeze_selection(run=run, window=window, candidate=candidate, selected_at=window.train.end, evidence_ids=("TEST:future-report",))
    prior = oos_run("wf-test-prior", data, candidate, window)
    with pytest.raises(ValueError, match="exactly"):
        service.execute_window(run=run, window=window, candidate=candidate, selected_at=window.train.end, test_run=replace(prior, evaluation_start=window.train.start), phase8_executor=lambda *_: None)
    assert repo.list_backtest_portfolio_ledger_events("wf-test-prior") == ()


def test_failed_window_is_retained_and_audit_detects_tampered_metrics(tmp_path):
    repo, data, candidate, _plan, windows, run = frozen_objects(tmp_path)
    window = windows[0]; test_run = oos_run("wf-test-failed", data, candidate, window)
    result = WalkForwardExecutionService(repo).execute_window(
        run=run, window=window, candidate=candidate, selected_at=window.train.end, test_run=test_run,
        phase8_executor=lambda value, partition: BacktestReplayEngine(repo).run(value, schedule(), CALENDAR, policy(), partition, handler=lambda _context: (_ for _ in ()).throw(RuntimeError("fixture failure"))),
    )
    assert result.status is WalkForwardWindowResultStatus.FAILED
    assert repo.get_walk_forward_window_result(result.result_id) == result
    # Create a completed clean TEST result, then alter only its stored analytical value.
    valid = oos_run("wf-test-tamper", data, candidate, windows[1])
    good = WalkForwardExecutionService(repo).execute_window(run=run, window=windows[1], candidate=candidate, selected_at=windows[1].train.end, test_run=valid, phase8_executor=lambda value, partition: BacktestReplayEngine(repo).run(value, schedule(), CALENDAR, policy(), partition))
    repo._connection.execute("UPDATE walk_forward_window_results SET payload_json=replace(payload_json, '\"trade_count\":0', '\"trade_count\":7') WHERE id=?", (good.result_id,)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError, match="metrics"):
        AuditReconstructionService(repo).reconstruct_walk_forward_window_result(good.result_id)
