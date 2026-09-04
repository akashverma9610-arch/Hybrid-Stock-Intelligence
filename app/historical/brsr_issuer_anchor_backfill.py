"""Immutable BRSR-to-same-session-NSE-MII anchor-readiness evidence.

This module joins only two supplied exact primary artifacts: an already
immutable NSE BRSR CIN+symbol filing receipt and an exact date-labelled NSE
MII security-master extraction.  It creates research anchor evidence, never an
active issuer bridge or continuity result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable

from app.historical.issuer_identifier_acquisition import (
    ExactIssuerIdentifierEvidence,
    IssuerIdentifierEvidenceSource,
)
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterExtraction,
    NseMiiSecurityMasterRow,
    NseMiiSecurityMasterSnapshot,
    nse_mii_security_master_url,
)
from app.historical.nse_mii_session_knownness import NseTradingSessionCalendar
from app.historical.nse_session_identity import NseSessionPointIdentity
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "brsr-issuer-anchor-session-master-backfill"
CONTRACT_VERSION = "v2"
LEGACY_CONTRACT_VERSION = "v1"
POLICY_ID = "isin-issuer-bridge-continuity-policy"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_CIN = re.compile(r"[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\Z")
_ISIN = re.compile(r"[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class BrsrIssuerAnchorError(ValueError):
    """Stable fail-closed error at the immutable anchor-evidence boundary."""


class BrsrIssuerAnchorStatus(StrEnum):
    ISSUER_ANCHOR_READY = "ISSUER_ANCHOR_READY"
    ANCHOR_SESSION_UNAVAILABLE = "ANCHOR_SESSION_UNAVAILABLE"
    ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING = "ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class BrsrIssuerAnchorReason(StrEnum):
    CANONICAL_TRADING_SESSION_REQUIRED = "CANONICAL_TRADING_SESSION_REQUIRED"
    EXACT_SESSION_SNAPSHOT_REQUIRED = "EXACT_SESSION_SNAPSHOT_REQUIRED"
    EXACT_SYMBOL_SESSION_ROW_REQUIRED = "EXACT_SYMBOL_SESSION_ROW_REQUIRED"
    AMBIGUOUS_EXACT_SYMBOL_SESSION_IDENTITY = "AMBIGUOUS_EXACT_SYMBOL_SESSION_IDENTITY"
    CONFLICTING_EXACT_ISIN_CIN_ANCHOR = "CONFLICTING_EXACT_ISIN_CIN_ANCHOR"


class BrsrAnchorSessionStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    REPORT_UNAVAILABLE = "REPORT_UNAVAILABLE"
    NON_TRADING_SESSION = "NON_TRADING_SESSION"
    SOURCE_INVALID = "SOURCE_INVALID"


class BrsrAnchorWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class ForwardIsinPotentialStatus(StrEnum):
    SAME_ISIN_SAME_SYMBOL_POTENTIAL = "SAME_ISIN_SAME_SYMBOL_POTENTIAL"
    SAME_ISIN_CHANGED_SYMBOL_POTENTIAL = "SAME_ISIN_CHANGED_SYMBOL_POTENTIAL"
    ISIN_NOT_PRESENT = "ISIN_NOT_PRESENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


@dataclass(frozen=True, slots=True)
class BrsrAnchorMiiRowEvidence:
    """One exact MII row retained when an anchor assessment needs source proof."""

    mii_row_id: str
    mii_row_source_fingerprint: str
    isin: str
    series: str | None
    normal_market_status_raw: str | None
    security_type_raw: str | None
    financial_instrument_type_raw: str | None

    def __post_init__(self) -> None:
        if not (
            _identifier(self.mii_row_id)
            and _fingerprint(self.mii_row_source_fingerprint)
            and _ISIN.fullmatch(self.isin) is not None
            and all(item is None or _nonblank(item) for item in (
                self.series,
                self.normal_market_status_raw,
                self.security_type_raw,
                self.financial_instrument_type_raw,
            ))
        ):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_MII_ROW_EVIDENCE_INVALID")


@dataclass(frozen=True, slots=True)
class BrsrIssuerAnchorReady:
    """One exact, non-active anchor candidate with complete source lineage."""

    anchor_id: str
    brsr_evidence_id: str
    brsr_evidence_fingerprint: str
    symbol: str
    cin: str
    anchor_known_at: datetime
    session_date: date
    mii_source_reference: str
    mii_snapshot_id: str
    mii_raw_file_fingerprint: str
    mii_schema_fingerprint: str
    mii_rows: tuple[BrsrAnchorMiiRowEvidence, ...]
    isin: str
    policy_id: str
    policy_version: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        _validate_anchor(self)
        if self.anchor_id != _anchor_id(_anchor_identity(self)):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_IDENTITY_MISMATCH")
        if self.fingerprint != _hash(_anchor_payload(self)):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class BrsrIssuerAnchorAssessment:
    """Pure one-filing assessment; unavailable states create no anchor."""

    assessment_id: str
    brsr_evidence_id: str
    brsr_evidence_fingerprint: str
    symbol: str
    cin: str
    anchor_known_at: datetime
    session_date: date
    mii_source_reference: str | None
    mii_snapshot_id: str | None
    mii_raw_file_fingerprint: str | None
    mii_schema_fingerprint: str | None
    status: BrsrIssuerAnchorStatus
    reasons: tuple[BrsrIssuerAnchorReason, ...]
    anchor: BrsrIssuerAnchorReady | None
    matching_rows: tuple[BrsrAnchorMiiRowEvidence, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not _identifier(self.assessment_id)
            or not _identifier(self.brsr_evidence_id)
            or not _fingerprint(self.brsr_evidence_fingerprint)
            or not _symbol(self.symbol)
            or _CIN.fullmatch(self.cin) is None
            or not _aware(self.anchor_known_at)
            or not isinstance(self.session_date, date)
            or not isinstance(self.status, BrsrIssuerAnchorStatus)
            or self.reasons != tuple(sorted(set(self.reasons), key=lambda item: item.value))
            or not all(isinstance(item, BrsrIssuerAnchorReason) for item in self.reasons)
            or self.matching_rows != tuple(sorted(set(self.matching_rows), key=lambda item: item.mii_row_id))
            or len({item.mii_row_id for item in self.matching_rows}) != len(self.matching_rows)
            or self.contract_id != CONTRACT_ID
            or self.contract_version not in {LEGACY_CONTRACT_VERSION, CONTRACT_VERSION}
            or self.assessment_id != _assessment_id(_assessment_identity(self))
            or self.fingerprint != _hash(_assessment_payload(self))
        ):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_INVALID")
        expected = {
            BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY: (True, (), None),
            BrsrIssuerAnchorStatus.ANCHOR_SESSION_UNAVAILABLE: (
                False, (BrsrIssuerAnchorReason.CANONICAL_TRADING_SESSION_REQUIRED,), 0,
            ),
            BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING: (
                False,
                (
                    BrsrIssuerAnchorReason.EXACT_SESSION_SNAPSHOT_REQUIRED,
                    BrsrIssuerAnchorReason.EXACT_SYMBOL_SESSION_ROW_REQUIRED,
                ),
                None,
            ),
            BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED: (
                False,
                (
                    BrsrIssuerAnchorReason.AMBIGUOUS_EXACT_SYMBOL_SESSION_IDENTITY,
                    BrsrIssuerAnchorReason.CONFLICTING_EXACT_ISIN_CIN_ANCHOR,
                ),
                None,
            ),
        }[self.status]
        anchor_required, permitted_reasons, required_rows = expected
        if bool(self.anchor) is not anchor_required:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_STATE_CONTRADICTION")
        if anchor_required and self.reasons:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_STATE_CONTRADICTION")
        if anchor_required and not self.matching_rows:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_ROW_CONTRADICTION")
        if not anchor_required and (len(self.reasons) != 1 or self.reasons[0] not in permitted_reasons):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_STATE_CONTRADICTION")
        source = (
            self.mii_source_reference,
            self.mii_snapshot_id,
            self.mii_raw_file_fingerprint,
            self.mii_schema_fingerprint,
        )
        if any(item is not None for item in source):
            if not (
                all(item is not None for item in source)
                and self.mii_source_reference == nse_mii_security_master_url(self.session_date)
                and _identifier(self.mii_snapshot_id)
                and _fingerprint(self.mii_raw_file_fingerprint)
                and _fingerprint(self.mii_schema_fingerprint)
            ):
                raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_SOURCE_INVALID")
        elif self.matching_rows:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_SOURCE_REQUIRED")
        if required_rows is not None and len(self.matching_rows) != required_rows:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_ROW_CONTRADICTION")
        if self.anchor is not None and (
            self.anchor.brsr_evidence_id != self.brsr_evidence_id
            or self.anchor.brsr_evidence_fingerprint != self.brsr_evidence_fingerprint
            or (self.anchor.symbol, self.anchor.cin, self.anchor.anchor_known_at, self.anchor.session_date)
            != (self.symbol, self.cin, _utc(self.anchor_known_at), self.session_date)
            or (
                self.anchor.mii_source_reference,
                self.anchor.mii_snapshot_id,
                self.anchor.mii_raw_file_fingerprint,
                self.anchor.mii_schema_fingerprint,
            ) != (
                self.mii_source_reference,
                self.mii_snapshot_id,
                self.mii_raw_file_fingerprint,
                self.mii_schema_fingerprint,
            )
            or self.matching_row_ids != tuple(item.mii_row_id for item in self.anchor.mii_rows)
        ):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_ASSESSMENT_LINEAGE_MISMATCH")

    @property
    def matching_row_ids(self) -> tuple[str, ...]:
        return tuple(item.mii_row_id for item in self.matching_rows)

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class BrsrAnchorSessionReceipt:
    """One terminal date checkpoint; it avoids re-downloading the same date."""

    receipt_id: str
    session_date: date
    source_reference: str
    status: BrsrAnchorSessionStatus
    brsr_evidence_count: int
    brsr_evidence_fingerprint: str
    mii_snapshot_id: str | None
    mii_raw_file_fingerprint: str | None
    mii_schema_fingerprint: str | None
    valid_mii_rows: int
    anchor_ready_count: int
    missing_symbol_count: int
    conflicted_count: int
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not _identifier(self.receipt_id)
            or not isinstance(self.session_date, date)
            or self.source_reference != nse_mii_security_master_url(self.session_date)
            or not isinstance(self.status, BrsrAnchorSessionStatus)
            or min(
                self.brsr_evidence_count, self.valid_mii_rows, self.anchor_ready_count,
                self.missing_symbol_count, self.conflicted_count,
            ) < 0
            or not _fingerprint(self.brsr_evidence_fingerprint)
            or self.contract_id != CONTRACT_ID
            or self.contract_version not in {LEGACY_CONTRACT_VERSION, CONTRACT_VERSION}
            or self.fingerprint != _hash(_session_receipt_payload(self))
        ):
            raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_RECEIPT_INVALID")
        mii = (self.mii_snapshot_id, self.mii_raw_file_fingerprint, self.mii_schema_fingerprint)
        if self.status is BrsrAnchorSessionStatus.ACQUIRED:
            if not all(mii) or not all(_fingerprint(value) for value in mii[1:]):
                raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_RECEIPT_SOURCE_REQUIRED")
            if self.anchor_ready_count + self.missing_symbol_count + self.conflicted_count != self.brsr_evidence_count:
                raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_RECEIPT_COUNT_INVALID")
        elif any(value is not None for value in mii) or any((
            self.valid_mii_rows, self.anchor_ready_count, self.missing_symbol_count, self.conflicted_count,
        )):
            raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_RECEIPT_UNAVAILABLE_FIELDS_FORBIDDEN")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class BrsrForwardIsinPotential:
    """Read-only later-session exact-ISIN audit; it never activates continuity."""

    anchor_id: str
    anchor_fingerprint: str
    later_session_date: date
    isin: str
    anchor_symbol: str
    later_symbols: tuple[str, ...]
    status: ForwardIsinPotentialStatus
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if (
            not _identifier(self.anchor_id)
            or not _fingerprint(self.anchor_fingerprint)
            or not isinstance(self.later_session_date, date)
            or _ISIN.fullmatch(self.isin) is None
            or not _symbol(self.anchor_symbol)
            or self.later_symbols != tuple(sorted(set(self.later_symbols)))
            or not all(_symbol(value) for value in self.later_symbols)
            or not isinstance(self.status, ForwardIsinPotentialStatus)
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.fingerprint != _hash(_forward_payload(self))
        ):
            raise BrsrIssuerAnchorError("BRSR_FORWARD_ISIN_POTENTIAL_INVALID")


class BrsrIssuerAnchorEvidenceStore:
    """Append-only anchor evidence/checkpoints in the existing core repository."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_anchor(self, value: BrsrIssuerAnchorReady, *, observed_at: datetime) -> BrsrAnchorWriteOutcome:
        value.verify()
        return self._save(
            value.anchor_id, "brsr-issuer-anchor-ready-v1", value, observed_at,
        )

    def save_assessment(self, value: BrsrIssuerAnchorAssessment, *, observed_at: datetime) -> BrsrAnchorWriteOutcome:
        value.verify()
        return self._save(
            value.assessment_id, "brsr-issuer-anchor-assessment-v1", value, observed_at,
        )

    def save_session_receipt(self, value: BrsrAnchorSessionReceipt, *, observed_at: datetime) -> BrsrAnchorWriteOutcome:
        value.verify()
        return self._save(
            value.receipt_id, "brsr-issuer-anchor-session-receipt-v1", value, observed_at,
        )

    def anchors(self) -> tuple[BrsrIssuerAnchorReady, ...]:
        return tuple(sorted(
            (item.payload for item in self._all() if isinstance(item.payload, BrsrIssuerAnchorReady)),
            key=lambda item: (item.session_date, item.symbol, item.isin, item.anchor_id),
        ))

    def session_receipts(self) -> tuple[BrsrAnchorSessionReceipt, ...]:
        return tuple(sorted(
            (item.payload for item in self._all() if isinstance(item.payload, BrsrAnchorSessionReceipt)),
            key=lambda item: (item.session_date, item.receipt_id),
        ))

    def assessments(self) -> tuple[BrsrIssuerAnchorAssessment, ...]:
        return tuple(sorted(
            (item.payload for item in self._all() if isinstance(item.payload, BrsrIssuerAnchorAssessment)),
            key=lambda item: (item.session_date, item.symbol, item.assessment_id),
        ))

    def _save(self, snapshot_id: str, record_type: str, value: object, observed_at: datetime) -> BrsrAnchorWriteOutcome:
        if not _aware(observed_at):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_OBSERVATION_TIMESTAMP_REQUIRED")
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.HISTORICAL_ISSUER_ANCHOR_EVIDENCE and existing.payload == value:
                return BrsrAnchorWriteOutcome.ALREADY_PRESENT
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_IMMUTABLE_COLLISION")
        self._repository.save_snapshot(CoreApiSnapshot(
            snapshot_id, CoreApiSnapshotFamily.HISTORICAL_ISSUER_ANCHOR_EVIDENCE, "v1",
            record_type, getattr(value, "fingerprint"), _utc(observed_at), value,
        ))
        return BrsrAnchorWriteOutcome.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.HISTORICAL_ISSUER_ANCHOR_EVIDENCE, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


