from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import inspect

import pytest

from app.domain.models import DataQuality
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    CapabilityState,
    ErrorCode,
    Exchange,
    FreshnessState,
    FreshnessThresholds,
    HistoricalBarsRequest,
    IndexMarketObservation,
    InstrumentIdentity,
    InstrumentType,
    MarketBreadthObservation,
    MarketDataError,
    MarketDataProvenance,
    MarketDataQualityError,
    MarketDataQualityValidator,
    MarketSessionObservation,
    MarketSessionState,
    ProviderCapabilities,
    ProviderInstrumentMapping,
    SessionAwareFreshnessEvaluator,
    Timeframe,
)
from app.market_data.normalization import MarketDataNormalizer
from app.market_data.providers import MarketDataProviderRegistry, StaticMarketDataProvider
from app.market_data.store import InMemoryMarketDataStore, MarketDataSnapshotWriter
from app.market_data.bridge import index_observation, price_bar_observation


T = datetime(2026, 8, 25, 10, tzinfo=UTC)


def instrument(identifier: str = "NSE:RELIANCE") -> InstrumentIdentity:
    return InstrumentIdentity(
        identifier, Exchange.NSE, "RELIANCE", "RELIANCE", "INE002A01018", "EQ",
        InstrumentType.NSE_EQUITY, "Reliance Industries", "INR",
        (ProviderInstrumentMapping("static", "vendor-token-739", "RELIANCE"),),
    )


def provenance(at: datetime = T) -> MarketDataProvenance:
    return MarketDataProvenance("static", "vendor-token-739", at, at, at, "canonical-v1", "request-1", "fixture-1")


def freshness(at: datetime = T):
    return SessionAwareFreshnessEvaluator(FreshnessThresholds(
        timedelta(minutes=1), timedelta(minutes=5), timedelta(days=1), timedelta(minutes=5), timedelta(minutes=5)
    )).evaluate(observed_at=at, evaluated_at=at, kind="quote", session_state=MarketSessionState.OPEN)


def quote(identifier: str = "quote-1", at: datetime = T):
    return MarketDataNormalizer().quote(
        {"last_price": "2500.25", "previous_close": "2490", "open": "2495", "high": "2510", "low": "2488", "volume": 123, "turnover": "307530.75", "bid": "2500", "ask": "2500.5"},
        quote_id=identifier, instrument=instrument(), provenance=provenance(at), freshness=freshness(at), quality=DataQuality.HIGH,
    )


def bar(identifier: str = "bar-1", at: datetime = T):
    return MarketDataNormalizer().bar(
        {"start_time": at - timedelta(minutes=5), "end_time": at, "open": "100", "high": "105", "low": "99", "close": "102", "volume": 1000, "turnover": "102000", "trade_count": 10, "adjustment_status": "RAW"},
        bar_id=identifier, instrument=instrument(), timeframe=Timeframe.FIVE_MINUTES, provenance=provenance(at), quality=DataQuality.HIGH,
    )


def index() -> IndexMarketObservation:
    index_instrument = InstrumentIdentity("INDEX:NIFTY50", Exchange.INDEX, "NIFTY 50", "NIFTY", None, None, InstrumentType.BROAD_INDEX, "Nifty 50")
    return IndexMarketObservation("index-1", index_instrument, Decimal("25000"), Decimal("24900"), None, None, None, Decimal("100"), Decimal("0.4"), T, provenance(), freshness(), DataQuality.HIGH)


def breadth() -> MarketBreadthObservation:
    return MarketBreadthObservation("breadth-1", "NIFTY500", 300, 180, 20, 35, 15, Decimal("60"), Decimal("40"), 1000, 500, 500, 500, T, provenance(), freshness(), DataQuality.HIGH)


def capabilities(*, batches=CapabilityState.SUPPORTED, multiple=True) -> ProviderCapabilities:
    return ProviderCapabilities(
        current_quotes=CapabilityState.SUPPORTED, batch_quotes=batches, historical_candles=CapabilityState.SUPPORTED,
        supported_timeframes=frozenset({Timeframe.FIVE_MINUTES}), index_data=CapabilityState.SUPPORTED,
        vix=CapabilityState.SUPPORTED, breadth=CapabilityState.SUPPORTED, instrument_master=CapabilityState.SUPPORTED,
        market_status=CapabilityState.SUPPORTED,
    )


