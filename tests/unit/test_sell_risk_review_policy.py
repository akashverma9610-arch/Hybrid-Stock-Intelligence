from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.domain.models import FreshnessStatus
from app.intelligence.external_intelligence import EventType, Materiality
from app.intelligence.sell_risk_review_policy import (
    AdverseEventClassification,
    CanonicalAdverseEventEvidence,
    CanonicalMappingStatus,
    Rule46ReviewContext,
    SellRiskReview,
    SellRiskReviewInput,
    SellRiskReviewPolicyError,
    SellRiskReviewStatus,
    evaluate_sell_risk_review,
)
import app.intelligence.sell_risk_review_policy as policy_module
from app.intelligence.unified_state import IntelligenceEvidenceAvailability
from app.reliability.models import ReliabilityStatus


AS_OF = datetime(2026, 9, 2, 10, tzinfo=UTC)


def _fingerprint(value: str) -> str:
    return "sha256:" + (value * 64)[:64]


def _event(
    *,
    event_id: str = "event:one",
    evidence_id: str = "evidence:one",
    materiality: Materiality | None = Materiality.HIGH,
    source: str | None = "OFFICIAL",
    classification: AdverseEventClassification | None = AdverseEventClassification.ADVERSE,
    mapping: CanonicalMappingStatus = CanonicalMappingStatus.VERIFIED_EXACT,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    freshness: FreshnessStatus | None = FreshnessStatus.FRESH,
    reliability: ReliabilityStatus | None = ReliabilityStatus.READY,
    conflict: bool = False,
    received_at: datetime | None = AS_OF - timedelta(minutes=2),
    available_at: datetime | None = AS_OF - timedelta(minutes=1),
    resolution_status: str | None = None,
    resolution_lineage_id: str | None = None,
) -> CanonicalAdverseEventEvidence:
    return CanonicalAdverseEventEvidence(
        canonical_event_id=event_id, evidence_version_id=evidence_id,
        evidence_fingerprint=_fingerprint(event_id + evidence_id), canonical_instrument_id="NSE:INE000A01001",
        event_type=EventType.GOVERNANCE, adverse_classification=classification,
        materiality=materiality, primary_source_type=source, mapping_status=mapping,
        evidence_availability=availability, freshness_status=freshness,
        reliability_status=reliability, conflict_detected=conflict,
        received_at=received_at, available_at=available_at, resolution_status=resolution_status,
        resolution_lineage_id=resolution_lineage_id,
    )


def _rule46(
    *,
    triggered: bool = False,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    freshness: FreshnessStatus | None = FreshnessStatus.FRESH,
    available_at: datetime | None = AS_OF - timedelta(minutes=1),
) -> Rule46ReviewContext:
    return Rule46ReviewContext(
        canonical_instrument_id="NSE:INE000A01001", diagnostic_result_id="diagnostic:46",
        artifact_id="artifact:46", artifact_fingerprint=_fingerprint("rule46"),
        source_state="PRICE_STRUCTURE_INVALIDATION" if triggered else "PRICE_STRUCTURE_INTACT",
        triggered=triggered, evidence_availability=availability,
        freshness_status=freshness, available_at=available_at,
    )


_DEFAULT_RULE46 = object()


def _input(
    *,
    events: tuple[CanonicalAdverseEventEvidence, ...] = (),
    rule46: Rule46ReviewContext | None | object = _DEFAULT_RULE46,
    availability: IntelligenceEvidenceAvailability = IntelligenceEvidenceAvailability.AVAILABLE,
    as_of: datetime = AS_OF,
) -> SellRiskReviewInput:
    return SellRiskReviewInput.create(
        canonical_instrument_id="NSE:INE000A01001", evaluation_as_of=as_of,
        external_evidence_availability=availability, events=events,
        rule46_context=_rule46() if rule46 is _DEFAULT_RULE46 else rule46,
    )


def test_high_primary_adverse_event_is_priority_review() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(),)))
    assert result.status is SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW
    assert result.event_lineage[0].materiality == "HIGH"
    assert result.actionability.value == "WATCH_ONLY"
    assert result.execution_status.value == "NON_EXECUTABLE"


