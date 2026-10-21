"""Assess draft lens dependencies against existing diagnostic results.

This module performs no acquisition, calculation, strategy qualification or
portfolio action. Catalog requirements are design inputs, not approved gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

from app.diagnostics.models import EvaluatedDiagnostic, EvaluationEligibility
from app.domain.models import DiagnosticStrategyLineageType, canonical_diagnostic_result_fingerprint
from app.domain.canonical_diagnostic_strategy import CANONICAL_61_STRATEGY_REFERENCE, CANONICAL_61_SEMANTIC_FINGERPRINT

_ROOT = Path(__file__).resolve().parent
_DIMENSIONS = frozenset({"FUNDAMENTALS", "EARNINGS", "TECHNICALS", "VALUATION", "CATALYST_NEWS", "SECTOR_MACRO", "FLOW", "BALANCE_SHEET_CASH_FLOW", "MANAGEMENT_GOVERNANCE", "LIQUIDITY_EXITABILITY"})


def catalog_fingerprint() -> str:
    """Bind a receipt to the exact imported matrix and taxonomy bytes."""
    paths = [_ROOT / "STRATEGY_DEPENDENCY_MATRIX.json", *sorted((_ROOT / "taxonomy").glob("*.json"))]
    digest = sha256()
    for path in paths:
        name = path.relative_to(_ROOT).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(name).to_bytes(8, "big")); digest.update(name)
        digest.update(len(content).to_bytes(8, "big")); digest.update(content)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class LensDefinition:
    lens_id: str
    name: str
    version: str
    proposed_primary_diagnostics: tuple[int, ...]
    proposed_primary_evidence: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LensAssessment:
    lens_id: str
    lens_version: str
    instrument_id: str
    as_of: datetime
    status: str
    available_primary_diagnostics: tuple[int, ...]
    unavailable_primary_diagnostics: tuple[int, ...]
    diagnostic_result_ids: tuple[str, ...]
    unresolved_dependencies: tuple[str, ...]
    reasons: tuple[str, ...]


@lru_cache(maxsize=1)
def load_catalog() -> tuple[LensDefinition, ...]:
    """Load and validate the pinned 35-lens draft and its 350-row matrix."""
    matrix = json.loads((_ROOT / "STRATEGY_DEPENDENCY_MATRIX.json").read_text(encoding="utf-8"))
    if matrix.get("status") != "DESIGN_ONLY_NOT_ACTIVE" or not matrix.get("requirements_are_design_only"):
        raise ValueError("Lens matrix must remain a non-active design")
    rows = matrix["rows"]
    files = sorted((_ROOT / "taxonomy").glob("*.json"))
    if len(files) != 35 or len(rows) != 350 or set(matrix["dimensions"]) != _DIMENSIONS:
        raise ValueError("Invalid lens catalog size or dimensions")
    definitions = []
    seen = set()
    for path in files:
        item = json.loads(path.read_text(encoding="utf-8"))
        lens_id = item["strategy_archetype_id"]
        if (path.stem != lens_id or lens_id in seen or item.get("activation_status") != "NOT_ACTIVE"
                or item.get("authority_status") != "PROPOSED_NOT_ACTIVE"
                or not item.get("requirements_are_design_only")):
            raise ValueError("Invalid or active lens definition")
        seen.add(lens_id)
        matching = [row for row in rows if row["strategy_archetype_id"] == lens_id]
        if len(matching) != 10 or {row["dependency_dimension"] for row in matching} != _DIMENSIONS:
            raise ValueError("Invalid lens matrix rows")
        if any(row["dependency_strength"] != item["dependency_strengths"][row["dependency_dimension"]] for row in matching):
            raise ValueError("Lens matrix and taxonomy disagree")
        primary = [row for row in matching if row["dependency_strength"] == "PRIMARY"]
        raw_ids = [value for row in matching for value in row["diagnostic_ids"]]
        if any(value not in {f"D{i:02}" for i in range(1, 62)} for value in raw_ids):
            raise ValueError("Malformed diagnostic ID")
        ids = {int(value[1:]) for row in primary for value in row["diagnostic_ids"] if value.startswith("D") and value[1:].isdigit()}
        if any(not 1 <= value <= 61 for value in ids):
            raise ValueError("Diagnostic ID outside canonical registry")
        definitions.append(LensDefinition(lens_id, item["name"], item["version"], tuple(sorted(ids)),
            tuple(sorted({value for row in primary for value in row["evidence_families"]})),
            tuple(sorted({value["dependency_id"] for value in item["future_evidence_dependencies"]}))))
    if {row["strategy_archetype_id"] for row in rows} != seen:
        raise ValueError("Unknown lens in matrix")
    return tuple(definitions)


def assess_lenses(*, instrument_id: str, as_of: datetime,
                  diagnostics: tuple[EvaluatedDiagnostic, ...]) -> tuple[LensAssessment, ...]:
    """Report draft diagnostic coverage, never infer a fit from readiness alone.

    Input must come from the caller's existing stored-data diagnostic pipeline.
    Conflicting identity, cutoff or duplicate rule is rejected, not mixed.
    """
    if not instrument_id or as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("Canonical instrument and timezone-aware cutoff required")
    cutoff = as_of.astimezone(timezone.utc)
    by_id: dict[int, EvaluatedDiagnostic] = {}
    for value in diagnostics:
        record = value.record
        if record.strategy_lineage_type is DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY:
            if (record.strategy_version != CANONICAL_61_STRATEGY_REFERENCE
                    or record.canonical_strategy_fingerprint != CANONICAL_61_SEMANTIC_FINGERPRINT
                    or record.diagnostic_fingerprint != canonical_diagnostic_result_fingerprint(record)
                    or tuple(x.id for x in value.evidence) != record.evidence_ids
                    or any(x.timestamp > cutoff or x.provenance.retrieved_timestamp > cutoff for x in value.evidence)):
                raise ValueError("LENS_CANONICAL_DIAGNOSTIC_INTEGRITY_FAILURE")
        if (value.canonical_rule_id in by_id or not 1 <= value.canonical_rule_id <= 61
                or str(value.canonical_rule_id) != str(record.rule_id)
                or record.instrument_id != instrument_id or record.as_of_timestamp.tzinfo is None
                or record.as_of_timestamp.utcoffset() is None
                or record.as_of_timestamp.astimezone(timezone.utc) != cutoff):
            raise ValueError("Diagnostic identity, rule or as-of mismatch")
        by_id[value.canonical_rule_id] = value
    results = []
    for lens in load_catalog():
        available = tuple(rule for rule in lens.proposed_primary_diagnostics
            if rule in by_id and by_id[rule].eligibility is EvaluationEligibility.ELIGIBLE
            and by_id[rule].record.result.upper() not in {"", "INSUFFICIENT_DATA", "UNVERIFIED", "NOT_APPLICABLE", "EVIDENCE_CONFLICTED"})
        missing = tuple(rule for rule in lens.proposed_primary_diagnostics if rule not in available)
        results.append(LensAssessment(lens.lens_id, lens.version, instrument_id, cutoff, "UNKNOWN",
            available, missing, tuple(by_id[rule].record.id for rule in available), lens.unresolved_dependencies,
            ("LENS_POLICY_NOT_APPROVED", "LENS_SPECIFIC_EVIDENCE_NOT_ASSESSED")))
    return tuple(results)
