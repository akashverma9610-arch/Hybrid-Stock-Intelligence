from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshRequest, EvidenceRefreshStatus
from app.data_operations.nse_reference import NseCorporateActionsRefreshJob, NseIndexMembershipRefreshJob
from app.forward_paper.composition import StoredExecutableSetup, StoredExecutableSetupStore, StoredForwardPaperComposition
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction, HistoricalSecurityMasterStore, NseOfficialCorporateActionCsvImporter
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, DataQuality, MarketDataProvenance, Timeframe
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.nse_sector_indices import NseSectorIndexConstituent, NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import CoreUniverseAnalysisStore


T = datetime(2026, 8, 30, 10, 0, tzinfo=UTC)


def _request(at: datetime = T) -> EvidenceRefreshRequest:
    return EvidenceRefreshRequest("run", EvidenceDataFamily.INDEX_MEMBERSHIP, EvidenceRefreshMode.INCREMENTAL, at, at, None, 0)


def _instrument(identifier: str, symbol: str, isin: str) -> NseEquityInstrument:
    return NseEquityInstrument(identifier, symbol, isin, None, None, "ACTIVE", None, True, T - timedelta(days=1), "fixture", company_name=f"{symbol} Ltd")


def _universe(repo, instruments: tuple[NseEquityInstrument, ...]) -> CoreUniverseAnalysisStore:
    snapshot = UniverseSnapshot("snapshot", T - timedelta(days=1), "fixture", len(instruments), len(instruments), 0, (), "v1", "hash", tuple(item.instrument_id for item in instruments))
    store = CoreUniverseAnalysisStore(repo)
    store.save_universe_snapshot(snapshot)
    for item in instruments:
        store.save_instrument(item)
    return store


def _nifty(path: Path, rows: tuple[tuple[str, str], ...]) -> None:
    path.write_text("Company Name,Industry,Symbol,Series,ISIN Code\n" + "\n".join(
        f"{symbol} Ltd,Industry,{symbol},EQ,{isin}" for symbol, isin in rows
    ) + "\n", encoding="utf-8")


