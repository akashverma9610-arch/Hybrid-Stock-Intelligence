from __future__ import annotations

import ast
import hashlib
import inspect
import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.hsi_signal_projection as projection_module
from app.intelligence.hsi_signal import (
    HSISignalActionability,
    HSISignalExecutionStatus,
    PortfolioRelevance,
    StrategyResolutionReference,
    StrategyResolutionStatus,
    serialize_hsi_signal,
)
from app.intelligence.hsi_signal_projection import (
    HSISignalProjectionError,
    project_watch_to_hsi_signal,
)
from app.intelligence.hsi_signal_strategy_registry import (
    HSISignalStrategyRegistry,
    StrategyRegistryReasonCode,
    StrategyRegistryResolution,
)
from app.intelligence.market_wide_watch import (
    MarketWideWatchRecord,
    WatchEvidenceReference,
    WatchStatus,
)
from app.intelligence.opportunity_archetypes import (
    ExternalEvidenceReference,
    OpportunityArchetype,
    SetupPolicyRoute,
)
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.pre_breakout.governance_commands import PreBreakoutPolicyGovernanceCommandService
from app.strategies.pre_breakout.policy import (
    PreBreakoutPolicyApprovalDecision,
)


T = datetime(2026, 9, 2, 10, 30, tzinfo=UTC)


def _fingerprint(value: str) -> str:
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def _watch(
    *,
    as_of: datetime = T,
    archetypes: tuple[OpportunityArchetype, ...] = (OpportunityArchetype.PRE_BREAKOUT,),
    setup_state: str = "CURRENT_VALID_SETUP",
    routes: tuple[tuple[str, str], ...] = ((
        OpportunityArchetype.PRE_BREAKOUT.value,
        SetupPolicyRoute.PRE_BREAKOUT_POLICY.value,
    ),),
    evidence: tuple[WatchEvidenceReference, ...] | None = None,
    external: tuple[ExternalEvidenceReference, ...] = (),
    last_evidence_as_of: datetime | None = T,
) -> MarketWideWatchRecord:
    return MarketWideWatchRecord.create(
        watch_id="", canonical_instrument_id="NSE:INE000000001", symbol="ALPHA",
        company_name="Alpha Limited", watch_as_of=as_of,
        classifications=(), status=WatchStatus.WATCH_ACTIVE,
        evidence_sufficiency="READY",
        evidence_references=evidence or (WatchEvidenceReference(
            rule_id="24", diagnostic_result="ACCELERATING", artifact_id="diagnostic:24",
            artifact_fingerprint=_fingerprint("diagnostic:24"),
        ),),
        sector=None, sector_rank=None, top3_eligible=False, decision_score_id=None,
        decision_score_status="UNSCORED", decision_score_value=None,
        setup_state=setup_state, six_gates_state="NOT_EVALUATED", reliability_state="AVAILABLE",
        blocker_codes=("SOURCE_BLOCKER",), last_evidence_as_of=last_evidence_as_of,
        policy_identity="market-wide-quality-inflection-watch/v1:opportunity-archetype-routing-policy/v1",
        archetypes=archetypes, external_evidence_references=external,
        setup_policy_routes=routes, lifecycle_flags=("DISCOVERED", "WATCH"),
    )


def _approved_registry(tmp_path, *, effective_from: datetime = T) -> HSISignalStrategyRegistry:
    tmp_path.mkdir(parents=True, exist_ok=True)
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "governance.sqlite")
    commands = PreBreakoutPolicyGovernanceCommandService(repository)
    approval = commands.approve(
        approval_id="approval:one", policy_id="pre-breakout-policy-v1-draft",
        policy_version="v1-draft", decision=PreBreakoutPolicyApprovalDecision.APPROVE,
        reviewer_id="human:owner", reviewed_at=T - timedelta(minutes=2),
    )
    commands.select_for_current_stored_scan(
        selection_id="selection:one", approval_id=approval.approval_id,
        selected_by="human:owner", selected_at=T - timedelta(minutes=1),
        effective_from=effective_from,
    )
    return HSISignalStrategyRegistry(repository)


def test_projector_projects_valid_prebreakout_provenance_without_new_intelligence(tmp_path):
    signal = project_watch_to_hsi_signal(
        watch=_watch(), archetype=OpportunityArchetype.PRE_BREAKOUT,
        registry=_approved_registry(tmp_path),
    )

    assert signal.strategy_resolution.status is StrategyResolutionStatus.RESOLVED
    assert signal.diagnostic_lineage[0].diagnostic_result_id == "ACCELERATING"
    assert signal.detected_at is None
    assert signal.actionability is HSISignalActionability.WATCH_ONLY
    assert signal.execution_status is HSISignalExecutionStatus.NON_EXECUTABLE
    assert signal.portfolio_relevance is PortfolioRelevance.NOT_EVALUATED
    assert signal.blocker_codes == ("SOURCE_BLOCKER",)
    assert signal.source_watch_status == WatchStatus.WATCH_ACTIVE.value
    assert signal.source_lifecycle_flags == ("DISCOVERED", "WATCH")


