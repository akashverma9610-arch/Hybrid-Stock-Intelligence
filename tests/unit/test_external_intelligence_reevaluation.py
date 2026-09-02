"""V1E isolated, PIT-safe external-intelligence Shared Brain consumption."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.intelligence.external_intelligence import (
    CompanyExposure,
    EventType,
    ExposureType,
    ExternalEvent,
    Materiality,
    PolicyStage,
    ReevaluationRequest,
    SourceEvidence,
)
from app.intelligence.external_intelligence_application import (
    ExternalIntelligenceApplicationService,
    ExternalIntelligenceRecordCommand,
)
from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector
from app.intelligence.external_intelligence_reevaluation import (
    ExternalIntelligenceReevaluationConsumer,
    ExternalIntelligenceReevaluationDisposition,
)
from app.intelligence.macro_news_evidence import NewsCatalystEvidenceAdapter
from app.intelligence.shared_brain_application import (
    SharedBrainApplicationService,
    StoredSharedBrainEvidenceAssembler,
)
from app.intelligence.unified_state import BrainOutputContext, IntelligenceEvidenceDomain
from app.news.store import SQLiteNewsEvidenceStore
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
from app.fundamentals.store import SQLiteFinancialFactStore
from app.universe_analysis.models import NseEquityInstrument


T0 = datetime(2026, 9, 1, 9, tzinfo=UTC)
T1 = T0 + timedelta(hours=1)
T2 = T1 + timedelta(hours=1)
TARGET = "NSE:INE090A01021"


@dataclass(frozen=True, slots=True)
class _View:
    evidence_domains: tuple[tuple[str, str], ...]
    evidence_status: str
    blockers: tuple[str, ...]


class _SharedBrainSpy:
    """Uses the existing News adapter and exposes only the reader's view fields."""

    def __init__(self, news: SQLiteNewsEvidenceStore, *, fail: bool = False) -> None:
        self._adapter = NewsCatalystEvidenceAdapter(news=news)
        self._news = news
        self._fail = fail
        self.calls: list[tuple[str, BrainOutputContext, datetime, tuple[str, ...]]] = []

    def analyze_stock(self, identifier: str, *, context: BrainOutputContext, as_of: datetime) -> _View:
        if self._fail:
            raise ValueError("synthetic Shared Brain composition failure")
        artifacts = self._adapter.artifacts(identifier, as_of=as_of)
        news = next(item for item in artifacts if item.domain is IntelligenceEvidenceDomain.NEWS_CATALYSTS)
        visible = tuple(item.article_id for item in self._news.list(instrument_id=identifier, as_of=as_of))
        self.calls.append((identifier, context, as_of, visible))
        return _View((("NEWS_CATALYSTS", news.availability.value),), "PARTIAL", ("OTHER_DOMAINS_MISSING",))


class _ExactResolver:
    def __init__(self) -> None:
        self.instrument = NseEquityInstrument(
            TARGET, "ICICIBANK", "INE090A01021", "DEMO", "FINANCIALS", "LISTED",
            None, True, T0, "TEST_OFFICIAL", company_name="ICICI Bank",
        )

    def resolve(self, identifier: str, *, as_of: datetime) -> NseEquityInstrument:
        if identifier != TARGET:
            raise ValueError("exact canonical target required")
        return self.instrument


def _command(
    *,
    summary: str = "Synthetic summary V1",
    exposures: tuple[CompanyExposure, ...] | None = None,
    requires_hsi_analysis: bool = True,
) -> ExternalIntelligenceRecordCommand:
    event = ExternalEvent(
        "HSI_EXTERNAL_INTELLIGENCE_DESK", "test-rbi-1", EventType.MONETARY_POLICY,
        "TEST_RBI_POLICY_EVENT", "IN", "MACRO", Materiality.HIGH, T0, PolicyStage.STATEMENT,
    )
    verified = CompanyExposure(TARGET, "ICICI Bank", ExposureType.DIRECT, 0.9, "VERIFIED")
    return ExternalIntelligenceRecordCommand(
        event, T0, T0, summary, "Synthetic policy change",
        SourceEvidence("RBI", "OFFICIAL", "https://invalid.test/rbi", 0.95),
        company_exposures=(verified,) if exposures is None else exposures,
        affected_sectors=("FINANCIALS",), affected_industries=("BANKS",),
        requires_hsi_analysis=requires_hsi_analysis,
    )


def _record(repository, *, received_at: datetime, **kwargs):
    return ExternalIntelligenceApplicationService(repository, clock=lambda: received_at).record_event(_command(**kwargs))


def _consumer(repository, news, brain=None):
    return ExternalIntelligenceReevaluationConsumer(repository, news, brain or _SharedBrainSpy(news))


class _RequestRepositoryView:
    """Read-only test view for impossible-in-production broken lineage rows."""

    def __init__(self, repository, request) -> None:
        self._repository = repository
        self._request = request

    def get_reevaluation_request(self, request_id: str):
        return self._request

    def get_event(self, canonical_event_id: str):
        return self._repository.get_event(canonical_event_id)

    def get_evidence_version(self, evidence_version_id: str):
        return self._repository.get_evidence_version(evidence_version_id)


