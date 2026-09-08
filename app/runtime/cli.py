"""Local-only runtime commands; no credentials or control HTTP endpoints."""

from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Callable, Sequence
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.runtime.cycle import RuntimeCycleResult, RuntimeCycleStatus, RuntimeMode
from app.runtime.scheduler import RuntimeHealthService, RuntimeScheduler, RuntimeSchedulerSettings, RuntimeWorker
from app.data_operations.files import FileStagingLayout, NodeDeliveryAcquirer, NseDeliveryStagingJob
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshStatus
from app.data_operations.service import DataOperationsScheduler, DataOperationsService, DataOperationsSettings, DataOperationsWorker
from app.data_operations.store import DataOperationsStore
from app.connections.credentials import create_credential_store
from app.market_data.dhan import DhanAuthError


class RuntimeCompositionError(RuntimeError):
    """Raised when a host has not supplied explicit stored-data dependencies."""

def build_nse_import_service():
    """Compose the strict existing frozen-40 official-file importer.

    This command intentionally cannot turn a supplied export into a whole-NSE
    ingestion.  It reuses the last persisted 40-stock real-Brain cohort and
    maps only its canonical identities.
    """
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.fundamentals.adapter import FundamentalsEngineAdapter
    from app.fundamentals.adapter import FundamentalsEngineAdapter
    from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
    from app.nse_import.service import (
        FrozenCohortInstrumentResolver, ImportRunStore, NSEOfficialExportProvider,
        OfficialExchangeImportService,
    )
    from app.real_brain.service import RealBrainTrialStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE:
        raise RuntimeCompositionError("Frozen local NSE official-file import currently requires PERSISTENT_SQLITE.")
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("Frozen local NSE official-file import requires a persistent database.")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository)
    snapshot = universe.latest_universe_snapshot()
    trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    if snapshot is None or trial is None or len(trial.selected_instrument_ids) != 40:
        raise RuntimeCompositionError("FROZEN_40_REAL_BRAIN_COHORT_REQUIRED")
    if trial.universe_checksum != snapshot.checksum:
        raise RuntimeCompositionError("FROZEN_COHORT_UNIVERSE_MISMATCH")
    identities = tuple(
        InstrumentIdentity(
            item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin,
            None, InstrumentType.NSE_EQUITY, item.company_name,
        )
        for item in universe.instruments_as_of(snapshot.as_of)
    )
    resolver = FrozenCohortInstrumentResolver(identities, trial.selected_instrument_ids)
    return OfficialExchangeImportService(
        NSEOfficialExportProvider(), resolver, SQLiteCorporateFilingsStore(path),
        SQLiteFinancialFactStore(path), ImportRunStore(path),
    )


# This is the approved feasibility cohort only.  The command cannot expand the
# operation to another instrument or to frozen-40 without a later explicit task.
_BSE_FINANCIAL_FEASIBILITY_COHORT = (
    ("INE437A01024", "APOLLOHOSP", "508869"),
    ("INE429E01023", "SAFARI", "523025"),
    ("INE0PPK01015", "ORIENTTECH", "544235"),
)


def build_bse_financial_feasibility_import_service():
    """Compose only the exact three-instrument BSE XBRL feasibility import."""
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.bse_official import BSEOfficialFinancialResultsIngestionService, BSEOfficialFinancialResultsProvider
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("BSE three-stock feasibility import requires PERSISTENT_SQLITE.")
    path = settings.url.removeprefix("sqlite:///")
    universe = CoreUniverseAnalysisStore(create_core_api_snapshot_repository(settings))
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        raise RuntimeCompositionError("BSE_OFFICIAL_UNIVERSE_SNAPSHOT_REQUIRED")
    identities = {item.isin.upper(): item for item in universe.instruments_as_of(snapshot.as_of) if item.isin}
    targets: list[tuple[InstrumentIdentity, str]] = []
    for isin, symbol, code in _BSE_FINANCIAL_FEASIBILITY_COHORT:
        item = identities.get(isin)
        if item is None or item.symbol != symbol:
            raise RuntimeCompositionError("BSE_THREE_STOCK_IDENTITY_MISMATCH")
        targets.append((InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, None, InstrumentType.NSE_EQUITY, item.company_name), code))
    return (
        BSEOfficialFinancialResultsIngestionService(
            BSEOfficialFinancialResultsProvider(), SQLiteCorporateFilingsStore(path), SQLiteFinancialFactStore(path),
            mapping_store=universe,
        ),
        tuple(targets),
    )


