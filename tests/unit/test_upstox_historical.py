from datetime import UTC, datetime, timedelta
from decimal import Decimal
import gzip
import json

import pytest

from app.market_data.historical import (
    BarWriteOutcome, GapStatus, HistoricalBarCoverage, HistoricalCoverageStatus,
    HistoricalIngestionService, SQLiteHistoricalBarStore,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, ErrorCode, Exchange, HistoricalBarsRequest, InstrumentIdentity,
    InstrumentType, MarketDataError, ProviderInstrumentMapping, Timeframe,
    MarketDataProvenance,
)
from app.market_data.providers import configured_market_data_provider
from app.market_data.upstox import (
    UPSTOX_PROVIDER, UpstoxHistoricalProvider, exact_upstox_mapping,
    load_upstox_nse_bod_instrument_master, parse_upstox_instrument_records,
)
import app.market_data.upstox as upstox_module
from app.market_data.upstox_population import (
    FrozenUpstoxPopulationService, resolve_upstox_equity_mapping,
    resolve_upstox_nifty_500_mapping,
)
from app.market_data.upstox_sector_indices import (
    UpstoxNseIndexPopulationService, nse_index_records,
    resolve_official_nse_index_mappings,
)
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 21, tzinfo=UTC)


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity(
        "NSE:RELIANCE", Exchange.NSE, "RELIANCE", "RELIANCE", "INE002A01018", None,
        InstrumentType.NSE_EQUITY, "Reliance Industries", provider_mappings=(
            ProviderInstrumentMapping(UPSTOX_PROVIDER, "NSE_EQ|INE002A01018", "RELIANCE", "upstox-v3", "NSE_EQ"),
        ),
    )


def _payload() -> dict:
    return {"status": "success", "data": {"candles": [
        ["2026-08-20T00:00:00+05:30", 100.01, 103, 99, 102.50, 1234, 0],
        ["2026-08-21T00:00:00+05:30", "102.50", "105", "101", "104.25", 2345, None],
    ]}}


def test_v3_daily_request_normalizes_decimal_timezone_volume_and_unknown_adjustment() -> None:
    seen = []
    provider = UpstoxHistoricalProvider("secret", transport=lambda request: seen.append(request) or _payload(), clock=lambda: T)
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=4), T, AdjustmentStatus.RAW, UPSTOX_PROVIDER)
    bars = provider.get_historical_bars(request)
    assert seen[0].unit == "days" and seen[0].interval == "1"
    assert "/NSE_EQ%7CINE002A01018/days/1/2026-08-21/2026-08-17" in seen[0].url
    assert seen[0].headers == {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer secret",
    }
    assert bars[0].close == Decimal("102.50") and bars[0].end_time.tzinfo is not None
    assert bars[0].start_time == bars[0].end_time == datetime(2026, 8, 19, 18, 30, tzinfo=UTC)
    assert bars[0].provenance.exchange_timestamp == bars[0].start_time
    assert bars[0].provenance.normalization_version == "upstox-history-v4-interval-start"
    assert bars[0].volume == 1234 and bars[0].adjustment_status is AdjustmentStatus.UNKNOWN
    assert "UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED" in bars[0].warnings
    assert "UPSTOX_DAILY_TIMESTAMP_INTERVAL_START" in bars[0].warnings
    assert "UPSTOX_DAILY_SESSION_END_UNBOUND" in bars[0].warnings
    assert "UPSTOX_OPEN_INTEREST_NOT_IN_CANONICAL_OHLCV_CONTRACT" in bars[0].warnings


