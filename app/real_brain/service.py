"""Controlled full-Brain trial over canonical stores, with no provider I/O."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from time import perf_counter
from typing import Callable, Protocol
from uuid import uuid4

from app.data_coverage.models import DataCoverageDomain, DataCoverageRecord, DataCoverageStatus, StrategyCoverageReadiness
from app.diagnostics.models import EvaluationEligibility
from app.historical.security_master import HistoricalPriceIntegrity
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import build_scorecard
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler

from .models import RealBrainBlocker, RealBrainCoverageDelta, RealBrainStockResult, RealBrainTrial, RealBrainTrialComparison, RealBrainTrialStatus


class RealBrainTrialError(ValueError):
    pass


class CanonicalStoredEvidenceSource(Protocol):
    """Marker makes a synthetic/provider source ineligible for a real trial."""
    canonical_stored_only: bool

    def observations_as_of(self, at: datetime): ...


@dataclass(frozen=True, slots=True)
class TrialSelection:
    instruments: tuple[NseEquityInstrument, ...]
    method: str


class DeterministicRealSampleSelector:
    """Balanced by known taxonomy; otherwise a stable snapshot-scoped hash."""

    def select(self, *, snapshot: UniverseSnapshot, instruments: tuple[NseEquityInstrument, ...],
               sample_size: int, sectors: dict[str, str] | None = None) -> TrialSelection:
        if not 30 <= sample_size <= 50:
            raise RealBrainTrialError("Real Brain trial sample_size must be between 30 and 50.")
        available = tuple(item for item in instruments if item.instrument_id in set(snapshot.instrument_ids))
        if len(available) < sample_size:
            raise RealBrainTrialError("Universe snapshot has fewer instruments than the requested bounded sample.")
        sectors = sectors or {}
        grouped: dict[str, list[NseEquityInstrument]] = {}
        for item in available:
            sector = sectors.get(item.instrument_id)
            if sector:
                grouped.setdefault(sector, []).append(item)
        if len(grouped) > 1:
            buckets = [sorted(values, key=lambda item: self._key(snapshot, item)) for _, values in sorted(grouped.items())]
            selected: list[NseEquityInstrument] = []
            while buckets and len(selected) < sample_size:
                next_buckets = []
                for bucket in buckets:
                    if bucket and len(selected) < sample_size:
                        selected.append(bucket.pop(0))
                    if bucket:
                        next_buckets.append(bucket)
                buckets = next_buckets
            if len(selected) < sample_size:
                used = {item.instrument_id for item in selected}
                selected.extend(item for item in sorted(available, key=lambda item: self._key(snapshot, item)) if item.instrument_id not in used)
            return TrialSelection(tuple(selected[:sample_size]), "KNOWN_TAXONOMY_ROUND_ROBIN_THEN_SNAPSHOT_HASH")
        return TrialSelection(tuple(sorted(available, key=lambda item: self._key(snapshot, item))[:sample_size]), "SNAPSHOT_SCOPED_STABLE_HASH_NO_TAXONOMY_INFERENCE")

    @staticmethod
    def _key(snapshot: UniverseSnapshot, item: NseEquityInstrument) -> tuple[str, str]:
        return sha256(f"{snapshot.snapshot_id}|{snapshot.checksum}|{item.instrument_id}".encode()).hexdigest(), item.instrument_id


class RealBrainTrialStore:
    """Append-only internal audit persistence; no public diagnostic trace."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_result(self, value: RealBrainStockResult) -> None:
        self._save(CoreApiSnapshotFamily.REAL_BRAIN_STOCK_RESULT, "real-brain-result:" + value.result_id, value, value.as_of)

    def save_trial(self, value: RealBrainTrial) -> None:
        self._save(CoreApiSnapshotFamily.REAL_BRAIN_TRIAL, "real-brain-trial:" + value.trial_id, value, value.created_at)

    def get_trial(self, trial_id: str) -> RealBrainTrial | None:
        item = self._repository.get_snapshot("real-brain-trial:" + trial_id)
        return item.payload if item is not None and isinstance(item.payload, RealBrainTrial) else None

    def latest_trial(self, *, sample_size: int | None = None) -> RealBrainTrial | None:
        values: list[RealBrainTrial] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.REAL_BRAIN_TRIAL, limit=100, offset=offset)
            values.extend(item.payload for item in page if isinstance(item.payload, RealBrainTrial) and (sample_size is None or item.payload.requested_sample_size == sample_size))
            if len(page) < 100:
                return max(values, key=lambda item: (item.created_at, item.trial_id)) if values else None
            offset += len(page)

    def results(self, trial_id: str) -> tuple[RealBrainStockResult, ...]:
        values: list[RealBrainStockResult] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.REAL_BRAIN_STOCK_RESULT, limit=100, offset=offset)
            values.extend(item.payload for item in page if isinstance(item.payload, RealBrainStockResult) and item.payload.trial_id == trial_id)
            if len(page) < 100:
                return tuple(sorted(values, key=lambda item: (item.symbol, item.instrument_id)))
            offset += len(page)

    def compare(self, *, before_trial_id: str, after_trial_id: str) -> RealBrainTrialComparison:
        before = self.get_trial(before_trial_id); after = self.get_trial(after_trial_id)
        if before is None or after is None:
            raise RealBrainTrialError("REAL_BRAIN_TRIAL_NOT_FOUND")
        if before.selected_instrument_ids != after.selected_instrument_ids:
            raise RealBrainTrialError("REAL_BRAIN_TRIAL_COHORT_MISMATCH")
        before_rows, after_rows = self.results(before_trial_id), self.results(after_trial_id)
        if len(before_rows) != len(before.selected_instrument_ids) or len(after_rows) != len(after.selected_instrument_ids):
            raise RealBrainTrialError("REAL_BRAIN_TRIAL_RESULTS_INCOMPLETE")
        coverage = []
        for domain in DataCoverageDomain:
            coverage.append(RealBrainCoverageDelta(
                domain.value,
                sum(next(item for item in row.coverage.domains if item.domain is domain).status is DataCoverageStatus.READY for row in before_rows),
                sum(next(item for item in row.coverage.domains if item.domain is domain).status is DataCoverageStatus.READY for row in after_rows),
            ))
        return RealBrainTrialComparison(
            before_trial_id, after_trial_id, len(before.selected_instrument_ids), tuple(coverage),
            before.complete_count, after.complete_count, before.partial_count, after.partial_count, before.unavailable_count, after.unavailable_count,
            before.diagnostic_evaluated_total, after.diagnostic_evaluated_total, before.diagnostic_missing_total, after.diagnostic_missing_total,
        )

    def _save(self, family: CoreApiSnapshotFamily, identifier: str, payload: object, created_at: datetime) -> None:
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", "real-brain-trial-v1", sha256(repr(payload).encode()).hexdigest(), created_at, payload))


