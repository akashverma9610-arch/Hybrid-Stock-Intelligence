from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.fundamentals import FundamentalRules
from app.config.freshness import FreshnessPolicyConfig
from app.diagnostics.evaluators import DeterministicDiagnosticEvaluators
from app.domain.models import AsOfSnapshot, DataQuality, Instrument, MarketObservation, ObservationKind, Provenance
from app.services.foundation_service import FoundationService
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.validation.freshness import FreshnessEngine
from app.validation.observation_validator import ObservationValidator
from tests.fixtures.analytical_observations import STRATEGY_REFERENCE
from tests.fixtures.fundamental_observations import FUNDAMENTAL_SCENARIOS

AS_OF=datetime(2026,8,5,tzinfo=UTC); RULES=FundamentalRules(.1,-.1,.12,1.5,2,.02)


def test_mock_fundamental_fixture_catalog_is_complete_and_deterministic():
    assert len(FUNDAMENTAL_SCENARIOS) == 27
    assert FUNDAMENTAL_SCENARIOS == tuple(FUNDAMENTAL_SCENARIOS)

def _filing(identifier, period_end, published, kind, factor=1, **extra):
    values={"period_end":period_end.isoformat(),"publication_timestamp":published.isoformat(),"period_type":kind,"revenue":100*factor,"cogs":60*factor,"ebitda":20*factor,"pat":12*factor,"eps":6*factor,"gross_profit":40*factor,"operating_cash_flow":15*factor,"capex":5*factor,"total_equity":100*factor,"total_debt":40*factor,"cash":10*factor,"interest_expense":4,"ebit":18*factor,"total_assets":180*factor,"current_assets":80*factor,"current_liabilities":40*factor,"inventory":10*factor,"receivables":20*factor,"payables":15*factor,"promoter_holding":55+factor,"promoter_pledge":max(0,5-factor),"fii_holding":10+factor,"dii_holding":8+factor,"mutual_fund_holding":6+factor,"order_book":200*factor,"order_inflow":120*factor,**extra}
    return MarketObservation(identifier,Instrument("stock","STOCK","MOCK"),ObservationKind.FUNDAMENTAL,values,Provenance("mock-filing",identifier,published,published,DataQuality.HIGH))

def _snapshots(tmp_path):
    repo=SQLiteStrategyGovernanceRepository(tmp_path/"financial.db")
    service=FoundationService(repo,ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.FUNDAMENTAL:timedelta(days=10000)},timedelta(days=10000)))))
    published=AS_OF-timedelta(days=1)
    records=[]
    for i in range(6): records.append(_filing(f"annual-{i}",datetime(2020+i,3,31,tzinfo=UTC),published,"annual",i+1))
    for i, (year, month) in enumerate(((2025,3),(2025,6),(2025,9),(2025,12),(2026,3))): records.append(_filing(f"quarter-{i}",datetime(year,month,28,tzinfo=UTC),published,"quarterly",i+1))
    for item in records: service.ingest(item,evaluated_timestamp=AS_OF+timedelta(days=30))
    before=service.build_as_of_snapshot(as_of_timestamp=AS_OF)
    future=_filing("future-publication",datetime(2026,6,30,tzinfo=UTC),AS_OF+timedelta(days=5),"quarterly",100)
    service.ingest(future,evaluated_timestamp=AS_OF+timedelta(days=30))
    return repo,before,service.build_as_of_snapshot(as_of_timestamp=AS_OF),future

def _evaluate(rule,snapshot):
    e=DeterministicDiagnosticEvaluators(); args=(snapshot,"stock",STRATEGY_REFERENCE,RULES,AS_OF)
    return {16:e.financial_trend,17:e.return_ratios,18:e.cash_flow,19:e.leverage,20:e.working_capital,21:e.ownership,22:e.institutional_holdings,24:e.earnings_acceleration,25:e.latest_quarter,26:e.margin_trajectory,27:e.order_book}[rule](*args)

@pytest.mark.parametrize("rule",(16,17,18,19,20,21,22,24,25,26,27))
def test_each_financial_rule_excludes_a_result_published_after_its_as_of_time(tmp_path,rule):
    repo,before,after,future=_snapshots(tmp_path)
    first,second=_evaluate(rule,before),_evaluate(rule,after)
    assert first==second
    assert first.record.input_observation_ids==second.record.input_observation_ids
    assert first.record.evidence_ids==second.record.evidence_ids
    assert first.record.confidence==second.record.confidence
    assert future.id not in repr(first)
    repo.close()

