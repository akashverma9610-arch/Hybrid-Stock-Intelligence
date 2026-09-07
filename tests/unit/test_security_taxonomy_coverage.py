from __future__ import annotations

import ast
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.nse_indices import NseIndicesConstituent, NseIndustryHierarchyEntry
from app.taxonomy.security_taxonomy_coverage import (
    ExistingTaxonomyRegressionState,
    SecurityTaxonomyCoverageError,
    SecurityTaxonomyCoverageInput,
    SecurityTaxonomyCoverageReason,
    SecurityTaxonomyCoverageState,
    audit_current_nse_indices_taxonomy_coverage,
    serialize_security_taxonomy_coverage_audit,
)
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 8, 27, 15, 33, tzinfo=UTC)


def _instrument(symbol: str = "ALPHA", isin: str = "INE000A01001", *, at: datetime = T) -> NseEquityInstrument:
    return NseEquityInstrument("NSE:" + isin, symbol, isin, None, None, "ACTIVE", None, True, at, "NSE")


def _row(
    symbol: str = "ALPHA", isin: str = "INE000A01001", label: str = "Healthcare", *,
    source: str = "NIFTY_TOTAL_MARKET_CONSTITUENTS", line: int = 2,
) -> NseIndicesConstituent:
    return NseIndicesConstituent("Alpha Ltd", label, symbol, "EQ", isin, source, "a" * 64, line)


def _hierarchy() -> tuple[NseIndustryHierarchyEntry, ...]:
    return (
        NseIndustryHierarchyEntry("IN01", "Health", "IN0101", "Healthcare", "IN010101", "Hospitals", "IN010101001", "Hospitals"),
        NseIndustryHierarchyEntry("IN07", "Industrials", "IN0702", "Capital Goods", "IN070201", "Electrical", "IN070201001", "Electrical Equipment"),
    )


def _classification(instrument: NseEquityInstrument, *, sector: str = "Healthcare") -> InstrumentTaxonomyClassification:
    macro = "Health" if sector == "Healthcare" else "Industrials"
    return InstrumentTaxonomyClassification(
        "taxonomy:" + instrument.instrument_id, instrument.instrument_id, None, sector, macro,
        "NSE_INDICES_OFFICIAL", ClassificationSourceStatus.OFFICIAL, T, None, T, None,
        "nse-indices-taxonomy-v1", "source=NIFTY_TOTAL_MARKET_CONSTITUENTS;sha256=" + "a" * 64 + ";line=2;mapping=EXACT_ISIN_AND_SYMBOL", raw_classification_label=sector,
        resolution_status="EXACT_UNIQUE", source_sha256="a" * 64,
        effective_observation_semantics="FIRST_OBSERVED_OFFICIAL_SNAPSHOT",
    )


def _audit(
    *,
    inputs: tuple[SecurityTaxonomyCoverageInput, ...] | None = None,
    rows: tuple[NseIndicesConstituent, ...] | None = None,
    at: datetime = T,
):
    alpha = _instrument()
    return audit_current_nse_indices_taxonomy_coverage(
        audit_as_of=at,
        inputs=inputs or (SecurityTaxonomyCoverageInput(alpha, _classification(alpha), True),),
        source_rows=rows or (_row(),), hierarchy=_hierarchy(),
    )


def test_exact_current_source_identity_retains_sector_only_and_existing_711_regression_shape():
    audit = _audit()
    record = audit.records[0]
    assert audit.source_label_level == "SECTOR"
    assert audit.hierarchy_counts() == (("macro_sector", 1), ("sector", 1), ("industry", 0), ("basic_industry", 0))
    assert record.coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_READY
    assert record.reason_code is SecurityTaxonomyCoverageReason.EXACT_CURRENT_CLASSIFICATION
    assert record.regression_state is ExistingTaxonomyRegressionState.EXACT_SAME
    assert (record.source_isin, record.source_symbol, record.source_series, record.industry, record.basic_industry) == (
        "INE000A01001", "ALPHA", "EQ", None, None,
    )


def test_absent_canonical_security_is_source_universe_limited_and_not_a_taxonomy_guess():
    alpha, beta = _instrument(), _instrument("BETA", "INE000B01002")
    audit = _audit(inputs=(
        SecurityTaxonomyCoverageInput(alpha, _classification(alpha), True),
        SecurityTaxonomyCoverageInput(beta, None, True),
    ))
    record = next(value for value in audit.records if value.symbol == "BETA")
    assert record.coverage_state is SecurityTaxonomyCoverageState.SOURCE_UNIVERSE_LIMITATION
    assert record.reason_code is SecurityTaxonomyCoverageReason.SOURCE_UNIVERSE_LIMITATION
    assert record.sector is None and record.source_symbol is None


def test_exact_new_source_evidence_is_a_promotion_candidate_but_is_not_persisted_by_audit():
    alpha = _instrument()
    audit = _audit(inputs=(SecurityTaxonomyCoverageInput(alpha, None, True),))
    record = audit.records[0]
    assert record.coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_READY
    assert record.reason_code is SecurityTaxonomyCoverageReason.TAXONOMY_PROMOTION_AVAILABLE
    assert record.regression_state is ExistingTaxonomyRegressionState.NOT_PREVIOUSLY_CLASSIFIED


