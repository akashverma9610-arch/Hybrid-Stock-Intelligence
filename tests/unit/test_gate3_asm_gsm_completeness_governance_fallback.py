"""Static governance/threat examples; no upload, importer or Gate implementation."""
from copy import deepcopy
from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path

import pytest

from app.fundamentals.diagnostic_comparability import canonical_json, content_fingerprint


ROOT = Path(__file__).resolve().parents[2]
ARTIFACT = ROOT / "docs/architecture/GATE3_ASM_GSM_COMPLETENESS_GOVERNANCE_FALLBACK_V1.json"
NEXT = "NSE_EXECUTION_MASTER_CURRENT_CAPTURE_CONTINUITY_REPAIR_V1"
OPTION_IDS = {
    "CONTROLLED_OFFICIAL_EXPORT_INGESTION", "POSITIVE_ONLY_GATE3_POLICY_AMENDMENT",
    "HARD_BLOCK_UNTIL_MACHINE_COMPLETE", "BROWSER_AUTOMATION",
}
CONFLICTS = {"HASH_OR_LINEAGE_MISMATCH", "IDENTITY_CONFLICT", "API_ARTIFACT_MATERIAL_CONFLICT"}
UNKNOWN = {
    "MISSING_CURRENT_ARTIFACT", "PARTIAL_FILE", "SCHEMA_DRIFT", "MISSING_REQUIRED_COMPONENT",
    "REJECTED_ROW", "UNPROVEN_PRODUCT_BINDING", "MISSING_OPERATOR_PROVENANCE",
    "UNAUTHORIZED_OR_NO_MFA", "UNSUPPORTED_STAGE", "STALE_OR_EFFECTIVE_STATE_UNRESOLVED",
    "WELL_FORMED_OMISSION_NOT_RULED_OUT",
}
CONTROLS = {
    "AUTHENTICATED_ADMIN_RA_OR_DELEGATED_OPERATOR", "MFA", "ACTION_AUTHORIZATION",
    "IMMUTABLE_AUDIT", "IMMUTABLE_RAW_RETENTION", "SHA256", "NO_FILE_MUTATION",
    "REPLAY_IDEMPOTENCY", "BOUNDED_SCHEMA_VALIDATION",
}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_GOVERNANCE_KEY")
        result[key] = value
    return result


def _read(path=ARTIFACT):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _digest(value):
    return content_fingerprint({k: v for k, v in value.items() if k != "fingerprint"})


