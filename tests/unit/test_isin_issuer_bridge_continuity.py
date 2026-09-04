from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
import gzip

import pytest

import app.historical.brsr_issuer_anchor_backfill as anchor_source
import app.historical.isin_issuer_bridge_continuity as continuity
from app.historical.issuer_identifier_acquisition import IssuerIdentifierEvidenceSource, evidence_from_structured_row
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.nse_mii_security_master import NseMiiSecurityMasterHttpResponse, extract_nse_mii_security_master, nse_mii_security_master_url
from app.historical.nse_session_identity import approve_nse_session_identity_policy, activate_nse_session_identity_policy, session_point_identity_from_row
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository


ANCHOR_DAY = date(2024, 6, 20)
LATER_DAY = date(2026, 8, 31)
ANCHOR_KNOWN_AT = datetime(2024, 6, 20, 10, 38, 9, tzinfo=UTC)
GOVERNANCE_AT = datetime(2026, 9, 4, 18, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 9, 4, 18, 1, tzinfo=UTC)
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"
BRSR_SOURCE = "https://nsearchives.nseindia.com/web/sites/default/files/inline-files/BRSR_Data_Dump.zip"


class Calendar:
    def is_trading_day(self, value: date) -> bool:
        return value == ANCHOR_DAY


def _row(symbol: str = "DEEPINDS", isin: str = "INE0FHS01024", code: str = "100") -> str:
    return f"{code},{symbol},EQ,Exact Ltd,{isin},6,100,0,EQ,EQUITY"


def _mii(*rows: str, day: date):
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=day, source_reference=nse_mii_security_master_url(day), content_type="application/x-gzip",
        body=gzip.compress((HEADERS + "\n".join(rows) + "\n").encode()), document_observed_at=OBSERVED_AT,
    ))


def _anchor(*, cin: str = "L14292GJ2006PLC049371", application: str = "45705", symbol: str = "DEEPINDS", isin: str = "INE0FHS01024", known_at: datetime = ANCHOR_KNOWN_AT):
    evidence = evidence_from_structured_row(
        source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, source_document=b"brsr-general",
        source_reference=BRSR_SOURCE, source_record_id="nse-brsr-application:" + application,
        source_as_of_date=ANCHOR_DAY, source_observed_at=OBSERVED_AT, historical_known_at=known_at,
        isin=None, nse_symbol=symbol, issuer_identifier_type=IssuerIdentifierType.CIN,
        issuer_identifier_value=cin, issuer_legal_name="Display only",
    )
    assessment = anchor_source.assess_brsr_issuer_anchor(
        evidence, extraction=_mii(_row(symbol, isin), day=ANCHOR_DAY), calendar=Calendar(),
    )
    assert assessment.anchor is not None
    return assessment.anchor


def _activation():
    approval = continuity.approve_isin_issuer_bridge_continuity_policy(
        approval_id="human-approval-v1", approved_by="human:explicit-user-approval", approved_at=GOVERNANCE_AT,
    )
    return approval, continuity.activate_isin_issuer_bridge_continuity_policy(
        selection_id="human-selection-v1", approval=approval,
        activated_by="human:explicit-user-approval", activated_at=GOVERNANCE_AT + timedelta(seconds=1),
    )


def _later(*, symbol: str = "DEEPINDS", isin: str = "INE0FHS01024", day: date = LATER_DAY, code: str = "100"):
    approval = approve_nse_session_identity_policy(
        approval_id="nse-session-approval", approved_by="human:explicit-user-approval", approved_at=GOVERNANCE_AT,
    )
    activation = activate_nse_session_identity_policy(
        selection_id="nse-session-selection", approval=approval,
        activated_by="human:explicit-user-approval", activated_at=GOVERNANCE_AT,
    )
    extraction = _mii(_row(symbol, isin, code), day=day)
    return session_point_identity_from_row(activation=activation, snapshot=extraction.snapshot, row=extraction.rows[0])


def test_policy_approval_and_active_selection_are_immutable_human_governance():
    policy = continuity.create_isin_issuer_bridge_continuity_policy()
    approval, activation = _activation()
    assert policy.policy_id == continuity.POLICY_ID and policy.policy_version == "v1"
    assert approval.approved_by.startswith("human:")
    assert activation.approval_id == approval.approval_id
    with pytest.raises(continuity.IsinIssuerBridgeContinuityError, match="APPROVAL_INVALID"):
        replace(approval, policy_fingerprint="sha256:" + "0" * 64)
    with pytest.raises(continuity.IsinIssuerBridgeContinuityError, match="PRECEDES_APPROVAL"):
        continuity.activate_isin_issuer_bridge_continuity_policy(
            selection_id="too-early", approval=approval, activated_by="human:explicit-user-approval",
            activated_at=GOVERNANCE_AT - timedelta(seconds=1),
        )


