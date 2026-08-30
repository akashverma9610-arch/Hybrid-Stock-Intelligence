from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.backtest.models import HistoricalPaperReplayReference, HistoricalSignalReplayReference, SignalConfigSnapshot, PaperTradingConfigSnapshot
from app.historical.guard import manifest_fingerprint
from app.paper.engine import PaperTradingEngine
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_paper_trading import CFG, E, T, plan
from tests.unit.test_signal_lifecycle import create, CONFIG as SIGNAL_CONFIG
from tests.integration.test_historical_analytical_replay import setup


def test_historical_signal_and_paper_replay_references_are_immutable_round_trips(tmp_path):
    repo, _manifest, _schedule, _gap, run, _config=setup(tmp_path); repo.save_backtest_run(run)
    signal_snapshot=SignalConfigSnapshot("signal-config-v1", SIGNAL_CONFIG, T, ("fixture",), manifest_fingerprint(config=SIGNAL_CONFIG))
    paper_snapshot=PaperTradingConfigSnapshot("paper-config-v1", CFG, T, ("fixture",), manifest_fingerprint(config=CFG))
    repo.save_signal_config_snapshot(signal_snapshot); repo.save_paper_config_snapshot(paper_snapshot)
    assert repo.get_signal_config_snapshot(signal_snapshot.snapshot_id) == signal_snapshot
    assert repo.get_paper_config_snapshot(paper_snapshot.snapshot_id) == paper_snapshot
    with pytest.raises(ValueError, match="immutable"): repo.save_signal_config_snapshot(signal_snapshot)
    with pytest.raises(ValueError, match="immutable"): repo.save_paper_config_snapshot(paper_snapshot)
    signal_v2=SignalConfigSnapshot("signal-config-v2", replace(SIGNAL_CONFIG, minimum_score=SIGNAL_CONFIG.minimum_score+1), T, ("fixture-v2",), manifest_fingerprint(config=replace(SIGNAL_CONFIG, minimum_score=SIGNAL_CONFIG.minimum_score+1)))
    paper_v2=PaperTradingConfigSnapshot("paper-config-v2", replace(CFG, entry_slippage=CFG.entry_slippage+1), T, ("fixture-v2",), manifest_fingerprint(config=replace(CFG, entry_slippage=CFG.entry_slippage+1)))
    repo.save_signal_config_snapshot(signal_v2); repo.save_paper_config_snapshot(paper_v2)
    assert repo.get_signal_config_snapshot(signal_snapshot.snapshot_id) == signal_snapshot
    assert repo.get_paper_config_snapshot(paper_snapshot.snapshot_id) == paper_snapshot
    assert signal_snapshot.fingerprint != signal_v2.fingerprint and paper_snapshot.fingerprint != paper_v2.fingerprint
    assert manifest_fingerprint(config=SIGNAL_CONFIG) == signal_snapshot.fingerprint
    assert manifest_fingerprint(config=CFG) == paper_snapshot.fingerprint
    signal, created=create(); repo.save_signal(signal); repo.append_signal_event(created); repo.save_trade_plan(plan())
    signal_ref=HistoricalSignalReplayReference("signal-ref", run.backtest_run_id, 3, T, "analytical-v1", "gate-v1", "rotation-v1", "state-v1", signal.signal_id,
        "signal-v1", plan().plan_id, "plan-v1", signal.status.value, None, ("frozen",), "signal-fingerprint", signal_snapshot.snapshot_id, signal_snapshot.fingerprint)
    repo.save_historical_signal_replay_reference(signal_ref)
    assert repo.get_historical_signal_replay_reference(signal_ref.reference_id) == signal_ref
    with pytest.raises(ValueError, match="immutable"): repo.save_historical_signal_replay_reference(signal_ref)
    assert repo.get_historical_signal_replay_reference(signal_ref.reference_id) == signal_ref

    trade=E.create(signal,plan(),instrument_id="stock",generated_at=T); repo.save_paper_trade(trade)
    paper_ref=HistoricalPaperReplayReference("paper-ref", run.backtest_run_id, signal.signal_id, trade.paper_trade_id, None, (3,4), ("bar-1","bar-2"),
        CFG.version, CFG.cost_model_version, CFG.fill_method.value, CFG.same_bar_policy.value, CFG.gap_policy.value, "WAITING_FOR_TRIGGER", ("frozen",), "paper-fingerprint", paper_snapshot.snapshot_id, paper_snapshot.fingerprint)
    repo.save_historical_paper_replay_reference(paper_ref)
    assert repo.get_historical_paper_replay_reference(paper_ref.reference_id) == paper_ref
    with pytest.raises(ValueError, match="immutable"): repo.save_historical_paper_replay_reference(paper_ref)
    assert repo.get_historical_paper_replay_reference(paper_ref.reference_id) == paper_ref
