"""Replay pinned pre-repair outputs and exercise real downstream entry points."""
import ast
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.analysis.models import AnalysisStatus
from app.diagnostics import synthesis as s
from app.diagnostics.downstream import (
    CROSS_REGISTRY, ScoreInputClassification, ScoreInputState as S,
    V1_SYNTHESIS_STATES, classify_score_input, shadow_diagnostic_envelope,
)
from app.diagnostics.models import EvaluationEligibility
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION as V1
from app.registry.versioned import RegistryMode, V2_VERSION, resolve_diagnostic_registry
from app.scoring.engine import BASE_STATE_SCORES, COMPONENTS, build_scorecard
from tests.unit.test_decision_score import complete, diagnostic, score
from tests.unit.test_higher_order_diagnostics import complete_context, context, diagnostic as upstream
from tests.unit.test_fundamental_diagnostic_v2_shadow import evaluate, rule, component, T

ROOT = Path(__file__).resolve().parents[2]
BASELINE = json.loads((ROOT/'tests/fixtures/fundamental_v2_downstream_baseline.json').read_text())


@pytest.fixture(scope='module')
def shadow():
    return evaluate()


@pytest.mark.parametrize('state,expected', BASELINE['numeric_mapping'].items())
def test_all_31_explicit_numeric_mappings_are_unchanged(state, expected):
    assert BASE_STATE_SCORES[state] == Decimal(expected)
    classified = classify_score_input(diagnostic(29,state),registry_version=V1,state_scores=BASE_STATE_SCORES)
    if state == 'INSUFFICIENT_DATA':
        # Retain the literal legacy sentinel; contradictory eligibility cannot
        # convert lack of evidence to a zero-valued score contribution.
        assert classified.state is S.SCORE_INELIGIBLE_INSUFFICIENT_DATA
        assert classified.value is None and score(complete(state)).final_score is None
    else:
        assert classified.state is S.SCORE_ELIGIBLE_EXPLICIT_STATE
        assert classified.value == Decimal(expected)
        assert content_fingerprint(score(complete(state))) == BASELINE['scorecards'][state]


@pytest.mark.parametrize('state,name,expected', BASELINE['synthesis_matrix'])
def test_recognized_v1_synthesis_outputs_equal_pre_change_fixture(state,name,expected):
    base=complete_context().diagnostics+(upstream(31,'MODERATE_RISK'),upstream(32,'STRONG'),upstream(33,'STRONG'))
    outputs=[]
    for item in base:
        values=tuple(upstream(x.canonical_rule_id,state) if x.canonical_rule_id==item.canonical_rule_id else x for x in base)
        outputs.append(content_fingerprint(getattr(s,name)(context(values),s.SynthesisRules())))
    assert content_fingerprint(tuple(outputs)) == expected


@pytest.mark.parametrize('value', ['', 'UNKNOWN', 'READY', 'ready', 'SHADOW_ONLY', ' HEALTHY', None, 5, True, {}, [], 'HEALTHY\x00'])
def test_unknown_empty_malformed_states_never_get_a_number(value):
    d=diagnostic(1); d=replace(d,record=replace(d.record,result=value))
    classified=classify_score_input(d,registry_version=V1,state_scores=BASE_STATE_SCORES)
    assert classified.state is S.SCORE_INELIGIBLE_UNKNOWN_STATE and classified.value is None
    card=score(tuple(x for x in complete() if x.canonical_rule_id!=1)+(d,))
    assert card.final_score is None and card.score_status=='SCORE_INCOMPLETE'
    assert 'DIAGNOSTIC_STATE_UNKNOWN' in card.warnings
    market=next(c for c in card.components if c.component_id=='market_regime')
    assert market.missing_rules==(1,) and market.weight==Decimal('.10') and market.score is None
    assert sum(c.weight for c in card.components)==Decimal('1.00')


@pytest.mark.parametrize('state,expected', [
    ('POLICY_BLOCKED',S.SCORE_INELIGIBLE_POLICY_BLOCKED),
    ('EVIDENCE_CONFLICTED',S.SCORE_INELIGIBLE_CONFLICTED),
    ('NOT_APPLICABLE',S.SCORE_INELIGIBLE_NOT_APPLICABLE),
    ('INSUFFICIENT_DATA',S.SCORE_INELIGIBLE_INSUFFICIENT_DATA),
])
def test_ineligible_vocabulary_is_not_neutral_or_zero(state,expected):
    value=classify_score_input(diagnostic(29,state),registry_version=V1,state_scores=BASE_STATE_SCORES)
    assert value.state is expected and value.value is None


