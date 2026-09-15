"""Real canonical61 integration; synthetic stored evidence, no production I/O."""
import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import inspect
import json

import pytest

import app.intelligence.discovery_union_radar_binding as m
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import HistoricalSecurityIdentity, HistoricalSecurityStatus
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F, multi_funnel_discovery_registry
from app.intelligence.multi_funnel_orchestration import orchestrate_whole_market_discovery
from app.market_data.current_sector_rotation import (
    CurrentConstituentResolution, CurrentSectorRankingArtifact, CurrentSectorRotationReport, SectorBackfillPlan,
)
from app.market_data.models import Exchange
from app.market_data.reference_data.tick_size import (
    NseTickSizeObservation, NseTickSizeSegment, TickSizeAvailabilitySemantics,
    TickSizeSourceClass, nse_tick_size_observation_fingerprint,
)
from app.production_v1.top3_opportunity_finder import Top3OpportunityFinderRun
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as Family
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import Canonical61DiagnosticRunner, StockDiagnosticInputAssembler, build_universe_snapshot
from app.universe_analysis import technical_diagnostic_input as technical
from tests.unit.test_canonical_61_runner_governance import _definition
from tests.unit.test_multi_funnel_discovery_adapters import _inflection
from tests.unit.test_technical_diagnostic_input import _input

T = datetime(2026, 9, 6, 12, tzinfo=UTC)
SECURITY = "NSE:INE372A01015"
FP = "a" * 64
CONTEXT = m.InspectionContext(m.InspectionTemporalRequirement.CURRENT_DESCRIPTIVE, m.CanonicalDiagnosticHorizon.POSITIONAL)


class Snapshots:
    def __init__(self): self.rows = {}
    def get_snapshot(self, identifier): return self.rows.get(identifier)


class Governance:
    def get_canonical_diagnostic_strategy_definition(self, reference): return _definition()


class CountingRunner(Canonical61DiagnosticRunner):
    def __init__(self): super().__init__(); self.calls = 0
    def run(self, evidence, **kwargs):
        self.calls += 1
        return super().run(evidence, **kwargs)


class StoredInputs:
    def __init__(self, instrument): self.instrument = instrument; self.calls = 0
    def instruments_as_of(self, at): return (self.instrument,)
    def observations_as_of(self, at): self.calls += 1; return ()


def technical_fixture(security, at):
    # Re-key a synthetic certified series for the integration fixture; its
    # native content fingerprint is constructed BEFORE it enters production code.
    original = _input(as_of=at)
    def snapshot(value):
        return replace(value, observations=tuple(replace(o, instrument=replace(o.instrument, id=security))
                                                 for o in value.observations))
    values = {f.name: getattr(original, f.name) for f in fields(original) if f.name != "fingerprint"}
    values.update(canonical_instrument_id=security, daily_snapshot=snapshot(original.daily_snapshot),
                  weekly_snapshot=snapshot(original.weekly_snapshot))
    ordered = (values["canonical_instrument_id"], values["as_of"], values["daily_snapshot"], values["weekly_snapshot"],
        values["daily_source_read_fingerprints"], values["weekly_source_fingerprints"],
        values["daily_price_continuity_ready"], values["daily_volume_continuity_ready"], values["weekly_volume_continuity_ready"],
        values["current_descriptive_state"], values["strict_historical_pit_state"], values["source_policy_id"], values["source_policy_version"])
    return technical.CanonicalTechnicalDiagnosticInput(**values, fingerprint=technical._fingerprint(technical._input_values(*ordered)))


