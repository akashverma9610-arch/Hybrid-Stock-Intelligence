from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import sqlite3

import pytest

from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionStatus, CanonicalDiagnosticGovernanceLimitation,
    CanonicalDiagnosticStrategyDefinition, CanonicalDiagnosticStrategyDefinitionError,
    semantic_fingerprint_for_payload,
)
from app.domain.models import StrategyVersionReference
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from tests.fixtures.governance_records import strategy_definition


APPROVED_FINGERPRINT = "sha256:3144ec1e9452f24a1e9f3776c77e33cbd59f31459c3e2f7d734c4924bb2b9ee3"
FIXTURE_TIME = datetime(2026, 8, 31, 9, 0, tzinfo=UTC)
LIMITATIONS = (
    CanonicalDiagnosticGovernanceLimitation("StockDiagnosticInputAssembler"),
    CanonicalDiagnosticGovernanceLimitation("BacktestLookaheadGuard"),
    CanonicalDiagnosticGovernanceLimitation("DeterministicDiagnosticEvaluators"),
    CanonicalDiagnosticGovernanceLimitation("NIFTY_50 default benchmark / explicit constructor override"),
    CanonicalDiagnosticGovernanceLimitation("DiagnosticResult / SQLiteStrategyGovernanceRepository"),
    CanonicalDiagnosticGovernanceLimitation(
        "Inline technical, fundamental, valuation, trade, liquidity, crowd, and freshness policy implementations"
    ),
)


def _approved_payload() -> dict:
    proposal = Path(__file__).parents[2] / "docs" / "architecture" / "CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md"
    text = proposal.read_text(encoding="utf-8")
    match = re.search(r"```json\r?\n(\{.*?\})\r?\n```", text, re.S)
    assert match is not None
    return json.loads(match.group(1))


def _definition(
    *, payload: dict | None = None,
    limitations: tuple[CanonicalDiagnosticGovernanceLimitation, ...] = LIMITATIONS,
    registered_at: datetime = FIXTURE_TIME,
) -> CanonicalDiagnosticStrategyDefinition:
    canonical_payload = payload or _approved_payload()
    return CanonicalDiagnosticStrategyDefinition(
        strategy_id="canonical-universe-analysis", strategy_version="v1",
        canonical_payload=canonical_payload, semantic_fingerprint=semantic_fingerprint_for_payload(canonical_payload),
        governance_limitations=limitations, definition_status=CanonicalDiagnosticDefinitionStatus.APPROVED,
        reviewer_id="human:Akash-Verma",
        definition_proposal_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_DEFINITION_PROPOSAL.md",
        human_approval_artifact="docs/architecture/CANONICAL_UNIVERSE_ANALYSIS_V1_APPROVAL.md",
        created_at=FIXTURE_TIME, registered_at=registered_at,
    )


def test_approved_payload_has_stable_serialization_and_exact_fingerprint() -> None:
    payload = _approved_payload()
    definition = _definition(payload=payload)

    assert semantic_fingerprint_for_payload(payload) == APPROVED_FINGERPRINT
    assert definition.semantic_fingerprint == APPROVED_FINGERPRINT
    assert definition.canonical_payload_serialization == json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    assert definition.canonical_payload["diagnostic_registry"]["rule_ids"] == tuple(range(1, 62))


def test_invalid_fingerprint_and_non_json_payload_fail_closed() -> None:
    payload = _approved_payload()
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="fingerprint"):
        replace(_definition(payload=payload), semantic_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="JSON-compatible"):
        _definition(payload={"not-json": object()})


def test_limitations_are_immutable_and_order_deterministic() -> None:
    definition = _definition(limitations=tuple(reversed(LIMITATIONS)))

    assert definition.governance_limitations == tuple(sorted(LIMITATIONS))
    with pytest.raises((AttributeError, TypeError)):
        definition.governance_limitations += (CanonicalDiagnosticGovernanceLimitation("new"),)  # type: ignore[misc]