def test_current_official_membership_is_exact_idempotent_and_pit_visible_only_after_observation(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reference.sqlite")
    alpha, beta = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001"), _instrument("NSE:INE000A01002", "BETA", "INE000A01002")
    universe = _universe(repo, (alpha, beta)); source = tmp_path / "indices"; source.mkdir(); _nifty(source / "nifty500.csv", (("ALPHA", alpha.isin), ("BETA", beta.isin)))
    job = NseIndexMembershipRefreshJob(repository=repo, universe=universe, source_root=source)

    first = job.refresh(_request())
    second = job.refresh(_request(T + timedelta(days=1)))
    master = HistoricalSecurityMasterStore(repo)

    assert first.status is EvidenceRefreshStatus.COMPLETE and first.accepted_count == 2
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == 2
    members = master.memberships("NIFTY_500")
    assert {item.instrument_id for item in members} == {alpha.instrument_id, beta.instrument_id}
    assert all(item.status is InstrumentLifecycle.ACTIVE and item.effective_from == T and item.known_at == T for item in members)
    assert not [item for item in members if item.known_at <= T - timedelta(microseconds=1)]


def test_current_only_membership_disappearance_is_a_typed_gap_not_an_invented_interval_close(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reference.sqlite")
    alpha, beta = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001"), _instrument("NSE:INE000A01002", "BETA", "INE000A01002")
    universe = _universe(repo, (alpha, beta)); source = tmp_path / "indices"; source.mkdir(); path = source / "nifty500.csv"
    _nifty(path, (("ALPHA", alpha.isin), ("BETA", beta.isin)))
    job = NseIndexMembershipRefreshJob(repository=repo, universe=universe, source_root=source)
    assert job.refresh(_request()).status is EvidenceRefreshStatus.COMPLETE
    _nifty(path, (("ALPHA", alpha.isin),))

    changed = job.refresh(_request(T + timedelta(days=7)))

    assert changed.status is EvidenceRefreshStatus.PARTIAL
    assert any(reason == "NSE_MEMBERSHIP_REMOVAL_EFFECTIVE_DATE_REQUIRED" for _, _, reason in changed.findings)
    # The official file has no removal-effective date, so the immutable first
    # observation remains intact rather than being silently rewritten.
    assert any(item.instrument_id == beta.instrument_id and item.effective_to is None for item in HistoricalSecurityMasterStore(repo).memberships("NIFTY_500"))


def test_unresolved_membership_never_uses_symbol_fallback(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reference.sqlite")
    alpha = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001")
    universe = _universe(repo, (alpha,)); source = tmp_path / "indices"; source.mkdir(); _nifty(source / "nifty500.csv", (("ALPHA", "INE999A01001"),))

    report = NseIndexMembershipRefreshJob(repository=repo, universe=universe, source_root=source).refresh(_request())

    assert report.status is EvidenceRefreshStatus.PARTIAL and report.accepted_count == 0
    assert report.gap_count == 1 and report.findings[0][2] == "NSE_MEMBERSHIP_EXACT_IDENTITY_UNRESOLVED"


def test_membership_uses_only_currently_approved_sector_index_mappings(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reference.sqlite")
    alpha = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001")
    beta = _instrument("NSE:INE000A01002", "BETA", "INE000A01002")
    gamma = _instrument("NSE:INE000A01003", "GAMMA", "INE000A01003")
    universe = _universe(repo, (alpha, beta, gamma)); source = tmp_path / "indices"; source.mkdir(); _nifty(source / "nifty500.csv", (("ALPHA", alpha.isin),))
    mapping = NseSectorIndexMapping("mapping:exact", "Exact", "Nifty Exact", "official", SectorIndexMappingStatus.EXACT_OFFICIAL, (), "sha", T)
    repo.save_snapshot(CoreApiSnapshot("mapping:exact", CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, "v1", "fixture", "fp:exact", T, mapping))
    approved = NseSectorIndexConstituent("member:exact", "Nifty Exact", "Beta", "BETA", beta.isin, "EQ", "Exact", "sha", None, T)
    unsupported = NseSectorIndexConstituent("member:unsupported", "Nifty Unsupported", "Gamma", "GAMMA", gamma.isin, "EQ", "Unsupported", "sha", None, T)
    repo.save_snapshot(CoreApiSnapshot("member:exact", CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, "v1", "fixture", "fp:member-exact", T, approved))
    repo.save_snapshot(CoreApiSnapshot("member:unsupported", CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, "v1", "fixture", "fp:member-unsupported", T, unsupported))

    report = NseIndexMembershipRefreshJob(repository=repo, universe=universe, source_root=source).refresh(_request())

    assert report.accepted_count == 2
    memberships = HistoricalSecurityMasterStore(repo).memberships("Nifty Exact")
    assert tuple(item.instrument_id for item in memberships) == (beta.instrument_id,)
    assert not HistoricalSecurityMasterStore(repo).memberships("Nifty Unsupported")


def test_membership_reconciliation_reports_overlapping_existing_intervals_without_repairing_them(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reference.sqlite")
    alpha = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001")
    universe = _universe(repo, (alpha,)); source = tmp_path / "indices"; source.mkdir(); _nifty(source / "nifty500.csv", (("ALPHA", alpha.isin),))
    master = HistoricalSecurityMasterStore(repo)
    master.save_membership(UniverseMembership("first", alpha.instrument_id, "NIFTY_500", T - timedelta(days=3), None, T - timedelta(days=3), "fixture", "fixture", InstrumentLifecycle.ACTIVE), as_of=T - timedelta(days=3))
    master.save_membership(UniverseMembership("second", alpha.instrument_id, "NIFTY_500", T - timedelta(days=2), None, T - timedelta(days=2), "fixture", "fixture", InstrumentLifecycle.ACTIVE), as_of=T - timedelta(days=2))

    report = NseIndexMembershipRefreshJob(repository=repo, universe=universe, source_root=source, master=master).refresh(_request())

    assert report.status is EvidenceRefreshStatus.PARTIAL
    assert report.conflict_count == 1
    assert any(reason == "NSE_MEMBERSHIP_OVERLAPPING_INTERVAL" for _, _, reason in report.findings)
    assert len(master.memberships("NIFTY_500")) == 2


def test_official_corporate_actions_append_idempotently_with_exact_mapping_and_provenance(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "actions.sqlite")
    alpha = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001")
    universe = _universe(repo, (alpha,)); source = tmp_path / "corporate_actions"; source.mkdir()
    (source / "corporate.csv").write_text(
        "SYMBOL,COMPANY NAME,SERIES,PURPOSE,FACE VALUE,EX-DATE,RECORD DATE,BOOK CLOSURE START DATE,BOOK CLOSURE END DATE\n"
        "ALPHA,Alpha Ltd,EQ,Bonus 1:1,10,01-Sep-2026,02-Sep-2026,-,-\n", encoding="utf-8",
    )
    job = NseCorporateActionsRefreshJob(repository=repo, universe=universe, source_directory=source)

    first = job.refresh(_request())
    second = job.refresh(_request(T + timedelta(days=1)))
    actions = HistoricalSecurityMasterStore(repo).actions_as_of(alpha.instrument_id, T + timedelta(days=3))

    assert first.status is EvidenceRefreshStatus.COMPLETE and first.accepted_count == 1
    assert second.status is EvidenceRefreshStatus.NO_CHANGE and second.duplicate_count == 1
    assert len(actions) == 1 and actions[0].kind is CorporateActionKind.BONUS
    assert "mapping_method=EXACT_SYMBOL_EQ" in (actions[0].source_reference or "")


def test_corporate_action_rerun_treats_resolver_provenance_upgrade_as_a_duplicate(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "actions.sqlite")
    canonical = _instrument("NSE:INE000A01001", "ALPHA", "INE000A01001")
    legacy = _instrument("NSE:ALPHA", "ALPHA", "")
    universe = _universe(repo, (canonical, legacy)); source = tmp_path / "corporate_actions"; source.mkdir()
    path = source / "corporate.csv"
    path.write_text(
        "SYMBOL,COMPANY NAME,SERIES,PURPOSE,FACE VALUE,EX-DATE,RECORD DATE,BOOK CLOSURE START DATE,BOOK CLOSURE END DATE\n"
        "ALPHA,Alpha Ltd,EQ,Bonus 1:1,10,01-Sep-2026,02-Sep-2026,-,-\n", encoding="utf-8",
    )
    # This is a prior immutable event observed before the legacy symbol-only
    # universe copy existed.  The official source event and canonical ISIN are
    # identical; only resolver-provenance annotations change on rerun.
    master = HistoricalSecurityMasterStore(repo)
    legacy_action = NseOfficialCorporateActionCsvImporter(master).preview(
        path, instruments=(canonical,), imported_at=T,
    ).actions[0]
    master.save_action(legacy_action)

    report = NseCorporateActionsRefreshJob(repository=repo, universe=universe, source_directory=source, master=master).refresh(_request(T + timedelta(days=1)))

    assert report.status is EvidenceRefreshStatus.NO_CHANGE
    assert report.duplicate_count == 1
    stored = master.actions_as_of(canonical.instrument_id, T + timedelta(days=3))
    assert len(stored) == 1
    assert "mapping_method=EXACT_SYMBOL_EQ" in (stored[0].source_reference or "")


def test_forward_paper_requires_review_for_a_known_post_decision_price_transforming_action(tmp_path: Path) -> None:
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "paper.sqlite")
    master = HistoricalSecurityMasterStore(repo)
    action = HistoricalCorporateAction("action", "NSE:ALPHA", CorporateActionKind.SPLIT, T, None, T + timedelta(days=1),
        T + timedelta(days=1), Decimal("10"), Decimal("5"), None, "NSE", "v1", T, "fixture")
    master.save_action(action)
    setup = StoredExecutableSetup.create(setup_id="setup", canonical_instrument_id="NSE:ALPHA", setup_fingerprint="setup-fp",
        source_candidate_fingerprint="candidate-fp", strategy_version="v1", policy_fingerprint="policy", decision_as_of=T,
        trigger=Decimal("101"), structural_stop=Decimal("95"), target=Decimal("120"), maximum_entry=None, time_stop_sessions=5)
    stores = StoredExecutableSetupStore(repo); assert stores.save(setup)
    bar = CanonicalOHLCVBar("bar", SimpleNamespace(instrument_id="NSE:ALPHA"), Timeframe.DAILY,
        T + timedelta(days=1), T + timedelta(days=1, hours=10), Decimal("100"), Decimal("105"), Decimal("99"),
        Decimal("103"), 10, None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("NSE", "fixture", None, None, T, "v1"), DataQuality.HIGH)
    history = SimpleNamespace(has_conflict_artifact=lambda _: False, range=lambda *args, **kwargs: (bar,))

    values = StoredForwardPaperComposition(stores, history, master).bars_for(setup.admission(), start=T, end=T + timedelta(days=2))

    assert values[0].corporate_action_requires_review is True
