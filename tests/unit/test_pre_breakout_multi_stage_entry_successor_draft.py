from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.strategies.pre_breakout.policy import (
    ActualExecutionPriceMethod,
    BreakoutTriggerRole,
    EntryReferenceMethod,
    ExecutableEntryGridMethod,
    MaximumAcceptableEntryMethod,
    PreBreakoutRiskRewardBasis,
    prebreakout_policy_governance_drafts,
    prebreakout_policy_v1_2_structural_successor_draft,
    prebreakout_policy_v1_3_multi_stage_entry_successor_draft,
)
from app.strategies.pre_breakout.policy_serialization import (
    multi_stage_entry_successor_draft_from,
    multi_stage_entry_successor_draft_to,
)


V12_FINGERPRINT = "c297513b6edd2da8e85dc5ceebd31c882527b8165118e964531c93d6dfdb5aef"
TRIGGER = Decimal("500")
SUPPORT = Decimal("450")
TICK = Decimal("0.05")
TARGET = Decimal("550")


def _rule():
    return prebreakout_policy_v1_3_multi_stage_entry_successor_draft().multi_stage_entry


def test_v13_is_new_unselected_successor_and_v12_is_unchanged() -> None:
    v12 = prebreakout_policy_v1_2_structural_successor_draft()
    v13 = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()

    assert v12.fingerprint == V12_FINGERPRINT
    assert v13.policy_id == v12.policy_id == "pre-breakout-policy-v1"
    assert v13.version == "v1.3-draft"
    assert v13.status == "DRAFT_REQUIRES_HUMAN_APPROVAL"
    assert v13.fingerprint != v12.fingerprint
    assert [item.version for item in prebreakout_policy_governance_drafts()] == [
        "v1-draft", "v1.1-draft", "v1.2-draft", "v1.3-draft",
    ]


def test_v13_separates_factual_entry_reference_execution_and_confirmation() -> None:
    rule = _rule()

    assert rule.entry_reference_method is EntryReferenceMethod.EVALUATION_SESSION_CANONICAL_CLOSE
    assert rule.entry_reference_is_factual_not_fill and rule.entry_reference_is_not_order_price
    assert rule.actual_execution_price_method is ActualExecutionPriceMethod.LATER_OBSERVED_REVALIDATED_PRICE
    assert rule.actual_execution_price_is_later_factual_value and rule.actual_execution_revalidation_required
    assert rule.breakout_trigger_role is BreakoutTriggerRole.CONFIRMATION_NOT_INITIAL_ENTRY
    assert rule.breakout_trigger_is_not_initial_entry
    assert rule.maximum_executable_entry_is_not_order_price and rule.maximum_executable_entry_is_not_assumed_fill


def test_exact_ceiling_and_conservative_tick_floor_examples() -> None:
    rule = _rule()

    assert rule.maximum_acceptable_entry_method is MaximumAcceptableEntryMethod.MIN_RR_ANALYTIC_CEILING
    assert rule.maximum_acceptable_entry_price(trigger=TRIGGER, support=SUPPORT, tick_size=TICK) == Decimal("474.9625")
    assert rule.executable_entry_grid_method is ExecutableEntryGridMethod.CONSERVATIVE_TICK_FLOOR
    assert rule.maximum_executable_entry_price(trigger=TRIGGER, support=SUPPORT, tick_size=TICK) == Decimal("474.95")

    assert rule.conservative_tick_floor(ceiling=Decimal("474.95"), tick_size=TICK) == Decimal("474.95")
    assert rule.conservative_tick_floor(ceiling=Decimal("474.9625"), tick_size=TICK) == Decimal("474.95")


