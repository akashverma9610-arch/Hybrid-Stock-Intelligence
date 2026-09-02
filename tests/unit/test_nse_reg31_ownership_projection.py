from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from app.data_operations.nse_reg31_pit_correction import TARGETS
from app.filings.models import CorporateFiling, FilingTextAvailability, FilingType, PrimarySourceQuality
from app.filings.store import SQLiteCorporateFilingsStore
from app.intelligence.company_evidence import CompanyEvidenceStoredSource
from app.intelligence.unified_state import IntelligenceEvidenceDomain
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.ownership.models import OwnershipCategory
from app.ownership.nse_reg31_projection import (
    NORMALIZATION_RULE_ID, NseReg31OwnershipProjectionService, _observation, _raw_fact,
)
from app.ownership.store import OwnershipObservationStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 1, tzinfo=UTC)


def _xml(*, ratio: str = "0.5542", unit: str = "pure") -> bytes:
    return f'''<?xml version="1.0"?><xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance" xmlns:shp="urn:shp">
      <shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI" unitRef="{unit}">{ratio}</shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
      <shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="PublicShareholding_ContextI" unitRef="pure">0.4458</shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
      <shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="MutualFundsOrUTI_ContextI" unitRef="pure">0.1</shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
      <shp:ShareholdingAsAPercentageOfTotalNumberOfShares contextRef="UnmappedButExplicit_ContextI" unitRef="pure">0.01</shp:ShareholdingAsAPercentageOfTotalNumberOfShares>
      <shp:EncumberedSharesHeldAsPercentageOfTotalNumberOfShares contextRef="ShareholdingOfPromoterAndPromoterGroup_ContextI" unitRef="pure">0.02</shp:EncumberedSharesHeldAsPercentageOfTotalNumberOfShares>
    </xbrli:xbrl>'''.encode()


def _setup(tmp_path: Path, *, ratio: str = "0.5542", unit: str = "pure"):
    filings = SQLiteCorporateFilingsStore(tmp_path / "filings.db")
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "ownership.db")
    targets = []
    source = tmp_path / "sources"; source.mkdir()
    for index, target in enumerate(TARGETS):
        raw = _xml(ratio=ratio, unit=unit)
        digest = sha256(raw).hexdigest()
        target = replace(target, raw_sha256=digest)
        targets.append(target)
        (source / target.artifact_filename).write_bytes(raw)
        period = datetime.fromisoformat(target.reporting_period_end).replace(tzinfo=UTC)
        published = T - timedelta(days=20 - index)
        instrument = InstrumentIdentity(target.canonical_instrument_id, Exchange.NSE, f"S{index}", f"S{index}", target.canonical_instrument_id.removeprefix("NSE:"), None, InstrumentType.NSE_EQUITY, f"Fixture {index}")
        filing = CorporateFiling(
            "nse:NSE:reg31-xbrl-pit-v1:test-" + str(index), instrument, Exchange.NSE, "NSE",
            PrimarySourceQuality.PRIMARY_EXCHANGE, FilingType.SHAREHOLDING_PATTERN,
            "REGULATION_31_SHAREHOLDING_PATTERN", "fixture", published, published,
            "https://nsearchives.nseindia.com/corporate/xbrl/SHP_fixture.xml",
            "https://nsearchives.nseindia.com/corporate/xbrl/SHP_fixture.xml",
            MarketDataProvenance("NSE", None, published, published, published, "fixture", "fixture", "fixture"),
            period_end=period, text_availability=FilingTextAvailability.SOURCE_TEXT,
            revision_of_filing_id=target.filing_id,
            warnings=("NSE_REG31_ARTIFACT_SHA256:" + digest, "NSE_REG31_PIT_TIMESTAMP_CORRECTED_V1:fixture"),
        )
        filings.save(filing)
    store = OwnershipObservationStore(repository)
    service = NseReg31OwnershipProjectionService(
        filings=filings, observations=store, source_directory=source, targets=tuple(targets), clock=lambda: T,
    )
    return filings, repository, store, service