def test_critical_primary_adverse_event_is_urgent_review() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(materiality=Materiality.CRITICAL),)))
    assert result.status is SellRiskReviewStatus.URGENT_EVIDENCE_REVIEW
    assert result.event_lineage[0].materiality == "CRITICAL"


def test_future_event_is_excluded_fail_closed() -> None:
    future = _event(received_at=AS_OF + timedelta(seconds=1), available_at=AS_OF + timedelta(seconds=2))
    result = evaluate_sell_risk_review(_input(events=(future,)))
    assert result.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE
    assert "EVENT_PIT_INELIGIBLE" in result.blocker_codes


@pytest.mark.parametrize("source,mapping", [("MEDIA", CanonicalMappingStatus.VERIFIED_EXACT), ("OFFICIAL", CanonicalMappingStatus.FUZZY)])
def test_secondary_or_fuzzy_event_is_unavailable(source: str, mapping: CanonicalMappingStatus) -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(source=source, mapping=mapping),)))
    assert result.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE


def test_missing_adverse_classification_is_unavailable_not_inferred() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(classification=None),)))
    assert result.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE
    assert "EVENT_ADVERSE_CLASSIFICATION_UNAVAILABLE" in result.blocker_codes


def test_event_category_is_retained_without_promotion_to_misconduct() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(),)))
    assert result.event_lineage[0].event_type == EventType.GOVERNANCE.value
    assert "fraud" not in result.serialize().lower()
    assert "misconduct" not in result.serialize().lower()


def test_conflicted_primary_critical_evidence_preserves_materiality() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(materiality=Materiality.CRITICAL, conflict=True),)))
    assert result.status is SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW
    assert result.event_lineage[0].materiality == "CRITICAL"


def test_canonical_domain_conflict_is_reviewed_not_erased_as_unavailable() -> None:
    result = evaluate_sell_risk_review(_input(
        events=(_event(),), availability=IntelligenceEvidenceAvailability.CONFLICTED,
    ))
    assert result.status is SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW


def test_exact_duplicate_event_is_deduplicated_without_escalation() -> None:
    event = _event()
    result = evaluate_sell_risk_review(_input(events=(event, event)))
    assert result.status is SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW
    assert len(result.event_lineage) == 1


def test_corrected_or_superseded_state_is_lineaged_not_transitioned() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(
        resolution_status="SUPERSEDED", resolution_lineage_id="evidence:two",
    ),)))
    lineage = result.event_lineage[0]
    assert lineage.resolution_status == "SUPERSEDED"
    assert lineage.resolution_lineage_id == "evidence:two"
    assert lineage.resolution_availability.value == "AVAILABLE"


def test_missing_freshness_and_stale_evidence_cannot_create_priority_review() -> None:
    for event in (_event(freshness=None), _event(freshness=FreshnessStatus.STALE)):
        result = evaluate_sell_risk_review(_input(events=(event,)))
        assert result.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE
        assert "EVENT_FRESHNESS_UNAVAILABLE" in result.blocker_codes


def test_rule46_only_is_descriptive_technical_review() -> None:
    result = evaluate_sell_risk_review(_input(rule46=_rule46(triggered=True)))
    assert result.status is SellRiskReviewStatus.TECHNICAL_STRUCTURE_REVIEW
    assert result.rule46_lineage is not None and result.rule46_lineage.triggered
    assert not result.event_lineage


def test_adverse_event_and_rule46_is_multi_domain_without_new_severity() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(materiality=Materiality.CRITICAL),), rule46=_rule46(triggered=True)))
    assert result.status is SellRiskReviewStatus.MULTI_DOMAIN_EVIDENCE_REVIEW
    assert result.event_lineage[0].materiality == "CRITICAL"
    assert result.rule46_lineage is not None and result.rule46_lineage.triggered


@pytest.mark.parametrize("rule46", [None, _rule46(availability=IntelligenceEvidenceAvailability.STALE), _rule46(freshness=FreshnessStatus.STALE)])
def test_missing_or_unverifiable_rule46_context_is_unavailable(rule46: Rule46ReviewContext | None) -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(),), rule46=rule46))
    assert result.status is SellRiskReviewStatus.EVIDENCE_UNAVAILABLE
    assert any(code.startswith("RULE46_CONTEXT") for code in result.blocker_codes)


