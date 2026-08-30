"""Human-only command operations over immutable Pre-Breakout governance records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.services.audit_reconstruction_service import AuditReconstructionService
from app.storage.governance_repository import StrategyGovernanceRepository
from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
from app.strategies.pre_breakout.policy import (
    PreBreakoutApprovedPolicy,
    PreBreakoutPolicyApproval,
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicyDraft,
    PreBreakoutPolicySelection,
    PreBreakoutPolicySelectionContext,
    PreBreakoutMultiStageEntrySuccessorDraft,
    PreBreakoutVolumeResolvedSuccessorDraft,
    prebreakout_policy_approval_fingerprint,
    prebreakout_policy_draft_fingerprint,
    prebreakout_policy_selection_fingerprint,
    prebreakout_policy_governance_drafts,
)


class PreBreakoutPolicyCommandError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PreBreakoutPolicyApprovalReceipt:
    approval_id: str
    policy_id: str
    policy_version: str
    decision: PreBreakoutPolicyApprovalDecision
    reviewer_id: str
    reviewed_at: datetime
    draft_policy_fingerprint: str
    approved_policy_fingerprint: str
    approval_fingerprint: str


@dataclass(frozen=True, slots=True)
class PreBreakoutPolicySelectionReceipt:
    selection_id: str
    approval_id: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    selection_context: PreBreakoutPolicySelectionContext
    selected_by: str
    selected_at: datetime
    effective_from: datetime
    selection_fingerprint: str
    selected_for_current_stored_scan: bool


class PreBreakoutPolicyGovernanceCommandService:
    """Creates human-supplied immutable artifacts; no activation or scan operation exists here."""

    def __init__(
        self,
        repository: StrategyGovernanceRepository,
        *,
        drafts: Iterable[PreBreakoutPolicyDraft | PreBreakoutVolumeResolvedSuccessorDraft | PreBreakoutMultiStageEntrySuccessorDraft] = prebreakout_policy_governance_drafts(),
    ) -> None:
        self._repository = repository
        self._drafts = {(draft.policy_id, draft.version): draft for draft in drafts}
        self._governance = PreBreakoutPolicyGovernanceService(repository, drafts=self._drafts.values())
        self._audit = AuditReconstructionService(repository)

    def approve(
        self,
        *,
        approval_id: str,
        policy_id: str,
        policy_version: str,
        decision: PreBreakoutPolicyApprovalDecision,
        reviewer_id: str,
        reviewed_at: datetime,
    ) -> PreBreakoutPolicyApprovalReceipt:
        draft = self._draft(policy_id, policy_version)
        policy = PreBreakoutApprovedPolicy.from_draft(draft)
        value = PreBreakoutPolicyApproval(
            approval_id=approval_id,
            policy_id=policy_id,
            policy_version=policy_version,
            draft_policy_fingerprint=prebreakout_policy_draft_fingerprint(draft),
            approved_policy_fingerprint=policy.fingerprint,
            approved_values_fingerprint=policy.values_fingerprint,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
            decision=decision,
            created_at=reviewed_at,
            warnings=(),
            fingerprint=prebreakout_policy_approval_fingerprint(
                approval_id=approval_id,
                policy_id=policy_id,
                policy_version=policy_version,
                draft_policy_fingerprint=prebreakout_policy_draft_fingerprint(draft),
                approved_policy_fingerprint=policy.fingerprint,
                approved_values_fingerprint=policy.values_fingerprint,
                reviewer_id=reviewer_id,
                reviewed_at=reviewed_at.isoformat(),
                decision=decision.value,
                created_at=reviewed_at.isoformat(),
                warnings=(),
            ),
        )
        self._governance.validate_approval(value)
        self._repository.save_prebreakout_policy_approval(value)
        if self._repository.get_prebreakout_policy_approval(approval_id) != value:
            raise PreBreakoutPolicyCommandError("PREBREAKOUT_POLICY_APPROVAL_READBACK_MISMATCH")
        self._audit.reconstruct_prebreakout_policy_approval(approval_id, drafts=tuple(self._drafts.values()))
        return PreBreakoutPolicyApprovalReceipt(
            approval_id=value.approval_id,
            policy_id=value.policy_id,
            policy_version=value.policy_version,
            decision=value.decision,
            reviewer_id=value.reviewer_id,
            reviewed_at=value.reviewed_at,
            draft_policy_fingerprint=value.draft_policy_fingerprint,
            approved_policy_fingerprint=value.approved_policy_fingerprint,
            approval_fingerprint=value.fingerprint,
        )

    def select_for_current_stored_scan(
        self,
        *,
        selection_id: str,
        approval_id: str,
        selected_by: str,
        selected_at: datetime,
        effective_from: datetime,
    ) -> PreBreakoutPolicySelectionReceipt:
        approval_view = self._governance.reconstruct_approved_policy(approval_id)
        value = PreBreakoutPolicySelection(
            selection_id=selection_id,
            approval_id=approval_id,
            policy_id=approval_view.policy.policy_id,
            policy_version=approval_view.policy.version,
            policy_fingerprint=approval_view.policy_fingerprint,
            selection_context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
            selected_by=selected_by,
            selected_at=selected_at,
            effective_from=effective_from,
            warnings=(),
            fingerprint=prebreakout_policy_selection_fingerprint(
                selection_id=selection_id,
                approval_id=approval_id,
                policy_id=approval_view.policy.policy_id,
                policy_version=approval_view.policy.version,
                policy_fingerprint=approval_view.policy_fingerprint,
                selection_context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN.value,
                selected_by=selected_by,
                selected_at=selected_at.isoformat(),
                effective_from=effective_from.isoformat(),
                warnings=(),
            ),
        )
        self._governance.validate_selection(value)
        self._repository.save_prebreakout_policy_selection(value)
        if self._repository.get_prebreakout_policy_selection(selection_id) != value:
            raise PreBreakoutPolicyCommandError("PREBREAKOUT_POLICY_SELECTION_READBACK_MISMATCH")
        self._audit.reconstruct_prebreakout_policy_selection(selection_id, drafts=tuple(self._drafts.values()))
        selected = self._governance.get_selected_prebreakout_policy(
            context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
            as_of=effective_from,
        )
        if selected is None or selected.selection != value:
            raise PreBreakoutPolicyCommandError("PREBREAKOUT_POLICY_SELECTION_AS_OF_MISMATCH")
        return PreBreakoutPolicySelectionReceipt(
            selection_id=value.selection_id,
            approval_id=value.approval_id,
            policy_id=value.policy_id,
            policy_version=value.policy_version,
            policy_fingerprint=value.policy_fingerprint,
            selection_context=value.selection_context,
            selected_by=value.selected_by,
            selected_at=value.selected_at,
            effective_from=value.effective_from,
            selection_fingerprint=value.fingerprint,
            selected_for_current_stored_scan=True,
        )

    def _draft(self, policy_id: str, policy_version: str) -> PreBreakoutPolicyDraft:
        draft = self._drafts.get((policy_id, policy_version))
        if draft is None:
            raise PreBreakoutPolicyCommandError("PREBREAKOUT_POLICY_DRAFT_NOT_FOUND")
        return draft
