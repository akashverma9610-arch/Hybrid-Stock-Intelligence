from __future__ import annotations
from dataclasses import dataclass
from app.analysis.models import AnalysisStatus
from app.analysis.series import closes, price_bar_series
from app.crowd.models import CrowdCategory, CrowdSnapshot

@dataclass(frozen=True, slots=True)
class CrowdRules:
    bearish:float; bullish:float; extreme_bearish:float; extreme_bullish:float; high_confidence:float; medium_confidence:float
@dataclass(frozen=True, slots=True)
class CrowdAnalysis:
    state:str; details:tuple[tuple[str,str],...]; input_ids:tuple[str,...]; status:AnalysisStatus; confidence:float|None

def as_of(snapshot,timestamp):
    return CrowdSnapshot(timestamp,tuple(x for x in snapshot.observations if x.publication_timestamp<=timestamp and x.retrieval_timestamp<=timestamp),tuple(x for x in snapshot.events if x.publication_timestamp<=timestamp))
def _unique(snapshot, category=None):
    out=[]; seen=set()
    for x in snapshot.observations:
        if category and x.category is not category: continue
        key=x.duplicate_group or x.observation_id
        if key not in seen: seen.add(key);out.append(x)
    return tuple(out)
def sentiment(snapshot,rules):
    obs=_unique(snapshot)
    if not obs:return _bad()
    score=sum(x.value*(x.confidence or .5) for x in obs)/sum(x.confidence or .5 for x in obs)
    state="EXTREME_BEARISH" if score<=rules.extreme_bearish else "BEARISH" if score<=rules.bearish else "EXTREME_BULLISH" if score>=rules.extreme_bullish else "BULLISH" if score>=rules.bullish else "NEUTRAL"
    return CrowdAnalysis(state,(("score",str(score)),("observations",str(len(obs))),("sample_sizes",",".join(str(x.sample_size) if x.sample_size is not None else "UNAVAILABLE" for x in obs)),("semantic","crowd sentiment data; not company truth")),tuple(x.observation_id for x in obs),AnalysisStatus.VALID,.8)
def positioning(snapshot,rules):
    obs=_unique(snapshot,CrowdCategory.POSITIONING)
    if not obs:return _bad()
    value=sum(x.value for x in obs)/len(obs); state="HEAVILY_SHORT_OR_BEARISH" if value<=rules.extreme_bearish else "BEARISH" if value<=rules.bearish else "HEAVILY_LONG_OR_EUPHORIC" if value>=rules.extreme_bullish else "BULLISH" if value>=rules.bullish else "BALANCED"
    return CrowdAnalysis(state,(("positioning",str(value)),),tuple(x.observation_id for x in obs),AnalysisStatus.VALID,.7)
def confidence(snapshot,rules):
    raw=snapshot.observations
    if not raw:return _bad()
    unique=_unique(snapshot); diversity=len({x.source for x in unique}); samples=[x.sample_size for x in unique if x.sample_size is not None]; duplicate_penalty=len(unique)/len(raw); value=min(1,(diversity/3)*.4+(sum(1 for x in samples if x>=100)/max(1,len(unique)))*.3+duplicate_penalty*.3)
    state="HIGH" if value>=rules.high_confidence else "MEDIUM" if value>=rules.medium_confidence else "LOW" if value>=.25 else "VERY_LOW"
    return CrowdAnalysis(state,(("crowd_confidence",str(value)),("source_diversity",str(diversity)),("independence",str(duplicate_penalty))),tuple(x.observation_id for x in unique),AnalysisStatus.VALID,value)
def divergence(crowd,market,instrument,rules):
    s=sentiment(crowd,rules); p=price_bar_series(market,instrument)
    if s.status is not AnalysisStatus.VALID or p.status is not AnalysisStatus.VALID or len(p.bars)<2:return _bad()
    price_up=closes(p)[-1]>closes(p)[0]; state="BEARISH_CONTRARIAN_DIVERGENCE" if s.state in {"BULLISH","EXTREME_BULLISH"} and not price_up else "BULLISH_CONTRARIAN_DIVERGENCE" if s.state in {"BEARISH","EXTREME_BEARISH"} and price_up else "CONFIRMING" if (price_up and s.state in {"BULLISH","EXTREME_BULLISH"}) or (not price_up and s.state in {"BEARISH","EXTREME_BEARISH"}) else "NO_DIVERGENCE"
    return CrowdAnalysis(state,s.details+(("price_change",str(closes(p)[-1]-closes(p)[0])),),s.input_ids+p.observation_ids,AnalysisStatus.VALID,.7)
