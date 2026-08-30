"""Immutable operational metadata for scheduled evidence refreshes.

These contracts describe work *around* canonical evidence.  They do not own
market, filing, delivery, or research data and consequently cannot overwrite
any historical evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class EvidenceDataFamily(StrEnum):
    OHLCV = "OHLCV"
    DELIVERY = "DELIVERY"
    INDEX_BARS = "INDEX_BARS"
    INDEX_MEMBERSHIP = "INDEX_MEMBERSHIP"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    FINANCIAL_RESULTS = "FINANCIAL_RESULTS"
    SHAREHOLDING = "SHAREHOLDING"
    TAXONOMY_REFERENCE = "TAXONOMY_REFERENCE"
    MACRO = "MACRO"
    NEWS = "NEWS"


class EvidenceRefreshMode(StrEnum):
    BACKFILL = "BACKFILL"
    INCREMENTAL = "INCREMENTAL"
    RECONCILIATION = "RECONCILIATION"


class EvidenceRefreshStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    GAP_FOUND = "GAP_FOUND"
    CONFLICT_FOUND = "CONFLICT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    NO_CHANGE = "NO_CHANGE"
    FAILED = "FAILED"


class EvidenceRefreshFailureKind(StrEnum):
    TRANSIENT = "TRANSIENT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    AUTHENTICATION_OR_CONFIGURATION = "AUTHENTICATION_OR_CONFIGURATION"
    VALIDATION = "VALIDATION"
    CONFLICT = "CONFLICT"
    CONCURRENCY = "CONCURRENCY"


class DataOperationsHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    NEVER_RUN = "NEVER_RUN"


class ReconciliationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    GAP_FOUND = "GAP_FOUND"
    CONFLICT_FOUND = "CONFLICT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    NO_CHANGE = "NO_CHANGE"


def _aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware.")


def _non_negative(value: int, field: str) -> None:
    if value < 0:
        raise ValueError(f"{field} must not be negative.")


@dataclass(frozen=True, slots=True)
class DataOperationCadence:
    family: EvidenceDataFamily
    interval: timedelta
    enabled: bool = True
    overlap_sessions: int = 0

    def __post_init__(self) -> None:
        if self.interval <= timedelta():
            raise ValueError("Data operation cadence must be positive.")
        if self.overlap_sessions < 0:
            raise ValueError("Reconciliation overlap must not be negative.")


@dataclass(frozen=True, slots=True)
class EvidenceRefreshWatermark:
    watermark_id: str
    family: EvidenceDataFamily
    provider: str
    scope: str
    accepted_through: datetime | None
    observed_at: datetime
    run_id: str
    source_fingerprint: str | None = None
    verified_from_store: bool = False

    def __post_init__(self) -> None:
        if not all((self.watermark_id.strip(), self.provider.strip(), self.scope.strip(), self.run_id.strip())):
            raise ValueError("Evidence watermark identity is required.")
        _aware(self.observed_at, "observed_at")
        if self.accepted_through is not None:
            _aware(self.accepted_through, "accepted_through")
            if self.accepted_through > self.observed_at:
                raise ValueError("Watermark cannot be accepted after it was observed.")
        if not self.verified_from_store:
            raise ValueError("Evidence watermarks require store verification.")


@dataclass(frozen=True, slots=True)
class EvidenceReconciliationFinding:
    finding_id: str
    run_id: str
    family: EvidenceDataFamily
    status: ReconciliationStatus
    subject: str
    observed_at: datetime
    reason: str
    provider: str | None = None
    source_reference: str | None = None

    def __post_init__(self) -> None:
        if not all((self.finding_id.strip(), self.run_id.strip(), self.subject.strip(), self.reason.strip())):
            raise ValueError("Reconciliation finding identity and reason are required.")
        _aware(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class EvidenceRefreshRun:
    run_id: str
    family: EvidenceDataFamily
    mode: EvidenceRefreshMode
    status: EvidenceRefreshStatus
    started_at: datetime
    completed_at: datetime
    requested_as_of: datetime
    provider: str
    discovered_count: int = 0
    accepted_count: int = 0
    duplicate_count: int = 0
    conflict_count: int = 0
    rejected_count: int = 0
    gap_count: int = 0
    retry_count: int = 0
    dependency_fingerprint: str | None = None
    error_summary: str | None = None
    warnings: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.run_id.strip(), self.provider.strip())):
            raise ValueError("Evidence refresh run identity is required.")
        for field in ("started_at", "completed_at", "requested_as_of"):
            _aware(getattr(self, field), field)
        if self.completed_at < self.started_at:
            raise ValueError("Evidence refresh run cannot complete before it starts.")
        for field in (
            "discovered_count", "accepted_count", "duplicate_count", "conflict_count",
            "rejected_count", "gap_count", "retry_count",
        ):
            _non_negative(getattr(self, field), field)
        if self.status in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, EvidenceRefreshStatus.INVALID_EVIDENCE} and not self.error_summary:
            raise ValueError("Failed refresh runs require a safe error summary.")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("Refresh warnings must be canonical.")
        if tuple(sorted(set(self.source_references))) != self.source_references:
            raise ValueError("Refresh source references must be canonical.")


@dataclass(frozen=True, slots=True)
class EvidenceRefreshRequest:
    run_id: str
    family: EvidenceDataFamily
    mode: EvidenceRefreshMode
    requested_as_of: datetime
    started_at: datetime
    prior_watermark: EvidenceRefreshWatermark | None
    overlap_sessions: int

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("Refresh request run_id is required.")
        _aware(self.requested_as_of, "requested_as_of")
        _aware(self.started_at, "started_at")
        if self.overlap_sessions < 0:
            raise ValueError("Refresh request overlap must not be negative.")


@dataclass(frozen=True, slots=True)
class EvidenceRefreshOutcome:
    status: EvidenceRefreshStatus
    provider: str
    discovered_count: int = 0
    accepted_count: int = 0
    duplicate_count: int = 0
    conflict_count: int = 0
    rejected_count: int = 0
    gap_count: int = 0
    accepted_through: datetime | None = None
    source_fingerprint: str | None = None
    verified_from_store: bool = False
    failure_kind: EvidenceRefreshFailureKind | None = None
    error_summary: str | None = None
    warnings: tuple[str, ...] = ()
    source_references: tuple[str, ...] = ()
    findings: tuple[tuple[ReconciliationStatus, str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("Refresh outcome provider is required.")
        for field in ("discovered_count", "accepted_count", "duplicate_count", "conflict_count", "rejected_count", "gap_count"):
            _non_negative(getattr(self, field), field)
        if self.accepted_through is not None:
            _aware(self.accepted_through, "accepted_through")
        if self.status in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, EvidenceRefreshStatus.INVALID_EVIDENCE} and not self.error_summary:
            raise ValueError("Failed refresh outcomes require a safe error summary.")
        if self.failure_kind is EvidenceRefreshFailureKind.TRANSIENT and self.status not in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE}:
            raise ValueError("Transient failures must have a failed operational outcome.")
        if tuple(sorted(set(self.warnings))) != self.warnings:
            raise ValueError("Outcome warnings must be canonical.")
        if tuple(sorted(set(self.source_references))) != self.source_references:
            raise ValueError("Outcome source references must be canonical.")


@dataclass(frozen=True, slots=True)
class DataOperationsFamilyHealth:
    family: EvidenceDataFamily
    status: DataOperationsHealthStatus
    last_run: EvidenceRefreshRun | None
    next_due_at: datetime | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataOperationsHealth:
    families: tuple[DataOperationsFamilyHealth, ...]
    generated_at: datetime

    def __post_init__(self) -> None:
        _aware(self.generated_at, "generated_at")
        if tuple(item.family for item in self.families) != tuple(EvidenceDataFamily):
            raise ValueError("Operational health families must be ordered.")
