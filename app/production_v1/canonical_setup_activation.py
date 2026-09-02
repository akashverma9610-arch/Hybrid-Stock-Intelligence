"""Canonical, stored-only setup/opportunity materialization for portfolio review.

This boundary evaluates only the five explicit portfolio instruments through
the already selected Pre-Breakout policy.  It persists opportunity evidence,
never a signal, paper-study admission, broker request, or execution decision.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum

from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)
from app.strategies.pre_breakout.candidate_assembly import (
    PreBreakoutCandidate,
    assemble_prebreakout_candidate,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment,
    PreBreakoutSetupAssessmentStatus,
)


CANONICAL_PORTFOLIO_SETUP_TARGETS: tuple[tuple[str, str], ...] = (
    ("APARINDS", "NSE:INE372A01015"),
    ("DEEPINDS", "NSE:INE0FHS01024"),
    ("GENUSPOWER", "NSE:INE955D01029"),
    ("GLAND", "NSE:INE068V01023"),
    ("ICICIBANK", "NSE:INE090A01021"),
)


class CanonicalSetupOpportunityState(StrEnum):
    CURRENT_SETUP_READY = "CURRENT_SETUP_READY"
    CURRENT_SETUP_NOT_READY = "CURRENT_SETUP_NOT_READY"


class CanonicalSetupGateInputStatus(StrEnum):
    READY = "GATE_SETUP_INPUT_READY"
    NOT_READY = "GATE_SETUP_INPUT_NOT_READY"


@dataclass(frozen=True, slots=True)
class CanonicalSetupOpportunity:
    """An immutable current opportunity, deliberately before all gate/action use."""

    opportunity_id: str
    canonical_instrument_id: str
    assessment_id: str
    assessment_fingerprint: str
    candidate: PreBreakoutCandidate
    decision_as_of: datetime
    policy_fingerprint: str
    time_horizon_status: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((
            self.opportunity_id, self.canonical_instrument_id, self.assessment_id,
            self.assessment_fingerprint, self.policy_fingerprint,
        )):
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_IDENTITY_REQUIRED")
        if self.decision_as_of.tzinfo is None or self.decision_as_of.utcoffset() is None:
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_AS_OF_REQUIRED")
        if self.candidate.instrument_id != self.canonical_instrument_id:
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_INSTRUMENT_MISMATCH")
        if self.candidate.assessment_fingerprint != self.assessment_fingerprint:
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_ASSESSMENT_LINEAGE_MISMATCH")
        if self.candidate.evaluation_as_of != self.decision_as_of:
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_AS_OF_LINEAGE_MISMATCH")
        if self.candidate.policy_fingerprint != self.policy_fingerprint:
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_POLICY_LINEAGE_MISMATCH")
        if self.time_horizon_status != "NOT_GOVERNED_FOR_SETUP_OPPORTUNITY":
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_HORIZON_SEMANTICS_INVALID")
        if self.fingerprint != _fingerprint(self):
            raise ValueError("CANONICAL_SETUP_OPPORTUNITY_FINGERPRINT_MISMATCH")

    @classmethod
    def from_assessment(cls, value: GovernedPreBreakoutSetupAssessment) -> "CanonicalSetupOpportunity":
        candidate = assemble_prebreakout_candidate(value)
        values = dict(
            opportunity_id=f"canonical-setup-opportunity:{candidate.candidate_id}",
            canonical_instrument_id=candidate.instrument_id,
            assessment_id=value.assessment_id,
            assessment_fingerprint=value.fingerprint,
            candidate=candidate,
            decision_as_of=value.evaluation_as_of,
            policy_fingerprint=candidate.policy_fingerprint,
            time_horizon_status="NOT_GOVERNED_FOR_SETUP_OPPORTUNITY",
        )
        return cls(**values, fingerprint=_fingerprint_values(values))


class CanonicalSetupOpportunityStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: CanonicalSetupOpportunity) -> bool:
        existing = self._repository.get_snapshot(value.opportunity_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("CANONICAL_SETUP_OPPORTUNITY_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.opportunity_id, CoreApiSnapshotFamily.CANONICAL_SETUP_OPPORTUNITY,
            "v1", type(value).__name__, value.fingerprint, value.decision_as_of, value,
        ))
        return True

    def list(
        self, *, as_of: datetime, canonical_instrument_id: str | None = None,
    ) -> tuple[CanonicalSetupOpportunity, ...]:
        values: list[CanonicalSetupOpportunity] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(
                CoreApiSnapshotFamily.CANONICAL_SETUP_OPPORTUNITY, limit=100, offset=offset,
            )
            values.extend(
                item.payload for item in page
                if isinstance(item.payload, CanonicalSetupOpportunity)
                and item.payload.decision_as_of <= as_of
                and (
                    canonical_instrument_id is None
                    or item.payload.canonical_instrument_id == canonical_instrument_id
                )
            )
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(sorted(values, key=lambda item: (item.decision_as_of, item.opportunity_id)))


@dataclass(frozen=True, slots=True)
class CanonicalPortfolioSetupOutcome:
    symbol: str
    canonical_instrument_id: str
    assessment_id: str
    assessment_fingerprint: str
    assessment_status: str
    setup_state: CanonicalSetupOpportunityState
    gate_setup_input_status: CanonicalSetupGateInputStatus
    opportunity_id: str | None
    opportunity_fingerprint: str | None
    blocker_codes: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.symbol, self.canonical_instrument_id, self.assessment_id, self.assessment_fingerprint)):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_OUTCOME_IDENTITY_REQUIRED")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_OUTCOME_BLOCKERS_NONCANONICAL")
        ready = self.setup_state is CanonicalSetupOpportunityState.CURRENT_SETUP_READY
        if ready != (self.gate_setup_input_status is CanonicalSetupGateInputStatus.READY):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_GATE_INPUT_STATUS_INVALID")
        if ready != bool(self.opportunity_id and self.opportunity_fingerprint):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_OPPORTUNITY_STATUS_INVALID")
        if self.fingerprint != _fingerprint(self):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_OUTCOME_FINGERPRINT_MISMATCH")

    @classmethod
    def from_assessment(
        cls, *, symbol: str, assessment: GovernedPreBreakoutSetupAssessment,
        opportunity: CanonicalSetupOpportunity | None,
    ) -> "CanonicalPortfolioSetupOutcome":
        ready = opportunity is not None
        values = dict(
            symbol=symbol,
            canonical_instrument_id=assessment.instrument_id,
            assessment_id=assessment.assessment_id,
            assessment_fingerprint=assessment.fingerprint,
            assessment_status=assessment.status.value,
            setup_state=(
                CanonicalSetupOpportunityState.CURRENT_SETUP_READY if ready
                else CanonicalSetupOpportunityState.CURRENT_SETUP_NOT_READY
            ),
            gate_setup_input_status=(
                CanonicalSetupGateInputStatus.READY if ready
                else CanonicalSetupGateInputStatus.NOT_READY
            ),
            opportunity_id=None if opportunity is None else opportunity.opportunity_id,
            opportunity_fingerprint=None if opportunity is None else opportunity.fingerprint,
            blocker_codes=tuple(sorted(
                f"{item.category.value}:{item.code}" for item in assessment.blockers
            )),
        )
        return cls(**values, fingerprint=_fingerprint_values(values))


@dataclass(frozen=True, slots=True)
class CanonicalPortfolioSetupRun:
    run_id: str
    as_of: datetime
    outcomes: tuple[CanonicalPortfolioSetupOutcome, ...]
    current_setup_count: int
    no_current_setup_count: int
    fingerprint: str

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_RUN_AS_OF_REQUIRED")
        if tuple(item.symbol for item in self.outcomes) != tuple(symbol for symbol, _ in CANONICAL_PORTFOLIO_SETUP_TARGETS):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_RUN_TARGET_SCOPE_INVALID")
        if self.current_setup_count + self.no_current_setup_count != len(self.outcomes):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_RUN_COUNTS_INVALID")
        if self.fingerprint != _fingerprint(self):
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_RUN_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, *, as_of: datetime, outcomes: tuple[CanonicalPortfolioSetupOutcome, ...]) -> "CanonicalPortfolioSetupRun":
        current = sum(item.setup_state is CanonicalSetupOpportunityState.CURRENT_SETUP_READY for item in outcomes)
        values = dict(
            as_of=as_of,
            outcomes=outcomes,
            current_setup_count=current,
            no_current_setup_count=len(outcomes) - current,
        )
        identity = manifest_fingerprint(**_semantic(values))
        return cls(
            run_id=f"canonical-portfolio-setup-run:{identity[:32]}",
            **values,
            fingerprint=_fingerprint_values({"run_id": f"canonical-portfolio-setup-run:{identity[:32]}", **values}),
        )


class CanonicalPortfolioSetupRunStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def get(self, run_id: str) -> CanonicalPortfolioSetupRun | None:
        item = self._repository.get_snapshot(run_id)
        return item.payload if item is not None and isinstance(item.payload, CanonicalPortfolioSetupRun) else None

    def save(self, value: CanonicalPortfolioSetupRun) -> bool:
        if self.get(value.run_id) is not None:
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.run_id, CoreApiSnapshotFamily.CANONICAL_PORTFOLIO_SETUP_RUN,
            "v1", type(value).__name__, value.fingerprint, value.as_of, value,
        ))
        return True


class CanonicalPortfolioSetupMaterializationService:
    """Materialize exactly the canonical portfolio setup evidence at one cutoff."""

    def __init__(
        self, *, assessment_service, assessment_repository, rotation_service,
        opportunities: CanonicalSetupOpportunityStore, runs: CanonicalPortfolioSetupRunStore,
    ) -> None:
        self._assessments = assessment_service
        self._assessment_repository = assessment_repository
        self._rotation = rotation_service
        self._opportunities = opportunities
        self._runs = runs

    def run(self, *, as_of: datetime) -> CanonicalPortfolioSetupRun:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_RUN_AS_OF_REQUIRED")
        stored = getattr(self._rotation, "latest_materialized", lambda *, as_of: None)(as_of=as_of)
        rotation = stored.report if stored is not None else self._rotation.assess(as_of=as_of)
        prepared: list[tuple[GovernedPreBreakoutSetupAssessment, CanonicalSetupOpportunity | None]] = []
        outcomes: list[CanonicalPortfolioSetupOutcome] = []
        for symbol, instrument_id in CANONICAL_PORTFOLIO_SETUP_TARGETS:
            assessment = self._existing_assessment(instrument_id, as_of=as_of)
            if assessment is None:
                assessment = self._assessments.assess_prebreakout_setup(
                    instrument_id, as_of=as_of, sector_rotation=rotation,
                )
            opportunity = (
                CanonicalSetupOpportunity.from_assessment(assessment)
                if assessment.status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE
                else None
            )
            prepared.append((assessment, opportunity))
            outcomes.append(CanonicalPortfolioSetupOutcome.from_assessment(
                symbol=symbol, assessment=assessment, opportunity=opportunity,
            ))
        result = CanonicalPortfolioSetupRun.create(as_of=as_of, outcomes=tuple(outcomes))
        existing = self._runs.get(result.run_id)
        if existing is not None:
            return existing
        for assessment, opportunity in prepared:
            stored = self._assessment_repository.get_prebreakout_setup_assessment(assessment.assessment_id)
            if stored is None:
                self._assessment_repository.save_prebreakout_setup_assessment(assessment)
            elif stored != assessment:
                raise ValueError("CANONICAL_PORTFOLIO_SETUP_ASSESSMENT_IMMUTABLE_CONFLICT")
            if opportunity is not None:
                self._opportunities.save(opportunity)
        self._runs.save(result)
        return result

    def _existing_assessment(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> GovernedPreBreakoutSetupAssessment | None:
        values = tuple(
            item for item in self._assessment_repository.list_prebreakout_setup_assessments(
                canonical_instrument_id=canonical_instrument_id,
            ) if item.evaluation_as_of == as_of
        )
        if len(values) > 1:
            raise ValueError("CANONICAL_PORTFOLIO_SETUP_ASSESSMENT_AS_OF_CONFLICT")
        return values[0] if values else None


def build_local_canonical_portfolio_setup_materialization_service():
    """Compose the local SQLite stored-only materialization operation."""
    from app.market_data.current_sector_rotation import CurrentSectorRankingStore, CurrentSectorRotationService
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.market_data.index_close_series import CoreSnapshotIndexCloseStore
    from app.market_data.nse_delivery import NseDeliveryStore
    from app.market_data.reference_data.resolver import TickSizeReferenceResolver
    from app.market_data.reference_data.sqlite_repository import SQLiteTickSizeObservationRepository
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.strategies.pre_breakout.governance import PreBreakoutPolicyGovernanceService
    from app.strategies.pre_breakout.materialization import GovernedPreBreakoutTechnicalMaterializer
    from app.strategies.pre_breakout.setup_assessment import GovernedPreBreakoutSetupAssessmentService
    from app.universe_analysis.service import CoreUniverseAnalysisStore
    from app.taxonomy.service import TaxonomySnapshotStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise ValueError("CANONICAL_PORTFOLIO_SETUP_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    governance_repository = SQLiteStrategyGovernanceRepository(path)
    historical = SQLiteHistoricalBarStore(path)
    rotation = CurrentSectorRotationService(
        repository=repository, universe=CoreUniverseAnalysisStore(repository), historical_store=historical,
        index_close_store=CoreSnapshotIndexCloseStore(repository), ranking_store=CurrentSectorRankingStore(repository),
    )
    materializer = GovernedPreBreakoutTechnicalMaterializer(
        governance=PreBreakoutPolicyGovernanceService(governance_repository),
        historical_store=historical,
        delivery_store=NseDeliveryStore(repository),
        tick_resolver=TickSizeReferenceResolver(SQLiteTickSizeObservationRepository(path)),
    )
    assessments = GovernedPreBreakoutSetupAssessmentService(
        materializer=materializer, sector_rotation_service=rotation,
        taxonomy_store=TaxonomySnapshotStore(repository),
    )
    return (
        CanonicalPortfolioSetupMaterializationService(
            assessment_service=assessments,
            assessment_repository=governance_repository,
            rotation_service=rotation,
            opportunities=CanonicalSetupOpportunityStore(repository),
            runs=CanonicalPortfolioSetupRunStore(repository),
        ),
        (repository, governance_repository),
    )


def build_local_top3_opportunity_finder_service():
    """Compose the complete current Top-3 scan without executable/paper setup creation."""
    from app.market_data.current_sector_rotation import CurrentSectorRankingStore
    from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRunStore, Top3OpportunityFinderService
    setup, (repository, governance) = build_local_canonical_portfolio_setup_materialization_service()
    return Top3OpportunityFinderService(
        rankings=CurrentSectorRankingStore(repository), assessments=setup._assessments,
        assessment_repository=governance, opportunities=setup._opportunities,
        runs=Top3OpportunityFinderRunStore(repository),
    ), (repository, governance)


def _semantic(values: dict) -> dict:
    return {
        key: _semantic_value(value)
        for key, value in sorted(values.items())
        if key not in {"fingerprint"}
    }


def _semantic_value(value):
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return tuple(_semantic_value(item) for item in value)
    if hasattr(value, "fingerprint"):
        return value.fingerprint
    return value


def _fingerprint(value) -> str:
    return _fingerprint_values({field.name: getattr(value, field.name) for field in fields(value) if field.name != "fingerprint"})


def _fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic(values))
