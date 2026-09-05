from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, date, datetime, timedelta
import gzip
from pathlib import Path

import pytest

import app.historical.brsr_issuer_anchor_backfill as anchor_source
import app.historical.isin_issuer_bridge_continuity as continuity
import app.historical.nse_taxonomy_company_type_map_activation as activation_module
from app.historical.issuer_identifier_acquisition import IssuerIdentifierEvidenceSource, evidence_from_structured_row
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.nse_mii_security_master import NseMiiSecurityMasterHttpResponse, extract_nse_mii_security_master, nse_mii_security_master_url
from app.historical.nse_session_identity import approve_nse_session_identity_policy, activate_nse_session_identity_policy, session_point_identity_from_row
from app.intelligence import nse_taxonomy_company_type_map_proposal as proposal
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification


AS_OF = datetime(2026, 8, 31, 12, tzinfo=UTC)
GOVERNANCE_AT = datetime(2026, 9, 5, 12, tzinfo=UTC)
ANCHOR_DAY = date(2024, 6, 20)
OBSERVED_AT = datetime(2026, 9, 5, 12, 1, tzinfo=UTC)
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
        body=gzip.compress((HEADERS + _row(symbol, isin, code) + "\n").encode()), document_observed_at=OBSERVED_AT,
    ))


def _forward(*, symbol: str = "APARINDS", isin: str = "INE372A01015", cin: str = "L14292GJ2006PLC049371", code: str = "100"):
    evidence = evidence_from_structured_row(
        source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, source_document=("brsr-" + code).encode(),
        source_reference=BRSR_SOURCE, source_record_id="nse-brsr-application:" + code,
        source_as_of_date=ANCHOR_DAY, source_observed_at=OBSERVED_AT,
        historical_known_at=datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC), isin=None, nse_symbol=symbol,
        issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=cin, issuer_legal_name="Display only",
    )
    anchor = anchor_source.assess_brsr_issuer_anchor(
        evidence, extraction=_mii(symbol=symbol, isin=isin, code=code, day=ANCHOR_DAY), calendar=Calendar(),
    ).anchor
    assert anchor is not None
    approval = continuity.approve_isin_issuer_bridge_continuity_policy(
        approval_id="issuer-approval-" + code, approved_by="human:fixture", approved_at=GOVERNANCE_AT,
    )
    issuer_activation = continuity.activate_isin_issuer_bridge_continuity_policy(
        selection_id="issuer-selection-" + code, approval=approval, activated_by="human:fixture", activated_at=GOVERNANCE_AT,
    )
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=issuer_activation, anchors=(anchor,)).bridges[0]
    session_approval = approve_nse_session_identity_policy(
        approval_id="session-approval-" + code, approved_by="human:fixture", approved_at=GOVERNANCE_AT,
    )
    session_activation = activate_nse_session_identity_policy(
        selection_id="session-selection-" + code, approval=session_approval, activated_by="human:fixture", activated_at=GOVERNANCE_AT,
    )
    later_extraction = _mii(symbol=symbol, isin=isin, code=code, day=AS_OF.date())
    later = session_point_identity_from_row(
        activation=session_activation, snapshot=later_extraction.snapshot, row=later_extraction.rows[0],
    )
    return continuity.activate_forward_issuer_observations(
        activation=issuer_activation, anchor_bridges=(bridge,), later_session_receipts=(later,),
    ).observations[0]


def _taxonomy(*, isin: str = "INE372A01015", macro: str = "IN07", sector: str = "IN0702", source: str = proposal.NSE_TAXONOMY_SOURCE, version: str = proposal.NSE_TAXONOMY_VERSION, effective_from: datetime = AS_OF - timedelta(days=4)):
    return InstrumentTaxonomyClassification(
        classification_id="nse-indices-taxonomy:" + isin, instrument_id="NSE:" + isin, industry=None,
        sector="Text intentionally ignored", super_sector="Text intentionally ignored", source=source,
        source_type=ClassificationSourceStatus.OFFICIAL, effective_from=effective_from, effective_to=None,
        as_of=effective_from, confidence=1.0, classification_version=version, source_reference="source=fixture",
        macro_economic_sector_code=macro, sector_code=sector, raw_classification_label="Never interpreted",
        resolution_status="EXACT_UNIQUE", source_sha256=SOURCE_SHA, fetched_at_utc=effective_from,
        effective_observation_semantics=proposal.NSE_TAXONOMY_SEMANTICS,
    )