def test_shadow_ready_pe_and_optional_gaps_are_never_valuation_support(shadow):
    r=rule(shadow,29)
    assert component(r,'PE').state.value=='READY'
    assert component(r,'EV_EBITDA').measurements==()
    c=classify_score_input(r,registry_version=V1,state_scores=BASE_STATE_SCORES)
    assert c.state is S.SCORE_INELIGIBLE_SHADOW and c.reason=='V2_SHADOW_SCORE_FORBIDDEN' and c.value is None
    assert score(complete()+(r,)).final_score is None


@pytest.mark.parametrize('state', ['READY','PARTIAL','INSUFFICIENT_DATA','POLICY_BLOCKED','NOT_APPLICABLE','EVIDENCE_CONFLICTED'])
def test_shadow_component_and_aggregate_state_cannot_enter_legacy_mapping(shadow,state):
    # Even tampering cannot bypass the nominal shadow rejection path. The
    # lineage adapter separately verifies and rejects tampering.
    r=replace(rule(shadow,29))
    object.__setattr__(r,'core_state',state)
    value=classify_score_input(r,registry_version=V1,state_scores=BASE_STATE_SCORES)
    assert value.state is S.SCORE_INELIGIBLE_SHADOW and value.value is None
    assert score(complete()+(r,)).final_score is None
    with pytest.raises(ValueError): shadow_diagnostic_envelope(r,as_of=T)


@pytest.mark.parametrize('name', ['risk','trading_thesis','investment_thesis','scenarios'])
@pytest.mark.parametrize('state', ['POLICY_BLOCKED','INSUFFICIENT_DATA','EVIDENCE_CONFLICTED','NOT_APPLICABLE','UNKNOWN','SHADOW_ONLY'])
def test_valid_or_truthy_missing_result_cannot_become_support_or_probability(name,state):
    c=complete_context()
    values=c.diagnostics+(upstream(31,'MODERATE_RISK'),upstream(32,'STRONG'),upstream(33,'STRONG'))
    values=tuple(replace(d,record=replace(d.record,result=state)) if d.canonical_rule_id==16 else d for d in values)
    result=getattr(s,name)(context(values),s.SynthesisRules())
    assert result.state=='INSUFFICIENT_DATA' and result.status is AnalysisStatus.INSUFFICIENT_DATA
    assert result.confidence is None and not any(k in {'bull','base','bear'} for k,_ in result.details)


@pytest.mark.parametrize('name',['risk','trading_thesis','investment_thesis','scenarios'])
def test_active_thesis_entries_reject_mixed_registry_and_raw_shadow(shadow,name):
    for value in (shadow[0],replace(upstream(16,'HEALTHY'),registry_version=V2_VERSION)):
        c=context(complete_context().diagnostics+(value,))
        result=getattr(s,name)(c,s.SynthesisRules())
        assert result.state=='INSUFFICIENT_DATA' and dict(result.details)['blocker']==CROSS_REGISTRY


def test_no_latest_version_fallback_or_unversioned_score_input():
    for registry in ('',None,'future-registry',V2_VERSION):
        d=replace(diagnostic(1),registry_version=registry)
        card=score(complete()+(d,))
        assert card.final_score is None and CROSS_REGISTRY in card.warnings
    assert classify_score_input(SimpleNamespace(),registry_version=V1,state_scores=BASE_STATE_SCORES).value is None
    d=diagnostic(1)
    card=build_scorecard(instrument_id='stock',strategy_version=d.record.strategy_version,registry_version=V2_VERSION,
        as_of_timestamp=d.record.as_of_timestamp,evaluated_at=d.record.evaluated_at,diagnostics=complete())
    assert card.final_score is None


def test_cross_registry_rejection_has_stable_precedence_even_for_future_records():
    unknown=upstream(16,'UNKNOWN')
    foreign=replace(upstream(29),registry_version=V2_VERSION)
    foreign=replace(foreign,record=replace(foreign.record,as_of_timestamp=T+timedelta(days=500)))
    for values in ((unknown,foreign),(foreign,unknown)):
        result=s.investment_thesis(context(values),s.SynthesisRules())
        assert dict(result.details)['blocker']==CROSS_REGISTRY
    assert score(complete()+(foreign,)).final_score is None


