"""Canonical persisted fixtures, real RSA auth, no providers or production writes."""
from dataclasses import fields, replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.api.pilot_canonical_query import PilotCanonicalQueryService
from app.historical.models import InstrumentLifecycle, UniverseMembership
from app.historical.security_master import HistoricalSecurityMasterStore
from app.intelligence.market_wide_watch import MarketWideWatchRun, MarketWideWatchService, MarketWideWatchStore
from app.market_data.current_sector_rotation import CurrentSectorRankingArtifact, CurrentSectorRankingStore
from app.storage.core_api_snapshot_repository import CoreApiSnapshot, CoreApiSnapshotFamily as F
from app.universe_analysis.service import CoreUniverseAnalysisStore
from tests.unit.test_market_sector_api import regime
from tests.unit.test_market_wide_watch import T, _Diagnostics, _Governance, _instrument, _result
from tests.unit.test_pilot_identity_and_ownership import setup, headers
from tests.unit.test_shared_brain_sector_ranking_projection import _report


def watch(repository):
    universe = CoreUniverseAnalysisStore(repository)
    instrument = _instrument("NSE:INE000000001", "ALPHA")
    universe.save_instrument(instrument)
    memberships = HistoricalSecurityMasterStore(repository)
    memberships.save_membership(UniverseMembership("m1", instrument.instrument_id, "NIFTY_500", T,
        None, T, "NSE", "exact", InstrumentLifecycle.ACTIVE), as_of=T)
    service = MarketWideWatchService(repository=repository, universe=universe, memberships=memberships,
        diagnostics=_Diagnostics({instrument.instrument_id: (
            _result(instrument.instrument_id, "24", "ACCELERATING"),
            _result(instrument.instrument_id, "6", "EMERGING_LEADER"))}), governance=_Governance())
    return service.run(as_of=T)


@pytest.mark.parametrize("surface,code", [("market", "MARKET_REGIME_UNAVAILABLE"),
    ("sectors", "CURRENT_SECTOR_RANKING_UNAVAILABLE"), ("opportunities", "MARKET_WIDE_WATCH_UNAVAILABLE")])
def test_missing_canonical_evidence_is_503_not_demo(setup, surface, code):
    client, _, _, _, _, token, *_ = setup
    result = client.get('/api/v1/pilot/canonical/' + surface, headers=headers(token()))
    assert result.status_code == 503
    assert result.json()['reason_codes'] == [code]
    assert result.json()['data'] is None
    assert result.json()['freshness'] == 'UNAVAILABLE'


def test_market_uses_persisted_regime_and_does_not_renew_freshness(setup):
    client, _, _, _, _, token, repo, *_ = setup
    value = regime()
    repo.save_snapshot(CoreApiSnapshot('m', F.MARKET_REGIME, 'v1', 'fixture', 'market-fingerprint', value.evaluated_at, value))
    result = client.get('/api/v1/pilot/canonical/market', headers=headers(token()))
    assert result.status_code == 200
    body = result.json()
    assert body['status'] == 'DEGRADED' and body['freshness'] == 'UNKNOWN'
    assert body['data']['regime'] == value.classification.value
    assert body['data']['input_observation_ids'] == list(value.input_observation_ids)
    assert body['data']['conditions'] == []
    assert body['sources'][0]['fingerprint'] == 'market-fingerprint'
    assert result.headers['cache-control'] == 'no-store'


def test_market_excludes_future_evaluation_and_scans_beyond_first_page(setup):
    repo = setup[6]
    for i in range(105):
        value = replace(regime(), id=f'm{i}', as_of_timestamp=T+timedelta(seconds=i), evaluated_at=T+timedelta(seconds=i))
        repo.save_snapshot(CoreApiSnapshot(f'm{i}', F.MARKET_REGIME, 'v1', 'fixture', f'fp{i}', value.evaluated_at, value))
    service = PilotCanonicalQueryService(repo)
    assert service.read('market', as_of=T+timedelta(seconds=104)).data.result_id == 'm104'
    assert service.read('market', as_of=T+timedelta(seconds=50)).data.result_id == 'm50'


