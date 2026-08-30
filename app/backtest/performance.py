from __future__ import annotations

"""Frozen adapter from completed backtest artifacts to Phase 7B engines."""

from dataclasses import dataclass
from decimal import Decimal
from statistics import pstdev

from app.historical.guard import manifest_fingerprint
from app.performance.benchmarks import buy_hold
from app.performance.engine import PerformanceEngine
from app.performance.models import PerformanceEvaluationDataset, TradePerformanceRecord
from app.performance.models import EquityPoint
from app.performance.reporting import compare


@dataclass(frozen=True, slots=True)
class HistoricalPerformanceResult:
    dataset: PerformanceEvaluationDataset
    report: object
    normalized_trades: tuple[TradePerformanceRecord, ...]
    benchmark_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class HistoricalPerformanceIntegrationService:
    """Uses only persisted run, paper, and supplied PIT benchmark inputs."""

    def __init__(self, repository, calendar, performance_config) -> None:
        self.repository, self.calendar, self.config = repository, calendar, performance_config
        self.engine = PerformanceEngine(performance_config)

    def generate(self, *, run, paper_trade_ids: tuple[str, ...], generated_at, benchmark_series: dict[str, tuple[Decimal, ...]] = {}, equity_series=None) -> HistoricalPerformanceResult:
        if run.status.value != "COMPLETED":
            raise ValueError("Historical performance requires a completed frozen backtest run.")
        if run.partition_id is not None and self.repository.get_historical_partition(run.partition_id) is None:
            raise ValueError("Historical performance requires the frozen historical partition.")
        manifest = self.repository.get_historical_manifest(run.dataset_manifest_id)
        if manifest is None or manifest.fingerprint != run.dataset_fingerprint:
            raise ValueError("Historical performance requires the exact frozen dataset manifest.")
        records = tuple(self._normalize(run, trade_id) for trade_id in paper_trade_ids)
        if any(record is None for record in records):
            raise ValueError("Historical performance has missing frozen paper artifacts.")
        records = tuple(records)
        dataset = PerformanceEvaluationDataset(
            "historical-performance-dataset-" + manifest_fingerprint(run=run.backtest_run_id, trades=paper_trade_ids, config=self.config.version)[:24],
            run.strategy_version, run.registry_version, run.scoring_config_version, run.gate_config_version, run.rotation_config_version,
            run.signal_config_version, run.paper_config_version, self.config.version, run.evaluation_start, run.evaluation_end,
            paper_trade_ids, tuple(record.paper_trade_id for record in records), tuple(sorted(benchmark_series)),
            tuple("v1" for _ in sorted(benchmark_series)), run.cost_model_reference, run.calendar_reference,
            "frozen_historical_paper_outcomes_and_backtest_run",
        )
        report = self.engine.report(strategy_version=run.strategy_version, start=run.evaluation_start, end=run.evaluation_end, trades=records, generated_at=generated_at)
        if equity_series is not None:
            if equity_series.backtest_run_id != run.backtest_run_id: raise ValueError("Historical equity series belongs to a different backtest run.")
            points=tuple(self.repository.get_historical_equity_point(point_id) for point_id in equity_series.point_ids)
            if any(point is None for point in points): raise ValueError("Historical performance has missing frozen equity points.")
            peak=points[0].equity; curve=[]
            for point in points:
                peak=max(peak,point.equity); curve.append(EquityPoint(point.evaluation_timestamp,point.equity,(point.equity-peak)/peak,f"state:{point.backtest_portfolio_state_id}"))
            metrics=dict(report.metrics); metrics["portfolio_return"]=points[-1].equity/equity_series.starting_capital-1; metrics["capital_efficiency"]=metrics["portfolio_return"]; metrics["max_drawdown"]=min((point.drawdown for point in curve),default=Decimal("0")); metrics["ending_equity"]=points[-1].equity
            returns=[float(points[index].equity/points[index-1].equity-1) for index in range(1,len(points)) if points[index-1].equity]
            volatility=Decimal(str(pstdev(returns))) if len(returns)>1 else None; downside=[min(0,value) for value in returns]; downside_volatility=Decimal(str(pstdev(downside))) if len(downside)>1 else None; mean=sum(returns)/len(returns) if returns else None
            metrics["volatility"]=volatility; metrics["sharpe"]=Decimal(str((mean-float(self.config.risk_free_rate))/float(volatility)*self.config.annualization_factor**.5)) if mean is not None and volatility else None; metrics["sortino"]=Decimal(str((mean-float(self.config.risk_free_rate))/float(downside_volatility)*self.config.annualization_factor**.5)) if mean is not None and downside_volatility else None; metrics["equity_return_observations"]=len(returns)
            report=__import__("dataclasses").replace(report,metrics=metrics,equity_curve=tuple(curve))
        # Canonical report ID is derived from strategy/end. Bind the immutable
        # backtest input in methodology notes without altering metric formulas.
        report = __import__("dataclasses").replace(report, methodology_notes=(f"BACKTEST_RUN:{run.backtest_run_id}", f"DATASET:{run.dataset_manifest_id}:{run.dataset_fingerprint}", "OPEN_TRADES_RETAINED_NOT_CLOSED", *( (f"HISTORICAL_EQUITY_SERIES:{equity_series.series_id}:{equity_series.fingerprint}",) if equity_series is not None else () )))
        self.repository.save_performance_dataset(dataset); self.repository.save_performance_report(report, dataset.dataset_id)
        benchmark_ids=[]; warnings=[]
        for benchmark_id, values in sorted(benchmark_series.items()):
            benchmark=buy_hold(benchmark_id, values)
            run_id="historical-benchmark-" + manifest_fingerprint(report=report.report_id, benchmark=benchmark_id, values=values)[:24]
            comparison=compare(benchmark_id, benchmark.version, report.metrics, benchmark.net_return, fairness=() if benchmark.net_return is not None else ("INSUFFICIENT_FROZEN_BENCHMARK_DATA",))
            self.repository.save_benchmark_run(run_id, report.report_id, benchmark, (f"historical:{benchmark_id}",), "v1", run.evaluation_end)
            self.repository.save_benchmark_comparison("historical-comparison-" + manifest_fingerprint(report=report.report_id, benchmark=benchmark_id)[:24], report.report_id, comparison)
            benchmark_ids.append(run_id)
            if benchmark.net_return is None: warnings.append(f"BENCHMARK_UNAVAILABLE:{benchmark_id}")
        return HistoricalPerformanceResult(dataset, report, records, tuple(benchmark_ids), tuple(warnings))

    def _normalize(self, run, paper_trade_id: str) -> TradePerformanceRecord | None:
        trade=self.repository.get_paper_trade(paper_trade_id); outcome=self.repository.get_paper_outcome(paper_trade_id)
        if trade is None or outcome is None: return None
        sessions=self.calendar.sessions_between(outcome.entry_timestamp.date(), outcome.final_exit_timestamp.date()) if outcome.entry_timestamp and outcome.final_exit_timestamp else None
        return TradePerformanceRecord(paper_trade_id, outcome.state.value, outcome.entry_timestamp, outcome.final_exit_timestamp,
            outcome.net_pnl, outcome.gross_pnl, outcome.r_multiple, trade.decision_score, trade.data_confidence,
            trade.market_regime, trade.sector, trade.entry_type, outcome.costs, outcome.mfe, outcome.mae,
            trade.catalyst, trade.catalyst_clock, sessions, outcome.triggered, outcome.filled, outcome.t1_reached,
            outcome.t2_reached, False, outcome.stop_hit, outcome.stop_hit and outcome.entry_price == outcome.final_exit_price,
            outcome.invalidated, outcome.expiry, outcome.mfe_r, outcome.mae_r)
