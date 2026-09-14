"""Contract conformance witnesses only; no runtime validator or scenario producer.

The closed shape vocabulary is specified by the governance artifact, not JSON
Schema. All authority, policy and endpoint witnesses below are synthetic and
isolated. They never register an authority or send a record to a live service.
"""
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from tests.unit import test_execution_gate_policy_v2_composite_governance_approval_2 as approval
from tests.unit import test_gate1_rotation_policy_v2_proposal as proposal


ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "docs/architecture/GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1.json"
BASELINE = "53cf15e1e299aa8ba89ca8380acf042dad71f79b"
FP = "sha256:b4f5c83f33c44c889218823041800d80507733b1932b89529c5aed26ea8c6e14"
AT = "2026-09-01T12:00:00+00:00"
END = "2026-10-01T12:00:00+00:00"  # Synthetic endpoint, NOT an approved horizon.
WIRE_SHAPES = proposal._read(PATH)["wire_contract"]["shapes"]


def _read():
    return proposal._read(PATH)


def _digest(c):
    return content_fingerprint({k: v for k, v in c.items() if k != "contract_fingerprint"})


class InvalidWitness(ValueError):
    pass


def _need(condition, code):
    if not condition:
        raise InvalidWitness(code)


def _time(s):
    value = datetime.fromisoformat(s)
    _need(value.tzinfo is not None and value.utcoffset() is not None, "INVALID_WIRE_SHAPE")
    return value.astimezone(UTC)


def _shape(value, kind):
    """Only the explicitly closed test-artifact vocabulary, no generic schema engine."""
    if kind.endswith("?"):
        return None if value is None else _shape(value, kind[:-1])
    if kind.startswith("["):
        _need(type(value) is list, "INVALID_WIRE_SHAPE")
        return [_shape(v, kind[1:-1]) for v in value]
    shapes = WIRE_SHAPES
    if kind in shapes:
        _need(type(value) is dict and value.keys() == shapes[kind].keys(), "INVALID_WIRE_SHAPE")
        return {k: _shape(value[k], t) for k, t in shapes[kind].items()}
    if kind == "null":
        _need(value is None, "INVALID_WIRE_SHAPE")
    elif kind == "false":
        _need(value is False, "INVALID_WIRE_SHAPE")
    elif kind == "decimal":
        _need(type(value) is str and re.fullmatch(r"-?\d+(?:\.\d+)?", value), "INVALID_WIRE_SHAPE")
        number = Decimal(value)
        _need(number.is_finite(), "INVALID_WIRE_SHAPE")
        # Lexical normalization only; never monetary rounding or context arithmetic.
        value = format(number, "f")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        if number == 0:
            value = "0"
    elif kind == "utc":
        _need(type(value) is str, "INVALID_WIRE_SHAPE")
        value = _time(value).isoformat()
    elif kind in ("id", "fingerprint"):
        pattern = r"[A-Za-z0-9._:/-]+" if kind == "id" else r"sha256:[0-9a-f]{64}"
        _need(type(value) is str and re.fullmatch(pattern, value), "INVALID_WIRE_SHAPE")
    else:
        _need(value == kind, "INVALID_WIRE_SHAPE")
    return value


def _normalized(w):
    value = _shape(w, "Scenario")
    unique = {}
    for r in value["evidence"]:
        _need(r["id"] not in unique or unique[r["id"]] == r, "EVIDENCE_CONFLICTED")
        unique[r["id"]] = r
    value["evidence"] = sorted(unique.values(), key=lambda r: (r["role"], r["id"], r["version"]))
    for key, fields in (("friction", ("component",)), ("tax_lots", ("acquisition_evidence_id",)),
                        ("slippage_legs", ("side", "instrument_id"))):
        identities = [tuple(r[f] for f in fields) for r in value[key]]
        _need(len(identities) == len(set(identities)), "EVIDENCE_CONFLICTED")
        value[key].sort(key=lambda r: tuple(r[f] for f in fields))
    sets = [value["parcel"]["reference_price_ids"], value["tax_context_evidence_ids"]]
    sets += [r["evidence_ids"] for r in value["friction"]]
    sets += [r["market_state_evidence_ids"] for r in value["slippage_legs"]]
    for items in sets:
        _need(len(items) == len(set(items)), "EVIDENCE_CONFLICTED")
        items.sort()
    return value


def _body(w):
    return {k: v for k, v in _normalized(w).items() if k not in ("scenario_id", "content_fingerprint")}


