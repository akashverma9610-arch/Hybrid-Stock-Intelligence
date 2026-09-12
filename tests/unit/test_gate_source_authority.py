"""Actual producer/reader admission tests; no synthetic authority composition."""
from dataclasses import FrozenInstanceError, asdict, fields, replace
from datetime import timedelta, timezone
from decimal import Decimal
import ast
import json
from pathlib import Path
import subprocess

import pytest

from app.gates.engine import ActionContext, ExecutionGateEngine, GateInput
from app.gates.score_provenance import score_evidence
from app.gates.source_authority import (CALENDAR_BLOCKER, RepositoryGateAuthority,
    ScoringRunGateAuthority, ScoreEvidenceAttestation, UnavailableGateAuthority)
from app.gates.version_compatibility import DOMAIN_FIELDS, GateVersionBlocked, domain_lineage, gate_evidence_context
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.versioned import V2_VERSION
from tests.unit.test_decision_score import complete, score, ANALYSIS_TIME, STRATEGY_REFERENCE
from tests.unit.test_execution_gates import CONFIG, CALENDAR, inputs as legacy_inputs
from tests.integration.test_decision_scorecard_persistence import persisted


def run_args(card):
    return dict(instrument_id=card.instrument_id, strategy_version=card.strategy_version,
        registry_version=card.registry_version, scoring_configuration_version=card.configuration_version,
        action_context=ActionContext.FRESH_ENTRY, as_of_timestamp=card.as_of_timestamp,
        evaluated_at=card.as_of_timestamp,
        inputs=GateInput(card.id, card.final_score, "isolated", card.as_of_timestamp),
        candidate_score_evidence=score_evidence(card))


def producer(items=None):
    return ScoringRunGateAuthority("stock", STRATEGY_REFERENCE, ANALYSIS_TIME,
                                   complete() if items is None else items)


def evaluate(args, authority=None):
    return ExecutionGateEngine(CONFIG, CALENDAR, source_authority=authority).evaluate(**args)


def test_actual_score_producer_attests_deterministically_without_changing_formula():
    card = score(complete()); authority = producer(); proof = score_evidence(card)
    before = content_fingerprint(card)
    receipt = authority.attest_score(proof)
    assert receipt.score_value == Decimal("9.00")
    assert receipt.score_eligible and receipt.execution_path_allowed and not receipt.shadow_only
    assert receipt.producer_id == "app.scoring.engine.build_scorecard/v1"
    assert receipt.source_fingerprint == before
    assert receipt.to_json() == authority.attest_score(proof).to_json()
    assert receipt.fingerprint == content_fingerprint({k:v for k,v in asdict(receipt).items() if k != "fingerprint"})
    assert len(evaluate(run_args(card), authority).decisions) == 6
    assert content_fingerprint(card) == before
    with pytest.raises(FrozenInstanceError): receipt.score_value = Decimal("2")


def test_explicit_reader_reopen_attestation_no_writes(tmp_path):
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    receipt = RepositoryGateAuthority(repo).attest_score(score_evidence(card))
    changes = repo._connection.total_changes
    assert len(evaluate(run_args(card), RepositoryGateAuthority(repo)).decisions) == 6
    assert repo._connection.total_changes == changes
    repo.close()
    from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
    reopened = SQLiteStrategyGovernanceRepository(tmp_path / "score-0.1.db")
    assert RepositoryGateAuthority(reopened).attest_score(score_evidence(card)).to_json() == receipt.to_json()
    reopened.close()


def test_candidate_and_incumbent_require_original_stored_score_and_gate(tmp_path):
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    authority = RepositoryGateAuthority(repo)
    original = evaluate(run_args(card), authority)
    repo.save_execution_gate_evaluation(original)
    a = run_args(card)
    a["action_context"] = ActionContext.ROTATE_IN
    a["inputs"] = replace(a["inputs"], comparison_score=original.comparison_score)
    a["incumbent_score_evidence"] = score_evidence(card, comparison_result=original)
    result = evaluate(a, authority)
    assert result.decisions[0].detail == "score advantage below configured hurdle"
    changes = repo._connection.total_changes
    forged = replace(original, id="unlinked-comparison")
    with pytest.raises(GateVersionBlocked, match="COMPARISON_CANONICAL_RECORD_UNVERIFIED"):
        evaluate(a | {"incumbent_score_evidence": score_evidence(card, comparison_result=forged)}, authority)
    assert repo._connection.total_changes == changes
    repo.close()


