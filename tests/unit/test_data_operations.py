"""U17 deterministic operational orchestration and file-staging tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.data_operations.files import FileStagingLayout, NseDeliveryStagingJob
from app.data_operations.models import (
    DataOperationCadence,
    DataOperationsHealthStatus,
    EvidenceDataFamily,
    EvidenceRefreshFailureKind,
    EvidenceRefreshMode,
    EvidenceRefreshOutcome,
    EvidenceRefreshStatus,
    ReconciliationStatus,
)
from app.data_operations.service import DataOperationsScheduler, DataOperationsService, DataOperationsSettings, DataOperationsWorker, RetryPolicy
from app.data_operations.store import DataOperationsStore
from app.runtime.cli import _production_delivery_targets, main
from app.fundamentals.store import SQLiteFinancialFactStore
from app.intelligence.shared_brain_application import StoredSharedBrainEvidenceAssembler
from app.universe_analysis.models import NseEquityInstrument

import test_brain_research_comparison_state_v2 as financial_helpers
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 8, 29, 12, tzinfo=UTC)


class Job:
    def __init__(self, outcomes: list[EvidenceRefreshOutcome]) -> None:
        self.outcomes = outcomes
        self.requests = []

    def refresh(self, request):
        self.requests.append(request)
        return self.outcomes.pop(0)


class RaisingJob:
    def __init__(self, error: Exception) -> None:
        self.error = error
        self.calls = 0

    def refresh(self, request):
        self.calls += 1
        raise self.error


def complete(*, accepted: int = 1, duplicate: int = 0, through: datetime | None = T) -> EvidenceRefreshOutcome:
    return EvidenceRefreshOutcome(
        EvidenceRefreshStatus.COMPLETE if accepted else EvidenceRefreshStatus.NO_CHANGE,
        "OFFICIAL_TEST", accepted_count=accepted, duplicate_count=duplicate,
        accepted_through=through, verified_from_store=through is not None,
        source_fingerprint="source-test", source_references=("official:test",),
    )


def service(tmp_path: Path, jobs=None, *, retry=RetryPolicy(), clock=lambda: T) -> DataOperationsService:
    return DataOperationsService(DataOperationsStore(SQLiteCoreApiSnapshotRepository(tmp_path / "operations.sqlite")), jobs or {}, retry_policy=retry, clock=clock, run_id_factory=lambda: "fixture")


def test_backfill_then_incremental_uses_store_verified_append_only_watermark(tmp_path):
    job = Job([complete(accepted=2), complete(accepted=0, duplicate=2)])
    value = service(tmp_path, {EvidenceDataFamily.OHLCV: job})
    first = value.run(EvidenceDataFamily.OHLCV, mode=EvidenceRefreshMode.BACKFILL, run_id="run-1")
    second = value.run(EvidenceDataFamily.OHLCV, run_id="run-2")
    assert first.accepted_count == 2 and second.duplicate_count == 2
    assert job.requests[0].prior_watermark is None
    assert job.requests[1].prior_watermark is not None
    assert job.requests[1].prior_watermark.verified_from_store is True
    assert job.requests[1].overlap_sessions == 2


def test_identical_rerun_no_new_sessions_is_idempotent_and_run_receipt_is_durable(tmp_path):
    value = service(tmp_path, {EvidenceDataFamily.OHLCV: Job([complete(accepted=0, duplicate=3)])})
    result = value.run(EvidenceDataFamily.OHLCV, run_id="run-idempotent")
    assert result.status is EvidenceRefreshStatus.NO_CHANGE and result.accepted_count == 0 and result.duplicate_count == 3
    reopened = DataOperationsStore(SQLiteCoreApiSnapshotRepository(tmp_path / "operations.sqlite"))
    assert reopened.get_run("run-idempotent") == result


def test_conflict_and_gap_are_reported_not_silently_overwritten(tmp_path):
    outcome = EvidenceRefreshOutcome(
        EvidenceRefreshStatus.CONFLICT_FOUND, "OFFICIAL_TEST", conflict_count=1, gap_count=1,
        warnings=("PROVIDER_BAR_CONFLICT",),
        findings=((ReconciliationStatus.CONFLICT_FOUND, "NSE:ALPHA", "PROVIDER_BAR_CONFLICT"),),
    )
    value = service(tmp_path, {EvidenceDataFamily.OHLCV: Job([outcome])})
    result = value.run(EvidenceDataFamily.OHLCV, mode=EvidenceRefreshMode.RECONCILIATION, run_id="run-conflict")
    assert result.status is EvidenceRefreshStatus.CONFLICT_FOUND and result.conflict_count == result.gap_count == 1
    assert value._store.findings("run-conflict")[0].reason == "PROVIDER_BAR_CONFLICT"


def test_only_transient_failure_is_retried_and_validation_failure_is_not(tmp_path):
    transient = EvidenceRefreshOutcome(
        EvidenceRefreshStatus.FAILED, "OFFICIAL_TEST", failure_kind=EvidenceRefreshFailureKind.TRANSIENT,
        error_summary="SOURCE_TIMEOUT",
    )
    job = Job([transient, complete()])
    value = service(tmp_path, {EvidenceDataFamily.NEWS: job}, retry=RetryPolicy(maximum_attempts=2))
    result = value.run(EvidenceDataFamily.NEWS, run_id="run-retry")
    assert result.status is EvidenceRefreshStatus.COMPLETE and result.retry_count == 1 and len(job.requests) == 2
    invalid = EvidenceRefreshOutcome(
        EvidenceRefreshStatus.INVALID_EVIDENCE, "OFFICIAL_TEST", failure_kind=EvidenceRefreshFailureKind.VALIDATION,
        error_summary="SCHEMA_INVALID",
    )
    invalid_job = Job([invalid])
    failed = service(tmp_path / "second", {EvidenceDataFamily.NEWS: invalid_job}, retry=RetryPolicy(maximum_attempts=2)).run(EvidenceDataFamily.NEWS, run_id="run-invalid")
    assert failed.retry_count == 0 and len(invalid_job.requests) == 1
    raising = RaisingJob(ValueError("invalid local schema"))
    raised = service(tmp_path / "third", {EvidenceDataFamily.NEWS: raising}, retry=RetryPolicy(maximum_attempts=2)).run(EvidenceDataFamily.NEWS, run_id="run-raised-invalid")
    assert raised.status is EvidenceRefreshStatus.INVALID_EVIDENCE and raising.calls == 1


def test_same_family_overlap_is_rejected_without_executing_job(tmp_path):
    job = Job([complete()])
    value = service(tmp_path, {EvidenceDataFamily.DELIVERY: job})
    assert value._locks[EvidenceDataFamily.DELIVERY].acquire(blocking=False)
    try:
        result = value.run(EvidenceDataFamily.DELIVERY, run_id="run-overlap")
    finally:
        value._locks[EvidenceDataFamily.DELIVERY].release()
    assert result.error_summary == "RUN_ALREADY_ACTIVE" and job.requests == []


def test_clock_injected_scheduler_dispatches_only_due_registered_families(tmp_path):
    base = T
    job = Job([complete()])
    value = service(tmp_path, {EvidenceDataFamily.DELIVERY: job}, clock=lambda: base)
    scheduler = DataOperationsScheduler(value, clock=lambda: base)
    assert value.due_families(now=base) == (EvidenceDataFamily.DELIVERY,)
    assert len(scheduler.run_due()) == 1
    assert scheduler.run_due() == ()


def test_health_and_read_only_api_expose_never_run_and_failed_without_starting_work(tmp_path):
    value = service(tmp_path)
    health = value.health()
    assert {item.status for item in health.families} == {DataOperationsHealthStatus.NEVER_RUN}
    with TestClient(create_app(data_operations_service=value)) as client:
        response = client.get("/api/v1/data-operations/health")
        control = client.post("/api/v1/data-operations/run")
    assert response.status_code == 200 and len(response.json()["families"]) == len(EvidenceDataFamily)
    assert control.status_code == 404


class DeliveryImporter:
    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.calls = []

    def import_csv(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if self.failure:
            raise ValueError(self.failure)
        return SimpleNamespace(
            accepted=1, duplicates=0, rejected=0, unresolved=0,
            artifact=SimpleNamespace(trade_date=T, report_id="nse-delivery:test"),
        )


def _delivery_request():
    from app.data_operations.models import EvidenceRefreshRequest
    return EvidenceRefreshRequest("run-delivery", EvidenceDataFamily.DELIVERY, EvidenceRefreshMode.INCREMENTAL, T, T, None, 0)


def test_delivery_staging_validates_archives_and_quarantines_without_network(tmp_path):
    layout = FileStagingLayout(tmp_path)
    layout.ensure("delivery")
    accepted = layout.incoming("delivery") / "sec_bhavdata_full_29082026.csv"
    accepted.write_text("SYMBOL\nALPHA\n", encoding="utf-8")
    job = NseDeliveryStagingJob(DeliveryImporter(), {"ALPHA": ("NSE:ALPHA", "INE000A01001")}, layout, clock=lambda: T)
    complete_result = job.refresh(_delivery_request())
    assert complete_result.status is EvidenceRefreshStatus.COMPLETE
    assert list(layout.incoming("delivery").glob("*.csv")) == []
    assert len(list(layout.archive("delivery").glob("*.csv"))) == 1
    bad = layout.incoming("delivery") / "bad.csv"
    bad.write_text("not-a-delivery-file", encoding="utf-8")
    invalid_result = NseDeliveryStagingJob(DeliveryImporter(failure="NSE_DELIVERY_FILENAME_UNSUPPORTED"), {}, layout, clock=lambda: T).refresh(_delivery_request())
    assert invalid_result.status is EvidenceRefreshStatus.INVALID_EVIDENCE
    assert len(list(layout.quarantine("delivery").glob("*.csv"))) == 1


def test_worker_and_cli_manual_surface_are_opt_in_and_never_need_real_time(tmp_path):
    job = Job([complete()])
    value = service(tmp_path, {EvidenceDataFamily.DELIVERY: job})
    waits = []
    worker = DataOperationsWorker(
        DataOperationsScheduler(value, clock=lambda: T), DataOperationsSettings(enabled=True, poll_seconds=7),
        wait=lambda seconds: waits.append(seconds) or True,
    )
    assert worker.run_forever() is True and waits == [7] and len(job.requests) == 1
    messages = []
    assert main(["data-operations-status"], data_operations_factory=lambda: (value, ()), output=messages.append) == 0
    assert any("family=DELIVERY" in line for line in messages)
    assert main(["data-operations-run", "--family", "macro"], data_operations_factory=lambda: (value, ()), output=messages.append) == 2
    assert "status=SOURCE_UNAVAILABLE" in messages[-1]


def test_repeated_staged_delivery_file_is_archived_once_and_importer_reports_idempotency(tmp_path):
    layout = FileStagingLayout(tmp_path)
    layout.ensure("delivery")
    first = layout.incoming("delivery") / "sec_bhavdata_full_29082026.csv"
    first.write_text("same", encoding="utf-8")
    importer = DeliveryImporter()
    job = NseDeliveryStagingJob(importer, {}, layout, clock=lambda: T)
    assert job.refresh(_delivery_request()).status is EvidenceRefreshStatus.COMPLETE
    repeated = layout.incoming("delivery") / "sec_bhavdata_full_29082026.csv"
    repeated.write_text("same", encoding="utf-8")
    assert job.refresh(_delivery_request()).status is EvidenceRefreshStatus.COMPLETE
    assert len(importer.calls) == 2 and len(list(layout.archive("delivery").glob("*.csv"))) == 1


def test_incremental_financial_refresh_keeps_old_pit_view_and_exposes_new_evidence_to_shared_brain(tmp_path):
    facts = SQLiteFinancialFactStore(tmp_path / "facts.sqlite")
    old = financial_helpers._fact("old-quarter", as_of=T)
    facts.save(old)
    new_available_at = T + timedelta(days=1)
    new = replace(financial_helpers._fact("new-quarter", period_end=datetime(2026, 9, 30, tzinfo=UTC), as_of=new_available_at), published_at=new_available_at, received_at=new_available_at)

    class FinancialJob:
        def refresh(self, request):
            assert request.mode is EvidenceRefreshMode.INCREMENTAL
            facts.save(new)
            return EvidenceRefreshOutcome(
                EvidenceRefreshStatus.COMPLETE, "BSE_OFFICIAL", accepted_count=1,
                accepted_through=new_available_at, verified_from_store=True, source_references=("bse:new-quarter",),
            )

    instrument = NseEquityInstrument("NSE:ALPHA", "ALPHA", "INE000A01001", "DEMO", "SOFTWARE", "LISTED", None, True, T, "TEST", company_name="Alpha")
    assembler = StoredSharedBrainEvidenceAssembler(facts)
    before = assembler.assemble(instrument, as_of=T)
    operations = service(tmp_path / "operations", {EvidenceDataFamily.FINANCIAL_RESULTS: FinancialJob()}, clock=lambda: new_available_at)
    receipt = operations.run(EvidenceDataFamily.FINANCIAL_RESULTS, run_id="run-financial")
    historical = assembler.assemble(instrument, as_of=T)
    current = assembler.assemble(instrument, as_of=new_available_at)
    assert receipt.accepted_count == 1 and operations._store.latest_watermark(EvidenceDataFamily.FINANCIAL_RESULTS) is not None
    assert len(before.financial_bundle.observations) == len(historical.financial_bundle.observations) == 1
    assert len(current.financial_bundle.observations) == 2


def test_operations_source_has_no_provider_or_action_semantics():
    source = (Path(__file__).parents[2] / "app" / "data_operations" / "service.py").read_text(encoding="utf-8").lower()
    assert not any(token in source for token in ("requests", "urllib", "buy", "sell", "paper_trade", "place_order", "activation", "promotion"))


def test_production_delivery_targets_use_the_authoritative_universe_not_top3_only():
    values = (
        SimpleNamespace(instrument_id="NSE:ALPHA", symbol="ALPHA", isin="INE000A01001"),
        SimpleNamespace(instrument_id="NSE:BETA", symbol="BETA", isin="INE000B01001"),
        SimpleNamespace(instrument_id="NSE:OUTSIDE", symbol="OUTSIDE", isin="INE000C01001"),
        SimpleNamespace(instrument_id="NSE:GAMMA", symbol="COLLIDE", isin="INE000D01001"),
        SimpleNamespace(instrument_id="NSE:DELTA", symbol="COLLIDE", isin="INE000E01001"),
    )
    targets = _production_delivery_targets(("NSE:ALPHA", "NSE:BETA", "NSE:GAMMA", "NSE:DELTA"), values)
    assert targets == {"ALPHA": ("NSE:ALPHA", "INE000A01001"), "BETA": ("NSE:BETA", "INE000B01001")}
