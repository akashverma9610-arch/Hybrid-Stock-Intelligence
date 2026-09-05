from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

import app.intelligence.multi_funnel_orchestration as module
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F, multi_funnel_discovery_registry
from app.intelligence.multi_funnel_discovery_adapters import DiscoveryAdapterCoverageState as S
from app.intelligence.multi_funnel_orchestration import (
    DiscoveryExecutionState as E, DiscoveryOrchestrationError,
    orchestrate_whole_market_discovery, serialize_whole_market_discovery,
)
from app.universe_analysis.models import NseEquityInstrument
from app.universe_analysis.service import build_universe_snapshot
from tests.unit.test_multi_funnel_discovery_adapters import _sector_run, _inflection, _compounder, _pre_breakout
from tests.unit import test_long_term_policy_transmission_research_shadow as policy_source


T = datetime(2026, 9, 5, 20, tzinfo=UTC)
SECURITY = "NSE:INE000A01001"


def _universe(ids=(SECURITY,), **changes):
    instruments = tuple(NseEquityInstrument(
        instrument_id=value, symbol=f"FIXTURE{i}", isin=value.split(":")[1],
        sector=None, industry=None, listing_status="LISTED", listing_date=None,
        tradable=True, data_as_of=T - timedelta(days=1), source="NSE_OFFICIAL_EXPORT", main_board=True,
    ) for i, value in enumerate(ids))
    snapshot = build_universe_snapshot(snapshot_id="nse-universe:fixture", as_of=T - timedelta(days=1),
        source="NSE_OFFICIAL_EXPORT", instruments=instruments)
    return replace(snapshot, **changes), instruments


def _run(sources=None, *, ids=(SECURITY,), reader=None, as_of=T, universe=None, instruments=None, registry=None):
    snapshot, records = _universe(ids)
    source_map = sources or {}
    return orchestrate_whole_market_discovery(as_of=as_of,
        universe=universe or snapshot, instruments=instruments or records,
        registry=registry or multi_funnel_discovery_registry(),
        read_sources=reader or (lambda funnel, cutoff: source_map.get(funnel, ())))


def _entry(result, funnel):
    return next(item for item in result.executions if item.original.funnel_id is funnel)


def test_registry_driven_all_fourteen_and_five_real_adapters_only():
    calls = []
    def read(funnel, cutoff):
        calls.append((funnel, cutoff))
        return ()
    result = _run(reader=read)
    assert len(result.executions) == 14
    assert tuple(x.original.funnel_id for x in result.executions) == tuple(sorted(F))
    assert tuple(x[0] for x in calls) == result.executable_funnels == result.evaluated_funnels
    assert len(calls) == 5 and all(x[1] == T for x in calls)
    assert len(result.envelope.blocked_funnels) == 9
    for f in (F.HOLDING_STATE_CHANGE, F.WATCHLIST_STATE_CHANGE):
        assert f not in {x[0] for x in calls}
    assert _entry(result, F.EMERGING_COMPOUNDER).original.coverage.adapter_state.value == "NOT_IMPLEMENTED"
    assert _entry(result, F.VALUATION_RECOVERY).original.coverage.state is S.POLICY_BLOCKED
    assert _entry(result, F.NEWS_CATALYST).original.coverage.state is S.POLICY_BLOCKED


@pytest.mark.parametrize("as_of", [None, datetime(2026, 9, 4)])
def test_explicit_aware_master_cutoff_required(as_of):
    with pytest.raises(DiscoveryOrchestrationError, match="EXPLICIT_AS_OF"):
        _run(as_of=as_of)


@pytest.mark.parametrize("changes,reason", [
    ({"checksum": "0" * 64}, "CONTENT_MISMATCH"),
    ({"eligible_security_count": 2}, "CONTENT_MISMATCH"),
    ({"instrument_ids": ()}, "CONTENT_MISMATCH"),
    ({"as_of": T + timedelta(seconds=1)}, "PIT_INVALID"),
    ({"warnings": ()}, "SCOPE_MISSING"),
])
def test_master_universe_invariants_fail_before_read(changes, reason):
    snapshot, records = _universe(**changes)
    def no_read(*args):
        pytest.fail("reader must not run")
    with pytest.raises(DiscoveryOrchestrationError, match=reason):
        _run(universe=snapshot, instruments=records, reader=no_read)


