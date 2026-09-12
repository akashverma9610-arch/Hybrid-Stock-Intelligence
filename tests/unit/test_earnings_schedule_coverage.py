"""Focused proofs for non-active earnings-calendar coverage semantics."""
from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.filings.earnings_schedule_coverage import (
    CoverageLineageReference,
    CoverageQueryFilterSemantics,
    CoverageQueryStatus,
    CoverageState,
    EarningsScheduleAbsenceState,
    EarningsScheduleCoverageError,
    EarningsScheduleFreshnessState,
    EarningsScheduleSourceFamily,
    SystemCoverageObservationOrigin,
    make_earnings_schedule_coverage_receipt,
    make_system_coverage_first_observed_receipt,
)
from app.fundamentals.diagnostic_comparability import content_fingerprint


T0 = datetime(2026, 9, 12, 10, tzinfo=UTC)
WINDOW_START, WINDOW_END = date(2026, 9, 14), date(2026, 9, 21)
INSTRUMENT = "NSE:INE372A01015"
RESPONSE = content_fingerprint({"response": "fixture"})


def row(name: str) -> CoverageLineageReference:
    return CoverageLineageReference(f"source-row:{name}", content_fingerprint({"row": name}))


def receipt(**overrides):
    values = {
        "canonical_instrument_id": INSTRUMENT,
        "source_family": EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS,
        "window_start": WINDOW_START,
        "window_end": WINDOW_END,
        "filter_semantics": CoverageQueryFilterSemantics.SOURCE_SCOPE_UNPROVEN,
        "query_status": CoverageQueryStatus.PARTIAL,
        "query_completed_at": T0,
        "response_fingerprints": (RESPONSE,),
    }
    return make_earnings_schedule_coverage_receipt(**(values | overrides))


def complete_no_event(**overrides):
    return receipt(**({
        "filter_semantics": CoverageQueryFilterSemantics.EXACT_INSTRUMENT_AND_DATE_WINDOW,
        "query_status": CoverageQueryStatus.SUCCEEDED,
        "pagination_complete": True,
        "identity_scope_complete": True,
        "revision_scope_complete": True,
    } | overrides))


def test_all_current_source_families_are_explicit_and_no_family_is_a_default_absence_authority():
    assert {item.value for item in EarningsScheduleSourceFamily} == {
        "NSE_EVENT_CALENDAR", "NSE_BOARD_MEETINGS", "NSE_ANNOUNCEMENTS",
        "NSE_PRIOR_INTIMATION_XBRL", "BSE_BOARD_MEETINGS", "BSE_ANNOUNCEMENTS",
    }
    assert receipt().coverage_state is CoverageState.PARTIAL


def test_unproven_scope_or_pagination_can_never_be_complete_or_negative_evidence():
    result = receipt()
    assert result.coverage_state is CoverageState.PARTIAL
    assert result.absence_state is EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW
    assert not result.negative_evidence_candidate and result.gate6_clearance is False
    assert result.freshness_state is EarningsScheduleFreshnessState.UNPROVEN


def test_complete_window_no_event_is_only_a_candidate_negative_evidence_never_clearance():
    result = complete_no_event()
    assert result.coverage_state is CoverageState.COMPLETE
    assert result.absence_state is EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_COMPLETE_WINDOW
    assert result.negative_evidence_candidate and result.gate6_clearance is False
    assert result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"


def test_positive_qualifying_row_remains_distinct_from_any_absence_result():
    result = complete_no_event(qualifying_rows=(row("qualifying"),))
    assert result.coverage_state is CoverageState.COMPLETE
    assert result.absence_state is EarningsScheduleAbsenceState.QUALIFYING_EVENT_FOUND
    assert not result.negative_evidence_candidate and result.gate6_clearance is False


def test_ambiguous_rows_fail_closed_as_conflicted_and_never_clear_a_window():
    result = complete_no_event(ambiguous_rows=(row("ambiguous"),))
    assert result.coverage_state is CoverageState.CONFLICTED
    assert result.absence_state is EarningsScheduleAbsenceState.EVIDENCE_CONFLICTED
    assert not result.negative_evidence_candidate


def test_source_failure_has_its_own_state_without_a_false_no_event_claim():
    result = receipt(query_status=CoverageQueryStatus.FAILED, response_fingerprints=(), source_error_code="HTTP_503")
    assert result.coverage_state is CoverageState.FAILED
    assert result.absence_state is EarningsScheduleAbsenceState.SOURCE_QUERY_FAILED
    assert result.freshness_state is EarningsScheduleFreshnessState.SOURCE_FAILED
    assert not result.negative_evidence_candidate

    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        receipt(source_error_code="HTTP_503")
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        receipt(query_status=CoverageQueryStatus.FAILED, response_fingerprints=(RESPONSE,))


