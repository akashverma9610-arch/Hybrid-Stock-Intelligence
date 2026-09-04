from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone
import gzip

import pytest

import app.intelligence.pit_company_type_classification as contract
from app.historical.nse_mii_security_master import (
    NseMiiSecurityMasterHttpResponse,
    extract_nse_mii_security_master,
    nse_mii_security_master_url,
)
from app.historical.nse_session_identity import (
    activate_nse_session_identity_policy,
    approve_nse_session_identity_policy,
    session_point_identity_from_row,
)


T = datetime(2026, 9, 4, 10, tzinfo=UTC)
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


def _session(day: date = date(2026, 8, 31)):
    extracted = extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        day, nse_mii_security_master_url(day), "application/x-gzip",
        gzip.compress((HEADERS + "100,EXACT,EQ,Exact Ltd,INE000A01001,6,100,0,EQ,EQUITY\n").encode()), T,
    ))
    approval = approve_nse_session_identity_policy(
        approval_id="session-policy-approval", approved_by="human:approved", approved_at=T,
    )
    activation = activate_nse_session_identity_policy(
        selection_id="session-policy-activation", approval=approval, activated_by="human:approved", activated_at=T,
    )
    return session_point_identity_from_row(activation=activation, snapshot=extracted.snapshot, row=extracted.rows[0])


def _bridge(session, *, issuer: str = "issuer:exact-ltd"):
    return contract.create_exact_issuer_security_bridge(
        bridge_id="bridge:exact-ltd", issuer_legal_entity_id=issuer,
        issuer_identity_fingerprint="sha256:" + "1" * 64,
        session_security_receipt_id=session.receipt_id,
        session_security_fingerprint=session.fingerprint,
        bridge_kind=contract.PitCompanyTypeBridgeKind.OFFICIAL_ISIN,
        exact_key_reference="isin:INE000A01001",
    )


def _evidence(
    session, *, branch=contract.PitCompanyTypeBranch.BANK,
    family=contract.PitCompanyTypeSourceFamily.RBI_SCHEDULED_COMMERCIAL_BANK,
    category=contract.PitCompanyTypeEvidenceCategory.RBI_BANK,
    as_of: date | None = None, semantics=contract.PitCompanyTypeTemporalSemantics.EXACT_SNAPSHOT_DATE,
    issuer="issuer:exact-ltd", evidence_id="evidence:one", subtype="PRIVATE_SECTOR_BANK", taxonomy_code=None,
    effective_from=None, effective_to=None,
):
    return contract.create_pit_company_type_evidence(
        evidence_id=evidence_id, source_family=family, source_category=category,
        source_snapshot_id="source:snapshot-one", source_fingerprint="sha256:" + "2" * 64,
        issuer_legal_entity_id=issuer, issuer_identity_fingerprint="sha256:" + "1" * 64,
        source_as_of_date=as_of or session.session_date, known_at=T if (as_of or session.session_date) >= T.date() else None,
        effective_from=effective_from, effective_to=effective_to, temporal_semantics=semantics,
        proposed_branch=branch, source_subtype_code=subtype, taxonomy_code=taxonomy_code,
    )


def test_policy_is_unapproved_inactive_research_only_and_deterministic():
    first = contract.create_proposed_pit_company_type_policy()
    second = contract.create_proposed_pit_company_type_policy()
    assert first == second
    assert first.status == (
        contract.PitCompanyTypePolicyStatus.PROPOSED,
        contract.PitCompanyTypePolicyStatus.NOT_APPROVED,
        contract.PitCompanyTypePolicyStatus.NOT_ACTIVE,
        contract.PitCompanyTypePolicyStatus.RESEARCH_ONLY,
        contract.PitCompanyTypePolicyStatus.NON_EXECUTABLE,
    )


@pytest.mark.parametrize(
    ("branch", "family", "category", "subtype"),
    (
        (contract.PitCompanyTypeBranch.BANK, contract.PitCompanyTypeSourceFamily.RBI_SCHEDULED_COMMERCIAL_BANK, contract.PitCompanyTypeEvidenceCategory.RBI_BANK, "SMALL_FINANCE_BANK"),
        (contract.PitCompanyTypeBranch.NBFC, contract.PitCompanyTypeSourceFamily.RBI_REGISTERED_NBFC_OR_ARC, contract.PitCompanyTypeEvidenceCategory.RBI_NBFC, "NBFC_INVESTMENT_CREDIT_COMPANY"),
        (contract.PitCompanyTypeBranch.INSURER, contract.PitCompanyTypeSourceFamily.IRDAI_REGISTERED_INSURER, contract.PitCompanyTypeEvidenceCategory.IRDAI_LIFE_INSURER, "LIFE"),
    ),
)
def test_exact_primary_regulator_evidence_preserves_supported_branch_and_subtype(branch, family, category, subtype):
    session = _session()
    evidence = _evidence(session, branch=branch, family=family, category=category, subtype=subtype)
    result = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(evidence,))
    assert result.state is contract.PitCompanyTypeReceiptState.EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE
    assert result.branch is branch and result.evidence[0].source_subtype_code == subtype
    assert (result.actionability, result.execution_status) == ("WATCH_ONLY", "NON_EXECUTABLE")


