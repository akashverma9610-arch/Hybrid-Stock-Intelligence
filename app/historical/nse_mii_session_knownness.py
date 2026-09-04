"""Proposed, non-active session evidence semantics for NSE MII snapshots.

This pure adapter does not promote a snapshot into ``HistoricalSecurityIdentity``.
It can only describe whether one exact validated NSE MII security-master row is
present in the *same* canonical trading session as its report date.  A dated
file is never substituted backward or forward, and no timestamp or listing
interval is inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import json
import re
from typing import Iterable, Protocol

from app.historical.guard import manifest_fingerprint
from app.historical.nse_mii_security_master import (
    CONTRACT_ID as SOURCE_CONTRACT_ID,
    CONTRACT_VERSION as SOURCE_CONTRACT_VERSION,
    NseMiiAvailabilitySemantics,
    NseMiiSecurityMasterRow,
    NseMiiSecurityMasterSnapshot,
    nse_mii_security_master_url,
)


POLICY_ID = "nse-security-master-session-knownness-policy"
POLICY_VERSION = "v1-proposed"
CONTRACT_ID = "nse-mii-session-knownness-evaluator"
CONTRACT_VERSION = "v1"
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseMiiSessionKnownnessPolicyState(StrEnum):
    PROPOSED = "PROPOSED"


class NseMiiSessionKnownnessApprovalState(StrEnum):
    NOT_APPROVED = "NOT_APPROVED"


class NseMiiSessionKnownnessActivationState(StrEnum):
    NOT_ACTIVE = "NOT_ACTIVE"


class NseMiiSessionKnownnessStatus(StrEnum):
    SESSION_IDENTITY_PRESENT = "SESSION_IDENTITY_PRESENT"
    SNAPSHOT_UNAVAILABLE = "SNAPSHOT_UNAVAILABLE"
    WRONG_SESSION = "WRONG_SESSION"
    FUTURE_SNAPSHOT = "FUTURE_SNAPSHOT"
    INVALID_SOURCE_DATE = "INVALID_SOURCE_DATE"
    AMBIGUOUS_CONFLICTED_ROW = "AMBIGUOUS_CONFLICTED_ROW"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class NseMiiSessionKnownnessReason(StrEnum):
    EVALUATION_SESSION_NOT_TRADING_DAY = "EVALUATION_SESSION_NOT_TRADING_DAY"
    SNAPSHOT_REQUIRED = "SNAPSHOT_REQUIRED"
    EXACT_ROW_REQUIRED = "EXACT_ROW_REQUIRED"
    SNAPSHOT_SOURCE_INVALID = "SNAPSHOT_SOURCE_INVALID"
    SNAPSHOT_FILENAME_DATE_MISMATCH = "SNAPSHOT_FILENAME_DATE_MISMATCH"
    SNAPSHOT_REPORT_DATE_MISMATCH = "SNAPSHOT_REPORT_DATE_MISMATCH"
    FUTURE_SNAPSHOT_EXCLUDED = "FUTURE_SNAPSHOT_EXCLUDED"
    LATER_SESSION_REQUIRES_OWN_SNAPSHOT = "LATER_SESSION_REQUIRES_OWN_SNAPSHOT"
    ROW_SNAPSHOT_BINDING_INVALID = "ROW_SNAPSHOT_BINDING_INVALID"
    ROW_NOT_IN_VALIDATED_SNAPSHOT = "ROW_NOT_IN_VALIDATED_SNAPSHOT"
    AMBIGUOUS_EXACT_SECURITY_ROW = "AMBIGUOUS_EXACT_SECURITY_ROW"


class NseTradingSessionCalendar(Protocol):
    """Existing calendar-compatible boundary; no calendar is implemented here."""

    def is_trading_day(self, value: date) -> bool: ...


@dataclass(frozen=True, slots=True)
class NseMiiSessionKnownnessPolicy:
    """The human-approval-gated policy, recorded without selection or activation."""

    policy_id: str
    version: str
    state: NseMiiSessionKnownnessPolicyState
    approval_state: NseMiiSessionKnownnessApprovalState
    activation_state: NseMiiSessionKnownnessActivationState
    source_contract_id: str
    source_contract_version: str
    allowed_semantics: tuple[str, ...]
    prohibited_semantics: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            self.policy_id != POLICY_ID
            or self.version != POLICY_VERSION
            or self.state is not NseMiiSessionKnownnessPolicyState.PROPOSED
            or self.approval_state is not NseMiiSessionKnownnessApprovalState.NOT_APPROVED
            or self.activation_state is not NseMiiSessionKnownnessActivationState.NOT_ACTIVE
            or self.source_contract_id != SOURCE_CONTRACT_ID
            or self.source_contract_version != SOURCE_CONTRACT_VERSION
            or self.allowed_semantics != _ALLOWED_SEMANTICS
            or self.prohibited_semantics != _PROHIBITED_SEMANTICS
            or self.fingerprint != nse_mii_session_knownness_policy_fingerprint(self)
        ):
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class NseMiiSessionKnownnessEvaluation:
    """Research-only result; it cannot be used as a listed-security receipt."""

    policy_id: str
    policy_version: str
    policy_fingerprint: str
    evaluation_session: date
    status: NseMiiSessionKnownnessStatus
    reasons: tuple[NseMiiSessionKnownnessReason, ...]
    session_identity_present: bool
    snapshot_id: str | None
    snapshot_fingerprint: str | None
    row_id: str | None
    row_fingerprint: str | None
    exchange: str | None
    symbol: str | None
    isin: str | None
    series: str | None
    security_code: str | None
    security_name: str | None
    normal_market_status_raw: str | None
    security_type_raw: str | None
    financial_instrument_type_raw: str | None
    historical_known_at: None = None
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if (
            self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.policy_fingerprint != create_proposed_nse_mii_session_knownness_policy().fingerprint
            or not _date_value(self.evaluation_session)
            or not isinstance(self.status, NseMiiSessionKnownnessStatus)
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value))
            or not all(isinstance(value, NseMiiSessionKnownnessReason) for value in self.reasons)
            or self.historical_known_at is not None
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
        ):
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_EVALUATION_INVALID")
        lineage = (self.snapshot_id, self.snapshot_fingerprint, self.row_id, self.row_fingerprint)
        identity = (
            self.exchange, self.symbol, self.isin, self.security_code, self.security_name,
            self.normal_market_status_raw, self.security_type_raw, self.financial_instrument_type_raw,
        )
        if self.status is NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT:
            if (
                self.reasons
                or not self.session_identity_present
                or not all(lineage)
                or not all((self.exchange == "NSE", self.symbol, self.isin, self.security_code, self.security_name))
            ):
                raise ValueError("NSE_MII_SESSION_KNOWNNESS_PRESENT_FIELDS_REQUIRED")
        elif self.session_identity_present or any(value is not None for value in (*lineage, *identity, self.series)):
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_UNAVAILABLE_FIELDS_FORBIDDEN")
        if self.status is not NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT and not self.reasons:
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_REASON_REQUIRED")
        if self.status is not NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT and (
            len(self.reasons) != 1 or self.reasons[0] not in _REASONS_FOR_STATUS[self.status]
        ):
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_REASON_STATUS_CONTRADICTION")
        if self.fingerprint != nse_mii_session_knownness_evaluation_fingerprint(self):
            raise ValueError("NSE_MII_SESSION_KNOWNNESS_FINGERPRINT_MISMATCH")


_ALLOWED_SEMANTICS = (
    "EXACT_NSE_SYMBOL_ISIN_SERIES_SECURITY_CODE_FOR_SAME_SESSION",
    "EXACT_PRESENT_SECURITY_STATUS_AND_TYPE_FIELDS",
    "SESSION_IDENTITY_EVIDENCE_ONLY",
)
_PROHIBITED_SEMANTICS = (
    "BACKWARD_SESSION_SUBSTITUTION",
    "FORWARD_SESSION_SUBSTITUTION",
    "LISTING_START_INFERENCE",
    "LISTING_END_INFERENCE",
    "DELISTING_FROM_ABSENCE",
    "LISTING_INTERVAL_INFERENCE",
    "CHANGED_ISIN_CONTINUITY_INFERENCE",
    "CHANGED_SYMBOL_CONTINUITY_INFERENCE",
    "PUBLICATION_TIMESTAMP_INFERENCE",
    "COMPANY_TYPE_CLASSIFICATION",
    "COMPOUNDER_OR_INVESTMENT_ELIGIBILITY",
)
_REASONS_FOR_STATUS = {
    NseMiiSessionKnownnessStatus.SNAPSHOT_UNAVAILABLE: frozenset({
        NseMiiSessionKnownnessReason.SNAPSHOT_REQUIRED,
        NseMiiSessionKnownnessReason.EXACT_ROW_REQUIRED,
    }),
    NseMiiSessionKnownnessStatus.WRONG_SESSION: frozenset({
        NseMiiSessionKnownnessReason.LATER_SESSION_REQUIRES_OWN_SNAPSHOT,
    }),
    NseMiiSessionKnownnessStatus.FUTURE_SNAPSHOT: frozenset({
        NseMiiSessionKnownnessReason.FUTURE_SNAPSHOT_EXCLUDED,
    }),
    NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE: frozenset({
        NseMiiSessionKnownnessReason.SNAPSHOT_SOURCE_INVALID,
        NseMiiSessionKnownnessReason.SNAPSHOT_FILENAME_DATE_MISMATCH,
        NseMiiSessionKnownnessReason.SNAPSHOT_REPORT_DATE_MISMATCH,
        NseMiiSessionKnownnessReason.ROW_SNAPSHOT_BINDING_INVALID,
        NseMiiSessionKnownnessReason.ROW_NOT_IN_VALIDATED_SNAPSHOT,
    }),
    NseMiiSessionKnownnessStatus.AMBIGUOUS_CONFLICTED_ROW: frozenset({
        NseMiiSessionKnownnessReason.AMBIGUOUS_EXACT_SECURITY_ROW,
    }),
    NseMiiSessionKnownnessStatus.NOT_APPLICABLE: frozenset({
        NseMiiSessionKnownnessReason.EVALUATION_SESSION_NOT_TRADING_DAY,
    }),
}


def create_proposed_nse_mii_session_knownness_policy() -> NseMiiSessionKnownnessPolicy:
    values = dict(
        policy_id=POLICY_ID,
        version=POLICY_VERSION,
        state=NseMiiSessionKnownnessPolicyState.PROPOSED,
        approval_state=NseMiiSessionKnownnessApprovalState.NOT_APPROVED,
        activation_state=NseMiiSessionKnownnessActivationState.NOT_ACTIVE,
        source_contract_id=SOURCE_CONTRACT_ID,
        source_contract_version=SOURCE_CONTRACT_VERSION,
        allowed_semantics=_ALLOWED_SEMANTICS,
        prohibited_semantics=_PROHIBITED_SEMANTICS,
    )
    return NseMiiSessionKnownnessPolicy(
        **values,
        fingerprint=_fingerprint(values),
    )


def evaluate_nse_mii_session_knownness(
    policy: NseMiiSessionKnownnessPolicy,
    *,
    snapshot: NseMiiSecurityMasterSnapshot | None,
    row: NseMiiSecurityMasterRow | None,
    snapshot_rows: Iterable[NseMiiSecurityMasterRow] | None = None,
    evaluation_session: date,
    calendar: NseTradingSessionCalendar,
) -> NseMiiSessionKnownnessEvaluation:
    """Test one exact row against the proposed same-session-only rule.

    ``snapshot_rows`` must be supplied from the same immutable artifact when
    conflict detection is desired.  The function never searches another date,
    reads storage, uses wall-clock time, or creates an identity/lifecycle fact.
    """
    if (
        not isinstance(policy, NseMiiSessionKnownnessPolicy)
        or policy.fingerprint != nse_mii_session_knownness_policy_fingerprint(policy)
        or not _date_value(evaluation_session)
    ):
        raise ValueError("NSE_MII_SESSION_KNOWNNESS_INPUT_INVALID")
    if not hasattr(calendar, "is_trading_day"):
        raise ValueError("NSE_MII_SESSION_KNOWNNESS_CALENDAR_REQUIRED")
    if not calendar.is_trading_day(evaluation_session):
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.NOT_APPLICABLE,
                            NseMiiSessionKnownnessReason.EVALUATION_SESSION_NOT_TRADING_DAY)
    if snapshot is None:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.SNAPSHOT_UNAVAILABLE,
                            NseMiiSessionKnownnessReason.SNAPSHOT_REQUIRED)
    snapshot_reason = _snapshot_failure_reason(snapshot)
    if snapshot_reason is not None:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE,
                            snapshot_reason)
    if snapshot.report_date > evaluation_session:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.FUTURE_SNAPSHOT,
                            NseMiiSessionKnownnessReason.FUTURE_SNAPSHOT_EXCLUDED)
    if snapshot.report_date < evaluation_session:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.WRONG_SESSION,
                            NseMiiSessionKnownnessReason.LATER_SESSION_REQUIRES_OWN_SNAPSHOT)
    if row is None:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.SNAPSHOT_UNAVAILABLE,
                            NseMiiSessionKnownnessReason.EXACT_ROW_REQUIRED)
    values = (row,) if snapshot_rows is None else tuple(snapshot_rows)
    if not _row_valid_for_snapshot(row, snapshot) or any(not _row_valid_for_snapshot(value, snapshot) for value in values):
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE,
                            NseMiiSessionKnownnessReason.SNAPSHOT_REPORT_DATE_MISMATCH if isinstance(row, NseMiiSecurityMasterRow) and row.report_date != snapshot.report_date else NseMiiSessionKnownnessReason.ROW_SNAPSHOT_BINDING_INVALID)
    if not values or row.row_id not in {value.row_id for value in values}:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE,
                            NseMiiSessionKnownnessReason.ROW_NOT_IN_VALIDATED_SNAPSHOT)
    exact = tuple(value for value in values if _exact_security_key(value) == _exact_security_key(row))
    if len(exact) != 1:
        return _unavailable(policy, evaluation_session, NseMiiSessionKnownnessStatus.AMBIGUOUS_CONFLICTED_ROW,
                            NseMiiSessionKnownnessReason.AMBIGUOUS_EXACT_SECURITY_ROW)
    return _present(policy, evaluation_session, snapshot, row)


def nse_mii_session_knownness_policy_fingerprint(value: NseMiiSessionKnownnessPolicy) -> str:
    return _fingerprint({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_mii_session_knownness_evaluation_fingerprint(value: NseMiiSessionKnownnessEvaluation) -> str:
    return _fingerprint({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_mii_session_knownness_payload(value: NseMiiSessionKnownnessEvaluation) -> dict[str, object]:
    """Stable, explicit serialization with no acquisition timestamp as known time."""
    return {
        "policy_id": value.policy_id, "policy_version": value.policy_version,
        "policy_fingerprint": value.policy_fingerprint, "evaluation_session": value.evaluation_session.isoformat(),
        "status": value.status.value, "reasons": tuple(item.value for item in value.reasons),
        "session_identity_present": value.session_identity_present, "snapshot_id": value.snapshot_id,
        "snapshot_fingerprint": value.snapshot_fingerprint, "row_id": value.row_id,
        "row_fingerprint": value.row_fingerprint, "exchange": value.exchange, "symbol": value.symbol,
        "isin": value.isin, "series": value.series, "security_code": value.security_code,
        "security_name": value.security_name, "normal_market_status_raw": value.normal_market_status_raw,
        "security_type_raw": value.security_type_raw,
        "financial_instrument_type_raw": value.financial_instrument_type_raw,
        "historical_known_at": None, "contract_id": value.contract_id,
        "contract_version": value.contract_version, "fingerprint": value.fingerprint,
    }


def serialize_nse_mii_session_knownness(value: NseMiiSessionKnownnessEvaluation) -> str:
    """Canonical JSON serialization independent of locale or runtime clock."""
    return json.dumps(nse_mii_session_knownness_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _present(policy, session, snapshot, row):
    values = dict(
        policy_id=policy.policy_id, policy_version=policy.version, policy_fingerprint=policy.fingerprint,
        evaluation_session=session, status=NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT,
        reasons=(), session_identity_present=True, snapshot_id=snapshot.snapshot_id,
        snapshot_fingerprint=snapshot.fingerprint, row_id=row.row_id, row_fingerprint=row.fingerprint,
        exchange="NSE", symbol=row.symbol, isin=row.isin, series=row.series,
        security_code=row.security_code, security_name=row.security_name,
        normal_market_status_raw=row.normal_market_status_raw, security_type_raw=row.security_type_raw,
        financial_instrument_type_raw=row.financial_instrument_type_raw,
    )
    return NseMiiSessionKnownnessEvaluation(**values, fingerprint=_fingerprint(values | {
        "historical_known_at": None, "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }))


def _unavailable(policy, session, status, reason):
    values = dict(
        policy_id=policy.policy_id, policy_version=policy.version, policy_fingerprint=policy.fingerprint,
        evaluation_session=session, status=status, reasons=(reason,), session_identity_present=False,
        snapshot_id=None, snapshot_fingerprint=None, row_id=None, row_fingerprint=None, exchange=None,
        symbol=None, isin=None, series=None, security_code=None, security_name=None,
        normal_market_status_raw=None, security_type_raw=None, financial_instrument_type_raw=None,
    )
    return NseMiiSessionKnownnessEvaluation(**values, fingerprint=_fingerprint(values | {
        "historical_known_at": None, "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }))


def _snapshot_failure_reason(value: object) -> NseMiiSessionKnownnessReason | None:
    if not isinstance(value, NseMiiSecurityMasterSnapshot) or not _date_value(value.report_date):
        return NseMiiSessionKnownnessReason.SNAPSHOT_SOURCE_INVALID
    if value.source_reference != nse_mii_security_master_url(value.report_date):
        return NseMiiSessionKnownnessReason.SNAPSHOT_SOURCE_INVALID
    if value.expected_filename != value.source_reference.rsplit("/", 1)[-1]:
        return NseMiiSessionKnownnessReason.SNAPSHOT_FILENAME_DATE_MISMATCH
    if (
        value.availability_semantics is not NseMiiAvailabilitySemantics.DOCUMENTED_PRE_TRADING_DATE_ONLY
        or value.historical_known_at is not None
        or value.contract_id != SOURCE_CONTRACT_ID
        or value.contract_version != SOURCE_CONTRACT_VERSION
        or not _fingerprint_value(value.raw_file_fingerprint)
        or not _fingerprint_value(value.schema_fingerprint)
    ):
        return NseMiiSessionKnownnessReason.SNAPSHOT_SOURCE_INVALID
    return None


def _row_valid_for_snapshot(row: object, snapshot: NseMiiSecurityMasterSnapshot) -> bool:
    return isinstance(row, NseMiiSecurityMasterRow) and (
        row.snapshot_id == snapshot.snapshot_id
        and row.report_date == snapshot.report_date
        and row.historical_known_at is None
        and row.contract_id == SOURCE_CONTRACT_ID
        and row.contract_version == SOURCE_CONTRACT_VERSION
        and _fingerprint_value(row.raw_row_fingerprint)
    )


def _exact_security_key(value: NseMiiSecurityMasterRow) -> tuple[str, str, str | None, str]:
    return value.symbol, value.isin, value.series, value.security_code


def _date_value(value: object) -> bool:
    return isinstance(value, date) and not hasattr(value, "hour")


def _fingerprint_value(value: object) -> bool:
    return isinstance(value, str) and _FINGERPRINT.fullmatch(value) is not None


def _fingerprint(values: dict[str, object]) -> str:
    def scalar(value: object) -> object:
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, tuple):
            return tuple(scalar(item) for item in value)
        return value
    return "sha256:" + manifest_fingerprint(**{key: scalar(value) for key, value in values.items()})


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "NseMiiSessionKnownnessActivationState", "NseMiiSessionKnownnessApprovalState",
    "NseMiiSessionKnownnessEvaluation", "NseMiiSessionKnownnessPolicy",
    "NseMiiSessionKnownnessPolicyState", "NseMiiSessionKnownnessReason",
    "NseMiiSessionKnownnessStatus", "NseTradingSessionCalendar",
    "create_proposed_nse_mii_session_knownness_policy", "evaluate_nse_mii_session_knownness",
    "nse_mii_session_knownness_evaluation_fingerprint", "nse_mii_session_knownness_payload",
    "nse_mii_session_knownness_policy_fingerprint", "serialize_nse_mii_session_knownness",
)
