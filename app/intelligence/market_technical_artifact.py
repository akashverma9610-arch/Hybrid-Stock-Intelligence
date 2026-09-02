"""Durable, PIT-safe market/technical evidence for Shared Brain.

This boundary derives no interpretation.  It records only canonical OHLCV
readiness and outputs from existing deterministic technical calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Protocol

from app.analysis.models import AnalysisStatus, IndicatorResult
from app.analysis.technical import TECHNICAL_CALCULATION_VERSION, TechnicalAnalysisEngine
from app.domain.models import AsOfSnapshot, FreshnessStatus, StrategyVersionReference, ValidationResult, ValidationStatus
from app.historical.guard import manifest_fingerprint
from app.intelligence.unified_state import (
    IntelligenceEvidenceAvailability, IntelligenceEvidenceDomain, IntelligenceInvalidationDomain,
)
from app.intelligence.unified_state_builder import StoredIntelligenceArtifact
from app.market_data.bridge import price_bar_observation
from app.market_data.models import Timeframe
from app.market_data.ohlcv_readiness import OhlcvInstrumentReadiness, OhlcvReadinessService, OhlcvReadinessStatus
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


ARTIFACT_ID = "shared-brain-market-technical-artifact"
ARTIFACT_VERSION = "v1"
TECHNICAL_REFERENCE = StrategyVersionReference(ARTIFACT_ID, ARTIFACT_VERSION)
_TECHNICAL_CALCULATIONS = ("RSI14", "ATR14", "SMA20", "SMA50", "BOLLINGER_BAND_WIDTH", "BOLLINGER_BAND_WIDTH_PERCENTILE")


@dataclass(frozen=True, slots=True)
class MarketTechnicalCalculation:
    calculation_id: str
    calculation_name: str
    status: AnalysisStatus
    value: float | None
    input_observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    calculation_version: str
    parameters_fingerprint: str


@dataclass(frozen=True, slots=True)
class SharedBrainMarketTechnicalArtifact:
    artifact_id: str
    canonical_instrument_id: str
    contract_id: str
    contract_version: str
    intelligence_as_of: datetime
    latest_completed_market_session: datetime | None
    evidence_visibility_cutoff: datetime
    canonical_ohlcv_bar_ids: tuple[str, ...]
    canonical_ohlcv_lineage_fingerprint: str
    benchmark_instrument_id: str | None
    canonical_session_count: int
    latest_eligible_market_session: datetime | None
    readiness_status: OhlcvReadinessStatus
    market_data_availability: IntelligenceEvidenceAvailability
    technical_availability: IntelligenceEvidenceAvailability
    technical_calculation_version: str
    technical_calculations: tuple[MarketTechnicalCalculation, ...]
    blockers: tuple[str, ...]
    created_at: datetime
    known_at: datetime
    fingerprint: str

    def verify(self) -> None:
        _require_aware(self.intelligence_as_of)
        _require_aware(self.evidence_visibility_cutoff)
        _require_aware(self.created_at)
        _require_aware(self.known_at)
        if self.latest_completed_market_session is not None:
            _require_aware(self.latest_completed_market_session)
        if self.latest_eligible_market_session is not None:
            _require_aware(self.latest_eligible_market_session)
        if self.contract_id != ARTIFACT_ID or self.contract_version != ARTIFACT_VERSION:
            raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_CONTRACT_MISMATCH")
        if self.evidence_visibility_cutoff != self.intelligence_as_of or self.known_at > self.intelligence_as_of:
            raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_PIT_INVALID")
        if self.fingerprint != _fingerprint(self):
            raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_FINGERPRINT_MISMATCH")


class HistoricalStore(Protocol):
    def latest(self, instrument_id: str, timeframe: Timeframe, count: int, *, as_of: datetime | None = None): ...


class MarketTechnicalArtifactBuilder:
    """Build one instrument-centric artifact from existing canonical OHLCV only."""

    def __init__(
        self,
        *,
        historical: HistoricalStore,
        readiness: OhlcvReadinessService | None = None,
        technical: TechnicalAnalysisEngine | None = None,
    ) -> None:
        self._historical = historical
        self._readiness = readiness or OhlcvReadinessService(historical)  # type: ignore[arg-type]
        self._technical = technical or TechnicalAnalysisEngine()

    def build(self, *, canonical_instrument_id: str, intelligence_as_of: datetime) -> SharedBrainMarketTechnicalArtifact:
        _require_aware(intelligence_as_of)
        bars = self._historical.latest(canonical_instrument_id, Timeframe.DAILY, 300, as_of=intelligence_as_of)
        mapping_available = bool(bars and bars[-1].instrument.provider_mappings)
        readiness = self._readiness.assess(
            canonical_instrument_id, as_of=intelligence_as_of, mapping_available=mapping_available,
        )
        market = _market_availability(readiness)
        calculations: tuple[MarketTechnicalCalculation, ...] = ()
        blockers = [readiness.reason]
        if market is IntelligenceEvidenceAvailability.AVAILABLE:
            calculations = _calculations(canonical_instrument_id, intelligence_as_of, bars, self._technical)
            blockers = [item for item in blockers if item != "CURRENT_SUFFICIENT_NONCONFLICTED_HISTORY"]
            if any(item.status is not AnalysisStatus.VALID for item in calculations):
                blockers.append("TECHNICAL_CALCULATION_INSUFFICIENT")
        technical = (
            IntelligenceEvidenceAvailability.AVAILABLE
            if market is IntelligenceEvidenceAvailability.AVAILABLE and calculations
            and all(item.status is AnalysisStatus.VALID for item in calculations)
            else IntelligenceEvidenceAvailability.UNAVAILABLE
        )
        latest = bars[-1].end_time if bars else None
        value = SharedBrainMarketTechnicalArtifact(
            artifact_id="", canonical_instrument_id=canonical_instrument_id,
            contract_id=ARTIFACT_ID, contract_version=ARTIFACT_VERSION,
            intelligence_as_of=intelligence_as_of, latest_completed_market_session=latest,
            evidence_visibility_cutoff=intelligence_as_of,
            canonical_ohlcv_bar_ids=tuple(item.bar_id for item in bars),
            canonical_ohlcv_lineage_fingerprint=manifest_fingerprint(
                canonical_instrument_id=canonical_instrument_id,
                bars=tuple((item.bar_id, item.end_time, item.provenance.received_at) for item in bars),
            ),
            benchmark_instrument_id=None, canonical_session_count=len(bars),
            latest_eligible_market_session=latest, readiness_status=readiness.status,
            market_data_availability=market, technical_availability=technical,
            technical_calculation_version=TECHNICAL_CALCULATION_VERSION,
            technical_calculations=calculations, blockers=tuple(sorted(set(blockers))),
            created_at=intelligence_as_of, known_at=intelligence_as_of, fingerprint="",
        )
        fingerprint = _fingerprint(value)
        return replace(value, artifact_id=f"{ARTIFACT_ID}:{fingerprint[7:27]}", fingerprint=_fingerprint(replace(value, artifact_id=f"{ARTIFACT_ID}:{fingerprint[7:27]}")))


class SharedBrainMarketTechnicalArtifactStore:
    """Typed append-only adapter over immutable Core API snapshots."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: SharedBrainMarketTechnicalArtifact) -> SharedBrainMarketTechnicalArtifact:
        value.verify()
        existing = self._repository.get_snapshot(value.artifact_id)
        if existing is not None:
            if existing.fingerprint != value.fingerprint or existing.payload != value:
                raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_IMMUTABILITY_CONFLICT")
            return value
        self._repository.save_snapshot(CoreApiSnapshot(
            value.artifact_id, CoreApiSnapshotFamily.SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT,
            "v1", ARTIFACT_ID, value.fingerprint, value.created_at, value,
        ))
        return value

    def list(self, *, canonical_instrument_id: str | None = None, as_of: datetime | None = None) -> tuple[SharedBrainMarketTechnicalArtifact, ...]:
        values: list[SharedBrainMarketTechnicalArtifact] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT, limit=100, offset=offset)
            for item in page:
                value = item.payload
                if not isinstance(value, SharedBrainMarketTechnicalArtifact):
                    raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_PAYLOAD_INVALID")
                value.verify()
                if canonical_instrument_id is not None and value.canonical_instrument_id != canonical_instrument_id:
                    continue
                if as_of is not None and (value.intelligence_as_of > as_of or value.known_at > as_of):
                    continue
                values.append(value)
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(sorted(values, key=lambda item: (item.intelligence_as_of, item.artifact_id)))


