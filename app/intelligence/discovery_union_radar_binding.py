"""Bounded, stored-only security union -> existing Radar -> canonical61 binding.

No discovery, diagnostic, setup or ranking algorithm lives here. Native source
objects are verified, never repaired. Session-local replay protection is bounded
and deliberately has no eviction, background worker or persistence side effect.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
import re
from threading import RLock
from typing import Protocol

from app.domain.canonical_diagnostic_strategy import CanonicalDiagnosticDefinitionReader
from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.historical.guard import BacktestLookaheadGuard
from app.historical.models import UniverseMembership
from app.historical.security_identity_selector import resolve_historical_security_identity
from app.historical.security_master import HistoricalSecurityIdentity
from app.intelligence import multi_funnel_discovery_adapters as adapters
from app.intelligence.multi_funnel_candidate_union import CanonicalDiscoveryPoolItem
from app.intelligence.multi_funnel_discovery import (
    CanonicalDiscoveryLead, DiscoveryFunnelId as F, DiscoveryFunnelStatus,
    discovery_lead_payload, multi_funnel_discovery_registry,
)
from app.intelligence.multi_funnel_orchestration import WholeMarketDiscoveryBatch
from app.intelligence.radar_diagnostic_orchestration import (
    CanonicalDiagnosticHorizon, CanonicalRadarEvidenceAssembler,
    RadarDiagnosticEvaluation, RadarToHsiDiagnosticOrchestrator,
)
from app.market_data.current_sector_rotation import CurrentSectorRankingArtifact
from app.market_data.reference_data.tick_size import NseTickSizeObservation
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as Family
from app.universe_analysis.service import (
    AssembledStockEvidence, Canonical61DiagnosticRunner, NseUniverseSource,
    StockDiagnosticInputAssembler,
)
from app.universe_analysis.technical_diagnostic_input import CanonicalTechnicalDiagnosticInput


CONTRACT_ID = "canonical-discovery-union-to-brain-handoff"
CONTRACT_VERSION = "v1"
CONTRACT_FINGERPRINT = "sha256:731399dfbca758763dda0ad9ee1350aa50cd433ab183bb62fc710e4b5826b1e8"
BINDING = "canonical-discovery-union-to-existing-radar61-runtime-binding/v1"
_CONTEXTUAL = frozenset({F.MARKET_DISLOCATION, F.HOLDING_STATE_CHANGE, F.WATCHLIST_STATE_CHANGE})
_FP = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
_SECURITY = re.compile(r"NSE:[A-Z]{2}[A-Z0-9]{9}[0-9]\Z")


class UnionRadarBindingError(ValueError):
    """Only fixed, non-secret reason codes cross the boundary."""


class InspectionTemporalRequirement(StrEnum):
    CURRENT_DESCRIPTIVE = "CURRENT_DESCRIPTIVE"
    STRICT_PIT = "STRICT_PIT"


class InspectionState(StrEnum):
    EVALUATED = "EVALUATED"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    BLOCKED = "BLOCKED"


class SnapshotReader(Protocol):
    """Existing snapshot repository's read method only, not a new store."""
    def get_snapshot(self, snapshot_id: str) -> CoreApiSnapshot | None: ...


@dataclass(frozen=True, slots=True)
class InspectionContext:
    temporal_requirement: InspectionTemporalRequirement
    canonical_horizon: CanonicalDiagnosticHorizon

    def __post_init__(self):
        _require(isinstance(self.temporal_requirement, InspectionTemporalRequirement)
                 and isinstance(self.canonical_horizon, CanonicalDiagnosticHorizon), "SCHEMA_INVALID")

    def payload(self):
        self.__post_init__()
        registry = multi_funnel_discovery_registry()
        return dict(purpose="MARKET_WIDE_DISCOVERY_REVIEW",
                    temporal_requirement=self.temporal_requirement.value,
                    canonical_horizon=self.canonical_horizon.value,
                    # Discovery-review scope only. Rule applicability remains POLICY_UNSET.
                    horizon_authority_reference=f"{registry.registry_id}/{registry.version}:{registry.fingerprint}")


