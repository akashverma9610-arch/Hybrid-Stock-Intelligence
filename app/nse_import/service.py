from __future__ import annotations
import csv, hashlib, json, sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Iterable, Mapping, Protocol
from decimal import Decimal

from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateActionDisclosure, CorporateFiling, FilingTextAvailability, FilingType, FinancialResultMetadata, PrimarySourceQuality
from app.filings.store import CorporateFilingsStore, FilingWriteOutcome
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialQualityFlag, FinancialValueBasis, NumericScale, StatementScope
from app.fundamentals.store import FinancialFactStore, FinancialFactWriteOutcome
from app.market_data.models import InstrumentIdentity, MarketDataProvenance

class ExportFamily(StrEnum): ANNOUNCEMENTS="ANNOUNCEMENTS"; FINANCIAL_RESULTS="FINANCIAL_RESULTS"; CORPORATE_ACTIONS="CORPORATE_ACTIONS"; REGULATION_30="REGULATION_30"; REGULATION_31="REGULATION_31"; XBRL_CONVERTED_RESULTS="XBRL_CONVERTED_RESULTS"
class ImportStatus(StrEnum): COMPLETED="COMPLETED"; PARTIAL="PARTIAL"; REJECTED="REJECTED"; IDENTICAL="IDENTICAL"
@dataclass(frozen=True,slots=True)
class ImportRun:
 import_id:str; source:str; filename:str; checksum:str; family:ExportFamily; started_at:datetime; completed_at:datetime; rows_seen:int; accepted:int; duplicates:int; revisions:int; conflicts:int; rejected:int; unresolved_symbols:int; warnings:tuple[str,...]; status:ImportStatus
class InstrumentResolver(Protocol):
 def resolve(self,symbol:str,isin:str|None=None,canonical_instrument_id:str|None=None,company_name:str|None=None)->InstrumentIdentity|None: ...
class MappingInstrumentResolver:
 def __init__(self,values:Mapping[str,InstrumentIdentity]):self.values={k.upper():v for k,v in values.items()}
 def resolve(self,symbol,isin=None,canonical_instrument_id=None,company_name=None):
  value=self.values.get((canonical_instrument_id or symbol or company_name or "").strip().upper())
  return value if value and (not isin or value.isin and value.isin.upper()==isin.upper()) else None


class FrozenCohortInstrumentResolver:
 """Maps only an explicit frozen cohort: ISIN, canonical ID, then unique symbol.

 A supplied ISIN is an integrity assertion.  If it does not match a cohort
 identity, the row is unresolved rather than silently falling back to a symbol.
 """
 def __init__(self,values:Iterable[InstrumentIdentity],frozen_instrument_ids:Iterable[str]):
  allowed=frozenset(frozen_instrument_ids); selected=tuple(item for item in values if item.instrument_id in allowed)
  if len(selected)!=len(allowed):raise ValueError("Frozen cohort identities are incomplete.")
  self._by_id={item.instrument_id.upper():item for item in selected}
  self._by_isin:dict[str,tuple[InstrumentIdentity,...]]={}
  self._by_symbol:dict[str,tuple[InstrumentIdentity,...]]={}
  self._by_company_name:dict[str,tuple[InstrumentIdentity,...]]={}
  for item in selected:
   if item.isin:self._by_isin[item.isin.upper()]=(*self._by_isin.get(item.isin.upper(),()),item)
   self._by_symbol[item.symbol.upper()]=(*self._by_symbol.get(item.symbol.upper(),()),item)
   if item.name:self._by_company_name[item.name.strip().upper()]=(*self._by_company_name.get(item.name.strip().upper(),()),item)
 def resolve(self,symbol,isin=None,canonical_instrument_id=None,company_name=None):
  if isin:
   values=self._by_isin.get(isin.strip().upper(),())
   return values[0] if len(values)==1 else None
  if canonical_instrument_id:
   return self._by_id.get(canonical_instrument_id.strip().upper())
  if company_name:
   values=self._by_company_name.get(company_name.strip().upper(),())
   return values[0] if len(values)==1 else None
  values=self._by_symbol.get(symbol.strip().upper(),())
  return values[0] if len(values)==1 else None
