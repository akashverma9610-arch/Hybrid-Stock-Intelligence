from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from statistics import median, pstdev

from app.historical.guard import manifest_fingerprint
from .walk_forward import WalkForwardWindowResultStatus


class OOSCapitalStitchingMethodology(str, Enum):
    CHAIN_WINDOW_RETURNS = "CHAIN_WINDOW_RETURNS"


class AggregateValidationStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    DEGRADED = "DEGRADED"
    UNSTABLE = "UNSTABLE"
    FAILED_AUDIT = "FAILED_AUDIT"


class BenchmarkAlignmentStatus(str, Enum):
    ALIGNED = "ALIGNED"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class WalkForwardValidationConfig:
    config_id: str; version: str; minimum_planned_windows: int; minimum_valid_oos_windows: int; minimum_coverage_ratio: Decimal
    minimum_oos_sessions: int; minimum_oos_trades: int; minimum_benchmark_coverage_ratio: Decimal | None
    max_window_drawdown: Decimal | None; max_return_dispersion: Decimal | None; max_expectancy_degradation: Decimal | None
    methodology_version: str; fingerprint: str


@dataclass(frozen=True, slots=True)
class OOSStitchedEquityObservation:
    observation_id: str; walk_forward_run_id: str; window_result_id: str; source_equity_series_id: str | None
    source_point_id: str | None; timestamp: datetime; equity: Decimal; rebasing_factor: Decimal; fingerprint: str


@dataclass(frozen=True, slots=True)
class WalkForwardOOSEquitySeries:
    series_id: str; walk_forward_run_id: str; ordered_window_result_ids: tuple[str, ...]; source_equity_series_ids: tuple[str, ...]
    observation_ids: tuple[str, ...]; methodology: OOSCapitalStitchingMethodology; methodology_version: str; warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class HistoricalBenchmarkObservation:
    observation_id: str; benchmark_run_id: str; session: str; timestamp: datetime; value: Decimal; source_observation_id: str; seed: int | None; fingerprint: str


@dataclass(frozen=True, slots=True)
class ValidationDegradationAnalysis:
    analysis_id: str; walk_forward_run_id: str; window_result_id: str; pre_test_report_id: str; test_report_id: str
    pre_test_end: datetime; test_start: datetime; return_difference: Decimal | None; return_ratio: Decimal | None
    expectancy_difference: Decimal | None; sharpe_difference: Decimal | None; drawdown_worsening: Decimal | None
    win_rate_difference: Decimal | None; profit_factor_difference: Decimal | None; warnings: tuple[str, ...]; fingerprint: str


@dataclass(frozen=True, slots=True)
class WalkForwardAggregateResult:
    aggregate_result_id: str; walk_forward_run_id: str; ordered_window_result_ids: tuple[str, ...]; validation_config_id: str
    aggregation_methodology: str; capital_stitching_methodology: OOSCapitalStitchingMethodology; oos_equity_series_id: str
    degradation_analysis_ids: tuple[str, ...]; valid_window_count: int; insufficient_window_count: int; failed_window_count: int
    benchmark_covered_window_count: int; total_planned_window_count: int; coverage_ratio: Decimal; oos_start: datetime | None; oos_end: datetime | None
    starting_aggregate_equity: Decimal; ending_aggregate_equity: Decimal; compounded_oos_return: Decimal | None; cagr: Decimal | None
    maximum_drawdown: Decimal | None; sharpe: Decimal | None; sortino: Decimal | None; expectancy: Decimal | None; profit_factor: Decimal | None
    win_rate: Decimal | None; average_r: Decimal | None; trade_count: int; turnover: Decimal | None; total_costs: Decimal | None
    capital_efficiency: Decimal | None; stability_metrics: dict; regime_metrics: dict; benchmark_alignment: BenchmarkAlignmentStatus
    benchmark_relative_metrics: dict; status: AggregateValidationStatus; warnings: tuple[str, ...]; fingerprint: str


