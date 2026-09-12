from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone
import ast
import inspect
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.gates.official_earnings_schedule_candidate import (
    CandidateVerificationState,
    EarningsScheduleGovernanceError,
    OfficialEarningsScheduleCandidate,
    PurposeClassification,
    ReconciliationState,
    ScheduleEventType,
    ScheduleLifecycleState,
    SchedulePrecision,
    SourceExchange,
    SourceInstrumentIdentifierKind,
    classify_results_purpose,
    make_official_earnings_schedule_candidate,
    reconcile_visible_schedule_candidates,
)


T = datetime(2026, 9, 12, 9, 0, tzinfo=UTC)


def candidate(**updates: object) -> OfficialEarningsScheduleCandidate:
    body: dict[str, object] = {
        "canonical_instrument_id": "NSE:INE372A01015",
        "source_instrument_identifier_kind": SourceInstrumentIdentifierKind.NSE_SYMBOL,
        "source_instrument_identifier": "APARINDS",
        "event_type": ScheduleEventType.FINANCIAL_RESULTS_BOARD_MEETING,
        "declared_purpose": "Consider and approve unaudited financial results for the quarter ended 30 September 2026",
        "purpose_classification": PurposeClassification.QUARTERLY_FINANCIAL_RESULTS,
        "scheduled_date": date(2026, 10, 30),
        "scheduled_time": None,
        "schedule_precision": SchedulePrecision.DATE_ONLY,
        "statement_scope": "STANDALONE_AND_CONSOLIDATED",
        "financial_period_reference": "2026-Q2",
        "source_exchange": SourceExchange.NSE,
        "source_reference": "https://www.nseindia.com/filing/fixture-nse-1",
        "source_filing_identity": "NSE:REG29:fixture-nse-1",
        "source_attachment_reference": "https://www.nseindia.com/attachment/fixture-nse-1.pdf",
        "source_xbrl_reference": "NSE:XBRL:fixture-nse-1",
        "revision_state": ScheduleLifecycleState.ANNOUNCED,
        "revision_of_schedule_id": None,
        "exchange_received_at": T,
        "exchange_disseminated_at": T + timedelta(seconds=1),
        "known_at": T + timedelta(seconds=1),
        "hsi_received_at": T + timedelta(seconds=2),
        "source_fingerprint": content_fingerprint({"source": "fixture-nse-1"}),
    }
    return make_official_earnings_schedule_candidate(**(body | updates))


def bse_candidate(**updates: object) -> OfficialEarningsScheduleCandidate:
    body = {
        "source_instrument_identifier_kind": SourceInstrumentIdentifierKind.BSE_SECURITY_CODE,
        "source_instrument_identifier": "532259",
        "source_exchange": SourceExchange.BSE,
        "source_reference": "https://www.bseindia.com/filing/fixture-bse-1",
        "source_filing_identity": "BSE:REG29:fixture-bse-1",
        "source_attachment_reference": "https://www.bseindia.com/attachment/fixture-bse-1.pdf",
        "source_xbrl_reference": "BSE:XBRL:fixture-bse-1",
        "source_fingerprint": content_fingerprint({"source": "fixture-bse-1"}),
    }
    return candidate(**(body | updates))


def test_primary_exchange_candidate_is_immutable_and_deterministic():
    first, second = candidate(), candidate()
    assert first == second
    assert first.schedule_id.startswith("earnings-schedule:")
    assert first.verification_state is CandidateVerificationState.UNVERIFIED_SOURCE_AUTHORITY
    assert first.to_json() == second.to_json()
    with pytest.raises(FrozenInstanceError):
        first.scheduled_date = date(2026, 10, 31)  # type: ignore[misc]


def test_only_explicit_financial_results_purposes_qualify():
    assert classify_results_purpose(structured_purpose="Quarterly Results", subject=None) is PurposeClassification.QUARTERLY_FINANCIAL_RESULTS
    assert classify_results_purpose(structured_purpose=None, subject="Meeting to consider and approve audited financial results") is PurposeClassification.AUDITED_FINANCIAL_RESULTS
    assert classify_results_purpose(structured_purpose="Dividend", subject=None) is PurposeClassification.NON_QUALIFYING
    assert classify_results_purpose(structured_purpose=None, subject="General Board Meeting") is PurposeClassification.NON_QUALIFYING
    with pytest.raises(EarningsScheduleGovernanceError, match="CANDIDATE_INVALID"):
        candidate(purpose_classification=PurposeClassification.NON_QUALIFYING)


def test_secondary_or_unresolved_identity_claims_cannot_construct_candidate():
    with pytest.raises(EarningsScheduleGovernanceError, match="CANDIDATE_INVALID"):
        candidate(source_authority_class="SECONDARY_MEDIA")
    with pytest.raises(EarningsScheduleGovernanceError, match="IDENTITY_MISMATCH"):
        replace(candidate(), canonical_instrument_id="NSE:UNRESOLVED")


def test_date_only_never_invents_a_time_and_datetime_requires_explicit_clock():
    assert candidate().scheduled_time is None
    timed = candidate(schedule_precision=SchedulePrecision.DATE_TIME, scheduled_time="14:30")
    assert timed.scheduled_time == "14:30"
    with pytest.raises(EarningsScheduleGovernanceError, match="PRECISION_INVALID"):
        candidate(schedule_precision=SchedulePrecision.DATE_ONLY, scheduled_time="14:30")
    with pytest.raises(EarningsScheduleGovernanceError, match="PRECISION_INVALID"):
        candidate(schedule_precision=SchedulePrecision.DATE_TIME, scheduled_time=None)