def _identity(w):
    b = _body(w)
    identity_body = {k: v for k, v in b.items() if k not in ("candidate_endpoint", "incumbent_endpoint")}
    return "gate1-rotation-scenario:" + content_fingerprint({"version": "rotation-scenario-identity/v1", "inputs": identity_body})[7:]


def _seal(w):
    """Fixture construction only, never used by verification to repair tampering."""
    w = deepcopy(w)
    w["scenario_id"] = _identity(w)
    w["content_fingerprint"] = content_fingerprint(_body(w))
    return w


def _fixture(terminal="1091", selected="10", held="20"):
    evidence = []

    def ref(name, role):
        identifier = "TEST:" + role + ":" + name
        evidence.append(dict(id=identifier, version="fixture-v1", fingerprint=content_fingerprint({"synthetic": name}),
                             as_of=AT, known_at=AT, role=role))
        return identifier

    policies = {key: ref(key, "POLICY") for key in _read()["wire_contract"]["shapes"]["Policies"]}
    producer = ref("producer", "SCENARIO_PRODUCER")
    horizon = dict(policy_ref=ref("horizon", "POLICY"), start=AT, endpoint=END,
                   calendar_ref=ref("calendar", "CALENDAR"), precision_ref=policies["precision"])
    capital = str(Decimal(selected) * Decimal("100"))
    parcel = dict(snapshot_id=ref("snapshot", "PORTFOLIO_SNAPSHOT"), holding_id="holding-NSE:INE090A01021",
        selected_quantity=selected, held_quantity=held, incumbent_reference_price_inr="100",
        candidate_reference_price_inr="100", candidate_quantity=selected,
        candidate_purchase_turnover_inr=capital, residual_capital_inr="0", switched_capital_inr=capital,
        cash_contribution_inr="0", reference_price_ids=[ref("incumbent-price", "PRICE"), ref("candidate-price", "PRICE")],
        actual_realized_proceeds_inr=None)
    parcel["reference_price_ids"].sort()
    candidate, incumbent = "NSE:INE372A01015", "NSE:INE090A01021"
    def endpoint(instrument, name, amount):
        return dict(instrument_id=instrument, parcel_fingerprint=content_fingerprint(parcel),
                    horizon_fingerprint=content_fingerprint(horizon), model_ref=policies["paired_model"],
                    terminal_gross_value_inr=amount, evidence_id=ref(name, "ENDPOINT_INPUT"), cost_basis="COST_EXCLUSIVE")
    w = dict(scenario_id="pending", content_fingerprint="sha256:" + "0" * 64,
        contract_version="v1", contract_fingerprint=FP,
        composite_proposal_fingerprint=proposal.EXPECTED_FINGERPRINT,
        composite_approval_fingerprint=approval.APPROVAL_FP,
        context="ROTATE_IN", decision_as_of=AT, currency="INR", candidate_instrument_id=candidate,
        incumbent_instrument_id=incumbent, portfolio_id="TEST:portfolio", parcel=parcel, horizon=horizon,
        policies=policies, candidate_endpoint=endpoint(candidate, "candidate-endpoint", terminal),
        incumbent_endpoint=endpoint(incumbent, "incumbent-endpoint", "1080"),
        friction=[], tax_lots=[dict(acquisition_evidence_id=ref("acquisition", "TAX_LOT"),
                                  selected_quantity=selected, cost_basis_evidence_id=ref("cost-basis", "TAX_BASIS"))],
        tax_context_evidence_ids=[ref("jurisdiction", "TAX_CONTEXT"), ref("tax-circumstances", "TAX_CONTEXT")],
        slippage_legs=[], producer_ref=producer,
        score_binding=dict(candidate_score_evidence_id=ref("candidate-score", "SCORE"),
                           incumbent_comparison_evidence_id=ref("incumbent-score", "SCORE")), evidence=evidence)
    for key, amount in zip(_read()["friction"]["components"], ("1", "1", "1", "2", "2", "1", "2"), strict=True):
        policy = policies["tax" if key == "capital_gains_tax" else "slippage" if key == "slippage" else "cost"]
        w["friction"].append(dict(component=key, amount_inr=amount, evidence_ids=[ref(key, "COST")], policy_ref=policy))
    for instrument, side in ((incumbent, "INCUMBENT_DISPOSAL"), (candidate, "CANDIDATE_ACQUISITION")):
        w["slippage_legs"].append(dict(instrument_id=instrument, side=side, quantity=selected,
            reference_price_inr="100", amount_inr="0.5", evidence_id=ref(side, "SLIPPAGE"),
            market_state_evidence_ids=[ref(side + "-market", "MARKET_STATE")], policy_ref=policies["slippage"],
            producer_ref=producer, confidence=None, confidence_status="UNAVAILABLE"))
    w = _seal(w)
    # Out-of-band hypothetical authority fixture, not caller-supplied real authority.
    authority = dict(producer=producer, expected_body=_body(w), pair=(candidate, incumbent),
        freshness={r["id"]: "FRESH" for r in w["evidence"]},
        pool={r["id"]: [deepcopy(r)] for r in w["evidence"]},
        policies={identifier: dict(approved_at=AT, effective_at=AT, applicable=True)
                  for identifier in (*policies.values(), horizon["policy_ref"])},
        quantity_steps={candidate: Decimal("1"), incumbent: Decimal("1")})
    return w, authority