class WalkForwardAggregationService:
    """Pure TEST-only aggregation over immutable WindowResults and Phase 8A artifacts."""
    methodology_version = "walk-forward-oos-aggregation-v1"

    def __init__(self, repository, *, annualization_factor: int = 252, risk_free_rate: Decimal = Decimal("0")) -> None:
        self.repository, self.annualization_factor, self.risk_free_rate = repository, annualization_factor, risk_free_rate

    def aggregate(self, *, run_id: str, config: WalkForwardValidationConfig, generated_at: datetime, pre_test_report_ids: dict[str, str] | None = None) -> WalkForwardAggregateResult:
        result, series, observations, degradations = self.build(run_id=run_id, config=config, generated_at=generated_at, pre_test_report_ids=pre_test_report_ids or {})
        if self.repository.get_walk_forward_validation_config(config.config_id) is None: self.repository.save_walk_forward_validation_config(config)
        self.repository.save_walk_forward_oos_equity_series(series)
        for observation in observations: self.repository.save_oos_stitched_equity_observation(observation)
        for degradation in degradations: self.repository.save_validation_degradation_analysis(degradation)
        self.repository.save_walk_forward_aggregate_result(result)
        return result

    def build(self, *, run_id: str, config: WalkForwardValidationConfig, generated_at: datetime, pre_test_report_ids: dict[str, str]) -> tuple[WalkForwardAggregateResult, WalkForwardOOSEquitySeries, tuple[OOSStitchedEquityObservation, ...], tuple[ValidationDegradationAnalysis, ...]]:
        run=self.repository.get_walk_forward_run(run_id)
        if run is None: raise ValueError("Walk-forward run does not exist.")
        results_by_window={item.walk_forward_window_id:item for item in self.repository.list_walk_forward_window_results(run_id)}
        results=tuple(results_by_window.get(identifier) for identifier in run.ordered_window_ids)
        if any(item is None for item in results): raise ValueError("Every planned window must retain a terminal WindowResult before OOS aggregation.")
        results=tuple(results)
        windows=tuple(self.repository.get_walk_forward_window(item.walk_forward_window_id) for item in results)
        if any(item is None for item in windows): raise ValueError("OOS aggregation has missing frozen windows.")
        windows=tuple(windows)
        for prior, current in zip(windows, windows[1:]):
            if current.test.start <= prior.test.end: raise ValueError("Overlapping TEST windows cannot be aggregated in V1.")
        valid=tuple(item for item in results if item.status in {WalkForwardWindowResultStatus.COMPLETED, WalkForwardWindowResultStatus.COMPLETED_WITH_WARNINGS} and item.absolute_return is not None)
        insufficient=sum(item.status is WalkForwardWindowResultStatus.INSUFFICIENT for item in results)
        failed=sum(item.status in {WalkForwardWindowResultStatus.FAILED,WalkForwardWindowResultStatus.FAILED_AUDIT} for item in results)
        warnings=[]; capital=Decimal("1"); observations=[]; source_series_ids=[]; returns=[]
        for item in valid:
            window_series=self._equity_series_for_report(item.performance_report_id)
            if window_series is None:
                capital=capital*(Decimal("1")+item.absolute_return); returns.append(item.absolute_return)
                observations.append(self._observation(run_id,item,None,None,item.test_end,capital,Decimal("1")+item.absolute_return))
                warnings.append(f"SESSION_EQUITY_UNAVAILABLE:{item.result_id}")
                continue
            source_series_ids.append(window_series.series_id)
            points=tuple(self.repository.get_historical_equity_point(point_id) for point_id in window_series.point_ids)
            if any(point is None for point in points) or not points or points[0].equity <= 0:
                raise ValueError("OOS source equity series is incomplete.")
            points=tuple(points); base=points[0].equity; factor=capital/base
            for point in points:
                rebased=point.equity*factor
                if observations and point.evaluation_timestamp <= observations[-1].timestamp: raise ValueError("OOS equity points must be strictly ordered and non-overlapping.")
                if observations: returns.append(rebased/observations[-1].equity-1)
                observations.append(self._observation(run_id,item,window_series.series_id,point.point_id,point.evaluation_timestamp,rebased,factor))
            capital=observations[-1].equity
        if not observations and valid:
            raise ValueError("Valid OOS results must supply a return or frozen session equity.")
        trade_records=self._test_trade_records(valid)
        if len({item[0] for item in trade_records}) != len(trade_records): raise ValueError("Duplicate paper-trade ID across OOS windows.")
        metrics=self._metrics(observations, trade_records)
        window_returns=[item.absolute_return for item in valid]
        stability=self._stability(valid,window_returns)
        degradations=tuple(self._degradation(run_id,item,pre_test_report_ids[item.result_id]) for item in valid if item.result_id in pre_test_report_ids)
        warnings.extend(warning for analysis in degradations for warning in analysis.warnings)
        covered=sum(item.benchmark_comparison_id is not None for item in results)
        benchmark_alignment=self._benchmark_alignment(valid)
        if config.minimum_benchmark_coverage_ratio is not None and (Decimal(covered)/len(valid) if valid else Decimal("0")) < config.minimum_benchmark_coverage_ratio: warnings.append("BENCHMARK_COVERAGE_INSUFFICIENT")
        coverage=Decimal(len(valid))/len(results) if results else Decimal("0")
        warnings.extend(self._warnings(config,valid,coverage,metrics,stability,degradations))
        status=self._status(config,valid,coverage,metrics,warnings)
        series=WalkForwardOOSEquitySeries("oos-series-"+manifest_fingerprint(run=run_id,results=[item.fingerprint for item in results])[:24],run_id,tuple(item.result_id for item in results),tuple(source_series_ids),tuple(item.observation_id for item in observations),OOSCapitalStitchingMethodology.CHAIN_WINDOW_RETURNS,self.methodology_version,tuple(sorted(set(warnings))),manifest_fingerprint(run=run_id,observations=[item.fingerprint for item in observations],method=self.methodology_version))
        result=WalkForwardAggregateResult("oos-aggregate-"+manifest_fingerprint(run=run_id,series=series.fingerprint,config=config.fingerprint)[:24],run_id,tuple(item.result_id for item in results),config.config_id,self.methodology_version,OOSCapitalStitchingMethodology.CHAIN_WINDOW_RETURNS,series.series_id,tuple(item.analysis_id for item in degradations),len(valid),insufficient,failed,covered,len(results),coverage,observations[0].timestamp if observations else None,observations[-1].timestamp if observations else None,Decimal("1"),capital,metrics["return"],metrics["cagr"],metrics["drawdown"],metrics["sharpe"],metrics["sortino"],metrics["expectancy"],metrics["profit_factor"],metrics["win_rate"],metrics["average_r"],len(trade_records),metrics["turnover"],metrics["costs"],metrics["return"],stability,{},benchmark_alignment,{},status,tuple(sorted(set(warnings))),manifest_fingerprint(run=run_id,series=series.fingerprint,config=config.fingerprint,metrics=metrics,status=status.value,warnings=sorted(set(warnings))))
        return result,series,tuple(observations),degradations

    def _observation(self,run,item,series_id,point_id,timestamp,equity,factor):
        return OOSStitchedEquityObservation("oos-point-"+manifest_fingerprint(run=run,window=item.result_id,source=point_id,timestamp=timestamp)[:24],run,item.result_id,series_id,point_id,timestamp,equity,factor,manifest_fingerprint(run=run,window=item.fingerprint,source=point_id,equity=equity,factor=factor))
    def _equity_series_for_report(self, report_id):
        if not report_id:return None
        report=self.repository.get_performance_report(report_id)
        if report is None:return None
        note=next((value for value in report.methodology_notes if value.startswith("HISTORICAL_EQUITY_SERIES:")),None)
        return self.repository.get_historical_equity_series(note.split(":")[1]) if note else None
    def _test_trade_records(self, results):
        records=[]
        for item in results:
            if not item.performance_report_id: continue
            dataset=self.repository.get_performance_dataset_for_report(item.performance_report_id)
            if dataset is None: raise ValueError("OOS performance report has no frozen dataset.")
            for trade_id in dataset.paper_trade_ids:
                outcome=self.repository.get_paper_outcome(trade_id)
                if outcome and outcome.net_pnl is not None: records.append((trade_id,outcome.net_pnl,outcome.r_multiple,outcome.costs,outcome.gross_pnl,outcome.final_exit_timestamp))
        return tuple(records)
    def _benchmark_alignment(self, results):
        """A direct benchmark path is aligned only with identical frozen TEST sessions."""
        if not results:return BenchmarkAlignmentStatus.UNAVAILABLE
        any_benchmark=False
        for item in results:
            if not item.performance_report_id:return BenchmarkAlignmentStatus.UNAVAILABLE
            report=self.repository.get_performance_report(item.performance_report_id)
            strategy=self._equity_series_for_report(item.performance_report_id)
            if report is None or strategy is None or not report.benchmark_run_ids:return BenchmarkAlignmentStatus.PARTIAL
            strategy_points=tuple(self.repository.get_historical_equity_point(point_id) for point_id in strategy.point_ids)
            expected={point.evaluation_timestamp for point in strategy_points if point is not None}
            if not expected:return BenchmarkAlignmentStatus.PARTIAL
            matched=False
            for benchmark_run_id in report.benchmark_run_ids:
                observations=self.repository.list_historical_benchmark_observations(benchmark_run_id)
                any_benchmark=any_benchmark or bool(observations)
                if {observation.timestamp for observation in observations}==expected:
                    matched=True; break
            if not matched:return BenchmarkAlignmentStatus.PARTIAL
        return BenchmarkAlignmentStatus.ALIGNED if any_benchmark else BenchmarkAlignmentStatus.UNAVAILABLE
    def _metrics(self, observations, trades):
        ret=observations[-1].equity-1 if observations else None; peak=Decimal("1"); dds=[]
        for observation in observations: peak=max(peak,observation.equity); dds.append(observation.equity/peak-1)
        returns=[float(current.equity/previous.equity-1) for previous,current in zip(observations,observations[1:]) if previous.equity]
        vol=Decimal(str(pstdev(returns))) if len(returns)>1 else None; down=Decimal(str(pstdev([min(0,value) for value in returns]))) if len(returns)>1 else None; mean=sum(returns)/len(returns) if returns else None
        pnls=[item[1] for item in trades]; wins=[value for value in pnls if value>0]; losses=[value for value in pnls if value<0]; rs=[item[2] for item in trades if item[2] is not None]
        start,end=(observations[0].timestamp,observations[-1].timestamp) if observations else (None,None); years=Decimal(str((end-start).total_seconds()/31557600)) if start and end else Decimal("0")
        return {"return":ret,"drawdown":min(dds,default=None),"sharpe":Decimal(str((mean-float(self.risk_free_rate))/float(vol)*self.annualization_factor**.5)) if mean is not None and vol else None,"sortino":Decimal(str((mean-float(self.risk_free_rate))/float(down)*self.annualization_factor**.5)) if mean is not None and down else None,"cagr":(observations[-1].equity**(Decimal("1")/years)-1) if observations and years>0 else None,"expectancy":sum(pnls,Decimal("0"))/len(pnls) if pnls else None,"profit_factor":sum(wins,Decimal("0"))/abs(sum(losses,Decimal("0"))) if losses else None,"win_rate":Decimal(len(wins))/len(pnls) if pnls else None,"average_r":sum(rs,Decimal("0"))/len(rs) if rs else None,"costs":sum((item[3] for item in trades),Decimal("0")) if trades else Decimal("0"),"turnover":None}
    def _stability(self, results, values):
        decimals=lambda values: Decimal(str(median(values))) if values else None; dispersion=lambda values:Decimal(str(pstdev([float(value) for value in values]))) if len(values)>1 else None
        drawdowns=[item.max_drawdown for item in results if item.max_drawdown is not None]; expectations=[item.expectancy for item in results if item.expectancy is not None]; sharpes=[item.sharpe for item in results if item.sharpe is not None]; counts=[item.trade_count for item in results]
        return {"profitable_window_percentage":Decimal(sum(value>0 for value in values))/len(values) if values else None,"positive_expectancy_window_percentage":Decimal(sum(item.expectancy is not None and item.expectancy>0 for item in results))/len(results) if results else None,"median_return":decimals(values),"mean_return":sum(values,Decimal("0"))/len(values) if values else None,"best_return":max(values) if values else None,"worst_return":min(values) if values else None,"return_dispersion":dispersion(values),"median_drawdown":decimals(drawdowns),"worst_drawdown":min(drawdowns) if drawdowns else None,"median_expectancy":decimals(expectations),"expectancy_dispersion":dispersion(expectations),"median_sharpe":decimals(sharpes),"sharpe_dispersion":dispersion(sharpes),"median_trade_count":decimals(counts),"trade_count_dispersion":dispersion(counts)}
    def _degradation(self, run_id,item,report_id):
        pre=self.repository.get_performance_report(report_id); test=self.repository.get_performance_report(item.performance_report_id) if item.performance_report_id else None
        if pre is None or test is None or pre.end>item.test_start: raise ValueError("Pre-TEST degradation evidence must exist before its TEST window.")
        pre_metrics,test_metrics=pre.metrics,test.metrics; pre_return=pre_metrics.get("portfolio_return",pre_metrics.get("capital_efficiency")); test_return=test_metrics.get("portfolio_return",test_metrics.get("capital_efficiency")); diff=test_return-pre_return if test_return is not None and pre_return is not None else None; warnings=("VALIDATION_TO_TEST_DEGRADATION",) if diff is not None and diff<0 else ()
        return ValidationDegradationAnalysis("oos-degradation-"+manifest_fingerprint(run=run_id,window=item.result_id,pre=report_id)[:24],run_id,item.result_id,report_id,test.report_id,pre.end,item.test_start,diff,test_return/pre_return if test_return is not None and pre_return not in (None,Decimal("0")) else None,test_metrics.get("expectancy")-pre_metrics.get("expectancy") if test_metrics.get("expectancy") is not None and pre_metrics.get("expectancy") is not None else None,test_metrics.get("sharpe")-pre_metrics.get("sharpe") if test_metrics.get("sharpe") is not None and pre_metrics.get("sharpe") is not None else None,test_metrics.get("max_drawdown")-pre_metrics.get("max_drawdown") if test_metrics.get("max_drawdown") is not None and pre_metrics.get("max_drawdown") is not None else None,test_metrics.get("win_rate")-pre_metrics.get("win_rate") if test_metrics.get("win_rate") is not None and pre_metrics.get("win_rate") is not None else None,test_metrics.get("profit_factor")-pre_metrics.get("profit_factor") if test_metrics.get("profit_factor") is not None and pre_metrics.get("profit_factor") is not None else None,warnings,manifest_fingerprint(window=item.fingerprint,pre=report_id,test=test.report_id,diff=diff))
    def _warnings(self,config,valid,coverage,metrics,stability,degradations):
        out=[]
        if len(valid)<config.minimum_valid_oos_windows or coverage<config.minimum_coverage_ratio:out.append("TOO_FEW_VALID_WINDOWS")
        if len(valid)<config.minimum_planned_windows:out.append("TOO_FEW_PLANNED_WINDOWS")
        if len(valid) and metrics["return"] is not None and stability["return_dispersion"] is not None and config.max_return_dispersion is not None and stability["return_dispersion"]>config.max_return_dispersion:out.append("HIGH_OOS_WINDOW_DISPERSION")
        if metrics["expectancy"] is None or sum(item.trade_count for item in valid)<config.minimum_oos_trades:out.append("TOO_FEW_OOS_TRADES")
        if config.max_window_drawdown is not None and any(item.max_drawdown is not None and item.max_drawdown < -config.max_window_drawdown for item in valid):out.append("OOS_DRAWDOWN_INSTABILITY")
        if any("VALIDATION_TO_TEST_DEGRADATION" in item.warnings for item in degradations):out.append("VALIDATION_TO_TEST_DEGRADATION")
        return out
    def _status(self,config,valid,coverage,metrics,warnings):
        if len(valid)<config.minimum_valid_oos_windows or coverage<config.minimum_coverage_ratio or metrics["return"] is None:return AggregateValidationStatus.INSUFFICIENT_EVIDENCE
        if "VALIDATION_TO_TEST_DEGRADATION" in warnings:return AggregateValidationStatus.DEGRADED
        if any(item in warnings for item in ("HIGH_OOS_WINDOW_DISPERSION","OOS_DRAWDOWN_INSTABILITY")):return AggregateValidationStatus.UNSTABLE
        return AggregateValidationStatus.VALID
