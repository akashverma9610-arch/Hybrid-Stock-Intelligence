"""Deterministic integrity facts for the retained NSE UDiFF daily backfill.

This is a read-only eligibility boundary.  It consumes immutable UDiFF
artifacts/receipts, existing first-party session evidence, and the existing
historical conflict ledger.  It neither fetches data, changes provider
precedence, rewrites OHLCV, derives adjusted prices, nor activates technical
indicators.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable, Mapping
from zoneinfo import ZoneInfo

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    TradingDayState,
)
from app.historical.security_identity_selector import (
    HistoricalSecurityIdentityResolution,
    HistoricalSecurityIdentityResolutionStatus,
)
from app.market_data.historical import HistoricalBarConflictArtifact
from app.market_data.nse_udiff_conflict_resolution import (
    NseUdiffConflictReconciliation, NseUdiffCurrentConflictState,
)
from app.market_data.models import CanonicalOHLCVBar, Timeframe
from app.market_data.nse_udiff_daily_history import (
    NSE_UDIFF_BAR_PROVIDER,
    NSE_UDIFF_END,
    NSE_UDIFF_START,
    NSE_UDIFF_SOURCE_FAMILY,
    NSE_UDIFF_SOURCE_VERSION,
    NseUdiffDailyAcquisitionReceipt,
    NseUdiffDailyHistoryStore,
    NseUdiffDailyStatus,
    nse_udiff_acquisition_id,
)


CONTRACT_ID = "nse-udiff-daily-history-integrity-and-continuity"
CONTRACT_VERSION = "v2"
POLICY_ID = "nse-udiff-daily-source-coverage-and-conflict-policy"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_ONE_PAISE = Decimal("0.01")
_NSE_SESSION_ZONE = ZoneInfo("Asia/Kolkata")


class NseUdiffSessionCoverageState(StrEnum):
    """A source-coverage fact, deliberately separate from technical use."""

    ARTIFACT_VALID_SESSION = "ARTIFACT_VALID_SESSION"
    CONFIRMED_NON_TRADING_DAY = "CONFIRMED_NON_TRADING_DAY"
    EXPECTED_SESSION_SOURCE_MISSING = "EXPECTED_SESSION_SOURCE_MISSING"
    HISTORICAL_SESSION_UNRESOLVED = "HISTORICAL_SESSION_UNRESOLVED"


class NseUdiffSourceGapClassification(StrEnum):
    CONFIRMED_EXCHANGE_HOLIDAY = "CONFIRMED_EXCHANGE_HOLIDAY"
    CONFIRMED_NON_TRADING_DAY = "CONFIRMED_NON_TRADING_DAY"
    CONFIRMED_SPECIAL_SESSION_DIFFERENCE = "CONFIRMED_SPECIAL_SESSION_DIFFERENCE"
    SOURCE_ARTIFACT_MISSING = "SOURCE_ARTIFACT_MISSING"
    SOURCE_RETRIEVAL_UNAVAILABLE = "SOURCE_RETRIEVAL_UNAVAILABLE"
    HISTORICAL_SESSION_UNRESOLVED = "HISTORICAL_SESSION_UNRESOLVED"


class NseUdiffConflictState(StrEnum):
    CONFLICT_FREE = "CONFLICT_FREE"
    CONFLICT_RESOLVED_BY_SOURCE_SEMANTICS = "CONFLICT_RESOLVED_BY_SOURCE_SEMANTICS"
    CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"


class NseUdiffConflictCause(StrEnum):
    INGESTION_KEY_COLLISION = "INGESTION_KEY_COLLISION"
    SAME_KEY_DIFFERING_OHLCV = "SAME_KEY_DIFFERING_OHLCV"
    SOURCE_ARTIFACT_DUPLICATION = "SOURCE_ARTIFACT_DUPLICATION"
    UNRESOLVED_SOURCE_CONFLICT = "UNRESOLVED_SOURCE_CONFLICT"


class NseUdiffDivergenceClassification(StrEnum):
    NO_OVERLAP = "NO_OVERLAP"
    EXACT_OR_NEAR_MATCH = "EXACT_OR_NEAR_MATCH"
    VOLUME_ONLY_MISMATCH = "VOLUME_ONLY_MISMATCH"
    CONSTANT_MULTIPLICATIVE_RATIO = "CONSTANT_MULTIPLICATIVE_RATIO"
    ONE_SESSION_DATE_SHIFT_SUSPECTED = "ONE_SESSION_DATE_SHIFT_SUSPECTED"
    FIELD_MAPPING_SUSPECTED = "FIELD_MAPPING_SUSPECTED"
    IRREGULAR_UNEXPLAINED = "IRREGULAR_UNEXPLAINED"


class NseUdiffDailySourceSelectionState(StrEnum):
    """Era-scoped selection provenance; never a fallback or provider merge."""

    SELECTED_UDIFF = "SELECTED_UDIFF"
    SERIES_SELECTION_NOT_ACTIVE = "SERIES_SELECTION_NOT_ACTIVE"
    OUT_OF_ERA = "OUT_OF_ERA"
    SOURCE_COVERAGE_UNAVAILABLE = "SOURCE_COVERAGE_UNAVAILABLE"
    CONFLICT_UNRESOLVED = "CONFLICT_UNRESOLVED"
    HISTORICAL_IDENTITY_UNRESOLVED = "HISTORICAL_IDENTITY_UNRESOLVED"
    UDIFF_BAR_INVALID = "UDIFF_BAR_INVALID"


@dataclass(frozen=True, slots=True)
class NseUdiffSessionCoverageEntry:
    trade_date: date
    state: NseUdiffSessionCoverageState
    artifact_id: str | None
    receipt_id: str | None
    source_gap: NseUdiffSourceGapClassification | None
    session_ids: tuple[str, ...]
    source_ids: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    reason: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        values = dict(
            trade_date=self.trade_date, state=self.state, artifact_id=self.artifact_id,
            receipt_id=self.receipt_id, source_gap=self.source_gap, session_ids=self.session_ids,
            source_ids=self.source_ids, source_fingerprints=self.source_fingerprints,
            reason=self.reason,
        )
        valid_artifact = self.state is NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION
        if (
            not isinstance(self.trade_date, date)
            or self.session_ids != tuple(sorted(set(self.session_ids)))
            or any(not _ID.fullmatch(item) for item in self.session_ids)
            or self.source_ids != tuple(sorted(set(self.source_ids)))
            or self.source_fingerprints != tuple(sorted(set(self.source_fingerprints)))
            or len(self.source_ids) != len(self.source_fingerprints)
            or (valid_artifact and (not self.artifact_id or not self.receipt_id or self.source_gap is not None or self.reason is not None))
            or (not valid_artifact and self.artifact_id is not None)
            or (not valid_artifact and self.source_gap is None)
            or (self.state is NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY and self.source_gap not in {NseUdiffSourceGapClassification.CONFIRMED_EXCHANGE_HOLIDAY, NseUdiffSourceGapClassification.CONFIRMED_NON_TRADING_DAY})
            or (self.state is NseUdiffSessionCoverageState.EXPECTED_SESSION_SOURCE_MISSING and self.source_gap not in {NseUdiffSourceGapClassification.SOURCE_ARTIFACT_MISSING, NseUdiffSourceGapClassification.SOURCE_RETRIEVAL_UNAVAILABLE, NseUdiffSourceGapClassification.CONFIRMED_SPECIAL_SESSION_DIFFERENCE})
            or (self.state is NseUdiffSessionCoverageState.HISTORICAL_SESSION_UNRESOLVED and self.source_gap is not NseUdiffSourceGapClassification.HISTORICAL_SESSION_UNRESOLVED)
            or self.fingerprint != _fingerprint(_coverage_entry_payload(values))
        ):
            raise ValueError("NSE_UDIFF_SESSION_COVERAGE_ENTRY_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffSessionCoverageManifest:
    manifest_id: str
    acquisition_id: str
    requested_dates: tuple[date, ...]
    entries: tuple[NseUdiffSessionCoverageEntry, ...]
    calendar_id: str
    calendar_fingerprint: str
    as_of: datetime
    source_family: str
    source_version: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        values = _manifest_values(self)
        entry_dates = tuple(item.trade_date for item in self.entries)
        if (
            not self.manifest_id.startswith("nse-udiff-session-coverage:")
            or not self.acquisition_id.startswith("nse-udiff-acquisition:")
            or not self.requested_dates
            or self.requested_dates != tuple(sorted(set(self.requested_dates)))
            or entry_dates != self.requested_dates
            or not _ID.fullmatch(self.calendar_id)
            or not _FP.fullmatch(self.calendar_fingerprint)
            or not _aware(self.as_of)
            or self.source_family != NSE_UDIFF_SOURCE_FAMILY
            or self.source_version != NSE_UDIFF_SOURCE_VERSION
            or (self.contract_id, self.contract_version) != (CONTRACT_ID, CONTRACT_VERSION)
            or self.fingerprint != _fingerprint(_manifest_payload(values))
        ):
            raise ValueError("NSE_UDIFF_SESSION_COVERAGE_MANIFEST_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffConflictAssessment:
    conflict_fingerprint: str
    canonical_instrument_id: str
    trade_date: date
    state: NseUdiffConflictState
    cause: NseUdiffConflictCause
    stored_provider_reference: str | None
    incoming_provider_reference: str | None
    source_identity: str
    differing_fields: tuple[str, ...]
    fingerprint: str
    reconciliation: NseUdiffConflictReconciliation | None = None

    def __post_init__(self) -> None:
        values = dict(
            conflict_fingerprint=self.conflict_fingerprint,
            canonical_instrument_id=self.canonical_instrument_id,
            trade_date=self.trade_date, state=self.state, cause=self.cause,
            stored_provider_reference=self.stored_provider_reference,
            incoming_provider_reference=self.incoming_provider_reference,
            source_identity=self.source_identity, differing_fields=self.differing_fields,
            reconciliation=self.reconciliation,
        )
        if self.reconciliation is not None:
            self.reconciliation.__post_init__()
            artifact = self.reconciliation.artifact
            if (artifact.conflict_fingerprint != self.conflict_fingerprint
                    or artifact.canonical_instrument_id != self.canonical_instrument_id
                    or _nse_trade_date(artifact.start_time) != self.trade_date):
                raise ValueError("NSE_UDIFF_CONFLICT_RECONCILIATION_BINDING_INVALID")
        resolved = (self.reconciliation is not None and self.reconciliation.state
                    is NseUdiffCurrentConflictState.RESOLVED_STRUCTURAL_CONFLICT)
        if (
            not _HEX.fullmatch(self.conflict_fingerprint)
            or not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.trade_date, date)
            or self.state is not (NseUdiffConflictState.CONFLICT_RESOLVED_BY_SOURCE_SEMANTICS
                                 if resolved else NseUdiffConflictState.CONFLICT_UNRESOLVED)
            or not self.source_identity.startswith("https://")
            or not self.differing_fields
            or self.differing_fields != tuple(sorted(set(self.differing_fields)))
            or self.fingerprint != _fingerprint(_conflict_payload(values))
        ):
            raise ValueError("NSE_UDIFF_CONFLICT_ASSESSMENT_INVALID")

    @property
    def current_state(self) -> NseUdiffCurrentConflictState:
        return (self.reconciliation.state if self.reconciliation is not None
                else NseUdiffCurrentConflictState.CURRENT_UNRESOLVED_CONFLICT)

    def blocks_window(self, bars: Iterable[CanonicalOHLCVBar], as_of: datetime) -> bool:
        self.__post_init__()
        return self.reconciliation is None or not self.reconciliation.resolves_window(bars, as_of)


@dataclass(frozen=True, slots=True)
class NseUdiffDivergenceAudit:
    canonical_instrument_id: str
    overlap_count: int
    near_ohlc_count: int
    near_ohlc_exact_volume_count: int
    classification: NseUdiffDivergenceClassification
    close_ratio: Decimal | None
    fingerprint: str

    def __post_init__(self) -> None:
        values = dict(
            canonical_instrument_id=self.canonical_instrument_id,
            overlap_count=self.overlap_count, near_ohlc_count=self.near_ohlc_count,
            near_ohlc_exact_volume_count=self.near_ohlc_exact_volume_count,
            classification=self.classification, close_ratio=self.close_ratio,
        )
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or min(self.overlap_count, self.near_ohlc_count, self.near_ohlc_exact_volume_count) < 0
            or self.near_ohlc_exact_volume_count > self.near_ohlc_count > self.overlap_count
            or (self.overlap_count == 0 and (self.classification is not NseUdiffDivergenceClassification.NO_OVERLAP or self.close_ratio is not None))
            or (self.overlap_count > 0 and self.classification is NseUdiffDivergenceClassification.NO_OVERLAP)
            or (self.close_ratio is not None and (not self.close_ratio.is_finite() or self.close_ratio <= 0))
            or self.fingerprint != _fingerprint(_divergence_payload(values))
        ):
            raise ValueError("NSE_UDIFF_DIVERGENCE_AUDIT_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailySourceSelection:
    canonical_instrument_id: str
    trade_date: date
    state: NseUdiffDailySourceSelectionState
    selected_provider: str | None
    bar_id: str | None
    coverage_entry_fingerprint: str | None
    identity_fingerprint: str | None
    conflict_fingerprints: tuple[str, ...]
    reason: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        values = dict(
            canonical_instrument_id=self.canonical_instrument_id, trade_date=self.trade_date,
            state=self.state, selected_provider=self.selected_provider, bar_id=self.bar_id,
            coverage_entry_fingerprint=self.coverage_entry_fingerprint,
            identity_fingerprint=self.identity_fingerprint,
            conflict_fingerprints=self.conflict_fingerprints, reason=self.reason,
        )
        selected = self.state is NseUdiffDailySourceSelectionState.SELECTED_UDIFF
        blocked_by_conflict = self.state is NseUdiffDailySourceSelectionState.CONFLICT_UNRESOLVED
        identity_unresolved = self.state is NseUdiffDailySourceSelectionState.HISTORICAL_IDENTITY_UNRESOLVED
        series_inactive = self.state is NseUdiffDailySourceSelectionState.SERIES_SELECTION_NOT_ACTIVE
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.trade_date, date)
            or self.conflict_fingerprints != tuple(sorted(set(self.conflict_fingerprints)))
            or any(not _HEX.fullmatch(item) for item in self.conflict_fingerprints)
            or (selected and (self.selected_provider != NSE_UDIFF_BAR_PROVIDER or not self.bar_id or not _FP.fullmatch(self.coverage_entry_fingerprint or "") or not _FP.fullmatch(self.identity_fingerprint or "") or self.conflict_fingerprints or self.reason is not None))
            or (not selected and self.selected_provider is not None)
            or (not selected and self.bar_id is not None)
            or (series_inactive and (not _FP.fullmatch(self.coverage_entry_fingerprint or "") or not _FP.fullmatch(self.identity_fingerprint or "") or self.conflict_fingerprints or self.reason != "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE"))
            or (blocked_by_conflict and (not _FP.fullmatch(self.coverage_entry_fingerprint or "") or self.identity_fingerprint is not None or not self.conflict_fingerprints or self.reason != "NSE_UDIFF_SAME_PROVIDER_CONFLICT"))
            or (identity_unresolved and (not _FP.fullmatch(self.coverage_entry_fingerprint or "") or not _FP.fullmatch(self.identity_fingerprint or "") or self.conflict_fingerprints or self.reason not in {"NSE_UDIFF_EFFECTIVE_IDENTITY_REQUIRED", "NSE_UDIFF_IDENTITY_PIT_CUTOFF_REQUIRED"}))
            or (self.state in {NseUdiffDailySourceSelectionState.OUT_OF_ERA, NseUdiffDailySourceSelectionState.UDIFF_BAR_INVALID, NseUdiffDailySourceSelectionState.SOURCE_COVERAGE_UNAVAILABLE} and any(value is not None for value in (self.coverage_entry_fingerprint, self.identity_fingerprint)))
            or self.fingerprint != _fingerprint(_selection_payload(values))
        ):
            raise ValueError("NSE_UDIFF_DAILY_SOURCE_SELECTION_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffDailyIntegrityReport:
    """One local, explicit audit receipt; no provider or price mutation occurs."""

    manifest: NseUdiffSessionCoverageManifest
    manifest_inserted: bool
    valid_artifact_sessions: int
    confirmed_non_trading_days: int
    expected_session_source_missing: int
    unresolved_sessions: int
    unresolved_conflicts: int

    def __post_init__(self) -> None:
        counts = (
            self.valid_artifact_sessions, self.confirmed_non_trading_days,
            self.expected_session_source_missing, self.unresolved_sessions,
            self.unresolved_conflicts,
        )
        if min(counts) < 0 or sum(counts[:4]) != len(self.manifest.entries):
            raise ValueError("NSE_UDIFF_DAILY_INTEGRITY_REPORT_INVALID")


class NseUdiffDailyIntegrityStore:
    """Persist deterministic coverage manifests in the existing snapshot store."""

    def __init__(self, repository) -> None:
        self._repository = repository

    def save_session_coverage(self, value: NseUdiffSessionCoverageManifest) -> bool:
        from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily

        prior = self._repository.get_snapshot(value.manifest_id)
        if prior is not None:
            if prior.payload != value:
                raise ValueError("NSE_UDIFF_SESSION_COVERAGE_IMMUTABILITY_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.manifest_id, CoreApiSnapshotFamily.NSE_UDIFF_DAILY_SESSION_COVERAGE_MANIFEST,
            "v1", CONTRACT_ID, value.fingerprint, value.as_of, value,
        ))
        return True


def run_local_udiff_daily_integrity_audit(*, as_of: datetime) -> NseUdiffDailyIntegrityReport:
    """Materialize only the deterministic source-coverage receipt locally.

    The caller supplies ``as_of``.  No wall-clock value is used for historical
    interpretation, and no network, indicator, or technical calculation is
    launched by this operation.
    """
    if not _aware(as_of):
        raise ValueError("NSE_UDIFF_INTEGRITY_AS_OF_REQUIRED")
    from app.historical.nse_capital_market_session_evidence_2022_2026 import nse_capital_market_calendar_2022_2026
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.universe_analysis.service import CoreUniverseAnalysisStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE:
        raise ValueError("NSE_UDIFF_LOCAL_INTEGRITY_AUDIT_SQLITE_REQUIRED")
    repository = create_core_api_snapshot_repository(settings)
    historical = SQLiteHistoricalBarStore(settings.url.removeprefix("sqlite:///"))
    try:
        universe = CoreUniverseAnalysisStore(repository).latest_universe_snapshot()
        if universe is None:
            raise ValueError("NSE_UDIFF_CURRENT_UNIVERSE_SNAPSHOT_REQUIRED")
        acquisition_id = nse_udiff_acquisition_id(universe)
        evidence = NseUdiffDailyHistoryStore(repository)
        artifact_sessions = {
            item.trade_date: _artifact_session_ids(item)
            for item in evidence.artifacts(acquisition_id)
        }
        manifest = build_udiff_session_coverage_manifest(
            acquisition_id=acquisition_id,
            requested_dates=_weekdays(NSE_UDIFF_START, NSE_UDIFF_END),
            receipts=evidence.receipts(acquisition_id),
            artifact_session_ids=artifact_sessions,
            calendar=nse_capital_market_calendar_2022_2026(),
            as_of=as_of,
        )
        inserted = NseUdiffDailyIntegrityStore(repository).save_session_coverage(manifest)
        conflicts = audit_udiff_same_provider_conflicts(historical.list_conflict_artifacts())
        states = {state: sum(item.state is state for item in manifest.entries) for state in NseUdiffSessionCoverageState}
        return NseUdiffDailyIntegrityReport(
            manifest=manifest, manifest_inserted=inserted,
            valid_artifact_sessions=states[NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION],
            confirmed_non_trading_days=states[NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY],
            expected_session_source_missing=states[NseUdiffSessionCoverageState.EXPECTED_SESSION_SOURCE_MISSING],
            unresolved_sessions=states[NseUdiffSessionCoverageState.HISTORICAL_SESSION_UNRESOLVED],
            unresolved_conflicts=len(conflicts),
        )
    finally:
        historical.close()


def build_udiff_session_coverage_manifest(
    *,
    acquisition_id: str,
    requested_dates: Iterable[date],
    receipts: Iterable[NseUdiffDailyAcquisitionReceipt],
    calendar: CanonicalMarketSessionCalendar,
    as_of: datetime,
    artifact_session_ids: Mapping[date, tuple[str, ...]] | None = None,
) -> NseUdiffSessionCoverageManifest:
    """Classify every requested UDiFF date from retained source and calendar facts.

    A valid UDiFF artifact proves an observed official session fact.  A missing
    artifact is *not* a holiday unless the existing first-party calendar says
    so at the supplied explicit cutoff.
    """
    if not _aware(as_of) or not acquisition_id.startswith("nse-udiff-acquisition:"):
        raise ValueError("NSE_UDIFF_SESSION_COVERAGE_INPUT_INVALID")
    dates = tuple(sorted(set(requested_dates)))
    if not dates:
        raise ValueError("NSE_UDIFF_SESSION_COVERAGE_DATES_REQUIRED")
    latest: dict[date, NseUdiffDailyAcquisitionReceipt] = {}
    for receipt in receipts:
        if receipt.acquisition_id != acquisition_id:
            continue
        prior = latest.get(receipt.trade_date)
        if prior is None or (receipt.observed_at, receipt.receipt_id) > (prior.observed_at, prior.receipt_id):
            latest[receipt.trade_date] = receipt
    sessions = artifact_session_ids or {}
    entries = tuple(_coverage_entry(day, latest.get(day), calendar, _utc(as_of), sessions.get(day, ())) for day in dates)
    values = dict(
        acquisition_id=acquisition_id, requested_dates=dates, entries=entries,
        calendar_id=calendar.calendar_id, calendar_fingerprint=calendar.fingerprint,
        as_of=_utc(as_of), source_family=NSE_UDIFF_SOURCE_FAMILY,
        source_version=NSE_UDIFF_SOURCE_VERSION,
    )
    manifest_id = "nse-udiff-session-coverage:" + _fingerprint(_manifest_payload(values)).removeprefix("sha256:")[:32]
    return NseUdiffSessionCoverageManifest(
        manifest_id=manifest_id, **values,
        fingerprint=_fingerprint(_manifest_payload(values)),
    )


def audit_udiff_same_provider_conflicts(
    values: Iterable[HistoricalBarConflictArtifact],
    *, reconciliations: Iterable[NseUdiffConflictReconciliation] = (),
) -> tuple[NseUdiffConflictAssessment, ...]:
    """Retain every artifact; resolve only with exact archived/storage proof."""
    evidence = {}
    for item in reconciliations:
        item.__post_init__()
        key = item.artifact.conflict_fingerprint
        if key in evidence:
            raise ValueError("NSE_UDIFF_CONFLICT_RECONCILIATION_DUPLICATE")
        evidence[key] = item
    result: list[NseUdiffConflictAssessment] = []
    for value in values:
        value.__post_init__()
        if value.stored_lineage.provider_identity.casefold() != NSE_UDIFF_BAR_PROVIDER.casefold():
            continue
        if value.incoming_lineage.provider_identity.casefold() != NSE_UDIFF_BAR_PROVIDER.casefold():
            continue
        same_source = value.stored_lineage.source_identity == value.incoming_lineage.source_identity
        different_reference = value.stored_lineage.provider_instrument_reference != value.incoming_lineage.provider_instrument_reference
        if same_source and different_reference:
            cause = NseUdiffConflictCause.INGESTION_KEY_COLLISION
        elif same_source:
            cause = NseUdiffConflictCause.SAME_KEY_DIFFERING_OHLCV
        elif not different_reference:
            cause = NseUdiffConflictCause.SOURCE_ARTIFACT_DUPLICATION
        else:
            cause = NseUdiffConflictCause.UNRESOLVED_SOURCE_CONFLICT
        trade_date = _nse_trade_date(value.start_time)
        reconciliation = evidence.pop(value.conflict_fingerprint, None)
        if reconciliation is not None and reconciliation.artifact != value:
            raise ValueError("NSE_UDIFF_CONFLICT_RECONCILIATION_ARTIFACT_MISMATCH")
        body = dict(
            conflict_fingerprint=value.conflict_fingerprint,
            canonical_instrument_id=value.canonical_instrument_id,
            trade_date=trade_date,
            state=(NseUdiffConflictState.CONFLICT_RESOLVED_BY_SOURCE_SEMANTICS
                   if reconciliation is not None and reconciliation.state
                   is NseUdiffCurrentConflictState.RESOLVED_STRUCTURAL_CONFLICT
                   else NseUdiffConflictState.CONFLICT_UNRESOLVED),
            cause=cause,
            stored_provider_reference=value.stored_lineage.provider_instrument_reference,
            incoming_provider_reference=value.incoming_lineage.provider_instrument_reference,
            source_identity=value.stored_lineage.source_identity or "https://nsearchives.nseindia.com/unknown",
            differing_fields=tuple(sorted(value.differing_fields)),
            reconciliation=reconciliation,
        )
        result.append(NseUdiffConflictAssessment(**body, fingerprint=_fingerprint(_conflict_payload(body))))
    if evidence:
        raise ValueError("NSE_UDIFF_CONFLICT_RECONCILIATION_ORPHAN")
    return tuple(sorted(result, key=lambda item: (item.canonical_instrument_id, item.trade_date, item.conflict_fingerprint)))


def audit_udiff_upstox_divergence(
    *, canonical_instrument_id: str, udiff_bars: Iterable[CanonicalOHLCVBar], upstox_bars: Iterable[CanonicalOHLCVBar],
) -> NseUdiffDivergenceAudit:
    """Classify raw numeric relationships; it never promotes Upstox semantics."""
    udiff = _bars_by_start(udiff_bars, canonical_instrument_id, NSE_UDIFF_BAR_PROVIDER)
    upstox = _bars_by_start(upstox_bars, canonical_instrument_id, "UPSTOX")
    pairs = tuple((udiff[key], upstox[key]) for key in sorted(set(udiff) & set(upstox)))
    if not pairs:
        return _divergence(canonical_instrument_id, 0, 0, 0, NseUdiffDivergenceClassification.NO_OVERLAP, None)
    near_ohlc = sum(_near_ohlc(left, right) for left, right in pairs)
    near_exact_volume = sum(_near_ohlc(left, right) and left.volume == right.volume for left, right in pairs)
    classification, ratio = _classify_divergence(pairs, udiff, upstox, near_ohlc, near_exact_volume)
    return _divergence(canonical_instrument_id, len(pairs), near_ohlc, near_exact_volume, classification, ratio)


def select_eligible_udiff_daily_bar(
    *,
    bar: CanonicalOHLCVBar,
    coverage: NseUdiffSessionCoverageManifest,
    identity: HistoricalSecurityIdentityResolution,
    conflicts: Iterable[NseUdiffConflictAssessment],
) -> NseUdiffDailySourceSelection:
    """Return an era-specific UDiFF decision or an explicit insufficiency.

    No path returns Upstox (or another provider) as a fallback.  Existing
    generic historical reads remain untouched until a caller is deliberately
    migrated to this contract.
    """
    day = _nse_trade_date(bar.start_time)
    instrument_id = bar.instrument.instrument_id
    conflict_ids = tuple(sorted(
        item.conflict_fingerprint for item in conflicts
        if item.canonical_instrument_id == instrument_id and item.trade_date == day
    ))
    entry = next((item for item in coverage.entries if item.trade_date == day), None)
    if day < NSE_UDIFF_START:
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.OUT_OF_ERA, None, None, None, None, (), "NSE_UDIFF_LEGACY_ERA_NOT_READY")
    if (
        bar.timeframe is not Timeframe.DAILY
        or bar.provenance.provider.casefold() != NSE_UDIFF_BAR_PROVIDER.casefold()
        or bar.adjustment_status.value != "RAW"
    ):
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.UDIFF_BAR_INVALID, None, None, None, None, (), "NSE_UDIFF_BAR_CONTRACT_INVALID")
    if entry is None or entry.state is not NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION:
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.SOURCE_COVERAGE_UNAVAILABLE, None, None, None, None, (), "NSE_UDIFF_SESSION_COVERAGE_REQUIRED")
    if conflict_ids:
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.CONFLICT_UNRESOLVED, None, None, entry.fingerprint, None, conflict_ids, "NSE_UDIFF_SAME_PROVIDER_CONFLICT")
    if identity.status is not HistoricalSecurityIdentityResolutionStatus.RESOLVED or identity.canonical_instrument_id != instrument_id:
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.HISTORICAL_IDENTITY_UNRESOLVED, None, None, entry.fingerprint, identity.fingerprint, (), "NSE_UDIFF_EFFECTIVE_IDENTITY_REQUIRED")
    if _utc(identity.as_of) != _utc(bar.end_time):
        return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.HISTORICAL_IDENTITY_UNRESOLVED, None, None, entry.fingerprint, identity.fingerprint, (), "NSE_UDIFF_IDENTITY_PIT_CUTOFF_REQUIRED")
    # Coverage and canonical-security identity alone do not govern EQ/BE/BL/T0
    # eligibility. Preserve old SELECTED_UDIFF receipts as history, but create
    # no new selection until a separate approved series policy exists.
    return _selection(instrument_id, day, NseUdiffDailySourceSelectionState.SERIES_SELECTION_NOT_ACTIVE, None, None, entry.fingerprint, identity.fingerprint, (), "NSE_UDIFF_TECHNICAL_SERIES_SELECTION_NOT_ACTIVE")


def _coverage_entry(
    day: date,
    receipt: NseUdiffDailyAcquisitionReceipt | None,
    calendar: CanonicalMarketSessionCalendar,
    as_of: datetime,
    session_ids: tuple[str, ...],
) -> NseUdiffSessionCoverageEntry:
    if receipt is not None and receipt.status is NseUdiffDailyStatus.ARTIFACT_VALID:
        body = dict(trade_date=day, state=NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION,
                    artifact_id=receipt.artifact_id, receipt_id=receipt.receipt_id,
                    source_gap=None, session_ids=tuple(sorted(set(session_ids))),
                    source_ids=(), source_fingerprints=(), reason=None)
        return NseUdiffSessionCoverageEntry(**body, fingerprint=_fingerprint(_coverage_entry_payload(body)))
    resolved = calendar.resolve_trading_day(day, as_of=as_of)
    if resolved.state in {TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING}:
        gap = NseUdiffSourceGapClassification.CONFIRMED_EXCHANGE_HOLIDAY if resolved.state is TradingDayState.HOLIDAY else NseUdiffSourceGapClassification.CONFIRMED_NON_TRADING_DAY
        state = NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY
        reason = None
    elif resolved.state in {TradingDayState.REGULAR_TRADING_DAY, TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}:
        gap = NseUdiffSourceGapClassification.SOURCE_RETRIEVAL_UNAVAILABLE if receipt is not None else NseUdiffSourceGapClassification.SOURCE_ARTIFACT_MISSING
        state = NseUdiffSessionCoverageState.EXPECTED_SESSION_SOURCE_MISSING
        reason = receipt.error_code if receipt is not None else "NSE_UDIFF_RECEIPT_MISSING"
    else:
        gap = NseUdiffSourceGapClassification.HISTORICAL_SESSION_UNRESOLVED
        state = NseUdiffSessionCoverageState.HISTORICAL_SESSION_UNRESOLVED
        reason = "|".join(item.value for item in resolved.reasons)
    body = dict(trade_date=day, state=state, artifact_id=None, receipt_id=None if receipt is None else receipt.receipt_id,
                source_gap=gap, session_ids=(), source_ids=resolved.source_ids,
                source_fingerprints=resolved.source_fingerprints, reason=reason)
    return NseUdiffSessionCoverageEntry(**body, fingerprint=_fingerprint(_coverage_entry_payload(body)))


def _selection(instrument_id, day, state, provider, bar_id, coverage_fp, identity_fp, conflict_ids, reason):
    body = dict(
        canonical_instrument_id=instrument_id, trade_date=day, state=state,
        selected_provider=provider, bar_id=bar_id,
        coverage_entry_fingerprint=coverage_fp, identity_fingerprint=identity_fp,
        conflict_fingerprints=conflict_ids, reason=reason,
    )
    return NseUdiffDailySourceSelection(**body, fingerprint=_fingerprint(_selection_payload(body)))


def _artifact_session_ids(artifact) -> tuple[str, ...]:
    """Recover exact session labels from the retained, already-validated ZIP."""
    from app.market_data.nse_udiff_daily_history import _parse_valid_archive

    parsed = _parse_valid_archive(artifact)
    return tuple(sorted({row["SsnId"].strip() for row in parsed.rows if row.get("SsnId", "").strip()}))


def _weekdays(start: date, end: date) -> tuple[date, ...]:
    values: list[date] = []
    day = start
    while day <= end:
        if day.weekday() < 5:
            values.append(day)
        day = date.fromordinal(day.toordinal() + 1)
    return tuple(values)


def _nse_trade_date(value: datetime) -> date:
    """Return the NSE-labelled session date, never the UTC-midnight date."""
    return _utc(value).astimezone(_NSE_SESSION_ZONE).date()


def _bars_by_start(values: Iterable[CanonicalOHLCVBar], instrument_id: str, provider: str) -> Mapping[datetime, CanonicalOHLCVBar]:
    result: dict[datetime, CanonicalOHLCVBar] = {}
    for value in values:
        if (
            value.instrument.instrument_id != instrument_id
            or value.timeframe is not Timeframe.DAILY
            or value.provenance.provider.casefold() != provider.casefold()
        ):
            raise ValueError("NSE_UDIFF_DIVERGENCE_BAR_INPUT_INVALID")
        key = _utc(value.start_time)
        if key in result:
            raise ValueError("NSE_UDIFF_DIVERGENCE_DUPLICATE_SESSION")
        result[key] = value
    return result


def _classify_divergence(pairs, udiff, upstox, near_ohlc: int, near_exact_volume: int):
    if near_ohlc == len(pairs):
        return (
            NseUdiffDivergenceClassification.EXACT_OR_NEAR_MATCH if near_exact_volume == len(pairs)
            else NseUdiffDivergenceClassification.VOLUME_ONLY_MISMATCH,
            None,
        )
    ratios = tuple(left.close / right.close for left, right in pairs if right.close != 0)
    if len(ratios) == len(pairs) and ratios and len(set(ratios)) == 1:
        ratio = ratios[0]
        if all(_all_prices_scaled(left, right, ratio) for left, right in pairs):
            return NseUdiffDivergenceClassification.CONSTANT_MULTIPLICATIVE_RATIO, ratio
    if _one_session_shift(udiff, upstox):
        return NseUdiffDivergenceClassification.ONE_SESSION_DATE_SHIFT_SUSPECTED, None
    if _field_mapping(pairs):
        return NseUdiffDivergenceClassification.FIELD_MAPPING_SUSPECTED, None
    return NseUdiffDivergenceClassification.IRREGULAR_UNEXPLAINED, None


def _one_session_shift(udiff, upstox) -> bool:
    common = tuple(sorted(set(udiff) & set(upstox)))
    if len(common) < 2:
        return False
    # Each shifted comparison intentionally omits one boundary session.
    forward = all(_near_decimal(udiff[left].close, upstox[right].close) for left, right in zip(common[1:], common))
    backward = all(_near_decimal(udiff[left].close, upstox[right].close) for left, right in zip(common, common[1:]))
    return forward or backward


def _field_mapping(pairs) -> bool:
    return bool(pairs) and all(
        _near_decimal(left.close, right.open)
        or _near_decimal(left.close, right.high)
        or _near_decimal(left.close, right.low)
        for left, right in pairs
    )


def _all_prices_scaled(left: CanonicalOHLCVBar, right: CanonicalOHLCVBar, ratio: Decimal) -> bool:
    return all(getattr(left, field) == getattr(right, field) * ratio for field in ("open", "high", "low", "close"))


def _near_ohlc(left: CanonicalOHLCVBar, right: CanonicalOHLCVBar) -> bool:
    return all(_near_decimal(getattr(left, field), getattr(right, field)) for field in ("open", "high", "low", "close"))


def _near_decimal(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= _ONE_PAISE


def _divergence(instrument_id, overlap, near, volume, state, ratio):
    body = dict(canonical_instrument_id=instrument_id, overlap_count=overlap, near_ohlc_count=near,
                near_ohlc_exact_volume_count=volume, classification=state, close_ratio=ratio)
    return NseUdiffDivergenceAudit(**body, fingerprint=_fingerprint(_divergence_payload(body)))


def _manifest_values(value: NseUdiffSessionCoverageManifest) -> dict[str, object]:
    return {
        name: getattr(value, name) for name in (
            "acquisition_id", "requested_dates", "entries", "calendar_id", "calendar_fingerprint",
            "as_of", "source_family", "source_version",
        )
    }


def _coverage_entry_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "date": value["trade_date"].isoformat(), "state": _enum(value["state"]),
        "artifact_id": value["artifact_id"], "receipt_id": value["receipt_id"],
        "source_gap": None if value["source_gap"] is None else _enum(value["source_gap"]),
        "session_ids": list(value["session_ids"]),
        "source_ids": list(value["source_ids"]), "source_fingerprints": list(value["source_fingerprints"]),
        "reason": value["reason"],
    }


def _manifest_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "acquisition_id": value["acquisition_id"],
        "requested_dates": [item.isoformat() for item in value["requested_dates"]],
        "entries": [{"date": item.trade_date.isoformat(), "fingerprint": item.fingerprint} for item in value["entries"]],
        "calendar_id": value["calendar_id"], "calendar_fingerprint": value["calendar_fingerprint"],
        "as_of": _time(value["as_of"]), "source_family": value["source_family"],
        "source_version": value["source_version"],
    }


def _conflict_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "conflict": value["conflict_fingerprint"], "instrument": value["canonical_instrument_id"],
        "date": value["trade_date"].isoformat(), "state": _enum(value["state"]),
        "cause": _enum(value["cause"]), "stored_ref": value["stored_provider_reference"],
        "incoming_ref": value["incoming_provider_reference"], "source": value["source_identity"],
        "fields": list(value["differing_fields"]),
        # No added key for legacy assessments: their hashes remain reproducible.
        **({"reconciliation": value["reconciliation"].fingerprint}
           if value.get("reconciliation") is not None else {}),
    }


def _divergence_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "instrument": value["canonical_instrument_id"], "overlap": value["overlap_count"],
        "near_ohlc": value["near_ohlc_count"], "near_ohlc_exact_volume": value["near_ohlc_exact_volume_count"],
        "classification": _enum(value["classification"]),
        "close_ratio": None if value["close_ratio"] is None else format(value["close_ratio"], "f"),
    }


def _selection_payload(value: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "instrument": value["canonical_instrument_id"], "date": value["trade_date"].isoformat(),
        "state": _enum(value["state"]), "selected_provider": value["selected_provider"],
        "bar_id": value["bar_id"], "coverage": value["coverage_entry_fingerprint"],
        "identity": value["identity_fingerprint"], "conflicts": list(value["conflict_fingerprints"]),
        "reason": value["reason"],
    }


def _fingerprint(value: Mapping[str, object]) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise ValueError("NSE_UDIFF_INTEGRITY_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _enum(value: StrEnum) -> str:
    return value.value


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "NseUdiffConflictAssessment", "NseUdiffConflictCause",
    "NseUdiffConflictState", "NseUdiffDailyIntegrityStore", "NseUdiffDivergenceAudit",
    "NseUdiffDailyIntegrityReport",
    "NseUdiffDivergenceClassification", "NseUdiffSessionCoverageEntry",
    "NseUdiffDailySourceSelection", "NseUdiffDailySourceSelectionState",
    "NseUdiffSessionCoverageManifest", "NseUdiffSessionCoverageState",
    "NseUdiffSourceGapClassification", "audit_udiff_same_provider_conflicts",
    "audit_udiff_upstox_divergence", "build_udiff_session_coverage_manifest",
    "run_local_udiff_daily_integrity_audit", "select_eligible_udiff_daily_bar",
)