def _assess(w, authority=None):
    """Reference conformance witness, NOT a production authority/evaluator API."""
    empty = dict(gross_advantage_inr=None, net_advantage_inr=None, economic_predicate="NOT_EVALUATED", execution_authority=False)
    try:
        _need(type(w) is dict, "INVALID_WIRE_SHAPE")
        _need(w.get("context") == "ROTATE_IN", "UNSUPPORTED_STATE")
        _need(w.get("currency") == "INR", "INVALID_UNIT")
        v = _normalized(w)
        _need(v["contract_version"] == "v1" and v["contract_fingerprint"] == FP
              and v["composite_proposal_fingerprint"] == proposal.EXPECTED_FINGERPRINT
              and v["composite_approval_fingerprint"] == approval.APPROVAL_FP, "POLICY_VERSION_MISMATCH")
        _need(v["scenario_id"] == _identity(v) and v["content_fingerprint"] == content_fingerprint(_body(v)), "FINGERPRINT_MISMATCH")
        _need(v["horizon"] is not None, "HORIZON_UNAVAILABLE")
        _need(authority is not None and v["producer_ref"] == authority["producer"], "SCENARIO_AUTHORITY_UNAVAILABLE")
        p, h, at = v["parcel"], v["horizon"], _time(v["decision_as_of"])
        _need(v["candidate_instrument_id"] != v["incumbent_instrument_id"], "INVALID_PARCEL")
        _need((v["candidate_instrument_id"], v["incumbent_instrument_id"]) == authority["pair"], "UNSUPPORTED_STATE")
        _need(_time(h["start"]) == at and _time(h["endpoint"]) > at, "HORIZON_UNAVAILABLE")
        _need(p["cash_contribution_inr"] in (None, "0"), "UNSUPPORTED_STATE")
        _need(v["policies"]["funding"] is not None and p["cash_contribution_inr"] is not None, "FUNDING_POLICY_UNSET")
        _need(v["policies"]["tax"] is not None, "TAX_POLICY_UNAVAILABLE")
        _need(v["policies"]["slippage"] is not None and len(v["slippage_legs"]) == 2, "SLIPPAGE_UNAVAILABLE")
        _need(all(v["policies"].values()), "POLICY_UNAVAILABLE")
        for identifier in (*v["policies"].values(), h["policy_ref"]):
            policy = authority["policies"].get(identifier)
            _need(policy is not None, "POLICY_UNAVAILABLE")
            _need(_time(policy["approved_at"]) <= at and _time(policy["effective_at"]) <= at, "FUTURE_EVIDENCE")
            _need(policy["applicable"] is True, "POLICY_UNAVAILABLE")
        refs = {r["id"]: r for r in v["evidence"]}
        for r in refs.values():
            _need(_time(r["known_at"]) <= at and _time(r["as_of"]) <= at, "FUTURE_EVIDENCE")
            pool = [_shape(x, "EvidenceRef") for x in authority["pool"].get(r["id"], [])
                    if x["id"] == r["id"] and x["version"] == r["version"]
                    and _time(x["known_at"]) <= at and _time(x["as_of"]) <= at]
            _need(len({canonical_json(x) for x in pool}) <= 1, "EVIDENCE_CONFLICTED")
            _need(pool and pool[0] == r, "LINEAGE_UNVERIFIED")
            freshness = authority["freshness"].get(r["id"])
            _need(freshness == "FRESH", "STALE_EVIDENCE" if freshness == "STALE" else "LINEAGE_UNVERIFIED")
        _need(v["candidate_endpoint"] is not None, "CANDIDATE_SCENARIO_UNAVAILABLE")
        _need(v["incumbent_endpoint"] is not None, "INCUMBENT_SCENARIO_UNAVAILABLE")
        # Synthetic numbers fit exactly. Production precision must be policy-bound.
        with localcontext() as ctx:
            ctx.prec = 80
            q, held, price, C = (Decimal(p[k]) for k in ("selected_quantity", "held_quantity", "incumbent_reference_price_inr", "switched_capital_inr"))
            _need(0 < q <= held and price > 0 and C > 0 and q * price == C, "INVALID_PARCEL")
            _need(all(p[k] is not None for k in ("candidate_quantity", "candidate_purchase_turnover_inr", "residual_capital_inr")), "FUNDING_POLICY_UNSET")
            cq, cp, purchase, residual = (Decimal(p[k]) for k in ("candidate_quantity", "candidate_reference_price_inr", "candidate_purchase_turnover_inr", "residual_capital_inr"))
            _need(cq > 0 and cp > 0 and purchase >= 0 and residual >= 0 and cq * cp == purchase and purchase + residual == C, "INVALID_PARCEL")
            for instrument, quantity in ((v["incumbent_instrument_id"], q), (v["candidate_instrument_id"], cq)):
                step = authority["quantity_steps"].get(instrument)
                _need(step is not None and step > 0 and quantity % step == 0, "INVALID_PARCEL")
            for key, instrument in (("candidate_endpoint", v["candidate_instrument_id"]), ("incumbent_endpoint", v["incumbent_instrument_id"])):
                endpoint = v[key]
                _need(endpoint["instrument_id"] == instrument and endpoint["parcel_fingerprint"] == content_fingerprint(p), "INVALID_PARCEL")
                _need(endpoint["horizon_fingerprint"] == content_fingerprint(h) and endpoint["model_ref"] == v["policies"]["paired_model"], "HORIZON_UNAVAILABLE")
                _need(Decimal(endpoint["terminal_gross_value_inr"]) >= 0, "INVALID_PARCEL")
            _need(v["tax_lots"] and v["tax_context_evidence_ids"], "TAX_INPUT_UNAVAILABLE")
            _need(all(Decimal(x["selected_quantity"]) > 0 for x in v["tax_lots"])
                  and sum(Decimal(x["selected_quantity"]) for x in v["tax_lots"]) == q, "TAX_INPUT_UNAVAILABLE")
            costs = {r["component"]: r for r in v["friction"]}
            _need(set(costs) == set(_read()["friction"]["components"]), "COST_EVIDENCE_UNAVAILABLE")
            _need(costs["capital_gains_tax"]["amount_inr"] is not None, "TAX_INPUT_UNAVAILABLE")
            _need(costs["slippage"]["amount_inr"] is not None, "SLIPPAGE_UNAVAILABLE")
            _need(all(r["amount_inr"] is not None and Decimal(r["amount_inr"]) >= 0 and r["evidence_ids"] for r in costs.values()), "COST_EVIDENCE_UNAVAILABLE")
            legs = {r["side"]: r for r in v["slippage_legs"]}
            _need(set(legs) == set(_read()["slippage"]["sides"]), "SLIPPAGE_UNAVAILABLE")
            for side, instrument, quantity, rp in (("INCUMBENT_DISPOSAL", v["incumbent_instrument_id"], q, price),
                                                   ("CANDIDATE_ACQUISITION", v["candidate_instrument_id"], cq, cp)):
                leg = legs[side]
                _need(leg["instrument_id"] == instrument and Decimal(leg["quantity"]) == quantity
                      and Decimal(leg["reference_price_inr"]) == rp and leg["amount_inr"] is not None
                      and Decimal(leg["amount_inr"]) >= 0 and leg["market_state_evidence_ids"], "SLIPPAGE_UNAVAILABLE")
            _need(sum(Decimal(x["amount_inr"]) for x in legs.values()) == Decimal(costs["slippage"]["amount_inr"]), "COST_DOUBLE_COUNT")
            # Hypothetical independent reproduction binds every source value, role,
            # unit, side, policy, reference and endpoint, not just caller fingerprints.
            _need(_body(v) == authority["expected_body"], "LINEAGE_UNVERIFIED")
            gross = Decimal(v["candidate_endpoint"]["terminal_gross_value_inr"]) - Decimal(v["incumbent_endpoint"]["terminal_gross_value_inr"])
            friction = sum(Decimal(x["amount_inr"]) for x in costs.values())
            net = gross - friction
        return dict(state="CONTRACT_CONFORMANT", reason_codes=[], gross_advantage_inr=str(gross),
                    net_advantage_inr=str(net), economic_predicate="POSITIVE" if net > 0 else "NON_POSITIVE", execution_authority=False)
    except (InvalidWitness, ValueError) as exc:
        code = str(exc)
        if code not in _read()["failure_contract"]["reason_codes"]:
            code = "INVALID_WIRE_SHAPE"
        state = "REJECTED" if code in ("INVALID_WIRE_SHAPE", "FINGERPRINT_MISMATCH") else "INSUFFICIENT_DATA"
        return dict(state=state, reason_codes=[code], **empty)


