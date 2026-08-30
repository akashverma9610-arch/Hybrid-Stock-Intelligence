from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.strategies.pre_breakout.policy import (
    PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS,
    BaseTopSource,
    BaseWindowCandidateKind,
    BaseWindowFailureStatus,
    BaseWindowSelectionMethod,
    EqualBaseTopLineage,
    PreBreakoutPolicySelectionContext,
    SupportBreachComparison,
    SupportPivotMethod,
    TargetSupportBindingStatus,
    TickGridMethod,
    TickSourceMethod,
    prebreakout_policy_governance_drafts,
    prebreakout_policy_v1_1_volume_successor_draft,
    prebreakout_policy_v1_2_structural_successor_draft,
)
from app.strategies.pre_breakout.policy_serialization import (
    structural_successor_draft_from,
    structural_successor_draft_to,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.policy import PreBreakoutPolicyApprovalDecision


V1_1_FINGERPRINT = "d61d2c51cf9af96fbee450d35b32354f688b89dc8bccba62592e761cdf39920d"
V1_2_UNBOUND_FINGERPRINT = "5d107087fc7b4d6660c7f2c65945ca2b61b6e598c0f5497e6b35d489f926beef"
T = datetime(2026, 8, 28, 12, tzinfo=UTC)


def test_v12_is_registered_as_an_unselected_successor_and_v11_fingerprint_is_unchanged() -> None:
    v11 = prebreakout_policy_v1_1_volume_successor_draft()
    successor = prebreakout_policy_v1_2_structural_successor_draft()
    drafts = prebreakout_policy_governance_drafts()

    assert v11.fingerprint == V1_1_FINGERPRINT
    assert successor.policy_id == v11.policy_id == "pre-breakout-policy-v1"
    assert successor.version == "v1.2-draft"
    assert successor.status == "DRAFT_REQUIRES_HUMAN_APPROVAL"
    assert successor.fingerprint != v11.fingerprint
    assert successor.fingerprint != V1_2_UNBOUND_FINGERPRINT
    assert [item.version for item in drafts] == ["v1-draft", "v1.1-draft", "v1.2-draft", "v1.3-draft"]
    assert PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN.value == "CURRENT_STORED_SCAN"


def test_constructing_v12_draft_never_changes_a_current_v11_selection(tmp_path) -> None:
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "governance.sqlite"))
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    commands.approve(
        approval_id="v1-approval", policy_id="pre-breakout-policy-v1-draft", policy_version="v1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(seconds=2),
    )
    commands.approve(
        approval_id="v11-approval", policy_id="pre-breakout-policy-v1", policy_version="v1.1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:tester", reviewed_at=T - timedelta(seconds=1),
    )
    commands.select_for_current_stored_scan(
        selection_id="v11-selection", approval_id="v11-approval", selected_by="human:tester", selected_at=T, effective_from=T,
    )
    governance = PreBreakoutPolicyGovernanceService(repository)
    before = governance.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T)
    approval_count = len(repository.list_prebreakout_policy_approvals())
    selection_count = len(repository.list_prebreakout_policy_selections())

    draft = prebreakout_policy_v1_2_structural_successor_draft()
    after = governance.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T)

    assert draft.status == "DRAFT_REQUIRES_HUMAN_APPROVAL"
    assert before is not None and after is not None
    assert after.policy.version == "v1.1-draft" and after.policy_fingerprint == V1_1_FINGERPRINT
    assert len(repository.list_prebreakout_policy_approvals()) == approval_count
    assert len(repository.list_prebreakout_policy_selections()) == selection_count


def test_base_validity_and_top_semantics_are_exactly_encoded_without_range_cap() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    rule = draft.base_window_validity
    top = draft.base_top_definition

    assert rule.candidate_kind is BaseWindowCandidateKind.SUFFIX_ENDING_AT_EVALUATION
    assert (rule.minimum_canonical_sessions, rule.maximum_canonical_sessions) == (20, 60)
    assert rule.require_consecutive_eligible_canonical_sessions
    assert rule.require_evaluation_session_included and rule.require_window_end_at_evaluation
    assert (rule.minimum_confirmed_pivot_highs, rule.minimum_confirmed_pivot_lows) == (2, 2)
    assert rule.require_latest_two_pivot_lows_non_decreasing
    assert rule.require_evaluation_close_at_or_below_base_top
    assert rule.no_valid_window_status is BaseWindowFailureStatus.NO_VALID_WINDOW
    assert rule.maximum_range_pct is None
    assert top.source is BaseTopSource.MAXIMUM_CONFIRMED_PIVOT_HIGH
    assert top.equal_maximum_lineage is EqualBaseTopLineage.MOST_RECENT_EQUAL_MAXIMUM_PIVOT
    assert top.pivot_must_be_inside_candidate_window and not top.raw_session_high_allowed


