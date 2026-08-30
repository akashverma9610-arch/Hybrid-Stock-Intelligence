"""U16 descriptive forward-paper intelligence regressions."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from app.forward_paper.models import ForwardPaperBar, PaperExecutionModel, PaperStudyAdmission
from app.forward_paper.service import ForwardPaperService
from app.forward_paper.store import ForwardPaperStore
from app.intelligence.forward_paper_intelligence import ForwardPaperIntelligenceProjector
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T0 = datetime(2026, 8, 3, 15, 30, tzinfo=UTC)


def _model() -> PaperExecutionModel:
    return PaperExecutionModel.create(version="execution-v1", entry_slippage=Decimal("0"), exit_slippage=Decimal("0"), round_trip_friction=Decimal("0.10"))


def _admission(label: str, *, horizon: int = 5) -> PaperStudyAdmission:
    return PaperStudyAdmission(
        "NSE:ALPHA", f"setup-{label}", f"setup-fp-{label}", f"source-fp-{label}", "pre-breakout-v1", "policy-v1", T0,
        Decimal("100"), Decimal("95"), Decimal("115"), Decimal("103"), horizon,
        market_regime="RISK_ON", sector="SOFTWARE", brain_version="brain-v1",
    )


def _bar(label: str, day: int, open_: str, high: str, low: str, close: str, **kwargs) -> ForwardPaperBar:
    at = T0 + timedelta(days=day)
    return ForwardPaperBar(label, at, at, Decimal(open_), Decimal(high), Decimal(low), Decimal(close), **kwargs)


def _ledger() -> tuple[ForwardPaperStore, ForwardPaperIntelligenceProjector]:
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    store = ForwardPaperStore(repository)
    service = ForwardPaperService(store)
    studies = {label: service.admit(_admission(label, horizon=1 if label == "expired" else 5), _model(), created_at=T0)[0] for label in (
        "winner", "loser", "open", "expired", "missed", "ambiguous", "blocked",
    )}
    service.evaluate(studies["winner"].study_id, (_bar("winner-fill", 1, "99", "101", "98", "100"), _bar("winner-exit", 2, "104", "116", "103", "115")), processing_as_of=T0 + timedelta(days=2))
    service.evaluate(studies["loser"].study_id, (_bar("loser-fill", 1, "99", "101", "98", "100"), _bar("loser-exit", 2, "94", "96", "90", "92")), processing_as_of=T0 + timedelta(days=2))
    service.evaluate(studies["open"].study_id, (_bar("open-fill", 1, "99", "101", "98", "100"),), processing_as_of=T0 + timedelta(days=1))
    service.evaluate(studies["expired"].study_id, (_bar("expired-wait", 1, "90", "99", "89", "95"), _bar("expired-end", 2, "90", "99", "89", "95")), processing_as_of=T0 + timedelta(days=2))
    service.evaluate(studies["missed"].study_id, (_bar("missed", 1, "104", "106", "103", "105"),), processing_as_of=T0 + timedelta(days=1))
    service.evaluate(studies["ambiguous"].study_id, (_bar("ambiguous", 1, "100", "116", "94", "105"),), processing_as_of=T0 + timedelta(days=1))
    service.evaluate(studies["blocked"].study_id, (_bar("blocked", 1, "99", "101", "98", "100", valid=False),), processing_as_of=T0 + timedelta(days=1))
    return store, ForwardPaperIntelligenceProjector(store)


def test_projects_all_frozen_u18_lifecycle_states_without_creating_outcomes() -> None:
    store, projector = _ledger()
    before = tuple((study.study_id, store.events(study.study_id)) for study in store.studies())
    view = projector.project(canonical_instrument_id="NSE:ALPHA", sector="SOFTWARE", as_of=T0 + timedelta(days=2))
    aggregate = view.instrument_history

    assert (aggregate.sample_count, aggregate.completed_count, aggregate.eligible_realized_count) == (7, 2, 2)
    assert (aggregate.open_count, aggregate.ambiguous_count, aggregate.blocked_count) == (1, 1, 1)
    assert (aggregate.expired_unfilled_count, aggregate.missed_do_not_chase_count) == (1, 1)
    assert aggregate.expectancy_r is not None and aggregate.average_gross_r is not None
    assert aggregate.median_mfe_r is not None and aggregate.median_mae_r is not None
    assert aggregate.evidence_sufficiency == "AVAILABLE_UNCALIBRATED"
    assert aggregate.policy_versions == ("pre-breakout-v1:policy-v1",)
    assert aggregate.direction_values == ()
    assert view.relevant_cohort_history.source_study_ids == aggregate.source_study_ids
    assert tuple((study.study_id, store.events(study.study_id)) for study in store.studies()) == before


def test_ambiguous_open_unfilled_and_blocked_studies_do_not_enter_realized_net_r() -> None:
    _, projector = _ledger()
    aggregate = projector.project(canonical_instrument_id="NSE:ALPHA", sector="SOFTWARE", as_of=T0 + timedelta(days=2)).instrument_history
    assert aggregate.eligible_realized_count == 2
    assert aggregate.target_hit_rate == Decimal("0.5") and aggregate.stop_hit_rate == Decimal("0.5")
    assert aggregate.expired_unfilled_rate == Decimal(1) / Decimal(7)
    assert aggregate.missed_do_not_chase_rate == Decimal(1) / Decimal(7)


def test_as_of_excludes_outcomes_unknown_at_the_cutoff_and_aggregate_is_deterministic() -> None:
    _, projector = _ledger()
    early = projector.project(canonical_instrument_id="NSE:ALPHA", sector="SOFTWARE", as_of=T0 + timedelta(days=1)).instrument_history
    late = projector.project(canonical_instrument_id="NSE:ALPHA", sector="SOFTWARE", as_of=T0 + timedelta(days=2)).instrument_history
    assert early.completed_count == 0 and early.expectancy_r is None
    assert late.completed_count == 2 and late.expectancy_r is not None
    assert late == projector.project(canonical_instrument_id="NSE:ALPHA", sector="SOFTWARE", as_of=T0 + timedelta(days=2)).instrument_history


def test_no_evidence_is_explicit_and_projection_has_no_policy_or_action_surface() -> None:
    repository = SQLiteCoreApiSnapshotRepository(":memory:")
    projector = ForwardPaperIntelligenceProjector(ForwardPaperStore(repository))
    aggregate = projector.project(canonical_instrument_id="NSE:UNKNOWN", sector="UNKNOWN", as_of=T0).instrument_history
    assert aggregate.evidence_sufficiency == "NO_EVIDENCE" and aggregate.sample_count == 0
    source = (Path(__file__).parents[2] / "app" / "intelligence" / "forward_paper_intelligence.py").read_text(encoding="utf-8")
    for forbidden in ("save_study", "save_event", "ForwardPaperService", "DecisionScore", "BUY", "SELL", "ExecutionGate"):
        assert forbidden not in source


def test_u16_panel_is_read_only_and_labels_forward_outcomes_as_non_recommendation() -> None:
    source = (Path(__file__).parents[2] / "frontend" / "src" / "components" / "stocks" / "ForwardPerformanceIntelligencePanel.tsx").read_text(encoding="utf-8")
    assert "Not a recommendation" in source
    for forbidden in ("BUY", "SELL", "ActionBadge", "ScoreBadge"):
        assert forbidden not in source
