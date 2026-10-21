from dataclasses import replace
from datetime import timedelta, timezone
from pathlib import Path
import ast
import json
import socket

import pytest

from app.lens_knowledge import canonical_binding as binding
from app.lens_knowledge.assessment import assess_lenses, load_catalog
from app.lens_knowledge.storage import DraftLensCoverageStore
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily
from app.fundamentals.diagnostic_comparability import assemble_financial_comparability
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.models import StatementScope
from app.universe_analysis.service import build_universe_snapshot, Canonical61DiagnosticRunner
from app.universe_analysis.benchmark_sector_technical_input import assemble_current_descriptive_benchmark_sector_input
from app.market_data.nse_udiff_daily_technical_read import NseUdiffDailyTechnicalUseMode
from tests.unit.test_native_technical_binding import Store, bind
from tests.unit.test_nse_udiff_daily_technical_read import request
from tests.unit.test_nse_udiff_daily_technical_eligibility import AT
from tests.unit.test_canonical_61_runner_governance import _definition
from tests.unit.test_universe_analysis import instrument
from tests.fixtures.analytical_observations import bars


class Governance:
    def __init__(self, definition=None):
        self.definition = definition or _definition()
        self.calls = 0

    def get_canonical_diagnostic_strategy_definition(self, reference):
        self.calls += 1
        return self.definition


def bundle(store=None):
    native = bind(store or Store()).read(request())
    technical = binding.technical_from_native(native)
    identifier = native.certified_read.request.canonical_instrument_id
    context = assemble_current_descriptive_benchmark_sector_input(
        canonical_instrument_id=identifier, as_of=AT,
        technical_input=technical, benchmark_observations=(), sector_mapping=None)
    financial = CanonicalFinancialDiagnosticInput(assemble_financial_comparability(
        (), (), canonical_instrument_id=identifier, as_of=AT))
    return binding.CanonicalLensInput(native, context, financial)


def args(value=None):
    value = value or bundle()
    member = replace(instrument(value.instrument_id), data_as_of=AT)
    universe = build_universe_snapshot(snapshot_id="fixture-universe", as_of=AT, source="fixture", instruments=(member,))
    return dict(universe=universe, instruments=(member,), as_of=AT, cursor=0, batch_size=1,
        inputs=(value,), observations=(), governance=Governance())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("network access forbidden")
    monkeypatch.setattr(socket, "create_connection", forbidden)


def test_real_native_certifier_assembler_runner_feed_35_unknown_lenses(monkeypatch):
    seen = []
    original = Canonical61DiagnosticRunner.run
    def run(self, evidence, **kwargs):
        seen.append(evidence)
        return original(self, evidence, **kwargs)
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", run)
    kw = args()
    value = binding.run_canonical_coverage_page(**kw)
    assert len(seen) == 1
    assert seen[0].technical_input == binding.technical_from_native(kw["inputs"][0].native)
    assert seen[0].benchmark_sector_input == kw["inputs"][0].benchmark_sector
    assert seen[0].financial_input == kw["inputs"][0].financial
    assert value.input_basis == "CANONICAL_CURRENT_DESCRIPTIVE"
    assert len(value.canonical_input_fingerprints) == 1
    assert len(value.securities[0].assessments) == 35
    assert {x.status for x in value.securities[0].assessments} == {"UNKNOWN"}
    assert seen[0].technical_input.strict_historical_pit_state.value == "NOT_READY"
    assert kw["governance"].calls == 1


def test_repeated_calls_and_equivalent_timezone_have_identical_content():
    kw = args()
    first = binding.run_canonical_coverage_page(**kw)
    assert binding.run_canonical_coverage_page(**kw) == first
    kw["as_of"] = AT.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert binding.run_canonical_coverage_page(**kw) == first


