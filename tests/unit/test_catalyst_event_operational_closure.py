"""Synthetic stored-evidence proofs; no live sources or production database."""
from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pytest

from app.api.main import create_app
from app.api.settings import APISettings
from app.intelligence.external_intelligence import EventType
from app.intelligence.external_intelligence_application import ExternalIntelligenceApplicationService
from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.intelligence.unified_state import IntelligenceEvidenceDomain
from app.fundamentals.store import SQLiteFinancialFactStore
from app.news.store import SQLiteNewsEvidenceStore
from app.filings.store import SQLiteCorporateFilingsStore
from app.intelligence.local_openai_worker import ResponsesResult, parse_worker_discovery
from app.storage.database import DatabaseSettings
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository
from app.storage.repository_factory import create_core_api_snapshot_repository
from app.universe_analysis.service import CoreUniverseAnalysisStore
from tests.unit.test_external_intelligence_reevaluation import _command, _ExactResolver, TARGET, T0, T1, T2
from tests.unit.test_external_intelligence_api import payload, headers, PATH
from tests.unit.test_unified_intelligence_macro_news_evidence import _news, _filing


def expected_catalyst_binding_source(path, accepted):
    """Exact additive successor of pinned source; historical hashes stay intact."""
    replacements = {
        "app/intelligence/external_intelligence_application.py": (
            ("from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository\n",
             "from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository\n"
             "from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector\n"),
            ("        *, clock: Callable[[], datetime] | None = None,\n",
             "        *, clock: Callable[[], datetime] | None = None,\n"
             "        news_projector: ExternalIntelligenceNewsProjector | None = None,\n"),
            ("        self._clock = clock or (lambda: datetime.now(UTC))\n",
             "        self._clock = clock or (lambda: datetime.now(UTC))\n"
             "        self._news_projector = news_projector\n"),
            ("        disposition = (\n",
             "        # The canonical transaction must complete before derived News is written.\n"
             "        # Replays also project: a failed derivative write can be repaired by the\n"
             "        # same request without duplicating or backdating canonical evidence.\n"
             "        if self._news_projector is not None:\n"
             "            self._news_projector.project_and_save(event, evidence)\n\n"
             "        disposition = (\n"),
        ),
        "app/api/dependencies.py": (
            ("from app.storage.database import DatabaseBackend\n",
             "from app.storage.database import DatabaseBackend\n"
             "from app.intelligence.external_intelligence_news_projection import ExternalIntelligenceNewsProjector\n"
             "from app.news.store import SQLiteNewsEvidenceStore\n"),
            ("    service = ExternalIntelligenceApplicationService(repository)\n",
             "    try:\n"
             "        news = SQLiteNewsEvidenceStore(database.url.removeprefix(\"sqlite:///\"))\n"
             "    except Exception:\n"
             "        repository.close()\n"
             "        raise\n"
             "    service = ExternalIntelligenceApplicationService(\n"
             "        repository, news_projector=ExternalIntelligenceNewsProjector(news),\n"
             "    )\n"
             "    request.app.state.external_intelligence_news_store = news\n"),
        ),
        "app/api/main.py": (
            ("        external_repository.close()\n",
             "        external_repository.close()\n"
             "    external_news = getattr(application.state, \"external_intelligence_news_store\", None)\n"
             "    if external_news is not None:\n"
             "        external_news._connection.close()\n"),
            ("    application.state.external_intelligence_application_repository = None\n",
             "    application.state.external_intelligence_application_repository = None\n"
             "    application.state.external_intelligence_news_store = None\n"),
        ),
        "tests/unit/test_hsi_brain_funnel_runtime_reconciliation_audit.py": (
            ('    assert "sha256:" + sha256(current).hexdigest() == expected\n'
             '    assert current == accepted\n',
             '    assert "sha256:" + sha256(accepted).hexdigest() == expected\n'
             '    if path in {"app/api/main.py", "app/api/dependencies.py"}:\n'
             '        from tests.unit.test_catalyst_event_operational_closure import expected_catalyst_binding_source\n'
             '        accepted = expected_catalyst_binding_source(path, accepted)\n'
             '    assert current == accepted\n'),
        ),
    }
    for before, after in replacements[path]:
        before, after = before.encode(), after.encode()
        assert accepted.count(before) == 1, (path, "exact predecessor anchor required")
        accepted = accepted.replace(before, after, 1)
    return accepted


def _reference(assembler, cutoff):
    state = assembler.assemble(_ExactResolver().instrument, as_of=cutoff).unified_state
    return state, next(r for r in state.evidence_references
                       if r.domain is IntelligenceEvidenceDomain.NEWS_CATALYSTS)