def assess_brsr_issuer_anchor(
    evidence: ExactIssuerIdentifierEvidence,
    *,
    extraction: NseMiiSecurityMasterExtraction | None,
    calendar: NseTradingSessionCalendar,
    existing_anchors: Iterable[BrsrIssuerAnchorReady] = (),
) -> BrsrIssuerAnchorAssessment:
    """Pure exact same-session assessment; no I/O, persistence, or continuity."""

    _validate_brsr_evidence(evidence)
    if not hasattr(calendar, "is_trading_day"):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_CALENDAR_REQUIRED")
    session_date = evidence.source_as_of_date
    values = _assessment_base(evidence, session_date)
    if not calendar.is_trading_day(session_date):
        return _assessment(
            values, BrsrIssuerAnchorStatus.ANCHOR_SESSION_UNAVAILABLE,
            (BrsrIssuerAnchorReason.CANONICAL_TRADING_SESSION_REQUIRED,), None, (),
        )
    if extraction is None or extraction.snapshot.report_date != session_date:
        return _assessment(
            values, BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING,
            (BrsrIssuerAnchorReason.EXACT_SESSION_SNAPSHOT_REQUIRED,), None, (),
        )
    snapshot = extraction.snapshot
    values = _assessment_base(evidence, session_date, snapshot=snapshot)
    rows = tuple(sorted(
        (_mii_row_evidence(row) for row in extraction.rows if row.symbol == evidence.nse_symbol),
        key=lambda item: item.mii_row_id,
    ))
    if not rows:
        return _assessment(
            values, BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING,
            (BrsrIssuerAnchorReason.EXACT_SYMBOL_SESSION_ROW_REQUIRED,), None, (),
        )
    if len({row.isin for row in rows}) != 1:
        return _assessment(
            values, BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED,
            (BrsrIssuerAnchorReason.AMBIGUOUS_EXACT_SYMBOL_SESSION_IDENTITY,), None,
            rows,
        )
    anchor = _anchor_from_exact(evidence, snapshot=snapshot, rows=rows)
    conflicts = tuple(
        item for item in _canonical_anchors(existing_anchors)
        if item.isin == anchor.isin and item.cin != anchor.cin
    )
    if conflicts:
        return _assessment(
            values, BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED,
            (BrsrIssuerAnchorReason.CONFLICTING_EXACT_ISIN_CIN_ANCHOR,), None, rows,
        )
    return _assessment(values, BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY, (), anchor, rows)


