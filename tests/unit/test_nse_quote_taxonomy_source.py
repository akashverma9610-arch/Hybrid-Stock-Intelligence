from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.taxonomy.nse_indices import NseIndustryHierarchyEntry
from app.taxonomy.nse_quote_taxonomy_source import (
    NSE_QUOTE_PAGE_IDENTITY,
    NSE_QUOTE_RESOURCE_IDENTITY,
    NseQuoteTaxonomyPrimaryResult,
    NseQuoteTaxonomyReconciliationStatus,
    NseQuoteTaxonomyRetrievalStatus,
    NseQuoteTaxonomySampleConclusion,
    NseQuoteTaxonomySchemaState,
    NseQuoteTaxonomySourceError,
    NseQuoteTaxonomySourceVersionState,
    NseQuoteTaxonomyObservation,
    assess_nse_quote_taxonomy_source,
    reconcile_quote_taxonomy_sample,
    serialize_nse_quote_taxonomy_source_assessment,
)
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 7, 15, 30, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _instrument(symbol: str = "APARINDS", isin: str = "INE372A01015") -> NseEquityInstrument:
    return NseEquityInstrument("NSE:" + isin, symbol, isin, None, None, "ACTIVE", None, True, T, "NSE")


def _hierarchy(*, duplicate: bool = False) -> tuple[NseIndustryHierarchyEntry, ...]:
    first = NseIndustryHierarchyEntry(
        "IN07", "Industrials", "IN0702", "Capital Goods", "IN070201", "Electrical Equipment",
        "IN070201001", "Other Electrical Equipment",
    )
    if not duplicate:
        return (first,)
    return (first, NseIndustryHierarchyEntry(
        "IN08", "Services", "IN0802", "Other Services", "IN080201", "Other Industry",
        "IN080201001", "Other Electrical Equipment",
    ))


def _observation(
    *, observation_id: str = "APAR_RENDERED", instrument: NseEquityInstrument | None = None,
    status: NseQuoteTaxonomyRetrievalStatus = NseQuoteTaxonomyRetrievalStatus.RENDERED_PUBLIC_FIELDS_OBSERVED,
    source_identity: str = NSE_QUOTE_PAGE_IDENTITY, at: datetime = T, isin: str | None = "INE372A01015",
    symbol: str | None = "APARINDS", basic: str | None = "Other Electrical Equipment", basic_code: str | None = None,
) -> NseQuoteTaxonomyObservation:
    stable = status in {
        NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        NseQuoteTaxonomyRetrievalStatus.HTML_PARSER_RECEIPT_ACCEPTED,
    }
    shell = status is NseQuoteTaxonomyRetrievalStatus.STATIC_HTML_SHELL_RECEIPT
    unavailable = status in {
        NseQuoteTaxonomyRetrievalStatus.MACHINE_RESOURCE_ACCESS_BLOCKED,
        NseQuoteTaxonomyRetrievalStatus.SOURCE_UNAVAILABLE,
        NseQuoteTaxonomyRetrievalStatus.SOURCE_NOT_SUITABLE,
    }
    return NseQuoteTaxonomyObservation(
        observation_id, source_identity, instrument or _instrument(), status, at,
        "https://www.nseindia.com/get-quote/equity/APARINDS/Apar-Industries-Limited",
        FP if stable or shell else None,
        None if shell or unavailable else symbol, None if shell or unavailable else isin,
        () if shell or unavailable else ("EQ",), None if shell or unavailable else "Listed",
        None if shell or unavailable else "Active", None if shell or unavailable else basic,
        None if shell or unavailable else basic_code, None, None, None, None,
        NseQuoteTaxonomySourceVersionState.SOURCE_CLASSIFICATION_VERSION_UNAVAILABLE,
    )


def _assessment(*, observations=None, hierarchy=None, at=T):
    return assess_nse_quote_taxonomy_source(
        audit_as_of=at, observations=observations if observations is not None else (_observation(),),
        hierarchy=hierarchy if hierarchy is not None else _hierarchy(),
    )


