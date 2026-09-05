"""Factual, PIT-safe quarterly Inflection research receipts.

This module is deliberately narrower than an Inflection policy.  It composes
the existing selected-vintage observation and trajectory contracts to retain
reported quarterly Revenue/PAT YoY and acceleration *observations*.  It also
binds an exact reported fact to its primary financial-result filing when that
identity is already present, and asks an injected canonical calendar about
dates only.  It does not qualify, score, rank, interpret a market reaction,
or access storage, portfolio, API, broker, or runtime-clock dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
import hashlib
import json
import re
from typing import Iterable

from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling, FilingType, PrimarySourceQuality
from app.fundamentals.financial_fact_vintage_selection_policy import (
    CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactVintageSelection,
    select_financial_fact_vintages,
)
from app.fundamentals.financial_metric_observation_materializer import (
    FinancialMetricObservationMaterializationStatus,
    materialize_financial_metric_observation,
)
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricObservation,
    FinancialMetricPeriodIdentity,
    financial_metric_observation_fingerprint,
    financial_metric_period_identity_fingerprint,
)
from app.fundamentals.financial_metric_trajectory import (
    FinancialMetricTrajectory,
    FinancialMetricTrajectoryRequest,
    build_financial_metric_trajectory,
    financial_metric_trajectory_fingerprint,
)
from app.fundamentals.financial_metric_trajectory_policy import (
    CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY,
    FinancialMetricSignTransition,
    FinancialMetricTrajectoryBasis,
    FinancialMetricTrajectoryStatus,
)
from app.fundamentals.financial_research_observation_bundle_builder import (
    build_financial_research_observation_bundle,
)
from app.fundamentals.financial_research_observation_bundle_schema import (
    CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    FinancialResearchInputFailure,
    FinancialResearchInputFailureStage,
    FinancialResearchObservationAttestation,
    FinancialResearchObservationBundle,
    financial_research_input_failure_fingerprint,
    financial_research_observation_attestation_fingerprint,
    financial_research_observation_bundle_fingerprint,
)
from app.fundamentals.models import (
    FinancialFact,
    FinancialMetric,
    FinancialPeriodType,
    FinancialValueBasis,
    StatementScope,
)
from app.historical.guard import manifest_fingerprint
from app.historical.pit_company_type_classification_activation import (
    PitCompanyType,
    PitCompanyTypeClassificationReceipt,
    PitCompanyTypeClassificationState,
)
from app.historical.nse_mii_session_knownness import NseTradingSessionCalendar
from app.market_data.models import Exchange


CONTRACT_ID = "inflection-testable-derived-metrics-and-event-alignment"
CONTRACT_VERSION = "v1-research-only"
PROPOSAL_ID = "FUNDAMENTAL_INFLECTION_POLICY_RESEARCH_PROPOSAL_V1"
PROPOSAL_VERSION = "v1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9._:-]+\Z")
_FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MANIFEST_FINGERPRINT = re.compile(r"[0-9a-f]{64}\Z")
_MAX_CALENDAR_SEARCH_DAYS = 370


class InflectionDerivedMetricsError(ValueError):
    """Stable fail-closed error for malformed research inputs or receipts."""


class InflectionResearchMetric(StrEnum):
    REVENUE = "REVENUE"
    PAT = "PAT"


class InflectionDerivedMetricsState(StrEnum):
    ACCELERATION_OBSERVED = "ACCELERATION_OBSERVED"
    YOY_OBSERVED = "YOY_OBSERVED"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"
    NON_COMPARABLE = "NON_COMPARABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class InflectionDerivedMetricsReason(StrEnum):
    NON_FINANCIAL_COMPANY_TYPE_REQUIRED = "NON_FINANCIAL_COMPANY_TYPE_REQUIRED"
    COMPANY_TYPE_UNAVAILABLE = "COMPANY_TYPE_UNAVAILABLE"
    COMPANY_TYPE_AFTER_AS_OF = "COMPANY_TYPE_AFTER_AS_OF"
    EXACT_STATEMENT_SCOPE_REQUIRED = "EXACT_STATEMENT_SCOPE_REQUIRED"
    CURRENT_QUARTER_UNAVAILABLE = "CURRENT_QUARTER_UNAVAILABLE"
    PRIOR_YEAR_QUARTER_UNAVAILABLE = "PRIOR_YEAR_QUARTER_UNAVAILABLE"
    PRIOR_QUARTER_UNAVAILABLE = "PRIOR_QUARTER_UNAVAILABLE"
    PRIOR_YEAR_PREVIOUS_QUARTER_UNAVAILABLE = "PRIOR_YEAR_PREVIOUS_QUARTER_UNAVAILABLE"
    RESTATEMENT_CONFLICT = "RESTATEMENT_CONFLICT"
    BASIS_CHANGED = "BASIS_CHANGED"
    PERIOD_ALIGNMENT_MISMATCH = "PERIOD_ALIGNMENT_MISMATCH"
    LOSS_TO_PROFIT = "LOSS_TO_PROFIT"
    PROFIT_TO_LOSS = "PROFIT_TO_LOSS"
    LOSS_TO_LOSS = "LOSS_TO_LOSS"
    ZERO_BASE = "ZERO_BASE"
    NEAR_ZERO_BASE = "NEAR_ZERO_BASE"
    NON_POSITIVE_DENOMINATOR = "NON_POSITIVE_DENOMINATOR"
    SOURCE_DATA_INSUFFICIENT = "SOURCE_DATA_INSUFFICIENT"
    SOURCE_EVIDENCE_CONFLICTED = "SOURCE_EVIDENCE_CONFLICTED"
    SOURCE_LINEAGE_INVALID = "SOURCE_LINEAGE_INVALID"
    PRICE_REACTION_POLICY_NOT_ACTIVE = "PRICE_REACTION_POLICY_NOT_ACTIVE"
    VOLUME_REACTION_POLICY_NOT_ACTIVE = "VOLUME_REACTION_POLICY_NOT_ACTIVE"


class FilingLineageState(StrEnum):
    EXACT_FILING_TIMESTAMP_AVAILABLE = "EXACT_FILING_TIMESTAMP_AVAILABLE"
    FILING_TIMESTAMP_MISSING = "FILING_TIMESTAMP_MISSING"
    FILING_PERIOD_MISMATCH = "FILING_PERIOD_MISMATCH"
    FILING_IDENTITY_UNRESOLVED = "FILING_IDENTITY_UNRESOLVED"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class EventCalendarAlignmentState(StrEnum):
    TRADING_DATE_IDENTIFIED = "TRADING_DATE_IDENTIFIED"
    NON_TRADING_DATE = "NON_TRADING_DATE"
    CALENDAR_UNAVAILABLE = "CALENDAR_UNAVAILABLE"
    EVIDENCE_CONFLICTED = "EVIDENCE_CONFLICTED"


class IntradayEventSessionState(StrEnum):
    INTRADAY_EVENT_SESSION_UNRESOLVED = "INTRADAY_EVENT_SESSION_UNRESOLVED"


@dataclass(frozen=True, slots=True)
class InflectionFactLineage:
    fact_id: str
    fact_fingerprint: str

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.fact_id) or not _FINGERPRINT.fullmatch(self.fact_fingerprint):
            raise InflectionDerivedMetricsError("INFLECTION_FACT_LINEAGE_INVALID")


@dataclass(frozen=True, slots=True)
class ExactFinancialResultFilingLineage:
    state: FilingLineageState
    filing_id: str | None
    filing_fingerprint: str | None
    canonical_instrument_id: str
    statement_scope: StatementScope
    reporting_period_end: datetime | None
    announced_at: datetime | None
    received_at: datetime | None
    source: str | None
    source_reference: str | None
    revision_of_filing_id: str | None
    provenance: tuple[str, ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.canonical_instrument_id) or not isinstance(self.statement_scope, StatementScope):
            raise InflectionDerivedMetricsError("INFLECTION_FILING_LINEAGE_SCOPE_INVALID")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise InflectionDerivedMetricsError("INFLECTION_FILING_LINEAGE_PROVENANCE_NONCANONICAL")
        if self.state is FilingLineageState.EXACT_FILING_TIMESTAMP_AVAILABLE:
            if not all((self.filing_id, self.filing_fingerprint, self.source)) or not all(
                _aware(value) for value in (self.reporting_period_end, self.announced_at, self.received_at)
            ):
                raise InflectionDerivedMetricsError("INFLECTION_FILING_LINEAGE_EXACT_FIELDS_REQUIRED")
        elif any(value is not None for value in (
            self.filing_id, self.filing_fingerprint, self.announced_at, self.received_at, self.source,
            self.source_reference, self.revision_of_filing_id,
        )):
            raise InflectionDerivedMetricsError("INFLECTION_FILING_LINEAGE_UNRESOLVED_FIELDS_FORBIDDEN")
        if self.fingerprint != _fingerprint(_filing_payload(self)):
            raise InflectionDerivedMetricsError("INFLECTION_FILING_LINEAGE_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class EventCalendarAlignmentReceipt:
    filing_lineage_fingerprint: str
    filing_date: date | None
    state: EventCalendarAlignmentState
    prior_trading_session: date | None
    next_trading_session: date | None
    intraday_state: IntradayEventSessionState
    reason: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not _FINGERPRINT.fullmatch(self.filing_lineage_fingerprint):
            raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_FILING_LINEAGE_REQUIRED")
        if self.state in {EventCalendarAlignmentState.TRADING_DATE_IDENTIFIED, EventCalendarAlignmentState.NON_TRADING_DATE}:
            if self.filing_date is None or self.prior_trading_session is None or self.next_trading_session is None:
                raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_SESSIONS_REQUIRED")
            if self.prior_trading_session >= self.filing_date or self.next_trading_session <= self.filing_date:
                raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_SESSION_ORDER_INVALID")
        elif any(value is not None for value in (self.filing_date, self.prior_trading_session, self.next_trading_session)):
            raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_UNAVAILABLE_FIELDS_FORBIDDEN")
        if self.intraday_state is not IntradayEventSessionState.INTRADAY_EVENT_SESSION_UNRESOLVED:
            raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_INTRADAY_GUESS_FORBIDDEN")
        if self.fingerprint != _fingerprint(_alignment_payload(self)):
            raise InflectionDerivedMetricsError("INFLECTION_EVENT_ALIGNMENT_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class InflectionDerivedMetricsReceipt:
    """One metric's factual quarterly YoY/acceleration research observation."""

    receipt_id: str
    canonical_instrument_id: str
    canonical_issuer_id: str
    company_type_receipt_id: str
    company_type_receipt_fingerprint: str
    company_type: PitCompanyType | None
    statement_scope: StatementScope
    metric: InflectionResearchMetric
    as_of: datetime
    current_period: FinancialMetricPeriodIdentity | None
    current_yoy: FinancialMetricTrajectory | None
    previous_yoy: FinancialMetricTrajectory | None
    acceleration: Decimal | None
    input_facts: tuple[InflectionFactLineage, ...]
    source_bundle_fingerprint: str | None
    state: InflectionDerivedMetricsState
    reasons: tuple[InflectionDerivedMetricsReason, ...]
    filing_lineage: ExactFinancialResultFilingLineage
    calendar_alignment: EventCalendarAlignmentReceipt
    proposal_id: str
    proposal_version: str
    provenance: tuple[str, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"
    research_status: str = "RESEARCH_ONLY"

    def __post_init__(self) -> None:
        if not all((_IDENTIFIER.fullmatch(self.receipt_id), _IDENTIFIER.fullmatch(self.canonical_instrument_id), _IDENTIFIER.fullmatch(self.canonical_issuer_id), _IDENTIFIER.fullmatch(self.company_type_receipt_id))):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_IDENTITY_INVALID")
        if not _FINGERPRINT.fullmatch(self.company_type_receipt_fingerprint) or not _aware(self.as_of):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_SCOPE_INVALID")
        if self.input_facts != tuple(sorted(set(self.input_facts), key=lambda value: value.fact_id)):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_FACT_LINEAGE_NONCANONICAL")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value)):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_REASONS_NONCANONICAL")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_PROVENANCE_NONCANONICAL")
        if (self.proposal_id, self.proposal_version) != (PROPOSAL_ID, PROPOSAL_VERSION):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_PROPOSAL_LINEAGE_INVALID")
        if (self.contract_id, self.contract_version, self.actionability, self.execution_status, self.research_status) != (
            CONTRACT_ID, CONTRACT_VERSION, "WATCH_ONLY", "NON_EXECUTABLE", "RESEARCH_ONLY",
        ):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_BOUNDARY_INVALID")
        _validate_metric_state(self)
        if self.receipt_id != _receipt_id(_receipt_identity(self)):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_IDENTITY_MISMATCH")
        if self.fingerprint != _fingerprint(_receipt_payload(self)):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        self.__post_init__()


