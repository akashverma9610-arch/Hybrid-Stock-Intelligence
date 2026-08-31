"""Read-only public projection of canonical capital-rotation evaluations.

The projection consumes a completed immutable evaluation. It never invokes the
rotation engine, changes a portfolio, or exposes configuration/gate internals.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from app.api.schemas.capital_rotation import (
    CapitalRotationOpportunityResponse,
    CapitalRotationResponse,
    CapitalRotationSummaryResponse,
)
from app.rotation.models import PortfolioRotationEvaluation, RotationDecisionState, RotationStance


class CapitalRotationQueryService(Protocol):
    """Read-model contract; implementations must not run or mutate rotation."""

    def get_rotation(self, *, holding_symbol: str | None = None, candidate_symbol: str | None = None, limit: int | None = None) -> CapitalRotationResponse: ...


class SnapshotCapitalRotationQueryService:
    """Projects one already-materialized canonical evaluation into public fields."""

    def __init__(self, evaluation: PortfolioRotationEvaluation | None, *, market_regime: str | None = None, coverage=None) -> None:
        self._evaluation = evaluation
        self._market_regime = market_regime
        self._coverage = coverage

    def get_rotation(self, *, holding_symbol: str | None = None, candidate_symbol: str | None = None, limit: int | None = None) -> CapitalRotationResponse:
        evaluation = self._evaluation
        now = datetime.now(timezone.utc)
        if evaluation is None:
            return CapitalRotationResponse(
                generated_at=now, data_as_of=None, portfolio_reference=None, overall_status="UNAVAILABLE",
                market_regime=None, freshness="UNAVAILABLE", cycle_id=None, summary=None, opportunities=(),
                opportunity_coverage="UNAVAILABLE",
                warnings=("ROTATION_EVALUATION_UNAVAILABLE",),
                message="No persisted capital-rotation evaluation is available.",
            )

        comparisons = tuple(
            item for item in evaluation.comparisons
            if (holding_symbol is None or item.holding_instrument_id == holding_symbol)
            and (candidate_symbol is None or item.candidate_instrument_id == candidate_symbol)
        )
        if limit is not None:
            comparisons = comparisons[:limit]
        candidates = {item.candidate.instrument_id: item.candidate for item in evaluation.ranked_candidates}
        opportunities = tuple(_opportunity(item, candidates.get(item.candidate_instrument_id), evaluation.execution_eligibility) for item in comparisons)
        status = _status(evaluation)
        if not evaluation.context.holdings and not evaluation.context.candidates:
            status = "EMPTY"
        warnings = _public_warnings(evaluation)
        if self._market_regime is None:
            warnings = (*warnings, "MARKET_CONTEXT_UNAVAILABLE")
        return CapitalRotationResponse(
            generated_at=evaluation.context.as_of_timestamp,
            data_as_of=evaluation.context.as_of_timestamp,
            # The evaluation's snapshot ID is an audit-internal identifier and
            # is not a public portfolio reference.
            portfolio_reference=None,
            overall_status=status,
            market_regime=self._market_regime,
            freshness="AS_OF_SNAPSHOT",
            cycle_id=None,
            opportunity_coverage=(self._coverage.coverage_status.value if self._coverage is not None else "PORTFOLIO_ONLY"),
            universe_count=(self._coverage.universe_total if self._coverage is not None else None),
            eligible_count=(self._coverage.eligible_total if self._coverage is not None else None),
            analyzed_count=((self._coverage.analyzed_complete + self._coverage.analyzed_partial) if self._coverage is not None else None),
            analyzed_complete=(self._coverage.analyzed_complete if self._coverage is not None else None),
            analyzed_partial=(self._coverage.analyzed_partial if self._coverage is not None else None),
            qualified_candidate_count=(self._coverage.qualified_candidates if self._coverage is not None else None),
            rotation_comparison_status=evaluation.comparison_status.value,
            summary=CapitalRotationSummaryResponse(
                holding_count=len(evaluation.context.holdings),
                portfolio_heat=_portfolio_heat(evaluation),
                weakest_holding_symbol=evaluation.weakest_holding_id,
            ),
            opportunities=opportunities,
            warnings=warnings,
            message=("No eligible rotation comparison is currently available." if not opportunities and status == "READY" else None),
        )


class UnavailableCapitalRotationQueryService(SnapshotCapitalRotationQueryService):
    def __init__(self) -> None:
        super().__init__(None)


def _opportunity(value, candidate, execution) -> CapitalRotationOpportunityResponse:
    action = _action(value.result, execution)
    eligibility, gate_summary = _eligibility(value, execution)
    return CapitalRotationOpportunityResponse(
        current_holding_symbol=value.holding_instrument_id,
        current_holding_score=value.holding_comparison_score,
        candidate_symbol=value.candidate_instrument_id,
        candidate_score=value.candidate_score,
        score_advantage=value.score_gap,
        candidate_confidence=value.candidate_confidence,
        holding_confidence=value.holding_confidence,
        candidate_risk_reward=value.candidate_risk_reward,
        sector_context=_sector_context(value),
        catalyst_context=(candidate.catalyst_timing if candidate and candidate.catalyst_timing else None),
        freshness="AS_OF_SNAPSHOT",
        execution_eligibility=eligibility,
        public_gate_summary=gate_summary,
        recommended_action=action,
        rationale=_rationale(value, action),
        invalidation_summary=("Current holding has invalidation concerns." if value.holding_invalidated else None),
        warnings=_public_comparison_warnings(value),
    )


def _status(value: PortfolioRotationEvaluation) -> str:
    if value.stance is RotationStance.INSUFFICIENT_DATA or value.decision is RotationDecisionState.INSUFFICIENT_DATA:
        return "PARTIAL"
    return "READY"


def _action(value: RotationDecisionState, execution) -> str:
    if execution.value == "EXECUTION_BLOCKED_CASH_UNKNOWN" and value is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
        return "NO_ACTION"
    return {
        RotationDecisionState.ROTATE_CANDIDATE_PREFERRED: "ROTATE",
        RotationDecisionState.KEEP_EXISTING: "HOLD",
        RotationDecisionState.CASH_PREFERRED: "WATCH",
        RotationDecisionState.NO_ACTION: "NO_ACTION",
        RotationDecisionState.INSUFFICIENT_DATA: "WATCH",
        RotationDecisionState.COMPARISON_AVAILABLE_EXECUTION_BLOCKED: "NO_ACTION",
    }[value]


def _eligibility(value, execution) -> tuple[str, tuple[str, ...]]:
    if execution.value == "EXECUTION_BLOCKED_CASH_UNKNOWN" and value.result is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
        return "BLOCKED", ("Candidate comparison is available; execution sizing is blocked because cash is unknown.",)
    if value.result is RotationDecisionState.ROTATE_CANDIDATE_PREFERRED:
        return "ELIGIBLE", ("Published analytical conditions are satisfied.",)
    if value.result is RotationDecisionState.INSUFFICIENT_DATA:
        return "PARTIAL", ("Analytical input is incomplete.",)
    if value.friction_status in {"FAIL", "INSUFFICIENT_DATA"}:
        return "BLOCKED", ("Rotation economics or supporting data do not permit a switch.",)
    return "CAUTION", ("The comparison does not support replacing the current holding.",)


def _rationale(value, action: str) -> str:
    if action == "ROTATE":
        return "Candidate has a stronger published score with eligible analytical context."
    if value.holding_invalidated:
        return "Current holding has invalidation concerns; the comparison remains analytical only."
    if value.friction_status in {"FAIL", "INSUFFICIENT_DATA"}:
        return "Candidate comparison is not actionable because rotation economics or supporting data are incomplete."
    if action == "WATCH":
        return "Additional complete analytical evidence is required before a rotation comparison can be acted on."
    return "Current holding remains acceptable; the published comparison does not support a rotation."


def _sector_context(value) -> str | None:
    if value.holding_sector and value.candidate_sector:
        return f"Holding: {value.holding_sector}; candidate: {value.candidate_sector}"
    return value.candidate_sector or value.holding_sector


def _portfolio_heat(value: PortfolioRotationEvaluation):
    values = tuple(item.heat for item in value.context.holdings)
    return sum(values) if values and all(item is not None for item in values) else None


def _public_warnings(value: PortfolioRotationEvaluation) -> tuple[str, ...]:
    warnings: list[str] = []
    if value.stance is RotationStance.INSUFFICIENT_DATA:
        warnings.append("ROTATION_DATA_PARTIAL")
    if any(item.startswith("ANTI_CHURN") for item in value.warnings):
        warnings.append("ROTATION_REVIEW_COOLDOWN_ACTIVE")
    if any(item.startswith("UNRESOLVED_CONFIG") for item in value.warnings):
        warnings.append("ROTATION_CONFIGURATION_INCOMPLETE")
    if value.blocked_candidate_ids:
        warnings.append("ROTATION_CANDIDATES_BLOCKED")
    return tuple(dict.fromkeys(warnings))


def _public_comparison_warnings(value) -> tuple[str, ...]:
    warnings: list[str] = []
    if value.friction_status == "INSUFFICIENT_DATA":
        warnings.append("ROTATION_ECONOMICS_DATA_PARTIAL")
    if value.holding_invalidated:
        warnings.append("HOLDING_INVALIDATION_CONCERN")
    return tuple(warnings)
