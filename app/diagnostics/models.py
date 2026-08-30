from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from app.domain.models import DiagnosticResult, Evidence

class EvaluationEligibility(StrEnum):
    ELIGIBLE = "eligible"
    INELIGIBLE_MISSING_DATA = "ineligible_missing_data"
    INELIGIBLE_STALE_DATA = "ineligible_stale_data"
    INELIGIBLE_INVALID_DATA = "ineligible_invalid_data"
    INELIGIBLE_UNVERIFIED_INPUT = "ineligible_unverified_input"

class ComponentEligibility(StrEnum):
    ELIGIBLE = "eligible"
    PARTIAL = "partial"
    INELIGIBLE = "ineligible"

@dataclass(frozen=True, slots=True)
class EvaluatedDiagnostic:
    record: DiagnosticResult
    canonical_rule_id: int
    registry_version: str
    eligibility: EvaluationEligibility
    evidence: tuple[Evidence, ...]
    details: tuple[tuple[str, str], ...]

@dataclass(frozen=True, slots=True)
class ComponentContributionEligibility:
    component_id: str
    status: ComponentEligibility
    reason: str
    missing_evidence: tuple[str, ...]
    confidence: float | None
