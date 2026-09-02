from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.intelligence.external_intelligence import (
    DataPoint,
    EventType,
    EvidenceVersion,
    ExternalEvent,
    Fact,
    Inference,
    Interpretation,
    Materiality,
    PolicyStage,
    ReevaluationRequest,
    SourceEvidence,
)
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


T = datetime(2026, 9, 1, 9, tzinfo=UTC)


def event(*, received_at: datetime = T, country: str = "IN") -> ExternalEvent:
    return ExternalEvent(
        "HSI_EXTERNAL_INTELLIGENCE_DESK", "test-rbi-1", EventType.MONETARY_POLICY,
        "TEST_RBI_POLICY_EVENT", country, "MACRO", Materiality.HIGH, received_at, PolicyStage.STATEMENT,
    )


def evidence(*, summary: str = "V1", received_at: datetime = T, source: str = "Synthetic") -> EvidenceVersion:
    return EvidenceVersion(
        event(), received_at, T, T, summary, "Policy rate signal updated",
        SourceEvidence(source, "SYNTHETIC", "https://invalid.test/rbi", 0.9),
        (Fact("Official policy statement", ("source-1",), 0.9),),
        (DataPoint("repo_rate", "6.25", "percent", "FY2026", ("source-1",)),),
        (Interpretation("Rates remain restrictive", 0.7),),
        (Inference("Credit sensitivity needs review", 0.4),),
    )


def request(value: EvidenceVersion, *, requested_at: datetime = T) -> ReevaluationRequest:
    return ReevaluationRequest(
        value.event.canonical_event_id, value.evidence_version_id, Materiality.HIGH, requested_at,
        ("NSE:INE090A01021",), ("FINANCIALS",), ("BANKS",),
    )


def repository(tmp_path) -> SQLiteExternalIntelligenceRepository:
    return SQLiteExternalIntelligenceRepository(tmp_path / "external-intelligence.sqlite")


def test_schema_event_save_load_retry_and_producer_identity_immutability(tmp_path) -> None:
    repo = repository(tmp_path)
    value = event()
    assert repo.save_event(value) == value
    assert repo.save_event(value) == value
    assert repo.get_event(value.canonical_event_id) == value
    assert repo.get_event_by_producer_identity(value.producer_id, value.producer_event_id) == value
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 0, "reevaluation_requests": 0}
    with pytest.raises(ValueError, match="immutable"):
        repo.save_event(replace(value, first_received_at=T + timedelta(seconds=1)))
    with pytest.raises(ValueError, match="Producer event identity"):
        repo.save_event(event(country="US"))
    assert repo.foreign_key_violations() == () and repo.sqlite_integrity() == "ok"
    repo.close()


def test_evidence_is_append_only_ordered_and_requires_exact_event(tmp_path) -> None:
    repo = repository(tmp_path)
    first, second = evidence(summary="V1", received_at=T), evidence(summary="V2", received_at=T + timedelta(minutes=1))
    with pytest.raises(ValueError, match="persisted canonical event"):
        repo.save_evidence_version(first)
    repo.save_event(first.event)
    assert repo.save_evidence_version(first) == first
    assert repo.save_evidence_version(first) == first
    assert repo.save_evidence_version(second) == second
    assert repo.list_evidence_versions(first.event.canonical_event_id) == (first, second)
    with pytest.raises(ValueError, match="immutable"):
        repo.save_evidence_version(replace(first, received_at=T + timedelta(seconds=1)))
    different_event = replace(
        evidence(summary="different event reference"), event=event(received_at=T + timedelta(seconds=1)),
    )
    with pytest.raises(ValueError, match="exact persisted event"):
        repo.save_evidence_version(different_event)
    assert repo.external_intelligence_row_counts()["evidence_versions"] == 2
    repo.close()


def test_reevaluation_is_immutable_and_requires_matching_persisted_lineage(tmp_path) -> None:
    repo = repository(tmp_path)
    value = evidence()
    item = request(value)
    with pytest.raises(ValueError, match="persisted canonical event"):
        repo.save_reevaluation_request(item)
    repo.save_event(value.event)
    with pytest.raises(ValueError, match="persisted evidence version"):
        repo.save_reevaluation_request(item)
    repo.save_evidence_version(value)
    assert repo.save_reevaluation_request(item) == item
    assert repo.save_reevaluation_request(item) == item
    assert repo.get_reevaluation_request(item.request_id) == item
    with pytest.raises(ValueError, match="immutable"):
        repo.save_reevaluation_request(replace(item, requested_at=T + timedelta(seconds=1)))
    wrong = ReevaluationRequest("missing-event", value.evidence_version_id, Materiality.HIGH, T)
    with pytest.raises(ValueError, match="persisted canonical event"):
        repo.save_reevaluation_request(wrong)
    repo.close()


