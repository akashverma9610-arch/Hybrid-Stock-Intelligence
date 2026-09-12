from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.data_sources.models import DataFamily, SourceRecordProvenance
from app.intelligence.catalysts import CatalystService, CatalystType, PolicyImplementationStage
from app.intelligence.company_sensitivity import CompanySensitivity, CompanySensitivityProfile, MacroToEarningsTransmissionEngine
from app.intelligence.macro import MacroEvidence, MacroInputFamily, MacroStateService
from app.intelligence.macro.service import IntelligenceSourceTier
from app.intelligence.sector_economics import SectorSensitivity, SectorSensitivityProfile, SectorTransmissionService
from app.intelligence.sector_economics.service import ProfileProvenance, SensitivityDirection, SensitivityMagnitude
from app.intelligence.store import IntelligenceSnapshotStore
from app.news.hardening import NewsEventClusteringService
from app.news.models import NewsArticleEvidence, NewsEventCategory, NewsSourceQuality
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.storage.database import DatabaseBackend, DatabaseSettings
from app.storage.repository_factory import create_core_api_snapshot_repository


T = datetime(2026, 8, 26, 10, tzinfo=UTC)

def _macro(identifier, component, state, *, available=T, reliability=.8):
    return MacroEvidence(identifier, MacroInputFamily.MONETARY_RATES, component, state, IntelligenceSourceTier.OFFICIAL, "official:" + identifier, available, available, available, available, reliability, "FRESH")

def _profile(identifier, sector, sensitivity):
    return SectorSensitivityProfile(identifier, sector, "sector-template-v1", (sensitivity,), ProfileProvenance.RULE_DERIVED, T)


def test_macro_state_independent_components_conflicts_and_future_revision_are_pit_safe(tmp_path):
    service = MacroStateService()
    state = service.build(state_id="macro-1", as_of=T, evidence=(
        _macro("rates", "rates", "TIGHTENING"), _macro("liquidity", "liquidity", "DEFICIT"),
        _macro("inr", "inr", "WEAKENING"), _macro("fii", "fii_flow", "OUTFLOW"),
        _macro("future-revision", "growth", "EXPANDING", available=T + timedelta(days=1)),
    ))
    assert state.rates.value == "TIGHTENING" and state.liquidity.value == "DEFICIT" and state.inr.value == "WEAKENING" and state.fii_flow.value == "OUTFLOW"
    assert "MACRO_EVIDENCE_EXCLUDED_AS_OF" in state.warnings and state.growth is None
    conflicted = service.build(state_id="macro-2", as_of=T, evidence=(_macro("a", "rates", "EASING"), _macro("b", "rates", "TIGHTENING")))
    assert conflicted.rates is None and "MACRO_SOURCE_CONFLICT:rates" in conflicted.warnings
    repository = create_core_api_snapshot_repository(DatabaseSettings(DatabaseBackend.SQLITE, f"sqlite:///{tmp_path / 'macro.db'}"))
    store = IntelligenceSnapshotStore(repository); store.save(record_id=state.state_id, family=CoreApiSnapshotFamily.MACRO_STATE, value=state, created_at=T)
    assert store.get(record_id=state.state_id, family=CoreApiSnapshotFamily.MACRO_STATE) == state


