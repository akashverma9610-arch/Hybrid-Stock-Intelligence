from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import pow

from app.analysis.models import AnalysisStatus
from app.domain.models import AsOfSnapshot, ObservationKind, ValidationStatus


@dataclass(frozen=True, slots=True)
class FundamentalRules:
    healthy_growth: float; weak_growth: float; return_ratio_healthy: float; leverage_elevated: float; coverage_stressed: float; margin_change: float
    roce_method: str = "equity_debt_cash_v1"
    annual_period_days: int = 365
    quarterly_period_days: int = 90


@dataclass(frozen=True, slots=True)
class FundamentalAnalysis:
    state: str; details: tuple[tuple[str, str], ...]; input_ids: tuple[str, ...]; status: AnalysisStatus; confidence: float | None


def filings(snapshot: AsOfSnapshot, instrument: str, period_type: str | None = None) -> tuple[dict, ...] | FundamentalAnalysis:
    rows=[]
    for item in snapshot.observations:
        if item.instrument.id != instrument or item.kind is not ObservationKind.FUNDAMENTAL: continue
        if item.validation is None or item.validation.status is not ValidationStatus.VALID: return FundamentalAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INVALID_DATA,None)
        p=item.payload
        if p.get("publication_timestamp") is None or p.get("period_end") is None: return FundamentalAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INVALID_DATA,None)
        published=_date(p["publication_timestamp"])
        if published > snapshot.as_of_timestamp: return FundamentalAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INVALID_DATA,None)
        if period_type is None or p.get("period_type") == period_type: rows.append({**p,"_id":item.id})
    rows.sort(key=lambda p: (_date(p["period_end"]), p["_id"]))
    return tuple(rows)


def five_year_trend(snapshot, instrument, rules):
    r=filings(snapshot,instrument,"annual")
    if isinstance(r,FundamentalAnalysis): return r
    if len(r)<6: return _insufficient(r)
    r=r[-6:]; metrics=("revenue","ebitda","pat","eps")
    values=[]
    for m in metrics:
        if any(not _positive(x.get(m)) for x in (r[0],r[-1])): return _insufficient(r)
        values.append((f"{m}_cagr",str(pow(float(r[-1][m])/float(r[0][m]),1/5)-1)))
    growth=[float(v) for _,v in values]; state="ACCELERATING" if min(growth)>=rules.healthy_growth else "DETERIORATING" if max(growth)<=rules.weak_growth else "HEALTHY" if sum(growth)/4>0 else "WEAK"
    return _result(state,values,r)


def return_ratios(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"annual")
    if isinstance(r,FundamentalAnalysis): return r
    if not r:return _insufficient(r)
    b=r[-1]; a=r[-2] if len(r)>1 else None
    if b.get("pat") is None or b.get("ebit") is None or b.get("total_equity") is None:return _insufficient(r)
    equity_values=[float(x["total_equity"]) for x in (a,b) if x is not None and x.get("total_equity") is not None]
    equity=sum(equity_values)/len(equity_values)
    if equity<=0:return _insufficient(r)
    roe=float(b["pat"])/equity; equity_basis="average beginning/end equity" if len(equity_values)==2 else "ending equity (average unavailable)"
    method=rules.roce_method
    if method=="equity_debt_cash_v1":
        required=("total_equity","total_debt","cash")
        if any(b.get(x) is None for x in required):return _insufficient(r)
        caps=[float(x["total_equity"])+float(x["total_debt"])-float(x["cash"]) for x in (a,b) if x is not None and all(x.get(k) is not None for k in required)]
        label="equity + interest-bearing debt - cash"
    elif method=="assets_current_liabilities_v1":
        required=("total_assets","current_liabilities")
        if any(b.get(x) is None for x in required):return _insufficient(r)
        caps=[float(x["total_assets"])-float(x["current_liabilities"]) for x in (a,b) if x is not None and all(x.get(k) is not None for k in required)]
        label="total assets - current liabilities"
    else: return _insufficient(r)
    capital=sum(caps)/len(caps) if caps else 0
    if capital<=0:return _insufficient(r)
    roce=float(b["ebit"])/capital; capital_basis="average beginning/end capital employed" if len(caps)==2 else "ending capital employed (average unavailable)"
    return _result("HEALTHY" if min(roe,roce)>=rules.return_ratio_healthy else "MODERATE",(("roe",str(roe)),("roe_basis",equity_basis),("roce",str(roce)),("ebit",str(b["ebit"])),("capital_employed",str(capital)),("roce_method",method),("denominator_methodology",label),("capital_basis",capital_basis),("period",str(b["period_end"]))),r[-2:])