def build_real_portfolio_bse_official_financial_collector():
    """Compose the fixed five-holding official-BSE collector.

    There are deliberately no target, URL, credential, or provider arguments:
    the collector discovers only its approved exact-ISIN BSE mappings and its
    public BSE result/XBRL links.
    """
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.bse_collector import (
        BseOfficialFinancialCollector, BseOfficialHttpTransport,
        BseOfficialSecurityMaster, BseOfficialXbrlStaging,
    )
    from app.fundamentals.bse_official import BSEOfficialFinancialResultsArchiveProvider
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("BSE_REAL_PORTFOLIO_COLLECTOR_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    universe = CoreUniverseAnalysisStore(create_core_api_snapshot_repository(settings))
    transport = BseOfficialHttpTransport()
    workspace_root = Path(__file__).resolve().parents[2]
    return BseOfficialFinancialCollector(
        universe=universe,
        filings=SQLiteCorporateFilingsStore(path),
        facts=SQLiteFinancialFactStore(path),
        security_master=BseOfficialSecurityMaster(transport),
        provider=BSEOfficialFinancialResultsArchiveProvider(fetch_csv=transport.fetch_results_archive),
        transport=transport,
        staging=BseOfficialXbrlStaging(
            workspace_root / "data" / "official_sources" / "bse_financial_results" / "collector",
        ),
    )


def build_nifty500_bse_financial_acquisition_orchestrator():
    """Compose the explicit, bounded official-BSE NIFTY 500 coordinator.

    No caller can supply a URL, security code, token, or alternate provider.
    The coordinator derives every target from the current governed NIFTY 500
    universe and accepts only an exact ISIN mapping from BSE.
    """
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.bse_collector import (
        BseOfficialHttpTransport, BseOfficialSecurityMaster, BseOfficialXbrlStaging,
    )
    from app.fundamentals.bse_nifty500_acquisition import (
        BseFinancialAcquisitionStore, BseNifty500FinancialAcquisitionOrchestrator,
    )
    from app.fundamentals.bse_official import BSEOfficialFinancialResultsArchiveProvider
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("BSE_NIFTY500_ACQUISITION_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository)
    if universe.latest_universe_snapshot() is None:
        raise RuntimeCompositionError("BSE_NIFTY500_UNIVERSE_SNAPSHOT_REQUIRED")
    transport = BseOfficialHttpTransport()
    root = Path(__file__).resolve().parents[2]
    return BseNifty500FinancialAcquisitionOrchestrator(
        repository=BseFinancialAcquisitionStore(repository), universe=universe,
        memberships=HistoricalSecurityMasterStore(repository),
        filings=SQLiteCorporateFilingsStore(path), facts=SQLiteFinancialFactStore(path),
        security_master=BseOfficialSecurityMaster(transport),
        provider=BSEOfficialFinancialResultsArchiveProvider(fetch_csv=transport.fetch_results_archive),
        transport=transport,
        staging=BseOfficialXbrlStaging(root / "data" / "official_sources" / "bse_financial_results" / "nifty500"),
    )


def build_real_portfolio_intelligence_refresh_service():
    """Compose the existing five-holding diagnostics/Brain chain, stored-only."""
    from app.api.repository_query_services import RepositoryPortfolioQueryService
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.fundamentals.adapter import FundamentalsEngineAdapter
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.intelligence.macro.store import MacroEvidenceStore
    from app.intelligence.market_technical_artifact import SharedBrainMarketTechnicalArtifactEvidenceSource, SharedBrainMarketTechnicalArtifactStore
    from app.intelligence.shared_brain_application import CoreUniverseInstrumentResolver, SharedBrainApplicationService, StoredSharedBrainEvidenceAssembler
    from app.ownership.store import OwnershipObservationStore
    from app.production_v1.canonical_setup import CanonicalSetupOpportunityStore
    from app.reliability.integrity import ReliabilityIntegrityObservationStore
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.market_data.current_sector_rotation import CurrentSectorRankingStore
    from app.news.store import SQLiteNewsEvidenceStore
    from app.portfolio.canonical_diagnostics_orchestration import CanonicalPortfolioDiagnosticsOrchestrator
    from app.real_brain.local import StoredTrialObservationSource
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.taxonomy.service import TaxonomySnapshotStore
    from app.universe_analysis.service import Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler
    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("REAL_PORTFOLIO_INTELLIGENCE_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///"); repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository); historical = SQLiteHistoricalBarStore(path)
    governance = SQLiteStrategyGovernanceRepository(path)
    brain = SharedBrainApplicationService(
        resolver=CoreUniverseInstrumentResolver(universe),
        evidence_assembler=StoredSharedBrainEvidenceAssembler(SQLiteFinancialFactStore(path), historical, filings=SQLiteCorporateFilingsStore(path), ownership_observations=OwnershipObservationStore(repository), historical_security_master=HistoricalSecurityMasterStore(repository), taxonomy=TaxonomySnapshotStore(repository), sector_rankings=CurrentSectorRankingStore(repository), macro_evidence_source=MacroEvidenceStore(repository), news=SQLiteNewsEvidenceStore(path), market_technical_artifacts=SharedBrainMarketTechnicalArtifactEvidenceSource(SharedBrainMarketTechnicalArtifactStore(repository)), reliability_integrity_observations=ReliabilityIntegrityObservationStore(repository), decision_scores=governance, setup_assessments=governance, setup_opportunities=CanonicalSetupOpportunityStore(repository)),
    )
    snapshot = RepositoryPortfolioQueryService(repository).get_snapshot()
    source = StoredTrialObservationSource(historical=historical, instrument_ids=("NSE:INE372A01015", "NSE:INE0FHS01024", "NSE:INE955D01029", "NSE:INE068V01023", "NSE:INE090A01021"), as_of=datetime.now(UTC), fundamentals=FundamentalsEngineAdapter(SQLiteFinancialFactStore(path), SQLiteCorporateFilingsStore(path)))
    service = CanonicalPortfolioDiagnosticsOrchestrator(universe=universe, assembler=StockDiagnosticInputAssembler(source), runner=Canonical61DiagnosticRunner(), governance=governance, shared_brain=brain)
    return service, snapshot, repository, historical, governance


def build_real_portfolio_reliability_integrity_context():
    """Compose the fixed five-holding, stored-only reliability projection.

    The assembler intentionally excludes stored Reliability / Integrity
    observations while constructing the input state, preventing the new
    artifact from referring to itself on a later idempotency pass.
    """
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.intelligence.macro.store import MacroEvidenceStore
    from app.intelligence.market_technical_artifact import SharedBrainMarketTechnicalArtifactEvidenceSource, SharedBrainMarketTechnicalArtifactStore
    from app.intelligence.shared_brain_application import CoreUniverseInstrumentResolver, StoredSharedBrainEvidenceAssembler
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.news.store import SQLiteNewsEvidenceStore
    from app.ownership.store import OwnershipObservationStore
    from app.reliability.integrity import ReliabilityIntegrityObservationStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.service import TaxonomySnapshotStore
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("REAL_PORTFOLIO_RELIABILITY_INTEGRITY_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    historical = SQLiteHistoricalBarStore(path)
    universe = CoreUniverseAnalysisStore(repository)
    assembler = StoredSharedBrainEvidenceAssembler(
        SQLiteFinancialFactStore(path), historical,
        filings=SQLiteCorporateFilingsStore(path),
        ownership_observations=OwnershipObservationStore(repository),
        historical_security_master=HistoricalSecurityMasterStore(repository),
        taxonomy=TaxonomySnapshotStore(repository),
        macro_evidence_source=MacroEvidenceStore(repository),
        news=SQLiteNewsEvidenceStore(path),
        market_technical_artifacts=SharedBrainMarketTechnicalArtifactEvidenceSource(
            SharedBrainMarketTechnicalArtifactStore(repository),
        ),
    )
    return CoreUniverseInstrumentResolver(universe), assembler, ReliabilityIntegrityObservationStore(repository), repository, historical


def build_nse_universe_importer():
    """Compose the official-file universe importer from explicit DB settings.

    An in-memory default is intentionally rejected: a successful command must
    create a durable immutable universe snapshot, not merely validate a file
    and discard it when the process exits.
    """
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.importer import OfficialNseUniverseImporter
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("import-nse-universe requires PERSISTENT_SQLITE or POSTGRESQL; sqlite:///:memory: is not durable.")
    return OfficialNseUniverseImporter(CoreUniverseAnalysisStore(create_core_api_snapshot_repository(settings)))


def build_nse_tick_master_importer():
    """Compose a local-only NSE/NDAL CM master importer; never download data."""
    from app.market_data.reference_data.nse_master import NseTickMasterLocalImporter
    from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("NSE_TICK_MASTER_IMPORT_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    universe = CoreUniverseAnalysisStore(create_core_api_snapshot_repository(settings))
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        raise RuntimeCompositionError("NSE_TICK_MASTER_UNIVERSE_SNAPSHOT_REQUIRED")
    repository = SQLiteTickSizeObservationRepository(path)
    return NseTickMasterLocalImporter(repository, universe.instruments_as_of(snapshot.as_of)), repository


def build_data_readiness_service():
    """Return a local persistent-store readiness composition without network I/O."""
    from app.runtime.data_readiness import LocalDataReadinessService
    from app.storage.database import DatabaseSettings
    return LocalDataReadinessService(DatabaseSettings.local_runtime())


def build_forward_paper_service():
    """Compose only the durable internal ledger; no setup/provider execution is implied."""
    from app.forward_paper.service import ForwardPaperService
    from app.forward_paper.store import ForwardPaperStore
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    settings = DatabaseSettings.local_runtime()
    return ForwardPaperService(ForwardPaperStore(create_core_api_snapshot_repository(settings)))


def build_controlled_forward_paper_runtime():
    """Compose the existing U18 stored-only paper seam for an explicit run.

    This is intentionally not a broker, account, or provider composition.  It
    reads immutable governed setups and canonical historical bars only.
    """
    from decimal import Decimal
    from app.forward_paper.composition import StoredExecutableSetupStore, StoredForwardPaperComposition
    from app.forward_paper.models import PaperExecutionModel
    from app.forward_paper.service import ForwardPaperOrchestrator, ForwardPaperService
    from app.forward_paper.store import ForwardPaperStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.production_v1.governed_setup_source import GovernedExecutableSetupSourceRunStore
    from app.production_v1.local import _paper_bar_composition_readiness, _paper_setup_composition_readiness
    from app.production_v1.models import ProductionReadinessState
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository

    settings = DatabaseSettings.local_runtime()
    repository = create_core_api_snapshot_repository(settings)
    historical = (
        SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
        if settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    )
    setups = StoredExecutableSetupStore(repository)
    composition = StoredForwardPaperComposition(
        setups, historical, HistoricalSecurityMasterStore(repository),
    )
    store = ForwardPaperStore(repository)
    service = ForwardPaperService(store)
    # This is the already-tested v1 internal paper execution model.  It is a
    # descriptive study model only; it neither routes nor reserves capital.
    execution_model = PaperExecutionModel.create(
        version="paper-execution-v1", entry_slippage=Decimal("0"),
        exit_slippage=Decimal("0"), round_trip_friction=Decimal("0.10"),
    )

    def data_ready(at: datetime) -> bool:
        run = GovernedExecutableSetupSourceRunStore(repository).latest(as_of=at)
        values = setups.list(as_of=at)
        return (
            _paper_setup_composition_readiness(run, values)[0] is ProductionReadinessState.READY
            and _paper_bar_composition_readiness(run, values)[0] is ProductionReadinessState.READY
        )

    orchestrator = ForwardPaperOrchestrator(
        service, execution_model=execution_model,
        admissions=lambda at: composition.admissions(as_of=at),
        bars_for=lambda study, at: composition.bars_for(
            study.admission, start=study.admission.decision_as_of, end=at,
        ),
        data_ready=data_ready,
    )
    return orchestrator, store, (repository, historical)


def build_controlled_production_v1_cycle_service():
    """Compose one explicit Production-v1 cycle from existing local seams."""
    from app.production_v1.controlled_cycle import ControlledProductionV1CycleService
    from app.production_v1.service import ProductionV1CycleRunStore
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository

    settings = DatabaseSettings.local_runtime()
    operations, operation_resources = build_data_operations_service()
    setup_source, setup_resources = build_governed_executable_setup_source_service()
    paper, paper_store, paper_resources = build_controlled_forward_paper_runtime()
    cycle_repository = create_core_api_snapshot_repository(settings)
    readiness = build_production_v1_readiness_service()
    service = ControlledProductionV1CycleService(
        operations=operations, readiness=lambda at: readiness.report(), setup_source=setup_source,
        paper=paper, paper_store=paper_store, cycle_store=ProductionV1CycleRunStore(cycle_repository),
    )
    return service, (*operation_resources, *setup_resources, *paper_resources, cycle_repository)


def build_production_v1_readiness_service():
    from app.production_v1.local import LocalProductionV1ReadinessService
    from app.storage.database import DatabaseSettings
    return LocalProductionV1ReadinessService(DatabaseSettings.local_runtime(), operations_factory=build_data_operations_service)


def build_coverage_report_service():
    from app.data_coverage.local import LocalCoverageReportService
    from app.storage.database import DatabaseSettings
    return LocalCoverageReportService(DatabaseSettings.local_runtime())


def build_prebreakout_policy_governance_command_service():
    """Compose the local SQLite-only human governance command boundary."""
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("PREBREAKOUT_POLICY_GOVERNANCE_REQUIRES_PERSISTENT_SQLITE")
    repository = SQLiteStrategyGovernanceRepository(settings.url.removeprefix("sqlite:///"))
    return PreBreakoutPolicyGovernanceCommandService(repository), repository


def build_governed_executable_setup_source_service(*, time_stop_sessions: int | None = None):
    """Compose the explicit stored-only Pre-Breakout setup source.

    ``time_stop_sessions`` deliberately has no default: it belongs to the
    later U18 paper-study policy.  A current no-setup scan needs no such value;
    a future candidate fails closed until that input is explicitly governed.
    """
    from app.forward_paper.composition import StoredExecutableSetupStore
    from app.market_data.current_sector_rotation import CurrentSectorRankingStore, CurrentSectorRotationService
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.index_close_series import CoreSnapshotIndexCloseStore
    from app.market_data.nse_delivery import NseDeliveryStore
    from app.market_data.reference_data.resolver import TickSizeReferenceResolver
    from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
    from app.production_v1.governed_setup_source import (
        GovernedExecutableSetupSourceRunStore,
        GovernedExecutableSetupSourceService,
    )
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
    from app.strategies.pre_breakout.materialization import GovernedPreBreakoutTechnicalMaterializer
    from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessmentService
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("GOVERNED_EXECUTABLE_SETUP_SOURCE_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    governance_repository = SQLiteStrategyGovernanceRepository(path)
    historical = SQLiteHistoricalBarStore(path) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    tick_repository = SQLiteTickSizeObservationRepository(path)
    universe = CoreUniverseAnalysisStore(repository)
    rotation = CurrentSectorRotationService(
        repository=repository, universe=universe, historical_store=historical,
        index_close_store=CoreSnapshotIndexCloseStore(repository), ranking_store=CurrentSectorRankingStore(repository),
    )
    governance = PreBreakoutPolicyGovernanceService(governance_repository)
    materializer = GovernedPreBreakoutTechnicalMaterializer(
        governance=governance, historical_store=historical, delivery_store=NseDeliveryStore(repository),
        tick_resolver=TickSizeReferenceResolver(tick_repository),
    )
    assessments = GovernedPreBreakoutSetupAssessmentService(
        materializer=materializer, sector_rotation_service=rotation,
    )
    return (
        GovernedExecutableSetupSourceService(
            assessment_service=assessments, assessment_repository=governance_repository,
            rotation_service=rotation, setup_store=StoredExecutableSetupStore(repository),
            run_store=GovernedExecutableSetupSourceRunStore(repository), time_stop_sessions=time_stop_sessions,
        ),
        (repository, governance_repository, historical, tick_repository),
    )


def build_taxonomy_importer():
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.service import TaxonomyCsvImporter, TaxonomySnapshotStore
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    settings = DatabaseSettings.local_runtime(); repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository).latest_universe_snapshot()
    if universe is None:
        raise RuntimeCompositionError("import-taxonomy requires an existing official NSE UniverseSnapshot.")
    instruments = CoreUniverseAnalysisStore(repository).instruments_as_of(universe.as_of)
    return TaxonomyCsvImporter(TaxonomySnapshotStore(repository)), instruments


def build_nse_indices_taxonomy_importer():
    """Compose the official-file taxonomy importer against the current universe.

    The command accepts already downloaded NSE Indices files.  It never opens a
    provider client or attempts a remote fallback.
    """
    from app.real_brain.service import RealBrainTrialStore
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_indices import NseIndicesTaxonomyImporter
    from app.taxonomy.service import TaxonomySnapshotStore
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    settings = DatabaseSettings.local_runtime(); repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository); snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        raise RuntimeCompositionError("NSE_INDICES_TAXONOMY_REQUIRES_UNIVERSE_SNAPSHOT")
    trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    frozen = trial.selected_instrument_ids if trial is not None else ()
    return NseIndicesTaxonomyImporter(TaxonomySnapshotStore(repository), repository), universe.instruments_as_of(snapshot.as_of), frozen


def build_nse_sector_index_importer():
    """Compose the local-only official NSE sector-index registry importer."""
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexImporter
    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("NSE_SECTOR_INDEX_IMPORT_REQUIRES_PERSISTENT_STORE")
    return NseSectorIndexImporter(create_core_api_snapshot_repository(settings))


def build_real_brain_trial_service():
    """Compose a bounded, stored-data-only local trial; no provider fallback."""
    from app.real_brain.local import LocalRealBrainTrialService
    from app.storage.database import DatabaseSettings
    return LocalRealBrainTrialService(DatabaseSettings.local_runtime())


def build_historical_conflict_store():
    """Compose the existing durable historical store for read-only inspection."""
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("HISTORICAL_CONFLICT_INSPECTION_REQUIRES_PERSISTENT_STORE")
    return (
        SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
        if settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    )


def build_ohlcv_readiness_context():
    """Compose a read-only, no-network per-instrument OHLCV view."""
    from app.market_data.ohlcv_readiness import OhlcvReadinessService
    from app.market_data.upstox import UPSTOX_PROVIDER
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    repository = create_core_api_snapshot_repository(settings)
    historical = build_historical_conflict_store()
    universe = CoreUniverseAnalysisStore(repository)
    watermark = DataOperationsStore(repository).latest_watermark(EvidenceDataFamily.OHLCV)
    return OhlcvReadinessService(historical), universe, watermark, UPSTOX_PROVIDER, (historical, repository)


class _ConflictSubsetOhlcvJob:
    """Bound an existing OHLCV job to prior immutable conflict subjects only."""

    def __init__(self, job: object, instrument_ids: frozenset[str]) -> None:
        self._job, self._instrument_ids = job, instrument_ids

    def refresh(self, request):
        refresh_selected = getattr(self._job, "refresh_selected", None)
        if refresh_selected is None:
            raise ValueError("OHLCV_CONFLICT_RECONCILIATION_JOB_UNAVAILABLE")
        return refresh_selected(request, canonical_instrument_ids=self._instrument_ids)


def build_upstox_frozen_population_service():
    """Compose the explicit 40-stock-only Upstox population boundary."""
    from app.connections.credentials import create_credential_store
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.upstox import load_upstox_nse_bod_instrument_master
    from app.nse_import.service import ImportRunStore
    from app.market_data.upstox_population import FrozenUpstoxPopulationService
    from app.real_brain.service import RealBrainTrialStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository)
    trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    if trial is None or len(trial.selected_instrument_ids) != 40:
        raise RuntimeCompositionError("UPSTOX_FROZEN_40_COHORT_REQUIRED")
    instruments = {item.instrument_id: item for item in universe.instruments_as_of(trial.as_of)}
    if any(identifier not in instruments for identifier in trial.selected_instrument_ids):
        raise RuntimeCompositionError("UPSTOX_FROZEN_40_COHORT_UNIVERSE_MISMATCH")
    values = create_credential_store().load("upstox")
    token = values.get("access_token")
    if not token:
        raise RuntimeCompositionError("UPSTOX_ACCESS_TOKEN_REQUIRED")
    historical = (
        SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
        if settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    )
    master = load_upstox_nse_bod_instrument_master()
    return (
        FrozenUpstoxPopulationService(universe_store=universe, historical_store=historical),
        tuple(instruments[item] for item in trial.selected_instrument_ids), master, historical,
    )


def build_upstox_sector_index_population_service():
    """Compose the explicit Task 38 index-history backfill boundary.

    The command runs only under the interactive user's process because it
    reads the existing Windows Credential Manager Upstox profile.  It never
    runs as part of diagnostics or the stored real-Brain replay.
    """
    from app.connections.credentials import create_credential_store
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.upstox import load_upstox_nse_bod_instrument_master
    from app.market_data.upstox_sector_indices import UpstoxNseIndexPopulationService
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("UPSTOX_SECTOR_INDEX_BACKFILL_REQUIRES_PERSISTENT_STORE")
    token = create_credential_store().load("upstox").get("access_token")
    if not token:
        raise RuntimeCompositionError("UPSTOX_ACCESS_TOKEN_REQUIRED")
    repository = create_core_api_snapshot_repository(settings)
    mappings = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
        mappings.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
        if len(page) < 100:
            break
        offset += len(page)
    historical = (
        SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
        if settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    )
    master = load_upstox_nse_bod_instrument_master()
    return (
        UpstoxNseIndexPopulationService(universe_store=CoreUniverseAnalysisStore(repository), historical_store=historical),
        tuple(mappings), master, historical, token,
    )


def build_upstox_sector_index_status_service():
    """Compose U06's stored-only index history status report without credentials."""
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("UPSTOX_SECTOR_INDEX_STATUS_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    values = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
        values.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
        if len(page) < 100:
            break
        offset += len(page)
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    return historical, tuple(values)


def build_current_sector_rotation_service():
    """Compose U07's current/forward stored-data sector route only."""
    from app.market_data.current_sector_rotation import CurrentSectorRankingStore, CurrentSectorRotationService
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.index_close_series import CoreSnapshotIndexCloseStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("CURRENT_SECTOR_ROTATION_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    return CurrentSectorRotationService(
        repository=repository, universe=CoreUniverseAnalysisStore(repository), historical_store=historical,
        index_close_store=CoreSnapshotIndexCloseStore(repository), ranking_store=CurrentSectorRankingStore(repository),
    ), historical


def build_official_nse_index_close_series_refresh():
    """Compose the fixed four-index official close-only acquisition boundary."""
    from app.market_data.index_close_series import CoreSnapshotIndexCloseStore, OfficialNseIndexCloseSeriesRefresh
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("OFFICIAL_NSE_INDEX_CLOSE_SERIES_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    mappings = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
        mappings.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
        if len(page) < 100:
            break
        offset += len(page)
    expected = {
        "Capital Goods": ("NSE_SECTOR_INDEX:CAPITAL_GOODS", "Nifty Capital Goods"),
        "Construction": ("NSE_SECTOR_INDEX:CONSTRUCTION", "Nifty Construction"),
        "Consumer Services": ("NSE_SECTOR_INDEX:CONSUMER_SERVICES", "Nifty Consumer Services"),
        "Power": ("NSE_SECTOR_INDEX:POWER", "Nifty Power"),
    }
    found = {item.canonical_sector: item for item in mappings if item.canonical_sector in expected}
    if set(found) != set(expected):
        raise RuntimeCompositionError("OFFICIAL_NSE_SECTOR_INDEX_REGISTRY_TARGETS_REQUIRED")
    targets = []
    for sector, (canonical_id, official_name) in expected.items():
        mapping = found[sector]
        if mapping.status is not SectorIndexMappingStatus.EXACT_OFFICIAL or mapping.official_index_name != official_name:
            raise RuntimeCompositionError("OFFICIAL_NSE_SECTOR_INDEX_EXACT_IDENTITY_REQUIRED")
        targets.append((canonical_id, official_name))
    root = Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_index_close_series"
    return OfficialNseIndexCloseSeriesRefresh(
        store=CoreSnapshotIndexCloseStore(repository), targets=tuple(sorted(targets)), artifact_directory=root,
    ), repository


def build_official_nse_index_ohlc_series_refresh():
    """Compose exactly the active Rule 1--3/6 first-party PRI targets."""
    from app.market_data.official_nse_index_ohlc import CoreSnapshotOfficialIndexOhlcStore, OfficialNseIndexOhlcSeriesRefresh
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
    from app.universe_analysis.benchmark_sector_technical_input import canonical_sector_index_id

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("OFFICIAL_NSE_INDEX_OHLC_SERIES_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    mappings = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
        mappings.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
        if len(page) < 100:
            break
        offset += len(page)
    exact = tuple(sorted(
        (item for item in mappings if item.status is SectorIndexMappingStatus.EXACT_OFFICIAL and item.official_index_name),
        key=lambda item: item.canonical_sector,
    ))
    targets = [("NIFTY_50", "Nifty 50")]
    targets.extend((canonical_sector_index_id(item.canonical_sector), item.official_index_name) for item in exact)
    root = Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_index_ohlc_series"
    return OfficialNseIndexOhlcSeriesRefresh(
        store=CoreSnapshotOfficialIndexOhlcStore(repository), targets=tuple(sorted(targets)), artifact_directory=root,
    ), repository


def build_official_nse_sector_index_alias_ohlc_lineage_refresh():
    """Compose only retained, exact source-query alias OHLC targets.

    This is intentionally narrower than the broad sector-index refresh: it
    permits current-descriptive canonicalization only for the two catalogued
    first-party aliases whose static identity evidence has been reviewed.
    """
    from app.market_data.official_nse_index_ohlc import (
        CoreSnapshotOfficialIndexOhlcStore,
        OfficialIndexOhlcTarget,
        OfficialNseIndexOhlcSeriesRefresh,
    )
    from app.market_data.official_nse_index_ohlc_reconciliation import (
        OfficialIndexSourceQueryResolutionStatus,
        resolve_official_nse_index_source_query,
    )
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
    from app.universe_analysis.benchmark_sector_technical_input import canonical_sector_index_id

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("OFFICIAL_NSE_INDEX_OHLC_SERIES_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    mappings = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
        mappings.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
        if len(page) < 100:
            break
        offset += len(page)
    target_ids = {
        "NSE_SECTOR_INDEX:CONSUMER_DURABLES",
        "NSE_SECTOR_INDEX:HEALTHCARE",
    }
    exact = tuple(sorted(
        (item for item in mappings if item.status is SectorIndexMappingStatus.EXACT_OFFICIAL and item.official_index_name),
        key=lambda item: item.canonical_sector,
    ))
    targets = []
    for mapping in exact:
        canonical_index_id = canonical_sector_index_id(mapping.canonical_sector)
        if canonical_index_id not in target_ids:
            continue
        resolution = resolve_official_nse_index_source_query(
            mapping=mapping, canonical_index_id=canonical_index_id,
        )
        if resolution.status is not OfficialIndexSourceQueryResolutionStatus.SOURCE_QUERY_ALIAS_PROVEN:
            raise RuntimeCompositionError("OFFICIAL_NSE_INDEX_SOURCE_QUERY_ALIAS_REQUIRED")
        targets.append(OfficialIndexOhlcTarget(
            resolution.canonical_index_id, resolution.canonical_mapping_name,
            resolution.source_query_name, resolution,
        ))
    if {item.canonical_index_id for item in targets} != target_ids:
        raise RuntimeCompositionError("OFFICIAL_NSE_INDEX_SOURCE_QUERY_ALIAS_TARGETS_REQUIRED")
    root = Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_index_ohlc_series"
    return OfficialNseIndexOhlcSeriesRefresh(
        store=CoreSnapshotOfficialIndexOhlcStore(repository),
        targets=tuple(sorted(targets, key=lambda item: item.canonical_index_id)), artifact_directory=root,
    ), repository


def build_current_sector_constituent_backfill_service():
    """Compose the explicit live U07 backfill; it performs no request itself."""
    from app.market_data.current_sector_rotation import CurrentSectorConstituentBackfillService
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("CURRENT_SECTOR_BACKFILL_REQUIRES_PERSISTENT_STORE")
    repository = create_core_api_snapshot_repository(settings)
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    return CurrentSectorConstituentBackfillService(universe=CoreUniverseAnalysisStore(repository), historical_store=historical), historical


def build_current_prebreakout_service():
    """Compose the read-only U09 delivery gate over the current Top-3."""
    from app.market_data.current_prebreakout import CurrentPreBreakoutService
    from app.market_data.nse_delivery import NseDeliveryStore
    from app.storage.database import DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    rotation, historical = build_current_sector_rotation_service()
    repository = rotation._repository
    return CurrentPreBreakoutService(rotation_service=rotation, delivery_store=NseDeliveryStore(repository), historical_store=historical, clock=lambda: datetime.now(UTC)), historical


def build_nse_delivery_import_service():
    """Compose official local delivery ingestion for the canonical universe.

    The parser is unchanged: it accepts only staged official NSE full
    bhavcopy files, matches exact symbols, keeps every observation append-only,
    and never estimates delivery.  U09's Top-3 read model remains a consumer,
    not an ingestion boundary.
    """
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.nse_delivery import NseDeliveryReportImporter, NseDeliveryStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    settings = DatabaseSettings.local_runtime(); repository = create_core_api_snapshot_repository(settings)
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    universe = CoreUniverseAnalysisStore(repository)
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None:
        raise RuntimeCompositionError("NSE_DELIVERY_UNIVERSE_SNAPSHOT_REQUIRED")
    # The snapshot is the provenance anchor, while imported universe identity
    # records can have a later forward-only ``data_as_of``.  Delivery is a
    # current EOD observation, so resolve the currently visible canonical
    # universe instead of accidentally selecting an empty historical slice.
    targets = _production_delivery_targets(snapshot.instrument_ids, universe.instruments_as_of(datetime.now(UTC)))
    return NseDeliveryReportImporter(NseDeliveryStore(repository)), targets, historical


def _production_delivery_targets(canonical_instrument_ids: Sequence[str], instruments: Sequence[object]) -> dict[str, tuple[str, str | None]]:
    """Build exact-symbol delivery targets from the authoritative universe scope.

    Repeated/superseded identity records are tolerated only when they retain a
    single canonical instrument ID.  Ambiguous symbol collisions are excluded,
    never guessed.
    """
    canonical_ids = set(canonical_instrument_ids)
    grouped: dict[str, list[object]] = {}
    for item in instruments:
        instrument_id = getattr(item, "instrument_id", None)
        symbol = getattr(item, "symbol", None)
        if instrument_id not in canonical_ids or not isinstance(symbol, str) or not symbol.strip():
            continue
        grouped.setdefault(symbol.upper(), []).append(item)
    return {
        symbol: (values[0].instrument_id, getattr(values[0], "isin", None) or None)
        for symbol, values in grouped.items()
        if len({item.instrument_id for item in values}) == 1
    }


def migrate_sqlite_provider_versioned_bars_factory():
    """Return the one explicit, network-free U06R SQLite migration operation."""
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.market_data.sqlite_provider_versioned_migration import migrate_sqlite_provider_versioned_historical_bars

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE:
        raise RuntimeCompositionError("SQLITE_PROVIDER_VERSIONED_MIGRATION_REFUSES_POSTGRESQL")
    if settings.url.endswith(":memory:"):
        raise RuntimeCompositionError("SQLITE_PROVIDER_VERSIONED_MIGRATION_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    return lambda: migrate_sqlite_provider_versioned_historical_bars(
        path, report_path=Path("reports/sqlite_provider_versioned_migration.json"),
    )


def build_yfinance_frozen_population_service():
    """Compose the explicit, secondary-research 40-stock yfinance boundary."""
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.yfinance_population import FrozenYahooPopulationService
    from app.real_brain.service import RealBrainTrialStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime(); repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository); trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    if trial is None or len(trial.selected_instrument_ids) != 40:
        raise RuntimeCompositionError("YFINANCE_FROZEN_40_COHORT_REQUIRED")
    instruments = {item.instrument_id: item for item in universe.instruments_as_of(trial.as_of)}
    if any(identifier not in instruments for identifier in trial.selected_instrument_ids):
        raise RuntimeCompositionError("YFINANCE_FROZEN_40_COHORT_UNIVERSE_MISMATCH")
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    return FrozenYahooPopulationService(universe_store=universe, historical_store=historical), tuple(instruments[item] for item in trial.selected_instrument_ids), historical


def build_yahoo_secondary_enrichment_service(*, delay_seconds: float = 0.25):
    """Compose the append-only Yahoo research enrichment for the frozen 40.

    The returned service has no route into canonical FinancialFact or taxonomy
    persistence.  Its official stores are passed only for read-only comparison.
    """
    from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.market_data.yahoo_enrichment import YahooSecondaryEnrichmentService, YahooSecondarySnapshotStore
    from app.real_brain.service import RealBrainTrialStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime(); repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository); trial = RealBrainTrialStore(repository).latest_trial(sample_size=40)
    if trial is None or len(trial.selected_instrument_ids) != 40:
        if hasattr(repository, "close"): repository.close()
        raise RuntimeCompositionError("YAHOO_SECONDARY_FROZEN_40_COHORT_REQUIRED")
    instruments = {item.instrument_id: item for item in universe.instruments_as_of(trial.as_of)}
    if any(identifier not in instruments for identifier in trial.selected_instrument_ids):
        if hasattr(repository, "close"): repository.close()
        raise RuntimeCompositionError("YAHOO_SECONDARY_FROZEN_40_COHORT_UNIVERSE_MISMATCH")
    facts = SQLiteFinancialFactStore(settings.url.removeprefix("sqlite:///")) if settings.backend is DatabaseBackend.SQLITE else PostgreSQLFinancialFactStore(DatabaseConnectionFactory(settings))
    master = HistoricalSecurityMasterStore(repository)
    service = YahooSecondaryEnrichmentService(
        store=YahooSecondarySnapshotStore(repository),
        official_facts=lambda instrument_id: tuple(item for item in facts.facts(instrument_id, limit=500) if item.source.lower().startswith(("bse", "nse"))),
        official_actions=lambda instrument_id, at: master.actions_as_of(instrument_id, at),
        delay_seconds=delay_seconds,
    )
    return service, tuple(instruments[item] for item in trial.selected_instrument_ids), repository


def build_runtime_scheduler(settings: RuntimeSchedulerSettings) -> RuntimeScheduler:
    """Fail safely until a local host composes an explicit store and universe.

    The repository intentionally has no implicit current-universe/data loader.
    A CLI user must use a local host composition rather than silently receiving
    mock data or a network/provider fallback.
    """
    raise RuntimeCompositionError("Runtime coordinator dependencies are not configured for this local process.")


def build_data_operations_service():
    """Compose registered U17 jobs; credentials are read only at run time.

    Upstox is the existing approved V3 history adapter.  Its job is registered
    here but remains explicitly blocked by its own secure-token check until an
    interactive local operator configures the existing ``upstox`` profile.
    The local NSE delivery staging path is likewise only active when targets
    and incoming files exist.  No source falls back to Yahoo, mock, or web
    discovery.
    """
    from app.connections.credentials import create_credential_store
    from app.data_operations.nse_reference import (
        NseCorporateActionsRefreshJob,
        NseIndexMembershipRefreshJob,
        NseTaxonomyReferenceRefreshJob,
    )
    from app.data_operations.official_financials import (
        BseLocalFinancialResultsRefreshJob,
        NseReg31ShareholdingRefreshJob,
    )
    from app.data_operations.nse_news import NseCorporateAnnouncementsRefreshJob
    from app.data_operations.rbi_macro import RbiCurrentRatesRefreshJob, RbiCurrentRatesSource
    from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
    from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
    from app.data_operations.upstox import UpstoxIndexBarsRefreshJob, UpstoxOhlcvRefreshJob
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.news.store import PostgreSQLNewsEvidenceStore, SQLiteNewsEvidenceStore
    from app.intelligence.macro.store import MacroEvidenceStore
    from app.market_data.upstox import load_upstox_nse_bod_instrument_master
    from app.nse_import.service import ImportRunStore
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    repository = create_core_api_snapshot_repository(settings)
    resources = [repository]
    historical = (
        SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
        if settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))
    )
    resources.append(historical)
    financial_path = settings.url.removeprefix("sqlite:///") if settings.backend is DatabaseBackend.SQLITE else None
    filings = SQLiteCorporateFilingsStore(financial_path) if financial_path else PostgreSQLCorporateFilingsStore(DatabaseConnectionFactory(settings))
    facts = SQLiteFinancialFactStore(financial_path) if financial_path else PostgreSQLFinancialFactStore(DatabaseConnectionFactory(settings))
    news = SQLiteNewsEvidenceStore(financial_path) if financial_path else PostgreSQLNewsEvidenceStore(DatabaseConnectionFactory(settings))
    macro = MacroEvidenceStore(repository)
    universe = CoreUniverseAnalysisStore(repository)
    def sector_mappings() -> tuple[NseSectorIndexMapping, ...]:
        values: list[NseSectorIndexMapping] = []
        offset = 0
        while True:
            page = repository.list_snapshots(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, limit=100, offset=offset)
            values.extend(item.payload for item in page if isinstance(item.payload, NseSectorIndexMapping))
            if len(page) < 100:
                return tuple(values)
            offset += len(page)
    jobs = {
        EvidenceDataFamily.OHLCV: UpstoxOhlcvRefreshJob(
            universe_store=universe,
            historical_store=historical,
            token_reader=lambda: create_credential_store().load("upstox").get("access_token"),
            master_loader=load_upstox_nse_bod_instrument_master,
        ),
        EvidenceDataFamily.INDEX_BARS: UpstoxIndexBarsRefreshJob(
            sector_mappings_loader=sector_mappings,
            universe_store=universe,
            historical_store=historical,
            token_reader=lambda: create_credential_store().load("upstox").get("access_token"),
            master_loader=load_upstox_nse_bod_instrument_master,
        ),
    }
    # These are local official-reference adapters only.  The integrated NSE
    # bot currently has a verified acquisition command only for delivery, so
    # no new bot/network path is implied here.
    workspace_root = Path(__file__).resolve().parents[2]
    indices_root = workspace_root / "data" / "official_sources" / "nse_indices" / "2026-08-27"
    actions_root = workspace_root / "data" / "official_sources" / "nse_corporate_actions"
    bse_financial_root = workspace_root / "data" / "official_sources" / "bse_financial_results"
    nse_shareholding_root = workspace_root / "data" / "official_sources" / "nse_shareholding"
    master = HistoricalSecurityMasterStore(repository)
    jobs.update({
        EvidenceDataFamily.INDEX_MEMBERSHIP: NseIndexMembershipRefreshJob(
            repository=repository, universe=universe, source_root=indices_root, master=master,
        ),
        EvidenceDataFamily.TAXONOMY_REFERENCE: NseTaxonomyReferenceRefreshJob(
            repository=repository, universe=universe, source_root=indices_root,
        ),
        EvidenceDataFamily.CORPORATE_ACTIONS: NseCorporateActionsRefreshJob(
            repository=repository, universe=universe, source_directory=actions_root, master=master,
        ),
        EvidenceDataFamily.FINANCIAL_RESULTS: BseLocalFinancialResultsRefreshJob(
            repository=repository, universe=universe, filings=filings, facts=facts,
            source_directory=bse_financial_root,
        ),
        EvidenceDataFamily.SHAREHOLDING: NseReg31ShareholdingRefreshJob(
            repository=repository, universe=universe, filings=filings, facts=facts,
            runs=ImportRunStore(financial_path) if financial_path else ImportRunStore(),
            source_directory=nse_shareholding_root,
        ),
        EvidenceDataFamily.NEWS: NseCorporateAnnouncementsRefreshJob(
            universe=universe, news=news,
        ),
        EvidenceDataFamily.MACRO: RbiCurrentRatesRefreshJob(
            source=RbiCurrentRatesSource(), store=macro,
        ),
    })
    try:
        importer, targets, delivery_historical = build_nse_delivery_import_service()
    except RuntimeCompositionError:
        pass
    else:
        jobs[EvidenceDataFamily.DELIVERY] = NseDeliveryStagingJob(
            importer,
            targets,
            FileStagingLayout(workspace_root / "data"),
            acquirer=NodeDeliveryAcquirer.from_environment(workspace_root),
        )
        resources.append(delivery_historical)
    return DataOperationsService(DataOperationsStore(repository), jobs), tuple(resources)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="python -m app.runtime", description="Local, controlled NSE runtime commands")
    commands = value.add_subparsers(dest="command", required=True)
    run_once = commands.add_parser("run-once", help="Run one explicit runtime cycle")
    run_once.add_argument("--mode", choices=("stored", "mock"))
    run_once.add_argument("--universe")
    run_once.add_argument("--dry-run", action="store_true", help="Run without snapshot publication")
    commands.add_parser("status", help="Read runtime status without running a cycle")
    commands.add_parser("dhan-auth-status", help="Read secret-free Dhan market-data authentication status")
    commands.add_parser("dhan-auth-configure", help="Store Dhan Client ID, API Key, and API Secret through hidden local prompts")
    commands.add_parser("dhan-auth-diagnose", help="Perform only one bounded Dhan Generate Consent diagnostic; never opens a browser")
    nse_udiff_backfill = commands.add_parser(
        "backfill-nse-udiff-daily-history",
        help="Acquire immutable NSE UDiFF Final-Bhavcopy daily source artifacts and additive raw bars; never selects a technical source",
    )
    nse_udiff_backfill.add_argument("--max-sessions", type=int, help="Bound one resumable sequential acquisition run; omit for the approved full UDiFF-era window")
    nse_udiff_integrity = commands.add_parser(
        "audit-nse-udiff-daily-integrity",
        help="Materialize only an explicit-as-of UDiFF source-session coverage receipt; never selects, adjusts, or derives technical bars",
    )
    nse_udiff_integrity.add_argument("--as-of", required=True, help="Timezone-aware ISO8601 evidence cutoff; no runtime-time default")
    commands.add_parser("dhan-materialize-mappings", help="Materialize the current immutable Dhan provider mappings from the official master")
    dhan_ltp_canary = commands.add_parser("dhan-ltp-canary", help="One bounded host-only Dhan LTP batch; defaults to the five portfolio holdings")
    dhan_ltp_canary.add_argument("--scope", choices=("portfolio", "all-current-targets"), default="portfolio", help="Use all stored current targets only when explicitly requested")
    commands.add_parser("dhan-live-feed-status", help="Read the safe in-process Dhan live-feed status")
    dhan_live_canary = commands.add_parser("dhan-live-feed-canary", help="Connect once to Dhan ticker feed using persisted current mappings")
    dhan_live_canary.add_argument("--seconds", type=int, default=30, help="Bound the host live-feed receive timeout")
    commands.add_parser("dhan-live-feed", help="Run the bounded Dhan live feed until Ctrl+C")
    commands.add_parser("dhan-live-feed-diagnose", help="Perform one safe bounded Dhan live-feed handshake diagnostic")
    dhan_auth_start = commands.add_parser("dhan-auth-start", help="Start bounded Dhan browser consent; market-data only")
    dhan_auth_start.add_argument("--open-browser", action="store_true", help="Open the official Dhan consent URL locally after it is generated")
    dhan_auth_start.add_argument("--manual-token-id", action="store_true", help="Read tokenId from a no-echo terminal prompt after the official browser redirect")
    dhan_auth_start.add_argument("--loopback-port", type=int, help="Wait on a pre-registered http://127.0.0.1 callback port for tokenId")
    dhan_auth_start.add_argument("--wait-seconds", type=float, default=180.0, help="Bounded loopback wait; defaults to 180 seconds")
    commands.add_parser("validate-config", help="Validate safe runtime settings")
    commands.add_parser("worker", help="Run the opt-in local interval worker")
    commands.add_parser("data-operations-status", help="Read immutable U17 refresh health without starting jobs")
    data_operations_run = commands.add_parser("data-operations-run", help="Run one U17 evidence family refresh manually")
    data_operations_run.add_argument("--family", choices=tuple(item.value.lower() for item in EvidenceDataFamily), required=True)
    data_operations_run.add_argument("--mode", choices=tuple(item.value.lower() for item in EvidenceRefreshMode), default="incremental")
    commands.add_parser(
        "reconcile-upstox-historical-conflicts",
        help="Explicitly reconcile only the latest recorded Upstox OHLCV conflict subjects",
    )
    historical_conflicts = commands.add_parser(
        "historical-bar-conflicts",
        help="Read immutable same-provider historical OHLCV conflict artifacts without changing bars",
    )
    historical_conflicts.add_argument("--instrument", help="Exact canonical instrument ID filter")
    ohlcv_readiness = commands.add_parser(
        "ohlcv-readiness",
        help="Read stored per-instrument OHLCV readiness without provider access or bar mutation",
    )
    ohlcv_readiness.add_argument("--instrument", help="Exact canonical instrument ID filter")
    commands.add_parser("data-operations-schedule-once", help="Dispatch due configured U17 family jobs once")
    commands.add_parser("data-operations-worker", help="Run the opt-in U17 local operations worker")
    commands.add_parser("paper-trading-status", help="Read internal forward-paper status without evaluating studies")
    commands.add_parser("paper-trading-run", help="Run one explicit opt-in stored-only forward-paper pass")
    commands.add_parser("paper-trading-worker", help="Run the opt-in internal forward-paper worker when its source composition is configured")
    commands.add_parser("production-v1-status", help="Read consolidated Production-V1 operational readiness without network activity")
    production_cycle = commands.add_parser("production-v1-cycle", help="Run one controlled Production-V1 cycle and persist an immutable receipt")
    production_cycle.add_argument("--refresh-due", action="store_true", help="Explicitly dispatch already-due U17 refresh jobs; default reuses stored evidence without provider requests")
    imported = commands.add_parser("import-nse", help="Import one local NSE official export into the existing frozen 40-stock cohort")
    imported.add_argument("file")
    imported.add_argument("--type", choices=("announcements","financial-results","corporate-actions","regulation-30","regulation-31","xbrl-converted-results"))
    imported.add_argument("--dry-run", action="store_true")
    bse_import = commands.add_parser("import-bse-financial-feasibility", help="Import BSE official XBRL for only APOLLOHOSP, SAFARI, and ORIENTTECH")
    bse_import.add_argument("--limit-per-instrument", type=int, default=12)
    commands.add_parser(
        "collect-real-portfolio-bse-financials",
        help="Fetch, verify, stage, and import BSE XBRL for exactly the five approved real-portfolio ISINs",
    )
    commands.add_parser(
        "collect-real-portfolio-bse-historical-annuals",
        help="Fetch, verify, stage, and import up to five BSE annual periods per scope for exactly four approved non-financial ISINs",
    )
    bse_nifty500 = commands.add_parser(
        "bse-nifty500-financials",
        help="Run explicit bounded official-BSE NIFTY 500 financial mapping, planning, and acquisition operations",
    )
    bse_nifty500.add_argument("operation", choices=("mapping-audit", "archive-discovery", "plan", "dry-run", "canary", "run", "resume", "status", "failures"))
    bse_nifty500.add_argument("--as-of", help="Timezone-aware ISO8601 cutoff; defaults to current UTC time")
    bse_nifty500.add_argument("--plan-id", help="Existing immutable plan ID for resume/status/failures")
    bse_nifty500.add_argument("--inventory-id", help="Existing immutable mapping inventory ID for deterministic plan construction")
    bse_nifty500.add_argument("--max-instruments", type=int, help="Bound mapping audit/dry-run; omit only for the full governed universe")
    bse_nifty500.add_argument("--max-units", type=int, help="Bound canary/run/resume work; omit only for a persisted full plan")
    bse_nifty500.add_argument("--batch-size", type=int, default=5, help="Conservative sequential batch boundary (1-25)")
    commands.add_parser(
        "acquire-real-portfolio-nse-shareholding",
        help="Fetch and stage official current NSE Regulation 31 XBRL for exactly the approved five holdings",
    )
    commands.add_parser(
        "correct-real-portfolio-nse-reg31-pit-timestamps",
        help="Append-only correction for only the five pre-fix NSE Reg31 XBRL publication timestamps",
    )
    commands.add_parser(
        "materialize-real-portfolio-nse-reg31-ownership",
        help="Materialize direct ownership observations from only the five corrected official NSE Reg31 XBRLs",
    )
    commands.add_parser(
        "materialize-real-portfolio-reliability-integrity",
        help="Materialize immutable, stored-only Reliability / Integrity observations for exactly the five approved holdings",
    )
    commands.add_parser("refresh-real-portfolio-intelligence", help="Run the existing stored-only five-holding intelligence chain")
    market_wide_watch = commands.add_parser(
        "materialize-market-wide-watch",
        help="Materialize the stored-only NIFTY 500 Quality & Inflection Watch twice for idempotency",
    )
    market_wide_watch.add_argument("--as-of", help="Timezone-aware ISO8601 cutoff; defaults to current UTC time")
    compounder_prospective = commands.add_parser(
        "compounder-prospective-shadow",
        help="Create explicit-as-of immutable Compounder research observations; never qualifies a company",
    )
    compounder_prospective.add_argument("--as-of", required=True, help="Timezone-aware ISO8601 PIT cutoff")
    inflection_accounting_prospective = commands.add_parser(
        "inflection-accounting-prospective-shadow",
        help="Create explicit-as-of immutable Inflection accounting observations; never qualifies an issuer",
    )
    inflection_accounting_prospective.add_argument("--as-of", required=True, help="Timezone-aware ISO8601 PIT cutoff")
    bridge_inbox = commands.add_parser(
        "bridge-external-intelligence-inbox",
        help="Claim and deliver a bounded Supabase intelligence inbox batch to loopback HSI",
    )
    bridge_inbox.add_argument("--once", action="store_true", help="Run one explicit bounded bridge cycle; otherwise run only when the bridge is enabled.")
    universe_import = commands.add_parser("import-nse-universe", help="Import one explicit local NSE equity-universe CSV")
    universe_import.add_argument("file")
    universe_import.add_argument("--dry-run", action="store_true", help="Validate without persisting a universe snapshot")
    universe_import.add_argument(
        "--refresh-identical-as-of", action="store_true",
        help="Create a new forward-only immutable snapshot when the official file content is unchanged",
    )
    tick_master_import = commands.add_parser("import-nse-tick-master", help="Import one explicit local NSE/NDAL CM security.txt or security.gz tick master")
    tick_master_import.add_argument("file")
    tick_master_import.add_argument("--observed-at", help="Timezone-aware ISO8601 observation time; defaults to current UTC time")
    commands.add_parser("data-readiness", help="Report source readiness without provider requests")
    commands.add_parser("universe-status", help="Alias for stored source/data readiness")
    commands.add_parser("coverage-report", help="Report persisted taxonomy/data coverage without provider requests")
    taxonomy_import = commands.add_parser("import-taxonomy", help="Import one explicit local sector/industry taxonomy CSV")
    taxonomy_import.add_argument("file")
    taxonomy_import.add_argument("--dry-run", action="store_true")
    nse_indices_taxonomy = commands.add_parser("import-nse-indices-taxonomy", help="Import downloaded official NSE Indices constituent taxonomy files")
    nse_indices_taxonomy.add_argument("source_dir", help="Directory containing nifty500.csv, nifty_total_market.csv, industry_classification_page.html, and industry_classification_structure_2023-07.pdf")
    nse_indices_taxonomy.add_argument("--dry-run", action="store_true")
    sector_indices = commands.add_parser("import-nse-sector-indices", help="Import archived official NSE sector-index pages and documented constituent files")
    sector_indices.add_argument("source_dir", help="Directory containing sectoral_indices_page.html plus pages/ and optional constituents/")
    sector_indices.add_argument("--taxonomy-structure", default="data/official_sources/nse_indices/2026-08-27/industry_classification_structure_2023-07.pdf")
    sector_indices.add_argument("--dry-run", action="store_true")
    real_trial = commands.add_parser("real-brain-trial", help="Run one bounded 30–50 stock stored-evidence Brain trial")
    real_trial.add_argument("--sample-size", type=int, default=40)
    real_trial.add_argument("--frozen-cohort", action="store_true", help="Reuse the latest compatible persisted cohort rather than selecting a new one")
    real_trial.add_argument("--frozen-cohort-trial", help="Reuse the exact cohort from this prior real-Brain trial ID")
    upstox_population = commands.add_parser("ingest-upstox-frozen-cohort", help="Explicitly map and ingest only the frozen 40-stock cohort plus NIFTY 500")
    upstox_population.add_argument("--years", type=int, choices=(1, 2, 3), default=3)
    upstox_sector_indices = commands.add_parser("ingest-upstox-sector-indices", help="Explicitly map Task 38 official sector indices and ingest only their daily V3 history")
    upstox_sector_indices.add_argument("--years", type=int, choices=(1, 2, 3), default=3)
    upstox_sector_indices.add_argument("--report-dir", default="reports")
    upstox_sector_probe = commands.add_parser("probe-upstox-sector-indices", help="Make at most three non-persisting Upstox V3 index-history probe requests")
    upstox_sector_probe.add_argument("--years", type=int, choices=(1, 2, 3), default=3)
    upstox_sector_probe.add_argument("--report-dir", default="reports")
    commands.add_parser("upstox-sector-index-status", help="Read provider-versioned NSE index coverage from the local historical store without provider calls")
    commands.add_parser("migrate-sqlite-provider-versioned-bars", help="Explicitly back up and transactionally upgrade the persistent local SQLite historical-bar table; no provider calls")
    constituent_plan = commands.add_parser("plan-upstox-sector-constituent-backfill", help="Stored-only U07 current-constituent coverage assessment and bounded Upstox backfill plan")
    constituent_plan.add_argument("--rs-ready-only", action="store_true", help="Plan only sectors whose existing stored production RS is ready")
    current_sector = commands.add_parser("current-sector-rotation-status", help="Stored-only current sector RS, breadth, ranking, and readiness status")
    current_sector.add_argument("--report-dir", default="reports")
    commands.add_parser("materialize-current-sector-ranking", help="Persist one immutable stored-only current sector-ranking snapshot")
    commands.add_parser(
        "ingest-official-nse-index-close-series",
        help="Acquire the fixed four exact official NSE Indices close-only series; never creates OHLC bars",
    )
    commands.add_parser(
        "ingest-official-nse-index-ohlc-series",
        help="Acquire active Rule 1--3/6 exact official NSE Indices price-return Daily OHLC evidence",
    )
    commands.add_parser(
        "ingest-official-nse-sector-index-alias-ohlc",
        help="Acquire only the retained Consumer Durables and Healthcare first-party source-query aliases",
    )
    current_prebreakout = commands.add_parser("current-prebreakout-status", help="Stored-only current Top-3 official NSE delivery gate and Pre-Breakout readiness")
    current_prebreakout.add_argument("--report-dir", default="reports")
    governed_setup_source = commands.add_parser("run-governed-executable-setup-source", help="Explicit stored-only governed Pre-Breakout assessment and executable-setup persistence; never starts paper trading")
    governed_setup_source.add_argument("--as-of", help="Timezone-aware ISO8601 cutoff; defaults to current UTC time")
    governed_setup_source.add_argument("--time-stop-sessions", type=int, help="Explicit later U18 paper-study horizon; required only if an eligible setup exists")
    constituent_backfill = commands.add_parser("ingest-upstox-sector-constituents", help="Explicit sequential Upstox backfill for only planned current sector constituents")
    constituent_backfill.add_argument("--years", type=int, choices=(2, 3), default=2)
    constituent_backfill.add_argument("--delay-seconds", type=float, default=0.25)
    constituent_backfill.add_argument("--rs-ready-only", action="store_true", help="Fetch only the stored plan for sectors with ready production RS")
    delivery_import = commands.add_parser("import-nse-delivery", help="Import one explicitly downloaded official NSE Full Bhavcopy delivery CSV for current Top-3 only")
    delivery_import.add_argument("file")
    delivery_import.add_argument("--source-url", required=True)
    delivery_import.add_argument("--source-page", default="https://www.nseindia.com/all-reports")
    yahoo_population = commands.add_parser("ingest-yfinance-frozen-cohort", help="Explicitly ingest only frozen 40 secondary-research Yahoo daily histories")
    yahoo_population.add_argument("--years", type=int, choices=(1, 2, 3), default=3)
    yahoo_population.add_argument("--without-nifty500", action="store_true", help="Do not attempt the separately verified NIFTY 500 candidate")
    yahoo_validate = commands.add_parser("validate-yfinance-frozen-stock", help="Fetch one frozen-cohort Yahoo daily history before cohort population")
    yahoo_validate.add_argument("--years", type=int, choices=(1, 2, 3), default=3)
    yahoo_validate.add_argument("--symbol", help="One exact symbol from the existing frozen cohort; default is deterministic")
    yahoo_secondary = commands.add_parser("enrich-yahoo-secondary-frozen-cohort", help="Persist bounded Yahoo secondary-research snapshots for anchors or frozen 40")
    yahoo_secondary.add_argument("--phase", choices=("anchors", "frozen-40"), required=True)
    yahoo_secondary.add_argument("--delay-seconds", type=float, default=0.25)
    approval = commands.add_parser("approve-prebreakout-policy", help="Create one immutable human Pre-Breakout policy approval or rejection")
    approval.add_argument("--approval-id", required=True)
    approval.add_argument("--policy-id", required=True)
    approval.add_argument("--policy-version", required=True)
    approval.add_argument("--decision", choices=("APPROVE", "REJECT"), required=True)
    approval.add_argument("--reviewer-id", required=True)
    approval.add_argument("--reviewed-at", required=True, help="Timezone-aware ISO8601 timestamp")
    selection = commands.add_parser("select-prebreakout-policy", help="Select one APPROVED policy for CURRENT_STORED_SCAN only")
    selection.add_argument("--selection-id", required=True)
    selection.add_argument("--approval-id", required=True)
    selection.add_argument("--selected-by", required=True)
    selection.add_argument("--selected-at", required=True, help="Timezone-aware ISO8601 timestamp")
    selection.add_argument("--effective-from", required=True, help="Timezone-aware ISO8601 timestamp")
    return value


