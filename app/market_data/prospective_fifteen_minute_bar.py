"""Canonical, prospective, provider-neutral fifteen-minute bar derivation.

This module sits after normalized one-minute evidence and before any future
technical reader.  It is intentionally a bounded derivation contract: callers
provide the calendar, the source receipts, and the actual finalization time.
There is no transport, current-time lookup, daemon, scheduler, reader, signal,
portfolio, broker, order, or API dependency here.

The current Dhan one-minute receipt can be adapted at this boundary, but Dhan
is source lineage only.  A canonical fifteen-minute identity contains no
provider identifier and future providers can create equivalent normalized
minute evidence without changing the derivation semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar,
    SessionPhaseType,
    TradingDayState,
)
from app.market_data.dhan_live_bar import (
    DhanProspectiveBarReason,
    DhanProspectiveBarState,
    ProspectiveDhanMinuteReceipt,
)
from app.market_data.models import AdjustmentStatus, Exchange
from app.market_data.technical_bar_contract import (
    CanonicalTechnicalInterval,
    TechnicalIntervalUnit,
    TechnicalTradingPeriod,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "canonical-prospective-fifteen-minute-bar-derivation"
CONTRACT_VERSION = "v1"
POLICY_ID = "canonical-intraday-timeframe-derivation-policy"
POLICY_VERSION = "v1-candidate"
POLICY_FINGERPRINT = "sha256:488ec1573dd07cfb75f0fe385f9957378767ac85aca2435ef6b42640eec33437"
FIFTEEN_MINUTE_INTERVAL = CanonicalTechnicalInterval(TechnicalIntervalUnit.MINUTE, 15)
_IST_TIMEZONE = "Asia/Kolkata"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_ISIN = re.compile(r"[A-Z0-9]{12}\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class ProspectiveFifteenMinuteBarError(ValueError):
    """Stable, fail-closed error for prospective canonical 15m evidence."""


class ProspectiveMinuteEvidenceState(StrEnum):
    CLOSED = "CLOSED"
    NO_TRADE_OBSERVED = "NO_TRADE_OBSERVED"
    INCOMPLETE = "INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class ProspectiveFifteenMinuteState(StrEnum):
    CLOSED = "CLOSED"
    INCOMPLETE = "INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NO_TRADE_OBSERVED = "NO_TRADE_OBSERVED"


class ProspectiveFifteenMinuteReason(StrEnum):
    SOURCE_COVERAGE_MISSING = "SOURCE_COVERAGE_MISSING"
    SOURCE_IDENTITY_INCOMPATIBLE = "SOURCE_IDENTITY_INCOMPATIBLE"
    SOURCE_SESSION_INCOMPATIBLE = "SOURCE_SESSION_INCOMPATIBLE"
    SOURCE_INCOMPLETE = "SOURCE_INCOMPLETE"
    PROVIDER_GAP_OR_UNOBSERVED = "PROVIDER_GAP_OR_UNOBSERVED"
    SOURCE_EVIDENCE_CONFLICTED = "SOURCE_EVIDENCE_CONFLICTED"
    SOURCE_VOLUME_UNVERIFIED = "SOURCE_VOLUME_UNVERIFIED"
    DUPLICATE_SOURCE_CONFLICT = "DUPLICATE_SOURCE_CONFLICT"
    ALL_NO_TRADE_OBSERVED = "ALL_NO_TRADE_OBSERVED"


class ProspectiveFifteenMinuteWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True)
class CanonicalProspectiveMinuteEvidence:
    """Provider-neutral, exact one-minute coverage evidence.

    ``CLOSED`` holds only genuine trade OHLC and an already-verified incremental
    volume.  ``NO_TRADE_OBSERVED`` proves coverage but deliberately carries no
    price.  ``INCOMPLETE`` and ``EVIDENCE_CONFLICTED`` retain source lineage so
    a 15m derivation can fail closed rather than treating absence as no trade.
    """

    source_receipt_id: str
    source_receipt_fingerprint: str
    canonical_security_id: str
    isin: str
    provider_family: str
    session_id: str
    period: TechnicalTradingPeriod
    interval_start: datetime
    interval_end: datetime
    state: ProspectiveMinuteEvidenceState
    source_reasons: tuple[str, ...]
    known_at: datetime
    open: Decimal | None
    high: Decimal | None
    low: Decimal | None
    close: Decimal | None
    volume: int | None
    event_count: int
    source_basis: str
    adjustment_status: AdjustmentStatus
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.source_reasons)))
        values = _minute_values(self, reasons)
        traded = self.state is ProspectiveMinuteEvidenceState.CLOSED
        no_trade = self.state is ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED
        prices = (self.open, self.high, self.low, self.close)
        if (
            not _identifier(self.source_receipt_id)
            or not _fingerprint(self.source_receipt_fingerprint)
            or not _identifier(self.canonical_security_id)
            or not _ISIN.fullmatch(self.isin)
            or not _identifier(self.provider_family)
            or not _identifier(self.session_id)
            or not isinstance(self.period, TechnicalTradingPeriod)
            or not _aware(self.interval_start)
            or not _aware(self.interval_end)
            or _utc(self.interval_end) - _utc(self.interval_start) != timedelta(minutes=1)
            or not _aware(self.known_at)
            or _utc(self.known_at) < _utc(self.interval_end)
            or self.event_count < 0
            or not self.source_basis.strip()
            or not isinstance(self.adjustment_status, AdjustmentStatus)
            or self.source_reasons != reasons
            or any(not _identifier(value) for value in reasons)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_MINUTE_EVIDENCE_INVALID")
        if traded:
            if (
                any(value is None or value <= 0 for value in prices)
                or self.volume is None
                or self.volume <= 0
                or self.event_count < 1
                or self.source_reasons
                or self.adjustment_status is not AdjustmentStatus.RAW
                or self.low is None or self.high is None or self.open is None or self.close is None
                or self.low > min(self.open, self.close) or self.high < max(self.open, self.close)
            ):
                raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_MINUTE_CLOSED_EVIDENCE_INVALID")
        elif no_trade:
            if prices != (None, None, None, None) or self.volume is not None or self.event_count != 0 or not self.source_reasons:
                raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_MINUTE_NO_TRADE_EVIDENCE_INVALID")
        elif any(value is not None for value in prices) or self.volume is not None or not self.source_reasons:
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_MINUTE_NONFINAL_EVIDENCE_INVALID")


def make_prospective_minute_evidence(
    *, source_receipt_id: str, source_receipt_fingerprint: str,
    canonical_security_id: str, isin: str, provider_family: str, session_id: str,
    period: TechnicalTradingPeriod, interval_start: datetime, interval_end: datetime,
    state: ProspectiveMinuteEvidenceState, known_at: datetime,
    source_reasons: Iterable[str] = (), open: Decimal | None = None,
    high: Decimal | None = None, low: Decimal | None = None, close: Decimal | None = None,
    volume: int | None = None, event_count: int = 0, source_basis: str = "RAW_AS_TRADED",
    adjustment_status: AdjustmentStatus = AdjustmentStatus.RAW,
) -> CanonicalProspectiveMinuteEvidence:
    """Construct deterministic normalized one-minute evidence with no provider lock-in."""
    values = dict(
        source_receipt_id=source_receipt_id,
        source_receipt_fingerprint=source_receipt_fingerprint,
        canonical_security_id=canonical_security_id,
        isin=isin.upper(),
        provider_family=provider_family,
        session_id=session_id,
        period=period,
        interval_start=_utc(interval_start),
        interval_end=_utc(interval_end),
        state=state,
        source_reasons=tuple(sorted(set(source_reasons))),
        known_at=_utc(known_at),
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        event_count=event_count,
        source_basis=source_basis,
        adjustment_status=adjustment_status,
    )
    return CanonicalProspectiveMinuteEvidence(**values, fingerprint=_digest(_minute_values_from(values)))


def prospective_minute_evidence_from_dhan(value: ProspectiveDhanMinuteReceipt) -> CanonicalProspectiveMinuteEvidence:
    """Adapt an approved Dhan receipt without making Dhan a canonical identity."""
    if not isinstance(value, ProspectiveDhanMinuteReceipt):
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_DHAN_MINUTE_ADAPTER_INPUT_INVALID")
    states = {
        DhanProspectiveBarState.CLOSED: ProspectiveMinuteEvidenceState.CLOSED,
        DhanProspectiveBarState.NO_TRADE_OBSERVED: ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED,
        DhanProspectiveBarState.INCOMPLETE: ProspectiveMinuteEvidenceState.INCOMPLETE,
        DhanProspectiveBarState.EVIDENCE_CONFLICTED: ProspectiveMinuteEvidenceState.EVIDENCE_CONFLICTED,
    }
    bar = value.bar
    return make_prospective_minute_evidence(
        source_receipt_id=value.receipt_id,
        source_receipt_fingerprint=value.fingerprint,
        canonical_security_id=value.instrument.canonical_security_id,
        isin=value.instrument.isin,
        provider_family="dhan-v2-live-quote",
        session_id=value.session_id,
        period=value.period,
        interval_start=value.interval_start,
        interval_end=value.interval_end,
        state=states[value.state],
        source_reasons=tuple(reason.value for reason in value.reasons),
        known_at=value.known_at,
        open=bar.open if bar else None,
        high=bar.high if bar else None,
        low=bar.low if bar else None,
        close=bar.close if bar else None,
        volume=bar.volume if bar else None,
        event_count=value.observed_event_count,
        source_basis=bar.source_basis if bar else "RAW_AS_TRADED",
        adjustment_status=bar.adjustment_status if bar else AdjustmentStatus.RAW,
    )


@dataclass(frozen=True, slots=True)
class CanonicalProspectiveFifteenMinuteSession:
    """One PIT-visible canonical continuous-trading phase, never a local clock rule."""

    session_id: str
    session_date: date
    phase_timing_id: str
    phase_fingerprint: str
    period: TechnicalTradingPeriod
    calendar_as_of: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        values = _session_values(self)
        if (
            not _identifier(self.session_id)
            or not isinstance(self.session_date, date)
            or not _identifier(self.phase_timing_id)
            or not _fingerprint(self.phase_fingerprint)
            or not isinstance(self.period, TechnicalTradingPeriod)
            or self.period.venue is not Exchange.NSE
            or self.period.segment != "CAPITAL_MARKET"
            or self.period.timezone_id != _IST_TIMEZONE
            or self.period.session_dates != (self.session_date,)
            or not _aware(self.calendar_as_of)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_SESSION_INVALID")


def bind_canonical_prospective_fifteen_minute_session(
    *, calendar: CanonicalMarketSessionCalendar, session_date: date, as_of: datetime,
) -> CanonicalProspectiveFifteenMinuteSession:
    """Resolve exactly one continuous phase at an explicit PIT cutoff."""
    if not isinstance(calendar, CanonicalMarketSessionCalendar) or not isinstance(session_date, date):
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_SESSION_INPUT_INVALID")
    cutoff = _utc(as_of)
    day = calendar.resolve_trading_day(session_date, as_of=cutoff)
    if day.state not in {
        TradingDayState.REGULAR_TRADING_DAY,
        TradingDayState.SPECIAL_TRADING_DAY,
        TradingDayState.MUHURAT_TRADING,
    }:
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_SESSION_UNAVAILABLE")
    phases = tuple(
        phase for phase in calendar.phases_for(session_date, as_of=cutoff)
        if phase.phase_type is SessionPhaseType.REGULAR_CONTINUOUS
    )
    if len(phases) != 1:
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_PHASE_UNAVAILABLE")
    phase = phases[0]
    source_ids = tuple(sorted(set((*day.source_ids, phase.source_id))))
    source_fingerprints = tuple(sorted(set((*day.source_fingerprints, phase.source_fingerprint))))
    # The minute Dhan adapter uses this normal-session identity.  A special
    # session deliberately has its own prefix and can only be used when a
    # future base source supplies matching special-session coverage.
    prefix = "nse-regular" if day.state is TradingDayState.REGULAR_TRADING_DAY else "nse-special"
    values = dict(
        session_id=f"{prefix}:{session_date.isoformat()}:{phase.timing_id}",
        session_date=session_date,
        phase_timing_id=phase.timing_id,
        phase_fingerprint=phase.fingerprint,
        period=TechnicalTradingPeriod(
            venue=Exchange.NSE,
            segment="CAPITAL_MARKET",
            period_id=f"nse-continuous-15m:{session_date.isoformat()}:{phase.timing_id}",
            session_dates=(session_date,),
            starts_at=phase.starts_at,
            ends_at=phase.ends_at,
            timezone_id=_IST_TIMEZONE,
            calendar_id=calendar.calendar_id,
            calendar_fingerprint=calendar.fingerprint,
            session_source_ids=source_ids,
            session_source_fingerprints=source_fingerprints,
        ),
        calendar_as_of=cutoff,
    )
    return CanonicalProspectiveFifteenMinuteSession(**values, fingerprint=_digest(_session_values_from(values)))


@dataclass(frozen=True, slots=True)
class CanonicalProspectiveFifteenMinutePartition:
    session: CanonicalProspectiveFifteenMinuteSession
    ordinal: int
    period: TechnicalTradingPeriod
    interval_start: datetime
    interval_end: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        values = _partition_values(self)
        expected_start = _utc(self.session.period.starts_at) + timedelta(minutes=15 * self.ordinal)
        if (
            not isinstance(self.session, CanonicalProspectiveFifteenMinuteSession)
            or self.ordinal < 0
            or not isinstance(self.period, TechnicalTradingPeriod)
            or self.period.venue is not Exchange.NSE
            or self.period.segment != "CAPITAL_MARKET"
            or self.period.calendar_fingerprint != self.session.period.calendar_fingerprint
            or _utc(self.interval_start) != expected_start
            or _utc(self.interval_end) - _utc(self.interval_start) != timedelta(minutes=15)
            or _utc(self.interval_end) > _utc(self.session.period.ends_at)
            or _utc(self.period.starts_at) != _utc(self.interval_start)
            or _utc(self.period.ends_at) != _utc(self.interval_end)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_PARTITION_INVALID")


def canonical_prospective_fifteen_minute_partitions(
    session: CanonicalProspectiveFifteenMinuteSession,
) -> tuple[CanonicalProspectiveFifteenMinutePartition, ...]:
    """Return only exact full partitions anchored to the actual phase start."""
    if not isinstance(session, CanonicalProspectiveFifteenMinuteSession):
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_PARTITION_INPUT_INVALID")
    duration = _utc(session.period.ends_at) - _utc(session.period.starts_at)
    count = int(duration.total_seconds() // (15 * 60))
    result: list[CanonicalProspectiveFifteenMinutePartition] = []
    for ordinal in range(count):
        start = _utc(session.period.starts_at) + timedelta(minutes=15 * ordinal)
        end = start + timedelta(minutes=15)
        values = dict(
            session=session,
            ordinal=ordinal,
            period=TechnicalTradingPeriod(
                venue=Exchange.NSE,
                segment="CAPITAL_MARKET",
                period_id=f"{session.period.period_id}:15m:{ordinal:03d}",
                session_dates=session.period.session_dates,
                starts_at=start,
                ends_at=end,
                timezone_id=session.period.timezone_id,
                calendar_id=session.period.calendar_id,
                calendar_fingerprint=session.period.calendar_fingerprint,
                session_source_ids=session.period.session_source_ids,
                session_source_fingerprints=session.period.session_source_fingerprints,
            ),
            interval_start=start,
            interval_end=end,
        )
        result.append(CanonicalProspectiveFifteenMinutePartition(**values, fingerprint=_digest(_partition_values_from(values))))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ProspectiveFifteenMinuteSourceLineage:
    source_receipt_id: str
    source_receipt_fingerprint: str
    provider_family: str
    state: ProspectiveMinuteEvidenceState
    interval_start: datetime
    known_at: datetime

    def __post_init__(self) -> None:
        if (
            not _identifier(self.source_receipt_id)
            or not _fingerprint(self.source_receipt_fingerprint)
            or not _identifier(self.provider_family)
            or not isinstance(self.state, ProspectiveMinuteEvidenceState)
            or not _aware(self.interval_start)
            or not _aware(self.known_at)
        ):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalProspectiveFifteenMinuteBar:
    """A genuine-trade-only, completed canonical 15m OHLCV bar."""

    bar_id: str
    canonical_security_id: str
    isin: str
    partition: CanonicalProspectiveFifteenMinutePartition
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    event_count: int
    traded_minute_count: int
    source_lineage: tuple[ProspectiveFifteenMinuteSourceLineage, ...]
    provider_families: tuple[str, ...]
    derivation_policy_id: str
    derivation_policy_version: str
    derivation_policy_fingerprint: str
    known_at: datetime
    source_lineage_fingerprint: str
    adjustment_status: AdjustmentStatus
    fingerprint: str

    def __post_init__(self) -> None:
        lineage = tuple(sorted(self.source_lineage, key=lambda value: (value.interval_start, value.source_receipt_id, value.source_receipt_fingerprint)))
        providers = tuple(sorted(set(self.provider_families)))
        values = _bar_values(self, lineage, providers)
        if (
            self.bar_id != canonical_prospective_fifteen_minute_identity(self.canonical_security_id, self.partition)
            or not _ISIN.fullmatch(self.isin)
            or not isinstance(self.partition, CanonicalProspectiveFifteenMinutePartition)
            or self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0
            or self.low > min(self.open, self.close) or self.high < max(self.open, self.close)
            or self.volume <= 0 or self.event_count < 1 or self.traded_minute_count < 1
            or len(lineage) != 15 or self.source_lineage != lineage
            or len({value.source_receipt_id for value in lineage}) != len(lineage)
            or len({value.interval_start for value in lineage}) != len(lineage)
            or self.provider_families != providers or not providers
            or set(providers) != {value.provider_family for value in lineage}
            or (self.derivation_policy_id, self.derivation_policy_version, self.derivation_policy_fingerprint)
            != (POLICY_ID, POLICY_VERSION, POLICY_FINGERPRINT)
            or not _aware(self.known_at) or _utc(self.known_at) < _utc(self.partition.interval_end)
            or any(_utc(value.known_at) > _utc(self.known_at) for value in lineage)
            or self.source_lineage_fingerprint != _lineage_fingerprint(lineage)
            or self.adjustment_status is not AdjustmentStatus.RAW
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_BAR_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalProspectiveFifteenMinuteReceipt:
    """Immutable result of one bounded prospective 15m derivation attempt."""

    receipt_id: str
    canonical_security_id: str
    isin: str
    partition: CanonicalProspectiveFifteenMinutePartition
    state: ProspectiveFifteenMinuteState
    reasons: tuple[ProspectiveFifteenMinuteReason, ...]
    expected_minute_starts: tuple[datetime, ...]
    source_lineage: tuple[ProspectiveFifteenMinuteSourceLineage, ...]
    known_at: datetime
    bar: CanonicalProspectiveFifteenMinuteBar | None
    derivation_policy_id: str
    derivation_policy_version: str
    derivation_policy_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        reasons = tuple(sorted(set(self.reasons), key=lambda value: value.value))
        expected = tuple(_utc(self.partition.interval_start) + timedelta(minutes=index) for index in range(15))
        lineage = tuple(sorted(self.source_lineage, key=lambda value: (value.interval_start, value.source_receipt_id, value.source_receipt_fingerprint)))
        values = _receipt_values(self, reasons, expected, lineage)
        closed = self.state is ProspectiveFifteenMinuteState.CLOSED
        no_trade = self.state is ProspectiveFifteenMinuteState.NO_TRADE_OBSERVED
        if (
            self.receipt_id != canonical_prospective_fifteen_minute_identity(self.canonical_security_id, self.partition)
            or not _ISIN.fullmatch(self.isin)
            or not isinstance(self.partition, CanonicalProspectiveFifteenMinutePartition)
            or self.reasons != reasons or self.expected_minute_starts != expected or self.source_lineage != lineage
            or len({value.source_receipt_id for value in lineage}) != len(lineage)
            or len({value.interval_start for value in lineage}) != len(lineage)
            or not _aware(self.known_at) or _utc(self.known_at) < _utc(self.partition.interval_end)
            or any(_utc(value.known_at) > _utc(self.known_at) for value in lineage)
            or (self.derivation_policy_id, self.derivation_policy_version, self.derivation_policy_fingerprint)
            != (POLICY_ID, POLICY_VERSION, POLICY_FINGERPRINT)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_RECEIPT_INVALID")
        if closed:
            if self.bar is None or reasons or len(lineage) != 15 or self.bar.bar_id != self.receipt_id or self.bar.known_at != self.known_at:
                raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_CLOSED_INVALID")
        elif self.bar is not None or not reasons:
            raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_NONFINAL_INVALID")
        elif no_trade and (reasons != (ProspectiveFifteenMinuteReason.ALL_NO_TRADE_OBSERVED,) or len(lineage) != 15):
            raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_NO_TRADE_INVALID")


def canonical_prospective_fifteen_minute_identity(
    canonical_security_id: str, partition: CanonicalProspectiveFifteenMinutePartition,
) -> str:
    """Provider-neutral identity for a canonical security and exact session partition."""
    if not _identifier(canonical_security_id) or not isinstance(partition, CanonicalProspectiveFifteenMinutePartition):
        raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_IDENTITY_INPUT_INVALID")
    values = {
        "contract_id": CONTRACT_ID,
        "contract_version": CONTRACT_VERSION,
        "canonical_security_id": canonical_security_id,
        "timeframe": "15m",
        "session_id": partition.session.session_id,
        # Calendar selection time is retained in session lineage but must not
        # make a canonical bar identity depend on a later caller cutoff when
        # the selected phase evidence itself has not changed.
        "phase_fingerprint": partition.session.phase_fingerprint,
        "calendar_fingerprint": partition.period.calendar_fingerprint,
        "interval_start": _time(partition.interval_start),
        "interval_end": _time(partition.interval_end),
    }
    return "canonical-15m:" + _digest(values).removeprefix("sha256:")[:32]


def derive_canonical_prospective_fifteen_minute_receipt(
    *, partition: CanonicalProspectiveFifteenMinutePartition,
    canonical_security_id: str, isin: str,
    source_evidence: Iterable[CanonicalProspectiveMinuteEvidence],
    finalized_at: datetime,
) -> CanonicalProspectiveFifteenMinuteReceipt:
    """Derive one 15m receipt from exact covered one-minute evidence.

    ``finalized_at`` is deliberately supplied by a bounded caller and is the
    actual time HSI had enough evidence; it is never synthesized from interval
    boundaries or a runtime clock.
    """
    if not isinstance(partition, CanonicalProspectiveFifteenMinutePartition) or not _identifier(canonical_security_id) or not _ISIN.fullmatch(isin.upper()):
        raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_DERIVATION_INPUT_INVALID")
    known_at = _utc(finalized_at)
    if known_at < _utc(partition.interval_end):
        raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_FINALIZATION_EARLY")
    evidence = tuple(source_evidence)
    if any(not isinstance(value, CanonicalProspectiveMinuteEvidence) for value in evidence):
        raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_SOURCE_INVALID")
    canonical_isin = isin.upper()
    by_start: dict[datetime, CanonicalProspectiveMinuteEvidence] = {}
    duplicate_conflict = False
    for value in evidence:
        start = _utc(value.interval_start)
        prior = by_start.get(start)
        if prior is None:
            by_start[start] = value
        elif prior != value:
            duplicate_conflict = True
    selected = tuple(sorted(by_start.values(), key=lambda value: (value.interval_start, value.source_receipt_id, value.source_receipt_fingerprint)))
    lineage = tuple(_source_lineage(value) for value in selected)
    reasons: set[ProspectiveFifteenMinuteReason] = set()
    expected_starts = tuple(_utc(partition.interval_start) + timedelta(minutes=index) for index in range(15))
    expected_set = set(expected_starts)
    if duplicate_conflict:
        reasons.add(ProspectiveFifteenMinuteReason.DUPLICATE_SOURCE_CONFLICT)
    if { _utc(value.interval_start) for value in selected } != expected_set:
        reasons.add(ProspectiveFifteenMinuteReason.SOURCE_COVERAGE_MISSING)
    for value in selected:
        if (
            value.canonical_security_id != canonical_security_id
            or value.isin != canonical_isin
            or value.session_id != partition.session.session_id
        ):
            reasons.add(ProspectiveFifteenMinuteReason.SOURCE_IDENTITY_INCOMPATIBLE)
        if (
            value.period.venue is not Exchange.NSE
            or value.period.segment != "CAPITAL_MARKET"
                or value.period.calendar_fingerprint != partition.period.calendar_fingerprint
                or value.period.session_dates != partition.period.session_dates
                or _utc(value.period.starts_at) != _utc(value.interval_start)
                or _utc(value.period.ends_at) != _utc(value.interval_end)
                or _utc(value.interval_start) not in expected_set
            or _utc(value.interval_end) != _utc(value.interval_start) + timedelta(minutes=1)
        ):
            reasons.add(ProspectiveFifteenMinuteReason.SOURCE_SESSION_INCOMPATIBLE)
        if value.state is ProspectiveMinuteEvidenceState.EVIDENCE_CONFLICTED:
            reasons.add(ProspectiveFifteenMinuteReason.SOURCE_EVIDENCE_CONFLICTED)
        elif value.state is ProspectiveMinuteEvidenceState.INCOMPLETE:
            if any(reason in {"PROVIDER_GAP", "MID_INTERVAL_START"} for reason in value.source_reasons):
                reasons.add(ProspectiveFifteenMinuteReason.PROVIDER_GAP_OR_UNOBSERVED)
            else:
                reasons.add(ProspectiveFifteenMinuteReason.SOURCE_INCOMPLETE)
        elif value.state is ProspectiveMinuteEvidenceState.CLOSED and value.volume is None:
            reasons.add(ProspectiveFifteenMinuteReason.SOURCE_VOLUME_UNVERIFIED)
    if any(_utc(value.known_at) > known_at for value in selected):
        raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_FINALIZATION_BEFORE_SOURCE")
    state: ProspectiveFifteenMinuteState
    bar: CanonicalProspectiveFifteenMinuteBar | None = None
    if reasons:
        state = (
            ProspectiveFifteenMinuteState.EVIDENCE_CONFLICTED
            if ProspectiveFifteenMinuteReason.DUPLICATE_SOURCE_CONFLICT in reasons
            or ProspectiveFifteenMinuteReason.SOURCE_EVIDENCE_CONFLICTED in reasons
            else ProspectiveFifteenMinuteState.INCOMPLETE
        )
    elif selected and all(value.state is ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED for value in selected):
        state = ProspectiveFifteenMinuteState.NO_TRADE_OBSERVED
        reasons.add(ProspectiveFifteenMinuteReason.ALL_NO_TRADE_OBSERVED)
    else:
        closed = tuple(value for value in selected if value.state is ProspectiveMinuteEvidenceState.CLOSED)
        if any(value.state not in {ProspectiveMinuteEvidenceState.CLOSED, ProspectiveMinuteEvidenceState.NO_TRADE_OBSERVED} for value in selected):
            raise ProspectiveFifteenMinuteBarError("CANONICAL_PROSPECTIVE_FIFTEEN_MINUTE_SOURCE_STATE_INVALID")
        state = ProspectiveFifteenMinuteState.CLOSED
        providers = tuple(sorted({value.provider_family for value in lineage}))
        bar_values = dict(
            bar_id=canonical_prospective_fifteen_minute_identity(canonical_security_id, partition),
            canonical_security_id=canonical_security_id,
            isin=canonical_isin,
            partition=partition,
            open=closed[0].open,
            high=max(value.high for value in closed if value.high is not None),
            low=min(value.low for value in closed if value.low is not None),
            close=closed[-1].close,
            volume=sum(value.volume or 0 for value in closed),
            event_count=sum(value.event_count for value in closed),
            traded_minute_count=len(closed),
            source_lineage=lineage,
            provider_families=providers,
            derivation_policy_id=POLICY_ID,
            derivation_policy_version=POLICY_VERSION,
            derivation_policy_fingerprint=POLICY_FINGERPRINT,
            known_at=known_at,
            source_lineage_fingerprint=_lineage_fingerprint(lineage),
            adjustment_status=AdjustmentStatus.RAW,
        )
        assert bar_values["open"] is not None and bar_values["close"] is not None
        bar = CanonicalProspectiveFifteenMinuteBar(**bar_values, fingerprint=_digest(_bar_values_from(bar_values)))
    receipt_values = dict(
        receipt_id=canonical_prospective_fifteen_minute_identity(canonical_security_id, partition),
        canonical_security_id=canonical_security_id,
        isin=canonical_isin,
        partition=partition,
        state=state,
        reasons=tuple(sorted(reasons, key=lambda value: value.value)),
        expected_minute_starts=expected_starts,
        source_lineage=lineage,
        known_at=known_at,
        bar=bar,
        derivation_policy_id=POLICY_ID,
        derivation_policy_version=POLICY_VERSION,
        derivation_policy_fingerprint=POLICY_FINGERPRINT,
    )
    return CanonicalProspectiveFifteenMinuteReceipt(**receipt_values, fingerprint=_digest(_receipt_values_from(receipt_values)))


@dataclass(frozen=True, slots=True)
class ProspectiveFifteenMinuteConflict:
    conflict_id: str
    receipt_id: str
    stored_fingerprint: str
    incoming_fingerprint: str
    detected_at: datetime
    fingerprint: str

    def __post_init__(self) -> None:
        values = _conflict_values(self)
        if (
            not _identifier(self.conflict_id) or not _identifier(self.receipt_id)
            or not _fingerprint(self.stored_fingerprint) or not _fingerprint(self.incoming_fingerprint)
            or self.stored_fingerprint == self.incoming_fingerprint or not _aware(self.detected_at)
            or self.fingerprint != _digest(values)
        ):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_CONFLICT_INVALID")


class ProspectiveCanonicalFifteenMinuteStore:
    """Append-only durable 15m receipts over the existing immutable snapshot store."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(
        self, receipt: CanonicalProspectiveFifteenMinuteReceipt, *, detected_at: datetime,
    ) -> ProspectiveFifteenMinuteWriteOutcome:
        if not isinstance(receipt, CanonicalProspectiveFifteenMinuteReceipt):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_PERSISTENCE_INPUT_INVALID")
        detected = _utc(detected_at)
        snapshot_id = f"canonical-prospective-15m:{receipt.receipt_id}"
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is None:
            self._repository.save_snapshot(CoreApiSnapshot(
                snapshot_id, CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR,
                "v1", "canonical-prospective-fifteen-minute-receipt-v1", receipt.fingerprint,
                receipt.known_at, receipt,
            ))
            return ProspectiveFifteenMinuteWriteOutcome.INSERTED
        if not isinstance(existing.payload, CanonicalProspectiveFifteenMinuteReceipt):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_STORAGE_TYPE_INVALID")
        if existing.payload == receipt or _same_derived_content(existing.payload, receipt):
            return ProspectiveFifteenMinuteWriteOutcome.ALREADY_PRESENT
        conflict = _conflict(existing.payload, receipt, detected)
        conflict_snapshot_id = f"canonical-prospective-15m-conflict:{conflict.conflict_id}"
        retained = self._repository.get_snapshot(conflict_snapshot_id)
        if retained is None:
            self._repository.save_snapshot(CoreApiSnapshot(
                conflict_snapshot_id, CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT,
                "v1", "canonical-prospective-fifteen-minute-conflict-v1", conflict.fingerprint,
                conflict.detected_at, conflict,
            ))
        elif retained.payload != conflict:
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_CONFLICT_IMMUTABLE_COLLISION")
        return ProspectiveFifteenMinuteWriteOutcome.CONFLICT

    def get(self, receipt_id: str) -> CanonicalProspectiveFifteenMinuteReceipt | None:
        if not _identifier(receipt_id):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_RECEIPT_ID_INVALID")
        snapshot = self._repository.get_snapshot(f"canonical-prospective-15m:{receipt_id}")
        if snapshot is None:
            return None
        if not isinstance(snapshot.payload, CanonicalProspectiveFifteenMinuteReceipt):
            raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_STORAGE_TYPE_INVALID")
        return snapshot.payload