@pytest.fixture
def chain(tmp_path):
    path = tmp_path / "events.sqlite"
    repository = SQLiteExternalIntelligenceRepository(path)
    news = SQLiteNewsEvidenceStore(path)
    facts = SQLiteFinancialFactStore(path)
    service = ExternalIntelligenceApplicationService(
        repository, clock=lambda: T1, news_projector=ExternalIntelligenceNewsProjector(news),
    )
    assembler = StoredSharedBrainEvidenceAssembler(facts, news=news)
    yield repository, news, service, assembler
    repository.close()
    news._connection.close()
    facts._connection.close()


@pytest.mark.parametrize("event_type,summary", [
    (EventType.ORDER_WIN, "Synthetic disclosed order award; economic significance unassessed"),
    (EventType.REGULATORY, "Synthetic adverse enforcement disclosure; liability unresolved"),
    (EventType.GOVERNANCE, "Synthetic mixed disclosure; allegation and company denial retained"),
])
def test_direct_evidence_enters_existing_brain_without_direction_or_authority_inference(chain, event_type, summary):
    repository, news, service, assembler = chain
    command = _command(summary=summary)
    command = replace(command, event=replace(command.event, event_type=event_type))
    receipt = service.record_event(command)
    state, reference = _reference(assembler, T1)
    article = news.list(as_of=T1)[0]
    lineage = json.loads(article.provenance.source_reference)
    assert reference.artifact_ids == ("news-evidence:" + article.article_id,)
    assert reference.availability.value == "PARTIAL"
    assert reference.freshness_status.value == "unknown"
    assert reference.freshness_policy_reference is None
    assert lineage["canonical_event_id"] == receipt.canonical_event_id
    assert lineage["evidence_fingerprint"] == receipt.evidence_fingerprint
    assert summary not in repr(state)  # Brain carries references, not AI prose/facts.
    for domain in (IntelligenceEvidenceDomain.DECISION_SCORE, IntelligenceEvidenceDomain.SIX_GATES):
        assert next(r for r in state.evidence_references if r.domain is domain).availability.value == "UNAVAILABLE"
    assert repository.external_intelligence_row_counts()["events"] == 1


def test_replay_and_new_report_retain_one_event_and_pit_safe_revision_lineage(chain):
    repository, news, service, assembler = chain
    first = service.record_event(_command(summary="Original disclosure"))
    original_state, original = _reference(assembler, T1)
    assert service.record_event(_command(summary="Original disclosure")).disposition.value == "ACCEPTED_EXISTING"
    assert len(news.list(as_of=T1)) == 1
    later = ExternalIntelligenceApplicationService(
        repository, clock=lambda: T2, news_projector=ExternalIntelligenceNewsProjector(news),
    )
    updated = later.record_event(_command(summary="Later report; same real event identity"))
    assert updated.canonical_event_id == first.canonical_event_id
    assert updated.evidence_version_id != first.evidence_version_id
    assert repository.external_intelligence_row_counts()["events"] == 1
    assert _reference(assembler, T1)[0] == original_state
    assert len(_reference(assembler, T2)[1].artifact_ids) == 2  # Evidence versions, not independent catalysts.
    assert len(original.artifact_ids) == 1
    assert _reference(assembler, T1 - timedelta(microseconds=1))[1].availability.value == "UNAVAILABLE"


def test_identity_conflict_rejected_and_explicit_source_conflict_reaches_brain(chain):
    repository, news, service, assembler = chain
    command = _command()
    service.record_event(command)
    bad = replace(command, event=replace(command.event, country="US"))
    receipt = service.record_event(bad)
    assert receipt.disposition.value == "REJECTED_CONFLICT"
    assert len(news.list()) == 1
    news.save(_news("conflict", instrument_ids=(TARGET,), published=T0,
                    received=T1, warnings=("CONFLICTED",)))
    assert _reference(assembler, T1)[1].availability.value == "CONFLICTED"
    assert repository.external_intelligence_row_counts()["events"] == 1


