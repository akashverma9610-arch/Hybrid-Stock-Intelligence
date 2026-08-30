"""Pure, bounded read-only views over validated shared-Brain context."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.output_evaluation_context import BrainOutputEvaluationContext
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    PortfolioContextRef,
)


class BrainOutputProjectionError(ValueError):
    """A projection is unavailable because its validated context is not ready."""


class BrainOutputProjectionStatus(StrEnum):
    READY = "READY"
    INFORMATIONAL = "INFORMATIONAL"
    PARTIAL = "PARTIAL"


class BrainOutputProjectionSectionKind(StrEnum):
    MARKET_CONTEXT = "MARKET_CONTEXT"
    SECTOR_CONTEXT = "SECTOR_CONTEXT"
    COMPANY_RESEARCH = "COMPANY_RESEARCH"
    TECHNICAL_SETUP = "TECHNICAL_SETUP"
    NEWS_CATALYST = "NEWS_CATALYST"
    RELIABILITY_INTEGRITY = "RELIABILITY_INTEGRITY"
    RESEARCH_DIAGNOSTIC = "RESEARCH_DIAGNOSTIC"
    DECISION_SCORE = "DECISION_SCORE"
    GATE_LINEAGE = "GATE_LINEAGE"
    PORTFOLIO_CONTEXT = "PORTFOLIO_CONTEXT"
    ENTRY_CONTEXT = "ENTRY_CONTEXT"
    ALERT_CONTEXT = "ALERT_CONTEXT"


@dataclass(frozen=True, slots=True)
class BrainOutputProjectionSection:
    """A bounded evidence-reference group, never a copied provider payload."""

    kind: BrainOutputProjectionSectionKind
    evidence_references: tuple[IntelligenceEvidenceReference, ...]
    portfolio_context_ref: PortfolioContextRef | None = None


@dataclass(frozen=True, slots=True)
class BrainOutputProjectionRequirement:
    output_context: BrainOutputContext
    section_kinds: tuple[BrainOutputProjectionSectionKind, ...]

    def __post_init__(self) -> None:
        if not self.section_kinds or self.section_kinds != tuple(sorted(set(self.section_kinds), key=lambda value: value.value)):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_SECTION_POLICY_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class BrainOutputProjectionPolicy:
    policy_id: str
    version: str
    requirements: tuple[BrainOutputProjectionRequirement, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        contexts = tuple(value.output_context for value in self.requirements)
        if not self.policy_id or not self.version:
            raise ValueError("BRAIN_OUTPUT_PROJECTION_POLICY_REQUIRED_FIELD")
        if contexts != tuple(sorted(contexts, key=lambda value: value.value)) or set(contexts) != set(BrainOutputContext):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_POLICY_CONTEXT_COVERAGE_REQUIRED")
        if self.fingerprint != brain_output_projection_policy_fingerprint(self):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_POLICY_FINGERPRINT_MISMATCH")

    def requirement_for(self, context: BrainOutputContext) -> BrainOutputProjectionRequirement:
        try:
            return next(value for value in self.requirements if value.output_context is context)
        except StopIteration as error:
            raise BrainOutputProjectionError("BRAIN_OUTPUT_PROJECTION_CONTEXT_UNDEFINED") from error


@dataclass(frozen=True, slots=True)
class BrainOutputProjection:
    """Deterministic view of coherent inputs; it has no action or recommendation."""

    projection_id: str
    canonical_instrument_id: str
    output_context: BrainOutputContext
    requested_as_of: datetime
    unified_state_id: str
    unified_state_fingerprint: str
    requirement_policy_id: str
    requirement_policy_version: str
    requirement_policy_fingerprint: str
    projection_policy_id: str
    projection_policy_version: str
    projection_policy_fingerprint: str
    evaluation_context_id: str
    evaluation_context_fingerprint: str
    status: BrainOutputProjectionStatus
    informational_only: bool
    ready_for_future_decision: bool
    sections: tuple[BrainOutputProjectionSection, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    lineage: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.projection_id, self.canonical_instrument_id, self.unified_state_id,
                    self.unified_state_fingerprint, self.evaluation_context_id,
                    self.evaluation_context_fingerprint, self.projection_policy_fingerprint)):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_REQUIRED_FIELD")
        if self.blockers:
            raise ValueError("BRAIN_OUTPUT_PROJECTION_BLOCKED_CONTEXT")
        if self.sections != tuple(sorted(self.sections, key=lambda value: value.kind.value)):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_SECTIONS_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_WARNINGS_NONCANONICAL")
        if self.lineage != tuple(sorted(set(self.lineage))):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_LINEAGE_NONCANONICAL")
        if self.fingerprint != brain_output_projection_fingerprint(self):
            raise ValueError("BRAIN_OUTPUT_PROJECTION_FINGERPRINT_MISMATCH")


_SECTION_DOMAINS: dict[BrainOutputProjectionSectionKind, tuple[IntelligenceEvidenceDomain, ...]] = {
    BrainOutputProjectionSectionKind.MARKET_CONTEXT: (IntelligenceEvidenceDomain.MACRO, IntelligenceEvidenceDomain.MARKET_DATA),
    BrainOutputProjectionSectionKind.SECTOR_CONTEXT: (IntelligenceEvidenceDomain.SECTOR,),
    BrainOutputProjectionSectionKind.COMPANY_RESEARCH: (
        IntelligenceEvidenceDomain.FUNDAMENTALS, IntelligenceEvidenceDomain.EARNINGS,
        IntelligenceEvidenceDomain.OWNERSHIP, IntelligenceEvidenceDomain.CORPORATE_ACTIONS,
    ),
    BrainOutputProjectionSectionKind.TECHNICAL_SETUP: (IntelligenceEvidenceDomain.TECHNICAL, IntelligenceEvidenceDomain.SETUP_OPPORTUNITY),
    BrainOutputProjectionSectionKind.NEWS_CATALYST: (IntelligenceEvidenceDomain.NEWS_CATALYSTS,),
    BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY: (
        IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY, IntelligenceEvidenceDomain.RELIABILITY,
        IntelligenceEvidenceDomain.REFERENCE_DATA,
    ),
    BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC: (IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,),
    BrainOutputProjectionSectionKind.DECISION_SCORE: (IntelligenceEvidenceDomain.DECISION_SCORE,),
    BrainOutputProjectionSectionKind.GATE_LINEAGE: (IntelligenceEvidenceDomain.SIX_GATES,),
    BrainOutputProjectionSectionKind.PORTFOLIO_CONTEXT: (),
    BrainOutputProjectionSectionKind.ENTRY_CONTEXT: (IntelligenceEvidenceDomain.SETUP_OPPORTUNITY,),
    BrainOutputProjectionSectionKind.ALERT_CONTEXT: (
        IntelligenceEvidenceDomain.NEWS_CATALYSTS, IntelligenceEvidenceDomain.RELIABILITY,
        IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,
    ),
}


def _requirement(context: BrainOutputContext, *sections: BrainOutputProjectionSectionKind) -> BrainOutputProjectionRequirement:
    return BrainOutputProjectionRequirement(context, tuple(sorted(sections, key=lambda value: value.value)))


def brain_output_projection_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"], version=values["version"],
        requirements=tuple((item.output_context.value, tuple(kind.value for kind in item.section_kinds))
                           for item in values["requirements"]),
    )


def brain_output_projection_policy_fingerprint(value: BrainOutputProjectionPolicy) -> str:
    return brain_output_projection_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def create_brain_output_projection_policy(*, policy_id: str, version: str,
                                          requirements: tuple[BrainOutputProjectionRequirement, ...]) -> BrainOutputProjectionPolicy:
    values = dict(policy_id=policy_id, version=version,
                  requirements=tuple(sorted(requirements, key=lambda value: value.output_context.value)))
    return BrainOutputProjectionPolicy(**values, fingerprint=brain_output_projection_policy_fingerprint_values(values))


CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY = create_brain_output_projection_policy(
    policy_id="brain-output-projection-sections",
    version="v1",
    requirements=(
        _requirement(BrainOutputContext.OPPORTUNITY_DISCOVERY, BrainOutputProjectionSectionKind.MARKET_CONTEXT, BrainOutputProjectionSectionKind.SECTOR_CONTEXT, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC, BrainOutputProjectionSectionKind.DECISION_SCORE, BrainOutputProjectionSectionKind.GATE_LINEAGE, BrainOutputProjectionSectionKind.ENTRY_CONTEXT),
        _requirement(BrainOutputContext.DEEP_ANALYSIS, BrainOutputProjectionSectionKind.MARKET_CONTEXT, BrainOutputProjectionSectionKind.SECTOR_CONTEXT, BrainOutputProjectionSectionKind.COMPANY_RESEARCH, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.NEWS_CATALYST, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC),
        _requirement(BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputProjectionSectionKind.MARKET_CONTEXT, BrainOutputProjectionSectionKind.SECTOR_CONTEXT, BrainOutputProjectionSectionKind.COMPANY_RESEARCH, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.NEWS_CATALYST, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC, BrainOutputProjectionSectionKind.PORTFOLIO_CONTEXT),
        _requirement(BrainOutputContext.SELL_TRIM_REVIEW, BrainOutputProjectionSectionKind.COMPANY_RESEARCH, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.NEWS_CATALYST, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC, BrainOutputProjectionSectionKind.PORTFOLIO_CONTEXT),
        _requirement(BrainOutputContext.ROTATION_REVIEW, BrainOutputProjectionSectionKind.MARKET_CONTEXT, BrainOutputProjectionSectionKind.SECTOR_CONTEXT, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC, BrainOutputProjectionSectionKind.DECISION_SCORE, BrainOutputProjectionSectionKind.GATE_LINEAGE, BrainOutputProjectionSectionKind.PORTFOLIO_CONTEXT),
        _requirement(BrainOutputContext.ENTRY_SETUP_REVIEW, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.DECISION_SCORE, BrainOutputProjectionSectionKind.GATE_LINEAGE, BrainOutputProjectionSectionKind.ENTRY_CONTEXT),
        _requirement(BrainOutputContext.ALERT_REVIEW, BrainOutputProjectionSectionKind.MARKET_CONTEXT, BrainOutputProjectionSectionKind.SECTOR_CONTEXT, BrainOutputProjectionSectionKind.TECHNICAL_SETUP, BrainOutputProjectionSectionKind.NEWS_CATALYST, BrainOutputProjectionSectionKind.RELIABILITY_INTEGRITY, BrainOutputProjectionSectionKind.RESEARCH_DIAGNOSTIC, BrainOutputProjectionSectionKind.ALERT_CONTEXT),
    ),
)


def project_brain_output(context: BrainOutputEvaluationContext, *,
                         projection_policy: BrainOutputProjectionPolicy = CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY) -> BrainOutputProjection:
    """Project only a previously validated context; no store or engine is called."""
    if not isinstance(context, BrainOutputEvaluationContext):
        raise BrainOutputProjectionError("BRAIN_OUTPUT_PROJECTION_VALIDATED_CONTEXT_REQUIRED")
    if not context.ready_for_output_decision:
        codes = ",".join(value.value for value in context.blockers)
        raise BrainOutputProjectionError(f"BRAIN_OUTPUT_PROJECTION_CONTEXT_NOT_READY:{codes}")
    requirement = projection_policy.requirement_for(context.output_context)
    references = {value.domain: value for value in context.evidence_references}
    sections = tuple(sorted((
        BrainOutputProjectionSection(
            kind=kind,
            evidence_references=tuple(
                references[domain] for domain in _SECTION_DOMAINS[kind] if domain in references
            ),
            portfolio_context_ref=context.portfolio_context_ref if kind is BrainOutputProjectionSectionKind.PORTFOLIO_CONTEXT else None,
        )
        for kind in requirement.section_kinds
    ), key=lambda value: value.kind.value))
    selected_references = tuple(reference for section in sections for reference in section.evidence_references)
    incomplete = any(reference.availability is not IntelligenceEvidenceAvailability.AVAILABLE for reference in selected_references)
    informational_only = context.output_context in {
        BrainOutputContext.DEEP_ANALYSIS, BrainOutputContext.PORTFOLIO_REVIEW,
        BrainOutputContext.SELL_TRIM_REVIEW, BrainOutputContext.ALERT_REVIEW,
    }
    status = BrainOutputProjectionStatus.PARTIAL if incomplete else (
        BrainOutputProjectionStatus.INFORMATIONAL if informational_only else BrainOutputProjectionStatus.READY
    )
    warnings = tuple(sorted(set(context.warnings).union(
        warning for reference in selected_references for warning in reference.warnings
    )))
    values = dict(
        canonical_instrument_id=context.canonical_instrument_id,
        output_context=context.output_context,
        requested_as_of=context.requested_as_of,
        unified_state_id=context.unified_state_id,
        unified_state_fingerprint=context.unified_state_fingerprint,
        requirement_policy_id=context.requirement_policy_id,
        requirement_policy_version=context.requirement_policy_version,
        requirement_policy_fingerprint=context.requirement_policy_fingerprint,
        projection_policy_id=projection_policy.policy_id,
        projection_policy_version=projection_policy.version,
        projection_policy_fingerprint=projection_policy.fingerprint,
        evaluation_context_id=context.evaluation_context_id,
        evaluation_context_fingerprint=context.fingerprint,
        status=status,
        informational_only=informational_only,
        ready_for_future_decision=context.ready_for_output_decision,
        sections=sections,
        blockers=(),
        warnings=warnings,
        lineage=tuple(sorted(set(context.state_origin_lineage).union({
            ("unified_state_id", context.unified_state_id),
            ("evaluation_context_id", context.evaluation_context_id),
        }))),
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["projection_id"] = f"brain-output-projection-{seed[:24]}"
    return BrainOutputProjection(**values, fingerprint=brain_output_projection_fingerprint_values(values))


def brain_output_projection_fingerprint(value: BrainOutputProjection) -> str:
    return brain_output_projection_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_output_projection_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({key: value for key, value in values.items() if key != "fingerprint"}))


def _semantic_values(values: dict) -> dict:
    return {key: _semantic_value(value) for key, value in sorted(values.items())}


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field: _semantic_value(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


__all__ = (
    "BrainOutputProjection", "BrainOutputProjectionError", "BrainOutputProjectionPolicy",
    "BrainOutputProjectionRequirement", "BrainOutputProjectionSection", "BrainOutputProjectionSectionKind",
    "BrainOutputProjectionStatus", "CURRENT_BRAIN_OUTPUT_PROJECTION_POLICY",
    "brain_output_projection_fingerprint", "brain_output_projection_policy_fingerprint",
    "create_brain_output_projection_policy", "project_brain_output",
)
