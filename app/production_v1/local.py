"""Local, no-network Production-V1 readiness composition."""
from __future__ import annotations

from datetime import UTC, datetime

from app.data_operations.models import DataOperationsFamilyHealth, DataOperationsHealthStatus, EvidenceDataFamily, EvidenceRefreshWatermark
from app.data_operations.upstox import MINIMUM_REQUIRED_DAILY_SESSIONS
from app.data_operations.service import DataOperationsService
from app.data_operations.store import DataOperationsStore
from app.forward_paper.composition import StoredExecutableSetupStore
from app.forward_paper.service import PaperTradingSettings
from app.production_v1.governed_setup_source import (
    GovernedExecutableSetupSourceRunStore,
    GovernedExecutableSetupSourceState,
)
from app.forward_paper.store import ForwardPaperStore
from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
from app.market_data.index_close_series import CoreSnapshotIndexCloseStore
from app.market_data.models import Timeframe
from app.market_data.ohlcv_readiness import OhlcvReadinessService
from app.market_data.upstox import UPSTOX_PROVIDER
from app.market_data.upstox_sector_indices import NIFTY_500_INDEX_ID
from app.market_data.current_sector_rotation import CurrentSectorRankingStore, CurrentSectorRotationService
from app.production_v1.models import ProductionComponent, ProductionComponentHealth, ProductionReadinessState, ProductionSourceHealth, ProductionSourceStatus
from app.production_v1.sector_universe_coverage import assess_sector_universe_coverage
from app.production_v1.service import ProductionV1CycleRunStore, build_readiness_report
from app.storage.database import DatabaseBackend, DatabaseReadinessProbe, DatabaseConnectionFactory, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.service import CoreUniverseAnalysisStore


_FAMILY_COMPONENT = {
    EvidenceDataFamily.OHLCV: ProductionComponent.OHLCV,
    EvidenceDataFamily.INDEX_BARS: ProductionComponent.INDEX_BARS,
    EvidenceDataFamily.DELIVERY: ProductionComponent.DELIVERY,
    EvidenceDataFamily.INDEX_MEMBERSHIP: ProductionComponent.MEMBERSHIP,
    EvidenceDataFamily.TAXONOMY_REFERENCE: ProductionComponent.TAXONOMY,
    EvidenceDataFamily.CORPORATE_ACTIONS: ProductionComponent.CORPORATE_ACTIONS,
    EvidenceDataFamily.FINANCIAL_RESULTS: ProductionComponent.FINANCIALS,
    EvidenceDataFamily.SHAREHOLDING: ProductionComponent.SHAREHOLDING,
    EvidenceDataFamily.MACRO: ProductionComponent.MACRO,
    EvidenceDataFamily.NEWS: ProductionComponent.NEWS,
}

_REGISTERED_SOURCE_METADATA = {
    EvidenceDataFamily.OHLCV: ("upstox", "UpstoxOhlcvRefreshJob"),
    EvidenceDataFamily.INDEX_BARS: ("upstox", "UpstoxIndexBarsRefreshJob"),
    EvidenceDataFamily.DELIVERY: ("nse_official_local", "NseDeliveryStagingJob"),
    EvidenceDataFamily.INDEX_MEMBERSHIP: ("nse_indices_official_local", "NseIndexMembershipRefreshJob"),
    EvidenceDataFamily.TAXONOMY_REFERENCE: ("nse_indices_official_local", "NseTaxonomyReferenceRefreshJob"),
    EvidenceDataFamily.CORPORATE_ACTIONS: ("nse_official_local", "NseCorporateActionsRefreshJob"),
    EvidenceDataFamily.FINANCIAL_RESULTS: ("bse_official_local_xbrl", "BseLocalFinancialResultsRefreshJob"),
    EvidenceDataFamily.SHAREHOLDING: ("nse_official_reg31_local", "NseReg31ShareholdingRefreshJob"),
    EvidenceDataFamily.MACRO: ("rbi_official_current_rates", "RbiCurrentRatesRefreshJob"),
    EvidenceDataFamily.NEWS: ("nse_official_corporate_announcements", "NseCorporateAnnouncementsRefreshJob"),
}


