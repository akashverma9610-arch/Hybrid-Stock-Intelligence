"""Pure Shared-Brain-to-portfolio holding intelligence composition.

This is deliberately an adapter, not another Brain, scorer, or thesis model.
It carries only the existing synthesis results required by the sell-side thesis
evaluator and preserves their immutable input lineage for audit/rebuild.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.diagnostics.brain_lineage import CROSS_PORTFOLIO, require_production_evidence
from app.diagnostics.downstream import active_v1_rejection
from app.diagnostics.synthesis import HigherOrderDiagnosticContext, SynthesisRules, investment_thesis, risk, trading_thesis
from app.historical.guard import manifest_fingerprint
from app.intelligence.shared_brain_application import SharedBrainAnalysisView
from app.portfolio.models import HoldingAnalytics, PortfolioHolding, PortfolioSnapshot
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION


COMPOSITION_POLICY_ID = "portfolio-holding-intelligence-composition"
COMPOSITION_POLICY_VERSION = "v1"
COMPOSITION_POLICY_FINGERPRINT = manifest_fingerprint(
    policy_id=COMPOSITION_POLICY_ID,
    version=COMPOSITION_POLICY_VERSION,
    source="shared-brain-exact-as-of-and-existing-higher-order-diagnostics",
    fields=("risk_state", "trading_thesis", "investment_thesis", "invalidation_status"),
)


@dataclass(frozen=True, slots=True)
class HoldingIntelligenceComposition:
    """Derived holding analytics and the exact non-canonical inputs that produced it."""

    analytics: HoldingAnalytics
    portfolio_snapshot_id: str
    portfolio_snapshot_as_of: datetime
    intelligence_as_of: datetime
    shared_brain_fingerprint: str
    shared_brain_context_fingerprint: str
    composition_policy_id: str
    composition_policy_version: str
    composition_policy_fingerprint: str
    diagnostic_ids: tuple[str, ...]
    evidence_fingerprints: tuple[str, ...]
    populated_fields: tuple[str, ...]
    unavailable_fields: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence_comparable: bool
    evidence_conflicted: bool
    fingerprint: str


def compose_holding_intelligence(
    *,
    holding: PortfolioHolding,
    portfolio_snapshot: PortfolioSnapshot,
    shared_brain: SharedBrainAnalysisView,
    diagnostics: tuple[EvaluatedDiagnostic, ...] = (),
    intelligence_as_of: datetime | None = None,
) -> HoldingIntelligenceComposition:
    """Compose existing thesis semantics without inferring any new thesis state.

    Shared Brain must be exact-as-of, complete, and non-conflicted.  Supplied
    diagnostics are independently PIT-filtered before the existing higher-order
    synthesis functions are reused.  P&L, cost, valuation, and forward-paper
    intelligence are intentionally never inspected.
    """
    require_production_evidence(shared_brain)
    if any(active_v1_rejection(item, DIAGNOSTIC_REGISTRY_VERSION) for item in diagnostics):
        raise ValueError(CROSS_PORTFOLIO)
    if not any(item.holding_id == holding.holding_id and item.instrument_id == holding.instrument_id for item in portfolio_snapshot.holdings):
        raise ValueError("HOLDING_INTELLIGENCE_HOLDING_NOT_IN_PORTFOLIO")
    if shared_brain.canonical_instrument_id != holding.instrument_id:
        raise ValueError("HOLDING_INTELLIGENCE_INSTRUMENT_MISMATCH")

    as_of = intelligence_as_of or portfolio_snapshot.as_of_timestamp
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("HOLDING_INTELLIGENCE_AS_OF_TIMEZONE_REQUIRED")
    if as_of < portfolio_snapshot.as_of_timestamp:
        raise ValueError("HOLDING_INTELLIGENCE_AS_OF_BEFORE_PORTFOLIO_SNAPSHOT")
    blockers: set[str] = set()
    if shared_brain.as_of != as_of:
        blockers.add("SHARED_BRAIN_AS_OF_MISMATCH")
    if shared_brain.evidence_status != "COMPLETE":
        blockers.add("SHARED_BRAIN_EVIDENCE_INCOMPLETE")
    availability = {domain: state for domain, state in shared_brain.evidence_domains}
    conflicted = any(state == "CONFLICTED" for state in availability.values())
    if conflicted:
        blockers.add("SHARED_BRAIN_EVIDENCE_CONFLICTED")

    eligible = tuple(sorted((
        item for item in diagnostics
        if item.record.instrument_id == holding.instrument_id
        and item.eligibility is EvaluationEligibility.ELIGIBLE
        and item.record.as_of_timestamp <= as_of
        and item.record.evaluated_at <= as_of
    ), key=lambda item: (item.canonical_rule_id, item.record.id)))
    excluded_future = any(
        item.record.instrument_id == holding.instrument_id
        and (item.record.as_of_timestamp > as_of or item.record.evaluated_at > as_of)
        for item in diagnostics
    )
    if excluded_future:
        blockers.add("FUTURE_DIAGNOSTIC_EXCLUDED")
    if not eligible:
        blockers.add("GOVERNED_DIAGNOSTICS_UNAVAILABLE")

    comparable = not blockers
    populated: tuple[str, ...] = ()
    unavailable = ("risk_state", "trading_thesis", "investment_thesis", "invalidation_status")
    risk_state = trading = investment = invalidation = None
    if comparable:
        strategy = eligible[0].record.strategy_version
        context = HigherOrderDiagnosticContext(
            as_of, strategy, DIAGNOSTIC_REGISTRY_VERSION, eligible, SynthesisRules().version,
        )
        risk_state = risk(context, SynthesisRules()).state
        trading = trading_thesis(context, SynthesisRules()).state
        investment = investment_thesis(context, SynthesisRules()).state
        by_rule = context.by_rule
        invalidation = "TRIGGERED" if by_rule.get(46) and by_rule[46].record.result == "TRIGGERED" else None
        # Existing synthesis reports INSUFFICIENT_DATA rather than a usable
        # sell-side thesis when required diagnostics are absent.
        if trading == "INSUFFICIENT_DATA":
            trading = None
        if investment == "INSUFFICIENT_DATA":
            investment = None
        populated = tuple(field for field, value in (
            ("risk_state", risk_state), ("trading_thesis", trading),
            ("investment_thesis", investment), ("invalidation_status", invalidation),
        ) if value is not None)
        unavailable = tuple(field for field in unavailable if field not in populated)

    known_at = max((item.record.evaluated_at for item in eligible), default=as_of)
    analytics = HoldingAnalytics(
        instrument_id=holding.instrument_id, as_of_timestamp=as_of, known_at=known_at,
        diagnostic_ids=tuple(item.record.id for item in eligible), risk_state=risk_state,
        trading_thesis=trading, investment_thesis=investment, invalidation_status=invalidation,
    )
    evidence = tuple(sorted((
        shared_brain.snapshot_fingerprint, shared_brain.context_projection_fingerprint,
        shared_brain.unified_state_fingerprint, shared_brain.brain_research_state_v2_fingerprint,
        shared_brain.financial_semantic_section_fingerprint,
        *(item.record.id for item in eligible),
    )))
    values = dict(
        portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
        holding_id=holding.holding_id,
        instrument_id=holding.instrument_id,
        portfolio_snapshot_as_of=portfolio_snapshot.as_of_timestamp.isoformat(),
        intelligence_as_of=as_of.isoformat(),
        shared_brain_fingerprint=shared_brain.snapshot_fingerprint,
        shared_brain_context_fingerprint=shared_brain.context_projection_fingerprint,
        policy_fingerprint=COMPOSITION_POLICY_FINGERPRINT,
        diagnostic_ids=analytics.diagnostic_ids,
        evidence_fingerprints=evidence,
        populated_fields=populated, unavailable_fields=unavailable,
        blockers=tuple(sorted(blockers)), evidence_comparable=comparable,
        evidence_conflicted=conflicted,
    )
    return HoldingIntelligenceComposition(
        analytics=analytics, portfolio_snapshot_id=portfolio_snapshot.snapshot_id,
        portfolio_snapshot_as_of=portfolio_snapshot.as_of_timestamp,
        intelligence_as_of=as_of,
        shared_brain_fingerprint=shared_brain.snapshot_fingerprint,
        shared_brain_context_fingerprint=shared_brain.context_projection_fingerprint,
        composition_policy_id=COMPOSITION_POLICY_ID,
        composition_policy_version=COMPOSITION_POLICY_VERSION,
        composition_policy_fingerprint=COMPOSITION_POLICY_FINGERPRINT,
        diagnostic_ids=analytics.diagnostic_ids, evidence_fingerprints=evidence,
        populated_fields=populated, unavailable_fields=unavailable,
        blockers=tuple(sorted(blockers)), evidence_comparable=comparable,
        evidence_conflicted=conflicted,
        fingerprint=manifest_fingerprint(**values),
    )
