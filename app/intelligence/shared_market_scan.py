"""Operator-owned, process-shared discovery snapshots; never a feed or detector.

The native orchestrator adapts stored funnel evidence. Quote coverage is a
separate observation, NOT evidence that those detectors ran on fresh ticks.
"""
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
import json
import re
from threading import Lock
from time import perf_counter

from app.historical.guard import manifest_fingerprint
from app.intelligence.multi_funnel_discovery import multi_funnel_discovery_registry
from app.intelligence.multi_funnel_orchestration import (
    WholeMarketDiscoveryBatch, orchestrate_whole_market_discovery,
    serialize_whole_market_discovery,
)
from app.market_data.dhan import DHAN_PROVIDER
from app.market_data.dhan_live import DhanLiveFeedHealth
from app.market_data.dhan_live_bar import DhanProspectiveInstrumentIdentity
from app.universe_analysis.models import ProviderMappingStatus
from app.universe_analysis.service import build_universe_snapshot


CONTRACT = "hsi-shared-market-scan/v1"
WARNINGS = (
    "CURRENT_DESCRIPTIVE_NOT_STRICT_HISTORICAL_PIT",
    "STORED_FUNNEL_EVIDENCE_NOT_FRESH_TICK_DETECTION",
    "QUOTE_FRESHNESS_AT_SCAN_ONLY_NOT_AT_READ_TIME",
    "NO_SYNTHETIC_SCAN_TTL_OR_MARKET_SESSION_INFERENCE",
    "PROCESS_LOCAL_SNAPSHOT_RESTART_REQUIRES_OPERATOR_REFRESH",
)
GAPS = ("PROSPECTIVE_VOLUME_TECHNICAL_FUNNEL_BINDING_NOT_CONFIGURED",
        "WHOLE_NSE_SOURCE_COMPLETENESS_NOT_PROVEN")


class SharedMarketScanError(ValueError):
    """Safe bounded refresh failure; no provider exception text."""


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SharedMarketScanError("MARKET_SCAN_EXPLICIT_CUTOFF_REQUIRED")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ScanSecurityCoverage:
    canonical_security_id: str
    universe_state: str
    mapping_state: str
    market_state: str
    mapping_fingerprint: str | None = None
    quote_fingerprint: str | None = None
    market_data_as_of: datetime | None = None
    received_at: datetime | None = None

    def __post_init__(self):
        if (self.universe_state not in ("ELIGIBLE", "IDENTITY_BLOCKED", "EXCLUDED", "NOT_LISTED_OR_TRADABLE")
                or self.mapping_state not in ("NOT_EVALUATED", "MISSING", "CONFLICTED", "INVALID", "MAPPED_EXACT")
                or self.market_state not in ("NOT_EVALUATED", "UNAVAILABLE", "CONFLICTED", "INVALID", "FUTURE_EXCLUDED", "LIVE", "STALE")):
            raise SharedMarketScanError("MARKET_SCAN_COVERAGE_STATE_INVALID")
        mapped = self.mapping_state == "MAPPED_EXACT"
        priced = self.market_state in ("LIVE", "STALE")
        if (mapped != (self.mapping_fingerprint is not None) or priced != (self.quote_fingerprint is not None)
                or priced != (self.market_data_as_of is not None and self.received_at is not None)
                or (not priced and (self.market_data_as_of is not None or self.received_at is not None))
                or (priced and not mapped)
                or (self.universe_state != "ELIGIBLE" and (self.mapping_state, self.market_state) != ("NOT_EVALUATED", "NOT_EVALUATED"))):
            raise SharedMarketScanError("MARKET_SCAN_COVERAGE_CONTRADICTION")
        for fingerprint in (self.mapping_fingerprint, self.quote_fingerprint):
            if fingerprint is not None and not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                raise SharedMarketScanError("MARKET_SCAN_COVERAGE_FINGERPRINT_INVALID")
        for name in ("market_data_as_of", "received_at"):
            if getattr(self, name) is not None:
                object.__setattr__(self, name, _utc(getattr(self, name)))


