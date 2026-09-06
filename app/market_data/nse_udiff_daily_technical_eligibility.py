"""Pure certification for one exact NSE UDiFF Daily technical-data window.

This contract is deliberately narrower than technical analysis.  It selects no
indicator, score, setup, signal, or action; writes no data; and never merges a
provider.  Its only job is to prove (or fail closed on) whether caller-supplied
raw NSE UDiFF observations can be read for one ``security + sessions +
requirement-profile`` window.

Historical identity proves addressability, not price or volume continuity.
Likewise raw exchange facts remain distinct from any future split/bonus
derived technical series.  The latter is intentionally not materialised here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    TradingDayState,
)
from app.historical.nse_udiff_identity_promotion import (
    NseUdiffHistoricalSourceIdentityInterval,
)
from app.historical.security_master import CorporateActionKind, HistoricalCorporateAction
from app.market_data.models import (
    CanonicalOHLCVBar,
    MarketDataQualityValidator,
)
from app.market_data.nse_udiff_daily_integrity import (
    NseUdiffConflictAssessment,
    NseUdiffConflictState,
    NseUdiffSessionCoverageManifest,
    NseUdiffSessionCoverageState,
)
from app.market_data.nse_udiff_source_identity import PROVIDER, source_fields
from app.market_data.technical_source_basis_action_coverage import (
    CorporateActionCoverageAssertion,
    CorporateActionCoverageState,
)


CONTRACT_ID = "nse-udiff-daily-technical-eligibility-and-continuity-certification"
CONTRACT_VERSION = "v1"
POLICY_ID = "nse-udiff-ordinary-daily-technical-series-selection"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class DailyTechnicalEligibilityError(ValueError):
    """Stable fail-closed error for malformed certification evidence."""


class DailyTechnicalRequirementProfile(StrEnum):
    PRICE_ONLY = "PRICE_ONLY"
    PRICE_AND_VOLUME = "PRICE_AND_VOLUME"
    RAW_EXCHANGE_HISTORY_ONLY = "RAW_EXCHANGE_HISTORY_ONLY"


class DailyTechnicalSeriesSelectionState(StrEnum):
    SERIES_CONTINUITY_READY = "SERIES_CONTINUITY_READY"
    SERIES_REGIME_CHANGED = "SERIES_REGIME_CHANGED"
    SERIES_NON_COMPARABLE = "SERIES_NON_COMPARABLE"
    SERIES_POLICY_UNRESOLVED = "SERIES_POLICY_UNRESOLVED"


class DailyTechnicalPriceContinuityState(StrEnum):
    PRICE_CONTINUITY_READY = "PRICE_CONTINUITY_READY"
    ACTION_ADJUSTMENT_REQUIRED = "ACTION_ADJUSTMENT_REQUIRED"
    COMPLEX_ACTION_NON_COMPARABLE = "COMPLEX_ACTION_NON_COMPARABLE"
    SERIES_TRANSITION_BLOCKED = "SERIES_TRANSITION_BLOCKED"
    IDENTITY_GAP = "IDENTITY_GAP"
    SOURCE_GAP = "SOURCE_GAP"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DailyTechnicalVolumeContinuityState(StrEnum):
    VOLUME_CONTINUITY_READY = "VOLUME_CONTINUITY_READY"
    VOLUME_NOT_REQUIRED = "VOLUME_NOT_REQUIRED"
    VOLUME_ADJUSTMENT_REQUIRED = "VOLUME_ADJUSTMENT_REQUIRED"
    VOLUME_REGIME_CHANGED = "VOLUME_REGIME_CHANGED"
    VOLUME_SOURCE_GAP = "VOLUME_SOURCE_GAP"
    VOLUME_NOT_READY = "VOLUME_NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DailyTechnicalEligibilityState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class CurrentDescriptiveDailyTechnicalState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class StrictHistoricalPitTechnicalState(StrEnum):
    NOT_READY = "NOT_READY"


class DailyTechnicalEligibilityReason(StrEnum):
    UDIFF_SOURCE_REQUIRED = "UDIFF_SOURCE_REQUIRED"
    RAW_DAILY_SOURCE_REQUIRED = "RAW_DAILY_SOURCE_REQUIRED"
    SOURCE_ROW_INVALID = "SOURCE_ROW_INVALID"
    SOURCE_ROW_QUALITY_INVALID = "SOURCE_ROW_QUALITY_INVALID"
    EXPECTED_SESSION_REQUIRED = "EXPECTED_SESSION_REQUIRED"
    EXPECTED_SESSION_UNRESOLVED = "EXPECTED_SESSION_UNRESOLVED"
    MISSING_REQUIRED_SECURITY_SESSION = "MISSING_REQUIRED_SECURITY_SESSION"
    UNEXPECTED_SECURITY_SESSION = "UNEXPECTED_SECURITY_SESSION"
    AMBIGUOUS_SECURITY_SESSION = "AMBIGUOUS_SECURITY_SESSION"
    HISTORICAL_IDENTITY_REQUIRED = "HISTORICAL_IDENTITY_REQUIRED"
    HISTORICAL_IDENTITY_AMBIGUOUS = "HISTORICAL_IDENTITY_AMBIGUOUS"
    SAME_PROVIDER_CONFLICT = "SAME_PROVIDER_CONFLICT"
    BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES = "BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES"
    T0_DISTINCT_SETTLEMENT_SERIES = "T0_DISTINCT_SETTLEMENT_SERIES"
    SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY = "SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY"
    SERIES_POLICY_UNRESOLVED = "SERIES_POLICY_UNRESOLVED"
    ACTION_COVERAGE_REQUIRED = "ACTION_COVERAGE_REQUIRED"
    ACTION_COVERAGE_NOT_READY = "ACTION_COVERAGE_NOT_READY"
    DUPLICATE_ACTION_ID = "DUPLICATE_ACTION_ID"
    SPLIT_ADJUSTMENT_REQUIRED = "SPLIT_ADJUSTMENT_REQUIRED"
    BONUS_ADJUSTMENT_REQUIRED = "BONUS_ADJUSTMENT_REQUIRED"
    RIGHTS_ADJUSTMENT_NOT_READY = "RIGHTS_ADJUSTMENT_NOT_READY"
    COMPLEX_ACTION_NON_COMPARABLE = "COMPLEX_ACTION_NON_COMPARABLE"
    DIVIDEND_PRICE_POLICY_NOT_APPROVED = "DIVIDEND_PRICE_POLICY_NOT_APPROVED"
    VOLUME_REQUIRED_BUT_ZERO_OR_MISSING = "VOLUME_REQUIRED_BUT_ZERO_OR_MISSING"
    HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE = "HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class DailyTechnicalRequirement:
    """One explicit non-scoring consumer requirement profile."""

    profile: DailyTechnicalRequirementProfile
    profile_version: str = "v1"

    def __post_init__(self) -> None:
        if not isinstance(self.profile, DailyTechnicalRequirementProfile) or not _ID.fullmatch(self.profile_version):
            raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_REQUIREMENT_INVALID")

    @property
    def requires_volume_continuity(self) -> bool:
        return self.profile is DailyTechnicalRequirementProfile.PRICE_AND_VOLUME

    @property
    def requires_price_continuity(self) -> bool:
        return self.profile is not DailyTechnicalRequirementProfile.RAW_EXCHANGE_HISTORY_ONLY


@dataclass(frozen=True, slots=True)
class NseUdiffDailyTechnicalSeriesPolicy:
    """First-party NSE category policy; no volume-based or insertion-order choice."""

    policy_id: str
    policy_version: str
    eq_state: DailyTechnicalSeriesSelectionState
    be_bz_same_series_state: DailyTechnicalSeriesSelectionState
    transition_state: DailyTechnicalSeriesSelectionState
    bl_state: DailyTechnicalSeriesSelectionState
    t0_state: DailyTechnicalSeriesSelectionState
    other_state: DailyTechnicalSeriesSelectionState
    fingerprint: str

    def __post_init__(self) -> None:
        expected = _fingerprint(_series_policy_payload(self))
        if (
            self.policy_id != POLICY_ID or self.policy_version != POLICY_VERSION
            or self.eq_state is not DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY
            or self.be_bz_same_series_state is not DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY
            or self.transition_state is not DailyTechnicalSeriesSelectionState.SERIES_REGIME_CHANGED
            or self.bl_state is not DailyTechnicalSeriesSelectionState.SERIES_NON_COMPARABLE
            or self.t0_state is not DailyTechnicalSeriesSelectionState.SERIES_NON_COMPARABLE
            or self.other_state is not DailyTechnicalSeriesSelectionState.SERIES_POLICY_UNRESOLVED
            or self.fingerprint != expected
        ):
            raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_SERIES_POLICY_INVALID")


def ordinary_nse_udiff_daily_technical_series_policy() -> NseUdiffDailyTechnicalSeriesPolicy:
    values = dict(
        policy_id=POLICY_ID, policy_version=POLICY_VERSION,
        eq_state=DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY,
        be_bz_same_series_state=DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY,
        transition_state=DailyTechnicalSeriesSelectionState.SERIES_REGIME_CHANGED,
        bl_state=DailyTechnicalSeriesSelectionState.SERIES_NON_COMPARABLE,
        t0_state=DailyTechnicalSeriesSelectionState.SERIES_NON_COMPARABLE,
        other_state=DailyTechnicalSeriesSelectionState.SERIES_POLICY_UNRESOLVED,
    )
    return NseUdiffDailyTechnicalSeriesPolicy(**values, fingerprint=_fingerprint(_series_policy_payload_values(values)))


@dataclass(frozen=True, slots=True)
class DailyTechnicalEligibilityReceipt:
    """Deterministic per-window proof.  It is an in-memory read receipt only."""

    receipt_id: str
    canonical_instrument_id: str
    start_session: date
    end_session: date
    requirement: DailyTechnicalRequirement
    evaluation_as_of: datetime
    source_policy_id: str
    source_policy_version: str
    source_policy_fingerprint: str
    expected_sessions: tuple[date, ...]
    observed_sessions: tuple[date, ...]
    selected_series: tuple[str, ...]
    series_state: DailyTechnicalSeriesSelectionState
    identity_interval_ids: tuple[str, ...]
    identity_interval_fingerprints: tuple[str, ...]
    source_bar_ids: tuple[str, ...]
    source_bar_fingerprints: tuple[str, ...]
    conflict_fingerprints: tuple[str, ...]
    action_coverage_fingerprint: str | None
    action_ids: tuple[str, ...]
    action_fingerprints: tuple[str, ...]
    price_continuity: DailyTechnicalPriceContinuityState
    volume_continuity: DailyTechnicalVolumeContinuityState
    current_descriptive_state: CurrentDescriptiveDailyTechnicalState
    strict_historical_pit_state: StrictHistoricalPitTechnicalState
    eligibility: DailyTechnicalEligibilityState
    reasons: tuple[DailyTechnicalEligibilityReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        intervals = tuple(sorted(zip(self.identity_interval_ids, self.identity_interval_fingerprints)))
        bars = tuple(sorted(zip(self.source_bar_ids, self.source_bar_fingerprints)))
        actions = tuple(sorted(zip(self.action_ids, self.action_fingerprints)))
        expected = tuple(sorted(set(self.expected_sessions)))
        observed = tuple(sorted(set(self.observed_sessions)))
        series = tuple(sorted(set(self.selected_series)))
        conflicts = tuple(sorted(set(self.conflict_fingerprints)))
        reasons = _reasons(self.reasons)
        expected_fp = _fingerprint(_receipt_payload(self, intervals, bars, actions, expected, observed, series, conflicts, reasons))
        if (
            not self.receipt_id.startswith("nse-udiff-daily-technical-eligibility:")
            or not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.start_session, date) or not isinstance(self.end_session, date)
            or self.start_session > self.end_session or not isinstance(self.requirement, DailyTechnicalRequirement)
            or not _aware(self.evaluation_as_of)
            or self.source_policy_id != POLICY_ID or self.source_policy_version != POLICY_VERSION
            or not _FP.fullmatch(self.source_policy_fingerprint)
            or not expected or self.expected_sessions != expected or self.observed_sessions != observed
            or any(session < self.start_session or session > self.end_session for session in expected)
            or self.selected_series != series or any(not value for value in series)
            or tuple(zip(self.identity_interval_ids, self.identity_interval_fingerprints)) != intervals
            or tuple(zip(self.source_bar_ids, self.source_bar_fingerprints)) != bars
            or tuple(zip(self.action_ids, self.action_fingerprints)) != actions
            or self.conflict_fingerprints != conflicts
            or any(not _ID.fullmatch(identifier) or not _FP.fullmatch(fingerprint) for identifier, fingerprint in (*intervals, *bars, *actions))
            or any(not _FP.fullmatch(value) for value in conflicts)
            or (self.action_coverage_fingerprint is not None and not _FP.fullmatch(self.action_coverage_fingerprint))
            or not isinstance(self.series_state, DailyTechnicalSeriesSelectionState)
            or not isinstance(self.price_continuity, DailyTechnicalPriceContinuityState)
            or not isinstance(self.volume_continuity, DailyTechnicalVolumeContinuityState)
            or ((self.current_descriptive_state is CurrentDescriptiveDailyTechnicalState.READY)
                != (self.eligibility is DailyTechnicalEligibilityState.READY))
            or self.strict_historical_pit_state is not StrictHistoricalPitTechnicalState.NOT_READY
            or DailyTechnicalEligibilityReason.HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE not in reasons
            or self.reasons != reasons or self.fingerprint != expected_fp
        ):
            raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_ELIGIBILITY_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalEligibleDailyRead:
    """The selected raw UDiFF bars for a previously READY receipt, and nothing else."""

    receipt_id: str
    receipt_fingerprint: str
    bars: tuple[CanonicalOHLCVBar, ...]

    def __post_init__(self) -> None:
        if (
            not self.receipt_id.startswith("nse-udiff-daily-technical-eligibility:")
            or not _FP.fullmatch(self.receipt_fingerprint)
            or not self.bars
            or self.bars != tuple(sorted(self.bars, key=lambda value: (value.start_time, value.bar_id)))
        ):
            raise DailyTechnicalEligibilityError("TECHNICAL_ELIGIBLE_DAILY_READ_INVALID")


def expected_nse_daily_sessions(
    *, calendar: CanonicalMarketSessionCalendar, start_session: date, end_session: date, as_of: datetime,
) -> tuple[date, ...]:
    """Resolve exact exchange trading sessions; unresolved calendar dates fail closed."""
    if not isinstance(start_session, date) or not isinstance(end_session, date) or start_session > end_session or not _aware(as_of):
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_SESSION_WINDOW_INVALID")
    values: list[date] = []
    cursor = start_session
    while cursor <= end_session:
        day = calendar.resolve_trading_day(cursor, as_of=as_of)
        if day.state is TradingDayState.UNKNOWN:
            raise DailyTechnicalEligibilityError("EXPECTED_SESSION_UNRESOLVED")
        if day.state not in {TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING}:
            values.append(cursor)
        cursor = date.fromordinal(cursor.toordinal() + 1)
    if not values:
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_REQUIRED")
    return tuple(values)


def expected_udiff_daily_sessions(
    *, coverage: NseUdiffSessionCoverageManifest, start_session: date, end_session: date,
) -> tuple[date, ...]:
    """Use the reconciled UDiFF artifact/session receipt as historical truth.

    The calendar establishes holidays and special sessions; the immutable
    coverage manifest establishes whether an exchange-labelled source artifact
    was retained for each historical trading day.  Neither missing artifacts
    nor unresolved dates are silently treated as holidays.
    """
    if not isinstance(start_session, date) or not isinstance(end_session, date) or start_session > end_session:
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_SESSION_WINDOW_INVALID")
    entries = tuple(item for item in coverage.entries if start_session <= item.trade_date <= end_session)
    # A historical manifest records its requested exchange/session dates, not
    # a fabricated calendar-day row for every weekend.  It is therefore the
    # source of the exact date population; its unresolved entries still block.
    if not entries or entries[0].trade_date != start_session or entries[-1].trade_date != end_session:
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_UNRESOLVED")
    unresolved = tuple(item for item in entries if item.state not in {
        NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION,
        NseUdiffSessionCoverageState.CONFIRMED_NON_TRADING_DAY,
    })
    if unresolved:
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_UNRESOLVED")
    result = tuple(item.trade_date for item in entries if item.state is NseUdiffSessionCoverageState.ARTIFACT_VALID_SESSION)
    if not result:
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_REQUIRED")
    return result


def certify_daily_technical_eligibility(
    *, canonical_instrument_id: str, start_session: date, end_session: date,
    requirement: DailyTechnicalRequirement, evaluation_as_of: datetime,
    expected_sessions: Iterable[date], observed_bars: Iterable[CanonicalOHLCVBar],
    identity_intervals: Iterable[NseUdiffHistoricalSourceIdentityInterval],
    action_coverage: CorporateActionCoverageAssertion | None,
    actions: Iterable[HistoricalCorporateAction] = (),
    conflicts: Iterable[NseUdiffConflictAssessment] = (),
    series_policy: NseUdiffDailyTechnicalSeriesPolicy | None = None,
) -> DailyTechnicalEligibilityReceipt:
    """Certify one exact window using only supplied immutable canonical evidence.

    ``evaluation_as_of`` is caller-supplied evidence time, never a runtime
    clock.  The strict-PIT output remains blocked because a current UDiFF
    archive backfill does not establish original historical availability.
    """
    if not _ID.fullmatch(canonical_instrument_id) or not isinstance(requirement, DailyTechnicalRequirement) or not _aware(evaluation_as_of):
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_ELIGIBILITY_INPUT_INVALID")
    policy = series_policy or ordinary_nse_udiff_daily_technical_series_policy()
    if not isinstance(policy, NseUdiffDailyTechnicalSeriesPolicy):
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_SERIES_POLICY_REQUIRED")
    expected_input = tuple(expected_sessions)
    expected = tuple(sorted(set(expected_input)))
    if not expected or expected[0] < start_session or expected[-1] > end_session:
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_REQUIRED")
    if len(expected) != len(expected_input):
        raise DailyTechnicalEligibilityError("EXPECTED_SESSION_DUPLICATE")
    at = _utc(evaluation_as_of)
    bars = tuple(sorted(observed_bars, key=lambda value: (value.start_time, value.bar_id)))
    intervals = tuple(sorted(identity_intervals, key=lambda value: value.interval_id))
    action_values = tuple(sorted(actions, key=lambda value: (value.effective_date, value.action_id)))
    conflict_values = tuple(sorted(conflicts, key=lambda value: (value.trade_date, value.conflict_fingerprint)))
    reasons: list[DailyTechnicalEligibilityReason] = [DailyTechnicalEligibilityReason.HISTORICAL_SOURCE_AVAILABILITY_UNAVAILABLE]
    candidates_by_day: dict[date, list[tuple[CanonicalOHLCVBar, dict[str, str]]]] = {}
    bar_by_day: dict[date, CanonicalOHLCVBar] = {}
    source_rows: dict[date, tuple[CanonicalOHLCVBar, dict[str, str]]] = {}
    identity_used: list[NseUdiffHistoricalSourceIdentityInterval] = []
    source_valid = True
    for bar in bars:
        try:
            MarketDataQualityValidator.validate_bar(bar)
            fields = source_fields(bar)
        except Exception:
            source_valid = False
            reasons.append(DailyTechnicalEligibilityReason.SOURCE_ROW_INVALID)
            continue
        day = date.fromisoformat(fields["TradDt"])
        if bar.instrument.instrument_id != canonical_instrument_id or day not in expected:
            source_valid = False
            reasons.append(DailyTechnicalEligibilityReason.UNEXPECTED_SECURITY_SESSION)
            continue
        candidates_by_day.setdefault(day, []).append((bar, fields))
    # BL and T0 are retained first-party source facts but are never ordinary
    # technical candidates.  Their coexistence cannot contaminate an EQ/BE/BZ
    # selection.  Competing ordinary series on one exact session still fail
    # closed rather than being selected by order, price, or volume.
    for day, candidates in sorted(candidates_by_day.items()):
        ordinary = tuple(item for item in candidates if item[1]["SctySrs"].upper() not in {"BL", "T0"})
        selected = ordinary if ordinary else tuple(candidates)
        if len(selected) != 1:
            source_valid = False
            reasons.append(DailyTechnicalEligibilityReason.AMBIGUOUS_SECURITY_SESSION)
            continue
        bar, fields = selected[0]
        bar_by_day[day] = bar
        source_rows[day] = (bar, fields)
        matches = tuple(
            item for item in intervals
            if item.canonical_instrument_id == canonical_instrument_id
            and item.source_observation_ids.count(bar.source_observation_identity) == 1
            and item.source_symbol == fields["TckrSymb"]
            and item.source_series == fields["SctySrs"]
            and item.observed_trade_start <= day <= item.observed_trade_end
        )
        if len(matches) == 1:
            identity_used.append(matches[0])
        elif len(matches) == 0:
            source_valid = False
            reasons.append(DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_REQUIRED)
        else:
            source_valid = False
            reasons.append(DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_AMBIGUOUS)
    missing = tuple(day for day in expected if day not in bar_by_day)
    if missing:
        source_valid = False
        reasons.append(DailyTechnicalEligibilityReason.MISSING_REQUIRED_SECURITY_SESSION)
    relevant_conflicts = tuple(
        item for item in conflict_values
        if item.canonical_instrument_id == canonical_instrument_id
        and item.trade_date in expected
        and item.state is NseUdiffConflictState.CONFLICT_UNRESOLVED
    )
    if relevant_conflicts:
        source_valid = False
        reasons.append(DailyTechnicalEligibilityReason.SAME_PROVIDER_CONFLICT)
    series = tuple(sorted({fields["SctySrs"].upper() for _, fields in source_rows.values()}))
    series_state, series_reason = _series_state(series, policy)
    if series_reason is not None:
        reasons.append(series_reason)
    coverage_ready = _coverage_ready(action_coverage, canonical_instrument_id, start_session, end_session, at)
    if action_coverage is None:
        reasons.append(DailyTechnicalEligibilityReason.ACTION_COVERAGE_REQUIRED)
    elif not coverage_ready:
        reasons.append(DailyTechnicalEligibilityReason.ACTION_COVERAGE_NOT_READY)
    relevant_actions, duplicate_action = _relevant_actions(action_values, canonical_instrument_id, start_session, end_session, at)
    if duplicate_action:
        reasons.append(DailyTechnicalEligibilityReason.DUPLICATE_ACTION_ID)
    price, volume = _continuity(
        requirement=requirement, source_valid=source_valid, series_state=series_state,
        coverage_ready=coverage_ready, duplicate_action=duplicate_action, actions=relevant_actions,
        bars=tuple(bar_by_day[day] for day in expected if day in bar_by_day), reasons=reasons,
    )
    eligible = (
        source_valid and coverage_ready and not duplicate_action
        and series_state is DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY
        and (not requirement.requires_price_continuity or price is DailyTechnicalPriceContinuityState.PRICE_CONTINUITY_READY)
        and (not requirement.requires_volume_continuity or volume is DailyTechnicalVolumeContinuityState.VOLUME_CONTINUITY_READY)
    )
    actual_reasons = _reasons(reasons)
    interval_pairs = tuple(sorted({(item.interval_id, item.fingerprint) for item in identity_used}))
    source_pairs = tuple(sorted(
        (bar_by_day[day].bar_id, _bar_fingerprint(bar_by_day[day]))
        for day in expected if day in bar_by_day
    ))
    action_pairs = tuple(sorted((item.action_id, _action_fingerprint(item)) for item in relevant_actions))
    values = dict(
        canonical_instrument_id=canonical_instrument_id, start_session=start_session, end_session=end_session,
        requirement=requirement, evaluation_as_of=at, source_policy_id=policy.policy_id,
        source_policy_version=policy.policy_version, source_policy_fingerprint=policy.fingerprint,
        expected_sessions=expected, observed_sessions=tuple(sorted(bar_by_day)), selected_series=series,
        series_state=series_state, identity_interval_ids=tuple(item[0] for item in interval_pairs),
        identity_interval_fingerprints=tuple(item[1] for item in interval_pairs),
        source_bar_ids=tuple(item[0] for item in source_pairs), source_bar_fingerprints=tuple(item[1] for item in source_pairs),
        conflict_fingerprints=tuple(item.fingerprint for item in relevant_conflicts),
        action_coverage_fingerprint=None if action_coverage is None else action_coverage.fingerprint,
        action_ids=tuple(item[0] for item in action_pairs), action_fingerprints=tuple(item[1] for item in action_pairs),
        price_continuity=price, volume_continuity=volume,
        current_descriptive_state=(CurrentDescriptiveDailyTechnicalState.READY if eligible else CurrentDescriptiveDailyTechnicalState.NOT_READY),
        strict_historical_pit_state=StrictHistoricalPitTechnicalState.NOT_READY,
        eligibility=DailyTechnicalEligibilityState.READY if eligible else DailyTechnicalEligibilityState.NOT_READY,
        reasons=actual_reasons,
    )
    base = _receipt_payload_values(values)
    receipt_id = "nse-udiff-daily-technical-eligibility:" + _fingerprint(base).removeprefix("sha256:")[:32]
    return DailyTechnicalEligibilityReceipt(receipt_id=receipt_id, **values, fingerprint=_fingerprint(base | {"receipt_id": receipt_id}))


def read_eligible_udiff_daily_bars(
    *, receipt: DailyTechnicalEligibilityReceipt, observed_bars: Iterable[CanonicalOHLCVBar],
) -> TechnicalEligibleDailyRead:
    """Return exactly the receipt-selected raw UDiFF bars or fail closed.

    There is intentionally no provider preference, fallback, or merge input.
    """
    receipt.__post_init__()
    if receipt.eligibility is not DailyTechnicalEligibilityState.READY:
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_ELIGIBILITY_NOT_READY")
    supplied = tuple(sorted(observed_bars, key=lambda value: (value.start_time, value.bar_id)))
    selected = tuple(
        bar for bar in supplied
        if bar.bar_id in receipt.source_bar_ids and _bar_fingerprint(bar) in receipt.source_bar_fingerprints
    )
    if (
        len(selected) != len(receipt.source_bar_ids)
        or {bar.bar_id for bar in selected} != set(receipt.source_bar_ids)
        or {_bar_fingerprint(bar) for bar in selected} != set(receipt.source_bar_fingerprints)
        or any(bar.provenance.provider.casefold() != PROVIDER for bar in selected)
    ):
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_ELIGIBLE_READ_SOURCE_MISMATCH")
    return TechnicalEligibleDailyRead(receipt.receipt_id, receipt.fingerprint, selected)


def serialize_daily_technical_eligibility(value: DailyTechnicalEligibilityReceipt) -> str:
    value.__post_init__()
    return _canonical(_receipt_payload(value, tuple(zip(value.identity_interval_ids, value.identity_interval_fingerprints)), tuple(zip(value.source_bar_ids, value.source_bar_fingerprints)), tuple(zip(value.action_ids, value.action_fingerprints)), value.expected_sessions, value.observed_sessions, value.selected_series, value.conflict_fingerprints, value.reasons) | {"fingerprint": value.fingerprint})


def _series_state(
    series: tuple[str, ...], policy: NseUdiffDailyTechnicalSeriesPolicy,
) -> tuple[DailyTechnicalSeriesSelectionState, DailyTechnicalEligibilityReason | None]:
    if not series:
        return DailyTechnicalSeriesSelectionState.SERIES_POLICY_UNRESOLVED, DailyTechnicalEligibilityReason.SOURCE_ROW_INVALID
    if "BL" in series:
        return policy.bl_state, DailyTechnicalEligibilityReason.BL_NOT_ORDINARY_DAILY_TECHNICAL_PRICE_SERIES
    if "T0" in series:
        return policy.t0_state, DailyTechnicalEligibilityReason.T0_DISTINCT_SETTLEMENT_SERIES
    if len(series) > 1 and set(series).issubset({"EQ", "BE", "BZ"}):
        return policy.transition_state, DailyTechnicalEligibilityReason.SERIES_TRANSITION_REQUIRES_TECHNICAL_POLICY
    if series == ("EQ",):
        return policy.eq_state, None
    if len(series) == 1 and series[0] in {"BE", "BZ"}:
        return policy.be_bz_same_series_state, None
    return policy.other_state, DailyTechnicalEligibilityReason.SERIES_POLICY_UNRESOLVED


def _coverage_ready(
    coverage: CorporateActionCoverageAssertion | None, instrument_id: str,
    start: date, end: date, at: datetime,
) -> bool:
    if coverage is None or coverage.canonical_instrument_id != instrument_id:
        return False
    window_start = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    window_end = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    return (
        coverage.coverage_state is CorporateActionCoverageState.READY
        and _utc(coverage.window_start) <= window_start
        and _utc(coverage.window_end) >= window_end
        and _utc(coverage.source_known_at) <= at
    )


def _relevant_actions(
    actions: tuple[HistoricalCorporateAction, ...], instrument_id: str, start: date, end: date, at: datetime,
) -> tuple[tuple[HistoricalCorporateAction, ...], bool]:
    seen: set[str] = set()
    values: list[HistoricalCorporateAction] = []
    duplicate = False
    for action in actions:
        if action.canonical_instrument_id != instrument_id or _utc(action.as_of) > at or _utc(action.effective_date) > at:
            continue
        if start <= _utc(action.effective_date).date() <= end:
            if action.action_id in seen:
                duplicate = True
            else:
                seen.add(action.action_id)
                values.append(action)
    return tuple(sorted(values, key=lambda item: (item.effective_date, item.action_id))), duplicate


def _continuity(
    *, requirement: DailyTechnicalRequirement, source_valid: bool,
    series_state: DailyTechnicalSeriesSelectionState, coverage_ready: bool, duplicate_action: bool,
    actions: tuple[HistoricalCorporateAction, ...], bars: tuple[CanonicalOHLCVBar, ...],
    reasons: list[DailyTechnicalEligibilityReason],
) -> tuple[DailyTechnicalPriceContinuityState, DailyTechnicalVolumeContinuityState]:
    if requirement.profile is DailyTechnicalRequirementProfile.RAW_EXCHANGE_HISTORY_ONLY:
        # All action facts are still carried in the receipt, but this profile
        # makes no adjusted-price or volume-continuity claim.
        return DailyTechnicalPriceContinuityState.NOT_APPLICABLE, DailyTechnicalVolumeContinuityState.NOT_APPLICABLE
    if not source_valid:
        price = DailyTechnicalPriceContinuityState.SOURCE_CONFLICT if DailyTechnicalEligibilityReason.SAME_PROVIDER_CONFLICT in reasons else DailyTechnicalPriceContinuityState.IDENTITY_GAP if any(reason in reasons for reason in (DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_REQUIRED, DailyTechnicalEligibilityReason.HISTORICAL_IDENTITY_AMBIGUOUS)) else DailyTechnicalPriceContinuityState.SOURCE_GAP
        return price, DailyTechnicalVolumeContinuityState.VOLUME_SOURCE_GAP
    if series_state is not DailyTechnicalSeriesSelectionState.SERIES_CONTINUITY_READY:
        return DailyTechnicalPriceContinuityState.SERIES_TRANSITION_BLOCKED, DailyTechnicalVolumeContinuityState.VOLUME_REGIME_CHANGED
    if not coverage_ready or duplicate_action:
        return DailyTechnicalPriceContinuityState.INSUFFICIENT_HISTORY, DailyTechnicalVolumeContinuityState.VOLUME_NOT_READY
    kinds = {item.kind for item in actions}
    if CorporateActionKind.RIGHTS in kinds:
        reasons.append(DailyTechnicalEligibilityReason.RIGHTS_ADJUSTMENT_NOT_READY)
        return DailyTechnicalPriceContinuityState.COMPLEX_ACTION_NON_COMPARABLE, DailyTechnicalVolumeContinuityState.VOLUME_ADJUSTMENT_REQUIRED
    if kinds & {CorporateActionKind.MERGER, CorporateActionKind.DEMERGER, CorporateActionKind.DELISTING, CorporateActionKind.SUSPENSION, CorporateActionKind.RELISTING}:
        reasons.append(DailyTechnicalEligibilityReason.COMPLEX_ACTION_NON_COMPARABLE)
        return DailyTechnicalPriceContinuityState.COMPLEX_ACTION_NON_COMPARABLE, DailyTechnicalVolumeContinuityState.VOLUME_ADJUSTMENT_REQUIRED
    if CorporateActionKind.SPLIT in kinds:
        reasons.append(DailyTechnicalEligibilityReason.SPLIT_ADJUSTMENT_REQUIRED)
        return DailyTechnicalPriceContinuityState.ACTION_ADJUSTMENT_REQUIRED, DailyTechnicalVolumeContinuityState.VOLUME_ADJUSTMENT_REQUIRED
    if CorporateActionKind.BONUS in kinds:
        reasons.append(DailyTechnicalEligibilityReason.BONUS_ADJUSTMENT_REQUIRED)
        return DailyTechnicalPriceContinuityState.ACTION_ADJUSTMENT_REQUIRED, DailyTechnicalVolumeContinuityState.VOLUME_ADJUSTMENT_REQUIRED
    if CorporateActionKind.DIVIDEND in kinds:
        reasons.append(DailyTechnicalEligibilityReason.DIVIDEND_PRICE_POLICY_NOT_APPROVED)
        return DailyTechnicalPriceContinuityState.INSUFFICIENT_HISTORY, DailyTechnicalVolumeContinuityState.VOLUME_NOT_READY
    if requirement.requires_volume_continuity and any(bar.volume is None or bar.volume <= 0 for bar in bars):
        reasons.append(DailyTechnicalEligibilityReason.VOLUME_REQUIRED_BUT_ZERO_OR_MISSING)
        return DailyTechnicalPriceContinuityState.PRICE_CONTINUITY_READY, DailyTechnicalVolumeContinuityState.VOLUME_NOT_READY
    return (
        DailyTechnicalPriceContinuityState.PRICE_CONTINUITY_READY,
        DailyTechnicalVolumeContinuityState.VOLUME_CONTINUITY_READY if requirement.requires_volume_continuity else DailyTechnicalVolumeContinuityState.VOLUME_NOT_REQUIRED,
    )


def _bar_fingerprint(value: CanonicalOHLCVBar) -> str:
    fields = source_fields(value)
    return _fingerprint({
        "bar_id": value.bar_id, "source_observation_identity": value.source_observation_identity,
        "trade_date": fields["TradDt"], "series": fields["SctySrs"], "token": fields["FinInstrmId"],
        "open": str(value.open), "high": str(value.high), "low": str(value.low), "close": str(value.close),
        "volume": value.volume, "adjustment_status": value.adjustment_status.value,
    })


def _action_fingerprint(value: HistoricalCorporateAction) -> str:
    return _fingerprint({
        "action_id": value.action_id, "instrument": value.canonical_instrument_id,
        "kind": value.kind.value, "effective_date": _time(value.effective_date), "as_of": _time(value.as_of),
        "ratio_numerator": None if value.ratio_numerator is None else str(value.ratio_numerator),
        "ratio_denominator": None if value.ratio_denominator is None else str(value.ratio_denominator),
        "revision": value.revision,
    })


def _series_policy_payload(value: NseUdiffDailyTechnicalSeriesPolicy) -> dict[str, object]:
    return _series_policy_payload_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _series_policy_payload_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "policy_id": value["policy_id"], "policy_version": value["policy_version"],
        "eq": _enum(value["eq_state"]), "be_bz_same_series": _enum(value["be_bz_same_series_state"]),
        "transition": _enum(value["transition_state"]), "bl": _enum(value["bl_state"]),
        "t0": _enum(value["t0_state"]), "other": _enum(value["other_state"]),
    }


def _receipt_payload(
    value: DailyTechnicalEligibilityReceipt, intervals, bars, actions, expected, observed, series, conflicts, reasons,
) -> dict[str, object]:
    return _receipt_payload_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"receipt_id", "fingerprint"}} | {
        "identity_interval_ids": tuple(item[0] for item in intervals), "identity_interval_fingerprints": tuple(item[1] for item in intervals),
        "source_bar_ids": tuple(item[0] for item in bars), "source_bar_fingerprints": tuple(item[1] for item in bars),
        "action_ids": tuple(item[0] for item in actions), "action_fingerprints": tuple(item[1] for item in actions),
        "expected_sessions": expected, "observed_sessions": observed, "selected_series": series,
        "conflict_fingerprints": conflicts, "reasons": reasons,
    }) | {"receipt_id": value.receipt_id}


def _receipt_payload_values(value: dict[str, object]) -> dict[str, object]:
    requirement = value["requirement"]
    assert isinstance(requirement, DailyTechnicalRequirement)
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "instrument": value["canonical_instrument_id"], "start_session": value["start_session"].isoformat(), "end_session": value["end_session"].isoformat(),
        "requirement": {"profile": requirement.profile.value, "version": requirement.profile_version},
        "evaluation_as_of": _time(value["evaluation_as_of"]), "source_policy": {"id": value["source_policy_id"], "version": value["source_policy_version"], "fingerprint": value["source_policy_fingerprint"]},
        "expected_sessions": [item.isoformat() for item in value["expected_sessions"]], "observed_sessions": [item.isoformat() for item in value["observed_sessions"]],
        "selected_series": list(value["selected_series"]), "series_state": _enum(value["series_state"]),
        "identity_intervals": [{"id": identifier, "fingerprint": fingerprint} for identifier, fingerprint in zip(value["identity_interval_ids"], value["identity_interval_fingerprints"], strict=True)],
        "source_bars": [{"id": identifier, "fingerprint": fingerprint} for identifier, fingerprint in zip(value["source_bar_ids"], value["source_bar_fingerprints"], strict=True)],
        "conflicts": list(value["conflict_fingerprints"]), "action_coverage_fingerprint": value["action_coverage_fingerprint"],
        "actions": [{"id": identifier, "fingerprint": fingerprint} for identifier, fingerprint in zip(value["action_ids"], value["action_fingerprints"], strict=True)],
        "price_continuity": _enum(value["price_continuity"]), "volume_continuity": _enum(value["volume_continuity"]),
        "current_descriptive_state": _enum(value["current_descriptive_state"]), "strict_historical_pit_state": _enum(value["strict_historical_pit_state"]),
        "eligibility": _enum(value["eligibility"]), "reasons": [_enum(item) for item in value["reasons"]],
    }


def _reasons(values: Iterable[DailyTechnicalEligibilityReason]) -> tuple[DailyTechnicalEligibilityReason, ...]:
    return tuple(sorted(set(values), key=lambda value: value.value))


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise DailyTechnicalEligibilityError("DAILY_TECHNICAL_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "CurrentDescriptiveDailyTechnicalState", "DailyTechnicalEligibilityError",
    "DailyTechnicalEligibilityReason", "DailyTechnicalEligibilityReceipt", "DailyTechnicalEligibilityState",
    "DailyTechnicalPriceContinuityState", "DailyTechnicalRequirement", "DailyTechnicalRequirementProfile",
    "DailyTechnicalSeriesSelectionState", "DailyTechnicalVolumeContinuityState",
    "NseUdiffDailyTechnicalSeriesPolicy", "StrictHistoricalPitTechnicalState", "TechnicalEligibleDailyRead",
    "certify_daily_technical_eligibility", "expected_nse_daily_sessions", "expected_udiff_daily_sessions", "ordinary_nse_udiff_daily_technical_series_policy",
    "read_eligible_udiff_daily_bars", "serialize_daily_technical_eligibility",
)
