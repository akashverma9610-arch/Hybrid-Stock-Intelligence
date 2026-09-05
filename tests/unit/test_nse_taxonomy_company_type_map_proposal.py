from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.intelligence import nse_taxonomy_company_type_map_proposal as proposal
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification


T = datetime(2026, 8, 31, 12, tzinfo=UTC)
SOURCE_SHA = "a" * 64


def _classification(
    *,
    macro: str = "IN07",
    sector: str = "IN0702",
    source: str = proposal.NSE_TAXONOMY_SOURCE,
    version: str = proposal.NSE_TAXONOMY_VERSION,
    industry_code: str | None = None,
    basic_industry_code: str | None = None,
    effective_from: datetime = T - timedelta(days=4),
) -> InstrumentTaxonomyClassification:
    return InstrumentTaxonomyClassification(
        classification_id="nse-indices-taxonomy:fixture",
        instrument_id="NSE:INE372A01015",
        industry=None,
        sector="Display name deliberately not used by the proposal",
        super_sector="Another display name deliberately not used by the proposal",
        source=source,
        source_type=ClassificationSourceStatus.OFFICIAL,
        effective_from=effective_from,
        effective_to=None,
        as_of=effective_from,
        confidence=1.0,
        classification_version=version,
        source_reference="source=fixture",
        macro_economic_sector_code=macro,
        sector_code=sector,
        industry_code=industry_code,
        basic_industry_code=basic_industry_code,
        raw_classification_label="No free-text mapping is allowed",
        resolution_status="EXACT_UNIQUE",
        source_sha256=SOURCE_SHA,
        fetched_at_utc=effective_from,
        effective_observation_semantics=proposal.NSE_TAXONOMY_SEMANTICS,
    )


def test_fixed_proposal_is_exactly_non_active_and_deterministically_serialized():
    first = proposal.create_proposed_nse_taxonomy_company_type_map()
    second = proposal.create_proposed_nse_taxonomy_company_type_map()

    assert first == second
    assert first.status == (
        proposal.NseTaxonomyCompanyTypeMapStatus.PROPOSED,
        proposal.NseTaxonomyCompanyTypeMapStatus.NOT_APPROVED,
        proposal.NseTaxonomyCompanyTypeMapStatus.NOT_ACTIVE,
        proposal.NseTaxonomyCompanyTypeMapStatus.RESEARCH_ONLY,
        proposal.NseTaxonomyCompanyTypeMapStatus.NON_EXECUTABLE,
    )
    assert first.actionability == "WATCH_ONLY"
    assert first.execution_status == "NON_EXECUTABLE"
    assert proposal.serialize_proposed_nse_taxonomy_company_type_map(first) == proposal.serialize_proposed_nse_taxonomy_company_type_map(second)
    assert len(first.entries) == 19
    assert first.entries == tuple(sorted(first.entries, key=lambda item: (item.macro_economic_sector_code, item.sector_code, item.entry_id)))
    assert len({(item.macro_economic_sector_code, item.sector_code) for item in first.entries}) == len(first.entries)


def test_exact_sector_code_maps_non_financial_candidate_without_reading_display_names():
    value = _classification()
    renamed = replace(value, sector="Financial Services", super_sector="Financial Services", raw_classification_label="Bank and Insurance")

    first = proposal.assess_proposed_nse_taxonomy_map(value, as_of=T)
    second = proposal.assess_proposed_nse_taxonomy_map(renamed, as_of=T)

    assert first.category is proposal.NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE
    assert first.reason is proposal.NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_MAPPED
    assert second.category is first.category and second.map_entry_id == first.map_entry_id


def test_current_financial_sector_is_unsupported_not_regulated_or_non_financial():
    result = proposal.assess_proposed_nse_taxonomy_map(_classification(macro="IN05", sector="IN0501"), as_of=T)

    assert result.category is proposal.NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL
    assert result.category is not proposal.NseTaxonomyResearchCategory.REGULATED_FINANCIAL_CANDIDATE
    assert result.category is not proposal.NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE
    assert not any(item.category is proposal.NseTaxonomyResearchCategory.REGULATED_FINANCIAL_CANDIDATE for item in proposal.create_proposed_nse_taxonomy_company_type_map().entries)


