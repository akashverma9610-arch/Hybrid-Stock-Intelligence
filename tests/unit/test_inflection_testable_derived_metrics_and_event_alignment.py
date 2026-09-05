from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
import ast
import gzip
import inspect
from pathlib import Path

import pytest

import app.intelligence.inflection_testable_derived_metrics_and_event_alignment as module
from app.data_sources.models import FundamentalFactKind
from app.filings.models import CorporateFiling, FilingType, FinancialResultMetadata, PrimarySourceQuality
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
from app.intelligence.inflection_testable_derived_metrics_and_event_alignment import (
    EventCalendarAlignmentState,
    FilingLineageState,
    InflectionDerivedMetricsReason,
    InflectionDerivedMetricsState,
    InflectionResearchMetric,
    evaluate_inflection_testable_derived_metrics_and_event_alignment,
    serialize_inflection_testable_derived_metrics,
)
from app.market_data.models import Exchange, InstrumentIdentity, InstrumentType, MarketDataProvenance
from app.taxonomy.models import ClassificationSourceStatus, InstrumentTaxonomyClassification


AS_OF = datetime(2026, 8, 31, 23, 59, tzinfo=UTC)
T = datetime(2026, 9, 5, 12, tzinfo=UTC)
ISIN = "INE372A01015"
CIN = "L14292GJ2006PLC049371"
HEADERS = "FinInstrmId,TckrSymb,SctySrs,FinInstrmNm,ISIN,SctyStsNrmlMkt,ListgDt,RmvlDt,FinInstrmTp,SctyTp\n"


class Calendar:
    def is_trading_day(self, value: date) -> bool:
        return value.weekday() < 5


