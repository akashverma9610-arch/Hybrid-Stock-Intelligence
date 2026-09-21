"""Real signed JWTs, isolated DBs; no production identity or portfolio writes."""
from datetime import UTC, datetime, timedelta
import sqlite3

import pytest

from app.api.pilot_p1_history import read_unarmed_history
from app.api.schemas.p1_signal_lifecycle import P1LifecycleQuery
from app.storage.database import DatabaseSettings
from app.storage.readonly_p1_signal_lifecycle import P1ReadUnavailable
from app.storage.sqlite_p1_signal_lifecycle import SCHEMA
from tests.unit.test_pilot_identity_and_ownership import setup, headers


PATH = '/api/v1/pilot/p1-history'
QUERY = {'canonical_instrument_id': 'NSE:INE372A01015', 'as_of': '2026-09-02T10:30:00Z'}


def configure(setup, tmp_path, provision=True):
    path = tmp_path / 'canonical.db'
    if provision:
        with sqlite3.connect(path) as con:
            for statement in SCHEMA:
                con.execute(statement)
    setup[0].app.state.database_settings = DatabaseSettings(url=f'sqlite:///{path}')
    return path


@pytest.mark.parametrize('subject', ['auth0|owner', 'auth0|a', 'auth0|b'])
def test_authenticated_empty_history_is_shared_and_truthful(setup, tmp_path, subject):
    path = configure(setup, tmp_path)
    before = path.read_bytes()
    response = setup[0].get(PATH, params=QUERY, headers=headers(setup[5](subject)))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['availability'] == 'NO_HISTORY'
    assert body['recorder_state'] == 'NOT_ACTIVE' and body['prospective_start'] is None
    assert body['source_readiness'] == 'SOURCE_BLOCKED'
    assert set(body['warnings']) == {'SOURCE_KNOWN_AT_ADAPTER_UNAVAILABLE', 'PROSPECTIVE_START_UNSET'}
    assert body['observations'] == body['transitions'] == []
    assert body['actionability'] == 'WATCH_ONLY' and body['execution_status'] == 'NON_EXECUTABLE'
    assert response.headers['cache-control'] == 'no-store'
    assert 'PRIVATE_LEGACY' not in response.text and 'portfolio-' not in response.text
    assert path.read_bytes() == before


def test_authentication_required_and_legacy_route_still_denied(setup, tmp_path):
    configure(setup, tmp_path)
    client = setup[0]
    assert client.get(PATH, params=QUERY).status_code == 401
    token = setup[5]
    for subject in ['auth0|owner', 'auth0|a', 'auth0|b']:
        assert client.post(PATH, json=QUERY, headers=headers(token(subject))).status_code == 403
        assert client.get('/api/v1/p1-signals/lifecycle', params=QUERY, headers=headers(token(subject))).status_code == 403
    assert client.get(PATH, params=QUERY, headers=headers(token(aud='wrong'))).status_code == 401
    assert client.get(PATH, params=QUERY, headers=headers(token(exp=1))).status_code == 401


@pytest.mark.parametrize('field', ['user_id', 'owner_id', 'role', 'admin', 'prospective_start'])
def test_client_cannot_supply_authority_or_activation(setup, tmp_path, field):
    configure(setup, tmp_path)
    result = setup[0].get(PATH, params={**QUERY, field: 'PRIVATE-SECRET'}, headers=headers(setup[5]()))
    assert result.status_code == 422
    assert result.json()['error']['code'] == 'P1_HISTORY_QUERY_INVALID'
    assert 'PRIVATE-SECRET' not in result.text


@pytest.mark.parametrize('query', [{}, {**QUERY, 'as_of': '2026-09-02T10:30:00'},
    {**QUERY, 'as_of': (datetime.now(UTC) + timedelta(days=1)).isoformat()},
    {**QUERY, 'canonical_instrument_id': '../private'}, list(QUERY.items()) + [('as_of', QUERY['as_of'])]])
def test_strict_query_validation(setup, tmp_path, query):
    configure(setup, tmp_path)
    assert setup[0].get(PATH, params=query, headers=headers(setup[5]())).status_code == 422


def test_schema_absence_is_not_empty_and_does_not_create_schema(setup, tmp_path):
    path = configure(setup, tmp_path, provision=False)
    before = path.read_bytes()
    result = setup[0].get(PATH, params=QUERY, headers=headers(setup[5]()))
    assert result.status_code == 503
    assert result.json()['error']['code'] == 'P1_LIFECYCLE_SCHEMA_UNAVAILABLE'
    assert path.read_bytes() == before


@pytest.mark.parametrize('table', ['core_api_snapshots', 'p1_signal_lifecycle_batch_index', 'p1_signal_lifecycle_heads'])
def test_unclassified_private_or_research_history_is_never_published(setup, tmp_path, table):
    path = configure(setup, tmp_path)
    # Orphan/corrupt/private payloads are deliberately never decoded by this read.
    with sqlite3.connect(path) as con:
        if table == 'core_api_snapshots':
            con.execute("INSERT INTO core_api_snapshots SELECT 'private-p1', 'P1_SIGNAL_LIFECYCLE_BATCH', schema_version, record_type, fingerprint, created_at, json_object('private', 'PRIVATE_SECRET') FROM core_api_snapshots LIMIT 1")
        elif table == 'p1_signal_lifecycle_batch_index':
            con.execute("INSERT INTO p1_signal_lifecycle_batch_index VALUES ('private', 'slot', 'input', 'cutoff')")
        else:
            con.execute("INSERT INTO p1_signal_lifecycle_heads VALUES ('slot', 'private', 'fp', 'cutoff', 'lifetime')")
    before = path.read_bytes()
    result = setup[0].get(PATH, params=QUERY, headers=headers(setup[5]()))
    assert result.status_code == 503
    assert result.json()['error']['code'] == 'P1_PROSPECTIVE_ORIGIN_UNVERIFIED'
    assert 'PRIVATE_SECRET' not in result.text and 'lifetime' not in result.text
    assert path.read_bytes() == before


def test_unavailable_database_never_becomes_empty(tmp_path):
    query = P1LifecycleQuery.model_validate(QUERY)
    for database in [DatabaseSettings(), DatabaseSettings(url=f'sqlite:///{tmp_path / "missing.db"}')]:
        with pytest.raises(P1ReadUnavailable, match='P1_LIFECYCLE_STORE_UNAVAILABLE'):
            read_unarmed_history(database, query)
    assert not (tmp_path / 'missing.db').exists()
