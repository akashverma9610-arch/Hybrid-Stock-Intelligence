from datetime import UTC, datetime, timedelta
from decimal import Decimal
import importlib.metadata

import pytest

from app.market_data.historical import BarWriteOutcome, HistoricalIngestionService, SQLiteHistoricalBarStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, ErrorCode, Exchange, HistoricalBarsRequest, InstrumentIdentity, InstrumentType, MarketDataError, MarketDataProvenance, Timeframe
from app.market_data.providers import configured_market_data_provider
from app.market_data.yfinance import YFINANCE_PROVIDER, YahooHistoricalDataProvider, YahooHistoryPayload, yahoo_nifty500_candidate_mapping, yahoo_nse_mapping
from app.market_data.yfinance_population import FrozenYahooPopulationService
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 25, tzinfo=UTC)


def _identity() -> InstrumentIdentity:
    bare = InstrumentIdentity("NSE:RELIANCE", Exchange.NSE, "RELIANCE", "RELIANCE", "INE002A01018", None, InstrumentType.NSE_EQUITY, "Reliance")
    return InstrumentIdentity(*bare.__dataclass_fields__.values()) if False else InstrumentIdentity(bare.instrument_id, bare.exchange, bare.symbol, bare.trading_symbol, bare.isin, bare.series, bare.instrument_type, bare.name, bare.currency, (yahoo_nse_mapping(bare),))


def _payload(*, metadata=None, bad=False) -> YahooHistoryPayload:
    return YahooHistoryPayload(({
        "Date": datetime(2026, 8, 20), "Open": "100.01", "High": "105", "Low": "99",
        "Close": "102.50" if not bad else "0", "Volume": 1234, "Adj Close": "99.50",
    },), metadata or {"symbol": "RELIANCE.NS", "exchangeName": "NSE", "instrumentType": "EQUITY"})


def test_yfinance_dependency_is_installed_and_nse_mapping_is_deterministic() -> None:
    assert importlib.metadata.version("yfinance") == "0.2.66"
    mapping = yahoo_nse_mapping(_identity())
    assert mapping is not None and mapping.provider == YFINANCE_PROVIDER and mapping.provider_instrument_reference == "RELIANCE.NS"
    assert yahoo_nse_mapping(InstrumentIdentity("NSE:NOISIN", Exchange.NSE, "BAD SYMBOL!", "BAD SYMBOL!", None, None, InstrumentType.NSE_EQUITY, None)) is None


def test_yfinance_explicit_raw_request_normalizes_without_substituting_adjusted_close() -> None:
    seen = []
    provider = YahooHistoricalDataProvider(history_loader=lambda request: seen.append(request) or _payload(), clock=lambda: T)
    request = HistoricalBarsRequest(_identity(), Timeframe.DAILY, T - timedelta(days=5), T, AdjustmentStatus.RAW, YFINANCE_PROVIDER)
    bars = provider.get_historical_bars(request)
    assert seen[0].symbol == "RELIANCE.NS" and seen[0].auto_adjust is False and seen[0].back_adjust is False and seen[0].actions is False
    assert bars[0].close == Decimal("102.50") and bars[0].adjustment_status is AdjustmentStatus.RAW
    assert "YFINANCE_ADJ_CLOSE_NOT_SUBSTITUTED" in bars[0].warnings and bars[0].provenance.provider == YFINANCE_PROVIDER


def test_yfinance_missing_volume_remains_null_without_weakening_ohlc_validation() -> None:
    payload = _payload(); row = dict(payload.rows[0]); row["Volume"] = float("nan")
    bar = YahooHistoricalDataProvider(history_loader=lambda _: YahooHistoryPayload((row,), payload.metadata), clock=lambda: T).get_historical_bars(HistoricalBarsRequest(_identity(), Timeframe.DAILY, T - timedelta(days=5), T))[0]
    assert bar.volume is None and bar.close == Decimal("102.50")