def test_restatement_is_append_only_and_reproduces_what_was_known_at_each_as_of_time(tmp_path):
    repo,before,_,_= _snapshots(tmp_path)
    original=next(x for x in before.observations if x.id=="annual-5")
    restated=_filing("annual-5-restated",datetime(2025,3,31,tzinfo=UTC),AS_OF+timedelta(days=10),"annual",99,supersedes_observation_id=original.id)
    service=FoundationService(repo,ObservationValidator(FreshnessEngine(FreshnessPolicyConfig({ObservationKind.FUNDAMENTAL:timedelta(days=10000)},timedelta(days=10000)))))
    service.ingest(restated,evaluated_timestamp=AS_OF+timedelta(days=30))
    historical=service.build_as_of_snapshot(as_of_timestamp=AS_OF)
    later=service.build_as_of_snapshot(as_of_timestamp=AS_OF+timedelta(days=10))
    assert original.id in {x.id for x in historical.observations}
    assert restated.id not in {x.id for x in historical.observations}
    assert {original.id,restated.id}.issubset({x.id for x in later.observations})
    repo.close()


def test_ccc_uses_average_receivables_and_cogs_for_inventory_payables(tmp_path):
    repo,before,_,_=_snapshots(tmp_path); result=_evaluate(20,before); d=dict(result.details)
    assert float(d["receivable_days"]) == pytest.approx((110/600)*365)
    assert float(d["inventory_days"]) == pytest.approx((55/360)*365)
    assert float(d["payable_days"]) == pytest.approx((82.5/360)*365)
    assert float(d["ccc"]) == pytest.approx(float(d["receivable_days"])+float(d["inventory_days"])-float(d["payable_days"]))
    assert d["receivable_basis"] == "average beginning/end balance"; repo.close()


def test_missing_cogs_preserves_dso_and_marks_other_ccc_components_partial(tmp_path):
    repo,before,_,_=_snapshots(tmp_path)
    rows=tuple(replace(item,payload={k:v for k,v in item.payload.items() if k!="cogs"}) if item.id=="annual-5" else item for item in before.observations)
    result=_evaluate(20,AsOfSnapshot("no-cogs",AS_OF,AS_OF,"fixture",rows)); d=dict(result.details)
    assert result.record.result == "PARTIAL" and "UNAVAILABLE" in d["inventory_days"] and d["ccc"].startswith("PARTIAL")
    repo.close()


@pytest.mark.parametrize(("method","expected"),(("equity_debt_cash_v1",108/715),("assets_current_liabilities_v1",108/770)))
def test_roce_methods_are_explicit_and_use_average_capital(tmp_path,method,expected):
    repo,before,_,_=_snapshots(tmp_path); configured=FundamentalRules(.1,-.1,.12,1.5,2,.02,method)
    result=DeterministicDiagnosticEvaluators().return_ratios(before,"stock",STRATEGY_REFERENCE,configured,AS_OF); d=dict(result.details)
    assert float(d["roce"]) == pytest.approx(expected)
    assert d["roce_method"] == method and d["capital_basis"] == "average beginning/end capital employed"
    repo.close()


def test_missing_configured_roce_denominator_is_insufficient_and_deterministic(tmp_path):
    repo,before,_,_=_snapshots(tmp_path)
    rows=tuple(replace(item,payload={k:v for k,v in item.payload.items() if k!="total_assets"}) if item.id=="annual-5" else item for item in before.observations)
    configured=FundamentalRules(.1,-.1,.12,1.5,2,.02,"assets_current_liabilities_v1")
    data=AsOfSnapshot("missing-assets",AS_OF,AS_OF,"fixture",rows); e=DeterministicDiagnosticEvaluators()
    assert e.return_ratios(data,"stock",STRATEGY_REFERENCE,configured,AS_OF) == e.return_ratios(data,"stock",STRATEGY_REFERENCE,configured,AS_OF)
    assert e.return_ratios(data,"stock",STRATEGY_REFERENCE,configured,AS_OF).record.result == "INSUFFICIENT_DATA"
    repo.close()
