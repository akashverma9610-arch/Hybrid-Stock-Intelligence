from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import ast
import gzip
import inspect
from pathlib import Path

import pytest

import app.intelligence.compounder_prospective_shadow_validation as module
from app.data_sources.models import FundamentalFactKind
from app.fundamentals.models import FinancialFact, FinancialMetric, FinancialPeriodType, FinancialValueBasis, NumericScale, StatementScope
from app.historical import isin_issuer_bridge_continuity as continuity
from app.historical import nse_taxonomy_company_type_map_activation as taxonomy_activation
from app.historical import pit_company_type_classification_activation as company_type
from app.historical.brsr_issuer_anchor_backfill import assess_brsr_issuer_anchor
from app.historical.issuer_identifier_acquisition import IssuerIdentifierEvidenceSource, evidence_from_structured_row
from app.historical.issuer_security_identity import IssuerIdentifierType
from app.historical.nse_mii_security_master import NseMiiSecurityMasterHttpResponse, extract_nse_mii_security_master, nse_mii_security_master_url
from app.historical.nse_session_identity import activate_nse_session_identity_policy, approve_nse_session_identity_policy, session_point_identity_from_row
from app.intelligence import nse_taxonomy_company_type_map_proposal as taxonomy_proposal
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType
from app.storage.sqlite_core_api_snapshot_repository import SQLiteCoreApiSnapshotRepository
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification

from app.intelligence.compounder_prospective_shadow_validation import (
    BusinessOutcomeMaturity,
    CompounderProspectiveObservation,
    CompounderProspectiveShadowStore,
    MarketOutcomeReadiness,
    ProspectiveReadinessState,
    assess_compounder_prospective_readiness,
    frozen_compounder_candidate_grid_plan,
    initial_business_outcome_readiness,
    market_outcome_readiness,
    run_compounder_prospective_batch,
    serialize_compounder_prospective_observation,
)


T = datetime(2026, 9, 5, 12, tzinfo=UTC)
AS_OF = datetime(2026, 8, 31, 23, 59, 59, tzinfo=UTC)
ISIN = "INE372A01015"
CIN = "L14292GJ2006PLC049371"
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


class Calendar:
    def is_trading_day(self, value: date) -> bool:
        return value == date(2024, 6, 20)


def _mii(day: date):
    body = (HEADERS + f"100,APARINDS,EQ,Exact Ltd,{ISIN},6,100,0,EQ,EQUITY\n").encode()
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=day, source_reference=nse_mii_security_master_url(day), content_type="application/x-gzip",
        body=gzip.compress(body), document_observed_at=T,
    ))


def _company_type_receipt():
    anchor_day = date(2024, 6, 20)
    evidence = evidence_from_structured_row(
        source=IssuerIdentifierEvidenceSource.NSE_BRSR_ARCHIVE, source_document=b"brsr", source_reference="https://nsearchives.nseindia.com/brsr",
        source_record_id="nse-brsr-application:100", source_as_of_date=anchor_day, source_observed_at=T,
        historical_known_at=datetime(2024, 6, 20, 10, tzinfo=UTC), isin=None, nse_symbol="APARINDS",
        issuer_identifier_type=IssuerIdentifierType.CIN, issuer_identifier_value=CIN, issuer_legal_name="Exact Legal Entity",
    )
    anchor = assess_brsr_issuer_anchor(evidence, extraction=_mii(anchor_day), calendar=Calendar()).anchor
    assert anchor is not None
    approval = continuity.approve_isin_issuer_bridge_continuity_policy(approval_id="issuer-approval", approved_by="human:fixture", approved_at=T)
    activation = continuity.activate_isin_issuer_bridge_continuity_policy(selection_id="issuer-selection", approval=approval, activated_by="human:fixture", activated_at=T)
    bridge = continuity.activate_isin_issuer_anchor_bridges(activation=activation, anchors=(anchor,)).bridges[0]
    session_approval = approve_nse_session_identity_policy(approval_id="session-approval", approved_by="human:fixture", approved_at=T)
    session_activation = activate_nse_session_identity_policy(selection_id="session-selection", approval=session_approval, activated_by="human:fixture", activated_at=T)
    extraction = _mii(AS_OF.date())
    session = session_point_identity_from_row(activation=session_activation, snapshot=extraction.snapshot, row=extraction.rows[0])
    forward = continuity.activate_forward_issuer_observations(activation=activation, anchor_bridges=(bridge,), later_session_receipts=(session,)).observations[0]
    classification = InstrumentTaxonomyClassification(
        classification_id="nse-indices-taxonomy:" + ISIN, instrument_id="NSE:" + ISIN, industry=None, sector="Ignored", super_sector="Ignored",
        source=taxonomy_proposal.NSE_TAXONOMY_SOURCE, source_type=ClassificationSourceStatus.OFFICIAL,
        effective_from=AS_OF - timedelta(days=4), effective_to=None, as_of=AS_OF - timedelta(days=4), confidence=1.0,
        classification_version=taxonomy_proposal.NSE_TAXONOMY_VERSION, source_reference="fixture", macro_economic_sector_code="IN07", sector_code="IN0702",
        raw_classification_label="Ignored", resolution_status="EXACT_UNIQUE", source_sha256="a" * 64,
        fetched_at_utc=AS_OF - timedelta(days=4), effective_observation_semantics=taxonomy_proposal.NSE_TAXONOMY_SEMANTICS,
    )
    tax_approval = taxonomy_activation.approve_nse_taxonomy_category_map_policy(approval_id="taxonomy-approval", approved_by="human:fixture", approved_at=T)
    tax_active = taxonomy_activation.activate_nse_taxonomy_category_map_policy(selection_id="taxonomy-selection", approval=tax_approval, activated_by="human:fixture", activated_at=T)
    taxonomy = taxonomy_activation.activate_nse_taxonomy_category_evidence(activation=tax_active, classifications=(classification,), issuer_observations=(forward,), as_of=AS_OF).receipts[0]
    policy_approval = company_type.approve_pit_company_type_classification_policy(approval_id="type-approval", approved_by="human:fixture", approved_at=T)
    policy_active = company_type.activate_pit_company_type_classification_policy(selection_id="type-selection", approval=policy_approval, activated_by="human:fixture", activated_at=T)
    receipt = company_type.activate_pit_company_type_classifications(activation=policy_active, issuer_observations=(forward,), taxonomy_receipts=(taxonomy,), regulator_links=(), regulator_evidence=(), as_of=AS_OF).receipts[0]
    return receipt, session


