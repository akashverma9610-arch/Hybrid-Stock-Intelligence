from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.taxonomy.security_sector_index_mapping_coverage import (
    CURRENT_SECURITY_SECTOR_INDEX_MAPPING_POLICY,
    CanonicalSectorIndexHistoryState,
    MappingApplicability,
    SecuritySectorIndexCoverageError,
    SecuritySectorIndexCoverageInput,
    SecuritySectorIndexCoverageReason,
    SecuritySectorIndexMappingState,
    StrictHistoricalPitMappingState,
    audit_current_security_sector_index_coverage,
    serialize_security_sector_index_coverage_audit,
)
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 7, 12, tzinfo=UTC)


def _instrument(instrument_id: str = "NSE:INE000A01001", **changes: object) -> NseEquityInstrument:
    values: dict[str, object] = {
        "instrument_id": instrument_id,
        "symbol": "ALPHA",
        "isin": "INE000A01001",
        "sector": None,
        "industry": None,
        "listing_status": "ACTIVE",
        "listing_date": None,
        "tradable": True,
        "data_as_of": T - timedelta(days=1),
        "source": "NSE_OFFICIAL",
        "main_board": True,
    }
    values.update(changes)
    return NseEquityInstrument(**values)  # type: ignore[arg-type]


def _classification(
    instrument: NseEquityInstrument, *, sector: str = "Information Technology", **changes: object,
) -> InstrumentTaxonomyClassification:
    values: dict[str, object] = {
        "classification_id": "taxonomy:" + instrument.instrument_id,
        "instrument_id": instrument.instrument_id,
        "industry": "Information Technology Services",
        "sector": sector,
        "super_sector": "Information Technology",
        "source": "NSE_INDICES_OFFICIAL",
        "source_type": ClassificationSourceStatus.OFFICIAL,
        "effective_from": T - timedelta(days=3),
        "effective_to": None,
        "as_of": T - timedelta(days=2),
        "confidence": 1.0,
        "classification_version": "nse-indices-taxonomy-v1",
        "source_reference": "source=official;sha256=fixture",
        "source_sha256": "fixture",
        "effective_observation_semantics": "FIRST_OBSERVED_OFFICIAL_SNAPSHOT",
    }
    values.update(changes)
    return InstrumentTaxonomyClassification(**values)  # type: ignore[arg-type]


def _mapping(
    *, sector: str = "Information Technology", status: SectorIndexMappingStatus = SectorIndexMappingStatus.EXACT_OFFICIAL,
    name: str | None = "Nifty IT", at: datetime = T - timedelta(days=1), mapping_id: str = "mapping:it",
) -> NseSectorIndexMapping:
    return NseSectorIndexMapping(
        mapping_id, sector, name,
        None if name is None else "https://www.niftyindices.com/indices/equity/sectoral-indices/nifty-it",
        status, ("OFFICIAL_INDEX_NAME=Nifty IT", "OFFICIAL_DESCRIPTION=IT segment"), "source-sha", at,
    )


def _audit(
    *, inputs: tuple[SecuritySectorIndexCoverageInput, ...] | None = None,
    mappings: tuple[NseSectorIndexMapping, ...] = (_mapping(),),
    counts: dict[str, int] | None = None,
):
    instrument = _instrument()
    values = inputs or (SecuritySectorIndexCoverageInput(instrument, _classification(instrument), True),)
    return audit_current_security_sector_index_coverage(
        audit_as_of=T,
        inputs=values,
        mappings=mappings,
        canonical_index_ohlc_session_counts=(
            {"NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY": 247} if counts is None else counts
        ),
    )


def test_exact_governed_mapping_is_current_descriptive_and_deterministically_serialized() -> None:
    alpha = _instrument()
    beta = _instrument("NSE:INE000A01002", symbol="BETA", isin="INE000A01002")
    values = (
        SecuritySectorIndexCoverageInput(alpha, _classification(alpha), True),
        SecuritySectorIndexCoverageInput(beta, _classification(beta), True),
    )
    first = _audit(inputs=values)
    second = _audit(inputs=tuple(reversed(values)))

    record = first.records[0]
    assert record.mapping_state is SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING
    assert record.index_history_state is CanonicalSectorIndexHistoryState.READY
    assert record.reason_code is SecuritySectorIndexCoverageReason.MAPPED_WITH_CANONICAL_INDEX_HISTORY
    assert record.canonical_index_id == "NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY"
    assert record.applicability is MappingApplicability.CURRENT_DESCRIPTIVE
    assert record.strict_historical_pit_state is StrictHistoricalPitMappingState.NOT_READY
    assert first.fingerprint == second.fingerprint
    assert serialize_security_sector_index_coverage_audit(first) == serialize_security_sector_index_coverage_audit(second)
    assert first.mapped_count(technical_scope_only=True) == first.canonical_history_ready_count(technical_scope_only=True) == 2


