"""Deterministic U17 composition tests for the existing Upstox V3 adapter."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.data_operations.upstox import MINIMUM_REQUIRED_DAILY_SESSIONS, UpstoxIndexBarsRefreshJob, UpstoxOhlcvRefreshJob
from app.domain.models import DataQuality
from app.market_data.historical import SQLiteHistoricalBarStore
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, MarketDataProvenance
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxInstrumentMaster, UpstoxInstrumentRecord
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus


T = datetime(2026, 8, 29, 12, tzinfo=UTC)


class Provider:
    def __init__(self) -> None:
        self.requests = []

    def get_historical_bars(self, request):
        self.requests.append(request)
        start = request.end - timedelta(days=MINIMUM_REQUIRED_DAILY_SESSIONS)
        return tuple(
            CanonicalOHLCVBar(
                f"upstox:{request.instrument.instrument_id}:{index}", request.instrument, request.timeframe,
                start + timedelta(days=index), start + timedelta(days=index + 1),
                Decimal("100"), Decimal("101"), Decimal("99"), Decimal("100"), 1000,
                None, None, AdjustmentStatus.UNKNOWN,
                MarketDataProvenance(UPSTOX_PROVIDER, "NSE_EQ|INE000A01001", None, None, T,
                                     "upstox-history-v3", "Historical Candle V3", "fixture"),
                DataQuality.HIGH, ("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED",),
            )
            for index in range(MINIMUM_REQUIRED_DAILY_SESSIONS)
        )


def _request(mode=EvidenceRefreshMode.BACKFILL):
    return EvidenceRefreshRequest("run:upstox", EvidenceDataFamily.OHLCV, mode, T, T, None, 2)


def _job(tmp_path, *, token="synthetic"):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "snapshots.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    universe.save_instrument(NseEquityInstrument("NSE:ALPHA", "ALPHA", "INE000A01001", None, None, "LISTED", None, True, T, "NSE_OFFICIAL"))
    history = SQLiteHistoricalBarStore(tmp_path / "bars.sqlite")
    provider = Provider()
    master = UpstoxInstrumentMaster("https://official.example/NSE.json.gz", "fixture-checksum", (
        UpstoxInstrumentRecord("NSE_EQ|INE000A01001", "NSE_EQ", "NSE", "EQ", "INE000A01001", "ALPHA"),
    ))
    job = UpstoxOhlcvRefreshJob(universe_store=universe, historical_store=history,
        token_reader=lambda: token, master_loader=lambda: master, provider_factory=lambda _: provider,
        clock=lambda: T, pause_seconds=0)
    return job, provider, universe, history


def test_missing_secure_upstox_configuration_blocks_without_master_or_provider_call(tmp_path):
    job, provider, _, _ = _job(tmp_path, token=None)
    result = job.refresh(_request())
    assert result.status is EvidenceRefreshStatus.SOURCE_UNAVAILABLE
    assert result.error_summary == "UPSTOX_ACCESS_TOKEN_REQUIRED" and provider.requests == []


def test_backfill_uses_exact_isin_mapping_and_canonical_provider_versioned_ingestion(tmp_path):
    job, provider, universe, history = _job(tmp_path)
    result = job.refresh(_request())
    mapping = universe.provider_mapping(canonical_instrument_id="NSE:ALPHA", provider=UPSTOX_PROVIDER, as_of=T)
    assert result.status is EvidenceRefreshStatus.COMPLETE
    assert result.accepted_count == MINIMUM_REQUIRED_DAILY_SESSIONS and len(provider.requests) == 1
    assert mapping is not None and history.count("NSE:ALPHA", provider.requests[0].timeframe) == MINIMUM_REQUIRED_DAILY_SESSIONS
    assert result.accepted_through is not None and result.source_fingerprint == "fixture-checksum"


def test_incremental_rerun_uses_store_coverage_and_overlap_without_conflict_overwrite(tmp_path):
    job, provider, _, history = _job(tmp_path)
    first = job.refresh(_request())
    second = job.refresh(_request(EvidenceRefreshMode.INCREMENTAL))
    assert first.accepted_count == MINIMUM_REQUIRED_DAILY_SESSIONS
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == MINIMUM_REQUIRED_DAILY_SESSIONS
    assert len(provider.requests) == 2 and history.count("NSE:ALPHA", provider.requests[0].timeframe) == MINIMUM_REQUIRED_DAILY_SESSIONS


def test_existing_governed_history_requirement_is_252_sessions_not_a_loosened_operational_threshold():
    assert MINIMUM_REQUIRED_DAILY_SESSIONS == 252


def test_index_job_uses_existing_official_mapping_and_the_same_versioned_bar_store(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "index-snapshots.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    history = SQLiteHistoricalBarStore(tmp_path / "index-bars.sqlite")
    provider = Provider()
    master = UpstoxInstrumentMaster("https://official.example/NSE.json.gz", "index-checksum", (
        UpstoxInstrumentRecord("NSE_INDEX|NIFTY500", "NSE_INDEX", "NSE", "INDEX", None, "NIFTY 500", "Nifty 500"),
        UpstoxInstrumentRecord("NSE_INDEX|NIFTYREALTY", "NSE_INDEX", "NSE", "INDEX", None, "NIFTY REALTY", "Nifty Realty"),
    ))
    sector = NseSectorIndexMapping("realty", "Realty", "Nifty Realty", None, SectorIndexMappingStatus.EXACT_OFFICIAL, (), "official", T)
    job = UpstoxIndexBarsRefreshJob(sector_mappings_loader=lambda: (sector,), universe_store=universe,
        historical_store=history, token_reader=lambda: "synthetic", master_loader=lambda: master,
        provider_factory=lambda _: provider, clock=lambda: T, pause_seconds=0)
    result = job.refresh(_request())
    assert result.status is EvidenceRefreshStatus.COMPLETE and result.accepted_count == 2 * MINIMUM_REQUIRED_DAILY_SESSIONS
    assert {item.instrument.instrument_id for item in provider.requests} == {"NIFTY_500", "NSE_SECTOR_INDEX:REALTY"}