def test_rendered_public_fields_are_current_descriptive_evidence_but_not_a_promotable_machine_source():
    value = _assessment()
    sample = value.sample_assessments[0]
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL
    assert value.schema_state is NseQuoteTaxonomySchemaState.SOURCE_MACHINE_SCHEMA_NOT_READY
    assert sample.conclusion is NseQuoteTaxonomySampleConclusion.RENDERED_FIELDS_OBSERVED_NOT_PROMOTABLE
    assert (sample.macro_economic_sector, sample.sector, sample.industry, sample.basic_industry) == (
        "Industrials", "Capital Goods", "Electrical Equipment", "Other Electrical Equipment",
    )
    assert value.applicability.value == "CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY"
    assert value.strict_historical_pit_state.value == "NOT_READY"
    assert value.acquisition_policy.max_concurrent_requests == 1
    assert value.acquisition_policy.minimum_interval_seconds >= 2
    assert value.acquisition_policy.stop_on_access_or_rate_limit


def test_machine_payload_proves_schema_and_exact_sample_without_promoting_or_persisting_anything():
    value = _assessment(observations=(_observation(
        observation_id="APAR_MACHINE", status=NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        source_identity=NSE_QUOTE_RESOURCE_IDENTITY,
    ),))
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_READY
    assert value.schema_state is NseQuoteTaxonomySchemaState.MACHINE_SCHEMA_PROVEN
    assert value.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN


def test_stable_html_parser_is_distinct_from_machine_schema_and_can_only_yield_html_only_readiness():
    value = _assessment(observations=(_observation(
        observation_id="APAR_HTML", status=NseQuoteTaxonomyRetrievalStatus.HTML_PARSER_RECEIPT_ACCEPTED,
    ),))
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_READY_HTML_ONLY
    assert value.schema_state is NseQuoteTaxonomySchemaState.SOURCE_MACHINE_SCHEMA_NOT_READY


def test_access_blocked_is_not_reclassified_as_missing_or_unsuitable_source():
    value = _assessment(observations=(_observation(
        observation_id="APAR_BLOCKED", source_identity=NSE_QUOTE_RESOURCE_IDENTITY,
        status=NseQuoteTaxonomyRetrievalStatus.MACHINE_RESOURCE_ACCESS_BLOCKED,
    ),))
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_ACCESS_BLOCKED
    assert value.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.SOURCE_UNAVAILABLE


def test_static_html_shell_and_machine_403_preserve_partial_result_and_do_not_force_a_brittle_parser():
    value = _assessment(observations=(
        _observation(observation_id="APAR_SHELL", status=NseQuoteTaxonomyRetrievalStatus.STATIC_HTML_SHELL_RECEIPT),
        _observation(observation_id="APAR_BLOCKED", source_identity=NSE_QUOTE_RESOURCE_IDENTITY,
                     status=NseQuoteTaxonomyRetrievalStatus.MACHINE_RESOURCE_ACCESS_BLOCKED),
    ))
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL
    assert value.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.SOURCE_UNAVAILABLE


def test_exact_isin_is_required_and_td_power_symbol_cannot_repair_a_conflicting_isin():
    td = _instrument("TDPOWERSYS", "INE419M01027")
    value = _assessment(observations=(_observation(
        observation_id="TD_RENDERED", instrument=td, symbol="TDPOWERSYS", isin="INE419M01035", basic="Heavy Electrical Equipment",
    ),))
    assert value.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.IDENTITY_MISMATCH
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL


def test_exact_basic_code_is_preferred_and_code_label_disagreement_fails_closed():
    exact = _assessment(observations=(_observation(
        observation_id="APAR_MACHINE", status=NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        basic_code="IN070201001",
    ),))
    assert exact.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.SAMPLE_TAXONOMY_PROVEN
    conflict = _assessment(observations=(_observation(
        observation_id="APAR_MACHINE", status=NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        basic_code="WRONG",
    ),))
    assert conflict.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.HIERARCHY_IDENTITY_AMBIGUOUS


def test_global_label_ambiguity_rejects_label_only_hierarchy_promotion():
    value = _assessment(hierarchy=_hierarchy(duplicate=True))
    assert value.hierarchy_audit.total_basic_industries == 2
    assert value.hierarchy_audit.unique_basic_industry_labels == 1
    assert value.hierarchy_audit.duplicate_basic_industry_labels == ("OTHER ELECTRICAL EQUIPMENT",)
    assert value.sample_assessments[0].conclusion is NseQuoteTaxonomySampleConclusion.HIERARCHY_IDENTITY_AMBIGUOUS


