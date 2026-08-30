from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from app.analysis.series import closes, price_bar_series
from app.analysis.models import AnalysisStatus
from app.domain.models import AsOfSnapshot

@dataclass(frozen=True, slots=True)
class SimpleAnalysis:
    state: str; details: tuple[tuple[str,str],...]; input_ids: tuple[str,...]; status: AnalysisStatus; confidence: float|None

def sector_health(snapshot: AsOfSnapshot, sector: str, benchmark: str, lookback:int, strong:float, weak:float)->SimpleAnalysis:
    s,b=price_bar_series(snapshot,sector),price_bar_series(snapshot,benchmark)
    if s.status is not AnalysisStatus.VALID or b.status is not AnalysisStatus.VALID or len(s.bars)<lookback+1 or len(b.bars)<lookback+1:
        status=AnalysisStatus.INVALID_DATA if AnalysisStatus.INVALID_DATA in (s.status,b.status) else AnalysisStatus.INSUFFICIENT_DATA
        return SimpleAnalysis("INSUFFICIENT_DATA",(),s.observation_ids+b.observation_ids,status,None)
    sr=closes(s)[-1]/closes(s)[-1-lookback]-1;br=closes(b)[-1]/closes(b)[-1-lookback]-1;ex=sr-br
    state="STRONG" if ex>=strong else "WEAK" if ex<=weak else "HEALTHY" if sr>0 else "WEAKENING" if sr<0 else "NEUTRAL"
    return SimpleAnalysis(state,(("sector_return",str(sr)),("benchmark_return",str(br)),("excess",str(ex))),s.observation_ids+b.observation_ids,AnalysisStatus.VALID,1.0)

def sector_rotation(snapshot: AsOfSnapshot, sector: str, benchmark: str, lookback:int, strong:float, weak:float)->SimpleAnalysis:
    health=sector_health(snapshot,sector,benchmark,lookback,strong,weak)
    phase={"STRONG":"ROTATING_IN","HEALTHY":"ACCUMULATING","WEAKENING":"ROTATING_OUT","WEAK":"DISTRIBUTING"}.get(health.state,"NEUTRAL")
    return SimpleAnalysis(phase,health.details+(("classification","observable price/RS proxy; inference only, not fund flow"),),health.input_ids,health.status,health.confidence)

def volume_rvol(snapshot:AsOfSnapshot,instrument:str,lookback:int,high:float,low:float)->SimpleAnalysis:
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<lookback+1 or any("volume" not in x.payload for x in s.bars):return SimpleAnalysis("INSUFFICIENT_DATA",(),s.observation_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA,None)
    vols=[float(x.payload["volume"]) for x in s.bars];r=vols[-1]/(sum(vols[-lookback-1:-1])/lookback)
    return SimpleAnalysis("EXPANSION" if r>=high else "CONTRACTION" if r<=low else "NORMAL",(("rvol",str(r)),),s.observation_ids,AnalysisStatus.VALID,1.0)

def obv(snapshot:AsOfSnapshot,instrument:str,lookback:int)->SimpleAnalysis:
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or len(s.bars)<lookback+1 or any("volume" not in x.payload for x in s.bars):return SimpleAnalysis("INSUFFICIENT_DATA",(),s.observation_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA,None)
    c=closes(s);v=[float(x.payload["volume"]) for x in s.bars];values=[0.0]
    for i in range(1,len(c)): values.append(values[-1] + (v[i] if c[i]>c[i-1] else -v[i] if c[i]<c[i-1] else 0))
    price_change=c[-1]-c[-1-lookback]; obv_change=values[-1]-values[-1-lookback]
    # This is a price/volume divergence proxy only.  It intentionally makes no
    # claim about institutional participation or underlying fund flows.
    state="BULLISH_DIVERGENCE" if price_change<0 and obv_change>0 else "BEARISH_DIVERGENCE" if price_change>0 and obv_change<0 else "BULLISH_CONFIRMATION" if price_change>0 and obv_change>0 else "BEARISH_CONFIRMATION" if price_change<0 and obv_change<0 else "NEUTRAL"
    return SimpleAnalysis(state,(("obv",str(values[-1])),("obv_change",str(obv_change)),("price_change",str(price_change)),("interpretation","price-volume proxy; not institutional accumulation")),s.observation_ids,AnalysisStatus.VALID,1.0)