def test_same_macro_state_transmits_differently_by_sector_and_company_override():
    macro = MacroStateService().build(state_id="macro", as_of=T, evidence=(_macro("rates", "rates", "TIGHTENING"),))
    rate_sensitive = SectorSensitivity("rates", SensitivityDirection.NEGATIVE, SensitivityMagnitude.HIGH, "1-4 quarters", .8, ("sector-evidence",))
    bank = SectorSensitivity("rates", SensitivityDirection.MIXED, SensitivityMagnitude.MODERATE, "next repricing", .7, ("bank-evidence",))
    realty_impacts = SectorTransmissionService().transmit(macro=macro, profile=_profile("realty", "REALTY", rate_sensitive))
    bank_impacts = SectorTransmissionService().transmit(macro=macro, profile=_profile("bank", "BANKS", bank))
    assert realty_impacts[0].direction is SensitivityDirection.NEGATIVE and bank_impacts[0].direction is SensitivityDirection.MIXED
    company_a = CompanySensitivityProfile("a", "A", "REALTY", "company-v1", (CompanySensitivity("rates", SensitivityDirection.MIXED, SensitivityMagnitude.LOW, "pass-through", "quarter", .9, ProfileProvenance.SOURCE_DERIVED, ("a-filing",)),), T)
    company_b = CompanySensitivityProfile("b", "B", "REALTY", "company-v1", (CompanySensitivity("rates", SensitivityDirection.NEGATIVE, SensitivityMagnitude.HIGH, "fixed-price", "quarter", .9, ProfileProvenance.SOURCE_DERIVED, ("b-filing",)),), T)
    engine = MacroToEarningsTransmissionEngine()
    assert engine.transmit(profile=company_a, sector_impacts=realty_impacts)[0].margin_impact is SensitivityDirection.MIXED
    assert engine.transmit(profile=company_b, sector_impacts=realty_impacts)[0].margin_impact is SensitivityDirection.NEGATIVE
    unknown = CompanySensitivityProfile("unknown", "U", "REALTY", "company-v1", (), T)
    assert "COMPANY_SENSITIVITY_UNKNOWN_NO_SECTOR_FACT_SUBSTITUTION" in engine.transmit(profile=unknown, sector_impacts=realty_impacts)[0].warnings


def test_event_catalyst_materiality_policy_gap_and_dedup_preserve_lineage():
    provenance = SourceRecordProvenance("nse", "nse", "filing", T - timedelta(days=10), T - timedelta(days=10), T, None, None, DataFamily.NEWS_RESEARCH, "v1", "v1")
    item = lambda identifier, received: NewsArticleEvidence(identifier, "nse", "NSE", None, "https://example.com/" + identifier, "Order", None, T - timedelta(days=10), received, "en", "in", ("company-a",), ("INDUSTRIAL",), (), NewsSourceQuality.PRIMARY_EXCHANGE, provenance, NewsEventCategory.ORDER_CONTRACT, "filing-1")
    cluster = NewsEventClusteringService().cluster((item("a", T - timedelta(days=10)), item("b", T)))[0]
    event = CatalystService().from_cluster(event_id="cat-1", cluster=cluster, event_type=CatalystType.ORDER_WIN, company_id="company-a", sector="INDUSTRIAL", publication_date=T, retrieved_at=T, source_quality=NewsSourceQuality.PRIMARY_EXCHANGE)
    assert event.event_date == T - timedelta(days=10) and len(event.evidence_ids) == 2 and event.primary_source_confirmation
    service = CatalystService()
    small = service.order_materiality(event_id="cat-a", order_value=Decimal("500"), ttm_revenue=Decimal("2000"))
    large = service.order_materiality(event_id="cat-b", order_value=Decimal("500"), ttm_revenue=Decimal("100000"))
    assert small.order_to_revenue > large.order_to_revenue
    assert not service.policy_realized(PolicyImplementationStage.ANNOUNCED)
    assert service.policy_realized(PolicyImplementationStage.PROJECT_EXECUTION)


def test_economic_intelligence_has_no_decision_engine_or_action_imports():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "app" / "intelligence"
    sources = []
    for item in root.rglob("*.py"):
        source = item.read_text(encoding="utf-8")
        if item == root / "six_gates_evidence.py":
            # B08's one pure rejection helper is not a gate engine/action call.
            admission = "from app.gates.version_compatibility import require_gate_source\n"
            assert source.count(admission) == 1
            assert ".evaluate(" not in source and "require_gate_inputs(" not in source
            source = source.replace(admission, "")
        sources.append(source)
    text = "\n".join(sources)
    assert "app.scoring" not in text and "app.gates" not in text and "RotationDecisionState" not in text