@pytest.mark.parametrize("change", ["missing", "future_created", "future_registered", "wrong_id", "tampered"])
def test_bad_governance_fails_before_diagnostic_run(change, monkeypatch):
    kw = args()
    d = kw["governance"].definition
    if change == "missing":
        kw["governance"].definition = None
    elif change == "future_created":
        kw["governance"].definition = replace(d, created_at=AT + timedelta(seconds=1))
    elif change == "future_registered":
        kw["governance"].definition = replace(d, registered_at=AT + timedelta(seconds=1))
    elif change == "wrong_id":
        kw["governance"].definition = replace(d, strategy_id="different")
    else:
        object.__setattr__(d, "semantic_fingerprint", "sha256:" + "0"*64)
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", lambda *a, **k: pytest.fail("must not evaluate"))
    with pytest.raises(ValueError):
        binding.run_canonical_coverage_page(**kw)


@pytest.mark.parametrize("change", ["future_universe", "wrong_checksum", "future_member", "duplicate_member",
                                  "missing_input", "duplicate_input", "oversized_page", "bool_cursor"])
def test_bad_page_rejected(change):
    kw = args()
    if change == "future_universe": kw["universe"] = replace(kw["universe"], as_of=AT + timedelta(seconds=1))
    if change == "wrong_checksum": kw["universe"] = replace(kw["universe"], checksum="bad")
    if change == "future_member": kw["instruments"] = (replace(kw["instruments"][0], data_as_of=AT+timedelta(seconds=1)),)
    if change == "duplicate_member": kw["instruments"] *= 2
    if change == "missing_input": kw["inputs"] = ()
    if change == "duplicate_input": kw["inputs"] *= 2
    if change == "oversized_page": kw["batch_size"] = 1001
    if change == "bool_cursor": kw["cursor"] = True
    with pytest.raises(ValueError):
        binding.run_canonical_coverage_page(**kw)


def test_missing_native_sources_remain_unavailable_without_generic_fallback(monkeypatch):
    value = bundle(Store(missing=(CoreApiSnapshotFamily.NSE_CORPORATE_ACTION_QUERY_RECEIPT,)))
    assert value.native.technical_input is None
    technical = binding.technical_from_native(value.native)
    assert technical is None
    seen = []
    original = Canonical61DiagnosticRunner.run
    def run(self, evidence, **kwargs):
        seen.append(evidence)
        return original(self, evidence, **kwargs)
    monkeypatch.setattr(Canonical61DiagnosticRunner, "run", run)
    result = binding.run_canonical_coverage_page(**args(value))
    assert not seen
    assert result.securities[0].diagnostic_source_state == "UNAVAILABLE"
    assert all(10 in x.unavailable_primary_diagnostics for x in result.securities[0].assessments
        if 10 in next(d for d in load_catalog() if d.lens_id == x.lens_id).proposed_primary_diagnostics)


def test_tampered_native_lineage_rejected():
    kw = args()
    object.__setattr__(kw["inputs"][0].native.certified_read, "fingerprint", "sha256:"+"0"*64)
    with pytest.raises(ValueError): binding.run_canonical_coverage_page(**kw)


def test_tampered_benchmark_or_financial_lineage_rejected():
    for field in ("benchmark_sector", "financial"):
        kw = args()
        target = getattr(kw["inputs"][0], field)
        target = target.comparable if field == "financial" else target
        object.__setattr__(target, "fingerprint", "sha256:"+"0"*64)
        with pytest.raises(ValueError): binding.run_canonical_coverage_page(**kw)


def test_strict_historical_request_is_not_promoted():
    native = bind(Store()).read(request(mode=NseUdiffDailyTechnicalUseMode.STRICT_HISTORICAL_PIT_TECHNICAL))
    with pytest.raises(ValueError, match="STRICT_HISTORICAL"):
        binding.technical_from_native(native)


def test_future_observations_are_excluded_not_retimed():
    kw = args()
    observation = bars(kw["inputs"][0].instrument_id, [10])[0]
    future = replace(observation, provenance=replace(observation.provenance,
        retrieved_timestamp=AT + timedelta(days=1)))
    first = binding.run_canonical_coverage_page(**kw)
    kw["observations"] = (future,)
    assert binding.run_canonical_coverage_page(**kw) == first
    assert future.provenance.retrieved_timestamp == AT + timedelta(days=1)


