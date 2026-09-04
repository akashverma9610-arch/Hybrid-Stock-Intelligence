from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
import gzip

import pytest

from app.gates.engine import ExchangeCalendar
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterEvidenceStore, NseMiiSecurityMasterHttpResponse,
    extract_nse_mii_security_master, nse_mii_security_master_url,
)
from app.historical.nse_session_identity import (
    NseSessionIdentityActivationState, NseSessionIdentityReceiptStatus,
    NseSessionIdentityResolutionReason, NseSessionIdentityResolutionStatus,
    NseSessionIdentitySemantic, NseSessionPointIdentityStore,
    activate_nse_mii_snapshot, activate_nse_session_identity_policy,
    activate_stored_nse_mii_snapshot, approve_nse_session_identity_policy,
    resolve_nse_session_identity, serialize_nse_session_point_identity,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


D = date(2025, 12, 29)
T = datetime(2026, 9, 4, 10, tzinfo=UTC)
CALENDAR = ExchangeCalendar("NSE", frozenset())
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


def _extraction(*, report_date=D, rows=("100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",)):
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        report_date, nse_mii_security_master_url(report_date), "application/x-gzip",
        gzip.compress((HEADERS + "\n".join(rows) + "\n").encode()), T,
    ))


def _lineage():
    approval = approve_nse_session_identity_policy(
        approval_id="nse-session-approval-v1", approved_by="human:explicit-user-approval", approved_at=T,
    )
    return approval, activate_nse_session_identity_policy(
        selection_id="nse-session-activation-v1", approval=approval,
        activated_by="human:explicit-user-approval", activated_at=T,
    )


def test_immutable_human_approval_and_active_selection_preserve_proposal_lineage(tmp_path):
    approval, activation = _lineage()
    assert approval.approved_by.startswith("human:") and approval.proposal_policy_id == "nse-security-master-session-knownness-policy"
    assert activation.state is NseSessionIdentityActivationState.ACTIVE
    assert activation.approval_id == approval.approval_id and activation.approval_fingerprint == approval.fingerprint
    with pytest.raises(ValueError, match="APPROVAL_INVALID"):
        replace(approval, proposal_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="ACTIVATION_PRECEDES_APPROVAL"):
        activate_nse_session_identity_policy(selection_id="too-early", approval=approval, activated_by="human:explicit-user-approval", activated_at=T.replace(hour=9))
    store = NseSessionPointIdentityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "governance.sqlite"))
    assert store.save_approval(approval) is NseSessionIdentityReceiptStatus.INSERTED
    assert store.save_activation(activation) is NseSessionIdentityReceiptStatus.INSERTED
    assert store.approval(approval.approval_id) == approval and store.activation(activation.selection_id) == activation
    assert store.save_approval(approval) is NseSessionIdentityReceiptStatus.ALREADY_PRESENT


def test_exact_session_receipt_preserves_identity_and_never_fabricates_a_timestamp(tmp_path):
    _, activation = _lineage(); extraction = _extraction(); store = NseSessionPointIdentityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "identities.sqlite"))
    receipt = activate_nse_mii_snapshot(store, activation=activation, snapshot=extraction.snapshot, rows=extraction.rows, calendar=CALENDAR)
    value = store.receipts()[0]
    assert receipt.receipts_inserted == 1 and value.semantic is NseSessionIdentitySemantic.KNOWN_FOR_SESSION_D
    assert (value.exchange, value.symbol, value.isin, value.series) == ("NSE", "EXACT", "INE000A01001", "EQ")
    assert value.historical_known_at is None and not hasattr(value, "listed_from") and not hasattr(value, "delisted")
    assert serialize_nse_session_point_identity(value) == serialize_nse_session_point_identity(value)


def test_selector_uses_only_the_exact_session_not_earlier_or_later(tmp_path):
    _, activation = _lineage(); extraction = _extraction(); store = NseSessionPointIdentityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "selector.sqlite"))
    activate_nse_mii_snapshot(store, activation=activation, snapshot=extraction.snapshot, rows=extraction.rows, calendar=CALENDAR)
    receipts = store.receipts()
    exact = resolve_nse_session_identity(receipts, session_date=D, symbol="EXACT", isin="INE000A01001")
    prior = resolve_nse_session_identity(receipts, session_date=date(2025, 12, 26), symbol="EXACT", isin="INE000A01001")
    later = resolve_nse_session_identity(receipts, session_date=date(2025, 12, 30), symbol="EXACT", isin="INE000A01001")
    assert exact.status is NseSessionIdentityResolutionStatus.SESSION_IDENTITY_PRESENT
    assert prior.status is NseSessionIdentityResolutionStatus.FUTURE_SESSION_RECEIPT_EXCLUDED
    assert prior.reasons == (NseSessionIdentityResolutionReason.FUTURE_SESSION_POINT_RECEIPT_EXCLUDED,)
    assert later.status is NseSessionIdentityResolutionStatus.LATER_SESSION_REQUIRES_OWN_RECEIPT


