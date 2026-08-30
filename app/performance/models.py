from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
class SampleStatus(str,Enum): VERY_LOW_SAMPLE="VERY_LOW_SAMPLE"; LOW_SAMPLE="LOW_SAMPLE"; MODERATE_SAMPLE="MODERATE_SAMPLE"; ADEQUATE_SAMPLE="ADEQUATE_SAMPLE"
@dataclass(frozen=True,slots=True)
class PerformanceConfig:
 version:str; starting_capital:Decimal; annualization_factor:int; risk_free_rate:Decimal; low_sample:int; moderate_sample:int; adequate_sample:int; score_bands:tuple[Decimal,...]
@dataclass(frozen=True,slots=True)
class TradePerformanceRecord:
 paper_trade_id:str; final_state:str; entry_timestamp:datetime|None; exit_timestamp:datetime|None; net_pnl:Decimal|None; gross_pnl:Decimal|None; r_multiple:Decimal|None; decision_score:Decimal|None; confidence:float|None; regime:str|None; sector:str|None; setup_type:str|None; costs:Decimal; mfe:Decimal|None; mae:Decimal|None; catalyst_type:str|None=None; catalyst_clock:str|None=None; holding_sessions:int|None=None; triggered:bool=False; filled:bool=False; t1_hit:bool=False; t2_hit:bool=False; extended_target_hit:bool=False; stop_hit:bool=False; breakeven_residual:bool|None=None; invalidation_exit:bool=False; time_stop_exit:bool=False; mfe_r:Decimal|None=None; mae_r:Decimal|None=None
 @property
 def closed(self): return self.final_state.startswith("CLOSED_")
@dataclass(frozen=True,slots=True)
class EquityPoint: timestamp:datetime; equity:Decimal; drawdown:Decimal; trade_id:str
@dataclass(frozen=True,slots=True)
class PerformanceReport:
 report_id:str; strategy_version:object; start:datetime; end:datetime; config_version:str; trade_ids:tuple[str,...]; metrics:dict; equity_curve:tuple[EquityPoint,...]; groups:dict; warnings:tuple[str,...]; generated_at:datetime; benchmark_run_ids:tuple[str,...]=(); comparison_ids:tuple[str,...]=(); methodology_notes:tuple[str,...]=()
@dataclass(frozen=True,slots=True)
class PerformanceEvaluationDataset:
 dataset_id:str;strategy_version:object;registry_version:str;scoring_version:str;gate_version:str;rotation_version:str|None;signal_version:str;paper_version:str;evaluation_version:str;start:datetime;end:datetime;paper_trade_ids:tuple[str,...];signal_ids:tuple[str,...];benchmark_input_ids:tuple[str,...];benchmark_versions:tuple[str,...];cost_model_version:str;calendar_id:str;as_of_metadata:str
@dataclass(frozen=True,slots=True)
class BenchmarkComparison:
 benchmark_id:str;benchmark_version:str;strategy_return:Decimal|None;benchmark_return:Decimal|None;excess_return:Decimal|None;strategy_cagr:Decimal|None;benchmark_cagr:Decimal|None;strategy_drawdown:Decimal|None;benchmark_drawdown:Decimal|None;strategy_sharpe:Decimal|None;benchmark_sharpe:Decimal|None;strategy_sortino:Decimal|None;benchmark_sortino:Decimal|None;strategy_volatility:Decimal|None;benchmark_volatility:Decimal|None;strategy_costs:Decimal|None;benchmark_costs:Decimal|None;strategy_efficiency:Decimal|None;benchmark_efficiency:Decimal|None;fairness_warnings:tuple[str,...];sample_warnings:tuple[str,...];classification:str