@dataclass(frozen=True, slots=True)
class InflectionDerivedMetricsEvaluation:
    canonical_instrument_id: str
    canonical_issuer_id: str
    statement_scope: StatementScope
    as_of: datetime
    company_type_receipt_id: str
    company_type_receipt_fingerprint: str
    receipts: tuple[InflectionDerivedMetricsReceipt, ...]
    fingerprint: str
    contract_id: str = CONTRACT_ID
    contract_version: str = CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not all((_IDENTIFIER.fullmatch(self.canonical_instrument_id), _IDENTIFIER.fullmatch(self.canonical_issuer_id), _IDENTIFIER.fullmatch(self.company_type_receipt_id), _FINGERPRINT.fullmatch(self.company_type_receipt_fingerprint), _aware(self.as_of))):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_EVALUATION_SCOPE_INVALID")
        if self.receipts != tuple(sorted(self.receipts, key=lambda value: value.metric.value)) or {value.metric for value in self.receipts} != set(InflectionResearchMetric) or len(self.receipts) != len(InflectionResearchMetric):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_EVALUATION_RECEIPTS_INVALID")
        if any(
            value.canonical_instrument_id != self.canonical_instrument_id
            or value.canonical_issuer_id != self.canonical_issuer_id
            or value.statement_scope is not self.statement_scope
            or value.as_of != self.as_of
            or value.company_type_receipt_id != self.company_type_receipt_id
            or value.company_type_receipt_fingerprint != self.company_type_receipt_fingerprint
            for value in self.receipts
        ):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_EVALUATION_RECEIPT_SCOPE_INVALID")
        if (self.contract_id, self.contract_version) != (CONTRACT_ID, CONTRACT_VERSION) or self.fingerprint != _fingerprint(_evaluation_payload(self)):
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_EVALUATION_FINGERPRINT_MISMATCH")

    def verify(self) -> None:
        self.__post_init__()


