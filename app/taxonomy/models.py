"""Canonical, provenance-bearing sector/industry and separate theme records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ClassificationSourceStatus(StrEnum):
    OFFICIAL = "OFFICIAL"
    PROVIDER_DERIVED = "PROVIDER_DERIVED"
    PRIMARY_SOURCE_DERIVED = "PRIMARY_SOURCE_DERIVED"
    MANUALLY_REVIEWED = "MANUALLY_REVIEWED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class InstrumentTaxonomyClassification:
    classification_id: str
    instrument_id: str
    industry: str | None
    sector: str | None
    super_sector: str | None
    source: str
    source_type: ClassificationSourceStatus
    effective_from: datetime
    effective_to: datetime | None
    as_of: datetime
    confidence: float | None
    classification_version: str
    source_reference: str | None = None
    warnings: tuple[str, ...] = ()
    macro_economic_sector_code: str | None = None
    sector_code: str | None = None
    industry_code: str | None = None
    basic_industry_code: str | None = None
    basic_industry: str | None = None
    raw_classification_label: str | None = None
    resolution_status: str | None = None
    source_sha256: str | None = None
    source_as_of_date: str | None = None
    fetched_at_utc: datetime | None = None
    effective_observation_semantics: str | None = None

    def eligible_as_of(self, at: datetime) -> bool:
        return self.effective_from <= at and (self.effective_to is None or at <= self.effective_to) and self.as_of <= at


@dataclass(frozen=True, slots=True)
class ThemeMembership:
    membership_id: str
    instrument_id: str
    theme: str
    source: str
    source_type: ClassificationSourceStatus
    effective_from: datetime
    effective_to: datetime | None
    as_of: datetime
    confidence: float | None
    classification_version: str
    evidence_ids: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def eligible_as_of(self, at: datetime) -> bool:
        return self.effective_from <= at and (self.effective_to is None or at <= self.effective_to) and self.as_of <= at