def test_ceiling_boundaries_and_reference_geometry_fail_closed() -> None:
    rule = _rule()

    assert rule.maximum_executable_entry_price(trigger=TRIGGER, support=SUPPORT, tick_size=TICK) > SUPPORT - TICK
    assert rule.maximum_executable_entry_price(trigger=TRIGGER, support=SUPPORT, tick_size=TICK) < TRIGGER
    with pytest.raises(ValueError, match="ENTRY_PRICE_TOO_HIGH"):
        rule.reference_reward_risk(entry_reference_price=Decimal("475"), trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET)
    with pytest.raises(ValueError, match="PRE_BREAKOUT_ENTRY_NOT_AVAILABLE"):
        rule.reference_reward_risk(entry_reference_price=TRIGGER, trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET)
    with pytest.raises(ValueError, match="INVALID_PRE_BREAKOUT_ENTRY_GEOMETRY"):
        rule.reference_reward_risk(entry_reference_price=SUPPORT - TICK, trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET)


def test_reference_rr_uses_entry_reference_not_trigger_and_actual_fill_is_revalidated() -> None:
    rule = _rule()

    assert rule.reference_reward_risk(entry_reference_price=Decimal("470"), trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET) > Decimal("3.99")
    assert rule.reference_reward_risk(entry_reference_price=Decimal("474.95"), trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET) > Decimal("3")
    with pytest.raises(ValueError, match="ENTRY_PRICE_TOO_HIGH"):
        rule.validate_actual_execution_price(actual_execution_price=Decimal("475"), trigger=TRIGGER, support=SUPPORT, tick_size=TICK, target=TARGET)


def test_no_stop_target_or_friction_semantic_manipulation_is_allowed() -> None:
    draft = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()
    rule = draft.multi_stage_entry

    assert draft.target_support_binding.target_may_be_moved_to_manufacture_reward_risk is False
    assert draft.structural_stop.method.value == "SUPPORT_MINUS_ONE_GOVERNED_TICK"
    assert rule.reward_risk_basis is PreBreakoutRiskRewardBasis.GROSS_STRUCTURAL_PRICE_RR
    assert rule.transaction_friction_handling == "INDEPENDENT_MANDATORY_EXECUTION_GATE"
    assert rule.do_not_chase and rule.price_too_high_status == "ENTRY_PRICE_TOO_HIGH"
    assert draft.unresolved_fields == () and draft.policy_fully_resolved and not draft.policy_semantic_conflict


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: replace(value, multi_stage_entry=replace(value.multi_stage_entry, upward_rounding_allowed=True)),
        lambda value: replace(value, multi_stage_entry=replace(value.multi_stage_entry, executable_entry_grid_method=ExecutableEntryGridMethod.CONSERVATIVE_TICK_FLOOR, do_not_chase=False)),
        lambda value: replace(value, multi_stage_entry=replace(value.multi_stage_entry, actual_execution_revalidation_required=False)),
    ),
)
def test_every_v13_semantic_change_changes_fingerprint(mutate) -> None:
    draft = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()
    assert mutate(draft).fingerprint != draft.fingerprint


def test_v13_round_trip_preserves_typed_semantics_and_tampering_fails_closed() -> None:
    draft = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()
    payload = multi_stage_entry_successor_draft_to(draft)

    restored = multi_stage_entry_successor_draft_from(payload)
    assert restored == draft
    assert isinstance(restored.multi_stage_entry.entry_reference_method, EntryReferenceMethod)
    assert isinstance(restored.multi_stage_entry.executable_entry_grid_method, ExecutableEntryGridMethod)

    payload = multi_stage_entry_successor_draft_to(draft)
    payload["multi_stage_entry"]["upward_rounding_allowed"] = True
    with pytest.raises(ValueError, match="SERIALIZATION_INVALID"):
        multi_stage_entry_successor_draft_from(payload)

    payload = multi_stage_entry_successor_draft_to(draft)
    payload["multi_stage_entry"]["executable_entry_grid_method"] = "NEAREST_TICK"
    with pytest.raises(ValueError, match="SERIALIZATION_INVALID"):
        multi_stage_entry_successor_draft_from(payload)


def test_v13_is_pure_domain_data_with_no_repository_provider_or_runtime_materializer() -> None:
    draft = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()
    assert "sqlite" not in type(draft).__module__.lower()
    assert "network" not in type(draft).__module__.lower()
    assert not any(hasattr(draft, name) for name in ("candidate", "signal", "trade", "order", "materialize"))
