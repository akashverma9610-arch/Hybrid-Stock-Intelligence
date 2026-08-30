"""Immutable governance contract for canonical diagnostic strategy definitions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Protocol

from app.domain.models import StrategyVersionReference


class CanonicalDiagnosticDefinitionStatus(StrEnum):
    APPROVED = "approved"


class CanonicalDiagnosticStrategyDefinitionError(ValueError):
    """Raised when a canonical diagnostic definition is incomplete or mismatched."""


CANONICAL_61_STRATEGY_REFERENCE = StrategyVersionReference("canonical-universe-analysis", "v1")
CANONICAL_61_SEMANTIC_FINGERPRINT = "sha256:3144ec1e9452f24a1e9f3776c77e33cbd59f31459c3e2f7d734c4924bb2b9ee3"
CANONICAL_61_GOVERNANCE_LIMITATIONS = (
    ("StockDiagnosticInputAssembler", "UNVERSIONED_DEPENDENCY"),
    ("BacktestLookaheadGuard", "UNVERSIONED_DEPENDENCY"),
    ("DeterministicDiagnosticEvaluators", "UNVERSIONED_DEPENDENCY"),
    ("NIFTY_50 default benchmark / explicit constructor override", "UNVERSIONED_DEPENDENCY"),
    ("DiagnosticResult / SQLiteStrategyGovernanceRepository", "UNVERSIONED_DEPENDENCY"),
    ("Inline technical, fundamental, valuation, trade, liquidity, crowd, and freshness policy implementations", "UNVERSIONED_DEPENDENCY"),
)


class CanonicalDiagnosticDefinitionReader(Protocol):
    def get_canonical_diagnostic_strategy_definition(
        self, reference: StrategyVersionReference,
    ) -> "CanonicalDiagnosticStrategyDefinition | None": ...


@dataclass(frozen=True, slots=True, order=True)
class CanonicalDiagnosticGovernanceLimitation:
    dependency: str
    classification: str = "UNVERSIONED_DEPENDENCY"

    def __post_init__(self) -> None:
        if not self.dependency:
            raise CanonicalDiagnosticStrategyDefinitionError("Governance limitation dependency is required.")
        if self.classification != "UNVERSIONED_DEPENDENCY":
            raise CanonicalDiagnosticStrategyDefinitionError(
                "Canonical diagnostic governance limitations must remain UNVERSIONED_DEPENDENCY."
            )


@dataclass(frozen=True, slots=True)
class CanonicalDiagnosticStrategyDefinition:
    """Approved, fingerprinted diagnostic semantics; separate from generic strategies."""

    strategy_id: str
    strategy_version: str
    canonical_payload: Mapping[str, Any]
    semantic_fingerprint: str
    governance_limitations: tuple[CanonicalDiagnosticGovernanceLimitation, ...]
    definition_status: CanonicalDiagnosticDefinitionStatus
    reviewer_id: str
    definition_proposal_artifact: str
    human_approval_artifact: str
    created_at: datetime
    registered_at: datetime

    def __post_init__(self) -> None:
        if not self.strategy_id or not self.strategy_version:
            raise CanonicalDiagnosticStrategyDefinitionError("Canonical diagnostic strategy identity is required.")
        if not self.reviewer_id or not self.definition_proposal_artifact or not self.human_approval_artifact:
            raise CanonicalDiagnosticStrategyDefinitionError("Approval lineage is required.")
        object.__setattr__(self, "canonical_payload", _freeze_json_mapping(self.canonical_payload))
        object.__setattr__(self, "governance_limitations", tuple(sorted(set(self.governance_limitations))))
        self.verify_integrity()

    @property
    def reference(self) -> StrategyVersionReference:
        return StrategyVersionReference(self.strategy_id, self.strategy_version)

    @property
    def canonical_payload_serialization(self) -> str:
        return canonical_payload_serialization(self.canonical_payload)

    def verify_integrity(self) -> None:
        actual = semantic_fingerprint_for_payload(self.canonical_payload)
        if self.semantic_fingerprint != actual:
            raise CanonicalDiagnosticStrategyDefinitionError(
                "Canonical diagnostic semantic fingerprint does not match the canonical payload."
            )


def canonical_payload_serialization(payload: Mapping[str, Any]) -> str:
    """Serialize approved JSON semantics deterministically and without runtime context."""
    return json.dumps(_plain_json(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def semantic_fingerprint_for_payload(payload: Mapping[str, Any]) -> str:
    serialized = canonical_payload_serialization(payload).encode("utf-8")
    return f"sha256:{sha256(serialized).hexdigest()}"


def governance_limitations_fingerprint(
    limitations: tuple[CanonicalDiagnosticGovernanceLimitation, ...],
) -> str:
    payload = [
        {"classification": item.classification, "dependency": item.dependency}
        for item in sorted(set(limitations))
    ]
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"sha256:{sha256(serialized).hexdigest()}"


def require_canonical_61_runner_authorization(
    reader: CanonicalDiagnosticDefinitionReader,
    reference: StrategyVersionReference,
) -> CanonicalDiagnosticStrategyDefinition:
    """Resolve the exact human-approved Canonical 61 definition or fail closed.

    The constants are approval requirements, not an authorization bypass: the
    typed definition must be present in the supplied governance repository,
    approved, self-integral, and exact on identity, semantic fingerprint, and
    all six declared unversioned dependencies.
    """
    if reference != CANONICAL_61_STRATEGY_REFERENCE:
        raise CanonicalDiagnosticStrategyDefinitionError(
            "Canonical 61 runner requires canonical-universe-analysis / v1."
        )
    definition = reader.get_canonical_diagnostic_strategy_definition(reference)
    if definition is None:
        raise CanonicalDiagnosticStrategyDefinitionError(
            "Canonical 61 runner requires the exact registered canonical definition."
        )
    definition.verify_integrity()
    if definition.definition_status is not CanonicalDiagnosticDefinitionStatus.APPROVED:
        raise CanonicalDiagnosticStrategyDefinitionError(
            "Canonical 61 runner requires an approved canonical definition."
        )
    if definition.semantic_fingerprint != CANONICAL_61_SEMANTIC_FINGERPRINT:
        raise CanonicalDiagnosticStrategyDefinitionError(
            "Canonical 61 runner semantic fingerprint mismatch."
        )
    expected_limitations = tuple(
        CanonicalDiagnosticGovernanceLimitation(dependency, classification)
        for dependency, classification in CANONICAL_61_GOVERNANCE_LIMITATIONS
    )
    if definition.governance_limitations != tuple(sorted(expected_limitations)):
        raise CanonicalDiagnosticStrategyDefinitionError(
            "Canonical 61 runner governance limitations mismatch."
        )
    return definition


def validate_canonical_diagnostic_strategy_definition(
    definition: CanonicalDiagnosticStrategyDefinition,
    *,
    reference: StrategyVersionReference,
    semantic_fingerprint: str,
    canonical_payload: Mapping[str, Any],
    governance_limitations: tuple[CanonicalDiagnosticGovernanceLimitation, ...],
) -> CanonicalDiagnosticStrategyDefinition:
    """Fail closed unless an exact approved definition matches every semantic input."""
    if definition.reference != reference:
        raise CanonicalDiagnosticStrategyDefinitionError("Canonical diagnostic strategy identity/version mismatch.")
    definition.verify_integrity()
    if definition.semantic_fingerprint != semantic_fingerprint:
        raise CanonicalDiagnosticStrategyDefinitionError("Canonical diagnostic strategy semantic fingerprint mismatch.")
    if definition.canonical_payload_serialization != canonical_payload_serialization(canonical_payload):
        raise CanonicalDiagnosticStrategyDefinitionError("Canonical diagnostic strategy payload mismatch.")
    if definition.governance_limitations != tuple(sorted(set(governance_limitations))):
        raise CanonicalDiagnosticStrategyDefinitionError("Canonical diagnostic strategy governance limitations mismatch.")
    return definition


def _freeze_json_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CanonicalDiagnosticStrategyDefinitionError("Canonical payload must be a mapping.")
    return MappingProxyType({key: _freeze_json_value(item) for key, item in value.items()})


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_json_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json_value(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise CanonicalDiagnosticStrategyDefinitionError("Canonical payload must contain JSON-compatible values only.")


def _plain_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalDiagnosticStrategyDefinitionError("Canonical payload keys must be strings.")
        return {key: _plain_json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain_json(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise CanonicalDiagnosticStrategyDefinitionError("Canonical payload must contain JSON-compatible values only.")
