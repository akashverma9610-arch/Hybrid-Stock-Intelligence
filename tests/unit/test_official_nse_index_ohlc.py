from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.official_nse_index_ohlc import (
    INDEX_LEVEL_BASIS,
    INDEX_RETURN_FAMILY,
    CanonicalOfficialIndexOhlcObservation,
    CoreSnapshotOfficialIndexOhlcStore,
    IndexOhlcWriteOutcome,
    OfficialIndexOhlcRetrievalArtifact,
    OfficialNseIndexOhlcSeriesRefresh,
    parse_official_nse_index_ohlc_response,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
INDEX = "NIFTY_50"


def _raw(*, close: str = "24175.65", index: str = "Nifty 50") -> bytes:
    return json.dumps([{
        "INDEX_NAME": index, "HistoricalDate": "31 Aug 2026",
        "OPEN": "24122.60", "HIGH": "24188.30", "LOW": "24076.85", "CLOSE": close,
    }]).encode()


def _observation(*, raw_hash: str = "a" * 64, close: str = "24175.65", retrieved_at: datetime = T):
    session, open_value, high, low, close_value = parse_official_nse_index_ohlc_response(_raw(close=close), "Nifty 50")[0]
    return CanonicalOfficialIndexOhlcObservation.create(
        canonical_index_id=INDEX, official_index_name="Nifty 50", session=session,
        open=open_value, high=high, low=low, close=close_value,
        retrieved_at=retrieved_at, raw_artifact_sha256=raw_hash,
    )


def _artifact(*, at: datetime = T):
    observation = _observation(retrieved_at=at)
    return OfficialIndexOhlcRetrievalArtifact(
        artifact_id="official-index-ohlc-artifact:" + "b" * 64,
        canonical_index_id=INDEX, official_index_name="Nifty 50",
        source_url="https://www.niftyindices.com/BackPage/getHistoricaldatatabletoString",
        requested_start="2025-09-01", requested_end="2026-09-01", retrieved_at=at,
        raw_artifact_sha256="b" * 64, row_count=1, earliest_session=observation.session,
        latest_session=observation.session, parser_version="nse-indices-historical-ohlc-v1",
        index_level_basis=INDEX_LEVEL_BASIS, index_return_family=INDEX_RETURN_FAMILY,
        local_path="data/official_sources/nse_index_ohlc_series/nifty_50.json",
    )


def test_official_parser_retains_only_exact_index_daily_ohlc_and_no_equity_fields() -> None:
    rows = parse_official_nse_index_ohlc_response(_raw(), "Nifty 50")
    assert rows == ((datetime(2026, 8, 31, 10, tzinfo=UTC), Decimal("24122.60"), Decimal("24188.30"), Decimal("24076.85"), Decimal("24175.65")),)
    with pytest.raises(ValueError, match="EXACT_INDEX_IDENTITY"):
        parse_official_nse_index_ohlc_response(_raw(index="Nifty 50 TRI"), "Nifty 50")
    with pytest.raises(ValueError, match="OHLC_UNAVAILABLE"):
        parse_official_nse_index_ohlc_response(_raw(close="-"), "Nifty 50")
    source = (Path(__file__).parents[2] / "app" / "market_data" / "official_nse_index_ohlc.py").read_text(encoding="utf-8")
    assert "from app.market_data.historical" not in source
    assert not any("upstox" in line.lower() for line in source.splitlines() if line.startswith("from ") or line.startswith("import "))


def test_index_observation_is_price_return_immutable_and_replay_safe(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotOfficialIndexOhlcStore(repository)
    first = _observation()
    # A changed artifact hash does not duplicate or conflict with an identical
    # official session level; the second raw document is retained separately.
    repeated = _observation(raw_hash="c" * 64, retrieved_at=T.replace(hour=13))
    assert first.observation_id == repeated.observation_id
    assert first.evidence_fingerprint != repeated.evidence_fingerprint
    assert store.save_observation(first) is IndexOhlcWriteOutcome.INSERTED
    assert store.save_observation(repeated) is IndexOhlcWriteOutcome.IDENTICAL
    assert store.save_observation(_observation(close="24176.65")) is IndexOhlcWriteOutcome.CONFLICT
    assert store.save_artifact(_artifact())
    assert not store.save_artifact(_artifact(at=T.replace(hour=13)))
    visible = store.range(INDEX, datetime(2026, 8, 1, tzinfo=UTC), T, as_of=T)
    assert visible == (first,)
    assert first.index_level_basis == INDEX_LEVEL_BASIS
    assert first.index_return_family == INDEX_RETURN_FAMILY
    assert not hasattr(first, "volume") and not hasattr(first, "corporate_action")


def test_two_run_refresh_is_idempotent_without_provider_merge_or_upstox(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotOfficialIndexOhlcStore(repository)

    class Client:
        def fetch(self, *, canonical_index_id, official_index_name, requested_start, requested_end, retrieved_at, artifact_directory):
            assert canonical_index_id == INDEX and official_index_name == "Nifty 50"
            return _artifact(at=retrieved_at), (_observation(retrieved_at=retrieved_at),)

    result = OfficialNseIndexOhlcSeriesRefresh(
        store=store, targets=((INDEX, "Nifty 50"),), artifact_directory=tmp_path / "archive",
        client=Client(), clock=lambda: T,
    ).run_twice()
    assert result.first_run[0].inserted_count == 1
    assert result.second_run[0].duplicate_count == 1
    assert result.second_run[0].conflict_count == 0


def test_one_official_close_only_target_is_retained_as_a_fail_closed_per_index_blocker(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotOfficialIndexOhlcStore(repository)

    class Client:
        def fetch(self, **_):
            raise ValueError("NSE_INDICES_HISTORICAL_OHLC_UNAVAILABLE")

    result = OfficialNseIndexOhlcSeriesRefresh(
        store=store, targets=((INDEX, "Nifty 50"),), artifact_directory=tmp_path / "archive",
        client=Client(), clock=lambda: T,
    ).run_twice()
    assert result.first_run[0].blocker == "NSE_INDICES_HISTORICAL_OHLC_UNAVAILABLE"
    assert result.first_run[0].sessions_after == 0
    assert result.second_run[0].inserted_count == result.second_run[0].duplicate_count == 0


def test_multi_target_refresh_uses_a_bounded_injected_request_interval(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotOfficialIndexOhlcStore(repository)
    pauses: list[float] = []

    class Client:
        def fetch(self, *, canonical_index_id, official_index_name, requested_start, requested_end, retrieved_at, artifact_directory):
            observation = _observation(retrieved_at=retrieved_at)
            return _artifact(at=retrieved_at), (observation,)

    OfficialNseIndexOhlcSeriesRefresh(
        store=store,
        targets=(("NIFTY_50", "Nifty 50"), ("NSE_SECTOR_INDEX:CAPITAL_GOODS", "Nifty Capital Goods")),
        artifact_directory=tmp_path / "archive", client=Client(), clock=lambda: T,
        sleeper=pauses.append,
    ).run_twice()
    assert pauses == [1.0, 1.0]
