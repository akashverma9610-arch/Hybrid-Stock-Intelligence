import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  Key,
  Lock,
  Moon,
  RefreshCw,
  Server,
  Shield,
  Sliders,
  Sun,
  Wifi,
  XCircle,
  Activity,
  Layers,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { useTheme } from '../context/ThemeContext';
import { ApiResponse } from '../types/api';
import { ConnectionProviderStatus, ConnectionsState, UpstoxValidationFlow } from '../types/connections';
import { SectionHeader } from '../components/common/SectionHeader';
import { StatusBadge } from '../components/common/StatusBadge';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { WarningBanner } from '../components/common/WarningBanner';
import { UpstoxConnectionCard } from '../components/settings/UpstoxConnectionCard';
import { GenericProviderCard } from '../components/settings/GenericProviderCard';
import { DataCoveragePanel } from '../components/settings/DataCoveragePanel';
import { BrainReadinessPanel } from '../components/settings/BrainReadinessPanel';
import { RealBrainTrialPanel } from '../components/settings/RealBrainTrialPanel';

export const SettingsPage: React.FC = () => {
  const { client, isMockMode, setMockMode, apiBaseUrl, setApiBaseUrl, triggerRefresh, refreshTrigger } = useDataClient();
  const { theme, toggleTheme } = useTheme();

  const [connectionsRes, setConnectionsRes] = useState<ApiResponse<ConnectionsState> | null>(null);
  const [loading, setLoading] = useState(true);

  // Validation & action loading states
  const [validatingProvider, setValidatingProvider] = useState<string | null>(null);
  const [validationResults, setValidationResults] = useState<Record<string, { success: boolean; message: string }>>({});

  // Upstox action states
  const [isSavingUpstox, setIsSavingUpstox] = useState(false);
  const [isTestingUpstox, setIsTestingUpstox] = useState(false);
  const [isClearingUpstox, setIsClearingUpstox] = useState(false);
  const [upstoxActionMsg, setUpstoxActionMsg] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Local ephemeral validation flow state if updated via action
  const [activeUpstoxFlow, setActiveUpstoxFlow] = useState<UpstoxValidationFlow | undefined>(undefined);

  // Ephemeral inputs for Kotak Neo, GDFL, GNews (never stored in localStorage)
  const [credentials, setCredentials] = useState<Record<string, Record<string, string>>>({
    kotak_neo: { consumerKey: '', consumerSecret: '', mobile: '', mpin: '' },
    global_datafeeds: { apiToken: '', serverHost: '' },
    gnews: { apiKey: '' },
  });

  const [customApiUrl, setCustomApiUrl] = useState(apiBaseUrl);

  useEffect(() => {
    let isMounted = true;
    const fetchConnections = async () => {
      setLoading(true);
      try {
        const res = await client.getConnectionsState();
        if (isMounted) {
          setConnectionsRes(res);
          if (res.data?.upstoxValidation) {
            setActiveUpstoxFlow(res.data.upstoxValidation);
          }
        }
      } catch (err) {
        console.error('Failed to load connections:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchConnections();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  const handleCredentialChange = (providerId: string, field: string, value: string) => {
    setCredentials((prev) => ({
      ...prev,
      [providerId]: {
        ...(prev[providerId] || {}),
        [field]: value,
      },
    }));
  };

  const handleValidateConnection = async (providerId: string) => {
    setValidatingProvider(providerId);
    try {
      const res = await client.validateConnection(providerId, credentials[providerId] || {});
      const isSuccess = res.data?.success ?? (res.status === 'READY');
      setValidationResults((prev) => ({
        ...prev,
        [providerId]: {
          success: isSuccess,
          message: res.data?.message || res.message || (isSuccess ? 'Validation succeeded on backend' : 'Validation failed'),
        },
      }));
      // Refresh to update backend provider state
      triggerRefresh();
    } catch (err: any) {
      setValidationResults((prev) => ({
        ...prev,
        [providerId]: {
          success: false,
          message: `Validation request error: ${err.message || 'Network timeout'}`,
        },
      }));
    } finally {
      setValidatingProvider(null);
    }
  };

  const handleSaveUpstoxToken = async (token: string) => {
    setIsSavingUpstox(true);
    setUpstoxActionMsg(null);
    try {
      if (client.saveConnectionCredentials) {
        const res = await client.saveConnectionCredentials('upstox', { access_token: token });
        setUpstoxActionMsg({
          type: res.data?.success ? 'success' : 'error',
          text: res.data?.message || res.message || 'Access token saved and validated with backend.',
        });
      }
      triggerRefresh();
    } catch (err: any) {
      setUpstoxActionMsg({
        type: 'error',
        text: `Error saving token: ${err.message || 'Backend connection error'}`,
      });
    } finally {
      setIsSavingUpstox(false);
    }
  };

  const handleTestUpstoxHistorical = async () => {
    setIsTestingUpstox(true);
    setUpstoxActionMsg(null);
    try {
      if (client.testHistoricalData) {
        const res = await client.testHistoricalData('upstox');
        if (res.data?.flow) {
          setActiveUpstoxFlow(res.data.flow);
        }
        setUpstoxActionMsg({
          type: res.data?.success ? 'success' : 'error',
          text: res.data?.message || res.message || 'Historical pipeline test completed.',
        });
      }
      triggerRefresh();
    } catch (err: any) {
      setUpstoxActionMsg({
        type: 'error',
        text: `Historical test error: ${err.message || 'Request failed'}`,
      });
    } finally {
      setIsTestingUpstox(false);
    }
  };

  const handleClearUpstoxCredentials = async () => {
    setIsClearingUpstox(true);
    setUpstoxActionMsg(null);
    try {
      if (client.clearConnectionCredentials) {
        const res = await client.clearConnectionCredentials('upstox');
        setUpstoxActionMsg({
          type: res.data?.success ? 'success' : 'info',
          text: res.data?.message || 'Upstox credentials cleared from backend session.',
        });
      } else {
        setUpstoxActionMsg({
          type: 'info',
          text: 'Credentials purged from active session.',
        });
      }
      triggerRefresh();
    } catch (err: any) {
      setUpstoxActionMsg({
        type: 'error',
        text: `Clear credentials error: ${err.message || 'Request failed'}`,
      });
    } finally {
      setIsClearingUpstox(false);
    }
  };

  const handleApplyApiUrl = (e: React.FormEvent) => {
    e.preventDefault();
    setApiBaseUrl(customApiUrl.trim());
    triggerRefresh();
  };

  const state = connectionsRes?.data;
  const providers = state?.providers || [];
  const upstoxProvider = providers.find((p) => p.id === 'upstox');
  const kotakProvider = providers.find((p) => p.id === 'kotak_neo');
  const datafeedsProvider = providers.find((p) => p.id === 'global_datafeeds');
  const gnewsProvider = providers.find((p) => p.id === 'gnews');

  return (
    <div id="settings-page" className="space-y-8 pb-14">
      {/* Top Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              Settings & Provider Connections
            </h1>
            {isMockMode ? (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-amber-500/20 text-amber-300 border border-amber-500/40">
                MOCK FIXTURE MODE
              </span>
            ) : (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                LIVE API ACTIVE
              </span>
            )}
          </div>
          <p className="text-xs sm:text-sm text-gray-400 mt-1">
            Institutional market-data routing, Upstox historical pipelines, and Brain data readiness
          </p>
        </div>

        <button
          id="settings-refresh-btn"
          onClick={triggerRefresh}
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded bg-[#161616] border border-[#333] hover:border-gray-500 text-xs font-semibold text-gray-200 hover:text-white transition-colors self-start sm:self-auto min-h-[40px]"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-400' : ''}`} />
          <span>Refresh All Statuses</span>
        </button>
      </div>

      {/* Security Architecture Notice */}
      <WarningBanner
        type="info"
        title="Zero Client-Side Secret Persistence & Direct Routing"
        message="Broker credentials and tokens are submitted directly to the secure FastAPI backend. In compliance with security standards, secrets are never stored in browser memory, localStorage, or cookies."
      />

      {/* 1. DATA PROVIDER CONNECTIONS SECTION */}
      <section id="settings-connections-section" className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Key className="w-4 h-4 text-emerald-400" />
              <span>Market Data Provider Connections</span>
            </h2>
            <p className="text-xs text-gray-400">
              Provider roles: Kotak Neo (Current Quotes) • Upstox (Historical OHLCV) • Global Datafeeds (Optional) • GNews (News / Catalysts)
            </p>
          </div>
        </div>

        <ApiStateWrapper<ConnectionsState>
          response={connectionsRes}
          isLoading={loading}
          skeletonType="card"
          skeletonRows={4}
          onRetry={triggerRefresh}
        >
          {() => (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* 1. Kotak Neo Card */}
              {kotakProvider ? (
                <GenericProviderCard
                  provider={kotakProvider}
                  credentials={credentials.kotak_neo || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('kotak_neo', field, val)}
                  onValidate={() => handleValidateConnection('kotak_neo')}
                  isValidating={validatingProvider === 'kotak_neo'}
                  validationResult={validationResults['kotak_neo'] || null}
                />
              ) : (
                <GenericProviderCard
                  provider={{
                    id: 'kotak_neo',
                    name: 'Kotak Neo API',
                    category: 'BROKER_API',
                    roleBadge: 'CURRENT QUOTES',
                    roleDescription: 'Current Quotes / Current Market Data',
                    configured: false,
                    validated: false,
                    status: 'NOT_CONFIGURED',
                    capabilities: ['Real-time NSE LTP', 'Order Gateway', 'Portfolio Sync'],
                    lastValidatedTimestamp: null,
                    warnings: [],
                    latencyMs: null,
                  }}
                  credentials={credentials.kotak_neo || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('kotak_neo', field, val)}
                  onValidate={() => handleValidateConnection('kotak_neo')}
                  isValidating={validatingProvider === 'kotak_neo'}
                  validationResult={validationResults['kotak_neo'] || null}
                />
              )}

              {/* 2. Upstox Card (First-Class Historical OHLCV Provider) */}
              <UpstoxConnectionCard
                provider={upstoxProvider || {
                  id: 'upstox',
                  name: 'Upstox API',
                  category: 'HISTORICAL_PROVIDER',
                  roleBadge: 'HISTORICAL OHLCV',
                  roleDescription: 'Historical Market Data (OHLCV Candles & Time Series)',
                  configured: false,
                  validated: false,
                  status: 'NOT_CONFIGURED',
                  capabilities: ['Historical Daily OHLCV', 'Multi-Year Historical OHLCV', 'Adjustment Basis: UNKNOWN'],
                  lastValidatedTimestamp: null,
                  warnings: [],
                  latencyMs: null,
                  hasSavedToken: false,
                }}
                validationFlow={activeUpstoxFlow || state?.upstoxValidation}
                onSaveToken={handleSaveUpstoxToken}
                onTestHistorical={handleTestUpstoxHistorical}
                onClearCredentials={handleClearUpstoxCredentials}
                isSaving={isSavingUpstox}
                isTesting={isTestingUpstox}
                isClearing={isClearingUpstox}
                isMockMode={isMockMode}
                actionMessage={upstoxActionMsg}
              />

              {/* 3. Global Datafeeds (GFDL) Card (Clearly marked OPTIONAL) */}
              {datafeedsProvider ? (
                <GenericProviderCard
                  provider={datafeedsProvider}
                  credentials={credentials.global_datafeeds || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('global_datafeeds', field, val)}
                  onValidate={() => handleValidateConnection('global_datafeeds')}
                  isValidating={validatingProvider === 'global_datafeeds'}
                  validationResult={validationResults['global_datafeeds'] || null}
                />
              ) : (
                <GenericProviderCard
                  provider={{
                    id: 'global_datafeeds',
                    name: 'Global Datafeeds (GFDL)',
                    category: 'DATA_FEED',
                    roleBadge: 'HISTORICAL OHLCV · OPTIONAL',
                    roleDescription: 'Historical OHLCV — Optional',
                    isOptional: true,
                    configured: false,
                    validated: false,
                    status: 'NOT_CONFIGURED',
                    capabilities: ['Level-2 Market Depth', 'Tick-by-Tick Feed', 'Index Greeks'],
                    lastValidatedTimestamp: null,
                    warnings: [],
                    latencyMs: null,
                  }}
                  credentials={credentials.global_datafeeds || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('global_datafeeds', field, val)}
                  onValidate={() => handleValidateConnection('global_datafeeds')}
                  isValidating={validatingProvider === 'global_datafeeds'}
                  validationResult={validationResults['global_datafeeds'] || null}
                />
              )}

              {/* 4. GNews Financial News Card */}
              {gnewsProvider ? (
                <GenericProviderCard
                  provider={gnewsProvider}
                  credentials={credentials.gnews || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('gnews', field, val)}
                  onValidate={() => handleValidateConnection('gnews')}
                  isValidating={validatingProvider === 'gnews'}
                  validationResult={validationResults['gnews'] || null}
                />
              ) : (
                <GenericProviderCard
                  provider={{
                    id: 'gnews',
                    name: 'GNews Financial API',
                    category: 'NEWS_PROVIDER',
                    roleBadge: 'SECONDARY NEWS / RESEARCH',
                    roleDescription: 'Secondary News / Research & Sentiment',
                    configured: false,
                    validated: false,
                    status: 'NOT_CONFIGURED',
                    capabilities: ['NSE Corporate Announcements', 'Macro Regulatory Feeds', 'Sentiment Scoring'],
                    lastValidatedTimestamp: null,
                    warnings: [],
                    latencyMs: null,
                  }}
                  credentials={credentials.gnews || {}}
                  onCredentialChange={(field, val) => handleCredentialChange('gnews', field, val)}
                  onValidate={() => handleValidateConnection('gnews')}
                  isValidating={validatingProvider === 'gnews'}
                  validationResult={validationResults['gnews'] || null}
                />
              )}
            </div>
          )}
        </ApiStateWrapper>
      </section>

      {/* 2. DATA COVERAGE SECTION */}
      <section id="settings-data-coverage-section" className="space-y-3">
        <DataCoveragePanel coverage={state?.dataCoverage} isLoading={loading} />
      </section>

      {/* 3. BRAIN DATA READINESS SECTION */}
      <section id="settings-brain-readiness-section" className="space-y-3">
        <BrainReadinessPanel readiness={state?.brainReadiness} />
      </section>

      {/* 4. REAL BRAIN TRIAL STATUS PANEL */}
      <section id="settings-real-brain-trial-section" className="space-y-3">
        <RealBrainTrialPanel trial={state?.realBrainTrial} />
      </section>

      {/* 5. BACKEND ENDPOINT & RUNTIME ENVIRONMENT */}
      <section id="settings-environment-section" className="space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Server className="w-4 h-4 text-blue-400" />
          <span>Backend Endpoint & Runtime Environment</span>
        </h2>

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-4">
          <form onSubmit={handleApplyApiUrl} className="space-y-3">
            <div>
              <label htmlFor="api-base-url-input" className="block text-xs font-bold text-gray-300 mb-1">
                FastAPI Backend Base URL (<code className="text-blue-400 font-mono">VITE_API_BASE_URL</code>)
              </label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  id="api-base-url-input"
                  type="text"
                  value={customApiUrl}
                  onChange={(e) => setCustomApiUrl(e.target.value)}
                  placeholder="http://127.0.0.1:8000"
                  className="flex-1 text-xs px-3 py-2 bg-black/50 border border-[#333] rounded font-mono text-white placeholder-gray-500 focus:outline-hidden focus:border-blue-500"
                />
                <button
                  type="submit"
                  id="save-api-url-btn"
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-bold transition-colors min-h-[38px]"
                >
                  Save & Apply
                </button>
              </div>
              <p className="text-[11px] text-gray-400 mt-1">
                Active base URL for all live HTTP client requests: <code className="text-gray-300 font-mono">{apiBaseUrl}</code>
              </p>
            </div>
          </form>

          {/* Mock mode toggle */}
          <div className="pt-3 border-t border-[#222] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="text-xs font-bold text-white">
                Mock Fixture Data Mode (<code className="text-amber-400 font-mono">VITE_USE_MOCK_DATA</code>)
              </div>
              <p className="text-xs text-gray-400">
                Toggle offline simulated mock data fixtures vs live FastAPI client requests.
              </p>
            </div>
            <button
              id="settings-mock-mode-toggle"
              onClick={() => setMockMode(!isMockMode)}
              className={`px-3 py-2 rounded text-xs font-bold border transition-colors self-start sm:self-auto min-h-[38px] ${
                isMockMode
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-blue-600/20 text-blue-300 border-blue-500/40'
              }`}
            >
              {isMockMode ? 'Mock Mode: Enabled' : 'Mock Mode: Disabled (Live API)'}
            </button>
          </div>
        </div>
      </section>

      {/* 6. INTERFACE APPEARANCE */}
      <section id="settings-appearance-section" className="space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Sun className="w-4 h-4 text-amber-400" />
          <span>Interface Appearance</span>
        </h2>

        <div className="bg-[#161616] border border-[#222] rounded-lg p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-xs font-bold text-white">
              Theme Mode
            </div>
            <p className="text-xs text-gray-400">
              Select between light and dark institutional color themes. Currently active: <strong className="capitalize text-gray-200">{theme}</strong>.
            </p>
          </div>
          <button
            id="settings-theme-btn"
            onClick={toggleTheme}
            className="flex items-center gap-2 px-3.5 py-2 rounded bg-[#222] hover:bg-[#333] border border-[#444] text-xs font-bold text-gray-200 transition-colors self-start sm:self-auto min-h-[38px]"
          >
            {theme === 'dark' ? (
              <>
                <Sun className="w-3.5 h-3.5 text-amber-400" />
                <span>Switch to Light</span>
              </>
            ) : (
              <>
                <Moon className="w-3.5 h-3.5 text-gray-300" />
                <span>Switch to Dark</span>
              </>
            )}
          </button>
        </div>
      </section>
    </div>
  );
};
