/** Dedicated retained-history reader. Never uses the legacy /signals mapper. */
export interface P1History {
  schema_version: 'p1-lifecycle-query/v1';
  canonical_instrument_id: string;
  as_of: string;
  availability: 'VERIFIED_HISTORY' | 'NO_HISTORY' | 'CONFLICTED';
  outcome: 'ACCEPTED' | 'NO_CHANGE' | 'SOURCE_BLOCKED' | 'POLICY_BLOCKED' | 'CONFLICTED';
  reason: string | null;
  last_transition: {
    transition_id: string;
    fingerprint: string;
    next_state: 'CURRENT' | 'INVALIDATED' | 'SUPERSEDED';
    transition_as_of: string;
    known_at: string;
  } | null;
  transition_ids: string[];
  observation_references: { signal_id: string; fingerprint: string }[];
  actionability: 'WATCH_ONLY';
  execution_status: 'NON_EXECUTABLE';
  expiry: 'EXPIRY_NOT_GOVERNED_FOR_THIS_PATH';
}

export type P1ReadResult =
  | { state: 'HISTORY'; data: P1History }
  | { state: 'UNAVAILABLE' | 'INVALID_RESPONSE' | 'INVALID_QUERY' | 'TIMEOUT' | 'CANCELLED'; code: string };

const reasons = new Set([
  'EVIDENCE_KNOWN_AT_UNAVAILABLE', 'EVIDENCE_CONFLICT', 'SOURCE_LINEAGE_UNAVAILABLE',
  'SOURCE_NOT_ELIGIBLE', 'STRATEGY_AUTHORITY_UNAVAILABLE', 'SECURITY_NOT_ELIGIBLE',
  'PREDICATE_NOT_LIFECYCLE_MAPPED', 'REEVALUATION_REQUIRED',
  'OUT_OF_ORDER_REQUIRES_REEVALUATION', 'CUTOFF_CONFLICT', 'INPUT_CONFLICT', 'CHAIN_CONFLICT',
]);
const safeErrors = new Set([
  'P1_LIFECYCLE_STORE_UNAVAILABLE', 'P1_LIFECYCLE_SCHEMA_UNAVAILABLE',
  'P1_LIFECYCLE_READ_LIMIT_EXCEEDED', 'INVALID_REQUEST',
]);
const object = (value: unknown): value is Record<string, unknown> => (
  value !== null && typeof value === 'object' && !Array.isArray(value)
);
const text = (value: unknown): value is string => typeof value === 'string' && value.length > 0;
const member = (value: unknown, values: readonly string[]) => typeof value === 'string' && values.includes(value);

// Preserve canonical microseconds; a JS Date alone would merge distinct cutoffs.
function instant(value: unknown): bigint | null {
  if (typeof value !== 'string') return null;
  const match = value.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d{1,6}))?(?:Z|[+-]\d{2}:\d{2})$/);
  const milliseconds = Date.parse(value);
  if (!match || !Number.isFinite(milliseconds)) return null;
  return BigInt(milliseconds) * 1000n + BigInt((match[1] ?? '').padEnd(6, '0').slice(3));
}

