"""Frozen passive schema contracts for future financial metric observations.

This module defines immutable value objects and deterministic fingerprints only.
It does not accept FinancialFact, select a vintage, materialize an observation,
query storage, or perform trajectory or investment interpretation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import (
    FinancialMetric,
    FinancialPeriodType,
    FinancialQualityFlag,
    FinancialValueBasis,
    FinancialValueDimension,
    NumericScale,
    StatementScope,
)
from app.historical.guard import manifest_fingerprint


_SCHEMA_ID = "financial-metric-observation-schema"
_SCHEMA_VERSION = "v1-approved"
_SELECTION_POLICY_ID = "financial-fact-vintage-selection-policy"
_SELECTION_POLICY_VERSION = "v1-approved"
_SELECTION_POLICY_FINGERPRINT = "862dc470ebd58abd2d066f2604440908eaf3aa9827e6c93b588b5f1bf806fc13"


class FinancialMetricObservationSchemaApprovalStatus(StrEnum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"


class FinancialMetricPeriodIdentityStrength(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"


class FinancialMetricObservationAdmissionRequirement(StrEnum):
    CANONICAL_INSTRUMENT = "CANONICAL_INSTRUMENT"
    METRIC = "METRIC"
    FACT_KIND = "FACT_KIND"
    FINITE_DECIMAL_VALUE = "FINITE_DECIMAL_VALUE"
    CURRENCY = "CURRENCY"
    UNIT = "UNIT"
    SCALE = "SCALE"
    STATEMENT_SCOPE = "STATEMENT_SCOPE"
    PERIOD_TYPE = "PERIOD_TYPE"
    PERIOD_BASIS = "PERIOD_BASIS"
    PERIOD_END = "PERIOD_END"
    PIT_VISIBILITY = "PIT_VISIBILITY"
    SOURCE_FACT_ID = "SOURCE_FACT_ID"
    SOURCE_FACT_SEMANTIC_FINGERPRINT = "SOURCE_FACT_SEMANTIC_FINGERPRINT"
    SELECTED_FACT_VINTAGE_LINEAGE = "SELECTED_FACT_VINTAGE_LINEAGE"


class FinancialMetricSourceFactSemanticField(StrEnum):
    CANONICAL_INSTRUMENT = "CANONICAL_INSTRUMENT"
    METRIC = "METRIC"
    FACT_KIND = "FACT_KIND"
    DECIMAL_VALUE = "DECIMAL_VALUE"
    CURRENCY = "CURRENCY"
    UNIT = "UNIT"
    SCALE = "SCALE"
    STATEMENT_SCOPE = "STATEMENT_SCOPE"
    PERIOD_IDENTITY = "PERIOD_IDENTITY"
    SOURCE_IDENTITY = "SOURCE_IDENTITY"
    FILING_IDENTITY = "FILING_IDENTITY"
    PUBLISHED_AT = "PUBLISHED_AT"
    RECEIVED_AT = "RECEIVED_AT"
    REVISION_LINEAGE = "REVISION_LINEAGE"
    QUALITY_FLAGS = "QUALITY_FLAGS"
    PROVENANCE = "PROVENANCE"
    NORMALIZATION_VERSION = "NORMALIZATION_VERSION"


class FinancialMetricObservationExclusion(StrEnum):
    FACT_VINTAGE_SELECTION = "FACT_VINTAGE_SELECTION"
    OBSERVATION_MATERIALIZATION = "OBSERVATION_MATERIALIZATION"
    TRAJECTORY = "TRAJECTORY"
    QOQ_YOY_TTM = "QOQ_YOY_TTM"
    DIRECTIONALITY = "DIRECTIONALITY"
    MATERIALITY = "MATERIALITY"
    THESIS_OR_OPPORTUNITY = "THESIS_OR_OPPORTUNITY"
    ALERT_OR_RECOMMENDATION = "ALERT_OR_RECOMMENDATION"
    BUY_HOLD_SELL_TRIM_ROTATE = "BUY_HOLD_SELL_TRIM_ROTATE"
    EXECUTION = "EXECUTION"


@dataclass(frozen=True, slots=True)
class FrozenFinancialMetricObservationSchema:
    schema_id: str
    version: str
    proposal_schema_id: str
    proposal_version: str
    approval_status: FinancialMetricObservationSchemaApprovalStatus
    approved_by: str
    selected_for_future_materializer: bool
    active: bool
    period_identity_strength_vocabulary: tuple[FinancialMetricPeriodIdentityStrength, ...]
    period_type_vocabulary: tuple[FinancialPeriodType, ...]
    period_basis_vocabulary: tuple[FinancialValueBasis, ...]
    statement_scope_vocabulary: tuple[StatementScope, ...]
    value_dimension_vocabulary: tuple[FinancialValueDimension, ...]
    admission_requirements: tuple[FinancialMetricObservationAdmissionRequirement, ...]
    source_fact_semantic_fields: tuple[FinancialMetricSourceFactSemanticField, ...]
    selector_policy_id: str
    selector_policy_version: str
    selector_policy_fingerprint: str
    exclusions: tuple[FinancialMetricObservationExclusion, ...]
    provenance: tuple[tuple[str, str], ...]
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.schema_id, self.version, self.proposal_schema_id, self.proposal_version, self.approved_by)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_REQUIRED_FIELD")
        if not self.approved_by.startswith("human:"):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_HUMAN_APPROVAL_REQUIRED")
        if self.approval_status is not FinancialMetricObservationSchemaApprovalStatus.APPROVED:
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_APPROVAL_REQUIRED")
        if self.selected_for_future_materializer or self.active:
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_MUST_NOT_BE_ACTIVE")
        if self.period_identity_strength_vocabulary != tuple(FinancialMetricPeriodIdentityStrength):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_STRENGTH_VOCABULARY_REQUIRED")
        if self.period_type_vocabulary != tuple(FinancialPeriodType) or self.period_basis_vocabulary != tuple(FinancialValueBasis):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_PERIOD_VOCABULARY_REQUIRED")
        if self.statement_scope_vocabulary != tuple(StatementScope) or self.value_dimension_vocabulary != tuple(FinancialValueDimension):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_VALUE_VOCABULARY_REQUIRED")
        if self.admission_requirements != tuple(FinancialMetricObservationAdmissionRequirement):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_ADMISSION_REQUIRED")
        if self.source_fact_semantic_fields != tuple(FinancialMetricSourceFactSemanticField):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_SOURCE_FIELDS_REQUIRED")
        if (
            self.selector_policy_id != _SELECTION_POLICY_ID
            or self.selector_policy_version != _SELECTION_POLICY_VERSION
            or self.selector_policy_fingerprint != _SELECTION_POLICY_FINGERPRINT
        ):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_SELECTOR_LINEAGE_REQUIRED")
        if self.exclusions != tuple(FinancialMetricObservationExclusion):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_EXCLUSIONS_REQUIRED")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_PROVENANCE_NONCANONICAL")
        if self.fingerprint != financial_metric_observation_schema_fingerprint(self):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialMetricPeriodIdentity:
    """Accounting meaning only; visibility is deliberately not a period field."""

    period_type: FinancialPeriodType
    value_basis: FinancialValueBasis
    period_start: datetime | None
    period_end: datetime | None
    fiscal_year: int | None
    fiscal_quarter: int | None
    statement_scope: StatementScope
    value_dimension: FinancialValueDimension
    currency: str
    unit: str
    scale: NumericScale
    normalization_version: str
    strength: FinancialMetricPeriodIdentityStrength
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.currency, self.unit, self.normalization_version)):
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_REPRESENTATION_REQUIRED")
        if self.period_start is not None and not _aware(self.period_start):
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_START_TIMEZONE_REQUIRED")
        if self.period_end is not None and not _aware(self.period_end):
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_END_TIMEZONE_REQUIRED")
        if self.fiscal_year is not None and self.fiscal_year <= 0:
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_FISCAL_YEAR_INVALID")
        if self.fiscal_quarter is not None and self.fiscal_quarter not in {1, 2, 3, 4}:
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_FISCAL_QUARTER_INVALID")
        if self.strength is FinancialMetricPeriodIdentityStrength.COMPLETE and not _period_identity_complete(self):
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_COMPLETE_FIELDS_REQUIRED")
        if self.strength is FinancialMetricPeriodIdentityStrength.PARTIAL and self.period_end is None:
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_PARTIAL_END_REQUIRED")
        if self.fingerprint != financial_metric_period_identity_fingerprint(self):
            raise ValueError("FINANCIAL_METRIC_PERIOD_IDENTITY_FINGERPRINT_MISMATCH")


@dataclass(frozen=True, slots=True)
class FinancialMetricObservation:
    """One passive factual representation of an already selected source fact."""

    canonical_instrument_id: str
    metric: FinancialMetric
    fact_kind: FundamentalFactKind
    value: Decimal
    currency: str
    unit: str
    scale: NumericScale
    statement_scope: StatementScope
    period_identity: FinancialMetricPeriodIdentity
    published_at: datetime
    received_at: datetime
    visible_as_of: datetime
    source_fact_id: str
    source: str
    filing_id: str | None
    source_reference: str | None
    revision_of_fact_id: str | None
    parent_fact_ids: tuple[str, ...]
    quality_flags: tuple[FinancialQualityFlag, ...]
    provenance: tuple[str, ...]
    normalization_version: str
    selection_policy_id: str
    selection_policy_version: str
    selection_policy_fingerprint: str
    selection_result_fingerprint: str
    source_fact_semantic_fingerprint: str
    schema_id: str
    schema_version: str
    schema_fingerprint: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((
            self.canonical_instrument_id,
            self.currency,
            self.unit,
            self.source_fact_id,
            self.source,
            self.normalization_version,
            self.selection_result_fingerprint,
            self.source_fact_semantic_fingerprint,
            self.schema_id,
            self.schema_version,
            self.schema_fingerprint,
        )):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_REQUIRED_FIELD")
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_FINITE_DECIMAL_REQUIRED")
        if not all(_aware(value) for value in (self.published_at, self.received_at, self.visible_as_of)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_PIT_TIMEZONE_REQUIRED")
        if self.received_at < self.published_at or self.visible_as_of != max(self.published_at, self.received_at):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_VISIBLE_AS_OF_INVALID")
        if self.period_identity.strength is FinancialMetricPeriodIdentityStrength.INSUFFICIENT:
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_PERIOD_IDENTITY_INSUFFICIENT")
        if self.period_identity.value_dimension is not _metric_value_dimension(self.metric):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_VALUE_DIMENSION_MISMATCH")
        if (
            self.statement_scope is not self.period_identity.statement_scope
            or self.currency != self.period_identity.currency
            or self.unit != self.period_identity.unit
            or self.scale is not self.period_identity.scale
            or self.normalization_version != self.period_identity.normalization_version
        ):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_PERIOD_IDENTITY_MISMATCH")
        if self.parent_fact_ids != tuple(sorted(set(self.parent_fact_ids))):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_PARENTS_NONCANONICAL")
        if self.quality_flags != tuple(sorted(set(self.quality_flags), key=lambda value: value.value)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_QUALITY_NONCANONICAL")
        if self.provenance != tuple(sorted(set(self.provenance))):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_PROVENANCE_NONCANONICAL")
        if (
            self.selection_policy_id != _SELECTION_POLICY_ID
            or self.selection_policy_version != _SELECTION_POLICY_VERSION
            or self.selection_policy_fingerprint != _SELECTION_POLICY_FINGERPRINT
        ):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SELECTOR_LINEAGE_REQUIRED")
        if (
            self.schema_id != _SCHEMA_ID
            or self.schema_version != _SCHEMA_VERSION
            or self.schema_fingerprint != _CURRENT_SCHEMA_FINGERPRINT
        ):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SCHEMA_LINEAGE_REQUIRED")
        if self.source_fact_semantic_fingerprint != financial_metric_source_fact_semantic_fingerprint_values(_source_fact_values(self)):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_SOURCE_FACT_FINGERPRINT_MISMATCH")
        if self.fingerprint != financial_metric_observation_fingerprint(self):
            raise ValueError("FINANCIAL_METRIC_OBSERVATION_FINGERPRINT_MISMATCH")


def create_frozen_financial_metric_observation_schema(
    *, schema_id: str, version: str, proposal_schema_id: str, proposal_version: str,
    approved_by: str, provenance: tuple[tuple[str, str], ...],
) -> FrozenFinancialMetricObservationSchema:
    values = dict(
        schema_id=schema_id,
        version=version,
        proposal_schema_id=proposal_schema_id,
        proposal_version=proposal_version,
        approval_status=FinancialMetricObservationSchemaApprovalStatus.APPROVED,
        approved_by=approved_by,
        selected_for_future_materializer=False,
        active=False,
        period_identity_strength_vocabulary=tuple(FinancialMetricPeriodIdentityStrength),
        period_type_vocabulary=tuple(FinancialPeriodType),
        period_basis_vocabulary=tuple(FinancialValueBasis),
        statement_scope_vocabulary=tuple(StatementScope),
        value_dimension_vocabulary=tuple(FinancialValueDimension),
        admission_requirements=tuple(FinancialMetricObservationAdmissionRequirement),
        source_fact_semantic_fields=tuple(FinancialMetricSourceFactSemanticField),
        selector_policy_id=_SELECTION_POLICY_ID,
        selector_policy_version=_SELECTION_POLICY_VERSION,
        selector_policy_fingerprint=_SELECTION_POLICY_FINGERPRINT,
        exclusions=tuple(FinancialMetricObservationExclusion),
        provenance=tuple(sorted(set(provenance))),
    )
    return FrozenFinancialMetricObservationSchema(
        **values, fingerprint=financial_metric_observation_schema_fingerprint_values(values),
    )


def financial_metric_observation_schema_fingerprint(value: FrozenFinancialMetricObservationSchema) -> str:
    return financial_metric_observation_schema_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_metric_observation_schema_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        schema_id=values["schema_id"], version=values["version"],
        proposal_schema_id=values["proposal_schema_id"], proposal_version=values["proposal_version"],
        approval_status=values["approval_status"].value, approved_by=values["approved_by"],
        selected_for_future_materializer=values["selected_for_future_materializer"], active=values["active"],
        period_identity_strength_vocabulary=tuple(item.value for item in values["period_identity_strength_vocabulary"]),
        period_type_vocabulary=tuple(item.value for item in values["period_type_vocabulary"]),
        period_basis_vocabulary=tuple(item.value for item in values["period_basis_vocabulary"]),
        statement_scope_vocabulary=tuple(item.value for item in values["statement_scope_vocabulary"]),
        value_dimension_vocabulary=tuple(item.value for item in values["value_dimension_vocabulary"]),
        admission_requirements=tuple(item.value for item in values["admission_requirements"]),
        source_fact_semantic_fields=tuple(item.value for item in values["source_fact_semantic_fields"]),
        selector_policy_id=values["selector_policy_id"], selector_policy_version=values["selector_policy_version"],
        selector_policy_fingerprint=values["selector_policy_fingerprint"],
        exclusions=tuple(item.value for item in values["exclusions"]), provenance=values["provenance"],
    )


def financial_metric_period_identity_fingerprint(value: FinancialMetricPeriodIdentity) -> str:
    return financial_metric_period_identity_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_metric_period_identity_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        period_type=values["period_type"].value, value_basis=values["value_basis"].value,
        period_start=_time(values["period_start"]), period_end=_time(values["period_end"]),
        fiscal_year=values["fiscal_year"], fiscal_quarter=values["fiscal_quarter"],
        statement_scope=values["statement_scope"].value, value_dimension=values["value_dimension"].value,
        currency=values["currency"], unit=values["unit"], scale=values["scale"].value,
        normalization_version=values["normalization_version"], strength=values["strength"].value,
    )


def financial_metric_source_fact_semantic_fingerprint_values(values: dict) -> str:
    """Canonical schema definition; it does not accept or materialize FinancialFact."""

    return manifest_fingerprint(
        canonical_instrument_id=values["canonical_instrument_id"], metric=values["metric"].value,
        fact_kind=values["fact_kind"].value, value=str(values["value"]), currency=values["currency"],
        unit=values["unit"], scale=values["scale"].value, statement_scope=values["statement_scope"].value,
        period_identity_fingerprint=values["period_identity"].fingerprint, source=values["source"],
        filing_id=values["filing_id"], source_reference=values["source_reference"],
        published_at=_time(values["published_at"]), received_at=_time(values["received_at"]),
        revision_of_fact_id=values["revision_of_fact_id"], parent_fact_ids=values["parent_fact_ids"],
        quality_flags=tuple(item.value for item in values["quality_flags"]),
        provenance=values["provenance"], normalization_version=values["normalization_version"],
    )


def financial_metric_observation_fingerprint(value: FinancialMetricObservation) -> str:
    return financial_metric_observation_fingerprint_values({
        field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"
    })


def financial_metric_observation_fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(
        canonical_instrument_id=values["canonical_instrument_id"], metric=values["metric"].value,
        fact_kind=values["fact_kind"].value, value=str(values["value"]), currency=values["currency"],
        unit=values["unit"], scale=values["scale"].value, statement_scope=values["statement_scope"].value,
        period_identity_fingerprint=values["period_identity"].fingerprint,
        published_at=_time(values["published_at"]), received_at=_time(values["received_at"]),
        visible_as_of=_time(values["visible_as_of"]), source_fact_id=values["source_fact_id"],
        source=values["source"], filing_id=values["filing_id"], source_reference=values["source_reference"],
        revision_of_fact_id=values["revision_of_fact_id"], parent_fact_ids=values["parent_fact_ids"],
        quality_flags=tuple(item.value for item in values["quality_flags"]),
        provenance=values["provenance"], normalization_version=values["normalization_version"],
        selection_policy_id=values["selection_policy_id"], selection_policy_version=values["selection_policy_version"],
        selection_policy_fingerprint=values["selection_policy_fingerprint"],
        selection_result_fingerprint=values["selection_result_fingerprint"],
        source_fact_semantic_fingerprint=values["source_fact_semantic_fingerprint"],
        schema_id=values["schema_id"], schema_version=values["schema_version"],
        schema_fingerprint=values["schema_fingerprint"],
    )


def _source_fact_values(value: FinancialMetricObservation) -> dict:
    return {
        "canonical_instrument_id": value.canonical_instrument_id, "metric": value.metric,
        "fact_kind": value.fact_kind, "value": value.value, "currency": value.currency,
        "unit": value.unit, "scale": value.scale, "statement_scope": value.statement_scope,
        "period_identity": value.period_identity, "source": value.source, "filing_id": value.filing_id,
        "source_reference": value.source_reference, "published_at": value.published_at,
        "received_at": value.received_at, "revision_of_fact_id": value.revision_of_fact_id,
        "parent_fact_ids": value.parent_fact_ids, "quality_flags": value.quality_flags,
        "provenance": value.provenance, "normalization_version": value.normalization_version,
    }


def _period_identity_complete(value: FinancialMetricPeriodIdentity) -> bool:
    if value.period_end is None or value.value_basis is FinancialValueBasis.UNKNOWN:
        return False
    if value.period_type is FinancialPeriodType.POINT_IN_TIME:
        return True
    if value.period_start is None:
        return False
    if value.period_type is FinancialPeriodType.QUARTERLY:
        return value.fiscal_year is not None and value.fiscal_quarter is not None
    if value.period_type is FinancialPeriodType.ANNUAL:
        return value.fiscal_year is not None
    return True


def _metric_value_dimension(metric: FinancialMetric) -> FinancialValueDimension:
    if metric in {FinancialMetric.EPS_BASIC, FinancialMetric.EPS_DILUTED, FinancialMetric.FACE_VALUE}:
        return FinancialValueDimension.PER_SHARE
    if metric is FinancialMetric.SHARES_OUTSTANDING:
        return FinancialValueDimension.COUNT
    return FinancialValueDimension.MONETARY


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _time(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value is not None else None


CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA = create_frozen_financial_metric_observation_schema(
    schema_id=_SCHEMA_ID,
    version=_SCHEMA_VERSION,
    proposal_schema_id="financial-metric-observation-schema",
    proposal_version="v1-proposed",
    approved_by="human:Akash-Verma",
    provenance=(
        ("governance_approval", "U14D-6H"),
        ("proposal_schema", "financial-metric-observation-schema/v1-proposed"),
        ("scope", "PASSIVE_FACTUAL_OBSERVATION_CONTRACT_ONLY"),
    ),
)
_CURRENT_SCHEMA_FINGERPRINT = CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA.fingerprint


__all__ = (
    "CURRENT_FROZEN_FINANCIAL_METRIC_OBSERVATION_SCHEMA",
    "FinancialMetricObservation",
    "FinancialMetricObservationAdmissionRequirement",
    "FinancialMetricObservationExclusion",
    "FinancialMetricObservationSchemaApprovalStatus",
    "FinancialMetricPeriodIdentity",
    "FinancialMetricPeriodIdentityStrength",
    "FinancialMetricSourceFactSemanticField",
    "FrozenFinancialMetricObservationSchema",
    "create_frozen_financial_metric_observation_schema",
    "financial_metric_observation_fingerprint",
    "financial_metric_observation_fingerprint_values",
    "financial_metric_observation_schema_fingerprint",
    "financial_metric_period_identity_fingerprint",
    "financial_metric_period_identity_fingerprint_values",
    "financial_metric_source_fact_semantic_fingerprint_values",
)
