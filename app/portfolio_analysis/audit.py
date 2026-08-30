"""Internal registry audit. This module is intentionally never an API schema."""
from __future__ import annotations

from dataclasses import dataclass

from app.registry.canonical import DIAGNOSTIC_RULES, DIAGNOSTIC_REGISTRY_VERSION


@dataclass(frozen=True, slots=True)
class DiagnosticRegistryAudit:
    registry_version: str
    canonical_count: int
    unique_ids: bool
    evaluator_wrapper_count: int
    end_to_end_portfolio_pipeline_count: int
    all_61_executable: bool
    gap: str | None


# `DeterministicDiagnosticEvaluators` contains wrappers for all registry IDs,
# while the currently wired historical replay intentionally invokes this narrow
# deterministic subset. There is no live holdings-wide 61-rule orchestrator.
HISTORICAL_REPLAY_EXECUTED_RULE_IDS = frozenset({1, 4, 5, 6, 10, 39})


def diagnostic_registry_audit() -> DiagnosticRegistryAudit:
    ids = tuple(rule.rule_id for rule in DIAGNOSTIC_RULES)
    canonical = tuple(range(1, 62))
    return DiagnosticRegistryAudit(
        registry_version=DIAGNOSTIC_REGISTRY_VERSION,
        canonical_count=len(DIAGNOSTIC_RULES),
        unique_ids=len(set(ids)) == len(ids) and ids == canonical,
        evaluator_wrapper_count=61,
        end_to_end_portfolio_pipeline_count=len(HISTORICAL_REPLAY_EXECUTED_RULE_IDS),
        all_61_executable=False,
        gap="No current live holdings-wide orchestrator assembles all 61 rule inputs and evaluators; missing evidence must remain partial.",
    )
