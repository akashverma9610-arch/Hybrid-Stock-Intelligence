"""Immutable SQLite/PostgreSQL corporate-filing stores."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.filings.models import (AttachmentParseStatus, BoardMeetingMetadata, CorporateActionDisclosure, CorporateFiling, FilingAttachment, FilingTextAvailability, FilingTimestampSourceEvidence, FilingType, FinancialResultMetadata, PrimarySourceQuality)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory


class FilingWriteOutcome(StrEnum):
    INSERTED="INSERTED"; IDENTICAL="IDENTICAL"


class CorporateFilingsStore(Protocol):
    def save(self, filing: CorporateFiling) -> FilingWriteOutcome: ...
    def get(self, filing_id: str) -> CorporateFiling | None: ...
    def list(self, *, instrument_id: str | None = None, exchange: Exchange | None = None, filing_type: FilingType | None = None, start: datetime | None = None, end: datetime | None = None, limit: int = 100, as_of: datetime | None = None) -> tuple[CorporateFiling, ...]: ...
    def revisions(self, filing_id: str) -> tuple[CorporateFiling, ...]: ...


class SQLiteCorporateFilingsStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS corporate_filings (
                filing_id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL, exchange TEXT NOT NULL,
                filing_type TEXT NOT NULL, announced_at TEXT NOT NULL, received_at TEXT NOT NULL,
                source TEXT NOT NULL, source_reference TEXT, revision_of_filing_id TEXT,
                payload_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_filings_instrument_announced ON corporate_filings(instrument_id, announced_at DESC);
            CREATE INDEX IF NOT EXISTS ix_filings_type_announced ON corporate_filings(filing_type, announced_at DESC);
            CREATE INDEX IF NOT EXISTS ix_filings_exchange_announced ON corporate_filings(exchange, announced_at DESC);
            CREATE INDEX IF NOT EXISTS ix_filings_source_reference ON corporate_filings(source, source_reference);
            CREATE INDEX IF NOT EXISTS ix_filings_revision ON corporate_filings(revision_of_filing_id);
        """)

    def save(self, filing: CorporateFiling) -> FilingWriteOutcome:
        existing = self.get(filing.filing_id)
        if existing is not None:
            if existing == filing: return FilingWriteOutcome.IDENTICAL
            raise ValueError("Corporate filing ID is immutable and cannot be overwritten.")
        self._connection.execute("INSERT INTO corporate_filings VALUES (?,?,?,?,?,?,?,?,?,?)", (filing.filing_id, filing.instrument.instrument_id, filing.exchange.value, filing.filing_type.value, _time(filing.announced_at), _time(filing.received_at), filing.source, filing.source_reference, filing.revision_of_filing_id, _dump(filing)))
        self._connection.commit()
        return FilingWriteOutcome.INSERTED

    def get(self, filing_id: str) -> CorporateFiling | None:
        row = self._connection.execute("SELECT payload_json FROM corporate_filings WHERE filing_id=?", (filing_id,)).fetchone()
        return _filing(json.loads(row["payload_json"])) if row else None

    def list(self, *, instrument_id: str | None = None, exchange: Exchange | None = None, filing_type: FilingType | None = None, start: datetime | None = None, end: datetime | None = None, limit: int = 100, as_of: datetime | None = None) -> tuple[CorporateFiling, ...]:
        if not 1 <= limit <= 500: raise ValueError("Filing limit must be between 1 and 500.")
        clauses: list[str] = []; values: list[str] = []
        for column, value in (("instrument_id", instrument_id), ("exchange", exchange.value if exchange else None), ("filing_type", filing_type.value if filing_type else None)):
            if value is not None: clauses.append(f"{column}=?"); values.append(value)
        if start: clauses.append("announced_at>=?"); values.append(_time(start))
        if end: clauses.append("announced_at<=?"); values.append(_time(end))
        if as_of:
            clauses.extend(("announced_at<=?", "received_at<=?")); values.extend((_time(as_of), _time(as_of)))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._connection.execute("SELECT payload_json FROM corporate_filings" + where + " ORDER BY announced_at DESC, filing_id DESC LIMIT ?", (*values, limit * 2)).fetchall()
        return _effective_filings(tuple(_filing(json.loads(row["payload_json"])) for row in rows), limit)

    def revisions(self, filing_id: str) -> tuple[CorporateFiling, ...]:
        rows = self._connection.execute("SELECT payload_json FROM corporate_filings WHERE revision_of_filing_id=? ORDER BY announced_at, filing_id", (filing_id,)).fetchall()
        return tuple(_filing(json.loads(row["payload_json"])) for row in rows)


