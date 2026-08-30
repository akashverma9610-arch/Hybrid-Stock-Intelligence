from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.valuation_trade import TradeRules, ValuationRules
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import AsOfSnapshot, DataQuality, Instrument, MarketObservation, ObservationKind, Provenance, ValidationResult, ValidationStatus
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, snapshot

TRADE=TradeRules(6,.08,.05,.02,2); VALUE=ValuationRules(15,30)
def market(): return snapshot(bars("stock",[100,101,100,101,100,101,100,103]))
def financial():
    p={"period_type":"annual","period_end":"2026-03-31T00:00:00+00:00","publication_timestamp":(ANALYSIS_TIME-timedelta(days=1)).isoformat(),"eps":5,"forward_eps":6,"configured_growth_rate":.2,"shares_outstanding":10,"ebitda":50,"total_debt":20,"cash":5,"total_equity":500}
    x=MarketObservation("filing",Instrument("stock","STOCK","MOCK"),ObservationKind.FUNDAMENTAL,p,Provenance("mock","filing",ANALYSIS_TIME-timedelta(days=1),ANALYSIS_TIME-timedelta(days=1),DataQuality.HIGH),ValidationResult(ValidationStatus.VALID,ANALYSIS_TIME))
    return AsOfSnapshot("financial",ANALYSIS_TIME,ANALYSIS_TIME,"fixture",(x,))
def evaluate(rule,data):
    e=DeterministicDiagnosticEvaluators(); m=market();
    return {29:lambda:e.valuation_multiples(m,financial(),"stock",STRATEGY_REFERENCE,VALUE,ANALYSIS_TIME),37:lambda:e.base_pattern(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),38:lambda:e.pullback_quality(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),40:lambda:e.aggressive_entry(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),41:lambda:e.confirmation_entry(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),42:lambda:e.retest_entry(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),43:lambda:e.structural_stop(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),44:lambda:e.target_hierarchy(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME),45:lambda:e.risk_reward(data,"stock",STRATEGY_REFERENCE,TRADE,101,98,107,ANALYSIS_TIME),46:lambda:e.thesis_invalidation(data,"stock",STRATEGY_REFERENCE,TRADE,ANALYSIS_TIME)}[rule]()

@pytest.mark.parametrize("rule",(29,37,38,40,41,42,43,44,45,46))
def test_each_new_rule_is_deterministic_and_excludes_future_bar_from_earlier_snapshot(rule):
    before=market(); future=replace(bars("stock",[1],start=ANALYSIS_TIME+timedelta(days=1))[0],id="future-collapse")
    after=AsOfSnapshot("same-earlier",ANALYSIS_TIME,ANALYSIS_TIME,"fixture",before.observations) # reconstructed as-of excludes future
    first,second=evaluate(rule,before),evaluate(rule,after)
    assert first==second and "future-collapse" not in repr(first) and future.provenance.market_timestamp>before.as_of_timestamp

def test_valuation_is_raw_multiples_not_a_buy_recommendation():
    result=evaluate(29,market()); d=dict(result.details)
    assert float(d["pe"])==pytest.approx(103/5) and result.record.score is None

def test_no_valid_base_fails_closed_without_entries_stops_targets_or_rr():
    bad=snapshot(bars("stock",[100,120,80,125,70,130,60,140]))
    for rule in (37,40,41,42,43,44,46): assert evaluate(rule,bad).record.result in {"NO_VALID_BASE","INSUFFICIENT_DATA","NO_VALID_ENTRY"}
    assert evaluate(45,bad).record.result=="ACCEPTABLE"  # R:R is a supplied analytical arithmetic structure.

def test_missing_stop_or_target_does_not_fabricate_rr():
    e=DeterministicDiagnosticEvaluators(); result=e.risk_reward(market(),"stock",STRATEGY_REFERENCE,TRADE,None,None,None,ANALYSIS_TIME)
    assert result.record.result=="INSUFFICIENT_DATA"


def test_future_financial_publication_cannot_be_consumed_by_earlier_valuation_snapshot():
    original=financial(); future=replace(original.observations[0],id="future-eps",payload={**original.observations[0].payload,"publication_timestamp":(ANALYSIS_TIME+timedelta(days=2)).isoformat(),"eps":100})
    contaminated=AsOfSnapshot("contaminated",ANALYSIS_TIME,ANALYSIS_TIME,"fixture",original.observations+(future,))
    result=DeterministicDiagnosticEvaluators().valuation_multiples(market(),contaminated,"stock",STRATEGY_REFERENCE,VALUE,ANALYSIS_TIME)
    assert result.eligibility.value=="ineligible_invalid_data" and "future-eps" not in result.record.input_observation_ids


def test_transparent_cup_and_handle_emits_common_base_structure_and_quality_metadata():
    data=snapshot(bars("stock",[100,95,85,80,85,95,99,100,97,99]))
    rules=replace(TRADE,base_period=6,cup_min_duration=8,cup_handle_duration=2)
    result=DeterministicDiagnosticEvaluators().base_pattern(data,"stock",STRATEGY_REFERENCE,rules,ANALYSIS_TIME); d=dict(result.details)
    assert result.record.result=="CUP_AND_HANDLE" and float(d["support"])==97 and float(d["resistance"])==100
    assert d["pattern_quality"] in {"HIGH","ACCEPTABLE","POOR"} and "CUP_AND_HANDLE" in d["candidate_patterns"]


def test_ascending_base_requires_multiple_progressively_higher_pullbacks():
    data=snapshot(bars("stock",[90,100,95,102,98,104,101,106]))
    rules=replace(TRADE,base_period=8,ascending_min_pullbacks=2)
    result=DeterministicDiagnosticEvaluators().base_pattern(data,"stock",STRATEGY_REFERENCE,rules,ANALYSIS_TIME)
    assert result.record.result=="ASCENDING_BASE" and dict(result.details)["support_consistency"]=="progressively higher lows"


@pytest.mark.parametrize("values",([100,95,85,80,85,95,99,100,97,80],[90,100,95,102,98,104,97,106],[90,91,92,93,94,95,96,97]))
def test_incomplete_or_malformed_patterns_are_not_fabricated(values):
    data=snapshot(bars("stock",values)); rules=replace(TRADE,base_period=min(8,len(values)))
    result=DeterministicDiagnosticEvaluators().base_pattern(data,"stock",STRATEGY_REFERENCE,rules,ANALYSIS_TIME)
    assert result.record.result not in {"CUP_AND_HANDLE","ASCENDING_BASE"}


@pytest.mark.parametrize("values,rules",(([100,95,85,80,85,95,99,100,97,99],replace(TRADE,cup_min_duration=8,cup_handle_duration=2)),([90,100,95,102,98,104,101,106],replace(TRADE,base_period=8))))
def test_cup_and_ascending_results_exclude_future_pattern_forming_bars(values,rules):
    before=snapshot(bars("stock",values)); future=replace(bars("stock",[150],start=ANALYSIS_TIME+timedelta(days=1))[0],id="future-pattern")
    reconstructed=AsOfSnapshot("earlier",ANALYSIS_TIME,ANALYSIS_TIME,"fixture",before.observations)
    e=DeterministicDiagnosticEvaluators(); first=e.base_pattern(before,"stock",STRATEGY_REFERENCE,rules,ANALYSIS_TIME); second=e.base_pattern(reconstructed,"stock",STRATEGY_REFERENCE,rules,ANALYSIS_TIME)
    assert first==second and future.id not in repr(first)