def _governance():
    policy = activation_module.create_nse_taxonomy_category_map_policy()
    approval = activation_module.approve_nse_taxonomy_category_map_policy(
        approval_id="nse-taxonomy-human-approval-v1", approved_by="human:explicit-user-approval", approved_at=GOVERNANCE_AT,
    )
    activation = activation_module.activate_nse_taxonomy_category_map_policy(
        selection_id="nse-taxonomy-active-selection-v1", approval=approval,
        activated_by="human:explicit-user-approval", activated_at=GOVERNANCE_AT + timedelta(seconds=1),
    )
    return policy, approval, activation


def _report():
    _, _, active = _governance()
    non_financial = _forward()
    unsupported = _forward(symbol="ICICIBANK", isin="INE090A01021", cin="L65190GJ1994PLC021012", code="101")
    unknown = _forward(symbol="MISC", isin="INE000A01001", cin="L91110GJ1989PLC012802", code="102")
    missing = _forward(symbol="DEEPINDS", isin="INE0FHS01024", cin="L24100GJ2006PLC049173", code="103")
    report = activation_module.activate_nse_taxonomy_category_evidence(
        activation=active,
        classifications=(
            _taxonomy(), _taxonomy(isin=unsupported.isin, macro="IN05", sector="IN0501"),
            _taxonomy(isin=unknown.isin, macro="IN12", sector="IN1201"),
        ), issuer_observations=(missing, unknown, unsupported, non_financial), as_of=AS_OF,
    )
    return report, (non_financial, unsupported, unknown, missing)


def test_immutable_human_approval_and_active_fixed_source_version_selection():
    policy, approval, active = _governance()
    assert (policy.policy_id, policy.policy_version) == (activation_module.POLICY_ID, "v1")
    assert policy.approved_map_fingerprint == proposal.create_proposed_nse_taxonomy_company_type_map().fingerprint
    assert (active.taxonomy_source, active.taxonomy_version) == (proposal.NSE_TAXONOMY_SOURCE, proposal.NSE_TAXONOMY_VERSION)
    with pytest.raises(activation_module.NseTaxonomyCategoryEvidenceError, match="APPROVAL_INVALID"):
        replace(approval, policy_fingerprint="sha256:" + "0" * 64).verify()
    with pytest.raises(activation_module.NseTaxonomyCategoryEvidenceError, match="PRECEDES_APPROVAL"):
        activation_module.activate_nse_taxonomy_category_map_policy(
            selection_id="too-early", approval=approval, activated_by="human:fixture", activated_at=GOVERNANCE_AT - timedelta(seconds=1),
        )


def test_exact_categories_and_missing_taxonomy_remain_evidence_only():
    report, observations = _report()
    assert (report.active_issuer_observations, report.exact_taxonomy_assignments, len(report.receipts), report.missing_taxonomy) == (4, 3, 3, 1)
    assert (report.non_financial_candidates, report.unsupported_financial, report.unknown_non_comparable, report.unmapped, report.conflicts) == (1, 1, 1, 0, 0)
    by_isin = {item.canonical_instrument_id.removeprefix("NSE:"): item for item in report.receipts}
    assert by_isin[observations[0].isin].category is proposal.NseTaxonomyResearchCategory.NON_FINANCIAL_CANDIDATE
    assert by_isin[observations[1].isin].category is proposal.NseTaxonomyResearchCategory.UNSUPPORTED_FINANCIAL
    assert by_isin[observations[2].isin].category is proposal.NseTaxonomyResearchCategory.UNKNOWN_NON_COMPARABLE
    assert observations[3].isin not in by_isin
    assert all(item.actionability == "WATCH_ONLY" and item.execution_status == "NON_EXECUTABLE" for item in report.receipts)