def serialize_canonical_prospective_fifteen_minute_receipt(
    value: CanonicalProspectiveFifteenMinuteReceipt,
) -> str:
    value.__post_init__()
    return _canonical(_receipt_payload(value) | {"fingerprint": value.fingerprint})


def _source_lineage(value: CanonicalProspectiveMinuteEvidence) -> ProspectiveFifteenMinuteSourceLineage:
    return ProspectiveFifteenMinuteSourceLineage(
        value.source_receipt_id, value.source_receipt_fingerprint, value.provider_family,
        value.state, _utc(value.interval_start), _utc(value.known_at),
    )


def _same_derived_content(left: CanonicalProspectiveFifteenMinuteReceipt, right: CanonicalProspectiveFifteenMinuteReceipt) -> bool:
    if left.state is not right.state or left.receipt_id != right.receipt_id:
        return False
    if (
        left.canonical_security_id, left.isin, left.partition, left.reasons,
        left.expected_minute_starts, left.source_lineage,
        left.derivation_policy_id, left.derivation_policy_version, left.derivation_policy_fingerprint,
    ) != (
        right.canonical_security_id, right.isin, right.partition, right.reasons,
        right.expected_minute_starts, right.source_lineage,
        right.derivation_policy_id, right.derivation_policy_version, right.derivation_policy_fingerprint,
    ):
        return False
    if left.bar is None or right.bar is None:
        return left.bar is right.bar
    return _bar_semantic_payload(left.bar) == _bar_semantic_payload(right.bar)