class RealBrainTrialService:
    """Executes exactly the selected stored evidence set and never fetches data."""

    def __init__(self, *, selector: DeterministicRealSampleSelector, assembler: StockDiagnosticInputAssembler,
                 runner: Canonical61DiagnosticRunner, store: RealBrainTrialStore,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._selector, self._assembler, self._runner, self._store, self._clock = selector, assembler, runner, store, clock

    def run(self, *, snapshot: UniverseSnapshot, instruments: tuple[NseEquityInstrument, ...],
            coverage_by_instrument: dict[str, DataCoverageRecord], source: CanonicalStoredEvidenceSource,
            sample_size: int = 40, sectors: dict[str, str] | None = None,
            integrity_by_instrument: dict[str, HistoricalPriceIntegrity] | None = None,
            frozen_cohort_instrument_ids: tuple[str, ...] | None = None,
            frozen_cohort_reference: str | None = None) -> RealBrainTrial:
        if not getattr(source, "canonical_stored_only", False):
            raise RealBrainTrialError("REAL_BRAIN_TRIAL_REQUIRES_CANONICAL_STORED_EVIDENCE")
        selection = self._selector.select(snapshot=snapshot, instruments=instruments, sample_size=sample_size, sectors=sectors)
        if frozen_cohort_instrument_ids is not None:
            if len(frozen_cohort_instrument_ids) != sample_size or len(set(frozen_cohort_instrument_ids)) != sample_size:
                raise RealBrainTrialError("Frozen cohort must contain exactly the requested number of unique instruments.")
            by_id = {item.instrument_id: item for item in instruments}
            if any(item not in set(snapshot.instrument_ids) or item not in by_id for item in frozen_cohort_instrument_ids):
                raise RealBrainTrialError("Frozen cohort is not fully present in the supplied immutable universe snapshot.")
            selection = TrialSelection(tuple(by_id[item] for item in frozen_cohort_instrument_ids), "FROZEN_COHORT_FROM_PRIOR_REAL_BRAIN_TRIAL")
        # Selection is deterministic; each explicit operator-run is separately
        # auditable and can never overwrite an earlier frozen evidence report.
        trial_id = "real-brain:" + uuid4().hex
        started = perf_counter(); results: list[RealBrainStockResult] = []
        integrity_by_instrument = integrity_by_instrument or {}
        for instrument in selection.instruments:
            coverage = coverage_by_instrument.get(instrument.instrument_id)
            if coverage is None:
                raise RealBrainTrialError("Coverage must be composed from canonical stored evidence before trial execution.")
            item_started = perf_counter()
            evidence = self._assembler.assemble(instrument, snapshot.as_of)
            run = self._runner.run(evidence)  # Always reaches the complete canonical registry, even when all inputs are missing.
            scorecard = build_scorecard(instrument_id=instrument.instrument_id, strategy_version=self._runner._strategy,
                                       registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=snapshot.as_of,
                                       evaluated_at=snapshot.as_of, diagnostics=run.evaluations)
            result = self._result(trial_id, instrument, snapshot.as_of, coverage, run, scorecard, integrity_by_instrument.get(instrument.instrument_id), evidence.snapshot.observations, item_started)
            self._store.save_result(result); results.append(result)
        trial = self._trial(trial_id, snapshot, selection, tuple(results), int((perf_counter() - started) * 1000), frozen_cohort_reference, self._clock())
        self._store.save_trial(trial)
        return trial

    @staticmethod
    def _result(trial_id, instrument, as_of, coverage, run, scorecard, integrity, observations, started) -> RealBrainStockResult:
        statuses = {item.domain: item.status for item in coverage.domains}
        meaningful = tuple(statuses[domain] for domain in DataCoverageDomain if domain is not DataCoverageDomain.IDENTITY)
        # Higher-order wrappers can be mechanically eligible while every raw
        # evidence domain is absent.  That must not turn an unavailable real
        # analysis into a partial one merely because the registry was walked.
        status = RealBrainTrialStatus.COMPLETE if run.completeness.value == "COMPLETE" and all(value is DataCoverageStatus.READY for value in meaningful) else RealBrainTrialStatus.PARTIAL if any(value in {DataCoverageStatus.READY, DataCoverageStatus.PARTIAL, DataCoverageStatus.STALE} for value in meaningful) else RealBrainTrialStatus.UNAVAILABLE
        score = scorecard.final_score
        confidence = scorecard.data_confidence if score is not None else None
        blockers = tuple(sorted({_blocker(item.domain) for item in coverage.domains if item.status is not DataCoverageStatus.READY}))
        warnings = tuple(sorted(set((*coverage.warnings, *run.warnings, *(integrity.warnings if integrity else ()), "DECISION_SCORE_UNAVAILABLE" if score is None else "", "SIX_GATES_NOT_EXECUTABLE_WITH_INCOMPLETE_EVIDENCE" if status is not RealBrainTrialStatus.COMPLETE else "")) - {""}))
        evidence_ids = tuple(sorted({identifier for item in coverage.domains for identifier in item.evidence_ids} | {item.id for item in observations if item.instrument.id == instrument.instrument_id}))
        value = RealBrainStockResult(
            "real-brain-result:" + sha256(f"{trial_id}|{instrument.instrument_id}|{coverage.coverage_id}".encode()).hexdigest()[:20], trial_id, instrument.instrument_id, instrument.symbol, as_of,
            status, coverage, len(run.evaluations), run.evaluated, run.missing, score, confidence,
            _ready(statuses, DataCoverageDomain.HISTORICAL_OHLCV) and _ready(statuses, DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY),
            _ready(statuses, DataCoverageDomain.FUNDAMENTALS), _ready(statuses, DataCoverageDomain.OWNERSHIP), _ready(statuses, DataCoverageDomain.DELIVERY_DATA),
            _ready(statuses, DataCoverageDomain.NEWS) or _ready(statuses, DataCoverageDomain.CATALYSTS), _ready(statuses, DataCoverageDomain.MARKET_CONTEXT),
            _ready(statuses, DataCoverageDomain.SECTOR_CONTEXT), _ready(statuses, DataCoverageDomain.MACRO_CONTEXT),
            "UNAVAILABLE" if status is not RealBrainTrialStatus.COMPLETE else "NOT_EVALUATED", coverage.pre_breakout, coverage.inflection,
            integrity.status.value if integrity else None, evidence_ids, blockers, warnings, int((perf_counter() - started) * 1000),
        )
        if value.status is RealBrainTrialStatus.UNAVAILABLE and value.confidence is not None:
            raise RealBrainTrialError("Insufficient real evidence cannot produce a confidence value.")
        return value

    @staticmethod
    def _trial(trial_id, snapshot, selection, results, elapsed, frozen_cohort_reference, created_at) -> RealBrainTrial:
        counts = Counter(item.status for item in results); blockers = Counter(code for item in results for code in item.blockers)
        pre = Counter(item.pre_breakout for item in results); inflection = Counter(item.inflection for item in results)
        audit = "real-brain-audit:" + sha256(repr((trial_id, snapshot.snapshot_id, tuple(item.result_id for item in results))).encode()).hexdigest()[:20]
        return RealBrainTrial(
            trial_id, "real-brain-trial-v1", snapshot.snapshot_id, snapshot.checksum, snapshot.as_of, created_at, len(results),
            tuple(item.instrument_id for item in selection.instruments), tuple(item.symbol for item in selection.instruments), selection.method,
            "CANONICAL_STORED_EVIDENCE_ONLY", 0, counts[RealBrainTrialStatus.COMPLETE], counts[RealBrainTrialStatus.PARTIAL], counts[RealBrainTrialStatus.UNAVAILABLE],
            61, sum(item.diagnostic_evaluated for item in results), sum(item.diagnostic_missing for item in results), sum(item.decision_score is not None for item in results), sum(item.confidence is not None for item in results),
            sum(item.technical_ready for item in results), sum(item.fundamental_ready for item in results), sum(item.ownership_ready for item in results), sum(item.delivery_ready for item in results),
            sum(item.news_catalyst_ready for item in results), sum(item.macro_context_ready for item in results), sum(item.sector_context_ready for item in results),
            sum(item.execution_eligibility == "EXECUTABLE" for item in results), pre[StrategyCoverageReadiness.READY], pre[StrategyCoverageReadiness.PARTIAL], pre[StrategyCoverageReadiness.UNAVAILABLE],
            inflection[StrategyCoverageReadiness.READY], inflection[StrategyCoverageReadiness.PARTIAL], inflection[StrategyCoverageReadiness.UNAVAILABLE],
            tuple(RealBrainBlocker(code, number) for code, number in sorted(blockers.items(), key=lambda item: (-item[1], item[0]))), tuple(item.result_id for item in results), audit, elapsed,
            ("STORED_DATA_ONLY", "NO_ALPHA_CLAIMS", "NO_PROVIDER_FANOUT", "DECISION_SCORE_CONFIDENCE_AND_GATES_REMAIN_SEPARATE"),
            "PORTFOLIO_NOT_PRESENT", DIAGNOSTIC_REGISTRY_VERSION, "canonical-61-runner-v1", "decision-score-v1",
            frozen_cohort_reference,
        )


def _ready(statuses: dict[DataCoverageDomain, DataCoverageStatus], domain: DataCoverageDomain) -> bool:
    return statuses.get(domain) is DataCoverageStatus.READY


def _blocker(domain: DataCoverageDomain) -> str:
    return {
        DataCoverageDomain.HISTORICAL_OHLCV: "NO_HISTORY", DataCoverageDomain.SECTOR_INDUSTRY: "NO_TAXONOMY",
        DataCoverageDomain.FUNDAMENTALS: "NO_FUNDAMENTALS", DataCoverageDomain.OWNERSHIP: "NO_OWNERSHIP",
        DataCoverageDomain.DELIVERY_DATA: "NO_DELIVERY", DataCoverageDomain.MARKET_CONTEXT: "NO_MARKET_CONTEXT",
        DataCoverageDomain.SECTOR_CONTEXT: "NO_SECTOR_CONTEXT", DataCoverageDomain.MACRO_CONTEXT: "NO_MACRO_CONTEXT",
        DataCoverageDomain.CORPORATE_ACTIONS: "NO_CORPORATE_ACTION_INTEGRITY", DataCoverageDomain.PRICE_ADJUSTMENT_INTEGRITY: "NO_CORPORATE_ACTION_INTEGRITY",
        DataCoverageDomain.NEWS: "NO_NEWS", DataCoverageDomain.CATALYSTS: "NO_CATALYSTS",
    }.get(domain, "NO_" + domain.value)