def test_consumer_reuses_existing_news_adapter_with_exact_request_lineage_pit_and_retry(tmp_path) -> None:
    path = tmp_path / "v1e.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    receipt = _record(repository, received_at=T1)
    event = repository.get_event(receipt.canonical_event_id)
    evidence = repository.get_evidence_version(receipt.evidence_version_id)
    request = repository.get_reevaluation_request(receipt.reevaluation_request_id)
    projected = ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence)
    brain = _SharedBrainSpy(news)
    consumer = _consumer(repository, news, brain)

    before = consumer.consume(request.request_id, intelligence_as_of=T1 - timedelta(microseconds=1))
    assert before.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_NOT_VISIBLE_AS_OF
    assert not brain.calls
    after = consumer.consume(request.request_id, intelligence_as_of=T1)
    retry = consumer.consume(request.request_id, intelligence_as_of=T1)

    assert after == retry
    assert after.disposition is ExternalIntelligenceReevaluationDisposition.COMPLETED_READ_ONLY
    assert (after.canonical_event_id, after.evidence_version_id, after.targeted_canonical_instruments) == (
        event.canonical_event_id, evidence.evidence_version_id, (TARGET,),
    )
    assert after.targets[0].news_state_before == "UNAVAILABLE"
    assert after.targets[0].news_state_after == "PARTIAL"
    assert after.targets[0].overall_brain_state_before == after.targets[0].overall_brain_state_after == "PARTIAL"
    assert all(call[1] is BrainOutputContext.ALERT_REVIEW for call in brain.calls)
    assert brain.calls[-1][3] == (projected.article_id,)
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    assert news._connection.execute("SELECT COUNT(*) FROM news_evidence").fetchone()[0] == 1
    repository.close(); news._connection.close()


def test_v1_v2_visibility_is_received_at_safe_and_uses_only_existing_news_rows(tmp_path) -> None:
    path = tmp_path / "v1-v2.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    first = _record(repository, received_at=T1, summary="V1")
    event = repository.get_event(first.canonical_event_id)
    evidence_one = repository.get_evidence_version(first.evidence_version_id)
    projector = ExternalIntelligenceNewsProjector(news)
    projected_one = projector.project_and_save(event, evidence_one)
    second = _record(repository, received_at=T2, summary="V2")
    evidence_two = repository.get_evidence_version(second.evidence_version_id)
    projected_two = projector.project_and_save(event, evidence_two)
    brain = _SharedBrainSpy(news)
    consumer = _consumer(repository, news, brain)

    v1_before_v2 = consumer.consume(first.reevaluation_request_id, intelligence_as_of=T2 - timedelta(microseconds=1))
    v2_before_v2 = consumer.consume(second.reevaluation_request_id, intelligence_as_of=T2 - timedelta(microseconds=1))
    v2_after_v2 = consumer.consume(second.reevaluation_request_id, intelligence_as_of=T2)

    assert v1_before_v2.disposition is ExternalIntelligenceReevaluationDisposition.COMPLETED_READ_ONLY
    assert v2_before_v2.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_NOT_VISIBLE_AS_OF
    assert v2_after_v2.disposition is ExternalIntelligenceReevaluationDisposition.COMPLETED_READ_ONLY
    assert brain.calls[1][3] == (projected_one.article_id,)
    assert brain.calls[-1][3] == tuple(sorted((projected_one.article_id, projected_two.article_id), reverse=True))
    repository.close(); news._connection.close()


def test_existing_shared_brain_service_consumes_projected_news_with_its_native_availability_policy(tmp_path) -> None:
    path = tmp_path / "native-shared-brain.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    receipt = _record(repository, received_at=T1)
    event = repository.get_event(receipt.canonical_event_id)
    evidence = repository.get_evidence_version(receipt.evidence_version_id)
    projected = ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence)
    shared_brain = SharedBrainApplicationService(
        resolver=_ExactResolver(),
        evidence_assembler=StoredSharedBrainEvidenceAssembler(SQLiteFinancialFactStore(path), news=news),
        clock=lambda: T1,
    )

    before = shared_brain.analyze_stock(TARGET, context=BrainOutputContext.ALERT_REVIEW, as_of=T1 - timedelta(microseconds=1))
    after = shared_brain.analyze_stock(TARGET, context=BrainOutputContext.ALERT_REVIEW, as_of=T1)

    assert dict(before.evidence_domains)["NEWS_CATALYSTS"] == "UNAVAILABLE"
    assert dict(after.evidence_domains)["NEWS_CATALYSTS"] == "PARTIAL"
    assert after.evidence_status == "PARTIAL"
    assert projected.article_id in news.list(instrument_id=TARGET, as_of=T1)[0].article_id
    repository.close(); news._connection.close()


