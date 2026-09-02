"""Stored-data activation adapter for the existing current sector route.

It does not introduce a sector-rotation formula.  Relative strength is the
existing Mansfield helper and ranking is the existing PreBreakout sector scan.
The module only composes current official constituents with canonical stored
bars and exposes an explicit, bounded backfill plan.
"""
from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from time import sleep
from typing import Callable, Iterable, Sequence

from app.market_data.historical import HistoricalIngestionService
from app.market_data.index_close_series import (
    CloseSeriesPoint,
    IndexCloseSeriesStore,
    close_series_from_bars,
    close_series_from_observations,
)
from app.market_data.models import AdjustmentStatus, Exchange, HistoricalBarsRequest, InstrumentIdentity, InstrumentType, MarketDataError, ProviderInstrumentMapping, Timeframe
from app.market_data.upstox import UPSTOX_PROVIDER, UpstoxHistoricalProvider, UpstoxInstrumentRecord
from app.market_data.upstox_population import resolve_upstox_equity_mapping
from app.market_data.upstox_sector_indices import NIFTY_500_INDEX_ID, _sector_index_id
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.historical.guard import manifest_fingerprint
from app.strategies.pre_breakout.service import PreBreakoutConfig, PreBreakoutEngine, SectorBreadth, SectorRelativeStrength, mansfield_relative_strength
from app.taxonomy.nse_sector_indices import NseSectorIndexConstituent, NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


CURRENT_BREADTH_MINIMUM_HISTORY = 200
CURRENT_BREADTH_PREFERRED_HISTORY = 320
SECTOR_RS_LOOKBACKS = (20, 60, 120)


@dataclass(frozen=True, slots=True)
class CurrentSectorRelativeStrength:
    sector: str
    official_index: str
    canonical_sessions: int
    recent_upstox_sessions: int
    official_close_sessions: int
    rs20: Decimal | None
    rs60: Decimal | None
    rs120: Decimal | None
    mansfield: Decimal | None
    exclusion_reason: str | None


@dataclass(frozen=True, slots=True)
class CurrentConstituentResolution:
    sector: str
    official_index: str
    symbol: str
    isin: str
    instrument_id: str | None
    identity_method: str | None
    mapping_present: bool
    resolution_status: str


@dataclass(frozen=True, slots=True)
class CurrentConstituentHistoryCoverage:
    sector: str
    official_index: str
    symbol: str
    isin: str
    instrument_id: str | None
    sessions: int
    at_least_20: bool
    at_least_60: bool
    at_least_120: bool
    at_least_200: bool
    at_least_252: bool
    at_least_320: bool
    close_ready: bool
    volume_ready: bool


@dataclass(frozen=True, slots=True)
class CurrentSectorBreadthResult:
    sector: str
    official_index: str
    constituent_count: int
    evaluable_50: int
    above_50: int
    above_50_pct: Decimal | None
    evaluable_200: int
    above_200: int
    above_200_pct: Decimal | None
    coverage_pct: Decimal
    status: str
    warning: str | None = None


@dataclass(frozen=True, slots=True)
class SectorBackfillTarget:
    sector: str
    official_index: str
    instrument: InstrumentIdentity
    sessions: int
    reason: str


@dataclass(frozen=True, slots=True)
class SectorBackfillSectorSummary:
    """Stored-only current-membership counts for one chosen plan sector."""

    sector: str
    official_index: str
    current_constituents: int
    already_sufficient: int
    need_backfill: int
    unresolved: int


@dataclass(frozen=True, slots=True)
class SectorBackfillPlan:
    rs_ready_only: bool
    rs_ready_sectors: tuple[str, ...]
    constituents_before_dedup: int
    unique_constituents: int
    total_constituents: int
    already_sufficient: int
    need_backfill: tuple[SectorBackfillTarget, ...]
    unresolved: int
    by_sector: tuple[SectorBackfillSectorSummary, ...]

    @property
    def estimated_provider_calls(self) -> int:
        return len(self.need_backfill)


