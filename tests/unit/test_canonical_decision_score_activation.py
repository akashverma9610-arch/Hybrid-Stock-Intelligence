from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re

import pytest

from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionStatus, CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition, governance_limitations_fingerprint,
    semantic_fingerprint_for_payload,
)
from app.domain.models import canonical_diagnostic_result
from app.intelligence.company_evidence import CompositeStoredIntelligenceSource
from app.intelligence.decision_score_evidence import (
    CanonicalDecisionScorecardSource, DecisionScoreEvidenceStoredSource,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact, UnifiedIntelligenceStateBuilder
from app.domain.models import FreshnessStatus
from app.portfolio.canonical_decision_score_activation import CanonicalPortfolioDecisionScoreActivator
from app.portfolio.canonical_diagnostics_orchestration import PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
from app.registry.canonical import get_diagnostic_rule
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository


T = datetime(2026, 8, 31, 18, 21, 20, 437011, tzinfo=UTC)


class _Historical:
    def latest(self, instrument_id, timeframe, count, *, as_of=None):
        return (type("Bar", (), {"start_time": T - timedelta(days=4)})(),)


class _Core:
    def list_stored_intelligence_artifacts(self, canonical_instrument_id, *, as_of):
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id=f"instrument:{canonical_instrument_id}", artifact_fingerprint="identity",
            availability=IntelligenceEvidenceAvailability.AVAILABLE, evidence_as_of=as_of,
            observed_at=as_of, available_at=as_of, freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None, source_provenance_fingerprint=None,
            historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


def _definition() -> CanonicalDiagnosticStrategyDefinition:
    root = Path(__file__).parents[2]
    parse = lambda path: json.loads(re.search(
        r"```json\r?\n(\{.*?\})\r?\n```", path.read_text(encoding="utf-8"), re.S,
    ).group(1))
    payload = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md")
    approval = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md")
    return CanonicalDiagnosticStrategyDefinition(
        strategy_id=payload["strategy"]["id"], strategy_version=payload["strategy"]["version"],
        canonical_payload=payload, semantic_fingerprint=semantic_fingerprint_for_payload(payload),
        governance_limitations=tuple(CanonicalDiagnosticGovernanceLimitation(**item) for item in approval["governance_limitations"]),
        definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED, reviewer_id=approval["reviewer"],
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=T, registered_at=T,
    )


def _repository(tmp_path, *, missing: dict[str, tuple[int, ...]] | None = None):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "canonical-score.db")
    definition = _definition()
    repository.save_canonical_diagnostic_strategy_definition(definition)
    limitation_fingerprint = governance_limitations_fingerprint(definition.governance_limitations)
    for instrument_id in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS:
        for rule_id in range(1, 62):
            result = "INSUFFICIENT_DATA" if rule_id in (missing or {}).get(instrument_id, ()) else "VALID"
            repository.save_diagnostic_result(canonical_diagnostic_result(
                id=f"diagnostic:{instrument_id}:{rule_id}", instrument_id=instrument_id,
                rule_id=str(rule_id), strategy_version=definition.reference,
                canonical_strategy_fingerprint=definition.semantic_fingerprint,
                canonical_limitations_fingerprint=limitation_fingerprint,
                result=result, score=None, confidence=0.8, evidence_ids=(f"evidence:{rule_id}",),
                input_observation_ids=(f"observation:{rule_id}",), evaluated_at=T, as_of_timestamp=T,
            ))
    return repository


def _activate(repository):
    return CanonicalPortfolioDecisionScoreActivator(governance=repository, historical=_Historical()).materialize()


