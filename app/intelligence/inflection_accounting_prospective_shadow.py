"""Forward-only, accounting-only Fundamental Inflection research ledger.

This composes the existing PIT quarterly acceleration receipts.  It does not
interpret an acceleration, estimate a market reaction, qualify an issuer, or
access portfolio, price, API, broker, order, or runtime-clock facilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
import re
from typing import Callable, Iterable

from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling
from app.fundamentals.financial_metric_observation_schema import FinancialMetricPeriodIdentity
from app.fundamentals.models import FinancialFact, FinancialPeriodType, StatementScope
from app.historical.pit_company_type_classification_activation import (
    PitCompanyType, PitCompanyTypeClassificationReceipt, PitCompanyTypeClassificationState,
)
from app.intelligence.inflection_testable_derived_metrics_and_event_alignment import (
    InflectionDerivedMetricsEvaluation, InflectionDerivedMetricsReceipt,
    InflectionDerivedMetricsState, InflectionResearchMetric,
    evaluate_inflection_testable_derived_metrics_and_event_alignment,
)
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository,
)


CONTRACT_ID = "inflection-accounting-prospective-shadow"
CONTRACT_VERSION = "v1"
PROPOSAL_ID = "FUNDAMENTAL_INFLECTION_POLICY_RESEARCH_PROPOSAL_V1"
PROPOSAL_VERSION = "v1"
# This contract begins prospectively at its recorded activation boundary.  It
# is a static governance datum, never a lookup of the machine clock.
PROSPECTIVE_LEDGER_ACTIVATED_AT = datetime(2026, 9, 4, tzinfo=UTC)
_ID = re.compile(r"[A-Za-z0-9._:-]+\Z")
_ISIN = re.compile(r"INE[A-Z0-9]{9}\Z")
_FP = re.compile(r"sha256:[0-9a-f]{64}\Z")


class InflectionAccountingProspectiveShadowError(ValueError):
    """Stable fail-closed error at the accounting-only ledger boundary."""


class InflectionAccountingObservationState(StrEnum):
    ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE = "ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE"
    ACCOUNTING_INFLECTION_NON_COMPARABLE = "ACCOUNTING_INFLECTION_NON_COMPARABLE"


class InflectionAccountingReadinessState(StrEnum):
    OBSERVATION_READY = "OBSERVATION_READY"
    COMPANY_TYPE_EXCLUDED = "COMPANY_TYPE_EXCLUDED"
    COMPANY_TYPE_CONFLICTED = "COMPANY_TYPE_CONFLICTED"
    FINANCIAL_FACTS_MISSING = "FINANCIAL_FACTS_MISSING"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    BASIS_MISMATCH = "BASIS_MISMATCH"
    INPUT_AFTER_AS_OF = "INPUT_AFTER_AS_OF"


class InflectionAccountingReason(StrEnum):
    NON_FINANCIAL_COMPANY_TYPE_REQUIRED = "NON_FINANCIAL_COMPANY_TYPE_REQUIRED"
    COMPANY_TYPE_RECEIPT_CONFLICTED = "COMPANY_TYPE_RECEIPT_CONFLICTED"
    COMPANY_TYPE_AFTER_AS_OF = "COMPANY_TYPE_AFTER_AS_OF"
    CANONICAL_QUARTERLY_FACTS_REQUIRED = "CANONICAL_QUARTERLY_FACTS_REQUIRED"
    REVENUE_ACCELERATION_NOT_READY = "REVENUE_ACCELERATION_NOT_READY"
    PAT_ACCELERATION_NOT_READY = "PAT_ACCELERATION_NOT_READY"
    METRIC_EVIDENCE_CONFLICTED = "METRIC_EVIDENCE_CONFLICTED"
    PERIOD_ALIGNMENT_MISMATCH = "PERIOD_ALIGNMENT_MISMATCH"
    EXACT_REPORTING_BASIS_REQUIRED = "EXACT_REPORTING_BASIS_REQUIRED"


class ExactIntradayEventTimeState(StrEnum):
    EXACT_INTRADAY_EVENT_TIME_UNAVAILABLE = "EXACT_INTRADAY_EVENT_TIME_UNAVAILABLE"


class AccountingOutcomeMaturity(StrEnum):
    IMMATURE = "IMMATURE"
    PARTIALLY_MATURE = "PARTIALLY_MATURE"
    MATURE = "MATURE"
    DATA_MISSING = "DATA_MISSING"
    NON_COMPARABLE = "NON_COMPARABLE"


class InflectionProspectiveWriteOutcome(StrEnum):
    INSERTED = "INSERTED"
    ALREADY_PRESENT = "ALREADY_PRESENT"


@dataclass(frozen=True, slots=True)
class InflectionAccountingCandidateGridPlan:
    """Frozen anti-hindsight lineage; its windows are never evaluated here."""
    plan_id: str
    proposal_id: str
    proposal_version: str
    persistence_windows: tuple[str, ...]
    blocked_dimensions: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not (
            _identifier(self.plan_id)
            and (self.proposal_id, self.proposal_version) == (PROPOSAL_ID, PROPOSAL_VERSION)
            and self.persistence_windows == ("ONE_QUARTER", "TWO_CONSECUTIVE_QUARTERS", "THREE_CONSECUTIVE_QUARTERS")
            and self.blocked_dimensions == ("CANONICAL_CONSENSUS_DATA_MISSING", "CANONICAL_GUIDANCE_DATA_MISSING", "INFLECTION_MARKET_REACTION_NOT_ACTIVE", "REVISION_DATA_MISSING")
            and self.fingerprint == _fingerprint(_plan_payload(self))
            and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)
        ):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_GRID_PLAN_INVALID")

    def verify(self) -> None: self.__post_init__()


def frozen_inflection_accounting_candidate_grid_plan() -> InflectionAccountingCandidateGridPlan:
    values = dict(
        proposal_id=PROPOSAL_ID, proposal_version=PROPOSAL_VERSION,
        persistence_windows=("ONE_QUARTER", "TWO_CONSECUTIVE_QUARTERS", "THREE_CONSECUTIVE_QUARTERS"),
        blocked_dimensions=("CANONICAL_CONSENSUS_DATA_MISSING", "CANONICAL_GUIDANCE_DATA_MISSING", "INFLECTION_MARKET_REACTION_NOT_ACTIVE", "REVISION_DATA_MISSING"),
    )
    plan_id = "inflection-accounting-grid:" + _hash(values)[:24]
    return InflectionAccountingCandidateGridPlan(plan_id=plan_id, **values, fingerprint=_fingerprint(_plan_payload_values(values | {"plan_id": plan_id})))


@dataclass(frozen=True, slots=True)
class InflectionAccountingProspectiveObservation:
    """One immutable factual issuer-quarter observation, never a candidate."""
    observation_id: str
    canonical_instrument_id: str
    canonical_issuer_id: str
    isin: str | None
    company_type_receipt: PitCompanyTypeClassificationReceipt
    statement_scope: StatementScope
    current_quarter: FinancialMetricPeriodIdentity
    as_of: datetime
    revenue: InflectionDerivedMetricsReceipt
    pat: InflectionDerivedMetricsReceipt
    observation_state: InflectionAccountingObservationState
    candidate_grid_plan_id: str
    candidate_grid_fingerprint: str
    proposal_id: str
    proposal_version: str
    exact_intraday_event_time: ExactIntradayEventTimeState
    provenance: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_SHADOW"
    qualification_status: str = "QUALIFICATION_NOT_EVALUATED"

    def __post_init__(self) -> None:
        _validate_observation(self)
        if self.observation_id != _observation_id(self):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_OBSERVATION_IDENTITY_MISMATCH")
        if self.fingerprint != _fingerprint(_observation_payload(self)):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_OBSERVATION_FINGERPRINT_MISMATCH")

    def verify(self) -> None: self.__post_init__()


@dataclass(frozen=True, slots=True)
class InflectionAccountingOutcome:
    """A linked future accounting outcome; initial outcomes contain no future fact."""
    outcome_id: str
    observation_id: str
    observation_fingerprint: str
    as_of: datetime
    maturity: AccountingOutcomeMaturity
    future_metric_receipt_fingerprints: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_SHADOW"

    def __post_init__(self) -> None:
        if not (_identifier(self.observation_id) and _fingerprint_value(self.observation_fingerprint) and _aware(self.as_of)
                and self.future_metric_receipt_fingerprints == tuple(sorted(set(self.future_metric_receipt_fingerprints)))
                and all(_fingerprint_value(item) for item in self.future_metric_receipt_fingerprints)
                and (self.contract_id, self.contract_version, self.actionability, self.execution_status, self.research_status) == (CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_SHADOW")):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_OUTCOME_INVALID")
        if self.maturity is AccountingOutcomeMaturity.IMMATURE and self.future_metric_receipt_fingerprints:
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_IMMATURE_OUTCOME_FABRICATION_FORBIDDEN")
        if self.maturity is not AccountingOutcomeMaturity.IMMATURE and not self.future_metric_receipt_fingerprints:
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_MATURE_OUTCOME_LINEAGE_REQUIRED")
        if self.outcome_id != _outcome_id(self) or self.fingerprint != _fingerprint(_outcome_payload(self)):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_OUTCOME_FINGERPRINT_MISMATCH")

    def verify(self) -> None: self.__post_init__()


def initial_inflection_accounting_outcome(value: InflectionAccountingProspectiveObservation) -> InflectionAccountingOutcome:
    value.verify()
    values = dict(observation_id=value.observation_id, observation_fingerprint=value.fingerprint, as_of=value.as_of,
                  maturity=AccountingOutcomeMaturity.IMMATURE, future_metric_receipt_fingerprints=())
    outcome_id = "inflection-accounting-outcome:" + _hash(_outcome_identity_values(values))[:24]
    return InflectionAccountingOutcome(outcome_id=outcome_id, **values, fingerprint=_fingerprint(_outcome_payload_values(values | {"outcome_id": outcome_id})))


@dataclass(frozen=True, slots=True)
class InflectionAccountingReadiness:
    canonical_instrument_id: str
    canonical_issuer_id: str
    statement_scope: StatementScope | None
    as_of: datetime
    state: InflectionAccountingReadinessState
    reasons: tuple[InflectionAccountingReason, ...]
    observation: InflectionAccountingProspectiveObservation | None
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not (_identifier(self.canonical_instrument_id) and _identifier(self.canonical_issuer_id) and _aware(self.as_of)
                and self.reasons == tuple(sorted(set(self.reasons), key=lambda item: item.value))
                and all(isinstance(item, InflectionAccountingReason) for item in self.reasons)
                and (self.state is InflectionAccountingReadinessState.OBSERVATION_READY) == (self.observation is not None)):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_READINESS_INVALID")
        if self.observation is not None and (self.observation.canonical_instrument_id != self.canonical_instrument_id
                                             or self.observation.canonical_issuer_id != self.canonical_issuer_id
                                             or self.observation.statement_scope is not self.statement_scope):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_READINESS_OBSERVATION_MISMATCH")
        object.__setattr__(self, "fingerprint", _fingerprint(_readiness_payload(self)))


@dataclass(frozen=True, slots=True)
class InflectionAccountingProspectiveBatchReport:
    report_id: str
    as_of: datetime
    non_financial_issuers_considered: int
    issuers_with_quarterly_facts: int
    revenue_acceleration_ready: int
    pat_acceleration_ready: int
    both_acceleration_ready: int
    special_state_observations: int
    observations_inserted: int
    observations_already_present: int
    outcomes_inserted: int
    outcomes_already_present: int
    rejected_by_state: tuple[tuple[str, int], ...]
    observation_ids: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        numbers = (self.non_financial_issuers_considered, self.issuers_with_quarterly_facts, self.revenue_acceleration_ready,
                   self.pat_acceleration_ready, self.both_acceleration_ready, self.special_state_observations,
                   self.observations_inserted, self.observations_already_present, self.outcomes_inserted, self.outcomes_already_present)
        if not (_identifier(self.report_id) and _aware(self.as_of) and min(numbers) >= 0
                and self.rejected_by_state == _canonical_counts(self.rejected_by_state)
                and self.observation_ids == tuple(sorted(set(self.observation_ids)))
                and self.fingerprint == _fingerprint(_report_payload(self))
                and (self.contract_id, self.contract_version) == (CONTRACT_ID, CONTRACT_VERSION)):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_BATCH_REPORT_INVALID")


class InflectionAccountingProspectiveStore:
    """Dedicated insert-only snapshots; no fact or filing is ever modified."""
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository

    def save_plan(self, value: InflectionAccountingCandidateGridPlan) -> InflectionProspectiveWriteOutcome:
        value.verify(); return self._save("inflection-accounting-plan:" + value.plan_id, value, datetime(1970, 1, 1, tzinfo=UTC))
    def save_observation(self, value: InflectionAccountingProspectiveObservation) -> InflectionProspectiveWriteOutcome:
        value.verify()
        if value.as_of < PROSPECTIVE_LEDGER_ACTIVATED_AT:
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_HISTORICAL_BACKDATING_FORBIDDEN")
        return self._save(value.observation_id, value, value.as_of)
    def save_outcome(self, value: InflectionAccountingOutcome) -> InflectionProspectiveWriteOutcome:
        value.verify(); return self._save(value.outcome_id, value, value.as_of)
    def save_report(self, value: InflectionAccountingProspectiveBatchReport) -> InflectionProspectiveWriteOutcome:
        existing = self._repository.get_snapshot(value.report_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW and isinstance(existing.payload, InflectionAccountingProspectiveBatchReport):
                return InflectionProspectiveWriteOutcome.ALREADY_PRESENT
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_IMMUTABILITY_CONFLICT")
        return self._save(value.report_id, value, value.as_of)
    def observations(self) -> tuple[InflectionAccountingProspectiveObservation, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, InflectionAccountingProspectiveObservation)), key=lambda item: item.observation_id))
    def outcomes(self) -> tuple[InflectionAccountingOutcome, ...]:
        return tuple(sorted((item.payload for item in self._all() if isinstance(item.payload, InflectionAccountingOutcome)), key=lambda item: item.outcome_id))
    def _save(self, snapshot_id: str, value: object, created_at: datetime) -> InflectionProspectiveWriteOutcome:
        existing = self._repository.get_snapshot(snapshot_id)
        if existing is not None:
            if existing.family is CoreApiSnapshotFamily.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW and existing.payload == value:
                return InflectionProspectiveWriteOutcome.ALREADY_PRESENT
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_IMMUTABILITY_CONFLICT")
        self._repository.save_snapshot(CoreApiSnapshot(snapshot_id, CoreApiSnapshotFamily.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW,
            "v1", type(value).__name__, getattr(value, "fingerprint"), _utc(created_at), value))
        return InflectionProspectiveWriteOutcome.INSERTED
    def _all(self) -> tuple[CoreApiSnapshot, ...]:
        values: list[CoreApiSnapshot] = []; offset = 0
        while True:
            page = self._repository.list_snapshots(CoreApiSnapshotFamily.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW, limit=100, offset=offset)
            values.extend(page)
            if len(page) < 100: return tuple(values)
            offset += len(page)


def assess_inflection_accounting_prospective_readiness(*, evaluation: InflectionDerivedMetricsEvaluation,
                                                       company_type_receipt: PitCompanyTypeClassificationReceipt,
                                                       candidate_grid: InflectionAccountingCandidateGridPlan) -> InflectionAccountingReadiness:
    """Admit an immutable observation only from an explicit, PIT-safe receipt."""
    evaluation.verify(); company_type_receipt.verify(); candidate_grid.verify()
    cutoff = _utc(evaluation.as_of)
    if company_type_receipt.evaluated_as_of > cutoff:
        return _readiness(evaluation, InflectionAccountingReadinessState.INPUT_AFTER_AS_OF, (InflectionAccountingReason.COMPANY_TYPE_AFTER_AS_OF,), None)
    if company_type_receipt.state is not PitCompanyTypeClassificationState.CLASSIFIED or company_type_receipt.company_type is not PitCompanyType.NON_FINANCIAL:
        return _readiness(evaluation, InflectionAccountingReadinessState.COMPANY_TYPE_EXCLUDED, (InflectionAccountingReason.NON_FINANCIAL_COMPANY_TYPE_REQUIRED,), None)
    by_metric = {item.metric: item for item in evaluation.receipts}
    revenue, pat = by_metric[InflectionResearchMetric.REVENUE], by_metric[InflectionResearchMetric.PAT]
    if any(item.state is InflectionDerivedMetricsState.EVIDENCE_CONFLICTED for item in (revenue, pat)):
        return _readiness(evaluation, InflectionAccountingReadinessState.EVIDENCE_CONFLICTED, (InflectionAccountingReason.METRIC_EVIDENCE_CONFLICTED,), None)
    usable = tuple(item for item in (revenue, pat) if item.state in {InflectionDerivedMetricsState.ACCELERATION_OBSERVED, InflectionDerivedMetricsState.NON_COMPARABLE})
    if not usable:
        reasons = tuple(sorted({InflectionAccountingReason.REVENUE_ACCELERATION_NOT_READY if revenue.state is not InflectionDerivedMetricsState.ACCELERATION_OBSERVED else InflectionAccountingReason.PAT_ACCELERATION_NOT_READY,
                                InflectionAccountingReason.PAT_ACCELERATION_NOT_READY if pat.state is not InflectionDerivedMetricsState.ACCELERATION_OBSERVED else InflectionAccountingReason.REVENUE_ACCELERATION_NOT_READY}, key=lambda item: item.value))
        return _readiness(evaluation, InflectionAccountingReadinessState.DATA_INSUFFICIENT, reasons, None)
    periods = {item.current_period.fingerprint: item.current_period for item in usable if item.current_period is not None}
    if len(periods) != 1:
        return _readiness(evaluation, InflectionAccountingReadinessState.BASIS_MISMATCH, (InflectionAccountingReason.PERIOD_ALIGNMENT_MISMATCH,), None)
    current = next(iter(periods.values()))
    values = dict(canonical_instrument_id=evaluation.canonical_instrument_id, canonical_issuer_id=evaluation.canonical_issuer_id,
                  isin=_isin(evaluation.canonical_instrument_id), company_type_receipt=company_type_receipt,
                  statement_scope=evaluation.statement_scope, current_quarter=current, as_of=cutoff,
                  revenue=revenue, pat=pat,
                  observation_state=(InflectionAccountingObservationState.ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE
                                     if any(item.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in usable)
                                     else InflectionAccountingObservationState.ACCOUNTING_INFLECTION_NON_COMPARABLE),
                  candidate_grid_plan_id=candidate_grid.plan_id, candidate_grid_fingerprint=candidate_grid.fingerprint,
                  proposal_id=PROPOSAL_ID, proposal_version=PROPOSAL_VERSION,
                  exact_intraday_event_time=ExactIntradayEventTimeState.EXACT_INTRADAY_EVENT_TIME_UNAVAILABLE,
                  provenance=("MARKET_EVENT_TIME_UNRESOLVED", "PIT_QUARTERLY_FACTS", "REVENUE_PAT_ACCELERATION", "REVENUE_PAT_YOY"))
    observation_id = "inflection-accounting-prospective:" + _hash(_observation_identity_values(values))[:24]
    observation = InflectionAccountingProspectiveObservation(observation_id=observation_id, **values,
        fingerprint=_fingerprint(_observation_payload_values(values | {"observation_id": observation_id})))
    return _readiness(evaluation, InflectionAccountingReadinessState.OBSERVATION_READY, (), observation)


def run_inflection_accounting_prospective_batch(*, as_of: datetime,
    company_type_receipts: Iterable[PitCompanyTypeClassificationReceipt], facts_for_instrument: Callable[[str], Iterable[FinancialFact]],
    filings_for_instrument: Callable[[str], Iterable[CorporateFiling]], store: InflectionAccountingProspectiveStore | None = None,
) -> tuple[InflectionAccountingProspectiveBatchReport, tuple[InflectionAccountingReadiness, ...]]:
    """Run a bounded explicit-cutoff ledger pass; it never manufactures history."""
    cutoff = _utc(as_of); plan = frozen_inflection_accounting_candidate_grid_plan()
    if cutoff < PROSPECTIVE_LEDGER_ACTIVATED_AT:
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_HISTORICAL_BACKDATING_FORBIDDEN")
    if store is not None: store.save_plan(plan)
    receipts, conflicted = _latest_receipts(company_type_receipts, cutoff)
    readiness: list[InflectionAccountingReadiness] = []; inserted = present = outcome_inserted = outcome_present = 0
    for receipt in receipts:
        if receipt.company_type is not PitCompanyType.NON_FINANCIAL or receipt.state is not PitCompanyTypeClassificationState.CLASSIFIED:
            readiness.append(InflectionAccountingReadiness(receipt.canonical_instrument_id, receipt.canonical_issuer_id, None, cutoff,
                InflectionAccountingReadinessState.COMPANY_TYPE_EXCLUDED, (InflectionAccountingReason.NON_FINANCIAL_COMPANY_TYPE_REQUIRED,), None)); continue
        if receipt.canonical_instrument_id in conflicted:
            readiness.append(InflectionAccountingReadiness(receipt.canonical_instrument_id, receipt.canonical_issuer_id, None, cutoff,
                InflectionAccountingReadinessState.COMPANY_TYPE_CONFLICTED, (InflectionAccountingReason.COMPANY_TYPE_RECEIPT_CONFLICTED,), None)); continue
        facts = tuple(facts_for_instrument(receipt.canonical_instrument_id))
        scopes = tuple(scope for scope in (StatementScope.CONSOLIDATED, StatementScope.STANDALONE) if _quarterly_scope_present(facts, scope))
        if not scopes:
            readiness.append(InflectionAccountingReadiness(receipt.canonical_instrument_id, receipt.canonical_issuer_id, None, cutoff,
                InflectionAccountingReadinessState.FINANCIAL_FACTS_MISSING, (InflectionAccountingReason.CANONICAL_QUARTERLY_FACTS_REQUIRED,), None)); continue
        filings = tuple(filings_for_instrument(receipt.canonical_instrument_id))
        for scope in scopes:
            evaluation = evaluate_inflection_testable_derived_metrics_and_event_alignment(facts=facts, filings=filings,
                company_type_receipt=receipt, statement_scope=scope, as_of=cutoff, calendar=None)
            item = assess_inflection_accounting_prospective_readiness(evaluation=evaluation, company_type_receipt=receipt, candidate_grid=plan)
            readiness.append(item)
            if item.observation is not None and store is not None:
                outcome = store.save_observation(item.observation); inserted += outcome is InflectionProspectiveWriteOutcome.INSERTED; present += outcome is InflectionProspectiveWriteOutcome.ALREADY_PRESENT
                initial = store.save_outcome(initial_inflection_accounting_outcome(item.observation)); outcome_inserted += initial is InflectionProspectiveWriteOutcome.INSERTED; outcome_present += initial is InflectionProspectiveWriteOutcome.ALREADY_PRESENT
    ordered = tuple(sorted(readiness, key=lambda item: (item.canonical_instrument_id, item.statement_scope.value if item.statement_scope else "", item.state.value)))
    observations = tuple(item.observation for item in ordered if item.observation is not None)
    revenue_ready = sum(item.observation is not None and item.observation.revenue.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in ordered)
    pat_ready = sum(item.observation is not None and item.observation.pat.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in ordered)
    body = dict(as_of=cutoff, non_financial_issuers_considered=len({value.canonical_issuer_id for value in receipts if value.company_type is PitCompanyType.NON_FINANCIAL and value.state is PitCompanyTypeClassificationState.CLASSIFIED}),
        issuers_with_quarterly_facts=len({item.canonical_issuer_id for item in ordered if item.statement_scope is not None}), revenue_acceleration_ready=revenue_ready, pat_acceleration_ready=pat_ready,
        both_acceleration_ready=sum(item.observation is not None and item.observation.revenue.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED and item.observation.pat.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in ordered),
        special_state_observations=sum(item.observation is not None and item.observation.observation_state is InflectionAccountingObservationState.ACCOUNTING_INFLECTION_NON_COMPARABLE for item in ordered),
        observations_inserted=inserted, observations_already_present=present, outcomes_inserted=outcome_inserted, outcomes_already_present=outcome_present,
        rejected_by_state=_canonical_counts(tuple((state.value, sum(item.state is state for item in ordered)) for state in InflectionAccountingReadinessState if state is not InflectionAccountingReadinessState.OBSERVATION_READY and any(item.state is state for item in ordered))),
        observation_ids=tuple(sorted(item.observation_id for item in observations)))
    report_id = "inflection-accounting-batch:" + _hash(_report_identity_values(body))[:24]
    report = InflectionAccountingProspectiveBatchReport(report_id=report_id, **body, fingerprint=_fingerprint(_report_payload_values(body | {"report_id": report_id})))
    if store is not None: store.save_report(report)
    return report, ordered


def serialize_inflection_accounting_observation(value: InflectionAccountingProspectiveObservation) -> str:
    value.verify(); return json.dumps(_jsonable(_observation_payload(value) | {"fingerprint": value.fingerprint}), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _latest_receipts(values: Iterable[PitCompanyTypeClassificationReceipt], cutoff: datetime) -> tuple[tuple[PitCompanyTypeClassificationReceipt, ...], frozenset[str]]:
    grouped: dict[str, list[PitCompanyTypeClassificationReceipt]] = {}
    for value in values:
        value.verify()
        if value.evaluated_as_of <= cutoff: grouped.setdefault(value.canonical_instrument_id, []).append(value)
    selected: list[PitCompanyTypeClassificationReceipt] = []; conflicted: set[str] = set()
    for instrument, items in grouped.items():
        latest_time = max(item.evaluated_as_of for item in items); latest = tuple(sorted((item for item in items if item.evaluated_as_of == latest_time), key=lambda item: item.receipt_id))
        if len({item.fingerprint for item in latest}) > 1: conflicted.add(instrument)
        selected.append(latest[0])
    return tuple(sorted(selected, key=lambda item: item.canonical_instrument_id)), frozenset(conflicted)


def _quarterly_scope_present(facts: tuple[FinancialFact, ...], scope: StatementScope) -> bool:
    return any(item.period_type is FinancialPeriodType.QUARTERLY and item.statement_scope is scope and item.fact_kind is FundamentalFactKind.REPORTED and item.metric.value in {"REVENUE", "PAT"} for item in facts)


def _readiness(evaluation: InflectionDerivedMetricsEvaluation, state: InflectionAccountingReadinessState,
               reasons: tuple[InflectionAccountingReason, ...], observation: InflectionAccountingProspectiveObservation | None) -> InflectionAccountingReadiness:
    return InflectionAccountingReadiness(evaluation.canonical_instrument_id, evaluation.canonical_issuer_id, evaluation.statement_scope, evaluation.as_of, state, tuple(sorted(set(reasons), key=lambda item: item.value)), observation)


def _validate_observation(value: InflectionAccountingProspectiveObservation) -> None:
    if not (_identifier(value.observation_id) and _identifier(value.canonical_instrument_id) and _identifier(value.canonical_issuer_id)
            and (value.isin is None or _ISIN.fullmatch(value.isin)) and _aware(value.as_of)
            and isinstance(value.statement_scope, StatementScope) and value.statement_scope is not StatementScope.UNKNOWN
            and isinstance(value.current_quarter, FinancialMetricPeriodIdentity) and isinstance(value.observation_state, InflectionAccountingObservationState)
            and isinstance(value.exact_intraday_event_time, ExactIntradayEventTimeState)
            and value.provenance == tuple(sorted(set(value.provenance))) and value.provenance
            and (value.proposal_id, value.proposal_version) == (PROPOSAL_ID, PROPOSAL_VERSION)
            and _identifier(value.candidate_grid_plan_id) and _fingerprint_value(value.candidate_grid_fingerprint)
            and (value.contract_id, value.contract_version, value.actionability, value.execution_status, value.research_status, value.qualification_status) == (CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_SHADOW", "QUALIFICATION_NOT_EVALUATED")):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_OBSERVATION_INVALID")
    value.company_type_receipt.verify(); value.revenue.verify(); value.pat.verify(); value.current_quarter.__post_init__()
    plan = frozen_inflection_accounting_candidate_grid_plan(); plan.verify()
    if (value.candidate_grid_plan_id, value.candidate_grid_fingerprint) != (plan.plan_id, plan.fingerprint):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_GRID_PLAN_LINEAGE_INVALID")
    if not (value.company_type_receipt.company_type is PitCompanyType.NON_FINANCIAL and value.company_type_receipt.state is PitCompanyTypeClassificationState.CLASSIFIED
            and value.company_type_receipt.canonical_instrument_id == value.canonical_instrument_id and value.company_type_receipt.canonical_issuer_id == value.canonical_issuer_id
            and value.company_type_receipt.evaluated_as_of <= value.as_of):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_COMPANY_TYPE_LINEAGE_INVALID")
    for receipt, metric in ((value.revenue, InflectionResearchMetric.REVENUE), (value.pat, InflectionResearchMetric.PAT)):
        if not (receipt.metric is metric and receipt.canonical_instrument_id == value.canonical_instrument_id and receipt.canonical_issuer_id == value.canonical_issuer_id
                and receipt.statement_scope is value.statement_scope and receipt.as_of == value.as_of and receipt.company_type_receipt_id == value.company_type_receipt.receipt_id
                and receipt.company_type_receipt_fingerprint == value.company_type_receipt.fingerprint):
            raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_METRIC_LINEAGE_INVALID")
    usable = tuple(item for item in (value.revenue, value.pat) if item.state in {InflectionDerivedMetricsState.ACCELERATION_OBSERVED, InflectionDerivedMetricsState.NON_COMPARABLE})
    if not usable or any(item.current_period is None or item.current_period.fingerprint != value.current_quarter.fingerprint for item in usable):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_PERIOD_LINEAGE_INVALID")
    if value.observation_state is InflectionAccountingObservationState.ACCOUNTING_INFLECTION_OBSERVATION_AVAILABLE and not any(item.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in usable):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_AVAILABLE_STATE_INVALID")
    if value.observation_state is InflectionAccountingObservationState.ACCOUNTING_INFLECTION_NON_COMPARABLE and any(item.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED for item in usable):
        raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_NON_COMPARABLE_STATE_INVALID")


def _observation_id(value: InflectionAccountingProspectiveObservation) -> str: return "inflection-accounting-prospective:" + _hash(_observation_identity(value))[:24]
def _outcome_id(value: InflectionAccountingOutcome) -> str: return "inflection-accounting-outcome:" + _hash(_outcome_identity(value))[:24]
def _observation_identity(value: InflectionAccountingProspectiveObservation) -> dict[str, object]: return _observation_identity_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key not in {"observation_id", "fingerprint"}})
def _observation_identity_values(value: dict[str, object]) -> dict[str, object]:
    return {"contract": CONTRACT_VERSION, "instrument": value["canonical_instrument_id"], "issuer": value["canonical_issuer_id"], "isin": value["isin"], "company_type": value["company_type_receipt"].fingerprint, "scope": value["statement_scope"].value, "quarter": value["current_quarter"].fingerprint, "as_of": _time(value["as_of"]), "revenue": value["revenue"].fingerprint, "pat": value["pat"].fingerprint, "plan": value["candidate_grid_fingerprint"], "proposal": (value["proposal_id"], value["proposal_version"])}
def _observation_payload(value: InflectionAccountingProspectiveObservation) -> dict[str, object]: return _observation_payload_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key != "fingerprint"})
def _observation_payload_values(value: dict[str, object]) -> dict[str, object]:
    return _observation_identity_values(value) | {"observation_id": value["observation_id"], "state": value["observation_state"].value, "revenue_fact_lineage": tuple((item.fact_id, item.fact_fingerprint) for item in value["revenue"].input_facts), "pat_fact_lineage": tuple((item.fact_id, item.fact_fingerprint) for item in value["pat"].input_facts), "revenue_acceleration": None if value["revenue"].acceleration is None else str(value["revenue"].acceleration), "pat_acceleration": None if value["pat"].acceleration is None else str(value["pat"].acceleration), "exact_intraday_event_time": value["exact_intraday_event_time"].value, "provenance": value["provenance"], "posture": (value.get("actionability", "WATCH_ONLY"), value.get("execution_status", "NON_EXECUTABLE"), value.get("research_status", "RESEARCH_SHADOW"), value.get("qualification_status", "QUALIFICATION_NOT_EVALUATED"))}
def _outcome_identity(value: InflectionAccountingOutcome) -> dict[str, object]: return _outcome_identity_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key not in {"outcome_id", "fingerprint"}})
def _outcome_identity_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_VERSION, "observation": value["observation_id"], "observation_fingerprint": value["observation_fingerprint"], "as_of": _time(value["as_of"]), "maturity": value["maturity"].value, "future": value["future_metric_receipt_fingerprints"]}
def _outcome_payload(value: InflectionAccountingOutcome) -> dict[str, object]: return _outcome_payload_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key != "fingerprint"})
def _outcome_payload_values(value: dict[str, object]) -> dict[str, object]: return _outcome_identity_values(value) | {"outcome_id": value["outcome_id"], "posture": (value.get("actionability", "WATCH_ONLY"), value.get("execution_status", "NON_EXECUTABLE"), value.get("research_status", "RESEARCH_SHADOW"))}
def _readiness_payload(value: InflectionAccountingReadiness) -> dict[str, object]: return {"instrument": value.canonical_instrument_id, "issuer": value.canonical_issuer_id, "scope": value.statement_scope.value if value.statement_scope else None, "as_of": _time(value.as_of), "state": value.state.value, "reasons": tuple(item.value for item in value.reasons), "observation": value.observation.fingerprint if value.observation else None}
def _report_identity_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_VERSION, "as_of": _time(value["as_of"]), "observations": value["observation_ids"], "rejections": value["rejected_by_state"]}
def _report_payload(value: InflectionAccountingProspectiveBatchReport) -> dict[str, object]: return _report_payload_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key not in {"fingerprint", "contract_id", "contract_version"}})
def _report_payload_values(value: dict[str, object]) -> dict[str, object]: return _report_identity_values(value) | {key: value[key] for key in ("report_id", "non_financial_issuers_considered", "issuers_with_quarterly_facts", "revenue_acceleration_ready", "pat_acceleration_ready", "both_acceleration_ready", "special_state_observations", "observations_inserted", "observations_already_present", "outcomes_inserted", "outcomes_already_present")}
def _plan_payload(value: InflectionAccountingCandidateGridPlan) -> dict[str, object]: return _plan_payload_values({key: getattr(value, key) for key in value.__dataclass_fields__ if key not in {"fingerprint", "contract_id", "contract_version"}})
def _plan_payload_values(value: dict[str, object]) -> dict[str, object]: return {"contract": CONTRACT_VERSION, **value}
def _canonical_counts(value: tuple[tuple[str, int], ...]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(value)) if all(_identifier(key) and isinstance(count, int) and count >= 0 for key, count in value) and len({key for key, _ in value}) == len(value) else ()
def _identifier(value: object) -> bool: return isinstance(value, str) and _ID.fullmatch(value) is not None
def _fingerprint_value(value: object) -> bool: return isinstance(value, str) and _FP.fullmatch(value) is not None
def _aware(value: object) -> bool: return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
def _utc(value: datetime) -> datetime:
    if not _aware(value): raise InflectionAccountingProspectiveShadowError("INFLECTION_ACCOUNTING_AWARE_AS_OF_REQUIRED")
    return value.astimezone(UTC)
def _time(value: datetime) -> str: return _utc(value).isoformat()
def _isin(value: str) -> str | None:
    exchange, separator, isin = value.partition(":"); return isin if exchange == "NSE" and separator and _ISIN.fullmatch(isin) else None
def _hash(value: object) -> str: return hashlib.sha256(json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
def _fingerprint(value: object) -> str: return "sha256:" + _hash(value)
def _jsonable(value: object):
    if isinstance(value, StrEnum): return value.value
    if isinstance(value, datetime): return _time(value)
    if isinstance(value, tuple): return tuple(_jsonable(item) for item in value)
    if isinstance(value, dict): return {str(key): _jsonable(item) for key, item in value.items()}
    return value


__all__ = (
    "AccountingOutcomeMaturity", "ExactIntradayEventTimeState", "InflectionAccountingCandidateGridPlan",
    "InflectionAccountingObservationState", "InflectionAccountingOutcome", "InflectionAccountingProspectiveBatchReport",
    "InflectionAccountingProspectiveObservation", "InflectionAccountingProspectiveShadowError", "InflectionAccountingProspectiveStore",
    "InflectionAccountingReadiness", "InflectionAccountingReadinessState", "InflectionAccountingReason", "InflectionProspectiveWriteOutcome",
    "PROSPECTIVE_LEDGER_ACTIVATED_AT", "assess_inflection_accounting_prospective_readiness", "frozen_inflection_accounting_candidate_grid_plan",
    "initial_inflection_accounting_outcome", "run_inflection_accounting_prospective_batch", "serialize_inflection_accounting_observation",
)
