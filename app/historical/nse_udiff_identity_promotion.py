"""Immutable, source-date UDiFF security-identity promotion.

This boundary turns retained NSE UDiFF source facts into effective-dated
historical-security receipts only when an exact current ISIN link, source
chronology, and the absence of contrary retained lifecycle evidence support
that link.  It deliberately does not select a technical series, certify any
price or volume continuity, or alter the raw source evidence.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Callable, Iterable, Iterator, Mapping

from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityMasterStore, HistoricalSecurityStatus
from app.market_data.historical import BarWriteOutcome, HistoricalBarConflictArtifact, HistoricalBarStore
from app.market_data.models import CanonicalOHLCVBar, Exchange, InstrumentIdentity, InstrumentType, MarketDataQualityValidator
from app.market_data.nse_udiff_daily_history import (
    NSE_UDIFF_SOURCE_FAMILY, NSE_UDIFF_SOURCE_VERSION, NseUdiffDailySourceArtifact,
    NseUdiffDailyTarget, _bar_from_row, _parse_valid_archive,
)
from app.market_data.nse_udiff_daily_integrity import (
    NseUdiffSessionCoverageManifest, NseUdiffSessionCoverageState,
)
from app.market_data.nse_udiff_source_identity import source_row_id
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


POLICY_ID = "nse-udiff-historical-security-identity-continuity-promotion"
POLICY_VERSION = "v1"
CONTRACT_ID = "nse-udiff-historical-source-security-identity"
CONTRACT_VERSION = "v1"
KNOWN_AT_SEMANTICS = "HSI_BACKFILL_RETRIEVAL_TIME_ONLY_HISTORICAL_DISSEMINATION_UNKNOWN"
SOURCE_DATE_SEMANTICS = "EXACT_NSE_UDIFF_TRADE_DATE_FACT"


class NseUdiffHistoricalIdentityState(StrEnum):
    SAME_SECURITY_SYMBOL_CHANGE_PROVEN = "SAME_SECURITY_SYMBOL_CHANGE_PROVEN"
    SAME_SECURITY_HISTORICAL_ALIAS_PROVEN = "SAME_SECURITY_HISTORICAL_ALIAS_PROVEN"
    SAME_ISIN_SERIES_VARIANT = "SAME_ISIN_SERIES_VARIANT"
    TOKEN_CHANGE_SAME_SECURITY_PROVEN = "TOKEN_CHANGE_SAME_SECURITY_PROVEN"
    SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY = "SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY"
    LIFECYCLE_BREAK = "LIFECYCLE_BREAK"
    CURRENT_CANONICAL_MAPPING_DEFECT = "CURRENT_CANONICAL_MAPPING_DEFECT"
    HISTORICAL_IDENTITY_UNRESOLVED = "HISTORICAL_IDENTITY_UNRESOLVED"


class NseUdiffPromotionOutcome(StrEnum):
    PROMOTED_ADDRESSABLE = "PROMOTED_ADDRESSABLE"
    STILL_BLOCKED = "STILL_BLOCKED"
    NO_OP_EXISTING = "NO_OP_EXISTING"
    UNEXPECTED_CONFLICT_OR_ERROR = "UNEXPECTED_CONFLICT_OR_ERROR"


@dataclass(frozen=True, slots=True)
class NseUdiffHistoricalSourceIdentityInterval:
    """One observed, source-date identity interval; no unobserved date is claimed."""

    interval_id: str
    canonical_instrument_id: str
    isin: str
    fin_instrm_id: str
    source_symbol: str
    source_series: str
    observed_trade_start: date
    observed_trade_end: date
    source_observation_ids: tuple[str, ...]
    source_artifact_ids: tuple[str, ...]
    source_session_ids: tuple[str, ...]
    session_coverage_fingerprints: tuple[str, ...]
    known_at: datetime
    historical_known_at: None
    source_family: str
    source_version: str
    source_date_semantics: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _interval_values(self)
        if (
            not self.interval_id.startswith("nse-udiff-identity-interval:")
            or not _canonical_id(self.canonical_instrument_id, self.isin)
            or not self.fin_instrm_id.isdigit() or not self.source_symbol or not self.source_series
            or self.observed_trade_start > self.observed_trade_end
            or not self.source_observation_ids or self.source_observation_ids != tuple(sorted(set(self.source_observation_ids)))
            or any(not value.startswith("nse-udiff-source-row:") for value in self.source_observation_ids)
            or not self.source_artifact_ids or self.source_artifact_ids != tuple(sorted(set(self.source_artifact_ids)))
            or not self.source_session_ids or self.source_session_ids != tuple(sorted(set(self.source_session_ids)))
            or not self.session_coverage_fingerprints or self.session_coverage_fingerprints != tuple(sorted(set(self.session_coverage_fingerprints)))
            or not _aware(self.known_at) or self.historical_known_at is not None
            or (self.source_family, self.source_version, self.source_date_semantics, self.policy_version)
            != (NSE_UDIFF_SOURCE_FAMILY, NSE_UDIFF_SOURCE_VERSION, SOURCE_DATE_SEMANTICS, POLICY_VERSION)
            or self.fingerprint != _fp(values)
        ):
            raise ValueError("NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffHistoricalIdentityPromotionReceipt:
    """One all-row-accounted continuity decision for a current/source alias pair."""

    receipt_id: str
    canonical_instrument_id: str
    current_isin: str
    current_symbol: str
    historical_source_symbol: str
    observed_trade_start: date
    observed_trade_end: date
    continuity_state: NseUdiffHistoricalIdentityState
    outcome: NseUdiffPromotionOutcome
    source_interval_ids: tuple[str, ...]
    historical_identity_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    current_support_source_observation_ids: tuple[str, ...]
    lifecycle_evidence_ids: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    series_technical_state: NseUdiffHistoricalIdentityState | None
    known_at: datetime
    historical_known_at: None
    source_family: str
    source_version: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _receipt_values(self)
        promoted = self.outcome in {NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE, NseUdiffPromotionOutcome.NO_OP_EXISTING}
        if (
            not self.receipt_id.startswith("nse-udiff-identity-promotion:")
            or not _canonical_id(self.canonical_instrument_id, self.current_isin)
            or not self.current_symbol or not self.historical_source_symbol
            or self.current_symbol == self.historical_source_symbol
            or self.observed_trade_start > self.observed_trade_end
            or not self.source_interval_ids or self.source_interval_ids != tuple(sorted(set(self.source_interval_ids)))
            or not self.source_observation_ids or self.source_observation_ids != tuple(sorted(set(self.source_observation_ids)))
            or self.current_support_source_observation_ids != tuple(sorted(set(self.current_support_source_observation_ids)))
            or self.historical_identity_ids != tuple(sorted(set(self.historical_identity_ids)))
            or self.lifecycle_evidence_ids != tuple(sorted(set(self.lifecycle_evidence_ids)))
            or self.blocker_codes != tuple(sorted(set(self.blocker_codes)))
            or (promoted and (not self.historical_identity_ids or self.blocker_codes))
            or (not promoted and (self.historical_identity_ids or not self.blocker_codes))
            or (self.continuity_state in {NseUdiffHistoricalIdentityState.LIFECYCLE_BREAK, NseUdiffHistoricalIdentityState.CURRENT_CANONICAL_MAPPING_DEFECT, NseUdiffHistoricalIdentityState.HISTORICAL_IDENTITY_UNRESOLVED} and promoted)
            or (self.series_technical_state not in {None, NseUdiffHistoricalIdentityState.SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY})
            or not _aware(self.known_at) or self.historical_known_at is not None
            or (self.source_family, self.source_version, self.policy_version) != (NSE_UDIFF_SOURCE_FAMILY, NSE_UDIFF_SOURCE_VERSION, POLICY_VERSION)
            or self.fingerprint != _fp(values)
        ):
            raise ValueError("NSE_UDIFF_HISTORICAL_IDENTITY_PROMOTION_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffHistoricalIdentityPromotionPlan:
    intervals: tuple[NseUdiffHistoricalSourceIdentityInterval, ...]
    identities: tuple[HistoricalSecurityIdentity, ...]
    receipts: tuple[NseUdiffHistoricalIdentityPromotionReceipt, ...]

    def __post_init__(self) -> None:
        if (
            self.intervals != tuple(sorted(self.intervals, key=lambda value: value.interval_id))
            or self.identities != tuple(sorted(self.identities, key=lambda value: value.identity_id))
            or self.receipts != tuple(sorted(self.receipts, key=lambda value: value.receipt_id))
            or len({value.interval_id for value in self.intervals}) != len(self.intervals)
            or len({value.identity_id for value in self.identities}) != len(self.identities)
            or len({value.receipt_id for value in self.receipts}) != len(self.receipts)
        ):
            raise ValueError("NSE_UDIFF_HISTORICAL_IDENTITY_PLAN_NONDETERMINISTIC")


@dataclass(frozen=True, slots=True)
class NseUdiffHistoricalIdentityPromotionReport:
    plan: NseUdiffHistoricalIdentityPromotionPlan
    intervals_inserted: int
    intervals_already_present: int
    identities_inserted: int
    identities_already_present: int
    receipts_inserted: int
    receipts_already_present: int
    source_rows_addressable: int
    source_rows_still_blocked: int
    bars_inserted: int
    bars_already_present: int
    bar_conflicts: int
    invalid_source_rows: int
    replay_errors: int


@dataclass(frozen=True, slots=True)
class _SourceFact:
    canonical_instrument_id: str
    current_symbol: str
    isin: str
    trade_date: date
    source_symbol: str
    series: str
    token: str
    session_id: str
    artifact_id: str
    observed_at: datetime
    source_observation_id: str


class NseUdiffHistoricalIdentityPromotionStore:
    """Append-only persistence for source intervals and continuity decisions."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def intervals(self) -> tuple[NseUdiffHistoricalSourceIdentityInterval, ...]:
        return tuple(sorted(
            (item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL)
             if isinstance(item.payload, NseUdiffHistoricalSourceIdentityInterval)),
            key=lambda item: item.interval_id,
        ))

    def receipts(self) -> tuple[NseUdiffHistoricalIdentityPromotionReceipt, ...]:
        return tuple(sorted(
            (item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_HISTORICAL_IDENTITY_PROMOTION_RECEIPT)
             if isinstance(item.payload, NseUdiffHistoricalIdentityPromotionReceipt)),
            key=lambda item: item.receipt_id,
        ))

    def save_interval(self, value: NseUdiffHistoricalSourceIdentityInterval) -> bool:
        return self._save(value.interval_id, CoreApiSnapshotFamily.NSE_UDIFF_HISTORICAL_IDENTITY_INTERVAL, value, value.known_at, value.fingerprint)

    def save_receipt(self, value: NseUdiffHistoricalIdentityPromotionReceipt) -> bool:
        return self._save(value.receipt_id, CoreApiSnapshotFamily.NSE_UDIFF_HISTORICAL_IDENTITY_PROMOTION_RECEIPT, value, value.known_at, value.fingerprint)

    def _save(self, identifier: str, family: CoreApiSnapshotFamily, value: object, created_at: datetime, fingerprint: str) -> bool:
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("NSE_UDIFF_HISTORICAL_IDENTITY_IMMUTABILITY_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", CONTRACT_ID, fingerprint, created_at, value))
        return True

    def _all(self, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


class NseUdiffHistoricalIdentityPromotionService:
    """A local explicit replay boundary; it performs no technical selection."""

    def __init__(
        self,
        *,
        repository: CoreApiSnapshotRepository,
        bars: HistoricalBarStore,
        artifacts: Iterable[NseUdiffDailySourceArtifact] | Callable[[], Iterable[NseUdiffDailySourceArtifact]],
        targets: Iterable[NseUdiffDailyTarget],
        session_coverage: NseUdiffSessionCoverageManifest,
        lifecycle_evidence: Iterable[object] = (),
    ) -> None:
        self._repository = repository
        self._bars = bars
        if callable(artifacts):
            self._artifact_loader: Callable[[], Iterable[NseUdiffDailySourceArtifact]] = artifacts
        else:
            # Fixtures and small explicitly supplied batches remain stable,
            # while the local archive operation injects a bounded iterator.
            fixed = tuple(sorted(artifacts, key=lambda item: (item.trade_date, item.artifact_id)))
            self._artifact_loader = lambda: fixed
        values = tuple(sorted(targets, key=lambda item: item.canonical_instrument_id))
        self._targets = {item.isin: item for item in values}
        if len(self._targets) != len(values):
            raise ValueError("NSE_UDIFF_PROMOTION_CURRENT_TARGET_ISIN_AMBIGUOUS")
        self._coverage = session_coverage
        self._lifecycle_evidence = tuple(lifecycle_evidence)
        if not self._targets:
            raise ValueError("NSE_UDIFF_PROMOTION_SOURCE_AND_TARGETS_REQUIRED")

    def plan(self) -> NseUdiffHistoricalIdentityPromotionPlan:
        return build_nse_udiff_historical_identity_promotion_plan(
            artifacts=self._artifacts(),
            targets=self._targets.values(),
            session_coverage=self._coverage,
            lifecycle_evidence=self._lifecycle_evidence,
        )

    def promote(self) -> NseUdiffHistoricalIdentityPromotionReport:
        plan = self.plan()
        store = NseUdiffHistoricalIdentityPromotionStore(self._repository)
        master = HistoricalSecurityMasterStore(self._repository)
        interval_inserted = sum(store.save_interval(value) for value in plan.intervals)
        identity_inserted = 0
        for value in plan.identities:
            previous = master.identity(value.identity_id)
            if previous is None:
                master.save_identity(value)
                identity_inserted += 1
            elif previous != value:
                raise ValueError("NSE_UDIFF_HISTORICAL_SECURITY_IDENTITY_IMMUTABILITY_CONFLICT")
        receipt_inserted = sum(store.save_receipt(value) for value in plan.receipts)
        replay = self._replay_addressable_source_rows(plan)
        source_rows_addressable = sum(len(item.source_observation_ids) for item in plan.receipts if item.outcome is NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE)
        source_rows_still_blocked = sum(len(item.source_observation_ids) for item in plan.receipts if item.outcome is NseUdiffPromotionOutcome.STILL_BLOCKED)
        return NseUdiffHistoricalIdentityPromotionReport(
            plan=plan,
            intervals_inserted=interval_inserted,
            intervals_already_present=len(plan.intervals) - interval_inserted,
            identities_inserted=identity_inserted,
            identities_already_present=len(plan.identities) - identity_inserted,
            receipts_inserted=receipt_inserted,
            receipts_already_present=len(plan.receipts) - receipt_inserted,
            source_rows_addressable=source_rows_addressable,
            source_rows_still_blocked=source_rows_still_blocked,
            **replay,
        )

    def _replay_addressable_source_rows(self, plan: NseUdiffHistoricalIdentityPromotionPlan) -> dict[str, int]:
        promoted_interval_ids = {
            interval_id
            for receipt in plan.receipts
            if receipt.outcome is NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE
            for interval_id in receipt.source_interval_ids
        }
        interval_by_source = {
            source_id: interval
            for interval in plan.intervals
            if interval.interval_id in promoted_interval_ids
            for source_id in interval.source_observation_ids
        }
        expected = sum(
            len(item.source_observation_ids)
            for item in plan.intervals if item.interval_id in promoted_interval_ids
        )
        if len(interval_by_source) != expected:
            raise ValueError("NSE_UDIFF_PROMOTION_SOURCE_INTERVAL_OVERLAP")
        inserted = already_present = conflicts = invalid = errors = 0
        for artifact in self._artifacts():
            parsed = _parse_valid_archive(artifact)
            candidates = []
            for index, row in enumerate(parsed.rows):
                source_id = _source_id(row)
                interval = interval_by_source.get(source_id)
                if interval is None:
                    continue
                target = _historical_target(interval)
                try:
                    bar, _ = _bar_from_row(artifact, parsed, index, row, target)
                    MarketDataQualityValidator.validate_bar(bar)
                except ValueError:
                    invalid += 1
                    continue
                candidates.append(bar)
            outcomes = _upsert_many(self._bars, candidates)
            for bar, outcome in zip(candidates, outcomes, strict=True):
                if outcome is BarWriteOutcome.INSERTED:
                    inserted += 1
                elif outcome is BarWriteOutcome.IDENTICAL:
                    already_present += 1
                else:
                    conflicts += 1
                    stored = self._bars.same_provider_bar(bar)
                    if stored is None:
                        errors += 1
                    else:
                        self._bars.save_conflict_artifact(HistoricalBarConflictArtifact.from_bars(
                            stored, bar, detected_at=artifact.observed_at, ingestion_run_id=POLICY_ID,
                        ))
        return dict(
            bars_inserted=inserted, bars_already_present=already_present,
            bar_conflicts=conflicts, invalid_source_rows=invalid, replay_errors=errors,
        )

    def _artifacts(self) -> Iterator[NseUdiffDailySourceArtifact]:
        yield from self._artifact_loader()


def build_nse_udiff_historical_identity_promotion_plan(
    *,
    artifacts: Iterable[NseUdiffDailySourceArtifact],
    targets: Iterable[NseUdiffDailyTarget],
    session_coverage: NseUdiffSessionCoverageManifest,
    lifecycle_evidence: Iterable[object] = (),
) -> NseUdiffHistoricalIdentityPromotionPlan:
    """Build a deterministic plan solely from retained exact source facts."""
    target_values = tuple(sorted(targets, key=lambda item: item.canonical_instrument_id))
    by_isin = {item.isin: item for item in target_values}
    if len(by_isin) != len(target_values):
        raise ValueError("NSE_UDIFF_PROMOTION_CURRENT_TARGET_ISIN_AMBIGUOUS")
    coverage_by_date = {item.trade_date: item for item in session_coverage.entries}
    valid_dates = tuple(item.trade_date for item in session_coverage.entries if item.state is NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION)
    valid_index = {value: index for index, value in enumerate(valid_dates)}
    if not valid_dates:
        raise ValueError("NSE_UDIFF_PROMOTION_SESSION_COVERAGE_REQUIRED")
    facts_by_pair: dict[tuple[str, str, str, str], list[_SourceFact]] = defaultdict(list)
    # One latest exact current-symbol source fact per ISIN/symbol/series/token
    # is sufficient to prove chronology.  Retaining every current source row
    # would deserialize the multi-gigabyte archive corpus into memory.
    current_support: dict[tuple[str, str, str, str], _SourceFact] = {}
    artifact_count = 0
    for artifact in artifacts:
        artifact_count += 1
        if artifact.trade_date not in valid_index:
            raise ValueError("NSE_UDIFF_PROMOTION_SESSION_COVERAGE_REQUIRED")
        parsed = _parse_valid_archive(artifact)
        for row in parsed.rows:
            isin = row["ISIN"].strip().upper()
            target = by_isin.get(isin)
            if target is None:
                continue
            fact = _fact(artifact, row, target)
            if fact.source_symbol == target.current_symbol:
                key = (isin, target.current_symbol, fact.series, fact.token)
                prior = current_support.get(key)
                if prior is None or (fact.trade_date, fact.source_observation_id) > (prior.trade_date, prior.source_observation_id):
                    current_support[key] = fact
            else:
                facts_by_pair[(target.canonical_instrument_id, target.current_symbol, fact.source_symbol, isin)].append(fact)
    if not artifact_count:
        raise ValueError("NSE_UDIFF_PROMOTION_SOURCE_AND_TARGETS_REQUIRED")
    intervals: list[NseUdiffHistoricalSourceIdentityInterval] = []
    identities: list[HistoricalSecurityIdentity] = []
    receipts: list[NseUdiffHistoricalIdentityPromotionReceipt] = []
    for pair_key, unsorted_facts in sorted(facts_by_pair.items()):
        canonical_id, current_symbol, old_symbol, isin = pair_key
        facts = tuple(sorted(unsorted_facts, key=lambda item: (item.trade_date, item.source_observation_id)))
        target = by_isin[isin]
        support = tuple(sorted(
            (fact for fact in current_support.values()
             if fact.isin == isin and fact.current_symbol == current_symbol
             and any(fact.series == prior.series and fact.token == prior.token and fact.trade_date > facts[-1].trade_date for prior in facts)),
            key=lambda item: (item.trade_date, item.source_observation_id),
        ))
        # A lifecycle event in the gap before the current-symbol support is
        # also contrary evidence.  Same-ISIN chronology cannot bridge it.
        pair_lifecycle = _contrary_lifecycle_evidence(
            lifecycle_evidence, isin, facts[0].trade_date,
            max((item.trade_date for item in support), default=facts[-1].trade_date),
        )
        state, blockers, series_state = _pair_state(target, facts, support, pair_lifecycle)
        pair_intervals = _intervals_for_pair(facts, coverage_by_date, valid_index)
        intervals.extend(pair_intervals)
        pair_identities = tuple(_historical_identity(value) for value in pair_intervals) if not blockers else ()
        identities.extend(pair_identities)
        receipt = _promotion_receipt(
            canonical_instrument_id=canonical_id, current_isin=isin, current_symbol=current_symbol,
            historical_source_symbol=old_symbol, facts=facts, intervals=pair_intervals,
            identities=pair_identities, state=state, blockers=blockers,
            current_support=support, lifecycle_evidence_ids=pair_lifecycle,
            series_technical_state=series_state,
        )
        receipts.append(receipt)
    return NseUdiffHistoricalIdentityPromotionPlan(
        tuple(sorted(intervals, key=lambda item: item.interval_id)),
        tuple(sorted(identities, key=lambda item: item.identity_id)),
        tuple(sorted(receipts, key=lambda item: item.receipt_id)),
    )


def build_local_nse_udiff_historical_identity_promotion() -> tuple[NseUdiffHistoricalIdentityPromotionService, tuple[object, ...]]:
    """Compose the explicit local replay; no network, API, or technical job is started."""
    from app.historical.bse_lifecycle import BseCompulsoryDelistedPdfRow, BsePrimaryLifecycleEvidence
    from app.historical.security_master import HistoricalCorporateAction, HistoricalSecurityIdentity
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.market_data.nse_udiff_daily_history import NseUdiffDailyHistoryStore, nse_udiff_acquisition_id
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE:
        raise ValueError("NSE_UDIFF_PROMOTION_LOCAL_SQLITE_REQUIRED")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    universe_store = CoreUniverseAnalysisStore(repository)
    snapshot = universe_store.latest_universe_snapshot()
    if snapshot is None:
        raise ValueError("NSE_UDIFF_CURRENT_UNIVERSE_SNAPSHOT_REQUIRED")
    instruments = {item.instrument_id: item for item in universe_store.instruments_as_of(snapshot.as_of)}
    targets = tuple(NseUdiffDailyTarget.from_instrument(instruments[item]) for item in snapshot.instrument_ids if item in instruments)
    acquisition_id = nse_udiff_acquisition_id(snapshot)
    evidence = NseUdiffDailyHistoryStore(repository)
    coverage = _local_session_coverage(repository, acquisition_id)
    lifecycle = tuple(
        item.payload
        for family in (
            CoreApiSnapshotFamily.HISTORICAL_SECURITY_LIFECYCLE_EVIDENCE,
            CoreApiSnapshotFamily.HISTORICAL_SECURITY_IDENTITY,
            CoreApiSnapshotFamily.HISTORICAL_CORPORATE_ACTION,
        )
        for item in _snapshots(repository, family)
        if isinstance(item.payload, (
            BsePrimaryLifecycleEvidence, BseCompulsoryDelistedPdfRow,
            HistoricalSecurityIdentity, HistoricalCorporateAction,
        ))
    )
    historical = SQLiteHistoricalBarStore(path)
    return NseUdiffHistoricalIdentityPromotionService(
        repository=repository, bars=historical,
        artifacts=lambda: evidence.iter_artifacts(acquisition_id), targets=targets,
        session_coverage=coverage, lifecycle_evidence=lifecycle,
    ), (historical, repository)


def _fact(artifact: NseUdiffDailySourceArtifact, row: Mapping[str, str], target: NseUdiffDailyTarget) -> _SourceFact:
    fields = _source_fields(row)
    if date.fromisoformat(fields["TradDt"]) != artifact.trade_date or fields["BizDt"] != fields["TradDt"]:
        raise ValueError("NSE_UDIFF_PROMOTION_SOURCE_DATE_MISMATCH")
    return _SourceFact(
        canonical_instrument_id=target.canonical_instrument_id, current_symbol=target.current_symbol,
        isin=fields["ISIN"].upper(), trade_date=artifact.trade_date, source_symbol=fields["TckrSymb"],
        series=fields["SctySrs"], token=fields["FinInstrmId"], session_id=fields["SsnId"],
        artifact_id=artifact.artifact_id,
        observed_at=artifact.observed_at, source_observation_id=source_row_id(fields),
    )


def _intervals_for_pair(
    facts: tuple[_SourceFact, ...], coverage_by_date: Mapping[date, object], valid_index: Mapping[date, int],
) -> tuple[NseUdiffHistoricalSourceIdentityInterval, ...]:
    grouped: dict[tuple[str, str], list[_SourceFact]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.series, fact.token)].append(fact)
    result: list[NseUdiffHistoricalSourceIdentityInterval] = []
    for (_, _), values in sorted(grouped.items()):
        rows = tuple(sorted(values, key=lambda item: (item.trade_date, item.source_observation_id)))
        runs: list[list[_SourceFact]] = [[]]
        previous_date: date | None = None
        for fact in rows:
            if fact.trade_date not in valid_index or coverage_by_date[fact.trade_date].state is not NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION:  # type: ignore[attr-defined]
                raise ValueError("NSE_UDIFF_PROMOTION_SESSION_COVERAGE_REQUIRED")
            if previous_date is not None and valid_index[fact.trade_date] > valid_index[previous_date] + 1:
                runs.append([])
            runs[-1].append(fact)
            previous_date = fact.trade_date
        for run in runs:
            result.append(_interval(tuple(run), coverage_by_date))
    return tuple(sorted(result, key=lambda item: item.interval_id))


