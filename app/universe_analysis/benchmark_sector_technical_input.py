"""Canonical current-descriptive benchmark/sector evidence for Rules 1--3/6.

This is a narrow adapter, not another technical brain or indicator layer.  It
combines a supplied certified equity Daily snapshot with separately governed,
first-party calculated-index OHLC observations.  Index data remains distinct
from equity OHLCV: it has no volume, VWAP, delivery, or corporate-action
semantics.  Strict historical PIT availability is intentionally not claimed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from app.domain.models import (
    AsOfSnapshot,
    DataQuality,
    DerivedObservationMetadata,
    Instrument,
    MarketObservation,
    ObservationKind,
    Provenance,
    ValidationResult,
    ValidationStatus,
)
from app.market_data.official_nse_index_ohlc import (
    CanonicalOfficialIndexOhlcObservation,
    INDEX_LEVEL_BASIS,
    INDEX_RETURN_FAMILY,
)
from app.taxonomy.nse_sector_indices import NseSectorIndexMapping, SectorIndexMappingStatus
from app.universe_analysis.technical_diagnostic_input import (
    CanonicalTechnicalDiagnosticInput,
    StrictHistoricalPitTechnicalState,
)


CONTRACT_ID = "canonical-benchmark-sector-technical-input"
CONTRACT_VERSION = "v1"
CANONICAL_BENCHMARK_ID = "NIFTY_50"
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class BenchmarkSectorTechnicalState(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BenchmarkSectorTechnicalBlocker(StrEnum):
    BENCHMARK_HISTORY_NOT_READY = "BENCHMARK_HISTORY_NOT_READY"
    SECTOR_INDEX_NOT_MAPPED = "SECTOR_INDEX_NOT_MAPPED"
    SECTOR_HISTORY_NOT_READY = "SECTOR_HISTORY_NOT_READY"
    SESSION_ALIGNMENT_FAILED = "SESSION_ALIGNMENT_FAILED"
    DAILY_CANONICAL_INPUT_UNAVAILABLE = "DAILY_CANONICAL_INPUT_UNAVAILABLE"
    DAILY_HISTORY_INSUFFICIENT = "DAILY_HISTORY_INSUFFICIENT"


class PeerCohortState(StrEnum):
    """Existing Rule 6 takes peers as descriptive context only."""

    NOT_APPLICABLE = "NOT_APPLICABLE"


class BenchmarkSectorTechnicalInputError(ValueError):
    """Stable fail-closed error for malformed contextual evidence."""


@dataclass(frozen=True, slots=True)
class CanonicalBenchmarkSectorTechnicalInput:
    """Immutable source-specific context; no calculations or policy changes."""

    canonical_instrument_id: str
    as_of: datetime
    technical_input: CanonicalTechnicalDiagnosticInput | None
    benchmark_index_id: str
    benchmark_observations: tuple[CanonicalOfficialIndexOhlcObservation, ...]
    canonical_sector: str | None
    sector_mapping_id: str | None
    sector_index_id: str | None
    sector_observations: tuple[CanonicalOfficialIndexOhlcObservation, ...]
    benchmark_state: BenchmarkSectorTechnicalState
    sector_state: BenchmarkSectorTechnicalState
    peer_cohort_state: PeerCohortState
    strict_historical_pit_state: StrictHistoricalPitTechnicalState
    fingerprint: str

    def __post_init__(self) -> None:
        benchmark = _canonical_observations(self.benchmark_observations, self.benchmark_index_id, self.as_of)
        sector = _canonical_observations(self.sector_observations, self.sector_index_id, self.as_of)
        if self.technical_input is not None:
            self.technical_input.__post_init__()
        values = _values(
            self.canonical_instrument_id, self.as_of, self.technical_input,
            self.benchmark_index_id, benchmark, self.canonical_sector,
            self.sector_mapping_id, self.sector_index_id, sector,
            self.benchmark_state, self.sector_state, self.peer_cohort_state,
            self.strict_historical_pit_state,
        )
        if (
            not _ID.fullmatch(self.canonical_instrument_id)
            or not _aware(self.as_of)
            or self.benchmark_index_id != CANONICAL_BENCHMARK_ID
            or self.benchmark_observations != benchmark
            or self.sector_observations != sector
            or self.fingerprint != _fingerprint(values)
            or not _FP.fullmatch(self.fingerprint)
            or self.peer_cohort_state is not PeerCohortState.NOT_APPLICABLE
            or self.strict_historical_pit_state is not StrictHistoricalPitTechnicalState.NOT_READY
            or (self.technical_input is not None and (
                self.technical_input.canonical_instrument_id != self.canonical_instrument_id
                or _utc(self.technical_input.as_of) != _utc(self.as_of)
            ))
            or (self.sector_index_id is None and (
                self.sector_mapping_id is not None or sector
                or self.sector_state is not BenchmarkSectorTechnicalState.NOT_READY
            ))
            or (self.sector_index_id is not None and (
                not _ID.fullmatch(self.sector_index_id)
                or not self.canonical_sector or not self.sector_mapping_id
            ))
            or (self.benchmark_state is BenchmarkSectorTechnicalState.READY and len(benchmark) < 4)
            or (self.sector_state is BenchmarkSectorTechnicalState.READY and (
                self.sector_index_id is None or len(sector) < 4
                or not _aligned(_last_sessions(sector, 4), _last_sessions(benchmark, 4))
            ))
        ):
            raise BenchmarkSectorTechnicalInputError("CANONICAL_BENCHMARK_SECTOR_TECHNICAL_INPUT_INVALID")

    @property
    def combined_snapshot(self) -> AsOfSnapshot | None:
        """A deterministic analysis snapshot containing no manufactured fields."""
        if not self.benchmark_observations:
            return None
        stock = () if self.technical_input is None or self.technical_input.daily_snapshot is None else self.technical_input.daily_snapshot.observations
        return _snapshot(self.fingerprint, self.as_of, stock, self.benchmark_observations, self.sector_observations)

    def _relative_strength_snapshot(self, stock: tuple[MarketObservation, ...]) -> tuple[AsOfSnapshot | None, str | None, str | None]:
        """Require exactly the equity sessions selected by its certified read.

        Index acquisition may be newer than the equity UDiFF window.  Rule 6
        therefore receives only the matching stock-date slice, rather than a
        newer benchmark endpoint or a forward-filled substitute.
        """
        stock = tuple(sorted(stock, key=lambda item: (item.provenance.market_timestamp, item.id)))
        stock_dates = tuple(item.provenance.market_timestamp.date() for item in stock)
        by_benchmark = {item.session.date(): item for item in self.benchmark_observations}
        if len(stock) < 4:
            return None, BenchmarkSectorTechnicalBlocker.DAILY_HISTORY_INSUFFICIENT.value, None
        if any(day not in by_benchmark for day in stock_dates):
            return None, BenchmarkSectorTechnicalBlocker.SESSION_ALIGNMENT_FAILED.value, None
        benchmark = tuple(by_benchmark[day] for day in stock_dates)
        sector: tuple[CanonicalOfficialIndexOhlcObservation, ...] = ()
        sector_id: str | None = None
        if self.sector_state is BenchmarkSectorTechnicalState.READY:
            by_sector = {item.session.date(): item for item in self.sector_observations}
            if all(day in by_sector for day in stock_dates):
                sector = tuple(by_sector[day] for day in stock_dates)
                sector_id = self.sector_index_id
        return _snapshot(self.fingerprint + ":rule6", self.as_of, stock, benchmark, sector), None, sector_id

    def rule_input(self, rule_id: int) -> tuple[AsOfSnapshot | None, str | None, str | None]:
        """Return only existing evaluator inputs, with no fallback or inference.

        The last member is the exact sector-index identity where an evaluator
        can consume it.  Rule 6 remains valid without it because the existing
        evaluator's classification does not depend on peers or sector return.
        """
        if rule_id not in {1, 2, 3, 6}:
            raise BenchmarkSectorTechnicalInputError("BENCHMARK_SECTOR_RULE_UNSUPPORTED")
        if self.benchmark_state is not BenchmarkSectorTechnicalState.READY:
            return None, BenchmarkSectorTechnicalBlocker.BENCHMARK_HISTORY_NOT_READY.value, None
        snapshot = self.combined_snapshot
        if snapshot is None:
            return None, BenchmarkSectorTechnicalBlocker.BENCHMARK_HISTORY_NOT_READY.value, None
        if rule_id == 1:
            return snapshot, None, None
        if rule_id in {2, 3}:
            if self.sector_index_id is None:
                return None, BenchmarkSectorTechnicalBlocker.SECTOR_INDEX_NOT_MAPPED.value, None
            if self.sector_state is not BenchmarkSectorTechnicalState.READY:
                return None, BenchmarkSectorTechnicalBlocker.SECTOR_HISTORY_NOT_READY.value, None
            return snapshot, None, self.sector_index_id
        daily = None if self.technical_input is None else self.technical_input.daily_snapshot
        if daily is None:
            return None, BenchmarkSectorTechnicalBlocker.DAILY_CANONICAL_INPUT_UNAVAILABLE.value, None
        return self._relative_strength_snapshot(daily.observations)


def assemble_current_descriptive_benchmark_sector_input(
    *,
    canonical_instrument_id: str,
    as_of: datetime,
    technical_input: CanonicalTechnicalDiagnosticInput | None,
    benchmark_observations: Iterable[CanonicalOfficialIndexOhlcObservation],
    sector_mapping: NseSectorIndexMapping | None,
    sector_observations: Iterable[CanonicalOfficialIndexOhlcObservation] = (),
) -> CanonicalBenchmarkSectorTechnicalInput:
    """Build a deterministic current-descriptive context from injected facts."""
    if not _ID.fullmatch(canonical_instrument_id) or not _aware(as_of):
        raise BenchmarkSectorTechnicalInputError("BENCHMARK_SECTOR_TECHNICAL_REQUEST_INVALID")
    cutoff = _utc(as_of)
    benchmark = _canonical_observations(tuple(benchmark_observations), CANONICAL_BENCHMARK_ID, cutoff)
    supplied_sector_observations = tuple(sector_observations)
    if sector_mapping is None or sector_mapping.status is not SectorIndexMappingStatus.EXACT_OFFICIAL:
        if supplied_sector_observations:
            raise BenchmarkSectorTechnicalInputError("SECTOR_INDEX_OBSERVATIONS_UNMAPPED")
        canonical_sector = None if sector_mapping is None else sector_mapping.canonical_sector
        mapping_id = index_id = None
        sector = ()
    else:
        canonical_sector = sector_mapping.canonical_sector
        mapping_id = sector_mapping.mapping_id
        index_id = canonical_sector_index_id(canonical_sector)
        sector = _canonical_observations(supplied_sector_observations, index_id, cutoff)
        # The benchmark owns the comparative endpoint. A newer sector fetch
        # must not hide an already available matching window, or compare a
        # newer sector close against an older benchmark close. Validate all
        # supplied lineage above before selecting this exact existing prefix;
        # never fill a missing session or move the benchmark endpoint back.
        if benchmark:
            sector = tuple(item for item in sector if item.session.date() <= benchmark[-1].session.date())
    benchmark_state = BenchmarkSectorTechnicalState.READY if len(benchmark) >= 4 else BenchmarkSectorTechnicalState.NOT_READY
    sector_state = (
        BenchmarkSectorTechnicalState.NOT_READY if index_id is None
        else BenchmarkSectorTechnicalState.READY if len(sector) >= 4 and _aligned(_last_sessions(sector, 4), _last_sessions(benchmark, 4))
        else BenchmarkSectorTechnicalState.NOT_READY
    )
    values = _values(
        canonical_instrument_id, cutoff, technical_input, CANONICAL_BENCHMARK_ID,
        benchmark, canonical_sector, mapping_id, index_id, sector, benchmark_state,
        sector_state, PeerCohortState.NOT_APPLICABLE,
        StrictHistoricalPitTechnicalState.NOT_READY,
    )
    return CanonicalBenchmarkSectorTechnicalInput(
        canonical_instrument_id, cutoff, technical_input, CANONICAL_BENCHMARK_ID,
        benchmark, canonical_sector, mapping_id, index_id, sector, benchmark_state,
        sector_state, PeerCohortState.NOT_APPLICABLE,
        StrictHistoricalPitTechnicalState.NOT_READY, _fingerprint(values),
    )


def canonical_sector_index_id(canonical_sector: str) -> str:
    """The exact canonical index identity derives from the governed mapping key."""
    value = re.sub(r"[^A-Z0-9]+", "_", canonical_sector.upper()).strip("_")
    if not value:
        raise BenchmarkSectorTechnicalInputError("SECTOR_INDEX_IDENTITY_REQUIRED")
    return f"NSE_SECTOR_INDEX:{value}"


def _canonical_observations(values, expected_index_id, cutoff):
    if expected_index_id is None:
        if values:
            raise BenchmarkSectorTechnicalInputError("SECTOR_INDEX_OBSERVATIONS_UNMAPPED")
        return ()
    result = tuple(sorted(values, key=lambda item: (item.session, item.observation_id)))
    sessions: set[datetime] = set()
    for item in result:
        item.__post_init__()
        if (
            item.canonical_index_id != expected_index_id
            or item.index_level_basis != INDEX_LEVEL_BASIS
            or item.index_return_family != INDEX_RETURN_FAMILY
            or not item.eligible_as_of(cutoff)
            or item.session in sessions
        ):
            raise BenchmarkSectorTechnicalInputError("CANONICAL_INDEX_OHLC_LINEAGE_INVALID")
        sessions.add(item.session)
    return result


def _index_observation(value: CanonicalOfficialIndexOhlcObservation) -> MarketObservation:
    payload = {
        "open": float(value.open), "high": float(value.high), "low": float(value.low), "close": float(value.close),
        "index_level_basis": value.index_level_basis,
        "index_return_family": value.index_return_family,
        "official_index_name": value.official_index_name,
        "raw_artifact_sha256": value.raw_artifact_sha256,
        "evidence_fingerprint": value.evidence_fingerprint,
    }
    return MarketObservation(
        value.observation_id,
        Instrument(value.canonical_index_id, value.official_index_name, "NSE_INDICES"),
        ObservationKind.PRICE_BAR, payload,
        Provenance(
            "canonical_nse_indices_current_descriptive_technical", value.source_reference,
            _utc(value.session), _utc(value.retrieved_at), DataQuality.HIGH,
            original_record={
                "official_index_ohlc_observation_id": value.observation_id,
                "raw_artifact_sha256": value.raw_artifact_sha256,
                "evidence_fingerprint": value.evidence_fingerprint,
            },
        ),
        ValidationResult(ValidationStatus.VALID, _utc(value.retrieved_at)),
        DerivedObservationMetadata(
            (value.observation_id, f"artifact:{value.raw_artifact_sha256}"),
            "official_index_ohlc_to_technical_snapshot",
            {"basis": INDEX_LEVEL_BASIS, "return_family": INDEX_RETURN_FAMILY},
            CONTRACT_VERSION, _utc(value.retrieved_at),
        ),
    )


def _snapshot(
    fingerprint: str,
    as_of: datetime,
    stock: tuple[MarketObservation, ...],
    benchmark: tuple[CanonicalOfficialIndexOhlcObservation, ...],
    sector: tuple[CanonicalOfficialIndexOhlcObservation, ...],
) -> AsOfSnapshot:
    observations = tuple(sorted(
        (*stock, *(_index_observation(item) for item in benchmark), *(_index_observation(item) for item in sector)),
        key=lambda item: (item.provenance.market_timestamp, item.id),
    ))
    identity = _fingerprint({
        "context": fingerprint,
        "observations": [item.id for item in observations],
    }).removeprefix("sha256:")[:32]
    return AsOfSnapshot(
        f"benchmark-sector-technical:{identity}", _utc(as_of), _utc(as_of),
        f"{CONTRACT_ID}:{CONTRACT_VERSION};CURRENT_DESCRIPTIVE_TECHNICAL;INDEX_PRICE_RETURN_ONLY",
        observations,
    )


def _last_sessions(values, count):
    return tuple(item.provenance.market_timestamp.date() if isinstance(item, MarketObservation) else item.session.date() for item in values[-count:])


def _aligned(left, right) -> bool:
    return bool(left) and tuple(left) == tuple(right)


def _values(instrument, as_of, technical, benchmark_id, benchmark, sector, mapping_id, sector_id, sector_values, benchmark_state, sector_state, peers, strict):
    return {
        "contract": CONTRACT_ID,
        "version": CONTRACT_VERSION,
        "canonical_instrument_id": instrument,
        "as_of": _utc(as_of).isoformat(),
        "technical_input_fingerprint": None if technical is None else technical.fingerprint,
        "benchmark_index_id": benchmark_id,
        "benchmark_observation_ids": [item.observation_id for item in benchmark],
        "benchmark_evidence_fingerprints": [item.evidence_fingerprint for item in benchmark],
        "canonical_sector": sector,
        "sector_mapping_id": mapping_id,
        "sector_index_id": sector_id,
        "sector_observation_ids": [item.observation_id for item in sector_values],
        "sector_evidence_fingerprints": [item.evidence_fingerprint for item in sector_values],
        "benchmark_state": benchmark_state.value,
        "sector_state": sector_state.value,
        "peer_cohort_state": peers.value,
        "strict_historical_pit_state": strict.value,
    }


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise BenchmarkSectorTechnicalInputError("BENCHMARK_SECTOR_TIMESTAMP_AWARE_REQUIRED")
    return value.astimezone(UTC)


__all__ = (
    "BenchmarkSectorTechnicalBlocker", "BenchmarkSectorTechnicalInputError",
    "BenchmarkSectorTechnicalState", "CANONICAL_BENCHMARK_ID",
    "CanonicalBenchmarkSectorTechnicalInput", "PeerCohortState",
    "assemble_current_descriptive_benchmark_sector_input", "canonical_sector_index_id",
)
