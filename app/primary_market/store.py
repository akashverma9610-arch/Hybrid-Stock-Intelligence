from __future__ import annotations
import json,sqlite3
from dataclasses import fields
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from app.data_sources.models import DataFamily,SourceRecordProvenance
from app.primary_market.models import *
class SQLitePrimaryMarketStore:
 def __init__(self,path=":memory:"):
  self.c=sqlite3.connect(str(path),check_same_thread=False);self.c.row_factory=sqlite3.Row;self.c.executescript("""CREATE TABLE IF NOT EXISTS primary_market_issues(issue_id TEXT PRIMARY KEY,open_date TEXT,listing_date TEXT,sector TEXT,issue_type TEXT,issuer TEXT,payload TEXT NOT NULL);CREATE INDEX IF NOT EXISTS ix_pm_open ON primary_market_issues(open_date);CREATE INDEX IF NOT EXISTS ix_pm_listing ON primary_market_issues(listing_date);CREATE INDEX IF NOT EXISTS ix_pm_sector ON primary_market_issues(sector);CREATE TABLE IF NOT EXISTS primary_market_subscriptions(snapshot_id TEXT PRIMARY KEY,issue_id TEXT NOT NULL,observed_at TEXT NOT NULL,category TEXT NOT NULL,payload TEXT NOT NULL);CREATE INDEX IF NOT EXISTS ix_pm_subscription ON primary_market_subscriptions(issue_id,observed_at,category);CREATE TABLE IF NOT EXISTS primary_market_listing_outcomes(issue_id TEXT PRIMARY KEY,observed_at TEXT NOT NULL,payload TEXT NOT NULL);""")
 def save_issue(self,v):
  old=self.get_issue(v.issue_id)
  if old:
   if old==v:return False
   raise ValueError("Primary-market issue identity is immutable.")
  self.c.execute("INSERT INTO primary_market_issues VALUES(?,?,?,?,?,?,?)",(v.issue_id,_t(v.issue_open_date),_t(v.listing_date),v.sector,v.issue_type.value,v.issuer_name,_d(v)));self.c.commit();return True
 def get_issue(self,i):
  r=self.c.execute("SELECT payload FROM primary_market_issues WHERE issue_id=?",(i,)).fetchone();return _issue(json.loads(r[0])) if r else None
 def list_issues(self,*,start=None,end=None,sector=None,issue_type=None,status=None,as_of=None,limit=100):
  if not 1<=limit<=200:raise ValueError("Primary-market limit must be 1..200.")
  rows=self.c.execute("SELECT payload FROM primary_market_issues ORDER BY COALESCE(open_date,listing_date) DESC,issue_id DESC LIMIT ?",(limit,)).fetchall();out=[]
  for r in rows:
   v=_issue(json.loads(r[0]));date=v.issue_open_date or v.listing_date
   if (start and (date is None or date<start)) or (end and (date is None or date>end)) or (sector and sector!=v.sector) or (issue_type and issue_type is not v.issue_type) or (as_of and not v.eligible_as_of(as_of)):continue
   if status and _status(v,as_of or datetime.max.replace(tzinfo=v.published_at.tzinfo)) is not status:continue
   out.append(v)
  return tuple(out)
 def save_subscription(self,v):
  r=self.c.execute("SELECT payload FROM primary_market_subscriptions WHERE snapshot_id=?",(v.snapshot_id,)).fetchone()
  if r:
   if _sub(json.loads(r[0]))==v:return False
   raise ValueError("Subscription snapshot identity is immutable.")
  self.c.execute("INSERT INTO primary_market_subscriptions VALUES(?,?,?,?,?)",(v.snapshot_id,v.issue_id,_t(v.observed_at),v.category.value,_d(v)));self.c.commit();return True
 def subscriptions(self,issue_id,*,as_of=None):
  rows=self.c.execute("SELECT payload FROM primary_market_subscriptions WHERE issue_id=? ORDER BY observed_at,snapshot_id",(issue_id,)).fetchall();return tuple(v for r in rows if (v:=_sub(json.loads(r[0]))) and (as_of is None or v.eligible_as_of(as_of)))
 def save_listing_outcome(self,v):
  old=self.get_listing_outcome(v.issue_id)
  if old:
   if old==v:return False
   raise ValueError("Listing outcome identity is immutable.")
  self.c.execute("INSERT INTO primary_market_listing_outcomes VALUES(?,?,?)",(v.issue_id,_t(v.observed_at),_d(v)));self.c.commit();return True
 def get_listing_outcome(self,issue_id,*,as_of=None):
  r=self.c.execute("SELECT payload FROM primary_market_listing_outcomes WHERE issue_id=?",(issue_id,)).fetchone();v=_out(json.loads(r[0])) if r else None;return v if v and (as_of is None or v.observed_at<=as_of) else None
