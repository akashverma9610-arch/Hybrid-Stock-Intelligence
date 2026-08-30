from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.brain_output_requirement_policy import (
    BrainOutputContextRequirement,
    CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY,
    create_brain_output_requirement_policy,
)
from app.gates.engine import ActionContext
from app.intelligence.unified_state import BrainOutputContext


POLICY = CURRENT_BRAIN_OUTPUT_REQUIREMENT_POLICY


def _requirement(context: BrainOutputContext) -> BrainOutputContextRequirement:
    return POLICY.requirement_for(context)


def _replacement_policy(*, requirement: BrainOutputContextRequirement, version: str = "v1"):
    return create_brain_output_requirement_policy(
        policy_id=POLICY.policy_id,
        version=version,
        requirements=tuple(
            requirement if item.output_context is requirement.output_context else item
            for item in POLICY.requirements
        ),
    )


def test_complete_explicit_seven_context_registry_is_canonical_and_deterministic():
    assert tuple(item.output_context for item in POLICY.requirements) == tuple(
        sorted(BrainOutputContext, key=lambda value: value.value)
    )
    assert {item.output_context for item in POLICY.requirements} == set(BrainOutputContext)
    recreated = create_brain_output_requirement_policy(
        policy_id=POLICY.policy_id, version=POLICY.version, requirements=POLICY.requirements,
    )
    assert recreated == POLICY


@pytest.mark.parametrize("changes", [
    {"requires_decision_score": False},
    {"requires_six_gates": False, "requires_action_context": False, "required_action_context": None},
    {"requires_portfolio_context": True},
    {"required_action_context": ActionContext.ROTATE_IN},
    {"informational_only": True, "output_decision_capable": False},
    {"output_decision_capable": False},
])
def test_each_semantic_requirement_change_changes_policy_fingerprint(changes):
    original = _requirement(BrainOutputContext.ENTRY_SETUP_REVIEW)
    changed = replace(original, **changes)
    assert _replacement_policy(requirement=changed).fingerprint != POLICY.fingerprint


def test_deep_analysis_is_state_only_and_informational():
    value = _requirement(BrainOutputContext.DEEP_ANALYSIS)
    assert value.requires_unified_state is True
    assert not any((value.requires_decision_score, value.requires_six_gates,
                    value.requires_portfolio_context, value.requires_action_context))
    assert value.required_action_context is None
    assert value.informational_only is True and value.output_decision_capable is False


@pytest.mark.parametrize(("context", "score", "gates", "portfolio", "action", "informational"), [
    (BrainOutputContext.OPPORTUNITY_DISCOVERY, True, True, False, ActionContext.FRESH_ENTRY, False),
    (BrainOutputContext.PORTFOLIO_REVIEW, False, False, True, None, True),
    (BrainOutputContext.SELL_TRIM_REVIEW, False, False, True, None, True),
    (BrainOutputContext.ROTATION_REVIEW, True, True, True, ActionContext.ROTATE_IN, False),
    (BrainOutputContext.ENTRY_SETUP_REVIEW, True, True, False, ActionContext.FRESH_ENTRY, False),
    (BrainOutputContext.ALERT_REVIEW, False, False, False, None, True),
])
def test_governed_context_semantics(context, score, gates, portfolio, action, informational):
    value = _requirement(context)
    assert value.requires_unified_state is True
    assert value.requires_decision_score is score
    assert value.requires_six_gates is gates
    assert value.requires_portfolio_context is portfolio
    assert value.requires_action_context is gates
    assert value.required_action_context is action
    assert value.informational_only is informational
    assert value.output_decision_capable is not informational


def test_broad_review_contexts_are_not_collapsed_to_concrete_gate_actions():
    for context in (BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.SELL_TRIM_REVIEW):
        value = _requirement(context)
        assert value.required_action_context is None
        assert value.informational_only is True


def test_invalid_action_requirement_combinations_fail_closed():
    with pytest.raises(ValueError, match="ACTION_CONTEXT_INCONSISTENT"):
        BrainOutputContextRequirement(
            BrainOutputContext.DEEP_ANALYSIS, True, False, False, False, True,
            None, True, False,
        )
    with pytest.raises(ValueError, match="GATE_ACTION_INCONSISTENT"):
        BrainOutputContextRequirement(
            BrainOutputContext.DEEP_ANALYSIS, True, False, True, False, False,
            None, True, False,
        )


def test_policy_has_no_engine_execution_network_persistence_or_action_output_surface():
    source = (Path(__file__).parents[2] / "app" / "brain_output_requirement_policy.py").read_text(encoding="utf-8")
    assert not any(token in source for token in (
        "build_scorecard", "evaluate_six_gates", "Canonical61DiagnosticRunner", "requests.",
        "urlopen", "httpx", "CREATE TABLE", "INSERT INTO", "Signal", "PaperTrade", "order(",
        "recommended_action",
    ))