def test_non_financial_requires_positive_exact_nse_taxonomy_code_not_absence_from_regulator_lists():
    session = _session()
    absent = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=())
    assert absent.state is contract.PitCompanyTypeReceiptState.DATA_EVIDENCE_UNAVAILABLE
    assert absent.branch is contract.PitCompanyTypeBranch.UNKNOWN
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="PRIMARY_EVIDENCE_INVALID"):
        _evidence(
            session, branch=contract.PitCompanyTypeBranch.NON_FINANCIAL,
            family=contract.PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION,
            category=contract.PitCompanyTypeEvidenceCategory.NSE_NON_FINANCIAL_TAXONOMY_CODE,
            subtype=None, taxonomy_code=None,
        )
    taxonomy = _evidence(
        session, branch=contract.PitCompanyTypeBranch.NON_FINANCIAL,
        family=contract.PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION,
        category=contract.PitCompanyTypeEvidenceCategory.NSE_NON_FINANCIAL_TAXONOMY_CODE,
        subtype=None, taxonomy_code="IN0302", evidence_id="evidence:nse-taxonomy",
    )
    result = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(taxonomy,))
    assert result.branch is contract.PitCompanyTypeBranch.NON_FINANCIAL
    assert result.state is contract.PitCompanyTypeReceiptState.EXACT_CLASSIFICATION_EVIDENCE_AVAILABLE


def test_arc_and_other_unsupported_financial_evidence_remain_fail_closed():
    session = _session()
    arc = _evidence(
        session, branch=contract.PitCompanyTypeBranch.FINANCIAL_TYPE_UNSUPPORTED,
        family=contract.PitCompanyTypeSourceFamily.RBI_REGISTERED_NBFC_OR_ARC,
        category=contract.PitCompanyTypeEvidenceCategory.RBI_ARC, subtype="ARC",
    )
    result = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(arc,))
    assert result.state is contract.PitCompanyTypeReceiptState.FINANCIAL_TYPE_UNSUPPORTED
    assert result.reasons == (contract.PitCompanyTypeReason.UNSUPPORTED_FINANCIAL_ENTITY,)


def test_exact_bridge_is_required_and_fuzzy_parent_subsidiary_inference_is_not_a_bridge():
    session = _session()
    evidence = _evidence(session)
    no_bridge = contract.assess_proposed_pit_company_type(session, bridge=None, evidence=())
    assert no_bridge.state is contract.PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE
    wrong_security = contract.create_exact_issuer_security_bridge(
        bridge_id="bridge:parent", issuer_legal_entity_id="issuer:parent",
        issuer_identity_fingerprint="sha256:" + "3" * 64,
        session_security_receipt_id="nse-session-identity:not-this-security",
        session_security_fingerprint="sha256:" + "4" * 64,
        bridge_kind=contract.PitCompanyTypeBridgeKind.CANONICAL_ISSUER_ID,
        exact_key_reference="issuer:parent",
    )
    assert contract.assess_proposed_pit_company_type(session, bridge=wrong_security, evidence=()).state is contract.PitCompanyTypeReceiptState.IDENTITY_LINKAGE_UNAVAILABLE
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="EXACT_BRIDGE_INVALID"):
        contract.create_exact_issuer_security_bridge(
            bridge_id="bridge:fuzzy", issuer_legal_entity_id="issuer:exact-ltd",
            issuer_identity_fingerprint="sha256:" + "1" * 64,
            session_security_receipt_id=session.receipt_id, session_security_fingerprint=session.fingerprint,
            bridge_kind="NAME", exact_key_reference="Exact Ltd",
        )
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="EVIDENCE_ENTITY_MISMATCH"):
        contract.assess_proposed_pit_company_type(session, bridge=_bridge(session, issuer="issuer:parent"), evidence=(evidence,))


def test_future_or_not_effective_evidence_is_excluded_without_backfilling_current_registry():
    session = _session(date(2024, 2, 5))
    future = _evidence(session, as_of=date(2026, 8, 27))
    result = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(future,))
    assert result.state is contract.PitCompanyTypeReceiptState.PIT_DATE_UNSUPPORTED
    assert result.reasons == (contract.PitCompanyTypeReason.FUTURE_EVIDENCE_EXCLUDED,)
    expired = _evidence(
        _session(), semantics=contract.PitCompanyTypeTemporalSemantics.EXPLICIT_EFFECTIVE_INTERVAL,
        as_of=date(2026, 8, 1), effective_from=date(2026, 8, 1), effective_to=date(2026, 8, 30),
    )
    result = contract.assess_proposed_pit_company_type(_session(), bridge=_bridge(_session()), evidence=(expired,))
    assert result.state is contract.PitCompanyTypeReceiptState.PIT_DATE_UNSUPPORTED
    assert result.reasons == (contract.PitCompanyTypeReason.SOURCE_EVIDENCE_NOT_EFFECTIVE,)