def test_stored_but_unknown_scoring_policy_never_attested(tmp_path):
    repo, card = persisted(tmp_path)
    card = replace(card, configuration_version="unknown-policy")
    repo.save_decision_scorecard(card)
    with pytest.raises(GateVersionBlocked, match="SCORING_POLICY_UNVERIFIED"):
        evaluate(run_args(card), RepositoryGateAuthority(repo))
    repo.close()


def test_real_historical_adapter_refuses_research_calendar_without_authority(tmp_path):
    from tests.integration.test_historical_analytical_replay import setup, CALENDAR as historical_calendar
    from app.backtest.analytical import HistoricalAnalyticalReplayService
    from app.backtest.engine import BacktestReplayEngine
    repo, _, schedule, gap, run, config = setup(tmp_path)
    BacktestReplayEngine(repo).run_analytical(run, schedule, historical_calendar, gap,
                                           HistoricalAnalyticalReplayService(repo, config))
    messages = tuple(e.message for e in repo.list_backtest_events(run.backtest_run_id))
    assert any(CALENDAR_BLOCKER in x for x in messages)
    assert not repo.list_historical_analytical_evaluations(run.backtest_run_id, 1)
    assert repo._connection.execute("SELECT count(*) FROM execution_gate_evaluations").fetchone()[0] == 0
    repo.close()


@pytest.mark.parametrize("delta", ({"final_score": Decimal("8")}, {"configuration_version": "made-up"},
    {"id": "unlinked"}, {"instrument_id": "other"}, {"registry_version": V2_VERSION}))
def test_reconstructed_v1_metadata_rehashed_score_cannot_override_reader(tmp_path, delta):
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    with pytest.raises(GateVersionBlocked):
        evaluate(run_args(replace(card, **delta)), RepositoryGateAuthority(repo))
    repo.close()


@pytest.mark.parametrize("value", (Decimal("7.5"), Decimal("8")))
def test_raw_and_stripped_v2_scalar_with_v1_label_rejected(value):
    card = score(complete()); a = run_args(card)
    a["inputs"] = replace(a["inputs"], raw_decision_score=value)
    a["candidate_score_evidence"] = None
    with pytest.raises(GateVersionBlocked, match="PROVENANCE_REQUIRED"): evaluate(a, producer())
    # Full fake V1 card + fresh self-hash is still not the producer's output.
    with pytest.raises(GateVersionBlocked, match="PRODUCER_MISMATCH"):
        evaluate(run_args(replace(card, final_score=value)), producer())


def test_receipt_is_not_a_gate_input_or_a_verifier():
    card = score(complete()); a = run_args(card)
    receipt = producer().attest_score(a["candidate_score_evidence"])
    with pytest.raises(GateVersionBlocked): evaluate(a | {"candidate_score_evidence": receipt})
    with pytest.raises(GateVersionBlocked, match="AUTHORITY_UNAVAILABLE"): evaluate(a)
    # An internally consistent reconstructed receipt alone confers nothing.
    copy = ScoreEvidenceAttestation(**{f.name: getattr(receipt, f.name) for f in fields(receipt)})
    assert copy == receipt
    with pytest.raises(TypeError): evaluate(a | {"attestation": copy}, producer())
    with pytest.raises(GateVersionBlocked, match="FINGERPRINT"):
        replace(receipt, score_value=Decimal("8"))


def test_mutation_and_fingerprint_mismatch_rejected_before_formula(monkeypatch):
    card = score(complete()); a = run_args(card)
    for name in ("_rotation", "_velocity", "_surveillance", "_plan", "_heat", "_blackout"):
        monkeypatch.setattr(ExecutionGateEngine, name, lambda *a: pytest.fail("formula reached"))
    object.__setattr__(card, "final_score", Decimal("1"))
    with pytest.raises(GateVersionBlocked, match="FINGERPRINT"): evaluate(a, producer())


