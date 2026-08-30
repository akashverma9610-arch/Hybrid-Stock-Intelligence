"""Official locally supplied NSE primary-market CSV adapter; no HTTP/scraping."""
from __future__ import annotations
import csv,hashlib
from datetime import UTC,datetime
from decimal import Decimal
from pathlib import Path
from app.data_sources.models import DataFamily,SourceRecordProvenance
from app.primary_market.models import *
class NSEOfficialPrimaryMarketExportProvider:
 REQUIRED={"issue_id","issuer_name","issue_type","published_at"}
 ALIASES={"issue id":"issue_id","company":"issuer_name","issuer":"issuer_name","issue type":"issue_type","open date":"issue_open_date","close date":"issue_close_date","listing date":"listing_date","issue price":"issue_price","total issue size":"total_issue_size","fresh issue":"fresh_issue_amount","ofs":"ofs_amount","symbol":"future_symbol","published at":"published_at","sector":"sector"}
 def read(self,path):
  target=Path(path)
  if not target.is_file() or target.suffix.lower()!=".csv":raise ValueError("Primary-market official import accepts local CSV only.")
  raw=target.read_bytes();rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()));rows=[{self.ALIASES.get(k.strip().lower(),k.strip().lower()):str(v).strip() for k,v in row.items() if k} for row in rows]
  if not rows or not self.REQUIRED.issubset(rows[0]):raise ValueError("NSE primary-market export schema is unsupported.")
  return target,hashlib.sha256(raw).hexdigest(),rows
 def normalize(self,row,*,received_at):
  published=_dt(row["published_at"]);issue_id=row["issue_id"] or "nse-issue:"+hashlib.sha256((row["issuer_name"]+row["published_at"]).encode()).hexdigest()[:20];prov=SourceRecordProvenance(issue_id,"NSE",issue_id,published,published,received_at,None,None,DataFamily.IPO_PRIMARY_MARKET,"nse-primary-market-export-v1","nse-primary-market-export-v1")
  kind=PrimaryMarketIssueType(row["issue_type"].upper()) if row["issue_type"].upper() in {x.value for x in PrimaryMarketIssueType} else PrimaryMarketIssueType.OTHER
  return PrimaryMarketIssue(issue_id,row["issuer_name"],row.get("instrument_id") or None,row.get("future_symbol") or None,row.get("exchange") or "NSE",kind,row.get("security_type") or None,row.get("sector") or None,*[_dt(row[k]) if row.get(k) else None for k in ("issue_open_date","issue_close_date","listing_date")],*[_decimal(row.get(k)) for k in ("price_band_low","price_band_high","issue_price")],int(row["lot_size"]) if row.get("lot_size") else None,*[_decimal(row.get(k)) for k in ("total_issue_size","fresh_issue_amount","ofs_amount","shares_offered")],row.get("currency") or "INR",row.get("size_unit") or "SOURCE_UNIT","NSE",published,received_at,prov,tuple(x for x in row.get("selling_shareholders","").split("|") if x),tuple(x for x in row.get("document_references","").split("|") if x),"nse-primary-market-export-v1",("PRIMARY_EXCHANGE","IMPORT_METHOD_OFFICIAL_EXPORT"))
class OfficialPrimaryMarketImportService:
 def __init__(self,provider,store,*,clock=lambda:datetime.now(UTC)):self.provider,self.store,self.clock=provider,store,clock
 def import_file(self,path):
  target,checksum,rows=self.provider.read(path);accepted=duplicates=conflicts=0
  for row in rows:
   try:
    if self.store.save_issue(self.provider.normalize(row,received_at=self.clock())):accepted+=1
    else:duplicates+=1
   except ValueError:conflicts+=1
  return {"filename":target.name,"checksum":checksum,"accepted":accepted,"duplicates":duplicates,"conflicts":conflicts}
def _dt(v):
 x=datetime.fromisoformat(v.replace("Z","+00:00"));return x.replace(tzinfo=UTC) if x.tzinfo is None else x.astimezone(UTC)
def _decimal(v):return Decimal(v) if v not in {None,""} else None
