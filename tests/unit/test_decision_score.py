from dataclasses import replace
from decimal import Decimal
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DiagnosticResult
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import COMPONENTS, build_scorecard
from tests.fixtures.analytical_observations import ANALYSIS_TIME, STRATEGY_REFERENCE

def diagnostic(rule,result="STRONG",confidence=.8,asof=ANALYSIS_TIME):
    r=DiagnosticResult(f"d-{rule}-{result}","stock",str(rule),STRATEGY_REFERENCE,result,None,confidence,(f"e-{rule}",),(f"i-{rule}",),ANALYSIS_TIME,asof)
    return EvaluatedDiagnostic(r,rule,DIAGNOSTIC_REGISTRY_VERSION,EvaluationEligibility.ELIGIBLE,(),())
def complete(result="STRONG",confidence=.8): return tuple(diagnostic(x,result,confidence) for c in COMPONENTS for x in c.mandatory)
def score(items): return build_scorecard(instrument_id="stock",strategy_version=STRATEGY_REFERENCE,registry_version=DIAGNOSTIC_REGISTRY_VERSION,as_of_timestamp=ANALYSIS_TIME,evaluated_at=ANALYSIS_TIME,diagnostics=items)

def test_exact_ten_components_weights_and_formula_are_deterministic():
    card=score(complete()); assert len(card.components)==10 and sum(x.weight for x in card.components)==Decimal("1.00")
    assert card.final_score==Decimal("9.00") and card==score(complete()) and card.score_status=="COMPLETE"

def test_missing_mandatory_component_does_not_renormalize_or_become_neutral():
    card=score(tuple(x for x in complete() if x.canonical_rule_id!=1)); market=next(x for x in card.components if x.component_id=="market_regime")
    assert card.final_score is None and card.score_status=="SCORE_INCOMPLETE" and market.status=="INELIGIBLE" and market.missing_rules==(1,)

def test_score_is_not_diagnostic_count_or_confidence_and_warnings_remain_visible():
    high_low_conf=score(complete("STRONG",.1)); low_high_conf=score(complete("WEAK",.95)); warning=score(complete()+ (diagnostic(23,"SEVERE_CONCERN"),))
    assert high_low_conf.final_score>low_high_conf.final_score and high_low_conf.data_confidence<low_high_conf.data_confidence
    assert warning.final_score==high_low_conf.final_score and warning.warnings==()

def test_future_diagnostic_cannot_change_earlier_scorecard_or_create_execution_behavior():
    base=complete(); item=diagnostic(1,"WEAK"); future=replace(item,record=replace(item.record,id="future",as_of_timestamp=ANALYSIS_TIME.replace(year=2027)))
    first,second=score(base),score(base+(future,))
    assert first==second and "future" not in repr(first) and not hasattr(first,"order") and not hasattr(first,"signal")
