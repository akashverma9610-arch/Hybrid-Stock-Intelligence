from dataclasses import replace
from datetime import timedelta

import pytest

from app.analysis.liquidity import LiquidityRules
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import AsOfSnapshot
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE, bars, snapshot

RULES=LiquidityRules(.005,2,2,1.5)
def data(): return snapshot(bars("stock",[100,101,100,101,100,100],highs=[101,105,101,105,101,106],lows=[99,98,99,98,99,97],volumes=[100,100,100,100,100,400]))
def evaluate(rule,s):
    e=DeterministicDiagnosticEvaluators(); return {7:e.smart_money_proxies,8:e.liquidity_pools,9:e.wyckoff_phase,50:e.accumulation_distribution_proxy,51:e.stop_clusters,52:e.liquidity_events,53:e.bull_trap,54:e.bear_trap,58:e.volume_climax}[rule](s,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)

@pytest.mark.parametrize("rule",(7,8,9,50,51,52,53,54,58))
def test_each_liquidity_rule_is_deterministic_and_excludes_future_contamination(rule):
    before=data(); future=replace(bars("stock",[150],start=ANALYSIS_TIME+timedelta(days=1),volumes=[9999])[0],id="future-liquidity")
    reconstructed=AsOfSnapshot("earlier",ANALYSIS_TIME,ANALYSIS_TIME,"fixture",before.observations)
    first,second=evaluate(rule,before),evaluate(rule,reconstructed)
    assert first==second and future.id not in repr(first)

def test_repeated_levels_are_required_and_stop_clusters_never_claim_quantity():
    mapped=evaluate(8,data()); clusters=evaluate(51,data())
    assert mapped.eligibility.value=="eligible" and "actual_quantity=UNOBSERVED" in repr(clusters)
    assert evaluate(8,snapshot(bars("stock",[100,102,99],highs=[101,104,100],lows=[99,101,98]))).record.result=="INSUFFICIENT_DATA"

def test_high_rvol_alone_is_not_a_climax_or_institutional_fact():
    flat=snapshot(bars("stock",[100,100,100],highs=[101,101,101],lows=[99,99,99],volumes=[100,100,400]))
    assert evaluate(58,flat).record.result=="HIGH_VOLUME_NO_CLEAR_SIGNAL"
    assert "institutional identity" in repr(evaluate(7,data()))

def test_missing_liquidity_cannot_fabricate_events_or_traps():
    empty=snapshot(bars("stock",[100,102,99],highs=[101,104,100],lows=[99,101,98]))
    for rule in (52,53,54): assert evaluate(rule,empty).record.result=="INSUFFICIENT_DATA"
