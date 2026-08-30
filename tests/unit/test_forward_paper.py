from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from threading import Thread

import pytest

from app.forward_paper.models import (
    ForwardPaperBar, PaperEventKind, PaperStudyAdmission, PaperStudyState,
    PaperExecutionModel,
)
from app.forward_paper.service import ForwardPaperHealth, ForwardPaperOrchestrator, ForwardPaperService, admission_from_prebreakout
from app.forward_paper.store import ForwardPaperStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository

T0 = datetime(2026, 8, 3, 15, 30, tzinfo=UTC)


def model(): return PaperExecutionModel.create(version="paper-execution-v1", entry_slippage=Decimal("0"), exit_slippage=Decimal("0"), round_trip_friction=Decimal("0.10"))
def admission(*, version="v1", maximum=Decimal("103"), horizon=5):
    return PaperStudyAdmission("stock-1", "setup-1", "setup-fingerprint-" + version, "source-fingerprint", version, "policy-" + version,
        T0, Decimal("100"), Decimal("95"), Decimal("115"), maximum, horizon,
        market_regime="RISK_ON", market_regime_fingerprint="regime-fp", sector="REALTY", sector_context_fingerprint="sector-fp",
        brain_version="brain-" + version, brain_fingerprint="brain-fp", decision_score=Decimal("9.1"),
        diagnostic_fingerprint="diagnostic-fp", financial_semantic_fingerprint="financial-fp")
def bar(name, days, open_, high, low, close, **kwargs):
    at = T0 + timedelta(days=days)
    return ForwardPaperBar(name, at, at, Decimal(open_), Decimal(high), Decimal(low), Decimal(close), **kwargs)
def service(path=":memory:"):
    repo = SQLiteCoreApiSnapshotRepository(path); return ForwardPaperService(ForwardPaperStore(repo)), repo
def admit(value, *, s=None):
    instance, repo = s or service(); study, inserted = instance.admit(value, model(), created_at=T0); assert inserted
    return instance, repo, study


def test_forward_winner_is_not_filled_on_decision_bar_and_tracks_r_mfe_mae():
    instance, _, study = admit(admission())
    # T0 is present but must never be eligible; T1 waits, T2 fills, T3 exits target.
    snapshot = instance.evaluate(study.study_id, (bar("t0", 0, "99", "101", "98", "100"), bar("t1", 1, "99", "99", "97", "98"),
        bar("t2", 2, "99", "101", "98", "100"), bar("t3", 3, "104", "116", "103", "115")), processing_as_of=T0 + timedelta(days=3))
    assert snapshot.state is PaperStudyState.CLOSED
    assert snapshot.entry_session == T0 + timedelta(days=2)
    assert snapshot.gross_r == Decimal("3") and snapshot.net_r == Decimal("2.98")
    assert snapshot.mfe_r == Decimal("3.2") and snapshot.mae_r == Decimal("-0.4")
    assert snapshot.sessions_held == 2


def test_gap_over_e_max_is_missed_and_not_filled():
    instance, _, study = admit(admission())
    snapshot = instance.evaluate(study.study_id, (bar("t1", 1, "104", "106", "103", "105"),), processing_as_of=T0 + timedelta(days=1))
    assert snapshot.state is PaperStudyState.MISSED_DO_NOT_CHASE and snapshot.entry_price is None


def test_stop_gap_uses_open_and_loss_is_retained_in_performance():
    instance, _, study = admit(admission())
    snapshot = instance.evaluate(study.study_id, (bar("t1", 1, "99", "101", "98", "100"), bar("t2", 2, "90", "94", "89", "92")), processing_as_of=T0 + timedelta(days=2))
    assert snapshot.exit_price == Decimal("90") and snapshot.net_r == Decimal("-2.02")
    report = instance.performance(generated_at=T0 + timedelta(days=2))
    assert report.losses == 1 and report.eligible_closed_count == 1 and report.expectancy_r == Decimal("-2.02")


def test_path_ambiguous_is_explicit_and_excluded_from_headline_r():
    instance, _, study = admit(admission())
    snapshot = instance.evaluate(study.study_id, (bar("t1", 1, "99", "101", "98", "100"), bar("t2", 2, "100", "116", "94", "105")), processing_as_of=T0 + timedelta(days=2))
    assert snapshot.state is PaperStudyState.AMBIGUOUS and snapshot.net_r is None
    report = instance.performance(generated_at=T0 + timedelta(days=2))
    assert report.ambiguous_count == 1 and report.eligible_closed_count == 0


def test_time_stop_and_waiting_expiry_are_distinct():
    instance, _, study = admit(admission(horizon=2))
    closed = instance.evaluate(study.study_id, (bar("t1", 1, "99", "101", "98", "100"), bar("t2", 2, "101", "103", "100", "102")), processing_as_of=T0 + timedelta(days=2))
    assert closed.state is PaperStudyState.CLOSED and closed.exit_reason.value == "TIME_STOP"
    instance2, _, study2 = admit(admission(horizon=1))
    expired = instance2.evaluate(study2.study_id, (bar("wait1", 1, "90", "99", "89", "95"), bar("wait2", 2, "90", "99", "89", "95")), processing_as_of=T0 + timedelta(days=2))
    assert expired.state is PaperStudyState.EXPIRED_UNFILLED


