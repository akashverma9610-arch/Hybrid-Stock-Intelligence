"""Explicit non-scoring shadow lineage and fail-closed active V1 admission.

No policy selection, activation, persistence or legacy-state translation. The
recognized synthesis vocabulary preserves V1 interpretation, not economic
approval for a new registry. Score values remain owned by the existing scorer.
"""
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Mapping

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint

ADAPTER_VERSION = "fundamental-v2-downstream-safety/v1"
CROSS_REGISTRY = "CROSS_REGISTRY_DIAGNOSTIC_CONSUMPTION_FORBIDDEN"


class ScoreInputState(StrEnum):
    SCORE_ELIGIBLE_EXPLICIT_STATE = "SCORE_ELIGIBLE_EXPLICIT_STATE"
    SCORE_INELIGIBLE_INSUFFICIENT_DATA = "SCORE_INELIGIBLE_INSUFFICIENT_DATA"
    SCORE_INELIGIBLE_POLICY_BLOCKED = "SCORE_INELIGIBLE_POLICY_BLOCKED"
    SCORE_INELIGIBLE_CONFLICTED = "SCORE_INELIGIBLE_CONFLICTED"
    SCORE_INELIGIBLE_NOT_APPLICABLE = "SCORE_INELIGIBLE_NOT_APPLICABLE"
    SCORE_INELIGIBLE_SHADOW = "SCORE_INELIGIBLE_SHADOW"
    SCORE_INELIGIBLE_UNKNOWN_STATE = "SCORE_INELIGIBLE_UNKNOWN_STATE"


@dataclass(frozen=True, slots=True)
class ScoreInputClassification:
    state: ScoreInputState
    value: Decimal | None
    reason: str

    def __post_init__(self):
        if not isinstance(self.state, ScoreInputState) or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("SCORE_INPUT_CLASSIFICATION_INVALID")
        eligible = self.state is ScoreInputState.SCORE_ELIGIBLE_EXPLICIT_STATE
        if (eligible and (not isinstance(self.value, Decimal) or not self.value.is_finite())
                or not eligible and self.value is not None):
            raise ValueError("SCORE_INPUT_CLASSIFICATION_CONTRADICTION")


# Exact V1 output vocabulary encountered at the synthesis boundary; no case
# folding, substring matching, aliases, numeric defaults or V2 readiness names.
V1_SYNTHESIS_STATES = frozenset({
    "ACCELERATING", "ACCEPTABLE", "ACCUMULATION", "ACTIVE_CATALYST", "ASCENDING_BASE",
    "ATTRACTIVE", "BALANCED", "BEAR", "BEARISH", "BEARISH_CONFIRMATION",
    "BEARISH_DIVERGENCE", "BELOW_THRESHOLD", "BROKEN", "BULL", "BULLISH",
    "BULLISH_CONFIRMATION", "BULLISH_DIVERGENCE", "CANDIDATE", "CLEAN", "CONCERN",
    "CONFIRMED", "CONTRACTING", "CONTRACTION", "CUP_AND_HANDLE", "DECLINING",
    "DETERIORATING", "DISTRIBUTION", "ELEVATED", "ELEVATED_RISK", "EXPANDING",
    "EXPANSION", "EXPENSIVE", "FLAT_BASE", "GROWING",
    "HEALTHY", "HH_HL_BULLISH", "HIGH", "HIGH_QUALITY", "HIGH_RISK",
    "INVALIDATED", "LH_LL_BEARISH", "LOW", "MARKDOWN",
    "MARKUP", "MIXED", "MODERATE", "MODERATE_RISK", "NEUTRAL",
    "NORMAL", "NO_VALID_BASE", "NO_VALID_ENTRY", "OCCURRED", "PARTIAL",
    "PRICE_STRUCTURE_INVALIDATION", "REASONABLE", "REPORTED", "SEVERE_CONCERN",
    "SEVERE_RISK", "SIDEWAYS", "STABLE", "STRESSED", "STRONG",
    "STRONG_BEARISH", "STRONG_BULL", "STRONG_BULLISH", "TRIGGERED", "UNCLEAR",
    "UNINTERPRETABLE", "VALID", "VCP", "WATCH", "WEAK",
    "WEAKENING", "average", "bear", "bull", "downtrend",
    "emerging_leader", "laggard", "leader", "neutral", "panic",
    "selective_bear", "selective_bull", "sideways", "strong_bull", "uptrend",
})


