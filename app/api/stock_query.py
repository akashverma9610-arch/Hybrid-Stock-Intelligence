"""Read-only stock-analysis query facade; it contains no analytical formulas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.analysis.models import MarketRegimeResult
from app.api.errors import APIRequestError
from app.api.schemas.stocks import (
    AnalysisCoverageResponse,
    AnalysisSectionResponse,
    DecisionScoreResponse,
    ExecutionGatesResponse,
    StockAnalysisResponse,
    StockDataStatusResponse,
    StockIdentityResponse,
    StockListItemResponse,
    StockListResponse,
    StockMarketContextResponse,
)
from app.diagnostics.models import EvaluatedDiagnostic
from app.gates.engine import ExecutionGateEvaluation
from app.scoring.engine import DecisionScorecard


_SYMBOL = re.compile(r"^[A-Z][A-Z0-9_-]{0,19}$")


def normalize_stock_symbol(symbol: str) -> str:
    """Apply only local case/whitespace normalization; no exchange mapping exists."""
    normalized = symbol.strip().upper()
    if not _SYMBOL.fullmatch(normalized):
        raise APIRequestError(
            status_code=422,
            code="INVALID_SYMBOL",
            message="Symbol must use the locally supported identifier format.",
        )
    return normalized


class StockAnalysisQueryService(Protocol):
    def get_analysis(self, symbol: str) -> "StockAnalysisQueryResult": ...
    def list_analysis(self) -> tuple["StockAnalysisQueryResult", ...]: ...


class UnavailableStockAnalysisQueryService:
    def get_analysis(self, symbol: str) -> "StockAnalysisQueryResult":
        raise APIRequestError(
            status_code=503,
            code="STOCK_ANALYSIS_UNAVAILABLE",
            message="Stock analysis is not available.",
        )

    def list_analysis(self) -> tuple["StockAnalysisQueryResult", ...]:
        raise APIRequestError(
            status_code=503,
            code="STOCK_ANALYSIS_UNAVAILABLE",
            message="Stock analysis is not available.",
        )


@dataclass(frozen=True, slots=True)
class DiagnosticCoverageQueryRecord:
    total_count: int
    pass_count: int
    fail_count: int
    neutral_count: int
    unknown_count: int
    items: tuple[EvaluatedDiagnostic, ...]


@dataclass(frozen=True, slots=True)
class AnalysisSectionQueryRecord:
    status: str
    items: tuple[EvaluatedDiagnostic, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StockAnalysisQueryResult:
    symbol: str
    exchange: str | None
    name: str | None
    sector: str | None
    industry: str | None
    analysis_timestamp: datetime
    data_as_of: datetime
    status: str
    market_regime: MarketRegimeResult | None
    sector_phase: str | None
    sector_rank: int | None
    diagnostics: DiagnosticCoverageQueryRecord
    decision_scorecard: DecisionScorecard | None
    execution_gates: ExecutionGateEvaluation | None
    technical: AnalysisSectionQueryRecord | None = None
    fundamentals: AnalysisSectionQueryRecord | None = None
    research: AnalysisSectionQueryRecord | None = None
    valuation: AnalysisSectionQueryRecord | None = None
    trade_structure: AnalysisSectionQueryRecord | None = None
    liquidity: AnalysisSectionQueryRecord | None = None
    warnings: tuple[str, ...] = ()
    provenance_ids: tuple[str, ...] = ()


class SnapshotStockAnalysisQueryService:
    def __init__(self, results: tuple[StockAnalysisQueryResult, ...]) -> None:
        self._results = {result.symbol: result for result in results}

    def get_analysis(self, symbol: str) -> StockAnalysisQueryResult:
        result = self._results.get(symbol)
        if result is None:
            raise APIRequestError(
                status_code=404,
                code="STOCK_NOT_FOUND",
                message="Stock analysis was not found.",
            )
        return result

    def list_analysis(self) -> tuple[StockAnalysisQueryResult, ...]:
        return tuple(sorted(self._results.values(), key=lambda item: item.symbol))


def stock_analysis_response(value: StockAnalysisQueryResult) -> StockAnalysisResponse:
    return StockAnalysisResponse(
        identity=StockIdentityResponse(
            symbol=value.symbol,
            exchange=value.exchange,
            name=value.name,
            sector=value.sector,
            industry=value.industry,
        ),
        data=StockDataStatusResponse(
            analysis_timestamp=value.analysis_timestamp,
            data_as_of=value.data_as_of,
            status=value.status,
            warnings=value.warnings,
        ),
        market_context=StockMarketContextResponse(
            market_regime=value.market_regime.classification.value if value.market_regime else None,
            sector_phase=value.sector_phase,
            sector_rank=value.sector_rank,
        ),
        analysis_coverage=AnalysisCoverageResponse(
            status=_coverage_status(value.diagnostics),
            warnings=(),
        ),
        decision=_decision_response(value.decision_scorecard),
        execution_gates=_gates_response(value.execution_gates),
        technical=_section_response(value.technical),
        fundamentals=_section_response(value.fundamentals),
        research=_section_response(value.research),
        valuation=_section_response(value.valuation),
        trade_structure=_section_response(value.trade_structure),
        liquidity=_section_response(value.liquidity),
    )


def stock_list_response(values: tuple[StockAnalysisQueryResult, ...]) -> StockListResponse:
    """Expose only public persisted-summary fields; never enumerate diagnostics."""
    return StockListResponse(items=tuple(_stock_list_item(value) for value in values), total=len(values))


def _stock_list_item(value: StockAnalysisQueryResult) -> StockListItemResponse:
    score = _decision_response(value.decision_scorecard)
    return StockListItemResponse(
        symbol=value.symbol,
        exchange=value.exchange,
        company_name=value.name,
        sector=value.sector,
        latest_score=score.final_score if score else None,
        confidence=score.confidence if score else None,
        score_status=score.score_status if score else None,
        data_as_of=value.data_as_of,
        freshness="AS_OF_SNAPSHOT",
        status=value.status,
        warnings=value.warnings,
    )


def _coverage_status(value: DiagnosticCoverageQueryRecord) -> str:
    """Distil coverage without revealing inventory size, rule IDs, or results."""
    if value.total_count == 0:
        return "UNAVAILABLE"
    return "PARTIAL" if value.unknown_count or value.neutral_count else "COMPLETE"


def _decision_response(value: DecisionScorecard | None) -> DecisionScoreResponse | None:
    if value is None:
        return None
    return DecisionScoreResponse(
        final_score=value.final_score,
        score_status=value.score_status,
        confidence=value.data_confidence,
        warnings=value.warnings,
    )


def _gates_response(value: ExecutionGateEvaluation | None) -> ExecutionGatesResponse | None:
    if value is None:
        return None
    return ExecutionGatesResponse(
        overall_status=value.eligibility.value,
        warnings=value.warnings,
    )


def _section_response(value: AnalysisSectionQueryRecord | None) -> AnalysisSectionResponse | None:
    if value is None:
        return None
    return AnalysisSectionResponse(
        status=value.status,
        warnings=value.warnings,
    )
