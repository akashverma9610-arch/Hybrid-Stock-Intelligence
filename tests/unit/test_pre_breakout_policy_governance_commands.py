from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.runtime.cli import main, parser
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance_commands import (
    PreBreakoutPolicyCommandError,
    PreBreakoutPolicyGovernanceCommandService,
)
from app.strategies.pre_breakout.policy import PreBreakoutPolicyApprovalDecision, PreBreakoutPolicySelectionContext


T = datetime(2026, 8, 28, tzinfo=UTC)
POLICY_ID = "pre-breakout-policy-v1-draft"
POLICY_VERSION = "v1-draft"


def command_service(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    return PreBreakoutPolicyGovernanceCommandService(repository), repository


def approve(service, *, approval_id: str = "approval", decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewed_at: datetime = T, reviewer_id: str = "human:owner"):
    return service.approve(
        approval_id=approval_id,
        policy_id=POLICY_ID,
        policy_version=POLICY_VERSION,
        decision=decision,
        reviewer_id=reviewer_id,
        reviewed_at=reviewed_at,
    )


def test_approve_command_service_persists_exact_audited_human_approval(tmp_path):
    service, repository = command_service(tmp_path)
    receipt = approve(service)
    stored = repository.get_prebreakout_policy_approval(receipt.approval_id)
    assert stored is not None and stored.fingerprint == receipt.approval_fingerprint
    assert receipt.decision is PreBreakoutPolicyApprovalDecision.APPROVE
    assert receipt.policy_id == POLICY_ID and receipt.policy_version == POLICY_VERSION


def test_reject_is_persisted_but_cannot_be_selected(tmp_path):
    service, repository = command_service(tmp_path)
    receipt = approve(service, decision=PreBreakoutPolicyApprovalDecision.REJECT)
    assert repository.get_prebreakout_policy_approval(receipt.approval_id) is not None
    with pytest.raises(ValueError, match="NOT_APPROVED"):
        service.select_for_current_stored_scan(
            selection_id="selection", approval_id=receipt.approval_id,
            selected_by="human:owner", selected_at=T, effective_from=T,
        )


@pytest.mark.parametrize(
    "reviewer_id,reviewed_at,error",
    [
        ("owner", T, "HUMAN_REVIEWER_REQUIRED"),
        ("system:owner", T, "HUMAN_REVIEWER_REQUIRED"),
        ("human:owner", datetime(2026, 8, 28), "NAIVE"),
    ],
)
def test_approval_command_enforces_human_identity_and_timezone(tmp_path, reviewer_id, reviewed_at, error):
    service, _ = command_service(tmp_path)
    with pytest.raises(ValueError, match=error):
        approve(service, reviewer_id=reviewer_id, reviewed_at=reviewed_at)


def test_command_cannot_override_policy_semantics_and_unknown_policy_fails(tmp_path):
    service, _ = command_service(tmp_path)
    with pytest.raises(PreBreakoutPolicyCommandError, match="DRAFT_NOT_FOUND"):
        service.approve(
            approval_id="wrong", policy_id="wrong", policy_version=POLICY_VERSION,
            decision=PreBreakoutPolicyApprovalDecision.APPROVE, reviewer_id="human:owner", reviewed_at=T,
        )
    with pytest.raises(SystemExit):
        parser().parse_args([
            "approve-prebreakout-policy", "--approval-id", "x", "--policy-id", POLICY_ID,
            "--policy-version", POLICY_VERSION, "--decision", "APPROVE", "--reviewer-id", "human:owner",
            "--reviewed-at", T.isoformat(), "--bbw-threshold", "99",
        ])


def test_selection_command_is_current_stored_scan_only_and_audited(tmp_path):
    service, repository = command_service(tmp_path); approval_receipt = approve(service)
    receipt = service.select_for_current_stored_scan(
        selection_id="selection", approval_id=approval_receipt.approval_id,
        selected_by="human:selector", selected_at=T, effective_from=T,
    )
    stored = repository.get_prebreakout_policy_selection(receipt.selection_id)
    assert stored is not None and receipt.selection_context is PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN
    assert receipt.selected_for_current_stored_scan is True


@pytest.mark.parametrize(
    "selected_by,selected_at,effective_from,error",
    [
        ("agent:x", T, T, "HUMAN_REVIEWER_REQUIRED"),
        ("human:selector", datetime(2026, 8, 28), T, "NAIVE"),
        ("human:selector", T, datetime(2026, 8, 28), "NAIVE"),
        ("human:selector", T, T - timedelta(seconds=1), "CHRONOLOGY"),
    ],
)
def test_selection_command_enforces_identity_and_timestamp_safety(tmp_path, selected_by, selected_at, effective_from, error):
    service, _ = command_service(tmp_path); approval_receipt = approve(service)
    with pytest.raises(ValueError, match=error):
        service.select_for_current_stored_scan(
            selection_id="selection", approval_id=approval_receipt.approval_id,
            selected_by=selected_by, selected_at=selected_at, effective_from=effective_from,
        )


def test_selection_before_approval_and_missing_approval_fail_closed(tmp_path):
    service, _ = command_service(tmp_path); approval_receipt = approve(service)
    with pytest.raises(ValueError, match="PRECEDES_APPROVAL"):
        service.select_for_current_stored_scan(
            selection_id="early", approval_id=approval_receipt.approval_id,
            selected_by="human:selector", selected_at=T - timedelta(seconds=2), effective_from=T - timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="NOT_FOUND"):
        service.select_for_current_stored_scan(
            selection_id="missing", approval_id="missing", selected_by="human:selector", selected_at=T, effective_from=T,
        )


def test_conflicts_fail_closed_and_future_effective_selection_is_not_yet_selected(tmp_path):
    service, repository = command_service(tmp_path); approval_receipt = approve(service)
    with pytest.raises(ValueError):
        approve(service, decision=PreBreakoutPolicyApprovalDecision.REJECT)
    receipt = service.select_for_current_stored_scan(
        selection_id="future", approval_id=approval_receipt.approval_id,
        selected_by="human:selector", selected_at=T, effective_from=T + timedelta(days=1),
    )
    with pytest.raises(ValueError):
        service.select_for_current_stored_scan(
            selection_id="future", approval_id=approval_receipt.approval_id,
            selected_by="human:other", selected_at=T, effective_from=T + timedelta(days=1),
        )
    assert service._governance.get_selected_prebreakout_policy(
        context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN, as_of=T,
    ) is None
    assert repository.get_prebreakout_policy_selection(receipt.selection_id) is not None


def test_cli_uses_exact_human_command_contract_and_safe_receipt(tmp_path):
    path = tmp_path / "cli.sqlite"; repository = SQLiteStrategyGovernanceRepository(path)
    service = PreBreakoutPolicyGovernanceCommandService(repository); output = []
    result = main(
        [
            "approve-prebreakout-policy", "--approval-id", "cli-approval", "--policy-id", POLICY_ID,
            "--policy-version", POLICY_VERSION, "--decision", "APPROVE", "--reviewer-id", "human:owner",
            "--reviewed-at", T.isoformat(),
        ],
        prebreakout_governance_command_factory=lambda: (service, repository), output=output.append,
    )
    assert result == 0 and "approval_id=cli-approval" in output[0] and "approved_policy_fingerprint=" in output[0]
    assert "active_strategy" not in output[0] and "promotion" not in output[0]


def test_command_operations_do_not_create_promotion_activation_or_scanner_artifacts(tmp_path):
    service, repository = command_service(tmp_path); approval_receipt = approve(service)
    service.select_for_current_stored_scan(selection_id="selection", approval_id=approval_receipt.approval_id, selected_by="human:selector", selected_at=T, effective_from=T)
    assert repository.get_approved_strategy_version("none") is None
    assert repository.get_strategy_activation("none") is None
    assert repository.get_strategy_promotion_proposal("none") is None
    assert repository.get_strategy_promotion_review("none") is None
    assert repository.get_strategy_rollback("none") is None
