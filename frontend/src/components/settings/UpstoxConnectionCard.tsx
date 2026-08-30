import React, { useState } from 'react';
import {
  CheckCircle2,
  Database,
  Key,
  Lock,
  RefreshCw,
  Trash2,
  AlertCircle,
  Clock,
  Layers,
  FileCheck,
  HardDrive,
  Cpu,
  HelpCircle,
} from 'lucide-react';
import { ConnectionProviderStatus, UpstoxValidationFlow } from '../../types/connections';
import { StatusBadge } from '../common/StatusBadge';

interface UpstoxConnectionCardProps {
  provider?: ConnectionProviderStatus;
  validationFlow?: UpstoxValidationFlow;
  onSaveToken: (token: string) => Promise<void>;
  onTestHistorical: () => Promise<void>;
  onClearCredentials: () => Promise<void>;
  isSaving: boolean;
  isTesting: boolean;
  isClearing: boolean;
  isMockMode: boolean;
  actionMessage: { type: 'success' | 'error' | 'info'; text: string } | null;
}

export const UpstoxConnectionCard: React.FC<UpstoxConnectionCardProps> = ({
  provider,
  validationFlow,
  onSaveToken,
  onTestHistorical,
  onClearCredentials,
  isSaving,
  isTesting,
  isClearing,
  isMockMode,
  actionMessage,
}) => {
  const [tokenInput, setTokenInput] = useState('');

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    await onSaveToken(tokenInput.trim());
    setTokenInput(''); // Clear input after submission for security
  };

  const stages: {
    key: keyof Omit<UpstoxValidationFlow, 'lastTestedTimestamp' | 'errorMessage'>;
    label: string;
    description: string;
    icon: React.ElementType;
  }[] = [
    { key: 'credentials', label: 'Credentials', description: 'Analytics token validation for authenticated historical access', icon: Key },
    { key: 'instrumentResolution', label: 'Instrument Resolution', description: 'Backend NSE instrument key mapping', icon: Layers },
    { key: 'historicalAccess', label: 'Historical Access', description: 'Multi-year historical OHLCV candle query', icon: Database },
    { key: 'normalization', label: 'Normalization', description: 'Timestamp/Decimal canonical normalization; adjustment basis is explicit', icon: Cpu },
    { key: 'persistence', label: 'Persistence', description: 'Data tier storage & caching validation', icon: HardDrive },
  ];

  // Mock fixtures may demonstrate UI layout but are never evidence that a
  // local backend credential was stored.
  const backendConfigured = !isMockMode && provider?.configured === true;
  const hasToken = !isMockMode && provider?.hasSavedToken === true;

  return (
    <div
      id="provider-card-upstox"
      className="bg-[#161616] border border-[#222] rounded-lg p-5 flex flex-col justify-between space-y-5 transition-all"
    >
      <div className="space-y-4">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-base text-white tracking-wide">
                {provider?.name || 'Upstox API'}
              </span>
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-blue-500/15 text-blue-300 border border-blue-500/30">
                HISTORICAL OHLCV
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              Historical Market Data (Multi-Year OHLCV Candles; Adjustment Basis: UNKNOWN)
            </p>
          </div>

          <div className="self-start">
            <StatusBadge status={provider?.status || 'NOT_CONFIGURED'} />
          </div>
        </div>

        {/* Status Indicators */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs font-mono pt-1">
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Configured:</span>
            <span className={backendConfigured ? 'text-emerald-400 font-bold' : 'text-gray-500'}>
              {isMockMode ? 'MOCK — NOT PERSISTED' : backendConfigured ? 'YES' : 'NO'}
            </span>
          </div>
          <span className="text-gray-600">•</span>
          <div className="flex items-center gap-1.5">
            <span className="text-gray-400">Validated:</span>
            <span className={provider?.validated ? 'text-blue-400 font-bold' : 'text-gray-500'}>
              {provider?.validated ? 'YES' : 'NOT VALIDATED'}
            </span>
          </div>
          {provider?.latencyMs !== null && provider?.latencyMs !== undefined && (
            <>
              <span className="text-gray-600">•</span>
              <div className="flex items-center gap-1.5">
                <span className="text-gray-400">Latency:</span>
                <span className="text-gray-300">{provider.latencyMs}ms</span>
              </div>
            </>
          )}
        </div>

        {/* Capabilities */}
        <div className="space-y-1.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
            Provider Capabilities
          </div>
          <div className="flex flex-wrap gap-1.5">
            {(provider?.capabilities || ['Historical Daily OHLCV', 'Multi-Year Historical OHLCV', 'Adjustment Basis: UNKNOWN']).map(
              (cap, i) => (
                <span
                  key={i}
                  className="text-[10px] px-2 py-0.5 rounded bg-black/40 text-gray-300 font-mono border border-[#222]"
                >
                  {cap}
                </span>
              )
            )}
          </div>
        </div>

        {/* Upstox Access Token Form */}
        <div className="pt-3 border-t border-[#222] space-y-3">
          <div className="flex items-center justify-between">
            <label htmlFor="upstox-token-input" className="text-xs font-bold text-gray-300 flex items-center gap-1.5">
              <Key className="w-3.5 h-3.5 text-blue-400" />
              <span>Upstox Analytics Token</span>
            </label>

            {hasToken ? (
              <span
                id="upstox-token-saved-badge"
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30"
              >
                <Lock className="w-3 h-3" />
                <span>Analytics Token: SAVED</span>
              </span>
            ) : (
              <span className="text-[10px] font-mono text-gray-500">
                Not stored in backend session
              </span>
            )}
          </div>

          <form onSubmit={handleSave} className="space-y-2">
            <div className="relative">
              <input
                id="upstox-token-input"
                type="password"
                placeholder={hasToken ? '•••••••••••••••• (Token is saved securely)' : 'Paste Upstox Analytics Token'}
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                autoComplete="off"
                className="w-full text-xs px-3 py-2 bg-black/60 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono tracking-wider"
              />
            </div>

            <div className="text-[11px] text-gray-500">
              Stored securely on the backend and sent only as the documented bearer credential for Historical Candle V3 validation.
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
              <button
                type="submit"
                id="upstox-save-btn"
                disabled={isSaving || !tokenInput.trim()}
                className="py-2 px-3 rounded bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 disabled:hover:bg-blue-600 min-h-[40px]"
              >
                <Lock className="w-3.5 h-3.5" />
                <span>{isSaving ? 'Saving...' : 'SAVE CONNECTION'}</span>
              </button>

              <button
                type="button"
                id="upstox-test-historical-btn"
                onClick={onTestHistorical}
                disabled={isTesting || isSaving}
                className="py-2 px-3 rounded bg-[#222] hover:bg-[#333] border border-[#444] text-white text-xs font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 min-h-[40px]"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isTesting ? 'animate-spin text-blue-400' : ''}`} />
                <span>{isTesting ? 'Testing...' : 'TEST HISTORICAL DATA'}</span>
              </button>

              <button
                type="button"
                id="upstox-clear-btn"
                onClick={onClearCredentials}
                disabled={isClearing || isSaving}
                className="py-2 px-3 rounded bg-[#1a1414] hover:bg-[#2b1717] border border-rose-900/40 text-rose-300 text-xs font-bold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 min-h-[40px]"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>{isClearing ? 'Purging...' : 'CLEAR CREDENTIALS'}</span>
              </button>
            </div>
          </form>

          {/* Action Feedback Message */}
          {actionMessage && (
            <div
              id="upstox-action-feedback"
              className={`p-2.5 rounded text-xs font-mono border ${
                actionMessage.type === 'success'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : actionMessage.type === 'error'
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  : 'bg-blue-500/10 border-blue-500/30 text-blue-300'
              }`}
            >
              {actionMessage.text}
            </div>
          )}
        </div>

        {/* Validation Flow Sub-panel */}
        <div id="upstox-validation-flow" className="pt-3 border-t border-[#222] space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
              <Database className="w-3.5 h-3.5 text-blue-400" />
              <span>Historical Pipeline Validation Stages</span>
            </div>
            {validationFlow?.lastTestedTimestamp && (
              <span className="text-[10px] font-mono text-gray-500">
                Last Tested: {validationFlow.lastTestedTimestamp}
              </span>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2">
            {stages.map((stage) => {
              const currentStatus = validationFlow?.[stage.key] || 'NOT_TESTED';
              const Icon = stage.icon;

              return (
                <div
                  key={stage.key}
                  id={`upstox-stage-${stage.key}`}
                  className="bg-black/40 border border-[#262626] rounded p-2.5 flex flex-col justify-between space-y-2"
                >
                  <div className="flex items-center gap-1.5">
                    <Icon className="w-3 h-3 text-gray-400" />
                    <span className="text-[11px] font-semibold text-gray-200 truncate" title={stage.label}>
                      {stage.label}
                    </span>
                  </div>

                  <div className="pt-1">
                    <StatusBadge status={currentStatus} className="text-[9px] px-1.5 py-0" />
                  </div>
                </div>
              );
            })}
          </div>

          {validationFlow?.errorMessage && (
            <div className="text-xs text-rose-400 font-mono bg-rose-500/10 border border-rose-500/20 p-2 rounded">
              Stage failure: {validationFlow.errorMessage}
            </div>
          )}
        </div>
      </div>

      <div className="pt-2 border-t border-[#1f1f1f] text-[10px] text-gray-500 font-mono flex items-center justify-between">
        <span>Last Validated: {provider?.lastValidatedTimestamp || 'Never'}</span>
        <span>Role: Historical OHLCV Feed</span>
      </div>
    </div>
  );
};
