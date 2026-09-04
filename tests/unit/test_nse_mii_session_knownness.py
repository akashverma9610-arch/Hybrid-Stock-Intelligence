from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
import gzip

import pytest

from app.gates.engine import ExchangeCalendar
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterHttpResponse, extract_nse_mii_security_master, nse_mii_security_master_url,
)
from app.historical.nse_mii_session_knownness import (
    NseMiiSessionKnownnessActivationState, NseMiiSessionKnownnessApprovalState,
    NseMiiSessionKnownnessPolicyState, NseMiiSessionKnownnessReason, NseMiiSessionKnownnessStatus,
    create_proposed_nse_mii_session_knownness_policy, evaluate_nse_mii_session_knownness,
    nse_mii_session_knownness_payload, serialize_nse_mii_session_knownness,
)


D = date(2025, 12, 29)
T = datetime(2026, 9, 4, 6, tzinfo=UTC)
CALENDAR = ExchangeCalendar("NSE", frozenset())
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


def _extraction(*, report_date: date = D, rows: tuple[str, ...] = ("100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",)):
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        report_date, nse_mii_security_master_url(report_date), "application/x-gzip",
        gzip.compress((HEADERS + "\n".join(rows) + "\n").encode()), T,
    ))


def _evaluate(*, extraction=None, row=None, rows=None, session=D):
    extraction = extraction or _extraction()
    return evaluate_nse_mii_session_knownness(
        create_proposed_nse_mii_session_knownness_policy(), snapshot=extraction.snapshot,
        row=extraction.rows[0] if row is None else row,
        snapshot_rows=extraction.rows if rows is None else rows,
        evaluation_session=session, calendar=CALENDAR,
    )


def test_proposed_policy_is_immutable_not_approved_not_active_and_fingerprinted():
    policy = create_proposed_nse_mii_session_knownness_policy()
    assert policy.state is NseMiiSessionKnownnessPolicyState.PROPOSED
    assert policy.approval_state is NseMiiSessionKnownnessApprovalState.NOT_APPROVED
    assert policy.activation_state is NseMiiSessionKnownnessActivationState.NOT_ACTIVE
    assert policy.fingerprint.startswith("sha256:")
    with pytest.raises((AttributeError, TypeError)):
        policy.version = "active"  # type: ignore[misc]
    with pytest.raises(ValueError, match="POLICY_INVALID"):
        replace(policy, fingerprint="sha256:" + "0" * 64)


def test_exact_validated_row_is_descriptive_session_identity_presence_only():
    result = _evaluate()
    assert result.status is NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT
    assert result.session_identity_present and (result.exchange, result.symbol, result.isin, result.series) == ("NSE", "EXACT", "INE000A01001", "EQ")
    assert result.historical_known_at is None
    assert not hasattr(result, "listed_from") and not hasattr(result, "delisted") and not hasattr(result, "canonical_instrument_id")


def test_earlier_and_later_sessions_never_substitute_a_same_date_snapshot():
    prior = _evaluate(session=date(2025, 12, 26))
    later = _evaluate(session=date(2025, 12, 30))
    assert prior.status is NseMiiSessionKnownnessStatus.FUTURE_SNAPSHOT
    assert NseMiiSessionKnownnessReason.FUTURE_SNAPSHOT_EXCLUDED in prior.reasons
    assert later.status is NseMiiSessionKnownnessStatus.WRONG_SESSION
    assert NseMiiSessionKnownnessReason.LATER_SESSION_REQUIRES_OWN_SNAPSHOT in later.reasons


def test_non_trading_session_is_not_applicable_and_never_known():
    result = _evaluate(session=date(2025, 12, 28))
    assert result.status is NseMiiSessionKnownnessStatus.NOT_APPLICABLE
    assert result.reasons == (NseMiiSessionKnownnessReason.EVALUATION_SESSION_NOT_TRADING_DAY,)


def test_missing_snapshot_row_and_invalid_binding_fail_closed():
    policy = create_proposed_nse_mii_session_knownness_policy()
    missing = evaluate_nse_mii_session_knownness(policy, snapshot=None, row=None, evaluation_session=D, calendar=CALENDAR)
    assert missing.status is NseMiiSessionKnownnessStatus.SNAPSHOT_UNAVAILABLE
    extraction = _extraction()
    broken = replace(extraction.rows[0], snapshot_id="nse-mii-security-master:other")
    result = _evaluate(extraction=extraction, row=broken, rows=(broken,))
    assert result.status is NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE
    assert result.reasons == (NseMiiSessionKnownnessReason.ROW_SNAPSHOT_BINDING_INVALID,)


