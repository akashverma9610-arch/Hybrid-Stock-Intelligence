"""Synthetic canonical/ledger fixtures only; never production state/provider I/O."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path

import pytest

from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus
from app.intelligence.hsi_signal import serialize_hsi_signal
from app.intelligence.hsi_signal_projection import project_watch_to_hsi_signal
from app.intelligence.hsi_signal_strategy_registry import HSISignalStrategyRegistry
from app.intelligence.market_wide_watch import MarketWideWatchRecord
from app.intelligence.opportunity_archetypes import OpportunityArchetype
from app.intelligence.p1_signal_lifecycle import (
    CONTRACT, Evaluation, LifecycleError, Outcome, Reason, SourceReference, State,
    TECHNICAL_FAILURES, _RetainedGovernance, canonical_json, evaluate, qualify,
    replay, verify_chain,
)
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.storage.sqlite_p1_signal_lifecycle import SQLiteP1SignalLifecycleRepository
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision, prebreakout_policy_v1_3_multi_stage_entry_successor_draft,
)
from app.strategies.pre_breakout.setup_assessment import (
    PreBreakoutSetupAssessmentStatus, PreBreakoutSetupBlocker, PreBreakoutSetupBlockerCategory,
)
from tests.unit.test_pre_breakout_candidate_assembly import _assessment
from tests.unit.test_hsi_signal_projection import _watch


T = datetime(2026, 9, 2, 10, 30, tzinfo=UTC)
I = "NSE:INE000000001"


class Ledger:
    """Immutable-source test double, not a production known-at adapter."""
    def __init__(self, value):
        self.refs = value.references

    def verify(self, reference, *, as_of):
        return reference in self.refs

    def dependencies(self, reference):
        if reference.kind in ("WATCH", "ASSESSMENT"):
            return tuple(x for x in self.refs if x.kind == "DIAGNOSTIC")
        return ()


@pytest.fixture
def governance(tmp_path):
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    commands = PreBreakoutPolicyGovernanceCommandService(repo)
    draft = prebreakout_policy_v1_3_multi_stage_entry_successor_draft()
    approval = commands.approve(approval_id="approval:lifecycle", policy_id=draft.policy_id,
        policy_version=draft.version, decision=PreBreakoutPolicyApprovalDecision.APPROVE,
        reviewer_id="human:fixture", reviewed_at=T - timedelta(days=1))
    selection = commands.select_for_current_stored_scan(selection_id="selection:lifecycle",
        approval_id=approval.approval_id, selected_by="human:fixture",
        selected_at=T - timedelta(hours=1), effective_from=T - timedelta(hours=1))
    yield repo, repo.get_prebreakout_policy_approval(approval.approval_id), repo.get_prebreakout_policy_selection(selection.selection_id)
    repo.close()


def fixture(governance, at=T, *, geometry=False, negative=None, security=None):
    _, approval, selection = governance
    original = _assessment()
    lineage = dict(instrument_id=I, evaluation_as_of=at, policy_id=selection.policy_id,
                   policy_version=selection.policy_version, policy_fingerprint=selection.policy_fingerprint,
                   selection_id=selection.selection_id, selection_fingerprint=selection.fingerprint)
    technical = replace(original.technical_inputs, **lineage)
    structural = replace(original.structural, **lineage)
    if geometry:
        structural = replace(structural, tick_size=Decimal("0.10"))
    assessment = replace(original, **lineage, technical_inputs=technical, structural=structural)
    if negative:
        assessment = replace(assessment, candidate_formation_eligible=False,
            status=PreBreakoutSetupAssessmentStatus.BLOCKED_TECHNICAL_SETUP,
            blockers=(PreBreakoutSetupBlocker(PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, negative),),
            technical_inputs=replace(technical, **{TECHNICAL_FAILURES[negative]: False}))
    identity = security or HistoricalSecurityIdentity(
        "identity:active", I, "INE000000001", "NSE", "ALPHA", "EQ", T - timedelta(days=365),
        None, T - timedelta(days=365), None, T - timedelta(days=365), None,
        HistoricalSecurityStatus.ACTIVE, "SYNTHETIC_OFFICIAL", T - timedelta(days=2), "v1")
    watch = _watch(as_of=at)
    opportunity = None if negative else CanonicalSetupOpportunity.from_assessment(assessment)
    def ref(kind, id, fp, when=at, effective=None, known=None):
        return SourceReference(kind, id, fp, I, when, known or when, effective)
    refs = [ref("SECURITY_IDENTITY", identity.identity_id, sha256(repr(identity).encode()).hexdigest(), identity.as_of,
                identity.symbol_effective_from),
            ref("ASSESSMENT", assessment.assessment_id, assessment.fingerprint),
            ref("WATCH", watch.watch_id, watch.fingerprint),
            ref("APPROVAL", approval.approval_id, approval.fingerprint, approval.created_at),
            ref("SELECTION", selection.selection_id, selection.fingerprint, selection.selected_at, selection.effective_from)]
    refs.extend(ref("DIAGNOSTIC", e.artifact_id, e.artifact_fingerprint, T - timedelta(days=2)) for e in watch.evidence_references)
    if opportunity:
        refs.extend((ref("OPPORTUNITY", opportunity.opportunity_id, opportunity.fingerprint),
                     ref("CANDIDATE", opportunity.candidate.candidate_id, opportunity.candidate.fingerprint)))
    value = Evaluation(I, at, tuple(refs), (identity,), watch=watch, assessments=(assessment,),
                       opportunity=opportunity, approvals=(approval,), selections=(selection,))
    if not negative:
        p1 = project_watch_to_hsi_signal(watch=watch, archetype=OpportunityArchetype.PRE_BREAKOUT,
                                       registry=HSISignalStrategyRegistry(_RetainedGovernance(value)))
        value = replace(value, p1_json=serialize_hsi_signal(p1))
    return value


def admitted(value, chain=()):
    result = evaluate(value, chain, Ledger(value))
    assert result.outcome is Outcome.ACCEPTED, result
    return result.batch


def test_initial_continuation_retry_and_replay(governance):
    first = fixture(governance)
    b1 = admitted(first)
    assert b1.transitions[0].next_state is State.CURRENT
    assert b1.transitions[0].reason_code == "INITIAL_QUALIFICATION"
    later = fixture(governance, T + timedelta(days=1))
    b2 = admitted(later, (b1,))
    assert b2.transitions[0].lifetime_id == b1.transitions[0].lifetime_id
    assert b2.transitions[0].reason_code == "SETUP_CONTINUED"
    assert evaluate(first, (b1, b2), Ledger(first)).outcome is Outcome.NO_CHANGE
    assert replay((b1, b2), as_of=T).last_transition == b1.transitions[-1]
    assert replay((b1, b2), as_of=later.as_of + timedelta(seconds=1)).reason is Reason.REEVALUATION_REQUIRED


@pytest.mark.parametrize("failure", tuple(TECHNICAL_FAILURES))
def test_exact_native_negative_predicate_terminal_then_new_lifetime(governance, failure):
    b1 = admitted(fixture(governance))
    b2 = admitted(fixture(governance, T + timedelta(days=1), negative=failure), (b1,))
    assert b2.transitions[-1].next_state is State.INVALIDATED
    b3 = admitted(fixture(governance, T + timedelta(days=2)), (b1, b2))
    assert b3.transitions[-1].lifetime_id != b1.transitions[0].lifetime_id
    assert b3.transitions[-1].predecessor_terminal_id == b2.transitions[-1].transition_id
    assert replay((b1, b2), as_of=T + timedelta(days=20)).outcome is Outcome.ACCEPTED


def test_geometry_replacement_atomic_links_and_no_double_current(governance):
    b1 = admitted(fixture(governance))
    b2 = admitted(fixture(governance, T + timedelta(days=1), geometry=True), (b1,))
    assert [t.next_state for t in b2.transitions] == [State.SUPERSEDED, State.CURRENT]
    assert b2.transitions[0].replacement_lifetime_id == b2.transitions[1].lifetime_id
    assert b2.transitions[1].predecessor_terminal_id == b2.transitions[0].transition_id
    verify_chain((b1, b2))


@pytest.mark.parametrize("timing", ("evidence_known_at", "evidence_as_of", "effective_at"))
def test_future_source_blocked_and_no_known_at_fallback(governance, timing):
    value = fixture(governance)
    refs = (replace(value.references[0], **{timing: T + timedelta(seconds=1)}), *value.references[1:])
    changed = replace(value, references=refs)
    # Changing the approval envelope's as-of also contradicts its retained
    # created_at. LC-11 requires that conflict to outrank the future timestamp.
    expected = Outcome.CONFLICTED if timing == "evidence_as_of" else Outcome.SOURCE_BLOCKED
    assert evaluate(changed, (), Ledger(changed)).outcome is expected
    changed = replace(value, references=(replace(value.references[0], evidence_known_at=None), *value.references[1:]))
    assert evaluate(changed, (), Ledger(changed)).reason is Reason.EVIDENCE_KNOWN_AT_UNAVAILABLE


def test_source_dependency_closure_and_owning_reader_required(governance):
    value = fixture(governance)
    ledger = Ledger(value)
    ledger.refs = ()
    assert evaluate(value, (), ledger).outcome is Outcome.SOURCE_BLOCKED
    class Incomplete(Ledger):
        def dependencies(self, reference):
            return None
    assert evaluate(value, (), Incomplete(value)).reason is Reason.SOURCE_LINEAGE_UNAVAILABLE


def test_exact_duplicates_coalesce_conflicts_block_and_order_deterministic(governance):
    value = fixture(governance)
    assert admitted(replace(value, references=(*reversed(value.references), value.references[0]))) == admitted(value)
    bad = replace(value.references[0], fingerprint="0" * 64)
    conflict = replace(value, references=(*value.references, bad))
    assert evaluate(conflict, (), Ledger(conflict)).reason is Reason.EVIDENCE_CONFLICT


@pytest.mark.parametrize("tamper", ("p1", "assessment", "selection", "candidate", "watch"))
def test_tampered_native_lineage_never_repaired(governance, tamper):
    value = fixture(governance)
    if tamper == "p1":
        value = replace(value, p1_json=value.p1_json.replace("WATCH_ONLY", "EXECUTABLE"))
    elif tamper == "assessment":
        value = replace(value, assessments=(replace(value.assessments[0], sector="Wrong"),))
    elif tamper == "selection":
        object.__setattr__(value.selections[0], "fingerprint", "0" * 64)
    elif tamper == "candidate":
        object.__setattr__(value.opportunity.candidate, "tick_size", Decimal("9"))
    else:
        object.__setattr__(value.watch, "symbol", "WRONG")
    assert evaluate(value, (), Ledger(value)).outcome in (Outcome.CONFLICTED, Outcome.POLICY_BLOCKED)


def test_policy_outage_and_wrong_version_do_not_invalidate(governance):
    first = admitted(fixture(governance))
    negative = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    unavailable = replace(negative, approvals=(), selections=())
    assert evaluate(unavailable, (first,), Ledger(unavailable)).outcome is Outcome.POLICY_BLOCKED
    assert replay((first,), as_of=negative.as_of).last_transition.next_state is State.CURRENT


def test_missing_setup_and_unmapped_predicate_cannot_create_or_invalidate(governance):
    value = fixture(governance)
    bad = replace(value, opportunity=None)
    assert evaluate(bad, (), Ledger(bad)).outcome is Outcome.SOURCE_BLOCKED
    negative = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    bad = replace(negative, assessments=(replace(negative.assessments[0], blockers=()),))
    assert evaluate(bad, (admitted(value),), Ledger(bad)).outcome is not Outcome.ACCEPTED


def test_equal_cutoff_conflict_and_out_of_order_rejected(governance):
    later = fixture(governance, T + timedelta(days=1))
    b = admitted(later)
    old = fixture(governance)
    assert evaluate(old, (b,), Ledger(old)).reason is Reason.OUT_OF_ORDER_REQUIRES_REEVALUATION
    other = fixture(governance, later.as_of, geometry=True)
    assert evaluate(other, (b,), Ledger(other)).reason is Reason.CUTOFF_CONFLICT


def test_security_cessation_works_without_policy_and_never_resurrects(governance):
    first = fixture(governance)
    b1 = admitted(first)
    ended = replace(first.identities[0], identity_id="identity:ended", status=HistoricalSecurityStatus.DELISTED,
                    symbol_effective_from=T + timedelta(days=1), as_of=T + timedelta(days=1))
    ref = SourceReference("SECURITY_IDENTITY", ended.identity_id, sha256(repr(ended).encode()).hexdigest(),
                          I, ended.as_of, ended.as_of, ended.symbol_effective_from)
    value = Evaluation(I, ended.as_of, (ref,), (ended,))
    b2 = admitted(value, (b1,))
    assert b2.transitions[0].reason_code == "SECURITY_LIFECYCLE_ENDED"
    assert b2.transitions[0].next_state is State.INVALIDATED


def test_suspended_or_ambiguous_identity_is_not_terminal(governance):
    value = fixture(governance)
    for status in (HistoricalSecurityStatus.SUSPENDED, HistoricalSecurityStatus.INACTIVE):
        identity = replace(value.identities[0], status=status)
        changed = fixture(governance, security=identity)
        assert evaluate(changed, (), Ledger(changed)).reason is Reason.SECURITY_NOT_ELIGIBLE


def test_utc_decimal_and_frozen_contract(governance):
    value = fixture(governance)
    assert admitted(replace(value, as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))))) == admitted(value)
    with localcontext() as ctx:
        ctx.prec = 2
        assert canonical_json((Decimal("123456.12000"), Decimal("-0"))) == '["123456.12","0"]'
    with pytest.raises(FrozenInstanceError):
        value.as_of = T


def test_storage_reopen_retry_rebuild_and_no_legacy_writes(tmp_path, governance):
    path = tmp_path / "snapshot.sqlite"
    value = fixture(governance)
    store = SQLiteP1SignalLifecycleRepository(path)
    first = store.submit(value, Ledger(value))
    assert first.outcome is Outcome.ACCEPTED
    store.close()
    store = SQLiteP1SignalLifecycleRepository(path)
    assert store.submit(value, Ledger(value)).outcome is Outcome.NO_CHANGE
    assert store.read(I, as_of=T).last_transition == first.batch.transitions[-1]
    store._connection.execute("DELETE FROM p1_signal_lifecycle_heads")
    store._connection.commit()
    assert store.read(I, as_of=T).reason is Reason.CHAIN_CONFLICT
    store.rebuild_indexes(I)
    assert store.read(I, as_of=T).outcome is Outcome.ACCEPTED
    assert store._connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not store._connection.execute("PRAGMA foreign_key_check").fetchall()
    assert store._connection.execute("SELECT COUNT(*) FROM core_api_snapshots WHERE family='SIGNAL'").fetchone()[0] == 0
    store.close()


def test_concurrent_duplicate_writers_are_exactly_once(tmp_path, governance):
    path = tmp_path / "race.sqlite"
    SQLiteP1SignalLifecycleRepository(path).close()
    value = fixture(governance)
    def submit(_):
        store = SQLiteP1SignalLifecycleRepository(path)
        try:
            return store.submit(value, Ledger(value)).outcome
        finally:
            store.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sorted(results) == sorted([Outcome.ACCEPTED, Outcome.NO_CHANGE])


def test_failure_during_replacement_rolls_back_entire_batch(tmp_path, governance):
    store = SQLiteP1SignalLifecycleRepository(tmp_path / "rollback.sqlite")
    first = fixture(governance)
    original = store.submit(first, Ledger(first)).batch
    store._connection.execute("CREATE TRIGGER fail_head BEFORE UPDATE ON p1_signal_lifecycle_heads BEGIN SELECT RAISE(ABORT,'SYNTHETIC_FAILURE'); END")
    store._connection.commit()
    next_value = fixture(governance, T + timedelta(days=1), geometry=True)
    with pytest.raises(Exception, match="SYNTHETIC_FAILURE"):
        store.submit(next_value, Ledger(next_value))
    assert store._connection.execute("SELECT COUNT(*) FROM core_api_snapshots").fetchone()[0] == 1
    assert store.read(I, as_of=T).last_transition == original.transitions[-1]
    store.close()


def test_chain_tampering_and_removed_predecessor_fail_closed(governance):
    b1 = admitted(fixture(governance))
    b2 = admitted(fixture(governance, T + timedelta(days=1)), (b1,))
    assert replay((b2,), as_of=b2.evaluation.as_of).reason is Reason.CHAIN_CONFLICT
    assert replay((replace(b1, fingerprint="bad"), b2), as_of=T).reason is Reason.CHAIN_CONFLICT


def test_boundaries_and_frozen_policy_vocabulary():
    source = Path("app/intelligence/p1_signal_lifecycle.py").read_text()
    tree = ast.parse(source)
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(s.startswith(("app.signals", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime")) for s in imports if s)
    assert not any(isinstance(n, ast.Attribute) and n.attr in ("now", "utcnow", "today") for n in ast.walk(tree))
    from app.intelligence.p1_signal_lifecycle import Transition, View
    forbidden = {"price", "entry", "stop", "target", "quantity", "allocation", "order_id", "gate_authorization"}
    assert not forbidden & {f.name for cls in (Transition, View) for f in fields(cls)}
    assert CONTRACT == "hsi-signal-lifecycle-p1/v1"


def refreshed_assessment(value, assessment):
    refs = tuple(r for r in value.references if r.kind != "ASSESSMENT")
    ref = SourceReference("ASSESSMENT", assessment.assessment_id, assessment.fingerprint, I,
                          value.as_of, value.as_of)
    return replace(value, assessments=(assessment,), references=(*refs, ref))


@pytest.mark.parametrize("code,native", (("BASE_STRUCTURE_BROKEN", "BASE_STRUCTURE_BROKEN"),
                                       ("NO_VALID_WINDOW", "NO_VALID_BASE_WINDOW")))
def test_structural_native_failures_invalidate_without_candidate(governance, code, native):
    from app.strategies.pre_breakout.materialization import PreBreakoutStructuralStatus
    b1 = admitted(fixture(governance))
    value = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    assessment = value.assessments[0]
    changed = replace(assessment, status=PreBreakoutSetupAssessmentStatus.BLOCKED_STRUCTURAL_SETUP,
        technical_inputs=replace(assessment.technical_inputs, bbw_pass=True),
        structural=replace(assessment.structural, status=PreBreakoutStructuralStatus(native)),
        blockers=(PreBreakoutSetupBlocker(PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL, code),))
    b2 = admitted(refreshed_assessment(value, changed), (b1,))
    assert b2.transitions[0].next_state is State.INVALIDATED


@pytest.mark.parametrize("condition", ("data_blocker", "missing_boolean", "future_nested", "unknown_predicate", "sector_only"))
def test_incomplete_or_unmapped_negative_is_not_invalidation(governance, condition):
    b1 = admitted(fixture(governance))
    value = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    a = value.assessments[0]
    if condition == "data_blocker":
        a = replace(a, blockers=(*a.blockers, PreBreakoutSetupBlocker(PreBreakoutSetupBlockerCategory.DATA_BLOCKER, "MISSING")))
    elif condition == "missing_boolean":
        a = replace(a, technical_inputs=replace(a.technical_inputs, rsi_pass=None))
    elif condition == "future_nested":
        a = replace(a, technical_inputs=replace(a.technical_inputs, atr_observation_session=value.as_of + timedelta(seconds=1)))
    elif condition == "unknown_predicate":
        a = replace(a, blockers=(PreBreakoutSetupBlocker(PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL, "ARBITRARY"),))
    else:
        a = replace(a, status=PreBreakoutSetupAssessmentStatus.BLOCKED_SECTOR,
                    blockers=(PreBreakoutSetupBlocker(PreBreakoutSetupBlockerCategory.SECTOR_BLOCKER, "NOT_IN_TOP3_SECTOR"),))
    value = refreshed_assessment(value, a)
    assert evaluate(value, (b1,), Ledger(value)).outcome is Outcome.SOURCE_BLOCKED


def test_negative_policy_change_blocks_and_positive_selection_change_supersedes(governance):
    b1 = admitted(fixture(governance))
    repo, approval, _ = governance
    receipt = PreBreakoutPolicyGovernanceCommandService(repo).select_for_current_stored_scan(
        selection_id="selection:replacement", approval_id=approval.approval_id,
        selected_by="human:fixture", selected_at=T + timedelta(hours=1), effective_from=T + timedelta(hours=1))
    new_governance = (repo, approval, repo.get_prebreakout_policy_selection(receipt.selection_id))
    negative = fixture(new_governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    assert evaluate(negative, (b1,), Ledger(negative)).outcome is Outcome.POLICY_BLOCKED
    positive = fixture(new_governance, T + timedelta(days=1))
    result = admitted(positive, (b1,))
    assert result.transitions[0].next_state is State.SUPERSEDED


def test_negative_needs_no_positive_watch_route(governance):
    b1 = admitted(fixture(governance))
    value = fixture(governance, T + timedelta(days=1), negative="BBW_NOT_COMPRESSED")
    value = replace(value, watch=None, references=tuple(r for r in value.references if r.kind != "WATCH"))
    assert admitted(value, (b1,)).transitions[0].next_state is State.INVALIDATED


def test_no_price_or_ttl_derived_from_watch_status_and_no_false_freshness(governance):
    value = fixture(governance)
    first = admitted(value)
    view = replay((first,), as_of=T + timedelta(hours=1))
    assert view.reason is Reason.REEVALUATION_REQUIRED
    assert view.last_transition.transition_as_of == T
    assert view.expiry == "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"
    assert view.observation_references and view.slot_key == first.slot_key


def test_reader_dependency_cycle_rejected(governance):
    value = fixture(governance)
    class Cycle(Ledger):
        def dependencies(self, reference):
            return (reference,)
    assert evaluate(value, (), Cycle(value)).reason is Reason.EVIDENCE_CONFLICT


def test_contradictory_positive_and_negative_assessments_block(governance):
    value = fixture(governance)
    negative = fixture(governance, negative="BBW_NOT_COMPRESSED")
    mixed = replace(value, assessments=(*value.assessments, *negative.assessments))
    assert evaluate(mixed, (), Ledger(mixed)).reason is Reason.EVIDENCE_CONFLICT


@pytest.mark.parametrize("field", ("setup_state", "setup_policy_routes"))
def test_actual_watch_routing_required(governance, field):
    value = fixture(governance)
    body = {f.name: getattr(value.watch, f.name) for f in fields(value.watch) if f.name != "fingerprint"}
    body[field] = "NO_CURRENT_SETUP" if field == "setup_state" else ()
    body["watch_id"] = ""
    watch = MarketWideWatchRecord.create(**body)
    refs = tuple(r for r in value.references if r.kind != "WATCH")
    value = replace(value, watch=watch, p1_json=None,
                    references=(*refs, SourceReference("WATCH", watch.watch_id, watch.fingerprint, I, T, T)))
    result = evaluate(value, (), Ledger(value))
    if field == "setup_policy_routes":
        # The existing P1B contract rejects a missing routing structure before
        # resolution. Preserve that malformed-source failure, do not patch P1B.
        assert result.outcome is Outcome.CONFLICTED
        assert result.reason is Reason.EVIDENCE_CONFLICT
    else:
        assert result.outcome is Outcome.POLICY_BLOCKED
        assert result.detail == "CURRENT_VALID_SETUP_REQUIRED"


def test_native_p1_reproduction_and_batch_codec_stable(governance):
    from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, snapshot_json, snapshot_json_from
    b = admitted(fixture(governance))
    s = CoreApiSnapshot(b.batch_id, CoreApiSnapshotFamily.P1_SIGNAL_LIFECYCLE_BATCH, "v1", "P1SignalLifecycleBatch", b.fingerprint, T, b)
    restored = snapshot_json_from(snapshot_json(s))
    verify_chain((restored.payload,))
    assert snapshot_json(restored) == snapshot_json(s)
    assert restored.payload.evaluation.p1_json == b.evaluation.p1_json


def test_conflicting_index_and_snapshot_payload_do_not_reconstruct_silently(tmp_path, governance):
    store = SQLiteP1SignalLifecycleRepository(tmp_path / "tampered.sqlite")
    value = fixture(governance)
    store.submit(value, Ledger(value))
    store._connection.execute("UPDATE core_api_snapshots SET fingerprint='tampered'")
    store._connection.commit()
    assert store.read(I, as_of=T).reason is Reason.CHAIN_CONFLICT
    with pytest.raises(LifecycleError):
        store.rebuild_indexes(I)
    assert store.submit(value, Ledger(value)).outcome is Outcome.CONFLICTED
    store.close()


def test_old_cessation_cannot_close_later_relisted_lifetime(governance):
    from app.historical.security_master import HistoricalCorporateAction, CorporateActionKind
    value = fixture(governance)
    b1 = admitted(value)
    action = HistoricalCorporateAction("action:old", I, CorporateActionKind.DELISTING,
        T - timedelta(days=10), None, None, T - timedelta(days=9), None, None,
        None, "SYNTHETIC_OFFICIAL", "v1", T - timedelta(days=8))
    ref = SourceReference("CORPORATE_ACTION", action.action_id, sha256(repr(action).encode()).hexdigest(),
                          I, action.as_of, action.as_of, action.effective_date)
    closing = Evaluation(I, T + timedelta(days=1), (ref,), (), actions=(action,))
    assert evaluate(closing, (b1,), Ledger(closing)).reason is Reason.SECURITY_NOT_ELIGIBLE


def test_corporate_action_cessation_does_not_need_live_governance(governance):
    from app.historical.security_master import HistoricalCorporateAction, CorporateActionKind
    value = fixture(governance)
    first = admitted(value)
    at = T + timedelta(days=1)
    action = HistoricalCorporateAction("action:new", I, CorporateActionKind.MERGER,
        T, None, None, at, None, None, None, "SYNTHETIC_OFFICIAL", "v1", T)
    ref = SourceReference("CORPORATE_ACTION", action.action_id, sha256(repr(action).encode()).hexdigest(),
                          I, action.as_of, action.as_of, action.effective_date)
    closing = Evaluation(I, at, (ref,), (), actions=(action,))
    assert admitted(closing, (first,)).transitions[-1].reason_code == "SECURITY_LIFECYCLE_ENDED"


def test_migration_adds_only_disposable_indexes_in_temporary_database():
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    migration = importlib.import_module("migrations.versions.20260917_11_p1_signal_lifecycle")
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE core_api_snapshots (snapshot_id TEXT PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            tables = sa.inspect(connection).get_table_names()
            assert set(tables) == {"core_api_snapshots", "p1_signal_lifecycle_heads", "p1_signal_lifecycle_batch_index"}
            migration.downgrade()
            assert sa.inspect(connection).get_table_names() == ["core_api_snapshots"]
    engine.dispose()


def test_result_and_query_authority_constants_cannot_be_overridden():
    from app.intelligence.p1_signal_lifecycle import Result, View
    with pytest.raises(LifecycleError):
        Result(Outcome.ACCEPTED, None, None)
    with pytest.raises(LifecycleError):
        View(T, None, (), Outcome.SOURCE_BLOCKED, Reason.REEVALUATION_REQUIRED, execution_status="EXECUTABLE")


def test_historical_query_excludes_future_payloads_even_if_future_is_corrupt(tmp_path, governance):
    store = SQLiteP1SignalLifecycleRepository(tmp_path / "historical.sqlite")
    first, later = fixture(governance), fixture(governance, T + timedelta(days=1))
    b1 = store.submit(first, Ledger(first)).batch
    b2 = store.submit(later, Ledger(later)).batch
    assert store.read(I, as_of=T).last_transition == b1.transitions[0]
    store._connection.execute("UPDATE core_api_snapshots SET fingerprint='tampered' WHERE snapshot_id=?", (b2.batch_id,))
    store._connection.commit()
    assert store.read(I, as_of=T).last_transition == b1.transitions[0]
    assert store.read(I, as_of=later.as_of).reason is Reason.CHAIN_CONFLICT
    store.close()


def test_policy_blocker_precedes_missing_source_timing(governance):
    value = fixture(governance, negative="BBW_NOT_COMPRESSED")
    value = replace(value, approvals=(), selections=(), references=tuple(
        replace(r, evidence_known_at=None) if r.kind == "ASSESSMENT" else r
        for r in value.references))
    result = evaluate(value, (), Ledger(value))
    assert result.outcome is Outcome.POLICY_BLOCKED
    assert result.reason is Reason.STRATEGY_AUTHORITY_UNAVAILABLE


def test_native_conflict_precedes_missing_source_timing(governance):
    value = fixture(governance)
    object.__setattr__(value.watch, "symbol", "TAMPERED")
    value = replace(value, references=tuple(replace(r, evidence_known_at=None) for r in value.references))
    assert evaluate(value, (), Ledger(value)).outcome is Outcome.CONFLICTED


def test_dependency_conflict_precedes_policy_and_source_blockers(governance):
    value = replace(fixture(governance, negative="BBW_NOT_COMPRESSED"), approvals=(), selections=())
    class Conflicted(Ledger):
        def verify(self, reference, *, as_of):
            return False
        def dependencies(self, reference):
            return (reference,)
    result = evaluate(value, (), Conflicted(value))
    assert result.outcome is Outcome.CONFLICTED
    assert result.reason is Reason.EVIDENCE_CONFLICT


@pytest.mark.parametrize("missing", ("identity", "identity_reference", "suspended", "future_identity"))
def test_unavailable_security_does_not_mask_policy_outage(governance, missing):
    value = fixture(governance, negative="BBW_NOT_COMPRESSED")
    if missing == "identity":
        value = replace(value, identities=())
    elif missing == "identity_reference":
        value = replace(value, references=tuple(r for r in value.references if r.kind != "SECURITY_IDENTITY"))
    else:
        identity = replace(value.identities[0], **(
            {"status": HistoricalSecurityStatus.SUSPENDED} if missing == "suspended"
            else {"as_of": T + timedelta(seconds=1)}))
        value = fixture(governance, negative="BBW_NOT_COMPRESSED", security=identity)
    value = replace(value, approvals=(), selections=())
    assert evaluate(value, (), Ledger(value)).outcome is Outcome.POLICY_BLOCKED


def test_missing_source_envelope_cannot_mask_tampered_watch(governance):
    value = fixture(governance)
    value = replace(value, references=tuple(r for r in value.references if r.kind != "SECURITY_IDENTITY"))
    object.__setattr__(value.watch, "symbol", "TAMPERED")
    assert evaluate(value, (), Ledger(value)).outcome is Outcome.CONFLICTED


def test_required_source_as_of_cannot_be_null():
    with pytest.raises(LifecycleError):
        SourceReference("EVIDENCE", "source:missing-as-of", "0" * 64, I, None, T)