def assess_brsr_issuer_anchor_session(
    evidence: Iterable[ExactIssuerIdentifierEvidence],
    *,
    extraction: NseMiiSecurityMasterExtraction | None,
    calendar: NseTradingSessionCalendar,
    existing_anchors: Iterable[BrsrIssuerAnchorReady] = (),
) -> tuple[BrsrIssuerAnchorAssessment, ...]:
    """Assess one exact date group and detect within-batch CIN/ISIN conflicts."""

    supplied = _canonical_brsr_evidence(evidence)
    if not supplied:
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_EVIDENCE_REQUIRED")
    session_dates = {item.source_as_of_date for item in supplied}
    if len(session_dates) != 1:
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_SESSION_GROUP_REQUIRED")
    initial = tuple(
        assess_brsr_issuer_anchor(
            item, extraction=extraction, calendar=calendar, existing_anchors=existing_anchors,
        )
        for item in supplied
    )
    ready = tuple(item.anchor for item in initial if item.anchor is not None)
    conflicts = {
        anchor.anchor_id
        for anchor in ready
        if len({item.cin for item in ready if item.isin == anchor.isin}) > 1
    }
    if not conflicts:
        return initial
    result: list[BrsrIssuerAnchorAssessment] = []
    for item in initial:
        if item.anchor is not None and item.anchor.anchor_id in conflicts:
            result.append(_assessment(
                _assessment_base_from(item), BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED,
                (BrsrIssuerAnchorReason.CONFLICTING_EXACT_ISIN_CIN_ANCHOR,), None, item.matching_rows,
            ))
        else:
            result.append(item)
    return tuple(result)


