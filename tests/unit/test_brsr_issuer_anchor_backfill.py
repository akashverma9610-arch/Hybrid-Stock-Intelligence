from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
import gzip
from hashlib import sha256

import pytest

import app.historical.brsr_issuer_anchor_backfill as anchors
from app.historical.issuer_identifier_acquisition import (
    IssuerIdentifierEvidenceSource,
    evidence_from_structured_row,
)
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterHttpResponse,
    extract_nse_mii_security_master,
    nse_mii_security_master_url,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 5, 9, tzinfo=UTC)
D = date(2024, 6, 20)
BRSR_SOURCE = "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip"
HEADERS = (
    "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,"
    "ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"
)


class Calendar:
    def __init__(self, *days: date) -> None:
        self.days = frozenset(days)

    def is_trading_day(self, value: date) -> bool:
        return value in self.days


def _brsr(
    *,
    symbol: str = "DEEPINDS",
    day: date = D,
    at: datetime = datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC),
    cin: str = "L14292GJ2006PLC049371",
    application: str = "45705",
):
    return evidence_from_structured_row(
        source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE,
        source_document=b"official-brsr-general", source_reference=BRSR_SOURCE,
        source_record_id="nse-brsr-application:" + application, source_as_of_date=day,
        source_observed_at=T, historical_known_at=at, isin=None, nse_symbol=symbol,
        issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=cin,
        issuer_legal_name="Display-only legal name",
    )


def _mii(*rows: str, day: date = D):
    body = gzip.compress((HEADERS + "\n".join(rows) + "\n").encode())
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=day, source_reference=nse_mii_security_master_url(day),
        content_type="application/x-gzip", body=body, document_observed_at=T,
    ))


def _row(symbol: str = "DEEPINDS", isin: str = "INE0FHS01024", code: str = "100") -> str:
    return f"{code},{symbol},EQ,Exact Ltd,{isin},6,100,0,EQ,EQUITY"


def _ready(*, evidence=None, extraction=None):
    evidence = evidence or _brsr()
    extraction = extraction or _mii(_row())
    result = anchors.assess_brsr_issuer_anchor(
        evidence, extraction=extraction, calendar=Calendar(evidence.source_as_of_date),
    )
    assert result.status is anchors.BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY
    assert result.anchor is not None
    return result.anchor


def test_exact_same_session_symbol_cin_and_isin_produce_immutable_anchor_ready_receipt():
    evidence = _brsr()
    result = anchors.assess_brsr_issuer_anchor(
        evidence, extraction=_mii(_row()), calendar=Calendar(D),
    )

    assert result.status is anchors.BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY
    assert result.reasons == ()
    anchor = result.anchor
    assert anchor is not None
    assert (anchor.symbol, anchor.cin, anchor.isin) == (
        "DEEPINDS", "L14292GJ2006PLC049371", "INE0FHS01024",
    )
    assert anchor.anchor_known_at == evidence.historical_known_at
    assert anchor.session_date == D
    assert anchor.policy_id == anchors.POLICY_ID and anchor.policy_version == anchors.POLICY_VERSION
    assert anchor.mii_source_reference == nse_mii_security_master_url(D)
    assert len(anchor.mii_rows) == 1
    assert anchor.mii_rows[0].mii_row_source_fingerprint.startswith("sha256:")
    assert "Display-only legal name" not in anchors.serialize_brsr_issuer_anchor(anchor)


def test_missing_or_wrong_date_mii_snapshot_cannot_be_substituted():
    evidence = _brsr()
    for extraction in (None, _mii(_row(), day=date(2024, 6, 21))):
        result = anchors.assess_brsr_issuer_anchor(
            evidence, extraction=extraction, calendar=Calendar(D),
        )
        assert result.status is anchors.BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING
        assert result.reasons == (anchors.BrsrIssuerAnchorReason.EXACT_SESSION_SNAPSHOT_REQUIRED,)
        assert result.anchor is None


def test_non_trading_filing_date_fails_closed_without_previous_or_next_date_substitution():
    weekend = date(2024, 6, 22)
    evidence = _brsr(day=weekend, at=datetime(2024, 6, 22, 10, tzinfo=UTC))
    result = anchors.assess_brsr_issuer_anchor(
        evidence, extraction=_mii(_row(), day=weekend), calendar=Calendar(D),
    )
    assert result.status is anchors.BrsrIssuerAnchorStatus.ANCHOR_SESSION_UNAVAILABLE
    assert result.reasons == (anchors.BrsrIssuerAnchorReason.CANONICAL_TRADING_SESSION_REQUIRED,)
    assert result.anchor is None


