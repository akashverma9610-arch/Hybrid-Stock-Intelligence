from dataclasses import FrozenInstanceError, fields, replace
from datetime import timedelta, timezone
from functools import lru_cache
import json
import subprocess
import sys
import ast
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from app.diagnostics.brain_lineage import (
    BrainDiagnosticResearch, CROSS_BRAIN, CROSS_PORTFOLIO, brain_diagnostic_research,
    compare_brain_diagnostics, portfolio_observation, require_production_evidence,
)
from app.diagnostics.downstream import shadow_diagnostic_envelope
from app.domain.models import StrategyVersionReference
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.intelligence.shared_brain_application import SharedBrainApplicationService
from app.intelligence.research_diagnostic_evidence import ResearchDiagnosticEvidenceAdapter
from app.intelligence.unified_state import BrainOutputContext
from app.portfolio.canonical_diagnostics_orchestration import rehydrate_persisted_canonical_diagnostics
from app.portfolio.holding_intelligence import compose_holding_intelligence
from app.portfolio.sell_side_runtime import PortfolioSellSideInput, evaluate_portfolio_sell_side_action
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import RegistryMode, V2_VERSION
from scripts.audit_fundamental_v2_downstream import shadow_fixture
import test_shared_brain_application as brain
import test_holding_intelligence_composition as holding
import test_capital_rotation as rotation
import test_execution_gates as gates
from tests.unit.test_decision_score import complete, score
from tests.unit.test_higher_order_diagnostics import context, complete_context
from app.diagnostics import synthesis

BASELINE = '01593df3d89c57d982f67b25bf8819281474d9ff'


@lru_cache(maxsize=1)
def shadow():
    return shadow_fixture()


def research(values=None, **kwargs):
    values = shadow() if values is None else values
    args = dict(canonical_instrument_id=shadow()[0].canonical_instrument_id,
                as_of=shadow()[0].as_of, diagnostics=values, registry_version=V2_VERSION, mode=RegistryMode.SHADOW)
    return brain_diagnostic_research(**(args | kwargs))


def legacy_diagnostics(instrument='NSE:ALPHA', at=brain.T):
    return tuple(replace(item, record=replace(item.record, instrument_id=instrument,
        strategy_version=StrategyVersionReference('test', 'v1'), as_of_timestamp=at, evaluated_at=at))
        for item in holding._complete_diagnostics())


def legacy_module(path):
    name = '_brain_baseline_' + path.replace('/', '_').replace('.', '_')
    module = ModuleType(name)
    module.__package__ = '.'.join(path.split('/')[:-1])
    sys.modules[name] = module
    exec(compile(subprocess.check_output(['git', 'show', BASELINE+':'+path], text=True), path, 'exec'), module.__dict__)
    return module


def test_default_and_explicit_v1_use_same_existing_brain_and_no_clock():
    service, _, _ = brain._service()
    service._clock = lambda: pytest.fail('runtime clock')
    view = service.analyze_stock('ALPHA', context=BrainOutputContext.DEEP_ANALYSIS, as_of=brain.T)
    a = service.diagnostic_research('ALPHA', as_of=brain.T, diagnostics=legacy_diagnostics())
    b = service.diagnostic_research('ALPHA', as_of=brain.T, diagnostics=legacy_diagnostics(), registry_version=DIAGNOSTIC_REGISTRY_VERSION)
    assert a == b and a.production_brain_fingerprint == view.snapshot_fingerprint
    assert a.mode is RegistryMode.ACTIVE and a.policy_version is None
    assert a.strategy_version == StrategyVersionReference('test','v1')
    old = legacy_module('app/intelligence/shared_brain_application.py')
    prior = old.SharedBrainApplicationService(resolver=service._resolver, evidence_assembler=service._evidence_assembler)
    assert content_fingerprint(prior.analyze_stock('ALPHA',context=BrainOutputContext.DEEP_ANALYSIS,as_of=brain.T)) == content_fingerprint(view)


def test_explicit_v2_uses_no_assembler_resolver_clock_or_paper():
    class NoUse:
        def __getattr__(self, name): pytest.fail(name)
    service = SharedBrainApplicationService(resolver=NoUse(), evidence_assembler=NoUse(), clock=lambda: pytest.fail('clock'), forward_paper_intelligence=NoUse())
    value = service.diagnostic_research(shadow()[0].canonical_instrument_id, as_of=shadow()[0].as_of,
        diagnostics=shadow(), registry_version=V2_VERSION, mode='SHADOW')
    assert value == research() and value.production_brain_fingerprint is None
    assert value.registry_version == V2_VERSION and value.strategy_version is None
    assert value.policy_version == shadow()[0].evaluator_version
    assert tuple(s.source.fingerprint for s in value.sources) == tuple(s.fingerprint for s in shadow())
    assert not value.score_eligible and not value.execution_eligible and not value.portfolio_action_eligible


