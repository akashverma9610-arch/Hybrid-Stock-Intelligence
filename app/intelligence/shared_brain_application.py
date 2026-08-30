"""Read-only application composition for the Production-v1 Shared Brain.

This is deliberately the only application-layer bridge from stored canonical
financial evidence to the U15 snapshot.  It contains no financial semantics:
selection, observation materialization, trajectories, and directionality are
all delegated to their already-governed contracts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Callable, Protocol

import app.fundamentals.financial_research_observation_bundle_schema as _bundle_contract
from app.domain.models import FreshnessStatus
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import select_financial_fact_vintages
from app.fundamentals.financial_metric_observation_materializer import (
    FinancialMetricObservationMaterializationStatus,
    materialize_financial_metric_observation,
)
from app.fundamentals.financial_metric_observation_schema import CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA
from app.fundamentals.financial_metric_trajectory_policy import CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY
from app.fundamentals.financial_research_observation_bundle_builder import build_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
    FinancialResearchObservationBundle,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
)
from app.fundamentals.financial_research_observation_wrapper import wrap_financial_research_observation_bundle
from app.fundamentals.financial_research_observation_wrapper_schema import CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA
from app.fundamentals.models import FinancialFact
from app.fundamentals.store import FinancialFactStore
from app.historical.guard import manifest_fingerprint
from app.intelligence.brain_research_comparability_policy import FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2
from app.intelligence.brain_research_comparison_state import ResearchMetricObservation
from app.intelligence.company_evidence import CompanyEvidenceStoredSource, CompositeStoredIntelligenceSource
from app.intelligence.macro_news_evidence import MacroNewsEvidenceStoredSource
from app.intelligence.non_company_evidence import NonCompanyEvidenceStoredSource
from app.intelligence.research_metric_directionality_policy import CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY
from app.intelligence.research_semantic_materiality_policy import CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY
from app.intelligence.shared_brain_production import (
    SharedBrainProductionSnapshot,
    build_shared_brain_production_snapshot,
    project_shared_brain_production_snapshot,
)
from app.intelligence.unified_state import (
    BrainOutputContext,
    IntelligenceEvidenceAvailability,
    IntelligenceEvidenceDomain,
    IntelligenceInvalidationDomain,
    UnifiedIntelligenceState,
)
from app.intelligence.unified_state_builder import (
    StoredIntelligenceArtifact,
    UnifiedIntelligenceStateBuilder,
)
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


class SharedBrainApplicationError(ValueError):
    """Typed, public-safe application-boundary failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class CanonicalInstrumentResolver(Protocol):
    def resolve(self, identifier: str, *, as_of: datetime) -> NseEquityInstrument: ...


class SharedBrainEvidenceAssembler(Protocol):
    def assemble(self, instrument: NseEquityInstrument, *, as_of: datetime) -> "SharedBrainApplicationInputs": ...


@dataclass(frozen=True, slots=True)
class SharedBrainApplicationInputs:
    """Explicit immutable U15 inputs assembled from already-stored evidence."""

    unified_state: UnifiedIntelligenceState
    financial_bundle: FinancialResearchObservationBundle
    financial_wrappers: tuple[ResearchMetricObservation, ...]
    financial_failures: tuple[FinancialResearchInputFailure, ...]


@dataclass(frozen=True, slots=True)
class FinancialSemanticView:
    """Presentation projection only; values and semantics remain upstream facts."""

    metric: str
    trajectory_basis: str
    previous_period_label: str | None
    current_period_label: str | None
    previous_value: Decimal | None
    current_value: Decimal | None
    absolute_delta: Decimal | None
    relative_delta: Decimal | None
    sign_transition: str | None
    factual_display_phrase: str | None
    directionality_orientation: str | None
    directionality_rationale_code: str | None
    materiality_governance_state: str
    trajectory_fingerprint: str
    directionality_fingerprint: str | None