def _conflict(
    stored: CanonicalProspectiveFifteenMinuteReceipt,
    incoming: CanonicalProspectiveFifteenMinuteReceipt,
    detected_at: datetime,
) -> ProspectiveFifteenMinuteConflict:
    values = dict(
        conflict_id="canonical-15m-conflict:" + _digest({
            "receipt_id": stored.receipt_id,
            "stored": stored.fingerprint,
            "incoming": incoming.fingerprint,
        }).removeprefix("sha256:")[:32],
        receipt_id=stored.receipt_id,
        stored_fingerprint=stored.fingerprint,
        incoming_fingerprint=incoming.fingerprint,
        detected_at=_utc(detected_at),
    )
    return ProspectiveFifteenMinuteConflict(**values, fingerprint=_digest(_conflict_values_from(values)))


def _minute_values(value: CanonicalProspectiveMinuteEvidence, reasons: tuple[str, ...]) -> dict[str, object]:
    return _minute_values_from({
        "source_receipt_id": value.source_receipt_id, "source_receipt_fingerprint": value.source_receipt_fingerprint,
        "canonical_security_id": value.canonical_security_id, "isin": value.isin, "provider_family": value.provider_family,
        "session_id": value.session_id, "period": value.period, "interval_start": value.interval_start,
        "interval_end": value.interval_end, "state": value.state, "source_reasons": reasons,
        "known_at": value.known_at, "open": value.open, "high": value.high, "low": value.low,
        "close": value.close, "volume": value.volume, "event_count": value.event_count,
        "source_basis": value.source_basis, "adjustment_status": value.adjustment_status,
    })


