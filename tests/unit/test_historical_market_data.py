from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.market_data.historical import (
    BarWriteOutcome, HistoricalChunkPolicy, HistoricalCoverageStatus,
    HistoricalIngestionService, PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore,
    plan_historical_chunks,
)
from app.market_data.bridge import price_bar_observation
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, ErrorCode, Exchange, HistoricalBarsRequest,
    InstrumentIdentity, InstrumentType, MarketDataError, MarketDataProvenance,
    Timeframe,
)
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings


T = datetime(2026, 8, 20, 10, tzinfo=UTC)
I = InstrumentIdentity("nse:RELIANCE", Exchange.NSE, "RELIANCE", "RELIANCE-EQ", None, "EQ", InstrumentType.NSE_EQUITY, "Reliance")


def bar(number: int, *, open="100", high="105", low="99", close="102", volume=1000, adjustment=AdjustmentStatus.RAW, received_at=T) -> CanonicalOHLCVBar:
    start = T - timedelta(minutes=15) + timedelta(minutes=5 * number)
    end = start + timedelta(minutes=5)
    return CanonicalOHLCVBar(
        f"bar-{number}", I, Timeframe.FIVE_MINUTES, start, end, Decimal(open), Decimal(high), Decimal(low), Decimal(close), volume,
        Decimal("102000"), 10, adjustment,
        MarketDataProvenance("FIXTURE", "7383", end, end, received_at, "historical-v1", "run-1", "fixture-bars"), DataQuality.HIGH,
    )


class FixtureHistoricalProvider:
    def __init__(self, bars=(), *, fail=False): self.bars, self.fail = tuple(bars), fail
    def get_historical_bars(self, request):
        if self.fail: raise MarketDataError(ErrorCode.PROVIDER_UNAVAILABLE, "fixture unavailable")
        return tuple(item for item in self.bars if request.start <= item.end_time <= request.end)


def request(start=None, end=None) -> HistoricalBarsRequest:
    return HistoricalBarsRequest(I, Timeframe.FIVE_MINUTES, start or T - timedelta(minutes=15), end or T, AdjustmentStatus.RAW, "fixture")


def test_sqlite_historical_bar_store_preserves_decimal_timezone_range_latest_and_as_of(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    values = (bar(0), bar(1), bar(2))
    assert tuple(store.upsert(item) for item in values) == (BarWriteOutcome.INSERTED,) * 3
    restored = store.range(I.instrument_id, Timeframe.FIVE_MINUTES, request().start, request().end)
    assert restored == values and restored[0].open == Decimal("100") and restored[0].end_time.tzinfo is not None
    assert store.latest(I.instrument_id, Timeframe.FIVE_MINUTES, 2) == values[-2:]
    assert store.range(I.instrument_id, Timeframe.FIVE_MINUTES, request().start, request().end, as_of=values[1].end_time) == ()
    assert store.count(I.instrument_id, Timeframe.FIVE_MINUTES) == 3


def test_identical_duplicates_are_idempotent_and_conflicts_never_rewrite_history(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    original = bar(0)
    conflict = bar(0, close="103")
    assert store.upsert(original) is BarWriteOutcome.INSERTED
    assert store.upsert(original) is BarWriteOutcome.IDENTICAL
    assert store.upsert(conflict) is BarWriteOutcome.CONFLICT
    assert store.latest(I.instrument_id, Timeframe.FIVE_MINUTES, 1) == (original,)


def test_ingestion_sorts_provider_values_counts_duplicates_conflicts_and_partial_coverage(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    original, duplicate, conflict = bar(0), bar(0), bar(0, close="103")
    provider = FixtureHistoricalProvider((bar(2), conflict, bar(1), original, duplicate))
    report = HistoricalIngestionService(provider, store, clock=lambda: T + timedelta(days=1)).ingest(request())
    assert (report.received_count, report.accepted_count, report.duplicate_count, report.conflict_count) == (5, 3, 1, 1)
    assert "PROVIDER_REVISION_CONFLICT" in report.warnings
    assert report.coverage is HistoricalCoverageStatus.COMPLETE
    assert store.latest(I.instrument_id, Timeframe.FIVE_MINUTES, 3) == (original, bar(1), bar(2))


def test_invalid_bars_are_rejected_and_unavailable_provider_is_explicit(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    invalid = bar(0, high="90", volume=-1)
    rejected = HistoricalIngestionService(FixtureHistoricalProvider((invalid,)), store, clock=lambda: T + timedelta(days=1)).ingest(request())
    unavailable = HistoricalIngestionService(FixtureHistoricalProvider(fail=True), store, clock=lambda: T + timedelta(days=1)).ingest(request())
    assert rejected.rejected_count == 1 and rejected.accepted_count == 0
    assert unavailable.coverage is HistoricalCoverageStatus.UNAVAILABLE and "CHUNK_PROVIDER_UNAVAILABLE" in unavailable.warnings


def test_partial_provider_range_remains_explicitly_partial(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    report = HistoricalIngestionService(FixtureHistoricalProvider((bar(0),)), store, clock=lambda: T + timedelta(days=1)).ingest(request())
    assert report.coverage is HistoricalCoverageStatus.PARTIAL and report.earliest_bar == bar(0).start_time


def test_store_as_of_query_and_existing_domain_bridge_preserve_point_in_time_isolation(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    first = bar(0, received_at=bar(0).end_time)
    later = bar(1, received_at=bar(1).end_time)
    store.upsert(first); store.upsert(later)
    available = store.range(I.instrument_id, Timeframe.FIVE_MINUTES, request().start, request().end, as_of=first.end_time)
    assert available == (first,)
    observation = price_bar_observation(available[0])
    assert observation.id == first.bar_id and observation.payload["adjustment_status"] == "RAW"


def test_chunk_planning_is_stable_and_has_no_duplicate_boundary() -> None:
    chunks = plan_historical_chunks(request(T - timedelta(minutes=15), T), HistoricalChunkPolicy(timedelta(minutes=7)))
    assert chunks[0].start == T - timedelta(minutes=15)
    assert all(current.start > previous.end for previous, current in zip(chunks, chunks[1:]))


def test_conservative_gap_detection_marks_intrasession_discontinuity_as_possible_not_corrupt(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    store.upsert(bar(0)); store.upsert(bar(2))
    coverage = store.coverage(I.instrument_id, Timeframe.FIVE_MINUTES, request().start, request().end)
    assert coverage.status is HistoricalCoverageStatus.PARTIAL and coverage.gap_status.value == "POSSIBLE_GAP"


def test_postgresql_store_requires_explicit_postgresql_configuration() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(DatabaseSettings(DatabaseBackend.SQLITE, "sqlite:///:memory:")))


def test_historical_storage_boundary_has_no_provider_network_or_trading_side_effects() -> None:
    import inspect
    import app.market_data.historical as historical
    source = inspect.getsource(historical).lower()
    assert not any(token in source for token in ("requests.", "httpx.", "place_order", "modify_order", "cancel_order", "holdings", "demat", "scheduler"))
