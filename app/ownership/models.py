"""Typed ownership facts and observations; no ownership thesis is encoded here."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.historical.guard import manifest_fingerprint


class OwnershipCategory(StrEnum):
    PROMOTER_AND_PROMOTER_GROUP = "PROMOTER_AND_PROMOTER_GROUP"
    PUBLIC = "PUBLIC"
    DII = "DII"
    MUTUAL_FUNDS = "MUTUAL_FUNDS"
    GOVERNMENT = "GOVERNMENT"
    INSURANCE = "INSURANCE"
    BANKS_FINANCIAL_INSTITUTIONS = "BANKS_FINANCIAL_INSTITUTIONS"
    PROMOTER_PLEDGE_OR_ENCUMBRANCE = "PROMOTER_PLEDGE_OR_ENCUMBRANCE"


class OwnershipCategoryRelationship(StrEnum):
    TOTAL = "TOTAL"
    SUBCATEGORY = "SUBCATEGORY"
    DERIVED_TOTAL = "DERIVED_TOTAL"


class OwnershipNormalizedUnit(StrEnum):
    PERCENTAGE_POINTS = "PERCENTAGE_POINTS"


class OwnershipEvidenceSufficiency(StrEnum):
    DIRECT_OFFICIAL = "DIRECT_OFFICIAL"
    PARTIAL = "PARTIAL"


def _require_aware(*values: datetime) -> None:
    if any(value.tzinfo is None or value.utcoffset() is None for value in values):
        raise ValueError("Ownership timestamps must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class OwnershipRawFact:
    fact_id: str
    canonical_instrument_id: str
    filing_id: str
    artifact_sha256: str
    reporting_period: datetime
    published_at: datetime
    received_at: datetime
    raw_concept: str
    raw_value: Decimal
    raw_unit: str
    scope: str
    source_context_reference: str
    source_reference: str
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.fact_id, self.canonical_instrument_id, self.filing_id, self.artifact_sha256,
                    self.raw_concept, self.raw_unit, self.scope, self.source_context_reference,
                    self.source_reference, self.fingerprint)) or len(self.artifact_sha256) != 64:
            raise ValueError("Ownership raw fact identity is incomplete.")
        _require_aware(self.reporting_period, self.published_at, self.received_at)
        if self.fingerprint != ownership_raw_fact_fingerprint(self):
            raise ValueError("Ownership raw fact fingerprint is invalid.")


@dataclass(frozen=True, slots=True)
class OwnershipObservation:
    observation_id: str
    raw_fact_id: str
    canonical_instrument_id: str
    filing_id: str
    category: OwnershipCategory
    category_relationship: OwnershipCategoryRelationship
    reporting_period: datetime
    published_at: datetime
    received_at: datetime
    raw_concept: str
    raw_value: Decimal
    raw_unit: str
    normalized_value: Decimal | None
    normalized_unit: OwnershipNormalizedUnit | None
    normalization_rule_id: str | None
    scope: str
    artifact_sha256: str
    source_context_reference: str
    source_reference: str
    evidence_sufficiency: OwnershipEvidenceSufficiency
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.observation_id, self.raw_fact_id, self.canonical_instrument_id, self.filing_id,
                    self.raw_concept, self.raw_unit, self.scope, self.artifact_sha256,
                    self.source_context_reference, self.source_reference, self.fingerprint)):
            raise ValueError("Ownership observation identity is incomplete.")
        if len(self.artifact_sha256) != 64:
            raise ValueError("Ownership observation artifact hash is invalid.")
        _require_aware(self.reporting_period, self.published_at, self.received_at)
        normalized = (self.normalized_value, self.normalized_unit, self.normalization_rule_id)
        if any(value is None for value in normalized) and any(value is not None for value in normalized):
            raise ValueError("Ownership normalization lineage must be complete or absent.")
        if self.category_relationship is OwnershipCategoryRelationship.DERIVED_TOTAL:
            raise ValueError("V1 ownership observations cannot invent derived totals.")
        if self.fingerprint != ownership_observation_fingerprint(self):
            raise ValueError("Ownership observation fingerprint is invalid.")


@dataclass(frozen=True, slots=True)
class OwnershipComparison:
    status: str
    category: OwnershipCategory
    current_observation_id: str | None
    prior_observation_id: str | None
    change_percentage_points: Decimal | None
    blocker: str | None


def ownership_raw_fact_fingerprint(value: OwnershipRawFact) -> str:
    return manifest_fingerprint(**{
        field: getattr(value, field) for field in value.__dataclass_fields__ if field not in {"fact_id", "fingerprint"}
    })


def ownership_observation_fingerprint(value: OwnershipObservation) -> str:
    return manifest_fingerprint(**{
        field: getattr(value, field) for field in value.__dataclass_fields__ if field not in {"observation_id", "fingerprint"}
    })