class SharedBrainMarketTechnicalArtifactEvidenceSource:
    """Expose persisted artifact metadata to Unified State; never rebuild it."""

    def __init__(self, store: SharedBrainMarketTechnicalArtifactStore) -> None:
        self._store = store

    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        values = self._store.list(canonical_instrument_id=canonical_instrument_id, as_of=as_of)
        if not values:
            return ()
        value = values[-1]
        warnings = tuple(sorted(set((value.readiness_status.value, *value.blockers))))
        market = StoredIntelligenceArtifact(
            canonical_instrument_id=value.canonical_instrument_id, domain=IntelligenceEvidenceDomain.MARKET_DATA,
            artifact_id=value.artifact_id, artifact_fingerprint=value.fingerprint,
            availability=value.market_data_availability, evidence_as_of=value.latest_eligible_market_session,
            observed_at=value.latest_completed_market_session, available_at=value.known_at,
            freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=f"{value.contract_id}/{value.contract_version}",
            source_provenance_fingerprint=value.canonical_ohlcv_lineage_fingerprint,
            historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.PRICE,
            warnings=warnings,
        )
        technical = StoredIntelligenceArtifact(
            canonical_instrument_id=value.canonical_instrument_id, domain=IntelligenceEvidenceDomain.TECHNICAL,
            artifact_id=f"{value.artifact_id}:technical", artifact_fingerprint=value.fingerprint,
            availability=value.technical_availability, evidence_as_of=value.intelligence_as_of,
            observed_at=value.latest_completed_market_session, available_at=value.known_at,
            freshness_status=FreshnessStatus.UNKNOWN, freshness_policy_reference=value.technical_calculation_version,
            source_provenance_fingerprint=manifest_fingerprint(
                artifact_fingerprint=value.fingerprint,
                calculation_ids=tuple(item.calculation_id for item in value.technical_calculations),
            ), historical_integrity_reference=None, invalidation_domain=IntelligenceInvalidationDomain.PRICE,
            warnings=warnings,
        )
        return market, technical