def test_input_order_timezone_and_fingerprint_are_deterministic() -> None:
    one = _event(event_id="event:one", evidence_id="evidence:one")
    two = _event(event_id="event:two", evidence_id="evidence:two", materiality=Materiality.CRITICAL)
    utc = evaluate_sell_risk_review(_input(events=(one, two), as_of=AS_OF))
    ist = evaluate_sell_risk_review(_input(events=(two, one), as_of=AS_OF.astimezone(timezone(timedelta(hours=5, minutes=30)))))
    assert utc.review_id == ist.review_id
    assert utc.fingerprint == ist.fingerprint
    assert utc.serialize() == ist.serialize()


def test_tampered_lineage_or_fingerprint_is_rejected() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(),)))
    with pytest.raises(SellRiskReviewPolicyError, match="FINGERPRINT_MISMATCH"):
        replace(result, fingerprint=_fingerprint("tampered")).verify()
    with pytest.raises(SellRiskReviewPolicyError, match="ID_MISMATCH"):
        replace(result, review_id="sell-risk-review:tampered", fingerprint=result.fingerprint).verify()


def test_conflicted_status_requires_retained_canonical_conflict_lineage() -> None:
    result = evaluate_sell_risk_review(_input(events=(_event(),)))
    tampered = replace(result, status=SellRiskReviewStatus.CONFLICTED_EVIDENCE_REVIEW)
    tampered = replace(tampered, review_id=policy_module._review_id(tampered))
    tampered = replace(tampered, fingerprint=policy_module._fingerprint(tampered))
    # Even a structurally recomputed result cannot claim conflict without a
    # retained canonical conflict fact.
    with pytest.raises(SellRiskReviewPolicyError, match="CONFLICT_LINEAGE_REQUIRED"):
        tampered.verify()


def test_conflicting_duplicate_lineage_is_rejected_not_silently_merged() -> None:
    event = _event()
    with pytest.raises(SellRiskReviewPolicyError, match="LINEAGE_CONFLICT"):
        SellRiskReviewInput.create(events=(event, replace(event, conflict_detected=True)), canonical_instrument_id="NSE:INE000A01001", evaluation_as_of=AS_OF, external_evidence_availability=IntelligenceEvidenceAvailability.AVAILABLE, rule46_context=_rule46())


def test_no_qualifying_evidence_requires_clean_evaluated_domains() -> None:
    result = evaluate_sell_risk_review(_input())
    assert result.status is SellRiskReviewStatus.NO_QUALIFYING_RISK_EVIDENCE
    assert not result.blocker_codes
    assert not result.event_lineage
    assert result.rule46_lineage is not None and not result.rule46_lineage.triggered


def test_contextual_secondary_evidence_cannot_suppress_valid_primary_review() -> None:
    primary = _event(event_id="event:primary", evidence_id="evidence:primary")
    secondary = _event(event_id="event:secondary", evidence_id="evidence:secondary", source="MEDIA")
    result = evaluate_sell_risk_review(_input(events=(secondary, primary)))
    assert result.status is SellRiskReviewStatus.PRIORITY_EVIDENCE_REVIEW
    assert tuple(item.canonical_event_id for item in result.event_lineage) == ("event:primary",)


def test_source_label_must_be_exact_canonical_value() -> None:
    with pytest.raises(SellRiskReviewPolicyError, match="SOURCE_NONCANONICAL"):
        _event(source=" OFFICIAL ")


def test_output_has_no_risk_severity_thesis_or_execution_surface() -> None:
    names = set(SellRiskReview.__dataclass_fields__)
    forbidden = {"risk_severity", "thesis_status", "entry", "stop", "target", "quantity", "allocation", "order", "broker", "portfolio", "action"}
    assert not names & forbidden
    result = evaluate_sell_risk_review(_input(events=(_event(),)))
    serialized = result.serialize()
    assert '"action"' not in serialized
    assert '"portfolio"' not in serialized


def test_policy_has_no_forbidden_dependencies_or_current_clock() -> None:
    source = Path("app/intelligence/sell_risk_review_policy.py").read_text(encoding="utf-8")
    forbidden = ("app.signals", "app.portfolio", "app.storage", "app.api", "broker", "order", "datetime.now", "utcnow")
    assert not any(value in source for value in forbidden)