@dataclass(frozen=True, slots=True)
class SharedMarketScanSnapshot:
    batch: WholeMarketDiscoveryBatch
    securities: tuple[ScanSecurityCoverage, ...]
    scan_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self):
        self.batch.verify()
        rows = tuple(sorted(self.securities, key=lambda row: row.canonical_security_id))
        if len({row.canonical_security_id for row in rows}) != len(rows):
            raise SharedMarketScanError("MARKET_SCAN_ROSTER_CONFLICT")
        if {r.canonical_security_id for r in rows if r.universe_state == "ELIGIBLE"} != set(self.batch.universe.instrument_ids):
            raise SharedMarketScanError("MARKET_SCAN_DENOMINATOR_MISMATCH")
        for row in rows:
            if replace(row) != row:
                raise SharedMarketScanError("MARKET_SCAN_COVERAGE_TAMPERED")
            for stamp in (row.market_data_as_of, row.received_at):
                if stamp is not None and _utc(stamp) > self.batch.as_of:
                    raise SharedMarketScanError("MARKET_SCAN_FUTURE_QUOTE")
        object.__setattr__(self, "securities", rows)
        fingerprint = manifest_fingerprint(contract=CONTRACT, batch=self.batch.fingerprint,
            coverage=tuple(_coverage_payload(r) for r in rows))
        object.__setattr__(self, "scan_id", "hsi-market-scan:" + fingerprint[:32])
        object.__setattr__(self, "fingerprint", fingerprint)

    def verify(self):
        if replace(self) != self:
            raise SharedMarketScanError("MARKET_SCAN_SNAPSHOT_TAMPERED")


def _coverage_payload(row):
    return {name: (value.isoformat() if isinstance(value, datetime) else value)
        for name in row.__dataclass_fields__ for value in (getattr(row, name),)}


def _coverage(instrument, mappings, quotes, cutoff, ambiguous_provider_ids):
    identifier = instrument.instrument_id
    if not re.fullmatch(r"NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]", identifier) or identifier != "NSE:" + (instrument.isin or ""):
        return ScanSecurityCoverage(identifier, "IDENTITY_BLOCKED", "NOT_EVALUATED", "NOT_EVALUATED")
    if instrument.exchange != "NSE" or instrument.security_type != "EQUITY" or instrument.main_board is False:
        return ScanSecurityCoverage(identifier, "EXCLUDED", "NOT_EVALUATED", "NOT_EVALUATED")
    # Existing universe-analysis ACTIVE/tradable boundary, not a new threshold.
    if instrument.listing_status.upper() != "ACTIVE" or instrument.tradable is False:
        return ScanSecurityCoverage(identifier, "NOT_LISTED_OR_TRADABLE", "NOT_EVALUATED", "NOT_EVALUATED")
    base = ScanSecurityCoverage(identifier, "ELIGIBLE", "MISSING", "UNAVAILABLE")
    eligible = tuple(m for m in mappings if m.canonical_instrument_id == identifier
        and m.provider == DHAN_PROVIDER and _utc(m.effective_as_of) <= cutoff)
    if not eligible:
        return base
    latest_time = max(m.effective_as_of for m in eligible)
    latest = tuple(m for m in eligible if m.effective_as_of == latest_time)
    if any(m != latest[0] for m in latest):
        return replace(base, mapping_state="CONFLICTED")
    mapping = latest[0]
    try:
        if (mapping.status is not ProviderMappingStatus.ACTIVE or mapping.isin != instrument.isin
                or mapping.normalized_instrument != "EQUITY" or mapping.raw_provider_exchange != "NSE"
                or mapping.raw_provider_series != "EQ"):
            raise ValueError
        identity = DhanProspectiveInstrumentIdentity(identifier, mapping.isin,
            int(mapping.provider_instrument_reference), mapping.provider_exchange_segment,
            mapping.raw_provider_series, mapping.source_checksum)
        if (identity.exchange_segment, str(identity.provider_security_id)) in ambiguous_provider_ids:
            return replace(base, mapping_state="CONFLICTED")
    except (ValueError, TypeError):
        return replace(base, mapping_state="INVALID")
    base = replace(base, mapping_state="MAPPED_EXACT", mapping_fingerprint=manifest_fingerprint(
        mapping_id=mapping.mapping_id, version=mapping.mapping_version, master=mapping.source_checksum,
        security=identifier, isin=mapping.isin, provider=DHAN_PROVIDER,
        provider_security_id=identity.provider_security_id, segment=identity.exchange_segment,
        series=identity.series, normalized_instrument=mapping.normalized_instrument,
        effective_as_of=_utc(mapping.effective_as_of).isoformat()))
    candidates = tuple(q for q in quotes if q.canonical_instrument_id == identifier)
    if not candidates:
        return base
    if any(q != candidates[0] for q in candidates):
        return replace(base, market_state="CONFLICTED")
    quote = candidates[0]
    try:
        traded, received = _utc(quote.provider_trade_timestamp), _utc(quote.received_at)
        if traded > cutoff or received > cutoff:
            return replace(base, market_state="FUTURE_EXCLUDED")
        if (quote.provider != DHAN_PROVIDER or str(quote.provider_security_id) != str(identity.provider_security_id)
                or not isinstance(quote.ltp, Decimal) or not quote.ltp.is_finite() or quote.ltp <= 0
                or traded > received or quote.freshness not in (DhanLiveFeedHealth.LIVE, DhanLiveFeedHealth.STALE)):
            return replace(base, market_state="INVALID")
        return replace(base, market_state=quote.freshness.value, market_data_as_of=traded,
            received_at=received, quote_fingerprint=manifest_fingerprint(security=identifier,
                mapping=base.mapping_fingerprint, price=str(quote.ltp), traded=traded.isoformat(), received=received.isoformat()))
    except (ValueError, TypeError):
        return replace(base, market_state="INVALID")


