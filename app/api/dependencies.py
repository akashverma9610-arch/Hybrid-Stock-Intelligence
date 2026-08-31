from fastapi import Request

from app.api.settings import APISettings
from app.storage.database import DatabaseSettings
from app.api.portfolio_query import PortfolioQueryService
from app.api.market_query import MarketRegimeQueryService, SectorQueryService
from app.api.stock_query import StockAnalysisQueryService
from app.api.signal_paper_query import PaperTradeQueryService, SignalQueryService
from app.api.performance_governance_query import BenchmarkQueryService, GovernanceQueryService, PerformanceQueryService
from app.feature_settings import FeatureSettings
from app.connections.service import ProviderConnectionService
from app.runtime.scheduler import RuntimeHealthService
from app.data_sources.service import DataSourceCompositionService
from app.api.filings_query import FilingsQueryService
from app.api.fundamentals_query import FundamentalsQueryService
from app.api.news_query import NewsQueryService
from app.api.capital_rotation_query import CapitalRotationQueryService
from app.api.market_context_query import BreadthQueryService, CrisisQueryService, MarketExtremesQueryService
from app.portfolio_import.service import PortfolioImportService
from app.portfolio_analysis.service import PortfolioAnalysisJobService
from app.api.universe_opportunity_query import UniverseOpportunityQueryService
from app.intelligence.shared_brain_application import SharedBrainApplicationService
from app.data_operations.service import DataOperationsService


def get_api_settings(request: Request) -> APISettings:
    return request.app.state.api_settings


def get_database_settings(request: Request) -> DatabaseSettings:
    return request.app.state.database_settings


def get_feature_settings(request: Request) -> FeatureSettings:
    return request.app.state.feature_settings


def get_portfolio_query_service(request: Request) -> PortfolioQueryService:
    return request.app.state.portfolio_query_service


def get_portfolio_import_service(request: Request) -> PortfolioImportService:
    return request.app.state.portfolio_import_service


def get_portfolio_analysis_job_service(request: Request) -> PortfolioAnalysisJobService:
    service = request.app.state.portfolio_analysis_job_service
    if service is None:
        raise RuntimeError("Portfolio analysis job service is not initialized.")
    return service


def get_market_regime_query_service(request: Request) -> MarketRegimeQueryService:
    return request.app.state.market_regime_query_service


def get_sector_query_service(request: Request) -> SectorQueryService:
    return request.app.state.sector_query_service


def get_stock_analysis_query_service(request: Request) -> StockAnalysisQueryService:
    return request.app.state.stock_analysis_query_service


def get_signal_query_service(request: Request) -> SignalQueryService:
    return request.app.state.signal_query_service


def get_paper_trade_query_service(request: Request) -> PaperTradeQueryService:
    return request.app.state.paper_trade_query_service


def get_performance_query_service(request: Request) -> PerformanceQueryService:
    return request.app.state.performance_query_service


def get_benchmark_query_service(request: Request) -> BenchmarkQueryService:
    return request.app.state.benchmark_query_service


def get_governance_query_service(request: Request) -> GovernanceQueryService:
    return request.app.state.governance_query_service


def get_connection_service(request: Request) -> ProviderConnectionService:
    return request.app.state.connection_service


def get_backend_local_real_portfolio_ohlcv_activation(request: Request):
    """Lazily compose the hidden local operation in the serving backend process."""
    from app.data_operations.backend_local_upstox import build_backend_local_real_portfolio_ohlcv_activation
    from app.storage.database import DatabaseSettings

    database = request.app.state.database_settings
    if database.storage_mode.value == "IN_MEMORY_SQLITE":
        database = DatabaseSettings.local_runtime()
    return build_backend_local_real_portfolio_ohlcv_activation(
        database_settings=database,
        credential_store=request.app.state.connection_credential_store,
    )


def get_runtime_health_service(request: Request) -> RuntimeHealthService:
    return request.app.state.runtime_health_service


def get_data_source_composition_service(request: Request) -> DataSourceCompositionService:
    return request.app.state.data_source_composition_service

def get_filings_query_service(request: Request) -> FilingsQueryService:
    return request.app.state.filings_query_service

def get_fundamentals_query_service(request: Request) -> FundamentalsQueryService:
    return request.app.state.fundamentals_query_service

def get_news_query_service(request: Request) -> NewsQueryService:
    return request.app.state.news_query_service


def get_capital_rotation_query_service(request: Request) -> CapitalRotationQueryService:
    return request.app.state.capital_rotation_query_service


def get_breadth_query_service(request: Request) -> BreadthQueryService:
    return request.app.state.breadth_query_service


def get_market_extremes_query_service(request: Request) -> MarketExtremesQueryService:
    return request.app.state.market_extremes_query_service


def get_crisis_query_service(request: Request) -> CrisisQueryService:
    return request.app.state.crisis_query_service


def get_universe_opportunity_query_service(request: Request) -> UniverseOpportunityQueryService:
    return request.app.state.universe_opportunity_query_service


def get_shared_brain_application_service(request: Request) -> SharedBrainApplicationService:
    service = request.app.state.shared_brain_application_service
    if service is None:
        raise RuntimeError("Shared Brain application service is not initialized.")
    return service


def get_data_operations_service(request: Request) -> DataOperationsService:
    service = request.app.state.data_operations_service
    if service is None:
        raise RuntimeError("Data operations service is not initialized.")
    return service