def evaluate_inflection_testable_derived_metrics_and_event_alignment(
    *,
    facts: Iterable[FinancialFact],
    filings: Iterable[CorporateFiling],
    company_type_receipt: PitCompanyTypeClassificationReceipt,
    statement_scope: StatementScope,
    as_of: datetime,
    calendar: NseTradingSessionCalendar | None,
) -> InflectionDerivedMetricsEvaluation:
    """Compose factual quarterly inputs at an explicit historical cutoff.

    There is no implicit latest-now lookup: ``as_of`` is supplied by the
    caller, fact selection is knowledge-at-the-time, and the current quarter
    is the greatest complete fiscal-quarter identity visible at that cutoff.
    """
    if not isinstance(company_type_receipt, PitCompanyTypeClassificationReceipt):
        raise InflectionDerivedMetricsError("INFLECTION_COMPANY_TYPE_RECEIPT_REQUIRED")
    try:
        company_type_receipt.verify()
    except (TypeError, ValueError, AttributeError) as error:
        raise InflectionDerivedMetricsError("INFLECTION_COMPANY_TYPE_RECEIPT_TAMPERED") from error
    if not _aware(as_of) or not isinstance(statement_scope, StatementScope) or statement_scope is StatementScope.UNKNOWN:
        raise InflectionDerivedMetricsError("INFLECTION_EVALUATION_INPUT_INVALID")
    cutoff = _utc(as_of)
    issuer = company_type_receipt.canonical_issuer_id
    instrument = company_type_receipt.canonical_instrument_id
    if company_type_receipt.evaluated_as_of > cutoff:
        return _evaluation(
            instrument, issuer, statement_scope, cutoff, company_type_receipt,
            tuple(_company_type_blocked(metric, company_type_receipt, statement_scope, cutoff, InflectionDerivedMetricsReason.COMPANY_TYPE_AFTER_AS_OF) for metric in InflectionResearchMetric),
        )
    if company_type_receipt.state is not PitCompanyTypeClassificationState.CLASSIFIED or company_type_receipt.company_type is None:
        return _evaluation(
            instrument, issuer, statement_scope, cutoff, company_type_receipt,
            tuple(_company_type_blocked(metric, company_type_receipt, statement_scope, cutoff, InflectionDerivedMetricsReason.COMPANY_TYPE_UNAVAILABLE) for metric in InflectionResearchMetric),
        )
    if company_type_receipt.company_type is not PitCompanyType.NON_FINANCIAL:
        return _evaluation(
            instrument, issuer, statement_scope, cutoff, company_type_receipt,
            tuple(_company_type_blocked(metric, company_type_receipt, statement_scope, cutoff, InflectionDerivedMetricsReason.NON_FINANCIAL_COMPANY_TYPE_REQUIRED) for metric in InflectionResearchMetric),
        )

    selected_facts = _canonical_facts(facts, instrument, statement_scope)
    bundle, fact_fingerprints = _bundle_from_facts(selected_facts, instrument, cutoff)
    filing_values = _canonical_filings(filings, instrument)
    receipts = tuple(
        _evaluate_metric(
            metric=metric,
            bundle=bundle,
            fact_fingerprints=fact_fingerprints,
            filings=filing_values,
            company_type_receipt=company_type_receipt,
            statement_scope=statement_scope,
            as_of=cutoff,
            calendar=calendar,
        )
        for metric in InflectionResearchMetric
    )
    return _evaluation(instrument, issuer, statement_scope, cutoff, company_type_receipt, receipts)


