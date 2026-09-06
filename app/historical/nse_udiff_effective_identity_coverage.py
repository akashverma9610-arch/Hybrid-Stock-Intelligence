"""Compact, effective-dated NSE UDiFF identity and action-window evidence.

This is a deliberately narrow metadata boundary.  It turns retained, exact
UDiFF source observations into maximal *session-contiguous* identity
intervals.  It does not rewrite OHLCV, select a technical series, derive an
indicator, adjust a price, or activate a reader.  A compact interval proves
addressability only; the existing daily certifier remains responsible for
series, price, and volume-continuity decisions.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable, Protocol

from app.historical.nse_corporate_action_coverage import (
    NseCorporateActionIdentityStatus, NseCorporateActionObservation,
    NseCorporateActionQueryReceipt, NseCorporateActionQueryStatus,
)
from app.historical.nse_udiff_identity_promotion import NseUdiffHistoricalSourceIdentityInterval
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction
from app.market_data.nse_udiff_daily_history import NSE_UDIFF_SOURCE_FAMILY, NSE_UDIFF_SOURCE_VERSION
from app.market_data.nse_udiff_source_identity import source_fields
from app.market_data.models import CanonicalOHLCVBar
from app.market_data.technical_source_basis_action_coverage import (
    CorporateActionCoverageAssertion, CorporateActionCoverageReason, CorporateActionCoverageState, SourceBasisEvidence,
    create_corporate_action_coverage_assertion,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


CONTRACT_ID = "nse-udiff-effective-dated-identity-and-action-window-coverage"
CONTRACT_VERSION = "v1"
IDENTITY_POLICY_ID = "nse-udiff-exact-isin-effective-identity-coverage"
ACTION_POLICY_ID = "nse-udiff-exchange-wide-action-window-coverage"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseUdiffEffectiveIdentityCoverageState(StrEnum):
    READY = "READY"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    CONTRARY_LIFECYCLE_EVIDENCE = "CONTRARY_LIFECYCLE_EVIDENCE"


class NseUdiffActionWindowCoverageState(StrEnum):
    READY = "READY"
    IDENTITY_COVERAGE_REQUIRED = "IDENTITY_COVERAGE_REQUIRED"
    QUERY_COVERAGE_INCOMPLETE = "QUERY_COVERAGE_INCOMPLETE"
    SOURCE_KNOWN_AFTER_AS_OF = "SOURCE_KNOWN_AFTER_AS_OF"


class NseUdiffCorporateActionIdentityMappingState(StrEnum):
    EXACT_MAPPED = "EXACT_MAPPED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    IDENTITY_CONFLICT = "IDENTITY_CONFLICT"


@dataclass(frozen=True, slots=True)
class NseUdiffIdentityAnchor:
    """The approved current exact-ISIN anchor; a symbol is never an anchor."""
    canonical_instrument_id: str
    isin: str
    anchor_snapshot_id: str
    anchor_snapshot_fingerprint: str

    def __post_init__(self) -> None:
        if (not _ID.fullmatch(self.canonical_instrument_id) or not _isin(self.isin)
                or not _ID.fullmatch(self.anchor_snapshot_id) or not _FP.fullmatch(self.anchor_snapshot_fingerprint)):
            raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_ANCHOR_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffIdentitySourceObservation:
    """One retained exact source row, kept in-memory while intervals are built."""
    canonical_instrument_id: str
    isin: str
    fin_instrm_id: str
    source_symbol: str
    source_series: str
    trade_date: date
    session_id: str
    source_observation_id: str
    source_artifact_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if (not _ID.fullmatch(self.canonical_instrument_id) or not _isin(self.isin)
                or not self.fin_instrm_id.isdigit() or not self.source_symbol or not self.source_series
                or not self.session_id or not self.source_observation_id.startswith("nse-udiff-source-row:")
                or not _ID.fullmatch(self.source_artifact_id) or not _aware(self.observed_at)):
            raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SOURCE_OBSERVATION_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffEffectiveIdentityInterval:
    """A compact maximal run.  It intentionally retains no one-row payload list."""
    interval_id: str
    canonical_instrument_id: str
    isin: str
    fin_instrm_id: str
    source_symbol: str
    source_series: str
    observed_trade_start: date
    observed_trade_end: date
    source_session_start: str
    source_session_end: str
    source_observation_count: int
    first_source_observation_id: str
    last_source_observation_id: str
    source_lineage_fingerprint: str
    source_artifact_fingerprint: str
    anchor_snapshot_id: str
    anchor_snapshot_fingerprint: str
    known_at: datetime
    historical_known_at: None
    coverage_state: NseUdiffEffectiveIdentityCoverageState
    blocker_codes: tuple[str, ...]
    source_family: str
    source_version: str
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _interval_payload(self)
        if (
            not self.interval_id.startswith("nse-udiff-effective-identity:")
            or not _ID.fullmatch(self.canonical_instrument_id) or not _isin(self.isin)
            or not self.fin_instrm_id.isdigit() or not self.source_symbol or not self.source_series
            or self.observed_trade_start > self.observed_trade_end or not self.source_session_start or not self.source_session_end
            or self.source_observation_count < 1
            or not self.first_source_observation_id.startswith("nse-udiff-source-row:")
            or not self.last_source_observation_id.startswith("nse-udiff-source-row:")
            or not _FP.fullmatch(self.source_lineage_fingerprint) or not _FP.fullmatch(self.source_artifact_fingerprint)
            or not _ID.fullmatch(self.anchor_snapshot_id) or not _FP.fullmatch(self.anchor_snapshot_fingerprint)
            or not _aware(self.known_at) or self.historical_known_at is not None
            or self.coverage_state is not NseUdiffEffectiveIdentityCoverageState.READY
            or self.blocker_codes or (self.source_family, self.source_version, self.policy_version)
            != (NSE_UDIFF_SOURCE_FAMILY, NSE_UDIFF_SOURCE_VERSION, POLICY_VERSION)
            or self.fingerprint != _fp(values)
        ):
            raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffEffectiveIdentityCoverageReceipt:
    receipt_id: str
    anchor_snapshot_id: str
    anchor_snapshot_fingerprint: str
    session_manifest_id: str
    session_manifest_fingerprint: str
    source_observation_count: int
    legacy_source_observation_count: int
    compact_source_observation_count: int
    unresolved_source_observation_count: int
    compact_interval_count: int
    interval_set_fingerprint: str
    known_at: datetime
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _receipt_payload(self)
        counts = (self.source_observation_count, self.legacy_source_observation_count,
                  self.compact_source_observation_count, self.unresolved_source_observation_count, self.compact_interval_count)
        if (
            not self.receipt_id.startswith("nse-udiff-effective-identity-receipt:")
            or not _ID.fullmatch(self.anchor_snapshot_id) or not _FP.fullmatch(self.anchor_snapshot_fingerprint)
            or not _ID.fullmatch(self.session_manifest_id) or not _FP.fullmatch(self.session_manifest_fingerprint)
            or min(counts) < 0 or self.source_observation_count != self.legacy_source_observation_count + self.compact_source_observation_count + self.unresolved_source_observation_count
            or not _FP.fullmatch(self.interval_set_fingerprint) or not _aware(self.known_at)
            or self.policy_version != POLICY_VERSION or self.fingerprint != _fp(values)
        ):
            raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffEffectiveIdentityCoveragePlan:
    intervals: tuple[NseUdiffEffectiveIdentityInterval, ...]
    receipt: NseUdiffEffectiveIdentityCoverageReceipt

    def __post_init__(self) -> None:
        if self.intervals != tuple(sorted(self.intervals, key=lambda item: item.interval_id)) or len({item.interval_id for item in self.intervals}) != len(self.intervals):
            raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_PLAN_NONDETERMINISTIC")


class IdentityInterval(Protocol):
    interval_id: str
    fingerprint: str
    canonical_instrument_id: str
    isin: str
    fin_instrm_id: str
    source_symbol: str
    source_series: str
    observed_trade_start: date
    observed_trade_end: date


class NseUdiffEffectiveIdentityCoverageIndex:
    """Keyed interval resolver; it never scans every receipt for each bar."""
    def __init__(self, intervals: Iterable[IdentityInterval]) -> None:
        mapping: dict[tuple[str, str, str, str, str], list[IdentityInterval]] = {}
        for interval in intervals:
            key = (interval.canonical_instrument_id, interval.isin.upper(), interval.fin_instrm_id,
                   interval.source_symbol, interval.source_series)
            mapping.setdefault(key, []).append(interval)
        self._values = {key: tuple(sorted(value, key=lambda item: (item.observed_trade_start, item.observed_trade_end, item.interval_id))) for key, value in mapping.items()}
        self._by_canonical = {
            instrument: tuple(sorted(
                (item for key, values in self._values.items() if key[0] == instrument for item in values),
                key=lambda item: item.interval_id,
            ))
            for instrument in sorted({key[0] for key in self._values})
        }
    def resolve_candidates(self, *, canonical_instrument_id: str, isin: str, fin_instrm_id: str, source_symbol: str, source_series: str, trade_date: date, source_observation_id: str) -> tuple[IdentityInterval, ...]:
        key = (canonical_instrument_id, isin.upper(), fin_instrm_id, source_symbol, source_series)
        values = self._values.get(key, ())
        starts = [item.observed_trade_start for item in values]
        position = bisect_right(starts, trade_date)
        candidates = []
        for interval in values[:position]:
            if not interval.observed_trade_start <= trade_date <= interval.observed_trade_end: continue
        # Legacy intervals explicitly retain row identifiers.  Compact intervals
        # prove the same identity through an ordered source-lineage digest.
            row_ids = getattr(interval, "source_observation_ids", None)
            if row_ids is None or source_observation_id in row_ids: candidates.append(interval)
        return tuple(candidates)

    def resolve(self, **kwargs) -> IdentityInterval | None:
        candidates = self.resolve_candidates(**kwargs)
        return candidates[0] if len(candidates) == 1 else None


def build_effective_identity_coverage_plan(
    *, observations: Iterable[NseUdiffIdentitySourceObservation], anchors: Iterable[NseUdiffIdentityAnchor],
    session_dates: Iterable[date], session_manifest_id: str, session_manifest_fingerprint: str,
    legacy_intervals: Iterable[NseUdiffHistoricalSourceIdentityInterval] = (),
    contrary_lifecycle_observation_ids: Iterable[str] = (),
) -> NseUdiffEffectiveIdentityCoveragePlan:
    """Build maximal exact-ISIN runs without a current-symbol fallback."""
    anchor_values = tuple(sorted(anchors, key=lambda item: item.canonical_instrument_id))
    anchors_by_isin = {item.isin.upper(): item for item in anchor_values}
    if len(anchors_by_isin) != len(anchor_values):
        raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_ANCHOR_AMBIGUOUS")
    dates = tuple(session_dates)
    if dates != tuple(sorted(set(dates))) or not dates:
        raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SESSION_MANIFEST_INVALID")
    if not _ID.fullmatch(session_manifest_id) or not _FP.fullmatch(session_manifest_fingerprint):
        raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SESSION_MANIFEST_INVALID")
    session_index = {item: index for index, item in enumerate(dates)}
    legacy_ids = {row_id for interval in legacy_intervals for row_id in interval.source_observation_ids}
    contrary = set(contrary_lifecycle_observation_ids)
    # The local retained corpus exceeds one million rows.  Consume the
    # date/source-id ordered iterator in one pass, retaining only active runs
    # (roughly one per current security), never an all-bar in-memory list.
    source_count = unresolved = compact_rows = legacy_count = 0
    known_at = datetime(1970, 1, 1, tzinfo=UTC)
    intervals: list[NseUdiffEffectiveIdentityInterval] = []
    active: dict[tuple[str, str, str, str, str, str], list[NseUdiffIdentitySourceObservation]] = {}

    def process_day(day_rows: list[NseUdiffIdentitySourceObservation]) -> None:
        nonlocal source_count, unresolved, compact_rows, legacy_count, known_at
        day = day_rows[0].trade_date
        if day not in session_index: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SESSION_REQUIRED")
        accepted: dict[tuple[str, str, str, str, str, str], NseUdiffIdentitySourceObservation] = {}
        for item in sorted(day_rows, key=lambda item: item.source_observation_id):
            source_count += 1; known_at = max(known_at, item.observed_at)
            if item.source_observation_id in legacy_ids:
                legacy_count += 1; continue
            anchor = anchors_by_isin.get(item.isin.upper())
            if anchor is None or item.source_observation_id in contrary or anchor.canonical_instrument_id != item.canonical_instrument_id:
                unresolved += 1; continue
            key = (anchor.canonical_instrument_id, anchor.isin.upper(), item.fin_instrm_id, item.source_symbol, item.source_series, anchor.anchor_snapshot_id)
            if key in accepted: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SOURCE_IDENTITY_DUPLICATE")
            accepted[key] = item; compact_rows += 1
        for key in tuple(sorted(active)):
            rows = active[key]
            if key not in accepted or session_index[day] != session_index[rows[-1].trade_date] + 1:
                intervals.append(_interval(tuple(rows), anchors_by_isin[key[1]])); del active[key]
        for key, item in accepted.items():
            active.setdefault(key, []).append(item)

    previous_date: date | None = None
    day_rows: list[NseUdiffIdentitySourceObservation] = []
    day_ids: set[str] = set()
    for item in observations:
        if previous_date is not None and item.trade_date < previous_date: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SOURCE_ORDER_REQUIRED")
        if previous_date is not None and item.trade_date != previous_date:
            process_day(day_rows); day_rows = []; day_ids = set()
        if item.source_observation_id in day_ids: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_SOURCE_DUPLICATE")
        day_ids.add(item.source_observation_id); day_rows.append(item); previous_date = item.trade_date
    if day_rows: process_day(day_rows)
    for key in tuple(sorted(active)):
        intervals.append(_interval(tuple(active[key]), anchors_by_isin[key[1]]))
    values = tuple(sorted(intervals, key=lambda item: item.interval_id))
    interval_set = _fp(tuple((item.interval_id, item.fingerprint) for item in values))
    receipt_values = dict(
        anchor_snapshot_id=anchor_values[0].anchor_snapshot_id if len({item.anchor_snapshot_id for item in anchor_values}) == 1 else "nse-udiff-multiple-anchor-snapshots",
        anchor_snapshot_fingerprint=_fp(tuple((item.anchor_snapshot_id, item.anchor_snapshot_fingerprint) for item in anchor_values)),
        session_manifest_id=session_manifest_id, session_manifest_fingerprint=session_manifest_fingerprint,
        source_observation_count=source_count, legacy_source_observation_count=legacy_count,
        compact_source_observation_count=compact_rows, unresolved_source_observation_count=unresolved,
        compact_interval_count=len(values), interval_set_fingerprint=interval_set, known_at=known_at, policy_version=POLICY_VERSION,
    )
    receipt_fp = _fp(receipt_values)
    receipt = NseUdiffEffectiveIdentityCoverageReceipt(
        receipt_id="nse-udiff-effective-identity-receipt:" + receipt_fp.removeprefix("sha256:")[:32], **receipt_values, fingerprint=receipt_fp,
    )
    return NseUdiffEffectiveIdentityCoveragePlan(values, receipt)


def _interval(rows: tuple[NseUdiffIdentitySourceObservation, ...], anchor: NseUdiffIdentityAnchor) -> NseUdiffEffectiveIdentityInterval:
    first, last = rows[0], rows[-1]
    values = dict(
        canonical_instrument_id=anchor.canonical_instrument_id, isin=anchor.isin.upper(), fin_instrm_id=first.fin_instrm_id,
        source_symbol=first.source_symbol, source_series=first.source_series,
        observed_trade_start=first.trade_date, observed_trade_end=last.trade_date,
        source_session_start=first.session_id, source_session_end=last.session_id,
        source_observation_count=len(rows), first_source_observation_id=first.source_observation_id,
        last_source_observation_id=last.source_observation_id,
        source_lineage_fingerprint=_fp(tuple(item.source_observation_id for item in rows)),
        source_artifact_fingerprint=_fp(tuple(sorted({item.source_artifact_id for item in rows}))),
        anchor_snapshot_id=anchor.anchor_snapshot_id, anchor_snapshot_fingerprint=anchor.anchor_snapshot_fingerprint,
        known_at=max(item.observed_at for item in rows), historical_known_at=None,
        coverage_state=NseUdiffEffectiveIdentityCoverageState.READY, blocker_codes=(),
        source_family=NSE_UDIFF_SOURCE_FAMILY, source_version=NSE_UDIFF_SOURCE_VERSION, policy_version=POLICY_VERSION,
    )
    fingerprint = _fp(values)
    return NseUdiffEffectiveIdentityInterval(
        interval_id="nse-udiff-effective-identity:" + fingerprint.removeprefix("sha256:")[:32], **values, fingerprint=fingerprint,
    )


class NseUdiffEffectiveIdentityCoverageStore:
    """Append-only compact metadata records in the established snapshot store."""
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def intervals(self) -> tuple[NseUdiffEffectiveIdentityInterval, ...]: return tuple(sorted((item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL) if isinstance(item.payload, NseUdiffEffectiveIdentityInterval)), key=lambda item: item.interval_id))
    def receipts(self) -> tuple[NseUdiffEffectiveIdentityCoverageReceipt, ...]: return tuple(sorted((item.payload for item in self._all(CoreApiSnapshotFamily.NSE_UDIFF_EFFECTIVE_IDENTITY_RECEIPT) if isinstance(item.payload, NseUdiffEffectiveIdentityCoverageReceipt)), key=lambda item: item.receipt_id))
    def save_plan(self, plan: NseUdiffEffectiveIdentityCoveragePlan) -> tuple[int, int, bool]:
        inserted = already = 0
        for value in plan.intervals:
            if self._save(value.interval_id, CoreApiSnapshotFamily.NSE_UDIFF_EFFECTIVE_IDENTITY_INTERVAL, value, value.known_at, value.fingerprint): inserted += 1
            else: already += 1
        return inserted, already, self._save(plan.receipt.receipt_id, CoreApiSnapshotFamily.NSE_UDIFF_EFFECTIVE_IDENTITY_RECEIPT, plan.receipt, plan.receipt.known_at, plan.receipt.fingerprint)
    def _save(self, identifier: str, family: CoreApiSnapshotFamily, value: object, at: datetime, fingerprint: str) -> bool:
        existing = self._repository.get_snapshot(identifier)
        if existing is not None:
            if existing.payload != value: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_IMMUTABILITY_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", type(value).__name__, fingerprint, at, value)); return True
    def _all(self, family: CoreApiSnapshotFamily):
        values = []; offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset); values.extend(page)
            if len(page) < 100: return tuple(values)
            offset += len(page)


@dataclass(frozen=True, slots=True)
class NseUdiffEffectiveIdentityCoverageReport:
    plan: NseUdiffEffectiveIdentityCoveragePlan
    intervals_inserted: int
    intervals_already_present: int
    receipt_inserted: bool


class NseUdiffEffectiveIdentityCoverageService:
    """Explicit local retained-source replay; it makes no network request."""
    def __init__(self, *, repository: CoreApiSnapshotRepository, observation_loader, anchors: Iterable[NseUdiffIdentityAnchor], session_dates: Iterable[date], session_manifest_id: str, session_manifest_fingerprint: str, legacy_intervals: Iterable[NseUdiffHistoricalSourceIdentityInterval]) -> None:
        self._repository = repository
        self._loader = observation_loader
        self._anchors = tuple(anchors)
        self._dates = tuple(session_dates)
        self._manifest_id = session_manifest_id
        self._manifest_fp = session_manifest_fingerprint
        self._legacy = tuple(legacy_intervals)

    def plan(self) -> NseUdiffEffectiveIdentityCoveragePlan:
        return build_effective_identity_coverage_plan(
            observations=self._loader(), anchors=self._anchors, session_dates=self._dates,
            session_manifest_id=self._manifest_id, session_manifest_fingerprint=self._manifest_fp,
            legacy_intervals=self._legacy,
        )

    def complete(self) -> NseUdiffEffectiveIdentityCoverageReport:
        plan = self.plan()
        inserted, already, receipt = NseUdiffEffectiveIdentityCoverageStore(self._repository).save_plan(plan)
        return NseUdiffEffectiveIdentityCoverageReport(plan, inserted, already, receipt)


def build_local_nse_udiff_effective_identity_coverage() -> tuple[NseUdiffEffectiveIdentityCoverageService, tuple[object, ...]]:
    """Compose a retained-archive-only local completion operation.

    It uses the frozen current-universe snapshot as the exact ISIN anchor and
    parses one immutable UDiFF archive at a time.  It imports no API/router,
    performs no provider call, and writes only compact snapshot metadata when
    ``complete`` is explicitly invoked.
    """
    from app.historical.nse_udiff_identity_promotion import _local_session_coverage
    from app.market_data.nse_udiff_daily_history import NseUdiffDailyHistoryStore, NseUdiffDailyTarget, _parse_valid_archive, nse_udiff_acquisition_id
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_LOCAL_SQLITE_REQUIRED")
    repository = create_core_api_snapshot_repository(settings)
    universe = CoreUniverseAnalysisStore(repository)
    snapshot = universe.latest_universe_snapshot()
    if snapshot is None: raise ValueError("NSE_UDIFF_EFFECTIVE_IDENTITY_UNIVERSE_SNAPSHOT_REQUIRED")
    snapshot_record = repository.get_snapshot("universe-snapshot:" + snapshot.snapshot_id)
    snapshot_fp = ("sha256:" + snapshot_record.fingerprint) if snapshot_record is not None and re.fullmatch(r"[0-9a-f]{64}", snapshot_record.fingerprint) else _fp({"snapshot": snapshot.snapshot_id, "checksum": snapshot.checksum})
    instruments = {item.instrument_id: item for item in universe.instruments_as_of(snapshot.as_of)}
    targets = tuple(NseUdiffDailyTarget.from_instrument(instruments[item]) for item in snapshot.instrument_ids if item in instruments)
    anchors = tuple(NseUdiffIdentityAnchor(item.canonical_instrument_id, item.isin, "universe-snapshot:" + snapshot.snapshot_id, snapshot_fp) for item in targets)
    acquisition_id = nse_udiff_acquisition_id(snapshot)
    history = NseUdiffDailyHistoryStore(repository)
    coverage = _local_session_coverage(repository, acquisition_id)
    valid_dates = tuple(item.trade_date for item in coverage.entries if getattr(item.state, "value", "") == "ARTIFACT_VALID_SESSION")
    targets_by_isin = {item.isin.upper(): item for item in targets}

    def observations():
        for artifact in history.iter_artifacts(acquisition_id):
            parsed = _parse_valid_archive(artifact)
            for row in parsed.rows:
                fields = {key: str(row.get(key, "")).strip() for key in ("TradDt", "BizDt", "FinInstrmId", "ISIN", "TckrSymb", "SctySrs", "SsnId")}
                target = targets_by_isin.get(fields["ISIN"].upper())
                if target is None or fields["TradDt"] != artifact.trade_date.isoformat() or fields["BizDt"] != fields["TradDt"]:
                    continue
                from app.market_data.nse_udiff_source_identity import source_row_id
                yield NseUdiffIdentitySourceObservation(
                    target.canonical_instrument_id, fields["ISIN"].upper(), fields["FinInstrmId"], fields["TckrSymb"], fields["SctySrs"],
                    artifact.trade_date, fields["SsnId"], source_row_id(fields), artifact.artifact_id, artifact.observed_at,
                )
    legacy_store = __import__("app.historical.nse_udiff_identity_promotion", fromlist=["NseUdiffHistoricalIdentityPromotionStore"]).NseUdiffHistoricalIdentityPromotionStore(repository)
    return NseUdiffEffectiveIdentityCoverageService(
        repository=repository, observation_loader=observations, anchors=anchors, session_dates=valid_dates,
        session_manifest_id=coverage.manifest_id, session_manifest_fingerprint=coverage.fingerprint, legacy_intervals=legacy_store.intervals(),
    ), (repository,)


@dataclass(frozen=True, slots=True)
class NseUdiffActionWindowCoverage:
    canonical_instrument_id: str
    window_start: date
    window_end: date
    state: NseUdiffActionWindowCoverageState
    query_receipt_ids: tuple[str, ...]
    query_receipt_fingerprints: tuple[str, ...]
    identity_interval_ids: tuple[str, ...]
    identity_interval_fingerprints: tuple[str, ...]
    action_ids: tuple[str, ...]
    action_fingerprints: tuple[str, ...]
    no_action_found_with_complete_query_coverage: bool
    source_known_at: datetime | None
    blocker_codes: tuple[str, ...]
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _action_payload(self)
        query_pairs = tuple(zip(self.query_receipt_ids, self.query_receipt_fingerprints, strict=True))
        identity_pairs = tuple(zip(self.identity_interval_ids, self.identity_interval_fingerprints, strict=True))
        action_pairs = tuple(zip(self.action_ids, self.action_fingerprints, strict=True))
        ready = self.state is NseUdiffActionWindowCoverageState.READY
        if (
            not _ID.fullmatch(self.canonical_instrument_id) or self.window_start > self.window_end
            or query_pairs != tuple(sorted(set(query_pairs))) or identity_pairs != tuple(sorted(set(identity_pairs))) or action_pairs != tuple(sorted(set(action_pairs)))
            or any(not _ID.fullmatch(value) for value in (*self.query_receipt_ids, *self.identity_interval_ids, *self.action_ids))
            or any(not _FP.fullmatch(value) for value in (*self.query_receipt_fingerprints, *self.identity_interval_fingerprints, *self.action_fingerprints))
            or (ready and (not self.query_receipt_ids or not self.identity_interval_ids or self.source_known_at is None or self.blocker_codes))
            or (self.no_action_found_with_complete_query_coverage != (ready and not self.action_ids))
            or (self.source_known_at is not None and not _aware(self.source_known_at))
            or self.blocker_codes != tuple(sorted(set(self.blocker_codes))) or self.policy_version != POLICY_VERSION or self.fingerprint != _fp(values)
        ): raise ValueError("NSE_UDIFF_ACTION_WINDOW_COVERAGE_INVALID")

    def assertion(self) -> CorporateActionCoverageAssertion | None:
        if self.state is not NseUdiffActionWindowCoverageState.READY or self.source_known_at is None: return None
        evidence = SourceBasisEvidence(
            "nse-udiff-action-window:" + self.fingerprint.removeprefix("sha256:")[:32],
            _fp({"coverage": self.fingerprint}), True,
        )
        return create_corporate_action_coverage_assertion(
            coverage_id="nse-udiff-action-window-coverage:" + self.fingerprint.removeprefix("sha256:")[:32],
            canonical_instrument_id=self.canonical_instrument_id,
            window_start=datetime.combine(self.window_start, datetime.min.time(), tzinfo=UTC),
            window_end=datetime.combine(self.window_end, datetime.max.time(), tzinfo=UTC),
            source_known_at=self.source_known_at, source_evidence=evidence,
            covered_action_kinds=tuple(CorporateActionKind),
            coverage_state=CorporateActionCoverageState.READY,
            reasons=(CorporateActionCoverageReason.OFFICIAL_SOURCE_WINDOW_COMPLETE,),
        )


def compose_action_window_coverage(*, canonical_instrument_id: str, window_start: date, window_end: date, identity_intervals: Iterable[IdentityInterval] | NseUdiffEffectiveIdentityCoverageIndex, query_receipts: Iterable[NseCorporateActionQueryReceipt], actions: Iterable[HistoricalCorporateAction], evaluation_as_of: datetime, required_sessions: Iterable[date] = ()) -> NseUdiffActionWindowCoverage:
    if not _aware(evaluation_as_of) or not _ID.fullmatch(canonical_instrument_id): raise ValueError("NSE_UDIFF_ACTION_WINDOW_INPUT_INVALID")
    index = identity_intervals if isinstance(identity_intervals, NseUdiffEffectiveIdentityCoverageIndex) else NseUdiffEffectiveIdentityCoverageIndex(identity_intervals)
    relevant_intervals = tuple(
        item for item in index._by_canonical.get(canonical_instrument_id, ())
        if item.observed_trade_start <= window_end and item.observed_trade_end >= window_start
    )
    required = tuple(required_sessions)
    if required != tuple(sorted(set(required))) or any(item < window_start or item > window_end for item in required):
        raise ValueError("NSE_UDIFF_ACTION_WINDOW_REQUIRED_SESSIONS_INVALID")
    complete_identity = bool(relevant_intervals) and all(any(item.observed_trade_start <= session <= item.observed_trade_end for item in relevant_intervals) for session in required)
    successes = tuple(sorted((item for item in query_receipts if item.status in {NseCorporateActionQueryStatus.SUCCESS_WITH_ACTIONS, NseCorporateActionQueryStatus.SUCCESS_EMPTY} and item.window.start_date <= window_end and item.window.end_date >= window_start), key=lambda item: (item.window.start_date, item.window.end_date, item.receipt_id)))
    complete = _dates_covered(window_start, window_end, tuple((item.window.start_date, item.window.end_date) for item in successes))
    source_known_at = max((item.observed_at for item in successes), default=None)
    state = NseUdiffActionWindowCoverageState.READY
    blockers: tuple[str, ...] = ()
    if not complete_identity: state, blockers = NseUdiffActionWindowCoverageState.IDENTITY_COVERAGE_REQUIRED, ("EFFECTIVE_IDENTITY_WINDOW_REQUIRED",)
    elif not complete: state, blockers = NseUdiffActionWindowCoverageState.QUERY_COVERAGE_INCOMPLETE, ("NSE_CORPORATE_ACTION_QUERY_WINDOW_INCOMPLETE",)
    elif source_known_at is None or source_known_at > evaluation_as_of: state, blockers = NseUdiffActionWindowCoverageState.SOURCE_KNOWN_AFTER_AS_OF, ("NSE_CORPORATE_ACTION_SOURCE_KNOWN_AFTER_EVALUATION",)
    relevant_actions = tuple(sorted((item for item in actions if item.canonical_instrument_id == canonical_instrument_id and window_start <= item.effective_date.date() <= window_end and item.eligible_as_of(evaluation_as_of)), key=lambda item: item.action_id))
    # The older acquisition contract stores its digest without a prefix;
    # normalize the *reference* here without changing that immutable receipt.
    query_pairs = tuple(sorted((item.receipt_id, item.fingerprint if item.fingerprint.startswith("sha256:") else "sha256:" + item.fingerprint) for item in successes))
    values = dict(canonical_instrument_id=canonical_instrument_id, window_start=window_start, window_end=window_end, state=state,
        query_receipt_ids=tuple(item[0] for item in query_pairs), query_receipt_fingerprints=tuple(item[1] for item in query_pairs),
        identity_interval_ids=tuple(item.interval_id for item in relevant_intervals), identity_interval_fingerprints=tuple(item.fingerprint for item in relevant_intervals),
        action_ids=tuple(item.action_id for item in relevant_actions), action_fingerprints=tuple(_action_fp(item) for item in relevant_actions),
        no_action_found_with_complete_query_coverage=(state is NseUdiffActionWindowCoverageState.READY and not relevant_actions), source_known_at=source_known_at,
        blocker_codes=blockers, policy_version=POLICY_VERSION)
    return NseUdiffActionWindowCoverage(**values, fingerprint=_fp(values))


def exact_action_observation_maps_to_interval(*, canonical_instrument_id: str, isin: str, symbol: str, series: str, token: str, effective_date: date, intervals: Iterable[IdentityInterval]) -> bool:
    """Strict helper for action remapping; absent exact fields never become a match."""
    return NseUdiffEffectiveIdentityCoverageIndex(intervals).resolve(canonical_instrument_id=canonical_instrument_id, isin=isin, fin_instrm_id=token, source_symbol=symbol, source_series=series, trade_date=effective_date, source_observation_id="nse-udiff-source-row:action-mapping-proof") is not None


@dataclass(frozen=True, slots=True)
class NseUdiffCorporateActionIdentityMapping:
    """An additive link to an old raw action observation, never an overwrite."""
    mapping_id: str
    observation_id: str
    observation_fingerprint: str
    canonical_instrument_id: str | None
    identity_interval_ids: tuple[str, ...]
    identity_interval_fingerprints: tuple[str, ...]
    state: NseUdiffCorporateActionIdentityMappingState
    blocker_codes: tuple[str, ...]
    source_known_at: datetime
    policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        pairs = tuple(zip(self.identity_interval_ids, self.identity_interval_fingerprints, strict=True))
        mapped = self.state is NseUdiffCorporateActionIdentityMappingState.EXACT_MAPPED
        values = _mapping_payload(self)
        if (
            not self.mapping_id.startswith("nse-udiff-action-identity-mapping:") or not _ID.fullmatch(self.observation_id)
            or not _FP.fullmatch(self.observation_fingerprint) or pairs != tuple(sorted(set(pairs)))
            or any(not _ID.fullmatch(identifier) or not _FP.fullmatch(fingerprint) for identifier, fingerprint in pairs)
            or (mapped != (self.canonical_instrument_id is not None)) or (mapped and (len(pairs) != 1 or self.blocker_codes))
            or (not mapped and (pairs or self.canonical_instrument_id is not None or not self.blocker_codes))
            or self.blocker_codes != tuple(sorted(set(self.blocker_codes))) or not _aware(self.source_known_at)
            or self.policy_version != POLICY_VERSION or self.fingerprint != _fp(values)
        ): raise ValueError("NSE_UDIFF_CORPORATE_ACTION_IDENTITY_MAPPING_INVALID")


def map_unresolved_corporate_action_observations_exact(*, observations: Iterable[NseCorporateActionObservation], identity_intervals: Iterable[IdentityInterval] | NseUdiffEffectiveIdentityCoverageIndex) -> tuple[NseUdiffCorporateActionIdentityMapping, ...]:
    """Resolve only exact retained action fields; missing token is never guessed.

    The official action source does not expose the UDiFF token.  Therefore a
    mapping is permitted only when ISIN, source symbol, series, effective date,
    and the interval chronology identify exactly one interval.  Multiple token
    intervals remain a typed conflict rather than a current-symbol fallback.
    """
    index = identity_intervals if isinstance(identity_intervals, NseUdiffEffectiveIdentityCoverageIndex) else NseUdiffEffectiveIdentityCoverageIndex(identity_intervals)
    results: list[NseUdiffCorporateActionIdentityMapping] = []
    for observation in sorted(observations, key=lambda item: item.observation_id):
        if observation.identity_status is not NseCorporateActionIdentityStatus.IDENTITY_UNRESOLVED: continue
        candidates: tuple[IdentityInterval, ...] = ()
        if observation.isin and observation.series and observation.ex_date:
            candidates = tuple(sorted(
                (interval for values in index._values.values() for interval in values
                 if interval.isin.upper() == observation.isin.upper()
                 and interval.source_symbol == observation.symbol
                 and interval.source_series == observation.series
                 and interval.observed_trade_start <= observation.ex_date.date() <= interval.observed_trade_end),
                key=lambda item: item.interval_id,
            ))
        if len(candidates) == 1:
            state, canonical, blockers = NseUdiffCorporateActionIdentityMappingState.EXACT_MAPPED, candidates[0].canonical_instrument_id, ()
        elif len(candidates) > 1:
            state, canonical, blockers = NseUdiffCorporateActionIdentityMappingState.IDENTITY_CONFLICT, None, ("NSE_UDIFF_ACTION_IDENTITY_AMBIGUOUS",)
        else:
            state, canonical, blockers = NseUdiffCorporateActionIdentityMappingState.IDENTITY_UNRESOLVED, None, ("NSE_UDIFF_ACTION_EXACT_IDENTITY_REQUIRED",)
        pairs = tuple((item.interval_id, item.fingerprint) for item in candidates) if state is NseUdiffCorporateActionIdentityMappingState.EXACT_MAPPED else ()
        observation_fp = observation.fingerprint if observation.fingerprint.startswith("sha256:") else "sha256:" + observation.fingerprint
        values = dict(observation_id=observation.observation_id, observation_fingerprint=observation_fp,
            canonical_instrument_id=canonical, identity_interval_ids=tuple(item[0] for item in pairs), identity_interval_fingerprints=tuple(item[1] for item in pairs),
            state=state, blocker_codes=blockers, source_known_at=observation.observed_at, policy_version=POLICY_VERSION)
        fp = _fp(values)
        results.append(NseUdiffCorporateActionIdentityMapping("nse-udiff-action-identity-mapping:" + fp.removeprefix("sha256:")[:32], **values, fingerprint=fp))
    return tuple(results)


def _dates_covered(start: date, end: date, windows: tuple[tuple[date, date], ...]) -> bool:
    cursor = start
    for low, high in sorted(windows):
        if high < cursor: continue
        if low > cursor: return False
        cursor = date.fromordinal(max(cursor.toordinal(), high.toordinal() + 1))
        if cursor > end: return True
    return cursor > end


def _interval_payload(value: NseUdiffEffectiveIdentityInterval) -> dict[str, object]: return {name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"interval_id", "fingerprint"}}
def _receipt_payload(value: NseUdiffEffectiveIdentityCoverageReceipt) -> dict[str, object]: return {name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"receipt_id", "fingerprint"}}
def _action_payload(value: NseUdiffActionWindowCoverage) -> dict[str, object]: return {name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"}
def _mapping_payload(value: NseUdiffCorporateActionIdentityMapping) -> dict[str, object]: return {name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"mapping_id", "fingerprint"}}
def _action_fp(value: HistoricalCorporateAction) -> str: return _fp({"id": value.action_id, "instrument": value.canonical_instrument_id, "kind": value.kind.value, "effective": value.effective_date.isoformat(), "as_of": value.as_of.isoformat(), "revision": value.revision})
def _isin(value: str) -> bool: return bool(re.fullmatch(r"[A-Za-z0-9]{12}", value or ""))
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _normal(value: object):
    if isinstance(value, datetime): return value.astimezone(UTC).isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, tuple): return [_normal(item) for item in value]
    if isinstance(value, dict): return {str(key): _normal(item) for key, item in sorted(value.items())}
    return value
def _fp(value: object) -> str: return "sha256:" + sha256(json.dumps(_normal(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


__all__ = (
    "ACTION_POLICY_ID", "CONTRACT_ID", "CONTRACT_VERSION", "IDENTITY_POLICY_ID", "POLICY_VERSION",
    "IdentityInterval", "NseUdiffActionWindowCoverage", "NseUdiffActionWindowCoverageState", "NseUdiffCorporateActionIdentityMapping", "NseUdiffCorporateActionIdentityMappingState", "NseUdiffEffectiveIdentityCoverageIndex", "NseUdiffEffectiveIdentityCoveragePlan", "NseUdiffEffectiveIdentityCoverageReceipt", "NseUdiffEffectiveIdentityCoverageReport", "NseUdiffEffectiveIdentityCoverageService", "NseUdiffEffectiveIdentityCoverageState", "NseUdiffEffectiveIdentityCoverageStore", "NseUdiffEffectiveIdentityInterval", "NseUdiffIdentityAnchor", "NseUdiffIdentitySourceObservation", "build_effective_identity_coverage_plan", "build_local_nse_udiff_effective_identity_coverage", "compose_action_window_coverage", "exact_action_observation_maps_to_interval", "map_unresolved_corporate_action_observations_exact",
)
