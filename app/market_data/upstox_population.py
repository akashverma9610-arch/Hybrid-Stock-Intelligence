"""Explicit bounded Upstox historical population for the frozen real-Brain cohort.

This is an operator-invoked ingestion boundary, not a diagnostic dependency.
It maps only supplied canonical identities, persists immutable provider
mappings, and writes canonical daily bars through HistoricalIngestionService.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Callable, Sequence

from app.market_data.historical import HistoricalIngestionReport, HistoricalIngestionService
from app.market_data.models import (
    AdjustmentStatus, Exchange, HistoricalBarsRequest, InstrumentIdentity,
    InstrumentType, ProviderInstrumentMapping, Timeframe,
)
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider, UpstoxInstrumentRecord
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


NIFTY_500_INSTRUMENT_ID = "NIFTY_500"
NIFTY_500_SYMBOL = "NIFTY 500"


@dataclass(frozen=True, slots=True)
class UpstoxMappingOutcome:
    instrument_id: str
    symbol: str
    status: str
    method: str | None
    provider_reference: str | None


@dataclass(frozen=True, slots=True)
class UpstoxPopulationReport:
    requested: int
    matched: int
    ambiguous: int
    unmatched: int
    benchmark_status: str
    mapped_records: int
    symbols_ingested: int
    sufficient_252: int
    bars_stored: int
    average_bars_per_symbol: float
    provider_requests: int
    failures: tuple[str, ...]
    adjustment_status: AdjustmentStatus
    quality_warnings: tuple[str, ...]
    runtime_milliseconds: int
    mapping_outcomes: tuple[UpstoxMappingOutcome, ...]
    reports: tuple[HistoricalIngestionReport, ...]


class FrozenUpstoxPopulationService:
    """Populate only one frozen cohort and its exact NIFTY 500 benchmark."""

    def __init__(
        self,
        *,
        universe_store: CoreUniverseAnalysisStore,
        historical_store,
        provider_factory: Callable[[str], UpstoxHistoricalProvider] = UpstoxHistoricalProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._universe, self._historical, self._provider_factory, self._clock = (
            universe_store, historical_store, provider_factory, clock,
        )

    def populate(
        self,
        *,
        cohort: Sequence[NseEquityInstrument],
        master_records: Sequence[UpstoxInstrumentRecord],
        master_source_reference: str | None = None,
        master_checksum: str | None = None,
        access_token: str | None,
        years: int = 3,
    ) -> UpstoxPopulationReport:
        if len(cohort) != 40 or len({item.instrument_id for item in cohort}) != 40:
            raise ValueError("Frozen Upstox population requires exactly 40 unique cohort instruments.")
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN_REQUIRED")
        if years < 1 or years > 3:
            raise ValueError("Upstox frozen-cohort history must request between one and three years.")

        started = perf_counter()
        now = self._clock().astimezone(UTC)
        start = now - timedelta(days=366 * years)
        provider = self._provider_factory(access_token)
        outcomes: list[UpstoxMappingOutcome] = []
        reports: list[HistoricalIngestionReport] = []
        failures: list[str] = []
        quality_warnings: set[str] = set()
        mapped_records = requests = 0

        mapped: list[InstrumentIdentity] = []
        for item in cohort:
            identity = _equity_identity(item)
            mapping, status, method = resolve_upstox_equity_mapping(identity, master_records)
            if mapping is None:
                outcomes.append(UpstoxMappingOutcome(item.instrument_id, item.symbol, status, None, None))
                continue
            mapped_identity = _with_mapping(identity, mapping)
            if self._persist_mapping(
                mapped_identity, now, source_reference=master_source_reference,
                source_checksum=master_checksum,
            ):
                mapped_records += 1
            outcomes.append(UpstoxMappingOutcome(item.instrument_id, item.symbol, "MATCHED", method, mapping.provider_instrument_reference))
            mapped.append(mapped_identity)

        benchmark = _nifty_500_identity()
        benchmark_mapping = resolve_upstox_nifty_500_mapping(benchmark, master_records)
        benchmark_status = "NIFTY500_MAPPING_UNAVAILABLE"
        if benchmark_mapping is not None:
            benchmark = _with_mapping(benchmark, benchmark_mapping)
            if self._persist_mapping(
                benchmark, now, source_reference=master_source_reference,
                source_checksum=master_checksum,
            ):
                mapped_records += 1
            benchmark_status = "MATCHED"
            mapped.append(benchmark)

        for identity in mapped:
            requests += 1
            request = HistoricalBarsRequest(
                identity, Timeframe.DAILY, start, now,
                AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER,
            )
            report = HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(request)
            reports.append(report)
            quality_warnings.update(report.warnings)
            if report.coverage.value == "UNAVAILABLE":
                failures.append(f"{identity.symbol}:{','.join(report.warnings) or 'HISTORY_UNAVAILABLE'}")

        # This is deliberately a warning, not an adjustment or a rejection:
        # the V3 contract's corporate-action basis is still UNKNOWN.  It
        # surfaces discontinuities for later corporate-action review without
        # manufacturing adjusted prices or treating a legitimate split as bad
        # data.
        for identity in mapped:
            bars = self._historical.latest(identity.instrument_id, Timeframe.DAILY, 800)
            for previous, current in zip(bars, bars[1:]):
                if previous.close > 0 and abs(current.close - previous.close) / previous.close >= 0.75:
                    quality_warnings.add(f"POSSIBLE_EXTREME_PRICE_DISCONTINUITY:{identity.instrument_id}")
                    break

        equities = tuple(item for item in mapped if item.instrument_id != NIFTY_500_INSTRUMENT_ID)
        sufficient = sum(
            self._historical.count(item.instrument_id, Timeframe.DAILY) >= 252
            for item in equities
        )
        bars = sum(self._historical.count(item.instrument_id, Timeframe.DAILY) for item in mapped)
        matched = sum(item.status == "MATCHED" for item in outcomes)
        ambiguous = sum(item.status == "AMBIGUOUS" for item in outcomes)
        return UpstoxPopulationReport(
            requested=len(cohort), matched=matched, ambiguous=ambiguous,
            unmatched=len(cohort) - matched - ambiguous, benchmark_status=benchmark_status,
            mapped_records=mapped_records,
            symbols_ingested=sum(report.accepted_count > 0 or self._historical.count(report.instrument_id, Timeframe.DAILY) > 0 for report in reports if report.instrument_id != NIFTY_500_INSTRUMENT_ID),
            sufficient_252=sufficient, bars_stored=bars,
            average_bars_per_symbol=(bars / len(mapped)) if mapped else 0.0,
            provider_requests=requests, failures=tuple(sorted(failures)),
            adjustment_status=AdjustmentStatus.UNKNOWN,
            quality_warnings=tuple(sorted(quality_warnings)),
            runtime_milliseconds=int((perf_counter() - started) * 1000),
            mapping_outcomes=tuple(outcomes), reports=tuple(reports),
        )

    def _persist_mapping(
        self,
        identity: InstrumentIdentity,
        at: datetime,
        *,
        source_reference: str | None,
        source_checksum: str | None,
    ) -> bool:
        mapped = identity.provider_mappings[0]
        existing = self._universe.provider_mapping(
            canonical_instrument_id=identity.instrument_id, provider=UPSTOX_PROVIDER, as_of=at,
        )
        if existing and existing.provider_instrument_reference == mapped.provider_instrument_reference:
            return False
        self._universe.capture_provider_mapping(
            identity, provider=UPSTOX_PROVIDER, effective_as_of=at,
            source_reference=source_reference or "upstox-nse-bod-json",
            source_checksum=source_checksum,
        )
        return True


def resolve_upstox_equity_mapping(
    identity: InstrumentIdentity,
    records: Sequence[UpstoxInstrumentRecord],
) -> tuple[ProviderInstrumentMapping | None, str, str | None]:
    """Exact ISIN first; exact unambiguous NSE cash symbol is a controlled fallback."""
    if identity.instrument_type is not InstrumentType.NSE_EQUITY:
        return None, "UNSUPPORTED", None
    isin = identity.isin.upper() if identity.isin else None
    isin_matches = tuple(item for item in records if item.segment == "NSE_EQ" and isin and item.isin and item.isin.upper() == isin)
    if len(isin_matches) == 1:
        return _provider_mapping(isin_matches[0]), "MATCHED", "EXACT_ISIN_NSE_CASH"
    if len(isin_matches) > 1:
        return None, "AMBIGUOUS", None
    symbol = (identity.trading_symbol or identity.symbol).strip().upper()
    symbol_matches = tuple(
        item for item in records
        if item.segment == "NSE_EQ"
        and (item.trading_symbol or "").strip().upper() == symbol
        and (item.instrument_type or "").upper() in {"EQ", "BE"}
    )
    if len(symbol_matches) == 1:
        return _provider_mapping(symbol_matches[0]), "MATCHED", "EXACT_SYMBOL_NSE_CASH"
    return None, "AMBIGUOUS" if len(symbol_matches) > 1 else "UNMATCHED", None


def resolve_upstox_nifty_500_mapping(
    identity: InstrumentIdentity,
    records: Sequence[UpstoxInstrumentRecord],
) -> ProviderInstrumentMapping | None:
    candidates = tuple(
        item for item in records
        if item.segment == "NSE_INDEX" and (item.instrument_type or "").upper() == "INDEX"
        and (item.trading_symbol or "").strip().upper() == NIFTY_500_SYMBOL
    )
    return _provider_mapping(candidates[0]) if len(candidates) == 1 else None


def _equity_identity(item: NseEquityInstrument) -> InstrumentIdentity:
    return InstrumentIdentity(
        item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin,
        None, InstrumentType.NSE_EQUITY, item.company_name,
    )


def _nifty_500_identity() -> InstrumentIdentity:
    return InstrumentIdentity(
        NIFTY_500_INSTRUMENT_ID, Exchange.INDEX, NIFTY_500_SYMBOL,
        NIFTY_500_SYMBOL, None, None, InstrumentType.BROAD_INDEX, NIFTY_500_SYMBOL,
    )


def _provider_mapping(record: UpstoxInstrumentRecord) -> ProviderInstrumentMapping:
    return ProviderInstrumentMapping(
        UPSTOX_PROVIDER, record.instrument_key, record.trading_symbol,
        "upstox-v3", record.segment,
    )


def _with_mapping(identity: InstrumentIdentity, mapping: ProviderInstrumentMapping) -> InstrumentIdentity:
    return InstrumentIdentity(
        identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol,
        identity.isin, identity.series, identity.instrument_type, identity.name,
        identity.currency, (mapping,),
    )


__all__ = (
    "FrozenUpstoxPopulationService", "NIFTY_500_INSTRUMENT_ID", "NIFTY_500_SYMBOL",
    "UpstoxMappingOutcome", "UpstoxPopulationReport", "resolve_upstox_equity_mapping",
    "resolve_upstox_nifty_500_mapping",
)
