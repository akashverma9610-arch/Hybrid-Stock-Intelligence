from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.audit_official_company_level_ebitda_ebit_sources import (
    NSE_ALLOWED_HOSTS,
    OfficialSourceProbeError,
    SourceDocument,
    _official_nse_url,
    aggregate_metric,
    formula_semantics,
    parse_official_xbrl,
)


T = datetime(2026, 9, 12, tzinfo=UTC)


def document() -> SourceDocument:
    return SourceDocument(
        source_family="NSE_INTEGRATED_FILING_FINANCIAL",
        authority="PRIMARY_EXCHANGE",
        role="LATEST_RELEVANT_FINANCIAL_RESULT",
        url="https://nsearchives.nseindia.com/corporate/xbrl/example.xml",
        publication_at=T,
        reporting_period="30-JUN-2026",
        scope="Consolidated",
        expected_isin="INE000A01001",
        received_at=T,
    )


def xml(body: str) -> bytes:
    return ("""<?xml version=\"1.0\"?>
    <xbrl xmlns:x=\"urn:test\">
      <x:ISIN>INE000A01001</x:ISIN>
      <context id=\"company\"><entity><identifier>issuer</identifier></entity></context>
      <context id=\"segment\"><entity><segment>one</segment></entity></context>
    """ + body + "</xbrl>").encode()


def test_company_level_direct_ebitda_is_structured_and_does_not_expose_value():
    parsed = parse_official_xbrl(document(), xml("<x:EBITDA contextRef=\"company\">123.45</x:EBITDA>"))
    result = aggregate_metric("EBITDA", (parsed,), ())

    assert parsed["identity"] == "EXACT"
    assert result["classification"] == "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA"
    assert result["direct_company_level_value"] is True
    assert result["machine_readability"] == ("STRUCTURED_NUMERIC_FIELD",)
    assert "123.45" not in repr(result)


def test_segment_ebit_never_becomes_company_level_ebit():
    parsed = parse_official_xbrl(document(), xml("<x:EarningsBeforeInterestAndTax contextRef=\"segment\">123</x:EarningsBeforeInterestAndTax>"))

    assert aggregate_metric("EBIT", (parsed,), ())["classification"] == "SEGMENT_EBIT_ONLY"


def test_ebitda_margin_and_adjusted_ebitda_remain_ineligible_even_with_camel_case_tags():
    parsed = parse_official_xbrl(
        document(),
        xml(
            "<x:EBITDAMargin contextRef=\"company\">17.0</x:EBITDAMargin>"
            "<x:AdjustedEBITDA contextRef=\"company\">123</x:AdjustedEBITDA>"
        ),
    )

    result = aggregate_metric("EBITDA", (parsed,), ())

    assert result["classification"] == "EBITDA_MARGIN_ONLY"
    assert result["all_observed_classifications"] == ("ADJUSTED_EBITDA_ONLY", "EBITDA_MARGIN_ONLY")
    assert result["direct_company_level_value"] is False


def test_direct_ebit_remains_a_direct_value_when_a_formula_also_exists():
    parsed = parse_official_xbrl(
        document(),
        xml(
            "<x:EarningsBeforeInterestAndTax contextRef=\"company\">123</x:EarningsBeforeInterestAndTax>"
            "<x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef=\"company\">EBIT is defined before tax.</x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>"
        ),
    )

    result = aggregate_metric("EBIT", (parsed,), ())

    assert result["classification"] == "COMPANY_LEVEL_DIRECT_EBIT_VALUE"
    assert result["direct_company_level_value"] is True


def test_formula_fingerprint_is_semantic_and_stable_across_whitespace():
    first = formula_semantics(
        "EBITDA is derived from profit before exceptional item and tax, less other income and adding back finance costs, depreciation and amortisation expense.",
        "EBITDA",
    )
    second = formula_semantics(
        " EBITDA   is derived from profit before exceptional item and tax, less other income and adding back finance costs, depreciation and amortisation expense. ",
        "EBITDA",
    )

    assert first == second
    assert first is not None
    assert first["other_income"] == "SUBTRACTED"
    assert first["finance_costs"] == "ADDED_BACK"
    assert first["depreciation_amortisation"] == "ADDED_BACK"