class LocalProductionV1ReadinessService:
    def __init__(self, settings: DatabaseSettings, *, operations_factory=None, historical_store_factory=None,
                 paper_settings_factory=PaperTradingSettings.from_environment,
                 clock=lambda: datetime.now(UTC)) -> None:
        self._settings, self._operations_factory = settings, operations_factory
        self._historical_store_factory, self._paper_settings_factory, self._clock = (
            historical_store_factory or _historical_store, paper_settings_factory, clock,
        )

    def report(self):
        repository = create_core_api_snapshot_repository(self._settings)
        resources: tuple[object, ...] = ()
        try:
            now = self._clock(); database = DatabaseReadinessProbe(DatabaseConnectionFactory(self._settings)).check()
            operation_store = DataOperationsStore(repository)
            # Health always reads the durable ledger.  Where the host has
            # registered concrete jobs, retain that source/adapter identity in
            # the public-safe readiness report; no credential value is read by
            # this code path.
            if self._operations_factory is None:
                operations = DataOperationsService(operation_store, {})
            else:
                operations, resources = self._operations_factory()
            historical = self._historical_store_factory(self._settings)
            resources = (*resources, historical)
            operation_health = operations.health(now=now)
            operation_map = {item.family: item for item in operation_health.families}
            sources=[]
            for family, component in _FAMILY_COMPONENT.items():
                item = operation_map[family]
                registered = family in operations.registered_families
                source, adapter = _REGISTERED_SOURCE_METADATA.get(family, (None, None)) if registered else (None, None)
                if item.status is DataOperationsHealthStatus.HEALTHY and registered:
                    status, blocker = ProductionSourceStatus.OPERATIONAL, None
                elif item.status is DataOperationsHealthStatus.DEGRADED and registered:
                    status, blocker = ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION, ",".join(item.reasons) or "REFRESH_DEGRADED"
                else:
                    status = ProductionSourceStatus.BLOCKED_CONFIGURATION if registered else ProductionSourceStatus.BLOCKED_MISSING_APPROVED_SOURCE
                    blocker = ",".join(item.reasons) or ("NEVER_RUN" if registered else "APPROVED_SOURCE_NOT_REGISTERED")
                watermark = operation_store.latest_watermark(family)
                coverage = watermark.accepted_through.isoformat() if watermark and watermark.accepted_through else None
                sources.append(ProductionSourceHealth(component, source, adapter, status, coverage, blocker))
            universe = CoreUniverseAnalysisStore(repository)
            current_universe = universe.latest_universe_snapshot()
            target_ids = current_universe.instrument_ids if current_universe is not None else ()
            mapped_ids = {
                item.canonical_instrument_id
                for item in universe.provider_mappings(provider=UPSTOX_PROVIDER, as_of=now)
            }
            ohlcv_watermark = operation_store.latest_watermark(EvidenceDataFamily.OHLCV)
            ohlcv_coverage, _ = OhlcvReadinessService(historical).coverage(
                target_ids,
                as_of=now,
                mapping_available=mapped_ids.__contains__,
                required_latest_at=(ohlcv_watermark.accepted_through if ohlcv_watermark else None),
            )
            index_health = operation_map[EvidenceDataFamily.INDEX_BARS]
            benchmark_state, benchmark_reason = _nifty500_benchmark_readiness(
                historical, watermark=operation_store.latest_watermark(EvidenceDataFamily.INDEX_BARS),
                index_health=index_health, now=now,
            )
            # This consumes the existing stored-only rotation result.  It does
            # not rerun a provider, invent index bars, or change ranking.
            rotation = CurrentSectorRotationService(
                repository=repository, universe=universe, historical_store=historical,
                index_close_store=CoreSnapshotIndexCloseStore(repository), clock=self._clock,
            ).assess(as_of=now)
            sector_coverage = assess_sector_universe_coverage(rotation)
            studies = ForwardPaperStore(repository).studies(); setups = StoredExecutableSetupStore(repository).list(as_of=now)
            setup_source_run = GovernedExecutableSetupSourceRunStore(repository).latest(as_of=now)
            latest_successful_cycle = ProductionV1CycleRunStore(repository).latest_successful(as_of=now)
            paper_settings = self._paper_settings_factory()
            shared_brain_state, shared_brain_reason = _shared_brain_readiness(repository, self._settings, universe)
            components=[]
            for component in ProductionComponent:
                if component is ProductionComponent.DATABASE:
                    state, reason = ProductionReadinessState.READY, None
                elif component is ProductionComponent.DATA_OPERATIONS:
                    state, reason = ProductionReadinessState.DEGRADED, "SOURCE_FAMILIES_NOT_YET_OPERATIONAL"
                elif component in _FAMILY_COMPONENT.values():
                    source=next(item for item in sources if item.family is component)
                    if component is ProductionComponent.OHLCV and source.status in {
                        ProductionSourceStatus.OPERATIONAL,
                        ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION,
                    }:
                        # U17's family health remains truthful (the refresh run
                        # recorded conflicts), but no global bar-source failure
                        # follows from an instrument-local immutable conflict.
                        # A non-empty safe subset is the only current consumer
                        # requirement; no percentage threshold is introduced.
                        state = (
                            ProductionReadinessState.READY
                            if source.status is ProductionSourceStatus.OPERATIONAL
                            else ProductionReadinessState.DEGRADED
                        ) if ohlcv_coverage.healthy_ready else ProductionReadinessState.BLOCKED
                        reason = (
                            None if state is ProductionReadinessState.READY else
                            _ohlcv_readiness_reason(ohlcv_coverage, source.blocker)
                        )
                    elif component in {
                        ProductionComponent.MEMBERSHIP,
                        ProductionComponent.TAXONOMY,
                        ProductionComponent.CORPORATE_ACTIONS,
                        ProductionComponent.MACRO,
                        ProductionComponent.NEWS,
                    }:
                        # Official reference imports may truthfully report a
                        # non-empty unresolved subset.  Their U17 receipt is
                        # operational with a limitation, not a fabricated
                        # all-or-nothing source outage.  Preserve the warning
                        # as DEGRADED without treating the family as a P0
                        # configuration block.
                        state = (
                            ProductionReadinessState.READY if source.status is ProductionSourceStatus.OPERATIONAL
                            else ProductionReadinessState.DEGRADED if source.status is ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION
                            else ProductionReadinessState.BLOCKED
                        )
                        reason = source.blocker
                    elif component is ProductionComponent.INDEX_BARS and source.status in {
                        ProductionSourceStatus.OPERATIONAL,
                        ProductionSourceStatus.OPERATIONAL_WITH_LIMITATION,
                    }:
                        # Family health stays factual: an incomplete official
                        # sector-index source is never recast as healthy.  The
                        # selected coverage policy permits the existing Top-3
                        # consumer only when its own benchmark and at least
                        # three evidence-derived ranked sectors are ready.
                        state, reason = _index_bars_consumer_readiness(
                            source, sector_coverage, benchmark_state=benchmark_state,
                            benchmark_reason=benchmark_reason,
                        )
                    else:
                        state = (
                            ProductionReadinessState.READY
                            if source.status is ProductionSourceStatus.OPERATIONAL
                            else ProductionReadinessState.BLOCKED
                        )
                        reason = None if state is ProductionReadinessState.READY else source.blocker
                elif component is ProductionComponent.SHARED_BRAIN:
                    state, reason = shared_brain_state, shared_brain_reason
                elif component is ProductionComponent.U16_APPLICATION:
                    state, reason = (
                        (ProductionReadinessState.READY, "U16_READ_ONLY_APPLICATION_COMPOSITION_OPERATIONAL")
                        if shared_brain_state is ProductionReadinessState.READY else
                        (shared_brain_state, shared_brain_reason)
                    )
                elif component is ProductionComponent.PIT_RECONSTRUCTION:
                    state, reason = _pit_reconstruction_readiness(shared_brain_state, shared_brain_reason)
                elif component is ProductionComponent.GOVERNED_SETUP_SOURCE:
                    state, reason = _governed_setup_source_readiness(setup_source_run)
                elif component is ProductionComponent.PAPER_SETUP_COMPOSITION:
                    state, reason = _paper_setup_composition_readiness(setup_source_run, setups)
                elif component is ProductionComponent.PAPER_BAR_COMPOSITION:
                    state, reason = _paper_bar_composition_readiness(setup_source_run, setups)
                elif component is ProductionComponent.PAPER_WORKER:
                    state, reason = (
                        (ProductionReadinessState.READY, "PAPER_WORKER_OPERATIONAL")
                        if paper_settings.enabled else
                        (ProductionReadinessState.NOT_CONFIGURED, "PAPER_TRADING_ENABLED_FALSE")
                    )
                elif component is ProductionComponent.BENCHMARK:
                    state, reason = benchmark_state, benchmark_reason
                else:
                    state, reason = (
                        (ProductionReadinessState.READY, "SUCCESSFUL_PRODUCTION_CYCLE")
                        if latest_successful_cycle is not None else
                        (ProductionReadinessState.NOT_CONFIGURED, "NO_SUCCESSFUL_PRODUCTION_CYCLE")
                    )
                components.append(ProductionComponentHealth(component, state, reason))
            return build_readiness_report(generated_at=now, components=components, sources=sources,
                p1=("SINGLE_HOST_PROCESS_LOCKS_ONLY", _ohlcv_readiness_reason(ohlcv_coverage, None)),
                p2=("PROVIDER_BATCH_SCALING_AND_DISTRIBUTED_ORCHESTRATION_NOT_IN_V1",))
        finally:
            for resource in reversed(resources):
                if resource is not repository and hasattr(resource, "close"):
                    resource.close()
            if hasattr(repository, "close"): repository.close()


