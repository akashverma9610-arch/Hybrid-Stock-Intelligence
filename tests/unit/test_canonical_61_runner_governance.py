from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
import re

import pytest

from app.domain.canonical_diagnostic_strategy import (
    CANONICAL_61_SEMANTIC_FINGERPRINT, CANONICAL_61_STRATEGY_REFERENCE,
    CanonicalDiagnosticDefinitionStatus, CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition, require_canonical_61_runner_authorization,
    semantic_fingerprint_for_payload,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler
from tests.fixtures.analytical_observations import ANALYSIS_TIME, bars


class StoredFacts:
    def __init__(self, values): self.values = tuple(values)
    def observations_as_of(self, at): return tuple(item for item in self.values if item.provenance.retrieved_timestamp <= at)


def _definition(*, payload: dict | None = None) -> CanonicalDiagnosticStrategyDefinition:
    root = Path(__file__).parents[2]
    parse = lambda path: json.loads(re.search(r"```json\r?\n(\{.*?\})\r?\n```", path.read_text(encoding="utf-8"), re.S).group(1))
    approved_payload = payload or parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md")
    approval = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md")
    return CanonicalDiagnosticStrategyDefinition(
        strategy_id=approved_payload["strategy"]["id"], strategy_version=approved_payload["strategy"]["version"],
        canonical_payload=approved_payload, semantic_fingerprint=semantic_fingerprint_for_payload(approved_payload),
        governance_limitations=tuple(CanonicalDiagnosticGovernanceLimitation(**item) for item in approval["governance_limitations"]),
        definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED, reviewer_id=approval["reviewer"],
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=datetime(2026, 8, 31, tzinfo=UTC), registered_at=datetime(2026, 8, 31, tzinfo=UTC),
    )


def _repository(tmp_path, definition: CanonicalDiagnosticStrategyDefinition | None = None, name: str = "governance.db"):
    value = SQLiteStrategyGovernanceRepository(tmp_path / name)
    if definition is not None:
        value.save_canonical_diagnostic_strategy_definition(definition)
    return value


def _evidence():
    instrument = NseEquityInstrument("NSE:TEST", "TEST", None, "Industrials", None, "ACTIVE", None, True,
                                     ANALYSIS_TIME, "official", "fixture:NSE:TEST")
    values = bars("NSE:TEST", [10, 11, 12, 13, 14, 15], volumes=[10, 11, 12, 13, 14, 15])
    values += bars("NIFTY_50", [100, 101, 102, 103, 104, 105])
    return StockDiagnosticInputAssembler(StoredFacts(values)).assemble(instrument, ANALYSIS_TIME)


def test_exact_approved_definition_authorizes_and_preserves_all_six_limitations(tmp_path):
    definition = _definition()
    repository = _repository(tmp_path, definition, "limitations.db")
    resolved = Canonical61DiagnosticRunner().authorize(repository)
    assert resolved.reference == CANONICAL_61_STRATEGY_REFERENCE
    assert resolved.semantic_fingerprint == CANONICAL_61_SEMANTIC_FINGERPRINT
    assert len(resolved.governance_limitations) == 6
    assert {item.classification for item in resolved.governance_limitations} == {"UNVERSIONED_DEPENDENCY"}
    repository.close()


def test_missing_wrong_identity_version_and_fingerprint_block_runner(tmp_path):
    missing = _repository(tmp_path)
    with pytest.raises(ValueError, match="exact registered"):
        Canonical61DiagnosticRunner().authorize(missing)
    with pytest.raises(ValueError, match="canonical-universe-analysis / v1"):
        Canonical61DiagnosticRunner(strategy=type(CANONICAL_61_STRATEGY_REFERENCE)("other", "v1")).authorize(missing)
    with pytest.raises(ValueError, match="canonical-universe-analysis / v1"):
        Canonical61DiagnosticRunner(strategy=type(CANONICAL_61_STRATEGY_REFERENCE)("canonical-universe-analysis", "v2")).authorize(missing)
    missing.close()

    payload = dict(_definition().canonical_payload)
    payload["analysis_kind"] = "different-canonical-analysis"
    repository = _repository(tmp_path, _definition(payload=payload))
    with pytest.raises(ValueError, match="semantic fingerprint mismatch"):
        Canonical61DiagnosticRunner().authorize(repository)
    repository.close()


def test_payload_limitations_and_nonapproved_tampering_fail_closed(tmp_path):
    definition = _definition()
    repository = _repository(tmp_path, definition)
    repository._connection.execute(
        "UPDATE canonical_diagnostic_strategy_definitions SET canonical_payload_json = ?", (json.dumps({"tampered": True}),)
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="fingerprint"):
        Canonical61DiagnosticRunner().authorize(repository)
    repository.close()

    repository = _repository(tmp_path, definition, "limitations.db")
    repository._connection.execute(
        "UPDATE canonical_diagnostic_strategy_definitions SET governance_limitations_json = ?",
        (json.dumps([{"dependency": "tampered", "classification": "UNVERSIONED_DEPENDENCY"}]),),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="limitations mismatch"):
        Canonical61DiagnosticRunner().authorize(repository)
    repository.close()

    class UnapprovedReader:
        def get_canonical_diagnostic_strategy_definition(self, reference):
            return replace(definition, definition_status="draft")

    with pytest.raises(ValueError, match="approved"):
        require_canonical_61_runner_authorization(UnapprovedReader(), CANONICAL_61_STRATEGY_REFERENCE)


def test_governed_execution_is_rule_equivalent_to_the_existing_pure_runner(tmp_path):
    repository = _repository(tmp_path, _definition())
    evidence = _evidence()
    runner = Canonical61DiagnosticRunner()
    pure = runner.run(evidence)
    governed = runner.run(evidence, governance=repository)
    assert governed == pure
    assert tuple(item.canonical_rule_id for item in governed.evaluations) == tuple(range(1, 62))
    repository.close()
