from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import datetime

from .models import (
    PortfolioRotationEvaluation, RankedCandidate, RotationCandidate, RotationComparison,
    RotationConfig, RotationDecisionState, RotationEvaluationContext, RotationHoldingState, RotationStance,
)


class CapitalRotationEngine:
    """Ranks fully disclosed analytical alternatives; it never emits a trading instruction."""
    def __init__(self, config: RotationConfig): self.config = config

    def evaluate(self, context: RotationEvaluationContext, evaluated_at: datetime) -> PortfolioRotationEvaluation:
        unresolved = self.config.unresolved()
        self._assert_asof(context)
        context = replace(context, candidates=tuple(x for x in context.candidates if x.as_of_timestamp <= context.as_of_timestamp and x.known_at <= context.as_of_timestamp))
        candidates, blocked = self._eligible_candidates(context, unresolved)
        ranked_candidates = self._rank_candidates(candidates)
        ranked_holdings = self._rank_holdings(context.holdings)
        comparable = tuple(x for x in ranked_holdings if x.comparison_score is not None)
        weakest = comparable[0] if comparable else None; strongest = comparable[-1] if comparable else None
        comparisons = tuple(self._compare(holding, rank.candidate, context, unresolved) for holding in comparable for rank in ranked_candidates)
        best = ranked_candidates[0].candidate if ranked_candidates else None
        if best and not comparable:
            comparisons = (self._cash_comparison(best),)
        selected = next((x for x in comparisons if best and x.candidate_instrument_id == best.instrument_id and x.holding_instrument_id == (weakest.instrument_id if weakest else None)), None)
        cooldown = context.last_rotation_at is not None and (context.as_of_timestamp - context.last_rotation_at).days < self.config.cooldown_days
        warnings = [f"UNRESOLVED_CONFIG:{x}" for x in unresolved] + (["ANTI_CHURN_COOLDOWN_ACTIVE"] if cooldown else [])
        if unresolved or (context.holdings and weakest is None): stance, decision = RotationStance.INSUFFICIENT_DATA, RotationDecisionState.INSUFFICIENT_DATA
        elif not best:
            invalidated = any(x.invalidated for x in context.holdings)
            stance, decision = (RotationStance.DEFENSIVE_CASH, RotationDecisionState.CASH_PREFERRED) if invalidated else (RotationStance.NO_ROTATION, RotationDecisionState.NO_ACTION)
        elif selected and selected.result is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED and not cooldown:
            stance, decision = RotationStance.ROTATION_OPPORTUNITY, RotationDecisionState.ROTATE_CANDIDATE_PREFERRED
        else: stance, decision = RotationStance.NO_ROTATION, RotationDecisionState.NO_ACTION
        marker = f"{context.portfolio_snapshot_id}|{context.as_of_timestamp.isoformat()}|{self.config.version}"
        return PortfolioRotationEvaluation("rotation-" + hashlib.sha256(marker.encode()).hexdigest()[:20], context, self.config.version,
            ranked_holdings, ranked_candidates, tuple(sorted(blocked)), weakest.instrument_id if weakest else None,
            strongest.instrument_id if strongest else None, comparisons, stance, best.instrument_id if stance is RotationStance.ROTATION_OPPORTUNITY else None,
            decision, tuple(sorted(set(warnings + ["NO_ORDER_OR_CAPITAL_MOVEMENT_CREATED"]))))

    def _eligible_candidates(self, context, unresolved):
        eligible, blocked = [], []
        for candidate in context.candidates:
            reasons = self._candidate_failures(candidate, context, unresolved)
            if reasons: blocked.append(candidate.instrument_id)
            else: eligible.append(candidate)
        return tuple(eligible), tuple(blocked)

    def _candidate_failures(self, candidate, context, unresolved):
        if candidate.as_of_timestamp > context.as_of_timestamp or candidate.known_at > context.as_of_timestamp: return ("FUTURE_CANDIDATE",)
        failures = []
        if unresolved: failures.append("UNRESOLVED_CONFIG")
        if candidate.decision_scorecard_id is None or candidate.raw_decision_score is None or candidate.score_status != "COMPLETE": failures.append("INCOMPLETE_SCORE")
        if candidate.data_confidence is None or self.config.minimum_confidence is None or candidate.data_confidence < self.config.minimum_confidence: failures.append("INSUFFICIENT_CONFIDENCE")
        if candidate.gate_evaluation_id is None or candidate.gate_status != "EXECUTABLE" or candidate.portfolio_constraints_ok is not True: failures.append("GATE_OR_PORTFOLIO_CONSTRAINT")
        if candidate.structural_risk_reward is None or self.config.minimum_risk_reward is None or candidate.structural_risk_reward < self.config.minimum_risk_reward: failures.append("RISK_REWARD")
        if candidate.blocking_warning: failures.append("BLOCKING_WARNING")
        if self.config.require_entry_stop_invalidation and not all((candidate.entry_valid, candidate.stop_valid, candidate.invalidation_valid)): failures.append("INVALID_STRUCTURE")
        if self.config.require_supportive_sector and candidate.sector_supportive is not True: failures.append("SECTOR_POLICY")
        if self.config.require_friction_check and (candidate.modeled_switching_friction is None or candidate.expected_incremental_benefit is None or candidate.expected_incremental_benefit < candidate.modeled_switching_friction): failures.append("FRICTION")
        if candidate.confirmation_count < (self.config.min_confirmations or 0): failures.append("ANTI_CHURN_CONFIRMATION")
        return tuple(failures)

    def _rank_candidates(self, candidates):
        ordered = sorted(candidates, key=lambda x: (-x.raw_decision_score, -x.data_confidence, -x.structural_risk_reward, x.instrument_id))
        return tuple(RankedCandidate(item, index + 1, {"score": str(item.raw_decision_score), "confidence": str(item.data_confidence), "risk_reward": str(item.structural_risk_reward)}, "score; then confidence; then risk/reward; then configured instrument identifier" if index else "highest score") for index, item in enumerate(ordered))

    def _rank_holdings(self, holdings):
        return tuple(sorted(holdings, key=lambda x: (x.comparison_score is None, x.comparison_score if x.comparison_score is not None else 0, x.data_confidence if x.data_confidence is not None else -1, x.current_forward_risk_reward if x.current_forward_risk_reward is not None else -1, x.instrument_id)))

    def _compare(self, holding, candidate, context, unresolved):
        gap = candidate.raw_decision_score - holding.comparison_score if holding.comparison_score is not None else None
        for_reasons, against = [], []
        friction = "NOT_REQUIRED"
        if self.config.require_friction_check:
            if candidate.modeled_switching_friction is None or candidate.expected_incremental_benefit is None: friction, against = "INSUFFICIENT_DATA", ["FRICTION_UNAVAILABLE"]
            elif candidate.expected_incremental_benefit >= candidate.modeled_switching_friction: friction, for_reasons = "PASS", ["FRICTION_COVERED"]
            else: friction, against = "FAIL", ["FRICTION_EXCEEDS_BENEFIT"]
        if gap is not None and self.config.min_score_advantage is not None and gap >= self.config.min_score_advantage: for_reasons.append("SCORE_HURDLE_MET")
        else: against.append("SCORE_HURDLE_NOT_MET")
        if holding.invalidated: for_reasons.append("HOLDING_INVALIDATED")
        if candidate.structural_risk_reward is not None and self.config.minimum_risk_reward is not None and candidate.structural_risk_reward >= self.config.minimum_risk_reward: for_reasons.append("CANDIDATE_RR_MET")
        outcome = RotationDecisionState.ROTATE_CANDIDATE_PREFERRED if not unresolved and gap is not None and gap >= self.config.min_score_advantage and friction in {"PASS", "NOT_REQUIRED"} else RotationDecisionState.KEEP_EXISTING
        return RotationComparison(holding.instrument_id, candidate.instrument_id, holding.comparison_score, candidate.raw_decision_score, gap, self.config.min_score_advantage, holding.sector, candidate.sector, holding.current_forward_risk_reward, candidate.structural_risk_reward, holding.data_confidence, candidate.data_confidence, holding.invalidated, candidate.gate_status, friction, outcome, tuple(for_reasons), tuple(against), tuple(sorted(set(holding.warnings + candidate.warnings))))

    @staticmethod
    def _cash_comparison(candidate):
        return RotationComparison(None, candidate.instrument_id, None, candidate.raw_decision_score, None, None, None, candidate.sector,
            None, candidate.structural_risk_reward, None, candidate.data_confidence, None, candidate.gate_status, "NOT_APPLICABLE_CASH",
            RotationDecisionState.ROTATE_CANDIDATE_PREFERRED, ("CASH_DEPLOYMENT_OPPORTUNITY",), (), candidate.warnings)

    @staticmethod
    def _assert_asof(context):
        if any(x.as_of_timestamp > context.as_of_timestamp or x.known_at > context.as_of_timestamp for x in context.holdings):
            raise ValueError("Holding analytics outside the approved as-of context are not accepted.")
