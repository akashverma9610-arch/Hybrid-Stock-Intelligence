"""Official NSE Indices sector-index registry and fail-closed mapping import.

This consumes only locally archived, visible official NSE Indices pages and
their documented constituent CSV downloads.  Historical Daily index OHLC is a
separate, bounded first-party source contract in
``official_nse_index_ohlc``; this mapping importer neither fetches it nor
claims historical PIT availability.
"""
from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.taxonomy.nse_indices import NseIndustryHierarchyEntry


NSE_INDICES_OFFICIAL = "NSE_INDICES_OFFICIAL"
SECTORAL_PAGE_URL = "https://www.niftyindices.com/indices/equity/sectoral-indices"
HISTORICAL_REPORT_URL = "https://www.niftyindices.com/reports/historical-data"


class SectorIndexMappingStatus(StrEnum):
    EXACT_OFFICIAL = "EXACT_OFFICIAL"
    DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS = "DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS"
    AMBIGUOUS = "AMBIGUOUS"
    NO_OFFICIAL_SECTOR_INDEX = "NO_OFFICIAL_SECTOR_INDEX"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class NseSectorIndexSourceArtifact:
    artifact_id: str
    source_name: str
    source_url: str
    local_path: str
    sha256: str
    content_length: int
    fetched_at_utc: datetime
    content_type: str
    canonical_authority: bool = True
    provider: str = NSE_INDICES_OFFICIAL


@dataclass(frozen=True, slots=True)
class NseSectorIndexRegistryEntry:
    registry_id: str
    official_index_name: str
    official_page: str
    index_type: str
    official_description: str | None
    constituent_download_identity: str | None
    source_artifact_sha256: str
    fetched_at_utc: datetime


@dataclass(frozen=True, slots=True)
class NseSectorIndexMapping:
    mapping_id: str
    canonical_sector: str
    official_index_name: str | None
    official_page: str | None
    status: SectorIndexMappingStatus
    evidence: tuple[str, ...]
    source_artifact_sha256: str
    fetched_at_utc: datetime
    historical_pit_eligible: bool = False


@dataclass(frozen=True, slots=True)
class NseSectorIndexConstituent:
    constituent_id: str
    official_index_name: str
    company_name: str
    symbol: str
    isin: str
    series: str
    raw_classification_label: str
    source_artifact_sha256: str
    source_as_of_date: str | None
    fetched_at_utc: datetime


@dataclass(frozen=True, slots=True)
class NseSectorIndexImportReport:
    indices_discovered: int
    mapped_exact: int
    mapped_deterministic: int
    ambiguous: int
    no_official_sector_index: int
    unresolved: int
    constituents_saved: int
    source_artifacts: tuple[NseSectorIndexSourceArtifact, ...]
    mappings: tuple[NseSectorIndexMapping, ...]
    warnings: tuple[str, ...]


# An accepted relation needs terms from a retained official description. This
# intentionally omits broader/narrower pairs such as Banks/Financial Services
# and Pharma/Healthcare.
_EXACT_DESCRIPTION_RULES: dict[str, tuple[str, tuple[str, ...]]] = {
    "Capital Goods": ("Nifty Capital Goods", ("capital goods sector",)),
    "Chemicals": ("Nifty Chemicals", ("chemicals sector",)),
    "Construction": ("Nifty Construction", ("construction sector",)),
    "Consumer Durables": ("Nifty Consumer Durables", ("consumer durables industry",)),
    "Consumer Services": ("Nifty Consumer Services", ("consumer services sector",)),
    "Financial Services": ("Nifty Financial Services", ("financial institutions", "other financial services companies")),
    "Fast Moving Consumer Goods": ("Nifty FMCG", ("fast moving consumer goods",)),
    "Healthcare": ("Nifty Healthcare", ("healthcare companies",)),
    "Information Technology": (
        "Nifty IT",
        ("information technology", "it segment of the market"),
    ),
    "Media, Entertainment & Publication": ("Nifty Media", ("media & entertainment sector", "printing and publishing")),
    "Metals & Mining": ("Nifty Metal", ("metals sector including mining",)),
    "Power": ("Nifty Power", ("power sector",)),
    "Realty": ("Nifty Realty", ("real estate companies",)),
}


