"""Official NSE Indices constituent taxonomy import.

The importer consumes downloaded, official static files only.  It does not
discover private endpoints, use a secondary provider, or backdate a current
classification.  The existing append-only taxonomy store remains the sole
canonical classification persistence boundary.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Callable, Iterable

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.service import TaxonomySnapshotStore
from app.universe_analysis.models import NseEquityInstrument


NSE_INDICES_OFFICIAL = "NSE_INDICES_OFFICIAL"
NIFTY_500_FILENAME = "ind_nifty500list.csv"
NIFTY_TOTAL_MARKET_FILENAME = "ind_niftytotalmarket_list.csv"
REQUIRED_CONSTITUENT_FIELDS = frozenset({"COMPANY NAME", "INDUSTRY", "SYMBOL", "SERIES", "ISIN CODE"})


@dataclass(frozen=True, slots=True)
class NseIndicesSourceArtifact:
    source_id: str
    source_name: str
    source_domain: str
    source_page_identity: str
    download_identity: str
    fetched_at_utc: datetime
    sha256: str
    content_length: int
    content_type: str
    schema: tuple[str, ...]
    local_path: str
    canonical_authority: bool = True
    provider: str = NSE_INDICES_OFFICIAL


@dataclass(frozen=True, slots=True)
class NseIndicesConstituent:
    company_name: str
    raw_label: str
    symbol: str
    series: str
    isin: str
    source_name: str
    source_sha256: str
    line_number: int


@dataclass(frozen=True, slots=True)
class NseIndustryHierarchyEntry:
    macro_code: str
    macro_name: str
    sector_code: str
    sector_name: str
    industry_code: str
    industry_name: str
    basic_industry_code: str
    basic_industry_name: str


@dataclass(frozen=True, slots=True)
class NseTaxonomyResolution:
    status: str
    raw_label: str
    macro_code: str | None = None
    macro_name: str | None = None
    sector_code: str | None = None
    sector_name: str | None = None
    industry_code: str | None = None
    industry_name: str | None = None
    basic_industry_code: str | None = None
    basic_industry_name: str | None = None


@dataclass(frozen=True, slots=True)
class NseIndicesTaxonomyReport:
    source_artifacts: tuple[NseIndicesSourceArtifact, ...]
    nifty500_rows: int
    total_market_rows: int
    valid_rows: int
    duplicate_symbols: int
    duplicate_isins: int
    missing_symbol: int
    missing_isin: int
    unmapped_to_canonical_universe: int
    isin_symbol_conflicts: int
    exact_unique: int
    exact_ambiguous: int
    not_found: int
    classifications_saved: int
    reconciliations: tuple[dict[str, str], ...]
    frozen40: tuple[dict[str, str], ...]
    warnings: tuple[str, ...] = ()


class NseIndicesTaxonomyImporter:
    """Resolve current official constituent labels through the official hierarchy."""

    def __init__(self, store: TaxonomySnapshotStore, repository: CoreApiSnapshotRepository, *,
                 structure_parser: Callable[[Path], tuple[NseIndustryHierarchyEntry, ...]] | None = None) -> None:
        self._store = store
        self._repository = repository
        self._structure_parser = structure_parser or parse_nse_indices_industry_structure

    def import_files(
        self, *, nifty500_csv: Path, total_market_csv: Path, structure_pdf: Path,
        classification_page: Path, instruments: Iterable[NseEquityInstrument],
        frozen_instrument_ids: Iterable[str] = (), fetched_at: datetime | None = None,
        dry_run: bool = False,
    ) -> NseIndicesTaxonomyReport:
        now = (fetched_at or datetime.now(UTC)).astimezone(UTC)
        if now.tzinfo is None:
            raise ValueError("NSE Indices taxonomy fetch time must be timezone-aware.")
        artifacts = (
            _artifact("NIFTY_500_CONSTITUENTS", nifty500_csv, "text/csv", now),
            _artifact("NIFTY_TOTAL_MARKET_CONSTITUENTS", total_market_csv, "text/csv", now),
            _artifact("NSE_INDICES_CLASSIFICATION_PAGE", classification_page, "text/html", now),
            _artifact("NSE_INDICES_CLASSIFICATION_STRUCTURE", structure_pdf, "application/pdf", now),
        )
        nifty500, five_counts = _constituents(nifty500_csv, "NIFTY_500_CONSTITUENTS", artifacts[0].sha256)
        total, total_counts = _constituents(total_market_csv, "NIFTY_TOTAL_MARKET_CONSTITUENTS", artifacts[1].sha256)
        hierarchy = self._structure_parser(structure_pdf)
        if not hierarchy:
            raise ValueError("NSE_INDICES_CLASSIFICATION_STRUCTURE_UNAVAILABLE")
        semantic_level = _constituent_label_level((*nifty500, *total), hierarchy)
        if semantic_level is None:
            raise ValueError("NSE_INDICES_CONSTITUENT_CLASSIFICATION_SCHEMA_UNRESOLVED")
        reconciliations = _reconcile(nifty500, total)
        by_isin, by_symbol = _canonical_indexes(tuple(instruments))
        by_id = {item.instrument_id: item for values in by_isin.values() for item in values}
        frozen = set(frozen_instrument_ids)
        selected = _choose_current_rows(nifty500, total)
        duplicate_symbols = _duplicate_values((*nifty500, *total), lambda item: item.symbol)
        duplicate_isins = _duplicate_values((*nifty500, *total), lambda item: item.isin)
        exact_unique = exact_ambiguous = not_found = saved = unmapped = conflicts = 0
        frozen_rows: list[dict[str, str]] = []
        for row in selected:
            if row.symbol in duplicate_symbols or row.isin in duplicate_isins:
                exact_ambiguous += 1
                if row.symbol or row.isin:
                    frozen_rows.extend(_frozen_unresolved(row, frozen, by_isin, "DUPLICATE_OFFICIAL_IDENTITY"))
                continue
            instrument, mapping_status = _resolve_instrument(row, by_isin, by_symbol)
            if mapping_status == "ISIN_SYMBOL_CONFLICT":
                conflicts += 1
            if instrument is None:
                unmapped += 1
                continue
            resolution = resolve_nse_indices_label(row.raw_label, hierarchy, expected_level=semantic_level)
            if resolution.status == "EXACT_UNIQUE":
                exact_unique += 1
                if not dry_run:
                    value = _classification(instrument, row, resolution, now)
                    self._store.save_classification(value)
                    saved += 1
            elif resolution.status == "EXACT_AMBIGUOUS":
                exact_ambiguous += 1
            else:
                not_found += 1
            if instrument.instrument_id in frozen:
                frozen_rows.append({
                    "instrument_id": instrument.instrument_id, "symbol": instrument.symbol,
                    "raw_label": row.raw_label, "mapping_status": mapping_status,
                    "resolution_status": resolution.status,
                    "macro_sector": resolution.macro_name or "",
                    "sector": resolution.sector_name or "", "industry": resolution.industry_name or "",
                    "basic_industry": resolution.basic_industry_name or "",
                })
        observed_frozen = {item["instrument_id"] for item in frozen_rows}
        for instrument_id in sorted(frozen - observed_frozen):
            instrument = by_id.get(instrument_id)
            if instrument is not None:
                frozen_rows.append({
                    "instrument_id": instrument.instrument_id, "symbol": instrument.symbol, "raw_label": "",
                    "mapping_status": "NOT_IN_OFFICIAL_INDEX_UNIVERSE", "resolution_status": "NOT_IN_OFFICIAL_INDEX_UNIVERSE",
                    "macro_sector": "", "sector": "", "industry": "", "basic_industry": "",
                })
        if not dry_run:
            for artifact in artifacts:
                self._save_artifact(artifact)
        return NseIndicesTaxonomyReport(
            artifacts, len(nifty500), len(total), len(nifty500) + len(total),
            five_counts["duplicate_symbols"] + total_counts["duplicate_symbols"],
            five_counts["duplicate_isins"] + total_counts["duplicate_isins"],
            five_counts["missing_symbol"] + total_counts["missing_symbol"],
            five_counts["missing_isin"] + total_counts["missing_isin"], unmapped, conflicts,
            exact_unique, exact_ambiguous, not_found, saved, tuple(reconciliations),
            tuple(sorted(frozen_rows, key=lambda item: item["symbol"])),
            ("FIRST_OBSERVED_OFFICIAL_SNAPSHOT", "CURRENT_TAXONOMY_NOT_HISTORICAL", "CONSTITUENT_LABEL_LEVEL=" + semantic_level),
        )

    def _save_artifact(self, artifact: NseIndicesSourceArtifact) -> None:
        payload = asdict(artifact)
        fingerprint = sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()
        snapshot_id = "nse-indices-taxonomy-source:" + artifact.source_name.lower() + ":" + artifact.sha256
        if self._repository.get_snapshot(snapshot_id) is not None:
            return
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id,
            CoreApiSnapshotFamily.NSE_INDICES_TAXONOMY_SOURCE, "v1", "nse-indices-taxonomy-source-v1",
            fingerprint, artifact.fetched_at_utc, artifact,
        ))


def parse_nse_indices_industry_structure(path: Path) -> tuple[NseIndustryHierarchyEntry, ...]:
    """Parse the official structure PDF's tabular hierarchy without inferring rows."""
    try:
        import pdfplumber
    except ImportError as error:  # pragma: no cover - packaging failure is explicit.
        raise RuntimeError("PDFPLUMBER_REQUIRED_FOR_NSE_INDICES_STRUCTURE") from error
    current = ["", "", "", "", "", ""]
    entries: list[NseIndustryHierarchyEntry] = []
    with pdfplumber.open(path) as document:
        for page in document.pages:
            for table in page.extract_tables() or ():
                for row in table:
                    cells = [_clean(value) for value in row or ()]
                    if len(cells) < 8 or cells[0] == "MES_Code":
                        continue
                    for index, target in ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (5, 5)):
                        if cells[index]:
                            current[target] = cells[index]
                    basic_code, basic_name = cells[6], cells[7]
                    if basic_code and basic_name and all(current):
                        entries.append(NseIndustryHierarchyEntry(
                            current[0], current[1], current[2], current[3], current[4], current[5], basic_code, basic_name,
                        ))
    return tuple(entries)


