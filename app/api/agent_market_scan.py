"""Local source composition and public read projection for the shared scan."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.api.schemas.agent_tools import ToolEnvelope
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F
from app.intelligence.shared_market_scan import (
    GAPS, WARNINGS, SharedMarketScanError, SharedMarketScanService,
)
from app.market_data.dhan import DHAN_PROVIDER
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily as Family
from app.universe_analysis.models import ProviderInstrumentMappingRecord
from app.universe_analysis.service import CoreUniverseAnalysisStore


class ScanFunnelResponse(BaseModel):
    funnel_id: str
    execution_state: str
    coverage_state: str
    adapter_state: str
    leads: int
    source_observations: int | None
    blockers: tuple[str, ...]


class ScanSecurityResponse(BaseModel):
    canonical_security_id: str
    universe_state: str
    mapping_state: str
    market_state: str
    mapping_fingerprint: str | None
    quote_fingerprint: str | None
    market_data_as_of: datetime | None
    received_at: datetime | None


class SharedMarketScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scan_id: str
    scan_as_of: datetime
    fingerprint: str
    universe_snapshot_id: str
    universe_fingerprint: str
    batch_id: str
    batch_fingerprint: str
    market_data_as_of: datetime | None
    securities: tuple[ScanSecurityResponse, ...]
    requested_funnels: tuple[str, ...]
    executed_funnels: tuple[str, ...]
    blocked_funnels: tuple[str, ...]
    funnels: tuple[ScanFunnelResponse, ...]
    # The unchanged canonical union serializer is authoritative, not a new
    # public union model or a lossy summary that drops originating evidence.
    candidate_union: dict
    metrics: dict[str, int]
    scan_duration_seconds: float
    deep_diagnostics_run: Literal[False]
    freshness: Literal["NATIVE_SOURCE_AS_OF_ONLY"]
    market_state_mode: Literal["CURRENT_DESCRIPTIVE"]


def _read_family(repository, family, cutoff):
    """One paginated local family read; never silently truncate a scan."""
    result = []
    for offset in range(0, 20001, 100):
        page = repository.list_snapshots(family, limit=100, offset=offset)
        result.extend(item.payload for item in page if item.created_at <= cutoff)
        if offset + len(page) > 20000:
            raise SharedMarketScanError("MARKET_SCAN_SOURCE_BOUND_EXCEEDED")
        if len(page) < 100:
            return tuple(result)
    raise SharedMarketScanError("MARKET_SCAN_SOURCE_BOUND_EXCEEDED")


class _CapturedUniverseReader:
    """Bounded read view, not another universe or storage system."""
    def __init__(self, rows):
        self.rows = rows

    def list_snapshots(self, family, *, limit=100, offset=0):
        if family is not Family.NSE_UNIVERSE:
            raise SharedMarketScanError("MARKET_SCAN_UNEXPECTED_UNIVERSE_READ")
        return self.rows[offset:offset + limit]


def shared_scan_from_existing_state(state_provider):
    """Creation is inert. Only operator refresh reads the borrowed resources."""
    def sources(cutoff):
        state = state_provider()
        repository = getattr(state, "core_api_snapshot_repository", None)
        if repository is None:
            raise SharedMarketScanError("MARKET_SCAN_CANONICAL_RESOURCES_UNAVAILABLE")
        # Capture bounded native envelopes, including their store availability.
        # No record acquired later may be relabelled as known at the cutoff.
        envelopes = []
        for offset in range(0, 20001, 100):
            page = repository.list_snapshots(Family.NSE_UNIVERSE, limit=100, offset=offset)
            if offset + len(page) > 20000:
                raise SharedMarketScanError("MARKET_SCAN_SOURCE_BOUND_EXCEEDED")
            envelopes.extend(row for row in page if row.created_at <= cutoff)
            if len(page) < 100:
                break
        universe = CoreUniverseAnalysisStore(_CapturedUniverseReader(tuple(envelopes)))
        instruments = universe.instruments_as_of(cutoff)
        selected = {item.instrument_id: item for item in instruments}
        for row in envelopes:
            value = row.payload
            current = selected.get(getattr(value, "instrument_id", None))
            if current is not None and value.data_as_of == current.data_as_of and value != current:
                raise SharedMarketScanError("MARKET_SCAN_UNIVERSE_CONFLICT")
        # Preserve inactive and equal-time conflicting mappings; do not use a
        # latest-active-only shortcut which could hide revocation/ambiguity.
        mappings = tuple(m for m in _read_family(repository, Family.PROVIDER_INSTRUMENT_MAPPING, cutoff)
            if isinstance(m, ProviderInstrumentMappingRecord) and m.provider == DHAN_PROVIDER)
        runtime = getattr(state, "dhan_live_market_runtime", None)
        quotes = tuple(runtime.quotes(now=cutoff)) if runtime is not None else ()

        def reader(funnel, at):
            families = {F.PRE_BREAKOUT: Family.CANONICAL_SETUP_OPPORTUNITY,
                        F.SECTOR_ROTATION: Family.TOP3_OPPORTUNITY_FINDER_RUN}
            family = families.get(funnel)
            # Research-only observation stores are not wired here. None is
            # unavailable, not an empty successful scan of every NSE security.
            return None if family is None else _read_family(repository, family, at)
        return instruments, mappings, quotes, reader
    return SharedMarketScanService(sources)


def market_scan_response(service, *, as_of):
    if service is None:
        return ToolEnvelope(status="BLOCKED", blockers=("SHARED_MARKET_SCAN_NOT_CONFIGURED",))
    try:
        payload = service.read_payload(as_of=as_of)
        if payload is None:
            return ToolEnvelope(status="BLOCKED", blockers=("SHARED_MARKET_SCAN_REFRESH_REQUIRED",))
        # Partial is truthful even with zero leads; an empty candidate pool is
        # not a crash and does not prove complete market coverage.
        data = SharedMarketScanResponse(**payload)
        blockers = (*GAPS, *tuple("FUNNEL_BLOCKED:" + f for f in data.blocked_funnels))
        return ToolEnvelope(status="PARTIAL", as_of=data.scan_as_of,
            data=data, blockers=blockers, warnings=WARNINGS,
            evidence_refs=(data.universe_snapshot_id,),
            provenance=(data.fingerprint, data.batch_fingerprint, data.candidate_union["fingerprint"]))
    except Exception:
        return ToolEnvelope(status="BLOCKED", blockers=("SHARED_MARKET_SCAN_INVALID_OR_UNAVAILABLE",))
