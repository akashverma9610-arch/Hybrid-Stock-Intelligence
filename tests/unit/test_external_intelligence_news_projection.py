from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.intelligence.external_intelligence import (
    CompanyExposure,
    EventType,
    ExposureType,
    ExternalEvent,
    Materiality,
    PolicyStage,
    SourceEvidence,
)
from app.intelligence.external_intelligence_application import (
    ExternalIntelligenceApplicationService,
    ExternalIntelligenceRecordCommand,
)
from app.intelligence.external_intelligence_news_projection import (
    EXTERNAL_INTELLIGENCE_NEWS_PROVIDER,
    ExternalIntelligenceNewsProjector,
)
from app.news.models import NewsSourceQuality
from app.news.store import SQLiteNewsEvidenceStore
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


T0 = datetime(2026, 9, 1, 9, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T1 + timedelta(minutes=1)


def command(*, summary: str = "Synthetic summary V1") -> ExternalIntelligenceRecordCommand:
    event = ExternalEvent(
        "HSI_EXTERNAL_INTELLIGENCE_DESK", "test-rbi-1", EventType.MONETARY_POLICY,
        "TEST_RBI_POLICY_EVENT", "IN", "MACRO", Materiality.HIGH, T0, PolicyStage.STATEMENT,
    )
    verified = CompanyExposure("NSE:INE090A01021", "ICICI Bank", ExposureType.DIRECT, 0.9, "VERIFIED")
    unverified = CompanyExposure(None, "Unmapped free-text company", ExposureType.DIRECT, 0.4)
    return ExternalIntelligenceRecordCommand(
        event, T0, T0, summary, "Synthetic policy change", SourceEvidence("RBI", "OFFICIAL", "https://invalid.test/rbi", 0.95),
        supporting_sources=(SourceEvidence("PIB", "OFFICIAL", "https://invalid.test/pib", 0.85),),
        company_exposures=(verified, unverified), event_confidence=0.9, exposure_confidence=0.8,
        time_horizon="MEDIUM_TERM", risks=("Synthetic risk",), counter_evidence=("Synthetic counter",),
        why_hsi_should_care="Synthetic test only.", effective_at=T0,
        affected_sectors=("FINANCIALS",), affected_industries=("BANKS",),
    )


def test_projection_maps_canonical_evidence_deterministically_with_full_traceability(tmp_path) -> None:
    path = tmp_path / "projection.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    receipt = ExternalIntelligenceApplicationService(repository, clock=lambda: T1).record_event(command())
    event = repository.get_event(receipt.canonical_event_id)
    evidence = repository.get_evidence_version(receipt.evidence_version_id)
    news = SQLiteNewsEvidenceStore(path)
    projector = ExternalIntelligenceNewsProjector(news)
    projected = projector.project_and_save(event, evidence)

    assert projected.article_id == projector.projection_id(event, evidence)
    assert projected.source_provider == EXTERNAL_INTELLIGENCE_NEWS_PROVIDER
    assert projected.publisher == "RBI" and projected.publisher_url == "https://invalid.test/rbi"
    assert projected.source_quality is NewsSourceQuality.SECONDARY_RESEARCH
    assert projected.instrument_ids == ("NSE:INE090A01021",) and projected.sectors == ("FINANCIALS",)
    assert projected.received_at == T1 and not news.list(as_of=T1 - timedelta(seconds=1))
    assert news.list(as_of=T1) == (projected,)
    provenance = json.loads(projected.provenance.source_reference)
    assert provenance["canonical_event_id"] == event.canonical_event_id
    assert provenance["evidence_version_id"] == evidence.evidence_version_id
    assert provenance["producer_id"] == "HSI_EXTERNAL_INTELLIGENCE_DESK"
    assert provenance["event_fingerprint"] == event.fingerprint and provenance["evidence_fingerprint"] == evidence.fingerprint
    assert provenance["supporting_source_references"] == ["https://invalid.test/pib"]
    assert "Synthetic inference" not in (projected.description or "")
    assert "CANONICAL_EXTERNAL_INTELLIGENCE_RETAINS_FACT_DATA_INTERPRETATION_INFERENCE" in projected.warnings
    assert "INFERENCES_NOT_PROMOTED_TO_NEWS_FACTS" in projected.warnings
    assert "UNVERIFIED_COMPANY_EXPOSURES_NOT_MAPPED" in projected.warnings
    repository.close(); news._connection.close()


def test_projection_retry_new_evidence_reopen_and_no_duplicate_news_rows(tmp_path) -> None:
    path = tmp_path / "reopen.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    first_service = ExternalIntelligenceApplicationService(repository, clock=lambda: T1)
    first = first_service.record_event(command(summary="V1"))
    news = SQLiteNewsEvidenceStore(path)
    projector = ExternalIntelligenceNewsProjector(news)
    event = repository.get_event(first.canonical_event_id)
    evidence_one = repository.get_evidence_version(first.evidence_version_id)
    one = projector.project_and_save(event, evidence_one)
    assert projector.project_and_save(event, evidence_one) == one

    second = ExternalIntelligenceApplicationService(repository, clock=lambda: T2).record_event(command(summary="V2"))
    evidence_two = repository.get_evidence_version(second.evidence_version_id)
    two = projector.project_and_save(event, evidence_two)
    assert one.article_id != two.article_id
    assert news._connection.execute("SELECT COUNT(*) FROM news_evidence").fetchone()[0] == 2
    repository.close(); news._connection.close()

    reopened_repository = SQLiteExternalIntelligenceRepository(path)
    reopened_news = SQLiteNewsEvidenceStore(path)
    reopened_projector = ExternalIntelligenceNewsProjector(reopened_news)
    reopened_event = reopened_repository.get_event(first.canonical_event_id)
    reopened_evidence = reopened_repository.get_evidence_version(second.evidence_version_id)
    assert reopened_projector.project_and_save(reopened_event, reopened_evidence) == two
    assert reopened_news._connection.execute("SELECT COUNT(*) FROM news_evidence").fetchone()[0] == 2
    reopened_repository.close(); reopened_news._connection.close()


def test_projection_identity_conflict_fails_closed_without_replacing_news_evidence(tmp_path) -> None:
    path = tmp_path / "conflict.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    receipt = ExternalIntelligenceApplicationService(repository, clock=lambda: T1).record_event(command())
    event = repository.get_event(receipt.canonical_event_id); evidence = repository.get_evidence_version(receipt.evidence_version_id)
    news = SQLiteNewsEvidenceStore(path); projector = ExternalIntelligenceNewsProjector(news)
    projected = projector.project_and_save(event, evidence)
    payload = json.loads(news._connection.execute("SELECT payload_json FROM news_evidence WHERE article_id = ?", (projected.article_id,)).fetchone()[0])
    payload["title"] = "tampered"
    news._connection.execute("UPDATE news_evidence SET payload_json = ? WHERE article_id = ?", (json.dumps(payload), projected.article_id))
    news._connection.commit()
    with pytest.raises(ValueError, match="immutable and conflicted"):
        projector.project_and_save(event, evidence)
    assert news._connection.execute("SELECT COUNT(*) FROM news_evidence").fetchone()[0] == 1
    repository.close(); news._connection.close()


def test_projection_is_pure_no_url_fetch_brain_diagnostics_portfolio_or_trading_calls(tmp_path) -> None:
    path = tmp_path / "pure.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    receipt = ExternalIntelligenceApplicationService(repository, clock=lambda: T1).record_event(command())
    news = SQLiteNewsEvidenceStore(path)
    before = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    ExternalIntelligenceNewsProjector(news).project_and_save(
        repository.get_event(receipt.canonical_event_id), repository.get_evidence_version(receipt.evidence_version_id),
    )
    after = {row[0] for row in repository._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert after == before and "news_evidence" in after and "paper_trades" not in after
    source = __import__("inspect").getsource(__import__("app.intelligence.external_intelligence_news_projection", fromlist=["ExternalIntelligenceNewsProjector"]))
    assert not any(value in source for value in ("import requests", "import httpx", "urlopen(", "urllib.", "SharedBrain", "diagnostic", "portfolio", "sell_side", "broker"))
    repository.close(); news._connection.close()
