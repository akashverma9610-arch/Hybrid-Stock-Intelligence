"""Bounded, resumable coordinator for official BSE NIFTY 500 financial XBRLs.

This module deliberately contains no XBRL parsing or FinancialFact writing.
It turns exact BSE mappings and BSE archive metadata into a deterministic
plan, then delegates every live document to the existing staging and importer
boundaries in :mod:`app.fundamentals.bse_collector` and
:mod:`app.fundamentals.bse_official`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
from time import sleep
from typing import Callable, Protocol

from app.filings.models import FilingType
from app.filings.store import CorporateFilingsStore, FilingWriteOutcome
from app.fundamentals.bse_collector import (
    BseCollectorError, BseFilingDisposition, BseOfficialHttpTransport,
    BseOfficialSecurityMaster, BseOfficialXbrlStaging, BseMappingStatus,
    BseSecurityMapping, BseStageDisposition,
)
from app.fundamentals.bse_official import (
    BSEOfficialFinancialResultsArchiveProvider, BSEOfficialLocalXbrlIngestionService,
    BseOfficialError, BseResultMetadata,
)
from app.fundamentals.store import FinancialFactStore
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


PLAN_POLICY_VERSION = "bse-financial-acquisition-plan/v1"
MAPPING_POLICY_VERSION = "bse-exact-isin-mapping/v1"
MINIMUM_ANNUAL_FILINGS = 6
MINIMUM_QUARTERLY_FILINGS = 5
MAXIMUM_FILING_DEPTH = MINIMUM_ANNUAL_FILINGS + MINIMUM_QUARTERLY_FILINGS


class BseNifty500MappingState(StrEnum):
    EXACT_VERIFIED = "EXACT_VERIFIED"
    UNMAPPED = "UNMAPPED"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"


class BseAcquisitionUnitState(StrEnum):
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    ACQUIRED = "ACQUIRED"
    ACCEPTED = "ACCEPTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    QUARANTINED = "QUARANTINED"
    UNAVAILABLE = "UNAVAILABLE"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


class BseArchiveDiscoveryState(StrEnum):
    """Durable lifecycle for one BSE archive discovery target.

    This is deliberately separate from document acquisition.  A complete
    archive listing is useful evidence even when it yields no eligible XBRL;
    neither outcome should cause another broad BSE archive request on resume.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    DISCOVERED = "DISCOVERED"
    NO_ARCHIVE_AVAILABLE = "NO_ARCHIVE_AVAILABLE"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


@dataclass(frozen=True, slots=True)
class BseNifty500Mapping:
    canonical_instrument_id: str
    nse_symbol: str
    isin: str | None
    bse_security_code: str | None
    bse_security_id: str | None
    bse_security_name: str | None
    as_of: datetime
    state: BseNifty500MappingState
    source_reference: str
    reason: str | None
    mapping_fingerprint: str