def _historical_store(settings: DatabaseSettings):
    if settings.backend is DatabaseBackend.SQLITE:
        return SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
    return PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(settings))


def _shared_brain_readiness(repository, settings: DatabaseSettings, universe: CoreUniverseAnalysisStore) -> tuple[ProductionReadinessState, str]:
    """Verify the existing stored-only U15/U16 composition without a provider call.

    This validates only durable-store reachability and construction of the one
    existing application service.  It deliberately does not select a stock,
    require a current setup, or reclassify unavailable optional evidence.
    """
    from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
    from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
    from app.historical.security_master import HistoricalSecurityMasterStore
    from app.intelligence.macro.store import MacroEvidenceStore
    from app.intelligence.shared_brain_application import (
        CoreUniverseInstrumentResolver,
        SharedBrainApplicationService,
        StoredSharedBrainEvidenceAssembler,
    )
    from app.ownership.store import OwnershipObservationStore
    from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore
    from app.reliability.integrity import ReliabilityIntegrityObservationStore
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.news.store import PostgreSQLNewsEvidenceStore, SQLiteNewsEvidenceStore
    from app.taxonomy.service import TaxonomySnapshotStore

    if universe.latest_universe_snapshot() is None:
        return ProductionReadinessState.BLOCKED, "PERSISTENT_CANONICAL_UNIVERSE_UNAVAILABLE"
    path = settings.url.removeprefix("sqlite:///") if settings.backend is DatabaseBackend.SQLITE else None
    try:
        facts = SQLiteFinancialFactStore(path) if path else PostgreSQLFinancialFactStore(DatabaseConnectionFactory(settings))
        filings = SQLiteCorporateFilingsStore(path) if path else PostgreSQLCorporateFilingsStore(DatabaseConnectionFactory(settings))
        news = SQLiteNewsEvidenceStore(path) if path else PostgreSQLNewsEvidenceStore(DatabaseConnectionFactory(settings))
        historical = _historical_store(settings)
        decision_scores = SQLiteStrategyGovernanceRepository(path) if path else None
        try:
            SharedBrainApplicationService(
                resolver=CoreUniverseInstrumentResolver(universe),
                evidence_assembler=StoredSharedBrainEvidenceAssembler(
                    facts, historical,
                    filings=filings,
                    ownership_observations=OwnershipObservationStore(repository),
                    historical_security_master=HistoricalSecurityMasterStore(repository),
                    taxonomy=TaxonomySnapshotStore(repository),
                    sector_rankings=CurrentSectorRankingStore(repository),
                    macro_evidence_source=MacroEvidenceStore(repository),
                    news=news,
                    reliability_integrity_observations=ReliabilityIntegrityObservationStore(repository),
                    decision_scores=decision_scores,
                    execution_gates=decision_scores,
                    setup_assessments=decision_scores,
                    setup_opportunities=CanonicalSetupOpportunityStore(repository),
                ),
            )
        finally:
            if hasattr(historical, "close"):
                historical.close()
            if decision_scores is not None:
                decision_scores.close()
    except Exception:
        return ProductionReadinessState.BLOCKED, "PERSISTENT_SHARED_BRAIN_STORE_COMPOSITION_UNAVAILABLE"
    return ProductionReadinessState.READY, "STORED_SHARED_BRAIN_READ_COMPOSITION_OPERATIONAL"