def _interval(facts: tuple[_SourceFact, ...], coverage_by_date: Mapping[date, object]) -> NseUdiffHistoricalSourceIdentityInterval:
    first, last = facts[0], facts[-1]
    coverage = tuple(coverage_by_date[item.trade_date] for item in facts)
    values = dict(
        canonical_instrument_id=first.canonical_instrument_id, isin=first.isin, fin_instrm_id=first.token,
        source_symbol=first.source_symbol, source_series=first.series,
        observed_trade_start=first.trade_date, observed_trade_end=last.trade_date,
        source_observation_ids=tuple(sorted({item.source_observation_id for item in facts})),
        source_artifact_ids=tuple(sorted({item.artifact_id for item in facts})),
        source_session_ids=tuple(sorted({item.session_id for item in facts})),
        session_coverage_fingerprints=tuple(sorted({item.fingerprint for item in coverage})),
        known_at=max(item.observed_at for item in facts), historical_known_at=None,
        source_family=NSE_UDIFF_SOURCE_FAMILY, source_version=NSE_UDIFF_SOURCE_VERSION,
        source_date_semantics=SOURCE_DATE_SEMANTICS, policy_version=POLICY_VERSION,
    )
    fingerprint = _fp(values)
    return NseUdiffHistoricalSourceIdentityInterval(
        interval_id="nse-udiff-identity-interval:" + fingerprint.removeprefix("sha256:")[:32],
        **values, fingerprint=fingerprint,
    )


