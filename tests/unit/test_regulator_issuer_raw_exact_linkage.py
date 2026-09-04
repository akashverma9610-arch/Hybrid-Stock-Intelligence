from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.historical.regulator_issuer_raw_exact_linkage as linkage
from app.historical.issuer_identifier_acquisition import IssuerIdentifierEvidenceSource
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.regulator_company_type_evidence import RegulatorEvidenceSource
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


T = datetime(2026, 9, 5, 10, tzinfo=UTC)
CIN = "L65190GJ1994PLC021012"


def _inputs(*, issuer_name: str = "ICICI Bank Limited", regulator_name: str = "ICICI Bank Limited", cin: str = CIN,
            regulator_source: RegulatorEvidenceSource = RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS,
            issuer_known: datetime = T - timedelta(days=2), regulator_known: datetime = T - timedelta(days=1),
            regulator_id: str = "regulator:one"):
    anchor = SimpleNamespace(bridge_id="anchor:one", brsr_evidence_id="issuer:one", issuer_known_at=issuer_known)
    forward = SimpleNamespace(later_session_date=date(2026, 8, 31), anchor_known_ats=(issuer_known,), anchor_bridge_ids=("anchor:one",), cin=cin, observation_id="forward:one")
    issuer = SimpleNamespace(evidence_id="issuer:one", source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=cin, issuer_legal_name=issuer_name, historical_known_at=issuer_known, fingerprint="sha256:" + "1" * 64)
    regulator = SimpleNamespace(evidence_id=regulator_id, source=regulator_source, legal_name=regulator_name, regulator_subtype="Domestic Private Sector Banks", observed_at=regulator_known, fingerprint="sha256:" + "2" * 64)
    return (forward,), (anchor,), (issuer,), (regulator,)


def _audit(**kwargs):
    forwards, anchors, issuers, regulators = _inputs(**kwargs)
    return linkage.audit_raw_exact_linkage(forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=regulators, as_of=T), forwards, anchors, issuers, regulators


def test_policy_identity_is_fixed_to_approved_raw_exact_semantics():
    policy = linkage.create_raw_exact_linkage_policy()
    assert (policy.policy_id, policy.policy_version) == (linkage.POLICY_ID, "v1")
    assert linkage.RawExactLinkageSemantic.NO_REPRESENTATION_EXACT in policy.semantics