def _minute_values_from(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "source_receipt_id": value["source_receipt_id"], "source_receipt_fingerprint": value["source_receipt_fingerprint"],
        "canonical_security_id": value["canonical_security_id"], "isin": value["isin"], "provider_family": value["provider_family"],
        "session_id": value["session_id"], "period": _period_payload(value["period"]),
        "interval_start": _time(value["interval_start"]), "interval_end": _time(value["interval_end"]),
        "state": _enum(value["state"]), "source_reasons": list(value["source_reasons"]),
        "known_at": _time(value["known_at"]), "open": _decimal(value["open"]), "high": _decimal(value["high"]),
        "low": _decimal(value["low"]), "close": _decimal(value["close"]), "volume": value["volume"],
        "event_count": value["event_count"], "source_basis": value["source_basis"], "adjustment_status": _enum(value["adjustment_status"]),
    }


def _session_values(value: CanonicalProspectiveFifteenMinuteSession) -> dict[str, object]:
    return _session_values_from({"session_id": value.session_id, "session_date": value.session_date, "phase_timing_id": value.phase_timing_id, "phase_fingerprint": value.phase_fingerprint, "period": value.period, "calendar_as_of": value.calendar_as_of})


def _session_values_from(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "session_id": value["session_id"],
        "session_date": value["session_date"].isoformat(), "phase_fingerprint": value["phase_fingerprint"],
        "phase_timing_id": value["phase_timing_id"], "period": _period_payload(value["period"]),
        "calendar_as_of": _time(value["calendar_as_of"]),
    }


