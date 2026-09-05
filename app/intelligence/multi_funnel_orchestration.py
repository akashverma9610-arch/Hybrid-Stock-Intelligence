"""Explicit-snapshot discovery only; never invoke downstream candidate judgement.

The injected reader returns retained canonical records, not provider data. None
means unavailable; an empty tuple means a successful read with no observations.
No source reader is invoked for an unadapted/contextual funnel.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field, fields, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum, StrEnum

from app.historical.guard import manifest_fingerprint
from app.intelligence import multi_funnel_discovery_adapters as adapters
from app.intelligence.multi_funnel_candidate_union import (
    MultiFunnelCandidateUnionBatch, union_discovery_candidates,
)
from app.intelligence.multi_funnel_discovery import (
    DiscoveryCoverageState, DiscoveryFunnelId, FunnelCoverage,
    MultiFunnelDiscoveryBatch, MultiFunnelDiscoveryRegistry,
    multi_funnel_discovery_registry,
)
from app.universe_analysis.models import NseEquityInstrument, UniverseSnapshot
from app.universe_analysis.service import build_universe_snapshot


WHOLE_MARKET_DISCOVERY_CONTRACT = "multi-funnel-whole-market-orchestration/v1"
SourceReader = Callable[[DiscoveryFunnelId, datetime], tuple[object, ...] | None]
F = DiscoveryFunnelId
S = adapters.DiscoveryAdapterCoverageState
A = adapters.DiscoveryAdapterState
R = adapters.DiscoveryAdapterReason


class DiscoveryOrchestrationError(ValueError):
    """Non-secret invalid master-input/receipt error."""


class DiscoveryExecutionState(StrEnum):
    NOT_EXECUTABLE = "NOT_EXECUTABLE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_READ_FAILED = "SOURCE_READ_FAILED"
    SOURCE_VALIDATION_FAILED = "SOURCE_VALIDATION_FAILED"
    ADAPTER_FAILED = "ADAPTER_FAILED"
    SOURCE_CONFLICT = "SOURCE_CONFLICT"
    EVALUATED = "EVALUATED"


# Capability bindings, not another funnel registry. Enumeration always comes
# from the verified canonical registry. Never call its engine entry-point text.
_BINDINGS = (
    (F.PRE_BREAKOUT, adapters.adapt_pre_breakout, "opportunities", "opportunity_id"),
    (F.SECTOR_ROTATION, adapters.adapt_sector_rotation, "runs", "run_id"),
    (F.FUNDAMENTAL_INFLECTION, adapters.adapt_fundamental_inflection, "observations", "observation_id"),
    (F.COMPOUNDER, adapters.adapt_compounder, "observations", "observation_id"),
    (F.POLICY_TRANSMISSION, adapters.adapt_policy_transmission, "observations", "result_id"),
)


@dataclass(frozen=True, slots=True)
class DiscoveryFunnelExecution:
    state: DiscoveryExecutionState
    original: adapters.DiscoveryAdapterResult
    # Identity/fingerprint pairs for all readable source records, including
    # non-emitting and future records. Replays remain visible, not silently lost.
    source_references: tuple[tuple[str, str], ...] = ()
    source_records_supplied: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, DiscoveryExecutionState):
            raise DiscoveryOrchestrationError("DISCOVERY_EXECUTION_STATE_INVALID")
        _verify_adapter(self.original)
        if not isinstance(self.source_references, tuple) or any(
            not isinstance(pair, tuple) or len(pair) != 2
            or not isinstance(pair[0], str) or not re.fullmatch(r"[A-Za-z0-9._:-]+", pair[0])
            or not isinstance(pair[1], str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", pair[1])
            for pair in self.source_references
        ):
            raise DiscoveryOrchestrationError("DISCOVERY_SOURCE_REFERENCES_INVALID")
        object.__setattr__(self, "source_references", tuple(sorted(self.source_references)))
        supported = self.original.funnel_id in {item[0] for item in _BINDINGS}
        if (self.state is DiscoveryExecutionState.NOT_EXECUTABLE) == supported:
            raise DiscoveryOrchestrationError("DISCOVERY_EXECUTION_CAPABILITY_MISMATCH")
        if self.state is not DiscoveryExecutionState.EVALUATED and self.original.leads:
            raise DiscoveryOrchestrationError("DISCOVERY_FAILED_EXECUTION_HAS_LEADS")
        read_completed = self.state in (DiscoveryExecutionState.EVALUATED,
            DiscoveryExecutionState.ADAPTER_FAILED, DiscoveryExecutionState.SOURCE_CONFLICT,
            DiscoveryExecutionState.SOURCE_VALIDATION_FAILED)
        if read_completed:
            if type(self.source_records_supplied) is not int or self.source_records_supplied < len(self.source_references):
                raise DiscoveryOrchestrationError("DISCOVERY_SOURCE_COUNT_INVALID")
            if self.state is DiscoveryExecutionState.EVALUATED and self.source_records_supplied != len(self.source_references):
                raise DiscoveryOrchestrationError("DISCOVERY_SOURCE_LINEAGE_INCOMPLETE")
        elif self.source_records_supplied is not None or self.source_references:
            raise DiscoveryOrchestrationError("DISCOVERY_UNREAD_SOURCE_LINEAGE_INVALID")
        if self.state not in (DiscoveryExecutionState.NOT_EXECUTABLE, DiscoveryExecutionState.EVALUATED):
            expected = _failure_coverage(self.original.funnel_id, self.state)
            if self.original.coverage != expected:
                raise DiscoveryOrchestrationError("DISCOVERY_FAILURE_COVERAGE_CONTRADICTION")

    @property
    def executed(self) -> bool:
        return self.state in (DiscoveryExecutionState.EVALUATED, DiscoveryExecutionState.ADAPTER_FAILED)


@dataclass(frozen=True, slots=True)
class WholeMarketDiscoveryBatch:
    as_of: datetime
    universe: UniverseSnapshot
    instruments: tuple[NseEquityInstrument, ...]
    registry: MultiFunnelDiscoveryRegistry
    executions: tuple[DiscoveryFunnelExecution, ...]
    envelope: MultiFunnelDiscoveryBatch = field(init=False)
    candidate_union: MultiFunnelCandidateUnionBatch = field(init=False)
    batch_id: str = field(init=False)
    fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "as_of", _utc(self.as_of))
        instruments = tuple(sorted(self.instruments, key=lambda item: item.instrument_id))
        object.__setattr__(self, "instruments", instruments)
        _verify_universe(self.universe, instruments, self.as_of)
        _verify_registry(self.registry)
        executions = tuple(sorted(self.executions, key=lambda item: item.original.funnel_id.value))
        object.__setattr__(self, "executions", executions)
        requested = tuple(item.funnel_id for item in self.registry.entries)
        if tuple(item.original.funnel_id for item in executions) != requested:
            raise DiscoveryOrchestrationError("DISCOVERY_ALL_FUNNELS_REQUIRED")
        for item in executions:
            if replace(item) != item or item.original.as_of != self.as_of:
                raise DiscoveryOrchestrationError("DISCOVERY_EXECUTION_INVALID")
            if item.state is DiscoveryExecutionState.NOT_EXECUTABLE and item.original != adapters.unavailable_adapter(funnel_id=item.original.funnel_id, as_of=self.as_of):
                raise DiscoveryOrchestrationError("DISCOVERY_BLOCKED_STATE_CHANGED")
        scoped = tuple(_scope(item.original, self.universe.instrument_ids) for item in executions)
        union = union_discovery_candidates(as_of=self.as_of, adapter_results=scoped)
        object.__setattr__(self, "candidate_union", union)
        evaluated = self.evaluated_funnels
        envelope = MultiFunnelDiscoveryBatch(
            as_of=self.as_of, universe_snapshot_id=self.universe.snapshot_id,
            universe_snapshot_fingerprint=self.universe.checksum, registry=self.registry,
            requested_funnels=requested, executed_funnels=evaluated,
            blocked_funnels=tuple(item for item in requested if item not in evaluated),
            coverage=tuple(_envelope_coverage(item, self.universe.eligible_security_count) for item in scoped),
            emitted_lead_ids=tuple(sorted(lead.lead_id for item in scoped for lead in item.leads)),
        )
        object.__setattr__(self, "envelope", envelope)
        identity = manifest_fingerprint(contract=WHOLE_MARKET_DISCOVERY_CONTRACT,
            envelope=envelope.batch_id, executions=_plain(executions), universe=_plain(self.universe))
        object.__setattr__(self, "batch_id", "whole-market-discovery:" + identity[:32])
        object.__setattr__(self, "fingerprint", manifest_fingerprint(**_payload(self)))

    @property
    def executable_funnels(self) -> tuple[DiscoveryFunnelId, ...]:
        return tuple(item.original.funnel_id for item in self.executions if item.state in (
            DiscoveryExecutionState.EVALUATED, DiscoveryExecutionState.ADAPTER_FAILED,
        ))

    @property
    def evaluated_funnels(self) -> tuple[DiscoveryFunnelId, ...]:
        return tuple(item.original.funnel_id for item in self.executions if item.state is DiscoveryExecutionState.EVALUATED)

    @property
    def source_not_operational_funnels(self) -> tuple[DiscoveryFunnelId, ...]:
        return tuple(item.original.funnel_id for item in self.executions if item.original.coverage.state is S.SOURCE_NOT_OPERATIONAL)

    @property
    def raw_lead_ids(self) -> tuple[str, ...]:
        return tuple(sorted(lead.lead_id for item in self.executions for lead in item.original.leads))

    @property
    def outside_universe_lead_ids(self) -> tuple[str, ...]:
        eligible = set(self.universe.instrument_ids)
        return tuple(sorted(lead.lead_id for item in self.executions for lead in item.original.leads if lead.canonical_instrument_id not in eligible))

    def verify(self) -> None:
        if replace(self) != self:
            raise DiscoveryOrchestrationError("DISCOVERY_BATCH_TAMPERED")


def orchestrate_whole_market_discovery(*, as_of: datetime, universe: UniverseSnapshot,
        instruments: tuple[NseEquityInstrument, ...], registry: MultiFunnelDiscoveryRegistry,
        read_sources: SourceReader) -> WholeMarketDiscoveryBatch:
    """One bounded pass; reads each callable source once and never writes/retries."""
    cutoff = _utc(as_of)
    _verify_universe(universe, instruments, cutoff)
    _verify_registry(registry)
    executions = []
    for entry in registry.entries:
        binding = next((item for item in _BINDINGS if item[0] is entry.funnel_id), None)
        if binding is None:
            executions.append(DiscoveryFunnelExecution(DiscoveryExecutionState.NOT_EXECUTABLE,
                adapters.unavailable_adapter(funnel_id=entry.funnel_id, as_of=cutoff)))
            continue
        try:
            sources = read_sources(entry.funnel_id, cutoff)
            if sources is not None and not isinstance(sources, tuple):
                raise TypeError("canonical immutable source tuple required")
        except Exception:
            # Deliberately do not inspect/serialize exception arguments or URLs.
            executions.append(_failure(entry.funnel_id, cutoff, DiscoveryExecutionState.SOURCE_READ_FAILED))
            continue
        if sources is None:
            executions.append(_failure(entry.funnel_id, cutoff, DiscoveryExecutionState.SOURCE_UNAVAILABLE))
            continue
        references: tuple[tuple[str, str], ...] = ()
        adapter_invoked = False
        try:
            keyed = tuple((getattr(item, binding[3]), item.fingerprint, item) for item in sources)
            references = tuple(sorted((key, fp) for key, fp, _ in keyed))
            # Do not let adapter first-record-wins order resolve conflicting
            # source identity. Exact replays still reach its canonical dedup.
            if any(len({fp for key, fp in references if key == source_id}) > 1 for source_id, _ in references):
                executions.append(_failure(entry.funnel_id, cutoff, DiscoveryExecutionState.SOURCE_CONFLICT, references, len(sources)))
                continue
            ordered = tuple(item for _, _, item in sorted(keyed, key=lambda row: row[:2]))
            if entry.funnel_id is F.SECTOR_ROTATION:
                for item in ordered:
                    # The source has a create/manifest convention, not verify().
                    # Compare; never repair the supplied source or fingerprint.
                    rebuilt = adapters.Top3OpportunityFinderRun.create(**{
                        f.name: getattr(item, f.name) for f in fields(item) if f.name not in ("run_id", "fingerprint")})
                    if rebuilt != item:
                        raise ValueError("source manifest mismatch")
            adapter_invoked = True
            result = binding[1](as_of=cutoff, **{binding[2]: ordered})
            if result.as_of != cutoff or result.funnel_id is not entry.funnel_id:
                raise ValueError("adapter result context mismatch")
            executions.append(DiscoveryFunnelExecution(DiscoveryExecutionState.EVALUATED, result, references, len(sources)))
        except Exception:
            # Isolate a corrupt source/adapter, but not BaseException, process
            # interrupts or master universe/registry invariant failures.
            safe = tuple(pair for pair in references if isinstance(pair[0], str) and isinstance(pair[1], str)
                and re.fullmatch(r"[A-Za-z0-9._:-]+", pair[0]) and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", pair[1]))
            state = DiscoveryExecutionState.ADAPTER_FAILED if adapter_invoked else DiscoveryExecutionState.SOURCE_VALIDATION_FAILED
            executions.append(_failure(entry.funnel_id, cutoff, state, safe, len(sources)))
    return WholeMarketDiscoveryBatch(cutoff, universe, instruments, registry, tuple(executions))


def serialize_whole_market_discovery(value: WholeMarketDiscoveryBatch) -> str:
    value.verify()
    return json.dumps(_payload(value) | {"fingerprint": value.fingerprint}, sort_keys=True, separators=(",", ":"))


def _failure_coverage(funnel, state):
    coverage_state = (S.EVIDENCE_CONFLICTED if state is DiscoveryExecutionState.SOURCE_CONFLICT else
        S.DATA_BLOCKED if state in (DiscoveryExecutionState.ADAPTER_FAILED, DiscoveryExecutionState.SOURCE_VALIDATION_FAILED) else S.SOURCE_NOT_OPERATIONAL)
    return adapters.DiscoveryAdapterCoverage(funnel, A.SOURCE_BLOCKED, coverage_state, 0, 0, (),
        reason_codes=(R.SOURCE_DUPLICATE_CONFLICT,) if state is DiscoveryExecutionState.SOURCE_CONFLICT else (R.SOURCE_LINEAGE_INVALID,))


def _failure(funnel, cutoff, state, references=(), source_records_supplied=None):
    result = adapters.DiscoveryAdapterResult(funnel, cutoff, (), _failure_coverage(funnel, state))
    return DiscoveryFunnelExecution(state, result, references, source_records_supplied)


def _scope(result, eligible):
    retained = tuple(item for item in result.leads if item.canonical_instrument_id in eligible)
    excluded = len(result.leads) - len(retained)
    if not excluded:
        return result
    c = result.coverage
    coverage = replace(c, lead_ids=tuple(item.lead_id for item in retained),
        securities_examined=len({item.canonical_instrument_id for item in retained}),
        identity_blocked=c.identity_blocked + excluded,
        state=c.state if retained else S.IDENTITY_BLOCKED,
        reason_codes=tuple(set((*c.reason_codes, R.SOURCE_IDENTITY_INVALID))))
    return replace(result, leads=retained, coverage=coverage)


def _envelope_coverage(result, eligible_count):
    c = result.coverage
    state = (DiscoveryCoverageState.LEADS_EMITTED if result.leads else
        DiscoveryCoverageState.EVALUATED_NO_LEADS if c.state is S.EVALUATED_NO_LEADS else
        DiscoveryCoverageState.POLICY_BLOCKED if c.state is S.POLICY_BLOCKED else
        DiscoveryCoverageState.NOT_EVALUATED if c.state in (S.NOT_EVALUATED, S.SOURCE_NOT_OPERATIONAL) else DiscoveryCoverageState.DATA_BLOCKED)
    # Adapters count source observations, not every eligible security examined.
    # Only emitted exact securities prove identifiable per-security coverage.
    proven = len({item.canonical_instrument_id for item in result.leads})
    return FunnelCoverage(result.funnel_id, eligible_count, proven, proven, c.lead_ids,
        c.data_blocked, c.policy_blocked, c.identity_blocked, c.conflicted, c.stale, 0, state)


def _verify_adapter(result):
    result.verify()
    if replace(result.coverage) != result.coverage or replace(result) != result:
        raise DiscoveryOrchestrationError("DISCOVERY_ADAPTER_TAMPERED")


def _verify_registry(registry):
    if not isinstance(registry, MultiFunnelDiscoveryRegistry):
        raise DiscoveryOrchestrationError("DISCOVERY_REGISTRY_REQUIRED")
    registry.verify()
    if registry != multi_funnel_discovery_registry():
        raise DiscoveryOrchestrationError("DISCOVERY_REGISTRY_NOT_CANONICAL")


def _verify_universe(universe, instruments, cutoff):
    if not isinstance(universe, UniverseSnapshot) or not isinstance(instruments, tuple):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_REQUIRED")
    if not universe.snapshot_id or not universe.source or _utc(universe.as_of) > cutoff:
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_PIT_INVALID")
    if not instruments or not all(isinstance(item, NseEquityInstrument) for item in instruments):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_RECORDS_REQUIRED")
    if len({item.instrument_id for item in instruments}) != len(instruments):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_IDENTITY_AMBIGUOUS")
    if any(_utc(item.data_as_of) > _utc(universe.as_of) for item in instruments):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_FUTURE_RECORD")
    rebuilt = build_universe_snapshot(snapshot_id=universe.snapshot_id, as_of=universe.as_of,
        source=universe.source, instruments=instruments, version=universe.version)
    if any(getattr(universe, name) != getattr(rebuilt, name) for name in (
        "checksum", "instrument_ids", "total_records", "eligible_security_count", "excluded_count")):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_CONTENT_MISMATCH")
    if not set(rebuilt.warnings) <= set(universe.warnings):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_SCOPE_MISSING")
    eligible = set(universe.instrument_ids)
    if any(item.instrument_id in eligible and (
        not isinstance(item.isin, str) or not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", item.isin)
        or item.instrument_id != "NSE:" + item.isin) for item in instruments):
        raise DiscoveryOrchestrationError("DISCOVERY_UNIVERSE_CANONICAL_SECURITY_REQUIRED")
    _plain(universe)
    _plain(instruments)


def _utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DiscoveryOrchestrationError("DISCOVERY_EXPLICIT_AS_OF_REQUIRED")
    return value.astimezone(UTC)


def _plain(value):
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {item.name: _plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    if value is None or type(value) in (str, int, bool):
        return value
    raise DiscoveryOrchestrationError("DISCOVERY_SERIALIZATION_TYPE_INVALID")


def _payload(value):
    return {"contract": WHOLE_MARKET_DISCOVERY_CONTRACT, "batch_id": value.batch_id,
        "as_of": _utc(value.as_of).isoformat(), "universe": _plain(value.universe),
        "instruments": _plain(value.instruments), "registry": _plain(value.registry),
        "executions": _plain(value.executions), "envelope": _plain(value.envelope),
        "candidate_union": _plain(value.candidate_union),
        "executable_funnels": _plain(value.executable_funnels), "evaluated_funnels": _plain(value.evaluated_funnels),
        "source_not_operational_funnels": _plain(value.source_not_operational_funnels),
        "raw_lead_ids": value.raw_lead_ids, "outside_universe_lead_ids": value.outside_universe_lead_ids}
