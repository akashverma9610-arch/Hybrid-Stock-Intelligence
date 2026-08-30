import React, { useEffect, useState } from 'react';
import {
  Activity,
  ChevronRight,
  Menu,
  Moon,
  RefreshCw,
  Server,
  Sun,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';
import { useDataClient } from '../../api/context';

interface TopBarProps {
  onOpenSidebar: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenSidebar }) => {
  const { route, params, navigate } = useNavigation();
  const { theme, toggleTheme } = useTheme();
  const { client, isMockMode, setMockMode, apiBaseUrl, triggerRefresh, refreshTrigger } = useDataClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [liveNifty, setLiveNifty] = useState<{ spot: number | null; pChange: number | null } | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchNifty = async () => {
      try {
        const res = await client.getMarketState();
        if (isMounted && res.data?.nifty50) {
          setLiveNifty({
            spot: res.data.nifty50.spot,
            pChange: res.data.nifty50.pChange,
          });
        } else if (isMounted && !isMockMode) {
          setLiveNifty(null);
        }
      } catch {
        if (isMounted && !isMockMode) setLiveNifty(null);
      }
    };
    fetchNifty();
    return () => {
      isMounted = false;
    };
  }, [client, refreshTrigger, isMockMode]);

  const getPageTitle = () => {
    switch (route) {
      case 'dashboard':
        return 'Market Dashboard';
      case 'portfolio':
        return 'Portfolio Health & Holdings';
      case 'rotation':
        return 'Capital Rotation Engine';
      case 'stocks':
        return 'NSE Equity Universe';
      case 'stock-detail':
        return `Equity Intelligence — ${params.symbol || 'STOCK'}`;
      case 'signals':
        return 'Proprietary Action Signals';
      case 'paper-trading':
        return 'Paper Trading & Thesis';
      case 'performance':
        return 'Performance & Alpha Attribution';
      case 'primary-market':
        return 'Primary Market & IPO Pipeline';
      case 'news':
        return 'Market News & Catalysts';
      case 'settings':
        return 'Settings & Provider Connections';
      case 'system-health':
        return 'System & Feed Health';
      default:
        return 'Market Dashboard';
    }
  };

  const handleRefresh = () => {
    setIsRefreshing(true);
    triggerRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  return (
    <header
      id="app-topbar"
      className="sticky top-0 z-30 h-16 border-b border-[#222] bg-[#111] px-4 sm:px-8 flex items-center justify-between gap-4 transition-colors text-gray-100"
    >
      {/* Left section: Hamburger (mobile) + Header Title & Live Status */}
      <div className="flex items-center gap-4 sm:gap-6 truncate">
        <button
          id="open-sidebar-mobile-btn"
          onClick={onOpenSidebar}
          className="p-2 -ml-2 text-gray-400 hover:text-white rounded-md lg:hidden"
          aria-label="Open navigation menu"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-4 truncate">
          <h2 className="text-base sm:text-xl font-semibold tracking-tight text-white truncate">
            {getPageTitle()}
          </h2>
          <div className="hidden sm:block h-4 w-[1px] bg-gray-700 shrink-0" />
          <div className="hidden sm:flex items-center gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-wider font-mono">
              Live Market
            </span>
            <span className="text-xs text-gray-400 font-mono">
              IST Live
            </span>
          </div>
        </div>
      </div>

      {/* Right section: Nifty Ticker + Indicators & Profile ID */}
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* NIFTY 50 Header Ticker Widget */}
        <div className="hidden md:block text-right pr-2">
          <div className="text-xs font-semibold text-gray-300">NIFTY 50</div>
          {liveNifty && liveNifty.spot !== null ? (
            <div className={`text-[10px] font-mono font-medium ${(liveNifty.pChange ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {liveNifty.spot.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ({((liveNifty.pChange ?? 0) >= 0 ? '+' : '') + (liveNifty.pChange ?? 0).toFixed(2)}%)
            </div>
          ) : isMockMode ? (
            <div className="text-[10px] text-emerald-400 font-mono font-medium">
              24,865.25 (+0.62%)
            </div>
          ) : (
            <div className="text-[10px] text-gray-500 font-mono font-medium">
              Live API
            </div>
          )}
        </div>

        {/* Mock/Live API Switch Button */}
        <button
          id="topbar-mock-toggle-btn"
          onClick={() => setMockMode(!isMockMode)}
          className={`px-2.5 py-1 rounded text-xs font-semibold border transition-colors ${
            isMockMode
              ? 'bg-amber-500/15 border-amber-500/40 text-amber-400'
              : 'bg-blue-600/15 border-blue-500/40 text-blue-400'
          }`}
          title="Toggle between Mock Data and Live API Mode"
        >
          {isMockMode ? 'MOCK' : 'LIVE API'}
        </button>

        {/* Refresh button */}
        <button
          id="topbar-refresh-btn"
          onClick={handleRefresh}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-md transition-colors border border-[#222]"
          title="Refresh All Feeds"
          aria-label="Refresh data"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
        </button>

        {/* Theme Toggle Button */}
        <button
          id="topbar-theme-toggle-btn"
          onClick={toggleTheme}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-md transition-colors border border-[#222]"
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-gray-300" />}
        </button>

        {/* User Identity badge as in design HTML */}
        <div
          id="user-avatar-pill"
          className="w-8 h-8 rounded-full bg-[#1e1e1e] flex items-center justify-center text-xs border border-gray-700 text-gray-300 font-mono font-semibold"
          title="User: ADM_CHINMAY"
        >
          ID
        </div>
      </div>
    </header>
  );
};

