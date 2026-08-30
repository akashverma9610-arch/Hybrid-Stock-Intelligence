from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.data_sources.models import DataFamily
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.non_company_evidence import ReliabilityEvidenceAdapter, ReliabilityRepositoryStoredSource
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.reliability.models import (
    DataAvailability, ReliabilityDecision, ReliabilityStatus,
    StoredReliabilityDecision, reliability_decision_fingerprint,
)
from app.reliability.serialization import ReliabilityDecisionSerializationError, reliability_decision_from, reliability_decision_to
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.domain.models import FreshnessStatus
from app.intelligence.unified_state import IntelligenceInvalidationDomain

T = datetime(2026, 8, 28, 12, tzinfo=UTC)
INSTRUMENT = "NSE:RELIABILITY"


def decision(
    *, identifier: str = "reliability-1", status: ReliabilityStatus = ReliabilityStatus.READY,
    at: datetime = T, family: DataFamily = DataFamily.HISTORICAL_OHLCV,
) -> StoredReliabilityDecision:
    source = None if status in {ReliabilityStatus.UNAVAILABLE, ReliabilityStatus.PRIMARY_UNAVAILABLE, ReliabilityStatus.CONFLICTED} else "source-a"
    tier = None if source is None else (2 if status in {ReliabilityStatus.FALLBACK_USED, ReliabilityStatus.LAST_KNOWN_GOOD} else 1)
    availability = DataAvailability(family, status, source, tier, at, ("SOURCE_VALUE_CONFLICT",) if status is ReliabilityStatus.CONFLICTED else ())
    raw = StoredReliabilityDecision(
        identifier, INSTRUMENT,
        ReliabilityDecision(family, availability, source, tier, status is ReliabilityStatus.FALLBACK_USED,
                            status is ReliabilityStatus.LAST_KNOWN_GOOD, status is ReliabilityStatus.CONFLICTED,
                            availability.warnings),
        at, at, "pending", at,
    )
    return replace(raw, fingerprint=reliability_decision_fingerprint(raw))


@pytest.mark.parametrize("status", (
    ReliabilityStatus.READY, ReliabilityStatus.FALLBACK_USED, ReliabilityStatus.LAST_KNOWN_GOOD,
    ReliabilityStatus.UNAVAILABLE, ReliabilityStatus.CONFLICTED,
))
def test_all_existing_typed_outcomes_round_trip_exactly(status) -> None:
    value = decision(status=status)
    assert reliability_decision_from(reliability_decision_to(value)) == value


def test_durable_reliability_serialization_requires_evaluation_as_of_and_fingerprint() -> None:
    value = decision()
    with pytest.raises(ReliabilityDecisionSerializationError, match="EVALUATION_AS_OF_REQUIRED"):
        reliability_decision_to(replace(value, evaluation_as_of=None))
    with pytest.raises(ReliabilityDecisionSerializationError, match="FINGERPRINT_MISMATCH"):
        reliability_decision_to(replace(value, fingerprint="tampered"))
    changed_source = replace(value, decision=replace(value.decision, selected_source_id="source-b"))
    changed_outcome = replace(value, decision=replace(value.decision, availability=replace(
        value.decision.availability, status=ReliabilityStatus.FALLBACK_USED,
    )))
    assert reliability_decision_fingerprint(changed_source) != value.fingerprint
    assert reliability_decision_fingerprint(changed_outcome) != value.fingerprint


@pytest.mark.parametrize("path,replacement", (
    (("canonical_instrument_id",), "NSE:TAMPERED"),
    (("evaluation_as_of",), (T + timedelta(days=1)).isoformat()),
    (("decision", "availability", "status"), ReliabilityStatus.UNAVAILABLE.value),
    (("decision", "selected_source_id"), "different-source"),
))
def test_tampered_reliability_payload_fails_closed(path, replacement) -> None:
    payload = reliability_decision_to(decision())
    target = payload
    for key in path[:-1]: target = target[key]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]
    with pytest.raises(ReliabilityDecisionSerializationError, match="FINGERPRINT_MISMATCH"):
        reliability_decision_from(payload)


