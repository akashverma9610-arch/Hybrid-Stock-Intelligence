"""Repository-backed implementations for existing read-only API query contracts."""
from __future__ import annotations
from typing import Any
from app.api.errors import APIRequestError
from app.api.market_query import SectorAnalysisQueryRecord
from app.api.performance_governance_query import (
    BenchmarkQueryRecord, PerformanceQueryRecord, PromotionQueryRecord,
    SnapshotBenchmarkQueryService, SnapshotGovernanceQueryService, SnapshotPerformanceQueryService,
)
from app.api.portfolio_query import SnapshotPortfolioQueryService
from app.api.signal_paper_query import (
    PaperTradeQueryRecord, SignalQueryRecord, SnapshotPaperTradeQueryService, SnapshotSignalQueryService,
)
from app.api.stock_query import SnapshotStockAnalysisQueryService, StockAnalysisQueryResult
from app.api.capital_rotation_query import SnapshotCapitalRotationQueryService
from app.api.market_context_query import (
    BreadthQueryRecord, SnapshotBreadthQueryService, SnapshotCrisisQueryService,
    SnapshotMarketExtremesQueryService,
)
from app.crisis.models import CrisisAssessment, UpsideExcessAssessment
from app.rotation.models import PortfolioRotationEvaluation
from app.universe_analysis.models import PortfolioUniverseRotationSnapshot
from app.analysis.models import MarketRegimeResult
from app.backtest.promotion import ApprovedStrategyVersion, StrategyActivation
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily, CoreApiSnapshotRepository


SNAPSHOT_FAMILIES = {
    "portfolio": CoreApiSnapshotFamily.PORTFOLIO, "market_regime": CoreApiSnapshotFamily.MARKET_REGIME,
    "sectors": CoreApiSnapshotFamily.SECTOR_ANALYSIS, "stock_analysis": CoreApiSnapshotFamily.STOCK_ANALYSIS,
    "signals": CoreApiSnapshotFamily.SIGNAL, "paper_trades": CoreApiSnapshotFamily.PAPER_TRADE,
    "performance": CoreApiSnapshotFamily.PERFORMANCE_REPORT, "benchmarks": CoreApiSnapshotFamily.BENCHMARK_COMPARISON,
    "strategy_versions": CoreApiSnapshotFamily.APPROVED_STRATEGY_VERSION,
    "promotions": CoreApiSnapshotFamily.PROMOTION_PROPOSAL, "activations": CoreApiSnapshotFamily.STRATEGY_ACTIVATION,
    "capital_rotation": CoreApiSnapshotFamily.CAPITAL_ROTATION,
    "portfolio_universe_rotation": CoreApiSnapshotFamily.PORTFOLIO_UNIVERSE_ROTATION,
    "crisis": CoreApiSnapshotFamily.CRISIS_ASSESSMENT,
    "upside_extremes": CoreApiSnapshotFamily.UPSIDE_EXCESS_ASSESSMENT,
}


class _RepositorySource:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def _payloads(self, key: str) -> tuple[Any, ...]:
        try:
            return tuple(
                item.payload
                for item in self._repository.list_snapshots(SNAPSHOT_FAMILIES[key])
            )
        except ValueError as error:
            # Version compatibility is a read-boundary concern.  A stored
            # unsupported snapshot must be unavailable, never an HTTP 500 or
            # a fallback to another symbol/current record.
            raise APIRequestError(
                status_code=503,
                code="SNAPSHOT_SCHEMA_UNSUPPORTED",
                message="Stored API snapshot schema is unsupported.",
            ) from error

    def _required(self, key: str, code: str, message: str) -> tuple[Any, ...]:
        value = self._payloads(key)
        if not value:
            raise APIRequestError(status_code=503, code=code, message=message)
        return value


