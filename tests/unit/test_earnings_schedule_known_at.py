"""Focused proofs for official schedule public/HSI known-at separation."""
from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from app.filings.earnings_schedule_known_at import (
    EarningsScheduleKnownAtError,
    EarningsScheduleKnownAtEvidence,
    KnownAtPerspective,
    KnownAtReason,
    KnownAtState,
    SourceTimestampEvidence,
    SourceTimestampSemanticAuthority,
    TimestampFieldSemantic,
    make_system_first_observed_receipt,
    resolve_earnings_schedule_known_at,
)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.historical.filing_timestamp_timezone_provenance import (
    EventKnownTimeStatus,
    SourceTimestampEncoding,
    make_filing_timestamp_input,
    resolve_filing_timestamp,
)


T0 = datetime(2026, 9, 12, 10, tzinfo=UTC)
INSTRUMENT = "NSE:INE372A01015"
FILING = "earnings-source:fixture"
PAYLOAD = content_fingerprint({"official": "fixture"})


def _timestamp(*, at: datetime = T0, raw: str | None = None):
    value = make_filing_timestamp_input(
        filing_id=FILING,
        canonical_instrument_id=INSTRUMENT,
        source_family="nse-corporate-filings/v1",
        source_document_identity="official-filing:fixture",
        source_payload_identity="official-payload:fixture",
        source_payload_fingerprint=PAYLOAD,
        raw_timestamp_field_path="Exchange Dissemination Time",
        raw_timestamp_value=raw or at.isoformat(),
        parsed_local_timestamp=at.replace(tzinfo=None) if raw is not None else at,
        filing_date=None,
        declared_timezone_id=None,
        encoding=SourceTimestampEncoding.TEXT,
        event_known_time_status=EventKnownTimeStatus.SOURCE_PUBLICATION_TIMESTAMP_UNVERIFIED,
    )
    return resolve_filing_timestamp(value, as_of=T0 + timedelta(days=2))


def _source(*, semantic=TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME,
            authority=SourceTimestampSemanticAuthority.PROVEN, at=T0):
    return SourceTimestampEvidence(
        semantic=semantic,
        semantic_authority=authority,
        semantic_evidence_ids=("nse-field-semantics:dissemination",) if authority is SourceTimestampSemanticAuthority.PROVEN else (),
        semantic_evidence_fingerprints=(content_fingerprint({"source": "nse-field-semantics"}),) if authority is SourceTimestampSemanticAuthority.PROVEN else (),
        semantic_evidence_known_at=T0 - timedelta(days=1) if authority is SourceTimestampSemanticAuthority.PROVEN else None,
        timestamp_receipt=_timestamp(at=at),
    )


def _observation(*, at=T0 + timedelta(minutes=2)):
    return make_system_first_observed_receipt(
        canonical_instrument_id=INSTRUMENT,
        source_filing_identity=FILING,
        source_payload_fingerprint=PAYLOAD,
        observed_at=at,
        ingestion_run_id="ingestion-run:fixture",
        run_sequence=4,
    )


def _evidence(*, source=None, observed=None):
    return EarningsScheduleKnownAtEvidence(
        canonical_instrument_id=INSTRUMENT,
        source_filing_identity=FILING,
        source_payload_fingerprint=PAYLOAD,
        source_timestamp=source,
        system_first_observed=observed,
    )


def _resolve(*, evidence, perspective, as_of=T0 + timedelta(days=1)):
    return resolve_earnings_schedule_known_at(evidence=evidence, perspective=perspective, as_of=as_of)