def serialize_inflection_testable_derived_metrics(value: InflectionDerivedMetricsEvaluation) -> str:
    value.verify()
    return json.dumps(_evaluation_payload(value) | {"fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_facts(
    facts: Iterable[FinancialFact], canonical_instrument_id: str, statement_scope: StatementScope,
) -> tuple[FinancialFact, ...]:
    result: dict[str, FinancialFact] = {}
    for fact in facts:
        if not isinstance(fact, FinancialFact):
            raise InflectionDerivedMetricsError("INFLECTION_FACT_TYPE_INVALID")
        if fact.instrument.instrument_id != canonical_instrument_id:
            raise InflectionDerivedMetricsError("INFLECTION_MIXED_INSTRUMENT_INPUT")
        if fact.fact_id in result and result[fact.fact_id] != fact:
            raise InflectionDerivedMetricsError("INFLECTION_FACT_ID_CONFLICT")
        if (
            fact.statement_scope is statement_scope
            and fact.metric in {FinancialMetric.REVENUE, FinancialMetric.PAT}
            and fact.fact_kind is FundamentalFactKind.REPORTED
            and fact.period_type is FinancialPeriodType.QUARTERLY
        ):
            result[fact.fact_id] = fact
    return tuple(sorted(result.values(), key=lambda value: value.fact_id))


def _canonical_filings(filings: Iterable[CorporateFiling], canonical_instrument_id: str) -> tuple[CorporateFiling, ...]:
    result: dict[str, CorporateFiling] = {}
    for filing in filings:
        if not isinstance(filing, CorporateFiling):
            raise InflectionDerivedMetricsError("INFLECTION_FILING_TYPE_INVALID")
        if filing.instrument.instrument_id != canonical_instrument_id:
            continue
        if filing.filing_id in result and result[filing.filing_id] != filing:
            raise InflectionDerivedMetricsError("INFLECTION_FILING_ID_CONFLICT")
        result[filing.filing_id] = filing
    return tuple(sorted(result.values(), key=lambda value: value.filing_id))


def _bundle_from_facts(
    facts: tuple[FinancialFact, ...], canonical_instrument_id: str, as_of: datetime,
) -> tuple[FinancialResearchObservationBundle, dict[str, str]]:
    selection_batch = select_financial_fact_vintages(
        facts,
        canonical_instrument_id=canonical_instrument_id,
        as_of=as_of,
        policy=CURRENT_FROZEN_FINANCIAL_FACT_VINTAGE_SELECTION_POLICY,
    )
    facts_by_id = {value.fact_id: value for value in facts}
    observations: list[FinancialMetricObservation] = []
    attestations: list[FinancialResearchObservationAttestation] = []
    failures: list[FinancialResearchInputFailure] = []
    for selection in selection_batch.selections:
        if selection.status is not FinancialFactVintageSelectionStatus.SELECTED:
            failures.append(_selection_failure(canonical_instrument_id, selection))
            continue
        assert selection.selected_fact_id is not None
        fact = facts_by_id.get(selection.selected_fact_id)
        if fact is None:
            raise InflectionDerivedMetricsError("INFLECTION_SELECTED_FACT_MISSING")
        materialization = materialize_financial_metric_observation(
            fact,
            selection=selection,
            schema=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
        )
        if materialization.status is FinancialMetricObservationMaterializationStatus.REJECTED or materialization.observation is None:
            failures.append(_materialization_failure(canonical_instrument_id, selection, materialization))
            continue
        observation = materialization.observation
        observations.append(observation)
        attestations.append(_attestation(observation, selection, as_of))
    bundle = build_financial_research_observation_bundle(
        canonical_instrument_id=canonical_instrument_id,
        as_of=as_of,
        observations=tuple(observations),
        attestations=tuple(attestations),
        failures=tuple(failures),
        schema=CURRENT_FROZEN_FINANCIAL_RESEARCH_OBSERVATION_BUNDLE_SCHEMA,
    )
    return bundle, {value.fact_id: _financial_fact_fingerprint(value) for value in facts}


def _selection_failure(canonical_instrument_id: str, selection: FinancialFactVintageSelection) -> FinancialResearchInputFailure:
    values = dict(
        canonical_instrument_id=canonical_instrument_id,
        semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.SELECTION,
        selection_as_of=selection.as_of,
        selection_status=selection.status,
        materialization_status=None,
        reason_codes=selection.reasons,
        source_fact_id=None,
        selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=None,
        selector_policy_id=selection.policy_id,
        selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.schema_id,
        observation_schema_version=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.version,
        observation_schema_fingerprint=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values,
        fingerprint=financial_research_input_failure_fingerprint_values(values),
    )


def _materialization_failure(canonical_instrument_id: str, selection: FinancialFactVintageSelection, materialization) -> FinancialResearchInputFailure:
    values = dict(
        canonical_instrument_id=canonical_instrument_id,
        semantic_key=selection.semantic_key,
        stage=FinancialResearchInputFailureStage.MATERIALIZATION,
        selection_as_of=selection.as_of,
        selection_status=selection.status,
        materialization_status=materialization.status,
        reason_codes=materialization.reasons,
        source_fact_id=materialization.source_fact_id,
        selection_result_fingerprint=selection.fingerprint,
        materialization_result_fingerprint=materialization.fingerprint,
        selector_policy_id=selection.policy_id,
        selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.schema_id,
        observation_schema_version=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.version,
        observation_schema_fingerprint=CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.fingerprint,
    )
    return FinancialResearchInputFailure(
        **values,
        fingerprint=financial_research_input_failure_fingerprint_values(values),
    )


def financial_research_input_failure_fingerprint_values(values: dict) -> str:
    """Use the existing failure semantic canonicalizer without exposing it as a new policy."""
    from app.fundamentals import financial_research_observation_bundle_schema as schema
    return manifest_fingerprint(**schema._semantic_values(values))


def _attestation(observation: FinancialMetricObservation, selection: FinancialFactVintageSelection, as_of: datetime) -> FinancialResearchObservationAttestation:
    values = dict(
        observation_fingerprint=observation.fingerprint,
        source_fact_id=observation.source_fact_id,
        selection_result_fingerprint=selection.fingerprint,
        selection_as_of=as_of,
        selector_policy_id=selection.policy_id,
        selector_policy_version=selection.policy_version,
        selector_policy_fingerprint=selection.policy_fingerprint,
        observation_schema_id=observation.schema_id,
        observation_schema_version=observation.schema_version,
        observation_schema_fingerprint=observation.schema_fingerprint,
    )
    return FinancialResearchObservationAttestation(
        **values,
        fingerprint=financial_research_observation_attestation_fingerprint_values(values),
    )


def financial_research_observation_attestation_fingerprint_values(values: dict) -> str:
    from app.fundamentals import financial_research_observation_bundle_schema as schema
    return manifest_fingerprint(**schema._semantic_values(values))


def _evaluate_metric(
    *, metric: InflectionResearchMetric, bundle: FinancialResearchObservationBundle,
    fact_fingerprints: dict[str, str], filings: tuple[CorporateFiling, ...],
    company_type_receipt: PitCompanyTypeClassificationReceipt, statement_scope: StatementScope,
    as_of: datetime, calendar: NseTradingSessionCalendar | None,
) -> InflectionDerivedMetricsReceipt:
    financial_metric = FinancialMetric(metric.value)
    observations = _quarterly_observations(bundle, financial_metric, statement_scope)
    conflicted_keys = _metric_conflicted_keys(bundle, financial_metric, statement_scope)
    current_key, current, current_reason = _current_observation(observations, conflicted_keys)
    if current_reason is InflectionDerivedMetricsReason.SOURCE_EVIDENCE_CONFLICTED:
        return _conflict_receipt(
            company_type_receipt, statement_scope, metric, as_of, bundle.fingerprint, None, (),
        )
    if current is None or current_key is None:
        return _receipt(
            company_type_receipt=company_type_receipt, statement_scope=statement_scope, metric=metric, as_of=as_of,
            current_period=None, current_yoy=None, previous_yoy=None, acceleration=None, input_facts=(),
            source_bundle_fingerprint=bundle.fingerprint,
            state=(
                InflectionDerivedMetricsState.NON_COMPARABLE
                if current_reason is InflectionDerivedMetricsReason.BASIS_CHANGED
                else InflectionDerivedMetricsState.DATA_INSUFFICIENT
            ),
            reasons=(current_reason or InflectionDerivedMetricsReason.CURRENT_QUARTER_UNAVAILABLE,),
            filing_lineage=_unresolved_filing(company_type_receipt.canonical_instrument_id, statement_scope, FilingLineageState.FILING_IDENTITY_UNRESOLVED),
            calendar_alignment=_unavailable_alignment("CURRENT_QUARTER_UNAVAILABLE"),
        )
    previous_year_key = (current_key[0] - 1, current_key[1])
    prior_quarter_key = _prior_quarter(current_key)
    prior_year_prior_quarter_key = (prior_quarter_key[0] - 1, prior_quarter_key[1])
    if any(key in conflicted_keys for key in (current_key, previous_year_key, prior_quarter_key, prior_year_prior_quarter_key)):
        return _conflict_receipt(
            company_type_receipt, statement_scope, metric, as_of, bundle.fingerprint,
            current.period_identity, _fact_lineage((current,), fact_fingerprints),
        )
    comparable, comparable_reason = _unique_observation(observations, previous_year_key, InflectionDerivedMetricsReason.PRIOR_YEAR_QUARTER_UNAVAILABLE)
    prior, prior_reason = _unique_observation(observations, prior_quarter_key, InflectionDerivedMetricsReason.PRIOR_QUARTER_UNAVAILABLE)
    prior_comparable, prior_comparable_reason = _unique_observation(observations, prior_year_prior_quarter_key, InflectionDerivedMetricsReason.PRIOR_YEAR_PREVIOUS_QUARTER_UNAVAILABLE)
    current_yoy = None if comparable is None else _trajectory(bundle, financial_metric, comparable, current)
    previous_yoy = None if prior is None or prior_comparable is None else _trajectory(bundle, financial_metric, prior_comparable, prior)
    source_observations = tuple(value for value in (current, comparable, prior, prior_comparable) if value is not None)
    input_facts = _fact_lineage(source_observations, fact_fingerprints)
    filing_lineage = _filing_lineage(current, filings, company_type_receipt.canonical_instrument_id, statement_scope, as_of)
    alignment = _calendar_alignment(filing_lineage, calendar)
    reasons = set[InflectionDerivedMetricsReason]({
        InflectionDerivedMetricsReason.PRICE_REACTION_POLICY_NOT_ACTIVE,
        InflectionDerivedMetricsReason.VOLUME_REACTION_POLICY_NOT_ACTIVE,
    })
    reasons.update(value for value in (comparable_reason, prior_reason, prior_comparable_reason) if value is not None)
    state = InflectionDerivedMetricsState.DATA_INSUFFICIENT
    acceleration: Decimal | None = None
    if current_yoy is None:
        reasons.add(InflectionDerivedMetricsReason.SOURCE_DATA_INSUFFICIENT)
        if InflectionDerivedMetricsReason.BASIS_CHANGED in reasons:
            state = InflectionDerivedMetricsState.NON_COMPARABLE
    else:
        current_state, current_reason = _trajectory_state(current_yoy, metric)
        if current_state is not None:
            state = current_state
            reasons.add(current_reason)
        elif previous_yoy is None:
            state = InflectionDerivedMetricsState.YOY_OBSERVED
        else:
            previous_state, previous_reason = _trajectory_state(previous_yoy, metric)
            if previous_state is not None:
                state = previous_state
                reasons.add(previous_reason)
            else:
                assert current_yoy.relative_delta is not None and previous_yoy.relative_delta is not None
                acceleration = current_yoy.relative_delta - previous_yoy.relative_delta
                state = InflectionDerivedMetricsState.ACCELERATION_OBSERVED
    if current_yoy is not None and current_yoy.status is FinancialMetricTrajectoryStatus.AVAILABLE and state is InflectionDerivedMetricsState.DATA_INSUFFICIENT:
        state = InflectionDerivedMetricsState.YOY_OBSERVED
    if state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED:
        reasons.discard(InflectionDerivedMetricsReason.SOURCE_DATA_INSUFFICIENT)
    return _receipt(
        company_type_receipt=company_type_receipt, statement_scope=statement_scope, metric=metric, as_of=as_of,
        current_period=current.period_identity, current_yoy=current_yoy, previous_yoy=previous_yoy,
        acceleration=acceleration, input_facts=input_facts, source_bundle_fingerprint=bundle.fingerprint,
        state=state, reasons=tuple(reasons), filing_lineage=filing_lineage, calendar_alignment=alignment,
    )


def _metric_conflicted_keys(
    bundle: FinancialResearchObservationBundle, metric: FinancialMetric, statement_scope: StatementScope,
) -> frozenset[tuple[int, int]]:
    """Expose only relevant conflicted quarters; unrelated history stays inert."""
    return frozenset(
        (failure.semantic_key.fiscal_year, failure.semantic_key.fiscal_quarter)
        for failure in bundle.failures
        if (
            failure.selection_status is FinancialFactVintageSelectionStatus.CONFLICTED
            and failure.semantic_key is not None
            and failure.semantic_key.metric is metric
            and failure.semantic_key.statement_scope is statement_scope
            and failure.semantic_key.period_type is FinancialPeriodType.QUARTERLY
            and failure.semantic_key.fiscal_year is not None
            and failure.semantic_key.fiscal_quarter is not None
        )
    )


def _quarterly_observations(
    bundle: FinancialResearchObservationBundle, metric: FinancialMetric, statement_scope: StatementScope,
) -> dict[tuple[int, int], tuple[FinancialMetricObservation, ...]]:
    result: dict[tuple[int, int], list[FinancialMetricObservation]] = {}
    for observation in bundle.observations:
        period = observation.period_identity
        if (
            observation.metric is metric
            and observation.statement_scope is statement_scope
            and period.period_type is FinancialPeriodType.QUARTERLY
            and period.fiscal_year is not None
            and period.fiscal_quarter is not None
        ):
            result.setdefault((period.fiscal_year, period.fiscal_quarter), []).append(observation)
    return {key: tuple(sorted(values, key=lambda value: value.fingerprint)) for key, values in result.items()}


def _current_observation(
    observations: dict[tuple[int, int], tuple[FinancialMetricObservation, ...]],
    conflicted_keys: frozenset[tuple[int, int]],
) -> tuple[tuple[int, int] | None, FinancialMetricObservation | None, InflectionDerivedMetricsReason | None]:
    keys = set(observations) | set(conflicted_keys)
    if not keys:
        return None, None, InflectionDerivedMetricsReason.CURRENT_QUARTER_UNAVAILABLE
    key = max(keys)
    if key in conflicted_keys:
        return key, None, InflectionDerivedMetricsReason.SOURCE_EVIDENCE_CONFLICTED
    value, reason = _unique_observation(observations, key, InflectionDerivedMetricsReason.CURRENT_QUARTER_UNAVAILABLE)
    return key, value, reason


def _unique_observation(
    observations: dict[tuple[int, int], tuple[FinancialMetricObservation, ...]], key: tuple[int, int],
    missing_reason: InflectionDerivedMetricsReason,
) -> tuple[FinancialMetricObservation | None, InflectionDerivedMetricsReason | None]:
    values = observations.get(key, ())
    if not values:
        return None, missing_reason
    if len(values) != 1:
        return None, InflectionDerivedMetricsReason.BASIS_CHANGED
    return values[0], None


def _prior_quarter(value: tuple[int, int]) -> tuple[int, int]:
    fiscal_year, fiscal_quarter = value
    return (fiscal_year - 1, 4) if fiscal_quarter == 1 else (fiscal_year, fiscal_quarter - 1)


def _trajectory(
    bundle: FinancialResearchObservationBundle, metric: FinancialMetric,
    previous: FinancialMetricObservation, current: FinancialMetricObservation,
) -> FinancialMetricTrajectory:
    return build_financial_metric_trajectory(
        bundle,
        request=FinancialMetricTrajectoryRequest(
            metric=metric,
            basis=FinancialMetricTrajectoryBasis.YEAR_OVER_YEAR_QUARTER,
            previous_observation_fingerprint=previous.fingerprint,
            current_observation_fingerprint=current.fingerprint,
        ),
        policy=CURRENT_FROZEN_FINANCIAL_METRIC_TRAJECTORY_POLICY,
    )


def _trajectory_state(
    trajectory: FinancialMetricTrajectory, metric: InflectionResearchMetric,
) -> tuple[InflectionDerivedMetricsState | None, InflectionDerivedMetricsReason | None]:
    if financial_metric_trajectory_fingerprint(trajectory) != trajectory.fingerprint:
        return InflectionDerivedMetricsState.EVIDENCE_CONFLICTED, InflectionDerivedMetricsReason.SOURCE_LINEAGE_INVALID
    if metric is InflectionResearchMetric.PAT and trajectory.sign_transition is not FinancialMetricSignTransition.POSITIVE_TO_POSITIVE:
        return InflectionDerivedMetricsState.NON_COMPARABLE, _trajectory_reason(trajectory, metric)
    if trajectory.previous_value is not None and trajectory.previous_value <= 0:
        return InflectionDerivedMetricsState.NON_COMPARABLE, _trajectory_reason(trajectory, metric)
    if trajectory.status is FinancialMetricTrajectoryStatus.AVAILABLE and trajectory.relative_delta is not None:
        return None, None
    if trajectory.status is FinancialMetricTrajectoryStatus.INSUFFICIENT:
        return InflectionDerivedMetricsState.DATA_INSUFFICIENT, InflectionDerivedMetricsReason.SOURCE_DATA_INSUFFICIENT
    if trajectory.status is FinancialMetricTrajectoryStatus.NON_COMPARABLE:
        return InflectionDerivedMetricsState.NON_COMPARABLE, _trajectory_reason(trajectory, metric)
    return InflectionDerivedMetricsState.NON_COMPARABLE, InflectionDerivedMetricsReason.PERIOD_ALIGNMENT_MISMATCH


def _trajectory_reason(trajectory: FinancialMetricTrajectory, metric: InflectionResearchMetric) -> InflectionDerivedMetricsReason:
    transition = trajectory.sign_transition
    if metric is InflectionResearchMetric.PAT:
        if transition is FinancialMetricSignTransition.NEGATIVE_TO_POSITIVE:
            return InflectionDerivedMetricsReason.LOSS_TO_PROFIT
        if transition is FinancialMetricSignTransition.POSITIVE_TO_NEGATIVE:
            return InflectionDerivedMetricsReason.PROFIT_TO_LOSS
        if transition is FinancialMetricSignTransition.NEGATIVE_TO_NEGATIVE:
            return InflectionDerivedMetricsReason.LOSS_TO_LOSS
    if trajectory.previous_value == 0:
        return InflectionDerivedMetricsReason.ZERO_BASE
    if trajectory.previous_value is not None and trajectory.previous_value < 0:
        return InflectionDerivedMetricsReason.NON_POSITIVE_DENOMINATOR
    if any("PARITY" in value or "BASIS" in value for value in trajectory.blockers):
        return InflectionDerivedMetricsReason.BASIS_CHANGED
    return InflectionDerivedMetricsReason.PERIOD_ALIGNMENT_MISMATCH


def _fact_lineage(observations: tuple[FinancialMetricObservation, ...], fact_fingerprints: dict[str, str]) -> tuple[InflectionFactLineage, ...]:
    values = []
    for observation in observations:
        if financial_metric_observation_fingerprint(observation) != observation.fingerprint:
            raise InflectionDerivedMetricsError("INFLECTION_OBSERVATION_TAMPERED")
        fingerprint = fact_fingerprints.get(observation.source_fact_id)
        if fingerprint is None:
            raise InflectionDerivedMetricsError("INFLECTION_SOURCE_FACT_LINEAGE_MISSING")
        values.append(InflectionFactLineage(observation.source_fact_id, fingerprint))
    return tuple(sorted(set(values), key=lambda value: value.fact_id))


def _filing_lineage(
    observation: FinancialMetricObservation, filings: tuple[CorporateFiling, ...], canonical_instrument_id: str,
    statement_scope: StatementScope, as_of: datetime,
) -> ExactFinancialResultFilingLineage:
    if not observation.filing_id:
        return _unresolved_filing(canonical_instrument_id, statement_scope, FilingLineageState.FILING_IDENTITY_UNRESOLVED)
    candidates = tuple(value for value in filings if value.filing_id == observation.filing_id)
    if len(candidates) != 1:
        state = FilingLineageState.FILING_IDENTITY_UNRESOLVED if not candidates else FilingLineageState.EVIDENCE_CONFLICTED
        return _unresolved_filing(canonical_instrument_id, statement_scope, state)
    filing = candidates[0]
    if not _filing_matches(filing, observation, canonical_instrument_id, statement_scope):
        return _unresolved_filing(canonical_instrument_id, statement_scope, FilingLineageState.FILING_PERIOD_MISMATCH)
    if not all(_aware(value) for value in (filing.announced_at, filing.received_at)):
        return _unresolved_filing(canonical_instrument_id, statement_scope, FilingLineageState.FILING_TIMESTAMP_MISSING)
    if filing.announced_at > as_of or filing.received_at > as_of:
        return _unresolved_filing(canonical_instrument_id, statement_scope, FilingLineageState.FILING_IDENTITY_UNRESOLVED)
    values = dict(
        state=FilingLineageState.EXACT_FILING_TIMESTAMP_AVAILABLE,
        filing_id=filing.filing_id,
        filing_fingerprint=_corporate_filing_fingerprint(filing),
        canonical_instrument_id=canonical_instrument_id,
        statement_scope=statement_scope,
        reporting_period_end=observation.period_identity.period_end,
        announced_at=filing.announced_at,
        received_at=filing.received_at,
        source=filing.source,
        source_reference=filing.source_reference,
        revision_of_filing_id=filing.revision_of_filing_id,
        provenance=(filing.provenance.source_reference,) if filing.provenance.source_reference else (),
    )
    return ExactFinancialResultFilingLineage(**values, fingerprint=_fingerprint(_filing_payload_values(values)))


def _filing_matches(
    filing: CorporateFiling, observation: FinancialMetricObservation, canonical_instrument_id: str,
    statement_scope: StatementScope,
) -> bool:
    metadata = filing.financial_result
    period = observation.period_identity
    return bool(
        filing.instrument.instrument_id == canonical_instrument_id
        and filing.exchange in {Exchange.BSE, Exchange.NSE}
        and filing.filing_type is FilingType.FINANCIAL_RESULTS
        and filing.source_quality in {PrimarySourceQuality.PRIMARY_EXCHANGE, PrimarySourceQuality.PRIMARY_ISSUER}
        and metadata is not None
        and filing.period_end is not None
        and metadata.period_end == period.period_end == filing.period_end
        and metadata.result_scope == statement_scope.value
    )


def _unresolved_filing(canonical_instrument_id: str, scope: StatementScope, state: FilingLineageState) -> ExactFinancialResultFilingLineage:
    values = dict(
        state=state, filing_id=None, filing_fingerprint=None, canonical_instrument_id=canonical_instrument_id,
        statement_scope=scope, reporting_period_end=None, announced_at=None, received_at=None, source=None,
        source_reference=None, revision_of_filing_id=None, provenance=(),
    )
    return ExactFinancialResultFilingLineage(**values, fingerprint=_fingerprint(_filing_payload_values(values)))


def _calendar_alignment(
    filing: ExactFinancialResultFilingLineage, calendar: NseTradingSessionCalendar | None,
) -> EventCalendarAlignmentReceipt:
    if filing.state is not FilingLineageState.EXACT_FILING_TIMESTAMP_AVAILABLE or filing.announced_at is None:
        return _unavailable_alignment(filing.state.value, filing.fingerprint)
    if calendar is None or not hasattr(calendar, "is_trading_day"):
        return _unavailable_alignment("CANONICAL_TRADING_CALENDAR_REQUIRED", filing.fingerprint)
    filing_date = filing.announced_at.astimezone(UTC).date()
    try:
        is_trading_day = calendar.is_trading_day(filing_date)
        prior = _adjacent_session(calendar, filing_date, -1)
        following = _adjacent_session(calendar, filing_date, 1)
    except (AttributeError, TypeError, ValueError):
        return _unavailable_alignment("CANONICAL_TRADING_CALENDAR_UNAVAILABLE", filing.fingerprint)
    if prior is None or following is None:
        return _unavailable_alignment("ADJACENT_TRADING_SESSION_UNAVAILABLE", filing.fingerprint)
    values = dict(
        filing_lineage_fingerprint=filing.fingerprint,
        filing_date=filing_date,
        state=EventCalendarAlignmentState.TRADING_DATE_IDENTIFIED if is_trading_day else EventCalendarAlignmentState.NON_TRADING_DATE,
        prior_trading_session=prior,
        next_trading_session=following,
        intraday_state=IntradayEventSessionState.INTRADAY_EVENT_SESSION_UNRESOLVED,
        reason="INTRADAY_MARKET_SESSION_BOUNDARY_NOT_CANONICAL",
    )
    return EventCalendarAlignmentReceipt(**values, fingerprint=_fingerprint(_alignment_payload_values(values)))


def _adjacent_session(calendar: NseTradingSessionCalendar, start: date, direction: int) -> date | None:
    for offset in range(1, _MAX_CALENDAR_SEARCH_DAYS + 1):
        candidate = start + timedelta(days=direction * offset)
        if calendar.is_trading_day(candidate):
            return candidate
    return None


def _unavailable_alignment(reason: str, filing_fingerprint: str | None = None) -> EventCalendarAlignmentReceipt:
    values = dict(
        filing_lineage_fingerprint=filing_fingerprint or "sha256:" + "0" * 64,
        filing_date=None, state=EventCalendarAlignmentState.CALENDAR_UNAVAILABLE,
        prior_trading_session=None, next_trading_session=None,
        intraday_state=IntradayEventSessionState.INTRADAY_EVENT_SESSION_UNRESOLVED,
        reason=reason,
    )
    return EventCalendarAlignmentReceipt(**values, fingerprint=_fingerprint(_alignment_payload_values(values)))


def _conflict_receipt(
    company_type_receipt: PitCompanyTypeClassificationReceipt,
    statement_scope: StatementScope,
    metric: InflectionResearchMetric,
    as_of: datetime,
    source_bundle_fingerprint: str,
    current_period: FinancialMetricPeriodIdentity | None,
    input_facts: tuple[InflectionFactLineage, ...],
) -> InflectionDerivedMetricsReceipt:
    return _receipt(
        company_type_receipt=company_type_receipt,
        statement_scope=statement_scope,
        metric=metric,
        as_of=as_of,
        current_period=current_period,
        current_yoy=None,
        previous_yoy=None,
        acceleration=None,
        input_facts=input_facts,
        source_bundle_fingerprint=source_bundle_fingerprint,
        state=InflectionDerivedMetricsState.EVIDENCE_CONFLICTED,
        reasons=(
            InflectionDerivedMetricsReason.RESTATEMENT_CONFLICT,
            InflectionDerivedMetricsReason.SOURCE_EVIDENCE_CONFLICTED,
            InflectionDerivedMetricsReason.PRICE_REACTION_POLICY_NOT_ACTIVE,
            InflectionDerivedMetricsReason.VOLUME_REACTION_POLICY_NOT_ACTIVE,
        ),
        filing_lineage=_unresolved_filing(
            company_type_receipt.canonical_instrument_id,
            statement_scope,
            FilingLineageState.EVIDENCE_CONFLICTED,
        ),
        calendar_alignment=_unavailable_alignment("SOURCE_EVIDENCE_CONFLICTED"),
    )


def _company_type_blocked(
    metric: InflectionResearchMetric, receipt: PitCompanyTypeClassificationReceipt, scope: StatementScope,
    as_of: datetime, reason: InflectionDerivedMetricsReason,
) -> InflectionDerivedMetricsReceipt:
    state = InflectionDerivedMetricsState.NOT_APPLICABLE if reason is InflectionDerivedMetricsReason.NON_FINANCIAL_COMPANY_TYPE_REQUIRED else InflectionDerivedMetricsState.DATA_INSUFFICIENT
    return _receipt(
        company_type_receipt=receipt, statement_scope=scope, metric=metric, as_of=as_of,
        current_period=None, current_yoy=None, previous_yoy=None, acceleration=None, input_facts=(),
        source_bundle_fingerprint=None, state=state, reasons=(reason,),
        filing_lineage=_unresolved_filing(receipt.canonical_instrument_id, scope, FilingLineageState.FILING_IDENTITY_UNRESOLVED),
        calendar_alignment=_unavailable_alignment(reason.value),
    )


def _receipt(
    *, company_type_receipt: PitCompanyTypeClassificationReceipt, statement_scope: StatementScope,
    metric: InflectionResearchMetric, as_of: datetime, current_period: FinancialMetricPeriodIdentity | None,
    current_yoy: FinancialMetricTrajectory | None, previous_yoy: FinancialMetricTrajectory | None,
    acceleration: Decimal | None, input_facts: tuple[InflectionFactLineage, ...],
    source_bundle_fingerprint: str | None, state: InflectionDerivedMetricsState,
    reasons: tuple[InflectionDerivedMetricsReason, ...], filing_lineage: ExactFinancialResultFilingLineage,
    calendar_alignment: EventCalendarAlignmentReceipt,
) -> InflectionDerivedMetricsReceipt:
    values = dict(
        canonical_instrument_id=company_type_receipt.canonical_instrument_id,
        canonical_issuer_id=company_type_receipt.canonical_issuer_id,
        company_type_receipt_id=company_type_receipt.receipt_id,
        company_type_receipt_fingerprint=company_type_receipt.fingerprint,
        company_type=company_type_receipt.company_type,
        statement_scope=statement_scope, metric=metric, as_of=as_of, current_period=current_period,
        current_yoy=current_yoy, previous_yoy=previous_yoy, acceleration=acceleration,
        input_facts=tuple(sorted(set(input_facts), key=lambda value: value.fact_id)),
        source_bundle_fingerprint=source_bundle_fingerprint, state=state,
        reasons=tuple(sorted(set(reasons), key=lambda value: value.value)), filing_lineage=filing_lineage,
        calendar_alignment=calendar_alignment, proposal_id=PROPOSAL_ID, proposal_version=PROPOSAL_VERSION,
        provenance=("FACT_TO_DATA_ONLY", "PRICE_REACTION_POLICY_NOT_ACTIVE", "VOLUME_REACTION_POLICY_NOT_ACTIVE"),
    )
    values["receipt_id"] = _receipt_id(_receipt_identity_values(values))
    return InflectionDerivedMetricsReceipt(**values, fingerprint=_fingerprint(_receipt_payload_values(values)))


def _evaluation(
    instrument: str, issuer: str, scope: StatementScope, as_of: datetime,
    company_type_receipt: PitCompanyTypeClassificationReceipt,
    receipts: tuple[InflectionDerivedMetricsReceipt, ...],
) -> InflectionDerivedMetricsEvaluation:
    values = dict(
        canonical_instrument_id=instrument, canonical_issuer_id=issuer, statement_scope=scope, as_of=as_of,
        company_type_receipt_id=company_type_receipt.receipt_id,
        company_type_receipt_fingerprint=company_type_receipt.fingerprint,
        receipts=tuple(sorted(receipts, key=lambda value: value.metric.value)),
    )
    return InflectionDerivedMetricsEvaluation(**values, fingerprint=_fingerprint(_evaluation_payload_values(values)))


def _validate_metric_state(value: InflectionDerivedMetricsReceipt) -> None:
    if value.current_period is not None and financial_metric_period_identity_fingerprint(value.current_period) != value.current_period.fingerprint:
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_PERIOD_TAMPERED")
    for trajectory in (value.current_yoy, value.previous_yoy):
        if trajectory is not None and financial_metric_trajectory_fingerprint(trajectory) != trajectory.fingerprint:
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_TRAJECTORY_TAMPERED")
    if value.source_bundle_fingerprint is not None and not _MANIFEST_FINGERPRINT.fullmatch(value.source_bundle_fingerprint):
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_BUNDLE_LINEAGE_INVALID")
    if value.filing_lineage.fingerprint != _fingerprint(_filing_payload(value.filing_lineage)):
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_FILING_TAMPERED")
    if value.calendar_alignment.fingerprint != _fingerprint(_alignment_payload(value.calendar_alignment)):
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_ALIGNMENT_TAMPERED")
    if value.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED:
        if value.acceleration is None or value.current_yoy is None or value.previous_yoy is None or not value.input_facts:
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_ACCELERATION_FIELDS_REQUIRED")
    elif value.acceleration is not None:
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_ACCELERATION_FORBIDDEN")
    if value.state is InflectionDerivedMetricsState.YOY_OBSERVED:
        if value.current_yoy is None or value.current_yoy.relative_delta is None:
            raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_YOY_FIELDS_REQUIRED")
    if value.state is InflectionDerivedMetricsState.NOT_APPLICABLE and value.company_type is PitCompanyType.NON_FINANCIAL:
        raise InflectionDerivedMetricsError("INFLECTION_DERIVED_RECEIPT_COMPANY_TYPE_CONTRADICTION")


def _financial_fact_fingerprint(value: FinancialFact) -> str:
    return "sha256:" + manifest_fingerprint(
        fact_id=value.fact_id, instrument=value.instrument.instrument_id, metric=value.metric.value,
        value=str(value.value), period_type=value.period_type.value, value_basis=value.value_basis.value,
        period_start=_time(value.period_start), period_end=_time(value.period_end), fiscal_year=value.fiscal_year,
        fiscal_quarter=value.fiscal_quarter, scope=value.statement_scope.value, kind=value.fact_kind.value,
        currency=value.currency, unit=value.unit, scale=value.scale.value, filing_id=value.filing_id,
        published_at=_time(value.published_at), received_at=_time(value.received_at),
        normalization_version=value.normalization_version, parent_fact_ids=tuple(sorted(set(value.parent_fact_ids))),
        revision_of_fact_id=value.revision_of_fact_id, provenance=tuple(sorted(set(value.provenance))),
    )


def _corporate_filing_fingerprint(value: CorporateFiling) -> str:
    financial = value.financial_result
    return manifest_fingerprint(
        filing_id=value.filing_id, instrument=value.instrument.instrument_id, exchange=value.exchange.value,
        source=value.source, source_quality=value.source_quality.value, filing_type=value.filing_type.value,
        announced_at=_time(value.announced_at), received_at=_time(value.received_at), period_end=_time(value.period_end),
        financial_period_end=None if financial is None else _time(financial.period_end),
        financial_scope=None if financial is None else financial.result_scope,
        financial_type=None if financial is None else financial.result_type,
        financial_revised=None if financial is None else financial.revised,
        source_reference=value.source_reference, document_reference=value.document_reference,
        revision_of_filing_id=value.revision_of_filing_id,
        provenance=(value.provenance.source_reference,) if value.provenance.source_reference else (),
        normalization_version=value.normalization_version,
    )


def _receipt_id(identity: dict) -> str:
    return "inflection-derived:" + _hash(identity)[:24]


def _receipt_identity(value: InflectionDerivedMetricsReceipt) -> dict:
    return _receipt_identity_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field not in {"receipt_id", "fingerprint", "contract_id", "contract_version", "actionability", "execution_status", "research_status"}})