def test_shadow_lineage_adapter_is_exact_immutable_reproducible_and_non_scoring(shadow):
    source=rule(shadow,29)
    one=shadow_diagnostic_envelope(source,as_of=T)
    two=shadow_diagnostic_envelope(source,as_of=T.astimezone(timezone(timedelta(hours=5,minutes=30))))
    assert one==two and one.to_json()==two.to_json()
    payload=json.loads(one.to_json())
    assert payload['source']['fingerprint']==one.source_result_fingerprint==source.fingerprint
    assert one.registry_version==V2_VERSION and one.strategy_version is None
    assert one.policy_version==source.evaluator_version and one.policy_fingerprint==source.approval_fingerprint
    assert not one.score_eligible and not one.execution_eligible
    assert score(complete()+(one,)).final_score is None
    assert s.investment_thesis(context((one,)),s.SynthesisRules()).state=='INSUFFICIENT_DATA'
    with pytest.raises(FrozenInstanceError): one.registry_version=V1
    for key,value in [('fingerprint','sha256:'+'0'*64),('source_result_fingerprint','sha256:'+'0'*64),
                      ('policy_version','repaired'),('registry_version',V1),('score_eligible',True)]:
        with pytest.raises(ValueError): replace(one,**{key:value})
    with pytest.raises(ValueError,match='FUTURE'): shadow_diagnostic_envelope(source,as_of=T-timedelta(seconds=1))
    with pytest.raises(ValueError,match='AS_OF'): shadow_diagnostic_envelope(source,as_of=T.replace(tzinfo=None))
    for unsupported in (diagnostic(29),SimpleNamespace(registry_version=V2_VERSION),None):
        with pytest.raises(ValueError,match='SOURCE_REQUIRED'): shadow_diagnostic_envelope(unsupported,as_of=T)


def test_duplicate_and_conflicting_input_order_is_explicit():
    base=complete(); d=diagnostic(1,'WEAK')
    assert score(base+(base[0],))==score(base)
    one,two=score(base+(d,)),score((d,)+base)
    assert one==two and one.final_score is None and 'DIAGNOSTIC_PROVENANCE_CONFLICTED' in one.warnings
    base=complete_context().diagnostics
    c=context(base+(upstream(16,'WEAK'),))
    other=context((upstream(16,'WEAK'),)+base)
    assert s.investment_thesis(c,s.SynthesisRules())==s.investment_thesis(other,s.SynthesisRules())


def test_optional_unavailable_is_visible_without_invented_points():
    card=score(complete()+(diagnostic(25,'READY'),))
    assert card.final_score==Decimal('9.00')  # existing optional-missing policy, not new normalization
    comp=next(c for c in card.components if c.component_id=='earnings_acceleration')
    assert comp.status=='PARTIAL' and 25 not in comp.available_rules
    assert 'DIAGNOSTIC_STATE_UNKNOWN' in card.warnings


def test_contract_cannot_construct_numeric_ineligibility():
    for state in S:
        if state is not S.SCORE_ELIGIBLE_EXPLICIT_STATE:
            with pytest.raises(ValueError): ScoreInputClassification(state,Decimal(5),'fabricated')


def test_active_registry_weights_and_forbidden_boundaries_unchanged():
    assert resolve_diagnostic_registry().registry_version==V1
    assert resolve_diagnostic_registry(V2_VERSION,mode=RegistryMode.SHADOW).mode is RegistryMode.SHADOW
    with pytest.raises(ValueError,match='NOT_ACTIVE'): resolve_diagnostic_registry(V2_VERSION)
    expected=BASELINE['components']
    assert expected==[dict(id=c.component_id,weight=str(c.weight),mandatory=list(c.mandatory),optional=list(c.optional)) for c in COMPONENTS]
    assert V1_SYNTHESIS_STATES==frozenset(BASELINE['synthesis_states'])
    allowed={'app/scoring/engine.py','app/diagnostics/synthesis.py'}
    lineage_repairs={'app/gates/engine.py','app/intelligence/research_diagnostic_evidence.py',
        'app/intelligence/shared_brain_application.py','app/portfolio/canonical_diagnostics_orchestration.py',
        'app/portfolio/engine.py','app/portfolio/holding_intelligence.py','app/portfolio/sell_side_runtime.py','app/rotation/engine.py',
        # B08 guards only; its independent baseline/replay test pins these.
        'app/backtest/analytical.py','app/backtest/portfolio_gates.py','app/portfolio/canonical_six_gates.py',
        'app/portfolio/canonical_six_gates_activation.py','app/intelligence/six_gates_evidence.py','app/universe_analysis/service.py'}
    for path,fp in BASELINE['source_sha256'].items():
        if path not in allowed:
            # Later authorized B07 boundary guards are separately tested for
            # exact V1 replay and unchanged gate/policy methods. Preserve this
            # prior receipt's historical source pins rather than rewrite them.
            import subprocess
            source=(subprocess.check_output(['git','show','01593df3d89c57d982f67b25bf8819281474d9ff:'+path],cwd=ROOT,text=True,encoding='utf-8')
                    if path in lineage_repairs else (ROOT/path).read_text(encoding='utf-8'))
            assert hashlib.sha256(source.encode('utf-8')).hexdigest()==fp,path
    tree=ast.parse((ROOT/'app/diagnostics/downstream.py').read_text())
    imports={n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)}
    assert not any(x.startswith(('app.portfolio','app.gates','app.api','app.runtime','app.storage','app.providers','app.broker')) for x in imports)
    calls={n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
    assert not calls & {'now','utcnow','connect','execute','save','write_text','submit_order'}
