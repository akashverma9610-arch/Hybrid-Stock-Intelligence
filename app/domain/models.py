from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Any, Mapping


class ObservationKind(StrEnum):
    PRICE_BAR = "price_bar"
    VOLUME = "volume"
    FUNDAMENTAL = "fundamental"
    CORPORATE_EVENT = "corporate_event"
    INDEX = "index"
    SECTOR = "sector"
    RESEARCH = "research"


class FinancialPeriodType(StrEnum):
    QUARTERLY = "quarterly"
    ANNUAL = "annual"
    TTM = "ttm"


class DataQuality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    FUTURE = "future"
    UNKNOWN = "unknown"


class ValidationStatus(StrEnum):
    VALID = "valid"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    INVALID = "invalid"
    DUPLICATE = "duplicate"
    FUTURE_TIMESTAMP = "future_timestamp"
    QUALITY_WARNING = "quality_warning"


@dataclass(frozen=True, slots=True)
class Instrument:
    id: str
    symbol: str
    exchange: str
    isin: str | None = None


@dataclass(frozen=True, slots=True)
class Freshness:
    status: FreshnessStatus
    observed_timestamp: datetime | None
    evaluated_timestamp: datetime
    age_seconds: float | None
    maximum_age_seconds: float | None


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    source_identifier: str | None
    market_timestamp: datetime | object
    retrieved_timestamp: datetime | object
    data_quality: DataQuality | object = DataQuality.UNKNOWN
    freshness: Freshness | None = None
    original_record: Mapping[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: ValidationStatus
    validated_timestamp: datetime
    issues: tuple[ValidationIssue, ...] = ()
    freshness: Freshness | None = None

    @property
    def eligible_for_analysis(self) -> bool:
        """Fail closed: only explicitly valid data can reach later engines."""
        return self.status is ValidationStatus.VALID


@dataclass(frozen=True, slots=True)
class DerivedObservationMetadata:
    input_references: tuple[str, ...]
    calculation_name: str
    parameters: Mapping[str, Any]
    calculation_version: str
    derived_timestamp: datetime


@dataclass(frozen=True, slots=True)
class MarketObservation:
    id: str
    instrument: Instrument
    kind: ObservationKind | object
    payload: Mapping[str, Any] | object
    provenance: Provenance
    validation: ValidationResult | None = None
    derivation: DerivedObservationMetadata | None = None

    def with_validation(self, validation: ValidationResult) -> "MarketObservation":
        return replace(self, validation=validation)


@dataclass(frozen=True, slots=True)
class FinancialObservation(MarketObservation):
    """Typed mock filing record; period/publication semantics remain explicit."""
    period_end: datetime | None = None
    publication_timestamp: datetime | None = None
    period_type: FinancialPeriodType | None = None
    supersedes_observation_id: str | None = None


# These typed observation specializations intentionally add no guessed financial
# fields. Their payload values must come from a future approved provider or fixture.
@dataclass(frozen=True, slots=True)
class PriceBar(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class VolumeObservation(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class FundamentalObservation(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class CorporateEvent(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class IndexObservation(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class SectorObservation(MarketObservation):
    pass


@dataclass(frozen=True, slots=True)
class ResearchItem(MarketObservation):
    pass


class StrategyStatus(StrEnum):
    DRAFT = "draft"
    EXPERIMENT = "experiment"
    VALIDATION = "validation"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"
    REJECTED = "rejected"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StrategyValidationStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    REQUIRES_APPROVAL = "requires_approval"


class ConfigurationValueStatus(StrEnum):
    UNSPECIFIED = "UNSPECIFIED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"


class EvidenceType(StrEnum):
    FACT = "fact"
    DATA = "data"
    INTERPRETATION = "interpretation"
    INFERENCE = "inference"


class GateOutcome(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class StrategyVersionReference:
    strategy_id: str
    version: str


class DiagnosticStrategyLineageType(StrEnum):
    GENERIC_STRATEGY_VERSION = "GENERIC_STRATEGY_VERSION"
    CANONICAL_DIAGNOSTIC_STRATEGY = "CANONICAL_DIAGNOSTIC_STRATEGY"


@dataclass(frozen=True, slots=True)
class AuthorReviewerMetadata:
    author_id: str
    reviewer_id: str | None = None
    review_notes: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyConfiguration:
    """Explicit parameters only; undecided decisions retain their approval state."""

    scoring_weights: Mapping[str, float | ConfigurationValueStatus] = field(default_factory=dict)
    rotation_threshold: float | ConfigurationValueStatus = ConfigurationValueStatus.REQUIRES_APPROVAL
    minimum_risk_reward: float | ConfigurationValueStatus = ConfigurationValueStatus.REQUIRES_APPROVAL
    execution_gate_parameters: Mapping[str, Any] = field(default_factory=dict)
    portfolio_heat_limits: Mapping[str, Any] = field(default_factory=dict)
    sector_exposure_limits: Mapping[str, Any] = field(default_factory=dict)
    position_limits: Mapping[str, Any] = field(default_factory=dict)
    capital_velocity_rule: Mapping[str, Any] | ConfigurationValueStatus = ConfigurationValueStatus.REQUIRES_APPROVAL
    earnings_blackout: Mapping[str, Any] | ConfigurationValueStatus = ConfigurationValueStatus.REQUIRES_APPROVAL
    risk_parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "scoring_weights", "execution_gate_parameters", "portfolio_heat_limits", "sector_exposure_limits",
            "position_limits", "risk_parameters",
        ):
            object.__setattr__(self, name, _freeze_mapping(getattr(self, name)))
        for name in ("capital_velocity_rule", "earnings_blackout"):
            value = getattr(self, name)
            if isinstance(value, Mapping):
                object.__setattr__(self, name, _freeze_mapping(value))


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    strategy_id: str
    version: str
    name: str
    status: StrategyStatus
    created_at: datetime
    effective_from: datetime | None
    effective_to: datetime | None
    description: str
    configuration: StrategyConfiguration
    rule_definition_version: str | ConfigurationValueStatus
    scoring_configuration_version: str | ConfigurationValueStatus
    execution_gate_configuration_version: str | ConfigurationValueStatus
    risk_configuration_version: str | ConfigurationValueStatus
    benchmark_configuration_version: str | ConfigurationValueStatus
    author_reviewer: AuthorReviewerMetadata
    approval_status: ApprovalStatus
    validation_status: StrategyValidationStatus
    parent_strategy_version: StrategyVersionReference | None = None

    @property
    def reference(self) -> StrategyVersionReference:
        return StrategyVersionReference(self.strategy_id, self.version)


@dataclass(frozen=True, slots=True)
class StrategyLifecycleEvent:
    id: str
    strategy_version: StrategyVersionReference
    status: StrategyStatus
    approval_status: ApprovalStatus
    validation_status: StrategyValidationStatus
    occurred_at: datetime
    actor_id: str
    rationale: str


@dataclass(frozen=True, slots=True)
class Evidence:
    id: str
    source: str
    source_identifier: str | None
    timestamp: datetime
    observation_ids: tuple[str, ...]
    evidence_type: EvidenceType
    factual_content_reference: str
    confidence: float | None
    provenance: Provenance


@dataclass(frozen=True, slots=True)
class DiagnosticResult:
    id: str
    instrument_id: str
    rule_id: str
    strategy_version: StrategyVersionReference
    result: str
    score: float | None
    confidence: float | None
    evidence_ids: tuple[str, ...]
    input_observation_ids: tuple[str, ...]
    evaluated_at: datetime
    as_of_timestamp: datetime
    strategy_lineage_type: DiagnosticStrategyLineageType = DiagnosticStrategyLineageType.GENERIC_STRATEGY_VERSION
    canonical_strategy_fingerprint: str | None = None
    canonical_limitations_fingerprint: str | None = None
    diagnostic_fingerprint: str | None = None


def canonical_diagnostic_result_fingerprint(result: DiagnosticResult) -> str:
    """Fingerprint the canonical output and its exact typed governance lineage."""
    if result.strategy_lineage_type is not DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY:
        raise ValueError("Only canonical diagnostic strategy results have a canonical diagnostic fingerprint.")
    if not result.canonical_strategy_fingerprint:
        raise ValueError("Canonical diagnostic strategy fingerprint is required.")
    if not result.canonical_limitations_fingerprint:
        raise ValueError("Canonical diagnostic strategy limitations fingerprint is required.")
    payload = {
        "as_of_timestamp": result.as_of_timestamp.isoformat(),
        "canonical_strategy_fingerprint": result.canonical_strategy_fingerprint,
        "canonical_limitations_fingerprint": result.canonical_limitations_fingerprint,
        "confidence": result.confidence,
        "evaluated_at": result.evaluated_at.isoformat(),
        "evidence_ids": list(result.evidence_ids),
        "id": result.id,
        "input_observation_ids": list(result.input_observation_ids),
        "instrument_id": result.instrument_id,
        "result": result.result,
        "rule_id": result.rule_id,
        "score": result.score,
        "strategy_id": result.strategy_version.strategy_id,
        "strategy_lineage_type": result.strategy_lineage_type.value,
        "strategy_version": result.strategy_version.version,
    }
    return "sha256:" + sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def canonical_diagnostic_result(
    *, id: str, instrument_id: str, rule_id: str, strategy_version: StrategyVersionReference,
    canonical_strategy_fingerprint: str, canonical_limitations_fingerprint: str, result: str,
    score: float | None, confidence: float | None,
    evidence_ids: tuple[str, ...], input_observation_ids: tuple[str, ...], evaluated_at: datetime,
    as_of_timestamp: datetime,
) -> DiagnosticResult:
    """Construct a typed canonical result without a generic strategy-version anchor."""
    # SQLite REAL columns rehydrate integral values as ``1.0``.  Canonicalize
    # numeric values before fingerprinting so a newly written typed result has
    # identical lineage before and after durable storage.
    score = None if score is None else float(score)
    confidence = None if confidence is None else float(confidence)
    value = DiagnosticResult(
        id, instrument_id, rule_id, strategy_version, result, score, confidence, evidence_ids,
        input_observation_ids, evaluated_at, as_of_timestamp,
        DiagnosticStrategyLineageType.CANONICAL_DIAGNOSTIC_STRATEGY, canonical_strategy_fingerprint,
        canonical_limitations_fingerprint,
    )
    return replace(value, diagnostic_fingerprint=canonical_diagnostic_result_fingerprint(value))


@dataclass(frozen=True, slots=True)
class ScorecardComponent:
    component_id: str
    weight: float | ConfigurationValueStatus
    score: float | None
    confidence: float | None
    evidence_ids: tuple[str, ...]
    missing_data_treatment: str | ConfigurationValueStatus


@dataclass(frozen=True, slots=True)
class Scorecard:
    id: str
    instrument_id: str
    strategy_version: StrategyVersionReference
    evaluated_at: datetime
    as_of_timestamp: datetime
    components: tuple[ScorecardComponent, ...]
    aggregate_score: float | None


@dataclass(frozen=True, slots=True)
class GateDecision:
    id: str
    gate_name: str
    strategy_version: StrategyVersionReference
    outcome: GateOutcome
    rationale: str
    evidence_ids: tuple[str, ...]
    parameters_used: Mapping[str, Any]
    evaluated_at: datetime
    as_of_timestamp: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters_used", _freeze_mapping(self.parameters_used))


@dataclass(frozen=True, slots=True)
class AnalyticalDecisionReconstruction:
    id: str
    strategy_version: StrategyVersionReference
    snapshot_id: str
    evidence: tuple[Evidence, ...]
    diagnostics: tuple[DiagnosticResult, ...]
    scorecard: Scorecard | None
    gate_decisions: tuple[GateDecision, ...]
    fingerprint: str


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType({key: _freeze_value(item) for key, item in value.items()})


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze_value(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class AsOfSnapshot:
    id: str
    as_of_timestamp: datetime
    created_timestamp: datetime
    inclusion_policy: str
    observations: tuple[MarketObservation, ...] = field(default_factory=tuple)
