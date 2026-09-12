"""Source-bound score admission, not score calculation or source authentication.

Only the existing score producer/repository artifact can supply the value. A
Decimal plus caller-declared V1 metadata is never a score source. Historical
comparison values additionally require their original gate result. Callers
remain responsible for loading these artifacts through their canonical reader.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.fundamentals.diagnostic_comparability import content_fingerprint, canonical_json
from app.gates.version_compatibility import GateVersionBlocked, require_gate_source, _utc
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import DecisionScorecard

if TYPE_CHECKING:
    from app.portfolio.canonical_decision_score import CanonicalDecisionScorecard
    from app.gates.engine import ExecutionGateEvaluation


VERSION = "gate-score-provenance/v1"


def _card(source):
    # This import is of an immutable artifact, never a portfolio service/reader.
    from app.portfolio.canonical_decision_score import CanonicalDecisionScorecard
    require_gate_source(source)
    if type(source) not in (DecisionScorecard, CanonicalDecisionScorecard):
        raise GateVersionBlocked("GATE_SCORE_SOURCE_REQUIRED")
    if source.registry_version != DIAGNOSTIC_REGISTRY_VERSION:
        raise GateVersionBlocked("GATE_SCORE_REGISTRY_UNVERIFIED")
    if not source.id or not source.instrument_id or not source.configuration_version:
        raise GateVersionBlocked("GATE_SCORE_IDENTITY_UNVERIFIED")
    if source.strategy_version is None:
        raise GateVersionBlocked("GATE_SCORE_STRATEGY_UNVERIFIED")
    if source.final_score is not None and (type(source.final_score) is not Decimal
            or not source.final_score.is_finite() or source.score_status != "COMPLETE"):
        raise GateVersionBlocked("GATE_SCORE_ELIGIBILITY_UNVERIFIED")
    if _utc(source.evaluated_at) > _utc(source.as_of_timestamp):
        raise GateVersionBlocked("GATE_SCORE_FUTURE_EVIDENCE")
    if type(source) is CanonicalDecisionScorecard:
        source.verify_integrity()
    return source


@dataclass(frozen=True, slots=True)
class GateScoreEvidence:
    """Retains the complete source, not a reconstructed number with a V1 label."""
    source: DecisionScorecard | CanonicalDecisionScorecard
    source_fingerprint: str
    comparison_result: ExecutionGateEvaluation | None = None
    comparison_fingerprint: str | None = None
    contract_version: str = VERSION

    def __post_init__(self):
        card = _card(self.source)
        if self.contract_version != VERSION or self.source_fingerprint != content_fingerprint(card):
            raise GateVersionBlocked("GATE_SCORE_SOURCE_FINGERPRINT_MISMATCH")
        if self.comparison_result is None:
            if self.comparison_fingerprint is not None:
                raise GateVersionBlocked("GATE_SCORE_COMPARISON_CONTRADICTION")
            return
        from app.gates.engine import ExecutionGateEvaluation
        result = self.comparison_result
        require_gate_source(result)
        if type(result) is not ExecutionGateEvaluation:
            raise GateVersionBlocked("GATE_COMPARISON_SOURCE_REQUIRED")
        if (result.registry_version != card.registry_version or result.scorecard_id != card.id
                or result.instrument_id != card.instrument_id or result.strategy_version != card.strategy_version
                or result.scoring_configuration_version != card.configuration_version
                or result.raw_decision_score != card.final_score
                or _utc(result.as_of_timestamp) < _utc(card.as_of_timestamp)
                or _utc(result.evaluated_at) > _utc(result.as_of_timestamp)
                or self.comparison_fingerprint != content_fingerprint(result)):
            raise GateVersionBlocked("GATE_COMPARISON_LINEAGE_MISMATCH")

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def score_evidence(source, *, comparison_result=None):
    """Narrow adapter for the exact V1 score artifact; no scalar argument."""
    _card(source)
    return GateScoreEvidence(source, content_fingerprint(source), comparison_result,
                             content_fingerprint(comparison_result) if comparison_result is not None else None)


def require_score_provenance(inputs, *, instrument_id, strategy_version, scoring_version,
                             gate_version, as_of, candidate, incumbent):
    for name, proof, value in (("candidate", candidate, inputs.raw_decision_score),
                               ("incumbent", incumbent, inputs.comparison_score)):
        if proof is None:
            if value is not None:
                raise GateVersionBlocked("GATE_" + name.upper() + "_SCORE_PROVENANCE_REQUIRED")
            continue
        if type(proof) is not GateScoreEvidence:
            require_gate_source(proof)
            raise GateVersionBlocked("GATE_SCORE_SOURCE_REQUIRED")
        proof.__post_init__()
        card = proof.source
        if _utc(card.as_of_timestamp) > _utc(as_of):
            raise GateVersionBlocked("GATE_SCORE_FUTURE_EVIDENCE")
        if name == "candidate":
            if (proof.comparison_result is not None or card.id != inputs.scorecard_id
                    or card.instrument_id != instrument_id or card.strategy_version != strategy_version
                    or card.configuration_version != scoring_version or card.final_score != value):
                raise GateVersionBlocked("GATE_CANDIDATE_SCORE_BINDING_MISMATCH")
        else:
            result = proof.comparison_result
            if (result is None or _utc(result.as_of_timestamp) > _utc(as_of)
                    or result.gate_configuration_version != gate_version
                    or result.scoring_configuration_version != scoring_version
                    or result.comparison_score != value):
                raise GateVersionBlocked("GATE_INCUMBENT_SCORE_BINDING_MISMATCH")