def active_v1_rejection(value, registry_version):
    """Inspect nominal envelopes before any duck-typed .record/.eligibility."""
    if registry_version != DIAGNOSTIC_REGISTRY_VERSION:
        return CROSS_REGISTRY
    if not isinstance(value, EvaluatedDiagnostic):
        return CROSS_REGISTRY if _is_shadow(value) else "DIAGNOSTIC_INPUT_UNVERIFIED"
    if value.registry_version != DIAGNOSTIC_REGISTRY_VERSION:
        return CROSS_REGISTRY
    return None


def _is_shadow(value):
    if isinstance(value, EvaluatedDiagnostic):
        return False
    # Only the explicit shadow path imports its domain type. No registry
    # artifact is loaded by ordinary V1 admission.
    from app.fundamentals.diagnostic_v2_shadow import FundamentalV2ShadowResult
    return isinstance(value, (FundamentalV2ShadowResult, ShadowDiagnosticEnvelope))


def classify_score_input(value, *, registry_version, state_scores: Mapping[str, Decimal]):
    S = ScoreInputState
    if _is_shadow(value):
        return ScoreInputClassification(S.SCORE_INELIGIBLE_SHADOW, None, "V2_SHADOW_SCORE_FORBIDDEN")
    reason = active_v1_rejection(value, registry_version)
    if reason:
        return ScoreInputClassification(S.SCORE_INELIGIBLE_UNKNOWN_STATE, None, reason)
    state = value.record.result
    if not isinstance(state, str) or not state or state != state.strip():
        return ScoreInputClassification(S.SCORE_INELIGIBLE_UNKNOWN_STATE, None, "DIAGNOSTIC_STATE_UNKNOWN")
    blocked = {
        "INSUFFICIENT_DATA": S.SCORE_INELIGIBLE_INSUFFICIENT_DATA,
        "POLICY_BLOCKED": S.SCORE_INELIGIBLE_POLICY_BLOCKED,
        "EVIDENCE_CONFLICTED": S.SCORE_INELIGIBLE_CONFLICTED,
        "NOT_APPLICABLE": S.SCORE_INELIGIBLE_NOT_APPLICABLE,
    }
    if state in blocked:
        return ScoreInputClassification(blocked[state], None, state)
    if value.eligibility is not EvaluationEligibility.ELIGIBLE:
        return ScoreInputClassification(S.SCORE_INELIGIBLE_INSUFFICIENT_DATA, None, "DIAGNOSTIC_INPUT_INELIGIBLE")
    if state not in state_scores:
        return ScoreInputClassification(S.SCORE_INELIGIBLE_UNKNOWN_STATE, None, "DIAGNOSTIC_STATE_UNKNOWN")
    return ScoreInputClassification(S.SCORE_ELIGIBLE_EXPLICIT_STATE, state_scores[state], "EXPLICIT_V1_STATE")


def v1_synthesis_rejection(values, registry_version, as_of):
    if registry_version != DIAGNOSTIC_REGISTRY_VERSION:
        return CROSS_REGISTRY
    seen = {}
    reasons = set()
    for value in values:
        reason = active_v1_rejection(value, registry_version)
        if reason:
            reasons.add(reason)
            continue
        if value.record.as_of_timestamp > as_of:
            continue
        if value.eligibility is not EvaluationEligibility.ELIGIBLE:
            continue
        state = value.record.result
        # Actual read dependencies of Rules 31-34, not the whole 61-rule
        # record set they also retain descriptively as input IDs. Unused
        # diagnostics must not acquire a new interpretation in this slice.
        participating = {1,2,4,6,10,16,17,18,19,23,29,30,31,32,33,37,38,41,43,45,46,55}
        if value.canonical_rule_id in participating and (not isinstance(state, str) or state not in V1_SYNTHESIS_STATES):
            reasons.add("DIAGNOSTIC_STATE_UNSUPPORTED_FOR_SYNTHESIS")
        old = seen.get(value.canonical_rule_id)
        if old is not None and old != value:
            reasons.add("DIAGNOSTIC_PROVENANCE_CONFLICTED")
        seen[value.canonical_rule_id] = value
    return CROSS_REGISTRY if CROSS_REGISTRY in reasons else min(reasons) if reasons else None


