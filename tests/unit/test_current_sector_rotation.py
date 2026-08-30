from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.market_data.current_sector_rotation import (
    CURRENT_BREADTH_MINIMUM_HISTORY,
    CurrentSectorConstituentBackfillService,
    CurrentSectorRotationService,
    SectorBackfillPlan,
)
from app.market_data.historical import BarWriteOutcome, SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity,
    InstrumentType, MarketDataProvenance, ProviderInstrumentMapping, Timeframe,
)
from app.market_data.upstox import UPSTOX_PROVIDER, parse_upstox_instrument_records
from app.market_data.upstox_sector_indices import NIFTY_500_INDEX_ID, _sector_index_id
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.nse_sector_indices import (
    NseSectorIndexConstituent, NseSectorIndexMapping, SectorIndexMappingStatus,
)
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _snapshot(repository, family, identifier: str, payload: object) -> None:
    repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", "fixture", identifier, T, payload))


def _instrument(symbol: str = "ALPHA", isin: str = "INE000A01001") -> NseEquityInstrument:
    return NseEquityInstrument(f"NSE:{symbol}", symbol, isin, "Realty", None, "ACTIVE", None, True, T, "NSE_OFFICIAL_EXPORT", company_name=symbol)


def _identity(identifier: str, symbol: str, isin: str | None = None) -> InstrumentIdentity:
    kind = InstrumentType.BROAD_INDEX if identifier == NIFTY_500_INDEX_ID or identifier.startswith("NSE_SECTOR_INDEX") else InstrumentType.NSE_EQUITY
    exchange = Exchange.INDEX if kind is not InstrumentType.NSE_EQUITY else Exchange.NSE
    return InstrumentIdentity(identifier, exchange, symbol, symbol, isin, None, kind, symbol)


def _bar(identity: InstrumentIdentity, number: int, *, provider: str = UPSTOX_PROVIDER, close: Decimal | None = None) -> CanonicalOHLCVBar:
    moment = T - timedelta(days=330 - number)
    value = close if close is not None else Decimal("100") + Decimal(number)
    return CanonicalOHLCVBar(
        f"{identity.instrument_id}:{provider}:{number}", identity, Timeframe.DAILY, moment, moment,
        value, value + 1, value - 1, value, 1000, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance(provider, identity.instrument_id, moment, moment, T - timedelta(days=1), "fixture", source_reference=provider),
    )


def _context(tmp_path, *, sessions: int = 220, include_equity: bool = True):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    universe = CoreUniverseAnalysisStore(repository)
    equity = _instrument()
    universe.save_instrument(equity)
    universe.save_universe_snapshot(UniverseSnapshot("current", T, "NSE", 1, 1, 0, (), "v1", "fixture", (equity.instrument_id,)))
    mapping = NseSectorIndexMapping("realty", "Realty", "Nifty Realty", "https://official.example/realty", SectorIndexMappingStatus.EXACT_OFFICIAL, ("official",), "sha", T)
    constituent = NseSectorIndexConstituent("realty:alpha", "Nifty Realty", "Alpha", "ALPHA", equity.isin or "", "EQ", "Realty", "sha", "2026-08-28", T)
    _snapshot(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, "mapping:realty", mapping)
    _snapshot(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, "constituent:realty:alpha", constituent)
    identity = _identity(equity.instrument_id, equity.symbol, equity.isin)
    mapped = InstrumentIdentity(identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol, identity.isin, identity.series, identity.instrument_type, identity.name, provider_mappings=(ProviderInstrumentMapping(UPSTOX_PROVIDER, "NSE_EQ|INE000A01001", "ALPHA", "upstox-v3", "NSE_EQ"),))
    universe.capture_provider_mapping(mapped, provider=UPSTOX_PROVIDER, effective_as_of=T, source_reference="fixture")
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    benchmark = _identity(NIFTY_500_INDEX_ID, "NIFTY 500")
    sector = _identity(_sector_index_id("Realty"), "Nifty Realty")
    for number in range(sessions):
        assert history.upsert(_bar(benchmark, number, close=Decimal("100") + Decimal(number))) is BarWriteOutcome.INSERTED
        assert history.upsert(_bar(sector, number, close=Decimal("100") + Decimal(number * 2))) is BarWriteOutcome.INSERTED
        if include_equity:
            assert history.upsert(_bar(identity, number, close=Decimal("100") + Decimal(number * 2))) is BarWriteOutcome.INSERTED
    service = CurrentSectorRotationService(repository=repository, universe=universe, historical_store=history, clock=lambda: T)
    return repository, universe, history, identity, service


