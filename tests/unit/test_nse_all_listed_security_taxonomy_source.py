from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.taxonomy.nse_all_listed_security_taxonomy_source import (
    NSE_EQUITY_ALL_SECURITIES_SOURCE,
    NSE_EQUITY_QUOTE_SOURCE,
    NseAllListedTaxonomyDecision,
    NseTaxonomyAcquisitionMode,
    NseTaxonomyAuthority,
    NseTaxonomySampleConclusion,
    NseTaxonomySampleReceipt,
    NseTaxonomySampleStatus,
    NseTaxonomySourceAvailability,
    NseTaxonomySourceCandidate,
    NseTaxonomySourceError,
    NseTaxonomySourceVersionState,
    NseTaxonomyUniverseCompleteness,
    assess_nse_all_listed_taxonomy_source,
    create_conservative_nse_taxonomy_acquisition_policy,
    serialize_nse_all_listed_taxonomy_source_assessment,
)
from app.taxonomy.nse_indices import NseIndustryHierarchyEntry
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 7, 15, 30, tzinfo=UTC)
FP = "sha256:" + "a" * 64


def _instrument(symbol: str = "APARINDS", isin: str = "INE372A01015") -> NseEquityInstrument:
    return NseEquityInstrument("NSE:" + isin, symbol, isin, None, None, "ACTIVE", None, True, T, "NSE")


def _hierarchy() -> tuple[NseIndustryHierarchyEntry, ...]:
    return (
        NseIndustryHierarchyEntry(
            "IN07", "Industrials", "IN0702", "Capital Goods", "IN070201", "Electrical Equipment",
            "IN070201001", "Other Electrical Equipment",
        ),
    )


def _quote_candidate(*, availability: NseTaxonomySourceAvailability = NseTaxonomySourceAvailability.VERIFIED) -> NseTaxonomySourceCandidate:
    return NseTaxonomySourceCandidate(
        NSE_EQUITY_QUOTE_SOURCE, NseTaxonomyAuthority.FIRST_PARTY_NSE,
        NseTaxonomyAcquisitionMode.PER_SECURITY, NseTaxonomyUniverseCompleteness.SAMPLE_ONLY,
        availability, ("isin", "listing_status", "symbol", "trading_status"), ("basic_industry",),
        NseTaxonomySourceVersionState.CURRENT_SOURCE_VERSION_UNAVAILABLE, None,
        "https://www.nseindia.com/get-quote/equity/<symbol>/<slug>",
    )


def _all_equities_candidate() -> NseTaxonomySourceCandidate:
    return NseTaxonomySourceCandidate(
        NSE_EQUITY_ALL_SECURITIES_SOURCE, NseTaxonomyAuthority.FIRST_PARTY_NSE,
        NseTaxonomyAcquisitionMode.BULK, NseTaxonomyUniverseCompleteness.IDENTITY_ONLY,
        NseTaxonomySourceAvailability.VERIFIED, ("isin", "listing_status", "series", "symbol"), (),
        NseTaxonomySourceVersionState.CURRENT_SOURCE_VERSION_UNAVAILABLE, None,
        "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv",
    )


def _receipt(
    *, instrument: NseEquityInstrument | None = None, status: NseTaxonomySampleStatus = NseTaxonomySampleStatus.RECEIPT_ACCEPTED,
    observed_at: datetime = T, symbol: str | None = "APARINDS", isin: str | None = "INE372A01015",
    basic: str | None = "Other Electrical Equipment",
) -> NseTaxonomySampleReceipt:
    no_response = status in {
        NseTaxonomySampleStatus.ACCESS_BLOCKED,
        NseTaxonomySampleStatus.RATE_LIMITED,
        NseTaxonomySampleStatus.SCHEMA_DRIFT,
    }
    return NseTaxonomySampleReceipt(
        NSE_EQUITY_QUOTE_SOURCE, instrument or _instrument(), status, observed_at,
        None if no_response else symbol, None if no_response else isin, None if no_response else "EQ",
        None if no_response else "Listed", None if no_response else "Active", None if no_response else basic,
        None if no_response else FP,
    )