@dataclass(frozen=True, slots=True)
class CurrentSectorRotationReport:
    generated_at: datetime
    latest_completed_session: datetime | None
    benchmark_sessions: int
    relative_strength: tuple[CurrentSectorRelativeStrength, ...]
    constituents: tuple[CurrentConstituentResolution, ...]
    coverage: tuple[CurrentConstituentHistoryCoverage, ...]
    breadth: tuple[CurrentSectorBreadthResult, ...]
    ranked_sectors: tuple[str, ...]
    top3: tuple[str, ...]
    plan: SectorBackfillPlan
    pre_breakout_technical_ready: int
    pre_breakout_full_ready: int
    inflection_ready: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CurrentSectorRankingArtifact:
    """Immutable, PIT-safe record of one already-calculated sector ranking."""

    ranking_id: str
    ranking_as_of: datetime
    latest_completed_session: datetime | None
    benchmark_identity: str
    ranking_policy_version: str
    report: CurrentSectorRotationReport
    fingerprint: str

    @classmethod
    def create(cls, report: CurrentSectorRotationReport) -> "CurrentSectorRankingArtifact":
        values = {
            "ranking_as_of": report.generated_at, "latest_completed_session": report.latest_completed_session,
            "benchmark_identity": NIFTY_500_INDEX_ID, "ranking_policy_version": "current-sector-rotation-v1",
            "report": asdict(report),
        }
        fingerprint = manifest_fingerprint(**values)
        return cls(
            ranking_id=f"current-sector-ranking:{fingerprint[:32]}", ranking_as_of=report.generated_at,
            latest_completed_session=report.latest_completed_session, benchmark_identity=NIFTY_500_INDEX_ID,
            ranking_policy_version="current-sector-rotation-v1", report=report, fingerprint=fingerprint,
        )


