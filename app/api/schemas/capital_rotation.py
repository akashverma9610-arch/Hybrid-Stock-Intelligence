"""Public, deliberately distilled capital-rotation HTTP models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CapitalRotationOpportunityResponse(BaseModel):
    """A public-safe analytical comparison, never an execution instruction."""

    current_holding_symbol: str | None
    current_holding_score: Decimal | None
    candidate_symbol: str
    candidate_score: Decimal | None
    score_advantage: Decimal | None
    candidate_confidence: float | None
    holding_confidence: float | None
    candidate_risk_reward: Decimal | None
    sector_context: str | None
    catalyst_context: str | None
    freshness: str
    execution_eligibility: str
    public_gate_summary: tuple[str, ...]
    recommended_action: str
    rationale: str
    invalidation_summary: str | None
    warnings: tuple[str, ...]


class CapitalRotationSummaryResponse(BaseModel):
    holding_count: int
    portfolio_heat: Decimal | None
    weakest_holding_symbol: str | None


class CapitalRotationResponse(BaseModel):
    generated_at: datetime
    data_as_of: datetime | None
    portfolio_reference: str | None
    overall_status: str
    market_regime: str | None
    freshness: str
    cycle_id: str | None
    opportunity_coverage: str = "UNAVAILABLE"
    universe_count: int | None = None
    eligible_count: int | None = None
    analyzed_count: int | None = None
    analyzed_complete: int | None = None
    analyzed_partial: int | None = None
    qualified_candidate_count: int | None = None
    rotation_comparison_status: str = "UNAVAILABLE"
    summary: CapitalRotationSummaryResponse | None
    opportunities: tuple[CapitalRotationOpportunityResponse, ...]
    warnings: tuple[str, ...]
    message: str | None = None
