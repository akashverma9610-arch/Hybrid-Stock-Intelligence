"""Local persistent-store coverage composition without provider/network I/O."""
from __future__ import annotations

from datetime import UTC, datetime

from app.data_coverage.models import DataCoverageDomain, DataCoverageStatus, DomainCoverage
from app.data_coverage.service import DataCoverageService
from app.data_coverage.store import DataCoverageSnapshotStore
from app.historical.security_master import HistoricalSecurityMasterStore, HistoricalIntegrityStatus, HistoricalPriceIntegrityService, PriceAdjustmentBasis
from app.filings.models import FilingType
from app.filings.store import PostgreSQLCorporateFilingsStore, SQLiteCorporateFilingsStore
from app.fundamentals.adapter import FundamentalsEngineAdapter
from app.fundamentals.store import PostgreSQLFinancialFactStore, SQLiteFinancialFactStore
from app.market_data.models import FreshnessState
from app.market_data.store import CoreSnapshotQuoteStore
from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
from app.market_data.models import Timeframe
from app.storage.database import DatabaseBackend, DatabaseConnectionFactory, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.taxonomy.service import TaxonomySnapshotStore
from app.universe_analysis.service import CoreUniverseAnalysisStore


class LocalCoverageReportService:
    """Measures only already-persisted evidence; absent stores remain missing."""
    def __init__(self, settings: DatabaseSettings, *, clock=lambda: datetime.now(UTC)) -> None:
        self._settings, self._clock = settings, clock

    def report(self):
        repository = create_core_api_snapshot_repository(self._settings)
        historical = self._historical_store()
        facts, filings = self._financial_stores()
        try:
            universe = CoreUniverseAnalysisStore(repository); snapshot = universe.latest_universe_snapshot()
            if snapshot is None:
                return None
            records = compose_coverage_records(
                repository=repository, historical=historical, snapshot=snapshot,
                instruments=universe.instruments_as_of(snapshot.as_of), persist=True,
                facts=facts, filings=filings,
            )
            service = DataCoverageService()
            result = service.summarize(universe_snapshot_id=snapshot.snapshot_id, as_of=snapshot.as_of, records=tuple(records))
            persistent = DataCoverageSnapshotStore(repository)
            if persistent.get_summary(result.summary_id) is None:
                persistent.save_summary(result)
            return result
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