def test_unresolved_current_source_label_is_an_exact_hierarchy_gap_not_a_fuzzy_classification():
    alpha = _instrument()
    audit = _audit(inputs=(SecurityTaxonomyCoverageInput(alpha, None, True),), rows=(
        _row(label="Telecommunication"),
        _row("UNMATCHED", "INE999A01001", "Healthcare", source="NIFTY_500_CONSTITUENTS"),
    ))
    record = audit.records[0]
    assert record.coverage_state is SecurityTaxonomyCoverageState.OTHER_EXACT_REASON
    assert record.reason_code is SecurityTaxonomyCoverageReason.NSE_INDICES_HIERARCHY_LABEL_UNRESOLVED
    assert record.macro_sector is record.sector is None


def test_equivalent_scope_sources_with_conflicting_classification_fail_closed():
    alpha = _instrument()
    audit = _audit(rows=(
        _row(label="Healthcare", source="NIFTY_500_CONSTITUENTS"),
        _row(label="Capital Goods", source="NIFTY_TOTAL_MARKET_CONSTITUENTS"),
    ))
    record = audit.records[0]
    assert record.coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED
    assert record.reason_code is SecurityTaxonomyCoverageReason.OFFICIAL_SOURCE_TAXONOMY_CONFLICT
    assert record.regression_state is ExistingTaxonomyRegressionState.CONFLICT


def test_duplicate_official_identity_and_isin_symbol_conflict_both_fail_closed():
    alpha = _instrument()
    duplicate = _audit(rows=(_row(line=2), _row(line=3)))
    assert duplicate.records[0].coverage_state is SecurityTaxonomyCoverageState.IDENTITY_AMBIGUOUS
    conflicting_symbol = _audit(rows=(_row(symbol="BETA"),))
    assert conflicting_symbol.records[0].coverage_state is SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED
    assert conflicting_symbol.records[0].reason_code is SecurityTaxonomyCoverageReason.ISIN_SYMBOL_CONFLICT
    stale_isin = _audit(rows=(_row(isin="INE000A01099"),))
    assert stale_isin.records[0].coverage_state is SecurityTaxonomyCoverageState.IDENTITY_UNRESOLVED
    assert stale_isin.records[0].source_isin == "INE000A01099"


def test_existing_taxonomy_mismatch_is_not_repaired_from_source():
    alpha = _instrument()
    audit = _audit(inputs=(SecurityTaxonomyCoverageInput(alpha, _classification(alpha, sector="Capital Goods"), True),))
    assert audit.records[0].coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED
    assert audit.records[0].reason_code is SecurityTaxonomyCoverageReason.EXISTING_TAXONOMY_CONFLICT


def test_tampered_existing_source_lineage_is_not_repaired_from_source():
    alpha = _instrument()
    classification = _classification(alpha)
    object.__setattr__(classification, "source_sha256", "b" * 64)
    audit = _audit(inputs=(SecurityTaxonomyCoverageInput(alpha, classification, True),))
    assert audit.records[0].coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED
    assert audit.records[0].regression_state is ExistingTaxonomyRegressionState.CONFLICT


def test_future_canonical_identity_and_future_existing_taxonomy_fail_closed():
    future = _instrument(at=T + timedelta(seconds=1))
    future_audit = _audit(inputs=(SecurityTaxonomyCoverageInput(future, None, True),))
    assert future_audit.records[0].reason_code is SecurityTaxonomyCoverageReason.CANONICAL_IDENTITY_AFTER_AUDIT_AS_OF
    alpha = _instrument()
    stale = _classification(alpha)
    object.__setattr__(stale, "effective_from", T + timedelta(seconds=1))
    conflict = _audit(inputs=(SecurityTaxonomyCoverageInput(alpha, stale, True),))
    assert conflict.records[0].coverage_state is SecurityTaxonomyCoverageState.TAXONOMY_EVIDENCE_CONFLICTED


def test_audit_is_order_independent_stably_serialized_and_exposes_unmatched_source_records():
    alpha, beta = _instrument(), _instrument("BETA", "INE000B01002")
    inputs = (
        SecurityTaxonomyCoverageInput(alpha, _classification(alpha), True),
        SecurityTaxonomyCoverageInput(beta, None, False),
    )
    rows = (_row(), _row("UNMATCHED", "INE999A01001", source="NIFTY_500_CONSTITUENTS"))
    left = _audit(inputs=inputs, rows=rows)
    right = _audit(inputs=tuple(reversed(inputs)), rows=tuple(reversed(rows)))
    assert (left.fingerprint, serialize_security_taxonomy_coverage_audit(left)) == (
        right.fingerprint, serialize_security_taxonomy_coverage_audit(right),
    )
    assert len(left.unmatched_source_records) == 1
    assert left.coverage_counts(technical_scope_only=True) == (("TAXONOMY_READY", 1),)


def test_invalid_inputs_and_tampered_fingerprint_are_rejected():
    alpha = _instrument()
    with pytest.raises(SecurityTaxonomyCoverageError, match="AUDIT_AS_OF_REQUIRED"):
        audit_current_nse_indices_taxonomy_coverage(
            audit_as_of=T.replace(tzinfo=None), inputs=(SecurityTaxonomyCoverageInput(alpha, None, True),),
            source_rows=(_row(),), hierarchy=_hierarchy(),
        )
    record = _audit().records[0]
    object.__setattr__(record, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(SecurityTaxonomyCoverageError, match="RECORD_INVALID"):
        record.__post_init__()


def test_contract_has_no_taxonomy_persistence_or_forbidden_operational_dependencies():
    source = Path(__file__).parents[2] / "app" / "taxonomy" / "security_taxonomy_coverage.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = ("sqlite", "requests", "app.signals", "broker", "portfolio", "order")
    assert not any(token in name.lower() for token in forbidden for name in imported)
