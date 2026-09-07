"""Pure source-contract and acquisition-policy assessment for NSE taxonomy.

This module records whether injected first-party candidate evidence can safely
become a *future* current-descriptive taxonomy source.  It deliberately does
not fetch NSE, retain raw receipts, write a repository, or promote a taxonomy
classification.  The existing ``NseIndicesTaxonomyImporter`` remains the sole
promotion boundary until a separately approved ingestion slice exists.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from app.taxonomy.nse_indices import NseIndustryHierarchyEntry, resolve_nse_indices_label
from app.universe_analysis.models import NseEquityInstrument


CONTRACT_ID = "nse-all-listed-security-taxonomy-source-feasibility-and-acquisition-policy"
CONTRACT_VERSION = "v1"
NSE_EQUITY_QUOTE_SOURCE = "NSE_EQUITY_QUOTE_PAGE"
NSE_EQUITY_ALL_SECURITIES_SOURCE = "NSE_EQUITY_ALL_SECURITIES_CSV"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseTaxonomyAuthority(StrEnum):
    FIRST_PARTY_NSE = "FIRST_PARTY_NSE"
    FIRST_PARTY_NSE_INDICES = "FIRST_PARTY_NSE_INDICES"


class NseTaxonomyAcquisitionMode(StrEnum):
    BULK = "BULK"
    PER_SECURITY = "PER_SECURITY"


class NseTaxonomyUniverseCompleteness(StrEnum):
    ALL_LISTED = "ALL_LISTED"
    BOUNDED_INDEX_UNIVERSE = "BOUNDED_INDEX_UNIVERSE"
    IDENTITY_ONLY = "IDENTITY_ONLY"
    SAMPLE_ONLY = "SAMPLE_ONLY"


class NseTaxonomySourceAvailability(StrEnum):
    VERIFIED = "VERIFIED"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    SCHEMA_UNVERIFIED = "SCHEMA_UNVERIFIED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class NseTaxonomySourceVersionState(StrEnum):
    SOURCE_VERSION_AVAILABLE = "SOURCE_VERSION_AVAILABLE"
    CURRENT_SOURCE_VERSION_UNAVAILABLE = "CURRENT_SOURCE_VERSION_UNAVAILABLE"


class CurrentDescriptiveTaxonomyState(StrEnum):
    CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY = "CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY"


class StrictHistoricalPitTaxonomyState(StrEnum):
    NOT_READY = "NOT_READY"


class NseTaxonomySampleStatus(StrEnum):
    RECEIPT_ACCEPTED = "RECEIPT_ACCEPTED"
    SUCCESS_INCOMPLETE = "SUCCESS_INCOMPLETE"
    ACCESS_BLOCKED = "ACCESS_BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    SCHEMA_DRIFT = "SCHEMA_DRIFT"


class NseTaxonomySampleConclusion(StrEnum):
    EXACT_FOUR_LEVEL_ASSIGNMENT = "EXACT_FOUR_LEVEL_ASSIGNMENT"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    HIERARCHY_UNRESOLVED = "HIERARCHY_UNRESOLVED"
    SOURCE_RESPONSE_INCOMPLETE = "SOURCE_RESPONSE_INCOMPLETE"
    SOURCE_ACCESS_BLOCKED = "SOURCE_ACCESS_BLOCKED"
    SOURCE_RATE_LIMITED = "SOURCE_RATE_LIMITED"
    SOURCE_SCHEMA_DRIFT = "SOURCE_SCHEMA_DRIFT"


class NseAllListedTaxonomyDecision(StrEnum):
    ALL_LISTED_TAXONOMY_BULK_SOURCE_READY = "ALL_LISTED_TAXONOMY_BULK_SOURCE_READY"
    PER_SECURITY_FIRST_PARTY_TAXONOMY_SOURCE_READY = "PER_SECURITY_FIRST_PARTY_TAXONOMY_SOURCE_READY"
    FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL = "FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL"
    FIRST_PARTY_ALL_LISTED_TAXONOMY_NOT_FOUND = "FIRST_PARTY_ALL_LISTED_TAXONOMY_NOT_FOUND"


class NseTaxonomySourceError(ValueError):
    """Stable fail-closed error for malformed source-feasibility input."""


@dataclass(frozen=True, slots=True)
class NseTaxonomySourceCandidate:
    """A source-level finding, never a per-security taxonomy assertion."""

    candidate_id: str
    authority: NseTaxonomyAuthority
    acquisition_mode: NseTaxonomyAcquisitionMode
    universe_completeness: NseTaxonomyUniverseCompleteness
    availability: NseTaxonomySourceAvailability
    exact_identity_fields: tuple[str, ...]
    taxonomy_assignment_fields: tuple[str, ...]
    source_version_state: NseTaxonomySourceVersionState
    source_version: str | None
    source_reference: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) for value in self.exact_identity_fields + self.taxonomy_assignment_fields):
            raise NseTaxonomySourceError("NSE_TAXONOMY_SOURCE_CANDIDATE_INVALID")
        fields = tuple(sorted(set(self.exact_identity_fields)))
        assignments = tuple(sorted(set(self.taxonomy_assignment_fields)))
        allowed_identity = {"isin", "symbol", "series", "listing_status", "trading_status"}
        allowed_assignments = {"macro_economic_sector", "sector", "industry", "basic_industry"}
        if (
            not _ID.fullmatch(self.candidate_id)
            or not isinstance(self.authority, NseTaxonomyAuthority)
            or not isinstance(self.acquisition_mode, NseTaxonomyAcquisitionMode)
            or not isinstance(self.universe_completeness, NseTaxonomyUniverseCompleteness)
            or not isinstance(self.availability, NseTaxonomySourceAvailability)
            or fields != self.exact_identity_fields
            or assignments != self.taxonomy_assignment_fields
            or not set(fields).issubset(allowed_identity)
            or not set(assignments).issubset(allowed_assignments)
            or not _nonempty(self.source_reference)
            or not isinstance(self.source_version_state, NseTaxonomySourceVersionState)
            or (
                self.source_version_state is NseTaxonomySourceVersionState.SOURCE_VERSION_AVAILABLE
                and not _nonempty(self.source_version)
            )
            or (
                self.source_version_state is NseTaxonomySourceVersionState.CURRENT_SOURCE_VERSION_UNAVAILABLE
                and self.source_version is not None
            )
        ):
            raise NseTaxonomySourceError("NSE_TAXONOMY_SOURCE_CANDIDATE_INVALID")


@dataclass(frozen=True, slots=True)
class NseTaxonomySampleReceipt:
    """A safe normalized receipt from one future quote request.

    Raw response retention belongs to the future acquisition operation; this
    domain object carries only canonical-safe fields and a content fingerprint.
    """

    candidate_id: str
    instrument: NseEquityInstrument
    status: NseTaxonomySampleStatus
    observed_at: datetime
    source_symbol: str | None
    source_isin: str | None
    source_series: str | None
    listing_status: str | None
    trading_status: str | None
    basic_industry: str | None
    source_content_fingerprint: str | None

    def __post_init__(self) -> None:
        response_present = self.status in {NseTaxonomySampleStatus.RECEIPT_ACCEPTED, NseTaxonomySampleStatus.SUCCESS_INCOMPLETE}
        no_response = self.status in {
            NseTaxonomySampleStatus.ACCESS_BLOCKED,
            NseTaxonomySampleStatus.RATE_LIMITED,
            NseTaxonomySampleStatus.SCHEMA_DRIFT,
        }
        metadata = (self.source_symbol, self.source_isin, self.source_series, self.listing_status, self.trading_status, self.basic_industry)
        if (
            not _ID.fullmatch(self.candidate_id)
            or not isinstance(self.instrument, NseEquityInstrument)
            or not _aware(self.observed_at)
            or not isinstance(self.status, NseTaxonomySampleStatus)
            or (response_present and (not _FP.fullmatch(self.source_content_fingerprint or "") or not _nonempty(self.source_symbol) or not _nonempty(self.source_isin)))
            or (no_response and (any(value is not None for value in metadata) or self.source_content_fingerprint is not None))
            or (self.status is NseTaxonomySampleStatus.IDENTITY_MISMATCH and (not _FP.fullmatch(self.source_content_fingerprint or "") or not _nonempty(self.source_symbol) or not _nonempty(self.source_isin)))
            or (self.status is NseTaxonomySampleStatus.IDENTITY_MISMATCH and self.basic_industry is not None)
        ):
            raise NseTaxonomySourceError("NSE_TAXONOMY_SAMPLE_RECEIPT_INVALID")


@dataclass(frozen=True, slots=True)
class NseTaxonomySampleAssessment:
    canonical_instrument_id: str
    candidate_id: str
    receipt_status: NseTaxonomySampleStatus
    conclusion: NseTaxonomySampleConclusion
    macro_economic_sector: str | None
    sector: str | None
    industry: str | None
    basic_industry: str | None
    source_content_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        fields = (self.macro_economic_sector, self.sector, self.industry, self.basic_industry)
        exact = self.conclusion is NseTaxonomySampleConclusion.EXACT_FOUR_LEVEL_ASSIGNMENT
        source_body_seen = self.conclusion not in {
            NseTaxonomySampleConclusion.SOURCE_ACCESS_BLOCKED,
            NseTaxonomySampleConclusion.SOURCE_RATE_LIMITED,
            NseTaxonomySampleConclusion.SOURCE_SCHEMA_DRIFT,
        }
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not _ID.fullmatch(self.candidate_id)
            or not isinstance(self.receipt_status, NseTaxonomySampleStatus)
            or not isinstance(self.conclusion, NseTaxonomySampleConclusion)
            or self.conclusion not in _allowed_conclusions(self.receipt_status)
            or (exact != all(_nonempty(value) for value in fields))
            or (not exact and any(value is not None for value in fields))
            or (source_body_seen and not _FP.fullmatch(self.source_content_fingerprint or ""))
            or (not source_body_seen and self.source_content_fingerprint is not None)
            or (not _FP.fullmatch(self.fingerprint))
            or self.fingerprint != _fingerprint(_sample_assessment_values(self, include_fingerprint=False))
        ):
            raise NseTaxonomySourceError("NSE_TAXONOMY_SAMPLE_ASSESSMENT_INVALID")


@dataclass(frozen=True, slots=True)
class NseTaxonomyAcquisitionPolicy:
    """A non-executing safety contract for a later approved backfill."""

    max_concurrent_requests: int
    minimum_interval_seconds: int
    retain_raw_first_party_receipt: bool
    cache_successful_response: bool
    checkpoint_each_document: bool
    stop_on_access_or_rate_limit: bool
    statuses: tuple[NseTaxonomySampleStatus, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, NseTaxonomySampleStatus) for value in self.statuses):
            raise NseTaxonomySourceError("NSE_TAXONOMY_ACQUISITION_POLICY_INVALID")
        ordered_statuses = tuple(sorted(set(self.statuses), key=lambda value: value.value))
        if (
            self.max_concurrent_requests != 1
            or self.minimum_interval_seconds < 2
            or not all((self.retain_raw_first_party_receipt, self.cache_successful_response, self.checkpoint_each_document, self.stop_on_access_or_rate_limit))
            or self.statuses != ordered_statuses
            or set(self.statuses) != set(NseTaxonomySampleStatus)
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(_policy_values(self, include_fingerprint=False))
        ):
            raise NseTaxonomySourceError("NSE_TAXONOMY_ACQUISITION_POLICY_INVALID")


@dataclass(frozen=True, slots=True)
class NseAllListedTaxonomySourceAssessment:
    audit_as_of: datetime
    candidates: tuple[NseTaxonomySourceCandidate, ...]
    sample_assessments: tuple[NseTaxonomySampleAssessment, ...]
    decision: NseAllListedTaxonomyDecision
    applicability: CurrentDescriptiveTaxonomyState
    strict_historical_pit_state: StrictHistoricalPitTaxonomyState
    acquisition_policy: NseTaxonomyAcquisitionPolicy
    fingerprint: str

    def __post_init__(self) -> None:
        candidates = tuple(sorted(self.candidates, key=lambda value: value.candidate_id))
        samples = tuple(sorted(self.sample_assessments, key=lambda value: (value.candidate_id, value.canonical_instrument_id)))
        candidate_ids = {value.candidate_id for value in candidates}
        if (
            not _aware(self.audit_as_of)
            or not candidates
            or self.candidates != candidates
            or self.sample_assessments != samples
            or len({value.candidate_id for value in self.candidates}) != len(self.candidates)
            or len({(value.candidate_id, value.canonical_instrument_id) for value in self.sample_assessments}) != len(self.sample_assessments)
            or any(value.candidate_id not in candidate_ids for value in self.sample_assessments)
            or self.decision != _decision(candidates, samples)
            or self.applicability is not CurrentDescriptiveTaxonomyState.CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY
            or self.strict_historical_pit_state is not StrictHistoricalPitTaxonomyState.NOT_READY
            or not isinstance(self.acquisition_policy, NseTaxonomyAcquisitionPolicy)
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(_assessment_values(self, include_fingerprint=False))
        ):
            raise NseTaxonomySourceError("NSE_ALL_LISTED_TAXONOMY_SOURCE_ASSESSMENT_INVALID")


def create_conservative_nse_taxonomy_acquisition_policy() -> NseTaxonomyAcquisitionPolicy:
    """Return the fixed non-executing policy for a separately approved run."""
    values = {
        "max_concurrent_requests": 1,
        "minimum_interval_seconds": 2,
        "retain_raw_first_party_receipt": True,
        "cache_successful_response": True,
        "checkpoint_each_document": True,
        "stop_on_access_or_rate_limit": True,
        "statuses": tuple(sorted(NseTaxonomySampleStatus, key=lambda value: value.value)),
    }
    return NseTaxonomyAcquisitionPolicy(**values, fingerprint=_fingerprint(values))


def assess_nse_all_listed_taxonomy_source(
    *, audit_as_of: datetime, candidates: Iterable[NseTaxonomySourceCandidate],
    sample_receipts: Iterable[NseTaxonomySampleReceipt], hierarchy: Iterable[NseIndustryHierarchyEntry],
) -> NseAllListedTaxonomySourceAssessment:
    """Assess injected source findings without I/O, a clock, or promotion.

    ``PER_SECURITY_*_READY`` requires samples that expose exact ISIN and
    symbol identity plus a Basic Industry that resolves uniquely through the
    supplied official hierarchy.  The Basic Industry is then the only source
    label used to derive the four descriptive levels.
    """
    if not _aware(audit_as_of):
        raise NseTaxonomySourceError("NSE_ALL_LISTED_TAXONOMY_AUDIT_AS_OF_REQUIRED")
    source_candidates = tuple(sorted(candidates, key=lambda value: value.candidate_id))
    receipts = tuple(sample_receipts)
    entries = tuple(hierarchy)
    if (
        not source_candidates
        or len({value.candidate_id for value in source_candidates}) != len(source_candidates)
        or any(not isinstance(value, NseTaxonomySourceCandidate) for value in source_candidates)
        or any(not isinstance(value, NseTaxonomySampleReceipt) for value in receipts)
        or len({(value.candidate_id, value.instrument.instrument_id) for value in receipts}) != len(receipts)
        or any(not isinstance(value, NseIndustryHierarchyEntry) for value in entries)
    ):
        raise NseTaxonomySourceError("NSE_ALL_LISTED_TAXONOMY_SOURCE_INPUT_INVALID")
    by_candidate = {value.candidate_id: value for value in source_candidates}
    if any(value.candidate_id not in by_candidate for value in receipts):
        raise NseTaxonomySourceError("NSE_ALL_LISTED_TAXONOMY_SAMPLE_SOURCE_UNKNOWN")
    assessments = tuple(sorted(
        (_assess_receipt(value, by_candidate[value.candidate_id], entries, audit_as_of.astimezone(UTC)) for value in receipts),
        key=lambda value: (value.candidate_id, value.canonical_instrument_id),
    ))
    decision = _decision(source_candidates, assessments)
    policy = create_conservative_nse_taxonomy_acquisition_policy()
    values = {
        "audit_as_of": audit_as_of.astimezone(UTC), "candidates": source_candidates,
        "sample_assessments": assessments, "decision": decision,
        "applicability": CurrentDescriptiveTaxonomyState.CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY,
        "strict_historical_pit_state": StrictHistoricalPitTaxonomyState.NOT_READY,
        "acquisition_policy": policy,
    }
    return NseAllListedTaxonomySourceAssessment(**values, fingerprint=_fingerprint(_assessment_values_from(values)))


def serialize_nse_all_listed_taxonomy_source_assessment(value: NseAllListedTaxonomySourceAssessment) -> str:
    value.__post_init__()
    return json.dumps(_assessment_values(value, include_fingerprint=True), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _assess_receipt(
    receipt: NseTaxonomySampleReceipt, candidate: NseTaxonomySourceCandidate,
    hierarchy: tuple[NseIndustryHierarchyEntry, ...], cutoff: datetime,
) -> NseTaxonomySampleAssessment:
    if receipt.status is NseTaxonomySampleStatus.ACCESS_BLOCKED:
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_ACCESS_BLOCKED)
    if receipt.status is NseTaxonomySampleStatus.RATE_LIMITED:
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_RATE_LIMITED)
    if receipt.status is NseTaxonomySampleStatus.SCHEMA_DRIFT:
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_SCHEMA_DRIFT)
    if receipt.observed_at.astimezone(UTC) > cutoff:
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE)
    if receipt.status is NseTaxonomySampleStatus.IDENTITY_MISMATCH or not _exact_identity(receipt):
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.IDENTITY_UNRESOLVED)
    if receipt.status is NseTaxonomySampleStatus.SUCCESS_INCOMPLETE or not _nonempty(receipt.basic_industry):
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE)
    if not {"isin", "symbol"}.issubset(candidate.exact_identity_fields) or "basic_industry" not in candidate.taxonomy_assignment_fields:
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.SOURCE_SCHEMA_DRIFT)
    resolved = resolve_nse_indices_label(receipt.basic_industry, hierarchy, expected_level="BASIC_INDUSTRY")
    if resolved.status != "EXACT_UNIQUE":
        return _sample_assessment(receipt, NseTaxonomySampleConclusion.HIERARCHY_UNRESOLVED)
    return _sample_assessment(
        receipt, NseTaxonomySampleConclusion.EXACT_FOUR_LEVEL_ASSIGNMENT,
        macro=resolved.macro_name, sector=resolved.sector_name,
        industry=resolved.industry_name, basic=resolved.basic_industry_name,
    )


def _sample_assessment(
    receipt: NseTaxonomySampleReceipt, conclusion: NseTaxonomySampleConclusion, *,
    macro: str | None = None, sector: str | None = None, industry: str | None = None, basic: str | None = None,
) -> NseTaxonomySampleAssessment:
    values = {
        "canonical_instrument_id": receipt.instrument.instrument_id, "candidate_id": receipt.candidate_id,
        "receipt_status": receipt.status, "conclusion": conclusion, "macro_economic_sector": macro,
        "sector": sector, "industry": industry, "basic_industry": basic,
        "source_content_fingerprint": receipt.source_content_fingerprint,
    }
    return NseTaxonomySampleAssessment(**values, fingerprint=_fingerprint(_sample_assessment_values_from(values)))


def _decision(
    candidates: tuple[NseTaxonomySourceCandidate, ...], samples: tuple[NseTaxonomySampleAssessment, ...],
) -> NseAllListedTaxonomyDecision:
    bulk_ready = any(
        candidate.authority in {NseTaxonomyAuthority.FIRST_PARTY_NSE, NseTaxonomyAuthority.FIRST_PARTY_NSE_INDICES}
        and candidate.acquisition_mode is NseTaxonomyAcquisitionMode.BULK
        and candidate.universe_completeness is NseTaxonomyUniverseCompleteness.ALL_LISTED
        and candidate.availability is NseTaxonomySourceAvailability.VERIFIED
        and {"isin", "symbol"}.issubset(candidate.exact_identity_fields)
        and {"macro_economic_sector", "sector", "industry", "basic_industry"}.issubset(candidate.taxonomy_assignment_fields)
        for candidate in candidates
    )
    if bulk_ready:
        return NseAllListedTaxonomyDecision.ALL_LISTED_TAXONOMY_BULK_SOURCE_READY
    per_security_candidates = {
        candidate.candidate_id for candidate in candidates
        if candidate.authority is NseTaxonomyAuthority.FIRST_PARTY_NSE
        and candidate.acquisition_mode is NseTaxonomyAcquisitionMode.PER_SECURITY
        and candidate.availability is NseTaxonomySourceAvailability.VERIFIED
        and {"isin", "symbol"}.issubset(candidate.exact_identity_fields)
        and "basic_industry" in candidate.taxonomy_assignment_fields
    }
    per_security_samples = tuple(value for value in samples if value.candidate_id in per_security_candidates)
    if per_security_samples and all(value.conclusion is NseTaxonomySampleConclusion.EXACT_FOUR_LEVEL_ASSIGNMENT for value in per_security_samples):
        return NseAllListedTaxonomyDecision.PER_SECURITY_FIRST_PARTY_TAXONOMY_SOURCE_READY
    if candidates:
        return NseAllListedTaxonomyDecision.FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL
    return NseAllListedTaxonomyDecision.FIRST_PARTY_ALL_LISTED_TAXONOMY_NOT_FOUND


def _exact_identity(value: NseTaxonomySampleReceipt) -> bool:
    return (
        value.instrument.isin is not None
        and value.source_isin == value.instrument.isin
        and value.source_symbol == value.instrument.symbol
    )


def _allowed_conclusions(status: NseTaxonomySampleStatus) -> frozenset[NseTaxonomySampleConclusion]:
    return {
        NseTaxonomySampleStatus.RECEIPT_ACCEPTED: frozenset({
            NseTaxonomySampleConclusion.EXACT_FOUR_LEVEL_ASSIGNMENT,
            NseTaxonomySampleConclusion.IDENTITY_UNRESOLVED,
            NseTaxonomySampleConclusion.HIERARCHY_UNRESOLVED,
            NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE,
        }),
        NseTaxonomySampleStatus.SUCCESS_INCOMPLETE: frozenset({
            NseTaxonomySampleConclusion.IDENTITY_UNRESOLVED,
            NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE,
        }),
        NseTaxonomySampleStatus.IDENTITY_MISMATCH: frozenset({NseTaxonomySampleConclusion.IDENTITY_UNRESOLVED}),
        NseTaxonomySampleStatus.ACCESS_BLOCKED: frozenset({NseTaxonomySampleConclusion.SOURCE_ACCESS_BLOCKED}),
        NseTaxonomySampleStatus.RATE_LIMITED: frozenset({NseTaxonomySampleConclusion.SOURCE_RATE_LIMITED}),
        NseTaxonomySampleStatus.SCHEMA_DRIFT: frozenset({NseTaxonomySampleConclusion.SOURCE_SCHEMA_DRIFT}),
    }[status]


def _assessment_values(value: NseAllListedTaxonomySourceAssessment, *, include_fingerprint: bool) -> dict[str, object]:
    values = _assessment_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _assessment_values_from(values: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION,
        "audit_as_of": _timestamp(values["audit_as_of"]),
        "candidates": [_candidate_values(value) for value in values["candidates"]],
        "sample_assessments": [_sample_assessment_values(value, include_fingerprint=True) for value in values["sample_assessments"]],
        "decision": _enum(values["decision"]), "applicability": _enum(values["applicability"]),
        "strict_historical_pit_state": _enum(values["strict_historical_pit_state"]),
        "acquisition_policy": _policy_values(values["acquisition_policy"], include_fingerprint=True),
    }


def _candidate_values(value: NseTaxonomySourceCandidate) -> dict[str, object]:
    return {field: _enum(getattr(value, field)) for field in value.__dataclass_fields__}


def _sample_assessment_values(value: NseTaxonomySampleAssessment, *, include_fingerprint: bool) -> dict[str, object]:
    values = _sample_assessment_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _sample_assessment_values_from(values: dict[str, object]) -> dict[str, object]:
    return {key: _enum(value) for key, value in values.items()}


def _policy_values(value: NseTaxonomyAcquisitionPolicy, *, include_fingerprint: bool) -> dict[str, object]:
    values = {field: _enum(getattr(value, field)) for field in value.__dataclass_fields__ if field != "fingerprint"}
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _timestamp(value: object) -> str:
    if not _aware(value):
        raise NseTaxonomySourceError("NSE_TAXONOMY_TIMESTAMP_INVALID")
    return value.astimezone(UTC).isoformat()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _enum(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, tuple):
        return [_enum(item) for item in value]
    return value


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "CurrentDescriptiveTaxonomyState",
    "NSE_EQUITY_ALL_SECURITIES_SOURCE", "NSE_EQUITY_QUOTE_SOURCE",
    "NseAllListedTaxonomyDecision", "NseAllListedTaxonomySourceAssessment",
    "NseTaxonomyAcquisitionMode", "NseTaxonomyAcquisitionPolicy", "NseTaxonomyAuthority",
    "NseTaxonomySampleAssessment", "NseTaxonomySampleConclusion", "NseTaxonomySampleReceipt",
    "NseTaxonomySampleStatus", "NseTaxonomySourceAvailability", "NseTaxonomySourceCandidate",
    "NseTaxonomySourceError", "NseTaxonomySourceVersionState", "NseTaxonomyUniverseCompleteness",
    "StrictHistoricalPitTaxonomyState", "assess_nse_all_listed_taxonomy_source",
    "create_conservative_nse_taxonomy_acquisition_policy", "serialize_nse_all_listed_taxonomy_source_assessment",
)
