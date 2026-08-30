"""Coverage/readiness facts, intentionally separate from stock attractiveness."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DataCoverageDomain(StrEnum):
    IDENTITY="IDENTITY"; SECTOR_INDUSTRY="SECTOR_INDUSTRY"; CURRENT_QUOTES="CURRENT_QUOTES"; HISTORICAL_OHLCV="HISTORICAL_OHLCV"; HISTORICAL_MEMBERSHIP="HISTORICAL_MEMBERSHIP"; SYMBOL_HISTORY="SYMBOL_HISTORY"; CORPORATE_ACTIONS="CORPORATE_ACTIONS"; PRICE_ADJUSTMENT_INTEGRITY="PRICE_ADJUSTMENT_INTEGRITY"; FUNDAMENTALS="FUNDAMENTALS"; FILINGS="FILINGS"; OWNERSHIP="OWNERSHIP"; PROMOTER_PLEDGE="PROMOTER_PLEDGE"; DELIVERY_DATA="DELIVERY_DATA"; NEWS="NEWS"; CATALYSTS="CATALYSTS"; MARKET_CONTEXT="MARKET_CONTEXT"; SECTOR_CONTEXT="SECTOR_CONTEXT"; MACRO_CONTEXT="MACRO_CONTEXT"; COMPANY_SENSITIVITY="COMPANY_SENSITIVITY"


class DataCoverageStatus(StrEnum):
    READY="READY"; PARTIAL="PARTIAL"; MISSING="MISSING"; STALE="STALE"; CONFLICTED="CONFLICTED"; UNAVAILABLE="UNAVAILABLE"


class DeepAnalysisReadiness(StrEnum):
    DEEP_ANALYSIS_READY="DEEP_ANALYSIS_READY"; DEEP_ANALYSIS_PARTIAL="DEEP_ANALYSIS_PARTIAL"; DEEP_ANALYSIS_UNAVAILABLE="DEEP_ANALYSIS_UNAVAILABLE"


class StrategyCoverageReadiness(StrEnum):
    READY="READY"; PARTIAL="PARTIAL"; UNAVAILABLE="UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DomainCoverage:
    domain: DataCoverageDomain
    status: DataCoverageStatus
    data_as_of: datetime | None
    evidence_ids: tuple[str, ...] = ()
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class DataCoverageRecord:
    coverage_id: str
    universe_snapshot_id: str
    instrument_id: str
    as_of: datetime
    domains: tuple[DomainCoverage, ...]
    deep_analysis: DeepAnalysisReadiness
    pre_breakout: StrategyCoverageReadiness
    inflection: StrategyCoverageReadiness
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DomainCoverageSummary:
    domain: DataCoverageDomain
    total: int
    ready: int
    partial: int
    missing: int
    stale: int
    conflicted: int
    unavailable: int

    @property
    def ready_percent(self) -> float:
        return round((self.ready * 100 / self.total), 2) if self.total else 0.0


@dataclass(frozen=True, slots=True)
class CoverageGap:
    domain: DataCoverageDomain
    affected_instrument_count: int
    coverage_percentage: float
    downstream_engines_blocked: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DataCoverageSummary:
    summary_id: str
    universe_snapshot_id: str
    as_of: datetime
    total_instruments: int
    domains: tuple[DomainCoverageSummary, ...]
    deep_ready: int
    deep_partial: int
    deep_unavailable: int
    pre_breakout_ready: int
    inflection_ready: int
    gaps: tuple[CoverageGap, ...]
    warnings: tuple[str, ...] = ()
