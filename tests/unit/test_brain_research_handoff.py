from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.research.handoff import (
    BrainResearchHandoff,
    BrainResearchHandoffError,
    BrainResearchHandoffStatus,
    BrainResearchOriginType,
    BrainResearchStage,
    create_brain_research_handoff,
    brain_research_handoff_fingerprint_values,
)
from app.research.handoff_serialization import handoff_from, handoff_to
from app.research.intake import (
    BrainResearchIntakeError,
    BrainResearchIntakeService,
    BrainResearchIntakeContextKind,
    create_brain_research_intake,
)
from app.services.audit_reconstruction_service import AuditReconstructionError, AuditReconstructionService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.strategies.common.models import CandidateStatus, StrategyFamily
from app.strategies.pre_breakout.candidate_assembly import (
    PreBreakoutCandidate,
    PreBreakoutCandidateAssemblyError,
    PreBreakoutCandidateResearchStatus,
    PreBreakoutCandidateRole,
    prebreakout_candidate_fingerprint,
    prebreakout_candidate_fingerprint_values,
)
from app.strategies.pre_breakout.research_handoff import (
    candidate_to_brain_research_handoff,
    validate_prebreakout_handoff_origin,
)


T = datetime(2026, 8, 28, 12, tzinfo=UTC)


def _candidate(*, as_of: datetime = T, policy_fingerprint: str = "policy-fingerprint") -> PreBreakoutCandidate:
    values = dict(
        candidate_id=f"prebreakout-candidate:{as_of.isoformat()}:{policy_fingerprint}",
        candidate_role=PreBreakoutCandidateRole.OPPORTUNITY_CANDIDATE,
        strategy_family=StrategyFamily.PRE_BREAKOUT,
        candidate_status=CandidateStatus.CANDIDATE_GENERATED,
        research_status=PreBreakoutCandidateResearchStatus.RESEARCH_PENDING,
        brain_evaluation_required=True,
        assessment_fingerprint="assessment-fingerprint",
        instrument_id="NSE:HANDOFF",
        evaluation_as_of=as_of,
        evaluation_session=as_of,
        policy_id="pre-breakout-policy-v1",
        policy_version="v1.3-draft",
        policy_fingerprint=policy_fingerprint,
        selection_id="selection-id",
        selection_fingerprint="selection-fingerprint",
        sector="Metals",
        sector_rotation_as_of=as_of,
        top3_sector_membership=True,
        bbw_percentile=Decimal("8"), bbw_pass=True,
        current_atr14=Decimal("1"), atr_contraction_pass=True,
        current_volume=499_999, volume_dry_up_pass=True,
        official_delivery_pct=Decimal("61"), delivery_pass=True,
        high_252=Decimal("500"), distance_below_high_pct=Decimal("6"), distance_from_high_pass=True,
        rsi14=Decimal("60"), rsi_pass=True,
        base_start=as_of - timedelta(days=20), base_end=as_of, base_duration=20, base_top=Decimal("500"),
        resistance=Decimal("500"), breakout_confirmation_trigger=Decimal("500"), structural_support=Decimal("450"),
        final_structural_stop=Decimal("449.95"), measured_move_target=Decimal("550"),
        tick_record_id="tick-id", tick_size=Decimal("0.05"), entry_reference_price=Decimal("470"),
        maximum_acceptable_entry_price=Decimal("474.9625"), maximum_executable_entry_price=Decimal("474.95"),
        reference_reward_risk=Decimal("80") / Decimal("20.05"), actual_execution_price=None,
        actual_execution_status="NOT_EVALUATED_AT_SCAN", formation_blockers=(), warnings=(),
    )
    return PreBreakoutCandidate(**values, fingerprint=prebreakout_candidate_fingerprint_values(values))


def test_governed_prebreakout_candidate_creates_generic_pending_shared_brain_handoff() -> None:
    candidate = _candidate()
    handoff = candidate_to_brain_research_handoff(candidate)
    assert handoff.canonical_instrument_id == candidate.instrument_id
    assert handoff.origin_type is BrainResearchOriginType.PRE_BREAKOUT_OPPORTUNITY
    assert handoff.origin_artifact_id == candidate.candidate_id
    assert handoff.origin_artifact_fingerprint == candidate.fingerprint
    assert handoff.evaluation_as_of == handoff.evaluation_session == T
    assert handoff.requested_brain_stage is BrainResearchStage.RESEARCH_DIAGNOSTIC
    assert handoff.research_status is BrainResearchHandoffStatus.PENDING_RESEARCH
    assert handoff.created_from_governed_artifact is True
    assert ("policy_fingerprint", candidate.policy_fingerprint) in handoff.origin_lineage
    assert ("selection_fingerprint", candidate.selection_fingerprint) in handoff.origin_lineage
    assert ("maximum_executable_entry_price", "474.95") in handoff.reference_facts


