"""Read-only deterministic safety receipt over synthetic, pinned fixtures.

Run with the repository test dependencies. No production execution or database
access; output is stdout only. This is an audit harness, not a runtime service.
"""
import hashlib
import gzip
from functools import partial
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from app.diagnostics import synthesis
from app.diagnostics.downstream import (
    CROSS_REGISTRY, ScoreInputState, classify_score_input, shadow_diagnostic_envelope,
)
from app.fundamentals.diagnostic_comparability import content_fingerprint
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.scoring.engine import BASE_STATE_SCORES, COMPONENTS
from tests.unit.test_decision_score import complete, score
from tests.unit.test_higher_order_diagnostics import diagnostic, context, complete_context
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.diagnostic_v2_shadow import FundamentalDiagnosticV2ShadowEvaluator, ShadowEntity
from app.registry.versioned import V2_VERSION
from tests.unit.test_fundamental_diagnostic_v2_shadow import facts, T
from tests.unit.test_financial_diagnostic_comparability import comparable, market
from tests.unit.test_pit_company_type_classification_activation import _forward, _taxonomy_receipt, _report

ROOT=Path(__file__).resolve().parents[1]


def shadow_fixture():
    # Existing fixture creates synthetic gzip source bytes with a default
    # header timestamp. Pin those bytes here; do not alter any Core policy,
    # provider document, canonical evidence or the shared fixture cache.
    compress=partial(gzip.compress,mtime=0)
    with patch('gzip.compress',compress):
        forward=_forward()
        company=_report(forward=forward,taxonomy=(_taxonomy_receipt(forward,macro='IN07',sector='IN0702'),)).receipts[0]
    source=CanonicalFinancialDiagnosticInput(comparable(facts()),company)
    return FundamentalDiagnosticV2ShadowEvaluator().evaluate(source,registry_version=V2_VERSION,
        as_of=T,entity_type=ShadowEntity.NON_FINANCIAL,market=market())


def audit(*, preserved_source_revision=None):
    baseline=json.loads((ROOT/'tests/fixtures/fundamental_v2_downstream_baseline.json').read_text())
    inventory=json.loads((ROOT/'docs/architecture/FUNDAMENTAL_V2_DOWNSTREAM_FAIL_CLOSED_INVENTORY.json').read_text())
    numeric={k:str(v) for k,v in BASE_STATE_SCORES.items()}
    assert numeric==baseline['numeric_mapping']
    components=[dict(id=c.component_id,weight=str(c.weight),mandatory=list(c.mandatory),optional=list(c.optional)) for c in COMPONENTS]
    assert components==baseline['components']
    scorecards={state:content_fingerprint(score(complete(state))) for state in baseline['scorecards']}
    assert scorecards==baseline['scorecards']
    base=complete_context().diagnostics+(diagnostic(31,'MODERATE_RISK'),diagnostic(32,'STRONG'),diagnostic(33,'STRONG'))
    for state,name,expected in baseline['synthesis_matrix']:
        fingerprints=[]
        for item in base:
            values=tuple(diagnostic(x.canonical_rule_id,state) if x.canonical_rule_id==item.canonical_rule_id else x for x in base)
            fingerprints.append(content_fingerprint(getattr(synthesis,name)(context(values),synthesis.SynthesisRules())))
        assert content_fingerprint(tuple(fingerprints))==expected
    rejected=[]
    for result in shadow_fixture():
        admission=classify_score_input(result,registry_version=DIAGNOSTIC_REGISTRY_VERSION,state_scores=BASE_STATE_SCORES)
        envelope=shadow_diagnostic_envelope(result,as_of=T)
        assert admission.state is ScoreInputState.SCORE_INELIGIBLE_SHADOW and admission.value is None
        assert score(complete()+(envelope,)).final_score is None
        higher={}
        for name in ('risk','trading_thesis','investment_thesis','scenarios'):
            value=getattr(synthesis,name)(context(base+(envelope,)),synthesis.SynthesisRules())
            assert value.state=='INSUFFICIENT_DATA' and dict(value.details)['blocker']==CROSS_REGISTRY
            higher[name]=content_fingerprint(value)
        rejected.append(dict(rule_id=result.rule_id,core_state=result.core_state.value,
            components=[(c.component_id,c.state.value) for c in result.component_states],
            reason=admission.reason,score=None,envelope_fingerprint=envelope.fingerprint,
            source_result_fingerprint=result.fingerprint,thesis_rejections=higher))
    preserved={}
    modified={}
    for path,fp in baseline['source_sha256'].items():
        # A later authorized slice may replay this immutable historical receipt
        # against its source checkpoint. Behavioral score/thesis replays above
        # still execute current code; the new slice separately pins its diff.
        text = (subprocess.check_output(['git','show',preserved_source_revision+':'+path],cwd=ROOT,text=True,encoding='utf-8')
                if preserved_source_revision is not None else (ROOT/path).read_text(encoding='utf-8'))
        actual=hashlib.sha256(text.encode('utf-8')).hexdigest()
        if path in {'app/scoring/engine.py','app/diagnostics/synthesis.py'}:
            modified[path]=dict(before=fp,after=actual)
        else:
            assert fp==actual,path
            preserved[path]=actual
    body=dict(schema_version='fundamental-v2-downstream-safety-receipt/v1',
        baseline_commit=baseline['baseline_commit'],inventory_fingerprint=content_fingerprint(inventory),
        fixture_fingerprint=content_fingerprint(baseline),
        numeric_mapping=numeric,explicit_values_equal=True,
        numeric_scorecard_replays=len(scorecards),scorecard_equality=True,
        insufficient_sentinel=baseline['insufficient_sentinel_exception'],
        thesis_state_count=len(baseline['synthesis_states']),thesis_matrix_count=len(baseline['synthesis_matrix']),
        thesis_position_replays=len(baseline['synthesis_matrix'])*len(base),thesis_equality=True,
        weights_and_dependencies=components,weights_unchanged=True,unknown_numeric_contribution=None,
        cross_registry_reason=CROSS_REGISTRY,shadow_rejections=rejected,
        preserved_app_files=len(preserved),preserved_source_fingerprint=content_fingerprint(preserved),
        modified_sources=modified,adapter_source_sha256=hashlib.sha256((ROOT/'app/diagnostics/downstream.py').read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
        blockers=dict(B03='PARTIALLY_CLOSED',B04='CLOSED_FOR_ACTIVATION_SAFETY',
                      B05='PARTIALLY_CLOSED',B06='PARTIALLY_CLOSED',
                      B07='STILL_BLOCKING_ACTIVATION',B08='STILL_BLOCKING_ACTIVATION',
                      B09='STILL_BLOCKING_ACTIVATION',B14='STILL_BLOCKING_ACTIVATION'),
        b04_scope='Diagnostic-to-Decision-Score unknown numeric fallback removed; not a claim that unrelated raw-evidence/crowd models are calibrated.',
        v1_active=True,v2_active=False,score_activation=False,production_work_performed=False,
        next_continuation='FUNDAMENTAL_V2_BRAIN_PORTFOLIO_VERSION_PROPAGATION_V1')
    return json.loads(json.dumps(dict(body,fingerprint=content_fingerprint(body))))


if __name__=='__main__':
    print(json.dumps(audit(),sort_keys=True,indent=2))