@dataclass(frozen=True, slots=True)
class UnionInspectionResult:
    state: InspectionState
    inspection_request_id: str | None
    handoff_json: str | None
    handoff_fingerprint: str | None
    radar: RadarDiagnosticEvaluation | None
    reason_codes: tuple[str, ...]
    prior_handoff_fingerprint: str | None = None
    diagnostic_strategy_fingerprint: str | None = None
    deep_input_fingerprint: str | None = None
    actionability: str = "WATCH_ONLY"
    execution_status: str = "NON_EXECUTABLE"

    def __post_init__(self):
        _require(isinstance(self.state, InspectionState)
                 and self.actionability == "WATCH_ONLY" and self.execution_status == "NON_EXECUTABLE",
                 "RESULT_AUTHORITY_INVALID")
        _require((self.handoff_json is None) == (self.handoff_fingerprint is None), "RESULT_CONTENT_INVALID")
        if self.handoff_json is not None:
            _require(self.handoff_fingerprint == "sha256:" + sha256(self.handoff_json.encode()).hexdigest(),
                     "RESULT_CONTENT_INVALID")
        ready = self.state is not InspectionState.BLOCKED
        _require(ready == (self.radar is not None and self.radar.receipt is not None)
                 and bool(self.reason_codes) != ready, "RESULT_STATE_INVALID")
        if ready:
            _require(self.inspection_request_id is not None and self.handoff_json is not None, "RESULT_CONTENT_INVALID")
            _require(self.diagnostic_strategy_fingerprint is not None and self.deep_input_fingerprint is not None
                     and _FP.fullmatch(self.diagnostic_strategy_fingerprint)
                     and _FP.fullmatch(self.deep_input_fingerprint), "RESULT_CONTENT_INVALID")
            self.radar.receipt.verify()
        else:
            _require(self.diagnostic_strategy_fingerprint is None and self.deep_input_fingerprint is None,
                     "RESULT_STATE_INVALID")


class _AssemblyCapture:
    """Reference capture for complete input correlation, not evidence assembly."""
    def __init__(self, assembler):
        self.assembler, self.evidence, self.fingerprint = assembler, None, None

    def assemble_for_radar(self, **kwargs):
        self.evidence = self.assembler.assemble_for_radar(**kwargs)
        # Validate complete serialization before any diagnostic runs. A bad
        # nested input must not fail only after evaluation and permit a retry.
        self.fingerprint = content_fingerprint(self.evidence)
        return self.evidence


class StoredCanonicalRadarEvidenceAssembler:
    """Concrete binding to existing stored input assembly; no provider fallback.

    ``read_technical`` must return the native certified current-descriptive input
    from the existing canonical technical reader. The stock assembler retains
    its native financial hook and PIT observation guard unchanged.
    """
    def __init__(self, *, universe: NseUniverseSource, assembler: StockDiagnosticInputAssembler,
                 read_technical: Callable[[str, datetime], CanonicalTechnicalDiagnosticInput | None]):
        self._universe, self._assembler, self._technical = universe, assembler, read_technical

    def assemble_for_radar(self, *, canonical_security_id: str, evaluation_as_of: datetime) -> AssembledStockEvidence:
        cutoff = _utc(evaluation_as_of)
        instruments = tuple(item for item in self._universe.instruments_as_of(cutoff)
                            if item.instrument_id == canonical_security_id)
        _require(len(instruments) == 1 and instruments[0].data_as_of <= cutoff
                 and instruments[0].instrument_id == "NSE:" + (instruments[0].isin or "")
                 and instruments[0].exchange == "NSE" and instruments[0].security_type == "EQUITY",
                 "IDENTITY_INVALID")
        technical = self._technical(canonical_security_id, cutoff)
        _require(technical is not None, "CANONICAL_TECHNICAL_INPUT_REQUIRED")
        technical.__post_init__()
        return self._assembler.assemble(instruments[0], cutoff, technical_input=technical)