def test_projection_failure_repaired_by_exact_retry_without_canonical_duplicates(chain):
    repository, news, _, assembler = chain

    class FailingOnce(ExternalIntelligenceNewsProjector):
        failed = False

        def project_and_save(self, event, evidence):
            if not self.failed:
                self.failed = True
                raise RuntimeError("synthetic derivative outage")
            return super().project_and_save(event, evidence)

    service = ExternalIntelligenceApplicationService(repository, clock=lambda: T1, news_projector=FailingOnce(news))
    with pytest.raises(RuntimeError, match="synthetic derivative outage"):
        service.record_event(_command())
    assert repository.external_intelligence_row_counts()["events"] == 1
    assert news.list() == ()
    assert _reference(assembler, T1)[1].availability.value == "UNAVAILABLE"
    assert service.record_event(_command()).disposition.value == "ACCEPTED_EXISTING"
    assert len(news.list()) == 1
    assert repository.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}


def test_empty_store_and_unverified_company_do_not_fabricate_catalyst(chain):
    _, news, service, assembler = chain
    assert _reference(assembler, T1)[1].availability.value == "UNAVAILABLE"
    command = _command()
    exposure = replace(command.company_exposures[0], verification_status="UNVERIFIED_INFERENCE")
    service.record_event(replace(command, company_exposures=(exposure,)))
    assert news.list()[0].instrument_ids == ()
    assert _reference(assembler, T1)[1].availability.value == "UNAVAILABLE"


def test_primary_disclosure_remains_primary_in_native_brain(tmp_path):
    path = tmp_path / "primary.sqlite"
    filings = SQLiteCorporateFilingsStore(path)
    facts = SQLiteFinancialFactStore(path)
    filing = _filing("primary-order")
    filing = replace(filing, instrument=replace(filing.instrument, instrument_id=TARGET))
    filings.save(filing)
    _, reference = _reference(StoredSharedBrainEvidenceAssembler(facts, filings=filings), T1)
    assert reference.availability.value == "AVAILABLE"
    assert reference.artifact_ids == ("exchange-disclosure:primary-order",)
    assert "OFFICIAL_EXCHANGE_DISCLOSURE" in reference.warnings
    assert reference.freshness_status.value == "unknown"  # Authority is not freshness.
    facts._connection.close()
    filings._connection.close()


def test_no_material_worker_result_is_valid_without_inserting_any_event(chain):
    repository, news, _, assembler = chain
    result = parse_worker_discovery(ResponsesResult(
        '{"outcome":"NO_NEW_MATERIAL_INTELLIGENCE","event":null}', 0,
    ))
    assert result.no_material and result.event is None
    assert repository.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    assert news.list() == ()
    assert _reference(assembler, T1)[1].availability.value == "UNAVAILABLE"


def test_default_authenticated_api_binding_feeds_native_brain_and_closes_owned_store(tmp_path, monkeypatch):
    class FixedTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return T1

    monkeypatch.setattr("app.intelligence.external_intelligence_application.datetime", FixedTime)
    monkeypatch.setattr("app.api.routes.intelligence.datetime", FixedTime)
    monkeypatch.setenv("HSI_EXTERNAL_INTELLIGENCE_INGEST_TOKEN", "test-secret")
    monkeypatch.setenv("DHAN_LIVE_MARKET_ENABLED", "false")
    settings = DatabaseSettings(url=f"sqlite:///{tmp_path / 'runtime.sqlite'}")
    core = create_core_api_snapshot_repository(settings)
    CoreUniverseAnalysisStore(core).save_instrument(_ExactResolver().instrument)
    core.close()
    application = create_app(api_settings=APISettings(database=settings))
    with TestClient(application) as client:
        assert client.post(PATH, json=payload()).status_code == 401
        assert application.state.external_intelligence_news_store is None
        response = client.post(PATH, json=payload(), headers=headers())
        assert response.status_code == 201
        cutoff = datetime.fromisoformat(response.json()["received_at"])
        assert cutoff == T1
        store = application.state.external_intelligence_news_store
        assert len(store.list(as_of=cutoff)) == 1
        view = client.get(f"/api/v1/stocks/{TARGET}/shared-brain",
                          params={"context": "ALERT_REVIEW", "as_of": cutoff.isoformat()})
        assert view.status_code == 200
        assert {r["domain"]: r["availability"] for r in view.json()["evidence_domains"]}["NEWS_CATALYSTS"] == "PARTIAL"
        assert client.post(PATH, json=payload(), headers=headers()).status_code == 200
        assert len(store.list()) == 1
        assert "test-secret" not in response.text + view.text
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        store._connection.execute("SELECT 1")


def test_no_new_fetch_or_downstream_authority_in_application_binding():
    source = (Path(__file__).parents[2] / "app/intelligence/external_intelligence_application.py").read_text()
    assert not any(s in source for s in ("app.scoring", "app.gates", "app.portfolio", "app.strategies", "httpx", "urlopen", "requests."))