def test_exact_symbol_only_is_required_and_multiple_symbol_rows_fail_closed():
    evidence = _brsr()
    absent = anchors.assess_brsr_issuer_anchor(
        evidence, extraction=_mii(_row("OTHER")), calendar=Calendar(D),
    )
    assert absent.status is anchors.BrsrIssuerAnchorStatus.ANCHOR_SESSION_SECURITY_EVIDENCE_MISSING
    assert absent.reasons == (anchors.BrsrIssuerAnchorReason.EXACT_SYMBOL_SESSION_ROW_REQUIRED,)
    ambiguous = anchors.assess_brsr_issuer_anchor(
        evidence,
        extraction=_mii(_row("DEEPINDS", "INE0FHS01024", "100"), _row("DEEPINDS", "INE000A01001", "101")),
        calendar=Calendar(D),
    )
    assert ambiguous.status is anchors.BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED
    assert ambiguous.reasons == (anchors.BrsrIssuerAnchorReason.AMBIGUOUS_EXACT_SYMBOL_SESSION_IDENTITY,)
    assert len(ambiguous.matching_rows) == 2
    assert {item.isin for item in ambiguous.matching_rows} == {"INE0FHS01024", "INE000A01001"}
    assert all(item.mii_row_source_fingerprint.startswith("sha256:") for item in ambiguous.matching_rows)


def test_multiple_exact_symbol_rows_with_one_exact_isin_retain_all_source_rows_and_are_anchor_ready():
    evidence = _brsr()
    result = anchors.assess_brsr_issuer_anchor(
        evidence,
        extraction=_mii(
            _row("DEEPINDS", "INE0FHS01024", "100"),
            _row("DEEPINDS", "INE0FHS01024", "101"),
        ),
        calendar=Calendar(D),
    )
    assert result.status is anchors.BrsrIssuerAnchorStatus.ISSUER_ANCHOR_READY
    assert result.anchor is not None
    assert result.anchor.isin == "INE0FHS01024"
    assert len(result.matching_rows) == len(result.anchor.mii_rows) == 2
    assert result.matching_row_ids == tuple(item.mii_row_id for item in result.anchor.mii_rows)


def test_anchor_known_time_is_exact_brsr_timestamp_not_mii_observation_or_session_start():
    known = datetime(2024, 6, 20, 17, 45, 27, tzinfo=UTC)
    anchor = _ready(evidence=_brsr(at=known))
    assert anchor.anchor_known_at == known
    assert anchor.anchor_known_at != T
    assert anchor.anchor_known_at.tzinfo is UTC


def test_same_isin_with_conflicting_cin_fails_closed_and_retains_no_anchor():
    first = _ready()
    conflicting = _brsr(cin="L91110GJ1989PLC012802", application="52562")
    result = anchors.assess_brsr_issuer_anchor(
        conflicting, extraction=_mii(_row()), calendar=Calendar(D), existing_anchors=(first,),
    )
    assert result.status is anchors.BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED
    assert result.reasons == (anchors.BrsrIssuerAnchorReason.CONFLICTING_EXACT_ISIN_CIN_ANCHOR,)
    assert result.anchor is None


def test_same_session_batch_detects_conflicting_cins_for_one_isin_deterministically():
    left, right = _brsr(application="45705"), _brsr(cin="L91110GJ1989PLC012802", application="52562")
    values = anchors.assess_brsr_issuer_anchor_session(
        (right, left), extraction=_mii(_row()), calendar=Calendar(D),
    )
    assert all(value.status is anchors.BrsrIssuerAnchorStatus.EVIDENCE_CONFLICTED for value in values)
    assert all(value.reasons == (anchors.BrsrIssuerAnchorReason.CONFLICTING_EXACT_ISIN_CIN_ANCHOR,) for value in values)