def _assessment(*, candidates=None, receipts=None, hierarchy=None, at=T):
    return assess_nse_all_listed_taxonomy_source(
        audit_as_of=at, candidates=candidates if candidates is not None else (_quote_candidate(), _all_equities_candidate()),
        sample_receipts=receipts if receipts is not None else (_receipt(),), hierarchy=hierarchy if hierarchy is not None else _hierarchy(),
    )


def test_exact_quote_basic_industry_and_hierarchy_yield_all_four_current_descriptive_levels():
    value = _assessment()
    sample = value.sample_assessments[0]
    assert value.decision is NseAllListedTaxonomyDecision.PER_SECURITY_FIRST_PARTY_TAXONOMY_SOURCE_READY
    assert sample.conclusion is NseTaxonomySampleConclusion.EXACT_FOUR_LEVEL_ASSIGNMENT
    assert (sample.macro_economic_sector, sample.sector, sample.industry, sample.basic_industry) == (
        "Industrials", "Capital Goods", "Electrical Equipment", "Other Electrical Equipment",
    )
    assert value.applicability.value == "CURRENT_DESCRIPTIVE_SECURITY_TAXONOMY"
    assert value.strict_historical_pit_state.value == "NOT_READY"


def test_bulk_requires_complete_exact_four_level_assignment_schema_not_identity_inventory_alone():
    identity_only = _assessment(candidates=(_all_equities_candidate(),), receipts=())
    assert identity_only.decision is NseAllListedTaxonomyDecision.FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL
    bulk = NseTaxonomySourceCandidate(
        "NSE_FULL_TAXONOMY", NseTaxonomyAuthority.FIRST_PARTY_NSE, NseTaxonomyAcquisitionMode.BULK,
        NseTaxonomyUniverseCompleteness.ALL_LISTED, NseTaxonomySourceAvailability.VERIFIED,
        ("isin", "symbol"), ("basic_industry", "industry", "macro_economic_sector", "sector"),
        NseTaxonomySourceVersionState.SOURCE_VERSION_AVAILABLE, "2026-09-07", "fixture",
    )
    assert _assessment(candidates=(bulk,), receipts=()).decision is NseAllListedTaxonomyDecision.ALL_LISTED_TAXONOMY_BULK_SOURCE_READY


@pytest.mark.parametrize(
    ("status", "conclusion"),
    (
        (NseTaxonomySampleStatus.ACCESS_BLOCKED, NseTaxonomySampleConclusion.SOURCE_ACCESS_BLOCKED),
        (NseTaxonomySampleStatus.RATE_LIMITED, NseTaxonomySampleConclusion.SOURCE_RATE_LIMITED),
        (NseTaxonomySampleStatus.SCHEMA_DRIFT, NseTaxonomySampleConclusion.SOURCE_SCHEMA_DRIFT),
    ),
)
def test_access_rate_and_schema_failures_are_not_reclassified_as_missing_taxonomy(status, conclusion):
    value = _assessment(candidates=(_quote_candidate(availability={
        NseTaxonomySampleStatus.ACCESS_BLOCKED: NseTaxonomySourceAvailability.ACCESS_BLOCKED,
        NseTaxonomySampleStatus.RATE_LIMITED: NseTaxonomySourceAvailability.RATE_LIMITED,
        NseTaxonomySampleStatus.SCHEMA_DRIFT: NseTaxonomySourceAvailability.SCHEMA_UNVERIFIED,
    }[status]),), receipts=(_receipt(status=status),))
    assert value.decision is NseAllListedTaxonomyDecision.FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL
    assert value.sample_assessments[0].conclusion is conclusion
    assert value.sample_assessments[0].basic_industry is None


def test_identity_conflict_is_fail_closed_and_symbol_never_repairs_an_isin():
    value = _assessment(receipts=(_receipt(isin="INE419M01035", basic=None),))
    assert value.decision is NseAllListedTaxonomyDecision.FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL
    assert value.sample_assessments[0].conclusion is NseTaxonomySampleConclusion.IDENTITY_UNRESOLVED