def _calculations(instrument_id: str, as_of: datetime, bars, technical: TechnicalAnalysisEngine) -> tuple[MarketTechnicalCalculation, ...]:
    observations = tuple(
        price_bar_observation(item).with_validation(ValidationResult(ValidationStatus.VALID, as_of))
        for item in bars
    )
    snapshot = AsOfSnapshot(
        f"{ARTIFACT_ID}:{instrument_id}:{as_of.isoformat()}", as_of, as_of,
        "canonical-ohclv-pit-visible-only", observations,
    )
    results = (
        ("RSI14", technical.rsi(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, period=14, evaluated_at=as_of)),
        ("ATR14", technical.atr(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, period=14, evaluated_at=as_of)),
        ("SMA20", technical.sma(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, period=20, evaluated_at=as_of)),
        ("SMA50", technical.sma(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, period=50, evaluated_at=as_of)),
        ("BOLLINGER_BAND_WIDTH", technical.bollinger_band_width(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, evaluated_at=as_of)),
        ("BOLLINGER_BAND_WIDTH_PERCENTILE", technical.bollinger_band_width_percentile(snapshot, instrument_id=instrument_id, strategy_version=TECHNICAL_REFERENCE, evaluated_at=as_of, history_sessions=20)),
    )
    return tuple(_calculation(name, result) for name, result in results)


def _calculation(name: str, result: IndicatorResult) -> MarketTechnicalCalculation:
    return MarketTechnicalCalculation(
        result.id, name, result.status, result.value, result.input_observation_ids,
        result.evidence_ids, result.calculation_version,
        manifest_fingerprint(parameters=dict(result.parameters)),
    )


def _market_availability(readiness: OhlcvInstrumentReadiness) -> IntelligenceEvidenceAvailability:
    if readiness.status is OhlcvReadinessStatus.READY:
        return IntelligenceEvidenceAvailability.AVAILABLE
    if readiness.status is OhlcvReadinessStatus.CONFLICTED:
        return IntelligenceEvidenceAvailability.CONFLICTED
    if readiness.status is OhlcvReadinessStatus.STALE:
        return IntelligenceEvidenceAvailability.STALE
    return IntelligenceEvidenceAvailability.UNAVAILABLE


def _fingerprint(value: SharedBrainMarketTechnicalArtifact) -> str:
    payload = {
        "artifact_id": value.artifact_id, "canonical_instrument_id": value.canonical_instrument_id,
        "contract_id": value.contract_id, "contract_version": value.contract_version,
        "intelligence_as_of": value.intelligence_as_of.isoformat(),
        "latest_completed_market_session": None if value.latest_completed_market_session is None else value.latest_completed_market_session.isoformat(),
        "evidence_visibility_cutoff": value.evidence_visibility_cutoff.isoformat(),
        "canonical_ohlcv_bar_ids": value.canonical_ohlcv_bar_ids,
        "canonical_ohlcv_lineage_fingerprint": value.canonical_ohlcv_lineage_fingerprint,
        "benchmark_instrument_id": value.benchmark_instrument_id, "canonical_session_count": value.canonical_session_count,
        "latest_eligible_market_session": None if value.latest_eligible_market_session is None else value.latest_eligible_market_session.isoformat(),
        "readiness_status": value.readiness_status.value,
        "market_data_availability": value.market_data_availability.value,
        "technical_availability": value.technical_availability.value,
        "technical_calculation_version": value.technical_calculation_version,
        "technical_calculations": tuple((
            item.calculation_id, item.calculation_name, item.status.value, item.value,
            item.input_observation_ids, item.evidence_ids, item.calculation_version, item.parameters_fingerprint,
        ) for item in value.technical_calculations),
        "blockers": value.blockers, "created_at": value.created_at.isoformat(), "known_at": value.known_at.isoformat(),
    }
    return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("SHARED_BRAIN_MARKET_TECHNICAL_ARTIFACT_TIMEZONE_REQUIRED")


__all__ = (
    "ARTIFACT_ID", "ARTIFACT_VERSION", "MarketTechnicalArtifactBuilder", "MarketTechnicalCalculation",
    "SharedBrainMarketTechnicalArtifact", "SharedBrainMarketTechnicalArtifactEvidenceSource",
    "SharedBrainMarketTechnicalArtifactStore",
)