def _facts(instrument_id: str, *, received: datetime = AS_OF - timedelta(days=1), scope=StatementScope.CONSOLIDATED):
    instrument = InstrumentIdentity(instrument_id, Exchange.NSE, "APARINDS", "APARINDS", ISIN, "EQ", InstrumentType.NSE_EQUITY, "Exact Ltd")
    result = []
    sequences = ((FinancialMetric.REVENUE, ("100", "120", "144", "172.8", "207.36")), (FinancialMetric.PAT, ("10", "12", "14.4", "17.28", "20.736")), (FinancialMetric.CFO, ("8", "10", "12", "14", "16")), (FinancialMetric.TOTAL_EQUITY, ("50", "60", "70", "80", "90")), (FinancialMetric.CASH_AND_EQUIVALENTS, ("5", "6", "7", "8", "9")))
    for metric, values in sequences:
        point = metric in {FinancialMetric.TOTAL_EQUITY, FinancialMetric.CASH_AND_EQUIVALENTS}
        for offset, value in enumerate(values):
            year = 2022 + offset
            result.append(FinancialFact(
                f"{metric.value}:{scope.value}:{year}", instrument, metric, Decimal(value), "INR", "INR", NumericScale.CRORES,
                FinancialPeriodType.POINT_IN_TIME if point else FinancialPeriodType.ANNUAL,
                FinancialValueBasis.UNKNOWN if point else FinancialValueBasis.FULL_YEAR,
                None if point else datetime(year - 1, 4, 1, tzinfo=UTC), datetime(year, 3, 31, tzinfo=UTC), year, None, scope,
                FundamentalFactKind.REPORTED, "BSE_OFFICIAL", f"filing:{metric.value}:{year}", "source", datetime(year, 5, 1, tzinfo=UTC), received,
                "bse-official-local-xbrl-v1",
            ))
    return tuple(result)


def _ready(scope=StatementScope.CONSOLIDATED):
    receipt, session = _company_type_receipt()
    facts = _facts(receipt.canonical_instrument_id, scope=scope)
    return assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(session,), facts=facts, statement_scope=scope), receipt, session, facts


def test_exact_non_financial_observation_is_immutable_and_deterministic():
    first, receipt, session, facts = _ready()
    second = assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(session,), facts=tuple(reversed(facts)), statement_scope=StatementScope.CONSOLIDATED)
    assert first.state is ProspectiveReadinessState.PROSPECTIVE_OBSERVATION_READY and first.observation is not None
    assert first.observation == second.observation
    assert first.observation.company_type_receipt.company_type is company_type.PitCompanyType.NON_FINANCIAL
    assert serialize_compounder_prospective_observation(first.observation) == serialize_compounder_prospective_observation(second.observation)
    with pytest.raises(FrozenInstanceError): first.observation.as_of = T  # type: ignore[misc]