def test_conservative_selection_and_current_structural_support_are_exactly_encoded() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    selection = draft.base_window_selection
    support = draft.support_pivot_selection

    assert selection.method is BaseWindowSelectionMethod.MAX_BASE_TOP_THEN_SHORTEST
    assert selection.construct_all_valid_suffix_windows
    assert selection.retain_exact_maximum_base_top and selection.select_shortest_retained_window
    assert not selection.allow_reward_risk_optimization
    assert not selection.allow_stop_optimization and not selection.allow_target_optimization
    assert support.method is SupportPivotMethod.MOST_RECENT_CONFIRMED_PIVOT_LOW_IN_SELECTED_BASE
    assert support.support_price_field == "LOW" and support.pivot_must_be_inside_selected_base
    assert not support.unconfirmed_pivot_allowed and not support.raw_session_low_fallback_allowed
    assert not support.allow_stop_or_reward_risk_selection


def test_breach_tick_grid_stop_and_trigger_semantics_are_exactly_encoded() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()

    assert draft.support_breach.comparison is SupportBreachComparison.STRICT_CLOSE_LESS_THAN_SUPPORT
    assert not draft.support_breach.equality_is_breach
    assert draft.support_breach.failure_status == "BASE_STRUCTURE_BROKEN"
    assert draft.tick_source.method is TickSourceMethod.AUTHORITATIVE_REFERENCE_DATA_WITH_PIT_PRECEDENCE
    assert draft.tick_source.official_nse_first
    assert draft.tick_source.approved_licensed_exact_identity_nse_cash_fallback
    assert draft.tick_source.licensed_fallback_requires_explicit_approval
    assert not draft.tick_source.inferred_tick_fallback_allowed
    assert draft.tick_source.conflict_status == "REFERENCE_DATA_CONFLICT"
    assert draft.tick_grid.method is TickGridMethod.EXACT_DECIMAL_MODULO
    assert draft.tick_grid.required_remainder == Decimal("0")
    assert not any((draft.tick_grid.epsilon_allowed, draft.tick_grid.rounding_repair_allowed,
                    draft.tick_grid.nearest_grid_repair_allowed, draft.tick_grid.floor_or_ceil_repair_allowed))
    assert draft.structural_stop.structural_invalidation_source == "CURRENT_STRUCTURAL_SUPPORT"
    assert draft.structural_stop.valid_tick_required and draft.structural_stop.support_grid_aligned_required
    assert draft.structural_stop.derived_stop_grid_aligned_required
    assert not draft.structural_stop.percent_or_atr_buffer_allowed
    assert not draft.structural_stop.forced_percent_range_allowed
    assert draft.resistance_trigger.resistance_source == "SELECTED_GOVERNED_BASE_TOP"
    assert draft.resistance_trigger.trigger_source == "RESISTANCE"
    assert draft.resistance_trigger.trigger_buffer == Decimal("0")


