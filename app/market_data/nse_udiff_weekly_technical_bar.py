"""Certified-Daily-only canonical NSE UDiFF Weekly technical bars.

This module is deliberately a narrow aggregation and persistence boundary.  It
never reads a generic historical-bar store, fetches a provider, chooses a
fallback, calculates an indicator, or accesses portfolio/execution state.  A
caller supplies an already-certified ``NSE_UDIFF_DAILY_TECHNICAL_READ`` for one
closed exchange week.  The only persistent representation is an additive,
lineage-complete Weekly artifact in the existing local SQLite database.

The UDiFF archive remains current-descriptive evidence.  Aggregation cannot
turn that evidence into strict historical PIT availability.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    TradingDayState,
)
from app.market_data.models import (
    CanonicalOHLCVBar,
    MarketDataProvenance,
    Timeframe,
)
from app.market_data.nse_udiff_daily_integrity import (
    NseUdiffSessionCoverageManifest,
    NseUdiffSessionCoverageState,
)
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalEligibilityState,
    DailyTechnicalRequirement,
    DailyTechnicalRequirementProfile,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffCertifiedDailyTechnicalRead,
    NseUdiffDailyTechnicalReadState,
    NseUdiffDailyTechnicalUseMode,
)
from app.market_data.nse_udiff_source_identity import PROVIDER as NSE_UDIFF_PROVIDER
from app.market_data.technical_bar_contract import (
    CanonicalTechnicalBar,
    CanonicalTechnicalInterval,
    ProviderIntervalRepresentation,
    TechnicalBarCompletenessState,
    TechnicalBarOrigin,
    TechnicalBarReadiness,
    TechnicalBarReason,
    TechnicalBarSourceLineage,
    TechnicalIntervalUnit,
    TechnicalTradingPeriod,
    TechnicalVolumeReadiness,
    derive_closed_bar,
    make_bar_receipt,
    make_derived_technical_bar,
    make_native_technical_bar,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    snapshot_json,
    snapshot_json_from,
)


CONTRACT_ID = "nse-udiff-certified-daily-weekly-technical-bar"
CONTRACT_VERSION = "v1"
AGGREGATION_POLICY_ID = "nse-udiff-certified-daily-to-weekly-technical"
AGGREGATION_POLICY_VERSION = "v1"
DERIVED_PROVIDER = "hsi_derived_from_nse_udiff_daily"
SQLITE_WEEKLY_TABLE = "nse_udiff_weekly_technical_bars"
SQLITE_WEEKLY_CONFLICT_TABLE = "nse_udiff_weekly_technical_bar_conflicts"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseUdiffWeeklyTechnicalBarError(ValueError):
    """Stable fail-closed error for malformed Weekly aggregation evidence."""


class NseUdiffWeeklyTechnicalState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class NseUdiffWeeklyTechnicalReason(StrEnum):
    SOURCE_ERA_UNAVAILABLE = "SOURCE_ERA_UNAVAILABLE"
    WEEK_SESSION_COVERAGE_UNAVAILABLE = "WEEK_SESSION_COVERAGE_UNAVAILABLE"
    SPECIAL_SESSION_SOURCE_MISSING = "SPECIAL_SESSION_SOURCE_MISSING"
    WEEK_HAS_NO_EXPECTED_SESSION = "WEEK_HAS_NO_EXPECTED_SESSION"
    WEEK_NOT_COMPLETE = "WEEK_NOT_COMPLETE"
    DAILY_READ_REQUIRED = "DAILY_READ_REQUIRED"
    DAILY_READ_NOT_READY = "DAILY_READ_NOT_READY"
    DAILY_READ_WINDOW_MISMATCH = "DAILY_READ_WINDOW_MISMATCH"
    DAILY_READ_SOURCE_MISMATCH = "DAILY_READ_SOURCE_MISMATCH"
    STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE = (
        "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE"
    )


class NseUdiffWeeklyTechnicalBarWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    IDENTICAL = "IDENTICAL"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class NseUdiffWeeklySessionPlan:
    """Exact exchange-local member-session proof for one Monday--Sunday week.

    Ordinary weekdays come from the acquired UDiFF coverage manifest; exchange
    holidays are explicit manifest entries.  An NSE calendar special/muhurat
    session is always considered, even when it falls on a weekend.  Missing
    manifest coverage for such a session blocks the Week rather than being
    silently ignored.
    """

    week_start: date
    week_end: date
    expected_sessions: tuple[date, ...]
    confirmed_non_trading_dates: tuple[date, ...]
    missing_session_dates: tuple[date, ...]
    special_expected_sessions: tuple[date, ...]
    calendar_id: str
    calendar_fingerprint: str
    coverage_manifest_id: str
    coverage_manifest_fingerprint: str
    coverage_as_of: datetime
    session_source_ids: tuple[str, ...]
    session_source_fingerprints: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        dates = (self.expected_sessions, self.confirmed_non_trading_dates,
                 self.missing_session_dates, self.special_expected_sessions)
        pairs = tuple(zip(self.session_source_ids, self.session_source_fingerprints, strict=True))
        values = _session_plan_values(
            self.week_start, self.week_end, *dates, self.calendar_id,
            self.calendar_fingerprint, self.coverage_manifest_id,
            self.coverage_manifest_fingerprint, self.coverage_as_of, pairs,
        )
        if (
            not isinstance(self.week_start, date)
            or self.week_start.weekday() != 0
            or self.week_end != date.fromordinal(self.week_start.toordinal() + 6)
            or any(value != tuple(sorted(set(value))) for value in dates)
            or any(any(item < self.week_start or item > self.week_end for item in value) for value in dates)
            or set(self.expected_sessions) & set(self.confirmed_non_trading_dates)
            or set(self.expected_sessions) & set(self.missing_session_dates)
            or set(self.confirmed_non_trading_dates) & set(self.missing_session_dates)
            or not set(self.special_expected_sessions) <= set(self.expected_sessions) | set(self.missing_session_dates)
            or not _ID.fullmatch(self.calendar_id)
            or not _FP.fullmatch(self.calendar_fingerprint)
            or not self.coverage_manifest_id.startswith("nse-udiff-session-coverage:")
            or not _FP.fullmatch(self.coverage_manifest_fingerprint)
            or not _aware(self.coverage_as_of)
            or self.session_source_ids != tuple(sorted(set(self.session_source_ids)))
            or self.session_source_fingerprints != tuple(sorted(set(self.session_source_fingerprints)))
            or len(self.session_source_ids) != len(self.session_source_fingerprints)
            or any(not _ID.fullmatch(identifier) or not _FP.fullmatch(fingerprint) for identifier, fingerprint in pairs)
            or self.fingerprint != _fingerprint(values)
        ):
            raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_SESSION_PLAN_INVALID")

    @property
    def is_complete(self) -> bool:
        return bool(self.expected_sessions) and not self.missing_session_dates

    @property
    def period_id(self) -> str:
        return "nse-udiff-week:" + self.week_start.isoformat()


@dataclass(frozen=True, slots=True)
class NseUdiffWeeklyTechnicalDerivationRequest:
    canonical_instrument_id: str
    session_plan: NseUdiffWeeklySessionPlan
    requirement: DailyTechnicalRequirement
    use_mode: NseUdiffDailyTechnicalUseMode
    aggregation_policy_id: str = AGGREGATION_POLICY_ID
    aggregation_policy_version: str = AGGREGATION_POLICY_VERSION

    def __post_init__(self) -> None:
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.session_plan, NseUdiffWeeklySessionPlan)
            or not isinstance(self.requirement, DailyTechnicalRequirement)
            or self.requirement.profile is not DailyTechnicalRequirementProfile.PRICE_AND_VOLUME
            or not isinstance(self.use_mode, NseUdiffDailyTechnicalUseMode)
            or (self.aggregation_policy_id, self.aggregation_policy_version)
            != (AGGREGATION_POLICY_ID, AGGREGATION_POLICY_VERSION)
        ):
            raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_TECHNICAL_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class NseUdiffWeeklyTechnicalBar:
    """A derived Weekly bar or one typed, no-bar fail-closed result."""

    request: NseUdiffWeeklyTechnicalDerivationRequest
    state: NseUdiffWeeklyTechnicalState
    daily_read: NseUdiffCertifiedDailyTechnicalRead | None
    technical_bar: CanonicalTechnicalBar | None
    source_daily_read_fingerprint: str | None
    source_daily_receipt_id: str | None
    source_daily_receipt_fingerprint: str | None
    source_daily_observation_ids: tuple[str, ...]
    source_references: tuple[str, ...]
    reasons: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reasons)))
        observations = tuple(sorted(set(self.source_daily_observation_ids)))
        references = tuple(sorted(set(self.source_references)))
        values = _weekly_values(
            self.request, self.state, self.daily_read, self.technical_bar,
            self.source_daily_read_fingerprint, self.source_daily_receipt_id,
            self.source_daily_receipt_fingerprint, observations, references, reasons,
        )
        ready = self.state is NseUdiffWeeklyTechnicalState.READY
        strict = self.request.use_mode is NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL
        daily = self.daily_read
        if (
            not isinstance(self.request, NseUdiffWeeklyTechnicalDerivationRequest)
            or not isinstance(self.state, NseUdiffWeeklyTechnicalState)
            or self.reasons != reasons
            or self.source_daily_observation_ids != observations
            or self.source_references != references
            or any(not _ID.fullmatch(item) for item in (*reasons, *observations))
            or any(not item for item in references)
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
            or (strict and (
                ready or daily is not None or self.technical_bar is not None
                or self.source_daily_read_fingerprint is not None
                or self.source_daily_receipt_id is not None
                or self.source_daily_receipt_fingerprint is not None
                or observations or references
                or reasons != (NseUdiffWeeklyTechnicalReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,)
            ))
            or (ready and (
                daily is None or self.technical_bar is None or not _FP.fullmatch(self.source_daily_read_fingerprint or "")
                or not (self.source_daily_receipt_id or "").startswith("nse-udiff-daily-technical-eligibility:")
                or not _FP.fullmatch(self.source_daily_receipt_fingerprint or "")
                or not observations or not references or reasons
                or daily.state is not NseUdiffDailyTechnicalReadState.READY
                or daily.certification is None or daily.certification.eligibility is not DailyTechnicalEligibilityState.READY
                or self.technical_bar.origin is not TechnicalBarOrigin.DERIVED_RESAMPLED_BAR
                or self.technical_bar.interval.interval_id != "1W"
                or self.technical_bar.receipt.state is not TechnicalBarCompletenessState.CLOSED
                or self.technical_bar.receipt.readiness is not TechnicalBarReadiness.READY
                or self.technical_bar.market_bar.provenance.provider != DERIVED_PROVIDER
                or self.source_daily_read_fingerprint != daily.fingerprint
                or self.source_daily_receipt_id != daily.certification.receipt_id
                or self.source_daily_receipt_fingerprint != daily.certification.fingerprint
                or observations != daily.source_observation_ids
                or references != daily.source_references
            ))
            or (not ready and self.technical_bar is not None)
            or (not ready and any(value is not None for value in (
                self.source_daily_read_fingerprint, self.source_daily_receipt_id,
                self.source_daily_receipt_fingerprint,
            )))
            or (not ready and (observations or references))
        ):
            raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_TECHNICAL_RESULT_INVALID")

    @property
    def weekly_bar_id(self) -> str | None:
        return None if self.technical_bar is None else self.technical_bar.canonical_bar_id

    @property
    def known_at(self) -> datetime | None:
        return None if self.technical_bar is None else self.technical_bar.receipt.known_at


def build_nse_udiff_weekly_session_plan(
    *, week_start: date, coverage: NseUdiffSessionCoverageManifest,
    calendar: CanonicalMarketSessionCalendar,
) -> NseUdiffWeeklySessionPlan:
    """Build the exact session set without assuming a five-bar Week."""
    if (
        not isinstance(week_start, date) or week_start.weekday() != 0
        or not isinstance(coverage, NseUdiffSessionCoverageManifest)
        or not isinstance(calendar, CanonicalMarketSessionCalendar)
        or coverage.calendar_id != calendar.calendar_id
        or coverage.calendar_fingerprint != calendar.fingerprint
    ):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_SESSION_PLAN_INPUT_INVALID")
    week_end = date.fromordinal(week_start.toordinal() + 6)
    entries = {item.trade_date: item for item in coverage.entries}
    expected: list[date] = []
    non_trading: list[date] = []
    missing: list[date] = []
    special: list[date] = []
    pairs: set[tuple[str, str]] = set()
    for ordinal in range(7):
        value = date.fromordinal(week_start.toordinal() + ordinal)
        entry = entries.get(value)
        day = calendar.resolve_trading_day(value, as_of=coverage.as_of)
        is_special = day.state in {TradingDayState.SPECIAL_TRADING_DAY, TradingDayState.MUHURAT_TRADING}
        if is_special:
            special.append(value)
            pairs.update(zip(day.source_ids, day.source_fingerprints, strict=True))
        if entry is not None:
            pairs.update(zip(entry.source_ids, entry.source_fingerprints, strict=True))
            if entry.state is NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION:
                expected.append(value)
            elif entry.state is NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY and not is_special:
                non_trading.append(value)
            else:
                missing.append(value)
        elif is_special:
            # An official special session is an expected child, even if the
            # historical acquisition did not request an unusual weekday.
            missing.append(value)
        elif value.weekday() < 5:
            # The retained manifest is the source-era weekday spine.  A
            # missing entry is an unproven expected session, never a holiday.
            missing.append(value)
        else:
            non_trading.append(value)
    # The pre-existing timeframe contract intentionally carries source IDs and
    # fingerprints as independently canonicalised vectors.  Preserve that
    # convention rather than inventing an unapproved ID-to-fingerprint pairing.
    source_ids = tuple(sorted({item[0] for item in pairs}))
    source_fingerprints = tuple(sorted({item[1] for item in pairs}))
    if len(source_ids) != len(source_fingerprints):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_SESSION_SOURCE_LINEAGE_INVALID")
    source_pairs = tuple(zip(source_ids, source_fingerprints, strict=True))
    values = _session_plan_values(
        week_start, week_end, tuple(sorted(set(expected))), tuple(sorted(set(non_trading))),
        tuple(sorted(set(missing))), tuple(sorted(set(special))), calendar.calendar_id,
        calendar.fingerprint, coverage.manifest_id, coverage.fingerprint,
        _utc(coverage.as_of), source_pairs,
    )
    return NseUdiffWeeklySessionPlan(
        week_start, week_end, tuple(sorted(set(expected))), tuple(sorted(set(non_trading))),
        tuple(sorted(set(missing))), tuple(sorted(set(special))), calendar.calendar_id,
        calendar.fingerprint, coverage.manifest_id, coverage.fingerprint,
        _utc(coverage.as_of), source_ids, source_fingerprints, _fingerprint(values),
    )


def derive_nse_udiff_weekly_technical_bar(
    *, request: NseUdiffWeeklyTechnicalDerivationRequest,
    daily_read: NseUdiffCertifiedDailyTechnicalRead | None,
) -> NseUdiffWeeklyTechnicalBar:
    """Derive one complete Weekly bar from exactly one certified Daily window."""
    request.__post_init__()
    if request.use_mode is NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL:
        return _blocked(request, None, (
            NseUdiffWeeklyTechnicalReason.STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE.value,
        ))
    plan = request.session_plan
    if plan.week_end < date(2024, 7, 8):
        return _blocked(request, None, (NseUdiffWeeklyTechnicalReason.SOURCE_ERA_UNAVAILABLE.value,))
    if not plan.expected_sessions:
        return _blocked(request, None, (NseUdiffWeeklyTechnicalReason.WEEK_HAS_NO_EXPECTED_SESSION.value,))
    if plan.missing_session_dates:
        special_missing = bool(set(plan.missing_session_dates) & set(plan.special_expected_sessions))
        return _blocked(request, None, (
            NseUdiffWeeklyTechnicalReason.SPECIAL_SESSION_SOURCE_MISSING.value
            if special_missing else NseUdiffWeeklyTechnicalReason.WEEK_SESSION_COVERAGE_UNAVAILABLE.value,
            NseUdiffWeeklyTechnicalReason.WEEK_NOT_COMPLETE.value,
        ))
    if daily_read is None:
        return _blocked(request, None, (NseUdiffWeeklyTechnicalReason.DAILY_READ_REQUIRED.value,))
    daily_read.__post_init__()
    if (
        daily_read.request.use_mode is not NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL
        or daily_read.request.canonical_instrument_id != request.canonical_instrument_id
        or daily_read.request.requirement != request.requirement
        or daily_read.request.start_session != plan.expected_sessions[0]
        or daily_read.request.end_session != plan.expected_sessions[-1]
        or daily_read.certification is None
        or daily_read.certification.expected_sessions != plan.expected_sessions
    ):
        return _blocked(request, daily_read, (NseUdiffWeeklyTechnicalReason.DAILY_READ_WINDOW_MISMATCH.value,))
    if daily_read.state is not NseUdiffDailyTechnicalReadState.READY:
        return _blocked(request, daily_read, (
            NseUdiffWeeklyTechnicalReason.DAILY_READ_NOT_READY.value, *daily_read.reasons,
        ))
    try:
        technical = _derive_technical_bar(request, daily_read)
    except (NseUdiffWeeklyTechnicalBarError, ValueError):
        return _blocked(request, daily_read, (NseUdiffWeeklyTechnicalReason.DAILY_READ_SOURCE_MISMATCH.value,))
    values = dict(
        request=request, state=NseUdiffWeeklyTechnicalState.READY, daily_read=daily_read,
        technical_bar=technical, source_daily_read_fingerprint=daily_read.fingerprint,
        source_daily_receipt_id=daily_read.certification.receipt_id,
        source_daily_receipt_fingerprint=daily_read.certification.fingerprint,
        source_daily_observation_ids=daily_read.source_observation_ids,
        source_references=daily_read.source_references, reasons=(),
    )
    return NseUdiffWeeklyTechnicalBar(**values, fingerprint=_fingerprint(_weekly_values(**values)))


def serialize_nse_udiff_weekly_technical_bar(value: NseUdiffWeeklyTechnicalBar) -> str:
    """Stable JSON containing every identity and content-fingerprint input."""
    value.__post_init__()
    return _canonical(_weekly_values(
        value.request, value.state, value.daily_read, value.technical_bar,
        value.source_daily_read_fingerprint, value.source_daily_receipt_id,
        value.source_daily_receipt_fingerprint, value.source_daily_observation_ids,
        value.source_references, value.reasons,
    ) | {"fingerprint": value.fingerprint})


class SQLiteNseUdiffWeeklyTechnicalBarStore:
    """Additive, immutable, source-lineage-complete Weekly SQLite artifacts."""

    def __init__(self, database_path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(f"""
            CREATE TABLE IF NOT EXISTS {SQLITE_WEEKLY_TABLE} (
                weekly_bar_id TEXT PRIMARY KEY,
                canonical_instrument_id TEXT NOT NULL,
                week_start TEXT NOT NULL,
                week_end TEXT NOT NULL,
                aggregation_policy_id TEXT NOT NULL,
                aggregation_policy_version TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                UNIQUE (canonical_instrument_id, week_start, week_end,
                        aggregation_policy_id, aggregation_policy_version)
            );
            CREATE INDEX IF NOT EXISTS nse_udiff_weekly_technical_bar_lookup_idx
                ON {SQLITE_WEEKLY_TABLE} (canonical_instrument_id, week_start, week_end);
            CREATE TABLE IF NOT EXISTS {SQLITE_WEEKLY_CONFLICT_TABLE} (
                conflict_fingerprint TEXT PRIMARY KEY,
                weekly_bar_id TEXT NOT NULL,
                existing_fingerprint TEXT NOT NULL,
                incoming_fingerprint TEXT NOT NULL,
                incoming_payload_json TEXT NOT NULL
            );
        """)
        self._connection.commit()

    def close(self) -> None:
        self._connection.close()

    def save(self, value: NseUdiffWeeklyTechnicalBar) -> NseUdiffWeeklyTechnicalBarWriteOutcome:
        value.__post_init__()
        if value.state is not NseUdiffWeeklyTechnicalState.READY or value.weekly_bar_id is None:
            raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_TECHNICAL_STORE_READY_ARTIFACT_REQUIRED")
        return self._save_without_commit(value, commit=True)

    def save_many(self, values: Iterable[NseUdiffWeeklyTechnicalBar]) -> tuple[NseUdiffWeeklyTechnicalBarWriteOutcome, ...]:
        results: list[NseUdiffWeeklyTechnicalBarWriteOutcome] = []
        try:
            self._connection.execute("BEGIN")
            for value in values:
                results.append(self._save_without_commit(value, commit=False))
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return tuple(results)

    def get(self, weekly_bar_id: str) -> NseUdiffWeeklyTechnicalBar | None:
        row = self._connection.execute(
            f"SELECT payload_json FROM {SQLITE_WEEKLY_TABLE} WHERE weekly_bar_id=?", (weekly_bar_id,),
        ).fetchone()
        return None if row is None else _stored_value(str(row["payload_json"]))

    def list(
        self, *, canonical_instrument_id: str | None = None,
        week_start: date | None = None, week_end: date | None = None,
    ) -> tuple[NseUdiffWeeklyTechnicalBar, ...]:
        query = f"SELECT payload_json FROM {SQLITE_WEEKLY_TABLE}"
        terms: list[str] = []
        params: list[str] = []
        if canonical_instrument_id is not None:
            terms.append("canonical_instrument_id=?"); params.append(canonical_instrument_id)
        if week_start is not None:
            terms.append("week_start>=?"); params.append(week_start.isoformat())
        if week_end is not None:
            terms.append("week_end<=?"); params.append(week_end.isoformat())
        if terms:
            query += " WHERE " + " AND ".join(terms)
        rows = self._connection.execute(query + " ORDER BY canonical_instrument_id, week_start, weekly_bar_id", params).fetchall()
        return tuple(_stored_value(str(row["payload_json"])) for row in rows)

    def count(self) -> int:
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {SQLITE_WEEKLY_TABLE}").fetchone()[0])

    def conflict_count(self) -> int:
        return int(self._connection.execute(f"SELECT COUNT(*) FROM {SQLITE_WEEKLY_CONFLICT_TABLE}").fetchone()[0])

    def _save_without_commit(
        self, value: NseUdiffWeeklyTechnicalBar, *, commit: bool,
    ) -> NseUdiffWeeklyTechnicalBarWriteOutcome:
        assert value.weekly_bar_id is not None and value.technical_bar is not None
        row = self._connection.execute(
            f"SELECT fingerprint,payload_json FROM {SQLITE_WEEKLY_TABLE} WHERE weekly_bar_id=?",
            (value.weekly_bar_id,),
        ).fetchone()
        encoded = _stored_json(value)
        if row is not None:
            # The immutable serialized representation includes the complete
            # content fingerprint.  Byte-for-byte equality is therefore a
            # sufficient replay proof and avoids decoding a complete lineage
            # payload for every already-materialised bar.  Any unequal value
            # still takes the defensive decode/conflict path below.
            if str(row["fingerprint"]) == value.fingerprint and str(row["payload_json"]) == encoded:
                return NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL
            existing = _stored_value(str(row["payload_json"]))
            if existing == value:
                return NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL
            self._save_conflict(value, str(row["fingerprint"]), encoded)
            if commit:
                self._connection.commit()
            return NseUdiffWeeklyTechnicalBarWriteOutcome.CONFLICT
        duplicate = self._connection.execute(
            f"SELECT fingerprint,payload_json FROM {SQLITE_WEEKLY_TABLE} "
            "WHERE canonical_instrument_id=? AND week_start=? AND week_end=? "
            "AND aggregation_policy_id=? AND aggregation_policy_version=?",
            (value.request.canonical_instrument_id, value.request.session_plan.week_start.isoformat(),
             value.request.session_plan.week_end.isoformat(), value.request.aggregation_policy_id,
             value.request.aggregation_policy_version),
        ).fetchone()
        if duplicate is not None:
            if str(duplicate["fingerprint"]) == value.fingerprint and str(duplicate["payload_json"]) == encoded:
                return NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL
            existing = _stored_value(str(duplicate["payload_json"]))
            if existing == value:
                return NseUdiffWeeklyTechnicalBarWriteOutcome.IDENTICAL
            self._save_conflict(value, str(duplicate["fingerprint"]), encoded)
            if commit:
                self._connection.commit()
            return NseUdiffWeeklyTechnicalBarWriteOutcome.CONFLICT
        self._connection.execute(
            f"INSERT INTO {SQLITE_WEEKLY_TABLE} "
            "(weekly_bar_id,canonical_instrument_id,week_start,week_end,aggregation_policy_id,aggregation_policy_version,fingerprint,payload_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (value.weekly_bar_id, value.request.canonical_instrument_id,
             value.request.session_plan.week_start.isoformat(), value.request.session_plan.week_end.isoformat(),
             value.request.aggregation_policy_id, value.request.aggregation_policy_version,
             value.fingerprint, encoded),
        )
        if commit:
            self._connection.commit()
        return NseUdiffWeeklyTechnicalBarWriteOutcome.INSERTED

    def _save_conflict(self, value: NseUdiffWeeklyTechnicalBar, existing_fingerprint: str, encoded: str) -> None:
        assert value.weekly_bar_id is not None
        conflict = _fingerprint({
            "weekly_bar_id": value.weekly_bar_id,
            "existing_fingerprint": existing_fingerprint,
            "incoming_fingerprint": value.fingerprint,
        })
        self._connection.execute(
            f"INSERT OR IGNORE INTO {SQLITE_WEEKLY_CONFLICT_TABLE} "
            "(conflict_fingerprint,weekly_bar_id,existing_fingerprint,incoming_fingerprint,incoming_payload_json) "
            "VALUES (?,?,?,?,?)",
            (conflict, value.weekly_bar_id, existing_fingerprint, value.fingerprint, encoded),
        )


def _derive_technical_bar(
    request: NseUdiffWeeklyTechnicalDerivationRequest,
    daily_read: NseUdiffCertifiedDailyTechnicalRead,
) -> CanonicalTechnicalBar:
    assert daily_read.certification is not None
    plan = request.session_plan
    if (
        len(daily_read.bars) != len(plan.expected_sessions)
        or {item.bar_id for item in daily_read.bars} != set(daily_read.certification.source_bar_ids)
        or any(item.provenance.provider.casefold() != NSE_UDIFF_PROVIDER for item in daily_read.bars)
    ):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_DAILY_SOURCE_INVALID")
    bars_by_session = {_session_date(item): item for item in daily_read.bars}
    if tuple(sorted(bars_by_session)) != plan.expected_sessions or len(bars_by_session) != len(daily_read.bars):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_DAILY_SESSION_MISMATCH")
    daily = tuple(bars_by_session[item] for item in plan.expected_sessions)
    pairs = tuple(zip(plan.session_source_ids, plan.session_source_fingerprints, strict=True))
    period = TechnicalTradingPeriod(
        venue=daily[0].instrument.exchange, segment="CAPITAL_MARKET", period_id=plan.period_id,
        session_dates=plan.expected_sessions, starts_at=daily[0].start_time, ends_at=daily[-1].end_time,
        timezone_id="Asia/Kolkata", calendar_id=plan.calendar_id,
        calendar_fingerprint=plan.calendar_fingerprint,
        session_source_ids=tuple(item[0] for item in pairs),
        session_source_fingerprints=tuple(item[1] for item in pairs),
    )
    child_bars = tuple(_daily_technical_bar(item, plan) for item in daily)
    aggregate = derive_closed_bar(
        interval=CanonicalTechnicalInterval(unit=TechnicalIntervalUnit.WEEK, multiplier=1),
        period=period, expected_source_bar_ids=tuple(item.canonical_bar_id for item in child_bars),
        source_bars=child_bars,
    )
    trade_count = (
        sum(item.trade_count for item in daily if item.trade_count is not None)
        if all(item.trade_count is not None for item in daily) else None
    )
    market_bar = CanonicalOHLCVBar(
        bar_id=aggregate.canonical_bar_id, instrument=daily[0].instrument, timeframe=Timeframe.WEEKLY,
        start_time=period.starts_at, end_time=period.ends_at, open=aggregate.open, high=aggregate.high,
        low=aggregate.low, close=aggregate.close, volume=aggregate.volume, turnover=None,
        trade_count=trade_count, adjustment_status=aggregate.adjustment_status,
        provenance=MarketDataProvenance(
            provider=DERIVED_PROVIDER, provider_instrument_reference=aggregate.canonical_bar_id,
            exchange_timestamp=period.ends_at, provider_timestamp=aggregate.known_at,
            received_at=aggregate.known_at,
            normalization_version="nse-udiff-weekly-technical-derivation-v1",
            request_reference="nse-udiff-daily-technical-read:" + daily_read.fingerprint.removeprefix("sha256:"),
            source_reference="nse-udiff-weekly-lineage:" + aggregate.fingerprint.removeprefix("sha256:"),
        ),
    )
    receipt = make_bar_receipt(
        canonical_bar_id=aggregate.canonical_bar_id, interval=aggregate.interval, period=period,
        state=TechnicalBarCompletenessState.CLOSED, readiness=TechnicalBarReadiness.READY,
        expected_source_bar_ids=tuple(item.canonical_bar_id for item in child_bars),
        observed_source_lineage=aggregate.source_lineage, missing_source_bar_count=0,
        known_at=aggregate.known_at, adjustment_status=aggregate.adjustment_status,
        volume_readiness=aggregate.volume_readiness, reasons=(),
    )
    return make_derived_technical_bar(
        market_bar=market_bar, aggregation=aggregate, receipt=receipt,
        aggregation_policy_id=request.aggregation_policy_id,
        aggregation_policy_version=request.aggregation_policy_version,
        corporate_action_ids=daily_read.certification.action_ids,
    )


def _daily_technical_bar(bar: CanonicalOHLCVBar, plan: NseUdiffWeeklySessionPlan) -> CanonicalTechnicalBar:
    session = _session_date(bar)
    pairs = tuple(zip(plan.session_source_ids, plan.session_source_fingerprints, strict=True))
    period = TechnicalTradingPeriod(
        venue=bar.instrument.exchange, segment="CAPITAL_MARKET", period_id="nse-udiff-day:" + session.isoformat(),
        session_dates=(session,), starts_at=bar.start_time, ends_at=bar.end_time,
        timezone_id="Asia/Kolkata", calendar_id=plan.calendar_id,
        calendar_fingerprint=plan.calendar_fingerprint,
        session_source_ids=tuple(item[0] for item in pairs),
        session_source_fingerprints=tuple(item[1] for item in pairs),
    )
    return make_native_technical_bar(
        market_bar=bar, period=period, state=TechnicalBarCompletenessState.CLOSED,
        readiness=TechnicalBarReadiness.READY, known_at=bar.provenance.received_at,
        provider_interval=ProviderIntervalRepresentation(NSE_UDIFF_PROVIDER, "1D"),
        volume_readiness=TechnicalVolumeReadiness.READY,
    )


def _blocked(
    request: NseUdiffWeeklyTechnicalDerivationRequest,
    daily_read: NseUdiffCertifiedDailyTechnicalRead | None,
    reasons: Iterable[str],
) -> NseUdiffWeeklyTechnicalBar:
    values = dict(
        request=request, state=NseUdiffWeeklyTechnicalState.NOT_READY, daily_read=daily_read,
        technical_bar=None, source_daily_read_fingerprint=None, source_daily_receipt_id=None,
        source_daily_receipt_fingerprint=None, source_daily_observation_ids=(),
        source_references=(), reasons=tuple(sorted(set(reasons))),
    )
    return NseUdiffWeeklyTechnicalBar(**values, fingerprint=_fingerprint(_weekly_values(**values)))


def _stored_json(value: NseUdiffWeeklyTechnicalBar) -> str:
    assert value.known_at is not None and value.weekly_bar_id is not None
    return snapshot_json(CoreApiSnapshot(
        value.weekly_bar_id, CoreApiSnapshotFamily.NSE_UDIFF_WEEKLY_TECHNICAL_BAR,
        CONTRACT_VERSION, type(value).__name__, value.fingerprint, value.known_at, value,
    ))


def _stored_value(payload: str) -> NseUdiffWeeklyTechnicalBar:
    snapshot = snapshot_json_from(payload)
    if (
        snapshot.family is not CoreApiSnapshotFamily.NSE_UDIFF_WEEKLY_TECHNICAL_BAR
        or snapshot.schema_version != CONTRACT_VERSION
        or not isinstance(snapshot.payload, NseUdiffWeeklyTechnicalBar)
        or snapshot.payload.weekly_bar_id != snapshot.snapshot_id
        or snapshot.payload.fingerprint != snapshot.fingerprint
    ):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_TECHNICAL_STORED_PAYLOAD_INVALID")
    snapshot.payload.__post_init__()
    return snapshot.payload


def _session_plan_values(
    week_start: date, week_end: date, expected: tuple[date, ...], non_trading: tuple[date, ...],
    missing: tuple[date, ...], special: tuple[date, ...], calendar_id: str,
    calendar_fingerprint: str, manifest_id: str, manifest_fingerprint: str,
    as_of: datetime, pairs: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
        "expected_sessions": [item.isoformat() for item in expected],
        "confirmed_non_trading_dates": [item.isoformat() for item in non_trading],
        "missing_session_dates": [item.isoformat() for item in missing],
        "special_expected_sessions": [item.isoformat() for item in special],
        "calendar": {"id": calendar_id, "fingerprint": calendar_fingerprint},
        "coverage_manifest": {"id": manifest_id, "fingerprint": manifest_fingerprint, "as_of": _utc(as_of).isoformat()},
        "session_sources": [[identifier, fingerprint] for identifier, fingerprint in pairs],
    }


def _weekly_values(
    request: NseUdiffWeeklyTechnicalDerivationRequest, state: NseUdiffWeeklyTechnicalState,
    daily_read: NseUdiffCertifiedDailyTechnicalRead | None, technical_bar: CanonicalTechnicalBar | None,
    source_daily_read_fingerprint: str | None, source_daily_receipt_id: str | None,
    source_daily_receipt_fingerprint: str | None, source_daily_observation_ids: tuple[str, ...],
    source_references: tuple[str, ...], reasons: tuple[str, ...],
) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "aggregation_policy": {"id": request.aggregation_policy_id, "version": request.aggregation_policy_version},
        "request": {
            "instrument": request.canonical_instrument_id,
            "week_plan_fingerprint": request.session_plan.fingerprint,
            "requirement": {"profile": request.requirement.profile.value, "version": request.requirement.profile_version},
            "use_mode": request.use_mode.value,
        },
        "state": state.value,
        "daily_read": None if daily_read is None else {
            "fingerprint": daily_read.fingerprint,
            "state": daily_read.state.value,
            "certification_fingerprint": None if daily_read.certification is None else daily_read.certification.fingerprint,
        },
        "technical_bar": None if technical_bar is None else {
            "canonical_bar_id": technical_bar.canonical_bar_id,
            "fingerprint": technical_bar.fingerprint,
            "receipt_fingerprint": technical_bar.receipt.fingerprint,
            "market_bar_id": technical_bar.market_bar.bar_id,
        },
        "source_daily_read_fingerprint": source_daily_read_fingerprint,
        "source_daily_receipt_id": source_daily_receipt_id,
        "source_daily_receipt_fingerprint": source_daily_receipt_fingerprint,
        "source_daily_observation_ids": list(source_daily_observation_ids),
        "source_references": list(source_references), "reasons": list(reasons),
    }


def _session_date(value: CanonicalOHLCVBar) -> date:
    from app.market_data.nse_udiff_source_identity import source_fields
    return date.fromisoformat(source_fields(value)["TradDt"])


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise NseUdiffWeeklyTechnicalBarError("NSE_UDIFF_WEEKLY_TECHNICAL_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


__all__ = (
    "AGGREGATION_POLICY_ID", "AGGREGATION_POLICY_VERSION", "CONTRACT_ID", "CONTRACT_VERSION",
    "DERIVED_PROVIDER", "NseUdiffWeeklySessionPlan", "NseUdiffWeeklyTechnicalBar",
    "NseUdiffWeeklyTechnicalBarError", "NseUdiffWeeklyTechnicalBarWriteOutcome",
    "NseUdiffWeeklyTechnicalDerivationRequest", "NseUdiffWeeklyTechnicalReason",
    "NseUdiffWeeklyTechnicalState", "SQLiteNseUdiffWeeklyTechnicalBarStore",
    "build_nse_udiff_weekly_session_plan", "derive_nse_udiff_weekly_technical_bar",
    "serialize_nse_udiff_weekly_technical_bar",
)
