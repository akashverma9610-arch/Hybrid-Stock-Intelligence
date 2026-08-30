from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

from app.domain.models import EvidenceType


class DiagnosticState(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    NEUTRAL = "neutral"
    INSUFFICIENT_DATA = "insufficient_data"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"


class EvaluationMode(StrEnum):
    DETERMINISTIC = "deterministic"
    HYBRID = "hybrid"
    INTERPRETIVE = "interpretive"


class ScoreEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE_MISSING_REQUIRED_COMPONENT = "ineligible_missing_required_component"


class MissingDataTreatment(StrEnum):
    NO_SILENT_WEIGHT_RENORMALIZATION = "no_silent_weight_renormalization"
    SURFACE_MISSING_COMPONENT = "surface_missing_component"
    REDUCE_ELIGIBILITY_AND_CONFIDENCE = "reduce_eligibility_and_confidence"


class CatalystTiming(StrEnum):
    IMMEDIATE = "immediate_0_to_30_days"
    NEAR_TERM = "near_term_1_to_3_months"
    MEDIUM_TERM = "medium_term_3_to_12_months"


@dataclass(frozen=True, slots=True)
class DiagnosticRuleDefinition:
    rule_id: int
    canonical_name: str
    category: str
    purpose: str
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...]
    output_type: str
    possible_statuses: tuple[DiagnosticState, ...]
    dependencies: tuple[int, ...]
    minimum_data_requirements: str
    missing_data_behavior: str
    confidence_policy: str
    evaluation_mode: EvaluationMode
    allowed_evidence_types: tuple[EvidenceType, ...]
    calculation_version: str
    notes_limitations: str


@dataclass(frozen=True, slots=True)
class DecisionScoreComponentDefinition:
    component_id: str
    canonical_name: str
    weight_percent: Decimal
    component_minimum: Decimal = Decimal("0.0")
    component_maximum: Decimal = Decimal("10.0")
    formula_status: str = "REQUIRES_APPROVED_COMPONENT_FORMULA"


@dataclass(frozen=True, slots=True)
class DataConfidencePolicy:
    version: str
    factors: tuple[str, ...]
    crowd_data_confidence_is_separate: bool = True
    decision_score_transformation: str = "NOT_DEFINED"


@dataclass(frozen=True, slots=True)
class MissingDataPolicy:
    version: str
    treatments: tuple[MissingDataTreatment, ...]
    default_weight_renormalization_allowed: bool = False

    def score_eligibility(self, required_component_states: Mapping[str, DiagnosticState]) -> ScoreEligibility:
        if any(state in {DiagnosticState.INSUFFICIENT_DATA, DiagnosticState.UNVERIFIED} for state in required_component_states.values()):
            return ScoreEligibility.INELIGIBLE_MISSING_REQUIRED_COMPONENT
        return ScoreEligibility.ELIGIBLE


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    version: str
    components: tuple[DecisionScoreComponentDefinition, ...]
    data_confidence_policy: DataConfidencePolicy
    missing_data_policy: MissingDataPolicy

    @property
    def total_weight_percent(self) -> Decimal:
        return sum((component.weight_percent for component in self.components), Decimal("0"))


@dataclass(frozen=True, slots=True)
class ExecutionGateDefinition:
    gate_id: int
    canonical_name: str
    purpose: str
    required_inputs: tuple[str, ...]
    intended_policy: str
    parameters_status: str
    missing_data_behavior: str
    calculation_version: str


@dataclass(frozen=True, slots=True)
class ResearchSourceTier:
    priority: int
    label: str
    sources: tuple[str, ...]
    permitted_use: str


@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    benchmark_id: int
    canonical_name: str
    purpose: str
    calculation_status: str = "NOT_IMPLEMENTED"


@dataclass(frozen=True, slots=True)
class SelfImprovementLifecycleDefinition:
    stages: tuple[str, ...]
    required_experiment_fields: tuple[str, ...]
    active_rule_change_policy: str
