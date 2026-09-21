"""Allowlisted shared projections of retained canonical evidence, never a Brain.

No calculation, materialization, portfolio lookup, policy selection or provider
call. UNKNOWN freshness deliberately cannot become FRESH merely by reading.
"""
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.analysis.models import MarketRegimeResult
from app.api.market_query import market_regime_response
from app.api.schemas.market import MarketRegimeResponse
from app.api.schemas.market_wide_watch import WatchEvidenceReferenceResponse, WatchExternalEvidenceReferenceResponse
from app.intelligence.market_wide_watch import MarketWideWatchStore
from app.market_data.current_sector_rotation import (
    CurrentSectorBreadthResult, CurrentSectorRankingArtifact, CurrentSectorRankingStore,
    CurrentSectorRelativeStrength,
)
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily as Family


class ReadModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceReference(ReadModel):
    artifact_id: str
    fingerprint: str
    as_of: datetime
    known_at: datetime
    policy_reference: str | None = None


class SectorRankingData(ReadModel):
    benchmark_identity: str
    latest_completed_session: datetime | None
    ranked_sectors: tuple[str, ...]
    top3: tuple[str, ...]
    relative_strength: tuple[CurrentSectorRelativeStrength, ...]
    breadth: tuple[CurrentSectorBreadthResult, ...]


class SharedWatchRecord(ReadModel):
    watch_id: str
    canonical_instrument_id: str
    symbol: str
    company_name: str | None
    watch_as_of: datetime
    last_evidence_as_of: datetime | None
    classifications: tuple[str, ...]
    archetypes: tuple[str, ...]
    status: str
    evidence_sufficiency: str
    evidence_references: tuple[WatchEvidenceReferenceResponse, ...]
    external_evidence_references: tuple[WatchExternalEvidenceReferenceResponse, ...]
    setup_policy_routes: tuple[tuple[str, str], ...]
    lifecycle_flags: tuple[str, ...]
    blocker_codes: tuple[str, ...]
    policy_identity: str
    fingerprint: str
    # These are unavailable, not inferred from an archetype or chart pattern.
    horizon: None = None
    direction: None = None
    strategy_eligibility: Literal["NOT_EVALUATED"] = "NOT_EVALUATED"
    actionability: Literal["WATCH_ONLY"] = "WATCH_ONLY"
    execution_status: Literal["NON_EXECUTABLE"] = "NON_EXECUTABLE"


class WatchData(ReadModel):
    interpretation: Literal["STORED_WATCH_EVIDENCE_ONLY"] = "STORED_WATCH_EVIDENCE_ONLY"
    records: tuple[SharedWatchRecord, ...]


class CanonicalQueryResponse(ReadModel):
    contract_version: Literal["pilot-canonical-query/v1"] = "pilot-canonical-query/v1"
    query_as_of: datetime
    status: Literal["READY", "DEGRADED", "STALE", "UNAVAILABLE"]
    freshness: Literal["FRESH", "UNKNOWN", "STALE", "UNAVAILABLE"]
    reason_codes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    sources: tuple[SourceReference, ...] = ()
    data: MarketRegimeResponse | SectorRankingData | WatchData | None = None


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("CANONICAL_TIMESTAMP_INVALID")
    return value.astimezone(UTC)


class _PITReader:
    """Bounded read adapter; never silently truncate history or accept late receipt."""
    def __init__(self, repository, as_of):
        self.repository, self.as_of, self.rows = repository, as_of, {}

    def list_snapshots(self, family, *, limit=100, offset=0):
        if family not in self.rows:
            values = []
            for start in range(0, 10001, 100):
                page = self.repository.list_snapshots(family, limit=100, offset=start)
                if start == 10000 and page:
                    raise ValueError("CANONICAL_READ_BOUND_EXCEEDED")
                for item in page:
                    if _utc(item.created_at) <= self.as_of:
                        if item.family != family or not item.snapshot_id or not item.fingerprint:
                            raise ValueError("CANONICAL_PROVENANCE_REQUIRED")
                        values.append(item)
                if len(page) < 100:
                    break
            self.rows[family] = tuple(values)
        return self.rows[family][offset:offset + limit]

    def reference(self, family, identifier, fingerprint, as_of, policy=None):
        matches = [r for r in self.rows[family] if r.snapshot_id == identifier]
        if len(matches) != 1 or matches[0].fingerprint != fingerprint:
            raise ValueError("CANONICAL_PROVENANCE_MISMATCH")
        return SourceReference(artifact_id=identifier, fingerprint=fingerprint,
                               as_of=_utc(as_of), known_at=_utc(matches[0].created_at), policy_reference=policy)