def test_replay_is_idempotent_and_exact_duplicate_source_rows_are_conflicted(tmp_path):
    _, activation = _lineage(); extraction = _extraction(); store = NseSessionPointIdentityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "replay.sqlite"))
    first = activate_nse_mii_snapshot(store, activation=activation, snapshot=extraction.snapshot, rows=extraction.rows, calendar=CALENDAR)
    replay = activate_nse_mii_snapshot(store, activation=activation, snapshot=extraction.snapshot, rows=extraction.rows, calendar=CALENDAR)
    assert (first.receipts_inserted, replay.receipts_inserted, replay.receipts_already_present) == (1, 0, 1)
    duplicate = _extraction(rows=(
        "100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",
        "100,EXACT,EQ,Exact Ltd,INE000A01001,7,100,0,EQ,EQUITY",
    ))
    conflicted = activate_nse_mii_snapshot(store, activation=activation, snapshot=duplicate.snapshot, rows=duplicate.rows, calendar=CALENDAR)
    assert conflicted.conflicts == 2 and conflicted.receipts_inserted == 0


def test_stored_source_activation_resumes_and_replays_without_current_master_or_intervals(tmp_path):
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "stored.sqlite"); extraction = _extraction(); NseMiiSecurityMasterEvidenceStore(repository).save(extraction)
    _, activation = _lineage(); store = NseSessionPointIdentityStore(repository)
    first = activate_stored_nse_mii_snapshot(store, repository, activation=activation, report_date=D, calendar=CALENDAR)
    replay = activate_stored_nse_mii_snapshot(store, repository, activation=activation, report_date=D, calendar=CALENDAR)
    assert first.receipts_inserted == 1 and replay.receipts_already_present == 1
    with pytest.raises(ValueError, match="NON_TRADING_SESSION"):
        weekend = _extraction(report_date=date(2025, 12, 28))
        activate_nse_mii_snapshot(store, activation=activation, snapshot=weekend.snapshot, rows=weekend.rows, calendar=CALENDAR)


def test_same_isin_changed_symbol_stays_session_specific_and_changed_isin_is_not_stitched(tmp_path):
    _, activation = _lineage(); store = NseSessionPointIdentityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "changes.sqlite"))
    old = _extraction(report_date=D, rows=("100,OLD,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",))
    new = _extraction(report_date=date(2026, 8, 31), rows=("100,NEW,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",))
    changed = _extraction(report_date=date(2026, 8, 31), rows=("100,OLD,EQ,Exact Ltd,INE000A01002,6,100,0,EQ,EQUITY",))
    activate_nse_mii_snapshot(store, activation=activation, snapshot=old.snapshot, rows=old.rows, calendar=CALENDAR)
    activate_nse_mii_snapshot(store, activation=activation, snapshot=new.snapshot, rows=new.rows, calendar=CALENDAR)
    assert resolve_nse_session_identity(store.receipts(), session_date=D, symbol="OLD", isin="INE000A01001").status is NseSessionIdentityResolutionStatus.SESSION_IDENTITY_PRESENT
    assert resolve_nse_session_identity(store.receipts(), session_date=date(2026, 8, 31), symbol="OLD", isin="INE000A01001").status is NseSessionIdentityResolutionStatus.LATER_SESSION_REQUIRES_OWN_RECEIPT
    assert not hasattr(activate_nse_mii_snapshot(store, activation=activation, snapshot=changed.snapshot, rows=changed.rows, calendar=CALENDAR), "continuity")


def test_static_boundaries_exclude_interval_company_type_backtest_portfolio_and_execution():
    import app.historical.nse_session_identity as module
    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in (
        "app.historical.security_master", "app.portfolio", "app.broker", "app.orders", "app.api",
        "app.runtime", "sqlite3", "Compounder", "company_type", "place_order", "listed_from",
    ):
        assert forbidden not in source
