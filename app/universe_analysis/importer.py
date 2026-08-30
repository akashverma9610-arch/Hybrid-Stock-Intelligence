"""Local, official-file-only NSE equity universe importer."""
from __future__ import annotations

import csv
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
import re

from .models import NseEquityInstrument, UniverseSnapshot
from .service import CoreUniverseAnalysisStore, build_universe_snapshot


@dataclass(frozen=True, slots=True)
class UniverseImportReport:
    snapshot: UniverseSnapshot
    accepted: int
    duplicates: int
    excluded: int
    warnings: tuple[str, ...]
    raw_records: int = 0
    missing_sector_count: int = 0
    missing_industry_count: int = 0
    dry_run: bool = False
    identical: bool = False
    missing_symbol_count: int = 0
    malformed_isin_count: int = 0

    @property
    def main_board_equity_records(self) -> int:
        return self.snapshot.eligible_security_count


class OfficialNseUniverseImporter:
    """Imports an explicit local official export; it performs no web request."""
    def __init__(self, store: CoreUniverseAnalysisStore) -> None: self._store = store

    def import_csv(self, path: str | Path, *, as_of: datetime, snapshot_id: str,
                   source: str = "NSE_OFFICIAL_EXPORT", dry_run: bool = False,
                   refresh_identical_as_of: bool = False) -> UniverseImportReport:
        """Import an explicit official file, or validate it without writing.

        This deliberately accepts only a caller-provided local path.  It never
        falls back to a web download or a provider instrument list.
        """
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            # NSE's official EQUITY_L export currently prefixes several header
            # cells with a space. Normalize headers here at the ingestion edge,
            # never in analytical identity logic.
            rows = tuple({(key or "").strip(): value for key, value in row.items()} for row in csv.DictReader(handle))
        selected: dict[str, NseEquityInstrument] = {}
        duplicates = 0
        missing_symbols = malformed_isins = 0
        for row in rows:
            item = _instrument(row, as_of, source)
            if not item.symbol:
                missing_symbols += 1
                continue
            if item.isin is not None and not _valid_isin(item.isin):
                malformed_isins += 1
            identity = _identity(item)
            previous = selected.get(identity)
            if previous is not None:
                duplicates += 1
                # Deterministic identity preference: a populated ISIN wins;
                # otherwise retain the first exact canonical identity.
                if previous.isin is None and item.isin is not None:
                    selected[identity] = item
                continue
            selected[identity] = item
        values = tuple(sorted(selected.values(), key=lambda item: (item.symbol, item.instrument_id)))
        snapshot = build_universe_snapshot(snapshot_id=snapshot_id, as_of=as_of, source=source, instruments=values)
        warnings = snapshot.warnings + ((f"MISSING_SYMBOL:{missing_symbols}",) if missing_symbols else ()) + ((f"MALFORMED_ISIN:{malformed_isins}",) if malformed_isins else ())
        existing = self._store.universe_snapshot_by_checksum(snapshot.checksum)
        if existing is not None and not dry_run and not (
            refresh_identical_as_of and as_of > existing.as_of
        ):
            return UniverseImportReport(
                existing, len(values), duplicates, existing.excluded_count, warnings,
                raw_records=len(rows), missing_sector_count=sum(item.sector is None for item in values),
                missing_industry_count=sum(item.industry is None for item in values), identical=True,
                missing_symbol_count=missing_symbols, malformed_isin_count=malformed_isins,
            )
        if existing is not None and refresh_identical_as_of and as_of > existing.as_of:
            # A same-content snapshot may be refreshed only forward in time.
            # The original snapshot remains immutable for historical/PIT audit;
            # this new identity makes subsequently retrieved evidence eligible.
            snapshot = replace(
                snapshot,
                warnings=snapshot.warnings + (f"IDENTICAL_CONTENT_REFRESH_OF:{existing.snapshot_id}",),
            )
            warnings = snapshot.warnings + ((f"MISSING_SYMBOL:{missing_symbols}",) if missing_symbols else ()) + ((f"MALFORMED_ISIN:{malformed_isins}",) if malformed_isins else ())
        if not dry_run:
            for item in values:
                self._store.save_instrument(item)
            self._store.save_universe_snapshot(snapshot)
        return UniverseImportReport(
            snapshot, len(values), duplicates, snapshot.excluded_count, warnings,
            raw_records=len(rows),
            missing_sector_count=sum(item.sector is None for item in values),
            missing_industry_count=sum(item.industry is None for item in values),
            dry_run=dry_run,
            missing_symbol_count=missing_symbols,
            malformed_isin_count=malformed_isins,
        )


def _instrument(row: dict[str, str], as_of: datetime, source: str) -> NseEquityInstrument:
    pick = lambda *keys: next((row[key].strip() for key in keys if row.get(key) and row[key].strip()), None)
    symbol = pick("SYMBOL", "symbol", "Symbol") or ""
    isin = pick("ISIN", "isin", "ISIN_CODE", "ISIN NUMBER")
    instrument_id = pick("INSTRUMENT_ID", "instrument_id") or (f"NSE:{isin}" if isin else f"NSE:{symbol}")
    return NseEquityInstrument(
        instrument_id, symbol, isin, pick("SECTOR", "sector"), pick("INDUSTRY", "industry"),
        pick("LISTING_STATUS", "listing_status", "STATUS") or "UNKNOWN", None,
        _bool(pick("TRADABLE", "tradable", "IS_TRADABLE")), as_of, source, pick("SOURCE_REFERENCE"),
        pick("SECURITY_TYPE", "security_type") or "EQUITY", pick("COMPANY_NAME", "NAME", "NAME OF COMPANY", "company_name"),
        pick("EXCHANGE", "exchange") or "NSE", _bool(pick("MAIN_BOARD", "main_board")),
    )


def _identity(item: NseEquityInstrument) -> str:
    if item.isin: return f"{item.exchange}:{item.isin}"
    if item.instrument_id: return f"instrument:{item.instrument_id}"
    return f"symbol:{item.exchange}:{item.symbol}"


def _bool(value: str | None) -> bool | None:
    if value is None: return None
    return value.strip().lower() in {"1", "true", "yes", "y", "active", "tradable"}


def _valid_isin(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value.upper()))
