from __future__ import annotations

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
    ExternalIntelligenceApplicationDisposition,
    ExternalIntelligenceApplicationService,
    ExternalIntelligenceRecordCommand,
)
from app.storage.sqlite_external_intelligence_repository import SQLiteExternalIntelligenceRepository


T0 = datetime(2026, 9, 1, 8, tzinfo=UTC)
T1 = T0 + timedelta(minutes=1)
T2 = T0 + timedelta(minutes=2)


def event(*, country: str = "IN") -> ExternalEvent:
    return ExternalEvent(
        "HSI_EXTERNAL_INTELLIGENCE_DESK", "test-rbi-1", EventType.MONETARY_POLICY,
        "TEST_RBI_POLICY_EVENT", country, "MACRO", Materiality.HIGH, T0, PolicyStage.STATEMENT,
    )


def command(
    *, summary: str = "V1", requires_hsi_analysis: bool = True, country: str = "IN",
    exposures: tuple[CompanyExposure, ...] = (),
) -> ExternalIntelligenceRecordCommand:
    return ExternalIntelligenceRecordCommand(
        event(country=country), T0, T0, summary, "Policy rate signal updated",
        SourceEvidence("Synthetic", "SYNTHETIC", "https://invalid.test/rbi", 0.9),
        company_exposures=exposures, affected_sectors=("FINANCIALS",), affected_industries=("BANKS",),
        requires_hsi_analysis=requires_hsi_analysis,
    )


def service(tmp_path, *, at: datetime = T1) -> tuple[SQLiteExternalIntelligenceRepository, ExternalIntelligenceApplicationService]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo = SQLiteExternalIntelligenceRepository(tmp_path / "external-intelligence.sqlite")
    return repo, ExternalIntelligenceApplicationService(repo, clock=lambda: at)


def test_application_service_constructs_and_records_new_event_with_verified_exposure_only(tmp_path) -> None:
    repo, value = service(tmp_path)
    verified = CompanyExposure("NSE:INE090A01021", None, ExposureType.DIRECT, 0.8, "VERIFIED")
    unverified = CompanyExposure(None, "Unmapped Co", ExposureType.DIRECT, 0.4)
    receipt = value.record_event(command(exposures=(unverified, verified)))
    assert receipt.disposition is ExternalIntelligenceApplicationDisposition.ACCEPTED_NEW
    assert receipt.received_at == T1 and receipt.reevaluation_requested is True
    assert receipt.evidence_version_id is not None and receipt.reevaluation_request_id is not None
    request = value.list_reevaluation_requests()[0]
    assert request.affected_canonical_instruments == ("NSE:INE090A01021",)
    assert request.affected_sectors == ("FINANCIALS",) and request.affected_industries == ("BANKS",)
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    repo.close()


def test_exact_retry_reuses_evidence_request_and_service_owned_received_at(tmp_path) -> None:
    repo, first_service = service(tmp_path, at=T1)
    first = first_service.record_event(command())
    retry = ExternalIntelligenceApplicationService(repo, clock=lambda: T2).record_event(command())
    assert first.disposition is ExternalIntelligenceApplicationDisposition.ACCEPTED_NEW
    assert retry.disposition is ExternalIntelligenceApplicationDisposition.ACCEPTED_EXISTING
    assert retry.received_at == T1 and retry.evidence_version_id == first.evidence_version_id
    assert retry.reevaluation_request_id == first.reevaluation_request_id
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    assert (value := repo.get_event(first.canonical_event_id)) is not None
    assert value.first_received_at == T1
    repo.close()


def test_existing_event_new_evidence_creates_new_request_and_no_analysis_creates_none(tmp_path) -> None:
    repo, first_service = service(tmp_path, at=T1)
    first = first_service.record_event(command())
    second = ExternalIntelligenceApplicationService(repo, clock=lambda: T2).record_event(command(summary="V2"))
    assert second.disposition is ExternalIntelligenceApplicationDisposition.ACCEPTED_NEW_EVIDENCE
    assert second.evidence_version_id != first.evidence_version_id
    assert second.reevaluation_request_id != first.reevaluation_request_id
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 2, "reevaluation_requests": 2}

    repo_no_request, no_request_service = service(tmp_path / "no-request", at=T1)
    receipt = no_request_service.record_event(command(requires_hsi_analysis=False))
    assert receipt.reevaluation_requested is False and receipt.reevaluation_request_id is None
    assert repo_no_request.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 0}
    repo.close(); repo_no_request.close()


def test_conflicting_producer_identity_returns_typed_conflict_without_mutation(tmp_path) -> None:
    repo, value = service(tmp_path)
    first = value.record_event(command())
    conflict = value.record_event(command(summary="conflicting", country="US"))
    assert conflict.disposition is ExternalIntelligenceApplicationDisposition.REJECTED_CONFLICT
    assert conflict.blocker == "Producer event identity maps to an incompatible canonical event."
    assert conflict.canonical_event_id == first.canonical_event_id and conflict.evidence_version_id is None
    assert repo.external_intelligence_row_counts() == {"events": 1, "evidence_versions": 1, "reevaluation_requests": 1}
    repo.close()