def cash_flow(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"annual")
    if isinstance(r,FundamentalAnalysis): return r
    if not r or any(x.get("operating_cash_flow") is None or x.get("capex") is None or x.get("pat") is None for x in r[-2:]):return _insufficient(r)
    b=r[-1]; fcf=float(b["operating_cash_flow"])-float(b["capex"]); state="HEALTHY" if float(b["operating_cash_flow"])>0 and fcf>0 else "WEAK"
    return _result(state,(("ocf",str(b["operating_cash_flow"])),("fcf",str(fcf)),("ocf_to_pat",str(float(b["operating_cash_flow"])/float(b["pat"])))),r)


def leverage(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"annual")
    if isinstance(r,FundamentalAnalysis): return r
    if not r:return _insufficient(r)
    b=r[-1]; needed=("total_debt","total_equity","cash","ebit","interest_expense")
    if any(b.get(x) is None for x in needed) or float(b["total_equity"])<=0 or float(b["interest_expense"])<=0:return _insufficient(r)
    de=float(b["total_debt"])/float(b["total_equity"]); coverage=float(b["ebit"])/float(b["interest_expense"]); state="STRESSED" if coverage<rules.coverage_stressed else "ELEVATED" if de>rules.leverage_elevated else "HEALTHY"
    return _result(state,(("debt_equity",str(de)),("net_debt",str(float(b["total_debt"])-float(b["cash"]))),("interest_coverage",str(coverage))),r)


def working_capital(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"annual")
    if isinstance(r,FundamentalAnalysis): return r
    if not r:return _insufficient(r)
    b=r[-1]; a=r[-2] if len(r)>1 else None
    if b.get("not_applicable_working_capital"): return _result("NOT_APPLICABLE",(),r)
    if b.get("revenue") is None or b.get("receivables") is None or float(b["revenue"])<=0:return _insufficient(r)
    days=rules.annual_period_days if b.get("period_type")=="annual" else rules.quarterly_period_days
    def average(name):
        values=[float(x[name]) for x in (a,b) if x is not None and x.get(name) is not None]
        return (sum(values)/len(values), "average beginning/end balance" if len(values)==2 else "ending balance (average unavailable)") if values else (None,"unavailable")
    rec,rec_basis=average("receivables"); dso=rec/float(b["revenue"])*days
    details=[("receivable_days",str(dso)),("receivable_basis",rec_basis),("period_days",str(days))]
    if b.get("cogs") is None or float(b["cogs"])<=0:
        details += [("inventory_days","UNAVAILABLE: COGS required"),("payable_days","UNAVAILABLE: COGS required"),("ccc","PARTIAL: COGS unavailable")]
        return FundamentalAnalysis("PARTIAL",tuple(details),tuple(x["_id"] for x in r[-2:]),AnalysisStatus.VALID,.5)
    inv,inv_basis=average("inventory"); pay,pay_basis=average("payables")
    if inv is None or pay is None:return FundamentalAnalysis("PARTIAL",tuple(details+[("inventory_days","UNAVAILABLE"),("payable_days","UNAVAILABLE"),("ccc","PARTIAL")]),tuple(x["_id"] for x in r[-2:]),AnalysisStatus.VALID,.5)
    dio=inv/float(b["cogs"])*days; dpo=pay/float(b["cogs"])*days; ccc=dso+dio-dpo
    return _result("HEALTHY",tuple(details)+(("inventory_days",str(dio)),("inventory_basis",inv_basis),("payable_days",str(dpo)),("payable_basis",pay_basis),("ccc",str(ccc)),("ccc_formula","DSO + DIO - DPO")),r[-2:])


