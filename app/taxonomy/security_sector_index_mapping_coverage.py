"""Current-descriptive coverage audit for the existing sector-index mapping.

The sector taxonomy and the immutable ``NseSectorIndexMapping`` snapshots
remain the only sources of truth.  This module consumes selected snapshots and
canonical index-OHLC session counts; it does not select taxonomy, fetch NSE
data, persist an audit row, or make a technical-rule decision.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Iterable, Mapping

from app.taxonomy.models import InstrumentTaxonomyClassification
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.models import NseEquityInstrument


CONTRACT_ID = "canonical-security-sector-index-mapping-coverage-governance"
CONTRACT_VERSION = "v1"
POLICY_ID = "canonical-sector-index-mapping-policy"
POLICY_VERSION = "v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class MappingApplicability(StrEnum):
    CURRENT_DESCRIPTIVE = "CURRENT_DESCRIPTIVE"


class StrictHistoricalPitMappingState(StrEnum):
    NOT_READY = "NOT_READY"


class SecuritySectorIndexMappingState(StrEnum):
    EXACT_GOVERNED_MAPPING = "EXACT_GOVERNED_MAPPING"
    NOT_GOVERNED = "NOT_GOVERNED"
    NO_OFFICIAL_INDEX = "NO_OFFICIAL_INDEX"
    AMBIGUOUS = "AMBIGUOUS"
    TAXONOMY_MISSING = "TAXONOMY_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CanonicalSectorIndexHistoryState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SecuritySectorIndexCoverageReason(StrEnum):
    MAPPED_WITH_CANONICAL_INDEX_HISTORY = "MAPPED_WITH_CANONICAL_INDEX_HISTORY"
    SECURITY_SECTOR_CLASSIFICATION_MISSING = "SECURITY_SECTOR_CLASSIFICATION_MISSING"
    TAXONOMY_STALE_OR_INCOMPLETE = "TAXONOMY_STALE_OR_INCOMPLETE"
    SECURITY_IDENTITY_UNRESOLVED = "SECURITY_IDENTITY_UNRESOLVED"
    SECTOR_INDEX_MAPPING_MISSING = "SECTOR_INDEX_MAPPING_MISSING"
    OFFICIAL_SECTOR_INDEX_UNAVAILABLE = "OFFICIAL_SECTOR_INDEX_UNAVAILABLE"
    INDEX_IDENTITY_AMBIGUOUS = "INDEX_IDENTITY_AMBIGUOUS"
    MAPPING_POLICY_NOT_GOVERNED = "MAPPING_POLICY_NOT_GOVERNED"
    CANONICAL_INDEX_OHLC_LINEAGE_ABSENT = "CANONICAL_INDEX_OHLC_LINEAGE_ABSENT"
    TECHNICAL_INPUT_OUT_OF_SCOPE = "TECHNICAL_INPUT_OUT_OF_SCOPE"


class SecuritySectorIndexCoverageError(ValueError):
    """Stable fail-closed error for malformed mapping-audit inputs."""


@dataclass(frozen=True, slots=True)
class CanonicalSecuritySectorIndexMappingPolicy:
    """Compact policy for reusing, never replacing, the mapping snapshots."""

    policy_id: str
    version: str
    taxonomy_source: str
    mapping_source: str
    index_return_family: str
    applicability: MappingApplicability
    strict_historical_pit_state: StrictHistoricalPitMappingState
    exact_mapping_status: SectorIndexMappingStatus
    broad_proxy_permitted: bool
    synthetic_index_permitted: bool
    fuzzy_mapping_permitted: bool
    fingerprint: str

    def __post_init__(self) -> None:
        values = _policy_values(self)
        if (
            not all(isinstance(value, str) and value for value in (
                self.policy_id, self.version, self.taxonomy_source, self.mapping_source,
                self.index_return_family,
            ))
            or self.policy_id != POLICY_ID
            or self.version != POLICY_VERSION
            or self.index_return_family != "PRICE_RETURN_INDEX"
            or self.applicability is not MappingApplicability.CURRENT_DESCRIPTIVE
            or self.strict_historical_pit_state is not StrictHistoricalPitMappingState.NOT_READY
            or self.exact_mapping_status is not SectorIndexMappingStatus.EXACT_OFFICIAL
            or self.broad_proxy_permitted
            or self.synthetic_index_permitted
            or self.fuzzy_mapping_permitted
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class SecuritySectorIndexCoverageInput:
    """One canonical security and its already-resolved current taxonomy."""

    instrument: NseEquityInstrument
    classification: InstrumentTaxonomyClassification | None
    in_current_technical_scope: bool

    def __post_init__(self) -> None:
        if not isinstance(self.instrument, NseEquityInstrument) or not isinstance(self.in_current_technical_scope, bool):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_INPUT_INVALID")
        if self.classification is not None and not isinstance(self.classification, InstrumentTaxonomyClassification):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_INPUT_INVALID")


@dataclass(frozen=True, slots=True)
class SecuritySectorIndexCoverageRecord:
    """A transient per-security audit result, not a persisted mapping receipt."""

    canonical_instrument_id: str
    symbol: str
    isin: str | None
    in_current_technical_scope: bool
    taxonomy_classification_id: str | None
    macro_sector: str | None
    canonical_sector: str | None
    industry: str | None
    basic_industry: str | None
    mapping_id: str | None
    source_mapping_status: SectorIndexMappingStatus | None
    official_index_name: str | None
    canonical_index_id: str | None
    mapping_state: SecuritySectorIndexMappingState
    index_history_state: CanonicalSectorIndexHistoryState
    canonical_ohlc_session_count: int
    reason_code: SecuritySectorIndexCoverageReason
    applicability: MappingApplicability
    strict_historical_pit_state: StrictHistoricalPitMappingState
    fingerprint: str

    def __post_init__(self) -> None:
        values = _record_values(self)
        exact = self.mapping_state is SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING
        has_source_mapping = self.mapping_id is not None
        history_ready = self.index_history_state is CanonicalSectorIndexHistoryState.READY
        missing_taxonomy = self.mapping_state is SecuritySectorIndexMappingState.TAXONOMY_MISSING
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not self.symbol
            or (self.isin is not None and (not isinstance(self.isin, str) or not self.isin))
            or not isinstance(self.in_current_technical_scope, bool)
            or self.applicability is not MappingApplicability.CURRENT_DESCRIPTIVE
            or self.strict_historical_pit_state is not StrictHistoricalPitMappingState.NOT_READY
            or self.canonical_ohlc_session_count < 0
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
            # A non-exact source receipt may legitimately retain an official
            # candidate name.  It remains non-governed and cannot obtain a
            # canonical index identity, but the audit must not discard its
            # descriptive provenance or reject the row merely for retaining it.
            or (exact and not bool(self.mapping_id and self.official_index_name and self.canonical_index_id))
            or (self.mapping_id is None) != (self.source_mapping_status is None)
            or (not has_source_mapping and self.official_index_name is not None)
            or (exact and self.index_history_state is CanonicalSectorIndexHistoryState.NOT_APPLICABLE)
            or (not exact and self.canonical_index_id is not None)
            or (not exact and self.canonical_ohlc_session_count != 0)
            or (history_ready != (exact and self.canonical_ohlc_session_count > 0))
            or (history_ready and self.reason_code is not SecuritySectorIndexCoverageReason.MAPPED_WITH_CANONICAL_INDEX_HISTORY)
            or (exact and not history_ready and self.reason_code is not SecuritySectorIndexCoverageReason.CANONICAL_INDEX_OHLC_LINEAGE_ABSENT)
            or (missing_taxonomy and any(value is not None for value in (
                self.taxonomy_classification_id, self.macro_sector, self.canonical_sector,
                self.industry, self.basic_industry,
            )))
        ):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_RECORD_INVALID")


@dataclass(frozen=True, slots=True)
class SecuritySectorIndexCoverageAudit:
    """Deterministic whole-universe current-descriptive mapping audit."""

    audit_as_of: datetime
    policy_id: str
    policy_version: str
    policy_fingerprint: str
    records: tuple[SecuritySectorIndexCoverageRecord, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.records, key=lambda item: item.canonical_instrument_id))
        values = _audit_values(self.audit_as_of, self.policy_id, self.policy_version, self.policy_fingerprint, ordered)
        if (
            not _aware(self.audit_as_of)
            or (self.policy_id, self.policy_version) != (POLICY_ID, POLICY_VERSION)
            or not _FP.fullmatch(self.policy_fingerprint)
            or self.records != ordered
            or len({item.canonical_instrument_id for item in self.records}) != len(self.records)
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_AUDIT_INVALID")

    @property
    def technical_scope_records(self) -> tuple[SecuritySectorIndexCoverageRecord, ...]:
        return tuple(item for item in self.records if item.in_current_technical_scope)

    def reason_counts(self, *, technical_scope_only: bool = False) -> tuple[tuple[str, int], ...]:
        values = self.technical_scope_records if technical_scope_only else self.records
        return tuple(sorted(Counter(item.reason_code.value for item in values).items()))

    def mapped_count(self, *, technical_scope_only: bool = False) -> int:
        values = self.technical_scope_records if technical_scope_only else self.records
        return sum(item.mapping_state is SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING for item in values)

    def canonical_history_ready_count(self, *, technical_scope_only: bool = False) -> int:
        values = self.technical_scope_records if technical_scope_only else self.records
        return sum(item.index_history_state is CanonicalSectorIndexHistoryState.READY for item in values)


def audit_current_security_sector_index_coverage(
    *,
    audit_as_of: datetime,
    inputs: Iterable[SecuritySectorIndexCoverageInput],
    mappings: Iterable[NseSectorIndexMapping],
    canonical_index_ohlc_session_counts: Mapping[str, int],
    policy: CanonicalSecuritySectorIndexMappingPolicy | None = None,
) -> SecuritySectorIndexCoverageAudit:
    """Audit injected current facts without accessing storage, a clock, or NSE."""
    if not _aware(audit_as_of):
        raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_AUDIT_AS_OF_REQUIRED")
    cutoff = audit_as_of.astimezone(UTC)
    selected_policy = policy or current_security_sector_index_mapping_policy()
    selected_policy.__post_init__()
    rows = tuple(inputs)
    if any(not isinstance(item, SecuritySectorIndexCoverageInput) for item in rows):
        raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_INPUT_INVALID")
    for item in rows:
        item.__post_init__()
    if len({item.instrument.instrument_id for item in rows}) != len(rows):
        raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_DUPLICATE_SECURITY")
    selected_mappings, ambiguous_sectors = _select_current_mappings(mappings, cutoff)
    counts = _session_counts(canonical_index_ohlc_session_counts)
    records = tuple(sorted(
        (_record(item, cutoff, selected_mappings, ambiguous_sectors, counts, selected_policy) for item in rows),
        key=lambda value: value.canonical_instrument_id,
    ))
    values = _audit_values(cutoff, selected_policy.policy_id, selected_policy.version, selected_policy.fingerprint, records)
    return SecuritySectorIndexCoverageAudit(
        cutoff, selected_policy.policy_id, selected_policy.version, selected_policy.fingerprint,
        records, _fingerprint(values),
    )


def current_security_sector_index_mapping_policy() -> CanonicalSecuritySectorIndexMappingPolicy:
    """Build the one fixed policy without a clock or environment dependency."""
    values = {
        "policy_id": POLICY_ID,
        "version": POLICY_VERSION,
        "taxonomy_source": "InstrumentTaxonomyClassification",
        "mapping_source": "NseSectorIndexMapping",
        "index_return_family": "PRICE_RETURN_INDEX",
        "applicability": MappingApplicability.CURRENT_DESCRIPTIVE,
        "strict_historical_pit_state": StrictHistoricalPitMappingState.NOT_READY,
        "exact_mapping_status": SectorIndexMappingStatus.EXACT_OFFICIAL,
        "broad_proxy_permitted": False,
        "synthetic_index_permitted": False,
        "fuzzy_mapping_permitted": False,
    }
    return CanonicalSecuritySectorIndexMappingPolicy(**values, fingerprint=_fingerprint(_policy_values_from(values)))


def serialize_security_sector_index_coverage_audit(value: SecuritySectorIndexCoverageAudit) -> str:
    """Stable JSON including every audit-fingerprint input and row fingerprint."""
    value.__post_init__()
    return json.dumps(_audit_values(
        value.audit_as_of, value.policy_id, value.policy_version, value.policy_fingerprint, value.records,
    ) | {"fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _record(
    item: SecuritySectorIndexCoverageInput,
    cutoff: datetime,
    mappings: Mapping[str, NseSectorIndexMapping],
    ambiguous_sectors: frozenset[str],
    counts: Mapping[str, int],
    policy: CanonicalSecuritySectorIndexMappingPolicy,
) -> SecuritySectorIndexCoverageRecord:
    instrument = item.instrument
    classification = item.classification
    if not item.in_current_technical_scope:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, None,
            SecuritySectorIndexMappingState.NOT_APPLICABLE,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.TECHNICAL_INPUT_OUT_OF_SCOPE, policy,
        )
    if instrument.data_as_of.astimezone(UTC) > cutoff:
        return _build_record(
            instrument, item.in_current_technical_scope, None, None,
            SecuritySectorIndexMappingState.TAXONOMY_MISSING,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.SECURITY_IDENTITY_UNRESOLVED, policy,
        )
    if classification is None or not classification.sector:
        return _build_record(
            instrument, item.in_current_technical_scope, None, None,
            SecuritySectorIndexMappingState.TAXONOMY_MISSING,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.SECURITY_SECTOR_CLASSIFICATION_MISSING, policy,
        )
    if (
        classification.instrument_id != instrument.instrument_id
        or not classification.classification_id
        or classification.as_of.astimezone(UTC) > cutoff
        or classification.effective_from.astimezone(UTC) > cutoff
        or (classification.effective_to is not None and classification.effective_to.astimezone(UTC) < cutoff)
    ):
        return _build_record(
            instrument, item.in_current_technical_scope, classification, None,
            SecuritySectorIndexMappingState.NOT_GOVERNED,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0,
            SecuritySectorIndexCoverageReason.SECURITY_IDENTITY_UNRESOLVED
            if classification.instrument_id != instrument.instrument_id
            else SecuritySectorIndexCoverageReason.TAXONOMY_STALE_OR_INCOMPLETE,
            policy,
        )
    sector = classification.sector
    if sector in ambiguous_sectors:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, None,
            SecuritySectorIndexMappingState.AMBIGUOUS,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.MAPPING_POLICY_NOT_GOVERNED, policy,
        )
    mapping = mappings.get(sector)
    if mapping is None:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, None,
            SecuritySectorIndexMappingState.NOT_GOVERNED,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.SECTOR_INDEX_MAPPING_MISSING, policy,
        )
    if not _mapping_valid(mapping, sector):
        return _build_record(
            instrument, item.in_current_technical_scope, classification, None,
            SecuritySectorIndexMappingState.NOT_GOVERNED,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.MAPPING_POLICY_NOT_GOVERNED, policy,
        )
    if mapping.status is SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, mapping,
            SecuritySectorIndexMappingState.NO_OFFICIAL_INDEX,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.OFFICIAL_SECTOR_INDEX_UNAVAILABLE, policy,
        )
    if mapping.status is SectorIndexMappingStatus.AMBIGUOUS:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, mapping,
            SecuritySectorIndexMappingState.AMBIGUOUS,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.INDEX_IDENTITY_AMBIGUOUS, policy,
        )
    if mapping.status is not policy.exact_mapping_status:
        return _build_record(
            instrument, item.in_current_technical_scope, classification, mapping,
            SecuritySectorIndexMappingState.NOT_GOVERNED,
            CanonicalSectorIndexHistoryState.NOT_APPLICABLE,
            0, SecuritySectorIndexCoverageReason.MAPPING_POLICY_NOT_GOVERNED, policy,
        )
    canonical_index_id = _canonical_sector_index_id(sector)
    count = counts.get(canonical_index_id, 0)
    history = CanonicalSectorIndexHistoryState.READY if count else CanonicalSectorIndexHistoryState.NOT_READY
    return _build_record(
        instrument, item.in_current_technical_scope, classification, mapping,
        SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING, history, count,
        SecuritySectorIndexCoverageReason.MAPPED_WITH_CANONICAL_INDEX_HISTORY
        if history is CanonicalSectorIndexHistoryState.READY
        else SecuritySectorIndexCoverageReason.CANONICAL_INDEX_OHLC_LINEAGE_ABSENT,
        policy,
    )


def _build_record(
    instrument: NseEquityInstrument,
    in_scope: bool,
    classification: InstrumentTaxonomyClassification | None,
    mapping: NseSectorIndexMapping | None,
    state: SecuritySectorIndexMappingState,
    history: CanonicalSectorIndexHistoryState,
    count: int,
    reason: SecuritySectorIndexCoverageReason,
    policy: CanonicalSecuritySectorIndexMappingPolicy,
) -> SecuritySectorIndexCoverageRecord:
    exact = state is SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING
    sector = None if classification is None else classification.sector
    values = {
        "canonical_instrument_id": instrument.instrument_id,
        "symbol": instrument.symbol,
        "isin": instrument.isin,
        "in_current_technical_scope": in_scope,
        "taxonomy_classification_id": None if classification is None else classification.classification_id,
        "macro_sector": None if classification is None else classification.super_sector,
        "canonical_sector": sector,
        "industry": None if classification is None else classification.industry,
        "basic_industry": None if classification is None else classification.basic_industry,
        "mapping_id": None if mapping is None else mapping.mapping_id,
        "source_mapping_status": None if mapping is None else mapping.status,
        "official_index_name": None if mapping is None else mapping.official_index_name,
        "canonical_index_id": None if not exact or sector is None else _canonical_sector_index_id(sector),
        "mapping_state": state,
        "index_history_state": history,
        "canonical_ohlc_session_count": count if exact else 0,
        "reason_code": reason,
        "applicability": policy.applicability,
        "strict_historical_pit_state": policy.strict_historical_pit_state,
    }
    return SecuritySectorIndexCoverageRecord(**values, fingerprint=_fingerprint(_record_values_from(values)))


def _select_current_mappings(
    values: Iterable[NseSectorIndexMapping], cutoff: datetime,
) -> tuple[dict[str, NseSectorIndexMapping], frozenset[str]]:
    grouped: dict[str, list[NseSectorIndexMapping]] = {}
    for value in values:
        if not isinstance(value, NseSectorIndexMapping) or not _aware(value.fetched_at_utc):
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_MAPPING_INPUT_INVALID")
        if value.fetched_at_utc.astimezone(UTC) <= cutoff:
            grouped.setdefault(value.canonical_sector, []).append(value)
    selected: dict[str, NseSectorIndexMapping] = {}
    ambiguous: set[str] = set()
    for sector, candidates in grouped.items():
        latest = max(item.fetched_at_utc.astimezone(UTC) for item in candidates)
        current = tuple(item for item in candidates if item.fetched_at_utc.astimezone(UTC) == latest)
        semantic = { _mapping_values(item) for item in current }
        if len(semantic) != 1 or len({item.mapping_id for item in current}) != 1:
            ambiguous.add(sector)
        else:
            selected[sector] = current[0]
    return selected, frozenset(ambiguous)


def _session_counts(values: Mapping[str, int]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index_id, count in values.items():
        if not isinstance(index_id, str) or not index_id.startswith("NSE_SECTOR_INDEX:") or not isinstance(count, int) or count < 0:
            raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_HISTORY_COUNTS_INVALID")
        result[index_id] = count
    return result


def _mapping_valid(value: NseSectorIndexMapping, sector: str) -> bool:
    if not all(isinstance(item, str) and item for item in (value.mapping_id, value.canonical_sector, value.source_artifact_sha256)):
        return False
    if value.canonical_sector != sector or not value.evidence:
        return False
    if value.status is SectorIndexMappingStatus.EXACT_OFFICIAL:
        return bool(value.official_index_name and value.official_page)
    return True


def _canonical_sector_index_id(sector: str) -> str:
    token = re.sub(r"[^A-Z0-9]+", "_", sector.upper()).strip("_")
    if not token:
        raise SecuritySectorIndexCoverageError("SECURITY_SECTOR_INDEX_IDENTITY_REQUIRED")
    return "NSE_SECTOR_INDEX:" + token


def _policy_values(value: CanonicalSecuritySectorIndexMappingPolicy) -> dict[str, object]:
    return _policy_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _policy_values_from(values: Mapping[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "policy_id": values["policy_id"],
        "policy_version": values["version"],
        "taxonomy_source": values["taxonomy_source"],
        "mapping_source": values["mapping_source"],
        "index_return_family": values["index_return_family"],
        "applicability": _enum(values["applicability"]),
        "strict_historical_pit_state": _enum(values["strict_historical_pit_state"]),
        "exact_mapping_status": _enum(values["exact_mapping_status"]),
        "broad_proxy_permitted": values["broad_proxy_permitted"],
        "synthetic_index_permitted": values["synthetic_index_permitted"],
        "fuzzy_mapping_permitted": values["fuzzy_mapping_permitted"],
    }


def _record_values(value: SecuritySectorIndexCoverageRecord) -> dict[str, object]:
    return _record_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _record_values_from(values: Mapping[str, object]) -> dict[str, object]:
    return {key: _enum(value) for key, value in values.items()}


def _audit_values(
    audit_as_of: datetime,
    policy_id: str,
    policy_version: str,
    policy_fingerprint: str,
    records: tuple[SecuritySectorIndexCoverageRecord, ...],
) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "audit_as_of": audit_as_of.astimezone(UTC).isoformat(),
        "policy": {"id": policy_id, "version": policy_version, "fingerprint": policy_fingerprint},
        "records": [_record_values(item) | {"fingerprint": item.fingerprint} for item in records],
    }


def _mapping_values(value: NseSectorIndexMapping) -> tuple[object, ...]:
    return (
        value.canonical_sector, value.official_index_name, value.official_page, value.status.value,
        value.evidence, value.source_artifact_sha256, value.historical_pit_eligible,
    )


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _enum(value: object) -> object:
    return value.value if isinstance(value, StrEnum) else value


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


CURRENT_SECURITY_SECTOR_INDEX_MAPPING_POLICY = current_security_sector_index_mapping_policy()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CURRENT_SECURITY_SECTOR_INDEX_MAPPING_POLICY",
    "CanonicalSecuritySectorIndexMappingPolicy", "CanonicalSectorIndexHistoryState",
    "MappingApplicability", "POLICY_ID", "POLICY_VERSION",
    "SecuritySectorIndexCoverageAudit", "SecuritySectorIndexCoverageError",
    "SecuritySectorIndexCoverageInput", "SecuritySectorIndexCoverageReason",
    "SecuritySectorIndexCoverageRecord", "SecuritySectorIndexMappingState",
    "StrictHistoricalPitMappingState", "audit_current_security_sector_index_coverage",
    "current_security_sector_index_mapping_policy", "serialize_security_sector_index_coverage_audit",
)