@dataclass(frozen=True, slots=True)
class ShadowDiagnosticEnvelope:
    """V2 audit-only reference; never impersonates EvaluatedDiagnostic.

    Policy version is the source evaluator version plus the pinned governance
    fingerprint. No strategy version exists on this source, so it stays absent.
    """
    source: "FundamentalV2ShadowResult"
    registry_version: str
    strategy_version: None
    policy_version: str
    policy_fingerprint: str
    as_of: datetime
    source_result_fingerprint: str
    fingerprint: str
    adapter_version: str = ADAPTER_VERSION
    score_eligible: bool = False
    execution_eligible: bool = False

    def __post_init__(self):
        from app.fundamentals.diagnostic_v2_shadow import FundamentalV2ShadowResult
        if not isinstance(self.source, FundamentalV2ShadowResult):
            raise ValueError("SHADOW_DIAGNOSTIC_SOURCE_REQUIRED")
        self.source.__post_init__()
        if not isinstance(self.as_of, datetime) or self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("SHADOW_DIAGNOSTIC_AS_OF_INVALID")
        object.__setattr__(self, "as_of", self.as_of.astimezone(UTC))
        if (self.registry_version != self.source.registry_version or self.strategy_version is not None
                or self.policy_version != self.source.evaluator_version
                or self.policy_fingerprint != self.source.approval_fingerprint
                or self.as_of != self.source.as_of
                or self.source_result_fingerprint != self.source.fingerprint
                or self.adapter_version != ADAPTER_VERSION
                or self.score_eligible is not False or self.execution_eligible is not False):
            raise ValueError("SHADOW_DIAGNOSTIC_LINEAGE_OR_AUTHORITY_MISMATCH")
        if self.fingerprint != content_fingerprint(self._identity()):
            raise ValueError("SHADOW_DIAGNOSTIC_FINGERPRINT_MISMATCH")

    def _identity(self):
        return dict(adapter_version=self.adapter_version, registry_version=self.registry_version,
                    strategy_version=self.strategy_version, policy_version=self.policy_version,
                    policy_fingerprint=self.policy_fingerprint, as_of=self.as_of,
                    source_result_fingerprint=self.source_result_fingerprint,
                    score_eligible=self.score_eligible, execution_eligible=self.execution_eligible)

    def to_json(self):
        self.__post_init__()
        return canonical_json(self)


def shadow_diagnostic_envelope(value, *, as_of):
    from app.fundamentals.diagnostic_v2_shadow import FundamentalV2ShadowResult
    if not isinstance(value, FundamentalV2ShadowResult):
        raise ValueError("SHADOW_DIAGNOSTIC_SOURCE_REQUIRED")
    value.__post_init__()
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("SHADOW_DIAGNOSTIC_AS_OF_INVALID")
    if value.as_of > as_of:
        raise ValueError("FUTURE_SHADOW_DIAGNOSTIC_EXCLUDED")
    identity = dict(adapter_version=ADAPTER_VERSION, registry_version=value.registry_version,
                    strategy_version=None, policy_version=value.evaluator_version,
                    policy_fingerprint=value.approval_fingerprint, as_of=value.as_of,
                    source_result_fingerprint=value.fingerprint, score_eligible=False, execution_eligible=False)
    return ShadowDiagnosticEnvelope(source=value, **identity, fingerprint=content_fingerprint(identity))