def test_missing_universe_duplicate_records_and_future_records_rejected():
    snapshot, records = _universe()
    with pytest.raises(DiscoveryOrchestrationError, match="UNIVERSE_REQUIRED"):
        orchestrate_whole_market_discovery(as_of=T, universe=None, instruments=records,
            registry=multi_funnel_discovery_registry(), read_sources=lambda *_: ())
    with pytest.raises(DiscoveryOrchestrationError, match="IDENTITY_AMBIGUOUS"):
        _run(instruments=records * 2)
    with pytest.raises(DiscoveryOrchestrationError, match="FUTURE_RECORD"):
        _run(instruments=(replace(records[0], data_as_of=T),))


def test_mismatched_canonical_security_not_accepted_even_with_matching_checksum():
    snapshot, records = _universe()
    records = (replace(records[0], isin="INE000A01002"),)
    snapshot = build_universe_snapshot(snapshot_id=snapshot.snapshot_id, as_of=snapshot.as_of,
        source=snapshot.source, instruments=records)
    with pytest.raises(DiscoveryOrchestrationError, match="CANONICAL_SECURITY_REQUIRED"):
        _run(universe=snapshot, instruments=records)


def test_reuses_existing_main_board_exclusion_without_inventing_metadata():
    _, records = _universe((SECURITY, "NSE:INE000A01002", "NSE:INE000A01003"))
    records = (records[0], replace(records[1], main_board=False), replace(records[2], main_board=None))
    snapshot = build_universe_snapshot(snapshot_id="nse-universe:scope", as_of=T,
        source="NSE_OFFICIAL_EXPORT", instruments=records)
    result = _run(universe=snapshot, instruments=records)
    assert result.universe.eligible_security_count == 2
    assert result.universe.excluded_count == 1


def test_altered_registry_cannot_inflate_status():
    registry = multi_funnel_discovery_registry()
    other = replace(registry, entries=tuple(replace(x, policy_identity="made-up") if x.funnel_id is F.NEWS_CATALYST else x for x in registry.entries))
    with pytest.raises(DiscoveryOrchestrationError, match="NOT_CANONICAL"):
        _run(registry=other)


@pytest.mark.parametrize("failure,expected", [(None, E.SOURCE_UNAVAILABLE), (OSError("secret token URL"), E.SOURCE_READ_FAILED)])
def test_unavailable_or_failed_source_isolated_and_secret_not_serialized(failure, expected):
    def read(funnel, cutoff):
        if funnel is F.COMPOUNDER:
            if failure:
                raise failure
            return None
        return (_sector_run(),) if funnel is F.SECTOR_ROTATION else ()
    result = _run(reader=read)
    assert _entry(result, F.COMPOUNDER).state is expected
    assert len(result.candidate_union.candidates) == 1
    assert "secret token URL" not in serialize_whole_market_discovery(result)
    assert F.COMPOUNDER not in result.evaluated_funnels


def test_adapter_exception_isolated_and_raw_exception_not_exposed(monkeypatch):
    def fail(**kwargs):
        raise RuntimeError("credential-bearing provider URL")
    bindings = tuple((f, fail if f is F.COMPOUNDER else fn, key, identity) for f, fn, key, identity in module._BINDINGS)
    monkeypatch.setattr(module, "_BINDINGS", bindings)
    result = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    assert _entry(result, F.COMPOUNDER).state is E.ADAPTER_FAILED
    assert len(result.candidate_union.candidates) == 1
    assert "credential-bearing" not in serialize_whole_market_discovery(result)


def test_future_evidence_retains_stale_coverage_and_never_enters_union():
    source = _sector_run()
    snapshot, records = _universe()
    earlier = source.as_of - timedelta(microseconds=1)
    records = tuple(replace(x, data_as_of=earlier) for x in records)
    snapshot = build_universe_snapshot(snapshot_id=snapshot.snapshot_id, as_of=earlier, source=snapshot.source, instruments=records)
    result = _run({F.SECTOR_ROTATION: (source,)}, as_of=earlier, universe=snapshot, instruments=records)
    assert _entry(result, F.SECTOR_ROTATION).original.coverage.state is S.STALE
    assert result.raw_lead_ids == ()
    assert result.candidate_union.candidates == ()


def test_outside_universe_preserved_but_not_in_pool():
    source = _sector_run(ids=(SECURITY, "NSE:INE000A01002"))
    result = _run({F.SECTOR_ROTATION: (source,)})
    assert len(result.raw_lead_ids) == 2
    assert len(result.outside_universe_lead_ids) == 1
    assert len(_entry(result, F.SECTOR_ROTATION).original.leads) == 2
    assert result.candidate_union.distinct_origin_count == 1
    assert result.candidate_union.candidates[0].canonical_instrument_id == SECURITY
    result.verify()


