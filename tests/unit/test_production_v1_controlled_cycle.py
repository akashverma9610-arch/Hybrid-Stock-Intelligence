from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.forward_paper.models import PaperExecutionModel
from app.forward_paper.service import ForwardPaperOrchestrator, ForwardPaperService, ForwardPaperWorker, PaperTradingSettings
from app.forward_paper.store import ForwardPaperStore
from app.production_v1.models import (
    ProductionComponent, ProductionComponentHealth, ProductionReadinessState,
    ProductionSourceHealth, ProductionSourceStatus, ProductionV1CycleStatus,
    ProductionV1FinalStatus, ProductionV1PhaseReceipt, ProductionV1PhaseStatus,
)
from app.production_v1.service import (
    ProductionV1ControlledCycle, ProductionV1CycleRunStore, build_readiness_report,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 30, 9, 30, tzinfo=UTC)


def _report(*, worker: ProductionReadinessState = ProductionReadinessState.READY,
            last: ProductionReadinessState = ProductionReadinessState.NOT_CONFIGURED):
    components = []
    for component in ProductionComponent:
        state = worker if component is ProductionComponent.PAPER_WORKER else last if component is ProductionComponent.LAST_FULL_CYCLE else ProductionReadinessState.READY
        reason = "PAPER_TRADING_ENABLED_FALSE" if component is ProductionComponent.PAPER_WORKER and state is not ProductionReadinessState.READY else "NO_SUCCESSFUL_PRODUCTION_CYCLE" if component is ProductionComponent.LAST_FULL_CYCLE and state is not ProductionReadinessState.READY else None
        components.append(ProductionComponentHealth(component, state, reason))
    families = tuple(
        ProductionSourceHealth(component, "approved", "adapter", ProductionSourceStatus.OPERATIONAL, "current")
        for component in (
            ProductionComponent.OHLCV, ProductionComponent.INDEX_BARS, ProductionComponent.DELIVERY,
            ProductionComponent.MEMBERSHIP, ProductionComponent.TAXONOMY, ProductionComponent.CORPORATE_ACTIONS,
            ProductionComponent.FINANCIALS, ProductionComponent.SHAREHOLDING, ProductionComponent.MACRO,
            ProductionComponent.NEWS,
        )
    )
    return build_readiness_report(generated_at=T, components=tuple(components), sources=families)


def _phase(name: str, status: ProductionV1PhaseStatus = ProductionV1PhaseStatus.COMPLETE, reason: str | None = None, lineage=()):
    return ProductionV1PhaseReceipt(name, status, reason, tuple(lineage))


def test_paper_trading_default_is_off_and_explicit_local_opt_in_is_supported() -> None:
    assert PaperTradingSettings.from_environment({}).enabled is False
    assert PaperTradingSettings.from_environment({"PAPER_TRADING_ENABLED": "true"}).enabled is True


def test_controlled_cycle_succeeds_for_a_zero_setup_no_action_and_persists_receipt(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "cycle.sqlite")
    store = ProductionV1CycleRunStore(repository)
    pre, post = _report(), _report(last=ProductionReadinessState.READY)
    reads = []

    def readiness(_: datetime):
        reads.append(True)
        return post if len(reads) >= 2 else pre

    cycle = ProductionV1ControlledCycle(
        refresh=lambda _: _phase("REFRESH", ProductionV1PhaseStatus.NO_ACTION, "STORED_EVIDENCE_REUSED_REFRESH_NOT_REQUESTED"),
        reconcile=lambda _: _phase("RECONCILE", ProductionV1PhaseStatus.DEGRADED, "OHLCV_CONFLICTS_ISOLATED_PER_INSTRUMENT"),
        readiness=readiness,
        brain=lambda _: _phase("SHARED_BRAIN", ProductionV1PhaseStatus.DEGRADED, "STORED_CONTRACT_VALIDATED"),
        setup=lambda _: _phase("SETUP", ProductionV1PhaseStatus.NO_ACTION, "NO_CURRENT_EXECUTABLE_SETUP", ("setup-run", "setup-fp")),
        paper=lambda _: _phase("PAPER", ProductionV1PhaseStatus.NO_ACTION, "NO_CURRENT_EXECUTABLE_SETUP", ("paper-run",)),
        store=store, clock=lambda: T,
    )

    receipt, report = cycle.run_once()

    assert receipt.status is ProductionV1CycleStatus.SUCCESS
    assert tuple(item.phase for item in receipt.phases) == ("REFRESH", "RECONCILE", "READINESS", "SHARED_BRAIN", "SETUP", "PAPER")
    assert receipt.setup_source_run_id == "setup-run" and receipt.forward_paper_run_id == "paper-run"
    assert report.final_status is ProductionV1FinalStatus.PRODUCTION_V1_READY
    repository.close()
    reopened = SQLiteCoreApiSnapshotRepository(tmp_path / "cycle.sqlite")
    assert ProductionV1CycleRunStore(reopened).latest_successful(as_of=T) == receipt


