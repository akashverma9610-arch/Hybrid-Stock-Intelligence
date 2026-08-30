"""Canonical, fail-closed serialization for immutable intelligence deltas."""
from __future__ import annotations

from datetime import datetime

from app.domain.models import FreshnessStatus
from app.intelligence.intelligence_delta import (
    CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY,
    IntelligenceDelta,
    IntelligenceDeltaChangeKind,
    IntelligenceDeltaError,
    IntelligenceDeltaImpactPolicy,
    IntelligenceDeltaStatus,
    IntelligenceDomainDelta,
    compare_intelligence_states,
    intelligence_delta_id_from_values,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceDependencyReference,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceEvidenceReference,
    IntelligenceInvalidationDomain,
    UnifiedIntelligenceState,
)

INTELLIGENCE_DELTA_SERIALIZATION_SCHEMA = "intelligence-delta-serialization-v1"


class IntelligenceDeltaSerializationError(ValueError):
    pass


def serialize_intelligence_domain_delta(value: IntelligenceDomainDelta) -> dict:
    return {
        "domain": value.domain.value, "change_kinds": [item.value for item in value.change_kinds],
        "previous_reference": _reference_to_dict(value.previous_reference),
        "current_reference": _reference_to_dict(value.current_reference), "fingerprint": value.fingerprint,
    }


def deserialize_intelligence_domain_delta(payload: dict) -> IntelligenceDomainDelta:
    _require_fields(payload, {"domain", "change_kinds", "previous_reference", "current_reference", "fingerprint"})
    try:
        return IntelligenceDomainDelta(
            domain=IntelligenceEvidenceDomain(payload["domain"]),
            change_kinds=tuple(sorted({IntelligenceDeltaChangeKind(item) for item in payload["change_kinds"]}, key=lambda value: value.value)),
            previous_reference=_reference_from_dict(payload["previous_reference"]),
            current_reference=_reference_from_dict(payload["current_reference"]),
            fingerprint=_text(payload["fingerprint"]),
        )
    except (KeyError, TypeError, ValueError, IntelligenceDeltaError) as error:
        raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_INVALID_DOMAIN_DELTA") from error


def serialize_intelligence_delta(value: IntelligenceDelta) -> dict:
    return {
        "schema": INTELLIGENCE_DELTA_SERIALIZATION_SCHEMA,
        "delta_id": value.delta_id, "canonical_instrument_id": value.canonical_instrument_id,
        "previous_state_id": value.previous_state_id, "previous_state_fingerprint": value.previous_state_fingerprint,
        "previous_as_of": value.previous_as_of.isoformat(), "previous_state_schema_version": value.previous_state_schema_version,
        "previous_intelligence_contract_version": value.previous_intelligence_contract_version,
        "current_state_id": value.current_state_id, "current_state_fingerprint": value.current_state_fingerprint,
        "current_as_of": value.current_as_of.isoformat(), "current_state_schema_version": value.current_state_schema_version,
        "current_intelligence_contract_version": value.current_intelligence_contract_version,
        "status": value.status.value, "change_kinds": [item.value for item in value.change_kinds],
        "changed_domains": [item.value for item in value.changed_domains], "unchanged_domains": [item.value for item in value.unchanged_domains],
        "domain_deltas": [serialize_intelligence_domain_delta(item) for item in value.domain_deltas],
        "added_blocking_domains": [item.value for item in value.added_blocking_domains], "removed_blocking_domains": [item.value for item in value.removed_blocking_domains],
        "added_degraded_domains": [item.value for item in value.added_degraded_domains], "removed_degraded_domains": [item.value for item in value.removed_degraded_domains],
        "added_dependencies": [_dependency_to_dict(item) for item in value.added_dependencies], "removed_dependencies": [_dependency_to_dict(item) for item in value.removed_dependencies],
        "affected_output_contexts": [item.value for item in value.affected_output_contexts],
        "impact_policy_id": value.impact_policy_id, "impact_policy_version": value.impact_policy_version,
        "impact_policy_fingerprint": value.impact_policy_fingerprint, "warnings": list(value.warnings), "fingerprint": value.fingerprint,
    }


