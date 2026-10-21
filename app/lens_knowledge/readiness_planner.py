"""Read-only operational dependency planning for all 35 draft lenses.

This module NEVER approves a lens, infers fit, executes diagnostics, performs
network acquisition, or treats diagnostic eligibility as complete data readiness.
It layers supplied explicit source certifications over the pinned draft catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping

from app.lens_knowledge.assessment import load_catalog, catalog_fingerprint


class InputReadiness(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    STALE = "STALE"
    CONFLICTED = "CONFLICTED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class LensReadinessPlan:
    lens_id: str
    catalog_fingerprint: str
    required_diagnostics: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]
    ready_diagnostics: tuple[str, ...]
    blocked_diagnostics: tuple[str, ...]
    ready_dependencies: tuple[str, ...]
    blocked_dependencies: tuple[str, ...]
    source_readiness: str
    policy_status: str = "PROPOSED_NOT_ACTIVE"
    lens_fit: str = "NOT_EVALUATED"


def build_readiness_plans(
    *,
    diagnostic_states: Mapping[str, InputReadiness],
    dependency_states: Mapping[str, InputReadiness],
) -> tuple[LensReadinessPlan, ...]:
    """Planning receipts only, no readiness inference from missing entries.

    Inputs are external *certification* results from canonical owner checks;
    callers must not turn a generic diagnostic result into named-evidence READY.
    An explicit NOT_APPLICABLE is never counted as READY for a proposed
    requirement, because approved applicability semantics are still absent.
    """
    catalog = load_catalog()
    valid_diagnostics = {f"D{i:02d}" for i in range(1, 62)}
    required_gaps = {gap for lens in catalog for gap in lens.unresolved_dependencies}
    if set(diagnostic_states) - valid_diagnostics:
        raise ValueError("UNKNOWN_CANONICAL_DIAGNOSTIC")
    if set(dependency_states) - required_gaps:
        raise ValueError("UNKNOWN_LENS_DEPENDENCY")
    if any(not isinstance(s, InputReadiness) for s in (*diagnostic_states.values(), *dependency_states.values())):
        raise ValueError("INVALID_READINESS_STATE")

    fingerprint = catalog_fingerprint()
    rows = []
    for lens in catalog:
        diagnostic_ids = tuple(f"D{i:02d}" for i in lens.proposed_primary_diagnostics)
        gaps = lens.unresolved_dependencies
        ready_d = tuple(d for d in diagnostic_ids if diagnostic_states.get(d) is InputReadiness.READY)
        blocked_d = tuple(d for d in diagnostic_ids if diagnostic_states.get(d) is not InputReadiness.READY)
        ready_g = tuple(g for g in gaps if dependency_states.get(g) is InputReadiness.READY)
        blocked_g = tuple(g for g in gaps if dependency_states.get(g) is not InputReadiness.READY)
        known = [diagnostic_states.get(d, InputReadiness.MISSING) for d in diagnostic_ids]
        known += [dependency_states.get(g, InputReadiness.MISSING) for g in gaps]
        if any(x is InputReadiness.CONFLICTED for x in known):
            status = "CONFLICTED"
        elif any(x is InputReadiness.POLICY_BLOCKED for x in known):
            status = "POLICY_BLOCKED"
        elif any(x is InputReadiness.UNSUPPORTED for x in known):
            status = "UNSUPPORTED"
        elif any(x is InputReadiness.STALE for x in known):
            status = "STALE"
        elif not blocked_d and not blocked_g:
            status = "PROVISIONAL_INPUTS_PRESENT"
        elif any(x in (InputReadiness.PARTIAL, InputReadiness.READY) for x in known):
            status = "PARTIAL"
        else:
            status = "MISSING"
        rows.append(LensReadinessPlan(
            lens_id=lens.lens_id, catalog_fingerprint=fingerprint,
            required_diagnostics=diagnostic_ids,
            unresolved_dependencies=gaps,
            ready_diagnostics=ready_d, blocked_diagnostics=blocked_d,
            ready_dependencies=ready_g, blocked_dependencies=blocked_g,
            source_readiness=status,
        ))
    if fingerprint != catalog_fingerprint():
        raise ValueError("LENS_CATALOG_CHANGED_DURING_PLANNING")
    return tuple(rows)
