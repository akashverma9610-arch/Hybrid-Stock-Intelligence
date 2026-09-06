from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from app.market_data.official_nse_index_ohlc_feasibility import OfficialIndexReturnFamily
from app.market_data.official_nse_index_ohlc_reconciliation import (
    CONSUMER_DURABLES_TARGET,
    HEALTHCARE_TARGET,
    OfficialIndexCloseLineagePoint,
    OfficialIndexIdentityReconciliationStatus,
    OfficialNseIndexIdentityEvidence,
    OfficialNseIndexSourceNameTarget,
    reconcile_official_nse_index_source_name,
    serialize_official_nse_index_source_name_reconciliation,
)


SESSIONS = (date(2026, 9, 3), date(2026, 9, 4))


def _evidence(target=CONSUMER_DURABLES_TARGET, **changes: object) -> OfficialNseIndexIdentityEvidence:
    values: dict[str, object] = {
        "canonical_index_id": target.canonical_index_id,
        "catalogue_name": target.catalogue_name,
        "dedicated_page_name": target.dedicated_page_name,
        "factsheet_name": target.factsheet_name,
        "historical_parameter": target.historical_parameter,
        "historical_observed_name": target.historical_parameter,
        "return_family": OfficialIndexReturnFamily.PRICE_RETURN_INDEX,
        "evidence_references": ("NSE_INDICES_CATALOGUE", "NSE_INDICES_FACTSHEET", "NSE_INDICES_HISTORICAL_REPORT"),
    }
    values.update(changes)
    return OfficialNseIndexIdentityEvidence(**values)  # type: ignore[arg-type]


def _points(*values: str) -> tuple[OfficialIndexCloseLineagePoint, ...]:
    return tuple(OfficialIndexCloseLineagePoint(session, Decimal(value)) for session, value in zip(SESSIONS, values, strict=True))


def _reconcile(*, target=CONSUMER_DURABLES_TARGET, evidence: OfficialNseIndexIdentityEvidence | None = None, canonical=None, alternate=None):
    return reconcile_official_nse_index_source_name(
        target=target,
        evidence=evidence or _evidence(target),
        canonical_close_points=_points("100.00", "101.00") if canonical is None else canonical,
        alternate_close_points=_points("100", "101.0") if alternate is None else alternate,
    )


def test_legitimate_consumer_durables_source_parameter_alias_requires_exact_close_lineage() -> None:
    result = _reconcile()
    assert result.status is OfficialIndexIdentityReconciliationStatus.SOURCE_PARAMETER_ALIAS_CONFIRMED
    assert result.reason_codes == ("EXACT_FIRST_PARTY_IDENTITY_AND_CLOSE_LINEAGE_VERIFIED",)
    assert result.overlap_start == SESSIONS[0] and result.overlap_end == SESSIONS[-1]
    assert result.exact_close_match_count == 2 and result.conflict_count == 0
    assert result.maximum_absolute_difference == result.maximum_relative_difference == Decimal("0")


def test_exact_same_name_identity_is_reconciled_without_alias_semantics() -> None:
    target = OfficialNseIndexSourceNameTarget(
        canonical_index_id="NSE_SECTOR_INDEX:TEST",
        canonical_mapping_name="Nifty Test",
        catalogue_name="Nifty Test",
        dedicated_page_name="Nifty Test",
        factsheet_name="Nifty Test",
        historical_parameter="Nifty Test",
        distinct_product_names=(),
        affected_security_count=1,
    )
    assert _reconcile(target=target).status is OfficialIndexIdentityReconciliationStatus.IDENTITY_RECONCILED


def test_healthcare_and_nifty500_healthcare_are_distinct_official_products() -> None:
    evidence = _evidence(HEALTHCARE_TARGET, catalogue_name="Nifty500 Healthcare")
    result = _reconcile(target=HEALTHCARE_TARGET, evidence=evidence)
    assert result.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_NOT_RECONCILED
    assert result.reason_codes == ("DISTINCT_OFFICIAL_INDEX_PRODUCT",)


def test_price_return_and_total_return_are_never_mixed() -> None:
    result = _reconcile(evidence=_evidence(return_family=OfficialIndexReturnFamily.TOTAL_RETURN_INDEX))
    assert result.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_NOT_RECONCILED
    assert result.reason_codes == ("PRI_TRI_MISMATCH",)