def test_contract_exact_parent_fingerprints_and_non_activation():
    c = _read()
    approval._verify(approval._read())
    assert c["contract_fingerprint"] == _digest(c) == FP
    assert c["baseline_commit"] == BASELINE
    assert c["parent"]["approval_fingerprint"] == approval.APPROVAL_FP
    assert c["parent"]["proposal_fingerprint"] == proposal.EXPECTED_FINGERPRINT
    assert c["status"] == "CONTRACT_SPECIFIED / GOVERNANCE_AND_TESTS_ONLY / NOT_ACTIVE"
    assert c["boundaries"] == approval._read()["boundaries"]
    assert c["blocker_effect"]["closed_operational_blockers"] == []
    assert c["authority_contract"]["registered_producers"] == []
    assert all(value is False for value in c["runtime"].values())
    assert c["horizon"]["numeric_value"] is None and c["economics"]["model"] == "POLICY_UNSET"
    assert c["tax"]["mandatory"] and c["tax"]["state"] == "POLICY_UNSET"
    assert c["slippage"]["mandatory"] and c["slippage"]["state"] == "NOT_READY"
    assert c["friction"]["rate_values"] == {} and c["scope"]["net_operator"] == ">"
    assert c["failure_contract"]["gate1_result_order"] == approval._read()["gate1_approval"]["result_precedence"]
    target, pointer = c["horizon"]["B09_reference"].split("#", 1)
    record = proposal._read(ROOT / target)
    for token in pointer.strip("/").split("/"):
        record = record[int(token)] if isinstance(record, list) else record[token]
    assert record["blocker_id"] == c["horizon"]["B09_blocker_id"] == "B09"
    assert record["resolution"] == "OPEN"
    assert FP in PATH.with_suffix(".md").read_text(encoding="utf-8")