def _mii(day: date):
    body = (HEADERS + f"100,APARINDS,EQ,Exact Ltd,{ISIN},6,100,0,EQ,EQUITY\n").encode()
    return extract_nse_mii_security_master(NseMiiSecurityMasterHttpResponse(
        requested_date=day, source_reference=nse_mii_security_master_url(day), content_type="application/x-gzip",
        body=gzip.compress(body, mtime=0), document_observed_at=T,
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
    session = session_point_identity_from_row(activation=session_activation, snapshot=_mii(AS_OF.date()).snapshot, row=_mii(AS_OF.date()).rows[0])
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
    return company_type.activate_pit_company_type_classifications(activation=policy_active, issuer_observations=(forward,), taxonomy_receipts=(taxonomy,), regulator_links=(), regulator_evidence=(), as_of=AS_OF).receipts[0]


def _instrument() -> InstrumentIdentity:
    return InstrumentIdentity("NSE:" + ISIN, Exchange.NSE, "APARINDS", "APARINDS", ISIN, "EQ", InstrumentType.NSE_EQUITY, "Exact Ltd")


def _period(year: int, quarter: int) -> tuple[datetime, datetime]:
    ends = {1: (6, 30), 2: (9, 30), 3: (12, 31), 4: (3, 31)}
    if quarter == 4:
        return datetime(year, 1, 1, tzinfo=UTC), datetime(year, 3, 31, tzinfo=UTC)
    calendar_year = year - 1
    month, day = ends[quarter]
    return datetime(calendar_year, {1: 4, 2: 7, 3: 10}[quarter], 1, tzinfo=UTC), datetime(calendar_year, month, day, tzinfo=UTC)


def _fact(metric: FinancialMetric, year: int, quarter: int, value: str, *, basis=FinancialValueBasis.QUARTER_ONLY, received: datetime | None = None, filing_id: str | None = None) -> FinancialFact:
    start, end = _period(year, quarter)
    published = end + timedelta(days=10)
    return FinancialFact(
        f"{metric.value}:{year}:Q{quarter}:{value}:{basis.value}", _instrument(), metric, Decimal(value), "INR", "INR", NumericScale.CRORES,
        FinancialPeriodType.QUARTERLY, basis, start, end, year, quarter, StatementScope.CONSOLIDATED,
        FundamentalFactKind.REPORTED, "BSE_OFFICIAL", filing_id or f"filing:{year}:Q{quarter}", "source", published,
        received or published + timedelta(days=1), "bse-official-local-xbrl-v1", ("BSE_OFFICIAL",), (), None,
    )


def _facts(*, revenue=("80", "100", "120", "144"), pat=("8", "10", "12", "14")) -> tuple[FinancialFact, ...]:
    periods = ((2024, 4), (2025, 1), (2025, 4), (2026, 1))
    return tuple(
        _fact(metric, year, quarter, value, filing_id="filing:2026:Q1" if (year, quarter) == (2026, 1) else None)
        for metric, values in ((FinancialMetric.REVENUE, revenue), (FinancialMetric.PAT, pat))
        for (year, quarter), value in zip(periods, values)
    )


def _filing(*, period_end: datetime | None = None, announced: datetime = datetime(2025, 8, 10, 10, tzinfo=UTC)) -> CorporateFiling:
    period = period_end or _period(2026, 1)[1]
    return CorporateFiling(
        "filing:2026:Q1", _instrument(), Exchange.BSE, "BSE_OFFICIAL", PrimarySourceQuality.PRIMARY_EXCHANGE,
        FilingType.FINANCIAL_RESULTS, "financial-results", "Results", announced, announced + timedelta(minutes=1),
        "bse:result:2026:q1", None,
        MarketDataProvenance("BSE_OFFICIAL", None, announced, announced, announced + timedelta(minutes=1), "corporate-filings-v1", source_reference="bse:result:2026:q1"),
        period_end=period, financial_result=FinancialResultMetadata(period, "CONSOLIDATED", "QUARTERLY", False),
    )


def _evaluate(*, facts=None, filings=None, calendar=Calendar()):
    return evaluate_inflection_testable_derived_metrics_and_event_alignment(
        facts=_facts() if facts is None else facts, filings=(_filing(),) if filings is None else filings,
        company_type_receipt=_company_type_receipt(), statement_scope=StatementScope.CONSOLIDATED,
        as_of=AS_OF, calendar=calendar,
    )


def _receipt(value, metric):
    return next(item for item in value.receipts if item.metric is metric)


def test_revenue_and_pat_yoy_acceleration_are_factual_and_deterministic():
    first = _evaluate()
    second = _evaluate(facts=tuple(reversed(_facts())))
    revenue = _receipt(first, InflectionResearchMetric.REVENUE)
    pat = _receipt(first, InflectionResearchMetric.PAT)
    assert revenue.state is pat.state is InflectionDerivedMetricsState.ACCELERATION_OBSERVED
    assert revenue.current_yoy is not None and revenue.current_yoy.relative_delta == Decimal("0.44")
    assert revenue.previous_yoy is not None and revenue.previous_yoy.relative_delta == Decimal("0.5")
    assert revenue.acceleration == Decimal("-0.06")
    assert pat.acceleration == Decimal("-0.1")
    assert first.fingerprint == second.fingerprint == _evaluate().fingerprint
    assert serialize_inflection_testable_derived_metrics(first) == serialize_inflection_testable_derived_metrics(second)


def test_pure_replay_is_idempotent_without_a_receipt_store():
    first = _evaluate()
    replay = _evaluate()
    assert first == replay
    assert first.receipts[0].receipt_id == replay.receipts[0].receipt_id
    assert "app.storage" not in Path(inspect.getfile(module)).read_text(encoding="utf-8")


@pytest.mark.parametrize(("values", "reason"), (
    (("8", "-10", "12", "14"), InflectionDerivedMetricsReason.LOSS_TO_PROFIT),
    (("8", "10", "12", "-14"), InflectionDerivedMetricsReason.PROFIT_TO_LOSS),
    (("8", "-10", "12", "-14"), InflectionDerivedMetricsReason.LOSS_TO_LOSS),
    (("8", "0", "12", "14"), InflectionDerivedMetricsReason.ZERO_BASE),
))
def test_pat_non_positive_base_transitions_are_never_percentage_growth(values, reason):
    result = _evaluate(facts=_facts(pat=values))
    receipt = _receipt(result, InflectionResearchMetric.PAT)
    assert receipt.state is InflectionDerivedMetricsState.NON_COMPARABLE
    assert reason in receipt.reasons and receipt.acceleration is None


def test_missing_t_minus_five_and_basis_change_fail_closed_without_quarter_inference():
    absent = tuple(value for value in _facts() if not (value.metric is FinancialMetric.REVENUE and value.fiscal_year == 2024))
    missing = _receipt(_evaluate(facts=absent), InflectionResearchMetric.REVENUE)
    assert missing.state is InflectionDerivedMetricsState.YOY_OBSERVED
    assert InflectionDerivedMetricsReason.PRIOR_YEAR_PREVIOUS_QUARTER_UNAVAILABLE in missing.reasons
    altered = _facts() + (_fact(FinancialMetric.REVENUE, 2026, 1, "999", basis=FinancialValueBasis.YEAR_TO_DATE, filing_id="filing:2026:Q1"),)
    mismatch = _receipt(_evaluate(facts=altered), InflectionResearchMetric.REVENUE)
    assert mismatch.state is InflectionDerivedMetricsState.NON_COMPARABLE
    assert InflectionDerivedMetricsReason.BASIS_CHANGED in mismatch.reasons


def test_selected_vintage_conflict_is_preserved_as_evidence_conflicted():
    conflict = replace(
        _fact(FinancialMetric.REVENUE, 2026, 1, "999", filing_id="filing:2026:Q1"),
        fact_id="revenue:2026:Q1:conflicting-vintage",
    )
    receipt = _receipt(_evaluate(facts=_facts() + (conflict,)), InflectionResearchMetric.REVENUE)
    assert receipt.state is InflectionDerivedMetricsState.EVIDENCE_CONFLICTED
    assert InflectionDerivedMetricsReason.RESTATEMENT_CONFLICT in receipt.reasons


def test_future_fact_is_excluded_by_pit_and_never_enters_lineage():
    future = replace(_fact(FinancialMetric.REVENUE, 2026, 1, "999", filing_id="filing:2026:Q1"), fact_id="future-current", published_at=AS_OF + timedelta(seconds=1), received_at=AS_OF + timedelta(days=1))
    result = _evaluate(facts=_facts() + (future,))
    receipt = _receipt(result, InflectionResearchMetric.REVENUE)
    assert "future-current" not in {value.fact_id for value in receipt.input_facts}
    assert receipt.current_yoy is not None and receipt.current_yoy.current_value == Decimal("144")


def test_exact_result_filing_lineage_timestamp_and_calendar_date_readiness_are_retained():
    receipt = _receipt(_evaluate(), InflectionResearchMetric.REVENUE)
    assert receipt.filing_lineage.state is FilingLineageState.EXACT_FILING_TIMESTAMP_AVAILABLE
    assert receipt.filing_lineage.filing_id == "filing:2026:Q1"
    assert receipt.filing_lineage.announced_at == datetime(2025, 8, 10, 10, tzinfo=UTC)
    assert receipt.calendar_alignment.state is EventCalendarAlignmentState.NON_TRADING_DATE
    assert receipt.calendar_alignment.prior_trading_session == date(2025, 8, 8)
    assert receipt.calendar_alignment.next_trading_session == date(2025, 8, 11)
    assert receipt.calendar_alignment.intraday_state.value == "INTRADAY_EVENT_SESSION_UNRESOLVED"


def test_filing_period_mismatch_and_missing_calendar_remain_explicitly_unavailable():
    mismatch = _receipt(_evaluate(filings=(_filing(period_end=datetime(2025, 9, 30, tzinfo=UTC)),)), InflectionResearchMetric.REVENUE)
    assert mismatch.filing_lineage.state is FilingLineageState.FILING_PERIOD_MISMATCH
    unavailable = _receipt(_evaluate(calendar=None), InflectionResearchMetric.REVENUE)
    assert unavailable.calendar_alignment.state is EventCalendarAlignmentState.CALENDAR_UNAVAILABLE


def test_missing_filing_timestamp_never_becomes_an_inferred_event_time():
    filing = _filing()
    object.__setattr__(filing, "announced_at", None)
    receipt = _receipt(_evaluate(filings=(filing,)), InflectionResearchMetric.REVENUE)
    assert receipt.filing_lineage.state is FilingLineageState.FILING_TIMESTAMP_MISSING
    assert receipt.calendar_alignment.state is EventCalendarAlignmentState.CALENDAR_UNAVAILABLE


def test_financial_company_is_not_applicable_without_running_nonfinancial_metrics(monkeypatch):
    receipt = _company_type_receipt()
    object.__setattr__(receipt, "company_type", company_type.PitCompanyType.BANK)
    monkeypatch.setattr(module.PitCompanyTypeClassificationReceipt, "verify", lambda self: None)
    result = evaluate_inflection_testable_derived_metrics_and_event_alignment(
        facts=_facts(), filings=(_filing(),), company_type_receipt=receipt,
        statement_scope=StatementScope.CONSOLIDATED, as_of=AS_OF, calendar=Calendar(),
    )
    assert {item.state for item in result.receipts} == {InflectionDerivedMetricsState.NOT_APPLICABLE}
    assert all(InflectionDerivedMetricsReason.NON_FINANCIAL_COMPANY_TYPE_REQUIRED in item.reasons for item in result.receipts)


def test_receipts_are_immutable_and_no_qualification_price_or_volume_surface_exists():
    receipt = _receipt(_evaluate(), InflectionResearchMetric.REVENUE)
    with pytest.raises(FrozenInstanceError):
        receipt.state = InflectionDerivedMetricsState.DATA_INSUFFICIENT  # type: ignore[misc]
    source = Path(inspect.getfile(module)).read_text(encoding="utf-8")
    imports = {item.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for item in node.names} | {node.module or "" for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    assert not any(value.startswith(prefix) for value in imports for prefix in ("app.portfolio", "app.broker", "app.orders", "app.api", "app.signals", "app.storage"))
    forbidden = {"entry", "stop", "target", "quantity", "allocation", "score", "rank", "candidate", "price", "volume"}
    assert not (set(receipt.__dataclass_fields__) & forbidden)
    assert "datetime.now" not in source and "SHADOW_CANDIDATE" not in source


def test_company_type_fingerprint_tamper_is_rejected_before_any_accounting_evaluation():
    receipt = _company_type_receipt()
    object.__setattr__(receipt, "fingerprint", "sha256:" + "0" * 64)
    with pytest.raises(ValueError, match="COMPANY_TYPE_RECEIPT_TAMPERED"):
        evaluate_inflection_testable_derived_metrics_and_event_alignment(
            facts=_facts(), filings=(_filing(),), company_type_receipt=receipt,
            statement_scope=StatementScope.CONSOLIDATED, as_of=AS_OF, calendar=Calendar(),
        )