def _add_sector(repository, history, *, sector: str, official: str, constituent: NseSectorIndexConstituent, sessions: int) -> None:
    mapping = NseSectorIndexMapping(
        f"mapping:{sector}", sector, official, f"https://official.example/{sector}",
        SectorIndexMappingStatus.EXACT_OFFICIAL, ("official",), f"sha:{sector}", T,
    )
    _snapshot(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, f"mapping:{sector}", mapping)
    _snapshot(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, constituent.constituent_id, constituent)
    index = _identity(_sector_index_id(sector), official)
    benchmark = _identity(NIFTY_500_INDEX_ID, "NIFTY 500")
    for number in range(sessions):
        # The benchmark observation is identical to the existing fixture row.
        # Insert-only storage reports it as identical on the second sector.
        history.upsert(_bar(benchmark, number, close=Decimal("100") + Decimal(number)))
        assert history.upsert(_bar(index, number, close=Decimal("100") + Decimal(number * 2))) is BarWriteOutcome.INSERTED


def test_stored_current_sector_status_prefers_upstox_overlap_and_selects_fewer_than_three(tmp_path) -> None:
    _, _, history, identity, service = _context(tmp_path)
    moment = T - timedelta(days=330)
    legacy = CanonicalOHLCVBar("legacy-overlap", identity, Timeframe.DAILY, moment, moment, Decimal("1"), Decimal("2"), Decimal("1"), Decimal("1"), None, None, None, AdjustmentStatus.RAW, MarketDataProvenance("unknown_existing_source", identity.instrument_id, moment, moment, T - timedelta(days=1), "legacy"))
    assert history.upsert(legacy) is BarWriteOutcome.INSERTED
    report = service.assess()
    equity_coverage = report.coverage[0]
    assert report.benchmark_sessions == 220
    assert report.relative_strength[0].rs20 is not None and report.relative_strength[0].rs120 is not None
    assert report.breadth[0].status == "READY" and report.breadth[0].above_200_pct == Decimal("100.00")
    assert report.top3 == ("Realty",) and report.pre_breakout_full_ready == 0
    assert equity_coverage.sessions == 220 and equity_coverage.at_least_200
    assert history.range(identity.instrument_id, Timeframe.DAILY, moment, moment)[0].provenance.provider == UPSTOX_PROVIDER
    assert "HISTORICAL_BREADTH_NOT_PIT_VALID" in report.warnings


def test_sector_mapping_snapshots_created_after_as_of_do_not_rewrite_historical_coverage(tmp_path) -> None:
    _, _, _, _, service = _context(tmp_path)
    historical = service.assess(as_of=T - timedelta(days=1))
    current = service.assess(as_of=T)
    assert historical.relative_strength == () and historical.top3 == ()
    assert current.relative_strength and current.relative_strength[0].sector == "Realty"


def test_unknown_legacy_fills_only_non_overlapping_session_in_canonical_view(tmp_path) -> None:
    _, _, history, identity, _ = _context(tmp_path, sessions=1, include_equity=True)
    old = T - timedelta(days=331)
    assert history.upsert(CanonicalOHLCVBar("legacy-old", identity, Timeframe.DAILY, old, old, Decimal("9"), Decimal("9"), Decimal("9"), Decimal("9"), None, None, None, AdjustmentStatus.RAW, MarketDataProvenance("unknown_existing_source", identity.instrument_id, old, old, T - timedelta(days=1), "legacy"))) is BarWriteOutcome.INSERTED
    values = history.range(identity.instrument_id, Timeframe.DAILY, old, T)
    assert len(values) == 2 and values[0].provenance.provider == "unknown_existing_source" and values[-1].provenance.provider == UPSTOX_PROVIDER


def test_stored_plan_makes_no_provider_calls_and_unresolved_is_never_a_target(tmp_path) -> None:
    repository, _, _, _, service = _context(tmp_path, sessions=199, include_equity=True)
    unresolved = NseSectorIndexConstituent("realty:missing", "Nifty Realty", "Missing", "MISSING", "INE999A01001", "EQ", "Realty", "sha", "2026-08-28", T)
    _snapshot(repository, CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, "constituent:realty:missing", unresolved)
    report = service.assess()
    assert report.plan.total_constituents == 2 and report.plan.unresolved == 1
    assert [item.instrument.symbol for item in report.plan.need_backfill] == ["ALPHA"]
    assert report.plan.estimated_provider_calls == 1


def test_already_sufficient_constituent_is_not_refetched(tmp_path) -> None:
    _, universe, history, _, service = _context(tmp_path, sessions=CURRENT_BREADTH_MINIMUM_HISTORY)
    plan = service.assess().plan
    assert plan.need_backfill == ()
    calls: list[object] = []
    class Provider:
        def __init__(self, _: str) -> None: calls.append("constructed")
    report = CurrentSectorConstituentBackfillService(universe=universe, historical_store=history, provider_factory=Provider, clock=lambda: T).ingest(plan, master_records=(), access_token="synthetic")
    assert report.provider_requests == 0 and calls == []