def test_known_at_is_exchange_dissemination_and_pit_excludes_future_notice():
    future = candidate(exchange_disseminated_at=T + timedelta(days=1), known_at=T + timedelta(days=1),
                       hsi_received_at=T + timedelta(days=1, seconds=1))
    assert not future.visible_at(T)
    receipt = reconcile_visible_schedule_candidates((future,), as_of=T)
    assert receipt.state is ReconciliationState.PIT_NOT_VISIBLE
    assert receipt.source_schedule_ids == ()
    with pytest.raises(EarningsScheduleGovernanceError, match="KNOWN_AT_INVALID"):
        candidate(known_at=T + timedelta(seconds=2))


def test_identical_timezone_representations_serialize_identically():
    local = candidate(exchange_received_at=T.astimezone(timezone(timedelta(hours=5, minutes=30))),
                      exchange_disseminated_at=(T + timedelta(seconds=1)).astimezone(timezone(timedelta(hours=5, minutes=30))),
                      known_at=(T + timedelta(seconds=1)).astimezone(timezone(timedelta(hours=5, minutes=30))),
                      hsi_received_at=(T + timedelta(seconds=2)).astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert local.to_json() == candidate().to_json()


def test_revision_and_cancellation_require_explicit_lineage_without_date_matching():
    original = candidate()
    revision = candidate(
        source_filing_identity="NSE:REG29:fixture-nse-2",
        source_reference="https://www.nseindia.com/filing/fixture-nse-2",
        source_attachment_reference="https://www.nseindia.com/attachment/fixture-nse-2.pdf",
        source_xbrl_reference="NSE:XBRL:fixture-nse-2",
        source_fingerprint=content_fingerprint({"source": "fixture-nse-2"}),
        revision_state=ScheduleLifecycleState.RESCHEDULED,
        revision_of_schedule_id=original.schedule_id,
        scheduled_date=date(2026, 11, 3),
    )
    cancelled = candidate(
        source_filing_identity="NSE:REG29:fixture-nse-3",
        source_reference="https://www.nseindia.com/filing/fixture-nse-3",
        source_attachment_reference="https://www.nseindia.com/attachment/fixture-nse-3.pdf",
        source_xbrl_reference="NSE:XBRL:fixture-nse-3",
        source_fingerprint=content_fingerprint({"source": "fixture-nse-3"}),
        revision_state=ScheduleLifecycleState.CANCELLED,
        revision_of_schedule_id=original.schedule_id,
    )
    assert revision.revision_of_schedule_id == cancelled.revision_of_schedule_id == original.schedule_id
    with pytest.raises(EarningsScheduleGovernanceError, match="REVISION_LINEAGE_UNRESOLVED"):
        candidate(revision_state=ScheduleLifecycleState.REVISED, revision_of_schedule_id=None)


def test_dual_exchange_agreement_retains_both_receipts_and_conflict_fails_closed():
    nse, bse = candidate(), bse_candidate()
    agreed = reconcile_visible_schedule_candidates((nse, bse), as_of=T + timedelta(days=1))
    assert agreed.state is ReconciliationState.DUAL_EXCHANGE_AGREEMENT
    assert agreed.source_exchanges == (SourceExchange.BSE, SourceExchange.NSE)
    conflict = bse_candidate(scheduled_date=date(2026, 10, 31))
    conflicted = reconcile_visible_schedule_candidates((nse, conflict), as_of=T + timedelta(days=1))
    assert conflicted.state is ReconciliationState.EVIDENCE_CONFLICTED
    assert conflicted.reason_code == "EVIDENCE_CONFLICTED"


def test_duplicate_receipts_are_rejected_not_silently_deduplicated():
    value = candidate()
    with pytest.raises(EarningsScheduleGovernanceError, match="DUPLICATE_RECEIPT"):
        reconcile_visible_schedule_candidates((value, value), as_of=T + timedelta(days=1))


def test_identity_and_fingerprint_detect_tampering_and_distinguish_second_meeting():
    first = candidate()
    second = candidate(
        source_filing_identity="NSE:REG29:fixture-nse-second",
        source_reference="https://www.nseindia.com/filing/fixture-nse-second",
        source_attachment_reference="https://www.nseindia.com/attachment/fixture-nse-second.pdf",
        source_xbrl_reference="NSE:XBRL:fixture-nse-second",
        declared_purpose="Consider and approve audited financial results for the year ended 31 March 2026",
        purpose_classification=PurposeClassification.ANNUAL_FINANCIAL_RESULTS,
        source_fingerprint=content_fingerprint({"source": "fixture-nse-second"}),
    )
    assert first.schedule_id != second.schedule_id
    with pytest.raises(EarningsScheduleGovernanceError, match="IDENTITY_MISMATCH"):
        replace(first, declared_purpose="Tampered")
    with pytest.raises(EarningsScheduleGovernanceError, match="FINGERPRINT_MISMATCH"):
        replace(first, source_attachment_reference="https://www.nseindia.com/attachment/tampered.pdf")


def test_inside_blackout_candidate_remains_non_admitted_and_has_no_gate_output():
    value = candidate(scheduled_date=(T + timedelta(days=3)).date())
    assert value.verification_state is CandidateVerificationState.UNVERIFIED_SOURCE_AUTHORITY
    assert not {"earnings_scheduled_at", "earnings_schedule_verified_at", "gate_result"} & set(value.__dataclass_fields__)


def test_candidate_contract_has_no_storage_network_clock_or_execution_dependency():
    import app.gates.official_earnings_schedule_candidate as module
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("sqlite3", "requests", "httpx", "app.api", "app.portfolio", "app.orders", "app.signals")
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    assert "datetime.now" not in source
    forbidden_fields = {"entry_price", "stop_loss", "target_price", "quantity", "allocation", "action", "order"}
    assert not forbidden_fields & set(OfficialEarningsScheduleCandidate.__dataclass_fields__)