@pytest.mark.parametrize('mode,version', [('ACTIVE',V2_VERSION),('SHADOW','unknown'),('LATEST_AVAILABLE','unknown'),('ACTIVE','latest')])
def test_unsupported_modes_versions_never_fallback(mode, version):
    with pytest.raises(ValueError): research(mode=mode,registry_version=version)


@pytest.mark.parametrize('value', [None, brain.T.replace(tzinfo=None)])
def test_research_requires_explicit_aware_cutoff(value):
    service, _, _ = brain._service()
    service._clock=lambda: pytest.fail('clock')
    with pytest.raises(ValueError): service.diagnostic_research('ALPHA',as_of=value,diagnostics=legacy_diagnostics())


@pytest.mark.parametrize('values', [(), (None,), (SimpleNamespace(),)])
def test_empty_or_ambiguous_shadow_fails(values):
    with pytest.raises(ValueError): research(values)


def test_cross_registry_both_directions_and_no_newer_substitution():
    with pytest.raises(ValueError,match=CROSS_BRAIN): research(legacy_diagnostics())
    with pytest.raises(ValueError,match=CROSS_BRAIN): research(registry_version=DIAGNOSTIC_REGISTRY_VERSION,mode='ACTIVE')
    with pytest.raises(ValueError): research(shadow() + legacy_diagnostics())
    with pytest.raises(ValueError): research(as_of=shadow()[0].as_of-timedelta(seconds=1))
    with pytest.raises(ValueError): research(as_of=shadow()[0].as_of+timedelta(seconds=1))


@pytest.mark.parametrize('change', [{'canonical_instrument_id':'NSE:OTHER'}, {'canonical_instrument_id':' NSE:A'},
    {'canonical_instrument_id':'NSE:'}, {'production_brain_fingerprint':'forged'}, {'mode':'ACTIVE'}])
def test_exact_identity_and_mode_required(change):
    with pytest.raises(ValueError): research(**change)


@pytest.mark.parametrize('field,value', [('score_eligible',True),('execution_eligible',True),('portfolio_action_eligible',True),
    ('policy_version','other'),('diagnostic_result_fingerprint','tampered'),('fingerprint','tampered'),
    ('strategy_version',StrategyVersionReference('fake','v2')),('purpose','PRODUCTION')])
def test_tampered_or_contradictory_lineage_cannot_be_repaired(field,value):
    with pytest.raises(ValueError): replace(research(),**{field:value})


def test_source_and_supplied_envelope_tamper_rejected_without_mutating_cache():
    item = replace(shadow()[0])
    object.__setattr__(item,'fingerprint','sha256:'+'0'*64)
    with pytest.raises(ValueError,match='FINGERPRINT'): research((item,*shadow()[1:]))
    envelope = shadow_diagnostic_envelope(shadow()[0],as_of=shadow()[0].as_of)
    object.__setattr__(envelope,'policy_version','tampered')
    with pytest.raises(ValueError): research((envelope,*shadow()[1:]))


def test_utc_order_idempotency_serialization_and_sidecar_no_forbidden_fields():
    a=research(); b=research(tuple(reversed(shadow())),as_of=shadow()[0].as_of.astimezone(timezone(timedelta(hours=5,minutes=30))))
    assert a.to_json()==b.to_json()
    payload=json.loads(a.to_json()); fp=payload.pop('fingerprint')
    assert fp==content_fingerprint(payload)
    obs=portfolio_observation(a,holding_reference='existing-holding-reference')
    assert obs.to_json()==portfolio_observation(b,holding_reference='existing-holding-reference').to_json()
    with pytest.raises(FrozenInstanceError): a.mode=RegistryMode.ACTIVE
    with pytest.raises(ValueError): replace(obs,portfolio_action_eligible=True)
    forbidden={'action','allocation','position_size','quantity','entry','stop','target','heat','rotation_recommendation','sell_instruction','profit_harvest_instruction','score'}
    assert not forbidden & {f.name for obj in (a,obs) for f in fields(obj)}