def fixture(*, multi=False, at=T, assembler=True):
    source = Snapshots()
    instrument = NseEquityInstrument(SECURITY, "APARINDS", SECURITY[4:], "Industrials", None,
        "ACTIVE", None, True, T - timedelta(days=3), "NSE_OFFICIAL_EXPORT", "official-master:fixture")
    universe = build_universe_snapshot(snapshot_id="nse-universe:fixture", as_of=instrument.data_as_of,
                                       source=instrument.source, instruments=(instrument,))
    plan = SectorBackfillPlan(False, (), 0, 0, 0, 0, (), 0, ())
    report = CurrentSectorRotationReport(at, at - timedelta(days=1), 252, (),
        (CurrentConstituentResolution("Industrials", "Nifty Industrials", instrument.symbol, instrument.isin,
                                     SECURITY, "EXACT_ISIN", True, "RESOLVED"),),
        (), (), ("Industrials",), ("Industrials",), plan, 0, 0, 0, ())
    ranking = CurrentSectorRankingArtifact.create(report)
    run = Top3OpportunityFinderRun.create(as_of=at, ranking_id=ranking.ranking_id,
        latest_completed_session=ranking.latest_completed_session, top3=report.top3,
        candidate_ids=(SECURITY,), excluded=(), assessment_ids=(), opportunity_ids=(),
        data_blocked_count=1, condition_not_met_count=0, valid_count=0, near_misses=())
    def row(identifier, family, value, fp, known):
        source.rows[identifier] = CoreApiSnapshot(identifier, family, "v1", type(value).__name__, fp, known, value)
    row(run.run_id, Family.TOP3_OPPORTUNITY_FINDER_RUN, run, run.fingerprint, at)
    row(ranking.ranking_id, Family.CURRENT_SECTOR_RANKING, ranking, ranking.fingerprint, at)
    source_map = {F.SECTOR_ROTATION: (run,)}
    if multi:
        inflection = _inflection()
        source_map[F.FUNDAMENTAL_INFLECTION] = (inflection,)
        row(inflection.observation_id, Family.INFLECTION_ACCOUNTING_PROSPECTIVE_SHADOW,
            inflection, inflection.fingerprint, inflection.as_of)
    master = orchestrate_whole_market_discovery(as_of=at, universe=universe, instruments=(instrument,),
        registry=multi_funnel_discovery_registry(), read_sources=lambda f, _: source_map.get(f, ()))
    identity = HistoricalSecurityIdentity("identity:fixture", SECURITY, instrument.isin, "NSE", instrument.symbol, "EQ",
        instrument.data_as_of, None, instrument.data_as_of, None, instrument.data_as_of, None,
        HistoricalSecurityStatus.ACTIVE, instrument.source, instrument.data_as_of, "v1",
        source_reference=instrument.provenance_reference, source_fingerprint=FP)
    membership = UniverseMembership("member:fixture", SECURITY, universe.snapshot_id, instrument.data_as_of,
        None, instrument.data_as_of, instrument.source, "official-membership:fixture", InstrumentLifecycle.ACTIVE)
    row("identity:fixture", Family.HISTORICAL_SECURITY_IDENTITY, identity, sha256(repr(identity).encode()).hexdigest(), identity.as_of)
    row("member:fixture", Family.HISTORICAL_UNIVERSE_MEMBERSHIP, membership, sha256(repr(membership).encode()).hexdigest(), membership.known_at)
    tick_values = dict(record_id="cash-segment:fixture", canonical_instrument_id=SECURITY, exchange=Exchange.NSE,
        segment=NseTickSizeSegment.NSE_CASH_EQUITY, isin=instrument.isin, tick_size=Decimal("0.05"),
        source_class=TickSizeSourceClass.OFFICIAL_EXCHANGE, source_name="NSE_CM_MASTER",
        source_artifact_fingerprint=FP, observed_at=instrument.data_as_of,
        effective_from=None, effective_to=None, availability_semantics=TickSizeAvailabilitySemantics.FIRST_OBSERVED_ONLY, warnings=())
    tick = NseTickSizeObservation(**tick_values, evidence_fingerprint=nse_tick_size_observation_fingerprint(**tick_values))
    stored = StoredInputs(instrument)
    assembly = m.StoredCanonicalRadarEvidenceAssembler(universe=stored, assembler=StockDiagnosticInputAssembler(stored),
        read_technical=technical_fixture) if assembler else None
    runner = CountingRunner()
    binding = m.UnionRadarRuntimeBinding(snapshots=source, governance=Governance(), evidence_assembler=assembly, runner=runner)
    args = dict(master=master, candidate_id=master.candidate_union.candidates[0].candidate_id,
        inspection_as_of=at, context=CONTEXT, identity_snapshot_ids=("identity:fixture",),
        membership_snapshot_ids=("member:fixture",), cash_segment_observation=tick)
    return binding, args, source, runner, stored