@dataclass(frozen=True, slots=True)
class SharedBrainAnalysisView:
    canonical_instrument_id: str
    symbol: str
    name: str | None
    exchange: str
    as_of: datetime
    requested_context: BrainOutputContext
    evidence_status: str
    evidence_domains: tuple[tuple[str, str], ...]
    financial_semantics: tuple[FinancialSemanticView, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    snapshot_fingerprint: str
    unified_state_fingerprint: str
    brain_research_state_v2_fingerprint: str
    context_projection_fingerprint: str
    financial_semantic_section_fingerprint: str
    materiality_policy_id: str
    materiality_policy_version: str
    materiality_policy_fingerprint: str
    materiality_calibration_status: str


class CoreUniverseInstrumentResolver:
    """Exact stored NSE symbol/canonical-ID resolver; it never guesses."""

    def __init__(self, store: CoreUniverseAnalysisStore) -> None:
        self._store = store

    def resolve(self, identifier: str, *, as_of: datetime) -> NseEquityInstrument:
        normalized = identifier.strip().upper()
        if not normalized:
            raise SharedBrainApplicationError("SHARED_BRAIN_INSTRUMENT_REQUIRED", "A supported NSE symbol or canonical instrument ID is required.")
        matches = tuple(
            item for item in self._store.instruments_as_of(as_of)
            if item.exchange == "NSE" and (item.symbol.upper() == normalized or item.instrument_id.upper() == normalized)
        )
        if len(matches) != 1:
            raise SharedBrainApplicationError("SHARED_BRAIN_INSTRUMENT_NOT_FOUND", "The requested canonical NSE instrument is not available at this cutoff.")
        return matches[0]


class _InstrumentReferenceSource:
    """Creates only a canonical identity reference from the resolved universe row."""

    def __init__(self, instrument: NseEquityInstrument) -> None:
        self._instrument = instrument

    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        if canonical_instrument_id != self._instrument.instrument_id:
            return ()
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.REFERENCE_DATA,
            artifact_id=f"canonical-instrument:{canonical_instrument_id}",
            artifact_fingerprint=f"universe:{canonical_instrument_id}:{self._instrument.data_as_of.isoformat()}",
            availability=IntelligenceEvidenceAvailability.AVAILABLE,
            evidence_as_of=self._instrument.data_as_of,
            observed_at=self._instrument.data_as_of,
            available_at=self._instrument.data_as_of,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None,
            source_provenance_fingerprint=f"universe-source:{self._instrument.source}",
            historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.REFERENCE_DATA,
        ),)


