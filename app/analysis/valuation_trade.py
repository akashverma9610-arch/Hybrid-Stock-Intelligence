from __future__ import annotations

from dataclasses import dataclass

from app.analysis.fundamentals import filings
from app.analysis.models import AnalysisStatus
from app.analysis.series import closes, price_bar_series

@dataclass(frozen=True, slots=True)
class ValuationRules:
    attractive_pe: float; expensive_pe: float; peg_growth_method: str = "reported_revenue_cagr_v1"
@dataclass(frozen=True, slots=True)
class TradeRules:
    base_period:int; max_base_depth:float; entry_tolerance:float; stop_buffer:float; minimum_r:float
    cup_min_duration:int=8; cup_max_depth:float=.35; cup_handle_duration:int=2; cup_max_handle_depth:float=.12; cup_upper_portion:float=.5; cup_recovery_tolerance:float=.05; require_prior_advance:bool=False; ascending_min_pullbacks:int=2; ascending_max_depth:float=.2; ascending_min_spacing:int=1
@dataclass(frozen=True, slots=True)
class PlanAnalysis:
    state:str; details:tuple[tuple[str,str],...]; input_ids:tuple[str,...]; status:AnalysisStatus; confidence:float|None

def valuation(market, financial, instrument, rules):
    s=price_bar_series(market,instrument); f=filings(financial,instrument,"annual")
    if s.status is not AnalysisStatus.VALID or not s.bars:return _insufficient(s.observation_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA)
    if not isinstance(f,tuple):return _insufficient(s.observation_ids,f.status)
    if not f:return _insufficient(s.observation_ids)
    b=f[-1]; price=closes(s)[-1]; details=[("price",str(price)),("comparison_universe",str(b.get("valuation_comparison_universe","none")))]
    eps=b.get("eps"); shares=b.get("shares_outstanding"); ebitda=b.get("ebitda"); equity=b.get("total_equity")
    if eps is not None and float(eps)>0: details.append(("pe",str(price/float(eps))))
    else: details.append(("pe","UNINTERPRETABLE: non-positive or missing EPS"))
    if b.get("forward_eps") is not None and float(b["forward_eps"])>0: details.append(("forward_pe",str(price/float(b["forward_eps"]))))
    else: details.append(("forward_pe","UNAVAILABLE: explicit forward EPS required"))
    growth=b.get("configured_growth_rate")
    pe=price/float(eps) if eps is not None and float(eps)>0 else None
    if pe is not None and growth is not None and float(growth)>0: details += [("peg",str(pe/(float(growth)*100))),("peg_growth_method",rules.peg_growth_method)]
    else: details.append(("peg","UNAVAILABLE: configured positive growth required"))
    if shares is not None and ebitda is not None and float(ebitda)>0:
        ev=price*float(shares)+float(b.get("total_debt",0))-float(b.get("cash",0)); details += [("ev",str(ev)),("ev_ebitda",str(ev/float(ebitda)))]
    else: details.append(("ev_ebitda","UNAVAILABLE: shares and positive EBITDA required"))
    if shares is not None and equity is not None and float(equity)>0: details.append(("pb",str(price*float(shares)/float(equity))))
    else: details.append(("pb","UNAVAILABLE: shares and positive book value required"))
    state="UNINTERPRETABLE" if pe is None else "ATTRACTIVE" if pe<=rules.attractive_pe else "EXPENSIVE" if pe>=rules.expensive_pe else "REASONABLE"
    return PlanAnalysis(state,tuple(details),s.observation_ids+tuple(x["_id"] for x in f[-1:]),AnalysisStatus.VALID,1.0)

