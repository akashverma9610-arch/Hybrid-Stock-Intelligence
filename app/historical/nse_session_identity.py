"""Human-approved NSE MII session-point identity evidence.

One official date-labelled MII row proves only its exact exchange identity for
that one trading session.  This module deliberately has no listing interval,
company-type, current-master, portfolio, broker, or execution dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import json
import re
from typing import Iterable

from app.historical.guard import manifest_fingerprint
from app.historical.nse_mii_security_master import (
    CONTRACT_ID as SOURCE_CONTRACT_ID,
    CONTRACT_VERSION as SOURCE_CONTRACT_VERSION,
    NseMiiAvailabilitySemantics,
    NseMiiSecurityMasterRow,
    NseMiiSecurityMasterSnapshot,
    nse_mii_security_master_url,
)
from app.historical.nse_mii_session_knownness import (
    POLICY_ID as PROPOSAL_POLICY_ID,
    POLICY_VERSION as PROPOSAL_POLICY_VERSION,
    NseTradingSessionCalendar,
    create_proposed_nse_mii_session_knownness_policy,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


POLICY_ID = "nse-session-known-security-identity-policy"
POLICY_VERSION = "v1"
CONTRACT_ID = "nse-session-known-security-identity"
CONTRACT_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseSessionIdentityApprovalState(StrEnum):
    APPROVED = "APPROVED"


class NseSessionIdentityActivationState(StrEnum):
    ACTIVE = "ACTIVE"


class NseSessionIdentitySemantic(StrEnum):
    KNOWN_FOR_SESSION_D = "KNOWN_FOR_SESSION_D"


class NseSessionIdentityReceiptStatus(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"
    CONFLICTED = "CONFLICTED"


class NseSessionIdentityResolutionStatus(StrEnum):
    SESSION_IDENTITY_PRESENT = "SESSION_IDENTITY_PRESENT"
    RECEIPT_UNAVAILABLE = "RECEIPT_UNAVAILABLE"
    FUTURE_SESSION_RECEIPT_EXCLUDED = "FUTURE_SESSION_RECEIPT_EXCLUDED"
    LATER_SESSION_REQUIRES_OWN_RECEIPT = "LATER_SESSION_REQUIRES_OWN_RECEIPT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class NseSessionIdentityResolutionReason(StrEnum):
    SESSION_POINT_RECEIPT_REQUIRED = "SESSION_POINT_RECEIPT_REQUIRED"
    FUTURE_SESSION_POINT_RECEIPT_EXCLUDED = "FUTURE_SESSION_POINT_RECEIPT_EXCLUDED"
    LATER_SESSION_POINT_RECEIPT_REQUIRED = "LATER_SESSION_POINT_RECEIPT_REQUIRED"
    AMBIGUOUS_EXACT_SESSION_POINT_IDENTITY = "AMBIGUOUS_EXACT_SESSION_POINT_IDENTITY"


@dataclass(frozen=True, slots=True)
class NseSessionIdentityPolicyApproval:
    approval_id: str
    policy_id: str
    policy_version: str
    proposal_policy_id: str
    proposal_policy_version: str
    proposal_fingerprint: str
    approved_semantics: tuple[NseSessionIdentitySemantic, ...]
    approved_by: str
    approved_at: datetime
    state: NseSessionIdentityApprovalState
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _id(self.approval_id)
            or self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.proposal_policy_id != PROPOSAL_POLICY_ID
            or self.proposal_policy_version != PROPOSAL_POLICY_VERSION
            or self.proposal_fingerprint != create_proposed_nse_mii_session_knownness_policy().fingerprint
            or self.approved_semantics != (NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D,)
            or not self.approved_by.startswith("human:")
            or not _aware(self.approved_at)
            or self.state is not NseSessionIdentityApprovalState.APPROVED
            or self.fingerprint != nse_session_identity_policy_approval_fingerprint(self)
        ):
            raise ValueError("NSE_SESSION_IDENTITY_POLICY_APPROVAL_INVALID")


@dataclass(frozen=True, slots=True)
class NseSessionIdentityPolicyActivation:
    selection_id: str
    approval_id: str
    approval_fingerprint: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    activated_by: str
    activated_at: datetime
    state: NseSessionIdentityActivationState
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _id(self.selection_id)
            or not _id(self.approval_id)
            or not _fingerprint(self.approval_fingerprint)
            or self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or not _fingerprint(self.policy_fingerprint)
            or not self.activated_by.startswith("human:")
            or not _aware(self.activated_at)
            or self.state is not NseSessionIdentityActivationState.ACTIVE
            or self.fingerprint != nse_session_identity_policy_activation_fingerprint(self)
        ):
            raise ValueError("NSE_SESSION_IDENTITY_POLICY_ACTIVATION_INVALID")


@dataclass(frozen=True, slots=True)
class NseSessionPointIdentity:
    receipt_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    approval_id: str
    activation_id: str
    session_date: date
    semantic: NseSessionIdentitySemantic
    source_snapshot_id: str
    source_snapshot_fingerprint: str
    source_row_id: str
    source_row_fingerprint: str
    exchange: str
    symbol: str
    isin: str
    series: str | None
    security_code: str
    security_name: str
    normal_market_status_raw: str | None
    security_type_raw: str | None
    financial_instrument_type_raw: str | None
    historical_known_at: None
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not _id(self.receipt_id)
            or self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or not _fingerprint(self.policy_fingerprint)
            or not _id(self.approval_id)
            or not _id(self.activation_id)
            or not _date(self.session_date)
            or self.semantic is not NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D
            or not all((self.source_snapshot_id.startswith("nse-mii-security-master:"), _fingerprint(self.source_snapshot_fingerprint), self.source_row_id.startswith("nse-mii-security-row:"), _fingerprint(self.source_row_fingerprint)))
            or self.exchange != "NSE"
            or not all((self.symbol, self.isin, self.security_code, self.security_name))
            or self.historical_known_at is not None
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.fingerprint != nse_session_point_identity_fingerprint(self)
        ):
            raise ValueError("NSE_SESSION_POINT_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class NseSessionIdentityActivationReceipt:
    session_date: date
    source_rows: int
    receipts_inserted: int
    receipts_already_present: int
    rejected_rows: int
    conflicts: int
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _date(self.session_date)
            or min(self.source_rows, self.receipts_inserted, self.receipts_already_present, self.rejected_rows, self.conflicts) < 0
            or self.source_rows != self.receipts_inserted + self.receipts_already_present + self.conflicts
            or not _fingerprint(self.fingerprint)
            or self.fingerprint != nse_session_identity_activation_receipt_fingerprint(self)
        ):
            raise ValueError("NSE_SESSION_IDENTITY_ACTIVATION_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseSessionIdentityResolution:
    session_date: date
    symbol: str
    isin: str
    status: NseSessionIdentityResolutionStatus
    reasons: tuple[NseSessionIdentityResolutionReason, ...]
    receipt: NseSessionPointIdentity | None
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _date(self.session_date)
            or not self.symbol
            or not self.isin
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value))
            or not all(isinstance(value, NseSessionIdentityResolutionReason) for value in self.reasons)
        ):
            raise ValueError("NSE_SESSION_IDENTITY_RESOLUTION_INVALID")
        if self.status is NseSessionIdentityResolutionStatus.SESSION_IDENTITY_PRESENT:
            if self.receipt is None or self.reasons or self.receipt.session_date != self.session_date or (self.receipt.symbol, self.receipt.isin) != (self.symbol, self.isin):
                raise ValueError("NSE_SESSION_IDENTITY_RESOLUTION_PRESENT_INVALID")
        elif self.receipt is not None or len(self.reasons) != 1:
            raise ValueError("NSE_SESSION_IDENTITY_RESOLUTION_UNAVAILABLE_INVALID")
        if self.fingerprint != nse_session_identity_resolution_fingerprint(self):
            raise ValueError("NSE_SESSION_IDENTITY_RESOLUTION_FINGERPRINT_MISMATCH")


def approve_nse_session_identity_policy(*, approval_id: str, approved_by: str, approved_at: datetime) -> NseSessionIdentityPolicyApproval:
    proposal = create_proposed_nse_mii_session_knownness_policy()
    values = dict(
        approval_id=approval_id, policy_id=POLICY_ID, policy_version=POLICY_VERSION,
        proposal_policy_id=proposal.policy_id, proposal_policy_version=proposal.version,
        proposal_fingerprint=proposal.fingerprint,
        approved_semantics=(NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D,),
        approved_by=approved_by, approved_at=_utc(approved_at), state=NseSessionIdentityApprovalState.APPROVED,
    )
    return NseSessionIdentityPolicyApproval(**values, fingerprint=_digest(values))


def activate_nse_session_identity_policy(*, selection_id: str, approval: NseSessionIdentityPolicyApproval, activated_by: str, activated_at: datetime) -> NseSessionIdentityPolicyActivation:
    values = dict(
        selection_id=selection_id, approval_id=approval.approval_id, approval_fingerprint=approval.fingerprint,
        policy_id=approval.policy_id,
        policy_version=approval.policy_version, policy_fingerprint=approval.fingerprint,
        activated_by=activated_by, activated_at=_utc(activated_at), state=NseSessionIdentityActivationState.ACTIVE,
    )
    if values["activated_at"] < approval.approved_at:
        raise ValueError("NSE_SESSION_IDENTITY_ACTIVATION_PRECEDES_APPROVAL")
    return NseSessionIdentityPolicyActivation(**values, fingerprint=_digest(values))


def session_point_identity_from_row(*, activation: NseSessionIdentityPolicyActivation, snapshot: NseMiiSecurityMasterSnapshot, row: NseMiiSecurityMasterRow) -> NseSessionPointIdentity:
    _validate_active_activation(activation)
    _validate_source_binding(snapshot, row)
    identity = _receipt_identity(activation, snapshot, row)
    values = identity | dict(
        semantic=NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D,
        source_snapshot_fingerprint=snapshot.fingerprint, source_row_fingerprint=row.fingerprint,
        exchange="NSE", symbol=row.symbol, isin=row.isin, series=row.series,
        security_code=row.security_code, security_name=row.security_name,
        normal_market_status_raw=row.normal_market_status_raw, security_type_raw=row.security_type_raw,
        financial_instrument_type_raw=row.financial_instrument_type_raw, historical_known_at=None,
    )
    receipt_id = "nse-session-identity:" + _digest(identity).removeprefix("sha256:")[:32]
    return NseSessionPointIdentity(receipt_id=receipt_id, **values, fingerprint=_digest(values | {
        "receipt_id": receipt_id, "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }))


def resolve_nse_session_identity(
    receipts: Iterable[NseSessionPointIdentity], *, session_date: date, symbol: str, isin: str,
) -> NseSessionIdentityResolution:
    if not _date(session_date) or not symbol or not isin:
        raise ValueError("NSE_SESSION_IDENTITY_SELECTOR_INPUT_INVALID")
    exact = tuple(value for value in receipts if value.symbol == symbol and value.isin == isin)
    current = tuple(value for value in exact if value.session_date == session_date)
    if len(current) == 1:
        return _resolution(session_date, symbol, isin, NseSessionIdentityResolutionStatus.SESSION_IDENTITY_PRESENT, (), current[0])
    if len(current) > 1:
        return _resolution(session_date, symbol, isin, NseSessionIdentityResolutionStatus.EVIDENCE_CONFLICTED,
                           (NseSessionIdentityResolutionReason.AMBIGUOUS_EXACT_SESSION_POINT_IDENTITY,), None)
    if any(value.session_date > session_date for value in exact):
        return _resolution(session_date, symbol, isin, NseSessionIdentityResolutionStatus.FUTURE_SESSION_RECEIPT_EXCLUDED,
                           (NseSessionIdentityResolutionReason.FUTURE_SESSION_POINT_RECEIPT_EXCLUDED,), None)
    if any(value.session_date < session_date for value in exact):
        return _resolution(session_date, symbol, isin, NseSessionIdentityResolutionStatus.LATER_SESSION_REQUIRES_OWN_RECEIPT,
                           (NseSessionIdentityResolutionReason.LATER_SESSION_POINT_RECEIPT_REQUIRED,), None)
    return _resolution(session_date, symbol, isin, NseSessionIdentityResolutionStatus.RECEIPT_UNAVAILABLE,
                       (NseSessionIdentityResolutionReason.SESSION_POINT_RECEIPT_REQUIRED,), None)


class NseSessionPointIdentityStore:
    """Append-only governance and session-point receipts in the existing store."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_approval(self, value: NseSessionIdentityPolicyApproval) -> NseSessionIdentityReceiptStatus:
        return self._save("nse-session-policy-approval:" + value.approval_id, "nse-session-identity-policy-approval-v1", value, value.approved_at)

    def approval(self, approval_id: str) -> NseSessionIdentityPolicyApproval | None:
        value = self._repository.get_snapshot("nse-session-policy-approval:" + approval_id)
        return value.payload if value is not None and isinstance(value.payload, NseSessionIdentityPolicyApproval) else None

    def save_activation(self, value: NseSessionIdentityPolicyActivation) -> NseSessionIdentityReceiptStatus:
        return self._save("nse-session-policy-activation:" + value.selection_id, "nse-session-identity-policy-activation-v1", value, value.activated_at)

    def activation(self, selection_id: str) -> NseSessionIdentityPolicyActivation | None:
        value = self._repository.get_snapshot("nse-session-policy-activation:" + selection_id)
        return value.payload if value is not None and isinstance(value.payload, NseSessionIdentityPolicyActivation) else None

    def save_receipt(self, value: NseSessionPointIdentity, *, activated_at: datetime) -> NseSessionIdentityReceiptStatus:
        return self._save(value.receipt_id, "nse-session-point-identity-v1", value, activated_at)

    def receipts(self) -> tuple[NseSessionPointIdentity, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, NseSessionPointIdentity)), key=lambda value: (value.session_date, value.symbol, value.isin, value.receipt_id)))

    def _save(self, snapshot_id: str, record_type: str, value: object, created_at: datetime) -> NseSessionIdentityReceiptStatus:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.payload == value:
                return NseSessionIdentityReceiptStatus.ALREADY_PRESENT
            raise ValueError("NSE_SESSION_IDENTITY_IMMUTABLE_COLLISION")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, CoreApiSnapshotFamily.HISTORICAL_NSE_SESSION_IDENTITY, "v1", record_type,
            getattr(value, "fingerprint"), created_at, value,
        ))
        return NseSessionIdentityReceiptStatus.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_NSE_SESSION_IDENTITY, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