def test_declared_formula_without_value_is_preserved_as_formula_only():
    parsed = parse_official_xbrl(
        document(),
        xml("<x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef=\"company\">EBITDA is derived from profit before exceptional items and tax, less other income and adding back finance costs, depreciation and amortisation.</x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>"),
    )

    result = aggregate_metric("EBITDA", (parsed,), ())

    assert result["classification"] == "COMPANY_LEVEL_DISCLOSED_FORMULA_ONLY"
    assert result["direct_company_level_value"] is False
    assert len(result["formula_fingerprints"]) == 1


def test_formula_from_a_different_document_cannot_promote_a_direct_value():
    direct = parse_official_xbrl(document(), xml("<x:EBITDA contextRef=\"company\">123.45</x:EBITDA>"))
    other_document = replace(document(), url="https://nsearchives.nseindia.com/corporate/xbrl/other.xml")
    formula = parse_official_xbrl(
        other_document,
        xml("<x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef=\"company\">EBITDA is derived from profit before exceptional items and tax, less other income and adding back finance costs, depreciation and amortisation.</x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>"),
    )

    assert aggregate_metric("EBITDA", (direct, formula), ())["classification"] == "COMPANY_LEVEL_DIRECT_DISCLOSED_VALUE_NO_FORMULA"


def test_ratio_prose_is_ambiguous_and_not_an_ebit_formula_or_value():
    parsed = parse_official_xbrl(document(), xml("<x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock contextRef=\"company\">Interest coverage ratio uses Earnings before Interest and Tax divided by interest expense.</x:DisclosureOfNotesOnFinancialResultsExplanatoryTextBlock>"))
    result = aggregate_metric("EBIT", (parsed,), ())

    assert result["classification"] == "AMBIGUOUS"
    assert result["direct_company_level_value"] is False
    assert result["formula_fingerprints"] == ()


def test_operating_profit_is_not_relabelled_as_ebitda():
    parsed = parse_official_xbrl(document(), xml("<x:OperatingProfitBeforeProvisionAndContingencies contextRef=\"company\">99</x:OperatingProfitBeforeProvisionAndContingencies>"))

    assert aggregate_metric("EBITDA", (parsed,), ())["classification"] == "OPERATING_PROFIT_ONLY"


def test_identity_mismatch_is_visible_to_the_caller_for_fail_closed_exclusion():
    parsed = parse_official_xbrl(document(), xml("<x:ISIN>INE999A01009</x:ISIN><x:EBITDA contextRef=\"company\">12</x:EBITDA>"))

    assert parsed["identity"] == "MISMATCH_OR_AMBIGUOUS"


@pytest.mark.parametrize(
    "url, expected",
    (
        ("https://www.nseindia.com/api/integrated-filing-results", True),
        ("https://nsearchives.nseindia.com/corporate/xbrl/a.xml", True),
        ("http://nsearchives.nseindia.com/corporate/xbrl/a.xml", False),
        ("https://example.invalid/a.xml", False),
        ("https://user:secret@nsearchives.nseindia.com/a.xml", False),
    ),
)
def test_only_allowlisted_https_nse_sources_are_admitted(url: str, expected: bool):
    assert _official_nse_url(url) is expected
    assert "nsearchives.nseindia.com" in NSE_ALLOWED_HOSTS


def test_audit_module_has_no_runtime_clock_or_production_write_dependencies():
    source = Path("scripts/audit_official_company_level_ebitda_ebit_sources.py").read_text(encoding="utf-8")

    for forbidden in ("datetime.now", "FinancialFactStore", "CorporateFilingsStore", "INSERT INTO", "UPDATE ", "DELETE FROM", "broker", "order"):
        assert forbidden not in source