def test_yfinance_rejects_only_malformed_rows_and_retains_valid_daily_history() -> None:
    payload = _payload(); bad = dict(payload.rows[0]); bad["Close"] = "0"; good = dict(payload.rows[0]); good["Date"] = datetime(2026, 8, 21)
    bars = YahooHistoricalDataProvider(history_loader=lambda _: YahooHistoryPayload((bad, good), payload.metadata), clock=lambda: T).get_historical_bars(HistoricalBarsRequest(_identity(), Timeframe.DAILY, T - timedelta(days=5), T))
    assert len(bars) == 1 and "YFINANCE_REJECTED_MALFORMED_ROWS:1" in bars[0].warnings


def test_yfinance_fails_closed_on_contradictory_identity_and_bad_quality() -> None:
    request = HistoricalBarsRequest(_identity(), Timeframe.DAILY, T - timedelta(days=5), T)
    wrong = YahooHistoricalDataProvider(history_loader=lambda _: _payload(metadata={"symbol": "TCS.NS", "exchangeName": "NSE", "instrumentType": "EQUITY"}))
    with pytest.raises(MarketDataError) as mismatch: wrong.get_historical_bars(request)
    assert mismatch.value.code is ErrorCode.INSTRUMENT_NOT_FOUND
    bad = YahooHistoricalDataProvider(history_loader=lambda _: _payload(bad=True))
    with pytest.raises(MarketDataError) as malformed: bad.get_historical_bars(request)
    assert malformed.value.code is ErrorCode.MALFORMED_RESPONSE


def test_yfinance_uses_existing_ingestion_and_restart_read(tmp_path) -> None:
    path = tmp_path / "history.sqlite"; request = HistoricalBarsRequest(_identity(), Timeframe.DAILY, T - timedelta(days=5), T, AdjustmentStatus.RAW, YFINANCE_PROVIDER)
    store = SQLiteHistoricalBarStore(path); report = HistoricalIngestionService(YahooHistoricalDataProvider(history_loader=lambda _: _payload(), clock=lambda: T), store, clock=lambda: T + timedelta(days=1)).ingest(request)
    assert report.accepted_count == 1 and report.provider == YFINANCE_PROVIDER
    store.close(); reopened = SQLiteHistoricalBarStore(path)
    persisted = reopened.latest("NSE:RELIANCE", Timeframe.DAILY, 1)
    assert len(persisted) == 1 and persisted[0].close == Decimal("102.50") and persisted[0].provenance.provider == YFINANCE_PROVIDER
    assert HistoricalIngestionService(YahooHistoricalDataProvider(history_loader=lambda _: _payload(), clock=lambda: T), reopened, clock=lambda: T + timedelta(days=1)).ingest(request).duplicate_count == 1


def _cohort() -> tuple[NseEquityInstrument, ...]:
    return tuple(NseEquityInstrument(f"NSE:F{number:02}", f"F{number:02}", f"INE{number:08}A01", None, None, "ACTIVE", None, True, T, "NSE", main_board=True) for number in range(40))


class _History:
    def __init__(self): self.calls = []
    def get_historical_bars(self, request):
        self.calls.append(request)
        return tuple(CanonicalOHLCVBar(f"bar:{request.instrument.instrument_id}:{number}", request.instrument, Timeframe.DAILY, request.start + timedelta(days=number), request.start + timedelta(days=number + 1), Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000, None, None, AdjustmentStatus.RAW, MarketDataProvenance(YFINANCE_PROVIDER, request.instrument.provider_mappings[0].provider_instrument_reference, None, None, T, "test")) for number in range(252))