def test_stored_status_cli_uses_only_its_injected_stored_service(tmp_path) -> None:
    """The U07 status path cannot compose a provider client or read a token."""
    from app.runtime.cli import main

    _, _, history, _, service = _context(tmp_path)
    writes: list[object] = []
    class StoredOnlyService:
        def assess(self): return service.assess()
        def write_reports(self, report, directory):
            writes.append((report, directory)); return ()
    output: list[str] = []
    assert main(
        ["current-sector-rotation-status", "--report-dir", str(tmp_path / "reports")],
        current_sector_rotation_factory=lambda: (StoredOnlyService(), history),
        output=output.append,
    ) == 0
    assert writes and any(line.startswith("benchmark_sessions=") for line in output)


def test_rs_ready_only_cli_plan_is_stored_only_and_reports_targeted_counts(tmp_path) -> None:
    from app.runtime.cli import main

    _, _, history, _, service = _context(tmp_path, sessions=CURRENT_BREADTH_MINIMUM_HISTORY - 1)
    output: list[str] = []
    assert main(
        ["plan-upstox-sector-constituent-backfill", "--rs-ready-only"],
        current_sector_rotation_factory=lambda: (service, history),
        output=output.append,
    ) == 0
    assert any("rs_ready_only=True" in line and "estimated_provider_calls=1" in line for line in output)
    assert any(line.startswith("plan_sector=Realty") for line in output)


def test_rs_ready_only_plan_excludes_unready_sector_and_preserves_broad_plan(tmp_path) -> None:
    repository, universe, _, _, service = _context(tmp_path, sessions=199)
    beta = _instrument("BETA", "INE000B01002")
    universe.save_instrument(beta)
    unready = NseSectorIndexConstituent("capital:beta", "Nifty Capital Goods", "Beta", "BETA", beta.isin or "", "EQ", "Capital Goods", "sha", "2026-08-28", T)
    _add_sector(repository, service._historical, sector="Capital Goods", official="Nifty Capital Goods", constituent=unready, sessions=0)
    broad = service.assess().plan
    targeted = service.assess(rs_ready_only=True).plan
    assert {item.instrument.symbol for item in broad.need_backfill} == {"ALPHA", "BETA"}
    assert [item.instrument.symbol for item in targeted.need_backfill] == ["ALPHA"]
    assert targeted.rs_ready_only and targeted.rs_ready_sectors == ("Realty",)
    assert {item.sector for item in targeted.by_sector} == {"Realty"}


def test_rs_ready_only_plan_deduplicates_overlapping_isin_across_ready_sectors(tmp_path) -> None:
    repository, _, history, _, service = _context(tmp_path, sessions=199)
    overlap = NseSectorIndexConstituent("fmcg:alpha", "Nifty FMCG", "Alpha", "ALPHA", "INE000A01001", "EQ", "FMCG", "sha", "2026-08-28", T)
    _add_sector(repository, history, sector="Fast Moving Consumer Goods", official="Nifty FMCG", constituent=overlap, sessions=199)
    plan = service.assess(rs_ready_only=True).plan
    assert plan.rs_ready_sectors == ("Fast Moving Consumer Goods", "Realty")
    assert plan.constituents_before_dedup == 2 and plan.unique_constituents == 1
    assert plan.estimated_provider_calls == 1 and plan.need_backfill[0].instrument.symbol == "ALPHA"


def test_targeted_plan_fetches_only_planned_identity_and_resumes_without_refetch(tmp_path) -> None:
    _, universe, history, _, service = _context(tmp_path, sessions=CURRENT_BREADTH_MINIMUM_HISTORY - 1, include_equity=True)
    plan = service.assess(rs_ready_only=True).plan
    assert [target.instrument.symbol for target in plan.need_backfill] == ["ALPHA"]
    calls: list[InstrumentIdentity] = []
    class Provider:
        def __init__(self, _: str) -> None: pass
        def get_historical_bars(self, request):
            calls.append(request.instrument)
            return (_bar(request.instrument, CURRENT_BREADTH_MINIMUM_HISTORY - 1),)
    master = parse_upstox_instrument_records([{
        "instrument_key": "NSE_EQ|INE000A01001", "segment": "NSE_EQ", "exchange": "NSE", "isin": "INE000A01001",
        "instrument_type": "EQ", "trading_symbol": "ALPHA",
    }])
    backfill = CurrentSectorConstituentBackfillService(universe=universe, historical_store=history, provider_factory=Provider, sleep_fn=lambda _: None, clock=lambda: T)
    first = backfill.ingest(plan, master_records=master, access_token="synthetic")
    second = backfill.ingest(plan, master_records=master, access_token="synthetic")
    assert first.provider_requests == 1 and first.accepted == 1
    assert second.provider_requests == 0 and len(calls) == 1
    assert history.count("NSE:ALPHA", Timeframe.DAILY) == CURRENT_BREADTH_MINIMUM_HISTORY
    source = (Path(__file__).parents[2] / "app" / "market_data" / "current_sector_rotation.py").read_text(encoding="utf-8")
    assert "fundamentals" not in source.casefold()
