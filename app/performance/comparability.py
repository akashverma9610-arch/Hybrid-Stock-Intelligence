from dataclasses import dataclass
from decimal import Decimal
@dataclass(frozen=True,slots=True)
class PreviousVersionComparison:
 current_report_id:str;prior_report_id:str;current_strategy_version:str;prior_strategy_version:str;current_window:tuple[str,str];prior_window:tuple[str,str];comparison_window:tuple[str,str]|None;compatible:bool;warnings:tuple[str,...]
@dataclass(frozen=True,slots=True)
class CostModelComparison:
 strategy_gross:Decimal|None;strategy_net:Decimal|None;benchmark_gross:Decimal|None;benchmark_net:Decimal|None;strategy_cost_version:str;benchmark_cost_version:str;warnings:tuple[str,...]
def previous_version(current_report,prior_report,current_version,prior_version):
 same=(current_report.start,current_report.end)==(prior_report.start,prior_report.end);return PreviousVersionComparison(current_report.report_id,prior_report.report_id,str(current_version),str(prior_version),(current_report.start.isoformat(),current_report.end.isoformat()),(prior_report.start.isoformat(),prior_report.end.isoformat()),(current_report.start.isoformat(),current_report.end.isoformat()) if same else None,same,() if same else ("WINDOW_DIFFERS",))
def cost_fairness(strategy_gross,strategy_net,benchmark_gross,benchmark_net,strategy_version,benchmark_version,buy_hold=False):
 warnings=[]
 if strategy_version!=benchmark_version:warnings.append("COST_MODELS_DIFFER")
 if buy_hold:warnings.append("TURNOVER_ASSUMPTIONS_DIFFER")
 return CostModelComparison(strategy_gross,strategy_net,benchmark_gross,benchmark_net,strategy_version,benchmark_version,tuple(warnings))
