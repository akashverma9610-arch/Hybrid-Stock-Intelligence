"""Fail-closed activation of the existing Six Execution Gates engine.

This service is backend-local and analytical only.  It accepts no transport
input, creates no order, and persists only an exact canonical lineage result.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.gates.engine import ActionContext, ExecutionGateEngine, GateInput
from app.gates.version_compatibility import require_gate_source
from app.gates.score_provenance import score_evidence
from app.portfolio.canonical_diagnostics_orchestration import PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
from app.portfolio.canonical_six_gates import canonical_execution_gate_evaluation_from


class _CanonicalGateRepository(Protocol):
    def list_canonical_decision_scorecards(self, canonical_instrument_id: str | None = None): ...
    def get_canonical_execution_gate_evaluation(self, value_id: str): ...
    def save_canonical_execution_gate_evaluation(self, value): ...


@dataclass(frozen=True, slots=True)
class CanonicalSixGatesActivationOutcome:
    instrument_id: str
    status: str
    evaluation_id: str | None
    eligibility: str | None
    gate_outcomes: tuple[tuple[str, str], ...]
    blockers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalSixGatesActivationRun:
    execution_as_of: datetime
    outcomes: tuple[CanonicalSixGatesActivationOutcome, ...]


class CanonicalPortfolioSixGatesActivator:
    """Materialize only PIT-compatible canonical execution-gate artifacts."""

    def __init__(self, *, governance: _CanonicalGateRepository, engine: ExecutionGateEngine | None) -> None:
        self._governance = governance
        self._engine = engine

    def materialize(
        self,
        *,
        execution_as_of: datetime,
        inputs_by_instrument: dict[str, GateInput] | None = None,
        action_context_by_instrument: dict[str, ActionContext] | None = None,
        evidence_context_by_instrument: dict | None = None,
    ) -> CanonicalSixGatesActivationRun:
        _aware(execution_as_of)
        values = inputs_by_instrument or {}
        contexts = action_context_by_instrument or {}
        provenance = evidence_context_by_instrument or {}
        if set(values) - set(PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS):
            raise ValueError("SIX_GATES_ACTIVATION_REQUIRES_EXACT_PORTFOLIO_FIVE")
        if set(contexts) - set(PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS):
            raise ValueError("SIX_GATES_ACTIVATION_REQUIRES_EXACT_PORTFOLIO_FIVE")
        if set(provenance) - set(PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS):
            raise ValueError("SIX_GATES_ACTIVATION_REQUIRES_EXACT_PORTFOLIO_FIVE")
        outcomes = tuple(
            self._materialize_one(instrument_id, execution_as_of, values.get(instrument_id), contexts.get(instrument_id), provenance.get(instrument_id))
            for instrument_id in PORTFOLIO_FIVE_CANONICAL_INSTRUMENT_IDS
        )
        return CanonicalSixGatesActivationRun(execution_as_of, outcomes)

    def _materialize_one(
        self, instrument_id: str, execution_as_of: datetime, inputs: GateInput | None,
        action_context: ActionContext | None, evidence_context=None,
    ):
        stored_scores = tuple(self._governance.list_canonical_decision_scorecards(instrument_id))
        require_gate_source(inputs)
        for value in stored_scores:
            require_gate_source(value)
            value.verify_integrity()
        scores = tuple(
            value for value in stored_scores
            if value.as_of_timestamp <= execution_as_of and value.evaluated_at <= execution_as_of
        )
        if not scores:
            return CanonicalSixGatesActivationOutcome(
                instrument_id, "NOT_EVALUATED", None, None, (), ("DECISION_SCORE_NOT_YET_COMPUTED",),
            )
        if self._engine is None:
            return CanonicalSixGatesActivationOutcome(
                instrument_id, "NOT_EVALUATED", None, None, (),
                tuple(f"UNRESOLVED_CONFIG:{item}" for item in _all_gate_parameters()),
            )
        if inputs is None:
            return CanonicalSixGatesActivationOutcome(
                instrument_id, "NOT_EVALUATED", None, None, (), ("NO_CURRENT_EXECUTABLE_SETUP",),
            )
        if action_context is None:
            return CanonicalSixGatesActivationOutcome(
                instrument_id, "NOT_EVALUATED", None, None, (), ("ACTION_CONTEXT_REQUIRED",),
            )
        score = max(scores, key=lambda item: (item.as_of_timestamp, item.evaluated_at, item.id))
        if inputs.scorecard_id != score.id or inputs.snapshot_as_of_timestamp != execution_as_of:
            return CanonicalSixGatesActivationOutcome(
                instrument_id, "NOT_EVALUATED", None, None, (),
                ("GATE_INPUT_SNAPSHOT_AS_OF_MISMATCH",),
            )
        evaluation = self._engine.evaluate(
            instrument_id=instrument_id, strategy_version=score.strategy_version,
            registry_version=score.registry_version, scoring_configuration_version=score.configuration_version,
            action_context=action_context, as_of_timestamp=execution_as_of,
            evaluated_at=execution_as_of, inputs=inputs,
            candidate_score_evidence=score_evidence(score), evidence_context=evidence_context,
        )
        value = canonical_execution_gate_evaluation_from(evaluation, score=score)
        existing = self._governance.get_canonical_execution_gate_evaluation(value.evaluation.id)
        saved = self._governance.save_canonical_execution_gate_evaluation(value)
        return CanonicalSixGatesActivationOutcome(
            instrument_id, "IDENTICAL" if existing else "CREATED", saved.evaluation.id,
            saved.eligibility.value,
            tuple((item.gate_id, item.outcome.value) for item in saved.decisions),
            tuple(sorted(set(saved.failed_gate_ids + saved.insufficient_gate_ids))),
        )


def _all_gate_parameters() -> tuple[str, ...]:
    return (
        "min_score_advantage", "friction_model_version", "inactivity_sessions",
        "atr_expansion_threshold", "velocity_penalty", "disallowed_asm_stage", "disallow_gsm",
        "circuit_limit_threshold", "surveillance_max_age_days", "initial_tranche", "t1_reduction",
        "require_breakeven_plan", "max_total_heat", "max_stock_allocation", "max_sector_allocation",
        "blackout_sessions", "heat_methodology_version",
    )


def _aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SIX_GATES_ACTIVATION_AS_OF_TIMEZONE_REQUIRED")


__all__ = (
    "CanonicalPortfolioSixGatesActivator", "CanonicalSixGatesActivationOutcome",
    "CanonicalSixGatesActivationRun",
)
