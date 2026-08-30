"""Read-only, point-in-time projections of immutable forward-paper evidence.

This module deliberately has no strategy, score, provider, or persistence
dependency.  It only summarizes U18's existing immutable study/event ledger.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from statistics import median

from app.forward_paper.models import PaperExitReason, PaperStudyState
from app.forward_paper.service import rebuild_snapshot
from app.forward_paper.store import ForwardPaperStore
from app.historical.guard import manifest_fingerprint


AGGREGATION_VERSION = "forward-paper-intelligence-v1"


@dataclass(frozen=True, slots=True)
class ForwardPaperAggregate:
    """A reproducible descriptive aggregate; never an execution instruction."""

    evidence_sufficiency: str
    scope: str
    cohort_definition: tuple[str, ...]
    as_of: datetime
    aggregation_version: str
    sample_count: int
    completed_count: int
    eligible_realized_count: int
    open_count: int
    waiting_count: int
    ambiguous_count: int
    blocked_count: int
    expired_unfilled_count: int
    missed_do_not_chase_count: int
    win_rate: Decimal | None
    expectancy_r: Decimal | None
    median_r: Decimal | None
    average_r: Decimal | None
    average_gross_r: Decimal | None
    median_gross_r: Decimal | None
    profit_factor: Decimal | None
    median_mfe_r: Decimal | None
    median_mae_r: Decimal | None
    average_holding_sessions: Decimal | None
    target_hit_rate: Decimal | None
    stop_hit_rate: Decimal | None
    expired_unfilled_rate: Decimal | None
    missed_do_not_chase_rate: Decimal | None
    source_study_ids: tuple[str, ...]
    source_study_fingerprints: tuple[str, ...]
    policy_versions: tuple[str, ...]
    execution_model_versions: tuple[str, ...]
    direction_values: tuple[str, ...]
    fingerprint: str


@dataclass(frozen=True, slots=True)
class ForwardPaperIntelligenceView:
    """Shared-Brain read section for factual forward-paper performance."""

    instrument_history: ForwardPaperAggregate
    relevant_cohort_history: ForwardPaperAggregate
    warnings: tuple[str, ...]


class ForwardPaperIntelligenceProjector:
    """Projects one immutable U18 ledger at a requested ``as_of`` cutoff."""

    def __init__(self, store: ForwardPaperStore) -> None:
        self._store = store

    def project(self, *, canonical_instrument_id: str, sector: str | None, as_of: datetime) -> ForwardPaperIntelligenceView:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("FORWARD_PAPER_INTELLIGENCE_AS_OF_TIMEZONE_REQUIRED")
        known = tuple(study for study in self._store.studies() if study.created_at <= as_of)
        instrument = tuple(study for study in known if study.admission.canonical_instrument_id == canonical_instrument_id)
        strategy_versions = tuple(sorted({study.admission.strategy_version for study in instrument}))
        cohort = tuple(study for study in known if sector is not None and study.admission.sector == sector and (
            not strategy_versions or study.admission.strategy_version in strategy_versions
        ))
        return ForwardPaperIntelligenceView(
            instrument_history=_aggregate(
                self._store, instrument, as_of=as_of, scope="INSTRUMENT",
                definition=(f"canonical_instrument_id={canonical_instrument_id}",),
            ),
            relevant_cohort_history=_aggregate(
                self._store, cohort, as_of=as_of, scope="SECTOR_COHORT",
                definition=(
                    f"sector={sector}" if sector is not None else "sector=UNAVAILABLE",
                    "strategy_versions=" + (",".join(strategy_versions) if strategy_versions else "ALL_STORED"),
                ),
            ),
            warnings=(
                "DESCRIPTIVE_ONLY_NO_POLICY_MUTATION",
                "NET_R_IS_HEADLINE_REALIZED_PERFORMANCE",
                "DIRECTION_UNAVAILABLE_IN_CURRENT_U18_ADMISSION_CONTRACT",
            ),
        )


def no_forward_paper_intelligence(*, canonical_instrument_id: str, sector: str | None, as_of: datetime) -> ForwardPaperIntelligenceView:
    """Return the same truthful shape when a deployment has no paper store."""
    return ForwardPaperIntelligenceView(
        instrument_history=_aggregate(None, (), as_of=as_of, scope="INSTRUMENT", definition=(f"canonical_instrument_id={canonical_instrument_id}",)),
        relevant_cohort_history=_aggregate(None, (), as_of=as_of, scope="SECTOR_COHORT", definition=(f"sector={sector}" if sector is not None else "sector=UNAVAILABLE", "strategy_versions=ALL_STORED")),
        warnings=("NO_FORWARD_PAPER_EVIDENCE", "DESCRIPTIVE_ONLY_NO_POLICY_MUTATION"),
    )


def _aggregate(store: ForwardPaperStore | None, studies, *, as_of: datetime, scope: str, definition: tuple[str, ...]) -> ForwardPaperAggregate:
    rows = []
    for study in sorted(studies, key=lambda value: value.study_id):
        # Event occurrence is the knowledge clock. Session timestamps are also
        # bounded to keep a malformed future-dated event from leaking forward.
        events = tuple(event for event in store.events(study.study_id) if event.occurred_at <= as_of and (event.session_at is None or event.session_at <= as_of)) if store else ()
        rows.append((study, rebuild_snapshot(study, events)))
    completed = tuple(snapshot for _, snapshot in rows if snapshot.state is PaperStudyState.CLOSED)
    realized = tuple(snapshot for snapshot in completed if snapshot.net_r is not None)
    net = tuple(snapshot.net_r for snapshot in realized if snapshot.net_r is not None)
    gross = tuple(snapshot.gross_r for snapshot in realized if snapshot.gross_r is not None)
    count = Decimal(len(realized))
    total = Decimal(len(rows))
    average = lambda values: sum(values, Decimal("0")) / Decimal(len(values)) if values else None
    middle = lambda values: median(values) if values else None
    positive = sum((value for value in net if value > 0), Decimal("0"))
    negative = -sum((value for value in net if value < 0), Decimal("0"))
    status = "NO_EVIDENCE" if not rows else "INSUFFICIENT" if not realized else "AVAILABLE_UNCALIBRATED"
    values = dict(
        evidence_sufficiency=status, scope=scope, cohort_definition=definition, as_of=as_of,
        aggregation_version=AGGREGATION_VERSION, sample_count=len(rows), completed_count=len(completed),
        eligible_realized_count=len(realized), open_count=sum(snapshot.state is PaperStudyState.OPEN for _, snapshot in rows),
        waiting_count=sum(snapshot.state is PaperStudyState.WAITING_FOR_TRIGGER for _, snapshot in rows),
        ambiguous_count=sum(snapshot.state is PaperStudyState.AMBIGUOUS for _, snapshot in rows),
        blocked_count=sum(snapshot.state is PaperStudyState.INVALID_DATA for _, snapshot in rows),
        expired_unfilled_count=sum(snapshot.state is PaperStudyState.EXPIRED_UNFILLED for _, snapshot in rows),
        missed_do_not_chase_count=sum(snapshot.state is PaperStudyState.MISSED_DO_NOT_CHASE for _, snapshot in rows),
        win_rate=(Decimal(sum(value > 0 for value in net)) / count if count else None),
        expectancy_r=average(net), median_r=middle(net), average_r=average(net),
        average_gross_r=average(gross), median_gross_r=middle(gross),
        profit_factor=(positive / negative if negative else None),
        median_mfe_r=middle(tuple(snapshot.mfe_r for snapshot in realized if snapshot.mfe_r is not None)),
        median_mae_r=middle(tuple(snapshot.mae_r for snapshot in realized if snapshot.mae_r is not None)),
        average_holding_sessions=average(tuple(Decimal(snapshot.sessions_held) for snapshot in realized)),
        target_hit_rate=(Decimal(sum(snapshot.exit_reason is PaperExitReason.TARGET for snapshot in realized)) / count if count else None),
        stop_hit_rate=(Decimal(sum(snapshot.exit_reason is PaperExitReason.STOP for snapshot in realized)) / count if count else None),
        expired_unfilled_rate=(Decimal(sum(snapshot.state is PaperStudyState.EXPIRED_UNFILLED for _, snapshot in rows)) / total if total else None),
        missed_do_not_chase_rate=(Decimal(sum(snapshot.state is PaperStudyState.MISSED_DO_NOT_CHASE for _, snapshot in rows)) / total if total else None),
        source_study_ids=tuple(study.study_id for study, _ in rows),
        source_study_fingerprints=tuple(study.fingerprint for study, _ in rows),
        policy_versions=tuple(sorted({study.admission.strategy_version + ":" + study.admission.policy_fingerprint for study, _ in rows})),
        execution_model_versions=tuple(sorted({study.execution_model.version for study, _ in rows})),
        # Current U18 admission has no direction field.  Keeping this explicit
        # avoids hard-coding the projection to LONG-only when U18 grows one.
        direction_values=(),
    )
    return ForwardPaperAggregate(**values, fingerprint=manifest_fingerprint(**_semantic(values)))


def _semantic(values: dict) -> dict:
    def value(item):
        if isinstance(item, datetime): return item.isoformat()
        if isinstance(item, Decimal): return str(item)
        if isinstance(item, tuple): return tuple(value(part) for part in item)
        return item
    return {key: value(item) for key, item in values.items()}


__all__ = (
    "AGGREGATION_VERSION", "ForwardPaperAggregate", "ForwardPaperIntelligenceProjector",
    "ForwardPaperIntelligenceView", "no_forward_paper_intelligence",
)
