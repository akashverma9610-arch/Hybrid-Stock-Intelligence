from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.index_close_series import (
    CanonicalIndexCloseObservation,
    CoreSnapshotIndexCloseStore,
    IndexCloseWriteOutcome,
    NSE_INDICES_HISTORICAL_URL,
    NSE_INDICES_OFFICIAL,
    OfficialIndexCloseRetrievalArtifact,
    OfficialNseIndexCloseSeriesRefresh,
    _parse_official_response,
    close_series_from_bars,
    close_series_from_observations,
)
from app.market_data.current_sector_rotation import _relative_strength
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
INDEX_ID = "NSE_SECTOR_INDEX:CAPITAL_GOODS"


def _raw(*, close: str = "17587.13", index: str = "Nifty Capital Goods") -> bytes:
    return json.dumps([{
        "INDEX_NAME": index, "HistoricalDate": "31 Aug 2026",
        "OPEN": "-", "HIGH": "-", "LOW": "-", "CLOSE": close,
    }]).encode()


def _observation(*, close: str = "17587.13", retrieved_at: datetime = T) -> CanonicalIndexCloseObservation:
    rows = _parse_official_response(_raw(close=close), "Nifty Capital Goods")
    session, value, missing = rows[0]
    return CanonicalIndexCloseObservation.create(
        canonical_index_id=INDEX_ID, official_index_name="Nifty Capital Goods",
        session=session, close=value, retrieved_at=retrieved_at,
        raw_artifact_sha256="a" * 64, raw_unavailable_fields=missing,
    )


def test_official_nse_close_parser_accepts_only_close_and_retains_raw_ohl_unavailability() -> None:
    rows = _parse_official_response(_raw(), "Nifty Capital Goods")
    assert rows == ((datetime(2026, 8, 31, 10, tzinfo=UTC), Decimal("17587.13"), ("HIGH", "LOW", "OPEN")),)
    assert NSE_INDICES_OFFICIAL == "NSE_INDICES_OFFICIAL"
    assert NSE_INDICES_HISTORICAL_URL.startswith("https://www.niftyindices.com/")


def test_official_nse_close_parser_rejects_semantic_proxy_and_missing_close() -> None:
    with pytest.raises(ValueError, match="EXACT_INDEX_IDENTITY"):
        _parse_official_response(_raw(index="Nifty Capital Mkt"), "Nifty Capital Goods")
    with pytest.raises(ValueError, match="CLOSE_UNAVAILABLE"):
        _parse_official_response(_raw(close="-"), "Nifty Capital Goods")


def test_close_observation_is_immutable_pit_safe_and_idempotent(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotIndexCloseStore(repository)
    first = _observation()
    assert store.save_observation(first) is IndexCloseWriteOutcome.INSERTED
    assert store.save_observation(first) is IndexCloseWriteOutcome.IDENTICAL
    # Same logical session with a revised value is a closed conflict; the
    # original evidence remains the only canonical observation.
    assert store.save_observation(_observation(close="17588.13")) is IndexCloseWriteOutcome.CONFLICT
    assert store.range(INDEX_ID, datetime(2026, 8, 1, tzinfo=UTC), T - datetime.resolution, as_of=T - datetime.resolution) == ()
    values = store.range(INDEX_ID, datetime(2026, 8, 1, tzinfo=UTC), T, as_of=T)
    assert values == (first,) and values[0].raw_unavailable_fields == ("HIGH", "LOW", "OPEN")


def test_close_series_interface_is_close_only_and_does_not_make_ohlc_values() -> None:
    observation = _observation()
    points = close_series_from_observations((observation,))
    assert points[0].close == Decimal("17587.13")
    assert not hasattr(points[0], "open") and not hasattr(points[0], "high") and not hasattr(points[0], "low")
    assert close_series_from_bars(()) == ()
    source = (Path(__file__).parents[2] / "app" / "market_data" / "index_close_series.py").read_text(encoding="utf-8")
    assert "CanonicalOHLCVBar" not in source


def test_fixed_official_close_activation_is_two_run_idempotent_without_ohlc_bars(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotIndexCloseStore(repository)

    class Client:
        def fetch(self, *, canonical_index_id, official_index_name, requested_start, requested_end, retrieved_at, artifact_directory):
            observation = _observation(retrieved_at=retrieved_at)
            artifact = OfficialIndexCloseRetrievalArtifact(
                artifact_id="official-index-close-artifact:" + "b" * 64,
                canonical_index_id=canonical_index_id, official_index_name=official_index_name,
                source_url=NSE_INDICES_HISTORICAL_URL, requested_start=requested_start.isoformat(),
                requested_end=requested_end.isoformat(), retrieved_at=retrieved_at,
                raw_artifact_sha256="b" * 64, row_count=1, earliest_session=observation.session,
                latest_session=observation.session, parser_version="nse-indices-historical-close-v1",
                raw_unavailable_field_counts=(("OPEN", 1), ("HIGH", 1), ("LOW", 1)),
                local_path=str(artifact_directory / "fixture.json"),
            )
            return artifact, (observation,)

    service = OfficialNseIndexCloseSeriesRefresh(
        store=store, targets=((INDEX_ID, "Nifty Capital Goods"),), artifact_directory=tmp_path / "archive",
        client=Client(), clock=lambda: T,
    )
    result = service.run_twice()
    assert result.first_run[0].inserted_count == 1
    assert result.second_run[0].duplicate_count == 1
    assert result.second_run[0].conflict_count == 0
    assert store.range(INDEX_ID, datetime(2026, 8, 1, tzinfo=UTC), T, as_of=T)[0].close == Decimal("17587.13")


def test_mansfield_close_interface_aligns_different_provider_timestamps_by_session_date() -> None:
    official = tuple(
        CanonicalIndexCloseObservation.create(
            canonical_index_id=INDEX_ID, official_index_name="Nifty Capital Goods",
            session=datetime(2026, 4, day, 10, tzinfo=UTC), close=Decimal(100 + day),
            retrieved_at=T, raw_artifact_sha256="c" * 64,
            raw_unavailable_fields=("HIGH", "LOW", "OPEN"),
        )
        for day in range(1, 29)
    )
    # Reuse the same calendar sessions at the legacy bar timestamp shape.
    benchmark = tuple(type("Bar", (), {
        "end_time": datetime(2026, 4, day, 18, 30, tzinfo=UTC),
        "close": Decimal(100), "bar_id": f"benchmark:{day}",
        "provenance": type("Provenance", (), {"provider": "upstox"})(),
    })() for day in range(1, 29))
    result = _relative_strength(
        "Capital Goods", "Nifty Capital Goods", close_series_from_observations(official),
        close_series_from_bars(benchmark), official_close_sessions=len(official),
    )
    assert result.official_close_sessions == 28
    assert result.rs20 is not None and result.rs60 is None