def test_close_difference_rejects_alias_without_tolerance() -> None:
    result = _reconcile(alternate=_points("100.01", "101"))
    assert result.status is OfficialIndexIdentityReconciliationStatus.SOURCE_PARAMETER_ALIAS_REJECTED
    assert result.reason_codes == ("CLOSE_LINEAGE_VALUE_MISMATCH",)
    assert result.conflict_count == 1
    assert result.maximum_absolute_difference == Decimal("0.01")
    assert result.maximum_relative_difference == Decimal("0.0001")


def test_absent_or_incomplete_overlap_is_ambiguous_not_a_synthetic_match() -> None:
    absent = _reconcile(canonical=())
    partial = _reconcile(alternate=(_points("100", "101")[0],))
    assert absent.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS
    assert absent.reason_codes == ("CANONICAL_CLOSE_LINEAGE_ABSENT",)
    assert partial.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS
    assert partial.reason_codes == ("CLOSE_LINEAGE_INSUFFICIENT_OVERLAP",)
    assert partial.canonical_missing_from_alternate_count == 1


def test_duplicate_session_and_incomplete_identity_fail_closed() -> None:
    duplicate = _reconcile(canonical=(*_points("100", "101"), OfficialIndexCloseLineagePoint(SESSIONS[0], Decimal("100"))))
    incomplete = _reconcile(evidence=_evidence(catalogue_name="Nifty Consumer Durables Other"))
    assert duplicate.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_AMBIGUOUS
    assert duplicate.reason_codes == ("CLOSE_LINEAGE_DUPLICATE_SESSION",)
    assert incomplete.status is OfficialIndexIdentityReconciliationStatus.IDENTITY_NOT_RECONCILED
    assert incomplete.reason_codes == ("OFFICIAL_IDENTITY_EVIDENCE_INCOMPLETE",)


def test_reconciliation_is_deterministic_and_fingerprint_includes_lineage() -> None:
    first = _reconcile()
    reordered = _reconcile(canonical=tuple(reversed(_points("100", "101"))), alternate=tuple(reversed(_points("100", "101"))))
    changed_lineage = _reconcile(evidence=replace(_evidence(), evidence_references=("NSE_INDICES_CATALOGUE", "NSE_INDICES_FACTSHEET", "NSE_INDICES_HISTORICAL_REPORT_V2")))
    assert first == reordered
    assert serialize_official_nse_index_source_name_reconciliation(first) == serialize_official_nse_index_source_name_reconciliation(reordered)
    assert first.reconciliation_fingerprint != changed_lineage.reconciliation_fingerprint


def test_evidence_references_must_be_nonempty_sorted_and_unique() -> None:
    with pytest.raises(ValueError, match="EVIDENCE_INVALID"):
        _evidence(evidence_references=("NSE_INDICES_CATALOGUE", "NSE_INDICES_CATALOGUE"))
    with pytest.raises(ValueError, match="EVIDENCE_INVALID"):
        _evidence(evidence_references=("",))


def test_close_lineage_requires_date_only_session_and_typed_points() -> None:
    with pytest.raises(ValueError, match="CLOSE_POINT_INVALID"):
        OfficialIndexCloseLineagePoint(datetime(2026, 9, 3, tzinfo=timezone.utc), Decimal("100"))
    with pytest.raises(ValueError, match="CLOSE_POINT_INVALID"):
        _reconcile(canonical=(object(),))


def test_contract_has_no_network_persistence_rule_or_activation_dependencies() -> None:
    source = (Path(__file__).parents[2] / "app" / "market_data" / "official_nse_index_ohlc_reconciliation.py").read_text(encoding="utf-8")
    imports = "\n".join(line.lower() for line in source.splitlines() if line.startswith(("from ", "import ")))
    forbidden = ("sqlite", "requests", "broker", "portfolio", "app.storage", "app.signals", "readiness", "rule_2", "rule_3")
    assert not any(value in imports for value in forbidden)
    assert "datetime.now" not in source and "date.today" not in source
    assert "save(" not in source and "insert(" not in source and "update(" not in source