def test_authoritative_zoned_public_dissemination_is_strict_source_pit():
    result = _resolve(evidence=_evidence(source=_source()), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert result.state is KnownAtState.STRICT_SOURCE_PIT
    assert result.known_at == T0 and result.source_public_at == T0
    assert result.hsi_available_at is None


@pytest.mark.parametrize("semantic", [
    TimestampFieldSemantic.EXCHANGE_RECEIPT_TIME,
    TimestampFieldSemantic.ISSUER_DOCUMENT_TIME,
    TimestampFieldSemantic.EVENT_SCHEDULE_TIME,
    TimestampFieldSemantic.UNKNOWN_SEMANTIC,
])
def test_event_date_report_date_and_exchange_receipt_never_become_public_known_at(semantic):
    result = _resolve(evidence=_evidence(source=_source(semantic=semantic, authority=SourceTimestampSemanticAuthority.UNPROVEN)), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert result.state is KnownAtState.CURRENT_DESCRIPTIVE_ONLY
    assert result.known_at is None
    assert KnownAtReason.SOURCE_TIMESTAMP_NOT_PUBLIC_DISSEMINATION in result.reason_codes


def test_unzoned_source_timestamp_is_retained_but_cannot_receive_a_guessed_timezone():
    receipt = _timestamp(at=T0, raw="12-Sep-2026 15:30:00")
    assert receipt.normalized_utc_timestamp is None
    source = SourceTimestampEvidence(
        semantic=TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME,
        semantic_authority=SourceTimestampSemanticAuthority.UNPROVEN,
        semantic_evidence_ids=(), semantic_evidence_fingerprints=(), semantic_evidence_known_at=None,
        timestamp_receipt=receipt,
    )
    result = _resolve(evidence=_evidence(source=source), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert result.known_at is None and KnownAtReason.SOURCE_TIMESTAMP_TIMEZONE_UNPROVEN in result.reason_codes


def test_public_market_and_hsi_local_are_separate_without_an_implicit_max_rule():
    evidence = _evidence(source=_source(), observed=_observation(at=T0 + timedelta(minutes=2)))
    public = _resolve(evidence=evidence, perspective=KnownAtPerspective.PUBLIC_MARKET)
    hsi = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL)
    assert public.state is KnownAtState.STRICT_SOURCE_PIT and public.known_at == T0
    assert hsi.state is KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT and hsi.known_at == T0 + timedelta(minutes=2)
    assert public.hsi_available_at == hsi.hsi_available_at == T0 + timedelta(minutes=2)


def test_first_observed_must_be_aware_and_automatic_ingestion_receipt():
    with pytest.raises(EarningsScheduleKnownAtError, match="TIMESTAMP_AWARE_REQUIRED"):
        _observation(at=datetime(2026, 9, 12, 10, 2))
    receipt = _observation()
    with pytest.raises(EarningsScheduleKnownAtError, match="FIRST_OBSERVED_RECEIPT_INVALID"):
        replace(receipt, origin="CALLER_SUPPLIED")


def test_first_observed_is_prospective_and_never_backdates():
    evidence = _evidence(observed=_observation())
    before = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(minutes=1))
    after = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(minutes=3))
    assert before.state is KnownAtState.TEMPORAL_AUTHORITY_UNAVAILABLE and before.known_at is None
    assert KnownAtReason.SYSTEM_FIRST_OBSERVED_AFTER_AS_OF in before.reason_codes
    assert after.state is KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT
    assert after.known_at == T0 + timedelta(minutes=2)


def test_later_discovered_historical_record_cannot_enter_earlier_replay():
    evidence = _evidence(source=_source(semantic=TimestampFieldSemantic.ISSUER_DOCUMENT_TIME,
                                         authority=SourceTimestampSemanticAuthority.UNPROVEN,
                                         at=datetime(2025, 7, 16, 8, tzinfo=UTC)),
                         observed=_observation(at=datetime(2026, 9, 12, 14, 2, tzinfo=UTC)))
    replay = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL,
                      as_of=datetime(2025, 7, 16, 9, tzinfo=UTC))
    assert replay.known_at is None
    assert KnownAtReason.SYSTEM_FIRST_OBSERVED_AFTER_AS_OF in replay.reason_codes


