"""Safety and coverage tests for read-only lens readiness planning."""
import pytest

from app.lens_knowledge.assessment import load_catalog
from app.lens_knowledge.readiness_planner import InputReadiness, build_readiness_plans


def test_all_35_lenses_fail_closed_on_empty_certifications():
    result = build_readiness_plans(diagnostic_states={}, dependency_states={})
    assert len(result) == 35
    assert {r.lens_id for r in result} == {l.lens_id for l in load_catalog()}
    assert all(r.policy_status == "PROPOSED_NOT_ACTIVE" and r.lens_fit == "NOT_EVALUATED" for r in result)
    assert all(r.source_readiness == "MISSING" for r in result)
    assert all(r.blocked_diagnostics or r.blocked_dependencies for r in result)


def test_one_diagnostic_does_not_auto_approve_lenses():
    result = build_readiness_plans(
        diagnostic_states={"D04": InputReadiness.READY}, dependency_states={}
    )
    assert all(r.policy_status == "PROPOSED_NOT_ACTIVE" and r.lens_fit == "NOT_EVALUATED" for r in result)
    assert any("D04" in r.ready_diagnostics for r in result)


def test_explicit_conflict_is_never_ready():
    result = build_readiness_plans(
        diagnostic_states={"D04": InputReadiness.CONFLICTED}, dependency_states={}
    )
    assert any(r.source_readiness == "CONFLICTED" for r in result)


def test_unknown_dependency_and_bad_state_rejected():
    with pytest.raises(ValueError, match="UNKNOWN_LENS_DEPENDENCY"):
        build_readiness_plans(diagnostic_states={}, dependency_states={"G999": InputReadiness.READY})
    with pytest.raises(ValueError, match="INVALID_READINESS_STATE"):
        build_readiness_plans(diagnostic_states={"D04": "READY"}, dependency_states={})


def test_even_all_proposed_inputs_are_not_lens_approval():
    catalog = load_catalog()
    gaps = {g for lens in catalog for g in lens.unresolved_dependencies}
    results = build_readiness_plans(
        diagnostic_states={f"D{i:02d}": InputReadiness.READY for i in range(1, 62)},
        dependency_states={gap: InputReadiness.READY for gap in gaps},
    )
    assert len(results) == 35
    assert all(r.source_readiness == "PROVISIONAL_INPUTS_PRESENT" for r in results)
    assert all(r.policy_status == "PROPOSED_NOT_ACTIVE" and r.lens_fit == "NOT_EVALUATED" for r in results)