class SharedMarketScanService:
    """One explicit operator refresh; bounded process-wide immutable cache.

    ``sources(cutoff)`` borrows existing canonical readers, never a transport.
    Reads do not call it. No user identity, scheduler or automatic refresh.
    """
    def __init__(self, sources):
        self._sources = sources
        self._refresh_lock = Lock()
        self._cache_lock = Lock()
        self._snapshots = ()

    def refresh(self, *, as_of: datetime) -> SharedMarketScanSnapshot:
        cutoff = _utc(as_of)
        if not self._refresh_lock.acquire(blocking=False):
            raise SharedMarketScanError("MARKET_SCAN_REFRESH_BUSY")
        try:
            started = perf_counter()  # Operational duration only, never semantic identity.
            instruments, mappings, quotes, reader = self._sources(cutoff)
            if len(instruments) > 20000 or len(mappings) > 40000 or len(quotes) > 20000:
                raise SharedMarketScanError("MARKET_SCAN_INPUT_BOUND_EXCEEDED")
            if len({i.instrument_id for i in instruments}) != len(instruments):
                raise SharedMarketScanError("MARKET_SCAN_UNIVERSE_CONFLICT")
            if any(_utc(i.data_as_of) > cutoff for i in instruments):
                raise SharedMarketScanError("MARKET_SCAN_FUTURE_UNIVERSE")
            mapped, quoted, provider_owners = {}, {}, {}
            for mapping in mappings:
                if mapping.provider == DHAN_PROVIDER and _utc(mapping.effective_as_of) <= cutoff:
                    mapped.setdefault(mapping.canonical_instrument_id, []).append(mapping)
            for identifier, values in mapped.items():
                latest = max(v.effective_as_of for v in values)
                for value in values:
                    if value.effective_as_of == latest and value.status is ProviderMappingStatus.ACTIVE:
                        ref = value.provider_instrument_reference
                        ref = str(int(ref)) if ref.isdecimal() else ref
                        provider_owners.setdefault((value.provider_exchange_segment, ref), set()).add(identifier)
            ambiguous = {key for key, ids in provider_owners.items() if len(ids) > 1}
            for quote in quotes:
                quoted.setdefault(quote.canonical_instrument_id, []).append(quote)
            coverage = tuple(_coverage(i, mapped.get(i.instrument_id, ()),
                quoted.get(i.instrument_id, ()), cutoff, ambiguous) for i in instruments)
            eligible = {r.canonical_security_id for r in coverage if r.universe_state == "ELIGIBLE"}
            records = tuple(i for i in instruments if i.instrument_id in eligible)
            if not records:
                raise SharedMarketScanError("MARKET_SCAN_CANONICAL_UNIVERSE_UNAVAILABLE")
            universe = build_universe_snapshot(snapshot_id="shared-nse:" + manifest_fingerprint(
                ids=tuple(sorted(eligible)), as_of=cutoff.isoformat())[:32], as_of=cutoff,
                source="CoreUniverseAnalysisStore:ACTIVE_NSE_MAIN_BOARD", instruments=records)
            batch = orchestrate_whole_market_discovery(as_of=cutoff, universe=universe,
                instruments=records, registry=multi_funnel_discovery_registry(), read_sources=reader)
            snapshot = SharedMarketScanSnapshot(batch, coverage)
            duration = max(0.0, perf_counter() - started)
            # Verify/serialize ONCE on the operator side. Native verification
            # rebuilds the union and must not run on every Agent read.
            payload_json = json.dumps(scan_payload(snapshot, duration), sort_keys=True,
                separators=(",", ":"), default=lambda value: _utc(value).isoformat())
            with self._cache_lock:
                for previous, _, _ in self._snapshots:
                    if previous.batch.as_of == cutoff:
                        if previous != snapshot:
                            raise SharedMarketScanError("MARKET_SCAN_SAME_CUTOFF_CONFLICT")
                        return previous
                self._snapshots = tuple(sorted((*self._snapshots, (snapshot, duration, payload_json)),
                    key=lambda item: item[0].batch.as_of))[-8:]
            return snapshot
        finally:
            self._refresh_lock.release()

    def latest(self, *, as_of: datetime):
        cutoff = _utc(as_of)
        with self._cache_lock:
            eligible = tuple(item for item in self._snapshots if item[0].batch.as_of <= cutoff)
        if not eligible:
            return None
        snapshot, duration, _ = eligible[-1]
        snapshot.verify()
        return snapshot, duration

    def read_payload(self, *, as_of: datetime):
        """Immutable JSON response, not a call to native union verification.

        The internal batch is retained for separate bounded diagnostic handoff.
        Serving its frozen public bytes cannot mutate it or recompute discovery.
        """
        cutoff = _utc(as_of)
        with self._cache_lock:
            eligible = tuple(item for item in self._snapshots if item[0].batch.as_of <= cutoff)
        if not eligible:
            return None
        snapshot, _, payload = eligible[-1]
        result = json.loads(payload)
        if result["fingerprint"] != snapshot.fingerprint or result["batch_fingerprint"] != snapshot.batch.fingerprint:
            raise SharedMarketScanError("MARKET_SCAN_SNAPSHOT_TAMPERED")
        return result


