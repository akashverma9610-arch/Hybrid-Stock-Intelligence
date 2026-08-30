from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class ProductionReadinessState(StrEnum):
    READY = "READY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    FAILED = "FAILED"


class ProductionV1FinalStatus(StrEnum):
    PRODUCTION_V1_READY = "PRODUCTION_V1_READY"
    PRODUCTION_V1_NOT_READY = "PRODUCTION_V1_NOT_READY"


class ProductionV1CycleStatus(StrEnum):
    """Terminal status of one immutable, controlled Production-v1 cycle."""

    SUCCESS = "SUCCESS"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ProductionV1PhaseStatus(StrEnum):
    COMPLETE = "COMPLETE"
    NO_ACTION = "NO_ACTION"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ProductionSourceStatus(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    OPERATIONAL_WITH_LIMITATION = "OPERATIONAL_WITH_LIMITATION"
    BLOCKED_MISSING_APPROVED_SOURCE = "BLOCKED_MISSING_APPROVED_SOURCE"
    BLOCKED_CONFIGURATION = "BLOCKED_CONFIGURATION"
    NOT_REQUIRED_FOR_CURRENT_V1_SCOPE = "NOT_REQUIRED_FOR_CURRENT_V1_SCOPE"


class ProductionComponent(StrEnum):
    DATABASE = "DATABASE"
    DATA_OPERATIONS = "DATA_OPERATIONS"
    OHLCV = "OHLCV"
    INDEX_BARS = "INDEX_BARS"
    DELIVERY = "DELIVERY"
    MEMBERSHIP = "MEMBERSHIP"
    TAXONOMY = "TAXONOMY"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    FINANCIALS = "FINANCIALS"
    SHAREHOLDING = "SHAREHOLDING"
    MACRO = "MACRO"
    NEWS = "NEWS"
    SHARED_BRAIN = "SHARED_BRAIN"
    U16_APPLICATION = "U16_APPLICATION"
    GOVERNED_SETUP_SOURCE = "GOVERNED_SETUP_SOURCE"
    PAPER_SETUP_COMPOSITION = "PAPER_SETUP_COMPOSITION"
    PAPER_BAR_COMPOSITION = "PAPER_BAR_COMPOSITION"
    PAPER_WORKER = "PAPER_WORKER"
    BENCHMARK = "BENCHMARK"
    PIT_RECONSTRUCTION = "PIT_RECONSTRUCTION"
    LAST_FULL_CYCLE = "LAST_FULL_CYCLE"


@dataclass(frozen=True, slots=True)
class ProductionComponentHealth:
    component: ProductionComponent
    state: ProductionReadinessState
    reason: str | None = None
    evidence_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionSourceHealth:
    family: ProductionComponent
    source: str | None
    adapter: str | None
    status: ProductionSourceStatus
    coverage: str | None
    blocker: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionV1ReadinessReport:
    generated_at: datetime
    final_status: ProductionV1FinalStatus
    components: tuple[ProductionComponentHealth, ...]
    sources: tuple[ProductionSourceHealth, ...]
    p0_blockers: tuple[str, ...]
    p1: tuple[str, ...] = ()
    p2: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("PRODUCTION_READINESS_TIMESTAMP_REQUIRED")
        if tuple(item.component for item in self.components) != tuple(ProductionComponent):
            raise ValueError("PRODUCTION_READINESS_COMPONENT_ORDER_REQUIRED")
        expected = ProductionV1FinalStatus.PRODUCTION_V1_READY if not self.p0_blockers else ProductionV1FinalStatus.PRODUCTION_V1_NOT_READY
        if self.final_status is not expected: raise ValueError("PRODUCTION_READINESS_FINAL_STATUS_INVALID")


@dataclass(frozen=True, slots=True)
class ProductionV1PhaseReceipt:
    """One factual phase outcome retained by a controlled cycle receipt."""

    phase: str
    status: ProductionV1PhaseStatus
    reason: str | None = None
    lineage_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.phase not in {"REFRESH", "RECONCILE", "READINESS", "SHARED_BRAIN", "SETUP", "PAPER"}:
            raise ValueError("PRODUCTION_V1_CYCLE_PHASE_UNKNOWN")
        if len(set(self.lineage_ids)) != len(self.lineage_ids) or any(not item for item in self.lineage_ids):
            raise ValueError("PRODUCTION_V1_CYCLE_PHASE_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class ProductionV1CycleRun:
    """Append-only receipt for one complete, controlled Production-v1 attempt."""

    run_id: str
    started_at: datetime
    completed_at: datetime
    as_of: datetime
    status: ProductionV1CycleStatus
    phases: tuple[ProductionV1PhaseReceipt, ...]
    readiness_fingerprint: str
    setup_source_run_id: str | None
    setup_source_fingerprint: str | None
    forward_paper_run_id: str | None
    blockers: tuple[str, ...]
    limitations: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.run_id or not self.readiness_fingerprint:
            raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_IDENTITY_REQUIRED")
        for field in ("started_at", "completed_at", "as_of"):
            value = getattr(self, field)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_TIMESTAMP_REQUIRED")
        if self.completed_at < self.started_at:
            raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_CHRONOLOGY_INVALID")
        phases = tuple(item.phase for item in self.phases)
        expected = ("REFRESH", "RECONCILE", "READINESS", "SHARED_BRAIN", "SETUP", "PAPER")
        if phases != expected[:len(phases)] or not phases:
            raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_PHASE_ORDER_INVALID")
        if tuple(sorted(set(self.blockers))) != self.blockers or tuple(sorted(set(self.limitations))) != self.limitations:
            raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_DISCLOSURE_INVALID")
        if self.fingerprint != _cycle_fingerprint(self):
            raise ValueError("PRODUCTION_V1_CYCLE_RECEIPT_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, **values) -> "ProductionV1CycleRun":
        values["phases"] = tuple(values["phases"])
        values["blockers"] = tuple(sorted(set(values.get("blockers", ()))))
        values["limitations"] = tuple(sorted(set(values.get("limitations", ()))))
        values["fingerprint"] = _cycle_fingerprint_values(values)
        return cls(**values)


def _cycle_fingerprint(value: ProductionV1CycleRun) -> str:
    return _cycle_fingerprint_values({field.name: getattr(value, field.name) for field in fields(value) if field.name != "fingerprint"})


def _cycle_fingerprint_values(values: dict) -> str:
    def semantic(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, ProductionV1PhaseReceipt):
            return {
                "phase": value.phase, "status": value.status.value, "reason": value.reason,
                "lineage_ids": value.lineage_ids,
            }
        if isinstance(value, tuple):
            return tuple(semantic(item) for item in value)
        return value
    return manifest_fingerprint(**{key: semantic(value) for key, value in values.items()})
