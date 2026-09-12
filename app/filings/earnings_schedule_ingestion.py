"""Pure schedule normalization using existing identity and timestamp governance.

No system-first-observed fallback is admitted. A typed candidate is descriptive
UNVERIFIED_SOURCE_AUTHORITY evidence, never a Gate 6 input.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
import re

from app.filings.earnings_schedule_source import (
    RawSchedule, SourceBatch, SourceState, classify, parse_meeting_date, utc,
)
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.official_earnings_schedule_candidate import (
    OfficialEarningsScheduleCandidate, PurposeClassification, ScheduleEventType,
    ScheduleLifecycleState, SchedulePrecision, SourceExchange,
    SourceInstrumentIdentifierKind, make_official_earnings_schedule_candidate,
)
from app.historical.security_master import HistoricalSecurityIdentity
from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge, IdentityState
from app.historical.filing_timestamp_timezone_provenance import (
    EventKnownTimeStatus, FilingTimestampProvenanceReceipt, SourceTimestampEncoding,
    SourceTimezoneRule, make_filing_timestamp_input, resolve_filing_timestamp,
)


@dataclass(frozen=True, slots=True)
class ScheduleNormalization:
    source: RawSchedule
    retrieved_at: datetime
    state: SourceState
    reasons: tuple[str, ...]
    canonical_instrument_id: str
    identity_receipt_fingerprint: str | None
    timestamp_receipt: FilingTimestampProvenanceReceipt | None
    candidate: OfficialEarningsScheduleCandidate | None

    @property
    def fingerprint(self) -> str:
        # Candidate serializer explicitly converts DATE_ONLY values.
        return content_fingerprint(self.to_json())

    def to_json(self) -> str:
        return canonical_json({"source": self.source, "retrieved_at": self.retrieved_at,
                               "state": self.state, "reasons": self.reasons,
                               "instrument": self.canonical_instrument_id,
                               "identity_fingerprint": self.identity_receipt_fingerprint,
                               "timestamp": self.timestamp_receipt,
                               "candidate": self.candidate.to_json() if self.candidate else None})


def _parsed_timestamp(raw: str) -> datetime:
    # ISO with explicit offset is preserved. Observed bare exchange display
    # formats remain naive; neither machine locale nor site-clock timezone enters.
    if re.search(r"\d{2}:\d{2}:\d{2}", raw) is None:
        raise ValueError("EARNINGS_SOURCE_EXACT_CLOCK_REQUIRED")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        parts = raw.split()
        if len(parts) != 2:
            raise ValueError("EARNINGS_SOURCE_TIMESTAMP_FORMAT_UNSUPPORTED") from None
        return datetime.combine(parse_meeting_date(parts[0]), time.fromisoformat(parts[1]))


def _timestamp(row: RawSchedule, field: str, instrument: str, retrieved_at: datetime,
               rules: tuple[SourceTimezoneRule, ...]) -> FilingTimestampProvenanceReceipt:
    raw = row.field(field)
    parsed = _parsed_timestamp(raw) if raw else None
    identity = "earnings-source:" + row.fingerprint[7:]
    value = make_filing_timestamp_input(
        filing_id=identity, canonical_instrument_id=instrument,
        source_family=row.parser_version, source_document_identity=row.reference,
        source_payload_identity=identity, source_payload_fingerprint=row.fingerprint,
        raw_timestamp_field_path=field if raw else None, raw_timestamp_value=raw,
        parsed_local_timestamp=parsed, filing_date=None, declared_timezone_id=None,
        encoding=SourceTimestampEncoding.TEXT if raw else SourceTimestampEncoding.MISSING,
        event_known_time_status=EventKnownTimeStatus.SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED,
    )
    # Existing timestamp policy checks exact field, source, effective dates,
    # rule provenance and visibility. No adapter-local timezone rule is added.
    return resolve_filing_timestamp(value, rules=rules, as_of=retrieved_at)


def normalize_schedule(row: RawSchedule, *, canonical_instrument_id: str,
                       identities: tuple[HistoricalSecurityIdentity, ...] = (),
                       retrieved_at: datetime,
                       timezone_rules: tuple[SourceTimezoneRule, ...] = (),
                       identity_bridge: EarningsScheduleCanonicalIdentityBridge | None = None) -> ScheduleNormalization:
    row.__post_init__()
    point = utc(retrieved_at)
    if not re.fullmatch(r"NSE:IN[A-Z0-9]{9}[0-9]", canonical_instrument_id):
        raise ValueError("EARNINGS_CANONICAL_IDENTITY_INVALID")
    timestamp, identity_fingerprint = None, None

    def failed(state, reason):
        return ScheduleNormalization(row, point, state, (reason,), canonical_instrument_id,
                                     identity_fingerprint, timestamp, None)

    # Current observed representations provide no exact parent-filing field.
    # Do not invent one from company/date or silently treat an amendment as new.
    text = " ".join(v.upper() for k, v in row.raw if k in {"purpose", "details", "intimation_type"})
    if (row.field("intimation_type") not in (None, "New", "Original")
            or re.search(r"\b(REVISED|REVISION|RESCHEDULED|CANCELLED|CANCELED|POSTPONED|SUPERSEDED|WITHDRAWN)\b", text)):
        return failed(SourceState.REVISION_LINEAGE_UNRESOLVED, "EXACT_PARENT_FILING_REQUIRED")
    purpose = classify(row)
    if purpose.classification == PurposeClassification.NON_QUALIFYING:
        return failed(SourceState.SUCCESS_NO_QUALIFYING_ROWS, purpose.rule)
    if purpose.classification == PurposeClassification.AMBIGUOUS:
        return failed(SourceState.PURPOSE_AMBIGUOUS, purpose.rule)
    try:
        timestamp = _timestamp(row, "disseminated", canonical_instrument_id, point, timezone_rules)
        known = timestamp.normalized_utc_timestamp
        if known is None or known > point:
            return failed(SourceState.TIMESTAMP_UNAVAILABLE, "PUBLIC_DISSEMINATION_TIME_UNPROVEN")
        received_receipt = _timestamp(row, "received", canonical_instrument_id, point, timezone_rules)
        received = received_receipt.normalized_utc_timestamp
        if row.field("received") and received is None:
            return failed(SourceState.TIMESTAMP_UNAVAILABLE, "EXCHANGE_RECEIPT_TIME_UNRESOLVED")
    except ValueError:
        return failed(SourceState.TIMESTAMP_UNAVAILABLE, "SOURCE_TIMESTAMP_UNPARSEABLE")
    source_key = "symbol" if row.exchange == SourceExchange.NSE else "security_code"
    source_identifier = row.field(source_key)
    if identity_bridge is not None and identities:
        raise ValueError("EARNINGS_IDENTITY_INPUT_AMBIGUOUS")
    bridge = identity_bridge or EarningsScheduleCanonicalIdentityBridge(identities=identities)
    resolve = bridge.resolve_nse if row.exchange == SourceExchange.NSE else bridge.resolve_bse
    selected = resolve(source_identifier, row.field("isin"), known)
    if selected.resolution_state != IdentityState.RESOLVED:
        return failed(SourceState.IDENTITY_UNRESOLVED, "EFFECTIVE_IDENTITY_REQUIRED")
    if selected.canonical_instrument_id != canonical_instrument_id:
        return failed(SourceState.IDENTITY_UNRESOLVED, "EXACT_SOURCE_IDENTITY_REQUIRED")
    identity_fingerprint = selected.fingerprint
    try:
        meeting = parse_meeting_date(row.field("meeting_date_iso") or row.field("meeting_date") or "")
        if type(meeting) is not date:
            raise ValueError
        candidate = make_official_earnings_schedule_candidate(
            canonical_instrument_id=canonical_instrument_id,
            source_instrument_identifier_kind=(SourceInstrumentIdentifierKind.NSE_SYMBOL if row.exchange == SourceExchange.NSE else SourceInstrumentIdentifierKind.BSE_SECURITY_CODE),
            source_instrument_identifier=source_identifier,
            event_type=ScheduleEventType.FINANCIAL_RESULTS_BOARD_MEETING,
            declared_purpose=row.field("purpose") or row.field("details"),
            purpose_classification=purpose.classification,
            scheduled_date=meeting, scheduled_time=None, schedule_precision=SchedulePrecision.DATE_ONLY,
            statement_scope=None, financial_period_reference=None,
            source_exchange=row.exchange, source_reference=row.reference,
            source_filing_identity=row.field("filing_identity") or row.field("link") or row.reference,
            source_attachment_reference=None,
            source_xbrl_reference=row.reference if row.parser_version.startswith("nse-reg29-") else None,
            revision_state=ScheduleLifecycleState.ANNOUNCED, revision_of_schedule_id=None,
            exchange_received_at=received, exchange_disseminated_at=known, known_at=known,
            hsi_received_at=point, source_fingerprint=row.fingerprint,
        )
    except ValueError:
        return failed(SourceState.SOURCE_MALFORMED, "CANDIDATE_FIELDS_INVALID")
    return ScheduleNormalization(row, point, SourceState.SUCCESS_WITH_ROWS, (), canonical_instrument_id,
                                 identity_fingerprint, timestamp, candidate)


def coverage_receipt(batch: SourceBatch, *, instruments: tuple[str, ...],
                     window_start: date, window_end: date) -> str:
    """Discovery coverage, not per-instrument success or inferred event absence.

    Counts explicitly refer to the source inventory. Unmapped RSS titles are
    not attributed to any requested company, even when a name appears familiar.
    """
    if (not instruments or instruments != tuple(sorted(set(instruments)))
            or any(not re.fullmatch(r"NSE:IN[A-Z0-9]{9}[0-9]", i) for i in instruments)
            or type(window_start) is not date or type(window_end) is not date or window_end < window_start):
        raise ValueError("EARNINGS_COVERAGE_REQUEST_INVALID")
    purposes = tuple(classify(row) for row in batch.rows)
    body = dict(version="official-schedule-coverage/v1", source=batch.exchange, url=batch.url,
                query_attempted=True, http_succeeded=batch.http_status == 200,
                query_succeeded=batch.state in {SourceState.SUCCESS_WITH_ROWS, SourceState.SUCCESS_NO_QUALIFYING_ROWS},
                window_start=window_start.isoformat(), window_end=window_end.isoformat(),
                window_applied_by_source=False, requested_instruments=instruments,
                individually_queried_instruments=(), state=batch.state, reason=batch.reason,
                retrieved_at=batch.retrieved_at, last_successful_complete_query=None,
                last_successful_transport_retrieval=batch.retrieved_at if batch.http_status == 200 else None,
                records_seen=len(batch.rows), inventory_qualifying=sum(p.classification not in {PurposeClassification.NON_QUALIFYING, PurposeClassification.AMBIGUOUS} for p in purposes),
                inventory_non_qualifying=sum(p.classification == PurposeClassification.NON_QUALIFYING for p in purposes),
                inventory_ambiguous=sum(p.classification == PurposeClassification.AMBIGUOUS for p in purposes),
                source_errors=() if batch.rows else (batch.reason,),
                source_fingerprints=() if batch.source_fingerprint is None else (batch.source_fingerprint,),
                row_fingerprints=tuple(sorted(row.fingerprint for row in batch.rows)),
                purpose_receipts=purposes, freshness="POLICY_BLOCKED", gate6_clearance=False)
    return canonical_json(body | {"fingerprint": content_fingerprint(body)})
