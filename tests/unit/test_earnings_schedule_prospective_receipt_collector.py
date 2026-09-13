"""Prospective-only official schedule collection; all network input is synthetic."""
from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from app.filings.earnings_schedule_coverage import (
    EarningsScheduleAbsenceState,
    EarningsScheduleCoverageReceipt,
)
from app.filings.earnings_schedule_discovery import BSE_CORPORATES
from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge
from app.filings.earnings_schedule_prospective_receipt_collector import (
    ProspectiveCollectionRunReceipt,
    ProspectiveEarningsScheduleReceiptCollector,
    ProspectiveEarningsScheduleReceiptStore,
    ProspectivePollState,
    ProspectiveQualifiedScheduleReceipt,
    ProspectiveRawArtifactReceipt,
    ProspectiveReceiptCollectorError,
    ProspectiveSourceObservation,
    make_raw_artifact_receipt,
)
from app.filings.earnings_schedule_source import Fetch, NSE_RSS
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord, ProviderMappingStatus


T = datetime(2026, 9, 12, 10, tzinfo=UTC)
INSTRUMENT = "NSE:INE372A01015"
ISIN = "INE372A01015"
NEWS_ID = "15bec8ef-4d88-44f6-bccc-4b0d111db3b3"
BSE_URL = f"https://m.bseindia.com/MAnnDet.aspx?Form=STR&newsid={NEWS_ID}&scrpcd=532259"

RSS_EMPTY = b"<rss><channel><title>NSE News - Board Meetings</title></channel></rss>"
NSE_DETAIL_URL = "https://nsearchives.nseindia.com/corporate/xbrl/PRIOR_INTIMATION_123_WebXMLFile_20260912.xml"
RSS_WITH_LINK = (
    "<rss><channel><title>NSE News - Board Meetings</title><item>"
    "<title>Synthetic issuer</title><link>" + NSE_DETAIL_URL + "</link>"
    "<description>Financial Results |Meeting Date: 16-Oct-2026</description>"
    "<pubDate>12-Sep-2026 10:00:00</pubDate></item>"
    "</channel></rss>"
).encode()
DISCOVERY = (
    "<html><a href='MAnnDet.aspx?Form=STR&newsid=" + NEWS_ID + "&scrpcd=532259'>"
    "Board meeting announcement</a></html>"
).encode()


def _detail(*, day: str = "16/10/2026", purpose: str = "to consider and approve quarterly financial results") -> bytes:
    return (
        "<table>"
        "<tr><td class='resultgreyhead'>Security Code</td><td class='resultleft'>532259</td></tr>"
        "<tr><td class='resultgreyhead'>Company</td><td class='resultleft'>Synthetic issuer</td></tr>"
        "<tr><td class='resultgreyhead'>Exchange Received Time</td><td class='resultleft'>12/09/2026 10:00:00</td></tr>"
        "<tr><td class='resultgreyhead'>Exchange Disseminated Time</td><td class='resultleft'>12/09/2026 10:00:00</td></tr>"
        "</table><table>"
        "<tr><td class='ann01'>Board Meeting Intimation for Financial Results | display date</td></tr>"
        f"<tr><td class='ann02'>Synthetic issuer has informed BSE that the meeting is scheduled on {day} ,inter alia, {purpose}</td></tr>"
        "</table>"
    ).encode()


def _nse_detail(*, intimation_type: str = "New") -> bytes:
    fields = {
        "NSESymbol": "APARINDS", "ISIN": ISIN, "NameOfTheCompany": "Synthetic issuer",
        "TypeOfMeeting": "Board Meeting", "TypeOfIntimation": intimation_type,
        "DateOfProposedMeeting": "2026-10-16", "Agenda1": "Financial Results",
    }
    return (
        '<xbrl xmlns="http://www.xbrl.org/2003/instance" '
        'xmlns:p="https://www.sebi.gov.in/xbrl/2023-05-31/in-capmkt">'
        + "".join(f"<p:{key}>{value}</p:{key}>" for key, value in fields.items()) + "</xbrl>"
    ).encode()


