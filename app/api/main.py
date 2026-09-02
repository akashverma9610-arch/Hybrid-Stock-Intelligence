"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import APIRequestError, api_request_error_handler, request_validation_error_handler, unexpected_exception_handler
from app.api.middleware import RequestContextMiddleware
from app.api.portfolio_query import PortfolioQueryService, UnavailablePortfolioQueryService
from app.api.market_query import (
    MarketRegimeQueryService,
    SectorQueryService,
    UnavailableMarketRegimeQueryService,
    UnavailableSectorQueryService,
)
from app.api.routes.market import market_router, sector_router
from app.api.routes.stocks import router as stocks_router
from app.api.stock_query import StockAnalysisQueryService, UnavailableStockAnalysisQueryService
from app.api.signal_paper_query import (
    PaperTradeQueryService,
    SignalQueryService,
    UnavailablePaperTradeQueryService,
    UnavailableSignalQueryService,
)
from app.api.routes.signals import router as signal_paper_router
from app.api.performance_governance_query import (
    BenchmarkQueryService,
    GovernanceQueryService,
    PerformanceQueryService,
    UnavailableBenchmarkQueryService,
    UnavailableGovernanceQueryService,
    UnavailablePerformanceQueryService,
)
from app.api.routes.performance_governance import router as performance_governance_router
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.api.repository_query_services import (
    RepositoryBenchmarkQueryService, RepositoryGovernanceQueryService, RepositoryMarketRegimeQueryService,
    RepositoryPaperTradeQueryService, RepositoryPerformanceQueryService, RepositoryPortfolioQueryService,
    RepositorySectorQueryService, RepositorySignalQueryService, RepositoryStockAnalysisQueryService,
    RepositoryCapitalRotationQueryService, RepositoryBreadthQueryService,
    RepositoryCrisisQueryService, RepositoryMarketExtremesQueryService,
)
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.portfolio_import import router as portfolio_import_router
from app.portfolio_import.service import PortfolioImportService
from app.api.routes.portfolio_analysis import router as portfolio_analysis_router
from app.portfolio_analysis.service import CoreSnapshotPortfolioAnalysisJobStore, PortfolioAnalysisJobService, QueryPortfolioSnapshotSource
from app.api.routes.system import health_router, router as system_router
from app.api.settings import APISettings
from app.feature_settings import FeatureSettings
from app.api.routes.connections import router as connections_router
from app.api.routes.connection_setup import router as connection_setup_router
from app.connections.credentials import create_credential_store
from app.connections.repository import SQLiteConnectionProfileRepository
from app.connections.service import ProviderConnectionService
from app.runtime.scheduler import RuntimeHealthService, RuntimeSchedulerSettings
from app.runtime.local_runtime import validate_local_operator_runtime
from app.api.routes.runtime import router as runtime_router
from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
from app.api.routes.data_sources import router as data_sources_router
from app.api.filings_query import FilingsQueryService, UnavailableFilingsQueryService
from app.api.routes.filings import router as filings_router
from app.api.fundamentals_query import FundamentalsQueryService, UnavailableFundamentalsQueryService
from app.api.routes.fundamentals import router as fundamentals_router
from app.api.news_query import NewsQueryService, RepositoryNewsQueryService, UnavailableNewsQueryService
from app.api.routes.news import router as news_router
from app.api.primary_market_query import UnavailablePrimaryMarketQueryService
from app.api.routes.primary_market import router as primary_market_router
from app.api.capital_rotation_query import CapitalRotationQueryService, UnavailableCapitalRotationQueryService
from app.api.routes.capital_rotation import router as capital_rotation_router
from app.api.market_context_query import (
    BreadthQueryService, CrisisQueryService, MarketExtremesQueryService,
    UnavailableBreadthQueryService, UnavailableCrisisQueryService,
    UnavailableMarketExtremesQueryService,
)
from app.api.universe_opportunity_query import CoreSnapshotUniverseOpportunityQueryService, UniverseOpportunityQueryService
from app.universe_analysis.service import CoreUniverseAnalysisStore
from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory
from app.storage.database import DatabaseSettings
from app.api.routes.opportunities import router as opportunities_router
from app.api.routes.market_wide_watch import router as market_wide_watch_router
from app.api.routes.dhan_live import router as dhan_live_router
from app.intelligence.shared_brain_application import (
    CoreUniverseInstrumentResolver,
    SharedBrainApplicationService,
    StoredSharedBrainEvidenceAssembler,
)
from app.intelligence.market_technical_artifact import (
    SharedBrainMarketTechnicalArtifactEvidenceSource,
    SharedBrainMarketTechnicalArtifactStore,
)
from app.forward_paper.store import ForwardPaperStore
from app.intelligence.forward_paper_intelligence import ForwardPaperIntelligenceProjector
from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
from app.historical.security_master import HistoricalSecurityMasterStore
from app.intelligence.macro.store import MacroEvidenceStore
from app.news.store import PostgreSQLNewsEvidenceStore, SQLiteNewsEvidenceStore
from app.taxonomy.service import TaxonomySnapshotStore
from app.data_operations.service import DataOperationsService
from app.data_operations.store import DataOperationsStore
from app.api.routes.data_operations import router as data_operations_router
from app.api.routes.intelligence import router as intelligence_router
from app.intelligence.external_intelligence_application import ExternalIntelligenceApplicationService


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Reserve lightweight application state only; start no background work."""
    repository = getattr(application.state, "core_api_snapshot_repository", None)
    if repository is None:
        repository = create_core_api_snapshot_repository(application.state.database_settings)
        application.state.core_api_snapshot_repository = repository
        application.state.owns_core_api_snapshot_repository = True
    for attribute, factory in application.state.repository_query_service_factories:
        setattr(application.state, attribute, factory(repository))
    if application.state.portfolio_analysis_job_service is None:
        application.state.portfolio_analysis_job_service = PortfolioAnalysisJobService(
            snapshots=QueryPortfolioSnapshotSource(lambda: application.state.portfolio_query_service),
            store=CoreSnapshotPortfolioAnalysisJobStore(repository),
        )
    if application.state.universe_opportunity_query_service is None:
        application.state.universe_opportunity_query_service = CoreSnapshotUniverseOpportunityQueryService(CoreUniverseAnalysisStore(repository))
    if application.state.shared_brain_application_service is None:
        database = application.state.database_settings
        facts = (
            SQLiteFinancialFactStore(database.url.removeprefix("sqlite:///"))
            if database.backend is DatabaseBackend.SQLITE
            else PostgreSQLFinancialFactStore(DatabaseConnectionFactory(database))
        )
        filings = (
            SQLiteCorporateFilingsStore(database.url.removeprefix("sqlite:///"))
            if database.backend is DatabaseBackend.SQLITE
            else PostgreSQLCorporateFilingsStore(DatabaseConnectionFactory(database))
        )
        news = (
            SQLiteNewsEvidenceStore(database.url.removeprefix("sqlite:///"))
            if database.backend is DatabaseBackend.SQLITE
            else PostgreSQLNewsEvidenceStore(DatabaseConnectionFactory(database))
        )
        historical = (
            SQLiteHistoricalBarStore(database.url.removeprefix("sqlite:///"))
            if database.backend is DatabaseBackend.SQLITE
            else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(database))
        )
        universe = CoreUniverseAnalysisStore(repository)
        from app.ownership.store import OwnershipObservationStore
        from app.market_data.current_sector_rotation import CurrentSectorRankingStore
        from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore
        from app.reliability.integrity import ReliabilityIntegrityObservationStore
        from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
        from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
        decision_scores = None
        if database.backend is DatabaseBackend.SQLITE:
            decision_scores = getattr(application.state, "decision_score_governance_repository", None)
            if decision_scores is None:
                decision_scores = SQLiteStrategyGovernanceRepository(database.url.removeprefix("sqlite:///"))
                application.state.decision_score_governance_repository = decision_scores
        application.state.shared_brain_application_service = SharedBrainApplicationService(
            resolver=CoreUniverseInstrumentResolver(universe),
            evidence_assembler=StoredSharedBrainEvidenceAssembler(
                facts,
                historical,
                filings=filings,
                ownership_observations=OwnershipObservationStore(repository),
                historical_security_master=HistoricalSecurityMasterStore(repository),
                taxonomy=TaxonomySnapshotStore(repository),
                sector_rankings=CurrentSectorRankingStore(repository),
                macro_evidence_source=MacroEvidenceStore(repository),
                news=news,
                market_technical_artifacts=SharedBrainMarketTechnicalArtifactEvidenceSource(
                    SharedBrainMarketTechnicalArtifactStore(repository),
                ),
                reliability_integrity_observations=ReliabilityIntegrityObservationStore(repository),
                decision_scores=decision_scores,
                setup_assessments=decision_scores,
                setup_opportunities=CanonicalSetupOpportunityStore(repository),
            ),
            forward_paper_intelligence=ForwardPaperIntelligenceProjector(ForwardPaperStore(repository)),
        )
    if application.state.data_operations_service is None:
        application.state.data_operations_service = DataOperationsService(DataOperationsStore(repository))
    if application.state.market_wide_watch_service is None and application.state.database_settings.backend is DatabaseBackend.SQLITE:
        from app.intelligence.market_wide_watch import MarketWideWatchService
        from app.intelligence.market_wide_evidence_readiness import MarketWideEvidenceReadinessService
        from app.ownership.store import OwnershipObservationStore
        from app.market_data.current_sector_rotation import CurrentSectorRankingStore
        from app.reliability.integrity import ReliabilityIntegrityObservationStore
        from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
        from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
        database = application.state.database_settings
        governance = getattr(application.state, "decision_score_governance_repository", None)
        if governance is None:
            governance = SQLiteStrategyGovernanceRepository(database.url.removeprefix("sqlite:///"))
            application.state.decision_score_governance_repository = governance
        external_evidence = SQLiteExternalIntelligenceRepository(database.url.removeprefix("sqlite:///"))
        historical = SQLiteHistoricalBarStore(database.url.removeprefix("sqlite:///"))
        facts = SQLiteFinancialFactStore(database.url.removeprefix("sqlite:///"))
        filings = SQLiteCorporateFilingsStore(database.url.removeprefix("sqlite:///"))
        reliability = ReliabilityIntegrityObservationStore(repository)
        ownership = OwnershipObservationStore(repository)
        readiness = MarketWideEvidenceReadinessService(
            historical=historical, diagnostics=governance,
            financial_fact_count=lambda instrument_id: len(facts.facts(instrument_id)),
            filing_count=lambda instrument_id: len(filings.list(instrument_id=instrument_id, limit=500)),
            ownership_available=lambda instrument_id: bool(ownership.list_by_instrument(instrument_id, limit=1)),
            reliability_available=lambda instrument_id: bool(reliability.list(canonical_instrument_id=instrument_id)),
        )
        application.state.market_wide_external_evidence_repository = external_evidence
        application.state.market_wide_evidence_resources = (historical, facts, filings)
        application.state.market_wide_watch_service = MarketWideWatchService(
            repository=repository, universe=CoreUniverseAnalysisStore(repository),
            memberships=HistoricalSecurityMasterStore(repository), diagnostics=governance, governance=governance,
            rankings=CurrentSectorRankingStore(repository),
            reliability=reliability,
            external_evidence_provider=lambda _as_of: external_evidence.list_all_evidence_versions(),
            evidence_readiness=readiness,
        )
    application.state.dhan_live_market_runtime.start()
    application.state.runtime_started = True
    yield
    application.state.runtime_started = False
    application.state.dhan_live_market_runtime.stop()
    if application.state.owns_core_api_snapshot_repository and hasattr(repository, "close"):
        repository.close()
    validation_repository = getattr(application.state, "upstox_validation_repository", None)
    if validation_repository is not None and validation_repository is not repository and hasattr(validation_repository, "close"):
        validation_repository.close()
    external_repository = getattr(application.state, "external_intelligence_application_repository", None)
    if getattr(application.state, "owns_external_intelligence_application_repository", False) and external_repository is not None:
        external_repository.close()
    decision_score_repository = getattr(application.state, "decision_score_governance_repository", None)
    if decision_score_repository is not None and hasattr(decision_score_repository, "close"):
        decision_score_repository.close()
    market_wide_external_evidence_repository = getattr(application.state, "market_wide_external_evidence_repository", None)
    if market_wide_external_evidence_repository is not None and hasattr(market_wide_external_evidence_repository, "close"):
        market_wide_external_evidence_repository.close()
    for resource in getattr(application.state, "market_wide_evidence_resources", ()):
        if hasattr(resource, "close"):
            resource.close()


def create_app(
    *,
    api_settings: APISettings | None = None,
    feature_settings: FeatureSettings | None = None,
    portfolio_query_service: PortfolioQueryService | None = None,
    portfolio_import_service: PortfolioImportService | None = None,
    portfolio_analysis_job_service: PortfolioAnalysisJobService | None = None,
    market_regime_query_service: MarketRegimeQueryService | None = None,
    sector_query_service: SectorQueryService | None = None,
    stock_analysis_query_service: StockAnalysisQueryService | None = None,
    signal_query_service: SignalQueryService | None = None,
    paper_trade_query_service: PaperTradeQueryService | None = None,
    performance_query_service: PerformanceQueryService | None = None,
    benchmark_query_service: BenchmarkQueryService | None = None,
    governance_query_service: GovernanceQueryService | None = None,
    connection_service: ProviderConnectionService | None = None,
    runtime_health_service: RuntimeHealthService | None = None,
    data_source_composition_service: DataSourceCompositionService | None = None,
    filings_query_service: FilingsQueryService | None = None,
    fundamentals_query_service: FundamentalsQueryService | None = None,
    news_query_service: NewsQueryService | None = None,
    primary_market_query_service=None,
    capital_rotation_query_service: CapitalRotationQueryService | None = None,
    breadth_query_service: BreadthQueryService | None = None,
    market_extremes_query_service: MarketExtremesQueryService | None = None,
    crisis_query_service: CrisisQueryService | None = None,
    universe_opportunity_query_service: UniverseOpportunityQueryService | None = None,
    shared_brain_application_service: SharedBrainApplicationService | None = None,
    data_operations_service: DataOperationsService | None = None,
    external_intelligence_application_service: ExternalIntelligenceApplicationService | None = None,
    core_api_snapshot_repository=None,
) -> FastAPI:
    settings = api_settings or APISettings.from_environment()
    validate_local_operator_runtime(settings.database)
    features = feature_settings or FeatureSettings.from_environment()
    application = FastAPI(
        title=settings.application_name,
        description="Provider-independent NSE research and paper-trading backend.",
        version=settings.application_version,
        openapi_tags=[{"name": "system", "description": "Operational system information."}],
        lifespan=_lifespan,
    )
    application.state.api_settings = settings
    application.state.database_settings = settings.database
    application.state.core_api_snapshot_repository = core_api_snapshot_repository
    application.state.owns_core_api_snapshot_repository = False
    application.state.upstox_validation_repository = None
    application.state.feature_settings = features
    application.state.portfolio_query_service = portfolio_query_service or UnavailablePortfolioQueryService()
    application.state.portfolio_import_service = portfolio_import_service or PortfolioImportService()
    application.state.portfolio_analysis_job_service = portfolio_analysis_job_service
    application.state.market_regime_query_service = market_regime_query_service or UnavailableMarketRegimeQueryService()
    application.state.sector_query_service = sector_query_service or UnavailableSectorQueryService()
    application.state.stock_analysis_query_service = stock_analysis_query_service or UnavailableStockAnalysisQueryService()
    application.state.signal_query_service = signal_query_service or UnavailableSignalQueryService()
    application.state.paper_trade_query_service = paper_trade_query_service or UnavailablePaperTradeQueryService()
    application.state.performance_query_service = performance_query_service or UnavailablePerformanceQueryService()
    application.state.benchmark_query_service = benchmark_query_service or UnavailableBenchmarkQueryService()
    application.state.governance_query_service = governance_query_service or UnavailableGovernanceQueryService()
    def current_universe_symbols() -> tuple[str, ...]:
        repository = application.state.core_api_snapshot_repository
        if repository is None:
            return ()
        store = CoreUniverseAnalysisStore(repository)
        return tuple(item.symbol for item in store.instruments_as_of(datetime.now(UTC)) if item.exchange == "NSE" and item.tradable is not False)

    def upstox_universe_store() -> CoreUniverseAnalysisStore:
        repository = application.state.core_api_snapshot_repository
        # API tests/defaults intentionally use an in-memory read model. A local
        # operator's imported NSE universe is durable, however, so this explicit
        # Settings validation path composes the existing persistent local store
        # rather than pretending an empty in-memory API store is the universe.
        if repository is None or application.state.database_settings.storage_mode.value == "IN_MEMORY_SQLITE":
            repository = application.state.upstox_validation_repository
            if repository is None:
                repository = create_core_api_snapshot_repository(DatabaseSettings.local_runtime())
                application.state.upstox_validation_repository = repository
        return CoreUniverseAnalysisStore(repository)

    def upstox_historical_store():
        database = application.state.database_settings
        if database.storage_mode.value == "IN_MEMORY_SQLITE":
            database = DatabaseSettings.local_runtime()
        if database.backend is DatabaseBackend.SQLITE:
            return SQLiteHistoricalBarStore(database.url.removeprefix("sqlite:///"))
        return PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(database))

    credential_store = create_credential_store()
    application.state.connection_credential_store = credential_store
    application.state.connection_service = connection_service or ProviderConnectionService(
        SQLiteConnectionProfileRepository(),
        credential_store,
        universe_symbols_provider=current_universe_symbols,
        upstox_universe_store_provider=upstox_universe_store,
        upstox_historical_store_provider=upstox_historical_store,
    )
    application.state.runtime_health_service = runtime_health_service or RuntimeHealthService(settings=RuntimeSchedulerSettings.from_environment())
    application.state.data_source_composition_service = data_source_composition_service or DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment())
    application.state.filings_query_service = filings_query_service or UnavailableFilingsQueryService()
    application.state.fundamentals_query_service = fundamentals_query_service or UnavailableFundamentalsQueryService()
    application.state.news_query_service = news_query_service or _persistent_news_query_service(settings.database)
    application.state.primary_market_query_service = primary_market_query_service or UnavailablePrimaryMarketQueryService()
    application.state.capital_rotation_query_service = capital_rotation_query_service or UnavailableCapitalRotationQueryService()
    application.state.breadth_query_service = breadth_query_service or UnavailableBreadthQueryService()
    application.state.market_extremes_query_service = market_extremes_query_service or UnavailableMarketExtremesQueryService()
    application.state.crisis_query_service = crisis_query_service or UnavailableCrisisQueryService()
    application.state.universe_opportunity_query_service = universe_opportunity_query_service
    application.state.shared_brain_application_service = shared_brain_application_service
    application.state.data_operations_service = data_operations_service
    application.state.external_intelligence_application_service = external_intelligence_application_service
    application.state.market_wide_watch_service = None
    from app.market_data.dhan import DhanCredentialService
    from app.market_data.dhan_live import DhanLiveFeedService, PersistedSetupLevels, open_dhan_live_transport
    from app.market_data.dhan_live_runtime import DhanLiveMarketRuntime
    from app.market_data.dhan_mapping import DhanProviderMappingService, current_dhan_targets
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRunStore
    from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore
    enabled = os.getenv("DHAN_LIVE_MARKET_ENABLED", "").strip().lower() == "true"
    def dhan_targets():
        repository = application.state.core_api_snapshot_repository
        if repository is None:
            return ()
        target_set = current_dhan_targets(
            portfolio=application.state.portfolio_query_service,
            top3_runs=Top3OpportunityFinderRunStore(repository),
            setup_opportunities=CanonicalSetupOpportunityStore(repository),
            as_of=datetime.now(UTC),
        )
        return DhanProviderMappingService(CoreUniverseAnalysisStore(repository)).ltp_targets(targets=target_set, as_of=datetime.now(UTC))

    def dhan_symbols() -> dict[str, str]:
        repository = application.state.core_api_snapshot_repository
        if repository is None:
            return {}
        return {
            item.instrument_id: item.symbol
            for item in CoreUniverseAnalysisStore(repository).instruments_as_of(datetime.now(UTC))
        }

    def dhan_setup_levels() -> tuple[PersistedSetupLevels, ...]:
        repository = application.state.core_api_snapshot_repository
        if repository is None:
            return ()
        # These are existing current canonical opportunities.  Reading them
        # does not create a setup or alter its decision-time evidence.
        values = CanonicalSetupOpportunityStore(repository).list(as_of=datetime.now(UTC))
        latest = {}
        for item in values:
            latest[item.canonical_instrument_id] = item
        return tuple(
            PersistedSetupLevels(
                canonical_instrument_id=item.canonical_instrument_id,
                entry=item.candidate.breakout_confirmation_trigger,
                stop=item.candidate.final_structural_stop,
                t1=item.candidate.measured_move_target,
                e_max=item.candidate.maximum_executable_entry_price,
            )
            for item in sorted(latest.values(), key=lambda value: value.canonical_instrument_id)
        )

    application.state.dhan_live_market_runtime = DhanLiveMarketRuntime(
        enabled=enabled, feed=DhanLiveFeedService(DhanCredentialService(credential_store)),
        target_loader=dhan_targets, transport_factory=lambda url: open_dhan_live_transport(url, timeout_seconds=30),
        portfolio_snapshot_loader=lambda: application.state.portfolio_query_service.get_snapshot(),
        symbol_loader=dhan_symbols, setup_levels_loader=dhan_setup_levels,
    )
    application.state.market_wide_external_evidence_repository = None
    application.state.market_wide_evidence_resources = ()
    application.state.external_intelligence_application_repository = None
    application.state.owns_external_intelligence_application_repository = False
    application.state.repository_query_service_factories = tuple(
        (attribute, factory) for attribute, supplied, factory in (
            ("portfolio_query_service", portfolio_query_service, RepositoryPortfolioQueryService),
            ("market_regime_query_service", market_regime_query_service, RepositoryMarketRegimeQueryService),
            ("sector_query_service", sector_query_service, RepositorySectorQueryService),
            ("stock_analysis_query_service", stock_analysis_query_service, RepositoryStockAnalysisQueryService),
            ("signal_query_service", signal_query_service, RepositorySignalQueryService),
            ("paper_trade_query_service", paper_trade_query_service, RepositoryPaperTradeQueryService),
            ("performance_query_service", performance_query_service, RepositoryPerformanceQueryService),
            ("benchmark_query_service", benchmark_query_service, RepositoryBenchmarkQueryService),
            ("governance_query_service", governance_query_service, RepositoryGovernanceQueryService),
            ("capital_rotation_query_service", capital_rotation_query_service, RepositoryCapitalRotationQueryService),
            ("breadth_query_service", breadth_query_service, RepositoryBreadthQueryService),
            ("market_extremes_query_service", market_extremes_query_service, RepositoryMarketExtremesQueryService),
            ("crisis_query_service", crisis_query_service, RepositoryCrisisQueryService),
        ) if supplied is None
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "PUT", "POST", "DELETE"],
        allow_headers=["X-Request-ID", "Content-Type"],
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_exception_handler(APIRequestError, api_request_error_handler)
    application.add_exception_handler(RequestValidationError, request_validation_error_handler)
    application.add_exception_handler(Exception, unexpected_exception_handler)
    application.include_router(health_router)
    application.include_router(system_router, prefix=f"/api/{settings.api_version}", tags=["system"])
    application.include_router(portfolio_router, prefix=f"/api/{settings.api_version}")
    application.include_router(portfolio_import_router, prefix=f"/api/{settings.api_version}")
    application.include_router(portfolio_analysis_router, prefix=f"/api/{settings.api_version}")
    application.include_router(market_router, prefix=f"/api/{settings.api_version}")
    application.include_router(sector_router, prefix=f"/api/{settings.api_version}")
    application.include_router(stocks_router, prefix=f"/api/{settings.api_version}")
    application.include_router(signal_paper_router, prefix=f"/api/{settings.api_version}")
    application.include_router(performance_governance_router, prefix=f"/api/{settings.api_version}")
    application.include_router(connections_router, prefix=f"/api/{settings.api_version}")
    application.include_router(connection_setup_router)
    application.include_router(runtime_router, prefix=f"/api/{settings.api_version}")
    application.include_router(data_operations_router, prefix=f"/api/{settings.api_version}")
    application.include_router(intelligence_router, prefix=f"/api/{settings.api_version}")
    application.include_router(data_sources_router, prefix=f"/api/{settings.api_version}")
    application.include_router(filings_router, prefix=f"/api/{settings.api_version}")
    application.include_router(fundamentals_router, prefix=f"/api/{settings.api_version}")
    application.include_router(news_router, prefix=f"/api/{settings.api_version}")
    application.include_router(primary_market_router, prefix=f"/api/{settings.api_version}")
    application.include_router(capital_rotation_router, prefix=f"/api/{settings.api_version}")
    application.include_router(opportunities_router, prefix=f"/api/{settings.api_version}")
    application.include_router(market_wide_watch_router, prefix=f"/api/{settings.api_version}")
    application.include_router(dhan_live_router, prefix=f"/api/{settings.api_version}")

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {"application_name": settings.application_name, "api_version": settings.api_version}

    return application


def _persistent_news_query_service(database: DatabaseSettings) -> NewsQueryService:
    """Expose the existing read-only NEWS contract only for durable stores.

    Unit/API defaults remain intentionally in-memory and unavailable; a local
    production process configured for its persistent repository can read the
    canonical NSE disclosure evidence without a second service or database.
    """
    if database.storage_mode.value == "IN_MEMORY_SQLITE":
        return UnavailableNewsQueryService()
    if database.backend is DatabaseBackend.SQLITE:
        return RepositoryNewsQueryService(SQLiteNewsEvidenceStore(database.url.removeprefix("sqlite:///")))
    return RepositoryNewsQueryService(PostgreSQLNewsEvidenceStore(DatabaseConnectionFactory(database)))


app = create_app()
