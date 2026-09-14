"""Offline protocol witnesses only; no model, event generation, storage or authority.

All monetary values, dates, policies and completion proofs below are synthetic.
The local witness checker illustrates necessary contract constraints, not a
production source verifier, horizon resolver or realized-wealth calculator.
"""
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_gate1_rotation_scenario_model_source_feasibility as previous


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1.json"
BASELINE = "2b303367eddf80697a5cb1bc601bfab3c731911e"
FP = "sha256:b45af9573b36d727619f630aad5990ba44ff9a7f84c4d9a489a602b6c950a7dd"
NEXT = "GATE1_ROTATION_RESEARCH_HORIZON_AUTHORITY_POLICY_V1"
D = "2026-01-05T10:00:00+00:00"
E = "2026-01-07T10:00:00+00:00"  # Synthetic endpoint, NOT a numeric policy.
R = "2026-01-08T10:00:00+00:00"


def _read():
    return previous.predecessor.proposal._read(PATH)


def _hash(value, *exclude):
    return content_fingerprint({k: v for k, v in value.items() if k not in exclude})


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _time(value):
    _need(type(value) is str, "INVALID_WIRE")
    result = datetime.fromisoformat(value)
    _need(result.tzinfo is not None and result.utcoffset() is not None, "INVALID_WIRE")
    return result.astimezone(UTC)


