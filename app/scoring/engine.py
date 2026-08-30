from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility

@dataclass(frozen=True, slots=True)
class ComponentConfig:
    component_id:str; name:str; weight:Decimal; mandatory:tuple[int,...]; optional:tuple[int,...]; state_scores:dict[str,Decimal]; version:str="decision-score-v1"
@dataclass(frozen=True, slots=True)
class ScoredComponent:
    component_id:str; status:str; score:Decimal|None; weight:Decimal; weighted_contribution:Decimal|None; available_rules:tuple[int,...]; missing_rules:tuple[int,...]; diagnostic_ids:tuple[str,...]; evidence_ids:tuple[str,...]; confidence:float|None; contradictions:tuple[str,...]
@dataclass(frozen=True, slots=True)
class DecisionScorecard:
    id:str; instrument_id:str; strategy_version:object; registry_version:str; configuration_version:str; as_of_timestamp:object; evaluated_at:object; components:tuple[ScoredComponent,...]; final_score:Decimal|None; score_status:str; data_confidence:float|None; warnings:tuple[str,...]

BASE_STATE_SCORES={"STRONG_BULL":Decimal("10"),"STRONG":Decimal("9"),"BULL":Decimal("8"),"HEALTHY":Decimal("7"),"VALID":Decimal("7"),"ACCUMULATION":Decimal("8"),"ACCELERATING":Decimal("9"),"EXPANDING":Decimal("8"),"ATTRACTIVE":Decimal("8"),"ACCEPTABLE":Decimal("7"),"CANDIDATE":Decimal("7"),"CONFIRMED":Decimal("8"),"MARKUP":Decimal("8"),"CLEAN":Decimal("8"),"NEUTRAL":Decimal("5"),"MIXED":Decimal("5"),"BALANCED":Decimal("5"),"REASONABLE":Decimal("6"),"PARTIAL":Decimal("5"),"WEAK":Decimal("3"),"BEAR":Decimal("2"),"BEARISH":Decimal("2"),"DISTRIBUTION":Decimal("2"),"MARKDOWN":Decimal("2"),"STRESSED":Decimal("1"),"SEVERE_CONCERN":Decimal("0"),"TRIGGERED":Decimal("0"),"BROKEN":Decimal("0"),"INVALIDATED":Decimal("0"),"BELOW_THRESHOLD":Decimal("2"),"INSUFFICIENT_DATA":Decimal("0")}
COMPONENTS=(
 ComponentConfig("earnings_acceleration","Earnings Acceleration",Decimal(".15"),(24,),(25,26,16,27,28),BASE_STATE_SCORES),ComponentConfig("market_regime","Market Regime",Decimal(".10"),(1,),(),BASE_STATE_SCORES),ComponentConfig("sector_rotation","Sector Rotation",Decimal(".10"),(2,),(3,),BASE_STATE_SCORES),ComponentConfig("smart_money_evidence","Smart Money Evidence",Decimal(".10"),(7,),(9,50,58,22),BASE_STATE_SCORES),ComponentConfig("relative_strength","Relative Strength",Decimal(".10"),(6,),(),BASE_STATE_SCORES),ComponentConfig("price_structure","Price Structure",Decimal(".10"),(10,),(4,5,37,38,40,41,42,46),BASE_STATE_SCORES),ComponentConfig("volume_obv_vwap","Volume / OBV / VWAP",Decimal(".10"),(11,),(35,36,58),BASE_STATE_SCORES),ComponentConfig("ichimoku_mtf","Ichimoku & MTF",Decimal(".10"),(12,),(13,14,59),BASE_STATE_SCORES),ComponentConfig("valuation_risk_reward","Valuation & Risk/Reward",Decimal(".10"),(29,45),(43,44,31),BASE_STATE_SCORES),ComponentConfig("liquidity_smc_traps","Liquidity & SMC Traps",Decimal(".05"),(8,),(51,52,53,54,55,56,57,60,61),BASE_STATE_SCORES),)
assert sum(x.weight for x in COMPONENTS)==Decimal("1.00")
def build_scorecard(*,instrument_id,strategy_version,registry_version,as_of_timestamp,evaluated_at,diagnostics:tuple[EvaluatedDiagnostic,...],configuration_version="decision-score-v1"):
    eligible={x.canonical_rule_id:x for x in diagnostics if x.eligibility is EvaluationEligibility.ELIGIBLE and x.record.as_of_timestamp<=as_of_timestamp}; components=[]; warnings=[]
    for cfg in COMPONENTS:
        missing=tuple(x for x in cfg.mandatory if x not in eligible); available=tuple(x for x in cfg.mandatory+cfg.optional if x in eligible); records=tuple(eligible[x] for x in available)
        if missing: components.append(ScoredComponent(cfg.component_id,"INELIGIBLE",None,cfg.weight,None,available,missing,tuple(x.record.id for x in records),tuple(y for x in records for y in x.record.evidence_ids),None,())); continue
        values=tuple(cfg.state_scores.get(x.record.result,Decimal("5")) for x in records); score=sum(values)/len(values); status="COMPLETE" if not tuple(x for x in cfg.optional if x not in eligible) else "PARTIAL"; confidence=sum((x.record.confidence or 0) for x in records)/len(records); contradictions=tuple(x.record.id for x in records if x.record.result in {"MIXED","WEAK","BROKEN","SEVERE_CONCERN","TRIGGERED"})
        components.append(ScoredComponent(cfg.component_id,status,score,cfg.weight,score*cfg.weight,available,(),tuple(x.record.id for x in records),tuple(y for x in records for y in x.record.evidence_ids),confidence,contradictions))
        if any(x.record.result in {"SEVERE_CONCERN","TRIGGERED","BROKEN","STRESSED"} for x in records):warnings.append(f"ANALYTICAL_WARNING:{cfg.component_id}")
    complete=all(x.status!="INELIGIBLE" for x in components); final=sum((x.weighted_contribution or Decimal("0")) for x in components) if complete else None; known=[x.confidence for x in components if x.confidence is not None]; confidence=sum(known)/len(known) if known else None
    return DecisionScorecard(f"scorecard-{instrument_id}-{strategy_version.strategy_id}-{strategy_version.version}-{as_of_timestamp.isoformat()}",instrument_id,strategy_version,registry_version,configuration_version,as_of_timestamp,evaluated_at,tuple(components),final,"COMPLETE" if complete else "SCORE_INCOMPLETE",confidence,tuple(warnings))
