import React, { createContext, useContext, useMemo, useState } from 'react';
import { config } from '../config/env';
import { DataClientInterface } from './clientInterface';
import { MockDataClient } from './mockClient';
import { HttpDataClient } from './httpClient';

interface DataClientContextType {
  client: DataClientInterface;
  isMockMode: boolean;
  setMockMode: (mock: boolean) => void;
  apiBaseUrl: string;
  setApiBaseUrl: (url: string) => void;
  backendConnected: boolean | null; // null = checking, true = ok, false = offline
  setBackendConnected: (status: boolean | null) => void;
  refreshTrigger: number;
  triggerRefresh: () => void;
}

const DataClientContext = createContext<DataClientContextType | null>(null);

export const DataClientProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isMockMode, setIsMockMode] = useState<boolean>(() => {
    // The deployment setting is authoritative at startup.  A stale browser
    // preference must not silently turn an API-mode deployment into mock mode.
    return config.useMockData;
  });

  const [apiBaseUrl, setApiBaseUrlState] = useState<string>(() => {
    // Likewise, start against the configured local API rather than a prior
    // browser-session override.  A user may still explicitly change it later.
    return config.apiBaseUrl;
  });

  const [backendConnected, setBackendConnected] = useState<boolean | null>(isMockMode ? true : null);
  const [refreshTrigger, setRefreshTrigger] = useState<number>(0);

  const setMockMode = (val: boolean) => {
    setIsMockMode(val);
    localStorage.setItem('nse_use_mock_data', String(val));
    if (val) {
      setBackendConnected(true);
    }
  };

  const setApiBaseUrl = (url: string) => {
    setApiBaseUrlState(url);
    localStorage.setItem('nse_api_base_url', url);
  };

  const triggerRefresh = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const client = useMemo<DataClientInterface>(() => {
    if (isMockMode) {
      return new MockDataClient();
    }
    return new HttpDataClient(apiBaseUrl);
  }, [isMockMode, apiBaseUrl]);

  const value = {
    client,
    isMockMode,
    setMockMode,
    apiBaseUrl,
    setApiBaseUrl,
    backendConnected,
    setBackendConnected,
    refreshTrigger,
    triggerRefresh,
  };

  return <DataClientContext.Provider value={value}>{children}</DataClientContext.Provider>;
};

export function useDataClient() {
  const context = useContext(DataClientContext);
  if (!context) {
    throw new Error('useDataClient must be used within a DataClientProvider');
  }
  return context;
}
