from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.models import DataQuality
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.market_technical_artifact import (
    MarketTechnicalArtifactBuilder,
    SharedBrainMarketTechnicalArtifactEvidenceSource,
    SharedBrainMarketTechnicalArtifactStore,
)
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.intelligence.unified_state import IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain
from app.market_data.historical import HistoricalBarConflictArtifact, SQLiteHistoricalBarStore
from app.market_data.models import (
    AdjustmentStatus,
    CanonicalOHLCVBar,
    Exchange,
    InstrumentIdentity,
    InstrumentType,
    MarketDataProvenance,
    ProviderInstrumentMapping,
    Timeframe,
)
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import snapshot_json
from app.universe_analysis.models import NseEquityInstrument


AS_OF = datetime(2026, 8, 31, 15, 30, tzinfo=UTC)
INSTRUMENT_ID = "NSE:INE000A01001"


def _identity() -> InstrumentIdentity:
    return InstrumentIdentity(
        INSTRUMENT_ID, Exchange.NSE, "ALPHA", "ALPHA", "INE000A01001", "EQ",
        InstrumentType.NSE_EQUITY, "Alpha Ltd",
        provider_mappings=(ProviderInstrumentMapping("fixture-provider", "NSE_EQ|INE000A01001", "ALPHA"),),
    )


def _instrument() -> NseEquityInstrument:
    return NseEquityInstrument(
        INSTRUMENT_ID, "ALPHA", "INE000A01001", "Demo", "TEST", "ACTIVE", None,
        True, AS_OF, "FIXTURE", company_name="Alpha Ltd",
    )


def _bar(number: int, *, close: Decimal | None = None) -> CanonicalOHLCVBar:
    end = AS_OF - timedelta(days=300 - number)
    value = close if close is not None else Decimal("100") + Decimal(number)
    return CanonicalOHLCVBar(
        f"fixture:{number}", _identity(), Timeframe.DAILY, end - timedelta(days=1), end,
        value, value + Decimal("2"), value - Decimal("2"), value, 1_000 + number,
        None, None, AdjustmentStatus.UNKNOWN,
        MarketDataProvenance("fixture-provider", "NSE_EQ|INE000A01001", end, end, AS_OF, "fixture-v1"),
        DataQuality.HIGH,
    )


def _history(tmp_path) -> SQLiteHistoricalBarStore:
    history = SQLiteHistoricalBarStore(tmp_path / "history.sqlite")
    for number in range(252):
        history.upsert(_bar(number))
    return history


def _availability(inputs, domain: IntelligenceEvidenceDomain) -> IntelligenceEvidenceAvailability:
    return next(item.availability for item in inputs.unified_state.evidence_references if item.domain is domain)


def test_raw_ohlcv_does_not_upgrade_shared_brain_until_a_valid_artifact_is_persisted(tmp_path) -> None:
    history = _history(tmp_path)
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = SharedBrainMarketTechnicalArtifactStore(repository)
    source = SharedBrainMarketTechnicalArtifactEvidenceSource(store)
    assembler = StoredSharedBrainEvidenceAssembler(
        SQLiteFinancialFactStore(tmp_path / "facts.sqlite"), history, market_technical_artifacts=source,
    )

    raw_only = assembler.assemble(_instrument(), as_of=AS_OF)
    assert _availability(raw_only, IntelligenceEvidenceDomain.MARKET_DATA) is IntelligenceEvidenceAvailability.UNAVAILABLE
    assert _availability(raw_only, IntelligenceEvidenceDomain.TECHNICAL) is IntelligenceEvidenceAvailability.UNAVAILABLE

    artifact = store.save(MarketTechnicalArtifactBuilder(historical=history).build(
        canonical_instrument_id=INSTRUMENT_ID, intelligence_as_of=AS_OF,
    ))
    assert artifact.market_data_availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert artifact.technical_availability is IntelligenceEvidenceAvailability.AVAILABLE
    assert artifact.benchmark_instrument_id is None
    assert all("provider" not in name for name in artifact.__dataclass_fields__)
    assert all("score" not in name and "gate" not in name and "action" not in name for name in artifact.__dataclass_fields__)
    persisted_snapshot = repository.get_snapshot(artifact.artifact_id)
    assert persisted_snapshot is not None
    assert "token" not in snapshot_json(persisted_snapshot).lower()

    persisted = assembler.assemble(_instrument(), as_of=AS_OF)
    assert _availability(persisted, IntelligenceEvidenceDomain.MARKET_DATA) is IntelligenceEvidenceAvailability.AVAILABLE
    assert _availability(persisted, IntelligenceEvidenceDomain.TECHNICAL) is IntelligenceEvidenceAvailability.AVAILABLE


def test_artifact_is_idempotent_reopens_and_is_invisible_before_its_cutoff(tmp_path) -> None:
    history = _history(tmp_path)
    path = tmp_path / "core.sqlite"
    repository = SQLiteCoreApiSnapshotRepository(path)
    store = SharedBrainMarketTechnicalArtifactStore(repository)
    artifact = MarketTechnicalArtifactBuilder(historical=history).build(
        canonical_instrument_id=INSTRUMENT_ID, intelligence_as_of=AS_OF,
    )

    assert store.save(artifact) == artifact
    assert store.save(artifact) == artifact
    assert store.list(canonical_instrument_id=INSTRUMENT_ID, as_of=AS_OF - timedelta(microseconds=1)) == ()
    repository.close()

    reopened = SharedBrainMarketTechnicalArtifactStore(SQLiteCoreApiSnapshotRepository(path))
    assert reopened.list(canonical_instrument_id=INSTRUMENT_ID, as_of=AS_OF) == (artifact,)


def test_conflicted_history_fails_closed_and_persisted_tampering_is_rejected(tmp_path) -> None:
    history = _history(tmp_path)
    stored = _bar(251)
    incoming = replace(stored, bar_id="fixture:conflict", close=stored.close + Decimal("1"))
    history.save_conflict_artifact(HistoricalBarConflictArtifact.from_bars(stored, incoming, detected_at=AS_OF))
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "core.sqlite")
    store = SharedBrainMarketTechnicalArtifactStore(repository)

    conflict = store.save(MarketTechnicalArtifactBuilder(historical=history).build(
        canonical_instrument_id=INSTRUMENT_ID, intelligence_as_of=AS_OF,
    ))
    assert conflict.market_data_availability is IntelligenceEvidenceAvailability.CONFLICTED
    assert conflict.technical_availability is IntelligenceEvidenceAvailability.UNAVAILABLE

    payload = json.loads(repository._connection.execute(
        "SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=?", (conflict.artifact_id,),
    ).fetchone()["payload_json"])
    payload["payload"]["fields"]["fingerprint"] = "sha256:tampered"
    repository._connection.execute(
        "UPDATE core_api_snapshots SET payload_json=? WHERE snapshot_id=?",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")), conflict.artifact_id),
    )
    repository._connection.commit()

    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        store.list(canonical_instrument_id=INSTRUMENT_ID, as_of=AS_OF)