def test_all_outside_universe_not_silent_no_leads():
    result = _run({F.SECTOR_ROTATION: (_sector_run(ids=("NSE:INE000A01002",)),)})
    assert len(result.outside_universe_lead_ids) == 1
    assert result.candidate_union.candidates == ()
    coverage = next(x for x in result.candidate_union.funnel_coverage if x.funnel_id is F.SECTOR_ROTATION)
    assert coverage.adapter_coverage.state is S.IDENTITY_BLOCKED
    assert _entry(result, F.SECTOR_ROTATION).original.coverage.state is S.LEADS_EMITTED


def test_raw_origins_existing_union_and_multi_funnel_metadata(monkeypatch):
    inflection = _inflection()
    security = inflection.canonical_instrument_id
    sources = {F.FUNDAMENTAL_INFLECTION: (inflection,), F.SECTOR_ROTATION: (_sector_run(ids=(security,)),)}
    calls = []
    real = module.union_discovery_candidates
    def record(**kwargs):
        calls.append(kwargs)
        return real(**kwargs)
    monkeypatch.setattr(module, "union_discovery_candidates", record)
    result = _run(sources, ids=(security,))
    assert calls and len(calls[0]["adapter_results"]) == 14
    assert result.candidate_union.distinct_origin_count == 2
    assert result.candidate_union.multi_funnel_security_count == 1
    assert len(result.candidate_union.candidates[0].origins) == 2
    assert result.candidate_union.candidates[0].status.value == "CANDIDATE_FOR_SHARED_BRAIN_INSPECTION"


def test_all_existing_callable_sources_dispatch_without_semantic_upgrade():
    pre, compounder, inflection = _pre_breakout(), _compounder(), _inflection()
    policy = policy_source.evaluate()
    ids = tuple(sorted({compounder.canonical_instrument_id, inflection.canonical_instrument_id, policy_source.TARGET, SECURITY}))
    result = _run({F.PRE_BREAKOUT: (pre,), F.COMPOUNDER: (compounder,), F.FUNDAMENTAL_INFLECTION: (inflection,), F.SECTOR_ROTATION: (_sector_run(),), F.POLICY_TRANSMISSION: (policy,)}, ids=ids)
    assert len(result.raw_lead_ids) == 5
    # The legacy setup fixture has an opaque non-ISIN identity. Preserve its
    # raw lineage but never promote it into the explicit canonical universe.
    assert len(result.outside_universe_lead_ids) == 1
    for funnel in (F.COMPOUNDER, F.FUNDAMENTAL_INFLECTION):
        assert _entry(result, funnel).original.leads[0].readiness.value == "RESEARCH_INSPECTION"
    assert _entry(result, F.EARNINGS_ACCELERATION).original.leads == ()


def test_conflicting_source_identity_and_tampered_source_fail_closed():
    original = _sector_run()
    tampered = replace(original, fingerprint="a" * 64)
    for sources in ((original, tampered), (tampered, original)):
        result = _run({F.SECTOR_ROTATION: sources})
        assert _entry(result, F.SECTOR_ROTATION).state is E.SOURCE_CONFLICT
        assert result.candidate_union.candidates == ()
    result = _run({F.SECTOR_ROTATION: (replace(original, candidate_ids=("NSE:INE000A01002",)),)})
    assert _entry(result, F.SECTOR_ROTATION).state is E.SOURCE_VALIDATION_FAILED
    assert not _entry(result, F.SECTOR_ROTATION).executed


