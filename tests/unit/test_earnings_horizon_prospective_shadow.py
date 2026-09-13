"""Synthetic prospective-only integration through existing canonical owners."""
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, localcontext
import ast
from pathlib import Path

import pytest

from app.filings.earnings_horizon_prospective_shadow import *
from app.filings.earnings_horizon_prospective_shadow import _atr, _record
from app.filings.earnings_horizon_shadow_runner import (
    FAMILY, SessionRequest, _qualified, _snapshots, persist_shadow, run_shadow_once,
)
from app.filings.earnings_schedule_known_at import (
    SourceTimestampEvidence, SourceTimestampSemanticAuthority, TimestampFieldSemantic,
)
from app.filings.earnings_schedule_prospective_receipt_collector import (
    make_qualified_schedule_receipt, make_system_first_observed_receipt,
    make_source_observation, make_raw_artifact_receipt,
)
from app.filings.earnings_schedule_source import RawSchedule
from app.filings.models import BoardMeetingMetadata, FilingTimestampSourceEvidence
from app.historical.filing_timestamp_timezone_provenance import receipt_from_corporate_filing
from app.market_data.daily_technical_bar_temporal_evidence import DailySourceAvailabilitySemantics
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import snapshot_json, snapshot_json_from
from tests.unit.test_earnings_schedule_prospective_receipt_collector import (
    T, INSTRUMENT, Clock, Transport, _bridge, _run, RSS_WITH_LINK,
)
from tests.unit.test_daily_technical_bar_temporal_evidence import _calendar, _bar
from tests.unit.test_filing_timestamp_timezone_provenance import _filing


DECISION = datetime(2026, 10, 15, 12, tzinfo=UTC)
AFTER = datetime(2026, 10, 17, 12, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "shadow.sqlite")
    _run(repo, clock=Clock(T), transport=Transport())
    yield repo
    repo.close()


def inputs(repo):
    return _qualified(_snapshots(repo, 1000), _bridge(), AFTER)


def daily(day=date(2026, 10, 15), *, opened="100", close="100", known=None, conflicted=False, instrument=INSTRUMENT):
    base = _bar()
    at = datetime(day.year, day.month, day.day, 10, tzinfo=UTC)
    bar = replace(base, bar_id="daily:" + instrument + ":" + day.isoformat(),
        instrument=replace(base.instrument, instrument_id=instrument), start_time=at - timedelta(hours=6), end_time=at,
        open=Decimal(opened), close=Decimal(close), high=max(Decimal(opened), Decimal(close)) + 2,
        low=min(Decimal(opened), Decimal(close)) - 2,
        provenance=replace(base.provenance, exchange_timestamp=at, provider_timestamp=at, received_at=known or at))
    timing = DailyBarSourceTimingEvidence("fixture", day, DailySourceAvailabilitySemantics.HSI_OBSERVED_AT_FORWARD_ONLY,
        None, "daily-source-receipt:" + day.isoformat(), "sha256:" + "a" * 64, known or at)
    return ShadowDailyInput(bar, timing, conflicted)


def observation(repo, *, at=DECISION, value=None):
    return observe_session(values=inputs(repo), instrument=INSTRUMENT, calendar=_calendar(), daily=value or daily(), decision_as_of=at)


def result(repo, *, at=datetime(2026, 10, 16, 3, tzinfo=UTC), explicit=True, publication=True, identity="result:one"):
    r = inputs(repo)[0].receipt
    raw = FilingTimestampSourceEvidence("BSE_OFFICIAL_FINANCIAL_RESULTS", "https://www.bseindia.com/XBRLFILES/synthetic.xml",
        "synthetic-results", "result.publication", at.isoformat(), "PUBLIC_DISSEMINATION_TIME")
    filing = replace(_filing(evidence=raw), filing_id=identity, announced_at=at, received_at=at + timedelta(minutes=1),
        board_meeting=BoardMeetingMetadata(datetime(2026, 10, 16, tzinfo=UTC), "Financial Results", r.source_filing_identity if explicit else None),
        provenance=replace(_filing(evidence=raw).provenance, received_at=at + timedelta(minutes=1)))
    receipt = receipt_from_corporate_filing(filing, as_of=AFTER)
    pub = SourceTimestampEvidence(TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME,
        SourceTimestampSemanticAuthority.PROVEN, ("official-pub-field",), ("sha256:" + "b" * 64,), T, receipt)
    return ShadowResultEvidence(filing, pub if publication else None)