@pytest.mark.parametrize("change", ("future", "duplicate", "wrong-instrument", "shadow"))
def test_scoring_source_requires_canonical_pit_diagnostics(change):
    items = complete(); item = items[0]
    if change == "future":
        item = replace(item, record=replace(item.record, as_of_timestamp=ANALYSIS_TIME+timedelta(seconds=1)))
    elif change == "duplicate":
        items = items + (item,)
    elif change == "wrong-instrument":
        item = replace(item, record=replace(item.record, instrument_id="other"))
    else:
        item = replace(item, registry_version=V2_VERSION)
    items = (item,) + items[1:]
    with pytest.raises(GateVersionBlocked): producer(items).attest_score(score_evidence(score(complete())))


@pytest.mark.parametrize("field", tuple(DOMAIN_FIELDS))
def test_every_self_declared_neutral_domain_fails_with_real_score_producer(field):
    card = score(complete()); a = run_args(card); value = getattr(legacy_inputs(
        expected_incremental_return=Decimal("1"), modeled_switching_friction=Decimal(".1")), field)
    if field.startswith("earnings_"): value = card.as_of_timestamp
    a["inputs"] = replace(a["inputs"], **{field: value})
    ref = domain_lineage(field, value, source_id=getattr(value, "id", "NSE"),
        source_version="V1", policy_version=CONFIG.version, as_of=card.as_of_timestamp,
        known_at=card.as_of_timestamp, source_fingerprints=(content_fingerprint("caller-claims-TRUSTED"),))
    a["evidence_context"] = gate_evidence_context(a["inputs"], as_of=card.as_of_timestamp,
        gate_policy_version=CONFIG.version, dependencies=(ref,))
    reason = CALENDAR_BLOCKER if field.startswith("earnings_") else "DOMAIN_AUTHORITY_UNAVAILABLE"
    with pytest.raises(GateVersionBlocked, match=reason): evaluate(a, producer())


def test_caller_surveillance_boolean_is_not_an_observation():
    card = score(complete()); a = run_args(card)
    a["inputs"] = replace(a["inputs"], surveillance=True)
    with pytest.raises(GateVersionBlocked, match="TYPE_UNVERIFIED"): evaluate(a, producer())


@pytest.mark.parametrize("key", ("period_end", "filing_date", "publication_timestamp"))
def test_historical_date_masquerading_as_schedule_is_rejected(key):
    from app.backtest.analytical import _earnings_schedule
    from tests.integration.test_historical_analytical_replay import metadata_observation
    from app.domain.models import AsOfSnapshot, ObservationKind
    at = ANALYSIS_TIME
    value = metadata_observation("filing", "stock", ObservationKind.CORPORATE_EVENT,
        {key: at, "earnings_scheduled_at": at, "earnings_schedule_verified_at": at}, at)
    snapshot = AsOfSnapshot("synthetic", at, at, "fixture", (value,))
    with pytest.raises(ValueError, match="FINANCIAL_SOURCE_FORBIDDEN"): _earnings_schedule(snapshot, "stock")


def test_candidate_calendar_contract_is_explicitly_non_authoritative():
    from app.gates.earnings_schedule_evidence import VerifiedEarningsScheduleEvidence, VERSION
    at = ANALYSIS_TIME
    body = dict(instrument_id="NSE:ISOLATED", scheduled_at=at+timedelta(days=5), event_type="FINANCIAL_RESULTS",
        source_authority="NSE", source_reference="synthetic-official-reference", received_at=at, known_at=at,
        verification_state="UNVERIFIED_SOURCE_AUTHORITY", source_contract_version="official-nse-earnings-calendar-v1",
        policy_version="six-gates-production-v1", revision_id=None, supersedes_id=None,
        source_fingerprint=content_fingerprint("synthetic"), contract_version=VERSION)
    value = VerifiedEarningsScheduleEvidence(**body, fingerprint=content_fingerprint(body))
    assert json.loads(value.to_json())["verification_state"] == "UNVERIFIED_SOURCE_AUTHORITY"
    for update in ({"verification_state": "VERIFIED"}, {"scheduled_at": at}, {"event_type": "HISTORICAL_RESULT"}):
        other = body | update
        with pytest.raises(GateVersionBlocked): VerifiedEarningsScheduleEvidence(**other, fingerprint=content_fingerprint(other))


def test_actual_canonical_score_and_diagnostic_reader(tmp_path):
    from tests.unit.test_canonical_decision_score_activation import _repository, _activate
    repo = _repository(tmp_path)
    card = repo.get_canonical_decision_scorecard(_activate(repo).outcomes[0].score_id)
    receipt = RepositoryGateAuthority(repo).attest_score(score_evidence(card))
    assert receipt.registry_version == card.registry_version
    assert receipt.score_value == card.final_score
    assert receipt.diagnostic_fingerprints
    repo.close()


