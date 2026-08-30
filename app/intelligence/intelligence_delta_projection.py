"""Pure manual read model for an already validated intelligence delta."""
from __future__ import annotations
from dataclasses import dataclass
from app.historical.guard import manifest_fingerprint
from app.intelligence.intelligence_delta import IntelligenceDelta, IntelligenceDomainDelta
from app.intelligence.unified_state import BrainOutputContext, IntelligenceEvidenceDomain

@dataclass(frozen=True, slots=True)
class IntelligenceDomainDeltaProjection:
    domain: IntelligenceEvidenceDomain
    change_kinds: tuple
    previous_reference: object
    current_reference: object
    affected_output_contexts: tuple[BrainOutputContext, ...]

@dataclass(frozen=True, slots=True)
class IntelligenceDeltaProjection:
    projection_id: str
    canonical_instrument_id: str
    previous_state_id: str
    previous_state_fingerprint: str
    previous_as_of: object
    current_state_id: str
    current_state_fingerprint: str
    current_as_of: object
    overall_change_status: object
    changed_domain_count: int
    changed_domains: tuple[IntelligenceEvidenceDomain, ...]
    domain_changes: tuple[IntelligenceDomainDeltaProjection, ...]
    added_blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    removed_blocking_domains: tuple[IntelligenceEvidenceDomain, ...]
    added_degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    removed_degraded_domains: tuple[IntelligenceEvidenceDomain, ...]
    added_dependencies: tuple
    removed_dependencies: tuple
    affected_output_contexts: tuple[BrainOutputContext, ...]
    impact_policy_id: str
    impact_policy_version: str
    impact_policy_fingerprint: str
    delta_id: str
    delta_fingerprint: str
    warnings: tuple[str, ...]
    fingerprint: str

def project_intelligence_delta(delta: IntelligenceDelta) -> IntelligenceDeltaProjection:
    if not isinstance(delta, IntelligenceDelta): raise ValueError("INTELLIGENCE_DELTA_PROJECTION_DELTA_REQUIRED")
    domains = tuple(IntelligenceDomainDeltaProjection(d.domain,d.change_kinds,d.previous_reference,d.current_reference,tuple(c for c in delta.affected_output_contexts)) for d in delta.domain_deltas)
    values=dict(canonical_instrument_id=delta.canonical_instrument_id,previous_state_id=delta.previous_state_id,previous_state_fingerprint=delta.previous_state_fingerprint,previous_as_of=delta.previous_as_of,current_state_id=delta.current_state_id,current_state_fingerprint=delta.current_state_fingerprint,current_as_of=delta.current_as_of,overall_change_status=delta.status,changed_domain_count=len(delta.changed_domains),changed_domains=delta.changed_domains,domain_changes=domains,added_blocking_domains=delta.added_blocking_domains,removed_blocking_domains=delta.removed_blocking_domains,added_degraded_domains=delta.added_degraded_domains,removed_degraded_domains=delta.removed_degraded_domains,added_dependencies=delta.added_dependencies,removed_dependencies=delta.removed_dependencies,affected_output_contexts=delta.affected_output_contexts,impact_policy_id=delta.impact_policy_id,impact_policy_version=delta.impact_policy_version,impact_policy_fingerprint=delta.impact_policy_fingerprint,delta_id=delta.delta_id,delta_fingerprint=delta.fingerprint,warnings=delta.warnings)
    seed=manifest_fingerprint(**_semantic(values)); values['projection_id']=f"intelligence-delta-projection-{seed[:24]}"
    return IntelligenceDeltaProjection(**values,fingerprint=manifest_fingerprint(**_semantic(values)))
def _semantic(values):
    def x(v):
        if hasattr(v,'value'): return v.value
        if hasattr(v,'isoformat'): return v.isoformat()
        if isinstance(v,tuple): return tuple(x(i) for i in v)
        if hasattr(v,'__dataclass_fields__'): return {k:x(getattr(v,k)) for k in v.__dataclass_fields__}
        return v
    return {k:x(v) for k,v in sorted(values.items())}
