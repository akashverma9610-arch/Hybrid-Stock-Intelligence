"""Proof of existing P1 scope, not a new lifecycle policy or state engine.

Only temporary Watch/governance stores are used. Reconstructing a projection
is deliberately not asserted to reconstruct a signal transition history.
"""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from datetime import timedelta
from pathlib import Path

import pytest

from app.intelligence.hsi_signal import (
    HSISignal, HSISignalActionability, HSISignalExecutionStatus,
    P1UnavailableReason, StrategyResolutionStatus, serialize_hsi_signal,
)
from app.intelligence.hsi_signal_projection import (
    HSISignalProjectionError, project_watch_to_hsi_signal,
)
from app.intelligence.hsi_signal_strategy_registry import HSISignalStrategyRegistry
from app.intelligence.market_wide_watch import (
    MarketWideWatchRecord, MarketWideWatchRun, MarketWideWatchStore,
    WatchClassification, WatchStatus,
)
from app.intelligence.opportunity_archetypes import OpportunityArchetype
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.unit.test_hsi_signal_projection import T, _watch
from tests.unit.test_hsi_signal_strategy_registry import _approved_selected


def _revision(watch, **changes):
    values = {f.name: getattr(watch, f.name) for f in fields(watch) if f.name != "fingerprint"}
    return MarketWideWatchRecord.create(**(values | changes))


def _run(watch):
    return MarketWideWatchRun.create(
        watch_as_of=watch.watch_as_of, universe_id="SYNTHETIC_TEST_ONLY",
        universe_count=1, eligible_count=1, excluded_count=0, exclusion_counts=(),
        evidence_ready_count=1, watch_candidate_count=1, classification_counts=(),
        top3_eligible_count=0, setup_candidate_count=1, valid_setup_count=1,
        decision_score_ready_count=0, six_gates_evaluated_count=0,
        six_gates_pass_count=0, filter_attribution=(), unsupported_classifications=(),
        records=(watch,), portfolio_records=(), policy_identity=watch.policy_identity,
        rotation_challenger_count=0, actual_rotation_candidate_count=0,
    )


@pytest.fixture
def stores(tmp_path):
    governance, _, _ = _approved_selected(tmp_path)
    snapshots = SQLiteCoreApiSnapshotRepository(tmp_path / "watch.sqlite")
    try:
        yield governance, snapshots, HSISignalStrategyRegistry(governance)
    finally:
        snapshots.close()
        governance.close()


def _project(watch, registry):
    return project_watch_to_hsi_signal(
        watch=watch, archetype=OpportunityArchetype.PRE_BREAKOUT, registry=registry,
    )


def test_persisted_watch_and_governance_reopen_reproduce_p1_not_signal_history(tmp_path, stores):
    governance, snapshots, registry = stores
    watch = _watch()
    store = MarketWideWatchStore(snapshots)
    assert store.save(_run(watch)) is True
    expected = serialize_hsi_signal(_project(watch, registry))
    assert store.save(_run(watch)) is False
    reopened_snapshots = SQLiteCoreApiSnapshotRepository(tmp_path / "watch.sqlite")
    reopened_governance = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    try:
        restored = MarketWideWatchStore(reopened_snapshots).latest(as_of=T).records[0]
        replayed = _project(restored, HSISignalStrategyRegistry(reopened_governance))
        assert serialize_hsi_signal(replayed) == expected
        assert replayed.strategy_resolution.status is StrategyResolutionStatus.RESOLVED
        assert reopened_snapshots.list_snapshots(CoreApiSnapshotFamily.SIGNAL) == ()
        for table in ("signals", "signal_lifecycle_events", "paper_trades", "trade_plans"):
            assert reopened_governance._connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    finally:
        reopened_snapshots.close()
        reopened_governance.close()


def test_source_arrival_order_and_duplicate_retry_do_not_change_asof_projection(stores):
    _, snapshots, registry = stores
    store = MarketWideWatchStore(snapshots)
    old = _watch()
    later = _revision(old, watch_as_of=T + timedelta(days=1))
    assert store.save(_run(later)) and store.save(_run(old))
    assert store.latest(as_of=T).records == (old,)
    assert store.latest(as_of=T - timedelta(microseconds=1)) is None
    assert store.latest(as_of=later.watch_as_of).records == (later,)
    original = _project(old, registry)
    for _ in range(3):
        assert store.save(_run(old)) is False
        assert _project(store.latest(as_of=T).records[0], registry) == original
    newer = _project(later, registry)
    assert newer.signal_id != original.signal_id
    assert not hasattr(newer, "supersedes_signal_id")


