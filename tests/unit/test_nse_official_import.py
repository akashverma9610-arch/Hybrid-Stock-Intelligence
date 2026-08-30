from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import pytest
from app.filings.store import SQLiteCorporateFilingsStore
from app.fundamentals.store import SQLiteFinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.nse_import.service import ExportFamily, FrozenCohortInstrumentResolver, ImportRunStore, MappingInstrumentResolver, NSEOfficialExportProvider, OfficialExchangeImportService, ImportStatus
T=datetime(2026,9,3,10,tzinfo=UTC)
def service(tmp_path):
 i=InstrumentIdentity("NSE:ALPHA",Exchange.NSE,"ALPHA","ALPHA","INE000A01000",None,InstrumentType.NSE_EQUITY,"Alpha")
 return OfficialExchangeImportService(NSEOfficialExportProvider(maximum_rows=10),MappingInstrumentResolver({"ALPHA":i}),SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite"),SQLiteFinancialFactStore(tmp_path/"facts.sqlite"),ImportRunStore(tmp_path/"runs.sqlite"),clock=lambda:T)
def write(tmp_path,name,text):p=tmp_path/name;p.write_text(text,encoding="utf-8");return p
def test_xbrl_csv_import_checksum_pit_facts_dry_run_and_unknown_symbol(tmp_path):
 p=write(tmp_path,"results.csv","Symbol,Broadcast Date,Period End,Metric,Value,Scope,Event ID\nALPHA,2026-08-20T10:00:00+05:30,2026-06-30,REVENUE,100,CONSOLIDATED,r1\nALPHA,2026-08-20T10:00:00+05:30,2026-06-30,PAT,10,CONSOLIDATED,r2\nUNKNOWN,2026-08-20T10:00:00+05:30,2026-06-30,REVENUE,99,CONSOLIDATED,r3\n")
 s=service(tmp_path);dry=s.import_file(p,family=ExportFamily.XBRL_CONVERTED_RESULTS,dry_run=True);assert dry.accepted==2 and dry.unresolved_symbols==1 and s.filings.list(limit=10)==()
 report=s.import_file(p,family=ExportFamily.XBRL_CONVERTED_RESULTS);assert report.status is ImportStatus.PARTIAL and report.accepted==2 and report.unresolved_symbols==1
 assert len(s.filings.list(instrument_id="NSE:ALPHA",as_of=T,limit=10))==2 and len(s.facts.series("NSE:ALPHA",__import__("app.fundamentals.models",fromlist=["FinancialMetric"]).FinancialMetric.REVENUE,as_of=T))==1
 assert s.import_file(p,family=ExportFamily.XBRL_CONVERTED_RESULTS).status is ImportStatus.IDENTICAL
def test_families_actions_schema_rejection_and_local_path_safety(tmp_path):
 s=service(tmp_path);actions=write(tmp_path,"actions.csv","Symbol,Broadcast Date,Action Type,Ratio,Event ID\nALPHA,2026-08-20T10:00:00+05:30,BONUS,1,r4\n")
 assert s.import_file(actions,family=ExportFamily.CORPORATE_ACTIONS).accepted==1 and s.filings.get("nse:NSE:r4").action.action_type.value=="BONUS"
 announcements=write(tmp_path,"ann.csv","Symbol,Broadcast Date,Subject,Category,Event ID\nALPHA,2026-08-20T10:00:00+05:30,Material disclosure,Regulation 30,r5\n")
 assert s.import_file(announcements,family=ExportFamily.REGULATION_30).accepted==1
 with pytest.raises(ValueError):s.import_file(write(tmp_path,"bad.csv","A,B\n1,2\n"))
 with pytest.raises(ValueError):NSEOfficialExportProvider().read("https://nse.example/export.csv")
def test_cli_reports_local_import_without_network(tmp_path):
 p=write(tmp_path,"ann.csv","Symbol,Broadcast Date,Subject,Event ID\nALPHA,2026-08-20T10:00:00+05:30,Update,r6\n");s=service(tmp_path);out=[]
 from app.runtime.cli import main
 assert main(["import-nse",str(p),"--type","announcements"],import_service_factory=lambda:s,output=out.append)==0 and "accepted=1" in out[0]


def test_official_reg31_shareholding_page_csv_maps_by_exact_current_nse_company_name_and_is_idempotent(tmp_path):
 i=InstrumentIdentity("NSE:APOLLOHOSP",Exchange.NSE,"APOLLOHOSP","APOLLOHOSP","INE437A01024",None,InstrumentType.NSE_EQUITY,"Apollo Hospitals Enterprise Limited")
 resolver=FrozenCohortInstrumentResolver((i,),(i.instrument_id,))
 filings=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
 importer=OfficialExchangeImportService(NSEOfficialExportProvider(maximum_rows=10),resolver,filings,SQLiteFinancialFactStore(tmp_path/"facts.sqlite"),ImportRunStore(tmp_path/"runs.sqlite"),clock=lambda:T)
 p=write(tmp_path,"CF-Shareholding-Pattern-equities-APOLLOHOSP.csv",'COMPANY,PROMOTER & PROMOTER GROUP (A),PUBLIC (B),SHARES HELD BY EMPLOYEE TRUSTS (C2),STATUS,AS ON DATE,SUBMISSION DATE,REVISION DATE,ACTION,BROADCAST DATE/TIME,EXCHANGE DISSEMINATION TIME,TIME TAKEN\nApollo Hospitals Enterprise Limited,28.02,71.98,0,-,30-JUN-2026,03-JUL-2026,,https://nsearchives.nseindia.com/corporate/xbrl/SHP_1.xml,03-JUL-2026 16:32:35,03-JUL-2026 16:32:39,00:00:04\n')

 report=importer.import_file(p,family=ExportFamily.REGULATION_31)
 reopened=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
 stored=reopened.list(instrument_id=i.instrument_id,as_of=T,limit=10)

 assert (report.status,report.accepted,report.unresolved_symbols,report.conflicts)==(ImportStatus.COMPLETED,1,0,0)
 assert len(stored)==1 and stored[0].filing_type.value=="SHAREHOLDING_PATTERN"
 assert stored[0].period_end.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat()=="2026-06-30"
 assert stored[0].announced_at.isoformat()=="2026-07-03T11:02:35+00:00"
 assert stored[0].document_reference=="https://nsearchives.nseindia.com/corporate/xbrl/SHP_1.xml"
 assert importer.import_file(p,family=ExportFamily.REGULATION_31).status is ImportStatus.IDENTICAL


def test_reg31_smoke_can_select_only_latest_explicit_reporting_period(tmp_path):
 i=InstrumentIdentity("NSE:APOLLOHOSP",Exchange.NSE,"APOLLOHOSP","APOLLOHOSP","INE437A01024",None,InstrumentType.NSE_EQUITY,"Apollo Hospitals Enterprise Limited")
 filings=SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite")
 importer=OfficialExchangeImportService(NSEOfficialExportProvider(maximum_rows=10),FrozenCohortInstrumentResolver((i,),(i.instrument_id,)),filings,SQLiteFinancialFactStore(tmp_path/"facts.sqlite"),ImportRunStore(tmp_path/"runs.sqlite"),clock=lambda:T)
 p=write(tmp_path,"shareholding.csv","COMPANY,AS ON DATE,ACTION,BROADCAST DATE/TIME\nApollo Hospitals Enterprise Limited,31-MAR-2026,https://nse.example/older.xml,03-APR-2026 10:00:00\nApollo Hospitals Enterprise Limited,30-JUN-2026,https://nse.example/latest.xml,03-JUL-2026 16:32:35\n")

 report=importer.import_file(p,family=ExportFamily.REGULATION_31,latest_reg31_period_only=True)
 stored=filings.list(instrument_id=i.instrument_id,as_of=T,limit=10)

 assert report.accepted==1 and report.rows_seen==1
 assert len(stored)==1 and stored[0].document_reference=="https://nse.example/latest.xml"


def test_reg31_same_period_different_raw_evidence_fails_closed_without_ownership_interpretation(tmp_path):
 i=InstrumentIdentity("NSE:APOLLOHOSP",Exchange.NSE,"APOLLOHOSP","APOLLOHOSP","INE437A01024",None,InstrumentType.NSE_EQUITY,"Apollo Hospitals Enterprise Limited")
 importer=OfficialExchangeImportService(NSEOfficialExportProvider(maximum_rows=10),FrozenCohortInstrumentResolver((i,),(i.instrument_id,)),SQLiteCorporateFilingsStore(tmp_path/"filings.sqlite"),SQLiteFinancialFactStore(tmp_path/"facts.sqlite"),ImportRunStore(tmp_path/"runs.sqlite"),clock=lambda:T)
 first=write(tmp_path,"first.csv","COMPANY,PROMOTER & PROMOTER GROUP (A),AS ON DATE,ACTION,BROADCAST DATE/TIME\nApollo Hospitals Enterprise Limited,28.02,30-JUN-2026,https://nse.example/latest.xml,03-JUL-2026 16:32:35\n")
 changed=write(tmp_path,"changed.csv","COMPANY,PROMOTER & PROMOTER GROUP (A),AS ON DATE,ACTION,BROADCAST DATE/TIME\nApollo Hospitals Enterprise Limited,29.02,30-JUN-2026,https://nse.example/latest.xml,03-JUL-2026 16:32:35\n")

 assert importer.import_file(first,family=ExportFamily.REGULATION_31).accepted==1
 report=importer.import_file(changed,family=ExportFamily.REGULATION_31)

 assert report.status is ImportStatus.PARTIAL and report.conflicts==1 and report.accepted==0
 assert "NSE_REG31_SAME_PERIOD_RAW_EVIDENCE_CONFLICT" in report.warnings[0]