def test_sector_adapter_preserves_ranking_breadth_warnings_and_pit(setup):
    repo = setup[6]
    artifact = CurrentSectorRankingArtifact.create(replace(_report(), warnings=('CURRENT_MEMBERSHIP_ONLY',)))
    CurrentSectorRankingStore(repo).save(artifact)
    service = PilotCanonicalQueryService(repo)
    result = service.read('sectors', as_of=artifact.ranking_as_of)
    assert result.status == 'DEGRADED'
    assert result.data.ranked_sectors == artifact.report.ranked_sectors
    assert result.data.breadth == artifact.report.breadth
    assert 'CURRENT_MEMBERSHIP_ONLY' in result.warnings
    assert result.sources[0].as_of == artifact.ranking_as_of
    assert service.read('sectors', as_of=artifact.ranking_as_of-timedelta(microseconds=1)).status == 'UNAVAILABLE'


def test_tampered_sector_not_repaired(setup):
    repo = setup[6]
    artifact = replace(CurrentSectorRankingArtifact.create(_report()), fingerprint='tampered')
    CurrentSectorRankingStore(repo).save(artifact)
    assert PilotCanonicalQueryService(repo).read('sectors', as_of=artifact.ranking_as_of).reason_codes == ('CANONICAL_PROVENANCE_INVALID',)


def test_watch_projection_preserves_multiple_archetypes_without_activation(setup):
    client, _, _, _, _, token, repo, *_ = setup
    value = watch(repo)
    result = client.get('/api/v1/pilot/canonical/opportunities', headers=headers(token()))
    assert result.status_code == 200, result.text
    record = result.json()['data']['records'][0]
    assert set(record['archetypes']) == {r.value for r in value.records[0].archetypes}
    assert len(record['archetypes']) >= 2
    assert record['strategy_eligibility'] == 'NOT_EVALUATED'
    assert record['execution_status'] == 'NON_EXECUTABLE'
    assert record['actionability'] == 'WATCH_ONLY'
    assert record['horizon'] is None and record['direction'] is None
    assert all(route[1] == 'SETUP_POLICY_UNAVAILABLE_FOR_ARCHETYPE' for route in record['setup_policy_routes'])
    assert record['evidence_references']
    assert result.json()['freshness'] == 'UNKNOWN'


def test_shared_projection_never_returns_private_watch_fields(setup):
    client, _, _, _, _, token, repo, *_ = setup
    value = watch(repo)
    response_a = client.get('/api/v1/pilot/canonical/opportunities', params={'as_of':T.isoformat()}, headers=headers(token()))
    response_b = client.get('/api/v1/pilot/canonical/opportunities', params={'as_of':T.isoformat(),'owner_id':'PRIVATE_LEGACY'}, headers=headers(token('auth0|b')))
    assert response_a.json() == response_b.json()
    for forbidden in ('portfolio_records', 'comparison_readiness', 'decision_score_value', 'rotation_funnel', 'PRIVATE_LEGACY'):
        assert forbidden not in response_a.text
    exact = client.get('/api/v1/pilot/canonical/stocks/'+value.records[0].canonical_instrument_id, headers=headers(token()))
    assert exact.status_code == 200
    assert len(exact.json()['data']['records']) == 1
    assert client.get('/api/v1/pilot/canonical/stocks/NSE:UNKNOWN', headers=headers(token())).status_code == 503


def test_watch_future_received_at_and_tampering_excluded(setup):
    repo=setup[6]; value=watch(repo)
    service=PilotCanonicalQueryService(repo)
    assert service.read('opportunities',as_of=T-timedelta(microseconds=1)).status == 'UNAVAILABLE'
    # Canonical store rejects tampering before persistence.
    with pytest.raises(ValueError):
        MarketWideWatchStore(repo).save(replace(value, fingerprint='tampered'))
    rows=repo.list_snapshots(F.MARKET_WIDE_QUALITY_INFLECTION_WATCH)
    assert len(rows)==1