class UnionRadarRuntimeBinding:
    """One explicitly bounded session, one diagnosis per security/cutoff/context.

    The dispatch lead is required to be the *unique* verified admitting origin,
    never the first origin. All others are retained with non-admitting roles.
    Multiple admitting origins currently fail closed pending a native multi-lead
    Radar receipt; they are not reduced by rank, input order or hit count.
    """
    def __init__(self, *, snapshots: SnapshotReader, governance: CanonicalDiagnosticDefinitionReader,
                 evidence_assembler: CanonicalRadarEvidenceAssembler | None,
                 runner: Canonical61DiagnosticRunner, request_limit: int = 100):
        _require(type(request_limit) is int and 1 <= request_limit <= 100, "REQUEST_BOUND_INVALID")
        self._snapshots, self._governance = snapshots, governance
        self._assembler, self._runner = evidence_assembler, runner
        self._limit = request_limit
        self._completed: dict[str, UnionInspectionResult] = {}
        self._lock = RLock()

    def inspect(self, *, master: WholeMarketDiscoveryBatch, candidate_id: str,
                inspection_as_of: datetime, context: InspectionContext,
                identity_snapshot_ids: tuple[str, ...], membership_snapshot_ids: tuple[str, ...],
                cash_segment_observation: NseTickSizeObservation | None) -> UnionInspectionResult:
        # The lock covers verification + the single delegated call, including
        # simultaneous identical submissions. No eviction permits an old replay.
        with self._lock:
            return self._inspect(master, candidate_id, inspection_as_of, context,
                                 identity_snapshot_ids, membership_snapshot_ids, cash_segment_observation)

    def _inspect(self, master, candidate_id, at, context, identity_ids, membership_ids, segment):
        key = handoff = fp = None
        try:
            cutoff = _utc(at)
            context.__post_init__()
            master.verify()
            candidates = tuple(c for c in master.candidate_union.candidates if c.candidate_id == candidate_id)
            _require(len(candidates) == 1, "CANDIDATE_MISSING_OR_CONFLICTED")
            candidate = candidates[0]
            candidate.verify()
            _require(bool(_SECURITY.fullmatch(candidate.canonical_instrument_id)), "IDENTITY_INVALID")
            identity = dict(contract_id=CONTRACT_ID, contract_version=CONTRACT_VERSION,
                            canonical_security_id=candidate.canonical_instrument_id,
                            inspection_as_of=cutoff, inspection_context=context.payload())
            key = "brain-inspection-request:" + content_fingerprint(identity).removeprefix("sha256:")
            # Retain immutable source content even when admission fails.
            payload = identity | dict(contract_fingerprint=CONTRACT_FINGERPRINT, inspection_request_id=key,
                source_master=(master.batch_id, master.fingerprint),
                source_union=(master.candidate_union.batch_id, master.candidate_union.fingerprint),
                source_candidate=(candidate.candidate_id, candidate.fingerprint),
                universe_reference=master.universe, union_as_of=master.as_of,
                union_formed_at=None, request_created_at=None, detected_at=None,
                materiality=None, confidence=None, context_references=(),
                origins=tuple(discovery_lead_payload(o.lead) for o in candidate.origins),
                consumer_binding=BINDING, actionability="WATCH_ONLY", execution_status="NON_EXECUTABLE")
            handoff = canonical_json(payload)
            fp = content_fingerprint(payload)
            _require(master.as_of <= cutoff, "FUTURE_EVIDENCE")
            _require(context.temporal_requirement is InspectionTemporalRequirement.CURRENT_DESCRIPTIVE,
                     "HISTORICAL_PIT_NOT_PROVEN")
            proofs = self._identity(master, candidate, cutoff, identity_ids, membership_ids, segment)
            admitting, origins = self._origins(master, candidate, cutoff, context)
            payload |= dict(identity_and_membership_proofs=proofs, origin_admission=origins)
            definition = self._runner.authorize(self._governance)
            _require(max(definition.created_at, definition.registered_at) <= cutoff, "FUTURE_GOVERNANCE")
            payload["canonical_diagnostic_definition"] = (
                definition.strategy_id, definition.strategy_version, definition.semantic_fingerprint,
                definition.created_at, definition.registered_at)
            handoff, fp = canonical_json(payload), content_fingerprint(payload)
            prior = self._completed.get(key)
            if prior is not None:
                if fp != prior.handoff_fingerprint:
                    return UnionInspectionResult(InspectionState.BLOCKED, key, handoff, fp, None,
                        ("DUPLICATE_REQUEST_AMBIGUOUS",), prior.handoff_fingerprint)
                return replace(prior, state=InspectionState.IDEMPOTENT_REPLAY)
            _require(len(self._completed) < self._limit, "REQUEST_BOUND_EXCEEDED")
            _require(self._assembler is not None, "CONSUMER_BINDING_NOT_READY")
            _require(len(admitting) == 1, "MULTI_ADMITTING_RADAR_RECEIPT_NOT_SUPPORTED" if admitting else "NO_ADMITTING_ORIGIN")
            # Native lead validation, evidence validation, all rule delegation and
            # result/readiness mapping remain entirely inside the existing bridge.
            capture = _AssemblyCapture(self._assembler)
            radar = RadarToHsiDiagnosticOrchestrator(evidence_assembler=capture, runner=self._runner).evaluate_one_lead(
                admitting[0], evaluation_as_of=cutoff, canonical_horizon=context.canonical_horizon)
            if radar.receipt is None:
                return UnionInspectionResult(InspectionState.BLOCKED, key, handoff, fp, None,
                                             tuple(r.value for r in radar.reason_codes))
            result = UnionInspectionResult(InspectionState.EVALUATED, key, handoff, fp, radar, (),
                diagnostic_strategy_fingerprint=definition.semantic_fingerprint,
                deep_input_fingerprint=capture.fingerprint)
            self._completed[key] = result
            return result
        except UnionRadarBindingError as error:
            return UnionInspectionResult(InspectionState.BLOCKED, key, handoff, fp, None, (str(error),))
        except Exception:
            # Do not leak repository exceptions, URLs, credentials or repr(payload).
            return UnionInspectionResult(InspectionState.BLOCKED, key, handoff, fp, None, ("SOURCE_PROVENANCE_INVALID",))

    def _snapshot(self, identifier, family, cutoff):
        row = self._snapshots.get_snapshot(identifier)
        _require(isinstance(row, CoreApiSnapshot) and row.snapshot_id == identifier
                 and row.family is family and row.schema_version == "v1"
                 and bool(_FP.fullmatch(row.fingerprint)), "INSUFFICIENT_PROVENANCE")
        _require(_utc(row.created_at) <= cutoff, "FUTURE_EVIDENCE")
        return row

    def _identity(self, master, candidate, cutoff, identity_ids, membership_ids, segment):
        _require(isinstance(identity_ids, tuple) and identity_ids and isinstance(membership_ids, tuple)
                 and membership_ids and len(set(identity_ids)) == len(identity_ids)
                 and len(set(membership_ids)) == len(membership_ids), "IDENTITY_INVALID")
        boundaries = tuple(sorted({cutoff, *(o.lead.discovery_as_of for o in candidate.origins)}))
        identities = tuple(self._snapshot(i, Family.HISTORICAL_SECURITY_IDENTITY, cutoff) for i in sorted(identity_ids))
        memberships = tuple(self._snapshot(i, Family.HISTORICAL_UNIVERSE_MEMBERSHIP, cutoff) for i in sorted(membership_ids))
        for row in (*identities, *memberships):
            _require(row.fingerprint == sha256(repr(row.payload).encode()).hexdigest(), "SOURCE_FINGERPRINT_INVALID")
        _require(all(isinstance(r.payload, HistoricalSecurityIdentity) for r in identities)
                 and all(isinstance(r.payload, UniverseMembership) for r in memberships), "IDENTITY_INVALID")
        instrument = next(i for i in master.instruments if i.instrument_id == candidate.canonical_instrument_id)
        _require(instrument.exchange == "NSE" and instrument.security_type == "EQUITY"
                 and instrument.isin == candidate.isin and instrument.provenance_reference,
                 "UNIVERSE_SCOPE_UNSUPPORTED")
        _require(segment is not None, "CASH_SEGMENT_PROVENANCE_REQUIRED")
        segment.__post_init__()
        _require(segment.canonical_instrument_id == candidate.canonical_instrument_id and segment.isin == candidate.isin
                 and segment.source_class.value == "OFFICIAL_EXCHANGE"
                 and segment.evidence_kind.value == "DIRECT_SOURCE"
                 and segment.evidence_sufficiency.value == "SUFFICIENT", "CASH_SEGMENT_PROVENANCE_REQUIRED")
        for boundary in boundaries:
            _require(instrument.data_as_of <= boundary, "FUTURE_IDENTITY_CLASSIFICATION")
            known_identities = tuple(r.payload for r in identities if r.created_at <= boundary)
            resolved = resolve_historical_security_identity(known_identities,
                canonical_instrument_id=candidate.canonical_instrument_id, as_of=boundary)
            _require(resolved.status.value == "RESOLVED" and resolved.isin == candidate.isin
                     and resolved.exchange == "NSE" and resolved.source_reference, "IDENTITY_INVALID")
            selected = next(i for i in known_identities if i.identity_id == resolved.identity_id)
            _require(selected.source_fingerprint and _FP.fullmatch(selected.source_fingerprint)
                     and selected.version and selected.source, "INSUFFICIENT_PROVENANCE")
            matches = tuple(r.payload for r in memberships if r.created_at <= boundary
                and r.payload.instrument_id == candidate.canonical_instrument_id
                and r.payload.universe_id == master.universe.snapshot_id
                and BacktestLookaheadGuard().membership(r.payload, boundary).value == "ELIGIBLE")
            _require(len(matches) == 1 and matches[0].status.value == "ACTIVE"
                     and matches[0].source and matches[0].provenance, "UNIVERSE_MEMBERSHIP_MISSING")
            _require(segment.observed_at <= boundary
                     and (segment.effective_from is None or segment.effective_from <= boundary)
                     and (segment.effective_to is None or boundary < segment.effective_to), "FUTURE_EVIDENCE")
        return tuple((r.snapshot_id, r.fingerprint, r.created_at) for r in (*identities, *memberships)) + (
            (segment.record_id, segment.evidence_fingerprint, segment.observed_at),
            (instrument.provenance_reference, content_fingerprint(instrument), instrument.data_as_of))

    def _origins(self, master, candidate, cutoff, context):
        admitting, proof = [], []
        registry = multi_funnel_discovery_registry()
        for origin in candidate.origins:
            lead = origin.lead
            _require(lead.funnel_id not in _CONTEXTUAL, "UNSUPPORTED_CONTEXTUAL_ORIGIN")
            _require(lead.discovery_as_of <= master.as_of <= cutoff
                     and all(r.known_at <= lead.discovery_as_of for r in lead.lineage), "FUTURE_EVIDENCE")
            entry = registry.get(lead.funnel_id)
            execution = next(e for e in master.executions if e.original.funnel_id is lead.funnel_id)
            # Exact native replay proves the emitted lead, including every nested
            # source reference. No synthetic union lead and no dropping research.
            native, envelopes = [], []
            if lead.funnel_id is F.SECTOR_ROTATION:
                for identifier, fp in execution.source_references:
                    row = self._snapshot(identifier, Family.TOP3_OPPORTUNITY_FINDER_RUN, lead.discovery_as_of)
                    value = row.payload
                    _require(isinstance(value, adapters.Top3OpportunityFinderRun), "INSUFFICIENT_PROVENANCE")
                    rebuilt = adapters.Top3OpportunityFinderRun.create(**{f.name: getattr(value, f.name)
                        for f in fields(value) if f.name not in {"run_id", "fingerprint"}})
                    _require(rebuilt == value and row.fingerprint == fp == value.fingerprint, "SOURCE_FINGERPRINT_INVALID")
                    native.append(value)
                    envelopes.append(_envelope_reference(row))
                regenerated = adapters.adapt_sector_rotation(as_of=master.as_of, runs=tuple(native))
                source = next(v for v in native if v.run_id == lead.parent_discovery_id)
                rank_row = self._snapshot(source.ranking_id, Family.CURRENT_SECTOR_RANKING, lead.discovery_as_of)
                ranking = rank_row.payload
                _require(isinstance(ranking, CurrentSectorRankingArtifact)
                         and CurrentSectorRankingArtifact.create(ranking.report) == ranking
                         and ranking.fingerprint == rank_row.fingerprint, "SOURCE_FINGERPRINT_INVALID")
                envelopes.append(_envelope_reference(rank_row))
                _require(source.as_of == ranking.ranking_as_of == cutoff, "SOURCE_FRESHNESS_NOT_PROVEN")
                _require(source.top3 == ranking.report.top3
                         and source.latest_completed_session == ranking.latest_completed_session
                         and ranking.latest_completed_session is not None
                         and ranking.latest_completed_session <= cutoff, "SOURCE_PROVENANCE_INVALID")
                rows = tuple(r for r in ranking.report.constituents if r.instrument_id == candidate.canonical_instrument_id)
                _require(rows and {r.sector for r in rows} <= set(ranking.report.top3)
                         and len({r.sector for r in rows}) == 1
                         and all(r.isin == candidate.isin for r in rows), "EXACT_SECTOR_MEMBERSHIP_REQUIRED")
                proof.append((lead.lead_id, "ADMITTING", ranking.ranking_id, ranking.fingerprint,
                              ranking.ranking_policy_version, source.run_id, source.fingerprint))
                admitting.append(lead)
            elif lead.funnel_id in {F.FUNDAMENTAL_INFLECTION, F.COMPOUNDER}:
                family, adapter, keyword = (
                    (Family.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW, adapters.adapt_fundamental_inflection, "observations")
                    if lead.funnel_id is F.FUNDAMENTAL_INFLECTION else
                    (Family.COMPOUNDER_PROSPECTIVE_SHADOW, adapters.adapt_compounder, "observations"))
                for identifier, fp in execution.source_references:
                    row = self._snapshot(identifier, family, lead.discovery_as_of)
                    row.payload.verify()
                    _require(row.fingerprint == fp == row.payload.fingerprint, "SOURCE_FINGERPRINT_INVALID")
                    native.append(row.payload)
                    envelopes.append(_envelope_reference(row))
                regenerated = adapter(as_of=master.as_of, **{keyword: tuple(native)})
                proof.append((lead.lead_id, "NON_ADMITTING_RESEARCH", entry.status.value,
                              *entry.fail_closed_codes))
            else:
                # No fake producer proof for yet-unbound sources, including
                # Pre-Breakout successor versions and policy-transmission context.
                raise UnionRadarBindingError("NATIVE_ORIGIN_PROOF_BINDING_UNAVAILABLE")
            _require(regenerated == execution.original and lead in regenerated.leads, "SOURCE_PROVENANCE_INVALID")
            proof.append((lead.lead_id, "NATIVE_SOURCE_ENVELOPES", tuple(sorted(envelopes))))
            if lead in admitting:
                _require(entry.status is DiscoveryFunnelStatus.OPERATIONAL and lead.funnel_version == entry.version,
                         "DISCOVERY_FAMILY_NOT_ACTIVE")
                _require(context.canonical_horizon.value in {h.value for h in lead.intended_horizons}
                         and context.canonical_horizon.value in {h.value for h in entry.horizons}, "HORIZON_NOT_GOVERNED")
        return tuple(admitting), tuple(proof)


def _utc(value):
    _require(isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None,
             "EXPLICIT_AS_OF_REQUIRED")
    return value.astimezone(UTC)


def _envelope_reference(row):
    return (row.snapshot_id, row.family.value, row.schema_version, row.record_type,
            row.fingerprint, _utc(row.created_at).isoformat())


def _require(condition, reason):
    if not condition:
        raise UnionRadarBindingError(reason)