def test_filename_source_date_mismatch_and_future_snapshot_fail_closed():
    extraction = _extraction()
    invalid = extraction.snapshot
    object.__setattr__(invalid, "expected_filename", "NSE_CM_security_30012025.csv.gz")
    result = _evaluate(extraction=replace(extraction, snapshot=invalid), row=extraction.rows[0], rows=extraction.rows)
    assert result.status is NseMiiSessionKnownnessStatus.INVALID_SOURCE_DATE
    assert result.reasons == (NseMiiSessionKnownnessReason.SNAPSHOT_FILENAME_DATE_MISMATCH,)
    future = _extraction(report_date=date(2026, 8, 20))
    assert _evaluate(extraction=future, session=D).status is NseMiiSessionKnownnessStatus.FUTURE_SNAPSHOT


def test_duplicate_exact_row_is_ambiguous_but_same_isin_changed_symbol_is_descriptive_only():
    extraction = _extraction(rows=(
        "100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",
        "100,EXACT,EQ,Exact Ltd,INE000A01001,7,100,0,EQ,EQUITY",
    ))
    assert _evaluate(extraction=extraction).status is NseMiiSessionKnownnessStatus.AMBIGUOUS_CONFLICTED_ROW
    changed = _extraction(rows=(
        "100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",
        "101,RENAMED,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY",
    ))
    assert _evaluate(extraction=changed).status is NseMiiSessionKnownnessStatus.SESSION_IDENTITY_PRESENT


def test_row_report_date_mismatch_and_reason_status_tampering_are_rejected():
    extraction = _extraction()
    mismatched = replace(extraction.rows[0], report_date=date(2025, 12, 30))
    result = _evaluate(extraction=extraction, row=mismatched, rows=(mismatched,))
    assert result.reasons == (NseMiiSessionKnownnessReason.SNAPSHOT_REPORT_DATE_MISMATCH,)
    with pytest.raises(ValueError, match="REASON_STATUS_CONTRADICTION"):
        replace(_evaluate(), status=NseMiiSessionKnownnessStatus.WRONG_SESSION,
                reasons=(NseMiiSessionKnownnessReason.FUTURE_SNAPSHOT_EXCLUDED,),
                session_identity_present=False, snapshot_id=None, snapshot_fingerprint=None,
                row_id=None, row_fingerprint=None, exchange=None, symbol=None, isin=None,
                series=None, security_code=None, security_name=None, normal_market_status_raw=None,
                security_type_raw=None, financial_instrument_type_raw=None)


def test_changed_isin_never_creates_continuity_and_absence_never_creates_delisting():
    first, second = _extraction(), _extraction(rows=("100,EXACT,EQ,Exact Ltd,INE000A01002,6,100,0,EQ,EQUITY",))
    assert _evaluate(extraction=first).isin != _evaluate(extraction=second).isin
    assert not hasattr(_evaluate(extraction=second), "predecessor")
    assert not hasattr(_evaluate(extraction=second), "listing_end")


def test_serialization_fingerprint_and_repeated_evaluation_are_deterministic():
    one, two = _evaluate(), _evaluate()
    assert one == two and one.fingerprint == two.fingerprint
    payload = nse_mii_session_knownness_payload(one)
    assert payload["evaluation_session"] == D.isoformat() and payload["historical_known_at"] is None
    assert serialize_nse_mii_session_knownness(one) == serialize_nse_mii_session_knownness(two)
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        replace(one, symbol="TAMPERED")


def test_static_boundaries_exclude_identity_promotion_company_type_backtest_and_execution():
    import app.historical.nse_mii_session_knownness as module
    source = open(module.__file__, encoding="utf-8").read()
    for forbidden in (
        "app.historical.security_master", "app.portfolio", "app.broker", "app.orders", "app.api",
        "app.runtime", "sqlite3", "Compounder", "company_type", "place_order", "listed_from",
    ):
        assert forbidden not in source