def test_human_approval_and_active_selection_are_immutable():
    approval = linkage.approve_raw_exact_linkage_policy(approval_id="human:raw-approval", approved_by="human:explicit-user-approval", approved_at=T)
    activation = linkage.activate_raw_exact_linkage_policy(selection_id="human:raw-selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T)
    assert activation.approval_id == approval.approval_id and activation.state is linkage.RawExactLinkageActivationState.ACTIVE
    with pytest.raises(linkage.RegulatorIssuerRawExactLinkageError, match="PRECEDES_APPROVAL"):
        linkage.activate_raw_exact_linkage_policy(selection_id="early", approval=approval, activated_by="human:explicit-user-approval", activated_at=T - timedelta(seconds=1))


def test_raw_exact_nfc_and_trim_creates_identity_valid_candidate():
    audit, forwards, anchors, issuers, regulators = _audit(issuer_name="  ICICI Bank Limited  ")
    assert audit.identity_candidates == 1 and audit.evaluations[0].status is linkage.RawExactLinkageStatus.IDENTITY_VALID
    approval = linkage.approve_raw_exact_linkage_policy(approval_id="human:raw-approval", approved_by="human:explicit-user-approval", approved_at=T)
    activation = linkage.activate_raw_exact_linkage_policy(selection_id="human:raw-selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T)
    link = linkage.activate_raw_exact_links(activation=activation, audit=audit, forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=regulators)[0]
    assert link.canonical_legal_name == "  ICICI Bank Limited  " and link.regulator_legal_name == "ICICI Bank Limited"


@pytest.mark.parametrize("name", ["ICICI BANK LIMITED", "ICICI Bank Ltd", "ICICI Bank Limited."])
def test_case_suffix_and_punctuation_differences_are_rejected(name):
    audit, *_ = _audit(regulator_name=name)
    assert audit.identity_candidates == 0 and not audit.evaluations


def test_one_name_to_multiple_cins_fails_closed():
    audit, forwards, anchors, issuers, regulators = _audit()
    second_anchor = SimpleNamespace(bridge_id="anchor:two", brsr_evidence_id="issuer:two", issuer_known_at=issuers[0].historical_known_at)
    second_forward = SimpleNamespace(**{**forwards[0].__dict__, "cin": "L65190GJ1994PLC021013", "anchor_bridge_ids": ("anchor:two",), "observation_id": "forward:two"})
    second_issuer = SimpleNamespace(**{**issuers[0].__dict__, "evidence_id": "issuer:two", "issuer_identifier_value": "L65190GJ1994PLC021013", "fingerprint": "sha256:" + "3" * 64})
    result = linkage.audit_raw_exact_linkage(forwards=(forwards[0], second_forward), anchors=(anchors[0], second_anchor), issuer_evidence=(issuers[0], second_issuer), regulator_evidence=regulators, as_of=T)
    assert result.evaluations[0].status is linkage.RawExactLinkageStatus.EVIDENCE_CONFLICTED


def test_one_cin_to_multiple_names_fails_closed():
    audit, forwards, anchors, issuers, regulators = _audit()
    second_anchor = SimpleNamespace(bridge_id="anchor:two", brsr_evidence_id="issuer:two", issuer_known_at=issuers[0].historical_known_at)
    second_forward = SimpleNamespace(**{**forwards[0].__dict__, "anchor_bridge_ids": ("anchor:two",), "observation_id": "forward:two"})
    second_issuer = SimpleNamespace(**{**issuers[0].__dict__, "evidence_id": "issuer:two", "issuer_legal_name": "Other Bank Limited", "fingerprint": "sha256:" + "3" * 64})
    result = linkage.audit_raw_exact_linkage(forwards=(forwards[0], second_forward), anchors=(anchors[0], second_anchor), issuer_evidence=(issuers[0], second_issuer), regulator_evidence=regulators, as_of=T)
    assert result.evaluations[0].status is linkage.RawExactLinkageStatus.EVIDENCE_CONFLICTED


def test_duplicate_regulator_name_fails_closed():
    audit, forwards, anchors, issuers, regulators = _audit()
    duplicate = SimpleNamespace(**{**regulators[0].__dict__, "evidence_id": "regulator:two", "fingerprint": "sha256:" + "4" * 64})
    result = linkage.audit_raw_exact_linkage(forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=(regulators[0], duplicate), as_of=T)
    assert all(item.status is linkage.RawExactLinkageStatus.EVIDENCE_CONFLICTED for item in result.evaluations)


def test_cross_regulator_family_collision_fails_closed():
    audit, forwards, anchors, issuers, regulators = _audit()
    insurer = SimpleNamespace(**{**regulators[0].__dict__, "evidence_id": "regulator:life", "source": RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, "fingerprint": "sha256:" + "5" * 64})
    result = linkage.audit_raw_exact_linkage(forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=(regulators[0], insurer), as_of=T)
    assert all(item.reasons == (linkage.RawExactLinkageReason.CROSS_REGULATOR_FAMILY_CONFLICT,) for item in result.evaluations)


def test_future_regulator_evidence_is_not_historically_valid():
    audit, *_ = _audit(regulator_known=T + timedelta(seconds=1))
    assert audit.evaluations[0].status is linkage.RawExactLinkageStatus.PIT_EVIDENCE_TOO_LATE
    assert audit.evaluations[0].reasons == (linkage.RawExactLinkageReason.REGULATOR_EVIDENCE_AFTER_AS_OF,)
    assert audit.identity_candidates == 1 and audit.active_links == 0


def test_link_known_at_is_the_later_exact_evidence_timestamp():
    audit, forwards, anchors, issuers, regulators = _audit()
    approval = linkage.approve_raw_exact_linkage_policy(approval_id="human:approval", approved_by="human:explicit-user-approval", approved_at=T)
    activation = linkage.activate_raw_exact_linkage_policy(selection_id="human:selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T)
    link = linkage.activate_raw_exact_links(activation=activation, audit=audit, forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=regulators)[0]
    assert link.link_known_at == T - timedelta(days=1) and link.canonical_legal_name == link.regulator_legal_name


def test_tampered_audit_cannot_create_a_link():
    audit, forwards, anchors, issuers, regulators = _audit()
    approval = linkage.approve_raw_exact_linkage_policy(approval_id="human:approval", approved_by="human:explicit-user-approval", approved_at=T)
    activation = linkage.activate_raw_exact_linkage_policy(selection_id="human:selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T)
    tampered = replace(audit, active_issuer_cins=999, fingerprint=linkage._hash(linkage._audit_payload_values(audit.as_of, 999, audit.identity_candidates, audit.active_links, audit.evaluations)))
    with pytest.raises(linkage.RegulatorIssuerRawExactLinkageError, match="AUDIT_LINEAGE_UNAVAILABLE"):
        linkage.activate_raw_exact_links(activation=activation, audit=tampered, forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=regulators)


def test_generic_icici_name_path_is_not_hardcoded():
    audit, *_ = _audit()
    assert audit.evaluations[0].cin == CIN
    source = Path(linkage.__file__).read_text(encoding="utf-8")
    assert "ICICIBANK" not in source and "ICICI Bank" not in source


def test_irdai_zero_match_stays_zero_without_broadening_normalization():
    audit, *_ = _audit(regulator_source=RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, regulator_name="Different Insurer")
    assert not audit.evaluations and audit.identity_candidates == 0


def test_nbfc_arc_absence_creates_no_link_or_non_financial_inference():
    audit, forwards, anchors, issuers, _ = _audit()
    result = linkage.audit_raw_exact_linkage(forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=(), as_of=T)
    assert not result.evaluations and result.active_links == 0


def test_deterministic_fingerprint_and_input_order():
    first, forwards, anchors, issuers, regulators = _audit()
    second = linkage.audit_raw_exact_linkage(forwards=tuple(reversed(forwards)), anchors=tuple(reversed(anchors)), issuer_evidence=tuple(reversed(issuers)), regulator_evidence=tuple(reversed(regulators)), as_of=T)
    assert first == second


def test_persistence_replay_is_insert_only_and_idempotent(tmp_path):
    audit, forwards, anchors, issuers, regulators = _audit()
    approval = linkage.approve_raw_exact_linkage_policy(approval_id="human:approval", approved_by="human:explicit-user-approval", approved_at=T)
    activation = linkage.activate_raw_exact_linkage_policy(selection_id="human:selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T)
    policy = linkage.create_raw_exact_linkage_policy(); links = linkage.activate_raw_exact_links(activation=activation, audit=audit, forwards=forwards, anchors=anchors, issuer_evidence=issuers, regulator_evidence=regulators)
    path = tmp_path / "linkage.sqlite"; repository = SQLiteCoreApiSnapshotRepository(path); store = linkage.RawExactLinkageStore(repository)
    assert linkage.persist_raw_exact_linkage(store=store, policy=policy, approval=approval, activation=activation, links=links) == (4, 0)
    repository.close()
    restarted = linkage.RawExactLinkageStore(SQLiteCoreApiSnapshotRepository(path))
    assert linkage.persist_raw_exact_linkage(store=restarted, policy=policy, approval=approval, activation=activation, links=links) == (0, 4)


def test_link_is_not_a_company_type_or_execution_contract():
    source = Path(linkage.__file__).read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    forbidden = ("app.intelligence", "portfolio", "broker", "order", "backtest", "discovery")
    assert not any(any(value in item for value in forbidden) for item in imports)
    assert "NON_FINANCIAL" not in source and "REPRESENTATION_EXACT" not in source.replace("NO_REPRESENTATION_EXACT", "")


def test_no_runtime_clock_or_name_fuzzy_library_is_used():
    source = Path(linkage.__file__).read_text(encoding="utf-8")
    assert "datetime.now" not in source and "difflib" not in source and "casefold" not in source and "edit_distance" not in source
