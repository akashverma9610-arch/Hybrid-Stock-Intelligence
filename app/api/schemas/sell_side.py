from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SellSideHoldingDecisionResponse(BaseModel):
    holding_id: str
    as_of: datetime
    action: str
    thesis_state: str
    capital_efficiency_state: str | None
    rotation_state: str | None
    reasons: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_freshness: str
    policy_fingerprint: str


class SellSidePortfolioResponse(BaseModel):
    status: str
    portfolio_snapshot_id: str | None
    policy_fingerprint: str
    decisions: tuple[SellSideHoldingDecisionResponse, ...]
    warnings: tuple[str, ...]

