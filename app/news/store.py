"""Insert-only SQLite/PostgreSQL persistence for normalized news metadata."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import fields
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory


class NewsEvidenceStore(Protocol):
    def save(self, evidence: NewsArticleEvidence) -> bool: ...
    def get(self, article_id: str) -> NewsArticleEvidence | None: ...
    def find_duplicate(self, *, provider: str, provider_article_id: str | None, url: str) -> NewsArticleEvidence | None: ...
    def list(self, *, instrument_id: str | None = None, sector: str | None = None, start: datetime | None = None, end: datetime | None = None, provider: str | None = None, as_of: datetime | None = None, limit: int = 100) -> tuple[NewsArticleEvidence, ...]: ...


class SQLiteNewsEvidenceStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript("""
        CREATE TABLE IF NOT EXISTS news_evidence (
          article_id TEXT PRIMARY KEY, source_provider TEXT NOT NULL, provider_article_id TEXT,
          url TEXT NOT NULL, published_at TEXT NOT NULL, received_at TEXT NOT NULL,
          instrument_ids_json TEXT NOT NULL, sectors_json TEXT NOT NULL, payload_json TEXT NOT NULL,
          UNIQUE(source_provider, url)
        );
        CREATE INDEX IF NOT EXISTS ix_news_evidence_published ON news_evidence(published_at DESC, article_id DESC);
        CREATE INDEX IF NOT EXISTS ix_news_evidence_provider_provider_id ON news_evidence(source_provider, provider_article_id);
        """)

    def save(self, evidence: NewsArticleEvidence) -> bool:
        existing = self.get(evidence.article_id)
        if existing is not None:
            if existing == evidence: return False
            raise ValueError("News evidence IDs are immutable and cannot be overwritten.")
        duplicate = self.find_duplicate(provider=evidence.source_provider, provider_article_id=evidence.provenance.source_reference, url=evidence.url)
        if duplicate is not None: return False
        self._connection.execute("INSERT INTO news_evidence VALUES (?,?,?,?,?,?,?,?,?)", (evidence.article_id, evidence.source_provider, evidence.provenance.source_reference, evidence.url, _time(evidence.published_at), _time(evidence.received_at), json.dumps(evidence.instrument_ids), json.dumps(evidence.sectors), _dump(evidence)))
        self._connection.commit(); return True

    def get(self, article_id: str) -> NewsArticleEvidence | None:
        row = self._connection.execute("SELECT payload_json FROM news_evidence WHERE article_id=?", (article_id,)).fetchone()
        return _evidence(json.loads(row["payload_json"])) if row else None

    def find_duplicate(self, *, provider: str, provider_article_id: str | None, url: str) -> NewsArticleEvidence | None:
        row = self._connection.execute("SELECT payload_json FROM news_evidence WHERE source_provider=? AND url=?", (provider, url)).fetchone()
        if row is None and provider_article_id:
            row = self._connection.execute("SELECT payload_json FROM news_evidence WHERE source_provider=? AND provider_article_id=?", (provider, provider_article_id)).fetchone()
        return _evidence(json.loads(row["payload_json"])) if row else None

    def list(self, *, instrument_id: str | None = None, sector: str | None = None, start: datetime | None = None, end: datetime | None = None, provider: str | None = None, as_of: datetime | None = None, limit: int = 100) -> tuple[NewsArticleEvidence, ...]:
        if not 1 <= limit <= 100: raise ValueError("News limit must be between 1 and 100.")
        clauses: list[str] = []; values: list[str] = []
        if provider: clauses.append("source_provider=?"); values.append(provider)
        if start: clauses.append("published_at>=?"); values.append(_time(start))
        if end: clauses.append("published_at<=?"); values.append(_time(end))
        if as_of: clauses.extend(("published_at<=?", "received_at<=?")); values.extend((_time(as_of), _time(as_of)))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self._connection.execute("SELECT payload_json FROM news_evidence" + where + " ORDER BY published_at DESC,article_id DESC LIMIT ?", (*values, limit)).fetchall()
        values_out = tuple(_evidence(json.loads(row["payload_json"])) for row in rows)
        return tuple(item for item in values_out if (instrument_id is None or instrument_id in item.instrument_ids) and (sector is None or sector in item.sectors))


class PostgreSQLNewsEvidenceStore:
    def __init__(self, connections: DatabaseConnectionFactory) -> None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL:
            raise ValueError("PostgreSQL news evidence requires DATABASE_BACKEND=postgresql.")
        self._connections = connections

    def save(self, evidence: NewsArticleEvidence) -> bool:
        existing = self.get(evidence.article_id)
        if existing is not None:
            if existing == evidence: return False
            raise ValueError("News evidence IDs are immutable and cannot be overwritten.")
        if self.find_duplicate(provider=evidence.source_provider, provider_article_id=evidence.provenance.source_reference, url=evidence.url): return False
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO news_evidence(article_id,source_provider,provider_article_id,url,published_at,received_at,instrument_ids_json,sectors_json,payload_json) VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)", (evidence.article_id,evidence.source_provider,evidence.provenance.source_reference,evidence.url,evidence.published_at,evidence.received_at,json.dumps(evidence.instrument_ids),json.dumps(evidence.sectors),_dump(evidence)))
        return True

    def get(self, article_id: str) -> NewsArticleEvidence | None:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute("SELECT payload_json FROM news_evidence WHERE article_id=%s", (article_id,)); row=cursor.fetchone()
        return _evidence(row[0] if isinstance(row[0],dict) else json.loads(row[0])) if row else None

    def find_duplicate(self, *, provider: str, provider_article_id: str | None, url: str) -> NewsArticleEvidence | None:
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT payload_json FROM news_evidence WHERE source_provider=%s AND url=%s",(provider,url));row=cursor.fetchone()
                if row is None and provider_article_id: cursor.execute("SELECT payload_json FROM news_evidence WHERE source_provider=%s AND provider_article_id=%s",(provider,provider_article_id));row=cursor.fetchone()
        return _evidence(row[0] if isinstance(row[0],dict) else json.loads(row[0])) if row else None

    def list(self, **kwargs) -> tuple[NewsArticleEvidence, ...]:
        # PostgreSQL selection remains intentionally equivalent to SQLite's factual filters.
        instrument_id,sector,start,end,provider,as_of,limit=(kwargs.get(name) for name in ("instrument_id","sector","start","end","provider","as_of","limit"))
        if not 1 <= (limit or 100) <= 100: raise ValueError("News limit must be between 1 and 100.")
        clauses=[]; values=[]
        if provider: clauses.append("source_provider=%s");values.append(provider)
        if start: clauses.append("published_at>=%s");values.append(start)
        if end: clauses.append("published_at<=%s");values.append(end)
        if as_of: clauses.extend(("published_at<=%s","received_at<=%s"));values.extend((as_of,as_of))
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        with self._connections.transaction() as connection:
            with connection.cursor() as cursor: cursor.execute("SELECT payload_json FROM news_evidence"+where+" ORDER BY published_at DESC,article_id DESC LIMIT %s",(*values,limit or 100)); rows=cursor.fetchall()
        values_out=tuple(_evidence(row[0] if isinstance(row[0],dict) else json.loads(row[0])) for row in rows)
        return tuple(item for item in values_out if (instrument_id is None or instrument_id in item.instrument_ids) and (sector is None or sector in item.sectors))


def _time(value: datetime) -> str: return value.isoformat()
def _parse(value: str | None) -> datetime | None: return datetime.fromisoformat(value) if value else None
def _encode(value):
    if isinstance(value, datetime): return _time(value)
    if isinstance(value, StrEnum): return value.value
    if hasattr(value, "__dataclass_fields__"): return {field.name:_encode(getattr(value,field.name)) for field in fields(value)}
    if isinstance(value, tuple): return [_encode(item) for item in value]
    return value
def _dump(value: NewsArticleEvidence) -> str: return json.dumps(_encode(value),sort_keys=True,separators=(",",":"))
def _provenance(value: dict) -> SourceRecordProvenance:
    return SourceRecordProvenance(value["source_id"],value["provider"],value.get("source_reference"),_parse(value.get("observed_at")),_parse(value.get("published_at")),_parse(value["received_at"]),_parse(value.get("effective_from")),_parse(value.get("effective_to")),DataFamily(value["family"]),value["schema_version"],value["normalization_version"])
def _evidence(value: dict) -> NewsArticleEvidence:
    return NewsArticleEvidence(value["article_id"],value["source_provider"],value.get("publisher"),value.get("publisher_url"),value["url"],value["title"],value.get("description"),_parse(value["published_at"]),_parse(value["received_at"]),value.get("language"),value.get("country"),tuple(value.get("instrument_ids",())),tuple(value.get("sectors",())),tuple(value.get("themes",())),NewsSourceQuality(value["source_quality"]),_provenance(value["provenance"]),NewsEventCategory(value.get("event_category","UNCLASSIFIED")),value.get("linked_filing_id"),tuple(value.get("match_warnings",())),tuple(value.get("warnings",())),value.get("normalization_version","news-evidence-v1"),value.get("company_name"))
