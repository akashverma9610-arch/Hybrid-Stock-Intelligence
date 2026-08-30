"""Deterministic aggregation of observed coverage; it never fetches or fills data."""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from app.data_coverage.models import (
    CoverageGap, DataCoverageDomain, DataCoverageRecord, DataCoverageStatus,
    DataCoverageSummary, DeepAnalysisReadiness, DomainCoverage,
    DomainCoverageSummary, StrategyCoverageReadiness,
)


_DEEP_REQUIRED = (DataCoverageDomain.IDENTITY, DataCoverageDomain.SECTOR_INDUSTRY, DataCoverageDomain.CURRENT_QUOTES, DataCoverageDomain.HISTORICAL_OHLCV, DataCoverageDomain.HISTORICAL_MEMBERSHIP, DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY, DataCoverageDomain.FUNDAMENTALS, DataCoverageDomain.FILINGS, DataCoverageDomain.OWNERSHIP, DataCoverageDomain.MARKET_CONTEXT, DataCoverageDomain.SECTOR_CONTEXT)
_PRE_REQUIRED = (DataCoverageDomain.SECTOR_INDUSTRY, DataCoverageDomain.CURRENT_QUOTES, DataCoverageDomain.HISTORICAL_OHLCV, DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY, DataCoverageDomain.DELIVERY_DATA, DataCoverageDomain.SECTOR_CONTEXT)
_INFLECTION_REQUIRED = (DataCoverageDomain.SECTOR_INDUSTRY, DataCoverageDomain.FUNDAMENTALS, DataCoverageDomain.OWNERSHIP, DataCoverageDomain.PROMOTER_PLEDGE, DataCoverageDomain.MACRO_CONTEXT, DataCoverageDomain.SECTOR_CONTEXT, DataCoverageDomain.COMPANY_SENSITIVITY)


class DataCoverageService:
    def record(self, *, universe_snapshot_id: str, instrument_id: str, as_of: datetime, domains: tuple[DomainCoverage, ...]) -> DataCoverageRecord:
        by_domain = {item.domain: item for item in domains}
        normalized = tuple(by_domain.get(domain, DomainCoverage(domain, DataCoverageStatus.MISSING, None, (), "NO_CANONICAL_EVIDENCE")) for domain in DataCoverageDomain)
        return DataCoverageRecord(
            "coverage-" + sha256(f"{universe_snapshot_id}|{instrument_id}|{as_of.isoformat()}|{normalized}".encode()).hexdigest()[:20],
            universe_snapshot_id, instrument_id, as_of, normalized,
            _readiness(normalized, _DEEP_REQUIRED), _strategy_readiness(normalized, _PRE_REQUIRED), _strategy_readiness(normalized, _INFLECTION_REQUIRED),
            tuple(sorted(item.warning for item in normalized if item.warning)),
        )

    def summarize(self, *, universe_snapshot_id: str, as_of: datetime, records: tuple[DataCoverageRecord, ...]) -> DataCoverageSummary:
        summaries = []
        for domain in DataCoverageDomain:
            counts = {status: 0 for status in DataCoverageStatus}
            for record in records:
                status = next(item.status for item in record.domains if item.domain is domain); counts[status] += 1
            summaries.append(DomainCoverageSummary(domain, len(records), counts[DataCoverageStatus.READY], counts[DataCoverageStatus.PARTIAL], counts[DataCoverageStatus.MISSING], counts[DataCoverageStatus.STALE], counts[DataCoverageStatus.CONFLICTED], counts[DataCoverageStatus.UNAVAILABLE]))
        gaps = tuple(sorted((_gap(item) for item in summaries if item.ready < item.total), key=lambda item: (-item.affected_instrument_count, item.domain.value)))
        return DataCoverageSummary(
            "coverage-summary-" + sha256(f"{universe_snapshot_id}|{as_of.isoformat()}|{records}".encode()).hexdigest()[:20], universe_snapshot_id, as_of, len(records), tuple(summaries),
            sum(item.deep_analysis is DeepAnalysisReadiness.DEEP_ANALYSIS_READY for item in records), sum(item.deep_analysis is DeepAnalysisReadiness.DEEP_ANALYSIS_PARTIAL for item in records), sum(item.deep_analysis is DeepAnalysisReadiness.DEEP_ANALYSIS_UNAVAILABLE for item in records),
            sum(item.pre_breakout is StrategyCoverageReadiness.READY for item in records), sum(item.inflection is StrategyCoverageReadiness.READY for item in records), gaps,
            ("TAXONOMY_SOURCE_REQUIRED",) if any(item.domain is DataCoverageDomain.SECTOR_INDUSTRY and item.ready == 0 for item in summaries) else (),
        )


def _readiness(domains: tuple[DomainCoverage, ...], required: tuple[DataCoverageDomain, ...]) -> DeepAnalysisReadiness:
    statuses = {item.domain: item.status for item in domains}
    values = tuple(statuses[item] for item in required)
    if all(item is DataCoverageStatus.READY for item in values): return DeepAnalysisReadiness.DEEP_ANALYSIS_READY
    if any(item in {DataCoverageStatus.READY, DataCoverageStatus.PARTIAL, DataCoverageStatus.STALE} for item in values): return DeepAnalysisReadiness.DEEP_ANALYSIS_PARTIAL
    return DeepAnalysisReadiness.DEEP_ANALYSIS_UNAVAILABLE


def _strategy_readiness(domains: tuple[DomainCoverage, ...], required: tuple[DataCoverageDomain, ...]) -> StrategyCoverageReadiness:
    statuses = {item.domain: item.status for item in domains}; values = tuple(statuses[item] for item in required)
    if all(item is DataCoverageStatus.READY for item in values): return StrategyCoverageReadiness.READY
    if any(item in {DataCoverageStatus.READY, DataCoverageStatus.PARTIAL, DataCoverageStatus.STALE} for item in values): return StrategyCoverageReadiness.PARTIAL
    return StrategyCoverageReadiness.UNAVAILABLE


def _gap(value: DomainCoverageSummary) -> CoverageGap:
    blocked = {
        DataCoverageDomain.DELIVERY_DATA: ("PRE_BREAKOUT", "VOLUME_QUALITY_DIAGNOSTICS"),
        DataCoverageDomain.SECTOR_INDUSTRY: ("SECTOR_CONTEXT", "PRE_BREAKOUT", "INFLECTION"),
        DataCoverageDomain.HISTORICAL_OHLCV: ("TECHNICAL_DIAGNOSTICS", "PRE_BREAKOUT"),
        DataCoverageDomain.HISTORICAL_MEMBERSHIP: ("HISTORICAL_BACKTEST", "BENCHMARKS"),
        DataCoverageDomain.SYMBOL_HISTORY: ("HISTORICAL_IDENTITY", "HISTORICAL_BARS"),
        DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY: ("TECHNICAL_DIAGNOSTICS", "PRE_BREAKOUT", "HISTORICAL_BACKTEST"),
        DataCoverageDomain.FUNDAMENTALS: ("FUNDAMENTAL_DIAGNOSTICS", "INFLECTION"),
        DataCoverageDomain.OWNERSHIP: ("OWNERSHIP_DIAGNOSTICS", "INFLECTION"),
        DataCoverageDomain.PROMOTER_PLEDGE: ("INFLECTION",),
    }.get(value.domain, ("DEEP_ANALYSIS",))
    return CoverageGap(value.domain, value.total - value.ready, value.ready_percent, blocked)
