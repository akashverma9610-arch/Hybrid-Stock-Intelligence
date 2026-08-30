from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance import (
    PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS,
    PreBreakoutPolicyGovernanceError,
    PreBreakoutPolicyGovernanceService,
    PreBreakoutPolicyGovernanceState,
)
from app.strategies.pre_breakout.policy import (
    PreBreakoutApprovedPolicy,
    PreBreakoutPolicyApproval,
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicyDraft,
    PreBreakoutPolicySelection,
    PreBreakoutPolicySelectionContext,
    prebreakout_policy_approval_fingerprint,
    prebreakout_policy_draft_fingerprint,
    prebreakout_policy_selection_fingerprint,
)


T = datetime(2026, 8, 28, tzinfo=UTC)


def draft(*, version: str = "v1") -> PreBreakoutPolicyDraft:
    return PreBreakoutPolicyDraft(policy_id="prebreakout", version=version)


def approval(
    policy_draft: PreBreakoutPolicyDraft,
    *,
    approval_id: str = "approval-v1",
    decision: PreBreakoutPolicyApprovalDecision = PreBreakoutPolicyApprovalDecision.APPROVE,
    reviewed_at: datetime = T,
    **overrides,
) -> PreBreakoutPolicyApproval:
    policy = PreBreakoutApprovedPolicy.from_draft(policy_draft)
    values = dict(
        approval_id=approval_id,
        policy_id=policy_draft.policy_id,
        policy_version=policy_draft.version,
        draft_policy_fingerprint=prebreakout_policy_draft_fingerprint(policy_draft),
        approved_policy_fingerprint=policy.fingerprint,
        approved_values_fingerprint=policy.values_fingerprint,
        reviewer_id="human:owner",
        reviewed_at=reviewed_at,
        decision=decision,
        created_at=reviewed_at,
        warnings=(),
    )
    values.update(overrides)
    values["fingerprint"] = prebreakout_policy_approval_fingerprint(
        **{
            key: value.value if hasattr(value, "value") else value.isoformat() if isinstance(value, datetime) else value
            for key, value in values.items()
            if key != "fingerprint"
        }
    )
    return PreBreakoutPolicyApproval(**values)


def selection(
    policy_draft: PreBreakoutPolicyDraft,
    approval_value: PreBreakoutPolicyApproval,
    *,
    selection_id: str = "selection-v1",
    effective_from: datetime = T,
    **overrides,
) -> PreBreakoutPolicySelection:
    values = dict(
        selection_id=selection_id,
        approval_id=approval_value.approval_id,
        policy_id=policy_draft.policy_id,
        policy_version=policy_draft.version,
        policy_fingerprint=approval_value.approved_policy_fingerprint,
        selection_context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
        selected_by="human:owner",
        selected_at=T,
        effective_from=effective_from,
        warnings=(),
    )
    values.update(overrides)
    values["fingerprint"] = prebreakout_policy_selection_fingerprint(
        **{
            key: value.value if hasattr(value, "value") else value.isoformat() if isinstance(value, datetime) else value
            for key, value in values.items()
            if key != "fingerprint"
        }
    )
    return PreBreakoutPolicySelection(**values)


def service(repo: SQLiteStrategyGovernanceRepository, *drafts: PreBreakoutPolicyDraft) -> PreBreakoutPolicyGovernanceService:
    return PreBreakoutPolicyGovernanceService(repo, drafts=drafts)


def test_exact_human_approval_reconstructs_only_the_governed_v1_values():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); stored = approval(value)
    repo.save_prebreakout_policy_approval(stored)
    view = service(repo, value).reconstruct_approved_policy(stored.approval_id)
    assert view.approval == stored and view.policy_fingerprint == stored.approved_policy_fingerprint
    assert view.approval_status is PreBreakoutPolicyGovernanceState.APPROVED
    assert view.policy.atr_period == 14 and view.policy.pivot_left_sessions == view.policy.pivot_right_sessions == 3
    assert view.policy.breakout_trigger_buffer == 0 and view.policy.reward_risk_below_minimum_rejected is True
    assert view.unresolved_fields == PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS


@pytest.mark.parametrize(
    "overrides,error",
    [
        ({"draft_policy_fingerprint": "wrong"}, "DRAFT_FINGERPRINT"),
        ({"approved_policy_fingerprint": "wrong"}, "POLICY_FINGERPRINT"),
        ({"approved_values_fingerprint": "wrong"}, "VALUES_FINGERPRINT"),
        ({"policy_version": "v2"}, "DRAFT_NOT_FOUND"),
    ],
)
def test_approval_relationship_mismatches_fail_closed(overrides, error):
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); stored = approval(value, **overrides)
    repo.save_prebreakout_policy_approval(stored)
    with pytest.raises(PreBreakoutPolicyGovernanceError, match=error):
        service(repo, value).reconstruct_approved_policy(stored.approval_id)


