from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.data_quality.reconciliation.service import ReconciliationService, ReconciliationStatus
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import (
    CorporateActionKind, HistoricalCorporateAction, HistoricalIntegrityStatus,
    HistoricalPriceIntegrityService, HistoricalSecurityIdentity,
    HistoricalSecurityMasterStore, HistoricalSecurityStatus, HistoricalCorporateActionCsvImporter,
    HistoricalUniverseService, HistoricalBacktestIntegrityGate, NseOfficialCorporateActionCsvImporter,
    PriceAdjustmentBasis,
)
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance, Timeframe
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.service import TaxonomySnapshotStore


UTC = timezone.utc
T = datetime(2026, 8, 24, tzinfo=UTC)
I = InstrumentIdentity("NSE:STABLE", Exchange.NSE, "NEW", "NEW", "INE000A01001", "EQ", InstrumentType.NSE_EQUITY, "Stable Ltd")


def _identity(symbol: str, start: datetime, end: datetime | None = None):
    return HistoricalSecurityIdentity("identity-" + symbol, "NSE:STABLE", "INE000A01001", "NSE", symbol, "EQ", T - timedelta(days=1500), None, T - timedelta(days=1500), None, start, end, HistoricalSecurityStatus.ACTIVE, "official", start, "v1")


def _bar(identifier: str, at: datetime, adjustment=AdjustmentStatus.RAW, close=Decimal("100")):
    return CanonicalOHLCVBar(identifier, I, Timeframe.DAILY, at - timedelta(days=1), at, close, close + 1, close - 1, close, 100, None, None, adjustment, MarketDataProvenance("fixture", None, at, at, at, "v1"))


def test_historical_security_identity_listing_delisting_and_symbol_change_are_pit_safe(tmp_path: Path):
    store = HistoricalSecurityMasterStore(SQLiteCoreApiSnapshotRepository(tmp_path / "security.sqlite"))
    listed_2022 = HistoricalSecurityIdentity("listed", "NSE:LISTED", "INE000A01002", "NSE", "LISTED", "EQ", datetime(2022, 1, 1, tzinfo=UTC), None, datetime(2022, 1, 1, tzinfo=UTC), None, datetime(2022, 1, 1, tzinfo=UTC), None, HistoricalSecurityStatus.ACTIVE, "official", datetime(2022, 1, 1, tzinfo=UTC), "v1")
    old = _identity("OLD", datetime(2023, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)); new = _identity("NEW", datetime(2024, 1, 2, tzinfo=UTC))
    store.save_identity(listed_2022); store.save_identity(old); store.save_identity(new)
    assert "NSE:LISTED" not in {item.canonical_instrument_id for item in store.identities_as_of(datetime(2020, 1, 1, tzinfo=UTC))}
    assert [item.symbol for item in store.identities_as_of(datetime(2023, 6, 1, tzinfo=UTC)) if item.canonical_instrument_id == "NSE:STABLE"] == ["OLD"]
    renamed = [item for item in store.identities_as_of(datetime(2025, 1, 1, tzinfo=UTC)) if item.canonical_instrument_id == "NSE:STABLE"]
    assert [item.symbol for item in renamed] == ["NEW"]


def test_historical_universe_retains_delisted_security_before_exit_and_never_substitutes_today():
    service = HistoricalUniverseService()
    membership = UniverseMembership("delisted-member", "NSE:DELISTED", "NIFTY_HISTORY", datetime(2020, 1, 1, tzinfo=UTC), datetime(2023, 1, 1, tzinfo=UTC), datetime(2020, 1, 1, tzinfo=UTC), "official", "source", InstrumentLifecycle.DELISTED)
    old = service.get_universe(universe_id="NIFTY_HISTORY", as_of=datetime(2022, 1, 1, tzinfo=UTC), memberships=(membership,), source_complete=True)
    after = service.get_universe(universe_id="NIFTY_HISTORY", as_of=datetime(2024, 1, 1, tzinfo=UTC), memberships=(membership,), source_complete=True)
    assert old.instrument_ids == ("NSE:DELISTED",) and after.instrument_ids == ()
    partial = service.get_universe(universe_id="NIFTY_HISTORY", as_of=datetime(2022, 1, 1, tzinfo=UTC), memberships=(membership,), source_complete=False)
    assert partial.status is HistoricalIntegrityStatus.PARTIAL and "HISTORICAL_MEMBERSHIP_SOURCE_PARTIAL" in partial.warnings