@pytest.mark.parametrize("multi", (False, True))
def test_real_union_existing_radar_real_runner_exact_61(multi):
    binding, args, _, runner, stored = fixture(multi=multi)
    result = binding.inspect(**args)
    assert result.state is m.InspectionState.EVALUATED, result.reason_codes
    assert runner.calls == stored.calls == 1
    receipt = result.radar.receipt
    assert tuple(r.rule_id for r in receipt.rule_references) == tuple(range(1, 62))
    assert any(r.diagnostic_result == "INSUFFICIENT_DATA" for r in receipt.rule_references)
    assert any(r.readiness.value == "PARTIAL" for r in receipt.rule_references)
    assert receipt.technical_temporal_readiness.value == "CURRENT_DESCRIPTIVE"
    payload = json.loads(result.handoff_json)
    assert len(payload["origins"]) == (2 if multi else 1)
    assert {o["funnel"] for o in payload["origins"]} == ({"SECTOR_ROTATION", "FUNDAMENTAL_INFLECTION"} if multi else {"SECTOR_ROTATION"})
    assert payload["inspection_context"]["canonical_horizon"] == "POSITIONAL"
    assert result.actionability == "WATCH_ONLY" and result.execution_status == "NON_EXECUTABLE"


def test_deterministic_identity_complete_content_and_repeated_idempotency():
    binding, args, _, runner, _ = fixture(multi=True)
    first = binding.inspect(**args)
    again = binding.inspect(**(args | {"inspection_as_of": T.astimezone(timezone(timedelta(hours=5, minutes=30)))}))
    assert first.state is m.InspectionState.EVALUATED, first.reason_codes
    assert again.state is m.InspectionState.IDEMPOTENT_REPLAY
    assert again.radar == first.radar and runner.calls == 1
    assert first.handoff_json == again.handoff_json
    payload = json.loads(first.handoff_json)
    identity = {k: payload[k] for k in ("contract_id", "contract_version", "canonical_security_id", "inspection_as_of", "inspection_context")}
    assert first.inspection_request_id == "brain-inspection-request:" + m.content_fingerprint(identity)[7:]
    assert first.handoff_fingerprint == "sha256:" + sha256(first.handoff_json.encode()).hexdigest()
    with pytest.raises(FrozenInstanceError): first.actionability = "OTHER"


def test_added_origin_at_same_cutoff_is_conflict_not_second_diagnosis():
    binding, args, source, runner, _ = fixture()
    first = binding.inspect(**args)
    _, newer, more, _, _ = fixture(multi=True)
    source.rows.update(more.rows)
    conflict = binding.inspect(**newer)
    assert first.state is m.InspectionState.EVALUATED
    assert conflict.reason_codes == ("DUPLICATE_REQUEST_AMBIGUOUS",)
    assert conflict.inspection_request_id == first.inspection_request_id
    assert conflict.prior_handoff_fingerprint == first.handoff_fingerprint
    assert len(json.loads(conflict.handoff_json)["origins"]) == 2 and runner.calls == 1


def test_parallel_replay_has_one_runner_call():
    binding, args, _, runner, _ = fixture()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: binding.inspect(**args), range(2)))
    assert sorted(r.state.value for r in results) == ["EVALUATED", "IDEMPOTENT_REPLAY"]
    assert runner.calls == 1


@pytest.mark.parametrize("field", ("fingerprint", "candidate_id", "canonical_instrument_id"))
def test_tampered_candidate_rejected_before_runner(field):
    binding, args, _, runner, _ = fixture()
    object.__setattr__(args["master"].candidate_union.candidates[0], field, "tampered")
    result = binding.inspect(**args)
    assert result.state is m.InspectionState.BLOCKED and runner.calls == 0


@pytest.mark.parametrize("mode", ("STRICT_PIT", "CAS_STRICT_PIT"))
def test_strict_historical_and_cas_never_masquerade_as_current(mode):
    binding, args, _, runner, _ = fixture()
    result = binding.inspect(**(args | {"context": m.InspectionContext(m.InspectionTemporalRequirement.STRICT_PIT,
                                                                                m.CanonicalDiagnosticHorizon.POSITIONAL)}))
    assert result.reason_codes == ("HISTORICAL_PIT_NOT_PROVEN",) and runner.calls == 0
    assert binding.inspect(**args).state is m.InspectionState.EVALUATED


