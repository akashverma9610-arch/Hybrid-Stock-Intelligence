from dataclasses import replace

from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.diagnostics.synthesis import HigherOrderDiagnosticContext, IMPLEMENTATION_MATURITY, SynthesisRules
from app.domain.models import DiagnosticResult
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE

RULES=SynthesisRules()
def diagnostic(rule,result="HEALTHY"):
    r=DiagnosticResult(f"upstream-{rule}-{result}","stock",str(rule),STRATEGY_REFERENCE,result,None,.8,(),(f"input-{rule}",),ANALYSIS_TIME,ANALYSIS_TIME)
    return EvaluatedDiagnostic(r,rule,DIAGNOSTIC_REGISTRY_VERSION,EvaluationEligibility.ELIGIBLE,(),(("source","fixture"),))
def context(items): return HigherOrderDiagnosticContext(ANALYSIS_TIME,STRATEGY_REFERENCE,DIAGNOSTIC_REGISTRY_VERSION,tuple(items),"higher-order-v1")
def complete_context(): return context([diagnostic(x) for x in (1,2,4,6,10,15,16,17,18,19,20,23,30,37,38,41,43,45,46)])

def test_risk_trading_investment_and_scenarios_are_deterministic_and_traceable():
    e=DeterministicDiagnosticEvaluators(); c=complete_context(); risk=e.comprehensive_risk(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    c2=context(c.diagnostics+(risk,)); trading=e.trading_thesis(c2,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); investment=e.investment_thesis(c2,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    c3=context(c2.diagnostics+(trading,investment)); scenarios=e.scenarios(c3,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    assert risk==e.comprehensive_risk(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    assert trading.record.result in {"STRONG","VALID","MIXED"} and investment.record.result in {"STRONG","VALID"}
    assert dict(scenarios.details)["weight_sum"]=="100" and scenarios.record.score is None

def test_trading_and_investment_theses_remain_separate_and_missing_dependencies_fail_closed():
    e=DeterministicDiagnosticEvaluators(); c=context([diagnostic(x) for x in (16,17,18,19,23)])
    assert e.trading_thesis(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME).record.result=="INSUFFICIENT_DATA"
    assert e.investment_thesis(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME).record.result=="STRONG"

def test_red_flags_and_triggered_invalidation_remain_visible_not_silently_averaged():
    e=DeterministicDiagnosticEvaluators(); c=context([diagnostic(23,"SEVERE_CONCERN"),diagnostic(19,"STRESSED"),diagnostic(43),diagnostic(45),diagnostic(46,"TRIGGERED")])
    risk=e.comprehensive_risk(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); trading=e.trading_thesis(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    assert risk.record.result=="SEVERE_RISK" and dict(risk.details)["red_flag_present"]=="True" and trading.record.result=="INVALIDATED"

def test_future_upstream_evidence_is_excluded_from_earlier_higher_order_reconstruction():
    e=DeterministicDiagnosticEvaluators(); c=complete_context(); item=diagnostic(23,"SEVERE_CONCERN")
    future=replace(item,record=replace(item.record,id="future-governance",as_of_timestamp=ANALYSIS_TIME.replace(year=2027)))
    earlier=context(c.diagnostics+(future,)); first=e.comprehensive_risk(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); second=e.comprehensive_risk(earlier,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    assert first==second and "future-governance" not in repr(first)

def test_all_four_higher_order_rules_exclude_future_upstream_evidence():
    e=DeterministicDiagnosticEvaluators(); base=complete_context(); item=diagnostic(16,"WEAK")
    future=replace(item,record=replace(item.record,id="future-earnings",as_of_timestamp=ANALYSIS_TIME.replace(year=2027)))
    def pipeline(c):
        r=e.comprehensive_risk(c,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); c2=context(c.diagnostics+(r,))
        t=e.trading_thesis(c2,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME); i=e.investment_thesis(c2,"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
        return r,t,i,e.scenarios(context(c2.diagnostics+(t,i)),"stock",STRATEGY_REFERENCE,RULES,ANALYSIS_TIME)
    first,second=pipeline(base),pipeline(context(base.diagnostics+(future,)))
    assert first==second and "future-earnings" not in repr(first)

def test_complete_canonical_coverage_is_explicit():
    assert len(DIAGNOSTIC_RULES)==61 and set(IMPLEMENTATION_MATURITY)==set(range(1,62)) and len(IMPLEMENTATION_MATURITY)==61
