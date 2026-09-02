"""Strict, redacted HTTP contracts for External Intelligence V1C."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.intelligence.external_intelligence import (
    CompanyExposure,
    DataPoint,
    EventType,
    ExposureType,
    ExternalEvent,
    Fact,
    Inference,
    Interpretation,
    Materiality,
    PolicyStage,
    SourceEvidence,
)
from app.intelligence.external_intelligence_application import (
    ExternalIntelligenceApplicationReceipt,
    ExternalIntelligenceRecordCommand,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntelligenceSourceRequest(_StrictModel):
    source_name: str = Field(min_length=1, max_length=200)
    source_type: str = Field(min_length=1, max_length=80)
    source_reference: str | None = Field(default=None, max_length=2_000)
    source_confidence: float = Field(ge=0, le=1)

    def to_domain(self) -> SourceEvidence:
        return SourceEvidence(self.source_name, self.source_type, self.source_reference, self.source_confidence)


class IntelligenceFactRequest(_StrictModel):
    content: str = Field(min_length=1, max_length=12_000)
    source_references: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    confidence: float = Field(ge=0, le=1)

    def to_domain(self) -> Fact:
        return Fact(self.content, self.source_references, self.confidence)


class IntelligenceDataPointRequest(_StrictModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=1_000)
    unit: str | None = Field(default=None, max_length=100)
    period: str | None = Field(default=None, max_length=200)
    source_references: tuple[str, ...] = Field(default_factory=tuple, max_length=50)

    def to_domain(self) -> DataPoint:
        return DataPoint(self.name, self.value, self.unit, self.period, self.source_references)


class IntelligenceInterpretationRequest(_StrictModel):
    content: str = Field(min_length=1, max_length=12_000)
    confidence: float = Field(ge=0, le=1)

    def to_domain(self) -> Interpretation:
        return Interpretation(self.content, self.confidence)


class IntelligenceInferenceRequest(_StrictModel):
    conclusion: str = Field(min_length=1, max_length=12_000)
    confidence: float = Field(ge=0, le=1)
    verification_status: str = Field(default="UNVERIFIED_INFERENCE", min_length=1, max_length=80)

    def to_domain(self) -> Inference:
        return Inference(self.conclusion, self.confidence, self.verification_status)


class IntelligenceCompanyExposureRequest(_StrictModel):
    canonical_instrument_id: str | None = Field(default=None, min_length=1, max_length=200)
    external_company_name: str | None = Field(default=None, min_length=1, max_length=300)
    exposure_type: ExposureType
    confidence: float | None = Field(default=None, ge=0, le=1)
    verification_status: Literal["VERIFIED", "UNVERIFIED_INFERENCE"] = "UNVERIFIED_INFERENCE"

    @model_validator(mode="after")
    def validate_identity_and_confidence(self) -> "IntelligenceCompanyExposureRequest":
        if self.canonical_instrument_id is None and self.external_company_name is None:
            raise ValueError("A company exposure requires a canonical ID or an external company name.")
        if self.verification_status == "VERIFIED" and self.canonical_instrument_id is None:
            raise ValueError("Verified exposure requires a canonical instrument ID.")
        return self

    def to_domain(self, default_confidence: float | None) -> CompanyExposure:
        confidence = self.confidence if self.confidence is not None else default_confidence
        if confidence is None:
            raise ValueError("Company exposure confidence is required.")
        return CompanyExposure(
            self.canonical_instrument_id, self.external_company_name, self.exposure_type,
            confidence, self.verification_status,
        )


class ExternalIntelligenceEventRequest(_StrictModel):
    schema_version: Literal["hsi-external-intelligence-event/v1"]
    producer_event_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    event_type: EventType
    title: str = Field(min_length=1, max_length=500)
    country: str = Field(min_length=1, max_length=80)
    domain: str = Field(min_length=1, max_length=120)
    materiality: Materiality
    policy_stage: PolicyStage | None = None
    published_at: AwareDatetime
    discovered_at: AwareDatetime
    effective_at: AwareDatetime | None = None
    summary: str = Field(min_length=1, max_length=24_000)
    what_changed: str = Field(min_length=1, max_length=24_000)
    primary_source: IntelligenceSourceRequest
    supporting_sources: tuple[IntelligenceSourceRequest, ...] = Field(default_factory=tuple, max_length=50)
    facts: tuple[IntelligenceFactRequest, ...] = Field(default_factory=tuple, max_length=100)
    data_points: tuple[IntelligenceDataPointRequest, ...] = Field(default_factory=tuple, max_length=100)
    interpretation: tuple[IntelligenceInterpretationRequest, ...] = Field(default_factory=tuple, max_length=100)
    inferences: tuple[IntelligenceInferenceRequest, ...] = Field(default_factory=tuple, max_length=100)
    affected_sectors: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    affected_industries: tuple[str, ...] = Field(default_factory=tuple, max_length=50)
    possible_company_exposure: tuple[IntelligenceCompanyExposureRequest, ...] = Field(default_factory=tuple, max_length=100)
    event_confidence: float | None = Field(default=None, ge=0, le=1)
    exposure_confidence: float | None = Field(default=None, ge=0, le=1)
    time_horizon: str | None = Field(default=None, max_length=300)
    risks: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    counter_evidence: tuple[str, ...] = Field(default_factory=tuple, max_length=100)
    why_hsi_should_care: str | None = Field(default=None, max_length=12_000)
    requires_hsi_analysis: bool = False

    @model_validator(mode="after")
    def validate_chronology(self) -> "ExternalIntelligenceEventRequest":
        if self.discovered_at < self.published_at:
            raise ValueError("discovered_at must not precede published_at.")
        return self

    def to_command(self, producer_id: str, received_at: datetime) -> ExternalIntelligenceRecordCommand:
        exposures = tuple(item.to_domain(self.exposure_confidence) for item in self.possible_company_exposure)
        event = ExternalEvent(
            producer_id, self.producer_event_id, self.event_type, self.title, self.country, self.domain,
            self.materiality, received_at, self.policy_stage, self.schema_version,
        )
        return ExternalIntelligenceRecordCommand(
            event, self.published_at, self.discovered_at, self.summary, self.what_changed,
            self.primary_source.to_domain(),
            tuple(item.to_domain() for item in self.facts),
            tuple(item.to_domain() for item in self.data_points),
            tuple(item.to_domain() for item in self.interpretation),
            tuple(item.to_domain() for item in self.inferences),
            exposures, tuple(item.to_domain() for item in self.supporting_sources),
            self.event_confidence, self.exposure_confidence, self.time_horizon, self.risks,
            self.counter_evidence, self.why_hsi_should_care, self.effective_at,
            self.affected_sectors, self.affected_industries, self.requires_hsi_analysis,
        )


class ExternalIntelligenceReceiptResponse(BaseModel):
    disposition: str
    canonical_event_id: str
    evidence_version_id: str | None
    received_at: datetime
    schema_version: str = "hsi-external-intelligence-event/v1"
    event_fingerprint: str
    evidence_fingerprint: str | None
    reevaluation_requested: bool
    reevaluation_request_id: str | None
    blocker: str | None

    @classmethod
    def from_receipt(cls, value: ExternalIntelligenceApplicationReceipt) -> "ExternalIntelligenceReceiptResponse":
        return cls(
            disposition=value.disposition.value, canonical_event_id=value.canonical_event_id,
            evidence_version_id=value.evidence_version_id, received_at=value.received_at,
            event_fingerprint=value.event_fingerprint, evidence_fingerprint=value.evidence_fingerprint,
            reevaluation_requested=value.reevaluation_requested,
            reevaluation_request_id=value.reevaluation_request_id, blocker=value.blocker,
        )