def test_conflicting_exact_primary_evidence_is_retained_as_a_conflict_not_silently_prioritized():
    session = _session()
    bank = _evidence(session, evidence_id="evidence:bank")
    taxonomy = _evidence(
        session, branch=contract.PitCompanyTypeBranch.NON_FINANCIAL,
        family=contract.PitCompanyTypeSourceFamily.NSE_INDICES_INDUSTRY_CLASSIFICATION,
        category=contract.PitCompanyTypeEvidenceCategory.NSE_NON_FINANCIAL_TAXONOMY_CODE,
        subtype=None, taxonomy_code="IN0302", evidence_id="evidence:nse-taxonomy",
    )
    result = contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(taxonomy, bank))
    assert result.state is contract.PitCompanyTypeReceiptState.EVIDENCE_CONFLICTED
    assert tuple(item.evidence_id for item in result.evidence) == ("evidence:bank", "evidence:nse-taxonomy")


def test_duplicate_or_tampered_lineage_is_rejected_and_serialization_is_stable():
    session = _session()
    bridge = _bridge(session)
    evidence = _evidence(session)
    result = contract.assess_proposed_pit_company_type(session, bridge=bridge, evidence=(evidence,))
    assert contract.serialize_pit_company_type_receipt(result) == contract.serialize_pit_company_type_receipt(result)
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="EVIDENCE_ID_DUPLICATE"):
        contract.assess_proposed_pit_company_type(session, bridge=bridge, evidence=(evidence, evidence))
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="RECEIPT_BRIDGE_PARTIAL"):
        replace(result, bridge_id=None)
    object.__setattr__(evidence, "source_subtype_code", "TAMPERED")
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="EVIDENCE_FINGERPRINT_MISMATCH"):
        contract.assess_proposed_pit_company_type(session, bridge=bridge, evidence=(evidence,))
    session = _session()
    object.__setattr__(session, "symbol", "TAMPERED")
    with pytest.raises(contract.PitCompanyTypeClassificationError, match="SESSION_SECURITY_INVALID"):
        contract.assess_proposed_pit_company_type(session, bridge=None)


def test_equivalent_timezone_aware_known_times_normalize_to_one_evidence_fingerprint():
    session = _session()
    first = contract.create_pit_company_type_evidence(
        evidence_id="evidence:time", source_family=contract.PitCompanyTypeSourceFamily.RBI_SCHEDULED_COMMERCIAL_BANK,
        source_category=contract.PitCompanyTypeEvidenceCategory.RBI_BANK,
        source_snapshot_id="source:time", source_fingerprint="sha256:" + "5" * 64,
        issuer_legal_entity_id="issuer:exact-ltd", issuer_identity_fingerprint="sha256:" + "1" * 64,
        source_as_of_date=date(2026, 8, 30), known_at=datetime(2026, 8, 30, 18, 30, tzinfo=UTC),
        effective_from=None, effective_to=None, temporal_semantics=contract.PitCompanyTypeTemporalSemantics.FIRST_OBSERVED_FROM_SOURCE_DATE,
        proposed_branch=contract.PitCompanyTypeBranch.BANK, source_subtype_code="PRIVATE_SECTOR_BANK",
    )
    second = contract.create_pit_company_type_evidence(
        evidence_id="evidence:time", source_family=contract.PitCompanyTypeSourceFamily.RBI_SCHEDULED_COMMERCIAL_BANK,
        source_category=contract.PitCompanyTypeEvidenceCategory.RBI_BANK,
        source_snapshot_id="source:time", source_fingerprint="sha256:" + "5" * 64,
        issuer_legal_entity_id="issuer:exact-ltd", issuer_identity_fingerprint="sha256:" + "1" * 64,
        source_as_of_date=date(2026, 8, 30), known_at=datetime(2026, 8, 31, 0, tzinfo=timezone(timedelta(hours=5, minutes=30))),
        effective_from=None, effective_to=None, temporal_semantics=contract.PitCompanyTypeTemporalSemantics.FIRST_OBSERVED_FROM_SOURCE_DATE,
        proposed_branch=contract.PitCompanyTypeBranch.BANK, source_subtype_code="PRIVATE_SECTOR_BANK",
    )
    assert first.fingerprint == second.fingerprint
    assert contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(first,)).fingerprint == contract.assess_proposed_pit_company_type(session, bridge=_bridge(session), evidence=(second,)).fingerprint


def test_static_boundaries_exclude_company_metrics_backtests_portfolio_execution_and_storage():
    source = open(contract.__file__, encoding="utf-8").read()
    for forbidden in (
        "sqlite3", "app.storage", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime",
        "Compounder", "threshold", "CAGR", "place_order", "datetime.now", "app.signals",
    ):
        assert forbidden not in source
