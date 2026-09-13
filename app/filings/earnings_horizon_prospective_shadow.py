"""Prospective Layer-1 event observations. No source acquisition or gate authority.

Inputs are canonical receipts, calendar, bars and explicit official result
links. Outcomes are separate immutable records, never pre-event inputs.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
from enum import StrEnum
import re
from zoneinfo import ZoneInfo

from app.analysis.models import AnalysisStatus
from app.analysis.technical import TechnicalAnalysisEngine
from app.domain.models import AsOfSnapshot, StrategyVersionReference, ValidationResult, ValidationStatus
from app.filings.earnings_schedule_identity import EarningsScheduleIdentityResolution, IdentityState
from app.filings.earnings_schedule_known_at import SourceTimestampEvidence, SourceTimestampSemanticAuthority, TimestampFieldSemantic
from app.filings.earnings_schedule_prospective_receipt_collector import (
    ProspectiveQualifiedScheduleReceipt, ProspectiveRawArtifactReceipt,
    ProspectiveSourceObservation, _explicit_lifecycle,
)
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.fundamentals.models import FinancialFact
from app.gates.official_earnings_schedule_candidate import ScheduleLifecycleState
from app.historical.canonical_market_session_event_time import (
    CanonicalMarketSessionCalendar, EventSessionState,
    TradingDayState, align_event_to_canonical_session,
)
from app.historical.filing_timestamp_timezone_provenance import FilingTimestampProvenanceReceipt, canonical_event_timestamp_from_receipt
from app.market_data.daily_technical_bar_temporal_evidence import (
    DailyBarSourceTimingEvidence, DailyStrictPitUsability,
    resolve_daily_technical_bar_temporal_evidence,
)
from app.market_data.models import CanonicalOHLCVBar, Exchange, MarketDataQualityValidator, Timeframe
from app.market_data.bridge import price_bar_observation


VERSION = "earnings-horizon-prospective-shadow/v1"
CALIBRATION_CONTRACT = "earnings-blackout-horizon-calibration-contract/v1"
CALIBRATION_FINGERPRINT = "sha256:4b9a920620d1dfeebaa247721b234b60d7715b86e2cec0d436019719b1026a5b"
MODE = "PROSPECTIVE_SHADOW_CALIBRATION"
DEFERRED = ("LAYER2_ACTION_IMPACT", "MAE", "MEASURED_SLIPPAGE", "MFE", "POST_EVENT_WINDOW", "TAIL_CUTOFF", "VOLATILITY_WINDOW")
IST = ZoneInfo("Asia/Kolkata")


class EarningsHorizonShadowError(ValueError):
    pass


class ShadowState(StrEnum):
    SCHEDULE_OBSERVED = "SCHEDULE_OBSERVED"
    PRE_EVENT_TRACKING = "PRE_EVENT_TRACKING"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    RESULT_LINK_PENDING = "RESULT_LINK_PENDING"
    RESULT_OBSERVED = "RESULT_OBSERVED"
    OUTCOME_READY = "OUTCOME_READY"
    TEMPORAL_OUTCOME_INCOMPLETE = "TEMPORAL_OUTCOME_INCOMPLETE"
    CONFLICTED = "CONFLICTED"


class ShadowQuality(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    PARTIAL = "PARTIAL"
    TEMPORAL_INCOMPLETE = "TEMPORAL_INCOMPLETE"
    RESULT_LINK_PENDING = "RESULT_LINK_PENDING"
    CONFLICTED = "CONFLICTED"


class ResultLinkState(StrEnum):
    LINKED = "LINKED"
    PENDING = "PENDING"
    AMBIGUOUS = "AMBIGUOUS"
    UNAVAILABLE = "UNAVAILABLE"


def utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EarningsHorizonShadowError("SHADOW_TIMEZONE_REQUIRED")
    return value.astimezone(UTC)


def _plain(value):
    # Extend the existing canonical encoder only for dates and MappingProxyType.
    if isinstance(value, FilingTimestampProvenanceReceipt):
        # A raw local time is retained descriptively by its canonical owner;
        # it must not be assigned a timezone by the shadow serializer.
        return {f.name: (value.parsed_local_timestamp.isoformat() if value.parsed_local_timestamp else None)
                if f.name == "parsed_local_timestamp" else _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, date):
        return value.isoformat()
    if is_dataclass(value):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return tuple(_plain(v) for v in value)
    return value


def fingerprint(value: object) -> str:
    return content_fingerprint(_plain(value))


def _body(value: object) -> dict[str, object]:
    return {f.name: getattr(value, f.name) for f in fields(value) if f.name not in {"record_id", "fingerprint"}}


def _record(kind, **body):
    body = {f.name: f.default for f in fields(kind) if f.default is not MISSING} | body
    body = body | {"version": VERSION, "calibration_contract": CALIBRATION_CONTRACT,
                   "calibration_fingerprint": CALIBRATION_FINGERPRINT,
                   "mode": MODE, "actionability": "WATCH_ONLY", "execution_status": "NON_EXECUTABLE"}
    fp = fingerprint(body)
    return kind(**body, record_id="earnings-shadow:" + kind.__name__ + ":" + fp[7:], fingerprint=fp)


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowRecord:
    record_id: str
    fingerprint: str
    version: str
    calibration_contract: str
    calibration_fingerprint: str
    mode: str
    actionability: str
    execution_status: str

    def __post_init__(self):
        fp = fingerprint(_body(self))
        if (self.version, self.calibration_contract, self.calibration_fingerprint, self.mode,
            self.actionability, self.execution_status) != (
            VERSION, CALIBRATION_CONTRACT, CALIBRATION_FINGERPRINT, MODE, "WATCH_ONLY", "NON_EXECUTABLE"
        ) or self.fingerprint != fp or self.record_id != "earnings-shadow:" + type(self).__name__ + ":" + fp[7:]:
            raise EarningsHorizonShadowError("SHADOW_RECORD_TAMPERED")


@dataclass(frozen=True, slots=True, order=True)
class ShadowReference:
    record_id: str
    fingerprint: str

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9._:/+-]+", self.record_id) or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.fingerprint):
            raise EarningsHorizonShadowError("SHADOW_LINEAGE_INVALID")


def reference(value) -> ShadowReference:
    return ShadowReference(value.record_id, value.fingerprint)


@dataclass(frozen=True, slots=True)
class QualifiedShadowInput:
    """Validated projection of collector evidence, not another identity source."""
    receipt: ProspectiveQualifiedScheduleReceipt
    observation: ProspectiveSourceObservation
    artifact: ProspectiveRawArtifactReceipt
    identity: EarningsScheduleIdentityResolution

    def __post_init__(self):
        r, o, a, i = self.receipt, self.observation, self.artifact, self.identity
        for value in (r, o, a, i):
            value.__post_init__()
        if (r.source_observation_id != o.observation_id or o.raw_artifact_id != a.artifact_id
            or r.source_family != o.source_family or o.source_family != a.source_family
            or r.source_payload_fingerprint != o.source_record_fingerprint
            or r.source_filing_identity != o.source_record_identity
            or o.discovery_observation_id is None
            or o.first_observed_at != r.system_first_observed.observed_at
            or a.first_observed_at > o.first_observed_at
            or i.resolution_state is not IdentityState.RESOLVED
            or i.canonical_instrument_id != r.canonical_instrument_id
            or i.fingerprint != r.identity_fingerprint or i.as_of != o.first_observed_at):
            raise EarningsHorizonShadowError("SHADOW_COLLECTOR_LINEAGE_INVALID")

    @property
    def known_at(self) -> datetime:
        # Collector v1 stamps request start, so processed_at is the conservative
        # completed-observation bound. Never rewrite the original first-observed.
        return self.receipt.processed_at


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowScheduleVersion:
    """Source-owned receipt and references; never copy raw downloads into shadow."""
    receipt: ProspectiveQualifiedScheduleReceipt
    source_observation: ShadowReference
    raw_artifact: ShadowReference
    raw_document_fingerprint: str
    source_exchange: Exchange

    def __post_init__(self):
        self.receipt.__post_init__(); self.source_observation.__post_init__(); self.raw_artifact.__post_init__()
        if (self.source_observation.record_id != self.receipt.source_observation_id
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.raw_document_fingerprint)
            or self.source_exchange.value not in {"NSE", "BSE"}):
            raise EarningsHorizonShadowError("SHADOW_SCHEDULE_REFERENCE_INVALID")

    @property
    def known_at(self):
        return self.receipt.processed_at


def _schedule_version(value: QualifiedShadowInput) -> ShadowScheduleVersion:
    return ShadowScheduleVersion(receipt=value.receipt,
        source_observation=ShadowReference(value.observation.observation_id, value.observation.fingerprint),
        raw_artifact=ShadowReference(value.artifact.artifact_id, value.artifact.fingerprint),
        raw_document_fingerprint=value.artifact.payload_fingerprint, source_exchange=value.observation.source.exchange)


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowEvent(ShadowRecord):
    logical_event_id: str
    canonical_instrument_id: str
    anchor_receipt_ids: tuple[str, ...]
    schedule_versions: tuple[ShadowScheduleVersion, ...]
    as_of: datetime
    first_observed_at: datetime
    effective_receipt_ids: tuple[str, ...]
    scheduled_event_date: date | None
    state: ShadowState
    quality: ShadowQuality
    reasons: tuple[str, ...]

    def __post_init__(self):
        ShadowRecord.__post_init__(self)
        for value in self.schedule_versions:
            value.__post_init__()
        roots = tuple(v for v in self.schedule_versions if v.receipt.receipt_id in self.anchor_receipt_ids)
        children = {v.receipt.revision_of_receipt_id for v in self.schedule_versions}
        effective = tuple(v for v in self.schedule_versions if v.receipt.receipt_id not in children)
        if (not self.schedule_versions or len({v.receipt.receipt_id for v in self.schedule_versions}) != len(self.schedule_versions)
            or not roots or len(roots) != len(self.anchor_receipt_ids)
            or self.anchor_receipt_ids != tuple(sorted(set(self.anchor_receipt_ids)))
            or self.schedule_versions != tuple(sorted(self.schedule_versions, key=lambda v: (v.known_at, v.receipt.receipt_id)))
            or self.logical_event_id != "earnings-event:" + fingerprint((VERSION, self.canonical_instrument_id, min(v.receipt.event_date for v in roots)))[7:]
            or any(v.receipt.canonical_instrument_id != self.canonical_instrument_id or v.known_at > utc(self.as_of) for v in self.schedule_versions)
            or self.first_observed_at != min(v.receipt.system_first_observed.observed_at for v in self.schedule_versions)
            or self.effective_receipt_ids != tuple(sorted(v.receipt.receipt_id for v in effective))
            or ((self.state is ShadowState.CONFLICTED) != (self.quality is ShadowQuality.CONFLICTED))
            or ((self.state is ShadowState.CONFLICTED) != bool(self.reasons))
            or ((self.state is ShadowState.CONFLICTED) != (self.scheduled_event_date is None))
            or (self.scheduled_event_date is not None and {v.receipt.event_date for v in effective} != {self.scheduled_event_date})
            or not isinstance(self.state, ShadowState) or not isinstance(self.quality, ShadowQuality)):
            raise EarningsHorizonShadowError("SHADOW_EVENT_INVALID")


def reconcile_events(values: tuple[QualifiedShadowInput, ...], *, as_of: datetime) -> tuple[ShadowEvent, ...]:
    """Exact parent chains; overlapping independent documents are unresolved.

    Only identical primary-document bytes can reconcile independent sources.
    Overlapping notice/event intervals form an exclusion group, not a guessed
    economic join. Distinct later non-overlapping events remain processable.
    """
    point = utc(as_of)
    indexed = {}
    for value in values:
        value.__post_init__()
        key = value.receipt.receipt_id
        if key in indexed and indexed[key] != value:
            raise EarningsHorizonShadowError("SHADOW_DUPLICATE_CONFLICT")
        indexed[key] = value
    visible = {key: v for key, v in indexed.items() if v.known_at <= point}
    chains = {}
    invalid = set()
    for key, value in sorted(visible.items()):
        cursor, seen = value, set()
        while cursor.receipt.revision_of_receipt_id is not None:
            parent = visible.get(cursor.receipt.revision_of_receipt_id)
            if (cursor.receipt.receipt_id in seen or parent is None or parent.known_at >= cursor.known_at
                or parent.receipt.canonical_instrument_id != value.receipt.canonical_instrument_id
                or parent.receipt.source_family != cursor.receipt.source_family
                or parent.receipt.source_filing_identity != cursor.receipt.source_filing_identity
                or parent.receipt.lifecycle_state in {ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED}
                or _explicit_lifecycle(cursor.observation.source) != cursor.receipt.lifecycle_state):
                invalid.add(key)
                break
            seen.add(cursor.receipt.receipt_id)
            cursor = parent
        chains.setdefault(cursor.receipt.receipt_id, []).append(value)
    groups = []
    for root_id, chain in sorted(chains.items()):
        root = visible[root_id]
        start = root.known_at.astimezone(IST).date()
        end = max(v.receipt.event_date for v in chain)
        if root.receipt.event_date <= start and not any(v.receipt.receipt_id in invalid for v in chain):
            continue  # A schedule first seen after/on event date is not prospective.
        matches = [g for g in groups if g[0] == root.receipt.canonical_instrument_id and start <= g[2] and end >= g[1]]
        group = [root.receipt.canonical_instrument_id, start, end, [root_id], list(chain)]
        for old in matches:
            groups.remove(old)
            group[1], group[2] = min(group[1], old[1]), max(group[2], old[2])
            group[3].extend(old[3]); group[4].extend(old[4])
        groups.append(group)
    output = []
    for instrument, _, _, roots, chain in groups:
        ordered = tuple(sorted(chain, key=lambda v: (v.known_at, v.receipt.receipt_id)))
        children = {v.receipt.revision_of_receipt_id for v in ordered}
        effective = tuple(v for v in ordered if v.receipt.receipt_id not in children)
        bad = any(v.receipt.receipt_id in invalid for v in ordered)
        # Multiple heads of one chain, or differing independent documents,
        # cannot be resolved by input order, source preference, or nearest date.
        reasons = []
        if bad or len(effective) != len(roots):
            reasons.append("LIFECYCLE_LINEAGE_CONFLICT")
        agreement = {(v.receipt.event_date, v.receipt.purpose_classification, v.receipt.lifecycle_state) for v in effective}
        if len(agreement) != 1 or (len(roots) > 1 and len({v.artifact.payload_fingerprint for v in effective}) != 1):
            reasons.append("LOGICAL_EVENT_RECONCILIATION_UNRESOLVED")
        scheduled = effective[0].receipt.event_date if not reasons else None
        lifecycle = effective[0].receipt.lifecycle_state
        state = ShadowState.SCHEDULE_OBSERVED
        if reasons:
            state = ShadowState.CONFLICTED
        elif lifecycle in {ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED}:
            state = ShadowState.CANCELLED
        elif lifecycle is ScheduleLifecycleState.RESCHEDULED:
            state = ShadowState.RESCHEDULED
        # Stable when a second exchange later delivers the identical document.
        # Uncertain date/chain combinations are exclusions, not counted events.
        anchor_date = min(visible[key].receipt.event_date for key in roots)
        logical_id = "earnings-event:" + fingerprint((VERSION, instrument, anchor_date))[7:]
        output.append(_record(ShadowEvent, logical_event_id=logical_id, canonical_instrument_id=instrument,
            anchor_receipt_ids=tuple(sorted(roots)), schedule_versions=tuple(_schedule_version(v) for v in ordered), as_of=max(v.known_at for v in ordered),
            first_observed_at=min(v.receipt.system_first_observed.observed_at for v in ordered),
            effective_receipt_ids=tuple(sorted(v.receipt.receipt_id for v in effective)), scheduled_event_date=scheduled,
            state=state, quality=ShadowQuality.CONFLICTED if reasons else ShadowQuality.PARTIAL, reasons=tuple(sorted(reasons))))
    return tuple(sorted(output, key=lambda v: v.logical_event_id))


def session_distance(calendar: CanonicalMarketSessionCalendar, start: date, end: date, *, as_of: datetime) -> int | None:
    calendar.__post_init__()
    if end < start or not calendar.coverage_start <= start <= end <= calendar.coverage_end:
        return None
    if calendar.resolve_trading_day(end, as_of=utc(as_of)).state is not TradingDayState.REGULAR_TRADING_DAY:
        return None
    count, cursor = 0, start + timedelta(days=1)
    while cursor <= end:
        state = calendar.resolve_trading_day(cursor, as_of=as_of).state
        if state is TradingDayState.REGULAR_TRADING_DAY:
            count += 1
        elif state not in {TradingDayState.HOLIDAY, TradingDayState.WEEKEND_NON_TRADING}:
            return None  # Unknown/non-standard session is not an inferred day.
        cursor += timedelta(days=1)
    return count


@dataclass(frozen=True, slots=True)
class ShadowDailyInput:
    bar: CanonicalOHLCVBar
    timing: DailyBarSourceTimingEvidence
    conflicted: bool = False

    def __post_init__(self):
        self.bar.__post_init__(); self.bar.provenance.__post_init__(); self.timing.__post_init__()
        MarketDataQualityValidator.validate_bar(self.bar)
        if self.bar.timeframe is not Timeframe.DAILY or self.bar.provenance.provider != self.timing.provider or type(self.conflicted) is not bool:
            raise EarningsHorizonShadowError("SHADOW_DAILY_INPUT_INVALID")


def visible_bar(value: ShadowDailyInput, calendar: CanonicalMarketSessionCalendar, as_of: datetime):
    value.__post_init__()
    temporal = resolve_daily_technical_bar_temporal_evidence(canonical_bar_id=value.bar.bar_id,
        bar=value.bar, calendar=calendar, evaluation_as_of=utc(as_of), source_timing=value.timing)
    if (value.conflicted or temporal.strict_pit_usability is not DailyStrictPitUsability.USABLE
        or any(at is not None and at > utc(as_of) for at in (value.bar.provenance.received_at,
            value.bar.provenance.exchange_timestamp, value.bar.provenance.provider_timestamp))):
        return None
    return temporal


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowSessionObservation(ShadowRecord):
    logical_event_id: str
    canonical_instrument_id: str
    session_date: date
    decision_as_of: datetime
    sessions_to_event: int
    known_notice_sessions: int | None
    schedule: ShadowEvent
    daily: ShadowDailyInput
    daily_fingerprint: str
    temporal_fingerprint: str
    calendar_fingerprint: str
    atr: Decimal | None
    atr_lineage: tuple[ShadowReference, ...]
    benchmark_lineage: tuple[ShadowReference, ...]
    quality: ShadowQuality
    unavailable: tuple[str, ...]

    def __post_init__(self):
        ShadowRecord.__post_init__(self); self.schedule.__post_init__(); self.daily.__post_init__()
        for refs in (self.atr_lineage, self.benchmark_lineage):
            for ref in refs: ref.__post_init__()
            if len({r.record_id for r in refs}) != len(refs):
                raise EarningsHorizonShadowError("SHADOW_DUPLICATE_LINEAGE")
        if (self.schedule.as_of > utc(self.decision_as_of) or self.logical_event_id != self.schedule.logical_event_id
            or self.schedule.state in {ShadowState.CONFLICTED, ShadowState.CANCELLED}
            or self.canonical_instrument_id != self.schedule.canonical_instrument_id
            or self.daily.bar.instrument.instrument_id != self.canonical_instrument_id
            or self.daily.timing.session_date != self.session_date or self.sessions_to_event < 0
            or self.daily_fingerprint != fingerprint(self.daily)
            or ((self.atr is None) != (not self.atr_lineage)) or (self.atr is not None and (not self.atr.is_finite() or self.atr <= 0))):
            raise EarningsHorizonShadowError("SHADOW_SESSION_INVALID")


def _atr(snapshot: AsOfSnapshot | None, history: tuple[ShadowDailyInput, ...], calendar, instrument, at):
    """Verify exact canonical bar-to-analysis inputs; reuse ATR14/Wilder engine."""
    if snapshot is not None and (snapshot.as_of_timestamp != at or snapshot.created_timestamp > at):
        return None, ()
    bars = {}
    for value in history:
        temporal = visible_bar(value, calendar, at)
        if temporal is None or value.bar.instrument.instrument_id != instrument:
            return None, ()
        key = temporal.session_date
        if key in bars:
            return None, ()
        bars[key] = value
    if len(bars) < 15 or len({v.bar.adjustment_status for v in bars.values()}) != 1:
        return None, ()
    # No gaps silently crossed in the supplied ATR window.
    days = sorted(bars)
    if any(calendar.adjacent_trading_session(a, as_of=at, direction=1) != b for a, b in zip(days, days[1:])):
        return None, ()
    try:
        observations = tuple(price_bar_observation(bars[d].bar).with_validation(ValidationResult(ValidationStatus.VALID, at)) for d in days)
    except ValueError:
        return None, ()  # Preserve existing source-selection restrictions.
    if snapshot is None:
        snapshot = AsOfSnapshot("earnings-shadow-atr:" + fingerprint(tuple(bars[d] for d in days))[7:], at, at,
                                "canonical-prospective-visible-daily-only", observations)
    if len(snapshot.observations) != len(bars):
        return None, ()
    inputs = {value.bar.bar_id: value for value in bars.values()}
    for obs in snapshot.observations:
        value = inputs.get(obs.id)
        if (value is None or obs.instrument.id != instrument or not isinstance(obs.payload, Mapping)
            or obs.provenance != price_bar_observation(value.bar).provenance
            or any(Decimal(str(obs.payload.get(name))) != getattr(value.bar, name) for name in ("open", "high", "low", "close"))):
            return None, ()
    # The engine requires a provenance reference, not a persisted/executable
    # strategy. Reuse its established artifact-reference convention.
    result = TechnicalAnalysisEngine().atr(snapshot, instrument_id=instrument,
        strategy_version=StrategyVersionReference("earnings-horizon-prospective-shadow", "v1"), period=14, evaluated_at=at)
    if result.status is not AnalysisStatus.VALID or result.value is None or result.value <= 0:
        return None, ()
    lineage = tuple(sorted((ShadowReference(v.bar.bar_id, fingerprint(v)) for v in bars.values())))
    return Decimal(str(result.value)), lineage + (ShadowReference(result.id, fingerprint(result)),)


def observe_session(*, values: tuple[QualifiedShadowInput, ...], instrument: str, calendar: CanonicalMarketSessionCalendar,
                    daily: ShadowDailyInput, decision_as_of: datetime, history: tuple[ShadowDailyInput, ...] = (),
                    analysis_snapshot: AsOfSnapshot | None = None, benchmarks: tuple[ShadowDailyInput, ...] = ()) -> ShadowSessionObservation | None:
    point = utc(decision_as_of)
    temporal = visible_bar(daily, calendar, point)
    if temporal is None or daily.bar.instrument.instrument_id != instrument or temporal.session_date != point.astimezone(IST).date():
        return None
    session = temporal.session_date
    events = tuple(e for e in reconcile_events(values, as_of=point) if e.canonical_instrument_id == instrument
                   and e.state not in {ShadowState.CONFLICTED, ShadowState.CANCELLED}
                   and e.scheduled_event_date is not None and e.scheduled_event_date >= session)
    if len(events) != 1:
        return None
    event = events[0]
    distance = session_distance(calendar, session, event.scheduled_event_date, as_of=point)
    if distance is None:
        return None
    notice = session_distance(calendar, event.first_observed_at.astimezone(IST).date(), event.scheduled_event_date, as_of=point)
    atr, lineage = _atr(analysis_snapshot, history, calendar, instrument, point)
    if atr is not None and (not any(v == daily for v in history) or max(v.timing.session_date for v in history) != session):
        atr, lineage = None, ()
    refs = []
    for value in benchmarks:
        t = visible_bar(value, calendar, point)
        # No sector membership inference. A separate governed context adapter
        # is needed for sector mappings; these two canonical IDs need no join.
        if t and t.session_date == session and value.bar.instrument.instrument_id in {"NIFTY_50", "NIFTY_500"}:
            refs.append(ShadowReference(value.bar.bar_id, fingerprint(value)))
    if len({r.record_id for r in refs}) != len(refs):
        raise EarningsHorizonShadowError("SHADOW_BENCHMARK_DUPLICATE")
    unavailable = ["SECTOR_CONTEXT_UNAVAILABLE"]
    if atr is None: unavailable.append("ATR_LINEAGE_UNAVAILABLE")
    if not refs: unavailable.append("BENCHMARK_CONTEXT_UNAVAILABLE")
    if notice is None: unavailable.append("KNOWN_NOTICE_SESSION_DISTANCE_UNAVAILABLE")
    return _record(ShadowSessionObservation, logical_event_id=event.logical_event_id, canonical_instrument_id=instrument,
        session_date=session, decision_as_of=point, sessions_to_event=distance, known_notice_sessions=notice,
        schedule=event, daily=daily, daily_fingerprint=fingerprint(daily), temporal_fingerprint=temporal.fingerprint,
        calendar_fingerprint=calendar.fingerprint, atr=atr, atr_lineage=lineage,
        benchmark_lineage=tuple(sorted(refs)), quality=ShadowQuality.PARTIAL, unavailable=tuple(sorted(unavailable)))


@dataclass(frozen=True, slots=True)
class ShadowResultEvidence:
    filing: CorporateFiling
    publication: SourceTimestampEvidence | None = None
    facts: tuple[FinancialFact, ...] = ()

    def __post_init__(self):
        f = self.filing
        object.__setattr__(self, "facts", tuple(sorted(self.facts, key=lambda value: value.fact_id)))
        utc(f.received_at); utc(f.announced_at)
        if self.publication:
            self.publication.__post_init__()
            receipt = self.publication.timestamp_receipt
            if receipt.filing_id != f.filing_id or receipt.canonical_instrument_id != f.instrument.instrument_id:
                raise EarningsHorizonShadowError("SHADOW_RESULT_TIMESTAMP_LINEAGE_INVALID")
            if f.timestamp_evidence is None or any(getattr(receipt, name) != getattr(f.timestamp_evidence, name)
                for name in ("source_family", "source_document_identity", "source_payload_identity", "raw_timestamp_field_path", "raw_timestamp_value")):
                raise EarningsHorizonShadowError("SHADOW_RESULT_RAW_TIMESTAMP_MISMATCH")
        if len({v.fact_id for v in self.facts}) != len(self.facts):
            raise EarningsHorizonShadowError("SHADOW_RESULT_FACT_DUPLICATE")
        for fact in self.facts:
            fact.__post_init__()
            if fact.filing_id != f.filing_id or fact.instrument.instrument_id != f.instrument.instrument_id:
                raise EarningsHorizonShadowError("SHADOW_RESULT_FACT_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowResultLink(ShadowRecord):
    event: ShadowEvent
    as_of: datetime
    state: ResultLinkState
    candidates: tuple[ShadowResultEvidence, ...]
    reasons: tuple[str, ...]

    def __post_init__(self):
        ShadowRecord.__post_init__(self); self.event.__post_init__()
        for value in self.candidates: value.__post_init__()
        if (not isinstance(self.state, ResultLinkState) or self.event.as_of > utc(self.as_of)
            or len({v.filing.filing_id for v in self.candidates}) != len(self.candidates)
            or (self.state is ResultLinkState.LINKED and self.event.state in {ShadowState.CONFLICTED, ShadowState.CANCELLED})
            or (self.state is ResultLinkState.LINKED and (len(self.candidates) != 1 or self.reasons))
            or (self.state is not ResultLinkState.LINKED and not self.reasons)
            or any(v.filing.received_at > self.as_of or v.filing.announced_at > self.as_of
                or v.filing.instrument.instrument_id != self.event.canonical_instrument_id
                or any(f.available_at > self.as_of for f in v.facts) for v in self.candidates)):
            raise EarningsHorizonShadowError("SHADOW_RESULT_LINK_INVALID")


def link_result(event: ShadowEvent, candidates: tuple[ShadowResultEvidence, ...], *, as_of: datetime) -> ShadowResultLink:
    point = utc(as_of)
    event.__post_init__()
    matches = {}
    for value in candidates:
        value.__post_init__()
        f = value.filing
        if f.received_at > point or f.announced_at > point:
            continue
        if (f.instrument.instrument_id != event.canonical_instrument_id or f.filing_type is not FilingType.FINANCIAL_RESULTS
            or f.source_quality is not PrimarySourceQuality.PRIMARY_EXCHANGE or f.board_meeting is None):
            continue
        # Explicit official relation, never nearest date or financial-period guessing.
        if not any(f.board_meeting.related_filing_id == v.receipt.source_filing_identity and f.exchange == v.source_exchange for v in event.schedule_versions):
            continue
        if any(fact.available_at > point for fact in value.facts):
            continue
        if f.filing_id in matches and matches[f.filing_id] != value:
            raise EarningsHorizonShadowError("SHADOW_RESULT_DUPLICATE_CONFLICT")
        matches[f.filing_id] = value
    result = tuple(matches[k] for k in sorted(matches))
    if event.state in {ShadowState.CONFLICTED, ShadowState.CANCELLED}:
        state, reasons = ResultLinkState.UNAVAILABLE, ("SCHEDULE_NOT_OUTCOME_ELIGIBLE",)
    elif len(result) > 1:
        state, reasons = ResultLinkState.AMBIGUOUS, ("EXACT_RESULT_LINK_AMBIGUOUS",)
    elif not result:
        state, reasons = ResultLinkState.PENDING, ("EXPLICIT_OFFICIAL_RESULT_RELATION_REQUIRED",)
    else:
        state, reasons = ResultLinkState.LINKED, ()
    return _record(ShadowResultLink, event=event, as_of=point, state=state, candidates=result, reasons=reasons)


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowOutcome(ShadowRecord):
    observation: ShadowReference
    result_link: ShadowReference
    state: ShadowState
    quality: ShadowQuality
    reaction_session: date | None
    reaction_bar: ShadowReference | None
    signed_gap: Decimal | None
    absolute_gap: Decimal | None
    reaction_return: Decimal | None
    absolute_reaction_return: Decimal | None
    atr_normalized_gap: Decimal | None
    reasons: tuple[str, ...]
    unavailable: tuple[str, ...]

    def __post_init__(self):
        ShadowRecord.__post_init__(self)
        values = (self.signed_gap, self.absolute_gap, self.reaction_return, self.absolute_reaction_return)
        if (not isinstance(self.state, ShadowState) or not isinstance(self.quality, ShadowQuality)
            or (self.state is ShadowState.OUTCOME_READY and (any(v is None for v in values) or self.reaction_bar is None or self.reaction_session is None))
            or (self.state is not ShadowState.OUTCOME_READY and any(v is not None for v in (*values, self.atr_normalized_gap)))
            or any(v is not None and not v.is_finite() for v in (*values, self.atr_normalized_gap))
            or (self.signed_gap is not None and self.absolute_gap != self.signed_gap.copy_abs())
            or (self.reaction_return is not None and self.absolute_reaction_return != self.reaction_return.copy_abs())):
            raise EarningsHorizonShadowError("SHADOW_OUTCOME_INVALID")


def attach_outcome(observation: ShadowSessionObservation, link: ShadowResultLink, *, calendar: CanonicalMarketSessionCalendar,
                   reaction_bars: tuple[ShadowDailyInput, ...], as_of: datetime | None = None) -> ShadowOutcome:
    observation.__post_init__(); link.__post_init__()
    point = utc(as_of) if as_of is not None else link.as_of
    if point < link.as_of:
        raise EarningsHorizonShadowError("SHADOW_OUTCOME_CUTOFF_BEFORE_LINK")
    if observation.logical_event_id != link.event.logical_event_id:
        raise EarningsHorizonShadowError("SHADOW_OUTCOME_EVENT_MISMATCH")
    def incomplete(reason, state=ShadowState.TEMPORAL_OUTCOME_INCOMPLETE):
        return _record(ShadowOutcome, observation=reference(observation), result_link=reference(link), state=state,
            quality=ShadowQuality.TEMPORAL_INCOMPLETE, reaction_session=None, reaction_bar=None,
            signed_gap=None, absolute_gap=None, reaction_return=None, absolute_reaction_return=None,
            atr_normalized_gap=None, reasons=(reason,), unavailable=DEFERRED + ("LAYER1_PRICE_METRICS",))
    if link.state is not ResultLinkState.LINKED:
        return incomplete(link.reasons[0], ShadowState.RESULT_LINK_PENDING if link.state is ResultLinkState.PENDING else ShadowState.CONFLICTED)
    pub = link.candidates[0].publication
    if (pub is None or pub.semantic is not TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME
        or pub.semantic_authority is not SourceTimestampSemanticAuthority.PROVEN
        or pub.semantic_evidence_known_at > point):
        return incomplete("EXACT_PUBLIC_DISSEMINATION_UNPROVEN")
    event = canonical_event_timestamp_from_receipt(pub.timestamp_receipt)
    if event is None or event.occurred_at > point or event.occurred_at <= observation.decision_as_of:
        return incomplete("RESULT_TEMPORAL_ORDER_UNPROVEN")
    alignment = align_event_to_canonical_session(calendar=calendar, canonical_instrument_id=link.event.canonical_instrument_id, trading_venue=Exchange.NSE, event=event)
    if alignment.state is EventSessionState.BEFORE_REGULAR_SESSION:
        reaction = alignment.session_date
    elif alignment.state is EventSessionState.AFTER_REGULAR_SESSION:
        reaction = alignment.next_session
    else:
        return incomplete("REACTION_SESSION_ORDERING_INCOMPLETE")
    if reaction is None or calendar.resolve_trading_day(reaction, as_of=point).state is not TradingDayState.REGULAR_TRADING_DAY:
        return incomplete("REACTION_REGULAR_SESSION_UNPROVEN")
    # Gap is previous close, NOT an arbitrary multi-day pre-event return.
    previous = calendar.adjacent_trading_session(reaction, as_of=event.occurred_at, direction=-1)
    if observation.session_date != previous:
        return incomplete("PREVIOUS_CLOSE_OBSERVATION_REQUIRED")
    selected = {}
    for value in reaction_bars:
        if value.bar.instrument.instrument_id != observation.canonical_instrument_id or value.timing.session_date != reaction:
            continue
        if visible_bar(value, calendar, point) is None:
            return incomplete("REACTION_BAR_PARTIAL_OR_CONFLICTED")
        selected[fingerprint(value)] = value
    if len(selected) != 1:
        return incomplete("REACTION_BAR_MISSING_OR_AMBIGUOUS")
    daily = next(iter(selected.values()))
    if daily.bar.adjustment_status != observation.daily.bar.adjustment_status:
        return incomplete("PRICE_ADJUSTMENT_BASIS_MISMATCH")
    close, opened, final = observation.daily.bar.close, daily.bar.open, daily.bar.close
    if close <= 0 or opened <= 0:
        return incomplete("PRICE_DENOMINATOR_INVALID")
    with localcontext() as ctx:
        ctx.prec = 28
        signed = (opened - close) / close
        ret = (final - opened) / opened
        atr_gap = abs(opened - close) / observation.atr if observation.atr else None
    return _record(ShadowOutcome, observation=reference(observation), result_link=reference(link),
        state=ShadowState.OUTCOME_READY, quality=ShadowQuality.PARTIAL if atr_gap is None else ShadowQuality.ELIGIBLE,
        reaction_session=reaction, reaction_bar=ShadowReference(daily.bar.bar_id, fingerprint(daily)),
        signed_gap=signed, absolute_gap=signed.copy_abs(), reaction_return=ret, absolute_reaction_return=ret.copy_abs(),
        atr_normalized_gap=atr_gap, reasons=(), unavailable=DEFERRED + (("ATR_NORMALIZED_OPENING_GAP",) if atr_gap is None else ()))


def serialize_shadow(value: ShadowRecord) -> str:
    value.__post_init__()
    return canonical_json(_plain(value))
