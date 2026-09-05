"""Forward-only immutable Compounder research-shadow observations.

This module freezes only factual, PIT-safe Compounder input observations.  It
does not run the pre-registered grid, classify a company, make a forecast, or
depend on a portfolio, market price, API, broker, or runtime clock.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Callable, Iterable

from app.fundamentals.compounder_canonical_annual_facts import (
    CanonicalAnnualFactsReadinessReceipt,
    assess_canonical_annual_facts,
)
from app.fundamentals.compounder_testable_derived_metrics import (
    CompounderDerivedMetric,
    CompounderDerivedResearchEvaluation,
    CompounderDerivedStatus,
    CompounderDerivedWindow,
    evaluate_compounder_testable_derived_metrics,
)
from app.fundamentals.models import FinancialFact, StatementScope
from app.historical.nse_session_identity import (
    NseSessionPointIdentity,
    nse_session_point_identity_fingerprint,
)
from app.historical.pit_company_type_classification_activation import (
    PitCompanyType,
    PitCompanyTypeClassificationReceipt,
    PitCompanyTypeClassificationState,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)


CONTRACT_ID = "compounder-prospective-shadow-validation"
CONTRACT_VERSION = "v1"
RESEARCH_PROPOSAL_ID = "COMPOUNDER_TESTABLE_SUBSET_V1"
RESEARCH_PROPOSAL_VERSION = "v1-research-only"
FINGERPRINT_SCHEME = "compounder-prospective-shadow/sha256/v1"
_ID = re.compile(r"[A-Za-z0-9._:-]+")
_FP = re.compile(r"sha256:[0-9a-f]{64}")


class CompounderProspectiveShadowError(ValueError):
    pass


class ProspectiveReadinessState(StrEnum):
    PROSPECTIVE_OBSERVATION_READY = "PROSPECTIVE_OBSERVATION_READY"
    SECURITY_IDENTITY_UNAVAILABLE = "SECURITY_IDENTITY_UNAVAILABLE"
    ISSUER_EVIDENCE_UNAVAILABLE = "ISSUER_EVIDENCE_UNAVAILABLE"
    COMPANY_TYPE_UNAVAILABLE = "COMPANY_TYPE_UNAVAILABLE"
    UNSUPPORTED_COMPANY_TYPE = "UNSUPPORTED_COMPANY_TYPE"
    FINANCIAL_FACTS_MISSING = "FINANCIAL_FACTS_MISSING"
    METRICS_INCOMPLETE = "METRICS_INCOMPLETE"
    METRICS_NON_COMPARABLE = "METRICS_NON_COMPARABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    BASIS_MISMATCH = "BASIS_MISMATCH"
    INPUT_AFTER_AS_OF = "INPUT_AFTER_AS_OF"


class ProspectiveWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


class BusinessOutcomeHorizon(StrEnum):
    ONE_YEAR = "ONE_YEAR"
    THREE_YEARS = "THREE_YEARS"
    FIVE_YEARS = "FIVE_YEARS"


class BusinessOutcomeMaturity(StrEnum):
    IMMATURE = "IMMATURE"
    FUTURE_EVIDENCE_REQUIRED = "FUTURE_EVIDENCE_REQUIRED"
    AVAILABLE = "AVAILABLE"


class MarketOutcomeReadiness(StrEnum):
    MARKET_OUTCOME_NOT_READY = "MARKET_OUTCOME_NOT_READY"


@dataclass(frozen=True, slots=True)
class CompounderCandidateGridResearchPlan:
    """Frozen anti-hindsight research lineage; values are never evaluated."""

    plan_id: str
    proposal_id: str
    proposal_version: str
    research_values: tuple[tuple[str, tuple[str, ...]], ...]
    state: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            _identifier(self.plan_id) and self.proposal_id == RESEARCH_PROPOSAL_ID
            and self.proposal_version == RESEARCH_PROPOSAL_VERSION
            and self.state == "NOT_APPROVED_NOT_ACTIVE_NON_EXECUTABLE"
            and self.research_values == _canonical_pairs(self.research_values)
            and self.fingerprint == _fingerprint(_plan_payload(self))
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
        ):
            raise CompounderProspectiveShadowError("COMPOUNDER_GRID_PLAN_INVALID")


def frozen_compounder_candidate_grid_plan() -> CompounderCandidateGridResearchPlan:
    values = (
        ("annual_observations", ("3", "5")),
        ("cumulative_cfo_pat", ("0.70", "0.80", "0.90", "1.00")),
        ("median_roe", ("12%", "15%", "18%", "20%")),
        ("pat_cagr", ("8%", "10%", "12%", "15%", "20%")),
        ("persistence", ("50%", "75%", "100%")),
        ("revenue_cagr", ("5%", "8%", "10%", "12%", "15%")),
    )
    body = dict(
        plan_id="compounder-candidate-grid:" + _hash({"proposal": RESEARCH_PROPOSAL_ID, "version": RESEARCH_PROPOSAL_VERSION, "values": values})[:24],
        proposal_id=RESEARCH_PROPOSAL_ID, proposal_version=RESEARCH_PROPOSAL_VERSION,
        research_values=values, state="NOT_APPROVED_NOT_ACTIVE_NON_EXECUTABLE",
    )
    return CompounderCandidateGridResearchPlan(**body, fingerprint=_fingerprint(_plan_payload_values(body)))


@dataclass(frozen=True, slots=True)
class CompounderProspectiveObservation:
    """A factual, immutable input snapshot; it has no qualification result."""

    observation_id: str
    canonical_instrument_id: str
    isin: str
    canonical_issuer_id: str
    issuer_observation_id: str
    issuer_observation_fingerprint: str
    security_identity: NseSessionPointIdentity
    company_type_receipt: PitCompanyTypeClassificationReceipt
    as_of: datetime
    input_known_at: datetime
    statement_scope: StatementScope
    annual_facts: CanonicalAnnualFactsReadinessReceipt
    derived_metrics: CompounderDerivedResearchEvaluation
    candidate_grid_plan_id: str
    candidate_grid_fingerprint: str
    proposal_id: str
    proposal_version: str
    fact_selection_policy_versions: tuple[tuple[str, str], ...]
    company_type_policy_version: str
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    research_status: str = "RESEARCH_SHADOW"
    execution_status: str = "NON_EXECUTABLE"
    qualification_status: str = "QUALIFICATION_NOT_EVALUATED"

    def __post_init__(self) -> None:
        _validate_observation(self)
        if self.observation_id != _observation_id(self):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_IDENTITY_MISMATCH")
        if self.fingerprint != _fingerprint(_observation_payload(self)):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class CompounderProspectiveReadiness:
    canonical_instrument_id: str
    canonical_issuer_id: str
    statement_scope: StatementScope | None
    as_of: datetime
    state: ProspectiveReadinessState
    reasons: tuple[str, ...]
    observation: CompounderProspectiveObservation | None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not (_identifier(self.canonical_instrument_id) and _identifier(self.canonical_issuer_id) and _aware(self.as_of)):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_READINESS_INVALID")
        if self.reasons != tuple(sorted(set(self.reasons))) or not all(_identifier(item) for item in self.reasons):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_READINESS_REASONS_INVALID")
        if (self.state is ProspectiveReadinessState.PROSPECTIVE_OBSERVATION_READY) != (self.observation is not None):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_READINESS_STATE_CONTRADICTION")
        if self.observation is not None and (self.observation.canonical_instrument_id != self.canonical_instrument_id or self.observation.canonical_issuer_id != self.canonical_issuer_id or self.observation.statement_scope is not self.statement_scope):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_READINESS_OBSERVATION_MISMATCH")
        object.__setattr__(self, "fingerprint", _fingerprint(_readiness_payload(self)))


@dataclass(frozen=True, slots=True)
class CompounderBusinessOutcomeReadiness:
    observation_id: str
    observation_fingerprint: str
    horizon: BusinessOutcomeHorizon
    maturity: BusinessOutcomeMaturity
    future_fact_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (_identifier(self.observation_id) and _fingerprint_value(self.observation_fingerprint) and isinstance(self.horizon, BusinessOutcomeHorizon) and isinstance(self.maturity, BusinessOutcomeMaturity)):
            raise CompounderProspectiveShadowError("COMPOUNDER_BUSINESS_OUTCOME_READINESS_INVALID")
        if self.maturity is BusinessOutcomeMaturity.AVAILABLE and not self.future_fact_ids:
            raise CompounderProspectiveShadowError("COMPOUNDER_BUSINESS_OUTCOME_FACTS_REQUIRED")
        if self.maturity is not BusinessOutcomeMaturity.AVAILABLE and self.future_fact_ids:
            raise CompounderProspectiveShadowError("COMPOUNDER_BUSINESS_OUTCOME_FABRICATION_FORBIDDEN")


@dataclass(frozen=True, slots=True)
class CompounderMarketOutcomeReadiness:
    observation_id: str
    observation_fingerprint: str
    state: MarketOutcomeReadiness = MarketOutcomeReadiness.MARKET_OUTCOME_NOT_READY

    def __post_init__(self) -> None:
        if not (_identifier(self.observation_id) and _fingerprint_value(self.observation_fingerprint) and self.state is MarketOutcomeReadiness.MARKET_OUTCOME_NOT_READY):
            raise CompounderProspectiveShadowError("COMPOUNDER_MARKET_OUTCOME_READINESS_INVALID")


@dataclass(frozen=True, slots=True)
class CompounderProspectiveBatchReport:
    report_id: str
    as_of: datetime
    non_financial_issuers_considered: int
    prospective_ready: int
    consolidated_ready: int
    standalone_ready: int
    observations_inserted: int
    observations_already_present: int
    rejected_by_state: tuple[tuple[str, int], ...]
    observation_ids: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (_identifier(self.report_id) and _aware(self.as_of) and min(self.non_financial_issuers_considered, self.prospective_ready, self.consolidated_ready, self.standalone_ready, self.observations_inserted, self.observations_already_present) >= 0 and self.rejected_by_state == _canonical_counts(self.rejected_by_state) and self.observation_ids == tuple(sorted(set(self.observation_ids))) and self.fingerprint == _fingerprint(_batch_payload(self))):
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_BATCH_REPORT_INVALID")


class CompounderProspectiveShadowStore:
    """Insert-only storage in the existing immutable core snapshot family."""

    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save_plan(self, value: CompounderCandidateGridResearchPlan) -> ProspectiveWriteOutcome:
        return self._save("compounder-prospective-plan:" + value.plan_id, value, datetime(1970, 1, 1, tzinfo=UTC))

    def save_observation(self, value: CompounderProspectiveObservation) -> ProspectiveWriteOutcome:
        value.verify()
        return self._save(value.observation_id, value, value.as_of)

    def save_report(self, value: CompounderProspectiveBatchReport) -> ProspectiveWriteOutcome:
        existing = self._repository.get_snapshot(value.report_id)
        if existing is not None:
            # A replay's *run-local* inserted/already-present counters differ,
            # but its immutable coverage receipt identity is the same.  The
            # first receipt remains the auditable stored artifact; no rewrite.
            if existing.family is CoreApiSnapshotFamily.COMPOUNDER_PROSPECTIVE_SHADOW and isinstance(existing.payload, CompounderProspectiveBatchReport):
                return ProspectiveWriteOutcome.ALREADY_PRESENT
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        return self._save(value.report_id, value, value.as_of)

    def observations(self) -> tuple[CompounderProspectiveObservation, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, CompounderProspectiveObservation)), key=lambda item: item.observation_id))

    def _save(self, snapshot_id: str, value: object, created_at: datetime) -> ProspectiveWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.COMPOUNDER_PROSPECTIVE_SHADOW and existing.payload == value:
                return ProspectiveWriteOutcome.ALREADY_PRESENT
            raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_IMMUTABILITY_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.COMPOUNDER_PROSPECTIVE_SHADOW, "v1", type(value).__name__, getattr(value, "fingerprint"), _utc(created_at), value))
        return ProspectiveWriteOutcome.INSERTED

    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        result: list[CoreApiSnapshot] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.COMPOUNDER_PROSPECTIVE_SHADOW, limit=100, offset=offset)
            result.extend(page)
            if len(page) < 100:
                return tuple(result)
            offset += len(page)


_REQUIRED_METRIC_KEYS = frozenset({
    (CompounderDerivedMetric.REVENUE_CAGR_3Y, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.REVENUE_CAGR_5Y, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.REVENUE_PERSISTENCE, CompounderDerivedWindow.FULL_AVAILABLE_SERIES),
    (CompounderDerivedMetric.PAT_CAGR_3Y, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.PAT_CAGR_5Y, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.PAT_PERSISTENCE, CompounderDerivedWindow.FULL_AVAILABLE_SERIES),
    (CompounderDerivedMetric.ROE_SUMMARY_3, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.ROE_SUMMARY_5, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.CFO_PAT_CUMULATIVE_3, CompounderDerivedWindow.THREE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.CFO_PAT_CUMULATIVE_5, CompounderDerivedWindow.FIVE_ANNUAL_OBSERVATIONS),
    (CompounderDerivedMetric.CASH_TRAJECTORY, CompounderDerivedWindow.FULL_AVAILABLE_SERIES),
})


def assess_compounder_prospective_readiness(
    *, as_of: datetime, company_type_receipt: PitCompanyTypeClassificationReceipt,
    security_identities: Iterable[NseSessionPointIdentity], facts: Iterable[FinancialFact],
    statement_scope: StatementScope, candidate_grid: CompounderCandidateGridResearchPlan | None = None,
) -> CompounderProspectiveReadiness:
    """Assess one exact issuer/basis without a latest-now query or mutation."""
    cutoff = _utc(as_of)
    all_facts = tuple(facts)
    receipt = company_type_receipt
    receipt.verify()
    instrument, issuer = receipt.canonical_instrument_id, receipt.canonical_issuer_id
    if not isinstance(statement_scope, StatementScope) or statement_scope is StatementScope.UNKNOWN:
        return _readiness(instrument, issuer, None, cutoff, ProspectiveReadinessState.BASIS_MISMATCH, ("EXACT_REPORTING_BASIS_REQUIRED",), None)
    if receipt.evaluated_as_of > cutoff:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.INPUT_AFTER_AS_OF, ("COMPANY_TYPE_AFTER_AS_OF",), None)
    if receipt.state is not PitCompanyTypeClassificationState.CLASSIFIED or receipt.company_type is None:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.COMPANY_TYPE_UNAVAILABLE, ("CLASSIFIED_COMPANY_TYPE_REQUIRED",), None)
    if receipt.company_type is not PitCompanyType.NON_FINANCIAL:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.UNSUPPORTED_COMPANY_TYPE, ("NON_FINANCIAL_REQUIRED",), None)
    if not (_identifier(receipt.issuer_observation_id) and _fingerprint_value(receipt.issuer_observation_fingerprint)):
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.ISSUER_EVIDENCE_UNAVAILABLE, ("EXACT_ISSUER_OBSERVATION_REQUIRED",), None)
    sessions = tuple(
        item for item in security_identities
        if item.fingerprint == nse_session_point_identity_fingerprint(item)
        and item.symbol and item.isin and item.session_date == cutoff.date()
        and item.isin == _isin_for_facts(all_facts, instrument)
    )
    if len(sessions) != 1:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.SECURITY_IDENTITY_UNAVAILABLE, ("EXACT_SESSION_SECURITY_IDENTITY_REQUIRED",), None)
    selected_facts = tuple(item for item in all_facts if item.instrument.instrument_id == instrument)
    if not selected_facts:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.FINANCIAL_FACTS_MISSING, ("CANONICAL_FINANCIAL_FACTS_REQUIRED",), None)
    annual = assess_canonical_annual_facts(selected_facts, canonical_instrument_id=instrument, statement_scope=statement_scope, as_of=cutoff)
    derived = evaluate_compounder_testable_derived_metrics(selected_facts, canonical_instrument_id=instrument, statement_scope=statement_scope, as_of=cutoff)
    conflict = any(item.status.name == "EVIDENCE_CONFLICTED" for item in annual.covers) or any(item.status is CompounderDerivedStatus.EVIDENCE_CONFLICTED for item in derived.receipts)
    if conflict:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.EVIDENCE_CONFLICTED, ("CANONICAL_EVIDENCE_CONFLICTED",), None)
    available = {(item.metric, item.window) for item in derived.receipts if item.status is CompounderDerivedStatus.AVAILABLE}
    unavailable = _REQUIRED_METRIC_KEYS - available
    if unavailable:
        state = ProspectiveReadinessState.METRICS_NON_COMPARABLE if any(item.status.name == "NON_COMPARABLE" for item in derived.receipts if (item.metric, item.window) in unavailable) else ProspectiveReadinessState.METRICS_INCOMPLETE
        return _readiness(instrument, issuer, statement_scope, cutoff, state, tuple(sorted("METRIC_" + metric.value + "_" + window.value for metric, window in unavailable)), None)
    selected_fact_ids = {identifier for cover in annual.covers for identifier in cover.selected_fact_ids}
    selected_known = tuple(item.available_at for item in selected_facts if item.fact_id in selected_fact_ids)
    if not selected_known:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.FINANCIAL_FACTS_MISSING, ("PIT_SELECTED_ANNUAL_FACTS_REQUIRED",), None)
    input_known_at = max((receipt.evaluated_as_of, *selected_known))
    if input_known_at > cutoff:
        return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.INPUT_AFTER_AS_OF, ("INPUT_KNOWN_AFTER_AS_OF",), None)
    plan = candidate_grid or frozen_compounder_candidate_grid_plan()
    policy_versions = tuple(sorted({(item.selection_policy_id or "UNAVAILABLE", item.selection_policy_version or "UNAVAILABLE") for item in annual.covers}))
    values = dict(
        canonical_instrument_id=instrument, isin=sessions[0].isin, canonical_issuer_id=issuer,
        issuer_observation_id=receipt.issuer_observation_id, issuer_observation_fingerprint=receipt.issuer_observation_fingerprint,
        security_identity=sessions[0], company_type_receipt=receipt, as_of=cutoff, input_known_at=_utc(input_known_at),
        statement_scope=statement_scope, annual_facts=annual, derived_metrics=derived,
        candidate_grid_plan_id=plan.plan_id, candidate_grid_fingerprint=plan.fingerprint,
        proposal_id=plan.proposal_id, proposal_version=plan.proposal_version,
        fact_selection_policy_versions=policy_versions, company_type_policy_version=receipt.policy_version,
        actionability="WATCH_ONLY", research_status="RESEARCH_SHADOW", execution_status="NON_EXECUTABLE",
        qualification_status="QUALIFICATION_NOT_EVALUATED",
    )
    identity = "compounder-prospective:" + _hash(_observation_identity_values(values))[:24]
    body = {**values, "observation_id": identity}
    observation = CompounderProspectiveObservation(**body, fingerprint=_fingerprint(_observation_payload_values(body)))
    return _readiness(instrument, issuer, statement_scope, cutoff, ProspectiveReadinessState.PROSPECTIVE_OBSERVATION_READY, (), observation)


def run_compounder_prospective_batch(
    *, as_of: datetime, company_type_receipts: Iterable[PitCompanyTypeClassificationReceipt],
    security_identities: Iterable[NseSessionPointIdentity], facts_for_instrument: Callable[[str], Iterable[FinancialFact]],
    store: CompounderProspectiveShadowStore | None = None,
) -> tuple[CompounderProspectiveBatchReport, tuple[CompounderProspectiveReadiness, ...]]:
    """Evaluate current factual readiness generically; write only ready snapshots."""
    cutoff = _utc(as_of)
    plan = frozen_compounder_candidate_grid_plan()
    if store is not None:
        store.save_plan(plan)
    latest: dict[str, PitCompanyTypeClassificationReceipt] = {}
    for value in company_type_receipts:
        prior = latest.get(value.canonical_instrument_id)
        if value.evaluated_as_of <= cutoff and (
            prior is None or (value.evaluated_as_of, value.receipt_id) > (prior.evaluated_as_of, prior.receipt_id)
        ):
            latest[value.canonical_instrument_id] = value
    non_financial = tuple(sorted((value for value in latest.values() if value.state is PitCompanyTypeClassificationState.CLASSIFIED and value.company_type is PitCompanyType.NON_FINANCIAL), key=lambda value: (value.canonical_issuer_id, value.canonical_instrument_id)))
    readiness: list[CompounderProspectiveReadiness] = []
    inserted = present = 0
    sessions = tuple(security_identities)
    for receipt in non_financial:
        facts = tuple(facts_for_instrument(receipt.canonical_instrument_id))
        scopes = tuple(scope for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE) if any(item.statement_scope is scope for item in facts)) or (None,)
        for scope in scopes:
            if scope is None:
                item = _readiness(receipt.canonical_instrument_id, receipt.canonical_issuer_id, None, cutoff, ProspectiveReadinessState.FINANCIAL_FACTS_MISSING, ("CANONICAL_FINANCIAL_FACTS_REQUIRED",), None)
            else:
                item = assess_compounder_prospective_readiness(as_of=cutoff, company_type_receipt=receipt, security_identities=sessions, facts=facts, statement_scope=scope, candidate_grid=plan)
            readiness.append(item)
            if item.observation is not None and store is not None:
                outcome = store.save_observation(item.observation)
                inserted += outcome is ProspectiveWriteOutcome.INSERTED
                present += outcome is ProspectiveWriteOutcome.ALREADY_PRESENT
    ordered = tuple(sorted(readiness, key=lambda item: (item.canonical_instrument_id, item.statement_scope.value if item.statement_scope else "", item.state.value)))
    counts: dict[str, int] = {}
    for item in ordered:
        if item.state is not ProspectiveReadinessState.PROSPECTIVE_OBSERVATION_READY:
            counts[item.state.value] = counts.get(item.state.value, 0) + 1
    observations = tuple(item.observation for item in ordered if item.observation is not None)
    body = dict(
        as_of=cutoff, non_financial_issuers_considered=len({item.canonical_issuer_id for item in non_financial}), prospective_ready=len(observations),
        consolidated_ready=sum(item.statement_scope is StatementScope.CONSOLIDATED for item in ordered if item.observation), standalone_ready=sum(item.statement_scope is StatementScope.STANDALONE for item in ordered if item.observation),
        observations_inserted=inserted, observations_already_present=present, rejected_by_state=tuple(sorted(counts.items())), observation_ids=tuple(sorted(item.observation_id for item in observations)),
    )
    report = CompounderProspectiveBatchReport(report_id="compounder-prospective-batch:" + _hash(_batch_identity_values(body))[:24], **body, fingerprint=_fingerprint(_batch_payload_values(body | {"report_id": "compounder-prospective-batch:" + _hash(_batch_identity_values(body))[:24]})))
    if store is not None:
        store.save_report(report)
    return report, ordered


def initial_business_outcome_readiness(value: CompounderProspectiveObservation) -> tuple[CompounderBusinessOutcomeReadiness, ...]:
    value.verify()
    return tuple(CompounderBusinessOutcomeReadiness(value.observation_id, value.fingerprint, horizon, BusinessOutcomeMaturity.IMMATURE) for horizon in BusinessOutcomeHorizon)


def market_outcome_readiness(value: CompounderProspectiveObservation) -> CompounderMarketOutcomeReadiness:
    value.verify()
    return CompounderMarketOutcomeReadiness(value.observation_id, value.fingerprint)


def serialize_compounder_prospective_observation(value: CompounderProspectiveObservation) -> str:
    value.verify()
    return json.dumps(_jsonable(_observation_payload(value) | {"fingerprint": value.fingerprint}), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _readiness(instrument, issuer, scope, as_of, state, reasons, observation):
    return CompounderProspectiveReadiness(instrument, issuer, scope, as_of, state, tuple(sorted(set(reasons))), observation)


def _validate_observation(value: CompounderProspectiveObservation) -> None:
    if not all((_identifier(value.canonical_instrument_id), _isin(value.isin), _identifier(value.canonical_issuer_id), _identifier(value.issuer_observation_id), _fingerprint_value(value.issuer_observation_fingerprint), _aware(value.as_of), _aware(value.input_known_at), isinstance(value.statement_scope, StatementScope), value.statement_scope is not StatementScope.UNKNOWN)):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_FIELD_INVALID")
    if not isinstance(value.security_identity, NseSessionPointIdentity) or not isinstance(value.company_type_receipt, PitCompanyTypeClassificationReceipt) or not isinstance(value.annual_facts, CanonicalAnnualFactsReadinessReceipt) or not isinstance(value.derived_metrics, CompounderDerivedResearchEvaluation):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_LINEAGE_INVALID")
    value.company_type_receipt.verify()
    # Re-run the existing nested immutable-contract validators rather than
    # treating their stored fingerprints as sufficient in isolation.  This
    # catches a tampered coverage/metric receipt before its lineage can be
    # relied upon by a prospective observation.
    for cover in value.annual_facts.covers:
        cover.__post_init__()
    value.annual_facts.__post_init__()
    for metric in value.derived_metrics.receipts:
        metric.__post_init__()
    value.derived_metrics.__post_init__()
    if value.security_identity.fingerprint != nse_session_point_identity_fingerprint(value.security_identity):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_SECURITY_LINEAGE_TAMPERED")
    if not (value.security_identity.isin == value.isin and value.company_type_receipt.canonical_instrument_id == value.canonical_instrument_id and value.company_type_receipt.canonical_issuer_id == value.canonical_issuer_id and value.company_type_receipt.company_type is PitCompanyType.NON_FINANCIAL and value.company_type_receipt.state is PitCompanyTypeClassificationState.CLASSIFIED and value.annual_facts.canonical_instrument_id == value.canonical_instrument_id and value.annual_facts.statement_scope is value.statement_scope and value.derived_metrics.canonical_instrument_id == value.canonical_instrument_id and value.derived_metrics.statement_scope is value.statement_scope):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_PROVENANCE_MISMATCH")
    if value.input_known_at > value.as_of or value.company_type_receipt.evaluated_as_of > value.as_of or any(item.available_at > value.as_of for item in _selected_facts(value.annual_facts)):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_AFTER_AS_OF")
    if not (value.candidate_grid_plan_id.startswith("compounder-candidate-grid:") and _fingerprint_value(value.candidate_grid_fingerprint) and value.proposal_id == RESEARCH_PROPOSAL_ID and value.proposal_version == RESEARCH_PROPOSAL_VERSION and value.fact_selection_policy_versions == tuple(sorted(set(value.fact_selection_policy_versions))) and value.company_type_policy_version == value.company_type_receipt.policy_version):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_POLICY_LINEAGE_INVALID")
    if (value.contract_id, value.contract_version, value.actionability, value.research_status, value.execution_status, value.qualification_status) != (CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "RESEARCH_SHADOW", "NON_EXECUTABLE", "QUALIFICATION_NOT_EVALUATED"):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_POSTURE_INVALID")
    keys = {(item.metric, item.window) for item in value.derived_metrics.receipts if item.status is CompounderDerivedStatus.AVAILABLE}
    if not _REQUIRED_METRIC_KEYS <= keys:
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_OBSERVATION_METRICS_INCOMPLETE")


def _selected_facts(value: CanonicalAnnualFactsReadinessReceipt) -> tuple[FinancialFact]:
    # Fact object values are not retained by an annual readiness receipt.  The
    # receipt's as_of and fingerprints are authoritative provenance; this
    # empty helper keeps validation at the constructed receipt boundary.
    return ()


def _isin_for_facts(facts: Iterable[FinancialFact], instrument: str) -> str | None:
    values = {item.instrument.isin for item in facts if item.instrument.instrument_id == instrument and item.instrument.isin}
    return next(iter(values)) if len(values) == 1 else None


def _observation_id(value: CompounderProspectiveObservation) -> str:
    return "compounder-prospective:" + _hash(_observation_identity(value))[:24]


def _observation_identity(value: CompounderProspectiveObservation) -> dict[str, object]:
    return _observation_identity_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"observation_id", "fingerprint"}})


def _observation_identity_values(value: dict[str, object]) -> dict[str, object]:
    return {
        "contract": CONTRACT_VERSION, "instrument": value["canonical_instrument_id"], "isin": value["isin"], "issuer": value["canonical_issuer_id"],
        "issuer_observation": value["issuer_observation_id"], "issuer_fingerprint": value["issuer_observation_fingerprint"],
        "security_receipt": value["security_identity"].receipt_id, "security_fingerprint": value["security_identity"].fingerprint,
        "company_type_receipt": value["company_type_receipt"].receipt_id, "company_type_fingerprint": value["company_type_receipt"].fingerprint,
        "as_of": _time(value["as_of"]), "scope": value["statement_scope"].value, "annual_facts": value["annual_facts"].fingerprint,
        "derived_metrics": value["derived_metrics"].fingerprint, "candidate_grid": value["candidate_grid_fingerprint"],
        "proposal": (value["proposal_id"], value["proposal_version"]), "selector_versions": value["fact_selection_policy_versions"],
        "company_type_policy": value["company_type_policy_version"],
    }


def _observation_payload(value: CompounderProspectiveObservation) -> dict[str, object]:
    return _observation_payload_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _observation_payload_values(value: dict[str, object]) -> dict[str, object]:
    return _observation_identity_values(value) | {
        "observation_id": value["observation_id"], "input_known_at": _time(value["input_known_at"]),
        "annual_fact_ids": tuple(sorted({identifier for cover in value["annual_facts"].covers for identifier in cover.selected_fact_ids})),
        "annual_fact_fingerprints": tuple(sorted({fingerprint for cover in value["annual_facts"].covers for fingerprint in cover.selected_fact_fingerprints})),
        "derived_receipts": tuple(item.fingerprint for item in value["derived_metrics"].receipts),
        "posture": (value["actionability"], value["research_status"], value["execution_status"], value["qualification_status"]),
    }


def _readiness_payload(value: CompounderProspectiveReadiness) -> dict[str, object]:
    return {"instrument": value.canonical_instrument_id, "issuer": value.canonical_issuer_id, "scope": None if value.statement_scope is None else value.statement_scope.value, "as_of": _time(value.as_of), "state": value.state.value, "reasons": value.reasons, "observation": None if value.observation is None else value.observation.fingerprint}


def _batch_identity_values(value: dict[str, object]) -> dict[str, object]:
    return {"contract": CONTRACT_VERSION, "as_of": _time(value["as_of"]), "observation_ids": value["observation_ids"], "rejections": value["rejected_by_state"]}


def _batch_payload(value: CompounderProspectiveBatchReport) -> dict[str, object]:
    return _batch_payload_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "contract_id", "contract_version"}})


def _batch_payload_values(value: dict[str, object]) -> dict[str, object]:
    return _batch_identity_values(value) | {"report_id": value["report_id"], "non_financial_issuers_considered": value["non_financial_issuers_considered"], "prospective_ready": value["prospective_ready"], "consolidated_ready": value["consolidated_ready"], "standalone_ready": value["standalone_ready"], "observations_inserted": value["observations_inserted"], "observations_already_present": value["observations_already_present"]}


def _plan_payload(value: CompounderCandidateGridResearchPlan) -> dict[str, object]:
    return _plan_payload_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name not in {"fingerprint", "contract_id", "contract_version"}})


def _plan_payload_values(value: dict[str, object]) -> dict[str, object]:
    return {"plan_id": value["plan_id"], "proposal": (value["proposal_id"], value["proposal_version"]), "values": value["research_values"], "state": value["state"], "contract": CONTRACT_VERSION}


def _canonical_pairs(value: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    # Individual values retain their explicitly frozen research-plan ordering;
    # only the named dimensions are canonicalized for serialization.
    if not value or any(not _identifier(key) or not items or len(set(items)) != len(items) for key, items in value):
        return ()
    return tuple(sorted(value))


def _canonical_counts(value: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
    if any(not _identifier(key) or not isinstance(count, int) or count < 0 for key, count in value):
        return ()
    return tuple(sorted(value))


def _identifier(value: object) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _isin(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"INE[A-Z0-9]{9}", value) is not None


def _fingerprint_value(value: object) -> bool:
    return isinstance(value, str) and _FP.fullmatch(value) is not None


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise CompounderProspectiveShadowError("COMPOUNDER_PROSPECTIVE_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


def _time(value: datetime) -> str:
    return _utc(value).isoformat()


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _fingerprint(value: object) -> str:
    return "sha256:" + _hash(value)


def _jsonable(value: object):
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return _time(value)
    if isinstance(value, tuple): return tuple(_jsonable(item) for item in value)
    if isinstance(value, dict): return {str(key): _jsonable(item) for key, item in value.items()}
    return value


__all__ = (
    "BusinessOutcomeHorizon", "BusinessOutcomeMaturity", "CompounderBusinessOutcomeReadiness",
    "CompounderCandidateGridResearchPlan", "CompounderMarketOutcomeReadiness", "CompounderProspectiveBatchReport",
    "CompounderProspectiveObservation", "CompounderProspectiveReadiness", "CompounderProspectiveShadowStore",
    "MarketOutcomeReadiness", "ProspectiveReadinessState", "ProspectiveWriteOutcome", "assess_compounder_prospective_readiness",
    "frozen_compounder_candidate_grid_plan", "initial_business_outcome_readiness", "market_outcome_readiness",
    "run_compounder_prospective_batch", "serialize_compounder_prospective_observation",
)
