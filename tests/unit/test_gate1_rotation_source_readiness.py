"""Read-only Gate 1 source-readiness receipt and frozen-contract proofs."""
from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint
from app.gates.engine import ActionContext, ExecutionGateEngine, GateInput, GateOutcome
from app.gates.production_policy import approved_six_gates_production_policy
from app.gates.source_readiness import SourceReadiness, source_gap


RECEIPT = json.loads(Path("docs/architecture/GATE1_ROTATION_SOURCE_READINESS_V1.json").read_text(encoding="utf-8"))
AS_OF = datetime(2026, 9, 1, tzinfo=timezone.utc)


def _input(**changes):
    base = GateInput(
        scorecard_id="synthetic-gate1-audit",
        raw_decision_score=Decimal("9"),
        snapshot_id="synthetic-snapshot",
        snapshot_as_of_timestamp=AS_OF,
        comparison_score=Decimal("7"),
        expected_incremental_return=Decimal("2"),
        modeled_switching_friction=Decimal("1"),
    )
    return GateInput(**({field.name: getattr(base, field.name) for field in fields(GateInput)} | changes))


def _rotation(data, context=ActionContext.ROTATE_IN):
    policy = approved_six_gates_production_policy(approved_at=AS_OF)
    return ExecutionGateEngine(policy.gate_config, calendar=None)._rotation(context, data, ())


def test_receipt_is_canonical_and_records_exact_final_policy_blocker():
    payload = {key: value for key, value in RECEIPT.items() if key != "receipt_fingerprint"}
    assert RECEIPT["receipt_fingerprint"] == content_fingerprint(payload)
    assert canonical_json(RECEIPT) == canonical_json(json.loads(canonical_json(RECEIPT)))
    assert RECEIPT["baseline_commit"] == "95c187a0adb7d8dc8942695003326460de5a7da6"
    assert RECEIPT["status"] == "GATE1_ROTATION_POLICY_DEFINITION_REPAIR_REQUIRED"
    assert RECEIPT["dominant_repair"]["next_continuation"] == "GATE1_ROTATION_POLICY_DEFINITION_REPAIR_V1"
    assert not RECEIPT["runtime_producer_active"] and not RECEIPT["policy_change_authorized"]


def test_exact_gate1_inputs_are_bare_decimals_and_source_gaps_remain_governance_not_data_ready():
    annotation = GateInput.__annotations__
    assert annotation["expected_incremental_return"] == "Decimal | None"
    assert annotation["modeled_switching_friction"] == "Decimal | None"
    for field in ("expected_incremental_return", "modeled_switching_friction"):
        gap = source_gap(field)
        assert gap is not None
        assert gap.state is SourceReadiness.SOURCE_GOVERNANCE_REQUIRED
        assert gap.blocker == "GATE1_FRICTION_POLICY_AUTHORITY_NOT_READY"
    inputs = {value["field"]: value for value in RECEIPT["substantive_inputs"]}
    assert all(value["declared_domain_family"] == "USER_APPROVED_CONTEXT" for value in inputs.values())
    assert inputs["expected_incremental_return"]["semantic_state"] == "POLICY_DEFINITION_MISSING"
    assert inputs["expected_incremental_return"]["unit_state"] == "UNSPECIFIED"
    assert inputs["modeled_switching_friction"]["unit_state"] == "INR_ABSOLUTE_AMOUNT"


def test_synthetic_formula_liveness_keeps_strict_hurdle_and_missing_evidence_fail_closed():
    assert _rotation(_input(raw_decision_score=Decimal("7.9"))).outcome is GateOutcome.FAIL
    assert _rotation(_input(expected_incremental_return=None)).outcome is GateOutcome.INSUFFICIENT_DATA
    assert _rotation(_input(expected_incremental_return=Decimal("1"), modeled_switching_friction=Decimal("1"))).outcome is GateOutcome.FAIL
    assert _rotation(_input()).outcome is GateOutcome.PASS


@pytest.mark.parametrize("context", tuple(value for value in ActionContext if value is not ActionContext.ROTATE_IN))
def test_existing_non_rotation_contexts_are_not_an_economic_source_clearance(context):
    decision = _rotation(_input(expected_incremental_return=None, modeled_switching_friction=None), context)
    assert decision.outcome is GateOutcome.PASS
    assert decision.detail == "not applicable: no holding is being replaced"


def test_trade_plan_and_rotation_candidate_remain_outside_the_gate1_economic_producer_contract():
    from app.rotation.models import RotationCandidate
    from app.signals.models import TradePlan

    assert "expected_incremental_return" not in {field.name for field in fields(TradePlan)}
    assert "modeled_switching_friction" in {field.name for field in fields(RotationCandidate)}
    assert "expected_incremental_benefit" in {field.name for field in fields(RotationCandidate)}
    assert RECEIPT["reuse_audit"]["portfolio_rotation_challenger"].endswith("NO_GATE1_PRODUCER")
