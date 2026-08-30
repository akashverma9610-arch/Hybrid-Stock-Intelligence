from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.market_data.models import (
    CanonicalQuote, Exchange, FreshnessAssessment, FreshnessState, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, MarketSessionState,
)
from app.market_data.store import CoreSnapshotQuoteStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import CoverageDomain, NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.readiness import DataReadinessService


T = datetime(2026, 8, 24, 10, tzinfo=UTC)


def quote() -> CanonicalQuote:
    instrument = InstrumentIdentity("NSE:INE436A01026", Exchange.NSE, "ANSALAPI", "ANSALAPI", "INE436A01026", "EQ", InstrumentType.NSE_EQUITY, "Ansal Properties")
    return CanonicalQuote(
        "kotak-neo-quote:NSE:INE436A01026:fixture", instrument, Decimal("12.50"), None, None, None, None,
        None, None, None, None, None, None, None, None,
        MarketDataProvenance("KOTAK_NEO", "fixture-token", T, T, T, "kotak-neo-v1", "quotes"),
        FreshnessAssessment(FreshnessState.STALE, T, T, None, None, MarketSessionState.CLOSED), DataQuality.HIGH,
    )


def test_canonical_quote_persists_reopens_and_rejects_overwrite(tmp_path) -> None:
    path = tmp_path / "quotes.sqlite"
    value = quote()
    first = CoreSnapshotQuoteStore(SQLiteCoreApiSnapshotRepository(path))
    first.save_quote(value)
    assert first.latest_quote(value.instrument.instrument_id) == value
    with pytest.raises(ValueError, match="immutable"):
        first.save_quote(value)

    reopened = CoreSnapshotQuoteStore(SQLiteCoreApiSnapshotRepository(path))
    assert reopened.latest_quote(value.instrument.instrument_id) == value


def test_quote_store_contributes_only_truthful_current_quote_coverage(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "coverage.sqlite")
    store = CoreSnapshotQuoteStore(repository)
    value = quote()
    store.save_quote(value)
    instrument = NseEquityInstrument(value.instrument.instrument_id, "ANSALAPI", value.instrument.isin, None, None, "ACTIVE", None, True, T, "fixture")
    snapshot = UniverseSnapshot("universe", T, "fixture", 1, 1, 0, (), "v1", "checksum", (instrument.instrument_id,))
    coverage = DataReadinessService(quote_store=store, clock=lambda: T).assess(snapshot=snapshot, instruments=(instrument,), as_of=T).coverage
    current = next(item for item in coverage if item.domain is CoverageDomain.CURRENT_QUOTES)
    assert (current.ready, current.stale, current.missing) == (0, 1, 0)
