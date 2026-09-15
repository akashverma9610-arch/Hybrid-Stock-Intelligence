"""Shared cached discovery HTTP proof: canonical fixtures, no live provider."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
import inspect
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from app.api.agent_main import create_app
from app.api.agent_market_scan import shared_scan_from_existing_state, market_scan_response
from app.intelligence import shared_market_scan as m
from app.intelligence.multi_funnel_discovery import DiscoveryFunnelId as F
from app.market_data.dhan import DHAN_PROVIDER
from app.market_data.dhan_live import LiveMarketState, LiveMarketStateStore, DhanLiveFeedHealth
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as Family
from app.universe_analysis.models import NseEquityInstrument, ProviderInstrumentMappingRecord, ProviderMappingStatus
from tests.unit.test_multi_funnel_discovery_adapters import _sector_run, _inflection

T = datetime(2026, 9, 6, 12, tzinfo=UTC)
ID = "NSE:INE000A01001"
KEY = "synthetic-agent-key"
AUTH = {"Authorization": "Bearer " + KEY}
URL = "/hsi/v1/market-scan"


def instrument(identifier=ID, **changes):
    return replace(NseEquityInstrument(identifier, "FIXTURE", identifier[4:], None, None,
        "ACTIVE", None, True, T - timedelta(days=1), "OFFICIAL_FIXTURE", "nse:fixture", main_board=True), **changes)


def mapping(identifier=ID, **changes):
    return replace(ProviderInstrumentMappingRecord("mapping:fixture", identifier, DHAN_PROVIDER,
        "NSE_EQ", "1", "FIXTURE", identifier[4:], ProviderMappingStatus.ACTIVE,
        T - timedelta(days=1), source_checksum="sha256:" + "a" * 64,
        raw_provider_exchange="NSE", raw_provider_series="EQ", normalized_instrument="EQUITY"), **changes)


def quote(identifier=ID, **changes):
    return replace(LiveMarketState(identifier, DHAN_PROVIDER, "1", Decimal("100"),
        T - timedelta(seconds=1), T, DhanLiveFeedHealth.LIVE), **changes)


def service(*, instruments=None, mappings=None, quotes=None, reader=None):
    calls = []
    def sources(at):
        calls.append(at)
        return (instruments if instruments is not None else (instrument(),),
                mappings if mappings is not None else (mapping(),),
                quotes if quotes is not None else (quote(),),
                reader or (lambda f, _: (_sector_run(),) if f is F.SECTOR_ROTATION else None))
    return m.SharedMarketScanService(sources), calls


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("HSI_AGENT_API_KEY", KEY)
    monkeypatch.delenv("DHAN_LIVE_MARKET_ENABLED", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_BACKEND", raising=False)


def test_full_fixture_path_and_shared_authenticated_reads_do_not_rescan():
    scan, calls = service()
    snapshot = scan.refresh(as_of=T)
    application = create_app()
    application.state.agent_market_scan_service = scan
    with TestClient(application) as client:
        a = client.get(URL, params={"as_of": T.isoformat()}, headers=AUTH)
        b = client.get(URL, params={"as_of": T.isoformat()}, headers=AUTH)
        assert client.get(URL).status_code == 401
        assert client.post(URL, headers=AUTH).status_code == 405
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert calls == [T]
    output = a.json()
    assert output["status"] == "PARTIAL"
    assert output["actionability"] == "WATCH_ONLY" and output["execution_status"] == "NON_EXECUTABLE"
    data = output["data"]
    assert data["scan_id"] == snapshot.scan_id
    assert len(data["requested_funnels"]) == 14
    assert data["executed_funnels"] == ["SECTOR_ROTATION"]
    assert len(data["blocked_funnels"]) == 13
    assert data["metrics"]["mapped_exact"] == data["metrics"]["fresh_quote_count"] == 1
    assert data["metrics"]["candidate_union_count"] == 1
    assert data["deep_diagnostics_run"] is False
    assert data["scan_duration_seconds"] >= 0
    assert KEY not in a.text


def test_no_snapshot_empty_default_app_never_queries_or_refreshes():
    scan, calls = service()
    assert market_scan_response(scan, as_of=T).blockers == ("SHARED_MARKET_SCAN_REFRESH_REQUIRED",)
    assert calls == []
    with TestClient(create_app()) as client:
        result = client.get(URL, headers=AUTH)
    assert result.status_code == 200 and result.json()["status"] == "BLOCKED"


def test_latest_pit_exclusion_no_ttl_and_explicit_timestamp():
    scan, _ = service()
    first = scan.refresh(as_of=T)
    assert scan.latest(as_of=T - timedelta(microseconds=1)) is None
    assert scan.latest(as_of=T + timedelta(days=10))[0] == first
    with pytest.raises(m.SharedMarketScanError):
        scan.refresh(as_of=datetime(2026, 9, 6))


def test_deterministic_timezone_identity_and_operational_duration_separation():
    a, _ = service()
    b, _ = service()
    one = a.refresh(as_of=T)
    two = b.refresh(as_of=T.astimezone(timezone(timedelta(hours=5, minutes=30))))
    assert one == two
    with pytest.raises(FrozenInstanceError):
        one.scan_id = "changed"
    before = a.latest(as_of=T)
    assert a.refresh(as_of=T) is one
    assert a.latest(as_of=T) == before


def test_tamper_rejected_and_same_cutoff_conflict_keeps_original():
    sources = {F.SECTOR_ROTATION: (_sector_run(),)}
    scan, _ = service(reader=lambda f, _: sources.get(f))
    first = scan.refresh(as_of=T)
    sources[F.SECTOR_ROTATION] = ()
    with pytest.raises(m.SharedMarketScanError, match="SAME_CUTOFF_CONFLICT"):
        scan.refresh(as_of=T)
    assert scan.latest(as_of=T)[0] is first
    object.__setattr__(first, "fingerprint", "bad")
    assert market_scan_response(scan, as_of=T).status == "BLOCKED"


def test_no_overlap_and_bounded_cache():
    scan, calls = service()
    scan._refresh_lock.acquire()
    try:
        with pytest.raises(m.SharedMarketScanError, match="BUSY"):
            scan.refresh(as_of=T)
        assert calls == []
    finally:
        scan._refresh_lock.release()
    for i in range(10):
        scan.refresh(as_of=T + timedelta(minutes=i))
    assert len(scan._snapshots) == 8
    assert scan.latest(as_of=T) is None


@pytest.mark.parametrize("changes,expected", [
    ({"mappings": ()}, ("MISSING", "UNAVAILABLE")),
    ({"quotes": ()}, ("MAPPED_EXACT", "UNAVAILABLE")),
    ({"mappings": (mapping(isin="INE000A01002"),)}, ("INVALID", "UNAVAILABLE")),
    ({"mappings": (mapping(effective_as_of=T + timedelta(seconds=1)),)}, ("MISSING", "UNAVAILABLE")),
    ({"mappings": (mapping(raw_provider_series=None),)}, ("INVALID", "UNAVAILABLE")),
    ({"mappings": (mapping(source_checksum="bad"),)}, ("INVALID", "UNAVAILABLE")),
    ({"mappings": (mapping(), mapping(provider_instrument_reference="2"))}, ("CONFLICTED", "UNAVAILABLE")),
    ({"quotes": (quote(provider_security_id="2"),)}, ("MAPPED_EXACT", "INVALID")),
    ({"quotes": (quote(received_at=T + timedelta(seconds=1)),)}, ("MAPPED_EXACT", "FUTURE_EXCLUDED")),
    ({"quotes": (quote(provider_trade_timestamp=T + timedelta(seconds=1)),)}, ("MAPPED_EXACT", "FUTURE_EXCLUDED")),
    ({"quotes": (quote(ltp=Decimal("NaN")),)}, ("MAPPED_EXACT", "INVALID")),
    ({"quotes": (quote(), quote(ltp=Decimal("101")))}, ("MAPPED_EXACT", "CONFLICTED")),
    ({"quotes": (quote(freshness=DhanLiveFeedHealth.STALE),)}, ("MAPPED_EXACT", "STALE")),
])
def test_mapping_and_current_data_fail_closed(changes, expected):
    scan, _ = service(**changes)
    row = scan.refresh(as_of=T).securities[0]
    assert (row.mapping_state, row.market_state) == expected


def test_native_quote_freshness_and_closed_market_no_historical_fallback():
    store = LiveMarketStateStore()
    store.replace(quote())
    scan, _ = service(quotes=store.values(now=T + timedelta(days=1)))
    value = scan.refresh(as_of=T + timedelta(days=1))
    assert value.securities[0].market_state == "STALE"
    assert value.securities[0].market_data_as_of == T - timedelta(seconds=1)


def test_universe_exclusions_are_accounted_and_not_in_candidates():
    ids = tuple("NSE:INE000A0100" + str(i) for i in range(1, 7))
    records = (instrument(ids[0]), instrument(ids[1], security_type="ETF"),
        instrument(ids[2], main_board=False), instrument(ids[3], listing_status="DELISTED"),
        instrument(ids[4], isin=ids[0][4:]), instrument(ids[5], main_board=None))
    scan, _ = service(instruments=records,
        reader=lambda f, _: (_sector_run(ids=ids),) if f is F.SECTOR_ROTATION else None)
    value = scan.refresh(as_of=T)
    assert value.batch.universe.instrument_ids == (ids[0], ids[5])
    assert {c.canonical_instrument_id for c in value.batch.candidate_union.candidates} == {ids[0], ids[5]}
    metrics = m.scan_payload(value, 0)["metrics"]
    assert metrics["source_universe"] == 6 and metrics["excluded"] == 3 and metrics["identity_blocked"] == 1


def test_duplicate_universe_future_records_and_empty_universe_fail_before_funnels():
    for records in ((), (instrument(), instrument()), (instrument(data_as_of=T + timedelta(seconds=1)),)):
        scan, _ = service(instruments=records, reader=lambda *_: pytest.fail("funnel must not run"))
        with pytest.raises(m.SharedMarketScanError):
            scan.refresh(as_of=T)


def test_shared_provider_identity_conflict_and_input_order_independence():
    records = (instrument(), instrument("NSE:INE000A01002"))
    maps = (mapping(), mapping(records[1].instrument_id))
    a, _ = service(instruments=records, mappings=maps)
    b, _ = service(instruments=records[::-1], mappings=maps[::-1])
    first, second = a.refresh(as_of=T), b.refresh(as_of=T)
    assert first == second
    assert all(row.mapping_state == "CONFLICTED" for row in first.securities)


def test_contextual_funnels_not_called_all_origins_preserved_no_hit_score():
    observation = _inflection()
    identifier = observation.canonical_instrument_id
    calls = []
    sources = {F.SECTOR_ROTATION: (_sector_run(ids=(identifier,)),), F.FUNDAMENTAL_INFLECTION: (observation,)}
    def reader(f, _):
        calls.append(f)
        return sources.get(f)
    scan, _ = service(instruments=(instrument(identifier),), reader=reader)
    snapshot = scan.refresh(as_of=max(T, observation.as_of))
    assert F.HOLDING_STATE_CHANGE not in calls and F.WATCHLIST_STATE_CHANGE not in calls
    assert len(calls) == 5
    candidate = snapshot.batch.candidate_union.candidates[0]
    assert len(snapshot.batch.candidate_union.candidates) == 1
    assert set(candidate.funnel_ids) == {F.SECTOR_ROTATION, F.FUNDAMENTAL_INFLECTION}
    assert len(candidate.origins) == 2 and not hasattr(candidate, "score")
    encoded = json.dumps(m.scan_payload(snapshot, 0), default=str)
    assert all(origin.origin_id in encoded and origin.fingerprint in encoded for origin in candidate.origins)


def test_default_state_binding_reads_canonical_repository_and_existing_runtime_only():
    class Repository:
        def __init__(self): self.calls = []
        def list_snapshots(self, family, *, limit, offset):
            self.calls.append(family)
            values = {Family.NSE_UNIVERSE: (instrument(),), Family.PROVIDER_INSTRUMENT_MAPPING: (mapping(),),
                      Family.TOP3_OPPORTUNITY_FINDER_RUN: (_sector_run(),)}.get(family, ())
            return tuple(CoreApiSnapshot(str(i), family, "v1", type(v).__name__, "fixture", T, v)
                         for i, v in enumerate(values))[offset:offset+limit]
        def save_snapshot(self, *_): pytest.fail("no persistence")
    class Runtime:
        def __init__(self): self.calls = []
        def quotes(self, *, now): self.calls.append(now); return (quote(),)
    repository, runtime = Repository(), Runtime()
    scan = shared_scan_from_existing_state(lambda: SimpleNamespace(
        core_api_snapshot_repository=repository, dhan_live_market_runtime=runtime))
    snapshot = scan.refresh(as_of=T)
    assert len(snapshot.batch.candidate_union.candidates) == 1
    assert set(snapshot.batch.evaluated_funnels) == {F.PRE_BREAKOUT, F.SECTOR_ROTATION}
    before = len(repository.calls)
    assert market_scan_response(scan, as_of=T).status == "PARTIAL"
    assert len(repository.calls) == before and runtime.calls == [T]


def test_exception_text_and_secrets_never_exposed():
    class Bad:
        def read_payload(self, **_): raise RuntimeError("Bearer " + KEY)
    response = market_scan_response(Bad(), as_of=T)
    assert KEY not in response.model_dump_json() and response.status == "BLOCKED"


def test_static_cost_and_authority_boundaries():
    from app.api import agent_market_scan
    from app.intelligence import multi_funnel_orchestration, multi_funnel_discovery_adapters, multi_funnel_candidate_union
    for module in (m, agent_market_scan, multi_funnel_orchestration, multi_funnel_discovery_adapters, multi_funnel_candidate_union):
        tree = ast.parse(inspect.getsource(module))
        calls = {ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        forbidden = ("requests.", "httpx.", "openai.", "lyzr.", "web_search", "connect(", "place_order", "save_snapshot", "run_forever")
        assert not any(term in call for term in forbidden for call in calls)
    assert "orchestrate_whole_market_discovery" in inspect.getsource(m.SharedMarketScanService.refresh)
    assert "_sources" not in inspect.getsource(m.SharedMarketScanService.latest)
    assert "refresh(" not in inspect.getsource(agent_market_scan.market_scan_response)
    assert "verify(" not in inspect.getsource(m.SharedMarketScanService.read_payload)


def test_snapshot_keeps_candidate_compatible_with_existing_radar61_binding():
    from tests.unit.test_discovery_union_radar_binding import fixture
    from app.intelligence.discovery_union_radar_binding import InspectionState
    binding, args, source, runner, _ = fixture()
    previous = args["master"]
    run = next(row.payload for row in source.rows.values() if row.family is Family.TOP3_OPPORTUNITY_FINDER_RUN)
    scan, _ = service(instruments=previous.instruments,
        reader=lambda f, _: (run,) if f is F.SECTOR_ROTATION else None)
    snapshot = scan.refresh(as_of=previous.as_of)
    assert runner.calls == 0  # Discovery itself never runs diagnostics.
    membership_row = source.rows["member:fixture"]
    membership = replace(membership_row.payload, universe_id=snapshot.batch.universe.snapshot_id)
    from hashlib import sha256
    source.rows["member:fixture"] = replace(membership_row, payload=membership,
        fingerprint=sha256(repr(membership).encode()).hexdigest())
    result = binding.inspect(**(args | {"master": snapshot.batch,
        "candidate_id": snapshot.batch.candidate_union.candidates[0].candidate_id}))
    assert result.state is InspectionState.EVALUATED, result.reason_codes
    assert runner.calls == 1
    assert tuple(r.rule_id for r in result.radar.receipt.rule_references) == tuple(range(1, 62))


@pytest.mark.parametrize("changes", [
    {"market_state": "LIVE"}, {"mapping_state": "MAPPED_EXACT"},
    {"market_data_as_of": T}, {"mapping_fingerprint": "bad"}, {"universe_state": "MADE_UP"},
])
def test_snapshot_coverage_cannot_lie_about_availability(changes):
    row = m.ScanSecurityCoverage(ID, "ELIGIBLE", "MISSING", "UNAVAILABLE")
    with pytest.raises(m.SharedMarketScanError):
        replace(row, **changes)


def test_newer_inactive_mapping_cannot_fall_back_to_older_active():
    inactive = next(value for value in ProviderMappingStatus if value is not ProviderMappingStatus.ACTIVE)
    scan, _ = service(mappings=(mapping(), mapping(effective_as_of=T, status=inactive)))
    assert scan.refresh(as_of=T).securities[0].mapping_state == "INVALID"


def test_duplicate_identical_inputs_do_not_inflate_data_coverage():
    scan, _ = service(mappings=(mapping(), mapping()), quotes=(quote(), quote()))
    snapshot = scan.refresh(as_of=T)
    assert len(snapshot.securities) == 1
    assert snapshot.securities[0].market_state == "LIVE"


def test_source_failure_isolated_no_secret_and_no_false_complete_coverage():
    def read(f, _):
        if f is F.PRE_BREAKOUT:
            raise RuntimeError("secret-bearing-provider-error")
        return (_sector_run(),) if f is F.SECTOR_ROTATION else None
    scan, _ = service(reader=read)
    snapshot = scan.refresh(as_of=T)
    result = market_scan_response(scan, as_of=T)
    assert result.status == "PARTIAL"
    assert "secret-bearing" not in result.model_dump_json()
    assert F.PRE_BREAKOUT in snapshot.batch.envelope.blocked_funnels


def test_store_availability_future_receipts_and_equal_time_master_conflict():
    class Repository:
        def __init__(self, values): self.values = values
        def list_snapshots(self, family, *, limit, offset):
            return tuple(row for row in self.values if row.family is family)[offset:offset+limit]
    def row(value, known, name):
        return CoreApiSnapshot(name, Family.NSE_UNIVERSE, "v1", "fixture", "fixture", known, value)
    hidden = Repository((row(instrument(), T + timedelta(seconds=1), "future"),))
    scan = shared_scan_from_existing_state(lambda: SimpleNamespace(core_api_snapshot_repository=hidden))
    with pytest.raises(m.SharedMarketScanError, match="UNIVERSE_UNAVAILABLE"):
        scan.refresh(as_of=T)
    conflict = Repository((row(instrument(), T, "a"), row(instrument(symbol="DIFFERENT"), T, "b")))
    scan = shared_scan_from_existing_state(lambda: SimpleNamespace(core_api_snapshot_repository=conflict))
    with pytest.raises(m.SharedMarketScanError, match="UNIVERSE_CONFLICT"):
        scan.refresh(as_of=T)


def test_future_funnel_store_receipt_not_retroactively_exposed():
    from app.api.agent_market_scan import _read_family
    class Repository:
        def list_snapshots(self, family, **_):
            run = _sector_run()
            return (CoreApiSnapshot(run.run_id, family, "v1", "fixture", run.fingerprint,
                T + timedelta(seconds=1), run),)
    assert _read_family(Repository(), Family.TOP3_OPPORTUNITY_FINDER_RUN, T) == ()


def test_source_bound_refuses_truncation():
    from app.api.agent_market_scan import _read_family
    class Repository:
        def list_snapshots(self, family, *, limit, offset):
            return tuple(CoreApiSnapshot(str(offset + i), family, "v1", "fixture", "fixture", T, instrument())
                for i in range(limit))
    with pytest.raises(m.SharedMarketScanError, match="BOUND_EXCEEDED"):
        _read_family(Repository(), Family.NSE_UNIVERSE, T)


def test_api_reads_never_rebuild_universe_or_union_and_cannot_mutate_cached_response(monkeypatch):
    import app.intelligence.multi_funnel_orchestration as native
    scan, _ = service()
    scan.refresh(as_of=T)
    def forbidden(*args, **kwargs): pytest.fail("Agent read recomputed discovery")
    monkeypatch.setattr(native, "build_universe_snapshot", forbidden)
    monkeypatch.setattr(native, "union_discovery_candidates", forbidden)
    monkeypatch.setattr(m, "orchestrate_whole_market_discovery", forbidden)
    first = market_scan_response(scan, as_of=T)
    assert first.status == "PARTIAL"
    first.data.candidate_union["candidates"].clear()
    second = market_scan_response(scan, as_of=T)
    assert second.status == "PARTIAL"
    assert len(second.data.candidate_union["candidates"]) == 1