def _historical_identity(interval: NseUdiffHistoricalSourceIdentityInterval) -> HistoricalSecurityIdentity:
    start = datetime.combine(interval.observed_trade_start, datetime.min.time(), tzinfo=UTC)
    # The source proves the labelled trade date, not market-close timing.  The
    # half-open date interval is represented without extending it backward.
    end = datetime.combine(interval.observed_trade_end + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    identity_id = "nse-udiff-historical-security:" + interval.fingerprint.removeprefix("sha256:")[:32]
    return HistoricalSecurityIdentity(
        identity_id, interval.canonical_instrument_id, interval.isin, "NSE", interval.source_symbol,
        interval.source_series, None, None, start, end, start, end, HistoricalSecurityStatus.ACTIVE,
        NSE_UDIFF_SOURCE_FAMILY, interval.known_at, POLICY_VERSION, interval.interval_id,
        (
            "HISTORICAL_SOURCE_DATE_IDENTITY_FACT", "HISTORICALLY_KNOWN_TO_HSI_UNAVAILABLE",
            "IDENTITY_CONTINUITY_NOT_PRICE_CONTINUITY", "IDENTITY_CONTINUITY_NOT_VOLUME_CONTINUITY",
            "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE",
        ),
        source_fingerprint=interval.fingerprint,
    )


def _promotion_receipt(
    *, canonical_instrument_id: str, current_isin: str, current_symbol: str,
    historical_source_symbol: str, facts: tuple[_SourceFact, ...],
    intervals: tuple[NseUdiffHistoricalSourceIdentityInterval, ...],
    identities: tuple[HistoricalSecurityIdentity, ...], state: NseUdiffHistoricalIdentityState,
    blockers: tuple[str, ...], current_support: tuple[_SourceFact, ...],
    lifecycle_evidence_ids: tuple[str, ...], series_technical_state: NseUdiffHistoricalIdentityState | None,
) -> NseUdiffHistoricalIdentityPromotionReceipt:
    values = dict(
        canonical_instrument_id=canonical_instrument_id, current_isin=current_isin,
        current_symbol=current_symbol, historical_source_symbol=historical_source_symbol,
        observed_trade_start=facts[0].trade_date, observed_trade_end=facts[-1].trade_date,
        continuity_state=state,
        outcome=NseUdiffPromotionOutcome.PROMOTED_ADDRESSABLE if not blockers else NseUdiffPromotionOutcome.STILL_BLOCKED,
        source_interval_ids=tuple(sorted(item.interval_id for item in intervals)),
        historical_identity_ids=tuple(sorted(item.identity_id for item in identities)),
        source_observation_ids=tuple(sorted(item.source_observation_id for item in facts)),
        current_support_source_observation_ids=tuple(sorted(item.source_observation_id for item in current_support)),
        lifecycle_evidence_ids=lifecycle_evidence_ids, blocker_codes=blockers,
        series_technical_state=series_technical_state,
        known_at=max(item.observed_at for item in facts), historical_known_at=None,
        source_family=NSE_UDIFF_SOURCE_FAMILY, source_version=NSE_UDIFF_SOURCE_VERSION,
        policy_version=POLICY_VERSION,
    )
    fingerprint = _fp(values)
    return NseUdiffHistoricalIdentityPromotionReceipt(
        receipt_id="nse-udiff-identity-promotion:" + fingerprint.removeprefix("sha256:")[:32],
        **values, fingerprint=fingerprint,
    )


def _pair_state(
    target: NseUdiffDailyTarget, facts: tuple[_SourceFact, ...], support: tuple[_SourceFact, ...], lifecycle_evidence_ids: tuple[str, ...],
) -> tuple[NseUdiffHistoricalIdentityState, tuple[str, ...], NseUdiffHistoricalIdentityState | None]:
    if not _canonical_id(target.canonical_instrument_id, target.isin):
        return NseUdiffHistoricalIdentityState.CURRENT_CANONICAL_MAPPING_DEFECT, ("NSE_UDIFF_CURRENT_CANONICAL_ISIN_EXACT_REQUIRED",), None
    if lifecycle_evidence_ids:
        return NseUdiffHistoricalIdentityState.LIFECYCLE_BREAK, ("NSE_UDIFF_CONTRARY_LIFECYCLE_EVIDENCE",), None
    if not support:
        return NseUdiffHistoricalIdentityState.HISTORICAL_IDENTITY_UNRESOLVED, ("NSE_UDIFF_CURRENT_SYMBOL_CHRONOLOGY_REQUIRED",), None
    series = {item.series for item in facts}
    tokens = {item.token for item in facts}
    series_state = NseUdiffHistoricalIdentityState.SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY if len(series) > 1 else None
    if len(series) > 1:
        return NseUdiffHistoricalIdentityState.SAME_ISIN_SERIES_VARIANT, (), series_state
    if len(tokens) > 1:
        return NseUdiffHistoricalIdentityState.TOKEN_CHANGE_SAME_SECURITY_PROVEN, (), series_state
    return NseUdiffHistoricalIdentityState.SAME_SECURITY_SYMBOL_CHANGE_PROVEN, (), series_state


def _contrary_lifecycle_evidence(values: Iterable[object], isin: str, start: date, end: date) -> tuple[str, ...]:
    """Only exact ISIN lifecycle evidence may overturn same-ISIN chronology."""
    blocked: list[str] = []
    for value in values:
        if str(getattr(value, "isin", "")).upper() != isin:
            continue
        event = str(getattr(value, "event_type", getattr(value, "kind", getattr(value, "status", ""))))
        when = getattr(
            value, "effective_at",
            getattr(value, "delisted_at", getattr(value, "tradable_until", getattr(value, "listed_until", None))),
        )
        if not isinstance(when, datetime) or not start <= when.date() <= end:
            continue
        if (event.endswith("DELISTING") or event.endswith("MERGER_OR_CESSATION")
                or event.endswith("MERGER") or event.endswith("DEMERGER")
                or event.endswith("DELISTED") or event.endswith("INACTIVE")
                or type(value).__name__ == "BseCompulsoryDelistedPdfRow"):
            identifier = getattr(value, "evidence_id", getattr(value, "row_id", getattr(value, "identity_id", getattr(value, "action_id", None))))
            if isinstance(identifier, str):
                blocked.append(identifier)
    return tuple(sorted(set(blocked)))


def _historical_target(interval: NseUdiffHistoricalSourceIdentityInterval) -> NseUdiffDailyTarget:
    instrument = InstrumentIdentity(
        interval.canonical_instrument_id, Exchange.NSE, interval.source_symbol, interval.source_symbol,
        interval.isin, None, InstrumentType.NSE_EQUITY, None,
    )
    return NseUdiffDailyTarget(interval.canonical_instrument_id, interval.isin, interval.source_symbol, instrument)


def _local_session_coverage(repository: CoreApiSnapshotRepository, acquisition_id: str) -> NseUdiffSessionCoverageManifest:
    values = tuple(
        item.payload for item in _snapshots(repository, CoreApiSnapshotFamily.NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST)
        if isinstance(item.payload, NseUdiffSessionCoverageManifest) and item.payload.acquisition_id == acquisition_id
    )
    if not values:
        raise ValueError("NSE_UDIFF_PROMOTION_SESSION_COVERAGE_REQUIRED")
    return max(values, key=lambda item: (item.as_of, item.manifest_id))


def _snapshots(repository: CoreApiSnapshotRepository, family: CoreApiSnapshotFamily) -> tuple[CoreApiSnapshot, ...]:
    values: list[CoreApiSnapshot] = []
    offset = 0
    while True:
        page = repository.list_snapshots(family, limit=100, offset=offset)
        values.extend(page)
        if len(page) < 100:
            return tuple(values)
        offset += len(page)


def _source_fields(row: Mapping[str, str]) -> dict[str, str]:
    # Keep the retained exchange spelling exactly as published.  Matching to a
    # canonical current identity may normalize an ISIN separately, but the
    # source-row identity itself must never be rewritten at this boundary.
    return {key: str(row.get(key, "")).strip() for key in (
        "TradDt", "BizDt", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "SsnId",
    )}


def _source_id(row: Mapping[str, str]) -> str:
    return source_row_id(_source_fields(row))


def _upsert_many(store: HistoricalBarStore, bars: list[CanonicalOHLCVBar]) -> tuple[BarWriteOutcome, ...]:
    method = getattr(store, "upsert_many", None)
    if callable(method):
        return tuple(method(bars))
    return tuple(store.upsert(item) for item in bars)


def _interval_values(value: NseUdiffHistoricalSourceIdentityInterval) -> dict[str, object]:
    return {name: getattr(value, name) for name in (
        "canonical_instrument_id", "isin", "fin_instrm_id", "source_symbol", "source_series",
        "observed_trade_start", "observed_trade_end", "source_observation_ids", "source_artifact_ids",
        "source_session_ids", "session_coverage_fingerprints", "known_at", "historical_known_at",
        "source_family", "source_version", "source_date_semantics", "policy_version",
    )}


def _receipt_values(value: NseUdiffHistoricalIdentityPromotionReceipt) -> dict[str, object]:
    return {name: getattr(value, name) for name in (
        "canonical_instrument_id", "current_isin", "current_symbol", "historical_source_symbol",
        "observed_trade_start", "observed_trade_end", "continuity_state", "outcome", "source_interval_ids",
        "historical_identity_ids", "source_observation_ids", "current_support_source_observation_ids",
        "lifecycle_evidence_ids", "blocker_codes", "series_technical_state", "known_at",
        "historical_known_at", "source_family", "source_version", "policy_version",
    )}


def _fp(values: Mapping[str, object]) -> str:
    return "sha256:" + manifest_fingerprint(**values)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _canonical_id(value: str, isin: str) -> bool:
    return bool(value) and value == f"NSE:{isin}" and len(isin) == 12


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "KNOWN_AT_SEMANTICS", "NseUdiffHistoricalIdentityPromotionPlan",
    "NseUdiffHistoricalIdentityPromotionReceipt", "NseUdiffHistoricalIdentityPromotionReport",
    "NseUdiffHistoricalIdentityPromotionService", "NseUdiffHistoricalIdentityPromotionStore",
    "NseUdiffHistoricalIdentityState", "NseUdiffHistoricalSourceIdentityInterval", "NseUdiffPromotionOutcome",
    "POLICY_ID", "POLICY_VERSION", "SOURCE_DATE_SEMANTICS", "build_local_nse_udiff_historical_identity_promotion",
    "build_nse_udiff_historical_identity_promotion_plan",
)
