from __future__ import annotations

import ast
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest

import app.historical.brsr_issuer_anchor_backfill as anchor_source
import app.historical.isin_issuer_bridge_continuity as continuity
import app.historical.nse_taxonomy_company_type_map_activation as taxonomy_activation
import app.historical.pit_company_type_classification_activation as company_type
import app.historical.regulator_company_type_evidence as regulator_source
import app.historical.regulator_issuer_raw_exact_linkage as raw_linkage
from app.historical.issuer_identifier_acquisition import (
    IssuerIdentifierEvidenceSource,
    evidence_from_structured_row,
)
from app.historical.issuer_security_identity import IssuerIdentifierType
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
from app.intelligence import nse_taxonomy_company_type_map_proposal as taxonomy_proposal
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification


T = datetime(2026, 9, 5, 12, tzinfo=UTC)
AS_OF = datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
EARLY = datetime(2024, 2, 5, 23, 59, 59, tzinfo=UTC)
ANCHOR_DAY = date(2024, 6, 20)
SOURCE_SHA = "a" * 64
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"
BRSR_SOURCE = "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip"


class Calendar:
    def is_trading_day(self, value: date) -> bool:
        return value == ANCHOR_DAY


def _row(symbol: str, isin: str, code: str) -> str:
    return f"{code},{symbol},EQ,Exact Ltd,{isin},6,100,0,EQ,EQUITY"


def _mii(*, symbol: str, isin: str, code: str, day: date):
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=day, source_reference=nse_mii_security_master_url(day), content_type="application/x-gzip",
        body=gzip.compress((HEADERS + _row(symbol, isin, code) + "\n").encode()), document_observed_at=T,
    ))


def _forward(*, symbol: str = "APARINDS", isin: str = "INE372A01015", cin: str = "L14292GJ2006PLC049371", code: str = "100"):
    issuer = evidence_from_structured_row(
        source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, source_document=("brsr-" + code).encode(),
        source_reference=BRSR_SOURCE, source_record_id="nse-brsr-application:" + code,
        source_as_of_date=ANCHOR_DAY, source_observed_at=T,
        historical_known_at=datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC), isin=None, nse_symbol=symbol,
        issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=cin, issuer_legal_name="Exact Legal Entity",
    )
    anchor = anchor_source.assess_brsr_issuer_anchor(
        issuer, extraction=_mii(symbol=symbol, isin=isin, code=code, day=ANCHOR_DAY), calendar=Calendar(),
    ).anchor
    assert anchor is not None
    approval = continuity.approve_isin_issuer_bridge_continuity_policy(
        approval_id="issuer-approval-" + code, approved_by="human:fixture", approved_at=T,
    )
    activation = continuity.activate_isin_issuer_bridge_continuity_policy(
        selection_id="issuer-selection-" + code, approval=approval, activated_by="human:fixture", activated_at=T,
    )
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(anchor,)).bridges[0]
    session_approval = approve_nse_session_identity_policy(
        approval_id="session-approval-" + code, approved_by="human:fixture", approved_at=T,
    )
    session_activation = activate_nse_session_identity_policy(
        selection_id="session-selection-" + code, approval=session_approval, activated_by="human:fixture", activated_at=T,
    )
    later = session_point_identity_from_row(
        activation=session_activation, snapshot=_mii(symbol=symbol, isin=isin, code=code, day=AS_OF.date()).snapshot,
        row=_mii(symbol=symbol, isin=isin, code=code, day=AS_OF.date()).rows[0],
    )
    return continuity.activate_forward_issuer_observations(
        activation=activation, anchor_bridges=(bridge,), later_session_receipts=(later,),
    ).observations[0]


