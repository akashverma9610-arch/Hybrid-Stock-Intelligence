"""Immutable, non-secret data-source readiness records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum


class DataFamily(StrEnum):
    CURRENT_QUOTES = "CURRENT_QUOTES"
    STREAMING_QUOTES = "STREAMING_QUOTES"
    HISTORICAL_OHLCV = "HISTORICAL_OHLCV"
    INDEX_DATA = "INDEX_DATA"
    VIX = "VIX"
    UNIVERSE_MEMBERSHIP = "UNIVERSE_MEMBERSHIP"
    FUNDAMENTALS = "FUNDAMENTALS"
    CORPORATE_FILINGS = "CORPORATE_FILINGS"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    NEWS_RESEARCH = "NEWS_RESEARCH"
    IPO_PRIMARY_MARKET = "IPO_PRIMARY_MARKET"


class SourceReadinessStatus(StrEnum):
    READY = "READY"
    CONFIGURED_NOT_VALIDATED = "CONFIGURED_NOT_VALIDATED"
    MISSING_CONFIGURATION = "MISSING_CONFIGURATION"
    UNSUPPORTED = "UNSUPPORTED"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class DataRequirement(StrEnum):
    CRITICAL = "CRITICAL"
    OPTIONAL = "OPTIONAL"


class PointInTimeCapability(StrEnum):
    SUPPORTED = "SUPPORTED"
    LIMITED = "LIMITED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class AdjustmentCapability(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


class FreshnessBasis(StrEnum):
    WALL_CLOCK = "WALL_CLOCK"
    COMPLETED_SESSION = "COMPLETED_SESSION"
    PUBLICATION_EVENT = "PUBLICATION_EVENT"
    EFFECTIVE_EVENT = "EFFECTIVE_EVENT"


class FundamentalFactKind(StrEnum):
    REPORTED = "REPORTED"
    GUIDANCE = "GUIDANCE"
    CONSENSUS_ESTIMATE = "CONSENSUS_ESTIMATE"
    DERIVED = "DERIVED"


@dataclass(frozen=True, slots=True)
class DataFreshnessPolicy:
    family: DataFamily
    basis: FreshnessBasis
    maximum_age: timedelta | None
    policy_version: str = "data-source-freshness-v1"


@dataclass(frozen=True, slots=True)
class SourceRecordProvenance:
    source_id: str
    provider: str
    source_reference: str | None
    observed_at: datetime | None
    published_at: datetime | None
    received_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    family: DataFamily
    schema_version: str
    normalization_version: str


@dataclass(frozen=True, slots=True)
class SourceCapability:
    family: DataFamily
    point_in_time: PointInTimeCapability
    adjustment: AdjustmentCapability
    freshness_policy: DataFreshnessPolicy
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataSourceDefinition:
    source_id: str
    provider: str
    display_name: str
    capabilities: tuple[SourceCapability, ...]
    provenance: SourceRecordProvenance

    def capability_for(self, family: DataFamily) -> SourceCapability | None:
        return next((value for value in self.capabilities if value.family is family), None)


@dataclass(frozen=True, slots=True)
class SourceValidationState:
    configured: bool
    validated: bool = False
    degraded: bool = False
    unavailable: bool = False
    last_success_at: datetime | None = None
    last_failure_classification: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataSourceReadiness:
    source_id: str | None
    provider: str | None
    family: DataFamily
    requirement: DataRequirement
    priority: int | None
    status: SourceReadinessStatus
    configured: bool
    validated: bool
    last_success_at: datetime | None
    last_failure_classification: str | None
    freshness_policy: DataFreshnessPolicy
    point_in_time: PointInTimeCapability
    adjustment: AdjustmentCapability
    warnings: tuple[str, ...]
    provenance: SourceRecordProvenance | None


@dataclass(frozen=True, slots=True)
class DataSourceReadinessReport:
    generated_at: datetime
    mode: str
    items: tuple[DataSourceReadiness, ...]
    warnings: tuple[str, ...] = ()

    def for_family(self, family: DataFamily) -> tuple[DataSourceReadiness, ...]:
        return tuple(item for item in self.items if item.family is family)

    def primary(self, family: DataFamily) -> DataSourceReadiness | None:
        values = self.for_family(family)
        return min(values, key=lambda item: item.priority if item.priority is not None else 10_000) if values else None


@dataclass(frozen=True, slots=True)
class RuntimeSourceReadiness:
    mode: str
    executable: bool
    critical_unavailable: tuple[DataFamily, ...]
    optional_unavailable: tuple[DataFamily, ...]
    report: DataSourceReadinessReport
    warnings: tuple[str, ...] = ()
