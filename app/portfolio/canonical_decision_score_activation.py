"""Stored-only activation of the approved Decision Score for five holdings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.canonical_diagnostic_strategy import (
    CANONICAL_61_STRATEGY_REFERENCE,
    require_canonical_61_runner_authorization,
)
from app.market_data.models import Timeframe
from app.portfolio.canonical_decision_score import (
    CanonicalDecisionScorecard, canonical_decision_scorecard_from,
)
from app.portfolio.canonical_diagnostics_orchestration import (
    PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
    rehydrate_persisted_canonical_diagnostics,
)
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, SCORING_POLICY, get_diagnostic_rule
from app.scoring.engine import build_scorecard


class _CanonicalDecisionScoreRepository(Protocol):
    def get_canonical_diagnostic_strategy_definition(self, reference): ...
    def latest_common_canonical_diagnostic_as_of(self, reference, instrument_ids: tuple[str, ...]) -> datetime | None: ...
    def list_diagnostic_results(self, reference, as_of_timestamp: datetime): ...
    def get_canonical_decision_scorecard(self, value_id: str) -> CanonicalDecisionScorecard | None: ...
    def save_canonical_decision_scorecard(self, value: CanonicalDecisionScorecard) -> CanonicalDecisionScorecard: ...


class _HistoricalBars(Protocol):
    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None): ...


@dataclass(frozen=True, slots=True)
class DecisionScoreBlocker:
    rule_id: int
    rule_name: str
    required_inputs: tuple[str, ...]
    upstream_domain: str


@dataclass(frozen=True, slots=True)
class CanonicalDecisionScoreActivationOutcome:
    instrument_id: str
    status: str
    score_id: str | None
    final_score: object | None
    artifact_fingerprint: str | None
    latest_completed_market_session: datetime | None
    blockers: tuple[DecisionScoreBlocker, ...]


@dataclass(frozen=True, slots=True)
class CanonicalDecisionScoreActivationRun:
    intelligence_as_of: datetime
    outcomes: tuple[CanonicalDecisionScoreActivationOutcome, ...]


class CanonicalPortfolioDecisionScoreActivator:
    """Rehydrate persisted Canonical 61 outputs; never rerun diagnostics or gates."""

    def __init__(self, *, governance: _CanonicalDecisionScoreRepository, historical: _HistoricalBars) -> None:
        self._governance = governance
        self._historical = historical

    def materialize(
        self, *, instrument_ids: tuple[str, ...] = PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS,
    ) -> CanonicalDecisionScoreActivationRun:
        if instrument_ids != PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS:
            raise ValueError("DECISION_SCORE_ACTIVATION_REQUIRES_EXACT_PORTFOLIO_FIVE")
        definition = require_canonical_61_runner_authorization(
            self._governance, CANONICAL_61_STRATEGY_REFERENCE,
        )
        intelligence_as_of = self._governance.latest_common_canonical_diagnostic_as_of(
            definition.reference, instrument_ids,
        )
        if intelligence_as_of is None:
            raise ValueError("CANONICAL_DECISION_SCORE_COMMON_AS_OF_MISSING")
        records = self._governance.list_diagnostic_results(definition.reference, intelligence_as_of)
        outcomes = tuple(
            self._materialize_holding(
                instrument_id, definition=definition, records=records,
                intelligence_as_of=intelligence_as_of,
            )
            for instrument_id in instrument_ids
        )
        return CanonicalDecisionScoreActivationRun(intelligence_as_of, outcomes)

    def _materialize_holding(self, instrument_id, *, definition, records, intelligence_as_of):
        diagnostics = rehydrate_persisted_canonical_diagnostics(
            records, instrument_id=instrument_id, as_of=intelligence_as_of,
        )
        value = build_scorecard(
            instrument_id=instrument_id,
            strategy_version=definition.reference,
            registry_version=DIAGNOSTIC_REGISTRY_VERSION,
            as_of_timestamp=intelligence_as_of,
            evaluated_at=intelligence_as_of,
            diagnostics=diagnostics,
        )
        blockers = _blockers(value)
        if blockers:
            return CanonicalDecisionScoreActivationOutcome(
                instrument_id, "INELIGIBLE", None, None, None,
                _latest_completed_market_session(self._historical, instrument_id, intelligence_as_of), blockers,
            )
        latest_session = _latest_completed_market_session(self._historical, instrument_id, intelligence_as_of)
        canonical = canonical_decision_scorecard_from(
            value, definition=definition, scoring_policy=SCORING_POLICY,
            latest_completed_market_session=latest_session,
        )
        existing = self._governance.get_canonical_decision_scorecard(canonical.id)
        stored = self._governance.save_canonical_decision_scorecard(canonical)
        return CanonicalDecisionScoreActivationOutcome(
            instrument_id, "IDENTICAL" if existing is not None else "CREATED", stored.id,
            stored.final_score, stored.artifact_fingerprint,
            stored.latest_completed_market_session, (),
        )


def _blockers(value) -> tuple[DecisionScoreBlocker, ...]:
    missing_rule_ids = tuple(sorted({
        rule_id for component in value.components for rule_id in component.missing_rules
    }))
    return tuple(
        DecisionScoreBlocker(
            rule_id=rule_id,
            rule_name=get_diagnostic_rule(rule_id).canonical_name,
            required_inputs=get_diagnostic_rule(rule_id).required_inputs,
            upstream_domain=("MARKET_TECHNICAL" if rule_id <= 14 or rule_id >= 35 else "FINANCIAL_EARNINGS"),
        )
        for rule_id in missing_rule_ids
    )


def _latest_completed_market_session(historical: _HistoricalBars, instrument_id: str, as_of: datetime) -> datetime | None:
    values = historical.latest(instrument_id, Timeframe.DAILY, 1, as_of=as_of)
    return values[-1].start_time if values else None


__all__ = (
    "CanonicalDecisionScoreActivationOutcome", "CanonicalDecisionScoreActivationRun",
    "CanonicalPortfolioDecisionScoreActivator", "DecisionScoreBlocker",
)
