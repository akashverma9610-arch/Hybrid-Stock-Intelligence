from __future__ import annotations
from dataclasses import dataclass
from app.analysis.models import AnalysisStatus
from app.analysis.series import closes, price_bar_series

@dataclass(frozen=True, slots=True)
class LiquidityRules:
    equal_tolerance:float; min_touches:int; rvol_high:float; wide_range_factor:float
@dataclass(frozen=True, slots=True)
class LiquidityPool:
    side:str; level:float; origin:str; first_seen:str; last_confirmed:str; touches:int; input_ids:tuple[str,...]
@dataclass(frozen=True, slots=True)
class MicroAnalysis:
    state:str; details:tuple[tuple[str,str],...]; input_ids:tuple[str,...]; status:AnalysisStatus; confidence:float|None

def pools(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<rules.min_touches:return _bad(s.observation_ids,s.status)
    found=[]
    for side,key in (("BUY_SIDE","high"),("SELL_SIDE","low")):
        groups=[]
        for bar in s.bars:
            value=float(bar.payload[key]); group=next((g for g in groups if abs(value-g[0])/g[0]<=rules.equal_tolerance),None)
            if group: group[1].append(bar)
            else: groups.append([value,[bar]])
        for value,bars in groups:
            if len(bars)>=rules.min_touches: found.append(LiquidityPool(side,sum(float(x.payload[key]) for x in bars)/len(bars),"equal highs" if side=="BUY_SIDE" else "equal lows",bars[0].provenance.market_timestamp.isoformat(),bars[-1].provenance.market_timestamp.isoformat(),len(bars),tuple(x.id for x in bars)))
    if not found:return MicroAnalysis("INSUFFICIENT_DATA",(("reason","no configured repeated liquidity levels"),),s.observation_ids,AnalysisStatus.INSUFFICIENT_DATA,None)
    details=tuple((f"{x.side}_{i}",f"level={x.level};origin={x.origin};touches={x.touches};first={x.first_seen};last={x.last_confirmed}") for i,x in enumerate(found))
    return MicroAnalysis("MAPPED",details,tuple(x for p in found for x in p.input_ids),AnalysisStatus.VALID,min(1.0,.4+.1*len(found)))

def stop_clusters(snapshot,instrument,rules):
    p=pools(snapshot,instrument,rules)
    if p.status is not AnalysisStatus.VALID:return _bad(p.input_ids,p.status)
    items=[]
    for k,v in p.details:
        level=v.split(";")[0].split("=")[1]; touches=int(v.split("touches=")[1].split(";")[0]); significance="MAJOR" if touches>=3 else "MODERATE"
        items.append((k,f"inferred stop-cluster proxy; level={level};significance={significance};actual_quantity=UNOBSERVED"))
    return MicroAnalysis("MAPPED",tuple(items),p.input_ids,AnalysisStatus.VALID,p.confidence)

def events(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument); p=pools(snapshot,instrument,rules)
    if s.status is not AnalysisStatus.VALID or p.status is not AnalysisStatus.VALID:return _bad(s.observation_ids+p.input_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else p.status)
    bar=s.bars[-1]; high=float(bar.payload["high"]); low=float(bar.payload["low"]); close=float(bar.payload["close"]); found=[]
    for key,value in p.details:
        side=key.rsplit("_",1)[0]; level=float(value.split(";")[0].split("=")[1])
        if side=="BUY_SIDE" and high>level:
            found.append(("event","SWEEP_AND_RECLAIM" if close<level else "BREAKOUT_ACCEPTED",))
        if side=="SELL_SIDE" and low<level:
            found.append(("event","SWEEP_AND_RECLAIM" if close>level else "BREAKDOWN_ACCEPTED",))
    return MicroAnalysis(found[-1][1] if found else "NO_EVENT",tuple(found)+(("event_timestamp",bar.provenance.market_timestamp.isoformat()),("absorption","UNAVAILABLE: no order-book data; proxy only")),s.observation_ids,AnalysisStatus.VALID,.8 if found else .6)

def bull_trap(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument); p=pools(snapshot,instrument,rules)
    if s.status is not AnalysisStatus.VALID or p.status is not AnalysisStatus.VALID:return _bad(s.observation_ids+p.input_ids,s.status)
    bar=s.bars[-1]; high=float(bar.payload["high"]); close=float(bar.payload["close"])
    levels=[float(v.split(";")[0].split("=")[1]) for k,v in p.details if k.startswith("BUY_SIDE")]
    swept=[x for x in levels if high>x]
    state="CONFIRMED_BULL_TRAP" if any(close<x for x in swept) else "POSSIBLE_BULL_TRAP" if swept else "NO_BULL_TRAP"
    return MicroAnalysis(state,(("methodology","buy-side break then return below resistance"),),s.observation_ids,AnalysisStatus.VALID,.8 if swept else .6)
def bear_trap(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument); p=pools(snapshot,instrument,rules)
    if s.status is not AnalysisStatus.VALID or p.status is not AnalysisStatus.VALID:return _bad(s.observation_ids+p.input_ids,s.status)
    bar=s.bars[-1]; low=float(bar.payload["low"]); close=float(bar.payload["close"])
    levels=[float(v.split(";")[0].split("=")[1]) for k,v in p.details if k.startswith("SELL_SIDE")]
    swept=[x for x in levels if low<x]
    state="CONFIRMED_BEAR_TRAP" if any(close>x for x in swept) else "POSSIBLE_BEAR_TRAP" if swept else "NO_BEAR_TRAP"
    return MicroAnalysis(state,(("methodology","sell-side break then reclaim support"),),s.observation_ids,AnalysisStatus.VALID,.8 if swept else .6)

def wyckoff(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument); e=events(snapshot,instrument,rules)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<3:return _bad(s.observation_ids,s.status)
    c=closes(s); change=c[-1]-c[0]; span=max(c)-min(c); state="MARKUP" if change>0 and abs(change)>span*.5 else "MARKDOWN" if change<0 and abs(change)>span*.5 else "ACCUMULATION" if e.state=="SWEEP_AND_RECLAIM" and change>=0 else "DISTRIBUTION" if e.state=="SWEEP_AND_RECLAIM" else "UNCLASSIFIED"
    return MicroAnalysis(state,(("trend_change",str(change)),("event",e.state),("methodology","transparent price/range/event approximation")),s.observation_ids,AnalysisStatus.VALID,.6)

def accumulation_distribution(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument); e=events(snapshot,instrument,rules); w=wyckoff(snapshot,instrument,rules)
    if s.status is not AnalysisStatus.VALID:return _bad(s.observation_ids,s.status)
    c=closes(s); score=(1 if c[-1]>c[0] else -1)+(1 if w.state in {"MARKUP","ACCUMULATION"} else -1 if w.state in {"MARKDOWN","DISTRIBUTION"} else 0)+(1 if e.state=="BREAKOUT_ACCEPTED" else -1 if e.state=="BREAKDOWN_ACCEPTED" else 0)
    state="ACCUMULATION" if score>=2 else "POSSIBLE_ACCUMULATION" if score==1 else "DISTRIBUTION" if score<=-2 else "POSSIBLE_DISTRIBUTION" if score==-1 else "NEUTRAL"
    return MicroAnalysis(state,(("observable_score",str(score)),("event",e.state),("wyckoff",w.state),("semantic","observable proxy; not institutional flow")),s.observation_ids,AnalysisStatus.VALID,.7)
def smart_money(snapshot,instrument,rules):
    a=accumulation_distribution(snapshot,instrument,rules)
    mapping={"ACCUMULATION":"STRONG_ACCUMULATION_PROXY","POSSIBLE_ACCUMULATION":"ACCUMULATION_PROXY","DISTRIBUTION":"STRONG_DISTRIBUTION_PROXY","POSSIBLE_DISTRIBUTION":"DISTRIBUTION_PROXY"}
    return MicroAnalysis(mapping.get(a.state,a.state),a.details+(("semantic","possible observable smart-money proxy; no institutional identity"),),a.input_ids,a.status,a.confidence)

def volume_climax(snapshot,instrument,rules):
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<3 or any("volume" not in x.payload for x in s.bars):return _bad(s.observation_ids,s.status)
    vols=[float(x.payload["volume"]) for x in s.bars]; ranges=[float(x.payload["high"])-float(x.payload["low"]) for x in s.bars]; rvol=vols[-1]/(sum(vols[:-1])/len(vols[:-1])); wide=ranges[-1]>=sum(ranges[:-1])/len(ranges[:-1])*rules.wide_range_factor
    last=s.bars[-1]; close=float(last.payload["close"]); position=(close-float(last.payload["low"]))/ranges[-1] if ranges[-1] else .5
    state="BUYING_CLIMAX_PROXY" if rvol>=rules.rvol_high and wide and position>.8 else "SELLING_CLIMAX_PROXY" if rvol>=rules.rvol_high and wide and position<.2 else "HIGH_VOLUME_NO_CLEAR_SIGNAL" if rvol>=rules.rvol_high else "NO_CLIMAX"
    return MicroAnalysis(state,(("rvol",str(rvol)),("wide_range",str(wide)),("close_location",str(position)),("semantic","price-volume proxy; not institutional activity")),s.observation_ids,AnalysisStatus.VALID,.8 if "CLIMAX" in state else .6)
def _bad(ids,status):return MicroAnalysis("INSUFFICIENT_DATA",(),tuple(ids),AnalysisStatus.INVALID_DATA if status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA,None)