def test_v3_index_candle_keeps_missing_volume_null_without_fabricating_zero() -> None:
    index = InstrumentIdentity(
        "NIFTY_500", Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None,
        InstrumentType.BROAD_INDEX, "NIFTY 500", provider_mappings=(
            ProviderInstrumentMapping(UPSTOX_PROVIDER, "NSE_INDEX|NIFTY 500", "NIFTY 500", "upstox-v3", "NSE_INDEX"),
        ),
    )
    provider = UpstoxHistoricalProvider("secret", transport=lambda _: {"status": "success", "data": {"candles": [
        ["2026-08-21T00:00:00+05:30", "100", "101", "99", "100.5", None, None],
    ]}}, clock=lambda: T)
    bars = provider.get_historical_bars(HistoricalBarsRequest(index, Timeframe.DAILY, T - timedelta(days=1), T))
    assert bars[0].volume is None and bars[0].close == Decimal("100.5")


def test_v3_provider_requires_one_clean_bearer_token_for_historical_candles() -> None:
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=1), T)
    with pytest.raises(MarketDataError) as missing:
        UpstoxHistoricalProvider().request_parameters(request)
    assert missing.value.code is ErrorCode.AUTHENTICATION_REQUIRED
    prefixed = UpstoxHistoricalProvider("  Bearer Bearer secure-token\n").request_parameters(request)
    assert prefixed.headers == {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer secure-token",
    }


def test_v3_production_transport_uses_requests_with_exact_headers_timeout_and_no_spoofed_user_agent(monkeypatch) -> None:
    calls = []

    class Response:
        status_code = 200
        content = json.dumps(_payload()).encode("utf-8")

    def get(url, *, headers, timeout):
        calls.append((url, dict(headers), timeout))
        return Response()

    monkeypatch.setattr(upstox_module.requests, "get", get)
    provider = UpstoxHistoricalProvider("synthetic-secret", clock=lambda: T, timeout_seconds=17.5)
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=1), T)

    payload = provider._https_transport(provider.request_parameters(request))

    assert payload == _payload()
    assert calls == [(
        "https://api.upstox.com/v3/historical-candle/NSE_EQ%7CINE002A01018/days/1/2026-08-21/2026-08-20",
        {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer synthetic-secret",
        },
        17.5,
    )]
    assert "User-Agent" not in calls[0][1]


@pytest.mark.parametrize(
    ("status", "code"),
    ((401, ErrorCode.AUTHENTICATION_REQUIRED), (403, ErrorCode.AUTHORIZATION_FAILURE), (404, ErrorCode.INSTRUMENT_NOT_FOUND), (429, ErrorCode.RATE_LIMITED), (500, ErrorCode.PROVIDER_UNAVAILABLE)),
)
def test_v3_requests_transport_preserves_http_error_mapping(monkeypatch, status, code) -> None:
    class Response:
        status_code = status
        content = b'{"status":"error","code":"UDAPI_TEST"}'

    monkeypatch.setattr(upstox_module.requests, "get", lambda *args, **kwargs: Response())
    provider = UpstoxHistoricalProvider("synthetic-secret", clock=lambda: T)
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=1), T)

    with pytest.raises(MarketDataError) as captured:
        provider._https_transport(provider.request_parameters(request))

    assert captured.value.code is code
    assert "synthetic-secret" not in str(captured.value)


def test_v3_provider_fails_closed_for_mapping_timeframe_and_malformed_rows() -> None:
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=1), T)
    with pytest.raises(MarketDataError) as unsupported:
        UpstoxHistoricalProvider("secret").request_parameters(HistoricalBarsRequest(_instrument(), Timeframe.WEEKLY, T - timedelta(days=7), T))
    assert unsupported.value.code is ErrorCode.UNSUPPORTED_TIMEFRAME
    with pytest.raises(MarketDataError) as malformed:
        UpstoxHistoricalProvider("secret", transport=lambda _: {"status": "success", "data": {"candles": [["bad"]]}}).get_historical_bars(request)
    assert malformed.value.code is ErrorCode.MALFORMED_RESPONSE