def _receipt_identity_values(values: dict) -> dict:
    return {
        "contract_id": CONTRACT_ID, "contract_version": CONTRACT_VERSION,
        "instrument": values["canonical_instrument_id"], "issuer": values["canonical_issuer_id"],
        "company_type_receipt_id": values["company_type_receipt_id"],
        "company_type_receipt_fingerprint": values["company_type_receipt_fingerprint"],
        "scope": values["statement_scope"].value, "metric": values["metric"].value,
        "as_of": _time(values["as_of"]),
        "current_period_fingerprint": None if values["current_period"] is None else values["current_period"].fingerprint,
        "current_yoy_fingerprint": None if values["current_yoy"] is None else values["current_yoy"].fingerprint,
        "previous_yoy_fingerprint": None if values["previous_yoy"] is None else values["previous_yoy"].fingerprint,
        "input_facts": tuple((value.fact_id, value.fact_fingerprint) for value in values["input_facts"]),
        "source_bundle_fingerprint": values["source_bundle_fingerprint"], "proposal_id": values["proposal_id"],
        "proposal_version": values["proposal_version"],
    }


def _receipt_payload(value: InflectionDerivedMetricsReceipt) -> dict:
    return _receipt_payload_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field not in {"fingerprint"}})


def _receipt_payload_values(values: dict) -> dict:
    return _receipt_identity_values(values) | {
        "receipt_id": values["receipt_id"], "company_type": None if values["company_type"] is None else values["company_type"].value,
        "current_yoy_relative_delta": None if values["current_yoy"] is None else _decimal(values["current_yoy"].relative_delta),
        "previous_yoy_relative_delta": None if values["previous_yoy"] is None else _decimal(values["previous_yoy"].relative_delta),
        "acceleration": _decimal(values["acceleration"]), "state": values["state"].value,
        "reasons": tuple(item.value for item in values["reasons"]),
        "filing_lineage_fingerprint": values["filing_lineage"].fingerprint,
        "calendar_alignment_fingerprint": values["calendar_alignment"].fingerprint,
        "provenance": values["provenance"], "actionability": values.get("actionability", "WATCH_ONLY"),
        "execution_status": values.get("execution_status", "NON_EXECUTABLE"),
        "research_status": values.get("research_status", "RESEARCH_ONLY"),
    }


