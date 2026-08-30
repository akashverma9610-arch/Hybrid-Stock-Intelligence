"""Official NSE daily delivery evidence, separate from OHLCV observations.

Only explicitly supplied/downloaded ``sec_bhavdata_full`` reports are parsed.
This module never constructs an archive URL, estimates delivery, or fetches a
provider from a scanner.
"""
from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from io import StringIO
from pathlib import Path
from typing import Iterable

from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


NSE_OFFICIAL = "NSE_OFFICIAL"
_FIELDS = {
    "symbol": ("SYMBOL",), "series": ("SERIES",), "trade_date": ("DATE1", "DATE", "TRADE_DATE"),
    "traded": ("TOTTRDQTY", "TTL_TRD_QNTY", "TOTAL TRADED QUANTITY"), "deliverable": ("DELIV_QTY", "DELIVERABLE QUANTITY"),
    "delivery_pct": ("DELIV_PER", "% DELIVERABLE TO TRADED QUANTITY"), "turnover": ("TOTTRDVAL", "TURNOVER", "TURNOVER_LACS"),
    "trades": ("TOTALTRADES", "NO OF TRADES", "NO. OF TRADES", "NO_OF_TRADES"), "vwap": ("VWAP",),
}


@dataclass(frozen=True, slots=True)
class NseDeliveryReportArtifact:
    report_id: str
    trade_date: datetime
    official_filename: str
    source_url: str
    source_page: str
    fetched_at_utc: datetime
    sha256: str
    content_type: str
    size: int
    authority: str = NSE_OFFICIAL


@dataclass(frozen=True, slots=True)
class NseDeliveryObservation:
    observation_id: str
    report_id: str
    instrument_id: str
    symbol: str
    isin: str | None
    trade_date: datetime
    total_traded_quantity: int
    deliverable_quantity: int
    delivery_percentage: Decimal
    turnover: Decimal | None
    trade_count: int | None
    vwap: Decimal | None
    available_at: datetime
    provider: str = NSE_OFFICIAL
    authority: str = "OFFICIAL_EXCHANGE"
    frequency: str = "DAILY_EOD"


@dataclass(frozen=True, slots=True)
class NseDeliveryImportReport:
    artifact: NseDeliveryReportArtifact
    rows_seen: int
    eq_rows_seen: int
    accepted: int
    unresolved: int
    rejected: int
    duplicates: int
    header_map: tuple[tuple[str, str], ...]


class NseDeliveryStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def save_report(self, value: NseDeliveryReportArtifact) -> None: self._save(CoreApiSnapshotFamily.NSE_DELIVERY_REPORT, value.report_id, value, value.fetched_at_utc)
    def save(self, value: NseDeliveryObservation) -> None: self._save(CoreApiSnapshotFamily.NSE_DELIVERY_OBSERVATION, value.observation_id, value, value.available_at)
    def latest(self, instrument_id: str, *, as_of: datetime) -> NseDeliveryObservation | None:
        values = [item.payload for item in self._all(CoreApiSnapshotFamily.NSE_DELIVERY_OBSERVATION) if isinstance(item.payload, NseDeliveryObservation) and item.payload.instrument_id == instrument_id and item.payload.available_at <= as_of]
        return max(values, key=lambda item: (item.trade_date, item.observation_id)) if values else None
    def latest_official_delivery(self, instrument_id: str, *, as_of: datetime) -> NseDeliveryObservation | None:
        """Exact-instrument, PIT-safe lookup with no alternative-provider fallback."""
        value = self.latest(instrument_id, as_of=as_of)
        return value if value is not None and value.provider == NSE_OFFICIAL and value.authority == "OFFICIAL_EXCHANGE" else None
    def _all(self, family):
        result=[]; offset=0
        while True:
            page=self._repository.list_snapshots(family, limit=100, offset=offset); result.extend(page)
            if len(page)<100:return tuple(result)
            offset+=len(page)
    def _save(self, family, identifier, value, at):
        if self._repository.get_snapshot(identifier) is not None: return
        fingerprint=sha256(repr(value).encode()).hexdigest()
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", type(value).__name__, fingerprint, at, value))


