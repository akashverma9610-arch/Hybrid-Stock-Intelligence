"""One-shot, bounded snapshot composition. Only the new shadow family is written.

Canonical market/result inputs can be supplied by existing readers. No provider
is contacted here; absent inputs remain explicit pending/partial states.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.models import AsOfSnapshot
from app.filings.earnings_horizon_prospective_shadow import (
    EarningsHorizonShadowError, QualifiedShadowInput, ShadowDailyInput,
    ShadowEvent, ShadowRecord, ShadowReference, ShadowResultEvidence,
    ShadowSessionObservation, ShadowState, ResultLinkState, _record, utc, reference,
    reconcile_events, observe_session, link_result, attach_outcome,
)
from app.filings.earnings_schedule_identity import EarningsScheduleCanonicalIdentityBridge
from app.filings.earnings_schedule_coverage import EarningsScheduleCoverageReceipt
from app.filings.earnings_schedule_prospective_receipt_collector import (
    ProspectiveQualifiedScheduleReceipt, ProspectiveSourceObservation,
    ProspectiveRawArtifactReceipt, ProspectiveSourcePollReceipt, ProspectivePollState,
    ProspectiveScheduleAssessmentReceipt, ProspectiveObservationState,
)
from app.historical.canonical_market_session_event_time import CanonicalMarketSessionCalendar
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


FAMILY = CoreApiSnapshotFamily.EARNINGS_HORIZON_PROSPECTIVE_SHADOW
COLLECTOR_FAMILY = CoreApiSnapshotFamily.EARNINGS_SCHEDULE_PROSPECTIVE_RECEIPT


@dataclass(frozen=True, slots=True)
class SessionRequest:
    """Exact canonical evidence supplied by a caller; no hypothetical entry."""
    daily: ShadowDailyInput
    as_of: datetime
    history: tuple[ShadowDailyInput, ...] = ()
    analysis_snapshot: AsOfSnapshot | None = None
    benchmarks: tuple[ShadowDailyInput, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class ShadowRunReceipt(ShadowRecord):
    run_at: datetime
    collector_receipts: tuple[ShadowReference, ...]
    qualified_count: int
    events: tuple[ShadowReference, ...]
    admitted_count: int
    conflicted_count: int
    cancelled_count: int
    sessions: tuple[ShadowReference, ...]
    result_links: tuple[ShadowReference, ...]
    linked_count: int
    outcomes: tuple[ShadowReference, ...]
    outcomes_ready: int
    source_partial: int
    source_failed: int
    bse_unsupported_shape: int
    status: str
    live_event_proof: str
    live_outcome_proof: str
    reasons: tuple[str, ...]
    horizon_state: str = "POLICY_UNSET_CALIBRATION_REQUIRED"
    layer2: str = "PARTIAL_NOT_IMPLEMENTED"
    gate_policy_v2_active: bool = False

    def __post_init__(self):
        ShadowRecord.__post_init__(self)
        utc(self.run_at)
        if (self.gate_policy_v2_active is not False or self.horizon_state != "POLICY_UNSET_CALIBRATION_REQUIRED"
            or self.layer2 != "PARTIAL_NOT_IMPLEMENTED"
            or any(type(v) is not int or v < 0 for v in (self.qualified_count, self.admitted_count,
                self.conflicted_count, self.cancelled_count, self.linked_count, self.outcomes_ready,
                self.source_partial, self.source_failed, self.bse_unsupported_shape))
            or self.admitted_count + self.conflicted_count + self.cancelled_count != len(self.events)
            or self.linked_count > len(self.result_links) or self.outcomes_ready > len(self.outcomes)
            or self.status not in {"WAITING_FOR_QUALIFYING_EVENT", "TRACKING", "RECONCILIATION_REQUIRED"}
            or self.live_event_proof != ("PROVEN" if self.admitted_count else "PENDING_EVENT")
            or self.live_outcome_proof != ("PROVEN" if self.outcomes_ready else "PENDING_RESULT" if self.admitted_count else "PENDING_EVENT")):
            raise EarningsHorizonShadowError("SHADOW_RUN_INVALID")


def _snapshots(repository, bound: int, family=COLLECTOR_FAMILY) -> tuple[CoreApiSnapshot, ...]:
    if type(bound) is not int or not 1 <= bound <= 10000:
        raise EarningsHorizonShadowError("SHADOW_RECEIPT_BOUND_INVALID")
    result = []
    for offset in range(0, bound + 1, 100):
        page = repository.list_snapshots(family, limit=min(100, bound + 1 - offset), offset=offset)
        result.extend(page)
        if len(result) > bound:
            raise EarningsHorizonShadowError("SHADOW_RECEIPT_BOUND_EXCEEDED_NO_PARTIAL_SCAN")
        if len(page) < min(100, bound + 1 - offset):
            break
    for s in result:
        p = s.payload
        p.__post_init__()
        if s.family is not family or s.fingerprint != p.fingerprint or s.schema_version != "v1" or s.record_type != type(p).__name__:
            raise EarningsHorizonShadowError("SHADOW_SNAPSHOT_ENVELOPE_INVALID")
        identifiers = ("record_id", "receipt_id", "artifact_id", "observation_id", "assessment_id", "poll_id", "run_id")
        own = next((getattr(p, name) for name in identifiers if hasattr(p, name)), None)
        if isinstance(p, EarningsScheduleCoverageReceipt):
            own = "prospective-earnings-coverage:" + p.receipt_id
        if own != s.snapshot_id:
            raise EarningsHorizonShadowError("SHADOW_SNAPSHOT_IDENTITY_INVALID")
    if len({s.snapshot_id for s in result}) != len(result):
        raise EarningsHorizonShadowError("SHADOW_SNAPSHOT_DUPLICATE")
    return tuple(result)


def _qualified(snapshots, bridge, point):
    by_id = {s.snapshot_id: s.payload for s in snapshots}
    output = []
    for s in snapshots:
        r = s.payload
        if not isinstance(r, ProspectiveQualifiedScheduleReceipt) or r.processed_at > point:
            continue
        o = by_id.get(r.source_observation_id)
        if not isinstance(o, ProspectiveSourceObservation):
            raise EarningsHorizonShadowError("SHADOW_SOURCE_OBSERVATION_MISSING")
        a = by_id.get(o.raw_artifact_id)
        discovery = by_id.get(o.discovery_observation_id)
        if not isinstance(a, ProspectiveRawArtifactReceipt) or not isinstance(discovery, ProspectiveSourceObservation):
            raise EarningsHorizonShadowError("SHADOW_RAW_OR_DISCOVERY_LINEAGE_MISSING")
        discovery_artifact = by_id.get(discovery.raw_artifact_id)
        if (not isinstance(discovery_artifact, ProspectiveRawArtifactReceipt)
            or discovery_artifact.source_family != discovery.source_family
            or discovery.first_observed_at > o.first_observed_at
            or discovery.source_family != o.source_family):
            raise EarningsHorizonShadowError("SHADOW_DISCOVERY_LINEAGE_INVALID")
        assessments = tuple(v for v in by_id.values() if isinstance(v, ProspectiveScheduleAssessmentReceipt)
            and v.qualified_receipt_id == r.receipt_id and v.source_observation_id == o.observation_id
            and v.processed_at <= point and v.state is ProspectiveObservationState.OBSERVED)
        if not assessments:
            raise EarningsHorizonShadowError("SHADOW_QUALIFICATION_ASSESSMENT_MISSING")
        method = bridge.resolve_nse if o.source.exchange.value == "NSE" else bridge.resolve_bse
        key = "symbol" if o.source.exchange.value == "NSE" else "security_code"
        identity = method(o.source.field(key), o.source.field("isin"), o.first_observed_at)
        output.append(QualifiedShadowInput(r, o, a, identity))
    return tuple(output)


def persist_shadow(repository: CoreApiSnapshotRepository, value: ShadowRecord, *, created_at: datetime) -> bool:
    value.__post_init__()
    existing = repository.get_snapshot(value.record_id)
    if existing is not None:
        if existing.family is not FAMILY or existing.fingerprint != value.fingerprint or existing.payload != value:
            raise EarningsHorizonShadowError("SHADOW_IMMUTABILITY_CONFLICT")
        existing.payload.__post_init__()
        return False
    repository.save_snapshot(CoreApiSnapshot(value.record_id, FAMILY, "v1", type(value).__name__,
        value.fingerprint, utc(created_at), value))
    return True


def run_shadow_once(repository: CoreApiSnapshotRepository, *, as_of: datetime,
                    identity_bridge: EarningsScheduleCanonicalIdentityBridge | None = None,
                    calendar: CanonicalMarketSessionCalendar | None = None,
                    sessions: tuple[SessionRequest, ...] = (), results: tuple[ShadowResultEvidence, ...] = (),
                    reaction_bars: tuple[ShadowDailyInput, ...] = (), max_receipts: int = 1000) -> ShadowRunReceipt:
    """No clock/network. One bounded family scan; late evidence appends outcomes.

    Empty input avoids identity/market/financial universe scans altogether.
    A later invocation sees newly qualified receipts without policy/code change.
    """
    point = utc(as_of)
    if len(sessions) > 500 or len(results) > 100 or len(reaction_bars) > 500:
        raise EarningsHorizonShadowError("SHADOW_ENRICHMENT_BOUND_EXCEEDED")
    snapshots = tuple(s for s in _snapshots(repository, max_receipts) if utc(s.created_at) <= point)
    positives = tuple(s for s in snapshots if isinstance(s.payload, ProspectiveQualifiedScheduleReceipt) and s.payload.processed_at <= point)
    bridge = identity_bridge
    if positives and bridge is None:
        bridge = EarningsScheduleCanonicalIdentityBridge.from_reader(repository)
    values = _qualified(snapshots, bridge, point) if positives else ()
    events = reconcile_events(values, as_of=point)
    session_records, links, outcomes = {}, {}, {}
    event_ids = {e.logical_event_id for e in events}
    # Only this typed shadow family is read, never a whole-market scan. The
    # bound applies independently to both families and fails rather than trims.
    for stored in _snapshots(repository, max_receipts, FAMILY):
        p = stored.payload
        if (isinstance(p, ShadowSessionObservation) and stored.created_at <= point
            and p.decision_as_of <= point and p.logical_event_id in event_ids):
            session_records[p.record_id] = p
    # Construct and validate all artifacts before the first write.
    if sessions and calendar is None:
        raise EarningsHorizonShadowError("SHADOW_CANONICAL_CALENDAR_REQUIRED")
    for request in sessions:
        if utc(request.as_of) > point:
            continue
        item = observe_session(values=values, instrument=request.daily.bar.instrument.instrument_id, calendar=calendar,
            daily=request.daily, decision_as_of=request.as_of, history=request.history,
            analysis_snapshot=request.analysis_snapshot, benchmarks=request.benchmarks)
        if item is not None:
            session_records[item.record_id] = item
    for event in events:
        link = link_result(event, results, as_of=point)
        # Link identity is evidence-based, not invocation-time-based. Its PIT
        # boundary is latest supplied visible evidence, not an invented clock.
        link_point = max((event.as_of, *(v.filing.received_at for v in link.candidates),
                          *(f.available_at for v in link.candidates for f in v.facts),
                          *(v.publication.semantic_evidence_known_at for v in link.candidates if v.publication and v.publication.semantic_evidence_known_at)))
        link = link_result(event, link.candidates, as_of=link_point)
        links[link.record_id] = link
        if calendar:
            for obs in session_records.values():
                if obs.logical_event_id == event.logical_event_id:
                    outcome = attach_outcome(obs, link, calendar=calendar, reaction_bars=reaction_bars, as_of=point)
                    outcomes[outcome.record_id] = outcome
    polls = tuple(s.payload for s in snapshots if isinstance(s.payload, ProspectiveSourcePollReceipt) and s.payload.processed_at <= point)
    admitted = sum(e.state not in {ShadowState.CONFLICTED, ShadowState.CANCELLED} for e in events)
    ready = sum(o.state is ShadowState.OUTCOME_READY for o in outcomes.values())
    reasons = []
    if admitted and calendar is None: reasons.append("CANONICAL_CALENDAR_ENRICHMENT_PENDING")
    if admitted and not session_records: reasons.append("PIT_DAILY_SESSION_ENRICHMENT_PENDING")
    if any(p.reason == "SOURCE_SHAPE_UNSUPPORTED" for p in polls): reasons.append("BSE_DETAIL_SOURCE_SHAPE_UNSUPPORTED")
    receipt = _record(ShadowRunReceipt, run_at=point,
        collector_receipts=tuple(sorted(ShadowReference(s.snapshot_id, s.fingerprint) for s in snapshots)),
        qualified_count=len(positives), events=tuple(sorted(reference(e) for e in events)), admitted_count=admitted,
        conflicted_count=sum(e.state is ShadowState.CONFLICTED for e in events), cancelled_count=sum(e.state is ShadowState.CANCELLED for e in events),
        sessions=tuple(sorted(reference(s) for s in session_records.values())), result_links=tuple(sorted(reference(s) for s in links.values())),
        linked_count=sum(s.state is ResultLinkState.LINKED for s in links.values()),
        outcomes=tuple(sorted(reference(o) for o in outcomes.values())), outcomes_ready=ready,
        source_partial=sum(p.state is ProspectivePollState.PARTIAL for p in polls), source_failed=sum(p.state is ProspectivePollState.FAILED for p in polls),
        bse_unsupported_shape=sum(p.source_family.value == "BSE_ANNOUNCEMENTS" and p.reason == "SOURCE_SHAPE_UNSUPPORTED" for p in polls),
        status="TRACKING" if admitted else "RECONCILIATION_REQUIRED" if events else "WAITING_FOR_QUALIFYING_EVENT",
        live_event_proof="PROVEN" if admitted else "PENDING_EVENT", live_outcome_proof="PROVEN" if ready else "PENDING_RESULT" if admitted else "PENDING_EVENT",
        reasons=tuple(sorted(reasons)))
    for value in (*events, *session_records.values(), *links.values(), *outcomes.values(), receipt):
        persist_shadow(repository, value, created_at=point)
    return receipt