def _filing_payload(value: ExactFinancialResultFilingLineage) -> dict:
    return _filing_payload_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _filing_payload_values(values: dict) -> dict:
    return {
        "state": values["state"].value, "filing_id": values["filing_id"], "filing_fingerprint": values["filing_fingerprint"],
        "instrument": values["canonical_instrument_id"], "scope": values["statement_scope"].value,
        "reporting_period_end": _time(values["reporting_period_end"]), "announced_at": _time(values["announced_at"]),
        "received_at": _time(values["received_at"]), "source": values["source"],
        "source_reference": values["source_reference"], "revision_of_filing_id": values["revision_of_filing_id"],
        "provenance": values["provenance"],
    }


def _alignment_payload(value: EventCalendarAlignmentReceipt) -> dict:
    return _alignment_payload_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"})


def _alignment_payload_values(values: dict) -> dict:
    return {
        "filing_lineage_fingerprint": values["filing_lineage_fingerprint"],
        "filing_date": None if values["filing_date"] is None else values["filing_date"].isoformat(),
        "state": values["state"].value,
        "prior_trading_session": None if values["prior_trading_session"] is None else values["prior_trading_session"].isoformat(),
        "next_trading_session": None if values["next_trading_session"] is None else values["next_trading_session"].isoformat(),
        "intraday_state": values["intraday_state"].value, "reason": values["reason"],
    }