@dataclass(frozen=True, slots=True)
class BseNifty500MappingInventory:
    inventory_id: str
    as_of: datetime
    universe_id: str
    policy_version: str
    mappings: tuple[BseNifty500Mapping, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseFinancialAcquisitionUnit:
    unit_id: str
    canonical_instrument_id: str
    nse_symbol: str
    isin: str
    bse_security_code: str
    metadata: BseResultMetadata
    purpose: str
    state: BseAcquisitionUnitState
    retry_count: int
    checkpoint_identity: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseFinancialAcquisitionPlan:
    plan_id: str
    as_of: datetime
    inventory_fingerprint: str
    policy_version: str
    units: tuple[BseFinancialAcquisitionUnit, ...]
    already_satisfied_unit_ids: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseArchiveDiscoveryCheckpoint:
    """An immutable attempt record for one exact BSE security archive."""

    checkpoint_id: str
    checkpoint_identity: str
    run_id: str
    inventory_fingerprint: str
    canonical_instrument_id: str
    isin: str
    bse_security_code: str
    discovery_cutoff: datetime
    state: BseArchiveDiscoveryState
    attempt: int
    attempted_at: datetime
    archive_metadata: tuple[BseResultMetadata, ...]
    error_classification: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseProviderHaltReceipt:
    receipt_id: str
    run_id: str
    inventory_fingerprint: str
    provider: str
    halt_reason: str
    observed_failure_pattern: tuple[str, ...]
    halted_at: datetime
    last_safely_completed_security: str | None
    unresolved_unit_count: int
    resume_state: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseArchiveDiscoveryReport:
    run_id: str
    inventory_fingerprint: str
    securities_examined: int
    discovered: int
    no_archive_available: int
    retryable_failures: int
    terminal_failures: int
    remaining_unresolved: int
    provider_halted: bool
    latest_halt_receipt: BseProviderHaltReceipt | None
    checkpoints: tuple[BseArchiveDiscoveryCheckpoint, ...]


class BseArchiveDiscoveryIncompleteError(RuntimeError):
    """Raised only after all completed work has been durably checkpointed."""

    def __init__(self, report: BseArchiveDiscoveryReport) -> None:
        super().__init__("BSE_FINANCIAL_ARCHIVE_DISCOVERY_INCOMPLETE")
        self.report = report


@dataclass(frozen=True, slots=True)
class BseFinancialAcquisitionReceipt:
    receipt_id: str
    run_id: str
    unit_id: str
    attempted_at: datetime
    state: BseAcquisitionUnitState
    attempt: int
    staged_disposition: BseStageDisposition | None
    filing_outcome: FilingWriteOutcome | None
    facts_inserted: int
    facts_duplicate: int
    facts_conflicted: int
    detail: str | None
    fingerprint: str


@dataclass(frozen=True, slots=True)
class BseFinancialAcquisitionRunReport:
    run_id: str
    plan_id: str
    attempted: int
    accepted: int
    already_present: int
    quarantined: int
    unavailable: int
    retryable_failure: int
    terminal_failure: int
    provider_halted: bool
    receipts: tuple[BseFinancialAcquisitionReceipt, ...]


@dataclass(frozen=True, slots=True)
class BseFinancialAcquisitionSettings:
    """Conservative host-side limits.  Concurrency remains one by design."""

    batch_size: int = 5
    maximum_retries: int = 1
    minimum_request_interval_seconds: float = 0.5
    retry_backoff_seconds: float = 2.0
    global_halt_after_unavailable: int = 2

    def __post_init__(self) -> None:
        if not 1 <= self.batch_size <= 25:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_BATCH_SIZE_INVALID")
        if not 0 <= self.maximum_retries <= 3:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_RETRY_LIMIT_INVALID")
        if self.minimum_request_interval_seconds < 0.1 or self.retry_backoff_seconds < 0.1:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_PACING_INVALID")
        if not 1 <= self.global_halt_after_unavailable <= 5:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_GLOBAL_HALT_INVALID")


class _Sleeper(Protocol):
    def __call__(self, seconds: float) -> None: ...


class _MembershipStore(Protocol):
    def memberships(self, universe_id: str) -> tuple[object, ...]: ...


class BseFinancialAcquisitionStore:
    """Append-only mapping, discovery, planning, and acquisition evidence."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_inventory(self, value: BseNifty500MappingInventory) -> None:
        self._save(value.inventory_id, value, value.as_of)

    def save_mapping(self, value: BseNifty500Mapping) -> None:
        identifier = "bse-nifty500-mapping-entry:" + _digest((
            value.as_of.astimezone(UTC).isoformat(), value.canonical_instrument_id,
        ))[7:39]
        self._save(identifier, value, value.as_of)

    def mappings_as_of(self, as_of: datetime) -> dict[str, BseNifty500Mapping]:
        values = [
            item.payload for item in self._all()
            if isinstance(item.payload, BseNifty500Mapping) and item.payload.as_of == as_of
        ]
        return {item.canonical_instrument_id: item for item in values}

    def save_plan(self, value: BseFinancialAcquisitionPlan) -> None:
        self._save(value.plan_id, value, value.as_of)

    def save_discovery(self, value: BseArchiveDiscoveryCheckpoint) -> None:
        self._save(value.checkpoint_id, value, value.attempted_at)

    def discoveries(self, run_id: str) -> tuple[BseArchiveDiscoveryCheckpoint, ...]:
        values = [
            item.payload for item in self._all()
            if isinstance(item.payload, BseArchiveDiscoveryCheckpoint) and item.payload.run_id == run_id
        ]
        return tuple(sorted(values, key=lambda item: (
            item.canonical_instrument_id, item.attempt, _discovery_state_order(item.state),
            item.attempted_at, item.checkpoint_id,
        )))

    def latest_discoveries(self, run_id: str) -> dict[str, BseArchiveDiscoveryCheckpoint]:
        latest: dict[str, BseArchiveDiscoveryCheckpoint] = {}
        for item in self.discoveries(run_id):
            current = latest.get(item.canonical_instrument_id)
            if current is None or _discovery_order(item) >= _discovery_order(current):
                latest[item.canonical_instrument_id] = item
        return latest

    def save_provider_halt(self, value: BseProviderHaltReceipt) -> None:
        self._save(value.receipt_id, value, value.halted_at)

    def provider_halts(self, run_id: str) -> tuple[BseProviderHaltReceipt, ...]:
        values = [
            item.payload for item in self._all()
            if isinstance(item.payload, BseProviderHaltReceipt) and item.payload.run_id == run_id
        ]
        return tuple(sorted(values, key=lambda item: (item.halted_at, item.receipt_id)))

    def get_inventory(self, inventory_id: str) -> BseNifty500MappingInventory | None:
        item = self._repository.get_snapshot(inventory_id)
        return item.payload if item and isinstance(item.payload, BseNifty500MappingInventory) else None

    def get_plan(self, plan_id: str) -> BseFinancialAcquisitionPlan | None:
        item = self._repository.get_snapshot(plan_id)
        return item.payload if item and isinstance(item.payload, BseFinancialAcquisitionPlan) else None

    def latest_plan(self) -> BseFinancialAcquisitionPlan | None:
        values = [item.payload for item in self._all() if isinstance(item.payload, BseFinancialAcquisitionPlan)]
        return max(values, key=lambda item: (item.as_of, item.plan_id)) if values else None

    def save_receipt(self, value: BseFinancialAcquisitionReceipt) -> None:
        self._save(value.receipt_id, value, value.attempted_at)

    def receipts(self, run_id: str) -> tuple[BseFinancialAcquisitionReceipt, ...]:
        values = [
            item.payload for item in self._all()
            if isinstance(item.payload, BseFinancialAcquisitionReceipt) and item.payload.run_id == run_id
        ]
        return tuple(sorted(values, key=lambda item: (item.attempted_at, item.receipt_id)))

    def latest_receipts(self, run_id: str) -> dict[str, BseFinancialAcquisitionReceipt]:
        latest: dict[str, BseFinancialAcquisitionReceipt] = {}
        for item in self.receipts(run_id):
            latest[item.unit_id] = item
        return latest

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        result: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.BSE_FINANCIAL_ACQUISITION, limit=100, offset=offset)
            result.extend(page)
            if len(page) < 100:
                return tuple(result)
            offset += len(page)

    def _save(self, identifier: str, value: object, created_at: datetime) -> None:
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.payload == value:
                return
            raise ValueError("BSE financial acquisition artifacts are immutable and cannot be overwritten.")
        self._repository.save_snapshot(CoreApiSnapshot(
            identifier, CoreApiSnapshotFamily.BSE_FINANCIAL_ACQUISITION, "v1",
            type(value).__name__, _fingerprint(value), created_at, value,
        ))


class BseNifty500FinancialAcquisitionOrchestrator:
    """Coordinates only official BSE evidence through the existing pipeline."""

    def __init__(
        self, *, repository: BseFinancialAcquisitionStore, universe: CoreUniverseAnalysisStore,
        memberships: _MembershipStore,
        filings: CorporateFilingsStore, facts: FinancialFactStore,
        security_master: BseOfficialSecurityMaster,
        provider: BSEOfficialFinancialResultsArchiveProvider,
        transport: BseOfficialHttpTransport, staging: BseOfficialXbrlStaging,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC), sleeper: _Sleeper = sleep,
        expected_universe_size: int = 500,
    ) -> None:
        self._store, self._universe, self._memberships, self._filings, self._facts = repository, universe, memberships, filings, facts
        self._security_master, self._provider, self._transport, self._staging = security_master, provider, transport, staging
        self._clock, self._sleeper = clock, sleeper
        self._expected_universe_size = expected_universe_size
        self._importer = BSEOfficialLocalXbrlIngestionService(filings, facts, mapping_store=universe, clock=clock)

    def mapping_audit(
        self, *, as_of: datetime, max_instruments: int | None = None,
        settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings(),
    ) -> BseNifty500MappingInventory:
        _aware(as_of)
        active_ids = {
            item.instrument_id for item in self._memberships.memberships("NIFTY_500")
            if item.known_at <= as_of and item.effective_from <= as_of
            and (item.effective_to is None or as_of <= item.effective_to)
        }
        if len(active_ids) != self._expected_universe_size:
            raise ValueError("BSE_NIFTY500_MEMBERSHIP_INCOMPLETE")
        identities = {item.instrument_id: item for item in self._universe.instruments_as_of(as_of)}
        if active_ids - identities.keys():
            raise ValueError("BSE_NIFTY500_CANONICAL_IDENTITY_INCOMPLETE")
        members = tuple(sorted((identities[item] for item in active_ids), key=lambda item: item.instrument_id))
        if max_instruments is not None:
            if max_instruments < 1:
                raise ValueError("BSE_FINANCIAL_ACQUISITION_MAX_INSTRUMENTS_INVALID")
            members = members[:max_instruments]
        self._security_master.begin_run()
        completed = self._store.mappings_as_of(as_of)
        values: list[BseNifty500Mapping] = []
        unavailable_streak = 0
        for index, item in enumerate(members):
            prior = completed.get(item.instrument_id)
            if prior is not None:
                values.append(prior)
                continue
            if not item.isin:
                value = _inventory_mapping(item, None, as_of)
                self._store.save_mapping(value); values.append(value)
                continue
            try:
                mapping = self._security_master.resolve(canonical_instrument_id=item.instrument_id, isin=item.isin)
                unavailable_streak = 0
            except BseCollectorError as error:
                if "SOURCE_UNAVAILABLE" in str(error):
                    unavailable_streak += 1
                    if unavailable_streak >= settings.global_halt_after_unavailable:
                        raise BseCollectorError("BSE_OFFICIAL_MAPPING_PROVIDER_HALTED") from error
                mapping = None
            value = _inventory_mapping(item, mapping, as_of)
            self._store.save_mapping(value); values.append(value)
            if index + 1 < len(members):
                self._sleeper(settings.minimum_request_interval_seconds)
                if (index + 1) % settings.batch_size == 0:
                    self._sleeper(settings.retry_backoff_seconds)
        fingerprint = _digest((MAPPING_POLICY_VERSION, as_of.astimezone(UTC).isoformat(), tuple(_mapping_key(item) for item in values)))
        inventory = BseNifty500MappingInventory(
            "bse-nifty500-mapping:" + fingerprint[7:39], as_of, "NIFTY_500", MAPPING_POLICY_VERSION,
            tuple(values), fingerprint,
        )
        self._store.save_inventory(inventory)
        return inventory

    def discover_archives(
        self, inventory: BseNifty500MappingInventory,
        *, max_instruments: int | None = None,
        settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings(),
    ) -> BseArchiveDiscoveryReport:
        """Discover BSE result archives exactly once per completed security.

        Every state transition is an append-only checkpoint.  Thus an
        interrupted process resumes from the next unresolved security instead
        of repeating an already completed BSE archive request.
        """
        if max_instruments is not None and max_instruments < 1:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_MAX_INSTRUMENTS_INVALID")
        _aware(inventory.as_of)
        run_id = _discovery_run_id(inventory)
        mappings = tuple(sorted((
            item for item in inventory.mappings
            if item.state is BseNifty500MappingState.EXACT_VERIFIED
            and item.bse_security_code and item.isin
        ), key=lambda item: item.canonical_instrument_id))
        latest = self._store.latest_discoveries(run_id)

        # Materialise every logical discovery unit before any broad provider
        # call.  This lets a process that exits between securities resume
        # deterministically and makes even untouched work auditable as PENDING.
        for mapping in mappings:
            if mapping.canonical_instrument_id not in latest:
                pending = self._discovery_checkpoint(
                    run_id, inventory, mapping, BseArchiveDiscoveryState.PENDING,
                    attempt=0, metadata=(), error=None,
                )
                self._store.save_discovery(pending)
                latest[mapping.canonical_instrument_id] = pending

        completed = {
            BseArchiveDiscoveryState.DISCOVERED,
            BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE,
            BseArchiveDiscoveryState.TERMINAL_FAILURE,
        }
        failures: list[str] = []
        attempted_this_call = 0
        unavailable_streak = 0
        last_completed = next((
            mapping.canonical_instrument_id for mapping in reversed(mappings)
            if latest[mapping.canonical_instrument_id].state in {
                BseArchiveDiscoveryState.DISCOVERED,
                BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE,
            }
        ), None)
        halted = False
        for mapping in mappings:
            prior = latest[mapping.canonical_instrument_id]
            if prior.state in completed:
                if prior.state in {
                    BseArchiveDiscoveryState.DISCOVERED,
                    BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE,
                }:
                    last_completed = mapping.canonical_instrument_id
                continue
            if prior.state is BseArchiveDiscoveryState.RETRYABLE_FAILURE and prior.attempt > settings.maximum_retries:
                exhausted = self._discovery_checkpoint(
                    run_id, inventory, mapping, BseArchiveDiscoveryState.TERMINAL_FAILURE,
                    attempt=prior.attempt, metadata=(), error="BSE_ARCHIVE_RETRY_LIMIT_EXHAUSTED",
                )
                self._store.save_discovery(exhausted)
                latest[mapping.canonical_instrument_id] = exhausted
                continue
            if max_instruments is not None and attempted_this_call >= max_instruments:
                break
            attempt = prior.attempt + 1
            in_progress = self._discovery_checkpoint(
                run_id, inventory, mapping, BseArchiveDiscoveryState.IN_PROGRESS,
                attempt=attempt, metadata=(), error=None,
            )
            self._store.save_discovery(in_progress)
            latest[mapping.canonical_instrument_id] = in_progress
            attempted_this_call += 1
            try:
                aliases = self._provider.result_metadata_aliases(mapping.bse_security_code)
                metadata = tuple(
                    item.preferred for item in aliases if item.preferred.filing_at <= inventory.as_of
                )
                state = BseArchiveDiscoveryState.DISCOVERED if metadata else BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE
                result = self._discovery_checkpoint(run_id, inventory, mapping, state, attempt=attempt, metadata=metadata, error=None)
                unavailable_streak = 0
                last_completed = mapping.canonical_instrument_id
            except (BseCollectorError, BseOfficialError, ValueError) as error:
                classification = _discovery_failure_classification(error)
                state = _discovery_failure_state(error)
                result = self._discovery_checkpoint(run_id, inventory, mapping, state, attempt=attempt, metadata=(), error=classification)
                failures.append(classification)
                unavailable_streak = unavailable_streak + 1 if _provider_degradation(classification) else 0
            self._store.save_discovery(result)
            latest[mapping.canonical_instrument_id] = result
            if unavailable_streak >= settings.global_halt_after_unavailable:
                halted = True
                receipt = self._provider_halt_receipt(
                    run_id, inventory, failures[-settings.global_halt_after_unavailable:], last_completed,
                    len([item for item in latest.values() if item.state not in completed]),
                )
                self._store.save_provider_halt(receipt)
                break
            if attempted_this_call < len(mappings):
                self._sleeper(settings.minimum_request_interval_seconds)
                if attempted_this_call % settings.batch_size == 0:
                    self._sleeper(settings.retry_backoff_seconds)
        return self._discovery_report(run_id, inventory, latest, halted)

    def build_plan(
        self, inventory: BseNifty500MappingInventory,
        *, max_instruments: int | None = None,
        settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings(),
    ) -> BseFinancialAcquisitionPlan:
        report = self.discover_archives(inventory, max_instruments=max_instruments, settings=settings)
        if report.remaining_unresolved or report.provider_halted:
            raise BseArchiveDiscoveryIncompleteError(report)
        units: list[BseFinancialAcquisitionUnit] = []
        already: list[str] = []
        mappings = {item.canonical_instrument_id: item for item in inventory.mappings}
        for discovered in report.checkpoints:
            if discovered.state is not BseArchiveDiscoveryState.DISCOVERED:
                continue
            mapping = mappings[discovered.canonical_instrument_id]
            selected = discovered.archive_metadata[-MAXIMUM_FILING_DEPTH:]
            for metadata in selected:
                identity = _unit_identity(mapping.canonical_instrument_id, mapping.bse_security_code, metadata)
                unit = BseFinancialAcquisitionUnit(
                    "bse-financial-unit:" + identity[7:39], mapping.canonical_instrument_id, mapping.nse_symbol,
                    mapping.isin, mapping.bse_security_code, metadata,
                    "CANONICAL_FINANCIAL_DIAGNOSTIC_MINIMUM_DEPTH", BseAcquisitionUnitState.PLANNED, 0,
                    "bse-financial-checkpoint:" + identity[7:39], identity,
                )
                if self._already_present(unit):
                    already.append(unit.unit_id)
                else:
                    units.append(unit)
        ordered = tuple(sorted(units, key=lambda item: (item.canonical_instrument_id, item.metadata.filing_at, item.metadata.xbrl_url)))
        fingerprint = _digest((PLAN_POLICY_VERSION, inventory.fingerprint, tuple(item.fingerprint for item in ordered), tuple(sorted(already))))
        plan = BseFinancialAcquisitionPlan(
            "bse-financial-plan:" + fingerprint[7:39], inventory.as_of, inventory.fingerprint,
            PLAN_POLICY_VERSION, ordered, tuple(sorted(already)), fingerprint,
        )
        self._store.save_plan(plan)
        return plan

    def dry_run(
        self, *, as_of: datetime, max_instruments: int | None = None,
        settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings(),
    ) -> tuple[BseNifty500MappingInventory, BseFinancialAcquisitionPlan]:
        inventory = self.mapping_audit(as_of=as_of, max_instruments=max_instruments, settings=settings)
        return inventory, self.build_plan(inventory, max_instruments=max_instruments, settings=settings)

    def execute(
        self, plan: BseFinancialAcquisitionPlan, *, run_id: str | None = None,
        max_units: int | None = None, unit_ids: tuple[str, ...] | None = None,
        settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings(),
    ) -> BseFinancialAcquisitionRunReport:
        if max_units is not None and max_units < 1:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_MAX_UNITS_INVALID")
        run = run_id or "bse-financial-run:" + plan.fingerprint[7:39]
        latest = self._store.latest_receipts(run)
        terminal = {BseAcquisitionUnitState.ACCEPTED, BseAcquisitionUnitState.ALREADY_PRESENT,
                    BseAcquisitionUnitState.QUARANTINED, BseAcquisitionUnitState.UNAVAILABLE,
                    BseAcquisitionUnitState.TERMINAL_FAILURE}
        selected = [
            item for item in plan.units
            if (unit_ids is None or item.unit_id in unit_ids)
            and (latest.get(item.unit_id) is None or latest[item.unit_id].state not in terminal)
        ]
        if max_units is not None:
            selected = selected[:max_units]
        unavailable_streak = 0
        halted = False
        for index, unit in enumerate(selected):
            prior = latest.get(unit.unit_id)
            result = self._execute_unit(run, unit, attempt=(prior.attempt + 1 if prior else 1), settings=settings)
            latest[unit.unit_id] = result
            if result.state is BseAcquisitionUnitState.UNAVAILABLE:
                unavailable_streak += 1
                if unavailable_streak >= settings.global_halt_after_unavailable:
                    halted = True
                    break
            else:
                unavailable_streak = 0
            if index + 1 < len(selected):
                self._sleeper(settings.minimum_request_interval_seconds)
        receipts = tuple(sorted(latest.values(), key=lambda item: (item.attempted_at, item.receipt_id)))
        return _run_report(run, plan.plan_id, receipts, halted)

    def resume(self, plan_id: str, *, max_units: int | None = None,
               settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings()) -> BseFinancialAcquisitionRunReport:
        plan = self._store.get_plan(plan_id)
        if plan is None:
            raise ValueError("BSE_FINANCIAL_ACQUISITION_PLAN_NOT_FOUND")
        return self.execute(plan, max_units=max_units, settings=settings)

    def canary(self, plan: BseFinancialAcquisitionPlan, *, max_units: int = 3,
               settings: BseFinancialAcquisitionSettings = BseFinancialAcquisitionSettings()) -> BseFinancialAcquisitionRunReport:
        """Run a deterministic small sample through the exact production path."""
        selected: list[BseFinancialAcquisitionUnit] = []
        for instrument_id in ("NSE:INE090A01021", "NSE:INE372A01015"):
            candidate = next((item for item in plan.units if item.canonical_instrument_id == instrument_id), None)
            if candidate is not None:
                selected.append(candidate)
        for item in plan.units:
            if item.canonical_instrument_id not in {value.canonical_instrument_id for value in selected}:
                selected.append(item)
            if len(selected) >= max_units:
                break
        return self.execute(plan, max_units=max_units, unit_ids=tuple(item.unit_id for item in selected), settings=settings)

    def status(self, plan_id: str | None = None) -> BseFinancialAcquisitionRunReport | None:
        plan = self._store.get_plan(plan_id) if plan_id else self._store.latest_plan()
        if plan is None:
            return None
        run = "bse-financial-run:" + plan.fingerprint[7:39]
        return _run_report(run, plan.plan_id, tuple(self._store.latest_receipts(run).values()), False)

    def plan(self, plan_id: str | None = None) -> BseFinancialAcquisitionPlan | None:
        """Read a persisted immutable plan without any provider request."""
        return self._store.get_plan(plan_id) if plan_id else self._store.latest_plan()

    def inventory(self, inventory_id: str) -> BseNifty500MappingInventory | None:
        return self._store.get_inventory(inventory_id)

    def discovery_status(self, inventory: BseNifty500MappingInventory) -> BseArchiveDiscoveryReport:
        """Read the persisted discovery state without calling BSE."""
        run_id = _discovery_run_id(inventory)
        return self._discovery_report(run_id, inventory, self._store.latest_discoveries(run_id), False)

    def _discovery_checkpoint(
        self, run_id: str, inventory: BseNifty500MappingInventory, mapping: BseNifty500Mapping,
        state: BseArchiveDiscoveryState, *, attempt: int, metadata: tuple[BseResultMetadata, ...],
        error: str | None,
    ) -> BseArchiveDiscoveryCheckpoint:
        identity = _digest((
            run_id, inventory.fingerprint, mapping.canonical_instrument_id, mapping.isin,
            mapping.bse_security_code, inventory.as_of.astimezone(UTC).isoformat(),
        ))
        fingerprint = _digest((
            identity, state.value, attempt, tuple(_metadata_key(item) for item in metadata), error,
        ))
        return BseArchiveDiscoveryCheckpoint(
            "bse-financial-discovery:" + fingerprint[7:39], identity, run_id, inventory.fingerprint,
            mapping.canonical_instrument_id, mapping.isin or "", mapping.bse_security_code or "",
            inventory.as_of, state, attempt, self._clock(), metadata, error, fingerprint,
        )

    def _provider_halt_receipt(
        self, run_id: str, inventory: BseNifty500MappingInventory, failures: list[str],
        last_completed: str | None, unresolved: int,
    ) -> BseProviderHaltReceipt:
        reason = failures[-1] if failures else "BSE_PROVIDER_DEGRADATION"
        fingerprint = _digest((
            run_id, inventory.fingerprint, "BSE_OFFICIAL_FINANCIAL_RESULTS_ARCHIVE", reason,
            tuple(failures), last_completed, unresolved, "RESUME_ELIGIBLE",
        ))
        return BseProviderHaltReceipt(
            "bse-financial-provider-halt:" + fingerprint[7:39], run_id, inventory.fingerprint,
            "BSE_OFFICIAL_FINANCIAL_RESULTS_ARCHIVE", reason, tuple(failures), self._clock(),
            last_completed, unresolved, "RESUME_ELIGIBLE", fingerprint,
        )

    def _discovery_report(
        self, run_id: str, inventory: BseNifty500MappingInventory,
        latest: dict[str, BseArchiveDiscoveryCheckpoint], halted: bool,
    ) -> BseArchiveDiscoveryReport:
        states = tuple(latest.values())
        completed = {
            BseArchiveDiscoveryState.DISCOVERED,
            BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE,
            BseArchiveDiscoveryState.TERMINAL_FAILURE,
        }
        exact_count = sum(
            item.state is BseNifty500MappingState.EXACT_VERIFIED and bool(item.bse_security_code and item.isin)
            for item in inventory.mappings
        )
        halts = self._store.provider_halts(run_id)
        return BseArchiveDiscoveryReport(
            run_id, inventory.fingerprint, len(states),
            sum(item.state is BseArchiveDiscoveryState.DISCOVERED for item in states),
            sum(item.state is BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE for item in states),
            sum(item.state is BseArchiveDiscoveryState.RETRYABLE_FAILURE for item in states),
            sum(item.state is BseArchiveDiscoveryState.TERMINAL_FAILURE for item in states),
            exact_count - sum(item.state in completed for item in states), halted,
            halts[-1] if halts else None,
            tuple(sorted(states, key=lambda item: item.canonical_instrument_id)),
        )

    def _execute_unit(self, run_id: str, unit: BseFinancialAcquisitionUnit, *, attempt: int,
                      settings: BseFinancialAcquisitionSettings) -> BseFinancialAcquisitionReceipt:
        now = self._clock()
        if self._already_present(unit):
            return self._receipt(run_id, unit, attempt, now, BseAcquisitionUnitState.ALREADY_PRESENT, None, None, 0, 0, 0, None)
        mapping = BseSecurityMapping(unit.canonical_instrument_id, unit.isin, BseMappingStatus.EXACT, unit.bse_security_code,
                                     None, None, "BSE_EXACT_ISIN_LOOKUP", now, unit.fingerprint)
        identity = InstrumentIdentity(unit.canonical_instrument_id, Exchange.NSE, unit.nse_symbol, unit.nse_symbol,
                                      unit.isin, None, InstrumentType.NSE_EQUITY, unit.nse_symbol)
        for retry in range(settings.maximum_retries + 1):
            try:
                response = self._transport.fetch_xbrl(unit.metadata.xbrl_url)
                staged = self._staging.stage(mapping=mapping, metadata=unit.metadata, response=response)
                imported = self._importer.ingest_official_staged(identity, unit.bse_security_code, staged.path, metadata=unit.metadata)
                state = BseAcquisitionUnitState.ACCEPTED if imported.filing_outcome is FilingWriteOutcome.INSERTED else BseAcquisitionUnitState.ALREADY_PRESENT
                return self._receipt(run_id, unit, attempt, self._clock(), state, staged.disposition, imported.filing_outcome,
                                     imported.facts_inserted, imported.facts_duplicate, imported.facts_conflicted, None)
            except (BseCollectorError, BseOfficialError, ValueError) as error:
                state = _failure_state(error)
                if state is BseAcquisitionUnitState.RETRYABLE_FAILURE and retry < settings.maximum_retries:
                    self._sleeper(settings.retry_backoff_seconds * (retry + 1))
                    continue
                return self._receipt(run_id, unit, attempt, self._clock(), state, None, None, 0, 0, 0, _safe_error(error))
        raise AssertionError("BSE financial acquisition retry loop did not return")

    def _already_present(self, unit: BseFinancialAcquisitionUnit) -> bool:
        return any(
            filing.source_reference == unit.metadata.xbrl_url
            for filing in self._filings.list(instrument_id=unit.canonical_instrument_id, exchange=Exchange.BSE,
                                             filing_type=FilingType.FINANCIAL_RESULTS, limit=500)
        )

    def _receipt(self, run_id: str, unit: BseFinancialAcquisitionUnit, attempt: int, at: datetime,
                 state: BseAcquisitionUnitState, staged: BseStageDisposition | None,
                 filing: FilingWriteOutcome | None, inserted: int, duplicate: int, conflicts: int,
                 detail: str | None) -> BseFinancialAcquisitionReceipt:
        key = _digest((run_id, unit.unit_id, attempt, state.value, staged.value if staged else None,
                       filing.value if filing else None, inserted, duplicate, conflicts, detail))
        value = BseFinancialAcquisitionReceipt(
            "bse-financial-receipt:" + key[7:39], run_id, unit.unit_id, at, state, attempt, staged,
            filing, inserted, duplicate, conflicts, detail, key,
        )
        self._store.save_receipt(value)
        return value


def _inventory_mapping(item: NseEquityInstrument, mapping: BseSecurityMapping | None, as_of: datetime) -> BseNifty500Mapping:
    if mapping is None:
        state, reason, source = BseNifty500MappingState.UNSUPPORTED, "BSE_OFFICIAL_SECURITY_MASTER_UNAVAILABLE", "BSE_EXACT_ISIN_LOOKUP"
        code = security_id = security_name = None
    else:
        state = {
            BseMappingStatus.EXACT: BseNifty500MappingState.EXACT_VERIFIED,
            BseMappingStatus.NOT_FOUND: BseNifty500MappingState.UNMAPPED,
            BseMappingStatus.AMBIGUOUS: BseNifty500MappingState.CONFLICT,
            BseMappingStatus.CONFLICTED: BseNifty500MappingState.CONFLICT,
            BseMappingStatus.BLOCKED: BseNifty500MappingState.UNSUPPORTED,
        }[mapping.status]
        reason, source = mapping.reason, mapping.source_reference
        code, security_id, security_name = mapping.security_code, mapping.security_id, mapping.security_name
    fingerprint = _digest((item.instrument_id, item.symbol, item.isin, code, security_id, security_name, state.value, source, reason, MAPPING_POLICY_VERSION))
    return BseNifty500Mapping(item.instrument_id, item.symbol, item.isin, code, security_id, security_name,
                               as_of, state, source, reason, fingerprint)


def _unit_identity(instrument_id: str, code: str, metadata: BseResultMetadata) -> str:
    return _digest((instrument_id, code, metadata.xbrl_url, metadata.period_end.isoformat(), metadata.scope.value, PLAN_POLICY_VERSION))


def _discovery_run_id(inventory: BseNifty500MappingInventory) -> str:
    return "bse-financial-discovery-run:" + inventory.fingerprint[7:39]


def _metadata_key(value: BseResultMetadata) -> tuple[object, ...]:
    return (
        value.security_code, value.period_end.isoformat(), value.filing_at.isoformat(),
        value.period_type.value, value.scope.value, value.value_basis.value,
        value.xbrl_url, value.source_page,
    )


def _discovery_state_order(value: BseArchiveDiscoveryState) -> int:
    return {
        BseArchiveDiscoveryState.PENDING: 0,
        BseArchiveDiscoveryState.IN_PROGRESS: 1,
        BseArchiveDiscoveryState.DISCOVERED: 2,
        BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE: 2,
        BseArchiveDiscoveryState.RETRYABLE_FAILURE: 2,
        BseArchiveDiscoveryState.TERMINAL_FAILURE: 2,
    }[value]


def _discovery_order(value: BseArchiveDiscoveryCheckpoint) -> tuple[object, ...]:
    return (value.attempt, _discovery_state_order(value.state), value.attempted_at, value.checkpoint_id)


def _discovery_failure_classification(error: Exception) -> str:
    value = _safe_error(error)
    if "429" in value or "RATE_LIMIT" in value:
        return "BSE_RATE_LIMIT"
    if "SOURCE_UNAVAILABLE" in value:
        return "BSE_SOURCE_UNAVAILABLE"
    if "HTTP_STATUS_REJECTED" in value or "BLOCKED" in value:
        return "BSE_PROVIDER_BLOCKED"
    if any(token in value for token in ("MALFORMED", "NOT_UTF8", "RESPONSE_EMPTY")):
        return "BSE_MALFORMED_ARCHIVE_RESPONSE"
    if any(token in value for token in ("TOO_LARGE", "INVALID", "SECURITY_CODE")):
        return "BSE_ARCHIVE_TERMINAL_FAILURE"
    return "BSE_ARCHIVE_RETRYABLE_FAILURE"


def _provider_degradation(classification: str) -> bool:
    return classification in {
        "BSE_RATE_LIMIT", "BSE_SOURCE_UNAVAILABLE", "BSE_PROVIDER_BLOCKED",
        "BSE_MALFORMED_ARCHIVE_RESPONSE",
    }


def _discovery_failure_state(error: Exception) -> BseArchiveDiscoveryState:
    classification = _discovery_failure_classification(error)
    if classification == "BSE_ARCHIVE_TERMINAL_FAILURE":
        return BseArchiveDiscoveryState.TERMINAL_FAILURE
    return BseArchiveDiscoveryState.RETRYABLE_FAILURE


def _mapping_key(value: BseNifty500Mapping) -> tuple[object, ...]:
    return (value.canonical_instrument_id, value.nse_symbol, value.isin, value.bse_security_code,
            value.bse_security_id, value.bse_security_name, value.state.value, value.source_reference, value.reason)


def _failure_state(error: Exception) -> BseAcquisitionUnitState:
    value = str(error)
    if "SOURCE_UNAVAILABLE" in value or "HTTP_STATUS_REJECTED" in value:
        return BseAcquisitionUnitState.UNAVAILABLE
    if any(token in value for token in ("IDENTITY", "SCOPE", "PERIOD", "SIGNATURE", "ROOT", "MALFORMED", "NOT_XBRL")):
        return BseAcquisitionUnitState.QUARANTINED
    if "TOO_LARGE" in value:
        return BseAcquisitionUnitState.TERMINAL_FAILURE
    return BseAcquisitionUnitState.RETRYABLE_FAILURE


def _safe_error(error: Exception) -> str:
    # Existing BSE exceptions are stable codes.  Preserve just that code rather
    # than a URL or raw provider body which could grow into an unsafe log path.
    text = str(error)
    return text if text.startswith("BSE_") and len(text) <= 160 else type(error).__name__


def _run_report(run_id: str, plan_id: str, receipts: tuple[BseFinancialAcquisitionReceipt, ...], halted: bool) -> BseFinancialAcquisitionRunReport:
    counts = {state: sum(item.state is state for item in receipts) for state in BseAcquisitionUnitState}
    return BseFinancialAcquisitionRunReport(
        run_id, plan_id, len(receipts), counts[BseAcquisitionUnitState.ACCEPTED],
        counts[BseAcquisitionUnitState.ALREADY_PRESENT], counts[BseAcquisitionUnitState.QUARANTINED],
        counts[BseAcquisitionUnitState.UNAVAILABLE], counts[BseAcquisitionUnitState.RETRYABLE_FAILURE],
        counts[BseAcquisitionUnitState.TERMINAL_FAILURE], halted, receipts,
    )


def _fingerprint(value: object) -> str:
    return _digest(repr(value))


def _digest(value: object) -> str:
    raw = json.dumps(value, default=_json_default, sort_keys=True, separators=(",", ":"))
    return "sha256:" + sha256(raw.encode("utf-8")).hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: getattr(value, key) for key in value.__dataclass_fields__}
    raise TypeError(type(value).__name__)


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("BSE_FINANCIAL_ACQUISITION_AS_OF_TIMEZONE_REQUIRED")


__all__ = (
    "BseAcquisitionUnitState", "BseArchiveDiscoveryCheckpoint", "BseArchiveDiscoveryIncompleteError",
    "BseArchiveDiscoveryReport", "BseArchiveDiscoveryState", "BseFinancialAcquisitionRunReport",
    "BseFinancialAcquisitionSettings", "BseFinancialAcquisitionStore", "BseFinancialAcquisitionUnit", "BseFinancialAcquisitionPlan",
    "BseNifty500FinancialAcquisitionOrchestrator", "BseNifty500Mapping", "BseNifty500MappingInventory",
    "BseNifty500MappingState", "BseProviderHaltReceipt", "MAXIMUM_FILING_DEPTH", "MAPPING_POLICY_VERSION", "PLAN_POLICY_VERSION",
)
