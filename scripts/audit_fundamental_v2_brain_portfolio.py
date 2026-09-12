"""One bounded read-only five-holding proof; stdout only, no production actions.

Use an explicit stored V1 diagnostic cutoff for a like-for-like comparison.
Read adapters delegate existing canonical parsers/selectors, never constructors
that migrate/open writable stores. SQLite must already be open mode=ro.
"""
from contextlib import closing
from dataclasses import replace
from datetime import datetime
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from types import ModuleType

from app.diagnostics.brain_lineage import compare_brain_diagnostics, portfolio_observation
from app.domain.canonical_diagnostic_strategy import CANONICAL_61_STRATEGY_REFERENCE
from app.fundamentals.diagnostic_comparability import assemble_financial_comparability, canonical_json, content_fingerprint
from app.fundamentals.diagnostic_input import CanonicalFinancialDiagnosticInput
from app.fundamentals.diagnostic_v2_shadow import FundamentalDiagnosticV2ShadowEvaluator, ShadowEntity
from app.fundamentals.models import FinancialMetric
from app.fundamentals.store import SQLiteFinancialFactStore, _fact
from app.filings.store import SQLiteCorporateFilingsStore, _filing
from app.data_operations.financial_period_identity_repair import FinancialPeriodIdentityCorrectionStore, FinancialPeriodIdentityProjection
from app.historical.pit_company_type_classification_activation import classify_pit_company_types_from_repository
from app.intelligence.shared_brain_application import SharedBrainApplicationService, SharedBrainApplicationError, StoredSharedBrainEvidenceAssembler, CoreUniverseInstrumentResolver
from app.intelligence.research_diagnostic_evidence import ResearchDiagnosticEvidenceStoredSource
from app.intelligence.unified_state import BrainOutputContext
from app.portfolio.canonical_diagnostics_orchestration import rehydrate_persisted_canonical_diagnostics
from app.portfolio.holding_intelligence import compose_holding_intelligence
from app.portfolio.sell_side_runtime import evaluate_portfolio_sell_side_action
from app.portfolio.serialization import snapshot_from
from app.registry.canonical import DIAGNOSTIC_REGISTRY_VERSION
from app.registry.versioned import V2_VERSION
from app.rotation.engine import CapitalRotationEngine
from app.gates.engine import ExecutionGateEngine
from app.intelligence.profit_harvesting_review import evaluate_profit_harvesting_review
from app.storage.sqlite_governance_repository import SQLiteStrategyGovernanceRepository
from app.storage.core_api_snapshot_repository import CoreApiSnapshotFamily, snapshot_json_from
from app.universe_analysis.service import CoreUniverseAnalysisStore
from scripts.audit_fundamental_v2_shadow import _ReadSnapshots, _read
from scripts.audit_financial_diagnostic_comparability import _market

BASELINE='01593df3d89c57d982f67b25bf8819281474d9ff'
ROOT=Path(__file__).resolve().parents[1]


class _Facts:
    def __init__(self,c): self._connection=c
    series=SQLiteFinancialFactStore.series
    facts=SQLiteFinancialFactStore.facts


class _Filings:
    def __init__(self,c): self._connection=c
    list=SQLiteCorporateFilingsStore.list


class _Diagnostics:
    def __init__(self,c): self._connection=c
    get_canonical_diagnostic_strategy_definition=SQLiteStrategyGovernanceRepository.get_canonical_diagnostic_strategy_definition
    _canonical_diagnostic_definition_from_row=staticmethod(SQLiteStrategyGovernanceRepository._canonical_diagnostic_definition_from_row)
    _canonical_diagnostic_from_row=SQLiteStrategyGovernanceRepository._canonical_diagnostic_from_row

    def list_stored_diagnostic_results(self,canonical_instrument_id,*,as_of):
        ref=CANONICAL_61_STRATEGY_REFERENCE
        rows=self._connection.execute('SELECT * FROM canonical_diagnostic_results WHERE instrument_id=? AND strategy_id=? AND strategy_version=? AND as_of_timestamp=? ORDER BY rule_id,id LIMIT 62',
            (canonical_instrument_id,ref.strategy_id,ref.version,as_of.isoformat())).fetchall()
        if len(rows)!=61: raise ValueError('BRAIN_AUDIT_EXACT_STORED_61_REQUIRED')
        return tuple(self._canonical_diagnostic_from_row(r) for r in rows)


