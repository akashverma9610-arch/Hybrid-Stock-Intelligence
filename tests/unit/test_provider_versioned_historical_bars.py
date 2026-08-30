from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.market_data.historical import (
    BarWriteOutcome, MarketBarReconciliationStatus, SQLiteHistoricalBarStore,
    reconcile_market_bars, resolve_market_bar,
)
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)


T = datetime(2026, 8, 28, tzinfo=UTC)
I = InstrumentIdentity("NIFTY_500", Exchange.INDEX, "NIFTY 500", "NIFTY 500", None, None, InstrumentType.BROAD_INDEX, "NIFTY 500")


def _bar(provider: str, *, close: str = "100", volume: int | None = 1000) -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(
        f"{provider}-bar", I, Timeframe.DAILY, T - timedelta(days=1), T,
        Decimal("99"), Decimal("101"), Decimal("98"), Decimal(close), volume, None, None,
        AdjustmentStatus.UNKNOWN if provider == "upstox" else AdjustmentStatus.RAW,
        MarketDataProvenance(provider, f"{provider}:NIFTY500", T, T, T, "v1", source_reference=provider), DataQuality.HIGH,
    )


def test_yahoo_and_upstox_coexist_immutably_with_one_canonical_upstox_bar(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    yahoo, upstox = _bar("yfinance", close="100"), _bar("upstox", close="100.1")
    assert store.upsert(yahoo) is BarWriteOutcome.INSERTED
    assert store.upsert(upstox) is BarWriteOutcome.INSERTED
    raw = store.raw_range(I.instrument_id, Timeframe.DAILY, yahoo.start_time, yahoo.end_time)
    assert {item.provenance.provider for item in raw} == {"yfinance", "upstox"}
    assert store.range(I.instrument_id, Timeframe.DAILY, yahoo.start_time, yahoo.end_time) == (upstox,)
    assert store.raw_count(I.instrument_id, Timeframe.DAILY) == 2 and store.count(I.instrument_id, Timeframe.DAILY) == 1


def test_same_provider_duplicate_is_idempotent_and_revision_never_overwrites(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    original = _bar("upstox")
    assert store.upsert(original) is BarWriteOutcome.INSERTED
    assert store.upsert(original) is BarWriteOutcome.IDENTICAL
    assert store.upsert(replace(original, close=Decimal("101"))) is BarWriteOutcome.CONFLICT
    assert store.raw_range(I.instrument_id, Timeframe.DAILY, original.start_time, original.end_time) == (original,)


def test_resolver_keeps_unknown_source_lowest_and_applies_contract_completeness() -> None:
    unknown = _bar("unknown_existing_source", close="99", volume=1000)
    yahoo = _bar("yfinance", close="100", volume=1000)
    upstox = _bar("upstox", close="101", volume=None)
    assert resolve_market_bar((unknown, yahoo, upstox)) == upstox
    assert resolve_market_bar((unknown, yahoo, upstox), require_volume=True) == yahoo
    assert upstox.volume is None


def test_legacy_single_source_rows_remain_readable_until_explicit_local_migration(tmp_path) -> None:
    path = tmp_path / "history.sqlite"
    legacy = _bar("yfinance")
    # Simulate the exact prior persistent SQLite table before U06R runs.
    import sqlite3
    connection = sqlite3.connect(path)
    connection.execute("""CREATE TABLE historical_bars (
        instrument_id TEXT, timeframe TEXT, start_time TEXT, end_time TEXT, bar_id TEXT, open TEXT, high TEXT, low TEXT, close TEXT,
        volume INTEGER, turnover TEXT, trade_count INTEGER, adjustment_status TEXT, instrument_json TEXT, provenance_json TEXT, quality TEXT, warnings_json TEXT,
        PRIMARY KEY (instrument_id,timeframe,start_time,end_time))""")
    from app.market_data.historical import _bar_values
    connection.execute("INSERT INTO historical_bars VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", _bar_values(legacy))
    connection.commit(); connection.close()
    reopened = SQLiteHistoricalBarStore(path)
    migrated = reopened.raw_range(I.instrument_id, Timeframe.DAILY, legacy.start_time, legacy.end_time)
    assert len(migrated) == 1 and migrated[0].close == legacy.close
    assert migrated[0].provenance.provider == "yfinance"
    with pytest.raises(RuntimeError, match="SQLITE_PROVIDER_VERSIONED_MIGRATION_REQUIRED"):
        reopened.upsert(_bar("upstox"))


def test_cross_provider_reconciliation_is_informational_and_never_mutates_raw_values() -> None:
    yahoo, upstox = _bar("yfinance", close="100"), replace(_bar("upstox", close="100.01"), adjustment_status=AdjustmentStatus.RAW)
    result = reconcile_market_bars((yahoo, upstox))
    assert result[0].status is MarketBarReconciliationStatus.ROUNDING_DIFFERENCE
    assert result[0].preferred_provider == "upstox" and result[0].secondary_provider == "yfinance"
    assert yahoo.close == Decimal("100") and upstox.close == Decimal("100.01")