def link(repo, *items):
    event = reconcile_events(inputs(repo), as_of=AFTER)[0]
    return link_result(event, tuple(items), as_of=AFTER)


def revised(value, *, at=DECISION - timedelta(days=1), day=date(2026, 10, 19), lifecycle=ScheduleLifecycleState.RESCHEDULED, parent=True):
    r, o = value.receipt, value.observation
    label = {ScheduleLifecycleState.RESCHEDULED: "Rescheduled", ScheduleLifecycleState.CANCELLED: "Cancelled", ScheduleLifecycleState.REVISED: "Revised"}[lifecycle]
    raw = dict(o.source.raw) | {"intimation_type": label, "meeting_date_iso": day.isoformat()}
    row = RawSchedule(o.source.exchange, o.source.reference, tuple(sorted(raw.items())), o.source.parser_version)
    art = make_raw_artifact_receipt(source_family=r.source_family, source_endpoint=value.artifact.source_endpoint,
        raw_payload=("synthetic:" + label + at.isoformat()).encode(), observed_at=at, request_identity="OFFICIAL_SOURCE_GET",
        adapter_version="official-earnings-schedule-source/v1", http_status=200)
    obs = make_source_observation(artifact=art, source=row, observed_at=at, discovery_observation_id=o.discovery_observation_id)
    identity = _bridge().resolve_bse(row.field("security_code"), row.field("isin"), at)
    first = make_system_first_observed_receipt(canonical_instrument_id=INSTRUMENT, source_filing_identity=obs.source_record_identity,
        source_payload_fingerprint=obs.source_record_fingerprint, observed_at=at, ingestion_run_id="synthetic-run", run_sequence=1)
    receipt = make_qualified_schedule_receipt(observation=obs, canonical_instrument_id=INSTRUMENT, identity_fingerprint=identity.fingerprint,
        purpose_classification=r.purpose_classification, purpose_rule=r.purpose_rule, event_date=day, first_observed=first,
        processed_at=at + timedelta(seconds=2), lifecycle_state=lifecycle, revision_of_receipt_id=r.receipt_id if parent else "missing-parent")
    return QualifiedShadowInput(receipt, obs, art, identity)


def test_real_collector_admission_immutability_and_no_runtime_identity(repository):
    v = inputs(repository)
    one = reconcile_events(v, as_of=DECISION)[0]
    assert one.first_observed_at == v[0].receipt.system_first_observed.observed_at
    assert one.as_of == v[0].receipt.processed_at
    assert reconcile_events(v, as_of=AFTER)[0] == one
    assert reconcile_events(v + v, as_of=DECISION) == (one,)
    with pytest.raises(FrozenInstanceError): one.state = ShadowState.CANCELLED
    with pytest.raises(ValueError): replace(one, fingerprint="sha256:" + "0" * 64)


def test_no_knowledge_before_completed_receipt_and_no_past_schedule(repository):
    v = inputs(repository)
    assert reconcile_events(v, as_of=v[0].receipt.system_first_observed.observed_at) == ()
    assert reconcile_events(v, as_of=v[0].known_at) != ()
    r = v[0].receipt
    past = make_qualified_schedule_receipt(observation=v[0].observation, canonical_instrument_id=INSTRUMENT,
        identity_fingerprint=r.identity_fingerprint, purpose_classification=r.purpose_classification, purpose_rule=r.purpose_rule,
        event_date=T.date(), first_observed=r.system_first_observed, processed_at=r.processed_at,
        lifecycle_state=r.lifecycle_state, revision_of_receipt_id=None)
    assert reconcile_events((replace(v[0], receipt=past),), as_of=AFTER) == ()


