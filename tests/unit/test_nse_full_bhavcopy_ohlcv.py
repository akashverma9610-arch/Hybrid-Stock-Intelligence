from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.market_data.nse_full_bhavcopy import (
    NSE_OFFICIAL_BAR_PROVIDER, NseFullBhavcopyOhlcvImporter, NseFullBhavcopyTarget,
)
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 1, 14, 20, tzinfo=UTC)
SOURCE = "https://archives.nseindia.com/products/content/sec_bhavdata_full_01092026.csv"


def instrument(symbol: str = "ALPHA", isin: str = "INE000A01001") -> NseEquityInstrument:
    return NseEquityInstrument("NSE:" + isin, symbol, isin, None, None, "LISTED", None, True, T, "NSE", security_type="EQUITY", exchange="NSE")


def csv_row(*, symbol: str = "ALPHA", date: str = "01-Sep-2026", open_: str = "100", high: str = "105", low: str = "99", close: str = "102", volume: str = "1000") -> str:
    return f"{symbol}, EQ, {date}, {open_}, {high}, {low}, {close}, {volume}, 12.5, 20\n"


def source(tmp_path, content: str):
    path = tmp_path / "sec_bhavdata_full_01092026.csv"
    path.write_text("SYMBOL, SERIES, DATE1, OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, TTL_TRD_QNTY, TURNOVER_LACS, NO_OF_TRADES\n" + content, encoding="utf-8")
    return path


def test_exact_official_full_bhavcopy_import_preserves_ohlcv_and_ist_session(tmp_path):
    target = NseFullBhavcopyTarget.from_instrument(instrument())
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    result = NseFullBhavcopyOhlcvImporter(store, (target,)).import_file(source(tmp_path, csv_row()), source_url=SOURCE, retrieved_at=T)
    assert result.source_columns[:4] == ("SYMBOL", " SERIES", " DATE1", " OPEN_PRICE")
    assert (result.accepted, result.rejected, result.missing_targets) == (1, 0, 0)
    bar = store.latest(target.canonical_instrument_id, Timeframe.DAILY, 1)[0]
    assert (bar.open, bar.high, bar.low, bar.close, bar.volume, bar.turnover, bar.trade_count) == (Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), 1000, Decimal("1250000.0"), 20)
    assert bar.end_time == datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
    assert bar.provenance.provider == NSE_OFFICIAL_BAR_PROVIDER
    assert "SOURCE_ISIN_NOT_PRESENT_PREVALIDATED_TARGET_MAPPING" in bar.warnings


def test_symbol_absence_or_invalid_raw_ohlcv_remains_fail_closed(tmp_path):
    target = NseFullBhavcopyTarget.from_instrument(instrument())
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    missing = NseFullBhavcopyOhlcvImporter(store, (target,)).import_file(source(tmp_path, csv_row(symbol="OTHER")), source_url=SOURCE, retrieved_at=T)
    assert missing.results[0].blocker == "OFFICIAL_NSE_EOD_OHLCV_UNAVAILABLE" and missing.accepted == 0
    invalid = NseFullBhavcopyOhlcvImporter(store, (target,)).import_file(source(tmp_path, csv_row(high="90")), source_url=SOURCE, retrieved_at=T)
    assert invalid.accepted == 0 and invalid.rejected == 1


def test_official_and_upstox_provider_versions_coexist_and_official_wins(tmp_path):
    target = NseFullBhavcopyTarget.from_instrument(instrument())
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    identity = InstrumentIdentity(target.canonical_instrument_id, Exchange.NSE, target.symbol, target.symbol, target.isin, "EQ", InstrumentType.NSE_EQUITY, None)
    end = datetime(2026, 8, 31, 18, 30, tzinfo=UTC)
    upstox = CanonicalOHLCVBar("upstox-fixture", identity, Timeframe.DAILY, end - timedelta(days=1), end, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), 1000, Decimal("1250000"), 20, AdjustmentStatus.UNKNOWN, MarketDataProvenance("UPSTOX", "key", end, end, T - timedelta(minutes=1), "fixture"), DataQuality.HIGH)
    store.upsert(upstox)
    importer = NseFullBhavcopyOhlcvImporter(store, (target,))
    first = importer.import_file(source(tmp_path, csv_row()), source_url=SOURCE, retrieved_at=T)
    second = importer.import_file(source(tmp_path, csv_row()), source_url=SOURCE, retrieved_at=T)
    assert (first.accepted, second.duplicates, store.raw_count(target.canonical_instrument_id, Timeframe.DAILY)) == (1, 1, 2)
    assert store.latest(target.canonical_instrument_id, Timeframe.DAILY, 1)[0].provenance.provider == NSE_OFFICIAL_BAR_PROVIDER


def test_importer_rejects_unofficial_source_ambiguous_targets_and_future_pit(tmp_path):
    target = NseFullBhavcopyTarget.from_instrument(instrument())
    with pytest.raises(ValueError, match="TARGET_SYMBOL_AMBIGUOUS"):
        NseFullBhavcopyOhlcvImporter(SQLiteHistoricalBarStore(tmp_path / "a.sqlite"), (target, target))
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    importer = NseFullBhavcopyOhlcvImporter(store, (target,))
    with pytest.raises(ValueError, match="OFFICIAL_SOURCE_REQUIRED"):
        importer.import_file(source(tmp_path, csv_row()), source_url="https://example.invalid/file.csv", retrieved_at=T)
    importer.import_file(source(tmp_path, csv_row()), source_url=SOURCE, retrieved_at=T)
    assert store.range(target.canonical_instrument_id, Timeframe.DAILY, datetime(2026, 8, 30, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC), as_of=T - timedelta(seconds=1)) == ()


def test_hash_verified_local_archive_suffix_is_accepted_but_arbitrary_names_are_not(tmp_path):
    target = NseFullBhavcopyTarget.from_instrument(instrument())
    original = source(tmp_path, csv_row())
    archived = tmp_path / "sec_bhavdata_full_01092026-0123456789ab.csv"
    original.rename(archived)
    result = NseFullBhavcopyOhlcvImporter(SQLiteHistoricalBarStore(tmp_path / "bars.sqlite"), (target,)).import_file(archived, source_url=SOURCE, retrieved_at=T)
    assert result.accepted == 1
    arbitrary = tmp_path / "sec_bhavdata_full_01092026-untrusted.csv"
    archived.rename(arbitrary)
    with pytest.raises(ValueError, match="FILENAME_UNSUPPORTED"):
        NseFullBhavcopyOhlcvImporter(SQLiteHistoricalBarStore(tmp_path / "other.sqlite"), (target,)).import_file(arbitrary, source_url=SOURCE, retrieved_at=T)