class PostgreSQLCorporateFilingsStore:
    """PostgreSQL adapter selected only by explicit database configuration."""
    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL:
            raise ValueError("PostgreSQL corporate filings require DATABASE_BACKEND=postgresql.")
        self._connections = connections

    def save(self, filing: CorporateFiling) -> FilingWriteOutcome:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM corporate_filings WHERE filing_id=%s", (filing.filing_id,)); row = cursor.fetchone()
                if row:
                    if _filing(row[0] if isinstance(row[0], dict) else json.loads(row[0])) == filing: return FilingWriteOutcome.IDENTICAL
                    raise ValueError("Corporate filing ID is immutable and cannot be overwritten.")
                cursor.execute("INSERT INTO corporate_filings(filing_id,instrument_id,exchange,filing_type,announced_at,received_at,source,source_reference,revision_of_filing_id,payload_json) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)", (filing.filing_id, filing.instrument.instrument_id, filing.exchange.value, filing.filing_type.value, filing.announced_at, filing.received_at, filing.source, filing.source_reference, filing.revision_of_filing_id, _dump(filing)))
        return FilingWriteOutcome.INSERTED

    def get(self, filing_id: str) -> CorporateFiling | None:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute("SELECT payload_json FROM corporate_filings WHERE filing_id=%s", (filing_id,)); row=cursor.fetchone()
        return _filing(row[0] if isinstance(row[0],dict) else json.loads(row[0])) if row else None

    def list(self, *, instrument_id: str | None = None, exchange: Exchange | None = None, filing_type: FilingType | None = None, start: datetime | None = None, end: datetime | None = None, limit: int = 100, as_of: datetime | None = None) -> tuple[CorporateFiling, ...]:
        if not 1 <= limit <= 500: raise ValueError("Filing limit must be between 1 and 500.")
        clauses: list[str] = []; values: list[object] = []
        for column, value in (("instrument_id", instrument_id), ("exchange", exchange.value if exchange else None), ("filing_type", filing_type.value if filing_type else None)):
            if value is not None: clauses.append(f"{column}=%s"); values.append(value)
        if start: clauses.append("announced_at>=%s"); values.append(start)
        if end: clauses.append("announced_at<=%s"); values.append(end)
        if as_of: clauses.extend(("announced_at<=%s", "received_at<=%s")); values.extend((as_of, as_of))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM corporate_filings" + where + " ORDER BY announced_at DESC,filing_id DESC LIMIT %s", (*values, limit * 2)); rows=cursor.fetchall()
        return _effective_filings(tuple(_filing(row[0] if isinstance(row[0],dict) else json.loads(row[0])) for row in rows), limit)

    def revisions(self, filing_id: str) -> tuple[CorporateFiling, ...]:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute("SELECT payload_json FROM corporate_filings WHERE revision_of_filing_id=%s ORDER BY announced_at,filing_id", (filing_id,)); rows=cursor.fetchall()
        return tuple(_filing(row[0] if isinstance(row[0],dict) else json.loads(row[0])) for row in rows)


def _time(value: datetime) -> str: return value.astimezone(UTC).isoformat()
def _effective_filings(values: tuple[CorporateFiling, ...], limit: int) -> tuple[CorporateFiling, ...]:
    """Hide only the parent of an explicit append-only PIT correction.

    ``get`` and ``revisions`` remain audit views.  Ordinary filing revisions
    are deliberately untouched.
    """
    parents = {
        item.revision_of_filing_id for item in values
        if item.revision_of_filing_id and any(warning.startswith("NSE_REG31_PIT_TIMESTAMP_CORRECTED_V1:") for warning in item.warnings)
    }
    return tuple(item for item in values if item.filing_id not in parents)[:limit]