def test_v3_ingestion_uses_existing_historical_service_and_store(tmp_path) -> None:
    provider = UpstoxHistoricalProvider("secret", transport=lambda _: _payload(), clock=lambda: T)
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    request = HistoricalBarsRequest(_instrument(), Timeframe.DAILY, T - timedelta(days=4), T, provider_preference=UPSTOX_PROVIDER)
    report = HistoricalIngestionService(provider, store, clock=lambda: T + timedelta(days=1)).ingest(request)
    assert report.accepted_count == 2 and report.provider == UPSTOX_PROVIDER
    persisted = store.latest("NSE:RELIANCE", Timeframe.DAILY, 2)
    assert persisted[0].provenance.provider == UPSTOX_PROVIDER and persisted[1].close == Decimal("104.25")
    repeated = HistoricalIngestionService(provider, store, clock=lambda: T + timedelta(days=1)).ingest(request)
    assert repeated.accepted_count == 0 and repeated.duplicate_count == 2


def test_official_bod_master_mapping_is_exact_isin_nse_equity_only() -> None:
    records = parse_upstox_instrument_records([
        {"segment": "NSE_EQ", "exchange": "NSE", "isin": "INE002A01018", "instrument_type": "EQ", "instrument_key": "NSE_EQ|INE002A01018", "trading_symbol": "RELIANCE"},
        {"segment": "NSE_EQ", "exchange": "NSE", "isin": "INE000000001", "instrument_type": "EQ", "instrument_key": "NSE_EQ|INE000000001", "trading_symbol": "RELIANCE"},
    ])
    mapping = exact_upstox_mapping(_instrument(), records)
    assert mapping is not None and mapping.provider_instrument_reference == "NSE_EQ|INE002A01018"
    assert exact_upstox_mapping(InstrumentIdentity("NSE:NOISIN", Exchange.NSE, "RELIANCE", "RELIANCE", None, None, InstrumentType.NSE_EQUITY, None), records) is None


def test_upstox_is_an_independent_historical_provider_selection() -> None:
    provider = configured_market_data_provider("upstox", upstox_access_token="secret", upstox_transport=lambda _: _payload())
    assert isinstance(provider, UpstoxHistoricalProvider)
    from app.data_sources.models import DataFamily, SourceReadinessStatus, SourceValidationState
    from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
    settings = SourceCompositionSettings.from_environment({"MARKET_DATA_PROVIDER": "kotak_neo", "HISTORICAL_DATA_PROVIDER": "upstox"})
    report = DataSourceCompositionService.from_settings(settings, states={"upstox": SourceValidationState(True, True)}).readiness()
    assert report.primary(DataFamily.CURRENT_QUOTES).source_id == "kotak_neo"
    assert report.primary(DataFamily.HISTORICAL_OHLCV).source_id == UPSTOX_PROVIDER
    assert report.primary(DataFamily.HISTORICAL_OHLCV).status is SourceReadinessStatus.READY


def test_technical_and_regime_consumers_do_not_depend_on_upstox() -> None:
    import inspect
    import app.analysis.relative_strength as relative_strength
    import app.analysis.series as technical
    import app.crisis as crisis
    import app.crisis.extremes as extremes

    source = "\n".join(inspect.getsource(item).lower() for item in (technical, relative_strength, crisis, extremes))
    assert "upstox" not in source


def test_official_bod_loader_handles_compressed_json_and_retains_only_sanitized_metadata() -> None:
    compressed = gzip.compress(json.dumps([
        {"instrument_key": "NSE_EQ|INE002A01018", "segment": "NSE_EQ", "exchange": "NSE", "isin": "INE002A01018", "instrument_type": "EQ", "trading_symbol": "RELIANCE"},
    ]).encode("utf-8"))
    master = load_upstox_nse_bod_instrument_master(
        url="https://example.invalid/nse.json.gz", downloader=lambda _, __: compressed,
    )
    assert master.source_url == "https://example.invalid/nse.json.gz"
    assert len(master.checksum) == 64 and master.records[0].instrument_key == "NSE_EQ|INE002A01018"