def activate_nse_mii_snapshot(
    store: NseSessionPointIdentityStore, *, activation: NseSessionIdentityPolicyActivation,
    snapshot: NseMiiSecurityMasterSnapshot, rows: Iterable[NseMiiSecurityMasterRow], calendar: NseTradingSessionCalendar,
) -> NseSessionIdentityActivationReceipt:
    """Promote one complete validated source artifact, never an inferred interval."""
    _validate_active_activation(activation)
    if not calendar.is_trading_day(snapshot.report_date):
        raise ValueError("NSE_SESSION_IDENTITY_NON_TRADING_SESSION")
    values = tuple(sorted(rows, key=lambda value: value.row_number))
    if not _source_snapshot_valid(snapshot) or len(values) != snapshot.row_count:
        raise ValueError("NSE_SESSION_IDENTITY_SOURCE_SNAPSHOT_INVALID")
    if any(not _source_row_valid(snapshot, value) for value in values):
        raise ValueError("NSE_SESSION_IDENTITY_SOURCE_ROW_INVALID")
    groups: dict[tuple[str, str, str | None, str], list[NseMiiSecurityMasterRow]] = {}
    for row in values:
        groups.setdefault((row.symbol, row.isin, row.series, row.security_code), []).append(row)
    inserted = present = conflicts = 0
    for key in sorted(groups):
        group = groups[key]
        if len(group) != 1:
            conflicts += len(group)
            continue
        status = store.save_receipt(session_point_identity_from_row(activation=activation, snapshot=snapshot, row=group[0]), activated_at=activation.activated_at)
        inserted += status is NseSessionIdentityReceiptStatus.INSERTED
        present += status is NseSessionIdentityReceiptStatus.ALREADY_PRESENT
    body = dict(
        session_date=snapshot.report_date, source_rows=len(values), receipts_inserted=inserted,
        receipts_already_present=present, rejected_rows=snapshot.rejected_rows, conflicts=conflicts,
    )
    return NseSessionIdentityActivationReceipt(**body, fingerprint=_digest(body))