def test_future_observation_is_excluded_at_audit_boundary_and_never_makes_source_ready():
    past = _observation(observation_id="APAR_RENDERED")
    future = _observation(
        observation_id="APAR_MACHINE", status=NseQuoteTaxonomyRetrievalStatus.MACHINE_PAYLOAD_RECEIPT_ACCEPTED,
        at=T + timedelta(seconds=1),
    )
    left = _assessment(observations=(past,))
    right = _assessment(observations=(past, future))
    assert (right.observations, right.fingerprint, serialize_nse_quote_taxonomy_source_assessment(right)) == (
        left.observations, left.fingerprint, serialize_nse_quote_taxonomy_source_assessment(left),
    )
    assert right.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_PARTIAL
    assert right.schema_state is NseQuoteTaxonomySchemaState.SOURCE_MACHINE_SCHEMA_NOT_READY
    with pytest.raises(NseQuoteTaxonomySourceError, match="NO_ELIGIBLE_OBSERVATION"):
        _assessment(observations=(future,))


def test_existing_sector_reconciliation_is_descriptive_only_and_requires_exact_parent_compatibility():
    sample = _assessment().sample_assessments[0]
    assert reconcile_quote_taxonomy_sample(sample, existing_macro_economic_sector="Industrials", existing_sector="Capital Goods") is NseQuoteTaxonomyReconciliationStatus.RICHER_HIERARCHY_COMPATIBLE
    assert reconcile_quote_taxonomy_sample(
        sample, existing_macro_economic_sector="Industrials", existing_sector="Capital Goods",
        existing_industry="Electrical Equipment", existing_basic_industry="Other Electrical Equipment",
    ) is NseQuoteTaxonomyReconciliationStatus.EXACT_COMPATIBLE
    assert reconcile_quote_taxonomy_sample(sample, existing_macro_economic_sector="Financial Services", existing_sector="Banks") is NseQuoteTaxonomyReconciliationStatus.CONFLICTED
    mismatch = _assessment(observations=(_observation(observation_id="TD", isin="INE419M01035"),)).sample_assessments[0]
    assert reconcile_quote_taxonomy_sample(mismatch, existing_macro_economic_sector="Industrials", existing_sector="Capital Goods") is NseQuoteTaxonomyReconciliationStatus.IDENTITY_MISMATCH


def test_order_independent_serialization_is_tamper_evident_and_observation_invariants_fail_closed():
    alpha = _observation()
    beta = _observation(observation_id="GLAND_RENDERED", instrument=_instrument("GLAND", "INE068V01023"), symbol="GLAND", isin="INE068V01023", basic="Other Electrical Equipment")
    left = _assessment(observations=(alpha, beta))
    right = _assessment(observations=(beta, alpha))
    assert (left.fingerprint, serialize_nse_quote_taxonomy_source_assessment(left)) == (
        right.fingerprint, serialize_nse_quote_taxonomy_source_assessment(right),
    )
    object.__setattr__(left.sample_assessments[0], "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(NseQuoteTaxonomySourceError, match="SAMPLE_ASSESSMENT_INVALID"):
        left.sample_assessments[0].__post_init__()
    with pytest.raises(NseQuoteTaxonomySourceError, match="SOURCE_ASSESSMENT_INVALID"):
        left.__post_init__()
    clean = _assessment()
    object.__setattr__(clean, "schema_state", "MACHINE_SCHEMA_PROVEN")
    with pytest.raises(NseQuoteTaxonomySourceError, match="SOURCE_ASSESSMENT_INVALID"):
        clean.__post_init__()
    with pytest.raises(NseQuoteTaxonomySourceError, match="OBSERVATION_INVALID"):
        _observation(status=NseQuoteTaxonomyRetrievalStatus.RENDERED_PUBLIC_FIELDS_OBSERVED, basic=None)


def test_explicit_not_suitable_state_is_distinct_from_access_blocked():
    value = _assessment(observations=(_observation(
        observation_id="APAR_UNSUITABLE", status=NseQuoteTaxonomyRetrievalStatus.SOURCE_NOT_SUITABLE,
    ),))
    assert value.primary_result is NseQuoteTaxonomyPrimaryResult.QUOTE_TAXONOMY_SOURCE_NOT_SUITABLE


def test_contract_has_no_network_dom_parser_persistence_clock_or_forbidden_operational_dependencies():
    source = Path(__file__).parents[2] / "app" / "taxonomy" / "nse_quote_taxonomy_source.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("requests", "urllib", "selenium", "playwright", "sqlite", "repository", "broker", "portfolio", "order", "api", "signal")
    assert not any(token in name.lower() for token in forbidden for name in imports)
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"now", "utcnow"}
        for node in ast.walk(tree)
    )
