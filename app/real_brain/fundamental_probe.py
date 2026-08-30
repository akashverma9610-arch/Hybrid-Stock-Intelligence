"""Bounded, stored-data-only audit probe for newly available official facts.

This is deliberately not a new Brain, scanner, score, or strategy path.  It
reuses the canonical input assembler, diagnostic runner, scorecard, and
coverage composer to measure what immutable financial evidence makes visible
for an explicitly named small cohort.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Callable
from uuid import uuid4

from app.data_coverage.local import compose_coverage_records
from app.data_coverage.models import DataCoverageDomain, DataCoverageRecord
from app.diagnostics.models import EvaluationEligibility
from app.filings.store import CorporateFilingsStore
from app.fundamentals.adapter import FundamentalEngineInput, FundamentalsEngineAdapter
from app.fundamentals.bse_official import BSE_OFFICIAL_PROVIDER
from app.fundamentals.store import FinancialFactStore
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.scoring.engine import build_scorecard
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler, build_universe_snapshot

from .local import StoredTrialObservationSource


class FundamentalBrainProbeError(ValueError):
    """The proposed probe would not be a bounded PIT-safe evidence comparison."""


@dataclass(frozen=True, slots=True)
class FundamentalProbeCoverage:
    """Coverage projection only; it is not a score or recommendation."""

    filings: str
    fundamentals: str
    earnings: str
    balance_sheet: str
    cash_flow: str
    technical: str
    deep_analysis: str


@dataclass(frozen=True, slots=True)
class FundamentalBrainProbeStockResult:
    instrument_id: str
    symbol: str
    first_observed_at: datetime
    filing_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    before_diagnostic_evaluated: int
    before_diagnostic_missing: int
    after_diagnostic_evaluated: int
    after_diagnostic_missing: int
    newly_evaluable_diagnostics: tuple[str, ...]
    before_coverage: FundamentalProbeCoverage
    after_coverage: FundamentalProbeCoverage
    before_decision_score_status: str
    after_decision_score_status: str
    before_confidence_status: str
    after_confidence_status: str
    consolidated_selected_after: bool
    unsupported_metrics_missing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FundamentalBrainProbe:
    """Append-only, internal evidence-value audit for exactly one cohort."""

    probe_id: str
    source_universe_snapshot_id: str
    current_universe_snapshot_id: str
    universe_checksum: str
    before_as_of: datetime
    as_of: datetime
    cohort_instrument_ids: tuple[str, ...]
    cohort_symbols: tuple[str, ...]
    filing_ids: tuple[str, ...]
    fact_ids: tuple[str, ...]
    provider_calls: int
    diagnostic_registry_version: str
    analysis_engine_version: str
    decision_score_configuration_version: str
    results: tuple[FundamentalBrainProbeStockResult, ...]
    warnings: tuple[str, ...]
    created_at: datetime


class FundamentalBrainProbeStore:
    """Insert-only persistence for internal probe/audit results."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: FundamentalBrainProbe) -> None:
        identifier = "fundamental-brain-probe:" + value.probe_id
        self._repository.save_snapshot(CoreApiSnapshot(
            identifier, CoreApiSnapshotFamily.FUNDAMENTAL_BRAIN_PROBE, "v1",
            "fundamental-brain-probe-v1", sha256(repr(value).encode()).hexdigest(),
            value.created_at, value,
        ))

    def get(self, probe_id: str) -> FundamentalBrainProbe | None:
        item = self._repository.get_snapshot("fundamental-brain-probe:" + probe_id)
        return item.payload if item is not None and isinstance(item.payload, FundamentalBrainProbe) else None


