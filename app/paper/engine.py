from __future__ import annotations
import hashlib
from decimal import Decimal
from app.gates.engine import ExchangeCalendar
from app.signals.models import SignalRecord, SignalStatus, TradePlan
from .models import *
class PaperTradingEngine:
 def __init__(self, config:PaperTradingConfig, calendar:ExchangeCalendar): self.config,self.calendar=config,calendar
 def create(self, signal:SignalRecord, plan:TradePlan, *, instrument_id:str, generated_at, market_regime=None, sector=None):
  if self.config.unresolved(): raise ValueError("Paper-trading configuration has unresolved parameters.")
  if self.config.creation_policy is CreationPolicy.TRIGGERED_ONLY and signal.status is not SignalStatus.TRIGGERED_ANALYTICALLY: raise ValueError("Configuration permits paper creation only after analytical trigger.")
  return PaperTrade("paper-"+hashlib.sha256((signal.signal_id+self.config.version).encode()).hexdigest()[:20],signal.signal_id,instrument_id,signal.strategy_version,signal.registry_version,signal.scoring_configuration_version,signal.gate_configuration_version,signal.rotation_configuration_version,"signal-config",self.config.version,signal.portfolio_snapshot_id,generated_at,signal.as_of_timestamp,plan.entry_type.value if plan.entry_type else None,plan.entry_price,plan.entry_zone_low,plan.entry_zone_high,plan.structural_stop,plan.target_1,plan.target_2,plan.extended_target,plan.risk_reward_t1,None,signal.data_confidence,market_regime,sector,plan.catalyst,plan.catalyst_clock,plan.thesis_reference,None,plan.exact_invalidation,signal.execution_gate_evaluation_id,signal.portfolio_rotation_evaluation_id,signal.warnings)
 def simulate(self, trade:PaperTrade, bars:tuple[PaperBar,...], as_of, *, invalidation_at=None, cancellation_at=None):
  bars=tuple(x for x in sorted(bars,key=lambda x:(x.timestamp,x.bar_id)) if x.timestamp<=as_of and x.known_at<=as_of)
  events=[PaperLifecycleEvent("created-"+trade.paper_trade_id,trade.paper_trade_id,PaperEventType.CREATED,trade.created_at,PaperTradeState.WAITING_FOR_TRIGGER,"hypothetical setup retained",())]; fills=[]
  if any(not x.valid or x.stale or x.timeframe!=self.config.timeframe for x in bars): return events, fills, self._out(trade,PaperTradeState.INSUFFICIENT_DATA,False,False,None,None,None,None,None,Decimal("0"),False,False,False,False,False,())
  entry=None; entrybar=None; qty=Decimal("1"); t1=False;t2=False;stop=False;invalid=False;expiry=False; partial=Decimal("0"); exitprice=None; exitbar=None; mfe=mae=None; active_stop=trade.structural_stop
  for b in bars:
   if cancellation_at and cancellation_at<=b.timestamp and entry is None: events.append(self._ev(trade,PaperEventType.CANCELLED,b,PaperTradeState.CANCELLED,"catalyst/signal cancelled")); return events,fills,self._out(trade,PaperTradeState.CANCELLED,False,False,None,None,None,None,None,Decimal("0"),False,False,False,False,False,tuple(x.bar_id for x in bars if x.timestamp<=b.timestamp))
   if entry is None:
    if self._entry_touch(trade,b):
     entry=(b.close+self.config.entry_slippage if self.config.fill_method is FillMethod.MARKETABLE_TRIGGER_FILL else trade.planned_entry); entrybar=b; fills.append(PaperFill("fill-"+trade.paper_trade_id,b.paper_trade_id if False else trade.paper_trade_id,b.timestamp,entry,qty,self.config.fill_method,self.config.entry_slippage,self.config.fees_per_unit,(b.bar_id,))); events += [self._ev(trade,PaperEventType.TRIGGERED,b,PaperTradeState.TRIGGERED,"trigger known at bar close"),self._ev(trade,PaperEventType.FILLED,b,PaperTradeState.OPEN,"hypothetical fill")]; continue
    if self.calendar.sessions_between(trade.created_at.date(),b.timestamp.date())>self.config.setup_expiry_sessions: events.append(self._ev(trade,PaperEventType.EXPIRED,b,PaperTradeState.UNFILLED,"setup expiry before fill")); return events,fills,self._out(trade,PaperTradeState.UNFILLED,False,False,None,None,None,None,None,Decimal("0"),False,False,False,False,True,tuple(x.bar_id for x in bars if x.timestamp<=b.timestamp))
    continue
   risk=entry-trade.structural_stop
   if risk<=0: return events,fills,self._out(trade,PaperTradeState.INSUFFICIENT_DATA,True,False,entry,b.timestamp,None,None,None,Decimal("0"),False,False,False,False,False,(b.bar_id,))
   mfe=max(mfe or b.high-entry,b.high-entry);mae=min(mae or b.low-entry,b.low-entry)
   if invalidation_at and invalidation_at<=b.timestamp and self.config.invalidation_policy is InvalidationPolicy.EXIT_ON_INVALIDATION: invalid=True;exitprice=b.close-self.config.exit_slippage;exitbar=b;events.append(self._ev(trade,PaperEventType.INVALIDATION,b,PaperTradeState.CLOSED_INVALIDATION,"configured invalidation exit"));break
   hitstop=b.low<=active_stop; hitt1=not t1 and trade.target_1 is not None and b.high>=trade.target_1
   if hitstop and hitt1 and self.config.same_bar_policy in {SameBarPolicy.UNRESOLVED,SameBarPolicy.LOWER_TIMEFRAME_REQUIRED}: events.append(self._ev(trade,PaperEventType.AMBIGUOUS,b,PaperTradeState.INSUFFICIENT_DATA,"same-bar stop/target ordering unresolved")); return events,fills,self._out(trade,PaperTradeState.INSUFFICIENT_DATA,True,True,entry,entrybar.timestamp,None,None,None,Decimal("0"),t1,t2,False,False,False,tuple(x.bar_id for x in bars if x.timestamp<=b.timestamp))
   if hitstop and (not hitt1 or self.config.same_bar_policy is SameBarPolicy.CONSERVATIVE_STOP_FIRST): stop=True;exitprice=(b.open if b.open<active_stop and self.config.gap_policy is GapPolicy.MARKET_OPEN else active_stop)-self.config.exit_slippage;exitbar=b;events.append(self._ev(trade,PaperEventType.STOP,b,PaperTradeState.CLOSED_STOP,"hypothetical breakeven residual stop" if active_stop==entry else "hypothetical stop"));break
   if hitt1:
    t1=True;partial=qty*self.config.t1_reduction;events.append(self._ev(trade,PaperEventType.T1,b,PaperTradeState.PARTIALLY_EXITED,"T1 partial simulated"));
    if self.config.move_stop_breakeven: active_stop=entry
   if trade.target_2 is not None and b.high>=trade.target_2: t2=True;exitprice=trade.target_2-self.config.exit_slippage;exitbar=b;events.append(self._ev(trade,PaperEventType.T2,b,PaperTradeState.CLOSED_TARGET,"T2 simulated"));break
   if self.calendar.sessions_between(entrybar.timestamp.date(),b.timestamp.date())>self.config.time_stop_sessions: expiry=True;exitprice=b.close-self.config.exit_slippage;exitbar=b;events.append(self._ev(trade,PaperEventType.EXPIRED,b,PaperTradeState.CLOSED_EXPIRY,"post-entry time stop"));break
  if entry is None: return events,fills,self._out(trade,PaperTradeState.WAITING_FOR_TRIGGER,False,False,None,None,None,None,None,Decimal("0"),False,False,False,False,False,tuple(x.bar_id for x in bars))
  state=PaperTradeState.CLOSED_INVALIDATION if invalid else PaperTradeState.CLOSED_STOP if stop else PaperTradeState.CLOSED_EXPIRY if expiry else PaperTradeState.CLOSED_TARGET if exitprice is not None else PaperTradeState.PARTIALLY_EXITED if t1 else PaperTradeState.OPEN
  return events,fills,self._out(trade,state,True,True,entry,entrybar.timestamp,exitprice,exitbar.timestamp if exitbar else None,(exitprice-entry)*(qty-partial)+(trade.target_1-entry)*partial if exitprice is not None else None,self.config.fees_per_unit*(qty+(qty-partial if exitprice else 0)),t1,t2,stop,invalid,expiry,tuple(x.bar_id for x in bars if x.timestamp<=(exitbar.timestamp if exitbar else as_of)),mfe,mae)
 def _entry_touch(self,t,b):
  if self.config.fill_method is FillMethod.MARKETABLE_TRIGGER_FILL:return t.planned_entry is not None and b.close>t.planned_entry
  return t.entry_zone_low is not None and t.entry_zone_high is not None and b.low<=t.entry_zone_high and b.high>=t.entry_zone_low
 def _ev(self,t,k,b,s,r):return PaperLifecycleEvent(f"{k.value}-{t.paper_trade_id}-{b.bar_id}",t.paper_trade_id,k,b.timestamp,s,r,(b.bar_id,))
 def _out(self,t,state,triggered,filled,entry,ets,exitp,xts,gross,costs,t1,t2,stop,inv,expiry,ids,mfe=None,mae=None):
  net=(gross-costs if gross is not None else None);risk=(entry-t.structural_stop if entry is not None and t.structural_stop is not None else None);return PaperOutcome(t.paper_trade_id,state,triggered,filled,entry,ets,exitp,xts,gross,costs,net,net/entry if net is not None and entry else None,net/risk if net is not None and risk and risk>0 else None,mfe,mae,mfe/risk if mfe is not None and risk and risk>0 else None,mae/risk if mae is not None and risk and risk>0 else None,t1,t2,stop,inv,expiry,ids)