def ownership(snapshot,instrument,rules): return _holding(snapshot,instrument,("promoter_holding","promoter_pledge"),"OWNERSHIP")
def institutional(snapshot,instrument,rules): return _holding(snapshot,instrument,("fii_holding","dii_holding","mutual_fund_holding"),"INSTITUTIONAL")
def _holding(snapshot,instrument,keys,label):
    r=filings(snapshot,instrument)
    if isinstance(r,FundamentalAnalysis): return r
    if len(r)<2 or any(x.get(k) is None for x in r[-2:] for k in keys):return _insufficient(r)
    a,b=r[-2:]; changes=[float(b[k])-float(a[k]) for k in keys]; state="INCREASING" if min(changes)>0 else "DECREASING" if max(changes)<0 else "STABLE" if all(x==0 for x in changes) else "MIXED"
    details=tuple((k,str(b[k])) for k in keys)+tuple((f"{k}_change",str(float(b[k])-float(a[k]))) for k in keys)+(("data_timestamp",str(b["publication_timestamp"])),("semantic",f"periodic {label.lower()} evidence; not intraday flow"))
    return _result(state,details,r[-2:])


def earnings_acceleration(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"quarterly")
    if isinstance(r,FundamentalAnalysis): return r
    if len(r)<5:return _insufficient(r)
    q=r[-5:]; growth=[float(q[i]["revenue"])/float(q[i-4]["revenue"])-1 for i in range(4,5) if _positive(q[i].get("revenue")) and _positive(q[i-4].get("revenue"))]
    if not growth:return _insufficient(r)
    return _result("ACCELERATING" if growth[-1]>=rules.healthy_growth else "DETERIORATING" if growth[-1]<=rules.weak_growth else "STABLE",(("revenue_yoy",str(growth[-1])),("quality","reported growth only; organic/one-off quality unassessed")),q)


def latest_quarter(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"quarterly")
    if isinstance(r,FundamentalAnalysis): return r
    if len(r)<5:return _insufficient(r)
    b,prior,year=r[-1],r[-2],r[-5]; details=[]
    for m in ("revenue","ebitda","pat","eps"):
        if _positive(b.get(m)) and _positive(prior.get(m)) and _positive(year.get(m)): details += [(f"{m}_qoq",str(float(b[m])/float(prior[m])-1)),(f"{m}_yoy",str(float(b[m])/float(year[m])-1))]
    return _result("REPORTED",tuple(details),r[-5:]) if details else _insufficient(r)


def margins(snapshot,instrument,rules):
    r=filings(snapshot,instrument,"quarterly")
    if isinstance(r,FundamentalAnalysis): return r
    if len(r)<5:return _insufficient(r)
    b,year=r[-1],r[-5]
    if not all(_positive(x.get("revenue")) and x.get("ebitda") is not None for x in (b,year)):return _insufficient(r)
    change=float(b["ebitda"])/float(b["revenue"])-float(year["ebitda"])/float(year["revenue"]); state="EXPANDING" if change>=rules.margin_change else "CONTRACTING" if change<=-rules.margin_change else "STABLE"
    return _result(state,(("ebitda_margin",str(float(b["ebitda"])/float(b["revenue"]))),("ebitda_margin_yoy_change",str(change))),r[-5:])


def order_book(snapshot,instrument,rules):
    r=filings(snapshot,instrument)
    if isinstance(r,FundamentalAnalysis): return r
    if not r:return _insufficient(r)
    b=r[-1]
    if b.get("not_applicable_order_book"):return _result("NOT_APPLICABLE",(),r)
    if any(b.get(k) is None for k in ("order_book","order_inflow","revenue")) or float(b["revenue"])<=0:return _insufficient(r)
    return _result("GROWING" if len(r)>1 and float(b["order_book"])>float(r[-2].get("order_book",b["order_book"])) else "DECLINING",(("order_book",str(b["order_book"])),("order_inflow",str(b["order_inflow"])),("book_to_bill",str(float(b["order_inflow"])/float(b["revenue"])))),r[-2:])


def _result(state,details,rows): return FundamentalAnalysis(state,tuple(details),tuple(x["_id"] for x in rows),AnalysisStatus.VALID,1.0)
def _insufficient(rows): return FundamentalAnalysis("INSUFFICIENT_DATA",(),tuple(x["_id"] for x in rows),AnalysisStatus.INSUFFICIENT_DATA,None)
def _positive(value): return isinstance(value,(int,float)) and not isinstance(value,bool) and value>0
def _date(value): return value if isinstance(value,datetime) else datetime.fromisoformat(value)
