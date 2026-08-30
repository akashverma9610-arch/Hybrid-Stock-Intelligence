"""Dedicated immutable financial fact repositories; no generic snapshot storage."""
from __future__ import annotations

import json, sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import (FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, ProviderInstrumentMapping
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory


class FinancialFactWriteOutcome(StrEnum): INSERTED="INSERTED"; IDENTICAL="IDENTICAL"; CONFLICT="CONFLICT"
class FinancialFactStore(Protocol):
    def save(self, fact: FinancialFact) -> FinancialFactWriteOutcome: ...
    def get(self, fact_id: str) -> FinancialFact | None: ...
    def series(self, instrument_id: str, metric: FinancialMetric, *, period_type: FinancialPeriodType | None = None, scope: StatementScope | None = None, fact_kind: FundamentalFactKind | None = None, start: datetime | None = None, end: datetime | None = None, as_of: datetime | None = None, limit: int = 100) -> tuple[FinancialFact, ...]: ...
    def facts(self, instrument_id: str, **kwargs) -> tuple[FinancialFact, ...]: ...


class SQLiteFinancialFactStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection=sqlite3.connect(str(path),check_same_thread=False); self._connection.row_factory=sqlite3.Row
        self._connection.executescript("""CREATE TABLE IF NOT EXISTS financial_facts (fact_id TEXT PRIMARY KEY,instrument_id TEXT NOT NULL,metric TEXT NOT NULL,value_numeric TEXT NOT NULL,period_end TEXT NOT NULL,period_type TEXT NOT NULL,statement_scope TEXT NOT NULL,fact_kind TEXT NOT NULL,source TEXT NOT NULL,source_reference TEXT,filing_id TEXT,published_at TEXT NOT NULL,received_at TEXT NOT NULL,payload_json TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS ix_financial_facts_metric_period ON financial_facts(instrument_id,metric,period_end DESC);
        CREATE INDEX IF NOT EXISTS ix_financial_facts_period ON financial_facts(instrument_id,period_end DESC);
        CREATE INDEX IF NOT EXISTS ix_financial_facts_filing ON financial_facts(filing_id,source,source_reference);""")
    def save(self,fact:FinancialFact)->FinancialFactWriteOutcome:
        existing=self.get(fact.fact_id)
        if existing is not None: return FinancialFactWriteOutcome.IDENTICAL if existing==fact else FinancialFactWriteOutcome.CONFLICT
        # The same source identity cannot silently acquire a different reported value.
        row=self._connection.execute("SELECT payload_json FROM financial_facts WHERE instrument_id=? AND metric=? AND period_end=? AND period_type=? AND statement_scope=? AND fact_kind=? AND source=? AND COALESCE(source_reference,'')=COALESCE(?, '')",(fact.instrument.instrument_id,fact.metric.value,_time(fact.period_end),fact.period_type.value,fact.statement_scope.value,fact.fact_kind.value,fact.source,fact.source_reference)).fetchone()
        if row:
            return FinancialFactWriteOutcome.IDENTICAL if _fact(json.loads(row[0]))==fact else FinancialFactWriteOutcome.CONFLICT
        self._connection.execute("INSERT INTO financial_facts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(fact.fact_id,fact.instrument.instrument_id,fact.metric.value,str(fact.value),_time(fact.period_end),fact.period_type.value,fact.statement_scope.value,fact.fact_kind.value,fact.source,fact.source_reference,fact.filing_id,_time(fact.published_at),_time(fact.received_at),_dump(fact)));self._connection.commit();return FinancialFactWriteOutcome.INSERTED
    def get(self,fact_id:str)->FinancialFact|None:
        row=self._connection.execute("SELECT payload_json FROM financial_facts WHERE fact_id=?",(fact_id,)).fetchone();return _fact(json.loads(row[0])) if row else None
    def series(self,instrument_id:str,metric:FinancialMetric,*,period_type:FinancialPeriodType|None=None,scope:StatementScope|None=None,fact_kind:FundamentalFactKind|None=None,start:datetime|None=None,end:datetime|None=None,as_of:datetime|None=None,limit:int=100)->tuple[FinancialFact,...]:
        if not 1<=limit<=500: raise ValueError("Financial fact limit must be between 1 and 500.")
        clauses=["instrument_id=?","metric=?"]; values:list[object]=[instrument_id,metric.value]
        for field,value in (("period_type",period_type.value if period_type else None),("statement_scope",scope.value if scope else None),("fact_kind",fact_kind.value if fact_kind else None)):
            if value is not None: clauses.append(field+"=?");values.append(value)
        if start:clauses.append("period_end>=?");values.append(_time(start))
        if end:clauses.append("period_end<=?");values.append(_time(end))
        if as_of:clauses.extend(("published_at<=?","received_at<=?"));values.extend((_time(as_of),_time(as_of)))
        rows=self._connection.execute("SELECT payload_json FROM financial_facts WHERE "+" AND ".join(clauses)+" ORDER BY period_end, published_at, fact_id LIMIT ?",(*values,limit)).fetchall();return tuple(_fact(json.loads(row[0])) for row in rows)
    def facts(self,instrument_id:str,**kwargs)->tuple[FinancialFact,...]:
        return tuple(fact for metric in FinancialMetric for fact in self.series(instrument_id,metric,**kwargs))
    def latest_reported_period(self,instrument_id:str,metric:FinancialMetric,**kwargs)->FinancialFact|None:
        values=self.series(instrument_id,metric,fact_kind=FundamentalFactKind.REPORTED,**kwargs);return values[-1] if values else None
    def latest_quarters(self,instrument_id:str,metric:FinancialMetric,count:int,**kwargs)->tuple[FinancialFact,...]:
        if count<1: raise ValueError("Quarter count must be positive.")
        return self.series(instrument_id,metric,period_type=FinancialPeriodType.QUARTERLY,**kwargs)[-count:]
    def annual_series(self,instrument_id:str,metric:FinancialMetric,**kwargs)->tuple[FinancialFact,...]: return self.series(instrument_id,metric,period_type=FinancialPeriodType.ANNUAL,**kwargs)


class PostgreSQLFinancialFactStore:
    def __init__(self,connections:DatabaseConnectionFactory)->None:
        if connections.settings.backend is not DatabaseBackend.POSTGRESQL: raise ValueError("PostgreSQL financial facts require DATABASE_BACKEND=postgresql.")
        self._connections=connections
    def save(self,fact:FinancialFact)->FinancialFactWriteOutcome:
        with self._connections.transaction() as connection:
            with connection.cursor() as cur:
                cur.execute("SELECT payload_json FROM financial_facts WHERE fact_id=%s",(fact.fact_id,));row=cur.fetchone()
                if row:return FinancialFactWriteOutcome.IDENTICAL if _fact(row[0] if isinstance(row[0],dict) else json.loads(row[0]))==fact else FinancialFactWriteOutcome.CONFLICT
                cur.execute("INSERT INTO financial_facts(fact_id,instrument_id,metric,value_numeric,period_end,period_type,statement_scope,fact_kind,source,source_reference,filing_id,published_at,received_at,payload_json) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",(fact.fact_id,fact.instrument.instrument_id,fact.metric.value,fact.value,fact.period_end,fact.period_type.value,fact.statement_scope.value,fact.fact_kind.value,fact.source,fact.source_reference,fact.filing_id,fact.published_at,fact.received_at,_dump(fact)))
        return FinancialFactWriteOutcome.INSERTED
    def get(self,fact_id:str)->FinancialFact|None:
        with self._connections.transaction() as c:
            with c.cursor() as cur:cur.execute("SELECT payload_json FROM financial_facts WHERE fact_id=%s",(fact_id,));row=cur.fetchone()
        return _fact(row[0] if isinstance(row[0],dict) else json.loads(row[0])) if row else None
    def series(self,instrument_id:str,metric:FinancialMetric,**kwargs)->tuple[FinancialFact,...]:
        # Keeps the same semantic filtering as SQLite while retaining a compact PostgreSQL adapter.
        with self._connections.transaction() as c:
            with c.cursor() as cur:cur.execute("SELECT payload_json FROM financial_facts WHERE instrument_id=%s AND metric=%s ORDER BY period_end,published_at,fact_id",(instrument_id,metric.value));rows=cur.fetchall()
        values=tuple(_fact(row[0] if isinstance(row[0],dict) else json.loads(row[0])) for row in rows); return _filter(values,**kwargs)
    def facts(self,instrument_id:str,**kwargs)->tuple[FinancialFact,...]:
        return tuple(fact for metric in FinancialMetric for fact in self.series(instrument_id,metric,**kwargs))


def _filter(values:tuple[FinancialFact,...],**kwargs)->tuple[FinancialFact,...]:
    as_of=kwargs.get("as_of");period_type=kwargs.get("period_type");scope=kwargs.get("scope");fact_kind=kwargs.get("fact_kind");start=kwargs.get("start");end=kwargs.get("end");limit=kwargs.get("limit",100)
    if not 1<=limit<=500:raise ValueError("Financial fact limit must be between 1 and 500.")
    return tuple(f for f in values if (not period_type or f.period_type is period_type) and (not scope or f.statement_scope is scope) and (not fact_kind or f.fact_kind is fact_kind) and (not start or f.period_end>=start) and (not end or f.period_end<=end) and (not as_of or f.published_at<=as_of and f.received_at<=as_of))[-limit:]
def _time(v:datetime)->str:return v.astimezone(UTC).isoformat()
def _encode(v):
    if isinstance(v,datetime):return _time(v)
    if isinstance(v,StrEnum):return v.value
    if v.__class__.__name__=="Decimal":return str(v)
    if hasattr(v,"__dataclass_fields__"):return {k:_encode(getattr(v,k)) for k in v.__dataclass_fields__}
    if isinstance(v,tuple):return [_encode(x) for x in v]
    return v
def _dump(v:FinancialFact)->str:return json.dumps(_encode(v),sort_keys=True,separators=(",",":"))
def _parse(v):return datetime.fromisoformat(v) if v else None
def _instrument(v:dict)->InstrumentIdentity:return InstrumentIdentity(v["instrument_id"],Exchange(v["exchange"]),v["symbol"],v.get("trading_symbol"),v.get("isin"),v.get("series"),InstrumentType(v["instrument_type"]),v.get("name"),v.get("currency","INR"),tuple(ProviderInstrumentMapping(**item) for item in v.get("provider_mappings",())))
def _fact(v:dict)->FinancialFact:return FinancialFact(v["fact_id"],_instrument(v["instrument"]),FinancialMetric(v["metric"]),__import__("decimal").Decimal(v["value"]),v["currency"],v["unit"],NumericScale(v["scale"]),FinancialPeriodType(v["period_type"]),FinancialValueBasis(v["value_basis"]),_parse(v.get("period_start")),_parse(v["period_end"]),v.get("fiscal_year"),v.get("fiscal_quarter"),StatementScope(v["statement_scope"]),FundamentalFactKind(v["fact_kind"]),v["source"],v.get("filing_id"),v.get("source_reference"),_parse(v["published_at"]),_parse(v["received_at"]),v["normalization_version"],tuple(v.get("provenance",())),tuple(v.get("parent_fact_ids",())),v.get("revision_of_fact_id"),tuple(FinancialQualityFlag(x) for x in v.get("quality_flags",())))
