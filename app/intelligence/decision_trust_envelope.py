"""Deterministic, stored-evidence Decision Trust Envelope v1.

This module is deliberately a read-model composer. It does not calculate a
score, create a setup, evaluate gates, or derive a recommendation. Every
non-Brain value is copied only from an already-persisted canonical artifact.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING, Protocol

from app.historical.guard import manifest_fingerprint
from app.intelligence.shared_brain_application import SharedBrainAnalysisView

if TYPE_CHECKING:
    from app.portfolio.canonical_decision_score import CanonicalDecisionScorecard
    from app.portfolio.canonical_six_gates import CanonicalExecutionGateEvaluation
    from app.portfolio.holding_intelligence import HoldingIntelligenceComposition
    from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity


ENVELOPE_VERSION = "decision-trust-envelope/v1"


class LiveMarketStateRead(Protocol):
    """Minimal provider-neutral live display context; no transport is exposed."""

    ltp: Decimal
    received_at: datetime
    freshness: object


@dataclass(frozen=True, slots=True)
class DecisionTrustDomain:
    """One exact Unified Intelligence State evidence reference."""

    domain: str
    availability: str
    freshness: str
    evidence_as_of: datetime | None
    observed_at: datetime | None
    artifact_ids: tuple[str, ...]
    artifact_fingerprints: tuple[str, ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionScoreTrust:
    state: str
    value: Decimal | None
    artifact_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    score_as_of: datetime | None
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SetupTrust:
    state: str
    setup_id: str | None
    setup_as_of: datetime | None
    setup_type: str | None
    entry: Decimal | None
    structural_invalidation: Decimal | None
    target_1: Decimal | None
    target_2: Decimal | None
    extended_target: Decimal | None
    risk_reward: Decimal | None
    maximum_executable_entry: Decimal | None
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SixGatesTrust:
    state: str
    evaluation_id: str | None
    policy_id: str | None
    policy_version: str | None
    policy_fingerprint: str | None
    evaluation_as_of: datetime | None
    aggregate_state: str | None
    gate_results: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ThesisTrust:
    trading_thesis: str | None
    investment_thesis: str | None
    invalidation_status: str | None
    structural_invalidation: Decimal | None
    source_as_of: datetime | None
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LiveMarketContext:
    ltp: Decimal | None
    received_at: datetime | None
    freshness: str | None


@dataclass(frozen=True, slots=True)
class DecisionTrustEnvelope:
    version: str
    canonical_instrument_id: str
    symbol: str
    intelligence_as_of: datetime
    latest_completed_market_session: datetime | None
    shared_brain_state: str
    domains: tuple[DecisionTrustDomain, ...]
    coverage_count: int
    coverage_total: int
    coverage_pct: Decimal
    missing_domains: tuple[str, ...]
    blockers: tuple[str, ...]
    decision_readiness: str
    decision_score: DecisionScoreTrust
    setup: SetupTrust
    six_gates: SixGatesTrust
    thesis: ThesisTrust
    live_market: LiveMarketContext
    fingerprint: str


def decision_trust_envelope_from_shared_brain(
    value: SharedBrainAnalysisView,
    *,
    decision_scorecard: CanonicalDecisionScorecard | None = None,
    setup_opportunity: CanonicalSetupOpportunity | None = None,
    six_gates_evaluation: CanonicalExecutionGateEvaluation | None = None,
    six_gates_policy: object | None = None,
    holding_intelligence: HoldingIntelligenceComposition | None = None,
    live_market_state: LiveMarketStateRead | None = None,
) -> DecisionTrustEnvelope:
    """Copy compatible persisted state into a deterministic UI-safe contract."""
    domains = tuple(_domain(item) for item in value.evidence_references)
    available = tuple(item.domain for item in domains if item.availability == "AVAILABLE")
    missing = tuple(item.domain for item in domains if item.availability != "AVAILABLE")
    total = len(domains)
    coverage_pct = (
        (Decimal(len(available)) * Decimal("100") / Decimal(total)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        )
        if total else Decimal("0")
    )
    score = _score(decision_scorecard)
    setup = _setup(setup_opportunity)
    gates = _gates(six_gates_evaluation, six_gates_policy)
    thesis = _thesis(holding_intelligence, setup)
    live = _live(live_market_state)
    latest_session = None if decision_scorecard is None else decision_scorecard.latest_completed_market_session
    blockers = tuple(sorted({
        *value.blockers,
        *score.blockers,
        *setup.blockers,
        *gates.blockers,
        *thesis.blockers,
        *(f"{item.domain}:{blocker}" for item in domains for blocker in item.blockers),
    }))
    fields = dict(
        version=ENVELOPE_VERSION,
        canonical_instrument_id=value.canonical_instrument_id,
        symbol=value.symbol,
        intelligence_as_of=value.as_of,
        latest_completed_market_session=latest_session,
        shared_brain_state=value.evidence_status,
        domains=domains,
        coverage_count=len(available),
        coverage_total=total,
        coverage_pct=coverage_pct,
        missing_domains=missing,
        blockers=blockers,
        decision_readiness="DECISION_READINESS_UNRESOLVED",
        decision_score=score,
        setup=setup,
        six_gates=gates,
        thesis=thesis,
        live_market=live,
    )
    return DecisionTrustEnvelope(**fields, fingerprint=manifest_fingerprint(**fields))


def _domain(value) -> DecisionTrustDomain:
    return DecisionTrustDomain(
        domain=value.domain.value,
        availability=value.availability.value,
        freshness=value.freshness_status.value,
        evidence_as_of=value.evidence_as_of,
        observed_at=value.observed_at,
        artifact_ids=value.artifact_ids,
        artifact_fingerprints=value.artifact_fingerprints,
        blockers=value.warnings,
    )


def _score(value: CanonicalDecisionScorecard | None) -> DecisionScoreTrust:
    if value is None:
        return DecisionScoreTrust("UNSCORED", None, None, None, None, None, ("DECISION_SCORE_NOT_YET_COMPUTED",))
    return DecisionScoreTrust(
        value.score_status,
        value.final_score,
        value.id,
        value.scoring_policy_version,
        value.scoring_policy_fingerprint,
        value.as_of_timestamp,
        value.warnings,
    )


def _setup(value: CanonicalSetupOpportunity | None) -> SetupTrust:
    if value is None:
        return SetupTrust(
            "NO_CURRENT_SETUP", None, None, None, None, None, None, None, None, None, None,
            ("NO_CURRENT_EXECUTABLE_SETUP",),
        )
    candidate = value.candidate
    return SetupTrust(
        "CURRENT_SETUP_READY",
        value.opportunity_id,
        value.decision_as_of,
        candidate.strategy_family.value,
        candidate.breakout_confirmation_trigger,
        candidate.final_structural_stop,
        candidate.measured_move_target,
        None,
        None,
        candidate.reference_reward_risk,
        candidate.maximum_executable_entry_price,
        candidate.warnings,
    )


def _gates(value: CanonicalExecutionGateEvaluation | None, policy: object | None) -> SixGatesTrust:
    policy_id = getattr(policy, "policy_id", None)
    policy_version = getattr(policy, "version", None)
    policy_fingerprint = getattr(policy, "fingerprint", None)
    if value is None:
        return SixGatesTrust(
            "NOT_EVALUATED", None, policy_id, policy_version, policy_fingerprint, None, None, (),
            ("SIX_GATES_NOT_YET_COMPUTED",),
        )
    evaluation = value.evaluation
    return SixGatesTrust(
        "EVALUATED",
        evaluation.id,
        policy_id,
        policy_version,
        policy_fingerprint,
        evaluation.as_of_timestamp,
        evaluation.eligibility.value,
        tuple(sorted((item.gate_id, item.outcome.value) for item in evaluation.decisions)),
        tuple(sorted(set(evaluation.failed_gate_ids + evaluation.insufficient_gate_ids + evaluation.warnings))),
    )


def _thesis(value: HoldingIntelligenceComposition | None, setup: SetupTrust) -> ThesisTrust:
    if value is None:
        return ThesisTrust(None, None, None, setup.structural_invalidation, None, ("HOLDING_INTELLIGENCE_NOT_AVAILABLE",))
    analytics = value.analytics
    return ThesisTrust(
        analytics.trading_thesis,
        analytics.investment_thesis,
        analytics.invalidation_status,
        setup.structural_invalidation,
        analytics.as_of_timestamp,
        value.blockers,
    )


def _live(value: LiveMarketStateRead | None) -> LiveMarketContext:
    if value is None:
        return LiveMarketContext(None, None, None)
    return LiveMarketContext(value.ltp, value.received_at, value.freshness.value)


__all__ = (
    "DecisionScoreTrust", "DecisionTrustDomain", "DecisionTrustEnvelope", "ENVELOPE_VERSION",
    "LiveMarketContext", "SetupTrust", "SixGatesTrust", "ThesisTrust",
    "decision_trust_envelope_from_shared_brain",
)