def test_tampered_source_identity_and_raw_lineage_rejected(repository):
    v = inputs(repository)[0]
    with pytest.raises(ValueError): replace(v, identity=replace(v.identity, canonical_instrument_id="NSE:INE000A01001"))
    with pytest.raises(ValueError): replace(v, artifact=replace(v.artifact, raw_payload_base64="eA=="))
    with pytest.raises(ValueError): replace(v, receipt=replace(v.receipt, processed_at=T))


def test_exact_revisions_and_cancellation_preserve_earlier_truth(repository):
    v = inputs(repository)
    change = revised(v[0])
    before = reconcile_events(v + (change,), as_of=change.known_at - timedelta(seconds=1))[0]
    assert before.scheduled_event_date == date(2026, 10, 16)
    after = reconcile_events(v + (change,), as_of=change.known_at)[0]
    assert after.scheduled_event_date == date(2026, 10, 19)
    assert after.logical_event_id == before.logical_event_id
    assert after.state is ShadowState.RESCHEDULED
    cancellation = revised(change, at=DECISION, day=date(2026, 10, 19), lifecycle=ScheduleLifecycleState.CANCELLED)
    cancelled = reconcile_events(v + (change, cancellation), as_of=AFTER)[0]
    assert cancelled.state is ShadowState.CANCELLED
    assert link_result(cancelled, (result(repository),), as_of=AFTER).state is ResultLinkState.UNAVAILABLE
    assert before.scheduled_event_date == date(2026, 10, 16)


def test_missing_parent_and_equal_time_revision_branches_fail_closed(repository):
    v = inputs(repository)
    assert reconcile_events(v + (revised(v[0], parent=False),), as_of=AFTER)[0].state is ShadowState.CONFLICTED
    changes = (revised(v[0]), revised(v[0], day=date(2026, 10, 20)))
    one = reconcile_events(v + changes, as_of=AFTER)
    assert one[0].state is ShadowState.CONFLICTED
    assert one == reconcile_events(changes[::-1] + v, as_of=AFTER)


@pytest.mark.parametrize("end,expected", [(date(2026, 10, 19), 1), (date(2026, 10, 18), None), (date(2027, 1, 1), None)])
def test_exchange_session_distance_no_calendar_day_fallback(end, expected):
    assert session_distance(_calendar(), date(2026, 10, 16), end, as_of=DECISION) == expected


def test_session_snapshot_pit_and_optional_atr_context(repository):
    obs = observation(repository)
    assert obs.sessions_to_event == 1 and obs.atr is None
    assert "ATR_LINEAGE_UNAVAILABLE" in obs.unavailable
    assert obs.known_notice_sessions > 1
    assert observation(repository, value=daily(known=DECISION + timedelta(seconds=1))) is None
    assert observation(repository, value=daily(conflicted=True)) is None
    assert observation(repository, at=datetime(2026, 10, 15, 8, tzinfo=UTC)) is None
    assert observation(repository, value=daily(instrument="NSE:OTHER")) is None


def test_result_link_is_explicit_never_nearest_date_and_future_excluded(repository):
    assert link(repository, result(repository, explicit=False)).state is ResultLinkState.PENDING
    assert link(repository, result(repository)).state is ResultLinkState.LINKED
    assert link(repository, result(repository), result(repository, identity="result:two")).state is ResultLinkState.AMBIGUOUS
    event = reconcile_events(inputs(repository), as_of=DECISION)[0]
    assert link_result(event, (result(repository),), as_of=DECISION).state is ResultLinkState.PENDING
    assert link(repository, result(repository), result(repository)).state is ResultLinkState.LINKED


def test_pre_open_reaction_metrics_and_decimal_context_independence(repository):
    obs, matched = observation(repository), link(repository, result(repository))
    kwargs = dict(calendar=_calendar(), reaction_bars=(daily(date(2026, 10, 16), opened="110", close="121"),))
    actual = attach_outcome(obs, matched, **kwargs)
    assert actual.state is ShadowState.OUTCOME_READY
    assert actual.signed_gap == actual.absolute_gap == Decimal("0.1")
    assert actual.reaction_return == actual.absolute_reaction_return == Decimal("0.1")
    assert actual.atr_normalized_gap is None
    with localcontext() as ctx:
        ctx.prec = 6
        assert attach_outcome(obs, matched, **kwargs) == actual
    assert attach_outcome(obs, matched, as_of=AFTER + timedelta(days=1), **kwargs) == actual