def _taxonomy(*, isin: str, macro: str, sector: str) -> InstrumentTaxonomyClassification:
    effective = AS_OF - timedelta(days=4)
    return InstrumentTaxonomyClassification(
        classification_id="nse-indices-taxonomy:" + isin, instrument_id="NSE:" + isin, industry=None,
        sector="Ignored", super_sector="Ignored", source=taxonomy_proposal.NSE_TAXONOMY_SOURCE,
        source_type=ClassificationSourceStatus.OFFICIAL, effective_from=effective, effective_to=None, as_of=effective,
        confidence=1.0, classification_version=taxonomy_proposal.NSE_TAXONOMY_VERSION, source_reference="fixture",
        macro_economic_sector_code=macro, sector_code=sector, raw_classification_label="Ignored",
        resolution_status="EXACT_UNIQUE", source_sha256=SOURCE_SHA, fetched_at_utc=effective,
        effective_observation_semantics=taxonomy_proposal.NSE_TAXONOMY_SEMANTICS,
    )


def _taxonomy_governance():
    approval = taxonomy_activation.approve_nse_taxonomy_category_map_policy(
        approval_id="taxonomy-human-approval", approved_by="human:fixture", approved_at=T,
    )
    return taxonomy_activation.activate_nse_taxonomy_category_map_policy(
        selection_id="taxonomy-selection", approval=approval, activated_by="human:fixture", activated_at=T,
    )


def _taxonomy_receipt(forward, *, macro: str, sector: str):
    return taxonomy_activation.activate_nse_taxonomy_category_evidence(
        activation=_taxonomy_governance(), classifications=(_taxonomy(isin=forward.isin, macro=macro, sector=sector),),
        issuer_observations=(forward,), as_of=AS_OF,
    ).receipts[0]


def _regulator(*, source, kind, cin: str, name: str = "Exact Legal Entity"):
    artifact = regulator_source.source_artifact_from_payload(
        source=source, source_reference="https://official.example/regulator", payload=b"official",
        content_type="text/html", observed_at=AS_OF - timedelta(days=1), source_as_of_date=AS_OF.date(), schema=("CIN", "Name"),
    )
    return regulator_source._entity(  # exercised public immutable evidence construction in its own module.
        artifact=artifact, source_record_id="row:" + kind.value, entity_kind=kind,
        entity_status=regulator_source.RegulatorEntityStatus.LISTED, legal_name=name, cin=cin,
    )


def _raw_link(forward, evidence):
    issuer_known = AS_OF - timedelta(days=2)
    raw_forward = SimpleNamespace(
        later_session_date=AS_OF.date(), anchor_known_ats=(issuer_known,), anchor_bridge_ids=("anchor:one",),
        cin=forward.cin, observation_id="raw-forward:" + forward.cin,
    )
    anchor = SimpleNamespace(bridge_id="anchor:one", brsr_evidence_id="issuer:one", issuer_known_at=issuer_known)
    issuer = SimpleNamespace(
        evidence_id="issuer:one", source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE,
        issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=forward.cin,
        issuer_legal_name="Exact Legal Entity", historical_known_at=issuer_known, fingerprint="sha256:" + "1" * 64,
    )
    approval = raw_linkage.approve_raw_exact_linkage_policy(
        approval_id="raw-link-approval:" + forward.cin, approved_by="human:fixture", approved_at=T,
    )
    activation = raw_linkage.activate_raw_exact_linkage_policy(
        selection_id="raw-link-selection:" + forward.cin, approval=approval, activated_by="human:fixture", activated_at=T,
    )
    audit = raw_linkage.audit_raw_exact_linkage(
        forwards=(raw_forward,), anchors=(anchor,), issuer_evidence=(issuer,), regulator_evidence=(evidence,), as_of=T,
    )
    return raw_linkage.activate_raw_exact_links(
        activation=activation, audit=audit, forwards=(raw_forward,), anchors=(anchor,),
        issuer_evidence=(issuer,), regulator_evidence=(evidence,),
    )[0]


def _governance():
    policy = company_type.create_pit_company_type_classification_policy()
    approval = company_type.approve_pit_company_type_classification_policy(
        approval_id="company-type-human-approval", approved_by="human:explicit-user-approval", approved_at=T,
    )
    active = company_type.activate_pit_company_type_classification_policy(
        selection_id="company-type-active-selection", approval=approval, activated_by="human:explicit-user-approval", activated_at=T,
    )
    return policy, approval, active


