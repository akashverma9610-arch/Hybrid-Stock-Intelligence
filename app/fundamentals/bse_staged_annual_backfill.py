"""Local-only backfill of already staged, official BSE annual XBRLs.

The service deliberately has no transport, provider, discovery, taxonomy, or
portfolio dependency.  A caller supplies the already-approved non-financial
targets explicitly; it never infers business type from a symbol or name.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from app.fundamentals.bse_official import (
    BSEOfficialLocalXbrlIngestionService,
    BseLocalIngestionReport,
    BseResultMetadata,
    BseTimestampStatus,
)
from app.fundamentals.models import FinancialPeriodType, FinancialValueBasis, StatementScope
from app.market_data.models import InstrumentIdentity


class BseStagedAnnualBackfillDisposition(StrEnum):
    IMPORTED = "IMPORTED"
    UNCHANGED = "UNCHANGED"
    SOURCE_METADATA_INVALID = "SOURCE_METADATA_INVALID"
    SOURCE_HASH_MISMATCH = "SOURCE_HASH_MISMATCH"
    SOURCE_ALIAS_MISSING = "SOURCE_ALIAS_MISSING"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    IMPORT_REJECTED = "IMPORT_REJECTED"


@dataclass(frozen=True, slots=True)
class BseStagedAnnualBackfillTarget:
    """Explicit operator-approved non-financial target; no classification lookup."""
    instrument: InstrumentIdentity
    security_code: str

    def __post_init__(self) -> None:
        if not self.instrument.instrument_id or not self.instrument.isin or not self.security_code.isdigit():
            raise ValueError("BSE_STAGED_ANNUAL_BACKFILL_TARGET_IDENTITY_REQUIRED")


@dataclass(frozen=True, slots=True)
class BseStagedAnnualBackfillItem:
    canonical_instrument_id: str
    path: Path
    period_end: datetime | None
    statement_scope: StatementScope | None
    disposition: BseStagedAnnualBackfillDisposition
    facts_inserted: int
    facts_duplicate: int
    facts_conflicted: int
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class BseStagedAnnualBackfillReport:
    items: tuple[BseStagedAnnualBackfillItem, ...]

    @property
    def facts_inserted(self) -> int:
        return sum(item.facts_inserted for item in self.items)

    @property
    def facts_duplicate(self) -> int:
        return sum(item.facts_duplicate for item in self.items)

    @property
    def facts_conflicted(self) -> int:
        return sum(item.facts_conflicted for item in self.items)


class BseStagedAnnualFactBackfillService:
    """Replays immutable local XBRLs through the existing canonical importer."""

    def __init__(self, importer: BSEOfficialLocalXbrlIngestionService, source_root: str | Path) -> None:
        self._importer = importer
        self._root = Path(source_root)

    def backfill(self, targets: Iterable[BseStagedAnnualBackfillTarget]) -> BseStagedAnnualBackfillReport:
        requested = tuple(sorted(tuple(targets), key=lambda value: value.instrument.instrument_id))
        if not requested or len({value.instrument.instrument_id for value in requested}) != len(requested):
            raise ValueError("BSE_STAGED_ANNUAL_BACKFILL_TARGETS_INVALID")
        by_instrument = {value.instrument.instrument_id: value for value in requested}
        items: list[BseStagedAnnualBackfillItem] = []
        matched: set[str] = set()
        for alias_path in sorted(self._root.glob("*.aliases.json")):
            try:
                payload = _read_json(alias_path)
            except (OSError, ValueError, json.JSONDecodeError):
                # A malformed unrelated sidecar must not prevent an explicitly
                # scoped target from receiving its own deterministic receipt.
                continue
            instrument_id = payload.get("canonical_instrument_id")
            target = by_instrument.get(instrument_id)
            if target is None:
                continue
            matched.add(instrument_id)
            items.append(self._backfill_one(target, alias_path, payload))
        for target in requested:
            if target.instrument.instrument_id not in matched:
                items.append(_item(
                    target, self._root, None, None,
                    BseStagedAnnualBackfillDisposition.SOURCE_ALIAS_MISSING,
                    "STAGED_ALIAS_FOR_TARGET_MISSING",
                ))
        return BseStagedAnnualBackfillReport(tuple(sorted(items, key=lambda value: (value.canonical_instrument_id, str(value.path)))))

    def _backfill_one(self, target: BseStagedAnnualBackfillTarget, alias_path: Path, aliases: dict) -> BseStagedAnnualBackfillItem:
        xml_path = alias_path.with_name(alias_path.name.removesuffix(".aliases.json") + ".xml")
        try:
            if aliases.get("canonical_instrument_id") != target.instrument.instrument_id or aliases.get("isin", "").upper() != target.instrument.isin.upper() or aliases.get("security_code") != target.security_code:
                return _item(target, xml_path, None, None, BseStagedAnnualBackfillDisposition.IDENTITY_MISMATCH, "STAGED_ALIAS_IDENTITY_MISMATCH")
            if not xml_path.is_file():
                return _item(target, xml_path, None, None, BseStagedAnnualBackfillDisposition.SOURCE_METADATA_INVALID, "STAGED_XML_MISSING")
            if sha256(xml_path.read_bytes()).hexdigest() != aliases.get("content_sha256"):
                return _item(target, xml_path, None, None, BseStagedAnnualBackfillDisposition.SOURCE_HASH_MISMATCH, "STAGED_XML_HASH_MISMATCH")
            metadata = _annual_metadata(aliases)
            if metadata is None:
                return _item(target, xml_path, None, None, BseStagedAnnualBackfillDisposition.SOURCE_ALIAS_MISSING, "ANNUAL_ALIAS_REQUIRED")
            report = self._importer.ingest_official_staged(target.instrument, target.security_code, xml_path, metadata=metadata)
            disposition = BseStagedAnnualBackfillDisposition.IMPORTED if report.facts_inserted else BseStagedAnnualBackfillDisposition.UNCHANGED
            return _from_report(target, xml_path, metadata, disposition, report)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return _item(target, xml_path, None, None, BseStagedAnnualBackfillDisposition.IMPORT_REJECTED, type(error).__name__)


def _annual_metadata(payload: dict) -> BseResultMetadata | None:
    values = [value for value in payload.get("aliases", ()) if value.get("period_type") == FinancialPeriodType.ANNUAL.value and value.get("value_basis") == FinancialValueBasis.FULL_YEAR.value]
    if len(values) != 1:
        return None
    value = values[0]
    try:
        return BseResultMetadata(
            payload["security_code"], value["financial_year"], value["quarter_label"], value["filing_type"], value["status"],
            datetime.fromisoformat(value["filing_at"]), datetime.fromisoformat(value["revised_at"]) if value.get("revised_at") else None,
            value.get("revision_reason"), StatementScope(value["statement_scope"]), datetime.fromisoformat(value["period_end"]),
            FinancialPeriodType(value["period_type"]), FinancialValueBasis(value["value_basis"]), payload["document_identifier"],
            value["source_page"], BseTimestampStatus(value["timestamp_status"]),
            value.get("raw_filing_timestamp"), value.get("raw_filing_timestamp_field_path"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("STAGED_ALIAS_JSON_OBJECT_REQUIRED")
    return value


def _item(target, path, period_end, scope, disposition, reason):
    return BseStagedAnnualBackfillItem(target.instrument.instrument_id, path, period_end, scope, disposition, 0, 0, 0, reason)


def _from_report(target, path, metadata, disposition, report: BseLocalIngestionReport):
    return BseStagedAnnualBackfillItem(target.instrument.instrument_id, path, metadata.period_end, metadata.scope, disposition, report.facts_inserted, report.facts_duplicate, report.facts_conflicted)


__all__ = (
    "BseStagedAnnualBackfillDisposition", "BseStagedAnnualBackfillItem", "BseStagedAnnualBackfillReport",
    "BseStagedAnnualBackfillTarget", "BseStagedAnnualFactBackfillService",
)
