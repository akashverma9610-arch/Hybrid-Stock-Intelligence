"""Immutable historical identity, membership, corporate-action, and price-basis guards."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.market_data.models import AdjustmentStatus, CanonicalOHLCVBar
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class HistoricalIntegrityStatus(StrEnum):
    VALID = "VALID"; PARTIAL = "PARTIAL"; INVALID = "INVALID"; UNAVAILABLE = "UNAVAILABLE"


class HistoricalSecurityStatus(StrEnum):
    ACTIVE="ACTIVE"; SUSPENDED="SUSPENDED"; DELISTED="DELISTED"; MERGED="MERGED"; INACTIVE="INACTIVE"; RELISTED="RELISTED"


class CorporateActionKind(StrEnum):
    SPLIT="SPLIT"; BONUS="BONUS"; RIGHTS="RIGHTS"; DIVIDEND="DIVIDEND"; MERGER="MERGER"; DEMERGER="DEMERGER"; SYMBOL_CHANGE="SYMBOL_CHANGE"; DELISTING="DELISTING"; SUSPENSION="SUSPENSION"; RELISTING="RELISTING"


class PriceAdjustmentBasis(StrEnum):
    RAW="RAW"; SPLIT_ADJUSTED="SPLIT_ADJUSTED"; CORPORATE_ACTION_ADJUSTED="CORPORATE_ACTION_ADJUSTED"; TOTAL_RETURN_ADJUSTED="TOTAL_RETURN_ADJUSTED"; UNKNOWN="UNKNOWN"


@dataclass(frozen=True, slots=True)
class HistoricalSecurityIdentity:
    identity_id: str
    canonical_instrument_id: str
    isin: str | None
    exchange: str
    symbol: str
    series: str | None
    listed_from: datetime | None
    listed_until: datetime | None
    tradable_from: datetime | None
    tradable_until: datetime | None
    symbol_effective_from: datetime
    symbol_effective_to: datetime | None
    status: HistoricalSecurityStatus
    source: str
    as_of: datetime
    version: str
    source_reference: str | None = None
    warnings: tuple[str, ...] = ()

    def eligible_as_of(self, at: datetime) -> bool:
        return self.as_of <= at and self.symbol_effective_from <= at and (self.symbol_effective_to is None or at <= self.symbol_effective_to) and (self.listed_from is None or self.listed_from <= at) and (self.listed_until is None or at <= self.listed_until)


@dataclass(frozen=True, slots=True)
class HistoricalCorporateAction:
    action_id: str
    canonical_instrument_id: str
    kind: CorporateActionKind
    announcement_date: datetime | None
    record_date: datetime | None
    ex_date: datetime | None
    effective_date: datetime
    ratio_numerator: Decimal | None
    ratio_denominator: Decimal | None
    details: str | None
    source: str
    revision: str
    as_of: datetime
    source_reference: str | None = None
    warnings: tuple[str, ...] = ()

    def eligible_as_of(self, at: datetime) -> bool:
        return self.as_of <= at and self.effective_date <= at and (self.announcement_date is None or self.announcement_date <= at)

    @property
    def price_transforming(self) -> bool:
        return self.kind in {CorporateActionKind.SPLIT, CorporateActionKind.BONUS, CorporateActionKind.RIGHTS, CorporateActionKind.MERGER, CorporateActionKind.DEMERGER, CorporateActionKind.SYMBOL_CHANGE}


@dataclass(frozen=True, slots=True)
class HistoricalUniverseResult:
    universe_id: str
    as_of: datetime
    instrument_ids: tuple[str, ...]
    status: HistoricalIntegrityStatus
    membership_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class HistoricalPriceIntegrity:
    assessment_id: str
    instrument_id: str
    as_of: datetime
    basis: PriceAdjustmentBasis
    status: HistoricalIntegrityStatus
    bar_ids: tuple[str, ...]
    action_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def technical_eligible(self) -> bool:
        return self.status is HistoricalIntegrityStatus.VALID


@dataclass(frozen=True, slots=True)
class HistoricalBacktestIntegrityAssessment:
    assessment_id: str
    dataset_or_run_id: str
    as_of: datetime
    status: HistoricalIntegrityStatus
    universe_reference: str
    price_integrity_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()


class HistoricalSecurityMasterStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save_identity(self, value: HistoricalSecurityIdentity) -> None: self._save(CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY, "historical-security:" + value.identity_id, value, value.as_of)
    def save_membership(self, value: UniverseMembership, *, as_of: datetime) -> None: self._save(CoreApiSnapshotFamily.HISTORICAL_UNIVERSE_MEMBERSHIP, "historical-membership:" + value.membership_id, value, as_of)
    def save_action(self, value: HistoricalCorporateAction) -> None: self._save(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION, "historical-action:" + value.action_id, value, value.as_of)
    def save_integrity(self, value: HistoricalPriceIntegrity) -> None: self._save(CoreApiSnapshotFamily.HISTORICAL_PRICE_INTEGRITY, "historical-integrity:" + value.assessment_id, value, value.as_of)
    def identities_as_of(self, at: datetime) -> tuple[HistoricalSecurityIdentity, ...]:
        return tuple(sorted((item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY) if isinstance(item.payload, HistoricalSecurityIdentity) and item.payload.eligible_as_of(at)), key=lambda item: (item.canonical_instrument_id, item.symbol_effective_from, item.identity_id)))
    def actions_as_of(self, instrument_id: str, at: datetime) -> tuple[HistoricalCorporateAction, ...]:
        return tuple(sorted((item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION) if isinstance(item.payload, HistoricalCorporateAction) and item.payload.canonical_instrument_id == instrument_id and item.payload.eligible_as_of(at)), key=lambda item: (item.effective_date, item.action_id)))
    def integrities_as_of(self, instrument_id: str, at: datetime) -> tuple[HistoricalPriceIntegrity, ...]:
        """Read immutable integrity assessments known at an explicit as-of boundary."""
        return tuple(sorted(
            (item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_PRICE_INTEGRITY)
             if isinstance(item.payload, HistoricalPriceIntegrity)
             and item.payload.instrument_id == instrument_id and item.payload.as_of <= at),
            key=lambda item: (item.as_of, item.assessment_id),
        ))
    def memberships(self, universe_id: str) -> tuple[UniverseMembership, ...]:
        return tuple(item.payload for item in self._all(CoreApiSnapshotFamily.HISTORICAL_UNIVERSE_MEMBERSHIP) if isinstance(item.payload, UniverseMembership) and item.payload.universe_id == universe_id)
    def _save(self, family, snapshot_id, value, created_at) -> None: self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, family, "v1", "historical-security-master-v1", sha256(repr(value).encode()).hexdigest(), created_at, value))
    def _all(self, family):
        values = []; offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset); values.extend(page)
            if len(page) < 100: return tuple(values)
            offset += len(page)


class HistoricalUniverseService:
    def get_universe(self, *, universe_id: str, as_of: datetime, memberships: tuple[UniverseMembership, ...], source_complete: bool) -> HistoricalUniverseResult:
        eligible = tuple(item for item in memberships if item.universe_id == universe_id and item.known_at <= as_of and item.effective_from <= as_of and (item.effective_to is None or as_of <= item.effective_to))
        status = HistoricalIntegrityStatus.VALID if source_complete else HistoricalIntegrityStatus.PARTIAL if memberships else HistoricalIntegrityStatus.UNAVAILABLE
        warnings = () if source_complete else ("HISTORICAL_MEMBERSHIP_SOURCE_PARTIAL",) if memberships else ("HISTORICAL_MEMBERSHIP_SOURCE_REQUIRED",)
        return HistoricalUniverseResult(universe_id, as_of, tuple(sorted(item.instrument_id for item in eligible)), status, tuple(sorted(item.membership_id for item in eligible)), warnings)


class HistoricalPriceIntegrityService:
    """Fail closed rather than silently mixing raw and adjusted prices."""
    def assess(self, *, instrument_id: str, bars: tuple[CanonicalOHLCVBar, ...], actions: tuple[HistoricalCorporateAction, ...], as_of: datetime, basis: PriceAdjustmentBasis) -> HistoricalPriceIntegrity:
        actions = tuple(item for item in actions if item.eligible_as_of(as_of))
        if not bars:
            return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.UNAVAILABLE, (), actions, ("NO_HISTORICAL_BARS",))
        states = {item.adjustment_status for item in bars}
        if len(states) != 1 or AdjustmentStatus.UNKNOWN in states:
            return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.INVALID, bars, actions, ("ADJUSTMENT_MISMATCH",))
        if basis is PriceAdjustmentBasis.UNKNOWN:
            return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.PARTIAL, bars, actions, ("PRICE_ADJUSTMENT_BASIS_UNKNOWN",))
        spans_transform = any(item.price_transforming and bars[0].end_time <= item.effective_date <= bars[-1].end_time for item in actions)
        if basis is PriceAdjustmentBasis.RAW and spans_transform:
            return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.PARTIAL, bars, actions, ("RAW_SERIES_SPANS_PRICE_TRANSFORMING_ACTION", "TECHNICAL_INPUT_REQUIRES_COHERENT_ADJUSTED_BASIS"))
        if basis is not PriceAdjustmentBasis.RAW and next(iter(states)) is AdjustmentStatus.RAW:
            return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.INVALID, bars, actions, ("DECLARED_ADJUSTED_BASIS_CONFLICTS_WITH_RAW_BARS",))
        return self._result(instrument_id, as_of, basis, HistoricalIntegrityStatus.VALID, bars, actions, ())
    @staticmethod
    def _result(instrument_id, as_of, basis, status, bars, actions, warnings):
        seed = f"{instrument_id}|{as_of.isoformat()}|{basis.value}|{status.value}|{tuple(item.bar_id for item in bars)}|{tuple(item.action_id for item in actions)}"
        return HistoricalPriceIntegrity("price-integrity:" + sha256(seed.encode()).hexdigest()[:20], instrument_id, as_of, basis, status, tuple(item.bar_id for item in bars), tuple(item.action_id for item in actions), warnings)


class HistoricalBacktestIntegrityGate:
    """A precondition contract for callers; it does not start or alter a backtest."""
    def assess(self, *, dataset_or_run_id: str, universe: HistoricalUniverseResult, prices: tuple[HistoricalPriceIntegrity, ...]) -> HistoricalBacktestIntegrityAssessment:
        states = (universe.status, *(item.status for item in prices))
        status = HistoricalIntegrityStatus.INVALID if HistoricalIntegrityStatus.INVALID in states else HistoricalIntegrityStatus.UNAVAILABLE if HistoricalIntegrityStatus.UNAVAILABLE in states else HistoricalIntegrityStatus.PARTIAL if HistoricalIntegrityStatus.PARTIAL in states else HistoricalIntegrityStatus.VALID
        warnings = tuple(sorted(set((*universe.warnings, *(warning for item in prices for warning in item.warnings)))) )
        seed = f"{dataset_or_run_id}|{universe.universe_id}|{universe.as_of.isoformat()}|{status.value}|{tuple(item.assessment_id for item in prices)}"
        return HistoricalBacktestIntegrityAssessment("backtest-integrity:" + sha256(seed.encode()).hexdigest()[:20], dataset_or_run_id, universe.as_of, status, universe.universe_id, tuple(item.assessment_id for item in prices), warnings)


class HistoricalSecurityMasterCsvImporter:
    """Local-file source boundary; it does not create historical facts by inference."""
    REQUIRED = {"SYMBOL", "EFFECTIVE_FROM", "STATUS", "SOURCE"}
    def __init__(self, store: HistoricalSecurityMasterStore) -> None: self._store = store
    def import_identities(self, path: str | Path, *, as_of: datetime, dry_run: bool = False) -> int:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle: rows = tuple({(key or "").strip().upper(): (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle))
        if not rows or not self.REQUIRED.issubset(rows[0]): raise ValueError("Historical security CSV requires SYMBOL,EFFECTIVE_FROM,STATUS,SOURCE and canonical identity/ISIN fields.")
        for index, row in enumerate(rows):
            effective = datetime.fromisoformat(row["EFFECTIVE_FROM"])
            if effective.tzinfo is None: raise ValueError("EFFECTIVE_FROM must be timezone-aware.")
            value = HistoricalSecurityIdentity("security-" + sha256(f"{index}|{row}".encode()).hexdigest()[:20], row.get("CANONICAL_INSTRUMENT_ID") or ("NSE:" + (row.get("ISIN") or row["SYMBOL"])), row.get("ISIN") or None, row.get("EXCHANGE") or "NSE", row["SYMBOL"], row.get("SERIES") or None, _dt(row.get("LISTED_FROM")), _dt(row.get("LISTED_UNTIL")), _dt(row.get("TRADABLE_FROM")), _dt(row.get("TRADABLE_UNTIL")), effective, _dt(row.get("EFFECTIVE_TO")), HistoricalSecurityStatus(row["STATUS"]), row["SOURCE"], as_of, row.get("VERSION") or "historical-security-v1", row.get("SOURCE_REFERENCE") or None)
            if not dry_run: self._store.save_identity(value)
        return len(rows)


def _dt(value: str | None) -> datetime | None: return datetime.fromisoformat(value) if value else None


class HistoricalCorporateActionCsvImporter:
    """Separate approved-file boundary; no event is inferred from a price move."""
    REQUIRED = {"CANONICAL_INSTRUMENT_ID", "ACTION_TYPE", "EFFECTIVE_DATE", "SOURCE"}
    def __init__(self, store: HistoricalSecurityMasterStore) -> None: self._store = store
    def import_actions(self, path: str | Path, *, as_of: datetime, dry_run: bool = False) -> int:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle: rows = tuple({(key or "").strip().upper(): (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle))
        if not rows or not self.REQUIRED.issubset(rows[0]): raise ValueError("Corporate-action CSV requires CANONICAL_INSTRUMENT_ID,ACTION_TYPE,EFFECTIVE_DATE,SOURCE.")
        for index, row in enumerate(rows):
            effective = _dt(row["EFFECTIVE_DATE"])
            if effective is None or effective.tzinfo is None: raise ValueError("Corporate action EFFECTIVE_DATE must be timezone-aware.")
            value = HistoricalCorporateAction(
                "action-" + sha256(f"{index}|{row}".encode()).hexdigest()[:20], row["CANONICAL_INSTRUMENT_ID"], CorporateActionKind(row["ACTION_TYPE"]),
                _dt(row.get("ANNOUNCEMENT_DATE")), _dt(row.get("RECORD_DATE")), _dt(row.get("EX_DATE")), effective,
                Decimal(row["RATIO_NUMERATOR"]) if row.get("RATIO_NUMERATOR") else None, Decimal(row["RATIO_DENOMINATOR"]) if row.get("RATIO_DENOMINATOR") else None,
                row.get("DETAILS") or None, row["SOURCE"], row.get("REVISION") or "v1", as_of, row.get("SOURCE_REFERENCE") or None,
            )
            if not dry_run: self._store.save_action(value)
        return len(rows)


@dataclass(frozen=True, slots=True)
class NseCorporateActionImportReport:
    """Read-only result for the bounded official NSE corporate-action boundary."""

    source_filename: str
    source_checksum: str
    total_rows: int
    supported_rows: int
    matched_rows: int
    ambiguous_rows: int
    unmatched_rows: int
    skipped_non_equity_rows: int
    actions: tuple[HistoricalCorporateAction, ...]

    @property
    def action_type_counts(self) -> tuple[tuple[CorporateActionKind, int], ...]:
        return tuple(
            (kind, sum(item.kind is kind for item in self.actions))
            for kind in CorporateActionKind
            if any(item.kind is kind for item in self.actions)
        )


class NseOfficialCorporateActionCsvImporter:
    """Conservative adapter for NSE's public corporate-actions CSV export.

    The official export does not carry ISINs or canonical IDs.  This adapter
    therefore accepts only ``SERIES=EQ`` rows and maps an action only when its
    NSE symbol identifies exactly one supplied canonical instrument.  It keeps
    the canonical importer/model contract as the persistence boundary.
    """

    REQUIRED = {
        "SYMBOL", "COMPANY NAME", "SERIES", "PURPOSE", "FACE VALUE", "EX-DATE",
        "RECORD DATE", "BOOK CLOSURE START DATE", "BOOK CLOSURE END DATE",
    }
    SOURCE = "NSE_OFFICIAL_CORPORATE_ACTION_EXPORT"
    _RATIO = re.compile(r"\b(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)\b")
    _SPLIT_FACE_VALUE = re.compile(
        r"\bFROM\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\s+TO\s+RS\.?\s*(\d+(?:\.\d+)?)\s*/?-?\s*PER\s+SHARE\b",
        re.IGNORECASE,
    )

    def __init__(self, store: HistoricalSecurityMasterStore) -> None:
        self._store = store

    def preview(
        self,
        path: str | Path,
        *,
        instruments: tuple[object, ...],
        imported_at: datetime,
    ) -> NseCorporateActionImportReport:
        """Parse and map an official export without writing any record."""
        if imported_at.tzinfo is None:
            raise ValueError("imported_at must be timezone-aware.")
        source = Path(path)
        raw = source.read_bytes()
        checksum = sha256(raw).hexdigest()
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            headers = {(value or "").strip().upper() for value in (reader.fieldnames or ())}
            if not self.REQUIRED.issubset(headers):
                missing = ",".join(sorted(self.REQUIRED - headers))
                raise ValueError(f"NSE corporate-action CSV missing required official columns: {missing}.")
            rows = tuple(
                ({(key or "").strip().upper(): (value or "").strip() for key, value in row.items()}, line)
                for line, row in enumerate(reader, start=2)
            )
        by_symbol: dict[str, list[object]] = {}
        for instrument in instruments:
            symbol = str(getattr(instrument, "symbol")).strip().upper()
            by_symbol.setdefault(symbol, []).append(instrument)
        actions: list[HistoricalCorporateAction] = []
        supported = matched = ambiguous = unmatched = non_equity = 0
        for row, line in rows:
            kind = self._kind(row["PURPOSE"])
            if kind is None:
                continue
            supported += 1
            if row["SERIES"].upper() != "EQ":
                non_equity += 1
                continue
            candidates = by_symbol.get(row["SYMBOL"].upper(), ())
            selected, mapping_method = self._canonical_candidate(candidates)
            if selected is None:
                if candidates:
                    ambiguous += 1
                else:
                    unmatched += 1
                continue
            matched += 1
            actions.append(self._action(
                row=row, line=line, kind=kind, instrument_id=str(getattr(selected, "instrument_id")), mapping_method=mapping_method,
                source_filename=source.name, source_checksum=checksum, imported_at=imported_at,
            ))
        return NseCorporateActionImportReport(
            source.name, checksum, len(rows), supported, matched, ambiguous, unmatched, non_equity, tuple(actions),
        )

    def import_frozen_cohort(
        self,
        path: str | Path,
        *,
        instruments: tuple[object, ...],
        imported_at: datetime,
        dry_run: bool = False,
    ) -> NseCorporateActionImportReport:
        """Persist only the reviewed, exactly matched supplied cohort actions."""
        report = self.preview(path, instruments=instruments, imported_at=imported_at)
        if not dry_run:
            for action in report.actions:
                self._store.save_action(action)
        return report

    @staticmethod
    def _canonical_candidate(candidates: tuple[object, ...]) -> tuple[object | None, str | None]:
        """Select only an exact symbol match with a unique canonical ISIN.

        The imported universe can retain a legacy symbol-only identity next to
        its authoritative ISIN-based identity.  That storage duplication is
        not an ambiguous official corporate-action mapping when exactly one
        same-symbol candidate carries the canonical NSE ISIN.  Multiple ISIN
        candidates remain fail-closed.
        """
        if len(candidates) == 1:
            return candidates[0], "EXACT_SYMBOL_EQ"
        canonical = tuple(item for item in candidates if str(getattr(item, "isin", "") or "").strip())
        return (canonical[0], "EXACT_SYMBOL_EQ_CANONICAL_ISIN") if len(canonical) == 1 else (None, None)

    @classmethod
    def _kind(cls, purpose: str) -> CorporateActionKind | None:
        value = purpose.strip().upper()
        if "DEMERGER" in value:
            return CorporateActionKind.DEMERGER
        if "MERGER" in value or "AMALGAMATION" in value:
            return CorporateActionKind.MERGER
        if "SYMBOL CHANGE" in value or "CHANGE IN SYMBOL" in value:
            return CorporateActionKind.SYMBOL_CHANGE
        if "SPLIT" in value or "SUB-DIVISION" in value:
            return CorporateActionKind.SPLIT
        if "BONUS" in value:
            return CorporateActionKind.BONUS
        if "RIGHTS" in value:
            return CorporateActionKind.RIGHTS
        return None

    @classmethod
    def _ratio(cls, purpose: str, kind: CorporateActionKind) -> tuple[Decimal | None, Decimal | None, tuple[str, ...]]:
        match = cls._RATIO.search(purpose)
        if match is not None:
            return Decimal(match.group(1)), Decimal(match.group(2)), ()
        if kind is CorporateActionKind.SPLIT:
            face_value = cls._SPLIT_FACE_VALUE.search(purpose)
            if face_value is not None:
                # Preserve the explicit old/new face-value relation from NSE's text.
                return Decimal(face_value.group(1)), Decimal(face_value.group(2)), ()
        return None, None, ("RATIO_UNPARSEABLE",)

    @staticmethod
    def _date(value: str) -> datetime | None:
        text = value.strip()
        if not text or text == "-":
            return None
        return datetime.strptime(text, "%d-%b-%Y").replace(tzinfo=UTC)

    def _action(
        self,
        *,
        row: dict[str, str],
        line: int,
        kind: CorporateActionKind,
        instrument_id: str,
        mapping_method: str | None,
        source_filename: str,
        source_checksum: str,
        imported_at: datetime,
    ) -> HistoricalCorporateAction:
        ex_date = self._date(row["EX-DATE"])
        if ex_date is None:
            raise ValueError(f"NSE supported action at line {line} has no EX-DATE.")
        record_date = self._date(row["RECORD DATE"])
        numerator, denominator, ratio_warnings = self._ratio(row["PURPOSE"], kind)
        source_reference = (
            f"filename={source_filename};sha256={source_checksum};line={line};"
            f"mapping_method={mapping_method or 'EXACT_SYMBOL_EQ'}"
        )
        details = json.dumps({
            "original_purpose": row["PURPOSE"], "original_company_name": row["COMPANY NAME"],
            "series": row["SERIES"], "face_value": row["FACE VALUE"],
            "book_closure_start_date": row["BOOK CLOSURE START DATE"],
            "book_closure_end_date": row["BOOK CLOSURE END DATE"],
            "mapping_method": mapping_method or "EXACT_SYMBOL_EQ",
        }, sort_keys=True, separators=(",", ":"))
        seed = f"{source_checksum}|{line}|{instrument_id}|{kind.value}|{ex_date.isoformat()}"
        return HistoricalCorporateAction(
            "nse-action:" + sha256(seed.encode()).hexdigest()[:32], instrument_id, kind,
            None, record_date, ex_date, ex_date, numerator, denominator, details,
            self.SOURCE, "nse-corporate-action-v1", imported_at, source_reference,
            ("MAPPING_METHOD_" + (mapping_method or "EXACT_SYMBOL_EQ"), *ratio_warnings),
        )