def deserialize_intelligence_delta(payload: dict) -> IntelligenceDelta:
    fields = {
        "schema", "delta_id", "canonical_instrument_id", "previous_state_id", "previous_state_fingerprint", "previous_as_of", "previous_state_schema_version", "previous_intelligence_contract_version", "current_state_id", "current_state_fingerprint", "current_as_of", "current_state_schema_version", "current_intelligence_contract_version", "status", "change_kinds", "changed_domains", "unchanged_domains", "domain_deltas", "added_blocking_domains", "removed_blocking_domains", "added_degraded_domains", "removed_degraded_domains", "added_dependencies", "removed_dependencies", "affected_output_contexts", "impact_policy_id", "impact_policy_version", "impact_policy_fingerprint", "warnings", "fingerprint",
    }
    _require_fields(payload, fields)
    if payload["schema"] != INTELLIGENCE_DELTA_SERIALIZATION_SCHEMA:
        raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_SCHEMA_UNSUPPORTED")
    try:
        values = dict(
            delta_id=_text(payload["delta_id"]), canonical_instrument_id=_text(payload["canonical_instrument_id"]),
            previous_state_id=_text(payload["previous_state_id"]), previous_state_fingerprint=_text(payload["previous_state_fingerprint"]), previous_as_of=_timestamp(payload["previous_as_of"]),
            previous_state_schema_version=_text(payload["previous_state_schema_version"]), previous_intelligence_contract_version=_text(payload["previous_intelligence_contract_version"]),
            current_state_id=_text(payload["current_state_id"]), current_state_fingerprint=_text(payload["current_state_fingerprint"]), current_as_of=_timestamp(payload["current_as_of"]),
            current_state_schema_version=_text(payload["current_state_schema_version"]), current_intelligence_contract_version=_text(payload["current_intelligence_contract_version"]),
            status=IntelligenceDeltaStatus(payload["status"]), change_kinds=_enums(payload["change_kinds"], IntelligenceDeltaChangeKind),
            changed_domains=_enums(payload["changed_domains"], IntelligenceEvidenceDomain), unchanged_domains=_enums(payload["unchanged_domains"], IntelligenceEvidenceDomain),
            domain_deltas=tuple(sorted((deserialize_intelligence_domain_delta(item) for item in payload["domain_deltas"]), key=lambda value: value.domain.value)),
            added_blocking_domains=_enums(payload["added_blocking_domains"], IntelligenceEvidenceDomain), removed_blocking_domains=_enums(payload["removed_blocking_domains"], IntelligenceEvidenceDomain),
            added_degraded_domains=_enums(payload["added_degraded_domains"], IntelligenceEvidenceDomain), removed_degraded_domains=_enums(payload["removed_degraded_domains"], IntelligenceEvidenceDomain),
            added_dependencies=tuple(sorted((_dependency_from_dict(item) for item in payload["added_dependencies"]), key=_dependency_key)), removed_dependencies=tuple(sorted((_dependency_from_dict(item) for item in payload["removed_dependencies"]), key=_dependency_key)),
            affected_output_contexts=_enums(payload["affected_output_contexts"], BrainOutputContext), impact_policy_id=_text(payload["impact_policy_id"]),
            impact_policy_version=_text(payload["impact_policy_version"]), impact_policy_fingerprint=_text(payload["impact_policy_fingerprint"]),
            warnings=tuple(sorted({_text(item) for item in payload["warnings"]})),
        )
        if values["delta_id"] != intelligence_delta_id_from_values(values):
            raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_ID_MISMATCH")
        return IntelligenceDelta(**values, fingerprint=_text(payload["fingerprint"]))
    except IntelligenceDeltaSerializationError:
        raise
    except (KeyError, TypeError, ValueError, IntelligenceDeltaError) as error:
        raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_INVALID") from error


def reconstruct_intelligence_delta(previous_state: UnifiedIntelligenceState, current_state: UnifiedIntelligenceState,
                                   expected_delta: IntelligenceDelta, *,
                                   impact_policy: IntelligenceDeltaImpactPolicy = CURRENT_INTELLIGENCE_DELTA_IMPACT_POLICY) -> IntelligenceDelta:
    actual = compare_intelligence_states(previous_state, current_state, impact_policy=impact_policy)
    if actual != expected_delta:
        raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_RECONSTRUCTION_MISMATCH")
    return actual


def _reference_to_dict(value: IntelligenceEvidenceReference | None):
    if value is None: return None
    return {"domain": value.domain.value, "availability": value.availability.value, "artifact_ids": list(value.artifact_ids), "artifact_fingerprints": list(value.artifact_fingerprints), "evidence_as_of": _time_or_none(value.evidence_as_of), "observed_at": _time_or_none(value.observed_at), "freshness_status": value.freshness_status.value, "freshness_policy_reference": value.freshness_policy_reference, "source_provenance_fingerprint": value.source_provenance_fingerprint, "historical_integrity_reference": value.historical_integrity_reference, "warnings": list(value.warnings)}


def _reference_from_dict(value):
    if value is None: return None
    return IntelligenceEvidenceReference(IntelligenceEvidenceDomain(value["domain"]), IntelligenceEvidenceAvailability(value["availability"]), tuple(sorted(set(value["artifact_ids"]))), tuple(sorted(set(value["artifact_fingerprints"]))), _time_or_none_parse(value["evidence_as_of"]), _time_or_none_parse(value["observed_at"]), FreshnessStatus(value["freshness_status"]), value["freshness_policy_reference"], value["source_provenance_fingerprint"], value["historical_integrity_reference"], tuple(sorted(set(value["warnings"]))))


def _dependency_to_dict(value): return {"invalidation_domain": value.invalidation_domain.value, "artifact_id": value.artifact_id, "artifact_fingerprint": value.artifact_fingerprint}
def _dependency_from_dict(value): return IntelligenceDependencyReference(IntelligenceInvalidationDomain(value["invalidation_domain"]), _text(value["artifact_id"]), _text(value["artifact_fingerprint"]))
def _dependency_key(value): return value.invalidation_domain.value, value.artifact_id, value.artifact_fingerprint
def _time_or_none(value): return None if value is None else value.isoformat()
def _time_or_none_parse(value): return None if value is None else _timestamp(value)
def _timestamp(value):
    parsed = datetime.fromisoformat(_text(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None: raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_TIMEZONE_REQUIRED")
    return parsed
def _text(value):
    if not isinstance(value, str) or not value: raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_TEXT_REQUIRED")
    return value
def _enums(values, enum): return tuple(sorted({enum(value) for value in values}, key=lambda value: value.value))
def _require_fields(payload, fields):
    if not isinstance(payload, dict) or set(payload) != fields: raise IntelligenceDeltaSerializationError("INTELLIGENCE_DELTA_SERIALIZATION_FIELDS_INVALID")


__all__ = ("INTELLIGENCE_DELTA_SERIALIZATION_SCHEMA", "IntelligenceDeltaSerializationError", "deserialize_intelligence_delta", "deserialize_intelligence_domain_delta", "reconstruct_intelligence_delta", "serialize_intelligence_delta", "serialize_intelligence_domain_delta")