def test_source_observation_before_proven_public_time_fails_closed():
    evidence = _evidence(source=_source(at=T0 + timedelta(minutes=2)), observed=_observation(at=T0 + timedelta(minutes=1)))
    result = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL)
    assert result.state is KnownAtState.CURRENT_DESCRIPTIVE_ONLY
    assert KnownAtReason.SYSTEM_OBSERVATION_PRECEDES_SOURCE_PUBLIC_TIME in result.reason_codes


def test_revisions_and_cancellations_have_independent_known_at_timelines_without_backward_leakage():
    original = _evidence(source=_source(at=T0), observed=_observation(at=T0 + timedelta(minutes=1)))
    revised_filing = "earnings-source:revision"
    revised_payload = content_fingerprint({"official": "revision"})
    revision_receipt = make_system_first_observed_receipt(
        canonical_instrument_id=INSTRUMENT, source_filing_identity=revised_filing,
        source_payload_fingerprint=revised_payload, observed_at=T0 + timedelta(hours=1),
        ingestion_run_id="ingestion-run:fixture", run_sequence=5,
    )
    revision = EarningsScheduleKnownAtEvidence(INSTRUMENT, revised_filing, revised_payload, None, revision_receipt)
    before_revision = _resolve(evidence=revision, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(minutes=30))
    original_visible = _resolve(evidence=original, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(minutes=30))
    after_revision = _resolve(evidence=revision, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(hours=2))
    assert before_revision.known_at is None and original_visible.known_at == T0 + timedelta(minutes=1)
    assert after_revision.known_at == T0 + timedelta(hours=1)


def test_cancellation_receipt_is_not_visible_before_its_own_first_observation():
    cancellation_filing = "earnings-source:cancellation"
    cancellation_payload = content_fingerprint({"official": "cancellation"})
    cancellation = EarningsScheduleKnownAtEvidence(
        INSTRUMENT, cancellation_filing, cancellation_payload, None,
        make_system_first_observed_receipt(
            canonical_instrument_id=INSTRUMENT, source_filing_identity=cancellation_filing,
            source_payload_fingerprint=cancellation_payload, observed_at=T0 + timedelta(hours=2),
            ingestion_run_id="ingestion-run:fixture", run_sequence=6,
        ),
    )
    before = _resolve(evidence=cancellation, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(hours=1))
    after = _resolve(evidence=cancellation, perspective=KnownAtPerspective.HSI_LOCAL, as_of=T0 + timedelta(hours=3))
    assert before.known_at is None and after.known_at == T0 + timedelta(hours=2)