class FundamentalBrainProbeService:
    """Run a strict old-vs-current-as-of financial-evidence comparison.

    The service opens no provider.  It only calls the existing stored-data
    composition boundaries supplied to it by the caller.
    """

    def __init__(self, *, repository: CoreApiSnapshotRepository, historical, facts: FinancialFactStore,
                 filings: CorporateFilingsStore, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._repository = repository
        self._historical = historical
        self._facts = facts
        self._filings = filings
        self._clock = clock

    def run(self, *, source_snapshot: UniverseSnapshot, as_of: datetime,
            cohort_instrument_ids: tuple[str, ...]) -> FundamentalBrainProbe:
        if as_of.tzinfo is None:
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_AS_OF_MUST_BE_TIMEZONE_AWARE")
        if len(cohort_instrument_ids) != 3 or len(set(cohort_instrument_ids)) != 3:
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_REQUIRES_EXACTLY_THREE_UNIQUE_INSTRUMENTS")
        if as_of <= source_snapshot.as_of:
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_REQUIRES_A_NEWER_CURRENT_AS_OF")

        universe = CoreUniverseAnalysisStore(self._repository)
        source_by_id = {item.instrument_id: item for item in universe.instruments_as_of(source_snapshot.as_of)}
        if set(source_snapshot.instrument_ids) - set(source_by_id):
            raise FundamentalBrainProbeError("SOURCE_UNIVERSE_CONTENT_CANNOT_BE_REHYDRATED")
        original_content = tuple(source_by_id[item_id] for item_id in source_snapshot.instrument_ids)
        current_snapshot = build_universe_snapshot(
            snapshot_id="nse-universe:fundamental-probe:" + uuid4().hex,
            as_of=as_of, source=source_snapshot.source, instruments=original_content,
            version=source_snapshot.version,
        )
        if current_snapshot.checksum != source_snapshot.checksum or current_snapshot.instrument_ids != source_snapshot.instrument_ids:
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_MUST_RETAIN_IDENTICAL_UNIVERSE_CONTENT")
        universe.save_universe_snapshot(current_snapshot)

        by_id = {item.instrument_id: item for item in original_content}
        if any(item_id not in by_id for item_id in cohort_instrument_ids):
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_COHORT_NOT_IN_FROZEN_UNIVERSE")
        cohort = tuple(by_id[item_id] for item_id in cohort_instrument_ids)
        bse_facts = {
            item.instrument_id: tuple(fact for fact in self._facts.facts(item.instrument_id, as_of=as_of, limit=500)
                                      if fact.source == BSE_OFFICIAL_PROVIDER)
            for item in cohort
        }
        if any(not values for values in bse_facts.values()):
            raise FundamentalBrainProbeError("FUNDAMENTAL_PROBE_REQUIRES_BSE_FACTS_FOR_EACH_COHORT_MEMBER")
        first_observed = {item_id: min(fact.available_at for fact in values) for item_id, values in bse_facts.items()}
        if source_snapshot.as_of >= min(first_observed.values()):
            raise FundamentalBrainProbeError("SOURCE_SNAPSHOT_MUST_PRECEDE_BSE_FIRST_OBSERVED_AVAILABILITY")
        if as_of < max(first_observed.values()):
            raise FundamentalBrainProbeError("CURRENT_SNAPSHOT_MUST_FOLLOW_ALL_BSE_FIRST_OBSERVED_TIMESTAMPS")

        adapter = FundamentalsEngineAdapter(self._facts, self._filings)
        before_coverages = self._coverage(source_snapshot, cohort)
        after_coverages = self._coverage(current_snapshot, cohort)
        before_source = StoredTrialObservationSource(
            historical=self._historical, instrument_ids=cohort_instrument_ids,
            as_of=source_snapshot.as_of, fundamentals=adapter,
        )
        after_source = StoredTrialObservationSource(
            historical=self._historical, instrument_ids=cohort_instrument_ids,
            as_of=current_snapshot.as_of, fundamentals=adapter,
        )
        before_assembler = StockDiagnosticInputAssembler(before_source)
        after_assembler = StockDiagnosticInputAssembler(after_source)
        before_runner = Canonical61DiagnosticRunner(benchmark_instrument_id="NIFTY_500")
        after_runner = Canonical61DiagnosticRunner(benchmark_instrument_id="NIFTY_500")
        results = tuple(
            self._stock_result(
                instrument=item, before_as_of=source_snapshot.as_of, after_as_of=current_snapshot.as_of,
                before_coverage=before_coverages[item.instrument_id], after_coverage=after_coverages[item.instrument_id],
                first_observed_at=first_observed[item.instrument_id], bse_facts=bse_facts[item.instrument_id],
                adapter=adapter, before_assembler=before_assembler, after_assembler=after_assembler,
                before_runner=before_runner, after_runner=after_runner,
            )
            for item in cohort
        )
        probe = FundamentalBrainProbe(
            probe_id="fundamental-brain-probe:" + uuid4().hex,
            source_universe_snapshot_id=source_snapshot.snapshot_id,
            current_universe_snapshot_id=current_snapshot.snapshot_id,
            universe_checksum=current_snapshot.checksum,
            before_as_of=source_snapshot.as_of,
            as_of=current_snapshot.as_of,
            cohort_instrument_ids=cohort_instrument_ids,
            cohort_symbols=tuple(item.symbol for item in cohort),
            filing_ids=tuple(sorted({fact.filing_id for values in bse_facts.values() for fact in values if fact.filing_id})),
            fact_ids=tuple(sorted(fact.fact_id for values in bse_facts.values() for fact in values)),
            provider_calls=0,
            diagnostic_registry_version=DIAGNOSTIC_REGISTRY_VERSION,
            analysis_engine_version="canonical-61-runner-v1",
            decision_score_configuration_version="decision-score-v1",
            results=results,
            warnings=(
                "STORED_DATA_ONLY", "NO_PROVIDER_CALLS", "NO_RECOMMENDATION", "NO_SCORE_OR_GATE_CONFIGURATION_CHANGE",
                "SOURCE_PUBLICATION_TIMESTAMP_UNKNOWN", "PIT_AVAILABLE_FROM_SYSTEM_FIRST_OBSERVED",
            ),
            created_at=self._clock(),
        )
        FundamentalBrainProbeStore(self._repository).save(probe)
        return probe

    def _coverage(self, snapshot: UniverseSnapshot, cohort: tuple[NseEquityInstrument, ...]) -> dict[str, DataCoverageRecord]:
        records = compose_coverage_records(
            repository=self._repository, historical=self._historical, snapshot=snapshot,
            instruments=cohort, persist=False, facts=self._facts, filings=self._filings,
        )
        return {item.instrument_id: item for item in records}

    def _stock_result(self, *, instrument: NseEquityInstrument, before_as_of: datetime, after_as_of: datetime,
                      before_coverage: DataCoverageRecord, after_coverage: DataCoverageRecord,
                      first_observed_at: datetime, bse_facts, adapter: FundamentalsEngineAdapter,
                      before_assembler: StockDiagnosticInputAssembler, after_assembler: StockDiagnosticInputAssembler,
                      before_runner: Canonical61DiagnosticRunner, after_runner: Canonical61DiagnosticRunner) -> FundamentalBrainProbeStockResult:
        before_input = adapter.build(instrument.instrument_id, as_of=before_as_of)
        after_input = adapter.build(instrument.instrument_id, as_of=after_as_of)
        if before_input.fact_ids:
            raise FundamentalBrainProbeError("BSE_FACTS_VISIBLE_BEFORE_SYSTEM_FIRST_OBSERVED")
        if not after_input.fact_ids:
            raise FundamentalBrainProbeError("BSE_FACTS_NOT_VISIBLE_AFTER_SYSTEM_FIRST_OBSERVED")
        before_run = before_runner.run(before_assembler.assemble(instrument, before_as_of))
        after_run = after_runner.run(after_assembler.assemble(instrument, after_as_of))
        before_score = build_scorecard(
            instrument_id=instrument.instrument_id, strategy_version=before_runner._strategy,
            registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=before_as_of,
            evaluated_at=before_as_of, diagnostics=before_run.evaluations,
        )
        after_score = build_scorecard(
            instrument_id=instrument.instrument_id, strategy_version=after_runner._strategy,
            registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=after_as_of,
            evaluated_at=after_as_of, diagnostics=after_run.evaluations,
        )
        before_by_rule = {item.canonical_rule_id: item for item in before_run.evaluations}
        after_by_rule = {item.canonical_rule_id: item for item in after_run.evaluations}
        newly_evaluable = tuple(
            rule.canonical_name for rule in DIAGNOSTIC_RULES
            if before_by_rule[rule.rule_id].eligibility is not EvaluationEligibility.ELIGIBLE
            and after_by_rule[rule.rule_id].eligibility is EvaluationEligibility.ELIGIBLE
        )
        return FundamentalBrainProbeStockResult(
            instrument_id=instrument.instrument_id, symbol=instrument.symbol,
            first_observed_at=first_observed_at,
            filing_ids=tuple(sorted({fact.filing_id for fact in bse_facts if fact.filing_id})),
            fact_ids=tuple(sorted(fact.fact_id for fact in bse_facts)),
            before_diagnostic_evaluated=before_run.evaluated, before_diagnostic_missing=before_run.missing,
            after_diagnostic_evaluated=after_run.evaluated, after_diagnostic_missing=after_run.missing,
            newly_evaluable_diagnostics=newly_evaluable,
            before_coverage=_coverage_view(before_coverage, before_input),
            after_coverage=_coverage_view(after_coverage, after_input),
            before_decision_score_status=_score_status(before_score.final_score),
            after_decision_score_status=_score_status(after_score.final_score),
            before_confidence_status=_score_status(before_score.data_confidence if before_score.final_score is not None else None),
            after_confidence_status=_score_status(after_score.data_confidence if after_score.final_score is not None else None),
            consolidated_selected_after=after_input.statement_scope is not None and after_input.statement_scope.value == "CONSOLIDATED",
            unsupported_metrics_missing=_unsupported_metrics(after_input),
        )


def _coverage_view(record: DataCoverageRecord, input_: FundamentalEngineInput) -> FundamentalProbeCoverage:
    domains = {item.domain: item.status.value for item in record.domains}
    payloads = tuple(item.payload for item in input_.snapshot.observations)
    values = {key for payload in payloads for key in payload}
    earnings = "PARTIAL" if {"revenue", "pat", "eps"}.issubset(values) else "INSUFFICIENT"
    balance = "PARTIAL" if {"total_assets", "total_equity", "total_debt"} & values else "INSUFFICIENT"
    cash_flow = "PARTIAL" if {"operating_cash_flow", "capex"} & values else "INSUFFICIENT"
    technical = domains.get(DataCoverageDomain.HISTORICAL_OHLCV.value, "MISSING")
    return FundamentalProbeCoverage(
        filings=domains.get(DataCoverageDomain.FILINGS.value, "MISSING"),
        fundamentals=input_.completeness,
        earnings=earnings, balance_sheet=balance, cash_flow=cash_flow,
        technical=technical, deep_analysis=record.deep_analysis.value,
    )


def _unsupported_metrics(input_: FundamentalEngineInput) -> tuple[str, ...]:
    payloads = tuple(item.payload for item in input_.snapshot.observations)
    values = {key for payload in payloads for key in payload}
    absent = []
    if "ebitda" not in values:
        absent.append("EBITDA")
    if "operating_cash_flow" not in values:
        absent.append("CASH_FLOW")
    if not ({"total_assets", "total_equity", "total_debt"} & values):
        absent.append("BALANCE_SHEET")
    return tuple(absent)


def _score_status(value: object | None) -> str:
    return "AVAILABLE" if value is not None else "UNAVAILABLE"