def create_anchor_session_receipt(
    evidence: Iterable[ExactIssuerIdentifierEvidence],
    *,
    status: BrsrAnchorSessionStatus,
    extraction: NseMiiSecurityMasterExtraction | None = None,
    assessments: Iterable[BrsrIssuerAnchorAssessment] = (),
) -> BrsrAnchorSessionReceipt:
    """Create one deterministic terminal session checkpoint from supplied facts."""

    supplied = _canonical_brsr_evidence(evidence)
    if not supplied:
        raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_EVIDENCE_REQUIRED")
    session_dates = {item.source_as_of_date for item in supplied}
    if len(session_dates) != 1:
        raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_GROUP_REQUIRED")
    session_date = next(iter(session_dates))
    assessment_values = tuple(sorted(assessments, key=lambda item: item.brsr_evidence_id))
    if len({item.brsr_evidence_id for item in assessment_values}) != len(assessment_values):
        raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_ASSESSMENT_DUPLICATE")
    if status is BrsrAnchorSessionStatus.ACQUIRED:
        if extraction is None or extraction.snapshot.report_date != session_date or len(assessment_values) != len(supplied):
            raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_ACQUIRED_LINEAGE_REQUIRED")
        if {item.brsr_evidence_id for item in assessment_values} != {item.evidence_id for item in supplied}:
            raise BrsrIssuerAnchorError("BRSR_ANCHOR_SESSION_ASSESSMENT_LINEAGE_REQUIRED")
        snapshot = extraction.snapshot
        values = dict(
            session_date=session_date, source_reference=snapshot.source_reference, status=status,
            brsr_evidence_count=len(supplied), brsr_evidence_fingerprint=_evidence_group_fingerprint(supplied),
            mii_snapshot_id=snapshot.snapshot_id, mii_raw_file_fingerprint=snapshot.raw_file_fingerprint,
            mii_schema_fingerprint=snapshot.schema_fingerprint, valid_mii_rows=len(extraction.rows),
            anchor_ready_count=sum(item.status is BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY for item in assessment_values),
            missing_symbol_count=sum(item.status is BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING for item in assessment_values),
            conflicted_count=sum(item.status is BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED for item in assessment_values),
        )
    else:
        values = dict(
            session_date=session_date, source_reference=nse_mii_security_master_url(session_date), status=status,
            brsr_evidence_count=len(supplied), brsr_evidence_fingerprint=_evidence_group_fingerprint(supplied),
            mii_snapshot_id=None, mii_raw_file_fingerprint=None, mii_schema_fingerprint=None,
            valid_mii_rows=0, anchor_ready_count=0, missing_symbol_count=0, conflicted_count=0,
        )
    receipt_id = "brsr-anchor-session:" + _hash({
        "session_date": session_date.isoformat(), "source_reference": values["source_reference"],
        "brsr_evidence_fingerprint": values["brsr_evidence_fingerprint"],
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    })[7:39]
    return BrsrAnchorSessionReceipt(
        receipt_id=receipt_id, **values,
        fingerprint=_hash(_session_receipt_payload_from_values(values | {"receipt_id": receipt_id})),
    )


