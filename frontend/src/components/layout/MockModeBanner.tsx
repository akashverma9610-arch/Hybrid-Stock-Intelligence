import React from 'react';
import { AlertCircle, ToggleLeft, ToggleRight } from 'lucide-react';
import { useDataClient } from '../../api/context';

export const MockModeBanner: React.FC = () => {
  const { isMockMode, setMockMode, apiBaseUrl } = useDataClient();

  if (!isMockMode) return null;

  return (
    <div
      id="mock-mode-warning-banner"
      className="w-full bg-amber-500/15 dark:bg-amber-950/40 border-b border-amber-500/40 px-4 py-1.5 text-xs text-amber-900 dark:text-amber-200 flex items-center justify-between gap-3 flex-wrap"
    >
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center px-1.5 py-0.5 rounded font-black tracking-wider text-[10px] bg-amber-500 text-slate-950 uppercase">
          MOCK DATA
        </span>
        <span className="font-medium text-[11px] sm:text-xs">
          Frontend is rendering isolated simulated fixture data for local verification. Live backend API is not queried.
        </span>
      </div>

      <div className="flex items-center gap-3">
        <button
          id="toggle-mock-to-api-btn"
          onClick={() => setMockMode(false)}
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-900 dark:text-amber-100 border border-amber-500/50 text-[11px] font-semibold transition-colors"
          title={`Switch to live API at ${apiBaseUrl}`}
        >
          <ToggleLeft className="w-3.5 h-3.5" />
          <span>Switch to API Mode ({apiBaseUrl})</span>
        </button>
      </div>
    </div>
  );
};