def _verify(value):
    """Test-only review guard; a rehash does not authorize changed semantics."""
    assert _digest(value) == value["fingerprint"]
    assert value["decision"] == "C"
    assert value["result"] == "KEEP_GATE3_BLOCKED_UNTIL_MACHINE_COMPLETE"
    assert value["status"] == "DECIDED_GOVERNANCE_ONLY_NOT_ACTIVE"
    assert value["next_continuation"] == NEXT and value["next_continuation_started"] is False
    evidence = value["current_evidence"]
    assert evidence["asm_capture"] == evidence["gsm_capture"] == "UNPROVEN"
    assert evidence["price_band_file_capture"] == "COMPLETE"
    assert evidence["execution_master_continuity"] == "OPEN"
    assert evidence["execution_master_scope"] == "SEPARATE_OPEN_BLOCKER"
    for key in ("official_ui_export_bytes_validated", "asm_export_scope_proven", "gsm_complete_component_manifest_proven"):
        assert evidence[key] is False
    policy = value["frozen_policy"]
    proposal = _read(ROOT / "docs/architecture/GATE3_SURVEILLANCE_POLICY_V2_PROPOSAL.json")
    assert policy["candidate_id"] == proposal["proposal_id"]
    assert policy["candidate_version"] == proposal["proposal_version"]
    assert policy["blocking_thresholds"] == proposal["gate3_proposed"]["blocking_thresholds"]
    assert policy["formula_inputs"] == ["ASM", "GSM", "PRICE_BAND"]
    assert policy["activation"] == "NOT_ACTIVE" and policy["all_three_components_required"] is True
    assert policy["blocking_plus_missing"] == "INSUFFICIENT_DATA"
    assert policy["independent_positive_veto"] is False and policy["security_status"] == "DESCRIPTIVE_ONLY"
    assert policy["selected_fallback_execution_policy_change"] == "NONE"
    assert policy["hypothetical_controlled_transport_change"] == "SOURCE_GOVERNANCE_ADDENDUM"
    assert policy["hypothetical_positive_only_change"] == "COMPOSITE_POLICY_AMENDMENT_REQUIRED"
    transport = value["controlled_transport"]
    assert transport["status"] == "CONDITIONAL_REQUIREMENTS_ONLY_NOT_APPROVED_OR_IMPLEMENTED"
    assert transport["source_authority"] == value["authority"]["source_authority"] == "NSE_OFFICIAL_PRODUCT"
    assert transport["operator_authority"] == "TRANSPORT_ONLY"
    assert transport["origin_state"] == "OFFICIAL_ORIGIN_ATTESTED"
    assert transport["cryptographic_source_authenticity"] == "UNPROVEN"
    assert set(transport["controls_required"]) == CONTROLS
    for key in ("completeness_by_attestation", "hash_authenticates_nse", "operator_set_stage",
                "operator_set_band", "operator_set_clearance", "operator_set_gate_result",
                "row_count_only_proof", "hidden_omissions_detectable_from_plain_schema",
                "completeness_implies_gate_admission", "security_controls_currently_verified"):
        assert transport[key] is False
    assert transport["asm_required_scope"] == ["longterm", "shortterm"]
    assert transport["gsm_required_scope"] == "SOURCE_DEFINED_COMBINED_PRODUCT_OR_EXHAUSTIVE_MANIFEST_UNPROVEN"
    known = value["first_observed"]
    assert known["source"] == "AUTOMATIC_HSI_COMPLETE_PAYLOAD_INGESTION_TIME"
    assert set(known["disallowed_sources"]) == {
        "FILE_CREATION_TIME", "FILE_MODIFICATION_TIME", "OPERATOR_DOWNLOAD_TIME",
        "NSE_PUBLICATION_DATE", "OPERATOR_HISTORICAL_TIMESTAMP", "REQUEST_START_TIME",
    }
    assert known["inclusive_as_of"] is known["later_validation_requires_own_known_at"] is True
    assert known["identical_reupload"] == "REUSE_EARLIEST_RAW_OBSERVATION_NEW_ACTION_AUDIT"
    assert known["reupload_renews_effective_age"] is known["retroactive_rewrite"] is False
    api = value["api_role"]
    assert api["role"] == "DISCOVERY_ONLY"
    assert api["api_positive_missing_in_artifact"] == ["CONFLICTED", "INSUFFICIENT_DATA"]
    assert api["future_evidence"] == "EXCLUDE_BEFORE_CONFLICT_AND_LINEAGE"
    for key in ("negative_evidence_allowed", "raw_positive_is_gate_veto", "voting",
                "row_count_preference", "latest_timestamp_wins", "human_override"):
        assert api[key] is False
    cases = value["failure_cases"]
    assert len(cases) == len(CONFLICTS | UNKNOWN)
    assert {row["id"] for row in cases} == CONFLICTS | UNKNOWN
    for row in cases:
        assert row["gate"] == "INSUFFICIENT_DATA"
        assert row["component"] == ("CONFLICTED" if row["id"] in CONFLICTS else "UNKNOWN")
    options = {row["id"]: row for row in value["options"]}
    assert len(value["options"]) == len(options) == 4 and options.keys() == OPTION_IDS
    assert [key for key, row in options.items() if row["selected"]] == ["HARD_BLOCK_UNTIL_MACHINE_COMPLETE"]
    assert options["CONTROLLED_OFFICIAL_EXPORT_INGESTION"]["current_readiness"] == "NOT_READY"
    assert options["POSITIVE_ONLY_GATE3_POLICY_AMENDMENT"]["current_readiness"] == "NOT_APPROVED"
    assert options["BROWSER_AUTOMATION"]["current_readiness"] == "UNPROVEN"
    for row in options.values():
        assert all(row[k] for k in ("source_authority", "truthfulness", "pit", "pilot_usability",
            "automation", "security_risk", "complexity", "policy_burden", "future_migration"))
    assert value["operating_burden"]["fixed_interval"] is None
    assert value["operating_burden"]["pre_market_file_valid_all_day"] is False
    assert all(v is False for k, v in value["runtime"].items() if k != "source_network_requests")
    assert value["runtime"]["source_network_requests"] == 0
    assert value["boundaries"] == {
        "V1_ACTIVE": True, "GATE_POLICY_V2_ACTIVE": False, "SIX_GATES_EXACTLY_SIX": True,
        "NO_FABRICATED_SURVEILLANCE_CLEARANCE": True, "NO_HUMAN_GATE_OVERRIDE": True,
        "NO_FUTURE_LEAKAGE": True, "NO_RETROACTIVE_SURVEILLANCE_STATE": True,
        "PILOT_SIMPLICITY_RULE": "ACTIVE", "AI_DECISION_AUTHORITY": False,
    }