def _report(*, forward, taxonomy=(), links=(), evidence=(), as_of=AS_OF):
    return company_type.activate_pit_company_type_classifications(
        activation=_governance()[2], issuer_observations=(forward,), taxonomy_receipts=taxonomy,
        regulator_links=links, regulator_evidence=evidence, as_of=as_of,
    )


def test_human_approval_and_active_policy_are_immutable():
    policy, approval, active = _governance()
    assert policy.semantics[-1] is company_type.PitCompanyTypeClassificationSemantic.WATCH_ONLY_NON_EXECUTABLE
    assert active.approval_id == approval.approval_id
    with pytest.raises(company_type.PitCompanyTypeClassificationError, match="PRECEDES_APPROVAL"):
        company_type.activate_pit_company_type_classification_policy(
            selection_id="early", approval=approval, activated_by="human:fixture", activated_at=T - timedelta(seconds=1),
        )
    with pytest.raises((AttributeError, TypeError)):
        policy.policy_id = "changed"  # type: ignore[misc]


def test_exact_non_financial_requires_positive_pit_taxonomy_not_regulator_absence():
    forward = _forward()
    result = _report(forward=forward, taxonomy=(_taxonomy_receipt(forward, macro="IN07", sector="IN0702"),))
    receipt = result.receipts[0]
    assert receipt.company_type is company_type.PitCompanyType.NON_FINANCIAL
    assert receipt.state is company_type.PitCompanyTypeClassificationState.CLASSIFIED
    assert not receipt.regulator_link_ids


def test_bank_nbfc_and_insurer_need_exact_regulator_links_and_preserve_insurer_subtype():
    bank_forward = _forward(symbol="BANK", isin="INE090A01021", cin="L65190GJ1994PLC021012", code="101")
    bank = _regulator(source=regulator_source.RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, kind=regulator_source.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK, cin=bank_forward.cin)
    bank_result = _report(forward=bank_forward, links=(_raw_link(bank_forward, bank),), evidence=(bank,))
    assert bank_result.receipts[0].company_type is company_type.PitCompanyType.BANK

    nbfc_forward = _forward(symbol="NBFC", isin="INE000A01001", cin="L12345MH2011PLC123456", code="102")
    nbfc = _regulator(source=regulator_source.RegulatorEvidenceSource.RBI_REGISTERED_NBFC_ARC, kind=regulator_source.RegulatorEntityEvidenceKind.RBI_REGISTERED_NBFC, cin=nbfc_forward.cin)
    nbfc_result = _report(forward=nbfc_forward, links=(_raw_link(nbfc_forward, nbfc),), evidence=(nbfc,))
    assert nbfc_result.receipts[0].company_type is company_type.PitCompanyType.NBFC

    insurer_forward = _forward(symbol="LIFE", isin="INE000A01011", cin="L12345MH2012PLC123456", code="103")
    insurer = _regulator(source=regulator_source.RegulatorEvidenceSource.IRDAI_LIFE_INSURERS, kind=regulator_source.RegulatorEntityEvidenceKind.IRDAI_LIFE_INSURER, cin=insurer_forward.cin)
    insurer_result = _report(forward=insurer_forward, links=(_raw_link(insurer_forward, insurer),), evidence=(insurer,))
    assert (insurer_result.receipts[0].company_type, insurer_result.receipts[0].insurer_subtype) == (company_type.PitCompanyType.INSURER, company_type.PitInsurerSubtype.LIFE)


def test_unsupported_financial_and_missing_taxonomy_fail_closed_without_inference():
    financial = _forward(symbol="FIN", isin="INE000A01021", cin="L12345MH2013PLC123456", code="104")
    unsupported = _report(forward=financial, taxonomy=(_taxonomy_receipt(financial, macro="IN05", sector="IN0501"),)).receipts[0]
    assert unsupported.state is company_type.PitCompanyTypeClassificationState.UNSUPPORTED_FINANCIAL
    missing = _report(forward=financial).receipts[0]
    assert (missing.company_type, missing.state) == (None, company_type.PitCompanyTypeClassificationState.DATA_INSUFFICIENT)
    assert company_type.PitCompanyTypeReason.REGULATOR_LINKAGE_UNAVAILABLE in missing.reasons


