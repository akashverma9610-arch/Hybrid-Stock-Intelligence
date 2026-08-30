import React, { useEffect, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  Clock,
  Database,
  Radio,
  RefreshCw,
  Server,
  Shield,
  Zap,
} from 'lucide-react';
import { useDataClient } from '../api/context';
import { ApiResponse } from '../types/api';
import { SystemHealthData, SourceHealth } from '../types/systemHealth';
import { SectionHeader } from '../components/common/SectionHeader';
import { StatusBadge } from '../components/common/StatusBadge';
import { ApiStateWrapper } from '../components/common/ApiStateWrapper';
import { WarningBanner } from '../components/common/WarningBanner';
import { FreshnessBadge } from '../components/common/FreshnessBadge';

export const SystemHealthPage: React.FC = () => {
  const { client, refreshTrigger, triggerRefresh } = useDataClient();
  const [healthRes, setHealthRes] = useState<ApiResponse<SystemHealthData> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchHealth = async () => {
      setLoading(true);
      try {
        const res = await client.getSystemHealth();
        if (isMounted) setHealthRes(res);
      } catch (err) {
        console.error('Failed to load system health:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchHealth();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger]);

  return (
    <div id="system-health-page" className="space-y-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            System & Data Feed Health Monitor
          </h1>
          <p className="text-xs sm:text-sm text-gray-400 mt-0.5">
            Real-time operational status of backend services, scheduler cycles, and external feed pipelines
          </p>
        </div>

        <button
          id="health-refresh-btn"
          onClick={triggerRefresh}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#161616] border border-[#333] hover:border-gray-500 text-xs font-semibold text-gray-200 hover:text-white transition-colors self-start sm:self-auto"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh Feeds</span>
        </button>
      </div>

      <ApiStateWrapper<SystemHealthData>
        response={healthRes}
        isLoading={loading}
        skeletonType="card"
        skeletonRows={4}
        onRetry={triggerRefresh}
      >
        {(health: SystemHealthData) => (
          <div className="space-y-6">
            {/* System Status Overview Header */}
            <div className="bg-[#161616] border border-[#222] rounded-lg p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center justify-center font-bold">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Backend Core Runtime
                  </div>
                  <div className="text-lg font-bold text-white flex items-center gap-2 mt-0.5">
                    <span>FastAPI Core</span>
                    <StatusBadge status={health.runtimeStatus === 'OPERATIONAL' ? 'ONLINE' : 'DEGRADED'} />
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 text-xs font-mono text-gray-400 flex-wrap">
                <div>
                  <span className="text-gray-500">Uptime:</span>{' '}
                  <strong className="text-gray-200">
                    {health.uptimeSeconds !== null ? `${Math.floor(health.uptimeSeconds / 3600)}h ${Math.floor((health.uptimeSeconds % 3600) / 60)}m` : '—'}
                  </strong>
                </div>
                <div>
                  <span className="text-gray-500">Environment:</span>{' '}
                  <strong className="text-gray-200">{health.environment}</strong>
                </div>
              </div>
            </div>

            {/* Scheduler Status */}
            <div className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Clock className="w-4 h-4 text-blue-400" />
                  <span>Cycle Scheduler & Ingestion Heartbeat</span>
                </h3>
                <StatusBadge status={health.schedulerStatus === 'ACTIVE' ? 'ONLINE' : 'DEGRADED'} />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-xs">
                <div className="p-3 rounded bg-black/40 border border-[#222]">
                  <div className="text-[10px] text-gray-500 uppercase font-sans">Scheduler State</div>
                  <div className="font-bold text-white mt-1">{health.schedulerStatus}</div>
                </div>
                <div className="p-3 rounded bg-black/40 border border-[#222]">
                  <div className="text-[10px] text-gray-500 uppercase font-sans">Last Completed Cycle</div>
                  <div className="font-bold text-white mt-1">{health.lastCycleRunTime ?? '—'}</div>
                </div>
                <div className="p-3 rounded bg-black/40 border border-[#222]">
                  <div className="text-[10px] text-gray-500 uppercase font-sans">Next Scheduled Run</div>
                  <div className="font-bold text-emerald-400 mt-1">{health.nextScheduledCycle ?? '—'}</div>
                </div>
              </div>
            </div>

            {/* Data Feed Providers Table */}
            <div className="bg-[#161616] border border-[#222] rounded-lg p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-purple-400" />
                  <span>External Ingestion & Data Sources Status</span>
                </h3>
                <span className="text-xs font-mono text-gray-500">
                  {health.sources.length} Feed{health.sources.length === 1 ? '' : 's'} Active
                </span>
              </div>

              {health.sources.length === 0 ? (
                <div className="p-4 rounded border border-[#222] bg-black/20 text-center text-xs text-gray-400">
                  No individual data feed providers reported by backend runtime.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-[#111] border-b border-[#222] text-[10px] uppercase tracking-wider text-gray-400">
                      <tr>
                        <th className="py-2.5 px-3">Feed / Pipeline</th>
                        <th className="py-2.5 px-3">Category</th>
                        <th className="py-2.5 px-3 text-center">Status</th>
                        <th className="py-2.5 px-3 text-right">Latency</th>
                        <th className="py-2.5 px-3 text-center">Freshness</th>
                        <th className="py-2.5 px-3 text-right">Last Sync</th>
                        <th className="py-2.5 px-3">Notes / Warnings</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#222]">
                      {health.sources.map((f, idx) => (
                        <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                          <td className="py-2.5 px-3 font-semibold text-white">{f.name}</td>
                          <td className="py-2.5 px-3 font-mono text-gray-400">{f.category}</td>
                          <td className="py-2.5 px-3 text-center">
                            <StatusBadge status={f.status === 'HEALTHY' ? 'ONLINE' : f.status === 'DEGRADED' ? 'DEGRADED' : 'OFFLINE'} />
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-gray-300">
                            {f.latencyMs !== null ? `${f.latencyMs} ms` : '—'}
                          </td>
                          <td className="py-2.5 px-3 text-center">
                            <FreshnessBadge freshness={f.freshness} size="sm" />
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-gray-400 text-[11px]">
                            {f.lastSuccessTimestamp || '—'}
                          </td>
                          <td className="py-2.5 px-3 text-gray-400 text-[11px] max-w-xs truncate">
                            {f.warningNote || '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Active Warnings if any */}
            {health.systemWarnings && health.systemWarnings.length > 0 && (
              <WarningBanner
                type="warning"
                title="Active Operational Warnings"
                message={
                  <ul className="list-disc list-inside space-y-0.5">
                    {health.systemWarnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                }
              />
            )}
          </div>
        )}
      </ApiStateWrapper>
    </div>
  );
};