class _FrozenCohortProvider:
    """Offline V3-shaped source used only to prove canonical population wiring."""

    def __init__(self, _: str) -> None:
        self.calls: list[HistoricalBarsRequest] = []

    def get_historical_bars(self, request: HistoricalBarsRequest):
        self.calls.append(request)
        reference = request.instrument.provider_mappings[0].provider_instrument_reference
        return tuple(
            CanonicalOHLCVBar(
                f"bar:{request.instrument.instrument_id}:{number}", request.instrument, Timeframe.DAILY,
                request.start + timedelta(days=number), request.start + timedelta(days=number),
                Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000, None, None,
                AdjustmentStatus.UNKNOWN,
                MarketDataProvenance(UPSTOX_PROVIDER, reference, None, None, T, "upstox-v3", source_reference="upstox-v3"),
                warnings=("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED",),
            )
            for number in range(252)
        )


class _FastHistoricalStore:
    """In-memory implementation of the existing store contract for 41x252 bars."""

    def __init__(self) -> None:
        self._bars: dict[tuple[str, Timeframe, datetime, datetime], CanonicalOHLCVBar] = {}

    def upsert(self, bar: CanonicalOHLCVBar) -> BarWriteOutcome:
        key = (bar.instrument.instrument_id, bar.timeframe, bar.start_time, bar.end_time)
        existing = self._bars.get(key)
        if existing is None:
            self._bars[key] = bar
            return BarWriteOutcome.INSERTED
        return BarWriteOutcome.IDENTICAL if existing == bar else BarWriteOutcome.CONFLICT

    def range(self, instrument_id, timeframe, start, end, *, as_of=None):
        return tuple(
            item for key, item in sorted(self._bars.items(), key=lambda entry: entry[0][2])
            if key[0] == instrument_id and key[1] is timeframe and start <= item.start_time <= end
            and (as_of is None or item.end_time <= as_of and item.provenance.received_at <= as_of)
        )

    def latest(self, instrument_id, timeframe, count, *, as_of=None):
        return self.range(instrument_id, timeframe, datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC), as_of=as_of)[-count:]

    def coverage(self, instrument_id, timeframe, start, end, *, as_of=None):
        bars = self.range(instrument_id, timeframe, start, end, as_of=as_of)
        return HistoricalBarCoverage(
            HistoricalCoverageStatus.PARTIAL if bars else HistoricalCoverageStatus.UNAVAILABLE,
            start, end, bars[0].start_time if bars else None, bars[-1].end_time if bars else None,
            len(bars), GapStatus.NONE if bars else GapStatus.UNKNOWN,
        )

    def count(self, instrument_id, timeframe):
        return sum(key[0] == instrument_id and key[1] is timeframe for key in self._bars)


def _frozen_cohort() -> tuple[NseEquityInstrument, ...]:
    return tuple(
        NseEquityInstrument(
            f"NSE:FROZEN{number:02}", f"FROZEN{number:02}", f"INE{number:08}A01",
            None, None, "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT", main_board=True,
        )
        for number in range(40)
    )