@pytest.mark.parametrize("status", tuple(WatchStatus))
def test_watch_status_is_descriptive_not_a_signal_transition_or_trade(stores, status):
    _, _, registry = stores
    watch = _revision(_watch(), status=status,
        classifications=(WatchClassification.RISK_WATCH,) if status is WatchStatus.WATCH_RISK else ())
    signal = _project(watch, registry)
    assert signal.source_watch_status == status.value
    assert signal.source_lifecycle_flags == watch.lifecycle_flags
    assert signal.actionability is HSISignalActionability.WATCH_ONLY
    assert signal.execution_status is HSISignalExecutionStatus.NON_EXECUTABLE
    assert signal.expires_at is None
    assert P1UnavailableReason.EXPIRY_POLICY_UNAVAILABLE in signal.unavailable_reasons
    assert not hasattr(signal, "previous_state") and not hasattr(signal, "transition_history")


def test_lost_setup_precondition_cannot_rewrite_prior_resolved_projection(stores):
    _, _, registry = stores
    first = _project(_watch(), registry)
    retained = serialize_hsi_signal(first)
    missing = _project(_watch(as_of=T + timedelta(days=1), setup_state="NO_CURRENT_SETUP"), registry)
    assert missing.strategy_resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert "CURRENT_VALID_SETUP_REQUIRED" in missing.blocker_codes
    assert missing.signal_id != first.signal_id
    assert serialize_hsi_signal(first) == retained
    # Missing current setup is not an approved terminal-invalidation event.
    assert missing.source_watch_status == WatchStatus.WATCH_ACTIVE.value


def test_projection_failure_after_watch_save_leaves_source_immutable_and_retryable(stores, monkeypatch):
    _, snapshots, registry = stores
    store = MarketWideWatchStore(snapshots)
    watch = _watch()
    store.save(_run(watch))
    expected = serialize_hsi_signal(_project(watch, registry))
    with monkeypatch.context() as patch:
        def fail(_context):
            raise RuntimeError("SYNTHETIC_PROJECTOR_INTERRUPTION")
        patch.setattr(registry, "resolve", fail)
        with pytest.raises(RuntimeError, match="SYNTHETIC"):
            _project(watch, registry)
    assert store.save(_run(watch)) is False
    assert serialize_hsi_signal(_project(store.latest(as_of=T).records[0], registry)) == expected
    assert len(snapshots.list_snapshots(CoreApiSnapshotFamily.MARKET_WIDE_QUALITY_INFLECTION_WATCH)) == 1


def test_future_or_tampered_watch_cannot_enter_projection(stores):
    _, _, registry = stores
    with pytest.raises(HSISignalProjectionError, match="FUTURE_EVIDENCE_EXCLUDED"):
        _project(_watch(last_evidence_as_of=T + timedelta(seconds=1)), registry)
    changed = _watch()
    object.__setattr__(changed, "canonical_instrument_id", "NSE:OTHER")
    with pytest.raises(HSISignalProjectionError, match="WATCH_INVALID"):
        _project(changed, registry)


def test_independent_concurrent_readers_return_identical_projection_not_write_guarantee(tmp_path, stores):
    _, snapshots, registry = stores
    MarketWideWatchStore(snapshots).save(_run(_watch()))
    expected = serialize_hsi_signal(_project(_watch(), registry))
    def read(_):
        source = SQLiteCoreApiSnapshotRepository(tmp_path / "watch.sqlite")
        governance = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
        try:
            return serialize_hsi_signal(_project(
                MarketWideWatchStore(source).latest(as_of=T).records[0],
                HSISignalStrategyRegistry(governance),
            ))
        finally:
            source.close()
            governance.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(read, range(4))) == [expected] * 4


def test_p1_contract_has_no_legacy_lifecycle_or_execution_bridge():
    assert HSISignal.__module__ == "app.intelligence.hsi_signal"
    names = {f.name for f in fields(HSISignal)}
    assert not names & {"trade_plan_id", "gate_evaluation_id", "order_id", "previous_state", "transition_id"}
    for name in ("hsi_signal", "hsi_signal_projection", "hsi_signal_strategy_registry"):
        tree = ast.parse(Path(f"app/intelligence/{name}.py").read_text(encoding="utf-8"))
        dependencies = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        dependencies += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        assert not any(value.startswith(("app.signals", "app.paper", "app.portfolio", "app.api", "app.runtime")) for value in dependencies)