def persist_anchor_session(
    store: BrsrIssuerAnchorEvidenceStore,
    *,
    receipt: BrsrAnchorSessionReceipt,
    assessments: Iterable[BrsrIssuerAnchorAssessment],
    observed_at: datetime,
) -> tuple[int, int, BrsrAnchorWriteOutcome]:
    """Append ready anchors then the terminal session receipt, idempotently."""

    inserted = present = 0
    for assessment in tuple(sorted(assessments, key=lambda item: item.brsr_evidence_id)):
        store.save_assessment(assessment, observed_at=observed_at)
        if assessment.anchor is None:
            continue
        outcome = store.save_anchor(assessment.anchor, observed_at=observed_at)
        inserted += outcome is BrsrAnchorWriteOutcome.INSERTED
        present += outcome is BrsrAnchorWriteOutcome.ALREADY_PRESENT
    return inserted, present, store.save_session_receipt(receipt, observed_at=observed_at)


def audit_forward_isin_potential(
    anchors: Iterable[BrsrIssuerAnchorReady],
    *,
    later_session_date: date,
    later_session_receipts: Iterable[NseSessionPointIdentity],
) -> tuple[BrsrForwardIsinPotential, ...]:
    """Read exact same-ISIN presence only; it does not activate continuity."""

    canonical = _canonical_anchors(anchors)
    later = tuple(
        item for item in later_session_receipts
        if isinstance(item, NseSessionPointIdentity) and item.session_date == later_session_date
    )
    results: list[BrsrForwardIsinPotential] = []
    for anchor in canonical:
        same_isin = tuple(item for item in later if item.isin == anchor.isin)
        cins = {item.cin for item in canonical if item.isin == anchor.isin}
        symbols = tuple(sorted({item.symbol for item in same_isin}))
        if len(cins) > 1:
            status = ForwardIsinPotentialStatus.EVIDENCE_CONFLICTED
        elif not symbols:
            status = ForwardIsinPotentialStatus.ISIN_NOT_PRESENT
        elif anchor.symbol in symbols:
            status = ForwardIsinPotentialStatus.SAME_ISIN_SAME_SYMBOL_POTENTIAL
        else:
            status = ForwardIsinPotentialStatus.SAME_ISIN_CHANGED_SYMBOL_POTENTIAL
        values = dict(
            anchor_id=anchor.anchor_id, anchor_fingerprint=anchor.fingerprint,
            later_session_date=later_session_date, isin=anchor.isin,
            anchor_symbol=anchor.symbol, later_symbols=symbols, status=status,
        )
        results.append(BrsrForwardIsinPotential(**values, fingerprint=_hash(_forward_payload_from_values(values))))
    return tuple(results)