def test_missing_assembler_auditable_without_runner():
    binding, args, _, runner, _ = fixture(assembler=False)
    result = binding.inspect(**args)
    assert result.reason_codes == ("CONSUMER_BINDING_NOT_READY",) and runner.calls == 0
    assert result.handoff_fingerprint and result.inspection_request_id


@pytest.mark.parametrize("mutation,reason", (
    ("future_cutoff", "FUTURE_EVIDENCE"), ("identity_missing", "IDENTITY_INVALID"),
    ("membership_missing", "IDENTITY_INVALID"), ("segment_missing", "CASH_SEGMENT_PROVENANCE_REQUIRED"),
    ("future_receipt", "FUTURE_EVIDENCE"), ("tampered_identity", "SOURCE_FINGERPRINT_INVALID"),
    ("tampered_run", "SOURCE_FINGERPRINT_INVALID"), ("missing_run", "INSUFFICIENT_PROVENANCE"),
    ("older_trigger", "SOURCE_FRESHNESS_NOT_PROVEN"), ("wrong_horizon", "HORIZON_NOT_GOVERNED"),
))
def test_fail_closed_proofs(mutation, reason):
    binding, args, source, runner, _ = fixture()
    run_id = next(k for k in source.rows if k.startswith("top3-opportunity"))
    if mutation == "future_cutoff": args["inspection_as_of"] -= timedelta(seconds=1)
    if mutation == "identity_missing": args["identity_snapshot_ids"] = ()
    if mutation == "membership_missing": args["membership_snapshot_ids"] = ()
    if mutation == "segment_missing": args["cash_segment_observation"] = None
    if mutation == "future_receipt": source.rows[run_id] = replace(source.rows[run_id], created_at=T + timedelta(seconds=1))
    if mutation == "tampered_identity": source.rows["identity:fixture"] = replace(source.rows["identity:fixture"], fingerprint="b" * 64)
    if mutation == "tampered_run": source.rows[run_id] = replace(source.rows[run_id], fingerprint="b" * 64)
    if mutation == "missing_run": del source.rows[run_id]
    if mutation == "older_trigger": args["inspection_as_of"] += timedelta(seconds=1)
    if mutation == "wrong_horizon": args["context"] = replace(CONTEXT, canonical_horizon=m.CanonicalDiagnosticHorizon.LONG_TERM)
    result = binding.inspect(**args)
    assert result.reason_codes == (reason,), result
    assert runner.calls == 0


def test_unapproved_family_and_context_cannot_become_admitting():
    binding, args, _, runner, _ = fixture(multi=True)
    # The genuine research source is verified but cannot supply admission.
    master = args["master"]
    from app.intelligence.multi_funnel_orchestration import DiscoveryFunnelExecution, DiscoveryExecutionState
    empty = m.adapters.adapt_sector_rotation(as_of=T, runs=())
    executions = tuple(DiscoveryFunnelExecution(DiscoveryExecutionState.EVALUATED, empty, (), 0)
                       if e.original.funnel_id is F.SECTOR_ROTATION else e for e in master.executions)
    research_only = replace(master, executions=executions)
    result = binding.inspect(**(args | {"master": research_only,
        "candidate_id": research_only.candidate_union.candidates[0].candidate_id}))
    assert result.reason_codes == ("NO_ADMITTING_ORIGIN",) and runner.calls == 0
    assert m._CONTEXTUAL == {F.MARKET_DISLOCATION, F.HOLDING_STATE_CHANGE, F.WATCHLIST_STATE_CHANGE}


def test_static_boundary_delegates_only_to_existing_canonical_path():
    source = inspect.getsource(m)
    tree = ast.parse(source)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "evaluate_one_lead" in calls and "run" not in calls
    assert not calls & {"save_snapshot", "execute", "commit", "build_scorecard", "assess_prebreakout_setup", "evaluate_gates", "now", "utcnow"}
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(s and s.startswith(("app.portfolio", "app.broker", "app.orders", "app.gates", "app.scoring", "app.api", "app.signals")) for s in imports)
    result = fixture()[0].inspect(**fixture()[1])
    assert result.state is m.InspectionState.EVALUATED, result.reason_codes
    assert not {"score", "entry", "stop", "target", "quantity", "allocation", "action"} & set(json.loads(result.handoff_json))