def test_only_complete_canonical_scores_persist_and_reopen_with_typed_fk(tmp_path) -> None:
    repository = _repository(tmp_path, missing={
        "NSE:INE955D01029": (45,), "NSE:INE090A01021": (24, 29, 45),
    })
    run = _activate(repository)
    assert [item.status for item in run.outcomes] == ["CREATED", "CREATED", "INELIGIBLE", "CREATED", "INELIGIBLE"]
    assert len(repository.list_canonical_decision_scorecards()) == 3
    assert repository._connection.execute("SELECT COUNT(*) FROM strategy_versions").fetchone()[0] == 0
    assert repository._connection.execute("SELECT COUNT(*) FROM decision_scorecards").fetchone()[0] == 0
    foreign_keys = repository._connection.execute("PRAGMA foreign_key_list(canonical_decision_scorecards)").fetchall()
    assert {(row[2], row[3], row[4]) for row in foreign_keys} == {
        ("canonical_diagnostic_strategy_definitions", "strategy_id", "strategy_id"),
        ("canonical_diagnostic_strategy_definitions", "strategy_version", "strategy_version"),
    }
    repository.close()
    reopened = SQLiteStrategyGovernanceRepository(tmp_path / "canonical-score.db")
    assert len(reopened.list_canonical_decision_scorecards()) == 3
    assert all(item.latest_completed_market_session == T - timedelta(days=4) for item in reopened.list_canonical_decision_scorecards())
    reopened.close()


def test_incomplete_holdings_surface_exact_canonical_rule_requirements(tmp_path) -> None:
    repository = _repository(tmp_path, missing={
        "NSE:INE955D01029": (45,), "NSE:INE090A01021": (24, 29, 45),
    })
    outcomes = {item.instrument_id: item for item in _activate(repository).outcomes}
    genus = outcomes["NSE:INE955D01029"]
    icici = outcomes["NSE:INE090A01021"]
    assert [(item.rule_id, item.rule_name, item.required_inputs, item.upstream_domain) for item in genus.blockers] == [
        (45, get_diagnostic_rule(45).canonical_name, get_diagnostic_rule(45).required_inputs, "MARKET_TECHNICAL"),
    ]
    assert [item.rule_id for item in icici.blockers] == [24, 29, 45]
    assert [item.upstream_domain for item in icici.blockers] == ["FINANCIAL_EARNINGS", "FINANCIAL_EARNINGS", "MARKET_TECHNICAL"]
    repository.close()


def test_second_activation_is_identical_and_does_not_duplicate_canonical_history(tmp_path) -> None:
    repository = _repository(tmp_path, missing={
        "NSE:INE955D01029": (45,), "NSE:INE090A01021": (24, 29, 45),
    })
    first = _activate(repository)
    second = _activate(repository)
    assert [item.status for item in first.outcomes] == ["CREATED", "CREATED", "INELIGIBLE", "CREATED", "INELIGIBLE"]
    assert [item.status for item in second.outcomes] == ["IDENTICAL", "IDENTICAL", "INELIGIBLE", "IDENTICAL", "INELIGIBLE"]
    assert len(repository.list_canonical_decision_scorecards()) == 3
    assert repository._connection.execute("SELECT COUNT(*) FROM canonical_diagnostic_results").fetchone()[0] == 305
    repository.close()


def test_tampering_and_generic_diagnostic_anchor_are_rejected(tmp_path) -> None:
    repository = _repository(tmp_path)
    card = next(item for item in _activate(repository).outcomes if item.score_id is not None)
    repository._connection.execute(
        "UPDATE canonical_decision_scorecards SET artifact_fingerprint = 'tampered' WHERE id = ?", (card.score_id,),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="fingerprint"):
        repository.get_canonical_decision_scorecard(card.score_id)
    repository.close()


def test_canonical_scores_project_to_shared_brain_at_their_pit_boundary(tmp_path) -> None:
    repository = _repository(tmp_path)
    run = _activate(repository)
    source = DecisionScoreEvidenceStoredSource(CanonicalDecisionScorecardSource(repository))
    state = UnifiedIntelligenceStateBuilder(CompositeStoredIntelligenceSource(_Core(), source)).build(
        "NSE:INE372A01015", as_of=run.intelligence_as_of,
    )
    reference = next(item for item in state.evidence_references if item.domain is IntelligenceEvidenceDomain.DECISION_SCORE)
    assert reference.availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert reference.artifact_ids == (run.outcomes[0].score_id,)
    assert repository._connection.execute("SELECT COUNT(*) FROM execution_gate_evaluations").fetchone()[0] == 0
    repository.close()
