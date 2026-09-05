"""Exact-security, read-only union of canonical discovery leads.

This is deliberately a *candidate-pool* boundary.  It groups already
PIT-valid discovery leads by their existing canonical NSE security identity,
but neither evaluates a security nor invokes the shared Brain.  A pool item
only means ``CANDIDATE_FOR_SHARED_BRAIN_INSPECTION``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Iterable

from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead,
    DiscoveryFunnelId,
    DiscoveryHorizon,
    discovery_lead_payload,
)
from app.intelligence.multi_funnel_discovery_adapters import (
    DiscoveryAdapterCoverage,
    DiscoveryAdapterResult,
)


CANDIDATE_UNION_CONTRACT = "multi-funnel-candidate-union/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_NSE_SECURITY = re.compile(r"NSE:([A-Z]{2}[A-Z0-9]{9}[0-9])\Z")


class CandidateUnionError(ValueError):
    """Stable fail-closed error for an ambiguous union input."""


class CandidatePoolStatus(StrEnum):
    CANDIDATE_FOR_SHARED_BRAIN_INSPECTION = "CANDIDATE_FOR_SHARED_BRAIN_INSPECTION"


class CandidateUnionExclusionState(StrEnum):
    IDENTITY_BLOCKED = "IDENTITY_BLOCKED"
    IDENTITY_CONFLICTED = "IDENTITY_CONFLICTED"
    FUTURE_LEAD_EXCLUDED = "FUTURE_LEAD_EXCLUDED"


class CandidateUnionReason(StrEnum):
    CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED = "CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED"
    CONFLICTING_CANONICAL_LEAD_IDENTITY = "CONFLICTING_CANONICAL_LEAD_IDENTITY"
    LEAD_AFTER_BATCH_AS_OF = "LEAD_AFTER_BATCH_AS_OF"


@dataclass(frozen=True, slots=True)
class DiscoveryCandidateOrigin:
    """One unmodified discovery origin retained in a security pool item."""

    lead: CanonicalDiscoveryLead
    origin_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.lead, CanonicalDiscoveryLead):
            raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_LEAD_INVALID")
        self.lead.verify()
        object.__setattr__(self, "origin_id", self.lead.lead_id)
        object.__setattr__(self, "fingerprint", self.lead.fingerprint)

    def verify(self) -> None:
        self.lead.verify()
        if self.origin_id != self.lead.lead_id:
            raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_IDENTITY_MISMATCH")
        if self.fingerprint != self.lead.fingerprint:
            raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CandidateUnionExclusion:
    """A supplied lead retained outside the pool with an explicit blocker."""

    origin: DiscoveryCandidateOrigin
    state: CandidateUnionExclusionState
    reason: CandidateUnionReason
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.origin, DiscoveryCandidateOrigin):
            raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_ORIGIN_INVALID")
        self.origin.verify()
        if not isinstance(self.state, CandidateUnionExclusionState) or not isinstance(self.reason, CandidateUnionReason):
            raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_ENUM_INVALID")
        expected = {
            CandidateUnionExclusionState.IDENTITY_BLOCKED: CandidateUnionReason.CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED,
            CandidateUnionExclusionState.IDENTITY_CONFLICTED: CandidateUnionReason.CONFLICTING_CANONICAL_LEAD_IDENTITY,
            CandidateUnionExclusionState.FUTURE_LEAD_EXCLUDED: CandidateUnionReason.LEAD_AFTER_BATCH_AS_OF,
        }
        if expected[self.state] is not self.reason:
            raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_REASON_INVALID")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_exclusion_payload(self)))

    def verify(self) -> None:
        self.origin.verify()
        if self.fingerprint != manifest_fingerprint(**_exclusion_payload(self)):
            raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CanonicalDiscoveryPoolItem:
    """One exact NSE security, with every distinct discovery origin intact."""

    canonical_instrument_id: str
    isin: str
    batch_as_of: datetime
    origins: tuple[DiscoveryCandidateOrigin, ...]
    issuer_ids: tuple[str, ...] = ()
    status: CandidatePoolStatus = CandidatePoolStatus.CANDIDATE_FOR_SHARED_BRAIN_INSPECTION
    candidate_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_as_of", _utc(self.batch_as_of, "CANDIDATE_UNION_AS_OF_INVALID"))
        object.__setattr__(self, "origins", _origins(self.origins))
        object.__setattr__(self, "issuer_ids", _ids(self.issuer_ids, "CANDIDATE_UNION_ISSUER_IDS_INVALID"))
        _validate_pool_item(self)
        object.__setattr__(self, "candidate_id", "discovery-pool:" + manifest_fingerprint(**_pool_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_pool_payload(self)))

    @property
    def funnel_ids(self) -> tuple[DiscoveryFunnelId, ...]:
        return tuple(sorted({item.lead.funnel_id for item in self.origins}, key=lambda item: item.value))

    @property
    def distinct_funnel_count(self) -> int:
        """Descriptive provenance only; it is not a score, vote, or rank."""
        return len(self.funnel_ids)

    @property
    def horizon_lineage(self) -> tuple[DiscoveryHorizon, ...]:
        """Originating horizons only; no primary/final horizon is resolved."""
        return tuple(sorted({item for origin in self.origins for item in origin.lead.intended_horizons}, key=lambda item: item.value))

    @property
    def earliest_known_at(self) -> datetime:
        return min(item.known_at for origin in self.origins for item in origin.lead.lineage)

    @property
    def latest_known_at(self) -> datetime:
        return max(item.known_at for origin in self.origins for item in origin.lead.lineage)

    def verify(self) -> None:
        _validate_pool_item(self)
        if self.candidate_id != "discovery-pool:" + manifest_fingerprint(**_pool_identity(self))[:32]:
            raise CandidateUnionError("CANDIDATE_UNION_POOL_IDENTITY_MISMATCH")
        if self.fingerprint != manifest_fingerprint(**_pool_payload(self)):
            raise CandidateUnionError("CANDIDATE_UNION_POOL_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class CandidateUnionFunnelCoverage:
    """Adapter coverage plus non-evaluative union accounting for one funnel."""

    funnel_id: DiscoveryFunnelId
    adapter_result_fingerprint: str
    adapter_coverage: DiscoveryAdapterCoverage
    raw_lead_count: int
    distinct_origin_count: int
    distinct_security_count: int
    exact_duplicate_lead_count: int
    identity_blocked_lead_count: int
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.funnel_id, DiscoveryFunnelId) or not isinstance(self.adapter_coverage, DiscoveryAdapterCoverage):
            raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_TYPE_INVALID")
        if self.adapter_coverage.funnel_id is not self.funnel_id or not _fp(self.adapter_result_fingerprint):
            raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_LINEAGE_INVALID")
        _verify_adapter_coverage(self.adapter_coverage)
        values = (self.raw_lead_count, self.distinct_origin_count, self.distinct_security_count, self.exact_duplicate_lead_count, self.identity_blocked_lead_count)
        if not all(isinstance(value, int) and value >= 0 for value in values):
            raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_COUNT_INVALID")
        if self.distinct_origin_count > self.raw_lead_count or self.distinct_security_count > self.distinct_origin_count:
            raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_COUNT_INCONSISTENT")
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_funnel_coverage_payload(self)))

    def verify(self) -> None:
        if self.fingerprint != manifest_fingerprint(**_funnel_coverage_payload(self)):
            raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class MultiFunnelCandidateUnionBatch:
    """Immutable result of one explicit read-only union at a PIT cutoff."""

    as_of: datetime
    funnel_coverage: tuple[CandidateUnionFunnelCoverage, ...]
    candidates: tuple[CanonicalDiscoveryPoolItem, ...]
    exclusions: tuple[CandidateUnionExclusion, ...] = ()
    batch_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of, "CANDIDATE_UNION_AS_OF_INVALID"))
        object.__setattr__(self, "funnel_coverage", _funnel_coverage(self.funnel_coverage))
        object.__setattr__(self, "candidates", _pool_items(self.candidates))
        object.__setattr__(self, "exclusions", _exclusions(self.exclusions))
        _validate_batch(self)
        object.__setattr__(self, "batch_id", "discovery-union-batch:" + manifest_fingerprint(**_batch_identity(self))[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_batch_payload(self)))

    @property
    def input_lead_count(self) -> int:
        return sum(item.raw_lead_count for item in self.funnel_coverage)

    @property
    def exact_duplicate_lead_count(self) -> int:
        return sum(item.exact_duplicate_lead_count for item in self.funnel_coverage)

    @property
    def distinct_origin_count(self) -> int:
        return sum(len(item.origins) for item in self.candidates)

    @property
    def identity_blocked_lead_count(self) -> int:
        return sum(item.identity_blocked_lead_count for item in self.funnel_coverage)

    @property
    def eligible_lead_count(self) -> int:
        """Distinct non-replay origins eligible for exact-security grouping."""
        return self.distinct_origin_count

    @property
    def final_distinct_security_pool_count(self) -> int:
        return len(self.candidates)

    @property
    def single_funnel_security_count(self) -> int:
        return sum(item.distinct_funnel_count == 1 for item in self.candidates)

    @property
    def multi_funnel_security_count(self) -> int:
        return sum(item.distinct_funnel_count > 1 for item in self.candidates)

    def verify(self) -> None:
        _validate_batch(self)
        if self.batch_id != "discovery-union-batch:" + manifest_fingerprint(**_batch_identity(self))[:32]:
            raise CandidateUnionError("CANDIDATE_UNION_BATCH_IDENTITY_MISMATCH")
        if self.fingerprint != manifest_fingerprint(**_batch_payload(self)):
            raise CandidateUnionError("CANDIDATE_UNION_BATCH_FINGERPRINT_MISMATCH")


def union_discovery_candidates(*, as_of: datetime, adapter_results: Iterable[DiscoveryAdapterResult]) -> MultiFunnelCandidateUnionBatch:
    """Union already-produced adapters without executing, scoring, or storing them."""
    cutoff = _utc(as_of, "CANDIDATE_UNION_AS_OF_INVALID")
    supplied = tuple(adapter_results)
    if not supplied or not all(isinstance(item, DiscoveryAdapterResult) for item in supplied):
        raise CandidateUnionError("CANDIDATE_UNION_ADAPTER_RESULTS_REQUIRED")
    for result in supplied:
        result.verify()
        if result.as_of != cutoff:
            raise CandidateUnionError("CANDIDATE_UNION_ADAPTER_AS_OF_MISMATCH")

    unique_results: dict[DiscoveryFunnelId, DiscoveryAdapterResult] = {}
    raw_by_funnel: dict[DiscoveryFunnelId, list[CanonicalDiscoveryLead]] = {}
    for result in supplied:
        raw_by_funnel.setdefault(result.funnel_id, []).extend(result.leads)
        prior = unique_results.get(result.funnel_id)
        if prior is None:
            unique_results[result.funnel_id] = result
        elif prior.fingerprint != result.fingerprint:
            raise CandidateUnionError("CANDIDATE_UNION_ADAPTER_RESULT_CONFLICT")

    accepted: dict[str, list[DiscoveryCandidateOrigin]] = {}
    exclusions: list[CandidateUnionExclusion] = []
    funnel_stats = {funnel: {"raw": len(raw), "origins": 0, "duplicates": 0, "identity": 0} for funnel, raw in raw_by_funnel.items()}
    for funnel in sorted(raw_by_funnel, key=lambda item: item.value):
        by_identity: dict[str, list[CanonicalDiscoveryLead]] = {}
        for lead in raw_by_funnel[funnel]:
            by_identity.setdefault(lead.lead_id, []).append(lead)
        for lead_id in sorted(by_identity):
            values = tuple(sorted(by_identity[lead_id], key=lambda item: item.fingerprint))
            fingerprints = {item.fingerprint for item in values}
            if len(fingerprints) > 1:
                for lead in values:
                    exclusions.append(_exclusion(lead, CandidateUnionExclusionState.IDENTITY_CONFLICTED))
                funnel_stats[funnel]["identity"] += len(values)
                continue
            lead = values[0]
            funnel_stats[funnel]["duplicates"] += len(values) - 1
            origin = DiscoveryCandidateOrigin(lead)
            if lead.discovery_as_of > cutoff or any(item.known_at > cutoff for item in lead.lineage):
                exclusions.append(_exclusion(lead, CandidateUnionExclusionState.FUTURE_LEAD_EXCLUDED))
                continue
            if _isin_for_instrument(lead.canonical_instrument_id) is None:
                exclusions.append(_exclusion(lead, CandidateUnionExclusionState.IDENTITY_BLOCKED))
                funnel_stats[funnel]["identity"] += 1
                continue
            accepted.setdefault(lead.canonical_instrument_id, []).append(origin)
            funnel_stats[funnel]["origins"] += 1

    candidates = tuple(
        CanonicalDiscoveryPoolItem(
            canonical_instrument_id=instrument,
            isin=_isin_for_instrument(instrument) or "",
            batch_as_of=cutoff,
            origins=tuple(origins),
            issuer_ids=tuple(sorted({origin.lead.issuer_id for origin in origins if origin.lead.issuer_id is not None})),
        )
        for instrument, origins in sorted(accepted.items())
    )
    coverage = tuple(
        CandidateUnionFunnelCoverage(
            funnel_id=funnel,
            adapter_result_fingerprint=result.fingerprint,
            adapter_coverage=result.coverage,
            raw_lead_count=funnel_stats[funnel]["raw"],
            distinct_origin_count=funnel_stats[funnel]["origins"],
            distinct_security_count=sum(any(origin.lead.funnel_id is funnel for origin in item.origins) for item in candidates),
            exact_duplicate_lead_count=funnel_stats[funnel]["duplicates"],
            identity_blocked_lead_count=funnel_stats[funnel]["identity"],
        )
        for funnel, result in sorted(unique_results.items(), key=lambda item: item[0].value)
    )
    return MultiFunnelCandidateUnionBatch(cutoff, coverage, candidates, tuple(exclusions))


def candidate_union_payload(value: MultiFunnelCandidateUnionBatch) -> dict[str, object]:
    value.verify()
    return _batch_payload(value) | {"batch_id": value.batch_id, "fingerprint": value.fingerprint}


def serialize_candidate_union(value: MultiFunnelCandidateUnionBatch) -> str:
    return json.dumps(candidate_union_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _exclusion(lead: CanonicalDiscoveryLead, state: CandidateUnionExclusionState) -> CandidateUnionExclusion:
    reason = {
        CandidateUnionExclusionState.IDENTITY_BLOCKED: CandidateUnionReason.CANONICAL_NSE_SECURITY_IDENTITY_REQUIRED,
        CandidateUnionExclusionState.IDENTITY_CONFLICTED: CandidateUnionReason.CONFLICTING_CANONICAL_LEAD_IDENTITY,
        CandidateUnionExclusionState.FUTURE_LEAD_EXCLUDED: CandidateUnionReason.LEAD_AFTER_BATCH_AS_OF,
    }[state]
    return CandidateUnionExclusion(DiscoveryCandidateOrigin(lead), state, reason)


def _validate_pool_item(value: CanonicalDiscoveryPoolItem) -> None:
    if _isin_for_instrument(value.canonical_instrument_id) != value.isin:
        raise CandidateUnionError("CANDIDATE_UNION_SECURITY_IDENTITY_INVALID")
    if not isinstance(value.status, CandidatePoolStatus) or value.status is not CandidatePoolStatus.CANDIDATE_FOR_SHARED_BRAIN_INSPECTION:
        raise CandidateUnionError("CANDIDATE_UNION_STATUS_INVALID")
    if not value.origins or any(origin.lead.canonical_instrument_id != value.canonical_instrument_id for origin in value.origins):
        raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_SECURITY_MISMATCH")
    for origin in value.origins:
        origin.verify()
        if origin.lead.discovery_as_of > value.batch_as_of or any(item.known_at > value.batch_as_of for item in origin.lead.lineage):
            raise CandidateUnionError("CANDIDATE_UNION_FUTURE_ORIGIN_FORBIDDEN")
    expected_issuers = tuple(sorted({item.lead.issuer_id for item in value.origins if item.lead.issuer_id is not None}))
    if value.issuer_ids != expected_issuers:
        raise CandidateUnionError("CANDIDATE_UNION_ISSUER_LINEAGE_MISMATCH")


def _validate_batch(value: MultiFunnelCandidateUnionBatch) -> None:
    if not value.funnel_coverage:
        raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_REQUIRED")
    if len({item.funnel_id for item in value.funnel_coverage}) != len(value.funnel_coverage):
        raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_DUPLICATE_FUNNEL")
    if len({item.canonical_instrument_id for item in value.candidates}) != len(value.candidates):
        raise CandidateUnionError("CANDIDATE_UNION_POOL_DUPLICATE_SECURITY")
    seen_origins: set[tuple[str, str]] = set()
    for item in value.candidates:
        item.verify()
        for origin in item.origins:
            identity = (origin.origin_id, origin.fingerprint)
            if identity in seen_origins:
                raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_REPLAY")
            seen_origins.add(identity)
    excluded = {(item.origin.origin_id, item.origin.fingerprint) for item in value.exclusions}
    if seen_origins & excluded:
        raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_ACCEPTED_AND_EXCLUDED")
    if sum(item.raw_lead_count for item in value.funnel_coverage) < len(seen_origins) + len(excluded):
        raise CandidateUnionError("CANDIDATE_UNION_COUNT_LINEAGE_INVALID")
    for item in value.funnel_coverage:
        item.verify()
    for item in value.exclusions:
        item.verify()


def _origins(values: Iterable[DiscoveryCandidateOrigin]) -> tuple[DiscoveryCandidateOrigin, ...]:
    supplied = tuple(values)
    if not supplied or not all(isinstance(item, DiscoveryCandidateOrigin) for item in supplied):
        raise CandidateUnionError("CANDIDATE_UNION_ORIGINS_REQUIRED")
    result = tuple(sorted(supplied, key=lambda item: (item.origin_id, item.fingerprint)))
    if len({(item.origin_id, item.fingerprint) for item in result}) != len(result):
        raise CandidateUnionError("CANDIDATE_UNION_ORIGIN_DUPLICATE")
    return result


def _pool_items(values: Iterable[CanonicalDiscoveryPoolItem]) -> tuple[CanonicalDiscoveryPoolItem, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, CanonicalDiscoveryPoolItem) for item in supplied):
        raise CandidateUnionError("CANDIDATE_UNION_POOL_ITEM_INVALID")
    return tuple(sorted(supplied, key=lambda item: item.canonical_instrument_id))


def _funnel_coverage(values: Iterable[CandidateUnionFunnelCoverage]) -> tuple[CandidateUnionFunnelCoverage, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, CandidateUnionFunnelCoverage) for item in supplied):
        raise CandidateUnionError("CANDIDATE_UNION_COVERAGE_TYPE_INVALID")
    return tuple(sorted(supplied, key=lambda item: item.funnel_id.value))


def _exclusions(values: Iterable[CandidateUnionExclusion]) -> tuple[CandidateUnionExclusion, ...]:
    supplied = tuple(values)
    if not all(isinstance(item, CandidateUnionExclusion) for item in supplied):
        raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_TYPE_INVALID")
    result = tuple(sorted(supplied, key=lambda item: (item.origin.origin_id, item.origin.fingerprint, item.state.value)))
    if len({(item.origin.origin_id, item.origin.fingerprint) for item in result}) != len(result):
        raise CandidateUnionError("CANDIDATE_UNION_EXCLUSION_DUPLICATE")
    return result


def _ids(values: Iterable[str], code: str) -> tuple[str, ...]:
    result = tuple(sorted(values))
    if result != tuple(values) or len(result) != len(set(result)) or not all(_id(item) for item in result):
        raise CandidateUnionError(code)
    return result


def _isin_for_instrument(value: str) -> str | None:
    if not isinstance(value, str):
        return None
    matched = _NSE_SECURITY.fullmatch(value)
    return matched.group(1) if matched else None


def _id(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _fp(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise CandidateUnionError(code)
    return value.astimezone(UTC)


def _origin_payload(value: DiscoveryCandidateOrigin) -> dict[str, object]:
    return {"origin_id": value.origin_id, "lead_fingerprint": value.fingerprint, "lead": discovery_lead_payload(value.lead)}


def _exclusion_payload(value: CandidateUnionExclusion) -> dict[str, object]:
    return {"origin": _origin_payload(value.origin), "state": value.state.value, "reason": value.reason.value}


def _pool_identity(value: CanonicalDiscoveryPoolItem) -> dict[str, object]:
    return {"contract": CANDIDATE_UNION_CONTRACT, "instrument": value.canonical_instrument_id, "as_of": value.batch_as_of.isoformat()}


def _pool_payload(value: CanonicalDiscoveryPoolItem) -> dict[str, object]:
    return _pool_identity(value) | {
        "isin": value.isin,
        "issuer_ids": value.issuer_ids,
        "status": value.status.value,
        "origins": tuple(_origin_payload(item) for item in value.origins),
        "funnel_ids": tuple(item.value for item in value.funnel_ids),
        "horizon_lineage": tuple(item.value for item in value.horizon_lineage),
        "earliest_known_at": value.earliest_known_at.isoformat(),
        "latest_known_at": value.latest_known_at.isoformat(),
    }


def _funnel_coverage_payload(value: CandidateUnionFunnelCoverage) -> dict[str, object]:
    return {
        "funnel": value.funnel_id.value,
        "adapter_result_fingerprint": value.adapter_result_fingerprint,
        "adapter_coverage": _adapter_coverage_payload(value.adapter_coverage),
        "raw_lead_count": value.raw_lead_count,
        "distinct_origin_count": value.distinct_origin_count,
        "distinct_security_count": value.distinct_security_count,
        "exact_duplicate_lead_count": value.exact_duplicate_lead_count,
        "identity_blocked_lead_count": value.identity_blocked_lead_count,
    }


def _batch_identity(value: MultiFunnelCandidateUnionBatch) -> dict[str, object]:
    return {
        "contract": CANDIDATE_UNION_CONTRACT,
        "as_of": value.as_of.isoformat(),
        "adapter_results": tuple((item.funnel_id.value, item.adapter_result_fingerprint) for item in value.funnel_coverage),
    }


def _batch_payload(value: MultiFunnelCandidateUnionBatch) -> dict[str, object]:
    return _batch_identity(value) | {
        "funnel_coverage": tuple(_funnel_coverage_payload(item) for item in value.funnel_coverage),
        "candidates": tuple(_pool_payload(item) | {"candidate_id": item.candidate_id, "fingerprint": item.fingerprint} for item in value.candidates),
        "exclusions": tuple(_exclusion_payload(item) | {"fingerprint": item.fingerprint} for item in value.exclusions),
        "input_lead_count": value.input_lead_count,
        "exact_duplicate_lead_count": value.exact_duplicate_lead_count,
        "eligible_lead_count": value.eligible_lead_count,
        "distinct_origin_count": value.distinct_origin_count,
        "identity_blocked_lead_count": value.identity_blocked_lead_count,
        "final_distinct_security_pool_count": value.final_distinct_security_pool_count,
        "single_funnel_security_count": value.single_funnel_security_count,
        "multi_funnel_security_count": value.multi_funnel_security_count,
    }


def _adapter_coverage_payload(value: DiscoveryAdapterCoverage) -> dict[str, object]:
    return {
        "funnel_id": value.funnel_id.value,
        "adapter_state": value.adapter_state.value,
        "state": value.state.value,
        "source_observations_examined": value.source_observations_examined,
        "securities_examined": value.securities_examined,
        "lead_ids": value.lead_ids,
        "data_blocked": value.data_blocked,
        "identity_blocked": value.identity_blocked,
        "policy_blocked": value.policy_blocked,
        "conflicted": value.conflicted,
        "no_lead": value.no_lead,
        "stale": value.stale,
        "reason_codes": tuple(item.value for item in value.reason_codes),
        "fingerprint": value.fingerprint,
    }


def _verify_adapter_coverage(value: DiscoveryAdapterCoverage) -> None:
    """Verify a frozen adapter coverage without giving the union write access."""
    expected = DiscoveryAdapterCoverage(
        value.funnel_id, value.adapter_state, value.state,
        value.source_observations_examined, value.securities_examined, value.lead_ids,
        value.data_blocked, value.identity_blocked, value.policy_blocked,
        value.conflicted, value.no_lead, value.stale, value.reason_codes,
    )
    if expected.fingerprint != value.fingerprint:
        raise CandidateUnionError("CANDIDATE_UNION_ADAPTER_COVERAGE_FINGERPRINT_MISMATCH")


__all__ = [
    "CANDIDATE_UNION_CONTRACT", "CandidatePoolStatus", "CandidateUnionError", "CandidateUnionExclusion",
    "CandidateUnionExclusionState", "CandidateUnionFunnelCoverage", "CandidateUnionReason",
    "CanonicalDiscoveryPoolItem", "DiscoveryCandidateOrigin", "MultiFunnelCandidateUnionBatch",
    "candidate_union_payload", "serialize_candidate_union", "union_discovery_candidates",
]
