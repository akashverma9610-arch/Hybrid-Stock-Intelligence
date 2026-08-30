from __future__ import annotations

from app.analysis.models import IndicatorResult, MarketRegimeResult, RelativeStrengthResult, TrendResult
from app.storage.governance_repository import StrategyGovernanceRepository
from app.domain.models import DiagnosticResult


class AnalysisAuditService:
    """Persists generated evidence and one immutable diagnostic record per analysis result."""

    def __init__(self, repository: StrategyGovernanceRepository) -> None:
        self._repository = repository

    def persist(self, result: IndicatorResult | TrendResult | MarketRegimeResult | RelativeStrengthResult) -> DiagnosticResult:
        for evidence in result.evidence:
            self._repository.save_evidence(evidence)
        diagnostic = DiagnosticResult(
            id=f"diagnostic-{result.id}", instrument_id=getattr(result, "instrument_id", getattr(result, "benchmark_instrument_id", "market")),
            rule_id=result.calculation_version, strategy_version=result.strategy_version,
            result=_result_value(result), score=None, confidence=result.confidence,
            evidence_ids=result.evidence_ids, input_observation_ids=result.input_observation_ids,
            evaluated_at=result.evaluated_at, as_of_timestamp=result.as_of_timestamp,
        )
        self._repository.save_diagnostic_result(diagnostic)
        return diagnostic


def _result_value(result: IndicatorResult | TrendResult | MarketRegimeResult | RelativeStrengthResult) -> str:
    if hasattr(result, "classification"):
        return result.classification.value
    return f"{result.calculation_name}:{result.value}"
