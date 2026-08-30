"""Backend-neutral immutable snapshots for forward-paper experimental history."""
from __future__ import annotations

from datetime import datetime

from app.forward_paper.models import ForwardPaperEvent, ForwardPaperStudy
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository


class ForwardPaperStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository

    def save_study(self, value: ForwardPaperStudy) -> bool:
        existing = self._repository.get_snapshot(value.study_id)
        if existing is not None:
            if existing.payload != value: raise ValueError("FORWARD_PAPER_STUDY_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(value.study_id, CoreApiSnapshotFamily.FORWARD_PAPER_STUDY,
            "v1", type(value).__name__, value.fingerprint, value.created_at, value))
        return True

    def save_event(self, value: ForwardPaperEvent) -> bool:
        existing = self._repository.get_snapshot(value.event_id)
        if existing is not None:
            if existing.payload != value: raise ValueError("FORWARD_PAPER_EVENT_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(value.event_id, CoreApiSnapshotFamily.FORWARD_PAPER_EVENT,
            "v1", type(value).__name__, value.fingerprint, value.occurred_at, value))
        return True

    def save_run(self, value: "ForwardPaperRun") -> bool:
        """Retain a bounded worker/run receipt without mutating studies or events."""
        existing = self._repository.get_snapshot(value.run_id)
        if existing is not None:
            if existing.family is not CoreApiSnapshotFamily.FORWARD_PAPER_RUN or existing.payload != value:
                raise ValueError("FORWARD_PAPER_RUN_IMMUTABLE_CONFLICT")
            return False
        self._repository.save_snapshot(CoreApiSnapshot(
            value.run_id, CoreApiSnapshotFamily.FORWARD_PAPER_RUN,
            "v1", type(value).__name__, _run_fingerprint(value), value.completed_at, value,
        ))
        return True

    def get_study(self, study_id: str) -> ForwardPaperStudy | None:
        item = self._repository.get_snapshot(study_id)
        return item.payload if item is not None and item.family is CoreApiSnapshotFamily.FORWARD_PAPER_STUDY else None

    def studies(self) -> tuple[ForwardPaperStudy, ...]:
        return tuple(item.payload for item in self._all(CoreApiSnapshotFamily.FORWARD_PAPER_STUDY)
                     if isinstance(item.payload, ForwardPaperStudy))

    def events(self, study_id: str) -> tuple[ForwardPaperEvent, ...]:
        values = (item.payload for item in self._all(CoreApiSnapshotFamily.FORWARD_PAPER_EVENT)
                  if isinstance(item.payload, ForwardPaperEvent) and item.payload.study_id == study_id)
        return tuple(sorted(values, key=lambda item: (item.session_at or item.occurred_at, item.occurred_at, item.event_id)))

    def runs(self) -> tuple["ForwardPaperRun", ...]:
        from app.forward_paper.service import ForwardPaperRun
        values = (item.payload for item in self._all(CoreApiSnapshotFamily.FORWARD_PAPER_RUN)
                  if isinstance(item.payload, ForwardPaperRun))
        return tuple(sorted(values, key=lambda item: (item.completed_at, item.run_id)))

    def latest_run(self) -> "ForwardPaperRun | None":
        values = self.runs()
        return values[-1] if values else None

    def _all(self, family: CoreApiSnapshotFamily):
        offset = 0
        while True:
            page = self._repository.list_snapshots(family, limit=100, offset=offset)
            yield from page
            if len(page) < 100: return
            offset += len(page)


def _run_fingerprint(value: "ForwardPaperRun") -> str:
    from app.historical.guard import manifest_fingerprint
    return manifest_fingerprint(
        run_id=value.run_id, started_at=value.started_at.isoformat(), completed_at=value.completed_at.isoformat(),
        health=value.health.value, admitted=value.admitted, sessions_processed=value.sessions_processed,
        entries=value.entries, exits=value.exits, marks=value.marks, misses=value.misses,
        ambiguous=value.ambiguous, failures=value.failures, reason=value.reason,
    )