def _partition_values(value: CanonicalProspectiveFifteenMinutePartition) -> dict[str, object]:
    return _partition_values_from({"session": value.session, "ordinal": value.ordinal, "period": value.period, "interval_start": value.interval_start, "interval_end": value.interval_end})


def _partition_values_from(value: dict[str, object]) -> dict[str, object]:
    session = value["session"]
    assert isinstance(session, CanonicalProspectiveFifteenMinuteSession)
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "session_fingerprint": session.fingerprint,
        "ordinal": value["ordinal"], "period": _period_payload(value["period"]),
        "interval_start": _time(value["interval_start"]), "interval_end": _time(value["interval_end"]),
    }


def _bar_values(value: CanonicalProspectiveFifteenMinuteBar, lineage: tuple[ProspectiveFifteenMinuteSourceLineage, ...], providers: tuple[str, ...]) -> dict[str, object]:
    return _bar_values_from({
        "bar_id": value.bar_id, "canonical_security_id": value.canonical_security_id, "isin": value.isin,
        "partition": value.partition, "open": value.open, "high": value.high, "low": value.low, "close": value.close,
        "volume": value.volume, "event_count": value.event_count, "traded_minute_count": value.traded_minute_count,
        "source_lineage": lineage, "provider_families": providers, "derivation_policy_id": value.derivation_policy_id,
        "derivation_policy_version": value.derivation_policy_version, "derivation_policy_fingerprint": value.derivation_policy_fingerprint,
        "known_at": value.known_at, "source_lineage_fingerprint": value.source_lineage_fingerprint,
        "adjustment_status": value.adjustment_status,
    })


