"""Bounded current-descriptive lens coverage over supplied canonical owner records.

No acquisition, repository selection, scheduling, portfolio or trade authority.
The owning caller reads canonical stores; this function takes their typed values.
It does not certify store origin or strict historical PIT availability.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
import json

from app.data_operations.native_technical_binding import NativeDailyBinding
from app.domain.canonical_diagnostic_strategy import (
    CanonicalDiagnosticDefinitionReader, CANONICAL_61_STRATEGY_REFERENCE,
    governance_limitations_fingerprint,
)
from app.domain.models import (
    MarketObservation, canonical_diagnostic_result,
)
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.lens_knowledge.storage import DraftLensCoverageStore
from app.lens_knowledge.universe import UniverseLensCoverageBatch, assess_universe_batch
from app.market_data.nse_udiff_daily_technical_read import (
    NseUdiffDailyTechnicalUseMode, NseUdiffDailyTechnicalReadState,
)
from app.universe_analysis.benchmark_sector_technical_input import CanonicalBenchmarkSectorTechnicalInput
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import (
    Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, build_universe_snapshot,
)
from app.universe_analysis.technical_diagnostic_input import (
    CanonicalTechnicalDiagnosticInput, assemble_current_descriptive_technical_input,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("LENS_AWARE_TIMESTAMP_REQUIRED")
    return value.astimezone(UTC)


def _fingerprint(value: object) -> str:
    return "sha256:" + sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        default=str, allow_nan=False).encode("utf-8")).hexdigest()


def technical_from_native(native: NativeDailyBinding) -> CanonicalTechnicalDiagnosticInput | None:
    """Reuse the existing adapter, including explicit missing-input receipts."""
    read = native.certified_read
    read.request.__post_init__()
    read.__post_init__()
    if read.request.use_mode is not NseUdiffDailyTechnicalUseMode.CURRENT_DESCRIPTIVE_TECHNICAL:
        raise ValueError("LENS_STRICT_HISTORICAL_PIT_NOT_SUPPORTED")
    if read.state is not NseUdiffDailyTechnicalReadState.READY:
        if native.technical_input is not None:
            raise ValueError("LENS_NATIVE_PROJECTION_MISMATCH")
        return None
    technical = assemble_current_descriptive_technical_input(
        canonical_instrument_id=read.request.canonical_instrument_id,
        as_of=_utc(read.request.evaluation_as_of),
        daily_reads=(read,), weekly_bars=())
    if native.technical_input != technical or not native.action_window_fingerprint:
        raise ValueError("LENS_NATIVE_PROJECTION_MISMATCH")
    return technical


@dataclass(frozen=True, slots=True)
class CanonicalLensInput:
    """References existing owner contracts, not another evidence database."""
    native: NativeDailyBinding
    benchmark_sector: CanonicalBenchmarkSectorTechnicalInput
    financial: CanonicalFinancialDiagnosticInput

    def __post_init__(self) -> None:
        self._validated_basis()

    def _validated_basis(self) -> tuple[CanonicalTechnicalDiagnosticInput | None, str]:
        """Validate once and retain the exact basis for this page's lineage."""
        technical = technical_from_native(self.native)
        self.benchmark_sector.__post_init__()
        self.financial.__post_init__()
        request = self.native.certified_read.request
        for item in (self.benchmark_sector, self.financial):
            if (item.canonical_instrument_id != request.canonical_instrument_id
                    or _utc(item.as_of) != _utc(request.evaluation_as_of)):
                raise ValueError("LENS_CANONICAL_INPUT_IDENTITY_MISMATCH")
        if self.benchmark_sector.technical_input != technical:
            raise ValueError("LENS_BENCHMARK_TECHNICAL_BINDING_MISMATCH")
        fingerprint = _fingerprint((self.native.certified_read.fingerprint,
            self.native.action_window_fingerprint, None if technical is None else technical.fingerprint,
            self.benchmark_sector.fingerprint, self.financial.fingerprint))
        return technical, fingerprint

    @property
    def instrument_id(self) -> str:
        return self.native.certified_read.request.canonical_instrument_id

    @property
    def fingerprint(self) -> str:
        return self._validated_basis()[1]


@dataclass(frozen=True, slots=True)
class _FrozenObservations:
    values: tuple[MarketObservation, ...]

    def observations_as_of(self, at: datetime) -> tuple[MarketObservation, ...]:
        # Existing assembler owns the PIT guard; future inputs are excluded there.
        return self.values


