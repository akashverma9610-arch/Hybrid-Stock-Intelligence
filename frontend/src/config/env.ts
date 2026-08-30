/**
 * Environment configuration for NSE Stock Manager v2.1 Frontend Shell
 */

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const rawUseMock = import.meta.env.VITE_USE_MOCK_DATA;

export const config = {
  apiBaseUrl: rawApiBaseUrl.replace(/\/+$/, ''), // strip trailing slashes
  // Default to mock data = false (live FastAPI backend mode)
  useMockData: rawUseMock === 'true' || rawUseMock === true,
  appVersion: 'v2.1.0-shell',
  appName: 'NSE Stock Manager',
  refreshIntervalMs: 15000,
};
