"""Small coordination/readiness seam; operational only, no strategy semantics."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Callable, Iterable
from uuid import uuid4

from app.historical.guard import manifest_fingerprint
from app.production_v1.models import (
    ProductionComponent, ProductionComponentHealth, ProductionReadinessState,
    ProductionSourceHealth, ProductionSourceStatus, ProductionV1CycleRun,
    ProductionV1CycleStatus, ProductionV1FinalStatus, ProductionV1PhaseReceipt,
    ProductionV1PhaseStatus, ProductionV1ReadinessReport,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


REQUIRED_SOURCE_COMPONENTS = (
    ProductionComponent.OHLCV, ProductionComponent.INDEX_BARS, ProductionComponent.DELIVERY,
    ProductionComponent.MEMBERSHIP, ProductionComponent.TAXONOMY, ProductionComponent.CORPORATE_ACTIONS,
    ProductionComponent.FINANCIALS, ProductionComponent.SHAREHOLDING, ProductionComponent.MACRO,
    ProductionComponent.NEWS,
)


def build_readiness_report(*, generated_at: datetime, components: Iterable[ProductionComponentHealth],
                           sources: Iterable[ProductionSourceHealth], p1: tuple[str, ...] = (),
                           p2: tuple[str, ...] = ()) -> ProductionV1ReadinessReport:
    component_map = {item.component: item for item in components}
    ordered = tuple(component_map.get(item, ProductionComponentHealth(item, ProductionReadinessState.BLOCKED, "COMPONENT_UNREPORTED")) for item in ProductionComponent)
    source_map = {item.family: item for item in sources}
    blockers = [f"{item.component.value}:{item.reason or item.state.value}" for item in ordered
                if item.state in {ProductionReadinessState.BLOCKED, ProductionReadinessState.NOT_CONFIGURED, ProductionReadinessState.FAILED}]
    for family in REQUIRED_SOURCE_COMPONENTS:
        source = source_map.get(family)
        if source is None or source.status in {ProductionSourceStatus.BLOCKED_CONFIGURATION, ProductionSourceStatus.BLOCKED_MISSING_APPROVED_SOURCE}:
            blockers.append(f"{family.value}:{source.blocker if source else 'SOURCE_UNREPORTED'}")
    p0 = tuple(sorted(set(blockers)))
    return ProductionV1ReadinessReport(generated_at,
        ProductionV1FinalStatus.PRODUCTION_V1_READY if not p0 else ProductionV1FinalStatus.PRODUCTION_V1_NOT_READY,
        ordered, tuple(sorted(sources, key=lambda item: item.family.value)), p0, tuple(sorted(set(p1))), tuple(sorted(set(p2))))


class ProductionV1Cycle:
    """Orders callbacks without blending their business logic or transactions."""
    def __init__(self, *, refresh: Callable[[datetime], object], reconcile: Callable[[datetime], object],
                 readiness: Callable[[datetime], ProductionV1ReadinessReport], brain: Callable[[datetime], object],
                 setup: Callable[[datetime], object], paper: Callable[[datetime], object], clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._refresh, self._reconcile, self._readiness = refresh, reconcile, readiness
        self._brain, self._setup, self._paper, self._clock = brain, setup, paper, clock

    def run_once(self, *, as_of: datetime | None = None) -> tuple[str, tuple[str, ...], ProductionV1ReadinessReport]:
        cutoff = as_of or self._clock(); stages=[]
        self._refresh(cutoff); stages.append("REFRESH")
        self._reconcile(cutoff); stages.append("RECONCILE")
        report = self._readiness(cutoff); stages.append("READINESS")
        if report.final_status is ProductionV1FinalStatus.PRODUCTION_V1_NOT_READY:
            return f"production-v1-cycle:{uuid4()}", tuple(stages), report
        self._brain(cutoff); stages.append("SHARED_BRAIN")
        self._setup(cutoff); stages.append("SETUP")
        self._paper(cutoff); stages.append("PAPER")
        return f"production-v1-cycle:{uuid4()}", tuple(stages), report


class ProductionV1CycleRunStore:
    """Append-only cycle history using the already-reserved snapshot family."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: ProductionV1CycleRun) -> bool:
        existing = self._repository.get_snapshot(value.run_id)
        if existing is not None:
            if existing.family is not CoreApiSnapshotFamily.PRODUCTION_V1_CYCLE_RUN or existing.payload != value:
                raise ValueError("PRODUCTION_V1_CYCLE_RUN_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.run_id, CoreApiSnapshotFamily.PRODUCTION_V1_CYCLE_RUN,
            "v1", type(value).__name__, value.fingerprint, value.completed_at, value,
        ))
        return True

    def runs(self) -> tuple[ProductionV1CycleRun, ...]:
        values: list[ProductionV1CycleRun] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.PRODUCTION_V1_CYCLE_RUN, limit=100, offset=offset)
            values.extend(item.payload for item in page if isinstance(item.payload, ProductionV1CycleRun))
            if len(page) < 100:
                return tuple(sorted(values, key=lambda item: (item.completed_at, item.run_id)))
            offset += len(page)

    def latest_successful(self, *, as_of: datetime) -> ProductionV1CycleRun | None:
        values = tuple(item for item in self.runs() if item.status is ProductionV1CycleStatus.SUCCESS and item.as_of <= as_of)
        return values[-1] if values else None