def _wire(value, kind):
    """Closed-shape normalization for test witnesses, no application registration."""
    if kind.endswith("?"):
        return None if value is None else _wire(value, kind[:-1])
    if kind.startswith("["):
        _need(type(value) is list, "INVALID_WIRE")
        return [_wire(x, kind[1:-1]) for x in value]
    shapes = _read()["wire_contract"]["shapes"]
    if kind in shapes:
        _need(type(value) is dict and value.keys() == shapes[kind].keys(), "INVALID_WIRE")
        return {k: _wire(v, shapes[kind][k]) for k, v in value.items()}
    if kind == "null":
        _need(value is None, "INVALID_WIRE")
    elif kind == "false":
        _need(value is False, "INVALID_WIRE")
    elif kind == "utc":
        return _time(value).isoformat()
    elif kind in {"decimal", "positive_decimal"}:
        _need(type(value) is str and re.fullmatch(r"-?\d+(?:\.\d+)?", value), "INVALID_WIRE")
        number = Decimal(value)
        _need(number.is_finite() and (kind != "positive_decimal" or number > 0), "INVALID_WIRE")
        value = format(number, "f")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        return "0" if number == 0 else value
    elif kind == "id":
        _need(type(value) is str and re.fullmatch(r"[A-Za-z0-9._:-]+", value), "INVALID_WIRE")
    elif kind == "fingerprint":
        _need(type(value) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", value), "INVALID_WIRE")
    else:
        _need(value in kind.split("|"), "INVALID_WIRE")
    return value


def _refs(value):
    if isinstance(value, dict):
        if value.keys() == _read()["wire_contract"]["shapes"]["SourceRef"].keys():
            yield value
        else:
            for item in value.values():
                yield from _refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from _refs(item)


def _key(ref):
    return ref["role"], ref["id"], ref["version"]


def _observation_id(decision):
    body = {}
    for path in _read()["identity"]["observation_body"]:
        value = decision
        for part in path.split("."):
            value = value[part]
        body[path] = value
    return "gate1-paired-research:" + content_fingerprint(body).split(":")[1]


def _seal(o):
    """Sign synthetic witness output; never repairs an input source fingerprint."""
    o["decision"]["decision_fingerprint"] = _hash(o["decision"], "decision_fingerprint")
    o["observation_id"] = _observation_id(o["decision"])
    if o["outcome"] is not None:
        o["outcome"]["observation_id"] = o["observation_id"]
        o["outcome"]["outcome_fingerprint"] = _hash(o["outcome"], "outcome_fingerprint")
    o["revision_fingerprint"] = _hash(o, "revision_fingerprint")
    return o


def _witness():
    trusted = {}

    def ref(name, role="DECISION", event=D, known=D):
        value = dict(id="test:" + name, version="v1", role=role, event_at=event, known_at=known)
        value["fingerprint"] = content_fingerprint(value)
        trusted[(value["id"], value["version"])] = deepcopy(value)
        return value

    def policy(name):
        return dict(id="test:" + name, version="v1", fingerprint=content_fingerprint({"test_policy": name}),
                    approved_at=D, known_at=D, effective_from=D, effective_to=None, selection_ref=ref(name))

    horizon = dict(policy=policy("horizon"), start=D, end=E, calendar_ref=ref("calendar"), endpoint_rule_ref=ref("endpoint-rule"))
    horizon["fingerprint"] = content_fingerprint(horizon)
    unavailable = dict(state="UNAVAILABLE", source_refs=[], reason="CONTEXT_NOT_AVAILABLE")
    decision = dict(protocol_version="v1", origin=dict(kind="PORTFOLIO_ROTATION", mode="ARCHIVED_DECISION",
        record=ref("original-event", "ORIGIN_RECORD"), event_id="test:original-event", comparison_ref="test:original-pair", decision_cutoff=D, run_ref=None, run_manifest_ref=None),
        incumbent_id="NSE:INE372A01015", challenger_id="NSE:INE090A01021", parcel_ref=ref("selected-parcel"), capital_basis_ref=ref("capital"),
        starting_capital_inr="100", currency="INR", strategy_context=deepcopy(unavailable), regime_context=deepcopy(unavailable),
        sector_context=deepcopy(unavailable), volatility_context=deepcopy(unavailable), diagnostic_context=deepcopy(unavailable),
        universe_ref=ref("original-universe"), horizon=horizon, methodology=policy("realized-wealth"),
        funding_quantity_residual_policy=policy("funding"), precision_policy=policy("precision"), evidence=[])
    decision["evidence"] = sorted((deepcopy(v) for v in _refs(decision)), key=_key)
    decision["decision_fingerprint"] = _hash(decision)
    policy_manifest = {p["id"]: deepcopy(p) for p in (horizon["policy"], decision["methodology"], decision["funding_quantity_residual_policy"], decision["precision_policy"])}

    def leg(instrument, value, suffix):
        return dict(instrument_id=instrument, decision_cutoff=D, horizon_fingerprint=horizon["fingerprint"],
            methodology_fingerprint=decision["methodology"]["fingerprint"], capital_basis_fingerprint=decision["capital_basis_ref"]["fingerprint"],
            starting_capital_inr="100", start_price_ref=ref("start-" + suffix), terminal_price_ref=ref("terminal-" + suffix, "TERMINAL_PRICE", E, R),
            terminal_gross_value_inr=value, parcel_transform_refs=[], completeness="COMPLETE", cost_basis="COST_EXCLUSIVE")

    outcome = dict(observation_id="placeholder", horizon_fingerprint=horizon["fingerprint"], methodology_ref=decision["methodology"],
        capital_basis_ref=decision["capital_basis_ref"], currency="INR", incumbent=leg(decision["incumbent_id"], "105", "i"),
        challenger=leg(decision["challenger_id"], "110", "c"), evidence=[], corporate_action_status="VERIFIED_COMPARABLE",
        label_state="PAIRED_GROSS_COMPLETE", incumbent_gross_pnl_inr="5", challenger_gross_pnl_inr="10", paired_gross_advantage_inr="5",
        auxiliary_return_percentage=None, missing_friction_components=_read()["outcomes"]["friction_components"], net_advantage_inr=None,
        matured_at=E, label_available_at=R)
    # Starting price evidence is D-visible and must also be in the decision closure.
    for name in ("incumbent", "challenger"):
        decision["evidence"].append(deepcopy(outcome[name]["start_price_ref"]))
    decision["evidence"].sort(key=_key)
    outcome["evidence"] = sorted((deepcopy(v) for v in _refs(outcome)), key=_key)
    o = dict(observation_id="placeholder", protocol_version="v1", decision=decision, research_as_of=R,
        maturity="MATURE", completion_evidence=[ref("completion", "SESSION_COMPLETED", E, E)], outcome=outcome,
        admission="ADMITTED", reason_codes=[], primary_reason=None, supersedes_revision=None, authority="RESEARCH_ONLY", execution_authority=False)
    return _seal(o), trusted, policy_manifest


def _check(o, trusted, policies):
    o = _wire(o, "PairedObservation")
    d, out = o["decision"], o["outcome"]
    _need(o["protocol_version"] == d["protocol_version"] == _read()["version"], "PAIR_MISMATCH")
    at, research = _time(d["origin"]["decision_cutoff"]), _time(o["research_as_of"])
    _need(research >= at, "INVALID_WIRE")
    _need(d["origin"]["kind"] in {"HISTORICAL_ROTATION", "PORTFOLIO_ROTATION", "BACKTEST_EVENT"}, "ORIGIN_NOT_AUTHENTIC")
    _need(d["origin"]["event_id"] == d["origin"]["record"]["id"], "ORIGIN_NOT_AUTHENTIC")
    replay_metadata = []
    if d["origin"]["mode"] == "FROZEN_REPLAY":
        manifest = d["origin"]["run_manifest_ref"]
        _need(d["origin"]["run_ref"] is not None and manifest is not None, "ORIGIN_NOT_AUTHENTIC")
        _need(manifest["role"] == "REPLAY_MANIFEST" and d["origin"]["record"]["role"] == "ORIGIN_RECORD", "ORIGIN_NOT_AUTHENTIC")
        proof = policies.get("__replay_manifests__", {}).get(manifest["fingerprint"])
        _need(proof == {"run_id": d["origin"]["run_ref"], "input_refs": d["evidence"]}, "ORIGIN_NOT_AUTHENTIC")
        replay_metadata = [d["origin"]["record"], manifest]
    else:
        _need(d["origin"]["run_ref"] is None and d["origin"]["run_manifest_ref"] is None, "ORIGIN_NOT_AUTHENTIC")
    _need(d["incumbent_id"] != d["challenger_id"], "IDENTITY_AMBIGUOUS")
    _need(d["horizon"] is not None, "HORIZON_POLICY_MISSING")
    h = d["horizon"]
    _need(h["fingerprint"] == _hash(h, "fingerprint"), "SOURCE_TAMPERED")
    _need(at <= _time(h["start"]) < _time(h["end"]), "HORIZON_AMBIGUOUS")
    for p in (h["policy"], d["methodology"], d["funding_quantity_residual_policy"], d["precision_policy"]):
        _need(p is not None, "OUTCOME_METHOD_UNSET")
        _need(all(_time(p[k]) <= at for k in ("approved_at", "known_at", "effective_from")), "DECISION_PIT_VIOLATION")
        # The synthetic manifest is independently fixed; no generic expiry rule is invented.
        _need(p == policies.get(p["id"]), "SOURCE_TAMPERED")
    for context in (d[k] for k in ("strategy_context", "regime_context", "sector_context", "volatility_context", "diagnostic_context")):
        if context["state"] == "AVAILABLE":
            _need(bool(context["source_refs"]) and context["reason"] is None, "INVALID_WIRE")
        elif context["state"] == "UNAVAILABLE":
            _need(not context["source_refs"] and context["reason"] is not None, "INVALID_WIRE")
        else:
            _need(bool(context["source_refs"]) and context["reason"] is not None, "SOURCE_CONFLICT")
    _need(d["evidence"] == sorted(d["evidence"], key=_key), "INVALID_WIRE")
    _need(len({_key(x) for x in d["evidence"]}) == len(d["evidence"]), "SOURCE_CONFLICT")
    for ref in _refs(d):
        if ref in replay_metadata:
            _need(ref not in d["evidence"] and _time(ref["known_at"]) <= research and _time(ref["event_at"]) <= research, "DECISION_PIT_VIOLATION")
            _need(ref == trusted.get((ref["id"], ref["version"])), "SOURCE_TAMPERED")
            continue
        _need(ref["role"] not in {"TERMINAL_PRICE", "REALIZED_OUTCOME", "SESSION_COMPLETED"}, "FUTURE_LABEL_LEAKAGE")
        _need(_time(ref["event_at"]) <= at and _time(ref["known_at"]) <= at, "DECISION_PIT_VIOLATION")
        _need(ref == trusted.get((ref["id"], ref["version"])), "SOURCE_TAMPERED")
        _need(ref in d["evidence"], "SOURCE_TAMPERED")
    _need(d["decision_fingerprint"] == _hash(d, "decision_fingerprint"), "SOURCE_TAMPERED")
    _need(o["observation_id"] == _observation_id(d), "SOURCE_TAMPERED")
    completed = bool(o["completion_evidence"]) and all(x["role"] == "SESSION_COMPLETED" and _time(x["event_at"]) == _time(h["end"]) and _time(x["known_at"]) <= research for x in o["completion_evidence"])
    expected_maturity = "PENDING_MATURITY" if research < _time(h["end"]) else "MATURE" if completed else "UNRESOLVED"
    _need(o["maturity"] == expected_maturity, "NON_MATURE")
    for ref in o["completion_evidence"]:
        _need(_time(ref["known_at"]) <= research and _time(ref["event_at"]) <= research, "OUTCOME_NOT_YET_KNOWN")
        _need(ref == trusted.get((ref["id"], ref["version"])), "SOURCE_TAMPERED")
    if o["maturity"] != "MATURE":
        _need(out is None and o["admission"] != "ADMITTED", "NON_MATURE")
    if out is not None:
        _need(out["observation_id"] == o["observation_id"] and out["horizon_fingerprint"] == h["fingerprint"], "PAIR_MISMATCH")
        _need(out["methodology_ref"] == d["methodology"] and out["capital_basis_ref"] == d["capital_basis_ref"], "PAIR_MISMATCH")
        _need(_time(out["matured_at"]) == _time(h["end"]) <= _time(out["label_available_at"]) <= research, "OUTCOME_NOT_YET_KNOWN")
        for ref in _refs(out):
            _need(_time(ref["event_at"]) <= research and _time(ref["known_at"]) <= research, "OUTCOME_NOT_YET_KNOWN")
            _need(ref == trusted.get((ref["id"], ref["version"])), "SOURCE_TAMPERED")
            _need(ref in out["evidence"], "SOURCE_TAMPERED")
        for name, instrument in (("incumbent", d["incumbent_id"]), ("challenger", d["challenger_id"])):
            leg = out[name]
            _need(leg["instrument_id"] == instrument and _time(leg["decision_cutoff"]) == at, "PAIR_MISMATCH")
            _need(leg["horizon_fingerprint"] == h["fingerprint"] and leg["methodology_fingerprint"] == d["methodology"]["fingerprint"] and leg["capital_basis_fingerprint"] == d["capital_basis_ref"]["fingerprint"] and leg["starting_capital_inr"] == d["starting_capital_inr"], "PAIR_MISMATCH")
            if leg["start_price_ref"] is not None:
                _need(leg["start_price_ref"] in d["evidence"], "DECISION_PIT_VIOLATION")
            if leg["terminal_price_ref"] is not None:
                _need(_time(leg["terminal_price_ref"]["event_at"]) == _time(h["end"]), "TERMINAL_OBSERVATION_MISSING")
        if out["label_state"] == "PAIRED_GROSS_COMPLETE":
            _need(out["corporate_action_status"] == "VERIFIED_COMPARABLE", "CORPORATE_ACTION_AMBIGUOUS")
            for leg in (out["incumbent"], out["challenger"]):
                _need(leg["completeness"] == "COMPLETE" and leg["terminal_gross_value_inr"] is not None and leg["start_price_ref"] is not None and leg["terminal_price_ref"] is not None, "GROSS_LABEL_INCOMPLETE")
            capital = Decimal(d["starting_capital_inr"])
            iv, cv = (Decimal(out[k]["terminal_gross_value_inr"]) for k in ("incumbent", "challenger"))
            _need((Decimal(out["incumbent_gross_pnl_inr"]), Decimal(out["challenger_gross_pnl_inr"]), Decimal(out["paired_gross_advantage_inr"])) == (iv-capital, cv-capital, cv-iv), "GROSS_LABEL_INCOMPLETE")
        else:
            _need(o["admission"] == "EXCLUDED" and all(out[k] is None for k in ("incumbent_gross_pnl_inr", "challenger_gross_pnl_inr", "paired_gross_advantage_inr")), "GROSS_LABEL_INCOMPLETE")
        _need(out["outcome_fingerprint"] == _hash(out, "outcome_fingerprint"), "SOURCE_TAMPERED")
    if o["admission"] == "ADMITTED":
        _need(o["maturity"] == "MATURE" and out is not None and out["label_state"] == "PAIRED_GROSS_COMPLETE" and not o["reason_codes"] and o["primary_reason"] is None, "GROSS_LABEL_INCOMPLETE")
    else:
        _need(bool(o["reason_codes"]), "INVALID_WIRE")
    taxonomy = [r["code"] for r in _read()["exclusion_taxonomy"]]
    _need(o["reason_codes"] == [x for x in taxonomy if x in o["reason_codes"]], "INVALID_WIRE")
    _need(o["primary_reason"] == (o["reason_codes"][0] if o["reason_codes"] else None), "INVALID_WIRE")
    _need(o["revision_fingerprint"] == _hash(o, "revision_fingerprint"), "SOURCE_TAMPERED")
    return o


def test_protocol_and_all_predecessor_boundaries_unchanged():
    a = _read()
    assert a["protocol_fingerprint"] == _hash(a, "protocol_fingerprint") == FP
    assert a["baseline_commit"] == BASELINE
    assert (a["decision"], a["semantic_decision"]) == ("B", "PAIRED_SCENARIO_RESEARCH_PROTOCOL_READY_WITH_POLICY_BLOCKERS")
    assert a["predecessor"]["fingerprint"] == previous.FP
    previous.test_artifact_and_predecessor_fingerprints_preserve_exact_accepted_contract()
    previous.test_existing_v1_and_six_gate_boundaries_unchanged()
    assert a["economic_contract"]["fingerprint"] == previous.predecessor.FP
    assert a["frozen_boundaries"]["v1"] == "six-gates-production-v1/v1 ACTIVE"
    assert a["frozen_boundaries"]["v2"] == "NOT_ACTIVE"
    assert a["frozen_boundaries"]["score_hurdle"] == "raw_decision_score - comparison_score >= 1.00"
    assert a["frozen_boundaries"]["economic_hurdle"] == "net_advantage_inr > 0.00"
    assert all(a["frozen_boundaries"][k] is True for k in ("independent_hurdles", "cost_exclusive", "friction_once", "same_parcel_cutoff_horizon_method_currency"))


@pytest.mark.parametrize("path,pin", _read()["inspected_file_fingerprints_lf"].items())
def test_inspected_files_pinned_to_baseline(path, pin):
    raw = subprocess.check_output(["git", "show", BASELINE + ":" + path])
    assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


def test_valid_gross_research_witness_is_never_net_or_live_authority():
    o, trusted, policies = _witness()
    result = _check(o, trusted, policies)
    assert result["outcome"]["paired_gross_advantage_inr"] == "5"
    assert result["outcome"]["net_advantage_inr"] is None
    assert len(result["outcome"]["missing_friction_components"]) == 7
    assert result["execution_authority"] is False


@pytest.mark.parametrize("field,new", [("decision_cutoff", R), ("horizon_fingerprint", "sha256:"+"a"*64), ("methodology_fingerprint", "sha256:"+"b"*64), ("capital_basis_fingerprint", "sha256:"+"c"*64), ("starting_capital_inr", "101"), ("instrument_id", "NIFTY_500")])
def test_pair_symmetry_cannot_change_one_leg(field, new):
    o, trusted, policies = _witness(); o["outcome"]["challenger"][field] = new
    with pytest.raises(ValueError, match="PAIR_MISMATCH"):
        _check(_seal(o), trusted, policies)


@pytest.mark.parametrize("where", ["observation", "decision"])
def test_protocol_version_identical_on_decision_and_observation(where):
    o, trusted, policies = _witness()
    target = o if where == "observation" else o["decision"]
    target["protocol_version"] = "v2"
    with pytest.raises(ValueError, match="PAIR_MISMATCH"):
        _check(_seal(o), trusted, policies)


@pytest.mark.parametrize("origin", ["RAW_PRICES", "WATCH_ROUTER", "AI", "USER", "UNKNOWN"])
def test_raw_bars_and_unpaired_or_invented_origins_cannot_create_observation(origin):
    o, trusted, policies = _witness(); o["decision"]["origin"]["kind"] = origin
    with pytest.raises(ValueError, match="ORIGIN_NOT_AUTHENTIC"):
        _check(_seal(o), trusted, policies)


def test_missing_horizon_and_no_hindsight_rebinding():
    o, trusted, policies = _witness(); o["decision"]["horizon"] = None
    with pytest.raises(ValueError, match="HORIZON_POLICY_MISSING"):
        _check(o, trusted, policies)
    o, trusted, policies = _witness(); o["decision"]["horizon"]["end"] = R
    with pytest.raises(ValueError, match="SOURCE_TAMPERED"):
        _check(_seal(o), trusted, policies)
    assert _read()["horizon"]["numeric_duration"] is None
    assert _read()["horizon"]["state"] == "POLICY_REQUIRED"


@pytest.mark.parametrize("field", ["event_at", "known_at"])
def test_future_decision_evidence_rejected_even_if_content_resealed(field):
    o, trusted, policies = _witness()
    future = deepcopy(o["decision"]["evidence"][0])
    future["id"] = "test:future-feature"
    future[field] = R
    future["fingerprint"] = _hash(future, "fingerprint")
    trusted[(future["id"], future["version"])] = deepcopy(future)
    o["decision"]["evidence"].append(future)
    o["decision"]["evidence"].sort(key=_key)
    with pytest.raises(ValueError, match="DECISION_PIT_VIOLATION"):
        _check(_seal(o), trusted, policies)


def test_terminal_label_cannot_be_used_as_decision_feature():
    o, trusted, policies = _witness()
    o["decision"]["evidence"].append(deepcopy(o["outcome"]["incumbent"]["terminal_price_ref"]))
    o["decision"]["evidence"].sort(key=_key)
    with pytest.raises(ValueError, match="FUTURE_LABEL_LEAKAGE"):
        _check(_seal(o), trusted, policies)


def test_early_maturity_and_missing_completion_proof_fail_closed():
    o, trusted, policies = _witness(); o["research_as_of"] = D
    with pytest.raises(ValueError, match="NON_MATURE"):
        _check(_seal(o), trusted, policies)
    o, trusted, policies = _witness(); o["completion_evidence"] = []
    with pytest.raises(ValueError, match="NON_MATURE"):
        _check(_seal(o), trusted, policies)
    o["maturity"] = "UNRESOLVED"; o["outcome"] = None; o["admission"] = "INADMISSIBLE"
    o["reason_codes"] = ["CALENDAR_UNRESOLVED"]; o["primary_reason"] = "CALENDAR_UNRESOLVED"
    assert _check(_seal(o), trusted, policies)["outcome"] is None


def test_endpoint_equality_needs_completion_and_outcome_receipts():
    o, trusted, policies = _witness(); o["research_as_of"] = E
    with pytest.raises(ValueError, match="OUTCOME_NOT_YET_KNOWN"):
        _check(_seal(o), trusted, policies)
    o["outcome"] = None; o["admission"] = "EXCLUDED"
    o["reason_codes"] = ["OUTCOME_NOT_YET_KNOWN"]; o["primary_reason"] = "OUTCOME_NOT_YET_KNOWN"
    assert _check(_seal(o), trusted, policies)["maturity"] == "MATURE"


def test_pending_record_cannot_retain_future_completion_evidence():
    o, trusted, policies = _witness()
    o.update(research_as_of=D, maturity="PENDING_MATURITY", outcome=None, admission="PENDING_MATURITY", reason_codes=["NON_MATURE"], primary_reason="NON_MATURE")
    with pytest.raises(ValueError, match="OUTCOME_NOT_YET_KNOWN"):
        _check(_seal(o), trusted, policies)


def test_later_frozen_replay_metadata_not_a_future_predictive_feature():
    o, trusted, policies = _witness(); d = o["decision"]
    original = d["origin"]["record"]
    d["evidence"] = [r for r in d["evidence"] if r != original]
    original["known_at"] = R
    original["fingerprint"] = _hash(original, "fingerprint")
    trusted[(original["id"], original["version"])] = deepcopy(original)
    manifest = dict(id="test:run-manifest", version="v1", role="REPLAY_MANIFEST", event_at=R, known_at=R)
    manifest["fingerprint"] = content_fingerprint(manifest)
    trusted[(manifest["id"], manifest["version"])] = deepcopy(manifest)
    d["origin"].update(kind="BACKTEST_EVENT", mode="FROZEN_REPLAY", run_ref="test:frozen-run", run_manifest_ref=manifest)
    policies["__replay_manifests__"] = {manifest["fingerprint"]: {"run_id": "test:frozen-run", "input_refs": deepcopy(d["evidence"])}}
    assert _check(_seal(o), trusted, policies)["decision"]["origin"]["mode"] == "FROZEN_REPLAY"
    d["origin"]["mode"] = "ARCHIVED_DECISION"
    with pytest.raises(ValueError, match="ORIGIN_NOT_AUTHENTIC"):
        _check(_seal(o), trusted, policies)


def test_maturation_keeps_identity_but_changes_revision_only():
    o, trusted, policies = _witness(); original_id = o["observation_id"]; decision_fp = o["decision"]["decision_fingerprint"]
    old = deepcopy(o); old.update(research_as_of=D, maturity="PENDING_MATURITY", outcome=None, admission="PENDING_MATURITY", completion_evidence=[], reason_codes=["NON_MATURE"], primary_reason="NON_MATURE")
    old = _check(_seal(old), trusted, policies)
    o["supersedes_revision"] = old["revision_fingerprint"]
    mature = _check(_seal(o), trusted, policies)
    assert old["observation_id"] == mature["observation_id"] == original_id
    assert old["decision"]["decision_fingerprint"] == mature["decision"]["decision_fingerprint"] == decision_fp
    assert old["revision_fingerprint"] != mature["revision_fingerprint"]


@pytest.mark.parametrize("field,new,code", [("terminal_price_ref", None, "GROSS_LABEL_INCOMPLETE"), ("terminal_gross_value_inr", None, "GROSS_LABEL_INCOMPLETE"), ("completeness", "INCOMPLETE", "GROSS_LABEL_INCOMPLETE")])
def test_missing_terminal_and_partial_leg_cannot_be_admitted(field, new, code):
    o, trusted, policies = _witness(); o["outcome"]["challenger"][field] = new
    with pytest.raises(ValueError, match=code):
        _check(_seal(o), trusted, policies)


def test_partial_evidence_retained_with_null_pair_and_exclusion():
    o, trusted, policies = _witness(); out = o["outcome"]
    out["label_state"] = "PARTIAL_EVIDENCE"; out["challenger"]["terminal_price_ref"] = None
    out["challenger"]["terminal_gross_value_inr"] = None; out["challenger"]["completeness"] = "INCOMPLETE"
    for field in ("incumbent_gross_pnl_inr", "challenger_gross_pnl_inr", "paired_gross_advantage_inr"):
        out[field] = None
    o.update(admission="EXCLUDED", reason_codes=["TERMINAL_OBSERVATION_MISSING"], primary_reason="TERMINAL_OBSERVATION_MISSING")
    assert _check(_seal(o), trusted, policies)["outcome"]["label_state"] == "PARTIAL_EVIDENCE"


@pytest.mark.parametrize("state", ["UNRESOLVED", "CONFLICTED"])
def test_corporate_action_ambiguity_not_hidden_as_zero_return(state):
    o, trusted, policies = _witness(); o["outcome"]["corporate_action_status"] = state
    with pytest.raises(ValueError, match="CORPORATE_ACTION_AMBIGUOUS"):
        _check(_seal(o), trusted, policies)


def test_duplicate_and_tampered_sources_not_repaired():
    o, trusted, policies = _witness(); o["decision"]["evidence"].append(o["decision"]["evidence"][0]); o["decision"]["evidence"].sort(key=_key)
    with pytest.raises(ValueError, match="SOURCE_CONFLICT"):
        _check(_seal(o), trusted, policies)
    o, trusted, policies = _witness(); o["decision"]["evidence"][0]["fingerprint"] = "sha256:"+"f"*64
    with pytest.raises(ValueError, match="SOURCE_TAMPERED"):
        _check(_seal(o), trusted, policies)


def test_utc_equivalent_timestamps_and_stable_wire_fingerprint():
    o, trusted, policies = _witness()
    changed = json.loads(canonical_json(o).replace("2026-01-05T10:00:00+00:00", "2026-01-05T15:30:00+05:30"))
    assert _check(changed, trusted, policies) == _check(o, trusted, policies)
    assert _hash(json.loads(canonical_json(_read())), "protocol_fingerprint") == FP


@pytest.mark.parametrize("key,new", [("net_advantage_inr", "0"), ("auxiliary_return_percentage", "5")])
def test_net_or_auxiliary_percentage_cannot_be_filled(key, new):
    o, trusted, policies = _witness(); o["outcome"][key] = new
    with pytest.raises(ValueError, match="INVALID_WIRE"):
        _check(_seal(o), trusted, policies)


@pytest.mark.parametrize("field", ["tax_rate", "expected_return", "slippage_default"])
def test_no_model_rate_or_neutral_slippage_default(field):
    assert _read()["outcomes"][field] is None


@pytest.mark.parametrize("reason", [r["code"] for r in _read()["exclusion_taxonomy"]])
def test_every_exclusion_has_explicit_meaning_and_retention(reason):
    row = next(r for r in _read()["exclusion_taxonomy"] if r["code"] == reason)
    assert row["meaning"].strip()
    assert "retain" in _read()["admission"]["receipt_retention"].lower()


def test_sampling_denominator_survivorship_dependence_and_no_fake_adequacy():
    a = _read()
    assert len({x["code"] for x in a["exclusion_taxonomy"]}) == 36
    assert a["sampling"]["minimum_sample_size"] is None
    assert a["sampling"]["adequacy_state"] == "CALIBRATION_POLICY_REQUIRED"
    for field in ("true_origin_count", "duplicate_alias_count", "excluded_count", "overlapping_interval_groups", "origin_mode_counts"):
        assert field in a["sampling"]["required_reporting"]
    assert "never present-day membership" in a["prices_and_actions"]["universe"]
    assert "decision-to-label-maturity" in a["sampling"]["dependence"]
    assert all(s["use"] != "ADMITTED" for s in a["source_classifications"])


@pytest.mark.parametrize("reason", ["CUTOFF_MISSING", "INCUMBENT_MISSING", "CHALLENGER_MISSING", "PARCEL_MISSING", "HORIZON_AMBIGUOUS", "INSUFFICIENT_HISTORY", "SOURCE_CONFLICT"])
def test_incomplete_input_retained_as_receipt_not_fabricated_observation(reason):
    receipt = dict(protocol_version="v1", origin_source_ref=None, input_fingerprint=content_fingerprint({"synthetic_missing_input": reason}),
        observation_id=None, research_as_of=R, reason_codes=[reason], primary_reason=reason, disposition="INADMISSIBLE", alias_of=None)
    identity = {k: receipt[k] for k in _read()["identity"]["receipt_body"]}
    receipt["receipt_id"] = _read()["identity"]["receipt_prefix"] + content_fingerprint(identity).split(":")[1]
    receipt["receipt_fingerprint"] = _hash(receipt, "receipt_id", "receipt_fingerprint")
    normalized = _wire(receipt, "RejectionReceipt")
    assert normalized["observation_id"] is None and normalized["primary_reason"] == reason
    assert normalized["receipt_fingerprint"] == _hash(normalized, "receipt_id", "receipt_fingerprint")


@pytest.mark.parametrize("key,new", [("execution_authority", True), ("authority", "AI_APPROVED")])
def test_unsupported_authority_or_execution_witness_rejects(key, new):
    o, trusted, policies = _witness(); o[key] = new
    with pytest.raises(ValueError, match="INVALID_WIRE"):
        _check(_seal(o), trusted, policies)


def _fit_labels(labels, *, fit, test_start, model_frozen, training_origin_ids):
    _need(_time(fit) <= _time(model_frozen) < _time(test_start), "OOS_LEAKAGE")
    for label in labels:
        _need(label["admission"] == "ADMITTED", "OOS_LEAKAGE")
        _need(_time(label["matured"]) <= _time(fit) and _time(label["available"]) <= _time(fit), "OOS_LEAKAGE")
        _need(label["split"] == "TRAIN" and label["origin"] in training_origin_ids and not label["overlaps_test"], "OOS_LEAKAGE")


@pytest.mark.parametrize("key,new", [("matured", R), ("available", R), ("split", "TEST"), ("origin", "test-only-origin"), ("overlaps_test", True), ("admission", "EXCLUDED")])
def test_fit_requires_mature_known_training_labels_and_oos_isolation(key, new):
    label = dict(matured=D, available=D, split="TRAIN", origin="train-origin", overlaps_test=False, admission="ADMITTED")
    _fit_labels([label], fit=E, test_start=R, model_frozen=E, training_origin_ids={"train-origin"})
    label[key] = new
    with pytest.raises(ValueError, match="OOS_LEAKAGE"):
        _fit_labels([label], fit=E, test_start=R, model_frozen=E, training_origin_ids={"train-origin"})


def test_split_parameters_unset_and_model_selection_strictly_before_test():
    split = _read()["splits"]
    assert split["random_split_allowed"] is False
    assert split["modes"] == ["CHRONOLOGICAL", "WALK_FORWARD"]
    assert split["numeric_percentages"] is split["purge_sessions"] is split["embargo_sessions"] is None
    with pytest.raises(ValueError, match="OOS_LEAKAGE"):
        _fit_labels([], fit=E, test_start=R, model_frozen=R, training_origin_ids=set())
    with pytest.raises(ValueError, match="OOS_LEAKAGE"):
        _fit_labels([], fit=E, test_start=R, model_frozen=D, training_origin_ids=set())


def test_no_runtime_ai_or_gate_authority_and_one_next_continuation():
    a = _read()
    assert all(v is False for v in a["runtime"].values())
    assert a["frozen_boundaries"]["ai_authority"] is False
    assert set(a["ownership"]["ai_forbidden"]) >= {"ORIGIN_CREATION", "LABEL_CREATION_OR_EDIT", "ADMISSION_OVERRIDE", "PIT_OVERRIDE", "PRODUCER_REGISTRATION"}
    assert a["next_continuations"] == [NEXT] and a["next_continuation_started"] is False
    assert a["blockers_closed"]["operational"] == []
    assert len(a["readiness"]) == 15 and not any(r["state"] == "READY" for r in a["readiness"])
    for path in (ROOT / "app").rglob("*.py"):
        assert "GATE1_ROTATION_PAIRED_SCENARIO_RESEARCH_PROTOCOL_V1" not in path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="DUPLICATE_PROPOSAL_KEY"):
        json.loads('{"decision":"B","decision":"A"}', object_pairs_hook=previous.predecessor.proposal.legacy._unique_object)
