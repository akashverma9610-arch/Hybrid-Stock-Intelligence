"""Durable stored-only setup and bar composition for forward-paper studies."""
from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from decimal import Decimal

from app.forward_paper.models import (
    ForwardPaperBar,
    PaperStudyAdmission,
    is_strictly_future_nse_session,
    nse_session_date,
)
from app.forward_paper.store import ForwardPaperStore
from app.historical.guard import manifest_fingerprint
from app.historical.security_master import HistoricalSecurityMasterStore
from app.market_data.historical import HistoricalBarStore
from app.market_data.models import Timeframe
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.strategies.pre_breakout.candidate_assembly import PreBreakoutCandidate
from app.strategies.pre_breakout.candidate_assembly import assemble_prebreakout_candidate
from app.strategies.pre_breakout.materialization import PreBreakoutStructuralStatus
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment,
    PreBreakoutSetupAssessmentStatus,
)


@dataclass(frozen=True, slots=True)
class StoredExecutableSetup:
    setup_id: str
    canonical_instrument_id: str
    setup_fingerprint: str
    source_candidate_fingerprint: str
    strategy_version: str
    policy_fingerprint: str
    decision_as_of: datetime
    trigger: Decimal
    structural_stop: Decimal
    target: Decimal
    maximum_entry: Decimal | None
    time_stop_sessions: int
    sector: str | None
    sector_context_fingerprint: str | None
    brain_version: str | None
    brain_fingerprint: str | None
    diagnostic_fingerprint: str | None
    financial_semantic_fingerprint: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if not all((self.setup_id, self.canonical_instrument_id, self.setup_fingerprint, self.source_candidate_fingerprint,
                    self.strategy_version, self.policy_fingerprint)):
            raise ValueError("STORED_EXECUTABLE_SETUP_IDENTITY_REQUIRED")
        if self.decision_as_of.tzinfo is None or self.decision_as_of.utcoffset() is None:
            raise ValueError("STORED_EXECUTABLE_SETUP_DECISION_CUTOFF_REQUIRED")
        if not self.structural_stop < self.trigger < self.target or self.time_stop_sessions < 1:
            raise ValueError("STORED_EXECUTABLE_SETUP_ECONOMICS_INVALID")
        expected = manifest_fingerprint(**{field.name: _semantic(getattr(self, field.name)) for field in fields(self) if field.name != "fingerprint"})
        if self.fingerprint != expected: raise ValueError("STORED_EXECUTABLE_SETUP_FINGERPRINT_MISMATCH")

    def admission(self) -> PaperStudyAdmission:
        return PaperStudyAdmission(self.canonical_instrument_id, self.setup_id, self.setup_fingerprint,
            self.source_candidate_fingerprint, self.strategy_version, self.policy_fingerprint, self.decision_as_of,
            self.trigger, self.structural_stop, self.target, self.maximum_entry, self.time_stop_sessions,
            sector=self.sector, sector_context_fingerprint=self.sector_context_fingerprint,
            brain_version=self.brain_version, brain_fingerprint=self.brain_fingerprint,
            diagnostic_fingerprint=self.diagnostic_fingerprint,
            financial_semantic_fingerprint=self.financial_semantic_fingerprint)

    @classmethod
    def create(cls, *, setup_id: str, canonical_instrument_id: str, setup_fingerprint: str,
               source_candidate_fingerprint: str, strategy_version: str, policy_fingerprint: str,
               decision_as_of: datetime, trigger: Decimal, structural_stop: Decimal, target: Decimal,
               maximum_entry: Decimal | None, time_stop_sessions: int, sector: str | None = None,
               sector_context_fingerprint: str | None = None, brain_version: str | None = None,
               brain_fingerprint: str | None = None, diagnostic_fingerprint: str | None = None,
               financial_semantic_fingerprint: str | None = None) -> "StoredExecutableSetup":
        values = locals().copy(); values.pop("cls")
        return cls(**values, fingerprint=manifest_fingerprint(**{key: _semantic(value) for key, value in values.items()}))


class StoredExecutableSetupStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository

    def save(self, value: StoredExecutableSetup) -> bool:
        existing = self._repository.get_snapshot(value.setup_id)
        if existing is not None:
            if existing.payload != value: raise ValueError("STORED_EXECUTABLE_SETUP_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(value.setup_id, CoreApiSnapshotFamily.FORWARD_PAPER_EXECUTABLE_SETUP,
            "v1", type(value).__name__, value.fingerprint, value.decision_as_of, value))
        return True

    def list(self, *, as_of: datetime) -> tuple[StoredExecutableSetup, ...]:
        rows=[]; offset=0
        while True:
            page=self._repository.list_snapshots(CoreApiSnapshotFamily.FORWARD_PAPER_EXECUTABLE_SETUP, limit=100, offset=offset)
            rows.extend(item.payload for item in page if isinstance(item.payload, StoredExecutableSetup) and item.payload.decision_as_of <= as_of)
            if len(page)<100: break
            offset += len(page)
        return tuple(sorted(rows, key=lambda item: (item.decision_as_of, item.setup_id)))


class StoredForwardPaperComposition:
    """Only reads durable setup artifacts and canonical historical bars."""
    def __init__(self, setups: StoredExecutableSetupStore, bars: HistoricalBarStore,
                 corporate_actions: HistoricalSecurityMasterStore | None = None) -> None:
        self._setups, self._bars, self._corporate_actions = setups, bars, corporate_actions

    def admissions(self, *, as_of: datetime) -> tuple[PaperStudyAdmission, ...]:
        # An immutable setup is retained for audit, but an instrument with an
        # unresolved bar-conflict artifact is never admitted to forward-paper
        # processing.  Healthy setups are not affected by another symbol's
        # conflict.
        return tuple(
            item.admission() for item in self._setups.list(as_of=as_of)
            if not self._bars.has_conflict_artifact(item.canonical_instrument_id)
        )

    def bars_for(self, admission: PaperStudyAdmission, *, start: datetime, end: datetime) -> tuple[ForwardPaperBar, ...]:
        if self._bars.has_conflict_artifact(admission.canonical_instrument_id):
            raise ValueError("OHLCV_CONFLICTED")
        bars = self._bars.range(admission.canonical_instrument_id, Timeframe.DAILY, start, end, as_of=end)
        review_actions = () if self._corporate_actions is None else tuple(
            item for item in self._corporate_actions.actions_as_of(admission.canonical_instrument_id, end)
            if item.price_transforming and admission.decision_as_of < item.effective_date <= end
        )
        values: list[ForwardPaperBar] = []
        previous_session = None
        for item in bars:
            if item.instrument.instrument_id != admission.canonical_instrument_id:
                raise ValueError("FORWARD_PAPER_CANONICAL_INSTRUMENT_IDENTITY_MISMATCH")
            # Do not let a caller's broad ``start`` parameter re-admit a T0
            # daily bar.  The decision session is frozen in the admission.
            if not is_strictly_future_nse_session(item.end_time, admission.decision_as_of):
                continue
            session = nse_session_date(item.end_time)
            if previous_session is not None and session <= previous_session:
                raise ValueError("FORWARD_PAPER_CANONICAL_SESSION_SEQUENCE_INVALID")
            previous_session = session
            values.append(ForwardPaperBar(
                item.bar_id, item.end_time, item.provenance.received_at,
                item.open, item.high, item.low, item.close, valid=True,
                corporate_action_requires_review=any(action.effective_date <= item.end_time for action in review_actions),
            ))
        return tuple(values)


