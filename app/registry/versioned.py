"""Explicit versions of the one canonical registry; V2 is research-only.

Artifact loading occurs only on an explicit SHADOW request. Existing V1
callers/constants are untouched; no latest-version selection is provided.
"""
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import lru_cache
import json
from pathlib import Path

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION, DIAGNOSTIC_RULES
from app.registry.models import DiagnosticRuleDefinition

V2_VERSION = "diagnostic-registry-v2-proposed"
V2_RULE_IDS = (16, 17, 19, 25, 26, 29)
PROPOSAL_FINGERPRINT = "sha256:668005237acd727ead86b19fca11a0fe9a1f640291dbe647a02cab989774a261"
APPROVAL_FINGERPRINT = "sha256:316936ca62d8b10accae8034f7e00ea7c5b17bcface796d3b9d79dd30c641013"


class RegistryMode(StrEnum):
    ACTIVE = "ACTIVE"
    SHADOW = "SHADOW"


@dataclass(frozen=True, slots=True)
class ApprovedShadowDefinition:
    rule_id: int
    canonical_name: str
    definition_json: str
    parent_definition_fingerprint: str


@dataclass(frozen=True, slots=True)
class VersionedDiagnosticRegistry:
    registry_version: str
    mode: RegistryMode
    rules: tuple[DiagnosticRuleDefinition | ApprovedShadowDefinition, ...]
    proposal_fingerprint: str | None
    approval_fingerprint: str | None

    @property
    def fingerprint(self) -> str:
        return content_fingerprint(self)


def _unique_object(pairs):
    value = dict(pairs)
    if len(value) != len(pairs):
        raise ValueError("REGISTRY_ARTIFACT_DUPLICATE_KEY")
    return value


def _artifact(name, expected, field):
    path = Path(__file__).resolve().parents[2] / "docs" / "architecture" / name
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    if value.get(field) != expected or content_fingerprint({k: v for k, v in value.items() if k != field}) != expected:
        raise ValueError("REGISTRY_GOVERNANCE_FINGERPRINT_MISMATCH")
    return value


def resolve_diagnostic_registry(version=DIAGNOSTIC_REGISTRY_VERSION, *, mode=RegistryMode.ACTIVE):
    try:
        mode = RegistryMode(mode)
    except (ValueError, TypeError):
        raise ValueError("REGISTRY_MODE_UNKNOWN") from None
    if version == DIAGNOSTIC_REGISTRY_VERSION:
        return VersionedDiagnosticRegistry(version, mode, DIAGNOSTIC_RULES, None, None)
    if version != V2_VERSION:
        raise ValueError("REGISTRY_VERSION_UNKNOWN")
    if mode is not RegistryMode.SHADOW:
        raise ValueError("V2_REGISTRY_NOT_ACTIVE")
    candidate = _artifact("FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_PROPOSED.json", PROPOSAL_FINGERPRINT, "proposal_fingerprint")
    approval = _artifact("FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json", APPROVAL_FINGERPRINT, "approval_fingerprint")
    if (approval["active"] or approval["approval_state"] != "GOVERNANCE_APPROVED_WITH_ACTIVATION_BLOCKERS"
            or approval["proposal_reference"]["proposal_fingerprint"] != PROPOSAL_FINGERPRINT
            or candidate["parent_registry_version"] != DIAGNOSTIC_REGISTRY_VERSION
            or candidate["parent_registry_semantic_fingerprint"] != content_fingerprint([asdict(r) for r in DIAGNOSTIC_RULES])
            or [r["rule_id"] for r in candidate["rules"]] != list(range(1, 62))
            or tuple(candidate["changed_rule_ids"]) != V2_RULE_IDS):
        raise ValueError("REGISTRY_GOVERNANCE_BINDING_INVALID")
    rows = []
    for row, parent in zip(candidate["rules"], DIAGNOSTIC_RULES, strict=True):
        if row["parent_definition_fingerprint"] != content_fingerprint(asdict(parent)):
            raise ValueError("REGISTRY_PARENT_DEFINITION_MISMATCH")
        if row["rule_id"] in V2_RULE_IDS:
            definition = row["definition"]
            rows.append(ApprovedShadowDefinition(parent.rule_id, definition["proposed_name"],
                canonical_json(definition), row["parent_definition_fingerprint"]))
        else:
            if row["change"] != "INHERIT_EXACT_PARENT" or "definition" in row:
                raise ValueError("REGISTRY_UNAPPROVED_SEMANTIC_CHANGE")
            rows.append(parent)
    return VersionedDiagnosticRegistry(version, mode, tuple(rows), PROPOSAL_FINGERPRINT, APPROVAL_FINGERPRINT)


@lru_cache(maxsize=1)
def approved_shadow_component_schema():
    """Immutable runtime schema derived from the pinned registry, not a second registry."""
    registry = resolve_diagnostic_registry(V2_VERSION, mode=RegistryMode.SHADOW)
    return tuple((r.rule_id, tuple(sorted((c["component_id"], c["role"])
        for c in json.loads(r.definition_json)["components"])))
        for r in registry.rules if isinstance(r, ApprovedShadowDefinition))
