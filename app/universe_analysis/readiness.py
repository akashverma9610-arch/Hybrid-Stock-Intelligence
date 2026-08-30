"""Stored-data readiness accounting for controlled NSE universe work.

The module is intentionally observational.  It never opens a provider
connection, imports a universe, runs diagnostics, or changes strategy state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from time import perf_counter
from typing import Mapping, Protocol

from app.data_sources.models import DataFamily, DataSourceReadinessReport, SourceReadinessStatus
from app.market_data.historical import HistoricalBarStore
from app.market_data.models import FreshnessState, Timeframe

from .models import CoverageDomain, CoverageDomainStatus, NseEquityInstrument, UniverseInstrumentCoverage, UniverseSnapshot
from .requirements import DIAGNOSTIC_INPUT_REQUIREMENTS


class ProviderMappingStatus(StrEnum):
    MATCHED = "MATCHED"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"
    UNSUPPORTED = "UNSUPPORTED"


class FullScanStatus(StrEnum):
    READY_FOR_FULL_SCAN = "READY_FOR_FULL_SCAN"
    NOT_READY_FOR_FULL_SCAN = "NOT_READY_FOR_FULL_SCAN"


@dataclass(frozen=True, slots=True)
class ProviderMappingReadiness:
    instrument_id: str
    provider: str
    status: ProviderMappingStatus
    reference: str | None = None


@dataclass(frozen=True, slots=True)
class DomainCoverageSummary:
    domain: CoverageDomain
    ready: int
    partial: int
    missing: int
    unavailable: int
    stale: int
    total: int

    @property
    def ready_percent(self) -> float:
        return 0.0 if self.total == 0 else round((self.ready * 100) / self.total, 2)


@dataclass(frozen=True, slots=True)
class HistoricalCoverageSummary:
    enough_lookback: int
    partial_lookback: int
    missing: int
    gaps: int
    latest_bar_at: datetime | None
    minimum_lookback: int


@dataclass(frozen=True, slots=True)
class FullScanReadinessDecision:
    status: FullScanStatus
    blockers: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DataReadinessReport:
    generated_at: datetime
    universe_snapshot_id: str | None
    universe_total: int
    eligible_equities: int
    excluded: int
    provider_statuses: tuple[tuple[str, SourceReadinessStatus], ...]
    mapping_statuses: tuple[ProviderMappingReadiness, ...]
    coverage: tuple[DomainCoverageSummary, ...]
    historical: HistoricalCoverageSummary
    full_scan: FullScanReadinessDecision
    warnings: tuple[str, ...] = ()


class CoverageStore(Protocol):
    def coverage(self, job_id: str) -> tuple[UniverseInstrumentCoverage, ...]: ...


class QuoteCoverageStore(Protocol):
    def latest_quote(self, instrument_id: str): ...


class DataReadinessService:
    """Aggregates existing canonical evidence without fabricating availability."""

    def __init__(self, *, historical_bars: HistoricalBarStore | None = None,
                 source_report: DataSourceReadinessReport | None = None,
                 mapping_registry: Mapping[tuple[str, str], ProviderMappingReadiness] | None = None,
                 quote_store: QuoteCoverageStore | None = None,
                 clock=lambda: datetime.now(UTC)) -> None:
        self._historical = historical_bars
        self._sources = source_report
        self._mappings = dict(mapping_registry or {})
        self._quotes = quote_store
        self._clock = clock

    def assess(self, *, snapshot: UniverseSnapshot | None,
               instruments: tuple[NseEquityInstrument, ...], as_of: datetime,
               coverage_records: tuple[UniverseInstrumentCoverage, ...] = ()) -> DataReadinessReport:
        selected = () if snapshot is None else tuple(
            item for item in instruments if item.instrument_id in set(snapshot.instrument_ids)
        )
        mapping = self._mapping_readiness(selected)
        coverage = _aggregate_coverage(selected, coverage_records, self._quotes)
        historical = self._historical_coverage(selected, as_of)
        sources = _provider_statuses(self._sources)
        decision = _full_scan_decision(snapshot, selected, mapping, historical, coverage, sources)
        warnings = (() if snapshot else ("UNIVERSE_SNAPSHOT_MISSING",)) + (
            ("MAPPING_SOURCE_UNAVAILABLE",) if selected and not self._mappings else ()
        )
        return DataReadinessReport(
            self._clock(), snapshot.snapshot_id if snapshot else None,
            snapshot.total_records if snapshot else 0,
            snapshot.eligible_security_count if snapshot else 0,
            snapshot.excluded_count if snapshot else 0,
            sources, mapping, coverage, historical, decision, warnings,
        )

    def deterministic_sample(self, *, snapshot: UniverseSnapshot, instruments: tuple[NseEquityInstrument, ...], limit: int) -> tuple[NseEquityInstrument, ...]:
        if limit < 1:
            raise ValueError("Sample limit must be positive.")
        allowed = set(snapshot.instrument_ids)
        return tuple(sorted((item for item in instruments if item.instrument_id in allowed), key=lambda item: item.instrument_id)[:limit])

    def _mapping_readiness(self, instruments: tuple[NseEquityInstrument, ...]) -> tuple[ProviderMappingReadiness, ...]:
        providers = ("kotak_neo", "global_datafeeds", "upstox", "fundamentals", "filings", "gnews")
        return tuple(
            self._mappings.get((instrument.instrument_id, provider), ProviderMappingReadiness(instrument.instrument_id, provider, ProviderMappingStatus.UNMATCHED))
            for instrument in instruments for provider in providers
        )

    def _historical_coverage(self, instruments: tuple[NseEquityInstrument, ...], as_of: datetime) -> HistoricalCoverageSummary:
        minimum = max((item.minimum_lookback or 0 for item in DIAGNOSTIC_INPUT_REQUIREMENTS if item.technical_dependency), default=0)
        if self._historical is None:
            return HistoricalCoverageSummary(0, 0, len(instruments), 0, None, minimum)
        enough = partial = missing = gaps = 0
        latest: datetime | None = None
        start = as_of - timedelta(days=max(30, minimum * 3))
        for instrument in instruments:
            bars = self._historical.latest(instrument.instrument_id, Timeframe.DAILY, minimum, as_of=as_of)
            if len(bars) >= minimum:
                enough += 1
            elif bars:
                partial += 1
            else:
                missing += 1
            if bars:
                latest = max(latest, bars[-1].end_time) if latest else bars[-1].end_time
                if self._historical.coverage(instrument.instrument_id, Timeframe.DAILY, start, as_of, as_of=as_of).warnings:
                    gaps += 1
        return HistoricalCoverageSummary(enough, partial, missing, gaps, latest, minimum)


def _provider_statuses(report: DataSourceReadinessReport | None) -> tuple[tuple[str, SourceReadinessStatus], ...]:
    if report is None:
        return tuple((name, SourceReadinessStatus.MISSING_CONFIGURATION) for name in ("kotak_neo", "global_datafeeds", "upstox", "nse_official_local", "gnews", "database", "stored_data"))
    by_provider: dict[str, SourceReadinessStatus] = {
        "kotak_neo": SourceReadinessStatus.MISSING_CONFIGURATION,
        "global_datafeeds": SourceReadinessStatus.MISSING_CONFIGURATION,
        "upstox": SourceReadinessStatus.MISSING_CONFIGURATION,
        "nse_official_local": SourceReadinessStatus.MISSING_CONFIGURATION,
        "gnews": SourceReadinessStatus.MISSING_CONFIGURATION,
        "stored_data": SourceReadinessStatus.MISSING_CONFIGURATION,
    }
    for item in report.items:
        provider = "nse_official_local" if item.provider == "nse" else item.provider
        if provider is None:
            continue
        current = by_provider.get(provider)
        # The first priority item for a provider is the declared status; do not
        # turn a configured-but-unvalidated source into READY.
        if current in {None, SourceReadinessStatus.MISSING_CONFIGURATION} or item.status is SourceReadinessStatus.READY:
            by_provider[provider] = item.status
    return tuple(sorted(by_provider.items()))


def _aggregate_coverage(instruments: tuple[NseEquityInstrument, ...], records: tuple[UniverseInstrumentCoverage, ...], quote_store: QuoteCoverageStore | None = None) -> tuple[DomainCoverageSummary, ...]:
    latest: dict[str, UniverseInstrumentCoverage] = {}
    for value in records:
        latest[value.instrument_id] = value
    result: list[DomainCoverageSummary] = []
    for domain in CoverageDomain:
        counts = {status: 0 for status in CoverageDomainStatus}
        for instrument in instruments:
            if domain is CoverageDomain.CURRENT_QUOTES and quote_store is not None:
                quote = quote_store.latest_quote(instrument.instrument_id)
                if quote is not None:
                    counts[CoverageDomainStatus.READY if quote.freshness.state is FreshnessState.FRESH else CoverageDomainStatus.STALE] += 1
                    continue
            record = latest.get(instrument.instrument_id)
            item = next((item for item in record.domains if item.domain is domain), None) if record else None
            counts[item.status if item else CoverageDomainStatus.MISSING] += 1
        result.append(DomainCoverageSummary(domain, counts[CoverageDomainStatus.READY], counts[CoverageDomainStatus.PARTIAL], counts[CoverageDomainStatus.MISSING], counts[CoverageDomainStatus.UNAVAILABLE], counts[CoverageDomainStatus.STALE], len(instruments)))
    return tuple(result)


def _full_scan_decision(snapshot: UniverseSnapshot | None, instruments: tuple[NseEquityInstrument, ...], mappings: tuple[ProviderMappingReadiness, ...], historical: HistoricalCoverageSummary, coverage: tuple[DomainCoverageSummary, ...], sources: tuple[tuple[str, SourceReadinessStatus], ...]) -> FullScanReadinessDecision:
    blockers: list[str] = []
    if snapshot is None or not instruments:
        blockers.append("UNIVERSE_INCOMPLETE")
    if any(item.status in {ProviderMappingStatus.AMBIGUOUS, ProviderMappingStatus.UNMATCHED} for item in mappings):
        blockers.append("SYMBOL_MAPPING_LOW")
    if historical.missing or historical.partial_lookback:
        blockers.append("HISTORICAL_COVERAGE_LOW")
    if any(item.domain is CoverageDomain.FUNDAMENTALS and item.ready < item.total for item in coverage):
        blockers.append("FUNDAMENTALS_COVERAGE_LOW")
    if any(item.domain is CoverageDomain.OWNERSHIP and item.ready < item.total for item in coverage):
        blockers.append("OWNERSHIP_GAP")
    if any(item.domain is CoverageDomain.MARKET_CONTEXT and item.stale for item in coverage):
        blockers.append("MARKET_CONTEXT_STALE")
    if any(status in {SourceReadinessStatus.MISSING_CONFIGURATION, SourceReadinessStatus.CONFIGURED_NOT_VALIDATED, SourceReadinessStatus.UNAVAILABLE} for _, status in sources):
        blockers.append("PROVIDER_UNVALIDATED")
    return FullScanReadinessDecision(FullScanStatus.NOT_READY_FOR_FULL_SCAN if blockers else FullScanStatus.READY_FOR_FULL_SCAN, tuple(sorted(set(blockers))))
