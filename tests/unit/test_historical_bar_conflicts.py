"""Append-only evidence tests for same-provider historical bar revisions."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domain.models import DataQuality
from app.market_data.historical import HistoricalIngestionService, SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, HistoricalBarsRequest,
    InstrumentIdentity, InstrumentType, MarketDataProvenance, ProviderInstrumentMapping,
    Timeframe,
)


T = datetime(2026, 8, 30, 12, tzinfo=UTC)
I = InstrumentIdentity(
    "NSE:ALPHA", Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ",
    InstrumentType.NSE_EQUITY, "Alpha Ltd", provider_mappings=(
        ProviderInstrumentMapping("upstox", "NSE_EQ|INE000A01001", "ALPHA", "upstox-v3", "NSE_EQ"),
    ),
)


def _bar(*, provider: str = "upstox", close: str = "102", volume: int | None = 1000) -> CanonicalOHLCVBar:
    return CanonicalOHLCVBar(
        "upstox:alpha:20260828", I, Timeframe.DAILY, T - timedelta(days=2), T - timedelta(days=1),
        Decimal("100"), Decimal("105"), Decimal("99"), Decimal(close), volume, Decimal("102000"), 10,
        AdjustmentStatus.UNKNOWN,
        MarketDataProvenance(
            provider, "NSE_EQ|INE000A01001", T - timedelta(days=1), T - timedelta(days=1), T,
            "upstox-history-v3", "fixture-run", "upstox-v3-historical-candle", "upstox-v3",
        ),
        DataQuality.HIGH,
    )


class _Provider:
    def __init__(self, values: tuple[CanonicalOHLCVBar, ...]) -> None:
        self._values = values
        self.requests: list[HistoricalBarsRequest] = []

    def get_historical_bars(self, request: HistoricalBarsRequest) -> tuple[CanonicalOHLCVBar, ...]:
        self.requests.append(request)
        return self._values


def _request() -> HistoricalBarsRequest:
    return HistoricalBarsRequest(I, Timeframe.DAILY, T - timedelta(days=3), T, AdjustmentStatus.UNKNOWN, "upstox")


def _ingest(store: SQLiteHistoricalBarStore, *values: CanonicalOHLCVBar, run_id: str = "run:conflict"):
    return HistoricalIngestionService(_Provider(tuple(values)), store, clock=lambda: T).ingest(
        _request(), ingestion_run_id=run_id,
    )


def test_same_provider_revision_creates_complete_immutable_artifact_and_preserves_accepted_bar(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    stored, incoming = _bar(), _bar(close="103", volume=1100)
    assert store.upsert(stored).value == "INSERTED"

    report = _ingest(store, incoming, run_id="evidence-refresh:ohlcv:fixture")
    values = store.list_conflict_artifacts()

    assert report.conflict_count == 1 and len(values) == 1
    artifact = values[0]
    assert store.same_provider_bar(incoming) == stored
    assert artifact.canonical_instrument_id == I.instrument_id
    assert artifact.start_time == stored.start_time and artifact.end_time == stored.end_time
    assert artifact.stored_values.close == Decimal("102") and artifact.incoming_values.close == Decimal("103")
    assert artifact.stored_values.volume == 1000 and artifact.incoming_values.volume == 1100
    assert artifact.differing_fields == ("close", "volume")
    assert artifact.stored_lineage.provider_identity == "upstox"
    assert artifact.stored_lineage.mapping_version == "upstox-v3"
    assert artifact.stored_lineage.normalizer_version == "upstox-history-v3"
    assert artifact.stored_lineage.source_identity == "upstox-v3-historical-candle"
    assert artifact.ingestion_run_id == "evidence-refresh:ohlcv:fixture"
    assert len(artifact.conflict_fingerprint) == 64


def test_exact_rerun_and_reconciliation_are_idempotent_but_second_revision_is_distinct(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    stored, first, second = _bar(), _bar(close="103"), _bar(close="104")
    store.upsert(stored)

    assert _ingest(store, first, run_id="run:first").conflict_count == 1
    assert _ingest(store, first, run_id="run:reconciliation").conflict_count == 1
    assert len(store.list_conflict_artifacts()) == 1
    assert _ingest(store, second, run_id="run:second").conflict_count == 1
    values = store.list_conflict_artifacts(instrument_id=I.instrument_id)
    assert len(values) == 2
    assert {item.incoming_values.close for item in values} == {Decimal("103"), Decimal("104")}
    assert len({item.conflict_fingerprint for item in values}) == 2


def test_conflict_artifact_is_durable_across_store_reopen(tmp_path) -> None:
    path = tmp_path / "history.sqlite"
    store = SQLiteHistoricalBarStore(path)
    store.upsert(_bar())
    _ingest(store, _bar(close="103"))
    expected = store.list_conflict_artifacts()
    store.close()

    reopened = SQLiteHistoricalBarStore(path)
    assert reopened.list_conflict_artifacts() == expected


def test_same_response_conflict_is_captured_with_exact_value_difference_and_no_auto_selection(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    stored, incoming = _bar(), _bar(close="103")
    report = _ingest(store, stored, incoming)
    artifact = store.list_conflict_artifacts()[0]

    assert report.accepted_count == 1 and report.conflict_count == 1
    assert artifact.differing_fields == ("close",)
    assert store.range(I.instrument_id, Timeframe.DAILY, stored.start_time, stored.end_time) == (stored,)


def test_cross_provider_and_legacy_unknown_source_remain_separate_observations_without_conflict_artifacts(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    upstox = _bar()
    yahoo = replace(_bar(provider="yfinance", close="103"), bar_id="yahoo:alpha:20260828")
    legacy = replace(_bar(provider="unknown_existing_source", close="104"), bar_id="legacy:alpha:20260828")

    assert store.upsert(upstox).value == "INSERTED"
    assert store.upsert(yahoo).value == "INSERTED"
    assert store.upsert(legacy).value == "INSERTED"
    assert store.list_conflict_artifacts() == ()
    assert store.raw_count(I.instrument_id, Timeframe.DAILY) == 3


def test_equal_same_provider_bar_is_a_duplicate_without_artifact_and_lookup_is_factual(tmp_path) -> None:
    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    stored = _bar()
    store.upsert(stored)

    report = _ingest(store, stored)

    assert report.duplicate_count == 1 and report.conflict_count == 0
    assert store.list_conflict_artifacts() == ()
    assert store.has_conflict_artifact(I.instrument_id) is False


def test_read_only_cli_lists_stored_and_incoming_values_with_exact_instrument_filter(tmp_path) -> None:
    from app.runtime.cli import main

    store = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    store.upsert(_bar())
    _ingest(store, _bar(close="103"))
    output: list[str] = []

    assert main(
        ["historical-bar-conflicts", "--instrument", I.instrument_id],
        historical_conflict_store_factory=lambda: store,
        output=output.append,
    ) == 0

    assert output[0] == f"conflicts=1 instrument={I.instrument_id}"
    assert "differing_fields=close" in output[1]
    assert "stored_values=open=100" in output[1]
    assert "incoming_values=open=100" in output[1]