@pytest.mark.parametrize("funnel", tuple(F))
def test_exact_registry_admission_without_promoting_context_or_research(funnel):
    binding, args, _, _, _ = fixture()
    candidate = args["master"].candidate_union.candidates[0]
    # Exercise admission before source access, using a valid native lead shape.
    from app.intelligence.multi_funnel_candidate_union import DiscoveryCandidateOrigin
    from app.intelligence.multi_funnel_discovery import DiscoveryHorizon
    lead = replace(candidate.origins[0].lead, funnel_id=funnel, intended_horizons=(DiscoveryHorizon.POSITIONAL,))
    modified = replace(candidate, origins=(DiscoveryCandidateOrigin(lead),))
    if funnel is F.SECTOR_ROTATION:
        admitted, _ = binding._origins(args["master"], modified, T, CONTEXT)
        assert admitted == (lead,)
    elif funnel in m._CONTEXTUAL:
        with pytest.raises(m.UnionRadarBindingError, match="UNSUPPORTED_CONTEXTUAL_ORIGIN"):
            binding._origins(args["master"], modified, T, CONTEXT)
    else:
        with pytest.raises(m.UnionRadarBindingError):
            binding._origins(args["master"], modified, T, CONTEXT)


def test_next_explicit_cutoff_is_new_request_without_rewriting_first():
    binding, args, source, runner, _ = fixture()
    first = binding.inspect(**args)
    _, next_args, next_source, _, _ = fixture(at=T + timedelta(seconds=1), multi=True)
    source.rows.update(next_source.rows)
    successor = binding.inspect(**next_args)
    assert successor.state is m.InspectionState.EVALUATED, successor.reason_codes
    assert successor.inspection_request_id != first.inspection_request_id and runner.calls == 2
    assert len(json.loads(first.handoff_json)["origins"]) == 1
    assert len(json.loads(successor.handoff_json)["origins"]) == 2


def test_resource_bound_has_no_eviction_and_old_replay_still_works():
    binding, args, source, runner, _ = fixture()
    binding._limit = 1
    first = binding.inspect(**args)
    _, later, more, _, _ = fixture(at=T + timedelta(seconds=1))
    source.rows.update(more.rows)
    assert binding.inspect(**later).reason_codes == ("REQUEST_BOUND_EXCEEDED",)
    assert binding.inspect(**args).state is m.InspectionState.IDEMPOTENT_REPLAY
    assert first.state is m.InspectionState.EVALUATED and runner.calls == 1


def test_full_input_fingerprint_and_native_rule_lineage_correlated():
    binding, args, _, _, _ = fixture()
    result = binding.inspect(**args)
    assert result.deep_input_fingerprint.startswith("sha256:")
    assert result.diagnostic_strategy_fingerprint == _definition().semantic_fingerprint
    assert result.radar.receipt.source_discovery_lead_id in {o.lead.lead_id for o in args["master"].candidate_union.candidates[0].origins}
    with pytest.raises(m.UnionRadarBindingError, match="RESULT_CONTENT_INVALID"):
        replace(result, handoff_json="{}")
    with pytest.raises(m.UnionRadarBindingError, match="RESULT_STATE_INVALID"):
        replace(result, state=m.InspectionState.BLOCKED)