def stored_setup_from_prebreakout(candidate: PreBreakoutCandidate, *, time_stop_sessions: int,
                                  brain_version: str | None = None, brain_fingerprint: str | None = None,
                                  diagnostic_fingerprint: str | None = None,
                                  financial_semantic_fingerprint: str | None = None) -> StoredExecutableSetup:
    """Persist a reviewed setup artifact; never infer missing time or price economics."""
    if candidate.actual_execution_price is not None or candidate.formation_blockers:
        raise ValueError("PREBREAKOUT_CANDIDATE_NOT_EXECUTABLE_FOR_FORWARD_PAPER")
    # The current candidate's pre-breakout entry ceiling is below confirmation
    # trigger and is not a breakout E_max.  Preserve it as unavailable rather
    # than mislabeling it as a do-not-chase ceiling.
    maximum_entry = None if candidate.maximum_executable_entry_price < candidate.breakout_confirmation_trigger else candidate.maximum_executable_entry_price
    return StoredExecutableSetup.create(setup_id=f"stored-executable:{candidate.candidate_id}",
        canonical_instrument_id=candidate.instrument_id, setup_fingerprint=candidate.fingerprint,
        source_candidate_fingerprint=candidate.fingerprint, strategy_version=candidate.policy_version,
        policy_fingerprint=candidate.policy_fingerprint, decision_as_of=candidate.evaluation_as_of,
        trigger=candidate.breakout_confirmation_trigger, structural_stop=candidate.final_structural_stop,
        target=candidate.measured_move_target, maximum_entry=maximum_entry, time_stop_sessions=time_stop_sessions,
        sector=candidate.sector, sector_context_fingerprint=candidate.selection_fingerprint,
        brain_version=brain_version, brain_fingerprint=brain_fingerprint,
        diagnostic_fingerprint=diagnostic_fingerprint, financial_semantic_fingerprint=financial_semantic_fingerprint)


def compose_stored_executable_setup(
    assessment: GovernedPreBreakoutSetupAssessment,
    *,
    time_stop_sessions: int,
) -> StoredExecutableSetup:
    """Compose the sole durable forward-paper setup from governed scan evidence.

    The assessment is the authoritative source.  A transient candidate is
    reconstructed solely through the existing governed candidate adapter; it
    is not a new scanner output and is never persisted by this boundary.
    """
    if not isinstance(assessment, GovernedPreBreakoutSetupAssessment):
        raise ValueError("GOVERNED_EXECUTABLE_SETUP_ASSESSMENT_REQUIRED")
    if assessment.status is not PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE:
        raise ValueError("GOVERNED_EXECUTABLE_SETUP_NOT_ELIGIBLE")
    technical, structural = assessment.technical_inputs, assessment.structural
    if (
        not assessment.candidate_formation_eligible
        or assessment.blockers
        or technical.blockers
        or structural.blockers
        or assessment.top3_sector_membership is not True
        or not all((technical.bbw_pass, technical.atr_contraction_pass, technical.volume_dry_up_pass,
                    technical.delivery_pass, technical.distance_from_high_pass, technical.rsi_pass))
        or structural.status is not PreBreakoutStructuralStatus.STRUCTURAL_ENTRY_READY
        or structural.entry_reference_rr_pass is not True
        or structural.actual_execution_price is not None
        or structural.actual_execution_status != "NOT_EVALUATED_AT_SCAN"
        or any(value is None for value in (
            assessment.evaluation_session, assessment.policy_id, assessment.policy_version,
            assessment.policy_fingerprint, assessment.selection_id, assessment.selection_fingerprint,
            assessment.sector, assessment.sector_rotation_as_of, structural.breakout_confirmation_trigger,
            structural.final_stop, structural.target, structural.entry_reference_price,
            structural.maximum_executable_entry_price, structural.entry_reference_rr,
        ))
    ):
        raise ValueError("GOVERNED_EXECUTABLE_SETUP_REQUIRED_EVIDENCE_MISSING")
    candidate = assemble_prebreakout_candidate(assessment)
    return stored_setup_from_prebreakout(candidate, time_stop_sessions=time_stop_sessions)


def _semantic(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, Decimal): return str(value)
    return value