def test_frozen_40_population_maps_exact_isins_persists_nifty500_and_ingests_canonical_history(tmp_path) -> None:
    cohort = _frozen_cohort()
    rows = [
        {"instrument_key": f"NSE_EQ|{item.isin}", "segment": "NSE_EQ", "exchange": "NSE", "isin": item.isin,
         "instrument_type": "EQ", "trading_symbol": item.symbol}
        for item in cohort
    ] + [{
        "instrument_key": "NSE_INDEX|NIFTY 500", "segment": "NSE_INDEX", "exchange": "NSE_INDEX",
        "instrument_type": "INDEX", "trading_symbol": "NIFTY 500",
    }]
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    history = _FastHistoricalStore()
    provider: _FrozenCohortProvider | None = None

    def provider_factory(token: str) -> _FrozenCohortProvider:
        nonlocal provider
        provider = _FrozenCohortProvider(token)
        return provider

    report = FrozenUpstoxPopulationService(
        universe_store=universe, historical_store=history, provider_factory=provider_factory, clock=lambda: T,
    ).populate(
        cohort=cohort, master_records=parse_upstox_instrument_records(rows),
        master_source_reference="official-upstox-nse-bod", master_checksum="bod-checksum",
        access_token="test-only", years=1,
    )

    assert (report.requested, report.matched, report.ambiguous, report.unmatched) == (40, 40, 0, 0)
    assert report.benchmark_status == "MATCHED"
    assert (report.symbols_ingested, report.sufficient_252, report.provider_requests) == (40, 40, 41)
    assert report.bars_stored == 41 * 252 and report.adjustment_status is AdjustmentStatus.UNKNOWN
    assert provider is not None and len(provider.calls) == 41
    assert history.count("NIFTY_500", Timeframe.DAILY) == 252
    persisted = universe.provider_mapping(canonical_instrument_id=cohort[0].instrument_id, provider=UPSTOX_PROVIDER, as_of=T)
    assert persisted is not None and persisted.source_reference == "official-upstox-nse-bod"
    assert persisted.source_checksum == "bod-checksum" and persisted.provider_instrument_reference

    # The same official master and frozen cohort do not rewrite stored bars or
    # mappings on a later operator retry.
    repeat = FrozenUpstoxPopulationService(
        universe_store=universe, historical_store=history, provider_factory=provider_factory, clock=lambda: T,
    ).populate(
        cohort=cohort, master_records=parse_upstox_instrument_records(rows),
        master_source_reference="official-upstox-nse-bod", master_checksum="bod-checksum",
        access_token="test-only", years=1,
    )
    assert repeat.mapped_records == 0 and repeat.bars_stored == report.bars_stored


def test_population_mapping_fallback_is_exact_unambiguous_and_nifty500_never_substitutes_nifty50() -> None:
    identity = InstrumentIdentity("NSE:EXACT", Exchange.NSE, "EXACT", "EXACT", "INE_CANONICAL", None, InstrumentType.NSE_EQUITY, None)
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_EQ|EXACT", "segment": "NSE_EQ", "exchange": "NSE", "isin": "OTHER", "instrument_type": "EQ", "trading_symbol": "EXACT"},
        {"instrument_key": "NSE_INDEX|NIFTY 50", "segment": "NSE_INDEX", "exchange": "NSE_INDEX", "instrument_type": "INDEX", "trading_symbol": "NIFTY 50"},
    ])
    fallback, status, method = resolve_upstox_equity_mapping(identity, records)
    assert status == "MATCHED" and method == "EXACT_SYMBOL_NSE_CASH" and fallback is not None
    duplicate = parse_upstox_instrument_records([
        {"instrument_key": "NSE_EQ|ONE", "segment": "NSE_EQ", "exchange": "NSE", "instrument_type": "EQ", "trading_symbol": "EXACT"},
        {"instrument_key": "NSE_EQ|TWO", "segment": "NSE_EQ", "exchange": "NSE", "instrument_type": "BE", "trading_symbol": "EXACT"},
    ])
    assert resolve_upstox_equity_mapping(identity, duplicate)[:2] == (None, "AMBIGUOUS")
    nifty500 = InstrumentIdentity("NIFTY_500", Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None, InstrumentType.BROAD_INDEX, "NIFTY 500")
    assert resolve_upstox_nifty_500_mapping(nifty500, records) is None


def _sector_mapping(sector: str, name: str) -> NseSectorIndexMapping:
    return NseSectorIndexMapping(
        f"mapping-{sector}", sector, name, "https://official.example/index", SectorIndexMappingStatus.EXACT_OFFICIAL,
        ("OFFICIAL",), "official-sha", T,
    )


