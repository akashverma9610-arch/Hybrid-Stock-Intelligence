"""Strict local taxonomy import and immutable Core-snapshot persistence."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Iterable

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification, ThemeMembership


@dataclass(frozen=True, slots=True)
class TaxonomyImportReport:
    accepted: int
    unresolved: int
    ambiguous: int
    dry_run: bool
    warnings: tuple[str, ...] = ()


class TaxonomySnapshotStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_classification(self, value: InstrumentTaxonomyClassification) -> None:
        self._save(CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION, "taxonomy:" + value.classification_id, value, value.as_of)

    def save_theme_membership(self, value: ThemeMembership) -> None:
        self._save(CoreApiSnapshotFamily.THEME_MEMBERSHIP, "theme:" + value.membership_id, value, value.as_of)

    def classification_as_of(self, instrument_id: str, at: datetime) -> InstrumentTaxonomyClassification | None:
        values = tuple(item.payload for item in self._all(CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION)
                       if isinstance(item.payload, InstrumentTaxonomyClassification) and item.payload.instrument_id == instrument_id and item.payload.eligible_as_of(at))
        return max(values, key=lambda item: (item.effective_from, item.as_of, item.classification_id)) if values else None

    def classifications_as_of(self, instrument_ids: Iterable[str], at: datetime) -> dict[str, InstrumentTaxonomyClassification]:
        """Resolve many PIT classifications from one immutable snapshot scan."""
        requested = set(instrument_ids)
        resolved: dict[str, InstrumentTaxonomyClassification] = {}
        for item in self._all(CoreApiSnapshotFamily.TAXONOMY_CLASSIFICATION):
            value = item.payload
            if not isinstance(value, InstrumentTaxonomyClassification) or value.instrument_id not in requested or not value.eligible_as_of(at):
                continue
            prior = resolved.get(value.instrument_id)
            if prior is None or (value.effective_from, value.as_of, value.classification_id) > (prior.effective_from, prior.as_of, prior.classification_id):
                resolved[value.instrument_id] = value
        return resolved

    def themes_as_of(self, instrument_id: str, at: datetime) -> tuple[ThemeMembership, ...]:
        return tuple(sorted((item.payload for item in self._all(CoreApiSnapshotFamily.THEME_MEMBERSHIP)
                             if isinstance(item.payload, ThemeMembership) and item.payload.instrument_id == instrument_id and item.payload.eligible_as_of(at)), key=lambda item: (item.theme, item.membership_id)))

    def _save(self, family: CoreApiSnapshotFamily, snapshot_id: str, payload: object, created_at: datetime) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, family, "v1", "taxonomy-v1", sha256(repr(payload).encode()).hexdigest(), created_at, payload))

    def _all(self, family: CoreApiSnapshotFamily):
        values = []; offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset); values.extend(page)
            if len(page) < 100: return tuple(values)
            offset += len(page)


class TaxonomyCsvImporter:
    """ISIN-first local import; symbol fallback is accepted only if unique."""
    REQUIRED = {"INDUSTRY", "SECTOR", "SUPER_SECTOR", "SOURCE", "EFFECTIVE_FROM"}

    def __init__(self, store: TaxonomySnapshotStore) -> None:
        self._store = store

    def import_csv(self, path: str | Path, *, instruments: tuple[NseEquityInstrument, ...], as_of: datetime, dry_run: bool = False) -> TaxonomyImportReport:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            rows = tuple({(key or "").strip().upper(): (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle))
        if not rows or not self.REQUIRED.issubset(rows[0]):
            raise ValueError("Taxonomy CSV requires INDUSTRY, SECTOR, SUPER_SECTOR, SOURCE, EFFECTIVE_FROM plus ISIN or SYMBOL.")
        by_isin = {item.isin: item for item in instruments if item.isin}
        by_symbol: dict[str, tuple[NseEquityInstrument, ...]] = {}
        for item in instruments: by_symbol[item.symbol] = (*by_symbol.get(item.symbol, ()), item)
        accepted = unresolved = ambiguous = 0
        for index, row in enumerate(rows, start=1):
            instrument = by_isin.get(row.get("ISIN") or "")
            if instrument is None:
                candidates = by_symbol.get(row.get("SYMBOL") or "", ())
                if len(candidates) == 1: instrument = candidates[0]
                elif len(candidates) > 1: ambiguous += 1; continue
            if instrument is None: unresolved += 1; continue
            effective = datetime.fromisoformat(row["EFFECTIVE_FROM"])
            if effective.tzinfo is None: raise ValueError("Taxonomy EFFECTIVE_FROM must be timezone-aware.")
            status = ClassificationSourceStatus(row.get("SOURCE_TYPE") or "UNKNOWN")
            value = InstrumentTaxonomyClassification(
                "taxonomy-" + sha256(f"{instrument.instrument_id}|{row}|{index}".encode()).hexdigest()[:20], instrument.instrument_id,
                row.get("INDUSTRY") or None, row.get("SECTOR") or None, row.get("SUPER_SECTOR") or None,
                row["SOURCE"], status, effective,
                datetime.fromisoformat(row["EFFECTIVE_TO"]) if row.get("EFFECTIVE_TO") else None,
                as_of, float(row["CONFIDENCE"]) if row.get("CONFIDENCE") else None, row.get("CLASSIFICATION_VERSION") or "taxonomy-v1",
                row.get("SOURCE_REFERENCE") or None,
            )
            if not dry_run: self._store.save_classification(value)
            accepted += 1
        warning = ("TAXONOMY_SOURCE_REQUIRED",) if not accepted else ()
        return TaxonomyImportReport(accepted, unresolved, ambiguous, dry_run, warning)