class _OhlcvConflictEvidenceSource:
    """Project a durable OHLCV conflict as market-data lineage only.

    This source never reads provider data or chooses a replacement bar.  The
    Unified State builder already treats conflicted market evidence as a
    fail-closed blocker, while unrelated instruments receive no artifact.
    """

    def __init__(self, historical_bars) -> None:
        self._historical = historical_bars

    def list_stored_intelligence_artifacts(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[StoredIntelligenceArtifact, ...]:
        conflicts = self._historical.list_conflict_artifacts(instrument_id=canonical_instrument_id)
        if not conflicts:
            return ()
        fingerprints = tuple(item.conflict_fingerprint for item in conflicts)
        latest = max(item.detected_at for item in conflicts)
        return (StoredIntelligenceArtifact(
            canonical_instrument_id=canonical_instrument_id,
            domain=IntelligenceEvidenceDomain.MARKET_DATA,
            artifact_id=f"ohlcv-conflict:{canonical_instrument_id}",
            artifact_fingerprint=manifest_fingerprint(
                canonical_instrument_id=canonical_instrument_id,
                conflict_fingerprints=fingerprints,
            ),
            availability=IntelligenceEvidenceAvailability.CONFLICTED,
            evidence_as_of=latest,
            observed_at=latest,
            available_at=latest,
            freshness_status=FreshnessStatus.UNKNOWN,
            freshness_policy_reference=None,
            source_provenance_fingerprint=manifest_fingerprint(conflict_fingerprints=fingerprints),
            historical_integrity_reference=None,
            invalidation_domain=IntelligenceInvalidationDomain.PRICE,
            warnings=("OHLCV_CONFLICTED",),
        ),)


class StoredSharedBrainEvidenceAssembler:
    """Read canonical facts once, then compose governed, non-persisted artifacts."""

    def __init__(
        self,
        facts: FinancialFactStore,
        historical_bars=None,
        *,
        filings=None,
        historical_security_master=None,
        taxonomy=None,
        macro_evidence_source=None,
        news=None,
    ) -> None:
        self._facts = facts
        self._historical = historical_bars
        self._filings = filings
        self._historical_security_master = historical_security_master
        self._taxonomy = taxonomy
        self._macro_evidence_source = macro_evidence_source
        self._news = news

    def assemble(self, instrument: NseEquityInstrument, *, as_of: datetime) -> SharedBrainApplicationInputs:
        sources = [
            _InstrumentReferenceSource(instrument),
            CompanyEvidenceStoredSource(
                financial_facts=self._facts,
                filings=self._filings,
                historical_security_master=self._historical_security_master,
            ),
            NonCompanyEvidenceStoredSource(
                taxonomy=self._taxonomy,
                historical_security_master=self._historical_security_master,
            ),
            MacroNewsEvidenceStoredSource(
                macro_evidence_source=self._macro_evidence_source,
                filings=self._filings,
                news=self._news,
            ),
        ]
        if self._historical is not None:
            sources.append(_OhlcvConflictEvidenceSource(self._historical))
        source = CompositeStoredIntelligenceSource(*sources)
        unified = UnifiedIntelligenceStateBuilder(source).build(
            instrument.instrument_id, as_of=as_of, evaluation_session=as_of,
        )
        facts = self._facts.facts(instrument.instrument_id, as_of=as_of, limit=500)
        bundle = _financial_bundle(facts, canonical_instrument_id=instrument.instrument_id, as_of=as_of)
        wrappers = wrap_financial_research_observation_bundle(
            bundle, wrapper_schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_WRAPPER_SCHEMA,
        )
        return SharedBrainApplicationInputs(unified, bundle, wrappers, bundle.failures)


class SharedBrainApplicationService:
    """The one read-only application service shared by every Brain context."""

    def __init__(
        self,
        *,
        resolver: CanonicalInstrumentResolver,
        evidence_assembler: SharedBrainEvidenceAssembler,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._resolver = resolver
        self._evidence_assembler = evidence_assembler
        self._clock = clock

    def analyze_stock(
        self,
        identifier: str,
        *,
        context: BrainOutputContext,
        as_of: datetime | None = None,
    ) -> SharedBrainAnalysisView:
        if not isinstance(context, BrainOutputContext):
            raise SharedBrainApplicationError("SHARED_BRAIN_CONTEXT_INVALID", "The requested Brain context is invalid.")
        cutoff = as_of if as_of is not None else self._clock()
        if cutoff.tzinfo is None or cutoff.utcoffset() is None:
            raise SharedBrainApplicationError("SHARED_BRAIN_AS_OF_TIMEZONE_REQUIRED", "The analysis cutoff must include a timezone.")
        instrument = self._resolver.resolve(identifier, as_of=cutoff)
        inputs = self._evidence_assembler.assemble(instrument, as_of=cutoff)
        try:
            snapshot = build_shared_brain_production_snapshot(
                inputs.unified_state,
                comparability_policy=FROZEN_BRAIN_RESEARCH_COMPARABILITY_POLICY_V2,
                financial_bundle=inputs.financial_bundle,
                financial_wrappers=inputs.financial_wrappers,
                financial_failures=inputs.financial_failures,
                trajectory_policy=CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY,
                directionality_policy=CURRENT_RESEARCH_METRIC_DIRECTIONALITY_POLICY,
                materiality_policy=CURRENT_RESEARCH_SEMANTIC_MATERIALITY_POLICY,
            )
            projection = project_shared_brain_production_snapshot(snapshot, output_context=context)
        except (TypeError, ValueError) as error:
            if "UNIFIED_INTELLIGENCE_STATE_MARKET_CONFLICT" in str(error):
                raise SharedBrainApplicationError(
                    "SHARED_BRAIN_OHLCV_CONFLICTED",
                    "Stored historical OHLCV contains an unresolved conflict for this instrument.",
                ) from error
            raise SharedBrainApplicationError("SHARED_BRAIN_SNAPSHOT_UNAVAILABLE", "Stored evidence cannot form a governed Shared Brain snapshot at this cutoff.") from error
        return _view(instrument, snapshot, projection, context)


def _financial_bundle(
    facts: tuple[FinancialFact, ...], *, canonical_instrument_id: str, as_of: datetime,
) -> FinancialResearchObservationBundle:
    selections = select_financial_fact_vintages(
        facts, canonical_instrument_id=canonical_instrument_id, as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    ).selections
    facts_by_id = {fact.fact_id: fact for fact in facts}
    observations, attestations, failures = [], [], []
    for selection in selections:
        if selection.status is not FinancialFactVintageSelectionStatus.SELECTED:
            failures.append(_selection_failure(selection, canonical_instrument_id, as_of))
            continue
        fact = facts_by_id.get(selection.selected_fact_id or "")
        if fact is None:
            failures.append(_selection_failure(selection, canonical_instrument_id, as_of))
            continue
        result = materialize_financial_metric_observation(
            fact, selection=selection, schema=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
        )
        if result.status is FinancialMetricObservationMaterializationStatus.MATERIALIZED:
            assert result.observation is not None
            observation = result.observation
            observations.append(observation)
            values = dict(
                observation_fingerprint=observation.fingerprint, source_fact_id=observation.source_fact_id,
                selection_result_fingerprint=selection.fingerprint, selection_as_of=as_of,
                selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
                selector_policy_fingerprint=selection.policy_fingerprint,
                observation_schema_id=observation.schema_id, observation_schema_version=observation.schema_version,
                observation_schema_fingerprint=observation.schema_fingerprint,
            )
            attestations.append(FinancialResearchObservationAttestation(
                **values, fingerprint=_bundle_contract.manifest_fingerprint(
                    **_bundle_contract._semantic_values(values)
                ),
            ))
        else:
            failures.append(_materialization_failure(selection, result, canonical_instrument_id, as_of))
    return build_financial_research_observation_bundle(
        canonical_instrument_id=canonical_instrument_id, as_of=as_of,
        observations=tuple(observations), attestations=tuple(attestations), failures=tuple(failures),
        schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    )


def _selection_failure(selection, instrument_id: str, as_of: datetime) -> FinancialResearchInputFailure:
    values = dict(
        canonical_instrument_id=instrument_id, semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.SELECTION, selection_as_of=as_of,
        selection_status=selection.status, materialization_status=None, reason_codes=selection.reasons,
        source_fact_id=None, selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=None,
        selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.schema_id,
        observation_schema_version=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.version,
        observation_schema_fingerprint=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values, fingerprint=_bundle_contract.manifest_fingerprint(**_bundle_contract._semantic_values(values)),
    )


def _materialization_failure(selection, result, instrument_id: str, as_of: datetime) -> FinancialResearchInputFailure:
    values = dict(
        canonical_instrument_id=instrument_id, semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.MATERIALIZATION, selection_as_of=as_of,
        selection_status=selection.status, materialization_status=result.status, reason_codes=result.reasons,
        source_fact_id=result.source_fact_id, selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=result.fingerprint,
        selector_policy_id=selection.policy_id, selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=result.schema_id, observation_schema_version=result.schema_version,
        observation_schema_fingerprint=result.schema_fingerprint,
    )
    return FinancialResearchInputFailure(
        **values, fingerprint=_bundle_contract.manifest_fingerprint(**_bundle_contract._semantic_values(values)),
    )


def _view(instrument, snapshot: SharedBrainProductionSnapshot, projection, context: BrainOutputContext) -> SharedBrainAnalysisView:
    observations = {item.fingerprint: item for item in snapshot.financial_bundle.observations}
    directionality = {item.source_trajectory_fingerprint: item for item in snapshot.directionality_interpretations}
    semantics = tuple(_semantic_view(item, observations, directionality.get(item.fingerprint), snapshot) for item in snapshot.financial_trajectories)
    blockers = tuple(sorted({
        *snapshot.warnings,
        *(value.value for value in snapshot.unified_state.degraded_domains),
        *(reason.value for failure in snapshot.financial_failures for reason in failure.reason_codes),
    }))
    return SharedBrainAnalysisView(
        canonical_instrument_id=instrument.instrument_id, symbol=instrument.symbol, name=instrument.company_name,
        exchange=instrument.exchange, as_of=snapshot.as_of, requested_context=context,
        evidence_status=snapshot.unified_state.completeness.value,
        evidence_domains=tuple((item.domain.value, item.availability.value) for item in snapshot.unified_state.evidence_references),
        financial_semantics=semantics, blockers=blockers, warnings=snapshot.warnings,
        snapshot_fingerprint=snapshot.fingerprint, unified_state_fingerprint=snapshot.unified_state.fingerprint,
        brain_research_state_v2_fingerprint=snapshot.brain_research_state_v2.fingerprint,
        context_projection_fingerprint=projection.fingerprint,
        financial_semantic_section_fingerprint=projection.financial_semantic_section_fingerprint,
        materiality_policy_id=snapshot.materiality_policy_id, materiality_policy_version=snapshot.materiality_policy_version,
        materiality_policy_fingerprint=snapshot.materiality_policy_fingerprint,
        materiality_calibration_status=snapshot.materiality_calibration_status.value,
    )


def _semantic_view(trajectory, observations, interpretation, snapshot) -> FinancialSemanticView:
    previous = observations.get(trajectory.previous_observation_fingerprint)
    current = observations.get(trajectory.current_observation_fingerprint)
    return FinancialSemanticView(
        metric=trajectory.metric.value, trajectory_basis=trajectory.basis.value,
        previous_period_label=_period_label(previous), current_period_label=_period_label(current),
        previous_value=trajectory.previous_value, current_value=trajectory.current_value,
        absolute_delta=trajectory.absolute_delta, relative_delta=trajectory.relative_delta,
        sign_transition=None if trajectory.sign_transition is None else trajectory.sign_transition.value,
        factual_display_phrase=_factual_phrase(trajectory.previous_value, trajectory.current_value, trajectory.absolute_delta),
        directionality_orientation=None if interpretation is None else interpretation.orientation.value,
        directionality_rationale_code=None if interpretation is None else interpretation.rationale_code,
        materiality_governance_state=snapshot.materiality_calibration_status.value,
        trajectory_fingerprint=trajectory.fingerprint,
        directionality_fingerprint=None if interpretation is None else interpretation.fingerprint,
    )


def _period_label(observation) -> str | None:
    if observation is None:
        return None
    period = observation.period_identity
    if period.fiscal_year is not None and period.fiscal_quarter is not None:
        return f"Q{period.fiscal_quarter} FY{period.fiscal_year}"
    if period.fiscal_year is not None:
        return f"FY{period.fiscal_year}"
    if period.period_end is not None:
        return f"{period.period_type.value} ending {period.period_end.date().isoformat()} ({period.strength.value})"
    return period.strength.value


def _factual_phrase(previous: Decimal | None, current: Decimal | None, delta: Decimal | None) -> str | None:
    if previous is None or current is None or delta is None:
        return None
    if previous < 0 and current < 0:
        return "loss narrowed" if delta > 0 else "loss widened" if delta < 0 else "unchanged"
    if previous < 0 < current:
        return "loss to profit"
    if previous > 0 > current:
        return "profit to loss"
    return "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"


__all__ = (
    "CanonicalInstrumentResolver", "CoreUniverseInstrumentResolver", "FinancialSemanticView",
    "SharedBrainAnalysisView", "SharedBrainApplicationError", "SharedBrainApplicationInputs",
    "SharedBrainApplicationService", "SharedBrainEvidenceAssembler", "StoredSharedBrainEvidenceAssembler",
)