class PostgreSQLPrimaryMarketStore:
 def __init__(self,connections):
  from app.storage.database import DatabaseBackend
  if connections.settings.backend is not DatabaseBackend.POSTGRESQL:raise ValueError("PostgreSQL primary-market store requires DATABASE_BACKEND=postgresql.")
  self.connections=connections
 def save_issue(self,v):
  old=self.get_issue(v.issue_id)
  if old:
   if old==v:return False
   raise ValueError("Primary-market issue identity is immutable.")
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("INSERT INTO primary_market_issues(issue_id,open_date,listing_date,sector,issue_type,issuer,payload) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)",(v.issue_id,v.issue_open_date,v.listing_date,v.sector,v.issue_type.value,v.issuer_name,_d(v)))
  return True
 def get_issue(self,i):
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("SELECT payload FROM primary_market_issues WHERE issue_id=%s",(i,));r=x.fetchone()
  return _issue(r[0] if isinstance(r[0],dict) else json.loads(r[0])) if r else None
 def list_issues(self,*,start=None,end=None,sector=None,issue_type=None,status=None,as_of=None,limit=100):
  if not 1<=limit<=200:raise ValueError("Primary-market limit must be 1..200.")
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("SELECT payload FROM primary_market_issues ORDER BY COALESCE(open_date,listing_date) DESC,issue_id DESC LIMIT %s",(limit,));rows=x.fetchall()
  out=[]
  for r in rows:
   v=_issue(r[0] if isinstance(r[0],dict) else json.loads(r[0]));date=v.issue_open_date or v.listing_date
   if (start and (date is None or date<start)) or (end and (date is None or date>end)) or (sector and sector!=v.sector) or (issue_type and issue_type is not v.issue_type) or (as_of and not v.eligible_as_of(as_of)):continue
   if status and _status(v,as_of or datetime.max.replace(tzinfo=v.published_at.tzinfo)) is not status:continue
   out.append(v)
  return tuple(out)
 def save_subscription(self,v):
  values=self.subscriptions(v.issue_id);old=next((x for x in values if x.snapshot_id==v.snapshot_id),None)
  if old:
   if old==v:return False
   raise ValueError("Subscription snapshot identity is immutable.")
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("INSERT INTO primary_market_subscriptions(snapshot_id,issue_id,observed_at,category,payload) VALUES(%s,%s,%s,%s,%s::jsonb)",(v.snapshot_id,v.issue_id,v.observed_at,v.category.value,_d(v)))
  return True
 def subscriptions(self,issue_id,*,as_of=None):
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("SELECT payload FROM primary_market_subscriptions WHERE issue_id=%s ORDER BY observed_at,snapshot_id",(issue_id,));rows=x.fetchall()
  return tuple(v for r in rows if (v:=_sub(r[0] if isinstance(r[0],dict) else json.loads(r[0]))) and (as_of is None or v.eligible_as_of(as_of)))
 def save_listing_outcome(self,v):
  old=self.get_listing_outcome(v.issue_id)
  if old:
   if old==v:return False
   raise ValueError("Listing outcome identity is immutable.")
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("INSERT INTO primary_market_listing_outcomes(issue_id,observed_at,payload) VALUES(%s,%s,%s::jsonb)",(v.issue_id,v.observed_at,_d(v)))
  return True
 def get_listing_outcome(self,issue_id,*,as_of=None):
  with self.connections.transaction() as c:
   with c.cursor() as x:x.execute("SELECT payload FROM primary_market_listing_outcomes WHERE issue_id=%s",(issue_id,));r=x.fetchone()
  v=_out(r[0] if r and isinstance(r[0],dict) else json.loads(r[0])) if r else None;return v if v and (as_of is None or v.observed_at<=as_of) else None
