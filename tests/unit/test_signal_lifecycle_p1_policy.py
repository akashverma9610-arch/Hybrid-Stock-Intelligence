"""Documentation conformance only; deliberately no lifetime reducer/writer.

These tests pin predecessor contracts, native field/reason compatibility and
the finite policy vocabulary. They are not runtime lifecycle scenario proof.
"""
import ast
from dataclasses import fields
from hashlib import sha256
import json
from pathlib import Path
import re

import pytest

from app.historical.security_master import HistoricalSecurityStatus
from app.intelligence.hsi_signal import HSISignal, HSISignalActionability, HSISignalExecutionStatus
from app.intelligence.opportunity_archetypes import OpportunityArchetype
from app.strategies.pre_breakout.candidate_assembly import PreBreakoutCandidate, assemble_prebreakout_candidate
from app.strategies.pre_breakout.materialization import PreBreakoutStructuralStatus
from app.strategies.pre_breakout.setup_assessment import PreBreakoutSetupBlockerCategory
from tests.unit.test_pre_breakout_candidate_assembly import _assessment


DOC = Path("docs/architecture/SIGNAL_LIFECYCLE_P1_COMPATIBILITY_POLICY_V1.md")
PINS = {
    "app/intelligence/hsi_signal.py": "85fddffaa85dd04ffac9c7aaf89acd04344b5621af3e3157a2edac81d2dc57e9",
    "app/intelligence/hsi_signal_strategy_registry.py": "6dc5d310d96bbb48544ff094834039f7d7a4abc177043dd83680025773aa6fea",
    "app/intelligence/hsi_signal_projection.py": "f75290810e75686b7af9e13aa336e0b8428e48061b2b21b356e4142f1342ac88",
    "app/intelligence/market_wide_watch.py": "4b065faedf7c23d3a294f056e5bf4ca916c56cc3e5dcf04a55a4260392aa8fd5",
    "app/strategies/pre_breakout/setup_assessment.py": "4808aa4a880867e63990da2c83cfb44b27a995ea4103f21d4a9e3da1eaa74bee",
    "app/strategies/pre_breakout/candidate_assembly.py": "ba3f57657b65acf011f831afb48d0c6990e5ada5713e4c98fcc5fb608d9e4e34",
    "docs/architecture/POST_V1_HSI_SIGNAL_P1_ACTIVATION_PROPOSAL.md": "554cdcc2d175212dacd33d49347c4bf0283c288f2c67fe480d719a447c72f6b0",
}


def contract():
    blocks = re.findall(r"```json\n(.*?)\n```", DOC.read_text(encoding="utf-8"), re.S)
    assert len(blocks) == 1
    return json.loads(blocks[0])


@pytest.mark.parametrize("name,expected", tuple(PINS.items()))
def test_frozen_predecessor_content_unchanged(name, expected):
    # Universal-newline text hash is portable between Git LF and Windows CRLF.
    assert sha256(Path(name).read_text(encoding="utf-8").encode()).hexdigest() == expected


def test_three_states_have_no_terminal_resurrection_or_expiry_edge():
    value = contract()
    assert value["states"] == ["CURRENT", "INVALIDATED", "SUPERSEDED"]
    assert value["terminal_states"] == ["INVALIDATED", "SUPERSEDED"]
    assert value["edges"] == [
        [None, "CURRENT", "INITIAL_QUALIFICATION"],
        ["CURRENT", "CURRENT", "SETUP_CONTINUED"],
        ["CURRENT", "INVALIDATED", "SETUP_PREDICATE_FAILED"],
        ["CURRENT", "SUPERSEDED", "REPLACED_BY_QUALIFYING_SETUP"],
        ["CURRENT", "INVALIDATED", "SECURITY_LIFECYCLE_ENDED"],
    ]
    assert not any(edge[0] in value["terminal_states"] for edge in value["edges"])
    assert value["expiry"] == "EXPIRY_NOT_GOVERNED_FOR_THIS_PATH"


def test_geometry_key_is_exact_native_fields_not_a_second_setup_calculation():
    value = contract()
    names = value["geometry_fields"]
    assert names == ["base_start", "base_end", "base_duration", "base_top", "resistance",
                     "breakout_confirmation_trigger", "structural_support", "final_structural_stop",
                     "measured_move_target", "tick_size"]
    assert set(names) <= {f.name for f in fields(PreBreakoutCandidate)}
    candidate = assemble_prebreakout_candidate(_assessment())
    assert all(getattr(candidate, name) is not None for name in names)
    assert not set(names) & {"evaluation_as_of", "entry_reference_price", "tick_record_id", "rsi14"}