def brsr_anchor_payload(value: BrsrIssuerAnchorReady) -> dict[str, object]:
    value.verify()
    return _anchor_payload(value) | {"fingerprint": value.fingerprint}


def serialize_brsr_issuer_anchor(value: BrsrIssuerAnchorReady) -> str:
    return json.dumps(
        brsr_anchor_payload(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_json_default,
    )


def _anchor_from_exact(
    evidence: ExactIssuerIdentifierEvidence,
    *,
    snapshot: NseMiiSecurityMasterSnapshot,
    rows: tuple[BrsrAnchorMiiRowEvidence, ...],
) -> BrsrIssuerAnchorReady:
    _validate_brsr_evidence(evidence)
    if snapshot.report_date != evidence.source_as_of_date or not rows or len({row.isin for row in rows}) != 1:
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_SESSION_LINEAGE_INVALID")
    values = dict(
        brsr_evidence_id=evidence.evidence_id, brsr_evidence_fingerprint=evidence.fingerprint,
        symbol=evidence.nse_symbol, cin=evidence.issuer_identifier_value,
        anchor_known_at=_utc(evidence.historical_known_at), session_date=snapshot.report_date,
        mii_source_reference=snapshot.source_reference, mii_snapshot_id=snapshot.snapshot_id,
        mii_raw_file_fingerprint=snapshot.raw_file_fingerprint, mii_schema_fingerprint=snapshot.schema_fingerprint,
        mii_rows=rows, isin=rows[0].isin,
        policy_id=POLICY_ID, policy_version=POLICY_VERSION,
    )
    anchor_id = _anchor_id(_anchor_identity_from_values(values))
    return BrsrIssuerAnchorReady(
        anchor_id=anchor_id, **values,
        fingerprint=_hash(_anchor_payload_from_values(values | {"anchor_id": anchor_id})),
    )


def _assessment_base(
    evidence: ExactIssuerIdentifierEvidence,
    session_date: date,
    *,
    snapshot: NseMiiSecurityMasterSnapshot | None = None,
) -> dict[str, object]:
    values: dict[str, object] = dict(
        brsr_evidence_id=evidence.evidence_id, brsr_evidence_fingerprint=evidence.fingerprint,
        symbol=evidence.nse_symbol, cin=evidence.issuer_identifier_value,
        anchor_known_at=_utc(evidence.historical_known_at), session_date=session_date,
        mii_source_reference=None, mii_snapshot_id=None, mii_raw_file_fingerprint=None,
        mii_schema_fingerprint=None,
    )
    if snapshot is not None:
        values.update(
            mii_source_reference=snapshot.source_reference, mii_snapshot_id=snapshot.snapshot_id,
            mii_raw_file_fingerprint=snapshot.raw_file_fingerprint,
            mii_schema_fingerprint=snapshot.schema_fingerprint,
        )
    return values


def _assessment_base_from(value: BrsrIssuerAnchorAssessment) -> dict[str, object]:
    return dict(
        brsr_evidence_id=value.brsr_evidence_id, brsr_evidence_fingerprint=value.brsr_evidence_fingerprint,
        symbol=value.symbol, cin=value.cin, anchor_known_at=value.anchor_known_at, session_date=value.session_date,
        mii_source_reference=value.mii_source_reference, mii_snapshot_id=value.mii_snapshot_id,
        mii_raw_file_fingerprint=value.mii_raw_file_fingerprint,
        mii_schema_fingerprint=value.mii_schema_fingerprint,
    )


def _assessment(
    values: dict[str, object], status: BrsrIssuerAnchorStatus, reasons: tuple[BrsrIssuerAnchorReason, ...],
    anchor: BrsrIssuerAnchorReady | None, matching_rows: tuple[BrsrAnchorMiiRowEvidence, ...],
) -> BrsrIssuerAnchorAssessment:
    body = values | dict(
        status=status, reasons=tuple(sorted(set(reasons), key=lambda item: item.value)),
        anchor=anchor, matching_rows=tuple(sorted(set(matching_rows), key=lambda item: item.mii_row_id)),
    )
    assessment_id = _assessment_id(_assessment_identity_from_values(body))
    body = body | {"assessment_id": assessment_id}
    return BrsrIssuerAnchorAssessment(**body, fingerprint=_hash(_assessment_payload_from_values(body)))


def _mii_row_evidence(value: NseMiiSecurityMasterRow) -> BrsrAnchorMiiRowEvidence:
    return BrsrAnchorMiiRowEvidence(
        mii_row_id=value.row_id,
        mii_row_source_fingerprint=value.raw_row_fingerprint,
        isin=value.isin,
        series=value.series,
        normal_market_status_raw=value.normal_market_status_raw,
        security_type_raw=value.security_type_raw,
        financial_instrument_type_raw=value.financial_instrument_type_raw,
    )


def _validate_anchor(value: BrsrIssuerAnchorReady) -> None:
    if not (
        _identifier(value.anchor_id)
        and _identifier(value.brsr_evidence_id)
        and _fingerprint(value.brsr_evidence_fingerprint)
        and _symbol(value.symbol)
        and _CIN.fullmatch(value.cin) is not None
        and _aware(value.anchor_known_at)
        and isinstance(value.session_date, date)
        and value.mii_source_reference == nse_mii_security_master_url(value.session_date)
        and _identifier(value.mii_snapshot_id)
        and _fingerprint(value.mii_raw_file_fingerprint)
        and _fingerprint(value.mii_schema_fingerprint)
        and value.mii_rows == tuple(sorted(set(value.mii_rows), key=lambda item: item.mii_row_id))
        and len({item.mii_row_id for item in value.mii_rows}) == len(value.mii_rows)
        and value.mii_rows
        and all(item.isin == value.isin for item in value.mii_rows)
        and _ISIN.fullmatch(value.isin) is not None
    ):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_INVALID")
    if (value.policy_id, value.policy_version, value.contract_id, value.contract_version) != (
        POLICY_ID, POLICY_VERSION, CONTRACT_ID, CONTRACT_VERSION,
    ):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_POLICY_INVALID")


def _validate_brsr_evidence(value: object) -> None:
    if not isinstance(value, ExactIssuerIdentifierEvidence):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_EVIDENCE_INVALID")
    value.verify()
    if not (
        value.source is IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE
        and value.issuer_identifier_type is IssuerIdentifierType.CIN
        and value.isin is None
        and value.bse_scrip_code is None
        and _symbol(value.nse_symbol)
        and _CIN.fullmatch(value.issuer_identifier_value) is not None
        and value.historical_known_at is not None
    ):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_EVIDENCE_INVALID")


def _canonical_brsr_evidence(values: Iterable[ExactIssuerIdentifierEvidence]) -> tuple[ExactIssuerIdentifierEvidence, ...]:
    supplied = tuple(values)
    for value in supplied:
        _validate_brsr_evidence(value)
    unique: dict[str, ExactIssuerIdentifierEvidence] = {}
    for value in supplied:
        prior = unique.get(value.evidence_id)
        if prior is not None and prior != value:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_EVIDENCE_CONFLICTED")
        unique[value.evidence_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.evidence_id))