@pytest.mark.parametrize("archetype", tuple(
    value for value in OpportunityArchetype if value is not OpportunityArchetype.PRE_BREAKOUT
))
def test_projector_emits_valid_fail_closed_signal_for_every_unsupported_archetype(tmp_path, archetype):
    watch = _watch(
        archetypes=(archetype,),
        routes=((archetype.value, SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value),),
        setup_state="NOT_EVALUATED",
    )
    signal = project_watch_to_hsi_signal(
        watch=watch, archetype=archetype,
        registry=HSISignalStrategyRegistry(SQLiteStrategyGovernanceRepository(tmp_path / f"{archetype.value}.sqlite")),
    )

    assert signal.strategy_resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert "STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE" in signal.blocker_codes


def test_projector_preserves_fail_closed_missing_setup_route_and_future_policy(tmp_path):
    no_route = _watch(routes=((
        OpportunityArchetype.PRE_BREAKOUT.value,
        SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value,
    ),))
    no_route_signal = project_watch_to_hsi_signal(
        watch=no_route, archetype=OpportunityArchetype.PRE_BREAKOUT,
        registry=_approved_registry(tmp_path / "route"),
    )
    assert "WATCH_ROUTING_PRECONDITION_MISSING" in no_route_signal.blocker_codes

    future_policy_signal = project_watch_to_hsi_signal(
        watch=_watch(), archetype=OpportunityArchetype.PRE_BREAKOUT,
        registry=_approved_registry(tmp_path / "future", effective_from=T + timedelta(seconds=1)),
    )
    assert future_policy_signal.strategy_resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE
    assert "PREBREAKOUT_POLICY_SELECTION_NOT_EFFECTIVE_AT_WATCH_AS_OF" in future_policy_signal.blocker_codes


def test_projector_rejects_tampered_watch_future_evidence_and_unrouted_archetype(tmp_path):
    tampered = _watch()
    object.__setattr__(tampered, "fingerprint", _fingerprint("tampered-watch"))
    with pytest.raises(HSISignalProjectionError, match="WATCH_INVALID"):
        project_watch_to_hsi_signal(
            watch=tampered, archetype=OpportunityArchetype.PRE_BREAKOUT,
            registry=_approved_registry(tmp_path / "tampered"),
        )

    with pytest.raises(HSISignalProjectionError, match="FUTURE_EVIDENCE_EXCLUDED"):
        project_watch_to_hsi_signal(
            watch=_watch(last_evidence_as_of=T + timedelta(seconds=1)),
            archetype=OpportunityArchetype.PRE_BREAKOUT,
            registry=_approved_registry(tmp_path / "future-evidence"),
        )

    with pytest.raises(HSISignalProjectionError, match="ARCHETYPE_NOT_ROUTED"):
        project_watch_to_hsi_signal(
            watch=_watch(), archetype=OpportunityArchetype.CATALYST_WATCH,
            registry=_approved_registry(tmp_path / "unrouted"),
        )


def test_projector_rejects_duplicate_or_conflicting_source_lineage(tmp_path):
    one = WatchEvidenceReference("24", "ACCELERATING", "diagnostic:24", _fingerprint("one"))
    duplicate = _watch(evidence=(one, one))
    with pytest.raises(HSISignalProjectionError, match="SOURCE_LINEAGE_INVALID"):
        project_watch_to_hsi_signal(
            watch=duplicate, archetype=OpportunityArchetype.PRE_BREAKOUT,
            registry=_approved_registry(tmp_path / "duplicate"),
        )

    conflict = _watch(evidence=(
        one,
        WatchEvidenceReference("24", "ACCELERATING", "diagnostic:other", _fingerprint("other")),
    ))
    with pytest.raises(HSISignalProjectionError, match="SOURCE_LINEAGE_INVALID"):
        project_watch_to_hsi_signal(
            watch=conflict, archetype=OpportunityArchetype.PRE_BREAKOUT,
            registry=_approved_registry(tmp_path / "conflict"),
        )