def test_no_downstream_call_or_database_write(monkeypatch):
    binding, args, _, runner, _ = fixture(multi=True)
    import sqlite3
    import requests
    import app.universe_analysis.service as universe
    def forbidden(*args, **kwargs): pytest.fail("forbidden side effect")
    monkeypatch.setattr(sqlite3, "connect", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(universe, "build_scorecard", forbidden)
    monkeypatch.setattr(universe.ExecutionGateEngine, "evaluate", forbidden)
    result = binding.inspect(**args)
    assert result.state is m.InspectionState.EVALUATED and runner.calls == 1


@pytest.mark.parametrize("kind", ("technical_missing", "technical_tampered", "wrong_security", "reader_failure"))
def test_concrete_assembler_does_not_fabricate_missing_inputs_or_expose_errors(kind):
    binding, args, _, runner, _ = fixture()
    def read(security, at):
        if kind == "technical_missing": return None
        if kind == "reader_failure": raise RuntimeError("token=PRIVATE-NEVER-OUTPUT")
        value = technical_fixture(security, at)
        object.__setattr__(value, "fingerprint" if kind == "technical_tampered" else "canonical_instrument_id", "wrong")
        return value
    binding._assembler._technical = read
    result = binding.inspect(**args)
    assert result.state is m.InspectionState.BLOCKED and runner.calls == 0
    assert "PRIVATE" not in repr(result)


def test_future_canonical_governance_fails_before_runner():
    binding, args, _, runner, _ = fixture()
    class FutureGovernance:
        def get_canonical_diagnostic_strategy_definition(self, reference):
            return replace(_definition(), registered_at=T + timedelta(seconds=1))
    binding._governance = FutureGovernance()
    assert binding.inspect(**args).reason_codes == ("FUTURE_GOVERNANCE",)
    assert runner.calls == 0


def test_missing_ranking_is_not_substituted_by_top3_run_fingerprint():
    binding, args, source, runner, _ = fixture()
    key = next(k for k in source.rows if k.startswith("current-sector-ranking:"))
    del source.rows[key]
    assert binding.inspect(**args).reason_codes == ("INSUFFICIENT_PROVENANCE",)
    assert runner.calls == 0


def test_multiple_admitting_origins_block_instead_of_arbitrary_first_lead():
    binding, args, source, runner, _ = fixture()
    master = args["master"]
    first = next(row.payload for row in source.rows.values() if row.family is Family.TOP3_OPPORTUNITY_FINDER_RUN)
    values = {f.name: getattr(first, f.name) for f in fields(first) if f.name not in {"run_id", "fingerprint"}}
    second = Top3OpportunityFinderRun.create(**(values | {"data_blocked_count": 2}))
    source.rows[second.run_id] = CoreApiSnapshot(second.run_id, Family.TOP3_OPPORTUNITY_FINDER_RUN,
        "v1", type(second).__name__, second.fingerprint, T, second)
    updated = orchestrate_whole_market_discovery(as_of=T, universe=master.universe,
        instruments=master.instruments, registry=master.registry,
        read_sources=lambda f, _: (first, second) if f is F.SECTOR_ROTATION else ())
    candidate = updated.candidate_union.candidates[0]
    assert len(candidate.origins) == 2
    result = binding.inspect(**(args | {"master": updated, "candidate_id": candidate.candidate_id}))
    assert result.reason_codes == ("MULTI_ADMITTING_RADAR_RECEIPT_NOT_SUPPORTED",)
    assert runner.calls == 0 and len(json.loads(result.handoff_json)["origins"]) == 2


def test_master_classification_known_only_at_union_does_not_backfill_origin_time():
    binding, args, _, runner, _ = fixture(multi=True)
    master = args["master"]
    instrument = replace(master.instruments[0], data_as_of=T)
    universe = build_universe_snapshot(snapshot_id=master.universe.snapshot_id, as_of=T,
        source=master.universe.source, instruments=(instrument,))
    changed = replace(master, universe=universe, instruments=(instrument,))
    result = binding.inspect(**(args | {"master": changed}))
    assert result.reason_codes == ("FUTURE_IDENTITY_CLASSIFICATION",) and runner.calls == 0


def test_incomplete_segment_proof_cannot_supply_identity_admission():
    binding, args, _, runner, _ = fixture()
    from app.market_data.reference_data.tick_size import TickSizeEvidenceSufficiency
    args["cash_segment_observation"] = replace(args["cash_segment_observation"],
        evidence_sufficiency=TickSizeEvidenceSufficiency.INSUFFICIENT)
    assert binding.inspect(**args).reason_codes == ("CASH_SEGMENT_PROVENANCE_REQUIRED",)
    assert runner.calls == 0


def test_empty_historical_identity_version_is_missing_provenance():
    binding, args, source, runner, _ = fixture()
    row = source.rows["identity:fixture"]
    identity = replace(row.payload, version="")
    source.rows[row.snapshot_id] = replace(row, payload=identity, fingerprint=sha256(repr(identity).encode()).hexdigest())
    assert binding.inspect(**args).reason_codes == ("INSUFFICIENT_PROVENANCE",)
    assert runner.calls == 0
