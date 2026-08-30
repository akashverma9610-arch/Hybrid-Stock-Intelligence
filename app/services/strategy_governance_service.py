from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.domain.models import (
    ApprovalStatus, StrategyDefinition, StrategyLifecycleEvent, StrategyStatus,
    StrategyValidationStatus, StrategyVersionReference,
)
from app.storage.governance_repository import StrategyGovernanceRepository


class StrategyGovernanceError(ValueError):
    pass


class StrategyGovernanceService:
    """Creates immutable versions and records lifecycle changes append-only."""

    def __init__(self, repository: StrategyGovernanceRepository) -> None:
        self._repository = repository

    def create(self, definition: StrategyDefinition) -> StrategyDefinition:
        if self._repository.get_strategy_definition(definition.reference) is not None:
            raise StrategyGovernanceError("Strategy versions are immutable; create a new version instead.")
        if definition.status is StrategyStatus.ACTIVE and not self._is_approved_and_validated(definition):
            raise StrategyGovernanceError("An unapproved or unvalidated strategy cannot become active.")
        self._repository.save_strategy_definition(definition)
        self._repository.append_strategy_lifecycle_event(
            StrategyLifecycleEvent(
                id=f"{definition.strategy_id}:{definition.version}:created",
                strategy_version=definition.reference,
                status=definition.status,
                approval_status=definition.approval_status,
                validation_status=definition.validation_status,
                occurred_at=definition.created_at,
                actor_id=definition.author_reviewer.author_id,
                rationale="Immutable strategy version created.",
            )
        )
        return definition

    def create_next_version(self, definition: StrategyDefinition) -> StrategyDefinition:
        parent = definition.parent_strategy_version
        if parent is None or self._repository.get_strategy_definition(parent) is None:
            raise StrategyGovernanceError("A successor strategy version requires an existing parent version.")
        if parent == definition.reference:
            raise StrategyGovernanceError("A successor must use a new strategy version identifier.")
        return self.create(definition)

    def record_validation(
        self, reference: StrategyVersionReference, *, status: StrategyValidationStatus,
        occurred_at: datetime, actor_id: str, rationale: str, event_id: str,
    ) -> StrategyLifecycleEvent:
        current = self._current(reference)
        event = StrategyLifecycleEvent(
            event_id, reference, StrategyStatus.VALIDATION, current.approval_status, status,
            occurred_at, actor_id, rationale,
        )
        self._repository.append_strategy_lifecycle_event(event)
        return event

    def approve(
        self, reference: StrategyVersionReference, *, occurred_at: datetime, actor_id: str,
        rationale: str, event_id: str,
    ) -> StrategyLifecycleEvent:
        current = self._current(reference)
        if current.validation_status is not StrategyValidationStatus.PASSED:
            raise StrategyGovernanceError("A strategy must pass validation before approval.")
        event = StrategyLifecycleEvent(
            event_id, reference, StrategyStatus.APPROVED, ApprovalStatus.APPROVED,
            current.validation_status, occurred_at, actor_id, rationale,
        )
        self._repository.append_strategy_lifecycle_event(event)
        return event

    def activate(
        self, reference: StrategyVersionReference, *, effective_from: datetime,
        actor_id: str, rationale: str, event_id: str,
    ) -> StrategyLifecycleEvent:
        current = self._current(reference)
        if not (current.approval_status is ApprovalStatus.APPROVED and current.validation_status is StrategyValidationStatus.PASSED):
            raise StrategyGovernanceError("An unapproved or unvalidated strategy cannot become active.")
        event = StrategyLifecycleEvent(
            event_id, reference, StrategyStatus.ACTIVE, current.approval_status,
            current.validation_status, effective_from, actor_id, rationale,
        )
        self._repository.append_strategy_lifecycle_event(event)
        return event

    def _current(self, reference: StrategyVersionReference) -> StrategyLifecycleEvent:
        if self._repository.get_strategy_definition(reference) is None:
            raise StrategyGovernanceError("Strategy version does not exist.")
        current = self._repository.latest_strategy_lifecycle_event(reference)
        if current is None:
            raise StrategyGovernanceError("Strategy version is missing its lifecycle record.")
        return current

    @staticmethod
    def _is_approved_and_validated(definition: StrategyDefinition) -> bool:
        return (
            definition.approval_status is ApprovalStatus.APPROVED
            and definition.validation_status is StrategyValidationStatus.PASSED
        )
