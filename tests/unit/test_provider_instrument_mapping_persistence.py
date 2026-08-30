from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import ProviderInstrumentMappingRecord, ProviderMappingStatus
from app.universe_analysis.service import CoreUniverseAnalysisStore
from app.market_data.kotak_neo import KotakNeoInstrumentRecord, _identity
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType


T = datetime(2026, 8, 24, 10, tzinfo=UTC)


def mapping(*, mapping_id: str = "kotak-ansalapi-v1", reference: str = "fixture-token-001",
            effective_as_of: datetime = T, provider: str = "KOTAK_NEO") -> ProviderInstrumentMappingRecord:
    return ProviderInstrumentMappingRecord(
        mapping_id=mapping_id,
        canonical_instrument_id="NSE:ANSALAPI-EQ",
        provider=provider,
        provider_exchange_segment="nse_cm",
        provider_instrument_reference=reference,
        provider_symbol="ANSALAPI-EQ",
        isin="INE436A01026",
        status=ProviderMappingStatus.ACTIVE,
        effective_as_of=effective_as_of,
        source_reference="kotak-nse-cm-master",
        source_checksum="fixture-master-checksum",
        mapping_version="kotak-neo-v1",
    )


def test_provider_mapping_persists_and_reopens_with_exact_internal_token(tmp_path) -> None:
    path = tmp_path / "persistent.sqlite"
    expected = mapping()
    first = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(path))
    first.save_provider_mapping(expected)
    assert first.provider_mapping(canonical_instrument_id=expected.canonical_instrument_id, provider="kotak_neo") == expected

    reopened = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(path))
    assert reopened.provider_mapping(canonical_instrument_id=expected.canonical_instrument_id, provider="KOTAK_NEO") == expected


def test_provider_mapping_is_append_only_and_keeps_version_history(tmp_path) -> None:
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "mappings.sqlite"))
    old = mapping()
    store.save_provider_mapping(old)
    with pytest.raises(ValueError, match="immutable"):
        store.save_provider_mapping(old)

    newer = mapping(mapping_id="kotak-ansalapi-v2", reference="fixture-token-002", effective_as_of=T + timedelta(days=1))
    store.save_provider_mapping(newer)
    assert store.provider_mapping(canonical_instrument_id=old.canonical_instrument_id, provider="KOTAK_NEO", as_of=T) == old
    assert store.provider_mapping(canonical_instrument_id=old.canonical_instrument_id, provider="KOTAK_NEO", as_of=T + timedelta(days=1)) == newer

    retired = ProviderInstrumentMappingRecord(
        mapping_id="kotak-ansalapi-retired", canonical_instrument_id=old.canonical_instrument_id,
        provider="KOTAK_NEO", provider_exchange_segment="nse_cm", provider_instrument_reference="retired-token",
        provider_symbol="ANSALAPI-EQ", isin=old.isin, status=ProviderMappingStatus.RETIRED,
        effective_as_of=T + timedelta(days=2), mapping_version="kotak-neo-v1",
    )
    store.save_provider_mapping(retired)
    assert store.provider_mapping(canonical_instrument_id=old.canonical_instrument_id, provider="KOTAK_NEO", as_of=T + timedelta(days=2)) is None


def test_provider_mappings_are_provider_isolated_and_have_no_public_route(tmp_path) -> None:
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(tmp_path / "mappings.sqlite"))
    kotak = mapping()
    other = mapping(mapping_id="gdfl-ansalapi-v1", provider="GLOBAL_DATAFEEDS", reference="ANSALAPI")
    store.save_provider_mapping(kotak)
    store.save_provider_mapping(other)
    assert store.provider_mapping(canonical_instrument_id=kotak.canonical_instrument_id, provider="KOTAK_NEO") == kotak
    assert store.provider_mapping(canonical_instrument_id=kotak.canonical_instrument_id, provider="GLOBAL_DATAFEEDS") == other

    from app.api.main import create_app
    assert not any("provider-mapping" in getattr(route, "path", "") for route in create_app().routes)


def test_capture_and_restart_rehydrate_an_existing_kotak_identity_without_provider_io(tmp_path) -> None:
    path = tmp_path / "mappings.sqlite"
    resolved = _identity(KotakNeoInstrumentRecord(
        "nse_cm", "fixture-ansalapi-token", "ANSALAPI", "ANSALAPI-EQ", "EQUITY", "INE436A01026", "EQ", "Ansal Properties",
    ))
    canonical = InstrumentIdentity(
        "NSE:INE436A01026", Exchange.NSE, "ANSALAPI", "ANSALAPI", "INE436A01026", "EQ",
        InstrumentType.NSE_EQUITY, "Ansal Properties",
    )
    store = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(path))
    captured = store.capture_provider_mapping(
        canonical, resolved_instrument=resolved, provider="KOTAK_NEO", effective_as_of=T,
        source_reference="kotak-nse-cm-master", source_checksum="fixture-master-checksum",
    )
    assert captured.canonical_instrument_id == canonical.instrument_id
    assert captured.provider_instrument_reference == "fixture-ansalapi-token"

    restarted = CoreUniverseAnalysisStore(SQLiteCoreApiSnapshotRepository(path))
    hydrated = restarted.instrument_with_provider_mapping(canonical, provider="kotak_neo", as_of=T)
    assert hydrated is not None
    assert hydrated.provider_mappings == resolved.provider_mappings
