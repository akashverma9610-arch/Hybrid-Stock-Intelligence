from datetime import timedelta
from decimal import Decimal

import pytest

from app.backtest.oos_aggregation import (
    AggregateValidationStatus, OOSCapitalStitchingMethodology, WalkForwardAggregationService,
    WalkForwardValidationConfig,
)
from app.backtest.walk_forward import (
    OOSStartingCapitalMethodology, WalkForwardWindowResult, WalkForwardWindowResultStatus,
)
from app.historical.guard import manifest_fingerprint
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from tests.integration.test_walk_forward_execution import T, frozen_objects, oos_run


def config():
    return WalkForwardValidationConfig("oos-config", "1", 2, 2, Decimal(".5"), 2, 1, None, Decimal(".30"), Decimal(".15"), Decimal(".10"), "oos-v1", manifest_fingerprint(config="oos-v1"))


def result(run, window, candidate, test_run, value, status=WalkForwardWindowResultStatus.COMPLETED):
    return WalkForwardWindowResult(
        f"oos-result-{window.ordinal}", run.run_id, window.window_id, candidate.candidate_id, candidate.fingerprint,
        (), window.train.end, run.selection_policy, run.selection_policy_version,
        OOSStartingCapitalMethodology.INDEPENDENT_WINDOW_CAPITAL, test_run.backtest_run_id, None, None,
        window.test.start, window.test.end, Decimal("1000"), None, value, Decimal("-.1"), None, None, None, None, None, 0, Decimal("0"), status, (),
        manifest_fingerprint(window=window.fingerprint, value=value, status=status.value),
    )


def stored_fixture(tmp_path):
    repo, data, candidate, _plan, windows, run = frozen_objects(tmp_path)
    run=__import__('dataclasses').replace(run,run_id="wf-run-small",ordered_window_ids=tuple(window.window_id for window in windows[:2]),fingerprint=manifest_fingerprint(run="small")); repo.save_walk_forward_run(run)
    for ordinal, value in enumerate((Decimal(".20"), Decimal("-.20")), 1):
        test_run=oos_run(f"aggregate-test-{ordinal}",data,candidate,windows[ordinal-1]); repo.save_backtest_run(test_run)
        repo.save_walk_forward_window_result(result(run,windows[ordinal-1],candidate,test_run,value))
    return repo, data, candidate, windows, run


def test_oos_aggregation_compounds_test_returns_retains_coverage_and_round_trips(tmp_path):
    repo, _data, _candidate, _windows, run=stored_fixture(tmp_path)
    aggregate=WalkForwardAggregationService(repo).aggregate(run_id=run.run_id,config=config(),generated_at=T+timedelta(days=30))
    assert aggregate.compounded_oos_return==Decimal("-.0400")
    assert aggregate.ending_aggregate_equity==Decimal(".9600")
    assert aggregate.valid_window_count==2 and aggregate.total_planned_window_count>=2
    assert aggregate.coverage_ratio==Decimal(2)/aggregate.total_planned_window_count
    assert aggregate.capital_stitching_methodology is OOSCapitalStitchingMethodology.CHAIN_WINDOW_RETURNS
    assert repo.get_walk_forward_aggregate_result(aggregate.aggregate_result_id)==aggregate
    assert repo.get_walk_forward_validation_config(config().config_id)==config()
    with pytest.raises(ValueError,match="immutable"): repo.save_walk_forward_aggregate_result(aggregate)


def test_oos_aggregate_audit_detects_metric_and_equity_tampering(tmp_path):
    repo, _data, _candidate, _windows, run=stored_fixture(tmp_path)
    aggregate=WalkForwardAggregationService(repo).aggregate(run_id=run.run_id,config=config(),generated_at=T+timedelta(days=30))
    assert AuditReconstructionService(repo).reconstruct_walk_forward_aggregate_result(aggregate.aggregate_result_id)==aggregate
    repo._connection.execute("UPDATE walk_forward_aggregate_results SET payload_json=replace(payload_json, '\"compounded_oos_return\":\"-0.0400\"', '\"compounded_oos_return\":\"0\"') WHERE id=?",(aggregate.aggregate_result_id,)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError,match="mismatch"):
        AuditReconstructionService(repo).reconstruct_walk_forward_aggregate_result(aggregate.aggregate_result_id)


def test_failed_and_insufficient_windows_stay_visible_and_samples_are_neutral(tmp_path):
    repo, data, candidate, windows, run=stored_fixture(tmp_path)
    # A second immutable run retains every planned window; it does not alter the two-window run.
    expanded=__import__('dataclasses').replace(run,run_id="wf-run-expanded",ordered_window_ids=tuple(window.window_id for window in windows),fingerprint=manifest_fingerprint(run="expanded")); repo.save_walk_forward_run(expanded)
    for ordinal, item in enumerate(repo.list_walk_forward_window_results(run.run_id),1):
        repo.save_walk_forward_window_result(__import__('dataclasses').replace(item,result_id=f"expanded-{ordinal}",walk_forward_run_id=expanded.run_id))
    for ordinal,status in ((3,WalkForwardWindowResultStatus.INSUFFICIENT),):
        test_run=oos_run(f"aggregate-extra-{ordinal}",data,candidate,windows[ordinal-1]); repo.save_backtest_run(test_run)
        repo.save_walk_forward_window_result(result(expanded,windows[ordinal-1],candidate,test_run,None,status))
    aggregate=WalkForwardAggregationService(repo).aggregate(run_id=expanded.run_id,config=__import__('dataclasses').replace(config(),config_id="oos-config-expanded",minimum_valid_oos_windows=3),generated_at=T+timedelta(days=30))
    assert (aggregate.valid_window_count,aggregate.insufficient_window_count,aggregate.failed_window_count)==(2,1,0)
    assert aggregate.coverage_ratio==Decimal(2)/Decimal(3) and aggregate.status is AggregateValidationStatus.INSUFFICIENT_EVIDENCE
