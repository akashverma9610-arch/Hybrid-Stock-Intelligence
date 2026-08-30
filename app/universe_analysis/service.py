"""Stored-data-only NSE universe and all-61 diagnostic orchestration."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import TYPE_CHECKING, Callable, Protocol
from uuid import uuid4

from app.analysis.fundamentals import FundamentalRules
from app.analysis.models import MarketRegimeRules, RelativeStrengthRules, TrendRules
from app.analysis.valuation_trade import TradeRules, ValuationRules
from app.crowd.models import CrowdSnapshot
from app.crowd.models import CrowdObservation, NewsEvent
from app.crowd.engine import CrowdRules
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators, WeinsteinRules
from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.diagnostics.synthesis import HigherOrderDiagnosticContext, SynthesisRules
from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticStrategyDefinition, require_canonical_61_runner_authorization,
)
from app.domain.models import AsOfSnapshot, MarketObservation, ObservationKind, StrategyVersionReference, ValidationStatus
from app.market_data.models import InstrumentIdentity, ProviderInstrumentMapping
from app.gates.engine import ActionContext, ExchangeCalendar, ExecutionGateConfig, ExecutionGateEngine, GateInput
from app.historical.guard import BacktestLookaheadGuard
from app.historical.models import HistoricalFact
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.scoring.engine import DecisionScorecard, build_scorecard
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.api.stock_query import AnalysisSectionQueryRecord, DiagnosticCoverageQueryRecord, StockAnalysisQueryResult
from app.portfolio.models import PortfolioSnapshot
from app.rotation.engine import CapitalRotationEngine
from app.rotation.models import RotationCandidate, RotationConfig, RotationEvaluationContext, RotationHoldingState
from app.research.models import Catalyst, GuidanceItem, ResearchClaim, ResearchDocument, ResearchSnapshot

from .models import (
    AnalyzedUniverseCandidate, CoverageDomain, CoverageDomainRecord, CoverageDomainStatus, DiagnosticCompleteness, NseEquityInstrument, OpportunityCoverageStatus,
    PortfolioUniverseRotationSnapshot, UniverseAnalysisItem, UniverseAnalysisJob, UniverseAnalysisJobStatus,
    UniverseAnalysisStage, UniverseEligibility, UniverseEligibilityStatus, UniverseInstrumentCoverage, UniverseOpportunity, UniverseOpportunitySnapshot, UniverseSnapshot,
    ProviderInstrumentMappingRecord, ProviderMappingStatus,
)
from .requirements import DIAGNOSTIC_INPUT_REQUIREMENTS

if TYPE_CHECKING:
    from app.storage.governance_repository import StrategyGovernanceRepository


class UniverseAnalysisError(ValueError):
    pass


class StoredObservationSource(Protocol):
    def observations_as_of(self, at: datetime) -> tuple[MarketObservation, ...]: ...


class NseUniverseSource(Protocol):
    def instruments_as_of(self, at: datetime) -> tuple[NseEquityInstrument, ...]: ...


@dataclass(frozen=True, slots=True)
class AssembledStockEvidence:
    symbol: str
    instrument_id: str
    sector_id: str | None
    as_of: datetime
    snapshot: AsOfSnapshot
    crowd: CrowdSnapshot
    research: ResearchSnapshot
    warnings: tuple[str, ...]
    freshness: str


@dataclass(frozen=True, slots=True)
class DiagnosticRun:
    evaluations: tuple[EvaluatedDiagnostic, ...]
    completeness: DiagnosticCompleteness
    evaluated: int
    missing: int
    warnings: tuple[str, ...]


class StockDiagnosticInputAssembler:
    """Assembles existing canonical stored facts once, with a fail-closed PIT cut."""

    def __init__(self, source: StoredObservationSource, guard: BacktestLookaheadGuard | None = None) -> None:
        self._source, self._guard = source, guard or BacktestLookaheadGuard()
        self._frozen_by_as_of: dict[datetime, tuple[tuple[MarketObservation, ...], int]] = {}

    def assemble(self, instrument: NseEquityInstrument, as_of: datetime) -> AssembledStockEvidence:
        cached = self._frozen_by_as_of.get(as_of)
        if cached is None:
            selected: list[MarketObservation] = []
            future_rejected = 0
            for observation in self._source.observations_as_of(as_of):
                fact = _historical_fact(observation)
                if self._guard.evaluate(fact, as_of).value != "ELIGIBLE":
                    future_rejected += 1
                    continue
                selected.append(observation)
            selected.sort(key=lambda item: (item.provenance.market_timestamp, item.id))
            cached = (tuple(selected), future_rejected)
            self._frozen_by_as_of[as_of] = cached
        selected, future_rejected = cached
        snapshot = AsOfSnapshot(
            f"universe-evidence:{as_of.isoformat()}", as_of, as_of,
            "canonical-stored-data;point-in-time-guard", selected,
        )
        own = tuple(item for item in selected if item.instrument.id == instrument.instrument_id)
        warnings: list[str] = []
        if not own:
            warnings.append("NO_INSTRUMENT_EVIDENCE")
        if future_rejected:
            warnings.append("FUTURE_EVIDENCE_EXCLUDED")
        freshness = "FRESH" if own and all(_valid(item) for item in own) else "PARTIAL" if own else "UNAVAILABLE"
        crowd, research = _research_evidence(selected, instrument.instrument_id, as_of)
        return AssembledStockEvidence(instrument.symbol, instrument.instrument_id, instrument.sector, as_of, snapshot,
                                      crowd, research, tuple(warnings), freshness)


class Canonical61DiagnosticRunner:
    """Registry-driven adapter over the existing 61 evaluator wrappers.

    The runner deliberately does not fetch providers or derive substitute
    evidence.  A wrapper exception/missing input becomes that rule's canonical
    missing result and does not abort the remainder of the registry.
    """

    def __init__(self, *, evaluator: DeterministicDiagnosticEvaluators | None = None,
                 strategy: StrategyVersionReference | None = None, benchmark_instrument_id: str = "NIFTY_50") -> None:
        self._evaluator = evaluator or DeterministicDiagnosticEvaluators()
        self._strategy = strategy or StrategyVersionReference("canonical-universe-analysis", "v1")
        self._benchmark = benchmark_instrument_id
        self._market_regime_cache: dict[str, EvaluatedDiagnostic] = {}
        actual = tuple(item.diagnostic_id for item in DIAGNOSTIC_INPUT_REQUIREMENTS)
        expected = tuple(rule.rule_id for rule in DIAGNOSTIC_RULES)
        if actual != expected:
            raise UniverseAnalysisError("Diagnostic requirements map does not match canonical registry.")

    def authorize(self, governance: StrategyGovernanceRepository) -> CanonicalDiagnosticStrategyDefinition:
        """Resolve the typed approved definition before a governed execution."""
        return require_canonical_61_runner_authorization(governance, self._strategy)

    def run(
        self,
        evidence: AssembledStockEvidence,
        *,
        governance: StrategyGovernanceRepository | None = None,
    ) -> DiagnosticRun:
        if governance is not None:
            self.authorize(governance)
        results: dict[int, EvaluatedDiagnostic] = {}
        # Rule 32 consumes the canonical trade-structure outputs 43/45/46 and
        # rule 34 consumes rule 32.  Evaluate that dependency tail first while
        # retaining registry order in the persisted/publicly distilled result.
        execution_order = tuple(rule.rule_id for rule in DIAGNOSTIC_RULES if rule.rule_id not in {32, 34}) + (32, 34)
        definitions = {rule.rule_id: rule for rule in DIAGNOSTIC_RULES}
        for rule_id in execution_order:
            definition = definitions[rule_id]
            try:
                results[definition.rule_id] = self._evaluate(definition.rule_id, evidence, results)
            except Exception:
                results[definition.rule_id] = self._evaluator._missing(
                    definition.rule_id, evidence.instrument_id, self._strategy, evidence.as_of,
                    "canonical stored inputs are unavailable or invalid",
                )
        normalized = tuple(_normalize(result, evidence.instrument_id, evidence.symbol) for result in (results[rule.rule_id] for rule in DIAGNOSTIC_RULES))
        evaluated = sum(item.eligibility is EvaluationEligibility.ELIGIBLE for item in normalized)
        missing = len(normalized) - evaluated
        completeness = DiagnosticCompleteness.COMPLETE if not missing else DiagnosticCompleteness.PARTIAL if evaluated else DiagnosticCompleteness.UNAVAILABLE
        warnings = () if not missing else ("DIAGNOSTIC_INPUTS_PARTIAL",)
        return DiagnosticRun(normalized, completeness, evaluated, missing, warnings)

    def _evaluate(self, rule_id: int, evidence: AssembledStockEvidence, prior: dict[int, EvaluatedDiagnostic]) -> EvaluatedDiagnostic:
        e, s, instrument, crowd, now = self._evaluator, evidence.snapshot, evidence.instrument_id, evidence.crowd, evidence.as_of
        strategy = self._strategy
        market_rules = MarketRegimeRules(2, 3, 2, 3, .2, .1, .02, -.02, -.1, -.4, .3)
        trend_rules = TrendRules(3, 5, True, 1)
        relative_rules = RelativeStrengthRules(3, .1, .03, -.03)
        fundamental_rules = FundamentalRules(.1, -.1, .1, 1.5, 2, .02)
        valuation_rules = ValuationRules(15, 35)
        trade_rules = TradeRules(5, .35, .03, .02, 2)
        liquidity_rules = __import__("app.analysis.liquidity", fromlist=["LiquidityRules"]).LiquidityRules(.01, 2, 1.5, 1.5)
        crowd_rules = CrowdRules(-.2, .2, -.6, .6, .7, .4)
        synthesis_rules = SynthesisRules()
        if rule_id == 1:
            cached = self._market_regime_cache.get(s.id)
            if cached is None:
                cached = e.market_regime(s, self._benchmark, strategy, market_rules, now)
                self._market_regime_cache[s.id] = cached
            return cached
        sector = evidence.sector_id or instrument
        if rule_id == 2: return e.sector_health(s, sector, self._benchmark, strategy, 3, .03, -.03, now)
        if rule_id == 3: return e.sector_rotation(s, sector, self._benchmark, strategy, 3, .03, -.03, now)
        if rule_id == 4: return e.primary_trend(s, s, instrument, strategy, trend_rules, now)
        if rule_id == 5: return e.weinstein(s, instrument, strategy, WeinsteinRules(3, 2), now)
        if rule_id == 6: return e.relative_strength(s, instrument, self._benchmark, sector, (), strategy, relative_rules, now)
        if rule_id == 7: return e.smart_money_proxies(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 8: return e.liquidity_pools(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 9: return e.wyckoff_phase(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 10: return e.market_structure(s, instrument, strategy, 1, now)
        if rule_id == 11: return e.volume(s, instrument, strategy, 3, 1.5, .5, now)
        if rule_id == 12: return e.ichimoku(s, instrument, strategy, 2, 3, 4, 1, now)
        if rule_id == 13: return e.chikou(s, instrument, strategy, 2, 3, 4, 1, now)
        if rule_id == 14: return e.mtf({"daily": s, "weekly": s}, instrument, strategy, now)
        if rule_id == 15: return e.business_model_moat(evidence.research, instrument, strategy, now)
        if rule_id == 16: return e.financial_trend(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 17: return e.return_ratios(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 18: return e.cash_flow(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 19: return e.leverage(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 20: return e.working_capital(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 21: return e.ownership(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 22: return e.institutional_holdings(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 23: return e.corporate_governance(evidence.research, instrument, strategy, now)
        if rule_id == 24: return e.earnings_acceleration(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 25: return e.latest_quarter(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 26: return e.margin_trajectory(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 27: return e.order_book(s, instrument, strategy, fundamental_rules, now)
        if rule_id == 28: return e.management_guidance(evidence.research, instrument, strategy, now)
        if rule_id == 29: return e.valuation_multiples(s, s, instrument, strategy, valuation_rules, now)
        if rule_id == 30: return e.fundamental_catalysts(evidence.research, instrument, strategy, now)
        if rule_id in {31, 32, 33, 34}:
            context = HigherOrderDiagnosticContext(now, strategy, DIAGNOSTIC_REGISTRY_VERSION, tuple(prior.values()), synthesis_rules.version)
            return {31: e.comprehensive_risk, 32: e.trading_thesis, 33: e.investment_thesis, 34: e.scenarios}[rule_id](context, instrument, strategy, synthesis_rules, now)
        if rule_id == 35: return e.vwap(s, instrument, strategy, now)
        if rule_id == 36: return e.obv(s, instrument, strategy, 3, now)
        if rule_id == 37: return e.base_pattern(s, instrument, strategy, trade_rules, now)
        if rule_id == 38: return e.pullback_quality(s, instrument, strategy, trade_rules, now)
        if rule_id == 39: return e.indicator_layer(s, instrument, strategy, 3, 70, 30, 20, 2, now)
        if rule_id == 40: return e.aggressive_entry(s, instrument, strategy, trade_rules, now)
        if rule_id == 41: return e.confirmation_entry(s, instrument, strategy, trade_rules, now)
        if rule_id == 42: return e.retest_entry(s, instrument, strategy, trade_rules, now)
        if rule_id == 43: return e.structural_stop(s, instrument, strategy, trade_rules, now)
        if rule_id == 44: return e.target_hierarchy(s, instrument, strategy, trade_rules, now)
        if rule_id == 45:
            return e.risk_reward(s, instrument, strategy, trade_rules,
                                 _detail_number(prior.get(40), "entry"), _detail_number(prior.get(43), "stop"),
                                 _detail_number(prior.get(44), "t1"), now)
        if rule_id == 46: return e.thesis_invalidation(s, instrument, strategy, trade_rules, now)
        if rule_id == 47: return e.crowd_sentiment(crowd, instrument, strategy, crowd_rules, now)
        if rule_id == 48: return e.crowd_positioning(crowd, instrument, strategy, crowd_rules, now)
        if rule_id == 49: return e.crowd_data_confidence(crowd, instrument, strategy, crowd_rules, now)
        if rule_id == 50: return e.accumulation_distribution_proxy(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 51: return e.stop_clusters(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 52: return e.liquidity_events(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 53: return e.bull_trap(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 54: return e.bear_trap(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 55: return e.crowd_trap_probability(crowd, s, instrument, strategy, crowd_rules, now)
        if rule_id == 56: return e.crowd_divergence(crowd, s, instrument, strategy, crowd_rules, now)
        if rule_id == 57: return e.post_news_reaction(crowd, s, instrument, strategy, now)
        if rule_id == 58: return e.volume_climax(s, instrument, strategy, liquidity_rules, now)
        if rule_id == 59: return e.contrarian_ichimoku(prior.get(47), prior.get(12), prior.get(13), prior.get(14), instrument, strategy, now)
        if rule_id == 60: return e.contrarian_quality(prior.get(55), prior.get(56), prior.get(59), prior.get(49), instrument, strategy, now)
        if rule_id == 61: return e.contrarian_verdict(prior.get(60), prior.get(49), instrument, strategy, now)
        raise UniverseAnalysisError(f"No evaluator wrapper configured for canonical rule {rule_id}.")


class CoreUniverseAnalysisStore:
    """Append-only job, universe, and opportunity persistence through core snapshots."""
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_job(self, value: UniverseAnalysisJob) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_JOB, f"universe-job:{value.job_id}:{value.revision}", value, value.requested_at)

    def save_instrument(self, value: NseEquityInstrument) -> None:
        self._save(CoreApiSnapshotFamily.NSE_UNIVERSE, f"nse-equity:{value.instrument_id}:{value.data_as_of.isoformat()}", value, value.data_as_of)

    def save_universe_snapshot(self, value: UniverseSnapshot) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_SNAPSHOT, f"universe-snapshot:{value.snapshot_id}", value, value.as_of)

    def save_provider_mapping(self, value: ProviderInstrumentMappingRecord) -> None:
        """Append one immutable mapping version; never update a prior token."""
        self._save(
            CoreApiSnapshotFamily.PROVIDER_INSTRUMENT_MAPPING,
            f"provider-mapping:{value.mapping_id}", value, value.effective_as_of,
        )

    def provider_mapping(
        self, *, canonical_instrument_id: str, provider: str, as_of: datetime | None = None,
    ) -> ProviderInstrumentMappingRecord | None:
        """Return the latest effective immutable mapping, never a provider lookup."""
        values = tuple(
            item.payload for item in self._all(CoreApiSnapshotFamily.PROVIDER_INSTRUMENT_MAPPING)
            if isinstance(item.payload, ProviderInstrumentMappingRecord)
            and item.payload.canonical_instrument_id == canonical_instrument_id
            and item.payload.provider.upper() == provider.upper()
            and (as_of is None or item.payload.effective_as_of <= as_of)
        )
        latest = max(values, key=lambda item: (item.effective_as_of, item.mapping_id)) if values else None
        return latest if latest is not None and latest.status is ProviderMappingStatus.ACTIVE else None

    def provider_mappings(self, *, provider: str, as_of: datetime | None = None) -> tuple[ProviderInstrumentMappingRecord, ...]:
        """Read the latest active mapping per instrument in one stored pass."""
        latest: dict[str, ProviderInstrumentMappingRecord] = {}
        for item in self._all(CoreApiSnapshotFamily.PROVIDER_INSTRUMENT_MAPPING):
            value = item.payload
            if (
                not isinstance(value, ProviderInstrumentMappingRecord)
                or value.provider.upper() != provider.upper()
                or value.status is not ProviderMappingStatus.ACTIVE
                or (as_of is not None and value.effective_as_of > as_of)
            ):
                continue
            current = latest.get(value.canonical_instrument_id)
            if current is None or (value.effective_as_of, value.mapping_id) > (current.effective_as_of, current.mapping_id):
                latest[value.canonical_instrument_id] = value
        return tuple(sorted(latest.values(), key=lambda value: value.canonical_instrument_id))

    def capture_provider_mapping(
        self,
        instrument: InstrumentIdentity,
        *,
        provider: str,
        effective_as_of: datetime,
        resolved_instrument: InstrumentIdentity | None = None,
        source_reference: str | None = None,
        source_checksum: str | None = None,
    ) -> ProviderInstrumentMappingRecord:
        """Persist the one unambiguous mapping already resolved by a provider.

        This method never resolves a symbol, fetches a provider master, or
        calls a quote endpoint.  It is deliberately a persistence boundary for
        a mapping obtained by an upstream bounded provider operation.
        """
        resolved = resolved_instrument or instrument
        if instrument.isin and resolved.isin and instrument.isin.upper() != resolved.isin.upper():
            raise UniverseAnalysisError("Canonical instrument and provider mapping have different ISINs.")
        matches = tuple(item for item in resolved.provider_mappings if item.provider.upper() == provider.upper())
        if len(matches) != 1 or not matches[0].provider_exchange_segment:
            raise UniverseAnalysisError("Instrument has no unambiguous provider mapping to persist.")
        value = matches[0]
        fingerprint = sha256(
            "|".join((provider.upper(), instrument.instrument_id, value.provider_exchange_segment,
                      value.provider_instrument_reference, value.mapping_version, effective_as_of.isoformat(),
                      source_checksum or "")).encode()
        ).hexdigest()[:24]
        record = ProviderInstrumentMappingRecord(
            mapping_id=f"mapping:{provider.lower()}:{fingerprint}",
            canonical_instrument_id=instrument.instrument_id,
            provider=provider.upper(),
            provider_exchange_segment=value.provider_exchange_segment,
            provider_instrument_reference=value.provider_instrument_reference,
            provider_symbol=value.provider_symbol,
            isin=instrument.isin,
            status=ProviderMappingStatus.ACTIVE,
            effective_as_of=effective_as_of,
            source_reference=source_reference,
            source_checksum=source_checksum,
            mapping_version=value.mapping_version,
        )
        self.save_provider_mapping(record)
        return record

    def instrument_with_provider_mapping(
        self, instrument: InstrumentIdentity, *, provider: str, as_of: datetime | None = None,
    ) -> InstrumentIdentity | None:
        """Rehydrate an existing canonical identity with its stored mapping only."""
        record = self.provider_mapping(
            canonical_instrument_id=instrument.instrument_id, provider=provider, as_of=as_of,
        )
        if record is None:
            return None
        retained = tuple(item for item in instrument.provider_mappings if item.provider.upper() != provider.upper())
        return replace(
            instrument,
            provider_mappings=retained + (ProviderInstrumentMapping(
                record.provider, record.provider_instrument_reference, record.provider_symbol,
                record.mapping_version, record.provider_exchange_segment,
            ),),
        )

    def get_universe_snapshot(self, snapshot_id: str) -> UniverseSnapshot | None:
        value = self._repository.get_snapshot(f"universe-snapshot:{snapshot_id}")
        return value.payload if value is not None and isinstance(value.payload, UniverseSnapshot) else None

    def latest_universe_snapshot(self) -> UniverseSnapshot | None:
        values = tuple(item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_SNAPSHOT)
                       if isinstance(item.payload, UniverseSnapshot))
        return max(values, key=lambda item: (item.as_of, item.snapshot_id)) if values else None

    def universe_snapshot_by_checksum(self, checksum: str) -> UniverseSnapshot | None:
        values = tuple(item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_SNAPSHOT)
                       if isinstance(item.payload, UniverseSnapshot) and item.payload.checksum == checksum)
        return max(values, key=lambda item: (item.as_of, item.snapshot_id)) if values else None

    def save_candidate(self, value: AnalyzedUniverseCandidate) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_CANDIDATE, f"universe-candidate:{value.candidate_id}", value, value.as_of)

    def candidates(self, job_id: str) -> tuple[AnalyzedUniverseCandidate, ...]:
        return tuple(item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_CANDIDATE)
                     if isinstance(item.payload, AnalyzedUniverseCandidate) and item.payload.job_id == job_id)

    def save_coverage(self, value: UniverseInstrumentCoverage) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_COVERAGE, f"universe-coverage:{value.coverage_id}", value, value.as_of)

    def coverage(self, job_id: str) -> tuple[UniverseInstrumentCoverage, ...]:
        return tuple(item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_COVERAGE)
                     if isinstance(item.payload, UniverseInstrumentCoverage) and item.payload.job_id == job_id)

    def save_rotation_snapshot(self, value: PortfolioUniverseRotationSnapshot) -> None:
        self._save(CoreApiSnapshotFamily.PORTFOLIO_UNIVERSE_ROTATION, f"portfolio-universe-rotation:{value.snapshot_id}", value, value.generated_at)

    def get_rotation_snapshot(self, snapshot_id: str) -> PortfolioUniverseRotationSnapshot | None:
        value = self._repository.get_snapshot(f"portfolio-universe-rotation:{snapshot_id}")
        return value.payload if value is not None and isinstance(value.payload, PortfolioUniverseRotationSnapshot) else None

    def instruments_as_of(self, at: datetime) -> tuple[NseEquityInstrument, ...]:
        latest: dict[str, NseEquityInstrument] = {}
        for item in self._all(CoreApiSnapshotFamily.NSE_UNIVERSE):
            value = item.payload
            if not isinstance(value, NseEquityInstrument) or value.data_as_of > at:
                continue
            if value.instrument_id not in latest or latest[value.instrument_id].data_as_of < value.data_as_of:
                latest[value.instrument_id] = value
        return tuple(sorted(latest.values(), key=lambda item: (item.symbol, item.instrument_id)))

    def save_opportunity(self, value: UniverseOpportunitySnapshot) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_OPPORTUNITY, f"universe-opportunity:{value.snapshot_id}", value, value.as_of)

    def save_stock_analysis(self, value: StockAnalysisQueryResult) -> None:
        self._save(CoreApiSnapshotFamily.STOCK_ANALYSIS, f"universe-stock:{value.symbol}:{value.data_as_of.isoformat()}", value, value.analysis_timestamp)

    def save_item(self, value: UniverseAnalysisItem, at: datetime) -> None:
        self._save(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_ITEM, f"universe-item:{value.job_id}:{value.instrument_id}", value, at)

    def items(self, job_id: str) -> tuple[UniverseAnalysisItem, ...]:
        return tuple(item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_ITEM)
                     if isinstance(item.payload, UniverseAnalysisItem) and item.payload.job_id == job_id)

    def get_job(self, job_id: str) -> UniverseAnalysisJob | None:
        values = [item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_JOB) if isinstance(item.payload, UniverseAnalysisJob) and item.payload.job_id == job_id]
        return max(values, key=lambda item: item.revision) if values else None

    def next_queued(self) -> UniverseAnalysisJob | None:
        values: dict[str, UniverseAnalysisJob] = {}
        for item in self._all(CoreApiSnapshotFamily.UNIVERSE_ANALYSIS_JOB):
            if isinstance(item.payload, UniverseAnalysisJob) and (item.payload.job_id not in values or values[item.payload.job_id].revision < item.payload.revision): values[item.payload.job_id] = item.payload
        queued = tuple(item for item in values.values() if item.status in {UniverseAnalysisJobStatus.QUEUED, UniverseAnalysisJobStatus.RUNNING})
        return min(queued, key=lambda item: (item.requested_at, item.job_id)) if queued else None

    def latest_opportunity(self) -> UniverseOpportunitySnapshot | None:
        values = [item.payload for item in self._all(CoreApiSnapshotFamily.UNIVERSE_OPPORTUNITY) if isinstance(item.payload, UniverseOpportunitySnapshot)]
        return max(values, key=lambda item: (item.as_of, item.snapshot_id)) if values else None

    def _save(self, family, identifier: str, payload: object, created_at: datetime) -> None:
        fingerprint = sha256(repr(payload).encode()).hexdigest()
        self._repository.save_snapshot(CoreApiSnapshot(identifier, family, "v1", "universe-analysis-v1", fingerprint, created_at, payload))

    def _all(self, family):
        values = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100:
                return tuple(values)
            offset += len(page)


class UniverseAnalysisService:
    """Bounded cooperative full-universe job; no HTTP-triggered provider fan-out."""
    def __init__(self, *, universe: NseUniverseSource, assembler: StockDiagnosticInputAssembler,
                 runner: Canonical61DiagnosticRunner, store: CoreUniverseAnalysisStore,
                 gate_config: ExecutionGateConfig | None = None,
                 gate_input_factory: Callable[[NseEquityInstrument, AssembledStockEvidence, DecisionScorecard], GateInput] | None = None,
                 clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._universe, self._assembler, self._runner, self._store, self._clock = universe, assembler, runner, store, clock
        self._gate_config = gate_config or _unresolved_gate_config()
        self._gate_input_factory = gate_input_factory

    def request(self, *, universe_id: str, universe_as_of: datetime, as_of: datetime, batch_size: int = 100,
                universe_snapshot_id: str | None = None) -> UniverseAnalysisJob:
        if batch_size < 1 or batch_size > 1000:
            raise UniverseAnalysisError("batch_size must be between 1 and 1000")
        now = self._clock()
        job = UniverseAnalysisJob(f"universe-analysis-{uuid4().hex}", 1, UniverseAnalysisJobStatus.QUEUED, now, None, None,
                                  universe_id, universe_as_of, as_of, 0, batch_size, 0, 0, 0, 0, 0, 0, (), universe_snapshot_id,
                                  UniverseAnalysisStage.UNIVERSE_READY)
        self._store.save_job(job)
        return job

    def get_job(self, job_id: str) -> UniverseAnalysisJob:
        value = self._store.get_job(job_id)
        if value is None: raise UniverseAnalysisError("UNIVERSE_ANALYSIS_JOB_NOT_FOUND")
        return value

    def latest_opportunity(self) -> UniverseOpportunitySnapshot | None:
        return self._store.latest_opportunity()

    def run_next_batch(self) -> UniverseAnalysisJob | None:
        job = self._store.next_queued()
        if job is None: return None
        members = self._universe.instruments_as_of(job.universe_as_of)
        if job.status is UniverseAnalysisJobStatus.QUEUED:
            job = replace(job, revision=job.revision + 1, status=UniverseAnalysisJobStatus.RUNNING,
                          stage=UniverseAnalysisStage.COVERAGE_PREFLIGHT, started_at=self._clock())
            self._store.save_job(job)
        if job.stage in {UniverseAnalysisStage.UNIVERSE_READY, UniverseAnalysisStage.COVERAGE_PREFLIGHT}:
            readiness = tuple(_coverage_preflight(job, instrument, self._assembler) for instrument in members)
            existing_coverage = {value.coverage_id for value in self._store.coverage(job.job_id)}
            for value in readiness:
                if value.coverage_id not in existing_coverage:
                    self._store.save_coverage(value)
            ready = sum(value.complete for value in readiness)
            partial = sum(not value.complete and any(record.status in {CoverageDomainStatus.READY, CoverageDomainStatus.PARTIAL, CoverageDomainStatus.STALE} for record in value.domains) for value in readiness)
            job = replace(job, revision=job.revision + 1, stage=UniverseAnalysisStage.ELIGIBILITY_COMPLETE,
                          coverage_ready_count=ready, coverage_partial_count=partial,
                          coverage_missing_count=len(readiness) - ready - partial)
            self._store.save_job(job)
        if job.stage is UniverseAnalysisStage.ELIGIBILITY_COMPLETE:
            job = replace(job, revision=job.revision + 1, stage=UniverseAnalysisStage.ANALYZING)
            self._store.save_job(job)
        start, end = job.cursor, min(job.cursor + job.batch_size, len(members))
        complete = partial = unavailable = failed = eligible_count = 0
        for instrument in members[start:end]:
            eligibility = _eligibility(instrument, job.as_of, self._assembler)
            if eligibility.status is not UniverseEligibilityStatus.ELIGIBLE:
                unavailable += 1
                self._store.save_item(UniverseAnalysisItem(job.job_id, instrument.instrument_id, instrument.symbol, eligibility.status,
                                                            DiagnosticCompleteness.UNAVAILABLE, None, None, (eligibility.reason,)), job.as_of)
                continue
            eligible_count += 1
            try:
                evidence = self._assembler.assemble(instrument, job.as_of)
                output = self._runner.run(evidence)
                score = build_scorecard(instrument_id=instrument.instrument_id, strategy_version=self._runner._strategy,
                                        registry_version=DIAGNOSTIC_REGISTRY_VERSION, as_of_timestamp=job.as_of,
                                        evaluated_at=job.as_of, diagnostics=output.evaluations)
                gate = _gates(self._gate_config, score, output.evaluations, evidence, job.as_of, self._runner._strategy,
                              self._gate_input_factory(instrument, evidence, score) if self._gate_input_factory else None)
                stock = _stock_result(instrument, output, score, gate, job.as_of)
                self._store.save_stock_analysis(stock)
                if output.completeness is DiagnosticCompleteness.COMPLETE: complete += 1
                elif output.completeness is DiagnosticCompleteness.PARTIAL: partial += 1
                else: unavailable += 1
                opportunity = _opportunity(instrument, score, gate, output, evidence) if score.final_score is not None and gate.eligibility.value == "EXECUTABLE" else None
                candidate = _candidate_from_analysis(job, instrument, stock, score, gate, output, evidence) if job.universe_snapshot_id is not None else None
                self._store.save_item(UniverseAnalysisItem(job.job_id, instrument.instrument_id, instrument.symbol,
                                                            eligibility.status, output.completeness, f"universe-stock:{stock.symbol}:{stock.data_as_of.isoformat()}", opportunity, output.warnings, candidate), job.as_of)
            except Exception:
                failed += 1
                self._store.save_item(UniverseAnalysisItem(job.job_id, instrument.instrument_id, instrument.symbol, eligibility.status,
                                                            DiagnosticCompleteness.UNAVAILABLE, None, None, ("STOCK_ANALYSIS_FAILED",)), job.as_of)
        progress = end
        done = progress >= len(members)
        status = UniverseAnalysisJobStatus.COMPLETED if done and not (partial or unavailable or failed) else UniverseAnalysisJobStatus.PARTIAL if done else UniverseAnalysisJobStatus.RUNNING
        result = replace(job, revision=job.revision + 1, status=status, completed_at=self._clock() if done else None,
                         cursor=progress, eligible_total=job.eligible_total + eligible_count, processed=job.processed + (end - start), complete_count=job.complete_count + complete,
                         partial_count=job.partial_count + partial, unavailable_count=job.unavailable_count + unavailable,
                         failed_count=job.failed_count + failed,
                         stage=UniverseAnalysisStage.CANDIDATES_MATERIALIZED if done else UniverseAnalysisStage.ANALYZING,
                         warnings=tuple(sorted(set(job.warnings + (("UNIVERSE_ANALYSIS_PARTIAL",) if partial or unavailable or failed else ())))) )
        self._store.save_job(result)
        if done:
            existing_candidates = {value.candidate_id for value in self._store.candidates(result.job_id)}
            for item in self._store.items(result.job_id):
                if item.candidate is not None and item.candidate.candidate_id not in existing_candidates:
                    self._store.save_candidate(item.candidate)
            items = self._store.items(result.job_id)
            opportunities = tuple(
                item.opportunity for item in items
                if item.opportunity is not None and (item.candidate is None or item.candidate.qualification_status == "QUALIFIED")
            )
            snapshot = UniverseOpportunitySnapshot(
                f"opportunity:{result.job_id}:{result.as_of.isoformat()}", result.job_id, result.as_of, len(members), result.eligible_total,
                result.processed, result.complete_count, result.partial_count, result.unavailable_count,
                len(opportunities), tuple(sorted(opportunities, key=lambda item: (item.score is None, -(item.score or Decimal("0")), item.symbol))),
                result.warnings, "AS_OF_SNAPSHOT", result.universe_snapshot_id,
                _coverage(result, bool(self._store.candidates(result.job_id))),
            )
            self._store.save_opportunity(snapshot)
        return result


def _eligibility(instrument: NseEquityInstrument, as_of: datetime, assembler: StockDiagnosticInputAssembler) -> UniverseEligibility:
    if instrument.security_type != "EQUITY": return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.UNSUPPORTED_SECURITY_TYPE, "NSE equity opportunity universe excludes this security type.", as_of)
    if instrument.listing_status.upper() != "ACTIVE" or instrument.tradable is False: return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.NOT_LISTED_OR_TRADABLE, "Instrument is not actively listed/tradable.", as_of)
    if not instrument.instrument_id or not instrument.symbol: return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.MISSING_INSTRUMENT_MAPPING, "Canonical instrument identity is incomplete.", as_of)
    evidence = assembler.assemble(instrument, as_of)
    own = tuple(item for item in evidence.snapshot.observations if item.instrument.id == instrument.instrument_id)
    bars = tuple(item for item in own if item.kind is ObservationKind.PRICE_BAR)
    if not own: return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.NO_CURRENT_DATA, "No stored canonical data is available as-of.", as_of)
    if len(bars) < 3: return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.INSUFFICIENT_HISTORY, "Minimum stored price-history coverage is unavailable.", as_of, tuple(item.id for item in own))
    return UniverseEligibility(instrument.instrument_id, instrument.symbol, UniverseEligibilityStatus.ELIGIBLE, "Eligible for registry-wide analysis; this is not a ranking decision.", as_of, tuple(item.id for item in own))


_CANONICAL_BAR_LOOKBACK = 6


def _coverage_preflight(job: UniverseAnalysisJob, instrument: NseEquityInstrument,
                        assembler: StockDiagnosticInputAssembler) -> UniverseInstrumentCoverage:
    """Describe stored input readiness without assigning quality or rank."""
    evidence = assembler.assemble(instrument, job.as_of)
    own = tuple(item for item in evidence.snapshot.observations if item.instrument.id == instrument.instrument_id)
    bars = tuple(item for item in own if item.kind is ObservationKind.PRICE_BAR and _valid(item))
    all_bars = tuple(item for item in evidence.snapshot.observations if item.kind is ObservationKind.PRICE_BAR and _valid(item))
    fundamentals = tuple(item for item in own if item.kind is ObservationKind.FUNDAMENTAL and _valid(item) and isinstance(item.payload, dict))
    annual = tuple(item for item in fundamentals if item.payload.get("period_type") == "annual")
    quarterly = tuple(item for item in fundamentals if item.payload.get("period_type") == "quarterly")
    ownership = tuple(item for item in fundamentals if all(key in item.payload for key in ("promoter_holding", "promoter_pledge", "fii_holding", "dii_holding", "mutual_fund_holding")))
    latest = max((item.provenance.market_timestamp for item in bars), default=None)
    current_status = CoverageDomainStatus.MISSING if not bars else CoverageDomainStatus.STALE if latest is not None and (job.as_of - latest).days > 7 else CoverageDomainStatus.READY
    historical_status = CoverageDomainStatus.READY if len(bars) >= _CANONICAL_BAR_LOOKBACK else CoverageDomainStatus.PARTIAL if bars else CoverageDomainStatus.MISSING
    fundamentals_status = CoverageDomainStatus.READY if len(annual) >= 6 and len(quarterly) >= 5 else CoverageDomainStatus.PARTIAL if fundamentals else CoverageDomainStatus.MISSING
    filings_status = CoverageDomainStatus.READY if fundamentals else CoverageDomainStatus.MISSING
    research_status = CoverageDomainStatus.READY if evidence.research.documents else CoverageDomainStatus.MISSING
    ownership_status = CoverageDomainStatus.READY if len(ownership) >= 2 else CoverageDomainStatus.PARTIAL if ownership else CoverageDomainStatus.MISSING
    benchmark_bars = tuple(item for item in all_bars if item.instrument.id == "NIFTY_50")
    market_status = CoverageDomainStatus.READY if len(benchmark_bars) >= _CANONICAL_BAR_LOOKBACK else CoverageDomainStatus.PARTIAL if benchmark_bars else CoverageDomainStatus.MISSING
    sector_bars = tuple(item for item in all_bars if instrument.sector and item.instrument.id == instrument.sector)
    sector_status = CoverageDomainStatus.READY if len(sector_bars) >= 4 else CoverageDomainStatus.PARTIAL if sector_bars else CoverageDomainStatus.MISSING
    domains = (
        _coverage_domain(CoverageDomain.CURRENT_QUOTES, current_status, latest, "current canonical quote/bar unavailable"),
        _coverage_domain(CoverageDomain.HISTORICAL, historical_status, latest, f"minimum {_CANONICAL_BAR_LOOKBACK}-bar stored lookback unavailable"),
        _coverage_domain(CoverageDomain.FUNDAMENTALS, fundamentals_status, _latest_timestamp(fundamentals), "annual/quarterly reported facts incomplete"),
        _coverage_domain(CoverageDomain.FILINGS, filings_status, _latest_timestamp(fundamentals), "official filing/fundamental evidence unavailable"),
        _coverage_domain(CoverageDomain.NEWS, research_status, _latest_research_timestamp(evidence.research), "validated stored research/news evidence unavailable"),
        _coverage_domain(CoverageDomain.OWNERSHIP, ownership_status, _latest_timestamp(ownership), "periodic shareholding evidence unavailable"),
        _coverage_domain(CoverageDomain.MARKET_CONTEXT, market_status, _latest_timestamp(benchmark_bars), "stored benchmark market context unavailable"),
        _coverage_domain(CoverageDomain.SECTOR_CONTEXT, sector_status, _latest_timestamp(sector_bars), "stored sector context unavailable"),
    )
    warnings = tuple(f"COVERAGE_{item.domain.value}:{item.status.value}" for item in domains if item.status is not CoverageDomainStatus.READY)
    return UniverseInstrumentCoverage(f"coverage:{job.job_id}:{instrument.instrument_id}", job.universe_snapshot_id,
                                      job.job_id, instrument.instrument_id, job.as_of, domains, warnings)


def _coverage_domain(domain: CoverageDomain, status: CoverageDomainStatus, data_as_of: datetime | None,
                     missing_reason: str) -> CoverageDomainRecord:
    freshness = "FRESH" if status is CoverageDomainStatus.READY else "STALE" if status is CoverageDomainStatus.STALE else "PARTIAL" if status is CoverageDomainStatus.PARTIAL else "UNAVAILABLE"
    return CoverageDomainRecord(domain, status, data_as_of, freshness, None if status is CoverageDomainStatus.READY else missing_reason)


def _latest_timestamp(values: tuple[MarketObservation, ...]) -> datetime | None:
    return max((item.provenance.market_timestamp for item in values), default=None)


def _latest_research_timestamp(snapshot: ResearchSnapshot) -> datetime | None:
    return max((item.publication_timestamp for item in snapshot.documents), default=None)


def _gates(config, score, diagnostics, evidence, at, strategy, supplied: GateInput | None = None):
    values = supplied or GateInput(score.id, score.final_score, evidence.snapshot.id, at, diagnostic_ids=tuple(item.record.id for item in diagnostics))
    if values.scorecard_id != score.id or values.snapshot_id != evidence.snapshot.id or values.snapshot_as_of_timestamp != at:
        raise UniverseAnalysisError("Gate inputs must remain bound to this instrument's frozen analysis snapshot and scorecard.")
    return ExecutionGateEngine(config, ExchangeCalendar("NSE")).evaluate(instrument_id=evidence.instrument_id, strategy_version=strategy,
        registry_version=DIAGNOSTIC_REGISTRY_VERSION, scoring_configuration_version=score.configuration_version,
        action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=at, evaluated_at=at, inputs=values)


def _stock_result(instrument, output, score, gates, at):
    coverage = DiagnosticCoverageQueryRecord(61, 0, 0, 0, output.missing, output.evaluations)
    sections = AnalysisSectionQueryRecord(output.completeness.value, (), output.warnings)
    return StockAnalysisQueryResult(instrument.symbol, "NSE", instrument.symbol, instrument.sector, instrument.industry, at, at,
                                    output.completeness.value, None, None, None, coverage, score, gates,
                                    technical=sections, fundamentals=sections, research=sections, valuation=sections,
                                    trade_structure=sections, liquidity=sections, warnings=output.warnings)


def _opportunity(instrument, score, gates, output, evidence):
    rr = next((item.record.result for item in output.evaluations if item.canonical_rule_id == 45), None)
    catalyst = next((item.record.result for item in output.evaluations if item.canonical_rule_id == 30), None)
    return UniverseOpportunity(instrument.symbol, instrument.sector, score.final_score, score.data_confidence, rr,
                               gates.eligibility.value, "QUALIFIED", catalyst, evidence.freshness, output.warnings)


def _normalize(value: EvaluatedDiagnostic, instrument_id: str, symbol: str) -> EvaluatedDiagnostic:
    record = replace(value.record, id=f"universe:{symbol}:{value.record.id}", instrument_id=instrument_id)
    return replace(value, record=record)


def _historical_fact(observation: MarketObservation) -> HistoricalFact:
    publication = getattr(observation, "publication_timestamp", None)
    if publication is None and isinstance(observation.payload, dict): publication = observation.payload.get("publication_timestamp")
    return HistoricalFact(observation.id, str(observation.kind), observation.provenance.market_timestamp, publication, observation.provenance.retrieved_timestamp)


def _research_evidence(observations: tuple[MarketObservation, ...], instrument_id: str,
                       as_of: datetime) -> tuple[CrowdSnapshot, ResearchSnapshot]:
    """Adapt already-stored typed research/crowd facts; never call a provider.

    Research observations may carry the canonical typed values produced by the
    research/news pipeline.  Unknown payloads are deliberately ignored so an
    unsupported source remains missing rather than being guessed into evidence.
    """
    documents: list[ResearchDocument] = []
    claims: list[ResearchClaim] = []
    guidance: list[GuidanceItem] = []
    catalysts: list[Catalyst] = []
    crowd: list[CrowdObservation] = []
    events: list[NewsEvent] = []
    for item in observations:
        if item.instrument.id != instrument_id or item.kind is not ObservationKind.RESEARCH or not isinstance(item.payload, dict):
            continue
        payload = item.payload
        document = payload.get("research_document")
        if isinstance(document, ResearchDocument):
            documents.append(document)
        for value, expected, target in (
            (payload.get("research_claims", ()), ResearchClaim, claims),
            (payload.get("guidance", ()), GuidanceItem, guidance),
            (payload.get("catalysts", ()), Catalyst, catalysts),
            (payload.get("crowd_observations", ()), CrowdObservation, crowd),
            (payload.get("news_events", ()), NewsEvent, events),
        ):
            if isinstance(value, expected):
                target.append(value)
            elif isinstance(value, tuple):
                target.extend(entry for entry in value if isinstance(entry, expected))
    from app.crowd.engine import as_of as crowd_as_of
    from app.research.engine import as_of as research_as_of
    return (
        crowd_as_of(CrowdSnapshot(as_of, tuple(crowd), tuple(events)), as_of),
        research_as_of(ResearchSnapshot(as_of, tuple(documents), tuple(claims), tuple(guidance), tuple(catalysts)), as_of),
    )


def _valid(observation: MarketObservation) -> bool:
    return observation.validation is not None and observation.validation.status is ValidationStatus.VALID


def _detail_number(value: EvaluatedDiagnostic | None, key: str) -> float | None:
    if value is None:
        return None
    raw = dict(value.details).get(key)
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _unresolved_gate_config() -> ExecutionGateConfig:
    return ExecutionGateConfig("universe-analysis-gates-v1", None, None, None, True, None, None, None, None, None, None, None, None, None, None, None, None, None, None)


def build_universe_snapshot(*, snapshot_id: str, as_of: datetime, source: str,
                            instruments: tuple[NseEquityInstrument, ...], version: str = "nse-equity-universe-v1") -> UniverseSnapshot:
    """Freeze the supported NSE main-board equity scope without guessing metadata."""
    ordered = tuple(sorted(instruments, key=lambda item: (item.instrument_id, item.data_as_of)))
    eligible = tuple(item for item in ordered if item.exchange == "NSE" and item.security_type == "EQUITY" and item.main_board is not False)
    # Content identity intentionally excludes import time.  A byte-for-byte or
    # canonical-equivalent official source can be recognised on a later local
    # import without mutating the earlier immutable snapshot.
    checksum = sha256("|".join(
        f"{item.instrument_id}:{item.symbol}:{item.isin or ''}:{item.sector or ''}:{item.industry or ''}:{item.listing_status}:{item.security_type}:{item.exchange}:{item.main_board}"
        for item in ordered
    ).encode()).hexdigest()
    warnings = ("UNIVERSE_SCOPE:NSE_MAIN_BOARD_EQUITY_ONLY",) + (("UNIVERSE_METADATA_PARTIAL",) if len(eligible) != len(ordered) else ())
    return UniverseSnapshot(snapshot_id, as_of, source, len(ordered), len(eligible), len(ordered) - len(eligible), warnings,
                            version, checksum, tuple(item.instrument_id for item in eligible))


def _candidate_from_analysis(job, instrument, stock, score, gate, output, evidence) -> AnalyzedUniverseCandidate:
    rr = _detail_number(next((item for item in output.evaluations if item.canonical_rule_id == 45), None), "r_t1")
    catalyst = next((item.record.result for item in output.evaluations if item.canonical_rule_id == 30), None)
    qualification = "QUALIFIED" if output.completeness is DiagnosticCompleteness.COMPLETE and score.final_score is not None and score.data_confidence is not None and gate.eligibility.value == "EXECUTABLE" else "PARTIAL"
    return AnalyzedUniverseCandidate(
        f"candidate:{job.job_id}:{instrument.instrument_id}", job.job_id, job.universe_snapshot_id, instrument.instrument_id,
        instrument.symbol, f"universe-stock:{stock.symbol}:{stock.data_as_of.isoformat()}", score.id, score.final_score,
        score.data_confidence, Decimal(str(rr)) if rr is not None else None, gate.eligibility.value, instrument.sector,
        catalyst, evidence.freshness, qualification, job.as_of, output.warnings,
        _supportive_sector(output), _has_result(output, 40, "CANDIDATE"), _has_result(output, 43, "CANDIDATE"),
        _eligible_result(output, 46), gate.eligibility.value == "EXECUTABLE", int(_has_result(output, 41, "CANDIDATE")),
    )


class PortfolioUniverseRotationService:
    """Thin snapshot-bound adapter over the existing canonical rotation engine."""
    def __init__(self, *, store: CoreUniverseAnalysisStore, rotation_config: RotationConfig) -> None:
        self._store, self._engine = store, CapitalRotationEngine(rotation_config)

    def evaluate(self, *, portfolio: PortfolioSnapshot, universe: UniverseSnapshot, job: UniverseAnalysisJob,
                 evaluated_at: datetime) -> PortfolioUniverseRotationSnapshot:
        if job.universe_snapshot_id != universe.snapshot_id:
            raise UniverseAnalysisError("Universe job is not bound to the supplied immutable universe snapshot.")
        snapshot_id = f"portfolio-universe:{portfolio.snapshot_id}:{universe.snapshot_id}:{job.as_of.isoformat()}"
        existing = self._store.get_rotation_snapshot(snapshot_id)
        if existing is not None:
            return existing
        if portfolio.as_of_timestamp != job.as_of:
            return self._partial(portfolio, universe, job, "PORTFOLIO_UNIVERSE_AS_OF_MISMATCH", evaluated_at)
        if portfolio.cash.amount is None:
            return self._partial(portfolio, universe, job, "CASH_UNKNOWN", evaluated_at=evaluated_at)
        if job.stage is UniverseAnalysisStage.CANDIDATES_MATERIALIZED:
            self._store.save_job(replace(job, revision=job.revision + 1, stage=UniverseAnalysisStage.ROTATION_COMPARISON))
        candidates = tuple(item for item in self._store.candidates(job.job_id) if item.qualification_status == "QUALIFIED")
        holding_ids = {item.instrument_id for item in portfolio.holdings if item.active}
        candidates = tuple(item for item in candidates if item.instrument_id not in holding_ids and item.instrument_id in universe.instrument_ids)
        holdings, holding_warnings = _rotation_holdings(portfolio, job.as_of)
        if holding_warnings:
            return self._partial(portfolio, universe, job, *holding_warnings, evaluated_at=evaluated_at)
        context = RotationEvaluationContext(
            portfolio.snapshot_id, portfolio.strategy_version or "UNVERSIONED", DIAGNOSTIC_REGISTRY_VERSION,
            "decision-score-v1", "universe-analysis-gates-v1", job.as_of, holdings, portfolio.cash.amount,
            tuple(_rotation_candidate(item) for item in candidates), self._engine.config.friction_model_version,
        )
        evaluation = self._engine.evaluate(context, evaluated_at)
        self._store._save(CoreApiSnapshotFamily.CAPITAL_ROTATION, f"universe-rotation:{evaluation.evaluation_id}", evaluation, evaluated_at)
        coverage = _coverage(job, bool(candidates))
        value = PortfolioUniverseRotationSnapshot(
            snapshot_id, evaluated_at, job.as_of,
            portfolio.snapshot_id, universe.snapshot_id, coverage, universe.total_records, job.eligible_total,
            job.complete_count, job.partial_count, len(candidates), len(holdings), evaluation.evaluation_id,
            tuple(sorted(set(job.warnings + evaluation.warnings + (("OPPORTUNITY_SET_PARTIAL",) if coverage is OpportunityCoverageStatus.PARTIAL else ())))),
        )
        self._store.save_rotation_snapshot(value)
        latest = self._store.get_job(job.job_id)
        if latest is not None and latest.stage is UniverseAnalysisStage.ROTATION_COMPARISON:
            self._store.save_job(replace(latest, revision=latest.revision + 1, stage=UniverseAnalysisStage.COMPLETED))
        return value

    def _partial(self, portfolio, universe, job, *warnings, evaluated_at):
        value = PortfolioUniverseRotationSnapshot(
            f"portfolio-universe:{portfolio.snapshot_id}:{universe.snapshot_id}:{job.as_of.isoformat()}", evaluated_at, job.as_of,
            portfolio.snapshot_id, universe.snapshot_id, OpportunityCoverageStatus.PARTIAL, universe.total_records,
            job.eligible_total, job.complete_count, job.partial_count, 0, 0, None, tuple(sorted(set(job.warnings + tuple(warnings)))),
        )
        self._store.save_rotation_snapshot(value)
        return value


def _rotation_holdings(portfolio: PortfolioSnapshot, as_of: datetime) -> tuple[tuple[RotationHoldingState, ...], tuple[str, ...]]:
    values: list[RotationHoldingState] = []
    warnings: list[str] = []
    for holding in portfolio.holdings:
        if not holding.active:
            continue
        analytics = holding.analytics
        if analytics is None or analytics.as_of_timestamp != as_of or analytics.known_at > as_of:
            warnings.append(f"STALE_OR_MISSING_HOLDING_ANALYSIS:{holding.instrument_id}")
            continue
        values.append(RotationHoldingState(
            holding.instrument_id, as_of, analytics.known_at, analytics.raw_decision_score, analytics.data_confidence,
            analytics.gate_status, holding.sector, None, analytics.trading_thesis, analytics.investment_thesis,
            analytics.invalidation_status, _forward_rr(holding.current_price, analytics.structural_stop, analytics.target_1),
            _forward_rr(holding.current_price, analytics.structural_stop, analytics.target_1),
            portfolio.exposure.position_allocations.get(holding.instrument_id), holding.risk_amount,
            holding.trading_sessions_held, warnings=(), evidence_ids=(analytics.decision_scorecard_id,) if analytics.decision_scorecard_id else (),
        ))
    return tuple(values), tuple(warnings)


def _rotation_candidate(value: AnalyzedUniverseCandidate) -> RotationCandidate:
    # Existing CapitalRotationEngine owns all eligibility thresholds. This adapter
    # only passes frozen facts from the analyzed universe.
    return RotationCandidate(
        value.instrument_id, value.as_of, value.as_of, value.scorecard_id, value.decision_score, "COMPLETE" if value.decision_score is not None else "SCORE_INCOMPLETE",
        value.confidence, f"gate:{value.candidate_id}" if value.execution_eligibility else None, value.execution_eligibility,
        value.sector, value.sector_supportive, None, None, None, value.risk_reward,
        value.entry_valid, value.stop_valid, value.invalidation_valid, value.catalyst_context, value.warnings, False, None, value.portfolio_constraints_ok, False, None, None, value.confirmation_count,
    )


def _forward_rr(price, stop, target):
    if price is None or stop is None or target is None or price <= stop:
        return None
    return (target - price) / (price - stop)


def _coverage(job: UniverseAnalysisJob, _candidates_materialized: bool) -> OpportunityCoverageStatus:
    materialized = job.stage in {UniverseAnalysisStage.CANDIDATES_MATERIALIZED, UniverseAnalysisStage.ROTATION_COMPARISON, UniverseAnalysisStage.COMPLETED}
    return OpportunityCoverageStatus.FULL if materialized and job.status is UniverseAnalysisJobStatus.COMPLETED and not job.partial_count and not job.unavailable_count and not job.failed_count else OpportunityCoverageStatus.PARTIAL if job.processed else OpportunityCoverageStatus.UNAVAILABLE


def _eligible_result(output: DiagnosticRun, rule_id: int) -> bool:
    item = next((value for value in output.evaluations if value.canonical_rule_id == rule_id), None)
    return item is not None and item.eligibility is EvaluationEligibility.ELIGIBLE


def _supportive_sector(output: DiagnosticRun) -> bool:
    value = next((item for item in output.evaluations if item.canonical_rule_id == 2), None)
    return value is not None and value.eligibility is EvaluationEligibility.ELIGIBLE and value.record.result in {"STRONG", "HEALTHY"}


def _has_result(output: DiagnosticRun, rule_id: int, result: str) -> bool:
    item = next((value for value in output.evaluations if value.canonical_rule_id == rule_id), None)
    return item is not None and item.eligibility is EvaluationEligibility.ELIGIBLE and item.record.result == result