def test_anchor_and_terminal_session_receipts_are_append_only_idempotent_and_reopen(tmp_path):
    evidence = _brsr()
    assessment = anchors.assess_brsr_issuer_anchor(evidence, extraction=_mii(_row()), calendar=Calendar(D))
    receipt = anchors.create_anchor_session_receipt(
        (evidence,), status=anchors.BrsrAnchorSessionStatus.ACQUIRED,
        extraction=_mii(_row()), assessments=(assessment,),
    )
    path = tmp_path / "anchor.sqlite"
    store = anchors.BrsrIssuerAnchorEvidenceStore(SQLiteCoreApiSnapshotRepository(path))
    first = anchors.persist_anchor_session(store, receipt=receipt, assessments=(assessment,), observed_at=T)
    replay = anchors.persist_anchor_session(store, receipt=receipt, assessments=(assessment,), observed_at=T)
    assert first == (1, 0, anchors.BrsrAnchorWriteOutcome.INSERTED)
    assert replay == (0, 1, anchors.BrsrAnchorWriteOutcome.ALREADY_PRESENT)
    assert len(store.anchors()) == 1 and len(store.assessments()) == 1 and len(store.session_receipts()) == 1
    assert store.anchors()[0].isin == "INE0FHS01024"
    store._repository.close()
    reopened = anchors.BrsrIssuerAnchorEvidenceStore(SQLiteCoreApiSnapshotRepository(path))
    assert len(reopened.anchors()) == 1 and len(reopened.assessments()) == 1 and len(reopened.session_receipts()) == 1
    reopened._repository.close()


def test_terminal_404_and_non_trading_receipts_retain_no_source_or_anchor_fields():
    evidence = _brsr()
    unavailable = anchors.create_anchor_session_receipt(
        (evidence,), status=anchors.BrsrAnchorSessionStatus.REPORT_UNAVAILABLE,
    )
    assert unavailable.mii_snapshot_id is None and unavailable.anchor_ready_count == 0
    non_trading = anchors.create_anchor_session_receipt(
        (evidence,), status=anchors.BrsrAnchorSessionStatus.NON_TRADING_SESSION,
    )
    assert unavailable != non_trading
    assert unavailable.source_reference == nse_mii_security_master_url(D)


def test_forward_same_isin_audit_is_descriptive_only_and_never_infers_from_symbol():
    anchor = _ready()
    later = _mii(_row("DEEPINDS", "INE0FHS01024"), day=date(2026, 8, 31))
    from app.historical.nse_session_identity import (
        activate_nse_session_identity_policy, approve_nse_session_identity_policy, session_point_identity_from_row,
    )

    approval = approve_nse_session_identity_policy(
        approval_id="anchor-forward-approval", approved_by="human:approved", approved_at=T,
    )
    activation = activate_nse_session_identity_policy(
        selection_id="anchor-forward-active", approval=approval, activated_by="human:approved", activated_at=T,
    )
    receipt = session_point_identity_from_row(activation=activation, snapshot=later.snapshot, row=later.rows[0])
    result = anchors.audit_forward_isin_potential(
        (anchor,), later_session_date=date(2026, 8, 31), later_session_receipts=(receipt,),
    )[0]
    assert result.status is anchors.ForwardIsinPotentialStatus.SAME_ISIN_SAME_SYMBOL_POTENTIAL
    changed = _mii(_row("NEWDEEP", "INE0FHS01024"), day=date(2026, 8, 31))
    changed_receipt = session_point_identity_from_row(activation=activation, snapshot=changed.snapshot, row=changed.rows[0])
    changed_result = anchors.audit_forward_isin_potential(
        (anchor,), later_session_date=date(2026, 8, 31), later_session_receipts=(changed_receipt,),
    )[0]
    assert changed_result.status is anchors.ForwardIsinPotentialStatus.SAME_ISIN_CHANGED_SYMBOL_POTENTIAL
    other = _mii(_row("DEEPINDS", "INE000A01001"), day=date(2026, 8, 31))
    other_receipt = session_point_identity_from_row(activation=activation, snapshot=other.snapshot, row=other.rows[0])
    absent = anchors.audit_forward_isin_potential(
        (anchor,), later_session_date=date(2026, 8, 31), later_session_receipts=(other_receipt,),
    )[0]
    assert absent.status is anchors.ForwardIsinPotentialStatus.ISIN_NOT_PRESENT


def test_deterministic_identity_stable_serialization_and_tamper_rejection():
    one, two = _ready(), _ready()
    assert one == two
    assert anchors.serialize_brsr_issuer_anchor(one) == anchors.serialize_brsr_issuer_anchor(two)
    with pytest.raises(anchors.BrsrIssuerAnchorError, match="IDENTITY_MISMATCH"):
        replace(one, cin="L91110GJ1989PLC012802")


def test_static_boundaries_exclude_continuity_activation_company_type_backtest_and_execution():
    source = open(anchors.__file__, encoding="utf-8").read().lower()
    for forbidden in (
        "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "app.intelligence",
        "company_type", "backtest", "compounder", "place_order", "datetime.now", "time.time",
        "buy", "sell", "rotate",
    ):
        assert forbidden not in source