class _MemoryStore:
    def __init__(self): self.values = {}
    def upsert(self, bar):
        key = (bar.instrument.instrument_id, bar.timeframe, bar.start_time, bar.end_time); old = self.values.get(key)
        if old is None: self.values[key] = bar; return BarWriteOutcome.INSERTED
        return BarWriteOutcome.IDENTICAL if old == bar else BarWriteOutcome.CONFLICT
    def range(self, instrument_id, timeframe, start, end, *, as_of=None): return tuple(value for key, value in sorted(self.values.items(), key=lambda pair: pair[0][2]) if key[0] == instrument_id and key[1] is timeframe and start <= value.start_time and value.end_time <= end)
    def latest(self, instrument_id, timeframe, count, *, as_of=None): return self.range(instrument_id, timeframe, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC))[-count:]
    def coverage(self, instrument_id, timeframe, start, end, *, as_of=None):
        from app.market_data.historical import GapStatus, HistoricalBarCoverage, HistoricalCoverageStatus
        bars = self.range(instrument_id, timeframe, start, end); return HistoricalBarCoverage(HistoricalCoverageStatus.PARTIAL if bars else HistoricalCoverageStatus.UNAVAILABLE, start, end, bars[0].start_time if bars else None, bars[-1].end_time if bars else None, len(bars), GapStatus.NONE if bars else GapStatus.UNKNOWN)
    def count(self, instrument_id, timeframe): return sum(key[0] == instrument_id and key[1] is timeframe for key in self.values)


def test_frozen_yfinance_population_is_40_only_and_never_substitutes_nifty50(tmp_path) -> None:
    cohort = _cohort(); history = _History(); repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    report = FrozenYahooPopulationService(universe_store=CoreUniverseAnalysisStore(repository), historical_store=_MemoryStore(), provider_factory=lambda: history, clock=lambda: T, sleeper=lambda _: None).populate(cohort=cohort, years=1, include_verified_nifty500=False)
    assert (report.requested, report.mapped, report.history_success, report.sufficient_252) == (40, 40, 40, 40)
    assert report.provider_requests == 40 and report.benchmark_status == "NIFTY500_UNAVAILABLE" and len(history.calls) == 40
    persisted = CoreUniverseAnalysisStore(repository).provider_mapping(canonical_instrument_id=cohort[0].instrument_id, provider=YFINANCE_PROVIDER, as_of=T)
    assert persisted is not None and persisted.provider_instrument_reference.endswith(".NS")
    nifty = InstrumentIdentity("NIFTY_500", Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None, InstrumentType.BROAD_INDEX, "NIFTY 500")
    assert yahoo_nifty500_candidate_mapping(nifty).provider_instrument_reference != "^NSEI"


def test_one_stock_validation_is_bounded_to_an_exact_frozen_symbol(tmp_path) -> None:
    cohort = _cohort(); history = _History(); repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    service = FrozenYahooPopulationService(universe_store=CoreUniverseAnalysisStore(repository), historical_store=_MemoryStore(), provider_factory=lambda: history, clock=lambda: T, sleeper=lambda _: None)
    value = service.validate_one(cohort=cohort, symbol="F17", years=1)
    assert value.canonical_symbol == "F17" and value.yahoo_symbol == "F17.NS" and value.session_count == 252
    assert value.report.accepted_count == 252 and len(history.calls) == 1
    with pytest.raises(ValueError, match="NOT_IN_FROZEN"):
        service.validate_one(cohort=cohort, symbol="OUTSIDE", years=1)


def test_yfinance_provider_is_independent_historical_selection_and_consumers_do_not_import_it() -> None:
    assert isinstance(configured_market_data_provider("yfinance", yfinance_loader=lambda _: _payload()), YahooHistoricalDataProvider)
    from app.data_sources.models import DataFamily
    from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings, SourceValidationState
    settings = SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER": "kotak_neo", "HISTORICAL_DATA_PROVIDER": "yfinance"})
    assert DataSourceCompositionService.from_settings(settings, states={"yfinance": SourceValidationState(True, True)}).readiness().primary(DataFamily.HISTORICAL_OHLCV).source_id == "yfinance"
    import inspect, app.analysis.relative_strength as relative_strength, app.analysis.series as technical, app.crisis as crisis, app.crisis.extremes as extremes
    assert "yfinance" not in "\n".join(inspect.getsource(value).lower() for value in (technical, relative_strength, crisis, extremes))
    # The adapter's deliberately narrow public surface rules out accidental
    # Yahoo fundamentals, ownership, delivery, or corporate-action ingestion.
    public = {name for name in dir(YahooHistoricalDataProvider) if not name.startswith("_")}
    assert public == {"capabilities", "get_historical_bars", "request_parameters"}
