from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta

import pytest

from app.intelligence.governed_setup_evidence import GovernedSetupEvidenceStoredSource
from app.intelligence.unified_state import IntelligenceEvidenceDomain
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.setup_assessment_serialization import (
    PreBreakoutSetupAssessmentSerializationError, assessment_from, assessment_to,
)
from app.strategies.pre_breakout.candidate_assembly import assemble_prebreakout_candidate
from app.strategies.pre_breakout.research_handoff import candidate_to_brain_research_handoff
from tests.unit.pre_breakout_setup_fixture import INSTRUMENT_ID, T, assessment


def test_assessment_serialization_round_trip_is_exact_and_fingerprints_all_semantics() -> None:
    value = assessment()
    payload = assessment_to(value)
    restored = assessment_from(payload)
    assert restored == value
    assert restored.assessment_id == value.assessment_id
    assert restored.fingerprint == value.fingerprint
    assert replace(value, sector="Changed").fingerprint != value.fingerprint
    assert replace(value, warnings=("NEW_WARNING",)).fingerprint != value.fingerprint


def test_assessment_serialization_fails_closed_on_semantic_tampering() -> None:
    payload = assessment_to(assessment())
    payload["assessment"]["fields"]["sector"] = "Tampered"  # type: ignore[index]
    with pytest.raises(PreBreakoutSetupAssessmentSerializationError, match="FINGERPRINT_MISMATCH"):
        assessment_from(payload)


@pytest.mark.parametrize("path,replacement", (
    (("instrument_id",), "NSE:TAMPERED"),
    (("policy_fingerprint",), "tampered-policy"),
    (("sector",), "Tampered-sector"),
    (("candidate_formation_eligible",), False),
    (("technical_inputs", "fields", "bbw_pass"), False),
    (("structural", "fields", "final_stop"), {"__decimal__": "400"}),
    (("structural", "fields", "target"), {"__decimal__": "600"}),
    (("structural", "fields", "entry_reference_rr"), {"__decimal__": "1.0"}),
))
def test_all_semantic_tampering_is_fingerprint_closed(path, replacement) -> None:
    payload = assessment_to(assessment())
    target = payload["assessment"]["fields"]  # type: ignore[index]
    for key in path[:-1]:
        target = target[key]  # type: ignore[index]
    target[path[-1]] = replacement  # type: ignore[index]
    with pytest.raises(PreBreakoutSetupAssessmentSerializationError, match="FINGERPRINT_MISMATCH"):
        assessment_from(payload)


def test_sqlite_assessment_is_insert_only_durable_and_tamper_closed(tmp_path) -> None:
    path = tmp_path / "governance.sqlite"
    value = assessment()
    repository = SQLiteStrategyGovernanceRepository(str(path))
    repository.save_prebreakout_setup_assessment(value)
    assert repository.get_prebreakout_setup_assessment(value.assessment_id) == value
    with pytest.raises(ValueError, match="immutable"):
        repository.save_prebreakout_setup_assessment(value)
    repository._connection.execute(
        "UPDATE prebreakout_setup_assessments SET payload_json=? WHERE id=?",
        (json.dumps({**assessment_to(value), "fingerprint": "tampered"}), value.assessment_id),
    )
    repository._connection.commit()
    with pytest.raises(PreBreakoutSetupAssessmentSerializationError, match="FINGERPRINT_MISMATCH"):
        repository.get_prebreakout_setup_assessment(value.assessment_id)
    repository.close()


def test_sqlite_reopen_and_filters_preserve_exact_immutable_assessments(tmp_path) -> None:
    path = tmp_path / "governance.sqlite"
    first, later = assessment(), assessment(at=T + timedelta(days=1))
    repository = SQLiteStrategyGovernanceRepository(str(path))
    repository.save_prebreakout_setup_assessment(first)
    repository.save_prebreakout_setup_assessment(later)
    repository.close()
    reopened = SQLiteStrategyGovernanceRepository(str(path))
    assert reopened.get_prebreakout_setup_assessment(first.assessment_id) == first
    assert reopened.list_prebreakout_setup_assessments(canonical_instrument_id=INSTRUMENT_ID) == (first, later)
    assert reopened.list_prebreakout_setup_assessments(policy_fingerprint="different") == ()
    reopened.close()


def test_persisted_eligible_assessment_reconstructs_same_candidate_and_handoff(tmp_path) -> None:
    path = tmp_path / "governance.sqlite"
    original = assessment()
    expected_candidate = assemble_prebreakout_candidate(original)
    expected_handoff = candidate_to_brain_research_handoff(expected_candidate)
    repository = SQLiteStrategyGovernanceRepository(str(path))
    repository.save_prebreakout_setup_assessment(original)
    reconstructed = repository.get_prebreakout_setup_assessment(original.assessment_id)
    assert reconstructed is not None
    candidate = assemble_prebreakout_candidate(reconstructed)
    handoff = candidate_to_brain_research_handoff(candidate)
    assert (candidate.candidate_id, candidate.fingerprint) == (expected_candidate.candidate_id, expected_candidate.fingerprint)
    assert (handoff.handoff_id, handoff.fingerprint) == (expected_handoff.handoff_id, expected_handoff.fingerprint)
    assert repository._connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='prebreakout_candidates'"
    ).fetchone() is None
    repository.close()


class _ReadOnlyRepository:
    def __init__(self, values): self.values = values
    def list_prebreakout_setup_assessments(self, canonical_instrument_id=None, policy_fingerprint=None):
        return tuple(value for value in self.values if canonical_instrument_id is None or value.instrument_id == canonical_instrument_id)


def test_stored_setup_adapter_uses_latest_as_of_assessment_and_never_materializes_candidate() -> None:
    old, current = assessment(at=T - timedelta(days=1)), assessment(at=T)
    source = GovernedSetupEvidenceStoredSource(_ReadOnlyRepository((current, old)))
    artifacts = source.list_stored_intelligence_artifacts(INSTRUMENT_ID, as_of=T)
    assert {item.domain for item in artifacts} == {IntelligenceEvidenceDomain.TECHNICAL, IntelligenceEvidenceDomain.SETUP_OPPORTUNITY}
    technical = next(item for item in artifacts if item.domain is IntelligenceEvidenceDomain.TECHNICAL)
    assert technical.artifact_id == current.assessment_id
    assert all("CANDIDATE_RECONSTRUCTIBLE_NOT_PERSISTED" in item.warnings for item in artifacts if item.domain is IntelligenceEvidenceDomain.SETUP_OPPORTUNITY)


def test_stored_setup_adapter_excludes_future_and_retains_ineligible_technical_intelligence() -> None:
    prior = assessment(eligible=False, at=T)
    future = assessment(at=T + timedelta(days=1))
    source = GovernedSetupEvidenceStoredSource(_ReadOnlyRepository((future, prior)))
    artifacts = source.list_stored_intelligence_artifacts(INSTRUMENT_ID, as_of=T)
    assert len(artifacts) == 1
    assert artifacts[0].domain is IntelligenceEvidenceDomain.TECHNICAL
    assert artifacts[0].artifact_id == prior.assessment_id
    assert source.list_stored_intelligence_artifacts(INSTRUMENT_ID, as_of=T - timedelta(days=1)) == ()