def test_nse_index_filter_and_task38_mapping_are_deterministic_and_fail_closed_on_ambiguity() -> None:
    sector = _sector_mapping("Healthcare", "Nifty Healthcare")
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_EQ|INE", "segment": "NSE_EQ", "exchange": "NSE", "instrument_type": "EQ", "trading_symbol": "NIFTY HEALTHCARE"},
        {"instrument_key": "NSE_INDEX|NIFTY 500", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY 500"},
        {"instrument_key": "NSE_INDEX|HEALTH", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY-HEALTHCARE"},
    ])
    assert [item.instrument_key for item in nse_index_records(records)] == ["NSE_INDEX|NIFTY 500", "NSE_INDEX|HEALTH"]
    resolved = resolve_official_nse_index_mappings((sector,), records)
    assert [(item.official_index_name, item.resolution_status) for item in resolved] == [
        ("NIFTY 500", "EXACT"), ("Nifty Healthcare", "NORMALIZED_EXACT"),
    ]
    ambiguous = parse_upstox_instrument_records([
        *[{
            "instrument_key": f"NSE_INDEX|H{number}", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY HEALTHCARE",
        } for number in range(2)],
        {"instrument_key": "NSE_INDEX|NIFTY 500", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY 500"},
    ])
    assert resolve_official_nse_index_mappings((sector,), ambiguous)[1].resolution_status == "AMBIGUOUS"


def test_reviewed_sector_index_aliases_are_exact_and_unsupported_indices_stay_unresolved() -> None:
    mappings = (
        _sector_mapping("Financial Services", "Nifty Financial Services"),
        _sector_mapping("Consumer Durables", "Nifty Consumer Durables Index"),
        _sector_mapping("Healthcare", "Nifty Healthcare Index"),
        _sector_mapping("Construction", "Nifty Construction"),
        _sector_mapping("Consumer Services", "Nifty Consumer Services"),
        _sector_mapping("Power", "Nifty Power"),
        _sector_mapping("Capital Goods", "Nifty Capital Goods"),
    )
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_INDEX|Nifty 500", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY 500"},
        {"instrument_key": "NSE_INDEX|Nifty Fin Service", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "FINNIFTY"},
        {"instrument_key": "NSE_INDEX|NIFTY CONSR DURBL", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY CONSR DURBL"},
        {"instrument_key": "NSE_INDEX|NIFTY HEALTHCARE", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY HEALTHCARE"},
        {"instrument_key": "NSE_INDEX|Nifty Infra", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY INFRA"},
        {"instrument_key": "NSE_INDEX|Nifty Energy", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY ENERGY"},
        {"instrument_key": "NSE_INDEX|Nifty Capital Mkt", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY CAPITAL MKT"},
    ])

    result = resolve_official_nse_index_mappings(mappings, records)
    by_name = {item.official_index_name: item for item in result}
    assert [by_name[name].instrument_key for name in (
        "Nifty Financial Services", "Nifty Consumer Durables Index", "Nifty Healthcare Index",
    )] == [
        "NSE_INDEX|Nifty Fin Service", "NSE_INDEX|NIFTY CONSR DURBL", "NSE_INDEX|NIFTY HEALTHCARE",
    ]
    assert all(by_name[name].resolution_status == "REVIEWED_ALIAS" for name in (
        "Nifty Financial Services", "Nifty Consumer Durables Index", "Nifty Healthcare Index",
    ))
    assert all(by_name[name].resolution_status == "UNRESOLVED" for name in (
        "Nifty Construction", "Nifty Consumer Services", "Nifty Power", "Nifty Capital Goods",
    ))


def test_index_population_uses_existing_ingestion_and_never_overwrites_existing_yahoo_bar(tmp_path) -> None:
    sector = _sector_mapping("Healthcare", "Nifty Healthcare")
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_INDEX|NIFTY 500", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY 500"},
        {"instrument_key": "NSE_INDEX|HEALTH", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY HEALTHCARE"},
    ])
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    start = T - timedelta(days=366)
    yahoo_identity = InstrumentIdentity("NIFTY_500", Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None, InstrumentType.BROAD_INDEX, "NIFTY 500")
    historical = CanonicalOHLCVBar(
        "yahoo-existing", yahoo_identity, Timeframe.DAILY, start, start, Decimal("90"), Decimal("91"), Decimal("89"), Decimal("90"), None, None, None,
        AdjustmentStatus.RAW, MarketDataProvenance("yahoo", "^NIFTY500", start, start, T, "yahoo", source_reference="yahoo"),
    )
    assert history.upsert(historical) is BarWriteOutcome.INSERTED

    provider: Provider | None = None

    class Provider:
        def __init__(self, _: str) -> None: self.calls = []
        def get_historical_bars(self, request):
            self.calls.append(request)
            return (CanonicalOHLCVBar(
                "upstox-new", request.instrument, Timeframe.DAILY, start, start,
                Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), None, None, None,
                AdjustmentStatus.UNKNOWN, MarketDataProvenance(UPSTOX_PROVIDER, request.instrument.provider_mappings[0].provider_instrument_reference, start, start, T, "upstox-v3"),
            ),)

    def factory(token: str) -> Provider:
        nonlocal provider
        provider = Provider(token)
        return provider

    outcome = UpstoxNseIndexPopulationService(
        universe_store=universe, historical_store=history, provider_factory=factory, clock=lambda: T,
    ).populate(sector_mappings=(sector,), master_records=records, access_token="synthetic", years=1, master_checksum="bod")
    assert outcome.provider_requests == 2
    nifty_report = next(item for item in outcome.reports if item.instrument_id == "NIFTY_500")
    assert nifty_report.accepted_count == 1 and nifty_report.conflict_count == 0
    retained = history.latest("NIFTY_500", Timeframe.DAILY, 1)[0]
    assert retained.provenance.provider == UPSTOX_PROVIDER and retained.close == Decimal("100")
    raw = history.raw_range("NIFTY_500", Timeframe.DAILY, start, start)
    assert {item.provenance.provider for item in raw} == {"yahoo", UPSTOX_PROVIDER}
    assert provider is not None and all(item.instrument.provider_mappings[0].provider == UPSTOX_PROVIDER for item in provider.calls)


