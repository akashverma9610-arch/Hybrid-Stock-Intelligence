from __future__ import annotations
from dataclasses import dataclass
from app.analysis.models import AnalysisStatus
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.diagnostics.downstream import v1_synthesis_rejection

@dataclass(frozen=True, slots=True)
class SynthesisRules:
    red_flags:tuple[str,...]=( "SEVERE_CONCERN","STRESSED","TRIGGERED")
    required_trading:tuple[int,...]=(43,45,46)
    required_investment:tuple[int,...]=(16,17,18,19,23)
    version:str="higher-order-v1"
@dataclass(frozen=True, slots=True)
class HigherOrderDiagnosticContext:
    as_of_timestamp:object; strategy_version:object; registry_version:str; diagnostics:tuple[EvaluatedDiagnostic,...]; configuration_version:str
    @property
    def eligible(self):
        if self.rejection_reason: return ()
        return tuple({x.canonical_rule_id:x for x in self.diagnostics if x.eligibility is EvaluationEligibility.ELIGIBLE and x.record.as_of_timestamp<=self.as_of_timestamp}.values())
    @property
    def rejection_reason(self): return v1_synthesis_rejection(self.diagnostics,self.registry_version,self.as_of_timestamp)
    @property
    def by_rule(self): return {x.canonical_rule_id:x for x in self.eligible}
@dataclass(frozen=True, slots=True)
class SynthesisAnalysis:
    state:str; details:tuple[tuple[str,str],...]; input_ids:tuple[str,...]; status:AnalysisStatus; confidence:float|None

def _analysis(state,details,items,confidence=.7): return SynthesisAnalysis(state,tuple(details),tuple(i.record.id for i in items),AnalysisStatus.VALID,confidence)
def _bad(reason=None): return SynthesisAnalysis("INSUFFICIENT_DATA",(("blocker",reason),) if reason else (),(),AnalysisStatus.INSUFFICIENT_DATA,None)
def risk(context,rules):
    if context.rejection_reason:return _bad(context.rejection_reason)
    items=context.eligible
    if not items:return _bad()
    categories=[]
    mapping={23:"GOVERNANCE_RISK",19:"BALANCE_SHEET_RISK",29:"VALUATION_RISK",46:"TECHNICAL_RISK",55:"CROWD_TRAP_RISK",30:"CATALYST_RISK",1:"MARKET_RISK",2:"SECTOR_RISK"}
    for item in items:
        cat=mapping.get(item.canonical_rule_id)
        if cat:
            severity="CRITICAL" if item.record.result in rules.red_flags else "MATERIAL" if item.record.result in {"WEAK","ELEVATED","HIGH","DISTRIBUTION"} else "MODERATE"
            categories.append((cat,f"severity={severity};upstream_rule={item.canonical_rule_id};result={item.record.result}"))
    if not categories:return _bad()
    critical=any("CRITICAL" in x[1] for x in categories); material=sum("MATERIAL" in x[1] for x in categories)
    state="SEVERE_RISK" if critical else "HIGH_RISK" if material>=3 else "ELEVATED_RISK" if material else "MODERATE_RISK"
    return _analysis(state,tuple(categories)+(("risk_matrix_semantics","ordinal MODEL_WEIGHTS / RISK_MATRIX_VALUES; not calibrated probability"),("red_flag_present",str(critical))),items,.8)
def trading_thesis(context,rules):
    if context.rejection_reason:return _bad(context.rejection_reason)
    d=context.by_rule; missing=[str(x) for x in rules.required_trading if x not in d]
    if missing:return _bad()
    inv=d[46].record.result
    if inv=="TRIGGERED": return _analysis("INVALIDATED",(("invalidation","triggered rule 46"),),tuple(d.values()),.8)
    supporting=[x for x in (4,6,10,37,38,41,45) if x in d and d[x].record.result not in {"MIXED","WEAK","INSUFFICIENT_DATA","BELOW_THRESHOLD"}]
    status="STRONG" if len(supporting)>=5 else "VALID" if len(supporting)>=3 else "MIXED"
    return _analysis(status,(("direction","structure-dependent; non-executable"),("supporting_rules",",".join(map(str,supporting))),("invalidation_rule","46"),("required_missing",",".join(missing) or "none")),tuple(d.values()),min(1,.4+.1*len(supporting)))
def investment_thesis(context,rules):
    if context.rejection_reason:return _bad(context.rejection_reason)
    d=context.by_rule; present=[x for x in rules.required_investment if x in d]
    if len(present)<len(rules.required_investment):return _bad()
    weak=[x for x in present if d[x].record.result in {"WEAK","STRESSED","SEVERE_CONCERN","INSUFFICIENT_DATA"}]
    status="WEAK" if weak else "STRONG" if len(present)>=5 else "VALID"
    return _analysis(status,(("business_quality_rules","15,16,17,18,19,20,23"),("fundamental_conflicts",",".join(map(str,weak)) or "none"),("horizon","longer-horizon; not an execution recommendation")),tuple(d.values()),.8 if not weak else .5)
def scenarios(context,rules):
    if context.rejection_reason:return _bad(context.rejection_reason)
    d=context.by_rule
    if 31 not in d:return _bad()
    risk_state=d[31].record.result; trading=d.get(32); investment=d.get(33)
    if not trading or not investment:return _bad()
    if risk_state in {"SEVERE_RISK","HIGH_RISK"}: weights=(20,30,50)
    elif trading.record.result=="STRONG" and investment.record.result=="STRONG": weights=(50,30,20)
    else: weights=(30,50,20)
    details=(("bull",f"MODEL_SCENARIO_WEIGHT={weights[0]}; requires constructive structure/catalyst"),("base",f"MODEL_SCENARIO_WEIGHT={weights[1]}; current supported pathway"),("bear",f"MODEL_SCENARIO_WEIGHT={weights[2]}; risk/invalidation pathway"),("weight_sum",str(sum(weights))),("semantics","coarse model scenario weights, not calibrated probabilities"),("risk_input",risk_state))
    return _analysis("SCENARIOS_DEFINED",details,tuple(d.values()),.7)

# All canonical IDs now have an explicit implementation maturity classification.
IMPLEMENTATION_MATURITY={rule_id:("V1_HYBRID" if rule_id in {15,23,28,30,31,32,33,34,47,48,49,55,56,57,59,60,61} else "V1_DETERMINISTIC") for rule_id in range(1,62)}
