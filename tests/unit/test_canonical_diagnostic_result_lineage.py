from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sqlite3

import pytest

from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionStatus, CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition, governance_limitations_fingerprint,
    semantic_fingerprint_for_payload,
)
from app.domain.models import (
    DiagnosticResult, DiagnosticStrategyLineageType, StrategyVersionReference,
    canonical_diagnostic_result, canonical_diagnostic_result_fingerprint,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.governance_records import GOVERNANCE_TIME, strategy_definition


T = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)


def _approved() -> tuple[CanonicalDiagnosticStrategyDefinition, tuple[CanonicalDiagnosticGovernanceLimitation, ...]]:
    root = Path(__file__).parents[2]
    parse = lambda path: json.loads(re.search(r"```json\r?\n(\{.*?\})\r?\n```", path.read_text(encoding="utf-8"), re.S).group(1))
    payload = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md")
    approval = parse(root / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md")
    limitations = tuple(CanonicalDiagnosticGovernanceLimitation(**item) for item in approval["governance_limitations"])
    definition = CanonicalDiagnosticStrategyDefinition(
        strategy_id=payload["strategy"]["id"], strategy_version=payload["strategy"]["version"],
        canonical_payload=payload, semantic_fingerprint=semantic_fingerprint_for_payload(payload),
        governance_limitations=limitations, definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED,
        reviewer_id=approval["reviewer"],
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=T, registered_at=T,
    )
    return definition, limitations


def _canonical_result(identifier: str = "canonical-result") -> DiagnosticResult:
    definition, limitations = _approved()
    return canonical_diagnostic_result(
        id=identifier, instrument_id="NSE:TEST", rule_id="46", strategy_version=definition.reference,
        canonical_strategy_fingerprint=definition.semantic_fingerprint,
        canonical_limitations_fingerprint=governance_limitations_fingerprint(limitations),
        result="INSUFFICIENT_DATA", score=None, confidence=None, evidence_ids=(), input_observation_ids=(),
        evaluated_at=T, as_of_timestamp=T,
    )


def _repository_with_canonical(
    tmp_path,
    database_name: str = "lineage.db",
) -> SQLiteStrategyGovernanceRepository:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / database_name)
    definition, _ = _approved()
    repository.save_canonical_diagnostic_strategy_definition(definition)
    return repository


def test_historical_generic_diagnostic_results_remain_unchanged(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "generic.db")
    definition = strategy_definition()
    repository.save_strategy_definition(definition)
    result = DiagnosticResult("generic", "NSE:GENERIC", "1", definition.reference, "VALID", None, None, (), (), GOVERNANCE_TIME, GOVERNANCE_TIME)
    repository.save_diagnostic_result(result)
    assert repository.list_diagnostic_results(definition.reference, GOVERNANCE_TIME) == (result,)
    repository.close()


def test_canonical_result_persists_with_exact_typed_lineage_and_no_generic_anchor(tmp_path) -> None:
    repository = _repository_with_canonical(tmp_path)
    result = _canonical_result()
    repository.save_diagnostic_result(result)
    stored = repository.list_diagnostic_results(result.strategy_version, T)
    assert stored == (result,)
    assert stored[0].strategy_lineage_type is DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY
    assert stored[0].canonical_strategy_fingerprint == result.canonical_strategy_fingerprint
    assert stored[0].diagnostic_fingerprint == canonical_diagnostic_result_fingerprint(result)
    assert repository.get_strategy_definition(result.strategy_version) is None
    repository.close()


def test_canonical_fingerprint_payload_and_limitations_tampering_fail_closed(tmp_path) -> None:
    repository = _repository_with_canonical(tmp_path)
    result = _canonical_result()
    with pytest.raises(ValueError, match="semantic fingerprint"):
        repository.save_diagnostic_result(replace(result, canonical_strategy_fingerprint="sha256:" + "1" * 64))

    repository._connection.execute(
        "UPDATE canonical_diagnostic_strategy_definitions SET canonical_payload_json = ?",
        (json.dumps({"tampered": True}),),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="fingerprint"):
        repository.save_diagnostic_result(result)
    repository.close()

    repository = _repository_with_canonical(tmp_path, "limitations.db")
    repository._connection.execute(
        "UPDATE canonical_diagnostic_strategy_definitions SET governance_limitations_json = ?",
        (json.dumps([{"dependency": "tampered", "classification": "UNVERSIONED_DEPENDENCY"}]),),
    )
    repository._connection.commit()
    with pytest.raises(ValueError, match="limitations"):
        repository.save_diagnostic_result(result)
    repository.close()