def test_exact_incompatible_taxonomy_and_regulator_evidence_fails_closed():
    forward = _forward(symbol="CONFLICT", isin="INE000A01031", cin="L12345MH2014PLC123456", code="105")
    bank = _regulator(source=regulator_source.RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, kind=regulator_source.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK, cin=forward.cin)
    receipt = _report(
        forward=forward, taxonomy=(_taxonomy_receipt(forward, macro="IN07", sector="IN0702"),),
        links=(_raw_link(forward, bank),), evidence=(bank,),
    ).receipts[0]
    assert (receipt.company_type, receipt.state) == (None, company_type.PitCompanyTypeClassificationState.EVIDENCE_CONFLICTED)


def test_future_identity_and_regulator_evidence_never_classify_2024():
    forward = _forward()
    bank = _regulator(source=regulator_source.RegulatorEvidenceSource.RBI_SCHEDULED_COMMERCIAL_BANKS, kind=regulator_source.RegulatorEntityEvidenceKind.SCHEDULED_COMMERCIAL_BANK, cin=forward.cin)
    report = _report(forward=forward, links=(_raw_link(forward, bank),), evidence=(bank,), as_of=EARLY)
    assert report.active_issuer_observations == 0 and not report.receipts


def test_deterministic_fingerprint_serialization_and_tamper_rejection():
    forward = _forward()
    taxonomy = _taxonomy_receipt(forward, macro="IN07", sector="IN0702")
    first = _report(forward=forward, taxonomy=(taxonomy,))
    second = _report(forward=forward, taxonomy=(taxonomy,))
    receipt = first.receipts[0]
    assert first == second and company_type.serialize_pit_company_type_classification(receipt) == company_type.serialize_pit_company_type_classification(second.receipts[0])
    with pytest.raises(company_type.PitCompanyTypeClassificationError, match="FINGERPRINT"):
        replace(receipt, fingerprint="sha256:" + "0" * 64)


def test_replay_is_immutable_idempotent_and_uses_dedicated_family(tmp_path):
    forward = _forward()
    report = _report(forward=forward, taxonomy=(_taxonomy_receipt(forward, macro="IN07", sector="IN0702"),))
    policy, approval, activation = _governance()
    database = tmp_path / "company-type.sqlite"
    repository = SQLiteCoreApiSnapshotRepository(database)
    store = company_type.PitCompanyTypeClassificationStore(repository)
    first = company_type.persist_pit_company_type_classifications(store=store, policy=policy, approval=approval, activation=activation, report=report)
    replay = company_type.persist_pit_company_type_classifications(store=store, policy=policy, approval=approval, activation=activation, report=report)
    assert first == (5, 0) and replay == (0, 5) and len(store.receipts()) == 1 and len(store.reports()) == 1
    repository.close()
    reopened = company_type.PitCompanyTypeClassificationStore(SQLiteCoreApiSnapshotRepository(database))
    assert company_type.persist_pit_company_type_classifications(
        store=reopened, policy=policy, approval=approval, activation=activation, report=report,
    ) == (0, 5)


def test_no_company_type_activation_leaks_to_compounder_portfolio_execution_or_runtime_clock():
    source = Path(company_type.__file__).read_text(encoding="utf-8")
    imports = [node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)]
    forbidden = ("compounder", "portfolio", "broker", "order", "decision", "six_gates", "app.signals")
    assert not any(any(value in module for value in forbidden) for module in imports)
    assert "datetime.now" not in source and "requests" not in source and "urllib" not in source
    assert not any(token in source for token in ("SHADOW_CANDIDATE", "BUY", "SELL", "HOLD", "score"))