def test_dual_exchange_times_remain_independent_and_same_schedule_time_difference_is_not_event_conflict():
    nse = _resolve(evidence=_evidence(source=_source(at=T0)), perspective=KnownAtPerspective.PUBLIC_MARKET)
    bse = _resolve(evidence=_evidence(source=_source(at=T0 + timedelta(seconds=3))), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert nse.known_at != bse.known_at
    assert nse.state is bse.state is KnownAtState.STRICT_SOURCE_PIT
    assert "CONFLICT" not in nse.to_json() + bse.to_json()


def test_schedule_date_conflict_is_not_decided_by_known_at_contract():
    result = _resolve(evidence=_evidence(source=_source()), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert "scheduled_date" not in result.to_json()
    assert "clearance" not in result.to_json().lower()


def test_identity_readiness_alone_is_not_temporal_readiness_and_absence_is_not_clearance():
    result = _resolve(evidence=_evidence(), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert result.state is KnownAtState.TEMPORAL_AUTHORITY_UNAVAILABLE
    assert result.known_at is None
    assert KnownAtReason.TEMPORAL_EVIDENCE_ABSENT in result.reason_codes
    assert "absence" not in result.to_json().lower()


def test_positive_schedule_time_can_be_temporally_ready_without_creating_a_gate_or_absence_policy():
    result = _resolve(evidence=_evidence(observed=_observation()), perspective=KnownAtPerspective.HSI_LOCAL)
    assert result.state is KnownAtState.PROSPECTIVE_FIRST_OBSERVED_PIT
    assert result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"
    assert "gate" not in result.to_json().lower()


def test_future_source_time_does_not_leak_into_earlier_public_replay():
    result = _resolve(evidence=_evidence(source=_source(at=T0 + timedelta(days=1))),
                      perspective=KnownAtPerspective.PUBLIC_MARKET, as_of=T0)
    assert result.state is KnownAtState.CURRENT_DESCRIPTIVE_ONLY
    assert result.source_public_at is None and result.known_at is None
    assert KnownAtReason.SOURCE_PUBLIC_TIME_AFTER_AS_OF in result.reason_codes


def test_future_field_semantic_proof_cannot_backdate_a_public_time():
    source = _source()
    unproven_at_source_time = replace(source, semantic_evidence_known_at=T0 + timedelta(seconds=1))
    result = _resolve(evidence=_evidence(source=unproven_at_source_time), perspective=KnownAtPerspective.PUBLIC_MARKET)
    assert result.state is KnownAtState.CURRENT_DESCRIPTIVE_ONLY and result.known_at is None
    assert KnownAtReason.SOURCE_SEMANTIC_EVIDENCE_AFTER_PUBLIC_TIME in result.reason_codes


def test_deterministic_receipt_replay_utc_normalization_and_tamper_rejection():
    evidence = _evidence(source=_source(), observed=_observation())
    a = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL)
    b = _resolve(evidence=evidence, perspective=KnownAtPerspective.HSI_LOCAL,
                 as_of=(T0 + timedelta(days=1)).astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert a.to_json() == b.to_json()
    assert a.source_timestamp_receipt_fingerprint == evidence.source_timestamp.timestamp_receipt.fingerprint
    assert a.system_first_observed_receipt_fingerprint == evidence.system_first_observed.fingerprint
    assert a.semantic_evidence_ids == evidence.source_timestamp.semantic_evidence_ids
    with pytest.raises(EarningsScheduleKnownAtError, match="RESOLUTION_INVALID"):
        replace(a, known_at=T0)


def test_duplicate_or_conflicting_semantic_lineage_is_rejected_not_silently_deduplicated():
    receipt = _timestamp()
    fp = content_fingerprint({"source": "nse-field-semantics"})
    with pytest.raises(EarningsScheduleKnownAtError, match="SOURCE_TIMESTAMP_SEMANTICS_INVALID"):
        SourceTimestampEvidence(
            TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME, SourceTimestampSemanticAuthority.PROVEN,
            ("nse-field-semantics:dissemination", "nse-field-semantics:dissemination"), (fp, fp),
            T0 - timedelta(days=1), receipt,
        )


def test_first_observed_receipt_fingerprint_includes_time_run_and_source_lineage():
    receipt = _observation()
    with pytest.raises(EarningsScheduleKnownAtError, match="FIRST_OBSERVED_RECEIPT_INVALID"):
        replace(receipt, run_sequence=receipt.run_sequence + 1)


def test_contract_has_no_gate_provider_clock_or_execution_dependencies():
    source = Path("app/filings/earnings_schedule_known_at.py").read_text(encoding="utf-8")
    forbidden = ("from app.gates", "import app.gates", "from app.portfolio", "from app.orders",
                 "import sqlite", "import requests", "time.now", "datetime.now", "date.today")
    assert all(value not in source for value in forbidden)
    assert "WATCH_ONLY" in source and "NON_EXECUTABLE" in source


def test_committed_read_only_audit_receipt_is_fingerprinted_and_keeps_gate_unwired():
    receipt = json.loads(Path("docs/architecture/EARNINGS_CALENDAR_KNOWN_AT_SEMANTICS_V1_RECEIPT.json").read_text(encoding="utf-8"))
    fingerprint = receipt.pop("fingerprint")
    assert fingerprint == content_fingerprint(receipt)
    assert receipt["gate6_wired"] is False and receipt["source_discovery_started"] is False
