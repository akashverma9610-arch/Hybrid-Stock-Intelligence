"""Local persistent-store readiness composition for explicit CLI use."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.data_sources.service import DataSourceCompositionService, SourceCompositionSettings
from app.runtime.cycle import RuntimeMode
from app.storage.database import DatabaseReadiness, DatabaseReadinessProbe, DatabaseConnectionFactory, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.market_data.store import CoreSnapshotQuoteStore
from app.universe_analysis.readiness import DataReadinessReport, DataReadinessService
from app.universe_analysis.service import CoreUniverseAnalysisStore


@dataclass(frozen=True, slots=True)
class LocalReadinessReport:
    database: DatabaseReadiness
    universe: DataReadinessReport


class LocalDataReadinessService:
    """Reads the selected persistent database and declared source settings.

    It does not call a provider, keyring, network client, or diagnostics.
    """
    def __init__(self, settings: DatabaseSettings, *, clock=lambda: datetime.now(UTC)) -> None:
        self._settings, self._clock = settings, clock

    def report(self) -> LocalReadinessReport:
        repository = create_core_api_snapshot_repository(self._settings)
        try:
            # Opening the repository creates a local SQLite parent/schema before
            # probing it, so a first status check is truthful and restart-safe.
            database = DatabaseReadinessProbe(DatabaseConnectionFactory(self._settings)).check()
            store = CoreUniverseAnalysisStore(repository)
            quotes = CoreSnapshotQuoteStore(repository)
            snapshot = store.latest_universe_snapshot()
            instruments = store.instruments_as_of(snapshot.as_of) if snapshot else ()
            sources = DataSourceCompositionService.from_settings(SourceCompositionSettings.from_environment()).readiness(mode=RuntimeMode.STORED_DATA)
            readiness = DataReadinessService(source_report=sources, quote_store=quotes, clock=self._clock).assess(
                snapshot=snapshot, instruments=instruments, as_of=snapshot.as_of if snapshot else self._clock(),
            )
            return LocalReadinessReport(database, readiness)
        finally:
            if hasattr(repository, "close"):
                repository.close()