def _parse(value: str | None) -> datetime | None: return datetime.fromisoformat(value) if value else None
def _dump(value: CorporateFiling) -> str:
    return json.dumps(_encode(value), sort_keys=True, separators=(",", ":"))
def _encode(value):
    if isinstance(value, datetime): return _time(value)
    if isinstance(value, StrEnum): return value.value
    if hasattr(value, "__dataclass_fields__"): return {key:_encode(getattr(value,key)) for key in value.__dataclass_fields__}
    if isinstance(value, tuple): return [_encode(item) for item in value]
    if isinstance(value, dict): return {key:_encode(item) for key,item in value.items()}
    return str(value) if value.__class__.__name__ == "Decimal" else value
def _instrument(value: dict) -> InstrumentIdentity:
    return InstrumentIdentity(value["instrument_id"], Exchange(value["exchange"]), value["symbol"], value.get("trading_symbol"), value.get("isin"), value.get("series"), InstrumentType(value["instrument_type"]), value.get("name"), value.get("currency", "INR"))
def _provenance(value: dict) -> MarketDataProvenance:
    return MarketDataProvenance(value["provider"],value.get("provider_instrument_reference"),_parse(value.get("exchange_timestamp")),_parse(value.get("provider_timestamp")),_parse(value["received_at"]),value["normalization_version"],value["request_reference"],value.get("source_reference"),value.get("schema_version", "market-data-v1"))
def _attachment(value: dict) -> FilingAttachment: return FilingAttachment(value["attachment_id"],value["document_type"],value.get("title"),value.get("filename"),value["source_reference"],value.get("mime_type"),_parse(value.get("published_at")),value.get("checksum"),AttachmentParseStatus(value.get("parse_status", "NOT_FETCHED")),value.get("is_xbrl",False))
def _filing(value: dict) -> CorporateFiling:
    action=value.get("action"); financial=value.get("financial_result"); board=value.get("board_meeting"); timestamp=value.get("timestamp_evidence")
    return CorporateFiling(value["filing_id"],_instrument(value["instrument"]),Exchange(value["exchange"]),value["source"],PrimarySourceQuality(value["source_quality"]),FilingType(value["filing_type"]),value.get("raw_category"),value["subject"],_parse(value["announced_at"]),_parse(value["received_at"]),value.get("source_reference"),value.get("document_reference"),_provenance(value["provenance"]),_parse(value.get("effective_at")),_parse(value.get("period_end")),_parse(value.get("board_meeting_date")),FilingTextAvailability(value.get("text_availability", "NOT_AVAILABLE")),tuple(_attachment(item) for item in value.get("attachments",())),value.get("revision_of_filing_id"),CorporateActionDisclosure(FilingType(action["action_type"]),_parse(action.get("record_date")),_parse(action.get("ex_date")),_parse(action.get("effective_date")),__import__("decimal").Decimal(action["ratio"]) if action.get("ratio") is not None else None,__import__("decimal").Decimal(action["amount"]) if action.get("amount") is not None else None,action.get("terms_text")) if action else None,FinancialResultMetadata(_parse(financial["period_end"]),financial.get("result_scope"),financial.get("result_type"),financial.get("revised",False)) if financial else None,BoardMeetingMetadata(_parse(board["meeting_date"]),board.get("purpose"),board.get("related_filing_id")) if board else None,_parse(value.get("reporting_as_of")),value.get("normalization_version", "corporate-filings-v1"),tuple(value.get("warnings",())),FilingTimestampSourceEvidence(timestamp["source_family"],timestamp["source_document_identity"],timestamp["source_payload_identity"],timestamp["raw_timestamp_field_path"],timestamp["raw_timestamp_value"],timestamp["timestamp_role"]) if timestamp else None)