@pytest.mark.parametrize('path', ['/api/v1/pilot/canonical/market','/api/v1/pilot/canonical/sectors',
    '/api/v1/pilot/canonical/opportunities','/api/v1/pilot/canonical/stocks/NSE:INE000000001'])
def test_auth_and_methods_remain_fail_closed(setup,path):
    client, _, _, _, _, token, *_=setup
    assert client.get(path).status_code==401
    assert client.post(path, headers=headers(token())).status_code==403
    assert client.get(path, headers=headers(token('auth0|uninvited'))).status_code==403


def test_cutoff_validation_and_unknown_surface(setup):
    client, _, _, _, _, token, *_=setup
    for cutoff in ('2026-01-01', '2099-01-01T00:00:00Z'):
        assert client.get('/api/v1/pilot/canonical/market', params={'as_of':cutoff}, headers=headers(token())).status_code==422
    assert client.get('/api/v1/pilot/canonical/unknown', headers=headers(token())).status_code==403


def test_projection_repeated_read_has_no_write_or_authority(setup):
    repo=setup[6]; value=watch(repo); service=PilotCanonicalQueryService(repo)
    before=repo._connection.total_changes
    assert service.read('opportunities',as_of=T).model_dump_json()==service.read('opportunities',as_of=T).model_dump_json()
    assert repo._connection.total_changes==before
    source=Path('app/api/pilot_canonical_query.py').read_text()
    for forbidden in ('save_snapshot(', 'portfolio_query', 'place_order', 'datetime.now', 'PreBreakoutEngine(', '.run('):
        assert forbidden not in source


def test_private_only_watch_record_is_not_shared_and_receipt_time_is_enforced(setup):
    repo=setup[6]; value=watch(repo)
    private_values={f.name:getattr(value.records[0],f.name) for f in fields(value.records[0]) if f.name!='fingerprint'}
    private_values.update(canonical_instrument_id='NSE:PRIVATE', symbol='PRIVATE', comparison_readiness='PRIVATE_CONTEXT')
    private=type(value.records[0]).create(**private_values)
    values={f.name:getattr(value,f.name) for f in fields(value) if f.name not in {'run_id','fingerprint'}}
    values['portfolio_records']=(private,)
    combined=MarketWideWatchRun.create(**values)
    record=CoreApiSnapshot(combined.run_id,F.MARKET_WIDE_QUALITY_INFLECTION_WATCH,'v1','fixture',combined.fingerprint,T,combined)
    class Reader:
        def list_snapshots(self,family,*,limit=100,offset=0):
            return (record,) if offset==0 and family==record.family else ()
    service=PilotCanonicalQueryService(Reader())
    response=service.read('opportunities',as_of=T)
    assert response.status=='DEGRADED'
    assert 'PRIVATE' not in response.model_dump_json()
    record=replace(record,created_at=T+timedelta(days=1))
    assert service.read('opportunities',as_of=T).status=='UNAVAILABLE'
    record=replace(record,created_at=T,fingerprint='mismatch')
    assert service.read('opportunities',as_of=T).reason_codes==('CANONICAL_PROVENANCE_INVALID',)


def test_old_data_never_becomes_fresh_and_source_warnings_survive(setup):
    repo=setup[6]
    artifact=CurrentSectorRankingArtifact.create(replace(_report(),warnings=('SOURCE_STALE','SOURCE_PARTIAL')))
    CurrentSectorRankingStore(repo).save(artifact)
    response=PilotCanonicalQueryService(repo).read('sectors',as_of=artifact.ranking_as_of+timedelta(days=365))
    assert response.freshness=='UNKNOWN' and response.status!='READY'
    assert {'SOURCE_STALE','SOURCE_PARTIAL'}<=set(response.warnings)
    assert response.data.latest_completed_session==artifact.latest_completed_session
