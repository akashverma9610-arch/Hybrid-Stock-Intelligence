import React from 'react';
import { Key, Lock, RefreshCw, AlertTriangle, ShieldCheck } from 'lucide-react';
import { ConnectionProviderStatus } from '../../types/connections';
import { StatusBadge } from '../common/StatusBadge';

interface GenericProviderCardProps {
  provider: ConnectionProviderStatus;
  credentials: Record<string, string>;
  onCredentialChange: (field: string, value: string) => void;
  onValidate: () => Promise<void>;
  isValidating: boolean;
  validationResult: { success: boolean; message: string } | null;
}

export const GenericProviderCard: React.FC<GenericProviderCardProps> = ({
  provider,
  credentials,
  onCredentialChange,
  onValidate,
  isValidating,
  validationResult,
}) => {
  const isKotak = provider.id === 'kotak_neo';
  const isGDFL = provider.id === 'global_datafeeds';
  const isGNews = provider.id === 'gnews';

  const hasToken = provider.hasSavedToken ?? provider.configured ?? false;

  return (
    <div
      id={`provider-card-${provider.id}`}
      className="bg-[#161616] border border-[#222] rounded-lg p-5 flex flex-col justify-between space-y-4"
    >
      <div className="space-y-3.5">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-bold text-sm sm:text-base text-white">
                {provider.name}
              </span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono border ${
                  provider.isOptional
                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                    : isKotak
                    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                    : 'bg-purple-500/15 text-purple-300 border-purple-500/30'
                }`}
              >
                {provider.roleBadge || (provider.isOptional ? 'OPTIONAL' : 'PRIMARY')}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-0.5">
              {provider.roleDescription}
            </p>
          </div>

          <div className="self-start">
            <StatusBadge status={provider.status} />
          </div>
        </div>

        {/* Optional notice if GFDL */}
        {provider.isOptional && (
          <div className="p-2 rounded bg-amber-500/10 border border-amber-500/20 text-amber-300/90 text-[11px]">
            <strong>Optional Provider:</strong> Upstox is the primary provider for Historical OHLCV. GFDL is optional for specialized tick feeds.
          </div>
        )}

        {/* Status flags */}
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1 text-xs font-mono">
          <span className="text-gray-400 font-mono">
            {provider.category.replace(/_/g, ' ')}
          </span>
          <span className="text-gray-600">•</span>
          <span className={`font-semibold ${provider.configured ? 'text-emerald-400' : 'text-gray-500'}`}>
            {provider.configured ? 'Configured' : 'Unconfigured'}
          </span>
          <span className="text-gray-600">•</span>
          <span className={`font-semibold ${provider.validated ? 'text-blue-400' : 'text-gray-500'}`}>
            {provider.validated ? 'Validated' : 'Not Validated'}
          </span>
          {provider.latencyMs !== null && (
            <>
              <span className="text-gray-600">•</span>
              <span className="text-gray-400">{provider.latencyMs}ms</span>
            </>
          )}
        </div>

        {/* Capabilities */}
        <div className="space-y-1">
          <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
            Capabilities
          </div>
          <div className="flex flex-wrap gap-1">
            {provider.capabilities.map((cap, i) => (
              <span
                key={i}
                className="text-[10px] px-1.5 py-0.5 rounded bg-black/40 text-gray-300 font-mono border border-[#222]"
              >
                {cap}
              </span>
            ))}
          </div>
        </div>

        {/* Ephemeral Inputs */}
        <div className="pt-2.5 border-t border-[#222] space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-gray-300 flex items-center gap-1.5">
              <Key className="w-3 h-3 text-gray-400" />
              <span>Authentication Credentials</span>
            </span>

            {hasToken && (
              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                <Lock className="w-2.5 h-2.5" />
                <span>SAVED</span>
              </span>
            )}
          </div>

          {isKotak && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input
                type="password"
                placeholder={hasToken ? '•••••••• (Consumer Key Saved)' : 'Consumer Key'}
                value={credentials.consumerKey || ''}
                onChange={(e) => onCredentialChange('consumerKey', e.target.value)}
                autoComplete="off"
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
              <input
                type="password"
                placeholder={hasToken ? '•••••••• (Consumer Secret Saved)' : 'Consumer Secret'}
                value={credentials.consumerSecret || ''}
                onChange={(e) => onCredentialChange('consumerSecret', e.target.value)}
                autoComplete="off"
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
              <input
                type="text"
                placeholder="Mobile Number"
                value={credentials.mobile || ''}
                onChange={(e) => onCredentialChange('mobile', e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
              <input
                type="password"
                placeholder="MPIN"
                value={credentials.mpin || ''}
                onChange={(e) => onCredentialChange('mpin', e.target.value)}
                autoComplete="off"
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
            </div>
          )}

          {isGDFL && (
            <div className="space-y-2">
              <input
                type="password"
                placeholder={hasToken ? '•••••••• (API Token Saved)' : 'Datafeed API Token'}
                value={credentials.apiToken || ''}
                onChange={(e) => onCredentialChange('apiToken', e.target.value)}
                autoComplete="off"
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
              <input
                type="text"
                placeholder="Server Host (Optional)"
                value={credentials.serverHost || ''}
                onChange={(e) => onCredentialChange('serverHost', e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
              />
            </div>
          )}

          {isGNews && (
            <input
              type="password"
              placeholder={hasToken ? '•••••••• (API Key Saved)' : 'GNews API Key'}
              value={credentials.apiKey || ''}
              onChange={(e) => onCredentialChange('apiKey', e.target.value)}
              autoComplete="off"
              className="w-full text-xs px-2.5 py-1.5 bg-black/50 border border-[#333] rounded text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500 font-mono"
            />
          )}

          {validationResult && (
            <div
              className={`p-2 rounded text-[11px] font-mono border ${
                validationResult.success
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}
            >
              {validationResult.message}
            </div>
          )}
        </div>
      </div>

      {/* Action button */}
      <div className="pt-2 border-t border-[#1f1f1f] space-y-1.5">
        <button
          id={`validate-btn-${provider.id}`}
          onClick={onValidate}
          disabled={isValidating}
          className="w-full py-1.5 px-3 rounded bg-[#222] hover:bg-[#333] border border-[#444] text-white text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 min-h-[36px]"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isValidating ? 'animate-spin text-blue-400' : ''}`} />
          <span>{isValidating ? 'Validating on Backend...' : 'Validate Connection'}</span>
        </button>
        <div className="text-[10px] text-gray-500 text-center font-mono">
          Last Validated: {provider.lastValidatedTimestamp || 'Never'}
        </div>
      </div>
    </div>
  );
};