class Clock:
    def __init__(self, start: datetime):
        self.value = start

    def now(self) -> datetime:
        value = self.value
        self.value += timedelta(seconds=1)
        return value


class Transport:
    def __init__(self, *, detail: bytes = _detail(), rss: bytes = RSS_EMPTY,
                 nse_detail: bytes = _nse_detail(), bse_error: Exception | None = None):
        self.detail, self.rss, self.nse_detail, self.bse_error, self.calls = detail, rss, nse_detail, bse_error, []

    def get(self, url: str) -> Fetch:
        self.calls.append(url)
        if url == NSE_RSS:
            return Fetch(url, 200, self.rss)
        if url == NSE_DETAIL_URL:
            return Fetch(url, 200, self.nse_detail)
        if url == BSE_CORPORATES:
            if self.bse_error is not None:
                raise self.bse_error
            return Fetch(url, 200, DISCOVERY)
        if url == BSE_URL:
            return Fetch(url, 200, self.detail)
        raise AssertionError(url)


def _master() -> NseEquityInstrument:
    return NseEquityInstrument(
        instrument_id=INSTRUMENT, symbol="APARINDS", isin=ISIN, sector=None, industry=None,
        listing_status="UNKNOWN", listing_date=None, tradable=None,
        data_as_of=T - timedelta(days=1), source="NSE_OFFICIAL_EXPORT",
    )


def _mapping() -> ProviderInstrumentMappingRecord:
    effective = T - timedelta(days=1)
    body = dict(
        canonical_instrument_id=INSTRUMENT, provider="BSE_OFFICIAL", provider_exchange_segment="BSE_EQ",
        provider_instrument_reference="532259", provider_symbol=None, isin=ISIN,
        status=ProviderMappingStatus.ACTIVE, effective_as_of=effective,
        source_reference="https://www.bseindia.com/XBRLFILES/synthetic.xml", source_checksum="a" * 64,
        mapping_version="bse-xbrl-v1",
    )
    key = sha256("|".join((body["provider"], body["canonical_instrument_id"], body["provider_exchange_segment"],
                             body["provider_instrument_reference"], body["mapping_version"],
                             body["effective_as_of"].isoformat(), body["source_checksum"])).encode()).hexdigest()[:24]
    return ProviderInstrumentMappingRecord(mapping_id="mapping:bse_official:" + key, **body)


def _snapshot(payload):
    if isinstance(payload, NseEquityInstrument):
        family, identity, at = CoreApiSnapshotFamily.NSE_UNIVERSE, f"nse-equity:{payload.instrument_id}:{payload.data_as_of.isoformat()}", payload.data_as_of
    else:
        family, identity, at = CoreApiSnapshotFamily.PROVIDER_INSTRUMENT_MAPPING, f"provider-mapping:{payload.mapping_id}", payload.effective_as_of
    return CoreApiSnapshot(identity, family, "v1", "universe-analysis-v1", sha256(repr(payload).encode()).hexdigest(), at, payload)


def _bridge() -> EarningsScheduleCanonicalIdentityBridge:
    return EarningsScheduleCanonicalIdentityBridge((_snapshot(_master()), _snapshot(_mapping())))


def _run(repo, *, clock: Clock, transport: Transport, targets: tuple[str, ...] = (INSTRUMENT,)):
    return ProspectiveEarningsScheduleReceiptCollector(
        store=ProspectiveEarningsScheduleReceiptStore(repo), identity_bridge=_bridge(),
        transport=transport, clock=clock,
    ).collect_once(target_instrument_ids=targets)


def _stored(repo, kind):
    return tuple(item for item in ProspectiveEarningsScheduleReceiptStore(repo).values() if isinstance(item, kind))