def test_reject_approval_and_missing_approval_never_support_selection():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); rejected = approval(value, decision=PreBreakoutPolicyApprovalDecision.REJECT)
    repo.save_prebreakout_policy_approval(rejected)
    rejected_selection = selection(value, rejected)
    repo.save_prebreakout_policy_selection(rejected_selection)
    with pytest.raises(PreBreakoutPolicyGovernanceError, match="NOT_APPROVED"):
        service(repo, value).validate_selection(rejected_selection)
    missing = selection(value, rejected, approval_id="missing", selection_id="missing-selection")
    with pytest.raises(PreBreakoutPolicyGovernanceError, match="APPROVAL_NOT_FOUND"):
        service(repo, value).validate_selection(missing)


def test_selection_lineage_and_effective_chronology_are_strict():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); approved = approval(value); repo.save_prebreakout_policy_approval(approved)
    for selection_value, error in (
        (selection(value, approved, policy_id="other", selection_id="wrong-policy"), "APPROVAL_LINEAGE"),
        (selection(value, approved, policy_fingerprint="wrong", selection_id="wrong-fingerprint"), "APPROVAL_LINEAGE"),
        (selection(value, approved, selected_at=T - timedelta(seconds=2), effective_from=T - timedelta(seconds=1), selection_id="too-early"), "PRECEDES_APPROVAL"),
    ):
        with pytest.raises(PreBreakoutPolicyGovernanceError, match=error):
            service(repo, value).validate_selection(selection_value)


def test_as_of_read_is_explicit_and_uses_latest_effective_selection_not_insertion_order():
    repo = SQLiteStrategyGovernanceRepository(); first = draft(version="v1"); second = draft(version="v2")
    first_approval = approval(first, approval_id="approval-v1", reviewed_at=T)
    second_approval = approval(second, approval_id="approval-v2", reviewed_at=T + timedelta(days=1))
    repo.save_prebreakout_policy_approval(first_approval); repo.save_prebreakout_policy_approval(second_approval)
    first_selection = selection(first, first_approval, selection_id="selection-v1", effective_from=T)
    second_selection = selection(second, second_approval, selection_id="selection-v2", effective_from=T + timedelta(days=2), selected_at=T + timedelta(days=1))
    repo.save_prebreakout_policy_selection(second_selection); repo.save_prebreakout_policy_selection(first_selection)
    governed = service(repo, first, second)
    assert governed.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T - timedelta(seconds=1)) is None
    assert governed.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T + timedelta(days=1)).selection == first_selection
    assert governed.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T + timedelta(days=2)).selection == second_selection
    status = governed.prebreakout_policy_governance_status(as_of=T + timedelta(days=2))
    assert status.selected_for_current_scan is True and status.policy_version == "v2"


def test_approved_but_unselected_policy_is_unavailable_for_current_stored_scan():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); approved = approval(value); repo.save_prebreakout_policy_approval(approved)
    governed = service(repo, value)
    assert governed.get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T) is None
    assert governed.prebreakout_policy_governance_status(as_of=T).approval_valid is True


def test_audit_reconstructs_intact_lineage_and_fails_closed_on_stored_tampering():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); approved = approval(value); selected = selection(value, approved)
    repo.save_prebreakout_policy_approval(approved); repo.save_prebreakout_policy_selection(selected)
    audit = AuditReconstructionService(repo)
    assert audit.reconstruct_prebreakout_policy_approval(approved.approval_id, drafts=(value,)).approval == approved
    assert audit.reconstruct_prebreakout_policy_selection(selected.selection_id, drafts=(value,)).selection == selected
    payload = json.loads(repo._connection.execute("SELECT payload_json FROM prebreakout_policy_selections WHERE id=?", (selected.selection_id,)).fetchone()["payload_json"])
    payload["policy_fingerprint"] = "tampered"
    repo._connection.execute("UPDATE prebreakout_policy_selections SET payload_json=? WHERE id=?", (json.dumps(payload, separators=(",", ":")), selected.selection_id)); repo._connection.commit()
    with pytest.raises(AuditReconstructionError, match="FINGERPRINT"):
        audit.reconstruct_prebreakout_policy_selection(selected.selection_id, drafts=(value,))


def test_governance_reads_create_no_strategy_promotion_activation_or_scanner_artifacts():
    repo = SQLiteStrategyGovernanceRepository(); value = draft(); approved = approval(value); selected = selection(value, approved)
    repo.save_prebreakout_policy_approval(approved); repo.save_prebreakout_policy_selection(selected)
    before = (
        repo.get_approved_strategy_version("none"),
        repo.get_strategy_activation("none"),
        repo.get_strategy_promotion_proposal("none"),
        repo.get_strategy_promotion_review("none"),
        repo.get_strategy_rollback("none"),
    )
    assert service(repo, value).get_selected_prebreakout_policy(context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T) is not None
    after = (
        repo.get_approved_strategy_version("none"),
        repo.get_strategy_activation("none"),
        repo.get_strategy_promotion_proposal("none"),
        repo.get_strategy_promotion_review("none"),
        repo.get_strategy_rollback("none"),
    )
    assert before == after == (None, None, None, None, None)
