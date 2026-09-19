import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { parseP1History, readP1History } from '../src/api/p1Lifecycle.ts';

const id = 'NSE:INE372A01015';
const cutoff = '2026-09-18T10:00:00.123456Z';
const fixture = () => ({
  schema_version: 'p1-lifecycle-query/v1', canonical_instrument_id: id, as_of: cutoff,
  availability: 'VERIFIED_HISTORY', outcome: 'ACCEPTED', reason: null,
  last_transition: { transition_id: 'transition:one', fingerprint: 'sha256:' + 'a'.repeat(64),
    next_state: 'CURRENT', transition_as_of: cutoff, known_at: cutoff },
  transition_ids: ['transition:one'], observation_references: [{ signal_id: 'signal:one', fingerprint: 'b'.repeat(64) }],
  actionability: 'WATCH_ONLY', execution_status: 'NON_EXECUTABLE', expiry: 'EXPIRY_NOT_GOVERNED_FOR_THIS_PATH',
});

test('existing frozen production page is unchanged; additive app mounts the reader', () => {
  const page = readFileSync(new URL('../src/pages/ProductionPages.tsx', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
  assert.equal(createHash('sha256').update(page).digest('hex'), 'd1fb6eb3fe49eb63d56fedab5575977342e81a17516aea5bed278f7f218dc595');
  const app = readFileSync(new URL('../src/App.tsx', import.meta.url), 'utf8');
  assert.match(app, /<P1LifecyclePanel key=\{params.canonicalInstrumentId\} instrument=\{params.canonicalInstrumentId\}/);
});

test('canonical snake_case, microsecond precision and timezone equivalence survive', () => {
  assert.deepEqual(parseP1History(fixture(), id, cutoff), fixture());
  assert.ok(parseP1History(fixture(), id, '2026-09-18T15:30:00.123456+05:30'));
  assert.equal(parseP1History(fixture(), id, '2026-09-18T10:00:00.123457Z'), null);
});

for (const [field, value] of Object.entries({ schema_version: 'unknown', canonical_instrument_id: 'NSE:OTHER',
  actionability: 'BUY', execution_status: 'EXECUTABLE', expiry: '2026-10-01', availability: 'LIVE',
  outcome: 'READY', reason: 'unknown', as_of: '2026-09-18T10:00:00' })) {
  test(`reject malformed ${field} without promotion`, () => {
    assert.equal(parseP1History({ ...fixture(), [field]: value }, id, cutoff), null);
  });
}

test('later unconfirmed CURRENT preserves source blocker instead of claiming freshness', () => {
  const body = { ...fixture(), outcome: 'SOURCE_BLOCKED', reason: 'REEVALUATION_REQUIRED' };
  assert.deepEqual(parseP1History(body, id, cutoff), body);
});

test('no history, conflict, invalidated and superseded remain distinct', () => {
  for (const state of ['INVALIDATED', 'SUPERSEDED']) {
    const body = fixture(); body.last_transition.next_state = state;
    assert.equal(parseP1History(body, id, cutoff)?.last_transition?.next_state, state);
  }
  for (const availability of ['NO_HISTORY', 'CONFLICTED']) {
    const body = { ...fixture(), availability, last_transition: null, transition_ids: [], observation_references: [],
      outcome: availability === 'CONFLICTED' ? 'CONFLICTED' : 'SOURCE_BLOCKED',
      reason: availability === 'CONFLICTED' ? 'CHAIN_CONFLICT' : 'SOURCE_LINEAGE_UNAVAILABLE' };
    assert.equal(parseP1History(body, id, cutoff)?.availability, availability);
  }
});

test('reject inconsistent chains, future transition and unknown state', () => {
  assert.equal(parseP1History({ ...fixture(), last_transition: null }, id, cutoff), null);
  assert.equal(parseP1History({ ...fixture(), transition_ids: ['transition:one', 'transition:one'] }, id, cutoff), null);
  const body = fixture(); body.last_transition.known_at = '2026-09-19T10:00:00Z';
  assert.equal(parseP1History(body, id, cutoff), null);
  body.last_transition.known_at = cutoff; body.last_transition.next_state = 'BUY';
  assert.equal(parseP1History(body, id, cutoff), null);
});

test('unknown fields, prices and secret-like extras are not forwarded', () => {
  const body = { ...fixture(), access_token: 'synthetic-not-a-token', price: 99 };
  assert.deepEqual(parseP1History(body, id, cutoff), fixture());
});

test('one exact GET only, explicit cutoff, no auth headers, redirects or fallback', async (t) => {
  const fetcher = t.mock.method(globalThis, 'fetch', async (url: URL, options: RequestInit) => {
    assert.equal(url.pathname, '/api/v1/p1-signals/lifecycle');
    assert.equal(url.searchParams.get('as_of'), cutoff);
    assert.equal(url.searchParams.get('canonical_instrument_id'), id);
    assert.equal(options.method, 'GET'); assert.equal(options.credentials, 'omit');
    assert.equal(options.redirect, 'error'); assert.equal(options.cache, 'no-store');
    assert.deepEqual(options.headers, { Accept: 'application/json' });
    return Response.json(fixture());
  });
  assert.equal((await readP1History('http://127.0.0.1:8000', id, cutoff)).state, 'HISTORY');
  assert.equal(fetcher.mock.callCount(), 1);
});

test('invalid input/origin does not issue a request', async (t) => {
  const fetcher = t.mock.method(globalThis, 'fetch', async () => { throw Error('must not run'); });
  for (const origin of ['http://public.example', 'https://user:secret@example.com', 'https://example.com?token=secret', 'https://example.com/path']) {
    assert.equal((await readP1History(origin, id, cutoff)).state, 'INVALID_QUERY');
  }
  assert.equal((await readP1History('http://localhost:8000', 'APARINDS', cutoff)).state, 'INVALID_QUERY');
  assert.equal((await readP1History('http://localhost:8000', id, 'now')).state, 'INVALID_QUERY');
  assert.equal(fetcher.mock.callCount(), 0);
});

test('schema unavailable is not empty history; raw error text never escapes', async (t) => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ error: {
    code: 'P1_LIFECYCLE_SCHEMA_UNAVAILABLE', message: 'synthetic-secret-path',
  } }, { status: 503 }));
  assert.deepEqual(await readP1History('http://localhost:8000', id, cutoff), {
    state: 'UNAVAILABLE', code: 'P1_LIFECYCLE_SCHEMA_UNAVAILABLE',
  });
});

