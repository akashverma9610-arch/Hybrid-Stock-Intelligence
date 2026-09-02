"""Immutable canonical Decision Score lineage.

This boundary retains the approved Canonical 61 diagnostics as the score
inputs.  It deliberately does not create a generic strategy-version anchor,
evaluate diagnostics, or perform any execution-gate work.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticStrategyDefinition,
    governance_limitations_fingerprint,
)
from app.domain.models import StrategyVersionReference
from app.historical.guard import manifest_fingerprint
from app.registry.models import ScoringPolicy
from app.scoring.engine import DecisionScorecard, ScoredComponent


@dataclass(frozen=True, slots=True)
class CanonicalDecisionScorecard:
    """A complete Decision Score with exact canonical diagnostic lineage."""

    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    registry_version: str
    configuration_version: str
    as_of_timestamp: datetime
    evaluated_at: datetime
    components: tuple[ScoredComponent, ...]
    final_score: Decimal
    score_status: str
    data_confidence: float | None
    warnings: tuple[str, ...]
    canonical_strategy_fingerprint: str
    canonical_limitations_fingerprint: str
    scoring_policy_version: str
    scoring_policy_fingerprint: str
    latest_completed_market_session: datetime | None
    artifact_fingerprint: str

    def verify_integrity(self) -> None:
        if self.score_status != "COMPLETE" or self.final_score is None:
            raise ValueError("Canonical Decision Score persistence requires a complete score.")
        if not _aware(self.as_of_timestamp) or not _aware(self.evaluated_at):
            raise ValueError("Canonical Decision Score timestamps must be timezone-aware.")
        if self.evaluated_at > self.as_of_timestamp:
            raise ValueError("Canonical Decision Score cannot be evaluated after its as-of boundary.")
        if self.latest_completed_market_session is not None:
            if not _aware(self.latest_completed_market_session):
                raise ValueError("Canonical Decision Score market-session timestamp must be timezone-aware.")
            if self.latest_completed_market_session > self.as_of_timestamp:
                raise ValueError("Canonical Decision Score market session exceeds its as-of boundary.")
        if self.artifact_fingerprint != canonical_decision_scorecard_fingerprint(self):
            raise ValueError("Canonical Decision Score artifact fingerprint does not match its lineage.")


def scoring_policy_fingerprint(policy: ScoringPolicy) -> str:
    """Deterministic identity of the already-approved scoring configuration."""
    return manifest_fingerprint(
        policy_version=policy.version,
        components=tuple(
            (
                item.component_id, item.canonical_name, item.weight_percent,
                item.component_minimum, item.component_maximum, item.formula_status,
            )
            for item in policy.components
        ),
        data_confidence_policy=(
            policy.data_confidence_policy.version,
            policy.data_confidence_policy.factors,
            policy.data_confidence_policy.crowd_data_confidence_is_separate,
            policy.data_confidence_policy.decision_score_transformation,
        ),
        missing_data_policy=(
            policy.missing_data_policy.version,
            tuple(item.value for item in policy.missing_data_policy.treatments),
            policy.missing_data_policy.default_weight_renormalization_allowed,
        ),
    )


def canonical_decision_scorecard_from(
    value: DecisionScorecard,
    *,
    definition: CanonicalDiagnosticStrategyDefinition,
    scoring_policy: ScoringPolicy,
    latest_completed_market_session: datetime | None,
) -> CanonicalDecisionScorecard:
    """Attach immutable policy and Canonical 61 lineage to a complete card."""
    if value.strategy_version != definition.reference:
        raise ValueError("Canonical Decision Score strategy definition mismatch.")
    if value.score_status != "COMPLETE" or value.final_score is None:
        raise ValueError("Incomplete Decision Score cannot become a canonical artifact.")
    initial = CanonicalDecisionScorecard(
        id=value.id,
        instrument_id=value.instrument_id,
        strategy_version=value.strategy_version,
        registry_version=value.registry_version,
        configuration_version=value.configuration_version,
        as_of_timestamp=value.as_of_timestamp,
        evaluated_at=value.evaluated_at,
        components=value.components,
        final_score=value.final_score,
        score_status=value.score_status,
        data_confidence=value.data_confidence,
        warnings=value.warnings,
        canonical_strategy_fingerprint=definition.semantic_fingerprint,
        canonical_limitations_fingerprint=governance_limitations_fingerprint(definition.governance_limitations),
        scoring_policy_version=scoring_policy.version,
        scoring_policy_fingerprint=scoring_policy_fingerprint(scoring_policy),
        latest_completed_market_session=latest_completed_market_session,
        artifact_fingerprint="",
    )
    return CanonicalDecisionScorecard(
        **{**_fields(initial), "artifact_fingerprint": canonical_decision_scorecard_fingerprint(initial)},
    )


def canonical_decision_scorecard_fingerprint(value: CanonicalDecisionScorecard) -> str:
    return manifest_fingerprint(
        artifact_id=value.id,
        instrument_id=value.instrument_id,
        strategy_id=value.strategy_version.strategy_id,
        strategy_version=value.strategy_version.version,
        registry_version=value.registry_version,
        configuration_version=value.configuration_version,
        as_of_timestamp=value.as_of_timestamp,
        evaluated_at=value.evaluated_at,
        components=tuple(
            (
                item.component_id, item.status, item.score, item.weight,
                item.weighted_contribution, item.available_rules, item.missing_rules,
                item.diagnostic_ids, item.evidence_ids, item.confidence, item.contradictions,
            )
            for item in sorted(value.components, key=lambda item: item.component_id)
        ),
        final_score=value.final_score,
        score_status=value.score_status,
        data_confidence=value.data_confidence,
        warnings=tuple(sorted(value.warnings)),
        canonical_strategy_fingerprint=value.canonical_strategy_fingerprint,
        canonical_limitations_fingerprint=value.canonical_limitations_fingerprint,
        scoring_policy_version=value.scoring_policy_version,
        scoring_policy_fingerprint=value.scoring_policy_fingerprint,
        latest_completed_market_session=value.latest_completed_market_session,
    )


def canonical_decision_scorecard_to_dict(value: CanonicalDecisionScorecard) -> dict[str, Any]:
    value.verify_integrity()
    return {
        "id": value.id,
        "instrument_id": value.instrument_id,
        "strategy_id": value.strategy_version.strategy_id,
        "strategy_version": value.strategy_version.version,
        "registry_version": value.registry_version,
        "configuration_version": value.configuration_version,
        "as_of_timestamp": value.as_of_timestamp.isoformat(),
        "evaluated_at": value.evaluated_at.isoformat(),
        "components": [_component_to_dict(item) for item in value.components],
        "final_score": str(value.final_score),
        "score_status": value.score_status,
        "data_confidence": value.data_confidence,
        "warnings": list(value.warnings),
        "canonical_strategy_fingerprint": value.canonical_strategy_fingerprint,
        "canonical_limitations_fingerprint": value.canonical_limitations_fingerprint,
        "scoring_policy_version": value.scoring_policy_version,
        "scoring_policy_fingerprint": value.scoring_policy_fingerprint,
        "latest_completed_market_session": (
            value.latest_completed_market_session.isoformat()
            if value.latest_completed_market_session else None
        ),
        "artifact_fingerprint": value.artifact_fingerprint,
    }


def canonical_decision_scorecard_from_dict(value: dict[str, Any]) -> CanonicalDecisionScorecard:
    card = CanonicalDecisionScorecard(
        id=value["id"],
        instrument_id=value["instrument_id"],
        strategy_version=StrategyVersionReference(value["strategy_id"], value["strategy_version"]),
        registry_version=value["registry_version"],
        configuration_version=value["configuration_version"],
        as_of_timestamp=datetime.fromisoformat(value["as_of_timestamp"]),
        evaluated_at=datetime.fromisoformat(value["evaluated_at"]),
        components=tuple(_component_from_dict(item) for item in value["components"]),
        final_score=Decimal(value["final_score"]),
        score_status=value["score_status"],
        data_confidence=value["data_confidence"],
        warnings=tuple(value["warnings"]),
        canonical_strategy_fingerprint=value["canonical_strategy_fingerprint"],
        canonical_limitations_fingerprint=value["canonical_limitations_fingerprint"],
        scoring_policy_version=value["scoring_policy_version"],
        scoring_policy_fingerprint=value["scoring_policy_fingerprint"],
        latest_completed_market_session=(
            datetime.fromisoformat(value["latest_completed_market_session"])
            if value["latest_completed_market_session"] else None
        ),
        artifact_fingerprint=value["artifact_fingerprint"],
    )
    card.verify_integrity()
    return card


def _component_to_dict(value: ScoredComponent) -> dict[str, Any]:
    return {
        "component_id": value.component_id,
        "status": value.status,
        "score": str(value.score) if value.score is not None else None,
        "weight": str(value.weight),
        "weighted_contribution": (
            str(value.weighted_contribution) if value.weighted_contribution is not None else None
        ),
        "available_rules": list(value.available_rules),
        "missing_rules": list(value.missing_rules),
        "diagnostic_ids": list(value.diagnostic_ids),
        "evidence_ids": list(value.evidence_ids),
        "confidence": value.confidence,
        "contradictions": list(value.contradictions),
    }


def _component_from_dict(value: dict[str, Any]) -> ScoredComponent:
    return ScoredComponent(
        value["component_id"], value["status"],
        Decimal(value["score"]) if value["score"] is not None else None,
        Decimal(value["weight"]),
        Decimal(value["weighted_contribution"]) if value["weighted_contribution"] is not None else None,
        tuple(value["available_rules"]), tuple(value["missing_rules"]),
        tuple(value["diagnostic_ids"]), tuple(value["evidence_ids"]),
        value["confidence"], tuple(value["contradictions"]),
    )


def _fields(value: CanonicalDecisionScorecard) -> dict[str, Any]:
    return {
        field: getattr(value, field)
        for field in value.__dataclass_fields__
    }


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


__all__ = (
    "CanonicalDecisionScorecard", "canonical_decision_scorecard_fingerprint",
    "canonical_decision_scorecard_from", "canonical_decision_scorecard_from_dict",
    "canonical_decision_scorecard_to_dict", "scoring_policy_fingerprint",
)
