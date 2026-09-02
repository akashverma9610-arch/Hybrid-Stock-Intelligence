"""Immutable, stored-evidence Market-Wide Quality & Inflection Watch.

The Watch is a discovery/read layer.  It never fetches data, evaluates a
setup, builds a Decision Score, evaluates Six Gates, or proposes an action.
Its only positive classifications are direct projections of existing canonical
diagnostic states; unsupported policy concepts are deliberately explicit.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import UTC, datetime
from enum import StrEnum
from typing import Callable, Protocol

from app.domain.models import DiagnosticResult
from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalSecurityMasterStore, HistoricalUniverseService
from app.intelligence.external_intelligence import EvidenceVersion
from app.intelligence.market_wide_evidence_readiness import EvidenceReadinessState, MarketWideEvidenceReadinessService
from app.intelligence.opportunity_archetypes import (
    ExternalEvidenceReference, OpportunityArchetype, OpportunityArchetypeRouter, ROUTING_POLICY,
)
from app.market_data.current_sector_rotation import CurrentSectorRankingStore
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunityStore
from app.reliability.integrity import ReliabilityIntegrityObservationStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import CoreUniverseAnalysisStore


WATCH_CONTRACT = "market-wide-quality-inflection-watch/v1"
# v1.1 corrects initial materialization's treatment of ``UNKNOWN`` listing
# metadata.  An exact, currently ACTIVE official NIFTY 500 membership is the
# governing listing/tradability evidence when the imported NSE universe has no
# separate listing-status field.  The version distinction keeps the first
# fail-closed empty artifact immutable and auditable rather than overwriting it.
WATCH_POLICY_VERSION = ROUTING_POLICY
NIFTY_500_UNIVERSE_ID = "NIFTY_500"


class WatchClassification(StrEnum):
    EMERGING_QUALITY = "EMERGING_QUALITY"
    EARNINGS_INFLECTION = "EARNINGS_INFLECTION"
    ORDER_BOOK_ACCELERATION = "ORDER_BOOK_ACCELERATION"
    MARGIN_INFLECTION = "MARGIN_INFLECTION"
    INSTITUTIONAL_ACCUMULATION = "INSTITUTIONAL_ACCUMULATION"
    RELATIVE_STRENGTH_WATCH = "RELATIVE_STRENGTH_WATCH"
    RISK_WATCH = "RISK_WATCH"


class WatchStatus(StrEnum):
    WATCH_ACTIVE = "WATCH_ACTIVE"
    WATCH_DATA_PARTIAL = "WATCH_DATA_PARTIAL"
    WATCH_RISK = "WATCH_RISK"
    WATCH_NO_LONGER_QUALIFIES = "WATCH_NO_LONGER_QUALIFIES"


UNSUPPORTED_CLASSIFICATIONS_V1 = (
    "BALANCE_SHEET_IMPROVEMENT_POLICY_UNRESOLVED",
    "NO_APPROVED_NON_PRE_BREAKOUT_SETUP_POLICY",
)


@dataclass(frozen=True, slots=True)
class WatchEvidenceReference:
    rule_id: str
    diagnostic_result: str
    artifact_id: str
    artifact_fingerprint: str


@dataclass(frozen=True, slots=True)
class MarketWideWatchRecord:
    watch_id: str
    canonical_instrument_id: str
    symbol: str
    company_name: str | None
    watch_as_of: datetime
    classifications: tuple[WatchClassification, ...]
    status: WatchStatus
    evidence_sufficiency: str
    evidence_references: tuple[WatchEvidenceReference, ...]
    sector: str | None
    sector_rank: int | None
    top3_eligible: bool
    decision_score_id: str | None
    decision_score_status: str
    decision_score_value: str | None
    setup_state: str
    six_gates_state: str
    reliability_state: str
    blocker_codes: tuple[str, ...]
    last_evidence_as_of: datetime | None
    policy_identity: str
    fingerprint: str
    # V1 Router additions are trailing/defaulted so older immutable Watch
    # payloads remain readable without alteration.
    archetypes: tuple[OpportunityArchetype, ...] = ()
    external_evidence_references: tuple[ExternalEvidenceReference, ...] = ()
    policy_maturity: str | None = None
    historical_quality_state: str = "UNAVAILABLE"
    current_inflection_state: str = "UNRESOLVED"
    setup_policy_routes: tuple[tuple[str, str], ...] = ()
    lifecycle_flags: tuple[str, ...] = ()
    evidence_domain_coverage: tuple[str, ...] = ()
    rotation_challenger_state: str = "NOT_A_CHALLENGER"
    comparison_readiness: str = "COMPARISON_NOT_AVAILABLE"

    @classmethod
    def create(cls, **values) -> "MarketWideWatchRecord":
        values["classifications"] = tuple(sorted(set(values["classifications"]), key=lambda item: item.value))
        values["evidence_references"] = tuple(sorted(values["evidence_references"], key=lambda item: (item.rule_id, item.artifact_id)))
        values["blocker_codes"] = tuple(sorted(set(values["blocker_codes"])))
        values["archetypes"] = tuple(sorted(set(values.get("archetypes", ())), key=lambda item: item.value))
        values["external_evidence_references"] = tuple(sorted(set(values.get("external_evidence_references", ())), key=lambda item: (item.canonical_event_id, item.evidence_version_id)))
        values["setup_policy_routes"] = tuple(sorted(set(values.get("setup_policy_routes", ()))))
        values["lifecycle_flags"] = tuple(dict.fromkeys(values.get("lifecycle_flags", ())))
        values["evidence_domain_coverage"] = tuple(sorted(set(values.get("evidence_domain_coverage", ()))))
        provisional = cls(**values, fingerprint="")
        identity = manifest_fingerprint(**_semantic(provisional, include_fingerprint=False))
        value = cls(**{**values, "watch_id": f"market-wide-watch:{identity[:32]}", "fingerprint": ""})
        return cls(**{**values, "watch_id": value.watch_id, "fingerprint": manifest_fingerprint(**_semantic(value, include_fingerprint=False))})

    def verify(self) -> None:
        if not self.watch_id or not self.canonical_instrument_id or not self.symbol:
            raise ValueError("MARKET_WIDE_WATCH_IDENTITY_REQUIRED")
        if self.watch_as_of.tzinfo is None or self.watch_as_of.utcoffset() is None:
            raise ValueError("MARKET_WIDE_WATCH_AS_OF_REQUIRED")
        if self.classifications != tuple(sorted(set(self.classifications), key=lambda item: item.value)):
            raise ValueError("MARKET_WIDE_WATCH_CLASSIFICATIONS_NONCANONICAL")
        if self.blocker_codes != tuple(sorted(set(self.blocker_codes))):
            raise ValueError("MARKET_WIDE_WATCH_BLOCKERS_NONCANONICAL")
        if self.archetypes != tuple(sorted(set(self.archetypes), key=lambda item: item.value)):
            raise ValueError("MARKET_WIDE_WATCH_ARCHETYPES_NONCANONICAL")
        if self.status is WatchStatus.WATCH_RISK and WatchClassification.RISK_WATCH not in self.classifications:
            raise ValueError("MARKET_WIDE_WATCH_RISK_STATUS_INVALID")
        if self.fingerprint != manifest_fingerprint(**_semantic(self, include_fingerprint=False)):
            raise ValueError("MARKET_WIDE_WATCH_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class MarketWideWatchRun:
    run_id: str
    watch_as_of: datetime
    universe_id: str
    universe_count: int
    eligible_count: int
    excluded_count: int
    exclusion_counts: tuple[tuple[str, int], ...]
    evidence_ready_count: int
    watch_candidate_count: int
    classification_counts: tuple[tuple[str, int], ...]
    top3_eligible_count: int
    setup_candidate_count: int
    valid_setup_count: int
    decision_score_ready_count: int
    six_gates_evaluated_count: int
    six_gates_pass_count: int
    filter_attribution: tuple[tuple[str, int], ...]
    unsupported_classifications: tuple[str, ...]
    records: tuple[MarketWideWatchRecord, ...]
    policy_identity: str
    fingerprint: str
    # Added after the initial immutable V1 run.  A default preserves reopen
    # compatibility for that historical payload; it is never rewritten.
    portfolio_records: tuple[MarketWideWatchRecord, ...] = ()
    archetype_counts: tuple[tuple[str, int], ...] = ()
    rotation_funnel: tuple[tuple[str, int], ...] = ()
    rotation_challenger_count: int = 0
    actual_rotation_candidate_count: int = 0
    evidence_readiness_counts: tuple[tuple[str, int], ...] = ()
    evidence_domain_counts: tuple[tuple[str, int], ...] = ()
    evidence_blocker_attribution: tuple[tuple[str, int], ...] = ()

    @classmethod
    def create(cls, **values) -> "MarketWideWatchRun":
        values["exclusion_counts"] = tuple(sorted(values["exclusion_counts"]))
        values["classification_counts"] = tuple(sorted(values["classification_counts"]))
        values["filter_attribution"] = tuple(sorted(values["filter_attribution"]))
        values["unsupported_classifications"] = tuple(sorted(set(values["unsupported_classifications"])))
        values["records"] = tuple(sorted(values["records"], key=lambda item: item.canonical_instrument_id))
        values["portfolio_records"] = tuple(sorted(values["portfolio_records"], key=lambda item: item.canonical_instrument_id))
        values["archetype_counts"] = tuple(sorted(values.get("archetype_counts", ())))
        values["rotation_funnel"] = tuple(sorted(values.get("rotation_funnel", ())))
        values["evidence_readiness_counts"] = tuple(sorted(values.get("evidence_readiness_counts", ())))
        values["evidence_domain_counts"] = tuple(sorted(values.get("evidence_domain_counts", ())))
        values["evidence_blocker_attribution"] = tuple(sorted(values.get("evidence_blocker_attribution", ())))
        semantic = _semantic_values(values)
        run_id = f"market-wide-watch-run:{manifest_fingerprint(**semantic)[:32]}"
        return cls(**{**values, "run_id": run_id, "fingerprint": manifest_fingerprint(**{**semantic, "run_id": run_id})})

    def verify(self) -> None:
        if self.watch_as_of.tzinfo is None or self.watch_as_of.utcoffset() is None:
            raise ValueError("MARKET_WIDE_WATCH_RUN_AS_OF_REQUIRED")
        if self.eligible_count != len(self.records):
            raise ValueError("MARKET_WIDE_WATCH_RUN_RECORD_COUNT_INVALID")
        if self.universe_count != self.eligible_count + self.excluded_count:
            raise ValueError("MARKET_WIDE_WATCH_RUN_UNIVERSE_COUNTS_INVALID")
        for record in (*self.records, *self.portfolio_records):
            record.verify()
        expected = manifest_fingerprint(**{**_semantic_values({field.name: getattr(self, field.name) for field in fields(self) if field.name not in {"fingerprint"}}), "run_id": self.run_id})
        if self.fingerprint != expected:
            raise ValueError("MARKET_WIDE_WATCH_RUN_FINGERPRINT_MISMATCH")


class MarketWideWatchStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: MarketWideWatchRun) -> bool:
        value.verify()
        existing = self._repository.get_snapshot(value.run_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("MARKET_WIDE_WATCH_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.run_id, CoreApiSnapshotFamily.MARKET_WIDE_QUALITY_INFLECTION_WATCH,
            "v1", WATCH_CONTRACT, value.fingerprint, value.watch_as_of, value,
        ))
        return True

    def latest(self, *, as_of: datetime | None = None) -> MarketWideWatchRun | None:
        # A public/read API without an explicit cutoff must never surface an
        # accidentally materialized future snapshot.
        cutoff = as_of or datetime.now(UTC)
        values: list[MarketWideWatchRun] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.MARKET_WIDE_QUALITY_INFLECTION_WATCH, limit=100, offset=offset)
            for item in page:
                if not isinstance(item.payload, MarketWideWatchRun):
                    raise ValueError("MARKET_WIDE_WATCH_PAYLOAD_INVALID")
                if item.payload.watch_as_of <= cutoff:
                    values.append(item.payload)
            if len(page) < 100:
                break
            offset += len(page)
        return max(values, key=lambda item: (item.watch_as_of, item.run_id), default=None)


class CanonicalDiagnosticReadSource(Protocol):
    def latest_canonical_diagnostic_results(self, canonical_instrument_id: str, *, as_of: datetime) -> tuple[DiagnosticResult, ...]: ...


class MarketWideWatchService:
    """Project a single PIT-safe NIFTY 500 discovery run from immutable stores."""

    def __init__(
        self, *, repository: CoreApiSnapshotRepository, universe: CoreUniverseAnalysisStore,
        memberships: HistoricalSecurityMasterStore, diagnostics: CanonicalDiagnosticReadSource,
        governance, rankings: CurrentSectorRankingStore | None = None,
        reliability: ReliabilityIntegrityObservationStore | None = None,
        portfolio_instrument_ids: Callable[[], tuple[str, ...]] | None = None,
        external_evidence_provider: Callable[[datetime], tuple[EvidenceVersion, ...]] | None = None,
        evidence_readiness: MarketWideEvidenceReadinessService | None = None,
    ) -> None:
        self._repository, self._universe, self._memberships = repository, universe, memberships
        self._diagnostics, self._governance = diagnostics, governance
        self._rankings, self._reliability = rankings, reliability
        self._portfolio_instrument_ids = portfolio_instrument_ids or (lambda: ())
        self._external_evidence_provider = external_evidence_provider or (lambda _as_of: ())
        self._evidence_readiness = evidence_readiness
        self._router = OpportunityArchetypeRouter()
        self._store = MarketWideWatchStore(repository)

    def latest(self, *, as_of: datetime | None = None) -> MarketWideWatchRun | None:
        """Read the latest PIT-valid immutable Watch run without starting work."""
        return self._store.latest(as_of=as_of)

    def run(self, *, as_of: datetime) -> MarketWideWatchRun:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("MARKET_WIDE_WATCH_AS_OF_REQUIRED")
        membership = HistoricalUniverseService().get_universe(
            universe_id=NIFTY_500_UNIVERSE_ID, as_of=as_of,
            memberships=self._memberships.memberships(NIFTY_500_UNIVERSE_ID), source_complete=True,
        )
        members = set(membership.instrument_ids)
        all_instruments = {item.instrument_id: item for item in self._universe.instruments_as_of(as_of)}
        eligible: list[NseEquityInstrument] = []
        excluded: dict[str, int] = {}
        for instrument_id in sorted(members):
            instrument = all_instruments.get(instrument_id)
            reason = _eligibility_reason(instrument)
            if reason is not None:
                excluded[reason] = excluded.get(reason, 0) + 1
            else:
                assert instrument is not None
                eligible.append(instrument)
        sector_context = self._sector_context(as_of)
        assessed, valid_setup, attribution = self._setup_context(as_of)
        reliability = self._reliability_context(as_of)
        external_evidence = self._external_evidence_context(as_of)
        readiness_run = self._evidence_readiness.assess(eligible, as_of=as_of) if self._evidence_readiness else None
        readiness_by_id = {} if readiness_run is None else {item.canonical_instrument_id: item for item in readiness_run.records}
        portfolio_ids = tuple(sorted(set(self._portfolio_instrument_ids())))
        portfolio_has_complete_score = any(
            (score := _latest_score(self._governance, instrument_id, as_of)) is not None and score.score_status == "COMPLETE"
            for instrument_id in portfolio_ids
        )
        records = tuple(self._record(
            instrument, as_of=as_of, sector_context=sector_context,
            assessed=assessed, valid_setup=valid_setup, reliability=reliability,
            external_evidence=external_evidence.get(instrument.instrument_id, ()),
            portfolio_has_complete_score=portfolio_has_complete_score,
            readiness=readiness_by_id.get(instrument.instrument_id),
        ) for instrument in eligible)
        portfolio_records = tuple(self._record(
            all_instruments[instrument_id], as_of=as_of, sector_context=sector_context,
            assessed=assessed, valid_setup=valid_setup, reliability=reliability,
            external_evidence=external_evidence.get(instrument_id, ()),
            portfolio_has_complete_score=portfolio_has_complete_score,
            readiness=None,
        ) for instrument_id in sorted(set(portfolio_ids) - members) if instrument_id in all_instruments)
        candidates = tuple(item for item in records if item.archetypes)
        counts = tuple((kind.value, sum(kind in item.classifications for item in records)) for kind in WatchClassification)
        archetype_counts = tuple((kind.value, sum(kind in item.archetypes for item in records)) for kind in OpportunityArchetype)
        challengers = tuple(item for item in candidates if item.rotation_challenger_state == "CHALLENGER_WATCH_ONLY")
        comparable = tuple(item for item in challengers if item.comparison_readiness == "COMPARABLE_EVIDENCE_CONTEXT")
        result = MarketWideWatchRun.create(
            watch_as_of=as_of, universe_id=NIFTY_500_UNIVERSE_ID,
            universe_count=len(members), eligible_count=len(records), excluded_count=sum(excluded.values()),
            exclusion_counts=tuple(excluded.items()), evidence_ready_count=sum(item.evidence_sufficiency == "READY" for item in records),
            watch_candidate_count=len(candidates), classification_counts=counts,
            top3_eligible_count=sum(item.top3_eligible for item in candidates),
            setup_candidate_count=sum(item.setup_state != "NOT_EVALUATED" for item in candidates),
            valid_setup_count=sum(item.setup_state == "CURRENT_VALID_SETUP" for item in candidates),
            decision_score_ready_count=sum(item.decision_score_status == "COMPLETE" for item in candidates),
            six_gates_evaluated_count=sum(item.six_gates_state == "EVALUATED" for item in candidates),
            six_gates_pass_count=0,
            filter_attribution=tuple(attribution.items()), unsupported_classifications=UNSUPPORTED_CLASSIFICATIONS_V1,
            records=records, portfolio_records=portfolio_records,
            policy_identity=f"{WATCH_CONTRACT}:{WATCH_POLICY_VERSION}",
            archetype_counts=archetype_counts,
            rotation_funnel=(
                ("WATCH_CHALLENGERS", len(challengers)), ("COMPARABLE_CHALLENGERS", len(comparable)),
                ("SCORE_ADVANTAGE_ELIGIBLE", 0), ("SETUP_ELIGIBLE", sum(item.setup_state == "CURRENT_VALID_SETUP" for item in comparable)),
                ("SIX_GATES_ELIGIBLE", 0), ("PORTFOLIO_FIT_ELIGIBLE", 0), ("ACTUAL_ROTATION_CANDIDATES", 0),
            ),
            rotation_challenger_count=len(challengers), actual_rotation_candidate_count=0,
            evidence_readiness_counts=() if readiness_run is None else readiness_run.readiness_counts,
            evidence_domain_counts=() if readiness_run is None else readiness_run.domain_counts,
            evidence_blocker_attribution=() if readiness_run is None else readiness_run.blocker_attribution,
        )
        existing = self._store.latest(as_of=as_of)
        if existing is not None and existing.run_id == result.run_id:
            return existing
        self._store.save(result)
        return result

    def _record(self, instrument: NseEquityInstrument, *, as_of: datetime, sector_context: dict[str, tuple[str | None, int | None, bool]], assessed: set[str], valid_setup: set[str], reliability: dict[str, str], external_evidence: tuple[EvidenceVersion, ...], portfolio_has_complete_score: bool, readiness=None) -> MarketWideWatchRecord:
        diagnostics = self._diagnostics.latest_canonical_diagnostic_results(instrument.instrument_id, as_of=as_of)
        by_rule = {str(item.rule_id): item for item in diagnostics}
        classifications, references = _classifications(by_rule)
        score = _latest_score(self._governance, instrument.instrument_id, as_of)
        setup_state = "CURRENT_VALID_SETUP" if instrument.instrument_id in valid_setup else "NO_CURRENT_SETUP" if instrument.instrument_id in assessed else "NOT_EVALUATED"
        gates = _latest_gates(self._governance, instrument.instrument_id, as_of)
        score_status = "UNSCORED" if score is None else score.score_status
        gates_state = "EVALUATED" if gates is not None else "NOT_EVALUATED"
        routing = self._router.route(
            instrument_id=instrument.instrument_id, diagnostics=diagnostics, setup_state=setup_state,
            decision_score_status=score_status, six_gates_state=gates_state,
            external_evidence=external_evidence,
        )
        reliability_state = reliability.get(instrument.instrument_id, "UNAVAILABLE")
        sector, rank, top3 = sector_context.get(instrument.instrument_id, (instrument.sector, None, False))
        diagnostic_ready = any(_diagnostic_ready(item) for item in diagnostics)
        evidence_ready = readiness is not None and readiness.readiness is EvidenceReadinessState.READY
        blockers = list(readiness.blocker_codes) if readiness is not None else ([] if diagnostic_ready else ["CANONICAL_DIAGNOSTICS_NOT_MATERIALIZED"])
        if not top3:
            blockers.append("TOP3_NOT_REQUIRED_FOR_WATCH")
        if setup_state == "NOT_EVALUATED":
            blockers.append("SETUP_NOT_EVALUATED")
        if score is None:
            blockers.append("DECISION_SCORE_NOT_COMPUTED")
        blockers.extend(routing.blocker_codes)
        status = (
            WatchStatus.WATCH_RISK if WatchClassification.RISK_WATCH in classifications else
            WatchStatus.WATCH_ACTIVE if routing.archetypes else
            WatchStatus.WATCH_NO_LONGER_QUALIFIES if (evidence_ready or diagnostic_ready) else
            WatchStatus.WATCH_DATA_PARTIAL
        )
        return MarketWideWatchRecord.create(
            watch_id="", canonical_instrument_id=instrument.instrument_id, symbol=instrument.symbol,
            company_name=instrument.company_name, watch_as_of=as_of, classifications=classifications,
            status=status, evidence_sufficiency="READY" if evidence_ready else "PARTIAL" if readiness is not None or diagnostic_ready else "UNAVAILABLE",
            evidence_references=references, sector=sector, sector_rank=rank, top3_eligible=top3,
            decision_score_id=None if score is None else score.id,
            decision_score_status=score_status,
            decision_score_value=None if score is None or score.final_score is None else str(score.final_score),
            setup_state=setup_state, six_gates_state=gates_state,
            reliability_state=reliability_state, blocker_codes=tuple(blockers),
            last_evidence_as_of=max((item.as_of_timestamp for item in diagnostics), default=None),
            policy_identity=f"{WATCH_CONTRACT}:{WATCH_POLICY_VERSION}",
            archetypes=routing.archetypes, external_evidence_references=routing.external_evidence_references,
            policy_maturity=routing.policy_maturity, historical_quality_state=routing.historical_quality_state,
            current_inflection_state=routing.current_inflection_state, setup_policy_routes=routing.setup_policy_routes,
            lifecycle_flags=routing.lifecycle_flags,
            evidence_domain_coverage=tuple(sorted(set(routing.evidence_domain_coverage + (() if readiness is None else tuple(f"{domain}:{state.value}" for domain, state in readiness.domain_states))))),
            rotation_challenger_state="CHALLENGER_WATCH_ONLY" if routing.archetypes else "NOT_A_CHALLENGER",
            comparison_readiness=(
                "UNSCORED_NOT_WEAK" if score is None else
                "COMPARABLE_EVIDENCE_CONTEXT" if portfolio_has_complete_score else
                "COMPARISON_UNAVAILABLE_NO_PORTFOLIO_SCORE"
            ),
        )

    def _sector_context(self, as_of: datetime) -> dict[str, tuple[str | None, int | None, bool]]:
        if self._rankings is None:
            return {}
        artifact = self._rankings.latest(as_of=as_of)
        if artifact is None:
            return {}
        ranks = {sector: index + 1 for index, sector in enumerate(artifact.report.ranked_sectors)}
        values: dict[str, tuple[str | None, int | None, bool]] = {}
        for item in artifact.report.constituents:
            if item.instrument_id:
                values[item.instrument_id] = (item.sector, ranks.get(item.sector), item.sector in artifact.report.top3)
        return values

    def _setup_context(self, as_of: datetime) -> tuple[set[str], set[str], dict[str, int]]:
        counts: dict[str, int] = {}
        assessed: set[str] = set()
        for assessment in self._governance.list_prebreakout_setup_assessments():
            if assessment.evaluation_as_of > as_of:
                continue
            assessed.add(assessment.instrument_id)
            for blocker in assessment.blockers:
                key = f"{blocker.category.value}:{blocker.code}"
                counts[key] = counts.get(key, 0) + 1
        valid = {item.canonical_instrument_id for item in CanonicalSetupOpportunityStore(self._repository).list(as_of=as_of)}
        return assessed, valid, counts

    def _reliability_context(self, as_of: datetime) -> dict[str, str]:
        if self._reliability is None:
            return {}
        values = self._reliability.list(as_of=as_of)
        latest: dict[str, object] = {}
        for value in values:
            current = latest.get(value.canonical_instrument_id)
            if current is None or (value.intelligence_as_of, value.artifact_id) > (current.intelligence_as_of, current.artifact_id):
                latest[value.canonical_instrument_id] = value
        return {instrument_id: value.evidence_state.value for instrument_id, value in latest.items()}

    def _external_evidence_context(self, as_of: datetime) -> dict[str, tuple[EvidenceVersion, ...]]:
        """Index already-verified company evidence visible at the requested PIT."""
        values: dict[str, list[EvidenceVersion]] = {}
        for evidence in self._external_evidence_provider(as_of):
            if evidence.received_at > as_of:
                continue
            for exposure in evidence.company_exposures:
                if exposure.canonical_instrument_id and exposure.verification_status == "VERIFIED":
                    values.setdefault(exposure.canonical_instrument_id, []).append(evidence)
        return {
            key: tuple(sorted(value, key=lambda item: (item.received_at, item.evidence_version_id)))
            for key, value in values.items()
        }


def build_local_market_wide_watch_service():
    """Compose the local stored-only V1 Watch; no provider or Brain execution."""
    from app.storage.database import DatabaseBackend, DatabaseSettings
    from app.storage.repository_factory import create_core_api_snapshot_repository
    from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    from app.market_data.historical import SQLiteHistoricalBarStore
    from app.fundamentals.store import SQLiteFinancialFactStore
    from app.filings.store import SQLiteCorporateFilingsStore
    from app.ownership.store import OwnershipObservationStore

    settings = DatabaseSettings.local_runtime()
    if settings.backend is not DatabaseBackend.SQLITE or settings.url.endswith(":memory:"):
        raise ValueError("MARKET_WIDE_WATCH_REQUIRES_PERSISTENT_SQLITE")
    path = settings.url.removeprefix("sqlite:///")
    repository = create_core_api_snapshot_repository(settings)
    governance = SQLiteStrategyGovernanceRepository(path)
    external = SQLiteExternalIntelligenceRepository(path)
    historical = SQLiteHistoricalBarStore(path)
    facts = SQLiteFinancialFactStore(path)
    filings = SQLiteCorporateFilingsStore(path)
    reliability = ReliabilityIntegrityObservationStore(repository)
    ownership = OwnershipObservationStore(repository)
    readiness = MarketWideEvidenceReadinessService(
        historical=historical, diagnostics=governance,
        financial_fact_count=lambda instrument_id: len(facts.facts(instrument_id)),
        filing_count=lambda instrument_id: len(filings.list(instrument_id=instrument_id, limit=500)),
        ownership_available=lambda instrument_id: bool(ownership.list_by_instrument(instrument_id, as_of=None, limit=1)),
        reliability_available=lambda instrument_id: bool(reliability.list(canonical_instrument_id=instrument_id)),
    )
    return MarketWideWatchService(
        repository=repository, universe=CoreUniverseAnalysisStore(repository),
        memberships=HistoricalSecurityMasterStore(repository), diagnostics=governance, governance=governance,
        rankings=CurrentSectorRankingStore(repository), reliability=reliability,
        portfolio_instrument_ids=lambda: _local_portfolio_instrument_ids(repository),
        external_evidence_provider=lambda _as_of: external.list_all_evidence_versions(),
        evidence_readiness=readiness,
    ), (repository, governance, external, historical, facts, filings)


def _local_portfolio_instrument_ids(repository: CoreApiSnapshotRepository) -> tuple[str, ...]:
    from app.api.repository_query_services import RepositoryPortfolioQueryService
    try:
        return tuple(item.instrument_id for item in RepositoryPortfolioQueryService(repository).get_snapshot().holdings)
    except Exception:
        return ()


def _classifications(by_rule: dict[str, DiagnosticResult]) -> tuple[tuple[WatchClassification, ...], tuple[WatchEvidenceReference, ...]]:
    triggers = (
        ("16", {"ACCELERATING"}, WatchClassification.EMERGING_QUALITY),
        ("24", {"ACCELERATING"}, WatchClassification.EARNINGS_INFLECTION),
        ("27", {"GROWING"}, WatchClassification.ORDER_BOOK_ACCELERATION),
        ("26", {"EXPANDING"}, WatchClassification.MARGIN_INFLECTION),
        ("22", {"INCREASING"}, WatchClassification.INSTITUTIONAL_ACCUMULATION),
        ("6", {"LEADING", "EMERGING_LEADER"}, WatchClassification.RELATIVE_STRENGTH_WATCH),
        ("19", {"STRESSED"}, WatchClassification.RISK_WATCH),
        ("24", {"DETERIORATING"}, WatchClassification.RISK_WATCH),
        ("26", {"CONTRACTING"}, WatchClassification.RISK_WATCH),
    )
    classifications: list[WatchClassification] = []
    references: list[WatchEvidenceReference] = []
    for rule_id, values, classification in triggers:
        item = by_rule.get(rule_id)
        if item is None or item.result.upper() not in values:
            continue
        classifications.append(classification)
        references.append(WatchEvidenceReference(
            rule_id=rule_id, diagnostic_result=item.result, artifact_id=item.id,
            artifact_fingerprint=item.diagnostic_fingerprint or "CANONICAL_DIAGNOSTIC_FINGERPRINT_NOT_REPORTED",
        ))
    return tuple(classifications), tuple(references)


def _eligibility_reason(instrument: NseEquityInstrument | None) -> str | None:
    if instrument is None:
        return "CANONICAL_IDENTITY_UNRESOLVED"
    if instrument.exchange != "NSE":
        return "NON_NSE_INSTRUMENT"
    if instrument.security_type != "EQUITY":
        return "UNSUPPORTED_SECURITY_TYPE"
    if instrument.tradable is False or instrument.listing_status.upper() in {"DELISTED", "SUSPENDED", "INACTIVE", "NOT_LISTED"}:
        return "NOT_LISTED_OR_TRADABLE"
    if instrument.main_board is False:
        return "NOT_MAIN_BOARD"
    return None


def _latest_score(governance, instrument_id: str, as_of: datetime):
    return max((item for item in governance.list_canonical_decision_scorecards(instrument_id) if item.as_of_timestamp <= as_of and item.evaluated_at <= as_of), key=lambda item: (item.as_of_timestamp, item.evaluated_at, item.id), default=None)


def _latest_gates(governance, instrument_id: str, as_of: datetime):
    return max((item for item in governance.list_canonical_execution_gate_evaluations(instrument_id) if item.as_of_timestamp <= as_of and item.evaluated_at <= as_of), key=lambda item: (item.as_of_timestamp, item.evaluated_at, item.id), default=None)


def _diagnostic_ready(value: DiagnosticResult) -> bool:
    return value.result.upper() not in {"INSUFFICIENT_DATA", "UNVERIFIED", "NOT_APPLICABLE", ""}


def _semantic(value, *, include_fingerprint: bool) -> dict:
    values = {field.name: getattr(value, field.name) for field in fields(value) if include_fingerprint or field.name != "fingerprint"}
    return _semantic_values(values)


def _semantic_values(values: dict) -> dict:
    def normalize(value):
        if isinstance(value, StrEnum):
            return value.value
        if isinstance(value, datetime):
            return value.astimezone(UTC).isoformat()
        if isinstance(value, tuple):
            return tuple(normalize(item) for item in value)
        if hasattr(value, "fingerprint"):
            return value.fingerprint
        return value
    return {key: normalize(value) for key, value in sorted(values.items()) if key != "fingerprint"}


__all__ = (
    "MarketWideWatchRecord", "MarketWideWatchRun", "MarketWideWatchService", "MarketWideWatchStore",
    "WatchClassification", "WatchStatus", "WATCH_CONTRACT", "UNSUPPORTED_CLASSIFICATIONS_V1",
    "build_local_market_wide_watch_service",
)