def scan_payload(snapshot, duration):
    """Projection only. Native union/origins survive; no score/AI ranking."""
    snapshot.verify()
    batch = snapshot.batch
    native = json.loads(serialize_whole_market_discovery(batch))
    rows = snapshot.securities
    eligible = tuple(r for r in rows if r.universe_state == "ELIGIBLE")
    identified = {lead.canonical_instrument_id for execution in batch.executions for lead in execution.original.leads}
    examined = len(identified & set(batch.universe.instrument_ids))
    return {
        "scan_id": snapshot.scan_id, "scan_as_of": batch.as_of, "fingerprint": snapshot.fingerprint,
        "universe_snapshot_id": batch.universe.snapshot_id, "universe_fingerprint": batch.universe.checksum,
        "batch_id": batch.batch_id, "batch_fingerprint": batch.fingerprint,
        "market_data_as_of": max((r.market_data_as_of for r in rows if r.market_data_as_of), default=None),
        "securities": tuple(_coverage_payload(r) for r in rows),
        "requested_funnels": native["envelope"]["requested_funnels"],
        "executed_funnels": native["envelope"]["executed_funnels"],
        "blocked_funnels": native["envelope"]["blocked_funnels"],
        "funnels": tuple({"funnel_id": e.original.funnel_id, "execution_state": e.state,
            "coverage_state": e.original.coverage.state, "adapter_state": e.original.coverage.adapter_state,
            "leads": len(e.original.leads), "source_observations": e.source_records_supplied,
            "blockers": e.original.coverage.reason_codes} for e in batch.executions),
        "candidate_union": native["candidate_union"],
        "metrics": {"source_universe": len(rows), "eligible_universe": len(eligible),
            "mapped_exact": sum(r.mapping_state == "MAPPED_EXACT" for r in eligible),
            "fresh_quote_count": sum(r.market_state == "LIVE" for r in eligible),
            "quote_insufficient": sum(r.market_state != "LIVE" for r in eligible),
            "identity_blocked": sum(r.universe_state == "IDENTITY_BLOCKED" for r in rows),
            "excluded": sum(r.universe_state not in ("ELIGIBLE", "IDENTITY_BLOCKED") for r in rows),
            "conflicted": sum("CONFLICTED" in (r.mapping_state, r.market_state) for r in rows),
            "securities_examined_proven": examined, "evaluation_coverage_unproven": len(eligible) - examined,
            "candidate_union_count": len(batch.candidate_union.candidates),
            "blocked_funnel_count": len(batch.envelope.blocked_funnels)},
        "scan_duration_seconds": duration, "deep_diagnostics_run": False,
        "freshness": "NATIVE_SOURCE_AS_OF_ONLY", "market_state_mode": "CURRENT_DESCRIPTIVE",
    }