def test_pit_visibility_latest_and_stable_tie_break_prevent_future_leakage(tmp_path) -> None:
    repo, first_service = service(tmp_path, at=T1)
    first = first_service.record_event(command(summary="V1"))
    second_service = ExternalIntelligenceApplicationService(repo, clock=lambda: T2)
    second = second_service.record_event(command(summary="V2"))
    between = T1 + timedelta(seconds=30)
    assert tuple(item.evidence_version_id for item in second_service.list_evidence_visible_as_of(first.canonical_event_id, between)) == (first.evidence_version_id,)
    assert second_service.latest_evidence_as_of(first.canonical_event_id, between).evidence_version_id == first.evidence_version_id
    assert tuple(item.evidence_version_id for item in second_service.list_evidence_visible_as_of(first.canonical_event_id, T2)) == (first.evidence_version_id, second.evidence_version_id)
    assert second_service.latest_evidence_as_of(first.canonical_event_id, T2).evidence_version_id == second.evidence_version_id

    tied = second_service.record_event(command(summary="V3"))
    visible = second_service.list_evidence_visible_as_of(first.canonical_event_id, T2)
    assert tuple(item.evidence_version_id for item in visible[-2:]) == tuple(sorted((second.evidence_version_id, tied.evidence_version_id)))
    assert second_service.latest_evidence_as_of(first.canonical_event_id, T2).evidence_version_id == max(second.evidence_version_id, tied.evidence_version_id)
    with pytest.raises(ValueError, match="timezone-aware"):
        second_service.list_evidence_visible_as_of(first.canonical_event_id, datetime(2026, 9, 1))
    repo.close()


@pytest.mark.parametrize("failure", ("event", "evidence", "request"))
def test_failure_injection_rolls_back_entire_application_composition(tmp_path, failure) -> None:
    class FailingRepository(SQLiteExternalIntelligenceRepository):
        def save_event(self, item):
            if failure == "event":
                raise RuntimeError("event persistence failed")
            return super().save_event(item)

        def save_evidence_version(self, item):
            if failure == "evidence":
                raise RuntimeError("evidence persistence failed")
            return super().save_evidence_version(item)

        def save_reevaluation_request(self, item):
            if failure == "request":
                raise RuntimeError("request persistence failed")
            return super().save_reevaluation_request(item)

    repo = FailingRepository(tmp_path / f"{failure}.sqlite")
    value = ExternalIntelligenceApplicationService(repo, clock=lambda: T1)
    with pytest.raises(RuntimeError, match="persistence failed"):
        value.record_event(command())
    assert repo.external_intelligence_row_counts() == {"events": 0, "evidence_versions": 0, "reevaluation_requests": 0}
    assert repo.foreign_key_violations() == ()
    repo.close()


def test_application_reopen_durability_and_read_operations(tmp_path) -> None:
    path = tmp_path / "durable.sqlite"
    repo = SQLiteExternalIntelligenceRepository(path)
    first_service = ExternalIntelligenceApplicationService(repo, clock=lambda: T1)
    first = first_service.record_event(command(summary="V1"))
    second = ExternalIntelligenceApplicationService(repo, clock=lambda: T2).record_event(command(summary="V2"))
    repo.close()

    reopened_repo = SQLiteExternalIntelligenceRepository(path)
    reopened = ExternalIntelligenceApplicationService(reopened_repo, clock=lambda: T2)
    assert reopened.get_event(first.canonical_event_id) is not None
    assert reopened.get_event_by_producer_identity("HSI_EXTERNAL_INTELLIGENCE_DESK", "test-rbi-1").canonical_event_id == first.canonical_event_id
    assert tuple(item.evidence_version_id for item in reopened.list_evidence_versions(first.canonical_event_id)) == (first.evidence_version_id, second.evidence_version_id)
    assert reopened.latest_evidence_as_of(first.canonical_event_id, T1).evidence_version_id == first.evidence_version_id
    assert tuple(item.request_id for item in reopened.list_reevaluation_requests(canonical_event_id=first.canonical_event_id)) == (first.reevaluation_request_id, second.reevaluation_request_id)
    reopened_repo.close()


def test_application_has_no_http_auth_news_brain_or_trading_side_effects(tmp_path) -> None:
    repo, value = service(tmp_path)
    before = {row[0] for row in repo._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    value.record_event(command())
    after = {row[0] for row in repo._connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert before == after
    assert "news_evidence" not in after and "paper_trades" not in after
    assert repo.audit_event_count() == 0
    repo.close()