def test_future_corporate_action_is_excluded_and_raw_split_is_not_technical_input():
    split = HistoricalCorporateAction("split", "NSE:STABLE", CorporateActionKind.SPLIT, T + timedelta(days=1), None, T + timedelta(days=2), T + timedelta(days=2), Decimal("2"), Decimal("1"), None, "official", "v1", T + timedelta(days=1))
    assert not split.eligible_as_of(T)
    service = HistoricalPriceIntegrityService()
    known_split = HistoricalCorporateAction("known-split", "NSE:STABLE", CorporateActionKind.SPLIT, T - timedelta(days=4), None, T - timedelta(days=3), T - timedelta(days=3), Decimal("2"), Decimal("1"), None, "official", "v1", T - timedelta(days=4))
    raw = service.assess(instrument_id="NSE:STABLE", bars=(_bar("before", T - timedelta(days=5), close=Decimal("100")), _bar("after", T - timedelta(days=1), close=Decimal("50"))), actions=(known_split,), as_of=T, basis=PriceAdjustmentBasis.RAW)
    assert raw.status is HistoricalIntegrityStatus.PARTIAL and not raw.technical_eligible
    assert "RAW_SERIES_SPANS_PRICE_TRANSFORMING_ACTION" in raw.warnings
    adjusted = service.assess(instrument_id="NSE:STABLE", bars=(_bar("adjusted-before", T - timedelta(days=5), AdjustmentStatus.ADJUSTED, Decimal("50")), _bar("adjusted-after", T - timedelta(days=1), AdjustmentStatus.ADJUSTED, Decimal("50"))), actions=(known_split,), as_of=T, basis=PriceAdjustmentBasis.CORPORATE_ACTION_ADJUSTED)
    assert adjusted.status is HistoricalIntegrityStatus.VALID and adjusted.technical_eligible


def test_adjusted_unadjusted_provider_mismatch_is_material_conflict_not_averaged():
    left = _bar("a", T, AdjustmentStatus.RAW); right = _bar("b", T, AdjustmentStatus.ADJUSTED)
    result = ReconciliationService().reconcile_bars(left, right, as_of=T, retrieved_at=T)
    assert result.status is ReconciliationStatus.MATERIAL_CONFLICT
    assert "ADJUSTMENT_POLICY_MISMATCH" in result.conflicts


