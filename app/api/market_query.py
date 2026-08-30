"""Read-only market-regime and sector query facades for HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.analysis.models import AnalysisStatus, MarketRegimeResult
from app.api.errors import APIRequestError
from app.api.schemas.market import MarketRegimeResponse, SectorResponse
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility


class MarketRegimeQueryService(Protocol):
    def get_market_regime(self) -> MarketRegimeResult: ...


class SectorQueryService(Protocol):
    def list_sectors(self) -> tuple["SectorAnalysisQueryRecord", ...]: ...
    def get_sector(self, sector_id: str) -> "SectorAnalysisQueryRecord": ...


class UnavailableMarketRegimeQueryService:
    def get_market_regime(self) -> MarketRegimeResult:
        raise APIRequestError(
            status_code=503,
            code="MARKET_REGIME_UNAVAILABLE",
            message="Market regime analysis is not available.",
        )


class UnavailableSectorQueryService:
    def list_sectors(self) -> tuple["SectorAnalysisQueryRecord", ...]:
        raise APIRequestError(
            status_code=503,
            code="SECTOR_ANALYSIS_UNAVAILABLE",
            message="Sector analysis is not available.",
        )

    def get_sector(self, sector_id: str) -> "SectorAnalysisQueryRecord":
        raise APIRequestError(
            status_code=503,
            code="SECTOR_ANALYSIS_UNAVAILABLE",
            message="Sector analysis is not available.",
        )


class SnapshotMarketRegimeQueryService:
    def __init__(self, result: MarketRegimeResult) -> None:
        self._result = result

    def get_market_regime(self) -> MarketRegimeResult:
        return self._result


@dataclass(frozen=True, slots=True)
class SectorAnalysisQueryRecord:
    """Presentation reference to existing sector health/rotation diagnostics."""

    sector_id: str
    sector_name: str | None
    rotation: EvaluatedDiagnostic
    health: EvaluatedDiagnostic | None = None
    rank: int | None = None
    warnings: tuple[str, ...] = ()


class SnapshotSectorQueryService:
    def __init__(self, sectors: tuple[SectorAnalysisQueryRecord, ...]) -> None:
        self._sectors = sectors

    def list_sectors(self) -> tuple[SectorAnalysisQueryRecord, ...]:
        return self._sectors

    def get_sector(self, sector_id: str) -> SectorAnalysisQueryRecord:
        for sector in self._sectors:
            if sector.sector_id == sector_id:
                return sector
        raise APIRequestError(
            status_code=404,
            code="SECTOR_NOT_FOUND",
            message="Sector analysis was not found.",
        )


def market_regime_response(result: MarketRegimeResult) -> MarketRegimeResponse:
    warnings = () if result.status is AnalysisStatus.VALID else (f"ANALYSIS_STATUS:{result.status.value}",)
    return MarketRegimeResponse(
        result_id=result.id,
        benchmark_instrument_id=result.benchmark_instrument_id,
        regime=result.classification.value,
        calculated_at=result.evaluated_at,
        data_as_of=result.as_of_timestamp,
        confidence=result.confidence,
        status=result.status.value,
        conditions=result.conditions,
        evidence_ids=result.evidence_ids,
        input_observation_ids=result.input_observation_ids,
        warnings=warnings,
    )


def sector_response(value: SectorAnalysisQueryRecord) -> SectorResponse:
    record = value.rotation.record
    details = dict(value.rotation.details)
    warnings = value.warnings + (
        () if value.rotation.eligibility is EvaluationEligibility.ELIGIBLE
        else (f"ANALYSIS_STATUS:{value.rotation.eligibility.value}",)
    )
    return SectorResponse(
        sector_id=value.sector_id,
        sector_name=value.sector_name,
        phase=record.result,
        rank=value.rank,
        relative_strength=_decimal_or_none(details.get("excess")),
        score=record.score,
        confidence=record.confidence,
        calculated_at=record.evaluated_at,
        data_as_of=record.as_of_timestamp,
        status=value.rotation.eligibility.value,
        evidence_ids=record.evidence_ids,
        input_observation_ids=record.input_observation_ids,
        warnings=warnings,
    )


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except (InvalidOperation, ValueError):
        return None
