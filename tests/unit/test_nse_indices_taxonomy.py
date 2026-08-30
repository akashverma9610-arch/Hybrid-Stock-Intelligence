from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.real_brain.local import _taxonomy_enriched_instruments
from app.taxonomy.nse_indices import NseIndicesTaxonomyImporter, NseIndustryHierarchyEntry
from app.taxonomy.service import TaxonomySnapshotStore
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 8, 27, 10, tzinfo=UTC)
HEADER = "Company Name,Industry,Symbol,Series,ISIN Code\n"


def _instrument(symbol="ALPHA", isin="INE000A01001"):
    return NseEquityInstrument("NSE:" + isin, symbol, isin, None, None, "ACTIVE", None, True, T, "NSE")


def _hierarchy():
    return (
        NseIndustryHierarchyEntry("IN01", "Health", "IN0101", "Healthcare", "IN010101", "Hospitals", "IN010101001", "Hospitals"),
        NseIndustryHierarchyEntry("IN07", "Industrials", "IN0702", "Capital Goods", "IN070201", "Electrical", "IN070201001", "Electrical Equipment"),
    )


def _files(path: Path, *, rows: str, total_rows: str | None = None):
    (path / "nifty500.csv").write_text(HEADER + rows, encoding="utf-8")
    (path / "nifty_total_market.csv").write_text(HEADER + (total_rows or rows), encoding="utf-8")
    (path / "industry_classification_page.html").write_text("<html>official</html>", encoding="utf-8")
    (path / "industry_classification_structure_2023-07.pdf").write_bytes(b"official-structure")


def _importer(path: Path, hierarchy=_hierarchy()):
    repository = SQLiteCoreApiSnapshotRepository(path / "taxonomy.sqlite")
    return repository, NseIndicesTaxonomyImporter(TaxonomySnapshotStore(repository), repository, structure_parser=lambda _: hierarchy)


def test_official_current_taxonomy_retains_source_hash_parent_levels_and_first_observed_pit(tmp_path):
    _files(tmp_path, rows="Alpha Ltd,Healthcare,ALPHA,EQ,INE000A01001\nBeta Ltd,Capital Goods,BETA,EQ,INE000B01002\n")
    repository, importer = _importer(tmp_path)
    report = importer.import_files(
        nifty500_csv=tmp_path / "nifty500.csv", total_market_csv=tmp_path / "nifty_total_market.csv",
        structure_pdf=tmp_path / "industry_classification_structure_2023-07.pdf", classification_page=tmp_path / "industry_classification_page.html",
        instruments=(_instrument(), _instrument("BETA", "INE000B01002")), frozen_instrument_ids=("NSE:INE000A01001",), fetched_at=T,
    )
    assert (report.classifications_saved, report.exact_unique, report.not_found) == (2, 2, 0)
    store = TaxonomySnapshotStore(repository)
    assert store.classification_as_of("NSE:INE000A01001", T - timedelta(microseconds=1)) is None
    alpha = store.classification_as_of("NSE:INE000A01001", T)
    assert alpha is not None and (alpha.super_sector, alpha.sector, alpha.industry, alpha.basic_industry) == ("Health", "Healthcare", None, None)
    assert alpha.raw_classification_label == "Healthcare" and alpha.resolution_status == "EXACT_UNIQUE"
    assert alpha.source_sha256 and alpha.effective_observation_semantics == "FIRST_OBSERVED_OFFICIAL_SNAPSHOT"
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.NSE_INDICES_TAXONOMY_SOURCE, limit=100)) == 4


def test_official_duplicate_and_isin_symbol_conflict_fail_closed(tmp_path):
    duplicate = "Alpha Ltd,Healthcare,ALPHA,EQ,INE000A01001\nAlpha Again,Healthcare,ALPHA,EQ,INE000A01001\n"
    _files(tmp_path, rows=duplicate)
    repository, importer = _importer(tmp_path)
    report = importer.import_files(
        nifty500_csv=tmp_path / "nifty500.csv", total_market_csv=tmp_path / "nifty_total_market.csv",
        structure_pdf=tmp_path / "industry_classification_structure_2023-07.pdf", classification_page=tmp_path / "industry_classification_page.html",
        instruments=(_instrument(),), fetched_at=T,
    )
    assert report.classifications_saved == 0 and report.duplicate_symbols > 0
    assert TaxonomySnapshotStore(repository).classification_as_of("NSE:INE000A01001", T) is None


def test_ambiguous_label_is_not_guessed_and_later_snapshot_appends(tmp_path):
    _files(tmp_path, rows="Alpha Ltd,Shared,ALPHA,EQ,INE000A01001\n")
    hierarchy = (
        NseIndustryHierarchyEntry("IN01", "One", "IN0101", "Shared", "IN010101", "One Industry", "IN010101001", "One Basic"),
        NseIndustryHierarchyEntry("IN02", "Two", "IN0201", "Shared", "IN020101", "Two Industry", "IN020101001", "Two Basic"),
    )
    repository, importer = _importer(tmp_path, hierarchy)
    report = importer.import_files(
        nifty500_csv=tmp_path / "nifty500.csv", total_market_csv=tmp_path / "nifty_total_market.csv",
        structure_pdf=tmp_path / "industry_classification_structure_2023-07.pdf", classification_page=tmp_path / "industry_classification_page.html",
        instruments=(_instrument(),), fetched_at=T,
    )
    assert report.classifications_saved == 0 and report.exact_ambiguous == 1
    assert TaxonomySnapshotStore(repository).classification_as_of("NSE:INE000A01001", T) is None


def test_later_official_snapshot_appends_without_yahoo_or_basic_industry_fabrication(tmp_path):
    _files(tmp_path, rows="Alpha Ltd,Healthcare,ALPHA,EQ,INE000A01001\n")
    repository, importer = _importer(tmp_path)
    arguments = dict(
        nifty500_csv=tmp_path / "nifty500.csv", total_market_csv=tmp_path / "nifty_total_market.csv",
        structure_pdf=tmp_path / "industry_classification_structure_2023-07.pdf", classification_page=tmp_path / "industry_classification_page.html",
        instruments=(_instrument(),),
    )
    first = importer.import_files(**arguments, fetched_at=T)
    second = importer.import_files(**arguments, fetched_at=T + timedelta(days=1))
    assert (first.classifications_saved, second.classifications_saved) == (1, 1)
    snapshots = repository.list_snapshots(CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION, limit=100)
    assert len(snapshots) == 2
    values = [item.payload for item in snapshots]
    assert all(value.source == "NSE_INDICES_OFFICIAL" and value.basic_industry is None for value in values)
    assert all("YAHOO" not in value.source_reference for value in values)


def test_taxonomy_composition_is_forward_only_and_never_backdates_a_trial(tmp_path):
    _files(tmp_path, rows="Alpha Ltd,Healthcare,ALPHA,EQ,INE000A01001\n")
    repository, importer = _importer(tmp_path)
    importer.import_files(
        nifty500_csv=tmp_path / "nifty500.csv", total_market_csv=tmp_path / "nifty_total_market.csv",
        structure_pdf=tmp_path / "industry_classification_structure_2023-07.pdf", classification_page=tmp_path / "industry_classification_page.html",
        instruments=(_instrument(),), fetched_at=T,
    )
    taxonomy = TaxonomySnapshotStore(repository)
    original = _instrument()
    historical = _taxonomy_enriched_instruments((original,), taxonomy, T - timedelta(microseconds=1))
    forward = _taxonomy_enriched_instruments((original,), taxonomy, T)
    assert historical == (original,)
    assert forward[0].sector == "Healthcare"
    assert forward[0].industry is None