def _canonical_anchors(values: Iterable[BrsrIssuerAnchorReady]) -> tuple[BrsrIssuerAnchorReady, ...]:
    supplied = tuple(values)
    for value in supplied:
        if not isinstance(value, BrsrIssuerAnchorReady):
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_INPUT_INVALID")
        value.verify()
    unique: dict[str, BrsrIssuerAnchorReady] = {}
    for value in supplied:
        prior = unique.get(value.anchor_id)
        if prior is not None and prior != value:
            raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_INPUT_CONFLICTED")
        unique[value.anchor_id] = value
    return tuple(sorted(unique.values(), key=lambda item: item.anchor_id))


def _anchor_id(values: dict[str, object]) -> str:
    return "brsr-issuer-anchor:" + _hash(values)[7:39]


def _anchor_identity(value: BrsrIssuerAnchorReady) -> dict[str, object]:
    return _anchor_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__})


def _anchor_identity_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "policy_id": value["policy_id"], "policy_version": value["policy_version"],
        "brsr_evidence_id": value["brsr_evidence_id"], "brsr_evidence_fingerprint": value["brsr_evidence_fingerprint"],
        "mii_snapshot_id": value["mii_snapshot_id"], "mii_raw_file_fingerprint": value["mii_raw_file_fingerprint"],
        "mii_rows": tuple(_mii_row_payload(item) for item in value["mii_rows"]),
        "session_date": value["session_date"], "symbol": value["symbol"], "cin": value["cin"], "isin": value["isin"],
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }


def _anchor_payload(value: BrsrIssuerAnchorReady) -> dict[str, object]:
    return _anchor_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _anchor_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "anchor_id": value["anchor_id"], **_anchor_identity_from_values(value),
        "anchor_known_at": value["anchor_known_at"], "mii_source_reference": value["mii_source_reference"],
        "mii_schema_fingerprint": value["mii_schema_fingerprint"],
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }


def _assessment_payload(value: BrsrIssuerAnchorAssessment) -> dict[str, object]:
    return _assessment_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _assessment_id(values: dict[str, object]) -> str:
    return "brsr-issuer-anchor-assessment:" + _hash(values)[7:39]


def _assessment_identity(value: BrsrIssuerAnchorAssessment) -> dict[str, object]:
    return _assessment_identity_from_values({name: getattr(value, name) for name in value.__dataclass_fields__})


