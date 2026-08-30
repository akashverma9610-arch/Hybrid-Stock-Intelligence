from dataclasses import replace
from datetime import timedelta
import pytest

from app.analysis.valuation_trade import TradeRules
from app.crowd.engine import CrowdRules, as_of
from app.crowd.models import CrowdCategory, CrowdObservation, CrowdSnapshot, NewsEvent
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, snapshot

RULES=CrowdRules(40,60,20,80,.7,.7)
def crowd():
    when=ANALYSIS_TIME-timedelta(days=1)
    obs=(CrowdObservation("social-1","stock",CrowdCategory.SOCIAL,"social","tier_5",90,when,when,"mock",.4,None,"echo"),CrowdObservation("social-copy","stock",CrowdCategory.SOCIAL,"social-copy","tier_5",90,when,when,"mock",.4,None,"echo"),CrowdObservation("position","stock",CrowdCategory.POSITIONING,"position","tier_4",85,when,when,"mock",.8,200))
    return CrowdSnapshot(ANALYSIS_TIME,obs,(NewsEvent("news","stock",ANALYSIS_TIME-timedelta(days=5),"positive news","positive","mock://news"),))
def market(): return snapshot(bars("stock",[100,99,98,97,96,95,94,93]))
def upstream(source=None):
    e=DeterministicDiagnosticEvaluators(); c=as_of(source or crowd(),ANALYSIS_TIME); m=market(); s=e.crowd_sentiment(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); conf=e.crowd_data_confidence(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); div=e.crowd_divergence(c,m,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); trap=e.crowd_trap_probability(c,m,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); i=e.ichimoku(m,"stock",STRATEGY_REFERENCE,2,3,4,1,ANALYSIS_TIME); ch=e.chikou(m,"stock",STRATEGY_REFERENCE,2,3,4,1,ANALYSIS_TIME); mt=e.mtf({"daily":m,"weekly":m},"stock",STRATEGY_REFERENCE,ANALYSIS_TIME); con=e.contrarian_ichimoku(s,i,ch,mt,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME); q=e.contrarian_quality(trap,div,con,conf,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME); return e,c,m,(s,conf,div,trap,con,q)

def test_crowd_score_positioning_and_confidence_keep_duplicate_and_sample_limits_visible():
    e,c,_,(s,conf,_,_,_,_)=upstream()
    assert s.record.result=="EXTREME_BULLISH" and dict(s.details)["observations"]=="2"
    assert conf.record.result in {"LOW","VERY_LOW","MEDIUM"}
    assert e.crowd_positioning(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME).record.result=="HEAVILY_LONG_OR_EUPHORIC"

def test_low_confidence_extreme_sentiment_cannot_create_strong_quality_or_executable_action():
    e,_,_,(_,conf,_,_,_,q)=upstream(); verdict=e.contrarian_verdict(q,conf,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME)
    assert q.record.result!="STRONG" and verdict.record.result in {"WAIT","AVOID","HOLD"}
    assert "non-executable" in repr(verdict)

def test_post_news_uses_only_bars_after_publication_and_fails_closed_without_them():
    e,c,m,_=upstream(); assert e.post_news_reaction(c,m,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME).record.result in {"NEGATIVE_ACCEPTANCE","SELL_THE_NEWS","BUY_THE_BAD_NEWS","POSITIVE_ACCEPTANCE"}
    after=replace(c,events=(replace(c.events[0],publication_timestamp=ANALYSIS_TIME+timedelta(days=1)),))
    assert e.post_news_reaction(after,m,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME).record.result=="INSUFFICIENT_DATA"

def test_all_nine_crowd_rules_are_deterministic_and_future_observations_do_not_enter_earlier_asof():
    e,c,m,(s,conf,div,trap,con,q)=upstream(); future=CrowdObservation("future","stock",CrowdCategory.SOCIAL,"future","tier_5",0,ANALYSIS_TIME+timedelta(days=1),ANALYSIS_TIME+timedelta(days=1),"mock",.9,999)
    reconstructed=as_of(replace(c,observations=c.observations+(future,)),ANALYSIS_TIME)
    first=(s,e.crowd_positioning(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME),conf,trap,div,e.post_news_reaction(c,m,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME),con,q,e.contrarian_verdict(q,conf,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME))
    e2,c2,m2,(s2,conf2,div2,trap2,con2,q2)=upstream(reconstructed)
    second=(s2,e2.crowd_positioning(c2,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME),conf2,trap2,div2,e2.post_news_reaction(c2,m2,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME),con2,q2,e2.contrarian_verdict(q2,conf2,"stock",STRATEGY_REFERENCE,ANALYSIS_TIME))
    assert first==second and future.observation_id not in repr(first)

def test_no_crowd_data_or_unsupported_upstream_evidence_fails_closed():
    e=DeterministicDiagnosticEvaluators(); empty=CrowdSnapshot(ANALYSIS_TIME,())
    assert e.crowd_sentiment(empty,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME).record.result=="INSUFFICIENT_DATA"
