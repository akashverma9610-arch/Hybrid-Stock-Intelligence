"""Explicit local composition for the bounded stored-data real-Brain trial."""
from __future__ import annotations

from dataclasses import replace
from app.data_coverage.local import compose_coverage_records
from datetime import timedelta
from app.data_operations.financial_period_identity_repair import (
    FinancialPeriodIdentityCorrectionStore,
    FinancialPeriodIdentityProjection,
)
from app.config.freshness import FreshnessPolicyConfig
from app.domain.models import ObservationKind
from app.historical.security_master import HistoricalIntegrityStatus, HistoricalPriceIntegrityService, HistoricalSecurityMasterStore, PriceAdjustmentBasis
from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
from app.market_data.bridge import price_bar_observation
from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
from app.market_data.models import Timeframe
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.taxonomy.service import TaxonomySnapshotStore
from app.universe_analysis.service import Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator

from .service import DeterministicRealSampleSelector, RealBrainTrialService, RealBrainTrialStore


class StoredTrialObservationSource:
    """Preloads only selected IDs plus pre-existing market context from canonical bars."""

    canonical_stored_only = True

    def __init__(self, *, historical, instrument_ids: tuple[str, ...], as_of, fundamentals: FundamentalsEngineAdapter | None = None) -> None:
        self._fundamentals = fundamentals
        # These are existing canonical market-context records, never provider
        # requests.  NIFTY 500 is retained when present for stock-relative
        # strength; NIFTY 50 remains the wider market-regime input.
        ids = tuple(dict.fromkeys((*instrument_ids, "NIFTY_500", "NIFTY_50", "INDIA_VIX")))
        # Canonical historical ingestion has already validated bar quality.  At
        # this rehydration boundary we retain explicit validation so existing
        # technical engines can consume it; analysis-time PIT is still enforced
        # independently by StockDiagnosticInputAssembler.
        validator = ObservationValidator(FreshnessEngine(FreshnessPolicyConfig(
            {ObservationKind.PRICE_BAR: timedelta(days=3650)}, timedelta(days=3650),
        )))
        values = []
        for instrument_id in ids:
            for bar in historical.latest(instrument_id, Timeframe.DAILY, 300, as_of=as_of):
                observation = price_bar_observation(bar)
                values.append(observation.with_validation(validator.validate(
                    observation, evaluated_timestamp=bar.provenance.received_at,
                )))
        if fundamentals is not None:
            for instrument_id in instrument_ids:
                values.extend(fundamentals.build(instrument_id, as_of=as_of).snapshot.observations)
        self._values = tuple(sorted(values, key=lambda item: (item.provenance.market_timestamp, item.id)))

    def observations_as_of(self, at):
        return tuple(item for item in self._values if item.provenance.market_timestamp <= at and item.provenance.retrieved_timestamp <= at)

    def financial_diagnostic_input(self, instrument_id, as_of):
        return self._fundamentals.diagnostic_input(instrument_id, as_of=as_of) if self._fundamentals is not None else None


