"""Pure selected-vintage to factual financial-observation materialization.

This module consumes one already-selected fact and its explicit selector
result.  It neither selects a fact nor accesses storage, providers, runtime
state, or any downstream research/trajectory layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.fundamentals.financial_fact_vintage_selection_policy import (
    FinancialFactVintageSelectionStatus,
)
from app.fundamentals.financial_fact_vintage_selector import (
    FinancialFactSemanticKey,
    FinancialFactVintageSelection,
    financial_fact_vintage_selection_fingerprint,
)
from app.fundamentals.financial_metric_observation_schema import (
    CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA,
    FinancialMetricObservation,
    FinancialMetricObservationSchemaApprovalStatus,
    FinancialMetricPeriodIdentity,
    FinancialMetricPeriodIdentityStrength,
    FrozenFinancialMetricObservationSchema,
    financial_metric_observation_schema_fingerprint,
    financial_metric_observation_fingerprint_values,
    financial_metric_period_identity_fingerprint,
    financial_metric_period_identity_fingerprint_values,
    financial_metric_source_fact_semantic_fingerprint_values,
)
from app.fundamentals.models import FinancialFact, FinancialPeriodType, FinancialValueBasis
from app.historical.guard import manifest_fingerprint


class FinancialMetricObservationMaterializationStatus(StrEnum):
    MATERIALIZED = "MATERIALIZED"
    REJECTED = "REJECTED"


class FinancialMetricObservationMaterializationReason(StrEnum):
    SELECTION_NOT_SELECTED = "SELECTION_NOT_SELECTED"
    SELECTED_FACT_ID_MISMATCH = "SELECTED_FACT_ID_MISMATCH"
    SELECTION_SEMANTIC_KEY_MISMATCH = "SELECTION_SEMANTIC_KEY_MISMATCH"
    SELECTION_LINEAGE_INVALID = "SELECTION_LINEAGE_INVALID"
    SOURCE_FACT_UNAVAILABLE_AT_SELECTION_AS_OF = "SOURCE_FACT_UNAVAILABLE_AT_SELECTION_AS_OF"
    SCHEMA_UNSUPPORTED = "SCHEMA_UNSUPPORTED"
    SCHEMA_MALFORMED = "SCHEMA_MALFORMED"
    NONFINITE_DECIMAL = "NONFINITE_DECIMAL"
    REPRESENTATION_REQUIRED = "REPRESENTATION_REQUIRED"
    PERIOD_END_REQUIRED = "PERIOD_END_REQUIRED"
    PERIOD_IDENTITY_INSUFFICIENT = "PERIOD_IDENTITY_INSUFFICIENT"
    PIT_VISIBILITY_INVALID = "PIT_VISIBILITY_INVALID"
    SOURCE_FACT_SEMANTIC_FINGERPRINT_INVALID = "SOURCE_FACT_SEMANTIC_FINGERPRINT_INVALID"


@dataclass(frozen=True, slots=True)
class FinancialMetricObservationMaterializationResult:
    """Immutable factual outcome for exactly one supplied fact/selection pair."""

    source_fact_id: str
    selection_result_fingerprint: str
    status: FinancialMetricObservationMaterializationStatus
    observation: FinancialMetricObservation | None
    reasons: tuple[FinancialMetricObservationMaterializationReason, ...]
    schema_id: str
    schema_version: str
    schema_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.source_fact_id, self.selection_result_fingerprint, self.schema_id, self.schema_version, self.schema_fingerprint)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZATION_REQUIRED_FIELD")
        if self.reasons != tuple(sorted(set(self.reasons), key=lambda value: value.value)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZATION_REASONS_NONCANONICAL")
        if self.status is FinancialMetricObservationMaterializationStatus.MATERIALIZED:
            if self.observation is None or self.reasons:
                raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZATION_SUCCESS_INVALID")
        elif self.observation is not None or not self.reasons:
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZATION_REJECTION_INVALID")
        if self.fingerprint != financial_metric_observation_materialization_result_fingerprint(self):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZATION_FINGERPRINT_MISMATCH")


def materialize_financial_metric_observation(
    fact: FinancialFact,
    *,
    selection: FinancialFactVintageSelection,
    schema: FrozenFinancialMetricObservationSchema,
) -> FinancialMetricObservationMaterializationResult:
    """Faithfully represent one already-selected fact, without selecting it."""

    if not isinstance(fact, FinancialFact):
        raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZER_FACT_TYPE_INVALID")
    if not isinstance(selection, FinancialFactVintageSelection):
        raise ValueError("FINANCIAL_METRIC_OBSERVATION_MATERIALIZER_SELECTION_TYPE_INVALID")

    schema_failure = _schema_failure(schema)
    if schema_failure is not None:
        return _rejected(fact, selection, schema, schema_failure)
    if financial_fact_vintage_selection_fingerprint(selection) != selection.fingerprint:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SELECTION_LINEAGE_INVALID)
    if selection.status is not FinancialFactVintageSelectionStatus.SELECTED:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SELECTION_NOT_SELECTED)
    if selection.selected_fact_id != fact.fact_id:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SELECTED_FACT_ID_MISMATCH)
    if not _selection_binds_fact(selection, fact):
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SELECTION_SEMANTIC_KEY_MISMATCH)
    if not _aware(selection.as_of) or fact.available_at > selection.as_of:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SOURCE_FACT_UNAVAILABLE_AT_SELECTION_AS_OF)
    if not isinstance(fact.value, Decimal) or not fact.value.is_finite():
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.NONFINITE_DECIMAL)
    if not all((fact.currency, fact.unit, fact.normalization_version)):
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.REPRESENTATION_REQUIRED)
    if fact.period_end is None or not _aware(fact.period_end):
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.PERIOD_END_REQUIRED)
    if not all(_aware(value) for value in (fact.published_at, fact.received_at)) or fact.received_at < fact.published_at:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.PIT_VISIBILITY_INVALID)

    period = _period_identity(fact)
    if period.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT:
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.PERIOD_IDENTITY_INSUFFICIENT)
    source_values = _source_values(fact, period)
    try:
        source_fingerprint = financial_metric_source_fact_semantic_fingerprint_values(source_values)
    except (KeyError, TypeError, ValueError, AttributeError):
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SOURCE_FACT_SEMANTIC_FINGERPRINT_INVALID)
    values = dict(
        **source_values,
        visible_as_of=fact.available_at,
        source_fact_id=fact.fact_id,
        selection_policy_id=selection.policy_id,
        selection_policy_version=selection.policy_version,
        selection_policy_fingerprint=selection.policy_fingerprint,
        selection_result_fingerprint=selection.fingerprint,
        source_fact_semantic_fingerprint=source_fingerprint,
        schema_id=schema.schema_id,
        schema_version=schema.version,
        schema_fingerprint=schema.fingerprint,
    )
    try:
        observation = FinancialMetricObservation(
            **values,
            fingerprint=financial_metric_observation_fingerprint_values(values),
        )
    except (TypeError, ValueError):
        return _rejected(fact, selection, schema, FinancialMetricObservationMaterializationReason.SOURCE_FACT_SEMANTIC_FINGERPRINT_INVALID)
    return _result(fact, selection, schema, FinancialMetricObservationMaterializationStatus.MATERIALIZED, observation, ())


def financial_metric_observation_materialization_result_fingerprint(
    value: FinancialMetricObservationMaterializationResult,
) -> str:
    return manifest_fingerprint(
        source_fact_id=value.source_fact_id,
        selection_result_fingerprint=value.selection_result_fingerprint,
        status=value.status.value,
        observation_fingerprint=None if value.observation is None else value.observation.fingerprint,
        reasons=tuple(reason.value for reason in value.reasons),
        schema_id=value.schema_id,
        schema_version=value.schema_version,
        schema_fingerprint=value.schema_fingerprint,
    )


def _schema_failure(
    schema: FrozenFinancialMetricObservationSchema,
) -> FinancialMetricObservationMaterializationReason | None:
    if not isinstance(schema, FrozenFinancialMetricObservationSchema):
        return FinancialMetricObservationMaterializationReason.SCHEMA_MALFORMED
    expected = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA
    if (schema.schema_id, schema.version, schema.fingerprint) != (expected.schema_id, expected.version, expected.fingerprint):
        return FinancialMetricObservationMaterializationReason.SCHEMA_UNSUPPORTED
    if financial_metric_observation_schema_fingerprint(schema) != schema.fingerprint:
        return FinancialMetricObservationMaterializationReason.SCHEMA_MALFORMED
    if schema.approval_status is not FinancialMetricObservationSchemaApprovalStatus.APPROVED:
        return FinancialMetricObservationMaterializationReason.SCHEMA_MALFORMED
    # The frozen schema remains intentionally inactive; that state is valid here.
    if schema.selected_for_future_materializer or schema.active:
        return FinancialMetricObservationMaterializationReason.SCHEMA_MALFORMED
    return None


def _selection_binds_fact(selection: FinancialFactVintageSelection, fact: FinancialFact) -> bool:
    key = selection.semantic_key
    if key is None:
        return False
    if (selection.policy_id, selection.policy_version, selection.policy_fingerprint) != (
        CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.selector_policy_id,
        CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.selector_policy_version,
        CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.selector_policy_fingerprint,
    ):
        return False
    try:
        fact_key = FinancialFactSemanticKey(
            canonical_instrument_id=fact.instrument.instrument_id,
            metric=fact.metric,
            fact_kind=fact.fact_kind,
            statement_scope=fact.statement_scope,
            period_type=fact.period_type,
            value_basis=fact.value_basis,
            period_start=fact.period_start,
            period_end=fact.period_end,
            fiscal_year=fact.fiscal_year,
            fiscal_quarter=fact.fiscal_quarter,
            value_dimension=fact.value_dimension,
            currency=fact.currency,
            unit=fact.unit,
            scale=fact.scale,
            normalization_version=fact.normalization_version,
        )
    except (TypeError, ValueError, AttributeError):
        return False
    return key == fact_key


def _period_identity(fact: FinancialFact) -> FinancialMetricPeriodIdentity:
    strength = _period_strength(fact)
    values = dict(
        period_type=fact.period_type,
        value_basis=fact.value_basis,
        period_start=fact.period_start,
        period_end=fact.period_end,
        fiscal_year=fact.fiscal_year,
        fiscal_quarter=fact.fiscal_quarter,
        statement_scope=fact.statement_scope,
        value_dimension=fact.value_dimension,
        currency=fact.currency,
        unit=fact.unit,
        scale=fact.scale,
        normalization_version=fact.normalization_version,
        strength=strength,
    )
    return FinancialMetricPeriodIdentity(
        **values,
        fingerprint=financial_metric_period_identity_fingerprint_values(values),
    )


def _period_strength(fact: FinancialFact) -> FinancialMetricPeriodIdentityStrength:
    if fact.period_end is None or not _aware(fact.period_end):
        return FinancialMetricPeriodIdentityStrength.INSUFFICIENT
    if not isinstance(fact.value_basis, FinancialValueBasis) or fact.value_basis is FinancialValueBasis.UNKNOWN:
        return FinancialMetricPeriodIdentityStrength.PARTIAL
    if fact.period_type is FinancialPeriodType.POINT_IN_TIME:
        return FinancialMetricPeriodIdentityStrength.COMPLETE
    if fact.period_start is None or not _aware(fact.period_start):
        return FinancialMetricPeriodIdentityStrength.PARTIAL
    if fact.period_type is FinancialPeriodType.QUARTERLY:
        return FinancialMetricPeriodIdentityStrength.COMPLETE if fact.fiscal_year and fact.fiscal_quarter else FinancialMetricPeriodIdentityStrength.PARTIAL
    if fact.period_type is FinancialPeriodType.ANNUAL:
        return FinancialMetricPeriodIdentityStrength.COMPLETE if fact.fiscal_year else FinancialMetricPeriodIdentityStrength.PARTIAL
    return FinancialMetricPeriodIdentityStrength.COMPLETE


def _source_values(fact: FinancialFact, period: FinancialMetricPeriodIdentity) -> dict:
    return dict(
        canonical_instrument_id=fact.instrument.instrument_id,
        metric=fact.metric, fact_kind=fact.fact_kind, value=fact.value,
        currency=fact.currency, unit=fact.unit, scale=fact.scale,
        statement_scope=fact.statement_scope, period_identity=period, source=fact.source,
        filing_id=fact.filing_id, source_reference=fact.source_reference,
        published_at=fact.published_at, received_at=fact.received_at,
        revision_of_fact_id=fact.revision_of_fact_id,
        parent_fact_ids=tuple(sorted(set(fact.parent_fact_ids))),
        quality_flags=tuple(sorted(set(fact.quality_flags), key=lambda value: value.value)),
        provenance=tuple(sorted(set(fact.provenance))),
        normalization_version=fact.normalization_version,
    )


def _rejected(
    fact: FinancialFact,
    selection: FinancialFactVintageSelection,
    schema: FrozenFinancialMetricObservationSchema,
    reason: FinancialMetricObservationMaterializationReason,
) -> FinancialMetricObservationMaterializationResult:
    return _result(fact, selection, schema, FinancialMetricObservationMaterializationStatus.REJECTED, None, (reason,))


def _result(
    fact: FinancialFact,
    selection: FinancialFactVintageSelection,
    schema: FrozenFinancialMetricObservationSchema,
    status: FinancialMetricObservationMaterializationStatus,
    observation: FinancialMetricObservation | None,
    reasons: tuple[FinancialMetricObservationMaterializationReason, ...],
) -> FinancialMetricObservationMaterializationResult:
    values = dict(
        source_fact_id=fact.fact_id,
        selection_result_fingerprint=selection.fingerprint,
        status=status,
        observation=observation,
        reasons=tuple(sorted(set(reasons), key=lambda value: value.value)),
        schema_id=getattr(schema, "schema_id", "invalid-schema"),
        schema_version=getattr(schema, "version", "invalid-schema"),
        schema_fingerprint=getattr(schema, "fingerprint", "invalid-schema"),
    )
    return FinancialMetricObservationMaterializationResult(
        **values,
        fingerprint=manifest_fingerprint(
            source_fact_id=values["source_fact_id"], selection_result_fingerprint=values["selection_result_fingerprint"],
            status=values["status"].value,
            observation_fingerprint=None if observation is None else observation.fingerprint,
            reasons=tuple(reason.value for reason in values["reasons"]),
            schema_id=values["schema_id"], schema_version=values["schema_version"], schema_fingerprint=values["schema_fingerprint"],
        ),
    )


def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def _time(value: datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).isoformat()


__all__ = (
    "FinancialMetricObservationMaterializationReason",
    "FinancialMetricObservationMaterializationResult",
    "FinancialMetricObservationMaterializationStatus",
    "financial_metric_observation_materialization_result_fingerprint",
    "materialize_financial_metric_observation",
)
