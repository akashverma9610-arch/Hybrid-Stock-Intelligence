from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class StockIdentityResponse(BaseModel):
    symbol: str
    exchange: str | None
    name: str | None
    sector: str | None
    industry: str | None


class StockDataStatusResponse(BaseModel):
    analysis_timestamp: datetime
    data_as_of: datetime
    status: str
    warnings: tuple[str, ...]


class StockListItemResponse(BaseModel):
    symbol: str
    exchange: str | None
    company_name: str | None
    sector: str | None
    latest_score: Decimal | None
    confidence: float | None
    score_status: str | None
    data_as_of: datetime
    freshness: str
    status: str
    warnings: tuple[str, ...]


class StockListResponse(BaseModel):
    items: tuple[StockListItemResponse, ...]
    total: int


class StockMarketContextResponse(BaseModel):
    market_regime: str | None
    sector_phase: str | None
    sector_rank: int | None


class AnalysisCoverageResponse(BaseModel):
    """Public availability summary; the proprietary diagnostic inventory stays private."""

    status: str
    warnings: tuple[str, ...]


class DecisionScoreResponse(BaseModel):
    final_score: Decimal | None
    score_status: str
    confidence: float | None
    warnings: tuple[str, ...]


class ExecutionGatesResponse(BaseModel):
    overall_status: str
    warnings: tuple[str, ...]


class AnalysisSectionResponse(BaseModel):
    status: str
    warnings: tuple[str, ...]


class StockAnalysisResponse(BaseModel):
    identity: StockIdentityResponse
    data: StockDataStatusResponse
    market_context: StockMarketContextResponse
    analysis_coverage: AnalysisCoverageResponse
    decision: DecisionScoreResponse | None
    execution_gates: ExecutionGatesResponse | None
    technical: AnalysisSectionResponse | None
    fundamentals: AnalysisSectionResponse | None
    research: AnalysisSectionResponse | None
    valuation: AnalysisSectionResponse | None
    trade_structure: AnalysisSectionResponse | None
    liquidity: AnalysisSectionResponse | None