def _bar_values_from(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "bar_id": value["bar_id"],
        "canonical_security_id": value["canonical_security_id"], "isin": value["isin"],
        "partition_fingerprint": value["partition"].fingerprint, "timeframe": "15m",
        "open": _decimal(value["open"]), "high": _decimal(value["high"]), "low": _decimal(value["low"]), "close": _decimal(value["close"]),
        "volume": value["volume"], "event_count": value["event_count"], "traded_minute_count": value["traded_minute_count"],
        "source_lineage": [_lineage_payload(item) for item in value["source_lineage"]],
        "provider_families": list(value["provider_families"]), "derivation_policy_id": value["derivation_policy_id"],
        "derivation_policy_version": value["derivation_policy_version"], "derivation_policy_fingerprint": value["derivation_policy_fingerprint"],
        "known_at": _time(value["known_at"]), "source_lineage_fingerprint": value["source_lineage_fingerprint"],
        "adjustment_status": _enum(value["adjustment_status"]),
    }


def _receipt_values(value: CanonicalProspectiveFifteenMinuteReceipt, reasons: tuple[ProspectiveFifteenMinuteReason, ...], expected: tuple[datetime, ...], lineage: tuple[ProspectiveFifteenMinuteSourceLineage, ...]) -> dict[str, object]:
    return _receipt_values_from({
        "receipt_id": value.receipt_id, "canonical_security_id": value.canonical_security_id, "isin": value.isin,
        "partition": value.partition, "state": value.state, "reasons": reasons, "expected_minute_starts": expected,
        "source_lineage": lineage, "known_at": value.known_at, "bar": value.bar,
        "derivation_policy_id": value.derivation_policy_id, "derivation_policy_version": value.derivation_policy_version,
        "derivation_policy_fingerprint": value.derivation_policy_fingerprint,
    })


