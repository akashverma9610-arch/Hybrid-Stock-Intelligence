"""Bounded yfinance research-history population for the frozen real-Brain cohort."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import perf_counter, sleep
from typing import Callable, Sequence

from app.market_data.historical import HistoricalIngestionReport, HistoricalIngestionService
from app.market_data.models import AdjustmentStatus, Exchange, HistoricalBarsRequest, InstrumentIdentity, InstrumentType, ProviderInstrumentMapping, Timeframe
from app.market_data.yfinance import YFINANCE_PROVIDER, YahooHistoricalDataProvider, yahoo_nifty500_candidate_mapping, yahoo_nse_mapping
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


NIFTY_500_INSTRUMENT_ID = "NIFTY_500"
NIFTY_500_SYMBOL = "NIFTY 500"


@dataclass(frozen=True, slots=True)
class YahooMappingOutcome:
    instrument_id: str
    symbol: str
    status: str
    method: str | None
    provider_reference: str | None


@dataclass(frozen=True, slots=True)
class YahooPopulationReport:
    requested: int
    mapped: int
    history_success: int
    history_failed: int
    sufficient_252: int
    gappy: int
    unavailable: int
    benchmark_status: str
    mapped_records: int
    symbols_ingested: int
    bars_stored: int
    provider_requests: int
    failures: tuple[str, ...]
    adjustment_status: AdjustmentStatus
    quality_warnings: tuple[str, ...]
    runtime_milliseconds: int
    mapping_outcomes: tuple[YahooMappingOutcome, ...]
    reports: tuple[HistoricalIngestionReport, ...]


@dataclass(frozen=True, slots=True)
class YahooOneStockValidation:
    canonical_symbol: str
    yahoo_symbol: str
    mapping_persisted: bool
    session_count: int
    report: HistoricalIngestionReport


class FrozenYahooPopulationService:
    """Populate only the frozen 40 plus an independently verified NIFTY 500."""

    def __init__(self, *, universe_store: CoreUniverseAnalysisStore, historical_store,
                 provider_factory: Callable[[], YahooHistoricalDataProvider] = YahooHistoricalDataProvider,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC), sleeper: Callable[[float], None] = sleep) -> None:
        self._universe, self._historical, self._provider_factory, self._clock, self._sleep = universe_store, historical_store, provider_factory, clock, sleeper

    def validate_one(self, *, cohort: Sequence[NseEquityInstrument], years: int = 3,
                     symbol: str | None = None) -> YahooOneStockValidation:
        """Perform exactly one bounded frozen-cohort history request."""
        if len(cohort) != 40 or len({item.instrument_id for item in cohort}) != 40:
            raise ValueError("Frozen yfinance validation requires exactly 40 unique cohort instruments.")
        if years < 1 or years > 3:
            raise ValueError("yfinance frozen-cohort history must request between one and three years.")
        choices = tuple(sorted(cohort, key=lambda item: item.symbol))
        selected = next((item for item in choices if item.symbol.upper() == symbol.strip().upper()), None) if symbol else choices[0]
        if selected is None:
            raise ValueError("YFINANCE_VALIDATION_SYMBOL_NOT_IN_FROZEN_COHORT")
        identity = _equity_identity(selected); mapping = yahoo_nse_mapping(identity)
        if mapping is None: raise ValueError("YFINANCE_NSE_MAPPING_UNAVAILABLE")
        now = self._clock().astimezone(UTC); identity = _with_mapping(identity, mapping)
        persisted = self._persist_mapping(identity, now)
        report = HistoricalIngestionService(self._provider_factory(), self._historical, clock=self._clock).ingest(
            HistoricalBarsRequest(identity, Timeframe.DAILY, now - timedelta(days=366 * years), now, AdjustmentStatus.RAW, YFINANCE_PROVIDER)
        )
        return YahooOneStockValidation(selected.symbol, mapping.provider_instrument_reference, persisted,
                                       self._historical.count(identity.instrument_id, Timeframe.DAILY), report)

    def populate(self, *, cohort: Sequence[NseEquityInstrument], years: int = 3,
                 include_verified_nifty500: bool = True) -> YahooPopulationReport:
        if len(cohort) != 40 or len({item.instrument_id for item in cohort}) != 40:
            raise ValueError("Frozen yfinance population requires exactly 40 unique cohort instruments.")
        if years < 1 or years > 3:
            raise ValueError("yfinance frozen-cohort history must request between one and three years.")
        started = perf_counter(); now = self._clock().astimezone(UTC); start = now - timedelta(days=366 * years)
        provider = self._provider_factory(); outcomes: list[YahooMappingOutcome] = []; reports: list[HistoricalIngestionReport] = []
        failures: list[str] = []; warnings: set[str] = set(); mapped: list[InstrumentIdentity] = []; mapped_records = 0
        for item in cohort:
            identity = _equity_identity(item); mapping = yahoo_nse_mapping(identity)
            if mapping is None:
                outcomes.append(YahooMappingOutcome(item.instrument_id, item.symbol, "UNMATCHED", None, None)); continue
            identity = _with_mapping(identity, mapping)
            if self._persist_mapping(identity, now): mapped_records += 1
            outcomes.append(YahooMappingOutcome(item.instrument_id, item.symbol, "MATCHED", "EXACT_NSE_SYMBOL_SUFFIX", mapping.provider_instrument_reference)); mapped.append(identity)
        benchmark_status = "NIFTY500_UNAVAILABLE"
        if include_verified_nifty500:
            candidate = _nifty500_identity(); benchmark_mapping = yahoo_nifty500_candidate_mapping(candidate)
            if benchmark_mapping is not None:
                # It remains unavailable if the historical response cannot
                # independently validate it as NIFTY 500.
                mapped.append(_with_mapping(candidate, benchmark_mapping)); benchmark_status = "NIFTY500_CANDIDATE_PENDING_VALIDATION"
        requests = 0
        for identity in mapped:
            requests += 1
            report = self._ingest_once(provider, identity, start, now)
            reports.append(report); warnings.update(report.warnings)
            if report.coverage.value == "UNAVAILABLE":
                failures.append(f"{identity.symbol}:{','.join(report.warnings) or 'HISTORY_UNAVAILABLE'}")
                if identity.instrument_id == NIFTY_500_INSTRUMENT_ID: benchmark_status = "NIFTY500_UNAVAILABLE"
            elif identity.instrument_id == NIFTY_500_INSTRUMENT_ID:
                # Persist mapping only after the provider response passed the
                # metadata identity guard in YahooHistoricalDataProvider.
                if self._persist_mapping(identity, now): mapped_records += 1
                benchmark_status = "NIFTY500_VERIFIED"
        equities = tuple(item for item in mapped if item.instrument_id != NIFTY_500_INSTRUMENT_ID)
        sufficient = sum(self._historical.count(item.instrument_id, Timeframe.DAILY) >= 252 for item in equities)
        unavailable = sum(report.coverage.value == "UNAVAILABLE" for report in reports if report.instrument_id != NIFTY_500_INSTRUMENT_ID)
        gappy = sum(report.gap_count > 0 for report in reports if report.instrument_id != NIFTY_500_INSTRUMENT_ID)
        bars = sum(self._historical.count(item.instrument_id, Timeframe.DAILY) for item in mapped)
        return YahooPopulationReport(
            requested=len(cohort), mapped=len(equities), history_success=len(equities) - unavailable,
            history_failed=unavailable, sufficient_252=sufficient, gappy=gappy, unavailable=unavailable,
            benchmark_status=benchmark_status, mapped_records=mapped_records,
            symbols_ingested=sum(report.accepted_count > 0 or self._historical.count(report.instrument_id, Timeframe.DAILY) > 0 for report in reports if report.instrument_id != NIFTY_500_INSTRUMENT_ID),
            bars_stored=bars, provider_requests=requests, failures=tuple(sorted(failures)), adjustment_status=AdjustmentStatus.RAW,
            quality_warnings=tuple(sorted(warnings)), runtime_milliseconds=int((perf_counter() - started) * 1000),
            mapping_outcomes=tuple(outcomes), reports=tuple(reports),
        )

    def _ingest_once(self, provider, identity, start, now) -> HistoricalIngestionReport:
        # Two bounded attempts only.  No parallel scrape and no changed mapping.
        report = HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
            HistoricalBarsRequest(identity, Timeframe.DAILY, start, now, AdjustmentStatus.RAW, YFINANCE_PROVIDER)
        )
        if report.coverage.value != "UNAVAILABLE": return report
        self._sleep(0.2)
        return HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
            HistoricalBarsRequest(identity, Timeframe.DAILY, start, now, AdjustmentStatus.RAW, YFINANCE_PROVIDER)
        )

    def _persist_mapping(self, identity: InstrumentIdentity, at: datetime) -> bool:
        mapping = identity.provider_mappings[0]
        existing = self._universe.provider_mapping(canonical_instrument_id=identity.instrument_id, provider=YFINANCE_PROVIDER, as_of=at)
        if existing and existing.provider_instrument_reference == mapping.provider_instrument_reference: return False
        self._universe.capture_provider_mapping(identity, provider=YFINANCE_PROVIDER, effective_as_of=at,
                                                source_reference="yfinance-nse-symbol-mapping", source_checksum=None)
        return True


def _equity_identity(item: NseEquityInstrument) -> InstrumentIdentity:
    return InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, None, InstrumentType.NSE_EQUITY, item.company_name)


def _nifty500_identity() -> InstrumentIdentity:
    return InstrumentIdentity(NIFTY_500_INSTRUMENT_ID, Exchange.INDEX, NIFTY_500_SYMBOL, NIFTY_500_SYMBOL, None, None, InstrumentType.BROAD_INDEX, NIFTY_500_SYMBOL)


def _with_mapping(identity: InstrumentIdentity, mapping: ProviderInstrumentMapping) -> InstrumentIdentity:
    return InstrumentIdentity(identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol, identity.isin, identity.series, identity.instrument_type, identity.name, identity.currency, (mapping,))


__all__ = ("FrozenYahooPopulationService", "YahooMappingOutcome", "YahooPopulationReport", "YahooOneStockValidation", "NIFTY_500_INSTRUMENT_ID", "NIFTY_500_SYMBOL")