def test_exact_anchor_activation_preserves_brsr_known_at_and_all_primary_lineage():
    _, activation = _activation()
    source = _anchor()
    result = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(source,))
    bridge = result.bridges[0]
    assert (bridge.isin, bridge.cin, bridge.anchor_symbol) == (source.isin, source.cin, source.symbol)
    assert bridge.issuer_known_at == ANCHOR_KNOWN_AT
    assert bridge.anchor_id == source.anchor_id and bridge.brsr_evidence_id == source.brsr_evidence_id
    assert bridge.mii_row_ids == tuple(value.mii_row_id for value in source.mii_rows)
    assert bridge.state is continuity.IsinIssuerBridgeState.ACTIVE


def test_timestamp_selector_rejects_pre_anchor_and_accepts_exact_known_at_without_session_open_inference():
    _, activation = _activation()
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges[0]
    before = continuity.resolve_isin_issuer_anchor_at(bridges=(bridge,), isin=bridge.isin, as_of=ANCHOR_KNOWN_AT - timedelta(seconds=1))
    exact = continuity.resolve_isin_issuer_anchor_at(bridges=(bridge,), isin=bridge.isin, as_of=ANCHOR_KNOWN_AT)
    assert before.status is continuity.IsinIssuerBridgeResolutionStatus.PRE_ANCHOR_KNOWN_AT
    assert exact.status is continuity.IsinIssuerBridgeResolutionStatus.ISSUER_ANCHOR_PRESENT
    assert exact.bridges == (bridge,)


def test_exchange_labelled_anchor_session_does_not_require_the_same_utc_calendar_date():
    _, activation = _activation()
    local_filing_timestamp_as_utc = datetime(2024, 6, 19, 19, 0, tzinfo=UTC)
    bridge = continuity.activate_isin_issuer_anchor_bridges(
        activation=activation, anchors=(_anchor(known_at=local_filing_timestamp_as_utc),),
    ).bridges[0]
    assert bridge.anchor_session_date == ANCHOR_DAY
    assert bridge.issuer_known_at == local_filing_timestamp_as_utc


def test_compatible_same_isin_same_cin_anchors_preserve_all_lineages_and_conflicting_cin_fails_closed():
    _, activation = _activation()
    first, compatible = _anchor(application="one"), _anchor(application="two")
    ready = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(compatible, first))
    assert len(ready.bridges) == 2 and not ready.conflicted_anchor_ids
    conflict = _anchor(application="three", cin="L91110GJ1989PLC012802")
    conflicted = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(first, conflict))
    assert not conflicted.bridges and conflicted.conflicted_anchor_ids == tuple(sorted((first.anchor_id, conflict.anchor_id)))


def test_exact_same_isin_later_session_creates_forward_observation_and_changed_symbol_is_descriptive():
    _, activation = _activation()
    bridges = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges
    normal = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=bridges, later_session_receipts=(_later(),))
    changed = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=bridges, later_session_receipts=(_later(symbol="NEWDEEP"),))
    assert normal.observations[0].later_symbol == "DEEPINDS"
    assert changed.observations[0].later_symbol == "NEWDEEP"
    assert changed.observations[0].cin == bridges[0].cin
    assert changed.observations[0].anchor_bridge_ids == (bridges[0].bridge_id,)
    assert changed.observations[0].later_session_receipt_ids == (_later(symbol="NEWDEEP").receipt_id,)


def test_compatible_same_isin_same_symbol_later_receipts_preserve_every_lineage_without_input_order_selection():
    _, activation = _activation()
    bridges = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges
    first, second = _later(code="100"), _later(code="101")
    result = continuity.activate_forward_issuer_observations(
        activation=activation, anchor_bridges=bridges, later_session_receipts=(second, first),
    )
    observation = result.observations[0]
    assert observation.later_session_receipt_ids == tuple(sorted((first.receipt_id, second.receipt_id)))
    assert observation.later_session_fingerprints == tuple(
        next(item.fingerprint for item in (first, second) if item.receipt_id == receipt_id)
        for receipt_id in observation.later_session_receipt_ids
    )


def test_compatible_anchor_lineage_keeps_each_known_timestamp_paired_to_its_bridge_id():
    _, activation = _activation()
    anchors = (_anchor(application="earlier", known_at=ANCHOR_KNOWN_AT), _anchor(application="later", known_at=ANCHOR_KNOWN_AT + timedelta(hours=1)))
    bridges = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=anchors).bridges
    observation = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=bridges, later_session_receipts=(_later(),)).observations[0]
    expected = {value.bridge_id: value.issuer_known_at for value in bridges}
    assert dict(zip(observation.anchor_bridge_ids, observation.anchor_known_ats, strict=True)) == expected


