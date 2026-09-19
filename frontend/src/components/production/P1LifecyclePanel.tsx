import React, { useEffect, useRef, useState } from 'react';
import { useDataClient } from '../../api/context';
import { P1ReadResult, readP1History } from '../../api/p1Lifecycle';

export const P1LifecyclePanel: React.FC<{ instrument: string }> = ({ instrument }) => {
  const { apiBaseUrl, isMockMode } = useDataClient();
  const [asOf, setAsOf] = useState('');
  const [result, setResult] = useState<P1ReadResult | null>(null);
  const [loading, setLoading] = useState(false);
  const active = useRef<AbortController | null>(null);

  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    active.current?.abort();
    setResult(null);
    setLoading(false);
  }, [instrument, apiBaseUrl, isMockMode]);

  const read = async (event: React.FormEvent) => {
    event.preventDefault();
    if (isMockMode) return;
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setResult(null);
    const response = await readP1History(apiBaseUrl, instrument, asOf, controller.signal);
    if (!controller.signal.aborted && active.current === controller) {
      setResult(response);
      setLoading(false);
    }
  };
  const history = result?.state === 'HISTORY' ? result.data : null;
  return (
    <section className="rounded-xl border border-[#dbe4dd] bg-white p-6" aria-label="P1 Watch lifecycle">
      <h2 className="text-lg font-semibold">Watch lifecycle · retained evidence</h2>
      <p className="mt-2 text-sm text-[#637068]">WATCH_ONLY / NON_EXECUTABLE. CURRENT means last confirmed qualification, not a live recommendation. INVALIDATED is not a sell instruction.</p>
      <form onSubmit={read} className="mt-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">Explicit evidence cutoff (timezone required)
          <input aria-label="P1 as-of cutoff" value={asOf} placeholder="YYYY-MM-DDTHH:mm:ss+05:30"
            onChange={(event) => { active.current?.abort(); setLoading(false); setResult(null); setAsOf(event.target.value); }}
            className="w-80 max-w-full rounded border border-[#cfd8d1] p-2 font-mono text-xs" required />
        </label>
        <button disabled={loading || isMockMode || !asOf} className="rounded bg-[#173c31] px-4 py-2 text-sm text-white disabled:opacity-50">
          {loading ? 'Reading retained history…' : 'Read history'}
        </button>
      </form>
      <div role="status" aria-live="polite" className="mt-4 space-y-2 text-sm">
        {isMockMode && <p>Unavailable in demo mode. No synthetic P1 history is substituted.</p>}
        {!isMockMode && !result && !loading && <p>No query performed. Enter a cutoff; no current-time assumption is made.</p>}
        {result && result.state !== 'HISTORY' && <p>{result.state}: {result.code}. No history has been promoted into a signal.</p>}
        {history && <>
          <p>{history.availability} · {history.outcome}{history.reason ? ` · ${history.reason}` : ''}</p>
          <p className="font-mono text-xs">{history.canonical_instrument_id} · as-of {history.as_of}</p>
          {history.availability === 'NO_HISTORY' && <p>No retained chain at this cutoff. This does not mean no market opportunities.</p>}
          {history.availability === 'CONFLICTED' && <p>History could not be verified. No lifecycle state is displayed.</p>}
          {history.last_transition && <>
            <p>Last confirmed state: {history.last_transition.next_state}</p>
            <p>Transition as-of: {history.last_transition.transition_as_of} · Known at: {history.last_transition.known_at}</p>
            <p>{history.transition_ids.length} retained transitions · {history.observation_references.length} observation references</p>
            <details><summary className="cursor-pointer">Inspect canonical lineage</summary>
              <p className="mt-2 break-all font-mono text-xs">{history.last_transition.fingerprint}</p>
              <ul className="mt-2 space-y-1 break-all font-mono text-xs">{history.transition_ids.map((id) => <li key={id}>{id}</li>)}</ul>
            </details>
          </>}
        </>}
      </div>
      <p className="mt-4 text-xs text-[#637068]">No synthetic expiry. Strength, confidence, materiality and execution instructions are not supplied by this view. This read does not refresh or acquire evidence.</p>
    </section>
  );
};