def _t(v):return v.isoformat() if v else None
def _p(v):return datetime.fromisoformat(v) if v else None
def _e(v):
 if isinstance(v,datetime):return _t(v)
 if isinstance(v,Decimal):return str(v)
 if isinstance(v,StrEnum):return v.value
 if hasattr(v,"__dataclass_fields__"):return {f.name:_e(getattr(v,f.name)) for f in fields(v)}
 if isinstance(v,tuple):return [_e(x) for x in v]
 return v
def _d(v):return json.dumps(_e(v),sort_keys=True,separators=(",",":"))
def _prov(v):return SourceRecordProvenance(v["source_id"],v["provider"],v.get("source_reference"),_p(v.get("observed_at")),_p(v.get("published_at")),_p(v["received_at"]),_p(v.get("effective_from")),_p(v.get("effective_to")),DataFamily(v["family"]),v["schema_version"],v["normalization_version"])
def _dec(v):return Decimal(v) if v is not None else None
def _issue(v):return PrimaryMarketIssue(v["issue_id"],v["issuer_name"],v.get("instrument_id"),v.get("future_symbol"),v["exchange"],PrimaryMarketIssueType(v["issue_type"]),v.get("security_type"),v.get("sector"),_p(v.get("issue_open_date")),_p(v.get("issue_close_date")),_p(v.get("listing_date")),*[_dec(v.get(k)) for k in ("price_band_low","price_band_high","issue_price")],v.get("lot_size"),*[_dec(v.get(k)) for k in ("total_issue_size","fresh_issue_amount","ofs_amount","shares_offered")],v["currency"],v["size_unit"],v["source"],_p(v["published_at"]),_p(v["received_at"]),_prov(v["provenance"]),tuple(v.get("selling_shareholder_references",())),tuple(v.get("document_references",())),v.get("normalization_version","primary-market-v1"),tuple(v.get("warnings",())))
def _sub(v):return IssueSubscriptionSnapshot(v["snapshot_id"],v["issue_id"],_p(v["observed_at"]),SubscriptionCategory(v["category"]),_dec(v.get("offered_quantity")),_dec(v.get("bid_quantity")),_dec(v.get("subscription_multiple")),SubscriptionSemantic(v["semantic"]),v["source"],_p(v["received_at"]),_prov(v["provenance"]),tuple(v.get("warnings",())))
def _out(v):return ListingOutcome(v["issue_id"],_p(v["observed_at"]),*[_dec(v.get(k)) for k in ("issue_price","listing_open","listing_high","listing_low","listing_close","first_day_return")],tuple(v.get("provenance_ids",())),tuple(v.get("warnings",())))
def _status(v,now):return PrimaryMarketIssueStatus.LISTED if v.listing_date and v.listing_date<=now else PrimaryMarketIssueStatus.CLOSED if v.issue_close_date and v.issue_close_date<now else PrimaryMarketIssueStatus.OPEN if v.issue_open_date and v.issue_open_date<=now else PrimaryMarketIssueStatus.UPCOMING if v.issue_open_date else PrimaryMarketIssueStatus.UNKNOWN
