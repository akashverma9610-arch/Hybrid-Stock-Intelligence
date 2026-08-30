from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.audit.decision import (
    DecisionAuditRecord, DecisionAuditService, DecisionAuditStore, DecisionOutcomeLink,
    decision_audit_fingerprint, decision_outcome_fingerprint,
)
from app.data_sources.models import DataFamily, SourceReadinessStatus
from app.governance.drift import (
    GovernanceDriftService, GovernanceDriftStore, GovernanceHealth,
    ModelVersionPerformance,
)
from app.historical.models import HistoricalFact, InstrumentLifecycle, UniverseMembership
from app.historical_integrity import HistoricalIntegrityService, HistoricalIntegrityStatus
from app.reliability import DataReliabilityService, ReliabilityStatus, SourceHealth
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 24, 10, tzinfo=UTC)


def test_reliability_uses_declared_fallback_and_never_fabricates_missing_data():
    service = DataReliabilityService()
    primary = SourceHealth("primary", DataFamily.CURRENT_QUOTES, 1, SourceReadinessStatus.UNAVAILABLE, T, False)
    fallback = SourceHealth("secondary", DataFamily.CURRENT_QUOTES, 2, SourceReadinessStatus.READY, T, True, value_fingerprint="exact-quote")
    decision = service.decide(DataFamily.CURRENT_QUOTES, (primary, fallback))
    assert decision.availability.status is ReliabilityStatus.FALLBACK_USED
    assert decision.selected_source_id == "secondary" and decision.fallback_used
    unavailable = service.decide(DataFamily.CURRENT_QUOTES, (primary,))
    assert unavailable.availability.status is ReliabilityStatus.PRIMARY_UNAVAILABLE
    assert unavailable.selected_source_id is None
    conflicted = service.decide(DataFamily.CURRENT_QUOTES, (
        SourceHealth("one", DataFamily.CURRENT_QUOTES, 1, SourceReadinessStatus.READY, T, True, value_fingerprint="a"),
        SourceHealth("two", DataFamily.CURRENT_QUOTES, 2, SourceReadinessStatus.READY, T, True, value_fingerprint="b"),
    ))
    assert conflicted.availability.status is ReliabilityStatus.CONFLICTED


def test_historical_integrity_delegates_to_pit_guard_and_never_assumes_current_universe():
    service = HistoricalIntegrityService()
    future = HistoricalFact("future-filing", "filing", T, T + timedelta(days=1), T)
    assert service.assess(future, as_of=T).status is HistoricalIntegrityStatus.INVALID
    eligible = HistoricalFact("eligible-filing", "filing", T - timedelta(days=1), T - timedelta(days=1), T - timedelta(days=1))
    assert service.assess(eligible, as_of=T, require_membership=True).status is HistoricalIntegrityStatus.PARTIAL
    membership = UniverseMembership("membership", "stock-1", "nifty", T - timedelta(days=30), T - timedelta(days=1), T - timedelta(days=30), "nse", "official", InstrumentLifecycle.DELISTED)
    decision = service.assess(eligible, as_of=T, membership=membership, require_membership=True)
    assert decision.status is HistoricalIntegrityStatus.INVALID
    historic = service.assess(eligible, as_of=T - timedelta(days=1), membership=membership, require_membership=True)
    assert historic.status is HistoricalIntegrityStatus.VALID


def test_governance_drift_is_immutable_recommendation_only_and_survives_restart(tmp_path):
    baseline = ModelVersionPerformance("baseline", "strategy", "v1", "expectancy", Decimal("1.0"), T - timedelta(days=60), T - timedelta(days=30), "RISK_ON", ("performance-a",), T, "baseline-fingerprint")
    current = ModelVersionPerformance("current", "strategy", "v1", "expectancy", Decimal("0.4"), T - timedelta(days=30), T, "RISK_ON", ("performance-b",), T, "current-fingerprint")
    service = GovernanceDriftService()
    observation = service.observe(baseline=baseline, current=current, threshold=Decimal("0.25"), created_at=T)
    assessment = service.assess(observations=(observation,), strategy_id="strategy", strategy_version="v1", created_at=T)
    assert assessment.health is GovernanceHealth.DISABLE_RECOMMENDED
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'governance.db'}"))
    store = GovernanceDriftStore(repository)
    store.save_observation(observation); store.save_assessment(assessment)
    repository.close()
    reopened = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'governance.db'}"))
    restored = GovernanceDriftStore(reopened)
    assert restored.get_observation(observation.observation_id) == observation
    assert restored.get_assessment(assessment.assessment_id) == assessment
    with pytest.raises(ValueError, match="immutable"):
        restored.save_assessment(assessment)
    assert assessment.recommendation == "REVIEW_REQUIRED_NO_AUTOMATIC_DEPLOYMENT"


def test_decision_audit_is_append_only_reconstructs_frozen_references_and_links_outcomes(tmp_path):
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'audit.db'}"))
    store = DecisionAuditStore(repository)
    unsigned = DecisionAuditRecord(
        "audit-1", "stock-1", T, "portfolio-1", "universe-1", "market-1", ("snapshot-1",),
        ("FALLBACK_USED",), "registry-v1", "score-v1", "confidence-v1", "gates-v1", "rotation-v1", "engine-v1",
        "WATCH", ("internal-evidence-1",), T, "",
    )
    record = DecisionAuditRecord(
        unsigned.audit_id, unsigned.instrument_id, unsigned.as_of, unsigned.portfolio_snapshot_id,
        unsigned.universe_snapshot_id, unsigned.market_context_snapshot_id, unsigned.data_snapshot_ids,
        unsigned.source_summary, unsigned.diagnostic_registry_version, unsigned.decision_score_version,
        unsigned.confidence_version, unsigned.gate_policy_version, unsigned.rotation_policy_version,
        unsigned.engine_version, unsigned.final_public_decision, unsigned.internal_evidence_ids,
        unsigned.created_at, decision_audit_fingerprint(unsigned),
    )
    store.save_record(record)
    outcome = DecisionOutcomeLink("outcome-1", record.audit_id, "PAPER_TRADE", "trade-1", T + timedelta(days=1), "")
    outcome = DecisionOutcomeLink(outcome.link_id, outcome.audit_id, outcome.outcome_type, outcome.outcome_id, outcome.linked_at, decision_outcome_fingerprint(outcome))
    store.save_outcome(outcome)
    bundle = DecisionAuditService(store).reconstruct_decision(record.audit_id)
    assert bundle.record == record and bundle.outcomes == (outcome,)
    with pytest.raises(ValueError, match="immutable"):
        store.save_record(record)
    repository.close()
    reopened = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'audit.db'}"))
    assert DecisionAuditService(DecisionAuditStore(reopened)).reconstruct_decision(record.audit_id) == bundle
