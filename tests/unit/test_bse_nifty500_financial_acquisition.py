from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.filings.store import FilingWriteOutcome, SQLiteCorporateFilingsStore
from app.fundamentals.bse_collector import (
    BseCollectorError, BseMappingStatus, BseSecurityMapping, BseStageDisposition, BseStagedXbrl,
)
from app.fundamentals.bse_nifty500_acquisition import (
    BseAcquisitionUnitState, BseArchiveDiscoveryState, BseFinancialAcquisitionSettings, BseFinancialAcquisitionStore,
    BseNifty500FinancialAcquisitionOrchestrator, BseNifty500MappingState,
)
from app.fundamentals.bse_official import (
    BseResultMetadata, BseTimestampStatus, BseLocalIngestionReport,
)
from app.fundamentals.models import FinancialPeriodType, FinancialValueBasis, StatementScope
from app.fundamentals.store import SQLiteFinancialFactStore
from app.runtime.cli import parser
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument


T = datetime(2026, 9, 1, tzinfo=UTC)


def _instrument(letter: str) -> NseEquityInstrument:
    return NseEquityInstrument(
        f"NSE:INE0000000{letter:02d}", f"SYM{letter}", f"INE0000000{letter:02d}",
        None, None, "ACTIVE", None, True, T, "fixture",
    )


def _metadata(number: int) -> BseResultMetadata:
    return BseResultMetadata(
        "123456", "2025-26", f"Q{number}", "Quarter", "Original", T, None, None,
        StatementScope.STANDALONE, T, FinancialPeriodType.QUARTERLY,
        FinancialValueBasis.QUARTER_ONLY,
        f"https://www.bseindia.com/XBRLFILES/FinancialResults/{number}.xml",
        "https://api.bseindia.com/BseIndiaAPI/api/Result_Arch_Download/w?scrip_cd=123456",
        BseTimestampStatus.DOCUMENTED,
    )


class _Universe:
    def __init__(self, values): self.values = tuple(values)
    def instruments_as_of(self, _as_of): return self.values


class _Memberships:
    def __init__(self, values):
        self.values = tuple(
            SimpleNamespace(instrument_id=item.instrument_id, known_at=T, effective_from=T, effective_to=None)
            for item in values
        )
    def memberships(self, universe_id):
        assert universe_id == "NIFTY_500"
        return self.values


class _Master:
    def __init__(self, states): self.states, self.calls = states, 0
    def begin_run(self): pass
    def resolve(self, *, canonical_instrument_id, isin):
        self.calls += 1
        state = self.states[canonical_instrument_id]
        return BseSecurityMapping(canonical_instrument_id, isin, state, "123456" if state is BseMappingStatus.EXACT else None,
                                  "ID" if state is BseMappingStatus.EXACT else None, "Issuer" if state is BseMappingStatus.EXACT else None,
                                  "https://api.bseindia.com/BseIndiaAPI/api/PeerSmartSearch/w", T, f"sha256:{canonical_instrument_id}",
                                  None if state is BseMappingStatus.EXACT else "BSE_ISIN_NOT_FOUND")


class _UnavailableMaster(_Master):
    def resolve(self, *, canonical_instrument_id, isin):
        self.calls += 1
        raise BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE")


class _Provider:
    def __init__(self, values): self.values, self.calls = tuple(values), 0
    def result_metadata_aliases(self, _code):
        self.calls += 1
        return tuple(type("Aliases", (), {"preferred": value}) for value in self.values)


class _SequencedProvider:
    def __init__(self, outcomes): self.outcomes, self.calls = list(outcomes), 0
    def result_metadata_aliases(self, _code):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return tuple(type("Aliases", (), {"preferred": value}) for value in outcome)


class _Transport:
    def __init__(self, error=None): self.error, self.calls = error, 0
    def fetch_xbrl(self, _url):
        self.calls += 1
        if self.error: raise self.error
        return object()


class _Staging:
    def __init__(self): self.calls = 0
    def stage(self, *, mapping, metadata, response):
        self.calls += 1
        return BseStagedXbrl(Path("staged.xml"), Path("staged.json"), BseStageDisposition.NEW, "a" * 64, 1, metadata.xbrl_url, T, T)


