from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.backtest.serialization import dump
from .oos_aggregation import *


def _decimal(value): return Decimal(value) if value is not None else None
def config_from(value: dict[str, Any]):
    value=dict(value)
    for key in ("minimum_coverage_ratio","minimum_benchmark_coverage_ratio","max_window_drawdown","max_return_dispersion","max_expectancy_degradation"): value[key]=_decimal(value[key])
    return WalkForwardValidationConfig(**value)
def observation_from(value: dict[str, Any]):
    value=dict(value); value["timestamp"]=datetime.fromisoformat(value["timestamp"]); value["equity"]=Decimal(value["equity"]); value["rebasing_factor"]=Decimal(value["rebasing_factor"]); return OOSStitchedEquityObservation(**value)
def series_from(value: dict[str, Any]):
    value=dict(value); value["ordered_window_result_ids"]=tuple(value["ordered_window_result_ids"]); value["source_equity_series_ids"]=tuple(value["source_equity_series_ids"]); value["observation_ids"]=tuple(value["observation_ids"]); value["methodology"]=OOSCapitalStitchingMethodology(value["methodology"]); value["warnings"]=tuple(value["warnings"]); return WalkForwardOOSEquitySeries(**value)
def degradation_from(value: dict[str, Any]):
    value=dict(value)
    for key in ("pre_test_end","test_start"): value[key]=datetime.fromisoformat(value[key])
    for key in ("return_difference","return_ratio","expectancy_difference","sharpe_difference","drawdown_worsening","win_rate_difference","profit_factor_difference"): value[key]=_decimal(value[key])
    value["warnings"]=tuple(value["warnings"]); return ValidationDegradationAnalysis(**value)
def aggregate_from(value: dict[str, Any]):
    value=dict(value)
    for key in ("coverage_ratio","starting_aggregate_equity","ending_aggregate_equity","compounded_oos_return","cagr","maximum_drawdown","sharpe","sortino","expectancy","profit_factor","win_rate","average_r","turnover","total_costs","capital_efficiency"): value[key]=_decimal(value[key])
    for key in ("oos_start","oos_end"):
        value[key]=datetime.fromisoformat(value[key]) if value[key] else None
    value["ordered_window_result_ids"]=tuple(value["ordered_window_result_ids"]); value["degradation_analysis_ids"]=tuple(value["degradation_analysis_ids"]); value["capital_stitching_methodology"]=OOSCapitalStitchingMethodology(value["capital_stitching_methodology"]); value["benchmark_alignment"]=BenchmarkAlignmentStatus(value["benchmark_alignment"]); value["status"]=AggregateValidationStatus(value["status"]); value["warnings"]=tuple(value["warnings"])
    def restore(item):
        if isinstance(item,dict): return {key:restore(nested) for key,nested in item.items()}
        if isinstance(item,list): return [restore(nested) for nested in item]
        if isinstance(item,str):
            try: return Decimal(item)
            except Exception: return item
        return item
    value["stability_metrics"]=restore(value["stability_metrics"]); value["regime_metrics"]=restore(value["regime_metrics"]); value["benchmark_relative_metrics"]=restore(value["benchmark_relative_metrics"])
    return WalkForwardAggregateResult(**value)