def _pit_reconstruction_readiness(
    shared_brain_state: ProductionReadinessState, shared_brain_reason: str,
) -> tuple[ProductionReadinessState, str]:
    """Keep the genuine current-only sector limitation separate from PIT facts."""
    if shared_brain_state is not ProductionReadinessState.READY:
        return shared_brain_state, shared_brain_reason
    return (
        ProductionReadinessState.DEGRADED,
        "PIT_FINANCIAL_FACT_VINTAGE_OPERATIONAL_CURRENT_SECTOR_MEMBERSHIP_BREADTH_LIMITED",
    )


def _ohlcv_readiness_reason(coverage, source_blocker: str | None) -> str:
    """Public-safe aggregate of stored per-instrument readiness only."""
    values = (
        f"OHLCV_PER_INSTRUMENT_READY={coverage.healthy_ready}",
        f"CONFLICTED={coverage.conflicted}",
        f"INSUFFICIENT={coverage.insufficient}",
        f"STALE={coverage.stale}",
        f"UNAVAILABLE={coverage.unavailable}",
        f"UNMAPPED={coverage.unmapped}",
    )
    return ",".join(((source_blocker,) if source_blocker else ()) + values)


def _sector_universe_coverage_reason(coverage, source_blocker: str | None) -> str:
    """Public-safe disclosure of the selected partial-universe boundary."""
    excluded = "|".join(
        f"{item.sector}:{item.official_index}:{item.reason}"
        for item in coverage.excluded_sectors
    ) or "NONE"
    values = (
        *( (f"COVERAGE_STATE={coverage.state.value}",) if getattr(coverage, "state", None) is not None else () ),
        *( (f"COVERAGE_REASON={coverage.reason}",) if getattr(coverage, "reason", None) else () ),
        f"POLICY={coverage.policy_id}/{coverage.policy_version}",
        f"POLICY_FINGERPRINT={coverage.policy_fingerprint}",
        f"CANONICAL_SECTORS={coverage.canonical_sector_count}",
        f"ELIGIBLE_SECTORS={len(coverage.eligible_sectors)}",
        f"TOP3={','.join(coverage.top_sectors) or 'NONE'}",
        f"EXCLUDED_SECTORS={excluded}",
    )
    return ",".join(((source_blocker,) if source_blocker else ()) + values)