def test_official_reg31_projection_preserves_raw_facts_maps_only_deterministic_categories_and_is_idempotent(tmp_path: Path):
    _filings, repository, store, service = _setup(tmp_path)
    first = service.materialize()
    assert len(first) == 5
    assert all(item.raw_fact_inserted == 5 and item.observation_inserted == 4 for item in first)
    assert all("ShareholdingAsAPercentageOfTotalNumberOfShares@UnmappedButExplicit_ContextI" in item.unsupported_concepts for item in first)
    values = store.list_by_instrument(TARGETS[0].canonical_instrument_id, as_of=T)
    promoter = next(item for item in values if item.category is OwnershipCategory.PROMOTER_AND_PROMOTER_GROUP)
    assert str(promoter.raw_value) == "0.5542"
    assert str(promoter.normalized_value) == "55.4200"
    assert promoter.normalization_rule_id == NORMALIZATION_RULE_ID
    assert promoter.normalized_unit.value == "PERCENTAGE_POINTS"
    assert promoter.category_relationship.value == "TOTAL"
    assert all(item.category_relationship.value != "DERIVED_TOTAL" for item in values)
    assert store.latest_comparable(TARGETS[0].canonical_instrument_id, OwnershipCategory.PUBLIC, as_of=T).status == "NON_COMPARABLE"
    second = service.materialize()
    assert all(item.raw_fact_inserted == item.observation_inserted == 0 for item in second)
    assert all(item.raw_fact_identical == 5 and item.observation_identical == 4 and item.conflict_count == 0 for item in second)
    repository.close()
    reopened = OwnershipObservationStore(SQLiteCoreApiSnapshotRepository(tmp_path / "ownership.db"))
    assert len(reopened.list_raw_facts(instrument_id=TARGETS[0].canonical_instrument_id)) == 5
    assert len(reopened.list_by_instrument(TARGETS[0].canonical_instrument_id)) == 4


def test_unit_lineage_never_uses_magnitude_and_pit_requires_corrected_effective_filing(tmp_path: Path):
    _filings, repository, store, service = _setup(tmp_path, ratio="55", unit="pure")
    service.materialize()
    promoter = next(item for item in store.list_by_instrument(TARGETS[0].canonical_instrument_id) if item.category is OwnershipCategory.PROMOTER_AND_PROMOTER_GROUP)
    assert str(promoter.normalized_value) == "5500"
    assert not store.list_by_instrument(TARGETS[0].canonical_instrument_id, as_of=promoter.published_at - timedelta(microseconds=1))
    assert store.list_by_instrument(TARGETS[0].canonical_instrument_id, as_of=promoter.published_at)
    repository.close()


def test_non_pure_unit_is_preserved_but_not_normalized_and_legacy_filing_is_rejected(tmp_path: Path):
    _filings, repository, store, service = _setup(tmp_path, unit="shares")
    first = service.materialize()
    assert all(item.observation_inserted == 3 and item.raw_fact_inserted == 5 for item in first)
    raw = store.list_raw_facts(instrument_id=TARGETS[0].canonical_instrument_id)
    assert any(item.raw_unit == "shares" for item in raw)
    assert all(item.category is not OwnershipCategory.PROMOTER_AND_PROMOTER_GROUP for item in store.list_by_instrument(TARGETS[0].canonical_instrument_id))
    repository.close()


def test_materialized_observations_replace_only_the_lineage_blocker_in_shared_brain_source(tmp_path: Path):
    filings, repository, store, service = _setup(tmp_path)
    service.materialize()
    source = CompanyEvidenceStoredSource(filings=filings, ownership_observations=store)
    artifacts = source.list_stored_intelligence_artifacts(TARGETS[0].canonical_instrument_id, as_of=T)
    ownership = [item for item in artifacts if item.domain is IntelligenceEvidenceDomain.OWNERSHIP]
    assert ownership
    assert all("SHAREHOLDING_FACTS_NOT_MATERIALIZED" not in item.warnings for item in ownership)
    assert any("OWNERSHIP_COMPARABLE_PRIOR_PERIOD_UNAVAILABLE" in item.warnings for item in ownership)
    repository.close()


def test_conflicting_same_period_observation_fails_closed_and_exact_current_isins_are_the_only_targets(tmp_path: Path):
    _filings, repository, store, service = _setup(tmp_path)
    service.materialize()
    existing = next(item for item in store.list_by_instrument(TARGETS[0].canonical_instrument_id) if item.category is OwnershipCategory.PUBLIC)
    raw = _raw_fact(
        canonical_instrument_id=existing.canonical_instrument_id, filing_id="different-official-filing",
        artifact_sha256="a" * 64, reporting_period=existing.reporting_period,
        published_at=existing.published_at, received_at=existing.received_at,
        raw_concept=existing.raw_concept, raw_value=existing.raw_value + 1, raw_unit=existing.raw_unit,
        scope=existing.scope, source_context_reference=existing.source_context_reference,
        source_reference="https://nsearchives.nseindia.com/corporate/xbrl/SHP_other.xml",
    )
    with pytest.raises(ValueError, match="OWNERSHIP_OBSERVATION_CONFLICT"):
        store.save_observation(_observation(raw, existing.category, existing.category_relationship))
    assert TARGETS[1].canonical_instrument_id == "NSE:INE0FHS01024"
    assert TARGETS[4].canonical_instrument_id == "NSE:INE090A01021"
    repository.close()