def test_unverified_or_sector_only_request_does_not_expand_to_a_stock_brain_target(tmp_path) -> None:
    path = tmp_path / "unverified.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    unverified = CompanyExposure(None, "Free-text issuer only", ExposureType.THEMATIC, 0.4)
    receipt = _record(repository, received_at=T1, exposures=(unverified,))
    event = repository.get_event(receipt.canonical_event_id)
    evidence = repository.get_evidence_version(receipt.evidence_version_id)
    ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence)
    request = repository.get_reevaluation_request(receipt.reevaluation_request_id)
    brain = _SharedBrainSpy(news)

    result = _consumer(repository, news, brain).consume(request.request_id, intelligence_as_of=T1)

    assert request.affected_canonical_instruments == () and request.affected_sectors == ("FINANCIALS",)
    assert result.disposition is ExternalIntelligenceReevaluationDisposition.UNSUPPORTED_NO_VERIFIED_CANONICAL_TARGET
    assert result.targeted_canonical_instruments == () and not brain.calls
    assert news.list(as_of=T1)[0].instrument_ids == ()
    repository.close(); news._connection.close()


def test_missing_tampered_target_and_shared_brain_failures_are_closed_without_request_mutation(tmp_path) -> None:
    path = tmp_path / "failures.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    missing = _consumer(repository, news).consume("missing-request", intelligence_as_of=T1)
    assert missing.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_REQUEST_NOT_FOUND

    receipt = _record(repository, received_at=T1, requires_hsi_analysis=False)
    event = repository.get_event(receipt.canonical_event_id)
    evidence = repository.get_evidence_version(receipt.evidence_version_id)
    invalid_request = ReevaluationRequest(
        event.canonical_event_id, evidence.evidence_version_id, event.materiality, T1,
        ("NSE:INVALID",), ("FINANCIALS",), ("BANKS",),
    )
    repository.save_reevaluation_request(invalid_request)
    missing_projection = _consumer(repository, news).consume(invalid_request.request_id, intelligence_as_of=T1)
    assert missing_projection.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_NEWS_PROJECTION_MISSING

    projected = ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence)
    invalid_target = _consumer(repository, news).consume(invalid_request.request_id, intelligence_as_of=T1)
    assert invalid_target.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_TARGET_INVALID
    payload = json.loads(news._connection.execute(
        "SELECT payload_json FROM news_evidence WHERE article_id = ?", (projected.article_id,),
    ).fetchone()[0])
    payload["title"] = "tampered projection"
    news._connection.execute("UPDATE news_evidence SET payload_json = ? WHERE article_id = ?", (json.dumps(payload), projected.article_id))
    news._connection.commit()
    tampered = _consumer(repository, news).consume(invalid_request.request_id, intelligence_as_of=T1)
    assert tampered.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_NEWS_PROJECTION_INVALID
    assert repository.get_reevaluation_request(invalid_request.request_id) == invalid_request

    # A valid request whose existing Shared Brain read fails remains blocked; no state changes occur.
    valid = _record(repository, received_at=T2, summary="V2")
    evidence_two = repository.get_evidence_version(valid.evidence_version_id)
    ExternalIntelligenceNewsProjector(news).project_and_save(event, evidence_two)
    failed_brain = _consumer(repository, news, _SharedBrainSpy(news, fail=True)).consume(
        valid.reevaluation_request_id, intelligence_as_of=T2,
    )
    assert failed_brain.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_SHARED_BRAIN_UNAVAILABLE
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 2, "reevaluation_requests": 2}
    repository.close(); news._connection.close()


def test_missing_event_and_evidence_lineage_are_closed_without_writing(tmp_path) -> None:
    path = tmp_path / "missing-lineage.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    missing_event_request = ReevaluationRequest("external-event:missing", "external-evidence:missing", Materiality.HIGH, T1)
    missing_event = _consumer(_RequestRepositoryView(repository, missing_event_request), news).consume(
        missing_event_request.request_id, intelligence_as_of=T1,
    )
    assert missing_event.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_EVENT_NOT_FOUND

    receipt = _record(repository, received_at=T1, requires_hsi_analysis=False)
    event = repository.get_event(receipt.canonical_event_id)
    missing_evidence_request = ReevaluationRequest(event.canonical_event_id, "external-evidence:missing", event.materiality, T1)
    missing_evidence = _consumer(_RequestRepositoryView(repository, missing_evidence_request), news).consume(
        missing_evidence_request.request_id, intelligence_as_of=T1,
    )
    assert missing_evidence.disposition is ExternalIntelligenceReevaluationDisposition.BLOCKED_EVIDENCE_NOT_FOUND
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 0}
    repository.close(); news._connection.close()


def test_consumer_has_no_diagnostics_portfolio_or_execution_surface() -> None:
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "external_intelligence_reevaluation.py").read_text(encoding="utf-8").lower()
    assert not any(token in source for token in (
        "diagnostic", "portfolio", "sell_side", "broker", "papertrade", "executiongate", "decision score", "six gates", "setup engine",
    ))