class ImportRunStore:
 def __init__(self,path=":memory:"):
  self.c=sqlite3.connect(str(path));self.c.execute("CREATE TABLE IF NOT EXISTS nse_import_runs(import_id TEXT PRIMARY KEY,checksum TEXT UNIQUE NOT NULL,payload TEXT NOT NULL)")
 def get_checksum(self,checksum):
  row=self.c.execute("SELECT payload FROM nse_import_runs WHERE checksum=?",(checksum,)).fetchone();return _run(json.loads(row[0])) if row else None
 def save(self,value):
  existing=self.get_checksum(value.checksum)
  if existing:return existing
  self.c.execute("INSERT INTO nse_import_runs VALUES(?,?,?)",(value.import_id,value.checksum,json.dumps(_enc(value),sort_keys=True,separators=(",",":"))));self.c.commit();return value

class NSEOfficialExportProvider:
 """Reads explicit local CSV/XLSX exports only; no requests, browser, or macros."""
 REQUIRED={ExportFamily.ANNOUNCEMENTS:{"symbol","broadcast_at","subject"},ExportFamily.FINANCIAL_RESULTS:{"symbol","broadcast_at","period_end"},ExportFamily.CORPORATE_ACTIONS:{"symbol","broadcast_at","action_type"},ExportFamily.REGULATION_30:{"symbol","broadcast_at","subject"},ExportFamily.REGULATION_31:{"symbol","broadcast_at","subject"},ExportFamily.XBRL_CONVERTED_RESULTS:{"symbol","broadcast_at","period_end","metric","value"}}
 ALIASES={"symbol":"symbol","symbol name":"symbol","company":"company_name","isin":"isin","instrument id":"canonical_instrument_id","canonical instrument id":"canonical_instrument_id","subject":"subject","headline":"subject","broadcast date":"broadcast_at","broadcast datetime":"broadcast_at","broadcast date/time":"broadcast_at","announcement date":"broadcast_at","dissemination time":"broadcast_at","period start":"period_start","period end":"period_end","reporting period":"period_end","as on date":"period_end","period type":"period_type","financial period type":"period_type","scope":"scope","consolidated/standalone":"scope","event id":"event_id","announcement id":"event_id","document link":"document_reference","attachment":"document_reference","action":"document_reference","category":"category","action type":"action_type","record date":"record_date","ex date":"ex_date","effective date":"effective_date","ratio":"ratio","amount":"amount","metric":"metric","value":"value","currency":"currency","unit":"unit","basis":"basis","value basis":"basis","scale":"scale","fiscal year":"fiscal_year","fiscal quarter":"fiscal_quarter","revision of":"revision_of"}
 def __init__(self,*,maximum_bytes:int=20_000_000,maximum_rows:int=50_000):self.maximum_bytes,self.maximum_rows=maximum_bytes,maximum_rows
 def read(self,path:str|Path,*,family:ExportFamily|None=None)->tuple[Path,str,ExportFamily,list[dict[str,str]]]:
  raw=str(path)
  if "://" in raw:raise ValueError("NSE official import accepts a local file path only.")
  target=Path(path)
  if not target.is_file():raise ValueError("NSE official import file does not exist.")
  if target.suffix.lower() not in {".csv",".xlsx"}:raise ValueError("NSE official import supports CSV or XLSX only.")
  if target.stat().st_size>self.maximum_bytes:raise ValueError("NSE official import exceeds configured file-size limit.")
  checksum=hashlib.sha256(target.read_bytes()).hexdigest();rows=self._rows(target)
  if len(rows)>self.maximum_rows:raise ValueError("NSE official import exceeds configured row limit.")
  normalized=[{self.ALIASES.get(k.strip().lower(),k.strip().lower()):str(v).strip() for k,v in row.items() if k is not None} for row in rows]
  detected=family or self._detect(normalized[0] if normalized else {})
  required=self.REQUIRED[detected]
  official_reg31={"company_name","broadcast_at","period_end","document_reference"}
  if not normalized or (not required.issubset(normalized[0]) and not (detected is ExportFamily.REGULATION_31 and official_reg31.issubset(normalized[0]))):raise ValueError("NSE official export schema is unsupported for selected family.")
  return target,checksum,detected,normalized
 def _rows(self,path):
  if path.suffix.lower()==".csv":
   with path.open("r",encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
  try:
   from openpyxl import load_workbook
  except ImportError as e:raise ValueError("XLSX import requires the optional openpyxl dependency.") from e
  book=load_workbook(path,read_only=True,data_only=True,keep_vba=False);sheet=book.active;values=list(sheet.iter_rows(values_only=True));headers=[str(x or "") for x in values[0]];return [dict(zip(headers,row)) for row in values[1:]]
 def _detect(self,row):
  columns=set(row)
  if {"metric","value","period_end"}.issubset(columns):return ExportFamily.XBRL_CONVERTED_RESULTS
  if "action_type" in columns:return ExportFamily.CORPORATE_ACTIONS
  if "period_end" in columns:return ExportFamily.FINANCIAL_RESULTS
  if "category" in columns and "31" in row.get("category",""):return ExportFamily.REGULATION_31
  if "category" in columns and "30" in row.get("category",""):return ExportFamily.REGULATION_30
  if {"symbol","broadcast_at","subject"}.issubset(columns):return ExportFamily.ANNOUNCEMENTS
  raise ValueError("NSE export family is ambiguous; select an explicit type.")

class OfficialExchangeImportService:
 def __init__(self,provider:NSEOfficialExportProvider,resolver:InstrumentResolver,filings:CorporateFilingsStore,facts:FinancialFactStore,runs:ImportRunStore,*,clock=lambda:datetime.now(UTC)):
  self.provider,self.resolver,self.filings,self.facts,self.runs,self.clock=provider,resolver,filings,facts,runs,clock
 def import_file(self,path,*,family:ExportFamily|None=None,dry_run:bool=False,latest_reg31_period_only:bool=False)->ImportRun:
  started=self.clock();target,checksum,kind,rows=self.provider.read(path,family=family);prior=self.runs.get_checksum(checksum)
  if prior:return ImportRun(prior.import_id,prior.source,prior.filename,prior.checksum,prior.family,started,self.clock(),prior.rows_seen,0,prior.rows_seen,0,0,0,0,("IDENTICAL_FILE_ALREADY_IMPORTED",),ImportStatus.IDENTICAL)
  if latest_reg31_period_only:
   if kind is not ExportFamily.REGULATION_31:raise ValueError("Latest-period selection is only supported for NSE Regulation 31 exports.")
   latest=max(_dt(row["period_end"]) for row in rows)
   rows=[row for row in rows if _dt(row["period_end"])==latest]
  count={"accepted":0,"duplicates":0,"revisions":0,"conflicts":0,"rejected":0,"unresolved":0};warnings=[]
  for number,row in enumerate(rows,1):
   try:
    instrument=self.resolver.resolve(row.get("symbol", ""),row.get("isin") or None,row.get("canonical_instrument_id") or None,row.get("company_name") or None)
    if not instrument:count["unresolved"]+=1;warnings.append(f"UNRESOLVED_SYMBOL_ROW:{number}");continue
    filing=self._filing(kind,row,instrument,started)
    if not dry_run:
     outcome=self.filings.save(filing)
     if outcome is FilingWriteOutcome.IDENTICAL:count["duplicates"]+=1;continue
     if kind is ExportFamily.XBRL_CONVERTED_RESULTS:self._fact(row,filing,instrument,count)
    count["accepted"]+=1
    if filing.revision_of_filing_id:count["revisions"]+=1
   except ValueError as e:
    if kind is ExportFamily.REGULATION_31 and str(e)=="Corporate filing ID is immutable and cannot be overwritten.":
     count["conflicts"]+=1;warnings.append(f"CONFLICT_ROW:{number}:NSE_REG31_SAME_PERIOD_RAW_EVIDENCE_CONFLICT")
    else:count["rejected"]+=1;warnings.append(f"REJECTED_ROW:{number}:{str(e)[:80]}")
  status=ImportStatus.REJECTED if not count["accepted"] and (count["rejected"] or count["unresolved"]) else ImportStatus.PARTIAL if count["rejected"] or count["unresolved"] or count["conflicts"] else ImportStatus.COMPLETED
  value=ImportRun("nse-import:"+checksum[:24],"NSE",target.name,checksum,kind,started,self.clock(),len(rows),count["accepted"],count["duplicates"],count["revisions"],count["conflicts"],count["rejected"],count["unresolved"],tuple(warnings),status)
  return value if dry_run else self.runs.save(value)
 def _filing(self,kind,row,instrument,received):
  published=_dt(row["broadcast_at"]);event=row.get("event_id") or hashlib.sha256((instrument.instrument_id+row["broadcast_at"]+row.get("subject","")+row.get("metric","")+row.get("period_end","")).encode()).hexdigest()[:18];identifier="nse:NSE:"+event
  action=_action(row) if kind is ExportFamily.CORPORATE_ACTIONS else None;ftype=FilingType.FINANCIAL_RESULTS if kind in {ExportFamily.FINANCIAL_RESULTS,ExportFamily.XBRL_CONVERTED_RESULTS} else FilingType.SHAREHOLDING_PATTERN if kind is ExportFamily.REGULATION_31 else action.action_type if action else FilingType.CORPORATE_ANNOUNCEMENT
  period=_dt(row["period_end"]) if row.get("period_end") else None;financial=FinancialResultMetadata(period,row.get("scope"),row.get("period_type") or "QUARTERLY",bool(row.get("revision_of"))) if period else None
  request_reference="local-import:"+_row_fingerprint(row) if kind is ExportFamily.REGULATION_31 else "local-import"
  p=MarketDataProvenance("NSE",event,published,published,received,"nse-official-export-v1",request_reference,row.get("document_reference"))
  category=row.get("category") or ("REGULATION_31_SHAREHOLDING_PATTERN" if kind is ExportFamily.REGULATION_31 else None)
  return CorporateFiling(identifier,instrument,instrument.exchange,"NSE",PrimarySourceQuality.PRIMARY_EXCHANGE,ftype,category,row.get("subject") or row.get("metric") or ftype.value,published,received,event,row.get("document_reference"),p,period_end=period,text_availability=FilingTextAvailability.SOURCE_TEXT,revision_of_filing_id=row.get("revision_of") or None,action=action,financial_result=financial,normalization_version="nse-official-export-v1",warnings=("IMPORT_METHOD_OFFICIAL_EXPORT",))
 def _fact(self,row,filing,instrument,count):
  try:metric=FinancialMetric(row["metric"].strip().upper())
  except ValueError:count["rejected"]+=1;return
  scope=StatementScope(row.get("scope","CONSOLIDATED").strip().upper()) if row.get("scope") else StatementScope.CONSOLIDATED
  end=_dt(row["period_end"]);period_type=_period_type(row.get("period_type"));basis=_basis(row.get("basis"),period_type);scale=_scale(row.get("scale"));start=_dt(row["period_start"]) if row.get("period_start") else None;fiscal_year=int(row["fiscal_year"]) if row.get("fiscal_year") else end.year;fiscal_quarter=int(row["fiscal_quarter"]) if row.get("fiscal_quarter") else ((end.month-1)//3)+1 if period_type is FinancialPeriodType.QUARTERLY else None;identifier="nse-fact:"+hashlib.sha256((filing.filing_id+metric.value).encode()).hexdigest()[:24]
  fact=FinancialFact(identifier,instrument,metric,Decimal(row["value"]),row.get("currency") or "INR",row.get("unit") or "INR",scale,period_type,basis,start,end,fiscal_year,fiscal_quarter,scope,FundamentalFactKind.REPORTED,"NSE",filing.filing_id,filing.source_reference,filing.announced_at,filing.received_at,"nse-official-export-v1",("OFFICIAL_EXPORT",),(),None,(FinancialQualityFlag.COMPLETE,))
  result=self.facts.save(fact)
  if result is FinancialFactWriteOutcome.CONFLICT:count["conflicts"]+=1
def _dt(value):
 for fmt in (None,"%d-%m-%Y","%d/%m/%Y","%d-%b-%Y","%d-%b-%Y %H:%M:%S"):
  try:
   parsed=datetime.fromisoformat(value.replace("Z","+00:00")) if fmt is None else datetime.strptime(value,fmt)
   return parsed.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
  except ValueError:pass
 raise ValueError("invalid required NSE date/timestamp")
def _row_fingerprint(row):return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _period_type(value):
 normalized=(value or "QUARTERLY").strip().upper().replace(" ","_")
 aliases={"QUARTER":"QUARTERLY","YEARLY":"ANNUAL","FULL_YEAR":"ANNUAL"}
 try:return FinancialPeriodType(aliases.get(normalized,normalized))
 except ValueError:raise ValueError("unsupported financial period type") from None
def _basis(value,period_type):
 if not value:return FinancialValueBasis.FULL_YEAR if period_type is FinancialPeriodType.ANNUAL else FinancialValueBasis.QUARTER_ONLY
 normalized=value.strip().upper().replace(" ","_")
 aliases={"QUARTER":"QUARTER_ONLY","YEAR_TO_DATE":"YEAR_TO_DATE","FULLYEAR":"FULL_YEAR"}
 try:return FinancialValueBasis(aliases.get(normalized,normalized))
 except ValueError:raise ValueError("unsupported financial value basis") from None
def _scale(value):
 if not value:return NumericScale.CRORES
 normalized=value.strip().upper().replace(" ","_")
 try:return NumericScale(normalized)
 except ValueError:raise ValueError("unsupported financial numeric scale") from None
def _action(row):
 mapping={"DIVIDEND":FilingType.DIVIDEND,"BONUS":FilingType.BONUS,"SPLIT":FilingType.SPLIT,"RIGHTS":FilingType.RIGHTS,"BUYBACK":FilingType.BUYBACK};kind=mapping.get(row["action_type"].strip().upper())
 if not kind:raise ValueError("unsupported corporate action type")
 return CorporateActionDisclosure(kind,_dt(row["record_date"]) if row.get("record_date") else None,_dt(row["ex_date"]) if row.get("ex_date") else None,_dt(row["effective_date"]) if row.get("effective_date") else None,Decimal(row["ratio"]) if row.get("ratio") else None,Decimal(row["amount"]) if row.get("amount") else None,row.get("subject"))
def _enc(v):
 if isinstance(v,datetime):return v.isoformat()
 if isinstance(v,StrEnum):return v.value
 if hasattr(v,"__dataclass_fields__"):return {k:_enc(getattr(v,k)) for k in v.__dataclass_fields__}
 if isinstance(v,tuple):return [_enc(x) for x in v]
 return v
def _run(v):return ImportRun(v["import_id"],v["source"],v["filename"],v["checksum"],ExportFamily(v["family"]),datetime.fromisoformat(v["started_at"]),datetime.fromisoformat(v["completed_at"]),v["rows_seen"],v["accepted"],v["duplicates"],v["revisions"],v["conflicts"],v["rejected"],v["unresolved_symbols"],tuple(v["warnings"]),ImportStatus(v["status"]))