@pytest.mark.parametrize(
    ("status", "name", "expected_state", "reason"),
    (
        (SectorIndexMappingStatus.NO_OFFICIAL_SECTOR_INDEX, None, SecuritySectorIndexMappingState.NO_OFFICIAL_INDEX, SecuritySectorIndexCoverageReason.OFFICIAL_SECTOR_INDEX_UNAVAILABLE),
        (SectorIndexMappingStatus.AMBIGUOUS, "Candidate Nifty IT", SecuritySectorIndexMappingState.AMBIGUOUS, SecuritySectorIndexCoverageReason.INDEX_IDENTITY_AMBIGUOUS),
        (SectorIndexMappingStatus.UNRESOLVED, None, SecuritySectorIndexMappingState.NOT_GOVERNED, SecuritySectorIndexCoverageReason.MAPPING_POLICY_NOT_GOVERNED),
    ),
)
def test_non_exact_mapping_states_fail_closed(
    status: SectorIndexMappingStatus,
    name: str | None,
    expected_state: SecuritySectorIndexMappingState,
    reason: SecuritySectorIndexCoverageReason,
) -> None:
    value = _audit(mappings=(_mapping(status=status, name=name),), counts={})
    record = value.records[0]
    assert record.mapping_state is expected_state
    assert record.reason_code is reason
    assert record.canonical_index_id is None
    assert record.canonical_ohlc_session_count == 0
    if status is SectorIndexMappingStatus.AMBIGUOUS:
        assert record.official_index_name == "Candidate Nifty IT"


def test_taxonomy_and_current_scope_boundaries_are_fail_closed() -> None:
    instrument = _instrument()
    missing = _audit(inputs=(SecuritySectorIndexCoverageInput(instrument, None, True),))
    assert missing.records[0].reason_code is SecuritySectorIndexCoverageReason.SECURITY_SECTOR_CLASSIFICATION_MISSING

    stale = _audit(inputs=(SecuritySectorIndexCoverageInput(
        instrument, _classification(instrument, effective_to=T - timedelta(seconds=1)), True,
    ),))
    assert stale.records[0].reason_code is SecuritySectorIndexCoverageReason.TAXONOMY_STALE_OR_INCOMPLETE

    outside = _audit(inputs=(SecuritySectorIndexCoverageInput(instrument, _classification(instrument), False),))
    assert outside.records[0].mapping_state is SecuritySectorIndexMappingState.NOT_APPLICABLE
    assert outside.records[0].reason_code is SecuritySectorIndexCoverageReason.TECHNICAL_INPUT_OUT_OF_SCOPE


def test_future_or_conflicting_mapping_records_are_never_selected_by_order() -> None:
    future = _mapping(at=T + timedelta(seconds=1))
    future_only = _audit(mappings=(future,))
    assert future_only.records[0].reason_code is SecuritySectorIndexCoverageReason.SECTOR_INDEX_MAPPING_MISSING

    conflict = _mapping(name="Nifty Other", mapping_id="mapping:other")
    ambiguous = _audit(mappings=(_mapping(), conflict))
    assert ambiguous.records[0].mapping_state is SecuritySectorIndexMappingState.AMBIGUOUS
    assert ambiguous.records[0].reason_code is SecuritySectorIndexCoverageReason.MAPPING_POLICY_NOT_GOVERNED

    duplicate_provenance = _mapping(mapping_id="mapping:duplicate")
    ambiguous_duplicate = _audit(mappings=(_mapping(), duplicate_provenance))
    assert ambiguous_duplicate.records[0].mapping_state is SecuritySectorIndexMappingState.AMBIGUOUS


def test_missing_history_does_not_claim_rule_readiness_and_tampering_is_rejected() -> None:
    audit = _audit(counts={})
    record = audit.records[0]
    assert record.mapping_state is SecuritySectorIndexMappingState.EXACT_GOVERNED_MAPPING
    assert record.index_history_state is CanonicalSectorIndexHistoryState.NOT_READY
    assert record.reason_code is SecuritySectorIndexCoverageReason.CANONICAL_INDEX_OHLC_LINEAGE_ABSENT
    with pytest.raises(SecuritySectorIndexCoverageError, match="RECORD_INVALID"):
        replace(record, reason_code=SecuritySectorIndexCoverageReason.MAPPED_WITH_CANONICAL_INDEX_HISTORY)
    with pytest.raises(SecuritySectorIndexCoverageError, match="AUDIT_INVALID"):
        replace(audit, policy_fingerprint="sha256:" + "0" * 64)


def test_duplicate_security_and_invalid_session_counts_are_rejected() -> None:
    input_value = SecuritySectorIndexCoverageInput(_instrument(), _classification(_instrument()), True)
    with pytest.raises(SecuritySectorIndexCoverageError, match="DUPLICATE_SECURITY"):
        _audit(inputs=(input_value, input_value))
    with pytest.raises(SecuritySectorIndexCoverageError, match="HISTORY_COUNTS_INVALID"):
        _audit(counts={"NSE_SECTOR_INDEX:INFORMATION_TECHNOLOGY": -1})


def test_policy_refuses_broad_proxy_synthetic_and_fuzzy_mapping() -> None:
    with pytest.raises(SecuritySectorIndexCoverageError, match="POLICY_INVALID"):
        replace(CURRENT_SECURITY_SECTOR_INDEX_MAPPING_POLICY, broad_proxy_permitted=True)
    assert CURRENT_SECURITY_SECTOR_INDEX_MAPPING_POLICY.index_return_family == "PRICE_RETURN_INDEX"


def test_static_boundaries_have_no_storage_provider_or_technical_rule_dependency() -> None:
    source = (Path(__file__).parents[2] / "app" / "taxonomy" / "security_sector_index_mapping_coverage.py").read_text(encoding="utf-8")
    imports = "\n".join(line for line in source.splitlines() if line.startswith(("from ", "import ")))
    forbidden = ("sqlite", "requests", "broker", "portfolio", "app.storage", "app.signals", "rule_2", "rule_3", "save(", "insert(", "update(")
    assert not any(value in imports or value in source for value in forbidden)
    assert "datetime.now" not in source and "date.today" not in source
