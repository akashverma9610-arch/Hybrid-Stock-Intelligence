"""Bounded, stored-only Top-3 sector opportunity discovery."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.historical.guard import manifest_fingerprint
from app.production_v1.canonical_setup_activation import CanonicalSetupOpportunity, CanonicalSetupOpportunityStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily, CoreApiSnapshotRepository
from app.strategies.pre_breakout.setup_assessment import PreBreakoutSetupAssessmentStatus


@dataclass(frozen=True, slots=True)
class Top3OpportunityNearMiss:
    canonical_instrument_id: str
    sector: str
    assessment_id: str
    status: str
    blocker_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Top3OpportunityFinderRun:
    run_id: str
    as_of: datetime
    ranking_id: str
    latest_completed_session: datetime | None
    top3: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]
    assessment_ids: tuple[str, ...]
    opportunity_ids: tuple[str, ...]
    data_blocked_count: int
    condition_not_met_count: int
    valid_count: int
    near_misses: tuple[Top3OpportunityNearMiss, ...]
    fingerprint: str

    @classmethod
    def create(cls, **values):
        for key in ("top3", "candidate_ids", "excluded", "assessment_ids", "opportunity_ids", "near_misses"):
            values[key] = tuple(values[key])
        identity = manifest_fingerprint(**{key: value for key, value in values.items() if key not in {"run_id", "fingerprint"}})
        values["run_id"] = f"top3-opportunity-finder:{identity[:32]}"
        values["fingerprint"] = manifest_fingerprint(**values)
        return cls(**values)


class Top3OpportunityFinderRunStore:
    def __init__(self, repository: CoreApiSnapshotRepository) -> None: self._repository = repository
    def get(self, run_id: str) -> Top3OpportunityFinderRun | None:
        item = self._repository.get_snapshot(run_id)
        return item.payload if item is not None and isinstance(item.payload, Top3OpportunityFinderRun) else None
    def save(self, value: Top3OpportunityFinderRun) -> bool:
        if self.get(value.run_id) is not None: return False
        self._repository.save_snapshot(CoreApiSnapshot(value.run_id, CoreApiSnapshotFamily.TOP3_OPPORTUNITY_FINDER_RUN, "v1", type(value).__name__, value.fingerprint, value.as_of, value))
        return True

    def list(self) -> tuple[Top3OpportunityFinderRun, ...]:
        values: list[Top3OpportunityFinderRun] = []
        offset = 0
        while True:
            page = self._repository.list_snapshots(
                CoreApiSnapshotFamily.TOP3_OPPORTUNITY_FINDER_RUN, limit=100, offset=offset,
            )
            values.extend(
                item.payload for item in page
                if isinstance(item.payload, Top3OpportunityFinderRun)
            )
            if len(page) < 100:
                break
            offset += len(page)
        return tuple(sorted(values, key=lambda item: (item.as_of, item.run_id)))


class Top3OpportunityFinderService:
    """Uses one stored ranking report and the approved setup service; no market fetch or action."""
    def __init__(self, *, rankings, assessments, assessment_repository, opportunities: CanonicalSetupOpportunityStore, runs: Top3OpportunityFinderRunStore) -> None:
        self._rankings, self._assessments, self._assessment_repository, self._opportunities, self._runs = rankings, assessments, assessment_repository, opportunities, runs

    def run(self, *, as_of: datetime) -> Top3OpportunityFinderRun:
        ranking = self._rankings.latest(as_of=as_of)
        if ranking is None: raise ValueError("TOP3_OPPORTUNITY_RANKING_UNAVAILABLE")
        report = ranking.report
        resolved = tuple(item for item in report.constituents if item.sector in report.top3 and item.instrument_id)
        memberships: dict[str, set[str]] = {}
        for item in resolved:
            memberships.setdefault(item.instrument_id, set()).add(item.sector)
        targets = tuple(sorted(identifier for identifier, sectors in memberships.items() if len(sectors) == 1))
        excluded = tuple(sorted(
            [(item.symbol, item.resolution_status) for item in report.constituents if item.sector in report.top3 and not item.instrument_id]
            + [(identifier, "SECTOR_MEMBERSHIP_CONFLICT") for identifier, sectors in memberships.items() if len(sectors) != 1]
        ))
        sector_for = {identifier: next(iter(sectors)) for identifier, sectors in memberships.items() if len(sectors) == 1}
        values=[]; opportunities=[]
        for instrument_id in targets:
            assessment = self._existing(instrument_id, as_of)
            if assessment is None:
                assessment = self._assessments.assess_prebreakout_setup(instrument_id, as_of=as_of, sector_rotation=report)
                self._assessment_repository.save_prebreakout_setup_assessment(assessment)
            values.append(assessment)
            if assessment.status is PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE:
                opportunity = CanonicalSetupOpportunity.from_assessment(assessment)
                self._opportunities.save(opportunity); opportunities.append(opportunity)
        data = tuple(item for item in values if item.status is PreBreakoutSetupAssessmentStatus.BLOCKED_DATA)
        rejected = tuple(item for item in values if item.status not in {PreBreakoutSetupAssessmentStatus.BLOCKED_DATA, PreBreakoutSetupAssessmentStatus.ELIGIBLE_TO_FORM_CANDIDATE})
        near = tuple(sorted((Top3OpportunityNearMiss(item.instrument_id, sector_for[item.instrument_id], item.assessment_id, item.status.value, tuple(sorted(f"{b.category.value}:{b.code}" for b in item.blockers))) for item in (*data, *rejected)), key=lambda item: (len(item.blocker_codes), item.canonical_instrument_id))[:10])
        result = Top3OpportunityFinderRun.create(
            as_of=as_of, ranking_id=ranking.ranking_id, latest_completed_session=ranking.latest_completed_session,
            top3=report.top3, candidate_ids=targets, excluded=excluded,
            assessment_ids=tuple(item.assessment_id for item in values), opportunity_ids=tuple(item.opportunity_id for item in opportunities),
            data_blocked_count=len(data), condition_not_met_count=len(rejected), valid_count=len(opportunities), near_misses=near,
        )
        existing = self._runs.get(result.run_id)
        if existing is not None:
            return existing
        self._runs.save(result)
        return result

    def _existing(self, instrument_id: str, as_of: datetime):
        values=tuple(item for item in self._assessment_repository.list_prebreakout_setup_assessments(canonical_instrument_id=instrument_id) if item.evaluation_as_of == as_of)
        if len(values)>1: raise ValueError("TOP3_OPPORTUNITY_ASSESSMENT_AS_OF_CONFLICT")
        return values[0] if values else None