def _index_bars_consumer_readiness(source, coverage, *, benchmark_state: ProductionReadinessState,
                                   benchmark_reason: str | None) -> tuple[ProductionReadinessState, str]:
    """Translate factual partial family health into safe consumer readiness."""
    if benchmark_state is ProductionReadinessState.READY and coverage.production_safe:
        state = (
            ProductionReadinessState.READY
            if not coverage.excluded_sectors and source.status is ProductionSourceStatus.OPERATIONAL
            else ProductionReadinessState.DEGRADED
        )
        return state, _sector_universe_coverage_reason(coverage, source.blocker)
    return ProductionReadinessState.BLOCKED, _sector_universe_coverage_reason(
        coverage, benchmark_reason or source.blocker,
    )


def _nifty500_benchmark_readiness(
    historical,
    *,
    watermark: EvidenceRefreshWatermark | None,
    index_health: DataOperationsFamilyHealth,
    now: datetime,
) -> tuple[ProductionReadinessState, str | None]:
    """Read benchmark readiness from its own stored bar evidence.

    A partial sector-index family may remain operational with limitations when
    unrelated sector mappings are unresolved.  That must not hide a complete,
    current NIFTY 500 benchmark; only benchmark coverage, its latest stored
    session, and the existing U17 refresh cadence participate here.
    """
    bars = historical.latest(NIFTY_500_INDEX_ID, Timeframe.DAILY, MINIMUM_REQUIRED_DAILY_SESSIONS)
    if len(bars) < MINIMUM_REQUIRED_DAILY_SESSIONS:
        return ProductionReadinessState.BLOCKED, "NIFTY500_HISTORICAL_COVERAGE_INSUFFICIENT"
    latest = bars[-1]
    if latest.provenance.provider.casefold() != UPSTOX_PROVIDER:
        return ProductionReadinessState.BLOCKED, "NIFTY500_UPSTOX_OPERATIONAL_BAR_SOURCE_UNAVAILABLE"
    if watermark is None or watermark.accepted_through is None or not watermark.verified_from_store:
        return ProductionReadinessState.BLOCKED, "NIFTY500_INDEX_BARS_WATERMARK_UNAVAILABLE"
    if latest.end_time < watermark.accepted_through:
        return ProductionReadinessState.DEGRADED, "NIFTY500_LATEST_BAR_BEHIND_INDEX_WATERMARK"
    if index_health.status is DataOperationsHealthStatus.FAILED:
        return ProductionReadinessState.DEGRADED, "NIFTY500_INDEX_BARS_SOURCE_FAILED"
    if index_health.next_due_at is None or index_health.next_due_at <= now:
        return ProductionReadinessState.DEGRADED, "NIFTY500_INDEX_BARS_REFRESH_OVERDUE"
    return ProductionReadinessState.READY, None