def test_same_symbol_changed_isin_is_not_stitched_and_absence_has_no_lifecycle_conclusion():
    _, activation = _activation()
    bridges = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges
    result = continuity.activate_forward_issuer_observations(
        activation=activation, anchor_bridges=bridges,
        later_session_receipts=(_later(symbol="DEEPINDS", isin="INE000A01001"),),
    )
    assert not result.observations
    assert result.absent_anchor_isins == ("INE0FHS01024",)
    assert not result.lifecycle_blocked_isins


def test_exact_nse_lifecycle_discontinuity_blocks_forward_but_bse_cannot_enter_the_contract():
    _, activation = _activation()
    bridges = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges
    blocker = continuity.ExactNseLifecycleDiscontinuity(
        evidence_id="nse-lifecycle:one", evidence_fingerprint="sha256:" + "1" * 64,
        isin=bridges[0].isin, known_at=datetime(2025, 1, 1, tzinfo=UTC), effective_on=date(2025, 1, 1),
        source_reference="https://www.nseindia.com/corporate/lifecycle.pdf",
    )
    result = continuity.activate_forward_issuer_observations(
        activation=activation, anchor_bridges=bridges, later_session_receipts=(_later(),), lifecycle_discontinuities=(blocker,),
    )
    assert not result.observations and result.lifecycle_blocked_isins == (bridges[0].isin,)
    with pytest.raises(continuity.IsinIssuerBridgeContinuityError, match="LIFECYCLE_DISCONTINUITY_INVALID"):
        continuity.ExactNseLifecycleDiscontinuity(
            evidence_id="bse-lifecycle:one", evidence_fingerprint="sha256:" + "2" * 64,
            isin=bridges[0].isin, known_at=datetime(2025, 1, 1, tzinfo=UTC), effective_on=date(2025, 1, 1),
            source_reference="https://www.bseindia.com/corporate/lifecycle.pdf",
        )


def test_forward_requires_strictly_later_session_and_does_not_use_anchor_day_as_session_start():
    _, activation = _activation()
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges[0]
    same_day = _later(day=ANCHOR_DAY)
    result = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=(bridge,), later_session_receipts=(same_day,))
    assert not result.observations and result.non_forward_anchor_ids == (bridge.anchor_id,)


def test_persistence_round_trip_replay_and_deterministic_fingerprints(tmp_path):
    approval, activation = _activation()
    anchor_result = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),))
    forward_result = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=anchor_result.bridges, later_session_receipts=(_later(),))
    store = continuity.IsinIssuerBridgeContinuityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "continuity.sqlite"))
    first = continuity.persist_isin_issuer_continuity(store=store, approval=approval, activation=activation, anchors=anchor_result, forwards=forward_result, observed_at=OBSERVED_AT)
    replay = continuity.persist_isin_issuer_continuity(store=store, approval=approval, activation=activation, anchors=anchor_result, forwards=forward_result, observed_at=OBSERVED_AT)
    assert first == (1, 0, 1, 0) and replay == (0, 1, 0, 1)
    assert len(store.anchor_bridges()) == 1 and len(store.forward_observations()) == 1
    store._repository.close()
    reopened = continuity.IsinIssuerBridgeContinuityStore(SQLiteCoreApiSnapshotRepository(tmp_path / "continuity.sqlite"))
    assert reopened.anchor_bridges() == anchor_result.bridges
    assert reopened.forward_observations() == forward_result.observations


def test_tampering_and_distinct_later_same_isin_symbols_preserve_separate_descriptive_observations():
    _, activation = _activation()
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(_anchor(),)).bridges[0]
    with pytest.raises(continuity.IsinIssuerBridgeContinuityError, match="ANCHOR_BRIDGE_INVALID"):
        replace(bridge, cin="L91110GJ1989PLC012802")
    first, second = _later(symbol="ONE"), _later(symbol="TWO")
    result = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=(bridge,), later_session_receipts=(second, first))
    assert {item.later_symbol for item in result.observations} == {"ONE", "TWO"}
    assert len({item.observation_id for item in result.observations}) == 2
    assert not result.conflicted_isins


def test_static_boundaries_exclude_generic_signal_company_type_backtest_portfolio_and_execution():
    source = open(continuity.__file__, encoding="utf-8").read().lower()
    for forbidden in (
        "app.intelligence", "app.portfolio", "app.broker", "app.orders", "app.api", "app.runtime", "sqlite3",
        "company_type", "backtest", "compounder", "place_order", "datetime.now", "time.time", "buy", "sell", "rotate",
        "app.historical.bse_lifecycle",
    ):
        assert forbidden not in source