def base_pattern(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<rules.base_period:return _insufficient(s.observation_ids)
    all_values=closes(s); values=all_values[-rules.base_period:]; boundary=values[:-1]; resistance=max(boundary); support=min(boundary); depth=(resistance-support)/resistance if resistance else 0
    ranges=[float(x.payload["high"])-float(x.payload["low"]) for x in s.bars[-rules.base_period:]]; contraction=ranges[-1]<=sum(ranges[:-1])/max(1,len(ranges)-1)
    candidates=[]
    cup=_cup_handle(all_values,rules)
    if cup: candidates.append(("CUP_AND_HANDLE",cup))
    ascending=_ascending_base(all_values,rules)
    if ascending: candidates.append(("ASCENDING_BASE",ascending))
    if not candidates and depth>rules.max_base_depth:return PlanAnalysis("NO_VALID_BASE",(("depth",str(depth)),),s.observation_ids,AnalysisStatus.VALID,.7)
    # Explicit precedence: completed cup/handle, then ascending base, then
    # VCP, then flat base. All matched candidates remain in measurements.
    state="CUP_AND_HANDLE" if cup else "ASCENDING_BASE" if ascending else "VCP" if contraction else "FLAT_BASE"
    selected=cup or ascending or {"support":support,"resistance":resistance,"depth":depth,"duration":rules.base_period}
    quality="HIGH" if contraction and depth<=rules.max_base_depth/2 else "ACCEPTABLE" if depth<=rules.max_base_depth else "POOR"
    details=(("duration",str(selected.get("duration",rules.base_period))),("depth",str(selected.get("depth",depth))),("resistance",str(selected["resistance"])),("support",str(selected["support"])),("base_height",str(float(selected["resistance"])-float(selected["support"]))),("volatility_contraction",str(contraction)),("support_consistency",str(selected.get("support_consistency","base boundary"))),("pivot_clarity",str(selected.get("pivot_clarity",True))),("volume_behavior","UNAVAILABLE unless valid volume is supplied"),("breakout_readiness",str(all_values[-1]>=float(selected["resistance"]))),("pattern_quality",quality),("resolution_policy","CUP_AND_HANDLE > ASCENDING_BASE > VCP > FLAT_BASE"),("candidate_patterns",",".join(name for name,_ in candidates) or state))
    return PlanAnalysis(state,details,s.observation_ids,AnalysisStatus.VALID,.9)

def _cup_handle(v,r):
    if len(v)<r.cup_min_duration+r.cup_handle_duration:return None
    body=v[-(r.cup_min_duration+r.cup_handle_duration):]; cup=body[:-r.cup_handle_duration]; handle=body[-r.cup_handle_duration:]
    peak=cup[0]; trough=min(cup); index=cup.index(trough); recovery=cup[-1]; depth=(peak-trough)/peak if peak else 1
    prior_ok=not r.require_prior_advance or (len(v)>len(body) and v[-len(body)-1]<peak)
    rounded=index>=2 and index<=len(cup)-3 and all(cup[i]>=trough for i in range(index,len(cup)))
    handle_depth=(recovery-min(handle))/recovery if recovery else 1; upper=trough+(peak-trough)*r.cup_upper_portion
    if not (prior_ok and rounded and depth<=r.cup_max_depth and recovery>=peak*(1-r.cup_recovery_tolerance) and min(handle)>=upper and handle_depth<=r.cup_max_handle_depth):return None
    return {"duration":len(body),"depth":depth,"support":min(handle),"resistance":peak,"handle_duration":len(handle),"handle_depth":handle_depth,"support_consistency":"upper-half handle","pivot_clarity":True}

def _ascending_base(v,r):
    if len(v)<max(r.base_period,5):return None
    window=v[-r.base_period:]; lows=[]
    for i in range(1,len(window)-1):
        if window[i]<=window[i-1] and window[i]<=window[i+1]: lows.append((i,window[i]))
    if len(lows)<r.ascending_min_pullbacks:return None
    spacing=all(lows[i][0]-lows[i-1][0]>=r.ascending_min_spacing for i in range(1,len(lows)))
    higher=all(lows[i][1]>lows[i-1][1] for i in range(1,len(lows)))
    resistance=max(window[:-1]); support=lows[-1][1]; depth=(resistance-min(x[1] for x in lows))/resistance if resistance else 1
    if not (spacing and higher and depth<=r.ascending_max_depth):return None
    return {"duration":len(window),"depth":depth,"support":support,"resistance":resistance,"pullbacks":len(lows),"support_consistency":"progressively higher lows","pivot_clarity":True}

def pullback(snapshot,instrument,rules):
    base=base_pattern(snapshot,instrument,rules)
    if base.status is not AnalysisStatus.VALID or base.state=="NO_VALID_BASE":return _insufficient(base.input_ids)
    d=dict(base.details); close=closes(price_bar_series(snapshot,instrument))[-1]; support=float(d["support"]); tolerance=rules.entry_tolerance*support
    state="HIGH_QUALITY" if close>=support and close<=support+tolerance else "BROKEN" if close<support else "MIXED"
    return PlanAnalysis(state,base.details+(("close",str(close)),("support_method","base boundary"),("support_timestamp",snapshot.as_of_timestamp.isoformat())),base.input_ids,AnalysisStatus.VALID,.9 if state=="HIGH_QUALITY" else .6)

def aggressive_entry(snapshot,instrument,rules):
    base=base_pattern(snapshot,instrument,rules)
    if base.state in {"NO_VALID_BASE","INSUFFICIENT_DATA"}:return _insufficient(base.input_ids)
    d=dict(base.details); price=float(d["resistance"])*(1-rules.entry_tolerance)
    return PlanAnalysis("CANDIDATE",(("entry",str(price)),("methodology","tight-base early entry"),("required_conditions","support holds; no execution implied"),("invalidation",f"close below {d['support']}")),base.input_ids,AnalysisStatus.VALID,.6)

def confirmation_entry(snapshot,instrument,rules):
    base=base_pattern(snapshot,instrument,rules)
    if base.state in {"NO_VALID_BASE","INSUFFICIENT_DATA"}:return _insufficient(base.input_ids)
    resistance=float(dict(base.details)["resistance"]); close=closes(price_bar_series(snapshot,instrument))[-1]
    if close<=resistance:return PlanAnalysis("NO_VALID_ENTRY",(("resistance",str(resistance)),("condition","close above resistance required")),base.input_ids,AnalysisStatus.VALID,.5)
    return PlanAnalysis("CANDIDATE",(("entry",str(close)),("methodology","confirmed close above base resistance"),("confirmation_condition",f"close > {resistance}")),base.input_ids,AnalysisStatus.VALID,.9)

def retest_entry(snapshot,instrument,rules):
    p=pullback(snapshot,instrument,rules)
    if p.state!="HIGH_QUALITY":return _insufficient(p.input_ids)
    support=dict(p.details)["support"]
    return PlanAnalysis("CANDIDATE",(("entry",support),("methodology","validated base-support retest"),("allowed_tolerance",str(rules.entry_tolerance)),("confirmation_requirement","support remains intact")),p.input_ids,AnalysisStatus.VALID,.8)

def structural_stop(snapshot,instrument,rules):
    p=pullback(snapshot,instrument,rules)
    if p.state not in {"HIGH_QUALITY","MIXED"}:return _insufficient(p.input_ids)
    support=float(dict(p.details)["support"]); stop=support*(1-rules.stop_buffer)
    return PlanAnalysis("CANDIDATE",(("stop",str(stop)),("basis","below base support"),("buffer",str(rules.stop_buffer)),("invalidation",f"close below {support}")),p.input_ids,AnalysisStatus.VALID,.8)

def targets(snapshot,instrument,rules):
    base=base_pattern(snapshot,instrument,rules)
    if base.state in {"NO_VALID_BASE","INSUFFICIENT_DATA"}:return _insufficient(base.input_ids)
    d=dict(base.details); resistance=float(d["resistance"]); height=resistance-float(d["support"])
    if height<=0:return _insufficient(base.input_ids)
    return PlanAnalysis("CANDIDATE",(("t1",str(resistance+height)),("t2",str(resistance+2*height)),("extended",str(resistance+3*height)),("methodology","base-height measured move")),base.input_ids,AnalysisStatus.VALID,.7)

def risk_reward(entry,stop,target, rules):
    if entry is None or stop is None or target is None or entry<=stop:return _insufficient(())
    risk=entry-stop; reward=target-entry; r=reward/risk
    return PlanAnalysis("ACCEPTABLE" if r>=rules.minimum_r else "BELOW_THRESHOLD",(("risk",str(risk)),("reward_t1",str(reward)),("r_t1",str(r)),("minimum_r",str(rules.minimum_r))),(),AnalysisStatus.VALID,1.0)

def invalidation(snapshot,instrument,rules):
    stop=structural_stop(snapshot,instrument,rules)
    if stop.status is not AnalysisStatus.VALID:return _insufficient(stop.input_ids)
    return PlanAnalysis("PRICE_STRUCTURE_INVALIDATION",(("condition",dict(stop.details)["invalidation"]),("machine_testable","true")),stop.input_ids,AnalysisStatus.VALID,.8)
def _insufficient(ids,status=AnalysisStatus.INSUFFICIENT_DATA):return PlanAnalysis("INSUFFICIENT_DATA",(),tuple(ids),status,None)