def test_todays_taxonomy_does_not_leak_into_old_analysis(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy.sqlite"); store = TaxonomySnapshotStore(repository)
    current = InstrumentTaxonomyClassification("current", "NSE:STABLE", "Cables", "Electrical", "Industrials", "official", ClassificationSourceStatus.OFFICIAL, T - timedelta(days=1), None, T, 1.0, "v1")
    store.save_classification(current)
    assert store.classification_as_of("NSE:STABLE", T - timedelta(days=365)) is None


def test_unknown_or_mixed_adjustment_basis_fails_closed_without_price_rewrite():
    service = HistoricalPriceIntegrityService()
    mixed = service.assess(instrument_id="NSE:STABLE", bars=(_bar("raw", T - timedelta(days=1), AdjustmentStatus.RAW), _bar("adjusted", T, AdjustmentStatus.ADJUSTED)), actions=(), as_of=T, basis=PriceAdjustmentBasis.CORPORATE_ACTION_ADJUSTED)
    unknown = service.assess(instrument_id="NSE:STABLE", bars=(_bar("unknown", T, AdjustmentStatus.RAW),), actions=(), as_of=T, basis=PriceAdjustmentBasis.UNKNOWN)
    assert mixed.status is HistoricalIntegrityStatus.INVALID and "ADJUSTMENT_MISMATCH" in mixed.warnings
    assert unknown.status is HistoricalIntegrityStatus.PARTIAL and "PRICE_ADJUSTMENT_BASIS_UNKNOWN" in unknown.warnings


def test_corporate_action_import_is_separate_local_and_dry_run_safe(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "actions.sqlite"); store = HistoricalSecurityMasterStore(repository)
    path = tmp_path / "actions.csv"
    path.write_text("CANONICAL_INSTRUMENT_ID,ACTION_TYPE,EFFECTIVE_DATE,SOURCE,RATIO_NUMERATOR,RATIO_DENOMINATOR\nNSE:STABLE,SPLIT,2026-08-20T00:00:00+00:00,official,2,1\n", encoding="utf-8")
    importer = HistoricalCorporateActionCsvImporter(store)
    assert importer.import_actions(path, as_of=T, dry_run=True) == 1
    assert store.actions_as_of("NSE:STABLE", T) == ()
    assert importer.import_actions(path, as_of=T, dry_run=False) == 1
    assert store.actions_as_of("NSE:STABLE", T)[0].kind is CorporateActionKind.SPLIT


@dataclass(frozen=True)
class _NseInstrument:
    instrument_id: str
    symbol: str


def _nse_export(path: Path, rows: str) -> None:
    path.write_text(
        "SYMBOL,COMPANY NAME,SERIES,PURPOSE,FACE VALUE,EX-DATE,RECORD DATE,BOOK CLOSURE START DATE,BOOK CLOSURE END DATE\n"
        + rows,
        encoding="utf-8",
    )


def test_nse_official_corporate_action_adapter_maps_eq_symbol_dates_ratios_and_provenance(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "nse-actions.sqlite")
    store = HistoricalSecurityMasterStore(repository)
    path = tmp_path / "nse-ca.csv"
    _nse_export(path, (
        'SAFE,"Safe Limited",EQ,"Bonus 1:1",10,12-Dec-2023,12-Dec-2023,-,-\n'
        'SPLIT,"Split Limited",EQ,"Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share",10,21-Jun-2024,21-Jun-2024,-,-\n'
        'RIGHTS,"Rights Limited",EQ,"Rights 3:8 @ Premium Rs 247/-",10,23-May-2025,23-May-2025,-,-\n'
        'DIV,"Dividend Limited",EQ,"Dividend - Rs 2 Per Share",10,01-Jan-2025,01-Jan-2025,-,-\n'
        'SAFE,"Safe Limited",BE,"Bonus 1:1",10,01-Jan-2025,01-Jan-2025,-,-\n'
    ))
    importer = NseOfficialCorporateActionCsvImporter(store)
    report = importer.import_frozen_cohort(
        path, instruments=(_NseInstrument("NSE:SAFE", "SAFE"), _NseInstrument("NSE:SPLIT", "SPLIT"), _NseInstrument("NSE:RIGHTS", "RIGHTS")),
        imported_at=T, dry_run=True,
    )
    assert report.total_rows == 5 and report.supported_rows == 4 and report.matched_rows == 3
    assert report.skipped_non_equity_rows == 1 and store.actions_as_of("NSE:SAFE", T) == ()
    actions = {item.kind: item for item in report.actions}
    assert actions[CorporateActionKind.BONUS].effective_date == datetime(2023, 12, 12, tzinfo=UTC)
    assert actions[CorporateActionKind.BONUS].record_date == datetime(2023, 12, 12, tzinfo=UTC)
    assert (actions[CorporateActionKind.BONUS].ratio_numerator, actions[CorporateActionKind.BONUS].ratio_denominator) == (Decimal("1"), Decimal("1"))
    assert (actions[CorporateActionKind.SPLIT].ratio_numerator, actions[CorporateActionKind.SPLIT].ratio_denominator) == (Decimal("10"), Decimal("2"))
    assert (actions[CorporateActionKind.RIGHTS].ratio_numerator, actions[CorporateActionKind.RIGHTS].ratio_denominator) == (Decimal("3"), Decimal("8"))
    assert actions[CorporateActionKind.BONUS].source == "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT"
    assert "mapping_method=EXACT_SYMBOL_EQ" in (actions[CorporateActionKind.BONUS].source_reference or "")
    assert "MAPPING_METHOD_EXACT_SYMBOL_EQ" in actions[CorporateActionKind.BONUS].warnings
    assert "original_purpose" in (actions[CorporateActionKind.BONUS].details or "")


def test_nse_official_corporate_action_adapter_rejects_ambiguous_and_retains_unparseable_ratio_warning(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "nse-ambiguous.sqlite")
    store = HistoricalSecurityMasterStore(repository)
    path = tmp_path / "nse-ca.csv"
    _nse_export(path, 'DUP,"Duplicate Limited",EQ,"Bonus as applicable",10,12-Dec-2023,12-Dec-2023,-,-\n')
    report = NseOfficialCorporateActionCsvImporter(store).preview(
        path, instruments=(_NseInstrument("NSE:DUP-A", "DUP"), _NseInstrument("NSE:DUP-B", "DUP")), imported_at=T,
    )
    assert report.ambiguous_rows == 1 and report.actions == ()
    report = NseOfficialCorporateActionCsvImporter(store).preview(
        path, instruments=(_NseInstrument("NSE:DUP", "DUP"),), imported_at=T,
    )
    assert report.actions[0].ratio_numerator is None and "RATIO_UNPARSEABLE" in report.actions[0].warnings


def test_nse_official_corporate_action_adapter_uses_unique_isin_backed_identity_when_legacy_symbol_copy_exists(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "nse-canonical-symbol.sqlite")
    store = HistoricalSecurityMasterStore(repository)
    path = tmp_path / "nse-ca.csv"
    _nse_export(path, 'SAFE,"Safe Limited",EQ,"Bonus 1:1",10,12-Dec-2023,12-Dec-2023,-,-\n')

    class _CanonicalInstrument:
        def __init__(self, instrument_id, symbol, isin): self.instrument_id, self.symbol, self.isin = instrument_id, symbol, isin

    report = NseOfficialCorporateActionCsvImporter(store).preview(
        path,
        instruments=(_CanonicalInstrument("NSE:SAFE-LEGACY", "SAFE", None), _CanonicalInstrument("NSE:INE000A01001", "SAFE", "INE000A01001")),
        imported_at=T,
    )

    assert report.matched_rows == 1 and report.ambiguous_rows == 0
    assert report.actions[0].canonical_instrument_id == "NSE:INE000A01001"
    assert "mapping_method=EXACT_SYMBOL_EQ_CANONICAL_ISIN" in (report.actions[0].source_reference or "")


def test_nse_official_corporate_action_adapter_persists_immutably_and_raw_crossing_remains_partial(tmp_path: Path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "nse-persist.sqlite")
    store = HistoricalSecurityMasterStore(repository)
    path = tmp_path / "nse-ca.csv"
    _nse_export(path, 'SAFE,"Safe Limited",EQ,"Bonus 1:1",10,12-Dec-2023,12-Dec-2023,-,-\n')
    importer = NseOfficialCorporateActionCsvImporter(store)
    report = importer.import_frozen_cohort(path, instruments=(_NseInstrument("NSE:STABLE", "SAFE"),), imported_at=T)
    persisted = store.actions_as_of("NSE:STABLE", T)
    assert persisted == report.actions
    # The official export's retrieval/import timestamp is a PIT boundary: an
    # old ex-date alone never makes later-imported evidence visible earlier.
    assert store.actions_as_of("NSE:STABLE", T - timedelta(seconds=1)) == ()
    try:
        importer.import_frozen_cohort(path, instruments=(_NseInstrument("NSE:STABLE", "SAFE"),), imported_at=T)
    except ValueError:
        pass
    else:  # Existing immutable snapshot boundary must not overwrite this source row.
        raise AssertionError("duplicate corporate action was silently overwritten")
    raw = HistoricalPriceIntegrityService().assess(
        instrument_id="NSE:STABLE",
        bars=(_bar("before", datetime(2023, 12, 11, tzinfo=UTC)), _bar("after", datetime(2023, 12, 13, tzinfo=UTC))),
        actions=persisted, as_of=T, basis=PriceAdjustmentBasis.RAW,
    )
    assert raw.status is HistoricalIntegrityStatus.PARTIAL
    assert "RAW_SERIES_SPANS_PRICE_TRANSFORMING_ACTION" in raw.warnings
    assert raw.bar_ids == ("before", "after")  # No source bar was rewritten.


def test_backtest_integrity_gate_preserves_partial_membership_and_invalid_basis():
    universe = HistoricalUniverseService().get_universe(universe_id="U", as_of=T, memberships=(), source_complete=False)
    no_bars = HistoricalPriceIntegrityService().assess(instrument_id="NSE:STABLE", bars=(), actions=(), as_of=T, basis=PriceAdjustmentBasis.RAW)
    result = HistoricalBacktestIntegrityGate().assess(dataset_or_run_id="run", universe=universe, prices=(no_bars,))
    assert result.status is HistoricalIntegrityStatus.UNAVAILABLE