class PilotCanonicalQueryService:
    def __init__(self, repository):
        self.repository = repository

    def read(self, surface: Literal["market", "sectors", "opportunities", "stocks"], *,
             as_of: datetime, instrument_id: str | None = None) -> CanonicalQueryResponse:
        cutoff = _utc(as_of)
        unavailable = lambda code: CanonicalQueryResponse(query_as_of=cutoff, status="UNAVAILABLE",
                                                         freshness="UNAVAILABLE", reason_codes=(code,))
        if self.repository is None:
            return unavailable("PILOT_CANONICAL_STORAGE_UNAVAILABLE")
        reader = _PITReader(self.repository, cutoff)
        try:
            if surface == "market":
                reader.list_snapshots(Family.MARKET_REGIME)
                rows = tuple(r for r in reader.rows[Family.MARKET_REGIME]
                             if isinstance(r.payload, MarketRegimeResult)
                             and _utc(r.payload.as_of_timestamp) <= cutoff
                             and _utc(r.payload.evaluated_at) <= cutoff)
                if not rows:
                    return unavailable("MARKET_REGIME_UNAVAILABLE")
                row = max(rows, key=lambda r: (r.payload.as_of_timestamp, r.payload.evaluated_at, r.snapshot_id))
                value = row.payload
                data = market_regime_response(value).model_copy(update={"conditions": ()})
                refs = (reader.reference(Family.MARKET_REGIME, row.snapshot_id, row.fingerprint,
                                         value.as_of_timestamp),)
                warnings = (*data.warnings, "INTERNAL_CONDITIONS_OMITTED")
            elif surface == "sectors":
                value = CurrentSectorRankingStore(reader).latest(as_of=cutoff)
                if value is None:
                    return unavailable("CURRENT_SECTOR_RANKING_UNAVAILABLE")
                # Compare, never repair or persist a recomputed fingerprint.
                if CurrentSectorRankingArtifact.create(value.report) != value:
                    return unavailable("CANONICAL_PROVENANCE_INVALID")
                if value.latest_completed_session and _utc(value.latest_completed_session) > _utc(value.ranking_as_of):
                    return unavailable("CANONICAL_EVIDENCE_AFTER_CUTOFF")
                refs = (reader.reference(Family.CURRENT_SECTOR_RANKING, value.ranking_id, value.fingerprint,
                                         value.ranking_as_of, value.ranking_policy_version),)
                data = SectorRankingData(benchmark_identity=value.benchmark_identity,
                    latest_completed_session=value.latest_completed_session,
                    ranked_sectors=value.report.ranked_sectors, top3=value.report.top3,
                    relative_strength=value.report.relative_strength, breadth=value.report.breadth)
                warnings = value.report.warnings
            elif surface in {"opportunities", "stocks"}:
                value = MarketWideWatchStore(reader).latest(as_of=cutoff)
                if value is None:
                    return unavailable("MARKET_WIDE_WATCH_UNAVAILABLE")
                value.verify()
                refs = (reader.reference(Family.MARKET_WIDE_QUALITY_INFLECTION_WATCH,
                    value.run_id, value.fingerprint, value.watch_as_of, value.policy_identity),)
                # Never use portfolio_records, comparison_readiness, private scores
                # or aggregate rotation counts from the broad legacy Watch DTO.
                records = tuple(r for r in value.records
                                if surface != "stocks" or r.canonical_instrument_id == instrument_id)
                if len({r.canonical_instrument_id for r in value.records}) != len(value.records):
                    return unavailable("CANONICAL_IDENTITY_CONFLICT")
                if surface == "stocks" and not records:
                    return unavailable("CANONICAL_INSTRUMENT_WATCH_UNAVAILABLE")
                if any(_utc(r.watch_as_of) != _utc(value.watch_as_of)
                       or r.last_evidence_as_of and _utc(r.last_evidence_as_of) > _utc(r.watch_as_of) for r in records):
                    return unavailable("CANONICAL_EVIDENCE_AFTER_CUTOFF")
                data = WatchData(records=tuple(SharedWatchRecord(
                    **{name: getattr(r, name) for name in SharedWatchRecord.model_fields
                       if name not in {"horizon", "direction", "strategy_eligibility", "actionability", "execution_status",
                                       "evidence_references", "external_evidence_references"}},
                    evidence_references=tuple(WatchEvidenceReferenceResponse.model_validate(e, from_attributes=True)
                                              for e in r.evidence_references),
                    external_evidence_references=tuple(WatchExternalEvidenceReferenceResponse.model_validate(e, from_attributes=True)
                                                       for e in r.external_evidence_references),
                ) for r in records))
                warnings = ("STORED_WATCH_NOT_EXECUTABLE_OPPORTUNITY", "HORIZON_DIRECTION_UNAVAILABLE",
                            "STRATEGY_ELIGIBILITY_NOT_EVALUATED")
            else:
                return unavailable("CANONICAL_SURFACE_UNAVAILABLE")
            # These three retained contracts do not establish current freshness.
            # Preserve lifecycle/source warnings; never guess an expiry or reset
            # an evidence timestamp to the request time. READY/FRESH and STALE
            # are vocabulary, not a license to classify age without a policy.
            return CanonicalQueryResponse(query_as_of=cutoff, status="DEGRADED",
                freshness="UNKNOWN", sources=refs, data=data,
                reason_codes=("FRESHNESS_POLICY_UNAVAILABLE",),
                warnings=tuple(sorted(set((*warnings, "RETAINED_EVIDENCE_NOT_LIVE")))))
        except (ValueError, TypeError, AttributeError, KeyError):
            return unavailable("CANONICAL_PROVENANCE_INVALID")