def baseline_module(path):
    name='_hsi_brain_audit_baseline_'+path.replace('/','_').replace('.','_')
    module=ModuleType(name); module.__package__='.'.join(path.split('/')[:-1]); sys.modules[name]=module
    exec(compile(subprocess.check_output(['git','show',BASELINE+':'+path],cwd=ROOT,text=True),path,'exec'),module.__dict__)
    return module


def rejected(call):
    try: call()
    except ValueError as error: return str(error)
    raise AssertionError('SHADOW_BOUNDARY_ACCEPTED')


def audit(connection,*,as_of):
    if as_of.tzinfo is None or as_of.utcoffset() is None: raise ValueError('BRAIN_AUDIT_EXPLICIT_ASOF_REQUIRED')
    connection.row_factory=sqlite3.Row; connection.execute('PRAGMA query_only=ON')
    initial_changes=connection.total_changes
    snapshots=connection.execute('SELECT payload_json FROM portfolio_snapshots ORDER BY id LIMIT 2').fetchall()
    if len(snapshots)!=1: raise ValueError('BRAIN_AUDIT_SINGLE_SNAPSHOT_REQUIRED')
    snapshot=snapshot_from(json.loads(snapshots[0][0]))
    if len(snapshot.holdings)!=5: raise ValueError('BRAIN_AUDIT_FIVE_STORED_HOLDINGS_REQUIRED')
    snapshot_fp=content_fingerprint(snapshots[0][0])
    raw_facts=_read(connection,'financial_facts','fact_id',20000)
    raw_filings=_read(connection,'corporate_filings','filing_id',2000)
    source_fp=content_fingerprint((raw_facts,raw_filings))
    facts=tuple(_fact(json.loads(v)) for v in raw_facts); filings=tuple(_filing(json.loads(v)) for v in raw_filings)
    repo=_ReadSnapshots(connection); projection=FinancialPeriodIdentityProjection(FinancialPeriodIdentityCorrectionStore(repo))
    activation_rows=connection.execute('SELECT payload_json FROM core_api_snapshots WHERE family=? AND record_type=? LIMIT 2',
        (CoreApiSnapshotFamily.PIT_COMPANY_TYPE_CLASSIFICATION.value,'PitCompanyTypeClassificationActivation')).fetchall()
    if len(activation_rows)>1: raise ValueError('BRAIN_AUDIT_CLASSIFICATION_AMBIGUOUS')
    report=classify_pit_company_types_from_repository(repository=repo,activation=snapshot_json_from(activation_rows[0][0]).payload,as_of=as_of) if activation_rows else None
    classifications={r.canonical_instrument_id:r for r in report.receipts} if report else {}
    diagnostics=_Diagnostics(connection)
    resolver=CoreUniverseInstrumentResolver(CoreUniverseAnalysisStore(repo))
    assembler=StoredSharedBrainEvidenceAssembler(_Facts(connection),filings=_Filings(connection),
        diagnostics=ResearchDiagnosticEvidenceStoredSource(diagnostics))
    service=SharedBrainApplicationService(resolver=resolver,evidence_assembler=assembler)
    old=baseline_module('app/intelligence/shared_brain_application.py').SharedBrainApplicationService(resolver=resolver,evidence_assembler=assembler)
    old_compose=baseline_module('app/portfolio/holding_intelligence.py').compose_holding_intelligence
    rows=[]
    for holding in sorted(snapshot.holdings,key=lambda h:h.instrument_id):
        instrument=holding.instrument_id
        records=diagnostics.list_stored_diagnostic_results(instrument,as_of=as_of)
        v1=rehydrate_persisted_canonical_diagnostics(records,instrument_id=instrument,as_of=as_of)
        def attempt(s):
            try: return s.analyze_stock(instrument,context=BrainOutputContext.DEEP_ANALYSIS,as_of=as_of),None
            except ValueError as error:
                if getattr(error,'code',None)!='SHARED_BRAIN_SNAPSHOT_UNAVAILABLE': raise
                return None,(error.code,str(error.__cause__))
        view,failed=attempt(service); prior,prior_failed=attempt(old)
        assert failed==prior_failed and content_fingerprint(view)==content_fingerprint(prior)
        composition_args=dict(holding=holding,portfolio_snapshot=snapshot,shared_brain=view,diagnostics=v1,intelligence_as_of=as_of)
        composition_equal=None
        if view is not None:
            composition_equal=content_fingerprint(compose_holding_intelligence(**composition_args))==content_fingerprint(old_compose(**composition_args))
            assert composition_equal
        reference=service.diagnostic_research(instrument,as_of=as_of,diagnostics=v1)
        projected=projection.project(tuple(f for f in facts if f.instrument.instrument_id==instrument),as_of=as_of)
        financial=CanonicalFinancialDiagnosticInput(assemble_financial_comparability(projected,
            tuple(f for f in filings if f.instrument.instrument_id==instrument),canonical_instrument_id=instrument,as_of=as_of),classifications.get(instrument))
        kind=financial.company_type.company_type if financial.company_type else None
        market,price_state=_market(connection,instrument,as_of)
        shadow=FundamentalDiagnosticV2ShadowEvaluator().evaluate(financial,registry_version=V2_VERSION,as_of=as_of,
            entity_type=ShadowEntity(kind.value) if kind else ShadowEntity.UNKNOWN_NON_COMPARABLE,market=market)
        research=service.diagnostic_research(instrument,as_of=as_of,diagnostics=shadow,registry_version=V2_VERSION,mode='SHADOW')
        observation=portfolio_observation(research,holding_reference=holding.holding_id)
        comparison=compare_brain_diagnostics(reference,research)
        assert comparison==compare_brain_diagnostics(reference,service.diagnostic_research(instrument,as_of=as_of,
            diagnostics=tuple(reversed(shadow)),registry_version=V2_VERSION,mode='SHADOW'))
        boundary={
            'portfolio':rejected(lambda:compose_holding_intelligence(**(composition_args|{'shared_brain':observation}))),
            'rotation':rejected(lambda:CapitalRotationEngine(None).evaluate(observation,as_of)),
            'sell':rejected(lambda:evaluate_portfolio_sell_side_action(observation)),
            'harvest':rejected(lambda:evaluate_profit_harvesting_review(assurance=observation)),
            'six_gates':rejected(lambda:ExecutionGateEngine(None,None).evaluate(instrument_id=instrument,strategy_version=None,
                registry_version=DIAGNOSTIC_REGISTRY_VERSION,scoring_configuration_version='v1',action_context=None,
                as_of_timestamp=as_of,evaluated_at=as_of,inputs=observation)),
            'cross_version':rejected(lambda:service.diagnostic_research(instrument,as_of=as_of,diagnostics=shadow)),
        }
        rows.append(dict(comparison=json.loads(comparison),v1_boundary_unchanged=True,v1_holding_composition_unchanged=composition_equal,
            v1_preexisting_failure=failed,brain_evidence_status=view.evidence_status if view else 'UNAVAILABLE',portfolio_observation_fingerprint=observation.fingerprint,
            price_state=price_state,rejections=boundary))
    assert source_fp==content_fingerprint((_read(connection,'financial_facts','fact_id',20000),_read(connection,'corporate_filings','filing_id',2000)))
    assert snapshot_fp==content_fingerprint(connection.execute('SELECT payload_json FROM portfolio_snapshots').fetchone()[0])
    assert connection.total_changes==initial_changes
    body=dict(audit_version='fundamental-v2-brain-portfolio-proof/v1',baseline_commit=BASELINE,as_of=as_of,
        source_scope='EXACT_STORED_61_CUTOFF; STORED_FINANCIAL_AND_DIAGNOSTIC_BRAIN_INPUTS_ONLY; OTHER_DOMAINS_UNAVAILABLE',
        source_fingerprint=source_fp,portfolio_snapshot_fingerprint=snapshot_fp,portfolio_unchanged=True,
        comparisons=rows,writes=0,provider_calls=0,production_action_evaluations=0,score_eligible=False,execution_eligible=False,
        portfolio_action_eligible=False,v1_active=True,v2_active=False,replay='PASS',
        B07='CLOSED_FOR_SHADOW_PROPAGATION',B07_activation='STILL_BLOCKING_ACTIVATION',
        next_continuation='FUNDAMENTAL_V2_SIX_GATES_VERSION_COMPATIBILITY_V1')
    return dict(body,fingerprint=content_fingerprint(body))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--database',type=Path,required=True); p.add_argument('--as-of',type=datetime.fromisoformat,required=True); args=p.parse_args()
    with closing(sqlite3.connect(args.database.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.execute('BEGIN'); result=audit(c,as_of=args.as_of)
    print(canonical_json(result))