def test_invalid_and_corporate_action_events_fail_closed_without_rewriting_history():
    instance, _, study = admit(admission())
    first = instance.evaluate(study.study_id, (bar("invalid", 1, "99", "101", "98", "100", valid=False),), processing_as_of=T0 + timedelta(days=1))
    assert first.state is PaperStudyState.INVALID_DATA
    assert [item.kind for item in instance._store.events(study.study_id)][-1] is PaperEventKind.DATA_INVALIDATED
    instance2, _, study2 = admit(admission())
    second = instance2.evaluate(study2.study_id, (bar("ca", 1, "99", "101", "98", "100", corporate_action_requires_review=True),), processing_as_of=T0 + timedelta(days=1))
    assert second.state is PaperStudyState.INVALID_DATA


def test_events_are_append_only_idempotent_and_durable_after_reopen(tmp_path):
    path = tmp_path / "paper.sqlite"; instance, repo, study = admit(admission(), s=service(path))
    bars = (bar("t1", 1, "99", "101", "98", "100"), bar("t2", 2, "104", "116", "103", "115"))
    first = instance.evaluate(study.study_id, bars, processing_as_of=T0 + timedelta(days=2)); event_count = first.event_count
    second = instance.evaluate(study.study_id, bars, processing_as_of=T0 + timedelta(days=2)); assert second.event_count == event_count
    repo.close(); reopened, reopened_repo = service(path)
    assert reopened.snapshot(study.study_id) == first
    reopened_repo.close()


def test_processing_cutoff_prevents_future_lookahead_and_catchup_is_chronological():
    instance, _, study = admit(admission())
    bars = (bar("t1", 1, "99", "99", "98", "98"), bar("t2", 2, "99", "101", "98", "100"), bar("t3", 3, "104", "116", "103", "115"))
    early = instance.evaluate(study.study_id, bars, processing_as_of=T0 + timedelta(days=1)); assert early.state is PaperStudyState.WAITING_FOR_TRIGGER
    later = instance.evaluate(study.study_id, bars, processing_as_of=T0 + timedelta(days=3)); assert later.state is PaperStudyState.CLOSED
    kinds = [item.kind for item in instance._store.events(study.study_id)]
    assert kinds.index(PaperEventKind.ENTRY_FILLED) < kinds.index(PaperEventKind.TARGET_EXIT)


def test_version_groups_stay_separate_and_context_is_preserved():
    instance, _, a = admit(admission(version="A")); _, _, b = admit(admission(version="B"), s=(instance, instance._store._repository))
    for study in (a, b): instance.evaluate(study.study_id, (bar("x" + study.study_id[-1], 1, "99", "101", "98", "100"), bar("z" + study.study_id[-1], 2, "104", "116", "103", "115")), processing_as_of=T0 + timedelta(days=2))
    evidence = instance.performance(generated_at=T0 + timedelta(days=2)); assert len(evidence.groups) == 2
    assert a.admission.financial_semantic_fingerprint == "financial-fp" and a.admission.decision_score == Decimal("9.1")


def test_prebreakout_adapter_does_not_treat_generic_candidate_as_a_score_admission():
    with pytest.raises((AttributeError, ValueError)):
        admission_from_prebreakout(object(), time_stop_sessions=5)  # no candidate / no executable economics


def test_concurrent_evaluation_does_not_create_duplicate_events():
    instance, _, study = admit(admission())
    bars = (bar("t1", 1, "99", "101", "98", "100"),)
    threads = [Thread(target=lambda: instance.evaluate(study.study_id, bars, processing_as_of=T0 + timedelta(days=1))) for _ in range(2)]
    for item in threads: item.start()
    for item in threads: item.join()
    assert len({item.event_id for item in instance._store.events(study.study_id)}) == len(instance._store.events(study.study_id))


def test_orchestrator_is_stored_only_orders_admission_before_paper_and_blocks_on_readiness():
    instance, _, _ = admit(admission())
    observed=[]
    orchestrator=ForwardPaperOrchestrator(instance, execution_model=model(), admissions=lambda at: (admission(version="orchestrated"),),
        bars_for=lambda study, at: (observed.append(study.study_id) or bar("future", 1, "99", "101", "98", "100"),),
        data_ready=lambda at: True, clock=lambda:T0)
    result=orchestrator.run_once()
    assert result.health is ForwardPaperHealth.HEALTHY and result.admitted == 1 and observed
    blocked=ForwardPaperOrchestrator(instance, execution_model=model(), admissions=lambda at: (), bars_for=lambda study, at: (), data_ready=lambda at:False, clock=lambda:T0).run_once()
    assert blocked.health is ForwardPaperHealth.BLOCKED_DATA


def test_orchestrator_preserves_per_instrument_ohlcv_conflict_as_blocked_data():
    instance, _, _ = admit(admission())
    orchestrator = ForwardPaperOrchestrator(
        instance, execution_model=model(), admissions=lambda at: (admission(version="ohlcv-conflict"),),
        bars_for=lambda study, at: (_ for _ in ()).throw(ValueError("OHLCV_CONFLICTED")),
        data_ready=lambda at: True, clock=lambda: T0,
    )

    result = orchestrator.run_once()

    assert result.health is ForwardPaperHealth.BLOCKED_DATA and result.reason == "OHLCV_CONFLICTED"