class RepositoryPortfolioQueryService(_RepositorySource):
    def get_snapshot(self):
        return SnapshotPortfolioQueryService(
            self._required("portfolio", "PORTFOLIO_UNAVAILABLE", "Portfolio data is not available.")[-1]
        ).get_snapshot()


class RepositoryMarketRegimeQueryService(_RepositorySource):
    def get_market_regime(self):
        values = tuple(item for item in self._payloads("market_regime") if isinstance(item, MarketRegimeResult))
        if not values:
            raise APIRequestError(status_code=503, code="MARKET_REGIME_UNAVAILABLE", message="Market regime is not available.")
        return values[-1]


class RepositorySectorQueryService(_RepositorySource):
    def list_sectors(self):
        return tuple(self._required("sectors", "SECTOR_ANALYSIS_UNAVAILABLE", "Sector analysis is not available."))

    def get_sector(self, sector_id: str):
        for item in self.list_sectors():
            if item.sector_id == sector_id:
                return item
        _sector_missing()


class RepositoryStockAnalysisQueryService(_RepositorySource):
    def get_analysis(self, symbol: str) -> StockAnalysisQueryResult:
        records = tuple(
            item
            for item in self._required("stock_analysis", "STOCK_ANALYSIS_UNAVAILABLE", "Stock analysis is not available.")
            if isinstance(item, StockAnalysisQueryResult) and item.symbol == symbol
        )
        if not records:
            raise APIRequestError(status_code=404, code="STOCK_NOT_FOUND", message="Stock analysis was not found.")
        return records[-1]

    def list_analysis(self) -> tuple[StockAnalysisQueryResult, ...]:
        records = tuple(
            item for item in self._required("stock_analysis", "STOCK_ANALYSIS_UNAVAILABLE", "Stock analysis is not available.")
            if isinstance(item, StockAnalysisQueryResult)
        )
        latest_by_symbol: dict[str, StockAnalysisQueryResult] = {}
        for item in records:
            latest_by_symbol[item.symbol] = item
        return tuple(sorted(latest_by_symbol.values(), key=lambda item: item.symbol))


class RepositorySignalQueryService(_RepositorySource):
    def _service(self):
        return SnapshotSignalQueryService(tuple(self._required("signals", "SIGNALS_UNAVAILABLE", "Signals are not available.")))

    def list_signals(self, **kwargs):
        return self._service().list_signals(**kwargs)

    def get_signal(self, signal_id):
        return self._service().get_signal(signal_id)


class RepositoryPaperTradeQueryService(_RepositorySource):
    def _reports(self):
        return tuple(
            item.report if isinstance(item, PerformanceQueryRecord) else item
            for item in self._payloads("performance")
        )

    def _trades(self):
        return SnapshotPaperTradeQueryService(
            tuple(self._required("paper_trades", "PAPER_TRADES_UNAVAILABLE", "Paper trades are not available.")),
            self._reports(),
        )

    def list_paper_trades(self, **kwargs):
        return self._trades().list_paper_trades(**kwargs)

    def get_paper_trade(self, trade_id):
        return self._trades().get_paper_trade(trade_id)

    def get_performance(self, **kwargs):
        records = self._payloads("performance")
        if not records:
            raise APIRequestError(status_code=503, code="PERFORMANCE_UNAVAILABLE", message="Paper-trade performance is not available.")
        return SnapshotPaperTradeQueryService(
            tuple(self._payloads("paper_trades")), self._reports()
        ).get_performance(**kwargs)


class RepositoryPerformanceQueryService(_RepositorySource):
    def _service(self):
        return SnapshotPerformanceQueryService(tuple(self._required("performance", "PERFORMANCE_UNAVAILABLE", "Performance is not available.")))

    def list_performance(self, **kwargs):
        return self._service().list_performance(**kwargs)

    def get_performance(self, report_id):
        return self._service().get_performance(report_id)