def provider(*, quote_values=None) -> StaticMarketDataProvider:
    return StaticMarketDataProvider(
        (instrument(),), quote_values or {instrument().instrument_id: quote()}, {instrument().instrument_id: (bar(),)},
        {index().instrument.instrument_id: index()}, {"NIFTY500": breadth()},
        {"NSE": MarketSessionObservation("session-1", Exchange.NSE, MarketSessionState.OPEN, T, provenance())}, capabilities(),
    )


def test_canonical_identity_keeps_provider_token_in_mapping_not_identity() -> None:
    value = instrument()
    assert value.instrument_id == "NSE:RELIANCE"
    assert value.provider_mappings[0].provider_instrument_reference == "vendor-token-739"
    assert value.provider_mappings[0].provider_instrument_reference != value.instrument_id


def test_static_provider_resolves_quote_batch_partial_and_preserves_decimal() -> None:
    value = provider()
    missing = InstrumentIdentity("NSE:MISSING", Exchange.NSE, "MISSING", "MISSING", None, "EQ", InstrumentType.NSE_EQUITY, None)
    assert value.resolve_instrument("reliance") == instrument()
    assert value.get_quote(instrument()).last_price == Decimal("2500.25")
    batch = value.get_quotes((instrument(), missing))
    assert batch.quotes == (quote(),)
    assert batch.failures[missing.instrument_id].code is ErrorCode.INSTRUMENT_NOT_FOUND
    assert batch.warnings


def test_static_provider_historical_index_breadth_session_and_timeframe_boundaries() -> None:
    value = provider()
    request = HistoricalBarsRequest(instrument(), Timeframe.FIVE_MINUTES, T - timedelta(days=1), T)
    assert value.get_historical_bars(request) == (bar(),)
    assert value.get_latest_bar(instrument(), Timeframe.FIVE_MINUTES) == bar()
    assert value.get_index_observation(index().instrument) == index()
    assert value.get_market_breadth("NIFTY500") == breadth()
    assert value.get_market_status(Exchange.NSE).state is MarketSessionState.OPEN
    with pytest.raises(MarketDataError, match="unsupported"):
        value.get_historical_bars(HistoricalBarsRequest(instrument(), Timeframe.DAILY, T - timedelta(days=1), T))


def test_vix_compatible_index_adjustment_and_degraded_freshness_are_explicit() -> None:
    vix_instrument = InstrumentIdentity("INDEX:INDIAVIX", Exchange.INDEX, "INDIA VIX", "INDIAVIX", None, None, InstrumentType.VOLATILITY_INDEX, "India VIX")
    vix = IndexMarketObservation("vix-1", vix_instrument, Decimal("14.2"), Decimal("13.8"), None, None, None, None, None, T, provenance(), freshness(), DataQuality.HIGH)
    assert vix.instrument.instrument_type is InstrumentType.VOLATILITY_INDEX
    assert bar().adjustment_status is AdjustmentStatus.RAW
    degraded = SessionAwareFreshnessEvaluator(FreshnessThresholds(timedelta(minutes=1), timedelta(minutes=5), timedelta(days=1), timedelta(minutes=5), timedelta(minutes=5))).evaluate(
        observed_at=T - timedelta(minutes=2), evaluated_at=T, kind="quote", session_state=MarketSessionState.DEGRADED
    )
    assert degraded.state is FreshnessState.STALE and degraded.warnings == ("feed/session is degraded",)


def test_historical_request_and_timezone_validation_fail_closed() -> None:
    with pytest.raises(ValueError, match="start"):
        HistoricalBarsRequest(instrument(), Timeframe.DAILY, T, T - timedelta(days=1))
    with pytest.raises(MarketDataError, match="timezone-aware"):
        MarketDataNormalizer().bar({"start_time": datetime(2026, 1, 1), "end_time": T, "open": 1, "high": 2, "low": 1, "close": 2}, bar_id="bad", instrument=instrument(), timeframe=Timeframe.DAILY, provenance=provenance())


def test_quote_bar_quality_checks_detect_material_corruption_and_ordering() -> None:
    invalid = MarketDataNormalizer().bar({"start_time": T - timedelta(minutes=5), "end_time": T, "open": 100, "high": 90, "low": 95, "close": 96, "volume": -1}, bar_id="bad", instrument=instrument(), timeframe=Timeframe.FIVE_MINUTES, provenance=provenance())
    with pytest.raises(MarketDataQualityError, match="high"):
        MarketDataQualityValidator.validate_bar(invalid)
    first, second = bar("same"), bar("same")
    with pytest.raises(MarketDataQualityError, match="Duplicate"):
        MarketDataQualityValidator.validate_bar_collection((first, second))
    with pytest.raises(MarketDataQualityError, match="Duplicate"):
        MarketDataQualityValidator.validate_bar_collection((bar("same-time-a"), bar("same-time-b")))
    earlier = bar("earlier", T - timedelta(minutes=10))
    with pytest.raises(MarketDataQualityError, match="chronological"):
        MarketDataQualityValidator.validate_bar_collection((bar(), earlier))
    negative_volume = MarketDataNormalizer().quote({"last_price": 1, "volume": -1}, quote_id="negative", instrument=instrument(), provenance=provenance(), freshness=freshness())
    with pytest.raises(MarketDataQualityError, match="volume"):
        MarketDataQualityValidator.validate_quote(negative_volume)


