"""Provider-neutral technical reads over persisted canonical prospective 15m bars.

This boundary reads only the immutable canonical 15m receipts produced by the
existing derivation contract.  It does not contact a provider, obtain the
current time, calculate an indicator, interpret a Rule, persist a result, or
create a signal.  A strict prospective read has an explicit ``known_at``
cutoff; a current-descriptive read intentionally has no historical-PIT claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Protocol

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
from app.market_data.models import Timeframe
from app.market_data.prospective_fifteen_minute_bar import (
    CanonicalProspectiveFifteenMinuteReceipt,
    ProspectiveFifteenMinuteConflict,
    ProspectiveFifteenMinuteReason,
    ProspectiveFifteenMinuteState,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily


CONTRACT_ID = "canonical-prospective-fifteen-minute-technical-reader"
CONTRACT_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_QUERY_RECEIPTS = 100


class CanonicalFifteenMinuteTechnicalReaderError(ValueError):
    """Stable, fail-closed error for malformed reader input or storage facts."""


class CanonicalFifteenMinuteTechnicalReadMode(StrEnum):
    AS_OF_PROSPECTIVE_PIT = "AS_OF_PROSPECTIVE_PIT"
    CURRENT_DESCRIPTIVE = "CURRENT_DESCRIPTIVE"


class CanonicalFifteenMinuteTechnicalReadState(StrEnum):
    READY = "READY"
    INSUFFICIENT = "INSUFFICIENT"


class CanonicalFifteenMinuteTechnicalReadReason(StrEnum):
    CANONICAL_SECURITY_NO_STORED_RECEIPTS = "CANONICAL_SECURITY_NO_STORED_RECEIPTS"
    ELIGIBLE_LOOKBACK_INSUFFICIENT = "ELIGIBLE_LOOKBACK_INSUFFICIENT"
    RECEIPT_INCOMPLETE = "RECEIPT_INCOMPLETE"
    RECEIPT_CONFLICTED = "RECEIPT_CONFLICTED"
    RECEIPT_NO_TRADE_NOT_MATERIALIZED = "RECEIPT_NO_TRADE_NOT_MATERIALIZED"
    CONFLICT_ARTIFACT_PRESENT = "CONFLICT_ARTIFACT_PRESENT"
    DUPLICATE_CANONICAL_INTERVAL = "DUPLICATE_CANONICAL_INTERVAL"
    RECEIPT_KNOWN_AFTER_AS_OF = "RECEIPT_KNOWN_AFTER_AS_OF"
    RECEIPT_INVALID = "RECEIPT_INVALID"


class CanonicalFifteenMinuteContinuityState(StrEnum):
    """Descriptive evidence only; no consumer continuity rule is selected here."""

    NO_OBSERVED_INTERRUPTION = "NO_OBSERVED_INTERRUPTION"
    NO_TRADE_UNMATERIALIZED = "NO_TRADE_UNMATERIALIZED"
    OBSERVATION_GAP_OR_INCOMPLETE = "OBSERVATION_GAP_OR_INCOMPLETE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    CONTINUITY_POLICY_UNSET = "CONTINUITY_POLICY_UNSET"


class CanonicalFifteenMinuteInputState(StrEnum):
    CANONICAL_15M_INPUT_AVAILABLE = "CANONICAL_15M_INPUT_AVAILABLE"
    CANONICAL_15M_INPUT_INSUFFICIENT = "CANONICAL_15M_INPUT_INSUFFICIENT"


class CanonicalFifteenMinuteTechnicalReaderRepository(Protocol):
    """The indexed, exact-security slice of the immutable snapshot store."""

    def list_canonical_prospective_fifteen_minute_snapshots(
        self, canonical_security_id: str, *, known_at_lte: str | None, limit: int,
    ) -> tuple[CoreApiSnapshot, ...]: ...

    def list_canonical_prospective_fifteen_minute_conflicts(
        self, receipt_ids: tuple[str, ...], *, detected_at_lte: str | None,
    ) -> tuple[CoreApiSnapshot, ...]: ...


@dataclass(frozen=True, slots=True)
class CanonicalFifteenMinuteTechnicalReadRequest:
    canonical_security_id: str
    count: int
    mode: CanonicalFifteenMinuteTechnicalReadMode
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        strict = self.mode is CanonicalFifteenMinuteTechnicalReadMode.AS_OF_PROSPECTIVE_PIT
        if (
            not _identifier(self.canonical_security_id)
            or not isinstance(self.count, int)
            or not 1 <= self.count <= _MAX_QUERY_RECEIPTS
            or not isinstance(self.mode, CanonicalFifteenMinuteTechnicalReadMode)
            or (strict and not _aware(self.as_of))
            or (not strict and self.as_of is not None)
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_READ_REQUEST_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalFifteenMinuteTechnicalBar:
    """A provider-neutral eligible technical bar, never a raw provider packet."""

    canonical_security_id: str
    timeframe: Timeframe
    session_id: str
    interval_start: datetime
    interval_end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    known_at: datetime
    bar_fingerprint: str
    derivation_policy_id: str
    derivation_policy_version: str
    derivation_policy_fingerprint: str
    source_lineage_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        values = _bar_values(self)
        if (
            not _identifier(self.canonical_security_id)
            or self.timeframe is not Timeframe.FIFTEEN_MINUTES
            or not _identifier(self.session_id)
            or not _aware(self.interval_start) or not _aware(self.interval_end) or not _aware(self.known_at)
            or _utc(self.interval_end) - _utc(self.interval_start) != timedelta(minutes=15)
            or _utc(self.known_at) < _utc(self.interval_end)
            or any(value <= 0 for value in (self.open, self.high, self.low, self.close))
            or self.low > min(self.open, self.close) or self.high < max(self.open, self.close)
            or self.volume <= 0
            or not all(_fingerprint(value) for value in (
                self.bar_fingerprint, self.derivation_policy_fingerprint, self.source_lineage_fingerprint,
            ))
            or not _identifier(self.derivation_policy_id) or not _identifier(self.derivation_policy_version)
            or self.fingerprint != _digest(values)
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_BAR_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalFifteenMinuteTechnicalRead:
    request: CanonicalFifteenMinuteTechnicalReadRequest
    state: CanonicalFifteenMinuteTechnicalReadState
    bars: tuple[CanonicalFifteenMinuteTechnicalBar, ...]
    eligible_bar_count: int
    scanned_receipt_count: int
    continuity_states: tuple[CanonicalFifteenMinuteContinuityState, ...]
    reasons: tuple[CanonicalFifteenMinuteTechnicalReadReason, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, CanonicalFifteenMinuteTechnicalReadRequest):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_READ_RESULT_INVALID")
        bars = tuple(sorted(self.bars, key=lambda value: (value.interval_start, value.interval_end, value.bar_fingerprint)))
        continuity = tuple(sorted(set(self.continuity_states), key=lambda value: value.value))
        reasons = tuple(sorted(set(self.reasons), key=lambda value: value.value))
        values = _read_values(self, bars, continuity, reasons)
        ready = self.state is CanonicalFifteenMinuteTechnicalReadState.READY
        if (
            not isinstance(self.state, CanonicalFifteenMinuteTechnicalReadState)
            or self.bars != bars
            or self.continuity_states != continuity
            or self.reasons != reasons
            or self.eligible_bar_count < len(bars)
            or self.scanned_receipt_count < self.eligible_bar_count
            or self.scanned_receipt_count > _MAX_QUERY_RECEIPTS
            or len({(value.interval_start, value.interval_end) for value in bars}) != len(bars)
            or any(value.canonical_security_id != self.request.canonical_security_id for value in bars)
            or (self.request.as_of is not None and any(value.known_at > _utc(self.request.as_of) for value in bars))
            or (ready and len(bars) != self.request.count)
            or (not ready and not reasons)
            or self.fingerprint != _digest(values)
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_READ_RESULT_INVALID")


@dataclass(frozen=True, slots=True)
class CanonicalFifteenMinuteTechnicalInput:
    """Minimal future-consumer adapter: canonical bars plus explicit readiness."""

    read: CanonicalFifteenMinuteTechnicalRead
    snapshot: AsOfSnapshot | None
    state: CanonicalFifteenMinuteInputState
    fingerprint: str

    def __post_init__(self) -> None:
        if not isinstance(self.read, CanonicalFifteenMinuteTechnicalRead):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_INPUT_INVALID")
        values = _input_values(self)
        expected = (
            CanonicalFifteenMinuteInputState.CANONICAL_15M_INPUT_AVAILABLE
            if self.read.state is CanonicalFifteenMinuteTechnicalReadState.READY and self.snapshot is not None
            else CanonicalFifteenMinuteInputState.CANONICAL_15M_INPUT_INSUFFICIENT
        )
        if (
            self.state is not expected
            or (self.snapshot is not None and not _valid_input_snapshot(self.snapshot, self.read))
            or (self.snapshot is None and self.read.state is CanonicalFifteenMinuteTechnicalReadState.READY)
            or self.fingerprint != _digest(values)
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_INPUT_INVALID")


def read_canonical_prospective_fifteen_minute_bars(
    *, repository: CanonicalFifteenMinuteTechnicalReaderRepository,
    request: CanonicalFifteenMinuteTechnicalReadRequest,
) -> CanonicalFifteenMinuteTechnicalRead:
    """Read a bounded exact-security lookback without a provider or wall clock.

    The repository query is security-indexed.  A current-descriptive read is
    deliberately not historical PIT; an as-of read filters only receipts HSI
    knew at or before the caller-supplied cutoff.
    """
    request.__post_init__()
    cutoff = None if request.as_of is None else _utc(request.as_of)
    try:
        snapshots = repository.list_canonical_prospective_fifteen_minute_snapshots(
            request.canonical_security_id,
            known_at_lte=None if cutoff is None else cutoff.isoformat(),
            limit=_MAX_QUERY_RECEIPTS,
        )
    except AttributeError as error:
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_INDEXED_REPOSITORY_REQUIRED") from error
    if len(snapshots) > _MAX_QUERY_RECEIPTS:
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_REPOSITORY_BOUND_VIOLATED")
    receipts, reasons, continuity = _validated_receipts(snapshots, request, cutoff)
    receipt_ids = tuple(sorted({value.receipt_id for value in receipts}))
    try:
        conflicts = repository.list_canonical_prospective_fifteen_minute_conflicts(
            receipt_ids, detected_at_lte=None if cutoff is None else cutoff.isoformat(),
        )
    except AttributeError as error:
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_INDEXED_REPOSITORY_REQUIRED") from error
    conflict_receipt_ids = _conflicted_receipt_ids(conflicts, receipt_ids)
    selected: list[CanonicalFifteenMinuteTechnicalBar] = []
    duplicate_ids = {
        receipt_id for receipt_id in receipt_ids
        if sum(value.receipt_id == receipt_id for value in receipts) != 1
    }
    if duplicate_ids:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.DUPLICATE_CANONICAL_INTERVAL)
        continuity.add(CanonicalFifteenMinuteContinuityState.EVIDENCE_CONFLICTED)
    for receipt in receipts:
        if receipt.receipt_id in duplicate_ids:
            continue
        if receipt.receipt_id in conflict_receipt_ids:
            reasons.add(CanonicalFifteenMinuteTechnicalReadReason.CONFLICT_ARTIFACT_PRESENT)
            continuity.add(CanonicalFifteenMinuteContinuityState.EVIDENCE_CONFLICTED)
            continue
        bar = _eligible_bar(receipt, request.canonical_security_id, cutoff)
        if bar is None:
            _classify_ineligible_receipt(receipt, reasons, continuity)
        else:
            selected.append(bar)
    eligible = tuple(sorted(selected, key=lambda value: (value.interval_start, value.interval_end, value.bar_fingerprint)))
    chosen = eligible[-request.count:]
    if not snapshots:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.CANONICAL_SECURITY_NO_STORED_RECEIPTS)
    if len(eligible) < request.count:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.ELIGIBLE_LOOKBACK_INSUFFICIENT)
    continuity.add(CanonicalFifteenMinuteContinuityState.CONTINUITY_POLICY_UNSET)
    state = CanonicalFifteenMinuteTechnicalReadState.READY if len(chosen) == request.count else CanonicalFifteenMinuteTechnicalReadState.INSUFFICIENT
    values = dict(
        request=request, state=state, bars=chosen, eligible_bar_count=len(eligible),
        scanned_receipt_count=len(snapshots), continuity_states=tuple(sorted(continuity, key=lambda value: value.value)),
        reasons=tuple(sorted(reasons, key=lambda value: value.value)),
    )
    return CanonicalFifteenMinuteTechnicalRead(**values, fingerprint=_digest(_read_values_from(values)))


def canonical_fifteen_minute_technical_input(
    read: CanonicalFifteenMinuteTechnicalRead, *, instrument: Instrument,
) -> CanonicalFifteenMinuteTechnicalInput:
    """Adapt a strict canonical 15m read to the existing generic snapshot shape.

    It is deliberately not wired into ``CanonicalTechnicalDiagnosticInput`` or
    any Rule.  That preserves the frozen daily/weekly diagnostic semantics
    while giving a future consumer an ordinary ``AsOfSnapshot`` when the
    caller has supplied an exact canonical instrument identity.
    """
    read.__post_init__()
    if (
        not isinstance(instrument, Instrument)
        or instrument.id != read.request.canonical_security_id
        or read.request.mode is not CanonicalFifteenMinuteTechnicalReadMode.AS_OF_PROSPECTIVE_PIT
        or read.request.as_of is None
    ):
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_INPUT_IDENTITY_OR_MODE_INVALID")
    snapshot = _input_snapshot(read, instrument) if read.state is CanonicalFifteenMinuteTechnicalReadState.READY else None
    state = (
        CanonicalFifteenMinuteInputState.CANONICAL_15M_INPUT_AVAILABLE
        if snapshot is not None
        else CanonicalFifteenMinuteInputState.CANONICAL_15M_INPUT_INSUFFICIENT
    )
    values = dict(read=read, snapshot=snapshot, state=state)
    return CanonicalFifteenMinuteTechnicalInput(**values, fingerprint=_digest(_input_values_from(values)))


def serialize_canonical_fifteen_minute_technical_read(value: CanonicalFifteenMinuteTechnicalRead) -> str:
    value.__post_init__()
    return _canonical(_read_values(value, value.bars, value.continuity_states, value.reasons) | {"fingerprint": value.fingerprint})


def _validated_receipts(
    snapshots: tuple[CoreApiSnapshot, ...], request: CanonicalFifteenMinuteTechnicalReadRequest, cutoff: datetime | None,
) -> tuple[tuple[CanonicalProspectiveFifteenMinuteReceipt, ...], set[CanonicalFifteenMinuteTechnicalReadReason], set[CanonicalFifteenMinuteContinuityState]]:
    receipts: list[CanonicalProspectiveFifteenMinuteReceipt] = []
    reasons: set[CanonicalFifteenMinuteTechnicalReadReason] = set()
    continuity: set[CanonicalFifteenMinuteContinuityState] = set()
    for snapshot in snapshots:
        receipt = snapshot.payload
        if (
            snapshot.family is not CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_BAR
            or snapshot.schema_version != "v1"
            or snapshot.record_type != "canonical-prospective-fifteen-minute-receipt-v1"
            or not isinstance(receipt, CanonicalProspectiveFifteenMinuteReceipt)
        ):
            reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INVALID)
            continue
        try:
            receipt.__post_init__()
        except ValueError:
            reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INVALID)
            continue
        if (
            snapshot.fingerprint != receipt.fingerprint
            or snapshot.snapshot_id != f"canonical-prospective-15m:{receipt.receipt_id}"
            or receipt.canonical_security_id != request.canonical_security_id
            or receipt.partition.period.session_dates != (receipt.partition.session.session_date,)
            or _utc(receipt.partition.interval_end) - _utc(receipt.partition.interval_start) != timedelta(minutes=15)
        ):
            reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INVALID)
            continue
        if cutoff is not None and _utc(receipt.known_at) > cutoff:
            reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_KNOWN_AFTER_AS_OF)
            continue
        receipts.append(receipt)
    return tuple(receipts), reasons, continuity


def _conflicted_receipt_ids(snapshots: tuple[CoreApiSnapshot, ...], permitted: tuple[str, ...]) -> set[str]:
    result: set[str] = set()
    for snapshot in snapshots:
        conflict = snapshot.payload
        if (
            snapshot.family is not CoreApiSnapshotFamily.PROSPECTIVE_CANONICAL_FIFTEEN_MINUTE_CONFLICT
            or snapshot.schema_version != "v1"
            or snapshot.record_type != "canonical-prospective-fifteen-minute-conflict-v1"
            or not isinstance(conflict, ProspectiveFifteenMinuteConflict)
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_CONFLICT_ARTIFACT_INVALID")
        conflict.__post_init__()
        if (
            snapshot.fingerprint != conflict.fingerprint
            or snapshot.snapshot_id != f"canonical-prospective-15m-conflict:{conflict.conflict_id}"
            or conflict.receipt_id not in permitted
        ):
            raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_CONFLICT_ARTIFACT_INVALID")
        result.add(conflict.receipt_id)
    return result


def _eligible_bar(
    receipt: CanonicalProspectiveFifteenMinuteReceipt, canonical_security_id: str, cutoff: datetime | None,
) -> CanonicalFifteenMinuteTechnicalBar | None:
    if (
        receipt.state is not ProspectiveFifteenMinuteState.CLOSED
        or receipt.reasons
        or receipt.bar is None
        or receipt.canonical_security_id != canonical_security_id
        or receipt.bar.canonical_security_id != canonical_security_id
        or receipt.bar.known_at != receipt.known_at
        or (cutoff is not None and _utc(receipt.known_at) > cutoff)
    ):
        return None
    bar = receipt.bar
    values = dict(
        canonical_security_id=bar.canonical_security_id, timeframe=Timeframe.FIFTEEN_MINUTES,
        session_id=bar.partition.session.session_id, interval_start=_utc(bar.partition.interval_start),
        interval_end=_utc(bar.partition.interval_end), open=bar.open, high=bar.high, low=bar.low,
        close=bar.close, volume=bar.volume, known_at=_utc(bar.known_at), bar_fingerprint=bar.fingerprint,
        derivation_policy_id=bar.derivation_policy_id, derivation_policy_version=bar.derivation_policy_version,
        derivation_policy_fingerprint=bar.derivation_policy_fingerprint,
        source_lineage_fingerprint=bar.source_lineage_fingerprint,
    )
    return CanonicalFifteenMinuteTechnicalBar(**values, fingerprint=_digest(_bar_values_from(values)))


def _classify_ineligible_receipt(
    receipt: CanonicalProspectiveFifteenMinuteReceipt,
    reasons: set[CanonicalFifteenMinuteTechnicalReadReason],
    continuity: set[CanonicalFifteenMinuteContinuityState],
) -> None:
    if receipt.state is ProspectiveFifteenMinuteState.NO_TRADE_OBSERVED:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_NO_TRADE_NOT_MATERIALIZED)
        continuity.add(CanonicalFifteenMinuteContinuityState.NO_TRADE_UNMATERIALIZED)
    elif receipt.state is ProspectiveFifteenMinuteState.EVIDENCE_CONFLICTED:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_CONFLICTED)
        continuity.add(CanonicalFifteenMinuteContinuityState.EVIDENCE_CONFLICTED)
    else:
        reasons.add(CanonicalFifteenMinuteTechnicalReadReason.RECEIPT_INCOMPLETE)
        continuity.add(CanonicalFifteenMinuteContinuityState.OBSERVATION_GAP_OR_INCOMPLETE)
        if ProspectiveFifteenMinuteReason.PROVIDER_GAP_OR_UNOBSERVED in receipt.reasons:
            continuity.add(CanonicalFifteenMinuteContinuityState.OBSERVATION_GAP_OR_INCOMPLETE)


def _bar_values(value: CanonicalFifteenMinuteTechnicalBar) -> dict[str, object]:
    return _bar_values_from({
        "canonical_security_id": value.canonical_security_id, "timeframe": value.timeframe,
        "session_id": value.session_id, "interval_start": value.interval_start, "interval_end": value.interval_end,
        "open": value.open, "high": value.high, "low": value.low, "close": value.close, "volume": value.volume,
        "known_at": value.known_at, "bar_fingerprint": value.bar_fingerprint,
        "derivation_policy_id": value.derivation_policy_id, "derivation_policy_version": value.derivation_policy_version,
        "derivation_policy_fingerprint": value.derivation_policy_fingerprint,
        "source_lineage_fingerprint": value.source_lineage_fingerprint,
    })


def _bar_values_from(value: dict[str, object]) -> dict[str, object]:
    return {
        "canonical_security_id": value["canonical_security_id"], "timeframe": _enum(value["timeframe"]),
        "session_id": value["session_id"], "interval_start": _time(value["interval_start"]),
        "interval_end": _time(value["interval_end"]), "open": _decimal(value["open"]),
        "high": _decimal(value["high"]), "low": _decimal(value["low"]), "close": _decimal(value["close"]),
        "volume": value["volume"], "known_at": _time(value["known_at"]),
        "bar_fingerprint": value["bar_fingerprint"],
        "derivation_policy": {"id": value["derivation_policy_id"], "version": value["derivation_policy_version"], "fingerprint": value["derivation_policy_fingerprint"]},
        "source_lineage_fingerprint": value["source_lineage_fingerprint"],
    }


def _read_values(
    value: CanonicalFifteenMinuteTechnicalRead, bars: tuple[CanonicalFifteenMinuteTechnicalBar, ...],
    continuity: tuple[CanonicalFifteenMinuteContinuityState, ...],
    reasons: tuple[CanonicalFifteenMinuteTechnicalReadReason, ...],
) -> dict[str, object]:
    return _read_values_from({
        "request": value.request, "state": value.state, "bars": bars,
        "eligible_bar_count": value.eligible_bar_count, "scanned_receipt_count": value.scanned_receipt_count,
        "continuity_states": continuity, "reasons": reasons,
    })


def _read_values_from(value: dict[str, object]) -> dict[str, object]:
    request = value["request"]
    assert isinstance(request, CanonicalFifteenMinuteTechnicalReadRequest)
    bars = value["bars"]
    assert isinstance(bars, tuple)
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "request": {"canonical_security_id": request.canonical_security_id, "count": request.count,
                    "mode": request.mode.value, "as_of": _time(request.as_of)},
        "state": _enum(value["state"]), "bars": [_bar_values(item) for item in bars],
        "eligible_bar_count": value["eligible_bar_count"], "scanned_receipt_count": value["scanned_receipt_count"],
        "continuity_states": [_enum(item) for item in value["continuity_states"]],
        "reasons": [_enum(item) for item in value["reasons"]],
    }


def _input_values(value: CanonicalFifteenMinuteTechnicalInput) -> dict[str, object]:
    return _input_values_from({"read": value.read, "snapshot": value.snapshot, "state": value.state})


def _input_values_from(value: dict[str, object]) -> dict[str, object]:
    read = value["read"]
    assert isinstance(read, CanonicalFifteenMinuteTechnicalRead)
    snapshot = value["snapshot"]
    assert snapshot is None or isinstance(snapshot, AsOfSnapshot)
    return {"contract": CONTRACT_ID, "version": CONTRACT_VERSION, "read_fingerprint": read.fingerprint, "snapshot_id": None if snapshot is None else snapshot.id, "state": _enum(value["state"])}


def _input_snapshot(read: CanonicalFifteenMinuteTechnicalRead, instrument: Instrument) -> AsOfSnapshot:
    assert read.request.as_of is not None
    cutoff = _utc(read.request.as_of)
    observations = tuple(_input_observation(bar, instrument, cutoff) for bar in read.bars)
    snapshot_id = "canonical-15m-technical-input:" + _digest({"read": read.fingerprint, "instrument": instrument.id}).removeprefix("sha256:")[:32]
    return AsOfSnapshot(
        snapshot_id, cutoff, cutoff,
        f"{CONTRACT_ID}:{CONTRACT_VERSION};AS_OF_PROSPECTIVE_PIT;timeframe=15m",
        observations,
    )


def _input_observation(value: CanonicalFifteenMinuteTechnicalBar, instrument: Instrument, cutoff: datetime) -> MarketObservation:
    if value.known_at > cutoff or value.interval_end > cutoff:
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_INPUT_AFTER_AS_OF")
    payload = {
        "open": value.open, "high": value.high, "low": value.low, "close": value.close, "volume": value.volume,
        "canonical_bar_fingerprint": value.bar_fingerprint, "timeframe": value.timeframe.value,
        "derivation_policy_fingerprint": value.derivation_policy_fingerprint,
        "source_lineage_fingerprint": value.source_lineage_fingerprint,
    }
    return MarketObservation(
        f"canonical-15m-technical-observation:{value.bar_fingerprint.removeprefix('sha256:')[:32]}",
        instrument, ObservationKind.PRICE_BAR, payload,
        Provenance("canonical_prospective_fifteen_minute_technical", value.bar_fingerprint, value.interval_end, value.known_at, DataQuality.HIGH, original_record={"timeframe": "15m", "bar_fingerprint": value.bar_fingerprint}),
        ValidationResult(ValidationStatus.VALID, cutoff),
        DerivedObservationMetadata((value.bar_fingerprint, value.derivation_policy_fingerprint, value.source_lineage_fingerprint), "canonical_prospective_fifteen_minute_technical_input", {"timeframe": "15m"}, CONTRACT_VERSION, cutoff),
    )


def _valid_input_snapshot(value: AsOfSnapshot, read: CanonicalFifteenMinuteTechnicalRead) -> bool:
    if read.request.as_of is None or _utc(value.as_of_timestamp) != _utc(read.request.as_of) or _utc(value.created_timestamp) != _utc(read.request.as_of) or "timeframe=15m" not in value.inclusion_policy or len(value.observations) != len(read.bars):
        return False
    return all(
        observation.kind is ObservationKind.PRICE_BAR
        and observation.instrument.id == read.request.canonical_security_id
        and observation.validation is not None and observation.validation.status is ValidationStatus.VALID
        and observation.payload.get("timeframe") == "15m"
        and observation.provenance.source == "canonical_prospective_fifteen_minute_technical"
        and _utc(observation.provenance.market_timestamp) <= _utc(read.request.as_of)
        and _utc(observation.provenance.retrieved_timestamp) <= _utc(read.request.as_of)
        for observation in value.observations
    )


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: object) -> str:
    return "sha256:" + sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identifier(value: object) -> bool:
    return isinstance(value, str) and bool(_IDENTIFIER.fullmatch(value))


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and bool(_FINGERPRINT.fullmatch(value))


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise CanonicalFifteenMinuteTechnicalReaderError("CANONICAL_15M_TECHNICAL_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


def _time(value: object) -> str | None:
    return _utc(value).isoformat() if isinstance(value, datetime) else None


def _decimal(value: object) -> str | None:
    return str(value) if isinstance(value, Decimal) else None


def _enum(value: object) -> str:
    return value.value if isinstance(value, StrEnum) else str(value)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CanonicalFifteenMinuteContinuityState",
    "CanonicalFifteenMinuteInputState", "CanonicalFifteenMinuteTechnicalBar",
    "CanonicalFifteenMinuteTechnicalInput", "CanonicalFifteenMinuteTechnicalRead",
    "CanonicalFifteenMinuteTechnicalReadMode", "CanonicalFifteenMinuteTechnicalReadReason",
    "CanonicalFifteenMinuteTechnicalReadRequest", "CanonicalFifteenMinuteTechnicalReadState",
    "CanonicalFifteenMinuteTechnicalReaderError", "CanonicalFifteenMinuteTechnicalReaderRepository",
    "canonical_fifteen_minute_technical_input", "read_canonical_prospective_fifteen_minute_bars",
    "serialize_canonical_fifteen_minute_technical_read",
)