def test_exactly_one_lineage_and_discriminator_mismatch_are_rejected(tmp_path) -> None:
    repository = _repository_with_canonical(tmp_path)
    canonical = _canonical_result("shared-id")
    generic_definition = strategy_definition()
    repository.save_strategy_definition(generic_definition)
    generic = DiagnosticResult("shared-id", "NSE:TEST", "46", generic_definition.reference, "VALID", None, None, (), (), T, T)
    repository.save_diagnostic_result(generic)
    with pytest.raises(ValueError, match="generic strategy lineage"):
        repository.save_diagnostic_result(canonical)
    canonical_first = _canonical_result("canonical-first")
    repository.save_diagnostic_result(canonical_first)
    with pytest.raises(ValueError, match="canonical diagnostic strategy lineage"):
        repository.save_diagnostic_result(replace(generic, id="canonical-first"))
    with pytest.raises(ValueError, match="cannot carry canonical"):
        repository.save_diagnostic_result(
            replace(generic, id="confused", canonical_strategy_fingerprint=canonical.canonical_strategy_fingerprint)
        )
    with pytest.raises(ValueError, match="existing strategy version"):
        repository.save_diagnostic_result(DiagnosticResult("none", "NSE:TEST", "1", None, "VALID", None, None, (), (), T, T))  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="exact registered"):
        repository.save_diagnostic_result(replace(canonical, strategy_version=generic_definition.reference, id="mismatch"))
    repository.close()


def test_canonical_fingerprint_is_deterministic_and_save_is_idempotent(tmp_path) -> None:
    repository = _repository_with_canonical(tmp_path)
    first = _canonical_result()
    second = _canonical_result()
    assert first.diagnostic_fingerprint == second.diagnostic_fingerprint
    changed_lineage = replace(first, canonical_strategy_fingerprint="sha256:" + "2" * 64)
    changed_lineage = replace(changed_lineage, diagnostic_fingerprint=canonical_diagnostic_result_fingerprint(changed_lineage))
    assert changed_lineage.diagnostic_fingerprint != first.diagnostic_fingerprint
    repository.save_diagnostic_result(first)
    repository.save_diagnostic_result(second)
    assert repository.list_diagnostic_results(first.strategy_version, T) == (first,)
    repository.close()


def test_reopen_and_additive_migration_preserve_historical_and_typed_rows(tmp_path) -> None:
    database = tmp_path / "reopen.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE strategy_versions (strategy_id TEXT NOT NULL, version TEXT NOT NULL, PRIMARY KEY (strategy_id, version))")
    connection.commit()
    connection.close()

    repository = SQLiteStrategyGovernanceRepository(database)
    tables = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"strategy_versions", "diagnostic_results", "canonical_diagnostic_results"} <= tables
    foreign_keys = repository._connection.execute("PRAGMA foreign_key_list(canonical_diagnostic_results)").fetchall()
    assert {(row[2], row[3], row[4]) for row in foreign_keys} == {
        ("canonical_diagnostic_strategy_definitions", "strategy_id", "strategy_id"),
        ("canonical_diagnostic_strategy_definitions", "strategy_version", "strategy_version"),
    }
    definition, _ = _approved()
    repository.save_canonical_diagnostic_strategy_definition(definition)
    result = _canonical_result()
    repository.save_diagnostic_result(result)
    repository.close()

    reopened = SQLiteStrategyGovernanceRepository(database)
    assert reopened.list_diagnostic_results(result.strategy_version, T) == (result,)
    assert reopened.get_strategy_definition(result.strategy_version) is None
    reopened.close()
