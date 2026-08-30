from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.data_coverage.local import compose_coverage_records
from app.data_coverage.models import DataCoverageDomain, DataCoverageStatus
from app.domain.models import DataQuality
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance, Timeframe
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore, build_universe_snapshot


T = datetime(2026, 8, 24, tzinfo=UTC)


def _instrument(symbol: str = "REAL"):
    return NseEquityInstrument(f"NSE:{symbol}", symbol, "INE000A01001", None, None, "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT")


def _identity(identifier: str, symbol: str, kind: InstrumentType = InstrumentType.NSE_EQUITY):
    return InstrumentIdentity(identifier, Exchange.INDEX if kind is InstrumentType.BROAD_INDEX else Exchange.NSE, symbol, symbol, None, None, kind, symbol)


def _bar(identity: InstrumentIdentity, number: int):
    end = T - timedelta(days=number + 1)
    return CanonicalOHLCVBar(
        f"bar:{identity.instrument_id}:{number}", identity, Timeframe.DAILY, end - timedelta(days=1), end,
        Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 1000, None, None, AdjustmentStatus.RAW,
        MarketDataProvenance("approved-offline", identity.instrument_id, end, end, T, "canonical-import-v1", "local-file"), DataQuality.HIGH,
    )


def test_real_package_coverage_uses_canonical_252_bars_and_nifty500_without_fabricating_integrity(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    instrument = _instrument(); snapshot = build_universe_snapshot(snapshot_id="frozen", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=(instrument,))
    CoreUniverseAnalysisStore(repository).save_universe_snapshot(snapshot)
    bars = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    stock = _identity(instrument.instrument_id, instrument.symbol)
    nifty = _identity("NIFTY_500", "NIFTY 500", InstrumentType.BROAD_INDEX)
    for number in range(252):
        assert bars.upsert(_bar(stock, number)).value == "INSERTED"
        assert bars.upsert(_bar(nifty, number)).value == "INSERTED"
    record = compose_coverage_records(repository=repository, historical=bars, snapshot=snapshot, instruments=(instrument,), persist=False)[0]
    by_domain = {item.domain: item for item in record.domains}
    assert by_domain[DataCoverageDomain.HISTORICAL_OHLCV].status is DataCoverageStatus.READY
    assert by_domain[DataCoverageDomain.MARKET_CONTEXT].status is DataCoverageStatus.READY
    # Raw bars are retained, but absent corporate-action provenance stays an
    # explicit integrity gap rather than being called fully adjusted/safe.
    assert by_domain[DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY].status is DataCoverageStatus.PARTIAL
    assert by_domain[DataCoverageDomain.DELIVERY_DATA].status is DataCoverageStatus.MISSING
    assert by_domain[DataCoverageDomain.FUNDAMENTALS].status is DataCoverageStatus.MISSING
    assert by_domain[DataCoverageDomain.SECTOR_INDUSTRY].status is DataCoverageStatus.MISSING
    bars.close(); repository.close()


def test_short_history_remains_partial_and_cannot_claim_nifty_context(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    instrument = _instrument(); snapshot = build_universe_snapshot(snapshot_id="frozen", as_of=T, source="NSE_OFFICIAL_EXPORT", instruments=(instrument,))
    bars = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite"); stock = _identity(instrument.instrument_id, instrument.symbol)
    for number in range(20):
        bars.upsert(_bar(stock, number))
    record = compose_coverage_records(repository=repository, historical=bars, snapshot=snapshot, instruments=(instrument,), persist=False)[0]
    by_domain = {item.domain: item for item in record.domains}
    assert by_domain[DataCoverageDomain.HISTORICAL_OHLCV].status is DataCoverageStatus.PARTIAL
    assert by_domain[DataCoverageDomain.MARKET_CONTEXT].status is DataCoverageStatus.MISSING
    bars.close(); repository.close()
