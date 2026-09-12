"""Synthetic canonical facts only; no production/provider/score integration."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal, localcontext
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.diagnostics.synthesis import HigherOrderDiagnosticContext, investment_thesis, SynthesisRules
from app.fundamentals.diagnostic_comparability import content_fingerprint, ComparabilityState as S
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.diagnostic_v2_shadow import FundamentalDiagnosticV2ShadowEvaluator, ShadowEntity as E
from app.registry.canonical import DIAGNOSTIC_RULES, DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import resolve_diagnostic_registry, RegistryMode, V2_VERSION, V2_RULE_IDS
from app.scoring.engine import build_scorecard
from tests.unit.test_financial_diagnostic_comparability import (
    fact, comparable, company, market, quarter_facts, M, B, T, ID, Scope, Scale,
)


def annual():
    return tuple(fact(m, year=y, value=100 + (y-2021)*10)
        for y in range(2021, 2027) for m in (M.REVENUE, M.PAT, M.EPS_BASIC))


def facts():
    return annual() + quarter_facts((M.REVENUE, M.PAT, M.EPS_BASIC)) + (
        fact(M.TOTAL_EQUITY, year=2025, balance=True, value=1000),
        fact(M.TOTAL_EQUITY, balance=True, value=2000), fact(M.TOTAL_DEBT, balance=True, value=200))


def evaluate(values=None, *, entity=E.NON_FINANCIAL, classified=True, prices=True, as_of=T):
    data = CanonicalFinancialDiagnosticInput(comparable(facts() if values is None else values, as_of=as_of), company() if classified else None)
    return FundamentalDiagnosticV2ShadowEvaluator().evaluate(data, registry_version=V2_VERSION,
        as_of=as_of, entity_type=entity, market=market(as_of=as_of) if prices else None)


def rule(values, number):
    return next(r for r in values if r.rule_id == number)


def component(value, name):
    return next(c for c in value.component_states if c.component_id == name)


def test_default_explicit_v1_and_exact_six_changed_definitions():
    default = resolve_diagnostic_registry()
    assert default.registry_version == DIAGNOSTIC_REGISTRY_VERSION
    assert default.rules is DIAGNOSTIC_RULES
    assert default == resolve_diagnostic_registry(DIAGNOSTIC_REGISTRY_VERSION)
    shadow = resolve_diagnostic_registry(V2_VERSION, mode=RegistryMode.SHADOW)
    assert [r.rule_id for r in default.rules] == [r.rule_id for r in shadow.rules] == list(range(1, 62))
    assert tuple(a.rule_id for a,b in zip(default.rules,shadow.rules) if a != b) == V2_RULE_IDS
    assert all(a is b for a,b in zip(default.rules,shadow.rules) if a.rule_id not in V2_RULE_IDS)
    assert shadow.fingerprint == resolve_diagnostic_registry(V2_VERSION, mode="SHADOW").fingerprint


@pytest.mark.parametrize("version,mode,error", [(V2_VERSION,"ACTIVE","V2_REGISTRY_NOT_ACTIVE"),
    ("latest","SHADOW","REGISTRY_VERSION_UNKNOWN"),(None,"SHADOW","REGISTRY_VERSION_UNKNOWN"),
    (V2_VERSION,"production","REGISTRY_MODE_UNKNOWN")])
def test_version_mode_fail_closed(version,mode,error):
    with pytest.raises(ValueError,match=error): resolve_diagnostic_registry(version,mode=mode)


def test_all_six_nonfinancial_core_measurements_without_ebitda_and_no_verdict():
    rows=evaluate()
    assert tuple(r.rule_id for r in rows)==V2_RULE_IDS
    assert all(r.core_state is S.READY for r in rows)
    assert all(r.classification_state is S.POLICY_BLOCKED for r in rows)
    assert all(r.optional_coverage=="INCOMPLETE" for r in rows)
    assert all(r.score_eligible is False and r.execution_eligible is False and r.shadow_only is True for r in rows)
    assert all(r.actionability=="WATCH_ONLY" and r.execution_status=="NON_EXECUTABLE" and r.confidence is None for r in rows)
    assert dict(component(rule(rows,17),"ROE").measurements)["ROE"]==Decimal("0.1")
    assert dict(component(rule(rows,19),"DEBT_EQUITY").measurements)["DEBT_EQUITY"]==Decimal("0.1")


@pytest.mark.parametrize("entity", [E.BANK,E.NBFC,E.INSURER,E.UNKNOWN_NON_COMPARABLE,None])
def test_unsupported_or_missing_entity_never_defaults_to_nonfinancial(entity):
    rows=evaluate(entity=entity,classified=False)
    assert all(r.core_state is S.POLICY_BLOCKED for r in rows)
    assert all(c.state is S.POLICY_BLOCKED and not c.measurements for r in rows for c in r.component_states)


def test_unverified_nonfinancial_label_is_not_canonical_evidence():
    assert all(r.core_state is S.POLICY_BLOCKED for r in evaluate(classified=False))


def test_rule16_requires_six_consecutive_full_years_and_exact_three_metrics():
    assert rule(evaluate(annual()),16).core_state is S.READY
    five=tuple(f for f in annual() if f.fiscal_year!=2021)
    assert rule(evaluate(five),16).core_state is S.INSUFFICIENT_DATA
    gap=tuple(f for f in annual() if f.fiscal_year!=2024)
    assert rule(evaluate(gap),16).core_state is S.INSUFFICIENT_DATA
    partial=tuple(f for f in annual() if f.metric is not M.PAT)
    assert rule(evaluate(partial),16).core_state is S.PARTIAL
    assert {c.component_id for c in rule(evaluate(),16).component_states if c.role=="MANDATORY_CORE"}=={"REVENUE_CAGR","PAT_CAGR","EPS_BASIC_CAGR"}


def test_conflict_blocks_only_affected_component_and_keeps_lineage():
    data=annual(); first=data[0]
    conflict=replace(first,fact_id="conflict",filing_id="conflicting-filing",value=Decimal(999))
    result=rule(evaluate(data+(conflict,)),16)
    assert result.core_state is S.EVIDENCE_CONFLICTED
    assert component(result,"REVENUE_CAGR").state is S.EVIDENCE_CONFLICTED
    assert component(result,"PAT_CAGR").state is S.READY
    assert "conflict" in result.input_evidence_ids


def test_rule17_no_ending_equity_fallback_or_roce_substitute():
    data=tuple(f for f in facts() if not(f.metric is M.TOTAL_EQUITY and f.fiscal_year==2025))
    result=rule(evaluate(data+(fact(M.EBIT),)),17)
    assert component(result,"ROE").state is S.INSUFFICIENT_DATA
    assert component(result,"ROCE").state is S.POLICY_BLOCKED
    ready=component(rule(evaluate(),17),"ROE")
    assert len(next(s for s in ready.series if s.metric is M.TOTAL_EQUITY).observations)==2


def test_rule19_core_completeness_not_whole_health_and_cash_is_independent():
    result=rule(evaluate(),19)
    assert result.core_state is S.READY and result.optional_coverage=="INCOMPLETE"
    net=component(result,"NET_DEBT")
    assert "DIRECT_COMPARABLE_METRIC_MISSING" in net.reasons
    assert net.state is S.POLICY_BLOCKED  # debt/cash boundary itself is not yet approved
    richer=rule(evaluate(facts()+(fact(M.CASH_AND_EQUIVALENTS,balance=True),fact(M.EBIT),fact(M.FINANCE_COST))),19)
    assert component(richer,"NET_DEBT").state is S.POLICY_BLOCKED
    assert component(richer,"INTEREST_COVERAGE").state is S.POLICY_BLOCKED
    assert "HEALTHY" not in richer.to_json() and "DSCR" not in {c.component_id for c in richer.component_states}


@pytest.mark.parametrize("metric,value", [(M.REVENUE,0),(M.PAT,-1),(M.EPS_BASIC,0)])
def test_rule25_unsafe_comparison_sign_or_zero_is_not_ready(metric,value):
    data=tuple(replace(f,value=Decimal(value)) if f.metric is metric and f.fiscal_quarter==4 else f for f in quarter_facts((M.REVENUE,M.PAT,M.EPS_BASIC)))
    assert rule(evaluate(data),25).core_state is S.PARTIAL


def test_rule25_ytd_not_quarter_and_no_retreat_or_partial_core_promotion():
    data=quarter_facts((M.REVENUE,M.PAT,M.EPS_BASIC))
    changed=tuple(replace(f,value_basis=B.YEAR_TO_DATE) if f.fiscal_quarter==3 else f for f in data)
    assert rule(evaluate(changed),25).core_state is S.INSUFFICIENT_DATA
    assert rule(evaluate(tuple(f for f in data if f.metric is not M.PAT)),25).core_state is S.PARTIAL
    assert rule(evaluate(data+(fact(M.REVENUE,year=2026,quarter=2),)),25).core_state is not S.READY


def test_rule26_signed_net_margin_exact_label_difference_and_no_legacy_threshold():
    data=tuple(replace(f,value=Decimal(-10)) if f.metric is M.PAT else f for f in quarter_facts((M.REVENUE,M.PAT)))
    result=rule(evaluate(data),26); net=component(result,"NET_PROFIT_MARGIN")
    assert net.state is S.READY
    values=dict(net.measurements)
    assert values["NET_PROFIT_MARGIN"]<0
    assert "NET_PROFIT_MARGIN_YOY_PERCENTAGE_POINTS" in values
    assert "POLICY_BLOCKED_THRESHOLD_NOT_APPROVED" in result.blockers
    for name in ("OPERATING_MARGIN","GROSS_MARGIN","ISSUER_EBITDA_MARGIN"):
        assert component(result,name).state is S.POLICY_BLOCKED
        assert not component(result,name).measurements
    assert result.classification_state is S.POLICY_BLOCKED


def test_rule29_only_reuses_canonical_pe_and_independent_policy_gated_multiples():
    result=rule(evaluate((fact(M.EPS_BASIC,value=5),)),29)
    assert component(result,"PE").measurements==(("PE",Decimal("20.0")),)
    for name in ("PB","EV_EBITDA","FORWARD_PE","PEG"):
        assert component(result,name).state is S.POLICY_BLOCKED
        assert not component(result,name).measurements
    assert rule(evaluate((fact(M.EPS_BASIC,value=5),),prices=False),29).core_state is S.INSUFFICIENT_DATA
    assert "ATTRACTIVE" not in result.to_json()


@pytest.mark.parametrize("case", ["future_fact","future_price","different_asof","wrong_units","source_cap"])
def test_canonical_pit_comparability_and_price_boundary(case):
    data=facts(); prices=market(); asof=T
    if case=="future_fact": data=tuple(replace(f,published_at=T+timedelta(days=1),received_at=T+timedelta(days=1)) if f.metric is M.PAT else f for f in data)
    if case=="future_price": prices=market(received=T+timedelta(seconds=1))
    if case=="different_asof": asof=T+timedelta(seconds=1)
    if case=="wrong_units": data=tuple(replace(f,scale=Scale.CRORES) if f.metric is M.TOTAL_EQUITY else f for f in data)
    financial=CanonicalFinancialDiagnosticInput(comparable(data,complete_input=case!="source_cap"),company())
    if case=="different_asof":
        with pytest.raises(ValueError,match="ASOF"): FundamentalDiagnosticV2ShadowEvaluator().evaluate(financial,registry_version=V2_VERSION,as_of=asof,entity_type=E.NON_FINANCIAL)
        return
    rows=FundamentalDiagnosticV2ShadowEvaluator().evaluate(financial,registry_version=V2_VERSION,as_of=T,entity_type=E.NON_FINANCIAL,market=prices)
    target=29 if case=="future_price" else 17 if case=="wrong_units" else 16
    assert rule(rows,target).core_state is not S.READY


def test_immutability_determinism_utc_decimal_context_and_tamper_rejection():
    first=evaluate()
    with localcontext() as ctx:
        ctx.prec=7
        second=evaluate(tuple(reversed(facts())),as_of=T.astimezone(timezone(timedelta(hours=5,minutes=30))))
    assert tuple(r.to_json() for r in first)==tuple(r.to_json() for r in second)
    for r in first:
        assert json.loads(r.to_json())["fingerprint"]==r.fingerprint
        with pytest.raises(FrozenInstanceError): r.core_state=S.READY
        with pytest.raises(ValueError,match="FINGERPRINT"): replace(r,fingerprint="sha256:"+"0"*64)
        with pytest.raises(ValueError,match="AUTHORITY"): replace(r,score_eligible=True)
    data=CanonicalFinancialDiagnosticInput(comparable(facts()),company())
    object.__setattr__(data.comparable.observations[0],"value",Decimal(999))
    with pytest.raises(ValueError,match="FINGERPRINT"):
        FundamentalDiagnosticV2ShadowEvaluator().evaluate(data,registry_version=V2_VERSION,as_of=T,entity_type=E.NON_FINANCIAL)


def test_actual_score_and_higher_order_entries_fail_closed_with_safety_adapter():
    rows=evaluate()
    score=build_scorecard(instrument_id=ID,strategy_version=SimpleNamespace(strategy_id="fixture",version="v1"),
        registry_version=V2_VERSION,as_of_timestamp=T,evaluated_at=T,diagnostics=rows)
    assert score.final_score is None and 'V2_SHADOW_SCORE_FORBIDDEN' in score.warnings
    context=HigherOrderDiagnosticContext(T,None,V2_VERSION,rows,"v1")
    result=investment_thesis(context,SynthesisRules())
    assert result.state=='INSUFFICIENT_DATA'
    assert dict(result.details)['blocker']=='CROSS_REGISTRY_DIAGNOSTIC_CONSUMPTION_FORBIDDEN'
    with pytest.raises(ValueError,match="CONSUMER_FORBIDDEN"): rows[0].record


def test_new_evaluator_has_no_clock_provider_storage_score_or_execution_dependencies():
    path=Path('app/fundamentals/diagnostic_v2_shadow.py')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    imports={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert not any(m.startswith(('app.portfolio','app.storage','app.api','app.scoring','app.signals','app.runtime','app.broker')) for m in imports)
    calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    assert not calls & {'now','utcnow','connect','execute','save','write_text','submit_order'}


@pytest.mark.parametrize("mutation", ["fingerprint", "rehash", "active"])
def test_resolver_rejects_modified_proposal_or_approval_even_with_a_new_self_hash(monkeypatch,mutation):
    original=Path.read_text
    def read(path,*args,**kwargs):
        text=original(path,*args,**kwargs)
        if path.name=='FUNDAMENTAL_DIAGNOSTIC_REGISTRY_V2_GOVERNANCE_APPROVAL.json':
            value=json.loads(text)
            value['active']=True
            if mutation=='rehash':
                value['approval_fingerprint']=content_fingerprint({k:v for k,v in value.items() if k!='approval_fingerprint'})
            text=json.dumps(value)
        return text
    monkeypatch.setattr(Path,'read_text',read)
    with pytest.raises(ValueError,match='GOVERNANCE_FINGERPRINT'):
        resolve_diagnostic_registry(V2_VERSION,mode='SHADOW')
    assert resolve_diagnostic_registry().rules is DIAGNOSTIC_RULES


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "role", "blockers", "execution"])
def test_result_rejects_rehashed_schema_and_authority_contradictions(mutation):
    from app.fundamentals.diagnostic_v2_shadow import _payload, FundamentalV2ShadowResult
    result=rule(evaluate(),19); values=_payload(result)
    if mutation=='duplicate': values['component_states'] += (values['component_states'][0],)
    elif mutation=='missing': values['component_states']=values['component_states'][:-1]
    elif mutation=='role':
        old=values['component_states'][0]; new=_payload(old); new['role']='OPTIONAL_COMPONENT'
        replacement=type(old)(**new,fingerprint=content_fingerprint(new))
        values['component_states']=(replacement,)+values['component_states'][1:]
    elif mutation=='blockers': values['blockers']=('OTHER_REASON',)
    elif mutation=='execution': values['execution_eligible']=True
    with pytest.raises(ValueError): FundamentalV2ShadowResult(**values,fingerprint=content_fingerprint(values))


def test_conflicting_optional_cash_cannot_disappear_behind_policy_unavailability():
    cash=fact(M.CASH_AND_EQUIVALENTS,balance=True)
    duplicate=replace(cash,fact_id='cash-conflict',filing_id='cash-filing-conflict',value=Decimal(999))
    result=rule(evaluate(facts()+(cash,duplicate)),19)
    assert result.core_state is S.READY
    assert result.optional_coverage=='CONFLICTED'
    assert component(result,'NET_DEBT').state is S.EVIDENCE_CONFLICTED
    assert 'COMPONENT_POLICY_NOT_APPROVED:NET_DEBT' in result.blockers


def test_positive_eps_cannot_use_scaled_or_future_market_input():
    scaled=fact(M.EPS_BASIC,value=5,scale=Scale.CRORES)
    result=rule(evaluate((scaled,)),29)
    assert component(result,'PE').state is S.INSUFFICIENT_DATA
    assert 'PRICE_EPS_RAW_INR_UNIT_ALIGNMENT_REQUIRED' in result.blockers


def test_governed_financial_company_receipt_still_has_no_standard_branch():
    from tests.unit.test_pit_company_type_classification_activation import _forward,_regulator,_raw_link,_report,regulator_source
    forward=_forward()
    raw=_regulator(source=regulator_source.RegulatorEvidenceSource('RBI_SCHEDULED_COMMERCIAL_BANKS'),
        kind=regulator_source.RegulatorEntityEvidenceKind('SCHEDULED_COMMERCIAL_BANK'),cin=forward.cin)
    receipt=_report(forward=forward,links=(_raw_link(forward,raw),),evidence=(raw,)).receipts[0]
    financial=CanonicalFinancialDiagnosticInput(comparable(facts()),receipt)
    rows=FundamentalDiagnosticV2ShadowEvaluator().evaluate(financial,registry_version=V2_VERSION,as_of=T,entity_type=E.BANK)
    assert all(r.core_state is S.POLICY_BLOCKED and r.entity_fingerprint==receipt.fingerprint for r in rows)
    mismatch=FundamentalDiagnosticV2ShadowEvaluator().evaluate(financial,registry_version=V2_VERSION,as_of=T,entity_type=E.NON_FINANCIAL)
    assert all(r.core_state is S.POLICY_BLOCKED and 'GOVERNED_ENTITY_TYPE_MISMATCH' in r.blockers for r in mismatch)


def test_rule17_negative_pat_descriptive_but_nonpositive_average_equity_unavailable():
    negative=tuple(replace(f,value=Decimal(-100)) if f.metric is M.PAT else f for f in facts())
    result=rule(evaluate(negative),17)
    assert component(result,'ROE').state is S.READY
    assert dict(component(result,'ROE').measurements)['ROE']<0
    zero=tuple(replace(f,value=Decimal(0)) if f.metric is M.TOTAL_EQUITY else f for f in facts())
    assert component(rule(evaluate(zero),17),'ROE').state is S.INSUFFICIENT_DATA


def test_no_scope_or_net_worth_substitution_for_equity():
    data=tuple(replace(f,statement_scope=Scope.STANDALONE) if f.metric is M.TOTAL_EQUITY else f for f in facts())
    assert rule(evaluate(data),17).core_state is S.INSUFFICIENT_DATA
    data=tuple(replace(f,metric=M.NET_WORTH) if f.metric is M.TOTAL_EQUITY else f for f in facts())
    assert rule(evaluate(data),19).core_state is S.INSUFFICIENT_DATA


def test_explicit_service_version_unknown_entity_and_naive_time_rejected():
    financial=CanonicalFinancialDiagnosticInput(comparable(facts()),company())
    evaluator=FundamentalDiagnosticV2ShadowEvaluator()
    with pytest.raises(ValueError,match='EXPLICIT_VERSION'):
        evaluator.evaluate(financial,registry_version=DIAGNOSTIC_REGISTRY_VERSION,as_of=T,entity_type=E.NON_FINANCIAL)
    with pytest.raises(ValueError,match='ENTITY_UNKNOWN'):
        evaluator.evaluate(financial,registry_version=V2_VERSION,as_of=T,entity_type='sector-guessed')
    with pytest.raises(ValueError,match='ASOF'):
        evaluator.evaluate(financial,registry_version=V2_VERSION,as_of=T.replace(tzinfo=None),entity_type=E.NON_FINANCIAL)