def _receipt_values_from(value: dict[str, object]) -> dict[str, object]:
    bar = value["bar"]
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "receipt_id": value["receipt_id"],
        "canonical_security_id": value["canonical_security_id"], "isin": value["isin"],
        "partition_fingerprint": value["partition"].fingerprint, "state": _enum(value["state"]),
        "reasons": [_enum(item) for item in value["reasons"]], "expected_minute_starts": [_time(item) for item in value["expected_minute_starts"]],
        "source_lineage": [_lineage_payload(item) for item in value["source_lineage"]], "known_at": _time(value["known_at"]),
        "bar_fingerprint": bar.fingerprint if isinstance(bar, CanonicalProspectiveFifteenMinuteBar) else None,
        "derivation_policy_id": value["derivation_policy_id"], "derivation_policy_version": value["derivation_policy_version"],
        "derivation_policy_fingerprint": value["derivation_policy_fingerprint"],
    }


def _receipt_payload(value: CanonicalProspectiveFifteenMinuteReceipt) -> dict[str, object]:
    return _receipt_values(value, value.reasons, value.expected_minute_starts, value.source_lineage) | {"bar": None if value.bar is None else _bar_values(value.bar, value.bar.source_lineage, value.bar.provider_families)}


def _bar_semantic_payload(value: CanonicalProspectiveFifteenMinuteBar) -> dict[str, object]:
    payload = _bar_values(value, value.source_lineage, value.provider_families)
    payload.pop("known_at")
    return payload