def run_canonical_coverage_page(
    *, universe: UniverseSnapshot, instruments: tuple[NseEquityInstrument, ...],
    as_of: datetime, cursor: int, batch_size: int,
    inputs: tuple[CanonicalLensInput, ...], observations: tuple[MarketObservation, ...],
    governance: CanonicalDiagnosticDefinitionReader,
) -> UniverseLensCoverageBatch:
    """Pure composition: one canonical run per selected stock, no writes.

    No injected provider or generic source callback runs here. Supplied typed
    source fingerprints are retained, not substituted with observation time.
    Replay recomputes; this slice adds no persistent calculation cache.
    """
    cutoff = _utc(as_of)
    if (type(cursor) is not int or type(batch_size) is not int
            or not 0 <= cursor <= len(universe.instrument_ids) or not 1 <= batch_size <= 1000):
        raise ValueError("LENS_PAGE_BOUNDS_INVALID")
    if _utc(universe.as_of) > cutoff:
        raise ValueError("LENS_FUTURE_UNIVERSE")
    if len({x.instrument_id for x in instruments}) != len(instruments):
        raise ValueError("LENS_DUPLICATE_INSTRUMENT")
    if any(_utc(x.data_as_of) > universe.as_of for x in instruments):
        raise ValueError("LENS_FUTURE_INSTRUMENT")
    rebuilt = build_universe_snapshot(snapshot_id=universe.snapshot_id, as_of=universe.as_of,
        source=universe.source, instruments=instruments, version=universe.version)
    if rebuilt != universe:
        raise ValueError("LENS_UNIVERSE_MISMATCH")
    selected = universe.instrument_ids[cursor:cursor + batch_size]
    if (not isinstance(inputs, tuple) or len(inputs) != len(selected)
            or {x.instrument_id for x in inputs} != set(selected)):
        raise ValueError("LENS_CANONICAL_PAGE_INPUTS_REQUIRED")
    if not isinstance(observations, tuple) or len({x.id for x in observations}) != len(observations):
        raise ValueError("LENS_OBSERVATION_DUPLICATE_OR_MUTABLE")
    validated = {}
    for item in inputs:
        validated[item.instrument_id] = item._validated_basis()
        if _utc(item.native.certified_read.request.evaluation_as_of) != cutoff:
            raise ValueError("LENS_INPUT_CUTOFF_MISMATCH")
    runner = Canonical61DiagnosticRunner()
    definition = runner.authorize(governance)
    if (definition.reference != CANONICAL_61_STRATEGY_REFERENCE
            or _utc(definition.created_at) > cutoff or _utc(definition.registered_at) > cutoff):
        raise ValueError("LENS_GOVERNANCE_NOT_EFFECTIVE_AS_OF")
    limitations = governance_limitations_fingerprint(definition.governance_limitations)
    # A fresh page-scoped runner prevents its internal market cache crossing vintages.
    assembler = StockDiagnosticInputAssembler(_FrozenObservations(observations))
    by_id = {x.instrument_id: x for x in instruments}
    bundles = {x.instrument_id: x for x in inputs}
    results, lineage = {}, []
    for instrument_id in selected:
        bundle = bundles[instrument_id]
        technical, input_fingerprint = validated[instrument_id]
        evidence = assembler.assemble(by_id[instrument_id], cutoff,
            technical_input=technical,
            benchmark_sector_input=bundle.benchmark_sector, financial_input=bundle.financial)
        # The existing technical contract cannot represent wholly absent bars.
        # Do not fall back to generic observations: retain an unavailable row.
        if evidence.technical_input is None:
            results[instrument_id] = ()
            lineage.append((instrument_id, _fingerprint((input_fingerprint,
                tuple(asdict(x) for x in evidence.snapshot.observations)))))
            continue
        run = runner.run(evidence)
        canonical = []
        for item in run.evaluations:
            r = item.record
            if r.strategy_version != definition.reference or r.as_of_timestamp != cutoff:
                raise ValueError("LENS_DIAGNOSTIC_LINEAGE_MISMATCH")
            record = canonical_diagnostic_result(id=r.id, instrument_id=r.instrument_id,
                rule_id=r.rule_id, strategy_version=definition.reference,
                canonical_strategy_fingerprint=definition.semantic_fingerprint,
                canonical_limitations_fingerprint=limitations, result=r.result, score=r.score,
                confidence=r.confidence, evidence_ids=r.evidence_ids,
                input_observation_ids=r.input_observation_ids, evaluated_at=r.evaluated_at,
                as_of_timestamp=r.as_of_timestamp)
            canonical.append(replace(item, record=record))
        results[instrument_id] = tuple(canonical)
        # Includes only PIT-admitted observations, retaining all source timestamps.
        admitted = tuple(asdict(x) for x in evidence.snapshot.observations)
        lineage.append((instrument_id, _fingerprint((input_fingerprint, admitted))))
    batch = assess_universe_batch(universe=universe, as_of=cutoff,
        diagnostics_by_instrument=results, cursor=cursor, batch_size=batch_size)
    return replace(batch, input_basis="CANONICAL_CURRENT_DESCRIPTIVE",
        canonical_input_fingerprints=tuple(lineage),
        canonical_strategy_fingerprint=definition.semantic_fingerprint,
        canonical_limitations_fingerprint=limitations)


def save_canonical_coverage_page(
    batch: UniverseLensCoverageBatch, *, store: DraftLensCoverageStore, recorded_at: datetime,
) -> str:
    """Explicit opt-in draft output only; never a source-ingestion receipt."""
    if batch.input_basis != "CANONICAL_CURRENT_DESCRIPTIVE":
        raise ValueError("LENS_CANONICAL_BATCH_REQUIRED")
    return store.save(batch, recorded_at=recorded_at)
