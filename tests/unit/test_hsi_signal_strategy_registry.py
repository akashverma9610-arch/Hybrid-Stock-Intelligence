from __future__ import annotations

import ast
import copy
import inspect
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.hsi_signal_strategy_registry as registry_module
from app.intelligence.hsi_signal import (
    StrategyResolutionReference,
    StrategyResolutionStatus,
)
from app.intelligence.hsi_signal_strategy_registry import (
    HSI_SIGNAL_STRATEGY_REGISTRY_ID,
    HSI_SIGNAL_STRATEGY_REGISTRY_VERSION,
    HSISignalStrategyRegistry,
    HSISignalStrategyRegistryError,
    StrategyRegistryReasonCode,
    StrategyRegistryResolution,
    WatchStrategyRoutingContext,
    serialize_strategy_registry_resolution,
    strategy_registry_resolution_payload,
)
from app.intelligence.opportunity_archetypes import OpportunityArchetype, SetupPolicyRoute
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision,
    PreBreakoutPolicySelection,
    PreBreakoutPolicySelectionContext,
    prebreakout_policy_selection_fingerprint,
)


T = datetime(2026, 9, 2, 10, 30, tzinfo=UTC)


def _fingerprint(value: str) -> str:
    import hashlib
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def _context(
    *,
    archetype: OpportunityArchetype | str = OpportunityArchetype.PRE_BREAKOUT,
    watch_archetypes: tuple[OpportunityArchetype | str, ...] = (OpportunityArchetype.PRE_BREAKOUT,),
    setup_state: str = "CURRENT_VALID_SETUP",
    setup_policy_routes: tuple[tuple[str, str], ...] = ((
        OpportunityArchetype.PRE_BREAKOUT.value,
        SetupPolicyRoute.PRE_BREAKOUT_POLICY.value,
    ),),
    watch_as_of: datetime = T,
) -> WatchStrategyRoutingContext:
    return WatchStrategyRoutingContext(
        canonical_instrument_id="NSE:INE000000001",
        watch_id="market-wide-watch:one",
        watch_fingerprint=_fingerprint("watch-one"),
        watch_as_of=watch_as_of,
        archetype=archetype,
        watch_archetypes=watch_archetypes,
        setup_state=setup_state,
        setup_policy_routes=setup_policy_routes,
    )


