import React, { useState } from 'react';
import {
  Menu,
  Moon,
  RefreshCw,
  Sun,
} from 'lucide-react';
import { useNavigation } from '../../context/NavigationContext';
import { useTheme } from '../../context/ThemeContext';
import { useDataClient } from '../../api/context';

interface TopBarProps {
  onOpenSidebar: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({ onOpenSidebar }) => {
  const { route } = useNavigation();
  const { theme, toggleTheme } = useTheme();
  const { isMockMode, setMockMode, triggerRefresh } = useDataClient();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const getPageTitle = () => {
    switch (route) {
      case 'dashboard':
        return 'HSI Development Console';
      case 'system-health':
        return 'System Health';
      case 'data-providers':
        return 'Data & Providers';
      case 'external-intelligence':
        return 'External Intelligence';
      case 'brain-inspector':
        return 'Shared Brain Inspector';
      case 'opportunity-setup':
        return 'Opportunity / Setup Inspector';
      case 'portfolio-runtime':
        return 'Portfolio Runtime';
      case 'policies-audit':
        return 'Policies & Audit';
      default:
        return 'HSI Development Console';
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
          <span className="hidden sm:inline text-[10px] font-mono text-gray-500 uppercase">Read-only operator view</span>
        </div>
      </div>

      {/* Right section: Nifty Ticker + Indicators & Profile ID */}
      <div className="flex items-center gap-3 sm:gap-4 shrink-0">
        {/* Mock/Live API Switch Button */}
        <button
          id="topbar-mock-toggle-btn"
          onClick={() => setMockMode(!isMockMode)}
          className={`px-2.5 py-1 rounded text-xs font-semibold border transition-colors ${
            isMockMode
              ? 'bg-amber-500/15 border-amber-500/40 text-amber-400'
              : 'bg-blue-600/15 border-blue-500/40 text-blue-400'
          }`}
          title="Toggle between mock and backend API mode"
        >
          {isMockMode ? 'MOCK' : 'LIVE API'}
        </button>

        {/* Refresh button */}
        <button
          id="topbar-refresh-btn"
          onClick={handleRefresh}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-white/5 rounded-md transition-colors border border-[#222]"
          title="Refresh displayed backend read models"
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

        <div
          id="user-avatar-pill"
          className="w-8 h-8 rounded-full bg-[#1e1e1e] flex items-center justify-center text-xs border border-gray-700 text-gray-300 font-mono font-semibold"
          title="Development console"
        >
          DEV
        </div>
      </div>
    </header>
  );
};