@pytest.mark.parametrize('subset', ['duplicate','missing','conflicting'])
def test_duplicate_missing_conflicting_rule_lineage_rejected(subset):
    values=shadow()
    if subset=='duplicate': values=values+(values[0],)
    elif subset=='missing': values=values[:-1]
    else:
        changed=replace(values[0])
        object.__setattr__(changed,'as_of',values[0].as_of-timedelta(days=1))
        values=(changed,*values[1:])
    with pytest.raises(ValueError): research(values)


def test_comparison_is_deterministic_descriptive_and_context_exact():
    v2=research(); sources=legacy_diagnostics(v2.canonical_instrument_id,v2.as_of)
    v1=brain_diagnostic_research(canonical_instrument_id=v2.canonical_instrument_id,as_of=v2.as_of,
        diagnostics=sources,production_brain_fingerprint='existing-brain-fingerprint')
    text=compare_brain_diagnostics(v1,v2); value=json.loads(text)
    fp=value.pop('fingerprint'); assert fp==content_fingerprint(value)
    assert text==compare_brain_diagnostics(v1,research(tuple(reversed(shadow()))))
    assert len(value['observations'])==6 and not value['portfolio_action_eligible']
    with pytest.raises(ValueError): compare_brain_diagnostics(v2,v1)


def variants():
    r=research()
    return (shadow()[0],r.sources[0],r,portfolio_observation(r))


@pytest.mark.parametrize('index',range(4))
def test_real_production_boundaries_reject_each_shadow_shape(index):
    value=variants()[index]
    h=holding._holding(); p=holding._snapshot(h)
    calls=(
        lambda: compose_holding_intelligence(holding=h,portfolio_snapshot=p,shared_brain=value),
        lambda: compose_holding_intelligence(holding=h,portfolio_snapshot=p,shared_brain=holding._brain(),diagnostics=(value,)),
        lambda: evaluate_portfolio_sell_side_action(value),
        lambda: evaluate_portfolio_sell_side_action(PortfolioSellSideInput(p,replace(h,analytics=value),None,'brain')),
        lambda: rotation.evaluate(value),
        lambda: rotation.evaluate(rotation.context(candidates=(value,))),
        lambda: rotation.evaluate(rotation.context(holdings=(value,))),
        lambda: rehydrate_persisted_canonical_diagnostics((value,),instrument_id='NSE:A',as_of=holding.T),
        lambda: ResearchDiagnosticEvidenceAdapter(SimpleNamespace(list_stored_diagnostic_results=lambda *a,**kw:(value,))).artifacts('NSE:A',as_of=holding.T),
    )
    for call in calls:
        with pytest.raises(ValueError,match='CROSS_REGISTRY'): call()
    from app.intelligence.profit_harvesting_review import evaluate_profit_harvesting_review
    with pytest.raises(ValueError,match='ASSURANCE_REQUIRED'): evaluate_profit_harvesting_review(assurance=value)
    from app.gates.engine import ExecutionGateEngine
    engine=ExecutionGateEngine(None,None)
    with pytest.raises(ValueError,match='V2_SHADOW_GATE'):
        engine.evaluate(instrument_id='NSE:A',strategy_version='v1',registry_version=DIAGNOSTIC_REGISTRY_VERSION,
            scoring_configuration_version='v1',action_context=None,as_of_timestamp=holding.T,evaluated_at=holding.T,inputs=value)
    assert score(complete()+(value,)).final_score is None
    for name in ('risk','trading_thesis','investment_thesis','scenarios'):
        output=getattr(synthesis,name)(context(complete_context().diagnostics+(value,)),synthesis.SynthesisRules())
        assert output.state=='INSUFFICIENT_DATA' and output.confidence is None


def test_pre_gate_rejects_explicit_v2_before_any_gate_and_registry_guard_rejects_unknown_brain():
    from app.gates.engine import ExecutionGateEngine
    with pytest.raises(ValueError,match='V2_SHADOW_GATE'):
        ExecutionGateEngine(None,None).evaluate(instrument_id='NSE:A',strategy_version='v1',registry_version=V2_VERSION,
            scoring_configuration_version='v1',action_context=None,as_of_timestamp=holding.T,evaluated_at=holding.T,inputs=SimpleNamespace())
    with pytest.raises(ValueError,match=CROSS_PORTFOLIO): require_production_evidence(SimpleNamespace(registry_version='unknown'))
    with pytest.raises(ValueError,match=CROSS_PORTFOLIO): require_production_evidence(SimpleNamespace(registry_version=DIAGNOSTIC_REGISTRY_VERSION,mode=RegistryMode.SHADOW))