@pytest.mark.parametrize("path,pin", _read()["frozen_files_lf"].items())
def test_frozen_core_and_all_governance_files_unchanged(path, pin):
    for raw in (subprocess.check_output(["git", "show", BASELINE + ":" + path]), (ROOT / path).read_bytes()):
        assert "sha256:" + sha256(raw.replace(b"\r\n", b"\n")).hexdigest() == pin


@pytest.mark.parametrize("terminal,net,predicate", [("1091", "1", "POSITIVE"), ("1090", "0", "NON_POSITIVE"), ("1089", "-1", "NON_POSITIVE")])
def test_valid_inr_partial_parcel_strict_zero_and_same_capital_pnl_identity(terminal, net, predicate):
    w, auth = _fixture(terminal)
    before = canonical_json(w)
    result = _assess(w, auth)
    assert result["state"] == "CONTRACT_CONFORMANT" and result["net_advantage_inr"] == net
    assert result["economic_predicate"] == predicate and not result["execution_authority"]
    C = Decimal(w["parcel"]["switched_capital_inr"])
    assert (Decimal(terminal) - C) - (Decimal("1080") - C) == Decimal(result["gross_advantage_inr"])
    assert canonical_json(w) == before
    gate = "PASS" if predicate == "POSITIVE" else "FAIL"
    assert approval.previous._compose([gate] + ["PASS"] * 5).eligibility.value == ("EXECUTABLE" if gate == "PASS" else "BLOCKED")


@pytest.mark.parametrize("selected,held", [("10", "20"), ("10", "10")])
def test_partial_and_explicit_full_selected_parcel_not_implicitly_nav(selected, held):
    w, auth = _fixture(selected=selected, held=held)
    assert _assess(w, auth)["state"] == "CONTRACT_CONFORMANT"