def main(
    argv: Sequence[str] | None = None,
    *,
    scheduler_factory: Callable[[RuntimeSchedulerSettings], RuntimeScheduler] = build_runtime_scheduler,
    import_service_factory: Callable[[], object] = build_nse_import_service,
    bse_financial_import_factory: Callable[[], object] = build_bse_financial_feasibility_import_service,
    bse_real_portfolio_collector_factory: Callable[[], object] = build_real_portfolio_bse_official_financial_collector,
    bse_nifty500_acquisition_factory: Callable[[], object] = build_nifty500_bse_financial_acquisition_orchestrator,
    universe_importer_factory: Callable[[], object] = build_nse_universe_importer,
    nse_tick_master_importer_factory: Callable[[], object] = build_nse_tick_master_importer,
    data_readiness_factory: Callable[[], object] = build_data_readiness_service,
    coverage_report_factory: Callable[[], object] = build_coverage_report_service,
    taxonomy_importer_factory: Callable[[], object] = build_taxonomy_importer,
    nse_indices_taxonomy_importer_factory: Callable[[], object] = build_nse_indices_taxonomy_importer,
    nse_sector_index_importer_factory: Callable[[], object] = build_nse_sector_index_importer,
    real_brain_trial_factory: Callable[[], object] = build_real_brain_trial_service,
    upstox_population_factory: Callable[[], object] = build_upstox_frozen_population_service,
    upstox_sector_index_population_factory: Callable[[], object] = build_upstox_sector_index_population_service,
    upstox_sector_index_status_factory: Callable[[], object] = build_upstox_sector_index_status_service,
    current_sector_rotation_factory: Callable[[], object] = build_current_sector_rotation_service,
    official_index_close_refresh_factory: Callable[[], object] = build_official_nse_index_close_series_refresh,
    official_index_ohlc_refresh_factory: Callable[[], object] = build_official_nse_index_ohlc_series_refresh,
    official_index_ohlc_alias_refresh_factory: Callable[[], object] = build_official_nse_sector_index_alias_ohlc_lineage_refresh,
    current_prebreakout_factory: Callable[[], object] = build_current_prebreakout_service,
    governed_executable_setup_source_factory: Callable[..., object] = build_governed_executable_setup_source_service,
    current_sector_constituent_backfill_factory: Callable[[], object] = build_current_sector_constituent_backfill_service,
    nse_delivery_import_factory: Callable[[], object] = build_nse_delivery_import_service,
    sqlite_provider_versioned_migration_factory: Callable[[], object] = migrate_sqlite_provider_versioned_bars_factory,
    yfinance_population_factory: Callable[[], object] = build_yfinance_frozen_population_service,
    yahoo_secondary_enrichment_factory: Callable[..., object] = build_yahoo_secondary_enrichment_service,
    prebreakout_governance_command_factory: Callable[[], object] = build_prebreakout_policy_governance_command_service,
    data_operations_factory: Callable[[], object] = build_data_operations_service,
    forward_paper_factory: Callable[[], object] = build_forward_paper_service,
    controlled_forward_paper_runtime_factory: Callable[[], object] = build_controlled_forward_paper_runtime,
    production_v1_readiness_factory: Callable[[], object] = build_production_v1_readiness_service,
    production_v1_cycle_factory: Callable[[], object] = build_controlled_production_v1_cycle_service,
    historical_conflict_store_factory: Callable[[], object] = build_historical_conflict_store,
    credential_store_factory: Callable[[], object] = create_credential_store,
    output: Callable[[str], None] = print,
) -> int:
    arguments = parser().parse_args(argv)
    try:
        settings = RuntimeSchedulerSettings.from_environment()
        if arguments.command == "backfill-nse-udiff-daily-history":
            from app.market_data.nse_udiff_daily_history import build_local_nse_udiff_daily_backfill
            service, resources = build_local_nse_udiff_daily_backfill()
            try:
                report = service.run(max_sessions=arguments.max_sessions)
                counts: dict[str, int] = {}
                for item in report.receipts:
                    counts[item.status.value] = counts.get(item.status.value, 0) + 1
                output(" ".join((
                    f"acquisition_id={report.acquisition_id}",
                    f"manifest_id={report.manifest.manifest_id}",
                    f"attempted_sessions={report.attempted_sessions}",
                    f"replayed_sessions={report.replayed_sessions}",
                    f"inserted={report.inserted}", f"duplicates={report.duplicates}",
                    f"source_rows={report.source_rows}",
                    f"source_blocked={'yes' if report.source_blocked else 'no'}",
                    f"receipt_statuses={','.join(f'{key}:{value}' for key, value in sorted(counts.items())) or 'NONE'}",
                )))
                return 0 if not report.source_blocked else 2
            finally:
                for resource in resources:
                    close = getattr(resource, "close", None)
                    if callable(close):
                        close()
        if arguments.command == "audit-nse-udiff-daily-integrity":
            from app.market_data.nse_udiff_daily_integrity import run_local_udiff_daily_integrity_audit
            report = run_local_udiff_daily_integrity_audit(as_of=_udiff_integrity_timestamp(arguments.as_of))
            output(" ".join((
                f"manifest_id={report.manifest.manifest_id}",
                f"manifest_inserted={'yes' if report.manifest_inserted else 'no'}",
                f"artifact_valid_sessions={report.valid_artifact_sessions}",
                f"confirmed_non_trading_days={report.confirmed_non_trading_days}",
                f"expected_session_source_missing={report.expected_session_source_missing}",
                f"historical_session_unresolved={report.unresolved_sessions}",
                f"unresolved_udiff_conflicts={report.unresolved_conflicts}",
            )))
            return 0
        if arguments.command == "compounder-prospective-shadow":
            from app.research.compounder_prospective_runtime import run_local_compounder_prospective_shadow
            cutoff = _prebreakout_timestamp(arguments.as_of)
            report = run_local_compounder_prospective_shadow(as_of=cutoff)
            output(" ".join((
                f"as_of={report.as_of.isoformat()}",
                f"non_financial_issuers={report.non_financial_issuers_considered}",
                f"prospective_ready={report.prospective_ready}",
                f"observations_inserted={report.observations_inserted}",
                f"observations_already_present={report.observations_already_present}",
                f"consolidated_ready={report.consolidated_ready}",
                f"standalone_ready={report.standalone_ready}",
                f"rejections={','.join(f'{key}:{count}' for key, count in report.rejected_by_state) or 'NONE'}",
                f"report_id={report.report_id}",
            )))
            return 0
        if arguments.command == "inflection-accounting-prospective-shadow":
            from app.research.inflection_accounting_prospective_runtime import run_local_inflection_accounting_prospective_shadow
            cutoff = _prebreakout_timestamp(arguments.as_of)
            report = run_local_inflection_accounting_prospective_shadow(as_of=cutoff)
            output(" ".join((
                f"as_of={report.as_of.isoformat()}",
                f"non_financial_issuers={report.non_financial_issuers_considered}",
                f"issuers_with_quarterly_facts={report.issuers_with_quarterly_facts}",
                f"revenue_acceleration_ready={report.revenue_acceleration_ready}",
                f"pat_acceleration_ready={report.pat_acceleration_ready}",
                f"both_acceleration_ready={report.both_acceleration_ready}",
                f"observations_inserted={report.observations_inserted}",
                f"observations_already_present={report.observations_already_present}",
                f"rejections={','.join(f'{key}:{count}' for key, count in report.rejected_by_state) or 'NONE'}",
                f"report_id={report.report_id}",
            )))
            return 0
        if arguments.command == "materialize-market-wide-watch":
            from app.intelligence.market_wide_watch import build_local_market_wide_watch_service
            as_of = _prebreakout_timestamp(arguments.as_of) if arguments.as_of else datetime.now(UTC)
            service, resources = build_local_market_wide_watch_service()
            try:
                first = service.run(as_of=as_of)
                second = service.run(as_of=as_of)
                output(" ".join((
                    f"run_id={first.run_id}", f"universe={first.universe_count}",
                    f"eligible={first.eligible_count}", f"evidence_ready={first.evidence_ready_count}",
                    f"watch_candidates={first.watch_candidate_count}",
                    f"first_fingerprint={first.fingerprint}", f"second_fingerprint={second.fingerprint}",
                    f"idempotent={'yes' if first == second else 'no'}",
                )))
                return 0 if first == second else 2
            finally:
                for resource in resources:
                    if hasattr(resource, "close"):
                        resource.close()
        if arguments.command in {"dhan-auth-status", "dhan-auth-configure", "dhan-auth-diagnose", "dhan-auth-start", "dhan-materialize-mappings", "dhan-ltp-canary", "dhan-live-feed-status", "dhan-live-feed-canary", "dhan-live-feed", "dhan-live-feed-diagnose"}:
            from app.market_data.dhan import DhanAuthClient, DhanCredentialService, DhanLoopbackTokenReceiver, DhanMarketDataClient, load_dhan_instrument_master
            if arguments.command in {"dhan-materialize-mappings", "dhan-ltp-canary", "dhan-live-feed-canary", "dhan-live-feed", "dhan-live-feed-diagnose"}:
                from app.market_data.dhan_mapping import DhanCurrentTargetSet, DhanProviderMappingService, current_dhan_targets
                from app.api.repository_query_services import RepositoryPortfolioQueryService
                from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRunStore
                from app.storage.database import DatabaseSettings
                from app.storage.repository_factory import create_core_api_snapshot_repository
                from app.universe_analysis.service import CoreUniverseAnalysisStore
                repository = create_core_api_snapshot_repository(DatabaseSettings.local_runtime())
                universe = CoreUniverseAnalysisStore(repository)
                target_set = current_dhan_targets(
                    portfolio=RepositoryPortfolioQueryService(repository), top3_runs=Top3OpportunityFinderRunStore(repository),
                )
                mapping_service = DhanProviderMappingService(universe)
            if arguments.command == "dhan-materialize-mappings":
                master = load_dhan_instrument_master()
                first = mapping_service.materialize(targets=target_set, master=master, as_of=master.retrieved_at)
                second = mapping_service.materialize(targets=target_set, master=master, as_of=master.retrieved_at)
                output(" ".join((
                    f"portfolio_targets={len(target_set.portfolio_ids)}", f"top3_targets={len(target_set.top3_ids)}",
                    f"union_targets={target_set.count}", f"master_sha256={master.fingerprint}",
                    f"first_created={first.created_count}", f"first_blocked={first.blocked_count}",
                    f"second_created={second.created_count}", f"second_identical={second.identical_count}", f"second_blocked={second.blocked_count}",
                )))
                for item in first.outcomes:
                    mapping = item.mapping
                    output(" ".join((
                        f"canonical_instrument_id={item.canonical_instrument_id}", f"symbol={item.symbol}", f"status={item.status.value}",
                        f"mapping_id={mapping.mapping_id if mapping else 'NONE'}", f"fingerprint={mapping.mapping_id.rsplit(':', 1)[-1] if mapping else 'NONE'}",
                    )))
                return 0 if first.blocked_count == 0 and second.created_count == second.blocked_count == 0 else 2
            if arguments.command == "dhan-live-feed-status":
                output("health=DISCONNECTED requested_targets=0 subscribed_targets=0 mapped_packets=0 rejected_packets=0")
                return 0
            credentials = DhanCredentialService(credential_store_factory())
            if arguments.command == "dhan-auth-status":
                status = credentials.status()
                output(" ".join((
                    f"configured={'yes' if status.configured else 'no'}",
                    f"api_key_present={'yes' if status.api_key_present else 'no'}",
                    f"api_secret_present={'yes' if status.api_secret_present else 'no'}",
                    f"access_token_present={'yes' if status.access_token_present else 'no'}",
                    f"token_state={status.token_state.value}",
                    f"expiry_time={status.expiry_time.isoformat() if status.expiry_time else 'NONE'}",
                    f"client_id_present={'yes' if status.client_id_present else 'no'}",
                )))
                return 0
            if arguments.command == "dhan-auth-configure":
                import getpass
                credentials.configure_base_credentials(
                    dhan_client_id=getpass.getpass("Dhan Client ID (input hidden): "),
                    api_key=getpass.getpass("Dhan API Key (input hidden): "),
                    api_secret=getpass.getpass("Dhan API Secret (input hidden): "),
                )
                output("DHAN_CREDENTIALS_STORED")
                return 0
            if arguments.command == "dhan-auth-diagnose":
                DhanAuthClient(credentials).generate_consent()
                output("DHAN_GENERATE_CONSENT_OK")
                return 0
            if arguments.command == "dhan-ltp-canary":
                profile = DhanAuthClient(credentials).profile_canary()
                plan = profile.get("dataPlan") if isinstance(profile.get("dataPlan"), str) else "UNKNOWN"
                validity = profile.get("dataValidity") if isinstance(profile.get("dataValidity"), str) else "UNKNOWN"
                if plan.upper() != "ACTIVE":
                    output(f"data_plan={plan} data_validity={validity} DHAN_DATA_PLAN_INACTIVE")
                    return 2
                selected = target_set if arguments.scope == "all-current-targets" else DhanCurrentTargetSet(
                    target_set.portfolio_ids, (), (), target_set.portfolio_ids,
                )
                targets = mapping_service.ltp_targets(targets=selected, as_of=datetime.now(UTC))
                observations = DhanMarketDataClient(credentials).ltp_batch(targets)
                output(f"data_plan={plan} data_validity={validity} scope={arguments.scope} targets_requested={selected.count} targets_resolved={len(targets)} targets_returned={len(observations)}")
                by_id = {item.canonical_instrument_id: item for item in observations}
                identities = {item.instrument_id: item for item in universe.instruments_as_of(datetime.now(UTC))}
                for identifier in selected.canonical_instrument_ids:
                    identity = identities.get(identifier)
                    if identity is None:
                        raise ValueError("DHAN_CURRENT_TARGET_IDENTITY_MISSING")
                    observation = by_id[identity.instrument_id]
                    output(f"symbol={identity.symbol} dhan_security_id={observation.provider_instrument_id} ltp={observation.ltp} received_at={observation.received_at.isoformat()}")
                return 0 if selected.count == len(targets) == len(observations) else 2
            if arguments.command == "dhan-live-feed-canary":
                if arguments.seconds <= 0 or arguments.seconds > 300:
                    raise ValueError("DHAN_LIVE_FEED_SECONDS_INVALID")
                from app.market_data.dhan_live import DhanLiveFeedService, open_dhan_live_transport
                targets = mapping_service.ltp_targets(targets=target_set, as_of=datetime.now(UTC))
                service = DhanLiveFeedService(credentials)
                status = service.canary(
                    targets=targets,
                    transport_factory=lambda url: open_dhan_live_transport(url, timeout_seconds=arguments.seconds),
                )
                output(" ".join((
                    f"health={status.health.value}", f"requested_targets={status.requested_targets}",
                    f"subscribed_targets={status.subscribed_targets}", f"mapped_packets={status.mapped_packets}",
                    f"rejected_packets={status.rejected_packets}",
                    f"oldest_received_at={status.oldest_received_at.isoformat() if status.oldest_received_at else 'NONE'}",
                    f"newest_received_at={status.newest_received_at.isoformat() if status.newest_received_at else 'NONE'}",
                )))
                return 0 if status.mapped_packets else 2
            if arguments.command == "dhan-live-feed":
                from app.market_data.dhan_live import DhanLiveFeedService, open_dhan_live_transport
                targets = mapping_service.ltp_targets(targets=target_set, as_of=datetime.now(UTC))
                service = DhanLiveFeedService(credentials)
                try:
                    service.run_forever(targets=targets, transport_factory=lambda url: open_dhan_live_transport(url, timeout_seconds=30), stop_requested=lambda: False)
                except KeyboardInterrupt:
                    output("health=DISCONNECTED shutdown=REQUESTED")
                    return 0
            if arguments.command == "dhan-live-feed-diagnose":
                from app.market_data.dhan_live import DhanLiveFeedService, open_dhan_live_transport
                targets = mapping_service.ltp_targets(targets=target_set, as_of=datetime.now(UTC))
                result = DhanLiveFeedService(credentials).diagnose(targets=targets, transport_factory=lambda url: open_dhan_live_transport(url, timeout_seconds=5))
                fields=["DHAN_LIVE_FEED_DIAGNOSTIC",f"stage={result.stage}",f"classification={result.classification}"]
                if result.exception_class: fields.append(f"exception_class={result.exception_class}")
                if result.http_status is not None: fields.append(f"http_status={result.http_status}")
                if result.provider_disconnect_code is not None: fields.append(f"provider_disconnect_code={result.provider_disconnect_code}")
                output(" ".join(fields))
                return 0 if result.ok else 2
            receiver = None
            if arguments.loopback_port is not None:
                if arguments.loopback_port < 1 or arguments.loopback_port > 65535 or arguments.wait_seconds <= 0:
                    raise ValueError("DHAN_LOOPBACK_ARGUMENT_INVALID")
                receiver = DhanLoopbackTokenReceiver(port=arguments.loopback_port)
                output(f"loopback_redirect_url={receiver.redirect_url}")
            auth = DhanAuthClient(credentials)
            consent = auth.generate_consent()
            output(f"official_browser_url={consent.browser_url}")
            if arguments.open_browser:
                import webbrowser
                webbrowser.open(consent.browser_url, new=1)
            token_id = None
            if receiver is not None:
                token_id = receiver.receive(timeout_seconds=arguments.wait_seconds)
                if token_id is None:
                    output("DHAN_AUTH_CALLBACK_TIMEOUT")
                    return 2
            elif arguments.manual_token_id:
                import getpass
                token_id = getpass.getpass("Paste Dhan tokenId from the official redirect (input hidden): ")
            else:
                output("DHAN_AUTH_AWAITING_TOKEN_ID")
                return 2
            grant = auth.consume_consent(token_id)
            auth.profile_canary()
            output(" ".join((
                "auth=VALIDATED", "profile_canary=VALIDATED",
                f"token_state={credentials.status().token_state.value}", f"expiry_time={grant.expiry_time.isoformat()}",
            )))
            return 0
        if arguments.command == "acquire-real-portfolio-nse-shareholding":
            from app.data_operations.nse_shareholding_acquisition import NseOfficialShareholdingAcquirer
            from app.data_operations.nse_reg31_identity import NseReg31IdentityReconciliationStore
            from app.storage.database import DatabaseSettings
            from app.storage.repository_factory import create_core_api_snapshot_repository
            source_directory = Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_shareholding"
            reconciliations = NseReg31IdentityReconciliationStore(
                create_core_api_snapshot_repository(DatabaseSettings.local_runtime())
            )
            staged = NseOfficialShareholdingAcquirer(
                source_directory, identity_reconciliation_store=reconciliations,
            ).acquire_current_xbrl()
            for item in staged:
                output(" ".join((
                    f"symbol={item.target.symbol}", f"isin={item.target.isin}",
                    f"status={item.status}", f"file={item.path.name}", f"sha256={item.sha256}",
                )))
            return 0
        if arguments.command == "correct-real-portfolio-nse-reg31-pit-timestamps":
            from app.data_operations.nse_reg31_pit_correction import (
                NseReg31PitTimestampCorrectionService, NseReg31PitTimestampCorrectionStore,
            )
            from app.filings.store import SQLiteCorporateFilingsStore
            from app.storage.database import DatabaseBackend, DatabaseSettings
            from app.storage.repository_factory import create_core_api_snapshot_repository
            database = DatabaseSettings.local_runtime()
            if database.backend is not DatabaseBackend.SQLITE or database.url.endswith(":memory:"):
                raise RuntimeCompositionError("NSE_REG31_PIT_CORRECTION_REQUIRES_PERSISTENT_SQLITE")
            path = database.url.removeprefix("sqlite:///")
            repository = create_core_api_snapshot_repository(database)
            try:
                service = NseReg31PitTimestampCorrectionService(
                    filings=SQLiteCorporateFilingsStore(path),
                    corrections=NseReg31PitTimestampCorrectionStore(repository),
                    source_directory=Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_shareholding",
                )
                for item in service.apply():
                    output(f"instrument={item.canonical_instrument_id} correction_id={item.correction_id} corrected_filing_id={item.corrected_filing_id} status={item.status}")
                return 0
            finally:
                if hasattr(repository, "close"):
                    repository.close()
        if arguments.command == "materialize-real-portfolio-nse-reg31-ownership":
            from app.ownership.nse_reg31_projection import NseReg31OwnershipProjectionService
            from app.ownership.store import OwnershipObservationStore
            from app.filings.store import SQLiteCorporateFilingsStore
            from app.storage.database import DatabaseBackend, DatabaseSettings
            from app.storage.repository_factory import create_core_api_snapshot_repository
            database = DatabaseSettings.local_runtime()
            if database.backend is not DatabaseBackend.SQLITE or database.url.endswith(":memory:"):
                raise RuntimeCompositionError("NSE_REG31_OWNERSHIP_REQUIRES_PERSISTENT_SQLITE")
            path = database.url.removeprefix("sqlite:///")
            repository = create_core_api_snapshot_repository(database)
            try:
                service = NseReg31OwnershipProjectionService(
                    filings=SQLiteCorporateFilingsStore(path), observations=OwnershipObservationStore(repository),
                    source_directory=Path(__file__).resolve().parents[2] / "data" / "official_sources" / "nse_shareholding",
                )
                for item in service.materialize():
                    output(" ".join((
                        f"instrument={item.canonical_instrument_id}", f"filing_id={item.filing_id}",
                        f"period={item.reporting_period.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()}", f"published_at={item.published_at.isoformat()}",
                        f"raw_inserted={item.raw_fact_inserted}", f"raw_identical={item.raw_fact_identical}",
                        f"observations_inserted={item.observation_inserted}",
                        f"observations_identical={item.observation_identical}",
                        f"normalized_percentage={item.normalized_percentage_count}",
                        f"unsupported={len(item.unsupported_concepts)}", f"conflicts={item.conflict_count}",
                    )))
                return 0
            finally:
                if hasattr(repository, "close"):
                    repository.close()
        if arguments.command == "materialize-real-portfolio-reliability-integrity":
            from app.portfolio.canonical_diagnostics_orchestration import PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
            from app.reliability.integrity import build_reliability_integrity_observation
            resolver, assembler, observations, repository, historical = build_real_portfolio_reliability_integrity_context()
            try:
                cutoff = datetime.now(UTC)
                for pass_number in (1, 2):
                    for instrument_id in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS:
                        instrument = resolver.resolve(instrument_id, as_of=cutoff)
                        value = build_reliability_integrity_observation(
                            assembler.assemble(instrument, as_of=cutoff).unified_state,
                        )
                        inserted = repository.get_snapshot(value.artifact_id) is None
                        observations.save(value)
                        output(" ".join((
                            f"pass={pass_number}", f"instrument={instrument_id}",
                            f"status={'INSERTED' if inserted else 'IDENTICAL'}",
                            f"evidence_state={value.evidence_state.value}",
                            f"freshness={value.freshness_state.value}",
                            f"conflict={value.conflict_detected}",
                            f"fallback={value.fallback_state.value}",
                            f"dimensions={len(value.dimensions)}", f"blockers={len(value.blockers)}",
                            f"artifact_id={value.artifact_id}",
                        )))
                return 0
            finally:
                for value in (historical, repository):
                    if hasattr(value, "close"):
                        value.close()
        if arguments.command == "bridge-external-intelligence-inbox":
            from app.intelligence.supabase_inbox_bridge import (
                SupabaseBridgeConfigurationError,
                build_supabase_external_intelligence_bridge,
            )
            bridge = build_supabase_external_intelligence_bridge()
            if arguments.once:
                receipt = bridge.run_once()
            else:
                cycles = bridge.run_forever()
                if cycles == 0:
                    raise SupabaseBridgeConfigurationError("SUPABASE_EXTERNAL_INTELLIGENCE_BRIDGE_DISABLED")
                return 0
            output(" ".join(
                f"{field}={getattr(receipt, field)}" for field in receipt.__dataclass_fields__
            ))
            return 0 if receipt.supabase_failure == 0 else 2
        if arguments.command == "refresh-real-portfolio-intelligence":
            from app.portfolio.canonical_diagnostics_orchestration import PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
            from app.domain.canonical_diagnostic_strategy import CANONICAL_61_STRATEGY_REFERENCE
            service, snapshot, repository, historical, governance = build_real_portfolio_intelligence_refresh_service()
            try:
                now = datetime.now(UTC)
                run = service.run(portfolio_snapshot=snapshot, canonical_instrument_ids=PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS, strategy_version=CANONICAL_61_STRATEGY_REFERENCE, intelligence_as_of=now)
                output(f"portfolio_snapshot_id={run.portfolio_snapshot_id} portfolio_snapshot_as_of={run.portfolio_snapshot_as_of.isoformat()} intelligence_as_of={run.intelligence_as_of.isoformat()} latest_completed_market_session={run.latest_completed_market_session.isoformat() if run.latest_completed_market_session else 'NONE'}")
                for item in run.holdings:
                    output(f"holding={item.instrument_id} evaluated={len(item.evaluated_rule_ids)} missing={len(item.blocked_rule_ids)} brain={item.shared_brain_status or 'BLOCKED'} sell_side={item.sell_side_decision.action.value if item.sell_side_decision else 'NONE'} blockers={'|'.join(item.blockers) or 'NONE'}")
                output(f"stage={'SUCCESS' if not run.blockers else 'BLOCKED'} blockers={'|'.join(run.blockers) or 'NONE'}")
                return 0 if not run.blockers else 2
            finally:
                for value in (governance, historical, repository):
                    if hasattr(value, 'close'): value.close()
        if arguments.command == "production-v1-status":
            report = production_v1_readiness_factory().report()
            output(f"final_status={report.final_status.value} p0_count={len(report.p0_blockers)}")
            for item in report.components:
                output(f"component={item.component.value} state={item.state.value} reason={item.reason or 'NONE'}")
            for item in report.sources:
                output(f"source_family={item.family.value} source={item.source or 'NONE'} adapter={item.adapter or 'NONE'} status={item.status.value} coverage={item.coverage or 'UNKNOWN'} blocker={item.blocker or 'NONE'}")
            for item in report.p0_blockers: output(f"p0={item}")
            return 0
        if arguments.command == "historical-bar-conflicts":
            store = historical_conflict_store_factory()
            try:
                values = store.list_conflict_artifacts(instrument_id=arguments.instrument)
                output(f"conflicts={len(values)} instrument={arguments.instrument or 'ALL'}")
                for item in values:
                    output(_historical_conflict_line(item))
                return 0
            finally:
                if hasattr(store, "close"):
                    store.close()
        if arguments.command == "ohlcv-readiness":
            readiness, universe, watermark, provider, resources = build_ohlcv_readiness_context()
            try:
                now = datetime.now(UTC)
                required_latest = watermark.accepted_through if watermark else None
                mapped_ids = {
                    item.canonical_instrument_id
                    for item in universe.provider_mappings(provider=provider, as_of=now)
                }
                if arguments.instrument:
                    values = (readiness.assess(
                        arguments.instrument,
                        as_of=now,
                        mapping_available=arguments.instrument in mapped_ids,
                        required_latest_at=required_latest,
                    ),)
                    coverage = None
                else:
                    snapshot = universe.latest_universe_snapshot()
                    target_ids = snapshot.instrument_ids if snapshot is not None else ()
                    coverage, values = readiness.coverage(
                        target_ids,
                        as_of=now,
                        mapping_available=mapped_ids.__contains__,
                        required_latest_at=required_latest,
                    )
                output(f"instruments={len(values)} required_sessions={values[0].required_sessions if values else 252}")
                if coverage is not None:
                    output(
                        f"coverage total={coverage.total} mapped={coverage.mapped} sufficient={coverage.sufficient} "
                        f"current={coverage.current} stale={coverage.stale} conflicted={coverage.conflicted} "
                        f"healthy_ready={coverage.healthy_ready} insufficient={coverage.insufficient} "
                        f"unavailable={coverage.unavailable} unmapped={coverage.unmapped}"
                    )
                for item in values:
                    output(
                        f"instrument={item.canonical_instrument_id} status={item.status.value} mapping={str(item.mapping_available).lower()} "
                        f"sessions={item.session_count} latest_bar={item.latest_bar_at.isoformat() if item.latest_bar_at else 'NONE'} "
                        f"required_latest={item.required_latest_at.isoformat() if item.required_latest_at else 'NONE'} "
                        f"conflicts={len(item.conflict_fingerprints)} reason={item.reason}"
                    )
                return 0
            finally:
                for resource in resources:
                    if hasattr(resource, "close"):
                        resource.close()
        if arguments.command in {"paper-trading-status", "paper-trading-run", "paper-trading-worker"}:
            from app.forward_paper.models import ForwardPaperHealth, PaperStudyState
            from app.forward_paper.service import PaperTradingSettings
            paper_settings = PaperTradingSettings.from_environment() if hasattr(PaperTradingSettings, "from_environment") else PaperTradingSettings()
            paper = forward_paper_factory()
            views = tuple(paper.snapshot(item.study_id) for item in paper._store.studies())
            if arguments.command == "paper-trading-status":
                latest = paper._store.latest_run()
                health = ForwardPaperHealth.DISABLED if not paper_settings.enabled else (
                    latest.health if latest is not None else ForwardPaperHealth.BLOCKED_DATA
                )
                output(" ".join((f"health={health.value}", f"waiting={sum(item.state is PaperStudyState.WAITING_FOR_TRIGGER for item in views)}",
                    f"open={sum(item.state is PaperStudyState.OPEN for item in views)}", f"closed={sum(item.state is PaperStudyState.CLOSED for item in views)}",
                    f"ambiguous={sum(item.state is PaperStudyState.AMBIGUOUS for item in views)}",
                    f"last_successful_run={latest.run_id if latest and latest.health is ForwardPaperHealth.HEALTHY else 'NONE'}")))
                return 0
            if not paper_settings.enabled:
                raise RuntimeCompositionError("PAPER_TRADING_DISABLED")
            orchestrator, store, resources = controlled_forward_paper_runtime_factory()
            try:
                if arguments.command == "paper-trading-worker":
                    from app.forward_paper.service import ForwardPaperWorker
                    worker = ForwardPaperWorker(orchestrator, paper_settings, record_run=store.save_run)
                    return 0 if worker.run_forever() else 2
                result = orchestrator.run_once()
                store.save_run(result)
            finally:
                for resource in reversed(resources):
                    if hasattr(resource, "close"):
                        resource.close()
            output(" ".join((
                f"run_id={result.run_id}", f"health={result.health.value}", f"admitted={result.admitted}",
                f"sessions_processed={result.sessions_processed}", f"entries={result.entries}",
                f"exits={result.exits}", f"marks={result.marks}", f"misses={result.misses}",
                f"ambiguous={result.ambiguous}", f"failures={result.failures}", f"reason={result.reason or 'NONE'}",
            )))
            return 0 if result.health in {ForwardPaperHealth.HEALTHY, ForwardPaperHealth.DEGRADED} else 2
        if arguments.command == "production-v1-cycle":
            from app.forward_paper.service import PaperTradingSettings
            if not PaperTradingSettings.from_environment().enabled:
                raise RuntimeCompositionError("PAPER_TRADING_DISABLED")
            service, resources = production_v1_cycle_factory()
            try:
                receipt, report = service.run(refresh_due=arguments.refresh_due)
            finally:
                for resource in reversed(resources):
                    if hasattr(resource, "close"):
                        resource.close()
            output(" ".join((
                f"cycle_run_id={receipt.run_id}", f"cycle_status={receipt.status.value}",
                f"as_of={receipt.as_of.isoformat()}", f"readiness_fingerprint={receipt.readiness_fingerprint}",
                f"setup_source_run_id={receipt.setup_source_run_id or 'NONE'}",
                f"forward_paper_run_id={receipt.forward_paper_run_id or 'NONE'}",
                f"blockers={','.join(receipt.blockers) or 'NONE'}",
            )))
            for phase in receipt.phases:
                output(" ".join((
                    f"phase={phase.phase}", f"status={phase.status.value}",
                    f"reason={phase.reason or 'NONE'}", f"lineage={','.join(phase.lineage_ids) or 'NONE'}",
                )))
            output(f"final_status={report.final_status.value} p0_count={len(report.p0_blockers)}")
            for item in report.p0_blockers:
                output(f"p0={item}")
            return 0 if receipt.status.value == "SUCCESS" and not report.p0_blockers else 2
        if arguments.command in {"data-operations-status", "data-operations-run", "reconcile-upstox-historical-conflicts", "data-operations-schedule-once", "data-operations-worker"}:
            service, resources = data_operations_factory()
            try:
                if arguments.command == "data-operations-status":
                    health = service.health()
                    for item in health.families:
                        output(
                            f"family={item.family.value} health={item.status.value} "
                            f"last_run={item.last_run.run_id if item.last_run else 'NONE'} "
                            f"last_status={item.last_run.status.value if item.last_run else 'NEVER_RUN'} "
                            f"next_due_at={item.next_due_at.isoformat() if item.next_due_at else 'NONE'} "
                            f"reasons={','.join(item.reasons) or 'NONE'}"
                        )
                    return 0
                if arguments.command == "data-operations-run":
                    family = EvidenceDataFamily(arguments.family.upper())
                    mode = EvidenceRefreshMode(arguments.mode.upper())
                    result = service.run(family, mode=mode)
                    output(_data_operations_run_line(result))
                    return 0 if result.status not in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, EvidenceRefreshStatus.INVALID_EVIDENCE} else 2
                if arguments.command == "reconcile-upstox-historical-conflicts":
                    subjects = frozenset(item.subject for item in service.latest_conflict_findings(EvidenceDataFamily.OHLCV))
                    if not subjects:
                        output("targeted_conflict_instruments=0")
                        return 0
                    job = service._jobs.get(EvidenceDataFamily.OHLCV)
                    if job is None:
                        raise RuntimeCompositionError("OHLCV_CONFLICT_RECONCILIATION_JOB_UNAVAILABLE")
                    scoped = DataOperationsService(
                        service._store,
                        {EvidenceDataFamily.OHLCV: _ConflictSubsetOhlcvJob(job, subjects)},
                        service.cadences,
                    )
                    result = scoped.run(EvidenceDataFamily.OHLCV, mode=EvidenceRefreshMode.RECONCILIATION)
                    output(f"targeted_conflict_instruments={len(subjects)}")
                    for subject in sorted(subjects):
                        output(f"target_instrument={subject}")
                    output(_data_operations_run_line(result))
                    return 0 if result.status not in {EvidenceRefreshStatus.FAILED, EvidenceRefreshStatus.SOURCE_UNAVAILABLE, EvidenceRefreshStatus.INVALID_EVIDENCE} else 2
                scheduler = DataOperationsScheduler(service)
                if arguments.command == "data-operations-schedule-once":
                    results = scheduler.run_due()
                    output(f"dispatched={len(results)}")
                    for result in results:
                        output(_data_operations_run_line(result))
                    return 0
                operations_settings = DataOperationsSettings.from_environment()
                worker = DataOperationsWorker(scheduler, operations_settings)
                return 0 if worker.run_forever() else 2
            finally:
                for resource in resources:
                    if hasattr(resource, "close"):
                        resource.close()
        if arguments.command == "approve-prebreakout-policy":
            from app.strategies.pre_breakout.policy import PreBreakoutPolicyApprovalDecision
            service, repository = prebreakout_governance_command_factory()
            try:
                receipt = service.approve(
                    approval_id=arguments.approval_id,
                    policy_id=arguments.policy_id,
                    policy_version=arguments.policy_version,
                    decision=PreBreakoutPolicyApprovalDecision(arguments.decision),
                    reviewer_id=arguments.reviewer_id,
                    reviewed_at=_prebreakout_timestamp(arguments.reviewed_at),
                )
            finally:
                if hasattr(repository, "close"):
                    repository.close()
            output(" ".join((
                f"approval_id={receipt.approval_id}", f"policy_id={receipt.policy_id}",
                f"policy_version={receipt.policy_version}", f"decision={receipt.decision.value}",
                f"reviewer_id={receipt.reviewer_id}", f"reviewed_at={receipt.reviewed_at.isoformat()}",
                f"draft_policy_fingerprint={receipt.draft_policy_fingerprint}",
                f"approved_policy_fingerprint={receipt.approved_policy_fingerprint}",
                f"approval_fingerprint={receipt.approval_fingerprint}",
            )))
            return 0
        if arguments.command == "select-prebreakout-policy":
            service, repository = prebreakout_governance_command_factory()
            try:
                receipt = service.select_for_current_stored_scan(
                    selection_id=arguments.selection_id,
                    approval_id=arguments.approval_id,
                    selected_by=arguments.selected_by,
                    selected_at=_prebreakout_timestamp(arguments.selected_at),
                    effective_from=_prebreakout_timestamp(arguments.effective_from),
                )
            finally:
                if hasattr(repository, "close"):
                    repository.close()
            output(" ".join((
                f"selection_id={receipt.selection_id}", f"approval_id={receipt.approval_id}",
                f"policy_id={receipt.policy_id}", f"policy_version={receipt.policy_version}",
                f"policy_fingerprint={receipt.policy_fingerprint}",
                f"selection_context={receipt.selection_context.value}", f"selected_by={receipt.selected_by}",
                f"selected_at={receipt.selected_at.isoformat()}", f"effective_from={receipt.effective_from.isoformat()}",
                f"selection_fingerprint={receipt.selection_fingerprint}",
                "selected_for_current_stored_scan=true",
            )))
            return 0
        if arguments.command == "import-nse":
            from app.nse_import.service import ExportFamily
            family = ExportFamily(arguments.type.replace("-", "_").upper()) if arguments.type else None
            report = import_service_factory().import_file(arguments.file, family=family, dry_run=arguments.dry_run)
            output(f"import_id={report.import_id} status={report.status.value} accepted={report.accepted} duplicates={report.duplicates} rejected={report.rejected} unresolved={report.unresolved_symbols}")
            return 0 if report.status.value in {"COMPLETED", "IDENTICAL"} else 2
        if arguments.command == "migrate-sqlite-provider-versioned-bars":
            report = sqlite_provider_versioned_migration_factory()()
            output(" ".join((
                f"database_path={report.database_path}", f"backup_path={report.backup_path or 'NONE'}",
                f"rows_before={report.rows_before}", f"rows_after={report.rows_after}",
                f"legacy_rows_tagged_unknown_existing_source={report.legacy_rows_tagged_unknown_existing_source}",
                f"migration_status={report.migration_status.value}",
            )))
            output(f"schema_before_pk={','.join(report.schema_before.primary_key)}")
            output(f"schema_after_pk={','.join(report.schema_after.primary_key)}")
            if report.error:
                output(f"error={report.error}")
            return 0 if report.migration_status.value in {"MIGRATED", "ALREADY_CURRENT"} else 2
        if arguments.command == "ingest-official-nse-index-close-series":
            service, repository = official_index_close_refresh_factory()
            try:
                result = service.run_twice()
            finally:
                if hasattr(repository, "close"):
                    repository.close()
            output(f"requested_at={result.requested_at.isoformat()} completed_at={result.completed_at.isoformat()}")
            for label, values in (("first", result.first_run), ("second", result.second_run)):
                for item in values:
                    output(" ".join((
                        f"run={label}", f"canonical_index_id={item.canonical_index_id}",
                        f"official_index_name={item.official_index_name}",
                        f"before={item.sessions_before}", f"after={item.sessions_after}",
                        f"inserted={item.inserted_count}", f"duplicates={item.duplicate_count}",
                        f"conflicts={item.conflict_count}",
                        f"latest={item.latest_session.isoformat() if item.latest_session else 'NONE'}",
                        f"artifact_sha256={item.raw_artifact_sha256}", f"blocker={item.blocker or 'NONE'}",
                    )))
            return 0 if not any(item.conflict_count for item in (*result.first_run, *result.second_run)) else 2
        if arguments.command in {"ingest-official-nse-index-ohlc-series", "ingest-official-nse-sector-index-alias-ohlc"}:
            factory = (
                official_index_ohlc_alias_refresh_factory
                if arguments.command == "ingest-official-nse-sector-index-alias-ohlc"
                else official_index_ohlc_refresh_factory
            )
            service, repository = factory()
            try:
                result = service.run_twice()
            finally:
                if hasattr(repository, "close"):
                    repository.close()
            output(f"requested_at={result.requested_at.isoformat()} completed_at={result.completed_at.isoformat()}")
            for label, values in (("first", result.first_run), ("second", result.second_run)):
                for item in values:
                    output(" ".join((
                        f"run={label}", f"canonical_index_id={item.canonical_index_id}",
                        f"official_index_name={item.official_index_name}",
                        f"before={item.sessions_before}", f"after={item.sessions_after}",
                        f"inserted={item.inserted_count}", f"duplicates={item.duplicate_count}",
                        f"conflicts={item.conflict_count}",
                        f"latest={item.latest_session.isoformat() if item.latest_session else 'NONE'}",
                        f"artifact_sha256={item.raw_artifact_sha256}", f"blocker={item.blocker or 'NONE'}",
                    )))
            return 0 if not any(item.conflict_count for item in (*result.first_run, *result.second_run)) else 2
        if arguments.command == "materialize-current-sector-ranking":
            service, historical = current_sector_rotation_factory()
            try:
                ranking = service.materialize()
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            output(f"ranking_id={ranking.ranking_id} ranking_as_of={ranking.ranking_as_of.isoformat()} benchmark={ranking.benchmark_identity} policy={ranking.ranking_policy_version}")
            return 0
        if arguments.command in {"plan-upstox-sector-constituent-backfill", "current-sector-rotation-status"}:
            service, historical = current_sector_rotation_factory()
            try:
                rs_ready_only = bool(getattr(arguments, "rs_ready_only", False))
                report = service.assess(rs_ready_only=True) if rs_ready_only else service.assess()
                if arguments.command == "current-sector-rotation-status":
                    service.write_reports(report, Path(arguments.report_dir))
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            output(f"benchmark_sessions={report.benchmark_sessions} eligible_sector_histories={sum(item.exclusion_reason is None for item in report.relative_strength)} breadth_ready={sum(item.status == 'READY' for item in report.breadth)} top3_ready={len(report.top3)}")
            for item in report.relative_strength:
                breadth = next((value for value in report.breadth if value.sector == item.sector), None)
                output(f"sector={item.sector} rs20={item.rs20} rs60={item.rs60} rs120={item.rs120} breadth50={breadth.above_50_pct if breadth else None} breadth200={breadth.above_200_pct if breadth else None} exclusion={item.exclusion_reason or 'NONE'}")
            output(f"top3={','.join(report.top3) or 'NONE'} prebreakout_technical_ready={report.pre_breakout_technical_ready} prebreakout_full_ready={report.pre_breakout_full_ready} inflection_ready={report.inflection_ready}")
            output(f"rs_ready_only={report.plan.rs_ready_only} rs_ready_sectors={','.join(report.plan.rs_ready_sectors) or 'NONE'} constituents_before_dedup={report.plan.constituents_before_dedup} unique_constituents={report.plan.unique_constituents} already_sufficient={report.plan.already_sufficient} need_backfill={len(report.plan.need_backfill)} unresolved={report.plan.unresolved} estimated_provider_calls={report.plan.estimated_provider_calls}")
            for item in report.plan.by_sector:
                output(f"plan_sector={item.sector} current_constituents={item.current_constituents} already_sufficient={item.already_sufficient} need_backfill={item.need_backfill} unresolved={item.unresolved}")
            return 0
        if arguments.command == "current-prebreakout-status":
            service, historical = current_prebreakout_factory()
            try:
                report = service.assess(); service.write_reports(report, Path(arguments.report_dir))
            finally:
                if hasattr(historical, "close"): historical.close()
            failed = sum(item.delivery_status == "FAIL" for item in report.rows)
            missing = sum(item.delivery_status == "MISSING" for item in report.rows)
            output(f"canonical_sectors={report.canonical_sector_count} excluded_sectors={len(report.excluded_sectors)} top3={','.join(report.top3) or 'NONE'} stocks={report.distinct_top3_stocks} ohlcv_ready={report.ohlcv_ready} delivery_ready={report.delivery_ready} delivery_pass={report.delivery_pass} delivery_fail={failed} delivery_missing={missing} full_setup_evaluable=0 prebreakout_candidates=0")
            for item in report.excluded_sectors:
                output(f"excluded_sector={item.sector} official_index={item.official_index} readiness=UNAVAILABLE reason={item.exclusion_reason}")
            for item in report.rows:
                output(f"symbol={item.symbol} sector={item.sector} delivery_status={item.delivery_status} delivery_pct={item.delivery_pct} bbw_pct={item.bbw_percentile} atr={item.atr} rsi={item.rsi14} setup_status={item.setup_status}")
            return 0
        if arguments.command == "run-governed-executable-setup-source":
            service, resources = governed_executable_setup_source_factory(time_stop_sessions=arguments.time_stop_sessions)
            try:
                as_of = _prebreakout_timestamp(arguments.as_of) if arguments.as_of else datetime.now(UTC)
                report = service.run(as_of=as_of)
            finally:
                for resource in reversed(resources):
                    if hasattr(resource, "close"):
                        resource.close()
            output(" ".join((
                f"run_id={report.run_id}", f"as_of={report.as_of.isoformat()}",
                f"state={report.state.value}", f"reason={report.reason or 'NONE'}",
                f"top3={','.join(report.top3) or 'NONE'}",
                f"excluded_sectors={','.join(report.excluded_sectors) or 'NONE'}",
                f"assessed={len(report.assessment_ids)}", f"eligible={report.eligible_count}",
                f"partial_or_data_blocked={report.partial_or_data_blocked_count}",
                f"rejected={report.rejected_count}", f"persisted={report.persisted_count}",
                f"duplicates={report.duplicate_count}",
            )))
            return 0 if report.state.value.startswith("READY_") else 2
        if arguments.command == "ingest-upstox-sector-constituents":
            from app.connections.credentials import create_credential_store
            from app.market_data.upstox import load_upstox_nse_bod_instrument_master
            planner, planner_store = current_sector_rotation_factory()
            try:
                plan = planner.assess(rs_ready_only=arguments.rs_ready_only).plan
            finally:
                if hasattr(planner_store, "close"):
                    planner_store.close()
            token = create_credential_store().load("upstox").get("access_token")
            if not token:
                raise RuntimeCompositionError("UPSTOX_ACCESS_TOKEN_REQUIRED")
            master = load_upstox_nse_bod_instrument_master()
            service, historical = current_sector_constituent_backfill_factory()
            try:
                report = service.ingest(plan, master_records=master.records, access_token=token, years=arguments.years, delay_seconds=arguments.delay_seconds)
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            output(f"planned={report.planned} provider_requests={report.provider_requests} accepted={report.accepted} duplicates={report.duplicates} conflicts={report.conflicts} unresolved={report.unresolved} stopped={report.stopped}")
            for failure in report.failures:
                output(f"failure={failure}")
            return 0 if not report.stopped else 2
        if arguments.command == "import-nse-delivery":
            importer, targets, historical = nse_delivery_import_factory()
            try:
                report = importer.import_csv(Path(arguments.file), source_url=arguments.source_url, source_page=arguments.source_page, fetched_at=datetime.now(UTC), targets=targets)
            finally:
                if hasattr(historical, "close"): historical.close()
            output(f"report_id={report.artifact.report_id} eq_rows={report.eq_rows_seen} accepted={report.accepted} unresolved={report.unresolved} rejected={report.rejected} duplicates={report.duplicates} universe_targets={len(targets)}")
            return 0 if report.rejected == 0 else 2
        if arguments.command == "import-bse-financial-feasibility":
            service, targets = bse_financial_import_factory()
            result = [service.ingest(instrument, code, limit=arguments.limit_per_instrument) for instrument, code in targets]
            for item in result:
                output(" ".join((
                    f"instrument_id={item.instrument_id}", f"bse_code={item.security_code}",
                    f"metadata={item.metadata_seen}", f"xbrl={item.xbrl_parsed}",
                    f"filings_inserted={item.filings_inserted}", f"facts_inserted={item.facts_inserted}",
                    f"rejected={item.rejected}",
                )))
            return 0 if all(item.rejected == 0 for item in result) else 2
        if arguments.command == "bse-nifty500-financials":
            from app.fundamentals.bse_nifty500_acquisition import (
                BseAcquisitionUnitState, BseArchiveDiscoveryIncompleteError, BseFinancialAcquisitionSettings,
            )
            service = bse_nifty500_acquisition_factory()
            as_of = _prebreakout_timestamp(arguments.as_of) if arguments.as_of else datetime.now(UTC)
            settings = BseFinancialAcquisitionSettings(batch_size=arguments.batch_size)
            if arguments.operation == "mapping-audit":
                inventory = service.mapping_audit(as_of=as_of, max_instruments=arguments.max_instruments, settings=settings)
                counts = {state.value: sum(item.state is state for item in inventory.mappings) for state in type(inventory.mappings[0].state)} if inventory.mappings else {}
                output(" ".join((
                    f"inventory_id={inventory.inventory_id}", f"universe_count={len(inventory.mappings)}",
                    f"exact_verified={counts.get('EXACT_VERIFIED', 0)}", f"unmapped={counts.get('UNMAPPED', 0)}",
                    f"conflict={counts.get('CONFLICT', 0)}", f"unsupported={counts.get('UNSUPPORTED', 0)}",
                    f"fingerprint={inventory.fingerprint}",
                )))
                return 0
            if arguments.operation == "dry-run":
                inventory, plan = service.dry_run(as_of=as_of, max_instruments=arguments.max_instruments, settings=settings)
                counts = {state.value: sum(item.state is state for item in inventory.mappings) for state in type(inventory.mappings[0].state)} if inventory.mappings else {}
                output(" ".join((
                    f"inventory_id={inventory.inventory_id}", f"universe_count={len(inventory.mappings)}",
                    f"exact_verified={counts.get('EXACT_VERIFIED', 0)}", f"unmapped={counts.get('UNMAPPED', 0)}",
                    f"conflict={counts.get('CONFLICT', 0)}", f"unsupported={counts.get('UNSUPPORTED', 0)}",
                    f"plan_id={plan.plan_id}", f"planned_units={len(plan.units)}",
                    f"already_satisfied={len(plan.already_satisfied_unit_ids)}", f"plan_fingerprint={plan.fingerprint}",
                )))
                return 0
            if arguments.operation == "plan":
                if not arguments.inventory_id:
                    raise RuntimeCompositionError("BSE_FINANCIAL_ACQUISITION_INVENTORY_REQUIRED")
                inventory = service.inventory(arguments.inventory_id)
                if inventory is None:
                    raise RuntimeCompositionError("BSE_FINANCIAL_ACQUISITION_INVENTORY_NOT_FOUND")
                try:
                    plan = service.build_plan(inventory, max_instruments=arguments.max_instruments, settings=settings)
                except BseArchiveDiscoveryIncompleteError as error:
                    output(_bse_nifty500_discovery_line(error.report))
                    return 2
                output(" ".join((
                    f"inventory_id={inventory.inventory_id}", f"plan_id={plan.plan_id}",
                    f"planned_units={len(plan.units)}", f"already_satisfied={len(plan.already_satisfied_unit_ids)}",
                    f"plan_fingerprint={plan.fingerprint}",
                )))
                return 0
            if arguments.operation == "archive-discovery":
                if not arguments.inventory_id:
                    raise RuntimeCompositionError("BSE_FINANCIAL_ACQUISITION_INVENTORY_REQUIRED")
                inventory = service.inventory(arguments.inventory_id)
                if inventory is None:
                    raise RuntimeCompositionError("BSE_FINANCIAL_ACQUISITION_INVENTORY_NOT_FOUND")
                report = service.discover_archives(inventory, max_instruments=arguments.max_instruments, settings=settings)
                output(_bse_nifty500_discovery_line(report))
                return 0 if not report.provider_halted and report.remaining_unresolved == 0 else 2
            plan = service.plan(arguments.plan_id)
            if plan is None:
                if arguments.operation in {"status", "failures"}:
                    output("status=NO_PERSISTED_BSE_FINANCIAL_ACQUISITION_PLAN")
                    return 0
                raise RuntimeCompositionError("BSE_FINANCIAL_ACQUISITION_PLAN_REQUIRED")
            if arguments.operation in {"status", "failures"}:
                report = service.status(plan.plan_id)
                assert report is not None
                output(_bse_nifty500_run_line(report))
                if arguments.operation == "failures":
                    for item in report.receipts:
                        if item.state not in {BseAcquisitionUnitState.ACCEPTED, BseAcquisitionUnitState.ALREADY_PRESENT}:
                            output(f"unit_id={item.unit_id} state={item.state.value} detail={item.detail or 'NONE'}")
                return 0 if not report.provider_halted else 2
            if arguments.operation == "canary":
                report = service.canary(plan, max_units=arguments.max_units or 3, settings=settings)
            elif arguments.operation == "resume":
                report = service.resume(plan.plan_id, max_units=arguments.max_units, settings=settings)
            else:
                report = service.execute(plan, max_units=arguments.max_units, settings=settings)
            output(_bse_nifty500_run_line(report))
            for item in report.receipts:
                output(f"unit_id={item.unit_id} state={item.state.value} attempt={item.attempt} facts_inserted={item.facts_inserted} facts_duplicate={item.facts_duplicate} conflicts={item.facts_conflicted} detail={item.detail or 'NONE'}")
            return 0 if not report.provider_halted and report.terminal_failure == 0 else 2
        if arguments.command == "collect-real-portfolio-bse-financials":
            report = bse_real_portfolio_collector_factory().run()
            for item in report.receipts:
                output(" ".join((
                    f"instrument_id={item.canonical_instrument_id}", f"isin={item.isin or 'UNKNOWN'}",
                    f"mapping={item.mapping.status.value}", f"bse_code={item.mapping.security_code or 'NONE'}",
                    f"bse_security_id={item.mapping.security_id or 'NONE'}",
                    f"bse_name={item.mapping.security_name or 'NONE'}",
                    f"mapping_source={item.mapping.source_type}",
                    f"source_master_date={item.mapping.source_master_date.isoformat() if item.mapping.source_master_date else 'NONE'}",
                    f"filings_discovered={item.filings_discovered}", f"new_filings={item.new_filings}",
                    f"unchanged_filings={item.unchanged_filings}", f"facts_accepted={item.canonical_facts_accepted}",
                    f"facts_unchanged={item.canonical_facts_unchanged}", f"conflicts={item.financial_conflicts}",
                    f"blockers={','.join(item.blockers) if item.blockers else 'NONE'}",
                )))
            return 0 if all(not item.blockers and item.financial_conflicts == 0 for item in report.receipts) else 2
        if arguments.command == "collect-real-portfolio-bse-historical-annuals":
            report = bse_real_portfolio_collector_factory().run_historical_annual_backfill()
            for item in report.receipts:
                output(" ".join((
                    f"instrument_id={item.canonical_instrument_id}", f"isin={item.isin or 'UNKNOWN'}",
                    f"mapping={item.mapping.status.value}", f"bse_code={item.mapping.security_code or 'NONE'}",
                    f"filings_discovered={item.filings_discovered}", f"new_filings={item.new_filings}",
                    f"unchanged_filings={item.unchanged_filings}", f"facts_accepted={item.canonical_facts_accepted}",
                    f"facts_unchanged={item.canonical_facts_unchanged}", f"conflicts={item.financial_conflicts}",
                    f"blockers={','.join(item.blockers) if item.blockers else 'NONE'}",
                )))
            return 0 if all(not item.blockers and item.financial_conflicts == 0 for item in report.receipts) else 2
        if arguments.command == "import-nse-universe":
            importer = universe_importer_factory()
            now = datetime.now(UTC)
            report = importer.import_csv(
                arguments.file, as_of=now, snapshot_id=f"nse-universe:{uuid4().hex}", dry_run=arguments.dry_run,
                refresh_identical_as_of=arguments.refresh_identical_as_of,
            )
            output(
                " ".join((
                    f"snapshot_id={report.snapshot.snapshot_id}", f"dry_run={report.dry_run}",
                    f"status={'IDENTICAL' if report.identical else 'IMPORTED'}",
                    f"raw_records={report.raw_records}", f"eligible_equities={report.snapshot.eligible_security_count}",
                    f"main_board_equities={report.main_board_equity_records}",
                    f"excluded={report.excluded}", f"duplicates={report.duplicates}",
                    f"missing_symbols={report.missing_symbol_count}", f"malformed_isins={report.malformed_isin_count}",
                    f"missing_sectors={report.missing_sector_count}", f"missing_industries={report.missing_industry_count}",
                ))
            )
            return 0
        if arguments.command == "import-nse-tick-master":
            importer, repository = nse_tick_master_importer_factory()
            try:
                report = importer.import_file(arguments.file, observed_at=_nse_tick_observed_at(arguments.observed_at))
            finally:
                if hasattr(repository, "close"):
                    repository.close()
            output(" ".join((
                f"source_file={report.source_file}", f"source_fingerprint={report.source_fingerprint}",
                f"observed_at={report.observed_at.isoformat()}",
                f"rows_seen={report.rows_seen}", f"eligible_rows={report.eligible_rows}",
                f"accepted={report.accepted}", f"duplicates={report.duplicates}",
                f"unresolved_identity={report.unresolved_identity}", f"invalid_tick={report.invalid_tick}",
                f"malformed={report.malformed}", f"conflicts={report.conflicts}",
            )))
            for failure in report.failures:
                output(f"failure=line:{failure.line_number}:{failure.code}")
            return 0 if report.conflicts == 0 else 2
        if arguments.command in {"data-readiness", "universe-status"}:
            service = data_readiness_factory()
            if hasattr(service, "report"):
                local = service.report()
                output(f"database={local.database.storage_mode.value if local.database.storage_mode else 'UNKNOWN'} ready={local.database.ready} detail={local.database.detail}")
                universe = local.universe
                output(f"universe_snapshot={universe.universe_snapshot_id or 'OFFICIAL_UNIVERSE_FILE_REQUIRED'} eligible={universe.eligible_equities} excluded={universe.excluded} full_scan={universe.full_scan.status.value}")
                for item in universe.coverage:
                    output(f"domain={item.domain.value} ready={item.ready} partial={item.partial} missing={item.missing} unavailable={item.unavailable} stale={item.stale} total={item.total}")
                for provider, status in universe.provider_statuses:
                    output(f"provider={provider} status={status.value}")
                for warning in universe.warnings:
                    output(f"warning={warning}")
                mapping_counts: dict[tuple[str, str], int] = {}
                for item in universe.mapping_statuses:
                    key = (item.provider, item.status.value)
                    mapping_counts[key] = mapping_counts.get(key, 0) + 1
                for (provider, status), count in sorted(mapping_counts.items()):
                    output(f"mapping_provider={provider} status={status} count={count}")
            else:
                report = service.readiness(mode=RuntimeMode.STORED_DATA)
                for item in report.items:
                    output(f"provider={item.provider or 'none'} family={item.family.value} status={item.status.value} configured={item.configured} validated={item.validated}")
            return 0
        if arguments.command == "coverage-report":
            report = coverage_report_factory().report()
            if report is None:
                output("UNIVERSE_SNAPSHOT_REQUIRED")
                return 2
            output(f"universe_snapshot={report.universe_snapshot_id} total={report.total_instruments} deep_ready={report.deep_ready} deep_partial={report.deep_partial} deep_unavailable={report.deep_unavailable} pre_breakout_ready={report.pre_breakout_ready} inflection_ready={report.inflection_ready}")
            for item in report.domains:
                output(f"domain={item.domain.value} ready={item.ready} partial={item.partial} missing={item.missing} stale={item.stale} conflicted={item.conflicted} unavailable={item.unavailable} total={item.total} ready_percent={item.ready_percent}")
            for item in report.gaps:
                output(f"gap={item.domain.value} affected={item.affected_instrument_count} coverage_percent={item.coverage_percentage} blocks={','.join(item.downstream_engines_blocked)}")
            for warning in report.warnings: output(f"warning={warning}")
            return 0
        if arguments.command == "import-taxonomy":
            importer, instruments = taxonomy_importer_factory()
            report = importer.import_csv(arguments.file, instruments=instruments, as_of=datetime.now(UTC), dry_run=arguments.dry_run)
            output(f"accepted={report.accepted} unresolved={report.unresolved} ambiguous={report.ambiguous} dry_run={report.dry_run}")
            for warning in report.warnings: output(f"warning={warning}")
            return 0 if report.accepted else 2
        if arguments.command == "import-nse-indices-taxonomy":
            from app.taxonomy.nse_indices import write_reconciliation_reports
            importer, instruments, frozen = nse_indices_taxonomy_importer_factory()
            root = Path(arguments.source_dir)
            report = importer.import_files(
                nifty500_csv=root / "nifty500.csv", total_market_csv=root / "nifty_total_market.csv",
                structure_pdf=root / "industry_classification_structure_2023-07.pdf",
                classification_page=root / "industry_classification_page.html", instruments=instruments,
                frozen_instrument_ids=frozen, fetched_at=datetime.now(UTC), dry_run=arguments.dry_run,
            )
            json_path, csv_path = write_reconciliation_reports(report, directory=Path("reports"))
            output(" ".join((
                f"nifty500_rows={report.nifty500_rows}", f"total_market_rows={report.total_market_rows}",
                f"classifications_saved={report.classifications_saved}", f"exact_unique={report.exact_unique}",
                f"not_found={report.not_found}", f"unmapped={report.unmapped_to_canonical_universe}",
                f"frozen40_evidence={len(report.frozen40)}", f"report_json={json_path}", f"report_csv={csv_path}",
            )))
            return 0 if report.classifications_saved or arguments.dry_run else 2
        if arguments.command == "import-nse-sector-indices":
            import json
            from app.taxonomy.nse_indices import parse_nse_indices_industry_structure
            root = Path(arguments.source_dir)
            importer = nse_sector_index_importer_factory()
            report = importer.import_files(
                sectoral_page=root / "sectoral_indices_page.html", individual_pages=tuple(sorted((root / "pages").glob("*.html"))),
                constituent_files=tuple(sorted((root / "constituents").glob("*.csv"))),
                historical_report_page=(root / "historical_data_report_page.html") if (root / "historical_data_report_page.html").is_file() else None,
                hierarchy=parse_nse_indices_industry_structure(Path(arguments.taxonomy_structure)), fetched_at=datetime.now(UTC), dry_run=arguments.dry_run,
            )
            frozen40_matches = None
            prior_report = Path("reports/nse_taxonomy_reconciliation.json")
            if prior_report.is_file():
                frozen40_matches = sum(1 for item in json.loads(prior_report.read_text(encoding="utf-8")).get("frozen40", ()) if item.get("mapping_status") == "EXACT_ISIN_AND_SYMBOL")
            json_path, csv_path = importer.write_reports(report, Path("reports"), frozen40_taxonomy_matches=frozen40_matches)
            output(" ".join((
                f"indices_discovered={report.indices_discovered}", f"mapped_exact={report.mapped_exact}",
                f"ambiguous={report.ambiguous}", f"unresolved={report.unresolved}", f"constituents_saved={report.constituents_saved}",
                f"report_json={json_path}", f"report_csv={csv_path}", "historical_export=NSE_INDICES_HISTORICAL_EXPORT_UNAVAILABLE",
            )))
            return 0
        if arguments.command == "real-brain-trial":
            report = real_brain_trial_factory().run(sample_size=arguments.sample_size, frozen_cohort=arguments.frozen_cohort, frozen_cohort_trial_id=arguments.frozen_cohort_trial)
            output(f"trial_id={report.trial_id} sample_size={report.requested_sample_size} selection={report.selection_method}")
            output(f"symbols={','.join(report.selected_symbols)}")
            output(f"complete={report.complete_count} partial={report.partial_count} unavailable={report.unavailable_count} diagnostic_evaluated={report.diagnostic_evaluated_total} diagnostic_missing={report.diagnostic_missing_total}")
            output(f"valid_score={report.valid_decision_score_count} valid_confidence={report.valid_confidence_count} provider_calls={report.provider_calls} runtime_ms={report.total_elapsed_milliseconds}")
            for blocker in report.blockers:
                output(f"blocker={blocker.code} affected={blocker.affected_stock_count}")
            return 0
        if arguments.command == "ingest-upstox-frozen-cohort":
            service, cohort, master, historical = upstox_population_factory()
            try:
                from app.connections.credentials import create_credential_store
                token = create_credential_store().load("upstox").get("access_token")
                report = service.populate(
                    cohort=cohort, master_records=master.records,
                    master_source_reference=master.source_url, master_checksum=master.checksum,
                    access_token=token, years=arguments.years,
                )
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            output(" ".join((
                f"requested={report.requested}", f"matched={report.matched}", f"ambiguous={report.ambiguous}",
                f"unmatched={report.unmatched}", f"nifty500={report.benchmark_status}",
                f"symbols_ingested={report.symbols_ingested}", f"bars_stored={report.bars_stored}",
                f"sufficient_252={report.sufficient_252}", f"provider_requests={report.provider_requests}",
                f"runtime_ms={report.runtime_milliseconds}", f"adjustment_status={report.adjustment_status.value}",
            )))
            for failure in report.failures:
                output(f"failure={failure}")
            return 0 if not report.failures else 2
        if arguments.command == "ingest-upstox-sector-indices":
            from app.market_data.upstox_sector_indices import write_upstox_nse_index_mapping_reports
            service, mappings, master, historical, token = upstox_sector_index_population_factory()
            try:
                report = service.populate(
                    sector_mappings=mappings, master_records=master.records, access_token=token,
                    years=arguments.years, master_source_reference=master.source_url, master_checksum=master.checksum,
                )
                json_path, csv_path = write_upstox_nse_index_mapping_reports(report.mappings, Path(arguments.report_dir))
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            resolved = len(report.resolved)
            output(" ".join((
                f"mapped={resolved}", f"unresolved={len(report.mappings) - resolved}",
                f"provider_requests={report.provider_requests}", f"report_json={json_path}", f"report_csv={csv_path}",
            )))
            for item in report.reports:
                output(" ".join((
                    f"index={item.instrument_id}", f"accepted={item.accepted_count}",
                    f"duplicates={item.duplicate_count}", f"conflicts={item.conflict_count}",
                    f"coverage={item.coverage.value}",
                )))
            return 0 if report.provider_requests else 2
        if arguments.command == "probe-upstox-sector-indices":
            from app.market_data.upstox_sector_indices import write_upstox_nse_index_mapping_reports
            service, mappings, master, historical, token = upstox_sector_index_population_factory()
            try:
                report = service.probe(
                    sector_mappings=mappings, master_records=master.records, access_token=token, years=arguments.years,
                )
                json_path, csv_path = write_upstox_nse_index_mapping_reports(report.mappings, Path(arguments.report_dir))
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            output(" ".join((
                f"probe_requests={report.provider_requests}", f"report_json={json_path}", f"report_csv={csv_path}",
            )))
            for item in report.reports:
                output(" ".join((
                    f"index={item.instrument_id}", f"received={item.received_count}",
                    f"coverage={item.coverage.value}", f"warnings={','.join(item.warnings) or 'NONE'}",
                )))
            return 0 if report.reports and all(item.coverage.value != "UNAVAILABLE" for item in report.reports) else 2
        if arguments.command == "upstox-sector-index-status":
            from app.market_data.upstox_sector_indices import stored_nse_index_history_status
            historical, mappings = upstox_sector_index_status_factory()
            try:
                values = stored_nse_index_history_status(historical, mappings)
            finally:
                if hasattr(historical, "close"):
                    historical.close()
            for item in values:
                output(" ".join((
                    f"index={item.canonical_instrument_id}", f"name={item.official_index_name}",
                    f"yahoo={item.yahoo_observations}", f"upstox={item.upstox_observations}",
                    f"raw={item.raw_observations}", f"canonical={item.canonical_observations}",
                    f"canonical_upstox={item.canonical_upstox_selected}", f"canonical_yahoo={item.canonical_yahoo_selected}",
                )))
            return 0
        if arguments.command == "ingest-yfinance-frozen-cohort":
            service, cohort, historical = yfinance_population_factory()
            try:
                report = service.populate(cohort=cohort, years=arguments.years, include_verified_nifty500=not arguments.without_nifty500)
            finally:
                if hasattr(historical, "close"): historical.close()
            output(" ".join((
                f"requested={report.requested}", f"mapped={report.mapped}", f"history_success={report.history_success}",
                f"history_failed={report.history_failed}", f"nifty500={report.benchmark_status}",
                f"symbols_ingested={report.symbols_ingested}", f"bars_stored={report.bars_stored}",
                f"sufficient_252={report.sufficient_252}", f"gappy={report.gappy}",
                f"provider_requests={report.provider_requests}", f"runtime_ms={report.runtime_milliseconds}",
                f"adjustment_status={report.adjustment_status.value}",
            )))
            for failure in report.failures: output(f"failure={failure}")
            return 0 if not report.failures else 2
        if arguments.command == "validate-yfinance-frozen-stock":
            service, cohort, historical = yfinance_population_factory()
            try:
                report = service.validate_one(cohort=cohort, years=arguments.years, symbol=arguments.symbol)
            finally:
                if hasattr(historical, "close"): historical.close()
            output(" ".join((
                f"symbol={report.canonical_symbol}", f"yahoo_symbol={report.yahoo_symbol}",
                f"mapping_persisted={report.mapping_persisted}", f"sessions={report.session_count}",
                f"accepted={report.report.accepted_count}", f"coverage={report.report.coverage.value}",
                f"adjustment_status={report.report.adjustment_status.value}",
            )))
            for warning in report.report.warnings: output(f"warning={warning}")
            return 0 if report.report.coverage.value != "UNAVAILABLE" else 2
        if arguments.command == "enrich-yahoo-secondary-frozen-cohort":
            if arguments.delay_seconds < 0.1:
                raise RuntimeCompositionError("YAHOO_SECONDARY_DELAY_MUST_BE_AT_LEAST_0_1_SECONDS")
            service, cohort, repository = yahoo_secondary_enrichment_factory(delay_seconds=arguments.delay_seconds)
            try:
                report = service.write_reports(service.enrich(cohort, phase=arguments.phase))
            finally:
                if hasattr(repository, "close"): repository.close()
            output(" ".join((
                f"phase={report.phase}", f"requested={report.requested}", f"snapshots_saved={report.snapshots_saved}",
                f"provider_requests={report.provider_requests}", f"quarterly_median={report.median_quarterly_periods}",
                f"annual_median={report.median_annual_periods}", f"failures={len(report.failures)}",
            )))
            output(f"report_json={report.report_json}")
            output(f"report_csv={report.report_csv}")
            for name, count in sorted(report.availability.items()): output(f"dataset={name} available={count}/{report.requested}")
            for failure in report.failures: output(f"failure={failure}")
            return 0
        if arguments.command == "run-once":
            settings = replace(
                settings,
                mode=RuntimeMode.MOCK if arguments.mode == "mock" else RuntimeMode.STORED_DATA if arguments.mode == "stored" else settings.mode,
                universe_id=arguments.universe or settings.universe_id,
            )
            if not settings.universe_id:
                raise RuntimeCompositionError("RUNTIME_UNIVERSE_ID or --universe is required for run-once.")
        if arguments.command == "validate-config":
            output("CONFIG VALID: runtime scheduler settings are safe.")
            return 0
        if arguments.command == "status":
            _write_status(RuntimeHealthService(settings=settings), output)
            return 0
        if arguments.command == "worker" and not settings.enabled:
            raise RuntimeCompositionError("Worker is disabled; set RUNTIME_SCHEDULER_ENABLED=true explicitly.")
        scheduler = scheduler_factory(settings)
        if arguments.command == "worker":
            worker = RuntimeWorker(scheduler, interval_seconds=settings.interval_seconds)
            try:
                return 0 if worker.run_forever() else 1
            except KeyboardInterrupt:
                worker.stop()
                output("WORKER STOPPED")
                return 0
        result = scheduler.run_once(dry_run=arguments.dry_run)
        _write_cycle(result, scheduler.status(), output)
        return _cycle_exit_code(result, scheduler.status().last_cycle_status)
    except DhanAuthError as error:
        output(str(error))
        return 1
    except (ValueError, RuntimeCompositionError) as error:
        # An explicit bounded ingestion command needs an actionable local
        # blocker, while the generic scheduler commands retain their safe
        # configuration-error behaviour.
        if arguments.command in {"backfill-nse-udiff-daily-history", "audit-nse-udiff-daily-integrity", "ingest-upstox-frozen-cohort", "ingest-yfinance-frozen-cohort", "validate-yfinance-frozen-stock", "import-bse-financial-feasibility", "collect-real-portfolio-bse-financials", "import-nse-delivery", "import-nse-tick-master", "approve-prebreakout-policy", "select-prebreakout-policy", "data-operations-run", "reconcile-upstox-historical-conflicts", "data-operations-schedule-once", "data-operations-worker", "historical-bar-conflicts", "ohlcv-readiness", "materialize-real-portfolio-nse-reg31-ownership", "materialize-real-portfolio-reliability-integrity", "dhan-ltp-canary", "dhan-materialize-mappings"}:
            output(str(error) or "UPSTOX_INGESTION_CONFIGURATION_ERROR")
        else:
            output("RUNTIME CONFIGURATION ERROR")
        return 1