def compose_coverage_records(*, repository, historical, snapshot, instruments, persist: bool = False, facts=None, filings=None):
    """Compose one or many coverage records from stores only; never fetches data.

    It is deliberately reusable by the bounded real-Brain trial so that trial
    coverage and the normal local coverage report cannot disagree.
    """
    taxonomy = TaxonomySnapshotStore(repository); quotes = CoreSnapshotQuoteStore(repository); service = DataCoverageService()
    historical_master = HistoricalSecurityMasterStore(repository)
    identities = {item.canonical_instrument_id: item for item in historical_master.identities_as_of(snapshot.as_of)}
    memberships = {item.instrument_id for item in historical_master.memberships(snapshot.snapshot_id) if item.known_at <= snapshot.as_of and item.effective_from <= snapshot.as_of and (item.effective_to is None or snapshot.as_of <= item.effective_to)}
    snapshot_ids = set(snapshot.instrument_ids); records = []; persistent = DataCoverageSnapshotStore(repository)
    # Benchmark context is a shared canonical series.  Check it once rather
    # than repeatedly loading it per stock and accept the existing NIFTY 500
    # preferred identifier or the long-standing NIFTY 50 fallback.
    benchmark = historical.latest("NIFTY_500", Timeframe.DAILY, 252, as_of=snapshot.as_of)
    if not benchmark:
        benchmark = historical.latest("NIFTY_50", Timeframe.DAILY, 252, as_of=snapshot.as_of)
    market_status = DataCoverageStatus.READY if len(benchmark) >= 252 else DataCoverageStatus.PARTIAL if benchmark else DataCoverageStatus.MISSING
    for instrument in instruments:
        if instrument.instrument_id not in snapshot_ids: continue
        classification = taxonomy.classification_as_of(instrument.instrument_id, snapshot.as_of)
        quote = quotes.latest_quote(instrument.instrument_id)
        history = historical.latest(instrument.instrument_id, Timeframe.DAILY, 252, as_of=snapshot.as_of)
        identity = identities.get(instrument.instrument_id)
        actions = historical_master.actions_as_of(instrument.instrument_id, snapshot.as_of)
        financial_facts = facts.facts(instrument.instrument_id, as_of=snapshot.as_of, limit=500) if facts else ()
        filing_values = filings.list(instrument_id=instrument.instrument_id, as_of=snapshot.as_of, limit=500) if filings else ()
        fundamental_status = DataCoverageStatus.MISSING
        if financial_facts:
            # Existing adapter owns the exact consolidated-preferred and
            # standalone-fallback completeness semantics used by diagnostics.
            completeness = FundamentalsEngineAdapter(facts, filings).build(instrument.instrument_id, as_of=snapshot.as_of).completeness
            fundamental_status = DataCoverageStatus.READY if completeness == "COMPLETE" else DataCoverageStatus.PARTIAL
        filings_status = DataCoverageStatus.READY if filing_values else DataCoverageStatus.MISSING
        integrity = HistoricalPriceIntegrityService().assess(instrument_id=instrument.instrument_id, bars=history, actions=actions, as_of=snapshot.as_of, basis=PriceAdjustmentBasis.RAW) if history and actions else None
        taxonomy_status = DataCoverageStatus.READY if classification and classification.industry and classification.sector and classification.super_sector else DataCoverageStatus.MISSING
        quote_status = (DataCoverageStatus.READY if quote.freshness.state is FreshnessState.FRESH else DataCoverageStatus.STALE) if quote else DataCoverageStatus.MISSING
        historical_status = DataCoverageStatus.READY if len(history) >= 252 else DataCoverageStatus.PARTIAL if history else DataCoverageStatus.MISSING
        domains = (
            DomainCoverage(DataCoverageDomain.IDENTITY, DataCoverageStatus.READY, instrument.data_as_of, (instrument.instrument_id,)),
            DomainCoverage(DataCoverageDomain.SECTOR_INDUSTRY, taxonomy_status, classification.as_of if classification else None, (classification.classification_id,) if classification else (), None if classification else "TAXONOMY_SOURCE_REQUIRED"),
            DomainCoverage(DataCoverageDomain.CURRENT_QUOTES, quote_status, quote.provenance.received_at if quote else None, (quote.quote_id,) if quote else (), None if quote else "NO_CANONICAL_QUOTE"),
            DomainCoverage(DataCoverageDomain.HISTORICAL_OHLCV, historical_status, history[-1].end_time if history else None, tuple(item.bar_id for item in history), "INSUFFICIENT_LOOKBACK" if history and len(history) < 252 else "NO_HISTORICAL_BARS" if not history else None),
            DomainCoverage(DataCoverageDomain.MARKET_CONTEXT, market_status, benchmark[-1].end_time if benchmark else None, tuple(item.bar_id for item in benchmark), "NIFTY500_OR_NIFTY50_CONTEXT_UNAVAILABLE" if not benchmark else "BENCHMARK_LOOKBACK_INSUFFICIENT" if len(benchmark) < 252 else None),
            DomainCoverage(DataCoverageDomain.HISTORICAL_MEMBERSHIP, DataCoverageStatus.READY if instrument.instrument_id in memberships else DataCoverageStatus.MISSING, snapshot.as_of if instrument.instrument_id in memberships else None, (), None if instrument.instrument_id in memberships else "HISTORICAL_MEMBERSHIP_SOURCE_REQUIRED"),
            DomainCoverage(DataCoverageDomain.SYMBOL_HISTORY, DataCoverageStatus.READY if identity else DataCoverageStatus.MISSING, identity.as_of if identity else None, (identity.identity_id,) if identity else (), None if identity else "HISTORICAL_SECURITY_MASTER_SOURCE_REQUIRED"),
            DomainCoverage(DataCoverageDomain.CORPORATE_ACTIONS, DataCoverageStatus.READY if actions else DataCoverageStatus.MISSING, actions[-1].as_of if actions else None, tuple(item.action_id for item in actions), None if actions else "CORPORATE_ACTION_SOURCE_REQUIRED"),
            DomainCoverage(DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY, DataCoverageStatus.READY if integrity and integrity.status is HistoricalIntegrityStatus.VALID else DataCoverageStatus.PARTIAL if integrity or history else DataCoverageStatus.MISSING, integrity.as_of if integrity else history[-1].end_time if history else None, (integrity.assessment_id,) if integrity else (), ",".join(integrity.warnings) if integrity and integrity.warnings else "CORPORATE_ACTION_SOURCE_REQUIRED" if history and not integrity else "PRICE_ADJUSTMENT_SOURCE_REQUIRED" if not integrity else None),
            DomainCoverage(DataCoverageDomain.FUNDAMENTALS, fundamental_status, max((fact.available_at for fact in financial_facts), default=None), tuple(fact.fact_id for fact in financial_facts), "FINANCIAL_FACTS_INCOMPLETE" if financial_facts and fundamental_status is DataCoverageStatus.PARTIAL else "OFFICIAL_FINANCIAL_RESULTS_REQUIRED" if not financial_facts else None),
            DomainCoverage(DataCoverageDomain.FILINGS, filings_status, max((filing.announced_at for filing in filing_values), default=None), tuple(filing.filing_id for filing in filing_values), "OFFICIAL_FILINGS_REQUIRED" if not filing_values else None),
            # A Reg 31 filing is primary ownership evidence, but no such
            # document is silently converted into promoter-pledge data.
            DomainCoverage(DataCoverageDomain.OWNERSHIP, DataCoverageStatus.READY if any(filing.filing_type is FilingType.SHAREHOLDING_PATTERN for filing in filing_values) else DataCoverageStatus.MISSING, max((filing.announced_at for filing in filing_values if filing.filing_type is FilingType.SHAREHOLDING_PATTERN), default=None), tuple(filing.filing_id for filing in filing_values if filing.filing_type is FilingType.SHAREHOLDING_PATTERN), "OFFICIAL_REG31_SHAREHOLDING_REQUIRED" if not any(filing.filing_type is FilingType.SHAREHOLDING_PATTERN for filing in filing_values) else None),
        )
        record = service.record(universe_snapshot_id=snapshot.snapshot_id, instrument_id=instrument.instrument_id, as_of=snapshot.as_of, domains=domains)
        if persist and persistent.get_record(record.coverage_id) is None:
            persistent.save_record(record)
        records.append(record)
    return tuple(records)