class NseDeliveryReportImporter:
    """Parse one locally retained official report once for many exact targets."""
    def __init__(self, store: NseDeliveryStore) -> None: self._store=store
    def import_csv(self, path: Path, *, source_url: str, source_page: str, fetched_at: datetime, targets: dict[str, tuple[str, str | None]]) -> NseDeliveryImportReport:
        trade_date=_date_from_name(path.name)
        raw=path.read_bytes(); text=raw.decode("utf-8-sig", errors="strict")
        reader=csv.DictReader(StringIO(text)); headers=tuple(reader.fieldnames or ())
        rows=tuple(reader)
        if not rows: raise ValueError("NSE_DELIVERY_REPORT_EMPTY")
        fields=_resolve_headers(headers)
        required=("symbol","series","trade_date","traded","deliverable","delivery_pct")
        if any(key not in fields for key in required): raise ValueError("NSE_DELIVERY_SCHEMA_REQUIRED_FIELDS_MISSING")
        artifact=NseDeliveryReportArtifact("nse-delivery:"+sha256(raw).hexdigest()[:24], trade_date, path.name, source_url, source_page, fetched_at.astimezone(UTC), sha256(raw).hexdigest(), "text/csv", len(raw))
        accepted=unresolved=rejected=duplicates=eq=0; self._store.save_report(artifact)
        # Production-universe imports can include thousands of exact rows.
        # Read immutable prior observation IDs once instead of repeatedly
        # scanning the snapshot store for each row.  The save boundary remains
        # insert-only and the same deterministic ID still decides idempotency.
        existing_ids = {
            item.payload.observation_id
            for item in self._store._all(CoreApiSnapshotFamily.NSE_DELIVERY_OBSERVATION)
            if isinstance(item.payload, NseDeliveryObservation)
        }
        for row in rows:
            if row.get(fields["series"], "").strip().upper() != "EQ": continue
            eq+=1; symbol=row[fields["symbol"]].strip().upper(); target=targets.get(symbol)
            if target is None: unresolved+=1; continue
            try:
                traded=_integer(row[fields["traded"]]); deliverable=_integer(row[fields["deliverable"]]); percent=_decimal(row[fields["delivery_pct"]])
                if traded < 0 or deliverable < 0 or deliverable > traded or not Decimal("0") <= percent <= Decimal("100"): raise ValueError
            except (ValueError, InvalidOperation): rejected+=1; continue
            value=NseDeliveryObservation("nse-delivery-observation:"+sha256(f"{artifact.report_id}|{target[0]}".encode()).hexdigest()[:24], artifact.report_id, target[0], symbol, target[1], trade_date, traded, deliverable, percent, _optional_decimal(row, fields.get("turnover")), _optional_integer(row, fields.get("trades")), _optional_decimal(row, fields.get("vwap")), fetched_at.astimezone(UTC))
            existed = value.observation_id in existing_ids
            self._store.save(value)
            if existed: duplicates+=1
            else: accepted+=1
        return NseDeliveryImportReport(artifact, len(rows), eq, accepted, unresolved, rejected, duplicates, tuple(sorted(fields.items())))


def _resolve_headers(headers: Iterable[str]) -> dict[str, str]:
    canonical={header.strip().upper():header for header in headers}; result={}
    for field, aliases in _FIELDS.items():
        for alias in aliases:
            if alias in canonical: result[field]=canonical[alias]; break
    return result
def _integer(value: str) -> int: return int(Decimal(value.replace(",", "").strip()))
def _decimal(value: str) -> Decimal: return Decimal(value.replace(",", "").strip())
def _optional_integer(row, field): return None if not field or not row.get(field, "").strip() else _integer(row[field])
def _optional_decimal(row, field): return None if not field or not row.get(field, "").strip() else _decimal(row[field])
def _date(value: str) -> datetime: return datetime.strptime(value.strip(), "%d-%b-%Y").replace(tzinfo=UTC)
def _date_from_name(name: str) -> datetime:
    match = re.fullmatch(r"sec_bhavdata_full_(\d{8})\.csv", name, flags=re.IGNORECASE)
    if match is None:
        raise ValueError("NSE_DELIVERY_FILENAME_UNSUPPORTED")
    try:
        return datetime.strptime(match.group(1), "%d%m%Y").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("NSE_DELIVERY_FILENAME_DATE_INVALID") from error
