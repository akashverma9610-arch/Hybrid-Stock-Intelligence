"""Pure, read-only source handoff; references only, never another evidence store.

Owning adapters must verify both the consumer's complete dependency manifest
and native retained records. An operations success/receipt is not such proof.
No production P1 adapter is registered here, and no freshness threshold is set.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re
from typing import Protocol

CONTRACT = "pilot-source-dependency-ledger/v1"


class SourceReadiness(StrEnum):
    READY_TO_EVALUATE = "READY_TO_EVALUATE"
    SOURCE_MISSING = "SOURCE_MISSING"
    SOURCE_STALE = "SOURCE_STALE"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    KNOWN_AT_INSUFFICIENT = "KNOWN_AT_INSUFFICIENT"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"


class RetainedFreshness(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("SOURCE_LEDGER_IDENTITY_REQUIRED")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SOURCE_LEDGER_AWARE_TIME_REQUIRED")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class SourceRequirement:
    dependency_id: str
    source_family: str
    provider: str
    canonical_subject: str
    required: bool

    def __post_init__(self):
        for name in ("dependency_id", "source_family", "provider", "canonical_subject"):
            _text(getattr(self, name))
        if type(self.required) is not bool:
            raise ValueError("SOURCE_LEDGER_REQUIREMENT_INVALID")


@dataclass(frozen=True, slots=True)
class RetainedSourceReference:
    """Owning-store view; source_at, known_at and ingested_at are independent.

    canonical_subject may name an exact index/security/shared reference scope.
    CURRENT is meaningful only after independent native-policy verification.
    """
    requirement: SourceRequirement
    reference: str
    fingerprint: str
    source_at: datetime | None
    known_at: datetime | None
    ingested_at: datetime | None
    identity_resolved: bool
    freshness: RetainedFreshness
    freshness_policy_reference: str | None

    def __post_init__(self):
        if not isinstance(self.requirement, SourceRequirement):
            raise ValueError("SOURCE_LEDGER_REQUIREMENT_INVALID")
        self.requirement.__post_init__()
        _text(self.reference)
        if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", self.fingerprint):
            raise ValueError("SOURCE_LEDGER_FINGERPRINT_INVALID")
        if type(self.identity_resolved) is not bool or not isinstance(self.freshness, RetainedFreshness):
            raise ValueError("SOURCE_LEDGER_STATE_INVALID")
        if self.freshness_policy_reference is not None:
            _text(self.freshness_policy_reference)
        for name in ("source_at", "known_at", "ingested_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _utc(getattr(self, name)))


class OwningSourceReader(Protocol):
    """Read exact references; verify native fingerprints/PIT/policy, no writes.

    manifest_verified checks COMPLETE direct/transitive requirements for the
    named consumer/run, not an arbitrary caller's partial list. verify checks
    the reference's retained metadata AND native freshness policy at as_of.
    Neither method may use 'latest now' or treat user assertions as evidence.
    """
    def manifest_verified(self, consumer: str, run_id: str, requirements: tuple[SourceRequirement, ...], *, as_of: datetime) -> bool: ...
    def read(self, requirement: SourceRequirement, *, as_of: datetime) -> tuple[RetainedSourceReference, ...]: ...
    def verify(self, reference: RetainedSourceReference, *, as_of: datetime) -> bool: ...


@dataclass(frozen=True, slots=True)
class SourceDependencyRow:
    requirement: SourceRequirement
    references: tuple[RetainedSourceReference, ...]
    states: tuple[SourceReadiness, ...]


@dataclass(frozen=True, slots=True)
class SourceDependencyLedger:
    consumer: str
    run_id: str
    as_of: datetime
    rows: tuple[SourceDependencyRow, ...]
    manifest_verified: bool

    @property
    def ready_to_evaluate(self) -> bool:
        return (self.manifest_verified and any(row.requirement.required for row in self.rows)
                and all(row.states == (SourceReadiness.READY_TO_EVALUATE,)
                        for row in self.rows if row.requirement.required))

    def serialize(self) -> str:
        def time_or_enum(value):
            if isinstance(value, datetime):
                return _utc(value).isoformat(timespec="microseconds")
            raise TypeError("SOURCE_LEDGER_SERIALIZATION_INVALID")
        return json.dumps({"contract": CONTRACT, **asdict(self)}, default=time_or_enum,
                          sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    @property
    def fingerprint(self) -> str:
        return "sha256:" + sha256(self.serialize().encode()).hexdigest()


def build_source_dependency_ledger(*, consumer: str, run_id: str, as_of: datetime,
                                  requirements: tuple[SourceRequirement, ...],
                                  reader: OwningSourceReader) -> SourceDependencyLedger:
    """Fail closed without changing or registering any downstream consumer."""
    _text(consumer)
    _text(run_id)
    as_of = _utc(as_of)
    if not isinstance(requirements, tuple) or not requirements:
        raise ValueError("SOURCE_LEDGER_COMPLETE_MANIFEST_REQUIRED")
    by_id = {}
    for requirement in requirements:
        requirement.__post_init__()
        if requirement.dependency_id in by_id and by_id[requirement.dependency_id] != requirement:
            raise ValueError("SOURCE_LEDGER_REQUIREMENT_CONFLICT")
        by_id[requirement.dependency_id] = requirement
    ordered = tuple(by_id[key] for key in sorted(by_id))
    manifest_verified = reader.manifest_verified(consumer, run_id, ordered, as_of=as_of) is True
    rows = []
    for requirement in ordered:
        references = reader.read(requirement, as_of=as_of)
        states = set()
        if not isinstance(references, tuple) or any(not isinstance(r, RetainedSourceReference) for r in references):
            references = ()
            states.add(SourceReadiness.SOURCE_UNVERIFIED)
        unique = {}
        for ref in references:
            ref.__post_init__()
            key = ref.reference
            if key in unique and unique[key] != ref:
                states.add(SourceReadiness.SOURCE_UNVERIFIED)
            unique.setdefault(key, ref)
            if ref.requirement != requirement or reader.verify(ref, as_of=as_of) is not True:
                states.add(SourceReadiness.SOURCE_UNVERIFIED)
            if not ref.identity_resolved:
                states.add(SourceReadiness.IDENTITY_UNRESOLVED)
            if ref.known_at is None or ref.known_at > as_of:
                states.add(SourceReadiness.KNOWN_AT_INSUFFICIENT)
            if ref.ingested_at is None or ref.ingested_at > as_of or ref.source_at is None or ref.source_at > as_of:
                states.add(SourceReadiness.SOURCE_UNVERIFIED)
            if ref.freshness_policy_reference is None:
                states.add(SourceReadiness.POLICY_UNAVAILABLE)
            if ref.freshness is RetainedFreshness.STALE:
                states.add(SourceReadiness.SOURCE_STALE)
            elif ref.freshness is RetainedFreshness.UNVERIFIED:
                states.add(SourceReadiness.SOURCE_UNVERIFIED)
        if not references:
            states.add(SourceReadiness.SOURCE_MISSING)
        if not manifest_verified:
            states.add(SourceReadiness.SOURCE_UNVERIFIED)
        # Preserve conflicting references, not only the first value of an ID.
        retained = tuple(sorted(set(references), key=lambda r: (r.reference, r.fingerprint, repr(r))))
        rows.append(SourceDependencyRow(requirement, retained,
                    tuple(sorted(states)) if states else (SourceReadiness.READY_TO_EVALUATE,)))
    return SourceDependencyLedger(consumer, run_id, as_of, tuple(rows), manifest_verified)