def test_handoff_identity_is_deterministic_and_changes_with_candidate_lineage_or_as_of() -> None:
    candidate = _candidate()
    first, second = candidate_to_brain_research_handoff(candidate), candidate_to_brain_research_handoff(candidate)
    changed_policy = candidate_to_brain_research_handoff(_candidate(policy_fingerprint="different-policy"))
    changed_time = candidate_to_brain_research_handoff(_candidate(as_of=T + timedelta(seconds=1)))
    assert (first.handoff_id, first.fingerprint) == (second.handoff_id, second.fingerprint)
    assert changed_policy.handoff_id != first.handoff_id
    assert changed_time.handoff_id != first.handoff_id


def test_handoff_is_frozen_and_semantic_tampering_fails_closed() -> None:
    handoff = candidate_to_brain_research_handoff(_candidate())
    with pytest.raises(FrozenInstanceError):
        handoff.sector = "Realty"  # type: ignore[misc]
    with pytest.raises(BrainResearchHandoffError, match="FINGERPRINT_MISMATCH"):
        replace(handoff, sector="Realty")


def test_malformed_or_execution_like_candidate_is_rejected_before_generic_handoff_creation() -> None:
    candidate = _candidate()
    object.__setattr__(candidate, "actual_execution_price", Decimal("471"))
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="CANDIDATE_FINGERPRINT_MISMATCH"):
        candidate_to_brain_research_handoff(candidate)
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="CANDIDATE_REQUIRED"):
        candidate_to_brain_research_handoff(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("candidate_status", CandidateStatus.PARTIAL),
        ("research_status", "CONSUMED_BY_BRAIN"),
        ("brain_evaluation_required", False),
        ("formation_blockers", ("UNEXPECTED",)),
        ("actual_execution_status", "EXECUTION_READY"),
    ),
)
def test_only_pending_governed_opportunity_candidate_can_form_handoff(field, value) -> None:
    candidate = _candidate()
    object.__setattr__(candidate, field, value)
    object.__setattr__(candidate, "fingerprint", prebreakout_candidate_fingerprint(candidate))
    with pytest.raises(PreBreakoutCandidateAssemblyError, match="CANDIDATE_INCONSISTENT"):
        candidate_to_brain_research_handoff(candidate)


def test_generic_contract_supports_future_non_prebreakout_origins_without_schema_change() -> None:
    handoff = create_brain_research_handoff(
        canonical_instrument_id="NSE:GENERIC", origin_type=BrainResearchOriginType.MANUAL_DEEP_ANALYSIS,
        origin_artifact_id="manual-request-1", origin_artifact_fingerprint="manual-fingerprint",
        evaluation_as_of=T, evaluation_session=None, created_from_governed_artifact=False,
    )
    assert handoff.origin_type is BrainResearchOriginType.MANUAL_DEEP_ANALYSIS
    assert handoff.setup_family is None and handoff.reference_facts == ()


def test_handoff_has_no_score_ranking_execution_or_trade_artifacts_and_generic_model_has_no_prebreakout_import() -> None:
    handoff = candidate_to_brain_research_handoff(_candidate())
    assert not any(hasattr(handoff, name) for name in (
        "score", "ranking", "decision_score", "confidence", "six_gates", "signal", "order", "paper_trade", "position",
    ))
    source = (Path(__file__).parents[2] / "app" / "research" / "handoff.py").read_text(encoding="utf-8")
    assert "strategies.pre_breakout" not in source and "PreBreakout" not in source
    adapter = (Path(__file__).parents[2] / "app" / "strategies" / "pre_breakout" / "research_handoff.py").read_text(encoding="utf-8")
    assert "materialize(" not in adapter and "run_prebreakout_research" not in adapter