def test_index_probe_is_bounded_to_three_requests_and_never_persists(tmp_path) -> None:
    mappings = (
        _sector_mapping("Healthcare", "Nifty Healthcare"),
        _sector_mapping("Fast Moving Consumer Goods", "Nifty FMCG"),
        _sector_mapping("Power", "Nifty Power"),
    )
    records = parse_upstox_instrument_records([
        {"instrument_key": "NSE_INDEX|NIFTY 500", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY 500"},
        {"instrument_key": "NSE_INDEX|HEALTH", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY HEALTHCARE"},
        {"instrument_key": "NSE_INDEX|FMCG", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY FMCG"},
        {"instrument_key": "NSE_INDEX|POWER", "segment": "NSE_INDEX", "exchange": "NSE", "instrument_type": "INDEX", "trading_symbol": "NIFTY POWER"},
    ])
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    calls: list[HistoricalBarsRequest] = []

    class Provider:
        def __init__(self, _: str) -> None: pass
        def get_historical_bars(self, request):
            calls.append(request)
            return ()

    report = UpstoxNseIndexPopulationService(
        universe_store=CoreUniverseAnalysisStore(repository), historical_store=history, provider_factory=Provider, clock=lambda: T,
    ).probe(sector_mappings=mappings, master_records=records, access_token="synthetic", years=1)
    assert report.provider_requests == 3 and [item.instrument.instrument_id for item in calls] == [
        "NIFTY_500", "NSE_SECTOR_INDEX:HEALTHCARE", "NSE_SECTOR_INDEX:FAST_MOVING_CONSUMER_GOODS",
    ]
    assert history.count("NIFTY_500", Timeframe.DAILY) == 0
    assert CoreUniverseAnalysisStore(repository).provider_mapping(canonical_instrument_id="NIFTY_500", provider=UPSTOX_PROVIDER) is None