def test_exact_pit_security_basis_and_metric_failures_are_closed():
    ready, receipt, session, facts = _ready()
    no_session = assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(), facts=facts, statement_scope=StatementScope.CONSOLIDATED)
    wrong_basis = assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(session,), facts=facts, statement_scope=StatementScope.UNKNOWN)
    future = tuple(replace(item, fact_id=item.fact_id + ":future", received_at=AS_OF + timedelta(seconds=1)) for item in facts)
    incomplete = assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(session,), facts=future, statement_scope=StatementScope.CONSOLIDATED)
    assert ready.observation is not None
    assert no_session.state is ProspectiveReadinessState.SECURITY_IDENTITY_UNAVAILABLE
    assert wrong_basis.state is ProspectiveReadinessState.BASIS_MISMATCH
    assert incomplete.state in {ProspectiveReadinessState.METRICS_INCOMPLETE, ProspectiveReadinessState.FINANCIAL_FACTS_MISSING}


def test_tampered_type_and_input_after_as_of_fail_closed():
    _, receipt, session, facts = _ready()
    with pytest.raises(ValueError):
        replace(receipt, company_type=company_type.PitCompanyType.BANK)
    object.__setattr__(receipt, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="FINGERPRINT"):
        assess_compounder_prospective_readiness(as_of=AS_OF, company_type_receipt=receipt, security_identities=(session,), facts=facts, statement_scope=StatementScope.CONSOLIDATED)
    _, receipt, session, facts = _ready()
    early = AS_OF - timedelta(seconds=1)
    assert assess_compounder_prospective_readiness(as_of=early, company_type_receipt=receipt, security_identities=(session,), facts=facts, statement_scope=StatementScope.CONSOLIDATED).state is ProspectiveReadinessState.INPUT_AFTER_AS_OF


def test_nested_annual_and_metric_lineage_tampering_is_rejected():
    ready, *_ = _ready()
    assert ready.observation is not None
    annual_cover = next(item for item in ready.observation.annual_facts.covers if item.selection_policy_fingerprint)
    object.__setattr__(annual_cover, "selection_policy_fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="CANONICAL_ANNUAL_FACT_COVERAGE_FINGERPRINT_MISMATCH"):
        ready.observation.verify()

    ready, *_ = _ready()
    assert ready.observation is not None
    metric = next(item for item in ready.observation.derived_metrics.receipts if item.status.name == "AVAILABLE")
    object.__setattr__(metric, "values", (("tampered", Decimal("1")),))
    with pytest.raises(ValueError, match="COMPOUNDER_DERIVED_RECEIPT_FINGERPRINT_MISMATCH"):
        ready.observation.verify()


def test_grid_is_lineage_only_outcomes_are_immature_and_market_is_not_ready():
    ready, *_ = _ready(); assert ready.observation is not None
    plan = frozen_compounder_candidate_grid_plan()
    assert plan.state == "NOT_APPROVED_NOT_ACTIVE_NON_EXECUTABLE"
    outcomes = initial_business_outcome_readiness(ready.observation)
    assert {item.maturity for item in outcomes} == {BusinessOutcomeMaturity.IMMATURE} and all(not item.future_fact_ids for item in outcomes)
    assert market_outcome_readiness(ready.observation).state is MarketOutcomeReadiness.MARKET_OUTCOME_NOT_READY
    assert not any(name in ready.observation.__dataclass_fields__ for name in ("score", "entry", "target", "price", "quantity", "portfolio", "order"))


def test_insert_only_replay_and_revision_create_distinct_observation(tmp_path):
    ready, receipt, session, facts = _ready(); assert ready.observation is not None
    store = CompounderProspectiveShadowStore(SQLiteCoreApiSnapshotRepository(tmp_path / "prospective.sqlite"))
    first, diagnostics = run_compounder_prospective_batch(as_of=AS_OF, company_type_receipts=(receipt,), security_identities=(session,), facts_for_instrument=lambda _: facts, store=store)
    replay, _ = run_compounder_prospective_batch(as_of=AS_OF, company_type_receipts=(receipt,), security_identities=(session,), facts_for_instrument=lambda _: facts, store=store)
    revised = tuple(replace(item, fact_id=item.fact_id + ":revision", received_at=AS_OF + timedelta(days=1)) for item in facts)
    later = AS_OF + timedelta(days=1)
    # The old observation remains intact; a later exact session would be required before a revision can be frozen.
    later_report, _ = run_compounder_prospective_batch(as_of=later, company_type_receipts=(receipt,), security_identities=(session,), facts_for_instrument=lambda _: revised, store=store)
    assert first.observations_inserted == 1 and replay.observations_inserted == 0 and replay.observations_already_present == 1
    assert len(store.observations()) == 1 and diagnostics[0].observation == ready.observation
    assert later_report.prospective_ready == 0 and len(store.observations()) == 1


def test_static_boundary_has_no_qualification_or_forbidden_dependencies():
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    imports = {item.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for item in node.names} | {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    assert not any(name.startswith(prefix) for name in imports for prefix in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.signals", "app.runtime"))
    assert "datetime.now" not in source
    assert not any(name in CompounderProspectiveObservation.__dataclass_fields__ for name in ("candidate", "qualification", "score", "ranking", "buy", "sell", "hold", "entry", "stop", "target", "price", "quantity", "allocation"))
