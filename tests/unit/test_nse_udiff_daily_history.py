from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO, StringIO
import csv
import zipfile

import pytest

from app.domain.models import DataQuality
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, Timeframe,
)
from app.market_data.nse_udiff_daily_history import (
    NSE_UDIFF_BAR_PROVIDER, NSE_UDIFF_START, NseUdiffDailyFetchResult,
    NseUdiffDailyHistoryBackfill, NseUdiffDailyHistoryStore,
    NseUdiffDailySource, NseUdiffDailyStatus, NseUdiffDailyTarget,
    UDIFF_COLUMNS, nse_udiff_acquisition_id, nse_udiff_daily_url,
)
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot


T = datetime(2026, 9, 6, 10, 30, tzinfo=UTC)
D = date(2024, 7, 8)


def target(symbol: str = "ALPHA", isin: str = "INE000A01001") -> NseUdiffDailyTarget:
    return NseUdiffDailyTarget.from_instrument(NseEquityInstrument(
        f"NSE:{isin}", symbol, isin, None, None, "LISTED", None, True, T,
        "NSE", security_type="EQUITY", exchange="NSE",
    ))


def snapshot() -> UniverseSnapshot:
    return UniverseSnapshot("nse-current", T, "NSE", 1, 1, 0, (), "v1", "checksum", ("NSE:INE000A01001",))


def row(*, symbol: str = "ALPHA", isin: str = "INE000A01001", high: str = "105", volume: str = "1000") -> dict[str, str]:
    value = {name: "" for name in UDIFF_COLUMNS}
    value.update({
        "TradDt": "2024-07-08", "BizDt": "2024-07-08", "Sgmt": "CM", "Src": "NSE",
        "FinInstrmTp": "STK", "FinInstrmId": "4963", "ISIN": isin, "TckrSymb": symbol,
        "SctySrs": "EQ", "FinInstrmNm": symbol, "OpnPric": "100", "HghPric": high,
        "LwPric": "99", "ClsPric": "102", "LastPric": "102", "PrvsClsgPric": "98",
        "TtlTradgVol": volume, "TtlTrfVal": "102000", "TtlNbOfTxsExctd": "50", "SsnId": "F1",
    })
    return value


def archive(rows: tuple[dict[str, str], ...] = (row(),), *, columns: tuple[str, ...] = UDIFF_COLUMNS, filename: str | None = None) -> bytes:
    body = StringIO()
    writer = csv.DictWriter(body, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for value in rows:
        writer.writerow(value)
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr(filename or "BhavCopy_NSE_CM_0_0_0_20240708_F_0000.csv", body.getvalue())
    return output.getvalue()


class Source(NseUdiffDailySource):
    def __init__(self, result: NseUdiffDailyFetchResult) -> None:
        self.result, self.calls = result, 0

    def fetch(self, trade_date: date) -> NseUdiffDailyFetchResult:
        self.calls += 1
        assert trade_date == self.result.trade_date
        return self.result


def backfill(tmp_path, source: Source, *, current_target: NseUdiffDailyTarget | None = None):
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'core.sqlite'}"))
    store = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    universe = snapshot()
    service = NseUdiffDailyHistoryBackfill(
        source=source, evidence=NseUdiffDailyHistoryStore(repository), bars=store,
        targets=(current_target or target(),), acquisition_id=nse_udiff_acquisition_id(universe, start=D, end=D),
        universe_snapshot=universe, requested_start=D, requested_end=D,
    )
    return service, store, repository


def result(raw: bytes) -> NseUdiffDailyFetchResult:
    return NseUdiffDailyFetchResult(NseUdiffDailyStatus.ARTIFACT_VALID, D, nse_udiff_daily_url(D), T, raw)


def test_exact_era_and_url_are_fail_closed():
    assert nse_udiff_daily_url(D).endswith("20240708_F_0000.csv.zip")
    with pytest.raises(ValueError, match="LEGACY"):
        nse_udiff_daily_url(D - timedelta(days=1))


def test_retains_exact_artifact_schema_source_basis_and_hsi_observed_at(tmp_path):
    source = Source(result(archive()))
    service, store, repository = backfill(tmp_path, source)
    report = service.run()
    receipt = report.receipts[0]
    artifact = NseUdiffDailyHistoryStore(repository).artifact(report.acquisition_id, D)
    assert artifact is not None
    assert artifact.source_columns == UDIFF_COLUMNS
    assert artifact.row_count == 1 and artifact.fingerprint.startswith("sha256:")
    assert receipt.inserted == 1 and receipt.exact_identity_rows == 1
    bar = store.raw_range("NSE:INE000A01001", Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), datetime(2024, 7, 10, tzinfo=UTC))[0]
    assert bar.provenance.provider == NSE_UDIFF_BAR_PROVIDER
    assert bar.provenance.received_at == T and bar.provenance.provider_timestamp is None
    assert bar.adjustment_status is AdjustmentStatus.RAW
    assert "EXCHANGE_EOD_TRADE_PRICE" in bar.warnings
    assert "DAILY_VWAP_FROM_UDIFF_NOT_APPLICABLE" in bar.warnings
    assert any(item.startswith("NSE_UDIFF_SESSION:F1") for item in bar.warnings)