@pytest.mark.parametrize('state', ['HEALTHY','WEAK','TRIGGERED','INSUFFICIENT_DATA'])
def test_v1_holding_and_sell_outputs_equal_frozen_baseline(state):
    h=holding._holding(); p=holding._snapshot(h); b=holding._brain()
    args=dict(holding=h,portfolio_snapshot=p,shared_brain=b,
        diagnostics=tuple(holding._diagnostic(n,state) for n in (4,6,10,16,17,18,19,23,37,38,41,43,45,46)))
    current=compose_holding_intelligence(**args)
    prior=legacy_module('app/portfolio/holding_intelligence.py').compose_holding_intelligence(**args)
    assert content_fingerprint(current)==content_fingerprint(prior)
    data=PortfolioSellSideInput(p,replace(h,analytics=current.analytics),None,current.shared_brain_fingerprint,
                               current.evidence_conflicted,current.evidence_comparable)
    assert content_fingerprint(evaluate_portfolio_sell_side_action(data))==content_fingerprint(
        legacy_module('app/portfolio/sell_side_runtime.py').evaluate_portfolio_sell_side_action(data))


@pytest.mark.parametrize('kind',['normal','cash_unknown','no_candidate','invalidated'])
def test_v1_rotation_replay_unchanged(kind):
    ctx=rotation.context()
    if kind=='cash_unknown': ctx=rotation.context(cash=None,cash_state='UNKNOWN')
    if kind=='no_candidate': ctx=rotation.context(candidates=())
    if kind=='invalidated': ctx=rotation.context(holdings=(rotation.holding(invalidation='TRIGGERED'),))
    before=legacy_module('app/rotation/engine.py').CapitalRotationEngine(rotation.CONFIG).evaluate(ctx,rotation.ASOF)
    after=rotation.evaluate(ctx)
    assert content_fingerprint(before)==content_fingerprint(after)


def test_v1_unavailable_brain_is_retained_as_unavailable_not_fabricated(monkeypatch):
    service,_,_=brain._service()
    def unavailable(*args,**kwargs):
        from app.intelligence.shared_brain_application import SharedBrainApplicationError
        raise SharedBrainApplicationError('SHARED_BRAIN_SNAPSHOT_UNAVAILABLE','Unavailable')
    monkeypatch.setattr(service,'analyze_stock',unavailable)
    value=service.diagnostic_research('ALPHA',as_of=brain.T,diagnostics=legacy_diagnostics())
    assert value.production_brain_fingerprint is None
    assert value.production_brain_blocker=='SHARED_BRAIN_SNAPSHOT_UNAVAILABLE'
    assert not value.portfolio_action_eligible
    with pytest.raises(ValueError): replace(value,production_brain_fingerprint='invented')
    with pytest.raises(ValueError): replace(value,production_brain_blocker=None)


@pytest.mark.parametrize('field',['allocation','heat','position_size','structural_stop','invalidation_status','trading_thesis'])
def test_research_context_has_no_action_or_economic_channels(field):
    value=portfolio_observation(research())
    assert not hasattr(value,field) and not hasattr(value.research,field)
    with pytest.raises(TypeError): replace(value,**{field:'forbidden'})


def test_shadow_analytics_rejected_before_any_portfolio_ledger_work():
    from app.portfolio.engine import PortfolioEngine
    with pytest.raises(ValueError,match=CROSS_PORTFOLIO):
        PortfolioEngine(None).reconstruct(portfolio=None,as_of_timestamp=holding.T,initial_cash=None,
            transactions=(),actions=(),prices=(),analytics=(portfolio_observation(research()),))