def test_save_get_reopen_and_identical_retry_are_immutable_and_idempotent(tmp_path) -> None:
    database = tmp_path / "canonical-governance.db"
    first = _definition()
    repository = SQLiteStrategyGovernanceRepository(database)
    assert repository.save_canonical_diagnostic_strategy_definition(first) == first
    retried = replace(first, registered_at=FIXTURE_TIME + timedelta(minutes=5))
    assert repository.save_canonical_diagnostic_strategy_definition(retried) == first
    repository.close()

    reopened = SQLiteStrategyGovernanceRepository(database)
    assert reopened.get_canonical_diagnostic_strategy_definition(first.reference) == first
    assert reopened.list_canonical_diagnostic_strategy_definitions() == (first,)
    reopened.close()


def test_conflicting_identity_version_and_payload_are_rejected(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "conflict.db")
    first = _definition()
    repository.save_canonical_diagnostic_strategy_definition(first)
    changed_payload = _approved_payload()
    changed_payload["thresholds"]["trend"]["fast_sma_period"] = 999
    with pytest.raises(ValueError, match="immutable"):
        repository.save_canonical_diagnostic_strategy_definition(_definition(payload=changed_payload))
    repository.close()


def test_exact_requirement_rejects_missing_fingerprint_payload_and_limitations(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "require.db")
    definition = _definition()
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="missing"):
        repository.require_canonical_diagnostic_strategy_definition(
            reference=definition.reference, semantic_fingerprint=definition.semantic_fingerprint,
            canonical_payload=definition.canonical_payload, governance_limitations=definition.governance_limitations,
        )
    repository.save_canonical_diagnostic_strategy_definition(definition)
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="fingerprint"):
        repository.require_canonical_diagnostic_strategy_definition(
            reference=definition.reference, semantic_fingerprint="sha256:" + "1" * 64,
            canonical_payload=definition.canonical_payload, governance_limitations=definition.governance_limitations,
        )
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="limitations"):
        repository.require_canonical_diagnostic_strategy_definition(
            reference=definition.reference, semantic_fingerprint=definition.semantic_fingerprint,
            canonical_payload=definition.canonical_payload, governance_limitations=LIMITATIONS[:-1],
        )
    repository.close()


def test_stored_payload_and_limitations_tampering_fail_closed(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "tamper.db")
    definition = _definition()
    repository.save_canonical_diagnostic_strategy_definition(definition)
    repository._connection.execute(  # isolated test fixture: emulate corruption outside the repository contract
        "UPDATE canonical_diagnostic_strategy_definitions SET canonical_payload_json = ?",
        (json.dumps({"tampered": True}),),
    )
    repository._connection.commit()
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="fingerprint"):
        repository.get_canonical_diagnostic_strategy_definition(definition.reference)
    repository.close()

    repository = SQLiteStrategyGovernanceRepository(tmp_path / "limitations-tamper.db")
    repository.save_canonical_diagnostic_strategy_definition(definition)
    repository._connection.execute(
        "UPDATE canonical_diagnostic_strategy_definitions SET governance_limitations_json = ?",
        (json.dumps([{"dependency": "tampered", "classification": "UNVERSIONED_DEPENDENCY"}]),),
    )
    repository._connection.commit()
    with pytest.raises(CanonicalDiagnosticStrategyDefinitionError, match="limitations"):
        repository.require_canonical_diagnostic_strategy_definition(
            reference=definition.reference, semantic_fingerprint=definition.semantic_fingerprint,
            canonical_payload=definition.canonical_payload, governance_limitations=definition.governance_limitations,
        )
    repository.close()


def test_lineage_and_existing_generic_strategy_governance_are_isolated(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "isolated.db")
    definition = _definition()
    stored = repository.save_canonical_diagnostic_strategy_definition(definition)
    generic = strategy_definition()
    repository.save_strategy_definition(generic)

    assert stored.reviewer_id == "human:Akash-Verma"
    assert stored.definition_proposal_artifact.endswith("DEFINITION_PROPOSAL.md")
    assert stored.human_approval_artifact.endswith("APPROVAL.md")
    assert repository.get_strategy_definition(generic.reference) == generic
    repository.close()


def test_additive_schema_is_reopen_safe_for_an_existing_database(tmp_path) -> None:
    database = tmp_path / "existing.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE strategy_versions (strategy_id TEXT NOT NULL, version TEXT NOT NULL, PRIMARY KEY (strategy_id, version))")
    connection.commit()
    connection.close()

    repository = SQLiteStrategyGovernanceRepository(database)
    tables = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "strategy_versions" in tables
    assert "canonical_diagnostic_strategy_definitions" in tables
    repository.close()