def _changed_handoff(value: BrainResearchHandoff, **changes: object) -> BrainResearchHandoff:
    values = {field: getattr(value, field) for field in value.__dataclass_fields__ if field != "fingerprint"}
    values.update(changes)
    return BrainResearchHandoff(**values, fingerprint=brain_research_handoff_fingerprint_values(values))


def _manual_handoff(*, instrument: str = "NSE:GENERIC", as_of: datetime = T):
    return create_brain_research_handoff(
        canonical_instrument_id=instrument,
        origin_type=BrainResearchOriginType.MANUAL_DEEP_ANALYSIS,
        origin_artifact_id=f"manual:{instrument}:{as_of.isoformat()}",
        origin_artifact_fingerprint="manual-fingerprint",
        evaluation_as_of=as_of,
        evaluation_session=None,
        created_from_governed_artifact=False,
        reference_facts=(("observed_price", "123.45"),),
        warnings=("MANUAL_RESEARCH_REQUEST",),
    )


def test_canonical_handoff_serialization_round_trip_preserves_immutable_values() -> None:
    value = candidate_to_brain_research_handoff(_candidate())
    payload = handoff_to(value)
    rebuilt = handoff_from(payload)
    assert rebuilt == value
    assert type(rebuilt.origin_type) is BrainResearchOriginType
    assert type(rebuilt.requested_brain_stage) is BrainResearchStage
    assert type(rebuilt.research_status) is BrainResearchHandoffStatus
    assert rebuilt.evaluation_as_of.tzinfo is not None
    assert rebuilt.origin_lineage == value.origin_lineage and rebuilt.reference_facts == value.reference_facts


def test_sqlite_handoff_save_get_missing_and_reopen_are_immutable_and_exact(tmp_path) -> None:
    path = tmp_path / "handoffs.db"
    value = candidate_to_brain_research_handoff(_candidate())
    first = SQLiteStrategyGovernanceRepository(path)
    first.save_brain_research_handoff(value)
    assert first.get_brain_research_handoff(value.handoff_id) == value
    assert first.get_brain_research_handoff("missing") is None
    assert first._connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='brain_research_handoffs'").fetchone()
    first.close()
    second = SQLiteStrategyGovernanceRepository(path)
    assert second.get_brain_research_handoff(value.handoff_id) == value