@pytest.mark.parametrize("hour,reason", [(7, "REACTION_SESSION_ORDERING_INCOMPLETE"), (10, "PREVIOUS_CLOSE_OBSERVATION_REQUIRED")])
def test_intraday_and_after_close_do_not_guess_reaction(hour, reason, repository):
    matched = link(repository, result(repository, at=datetime(2026, 10, 16, hour, tzinfo=UTC)))
    actual = attach_outcome(observation(repository), matched, calendar=_calendar(), reaction_bars=())
    assert actual.state is ShadowState.TEMPORAL_OUTCOME_INCOMPLETE and reason in actual.reasons


def test_unknown_publication_and_reaction_bar_conflicts_fail_closed(repository):
    obs = observation(repository)
    assert attach_outcome(obs, link(repository, result(repository, publication=False)), calendar=_calendar(), reaction_bars=()).signed_gap is None
    bars = (daily(date(2026, 10, 16)), daily(date(2026, 10, 16), opened="101"))
    assert attach_outcome(obs, link(repository, result(repository)), calendar=_calendar(), reaction_bars=bars).state is ShadowState.TEMPORAL_OUTCOME_INCOMPLETE


def test_no_arbitrary_pre_event_return_mislabeled_as_previous_close(repository):
    obs = observation(repository, at=DECISION - timedelta(days=1), value=daily(date(2026, 10, 14)))
    actual = attach_outcome(obs, link(repository, result(repository)), calendar=_calendar(), reaction_bars=(daily(date(2026, 10, 16)),))
    assert actual.signed_gap is None and actual.reasons == ("PREVIOUS_CLOSE_OBSERVATION_REQUIRED",)


def test_runner_restart_idempotency_roundtrip_and_no_other_family_writes(repository):
    request = SessionRequest(daily(), DECISION)
    kwargs = dict(as_of=AFTER, identity_bridge=_bridge(), calendar=_calendar(), sessions=(request,),
        results=(result(repository),), reaction_bars=(daily(date(2026, 10, 16), opened="110", close="121"),))
    before = len(_snapshots(repository, 1000))
    first = run_shadow_once(repository, **kwargs)
    count = len(repository.list_snapshots(FAMILY))
    assert first.admitted_count == 1 and first.outcomes_ready == 1
    assert run_shadow_once(repository, **kwargs) == first
    assert len(repository.list_snapshots(FAMILY)) == count
    assert len(_snapshots(repository, 1000)) == before
    for snap in repository.list_snapshots(FAMILY):
        restored = snapshot_json_from(snapshot_json(snap))
        assert restored == snap
        assert not persist_shadow(repository, restored.payload, created_at=AFTER)


def test_zero_event_runner_no_identity_scan_or_fake_observation(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "empty.sqlite")
    try:
        receipt = run_shadow_once(repo, as_of=AFTER)
        assert receipt.status == "WAITING_FOR_QUALIFYING_EVENT"
        assert receipt.admitted_count == receipt.outcomes_ready == 0
        assert receipt.live_event_proof == receipt.live_outcome_proof == "PENDING_EVENT"
        assert not receipt.sessions and not receipt.result_links
    finally: repo.close()


def test_bound_failure_writes_nothing(repository):
    with pytest.raises(ValueError, match="BOUND_EXCEEDED"):
        run_shadow_once(repository, as_of=AFTER, max_receipts=1)
    assert repository.list_snapshots(FAMILY) == ()


