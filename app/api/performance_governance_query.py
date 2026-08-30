"""Read facades over frozen performance, benchmark, OOS, and governance records.

No metric, benchmark, eligibility, approval, activation, or rollback logic is
implemented here; callers provide already-existing immutable records.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.api.errors import APIRequestError
from app.api.schemas.performance_governance import (
    ActiveStrategyResponse, BenchmarkResponse, PerformanceResponse,
    PromotionSummaryResponse, StrategyVersionResponse,
)
from app.backtest.promotion import (
    ApprovedStrategyVersion, PromotionEligibilityResult, StrategyActivation,
    StrategyPromotionProposal, StrategyPromotionReview, StrategyRollback,
)
from app.performance.models import BenchmarkComparison, PerformanceReport


def _version(value: object) -> str:
    strategy_id, version = getattr(value, "strategy_id", None), getattr(value, "version", None)
    return f"{strategy_id}/{version}" if strategy_id is not None and version is not None else str(value)


@dataclass(frozen=True, slots=True)
class PerformanceQueryRecord:
    report: PerformanceReport
    source_run_id: str | None = None
    mode: str | None = None


@dataclass(frozen=True, slots=True)
class BenchmarkQueryRecord:
    comparison_id: str
    comparison: BenchmarkComparison
    report_id: str | None = None
    mode: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    alignment_status: str | None = None
    provenance_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PromotionQueryRecord:
    proposal: StrategyPromotionProposal
    eligibility: PromotionEligibilityResult | None = None
    review: StrategyPromotionReview | None = None
    approved_version: ApprovedStrategyVersion | None = None
    activation: StrategyActivation | None = None
    rollback: StrategyRollback | None = None


class PerformanceQueryService(Protocol):
    def list_performance(self, *, strategy_version: str | None, source_run_id: str | None, mode: str | None) -> tuple[PerformanceQueryRecord, ...]: ...
    def get_performance(self, report_id: str) -> PerformanceQueryRecord: ...


class BenchmarkQueryService(Protocol):
    def list_benchmarks(self, *, benchmark_id: str | None, report_id: str | None, mode: str | None) -> tuple[BenchmarkQueryRecord, ...]: ...
    def get_benchmark(self, benchmark_id: str) -> BenchmarkQueryRecord: ...


class GovernanceQueryService(Protocol):
    def list_strategy_versions(self) -> tuple[ApprovedStrategyVersion, ...]: ...
    def get_active_strategy(self) -> tuple[StrategyActivation, ApprovedStrategyVersion] | None: ...
    def list_promotions(self) -> tuple[PromotionQueryRecord, ...]: ...
    def get_promotion(self, proposal_id: str) -> PromotionQueryRecord: ...


class _Unavailable:
    code = ""
    message = ""
    def _raise(self):
        raise APIRequestError(status_code=503, code=self.code, message=self.message)


class UnavailablePerformanceQueryService(_Unavailable):
    code, message = "PERFORMANCE_UNAVAILABLE", "Performance is not available."
    def list_performance(self, **_: object): return self._raise()
    def get_performance(self, report_id: str): return self._raise()


class UnavailableBenchmarkQueryService(_Unavailable):
    code, message = "BENCHMARKS_UNAVAILABLE", "Benchmarks are not available."
    def list_benchmarks(self, **_: object): return self._raise()
    def get_benchmark(self, benchmark_id: str): return self._raise()


class UnavailableGovernanceQueryService(_Unavailable):
    code, message = "GOVERNANCE_UNAVAILABLE", "Strategy governance is not available."
    def list_strategy_versions(self): return self._raise()
    def get_active_strategy(self): return self._raise()
    def list_promotions(self): return self._raise()
    def get_promotion(self, proposal_id: str): return self._raise()


class SnapshotPerformanceQueryService:
    def __init__(self, records: tuple[PerformanceQueryRecord, ...]) -> None: self._records = records
    def list_performance(self, *, strategy_version: str | None, source_run_id: str | None, mode: str | None) -> tuple[PerformanceQueryRecord, ...]:
        return tuple(item for item in self._records if (strategy_version is None or _version(item.report.strategy_version) == strategy_version) and (source_run_id is None or item.source_run_id == source_run_id) and (mode is None or item.mode == mode))
    def get_performance(self, report_id: str) -> PerformanceQueryRecord:
        for item in self._records:
            if item.report.report_id == report_id:
                return item
        _missing("PERFORMANCE_NOT_FOUND", "Performance report was not found.")


class SnapshotBenchmarkQueryService:
    def __init__(self, records: tuple[BenchmarkQueryRecord, ...]) -> None: self._records = records
    def list_benchmarks(self, *, benchmark_id: str | None, report_id: str | None, mode: str | None) -> tuple[BenchmarkQueryRecord, ...]:
        return tuple(item for item in self._records if (benchmark_id is None or item.comparison.benchmark_id == benchmark_id) and (report_id is None or item.report_id == report_id) and (mode is None or item.mode == mode))
    def get_benchmark(self, benchmark_id: str) -> BenchmarkQueryRecord:
        for item in self._records:
            if item.comparison_id == benchmark_id:
                return item
        _missing("BENCHMARK_NOT_FOUND", "Benchmark comparison was not found.")


class SnapshotGovernanceQueryService:
    def __init__(self, versions: tuple[ApprovedStrategyVersion, ...] = (), promotions: tuple[PromotionQueryRecord, ...] = (), active: tuple[StrategyActivation, ApprovedStrategyVersion] | None = None) -> None:
        self._versions, self._promotions, self._active = versions, promotions, active
    def list_strategy_versions(self) -> tuple[ApprovedStrategyVersion, ...]: return self._versions
    def get_active_strategy(self) -> tuple[StrategyActivation, ApprovedStrategyVersion] | None: return self._active
    def list_promotions(self) -> tuple[PromotionQueryRecord, ...]: return self._promotions
    def get_promotion(self, proposal_id: str) -> PromotionQueryRecord:
        for item in self._promotions:
            if item.proposal.proposal_id == proposal_id:
                return item
        _missing("PROMOTION_NOT_FOUND", "Promotion proposal was not found.")


def _missing(code: str, message: str):
    raise APIRequestError(status_code=404, code=code, message=message)


def performance_response(item: PerformanceQueryRecord) -> PerformanceResponse:
    m = item.report.metrics
    return PerformanceResponse(report_id=item.report.report_id, strategy_version=_version(item.report.strategy_version), source_run_id=item.source_run_id, mode=item.mode, start=item.report.start, end=item.report.end, generated_at=item.report.generated_at, total_trades=m.get("total_trades"), closed_trades=m.get("closed_trades"), win_rate=m.get("win_rate"), expectancy=m.get("expectancy"), average_r=m.get("average_r"), profit_factor=m.get("profit_factor"), total_return=m.get("total_return"), cagr=m.get("cagr"), max_drawdown=m.get("max_drawdown"), volatility=m.get("volatility"), sharpe=m.get("sharpe"), sortino=m.get("sortino"), turnover=m.get("turnover"), costs=m.get("costs"), capital_efficiency=m.get("capital_efficiency"), sample_status=m.get("sample_status"), warnings=item.report.warnings)


def benchmark_response(item: BenchmarkQueryRecord) -> BenchmarkResponse:
    c = item.comparison
    return BenchmarkResponse(comparison_id=item.comparison_id, benchmark_id=c.benchmark_id, benchmark_version=c.benchmark_version, report_id=item.report_id, mode=item.mode, start=item.start, end=item.end, strategy_return=c.strategy_return, benchmark_return=c.benchmark_return, excess_return=c.excess_return, strategy_cagr=c.strategy_cagr, benchmark_cagr=c.benchmark_cagr, strategy_drawdown=c.strategy_drawdown, benchmark_drawdown=c.benchmark_drawdown, strategy_sharpe=c.strategy_sharpe, benchmark_sharpe=c.benchmark_sharpe, strategy_sortino=c.strategy_sortino, benchmark_sortino=c.benchmark_sortino, strategy_volatility=c.strategy_volatility, benchmark_volatility=c.benchmark_volatility, strategy_costs=c.strategy_costs, benchmark_costs=c.benchmark_costs, classification=c.classification, alignment_status=item.alignment_status, warnings=(*c.fairness_warnings, *c.sample_warnings))


def strategy_version_response(value: ApprovedStrategyVersion) -> StrategyVersionResponse:
    return StrategyVersionResponse(approved_id=value.approved_id, strategy_id=value.strategy_id, version=value.version, parent_approved_id=value.parent_approved_id, proposal_id=value.proposal_id, review_id=value.review_id, candidate_id=value.candidate_id, config_fingerprints=value.config_fingerprints, approved_at=value.approved_at, effective_from=value.effective_from, status=value.status.value, methodology_notes=value.methodology_notes, fingerprint=value.fingerprint)


def active_strategy_response(value: tuple[StrategyActivation, ApprovedStrategyVersion] | None) -> ActiveStrategyResponse:
    if value is None: return ActiveStrategyResponse(active=False, activation_id=None, active_version=None, previous_approved_id=None, effective_at=None, reason=None, fingerprint=None)
    activation, version = value
    return ActiveStrategyResponse(active=True, activation_id=activation.activation_id, active_version=strategy_version_response(version), previous_approved_id=activation.previous_approved_id, effective_at=activation.effective_at, reason=activation.reason, fingerprint=activation.fingerprint)


def promotion_response(value: PromotionQueryRecord) -> PromotionSummaryResponse:
    p, e, r, approved, activation, rollback = value.proposal, value.eligibility, value.review, value.approved_version, value.activation, value.rollback
    return PromotionSummaryResponse(proposal_id=p.proposal_id, candidate_id=p.candidate_id, baseline_strategy_id=p.baseline_strategy_id, baseline_version=p.baseline_version, status=p.status.value, eligibility_status=e.status.value if e else None, eligibility_reasons=e.reasons if e else (), review_decision=r.decision.value if r else None, reviewed_at=r.reviewed_at if r else None, approved_version_id=approved.approved_id if approved else None, activation_id=activation.activation_id if activation else None, rollback_id=rollback.rollback_id if rollback else None, created_at=p.created_at, warnings=(*p.warnings, *(e.warnings if e else ())), provenance_ids=(p.selection_id, *p.walk_forward_run_ids, *p.aggregate_result_ids, *p.benchmark_comparison_ids, *p.robustness_result_ids, *((e.eligibility_id,) if e else ()), *((r.review_id,) if r else ())))
