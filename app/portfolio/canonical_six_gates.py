"""Immutable canonical Six Execution Gates lineage.

This is deliberately a persistence boundary only. Evaluation remains the
existing pure ``ExecutionGateEngine`` and no artifact can provide execution,
broker, or order authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.gates.engine import ExecutionGateEvaluation
from app.gates.version_compatibility import require_gate_source
from app.historical.guard import manifest_fingerprint
from app.portfolio.canonical_decision_score import CanonicalDecisionScorecard


@dataclass(frozen=True, slots=True)
class CanonicalExecutionGateEvaluation:
    """An immutable gate result anchored to a canonical Decision Score."""

    evaluation: ExecutionGateEvaluation
    canonical_decision_score_fingerprint: str
    canonical_strategy_fingerprint: str
    canonical_limitations_fingerprint: str
    artifact_fingerprint: str

    def verify_integrity(self) -> None:
        value = self.evaluation
        require_gate_source(value)
        if not _aware(value.as_of_timestamp) or not _aware(value.evaluated_at):
            raise ValueError("Canonical execution gate timestamps must be timezone-aware.")
        if value.evaluated_at > value.as_of_timestamp:
            raise ValueError("Canonical execution gates cannot be evaluated after their as-of boundary.")
        if len(value.decisions) != 6 or len({item.gate_id for item in value.decisions}) != 6:
            raise ValueError("Canonical execution gates require exactly six distinct decisions.")
        if not all((self.canonical_decision_score_fingerprint, self.canonical_strategy_fingerprint,
                    self.canonical_limitations_fingerprint, self.artifact_fingerprint)):
            raise ValueError("Canonical execution gate lineage is incomplete.")
        if self.artifact_fingerprint != canonical_execution_gate_evaluation_fingerprint(self):
            raise ValueError("Canonical execution gate artifact fingerprint does not match its lineage.")

    def __getattr__(self, name: str):
        """Expose the established evaluation shape to the evidence adapter."""
        return getattr(self.evaluation, name)


def canonical_execution_gate_evaluation_from(
    evaluation: ExecutionGateEvaluation, *, score: CanonicalDecisionScorecard,
) -> CanonicalExecutionGateEvaluation:
    require_gate_source(evaluation)
    require_gate_source(score)
    score.verify_integrity()
    if evaluation.scorecard_id != score.id or evaluation.instrument_id != score.instrument_id:
        raise ValueError("Canonical execution gates require the exact canonical Decision Score.")
    if evaluation.strategy_version != score.strategy_version:
        raise ValueError("Canonical execution gate strategy does not match its Decision Score.")
    if score.as_of_timestamp > evaluation.as_of_timestamp:
        raise ValueError("Canonical Decision Score cannot be newer than its execution gate input snapshot.")
    initial = CanonicalExecutionGateEvaluation(
        evaluation=evaluation,
        canonical_decision_score_fingerprint=score.artifact_fingerprint,
        canonical_strategy_fingerprint=score.canonical_strategy_fingerprint,
        canonical_limitations_fingerprint=score.canonical_limitations_fingerprint,
        artifact_fingerprint="",
    )
    return CanonicalExecutionGateEvaluation(
        **{**_fields(initial), "artifact_fingerprint": canonical_execution_gate_evaluation_fingerprint(initial)},
    )


def canonical_execution_gate_evaluation_fingerprint(value: CanonicalExecutionGateEvaluation) -> str:
    item = value.evaluation
    return manifest_fingerprint(
        evaluation_id=item.id,
        instrument_id=item.instrument_id,
        strategy_id=item.strategy_version.strategy_id,
        strategy_version=item.strategy_version.version,
        registry_version=item.registry_version,
        scoring_configuration_version=item.scoring_configuration_version,
        gate_configuration_version=item.gate_configuration_version,
        scorecard_id=item.scorecard_id,
        input_snapshot_id=item.input_snapshot_id,
        action_context=_enum(item.action_context),
        as_of_timestamp=item.as_of_timestamp,
        evaluated_at=item.evaluated_at,
        raw_decision_score=item.raw_decision_score,
        rotation_adjustment=item.rotation_adjustment,
        comparison_score=item.comparison_score,
        decisions=tuple(sorted((
            decision.gate_id, _enum(decision.outcome), decision.detail, decision.confidence,
            tuple(sorted(decision.evidence_ids)), tuple(sorted(decision.parameters.items())),
        ) for decision in item.decisions)),
        eligibility=_enum(item.eligibility),
        failed_gate_ids=tuple(sorted(item.failed_gate_ids)),
        insufficient_gate_ids=tuple(sorted(item.insufficient_gate_ids)),
        warnings=tuple(sorted(item.warnings)),
        evidence_ids=tuple(sorted(item.evidence_ids)),
        diagnostic_ids=tuple(sorted(item.diagnostic_ids)),
        configuration_parameters=tuple(sorted(item.configuration_parameters.items())),
        canonical_decision_score_fingerprint=value.canonical_decision_score_fingerprint,
        canonical_strategy_fingerprint=value.canonical_strategy_fingerprint,
        canonical_limitations_fingerprint=value.canonical_limitations_fingerprint,
    )


def _enum(value: object) -> str:
    return str(getattr(value, "value", value))


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _fields(value: CanonicalExecutionGateEvaluation) -> dict[str, Any]:
    return {field: getattr(value, field) for field in value.__dataclass_fields__}


__all__ = (
    "CanonicalExecutionGateEvaluation", "canonical_execution_gate_evaluation_fingerprint",
    "canonical_execution_gate_evaluation_from",
)