def _governed_setup_source_readiness(run) -> tuple[ProductionReadinessState, str | None]:
    """Keep a valid no-opportunity scan distinct from a broken source seam."""
    if run is None:
        return ProductionReadinessState.BLOCKED, "GOVERNED_SETUP_SOURCE_RUN_REQUIRED"
    if run.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP:
        return ProductionReadinessState.READY, "READY_WITH_EXECUTABLE_SETUP"
    if run.state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP:
        return ProductionReadinessState.DEGRADED, "READY_NO_CURRENT_SETUP"
    return ProductionReadinessState.BLOCKED, run.reason or run.state.value


def _paper_setup_composition_readiness(run, setups) -> tuple[ProductionReadinessState, str | None]:
    """Report the U18 capability separately from today's opportunity set."""
    if setups:
        return ProductionReadinessState.READY, "PAPER_SETUP_COMPOSITION_OPERATIONAL"
    if run is not None and run.state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP:
        return ProductionReadinessState.READY, "PAPER_SETUP_COMPOSITION_OPERATIONAL_NO_CURRENT_SETUP"
    if run is not None and run.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP:
        return ProductionReadinessState.BLOCKED, "GOVERNED_SETUP_SOURCE_OUTPUT_MISSING"
    return ProductionReadinessState.BLOCKED, "GOVERNED_EXECUTABLE_SETUP_SOURCE_UNAVAILABLE"


def _paper_bar_composition_readiness(run, setups) -> tuple[ProductionReadinessState, str | None]:
    """The canonical resolver seam is capable even while no study is due."""
    if setups:
        return ProductionReadinessState.READY, "PAPER_BAR_COMPOSITION_OPERATIONAL"
    if run is not None and run.state is GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP:
        return ProductionReadinessState.READY, "PAPER_BAR_COMPOSITION_OPERATIONAL_NO_CURRENT_SETUP"
    if run is not None and run.state is GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP:
        return ProductionReadinessState.BLOCKED, "GOVERNED_SETUP_SOURCE_OUTPUT_MISSING"
    return ProductionReadinessState.BLOCKED, "GOVERNED_EXECUTABLE_SETUP_SOURCE_UNAVAILABLE"