def activate_stored_nse_mii_snapshot(
    store: NseSessionPointIdentityStore, repository: CoreApiSnapshotRepository, *,
    activation: NseSessionIdentityPolicyActivation, report_date: date, calendar: NseTradingSessionCalendar,
) -> NseSessionIdentityActivationReceipt:
    """Activate one already validated immutable source snapshot by exact date."""
    if not _date(report_date):
        raise ValueError("NSE_SESSION_IDENTITY_REPORT_DATE_INVALID")
    source: list[CoreApiSnapshot] = []
    offset = 0
    while True:
        page = repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_NSE_SECURITY_MASTER_SNAPSHOT, limit=100, offset=offset)
        source.extend(page)
        if len(page) < 100:
            break
        offset += len(page)
    snapshots = tuple(item.payload for item in source if isinstance(item.payload, NseMiiSecurityMasterSnapshot) and item.payload.report_date == report_date)
    if len(snapshots) != 1:
        raise ValueError("NSE_SESSION_IDENTITY_STORED_SNAPSHOT_UNAVAILABLE_OR_AMBIGUOUS")
    snapshot = snapshots[0]
    rows = tuple(item.payload for item in source if isinstance(item.payload, NseMiiSecurityMasterRow) and item.payload.snapshot_id == snapshot.snapshot_id)
    return activate_nse_mii_snapshot(store, activation=activation, snapshot=snapshot, rows=rows, calendar=calendar)