def _lineage_payload(value: ProspectiveFifteenMinuteSourceLineage) -> dict[str, object]:
    return {
        "source_receipt_id": value.source_receipt_id, "source_receipt_fingerprint": value.source_receipt_fingerprint,
        "provider_family": value.provider_family, "state": value.state.value,
        "interval_start": _time(value.interval_start), "known_at": _time(value.known_at),
    }


def _lineage_fingerprint(value: tuple[ProspectiveFifteenMinuteSourceLineage, ...]) -> str:
    return _digest([_lineage_payload(item) for item in value])


def _conflict_values(value: ProspectiveFifteenMinuteConflict) -> dict[str, object]:
    return _conflict_values_from({"conflict_id": value.conflict_id, "receipt_id": value.receipt_id, "stored_fingerprint": value.stored_fingerprint, "incoming_fingerprint": value.incoming_fingerprint, "detected_at": value.detected_at})


def _conflict_values_from(value: dict[str, object]) -> dict[str, object]:
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "conflict_id": value["conflict_id"], "receipt_id": value["receipt_id"], "stored_fingerprint": value["stored_fingerprint"], "incoming_fingerprint": value["incoming_fingerprint"], "detected_at": _time(value["detected_at"])}


def _period_payload(value: object) -> dict[str, object]:
    assert isinstance(value, TechnicalTradingPeriod)
    return {
        "venue": value.venue.value, "segment": value.segment, "period_id": value.period_id,
        "session_dates": [item.isoformat() for item in value.session_dates], "starts_at": _time(value.starts_at), "ends_at": _time(value.ends_at),
        "timezone_id": value.timezone_id, "calendar_id": value.calendar_id, "calendar_fingerprint": value.calendar_fingerprint,
        "session_source_ids": list(value.session_source_ids), "session_source_fingerprints": list(value.session_source_fingerprints),
    }


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode()).hexdigest()


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_FINGERPRINT.fullmatch(value))


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise ProspectiveFifteenMinuteBarError("PROSPECTIVE_FIFTEEN_MINUTE_TIMESTAMP_MUST_BE_AWARE")
    return value.astimezone(UTC)


def _time(value: object) -> str | None:
    return _utc(value).isoformat() if isinstance(value, datetime) else None


def _decimal(value: object) -> str | None:
    return str(value) if isinstance(value, Decimal) else None


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)