def resolve_nse_indices_label(label: str, hierarchy: Iterable[NseIndustryHierarchyEntry], *, expected_level: str | None = None) -> NseTaxonomyResolution:
    normalized = _key(label)
    values = tuple(hierarchy)
    matches = {
        "BASIC_INDUSTRY": [item for item in values if _key(item.basic_industry_name) == normalized],
        "INDUSTRY": [item for item in values if _key(item.industry_name) == normalized],
        "SECTOR": [item for item in values if _key(item.sector_name) == normalized],
        "MACRO_ECONOMIC_SECTOR": [item for item in values if _key(item.macro_name) == normalized],
    }
    levels = (expected_level,) if expected_level else ("BASIC_INDUSTRY", "INDUSTRY", "SECTOR", "MACRO_ECONOMIC_SECTOR")
    for level in levels:
        value = _unique_at_level(matches[level], level)
        if value is not None:
            return NseTaxonomyResolution(
                "EXACT_UNIQUE", label, value.macro_code, value.macro_name, value.sector_code, value.sector_name,
                value.industry_code if level in {"BASIC_INDUSTRY", "INDUSTRY"} else None,
                value.industry_name if level in {"BASIC_INDUSTRY", "INDUSTRY"} else None,
                value.basic_industry_code if level == "BASIC_INDUSTRY" else None,
                value.basic_industry_name if level == "BASIC_INDUSTRY" else None,
            )
        if matches[level]:
            return NseTaxonomyResolution("EXACT_AMBIGUOUS", label)
    return NseTaxonomyResolution("NOT_FOUND", label)