def test_target_support_is_bound_to_current_structural_support_with_exact_measured_move_semantics() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    target = draft.target_support_binding

    assert target.status is TargetSupportBindingStatus.CURRENT_STRUCTURAL_SUPPORT
    assert target.target_support_source == "CURRENT_STRUCTURAL_SUPPORT"
    assert target.current_structural_support_is_bound
    assert target.base_height_formula == "SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT"
    assert target.target_formula == "SELECTED_BASE_TOP_PLUS_(SELECTED_BASE_TOP_MINUS_CURRENT_STRUCTURAL_SUPPORT)"
    assert not target.target_only_support_definition_allowed
    assert not target.older_or_deeper_support_fallback_allowed
    assert target.selected_base_top_required and target.current_structural_support_required
    assert target.selected_base_top_must_exceed_support
    assert target.unavailable_geometry_status == "TARGET_GEOMETRY_UNAVAILABLE"
    assert target.invalid_geometry_status == "INVALID_TARGET_GEOMETRY"
    assert target.reward_formula == "TARGET_MINUS_TRIGGER"
    assert target.risk_formula == "TRIGGER_MINUS_FINAL_STOP"
    assert target.reward_risk_minimum == Decimal("3")
    assert target.reward_risk_requires_positive_risk_and_reward
    assert not target.target_may_be_moved_to_manufacture_reward_risk
    assert draft.unresolved_fields == PREBREAKOUT_APPROVED_V1_2_UNRESOLVED_FIELDS
    assert draft.policy_fully_resolved


def test_policy_resolution_does_not_claim_tick_data_availability() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    assert draft.policy_fully_resolved
    assert draft.tick_source.unavailable_status == "TICK_SIZE_UNAVAILABLE_FOR_AS_OF"


@pytest.mark.parametrize(
    "mutate",
    (
        lambda value: replace(value, base_window_validity=replace(value.base_window_validity, minimum_canonical_sessions=21)),
        lambda value: replace(value, base_window_selection=replace(value.base_window_selection, select_shortest_retained_window=False)),
        lambda value: replace(value, support_pivot_selection=replace(value.support_pivot_selection, raw_session_low_fallback_allowed=True)),
        lambda value: replace(value, support_breach=replace(value.support_breach, equality_is_breach=True)),
        lambda value: replace(value, tick_source=replace(value.tick_source, official_nse_first=False)),
        lambda value: replace(value, tick_grid=replace(value.tick_grid, epsilon_allowed=True)),
        lambda value: replace(value, target_support_binding=replace(value.target_support_binding, older_or_deeper_support_fallback_allowed=True)),
    ),
)
def test_every_structural_semantic_change_changes_successor_fingerprint(mutate) -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    assert mutate(draft).fingerprint != draft.fingerprint


def test_structural_successor_serialization_round_trips_and_tampering_fails_closed() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    payload = structural_successor_draft_to(draft)

    restored = structural_successor_draft_from(payload)
    assert restored == draft
    assert restored.tick_grid.required_remainder == Decimal("0")
    assert isinstance(restored.tick_source.method, TickSourceMethod)

    payload["base_window_validity"]["minimum_confirmed_pivot_highs"] = 3
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        structural_successor_draft_from(payload)

    payload = structural_successor_draft_to(draft)
    payload["target_support_binding"]["target_support_source"] = "OLDER_SUPPORT"
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        structural_successor_draft_from(payload)

    payload = structural_successor_draft_to(draft)
    payload["target_support_binding"]["target_formula"] = "PERCENTAGE_TARGET"
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        structural_successor_draft_from(payload)


def test_structural_successor_rejects_malformed_boolean_instead_of_coercing_it() -> None:
    payload = structural_successor_draft_to(prebreakout_policy_v1_2_structural_successor_draft())
    payload["tick_grid"]["rounding_repair_allowed"] = "false"
    with pytest.raises(ValueError, match="SERIALIZATION_INVALID"):
        structural_successor_draft_from(payload)


@pytest.mark.parametrize(
    "name, nested, replacement",
    (
        ("base_window_selection", "allow_target_optimization", True),
        ("support_pivot_selection", "unconfirmed_pivot_allowed", True),
        ("tick_source", "licensed_fallback_requires_explicit_approval", False),
        ("tick_grid", "rounding_repair_allowed", True),
    ),
)
def test_tampered_nested_structural_payloads_fail_fingerprint_validation(name, nested, replacement) -> None:
    payload = structural_successor_draft_to(prebreakout_policy_v1_2_structural_successor_draft())
    payload[name][nested] = replacement
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        structural_successor_draft_from(payload)


def test_structural_draft_is_pure_domain_data_without_repository_or_provider_dependencies() -> None:
    draft = prebreakout_policy_v1_2_structural_successor_draft()
    assert draft.fingerprint
    assert "sqlite" not in type(draft).__module__.lower()
    assert "network" not in type(draft).__module__.lower()