def test_replay_order_utc_identity_and_stable_serialization():
    a = _sector_run()
    b = _sector_run(ids=(SECURITY, "NSE:INE000A01002"))
    first = _run({F.SECTOR_ROTATION: (a, b, a)})
    other = _run({F.SECTOR_ROTATION: (b, a, a)}, as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert first == other
    assert serialize_whole_market_discovery(first) == serialize_whole_market_discovery(other)
    assert json.loads(serialize_whole_market_discovery(first))["fingerprint"] == first.fingerprint
    assert len(_entry(first, F.SECTOR_ROTATION).source_references) == 3
    assert len(first.raw_lead_ids) == 3  # adapter removes exact replay, not distinct run origins
    assert first.candidate_union.distinct_origin_count == 2  # one lead outside universe


def test_immutable_and_tamper_evident_batch():
    result = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    with pytest.raises(FrozenInstanceError):
        result.as_of = T
    object.__setattr__(result, "fingerprint", "0" * 64)
    with pytest.raises(DiscoveryOrchestrationError, match="TAMPERED"):
        serialize_whole_market_discovery(result)


def test_failed_execution_cannot_claim_success_or_missing_source_lineage():
    result = _run()
    entry = _entry(result, F.COMPOUNDER)
    with pytest.raises(DiscoveryOrchestrationError, match="FAILURE_COVERAGE_CONTRADICTION"):
        replace(entry, state=E.ADAPTER_FAILED)
    with pytest.raises(DiscoveryOrchestrationError, match="SOURCE_COUNT_INVALID"):
        replace(entry, source_records_supplied=None)
    with pytest.raises(DiscoveryOrchestrationError, match="ALL_FUNNELS_REQUIRED"):
        replace(result, executions=result.executions[:-1])


def test_tampered_adapter_coverage_is_isolated(monkeypatch):
    real = module.adapters.adapt_sector_rotation
    def corrupt(**kwargs):
        result = real(**kwargs)
        object.__setattr__(result.coverage, "fingerprint", "0" * 64)
        return result
    monkeypatch.setattr(module, "_BINDINGS", tuple((f, corrupt if f is F.SECTOR_ROTATION else fn, key, identity) for f, fn, key, identity in module._BINDINGS))
    result = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    assert _entry(result, F.SECTOR_ROTATION).state is E.ADAPTER_FAILED
    assert len(result.executions) == 14
    assert len(_entry(result, F.SECTOR_ROTATION).source_references) == 1


def test_malformed_source_count_preserved_without_raw_data_leak():
    result = _run({F.COMPOUNDER: (object(),)})
    entry = _entry(result, F.COMPOUNDER)
    assert entry.state is E.SOURCE_VALIDATION_FAILED
    assert not entry.executed
    assert entry.source_records_supplied == 1
    assert entry.source_references == ()
    assert entry.original.coverage.state is S.DATA_BLOCKED


@pytest.mark.parametrize("wrong_context", ["cutoff", "funnel"])
def test_adapter_wrong_context_fails_its_funnel_not_entire_batch(monkeypatch, wrong_context):
    def wrong(**kwargs):
        if wrong_context == "cutoff":
            return module.adapters.adapt_compounder(as_of=T + timedelta(seconds=1), observations=())
        return module.adapters.adapt_fundamental_inflection(as_of=T, observations=())
    monkeypatch.setattr(module, "_BINDINGS", tuple((f, wrong if f is F.COMPOUNDER else fn, key, identity) for f, fn, key, identity in module._BINDINGS))
    result = _run({F.SECTOR_ROTATION: (_sector_run(),)})
    assert _entry(result, F.COMPOUNDER).state is E.ADAPTER_FAILED
    assert _entry(result, F.COMPOUNDER).executed
    assert len(result.candidate_union.candidates) == 1
    assert len(result.executions) == 14


@pytest.mark.parametrize("security", ["NSE:INE372A01015", "NSE:INE0FHS01024", "NSE:INE955D01029", "NSE:INE068V01023", "NSE:INE090A01021"])
def test_five_targets_use_same_generic_universe_and_origin_path(security):
    result = _run({F.SECTOR_ROTATION: (_sector_run(ids=(security,)),)}, ids=(security,))
    assert security in result.universe.instrument_ids
    assert len(result.candidate_union.candidates) == 1
    assert result.candidate_union.candidates[0].canonical_instrument_id == security
    assert len(result.candidate_union.candidates[0].origins) == 1
    assert security not in Path(module.__file__).read_text(encoding="utf-8")


def test_static_boundary_no_engine_io_runtime_or_qualification():
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {"now", "utcnow", "today", "connect", "execute", "save", "write", "open", "run_diagnostics", "evaluate", "run", "start", "schedule"}
    calls = {x.func.attr for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)}
    assert not calls & forbidden
    imports = [x.module for x in ast.walk(tree) if isinstance(x, ast.ImportFrom)]
    assert not any(x and x.startswith(("app.portfolio", "app.storage", "app.api", "app.runtime", "app.broker", "sqlite3")) for x in imports)
    payload = serialize_whole_market_discovery(_run())
    assert not any('"' + word + '":' in payload for word in (
        "decision_score", "confidence", "entry_price", "target_price", "quantity", "gate_state", "action"))
    assert "UniverseAnalysisService" not in source
    assert "Top3OpportunityFinderService" not in source
    assert all(x.name not in {"score", "action", "recall"} for x in fields(module.WholeMarketDiscoveryBatch))
