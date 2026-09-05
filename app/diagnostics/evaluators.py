from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from app.analysis.market_regime import MarketRegimeEngine
from app.analysis.models import AnalysisStatus, MarketRegimeRules, RelativeStrengthRules, TrendRules
from app.analysis.relative_strength import RelativeStrengthEngine
from app.analysis.technical import TechnicalAnalysisEngine
from app.analysis.trend import TrendEngine
from app.diagnostics.models import ComponentContributionEligibility, ComponentEligibility, EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import AsOfSnapshot, DiagnosticResult, Evidence, EvidenceType, StrategyVersionReference
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, get_diagnostic_rule
from app.analysis.sector_volume_ichimoku import sector_health, sector_rotation, volume_rvol, ichimoku, multi_timeframe_alignment, vwap, obv
from app.analysis.evidence import analysis_evidence
from app.domain.models import DataQuality
from app.analysis.fundamentals import FundamentalRules, five_year_trend, return_ratios, cash_flow, leverage, working_capital, ownership, institutional, earnings_acceleration, latest_quarter, margins, order_book
from app.research.engine import moat, governance, guidance_delivery, catalysts
from app.analysis.valuation_trade import ValuationRules, TradeRules, valuation, base_pattern, pullback, aggressive_entry, confirmation_entry, retest_entry, structural_stop, targets, risk_reward, invalidation
from app.analysis.liquidity import LiquidityRules, pools, stop_clusters, events, bull_trap, bear_trap, wyckoff, accumulation_distribution, smart_money, volume_climax
from app.crowd.engine import CrowdRules, sentiment, positioning, confidence as crowd_confidence, divergence, post_news, trap_probability, ichimoku_confluence, quality as contrarian_quality, verdict as contrarian_verdict
from app.diagnostics.synthesis import SynthesisRules, risk as synthesis_risk, trading_thesis as synthesis_trading, investment_thesis as synthesis_investment, scenarios as synthesis_scenarios

@dataclass(frozen=True, slots=True)
class WeinsteinRules:
    long_ma_period: int
    slope_lookback: int

