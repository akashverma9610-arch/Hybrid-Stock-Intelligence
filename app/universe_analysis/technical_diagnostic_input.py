"""Current-descriptive canonical Daily/Weekly input for existing diagnostics.

This module is an intentionally narrow adapter.  It accepts only previously
certified NSE UDiFF Daily reads and already-derived Weekly technical bars and
projects their immutable lineage into the existing ``AsOfSnapshot`` /
``MarketObservation`` shape consumed by the canonical diagnostic evaluators.
It does not calculate an indicator, choose a horizon, persist a result, fetch
a provider, or create a second technical data model.

The UDiFF archive is explicitly current-descriptive evidence.  The adapter
therefore never claims strict historical PIT eligibility.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Iterable

from app.domain.models import (
    AsOfSnapshot,
    DataQuality,
    DerivedObservationMetadata,
    Instrument,
    MarketObservation,
    ObservationKind,
    Provenance,
    ValidationResult,
    ValidationStatus,
)
from app.market_data.models import CanonicalOHLCVBar, Timeframe
from app.market_data.nse_udiff_daily_technical_eligibility import (
    DailyTechnicalPriceContinuityState,
    DailyTechnicalVolumeContinuityState,
)
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffCertifiedDailyTechnicalRead,
    NseUdiffDailyTechnicalReadState,
    NseUdiffDailyTechnicalUseMode,
)
from app.market_data.nse_udiff_weekly_technical_bar import (
    NseUdiffWeeklyTechnicalBar,
    NseUdiffWeeklyTechnicalState,
)


CONTRACT_ID = "canonical-current-descriptive-technical-diagnostic-input"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class TechnicalDiagnosticInputError(ValueError):
    """Stable fail-closed error for malformed canonical technical input."""


class CurrentDescriptiveTechnicalState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class StrictHistoricalPitTechnicalState(StrEnum):
    NOT_READY = "NOT_READY"


class TechnicalDiagnosticReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class TechnicalEvidenceClass(StrEnum):
    PRICE_ONLY = "PRICE_ONLY"
    PRICE_AND_VOLUME = "PRICE_AND_VOLUME"
    BENCHMARK_RELATIVE = "BENCHMARK_RELATIVE"
    SECTOR_RELATIVE = "SECTOR_RELATIVE"
    EVENT_DEPENDENT = "EVENT_DEPENDENT"
    EXECUTION_CONTEXT = "EXECUTION_CONTEXT"
    TECHNICAL_DEPENDENT = "TECHNICAL_DEPENDENT"


class TechnicalDiagnosticBlocker(StrEnum):
    DAILY_CANONICAL_INPUT_UNAVAILABLE = "DAILY_CANONICAL_INPUT_UNAVAILABLE"
    WEEKLY_CANONICAL_INPUT_UNAVAILABLE = "WEEKLY_CANONICAL_INPUT_UNAVAILABLE"
    DAILY_HISTORY_INSUFFICIENT = "DAILY_HISTORY_INSUFFICIENT"
    WEEKLY_HISTORY_INSUFFICIENT = "WEEKLY_HISTORY_INSUFFICIENT"
    PRICE_CONTINUITY_NOT_READY = "PRICE_CONTINUITY_NOT_READY"
    VOLUME_CONTINUITY_NOT_READY = "VOLUME_CONTINUITY_NOT_READY"
    BENCHMARK_HISTORY_NOT_READY = "BENCHMARK_HISTORY_NOT_READY"
    SECTOR_HISTORY_NOT_READY = "SECTOR_HISTORY_NOT_READY"
    PEER_COHORT_NOT_READY = "PEER_COHORT_NOT_READY"
    EVENT_EVIDENCE_NOT_READY = "EVENT_EVIDENCE_NOT_READY"
    NAMED_VWAP_SEMANTICS_UNAVAILABLE = "NAMED_VWAP_SEMANTICS_UNAVAILABLE"
    UPSTREAM_TECHNICAL_RESULT_REQUIRED = "UPSTREAM_TECHNICAL_RESULT_REQUIRED"
    STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE = (
        "STRICT_HISTORICAL_PIT_SOURCE_AVAILABILITY_UNAVAILABLE"
    )


@dataclass(frozen=True, slots=True)
class TechnicalDiagnosticRuleRequirement:
    """Actual evaluator input facts; this is not a horizon applicability policy."""

    rule_id: int
    evidence_class: TechnicalEvidenceClass
    minimum_daily_observations: int | None
    minimum_weekly_observations: int | None
    requires_price_continuity: bool
    requires_volume_continuity: bool
    requires_benchmark: bool
    requires_sector: bool
    requires_peers: bool
    requires_event: bool
    evaluator_implemented: bool = True

    def __post_init__(self) -> None:
        if (
            self.rule_id < 1 or self.rule_id > 61
            or not isinstance(self.evidence_class, TechnicalEvidenceClass)
            or any(value is not None and value < 1 for value in (
                self.minimum_daily_observations, self.minimum_weekly_observations,
            ))
        ):
            raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_REQUIREMENT_INVALID")


@dataclass(frozen=True, slots=True)
class TechnicalDiagnosticRuleReadinessReceipt:
    """Non-scoring per-rule operational input receipt."""

    rule_id: int
    evaluator_implemented: bool
    evidence_class: TechnicalEvidenceClass
    daily_state: TechnicalDiagnosticReadiness
    weekly_state: TechnicalDiagnosticReadiness
    benchmark_state: TechnicalDiagnosticReadiness
    sector_state: TechnicalDiagnosticReadiness
    volume_state: TechnicalDiagnosticReadiness
    event_state: TechnicalDiagnosticReadiness
    current_descriptive_operational: TechnicalDiagnosticReadiness
    strict_historical_pit_operational: StrictHistoricalPitTechnicalState
    blockers: tuple[TechnicalDiagnosticBlocker, ...]
    daily_observation_ids: tuple[str, ...]
    weekly_observation_ids: tuple[str, ...]
    source_policy_id: str
    source_policy_version: str
    source_fingerprint: str

    def __post_init__(self) -> None:
        blockers = tuple(sorted(set(self.blockers), key=lambda item: item.value))
        # Observation IDs retain canonical bar chronology.  Sorting them here
        # would replace that chronology with an arbitrary lexical order.
        daily = tuple(self.daily_observation_ids)
        weekly = tuple(self.weekly_observation_ids)
        if (
            self.rule_id < 1 or self.rule_id > 61
            or not isinstance(self.evidence_class, TechnicalEvidenceClass)
            or any(not isinstance(item, TechnicalDiagnosticReadiness) for item in (
                self.daily_state, self.weekly_state, self.benchmark_state,
                self.sector_state, self.volume_state, self.event_state,
                self.current_descriptive_operational,
            ))
            or self.strict_historical_pit_operational is not StrictHistoricalPitTechnicalState.NOT_READY
            or self.blockers != blockers
            or self.daily_observation_ids != daily
            or self.weekly_observation_ids != weekly
            or len(set(daily)) != len(daily)
            or len(set(weekly)) != len(weekly)
            or any(not _ID.fullmatch(item) for item in (*daily, *weekly))
            or self.source_policy_id != CONTRACT_ID
            or self.source_policy_version != CONTRACT_VERSION
            or not _FP.fullmatch(self.source_fingerprint)
            or (self.current_descriptive_operational is TechnicalDiagnosticReadiness.READY and blockers)
        ):
            raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_READINESS_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalTechnicalDiagnosticInput:
    """Two genuine timeframe snapshots with their certified canonical lineage."""

    canonical_instrument_id: str
    as_of: datetime
    daily_snapshot: AsOfSnapshot | None
    weekly_snapshot: AsOfSnapshot | None
    daily_source_read_fingerprints: tuple[str, ...]
    weekly_source_fingerprints: tuple[str, ...]
    daily_price_continuity_ready: bool
    daily_volume_continuity_ready: bool
    weekly_volume_continuity_ready: bool
    current_descriptive_state: CurrentDescriptiveTechnicalState
    strict_historical_pit_state: StrictHistoricalPitTechnicalState
    source_policy_id: str
    source_policy_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        daily_reads = tuple(sorted(set(self.daily_source_read_fingerprints)))
        weekly = tuple(sorted(set(self.weekly_source_fingerprints)))
        values = _input_values(
            self.canonical_instrument_id, self.as_of, self.daily_snapshot,
            self.weekly_snapshot, daily_reads, weekly,
            self.daily_price_continuity_ready, self.daily_volume_continuity_ready,
            self.weekly_volume_continuity_ready, self.current_descriptive_state,
            self.strict_historical_pit_state, self.source_policy_id,
            self.source_policy_version,
        )
        daily_ids = _snapshot_ids(self.daily_snapshot)
        weekly_ids = _snapshot_ids(self.weekly_snapshot)
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not _aware(self.as_of)
            or self.daily_source_read_fingerprints != daily_reads
            or self.weekly_source_fingerprints != weekly
            or any(not _FP.fullmatch(item) for item in (*daily_reads, *weekly))
            or self.source_policy_id != CONTRACT_ID
            or self.source_policy_version != CONTRACT_VERSION
            or self.strict_historical_pit_state is not StrictHistoricalPitTechnicalState.NOT_READY
            or self.current_descriptive_state is not CurrentDescriptiveTechnicalState.READY
            or self.fingerprint != _fingerprint(values)
            or (self.daily_snapshot is None and self.weekly_snapshot is None)
            or (self.daily_snapshot is None and (daily_reads or self.daily_price_continuity_ready or self.daily_volume_continuity_ready))
            or (self.weekly_snapshot is None and (weekly or self.weekly_volume_continuity_ready))
            or (self.daily_snapshot is not None and (
                not daily_reads or not _valid_snapshot(self.daily_snapshot, self.canonical_instrument_id, self.as_of, "1D")
            ))
            or (self.weekly_snapshot is not None and (
                not weekly or not _valid_snapshot(self.weekly_snapshot, self.canonical_instrument_id, self.as_of, "1W")
            ))
            or set(daily_ids) & set(weekly_ids)
        ):
            raise TechnicalDiagnosticInputError("CANONICAL_TECHNICAL_DIAGNOSTIC_INPUT_INVALID")


def assemble_current_descriptive_technical_input(
    *, canonical_instrument_id: str, as_of: datetime,
    daily_reads: Iterable[NseUdiffCertifiedDailyTechnicalRead],
    weekly_bars: Iterable[NseUdiffWeeklyTechnicalBar],
) -> CanonicalTechnicalDiagnosticInput:
    """Project only certified Daily and derived Weekly evidence into snapshots.

    ``as_of`` is supplied by the caller's canonical evidence cutoff.  The
    function neither obtains current time nor extends an evidence cutoff.
    """
    if not _ID.fullmatch(canonical_instrument_id) or not _aware(as_of):
        raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_INPUT_REQUEST_INVALID")
    cutoff = _utc(as_of)
    reads = tuple(sorted(daily_reads, key=lambda item: (item.request.start_session, item.request.end_session, item.fingerprint)))
    weekly_values = tuple(sorted(weekly_bars, key=lambda item: (item.request.session_plan.week_start, item.weekly_bar_id or "", item.fingerprint)))
    daily_observations, read_fingerprints, daily_price, daily_volume = _daily_observations(
        canonical_instrument_id, cutoff, reads,
    )
    weekly_observations, weekly_fingerprints, weekly_volume = _weekly_observations(
        canonical_instrument_id, cutoff, weekly_values,
    )
    daily_snapshot = _snapshot(canonical_instrument_id, cutoff, "1D", daily_observations, read_fingerprints)
    weekly_snapshot = _snapshot(canonical_instrument_id, cutoff, "1W", weekly_observations, weekly_fingerprints)
    values = (
        canonical_instrument_id, cutoff, daily_snapshot, weekly_snapshot,
        read_fingerprints, weekly_fingerprints, daily_price, daily_volume,
        weekly_volume, CurrentDescriptiveTechnicalState.READY,
        StrictHistoricalPitTechnicalState.NOT_READY, CONTRACT_ID, CONTRACT_VERSION,
    )
    return CanonicalTechnicalDiagnosticInput(*values, _fingerprint(_input_values(*values)))


def technical_diagnostic_rule_requirements() -> tuple[TechnicalDiagnosticRuleRequirement, ...]:
    """The current evaluator matrix, derived from live wrapper configuration.

    It intentionally describes only currently implemented technical and hybrid
    rules.  It does not assign a horizon or introduce a second registry.
    """
    return _RULE_REQUIREMENTS


def technical_diagnostic_readiness(
    input_value: CanonicalTechnicalDiagnosticInput, rule_id: int,
) -> TechnicalDiagnosticRuleReadinessReceipt:
    """Return a precise current-descriptive receipt without evaluating a rule."""
    input_value.__post_init__()
    requirement = next((item for item in _RULE_REQUIREMENTS if item.rule_id == rule_id), None)
    if requirement is None:
        raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_RULE_NOT_TECHNICAL")
    blockers: list[TechnicalDiagnosticBlocker] = []
    daily_count = 0 if input_value.daily_snapshot is None else len(input_value.daily_snapshot.observations)
    weekly_count = 0 if input_value.weekly_snapshot is None else len(input_value.weekly_snapshot.observations)
    daily = _timeframe_state(
        available=input_value.daily_snapshot is not None, count=daily_count,
        minimum=requirement.minimum_daily_observations,
        unavailable=TechnicalDiagnosticBlocker.DAILY_CANONICAL_INPUT_UNAVAILABLE,
        insufficient=TechnicalDiagnosticBlocker.DAILY_HISTORY_INSUFFICIENT, blockers=blockers,
    )
    weekly = _timeframe_state(
        available=input_value.weekly_snapshot is not None, count=weekly_count,
        minimum=requirement.minimum_weekly_observations,
        unavailable=TechnicalDiagnosticBlocker.WEEKLY_CANONICAL_INPUT_UNAVAILABLE,
        insufficient=TechnicalDiagnosticBlocker.WEEKLY_HISTORY_INSUFFICIENT, blockers=blockers,
    )
    if requirement.requires_price_continuity and not input_value.daily_price_continuity_ready:
        blockers.append(TechnicalDiagnosticBlocker.PRICE_CONTINUITY_NOT_READY)
    if requirement.requires_volume_continuity and not input_value.daily_volume_continuity_ready:
        blockers.append(TechnicalDiagnosticBlocker.VOLUME_CONTINUITY_NOT_READY)
    benchmark = _dependency_state(requirement.requires_benchmark, TechnicalDiagnosticBlocker.BENCHMARK_HISTORY_NOT_READY, blockers)
    sector = _dependency_state(requirement.requires_sector, TechnicalDiagnosticBlocker.SECTOR_HISTORY_NOT_READY, blockers)
    if requirement.requires_peers:
        blockers.append(TechnicalDiagnosticBlocker.PEER_COHORT_NOT_READY)
    event = _dependency_state(requirement.requires_event, TechnicalDiagnosticBlocker.EVENT_EVIDENCE_NOT_READY, blockers)
    volume = (
        TechnicalDiagnosticReadiness.NOT_APPLICABLE if not requirement.requires_volume_continuity
        else TechnicalDiagnosticReadiness.READY if input_value.daily_volume_continuity_ready
        else TechnicalDiagnosticReadiness.NOT_READY
    )
    if rule_id == 35:
        blockers.append(TechnicalDiagnosticBlocker.NAMED_VWAP_SEMANTICS_UNAVAILABLE)
    if requirement.evidence_class is TechnicalEvidenceClass.TECHNICAL_DEPENDENT:
        blockers.append(TechnicalDiagnosticBlocker.UPSTREAM_TECHNICAL_RESULT_REQUIRED)
    unique = tuple(sorted(set(blockers), key=lambda item: item.value))
    operational = (
        TechnicalDiagnosticReadiness.READY if not unique
        else TechnicalDiagnosticReadiness.NOT_READY if rule_id == 35
        else _partial_or_not_ready(daily, weekly)
    )
    return TechnicalDiagnosticRuleReadinessReceipt(
        rule_id=rule_id, evaluator_implemented=requirement.evaluator_implemented,
        evidence_class=requirement.evidence_class, daily_state=daily,
        weekly_state=weekly, benchmark_state=benchmark, sector_state=sector,
        volume_state=volume, event_state=event,
        current_descriptive_operational=operational,
        strict_historical_pit_operational=StrictHistoricalPitTechnicalState.NOT_READY,
        blockers=unique,
        daily_observation_ids=() if input_value.daily_snapshot is None else _snapshot_ids(input_value.daily_snapshot),
        weekly_observation_ids=() if input_value.weekly_snapshot is None else _snapshot_ids(input_value.weekly_snapshot),
        source_policy_id=CONTRACT_ID, source_policy_version=CONTRACT_VERSION,
        source_fingerprint=input_value.fingerprint,
    )


def serialize_technical_diagnostic_input(value: CanonicalTechnicalDiagnosticInput) -> str:
    """Stable serialization of every fingerprint input, with no wall-clock field."""
    value.__post_init__()
    return _canonical(_input_values(
        value.canonical_instrument_id, value.as_of, value.daily_snapshot,
        value.weekly_snapshot, value.daily_source_read_fingerprints,
        value.weekly_source_fingerprints, value.daily_price_continuity_ready,
        value.daily_volume_continuity_ready, value.weekly_volume_continuity_ready,
        value.current_descriptive_state, value.strict_historical_pit_state,
        value.source_policy_id, value.source_policy_version,
    ) | {"fingerprint": value.fingerprint})


def _daily_observations(instrument_id, cutoff, reads):
    observations: list[MarketObservation] = []
    fingerprints: list[str] = []
    seen: dict[str, str] = {}
    price_ready = bool(reads)
    volume_ready = bool(reads)
    for read in reads:
        read.__post_init__()
        certification = read.certification
        if (
            read.request.canonical_instrument_id != instrument_id
            or read.request.use_mode is not NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL
            or read.state is not NseUdiffDailyTechnicalReadState.READY
            or certification is None
            or _utc(read.request.evaluation_as_of) > cutoff
        ):
            raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_DAILY_READ_INVALID")
        if observations:
            previous = max(item.provenance.market_timestamp.date() for item in observations)
            if (read.request.start_session - previous).days > 7:
                raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_DAILY_CONTINUITY_GAP")
        fingerprints.append(read.fingerprint)
        price_ready = price_ready and certification.price_continuity is DailyTechnicalPriceContinuityState.PRICE_CONTINUITY_READY
        volume_ready = volume_ready and certification.volume_continuity is DailyTechnicalVolumeContinuityState.VOLUME_CONTINUITY_READY
        for bar in read.bars:
            content = _bar_fingerprint(bar)
            previous = seen.get(bar.bar_id)
            # Replaying an identical read under two windows cannot make an
            # ambiguous Daily lineage look continuous; a differing payload is
            # likewise a conflict rather than a caller-order choice.
            if previous is not None:
                raise TechnicalDiagnosticInputError(
                    "TECHNICAL_DIAGNOSTIC_DAILY_LINEAGE_CONFLICT"
                    if previous != content else "TECHNICAL_DIAGNOSTIC_DAILY_LINEAGE_DUPLICATE"
                )
            seen[bar.bar_id] = content
            observations.append(_observation(bar, cutoff, "1D", read.fingerprint, certification.fingerprint))
    return tuple(sorted(observations, key=lambda item: (item.provenance.market_timestamp, item.id))), tuple(sorted(fingerprints)), price_ready, volume_ready


def _weekly_observations(instrument_id, cutoff, values):
    observations: list[MarketObservation] = []
    fingerprints: list[str] = []
    seen: set[str] = set()
    volume_ready = bool(values)
    previous_week_start = None
    for value in values:
        value.__post_init__()
        technical = value.technical_bar
        if (
            value.request.canonical_instrument_id != instrument_id
            or value.request.use_mode is not NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL
            or value.state is not NseUdiffWeeklyTechnicalState.READY
            or technical is None or value.weekly_bar_id is None
            or value.known_at is None or _utc(value.known_at) > cutoff
            or value.weekly_bar_id in seen
        ):
            raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_WEEKLY_BAR_INVALID")
        if previous_week_start is not None and (value.request.session_plan.week_start - previous_week_start).days != 7:
            raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_WEEKLY_CONTINUITY_GAP")
        previous_week_start = value.request.session_plan.week_start
        seen.add(value.weekly_bar_id)
        fingerprints.append(value.fingerprint)
        volume_ready = volume_ready and technical.receipt.volume_readiness.value == "READY"
        observations.append(_observation(
            technical.market_bar, cutoff, "1W", value.fingerprint,
            technical.fingerprint,
        ))
    return tuple(sorted(observations, key=lambda item: (item.provenance.market_timestamp, item.id))), tuple(sorted(fingerprints)), volume_ready


def _observation(bar: CanonicalOHLCVBar, cutoff: datetime, timeframe: str, source_fingerprint: str, lineage_fingerprint: str) -> MarketObservation:
    if _utc(bar.end_time) > cutoff or _utc(bar.provenance.received_at) > cutoff:
        raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_BAR_AFTER_AS_OF")
    identifier = f"technical-{'daily' if timeframe == '1D' else 'weekly'}:{bar.bar_id}"
    payload = {
        "open": float(bar.open), "high": float(bar.high), "low": float(bar.low),
        "close": float(bar.close), "volume": bar.volume,
        "canonical_bar_id": bar.bar_id, "timeframe": timeframe,
        "source_observation_identity": bar.source_observation_identity,
        "source_fingerprint": source_fingerprint,
        "lineage_fingerprint": lineage_fingerprint,
    }
    instrument = Instrument(bar.instrument.instrument_id, bar.instrument.symbol, bar.instrument.exchange.value, bar.instrument.isin)
    return MarketObservation(
        identifier, instrument, ObservationKind.PRICE_BAR, payload,
        Provenance(
            "canonical_nse_udiff_current_descriptive_technical", bar.bar_id,
            _utc(bar.end_time), _utc(bar.provenance.received_at), DataQuality.HIGH,
            original_record={"canonical_bar_id": bar.bar_id, "timeframe": timeframe, "lineage_fingerprint": lineage_fingerprint},
        ),
        ValidationResult(ValidationStatus.VALID, cutoff),
        DerivedObservationMetadata(
            (bar.bar_id, bar.source_observation_identity),
            "certified_daily_to_diagnostic_snapshot" if timeframe == "1D" else "derived_weekly_to_diagnostic_snapshot",
            {"timeframe": timeframe, "source_fingerprint": source_fingerprint, "lineage_fingerprint": lineage_fingerprint},
            CONTRACT_VERSION, cutoff,
        ),
    )


def _snapshot(instrument_id, cutoff, timeframe, observations, fingerprints):
    if not observations:
        return None
    digest = _fingerprint({"instrument": instrument_id, "as_of": _time(cutoff), "timeframe": timeframe, "sources": list(fingerprints)})
    return AsOfSnapshot(
        f"technical-diagnostic-input:{timeframe}:{digest.removeprefix('sha256:')[:32]}",
        cutoff, cutoff,
        f"{CONTRACT_ID}:{CONTRACT_VERSION};CURRENT_DESCRIPTIVE_TECHNICAL;timeframe={timeframe}",
        observations,
    )


def _valid_snapshot(snapshot, instrument_id, cutoff, timeframe):
    if _utc(snapshot.as_of_timestamp) != cutoff or _utc(snapshot.created_timestamp) != cutoff or f"timeframe={timeframe}" not in snapshot.inclusion_policy or not snapshot.observations:
        return False
    return all(
        item.instrument.id == instrument_id
        and item.kind is ObservationKind.PRICE_BAR
        and item.validation is not None and item.validation.status is ValidationStatus.VALID
        and item.payload.get("timeframe") == timeframe
        and item.provenance.source == "canonical_nse_udiff_current_descriptive_technical"
        and _utc(item.provenance.market_timestamp) <= cutoff
        and _utc(item.provenance.retrieved_timestamp) <= cutoff
        for item in snapshot.observations
    )


def _snapshot_ids(value):
    return () if value is None else tuple(item.id for item in value.observations)


def _timeframe_state(*, available, count, minimum, unavailable, insufficient, blockers):
    if minimum is None:
        return TechnicalDiagnosticReadiness.NOT_APPLICABLE
    if not available:
        blockers.append(unavailable)
        return TechnicalDiagnosticReadiness.NOT_READY
    if count < minimum:
        blockers.append(insufficient)
        return TechnicalDiagnosticReadiness.PARTIAL
    return TechnicalDiagnosticReadiness.READY


def _dependency_state(required, blocker, blockers):
    if not required:
        return TechnicalDiagnosticReadiness.NOT_APPLICABLE
    blockers.append(blocker)
    return TechnicalDiagnosticReadiness.NOT_READY


def _partial_or_not_ready(daily, weekly):
    return TechnicalDiagnosticReadiness.PARTIAL if TechnicalDiagnosticReadiness.READY in {daily, weekly} else TechnicalDiagnosticReadiness.NOT_READY


def _input_values(instrument, as_of, daily, weekly, daily_fingerprints, weekly_fingerprints, daily_price, daily_volume, weekly_volume, current, strict, policy_id, policy_version):
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "instrument": instrument,
        "as_of": _time(as_of),
        "daily": None if daily is None else {"id": daily.id, "observations": list(_snapshot_ids(daily))},
        "weekly": None if weekly is None else {"id": weekly.id, "observations": list(_snapshot_ids(weekly))},
        "daily_read_fingerprints": list(daily_fingerprints),
        "weekly_bar_fingerprints": list(weekly_fingerprints),
        "daily_price_continuity_ready": daily_price,
        "daily_volume_continuity_ready": daily_volume,
        "weekly_volume_continuity_ready": weekly_volume,
        "current_descriptive_state": current.value,
        "strict_historical_pit_state": strict.value,
        "source_policy": {"id": policy_id, "version": policy_version},
    }


def _bar_fingerprint(value: CanonicalOHLCVBar) -> str:
    return _fingerprint({
        "id": value.bar_id, "instrument": value.instrument.instrument_id,
        "start": _time(value.start_time), "end": _time(value.end_time),
        "open": str(value.open), "high": str(value.high), "low": str(value.low),
        "close": str(value.close), "volume": value.volume,
        "source": value.source_observation_identity,
    })


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise TechnicalDiagnosticInputError("TECHNICAL_DIAGNOSTIC_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


_RULE_REQUIREMENTS = (
    TechnicalDiagnosticRuleRequirement(1, TechnicalEvidenceClass.BENCHMARK_RELATIVE, None, None, False, False, True, False, False, False),
    TechnicalDiagnosticRuleRequirement(2, TechnicalEvidenceClass.SECTOR_RELATIVE, None, None, False, False, True, True, False, False),
    TechnicalDiagnosticRuleRequirement(3, TechnicalEvidenceClass.SECTOR_RELATIVE, None, None, False, False, True, True, False, False),
    TechnicalDiagnosticRuleRequirement(4, TechnicalEvidenceClass.PRICE_ONLY, 6, 6, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(5, TechnicalEvidenceClass.PRICE_ONLY, None, 5, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(6, TechnicalEvidenceClass.BENCHMARK_RELATIVE, 4, None, True, False, True, True, True, False),
    TechnicalDiagnosticRuleRequirement(7, TechnicalEvidenceClass.PRICE_AND_VOLUME, 3, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(8, TechnicalEvidenceClass.PRICE_AND_VOLUME, 2, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(9, TechnicalEvidenceClass.PRICE_AND_VOLUME, 3, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(10, TechnicalEvidenceClass.PRICE_ONLY, 6, None, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(11, TechnicalEvidenceClass.PRICE_AND_VOLUME, 4, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(12, TechnicalEvidenceClass.PRICE_ONLY, 5, None, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(13, TechnicalEvidenceClass.PRICE_ONLY, 5, None, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(14, TechnicalEvidenceClass.PRICE_ONLY, 5, 5, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(29, TechnicalEvidenceClass.PRICE_ONLY, 1, None, True, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(31, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(32, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(34, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(35, TechnicalEvidenceClass.PRICE_AND_VOLUME, 1, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(36, TechnicalEvidenceClass.PRICE_AND_VOLUME, 4, None, True, True, False, False, False, False),
    *(TechnicalDiagnosticRuleRequirement(rule_id, TechnicalEvidenceClass.EXECUTION_CONTEXT, 5, None, True, False, False, False, False, False) for rule_id in range(37, 47)),
    *(TechnicalDiagnosticRuleRequirement(rule_id, TechnicalEvidenceClass.PRICE_AND_VOLUME, 3, None, True, True, False, False, False, False) for rule_id in range(50, 55)),
    TechnicalDiagnosticRuleRequirement(55, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(56, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(57, TechnicalEvidenceClass.EVENT_DEPENDENT, 1, None, True, False, False, False, False, True),
    TechnicalDiagnosticRuleRequirement(58, TechnicalEvidenceClass.PRICE_AND_VOLUME, 3, None, True, True, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(59, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(60, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
    TechnicalDiagnosticRuleRequirement(61, TechnicalEvidenceClass.TECHNICAL_DEPENDENT, None, None, False, False, False, False, False, False),
)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CanonicalTechnicalDiagnosticInput",
    "CurrentDescriptiveTechnicalState", "StrictHistoricalPitTechnicalState",
    "TechnicalDiagnosticBlocker", "TechnicalDiagnosticInputError",
    "TechnicalDiagnosticReadiness", "TechnicalDiagnosticRuleReadinessReceipt",
    "TechnicalDiagnosticRuleRequirement", "TechnicalEvidenceClass",
    "assemble_current_descriptive_technical_input",
    "serialize_technical_diagnostic_input", "technical_diagnostic_readiness",
    "technical_diagnostic_rule_requirements",
)