def test_handoff_list_is_deterministic_filters_exactly_and_supports_future_origins(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    later = _manual_handoff(as_of=T + timedelta(days=1))
    candidate = candidate_to_brain_research_handoff(_candidate())
    other = _manual_handoff(instrument="NSE:OTHER", as_of=T - timedelta(days=1))
    for value in (later, candidate, other):
        repo.save_brain_research_handoff(value)
    assert repo.list_brain_research_handoffs() == (other, candidate, later)
    assert repo.list_brain_research_handoffs(canonical_instrument_id="NSE:HANDOFF") == (candidate,)
    assert repo.list_brain_research_handoffs(origin_type=BrainResearchOriginType.MANUAL_DEEP_ANALYSIS) == (other, later)
    assert repo.list_brain_research_handoffs(requested_brain_stage=BrainResearchStage.RESEARCH_DIAGNOSTIC) == (other, candidate, later)
    assert repo.list_brain_research_handoffs(status=BrainResearchHandoffStatus.PENDING_RESEARCH) == (other, candidate, later)
    assert repo.list_brain_research_handoffs(
        canonical_instrument_id="NSE:GENERIC", origin_type=BrainResearchOriginType.MANUAL_DEEP_ANALYSIS,
        requested_brain_stage=BrainResearchStage.RESEARCH_DIAGNOSTIC, status=BrainResearchHandoffStatus.PENDING_RESEARCH,
    ) == (later,)
    with pytest.raises(ValueError, match="ORIGIN_TYPE_INVALID"):
        repo.list_brain_research_handoffs(origin_type="PRE_BREAKOUT_OPPORTUNITY")  # type: ignore[arg-type]


def test_handoff_save_is_insert_only_for_exact_and_conflicting_same_ids(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    value = candidate_to_brain_research_handoff(_candidate())
    repo.save_brain_research_handoff(value)
    with pytest.raises(ValueError, match="immutable"):
        repo.save_brain_research_handoff(value)
    conflicting = _changed_handoff(value, sector="Realty")
    with pytest.raises(ValueError, match="immutable"):
        repo.save_brain_research_handoff(conflicting)
    assert repo.get_brain_research_handoff(value.handoff_id) == value


@pytest.mark.parametrize(
    ("path", "replacement", "expected"),
    (
        (("canonical_instrument_id",), "NSE:TAMPERED", "FINGERPRINT_MISMATCH"),
        (("origin_artifact_fingerprint",), "tampered-origin", "FINGERPRINT_MISMATCH"),
        (("origin_lineage", 0, 1), "tampered-policy-lineage", "FINGERPRINT_MISMATCH"),
        (("evaluation_as_of",), (T + timedelta(days=1)).isoformat(), "FINGERPRINT_MISMATCH"),
        (("reference_facts", 0, 1), "999.99", "FINGERPRINT_MISMATCH"),
        (("requested_brain_stage",), "CONSUMED", "SERIALIZATION_INVALID"),
        (("research_status",), "COMPLETED", "SERIALIZATION_INVALID"),
    ),
)
def test_tampered_persisted_handoff_get_and_list_fail_closed(tmp_path, path, replacement, expected) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    value = candidate_to_brain_research_handoff(_candidate())
    repo.save_brain_research_handoff(value)
    payload = json.loads(repo._connection.execute(
        "SELECT payload_json FROM brain_research_handoffs WHERE id=?", (value.handoff_id,)
    ).fetchone()["payload_json"])
    target = payload
    for step in path[:-1]:
        target = target[step]
    target[path[-1]] = replacement
    repo._connection.execute(
        "UPDATE brain_research_handoffs SET payload_json=? WHERE id=?",
        (json.dumps(payload, sort_keys=True, separators=(",", ":")), value.handoff_id),
    )
    repo._connection.commit()
    with pytest.raises(ValueError, match=expected):
        repo.get_brain_research_handoff(value.handoff_id)
    with pytest.raises(ValueError, match=expected):
        repo.list_brain_research_handoffs()


def test_generic_audit_and_explicit_prebreakout_origin_reconstruction_are_exact(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    candidate = _candidate()
    handoff = candidate_to_brain_research_handoff(candidate)
    repo.save_brain_research_handoff(handoff)
    audit = AuditReconstructionService(repo)
    assert audit.reconstruct_brain_research_handoff(
        handoff.handoff_id,
        origin_validator=lambda value: validate_prebreakout_handoff_origin(value, candidate),
    ) == handoff
    wrong_policy = _candidate(policy_fingerprint="wrong-policy")
    with pytest.raises(AuditReconstructionError, match="ORIGIN_RECONSTRUCTION_MISMATCH"):
        audit.reconstruct_brain_research_handoff(
            handoff.handoff_id,
            origin_validator=lambda value: validate_prebreakout_handoff_origin(value, wrong_policy),
        )
    wrong_instrument = _candidate()
    object.__setattr__(wrong_instrument, "instrument_id", "NSE:WRONG")
    object.__setattr__(wrong_instrument, "fingerprint", prebreakout_candidate_fingerprint(wrong_instrument))
    with pytest.raises(AuditReconstructionError, match="ORIGIN_RECONSTRUCTION_MISMATCH"):
        audit.reconstruct_brain_research_handoff(
            handoff.handoff_id,
            origin_validator=lambda value: validate_prebreakout_handoff_origin(value, wrong_instrument),
        )


def test_handoff_persistence_is_not_candidate_storage_queue_research_or_governance_execution(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    handoff = candidate_to_brain_research_handoff(_candidate())
    repo.save_brain_research_handoff(handoff)
    tables = {row["name"] for row in repo._connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "brain_research_handoffs" in tables
    assert "prebreakout_candidates" not in tables
    assert not any("queue" in name or "worker" in name for name in tables if name.startswith("brain_research"))
    assert repo.get_approved_strategy_version("none") is None
    assert repo.get_strategy_activation("none") is None
    assert repo.get_strategy_promotion_proposal("none") is None
    assert repo.get_strategy_promotion_review("none") is None


def test_persisted_handoff_derives_audited_generic_intake_with_bounded_origin_context(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    handoff = candidate_to_brain_research_handoff(_candidate())
    repo.save_brain_research_handoff(handoff)
    intake = BrainResearchIntakeService(repo).get_research_intake(handoff.handoff_id)
    assert intake is not None
    assert intake.handoff_id == handoff.handoff_id and intake.handoff_fingerprint == handoff.fingerprint
    assert intake.canonical_instrument_id == handoff.canonical_instrument_id
    assert intake.origin_type == handoff.origin_type
    assert intake.origin_artifact_id == handoff.origin_artifact_id
    assert intake.origin_artifact_fingerprint == handoff.origin_artifact_fingerprint
    assert intake.evaluation_as_of == handoff.evaluation_as_of and intake.evaluation_session == handoff.evaluation_session
    assert intake.requested_brain_stage == handoff.requested_brain_stage
    assert intake.research_status == handoff.research_status
    assert intake.origin_lineage == handoff.origin_lineage
    assert intake.context_kind is BrainResearchIntakeContextKind.ORIGIN_CONTEXT
    assert ("sector", "Metals") in intake.origin_context
    assert ("maximum_executable_entry_price", "474.95") in intake.origin_context


def test_intake_is_deterministic_generic_immutable_and_missing_handoff_returns_none(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    service = BrainResearchIntakeService(repo)
    assert service.get_research_intake("missing") is None
    first_handoff = candidate_to_brain_research_handoff(_candidate())
    second_handoff = candidate_to_brain_research_handoff(_candidate(policy_fingerprint="new-policy"))
    repo.save_brain_research_handoff(first_handoff); repo.save_brain_research_handoff(second_handoff)
    first = service.get_research_intake(first_handoff.handoff_id)
    again = service.get_research_intake(first_handoff.handoff_id)
    second = service.get_research_intake(second_handoff.handoff_id)
    assert first == again and first.intake_id == again.intake_id
    assert (second.intake_id, second.fingerprint) != (first.intake_id, first.fingerprint)
    with pytest.raises(FrozenInstanceError):
        first.canonical_instrument_id = "NSE:OTHER"  # type: ignore[misc]
    manual = _manual_handoff()
    repo.save_brain_research_handoff(manual)
    assert service.get_research_intake(manual.handoff_id).origin_type is BrainResearchOriginType.MANUAL_DEEP_ANALYSIS


def test_intake_read_keeps_handoff_payload_and_pending_status_unchanged_and_tampering_fails(tmp_path) -> None:
    repo = SQLiteStrategyGovernanceRepository(tmp_path / "handoffs.db")
    handoff = candidate_to_brain_research_handoff(_candidate())
    repo.save_brain_research_handoff(handoff)
    before = repo._connection.execute("SELECT payload_json FROM brain_research_handoffs WHERE id=?", (handoff.handoff_id,)).fetchone()["payload_json"]
    assert BrainResearchIntakeService(repo).get_research_intake(handoff.handoff_id) is not None
    after = repo._connection.execute("SELECT payload_json FROM brain_research_handoffs WHERE id=?", (handoff.handoff_id,)).fetchone()["payload_json"]
    assert after == before and repo.get_brain_research_handoff(handoff.handoff_id).research_status is BrainResearchHandoffStatus.PENDING_RESEARCH
    payload = json.loads(before); payload["canonical_instrument_id"] = "NSE:TAMPERED"
    repo._connection.execute("UPDATE brain_research_handoffs SET payload_json=? WHERE id=?", (json.dumps(payload, sort_keys=True, separators=(",", ":")), handoff.handoff_id)); repo._connection.commit()
    with pytest.raises(ValueError, match="FINGERPRINT_MISMATCH"):
        BrainResearchIntakeService(repo).get_research_intake(handoff.handoff_id)


def test_intake_rejects_unsupported_nonpending_state_and_has_no_research_queue_or_trading_behavior() -> None:
    handoff = candidate_to_brain_research_handoff(_candidate())
    object.__setattr__(handoff, "research_status", "CONSUMED")
    with pytest.raises(BrainResearchIntakeError, match="STATUS_UNSUPPORTED|STATUS_INVALID"):
        create_brain_research_intake(handoff)
    source = (Path(__file__).parents[2] / "app" / "research" / "intake.py").read_text(encoding="utf-8")
    assert "strategies.pre_breakout" not in source and "PreBreakout" not in source
    assert not any(term in source for term in ("next_pending", "claim(", "lease(", "ack(", "retry(", "worker", "DecisionScore", "SixGate", "Signal", "PaperTrade"))
