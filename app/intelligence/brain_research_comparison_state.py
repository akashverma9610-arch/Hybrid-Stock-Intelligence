"""Single-as-of factual Shared-Brain research projection.

This module deliberately builds *one* immutable research state from a supplied
``UnifiedIntelligenceState``.  It does not read a repository, call a provider,
compare two states, or attach thesis, opportunity, recommendation, portfolio,
gate, alert, or execution semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import (
    CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY,
    FrozenBrainResearchComparabilityPolicy,
    ResearchComparabilityDomain,
    ResearchComparisonMode,
    ResearchNonComparableCase,
    ResearchSourceEligibility,
)
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    UnifiedIntelligenceState,
)


class BrainResearchComparisonStateError(ValueError):
    """A supplied state or policy cannot safely define this factual projection."""


class ResearchMetricValueType(StrEnum):
    FACTUAL_VALUE = "FACTUAL_VALUE"
    ARTIFACT_REFERENCE = "ARTIFACT_REFERENCE"
    LIMITATION = "LIMITATION"


@dataclass(frozen=True, slots=True)
class ResearchMetricObservation:
    """One typed factual observation or bounded artifact reference.

    ``identity_components`` carries only deterministic comparison identity
    (period, scope, unit, methodology, dependency fingerprint, and similar
    factual fields).  It is intentionally not a mutable payload bag.
    """

    dimension: ResearchComparabilityDomain
    metric_id: str
    value_type: ResearchMetricValueType
    value: str | int | Decimal | None
    unit: str | None
    scale: str | None
    basis: str | None
    scope: str | None
    period_identity: str | None
    effective_at: datetime | None
    published_at: datetime | None
    lookback_or_window: str | None
    benchmark: str | None
    methodology_id: str | None
    methodology_version: str | None
    source_artifact_type: str | None
    source_artifact_fingerprint: str | None
    dependency_manifest_fingerprint: str | None
    source_eligibility: ResearchSourceEligibility
    freshness_status: FreshnessStatus
    reliability_lineage: str | None
    historical_integrity_lineage: str | None
    identity_components: tuple[tuple[str, str], ...] = ()
    lineage_components: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_METRIC_ID_REQUIRED")
        _aware_or_none(self.effective_at, "METRIC_EFFECTIVE_AT")
        _aware_or_none(self.published_at, "METRIC_PUBLISHED_AT")
        if self.value_type is ResearchMetricValueType.FACTUAL_VALUE and self.value is None:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_FACTUAL_VALUE_REQUIRED")
        if self.value_type is ResearchMetricValueType.ARTIFACT_REFERENCE and not self.source_artifact_fingerprint:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_ARTIFACT_FINGERPRINT_REQUIRED")
        _canonical_pairs(self.identity_components, "BRAIN_RESEARCH_METRIC_IDENTITY_NONCANONICAL")
        _canonical_lineage_components(self.lineage_components)
        _canonical_strings(self.warnings, "BRAIN_RESEARCH_METRIC_WARNINGS_NONCANONICAL")
        _canonical_strings(self.blockers, "BRAIN_RESEARCH_METRIC_BLOCKERS_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class ResearchComparabilityDescriptor:
    """Static identity required by a *future* pairwise comparator.

    It has no pairwise status field by design.  Eligibility and limitations are
    single-state facts; COMPARABLE/NON_COMPARABLE belongs to U14D-5F.
    """

    dimension: ResearchComparabilityDomain
    source_eligibility: ResearchSourceEligibility
    required_identity: tuple[str, ...]
    source_boundary: str
    prerequisites: tuple[str, ...]
    limitation_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.source_boundary or not self.required_identity:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_DESCRIPTOR_IDENTITY_REQUIRED")
        _canonical_strings(self.required_identity, "BRAIN_RESEARCH_DESCRIPTOR_IDENTITY_NONCANONICAL")
        _canonical_strings(self.prerequisites, "BRAIN_RESEARCH_DESCRIPTOR_PREREQUISITES_NONCANONICAL")
        _canonical_strings(self.limitation_codes, "BRAIN_RESEARCH_DESCRIPTOR_LIMITATIONS_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class ResearchDimensionState:
    """One factual evidence family at one as-of moment."""

    dimension: ResearchComparabilityDomain
    source_eligibility: ResearchSourceEligibility
    availability: IntelligenceEvidenceAvailability
    observations: tuple[ResearchMetricObservation, ...]
    descriptor: ResearchComparabilityDescriptor
    methodology_lineage: tuple[tuple[str, str], ...]
    dependency_lineage: tuple[tuple[str, str], ...]
    evidence_lineage: tuple[tuple[str, str], ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if self.descriptor.dimension is not self.dimension or self.descriptor.source_eligibility is not self.source_eligibility:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_DIMENSION_DESCRIPTOR_MISMATCH")
        if any(item.dimension is not self.dimension for item in self.observations):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_DIMENSION_OBSERVATION_MISMATCH")
        if self.observations != tuple(sorted(self.observations, key=_observation_key)):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_DIMENSION_OBSERVATIONS_NONCANONICAL")
        _canonical_pairs(self.methodology_lineage, "BRAIN_RESEARCH_DIMENSION_METHODOLOGY_NONCANONICAL")
        _canonical_pairs(self.dependency_lineage, "BRAIN_RESEARCH_DIMENSION_DEPENDENCY_NONCANONICAL")
        _canonical_pairs(self.evidence_lineage, "BRAIN_RESEARCH_DIMENSION_EVIDENCE_NONCANONICAL")
        _canonical_strings(self.warnings, "BRAIN_RESEARCH_DIMENSION_WARNINGS_NONCANONICAL")
        _canonical_strings(self.blockers, "BRAIN_RESEARCH_DIMENSION_BLOCKERS_NONCANONICAL")
        if self.fingerprint != research_dimension_state_fingerprint(self):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_DIMENSION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class BrainResearchComparisonState:
    """Immutable portfolio-independent factual projection at one PIT as-of."""

    state_id: str
    canonical_instrument_id: str
    as_of: datetime
    evaluation_session: datetime | None
    source_unified_state_id: str
    source_unified_state_fingerprint: str
    source_state_schema_version: str
    source_intelligence_contract_version: str
    state_schema_version: str
    research_methodology_id: str
    research_methodology_version: str
    comparability_policy_id: str
    comparability_policy_version: str
    comparability_policy_fingerprint: str
    comparison_mode: ResearchComparisonMode
    dimensions: tuple[ResearchDimensionState, ...]
    warnings: tuple[str, ...]
    blockers: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.state_id, self.canonical_instrument_id, self.source_unified_state_id,
                    self.source_unified_state_fingerprint, self.state_schema_version,
                    self.research_methodology_id, self.research_methodology_version,
                    self.comparability_policy_id, self.comparability_policy_version,
                    self.comparability_policy_fingerprint)):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_REQUIRED_FIELD")
        _aware_or_none(self.as_of, "STATE_AS_OF")
        _aware_or_none(self.evaluation_session, "STATE_EVALUATION_SESSION")
        if self.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_COMPARISON_MODE_UNSUPPORTED")
        if self.dimensions != tuple(sorted(self.dimensions, key=lambda item: item.dimension.value)):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_DIMENSIONS_NONCANONICAL")
        if tuple(item.dimension for item in self.dimensions) != tuple(sorted(ResearchComparabilityDomain, key=lambda item: item.value)):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_DIMENSION_COVERAGE_REQUIRED")
        _canonical_strings(self.warnings, "BRAIN_RESEARCH_STATE_WARNINGS_NONCANONICAL")
        _canonical_strings(self.blockers, "BRAIN_RESEARCH_STATE_BLOCKERS_NONCANONICAL")
        if self.fingerprint != brain_research_comparison_state_fingerprint(self):
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_FINGERPRINT_MISMATCH")


_UNIFIED_DOMAIN_MAP: dict[ResearchComparabilityDomain, tuple[IntelligenceEvidenceDomain, ...]] = {
    ResearchComparabilityDomain.FINANCIAL_RAW: (IntelligenceEvidenceDomain.FUNDAMENTALS, IntelligenceEvidenceDomain.EARNINGS),
    # Retain disclosure lineage, while the frozen policy continues to prohibit
    # synthesized normalized ownership-percentage comparison.
    ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE: (IntelligenceEvidenceDomain.OWNERSHIP,),
    ResearchComparabilityDomain.NEWS_CATALYST: (IntelligenceEvidenceDomain.NEWS_CATALYSTS,),
    ResearchComparabilityDomain.CORPORATE_ACTION: (IntelligenceEvidenceDomain.CORPORATE_ACTIONS,),
    # The unified projection keeps native integrity as its own bounded
    # reference.  Retain that lineage with price evidence; never infer a
    # native integrity status from its availability projection.
    ResearchComparabilityDomain.MARKET_PRICE: (
        IntelligenceEvidenceDomain.MARKET_DATA,
        IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY,
    ),
    ResearchComparabilityDomain.SECTOR_IDENTITY: (IntelligenceEvidenceDomain.SECTOR, IntelligenceEvidenceDomain.REFERENCE_DATA),
    ResearchComparabilityDomain.PRE_BREAKOUT_SETUP: (IntelligenceEvidenceDomain.TECHNICAL, IntelligenceEvidenceDomain.SETUP_OPPORTUNITY),
    ResearchComparabilityDomain.PRE_BREAKOUT_CANDIDATE: (IntelligenceEvidenceDomain.SETUP_OPPORTUNITY,),
    ResearchComparabilityDomain.ENTRY_ECONOMICS: (IntelligenceEvidenceDomain.SETUP_OPPORTUNITY,),
    ResearchComparabilityDomain.DIAGNOSTIC: (IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS,),
    ResearchComparabilityDomain.DECISION_SCORE: (IntelligenceEvidenceDomain.DECISION_SCORE,),
    ResearchComparabilityDomain.RELIABILITY: (IntelligenceEvidenceDomain.RELIABILITY,),
    ResearchComparabilityDomain.MACRO_STATE: (IntelligenceEvidenceDomain.MACRO,),
    ResearchComparabilityDomain.TECHNICAL_MATERIALIZATION: (IntelligenceEvidenceDomain.TECHNICAL,),
    ResearchComparabilityDomain.CORPORATE_ACTION_REFERENCE: (IntelligenceEvidenceDomain.CORPORATE_ACTIONS,),
}


def build_brain_research_comparison_state(
    unified_state: UnifiedIntelligenceState,
    *,
    policy: FrozenBrainResearchComparabilityPolicy,
    explicit_observations: tuple[ResearchMetricObservation, ...] = (),
    state_schema_version: str = "brain-research-comparison-state-v1",
    research_methodology_id: str = "shared-brain-research-comparison",
    research_methodology_version: str = "v1",
) -> BrainResearchComparisonState:
    """Create one deterministic factual state from already-materialized input.

    No repository or provider is accepted here: all raw/durable values beyond
    Unified State lineage must be supplied explicitly as typed observations.
    """
    if not isinstance(unified_state, UnifiedIntelligenceState):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_UNIFIED_STATE_REQUIRED")
    _validate_policy(policy)
    if not state_schema_version or not research_methodology_id or not research_methodology_version:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_STATE_METHODOLOGY_REQUIRED")
    _validate_source_state(unified_state)
    if explicit_observations != tuple(sorted(explicit_observations, key=_observation_key)):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_EXPLICIT_OBSERVATIONS_NONCANONICAL")
    for observation in explicit_observations:
        if observation.published_at is not None and observation.published_at > unified_state.as_of:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_OBSERVATION_AFTER_AS_OF")
        if observation.effective_at is not None and observation.effective_at > unified_state.as_of:
            raise BrainResearchComparisonStateError("BRAIN_RESEARCH_OBSERVATION_EFFECTIVE_AFTER_AS_OF")
    observations_by_dimension: dict[ResearchComparabilityDomain, list[ResearchMetricObservation]] = {
        domain: [] for domain in ResearchComparabilityDomain
    }
    for observation in explicit_observations:
        observations_by_dimension[observation.dimension].append(observation)
    references = {value.domain: value for value in unified_state.evidence_references}
    dimensions = tuple(
        _build_dimension(domain, references, observations_by_dimension[domain], policy)
        for domain in sorted(ResearchComparabilityDomain, key=lambda item: item.value)
    )
    warnings = tuple(sorted({warning for dimension in dimensions for warning in dimension.warnings}))
    blockers = tuple(sorted({blocker for dimension in dimensions for blocker in dimension.blockers}))
    values = dict(
        canonical_instrument_id=unified_state.canonical_instrument_id,
        as_of=unified_state.as_of,
        evaluation_session=unified_state.evaluation_session,
        source_unified_state_id=unified_state.state_id,
        source_unified_state_fingerprint=unified_state.fingerprint,
        source_state_schema_version=unified_state.state_schema_version,
        source_intelligence_contract_version=unified_state.intelligence_contract_version,
        state_schema_version=state_schema_version,
        research_methodology_id=research_methodology_id,
        research_methodology_version=research_methodology_version,
        comparability_policy_id=policy.policy_id,
        comparability_policy_version=policy.version,
        comparability_policy_fingerprint=policy.fingerprint,
        comparison_mode=policy.comparison_mode,
        dimensions=dimensions,
        warnings=warnings,
        blockers=blockers,
    )
    seed = manifest_fingerprint(**_semantic_values(values))
    values["state_id"] = f"brain-research-comparison-state-{seed[:24]}"
    return BrainResearchComparisonState(
        **values, fingerprint=brain_research_comparison_state_fingerprint_values(values)
    )


def _build_dimension(
    domain: ResearchComparabilityDomain,
    references: dict[IntelligenceEvidenceDomain, IntelligenceEvidenceReference],
    explicit: list[ResearchMetricObservation],
    policy: FrozenBrainResearchComparabilityPolicy,
) -> ResearchDimensionState:
    source_rule = next(item for item in policy.source_rules if item.domain is domain)
    domain_rule = next((item for item in policy.domain_rules if item.domain is domain), None)
    relevant = tuple(references[value] for value in _UNIFIED_DOMAIN_MAP.get(domain, ()) if value in references)
    limitations: set[str] = set()
    if source_rule.eligibility is ResearchSourceEligibility.UNSUPPORTED:
        limitations.add(_unsupported_code(domain))
    if source_rule.eligibility is ResearchSourceEligibility.CURRENT_ONLY:
        limitations.add("CURRENT_ONLY_EVIDENCE_NOT_HISTORICALLY_RETROJECTED")
    if not relevant and not explicit and source_rule.eligibility is not ResearchSourceEligibility.UNSUPPORTED:
        limitations.add("SOURCE_EVIDENCE_UNAVAILABLE")
    availability = _availability(relevant, source_rule.eligibility)
    observations = [*_reference_observations(domain, relevant, source_rule.eligibility), *explicit]
    warnings = set(limitations)
    blockers: set[str] = set()
    for reference in relevant:
        warnings.update(reference.warnings)
        if reference.availability is IntelligenceEvidenceAvailability.STALE:
            warnings.add("EVIDENCE_STALE")
            blockers.add("EVIDENCE_STALE")
        if reference.availability is IntelligenceEvidenceAvailability.CONFLICTED:
            blockers.add("RELIABILITY_OR_INTEGRITY_CONFLICTED")
        if reference.availability is IntelligenceEvidenceAvailability.UNAVAILABLE:
            blockers.add("REQUIRED_EVIDENCE_UNAVAILABLE")
    if source_rule.eligibility is ResearchSourceEligibility.UNSUPPORTED:
        blockers.update(limitations)
    descriptor = ResearchComparabilityDescriptor(
        dimension=domain,
        source_eligibility=source_rule.eligibility,
        # The frozen policy intentionally has no extra parity rule for every
        # source domain.  In that case retain the source prerequisites rather
        # than inventing a new pairwise rule at this single-state boundary.
        required_identity=(domain_rule.required_identity if domain_rule is not None else source_rule.prerequisites),
        source_boundary=source_rule.source_boundary,
        prerequisites=source_rule.prerequisites,
        limitation_codes=tuple(sorted(limitations)),
    )
    evidence_lineage = tuple(sorted(
        (f"{reference.domain.value}:{artifact_id}", fingerprint)
        for reference in relevant
        for artifact_id, fingerprint in zip(reference.artifact_ids, reference.artifact_fingerprints)
    ))
    methodology_lineage = tuple(sorted({
        ("comparability_policy", policy.fingerprint),
        ("source_boundary", source_rule.source_boundary),
        *( ("freshness_policy", value.freshness_policy_reference) for value in relevant if value.freshness_policy_reference ),
    }))
    # FUNDAMENTALS and EARNINGS can intentionally reference the same canonical
    # financial-fact integrity artifact.  Retain that dependency once: it is
    # one immutable lineage dependency, not two competing values for the same
    # dependency key.
    dependency_lineage = tuple(sorted({
        ("historical_integrity", value.historical_integrity_reference)
        for value in relevant if value.historical_integrity_reference
    }))
    values = dict(
        dimension=domain,
        source_eligibility=source_rule.eligibility,
        availability=availability,
        observations=tuple(sorted(observations, key=_observation_key)),
        descriptor=descriptor,
        methodology_lineage=methodology_lineage,
        dependency_lineage=dependency_lineage,
        evidence_lineage=evidence_lineage,
        warnings=tuple(sorted(warnings)),
        blockers=tuple(sorted(blockers)),
    )
    return ResearchDimensionState(
        **values, fingerprint=research_dimension_state_fingerprint_values(values)
    )


def _reference_observations(
    domain: ResearchComparabilityDomain,
    references: tuple[IntelligenceEvidenceReference, ...],
    eligibility: ResearchSourceEligibility,
) -> tuple[ResearchMetricObservation, ...]:
    values: list[ResearchMetricObservation] = []
    for reference in references:
        for artifact_id, fingerprint in zip(reference.artifact_ids, reference.artifact_fingerprints):
            values.append(ResearchMetricObservation(
                dimension=domain,
                metric_id=f"{reference.domain.value}:{artifact_id}",
                value_type=ResearchMetricValueType.ARTIFACT_REFERENCE,
                value=None,
                unit=None, scale=None, basis=None, scope=None, period_identity=None,
                effective_at=reference.evidence_as_of,
                published_at=reference.observed_at,
                lookback_or_window=None, benchmark=None,
                methodology_id=None, methodology_version=None,
                source_artifact_type=reference.domain.value,
                source_artifact_fingerprint=fingerprint,
                dependency_manifest_fingerprint=reference.source_provenance_fingerprint,
                source_eligibility=eligibility,
                freshness_status=reference.freshness_status,
                reliability_lineage=None,
                historical_integrity_lineage=reference.historical_integrity_reference,
                identity_components=tuple(sorted({
                    ("artifact_id", artifact_id),
                    ("availability", reference.availability.value),
                })),
                warnings=reference.warnings,
                blockers=("EVIDENCE_STALE",) if reference.availability is IntelligenceEvidenceAvailability.STALE else (),
            ))
    return tuple(values)


def _availability(
    references: tuple[IntelligenceEvidenceReference, ...], eligibility: ResearchSourceEligibility,
) -> IntelligenceEvidenceAvailability:
    if eligibility is ResearchSourceEligibility.UNSUPPORTED:
        return IntelligenceEvidenceAvailability.NOT_APPLICABLE
    if not references:
        return IntelligenceEvidenceAvailability.UNAVAILABLE
    statuses = {item.availability for item in references}
    for status in (
        IntelligenceEvidenceAvailability.CONFLICTED,
        IntelligenceEvidenceAvailability.STALE,
        IntelligenceEvidenceAvailability.UNAVAILABLE,
        IntelligenceEvidenceAvailability.PARTIAL,
    ):
        if status in statuses:
            return status
    return IntelligenceEvidenceAvailability.AVAILABLE


def _unsupported_code(domain: ResearchComparabilityDomain) -> str:
    if domain is ResearchComparabilityDomain.OWNERSHIP_PERCENTAGE:
        return ResearchNonComparableCase.OWNERSHIP_PERCENTAGES_UNSUPPORTED.value
    return "VALUATION_COMPARISON_UNSUPPORTED"


def _validate_policy(policy: FrozenBrainResearchComparabilityPolicy) -> None:
    expected = CURRENT_FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY
    if not isinstance(policy, FrozenBrainResearchComparabilityPolicy):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_COMPARABILITY_POLICY_REQUIRED")
    if (policy.policy_id, policy.version, policy.fingerprint) != (expected.policy_id, expected.version, expected.fingerprint):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_COMPARABILITY_POLICY_IDENTITY_INVALID")
    if policy.comparison_mode is not ResearchComparisonMode.KNOWLEDGE_AT_THE_TIME:
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_COMPARABILITY_POLICY_MODE_UNSUPPORTED")


def _validate_source_state(state: UnifiedIntelligenceState) -> None:
    _aware_or_none(state.as_of, "SOURCE_AS_OF")
    for reference in state.evidence_references:
        for value in (reference.evidence_as_of, reference.observed_at):
            if value is not None and value > state.as_of:
                raise BrainResearchComparisonStateError("BRAIN_RESEARCH_SOURCE_EVIDENCE_AFTER_AS_OF")


def research_dimension_state_fingerprint(value: ResearchDimensionState) -> str:
    return research_dimension_state_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def research_dimension_state_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def brain_research_comparison_state_fingerprint(value: BrainResearchComparisonState) -> str:
    return brain_research_comparison_state_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_research_comparison_state_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({key: value for key, value in values.items() if key != "fingerprint"}))


def research_metric_observation_fingerprint(value: ResearchMetricObservation) -> str:
    """Deterministic generic artifact identity, including non-slot lineage."""

    return manifest_fingerprint(**_semantic_value(value))


def _observation_key(value: ResearchMetricObservation) -> tuple[str, str, str, str]:
    return value.dimension.value, value.metric_id, value.value_type.value, value.source_artifact_fingerprint or ""


def _aware_or_none(value: datetime | None, code: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise BrainResearchComparisonStateError(f"BRAIN_RESEARCH_{code}_TIMEZONE_REQUIRED")


def _canonical_strings(values: tuple[str, ...], code: str) -> None:
    if values != tuple(sorted(set(values))):
        raise BrainResearchComparisonStateError(code)


def _canonical_pairs(values: tuple[tuple[str, str], ...], code: str) -> None:
    if values != tuple(sorted(set(values))) or any(not key or not value for key, value in values):
        raise BrainResearchComparisonStateError(code)


def _canonical_lineage_components(values: tuple[tuple[str, str], ...]) -> None:
    _canonical_pairs(values, "BRAIN_RESEARCH_METRIC_LINEAGE_NONCANONICAL")
    keys = tuple(key for key, _ in values)
    if len(keys) != len(set(keys)):
        raise BrainResearchComparisonStateError("BRAIN_RESEARCH_METRIC_LINEAGE_KEYS_DUPLICATE")


def _semantic_values(values: dict) -> dict:
    return {key: _semantic_value(value) for key, value in sorted(values.items())}


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if isinstance(value, ResearchMetricObservation):
        return {
            field: _semantic_value(getattr(value, field))
            for field in value.__dataclass_fields__
            if field != "lineage_components" or value.lineage_components
        }
    if hasattr(value, "__dataclass_fields__"):
        return {field: _semantic_value(getattr(value, field)) for field in value.__dataclass_fields__}
    return value


__all__ = (
    "BrainResearchComparisonState", "BrainResearchComparisonStateError",
    "ResearchComparabilityDescriptor", "ResearchDimensionState", "ResearchMetricObservation",
    "ResearchMetricValueType", "brain_research_comparison_state_fingerprint",
    "build_brain_research_comparison_state", "research_dimension_state_fingerprint",
    "research_metric_observation_fingerprint",
)