def post_news(crowd,market,instrument):
    if not crowd.events:return _bad()
    event=crowd.events[-1]; s=price_bar_series(market,instrument); bars=[x for x in s.bars if x.provenance.market_timestamp>event.publication_timestamp]
    if s.status is not AnalysisStatus.VALID or not bars:return _bad()
    first,last=float(bars[0].payload["close"]),float(bars[-1].payload["close"]); positive=last>first
    state="POSITIVE_ACCEPTANCE" if event.polarity=="positive" and positive else "SELL_THE_NEWS" if event.polarity=="positive" else "BUY_THE_BAD_NEWS" if event.polarity=="negative" and positive else "NEGATIVE_ACCEPTANCE"
    return CrowdAnalysis(state,(("event",event.event_id),("post_event_bars",str(len(bars))),),tuple(x.id for x in bars)+(event.event_id,),AnalysisStatus.VALID,.8)
def trap_probability(crowd,market,instrument,rules):
    s=sentiment(crowd,rules); c=confidence(crowd,rules); d=divergence(crowd,market,instrument,rules)
    if any(x.status is not AnalysisStatus.VALID for x in (s,c,d)):return _bad()
    score=(2 if "EXTREME" in s.state else 1 if s.state!="NEUTRAL" else 0)+(2 if "DIVERGENCE" in d.state else 0)
    state="VERY_HIGH" if score>=4 and c.state in {"HIGH","MEDIUM"} else "HIGH" if score>=3 and c.state!="VERY_LOW" else "MODERATE" if score else "LOW"
    return CrowdAnalysis(state,(("model_score",str(score)),("label","ESTIMATED_TRAP_PROBABILITY"),("crowd_confidence",c.state)),s.input_ids+d.input_ids,AnalysisStatus.VALID,c.confidence)
def ichimoku_confluence(sentiment_result,ichimoku_result,chikou_result,mtf_result):
    if not all((sentiment_result,ichimoku_result,chikou_result,mtf_result)):return _bad()
    bear=sentiment_result.record.result in {"BEARISH","EXTREME_BEARISH"}; bull=sentiment_result.record.result in {"BULLISH","EXTREME_BULLISH"}; cloud=ichimoku_result.record.result; chikou=chikou_result.record.result; mtf=mtf_result.record.result
    state="STRONG_BULLISH_CONTRARIAN_CONFLUENCE" if bear and "BULL" in cloud and "BULL" in chikou and "BULL" in mtf else "STRONG_BEARISH_CONTRARIAN_CONFLUENCE" if bull and "BEAR" in cloud and "BEAR" in chikou and "BEAR" in mtf else "CONFLICTING"
    return CrowdAnalysis(state,(("reuse","rules 12/13/14 outputs"),),sentiment_result.record.input_observation_ids+ichimoku_result.record.input_observation_ids+chikou_result.record.input_observation_ids+mtf_result.record.input_observation_ids,AnalysisStatus.VALID,.8)
def quality(trap,divergence_result,confluence,confidence_result):
    if any(x is None or x.eligibility.value!="eligible" for x in (trap,divergence_result,confluence,confidence_result)):return _bad()
    state="STRONG" if trap.record.result in {"HIGH","VERY_HIGH"} and "STRONG" in confluence.record.result and confidence_result.record.result in {"HIGH","MEDIUM"} else "MODERATE" if trap.record.result=="MODERATE" and confidence_result.record.result!="VERY_LOW" else "WEAK"
    return CrowdAnalysis(state,(("trap",trap.record.result),("divergence",divergence_result.record.result),("confluence",confluence.record.result),("crowd_confidence",confidence_result.record.result)),trap.record.input_observation_ids+divergence_result.record.input_observation_ids+confluence.record.input_observation_ids,AnalysisStatus.VALID,confidence_result.record.confidence)
def verdict(quality_result,confidence_result):
    if quality_result is None or confidence_result is None or quality_result.eligibility.value!="eligible":return _bad()
    state="WAIT" if confidence_result.record.result in {"LOW","VERY_LOW"} else "BUY" if quality_result.record.result=="STRONG" and "BULLISH" in repr(quality_result) else "SELL" if quality_result.record.result=="STRONG" else "AVOID" if quality_result.record.result in {"WEAK","CONFLICTING"} else "HOLD"
    return CrowdAnalysis(state,(("semantic","ContrarianDiagnosticVerdict only; non-executable"),),quality_result.record.input_observation_ids,AnalysisStatus.VALID,confidence_result.record.confidence)
def _bad():return CrowdAnalysis("INSUFFICIENT_DATA",(),(),AnalysisStatus.INSUFFICIENT_DATA,None)