def nse_session_identity_policy_approval_fingerprint(value: NseSessionIdentityPolicyApproval) -> str:
    return _digest({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_session_identity_policy_activation_fingerprint(value: NseSessionIdentityPolicyActivation) -> str:
    return _digest({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_session_point_identity_fingerprint(value: NseSessionPointIdentity) -> str:
    return _digest({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_session_identity_activation_receipt_fingerprint(value: NseSessionIdentityActivationReceipt) -> str:
    return _digest({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_session_identity_resolution_fingerprint(value: NseSessionIdentityResolution) -> str:
    return _digest({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def nse_session_point_identity_payload(value: NseSessionPointIdentity) -> dict[str, object]:
    return {name: _scalar(getattr(value, name)) for name in value.__dataclass_fields__}


def serialize_nse_session_point_identity(value: NseSessionPointIdentity) -> str:
    return json.dumps(nse_session_point_identity_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _resolution(session, symbol, isin, status, reasons, receipt):
    body = dict(session_date=session, symbol=symbol, isin=isin, status=status, reasons=reasons, receipt=receipt)
    return NseSessionIdentityResolution(**body, fingerprint=_digest(body))


def _receipt_identity(activation, snapshot, row):
    return dict(
        policy_id=activation.policy_id, policy_version=activation.policy_version, policy_fingerprint=activation.policy_fingerprint,
        approval_id=activation.approval_id, activation_id=activation.selection_id, session_date=snapshot.report_date,
        source_snapshot_id=snapshot.snapshot_id, source_row_id=row.row_id,
    )


def _validate_active_activation(value: NseSessionIdentityPolicyActivation) -> None:
    if not isinstance(value, NseSessionIdentityPolicyActivation) or value.state is not NseSessionIdentityActivationState.ACTIVE:
        raise ValueError("NSE_SESSION_IDENTITY_ACTIVE_POLICY_REQUIRED")


def _validate_source_binding(snapshot, row) -> None:
    if not _source_snapshot_valid(snapshot) or not _source_row_valid(snapshot, row):
        raise ValueError("NSE_SESSION_IDENTITY_SOURCE_BINDING_INVALID")


def _source_snapshot_valid(value: object) -> bool:
    return isinstance(value, NseMiiSecurityMasterSnapshot) and _date(value.report_date) and (
        value.source_reference == nse_mii_security_master_url(value.report_date)
        and value.expected_filename == value.source_reference.rsplit("/", 1)[-1]
        and value.availability_semantics is NseMiiAvailabilitySemantics.DOCUMENTED_PRE_TRADING_DATE_ONLY
        and value.historical_known_at is None
        and value.contract_id == SOURCE_CONTRACT_ID and value.contract_version == SOURCE_CONTRACT_VERSION
        and _fingerprint(value.raw_file_fingerprint) and _fingerprint(value.schema_fingerprint)
    )


def _source_row_valid(snapshot: NseMiiSecurityMasterSnapshot, value: object) -> bool:
    return isinstance(value, NseMiiSecurityMasterRow) and (
        value.snapshot_id == snapshot.snapshot_id and value.report_date == snapshot.report_date
        and value.historical_known_at is None and value.contract_id == SOURCE_CONTRACT_ID
        and value.contract_version == SOURCE_CONTRACT_VERSION and _fingerprint(value.raw_row_fingerprint)
    )


def _digest(values: dict[str, object]) -> str:
    return "sha256:" + manifest_fingerprint(**{key: _scalar(value) for key, value in values.items()})


def _scalar(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_scalar(item) for item in value)
    if isinstance(value, NseSessionPointIdentity):
        return nse_session_point_identity_payload(value)
    return value


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise ValueError("NSE_SESSION_IDENTITY_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "NseSessionIdentityActivationReceipt", "NseSessionIdentityActivationState",
    "NseSessionIdentityPolicyActivation", "NseSessionIdentityPolicyApproval",
    "NseSessionIdentityApprovalState", "NseSessionIdentityReceiptStatus",
    "NseSessionIdentityResolution", "NseSessionIdentityResolutionReason",
    "NseSessionIdentityResolutionStatus", "NseSessionIdentitySemantic",
    "NseSessionPointIdentity", "NseSessionPointIdentityStore",
    "activate_nse_mii_snapshot", "activate_nse_session_identity_policy",
    "approve_nse_session_identity_policy", "nse_session_point_identity_payload",
    "resolve_nse_session_identity", "serialize_nse_session_point_identity",
)
