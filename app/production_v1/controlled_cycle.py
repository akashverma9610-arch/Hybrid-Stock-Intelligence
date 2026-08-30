"""Controlled local composition of the existing Production-v1 cycle.

This module owns no provider adapter, strategy threshold, broker integration,
or scheduler.  It supplies factual callbacks to the existing
``ProductionV1Cycle`` coordinator and persists its immutable receipt.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Callable

from app.data_operations.models import EvidenceDataFamily
from app.data_operations.service import DataOperationsScheduler, DataOperationsService
from app.forward_paper.models import ForwardPaperHealth
from app.forward_paper.service import ForwardPaperOrchestrator, ForwardPaperRun
from app.forward_paper.store import ForwardPaperStore
from app.production_v1.governed_setup_source import GovernedExecutableSetupSourceState
from app.production_v1.models import ProductionV1PhaseReceipt, ProductionV1PhaseStatus
from app.production_v1.service import ProductionV1ControlledCycle, ProductionV1CycleRunStore


class ControlledProductionV1CycleService:
    """One explicit, bounded cycle over configured stored evidence.

    ``refresh_due`` is deliberately opt-in.  The default cycle proves the
    complete stored-data path against current canonical evidence and never
    creates a provider request merely to clear an operational receipt blocker.
    """

    def __init__(
        self,
        *,
        operations: DataOperationsService,
        readiness: Callable[[datetime], object],
        setup_source,
        paper: ForwardPaperOrchestrator,
        paper_store: ForwardPaperStore,
        cycle_store: ProductionV1CycleRunStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._operations, self._readiness = operations, readiness
        self._setup_source, self._paper, self._paper_store = setup_source, paper, paper_store
        self._cycle_store, self._clock = cycle_store, clock

    def run(self, *, as_of: datetime | None = None, refresh_due: bool = False):
        def refresh(cutoff: datetime) -> ProductionV1PhaseReceipt:
            if not refresh_due:
                return ProductionV1PhaseReceipt(
                    "REFRESH", ProductionV1PhaseStatus.NO_ACTION,
                    "STORED_EVIDENCE_REUSED_REFRESH_NOT_REQUESTED",
                )
            runs = DataOperationsScheduler(self._operations, clock=lambda: cutoff).run_due(requested_as_of=cutoff)
            status = ProductionV1PhaseStatus.COMPLETE if runs else ProductionV1PhaseStatus.NO_ACTION
            return ProductionV1PhaseReceipt(
                "REFRESH", status,
                None if runs else "NO_DUE_APPROVED_REFRESH_JOBS",
                tuple(sorted(item.run_id for item in runs)),
            )

        def reconcile(cutoff: datetime) -> ProductionV1PhaseReceipt:
            findings = self._operations.latest_conflict_findings(EvidenceDataFamily.OHLCV)
            return ProductionV1PhaseReceipt(
                "RECONCILE",
                ProductionV1PhaseStatus.DEGRADED if findings else ProductionV1PhaseStatus.COMPLETE,
                "OHLCV_CONFLICTS_ISOLATED_PER_INSTRUMENT" if findings else "STORED_RECONCILIATION_CLEAN",
                tuple(sorted(item.finding_id for item in findings)),
            )

        def brain(cutoff: datetime) -> ProductionV1PhaseReceipt:
            report = self._readiness(cutoff)
            component = next(item for item in report.components if item.component.value == "SHARED_BRAIN")
            return ProductionV1PhaseReceipt(
                "SHARED_BRAIN",
                ProductionV1PhaseStatus.COMPLETE if component.state.value == "READY" else ProductionV1PhaseStatus.DEGRADED,
                component.reason or "SHARED_BRAIN_STORED_EVIDENCE_AVAILABLE",
            )

        def setup(cutoff: datetime) -> ProductionV1PhaseReceipt:
            result = self._setup_source.run(as_of=cutoff)
            if result.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP:
                status, reason = ProductionV1PhaseStatus.COMPLETE, None
            elif result.state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP:
                status, reason = ProductionV1PhaseStatus.NO_ACTION, result.reason or "NO_CURRENT_EXECUTABLE_SETUP"
            else:
                status, reason = ProductionV1PhaseStatus.BLOCKED, result.reason or result.state.value
            return ProductionV1PhaseReceipt("SETUP", status, reason, (result.run_id, result.fingerprint))

        def paper(cutoff: datetime) -> ProductionV1PhaseReceipt:
            result: ForwardPaperRun = self._paper.run_once(processing_as_of=cutoff)
            self._paper_store.save_run(result)
            if result.health in {ForwardPaperHealth.BLOCKED_DATA, ForwardPaperHealth.FAILED}:
                status = ProductionV1PhaseStatus.BLOCKED
            elif result.health is ForwardPaperHealth.DEGRADED:
                status = ProductionV1PhaseStatus.DEGRADED
            elif result.admitted == result.entries == result.exits == result.marks == result.misses == result.ambiguous == 0:
                status = ProductionV1PhaseStatus.NO_ACTION
            else:
                status = ProductionV1PhaseStatus.COMPLETE
            reason = result.reason or ("NO_CURRENT_EXECUTABLE_SETUP" if status is ProductionV1PhaseStatus.NO_ACTION else None)
            return ProductionV1PhaseReceipt("PAPER", status, reason, (result.run_id,))

        cycle = ProductionV1ControlledCycle(
            refresh=refresh, reconcile=reconcile, readiness=self._readiness,
            brain=brain, setup=setup, paper=paper, store=self._cycle_store,
            clock=self._clock,
        )
        return cycle.run_once(as_of=as_of)


__all__ = ("ControlledProductionV1CycleService",)
