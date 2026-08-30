from __future__ import annotations
from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal
from enum import Enum

class PaperTradeState(str, Enum):
    CREATED="CREATED"; WAITING_FOR_TRIGGER="WAITING_FOR_TRIGGER"; TRIGGERED="TRIGGERED"; OPEN="OPEN"; PARTIALLY_EXITED="PARTIALLY_EXITED"; CLOSED_TARGET="CLOSED_TARGET"; CLOSED_STOP="CLOSED_STOP"; CLOSED_INVALIDATION="CLOSED_INVALIDATION"; CLOSED_EXPIRY="CLOSED_EXPIRY"; CANCELLED="CANCELLED"; UNFILLED="UNFILLED"; INSUFFICIENT_DATA="INSUFFICIENT_DATA"
class CreationPolicy(str, Enum): GENERATED="GENERATED"; TRIGGERED_ONLY="TRIGGERED_ONLY"
class FillMethod(str, Enum): MARKETABLE_TRIGGER_FILL="MARKETABLE_TRIGGER_FILL"; LIMIT_ZONE_FILL="LIMIT_ZONE_FILL"
class SameBarPolicy(str, Enum): CONSERVATIVE_STOP_FIRST="CONSERVATIVE_STOP_FIRST"; OPTIMISTIC_TARGET_FIRST="OPTIMISTIC_TARGET_FIRST"; UNRESOLVED="UNRESOLVED"; LOWER_TIMEFRAME_REQUIRED="LOWER_TIMEFRAME_REQUIRED"
class GapPolicy(str, Enum): MARKET_OPEN="MARKET_OPEN"; LEVEL="LEVEL"
class SizingBasis(str, Enum): UNIT_BASIS="UNIT_BASIS"; FIXED_NOTIONAL="FIXED_NOTIONAL"; FIXED_R_R="FIXED_R_R"
class InvalidationPolicy(str, Enum): EXIT_ON_INVALIDATION="EXIT_ON_INVALIDATION"; RECORD_ONLY="RECORD_ONLY"
class PaperEventType(str, Enum): CREATED="CREATED"; TRIGGERED="TRIGGERED"; FILLED="FILLED"; T1="T1"; T2="T2"; STOP="STOP"; INVALIDATION="INVALIDATION"; EXPIRED="EXPIRED"; CANCELLED="CANCELLED"; AMBIGUOUS="AMBIGUOUS"
@dataclass(frozen=True, slots=True)
class PaperTradingConfig:
    version:str; creation_policy:CreationPolicy; fill_method:FillMethod; same_bar_policy:SameBarPolicy; gap_policy:GapPolicy; sizing_basis:SizingBasis; entry_slippage:Decimal|None; exit_slippage:Decimal|None; cost_model_version:str|None; fees_per_unit:Decimal|None; initial_tranche:Decimal|None; t1_reduction:Decimal|None; move_stop_breakeven:bool|None; invalidation_policy:InvalidationPolicy|None; setup_expiry_sessions:int|None; time_stop_sessions:int|None; timeframe:str|None
    def unresolved(self): return tuple(item.name for item in fields(self) if item.name != "version" and getattr(self,item.name) is None)
@dataclass(frozen=True, slots=True)
class PaperBar:
    bar_id:str; timestamp:datetime; known_at:datetime; open:Decimal; high:Decimal; low:Decimal; close:Decimal; timeframe:str; valid:bool=True; stale:bool=False
@dataclass(frozen=True, slots=True)
class PaperTrade:
    paper_trade_id:str; source_signal_id:str; instrument_id:str; strategy_version:object; registry_version:str; scoring_configuration_version:str; gate_configuration_version:str; rotation_configuration_version:str|None; signal_configuration_version:str; paper_configuration_version:str; portfolio_context_reference:str|None; created_at:datetime; as_of_timestamp:datetime; entry_type:str|None; planned_entry:Decimal|None; entry_zone_low:Decimal|None; entry_zone_high:Decimal|None; structural_stop:Decimal|None; target_1:Decimal|None; target_2:Decimal|None; extended_target:Decimal|None; initial_risk_reward:Decimal|None; decision_score:Decimal|None; data_confidence:float|None; market_regime:str|None; sector:str|None; catalyst:str|None; catalyst_clock:str|None; trading_thesis_reference:str|None; investment_thesis_reference:str|None; invalidation_reference:str|None; gate_status:str|None; rotation_context:str|None; warnings:tuple[str,...]
@dataclass(frozen=True, slots=True)
class PaperFill:
    fill_id:str; paper_trade_id:str; timestamp:datetime; price:Decimal; quantity:Decimal; methodology:FillMethod; slippage:Decimal; fees:Decimal; source_bar_ids:tuple[str,...]
@dataclass(frozen=True, slots=True)
class PaperLifecycleEvent:
    event_id:str; paper_trade_id:str; event_type:PaperEventType; timestamp:datetime; state:PaperTradeState; reason:str; bar_ids:tuple[str,...]
@dataclass(frozen=True, slots=True)
class PaperOutcome:
    paper_trade_id:str; state:PaperTradeState; triggered:bool; filled:bool; entry_price:Decimal|None; entry_timestamp:datetime|None; final_exit_price:Decimal|None; final_exit_timestamp:datetime|None; gross_pnl:Decimal|None; costs:Decimal; net_pnl:Decimal|None; percentage_return:Decimal|None; r_multiple:Decimal|None; mfe:Decimal|None; mae:Decimal|None; mfe_r:Decimal|None; mae_r:Decimal|None; t1_reached:bool; t2_reached:bool; stop_hit:bool; invalidated:bool; expiry:bool; price_bar_ids:tuple[str,...]
