"""Immutable contract for a rebuildable shared-Brain intelligence projection.

Canonical stores remain the source of truth.  A ``UnifiedIntelligenceState``
only references their as-of eligible artifacts; it never copies raw provider
payloads, portfolio ownership, a score, or a decision.  Future delta
intelligence can compare state fingerprints without adding mutable state here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.domain.models import FreshnessStatus
from app.historical.guard import manifest_fingerprint


class UnifiedIntelligenceStateError(ValueError):
    pass


class IntelligenceEvidenceDomain(StrEnum):
    MARKET_DATA = "MARKET_DATA"
    FUNDAMENTALS = "FUNDAMENTALS"
    EARNINGS = "EARNINGS"
    OWNERSHIP = "OWNERSHIP"
    CORPORATE_ACTIONS = "CORPORATE_ACTIONS"
    NEWS_CATALYSTS = "NEWS_CATALYSTS"
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    TECHNICAL = "TECHNICAL"
    HISTORICAL_INTEGRITY = "HISTORICAL_INTEGRITY"
    REFERENCE_DATA = "REFERENCE_DATA"
    RELIABILITY = "RELIABILITY"
    RESEARCH_DIAGNOSTICS = "RESEARCH_DIAGNOSTICS"
    SETUP_OPPORTUNITY = "SETUP_OPPORTUNITY"
    DECISION_SCORE = "DECISION_SCORE"
    SIX_GATES = "SIX_GATES"


class IntelligenceEvidenceAvailability(StrEnum):
    """State-specific availability projection; missing data is never neutral."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class IntelligenceStateCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class IntelligenceInvalidationDomain(StrEnum):
    PRICE = "PRICE"
    FUNDAMENTALS = "FUNDAMENTALS"
    EARNINGS = "EARNINGS"
    NEWS = "NEWS"
    MACRO = "MACRO"
    SECTOR = "SECTOR"
    REFERENCE_DATA = "REFERENCE_DATA"
    POLICY = "POLICY"
    PORTFOLIO_CONTEXT = "PORTFOLIO_CONTEXT"


class BrainOutputContext(StrEnum):
    OPPORTUNITY_DISCOVERY = "OPPORTUNITY_DISCOVERY"
    DEEP_ANALYSIS = "DEEP_ANALYSIS"
    PORTFOLIO_REVIEW = "PORTFOLIO_REVIEW"
    SELL_TRIM_REVIEW = "SELL_TRIM_REVIEW"
    ROTATION_REVIEW = "ROTATION_REVIEW"
    ENTRY_SETUP_REVIEW = "ENTRY_SETUP_REVIEW"
    ALERT_REVIEW = "ALERT_REVIEW"


@dataclass(frozen=True, slots=True)
class IntelligenceEvidenceReference:
    """Bounded provenance reference for one evidence domain, never raw evidence."""

    domain: IntelligenceEvidenceDomain
    availability: IntelligenceEvidenceAvailability
    artifact_ids: tuple[str, ...]
    artifact_fingerprints: tuple[str, ...]
    evidence_as_of: datetime | None
    observed_at: datetime | None
    freshness_status: FreshnessStatus
    freshness_policy_reference: str | None
    source_provenance_fingerprint: str | None
    historical_integrity_reference: str | None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _aware_or_none(self.evidence_as_of, "evidence_as_of")
        _aware_or_none(self.observed_at, "observed_at")
        if self.artifact_ids != tuple(sorted(set(self.artifact_ids))):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_EVIDENCE_IDS_NONCANONICAL")
        if self.artifact_fingerprints != tuple(sorted(set(self.artifact_fingerprints))):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_EVIDENCE_FINGERPRINTS_NONCANONICAL")
        if self.warnings != tuple(sorted(set(self.warnings))):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_EVIDENCE_WARNINGS_NONCANONICAL")