def test_stored_holding_acquisition_requires_independent_snapshot(tmp_path):
    from tests.unit.test_portfolio_engine import build, buy100, PORTFOLIO
    repo, card = persisted(tmp_path); repo.save_decision_scorecard(card)
    snapshot = build((buy100(),), analytics=())
    repo.save_portfolio(PORTFOLIO)
    repo.save_portfolio_snapshot(snapshot)
    holding = snapshot.holdings[0]
    value = holding.acquisition_at.date()
    ref = domain_lineage("holding_entry_date", value, source_id=snapshot.snapshot_id,
        source_version=snapshot.cost_basis_methodology_version, policy_version=CONFIG.version,
        as_of=snapshot.as_of_timestamp, known_at=snapshot.source_transaction_cutoff,
        source_fingerprints=(content_fingerprint(snapshot),))
    authority = RepositoryGateAuthority(repo)
    context = dict(instrument_id=holding.instrument_id, as_of=ANALYSIS_TIME, gate_policy_version=CONFIG.version)
    changes = repo._connection.total_changes
    authority.verify_domain(ref, value, **context)
    for altered in (replace(ref, source_id="caller-label"), replace(ref, source_version="V2"),
                    replace(ref, source_fingerprints=(content_fingerprint("fake"),))):
        with pytest.raises(GateVersionBlocked): authority.verify_domain(altered, value, **context)
    with pytest.raises(GateVersionBlocked): authority.verify_domain(ref, value+timedelta(days=1), **context)
    with pytest.raises(GateVersionBlocked): authority.verify_domain(ref, value, **(context | {"as_of": snapshot.as_of_timestamp-timedelta(seconds=1)}))
    assert repo._connection.total_changes == changes
    repo.close()


def test_frozen_scoring_run_rejects_nested_mutation():
    items = complete(); authority = producer(items); card = score(items)
    object.__setattr__(items[0].record, "confidence", .1)
    with pytest.raises(GateVersionBlocked, match="PRODUCER_INPUT_TAMPERED"):
        authority.attest_score(score_evidence(card))


def test_v2_shadow_timestamp_and_input_authority_injection_rejected():
    from tests.unit.test_fundamental_v2_brain_lineage import variants
    card = score(complete()); a = run_args(card)
    a["inputs"] = replace(a["inputs"], earnings_scheduled_at=variants()[3])
    with pytest.raises(GateVersionBlocked): evaluate(a, producer())
    with pytest.raises(TypeError): evaluate(run_args(card) | {"source_authority": producer()})


def test_utc_receipt_normalization_and_forbidden_surface():
    card = score(complete()); receipt = producer().attest_score(score_evidence(card))
    assert replace(receipt, as_of=receipt.as_of.astimezone(timezone(timedelta(hours=5, minutes=30)))).to_json() == receipt.to_json()
    for name in ("app/gates/source_authority.py", "app/gates/earnings_schedule_evidence.py"):
        tree = ast.parse(Path(name).read_text())
        calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not any(x in {"datetime.now", "datetime.utcnow", "open", "sqlite3.connect"} for x in calls)
        assert not any(".save_" in x or ".execute" in x or ".commit" in x for x in calls)
        assert "tests.fixtures" not in Path(name).read_text()
    for name in ("app/scoring/engine.py", "app/gates/production_policy.py", "app/registry/canonical.py"):
        assert Path(name).read_text() == subprocess.check_output(["git", "show", "4027fb6:"+name], text=True)


def test_machine_authority_matrix_and_receipt_replay():
    from scripts.audit_gate_source_authority import matrix, receipt
    for label, actual in (("MATRIX", matrix()), ("RECEIPT", receipt())):
        stored = json.loads(Path("docs/architecture/FUNDAMENTAL_V2_GATE_SOURCE_AUTHORITY_"+label+".json").read_text())
        assert actual == stored
        assert actual["fingerprint"] == content_fingerprint({k:v for k,v in actual.items() if k != "fingerprint"})
    assert matrix()["expanded_field_count"] == 36
    assert receipt()["unsafe_self_declared_ingress_accepted"] == 0
    assert receipt()["frozen_v1_replay_cases"] == 21