test('HTTP failures and invalid JSON cannot fall back to mocks', async (t) => {
  const fetcher = t.mock.method(globalThis, 'fetch', async () => new Response('private text', { status: 403 }));
  assert.deepEqual(await readP1History('http://localhost:8000', id, cutoff), { state: 'UNAVAILABLE', code: 'HTTP_403' });
  fetcher.mock.mockImplementation(async () => Response.json({ data: fixture() }));
  assert.equal((await readP1History('http://localhost:8000', id, cutoff)).state, 'INVALID_RESPONSE');
  fetcher.mock.mockImplementation(async () => new Response('not json'));
  assert.equal((await readP1History('http://localhost:8000', id, cutoff)).state, 'UNAVAILABLE');
});

test('unmount cancellation and bounded six-second timeout remain distinct', async (t) => {
  t.mock.timers.enable({ apis: ['setTimeout'] });
  t.mock.method(globalThis, 'fetch', async (_url: URL, options: RequestInit) => new Promise<Response>((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new Error('redacted')), { once: true });
  }));
  const controller = new AbortController();
  const cancelled = readP1History('http://localhost:8000', id, cutoff, controller.signal);
  controller.abort(); assert.equal((await cancelled).state, 'CANCELLED');
  const timed = readP1History('http://localhost:8000', id, cutoff);
  t.mock.timers.tick(6000); assert.equal((await timed).state, 'TIMEOUT');
});