class RepositoryBenchmarkQueryService(_RepositorySource):
    def _service(self):
        return SnapshotBenchmarkQueryService(tuple(self._required("benchmarks", "BENCHMARKS_UNAVAILABLE", "Benchmarks are not available.")))

    def list_benchmarks(self, **kwargs):
        return self._service().list_benchmarks(**kwargs)

    def get_benchmark(self, benchmark_id):
        return self._service().get_benchmark(benchmark_id)


class RepositoryGovernanceQueryService(_RepositorySource):
    def _service(self):
        versions = tuple(self._payloads("strategy_versions"))
        promotions = tuple(self._payloads("promotions"))
        activations = tuple(self._payloads("activations"))
        if not versions and not promotions and not activations:
            raise APIRequestError(status_code=503, code="GOVERNANCE_UNAVAILABLE", message="Strategy governance is not available.")
        version_by_id = {item.approved_id: item for item in versions if isinstance(item, ApprovedStrategyVersion)}
        active_records = tuple(
            item for item in activations
            if isinstance(item, StrategyActivation) and item.approved_id in version_by_id
        )
        if active_records:
            activation = max(active_records, key=lambda item: (item.effective_at, item.activation_id))
            active = activation, version_by_id[activation.approved_id]
        else:
            active = None
        return SnapshotGovernanceQueryService(tuple(versions), tuple(promotions), active)

    def list_strategy_versions(self):
        return self._service().list_strategy_versions()

    def get_active_strategy(self):
        return self._service().get_active_strategy()

    def list_promotions(self):
        return self._service().list_promotions()

    def get_promotion(self, proposal_id):
        return self._service().get_promotion(proposal_id)


class RepositoryCapitalRotationQueryService(_RepositorySource):
    """Reads the latest published canonical evaluation; it never calculates one."""

    def get_rotation(self, **kwargs):
        evaluations = tuple(item for item in self._payloads("capital_rotation") if isinstance(item, PortfolioRotationEvaluation))
        evaluation = evaluations[-1] if evaluations else None
        regime = None
        if evaluation is not None:
            matching = tuple(
                item for item in self._payloads("market_regime")
                if getattr(item, "as_of_timestamp", None) == evaluation.context.as_of_timestamp
            )
            if matching:
                classification = getattr(matching[-1], "classification", None)
                regime = getattr(classification, "value", classification)
        coverage = None
        if evaluation is not None:
            values = tuple(item for item in self._payloads("portfolio_universe_rotation") if isinstance(item, PortfolioUniverseRotationSnapshot) and item.rotation_evaluation_id == evaluation.evaluation_id)
            coverage = values[-1] if values else None
        return SnapshotCapitalRotationQueryService(evaluation, market_regime=regime, coverage=coverage).get_rotation(**kwargs)


class RepositoryBreadthQueryService(_RepositorySource):
    """Reads the breadth/participation pair published by a prior runtime cycle."""
    def get_breadth(self):
        for item in reversed(self._payloads("market_regime")):
            if not isinstance(item, dict):
                continue
            breadth, participation = item.get("breadth"), item.get("participation")
            if breadth is not None:
                return SnapshotBreadthQueryService(BreadthQueryRecord(
                    breadth, participation, item.get("data_as_of"), item.get("cycle_id"),
                )).get_breadth()
        return SnapshotBreadthQueryService(None).get_breadth()


class RepositoryMarketExtremesQueryService(_RepositorySource):
    def get_extremes(self):
        values = tuple(item for item in self._payloads("upside_extremes") if isinstance(item, UpsideExcessAssessment))
        return SnapshotMarketExtremesQueryService(values[-1] if values else None).get_extremes()


class RepositoryCrisisQueryService(_RepositorySource):
    def get_crisis(self):
        values = tuple(item for item in self._payloads("crisis") if isinstance(item, CrisisAssessment))
        return SnapshotCrisisQueryService(values[-1] if values else None).get_crisis()


def _sector_missing():
    raise APIRequestError(status_code=404, code="SECTOR_NOT_FOUND", message="Sector analysis was not found.")
