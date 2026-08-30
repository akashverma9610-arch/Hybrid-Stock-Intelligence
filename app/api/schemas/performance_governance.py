"""Explicit read-only schemas for stored performance, benchmark, and governance data."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PerformanceResponse(BaseModel):
    report_id: str
    strategy_version: str
    source_run_id: str | None
    mode: str | None
    start: datetime
    end: datetime
    generated_at: datetime
    total_trades: int | None
    closed_trades: int | None
    win_rate: Decimal | None
    expectancy: Decimal | None
    average_r: Decimal | None
    profit_factor: Decimal | None
    total_return: Decimal | None
    cagr: Decimal | None
    max_drawdown: Decimal | None
    volatility: Decimal | None
    sharpe: Decimal | None
    sortino: Decimal | None
    turnover: Decimal | None
    costs: Decimal | None
    capital_efficiency: Decimal | None
    sample_status: str | None
    warnings: tuple[str, ...]


class PerformanceListResponse(BaseModel):
    items: tuple[PerformanceResponse, ...]
    total: int
    limit: int
    offset: int


class BenchmarkResponse(BaseModel):
    comparison_id: str
    benchmark_id: str
    benchmark_version: str
    report_id: str | None
    mode: str | None
    start: datetime | None
    end: datetime | None
    strategy_return: Decimal | None
    benchmark_return: Decimal | None
    excess_return: Decimal | None
    strategy_cagr: Decimal | None
    benchmark_cagr: Decimal | None
    strategy_drawdown: Decimal | None
    benchmark_drawdown: Decimal | None
    strategy_sharpe: Decimal | None
    benchmark_sharpe: Decimal | None
    strategy_sortino: Decimal | None
    benchmark_sortino: Decimal | None
    strategy_volatility: Decimal | None
    benchmark_volatility: Decimal | None
    strategy_costs: Decimal | None
    benchmark_costs: Decimal | None
    classification: str
    alignment_status: str | None
    warnings: tuple[str, ...]


class BenchmarkListResponse(BaseModel):
    items: tuple[BenchmarkResponse, ...]
    total: int
    limit: int
    offset: int


class StrategyVersionResponse(BaseModel):
    approved_id: str
    strategy_id: str
    version: str
    parent_approved_id: str | None
    proposal_id: str
    review_id: str
    candidate_id: str
    config_fingerprints: tuple[str, ...]
    approved_at: datetime
    effective_from: datetime
    status: str
    methodology_notes: tuple[str, ...]
    fingerprint: str


class StrategyVersionListResponse(BaseModel):
    items: tuple[StrategyVersionResponse, ...]
    total: int
    limit: int
    offset: int


class ActiveStrategyResponse(BaseModel):
    active: bool
    activation_id: str | None
    active_version: StrategyVersionResponse | None
    previous_approved_id: str | None
    effective_at: datetime | None
    reason: str | None
    fingerprint: str | None


class PromotionSummaryResponse(BaseModel):
    proposal_id: str
    candidate_id: str
    baseline_strategy_id: str
    baseline_version: str
    status: str
    eligibility_status: str | None
    eligibility_reasons: tuple[str, ...]
    review_decision: str | None
    reviewed_at: datetime | None
    approved_version_id: str | None
    activation_id: str | None
    rollback_id: str | None
    created_at: datetime
    warnings: tuple[str, ...]
    provenance_ids: tuple[str, ...]


class PromotionListResponse(BaseModel):
    items: tuple[PromotionSummaryResponse, ...]
    total: int
    limit: int
    offset: int