def _cycle_exit_code(result: RuntimeCycleResult | None, status: RuntimeCycleStatus | None) -> int:
    if result is None:
        return 1 if status is None else 2
    return 0 if result.overall_status is RuntimeCycleStatus.SUCCESS else 2 if result.overall_status in {RuntimeCycleStatus.PARTIAL, RuntimeCycleStatus.SKIPPED} else 1


def _prebreakout_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("PREBREAKOUT_POLICY_TIMESTAMP_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("PREBREAKOUT_POLICY_TIMESTAMP_NAIVE")
    return parsed


def _udiff_integrity_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("NSE_UDIFF_INTEGRITY_TIMESTAMP_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("NSE_UDIFF_INTEGRITY_TIMESTAMP_NAIVE")
    return parsed


def _nse_tick_observed_at(value: str | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("NSE_TICK_OBSERVED_AT_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("NSE_TICK_OBSERVED_AT_NAIVE")
    return parsed


def _bse_nifty500_run_line(report) -> str:
    return " ".join((
        f"run_id={report.run_id}", f"plan_id={report.plan_id}", f"attempted={report.attempted}",
        f"accepted={report.accepted}", f"already_present={report.already_present}",
        f"quarantined={report.quarantined}", f"unavailable={report.unavailable}",
        f"retryable_failure={report.retryable_failure}", f"terminal_failure={report.terminal_failure}",
        f"provider_halted={'yes' if report.provider_halted else 'no'}",
    ))


def _bse_nifty500_discovery_line(report) -> str:
    halt = report.latest_halt_receipt
    return " ".join((
        f"discovery_run_id={report.run_id}", f"securities_examined={report.securities_examined}",
        f"discovered={report.discovered}", f"no_archive_available={report.no_archive_available}",
        f"retryable_failure={report.retryable_failures}", f"terminal_failure={report.terminal_failures}",
        f"remaining_unresolved={report.remaining_unresolved}",
        f"provider_halted={'yes' if report.provider_halted else 'no'}",
        f"halt_reason={halt.halt_reason if halt else 'NONE'}",
    ))


def _write_cycle(result: RuntimeCycleResult | None, health, output: Callable[[str], None]) -> None:
    if result is None:
        output(f"CYCLE {health.last_cycle_status.value if health.last_cycle_status else 'FAILED'}")
        return
    output(f"cycle_id={result.cycle_id} status={result.overall_status.value} mode={result.mode.value} universe={result.universe_id}")
    output(f"data_as_of={result.data_as_of.isoformat()} snapshots={','.join(result.snapshots_written) or 'none'}")
    output(f"stages={','.join(f'{stage.stage.value}:{stage.status.value}' for stage in result.stage_results)}")
    if result.warnings:
        output(f"warnings={','.join(result.warnings)}")


def _write_status(service: RuntimeHealthService, output: Callable[[str], None]) -> None:
    status = service.status()
    output(
        " ".join((
            f"scheduler_enabled={status.scheduler_enabled}",
            f"scheduler_running={status.scheduler_running}",
            f"mode={status.runtime_mode.value}",
            f"universe={status.universe_id or 'unconfigured'}",
            f"last_cycle_status={status.last_cycle_status.value if status.last_cycle_status else 'none'}",
        ))
    )


def _data_operations_run_line(value) -> str:
    return " ".join((
        f"run_id={value.run_id}", f"family={value.family.value}", f"mode={value.mode.value}",
        f"status={value.status.value}", f"accepted={value.accepted_count}",
        f"duplicates={value.duplicate_count}", f"conflicts={value.conflict_count}",
        f"rejected={value.rejected_count}", f"gaps={value.gap_count}",
        f"retries={value.retry_count}", f"error={value.error_summary or 'NONE'}",
    ))


def _historical_conflict_line(value) -> str:
    """Render factual conflict evidence only; neither side is selected."""
    def values(item) -> str:
        return ",".join((
            f"open={item.open}", f"high={item.high}", f"low={item.low}", f"close={item.close}",
            f"volume={item.volume if item.volume is not None else 'NONE'}",
            f"turnover={item.turnover if item.turnover is not None else 'NONE'}",
            f"trade_count={item.trade_count if item.trade_count is not None else 'NONE'}",
            f"adjustment_status={item.adjustment_status.value}",
        ))
    return " ".join((
        f"conflict_fingerprint={value.conflict_fingerprint}",
        f"instrument_id={value.canonical_instrument_id}", f"timeframe={value.timeframe.value}",
        f"start_time={value.start_time.isoformat()}", f"end_time={value.end_time.isoformat()}",
        f"stored_provider={value.stored_lineage.provider_identity}",
        f"stored_provider_version={value.stored_lineage.provider_version or 'NONE'}",
        f"stored_mapping_version={value.stored_lineage.mapping_version or 'NONE'}",
        f"stored_normalizer_version={value.stored_lineage.normalizer_version or 'NONE'}",
        f"stored_source_identity={value.stored_lineage.source_identity or 'NONE'}",
        f"incoming_provider={value.incoming_lineage.provider_identity}",
        f"incoming_provider_version={value.incoming_lineage.provider_version or 'NONE'}",
        f"incoming_mapping_version={value.incoming_lineage.mapping_version or 'NONE'}",
        f"incoming_normalizer_version={value.incoming_lineage.normalizer_version or 'NONE'}",
        f"incoming_source_identity={value.incoming_lineage.source_identity or 'NONE'}",
        f"stored_bar_fingerprint={value.stored_bar_fingerprint}",
        f"incoming_bar_fingerprint={value.incoming_bar_fingerprint}",
        f"differing_fields={','.join(value.differing_fields)}",
        f"detected_at={value.detected_at.isoformat()}", f"ingestion_run_id={value.ingestion_run_id or 'NONE'}",
        f"stored_values={values(value.stored_values)}", f"incoming_values={values(value.incoming_values)}",
    ))


if __name__ == "__main__":
    sys.exit(main())