@pytest.mark.parametrize("gap,terminal,expected", [("0.99", "1091", "BLOCKED"), ("1.00", "1091", "EXECUTABLE"), ("2", "1090", "BLOCKED")])
def test_score_and_economic_hurdles_are_independent(gap, terminal, expected):
    w, auth = _fixture(terminal)
    r = _assess(w, auth)
    # Synthetic declared policy outcomes only, no new runtime evaluator.
    state = "FAIL" if Decimal(gap) < 1 or r["economic_predicate"] != "POSITIVE" else "PASS"
    assert approval.previous._compose([state] + ["PASS"] * 5).eligibility.value == expected
    assert _read()["scope"]["score_formula"] == "raw_decision_score - comparison_score >= 1.00"


@pytest.mark.parametrize("path,value,code", [
    ("horizon", None, "HORIZON_UNAVAILABLE"), ("producer_ref", None, "SCENARIO_AUTHORITY_UNAVAILABLE"),
    ("candidate_endpoint", None, "CANDIDATE_SCENARIO_UNAVAILABLE"), ("incumbent_endpoint", None, "INCUMBENT_SCENARIO_UNAVAILABLE"),
    ("policies/tax", None, "TAX_POLICY_UNAVAILABLE"), ("tax_lots", [], "TAX_INPUT_UNAVAILABLE"),
    ("tax_context_evidence_ids", [], "TAX_INPUT_UNAVAILABLE"), ("slippage_legs", [], "SLIPPAGE_UNAVAILABLE"),
    ("policies/slippage", None, "SLIPPAGE_UNAVAILABLE"), ("policies/funding", None, "FUNDING_POLICY_UNSET"),
    ("parcel/cash_contribution_inr", None, "FUNDING_POLICY_UNSET"), ("parcel/cash_contribution_inr", "1", "UNSUPPORTED_STATE"),
    ("parcel/selected_quantity", "0", "INVALID_PARCEL"), ("parcel/selected_quantity", "-1", "INVALID_PARCEL"),
    ("parcel/selected_quantity", "21", "INVALID_PARCEL"), ("parcel/switched_capital_inr", "0", "INVALID_PARCEL"),
    ("parcel/switched_capital_inr", "-1", "INVALID_PARCEL"),
    ("parcel/switched_capital_inr", "2000", "INVALID_PARCEL"), ("parcel/residual_capital_inr", "100", "INVALID_PARCEL"),
    ("candidate_endpoint/parcel_fingerprint", "sha256:" + "0" * 64, "INVALID_PARCEL"),
    ("incumbent_endpoint/horizon_fingerprint", "sha256:" + "0" * 64, "HORIZON_UNAVAILABLE"),
    ("contract_version", "v2", "POLICY_VERSION_MISMATCH"), ("policies/cost", "TEST:unknown", "POLICY_UNAVAILABLE"),
])
def test_missing_invalid_or_ambiguous_requirement_fails_closed(path, value, code):
    w, auth = _fixture()
    target = w
    *parents, key = path.split("/")
    for name in parents:
        target = target[name]
    target[key] = value
    result = _assess(_seal(w), auth)
    assert result["reason_codes"] == [code]
    assert result["net_advantage_inr"] is None and not result["execution_authority"]


@pytest.mark.parametrize("component,code", [("slippage", "SLIPPAGE_UNAVAILABLE"), ("capital_gains_tax", "TAX_INPUT_UNAVAILABLE"), ("brokerage", "COST_EVIDENCE_UNAVAILABLE")])
def test_missing_friction_component_never_defaults_to_zero(component, code):
    w, auth = _fixture()
    next(r for r in w["friction"] if r["component"] == component)["amount_inr"] = None
    assert _assess(_seal(w), auth)["reason_codes"] == [code]


@pytest.mark.parametrize("value", ["USD", "PERCENT"])
def test_invalid_units_are_never_compared(value):
    w, auth = _fixture()
    w["currency"] = value
    assert _assess(w, auth)["reason_codes"] == ["INVALID_UNIT"]


@pytest.mark.parametrize("value", [0, 0.0, "NaN", "Infinity", True])
def test_numeric_wire_values_must_be_exact_decimal_strings(value):
    w, auth = _fixture()
    w["parcel"]["switched_capital_inr"] = value
    assert _assess(w, auth)["state"] == "REJECTED"


def test_costs_deducted_once_and_forged_cost_exclusion_rejected():
    w, auth = _fixture()
    assert _assess(w, auth)["net_advantage_inr"] == "1"  # 11 - 10, not slippage/tax twice.
    w["candidate_endpoint"]["terminal_gross_value_inr"] = "1081"  # Hidden cost deduction, same lineage.
    assert _assess(_seal(w), auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]
    w, auth = _fixture()
    w["candidate_endpoint"]["cost_basis"] = "NET_OF_COSTS"
    assert _assess(w, auth)["state"] == "REJECTED"