def _evaluation_payload(value: InflectionDerivedMetricsEvaluation) -> dict:
    return _evaluation_payload_values({field: getattr(value, field) for field in value.__dataclass_fields__ if field not in {"fingerprint"}})


def _evaluation_payload_values(values: dict) -> dict:
    return {
        "contract_id": values.get("contract_id", CONTRACT_ID), "contract_version": values.get("contract_version", CONTRACT_VERSION),
        "instrument": values["canonical_instrument_id"], "issuer": values["canonical_issuer_id"],
        "scope": values["statement_scope"].value, "as_of": _time(values["as_of"]),
        "company_type_receipt_id": values["company_type_receipt_id"],
        "company_type_receipt_fingerprint": values["company_type_receipt_fingerprint"],
        "receipt_fingerprints": tuple(value.fingerprint for value in values["receipts"]),
    }


def _fingerprint(values: dict) -> str:
    return "sha256:" + _hash(values)


def _hash(values: dict) -> str:
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value: datetime) -> datetime:
    if not _aware(value):
        raise InflectionDerivedMetricsError("INFLECTION_TIMEZONE_AWARE_AS_OF_REQUIRED")
    return value.astimezone(UTC)


def _time(value: datetime | None) -> str | None:
    return None if value is None else _utc(value).isoformat()


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


__all__ = (
    "CONTRACT_ID", "CONTRACT_VERSION", "EventCalendarAlignmentReceipt", "EventCalendarAlignmentState",
    "ExactFinancialResultFilingLineage", "FilingLineageState", "InflectionDerivedMetricsError",
    "InflectionDerivedMetricsEvaluation", "InflectionDerivedMetricsReason", "InflectionDerivedMetricsReceipt",
    "InflectionDerivedMetricsState", "InflectionFactLineage", "InflectionResearchMetric",
    "IntradayEventSessionState",
    "evaluate_inflection_testable_derived_metrics_and_event_alignment",
    "serialize_inflection_testable_derived_metrics",
)