def test_diversified_and_unknown_exact_codes_remain_fail_closed():
    mapped_unknown = proposal.assess_proposed_nse_taxonomy_map(_classification(macro="IN12", sector="IN1201"), as_of=T)
    unmapped = proposal.assess_proposed_nse_taxonomy_map(_classification(macro="IN99", sector="IN9901"), as_of=T)

    assert mapped_unknown.category is proposal.NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE
    assert mapped_unknown.reason is proposal.NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_MAPPED
    assert unmapped.category is proposal.NseTaxonomyResearchCategory.UNMAPPED
    assert unmapped.reason is proposal.NseTaxonomyMapAuditReason.EXACT_TAXONOMY_IDENTITY_UNMAPPED


def test_more_specific_taxonomy_is_not_reclassified_by_the_broad_sector_map():
    value = _classification(macro="IN05", sector="IN0501", industry_code="IN050101", basic_industry_code="IN050101001")

    result = proposal.assess_proposed_nse_taxonomy_map(value, as_of=T)

    assert result.category is proposal.NseTaxonomyResearchCategory.UNMAPPED
    assert result.reason is proposal.NseTaxonomyMapAuditReason.LOWEST_RELIABLE_LEVEL_MAP_REQUIRED


def test_future_current_taxonomy_is_excluded_without_backward_fallback():
    current = _classification(effective_from=T)

    result = proposal.assess_proposed_nse_taxonomy_map(current, as_of=T - timedelta(microseconds=1))

    assert result.category is proposal.NseTaxonomyResearchCategory.UNMAPPED
    assert result.reason is proposal.NseTaxonomyMapAuditReason.PIT_TAXONOMY_UNAVAILABLE


def test_source_version_and_malformed_exact_identity_fail_closed_or_reject():
    unsupported_source = proposal.assess_proposed_nse_taxonomy_map(_classification(source="OTHER_OFFICIAL"), as_of=T)
    unsupported_version = proposal.assess_proposed_nse_taxonomy_map(_classification(version="v2"), as_of=T)

    assert unsupported_source.reason is proposal.NseTaxonomyMapAuditReason.TAXONOMY_SOURCE_OR_VERSION_UNSUPPORTED
    assert unsupported_version.reason is proposal.NseTaxonomyMapAuditReason.TAXONOMY_SOURCE_OR_VERSION_UNSUPPORTED
    with pytest.raises(proposal.NseTaxonomyCompanyTypeMapError, match="TAXONOMY_IDENTITY_INVALID"):
        proposal.assess_proposed_nse_taxonomy_map(replace(_classification(), source_sha256=None), as_of=T)
    with pytest.raises(proposal.NseTaxonomyCompanyTypeMapError, match="INPUT_INVALID"):
        proposal.assess_proposed_nse_taxonomy_map(_classification(), as_of=T.replace(tzinfo=None))


def test_assessment_fingerprint_is_tamper_evident_and_stably_serialized():
    value = _classification()
    first = proposal.assess_proposed_nse_taxonomy_map(value, as_of=T)
    second = proposal.assess_proposed_nse_taxonomy_map(value, as_of=T.astimezone(UTC))

    assert first == second
    assert proposal.serialize_proposed_nse_taxonomy_map_assessment(first) == proposal.serialize_proposed_nse_taxonomy_map_assessment(second)
    with pytest.raises(proposal.NseTaxonomyCompanyTypeMapError, match="ASSESSMENT_INVALID"):
        replace(first, category=proposal.NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL).verify()


def test_taxonomy_only_contract_has_no_issuer_company_type_or_execution_surface():
    assessment_fields = {item.name for item in fields(proposal.ProposedNseTaxonomyMapAssessment)}
    map_fields = {item.name for item in fields(proposal.ProposedNseTaxonomyCompanyTypeMap)}
    source = Path("app/intelligence/nse_taxonomy_company_type_map_proposal.py").read_text(encoding="utf-8")

    assert not assessment_fields & {"issuer", "cin", "company_type", "portfolio", "order", "broker", "quantity", "price"}
    assert not map_fields & {"issuer", "company_type", "portfolio", "order", "broker"}
    assert "app.intelligence.pit_company_type" not in source
    assert not any(path in source for path in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "sqlite3", "datetime.now", "time.time"))
    assert "raw_classification_label" not in source
    assert ".lower(" not in source and ".casefold(" not in source and ".startswith(" not in source