def test_tampering_is_rejected_without_rehash_repair_or_identity_circularity():
    w, auth = _fixture()
    old_id, old_fp = w["scenario_id"], w["content_fingerprint"]
    w["candidate_endpoint"]["terminal_gross_value_inr"] = "99999"
    assert _identity(w) == old_id  # Same inputs, different output -> content tamper.
    assert content_fingerprint(_body(w)) != old_fp
    assert _assess(w, auth)["reason_codes"] == ["FINGERPRINT_MISMATCH"]
    assert w["content_fingerprint"] == old_fp
    assert _assess(_seal(w), auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]


@pytest.mark.parametrize("who", ["USER", "AI", "ANALYST", "DETERMINISTIC_HSI_DERIVED_SCENARIO"])
def test_self_hash_or_claimed_role_is_not_registered_authority(who):
    w, auth = _fixture()
    w["producer_ref"] = "TEST:" + who
    assert _assess(_seal(w), auth)["reason_codes"] == ["SCENARIO_AUTHORITY_UNAVAILABLE"]
    assert _assess(_fixture()[0])["reason_codes"] == ["SCENARIO_AUTHORITY_UNAVAILABLE"]


def test_future_policies_and_required_evidence_fail_but_unseen_future_pool_does_not_rewrite_history():
    w, auth = _fixture()
    original = _assess(w, auth)
    future = deepcopy(w["evidence"][0])
    future["known_at"] = "2026-09-01T12:00:01+00:00"
    future["fingerprint"] = "sha256:" + "f" * 64
    auth["pool"][future["id"]].append(future)
    assert _assess(w, auth) == original
    future["known_at"] = AT
    assert _assess(w, auth)["reason_codes"] == ["EVIDENCE_CONFLICTED"]
    for field in ("approved_at", "effective_at"):
        w, auth = _fixture()
        auth["policies"][w["policies"]["tax"]][field] = "2026-09-01T12:00:01+00:00"
        assert _assess(w, auth)["reason_codes"] == ["FUTURE_EVIDENCE"]
    for field in ("as_of", "known_at"):
        w, auth = _fixture()
        w["evidence"][0][field] = "2026-09-01T12:00:01+00:00"
        assert _assess(_seal(w), auth)["reason_codes"] == ["FUTURE_EVIDENCE"]


def test_exact_replay_order_duplicates_timezone_and_decimal_normalization():
    w, auth = _fixture()
    encoded = canonical_json(w)
    assert _assess(json.loads(encoded), auth) == _assess(w, auth)
    changed = deepcopy(w)
    changed["evidence"].reverse()
    changed["evidence"].append(deepcopy(changed["evidence"][0]))
    changed["friction"].reverse()
    changed["slippage_legs"].reverse()
    changed["decision_as_of"] = "2026-09-01T17:30:00+05:30"
    changed["parcel"]["selected_quantity"] = "10.0000"
    assert _identity(changed) == w["scenario_id"]
    assert _assess(changed, auth) == _assess(w, auth)
    assert _assess(json.loads(encoded))["state"] == "INSUFFICIENT_DATA"


def test_duplicate_conflicting_cost_and_reference_inputs_are_not_silently_discarded():
    for collection in ("friction", "tax_lots", "slippage_legs"):
        w, auth = _fixture()
        w[collection].append(deepcopy(w[collection][0]))
        assert _assess(w, auth)["reason_codes"] == ["EVIDENCE_CONFLICTED"]
    w, auth = _fixture()
    conflict = deepcopy(w["evidence"][0])
    conflict["fingerprint"] = "sha256:" + "0" * 64
    w["evidence"].append(conflict)
    assert _assess(w, auth)["reason_codes"] == ["EVIDENCE_CONFLICTED"]


def test_no_lot_invention_stale_applicability_or_active_horizon_default():
    c = _read()
    assert c["tax"]["weighted_average_portfolio_basis_is_tax_basis"] is False
    assert c["tax"]["default_FIFO_or_rate"] is False
    proposal.test_b09_namespaced_dependency_is_applicability_not_a_numeric_holding_period()
    w, auth = _fixture()
    auth["policies"][w["policies"]["freshness"]]["applicable"] = False
    assert _assess(w, auth)["reason_codes"] == ["POLICY_UNAVAILABLE"]
    w["tax_lots"][0]["selected_quantity"] = "20"
    w, auth = _seal(w), _fixture()[1]
    assert _assess(w, auth)["reason_codes"] == ["TAX_INPUT_UNAVAILABLE"]
    w, auth = _fixture()
    auth["freshness"][w["evidence"][0]["id"]] = "STALE"
    assert _assess(w, auth)["reason_codes"] == ["STALE_EVIDENCE"]