class _Importer:
    def __init__(self): self.calls = 0
    def ingest_official_staged(self, identity, security_code, path, *, metadata):
        self.calls += 1
        return BseLocalIngestionReport(identity.instrument_id, security_code, "staged.xml", True, FilingWriteOutcome.INSERTED, 2, 0, 0, T, None, ())


def _service(*, states=(BseMappingStatus.EXACT,), metadata=(_metadata(1),), error=None):
    instruments = tuple(_instrument(index + 1) for index in range(len(states)))
    master = _Master({item.instrument_id: state for item, state in zip(instruments, states, strict=True)})
    provider, transport, staging = _Provider(metadata), _Transport(error), _Staging()
    repository = SQLiteCoreApiSnapshotRepository()
    service = BseNifty500FinancialAcquisitionOrchestrator(
        repository=BseFinancialAcquisitionStore(repository), universe=_Universe(instruments),
        memberships=_Memberships(instruments),
        filings=SQLiteCorporateFilingsStore(), facts=SQLiteFinancialFactStore(), security_master=master,
        provider=provider, transport=transport, staging=staging, clock=lambda: T, sleeper=lambda _seconds: None,
        expected_universe_size=len(instruments),
    )
    importer = _Importer(); service._importer = importer
    return service, master, provider, transport, staging, importer


def test_exact_mapping_inventory_is_immutable_and_deterministic():
    service, master, *_ = _service(states=(BseMappingStatus.EXACT, BseMappingStatus.NOT_FOUND, BseMappingStatus.AMBIGUOUS, BseMappingStatus.BLOCKED))
    first = service.mapping_audit(as_of=T)
    second = service.mapping_audit(as_of=T)
    assert first == second
    assert [item.state for item in first.mappings] == [
        BseNifty500MappingState.EXACT_VERIFIED, BseNifty500MappingState.UNMAPPED,
        BseNifty500MappingState.CONFLICT, BseNifty500MappingState.UNSUPPORTED,
    ]
    assert master.calls == 4


def test_dry_run_discovers_plan_without_xbrl_acquisition_or_canonical_writes():
    service, _, provider, transport, staging, importer = _service(metadata=(_metadata(1), _metadata(2)))
    inventory, plan = service.dry_run(as_of=T)
    assert len(inventory.mappings) == 1 and len(plan.units) == 2
    assert provider.calls == 1 and transport.calls == staging.calls == importer.calls == 0
    assert plan.policy_version == "bse-financial-acquisition-plan/v1"


def test_mapping_checkpoint_resumes_completed_entries_and_halts_provider_outage():
    service, master, *_ = _service(states=(BseMappingStatus.EXACT, BseMappingStatus.EXACT))
    service.mapping_audit(as_of=T, max_instruments=1)
    service.mapping_audit(as_of=T)
    assert master.calls == 2
    service._security_master = _UnavailableMaster({})
    with pytest.raises(BseCollectorError, match="BSE_OFFICIAL_MAPPING_PROVIDER_HALTED"):
        service.mapping_audit(as_of=datetime(2026, 9, 2, tzinfo=UTC), settings=BseFinancialAcquisitionSettings(global_halt_after_unavailable=2))


def test_archive_discovery_checkpoint_is_immutable_deterministic_and_completed_work_is_skipped():
    service, *_ = _service()
    inventory = service.mapping_audit(as_of=T)
    first = service.discover_archives(inventory)
    second = service.discover_archives(inventory)
    assert first.discovered == 1 and second.discovered == 1
    assert first.checkpoints == second.checkpoints
    assert first.checkpoints[0].state is BseArchiveDiscoveryState.DISCOVERED
    assert first.checkpoints[0].fingerprint.startswith("sha256:")
    assert service._provider.calls == 1


def test_archive_discovery_resume_continues_after_bounded_interruption_without_rediscovery():
    service, *_ = _service(states=(BseMappingStatus.EXACT,) * 3)
    inventory = service.mapping_audit(as_of=T)
    first = service.discover_archives(inventory, max_instruments=1)
    second = service.discover_archives(inventory)
    assert first.discovered == 1 and first.remaining_unresolved == 2
    assert second.discovered == 3 and second.remaining_unresolved == 0
    assert service._provider.calls == 3


def test_archive_discovery_no_archive_is_terminal_auditable_and_plan_has_no_units():
    service, *_ = _service()
    service._provider = _SequencedProvider([()])
    inventory = service.mapping_audit(as_of=T)
    plan = service.build_plan(inventory)
    report = service.discovery_status(inventory)
    assert report.no_archive_available == 1 and report.remaining_unresolved == 0
    assert report.checkpoints[0].state is BseArchiveDiscoveryState.NO_ARCHIVE_AVAILABLE
    assert plan.units == ()


