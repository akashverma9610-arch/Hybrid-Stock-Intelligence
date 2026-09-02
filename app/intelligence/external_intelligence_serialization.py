"""Canonical rehydration helpers for immutable external-intelligence records."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping

from app.intelligence.external_intelligence import (
    CompanyExposure,
    DataPoint,
    EventType,
    EvidenceVersion,
    ExposureType,
    ExternalEvent,
    Fact,
    Inference,
    Interpretation,
    Materiality,
    PolicyStage,
    ReevaluationRequest,
    ReevaluationState,
    SourceEvidence,
)


def event_from_canonical_payload(payload: str | Mapping[str, Any]) -> ExternalEvent:
    value = _object(payload)
    return ExternalEvent(
        producer_id=_string(value, "producer_id"),
        producer_event_id=_string(value, "producer_event_id"),
        event_type=EventType(_string(value, "event_type")),
        title=_string(value, "title"),
        country=_string(value, "country"),
        domain=_string(value, "domain"),
        materiality=Materiality(_string(value, "materiality")),
        first_received_at=_timestamp(value, "first_received_at"),
        policy_stage=PolicyStage(value["policy_stage"]) if value.get("policy_stage") is not None else None,
        schema_version=_string(value, "schema_version"),
    )


def evidence_version_from_canonical_payload(payload: str | Mapping[str, Any]) -> EvidenceVersion:
    value = _object(payload)
    return EvidenceVersion(
        event=event_from_canonical_payload(_mapping(value, "event")),
        received_at=_timestamp(value, "received_at"),
        published_at=_timestamp(value, "published_at"),
        discovered_at=_timestamp(value, "discovered_at"),
        summary=_string(value, "summary"),
        what_changed=_string(value, "what_changed"),
        primary_source=_source(_mapping(value, "primary_source")),
        facts=tuple(_fact(_object(item)) for item in _list(value, "facts")),
        data_points=tuple(_data_point(_object(item)) for item in _list(value, "data_points")),
        interpretation=tuple(_interpretation(_object(item)) for item in _list(value, "interpretation")),
        inferences=tuple(_inference(_object(item)) for item in _list(value, "inferences")),
        supporting_sources=tuple(_source(_object(item)) for item in _list_default(value, "supporting_sources")),
        company_exposures=tuple(_company_exposure(_object(item)) for item in _list_default(value, "company_exposures")),
        event_confidence=_optional_number(value, "event_confidence"),
        exposure_confidence=_optional_number(value, "exposure_confidence"),
        time_horizon=_optional_string(value, "time_horizon"),
        risks=_strings_default(value, "risks"),
        counter_evidence=_strings_default(value, "counter_evidence"),
        why_hsi_should_care=_optional_string(value, "why_hsi_should_care"),
        effective_at=_optional_timestamp(value, "effective_at"),
        affected_sectors=_strings_default(value, "affected_sectors"),
        affected_industries=_strings_default(value, "affected_industries"),
    )


def reevaluation_request_from_canonical_payload(payload: str | Mapping[str, Any]) -> ReevaluationRequest:
    value = _object(payload)
    return ReevaluationRequest(
        canonical_event_id=_string(value, "canonical_event_id"),
        evidence_version_id=_string(value, "evidence_version_id"),
        materiality=Materiality(_string(value, "materiality")),
        requested_at=_timestamp(value, "requested_at"),
        affected_canonical_instruments=_strings(value, "affected_canonical_instruments"),
        affected_sectors=_strings(value, "affected_sectors"),
        affected_industries=_strings(value, "affected_industries"),
        processing_state=ReevaluationState(_string(value, "processing_state")),
        blocker=value.get("blocker"),
    )


def _source(value: Mapping[str, Any]) -> SourceEvidence:
    return SourceEvidence(_string(value, "source_name"), _string(value, "source_type"), value.get("source_reference"), _number(value, "source_confidence"))


def _fact(value: Mapping[str, Any]) -> Fact:
    return Fact(_string(value, "content"), _strings(value, "source_references"), _number(value, "confidence"))


def _data_point(value: Mapping[str, Any]) -> DataPoint:
    return DataPoint(_string(value, "name"), _string(value, "value"), value.get("unit"), value.get("period"), _strings(value, "source_references"))


def _interpretation(value: Mapping[str, Any]) -> Interpretation:
    return Interpretation(_string(value, "content"), _number(value, "confidence"))


def _inference(value: Mapping[str, Any]) -> Inference:
    return Inference(_string(value, "conclusion"), _number(value, "confidence"), _string(value, "verification_status"))


def _company_exposure(value: Mapping[str, Any]) -> CompanyExposure:
    canonical_instrument_id = value.get("canonical_instrument_id")
    external_company_name = value.get("external_company_name")
    if canonical_instrument_id is not None and not isinstance(canonical_instrument_id, str):
        raise ValueError("External-intelligence company exposure canonical identity must be a string.")
    if external_company_name is not None and not isinstance(external_company_name, str):
        raise ValueError("External-intelligence company exposure name must be a string.")
    return CompanyExposure(
        canonical_instrument_id, external_company_name, ExposureType(_string(value, "exposure_type")),
        _number(value, "confidence"), _string(value, "verification_status"),
    )


def _object(value: str | Mapping[str, Any]) -> Mapping[str, Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("External-intelligence canonical payload must be an object.")
    return parsed


def _mapping(value: Mapping[str, Any], field: str) -> Mapping[str, Any]:
    item = value.get(field)
    if not isinstance(item, dict):
        raise ValueError(f"External-intelligence payload field {field} must be an object.")
    return item


def _list(value: Mapping[str, Any], field: str) -> list[Any]:
    item = value.get(field)
    if not isinstance(item, list):
        raise ValueError(f"External-intelligence payload field {field} must be a list.")
    return item


def _list_default(value: Mapping[str, Any], field: str) -> list[Any]:
    return [] if field not in value else _list(value, field)


def _strings(value: Mapping[str, Any], field: str) -> tuple[str, ...]:
    items = _list(value, field)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"External-intelligence payload field {field} must contain strings.")
    return tuple(items)


def _strings_default(value: Mapping[str, Any], field: str) -> tuple[str, ...]:
    return () if field not in value else _strings(value, field)


def _string(value: Mapping[str, Any], field: str) -> str:
    item = value.get(field)
    if not isinstance(item, str):
        raise ValueError(f"External-intelligence payload field {field} must be a string.")
    return item


def _number(value: Mapping[str, Any], field: str) -> float:
    item = value.get(field)
    if not isinstance(item, (int, float)) or isinstance(item, bool):
        raise ValueError(f"External-intelligence payload field {field} must be numeric.")
    return float(item)


def _optional_number(value: Mapping[str, Any], field: str) -> float | None:
    return None if value.get(field) is None else _number(value, field)


def _optional_string(value: Mapping[str, Any], field: str) -> str | None:
    return None if value.get(field) is None else _string(value, field)


def _timestamp(value: Mapping[str, Any], field: str) -> datetime:
    try:
        return datetime.fromisoformat(_string(value, field))
    except ValueError as error:
        raise ValueError(f"External-intelligence payload field {field} must be an ISO timestamp.") from error


def _optional_timestamp(value: Mapping[str, Any], field: str) -> datetime | None:
    return None if value.get(field) is None else _timestamp(value, field)
