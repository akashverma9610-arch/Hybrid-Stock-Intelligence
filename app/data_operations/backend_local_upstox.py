"""Private, bounded real-portfolio Upstox OHLCV activation composition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable
from uuid import uuid4

from app.connections.credentials import CredentialStore
from app.data_operations.models import EvidenceDataFamily, EvidenceRefreshMode, EvidenceRefreshOutcome, EvidenceRefreshRequest
from app.data_operations.upstox import UpstoxIndexBarsRefreshJob, UpstoxOhlcvRefreshJob
from app.market_data.historical import HistoricalBarStore
from app.market_data.models import Timeframe
from app.market_data.ohlcv_readiness import OhlcvReadinessService
from app.market_data.upstox import UPSTOX_PROVIDER
from app.portfolio.canonical_diagnostics_orchestration import PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
from app.universe_analysis.service import CoreUniverseAnalysisStore


BENCHMARK_INSTRUMENT_IDS = ("NIFTY_50", "NIFTY_500")
REAL_PORTFOLIO_OHLCV_TARGETS = (*PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS, *BENCHMARK_INSTRUMENT_IDS)
# These are the only official index histories currently preventing otherwise
# governed sector ranking coverage.  This local operation deliberately has no
# caller-selected symbols, provider, or credential input.
SECTOR_ROTATION_INDEX_TARGETS = (
    "NSE_SECTOR_INDEX:CAPITAL_GOODS",
    "NSE_SECTOR_INDEX:CONSTRUCTION",
    "NSE_SECTOR_INDEX:CONSUMER_SERVICES",
    "NSE_SECTOR_INDEX:POWER",
)


@dataclass(frozen=True, slots=True)
class BackendLocalOhlcvTargetRun:
    canonical_instrument_id: str
    mapping_status: str
    session_count_before: int
    session_count_after: int
    latest_session: datetime | None
    accepted_count: int
    duplicate_count: int
    conflict_count: int
    readiness: str
    blocker: str | None


@dataclass(frozen=True, slots=True)
class BackendLocalOhlcvActivationResult:
    requested_at: datetime
    completed_at: datetime
    first_run: tuple[BackendLocalOhlcvTargetRun, ...]
    second_run: tuple[BackendLocalOhlcvTargetRun, ...]


class BackendLocalRealPortfolioOhlcvActivation:
    """Run only the approved seven IDs through existing immutable boundaries."""

    def __init__(
        self,
        *,
        credential_store: CredentialStore,
        universe: CoreUniverseAnalysisStore,
        historical: HistoricalBarStore,
        equity_job: UpstoxOhlcvRefreshJob,
        index_job: UpstoxIndexBarsRefreshJob,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._credentials = credential_store
        self._universe = universe
        self._historical = historical
        self._equity_job = equity_job
        self._index_job = index_job
        self._clock = clock

    def run_twice(self) -> BackendLocalOhlcvActivationResult:
        at = self._clock().astimezone(UTC)
        first = self._run("first", at)
        second = self._run("second", at)
        return BackendLocalOhlcvActivationResult(at, self._clock().astimezone(UTC), first, second)

    def _run(self, ordinal: str, at: datetime) -> tuple[BackendLocalOhlcvTargetRun, ...]:
        results = []
        for instrument_id in REAL_PORTFOLIO_OHLCV_TARGETS:
            family = EvidenceDataFamily.OHLCV if instrument_id in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS else EvidenceDataFamily.INDEX_BARS
            before = self._canonical_session_count(instrument_id)
            outcome = self._refresh(instrument_id, family, ordinal, at)
            # ``requested_at`` remains immutable request lineage.  Evidence
            # written by this operation was not known at that earlier instant,
            # so readiness must use a distinct cutoff captured after writes.
            visibility_cutoff = self._clock().astimezone(UTC)
            mapping = self._universe.provider_mapping(
                canonical_instrument_id=instrument_id, provider=UPSTOX_PROVIDER, as_of=visibility_cutoff,
            )
            readiness = OhlcvReadinessService(self._historical).assess(
                instrument_id, as_of=visibility_cutoff, mapping_available=mapping is not None,
                required_latest_at=outcome.accepted_through,
            )
            results.append(BackendLocalOhlcvTargetRun(
                instrument_id,
                "EXACT_MAPPING_AVAILABLE" if mapping is not None else "EXACT_MAPPING_UNAVAILABLE",
                before,
                self._canonical_session_count(instrument_id, as_of=visibility_cutoff),
                readiness.latest_bar_at,
                outcome.accepted_count,
                outcome.duplicate_count,
                outcome.conflict_count,
                readiness.status.value,
                outcome.error_summary or (None if readiness.ready else readiness.reason),
            ))
        return tuple(results)

    def _canonical_session_count(self, instrument_id: str, *, as_of: datetime | None = None) -> int:
        return len(self._historical.range(
            instrument_id, Timeframe.DAILY,
            datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC), as_of=as_of,
        ))

    def _refresh(self, instrument_id: str, family: EvidenceDataFamily, ordinal: str, at: datetime) -> EvidenceRefreshOutcome:
        request = EvidenceRefreshRequest(
            f"backend-local-real-portfolio-ohlcv:{ordinal}:{instrument_id}:{uuid4().hex}",
            family, EvidenceRefreshMode.INCREMENTAL, at, at, None, 2,
        )
        if family is EvidenceDataFamily.OHLCV:
            return self._equity_job.refresh_selected(request, canonical_instrument_ids=frozenset({instrument_id}))
        return self._index_job.refresh_selected(request, canonical_instrument_ids=frozenset({instrument_id}))


class BackendLocalSectorRotationIndexCoverageActivation:
    """Refresh only the approved official sector-index coverage gap locally."""

    def __init__(
        self,
        *,
        universe: CoreUniverseAnalysisStore,
        historical: HistoricalBarStore,
        index_job: UpstoxIndexBarsRefreshJob,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._universe = universe
        self._historical = historical
        self._index_job = index_job
        self._clock = clock

    def run_twice(self) -> BackendLocalOhlcvActivationResult:
        at = self._clock().astimezone(UTC)
        first = self._run("first", at)
        second = self._run("second", at)
        return BackendLocalOhlcvActivationResult(at, self._clock().astimezone(UTC), first, second)

    def _run(self, ordinal: str, at: datetime) -> tuple[BackendLocalOhlcvTargetRun, ...]:
        values: list[BackendLocalOhlcvTargetRun] = []
        for instrument_id in SECTOR_ROTATION_INDEX_TARGETS:
            before = self._session_count(instrument_id)
            request = EvidenceRefreshRequest(
                f"backend-local-sector-rotation-index:{ordinal}:{instrument_id}:{uuid4().hex}",
                EvidenceDataFamily.INDEX_BARS, EvidenceRefreshMode.INCREMENTAL, at, at, None, 2,
            )
            outcome = self._index_job.refresh_selected(request, canonical_instrument_ids=frozenset({instrument_id}))
            visibility_cutoff = self._clock().astimezone(UTC)
            mapping = self._universe.provider_mapping(
                canonical_instrument_id=instrument_id, provider=UPSTOX_PROVIDER, as_of=visibility_cutoff,
            )
            readiness = OhlcvReadinessService(self._historical).assess(
                instrument_id, as_of=visibility_cutoff, mapping_available=mapping is not None,
                required_latest_at=outcome.accepted_through,
            )
            values.append(BackendLocalOhlcvTargetRun(
                instrument_id,
                "EXACT_MAPPING_AVAILABLE" if mapping is not None else "EXACT_MAPPING_UNAVAILABLE",
                before, self._session_count(instrument_id, as_of=visibility_cutoff), readiness.latest_bar_at,
                outcome.accepted_count, outcome.duplicate_count, outcome.conflict_count, readiness.status.value,
                outcome.error_summary or (None if readiness.ready else readiness.reason),
            ))
        return tuple(values)

    def _session_count(self, instrument_id: str, *, as_of: datetime | None = None) -> int:
        return len(self._historical.range(
            instrument_id, Timeframe.DAILY, datetime.min.replace(tzinfo=UTC),
            datetime.max.replace(tzinfo=UTC), as_of=as_of,
        ))


def secure_upstox_token_reader(credentials: CredentialStore) -> Callable[[], str | None]:
    """Return a private reader; callers never receive or serialize its secret."""
    return lambda: credentials.load("upstox").get("access_token")


def build_backend_local_real_portfolio_ohlcv_activation(*, database_settings, credential_store: CredentialStore) -> BackendLocalRealPortfolioOhlcvActivation:
    """Compose from the backend's database and credential boundaries only."""
    from app.market_data.historical import PostgreSQLHistoricalBarStore, SQLiteHistoricalBarStore
    from app.market_data.upstox import load_upstox_nse_bod_instrument_master
    from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
    from app.storage.database import DatabaseBackend, DatabaseConnectionFactory
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.taxonomy.nse_sector_indices import NseSectorIndexMapping

    repository = create_core_api_snapshot_repository(database_settings)
    historical = (
        SQLiteHistoricalBarStore(database_settings.url.removeprefix("sqlite:///"))
        if database_settings.backend is DatabaseBackend.SQLITE
        else PostgreSQLHistoricalBarStore(DatabaseConnectionFactory(database_settings))
    )
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

    master = None
    def cached_master():
        nonlocal master
        if master is None:
            master = load_upstox_nse_bod_instrument_master()
        return master

    token_reader = secure_upstox_token_reader(credential_store)
    return BackendLocalRealPortfolioOhlcvActivation(
        credential_store=credential_store,
        universe=universe,
        historical=historical,
        equity_job=UpstoxOhlcvRefreshJob(
            universe_store=universe, historical_store=historical,
            token_reader=token_reader, master_loader=cached_master,
        ),
        index_job=UpstoxIndexBarsRefreshJob(
            sector_mappings_loader=sector_mappings, universe_store=universe, historical_store=historical,
            token_reader=token_reader, master_loader=cached_master,
        ),
    )


def build_backend_local_sector_rotation_index_coverage_activation(*, database_settings, credential_store: CredentialStore) -> BackendLocalSectorRotationIndexCoverageActivation:
    """Compose the fixed official-index operation inside the serving backend."""
    portfolio_operation = build_backend_local_real_portfolio_ohlcv_activation(
        database_settings=database_settings, credential_store=credential_store,
    )
    return BackendLocalSectorRotationIndexCoverageActivation(
        universe=portfolio_operation._universe,
        historical=portfolio_operation._historical,
        index_job=portfolio_operation._index_job,
    )


__all__ = (
    "BENCHMARK_INSTRUMENT_IDS", "BackendLocalOhlcvActivationResult",
    "BackendLocalOhlcvTargetRun", "BackendLocalRealPortfolioOhlcvActivation",
    "BackendLocalSectorRotationIndexCoverageActivation", "REAL_PORTFOLIO_OHLCV_TARGETS",
    "SECTOR_ROTATION_INDEX_TARGETS", "build_backend_local_real_portfolio_ohlcv_activation",
    "build_backend_local_sector_rotation_index_coverage_activation", "secure_upstox_token_reader",
)
