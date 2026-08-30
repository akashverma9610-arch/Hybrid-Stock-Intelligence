from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.policy import (
    PREBREAKOUT_APPROVED_V1_1_UNRESOLVED_FIELDS,
    PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS,
    ConsolidationVolumeComparisonOperator,
    ConsolidationVolumeSemanticStatus,
    ConsolidationVolumeStatistic,
    PreBreakoutApprovedPolicy,
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicyDraft,
    PreBreakoutPolicySelectionContext,
    prebreakout_policy_v1_1_volume_successor_draft,
)
from app.strategies.pre_breakout.policy_serialization import successor_draft_from, successor_draft_to


T = datetime(2026, 8, 28, 12, tzinfo=UTC)
CURRENT_V1_FINGERPRINT = "5d54b7d3a3d8c85559caddfd2f11178330e42a5eb31f3dc2f9e3d4c39ecc4933"


def _selected_v1_repository(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(str(tmp_path / "governance.sqlite"))
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    commands.approve(
        approval_id="v1-approval",
        policy_id="pre-breakout-policy-v1-draft",
        policy_version="v1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE,
        reviewer_id="human:tester",
        reviewed_at=T - timedelta(seconds=1),
    )
    commands.select_for_current_stored_scan(
        selection_id="v1-selection",
        approval_id="v1-approval",
        selected_by="human:tester",
        selected_at=T,
        effective_from=T,
    )
    return repository


def test_existing_v1_is_unchanged_and_successor_resolves_only_volume_semantics() -> None:
    existing = PreBreakoutApprovedPolicy.from_draft(PreBreakoutPolicyDraft())
    successor = prebreakout_policy_v1_1_volume_successor_draft()
    assert existing.fingerprint == CURRENT_V1_FINGERPRINT
    assert successor.policy_id == "pre-breakout-policy-v1" and successor.version == "v1.1-draft"
    assert successor.fingerprint != existing.fingerprint
    assert existing.unresolved_fields == PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS
    assert successor.unresolved_fields == PREBREAKOUT_APPROVED_V1_1_UNRESOLVED_FIELDS
    assert successor.consolidation_volume_statistic.statistic is ConsolidationVolumeStatistic.EVALUATION_SESSION_VOLUME
    assert successor.consolidation_volume_statistic.reference_period == 20
    assert successor.consolidation_volume_statistic.include_current_in_reference is False
    assert successor.consolidation_volume_statistic.threshold_ratio == Decimal("0.50")
    assert successor.consolidation_volume_statistic.operator is ConsolidationVolumeComparisonOperator.STRICT_LESS_THAN
    assert successor.atr_period == existing.atr_period == 14
    assert successor.high_lookback_sessions == existing.high_lookback_sessions == 252
    assert successor.base_duration_min_sessions == existing.base_duration_min_sessions == 20


@pytest.mark.parametrize(
    ("current", "expected"),
    ((499_999, ConsolidationVolumeSemanticStatus.PASS), (500_000, ConsolidationVolumeSemanticStatus.FAIL), (500_001, ConsolidationVolumeSemanticStatus.FAIL)),
)
def test_successor_volume_semantic_is_prior_twenty_strictly_less_than_half(current, expected) -> None:
    rule = prebreakout_policy_v1_1_volume_successor_draft().consolidation_volume_statistic
    result = rule.evaluate(current_volume=current, prior_valid_volumes=(1_000_000,) * 20)
    assert result.status is expected
    assert result.prior_valid_session_sma == 1_000_000 and result.threshold_volume == 500_000


def test_successor_volume_semantic_is_unavailable_for_missing_or_insufficient_observations() -> None:
    rule = prebreakout_policy_v1_1_volume_successor_draft().consolidation_volume_statistic
    assert rule.evaluate(current_volume=1, prior_valid_volumes=(1_000_000,) * 19).status is ConsolidationVolumeSemanticStatus.UNAVAILABLE
    assert rule.evaluate(current_volume=None, prior_valid_volumes=(1_000_000,) * 20).status is ConsolidationVolumeSemanticStatus.UNAVAILABLE


def test_successor_fingerprint_covers_each_volume_semantic_field() -> None:
    successor = prebreakout_policy_v1_1_volume_successor_draft()
    rule = successor.consolidation_volume_statistic
    alternatives = (
        replace(rule, statistic=ConsolidationVolumeStatistic.BASE_WINDOW_AVERAGE_VOLUME),
        replace(rule, reference_period=21),
        replace(rule, include_current_in_reference=True),
        replace(rule, threshold_ratio=rule.threshold_ratio + Decimal("0.01")),
        replace(rule, operator=ConsolidationVolumeComparisonOperator.LESS_THAN_OR_EQUAL),
    )
    assert all(candidate.fingerprint != rule.fingerprint for candidate in alternatives)
    assert all(
        replace(successor, consolidation_volume_statistic=candidate).fingerprint != successor.fingerprint
        for candidate in alternatives
    )


def test_successor_serialization_round_trip_and_tampering_fail_closed() -> None:
    successor = prebreakout_policy_v1_1_volume_successor_draft()
    payload = successor_draft_to(successor)
    assert successor_draft_from(payload) == successor
    payload["consolidation_volume_statistic"]["threshold_ratio"] = "0.51"
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        successor_draft_from(payload)


def test_successor_creation_does_not_change_current_selection_or_create_governance_state(tmp_path) -> None:
    repository = _selected_v1_repository(tmp_path)
    governance = PreBreakoutPolicyGovernanceService(repository)
    before = (
        repository.list_prebreakout_policy_approvals(),
        repository.list_prebreakout_policy_selections(),
        repository.get_approved_strategy_version("none"),
        repository.get_strategy_activation("none"),
    )
    successor = prebreakout_policy_v1_1_volume_successor_draft()
    selected = governance.get_selected_prebreakout_policy(
        context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
        as_of=T,
    )
    after = (
        repository.list_prebreakout_policy_approvals(),
        repository.list_prebreakout_policy_selections(),
        repository.get_approved_strategy_version("none"),
        repository.get_strategy_activation("none"),
    )
    assert successor.status == "DRAFT_REQUIRES_HUMAN_APPROVAL"
    assert selected is not None and selected.policy_fingerprint == CURRENT_V1_FINGERPRINT
    assert before == after