def test_decision_binds_accepted_evidence_and_unchanged_engine_collector_policy():
    value = _read()
    _verify(value)
    assert value["baseline_commit"] == "cf4bd84aea7fffd6e4d4b4fbbe2cc9375ed4c8a1"
    assert value["authority"]["directive_id"] == "b93618da-ad13-47bf-ac48-5bcfaf2389a7"
    assert value["authority"]["human_signature_claimed"] is False
    for name, fingerprint in value["reviewed_files_lf"].items():
        assert "sha256:" + sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest() == fingerprint
    prior = _read(ROOT / "docs/architecture/GATE3_ASM_GSM_OFFICIAL_COMPLETE_EXPORT_IDENTITY_FEASIBILITY_DECISION_V1.json")
    assert prior["result"] == "CURRENT_OFFICIAL_PATH_CANNOT_PROVE_COMPLETE_CAPTURE"
    assert all(row["api_to_complete_export_relationship"] == "UNPROVEN" for row in prior["families"])


def test_matrix_decision_is_independent_of_option_order_and_receipt_is_reproducible():
    value = _read()
    assert canonical_json(json.loads(canonical_json(value))) == canonical_json(value)
    for order in permutations(value["options"]):
        changed = deepcopy(value)
        changed["options"] = list(order)
        changed["fingerprint"] = _digest(changed)
        _verify(changed)
    # Serialization preserves recorded order; changing it changes the receipt,
    # but cannot change which documented alternative is justified/selected.
    for key in value.keys() - {"fingerprint"}:
        changed = deepcopy(value)
        changed[key] = None
        assert _digest(changed) != value["fingerprint"]


def test_threat_model_keeps_residual_risk_and_no_cryptographic_source_claim():
    threats = {row["id"]: row for row in _read()["threat_model"]}
    assert len(threats) == len(_read()["threat_model"]) == 7
    assert threats["PRE_UPLOAD_EDIT"]["residual"] == "VALID_PRE_UPLOAD_EDIT_CAN_RECEIVE_VALID_HASH"
    assert threats["POST_RETENTION_EDIT"]["residual"] == "PRIVILEGED_COORDINATED_REWRITE_NOT_PREVENTED_BY_HASH"
    assert threats["FALSE_SOURCE_DECLARATION"]["residual"] == "ATTESTATION_IS_NOT_NSE_SIGNATURE"
    assert threats["HIDDEN_OMISSION"]["residual"] == "SCHEMA_HASH_COUNTS_CANNOT_PROVE_UNDECLARED_OMISSIONS"
    assert {"WRONG_FILE", "STALE_FILE", "MALICIOUS_UPLOAD"} <= threats.keys()
    assert all(row["mitigations"] and row["residual"] for row in threats.values())


@pytest.mark.parametrize("section,key,unsafe", [
    ("current_evidence", "gsm_complete_component_manifest_proven", True),
    ("current_evidence", "execution_master_continuity", "CLOSED"),
    ("frozen_policy", "blocking_plus_missing", "FAIL"),
    ("frozen_policy", "all_three_components_required", False),
    ("controlled_transport", "completeness_by_attestation", True),
    ("controlled_transport", "hash_authenticates_nse", True),
    ("controlled_transport", "operator_set_gate_result", True),
    ("controlled_transport", "row_count_only_proof", True),
    ("controlled_transport", "hidden_omissions_detectable_from_plain_schema", True),
    ("controlled_transport", "controls_required", sorted(CONTROLS - {"MFA"})),
    ("first_observed", "source", "OPERATOR_DOWNLOAD_TIME"),
    ("first_observed", "later_validation_requires_own_known_at", False),
    ("first_observed", "reupload_renews_effective_age", True),
    ("api_role", "api_positive_missing_in_artifact", ["UNKNOWN", "PASS"]),
    ("api_role", "raw_positive_is_gate_veto", True),
    ("api_role", "latest_timestamp_wins", True),
    ("operating_burden", "fixed_interval", "DAILY"),
    ("boundaries", "GATE_POLICY_V2_ACTIVE", True),
])
def test_rehash_cannot_authorize_unsafe_transport_time_or_policy_semantics(section, key, unsafe):
    value = _read()
    value[section][key] = unsafe
    value["fingerprint"] = _digest(value)
    with pytest.raises(AssertionError):
        _verify(value)


@pytest.mark.parametrize("failure", sorted(CONFLICTS | UNKNOWN))
def test_no_failed_artifact_threat_case_can_be_rehashed_into_gate_pass(failure):
    value = _read()
    next(row for row in value["failure_cases"] if row["id"] == failure)["gate"] = "PASS"
    value["fingerprint"] = _digest(value)
    with pytest.raises(AssertionError):
        _verify(value)


def test_operator_or_browser_readiness_cannot_be_selected_by_declaration():
    for option in OPTION_IDS - {"HARD_BLOCK_UNTIL_MACHINE_COMPLETE"}:
        value = _read()
        for row in value["options"]:
            row["selected"] = row["id"] == option
        value["fingerprint"] = _digest(value)
        with pytest.raises(AssertionError):
            _verify(value)
    with pytest.raises(ValueError, match="DUPLICATE_GOVERNANCE_KEY"):
        json.loads('{"decision":"C","decision":"A"}', object_pairs_hook=_unique_object)