def _constituent_label_level(rows: Iterable[NseIndicesConstituent], hierarchy: Iterable[NseIndustryHierarchyEntry]) -> str | None:
    """Prove the CSV column's semantic tier from exact structure alignment.

    A dated structure can legitimately lack a current constituent label.  Such
    labels remain unresolved; they do not make the clearly dominant exact tier
    into an implicit fuzzy match.
    """
    labels = {_key(item.raw_label) for item in rows if item.raw_label}
    if not labels:
        return None
    values = tuple(hierarchy)
    names = {
        "BASIC_INDUSTRY": {_key(item.basic_industry_name) for item in values},
        "INDUSTRY": {_key(item.industry_name) for item in values},
        "SECTOR": {_key(item.sector_name) for item in values},
        "MACRO_ECONOMIC_SECTOR": {_key(item.macro_name) for item in values},
    }
    scores = {level: len(labels & allowed) for level, allowed in names.items()}
    maximum = max(scores.values(), default=0)
    winners = tuple(level for level, score in scores.items() if score == maximum)
    return winners[0] if maximum and len(winners) == 1 else None


def _unique_at_level(values: list[NseIndustryHierarchyEntry], level: str) -> NseIndustryHierarchyEntry | None:
    if not values:
        return None
    if level == "BASIC_INDUSTRY":
        distinct = {(item.macro_code, item.sector_code, item.industry_code, item.basic_industry_code) for item in values}
    elif level == "INDUSTRY":
        distinct = {(item.macro_code, item.sector_code, item.industry_code) for item in values}
    elif level == "SECTOR":
        distinct = {(item.macro_code, item.sector_code) for item in values}
    else:
        distinct = {(item.macro_code,) for item in values}
    return values[0] if len(distinct) == 1 else None


