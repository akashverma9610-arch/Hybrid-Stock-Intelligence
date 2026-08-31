"""U17 operational composition for the existing Upstox Historical Candle V3 adapter.

This module owns only run planning and aggregate receipts.  Exact instrument
resolution, HTTP transport, canonical normalisation, provider-versioned writes,
and conflict handling remain in the already-approved market-data boundaries.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import sleep
from typing import Callable, Iterable, Sequence

from app.data_operations.models import (
    EvidenceDataFamily, EvidenceRefreshFailureKind, EvidenceRefreshMode,
    EvidenceRefreshOutcome, EvidenceRefreshRequest, EvidenceRefreshStatus,
    ReconciliationStatus,
)
from app.market_data.historical import HistoricalBarStore, HistoricalIngestionService
from app.market_data.models import (
    AdjustmentStatus, Exchange, HistoricalBarsRequest, InstrumentIdentity,
    InstrumentType, MarketDataError, ProviderInstrumentMapping, Timeframe,
)
from app.market_data.upstox import (
    UPSTOX_PROVIDER, UpstoxHistoricalProvider, UpstoxInstrumentMaster,
    UpstoxInstrumentRecord, exact_upstox_mapping,
)
from app.market_data.upstox_sector_indices import (
    NIFTY_50_INDEX_ID, RESOLVED_INDEX_MAPPING_STATUSES, resolve_official_nse_index_mappings,
)
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


# Existing Pre-Breakout structural and high-window consumers require 252
# sessions.  The 120-session BBW percentile is evaluated only after this same
# canonical history has been stored; no separate strategy-specific length is
# introduced here.  The existing bounded Upstox backfill path uses three years
# of daily history, retained as the operational safety margin.
MINIMUM_REQUIRED_DAILY_SESSIONS = 252
EXISTING_BACKFILL_YEARS = 3


class UpstoxOhlcvRefreshJob:
    """Sequential, resumable all-universe V3 backfill/incremental job.

    The job has no credential field and never retains a token.  The hosting
    composition supplies a secure token reader for each run.  A missing token
    is an auditable configuration block, never an implicit fallback.
    """

    def __init__(
        self,
        *,
        universe_store: CoreUniverseAnalysisStore,
        historical_store: HistoricalBarStore,
        token_reader: Callable[[], str | None],
        master_loader: Callable[[], UpstoxInstrumentMaster],
        provider_factory: Callable[[str], UpstoxHistoricalProvider] = UpstoxHistoricalProvider,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        pause_seconds: float = 0.2,
        required_sessions: int = MINIMUM_REQUIRED_DAILY_SESSIONS,
        backfill_years: int = EXISTING_BACKFILL_YEARS,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        if required_sessions < 1 or backfill_years < 1 or pause_seconds < 0:
            raise ValueError("UPSTOX_OPERATIONAL_REFRESH_CONFIGURATION_INVALID")
        self._universe, self._historical = universe_store, historical_store
        self._token_reader, self._master_loader, self._provider_factory = token_reader, master_loader, provider_factory
        self._clock, self._pause, self._required, self._years, self._sleep = clock, pause_seconds, required_sessions, backfill_years, sleep_fn

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        return self.refresh_selected(request, canonical_instrument_ids=None)

    def refresh_selected(
        self,
        request: EvidenceRefreshRequest,
        *,
        canonical_instrument_ids: frozenset[str] | None,
    ) -> EvidenceRefreshOutcome:
        """Refresh an explicit stored target subset without changing selection rules.

        The public operations job remains all-universe by default.  This seam
        exists only for a bounded reconciliation of identities already named
        by immutable conflict findings; no new universe discovery occurs.
        """
        token = self._token_reader()
        if not token:
            return _unavailable("UPSTOX_ACCESS_TOKEN_REQUIRED")
        try:
            master = self._master_loader()
        except MarketDataError:
            return _unavailable("UPSTOX_INSTRUMENT_MASTER_UNAVAILABLE", transient=True)
        at = min(request.requested_as_of, self._clock()).astimezone(UTC)
        instruments = tuple(
            item for item in self._universe.instruments_as_of(at)
            if item.tradable is not False
            and (canonical_instrument_ids is None or item.instrument_id in canonical_instrument_ids)
        )
        provider = self._provider_factory(token)
        totals = _Totals(discovered=len(instruments))
        references: set[str] = {master.source_url}
        latest: datetime | None = None
        for index, item in enumerate(instruments):
            identity = _equity_identity(item)
            mapping = self._resolve_mapping(identity, master.records, at)
            if mapping is None:
                totals.unresolved += 1
                totals.findings.append((ReconciliationStatus.GAP_FOUND, item.instrument_id, "UPSTOX_EXACT_INSTRUMENT_MAPPING_UNAVAILABLE"))
                continue
            bound = _with_mapping(identity, mapping)
            start = _request_start(self._historical, bound.instrument_id, at, request, self._required, self._years)
            report = HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
                HistoricalBarsRequest(bound, Timeframe.DAILY, start, at, AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER),
                ingestion_run_id=request.run_id,
            )
            totals.add(report)
            latest = max((value for value in (latest, report.latest_bar) if value is not None), default=latest)
            references.update(report.provenance_references)
            if index + 1 < len(instruments) and self._pause:
                self._sleep(self._pause)
        return totals.outcome("UPSTOX_HISTORICAL_V3", latest, master.checksum, references)

    def _resolve_mapping(self, identity: InstrumentIdentity, records: Sequence[UpstoxInstrumentRecord], at: datetime) -> ProviderInstrumentMapping | None:
        stored = self._universe.provider_mapping(canonical_instrument_id=identity.instrument_id, provider=UPSTOX_PROVIDER, as_of=at)
        if stored is not None:
            return ProviderInstrumentMapping(stored.provider, stored.provider_instrument_reference, stored.provider_symbol, stored.mapping_version, stored.provider_exchange_segment)
        mapping = exact_upstox_mapping(identity, records)
        if mapping is None:
            return None
        self._universe.capture_provider_mapping(identity, provider=UPSTOX_PROVIDER, effective_as_of=at,
                                                resolved_instrument=_with_mapping(identity, mapping),
                                                source_reference="upstox-nse-bod-json", source_checksum=None)
        return mapping


class UpstoxIndexBarsRefreshJob:
    """U17 wrapper for the existing official NIFTY 500/sector-index mappings."""

    def __init__(self, *, sector_mappings_loader: Callable[[], Sequence[NseSectorIndexMapping]],
                 universe_store: CoreUniverseAnalysisStore, historical_store: HistoricalBarStore,
                 token_reader: Callable[[], str | None], master_loader: Callable[[], UpstoxInstrumentMaster],
                 provider_factory: Callable[[str], UpstoxHistoricalProvider] = UpstoxHistoricalProvider,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC), pause_seconds: float = 0.2,
                 required_sessions: int = MINIMUM_REQUIRED_DAILY_SESSIONS,
                 backfill_years: int = EXISTING_BACKFILL_YEARS, sleep_fn: Callable[[float], None] = sleep) -> None:
        self._sector_mappings_loader, self._universe, self._historical = sector_mappings_loader, universe_store, historical_store
        self._token_reader, self._master_loader, self._provider_factory = token_reader, master_loader, provider_factory
        self._clock, self._pause, self._required, self._years, self._sleep = clock, pause_seconds, required_sessions, backfill_years, sleep_fn

    def refresh(self, request: EvidenceRefreshRequest) -> EvidenceRefreshOutcome:
        return self.refresh_selected(request, canonical_instrument_ids=None)

    def refresh_selected(
        self,
        request: EvidenceRefreshRequest,
        *,
        canonical_instrument_ids: frozenset[str] | None,
    ) -> EvidenceRefreshOutcome:
        """Refresh only explicit canonical index IDs through the approved mapping path."""
        token = self._token_reader()
        if not token:
            return _unavailable("UPSTOX_ACCESS_TOKEN_REQUIRED")
        sectors = tuple(self._sector_mappings_loader())
        benchmark_only = canonical_instrument_ids is not None and canonical_instrument_ids <= {"NIFTY_50", "NIFTY_500"}
        if not sectors and not benchmark_only:
            return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, "UPSTOX_HISTORICAL_V3",
                failure_kind=EvidenceRefreshFailureKind.AUTHENTICATION_OR_CONFIGURATION,
                error_summary="NSE_SECTOR_INDEX_MAPPING_REQUIRED", warnings=("NSE_SECTOR_INDEX_MAPPING_REQUIRED",))
        try:
            master = self._master_loader()
        except MarketDataError:
            return _unavailable("UPSTOX_INSTRUMENT_MASTER_UNAVAILABLE", transient=True)
        at = min(request.requested_as_of, self._clock()).astimezone(UTC)
        mappings = resolve_official_nse_index_mappings(
            sectors, master.records,
            include_nifty50=canonical_instrument_ids is not None and NIFTY_50_INDEX_ID in canonical_instrument_ids,
        )
        selected = tuple(
            item for item in mappings
            if canonical_instrument_ids is None or item.canonical_instrument_id in canonical_instrument_ids
        )
        targets = tuple(item for item in selected if item.resolution_status in RESOLVED_INDEX_MAPPING_STATUSES)
        if canonical_instrument_ids is not None and len({item.canonical_instrument_id for item in selected}) != len(canonical_instrument_ids):
            missing = sorted(canonical_instrument_ids - {item.canonical_instrument_id for item in selected})
            raise ValueError(f"UPSTOX_SELECTED_INDEX_TARGETS_UNKNOWN:{','.join(missing)}")
        totals = _Totals(discovered=len(selected)); provider = self._provider_factory(token)
        references: set[str] = {master.source_url}; latest: datetime | None = None
        for index, item in enumerate(selected):
            if item not in targets:
                totals.unresolved += 1
                totals.findings.append((ReconciliationStatus.GAP_FOUND, item.canonical_instrument_id, "UPSTOX_EXACT_INDEX_MAPPING_UNAVAILABLE"))
                continue
            assert item.instrument_key is not None
            identity = InstrumentIdentity(item.canonical_instrument_id, Exchange.INDEX, item.official_index_name,
                item.trading_symbol or item.official_index_name, None, None,
                InstrumentType.BROAD_INDEX if item.canonical_sector is None else InstrumentType.SECTOR_INDEX,
                item.official_index_name, provider_mappings=(ProviderInstrumentMapping(UPSTOX_PROVIDER, item.instrument_key,
                    item.trading_symbol, "upstox-v3", "NSE_INDEX"),))
            self._persist_mapping(identity, at, master.checksum)
            start = _request_start(self._historical, identity.instrument_id, at, request, self._required, self._years)
            report = HistoricalIngestionService(provider, self._historical, clock=self._clock).ingest(
                HistoricalBarsRequest(identity, Timeframe.DAILY, start, at, AdjustmentStatus.UNKNOWN, UPSTOX_PROVIDER),
                ingestion_run_id=request.run_id,
            )
            totals.add(report); latest = max((value for value in (latest, report.latest_bar) if value is not None), default=latest)
            references.update(report.provenance_references)
            if index + 1 < len(targets) and self._pause:
                self._sleep(self._pause)
        return totals.outcome("UPSTOX_HISTORICAL_V3", latest, master.checksum, references)

    def _persist_mapping(self, identity: InstrumentIdentity, at: datetime, checksum: str) -> None:
        current = self._universe.provider_mapping(canonical_instrument_id=identity.instrument_id, provider=UPSTOX_PROVIDER, as_of=at)
        reference = identity.provider_mappings[0].provider_instrument_reference
        if current is None or current.provider_instrument_reference != reference:
            self._universe.capture_provider_mapping(identity, provider=UPSTOX_PROVIDER, effective_as_of=at,
                                                    source_reference="upstox-nse-bod-json", source_checksum=checksum)


def _equity_identity(value: NseEquityInstrument) -> InstrumentIdentity:
    return InstrumentIdentity(value.instrument_id, Exchange.NSE, value.symbol, value.symbol, value.isin, None,
                              InstrumentType.NSE_EQUITY, value.company_name)


def _with_mapping(identity: InstrumentIdentity, mapping: ProviderInstrumentMapping) -> InstrumentIdentity:
    return InstrumentIdentity(identity.instrument_id, identity.exchange, identity.symbol, identity.trading_symbol,
                              identity.isin, identity.series, identity.instrument_type, identity.name,
                              identity.currency, (mapping,))


def _request_start(store: HistoricalBarStore, instrument_id: str, at: datetime, request: EvidenceRefreshRequest,
                   required: int, years: int) -> datetime:
    latest = store.latest(instrument_id, Timeframe.DAILY, 1)
    if request.mode is EvidenceRefreshMode.BACKFILL or store.count(instrument_id, Timeframe.DAILY) < required or not latest:
        return at - timedelta(days=366 * years)
    # Re-fetch the U17 configured two-session overlap for append-only
    # reconciliation.  Existing provider-versioned content remains immutable.
    return latest[-1].end_time - timedelta(days=max(1, request.overlap_sessions))


class _Totals:
    def __init__(self, *, discovered: int) -> None:
        self.discovered = discovered
        self.accepted = self.duplicates = self.conflicts = self.rejected = self.gaps = self.unresolved = 0
        self.unavailable = 0
        self.findings: list[tuple[ReconciliationStatus, str, str]] = []

    def add(self, report) -> None:
        self.accepted += report.accepted_count; self.duplicates += report.duplicate_count
        self.conflicts += report.conflict_count; self.rejected += report.rejected_count; self.gaps += report.gap_count
        if report.coverage.value == "UNAVAILABLE":
            self.unavailable += 1
            self.findings.append((ReconciliationStatus.SOURCE_UNAVAILABLE, report.instrument_id, "UPSTOX_HISTORICAL_UNAVAILABLE"))
        if report.conflict_count:
            self.findings.append((ReconciliationStatus.CONFLICT_FOUND, report.instrument_id, "UPSTOX_PROVIDER_REVISION_CONFLICT"))

    def outcome(self, provider: str, latest: datetime | None, checksum: str, references: Iterable[str]) -> EvidenceRefreshOutcome:
        gaps = self.gaps + self.unresolved + self.unavailable
        if self.accepted == 0 and self.duplicates == 0 and (self.unavailable == self.discovered or self.discovered == 0):
            return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, provider, discovered_count=self.discovered,
                gap_count=gaps, failure_kind=EvidenceRefreshFailureKind.TRANSIENT, error_summary="UPSTOX_HISTORICAL_SOURCE_UNAVAILABLE",
                warnings=("UPSTOX_HISTORICAL_SOURCE_UNAVAILABLE",), source_references=tuple(sorted(references)), findings=tuple(self.findings))
        status = EvidenceRefreshStatus.CONFLICT_FOUND if self.conflicts else EvidenceRefreshStatus.PARTIAL if gaps or self.rejected else EvidenceRefreshStatus.NO_CHANGE if not self.accepted else EvidenceRefreshStatus.COMPLETE
        warnings = tuple(sorted(set(("UPSTOX_ADJUSTMENT_SEMANTICS_UNDOCUMENTED",) + (("UPSTOX_EXACT_INSTRUMENT_MAPPING_UNAVAILABLE",) if self.unresolved else ()))))
        return EvidenceRefreshOutcome(status, provider, discovered_count=self.discovered, accepted_count=self.accepted,
            duplicate_count=self.duplicates, conflict_count=self.conflicts, rejected_count=self.rejected, gap_count=gaps,
            accepted_through=latest, source_fingerprint=checksum, verified_from_store=latest is not None,
            warnings=warnings, source_references=tuple(sorted(references)), findings=tuple(self.findings))


def _unavailable(code: str, *, transient: bool = False) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(EvidenceRefreshStatus.SOURCE_UNAVAILABLE, "UPSTOX_HISTORICAL_V3",
        failure_kind=EvidenceRefreshFailureKind.TRANSIENT if transient else EvidenceRefreshFailureKind.AUTHENTICATION_OR_CONFIGURATION,
        error_summary=code, warnings=(code,))


__all__ = ("EXISTING_BACKFILL_YEARS", "MINIMUM_REQUIRED_DAILY_SESSIONS", "UpstoxIndexBarsRefreshJob", "UpstoxOhlcvRefreshJob")
