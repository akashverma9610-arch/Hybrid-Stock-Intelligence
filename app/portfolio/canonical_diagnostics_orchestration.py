"""Narrow stored-evidence orchestration for canonical portfolio diagnostics.

This module deliberately composes existing acquisition/read boundaries, the
registry-wide diagnostic runner, the governance diagnostic store, Shared Brain,
and the existing holding-intelligence/sell-side contracts.  It owns no rule,
score, provider, or portfolio mutation semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Protocol

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.diagnostics.brain_lineage import require_v1_stored_diagnostic
from app.data_operations.models import EvidenceRefreshOutcome, EvidenceRefreshRequest
from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticStrategyDefinition, governance_limitations_fingerprint,
)
from app.domain.models import DiagnosticResult, StrategyVersionReference, canonical_diagnostic_result
from app.intelligence.shared_brain_application import SharedBrainApplicationError, SharedBrainAnalysisView
from app.intelligence.unified_state import BrainOutputContext
from app.portfolio.holding_intelligence import HoldingIntelligenceComposition, compose_holding_intelligence
from app.portfolio.models import PortfolioHolding, PortfolioSnapshot
from app.portfolio.sell_side_runtime import (
    PortfolioSellSideDecision, PortfolioSellSideDecisionAuditService,
    PortfolioSellSideInput, evaluate_portfolio_sell_side_action,
)
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.storage.governance_repository import StrategyGovernanceRepository
from app.universe_analysis.models import DiagnosticCompleteness, NseEquityInstrument
from app.universe_analysis.service import (
    Canonical61DiagnosticRunner, CoreUniverseAnalysisStore, StockDiagnosticInputAssembler,
)


PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS = (
    "NSE:INE372A01015", "NSE:INE0FHS01024", "NSE:INE955D01029",
    "NSE:INE068V01023", "NSE:INE090A01021",
)
MINIMUM_COMPARABLE_THESIS_RULE_IDS = (16, 17, 18, 19, 23, 43, 45, 46)
INVALIDATION_RULE_IDS = (46,)


class SharedBrainReader(Protocol):
    def analyze_stock(
        self, identifier: str, *, context: BrainOutputContext, as_of: datetime | None = None,
    ) -> SharedBrainAnalysisView: ...


class TargetedOhlcvRefreshJob(Protocol):
    """Existing provider-governed targeted refresh seam."""

    def refresh_selected(
        self, request: EvidenceRefreshRequest, *, canonical_instrument_ids: frozenset[str] | None,
    ) -> EvidenceRefreshOutcome: ...


@dataclass(frozen=True, slots=True)
class CanonicalDiagnosticHoldingRun:
    instrument_id: str
    evaluated_rule_ids: tuple[int, ...]
    blocked_rule_ids: tuple[int, ...]
    persisted_diagnostic_ids: tuple[str, ...]
    diagnostic_completeness: DiagnosticCompleteness | None
    shared_brain_status: str | None
    composition: HoldingIntelligenceComposition | None
    sell_side_decision: PortfolioSellSideDecision | None
    blockers: tuple[str, ...]
    latest_completed_market_session: datetime | None = None


@dataclass(frozen=True, slots=True)
class CanonicalDiagnosticsOrchestrationRun:
    portfolio_snapshot_id: str
    portfolio_snapshot_as_of: datetime
    intelligence_as_of: datetime
    latest_completed_market_session: datetime | None
    canonical_instrument_ids: tuple[str, ...]
    strategy_version: StrategyVersionReference
    holdings: tuple[CanonicalDiagnosticHoldingRun, ...]
    blockers: tuple[str, ...]

    @property
    def as_of(self) -> datetime:
        """Backward-compatible alias for the evidence cutoff.

        New callers must use ``portfolio_snapshot_as_of`` and
        ``intelligence_as_of`` explicitly; keeping this read-only alias avoids
        breaking existing in-process consumers while the service contract
        makes the two time axes unambiguous.
        """
        return self.intelligence_as_of


class CanonicalPortfolioDiagnosticsOrchestrator:
    """Run one exact holding set using stored evidence and append-only diagnostics.

    A registered strategy version is deliberately mandatory: the governance
    repository rejects otherwise-unanchored diagnostic records.  This is a
    policy boundary, not something an orchestration command can create.
    """

    def __init__(
        self,
        *,
        universe: CoreUniverseAnalysisStore,
        assembler: StockDiagnosticInputAssembler,
        runner: Canonical61DiagnosticRunner,
        governance: StrategyGovernanceRepository,
        shared_brain: SharedBrainReader,
        sell_side_audits: PortfolioSellSideDecisionAuditService | None = None,
    ) -> None:
        self._universe = universe
        self._assembler = assembler
        self._runner = runner
        self._governance = governance
        self._shared_brain = shared_brain
        self._sell_side_audits = sell_side_audits

    def run(
        self,
        *,
        portfolio_snapshot: PortfolioSnapshot,
        canonical_instrument_ids: tuple[str, ...],
        strategy_version: StrategyVersionReference,
        intelligence_as_of: datetime | None = None,
    ) -> CanonicalDiagnosticsOrchestrationRun:
        targets = _validated_targets(portfolio_snapshot, canonical_instrument_ids)
        snapshot_as_of = portfolio_snapshot.as_of_timestamp
        as_of = intelligence_as_of or snapshot_as_of
        _require_aware(as_of, "INTELLIGENCE_AS_OF_TIMEZONE_REQUIRED")
        if as_of < snapshot_as_of:
            raise ValueError("INTELLIGENCE_AS_OF_BEFORE_PORTFOLIO_SNAPSHOT")
        try:
            definition = self._runner.authorize(self._governance)
        except ValueError:
            blocker = "CANONICAL_DIAGNOSTIC_RUNNER_UNAUTHORIZED"
            return _orchestration_run(
                portfolio_snapshot, as_of, targets, strategy_version,
                tuple(_blocked_holding(item.instrument_id, blocker) for item in _target_holdings(portfolio_snapshot, targets)),
                (blocker,),
            )
        if strategy_version != definition.reference:
            blocker = "CANONICAL_DIAGNOSTIC_STRATEGY_MISMATCH"
            return _orchestration_run(
                portfolio_snapshot, as_of, targets, strategy_version,
                tuple(_blocked_holding(item.instrument_id, blocker) for item in _target_holdings(portfolio_snapshot, targets)),
                (blocker,),
            )

        known_instruments = {item.instrument_id: item for item in self._universe.instruments_as_of(as_of)}
        results: list[CanonicalDiagnosticHoldingRun] = []
        for holding in _target_holdings(portfolio_snapshot, targets):
            instrument = known_instruments.get(holding.instrument_id)
            if instrument is None:
                results.append(_blocked_holding(holding.instrument_id, "CANONICAL_INSTRUMENT_NOT_AVAILABLE_AT_AS_OF"))
                continue
            results.append(self._run_holding(holding, instrument, portfolio_snapshot, as_of, strategy_version, definition))
        blockers = tuple(sorted({code for item in results for code in item.blockers}))
        return _orchestration_run(portfolio_snapshot, as_of, targets, strategy_version, tuple(results), blockers)

    def _run_holding(
        self,
        holding: PortfolioHolding,
        instrument: NseEquityInstrument,
        portfolio_snapshot: PortfolioSnapshot,
        intelligence_as_of: datetime,
        strategy_version: StrategyVersionReference,
        definition: CanonicalDiagnosticStrategyDefinition,
    ) -> CanonicalDiagnosticHoldingRun:
        evidence = self._assembler.assemble(instrument, intelligence_as_of)
        latest_session = _latest_completed_market_session(evidence, holding.instrument_id)
        run = self._runner.run(evidence, governance=self._governance)
        records = _canonical_result_records(tuple(item.record for item in run.evaluations), definition)
        if any(item.strategy_version != strategy_version for item in records):
            return _blocked_holding(holding.instrument_id, "CANONICAL_DIAGNOSTIC_STRATEGY_MISMATCH")
        persisted = _persist_idempotently(self._governance, strategy_version, intelligence_as_of, records)
        diagnostics = rehydrate_persisted_canonical_diagnostics(
            persisted, instrument_id=holding.instrument_id, as_of=intelligence_as_of,
        )
        evaluated = tuple(item.canonical_rule_id for item in diagnostics if item.eligibility is EvaluationEligibility.ELIGIBLE)
        blocked = tuple(item.canonical_rule_id for item in diagnostics if item.eligibility is not EvaluationEligibility.ELIGIBLE)
        try:
            brain = self._shared_brain.analyze_stock(
                holding.instrument_id, context=BrainOutputContext.SELL_TRIM_REVIEW,
                as_of=intelligence_as_of,
            )
        except SharedBrainApplicationError as error:
            return CanonicalDiagnosticHoldingRun(
                holding.instrument_id, evaluated, blocked, tuple(item.id for item in persisted), run.completeness,
                None, None, None, (error.code,), latest_session,
            )
        composition = compose_holding_intelligence(
            holding=holding, portfolio_snapshot=portfolio_snapshot, shared_brain=brain, diagnostics=diagnostics,
            intelligence_as_of=intelligence_as_of,
        )
        decision = evaluate_portfolio_sell_side_action(PortfolioSellSideInput(
            portfolio_snapshot, replace(holding, analytics=composition.analytics),
            None, composition.shared_brain_fingerprint, composition.evidence_conflicted, composition.evidence_comparable,
            intelligence_as_of=intelligence_as_of, latest_completed_market_session=latest_session,
        ))
        if self._sell_side_audits is not None:
            decision = self._sell_side_audits.persist(decision)
        return CanonicalDiagnosticHoldingRun(
            holding.instrument_id, evaluated, blocked, tuple(item.id for item in persisted), run.completeness,
            brain.evidence_status, composition, decision, composition.blockers, latest_session,
        )


def rehydrate_persisted_canonical_diagnostics(
    records: tuple[DiagnosticResult, ...], *, instrument_id: str, as_of: datetime,
) -> tuple[EvaluatedDiagnostic, ...]:
    """Recover the runner's durable eligible/missing distinction without new semantics.

    The existing immutable ``DiagnosticResult`` schema stores the canonical
    output, but not the transient wrapper enum.  The canonical runner emits
    ``INSUFFICIENT_DATA`` exclusively through its missing-input path; preserve
    that existing vocabulary as ineligible and retain all other stored outputs
    as eligible.  Future records are excluded before any synthesis consumer.
    """
    values = []
    for record in records:
        require_v1_stored_diagnostic(record)
        if record.instrument_id != instrument_id or record.as_of_timestamp > as_of or record.evaluated_at > as_of:
            continue
        try:
            rule_id = int(record.rule_id)
        except ValueError:
            continue
        eligibility = (
            EvaluationEligibility.INELIGIBLE_MISSING_DATA
            if record.result == "INSUFFICIENT_DATA" else EvaluationEligibility.ELIGIBLE
        )
        values.append(EvaluatedDiagnostic(record, rule_id, DIAGNOSTIC_REGISTRY_VERSION, eligibility, (), ()))
    return tuple(sorted(values, key=lambda item: (item.canonical_rule_id, item.record.id)))


def refresh_targeted_holding_ohlcv(
    *,
    job: TargetedOhlcvRefreshJob,
    request: EvidenceRefreshRequest,
    portfolio_snapshot: PortfolioSnapshot,
    canonical_instrument_ids: tuple[str, ...],
) -> EvidenceRefreshOutcome:
    """Delegate exact holding IDs to the existing provider/version/conflict job.

    Instrument resolution, provider mapping capture, provider-versioned bar
    writes, and immutable conflict handling remain exclusively inside
    ``UpstoxOhlcvRefreshJob.refresh_selected``.
    """
    targets = _validated_targets(portfolio_snapshot, canonical_instrument_ids)
    return job.refresh_selected(request, canonical_instrument_ids=frozenset(targets))


def _persist_idempotently(
    governance: StrategyGovernanceRepository,
    strategy_version: StrategyVersionReference,
    as_of: datetime,
    records: tuple[DiagnosticResult, ...],
) -> tuple[DiagnosticResult, ...]:
    existing = {item.id: item for item in governance.list_diagnostic_results(strategy_version, as_of)}
    for record in records:
        if record.as_of_timestamp > as_of or record.evaluated_at > as_of:
            raise ValueError("CANONICAL_DIAGNOSTIC_FUTURE_RECORD_REJECTED")
        prior = existing.get(record.id)
        if prior is None:
            governance.save_diagnostic_result(record)
        elif prior != record:
            raise ValueError("CANONICAL_DIAGNOSTIC_IMMUTABILITY_CONFLICT")
    return tuple(
        item for item in governance.list_diagnostic_results(strategy_version, as_of)
        if item.id in {record.id for record in records}
    )


def _canonical_result_records(
    records: tuple[DiagnosticResult, ...],
    definition: CanonicalDiagnosticStrategyDefinition,
) -> tuple[DiagnosticResult, ...]:
    """Attach the exact approved definition lineage without changing rule output."""
    limitations_fingerprint = governance_limitations_fingerprint(definition.governance_limitations)
    values = []
    for record in records:
        if record.strategy_version != definition.reference:
            raise ValueError("CANONICAL_DIAGNOSTIC_STRATEGY_MISMATCH")
        values.append(canonical_diagnostic_result(
            id=record.id, instrument_id=record.instrument_id, rule_id=record.rule_id,
            strategy_version=record.strategy_version,
            canonical_strategy_fingerprint=definition.semantic_fingerprint,
            canonical_limitations_fingerprint=limitations_fingerprint,
            result=record.result, score=record.score, confidence=record.confidence,
            evidence_ids=record.evidence_ids, input_observation_ids=record.input_observation_ids,
            evaluated_at=record.evaluated_at, as_of_timestamp=record.as_of_timestamp,
        ))
    return tuple(values)


def _validated_targets(snapshot: PortfolioSnapshot, values: tuple[str, ...]) -> tuple[str, ...]:
    if not values or len(values) != len(set(values)):
        raise ValueError("CANONICAL_DIAGNOSTIC_TARGETS_INVALID")
    targets = tuple(values)
    holdings = {item.instrument_id for item in snapshot.holdings}
    if not set(targets) <= holdings:
        raise ValueError("CANONICAL_DIAGNOSTIC_TARGET_NOT_IN_PORTFOLIO")
    return targets


def _target_holdings(snapshot: PortfolioSnapshot, targets: tuple[str, ...]) -> tuple[PortfolioHolding, ...]:
    by_id = {item.instrument_id: item for item in snapshot.holdings}
    return tuple(by_id[item] for item in targets)


def _blocked_holding(instrument_id: str, blocker: str) -> CanonicalDiagnosticHoldingRun:
    return CanonicalDiagnosticHoldingRun(instrument_id, (), (), (), None, None, None, None, (blocker,))


def _orchestration_run(
    portfolio_snapshot: PortfolioSnapshot,
    intelligence_as_of: datetime,
    targets: tuple[str, ...],
    strategy_version: StrategyVersionReference,
    holdings: tuple[CanonicalDiagnosticHoldingRun, ...],
    blockers: tuple[str, ...],
) -> CanonicalDiagnosticsOrchestrationRun:
    sessions = tuple(item.latest_completed_market_session for item in holdings)
    # A portfolio-level market cutoff is meaningful only when every requested
    # holding has a completed stored daily session.  The earliest such session
    # is the conservative common boundary; never substitute a later bar.
    common_session = min(sessions) if sessions and all(item is not None for item in sessions) else None
    return CanonicalDiagnosticsOrchestrationRun(
        portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
        portfolio_snapshot_as_of=portfolio_snapshot.as_of_timestamp,
        intelligence_as_of=intelligence_as_of,
        latest_completed_market_session=common_session,
        canonical_instrument_ids=targets,
        strategy_version=strategy_version,
        holdings=holdings,
        blockers=blockers,
    )


def _latest_completed_market_session(evidence, instrument_id: str) -> datetime | None:
    """Return only the latest stored price-bar session already admitted by PIT."""
    values = tuple(
        item.provenance.market_timestamp for item in evidence.snapshot.observations
        if item.instrument.id == instrument_id and getattr(item.kind, "value", item.kind) == "price_bar"
        and isinstance(item.provenance.market_timestamp, datetime)
    )
    return max(values) if values else None


def _require_aware(value: datetime, error: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(error)


__all__ = (
    "CanonicalDiagnosticHoldingRun", "CanonicalDiagnosticsOrchestrationRun",
    "CanonicalPortfolioDiagnosticsOrchestrator", "INVALIDATION_RULE_IDS",
    "MINIMUM_COMPARABLE_THESIS_RULE_IDS", "PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS",
    "refresh_targeted_holding_ohlcv", "rehydrate_persisted_canonical_diagnostics",
)