def _assessment_identity_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "brsr_evidence_id": value["brsr_evidence_id"],
        "brsr_evidence_fingerprint": value["brsr_evidence_fingerprint"],
        "session_date": value["session_date"],
        "mii_snapshot_id": value["mii_snapshot_id"],
        "mii_raw_file_fingerprint": value["mii_raw_file_fingerprint"],
        "status": value["status"],
        "reasons": value["reasons"],
        "matching_rows": tuple(_mii_row_payload(item) for item in value["matching_rows"]),
        "contract_id": value.get("contract_id", CONTRACT_ID),
        "contract_version": value.get("contract_version", CONTRACT_VERSION),
    }


def _mii_row_payload(value: BrsrAnchorMiiRowEvidence) -> dict[str, object]:
    return {
        "mii_row_id": value.mii_row_id,
        "mii_row_source_fingerprint": value.mii_row_source_fingerprint,
        "isin": value.isin,
        "series": value.series,
        "normal_market_status_raw": value.normal_market_status_raw,
        "security_type_raw": value.security_type_raw,
        "financial_instrument_type_raw": value.financial_instrument_type_raw,
    }


def _assessment_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "assessment_id": value["assessment_id"],
        "brsr_evidence_id": value["brsr_evidence_id"], "brsr_evidence_fingerprint": value["brsr_evidence_fingerprint"],
        "symbol": value["symbol"], "cin": value["cin"], "anchor_known_at": value["anchor_known_at"],
        "session_date": value["session_date"], "mii_source_reference": value["mii_source_reference"],
        "mii_snapshot_id": value["mii_snapshot_id"],
        "mii_raw_file_fingerprint": value["mii_raw_file_fingerprint"],
        "mii_schema_fingerprint": value["mii_schema_fingerprint"], "status": value["status"],
        "reasons": value["reasons"], "anchor_fingerprint": value["anchor"].fingerprint if value["anchor"] else None,
        "matching_rows": tuple(_mii_row_payload(item) for item in value["matching_rows"]),
        "contract_id": value.get("contract_id", CONTRACT_ID),
        "contract_version": value.get("contract_version", CONTRACT_VERSION),
    }


def _session_receipt_payload(value: BrsrAnchorSessionReceipt) -> dict[str, object]:
    return _session_receipt_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _session_receipt_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "receipt_id": value["receipt_id"], "session_date": value["session_date"],
        "source_reference": value["source_reference"], "status": value["status"],
        "brsr_evidence_count": value["brsr_evidence_count"], "brsr_evidence_fingerprint": value["brsr_evidence_fingerprint"],
        "mii_snapshot_id": value["mii_snapshot_id"], "mii_raw_file_fingerprint": value["mii_raw_file_fingerprint"],
        "mii_schema_fingerprint": value["mii_schema_fingerprint"], "valid_mii_rows": value["valid_mii_rows"],
        "anchor_ready_count": value["anchor_ready_count"], "missing_symbol_count": value["missing_symbol_count"],
        "conflicted_count": value["conflicted_count"],
        "contract_id": value.get("contract_id", CONTRACT_ID),
        "contract_version": value.get("contract_version", CONTRACT_VERSION),
    }


def _forward_payload(value: BrsrForwardIsinPotential) -> dict[str, object]:
    return _forward_payload_from_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _forward_payload_from_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "anchor_id": value["anchor_id"], "anchor_fingerprint": value["anchor_fingerprint"],
        "later_session_date": value["later_session_date"], "isin": value["isin"],
        "anchor_symbol": value["anchor_symbol"], "later_symbols": value["later_symbols"],
        "status": value["status"], "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
    }


def _evidence_group_fingerprint(values: tuple[ExactIssuerIdentifierEvidence, ...]) -> str:
    return _hash(tuple((item.evidence_id, item.fingerprint) for item in values))


def _hash(value: object) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=_json_default).encode(),
    ).hexdigest()


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    raise TypeError(type(value).__name__)


def _utc(value: datetime | None) -> datetime:
    if not _aware(value):
        raise BrsrIssuerAnchorError("BRSR_ISSUER_ANCHOR_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fingerprint(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _symbol(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip() and " " not in value


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "POLICY_ID", "POLICY_VERSION",
    "BrsrAnchorMiiRowEvidence", "BrsrAnchorSessionReceipt", "BrsrAnchorSessionStatus", "BrsrAnchorWriteOutcome",
    "BrsrForwardIsinPotential", "BrsrIssuerAnchorAssessment", "BrsrIssuerAnchorError",
    "BrsrIssuerAnchorEvidenceStore", "BrsrIssuerAnchorReady", "BrsrIssuerAnchorReason",
    "BrsrIssuerAnchorStatus", "ForwardIsinPotentialStatus", "assess_brsr_issuer_anchor",
    "assess_brsr_issuer_anchor_session", "audit_forward_isin_potential",
    "brsr_anchor_payload", "create_anchor_session_receipt", "persist_anchor_session",
    "serialize_brsr_issuer_anchor",
)
