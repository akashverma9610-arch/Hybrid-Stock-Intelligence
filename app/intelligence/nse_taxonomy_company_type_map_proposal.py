"""Non-active exact NSE taxonomy-code company-type research map.

This is a versioned policy proposal, not an authoritative company-type
classifier.  It can audit a PIT-eligible canonical NSE taxonomy record against
the exact current official sector-code identities recorded in the proposal.
It deliberately has no issuer, regulator, repository, portfolio, API, or
execution dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import json
import re

from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification


POLICY_ID = "nse-taxonomy-company-type-code-map-proposal"
POLICY_VERSION = "v1"
CONTRACT_ID = "nse-taxonomy-company-type-code-map-proposal-contract"
CONTRACT_VERSION = "v1"
NSE_TAXONOMY_SOURCE = "NSE_INDICES_OFFICIAL"
NSE_TAXONOMY_VERSION = "nse-indices-taxonomy-v1"
NSE_TAXONOMY_SEMANTICS = "FIRST_OBSERVED_OFFICIAL_SNAPSHOT"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SOURCE_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class NseTaxonomyCompanyTypeMapStatus(StrEnum):
    PROPOSED = "PROPOSED"
    NOT_APPROVED = "NOT_APPROVED"
    NOT_ACTIVE = "NOT_ACTIVE"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    NON_EXECUTABLE = "NON_EXECUTABLE"


class NseTaxonomyLevel(StrEnum):
    SECTOR = "SECTOR"


class NseTaxonomyResearchCategory(StrEnum):
    NON_FINANCIAL_CANDIDATE = "NON_FINANCIAL_CANDIDATE"
    REGULATED_FINANCIAL_CANDIDATE = "REGULATED_FINANCIAL_CANDIDATE"
    UNSUPPORTED_FINANCIAL = "UNSUPPORTED_FINANCIAL"
    UNKNOWN_NON_COMPARABLE = "UNKNOWN_NON_COMPARABLE"
    UNMAPPED = "UNMAPPED"


class NseTaxonomyMapAuditReason(StrEnum):
    EXACT_TAXONOMY_IDENTITY_MAPPED = "EXACT_TAXONOMY_IDENTITY_MAPPED"
    PIT_TAXONOMY_UNAVAILABLE = "PIT_TAXONOMY_UNAVAILABLE"
    TAXONOMY_SOURCE_OR_VERSION_UNSUPPORTED = "TAXONOMY_SOURCE_OR_VERSION_UNSUPPORTED"
    LOWEST_RELIABLE_LEVEL_MAP_REQUIRED = "LOWEST_RELIABLE_LEVEL_MAP_REQUIRED"
    EXACT_TAXONOMY_IDENTITY_UNMAPPED = "EXACT_TAXONOMY_IDENTITY_UNMAPPED"


_STATUS = (
    NseTaxonomyCompanyTypeMapStatus.PROPOSED,
    NseTaxonomyCompanyTypeMapStatus.NOT_APPROVED,
    NseTaxonomyCompanyTypeMapStatus.NOT_ACTIVE,
    NseTaxonomyCompanyTypeMapStatus.RESEARCH_ONLY,
    NseTaxonomyCompanyTypeMapStatus.NON_EXECUTABLE,
)


@dataclass(frozen=True, slots=True)
class NseTaxonomyCompanyTypeMapEntry:
    """One exact official code pair and a descriptive research category."""

    entry_id: str
    taxonomy_source: str
    taxonomy_version: str
    taxonomy_level: NseTaxonomyLevel
    macro_economic_sector_code: str
    sector_code: str
    category: NseTaxonomyResearchCategory
    rationale: str
    fingerprint: str

    def __post_init__(self) -> None:
        if (
            not _identifier_ok(self.entry_id)
            or self.taxonomy_source != NSE_TAXONOMY_SOURCE
            or self.taxonomy_version != NSE_TAXONOMY_VERSION
            or self.taxonomy_level is not NseTaxonomyLevel.SECTOR
            or not _identifier_ok(self.macro_economic_sector_code)
            or not _identifier_ok(self.sector_code)
            or self.category is NseTaxonomyResearchCategory.UNMAPPED
            or not self.rationale.strip()
            or self.fingerprint != _hash(_entry_payload(self))
        ):
            raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_ENTRY_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class ProposedNseTaxonomyCompanyTypeMap:
    """The fixed proposal artifact; it is deliberately not an active selector."""

    policy_id: str
    policy_version: str
    status: tuple[NseTaxonomyCompanyTypeMapStatus, ...]
    taxonomy_source: str
    taxonomy_version: str
    taxonomy_level: NseTaxonomyLevel
    entries: tuple[NseTaxonomyCompanyTypeMapEntry, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        expected = _entries()
        if (
            self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or self.status != _STATUS
            or self.taxonomy_source != NSE_TAXONOMY_SOURCE
            or self.taxonomy_version != NSE_TAXONOMY_VERSION
            or self.taxonomy_level is not NseTaxonomyLevel.SECTOR
            or self.entries != expected
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != _hash(_map_payload(self))
        ):
            raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_PROPOSAL_INVALID")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class ProposedNseTaxonomyMapAssessment:
    """A taxonomy-only audit observation, never an issuer company type."""

    policy_id: str
    policy_version: str
    policy_fingerprint: str
    classification_id: str
    classification_source_sha256: str
    canonical_instrument_id: str
    as_of: datetime
    category: NseTaxonomyResearchCategory
    reason: NseTaxonomyMapAuditReason
    map_entry_id: str | None
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self) -> None:
        mapped = self.reason is NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_MAPPED
        if (
            self.policy_id != POLICY_ID
            or self.policy_version != POLICY_VERSION
            or not _fingerprint_ok(self.policy_fingerprint)
            or not _identifier_ok(self.classification_id)
            or not _source_sha256_ok(self.classification_source_sha256)
            or not _canonical_instrument_id(self.canonical_instrument_id)
            or not _aware(self.as_of)
            or not isinstance(self.category, NseTaxonomyResearchCategory)
            or not isinstance(self.reason, NseTaxonomyMapAuditReason)
            or (mapped and (self.category is NseTaxonomyResearchCategory.UNMAPPED or not _identifier_ok(self.map_entry_id or "")))
            or (not mapped and (self.category is not NseTaxonomyResearchCategory.UNMAPPED or self.map_entry_id is not None))
            or self.contract_id != CONTRACT_ID
            or self.contract_version != CONTRACT_VERSION
            or self.actionability != "WATCH_ONLY"
            or self.execution_status != "NON_EXECUTABLE"
            or self.fingerprint != _hash(_assessment_payload(self))
        ):
            raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_ASSESSMENT_INVALID")

    def verify(self) -> None:
        self.__post_init__()


class NseTaxonomyCompanyTypeMapError(ValueError):
    pass


def create_proposed_nse_taxonomy_company_type_map() -> ProposedNseTaxonomyCompanyTypeMap:
    """Return the sole immutable, non-active current-source proposal artifact."""
    values = {
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "status": _STATUS,
        "taxonomy_source": NSE_TAXONOMY_SOURCE,
        "taxonomy_version": NSE_TAXONOMY_VERSION,
        "taxonomy_level": NseTaxonomyLevel.SECTOR,
        "entries": _entries(),
    }
    return ProposedNseTaxonomyCompanyTypeMap(**values, fingerprint=_hash(_map_payload_from_values(values)))


def assess_proposed_nse_taxonomy_map(
    classification: InstrumentTaxonomyClassification,
    *,
    as_of: datetime,
) -> ProposedNseTaxonomyMapAssessment:
    """Audit an exact PIT taxonomy record against the proposal only.

    The function cannot see issuer, regulator, portfolio, or runtime state.  A
    ``NON_FINANCIAL_CANDIDATE`` result is therefore expressly not a final
    company-type result and cannot be used as one without later approval.
    """
    if not isinstance(classification, InstrumentTaxonomyClassification) or not _aware(as_of):
        raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_INPUT_INVALID")
    policy = create_proposed_nse_taxonomy_company_type_map()
    normalized_as_of = _utc(as_of)
    if not _classification_identity_valid(classification):
        raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_TAXONOMY_IDENTITY_INVALID")
    if not classification.eligible_as_of(normalized_as_of):
        return _assessment(
            policy, classification, normalized_as_of, NseTaxonomyResearchCategory.UNMAPPED,
            NseTaxonomyMapAuditReason.PIT_TAXONOMY_UNAVAILABLE, None,
        )
    if not _source_version_supported(classification):
        return _assessment(
            policy, classification, normalized_as_of, NseTaxonomyResearchCategory.UNMAPPED,
            NseTaxonomyMapAuditReason.TAXONOMY_SOURCE_OR_VERSION_UNSUPPORTED, None,
        )
    if classification.industry_code is not None or classification.basic_industry_code is not None:
        return _assessment(
            policy, classification, normalized_as_of, NseTaxonomyResearchCategory.UNMAPPED,
            NseTaxonomyMapAuditReason.LOWEST_RELIABLE_LEVEL_MAP_REQUIRED, None,
        )
    entry = _entry_by_code(policy.entries).get((classification.macro_economic_sector_code, classification.sector_code))
    if entry is None:
        return _assessment(
            policy, classification, normalized_as_of, NseTaxonomyResearchCategory.UNMAPPED,
            NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_UNMAPPED, None,
        )
    return _assessment(
        policy, classification, normalized_as_of, entry.category,
        NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_MAPPED, entry.entry_id,
    )


def proposed_nse_taxonomy_company_type_map_payload(value: ProposedNseTaxonomyCompanyTypeMap) -> dict[str, object]:
    value.verify()
    return _map_payload(value) | {"fingerprint": value.fingerprint}


def serialize_proposed_nse_taxonomy_company_type_map(value: ProposedNseTaxonomyCompanyTypeMap) -> str:
    return json.dumps(proposed_nse_taxonomy_company_type_map_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def proposed_nse_taxonomy_map_assessment_payload(value: ProposedNseTaxonomyMapAssessment) -> dict[str, object]:
    value.verify()
    return _assessment_payload(value) | {"fingerprint": value.fingerprint}


def serialize_proposed_nse_taxonomy_map_assessment(value: ProposedNseTaxonomyMapAssessment) -> str:
    return json.dumps(proposed_nse_taxonomy_map_assessment_payload(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _entries() -> tuple[NseTaxonomyCompanyTypeMapEntry, ...]:
    raw = (
        ("IN01", "IN0101", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Chemicals sector identity."),
        ("IN01", "IN0102", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Construction Materials sector identity."),
        ("IN01", "IN0103", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Metals and Mining sector identity."),
        ("IN01", "IN0104", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Forest Materials sector identity."),
        ("IN02", "IN0201", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Automobile and Auto Components sector identity."),
        ("IN02", "IN0202", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Consumer Durables sector identity."),
        ("IN02", "IN0203", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Textiles sector identity."),
        ("IN02", "IN0205", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Realty sector identity."),
        ("IN02", "IN0206", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Consumer Services sector identity."),
        ("IN04", "IN0401", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Fast Moving Consumer Goods sector identity."),
        ("IN05", "IN0501", NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL, "Current sector-level evidence is too broad to distinguish regulated and unsupported financial business types."),
        ("IN06", "IN0601", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Healthcare sector identity."),
        ("IN07", "IN0701", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Construction sector identity."),
        ("IN07", "IN0702", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Capital Goods sector identity."),
        ("IN08", "IN0801", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Information Technology sector identity."),
        ("IN09", "IN0901", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Services sector identity."),
        ("IN11", "IN1101", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Power sector identity."),
        ("IN11", "IN1102", NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE, "Exact official Utilities sector identity."),
        ("IN12", "IN1201", NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE, "Current sector-level evidence is not sufficiently specific for a research company-type candidate."),
    )
    values = tuple(
        _entry(macro_code, sector_code, category, rationale)
        for macro_code, sector_code, category, rationale in raw
    )
    return tuple(sorted(values, key=lambda item: (item.macro_economic_sector_code, item.sector_code, item.entry_id)))


def _entry(
    macro_economic_sector_code: str,
    sector_code: str,
    category: NseTaxonomyResearchCategory,
    rationale: str,
) -> NseTaxonomyCompanyTypeMapEntry:
    values = {
        "entry_id": f"nse-taxonomy-company-type-map:{POLICY_VERSION}:{macro_economic_sector_code}:{sector_code}",
        "taxonomy_source": NSE_TAXONOMY_SOURCE,
        "taxonomy_version": NSE_TAXONOMY_VERSION,
        "taxonomy_level": NseTaxonomyLevel.SECTOR,
        "macro_economic_sector_code": macro_economic_sector_code,
        "sector_code": sector_code,
        "category": category,
        "rationale": rationale,
    }
    return NseTaxonomyCompanyTypeMapEntry(**values, fingerprint=_hash(_entry_payload_from_values(values)))


def _assessment(
    policy: ProposedNseTaxonomyCompanyTypeMap,
    classification: InstrumentTaxonomyClassification,
    as_of: datetime,
    category: NseTaxonomyResearchCategory,
    reason: NseTaxonomyMapAuditReason,
    entry_id: str | None,
) -> ProposedNseTaxonomyMapAssessment:
    values = {
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_fingerprint": policy.fingerprint,
        "classification_id": classification.classification_id,
        "classification_source_sha256": classification.source_sha256,
        "canonical_instrument_id": classification.instrument_id,
        "as_of": _utc(as_of),
        "category": category,
        "reason": reason,
        "map_entry_id": entry_id,
    }
    return ProposedNseTaxonomyMapAssessment(**values, fingerprint=_hash(_assessment_payload_from_values(values)))


def _classification_identity_valid(value: InstrumentTaxonomyClassification) -> bool:
    return (
        _identifier_ok(value.classification_id)
        and _canonical_instrument_id(value.instrument_id)
        and _source_sha256_ok(value.source_sha256 or "")
        and _identifier_ok(value.macro_economic_sector_code or "")
        and _identifier_ok(value.sector_code or "")
        and _aware(value.effective_from)
        and _aware(value.as_of)
    )


def _source_version_supported(value: InstrumentTaxonomyClassification) -> bool:
    return (
        value.source == NSE_TAXONOMY_SOURCE
        and value.source_type is ClassificationSourceStatus.OFFICIAL
        and value.classification_version == NSE_TAXONOMY_VERSION
        and value.resolution_status == "EXACT_UNIQUE"
        and value.effective_observation_semantics == NSE_TAXONOMY_SEMANTICS
    )


def _entry_by_code(values: tuple[NseTaxonomyCompanyTypeMapEntry, ...]) -> dict[tuple[str | None, str | None], NseTaxonomyCompanyTypeMapEntry]:
    return {(item.macro_economic_sector_code, item.sector_code): item for item in values}


def _map_payload(value: ProposedNseTaxonomyCompanyTypeMap) -> dict[str, object]:
    return _map_payload_from_values({
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "status": value.status,
        "taxonomy_source": value.taxonomy_source,
        "taxonomy_version": value.taxonomy_version,
        "taxonomy_level": value.taxonomy_level,
        "entries": value.entries,
        "contract_id": value.contract_id,
        "contract_version": value.contract_version,
        "actionability": value.actionability,
        "execution_status": value.execution_status,
    })


def _map_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return {
        "policy_id": values["policy_id"],
        "policy_version": values["policy_version"],
        "status": tuple(item.value for item in values["status"]),
        "taxonomy_source": values["taxonomy_source"],
        "taxonomy_version": values["taxonomy_version"],
        "taxonomy_level": values["taxonomy_level"].value,
        "entries": tuple(_entry_payload(item) for item in values["entries"]),
        "contract_id": values.get("contract_id", CONTRACT_ID),
        "contract_version": values.get("contract_version", CONTRACT_VERSION),
        "actionability": values.get("actionability", "WATCH_ONLY"),
        "execution_status": values.get("execution_status", "NON_EXECUTABLE"),
    }


def _entry_payload(value: NseTaxonomyCompanyTypeMapEntry) -> dict[str, object]:
    return _entry_payload_from_values({
        "entry_id": value.entry_id,
        "taxonomy_source": value.taxonomy_source,
        "taxonomy_version": value.taxonomy_version,
        "taxonomy_level": value.taxonomy_level,
        "macro_economic_sector_code": value.macro_economic_sector_code,
        "sector_code": value.sector_code,
        "category": value.category,
        "rationale": value.rationale,
    })


def _entry_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return {
        "entry_id": values["entry_id"],
        "taxonomy_source": values["taxonomy_source"],
        "taxonomy_version": values["taxonomy_version"],
        "taxonomy_level": values["taxonomy_level"].value,
        "macro_economic_sector_code": values["macro_economic_sector_code"],
        "sector_code": values["sector_code"],
        "category": values["category"].value,
        "rationale": values["rationale"],
    }


def _assessment_payload(value: ProposedNseTaxonomyMapAssessment) -> dict[str, object]:
    return _assessment_payload_from_values({
        "policy_id": value.policy_id,
        "policy_version": value.policy_version,
        "policy_fingerprint": value.policy_fingerprint,
        "classification_id": value.classification_id,
        "classification_source_sha256": value.classification_source_sha256,
        "canonical_instrument_id": value.canonical_instrument_id,
        "as_of": value.as_of,
        "category": value.category,
        "reason": value.reason,
        "map_entry_id": value.map_entry_id,
        "contract_id": value.contract_id,
        "contract_version": value.contract_version,
        "actionability": value.actionability,
        "execution_status": value.execution_status,
    })


def _assessment_payload_from_values(values: dict[str, object]) -> dict[str, object]:
    return {
        "policy_id": values["policy_id"],
        "policy_version": values["policy_version"],
        "policy_fingerprint": values["policy_fingerprint"],
        "classification_id": values["classification_id"],
        "classification_source_sha256": values["classification_source_sha256"],
        "canonical_instrument_id": values["canonical_instrument_id"],
        "as_of": _utc(values["as_of"]).isoformat(),
        "category": values["category"].value,
        "reason": values["reason"].value,
        "map_entry_id": values["map_entry_id"],
        "contract_id": values.get("contract_id", CONTRACT_ID),
        "contract_version": values.get("contract_version", CONTRACT_VERSION),
        "actionability": values.get("actionability", "WATCH_ONLY"),
        "execution_status": values.get("execution_status", "NON_EXECUTABLE"),
    }


def _identifier_ok(value: str) -> bool:
    return bool(_IDENTIFIER.fullmatch(value))


def _fingerprint_ok(value: str) -> bool:
    return bool(_FINGERPRINT.fullmatch(value))


def _source_sha256_ok(value: str) -> bool:
    return bool(_SOURCE_SHA256.fullmatch(value))


def _canonical_instrument_id(value: str) -> bool:
    exchange, separator, isin = value.partition(":")
    return exchange == "NSE" and separator == ":" and _identifier_ok(isin)


def _aware(value: datetime) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise NseTaxonomyCompanyTypeMapError("NSE_TAXONOMY_COMPANY_TYPE_MAP_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _hash(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


__all__ = [
    "CONTRACT_ID", "CONTRACT_VERSION", "NSE_TAXONOMY_SOURCE", "NSE_TAXONOMY_VERSION", "POLICY_ID", "POLICY_VERSION",
    "NseTaxonomyCompanyTypeMapEntry", "NseTaxonomyCompanyTypeMapError", "NseTaxonomyCompanyTypeMapStatus", "NseTaxonomyLevel",
    "NseTaxonomyMapAuditReason", "NseTaxonomyResearchCategory", "ProposedNseTaxonomyCompanyTypeMap", "ProposedNseTaxonomyMapAssessment",
    "assess_proposed_nse_taxonomy_map", "create_proposed_nse_taxonomy_company_type_map",
    "proposed_nse_taxonomy_company_type_map_payload", "proposed_nse_taxonomy_map_assessment_payload",
    "serialize_proposed_nse_taxonomy_company_type_map", "serialize_proposed_nse_taxonomy_map_assessment",
]