def test_freshness_is_threshold_and_session_aware_without_calendar_guesses() -> None:
    evaluator = SessionAwareFreshnessEvaluator(FreshnessThresholds(timedelta(minutes=1), timedelta(minutes=5), timedelta(days=1), timedelta(minutes=5), timedelta(minutes=5)))
    assert evaluator.evaluate(observed_at=T - timedelta(seconds=30), evaluated_at=T, kind="quote", session_state=MarketSessionState.OPEN).state is FreshnessState.FRESH
    assert evaluator.evaluate(observed_at=T - timedelta(minutes=3), evaluated_at=T, kind="quote", session_state=MarketSessionState.OPEN).state is FreshnessState.VERY_STALE
    closed = evaluator.evaluate(observed_at=T - timedelta(minutes=3), evaluated_at=T, kind="quote", session_state=MarketSessionState.CLOSED)
    assert closed.state is FreshnessState.FRESH and closed.threshold == timedelta(minutes=48)
    assert evaluator.evaluate(observed_at=None, evaluated_at=T, kind="breadth").state is FreshnessState.UNKNOWN


def test_registry_unknown_provider_has_no_silent_mock_fallback() -> None:
    registry = MarketDataProviderRegistry()
    registry.register("mock", provider())
    assert registry.create("mock").get_quote(instrument()) == quote()
    with pytest.raises(MarketDataError, match="unavailable"):
        registry.create("unconfigured-real-provider")
    with pytest.raises(ValueError, match="once"):
        registry.register("MOCK", provider())


def test_capabilities_and_sanitized_malformed_provider_errors() -> None:
    value = provider()
    assert value.capabilities().websocket is CapabilityState.UNSUPPORTED
    assert value.capabilities().vix is CapabilityState.SUPPORTED
    with pytest.raises(MarketDataError, match="malformed numeric") as caught:
        MarketDataNormalizer().quote({"last_price": object()}, quote_id="bad", instrument=instrument(), provenance=provenance(), freshness=freshness())
    assert "vendor-token" not in str(caught.value)


def test_deterministic_writer_store_round_trip_and_no_overwrite() -> None:
    store = InMemoryMarketDataStore()
    writer = MarketDataSnapshotWriter(store)
    writer.write(quote())
    writer.write(bar())
    writer.write(index())
    writer.write(breadth())
    writer.write(MarketSessionObservation("session-1", Exchange.NSE, MarketSessionState.DEGRADED, T, provenance()))
    assert store.latest_quote(instrument().instrument_id) == quote()
    assert store.historical_bars(instrument().instrument_id) == (bar(),)
    assert store.latest_index(index().instrument.instrument_id) == index()
    assert store.latest_breadth("NIFTY500") == breadth()
    assert store.latest_session("NSE").state is MarketSessionState.DEGRADED
    with pytest.raises(ValueError, match="immutable"):
        writer.write(quote())
    with pytest.raises(TypeError, match="canonical"):
        writer.write(object())  # type: ignore[arg-type]


def test_canonical_facts_cross_to_existing_validated_engine_boundary_without_provider_types() -> None:
    price = price_bar_observation(bar())
    market = index_observation(index())
    assert price.kind.value == "price_bar" and price.payload["close"] == 102.0
    assert market.kind.value == "index" and market.payload["value"] == 25000.0
    assert price.provenance.source_identifier == "vendor-token-739"


def test_provider_boundary_has_no_network_or_analysis_engine_side_effects() -> None:
    import app.market_data.normalization as normalization
    import app.market_data.providers as providers
    import app.market_data.store as store
    source = "\n".join((inspect.getsource(normalization), inspect.getsource(providers), inspect.getsource(store))).lower()
    assert not any(token in source for token in ("requests.", "httpx.", "urllib", "websocket", "broker", "demat", "place_order", "decision score", "activate_strategy"))
    assert provider().get_quote(instrument()).instrument.provider_mappings[0].provider_instrument_reference == "vendor-token-739"
