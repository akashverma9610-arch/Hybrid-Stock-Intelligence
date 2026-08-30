"""Stored-only governance linkage for the Pre-Breakout Policy V1 read path."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable

from app.storage.governance_repository import StrategyGovernanceRepository
from app.strategies.pre_breakout.policy import (
    PREBREAKOUT_APPROVED_V1_UNRESOLVED_FIELDS,
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


class PreBreakoutPolicyGovernanceError(ValueError):
    pass


class PreBreakoutPolicyGovernanceState(str, Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    SELECTED_FOR_SCAN = "SELECTED_FOR_SCAN"


@dataclass(frozen=True, slots=True)
class ApprovedPreBreakoutPolicyView:
    policy: PreBreakoutApprovedPolicy
    approval: PreBreakoutPolicyApproval
    policy_fingerprint: str
    approval_fingerprint: str
    approval_status: PreBreakoutPolicyGovernanceState
    unresolved_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SelectedPreBreakoutPolicyView:
    policy: PreBreakoutApprovedPolicy
    approval: PreBreakoutPolicyApproval
    selection: PreBreakoutPolicySelection
    policy_fingerprint: str
    approval_fingerprint: str
    selection_fingerprint: str
    state: PreBreakoutPolicyGovernanceState
    unresolved_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreBreakoutPolicyGovernanceStatus:
    draft_present: bool
    approval_present: bool
    approval_valid: bool
    selection_present: bool
    selection_valid: bool
    selected_for_current_scan: bool
    policy_version: str | None
    policy_fingerprint: str | None
    unresolved_fields: tuple[str, ...]


class PreBreakoutPolicyGovernanceService:
    """Validates immutable lineage; it never writes, approves, selects, or activates."""

    def __init__(
        self,
        repository: StrategyGovernanceRepository,
        *,
        drafts: Iterable[PreBreakoutPolicyDraft | PreBreakoutVolumeResolvedSuccessorDraft | PreBreakoutMultiStageEntrySuccessorDraft] = prebreakout_policy_governance_drafts(),
    ) -> None:
        self._repository = repository
        self._drafts = {(draft.policy_id, draft.version): draft for draft in drafts}
        if len(self._drafts) == 0:
            raise ValueError("PREBREAKOUT_POLICY_DRAFT_REQUIRED")

    def validate_approval(self, approval: PreBreakoutPolicyApproval) -> ApprovedPreBreakoutPolicyView:
        draft = self._draft(approval.policy_id, approval.policy_version)
        self._verify_approval_fingerprint(approval)
        if approval.draft_policy_fingerprint != prebreakout_policy_draft_fingerprint(draft):
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_DRAFT_FINGERPRINT_MISMATCH")
        policy = PreBreakoutApprovedPolicy.from_draft(draft)
        if approval.approved_policy_fingerprint != policy.fingerprint:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_POLICY_FINGERPRINT_MISMATCH")
        if approval.approved_values_fingerprint != policy.values_fingerprint:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_VALUES_FINGERPRINT_MISMATCH")
        return ApprovedPreBreakoutPolicyView(
            policy=policy,
            approval=approval,
            policy_fingerprint=policy.fingerprint,
            approval_fingerprint=approval.fingerprint,
            approval_status=(
                PreBreakoutPolicyGovernanceState.APPROVED
                if approval.decision is PreBreakoutPolicyApprovalDecision.APPROVE
                else PreBreakoutPolicyGovernanceState.DRAFT
            ),
            unresolved_fields=policy.unresolved_fields,
        )

    def reconstruct_approved_policy(self, approval_id: str) -> ApprovedPreBreakoutPolicyView:
        approval = self._repository.get_prebreakout_policy_approval(approval_id)
        if approval is None:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_NOT_FOUND")
        view = self.validate_approval(approval)
        if approval.decision is not PreBreakoutPolicyApprovalDecision.APPROVE:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_NOT_APPROVED")
        return view

    def validate_selection(self, selection: PreBreakoutPolicySelection) -> SelectedPreBreakoutPolicyView:
        self._verify_selection_fingerprint(selection)
        if selection.selection_context is not PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_SELECTION_CONTEXT_INVALID")
        approval_view = self.reconstruct_approved_policy(selection.approval_id)
        approval = approval_view.approval
        if (selection.policy_id, selection.policy_version, selection.policy_fingerprint) != (
            approval.policy_id,
            approval.policy_version,
            approval.approved_policy_fingerprint,
        ):
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_SELECTION_APPROVAL_LINEAGE_MISMATCH")
        if selection.effective_from < approval.reviewed_at:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_SELECTION_PRECEDES_APPROVAL")
        return SelectedPreBreakoutPolicyView(
            policy=approval_view.policy,
            approval=approval,
            selection=selection,
            policy_fingerprint=approval_view.policy_fingerprint,
            approval_fingerprint=approval.fingerprint,
            selection_fingerprint=selection.fingerprint,
            state=PreBreakoutPolicyGovernanceState.SELECTED_FOR_SCAN,
            unresolved_fields=approval_view.unresolved_fields,
        )

    def get_selected_prebreakout_policy(
        self,
        *,
        context: PreBreakoutPolicySelectionContext,
        as_of: datetime,
    ) -> SelectedPreBreakoutPolicyView | None:
        _aware(as_of, "PREBREAKOUT_POLICY_AS_OF_NAIVE")
        eligible = tuple(
            selection
            for selection in self._repository.list_prebreakout_policy_selections(context=context)
            if selection.effective_from <= as_of
        )
        if not eligible:
            return None
        # Temporal selection is explicit and deterministic, never insertion order.
        selected = max(
            eligible,
            key=lambda value: (value.effective_from, value.selected_at, value.selection_id),
        )
        return self.validate_selection(selected)

    def prebreakout_policy_governance_status(self, *, as_of: datetime) -> PreBreakoutPolicyGovernanceStatus:
        _aware(as_of, "PREBREAKOUT_POLICY_AS_OF_NAIVE")
        approvals = self._repository.list_prebreakout_policy_approvals()
        approval_valid = False
        latest_approval: ApprovedPreBreakoutPolicyView | None = None
        for approval in approvals:
            view = self.validate_approval(approval)
            approval_valid = approval_valid or approval.decision is PreBreakoutPolicyApprovalDecision.APPROVE
            if approval.decision is PreBreakoutPolicyApprovalDecision.APPROVE and (
                latest_approval is None or (approval.reviewed_at, approval.created_at, approval.approval_id) >
                (latest_approval.approval.reviewed_at, latest_approval.approval.created_at, latest_approval.approval.approval_id)
            ):
                latest_approval = view
        selections = self._repository.list_prebreakout_policy_selections(
            context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
        )
        selected = self.get_selected_prebreakout_policy(
            context=PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
            as_of=as_of,
        )
        return PreBreakoutPolicyGovernanceStatus(
            draft_present=bool(self._drafts),
            approval_present=bool(approvals),
            approval_valid=approval_valid,
            selection_present=bool(selections),
            selection_valid=selected is not None,
            selected_for_current_scan=selected is not None,
            policy_version=(selected.policy.version if selected else latest_approval.policy.version if latest_approval else None),
            policy_fingerprint=(selected.policy_fingerprint if selected else latest_approval.policy_fingerprint if latest_approval else None),
            unresolved_fields=(selected.unresolved_fields if selected else latest_approval.unresolved_fields if latest_approval else ()),
        )

    def _draft(self, policy_id: str, version: str) -> PreBreakoutPolicyDraft:
        draft = self._drafts.get((policy_id, version))
        if draft is None:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_DRAFT_NOT_FOUND")
        return draft

    @staticmethod
    def _verify_approval_fingerprint(value: PreBreakoutPolicyApproval) -> None:
        expected = prebreakout_policy_approval_fingerprint(
            approval_id=value.approval_id,
            policy_id=value.policy_id,
            policy_version=value.policy_version,
            draft_policy_fingerprint=value.draft_policy_fingerprint,
            approved_policy_fingerprint=value.approved_policy_fingerprint,
            approved_values_fingerprint=value.approved_values_fingerprint,
            reviewer_id=value.reviewer_id,
            reviewed_at=value.reviewed_at.isoformat(),
            decision=value.decision.value,
            created_at=value.created_at.isoformat(),
            warnings=value.warnings,
        )
        if value.fingerprint != expected:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_APPROVAL_FINGERPRINT_MISMATCH")

    @staticmethod
    def _verify_selection_fingerprint(value: PreBreakoutPolicySelection) -> None:
        expected = prebreakout_policy_selection_fingerprint(
            selection_id=value.selection_id,
            approval_id=value.approval_id,
            policy_id=value.policy_id,
            policy_version=value.policy_version,
            policy_fingerprint=value.policy_fingerprint,
            selection_context=value.selection_context.value,
            selected_by=value.selected_by,
            selected_at=value.selected_at.isoformat(),
            effective_from=value.effective_from.isoformat(),
            warnings=value.warnings,
        )
        if value.fingerprint != expected:
            raise PreBreakoutPolicyGovernanceError("PREBREAKOUT_POLICY_SELECTION_FINGERPRINT_MISMATCH")


def _aware(value: datetime, code: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PreBreakoutPolicyGovernanceError(code)
