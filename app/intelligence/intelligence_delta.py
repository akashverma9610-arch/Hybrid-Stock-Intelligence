"""Pure, deterministic comparison of two immutable intelligence states."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceDependencyReference,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    UnifiedIntelligenceState,
)


class IntelligenceDeltaError(ValueError):
    pass


class IntelligenceDeltaStatus(StrEnum):
    NO_SEMANTIC_CHANGE = "NO_SEMANTIC_CHANGE"
    CHANGE_DETECTED = "CHANGE_DETECTED"


class IntelligenceDeltaChangeKind(StrEnum):
    EVIDENCE_ADDED = "EVIDENCE_ADDED"
    EVIDENCE_REMOVED = "EVIDENCE_REMOVED"
    EVIDENCE_REPLACED = "EVIDENCE_REPLACED"
    STATUS_CHANGED = "STATUS_CHANGED"
    FRESHNESS_CHANGED = "FRESHNESS_CHANGED"
    RELIABILITY_CHANGED = "RELIABILITY_CHANGED"
    INTEGRITY_CHANGED = "INTEGRITY_CHANGED"
    COMPLETENESS_CHANGED = "COMPLETENESS_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    VERSION_CHANGED = "VERSION_CHANGED"
    PROVENANCE_CHANGED = "PROVENANCE_CHANGED"
    WARNING_CHANGED = "WARNING_CHANGED"


@dataclass(frozen=True, slots=True)
class IntelligenceDomainDelta:
    domain: IntelligenceEvidenceDomain
    change_kinds: tuple[IntelligenceDeltaChangeKind, ...]
    previous_reference: IntelligenceEvidenceReference | None
    current_reference: IntelligenceEvidenceReference | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not self.change_kinds or self.change_kinds != tuple(sorted(set(self.change_kinds), key=lambda value: value.value)):
            raise IntelligenceDeltaError("INTELLIGENCE_DOMAIN_DELTA_CHANGE_KINDS_NONCANONICAL")
        if self.fingerprint != intelligence_domain_delta_fingerprint(self):
            raise IntelligenceDeltaError("INTELLIGENCE_DOMAIN_DELTA_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class IntelligenceDeltaImpactRequirement:
    domain: IntelligenceEvidenceDomain
    affected_output_contexts: tuple[BrainOutputContext, ...]

    def __post_init__(self) -> None:
        if self.affected_output_contexts != tuple(sorted(set(self.affected_output_contexts), key=lambda value: value.value)):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_IMPACT_CONTEXTS_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class IntelligenceDeltaImpactPolicy:
    policy_id: str
    version: str
    requirements: tuple[IntelligenceDeltaImpactRequirement, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        domains = tuple(value.domain for value in self.requirements)
        if not self.policy_id or not self.version or domains != tuple(sorted(domains, key=lambda value: value.value)):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_IMPACT_POLICY_NONCANONICAL")
        if set(domains) != set(IntelligenceEvidenceDomain):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_IMPACT_POLICY_COVERAGE_REQUIRED")
        if self.fingerprint != intelligence_delta_impact_policy_fingerprint(self):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_IMPACT_POLICY_FINGERPRINT_MISMATCH")

    def contexts_for(self, domain: IntelligenceEvidenceDomain) -> tuple[BrainOutputContext, ...]:
        return next(value.affected_output_contexts for value in self.requirements if value.domain is domain)


@dataclass(frozen=True, slots=True)
class IntelligenceDelta:
    delta_id: str
    canonical_instrument_id: str
    previous_state_id: str
    previous_state_fingerprint: str
    previous_as_of: object
    previous_state_schema_version: str
    previous_intelligence_contract_version: str
    current_state_id: str
    current_state_fingerprint: str
    current_as_of: object
    current_state_schema_version: str
    current_intelligence_contract_version: str
    status: IntelligenceDeltaStatus
    change_kinds: tuple[IntelligenceDeltaChangeKind, ...]
    changed_domains: tuple[IntelligenceEvidenceDomain, ...]
    unchanged_domains: tuple[IntelligenceEvidenceDomain, ...]
    domain_deltas: tuple[IntelligenceDomainDelta, ...]
    added_blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    removed_blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    added_degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    removed_degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    added_dependencies: tuple[IntelligenceDependencyReference, ...]
    removed_dependencies: tuple[IntelligenceDependencyReference, ...]
    affected_output_contexts: tuple[BrainOutputContext, ...]
    impact_policy_id: str
    impact_policy_version: str
    impact_policy_fingerprint: str
    warnings: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.delta_id, self.canonical_instrument_id, self.previous_state_id,
                    self.previous_state_fingerprint, self.current_state_id,
                    self.current_state_fingerprint, self.impact_policy_fingerprint)):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_REQUIRED_FIELD")
        if self.previous_as_of >= self.current_as_of:
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_CHRONOLOGY_REQUIRED")
        for values, code in (
            (self.change_kinds, "CHANGE_KINDS"), (self.changed_domains, "CHANGED_DOMAINS"),
            (self.unchanged_domains, "UNCHANGED_DOMAINS"), (self.affected_output_contexts, "AFFECTED_CONTEXTS"),
        ):
            if values != tuple(sorted(set(values), key=lambda value: value.value)):
                raise IntelligenceDeltaError(f"INTELLIGENCE_DELTA_{code}_NONCANONICAL")
        if self.domain_deltas != tuple(sorted(self.domain_deltas, key=lambda value: value.domain.value)):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_DOMAIN_DELTAS_NONCANONICAL")
        if self.status is IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE and (self.change_kinds or self.domain_deltas):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_NO_CHANGE_INCONSISTENT")
        if self.status is IntelligenceDeltaStatus.CHANGE_DETECTED and not self.change_kinds:
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_CHANGE_STATUS_INCONSISTENT")
        if self.fingerprint != intelligence_delta_fingerprint(self):
            raise IntelligenceDeltaError("INTELLIGENCE_DELTA_FINGERPRINT_MISMATCH")


def _contexts(*values: BrainOutputContext) -> tuple[BrainOutputContext, ...]:
    return tuple(sorted(set(values), key=lambda value: value.value))


_ALL_CONTEXTS = _contexts(*BrainOutputContext)
_MARKET_CONTEXTS = _contexts(BrainOutputContext.OPPORTUNITY_DISCOVERY, BrainOutputContext.DEEP_ANALYSIS,
                             BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.ROTATION_REVIEW,
                             BrainOutputContext.ALERT_REVIEW)
_COMPANY_CONTEXTS = _contexts(BrainOutputContext.DEEP_ANALYSIS, BrainOutputContext.PORTFOLIO_REVIEW,
                              BrainOutputContext.SELL_TRIM_REVIEW)
_TECHNICAL_CONTEXTS = _contexts(BrainOutputContext.OPPORTUNITY_DISCOVERY, BrainOutputContext.DEEP_ANALYSIS,
                                BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.SELL_TRIM_REVIEW,
                                BrainOutputContext.ROTATION_REVIEW, BrainOutputContext.ENTRY_SETUP_REVIEW,
                                BrainOutputContext.ALERT_REVIEW)
_SCORE_GATE_CONTEXTS = _contexts(BrainOutputContext.OPPORTUNITY_DISCOVERY, BrainOutputContext.ROTATION_REVIEW,
                                 BrainOutputContext.ENTRY_SETUP_REVIEW)


def _impact(domain: IntelligenceEvidenceDomain) -> IntelligenceDeltaImpactRequirement:
    contexts = {
        IntelligenceEvidenceDomain.MARKET_DATA: _MARKET_CONTEXTS,
        IntelligenceEvidenceDomain.MACRO: _MARKET_CONTEXTS,
        IntelligenceEvidenceDomain.SECTOR: _MARKET_CONTEXTS,
        IntelligenceEvidenceDomain.FUNDAMENTALS: _COMPANY_CONTEXTS,
        IntelligenceEvidenceDomain.EARNINGS: _COMPANY_CONTEXTS,
        IntelligenceEvidenceDomain.OWNERSHIP: _COMPANY_CONTEXTS,
        IntelligenceEvidenceDomain.CORPORATE_ACTIONS: _COMPANY_CONTEXTS,
        IntelligenceEvidenceDomain.TECHNICAL: _TECHNICAL_CONTEXTS,
        IntelligenceEvidenceDomain.SETUP_OPPORTUNITY: _TECHNICAL_CONTEXTS,
        IntelligenceEvidenceDomain.NEWS_CATALYSTS: _contexts(BrainOutputContext.DEEP_ANALYSIS, BrainOutputContext.PORTFOLIO_REVIEW, BrainOutputContext.SELL_TRIM_REVIEW, BrainOutputContext.ALERT_REVIEW),
        IntelligenceEvidenceDomain.DECISION_SCORE: _SCORE_GATE_CONTEXTS,
        IntelligenceEvidenceDomain.SIX_GATES: _SCORE_GATE_CONTEXTS,
        IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY: _ALL_CONTEXTS,
        IntelligenceEvidenceDomain.RELIABILITY: _ALL_CONTEXTS,
        IntelligenceEvidenceDomain.REFERENCE_DATA: _ALL_CONTEXTS,
        IntelligenceEvidenceDomain.RESEARCH_DIAGNOSTICS: _ALL_CONTEXTS,
    }[domain]
    return IntelligenceDeltaImpactRequirement(domain, contexts)


def create_intelligence_delta_impact_policy(*, policy_id: str, version: str,
                                             requirements: tuple[IntelligenceDeltaImpactRequirement, ...]) -> IntelligenceDeltaImpactPolicy:
    values = dict(policy_id=policy_id, version=version,
                  requirements=tuple(sorted(requirements, key=lambda value: value.domain.value)))
    return IntelligenceDeltaImpactPolicy(**values, fingerprint=intelligence_delta_impact_policy_fingerprint_values(values))


def intelligence_delta_impact_policy_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        policy_id=values["policy_id"], version=values["version"],
        requirements=tuple((item.domain.value, tuple(context.value for context in item.affected_output_contexts))
                           for item in values["requirements"]),
    )


def intelligence_delta_impact_policy_fingerprint(value: IntelligenceDeltaImpactPolicy) -> str:
    return intelligence_delta_impact_policy_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY = create_intelligence_delta_impact_policy(
    policy_id="intelligence-delta-output-impact", version="v1",
    requirements=tuple(_impact(domain) for domain in sorted(IntelligenceEvidenceDomain, key=lambda value: value.value)),
)


def compare_intelligence_states(previous_state: UnifiedIntelligenceState, current_state: UnifiedIntelligenceState, *,
                                impact_policy: IntelligenceDeltaImpactPolicy = CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY) -> IntelligenceDelta:
    """Compare supplied state artifacts only; this function performs no reads or work."""
    if not isinstance(previous_state, UnifiedIntelligenceState) or not isinstance(current_state, UnifiedIntelligenceState):
        raise IntelligenceDeltaError("INTELLIGENCE_DELTA_STATE_REQUIRED")
    if previous_state.canonical_instrument_id != current_state.canonical_instrument_id:
        raise IntelligenceDeltaError("INTELLIGENCE_DELTA_INSTRUMENT_MISMATCH")
    if previous_state.as_of >= current_state.as_of:
        raise IntelligenceDeltaError("INTELLIGENCE_DELTA_CHRONOLOGY_REQUIRED")
    previous = {item.domain: item for item in previous_state.evidence_references}
    current = {item.domain: item for item in current_state.evidence_references}
    domain_deltas = tuple(
        delta for domain in sorted(set(previous).union(current), key=lambda value: value.value)
        if (delta := _compare_domain(domain, previous.get(domain), current.get(domain))) is not None
    )
    added_blocking, removed_blocking = _difference(previous_state.blocking_domains, current_state.blocking_domains)
    added_degraded, removed_degraded = _difference(previous_state.degraded_domains, current_state.degraded_domains)
    added_dependencies, removed_dependencies = _difference(previous_state.dependency_lineage, current_state.dependency_lineage)
    change_kinds = {kind for delta in domain_deltas for kind in delta.change_kinds}
    if previous_state.completeness != current_state.completeness or added_blocking or removed_blocking or added_degraded or removed_degraded:
        change_kinds.add(IntelligenceDeltaChangeKind.COMPLETENESS_CHANGED)
    if added_dependencies or removed_dependencies:
        change_kinds.add(IntelligenceDeltaChangeKind.DEPENDENCY_CHANGED)
    version_changed = (
        previous_state.state_schema_version != current_state.state_schema_version
        or previous_state.intelligence_contract_version != current_state.intelligence_contract_version
    )
    if version_changed:
        change_kinds.add(IntelligenceDeltaChangeKind.VERSION_CHANGED)
    changed_domains = tuple(delta.domain for delta in domain_deltas)
    unchanged_domains = tuple(sorted(set(previous).intersection(current).difference(changed_domains), key=lambda value: value.value))
    affected = set()
    for domain in changed_domains:
        affected.update(impact_policy.contexts_for(domain))
    if change_kinds.difference({
        IntelligenceDeltaChangeKind.VERSION_CHANGED, IntelligenceDeltaChangeKind.DEPENDENCY_CHANGED,
        IntelligenceDeltaChangeKind.COMPLETENESS_CHANGED,
    }):
        pass
    elif change_kinds:
        affected.update(_ALL_CONTEXTS)
    warnings = ("INTELLIGENCE_DELTA_VERSION_LINEAGE_CHANGED",) if version_changed else ()
    values = dict(
        canonical_instrument_id=previous_state.canonical_instrument_id,
        previous_state_id=previous_state.state_id,
        previous_state_fingerprint=previous_state.fingerprint,
        previous_as_of=previous_state.as_of,
        previous_state_schema_version=previous_state.state_schema_version,
        previous_intelligence_contract_version=previous_state.intelligence_contract_version,
        current_state_id=current_state.state_id,
        current_state_fingerprint=current_state.fingerprint,
        current_as_of=current_state.as_of,
        current_state_schema_version=current_state.state_schema_version,
        current_intelligence_contract_version=current_state.intelligence_contract_version,
        status=IntelligenceDeltaStatus.CHANGE_DETECTED if change_kinds else IntelligenceDeltaStatus.NO_SEMANTIC_CHANGE,
        change_kinds=tuple(sorted(change_kinds, key=lambda value: value.value)),
        changed_domains=changed_domains,
        unchanged_domains=unchanged_domains,
        domain_deltas=domain_deltas,
        added_blocking_domains=added_blocking,
        removed_blocking_domains=removed_blocking,
        added_degraded_domains=added_degraded,
        removed_degraded_domains=removed_degraded,
        added_dependencies=added_dependencies,
        removed_dependencies=removed_dependencies,
        affected_output_contexts=tuple(sorted(affected, key=lambda value: value.value)),
        impact_policy_id=impact_policy.policy_id,
        impact_policy_version=impact_policy.version,
        impact_policy_fingerprint=impact_policy.fingerprint,
        warnings=warnings,
    )
    values["delta_id"] = intelligence_delta_id_from_values(values)
    return IntelligenceDelta(**values, fingerprint=intelligence_delta_fingerprint_values(values))


def _compare_domain(domain: IntelligenceEvidenceDomain, previous: IntelligenceEvidenceReference | None,
                    current: IntelligenceEvidenceReference | None) -> IntelligenceDomainDelta | None:
    if _reference_semantically_equal(previous, current):
        return None
    kinds: set[IntelligenceDeltaChangeKind] = set()
    if previous is None:
        kinds.add(IntelligenceDeltaChangeKind.EVIDENCE_ADDED)
    elif current is None:
        kinds.add(IntelligenceDeltaChangeKind.EVIDENCE_REMOVED)
    else:
        if (previous.artifact_ids, previous.artifact_fingerprints) != (current.artifact_ids, current.artifact_fingerprints):
            kinds.add(IntelligenceDeltaChangeKind.EVIDENCE_REPLACED)
        if previous.availability != current.availability:
            kinds.add(IntelligenceDeltaChangeKind.STATUS_CHANGED)
        if previous.freshness_status != current.freshness_status:
            kinds.add(IntelligenceDeltaChangeKind.FRESHNESS_CHANGED)
        if previous.source_provenance_fingerprint != current.source_provenance_fingerprint:
            kinds.add(IntelligenceDeltaChangeKind.PROVENANCE_CHANGED)
        if previous.historical_integrity_reference != current.historical_integrity_reference:
            kinds.add(IntelligenceDeltaChangeKind.INTEGRITY_CHANGED)
        if previous.warnings != current.warnings:
            kinds.add(IntelligenceDeltaChangeKind.WARNING_CHANGED)
        if previous.freshness_policy_reference != current.freshness_policy_reference:
            kinds.add(IntelligenceDeltaChangeKind.VERSION_CHANGED)
        if domain is IntelligenceEvidenceDomain.RELIABILITY and previous != current:
            kinds.add(IntelligenceDeltaChangeKind.RELIABILITY_CHANGED)
        if domain is IntelligenceEvidenceDomain.HISTORICAL_INTEGRITY and previous != current:
            kinds.add(IntelligenceDeltaChangeKind.INTEGRITY_CHANGED)
    values = dict(domain=domain, change_kinds=tuple(sorted(kinds, key=lambda value: value.value)),
                  previous_reference=previous, current_reference=current)
    return IntelligenceDomainDelta(**values, fingerprint=intelligence_domain_delta_fingerprint_values(values))


def _reference_semantically_equal(previous: IntelligenceEvidenceReference | None,
                                  current: IntelligenceEvidenceReference | None) -> bool:
    if previous is None or current is None:
        return previous is current
    return (
        previous.domain, previous.availability, previous.artifact_ids, previous.artifact_fingerprints,
        previous.freshness_status, previous.freshness_policy_reference,
        previous.source_provenance_fingerprint, previous.historical_integrity_reference, previous.warnings,
    ) == (
        current.domain, current.availability, current.artifact_ids, current.artifact_fingerprints,
        current.freshness_status, current.freshness_policy_reference,
        current.source_provenance_fingerprint, current.historical_integrity_reference, current.warnings,
    )


def _difference(previous, current):
    return tuple(sorted(set(current).difference(previous), key=_sort_key)), tuple(sorted(set(previous).difference(current), key=_sort_key))


def _sort_key(value):
    return value.value if hasattr(value, "value") else (value.invalidation_domain.value, value.artifact_id, value.artifact_fingerprint)


def intelligence_domain_delta_fingerprint(value: IntelligenceDomainDelta) -> str:
    return intelligence_domain_delta_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def intelligence_domain_delta_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values(values))


def intelligence_delta_fingerprint(value: IntelligenceDelta) -> str:
    return intelligence_delta_fingerprint_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def intelligence_delta_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({key: value for key, value in values.items() if key != "fingerprint"}))


def intelligence_delta_id_from_values(values: dict) -> str:
    seed = manifest_fingerprint(**_semantic_values({
        key: value for key, value in values.items() if key not in {"delta_id", "fingerprint"}
    }))
    return f"intelligence-delta-{seed[:24]}"


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
    "CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY", "IntelligenceDelta", "IntelligenceDeltaChangeKind",
    "IntelligenceDeltaError", "IntelligenceDeltaImpactPolicy", "IntelligenceDeltaImpactRequirement",
    "IntelligenceDeltaStatus", "IntelligenceDomainDelta", "compare_intelligence_states",
    "create_intelligence_delta_impact_policy", "intelligence_delta_fingerprint", "intelligence_delta_id_from_values",
)