def _approved_selected(
    tmp_path, *, reviewed_at: datetime = T - timedelta(minutes=2),
    selected_at: datetime = T - timedelta(minutes=1), effective_from: datetime = T,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    approval = commands.approve(
        approval_id="approval:one",
        policy_id="pre-breakout-policy-v1-draft",
        policy_version="v1-draft",
        decision=PreBreakoutPolicyApprovalDecision.APPROVE,
        reviewer_id="human:owner",
        reviewed_at=reviewed_at,
    )
    selection = commands.select_for_current_stored_scan(
        selection_id="selection:one",
        approval_id=approval.approval_id,
        selected_by="human:owner",
        selected_at=selected_at,
        effective_from=effective_from,
    )
    return repository, approval, selection


def test_registry_identity_and_exact_valid_prebreakout_resolution_are_deterministic(tmp_path):
    repository, approval, selection = _approved_selected(tmp_path)
    registry = HSISignalStrategyRegistry(repository)

    first = registry.resolve(_context())
    second = registry.resolve(_context())

    assert registry.registry_identity == (
        HSI_SIGNAL_STRATEGY_REGISTRY_ID,
        HSI_SIGNAL_STRATEGY_REGISTRY_VERSION,
    )
    assert first == second
    assert first.resolution.status is StrategyResolutionStatus.RESOLVED
    assert first.reason_code is None
    assert first.resolution.approval_id == approval.approval_id
    assert first.resolution.selection_id == selection.selection_id
    assert first.resolution.policy_fingerprint
    assert first.resolution_id.startswith("hsi-signal-strategy-resolution:")


def test_registry_uses_inclusive_approval_and_selection_boundaries_at_watch_as_of(tmp_path):
    repository, approval, selection = _approved_selected(
        tmp_path, reviewed_at=T, selected_at=T, effective_from=T,
    )
    result = HSISignalStrategyRegistry(repository).resolve(_context())

    assert result.resolution.status is StrategyResolutionStatus.RESOLVED
    assert result.resolution.approval_id == approval.approval_id
    assert result.resolution.selection_id == selection.selection_id


def test_registry_excludes_future_selection_and_future_approval_at_watch_as_of(tmp_path):
    repository, _, _ = _approved_selected(tmp_path, effective_from=T + timedelta(minutes=1))
    future_selection = HSISignalStrategyRegistry(repository).resolve(_context())
    assert future_selection.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_NOT_EFFECTIVE_AT_WATCH_AS_OF

    repository, approval, _ = _approved_selected(tmp_path / "approval-future")
    selected = repository.get_prebreakout_policy_selection("selection:one")
    stored = repository.get_prebreakout_policy_approval(approval.approval_id)
    assert selected is not None and stored is not None
    object.__setattr__(stored, "created_at", T + timedelta(seconds=1))
    future_approval = HSISignalStrategyRegistry(_Reader(approvals=(stored,), selections=(selected,))).resolve(_context())
    assert future_approval.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_APPROVAL_NOT_EFFECTIVE_AT_WATCH_AS_OF


def test_registry_fails_closed_for_missing_unapproved_or_inactive_prebreakout_provenance(tmp_path):
    missing = HSISignalStrategyRegistry(SQLiteStrategyGovernanceRepository(tmp_path / "missing.sqlite")).resolve(_context())
    assert missing.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_MISSING

    repository, approval, selection = _approved_selected(tmp_path / "inactive")
    stored = repository.get_prebreakout_policy_approval(approval.approval_id)
    selected = repository.get_prebreakout_policy_selection(selection.selection_id)
    assert stored is not None and selected is not None
    object.__setattr__(stored, "decision", PreBreakoutPolicyApprovalDecision.REJECT)
    object.__setattr__(stored, "fingerprint", "tampered")
    unavailable = HSISignalStrategyRegistry(_Reader(approvals=(stored,), selections=(selected,))).resolve(_context())
    assert unavailable.resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert unavailable.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID
    assert unavailable.resolution.policy_id is None

    rejected_repository = SQLiteStrategyGovernanceRepository(tmp_path / "rejected.sqlite")
    rejected_commands = PreBreakoutPolicyGovernanceCommandService(rejected_repository)
    rejected_receipt = rejected_commands.approve(
        approval_id="approval:rejected",
        policy_id="pre-breakout-policy-v1-draft",
        policy_version="v1-draft",
        decision=PreBreakoutPolicyApprovalDecision.REJECT,
        reviewer_id="human:owner",
        reviewed_at=T - timedelta(minutes=2),
    )
    rejected = rejected_repository.get_prebreakout_policy_approval(rejected_receipt.approval_id)
    assert rejected is not None
    rejected_selection = _selection_for(rejected)
    unapproved = HSISignalStrategyRegistry(_Reader(
        approvals=(rejected,), selections=(rejected_selection,),
    )).resolve(_context())
    assert unapproved.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_UNAPPROVED


def test_registry_requires_current_valid_setup_and_exact_prebreakout_watch_route(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    registry = HSISignalStrategyRegistry(repository)

    no_setup = registry.resolve(_context(setup_state="NOT_EVALUATED"))
    no_route = registry.resolve(_context(setup_policy_routes=((
        OpportunityArchetype.PRE_BREAKOUT.value,
        SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value,
    ),)))
    not_routed = registry.resolve(_context(watch_archetypes=(OpportunityArchetype.EARNINGS_INFLECTION,)))

    assert no_setup.reason_code is StrategyRegistryReasonCode.CURRENT_VALID_SETUP_REQUIRED
    assert no_route.reason_code is StrategyRegistryReasonCode.WATCH_ROUTING_PRECONDITION_MISSING
    assert not_routed.reason_code is StrategyRegistryReasonCode.WATCH_ARCHETYPE_NOT_ROUTED


def test_registry_rejects_provenance_mismatch_and_conflicting_latest_selection(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    selection = repository.get_prebreakout_policy_selection("selection:one")
    assert selection is not None
    object.__setattr__(selection, "policy_fingerprint", _fingerprint("mismatch"))
    approval = repository.get_prebreakout_policy_approval("approval:one")
    assert approval is not None
    mismatch = HSISignalStrategyRegistry(_Reader(approvals=(approval,), selections=(selection,))).resolve(_context())
    assert mismatch.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID

    repository, _, _ = _approved_selected(tmp_path / "ambiguous")
    first = repository.get_prebreakout_policy_selection("selection:one")
    assert first is not None
    conflict = copy.copy(first)
    object.__setattr__(conflict, "selection_id", "selection:two")
    object.__setattr__(conflict, "approval_id", "approval:conflict")
    ambiguous_reader = _Reader(
        approvals=(repository.get_prebreakout_policy_approval("approval:one"),),
        selections=(first, conflict),
    )
    ambiguous = HSISignalStrategyRegistry(ambiguous_reader).resolve(_context())
    assert ambiguous.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_AMBIGUOUS


def test_registry_rejects_tampered_approval_selection_and_policy_fingerprints(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    approval = repository.get_prebreakout_policy_approval("approval:one")
    selection = repository.get_prebreakout_policy_selection("selection:one")
    assert approval is not None and selection is not None

    for attribute, value in (
        ("fingerprint", _fingerprint("approval-tampered")),
        ("approved_policy_fingerprint", _fingerprint("policy-tampered")),
    ):
        tampered = copy.copy(approval)
        object.__setattr__(tampered, attribute, value)
        result = HSISignalStrategyRegistry(_Reader(
            approvals=(tampered,), selections=(selection,),
        )).resolve(_context())
        assert result.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID

    tampered_selection = copy.copy(selection)
    object.__setattr__(tampered_selection, "fingerprint", _fingerprint("selection-tampered"))
    result = HSISignalStrategyRegistry(_Reader(
        approvals=(approval,), selections=(tampered_selection,),
    )).resolve(_context())
    assert result.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_PROVENANCE_INVALID


def test_registry_is_input_order_independent_and_rejects_duplicate_selection_ids(tmp_path):
    repository, _, _ = _approved_selected(
        tmp_path, reviewed_at=T - timedelta(minutes=5),
        selected_at=T - timedelta(minutes=4), effective_from=T - timedelta(minutes=4),
    )
    approval = repository.get_prebreakout_policy_approval("approval:one")
    earlier = repository.get_prebreakout_policy_selection("selection:one")
    assert approval is not None and earlier is not None
    later = _selection_for(
        approval, selection_id="selection:later", selected_at=T - timedelta(minutes=1),
        effective_from=T - timedelta(minutes=1),
    )

    forward = HSISignalStrategyRegistry(_Reader(
        approvals=(approval,), selections=(earlier, later),
    )).resolve(_context())
    reverse = HSISignalStrategyRegistry(_Reader(
        approvals=(approval,), selections=(later, earlier),
    )).resolve(_context())
    assert forward == reverse
    assert forward.resolution.selection_id == "selection:later"

    duplicate = HSISignalStrategyRegistry(_Reader(
        approvals=(approval,), selections=(earlier, earlier),
    )).resolve(_context())
    assert duplicate.reason_code is StrategyRegistryReasonCode.PREBREAKOUT_POLICY_SELECTION_DUPLICATE


def test_resolution_contract_rejects_contradictory_reason_and_provenance_fields(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    resolved = HSISignalStrategyRegistry(repository).resolve(_context())
    values = dict(
        canonical_instrument_id=resolved.canonical_instrument_id,
        watch_id=resolved.watch_id,
        watch_fingerprint=resolved.watch_fingerprint,
        watch_as_of=resolved.watch_as_of,
        archetype=resolved.archetype,
    )
    with pytest.raises(HSISignalStrategyRegistryError, match="RESOLVED_REASON_FORBIDDEN"):
        StrategyRegistryResolution(
            **values, resolution=resolved.resolution,
            reason_code=StrategyRegistryReasonCode.UNKNOWN_ARCHETYPE,
        )
    with pytest.raises(HSISignalStrategyRegistryError, match="UNAVAILABLE_REASON_REQUIRED"):
        StrategyRegistryResolution(
            **values,
            resolution=StrategyResolutionReference(StrategyResolutionStatus.STRATEGY_UNAVAILABLE),
            reason_code=None,
        )

    object.__setattr__(resolved, "reason_code", StrategyRegistryReasonCode.UNKNOWN_ARCHETYPE)
    with pytest.raises(HSISignalStrategyRegistryError, match="RESOLVED_REASON_FORBIDDEN"):
        resolved.verify()


def test_registry_revalidates_tampered_context_and_resolution_without_repair(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    registry = HSISignalStrategyRegistry(repository)
    context = _context()
    object.__setattr__(context, "watch_as_of", datetime(2026, 9, 2, 10, 30))
    with pytest.raises(HSISignalStrategyRegistryError, match="WATCH_AS_OF_INVALID"):
        registry.resolve(context)

    resolution = registry.resolve(_context())
    object.__setattr__(resolution, "watch_as_of", datetime(2026, 9, 2, 10, 30))
    with pytest.raises(HSISignalStrategyRegistryError, match="RESOLUTION_WATCH_AS_OF_INVALID"):
        resolution.verify()


@pytest.mark.parametrize("archetype", tuple(
    value for value in OpportunityArchetype if value is not OpportunityArchetype.PRE_BREAKOUT
))
def test_every_other_current_archetype_fails_closed(tmp_path, archetype):
    registry = HSISignalStrategyRegistry(SQLiteStrategyGovernanceRepository(tmp_path / f"{archetype.value}.sqlite"))
    result = registry.resolve(_context(archetype=archetype, watch_archetypes=(archetype,)))
    assert result.resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is StrategyRegistryReasonCode.STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE


def test_unknown_archetype_is_safe_and_unavailable(tmp_path):
    registry = HSISignalStrategyRegistry(SQLiteStrategyGovernanceRepository(tmp_path / "unknown.sqlite"))
    result = registry.resolve(_context(archetype="UNKNOWN_ARCHETYPE", watch_archetypes=("UNKNOWN_ARCHETYPE",)))
    assert result.resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert result.reason_code is StrategyRegistryReasonCode.UNKNOWN_ARCHETYPE


def test_registry_resolution_serialization_is_stable_and_pit_timezone_normalized(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    first = HSISignalStrategyRegistry(repository).resolve(_context())
    equivalent = HSISignalStrategyRegistry(repository).resolve(_context(
        watch_as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))),
    ))

    assert first.resolution_id == equivalent.resolution_id
    assert serialize_strategy_registry_resolution(first) == serialize_strategy_registry_resolution(equivalent)
    assert json.loads(serialize_strategy_registry_resolution(first)) == strategy_registry_resolution_payload(first)
    assert strategy_registry_resolution_payload(first)["watch_as_of"] == T.isoformat()


def test_registry_is_read_only_and_has_no_forbidden_dependencies_or_write_methods(tmp_path):
    repository, _, _ = _approved_selected(tmp_path)
    before = repository._connection.execute(
        "SELECT COUNT(*) FROM prebreakout_policy_approvals"
    ).fetchone()[0], repository._connection.execute(
        "SELECT COUNT(*) FROM prebreakout_policy_selections"
    ).fetchone()[0]
    HSISignalStrategyRegistry(repository).resolve(_context())
    after = repository._connection.execute(
        "SELECT COUNT(*) FROM prebreakout_policy_approvals"
    ).fetchone()[0], repository._connection.execute(
        "SELECT COUNT(*) FROM prebreakout_policy_selections"
    ).fetchone()[0]
    assert before == after

    source = Path(inspect.getsourcefile(registry_module)).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    forbidden = (
        "app.signals", "app.broker", "app.orders", "app.portfolio",
        "app.api", "app.ui", "app.news",
    )
    assert not any(name.startswith(forbidden) for name in imports)
    assert ".save_" not in source and ".execute(" not in source and "datetime.now" not in source


class _Reader:
    def __init__(self, *, approvals, selections):
        self._approvals = tuple(value for value in approvals if value is not None)
        self._selections = tuple(selections)

    def get_prebreakout_policy_approval(self, approval_id):
        return next((value for value in self._approvals if value.approval_id == approval_id), None)

    def list_prebreakout_policy_approvals(self, policy_id=None):
        return tuple(value for value in self._approvals if policy_id is None or value.policy_id == policy_id)

    def list_prebreakout_policy_selections(self, policy_id=None, context=None):
        return tuple(value for value in self._selections if (
            (policy_id is None or value.policy_id == policy_id)
            and (context is None or value.selection_context is context)
        ))


def _selection_for(
    approval, *, selection_id: str = "selection:rejected",
    selected_at: datetime = T - timedelta(minutes=1),
    effective_from: datetime = T - timedelta(minutes=1),
):
    values = {
        "selection_id": selection_id,
        "approval_id": approval.approval_id,
        "policy_id": approval.policy_id,
        "policy_version": approval.policy_version,
        "policy_fingerprint": approval.approved_policy_fingerprint,
        "selection_context": PreBreakoutPolicySelectionContext.CURRENT_STORED_SCAN,
        "selected_by": "human:owner",
        "selected_at": selected_at,
        "effective_from": effective_from,
        "warnings": (),
    }
    return PreBreakoutPolicySelection(
        **values,
        fingerprint=prebreakout_policy_selection_fingerprint(**{
            key: value.value if hasattr(value, "value") else value.isoformat()
            if isinstance(value, datetime) else value
            for key, value in values.items()
        }),
    )