def test_duplicate_observation_identity_is_rejected():
    kw = args(); observation = bars(kw["inputs"][0].instrument_id, [10])[0]
    kw["observations"] = (observation, observation)
    with pytest.raises(ValueError, match="DUPLICATE"):
        binding.run_canonical_coverage_page(**kw)


def test_retention_time_is_not_evaluation_or_source_known_at(tmp_path):
    value = binding.run_canonical_coverage_page(**args())
    repo = SQLiteCoreApiSnapshotRepository(tmp_path/"draft.sqlite")
    store = DraftLensCoverageStore(repo)
    recorded = AT + timedelta(days=2)
    key = binding.save_canonical_coverage_page(value, store=store, recorded_at=recorded)
    assert repo.get_snapshot(key).created_at == recorded
    assert store.get(key) == value and value.as_of == AT
    assert store.save(value, recorded_at=recorded+timedelta(days=1)) == key
    assert repo.get_snapshot(key).created_at == recorded
    assert {x.family for x in repo.list_snapshots(CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE)} == {CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE}
    repo.close()


@pytest.mark.parametrize("recorded", [AT-timedelta(seconds=1), AT.replace(tzinfo=None)])
def test_invalid_retention_timestamp_is_rejected(tmp_path, recorded):
    repo = SQLiteCoreApiSnapshotRepository(tmp_path/"draft.sqlite")
    with pytest.raises(ValueError, match="RETENTION"):
        DraftLensCoverageStore(repo).save(binding.run_canonical_coverage_page(**args()), recorded_at=recorded)
    assert repo.list_snapshots(CoreApiSnapshotFamily.DRAFT_LENS_COVERAGE) == ()
    repo.close()


def test_changed_source_vintage_is_conflict_not_replay(tmp_path):
    kw = args(); original = binding.run_canonical_coverage_page(**kw)
    item = kw["inputs"][0]
    kw["observations"] = (bars(item.instrument_id, [10])[0],)
    changed = binding.run_canonical_coverage_page(**kw)
    assert changed.canonical_input_fingerprints != original.canonical_input_fingerprints
    repo = SQLiteCoreApiSnapshotRepository(tmp_path/"draft.sqlite"); store = DraftLensCoverageStore(repo)
    store.save(original, recorded_at=AT)
    with pytest.raises(ValueError, match="CONFLICT"): store.save(changed, recorded_at=AT)
    repo.close()


def test_canonical_diagnostic_tampering_rejected(monkeypatch):
    real = binding.assess_universe_batch
    def corrupt(**kw):
        key = next(iter(kw["diagnostics_by_instrument"]))
        values = kw["diagnostics_by_instrument"][key]
        first = values[0]
        kw["diagnostics_by_instrument"][key] = (replace(first, record=replace(first.record, result="forged")),)+values[1:]
        return real(**kw)
    monkeypatch.setattr(binding, "assess_universe_batch", corrupt)
    with pytest.raises(ValueError, match="INTEGRITY"): binding.run_canonical_coverage_page(**args())


def test_all_21_future_dependencies_survive_catalog_import():
    root = Path(binding.__file__).parent
    definitions = load_catalog()
    labels = set()
    for item in definitions:
        raw = json.loads((root/"taxonomy"/(item.lens_id+".json")).read_text())
        expected = {x["dependency_id"] for x in raw["future_evidence_dependencies"]}
        assert set(item.unresolved_dependencies) == expected
        labels.update(expected)
    assert len(labels) == 21


def test_no_clock_provider_order_or_service_wiring():
    tree = ast.parse(Path(binding.__file__).read_text())
    imports = {x.module or "" for x in ast.walk(tree) if isinstance(x, ast.ImportFrom)}
    assert not any(x.startswith(("app.portfolio", "app.api", "app.gates", "app.rotation", "requests", "httpx")) for x in imports)
    calls = {x.func.attr for x in ast.walk(tree) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)}
    assert not calls.intersection({"now", "utcnow", "execute", "commit", "post", "place_order", "connect"})
    # save is only the explicit opt-in draft wrapper, not the pure computation.
    run = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name=="run_canonical_coverage_page")
    assert not any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute) and x.func.attr=="save" for x in ast.walk(run))