@dataclass(frozen=True, slots=True)
class IntelligenceDependencyReference:
    """Immutable dependency/invalidation lineage; it does not listen for changes."""

    invalidation_domain: IntelligenceInvalidationDomain
    artifact_id: str
    artifact_fingerprint: str

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_fingerprint:
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_DEPENDENCY_REQUIRED_FIELD")


@dataclass(frozen=True, slots=True)
class PortfolioContextRef:
    """Optional output-only portfolio reference, deliberately outside stock intelligence."""

    portfolio_context_id: str
    portfolio_snapshot_id: str | None
    portfolio_context_fingerprint: str

    def __post_init__(self) -> None:
        if not self.portfolio_context_id or not self.portfolio_context_fingerprint:
            raise UnifiedIntelligenceStateError("PORTFOLIO_CONTEXT_REFERENCE_REQUIRED_FIELD")


@dataclass(frozen=True, slots=True)
class UnifiedIntelligenceState:
    """Reproducible as-of shared intelligence for one canonical instrument."""

    state_id: str
    canonical_instrument_id: str
    as_of: datetime
    evaluation_session: datetime | None
    state_schema_version: str
    intelligence_contract_version: str
    evidence_references: tuple[IntelligenceEvidenceReference, ...]
    completeness: IntelligenceStateCompleteness
    blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    dependency_lineage: tuple[IntelligenceDependencyReference, ...]
    origin_lineage: tuple[tuple[str, str], ...]
    previous_state_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.state_id, self.canonical_instrument_id, self.state_schema_version, self.intelligence_contract_version)):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_REQUIRED_FIELD")
        _aware_or_none(self.as_of, "as_of")
        _aware_or_none(self.evaluation_session, "evaluation_session")
        domains = tuple(reference.domain for reference in self.evidence_references)
        if domains != tuple(sorted(set(domains), key=lambda value: value.value)):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_EVIDENCE_DOMAINS_NONCANONICAL")
        if self.blocking_domains != tuple(sorted(set(self.blocking_domains), key=lambda value: value.value)):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_BLOCKING_DOMAINS_NONCANONICAL")
        if self.degraded_domains != tuple(sorted(set(self.degraded_domains), key=lambda value: value.value)):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_DEGRADED_DOMAINS_NONCANONICAL")
        if self.origin_lineage != tuple(sorted(set(self.origin_lineage))):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_ORIGIN_LINEAGE_NONCANONICAL")
        if self.fingerprint != unified_intelligence_state_fingerprint(self):
            raise UnifiedIntelligenceStateError("UNIFIED_INTELLIGENCE_STATE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class BrainOutputRequest:
    """A view/request context over shared state; it carries no action result."""

    request_id: str
    canonical_instrument_id: str
    intelligence_state_id: str
    intelligence_state_fingerprint: str
    output_context: BrainOutputContext
    portfolio_context: PortfolioContextRef | None
    requested_as_of: datetime
    origin_lineage: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.request_id, self.canonical_instrument_id, self.intelligence_state_id, self.intelligence_state_fingerprint)):
            raise UnifiedIntelligenceStateError("BRAIN_OUTPUT_REQUEST_REQUIRED_FIELD")
        _aware_or_none(self.requested_as_of, "requested_as_of")
        if self.origin_lineage != tuple(sorted(set(self.origin_lineage))):
            raise UnifiedIntelligenceStateError("BRAIN_OUTPUT_REQUEST_ORIGIN_LINEAGE_NONCANONICAL")
        if self.fingerprint != brain_output_request_fingerprint(self):
            raise UnifiedIntelligenceStateError("BRAIN_OUTPUT_REQUEST_FINGERPRINT_MISMATCH")


