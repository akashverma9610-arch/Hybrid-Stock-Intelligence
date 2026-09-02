from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SellSideHoldingDecisionResponse(BaseModel):
    holding_id: str
    portfolio_snapshot_as_of: datetime
    intelligence_as_of: datetime
    latest_completed_market_session: datetime | None
    # Retained for clients that consumed the original projection.  New clients
    # must use the explicit fields above; this value is the intelligence cutoff.
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