class DeterministicDiagnosticEvaluators:
    def __init__(self, technical: TechnicalAnalysisEngine | None = None, regime: MarketRegimeEngine | None = None, relative: RelativeStrengthEngine | None = None, trend: TrendEngine | None = None) -> None:
        self.technical = technical or TechnicalAnalysisEngine(); self.regime = regime or MarketRegimeEngine(self.technical)
        self.relative = relative or RelativeStrengthEngine(); self.trend = trend or TrendEngine(self.technical)

    def market_regime(self, snapshot: AsOfSnapshot, instrument: str, strategy: StrategyVersionReference, rules: MarketRegimeRules, now: datetime) -> EvaluatedDiagnostic:
        return self._wrap(1, self.regime.classify(snapshot, benchmark_instrument_id=instrument, strategy_version=strategy, rules=rules, evaluated_at=now), strategy, now)

    def primary_trend(self, weekly: AsOfSnapshot | None, daily: AsOfSnapshot | None, instrument: str, strategy: StrategyVersionReference, rules: TrendRules, now: datetime) -> EvaluatedDiagnostic:
        if weekly is None or daily is None: return self._missing(4, instrument, strategy, now, "weekly and daily bars are both required")
        if weekly.id == daily.id or {item.id for item in weekly.observations} & {item.id for item in daily.observations}:
            return self._missing(4, instrument, strategy, now, "distinct canonical daily and weekly snapshots are required")
        w=self.trend.classify(weekly,instrument_id=instrument,strategy_version=strategy,rules=rules,evaluated_at=now); d=self.trend.classify(daily,instrument_id=instrument,strategy_version=strategy,rules=rules,evaluated_at=now)
        if w.status is not AnalysisStatus.VALID or d.status is not AnalysisStatus.VALID: return self._missing(4,instrument,strategy,now,"timeframe trend is insufficient")
        result = "BULLISH" if w.classification.value==d.classification.value=="uptrend" else "BEARISH" if w.classification.value==d.classification.value=="downtrend" else "SIDEWAYS" if w.classification.value==d.classification.value=="sideways" else "MIXED"
        return self._record(4,instrument,strategy,now,daily.as_of_timestamp,result,1.0,w.input_observation_ids+d.input_observation_ids,w.evidence+d.evidence,EvaluationEligibility.ELIGIBLE,(("weekly",w.classification.value),("daily",d.classification.value)))

    def weinstein(self,snapshot:AsOfSnapshot,instrument:str,strategy:StrategyVersionReference,rules:WeinsteinRules,now:datetime)->EvaluatedDiagnostic:
        from app.analysis.series import closes, price_bar_series
        s=price_bar_series(snapshot,instrument)
        if s.status is not AnalysisStatus.VALID or len(s.bars)<rules.long_ma_period+rules.slope_lookback: return self._missing(5,instrument,strategy,now,"long moving-average history is insufficient")
        c=closes(s); ma=sum(c[-rules.long_ma_period:])/rules.long_ma_period; prior=sum(c[-rules.long_ma_period-rules.slope_lookback:-rules.slope_lookback])/rules.long_ma_period
        stage="STAGE_2_ADVANCE" if c[-1]>ma and ma>prior else "STAGE_4_DECLINE" if c[-1]<ma and ma<prior else "STAGE_1_BASE" if c[-1]>=ma and ma<=prior else "STAGE_3_TOP" if c[-1]<=ma and ma>=prior else "UNCLASSIFIED"
        return self._record(5,instrument,strategy,now,snapshot.as_of_timestamp,stage,1.0,s.observation_ids,(),EvaluationEligibility.ELIGIBLE,(("long_ma",str(ma)),("prior_ma",str(prior))))

    def relative_strength(self,snapshot:AsOfSnapshot,instrument:str,benchmark:str,sector:str|None,peers:tuple[str,...],strategy:StrategyVersionReference,rules:RelativeStrengthRules,now:datetime)->EvaluatedDiagnostic:
        r=self.relative.calculate(snapshot,instrument_id=instrument,benchmark_instrument_id=benchmark,sector_instrument_id=sector,strategy_version=strategy,rules=rules,evaluated_at=now)
        return self._wrap(6,r,strategy,now,(("sector_available",str(r.sector_return is not None)),("peers_available",str(bool(peers)))))

    def market_structure(self,snapshot:AsOfSnapshot,instrument:str,strategy:StrategyVersionReference,pivot_window:int,now:datetime)->EvaluatedDiagnostic:
        r=self.technical.price_structure(snapshot,instrument_id=instrument,strategy_version=strategy,pivot_window=pivot_window,evaluated_at=now)
        result="HH_HL_BULLISH" if r.higher_high and r.higher_low else "LH_LL_BEARISH" if r.lower_high and r.lower_low else "MIXED" if r.status is AnalysisStatus.VALID else "INSUFFICIENT_DATA"
        return self._record(10,instrument,strategy,now,snapshot.as_of_timestamp,result,r.confidence,r.pivot_observation_ids,r.evidence,_eligibility(r.status),())

    def indicator_layer(self,snapshot:AsOfSnapshot,instrument:str,strategy:StrategyVersionReference,period:int,rsi_high:float,rsi_low:float,adx_strong:float,atr_high:float,now:datetime)->EvaluatedDiagnostic:
        rsi=self.technical.rsi(snapshot,instrument_id=instrument,strategy_version=strategy,period=period,evaluated_at=now); adx=self.technical.adx(snapshot,instrument_id=instrument,strategy_version=strategy,period=period,evaluated_at=now); atr=self.technical.atr(snapshot,instrument_id=instrument,strategy_version=strategy,period=period,evaluated_at=now)
        if any(x.status is not AnalysisStatus.VALID for x in (rsi,adx,atr)): return self._missing(39,instrument,strategy,now,"RSI, ADX, and ATR are all required")
        details=(("rsi",f"{rsi.value}:{'HIGH' if rsi.value>=rsi_high else 'LOW' if rsi.value<=rsi_low else 'MID'}"),("adx",f"{adx.value}:{'STRONG' if adx.value>=adx_strong else 'LOW'}"),("atr",f"{atr.value}:{'HIGH' if atr.value>=atr_high else 'NORMAL'}"))
        return self._record(39,instrument,strategy,now,snapshot.as_of_timestamp,"NEUTRAL",1.0,rsi.input_observation_ids+adx.input_observation_ids+atr.input_observation_ids,rsi.evidence+adx.evidence+atr.evidence,EvaluationEligibility.ELIGIBLE,details)

    def sector_health(self,snapshot,sector,benchmark,strategy,lookback,strong,weak,now):
        return self._simple(2,sector,strategy,now,snapshot,sector_health(snapshot,sector,benchmark,lookback,strong,weak))
    def sector_rotation(self,snapshot,sector,benchmark,strategy,lookback,strong,weak,now):
        return self._simple(3,sector,strategy,now,snapshot,sector_rotation(snapshot,sector,benchmark,lookback,strong,weak))
    def volume(self,snapshot,instrument,strategy,lookback,high,low,now): return self._simple(11,instrument,strategy,now,snapshot,volume_rvol(snapshot,instrument,lookback,high,low))
    def ichimoku(self,snapshot,instrument,strategy,tenkan,kijun,span_b,displacement,now): return self._simple(12,instrument,strategy,now,snapshot,ichimoku(snapshot,instrument,tenkan,kijun,span_b,displacement))
    def chikou(self,snapshot,instrument,strategy,tenkan,kijun,span_b,displacement,now):
        x=ichimoku(snapshot,instrument,tenkan,kijun,span_b,displacement); return self._simple(13,instrument,strategy,now,snapshot,x,(("chikou",dict(x.details).get("chikou","INSUFFICIENT_DATA")),),dict(x.details).get("chikou","INSUFFICIENT_DATA"))
    def mtf(self,timeframes,instrument,strategy,now,tenkan=2,kijun=3,span_b=4,displacement=1):
        available=[snapshot for snapshot in timeframes.values() if snapshot is not None]
        analysis=multi_timeframe_alignment(timeframes,instrument,tenkan,kijun,span_b,displacement)
        # Raw future/invalid observations take precedence over an otherwise
        # insufficient timeframe composition.  A caller cannot mask malformed
        # evidence by labelling one snapshot as more than one timeframe.
        if analysis.status is AnalysisStatus.INVALID_DATA:
            return self._simple(14,instrument,strategy,now,available[0] if available else None,analysis)
        identities=[(snapshot.id, tuple(sorted(item.id for item in snapshot.observations))) for snapshot in available]
        if len(available) < 2:return self._missing(14,instrument,strategy,now,"at least two distinct canonical timeframes are required")
        if len(set(identities)) != len(identities) or any(set(left[1]) & set(right[1]) for index,left in enumerate(identities) for right in identities[index + 1:]):
            return self._missing(14,instrument,strategy,now,"distinct canonical timeframe snapshots are required")
        return self._simple(14,instrument,strategy,now,available[0],analysis)
    def vwap(self,snapshot,instrument,strategy,now): return self._simple(35,instrument,strategy,now,snapshot,vwap(snapshot,instrument))
    def obv(self,snapshot,instrument,strategy,lookback,now): return self._simple(36,instrument,strategy,now,snapshot,obv(snapshot,instrument,lookback))
    def financial_trend(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(16,instrument,strategy,now,snapshot,five_year_trend(snapshot,instrument,rules))
    def return_ratios(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(17,instrument,strategy,now,snapshot,return_ratios(snapshot,instrument,rules))
    def cash_flow(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(18,instrument,strategy,now,snapshot,cash_flow(snapshot,instrument,rules))
    def leverage(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(19,instrument,strategy,now,snapshot,leverage(snapshot,instrument,rules))
    def working_capital(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(20,instrument,strategy,now,snapshot,working_capital(snapshot,instrument,rules))
    def ownership(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(21,instrument,strategy,now,snapshot,ownership(snapshot,instrument,rules))
    def institutional_holdings(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(22,instrument,strategy,now,snapshot,institutional(snapshot,instrument,rules))
    def earnings_acceleration(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(24,instrument,strategy,now,snapshot,earnings_acceleration(snapshot,instrument,rules))
    def latest_quarter(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(25,instrument,strategy,now,snapshot,latest_quarter(snapshot,instrument,rules))
    def margin_trajectory(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(26,instrument,strategy,now,snapshot,margins(snapshot,instrument,rules))
    def order_book(self,snapshot,instrument,strategy,rules:FundamentalRules,now): return self._simple(27,instrument,strategy,now,snapshot,order_book(snapshot,instrument,rules))
    def business_model_moat(self,snapshot,instrument,strategy,now): return self._simple(15,instrument,strategy,now,snapshot,moat(snapshot))
    def corporate_governance(self,snapshot,instrument,strategy,now): return self._simple(23,instrument,strategy,now,snapshot,governance(snapshot))
    def management_guidance(self,snapshot,instrument,strategy,now): return self._simple(28,instrument,strategy,now,snapshot,guidance_delivery(snapshot))
    def fundamental_catalysts(self,snapshot,instrument,strategy,now): return self._simple(30,instrument,strategy,now,snapshot,catalysts(snapshot))
    def valuation_multiples(self,market,financial,instrument,strategy,rules:ValuationRules,now): return self._simple(29,instrument,strategy,now,market,valuation(market,financial,instrument,rules))
    def base_pattern(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(37,instrument,strategy,now,snapshot,base_pattern(snapshot,instrument,rules))
    def pullback_quality(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(38,instrument,strategy,now,snapshot,pullback(snapshot,instrument,rules))
    def aggressive_entry(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(40,instrument,strategy,now,snapshot,aggressive_entry(snapshot,instrument,rules))
    def confirmation_entry(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(41,instrument,strategy,now,snapshot,confirmation_entry(snapshot,instrument,rules))
    def retest_entry(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(42,instrument,strategy,now,snapshot,retest_entry(snapshot,instrument,rules))
    def structural_stop(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(43,instrument,strategy,now,snapshot,structural_stop(snapshot,instrument,rules))
    def target_hierarchy(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(44,instrument,strategy,now,snapshot,targets(snapshot,instrument,rules))
    def risk_reward(self,snapshot,instrument,strategy,rules:TradeRules,entry,stop,target,now): return self._simple(45,instrument,strategy,now,snapshot,risk_reward(entry,stop,target,rules))
    def thesis_invalidation(self,snapshot,instrument,strategy,rules:TradeRules,now): return self._simple(46,instrument,strategy,now,snapshot,invalidation(snapshot,instrument,rules))
    def smart_money_proxies(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(7,instrument,strategy,now,snapshot,smart_money(snapshot,instrument,rules))
    def liquidity_pools(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(8,instrument,strategy,now,snapshot,pools(snapshot,instrument,rules))
    def wyckoff_phase(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(9,instrument,strategy,now,snapshot,wyckoff(snapshot,instrument,rules))
    def accumulation_distribution_proxy(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(50,instrument,strategy,now,snapshot,accumulation_distribution(snapshot,instrument,rules))
    def stop_clusters(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(51,instrument,strategy,now,snapshot,stop_clusters(snapshot,instrument,rules))
    def liquidity_events(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(52,instrument,strategy,now,snapshot,events(snapshot,instrument,rules))
    def bull_trap(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(53,instrument,strategy,now,snapshot,bull_trap(snapshot,instrument,rules))
    def bear_trap(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(54,instrument,strategy,now,snapshot,bear_trap(snapshot,instrument,rules))
    def volume_climax(self,snapshot,instrument,strategy,rules:LiquidityRules,now): return self._simple(58,instrument,strategy,now,snapshot,volume_climax(snapshot,instrument,rules))
    def crowd_sentiment(self,snapshot,instrument,strategy,rules:CrowdRules,now): return self._simple(47,instrument,strategy,now,snapshot,sentiment(snapshot,rules))
    def crowd_positioning(self,snapshot,instrument,strategy,rules:CrowdRules,now): return self._simple(48,instrument,strategy,now,snapshot,positioning(snapshot,rules))
    def crowd_data_confidence(self,snapshot,instrument,strategy,rules:CrowdRules,now): return self._simple(49,instrument,strategy,now,snapshot,crowd_confidence(snapshot,rules))
    def crowd_trap_probability(self,crowd,market,instrument,strategy,rules:CrowdRules,now): return self._simple(55,instrument,strategy,now,crowd,trap_probability(crowd,market,instrument,rules))
    def crowd_divergence(self,crowd,market,instrument,strategy,rules:CrowdRules,now): return self._simple(56,instrument,strategy,now,crowd,divergence(crowd,market,instrument,rules))
    def post_news_reaction(self,crowd,market,instrument,strategy,now): return self._simple(57,instrument,strategy,now,crowd,post_news(crowd,market,instrument))
    def contrarian_ichimoku(self,crowd_result,ichimoku_result,chikou_result,mtf_result,instrument,strategy,now): return self._simple(59,instrument,strategy,now,type("S",(),{"as_of_timestamp":crowd_result.record.as_of_timestamp})(),ichimoku_confluence(crowd_result,ichimoku_result,chikou_result,mtf_result))
    def contrarian_quality(self,trap,divergence_result,confluence,confidence_result,instrument,strategy,now): return self._simple(60,instrument,strategy,now,type("S",(),{"as_of_timestamp":trap.record.as_of_timestamp})(),contrarian_quality(trap,divergence_result,confluence,confidence_result))
    def contrarian_verdict(self,quality_result,confidence_result,instrument,strategy,now): return self._simple(61,instrument,strategy,now,type("S",(),{"as_of_timestamp":quality_result.record.as_of_timestamp})(),contrarian_verdict(quality_result,confidence_result))
    def comprehensive_risk(self,context,instrument,strategy,rules:SynthesisRules,now): return self._simple(31,instrument,strategy,now,context,synthesis_risk(context,rules))
    def trading_thesis(self,context,instrument,strategy,rules:SynthesisRules,now): return self._simple(32,instrument,strategy,now,context,synthesis_trading(context,rules))
    def investment_thesis(self,context,instrument,strategy,rules:SynthesisRules,now): return self._simple(33,instrument,strategy,now,context,synthesis_investment(context,rules))
    def scenarios(self,context,instrument,strategy,rules:SynthesisRules,now): return self._simple(34,instrument,strategy,now,context,synthesis_scenarios(context,rules))

    def _simple(self,rule,instrument,strategy,now,snapshot,x,extra=(),outcome=None):
        result=outcome or x.state; analysis_id=f"rule-{rule}|{instrument}|{strategy.strategy_id}|{strategy.version}|{snapshot.as_of_timestamp.isoformat()}|{'|'.join(x.input_ids)}|{result}"
        quality=DataQuality.UNKNOWN
        evidence=(
            analysis_evidence(analysis_id=analysis_id,evidence_type=EvidenceType.DATA,source="sector-volume-ichimoku-engine",timestamp=now,observation_ids=x.input_ids,content_reference=f"analysis://rule-{rule}/inputs",confidence=x.confidence,data_quality=quality),
            analysis_evidence(analysis_id=analysis_id,evidence_type=EvidenceType.INTERPRETATION,source="sector-volume-ichimoku-engine",timestamp=now,observation_ids=x.input_ids,content_reference=f"analysis://rule-{rule}/result/{result}",confidence=x.confidence,data_quality=quality),
        ) if x.status is AnalysisStatus.VALID else ()
        return self._record(rule,instrument,strategy,now,snapshot.as_of_timestamp,result,x.confidence,x.input_ids,evidence,_eligibility(x.status),x.details+tuple(extra))

    def _wrap(self,rule_id:int,r,strategy,now,extra=()): return self._record(rule_id,getattr(r,'instrument_id',getattr(r,'benchmark_instrument_id','market')),strategy,now,r.as_of_timestamp,getattr(r,'classification',None).value if getattr(r,'classification',None) else "INSUFFICIENT_DATA",r.confidence,r.input_observation_ids,r.evidence,_eligibility(r.status),extra)
    def _missing(self,rule_id,instrument,strategy,now,reason): return self._record(rule_id,instrument,strategy,now,now,"INSUFFICIENT_DATA",None,(),(),EvaluationEligibility.INELIGIBLE_MISSING_DATA,(("reason",reason),))
    def _record(self,rule_id,instrument,strategy,now,asof,result,confidence,ids,evidence,eligibility,details):
        rule=get_diagnostic_rule(rule_id); rec=DiagnosticResult(f"diagnostic-{rule_id}-{strategy.strategy_id}-{strategy.version}-{asof.isoformat()}",instrument,str(rule_id),strategy,result,None,confidence,tuple(x.id for x in evidence),tuple(ids),now,asof)
        return EvaluatedDiagnostic(rec,rule.rule_id,rule.calculation_version,eligibility,tuple(evidence),tuple(details))

def _eligibility(status:AnalysisStatus)->EvaluationEligibility:
    return EvaluationEligibility.ELIGIBLE if status is AnalysisStatus.VALID else EvaluationEligibility.INELIGIBLE_INVALID_DATA if status is AnalysisStatus.INVALID_DATA else EvaluationEligibility.INELIGIBLE_MISSING_DATA

class ComponentEligibilityService:
    _MAP={1:"market_regime",2:"sector_rotation",3:"sector_rotation",6:"relative_strength",7:"smart_money_evidence",8:"liquidity_smc_traps",9:"smart_money_evidence",10:"price_structure",11:"volume_obv_vwap",12:"ichimoku_mtf",13:"ichimoku_mtf",14:"ichimoku_mtf",15:"fundamental_business_quality",16:"earnings_acceleration",17:"valuation_risk_reward",18:"earnings_acceleration",19:"valuation_risk_reward",20:"valuation_risk_reward",21:"smart_money_evidence",22:"smart_money_evidence",23:"governance_risk",24:"earnings_acceleration",25:"earnings_acceleration",26:"earnings_acceleration",27:"earnings_acceleration",28:"earnings_acceleration",29:"valuation_risk_reward",30:"earnings_acceleration",31:"valuation_risk_reward",32:"price_structure",33:"fundamental_business_quality",34:"valuation_risk_reward",35:"volume_obv_vwap",36:"volume_obv_vwap",37:"price_structure",38:"price_structure",39:"price_structure",40:"price_structure",41:"price_structure",42:"price_structure",43:"valuation_risk_reward",44:"valuation_risk_reward",45:"valuation_risk_reward",46:"price_structure",47:"crowd_contrarian_evidence",48:"crowd_contrarian_evidence",49:"crowd_contrarian_evidence",50:"smart_money_evidence",51:"liquidity_smc_traps",52:"liquidity_smc_traps",53:"liquidity_smc_traps",54:"liquidity_smc_traps",55:"liquidity_smc_traps",56:"smart_money_evidence",57:"smart_money_evidence",58:"volume_obv_vwap",59:"smart_money_evidence",60:"smart_money_evidence",61:"smart_money_evidence"}
    def assess(self,d:EvaluatedDiagnostic)->ComponentContributionEligibility:
        component=self._MAP.get(d.canonical_rule_id,"unmapped")
        if d.eligibility is not EvaluationEligibility.ELIGIBLE: return ComponentContributionEligibility(component,ComponentEligibility.INELIGIBLE,d.eligibility.value,(),d.record.confidence)
        return ComponentContributionEligibility(component,ComponentEligibility.ELIGIBLE,"Evidence and required inputs are present.",(),d.record.confidence)
