"""Pure approved-policy sell-side classification and immutable audit bridge."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from app.audit.decision import DecisionAuditRecord, DecisionAuditStore, DecisionOutcomeLink, decision_audit_fingerprint, decision_outcome_fingerprint
from app.historical.guard import manifest_fingerprint
from app.portfolio.models import PortfolioHolding, PortfolioSnapshot
from app.portfolio.sell_side_policy import (
    CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY, CapitalEfficiencyState,
    FrozenPortfolioSellSideDecisionPolicy, SellSideDecision, SellSideThesisState,
)
from app.rotation.models import PortfolioRotationEvaluation, RotationDecisionState, RotationExecutionEligibility
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class EvidenceFreshness(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    MISSING = "MISSING"
    CONFLICTED = "CONFLICTED"
    NON_COMPARABLE = "NON_COMPARABLE"


@dataclass(frozen=True, slots=True)
class PortfolioSellSideInput:
    portfolio_snapshot: PortfolioSnapshot
    holding: PortfolioHolding
    rotation_evaluation: PortfolioRotationEvaluation | None
    shared_brain_fingerprint: str | None
    evidence_conflicted: bool = False
    evidence_comparable: bool = True


@dataclass(frozen=True, slots=True)
class PortfolioSellSideDecision:
    decision_id: str
    canonical_holding_id: str
    as_of: datetime
    action: SellSideDecision
    thesis_state: SellSideThesisState
    capital_efficiency_state: CapitalEfficiencyState | None
    rotation_state: RotationDecisionState | None
    rotation_evaluation_id: str | None
    portfolio_snapshot_id: str
    portfolio_context_references: tuple[str, ...]
    evidence_freshness: EvidenceFreshness
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    shared_brain_fingerprint: str
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    fingerprint: str


def _thesis(value: PortfolioSellSideInput) -> tuple[SellSideThesisState, EvidenceFreshness, tuple[str, ...]]:
    analytics = value.holding.analytics
    if analytics is None or not value.shared_brain_fingerprint:
        return SellSideThesisState.INSUFFICIENT, EvidenceFreshness.MISSING, ("MISSING_THESIS_OR_SHARED_BRAIN_EVIDENCE",)
    if analytics.as_of_timestamp != value.portfolio_snapshot.as_of_timestamp or analytics.known_at > value.portfolio_snapshot.as_of_timestamp:
        return SellSideThesisState.INSUFFICIENT, EvidenceFreshness.STALE, ("STALE_OR_FUTURE_THESIS_EVIDENCE",)
    if value.evidence_conflicted:
        return SellSideThesisState.INSUFFICIENT, EvidenceFreshness.CONFLICTED, ("CONFLICTED_THESIS_EVIDENCE",)
    if not value.evidence_comparable:
        return SellSideThesisState.INSUFFICIENT, EvidenceFreshness.NON_COMPARABLE, ("NON_COMPARABLE_THESIS_EVIDENCE",)
    invalidation = analytics.invalidation_status
    trading = analytics.trading_thesis
    if invalidation in {"TRIGGERED", "BROKEN", "SEVERE_CONCERN"} or trading in {"INVALIDATED", "BROKEN"}:
        return SellSideThesisState.INVALIDATED, EvidenceFreshness.CURRENT, ("GOVERNED_THESIS_INVALIDATED",)
    if trading in {"MIXED", "WEAK"} or analytics.investment_thesis == "WEAK":
        return SellSideThesisState.WEAKENED, EvidenceFreshness.CURRENT, ("GOVERNED_THESIS_WEAKENED",)
    if trading in {"VALID", "STRONG"} and invalidation in {None, "INTACT"}:
        return SellSideThesisState.INTACT, EvidenceFreshness.CURRENT, ("GOVERNED_THESIS_INTACT",)
    return SellSideThesisState.INSUFFICIENT, EvidenceFreshness.MISSING, ("UNRESOLVED_THESIS_EVIDENCE",)


def _rotation(value: PortfolioSellSideInput) -> tuple[RotationDecisionState | None, str | None, tuple[str, ...]]:
    evaluation = value.rotation_evaluation
    if evaluation is None:
        return None, None, ("UNRESOLVED_REPLACEMENT_EVIDENCE",)
    if evaluation.context.as_of_timestamp != value.portfolio_snapshot.as_of_timestamp:
        return None, evaluation.evaluation_id, ("STALE_ROTATION_EVIDENCE",)
    matches = tuple(item for item in evaluation.comparisons if item.holding_instrument_id == value.holding.instrument_id)
    if evaluation.decision is RotationDecisionState.INSUFFICIENT_DATA:
        return evaluation.decision, evaluation.evaluation_id, ("INSUFFICIENT_ROTATION_EVIDENCE",)
    execution_eligibility = getattr(
        evaluation, "execution_eligibility", RotationExecutionEligibility.EXECUTION_ELIGIBLE,
    )
    if (
        evaluation.decision is RotationDecisionState.COMPARISON_AVAILABLE_EXECUTION_BLOCKED
        or execution_eligibility is RotationExecutionEligibility.EXECUTION_BLOCKED_CASH_UNKNOWN
        and evaluation.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
    ):
        return evaluation.decision, evaluation.evaluation_id, ("CASH_UNKNOWN_EXECUTION_BLOCKED",)
    if evaluation.decision is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED and not any(item.result is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED for item in matches):
        return evaluation.decision, evaluation.evaluation_id, ("UNRESOLVED_REPLACEMENT_EVIDENCE",)
    return evaluation.decision, evaluation.evaluation_id, ()


def evaluate_portfolio_sell_side_action(
    value: PortfolioSellSideInput,
    *,
    policy: FrozenPortfolioSellSideDecisionPolicy = CURRENT_FROZEN_PORTFOLIO_SELL_SIDE_DECISION_POLICY,
) -> PortfolioSellSideDecision:
    """Classify one existing holding without recalculating Brain/rotation inputs."""
    thesis, freshness, thesis_notes = _thesis(value)
    rotation, rotation_id, rotation_blockers = _rotation(value)
    policy_valid = (
        policy.policy_id == "portfolio-sell-side-decision-policy"
        and policy.version == "v1-approved"
        and policy.fingerprint == "78bef6fc3a5a3373d6ae27f48010ee431b16cf77bcab6a57da56413af579927f"
    )
    thesis_blockers = thesis_notes if thesis is SellSideThesisState.INSUFFICIENT else ()
    blockers = tuple(sorted(set(thesis_blockers + rotation_blockers + (() if policy_valid else ("POLICY_FINGERPRINT_MISMATCH",)))))
    rotation_holding = next((item for item in value.rotation_evaluation.context.holdings if item.instrument_id == value.holding.instrument_id), None) if value.rotation_evaluation else None
    capital = CapitalEfficiencyState.CAPITAL_INEFFICIENT if rotation_holding and rotation_holding.capital_velocity_adjustment != 0 else None
    if blockers:
        action, reasons = SellSideDecision.REVIEW_REQUIRED, ("FAIL_CLOSED_REVIEW_REQUIRED",)
    elif thesis is SellSideThesisState.INVALIDATED and rotation is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
        action, reasons = SellSideDecision.ROTATE, ("INVALIDATED_WITH_ELIGIBLE_GOVERNED_REPLACEMENT",)
    elif thesis is SellSideThesisState.INVALIDATED:
        action, reasons = SellSideDecision.EXIT_TO_CASH, ("INVALIDATED_WITHOUT_ELIGIBLE_GOVERNED_REPLACEMENT",)
    elif rotation is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
        action, reasons = SellSideDecision.ROTATE, ("VALID_GOVERNED_ROTATION",)
    elif thesis is SellSideThesisState.INTACT:
        action, reasons = SellSideDecision.HOLD, ("INTACT_THESIS_NO_STRONGER_APPROVED_ACTION",)
    else:
        action, reasons = SellSideDecision.NO_ACTION, ("NO_APPROVED_ACTION_SUPPORTED",)
    values = dict(
        canonical_holding_id=value.holding.holding_id, as_of=value.portfolio_snapshot.as_of_timestamp,
        action=action.value, thesis_state=thesis.value, capital_efficiency_state=None if capital is None else capital.value,
        rotation_state=None if rotation is None else rotation.value, rotation_evaluation_id=rotation_id,
        portfolio_snapshot_id=value.portfolio_snapshot.snapshot_id,
        portfolio_context_references=(value.portfolio_snapshot.snapshot_id,),
        evidence_freshness=freshness.value, reasons=reasons, blockers=blockers,
        shared_brain_fingerprint=value.shared_brain_fingerprint or "", policy_id=policy.policy_id,
        policy_version=policy.version, policy_fingerprint=policy.fingerprint,
    )
    fingerprint = manifest_fingerprint(**values)
    return PortfolioSellSideDecision(
        decision_id="sell-side-" + fingerprint[:20], fingerprint=fingerprint,
        canonical_holding_id=value.holding.holding_id, as_of=value.portfolio_snapshot.as_of_timestamp,
        action=action, thesis_state=thesis, capital_efficiency_state=capital, rotation_state=rotation,
        rotation_evaluation_id=rotation_id, portfolio_snapshot_id=value.portfolio_snapshot.snapshot_id,
        portfolio_context_references=(value.portfolio_snapshot.snapshot_id,), evidence_freshness=freshness,
        reasons=reasons, blockers=blockers, shared_brain_fingerprint=value.shared_brain_fingerprint or "",
        policy_id=policy.policy_id, policy_version=policy.version, policy_fingerprint=policy.fingerprint,
    )


class PortfolioSellSideDecisionAuditService:
    """Append-only sell-side decision and existing generic decision-audit persistence."""

    def __init__(self, repository: CoreApiSnapshotRepository):
        self._repository = repository
        self._audits = DecisionAuditStore(repository)

    def persist(self, value: PortfolioSellSideDecision) -> PortfolioSellSideDecision:
        snapshot_id = "sell-side-decision:" + value.decision_id
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.fingerprint != value.fingerprint or not isinstance(existing.payload, PortfolioSellSideDecision):
                raise ValueError("SELL_SIDE_DECISION_IMMUTABILITY_CONFLICT")
            return existing.payload
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.SELL_SIDE_DECISION, "v1", "portfolio-sell-side-decision-v1", value.fingerprint, value.as_of, value))
        record = DecisionAuditRecord(
            audit_id="sell-side-audit-" + value.decision_id, instrument_id=value.canonical_holding_id, as_of=value.as_of,
            portfolio_snapshot_id=value.portfolio_snapshot_id, universe_snapshot_id=None, market_context_snapshot_id=None,
            data_snapshot_ids=value.portfolio_context_references + (() if value.rotation_evaluation_id is None else (value.rotation_evaluation_id,)),
            source_summary=(value.thesis_state.value, value.evidence_freshness.value, *value.reasons, *value.blockers),
            diagnostic_registry_version="shared-brain-fingerprint:" + value.shared_brain_fingerprint,
            decision_score_version="holding-analytics-reference", confidence_version="holding-analytics-reference",
            gate_policy_version="existing-six-gates", rotation_policy_version=value.policy_version,
            engine_version="portfolio-sell-side-runtime-v1", final_public_decision=value.action.value,
            internal_evidence_ids=(value.fingerprint, value.policy_fingerprint), created_at=value.as_of, fingerprint="",
        )
        record = replace(record, fingerprint=decision_audit_fingerprint(record))
        self._audits.save_record(record)
        event = DecisionOutcomeLink(
            link_id="sell-side-event-" + value.decision_id, audit_id=record.audit_id,
            outcome_type="SELL_SIDE_DECISION_EVENT", outcome_id=value.decision_id, linked_at=value.as_of, fingerprint="",
        )
        event = replace(event, fingerprint=decision_outcome_fingerprint(event))
        self._audits.save_outcome(event)
        return value
