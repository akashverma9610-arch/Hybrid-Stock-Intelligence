"""Immutable, source-injected provenance for official filing timestamps.

This module deliberately resolves *timezone semantics*, not a market reaction
or public-known-time assertion.  It has no clock, transport, persistence,
price, portfolio, broker, order, API, or UI dependency.  A source adapter must
retain its exact timestamp text and field path; a rule can attach a timezone
only when its first-party scope and PIT visibility are explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.filings.models import CorporateFiling, FilingTimestampSourceEvidence
from app.historical.canonical_market_session_event_time import (
    CanonicalEventTimestamp,
    EventTimestampState,
    make_canonical_event_timestamp,
)


CONTRACT_ID = "canonical-filing-timestamp-timezone-provenance"
CONTRACT_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_OFFSET_TIMESTAMP = re.compile(r".*(?:Z|[+-]\d{2}:\d{2})\Z")


class FilingTimestampTimezoneError(ValueError):
    """Stable fail-closed error for invalid timezone provenance."""


class TimestampProvenanceState(StrEnum):
    EXPLICIT_OFFSET = "EXPLICIT_OFFSET"
    EXPLICIT_TIMEZONE_IDENTIFIER = "EXPLICIT_TIMEZONE_IDENTIFIER"
    SOURCE_SCHEMA_DOCUMENTED = "SOURCE_SCHEMA_DOCUMENTED"
    SOURCE_SYSTEM_DOCUMENTED = "SOURCE_SYSTEM_DOCUMENTED"
    SOURCE_NATIVE_EPOCH = "SOURCE_NATIVE_EPOCH"
    DERIVED_FROM_APPROVED_SOURCE_RULE = "DERIVED_FROM_APPROVED_SOURCE_RULE"
    TIMEZONE_UNRESOLVED = "TIMEZONE_UNRESOLVED"
    TIMEZONE_EVIDENCE_CONFLICTED = "TIMEZONE_EVIDENCE_CONFLICTED"


class TimestampResolutionState(StrEnum):
    EXACT_FILING_TIMESTAMP_KNOWN = "EXACT_FILING_TIMESTAMP_KNOWN"
    FILING_DATE_KNOWN = "FILING_DATE_KNOWN"
    EVENT_TIME_OF_DAY_UNAVAILABLE = "EVENT_TIME_OF_DAY_UNAVAILABLE"
    EVENT_TIMESTAMP_UNAVAILABLE = "EVENT_TIMESTAMP_UNAVAILABLE"
    TIMEZONE_UNRESOLVED = "TIMEZONE_UNRESOLVED"
    TIMEZONE_EVIDENCE_CONFLICTED = "TIMEZONE_EVIDENCE_CONFLICTED"


class RawTimestampRetentionState(StrEnum):
    RETAINED = "RETAINED"
    NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD = "NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD"
    SOURCE_TIMESTAMP_ABSENT = "SOURCE_TIMESTAMP_ABSENT"


class EventKnownTimeStatus(StrEnum):
    """Describes the source role without pretending it is public dissemination."""

    SOURCE_TIMESTAMP_ROLE_UNVERIFIED = "SOURCE_TIMESTAMP_ROLE_UNVERIFIED"
    SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED = "SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED"
    SYSTEM_FIRST_OBSERVED_NOT_SOURCE_PUBLICATION = "SYSTEM_FIRST_OBSERVED_NOT_SOURCE_PUBLICATION"


class SourceTimestampEncoding(StrEnum):
    TEXT = "TEXT"
    UNIX_SECONDS = "UNIX_SECONDS"
    UNIX_MILLISECONDS = "UNIX_MILLISECONDS"
    DATE_ONLY = "DATE_ONLY"
    MISSING = "MISSING"


@dataclass(frozen=True, slots=True)
class SourceTimezoneRule:
    """An exact field-level rule backed by first-party source semantics."""

    rule_id: str
    source_family: str
    raw_timestamp_field_path: str
    timezone_id: str
    provenance_state: TimestampProvenanceState
    source_evidence_identity: str
    source_evidence_fingerprint: str
    evidence_known_at: datetime
    effective_from: date
    effective_to: date | None
    historical_continuity_proven: bool
    epoch_encoding: SourceTimestampEncoding | None = None
    fingerprint: str = ""

    def __post_init__(self) -> None:
        expected = _fingerprint(_rule_values(_without(self, "fingerprint")))
        allowed = {
            TimestampProvenanceState.SOURCE_SCHEMA_DOCUMENTED,
            TimestampProvenanceState.SOURCE_SYSTEM_DOCUMENTED,
            TimestampProvenanceState.SOURCE_NATIVE_EPOCH,
            TimestampProvenanceState.DERIVED_FROM_APPROVED_SOURCE_RULE,
        }
        epoch = self.provenance_state is TimestampProvenanceState.SOURCE_NATIVE_EPOCH
        if (
            not _identifier(self.rule_id)
            or not _nonempty(self.source_family)
            or not _nonempty(self.raw_timestamp_field_path)
            or not _timezone(self.timezone_id)
            or self.provenance_state not in allowed
            or not _nonempty(self.source_evidence_identity)
            or not _fingerprint_value(self.source_evidence_fingerprint)
            or not _aware(self.evidence_known_at)
            or not _date(self.effective_from)
            or (self.effective_to is not None and (not _date(self.effective_to) or self.effective_to < self.effective_from))
            or not isinstance(self.historical_continuity_proven, bool)
            or (epoch and self.epoch_encoding not in {SourceTimestampEncoding.UNIX_SECONDS, SourceTimestampEncoding.UNIX_MILLISECONDS})
            or (not epoch and self.epoch_encoding is not None)
            or self.fingerprint != expected
        ):
            raise FilingTimestampTimezoneError("FILING_TIMEZONE_RULE_INVALID")


@dataclass(frozen=True, slots=True)
class FilingTimestampInput:
    """Raw source evidence and a source-specific parse, before timezone resolution."""

    filing_id: str
    canonical_instrument_id: str
    source_family: str
    source_document_identity: str
    source_payload_identity: str
    source_payload_fingerprint: str
    raw_timestamp_field_path: str | None
    raw_timestamp_value: str | None
    parsed_local_timestamp: datetime | None
    filing_date: date | None
    declared_timezone_id: str | None
    encoding: SourceTimestampEncoding
    event_known_time_status: EventKnownTimeStatus

    def __post_init__(self) -> None:
        raw_retained = self.raw_timestamp_field_path is not None or self.raw_timestamp_value is not None
        exact = self.encoding is SourceTimestampEncoding.TEXT
        date_only = self.encoding is SourceTimestampEncoding.DATE_ONLY
        epoch = self.encoding in {SourceTimestampEncoding.UNIX_SECONDS, SourceTimestampEncoding.UNIX_MILLISECONDS}
        if (
            not _identifier(self.filing_id)
            or not _identifier(self.canonical_instrument_id)
            or not _nonempty(self.source_family)
            or not _nonempty(self.source_document_identity)
            or not _nonempty(self.source_payload_identity)
            or not _fingerprint_value(self.source_payload_fingerprint)
            or (raw_retained and (not _nonempty(self.raw_timestamp_field_path) or not _nonempty(self.raw_timestamp_value)))
            or (self.raw_timestamp_value is not None and not isinstance(self.raw_timestamp_value, str))
            or (self.parsed_local_timestamp is not None and not isinstance(self.parsed_local_timestamp, datetime))
            or (self.filing_date is not None and not _date(self.filing_date))
            or (self.declared_timezone_id is not None and not _timezone(self.declared_timezone_id))
            or not isinstance(self.encoding, SourceTimestampEncoding)
            or not isinstance(self.event_known_time_status, EventKnownTimeStatus)
            or (exact and (not _nonempty(self.raw_timestamp_value) or self.parsed_local_timestamp is None or self.filing_date is not None))
            or (date_only and (not _nonempty(self.raw_timestamp_value) or self.parsed_local_timestamp is not None or self.filing_date is None))
            or (epoch and (not _nonempty(self.raw_timestamp_value) or self.parsed_local_timestamp is not None or self.filing_date is not None))
            or (self.encoding is SourceTimestampEncoding.MISSING and (raw_retained or self.parsed_local_timestamp is not None or self.filing_date is not None))
        ):
            raise FilingTimestampTimezoneError("FILING_TIMESTAMP_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class FilingTimestampProvenanceReceipt:
    """One immutable interpretation receipt; it never substitutes a source time."""

    receipt_id: str
    filing_id: str
    canonical_instrument_id: str
    source_family: str
    source_document_identity: str
    source_payload_identity: str
    source_payload_fingerprint: str
    raw_timestamp_field_path: str | None
    raw_timestamp_value: str | None
    raw_retention_state: RawTimestampRetentionState
    parsed_local_timestamp: datetime | None
    original_timezone_id: str | None
    timezone_provenance_state: TimestampProvenanceState
    timezone_evidence_ids: tuple[str, ...]
    timezone_evidence_fingerprints: tuple[str, ...]
    normalized_utc_timestamp: datetime | None
    resolution_state: TimestampResolutionState
    event_known_time_status: EventKnownTimeStatus
    reason_codes: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        resolved = self.resolution_state is TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN
        unavailable = self.resolution_state in {
            TimestampResolutionState.FILING_DATE_KNOWN,
            TimestampResolutionState.EVENT_TIME_OF_DAY_UNAVAILABLE,
            TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE,
            TimestampResolutionState.TIMEZONE_UNRESOLVED,
            TimestampResolutionState.TIMEZONE_EVIDENCE_CONFLICTED,
        }
        no_time = self.resolution_state is TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE
        expected_id = _receipt_id(
            self.filing_id, self.source_family, self.source_document_identity,
            self.raw_timestamp_field_path, self.source_payload_fingerprint,
        )
        if (
            self.receipt_id != expected_id
            or not _identifier(self.filing_id)
            or not _identifier(self.canonical_instrument_id)
            or not _nonempty(self.source_family)
            or not _nonempty(self.source_document_identity)
            or not _nonempty(self.source_payload_identity)
            or not _fingerprint_value(self.source_payload_fingerprint)
            or not isinstance(self.raw_retention_state, RawTimestampRetentionState)
            or not isinstance(self.timezone_provenance_state, TimestampProvenanceState)
            or not isinstance(self.resolution_state, TimestampResolutionState)
            or not isinstance(self.event_known_time_status, EventKnownTimeStatus)
            or self.timezone_evidence_ids != tuple(sorted(set(self.timezone_evidence_ids)))
            or len(self.timezone_evidence_ids) != len(self.timezone_evidence_fingerprints)
            or any(not _identifier(value) for value in self.timezone_evidence_ids)
            or any(not _fingerprint_value(value) for value in self.timezone_evidence_fingerprints)
            or self.reason_codes != tuple(sorted(set(self.reason_codes)))
            or not self.reason_codes
            or any(not _identifier(value) for value in self.reason_codes)
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or (self.raw_retention_state is RawTimestampRetentionState.RETAINED and (not _nonempty(self.raw_timestamp_field_path) or not _nonempty(self.raw_timestamp_value)))
            or (self.raw_retention_state is not RawTimestampRetentionState.RETAINED and (self.raw_timestamp_field_path is not None or self.raw_timestamp_value is not None))
            or (resolved and (not _aware(self.parsed_local_timestamp) or not _aware(self.normalized_utc_timestamp) or not _timezone_or_offset(self.original_timezone_id)))
            or (resolved and self.normalized_utc_timestamp != self.parsed_local_timestamp.astimezone(UTC))
            or (resolved and self.timezone_provenance_state in {TimestampProvenanceState.TIMEZONE_UNRESOLVED, TimestampProvenanceState.TIMEZONE_EVIDENCE_CONFLICTED})
            or (unavailable and self.normalized_utc_timestamp is not None)
            or (no_time and self.parsed_local_timestamp is not None)
            or (self.resolution_state is TimestampResolutionState.TIMEZONE_UNRESOLVED and self.timezone_provenance_state is not TimestampProvenanceState.TIMEZONE_UNRESOLVED)
            or (self.resolution_state is TimestampResolutionState.TIMEZONE_EVIDENCE_CONFLICTED and self.timezone_provenance_state is not TimestampProvenanceState.TIMEZONE_EVIDENCE_CONFLICTED)
            or self.fingerprint != _fingerprint(_receipt_values(_without(self, "fingerprint")))
        ):
            raise FilingTimestampTimezoneError("FILING_TIMESTAMP_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class FilingTimestampAuditRecord:
    receipt: FilingTimestampProvenanceReceipt
    coverage_year: int

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, FilingTimestampProvenanceReceipt) or not isinstance(self.coverage_year, int) or not 2000 <= self.coverage_year <= 2100:
            raise FilingTimestampTimezoneError("FILING_TIMESTAMP_AUDIT_RECORD_INVALID")


@dataclass(frozen=True, slots=True)
class FilingTimestampAuditBucket:
    key: str
    total: int
    resolution_counts: tuple[tuple[TimestampResolutionState, int], ...]

    def __post_init__(self) -> None:
        if (
            not _nonempty(self.key)
            or not isinstance(self.total, int)
            or self.total < 0
            or self.resolution_counts != tuple(sorted(self.resolution_counts, key=lambda item: item[0].value))
            or any(not isinstance(state, TimestampResolutionState) or not isinstance(count, int) or count < 0 for state, count in self.resolution_counts)
            or sum(count for _state, count in self.resolution_counts) != self.total
        ):
            raise FilingTimestampTimezoneError("FILING_TIMESTAMP_AUDIT_BUCKET_INVALID")


@dataclass(frozen=True, slots=True)
class FilingTimestampAudit:
    total: int
    resolution_counts: tuple[tuple[TimestampResolutionState, int], ...]
    provenance_counts: tuple[tuple[TimestampProvenanceState, int], ...]
    source_family: tuple[FilingTimestampAuditBucket, ...]
    coverage_year: tuple[FilingTimestampAuditBucket, ...]
    instrument: tuple[FilingTimestampAuditBucket, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.total, int)
            or self.total < 0
            or _state_counts_invalid(self.resolution_counts, TimestampResolutionState, self.total)
            or _state_counts_invalid(self.provenance_counts, TimestampProvenanceState, self.total)
            or self.source_family != tuple(sorted(self.source_family, key=lambda item: item.key))
            or self.coverage_year != tuple(sorted(self.coverage_year, key=lambda item: item.key))
            or self.instrument != tuple(sorted(self.instrument, key=lambda item: item.key))
            or self.fingerprint != _fingerprint(_audit_values(_without(self, "fingerprint")))
        ):
            raise FilingTimestampTimezoneError("FILING_TIMESTAMP_AUDIT_INVALID")


def make_source_timezone_rule(*, rule_id: str, source_family: str, raw_timestamp_field_path: str,
                              timezone_id: str, provenance_state: TimestampProvenanceState,
                              source_evidence_identity: str, source_evidence_fingerprint: str,
                              evidence_known_at: datetime, effective_from: date,
                              effective_to: date | None = None,
                              historical_continuity_proven: bool = False,
                              epoch_encoding: SourceTimestampEncoding | None = None) -> SourceTimezoneRule:
    values = dict(rule_id=rule_id, source_family=source_family, raw_timestamp_field_path=raw_timestamp_field_path,
                  timezone_id=timezone_id, provenance_state=provenance_state,
                  source_evidence_identity=source_evidence_identity, source_evidence_fingerprint=source_evidence_fingerprint,
                  evidence_known_at=_utc(evidence_known_at), effective_from=effective_from, effective_to=effective_to,
                  historical_continuity_proven=historical_continuity_proven, epoch_encoding=epoch_encoding)
    return SourceTimezoneRule(**values, fingerprint=_fingerprint(_rule_values(values)))


def make_filing_timestamp_input(*, filing_id: str, canonical_instrument_id: str, source_family: str,
                                source_document_identity: str, source_payload_identity: str,
                                source_payload_fingerprint: str, raw_timestamp_field_path: str | None,
                                raw_timestamp_value: str | None, parsed_local_timestamp: datetime | None,
                                filing_date: date | None, declared_timezone_id: str | None,
                                encoding: SourceTimestampEncoding,
                                event_known_time_status: EventKnownTimeStatus) -> FilingTimestampInput:
    return FilingTimestampInput(filing_id, canonical_instrument_id, source_family, source_document_identity,
                                source_payload_identity, source_payload_fingerprint, raw_timestamp_field_path,
                                raw_timestamp_value, parsed_local_timestamp, filing_date, declared_timezone_id,
                                encoding, event_known_time_status)


def resolve_filing_timestamp(value: FilingTimestampInput, *, rules: Iterable[SourceTimezoneRule] = (),
                             as_of: datetime) -> FilingTimestampProvenanceReceipt:
    """Resolve a filing time only from exact raw evidence and visible exact rules."""
    if not isinstance(value, FilingTimestampInput) or not _aware(as_of):
        raise FilingTimestampTimezoneError("FILING_TIMESTAMP_RESOLUTION_INPUT_INVALID")
    candidates = _matching_rules(value, rules, as_of)
    if value.encoding is SourceTimestampEncoding.MISSING:
        return _receipt(value, raw_state=RawTimestampRetentionState.SOURCE_TIMESTAMP_ABSENT,
                        parsed=None, original_zone=None, provenance=TimestampProvenanceState.TIMEZONE_UNRESOLVED,
                        evidence=(), normalized=None, resolution=TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE,
                        reasons=("SOURCE_TIMESTAMP_ABSENT",))
    if value.encoding is SourceTimestampEncoding.DATE_ONLY:
        return _receipt(value, raw_state=RawTimestampRetentionState.RETAINED,
                        parsed=None, original_zone=None, provenance=TimestampProvenanceState.TIMEZONE_UNRESOLVED,
                        evidence=(), normalized=None, resolution=TimestampResolutionState.FILING_DATE_KNOWN,
                        reasons=("FILING_DATE_KNOWN_EXACT_TIME_UNAVAILABLE",))
    if value.encoding in {SourceTimestampEncoding.UNIX_SECONDS, SourceTimestampEncoding.UNIX_MILLISECONDS}:
        return _resolve_epoch(value, candidates)
    return _resolve_text(value, candidates)


def receipt_from_corporate_filing(filing: CorporateFiling, *, rules: Iterable[SourceTimezoneRule] = (),
                                  as_of: datetime) -> FilingTimestampProvenanceReceipt:
    """Replay a stored filing without treating legacy normalized time as raw evidence."""
    if not isinstance(filing, CorporateFiling):
        raise FilingTimestampTimezoneError("CANONICAL_FILING_REQUIRED")
    evidence = filing.timestamp_evidence
    source_fingerprint = _fingerprint({"filing_id": filing.filing_id, "source_reference": filing.source_reference,
                                       "document_reference": filing.document_reference, "warnings": filing.warnings})
    if evidence is not None:
        parsed = _parse_known_bse_or_iso_text(evidence.raw_timestamp_value)
        value = make_filing_timestamp_input(
            filing_id=filing.filing_id, canonical_instrument_id=filing.instrument.instrument_id,
            source_family=evidence.source_family, source_document_identity=evidence.source_document_identity,
            source_payload_identity=evidence.source_payload_identity, source_payload_fingerprint=source_fingerprint,
            raw_timestamp_field_path=evidence.raw_timestamp_field_path, raw_timestamp_value=evidence.raw_timestamp_value,
            parsed_local_timestamp=parsed, filing_date=None, declared_timezone_id=None,
            encoding=SourceTimestampEncoding.TEXT, event_known_time_status=EventKnownTimeStatus.SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED,
        )
        return resolve_filing_timestamp(value, rules=rules, as_of=as_of)
    if "SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN" in filing.warnings:
        return _legacy_receipt(filing, source_fingerprint, TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE,
                               "SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN", EventKnownTimeStatus.SYSTEM_FIRST_OBSERVED_NOT_SOURCE_PUBLICATION)
    return _legacy_receipt(filing, source_fingerprint, TimestampResolutionState.TIMEZONE_UNRESOLVED,
                           "RAW_TIMESTAMP_EVIDENCE_NOT_RETAINED", EventKnownTimeStatus.SOURCE_TIMESTAMP_ROLE_UNVERIFIED)


def canonical_event_timestamp_from_receipt(value: FilingTimestampProvenanceReceipt) -> CanonicalEventTimestamp | None:
    """Adapt only an exact resolved instant to the existing event-time contract."""
    if not isinstance(value, FilingTimestampProvenanceReceipt):
        raise FilingTimestampTimezoneError("FILING_TIMESTAMP_RECEIPT_REQUIRED")
    if value.resolution_state is not TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN:
        return None
    assert value.normalized_utc_timestamp is not None and value.original_timezone_id is not None
    return make_canonical_event_timestamp(
        event_id=value.filing_id, occurred_at=value.normalized_utc_timestamp,
        timezone_id="UTC", state=EventTimestampState.EXACT_TIMEZONE_AWARE,
        source_id=value.receipt_id, source_fingerprint=value.fingerprint,
        original_timestamp=value.raw_timestamp_value, original_timezone=value.original_timezone_id,
    )


def audit_filing_timestamp_receipts(records: Iterable[FilingTimestampAuditRecord]) -> FilingTimestampAudit:
    values = tuple(records)
    if any(not isinstance(value, FilingTimestampAuditRecord) for value in values):
        raise FilingTimestampTimezoneError("FILING_TIMESTAMP_AUDIT_RECORD_REQUIRED")
    resolution = _enum_counts((value.receipt.resolution_state for value in values), TimestampResolutionState)
    provenance = _enum_counts((value.receipt.timezone_provenance_state for value in values), TimestampProvenanceState)
    source = _buckets(values, lambda value: value.receipt.source_family)
    year = _buckets(values, lambda value: str(value.coverage_year))
    instrument = _buckets(values, lambda value: value.receipt.canonical_instrument_id)
    data = dict(total=len(values), resolution_counts=resolution, provenance_counts=provenance,
                source_family=source, coverage_year=year, instrument=instrument)
    return FilingTimestampAudit(**data, fingerprint=_fingerprint(_audit_values(data)))


def serialize_filing_timestamp_receipt(value: FilingTimestampProvenanceReceipt) -> str:
    value.__post_init__()
    return json.dumps(_receipt_values(_without(value, "fingerprint")) | {"fingerprint": value.fingerprint},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _resolve_text(value: FilingTimestampInput, candidates: tuple[SourceTimezoneRule, ...]) -> FilingTimestampProvenanceReceipt:
    assert value.parsed_local_timestamp is not None
    raw_explicit = _raw_explicit_offset(value.raw_timestamp_value or "")
    parsed = value.parsed_local_timestamp
    if raw_explicit is not None:
        if not _aware(parsed) or parsed.astimezone(UTC) != raw_explicit.astimezone(UTC):
            raise FilingTimestampTimezoneError("RAW_OFFSET_PARSE_CONFLICT")
        zones = {candidate.timezone_id for candidate in candidates}
        if zones and any(not _timestamp_matches_zone(parsed, zone) for zone in zones):
            return _conflicted_receipt(value, parsed, candidates, "RAW_OFFSET_SOURCE_RULE_CONFLICT")
        return _resolved_receipt(value, parsed, _offset_label(parsed), TimestampProvenanceState.EXPLICIT_OFFSET, (), "RAW_EXPLICIT_OFFSET")
    if _aware(parsed):
        raise FilingTimestampTimezoneError("AWARE_TIMESTAMP_REQUIRES_RAW_OFFSET")
    if value.declared_timezone_id is not None:
        zones = {candidate.timezone_id for candidate in candidates}
        if zones and zones != {value.declared_timezone_id}:
            return _conflicted_receipt(value, parsed, candidates, "DECLARED_TIMEZONE_SOURCE_RULE_CONFLICT")
        resolved = parsed.replace(tzinfo=ZoneInfo(value.declared_timezone_id))
        return _resolved_receipt(value, resolved, value.declared_timezone_id,
                                 TimestampProvenanceState.EXPLICIT_TIMEZONE_IDENTIFIER, (), "RAW_EXPLICIT_TIMEZONE_IDENTIFIER")
    return _resolve_with_rules(value, parsed, candidates)


def _resolve_epoch(value: FilingTimestampInput, candidates: tuple[SourceTimezoneRule, ...]) -> FilingTimestampProvenanceReceipt:
    if len(candidates) != 1 or candidates[0].provenance_state is not TimestampProvenanceState.SOURCE_NATIVE_EPOCH:
        return _unresolved_receipt(value, None, candidates, "SOURCE_NATIVE_EPOCH_SEMANTICS_UNAVAILABLE")
    rule = candidates[0]
    if rule.epoch_encoding is not value.encoding:
        return _conflicted_receipt(value, None, candidates, "SOURCE_NATIVE_EPOCH_ENCODING_CONFLICT")
    try:
        magnitude = int(value.raw_timestamp_value or "")
    except ValueError as error:
        raise FilingTimestampTimezoneError("SOURCE_NATIVE_EPOCH_MALFORMED") from error
    divisor = 1 if value.encoding is SourceTimestampEncoding.UNIX_SECONDS else 1000
    parsed = datetime.fromtimestamp(magnitude / divisor, UTC)
    return _resolved_receipt(value, parsed, "UTC", rule.provenance_state, (rule,), "SOURCE_NATIVE_EPOCH_DOCUMENTED")


def _resolve_with_rules(value: FilingTimestampInput, parsed: datetime, candidates: tuple[SourceTimezoneRule, ...]) -> FilingTimestampProvenanceReceipt:
    if not candidates:
        return _unresolved_receipt(value, parsed, (), "SOURCE_TIMEZONE_SEMANTICS_UNAVAILABLE")
    zones = {candidate.timezone_id for candidate in candidates}
    if len(candidates) != 1 or len(zones) != 1:
        return _conflicted_receipt(value, parsed, candidates, "SOURCE_TIMEZONE_RULE_AMBIGUOUS")
    rule = candidates[0]
    resolved = parsed.replace(tzinfo=ZoneInfo(rule.timezone_id))
    return _resolved_receipt(value, resolved, rule.timezone_id, rule.provenance_state, (rule,), "SOURCE_TIMEZONE_RULE_APPLIED")


def _matching_rules(value: FilingTimestampInput, rules: Iterable[SourceTimezoneRule], as_of: datetime) -> tuple[SourceTimezoneRule, ...]:
    rules_tuple = tuple(rules)
    if any(not isinstance(rule, SourceTimezoneRule) for rule in rules_tuple):
        raise FilingTimestampTimezoneError("SOURCE_TIMEZONE_RULE_REQUIRED")
    by_id: dict[str, set[str]] = {}
    for rule in rules_tuple:
        by_id.setdefault(rule.rule_id, set()).add(rule.fingerprint)
    if any(len(fingerprints) > 1 for fingerprints in by_id.values()):
        raise FilingTimestampTimezoneError("SOURCE_TIMEZONE_RULE_IDENTITY_CONFLICT")
    raw_date = value.parsed_local_timestamp.date() if value.parsed_local_timestamp is not None else value.filing_date
    output = []
    for rule in rules_tuple:
        if rule.source_family != value.source_family or rule.raw_timestamp_field_path != value.raw_timestamp_field_path:
            continue
        if rule.evidence_known_at > as_of or raw_date is None:
            continue
        within_effective_range = rule.effective_from <= raw_date and (rule.effective_to is None or raw_date <= rule.effective_to)
        if within_effective_range or (raw_date < rule.effective_from and rule.historical_continuity_proven):
            output.append(rule)
    # Exact duplicate injection must not manufacture ambiguity. A repeated
    # rule identity with divergent fingerprints remains as competing evidence
    # and therefore fails closed later; this is never resolved by input order.
    unique = {(item.rule_id, item.fingerprint): item for item in output}
    return tuple(sorted(unique.values(), key=lambda item: (item.rule_id, item.fingerprint)))


def _legacy_receipt(filing: CorporateFiling, source_fingerprint: str, resolution: TimestampResolutionState,
                    reason: str, event_known_status: EventKnownTimeStatus) -> FilingTimestampProvenanceReceipt:
    input_value = make_filing_timestamp_input(
        filing_id=filing.filing_id, canonical_instrument_id=filing.instrument.instrument_id,
        source_family="BSE_OFFICIAL_LEGACY_CANONICAL" if filing.source == "BSE_OFFICIAL" else filing.source,
        source_document_identity=filing.document_reference or filing.source_reference or filing.filing_id,
        source_payload_identity=filing.source_reference or filing.document_reference or filing.filing_id,
        source_payload_fingerprint=source_fingerprint, raw_timestamp_field_path=None, raw_timestamp_value=None,
        parsed_local_timestamp=None, filing_date=None, declared_timezone_id=None,
        encoding=SourceTimestampEncoding.MISSING, event_known_time_status=event_known_status,
    )
    retention = RawTimestampRetentionState.NOT_RETAINED_IN_LEGACY_CANONICAL_RECORD
    if resolution is TimestampResolutionState.EVENT_TIMESTAMP_UNAVAILABLE:
        return _receipt(input_value, raw_state=retention, parsed=None, original_zone=None,
                        provenance=TimestampProvenanceState.TIMEZONE_UNRESOLVED, evidence=(), normalized=None,
                        resolution=resolution, reasons=(reason,))
    return _receipt(input_value, raw_state=retention, parsed=None, original_zone=None,
                    provenance=TimestampProvenanceState.TIMEZONE_UNRESOLVED, evidence=(), normalized=None,
                    resolution=resolution, reasons=(reason,))


def _resolved_receipt(value: FilingTimestampInput, parsed: datetime, timezone_id: str,
                      provenance: TimestampProvenanceState, evidence: tuple[SourceTimezoneRule, ...], reason: str) -> FilingTimestampProvenanceReceipt:
    return _receipt(value, raw_state=RawTimestampRetentionState.RETAINED, parsed=parsed,
                    original_zone=timezone_id, provenance=provenance, evidence=evidence,
                    normalized=parsed.astimezone(UTC), resolution=TimestampResolutionState.EXACT_FILING_TIMESTAMP_KNOWN,
                    reasons=(reason,))


def _unresolved_receipt(value: FilingTimestampInput, parsed: datetime | None,
                        evidence: tuple[SourceTimezoneRule, ...], reason: str) -> FilingTimestampProvenanceReceipt:
    return _receipt(value, raw_state=RawTimestampRetentionState.RETAINED, parsed=parsed,
                    original_zone=None, provenance=TimestampProvenanceState.TIMEZONE_UNRESOLVED,
                    evidence=evidence, normalized=None, resolution=TimestampResolutionState.TIMEZONE_UNRESOLVED,
                    reasons=(reason,))


def _conflicted_receipt(value: FilingTimestampInput, parsed: datetime | None,
                        evidence: tuple[SourceTimezoneRule, ...], reason: str) -> FilingTimestampProvenanceReceipt:
    return _receipt(value, raw_state=RawTimestampRetentionState.RETAINED, parsed=parsed,
                    original_zone=None, provenance=TimestampProvenanceState.TIMEZONE_EVIDENCE_CONFLICTED,
                    evidence=evidence, normalized=None, resolution=TimestampResolutionState.TIMEZONE_EVIDENCE_CONFLICTED,
                    reasons=(reason,))


def _receipt(value: FilingTimestampInput, *, raw_state: RawTimestampRetentionState,
             parsed: datetime | None, original_zone: str | None, provenance: TimestampProvenanceState,
             evidence: tuple[SourceTimezoneRule, ...], normalized: datetime | None,
             resolution: TimestampResolutionState, reasons: tuple[str, ...]) -> FilingTimestampProvenanceReceipt:
    evidence = tuple(sorted(evidence, key=lambda item: item.rule_id))
    ids = tuple(item.rule_id for item in evidence)
    fingerprints = tuple(item.fingerprint for item in evidence)
    data = dict(
        receipt_id=_receipt_id(value.filing_id, value.source_family, value.source_document_identity,
                               value.raw_timestamp_field_path, value.source_payload_fingerprint),
        filing_id=value.filing_id, canonical_instrument_id=value.canonical_instrument_id,
        source_family=value.source_family, source_document_identity=value.source_document_identity,
        source_payload_identity=value.source_payload_identity, source_payload_fingerprint=value.source_payload_fingerprint,
        raw_timestamp_field_path=value.raw_timestamp_field_path, raw_timestamp_value=value.raw_timestamp_value,
        raw_retention_state=raw_state, parsed_local_timestamp=parsed, original_timezone_id=original_zone,
        timezone_provenance_state=provenance, timezone_evidence_ids=ids,
        timezone_evidence_fingerprints=fingerprints, normalized_utc_timestamp=normalized,
        resolution_state=resolution, event_known_time_status=value.event_known_time_status,
        reason_codes=tuple(sorted(set(reasons))), contract_id=CONTRACT_ID,
        contract_version=CONTRACT_VERSION, actionability="WATCH_ONLY", execution_status="NON_EXECUTABLE",
    )
    return FilingTimestampProvenanceReceipt(**data, fingerprint=_fingerprint(_receipt_values(data)))


def _buckets(values: tuple[FilingTimestampAuditRecord, ...], key) -> tuple[FilingTimestampAuditBucket, ...]:
    groups: dict[str, list[FilingTimestampAuditRecord]] = {}
    for value in values:
        groups.setdefault(key(value), []).append(value)
    return tuple(
        FilingTimestampAuditBucket(name, len(group), _enum_counts((item.receipt.resolution_state for item in group), TimestampResolutionState))
        for name, group in sorted(groups.items())
    )


def _enum_counts(values: Iterable[StrEnum], enum_type) -> tuple[tuple[StrEnum, int], ...]:
    counts = {state: 0 for state in enum_type}
    for value in values:
        counts[value] += 1
    return tuple((state, count) for state, count in sorted(counts.items(), key=lambda item: item[0].value) if count)


def _state_counts_invalid(values, enum_type, expected_total: int) -> bool:
    return (
        values != tuple(sorted(values, key=lambda item: item[0].value))
        or any(not isinstance(state, enum_type) or not isinstance(count, int) or count < 0 for state, count in values)
        or sum(count for _state, count in values) != expected_total
    )


def _parse_known_bse_or_iso_text(raw: str) -> datetime:
    explicit = _raw_explicit_offset(raw)
    if explicit is not None:
        return explicit
    for pattern in ("%d-%m-%Y %H:%M:%S", "%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, pattern)
        except ValueError:
            pass
    raise FilingTimestampTimezoneError("SOURCE_TIMESTAMP_TEXT_MALFORMED")


def _raw_explicit_offset(raw: str) -> datetime | None:
    if not _OFFSET_TIMESTAMP.fullmatch(raw):
        return None
    try:
        parsed = datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
    except ValueError as error:
        raise FilingTimestampTimezoneError("EXPLICIT_OFFSET_TIMESTAMP_MALFORMED") from error
    if not _aware(parsed):
        raise FilingTimestampTimezoneError("EXPLICIT_OFFSET_TIMESTAMP_MALFORMED")
    return parsed


def _timestamp_matches_zone(value: datetime, timezone_id: str) -> bool:
    try:
        zone = ZoneInfo(timezone_id)
    except ZoneInfoNotFoundError:
        return False
    return value.astimezone(zone).utcoffset() == value.utcoffset()


def _offset_label(value: datetime) -> str:
    offset = value.utcoffset()
    if offset is None:
        raise FilingTimestampTimezoneError("EXPLICIT_OFFSET_REQUIRED")
    seconds = int(offset.total_seconds())
    sign = "+" if seconds >= 0 else "-"
    hours, minutes = divmod(abs(seconds) // 60, 60)
    return f"{sign}{hours:02d}:{minutes:02d}"


def _rule_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _receipt_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _audit_values(values: dict[str, object]) -> dict[str, object]: return _scalar(values)
def _without(value: object, *names: str) -> dict[str, object]: return {field.name: getattr(value, field.name) for field in fields(value) if field.name not in names}


def _scalar(value: object) -> object:
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return value.astimezone(UTC).isoformat() if _aware(value) else value.isoformat()
    if isinstance(value, date): return value.isoformat()
    if isinstance(value, tuple): return tuple(_scalar(item) for item in value)
    if hasattr(value, "__dataclass_fields__"): return {field.name: _scalar(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict): return {key: _scalar(item) for key, item in value.items()}
    return value


def _fingerprint(values: dict[str, object]) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(_scalar(values), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _receipt_id(filing_id: str, source_family: str, source_document_identity: str,
                raw_field: str | None, source_payload_fingerprint: str) -> str:
    material = "|".join((filing_id, source_family, source_document_identity, raw_field or "", source_payload_fingerprint))
    return "filing-timezone:" + hashlib.sha256(material.encode()).hexdigest()[:24]


def _identifier(value: object) -> bool: return isinstance(value, str) and _IDENTIFIER.fullmatch(value) is not None
def _nonempty(value: object) -> bool: return isinstance(value, str) and bool(value.strip())
def _fingerprint_value(value: object) -> bool: return isinstance(value, str) and _FINGERPRINT.fullmatch(value) is not None
def _date(value: object) -> bool: return isinstance(value, date) and not isinstance(value, datetime)
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise FilingTimestampTimezoneError("AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)
def _timezone(value: object) -> bool:
    if not _nonempty(value): return False
    try: ZoneInfo(str(value))
    except ZoneInfoNotFoundError: return False
    return True
def _timezone_or_offset(value: object) -> bool:
    return _timezone(value) or (isinstance(value, str) and re.fullmatch(r"[+-]\d{2}:\d{2}", value) is not None)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "EventKnownTimeStatus", "FilingTimestampAudit",
    "FilingTimestampAuditBucket", "FilingTimestampAuditRecord", "FilingTimestampInput",
    "FilingTimestampProvenanceReceipt", "FilingTimestampTimezoneError", "RawTimestampRetentionState",
    "SourceTimestampEncoding", "SourceTimezoneRule", "TimestampProvenanceState", "TimestampResolutionState",
    "audit_filing_timestamp_receipts", "canonical_event_timestamp_from_receipt",
    "make_filing_timestamp_input", "make_source_timezone_rule", "receipt_from_corporate_filing",
    "resolve_filing_timestamp", "serialize_filing_timestamp_receipt",
)