def test_v1_raw_records_rehydrate_identically_and_tampered_canonical_fails():
    from app.domain.canonical_diagnostic_strategy import CANONICAL_61_SEMANTIC_FINGERPRINT,CANONICAL_61_STRATEGY_REFERENCE
    from app.domain.models import canonical_diagnostic_result
    records=tuple(item.record for item in legacy_diagnostics())
    kwargs=dict(instrument_id='NSE:ALPHA',as_of=brain.T)
    before=legacy_module('app/portfolio/canonical_diagnostics_orchestration.py').rehydrate_persisted_canonical_diagnostics(records,**kwargs)
    after=rehydrate_persisted_canonical_diagnostics(records,**kwargs)
    assert content_fingerprint(before)==content_fingerprint(after)
    r=canonical_diagnostic_result(id='canonical',instrument_id='NSE:ALPHA',rule_id='16',strategy_version=CANONICAL_61_STRATEGY_REFERENCE,
        canonical_strategy_fingerprint=CANONICAL_61_SEMANTIC_FINGERPRINT,canonical_limitations_fingerprint='sha256:'+'1'*64,
        result='INSUFFICIENT_DATA',score=None,confidence=None,evidence_ids=(),input_observation_ids=(),evaluated_at=brain.T,as_of_timestamp=brain.T)
    with pytest.raises(ValueError,match='LINEAGE'): rehydrate_persisted_canonical_diagnostics((replace(r,result='STRONG'),),**kwargs)
    with pytest.raises(ValueError,match='LINEAGE'): rehydrate_persisted_canonical_diagnostics((replace(records[0],diagnostic_fingerprint='fake'),),**kwargs)


def test_current_source_boundary_and_preserved_policy_files():
    permitted={'app/diagnostics/brain_lineage.py','app/intelligence/shared_brain_application.py',
        'app/intelligence/research_diagnostic_evidence.py','app/portfolio/canonical_diagnostics_orchestration.py',
        'app/portfolio/holding_intelligence.py','app/portfolio/sell_side_runtime.py','app/portfolio/engine.py',
        'app/rotation/engine.py','app/gates/engine.py'}
    # B07's immutable source scope remains pinned to its completed checkpoint.
    # The successor B08 tests independently pin its exact production edit set.
    changed=set(subprocess.check_output(['git','diff',BASELINE,'c182b6421303f5f1cb8df3517be36872e72d5602','--name-only','--','app'],text=True).splitlines())
    assert changed<=permitted
    for path in ('app/scoring/engine.py','app/diagnostics/downstream.py','app/diagnostics/synthesis.py',
                 'app/portfolio/sell_side_policy.py','app/gates/production_policy.py','app/rotation/models.py',
                 'app/intelligence/shared_brain_production.py','app/intelligence/unified_state.py'):
        assert Path(path).read_text(encoding='utf-8')==subprocess.check_output(['git','show',BASELINE+':'+path],text=True)
    tree=ast.parse(Path('app/diagnostics/brain_lineage.py').read_text())
    imports=[node.module or '' for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
    assert not any(x.startswith(('app.portfolio','app.storage','app.api','app.runtime','app.providers','app.gates','app.rotation')) for x in imports)
    calls=[ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node,ast.Call)]
    assert not any(x in calls for x in ('datetime.now','datetime.utcnow','open','sqlite3.connect','requests.get','requests.post'))
    old=ast.parse(subprocess.check_output(['git','show',BASELINE+':app/gates/engine.py'],text=True))
    new=ast.parse(Path('app/gates/engine.py').read_text())
    def policies(t):
        engine=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=='ExecutionGateEngine')
        return {x.name:ast.dump(x,include_attributes=False) for x in engine.body if isinstance(x,ast.FunctionDef) and x.name not in {'evaluate','__init__'}}
    assert policies(old)==policies(new)


def test_stored_proof_receipt_integrity_and_truthful_unavailable_baseline():
    receipt=json.loads(Path('docs/architecture/FUNDAMENTAL_V2_BRAIN_PORTFOLIO_COMPARISON_RECEIPT.json').read_text())
    fp=receipt.pop('fingerprint'); assert fp==content_fingerprint(receipt)
    assert receipt['writes']==receipt['provider_calls']==receipt['production_action_evaluations']==0
    assert receipt['portfolio_unchanged'] and receipt['v1_active'] and not receipt['v2_active']
    assert len(receipt['comparisons'])==5
    for row in receipt['comparisons']:
        value=row['comparison'].copy(); fingerprint=value.pop('fingerprint')
        assert fingerprint==content_fingerprint(value)
        assert value['v1_registry']==DIAGNOSTIC_REGISTRY_VERSION and value['v2_registry']==V2_VERSION
        assert len(value['observations'])==6
        assert not any(value[k] for k in ('score_eligible','execution_eligible','portfolio_action_eligible'))
        assert row['v1_boundary_unchanged'] and len(row['rejections'])==6
        if row['v1_preexisting_failure']:
            assert value['v1_production_fingerprint'] is None and row['v1_holding_composition_unchanged'] is None
            assert value['v1_production_blocker']=='SHARED_BRAIN_SNAPSHOT_UNAVAILABLE'
        else:
            assert value['v1_production_fingerprint'] and row['v1_holding_composition_unchanged']
