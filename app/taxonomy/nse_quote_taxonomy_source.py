"""Pure proof contract for the first-party NSE per-security quote surface.

The quote page may visibly render useful current classification information
while the underlying payload is not normally accessible or the static HTML is
only an application shell.  This module records that distinction.  It never
fetches NSE, parses a browser DOM, writes a receipt, promotes a classification,
or turns current taxonomy into historical PIT evidence.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from app.taxonomy.nse_all_listed_security_taxonomy_source import (
    NseTaxonomyAcquisitionPolicy,
    create_conservative_nse_taxonomy_acquisition_policy,
)
from app.taxonomy.nse_indices import NseIndustryHierarchyEntry, resolve_nse_indices_label
from app.universe_analysis.models import NseEquityInstrument


CONTRACT_ID = "nse-first-party-quote-taxonomy-access-and-schema-proof"
CONTRACT_VERSION = "v1"
NSE_QUOTE_PAGE_IDENTITY = "NSE_EQUITY_QUOTE_PAGE"
NSE_QUOTE_RESOURCE_IDENTITY = "NSE_EQUITY_QUOTE_RESOURCE"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class NseQuoteTaxonomyPrimaryResult(StrEnum):
    QUOTE_TAXONOMY_SOURCE_READY = "QUOTE_TAXONOMY_SOURCE_READY"
    QUOTE_TAXONOMY_SOURCE_READY_HTML_ONLY = "QUOTE_TAXONOMY_SOURCE_READY_HTML_ONLY"
    QUOTE_TAXONOMY_SOURCE_PARTIAL = "QUOTE_TAXONOMY_SOURCE_PARTIAL"
    QUOTE_TAXONOMY_SOURCE_ACCESS_BLOCKED = "QUOTE_TAXONOMY_SOURCE_ACCESS_BLOCKED"
    QUOTE_TAXONOMY_SOURCE_NOT_SUITABLE = "QUOTE_TAXONOMY_SOURCE_NOT_SUITABLE"


class NseQuoteTaxonomyRetrievalStatus(StrEnum):
    STATIC_HTML_SHELL_RECEIPT = "STATIC_HTML_SHELL_RECEIPT"
    MACHINE_RESOURCE_ACCESS_BLOCKED = "MACHINE_RESOURCE_ACCESS_BLOCKED"
    RENDERED_PUBLIC_FIELDS_OBSERVED = "RENDERED_PUBLIC_FIELDS_OBSERVED"
    MACHINE_PAYLOAD_RECEIPT_ACCEPTED = "MACHINE_PAYLOAD_RECEIPT_ACCEPTED"
    HTML_PARSER_RECEIPT_ACCEPTED = "HTML_PARSER_RECEIPT_ACCEPTED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_NOT_SUITABLE = "SOURCE_NOT_SUITABLE"


class NseQuoteTaxonomySchemaState(StrEnum):
    MACHINE_SCHEMA_PROVEN = "MACHINE_SCHEMA_PROVEN"
    SOURCE_MACHINE_SCHEMA_NOT_READY = "SOURCE_MACHINE_SCHEMA_NOT_READY"


class NseQuoteTaxonomySampleConclusion(StrEnum):
    SAMPLE_TAXONOMY_PROVEN = "SAMPLE_TAXONOMY_PROVEN"
    RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE = "RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    HIERARCHY_IDENTITY_AMBIGUOUS = "HIERARCHY_IDENTITY_AMBIGUOUS"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class NseQuoteTaxonomyReconciliationStatus(StrEnum):
    EXACT_COMPATIBLE = "EXACT_COMPATIBLE"
    RICHER_HIERARCHY_COMPATIBLE = "RICHER_HIERARCHY_COMPATIBLE"
    CONFLICTED = "CONFLICTED"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"


class CurrentDescriptiveTaxonomyState(StrEnum):
    CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY = "CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY"


class StrictHistoricalPitTaxonomyState(StrEnum):
    NOT_READY = "NOT_READY"


class NseQuoteTaxonomySourceVersionState(StrEnum):
    SOURCE_CLASSIFICATION_VERSION_AVAILABLE = "SOURCE_CLASSIFICATION_VERSION_AVAILABLE"
    SOURCE_CLASSIFICATION_VERSION_UNAVAILABLE = "SOURCE_CLASSIFICATION_VERSION_UNAVAILABLE"


class NseQuoteTaxonomySourceError(ValueError):
    """Stable fail-closed error for malformed quote-source proof input."""


@dataclass(frozen=True, slots=True)
class NseQuoteTaxonomyObservation:
    """One injected normal-access observation, not a taxonomy assignment."""

    observation_id: str
    source_identity: str
    instrument: NseEquityInstrument
    retrieval_status: NseQuoteTaxonomyRetrievalStatus
    observed_at: datetime
    source_url: str
    source_content_fingerprint: str | None
    source_symbol: str | None
    source_isin: str | None
    source_series: tuple[str, ...]
    listing_status: str | None
    trading_status: str | None
    basic_industry: str | None
    basic_industry_code: str | None
    source_sector: str | None
    source_industry: str | None
    source_macro_economic_sector: str | None
    source_classification_version: str | None
    source_version_state: NseQuoteTaxonomySourceVersionState

    def __post_init__(self) -> None:
        stable = self.retrieval_status in {
            NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
            NseQuoteTaxonomyRetrievalStatus.HTML_PARSER_RECEIPT_ACCEPTED,
        }
        shell = self.retrieval_status is NseQuoteTaxonomyRetrievalStatus.STATIC_HTML_SHELL_RECEIPT
        rendered = self.retrieval_status is NseQuoteTaxonomyRetrievalStatus.RENDERED_PUBLIC_FIELDS_OBSERVED
        unavailable = self.retrieval_status in {
            NseQuoteTaxonomyRetrievalStatus.MACHINE_RESOURCE_ACCESS_BLOCKED,
            NseQuoteTaxonomyRetrievalStatus.SOURCE_UNAVAILABLE,
            NseQuoteTaxonomyRetrievalStatus.SOURCE_NOT_SUITABLE,
        }
        taxonomy_values = (
            self.source_symbol, self.source_isin, self.source_series, self.listing_status,
            self.trading_status, self.basic_industry, self.basic_industry_code, self.source_sector,
            self.source_industry, self.source_macro_economic_sector,
        )
        required_rendered = (
            _nonempty(self.source_symbol), _nonempty(self.source_isin), bool(self.source_series),
            _nonempty(self.listing_status), _nonempty(self.trading_status), _nonempty(self.basic_industry),
        )
        canonical_series = tuple(sorted(set(self.source_series)))
        if (
            not _ID.fullmatch(self.observation_id)
            or self.source_identity not in {NSE_QUOTE_PAGE_IDENTITY, NSE_QUOTE_RESOURCE_IDENTITY}
            or not isinstance(self.instrument, NseEquityInstrument)
            or not isinstance(self.retrieval_status, NseQuoteTaxonomyRetrievalStatus)
            or not _aware(self.observed_at)
            or not _nse_url(self.source_url)
            or canonical_series != self.source_series
            or not all(_nonempty(value) for value in self.source_series)
            or not isinstance(self.source_version_state, NseQuoteTaxonomySourceVersionState)
            or (
                self.source_version_state is NseQuoteTaxonomySourceVersionState.SOURCE_CLASSIFICATION_VERSION_AVAILABLE
                and not _nonempty(self.source_classification_version)
            )
            or (
                self.source_version_state is NseQuoteTaxonomySourceVersionState.SOURCE_CLASSIFICATION_VERSION_UNAVAILABLE
                and self.source_classification_version is not None
            )
            or ((stable or shell) and not _FP.fullmatch(self.source_content_fingerprint or ""))
            or (rendered and self.source_content_fingerprint is not None)
            or (unavailable and (self.source_content_fingerprint is not None or any(taxonomy_values)))
            or (shell and any(taxonomy_values))
            or ((stable or rendered) and not all(required_rendered))
        ):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_OBSERVATION_INVALID")


@dataclass(frozen=True, slots=True)
class NseQuoteTaxonomyHierarchyAudit:
    total_basic_industries: int
    unique_basic_industry_labels: int
    duplicate_basic_industry_labels: tuple[str, ...]
    ambiguous_basic_industry_labels: tuple[str, ...]
    unique_basic_industry_codes: int
    missing_basic_industry_codes: int
    fingerprint: str

    def __post_init__(self) -> None:
        canonical_duplicates = tuple(sorted(set(self.duplicate_basic_industry_labels)))
        canonical_ambiguous = tuple(sorted(set(self.ambiguous_basic_industry_labels)))
        values = _hierarchy_audit_values(self, include_fingerprint=False)
        if (
            self.total_basic_industries <= 0
            or self.unique_basic_industry_labels <= 0
            or self.unique_basic_industry_codes < 0
            or self.missing_basic_industry_codes < 0
            or canonical_duplicates != self.duplicate_basic_industry_labels
            or canonical_ambiguous != self.ambiguous_basic_industry_labels
            or self.duplicate_basic_industry_labels != self.ambiguous_basic_industry_labels
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_HIERARCHY_AUDIT_INVALID")


@dataclass(frozen=True, slots=True)
class NseQuoteTaxonomySampleAssessment:
    canonical_instrument_id: str
    conclusion: NseQuoteTaxonomySampleConclusion
    source_symbol: str | None
    source_isin: str | None
    basic_industry: str | None
    basic_industry_code: str | None
    macro_economic_sector: str | None
    sector: str | None
    industry: str | None
    source_content_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        resolved = self.conclusion in {
            NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN,
            NseQuoteTaxonomySampleConclusion.RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE,
        }
        fields = (self.basic_industry, self.macro_economic_sector, self.sector, self.industry)
        values = _sample_values(self, include_fingerprint=False)
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not isinstance(self.conclusion, NseQuoteTaxonomySampleConclusion)
            or (resolved and (not _nonempty(self.source_symbol) or not _nonempty(self.source_isin) or not all(_nonempty(value) for value in fields)))
            or (resolved and self.conclusion is NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN and not _FP.fullmatch(self.source_content_fingerprint or ""))
            or (resolved and self.conclusion is NseQuoteTaxonomySampleConclusion.RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE and self.source_content_fingerprint is not None)
            or (not resolved and any(value is not None for value in (self.basic_industry, self.basic_industry_code, self.macro_economic_sector, self.sector, self.industry, self.source_content_fingerprint)))
            or (self.conclusion is NseQuoteTaxonomySampleConclusion.IDENTITY_MISMATCH and (not _nonempty(self.source_symbol) or not _nonempty(self.source_isin)))
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(values)
        ):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_SAMPLE_ASSESSMENT_INVALID")


@dataclass(frozen=True, slots=True)
class NseQuoteTaxonomySourceAssessment:
    audit_as_of: datetime
    observations: tuple[NseQuoteTaxonomyObservation, ...]
    sample_assessments: tuple[NseQuoteTaxonomySampleAssessment, ...]
    hierarchy_audit: NseQuoteTaxonomyHierarchyAudit
    primary_result: NseQuoteTaxonomyPrimaryResult
    schema_state: NseQuoteTaxonomySchemaState
    applicability: CurrentDescriptiveTaxonomyState
    strict_historical_pit_state: StrictHistoricalPitTaxonomyState
    acquisition_policy: NseTaxonomyAcquisitionPolicy
    fingerprint: str

    def __post_init__(self) -> None:
        if not _aware(self.audit_as_of):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_SOURCE_ASSESSMENT_INVALID")
        if (
            any(not isinstance(value, NseQuoteTaxonomyObservation) for value in self.observations)
            or any(not isinstance(value, NseQuoteTaxonomySampleAssessment) for value in self.sample_assessments)
        ):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_SOURCE_ASSESSMENT_INVALID")
        observations = tuple(sorted(self.observations, key=lambda value: value.observation_id))
        samples = tuple(sorted(self.sample_assessments, key=lambda value: value.canonical_instrument_id))
        eligible = tuple(value for value in observations if value.observed_at.astimezone(UTC) <= self.audit_as_of.astimezone(UTC))
        expected_schema_state = (
            NseQuoteTaxonomySchemaState.MACHINE_SCHEMA_PROVEN
            if any(value.retrieval_status is NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED for value in eligible)
            else NseQuoteTaxonomySchemaState.SOURCE_MACHINE_SCHEMA_NOT_READY
        )
        if (
            not observations
            or observations != self.observations
            or samples != self.sample_assessments
            or len({value.observation_id for value in observations}) != len(observations)
            or len({value.canonical_instrument_id for value in samples}) != len(samples)
            or any(value.observed_at.astimezone(UTC) > self.audit_as_of.astimezone(UTC) for value in observations)
            or not isinstance(self.hierarchy_audit, NseQuoteTaxonomyHierarchyAudit)
            or not isinstance(self.primary_result, NseQuoteTaxonomyPrimaryResult)
            or not isinstance(self.schema_state, NseQuoteTaxonomySchemaState)
            or self.schema_state is not expected_schema_state
            or self.primary_result != _primary_result(eligible, samples, self.schema_state)
            or self.applicability is not CurrentDescriptiveTaxonomyState.CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY
            or self.strict_historical_pit_state is not StrictHistoricalPitTaxonomyState.NOT_READY
            or not isinstance(self.acquisition_policy, NseTaxonomyAcquisitionPolicy)
            or self.acquisition_policy != create_conservative_nse_taxonomy_acquisition_policy()
            or not _FP.fullmatch(self.fingerprint)
            or self.fingerprint != _fingerprint(_assessment_values(self, include_fingerprint=False))
        ):
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_SOURCE_ASSESSMENT_INVALID")


def audit_nse_quote_taxonomy_hierarchy(
    hierarchy: Iterable[NseIndustryHierarchyEntry],
) -> NseQuoteTaxonomyHierarchyAudit:
    """Audit the retained official hierarchy without label repair or I/O."""
    entries = tuple(hierarchy)
    if not entries or any(not isinstance(value, NseIndustryHierarchyEntry) for value in entries):
        raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_HIERARCHY_REQUIRED")
    labels: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    codes: set[str] = set()
    missing_codes = 0
    for value in entries:
        label = _normalized(value.basic_industry_name)
        if not label:
            raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_HIERARCHY_INVALID")
        lineage = (value.macro_code, value.sector_code, value.industry_code, value.basic_industry_code)
        labels[label].add(lineage)
        if _normalized(value.basic_industry_code):
            codes.add(_normalized(value.basic_industry_code))
        else:
            missing_codes += 1
    duplicates = tuple(sorted(label for label, lineages in labels.items() if len(lineages) > 1))
    values = {
        "total_basic_industries": len(entries), "unique_basic_industry_labels": len(labels),
        "duplicate_basic_industry_labels": duplicates, "ambiguous_basic_industry_labels": duplicates,
        "unique_basic_industry_codes": len(codes), "missing_basic_industry_codes": missing_codes,
    }
    return NseQuoteTaxonomyHierarchyAudit(**values, fingerprint=_fingerprint(values))


def assess_nse_quote_taxonomy_source(
    *, audit_as_of: datetime, observations: Iterable[NseQuoteTaxonomyObservation], hierarchy: Iterable[NseIndustryHierarchyEntry],
) -> NseQuoteTaxonomySourceAssessment:
    """Assess only injected normal-access observations.

    A rendered page is descriptive evidence, but it is not a promoted source
    receipt.  ``SAMPLE_TAXONOMY_PROVEN`` therefore requires a byte-retained
    accepted machine payload or an explicitly stable HTML parser receipt.
    """
    if not _aware(audit_as_of):
        raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_AUDIT_AS_OF_REQUIRED")
    source_observations = tuple(sorted(observations, key=lambda value: value.observation_id))
    entries = tuple(hierarchy)
    if (
        not source_observations
        or len({value.observation_id for value in source_observations}) != len(source_observations)
        or any(not isinstance(value, NseQuoteTaxonomyObservation) for value in source_observations)
        or any(not isinstance(value, NseIndustryHierarchyEntry) for value in entries)
    ):
        raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_SOURCE_INPUT_INVALID")
    cutoff = audit_as_of.astimezone(UTC)
    eligible_observations = tuple(value for value in source_observations if value.observed_at.astimezone(UTC) <= cutoff)
    if not eligible_observations:
        raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_NO_ELIGIBLE_OBSERVATION")
    audit = audit_nse_quote_taxonomy_hierarchy(entries)
    grouped: dict[str, list[NseQuoteTaxonomyObservation]] = defaultdict(list)
    for observation in eligible_observations:
        grouped[observation.instrument.instrument_id].append(observation)
    samples = tuple(sorted(
        (_assess_sample(values, entries) for _, values in sorted(grouped.items())),
        key=lambda value: value.canonical_instrument_id,
    ))
    schema_state = (
        NseQuoteTaxonomySchemaState.MACHINE_SCHEMA_PROVEN
        if any(value.retrieval_status is NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED for value in eligible_observations)
        else NseQuoteTaxonomySchemaState.SOURCE_MACHINE_SCHEMA_NOT_READY
    )
    values = {
        "audit_as_of": cutoff, "observations": eligible_observations, "sample_assessments": samples,
        "hierarchy_audit": audit, "schema_state": schema_state,
        "applicability": CurrentDescriptiveTaxonomyState.CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY,
        "strict_historical_pit_state": StrictHistoricalPitTaxonomyState.NOT_READY,
        "acquisition_policy": create_conservative_nse_taxonomy_acquisition_policy(),
    }
    primary = _primary_result(eligible_observations, samples, schema_state)
    return NseQuoteTaxonomySourceAssessment(**(values | {"primary_result": primary}), fingerprint=_fingerprint(_assessment_values_from(values | {"primary_result": primary})))


def reconcile_quote_taxonomy_sample(
    sample: NseQuoteTaxonomySampleAssessment, *, existing_macro_economic_sector: str | None,
    existing_sector: str | None, existing_industry: str | None = None,
    existing_basic_industry: str | None = None,
) -> NseQuoteTaxonomyReconciliationStatus:
    """Compare descriptive quote lineage with retained Core taxonomy; never write it."""
    if sample.conclusion is NseQuoteTaxonomySampleConclusion.IDENTITY_MISMATCH:
        return NseQuoteTaxonomyReconciliationStatus.IDENTITY_MISMATCH
    if sample.conclusion not in {
        NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN,
        NseQuoteTaxonomySampleConclusion.RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE,
    }:
        return NseQuoteTaxonomyReconciliationStatus.SOURCE_UNAVAILABLE
    if _normalized(sample.macro_economic_sector) != _normalized(existing_macro_economic_sector) or _normalized(sample.sector) != _normalized(existing_sector):
        return NseQuoteTaxonomyReconciliationStatus.CONFLICTED
    if _nonempty(existing_industry) and _nonempty(existing_basic_industry):
        if _normalized(sample.industry) == _normalized(existing_industry) and _normalized(sample.basic_industry) == _normalized(existing_basic_industry):
            return NseQuoteTaxonomyReconciliationStatus.EXACT_COMPATIBLE
        return NseQuoteTaxonomyReconciliationStatus.CONFLICTED
    return NseQuoteTaxonomyReconciliationStatus.RICHER_HIERARCHY_COMPATIBLE


def serialize_nse_quote_taxonomy_source_assessment(value: NseQuoteTaxonomySourceAssessment) -> str:
    value.__post_init__()
    return json.dumps(_assessment_values(value, include_fingerprint=True), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _assess_sample(
    observations: list[NseQuoteTaxonomyObservation], hierarchy: tuple[NseIndustryHierarchyEntry, ...],
) -> NseQuoteTaxonomySampleAssessment:
    instrument = observations[0].instrument
    stable = [value for value in observations if value.retrieval_status in {
        NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        NseQuoteTaxonomyRetrievalStatus.HTML_PARSER_RECEIPT_ACCEPTED,
    }]
    rendered = [value for value in observations if value.retrieval_status is NseQuoteTaxonomyRetrievalStatus.RENDERED_PUBLIC_FIELDS_OBSERVED]
    candidate = stable[0] if len(stable) == 1 else (rendered[0] if len(rendered) == 1 else None)
    if candidate is None:
        return _sample(instrument.instrument_id, NseQuoteTaxonomySampleConclusion.SOURCE_UNAVAILABLE)
    if not _exact_identity(candidate):
        return _sample(instrument.instrument_id, NseQuoteTaxonomySampleConclusion.IDENTITY_MISMATCH, candidate)
    resolved = _resolve_basic_industry(candidate, hierarchy)
    if resolved is None:
        return _sample(instrument.instrument_id, NseQuoteTaxonomySampleConclusion.HIERARCHY_IDENTITY_AMBIGUOUS, candidate)
    conclusion = (
        NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN
        if candidate in stable else NseQuoteTaxonomySampleConclusion.RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE
    )
    return _sample(instrument.instrument_id, conclusion, candidate, resolved)


def _resolve_basic_industry(
    observation: NseQuoteTaxonomyObservation, hierarchy: tuple[NseIndustryHierarchyEntry, ...],
) -> NseIndustryHierarchyEntry | None:
    if _nonempty(observation.basic_industry_code):
        matches = [value for value in hierarchy if _normalized(value.basic_industry_code) == _normalized(observation.basic_industry_code)]
        if len(matches) == 1 and _normalized(matches[0].basic_industry_name) == _normalized(observation.basic_industry):
            return matches[0]
        return None
    resolved = resolve_nse_indices_label(observation.basic_industry or "", hierarchy, expected_level="BASIC_INDUSTRY")
    if resolved.status != "EXACT_UNIQUE":
        return None
    return NseIndustryHierarchyEntry(
        resolved.macro_code or "", resolved.macro_name or "", resolved.sector_code or "", resolved.sector_name or "",
        resolved.industry_code or "", resolved.industry_name or "", resolved.basic_industry_code or "", resolved.basic_industry_name or "",
    )


def _sample(
    instrument_id: str, conclusion: NseQuoteTaxonomySampleConclusion,
    observation: NseQuoteTaxonomyObservation | None = None, resolved: NseIndustryHierarchyEntry | None = None,
) -> NseQuoteTaxonomySampleAssessment:
    values = {
        "canonical_instrument_id": instrument_id, "conclusion": conclusion,
        "source_symbol": observation.source_symbol if observation else None,
        "source_isin": observation.source_isin if observation else None,
        "basic_industry": resolved.basic_industry_name if resolved else None,
        "basic_industry_code": resolved.basic_industry_code if resolved else None,
        "macro_economic_sector": resolved.macro_name if resolved else None,
        "sector": resolved.sector_name if resolved else None,
        "industry": resolved.industry_name if resolved else None,
        "source_content_fingerprint": observation.source_content_fingerprint if observation and conclusion is NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN else None,
    }
    return NseQuoteTaxonomySampleAssessment(**values, fingerprint=_fingerprint(values))


def _primary_result(
    observations: tuple[NseQuoteTaxonomyObservation, ...], samples: tuple[NseQuoteTaxonomySampleAssessment, ...],
    schema_state: NseQuoteTaxonomySchemaState,
) -> NseQuoteTaxonomyPrimaryResult:
    statuses = {value.retrieval_status for value in observations}
    if not statuses:
        return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL
    proven = bool(samples) and all(value.conclusion is NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN for value in samples)
    if proven and schema_state is NseQuoteTaxonomySchemaState.MACHINE_SCHEMA_PROVEN:
        return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_READY
    if proven and NseQuoteTaxonomyRetrievalStatus.HTML_PARSER_RECEIPT_ACCEPTED in statuses:
        return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_READY_HTML_ONLY
    if statuses <= {NseQuoteTaxonomyRetrievalStatus.MACHINE_RESOURCE_ACCESS_BLOCKED, NseQuoteTaxonomyRetrievalStatus.SOURCE_UNAVAILABLE}:
        return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_ACCESS_BLOCKED
    if statuses == {NseQuoteTaxonomyRetrievalStatus.SOURCE_NOT_SUITABLE}:
        return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_NOT_SUITABLE
    return NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL


def _exact_identity(value: NseQuoteTaxonomyObservation) -> bool:
    return value.instrument.isin is not None and value.source_isin == value.instrument.isin and value.source_symbol == value.instrument.symbol


def _assessment_values(value: NseQuoteTaxonomySourceAssessment, *, include_fingerprint: bool) -> dict[str, object]:
    values = _assessment_values_from({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _assessment_values_from(values: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_ID, "version": CONTRACT_VERSION, "audit_as_of": _timestamp(values["audit_as_of"]),
        "observations": [_observation_values(value) for value in values["observations"]],
        "sample_assessments": [_sample_values(value, include_fingerprint=True) for value in values["sample_assessments"]],
        "hierarchy_audit": _hierarchy_audit_values(values["hierarchy_audit"], include_fingerprint=True),
        "primary_result": _enum(values["primary_result"]), "schema_state": _enum(values["schema_state"]),
        "applicability": _enum(values["applicability"]), "strict_historical_pit_state": _enum(values["strict_historical_pit_state"]),
        "acquisition_policy": _policy_values(values["acquisition_policy"]),
    }


def _observation_values(value: NseQuoteTaxonomyObservation) -> dict[str, object]:
    return {
        "observation_id": value.observation_id,
        "source_identity": value.source_identity,
        "canonical_instrument_id": value.instrument.instrument_id,
        "canonical_symbol": value.instrument.symbol,
        "canonical_isin": value.instrument.isin,
        "retrieval_status": _enum(value.retrieval_status),
        "observed_at": _timestamp(value.observed_at),
        "source_url": value.source_url,
        "source_content_fingerprint": value.source_content_fingerprint,
        "source_symbol": value.source_symbol,
        "source_isin": value.source_isin,
        "source_series": list(value.source_series),
        "listing_status": value.listing_status,
        "trading_status": value.trading_status,
        "basic_industry": value.basic_industry,
        "basic_industry_code": value.basic_industry_code,
        "source_sector": value.source_sector,
        "source_industry": value.source_industry,
        "source_macro_economic_sector": value.source_macro_economic_sector,
        "source_classification_version": value.source_classification_version,
        "source_version_state": _enum(value.source_version_state),
    }


def _sample_values(value: NseQuoteTaxonomySampleAssessment, *, include_fingerprint: bool) -> dict[str, object]:
    values = {field: _enum(getattr(value, field)) for field in value.__dataclass_fields__ if field != "fingerprint"}
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _hierarchy_audit_values(value: NseQuoteTaxonomyHierarchyAudit, *, include_fingerprint: bool) -> dict[str, object]:
    values = {field: _enum(getattr(value, field)) for field in value.__dataclass_fields__ if field != "fingerprint"}
    return values | ({"fingerprint": value.fingerprint} if include_fingerprint else {})


def _policy_values(value: NseTaxonomyAcquisitionPolicy) -> dict[str, object]:
    return {field: _enum(getattr(value, field)) for field in value.__dataclass_fields__}


def _timestamp(value: object) -> str:
    if not _aware(value):
        raise NseQuoteTaxonomySourceError("NSE_QUOTE_TAXONOMY_TIMESTAMP_INVALID")
    return value.astimezone(UTC).isoformat()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split()).upper()


def _nse_url(value: object) -> bool:
    return isinstance(value, str) and value.startswith("https://www.nseindia.com/")


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
    "CONTRACT_ID", "CONTRACT_VERSION", "CurrentDescriptiveTaxonomyState", "NSE_QUOTE_PAGE_IDENTITY",
    "NSE_QUOTE_RESOURCE_IDENTITY", "NseQuoteTaxonomyHierarchyAudit", "NseQuoteTaxonomyObservation",
    "NseQuoteTaxonomyPrimaryResult", "NseQuoteTaxonomyReconciliationStatus", "NseQuoteTaxonomySampleAssessment",
    "NseQuoteTaxonomySampleConclusion", "NseQuoteTaxonomySchemaState", "NseQuoteTaxonomySourceAssessment",
    "NseQuoteTaxonomySourceError", "NseQuoteTaxonomySourceVersionState", "NseQuoteTaxonomyRetrievalStatus",
    "StrictHistoricalPitTaxonomyState", "assess_nse_quote_taxonomy_source", "audit_nse_quote_taxonomy_hierarchy",
    "reconcile_quote_taxonomy_sample", "serialize_nse_quote_taxonomy_source_assessment",
)