def test_isolated_synthetic_reopen_durability_preserves_typed_objects_and_pit_timestamps(tmp_path) -> None:
    path = tmp_path / "durable.sqlite"
    repo = SQLiteExternalIntelligenceRepository(path)
    first = evidence(summary="V1", received_at=T)
    second = evidence(summary="V2", received_at=T + timedelta(minutes=1))
    first_request, second_request = request(first), request(second, requested_at=T + timedelta(minutes=1))
    repo.save_event(first.event)
    for item in (first, first, second):
        repo.save_evidence_version(item)
    for item in (first_request, first_request, second_request):
        repo.save_reevaluation_request(item)
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 2, "reevaluation_requests": 2}
    repo.close()

    reopened = SQLiteExternalIntelligenceRepository(path)
    assert reopened.get_event(first.event.canonical_event_id) == first.event
    assert reopened.list_evidence_versions(first.event.canonical_event_id) == (first, second)
    assert reopened.list_reevaluation_requests(canonical_event_id=first.event.canonical_event_id) == (first_request, second_request)
    assert reopened.foreign_key_violations() == () and reopened.sqlite_integrity() == "ok"
    reopened.close()


@pytest.mark.parametrize("table,column,replacement,reader", (
    ("external_intelligence_events", "stable_event_fingerprint", "sha256:tampered", "event"),
    ("external_intelligence_evidence_versions", "payload_fingerprint", "sha256:tampered", "evidence"),
    ("external_intelligence_reevaluation_requests", "canonical_payload_json", '{"tampered":true}', "request"),
))
def test_tampering_fails_closed_on_rehydration(tmp_path, table, column, replacement, reader) -> None:
    repo = repository(tmp_path)
    value = evidence()
    item = request(value)
    repo.save_event(value.event); repo.save_evidence_version(value); repo.save_reevaluation_request(item)
    identity_column, identity = {
        "event": ("canonical_event_id", value.event.canonical_event_id),
        "evidence": ("evidence_version_id", value.evidence_version_id),
        "request": ("request_id", item.request_id),
    }[reader]
    repo._connection.execute(f"UPDATE {table} SET {column} = ? WHERE {identity_column} = ?", (replacement, identity))
    repo._connection.commit()
    with pytest.raises(ValueError, match="immutable integrity verification|canonical payload|payload field"):
        {"event": repo.get_event, "evidence": repo.get_evidence_version, "request": repo.get_reevaluation_request}[reader](identity)
    repo.close()


def test_sqlite_fk_rollback_leaves_no_partial_inconsistent_rows(tmp_path) -> None:
    repo = repository(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        with repo._connection:
            repo._connection.execute(
                """INSERT INTO external_intelligence_events VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("transaction-event", "producer", "transaction", "v1", "fingerprint", "{}", T.isoformat()),
            )
            repo._connection.execute(
                """INSERT INTO external_intelligence_evidence_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("broken-evidence", "missing-event", "fingerprint", "payload", T.isoformat(), T.isoformat(), T.isoformat(), "{}"),
            )
    assert repo.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    assert repo.foreign_key_violations() == ()
    repo.close()


def test_persistence_has_no_news_brain_or_trading_side_effects(tmp_path) -> None:
    repo = repository(tmp_path)
    before = {row[0] for row in repo._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    value = evidence(); repo.save_event(value.event); repo.save_evidence_version(value); repo.save_reevaluation_request(request(value))
    after = {row[0] for row in repo._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert before == after
    assert "news_evidence" not in after and "paper_trades" not in after
    assert repo.audit_event_count() == 0
    repo.close()


def test_payload_tamper_does_not_get_silently_regenerated(tmp_path) -> None:
    repo = repository(tmp_path)
    value = evidence(); repo.save_event(value.event); repo.save_evidence_version(value)
    payload = json.loads(repo._connection.execute(
        "SELECT canonical_payload_json FROM external_intelligence_evidence_versions WHERE evidence_version_id = ?", (value.evidence_version_id,),
    ).fetchone()[0])
    payload["summary"] = "tampered"
    repo._connection.execute(
        "UPDATE external_intelligence_evidence_versions SET canonical_payload_json = ? WHERE evidence_version_id = ?",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")), value.evidence_version_id),
    )
    repo._connection.commit()
    with pytest.raises(ValueError, match="immutable integrity verification"):
        repo.get_evidence_version(value.evidence_version_id)
    repo.close()