def test_mandatory_worker_blocker_stops_before_brain_setup_or_paper_and_records_receipt(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "blocked.sqlite")
    calls: list[str] = []
    cycle = ProductionV1ControlledCycle(
        refresh=lambda _: calls.append("refresh") or _phase("REFRESH"),
        reconcile=lambda _: calls.append("reconcile") or _phase("RECONCILE"),
        readiness=lambda _: _report(worker=ProductionReadinessState.NOT_CONFIGURED),
        brain=lambda _: calls.append("brain") or _phase("SHARED_BRAIN"),
        setup=lambda _: calls.append("setup") or _phase("SETUP"),
        paper=lambda _: calls.append("paper") or _phase("PAPER"),
        store=ProductionV1CycleRunStore(repository), clock=lambda: T,
    )

    receipt, _ = cycle.run_once()

    assert receipt.status is ProductionV1CycleStatus.BLOCKED
    assert tuple(item.phase for item in receipt.phases) == ("REFRESH", "RECONCILE", "READINESS")
    assert calls == ["refresh", "reconcile"]
    assert "PAPER_WORKER:PAPER_TRADING_ENABLED_FALSE" in receipt.blockers


def test_paper_orchestrator_empty_admission_is_a_durable_idempotent_no_op(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "paper.sqlite")
    store = ForwardPaperStore(repository)
    service = ForwardPaperService(store)
    model = PaperExecutionModel.create(
        version="paper-execution-v1", entry_slippage=Decimal("0"), exit_slippage=Decimal("0"), round_trip_friction=Decimal("0"),
    )
    orchestrator = ForwardPaperOrchestrator(
        service, execution_model=model, admissions=lambda _: (), bars_for=lambda *_: (),
        data_ready=lambda _: True, clock=lambda: T,
    )

    first, second = orchestrator.run_once(), orchestrator.run_once()
    assert first.health.value == "HEALTHY" and first.admitted == first.entries == first.exits == 0
    assert store.save_run(first) and store.save_run(second)
    assert len(store.runs()) == 2 and not store.studies()


def test_worker_never_runs_without_opt_in_and_repeated_zero_setup_ticks_are_safe(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "worker.sqlite")
    store = ForwardPaperStore(repository)
    service = ForwardPaperService(store)
    model = PaperExecutionModel.create(
        version="paper-execution-v1", entry_slippage=Decimal("0"), exit_slippage=Decimal("0"), round_trip_friction=Decimal("0"),
    )
    orchestrator = ForwardPaperOrchestrator(
        service, execution_model=model, admissions=lambda _: (), bars_for=lambda *_: (),
        data_ready=lambda _: True, clock=lambda: T,
    )
    assert ForwardPaperWorker(orchestrator, PaperTradingSettings()).run_forever(max_ticks=1) is False
    enabled = ForwardPaperWorker(
        orchestrator, PaperTradingSettings(enabled=True, poll_seconds=1), record_run=store.save_run,
    )
    assert enabled.run_forever(max_ticks=2) is True
    assert len(store.runs()) == 2 and not store.studies() and not store.events("not-a-study")
