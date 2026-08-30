from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MarketRegimeResponse(BaseModel):
    result_id: str
    benchmark_instrument_id: str
    regime: str
    calculated_at: datetime
    data_as_of: datetime
    confidence: float | None
    status: str
    conditions: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class SectorResponse(BaseModel):
    sector_id: str
    sector_name: str | None
    phase: str
    rank: int | None
    relative_strength: Decimal | None
    score: float | None
    confidence: float | None
    calculated_at: datetime
    data_as_of: datetime
    status: str
    evidence_ids: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    warnings: tuple[str, ...]


class SectorListResponse(BaseModel):
    sectors: tuple[SectorResponse, ...]


class BreadthResponse(BaseModel):
    status: str
    generated_at: datetime
    data_as_of: datetime
    freshness: str
    universe_reference: str
    participation_state: str | None
    advances: int | None
    declines: int | None
    unchanged: int | None
    advance_decline_ratio: Decimal | None
    new_highs: int | None
    new_lows: int | None
    percent_above_reference: Decimal | None
    leadership_concentration: Decimal | None
    coverage_percent: Decimal | None
    warnings: tuple[str, ...]
    cycle_reference: str | None


class MarketExtremesResponse(BaseModel):
    status: str
    generated_at: datetime
    data_as_of: datetime
    market_state: str
    cycle_stage: str
    top_confirmed: bool
    distribution_risk: str
    leadership_quality: str
    price_earnings_divergence: str
    rationale: str
    warnings: tuple[str, ...]


class CrisisResponse(BaseModel):
    status: str
    generated_at: datetime
    data_as_of: datetime
    state: str
    risk_posture: str | None
    rationale: str
    warnings: tuple[str, ...]