def test_unseen_and_future_or_unsupported_source_taxonomy_fail_closed_without_receipt():
    _, _, active = _governance()
    observed = _forward()
    unseen = activation_module.activate_nse_taxonomy_category_evidence(
        activation=active, classifications=(_taxonomy(macro="IN99", sector="IN9901"),), issuer_observations=(observed,), as_of=AS_OF,
    )
    future = activation_module.activate_nse_taxonomy_category_evidence(
        activation=active, classifications=(_taxonomy(effective_from=AS_OF + timedelta(microseconds=1)),), issuer_observations=(observed,), as_of=AS_OF,
    )
    unsupported = activation_module.activate_nse_taxonomy_category_evidence(
        activation=active, classifications=(_taxonomy(version="nse-indices-taxonomy-v2"),), issuer_observations=(observed,), as_of=AS_OF,
    )
    assert (len(unseen.receipts), unseen.unmapped, unseen.missing_taxonomy) == (0, 1, 0)
    assert (len(future.receipts), future.unmapped, future.missing_taxonomy) == (0, 0, 1)
    assert (len(unsupported.receipts), unsupported.unmapped, unsupported.missing_taxonomy) == (0, 1, 0)


def test_current_taxonomy_never_propagates_backward_and_inactive_future_observation_is_excluded():
    _, _, active = _governance()
    observed = _forward()
    historic = activation_module.activate_nse_taxonomy_category_evidence(
        activation=active, classifications=(_taxonomy(),), issuer_observations=(observed,), as_of=datetime(2024, 2, 5, 12, tzinfo=UTC),
    )
    assert (historic.active_issuer_observations, historic.exact_taxonomy_assignments, len(historic.receipts)) == (0, 0, 0)


def test_deterministic_fingerprint_and_tampered_lineage_are_rejected():
    report, observations = _report()
    reordered = activation_module.activate_nse_taxonomy_category_evidence(
        activation=_governance()[2], classifications=tuple(reversed((_taxonomy(), _taxonomy(isin="INE090A01021", macro="IN05", sector="IN0501"), _taxonomy(isin="INE000A01001", macro="IN12", sector="IN1201")))), issuer_observations=tuple(reversed(observations)), as_of=AS_OF,
    )
    assert report.receipts == reordered.receipts and report.fingerprint == reordered.fingerprint
    with pytest.raises(activation_module.NseTaxonomyCategoryEvidenceError, match="RECEIPT_INVALID"):
        replace(report.receipts[0], taxonomy_assignment_source_sha256="b" * 64).verify()


def test_persistence_is_insert_only_idempotent_and_reopen_safe(tmp_path: Path):
    report, _ = _report()
    policy, approval, active = _governance()
    repository = SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy-category.sqlite")
    store = activation_module.NseTaxonomyCategoryEvidenceStore(repository)
    first = activation_module.persist_nse_taxonomy_category_evidence(store=store, policy=policy, approval=approval, activation=active, report=report)
    replay = activation_module.persist_nse_taxonomy_category_evidence(store=store, policy=policy, approval=approval, activation=active, report=report)
    assert first == (6, 0) and replay == (0, 6)
    repository.close()
    reopened = activation_module.NseTaxonomyCategoryEvidenceStore(SQLiteCoreApiSnapshotRepository(tmp_path / "taxonomy-category.sqlite"))
    assert reopened.receipts() == report.receipts


def test_receipt_surface_and_static_dependencies_preserve_regulator_and_final_classifier_independence():
    report, _ = _report()
    receipt_fields = {item.name for item in fields(activation_module.NseTaxonomyCategoryEvidenceReceipt)}
    source = Path(activation_module.__file__).read_text(encoding="utf-8").lower()
    assert not receipt_fields & {"company_type", "portfolio", "order", "broker", "price", "quantity", "score", "rank", "strategy"}
    assert "app.intelligence.pit_company_type" not in source
    for forbidden in ("app.historical.regulator", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "sqlite3", "datetime.now", "time.time", "backtest", "compounder"):
        assert forbidden not in source
    assert all(item.canonical_issuer_id and item.category is not proposal.NseTaxonomyResearchCategory.UNMAPPED for item in report.receipts)