def _constituents(path: Path, source_name: str, source_sha: str) -> tuple[tuple[NseIndicesConstituent, ...], dict[str, int]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = tuple((item or "").strip() for item in reader.fieldnames or ())
        normalized = {_key(item) for item in headers}
        if not REQUIRED_CONSTITUENT_FIELDS.issubset(normalized):
            raise ValueError("NSE_INDICES_CONSTITUENT_SCHEMA_UNSUPPORTED")
        rows = []
        for line, value in enumerate(reader, start=2):
            item = {_key(key): _clean(raw) for key, raw in value.items() if key is not None}
            rows.append(NseIndicesConstituent(item["COMPANY NAME"], item["INDUSTRY"], item["SYMBOL"].upper(), item["SERIES"].upper(), item["ISIN CODE"].upper(), source_name, source_sha, line))
    symbols = [item.symbol for item in rows if item.symbol]
    isins = [item.isin for item in rows if item.isin]
    counts = {
        "duplicate_symbols": len(symbols) - len(set(symbols)), "duplicate_isins": len(isins) - len(set(isins)),
        "missing_symbol": sum(not item.symbol for item in rows), "missing_isin": sum(not item.isin for item in rows),
    }
    return tuple(rows), counts


def _artifact(name: str, path: Path, content_type: str, fetched_at: datetime) -> NseIndicesSourceArtifact:
    raw = path.read_bytes(); checksum = sha256(raw).hexdigest()
    schema: tuple[str, ...] = ()
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            schema = tuple(next(csv.reader(handle)))
    return NseIndicesSourceArtifact(
        "nse-indices-source:" + checksum[:24], name, "www.niftyindices.com", "https://www.niftyindices.com/resources/industry-classification",
        str(path), fetched_at, checksum, len(raw), content_type, schema, str(path),
    )


def _canonical_indexes(values: tuple[NseEquityInstrument, ...]):
    by_isin: dict[str, list[NseEquityInstrument]] = defaultdict(list)
    by_symbol: dict[str, list[NseEquityInstrument]] = defaultdict(list)
    for item in values:
        if item.isin:
            by_isin[item.isin.upper()].append(item)
        by_symbol[item.symbol.upper()].append(item)
    return by_isin, by_symbol


def _resolve_instrument(row: NseIndicesConstituent, by_isin, by_symbol):
    isin_matches = by_isin.get(row.isin, ()) if row.isin else ()
    symbol_matches = by_symbol.get(row.symbol, ()) if row.symbol else ()
    if len(isin_matches) == 1:
        if row.symbol and row.symbol != isin_matches[0].symbol.upper():
            return None, "ISIN_SYMBOL_CONFLICT"
        return isin_matches[0], "EXACT_ISIN_AND_SYMBOL"
    if isin_matches:
        return None, "AMBIGUOUS_ISIN"
    if not row.isin and len(symbol_matches) == 1:
        return symbol_matches[0], "EXACT_UNIQUE_SYMBOL"
    return None, "UNMAPPED_TO_CANONICAL_UNIVERSE"


def _choose_current_rows(nifty500: tuple[NseIndicesConstituent, ...], total: tuple[NseIndicesConstituent, ...]) -> tuple[NseIndicesConstituent, ...]:
    """Total Market supplies broad coverage; NIFTY 500 is retained for reconciliation."""
    by_identity: dict[tuple[str, str], NseIndicesConstituent] = {}
    for item in (*nifty500, *total):
        key = (item.isin, item.symbol)
        by_identity[key] = item
    return tuple(sorted(by_identity.values(), key=lambda item: (item.symbol, item.isin)))


def _duplicate_values(rows: Iterable[NseIndicesConstituent], value) -> set[str]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        item = value(row)
        if item:
            counts[item] += 1
    # Cross-file membership overlap is expected, but same source duplicate is
    # not.  Count the occurrence within a source rather than both sources.
    per_source: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        item = value(row)
        if item:
            per_source[(row.source_name, item)] += 1
    return {item for (_, item), count in per_source.items() if count > 1}


def _frozen_unresolved(row: NseIndicesConstituent, frozen: set[str], by_isin, status: str) -> list[dict[str, str]]:
    values = by_isin.get(row.isin, ())
    return [{"instrument_id": item.instrument_id, "symbol": item.symbol, "raw_label": row.raw_label,
             "mapping_status": status, "resolution_status": status, "macro_sector": "", "sector": "", "industry": "", "basic_industry": ""}
            for item in values if item.instrument_id in frozen]


def _reconcile(left: tuple[NseIndicesConstituent, ...], right: tuple[NseIndicesConstituent, ...]) -> tuple[dict[str, str], ...]:
    by_symbol = {item.symbol: item for item in right if item.symbol}
    rows: list[dict[str, str]] = []
    for item in left:
        other = by_symbol.get(item.symbol)
        if other is None:
            continue
        if item.isin != other.isin:
            status = "ISIN_MISMATCH"
        elif item.raw_label != other.raw_label:
            status = "CLASSIFICATION_MISMATCH"
        elif item.company_name != other.company_name:
            status = "NAME_VARIATION"
        else:
            status = "MATCH"
        rows.append({"symbol": item.symbol, "isin_nifty500": item.isin, "isin_total_market": other.isin,
                     "name_nifty500": item.company_name, "name_total_market": other.company_name,
                     "classification_nifty500": item.raw_label, "classification_total_market": other.raw_label,
                     "status": status})
    return tuple(sorted(rows, key=lambda item: item["symbol"]))


def _classification(instrument: NseEquityInstrument, row: NseIndicesConstituent, resolution: NseTaxonomyResolution, observed: datetime) -> InstrumentTaxonomyClassification:
    source_reference = f"source={row.source_name};sha256={row.source_sha256};line={row.line_number};mapping=EXACT_ISIN_AND_SYMBOL"
    key = "|".join((instrument.instrument_id, row.source_sha256, row.raw_label, resolution.status, observed.isoformat()))
    return InstrumentTaxonomyClassification(
        "nse-indices-taxonomy:" + sha256(key.encode()).hexdigest()[:24], instrument.instrument_id,
        resolution.industry_name, resolution.sector_name, resolution.macro_name, NSE_INDICES_OFFICIAL,
        ClassificationSourceStatus.OFFICIAL, observed, None, observed, 1.0, "nse-indices-taxonomy-v1", source_reference,
        ("FIRST_OBSERVED_OFFICIAL_SNAPSHOT", "CURRENT_TAXONOMY_ONLY"), resolution.macro_code, resolution.sector_code,
        resolution.industry_code, resolution.basic_industry_code, resolution.basic_industry_name, row.raw_label,
        resolution.status, row.source_sha256, None, observed, "FIRST_OBSERVED_OFFICIAL_SNAPSHOT",
    )


def write_reconciliation_reports(report: NseIndicesTaxonomyReport, *, directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "nse_taxonomy_reconciliation.json"; csv_path = directory / "nse_taxonomy_reconciliation.csv"
    json_path.write_text(json.dumps({"reconciliations": report.reconciliations, "frozen40": report.frozen40}, indent=2), encoding="utf-8")
    fields = ("symbol", "isin_nifty500", "isin_total_market", "name_nifty500", "name_total_market", "classification_nifty500", "classification_total_market", "status")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(report.reconciliations)
    return json_path, csv_path


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _key(value: object) -> str:
    return _clean(value).upper()