def test_sqlite_save_get_list_as_of_reopen_and_conflict(tmp_path) -> None:
    path = tmp_path / "reliability.sqlite"
    first, later, other = decision(identifier="a", at=T - timedelta(days=1)), decision(identifier="b", at=T), decision(identifier="c", family=DataFamily.FUNDAMENTALS)
    repository = SQLiteStrategyGovernanceRepository(str(path))
    for value in (later, other, first): repository.save_reliability_decision(value)
    assert repository.get_reliability_decision("missing") is None
    assert repository.list_reliability_decisions(canonical_instrument_id=INSTRUMENT, evidence_domain=DataFamily.HISTORICAL_OHLCV) == (first, later)
    assert repository.list_reliability_decisions(outcome=ReliabilityStatus.READY) == (first, later, other)
    assert repository.latest_reliability_decision_as_of(INSTRUMENT, DataFamily.HISTORICAL_OHLCV, T - timedelta(hours=12)) == first
    with pytest.raises(ValueError, match="immutable"):
        repository.save_reliability_decision(first)
    repository.close()
    reopened = SQLiteStrategyGovernanceRepository(str(path))
    assert reopened.get_reliability_decision(later.decision_id) == later
    reopened.close()


def test_valid_conflict_is_persistable_but_stored_corruption_is_not(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "reliability.sqlite"))
    conflict = decision(status=ReliabilityStatus.CONFLICTED)
    repository.save_reliability_decision(conflict)
    assert repository.get_reliability_decision(conflict.decision_id).decision.availability.status is ReliabilityStatus.CONFLICTED
    repository._connection.execute("UPDATE reliability_decisions SET payload_json=? WHERE id=?", (
        json.dumps({**reliability_decision_to(conflict), "fingerprint": "tampered"}), conflict.decision_id,
    ))
    repository._connection.commit()
    with pytest.raises(ReliabilityDecisionSerializationError, match="FINGERPRINT_MISMATCH"):
        repository.list_reliability_decisions()
    repository.close()


class _CoreSource:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
        return (StoredIntelligenceArtifact(
            canonical_instrument_id, IntelligenceEvidenceDomain.REFERENCE_DATA, "identity", "identity-fp",
            IntelligenceEvidenceAvailability.AVAILABLE, as_of, as_of, as_of, FreshnessStatus.UNKNOWN,
            None, None, None, IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


def test_repository_adapter_is_as_of_stored_only_and_preserves_existing_availability_mapping(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "reliability.sqlite"))
    fallback, future = decision(status=ReliabilityStatus.FALLBACK_USED), decision(identifier="future", status=ReliabilityStatus.CONFLICTED, at=T + timedelta(days=1))
    repository.save_reliability_decision(fallback); repository.save_reliability_decision(future)
    source = ReliabilityRepositoryStoredSource(repository)
    artifacts = ReliabilityEvidenceAdapter(source).artifacts(INSTRUMENT, as_of=T)
    assert len(artifacts) == 1 and artifacts[0].availability is IntelligenceEvidenceAvailability.PARTIAL
    state = UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_CoreSource(), type("Source", (), {"list_stored_intelligence_artifacts": lambda self, canonical_instrument_id, *, as_of: artifacts})())).build(INSTRUMENT, as_of=T)
    ref = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.RELIABILITY)
    assert ref.availability is IntelligenceEvidenceAvailability.PARTIAL and "reliability:reliability-1" in ref.artifact_ids
    repository.close()


def test_reliability_state_lineage_is_insertion_order_independent(tmp_path) -> None:
    values = (decision(identifier="a", family=DataFamily.HISTORICAL_OHLCV), decision(identifier="b", family=DataFamily.FUNDAMENTALS))

    def build(path, ordered):
        repository = SQLiteStrategyGovernanceRepository(str(path))
        for value in ordered: repository.save_reliability_decision(value)
        artifacts = ReliabilityEvidenceAdapter(ReliabilityRepositoryStoredSource(repository)).artifacts(INSTRUMENT, as_of=T)
        state = UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(
            _CoreSource(), type("Source", (), {"list_stored_intelligence_artifacts": lambda self, canonical_instrument_id, *, as_of: artifacts})(),
        )).build(INSTRUMENT, as_of=T)
        return next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.RELIABILITY)

    first, second = build(tmp_path / "first.sqlite", values), build(tmp_path / "second.sqlite", tuple(reversed(values)))
    assert (first.artifact_ids, first.artifact_fingerprints) == (second.artifact_ids, second.artifact_fingerprints)
