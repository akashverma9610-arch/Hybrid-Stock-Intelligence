from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.nse_indices import NseIndustryHierarchyEntry
from app.taxonomy.nse_sector_indices import NseSectorIndexImporter, SectorIndexMappingStatus


T = datetime(2026, 8, 27, 12, tzinfo=UTC)


def _hierarchy(*sectors: str):
    return tuple(NseIndustryHierarchyEntry("M", "Macro", f"S{index}", sector, f"I{index}", "Industry", f"B{index}", "Basic") for index, sector in enumerate(sectors, start=1))


def _source(path: Path, links: tuple[tuple[str, str], ...], pages: dict[str, str], constituents: dict[str, str] | None = None):
    (path / "pages").mkdir(); (path / "constituents").mkdir()
    (path / "sectoral_indices_page.html").write_text("".join(f'<a href="/indices/equity/sectoral-indices/{slug}">{name}</a>' for slug, name in links), encoding="utf-8")
    for slug, body in pages.items():
        (path / "pages" / f"{slug}.html").write_text(body, encoding="utf-8")
    for name, body in (constituents or {}).items():
        (path / "constituents" / name).write_text(body, encoding="utf-8")


def test_official_description_evidence_maps_only_exact_sector_and_retains_constituents(tmp_path):
    _source(
        tmp_path,
        (("nifty-chemicals", "Nifty Chemicals"),),
        {"nifty-chemicals": '<img title="Nifty Chemicals" />The Nifty Chemicals Index is designed to reflect the behaviour and performance of the chemicals sector in India. Highlights<a href="/IndexConstituent/ind_niftyChemicals_list.csv">Index Constituent</a>'},
        {"ind_niftyChemicals_list.csv": "Company Name,Industry,Symbol,Series,ISIN Code\nAlpha Chemicals,Chemicals,ALPHA,EQ,INE000A01001\n"},
    )
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "db.sqlite")
    importer = NseSectorIndexImporter(repository)
    kwargs = dict(sectoral_page=tmp_path / "sectoral_indices_page.html", individual_pages=tuple((tmp_path / "pages").glob("*.html")), constituent_files=tuple((tmp_path / "constituents").glob("*.csv")), hierarchy=_hierarchy("Chemicals"), fetched_at=T)
    first = importer.import_files(**kwargs)
    second = importer.import_files(**kwargs)
    mapping = first.mappings[0]
    assert mapping.status is SectorIndexMappingStatus.EXACT_OFFICIAL
    assert mapping.official_index_name == "Nifty Chemicals"
    assert first.constituents_saved == 1 and second.constituents_saved == 1
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100)) == 1
    assert len(repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, limit=100)) == 1


def test_visible_nifty_info_description_supports_exact_information_technology_mapping(tmp_path):
    _source(
        tmp_path,
        (("nifty-it", "Nifty IT"),),
        {
            "nifty-it": (
                '<img title="Nifty IT" />'
                '<div class="NiftyInfoCont"><h2>Information Technology (IT) industry</h2>'
                '<p>Nifty IT provides an appropriate benchmark that captures the performance '
                'of the IT segment of the market in India.</p></div></div>'
            ),
        },
        {},
    )
    report = NseSectorIndexImporter(SQLiteCoreApiSnapshotRepository(tmp_path / "db.sqlite")).import_files(
        sectoral_page=tmp_path / "sectoral_indices_page.html",
        individual_pages=tuple((tmp_path / "pages").glob("*.html")),
        hierarchy=_hierarchy("Information Technology"),
        fetched_at=T,
        dry_run=True,
    )

    mapping = report.mappings[0]
    assert mapping.status is SectorIndexMappingStatus.EXACT_OFFICIAL
    assert mapping.official_index_name == "Nifty IT"
    assert "information technology" in " ".join(mapping.evidence).casefold()


def test_financial_subindices_are_ambiguous_without_the_broad_official_index(tmp_path):
    _source(tmp_path, (("nifty-bank", "Nifty Bank"), ("nifty-private-bank", "Nifty Private Bank")), {}, {})
    report = NseSectorIndexImporter(SQLiteCoreApiSnapshotRepository(tmp_path / "db.sqlite")).import_files(
        sectoral_page=tmp_path / "sectoral_indices_page.html", individual_pages=(), hierarchy=_hierarchy("Financial Services"), fetched_at=T, dry_run=True,
    )
    assert report.mappings[0].status is SectorIndexMappingStatus.AMBIGUOUS
    assert report.mappings[0].official_index_name is None


def test_name_alone_never_creates_a_sector_mapping(tmp_path):
    _source(tmp_path, (("nifty-chemicals", "Nifty Chemicals"),), {"nifty-chemicals": '<img title="Nifty Chemicals" />'}, {})
    report = NseSectorIndexImporter(SQLiteCoreApiSnapshotRepository(tmp_path / "db.sqlite")).import_files(
        sectoral_page=tmp_path / "sectoral_indices_page.html", individual_pages=tuple((tmp_path / "pages").glob("*.html")), hierarchy=_hierarchy("Chemicals"), fetched_at=T, dry_run=True,
    )
    assert report.mappings[0].status is SectorIndexMappingStatus.UNRESOLVED


def test_mapping_is_current_forward_only_and_has_no_yahoo_or_historical_backfill(tmp_path):
    _source(tmp_path, (("nifty-chemicals", "Nifty Chemicals"),), {"nifty-chemicals": '<img title="Nifty Chemicals" />The Nifty Chemicals Index is designed to reflect chemicals sector. Highlights'}, {})
    report = NseSectorIndexImporter(SQLiteCoreApiSnapshotRepository(tmp_path / "db.sqlite")).import_files(
        sectoral_page=tmp_path / "sectoral_indices_page.html", individual_pages=tuple((tmp_path / "pages").glob("*.html")), hierarchy=_hierarchy("Chemicals"), fetched_at=T, dry_run=True,
    )
    assert report.mappings[0].historical_pit_eligible is False
    assert "HISTORICAL_BREADTH_NOT_PIT_VALID" in report.warnings
    assert "YAHOO" not in Path("app/taxonomy/nse_sector_indices.py").read_text(encoding="utf-8").upper()