def test_bounded_dual_source_collection_retains_raw_bytes_positive_evidence_and_partial_coverage(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "collector.sqlite")
    transport = Transport()
    result = _run(repo, clock=Clock(T), transport=transport)

    assert result.live_positive_event_proof == "PROVEN"
    assert len(result.positive_receipts) == 1
    positive = result.positive_receipts[0]
    assert positive.canonical_instrument_id == INSTRUMENT
    assert positive.system_first_observed.observed_at < positive.processed_at
    assert positive.source_timestamp_authority.value == "UNPROVEN"
    assert positive.actionability == "WATCH_ONLY" and positive.execution_status == "NON_EXECUTABLE"
    assert positive.gate6_clearance is False
    artifacts = _stored(repo, ProspectiveRawArtifactReceipt)
    assert any(item.raw_payload == _detail() for item in artifacts)
    assert all(item.payload_fingerprint.startswith("sha256:") for item in artifacts)
    observations = _stored(repo, ProspectiveSourceObservation)
    assert any(item.source_reference if False else item.source.field("filing_identity") == NEWS_ID for item in observations)
    coverage = _stored(repo, EarningsScheduleCoverageReceipt)
    assert len(coverage) == 2
    assert {item.absence_state for item in coverage} == {
        EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW,
        EarningsScheduleAbsenceState.QUALIFYING_EVENT_FOUND,
    }
    assert all(item.gate6_clearance is False for item in coverage)
    assert all(item.filter_semantics.value == "SOURCE_SCOPE_UNPROVEN" for item in coverage)
    polls = _stored(repo, __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveSourcePollReceipt"]).ProspectiveSourcePollReceipt)
    assert len(polls) == 3 and all(item.state is ProspectivePollState.PARTIAL for item in polls)
    assert BSE_URL in transport.calls
    assert any(item.source_endpoint == BSE_URL for item in polls)


def test_exact_nse_rss_to_linked_detail_preserves_discovery_before_qualification(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "nse-linked.sqlite")
    result = _run(repo, clock=Clock(T), transport=Transport(rss=RSS_WITH_LINK))
    nse = next(item for item in result.positive_receipts if item.source_family.value == "NSE_BOARD_MEETINGS")
    observations = _stored(repo, ProspectiveSourceObservation)
    detail = next(item for item in observations if item.source.reference == NSE_DETAIL_URL)
    discovery = next(item for item in observations if item.source.reference == NSE_RSS)
    assert detail.discovery_observation_id == discovery.observation_id
    assert detail.first_observed_at > discovery.first_observed_at
    assert nse.source_observation_id == detail.observation_id
    assert nse.system_first_observed.observed_at == detail.first_observed_at


def test_unresolved_and_nonqualifying_rows_create_explicit_assessments_not_silent_drops(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "assessment.sqlite")
    _run(repo, clock=Clock(T), transport=Transport(detail=_detail(purpose="general corporate matters")))
    module = __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveScheduleAssessmentReceipt"])
    assessments = _stored(repo, module.ProspectiveScheduleAssessmentReceipt)
    assert len(assessments) == 1
    assert assessments[0].state.value == "PURPOSE_AMBIGUOUS"
    assert assessments[0].qualified_receipt_id is None
    assert assessments[0].gate6_clearance is False


def test_restart_replay_preserves_original_first_observed_and_creates_no_duplicate_positive(tmp_path):
    path = tmp_path / "restart.sqlite"
    first_repo = SQLiteCoreApiSnapshotRepository(path)
    first = _run(first_repo, clock=Clock(T), transport=Transport())
    first_observed = first.positive_receipts[0].system_first_observed.observed_at
    first_repo.close()

    reopened = SQLiteCoreApiSnapshotRepository(path)
    second = _run(reopened, clock=Clock(T + timedelta(days=1)), transport=Transport())
    events = _stored(reopened, ProspectiveQualifiedScheduleReceipt)
    assert len(events) == 1 and second.positive_receipts[0].system_first_observed.observed_at == first_observed
    assert second.run_receipt.already_present > 0
    reopened.close()


def test_materially_changed_same_source_record_creates_immutable_revision_with_parent(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "revision.sqlite")
    first = _run(repo, clock=Clock(T), transport=Transport())
    second = _run(repo, clock=Clock(T + timedelta(days=1)), transport=Transport(detail=_detail(day="17/10/2026")))
    events = _stored(repo, ProspectiveQualifiedScheduleReceipt)
    assert len(events) == 2
    revised = next(item for item in events if item.receipt_id != first.positive_receipts[0].receipt_id)
    assert revised.lifecycle_state.value == "REVISED"
    assert revised.revision_of_receipt_id == first.positive_receipts[0].receipt_id
    assert revised.system_first_observed.observed_at > first.positive_receipts[0].system_first_observed.observed_at
    assert second.live_positive_event_proof == "PROVEN"


def test_explicit_reschedule_requires_and_links_exact_persisted_parent_receipt(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "reschedule.sqlite")
    first = _run(repo, clock=Clock(T), transport=Transport(rss=RSS_WITH_LINK))
    original = next(item for item in first.positive_receipts if item.source_family.value == "NSE_BOARD_MEETINGS")
    second = _run(
        repo,
        clock=Clock(T + timedelta(days=1)),
        transport=Transport(rss=RSS_WITH_LINK, nse_detail=_nse_detail(intimation_type="Rescheduled")),
    )
    receipt = next(
        item for item in second.positive_receipts
        if item.source_family.value == "NSE_BOARD_MEETINGS" and item.receipt_id != original.receipt_id
    )
    assert receipt.lifecycle_state.value == "RESCHEDULED"
    assert receipt.revision_of_receipt_id == original.receipt_id


def test_explicit_cancellation_without_exact_prior_is_retained_but_not_qualified(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "cancel-without-parent.sqlite")
    result = _run(
        repo,
        clock=Clock(T),
        transport=Transport(rss=RSS_WITH_LINK, nse_detail=_nse_detail(intimation_type="Cancelled")),
    )
    assert all(item.source_family.value != "NSE_BOARD_MEETINGS" for item in result.positive_receipts)
    module = __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveScheduleAssessmentReceipt"])
    assessment = next(
        item for item in _stored(repo, module.ProspectiveScheduleAssessmentReceipt)
        if item.source_observation_id in {
            observation.observation_id for observation in _stored(repo, ProspectiveSourceObservation)
            if observation.source.reference == NSE_DETAIL_URL
        }
    )
    assert assessment.state.value == "REVISION_LINEAGE_UNRESOLVED"
    assert assessment.reason_codes == ("EXACT_PARENT_RECEIPT_REQUIRED",)


def test_terminal_cancellation_cannot_be_reopened_by_later_changed_source_bytes(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "cancel-terminal.sqlite")
    _run(repo, clock=Clock(T), transport=Transport(rss=RSS_WITH_LINK))
    cancelled = _run(
        repo,
        clock=Clock(T + timedelta(days=1)),
        transport=Transport(rss=RSS_WITH_LINK, nse_detail=_nse_detail(intimation_type="Cancelled")),
    )
    assert any(item.lifecycle_state.value == "CANCELLED" for item in cancelled.positive_receipts)
    reopened = _run(
        repo,
        clock=Clock(T + timedelta(days=2)),
        transport=Transport(rss=RSS_WITH_LINK, nse_detail=_nse_detail(intimation_type="Revised")),
    )
    assert all(item.source_family.value != "NSE_BOARD_MEETINGS" for item in reopened.positive_receipts)
    module = __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveScheduleAssessmentReceipt"])
    assert any(
        item.state.value == "REVISION_LINEAGE_UNRESOLVED"
        and item.reason_codes == ("REVISION_PARENT_TERMINAL",)
        for item in _stored(repo, module.ProspectiveScheduleAssessmentReceipt)
    )


def test_source_failure_and_zero_nse_rows_emit_evidence_only_without_clearance(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "failed.sqlite")
    result = _run(repo, clock=Clock(T), transport=Transport(bse_error=OSError("network")))
    assert not result.positive_receipts and result.live_positive_event_proof == "PENDING_EVENT"
    coverage = _stored(repo, EarningsScheduleCoverageReceipt)
    assert len(coverage) == 2
    assert all(item.gate6_clearance is False for item in coverage)
    assert any(item.absence_state is EarningsScheduleAbsenceState.SOURCE_QUERY_FAILED for item in coverage)
    assert any(item.absence_state is EarningsScheduleAbsenceState.NO_QUALIFYING_EVENT_FOUND_INCOMPLETE_WINDOW for item in coverage)
    polls = _stored(repo, __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveSourcePollReceipt"]).ProspectiveSourcePollReceipt)
    assert any(item.state is ProspectivePollState.FAILED for item in polls)


def test_exact_identity_failure_and_purpose_ambiguity_do_not_become_positive_receipts(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "unresolved.sqlite")
    result = _run(repo, clock=Clock(T), transport=Transport(detail=_detail(purpose="general corporate matters")))
    assert result.live_positive_event_proof == "PENDING_EVENT"
    assert not _stored(repo, ProspectiveQualifiedScheduleReceipt)
    assert _stored(repo, ProspectiveSourceObservation)


def test_global_discovery_detail_outside_exact_target_cohort_is_retained_but_not_admitted(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "outside-cohort.sqlite")
    result = _run(
        repo,
        clock=Clock(T),
        transport=Transport(),
        targets=("NSE:INE090A01021",),
    )
    assert not result.positive_receipts
    module = __import__("app.filings.earnings_schedule_prospective_receipt_collector", fromlist=["ProspectiveScheduleAssessmentReceipt"])
    assessment = next(item for item in _stored(repo, module.ProspectiveScheduleAssessmentReceipt))
    assert assessment.state.value == "OUTSIDE_TARGET_COHORT"
    assert assessment.reason_codes == ("OUTSIDE_EXACT_TARGET_COHORT",)


def test_raw_and_lineage_tampering_is_rejected_and_serialization_reopens(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "tamper.sqlite")
    result = _run(repo, clock=Clock(T), transport=Transport())
    artifact = _stored(repo, ProspectiveRawArtifactReceipt)[0]
    with pytest.raises(ProspectiveReceiptCollectorError, match="RAW_ARTIFACT_INVALID"):
        replace(artifact, raw_payload_base64="dGFtcGVy")
    event = result.positive_receipts[0]
    with pytest.raises(ProspectiveReceiptCollectorError, match="QUALIFIED_RECEIPT_INVALID"):
        replace(event, canonical_instrument_id="NSE:INE090A01021")
    expected = tuple(_stored(repo, ProspectiveQualifiedScheduleReceipt))
    repo.close()
    reopened = SQLiteCoreApiSnapshotRepository(tmp_path / "tamper.sqlite")
    assert _stored(reopened, ProspectiveQualifiedScheduleReceipt) == expected
    reopened.close()


def test_clock_and_target_boundary_are_injected_and_caller_cannot_supply_historical_first_observed(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "clock.sqlite")
    collector = ProspectiveEarningsScheduleReceiptCollector(
        store=ProspectiveEarningsScheduleReceiptStore(repo), identity_bridge=_bridge(),
        transport=Transport(), clock=Clock(T),
    )
    with pytest.raises(TypeError):
        collector.collect_once(target_instrument_ids=(INSTRUMENT,), first_observed_at=T - timedelta(days=1))
    with pytest.raises(ProspectiveReceiptCollectorError, match="EXACT_TARGETS_REQUIRED"):
        collector.collect_once(target_instrument_ids=(INSTRUMENT, INSTRUMENT))


def test_contract_has_no_execution_or_forbidden_runtime_dependencies():
    path = Path("app/filings/earnings_schedule_prospective_receipt_collector.py")
    source = path.read_text(encoding="utf-8")
    imports = [item.module for item in ast.walk(ast.parse(source)) if isinstance(item, ast.ImportFrom)]
    forbidden = ("app.api", "app.portfolio", "app.rotation", "app.orders", "app.broker", "app.runtime", "app.signals", "app.gates.engine")
    assert not any(item and item.startswith(forbidden) for item in imports)
    assert "datetime.now" not in source.replace("return datetime.now(UTC)", "")
    for value in _stored(SQLiteCoreApiSnapshotRepository(), ProspectiveCollectionRunReceipt):
        assert value.gate6_clearance is False
    fields = set(ProspectiveQualifiedScheduleReceipt.__dataclass_fields__)
    assert not fields & {"entry_price", "stop_loss", "target_price", "quantity", "allocation", "portfolio", "order"}
