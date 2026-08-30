"""Stored-only governed Pre-Breakout setup-source composition for Production V1.

This module bridges one already-governed assessment to the existing immutable
``StoredExecutableSetup`` seam.  It deliberately does not admit a paper study,
process bars, create fills, or make provider requests.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.forward_paper.composition import (
    StoredExecutableSetup,
    StoredExecutableSetupStore,
    compose_stored_executable_setup,
)
from app.historical.guard import manifest_fingerprint
from app.storage.core_api_snapshot_repository import (
    CoreApiSnapshot,
    CoreApiSnapshotFamily,
    CoreApiSnapshotRepository,
)
from app.strategies.pre_breakout.setup_assessment import (
    GovernedPreBreakoutSetupAssessment,
    PreBreakoutSetupAssessmentStatus,
)


class GovernedExecutableSetupSourceState(StrEnum):
    READY_WITH_EXECUTABLE_SETUP = "READY_WITH_EXECUTABLE_SETUP"
    READY_NO_CURRENT_SETUP = "READY_NO_CURRENT_SETUP"
    BLOCKED_DATA = "BLOCKED_DATA"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_COMPOSITION = "BLOCKED_COMPOSITION"


@dataclass(frozen=True, slots=True)
class GovernedExecutableSetupSourceRun:
    """Immutable receipt for one explicit stored-data governed setup scan."""

    run_id: str
    as_of: datetime
    top3: tuple[str, ...]
    excluded_sectors: tuple[str, ...]
    assessment_ids: tuple[str, ...]
    assessment_fingerprints: tuple[str, ...]
    executable_setup_ids: tuple[str, ...]
    executable_setup_fingerprints: tuple[str, ...]
    eligible_count: int
    partial_or_data_blocked_count: int
    rejected_count: int
    persisted_count: int
    duplicate_count: int
    state: GovernedExecutableSetupSourceState
    reason: str | None
    fingerprint: str

    def __post_init__(self) -> None:
        if self.as_of.tzinfo is None or self.as_of.utcoffset() is None:
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_AS_OF_REQUIRED")
        if len(self.assessment_ids) != len(self.assessment_fingerprints):
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_ASSESSMENT_LINEAGE_INVALID")
        if len(self.executable_setup_ids) != len(self.executable_setup_fingerprints):
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_SETUP_LINEAGE_INVALID")
        if any(value < 0 for value in (
            self.eligible_count, self.partial_or_data_blocked_count, self.rejected_count,
            self.persisted_count, self.duplicate_count,
        )):
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_COUNTS_INVALID")
        expected = _fingerprint(self)
        if self.fingerprint != expected:
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_FINGERPRINT_MISMATCH")

    @classmethod
    def create(cls, **values) -> "GovernedExecutableSetupSourceRun":
        values["top3"] = tuple(values["top3"])
        values["excluded_sectors"] = tuple(values["excluded_sectors"])
        values["assessment_ids"] = tuple(values["assessment_ids"])
        values["assessment_fingerprints"] = tuple(values["assessment_fingerprints"])
        values["executable_setup_ids"] = tuple(values["executable_setup_ids"])
        values["executable_setup_fingerprints"] = tuple(values["executable_setup_fingerprints"])
        # The receipt identity is the deterministic source decision, not the
        # mutable outcome of attempting an already-recorded insert again.
        identity = manifest_fingerprint(**_semantic({
            key: values[key] for key in (
                "as_of", "top3", "excluded_sectors", "assessment_ids",
                "assessment_fingerprints", "executable_setup_ids",
                "executable_setup_fingerprints", "eligible_count", "state", "reason",
            )
        }))
        values.setdefault("run_id", f"governed-executable-setup-source:{identity[:32]}")
        values["fingerprint"] = _fingerprint_values(values)
        return cls(**values)


class GovernedExecutableSetupSourceRunStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None:
        self._repository = repository

    def save(self, value: GovernedExecutableSetupSourceRun) -> bool:
        existing = self._repository.get_snapshot(value.run_id)
        if existing is not None:
            if existing.payload != value:
                raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_RUN_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.run_id, CoreApiSnapshotFamily.GOVERNED_EXECUTABLE_SETUP_SOURCE_RUN,
            "v1", type(value).__name__, value.fingerprint, value.as_of, value,
        ))
        return True

    def get(self, run_id: str) -> GovernedExecutableSetupSourceRun | None:
        item = self._repository.get_snapshot(run_id)
        return item.payload if item is not None and isinstance(item.payload, GovernedExecutableSetupSourceRun) else None

    def latest(self, *, as_of: datetime) -> GovernedExecutableSetupSourceRun | None:
        rows: list[GovernedExecutableSetupSourceRun] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(
                CoreApiSnapshotFamily.GOVERNED_EXECUTABLE_SETUP_SOURCE_RUN, limit=100, offset=offset,
            )
            rows.extend(
                item.payload for item in page
                if isinstance(item.payload, GovernedExecutableSetupSourceRun) and item.payload.as_of <= as_of
            )
            if len(page) < 100:
                break
            offset += len(page)
        return max(rows, key=lambda item: (item.as_of, item.run_id)) if rows else None


class GovernedExecutableSetupSourceService:
    """Explicit scan/persistence runner; never a paper-trading orchestrator."""

    def __init__(
        self,
        *,
        assessment_service,
        assessment_repository,
        rotation_service,
        setup_store: StoredExecutableSetupStore,
        run_store: GovernedExecutableSetupSourceRunStore,
        time_stop_sessions: int | None = None,
    ) -> None:
        self._assessments = assessment_service
        self._assessment_repository = assessment_repository
        self._rotation = rotation_service
        self._setups = setup_store
        self._runs = run_store
        self._time_stop_sessions = time_stop_sessions

    def run(self, *, as_of: datetime) -> GovernedExecutableSetupSourceRun:
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_SOURCE_AS_OF_REQUIRED")
        rotation = self._rotation.assess(as_of=as_of)
        target_ids = tuple(sorted({item.instrument_id for item in rotation.constituents if item.sector in rotation.top3 and item.instrument_id}))
        excluded = tuple(sorted(item.sector for item in rotation.relative_strength if item.exclusion_reason is not None))
        assessments: list[GovernedPreBreakoutSetupAssessment] = []
        setups: list[StoredExecutableSetup] = []
        persisted = duplicates = eligible = partial = rejected = 0
        composition_errors: list[str] = []
        for instrument_id in target_ids:
            assessment = self._existing_assessment(instrument_id, as_of=as_of)
            if assessment is None:
                assessment = self._assessments.assess_prebreakout_setup(
                    instrument_id,
                    as_of=as_of,
                    sector_rotation=rotation,
                )
                self._save_assessment(assessment)
            assessments.append(assessment)
            if assessment.status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE:
                eligible += 1
                if self._time_stop_sessions is None:
                    composition_errors.append("PAPER_TIME_STOP_SOURCE_UNCONFIGURED")
                    continue
                try:
                    setup = compose_stored_executable_setup(
                        assessment, time_stop_sessions=self._time_stop_sessions,
                    )
                    setups.append(setup)
                    if self._setups.save(setup):
                        persisted += 1
                    else:
                        duplicates += 1
                except ValueError as error:
                    composition_errors.append(str(error))
            elif assessment.status is PreBreakoutSetupAssessmentStatus.BLOCKED_DATA:
                partial += 1
            else:
                rejected += 1
        state, reason = _state(
            target_ids=target_ids,
            assessments=assessments,
            eligible=eligible,
            composition_errors=composition_errors,
        )
        result = GovernedExecutableSetupSourceRun.create(
            as_of=as_of, top3=tuple(rotation.top3), excluded_sectors=excluded,
            assessment_ids=tuple(item.assessment_id for item in assessments),
            assessment_fingerprints=tuple(item.fingerprint for item in assessments),
            executable_setup_ids=tuple(item.setup_id for item in setups),
            executable_setup_fingerprints=tuple(item.fingerprint for item in setups),
            eligible_count=eligible, partial_or_data_blocked_count=partial, rejected_count=rejected,
            persisted_count=persisted, duplicate_count=duplicates, state=state, reason=reason,
        )
        existing = self._runs.get(result.run_id)
        if existing is not None:
            return existing
        self._runs.save(result)
        return result

    def _save_assessment(self, value: GovernedPreBreakoutSetupAssessment) -> None:
        existing = self._assessment_repository.get_prebreakout_setup_assessment(value.assessment_id)
        if existing is None:
            self._assessment_repository.save_prebreakout_setup_assessment(value)
        elif existing != value:
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_ASSESSMENT_IMMUTABLE_CONFLICT")

    def _existing_assessment(
        self, canonical_instrument_id: str, *, as_of: datetime,
    ) -> GovernedPreBreakoutSetupAssessment | None:
        """Reuse only an exact persisted governed scan result at this cutoff.

        This prevents an explicit idempotent rerun from recalculating the same
        expensive PIT assessment.  No older/newer evidence is eligible and an
        ambiguous exact-cutoff record fails closed.
        """
        values = tuple(
            item for item in self._assessment_repository.list_prebreakout_setup_assessments(
                canonical_instrument_id=canonical_instrument_id,
            )
            if item.evaluation_as_of == as_of
        )
        if len(values) > 1:
            raise ValueError("GOVERNED_EXECUTABLE_SETUP_ASSESSMENT_AS_OF_CONFLICT")
        return values[0] if values else None


def _state(*, target_ids, assessments, eligible: int, composition_errors: list[str]):
    if not target_ids:
        return GovernedExecutableSetupSourceState.BLOCKED_DATA, "TOP3_SECTOR_UNIVERSE_UNAVAILABLE"
    if assessments and all(item.status is PreBreakoutSetupAssessmentStatus.BLOCKED_GOVERNANCE for item in assessments):
        return GovernedExecutableSetupSourceState.BLOCKED_POLICY, "SELECTED_PREBREAKOUT_POLICY_UNAVAILABLE"
    if eligible and composition_errors:
        return GovernedExecutableSetupSourceState.BLOCKED_COMPOSITION, ",".join(sorted(set(composition_errors)))
    if eligible:
        return GovernedExecutableSetupSourceState.READY_WITH_EXECUTABLE_SETUP, None
    return GovernedExecutableSetupSourceState.READY_NO_CURRENT_SETUP, "NO_CURRENT_EXECUTABLE_SETUP"


def _semantic(values: dict) -> dict:
    return {
        key: (value.value if isinstance(value, StrEnum) else value.isoformat() if isinstance(value, datetime) else value)
        for key, value in sorted(values.items()) if key not in {"run_id", "fingerprint"}
    }


def _fingerprint(value: GovernedExecutableSetupSourceRun) -> str:
    return _fingerprint_values({name: getattr(value, name) for name in value.__dataclass_fields__ if name != "fingerprint"})


def _fingerprint_values(values: dict) -> str:
    return manifest_fingerprint(**_semantic(values))