def test_schema_drift_is_retained_and_fails_closed(tmp_path):
    source = Source(result(archive(columns=UDIFF_COLUMNS[:-1])))
    service, store, repository = backfill(tmp_path, source)
    receipt = service.run().receipts[0]
    artifact = NseUdiffDailyHistoryStore(repository).artifact(receipt.acquisition_id, D)
    assert receipt.status is NseUdiffDailyStatus.SOURCE_SCHEMA_DRIFT
    assert receipt.error_code == "SOURCE_SCHEMA_DRIFT" and receipt.inserted == 0
    assert artifact is not None and artifact.raw_zip_base64 and artifact.schema_status is NseUdiffDailyStatus.SOURCE_SCHEMA_DRIFT
    assert store.raw_count("NSE:INE000A01001", Timeframe.DAILY) == 0


def test_identity_discontinuity_and_invalid_ohlc_remain_explicit(tmp_path):
    source = Source(result(archive((row(symbol="RENAMED"), row(high="90")))))
    service, store, _ = backfill(tmp_path, source)
    receipt = service.run().receipts[0]
    assert (receipt.identity_discontinuities, receipt.invalid_rows, receipt.inserted) == (1, 1, 0)
    assert store.raw_count("NSE:INE000A01001", Timeframe.DAILY) == 0


def test_zero_volume_is_preserved_not_repaired_or_rejected(tmp_path):
    source = Source(result(archive((row(volume="0"),))))
    service, store, _ = backfill(tmp_path, source)
    receipt = service.run().receipts[0]
    bar = store.raw_range("NSE:INE000A01001", Timeframe.DAILY, datetime(2024, 7, 7, tzinfo=UTC), T)[0]
    assert (receipt.inserted, receipt.zero_volume_rows, bar.volume) == (1, 1, 0)


def test_replay_uses_immutable_artifact_and_creates_no_new_bar(tmp_path):
    source = Source(result(archive()))
    service, store, _ = backfill(tmp_path, source)
    first = service.run()
    second = service.run()
    assert (first.inserted, second.inserted, second.replayed_sessions, source.calls) == (1, 0, 1, 1)
    assert store.raw_count("NSE:INE000A01001", Timeframe.DAILY) == 1


def test_udiff_coexists_with_upstox_without_implicit_technical_fallback(tmp_path):
    source = Source(result(archive()))
    service, store, _ = backfill(tmp_path, source)
    instrument = target().instrument
    start = datetime(2024, 7, 7, 18, 30, tzinfo=UTC)
    store.upsert(CanonicalOHLCVBar(
        "upstox-existing", instrument, Timeframe.DAILY, start, start + timedelta(days=1),
        Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), 1000, Decimal("102000"), 50,
        AdjustmentStatus.UNKNOWN, MarketDataProvenance("UPSTOX", "existing", start, None, T, "fixture"), DataQuality.HIGH,
    ))
    receipt = service.run().receipts[0]
    assert receipt.inserted == 1
    assert store.raw_count("NSE:INE000A01001", Timeframe.DAILY) == 2
    assert store.latest("NSE:INE000A01001", Timeframe.DAILY, 1) == ()
    raw = store.raw_range("NSE:INE000A01001", Timeframe.DAILY, start, T)
    assert next(b for b in raw if b.provenance.provider == "UPSTOX").adjustment_status is AdjustmentStatus.UNKNOWN


def test_source_unavailable_is_not_inferred_as_a_holiday(tmp_path):
    source = Source(NseUdiffDailyFetchResult(NseUdiffDailyStatus.SOURCE_UNAVAILABLE, D, nse_udiff_daily_url(D), T, None, "NSE_UDIFF_ARTIFACT_UNAVAILABLE"))
    service, store, _ = backfill(tmp_path, source)
    receipt = service.run().receipts[0]
    assert receipt.status is NseUdiffDailyStatus.SOURCE_UNAVAILABLE
    assert receipt.error_code == "NSE_UDIFF_ARTIFACT_UNAVAILABLE" and store.raw_count("NSE:INE000A01001", Timeframe.DAILY) == 0