def create_unified_intelligence_state(
    *,
    canonical_instrument_id: str,
    as_of: datetime,
    evaluation_session: datetime | None,
    state_schema_version: str,
    intelligence_contract_version: str,
    evidence_references: tuple[IntelligenceEvidenceReference, ...],
    completeness: IntelligenceStateCompleteness,
    blocking_domains: tuple[IntelligenceEvidenceDomain, ...] = (),
    degraded_domains: tuple[IntelligenceEvidenceDomain, ...] = (),
    dependency_lineage: tuple[IntelligenceDependencyReference, ...] = (),
    origin_lineage: tuple[tuple[str, str], ...] = (),
    previous_state_fingerprint: str | None = None,
) -> UnifiedIntelligenceState:
    """Pure deterministic construction; no canonical evidence is read or copied."""
    values = dict(
        canonical_instrument_id=canonical_instrument_id,
        as_of=as_of,
        evaluation_session=evaluation_session,
        state_schema_version=state_schema_version,
        intelligence_contract_version=intelligence_contract_version,
        evidence_references=tuple(sorted(evidence_references, key=lambda value: value.domain.value)),
        completeness=completeness,
        blocking_domains=tuple(sorted(set(blocking_domains), key=lambda value: value.value)),
        degraded_domains=tuple(sorted(set(degraded_domains), key=lambda value: value.value)),
        dependency_lineage=tuple(sorted(set(dependency_lineage), key=lambda value: (value.invalidation_domain.value, value.artifact_id, value.artifact_fingerprint))),
        origin_lineage=tuple(sorted(set(origin_lineage))),
        previous_state_fingerprint=previous_state_fingerprint,
    )
    state_seed = manifest_fingerprint(**_state_semantic_values(values))
    values["state_id"] = f"unified-intelligence-state-{state_seed[:24]}"
    return UnifiedIntelligenceState(**values, fingerprint=unified_intelligence_state_fingerprint_values(values))


def create_brain_output_request(
    state: UnifiedIntelligenceState,
    *,
    output_context: BrainOutputContext,
    portfolio_context: PortfolioContextRef | None = None,
    requested_as_of: datetime | None = None,
    origin_lineage: tuple[tuple[str, str], ...] = (),
) -> BrainOutputRequest:
    """Derive a deterministic view request without changing shared state."""
    if not isinstance(state, UnifiedIntelligenceState):
        raise UnifiedIntelligenceStateError("BRAIN_OUTPUT_REQUEST_STATE_REQUIRED")
    requested = requested_as_of or state.as_of
    values = dict(
        canonical_instrument_id=state.canonical_instrument_id,
        intelligence_state_id=state.state_id,
        intelligence_state_fingerprint=state.fingerprint,
        output_context=output_context,
        portfolio_context=portfolio_context,
        requested_as_of=requested,
        origin_lineage=tuple(sorted(set(origin_lineage))),
    )
    request_seed = manifest_fingerprint(**_semantic_values(values))
    values["request_id"] = f"brain-output-request-{request_seed[:24]}"
    return BrainOutputRequest(**values, fingerprint=brain_output_request_fingerprint_values(values))


def unified_intelligence_state_fingerprint(value: UnifiedIntelligenceState) -> str:
    return unified_intelligence_state_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def unified_intelligence_state_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_state_semantic_values({field: value for field, value in values.items() if field != "fingerprint"}))


def brain_output_request_fingerprint(value: BrainOutputRequest) -> str:
    return brain_output_request_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def brain_output_request_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic_values({field: value for field, value in values.items() if field != "fingerprint"}))


def _aware_or_none(value: datetime | None, name: str) -> None:
    if value is None:
        return
    if value.tzinfo is None or value.utcoffset() is None:
        raise UnifiedIntelligenceStateError(f"UNIFIED_INTELLIGENCE_{name.upper()}_TIMEZONE_REQUIRED")


def _semantic_values(values: dict) -> dict:
    return {key: _semantic_value(value) for key, value in sorted(values.items())}


def _state_semantic_values(values: dict) -> dict:
    """Origin lineage is audit context, deliberately outside canonical state identity."""
    return _semantic_values({key: value for key, value in values.items() if key != "origin_lineage"})


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if hasattr(value, "__dataclass_fields__"):
        return {field: _semantic_value(getattr(value, field)) for field in value.__dataclass_fields__}
    return value