def test_archive_discovery_retries_transient_failure_then_resumes_after_recovery():
    service, *_ = _service()
    service._provider = _SequencedProvider([
        BseCollectorError("BSE_TRANSIENT_FAILURE"), (_metadata(1),),
    ])
    inventory = service.mapping_audit(as_of=T)
    first = service.discover_archives(inventory)
    second = service.discover_archives(inventory)
    assert first.retryable_failures == 1 and first.remaining_unresolved == 1
    assert second.discovered == 1 and second.remaining_unresolved == 0
    assert service._provider.calls == 2


def test_archive_discovery_terminal_failure_is_not_retried():
    service, *_ = _service()
    service._provider = _SequencedProvider([BseCollectorError("BSE_OFFICIAL_RESPONSE_TOO_LARGE")])
    inventory = service.mapping_audit(as_of=T)
    first = service.discover_archives(inventory)
    second = service.discover_archives(inventory)
    assert first.terminal_failures == 1 and second.terminal_failures == 1
    assert service._provider.calls == 1


def test_provider_halt_is_durable_stops_further_requests_and_recovery_can_resume():
    service, *_ = _service(states=(BseMappingStatus.EXACT,) * 3)
    service._provider = _SequencedProvider([
        BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE"),
        BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE"),
    ])
    inventory = service.mapping_audit(as_of=T)
    halted = service.discover_archives(inventory, settings=BseFinancialAcquisitionSettings(global_halt_after_unavailable=2))
    assert halted.provider_halted is True and service._provider.calls == 2
    assert halted.latest_halt_receipt is not None
    assert halted.latest_halt_receipt.resume_state == "RESUME_ELIGIBLE"
    service._provider = _SequencedProvider([(_metadata(1),), (_metadata(1),), (_metadata(1),)])
    recovered = service.discover_archives(inventory, settings=BseFinancialAcquisitionSettings(global_halt_after_unavailable=2))
    assert recovered.provider_halted is False and recovered.discovered == 3


def test_execute_persists_checkpoint_and_second_run_is_idempotent():
    service, *_rest, transport, staging, importer = _service()
    _, plan = service.dry_run(as_of=T)
    first = service.execute(plan)
    second = service.execute(plan)
    assert first.accepted == 1 and second.accepted == 1
    assert transport.calls == staging.calls == importer.calls == 1
    assert second.receipts[0].state is BseAcquisitionUnitState.ACCEPTED


def test_retry_cap_and_global_provider_halt_are_bounded():
    service, *_prefix, transport, _staging, _importer = _service(metadata=(_metadata(1), _metadata(2)), error=BseCollectorError("BSE_OFFICIAL_SOURCE_UNAVAILABLE"))
    _, plan = service.dry_run(as_of=T)
    report = service.execute(plan, settings=BseFinancialAcquisitionSettings(maximum_retries=1, global_halt_after_unavailable=2))
    assert report.provider_halted is True and report.unavailable == 2
    assert transport.calls == 2


def test_retry_cap_is_enforced_for_a_transient_unknown_failure():
    service, *_prefix, transport, _staging, _importer = _service(error=BseCollectorError("BSE_TRANSIENT_FAILURE"))
    _, plan = service.dry_run(as_of=T)
    report = service.execute(plan, settings=BseFinancialAcquisitionSettings(maximum_retries=1))
    assert report.retryable_failure == 1 and transport.calls == 2


def test_failure_isolated_and_safe_error_never_contains_provider_url():
    service, *_prefix, transport, _staging, _importer = _service(error=BseCollectorError("BSE_XBRL_CANONICAL_IDENTITY_MISMATCH"))
    _, plan = service.dry_run(as_of=T)
    report = service.execute(plan, settings=BseFinancialAcquisitionSettings(maximum_retries=0))
    assert report.quarantined == 1
    assert "https://" not in report.receipts[0].detail
    assert transport.calls == 1


def test_cli_exposes_only_explicit_operator_controls():
    arguments = parser().parse_args(["bse-nifty500-financials", "dry-run", "--max-instruments", "5"])
    assert arguments.operation == "dry-run" and arguments.max_instruments == 5