def vwap(snapshot:AsOfSnapshot,instrument:str)->SimpleAnalysis:
    s=price_bar_series(snapshot,instrument)
    if s.status is not AnalysisStatus.VALID or any("volume" not in x.payload for x in s.bars):return SimpleAnalysis("INSUFFICIENT_DATA",(("value_area","UNAVAILABLE"),),s.observation_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA,None)
    denom=sum(float(x.payload["volume"]) for x in s.bars)
    if not denom:return SimpleAnalysis("INSUFFICIENT_DATA",(("value_area","UNAVAILABLE"),),s.observation_ids,AnalysisStatus.INSUFFICIENT_DATA,None)
    value=sum(((float(x.payload["high"])+float(x.payload["low"])+float(x.payload["close"]))/3)*float(x.payload["volume"]) for x in s.bars)/denom
    state="ACCEPTANCE_ABOVE" if closes(s)[-1]>value else "ACCEPTANCE_BELOW" if closes(s)[-1]<value else "MIXED"
    return SimpleAnalysis(state,(("vwap",str(value)),("value_area","UNAVAILABLE")),s.observation_ids,AnalysisStatus.VALID,1.0)

def ichimoku(snapshot:AsOfSnapshot,instrument:str,tenkan:int,kijun:int,span_b:int,displacement:int)->SimpleAnalysis:
    s=price_bar_series(snapshot,instrument);need=max(kijun,span_b)+displacement
    if s.status is not AnalysisStatus.VALID or len(s.bars)<need:return SimpleAnalysis("INSUFFICIENT_DATA",(),s.observation_ids,AnalysisStatus.INVALID_DATA if s.status is AnalysisStatus.INVALID_DATA else AnalysisStatus.INSUFFICIENT_DATA,None)
    def mid(p,offset=0):
        z=s.bars[-p-offset:len(s.bars)-offset if offset else None];return (max(float(x.payload['high']) for x in z)+min(float(x.payload['low']) for x in z))/2
    # The cloud visible at the current bar is projected from `displacement`
    # bars earlier.  Chikou compares today's close with that same historical bar.
    t,k,b=mid(tenkan,displacement),mid(kijun,displacement),mid(span_b,displacement);a=(t+k)/2;close=closes(s)[-1]
    state="STRONG_BULLISH" if close>max(a,b) and t>k else "STRONG_BEARISH" if close<min(a,b) and t<k else "NEUTRAL_CLOUD"
    chikou="BULLISH_CONFIRMATION" if closes(s)[-1]>closes(s)[-1-displacement] else "BEARISH_CONFIRMATION" if closes(s)[-1]<closes(s)[-1-displacement] else "NEUTRAL"
    return SimpleAnalysis(state,(("tenkan",str(t)),("kijun",str(k)),("span_a",str(a)),("span_b",str(b)),("thickness",str(abs(a-b))),("chikou",chikou)),s.observation_ids,AnalysisStatus.VALID,1.0)

def multi_timeframe_alignment(timeframes: Mapping[str, AsOfSnapshot | None], instrument: str, tenkan:int, kijun:int, span_b:int, displacement:int)->SimpleAnalysis:
    available=[(name,snapshot) for name,snapshot in timeframes.items() if snapshot is not None]
    if not available:return SimpleAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INSUFFICIENT_DATA,None)
    analyses=[(name,ichimoku(s,instrument,tenkan,kijun,span_b,displacement)) for name,s in available]
    ids=tuple(item for _,analysis in analyses for item in analysis.input_ids)
    if any(analysis.status is AnalysisStatus.INVALID_DATA for _,analysis in analyses):return SimpleAnalysis("INSUFFICIENT_DATA",tuple((name,analysis.state) for name,analysis in analyses),ids,AnalysisStatus.INVALID_DATA,None)
    valid=[analysis.state for _,analysis in analyses if analysis.status is AnalysisStatus.VALID]
    if not valid:return SimpleAnalysis("INSUFFICIENT_DATA",tuple((name,analysis.state) for name,analysis in analyses),ids,AnalysisStatus.INSUFFICIENT_DATA,None)
    state="FULL_BULLISH_ALIGNMENT" if len(valid)==len(available) and all(v=="STRONG_BULLISH" for v in valid) else "FULL_BEARISH_ALIGNMENT" if len(valid)==len(available) and all(v=="STRONG_BEARISH" for v in valid) else "CONFLICTING" if any("BULL" in v for v in valid) and any("BEAR" in v for v in valid) else "PARTIAL_BULLISH_ALIGNMENT" if any("BULL" in v for v in valid) else "PARTIAL_BEARISH_ALIGNMENT" if any("BEAR" in v for v in valid) else "NEUTRAL"
    return SimpleAnalysis(state,tuple((name,analysis.state) for name,analysis in analyses)+(("configured_timeframes",str(len(available))),),ids,AnalysisStatus.VALID,1.0 if len(valid)==len(available) else .5)