def test_identity_unresolved_and_window_unproven_are_explicit_distinct_fail_closed_states():
    unresolved = receipt(query_status=CoverageQueryStatus.IDENTITY_UNRESOLVED)
    unproven = receipt(query_status=CoverageQueryStatus.UNPROVEN)
    assert unresolved.coverage_state is unproven.coverage_state is CoverageState.UNPROVEN
    assert unresolved.absence_state is EarningsScheduleAbsenceState.IDENTITY_UNRESOLVED
    assert unproven.absence_state is EarningsScheduleAbsenceState.WINDOW_UNPROVEN


def test_collector_first_observed_is_automatic_aware_and_prospective_only():
    base = complete_no_event()
    observed = make_system_coverage_first_observed_receipt(
        canonical_instrument_id=INSTRUMENT,
        source_family=EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS,
        query_identity=base.receipt_id,
        response_fingerprints=(RESPONSE,),
        observed_at=T0 + timedelta(seconds=1),
        ingestion_run_id="schedule-collector:run-1",
        run_sequence=0,
    )
    result = complete_no_event(system_first_observed=observed)
    assert result.system_first_observed is not None
    assert result.system_first_observed.origin is SystemCoverageObservationOrigin.AUTOMATIC_INGESTION_BOUNDARY
    equivalent = make_system_coverage_first_observed_receipt(
        canonical_instrument_id=INSTRUMENT,
        source_family=EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS,
        query_identity=base.receipt_id,
        response_fingerprints=(RESPONSE,),
        observed_at=(T0 + timedelta(seconds=1)).astimezone(timezone(timedelta(hours=5, minutes=30))),
        ingestion_run_id="schedule-collector:run-1",
        run_sequence=0,
    )
    assert observed.to_json() == equivalent.to_json()
    assert result.to_json() == complete_no_event(system_first_observed=equivalent).to_json()
    with pytest.raises(EarningsScheduleCoverageError, match="AWARE_TIMESTAMP_REQUIRED"):
        make_system_coverage_first_observed_receipt(
            canonical_instrument_id=INSTRUMENT, source_family=EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS,
            query_identity=base.receipt_id, response_fingerprints=(RESPONSE,), observed_at=datetime(2026, 9, 12, 10),
            ingestion_run_id="schedule-collector:run-1", run_sequence=0,
        )


def test_collector_observation_before_query_completion_is_rejected():
    base = complete_no_event()
    observed = make_system_coverage_first_observed_receipt(
        canonical_instrument_id=INSTRUMENT, source_family=EarningsScheduleSourceFamily.NSE_BOARD_MEETINGS,
        query_identity=base.receipt_id, response_fingerprints=(RESPONSE,), observed_at=T0 - timedelta(seconds=1),
        ingestion_run_id="schedule-collector:run-1", run_sequence=0,
    )
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        complete_no_event(system_first_observed=observed)


def test_replay_is_deterministic_across_equivalent_utc_representations_and_tampering_rejects():
    a = complete_no_event()
    b = complete_no_event(query_completed_at=T0.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert a.to_json() == b.to_json() and a.receipt_id == b.receipt_id
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        replace(a, coverage_state=CoverageState.PARTIAL)
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        replace(a, fingerprint=content_fingerprint({"tampered": True}))


def test_duplicate_or_cross_category_lineage_is_rejected_not_silently_deduplicated():
    repeated = row("same")
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        complete_no_event(qualifying_rows=(repeated,), non_qualifying_rows=(repeated,))
    with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
        complete_no_event(qualifying_rows=(repeated, repeated))


def test_fresh_and_stale_cannot_be_fabricated_before_a_separately_approved_policy():
    result = complete_no_event()
    for state in (EarningsScheduleFreshnessState.FRESH, EarningsScheduleFreshnessState.STALE):
        with pytest.raises(EarningsScheduleCoverageError, match="COVERAGE_RECEIPT_INVALID"):
            replace(result, freshness_state=state)


def test_contract_has_no_source_fetch_gate_database_or_execution_dependency():
    source = Path("app/filings/earnings_schedule_coverage.py").read_text(encoding="utf-8")
    forbidden = (
        "from app.gates", "import app.gates", "from app.portfolio", "from app.orders", "from app.api",
        "import sqlite", "import requests", "datetime.now", "date.today", "time.now", "app.signals",
    )
    assert all(item not in source for item in forbidden)
    names = {field.name for field in fields(type(complete_no_event()))}
    assert not names & {"entry_price", "stop_loss", "target_price", "quantity", "portfolio", "broker", "order"}
    assert "WATCH_ONLY" in source and "NON_EXECUTABLE" in source