class ProductionV1ControlledCycle:
    """Durable wrapper around :class:`ProductionV1Cycle`, not a second coordinator.

    The existing coordinator remains the one place that orders production
    phases.  This wrapper supplies its callbacks, records their factual
    outcomes, and treats only the self-referential ``LAST_FULL_CYCLE`` blocker
    as permissible before the first successful receipt exists.
    """

    def __init__(
        self,
        *,
        refresh: Callable[[datetime], ProductionV1PhaseReceipt],
        reconcile: Callable[[datetime], ProductionV1PhaseReceipt],
        readiness: Callable[[datetime], ProductionV1ReadinessReport],
        brain: Callable[[datetime], ProductionV1PhaseReceipt],
        setup: Callable[[datetime], ProductionV1PhaseReceipt],
        paper: Callable[[datetime], ProductionV1PhaseReceipt],
        store: ProductionV1CycleRunStore,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._refresh, self._reconcile, self._readiness = refresh, reconcile, readiness
        self._brain, self._setup, self._paper, self._store, self._clock = brain, setup, paper, store, clock

    def run_once(self, *, as_of: datetime | None = None) -> tuple[ProductionV1CycleRun, ProductionV1ReadinessReport]:
        started = self._clock()
        cutoff = as_of or started
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise ValueError("PRODUCTION_V1_CYCLE_AS_OF_REQUIRED")
        phase_receipts: list[ProductionV1PhaseReceipt] = []
        values: dict[str, object] = {}

        def phase(name: str, action):
            result = action(cutoff)
            if not isinstance(result, ProductionV1PhaseReceipt) or result.phase != name:
                raise ValueError("PRODUCTION_V1_CYCLE_PHASE_RECEIPT_REQUIRED")
            phase_receipts.append(result)
            values[name] = result
            if result.status in {ProductionV1PhaseStatus.BLOCKED, ProductionV1PhaseStatus.FAILED}:
                raise _ProductionV1CycleBlocked(result.reason or result.status.value)
            return result

        report: ProductionV1ReadinessReport | None = None
        try:
            def readiness_callback(at: datetime) -> ProductionV1ReadinessReport:
                nonlocal report
                report = self._readiness(at)
                phase_receipts.append(ProductionV1PhaseReceipt(
                    "READINESS", ProductionV1PhaseStatus.COMPLETE,
                    "PRE_FLIGHT_READINESS_CAPTURED", (readiness_fingerprint(report),),
                ))
                return _preflight_readiness(report)

            coordinator = ProductionV1Cycle(
                refresh=lambda at: phase("REFRESH", self._refresh),
                reconcile=lambda at: phase("RECONCILE", self._reconcile),
                readiness=readiness_callback,
                brain=lambda at: phase("SHARED_BRAIN", self._brain),
                setup=lambda at: phase("SETUP", self._setup),
                paper=lambda at: phase("PAPER", self._paper),
                clock=lambda: cutoff,
            )
            _, stages, preflight = coordinator.run_once(as_of=cutoff)
            assert report is not None
            if len(stages) != 6:
                receipt = self._receipt(
                    started, cutoff, ProductionV1CycleStatus.BLOCKED, phase_receipts, report,
                    blockers=preflight.p0_blockers,
                )
                self._store.save(receipt)
                return receipt, report
            receipt = self._receipt(
                started, cutoff, ProductionV1CycleStatus.SUCCESS, phase_receipts, report,
            )
            self._store.save(receipt)
            # Re-read after persisting the immutable success receipt.  This is
            # the only point at which LAST_FULL_CYCLE may truthfully clear.
            return receipt, self._readiness(cutoff)
        except _ProductionV1CycleBlocked as error:
            if report is None:
                report = self._readiness(cutoff)
            receipt = self._receipt(
                started, cutoff, ProductionV1CycleStatus.BLOCKED, phase_receipts, report,
                blockers=(str(error),),
            )
            self._store.save(receipt)
            return receipt, report
        except Exception as error:
            if report is None:
                report = self._readiness(cutoff)
            failed_phase = _next_phase(phase_receipts)
            phase_receipts.append(ProductionV1PhaseReceipt(
                failed_phase, ProductionV1PhaseStatus.FAILED, "PRODUCTION_V1_CYCLE_PHASE_FAILED",
            ))
            receipt = self._receipt(
                started, cutoff, ProductionV1CycleStatus.FAILED, phase_receipts, report,
                blockers=("PRODUCTION_V1_CYCLE_PHASE_FAILED",),
                limitations=(type(error).__name__,),
            )
            self._store.save(receipt)
            return receipt, report

    def _receipt(
        self,
        started: datetime,
        cutoff: datetime,
        status: ProductionV1CycleStatus,
        phases: list[ProductionV1PhaseReceipt],
        report: ProductionV1ReadinessReport,
        *,
        blockers: tuple[str, ...] = (),
        limitations: tuple[str, ...] = (),
    ) -> ProductionV1CycleRun:
        by_name = {item.phase: item for item in phases}
        setup = by_name.get("SETUP")
        paper = by_name.get("PAPER")
        return ProductionV1CycleRun.create(
            run_id=f"production-v1-cycle:{uuid4().hex}", started_at=started,
            completed_at=self._clock(), as_of=cutoff, status=status,
            phases=tuple(phases), readiness_fingerprint=readiness_fingerprint(report),
            setup_source_run_id=_lineage_id(setup), setup_source_fingerprint=_lineage_id(setup, index=1),
            forward_paper_run_id=_lineage_id(paper), blockers=blockers,
            limitations=limitations or tuple(sorted(set((*report.p1, *report.p2)))),
        )


def readiness_fingerprint(report: ProductionV1ReadinessReport) -> str:
    """Stable receipt lineage for the factual readiness captured by a cycle."""
    return manifest_fingerprint(
        generated_at=report.generated_at.isoformat(), final_status=report.final_status.value,
        components=tuple((item.component.value, item.state.value, item.reason, item.evidence_id) for item in report.components),
        sources=tuple((item.family.value, item.source, item.adapter, item.status.value, item.coverage, item.blocker) for item in report.sources),
        p0=report.p0_blockers, p1=report.p1, p2=report.p2,
    )


def _preflight_readiness(report: ProductionV1ReadinessReport) -> ProductionV1ReadinessReport:
    """A first cycle cannot be blocked solely by the absence of itself."""
    retained = tuple(item for item in report.p0_blockers if not item.startswith("LAST_FULL_CYCLE:"))
    if retained == report.p0_blockers:
        return report
    return replace(
        report,
        final_status=(ProductionV1FinalStatus.PRODUCTION_V1_READY if not retained else ProductionV1FinalStatus.PRODUCTION_V1_NOT_READY),
        p0_blockers=retained,
    )


def _next_phase(values: list[ProductionV1PhaseReceipt]) -> str:
    ordered = ("REFRESH", "RECONCILE", "READINESS", "SHARED_BRAIN", "SETUP", "PAPER")
    completed = {item.phase for item in values}
    return next((item for item in ordered if item not in completed), ordered[-1])


def _lineage_id(value: ProductionV1PhaseReceipt | None, *, index: int = 0) -> str | None:
    return value.lineage_ids[index] if value is not None and len(value.lineage_ids) > index else None


class _ProductionV1CycleBlocked(RuntimeError):
    """Internal control-flow marker for a factual fail-closed phase outcome."""