def test_projector_rejects_registry_provenance_for_a_different_watch(tmp_path, monkeypatch):
    registry = _approved_registry(tmp_path)

    def mismatched(context):
        return StrategyRegistryResolution(
            canonical_instrument_id=context.canonical_instrument_id,
            watch_id="market-wide-watch:other",
            watch_fingerprint=context.watch_fingerprint,
            watch_as_of=context.watch_as_of,
            archetype=context.archetype.value,
            resolution=StrategyResolutionReference(StrategyResolutionStatus.STRATEGY_UNAVAILABLE),
            reason_code=StrategyRegistryReasonCode.UNKNOWN_ARCHETYPE,
        )

    monkeypatch.setattr(registry, "resolve", mismatched)
    with pytest.raises(HSISignalProjectionError, match="REGISTRY_RESOLUTION_MISMATCH"):
        project_watch_to_hsi_signal(
            watch=_watch(), archetype=OpportunityArchetype.PRE_BREAKOUT, registry=registry,
        )


def test_projector_is_order_and_timezone_independent_and_serializes_stably(tmp_path):
    evidence = (
        WatchEvidenceReference("24", "ACCELERATING", "diagnostic:24", _fingerprint("24")),
        WatchEvidenceReference("16", "ACCELERATING", "diagnostic:16", _fingerprint("16")),
    )
    external = (
        ExternalEvidenceReference("event:two", "evidence:two", "RESULT", "HIGH", None, "EXCHANGE", "DIRECT", "VERIFIED", _fingerprint("event:two")),
        ExternalEvidenceReference("event:one", "evidence:one", "RESULT", "HIGH", None, "EXCHANGE", "DIRECT", "VERIFIED", _fingerprint("event:one")),
    )
    first = project_watch_to_hsi_signal(
        watch=_watch(evidence=evidence, external=external),
        archetype=OpportunityArchetype.PRE_BREAKOUT, registry=_approved_registry(tmp_path / "first"),
    )
    equivalent = project_watch_to_hsi_signal(
        watch=_watch(
            as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))),
            evidence=tuple(reversed(evidence)), external=tuple(reversed(external)),
            last_evidence_as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))),
        ),
        archetype=OpportunityArchetype.PRE_BREAKOUT, registry=_approved_registry(tmp_path / "second"),
    )

    assert first.signal_id == equivalent.signal_id
    assert first.fingerprint == equivalent.fingerprint
    assert serialize_hsi_signal(first) == serialize_hsi_signal(equivalent)
    assert json.loads(serialize_hsi_signal(first))["watch_as_of"] == T.isoformat()


def test_projector_canonicalizes_the_source_and_registry_blocker_union(tmp_path):
    archetype = OpportunityArchetype.CATALYST_WATCH
    signal = project_watch_to_hsi_signal(
        watch=_watch(
            archetypes=(archetype,), setup_state="NOT_EVALUATED",
            routes=((archetype.value, SetupPolicyRoute.SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE.value),),
        ),
        archetype=archetype,
        registry=HSISignalStrategyRegistry(SQLiteStrategyGovernanceRepository(tmp_path / "union.sqlite")),
    )
    assert signal.blocker_codes == (
        "SOURCE_BLOCKER",
        "STRATEGY_POLICY_UNAVAILABLE_FOR_ARCHETYPE",
    )


def test_projector_has_no_forbidden_dependencies_or_write_side_effect(tmp_path):
    repository = SQLiteStrategyGovernanceRepository(tmp_path / "read-only.sqlite")
    before = repository._connection.execute("SELECT COUNT(*) FROM prebreakout_policy_approvals").fetchone()[0]
    signal = project_watch_to_hsi_signal(
        watch=_watch(), archetype=OpportunityArchetype.PRE_BREAKOUT,
        registry=HSISignalStrategyRegistry(repository),
    )
    after = repository._connection.execute("SELECT COUNT(*) FROM prebreakout_policy_approvals").fetchone()[0]
    assert before == after and signal.strategy_resolution.status is StrategyResolutionStatus.STRATEGY_UNAVAILABLE

    source = Path(inspect.getsourcefile(projection_module)).read_text(encoding="utf-8")
    imports = {
        alias.name for node in ast.walk(ast.parse(source))
        if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names
    }
    forbidden = ("app.signals", "app.broker", "app.orders", "app.portfolio", "app.storage", "app.api", "app.ui")
    assert not any(name.startswith(forbidden) for name in imports)
    assert "datetime.now" not in source and ".save_" not in source and ".execute(" not in source


def test_projected_signal_has_no_forbidden_trade_or_execution_fields(tmp_path):
    signal = project_watch_to_hsi_signal(
        watch=_watch(), archetype=OpportunityArchetype.PRE_BREAKOUT,
        registry=_approved_registry(tmp_path),
    )
    payload = json.loads(serialize_hsi_signal(signal))
    forbidden = ("entry", "stop", "target", "price", "quantity", "sizing", "allocation", "order", "broker", "buy", "sell", "rotate")
    assert not any(token in key.lower() for key in payload for token in forbidden)
    assert payload["portfolio_relevance"] == PortfolioRelevance.NOT_EVALUATED.value