def test_negative_predicates_use_only_existing_native_categories_and_codes():
    native = "\n".join(Path(path).read_text(encoding="utf-8") for path in (
        "app/strategies/pre_breakout/setup_assessment.py",
        "app/strategies/pre_breakout/materialization.py",
    ))
    strings = {node.value for node in ast.walk(ast.parse(native))
               if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    negative = contract()["negative_codes"]
    assert set(negative) == {PreBreakoutSetupBlockerCategory.TECHNICAL_SETUP_FAIL.value,
                             PreBreakoutSetupBlockerCategory.STRUCTURAL_SETUP_FAIL.value}
    assert sum(len(codes) for codes in negative.values()) == 8
    assert all(code in strings for codes in negative.values() for code in codes)
    assert PreBreakoutStructuralStatus.BASE_STRUCTURE_BROKEN.value == "BASE_STRUCTURE_BROKEN"
    assert PreBreakoutStructuralStatus.NO_VALID_BASE_WINDOW.value == "NO_VALID_BASE_WINDOW"
    assert {HistoricalSecurityStatus.DELISTED.value, HistoricalSecurityStatus.MERGED.value} == {"DELISTED", "MERGED"}


def test_policy_preserves_p1_authority_and_unavailable_fields():
    value = contract()
    assert value["strategy"] == OpportunityArchetype.PRE_BREAKOUT.value
    assert value["actionability"] == HSISignalActionability.WATCH_ONLY.value
    assert value["execution_status"] == HSISignalExecutionStatus.NON_EXECUTABLE.value
    p1 = {f.name: f for f in fields(HSISignal)}
    assert p1["expires_at"].default is None and p1["expires_at"].init is False
    assert not {"lifetime_id", "prior_state", "next_state", "setup_instance_key"} & p1.keys()
    assert all(p1[name].default is None for name in ("strength", "confidence", "materiality"))


def test_all_ten_required_scenarios_have_explicit_non_runtime_decisions():
    assert contract()["cases"] == {
        "A": "FIRST_QUALIFICATION_NEW_CURRENT",
        "B": "IDENTICAL_INPUT_NO_CHANGE",
        "C": "MATCHING_KEYS_CURRENT_TO_CURRENT",
        "D": "ALLOWED_COMPLETE_NEGATIVE_TERMINAL_INVALIDATION",
        "E": "RECOVERY_NEW_LIFETIME_NEVER_RESURRECTION",
        "F": "CHANGED_GEOMETRY_ATOMIC_SUPERSESSION_AND_ADMISSION",
        "G": "FUTURE_INPUT_REJECTED_NO_TRANSITION",
        "H": "NEW_PROVENANCE_NEW_LIFETIME_ONLY_IF_QUALIFIED",
        "I": "AUTHORITY_UNAVAILABLE_BLOCK_NEW_EMISSION_PRESERVE_HISTORY",
        "J": "DUPLICATE_NO_OP_OR_CAS_RELOAD_WITHOUT_DOUBLE_TRANSITION",
    }


def test_document_settles_scope_storage_ordering_and_exactly_one_next_slice():
    body = DOC.read_text(encoding="utf-8")
    assert re.findall(r"^## (LC-\d+)", body, re.M) == [f"LC-{i:02}" for i in range(1, 17)]
    for required in ("DIRECTLY_DERIVED_FROM_P1", "COMPATIBLE_EXTENSION",
                     "REJECTED_AS_LEGACY_CONFLICT", "DEFERRED", "BEGIN IMMEDIATE",
                     "UNIQUE(slot_key, input_key)", "UNIQUE(slot_key, accepted_cutoff)",
                     "POLICY_BLOCKED", "SOURCE_BLOCKED", "NOT_RUNTIME_ACTIVE",
                     "V1 ACTIVE", "Execution Gate V2 NOT_ACTIVE"):
        assert required in body
    assert body.count("SIGNAL_LIFECYCLE_P1_RUNTIME_BINDING_V1") == 1
    assert "NOTIFICATION" not in contract()["states"]
    assert len(contract()["blocked_reasons"]) == len(set(contract()["blocked_reasons"]))


def test_policy_local_links_resolve_and_whitespace_is_clean():
    body = DOC.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", body):
        assert (DOC.parent / target).is_file(), target
    assert all(line == line.rstrip() for line in body.splitlines())