export function parseP1History(value: unknown, instrument: string, asOf: string): P1History | null {
  if (!object(value) || value.schema_version !== 'p1-lifecycle-query/v1'
    || value.canonical_instrument_id !== instrument || instant(value.as_of) === null
    || instant(value.as_of) !== instant(asOf)
    || value.actionability !== 'WATCH_ONLY' || value.execution_status !== 'NON_EXECUTABLE'
    || value.expiry !== 'EXPIRY_NOT_GOVERNED_FOR_THIS_PATH'
    || !member(value.availability, ['VERIFIED_HISTORY', 'NO_HISTORY', 'CONFLICTED'])
    || !member(value.outcome, ['ACCEPTED', 'NO_CHANGE', 'SOURCE_BLOCKED', 'POLICY_BLOCKED', 'CONFLICTED'])
    || !(value.reason === null || typeof value.reason === 'string' && reasons.has(value.reason))
    || !Array.isArray(value.transition_ids) || !value.transition_ids.every(text)
    || new Set(value.transition_ids).size !== value.transition_ids.length
    || !Array.isArray(value.observation_references)
    || !value.observation_references.every((item) => object(item) && text(item.signal_id) && text(item.fingerprint))) return null;
  const transition = value.last_transition;
  if (transition !== null && (!object(transition) || !text(transition.transition_id)
    || !text(transition.fingerprint) || !member(transition.next_state, ['CURRENT', 'INVALIDATED', 'SUPERSEDED'])
    || instant(transition.transition_as_of) === null || instant(transition.known_at) === null
    || instant(transition.transition_as_of)! > instant(asOf)! || instant(transition.known_at)! > instant(asOf)!
    || value.transition_ids.at(-1) !== transition.transition_id)) return null;
  if ((value.availability === 'VERIFIED_HISTORY') !== (transition !== null)
    || (value.availability === 'CONFLICTED') !== (value.outcome === 'CONFLICTED')
    || (value.availability !== 'VERIFIED_HISTORY' && (value.transition_ids.length || value.observation_references.length))) return null;
  // Server verifies lineage. This consumer validates the envelope, not its hashes.
  const checked = value as unknown as P1History;
  return {
    schema_version: checked.schema_version, canonical_instrument_id: instrument,
    as_of: checked.as_of, availability: checked.availability, outcome: checked.outcome,
    reason: checked.reason, actionability: 'WATCH_ONLY', execution_status: 'NON_EXECUTABLE',
    expiry: 'EXPIRY_NOT_GOVERNED_FOR_THIS_PATH',
    last_transition: checked.last_transition ? {
      transition_id: checked.last_transition.transition_id,
      fingerprint: checked.last_transition.fingerprint,
      next_state: checked.last_transition.next_state,
      transition_as_of: checked.last_transition.transition_as_of,
      known_at: checked.last_transition.known_at,
    } : null,
    transition_ids: [...checked.transition_ids],
    observation_references: checked.observation_references.map(({ signal_id, fingerprint }) => ({ signal_id, fingerprint })),
  };
}

export async function readP1History(
  origin: string, instrument: string, asOf: string, signal?: AbortSignal,
): Promise<P1ReadResult> {
  if (instrument.length > 128 || !/^NSE:[A-Za-z0-9._:-]+$/.test(instrument) || instant(asOf) === null) {
    return { state: 'INVALID_QUERY', code: 'EXACT_IDENTITY_AND_AWARE_CUTOFF_REQUIRED' };
  }
  let url: URL;
  try {
    url = new URL(origin);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
      || url.search || url.hash || url.pathname !== '/') throw new Error();
    if (url.protocol !== 'https:' && !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) throw new Error();
    url.pathname = '/api/v1/p1-signals/lifecycle';
    url.search = new URLSearchParams({ canonical_instrument_id: instrument, as_of: asOf }).toString();
  } catch {
    return { state: 'INVALID_QUERY', code: 'INVALID_BACKEND_ORIGIN' };
  }
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal?.addEventListener('abort', cancel, { once: true });
  if (signal?.aborted) cancel();
  const timer = setTimeout(cancel, 6000);
  try {
    if (controller.signal.aborted) return { state: 'CANCELLED', code: 'REQUEST_CANCELLED' };
    const response = await fetch(url, {
      method: 'GET', signal: controller.signal, cache: 'no-store', redirect: 'error',
      credentials: 'omit', headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      let code = `HTTP_${response.status}`;
      try {
        const body: unknown = await response.json();
        if (object(body) && object(body.error) && typeof body.error.code === 'string' && safeErrors.has(body.error.code)) code = body.error.code;
      } catch { /* No raw server text or credentials are displayed. */ }
      return { state: 'UNAVAILABLE', code };
    }
    const data = parseP1History(await response.json(), instrument, asOf);
    return data ? { state: 'HISTORY', data } : { state: 'INVALID_RESPONSE', code: 'P1_RESPONSE_CONTRACT_MISMATCH' };
  } catch {
    if (controller.signal.aborted) return signal?.aborted
      ? { state: 'CANCELLED', code: 'REQUEST_CANCELLED' }
      : { state: 'TIMEOUT', code: 'P1_QUERY_TIMEOUT' };
    return { state: 'UNAVAILABLE', code: 'P1_TRANSPORT_OR_RESPONSE_UNAVAILABLE' };
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', cancel);
  }
}