def test_fixed_authority_and_static_boundary(repository):
    obs = observation(repository)
    with pytest.raises(ValueError): replace(obs, execution_status="AUTHORIZED")
    for module in ("earnings_horizon_prospective_shadow", "earnings_horizon_shadow_runner"):
        tree = ast.parse(Path("app/filings", module + ".py").read_text(encoding="utf-8"))
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(name and name.startswith(("app.portfolio", "app.rotation", "app.broker", "app.orders", "app.api", "app.signals", "app.gates.engine")) for name in imports)
        assert not any(isinstance(n, ast.Attribute) and n.attr in {"now", "utcnow", "execute", "submit_order"} for n in ast.walk(tree))
    names = {f.name for f in fields(type(obs))}
    assert not names & {"entry_price", "target_price", "quantity", "horizon", "order", "portfolio", "gate_authorization"}


def test_two_exchanges_without_exact_document_agreement_excluded_not_double_counted(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "dual.sqlite")
    try:
        _run(repo, clock=Clock(T), transport=Transport(rss=RSS_WITH_LINK))
        v = inputs(repo)
        assert len(v) == 2
        events = reconcile_events(v, as_of=AFTER)
        assert len(events) == 1
        assert events[0].state is ShadowState.CONFLICTED
        assert "LOGICAL_EVENT_RECONCILIATION_UNRESOLVED" in events[0].reasons
        assert events == reconcile_events(v[::-1], as_of=AFTER)
        run = run_shadow_once(repo, as_of=AFTER, identity_bridge=_bridge())
        assert run.qualified_count == 2 and run.admitted_count == 0 and run.conflicted_count == 1
    finally: repo.close()


def test_existing_atr14_formula_and_exact_lineage_no_future_history(repository):
    days = [date(2026, 9, 25) + timedelta(days=i) for i in range(21)]
    history = tuple(daily(d) for d in days if d.weekday() < 5)
    assert len(history) == 15
    kwargs = dict(values=inputs(repository), instrument=INSTRUMENT, calendar=_calendar(), daily=daily(), decision_as_of=DECISION)
    obs = observe_session(**kwargs, history=history)
    assert obs.atr == Decimal("4.0") and len(obs.atr_lineage) == 16
    actual = attach_outcome(obs, link(repository, result(repository)), calendar=_calendar(),
        reaction_bars=(daily(date(2026, 10, 16), opened="110", close="121"),))
    assert actual.atr_normalized_gap == Decimal("2.5")
    assert observe_session(**kwargs, history=history + (daily(date(2026, 10, 16)),)).atr is None
    assert observe_session(**kwargs, history=history + history[:1]).atr is None
    assert observe_session(**kwargs, history=history[:-1]).atr is None
    assert observe_session(**kwargs, history=history[:3] + history[4:]).atr is None


def test_after_close_result_maps_to_next_regular_session_without_weekend_shift_guess(repository):
    point = datetime(2026, 10, 16, 11, tzinfo=UTC)
    obs = observation(repository, at=point, value=daily(date(2026, 10, 16)))
    assert obs.sessions_to_event == 0
    evidence = result(repository, at=datetime(2026, 10, 16, 13, tzinfo=UTC))
    matched = link(repository, evidence)
    actual = attach_outcome(obs, matched, calendar=_calendar(), as_of=datetime(2026, 10, 19, 12, tzinfo=UTC),
        reaction_bars=(daily(date(2026, 10, 19), opened="110", close="121"),))
    assert actual.state is ShadowState.OUTCOME_READY and actual.reaction_session == date(2026, 10, 19)


def test_timezone_equivalent_serialization_and_no_future_bar_receipt(repository):
    obs = observation(repository)
    same = observation(repository, at=DECISION.astimezone(IST))
    assert serialize_shadow(obs) == serialize_shadow(same)
    bad = daily()
    bad = replace(bad, bar=replace(bad.bar, provenance=replace(bad.bar.provenance, received_at=AFTER)))
    assert observation(repository, value=bad) is None