def test_contract_loading_cannot_change_v1_any_gate_or_register_v2():
    approval.test_independent_gate_definitions_methods_config_and_v1_result_remain_unchanged()
    previous_result = approval.previous._compose(["PASS"] * 6)
    _read()
    assert approval.previous._compose(["PASS"] * 6) == previous_result
    assert _read()["authority_contract"]["production_registration"] is False
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "GATE1_ROTATION_ECONOMIC_SCENARIO_CONTRACT_V1" not in text
        assert "gate1-rotation-economic-scenario" not in text


def test_contract_fingerprint_covers_all_fields_and_stable_replay():
    c = _read()
    assert _digest(json.loads(canonical_json(c))) == _digest(dict(reversed(tuple(c.items())))) == FP
    for key in c.keys() - {"contract_fingerprint"}:
        changed = deepcopy(c)
        del changed[key]
        assert _digest(changed) != FP


@pytest.mark.parametrize("field", ["expected_return", "probability", "portfolio_nav", "order", "extra_cost"])
def test_no_unrecognized_authority_or_economic_fields(field):
    w, auth = _fixture()
    w[field] = "1"
    assert _assess(w, auth)["reason_codes"] == ["INVALID_WIRE_SHAPE"]


def test_required_transitive_provenance_cannot_be_deleted_or_retyped_and_resealed():
    for role in ("POLICY", "SCENARIO_PRODUCER", "PORTFOLIO_SNAPSHOT", "PRICE",
                 "ENDPOINT_INPUT", "TAX_LOT", "TAX_BASIS", "TAX_CONTEXT", "SCORE", "COST", "SLIPPAGE"):
        w, auth = _fixture()
        ref = next(r for r in w["evidence"] if r["role"] == role)
        w["evidence"].remove(ref)
        assert _assess(_seal(w), auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]
        w, auth = _fixture()
        next(r for r in w["evidence"] if r["role"] == role)["role"] = "USER_ASSERTION"
        assert _assess(_seal(w), auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]


def test_pinned_version_does_not_silently_select_newer_policy_or_false_conflict():
    w, auth = _fixture()
    result = _assess(w, auth)
    assert result["state"] == "CONTRACT_CONFORMANT"  # Boundary equals decision cutoff.
    ref = deepcopy(w["evidence"][0])
    auth["pool"][ref["id"]].append(deepcopy(ref))  # Idempotent identical receipt.
    newer = deepcopy(ref)
    newer["version"], newer["fingerprint"] = "fixture-v2", "sha256:" + "f" * 64
    auth["pool"][ref["id"]].insert(0, newer)
    assert _assess(w, auth) == result
    auth["pool"][ref["id"]] = [newer]
    assert _assess(w, auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]


@pytest.mark.parametrize("side", ["candidate_instrument_id", "incumbent_instrument_id"])
def test_quantity_quantum_and_exact_identity_are_bound_separately_for_each_leg(side):
    w, auth = _fixture()
    auth["quantity_steps"][w[side]] = Decimal("3")  # Test-only incompatible quantum.
    assert _assess(w, auth)["reason_codes"] == ["INVALID_PARCEL"]
    w, auth = _fixture()
    w[side] = "NSE:UNKNOWN"
    assert _assess(_seal(w), auth)["reason_codes"] == ["UNSUPPORTED_STATE"]


def test_verified_zero_is_distinct_from_missing_slippage_and_no_secondary_cost():
    w, auth = _fixture()
    for leg in w["slippage_legs"]:
        leg["amount_inr"] = "0"
    next(r for r in w["friction"] if r["component"] == "slippage")["amount_inr"] = "0"
    # A caller's all-zero claim is not proof. No production model exists here.
    assert _assess(_seal(w), auth)["reason_codes"] == ["LINEAGE_UNVERIFIED"]
    w, auth = _fixture()
    w["slippage_legs"][0]["amount_inr"] = "1.5"
    assert _assess(_seal(w), auth)["reason_codes"] == ["COST_DOUBLE_COUNT"]
