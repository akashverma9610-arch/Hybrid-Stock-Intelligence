from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.official_nse_index_ohlc import (
    INDEX_LEVEL_BASIS,
    INDEX_RETURN_FAMILY,
    CanonicalOfficialIndexOhlcObservation,
    CoreSnapshotOfficialIndexOhlcStore,
    IndexOhlcWriteOutcome,
    NseIndicesOfficialOhlcClient,
    OfficialIndexOhlcActivationResult,
    OfficialIndexOhlcRetrievalArtifact,
    OfficialIndexOhlcTarget,
    OfficialIndexOhlcTargetRun,
    OfficialNseIndexOhlcSeriesRefresh,
    parse_official_nse_index_ohlc_response,
)
from app.market_data.official_nse_index_ohlc_reconciliation import (
    resolve_official_nse_index_source_query,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus


T = datetime(2026, 9, 1, 12, tzinfo=UTC)
INDEX = "NIFTY_50"


def _alias_resolution(*, sector: str, official_index_name: str, canonical_index_id: str):
    return resolve_official_nse_index_source_query(
        mapping=NseSectorIndexMapping(
            "nse-sector-index-mapping:test", sector, official_index_name,
            "https://www.niftyindices.com/", SectorIndexMappingStatus.EXACT_OFFICIAL,
            ("NSE_INDICES_SECTORAL_CATALOGUE",), "a" * 64, T,
        ),
        canonical_index_id=canonical_index_id,
    )


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


def test_explicit_first_party_query_alias_retains_canonical_identity_and_replays_idempotently(tmp_path) -> None:
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = CoreSnapshotOfficialIndexOhlcStore(repository)
    resolution = _alias_resolution(
        sector="Consumer Durables", official_index_name="Nifty Consumer Durables Index",
        canonical_index_id="NSE_SECTOR_INDEX:CONSUMER_DURABLES",
    )
    target = OfficialIndexOhlcTarget(
        resolution.canonical_index_id, resolution.canonical_mapping_name,
        resolution.source_query_name, resolution,
    )

    def alias_values(retrieved_at: datetime):
        session, open_value, high, low, close = parse_official_nse_index_ohlc_response(
            _raw(index="Nifty Consumer Durables"), target.source_query_name,
        )[0]
        observation = CanonicalOfficialIndexOhlcObservation.create(
            canonical_index_id=target.canonical_index_id,
            official_index_name=target.official_index_name, session=session,
            open=open_value, high=high, low=low, close=close,
            retrieved_at=retrieved_at, raw_artifact_sha256="e" * 64,
            source_reference="https://www.niftyindices.com/reports/historical-data#source-query-alias-sha256=" + resolution.fingerprint,
        )
        artifact = OfficialIndexOhlcRetrievalArtifact(
            artifact_id="official-index-ohlc-artifact:" + "e" * 64,
            canonical_index_id=target.canonical_index_id,
            official_index_name=target.official_index_name,
            source_url="https://official.example/historical", requested_start="2025-09-01",
            requested_end="2026-09-01", retrieved_at=retrieved_at,
            raw_artifact_sha256="e" * 64, row_count=1, earliest_session=session,
            latest_session=session, parser_version="nse-indices-historical-ohlc-v1",
            index_level_basis=INDEX_LEVEL_BASIS, index_return_family=INDEX_RETURN_FAMILY,
            local_path="data/official_sources/nse_index_ohlc_series/consumer.json",
            source_query_name=target.source_query_name,
            source_query_alias_fingerprint=resolution.fingerprint,
        )
        return artifact, (observation,)

    class Client:
        def fetch(self, *, source_query_resolution, retrieved_at, **values):
            assert values["canonical_index_id"] == target.canonical_index_id
            assert values["official_index_name"] == target.official_index_name
            assert source_query_resolution == resolution
            return alias_values(retrieved_at)

    result = OfficialNseIndexOhlcSeriesRefresh(
        store=store, targets=(target,), artifact_directory=tmp_path / "archive",
        client=Client(), clock=lambda: T,
    ).run_twice()
    first = result.first_run[0]
    second = result.second_run[0]
    values = store.range(target.canonical_index_id, datetime(2026, 8, 1, tzinfo=UTC), T, as_of=T)
    assert (first.inserted_count, second.duplicate_count, second.conflict_count) == (1, 1, 0)
    assert values[0].official_index_name == target.official_index_name
    assert values[0].source_reference.endswith("source-query-alias-sha256=" + resolution.fingerprint)


def test_client_uses_only_the_proven_query_alias_and_records_its_lineage(tmp_path) -> None:
    resolution = _alias_resolution(
        sector="Healthcare", official_index_name="Nifty Healthcare Index",
        canonical_index_id="NSE_SECTOR_INDEX:HEALTHCARE",
    )
    target = OfficialIndexOhlcTarget(
        resolution.canonical_index_id, resolution.canonical_mapping_name,
        resolution.source_query_name, resolution,
    )

    class Response:
        content = _raw(index="Nifty Healthcare")

        def raise_for_status(self) -> None:
            return None

    class Session:
        def post(self, url, *, json, timeout, headers):
            assert "NIFTY HEALTHCARE" in json["cinfo"]
            assert "Nifty Healthcare Index" not in json["cinfo"]
            assert timeout == 45 and headers["Accept"] == "application/json"
            return Response()

    artifact, observations = NseIndicesOfficialOhlcClient(session=Session()).fetch(
        canonical_index_id=target.canonical_index_id, official_index_name=target.official_index_name,
        source_query_resolution=resolution,
        requested_start=date(2025, 9, 1), requested_end=date(2026, 9, 1),
        retrieved_at=T, artifact_directory=tmp_path,
    )
    assert artifact.source_query_name == target.source_query_name
    assert artifact.source_query_alias_fingerprint == target.source_query_alias_fingerprint
    assert observations[0].official_index_name == target.official_index_name
    assert observations[0].source_reference.endswith("source-query-alias-sha256=" + resolution.fingerprint)
    with pytest.raises(ValueError, match="TARGET_INVALID"):
        OfficialIndexOhlcTarget(target.canonical_index_id, target.official_index_name, target.source_query_name)


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


def test_remainder_cli_selects_only_the_injected_exact_it_refresh() -> None:
    """The remainder command cannot fall through to the broad refresh path."""
    from app.runtime.cli import main

    run = OfficialIndexOhlcTargetRun(
        "NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY", "Nifty IT",
        0, 1, datetime(2026, 8, 31, 10, tzinfo=UTC), datetime(2026, 8, 31, 10, tzinfo=UTC),
        1, 0, 0, "f" * 64,
    )
    result = OfficialIndexOhlcActivationResult(T, T, (run,), (run,))
    calls: list[str] = []

    class Service:
        def run_twice(self):
            calls.append("run_twice")
            return result

    class Repository:
        def close(self):
            calls.append("close")

    output: list[str] = []
    assert main(
        ["ingest-official-nse-sector-index-remainder-ohlc"],
        official_index_ohlc_remainder_refresh_factory=lambda: (Service(), Repository()),
        official_index_ohlc_refresh_factory=lambda: (_ for _ in ()).throw(AssertionError("broad factory used")),
        official_index_ohlc_alias_refresh_factory=lambda: (_ for _ in ()).throw(AssertionError("alias factory used")),
        output=output.append,
    ) == 0
    assert calls == ["run_twice", "close"]
    assert len(output) == 3 and all("NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY" in line for line in output[1:])
