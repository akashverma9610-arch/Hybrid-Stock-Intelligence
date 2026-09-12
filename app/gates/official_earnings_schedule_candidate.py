"""Pure, non-admitted official earnings-schedule candidate evidence.

This contract preserves a first-party exchange receipt for a Regulation 29
financial-results board-meeting notice.  It is deliberately not an adapter,
store, Gate 6 producer, or absence certificate.  In particular, a candidate
can never make an earnings blackout pass: source coverage, revision ingestion,
and authority admission remain separate future work.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from enum import StrEnum
import re

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint


CONTRACT_VERSION = "official-earnings-schedule-candidate/v1"
POLICY_ID = "official-nse-bse-earnings-calendar-governance"
POLICY_VERSION = "v1"
SOURCE_AUTHORITY_CLASS = "PRIMARY_EXCHANGE_DISTRIBUTED_COMPANY_FILING"


class EarningsScheduleGovernanceError(ValueError):
    """A source-governance failure, never a company-risk or Gate 6 result."""


class SourceExchange(StrEnum):
    NSE = "NSE"
    BSE = "BSE"


class SourceInstrumentIdentifierKind(StrEnum):
    NSE_SYMBOL = "NSE_SYMBOL"
    BSE_SECURITY_CODE = "BSE_SECURITY_CODE"
    ISIN = "ISIN"


class ScheduleEventType(StrEnum):
    FINANCIAL_RESULTS_BOARD_MEETING = "FINANCIAL_RESULTS_BOARD_MEETING"


class SchedulePrecision(StrEnum):
    DATE_ONLY = "DATE_ONLY"
    DATE_TIME = "DATE_TIME"


class PurposeClassification(StrEnum):
    QUARTERLY_FINANCIAL_RESULTS = "QUARTERLY_FINANCIAL_RESULTS"
    HALF_YEARLY_FINANCIAL_RESULTS = "HALF_YEARLY_FINANCIAL_RESULTS"
    ANNUAL_FINANCIAL_RESULTS = "ANNUAL_FINANCIAL_RESULTS"
    AUDITED_FINANCIAL_RESULTS = "AUDITED_FINANCIAL_RESULTS"
    UNAUDITED_FINANCIAL_RESULTS = "UNAUDITED_FINANCIAL_RESULTS"
    FINANCIAL_RESULTS_UNSPECIFIED = "FINANCIAL_RESULTS_UNSPECIFIED"
    NON_QUALIFYING = "NON_QUALIFYING"
    AMBIGUOUS = "AMBIGUOUS"


class ScheduleLifecycleState(StrEnum):
    ANNOUNCED = "ANNOUNCED"
    REVISED = "REVISED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"
    COMPLETED = "COMPLETED"


class CandidateVerificationState(StrEnum):
    UNVERIFIED_SOURCE_AUTHORITY = "UNVERIFIED_SOURCE_AUTHORITY"


class CandidateIdentityState(StrEnum):
    EXACT_CANONICAL_IDENTITY = "EXACT_CANONICAL_IDENTITY"


class ReconciliationState(StrEnum):
    ONE_EXCHANGE_CANDIDATE = "ONE_EXCHANGE_CANDIDATE"
    DUAL_EXCHANGE_AGREEMENT = "DUAL_EXCHANGE_AGREEMENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    PIT_NOT_VISIBLE = "PIT_NOT_VISIBLE"


_QUALIFYING_PURPOSES = frozenset({
    PurposeClassification.QUARTERLY_FINANCIAL_RESULTS,
    PurposeClassification.HALF_YEARLY_FINANCIAL_RESULTS,
    PurposeClassification.ANNUAL_FINANCIAL_RESULTS,
    PurposeClassification.AUDITED_FINANCIAL_RESULTS,
    PurposeClassification.UNAUDITED_FINANCIAL_RESULTS,
    PurposeClassification.FINANCIAL_RESULTS_UNSPECIFIED,
})
_STRUCTURED_PURPOSES = {
    "QUARTERLY RESULTS": PurposeClassification.QUARTERLY_FINANCIAL_RESULTS,
    "HALF YEARLY RESULTS": PurposeClassification.HALF_YEARLY_FINANCIAL_RESULTS,
    "ANNUAL RESULTS": PurposeClassification.ANNUAL_FINANCIAL_RESULTS,
    "AUDITED RESULTS": PurposeClassification.AUDITED_FINANCIAL_RESULTS,
    "UNAUDITED RESULTS": PurposeClassification.UNAUDITED_FINANCIAL_RESULTS,
    "FINANCIAL RESULTS": PurposeClassification.FINANCIAL_RESULTS_UNSPECIFIED,
}
_NON_QUALIFYING_WORDS = frozenset({
    "BONUS", "BUYBACK", "DIVIDEND", "FUND RAISE", "GENERAL",
    "ISSUE OF WARRANTS", "PREFERENTIAL ISSUE", "RIGHTS ISSUE", "STOCK SPLIT",
})
_CLOCK = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?$")


def _utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None or value.utcoffset() is None:
        raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _text(value: str | None) -> bool:
    return type(value) is str and bool(value) and value == value.strip()


def _optional_text(value: str | None) -> bool:
    return value is None or _text(value)


def _fingerprint(value: str) -> bool:
    return type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _normalise_source_text(value: str | None) -> str | None:
    if value is None:
        return None
    return " ".join(value.upper().split())


def classify_results_purpose(*, structured_purpose: str | None, subject: str | None) -> PurposeClassification:
    """Classify only an explicit structured label or bounded results wording.

    This is intentionally not natural-language understanding.  Generic board
    meetings and corporate-action purposes do not become earnings events.
    """
    structured = _normalise_source_text(structured_purpose)
    if structured in _STRUCTURED_PURPOSES:
        return _STRUCTURED_PURPOSES[structured]
    if structured in _NON_QUALIFYING_WORDS:
        return PurposeClassification.NON_QUALIFYING
    text = _normalise_source_text(subject)
    if text is None:
        return PurposeClassification.AMBIGUOUS
    has_action = re.search(r"\b(CONSIDER|APPROVE|TAKE ON RECORD)\b", text) is not None
    if has_action and re.search(r"\bFINANCIAL RESULTS?\b", text) is not None:
        if "HALF YEAR" in text:
            return PurposeClassification.HALF_YEARLY_FINANCIAL_RESULTS
        if "QUARTER" in text:
            return PurposeClassification.QUARTERLY_FINANCIAL_RESULTS
        if "ANNUAL" in text or "YEAR ENDED" in text:
            return PurposeClassification.ANNUAL_FINANCIAL_RESULTS
        if "UNAUDITED" in text:
            return PurposeClassification.UNAUDITED_FINANCIAL_RESULTS
        if "AUDITED" in text:
            return PurposeClassification.AUDITED_FINANCIAL_RESULTS
        return PurposeClassification.FINANCIAL_RESULTS_UNSPECIFIED
    if any(word in text for word in _NON_QUALIFYING_WORDS):
        return PurposeClassification.NON_QUALIFYING
    return PurposeClassification.AMBIGUOUS


def _candidate_identity_body(value: "OfficialEarningsScheduleCandidate") -> dict[str, object]:
    return {
        "contract_version": value.contract_version,
        "canonical_instrument_id": value.canonical_instrument_id,
        "event_type": value.event_type,
        "declared_purpose": value.declared_purpose,
        "purpose_classification": value.purpose_classification,
        "scheduled_date": value.scheduled_date.isoformat(),
        "scheduled_time": value.scheduled_time,
        "schedule_precision": value.schedule_precision,
        "statement_scope": value.statement_scope,
        "financial_period_reference": value.financial_period_reference,
        "source_exchange": value.source_exchange,
        "source_filing_identity": value.source_filing_identity,
        "revision_state": value.revision_state,
        "revision_of_schedule_id": value.revision_of_schedule_id,
        "source_fingerprint": value.source_fingerprint,
    }


def _candidate_payload(value: "OfficialEarningsScheduleCandidate") -> dict[str, object]:
    body: dict[str, object] = {}
    for field in fields(value):
        if field.name == "fingerprint":
            continue
        item = getattr(value, field.name)
        body[field.name] = item.isoformat() if type(item) is date else item
    return body


@dataclass(frozen=True, slots=True)
class OfficialEarningsScheduleCandidate:
    """One immutable exchange-distributed Regulation 29 schedule receipt.

    ``schedule_id`` is deliberately receipt-specific.  Cross-exchange
    reconciliation is a later pure view, so a BSE receipt can never overwrite
    an NSE receipt (or vice versa).
    """

    schedule_id: str
    canonical_instrument_id: str
    source_instrument_identifier_kind: SourceInstrumentIdentifierKind
    source_instrument_identifier: str
    event_type: ScheduleEventType
    declared_purpose: str
    purpose_classification: PurposeClassification
    scheduled_date: date
    scheduled_time: str | None
    schedule_precision: SchedulePrecision
    statement_scope: str | None
    financial_period_reference: str | None
    source_exchange: SourceExchange
    source_authority_class: str
    source_reference: str
    source_filing_identity: str
    source_attachment_reference: str | None
    source_xbrl_reference: str | None
    source_announcement_type: str
    revision_state: ScheduleLifecycleState
    revision_of_schedule_id: str | None
    exchange_received_at: datetime | None
    exchange_disseminated_at: datetime
    known_at: datetime
    hsi_received_at: datetime
    verification_state: CandidateVerificationState
    identity_state: CandidateIdentityState
    policy_id: str
    policy_version: str
    source_fingerprint: str
    fingerprint: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("exchange_disseminated_at", "known_at", "hsi_received_at"):
            object.__setattr__(self, name, _utc(getattr(self, name)))
        if self.exchange_received_at is not None:
            object.__setattr__(self, "exchange_received_at", _utc(self.exchange_received_at))
        required = (
            self.schedule_id, self.canonical_instrument_id, self.source_instrument_identifier,
            self.declared_purpose, self.source_reference, self.source_filing_identity,
            self.source_announcement_type, self.policy_id, self.policy_version,
        )
        if (self.contract_version != CONTRACT_VERSION
                or not isinstance(self.source_exchange, SourceExchange)
                or not isinstance(self.source_instrument_identifier_kind, SourceInstrumentIdentifierKind)
                or not isinstance(self.schedule_precision, SchedulePrecision)
                or not isinstance(self.revision_state, ScheduleLifecycleState)
                or not isinstance(self.purpose_classification, PurposeClassification)
                or self.event_type is not ScheduleEventType.FINANCIAL_RESULTS_BOARD_MEETING
                or self.purpose_classification not in _QUALIFYING_PURPOSES
                or type(self.scheduled_date) is not date
                or not all(_text(value) for value in required)
                or not all(_optional_text(value) for value in (
                    self.scheduled_time, self.statement_scope, self.financial_period_reference,
                    self.source_attachment_reference, self.source_xbrl_reference,
                    self.revision_of_schedule_id,
                ))
                or self.source_authority_class != SOURCE_AUTHORITY_CLASS
                or self.source_announcement_type != "REGULATION_29_PRIOR_INTIMATION"
                or self.verification_state is not CandidateVerificationState.UNVERIFIED_SOURCE_AUTHORITY
                or self.identity_state is not CandidateIdentityState.EXACT_CANONICAL_IDENTITY
                or self.policy_id != POLICY_ID or self.policy_version != POLICY_VERSION
                or not _fingerprint(self.source_fingerprint)):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_CANDIDATE_INVALID")
        if ((self.schedule_precision is SchedulePrecision.DATE_ONLY and self.scheduled_time is not None)
                or (self.schedule_precision is SchedulePrecision.DATE_TIME
                    and (self.scheduled_time is None or _CLOCK.fullmatch(self.scheduled_time) is None))):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_PRECISION_INVALID")
        revision_required = {
            ScheduleLifecycleState.REVISED, ScheduleLifecycleState.RESCHEDULED,
            ScheduleLifecycleState.CANCELLED, ScheduleLifecycleState.SUPERSEDED,
        }
        if ((self.revision_state in revision_required and self.revision_of_schedule_id is None)
                or (self.revision_state is ScheduleLifecycleState.ANNOUNCED and self.revision_of_schedule_id is not None)
                or self.revision_of_schedule_id == self.schedule_id):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_REVISION_LINEAGE_UNRESOLVED")
        if (self.known_at != self.exchange_disseminated_at
                or self.hsi_received_at < self.known_at
                or (self.exchange_received_at is not None
                    and self.exchange_received_at > self.exchange_disseminated_at)):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_KNOWN_AT_INVALID")
        expected_id = "earnings-schedule:" + content_fingerprint(_candidate_identity_body(self))[7:]
        if self.schedule_id != expected_id:
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_IDENTITY_MISMATCH")
        if self.fingerprint != content_fingerprint(_candidate_payload(self)):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_FINGERPRINT_MISMATCH")

    def visible_at(self, as_of: datetime) -> bool:
        self.__post_init__()
        return self.known_at <= _utc(as_of)

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_candidate_payload(self))


def make_official_earnings_schedule_candidate(**kwargs: object) -> OfficialEarningsScheduleCandidate:
    """Create a candidate with deterministic receipt identity and fingerprint."""
    body = dict(kwargs)
    body.setdefault("source_authority_class", SOURCE_AUTHORITY_CLASS)
    body.setdefault("source_announcement_type", "REGULATION_29_PRIOR_INTIMATION")
    body.setdefault("verification_state", CandidateVerificationState.UNVERIFIED_SOURCE_AUTHORITY)
    body.setdefault("identity_state", CandidateIdentityState.EXACT_CANONICAL_IDENTITY)
    body.setdefault("policy_id", POLICY_ID)
    body.setdefault("policy_version", POLICY_VERSION)
    body.setdefault("contract_version", CONTRACT_VERSION)
    if "schedule_id" in body or "fingerprint" in body:
        raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_DERIVED_FIELDS_FORBIDDEN")
    required_names = {field.name for field in fields(OfficialEarningsScheduleCandidate)} - {"schedule_id", "fingerprint"}
    if set(body) != required_names:
        raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_CANDIDATE_FIELDS_INVALID")
    provisional = object.__new__(OfficialEarningsScheduleCandidate)
    for name, value in body.items():
        object.__setattr__(provisional, name, value)
    # Constructor validation gives precise reasons for omitted or malformed fields.
    schedule_id = "earnings-schedule:" + content_fingerprint(_candidate_identity_body(provisional))[7:]
    object.__setattr__(provisional, "schedule_id", schedule_id)
    fingerprint = content_fingerprint(_candidate_payload(provisional))
    return OfficialEarningsScheduleCandidate(**(body | {"schedule_id": schedule_id, "fingerprint": fingerprint}))


def _reconciliation_payload(value: "EarningsScheduleReconciliation") -> dict[str, object]:
    return {field.name: getattr(value, field.name) for field in fields(value) if field.name != "fingerprint"}


@dataclass(frozen=True, slots=True)
class EarningsScheduleReconciliation:
    """PIT-safe, descriptive view over one or two visible source receipts."""

    as_of: datetime
    state: ReconciliationState
    canonical_instrument_id: str | None
    source_schedule_ids: tuple[str, ...]
    source_exchanges: tuple[SourceExchange, ...]
    reason_code: str | None
    fingerprint: str
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of))
        if (self.contract_version != CONTRACT_VERSION
                or self.source_schedule_ids != tuple(sorted(self.source_schedule_ids))
                or self.source_exchanges != tuple(sorted(self.source_exchanges, key=str))
                or len(set(self.source_schedule_ids)) != len(self.source_schedule_ids)
                or len(set(self.source_exchanges)) != len(self.source_exchanges)
                or not all(_text(item) for item in self.source_schedule_ids)
                or not _optional_text(self.canonical_instrument_id)
                or not _optional_text(self.reason_code)):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_RECONCILIATION_INVALID")
        if self.state is ReconciliationState.PIT_NOT_VISIBLE:
            valid = (self.canonical_instrument_id is None and not self.source_schedule_ids
                     and not self.source_exchanges and self.reason_code == "PIT_NOT_VISIBLE")
        elif self.state is ReconciliationState.ONE_EXCHANGE_CANDIDATE:
            valid = (self.canonical_instrument_id is not None and len(self.source_schedule_ids) >= 1
                     and len(self.source_exchanges) == 1 and self.reason_code is None)
        elif self.state is ReconciliationState.DUAL_EXCHANGE_AGREEMENT:
            valid = (self.canonical_instrument_id is not None and len(self.source_schedule_ids) >= 2
                     and self.source_exchanges == (SourceExchange.BSE, SourceExchange.NSE)
                     and self.reason_code is None)
        else:
            valid = (len(self.source_schedule_ids) >= 2
                     and self.reason_code == "EVIDENCE_CONFLICTED")
        if not valid or self.fingerprint != content_fingerprint(_reconciliation_payload(self)):
            raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_RECONCILIATION_INVALID")

    def to_json(self) -> str:
        self.__post_init__()
        return canonical_json(_reconciliation_payload(self))


def _make_reconciliation(*, as_of: datetime, state: ReconciliationState,
                         canonical_instrument_id: str | None,
                         candidates: tuple[OfficialEarningsScheduleCandidate, ...],
                         reason_code: str | None) -> EarningsScheduleReconciliation:
    ordered = tuple(sorted(candidates, key=lambda item: (item.source_exchange.value, item.schedule_id)))
    body = {
        "as_of": _utc(as_of), "state": state,
        "canonical_instrument_id": canonical_instrument_id,
        "source_schedule_ids": tuple(sorted(item.schedule_id for item in ordered)),
        "source_exchanges": tuple(sorted({item.source_exchange for item in ordered}, key=str)),
        "reason_code": reason_code, "contract_version": CONTRACT_VERSION,
    }
    return EarningsScheduleReconciliation(**(body | {"fingerprint": content_fingerprint(body)}))


def reconcile_visible_schedule_candidates(candidates: tuple[OfficialEarningsScheduleCandidate, ...], *,
                                          as_of: datetime) -> EarningsScheduleReconciliation:
    """Reconcile only evidence public by ``as_of``; never guess amendments.

    The caller must supply an explicitly linked revision chain where one is
    available.  This function does not equate same-company/date records or
    infer an NSE/BSE preference.
    """
    point = _utc(as_of)
    visible = tuple(item for item in candidates if item.visible_at(point))
    if not visible:
        return _make_reconciliation(as_of=point, state=ReconciliationState.PIT_NOT_VISIBLE,
                                    canonical_instrument_id=None, candidates=(), reason_code="PIT_NOT_VISIBLE")
    identities = {item.schedule_id for item in visible}
    if len(identities) != len(visible):
        raise EarningsScheduleGovernanceError("EARNINGS_SCHEDULE_DUPLICATE_RECEIPT")
    instruments = {item.canonical_instrument_id for item in visible}
    exchanges = {item.source_exchange for item in visible}
    agreement = {
        (item.canonical_instrument_id, item.event_type,
         item.purpose_classification, item.scheduled_date, item.scheduled_time,
         item.schedule_precision, item.statement_scope, item.financial_period_reference,
         item.revision_state is ScheduleLifecycleState.CANCELLED)
        for item in visible
    }
    if len(instruments) != 1 or len(agreement) != 1:
        return _make_reconciliation(as_of=point, state=ReconciliationState.EVIDENCE_CONFLICTED,
                                    canonical_instrument_id=next(iter(instruments)) if len(instruments) == 1 else None,
                                    candidates=visible, reason_code="EVIDENCE_CONFLICTED")
    state = ReconciliationState.ONE_EXCHANGE_CANDIDATE if len(exchanges) == 1 else ReconciliationState.DUAL_EXCHANGE_AGREEMENT
    return _make_reconciliation(as_of=point, state=state,
                                canonical_instrument_id=next(iter(instruments)), candidates=visible,
                                reason_code=None)