class CurrentSectorRankingStore:
    """Immutable snapshot store and PIT reader for current sector rankings."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: CurrentSectorRankingArtifact) -> CurrentSectorRankingArtifact:
        existing = self._repository.get_snapshot(value.ranking_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("CURRENT_SECTOR_RANKING_IMMUTABLE_CONFLICT")
            return existing.payload
        self._repository.save_snapshot(CoreApiSnapshot(
            value.ranking_id, CoreApiSnapshotFamily.CURRENT_SECTOR_RANKING, "v1",
            "current-sector-ranking-v1", value.fingerprint, value.ranking_as_of, value,
        ))
        return value

    def latest(self, *, as_of: datetime) -> CurrentSectorRankingArtifact | None:
        values: list[CoreApiSnapshot] = []; offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.CURRENT_SECTOR_RANKING, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                break
            offset += len(page)
        eligible = tuple(
            item.payload for item in values
            if isinstance(item.payload, CurrentSectorRankingArtifact)
            and item.created_at <= as_of and item.payload.ranking_as_of <= as_of
        )
        return max(eligible, key=lambda item: (item.ranking_as_of, item.ranking_id)) if eligible else None


@dataclass(frozen=True, slots=True)
class SectorConstituentBackfillReport:
    planned: int
    provider_requests: int
    accepted: int
    duplicates: int
    conflicts: int
    unresolved: int
    stopped: bool
    failures: tuple[str, ...]


class CurrentSectorRotationService:
    """Build current/forward rotation readiness solely from stored facts."""

    def __init__(self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore,
                 historical_store, index_close_store: IndexCloseSeriesStore | None = None,
                 ranking_store: CurrentSectorRankingStore | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._repository, self._universe, self._historical, self._index_closes, self._ranking_store, self._clock = repository, universe, historical_store, index_close_store, ranking_store, clock

    def assess(
        self, *, rs_ready_only: bool = False, as_of: datetime | None = None,
    ) -> CurrentSectorRotationReport:
        """Assess stored current membership at one explicit evaluation boundary.

        ``as_of`` is optional solely for backwards compatibility with the
        existing status/CLI callers.  Consumers that compose the report into a
        governed historical assessment provide it explicitly; no second sector
        ranking is calculated for that path.
        """
        at = (as_of or self._clock()).astimezone(UTC)
        # Current mapping imports are immutable snapshots.  Do not let a later
        # import alter an earlier ``as_of`` coverage decision.
        mappings = tuple(item for item in self._payloads(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_MAPPING, as_of=at) if isinstance(item, NseSectorIndexMapping))
        constituents = tuple(item for item in self._payloads(CoreApiSnapshotFamily.NSE_SECTOR_INDEX_CONSTITUENT, as_of=at) if isinstance(item, NseSectorIndexConstituent))
        # Instrument identities themselves are versioned by their source
        # ``data_as_of``.  Use the requested boundary directly rather than a
        # later current-universe snapshot.
        instruments = self._universe.instruments_as_of(at)
        benchmark = self._close_series(NIFTY_500_INDEX_ID, at)
        rs: list[CurrentSectorRelativeStrength] = []
        resolved: list[CurrentConstituentResolution] = []
        coverage: list[CurrentConstituentHistoryCoverage] = []
        breadth: list[CurrentSectorBreadthResult] = []
        sector_values: list[tuple[SectorRelativeStrength, SectorBreadth]] = []
        plan_memberships: list[tuple[NseSectorIndexMapping, tuple[NseSectorIndexConstituent, ...], tuple[CurrentConstituentResolution, ...], tuple[CurrentConstituentHistoryCoverage, ...]]] = []

        for mapping in sorted(mappings, key=lambda item: item.canonical_sector):
            if mapping.status not in {SectorIndexMappingStatus.EXACT_OFFICIAL, SectorIndexMappingStatus.DETERMINISTIC_FROM_OFFICIAL_CONSTITUENTS} or not mapping.official_index_name:
                continue
            sector_series, official_close_sessions = self._sector_close_series(_sector_index_id(mapping.canonical_sector), at)
            item_rs = _relative_strength(mapping.canonical_sector, mapping.official_index_name, sector_series, benchmark, official_close_sessions)
            rs.append(item_rs)
            raw_current = _current_constituents(constituents, mapping.official_index_name)
            current = _deduplicated_current_constituents(raw_current)
            identities = _resolve_current_constituents(mapping, current, instruments, self._universe, at)
            resolved.extend(identities)
            sector_coverage: list[CurrentConstituentHistoryCoverage] = []
            for item, identity in zip(current, identities, strict=True):
                if identity.instrument_id is None:
                    sector_coverage.append(_unresolved_coverage(item, mapping))
                    continue
                instrument = next(value for value in instruments if value.instrument_id == identity.instrument_id)
                bars = self._bars(instrument.instrument_id, at)
                value = _coverage(mapping, item, instrument, bars)
                coverage.append(value); sector_coverage.append(value)
            sector_breadth = _breadth(mapping, sector_coverage, self._historical, at)
            breadth.append(sector_breadth)
            if item_rs.exclusion_reason is None and sector_breadth.status == "READY":
                sector_values.append((
                    SectorRelativeStrength(mapping.canonical_sector, at, item_rs.rs20, item_rs.rs60, item_rs.rs120, tuple(point.evidence_id for point in sector_series)),
                    SectorBreadth(mapping.canonical_sector, at, mapping.mapping_id, sector_breadth.above_50_pct, sector_breadth.above_200_pct, sector_breadth.constituent_count,
                                  tuple(item.instrument_id for item in identities if item.instrument_id is not None)),
                ))
            if not rs_ready_only or item_rs.exclusion_reason is None:
                plan_memberships.append((mapping, raw_current, identities, tuple(sector_coverage)))

        scan = PreBreakoutEngine().sector_scan(scan_id=f"current-sector:{at.isoformat()}", as_of=at, values=tuple(sector_values), config=PreBreakoutConfig())
        plan = _backfill_plan(plan_memberships, rs, instruments, rs_ready_only=rs_ready_only)
        warnings = ["CURRENT_MEMBERSHIP_ONLY", "HISTORICAL_BREADTH_NOT_PIT_VALID", "DELIVERY_DATA_UNAVAILABLE", "INFLECTION_INPUTS_NOT_MATERIALIZED"]
        return CurrentSectorRotationReport(
            at, max((point.session for point in benchmark), default=None), len(benchmark), tuple(rs), tuple(resolved), tuple(coverage), tuple(breadth),
            tuple(item.sector for item in scan.relative_strength), scan.selected_sectors, plan,
            sum(item.at_least_320 for item in coverage), 0, 0, tuple(warnings),
        )

    def materialize(self, *, as_of: datetime | None = None) -> CurrentSectorRankingArtifact:
        if self._ranking_store is None:
            raise ValueError("CURRENT_SECTOR_RANKING_STORE_REQUIRED")
        return self._ranking_store.save(CurrentSectorRankingArtifact.create(self.assess(as_of=as_of)))

    def latest_materialized(self, *, as_of: datetime) -> CurrentSectorRankingArtifact | None:
        return None if self._ranking_store is None else self._ranking_store.latest(as_of=as_of)

    def write_reports(self, report: CurrentSectorRotationReport, directory: Path) -> tuple[Path, ...]:
        directory.mkdir(parents=True, exist_ok=True)
        _write_json_csv(directory / "current_sector_rs", report.relative_strength)
        _write_json_csv(directory / "current_sector_constituent_history_coverage", report.coverage)
        summary = directory / "current_sector_rotation_status.json"
        summary.write_text(json.dumps(asdict(report), default=str, indent=2, sort_keys=True), encoding="utf-8")
        return (directory / "current_sector_rs.json", directory / "current_sector_rs.csv", directory / "current_sector_constituent_history_coverage.json", directory / "current_sector_constituent_history_coverage.csv", summary)

    def _bars(self, instrument_id: str, at: datetime):
        return self._historical.range(instrument_id, Timeframe.DAILY, datetime(1970, 1, 1, tzinfo=UTC), at, as_of=at)

    def _close_series(self, instrument_id: str, at: datetime) -> tuple[CloseSeriesPoint, ...]:
        """Close-only RS can safely reuse canonical bar closes for benchmarks."""
        return close_series_from_bars(self._bars(instrument_id, at))

    def _sector_close_series(self, instrument_id: str, at: datetime) -> tuple[tuple[CloseSeriesPoint, ...], int]:
        """Official close-only evidence takes precedence for its exact index.

        It is intentionally selected only here.  ATR, BBW, pivots, and all
        constituent breadth paths continue to call ``_bars`` exclusively.
        """
        if self._index_closes is not None:
            official = self._index_closes.range(instrument_id, datetime(1970, 1, 1, tzinfo=UTC), at, as_of=at)
            if official:
                points = close_series_from_observations(official)
                return points, len(points)
        values = close_series_from_bars(self._bars(instrument_id, at))
        return values, 0

    def _payloads(self, family: CoreApiSnapshotFamily, *, as_of: datetime | None = None) -> tuple[object, ...]:
        values: list[object] = []; offset = 0
        while True:
            # Core snapshots deliberately cap a page at 100.  Continue paging
            # rather than requesting an invalid oversized page for a complete
            # current constituent universe.
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(
                item.payload for item in page
                if as_of is None or item.created_at <= as_of
            )
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


class CurrentSectorConstituentBackfillService:
    """Explicit, sequential Upstox backfill of a previously stored plan only."""

    def __init__(self, *, universe: CoreUniverseAnalysisStore, historical_store,
                 provider_factory: Callable[[str], UpstoxHistoricalProvider] = UpstoxHistoricalProvider,
                 sleep_fn: Callable[[float], None] = sleep, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._universe, self._historical, self._provider_factory, self._sleep, self._clock = universe, historical_store, provider_factory, sleep_fn, clock

    def ingest(self, plan: SectorBackfillPlan, *, master_records: Sequence[UpstoxInstrumentRecord], access_token: str, years: int = 2, delay_seconds: float = 0.25) -> SectorConstituentBackfillReport:
        if not access_token:
            raise ValueError("UPSTOX_ACCESS_TOKEN_REQUIRED")
        if years not in {2, 3} or delay_seconds < 0:
            raise ValueError("UPSTOX_SECTOR_CONSTITUENT_BACKFILL_CONFIGURATION_INVALID")
        # An empty stored-only plan must not even instantiate a provider
        # client; this keeps the no-refetch path free of network side effects.
        if not plan.need_backfill:
            return SectorConstituentBackfillReport(0, 0, 0, 0, 0, 0, False, ())
        at = self._clock().astimezone(UTC)
        provider, start = self._provider_factory(access_token), at - timedelta(days=366 * years)
        accepted = duplicates = conflicts = unresolved = requests = 0; failures: list[str] = []; stopped = False
        for target in plan.need_backfill:
            if self._historical.count(target.instrument.instrument_id, Timeframe.DAILY) >= CURRENT_BREADTH_MINIMUM_HISTORY:
                continue
            mapping, status, _ = resolve_upstox_equity_mapping(target.instrument, master_records)
            if mapping is None:
                unresolved += 1; failures.append(f"{target.instrument.instrument_id}:{status}"); continue
            identity = _with_mapping(target.instrument, mapping)
            existing = self._universe.provider_mapping(canonical_instrument_id=identity.instrument_id, provider=UPSTOX_PROVIDER, as_of=at)
            if existing is None or existing.provider_instrument_reference != mapping.provider_instrument_reference:
                self._universe.capture_provider_mapping(identity, provider=UPSTOX_PROVIDER, effective_as_of=at, source_reference="upstox-nse-bod-json")
            try:
                # One target maps to one bounded HistoricalIngestionService
                # request.  Count an attempted request as well as accepted
                # bars so an immediate provider rejection is not hidden.
                requests += 1
                result = HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
                    HistoricalBarsRequest(identity, Timeframe.DAILY, start, at, AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER)
                )
            except MarketDataError as error:
                failures.append(f"{identity.instrument_id}:{error.code.value}")
                if error.code.value == "AUTHORIZATION_FAILURE":
                    stopped = True; break
                continue
            accepted += result.accepted_count; duplicates += result.duplicate_count; conflicts += result.conflict_count
            if result.conflict_count:
                failures.append(f"{identity.instrument_id}:PROVIDER_REVISION_CONFLICT")
                stopped = True; break
            if delay_seconds:
                self._sleep(delay_seconds)
        return SectorConstituentBackfillReport(len(plan.need_backfill), requests, accepted, duplicates, conflicts, unresolved, stopped, tuple(failures))


def _relative_strength(sector: str, official: str, sector_points: Sequence[CloseSeriesPoint], benchmark_points: Sequence[CloseSeriesPoint], official_close_sessions: int = 0) -> CurrentSectorRelativeStrength:
    # Providers may encode the same completed NSE daily session at different
    # instants.  Align close-only RS on the UTC market-session date, while each
    # evidence record retains its own precise PIT timestamp.
    by_session_date = {point.session.astimezone(UTC).date(): point.close for point in benchmark_points}
    pairs = tuple(
        (point.close, by_session_date[point.session.astimezone(UTC).date()])
        for point in sector_points if point.session.astimezone(UTC).date() in by_session_date
    )
    values = tuple(left for left, _ in pairs); benchmark = tuple(right for _, right in pairs)
    measure = {lookback: mansfield_relative_strength(sector_prices=values, benchmark_prices=benchmark, lookback=lookback) for lookback in SECTOR_RS_LOOKBACKS}
    reason = None if measure[120] is not None else "INSUFFICIENT_ALIGNED_120_SESSION_HISTORY"
    upstox = sum(point.provider.casefold() == UPSTOX_PROVIDER for point in sector_points)
    return CurrentSectorRelativeStrength(
        sector, official, len(sector_points), upstox, official_close_sessions,
        measure[20], measure[60], measure[120], measure[120], reason,
    )


def _current_constituents(values: Iterable[NseSectorIndexConstituent], official: str) -> tuple[NseSectorIndexConstituent, ...]:
    return tuple(sorted((item for item in values if item.official_index_name == official), key=lambda value: (value.isin, value.symbol, value.constituent_id)))


def _deduplicated_current_constituents(values: Iterable[NseSectorIndexConstituent]) -> tuple[NseSectorIndexConstituent, ...]:
    unique: dict[str, NseSectorIndexConstituent] = {}
    for item in values:
        unique.setdefault(item.isin.upper() or f"SYMBOL:{item.symbol.upper()}", item)
    return tuple(unique.values())


def _backfill_plan(
    memberships: Sequence[tuple[NseSectorIndexMapping, tuple[NseSectorIndexConstituent, ...], tuple[CurrentConstituentResolution, ...], tuple[CurrentConstituentHistoryCoverage, ...]]],
    relative_strength: Sequence[CurrentSectorRelativeStrength], instruments: Sequence[NseEquityInstrument], *, rs_ready_only: bool,
) -> SectorBackfillPlan:
    """Deduplicate a stored current-membership plan without changing ranking.

    This is deliberately a routing layer: eligibility remains the existing RS
    result.  A current constituent occurring in two eligible indices has one
    canonical ISIN/instrument history request, while each sector retains its
    own membership count in the report.
    """
    by_instrument = {item.instrument_id: item for item in instruments}
    targets: dict[str, SectorBackfillTarget] = {}
    members: set[str] = set()
    sufficient: set[str] = set()
    unresolved: set[str] = set()
    before = 0
    summaries: list[SectorBackfillSectorSummary] = []
    for mapping, raw_current, identities, coverage in memberships:
        before += len(raw_current)
        sector_sufficient = sector_needed = sector_unresolved = 0
        for constituent, identity, history in zip(_deduplicated_current_constituents(raw_current), identities, coverage, strict=True):
            member = f"ISIN:{constituent.isin.upper()}" if constituent.isin else f"SYMBOL:{constituent.symbol.upper()}"
            members.add(member)
            if identity.instrument_id is None:
                sector_unresolved += 1; unresolved.add(member); continue
            if history.at_least_200:
                sector_sufficient += 1; sufficient.add(member); continue
            sector_needed += 1
            instrument = by_instrument[identity.instrument_id]
            # Stable first-sector attribution makes the command and reports
            # deterministic while de-duplicating an overlapping ISIN.
            targets.setdefault(identity.instrument_id, SectorBackfillTarget(
                mapping.canonical_sector, mapping.official_index_name or "", _identity(instrument), history.sessions,
                "CURRENT_200DMA_HISTORY_REQUIRED",
            ))
        summaries.append(SectorBackfillSectorSummary(
            mapping.canonical_sector, mapping.official_index_name or "", len(raw_current),
            sector_sufficient, sector_needed, sector_unresolved,
        ))
    ready = tuple(item.sector for item in relative_strength if item.exclusion_reason is None)
    return SectorBackfillPlan(
        rs_ready_only, ready, before, len(members), len(members), len(sufficient),
        tuple(sorted(targets.values(), key=lambda item: item.instrument.instrument_id)), len(unresolved),
        tuple(sorted(summaries, key=lambda item: item.sector)),
    )


def _resolve_current_constituents(mapping, current, instruments: Sequence[NseEquityInstrument], universe, at) -> tuple[CurrentConstituentResolution, ...]:
    by_isin: dict[str, list[NseEquityInstrument]] = {}; by_symbol: dict[str, list[NseEquityInstrument]] = {}
    for item in instruments:
        if item.isin: by_isin.setdefault(item.isin.upper(), []).append(item)
        by_symbol.setdefault(item.symbol.upper(), []).append(item)
    values = []
    for item in current:
        candidates = by_isin.get(item.isin.upper(), ())
        method = "EXACT_ISIN" if len(candidates) == 1 else None
        if len(candidates) > 1:
            values.append(CurrentConstituentResolution(mapping.canonical_sector, mapping.official_index_name, item.symbol, item.isin, None, None, False, "ISIN_CONFLICT")); continue
        if not candidates:
            candidates = by_symbol.get(item.symbol.upper(), ()); method = "EXACT_SYMBOL" if len(candidates) == 1 else None
        if len(candidates) != 1:
            values.append(CurrentConstituentResolution(mapping.canonical_sector, mapping.official_index_name, item.symbol, item.isin, None, None, False, "UNRESOLVED" if not candidates else "SYMBOL_CONFLICT")); continue
        candidate = candidates[0]
        has_mapping = universe.provider_mapping(canonical_instrument_id=candidate.instrument_id, provider=UPSTOX_PROVIDER, as_of=at) is not None
        values.append(CurrentConstituentResolution(mapping.canonical_sector, mapping.official_index_name, item.symbol, item.isin, candidate.instrument_id, method, has_mapping, "RESOLVED"))
    return tuple(values)


def _coverage(mapping, constituent, instrument: NseEquityInstrument, bars) -> CurrentConstituentHistoryCoverage:
    sessions = len(bars); volumes = tuple(bar.volume for bar in bars[-20:])
    return CurrentConstituentHistoryCoverage(mapping.canonical_sector, mapping.official_index_name, constituent.symbol, constituent.isin, instrument.instrument_id,
        sessions, sessions >= 20, sessions >= 60, sessions >= 120, sessions >= 200, sessions >= 252, sessions >= 320,
        sessions >= CURRENT_BREADTH_MINIMUM_HISTORY, len(volumes) == 20 and all(value is not None for value in volumes))


def _unresolved_coverage(constituent, mapping) -> CurrentConstituentHistoryCoverage:
    return CurrentConstituentHistoryCoverage(mapping.canonical_sector, mapping.official_index_name, constituent.symbol, constituent.isin, None, 0, False, False, False, False, False, False, False, False)


def _breadth(mapping, coverage: Sequence[CurrentConstituentHistoryCoverage], store, at: datetime) -> CurrentSectorBreadthResult:
    complete = [item for item in coverage if item.instrument_id]
    above50 = above200 = evaluated50 = evaluated200 = 0
    for item in complete:
        bars = store.range(item.instrument_id, Timeframe.DAILY, datetime(1970, 1, 1, tzinfo=UTC), at, as_of=at)
        closes = tuple(bar.close for bar in bars)
        if len(closes) >= 50:
            evaluated50 += 1; above50 += closes[-1] > sum(closes[-50:], Decimal("0")) / Decimal(50)
        if len(closes) >= 200:
            evaluated200 += 1; above200 += closes[-1] > sum(closes[-200:], Decimal("0")) / Decimal(200)
    total = len(coverage)
    percentage = lambda numerator, denominator: (Decimal("100") * Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.01")) if denominator else None
    ready = total > 0 and evaluated50 == total and evaluated200 == total
    status = "READY" if ready else "PARTIAL" if evaluated50 or evaluated200 else "INSUFFICIENT"
    return CurrentSectorBreadthResult(mapping.canonical_sector, mapping.official_index_name, total, evaluated50, above50, percentage(above50, evaluated50), evaluated200, above200, percentage(above200, evaluated200), percentage(evaluated200, total) or Decimal("0"), status, None if ready else "CURRENT_CONSTITUENT_HISTORY_INCOMPLETE")


def _identity(item: NseEquityInstrument) -> InstrumentIdentity:
    return InstrumentIdentity(item.instrument_id, Exchange.NSE, item.symbol, item.symbol, item.isin, None, InstrumentType.NSE_EQUITY, item.company_name)


def _with_mapping(identity: InstrumentIdentity, mapping: ProviderInstrumentMapping) -> InstrumentIdentity:
    return InstrumentIdentity(identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol, identity.isin, identity.series, identity.instrument_type, identity.name, identity.currency, (mapping,))


def _write_json_csv(stem: Path, values: Iterable[object]) -> None:
    rows = [asdict(item) for item in values]
    stem.with_suffix(".json").write_text(json.dumps(rows, default=str, indent=2, sort_keys=True), encoding="utf-8")
    with stem.with_suffix(".csv").open("w", newline="", encoding="utf-8") as handle:
        fields = tuple(rows[0]) if rows else ("status",)
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