def test_cancellation_prevents_later_session_without_erasing_frozen_one(repository):
    v = inputs(repository)
    frozen = observation(repository)
    change = revised(v[0], at=DECISION + timedelta(minutes=1), day=date(2026, 10, 16), lifecycle=ScheduleLifecycleState.CANCELLED)
    assert observe_session(values=v + (change,), instrument=INSTRUMENT, calendar=_calendar(), daily=daily(), decision_as_of=DECISION) == frozen
    assert observe_session(values=v + (change,), instrument=INSTRUMENT, calendar=_calendar(), daily=daily(), decision_as_of=DECISION + timedelta(hours=1)) is None


def test_restart_later_run_reuses_event_and_session_and_outcome_records(repository):
    kwargs = dict(identity_bridge=_bridge(), calendar=_calendar(), sessions=(SessionRequest(daily(), DECISION),),
        results=(result(repository),), reaction_bars=(daily(date(2026, 10, 16)),))
    first = run_shadow_once(repository, as_of=AFTER, **kwargs)
    second = run_shadow_once(repository, as_of=AFTER + timedelta(days=1), **kwargs)
    assert first.events == second.events and first.sessions == second.sessions
    assert first.result_links == second.result_links and first.outcomes == second.outcomes
    assert first.record_id != second.record_id  # run timestamp is operational lineage only


def test_new_positive_arrives_after_waiting_no_code_or_policy_rewrite(tmp_path):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path / "arriving.sqlite")
    try:
        assert run_shadow_once(repo, as_of=T).admitted_count == 0
        _run(repo, clock=Clock(T), transport=Transport())
        run = run_shadow_once(repo, as_of=DECISION, identity_bridge=_bridge())
        assert run.admitted_count == 1 and run.live_event_proof == "PROVEN"
        assert run.live_outcome_proof == "PENDING_RESULT"
        assert not run.gate_policy_v2_active
    finally: repo.close()


def test_later_result_attaches_to_stored_session_after_reopen_without_rebuilding(repository):
    first = run_shadow_once(repository, as_of=DECISION, identity_bridge=_bridge(), calendar=_calendar(),
        sessions=(SessionRequest(daily(), DECISION),))
    assert first.outcomes_ready == 0 and len(first.sessions) == 1
    reopened = SQLiteCoreApiSnapshotRepository(repository._connection.execute("PRAGMA database_list").fetchone()[2])
    try:
        later = run_shadow_once(reopened, as_of=AFTER, identity_bridge=_bridge(), calendar=_calendar(),
            results=(result(repository),), reaction_bars=(daily(date(2026, 10, 16)),))
        assert later.outcomes_ready == 1 and later.sessions == first.sessions
        assert reopened.get_snapshot(first.sessions[0].record_id) == repository.get_snapshot(first.sessions[0].record_id)
    finally: reopened.close()


def test_nonterminating_metric_does_not_depend_on_global_decimal_precision(repository):
    obs = observation(repository, value=daily(opened="3", close="3"))
    matched = link(repository, result(repository))
    kwargs = dict(calendar=_calendar(), reaction_bars=(daily(date(2026, 10, 16), opened="4", close="5"),))
    one = attach_outcome(obs, matched, **kwargs)
    with localcontext() as ctx:
        ctx.prec = 4
        assert attach_outcome(obs, matched, **kwargs) == one


def test_date_only_and_naive_result_timestamp_is_retained_not_guessed(repository):
    value = result(repository)
    raw = replace(value.filing.timestamp_evidence, raw_timestamp_value="10/16/2026 8:30:00 AM")
    filing = replace(value.filing, timestamp_evidence=raw)
    receipt = receipt_from_corporate_filing(filing, as_of=AFTER)
    pub = SourceTimestampEvidence(TimestampFieldSemantic.PUBLIC_DISSEMINATION_TIME,
        SourceTimestampSemanticAuthority.PROVEN, ("official-pub-field",), ("sha256:" + "b" * 64,), T, receipt)
    matched = link(repository, ShadowResultEvidence(filing, pub))
    actual = attach_outcome(observation(repository), matched, calendar=_calendar(), reaction_bars=())
    assert actual.state is ShadowState.TEMPORAL_OUTCOME_INCOMPLETE
    assert serialize_shadow(matched)  # raw naive timestamp is retained, never localized