def test_missing_basic_industry_and_unknown_hierarchy_are_distinct_fail_closed_results():
    incomplete = _assessment(receipts=(_receipt(status=NseTaxonomySampleStatus.SUCCESS_INCOMPLETE, basic=None),))
    assert incomplete.sample_assessments[0].conclusion is NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE
    unresolved = _assessment(receipts=(_receipt(basic="No Exact Official Label"),))
    assert unresolved.sample_assessments[0].conclusion is NseTaxonomySampleConclusion.HIERARCHY_UNRESOLVED


def test_future_receipt_is_excluded_at_the_audit_as_of_boundary():
    value = _assessment(receipts=(_receipt(observed_at=T + timedelta(seconds=1)),))
    assert value.sample_assessments[0].conclusion is NseTaxonomySampleConclusion.SOURCE_RESPONSE_INCOMPLETE
    assert value.decision is NseAllListedTaxonomyDecision.FIRST_PARTY_TAXONOMY_SOURCE_PARTIAL
    future_access = _assessment(
        candidates=(_quote_candidate(availability=NseTaxonomySourceAvailability.ACCESS_BLOCKED),),
        receipts=(_receipt(status=NseTaxonomySampleStatus.ACCESS_BLOCKED, observed_at=T + timedelta(seconds=1)),),
    )
    assert future_access.sample_assessments[0].conclusion is NseTaxonomySampleConclusion.SOURCE_ACCESS_BLOCKED


def test_assessment_and_serialization_are_order_independent_and_tamper_evident():
    alpha, beta = _instrument(), _instrument("GLAND", "INE068V01023")
    receipts = (_receipt(instrument=alpha), _receipt(instrument=beta, symbol="GLAND", isin="INE068V01023"))
    left = _assessment(receipts=receipts)
    right = _assessment(candidates=tuple(reversed((_quote_candidate(), _all_equities_candidate()))), receipts=tuple(reversed(receipts)))
    assert (left.fingerprint, serialize_nse_all_listed_taxonomy_source_assessment(left)) == (
        right.fingerprint, serialize_nse_all_listed_taxonomy_source_assessment(right),
    )
    object.__setattr__(left.sample_assessments[0], "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(NseTaxonomySourceError, match="SAMPLE_ASSESSMENT_INVALID"):
        left.sample_assessments[0].__post_init__()
    object.__setattr__(left.sample_assessments[0], "candidate_id", "UNKNOWN")
    with pytest.raises(NseTaxonomySourceError, match="SOURCE_ASSESSMENT_INVALID"):
        left.__post_init__()


def test_policy_is_single_worker_checkpointed_cached_and_stops_on_access_or_rate_limit():
    policy = create_conservative_nse_taxonomy_acquisition_policy()
    assert policy.max_concurrent_requests == 1
    assert policy.minimum_interval_seconds == 2
    assert policy.retain_raw_first_party_receipt and policy.cache_successful_response
    assert policy.checkpoint_each_document and policy.stop_on_access_or_rate_limit
    assert set(policy.statuses) == set(NseTaxonomySampleStatus)


def test_invalid_candidate_and_unknown_sample_source_fail_closed():
    with pytest.raises(NseTaxonomySourceError, match="SOURCE_CANDIDATE_INVALID"):
        NseTaxonomySourceCandidate(
            "bad", NseTaxonomyAuthority.FIRST_PARTY_NSE, NseTaxonomyAcquisitionMode.BULK,
            NseTaxonomyUniverseCompleteness.ALL_LISTED, NseTaxonomySourceAvailability.VERIFIED,
            ("symbol", "isin"), (), NseTaxonomySourceVersionState.CURRENT_SOURCE_VERSION_UNAVAILABLE, None, "fixture",
        )
    receipt = _receipt()
    object.__setattr__(receipt, "candidate_id", "UNKNOWN")
    with pytest.raises(NseTaxonomySourceError, match="SAMPLE_SOURCE_UNKNOWN"):
        _assessment(receipts=(receipt,))


def test_contract_has_no_network_persistence_clock_or_forbidden_operational_dependencies():
    source = Path(__file__).parents[2] / "app" / "taxonomy" / "nse_all_listed_security_taxonomy_source.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("requests", "urllib", "http", "sqlite", "repository", "broker", "portfolio", "order", "api", "signal")
    assert not any(token in name.lower() for token in forbidden for name in imports)
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"now", "utcnow"}
        for node in ast.walk(tree)
    )