class NseSectorIndexImporter:
    """Persist current official index identities and evidenced sector mappings."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def import_files(
        self, *, sectoral_page: Path, individual_pages: Iterable[Path], hierarchy: Iterable[NseIndustryHierarchyEntry],
        constituent_files: Iterable[Path] = (), historical_report_page: Path | None = None,
        fetched_at: datetime | None = None, dry_run: bool = False,
    ) -> NseSectorIndexImportReport:
        at = (fetched_at or datetime.now(UTC)).astimezone(UTC)
        if at.tzinfo is None:
            raise ValueError("NSE_SECTOR_INDEX_FETCH_TIME_MUST_BE_TIMEZONE_AWARE")
        pages = tuple(individual_pages); files = tuple(constituent_files)
        main_artifact = _artifact("NSE_SECTORAL_INDICES_PAGE", sectoral_page, SECTORAL_PAGE_URL, "text/html", at)
        page_artifacts = tuple(_artifact("NSE_SECTOR_INDEX_PAGE:" + path.stem, path, _page_url(path.stem), "text/html", at) for path in pages)
        constituent_artifacts = tuple(_artifact("NSE_SECTOR_INDEX_CONSTITUENTS:" + path.stem, path, _constituent_url(path.name), "text/csv", at) for path in files)
        historical_artifact = (_artifact("NSE_INDICES_HISTORICAL_REPORT_PAGE", historical_report_page, HISTORICAL_REPORT_URL, "text/html", at),) if historical_report_page else ()
        artifacts = (main_artifact, *page_artifacts, *constituent_artifacts, *historical_artifact)
        registry = _registry(sectoral_page, main_artifact, tuple(zip(pages, page_artifacts, strict=True)))
        mappings = _mappings(tuple(sorted({entry.sector_name for entry in hierarchy})), registry, main_artifact, at)
        constituents = _constituents(files, registry, constituent_artifacts, at)
        if not dry_run:
            for artifact in artifacts:
                self._save(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_SOURCE, "nse-sector-index-source:" + artifact.sha256, "nse-sector-index-source-v1", artifact, artifact.fetched_at_utc)
            for entry in registry:
                self._save(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_REGISTRY, "nse-sector-index-registry:" + entry.registry_id, "nse-sector-index-registry-v1", entry, entry.fetched_at_utc)
            for mapping in mappings:
                self._save(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, "nse-sector-index-mapping:" + mapping.mapping_id, "nse-sector-index-mapping-v1", mapping, mapping.fetched_at_utc)
            for constituent in constituents:
                self._save(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, "nse-sector-index-constituent:" + constituent.constituent_id, "nse-sector-index-constituent-v1", constituent, constituent.fetched_at_utc)
        counts = {status: sum(item.status is status for item in mappings) for status in SectorIndexMappingStatus}
        return NseSectorIndexImportReport(
            len(registry), counts[SectorIndexMappingStatus.EXACT_OFFICIAL], counts[SectorIndexMappingStatus.DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS],
            counts[SectorIndexMappingStatus.AMBIGUOUS], counts[SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX], counts[SectorIndexMappingStatus.UNRESOLVED],
            len(constituents), artifacts, mappings,
            ("CURRENT_FORWARD_ONLY", "HISTORICAL_BREADTH_NOT_PIT_VALID", "NSE_INDICES_HISTORICAL_EXPORT_UNAVAILABLE"),
        )

    def write_reports(self, report: NseSectorIndexImportReport, directory: Path, *, frozen40_taxonomy_matches: int | None = None) -> tuple[Path, Path]:
        directory.mkdir(parents=True, exist_ok=True)
        rows = [asdict(item) | {"status": item.status.value, "evidence": " | ".join(item.evidence)} for item in report.mappings]
        payload = {
            "indices_discovered": report.indices_discovered, "mapped_exact": report.mapped_exact,
            "mapped_deterministic": report.mapped_deterministic, "ambiguous": report.ambiguous,
            "no_official_sector_index": report.no_official_sector_index, "unresolved": report.unresolved,
            "historical_index_export": "NSE_INDICES_HISTORICAL_EXPORT_UNAVAILABLE", "mappings": rows,
        }
        json_path, csv_path = directory / "nse_sector_index_mapping.json", directory / "nse_sector_index_mapping.csv"
        json_path.write_text(json.dumps(payload, sort_keys=True, indent=2, default=str), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=("canonical_sector", "official_index_name", "official_page", "status", "evidence", "historical_pit_eligible"))
            writer.writeheader(); writer.writerows({key: row.get(key) for key in writer.fieldnames} for row in rows)
        coverage_rows = [
            {
                "canonical_sector": item.canonical_sector, "official_index_name": item.official_index_name or "",
                "mapping_status": item.status.value, "official_history_status": "NSE_INDICES_HISTORICAL_EXPORT_UNAVAILABLE",
                "sessions": 0, "current_breadth_status": "UNAVAILABLE", "historical_breadth_status": "HISTORICAL_BREADTH_NOT_PIT_VALID",
                "current_sector_ready": False, "historical_pit_ready": False,
            }
            for item in report.mappings
        ]
        coverage = {
            "official_sector_indices_discovered": report.indices_discovered,
            "indices_mapped_deterministically": report.mapped_exact + report.mapped_deterministic,
            "indices_ambiguous": report.ambiguous, "indices_with_official_history": 0,
            "indices_breadth_ready": 0, "indices_current_sector_ready": 0,
            "historical_pit_ready": 0, "historical_pit_blocked": len(report.mappings),
            "frozen40_taxonomy_matches": frozen40_taxonomy_matches,
            "rows": coverage_rows,
        }
        history_json, history_csv = directory / "nse_sector_index_history_coverage.json", directory / "nse_sector_index_history_coverage.csv"
        history_json.write_text(json.dumps(coverage, sort_keys=True, indent=2, default=str), encoding="utf-8")
        with history_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=tuple(coverage_rows[0]) if coverage_rows else ("canonical_sector",))
            writer.writeheader(); writer.writerows(coverage_rows)
        return json_path, csv_path

    def _save(self, family: CoreApiSnapshotFamily, snapshot_id: str, record_type: str, payload: object, at: datetime) -> None:
        if self._repository.get_snapshot(snapshot_id) is not None:
            return
        fingerprint = sha256(json.dumps(asdict(payload), sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, family, "v1", record_type, fingerprint, at, payload))


def _registry(main_path: Path, main_artifact: NseSectorIndexSourceArtifact, individual_pages: tuple[tuple[Path, NseSectorIndexSourceArtifact], ...]) -> tuple[NseSectorIndexRegistryEntry, ...]:
    main_values: dict[str, tuple[str, str]] = {}
    for href, label in re.findall(r'href="([^"]*sectoral-indices/[^"]+)"[^>]*>\s*([^<]+?)\s*</a>', main_path.read_text(encoding="utf-8", errors="replace"), re.IGNORECASE):
        name = _text(label)
        if name.lower().startswith("nifty"):
            main_values.setdefault(_index_key(name), (name, _absolute(href)))
    detail: dict[str, tuple[str, str | None, str | None, NseSectorIndexSourceArtifact]] = {}
    for path, artifact in individual_pages:
        source = path.read_text(encoding="utf-8", errors="replace"); name = _title(source) or _name_from_slug(path.stem)
        detail[_index_key(name)] = (name, _description(source), _constituent_href(source), artifact)
    rows = []
    for key, (name, page) in main_values.items():
        official_name, description, download, artifact = detail.get(key, (name, None, None, main_artifact))
        registry_id = sha256(f"{official_name}|{page}|{artifact.sha256}".encode()).hexdigest()[:24]
        rows.append(NseSectorIndexRegistryEntry(registry_id, official_name, page, "SECTORAL", description, download, artifact.sha256, artifact.fetched_at_utc))
    return tuple(sorted(rows, key=lambda item: item.official_index_name))


def _mappings(canonical_sectors: tuple[str, ...], registry: tuple[NseSectorIndexRegistryEntry, ...], source: NseSectorIndexSourceArtifact, at: datetime) -> tuple[NseSectorIndexMapping, ...]:
    by_name = {_index_key(item.official_index_name): item for item in registry}; result = []
    for sector in canonical_sectors:
        rule = _EXACT_DESCRIPTION_RULES.get(sector); selected = None
        if rule:
            target_name, terms = rule; candidate = by_name.get(_index_key(target_name)); description = _key(candidate.official_description or "") if candidate else ""
            if candidate and all(_key(term) in description for term in terms): selected = candidate
        if selected:
            status, name, page = SectorIndexMappingStatus.EXACT_OFFICIAL, selected.official_index_name, selected.official_page
            evidence = ("OFFICIAL_INDEX_NAME=" + name, "OFFICIAL_DESCRIPTION=" + (selected.official_description or ""), "NSE_INDICES_TAXONOMY_SECTOR=" + sector)
        else:
            financial_options = tuple(item.official_index_name for item in registry if "FINANCIAL" in _key(item.official_index_name) or "BANK" in _key(item.official_index_name))
            if sector == "Financial Services" and len(financial_options) > 1 and not by_name.get(_index_key("Nifty Financial Services")):
                status, name, page, evidence = SectorIndexMappingStatus.AMBIGUOUS, None, None, tuple(sorted(financial_options))
            elif any(_key(sector) in _key(item.official_index_name) for item in registry):
                status, name, page, evidence = SectorIndexMappingStatus.UNRESOLVED, None, None, ("OFFICIAL_DESCRIPTION_EVIDENCE_INSUFFICIENT",)
            else:
                status, name, page, evidence = SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX, None, None, ("NO_DETERMINISTIC_OFFICIAL_SECTOR_INDEX",)
        mapping_id = sha256(f"{sector}|{name}|{source.sha256}".encode()).hexdigest()[:24]
        result.append(NseSectorIndexMapping(mapping_id, sector, name, page, status, evidence, source.sha256, at))
    return tuple(result)


def _constituents(paths: tuple[Path, ...], registry: tuple[NseSectorIndexRegistryEntry, ...], artifacts: tuple[NseSectorIndexSourceArtifact, ...], at: datetime) -> tuple[NseSectorIndexConstituent, ...]:
    by_download = {_key(item.constituent_download_identity or ""): item for item in registry if item.constituent_download_identity}; rows: list[NseSectorIndexConstituent] = []
    for path, artifact in zip(paths, artifacts, strict=True):
        entry = by_download.get(_key(_constituent_url(path.name)))
        if entry is None: continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                value = {_key(key): _text(raw) for key, raw in row.items() if key is not None}; symbol, isin = value.get("SYMBOL", ""), value.get("ISIN CODE", "")
                if not symbol or not isin: continue
                identity = sha256(f"{entry.registry_id}|{symbol}|{isin}|{artifact.sha256}".encode()).hexdigest()[:24]
                rows.append(NseSectorIndexConstituent(identity, entry.official_index_name, value.get("COMPANY NAME", ""), symbol, isin, value.get("SERIES", ""), value.get("INDUSTRY", ""), artifact.sha256, None, at))
    return tuple(rows)


def _artifact(name: str, path: Path, source_url: str, content_type: str, at: datetime) -> NseSectorIndexSourceArtifact:
    raw = path.read_bytes(); checksum = sha256(raw).hexdigest()
    return NseSectorIndexSourceArtifact("nse-sector-index-source:" + checksum[:24], name, source_url, str(path), checksum, len(raw), at, content_type)


def _title(source: str) -> str | None:
    match = re.search(r'<[^>]*(?:title|alt)="(?P<name>Nifty[^\"]+)"', source, re.IGNORECASE)
    return _text(match.group("name")) if match else None


def _description(source: str) -> str | None:
    marker = re.search(r'(?is)(The\s+Nifty.{0,800}?designed\s+to\s+reflect.{0,1000}?)(?:<div|<h[1-6]|Highlights)', source)
    if marker:
        return _text(marker.group(1))
    # NSE Indices' visible ``NiftyInfoCont`` block is the authoritative
    # dedicated-page description for a few products whose prose does not use
    # the otherwise common "The Nifty ... designed to reflect" wording.
    info = re.search(r'(?is)<div[^>]+class="[^"]*\bNiftyInfoCont\b[^"]*"[^>]*>(?P<value>.*?)</div>\s*</div>', source)
    return _text(info.group("value")) if info else None


def _constituent_href(source: str) -> str | None:
    match = re.search(r'(?is)<a[^>]+href="(?P<href>[^"]+)"[^>]*>\s*Index Constituent\s*</a>', source)
    return _absolute(html.unescape(match.group("href"))) if match else None


def _absolute(value: str) -> str: return value if value.startswith("http") else "https://www.niftyindices.com/" + value.lstrip("/")
def _page_url(slug: str) -> str: return SECTORAL_PAGE_URL + "/" + slug
def _constituent_url(name: str) -> str: return "https://www.niftyindices.com/IndexConstituent/" + name
def _name_from_slug(value: str) -> str: return " ".join(part.capitalize() for part in value.replace("-index", "").split("-"))
def _text(value: object) -> str: return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()
def _key(value: object) -> str: return re.sub(r"[^A-Z0-9]+", " ", _text(value).upper()).strip()
def _index_key(value: object) -> str: return re.sub(r"\b(?:INDEX|LOGO)\b", "", _key(value)).strip()


__all__ = ("HISTORICAL_REPORT_URL", "NSE_INDICES_OFFICIAL", "NseSectorIndexConstituent", "NseSectorIndexImportReport", "NseSectorIndexImporter", "NseSectorIndexMapping", "NseSectorIndexRegistryEntry", "NseSectorIndexSourceArtifact", "SECTORAL_PAGE_URL", "SectorIndexMappingStatus")