class LocalRealBrainTrialService:
    """Local-only convenience boundary; it opens no provider/network client."""

    def __init__(self, settings: DatabaseSettings) -> None:
        self._settings = settings

    def run(self, *, sample_size: int = 40, frozen_cohort: bool = False, frozen_cohort_trial_id: str | None = None):
        repository = create_core_api_snapshot_repository(self._settings)
        historical = self._historical_store()
        facts, filings = self._financial_stores()
        try:
            universe_store = CoreUniverseAnalysisStore(repository); snapshot = universe_store.latest_universe_snapshot()
            if snapshot is None:
                raise ValueError("REAL_BRAIN_TRIAL_REQUIRES_UNIVERSE_SNAPSHOT")
            taxonomy = TaxonomySnapshotStore(repository)
            instruments = _taxonomy_enriched_instruments(universe_store.instruments_as_of(snapshot.as_of), taxonomy, snapshot.as_of)
            sectors = {instrument.instrument_id: instrument.sector for instrument in instruments if instrument.sector}
            selector = DeterministicRealSampleSelector(); trial_store = RealBrainTrialStore(repository)
            prior = None
            if frozen_cohort_trial_id:
                prior = trial_store.get_trial(frozen_cohort_trial_id)
                if prior is None:
                    raise ValueError("FROZEN_COHORT_TRIAL_NOT_FOUND")
            elif frozen_cohort:
                prior = trial_store.latest_trial(sample_size=sample_size)
                if prior is None:
                    raise ValueError("FROZEN_COHORT_TRIAL_REQUIRED")
            # A later immutable import with the same official universe content
            # may advance the point-in-time boundary for newly retrieved
            # evidence.  The frozen cohort remains the exact prior 40 IDs;
            # only a changed universe checksum is a rebase.
            if prior is not None and prior.universe_checksum != snapshot.checksum:
                raise ValueError("FROZEN_COHORT_UNIVERSE_MISMATCH")
            selection = selector.select(snapshot=snapshot, instruments=instruments, sample_size=sample_size, sectors=sectors)
            if prior is not None:
                by_id = {item.instrument_id: item for item in instruments}
                selection = selection.__class__(tuple(by_id[item] for item in prior.selected_instrument_ids), "FROZEN_COHORT_FROM_PRIOR_REAL_BRAIN_TRIAL")
            coverage = compose_coverage_records(repository=repository, historical=historical, snapshot=snapshot, instruments=selection.instruments, persist=True, facts=facts, filings=filings)
            coverage_by_instrument = {item.instrument_id: item for item in coverage}
            master = HistoricalSecurityMasterStore(repository); integrity = {}
            for instrument in selection.instruments:
                bars = historical.latest(instrument.instrument_id, Timeframe.DAILY, 300, as_of=snapshot.as_of)
                actions = master.actions_as_of(instrument.instrument_id, snapshot.as_of)
                if bars:
                    integrity[instrument.instrument_id] = _trial_price_integrity(
                        instrument_id=instrument.instrument_id, bars=bars, actions=actions, as_of=snapshot.as_of,
                    )
            source = StoredTrialObservationSource(
                historical=historical, instrument_ids=tuple(item.instrument_id for item in selection.instruments),
                as_of=snapshot.as_of,
                fundamentals=FundamentalsEngineAdapter(
                    facts, filings,
                    FinancialPeriodIdentityProjection(FinancialPeriodIdentityCorrectionStore(repository)),
                ),
            )
            # Relative strength for the bounded real-data trial is explicitly
            # stock-vs-NIFTY 500.  If that exact stored benchmark is not
            # eligible at the snapshot boundary, rule #6 remains partial; it
            # must never silently substitute NIFTY 50.
            benchmark_instrument_id = "NIFTY_500"
            return RealBrainTrialService(
                selector=selector, assembler=StockDiagnosticInputAssembler(source),
                runner=Canonical61DiagnosticRunner(benchmark_instrument_id=benchmark_instrument_id), store=trial_store,
            ).run(snapshot=snapshot, instruments=instruments, coverage_by_instrument=coverage_by_instrument, source=source,
                  sample_size=sample_size, sectors=sectors, integrity_by_instrument=integrity,
                  frozen_cohort_instrument_ids=prior.selected_instrument_ids if prior else None,
                  frozen_cohort_reference=prior.trial_id if prior else None)
        finally:
            if hasattr(historical, "close"): historical.close()
            if hasattr(repository, "close"): repository.close()

    def _historical_store(self):
        if self._settings.backend is DatabaseBackend.SQLITE:
            return SQLiteHistoricalBarStore(self._settings.url.removeprefix("sqlite:///"))
        return PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(self._settings))

    def _financial_stores(self):
        if self._settings.backend is DatabaseBackend.SQLITE:
            path = self._settings.url.removeprefix("sqlite:///")
            return SQLiteFinancialFactStore(path), SQLiteCorporateFilingsStore(path)
        connections = DatabaseConnectionFactory(self._settings)
        return PostgreSQLFinancialFactStore(connections), PostgreSQLCorporateFilingsStore(connections)


def _taxonomy_enriched_instruments(instruments, taxonomy: TaxonomySnapshotStore, as_of):
    """Attach only PIT-eligible canonical sector evidence to existing identities.

    This is a composition detail, not a sector model: a missing or future
    classification leaves the original instrument unchanged.
    """
    classifications = taxonomy.classifications_as_of((item.instrument_id for item in instruments), as_of)
    values = []
    for instrument in instruments:
        classification = classifications.get(instrument.instrument_id)
        if classification is None:
            values.append(instrument)
            continue
        values.append(replace(
            instrument,
            sector=classification.sector or instrument.sector,
            industry=classification.industry or instrument.industry,
        ))
    return tuple(values)


def _trial_price_integrity(*, instrument_id, bars, actions, as_of):
    """Apply the existing real-data coverage policy to the trial audit field.

    Raw bars may be internally coherent while still lacking an official
    corporate-action provenance source.  The bounded trial must retain that
    distinction as PARTIAL rather than presenting raw secondary history as
    fully corporate-action-safe.
    """
    assessment = HistoricalPriceIntegrityService().assess(
        instrument_id=instrument_id, bars=bars, actions=actions, as_of=as_of,
        basis=PriceAdjustmentBasis.RAW,
    )
    if not actions:
        return replace(
            assessment, status=HistoricalIntegrityStatus.PARTIAL,
            warnings=tuple(sorted(set((*assessment.warnings, "CORPORATE_ACTION_SOURCE_REQUIRED")))),
        )
    return assessment
