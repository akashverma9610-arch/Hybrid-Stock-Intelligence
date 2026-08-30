import React from 'react';
import {
  Activity,
  ArrowLeftRight,
  Briefcase,
  Layers,
  LayoutDashboard,
  LineChart,
  Newspaper,
  Radio,
  Shield,
  Sliders,
  Sparkles,
  Target,
  X,
} from 'lucide-react';
import { NAVIGATION_ITEMS } from '../../config/navigation';
import { useNavigation } from '../../context/NavigationContext';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { route, navigate } = useNavigation();

  const getIcon = (iconName: string) => {
    switch (iconName) {
      case 'LayoutDashboard':
        return <LayoutDashboard className="w-4 h-4" />;
      case 'Briefcase':
        return <Briefcase className="w-4 h-4" />;
      case 'ArrowLeftRight':
        return <ArrowLeftRight className="w-4 h-4" />;
      case 'Layers':
        return <Layers className="w-4 h-4" />;
      case 'Radio':
        return <Radio className="w-4 h-4" />;
      case 'Target':
        return <Target className="w-4 h-4" />;
      case 'LineChart':
        return <LineChart className="w-4 h-4" />;
      case 'Sparkles':
        return <Sparkles className="w-4 h-4" />;
      case 'Newspaper':
        return <Newspaper className="w-4 h-4" />;
      case 'Sliders':
        return <Sliders className="w-4 h-4" />;
      case 'Activity':
        return <Activity className="w-4 h-4" />;
      default:
        return <LayoutDashboard className="w-4 h-4" />;
    }
  };

  const mainItems = NAVIGATION_ITEMS.filter((i) => i.category === 'MAIN');
  const systemItems = NAVIGATION_ITEMS.filter((i) => i.category === 'SYSTEM');

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div
          id="mobile-sidebar-backdrop"
          onClick={onClose}
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-xs lg:hidden transition-opacity"
        />
      )}

      {/* Sidebar Container */}
      <aside
        id="app-sidebar"
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-[#111] border-r border-[#222] text-gray-100 flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="p-6 border-b border-[#222] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 bg-blue-600 rounded-xs flex items-center justify-center font-bold text-white text-[11px] shadow-xs">
              N
            </div>
            <div>
              <h1 className="font-bold text-base sm:text-lg tracking-tight text-white flex items-center gap-1.5">
                <span>NSE MANAGER</span>
                <span className="text-blue-500 font-mono text-xs">v2.1</span>
              </h1>
            </div>
          </div>

          <button
            id="close-sidebar-mobile-btn"
            onClick={onClose}
            className="p-1.5 text-gray-400 hover:text-white rounded lg:hidden"
            aria-label="Close sidebar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 py-4 overflow-y-auto space-y-5">
          <div>
            <div className="px-5 mb-2 text-[10px] uppercase tracking-widest text-gray-500 font-semibold">
              Main Menu
            </div>
            <div className="space-y-0.5">
              {mainItems.map((item) => {
                const isActive = route === item.route || (item.route === 'stocks' && route === 'stock-detail');
                return (
                  <button
                    key={item.id}
                    id={item.id}
                    onClick={() => {
                      navigate(item.path);
                      onClose();
                    }}
                    className={`w-full flex items-center justify-between px-6 py-2.5 text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-600/10 text-blue-400 border-r-2 border-blue-500'
                        : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-3 truncate">
                      <span className={isActive ? 'text-blue-400' : 'text-gray-500'}>
                        {getIcon(item.iconName)}
                      </span>
                      <span className="truncate">{item.label}</span>
                    </div>
                    {item.badge && (
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#1f1f1f] text-gray-400 font-mono">
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <div className="px-5 mb-2 text-[10px] uppercase tracking-widest text-gray-500 font-semibold">
              System & Config
            </div>
            <div className="space-y-0.5">
              {systemItems.map((item) => {
                const isActive = route === item.route;
                return (
                  <button
                    key={item.id}
                    id={item.id}
                    onClick={() => {
                      navigate(item.path);
                      onClose();
                    }}
                    className={`w-full flex items-center justify-between px-6 py-2.5 text-xs font-medium transition-colors ${
                      isActive
                        ? 'bg-blue-600/10 text-blue-400 border-r-2 border-blue-500'
                        : 'text-gray-400 hover:bg-white/5 hover:text-gray-200'
                    }`}
                  >
                    <div className="flex items-center gap-3 truncate">
                      <span className={isActive ? 'text-blue-400' : 'text-gray-500'}>
                        {getIcon(item.iconName)}
                      </span>
                      <span className="truncate">{item.label}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </nav>

        {/* System Health Section from Design HTML */}
        <div className="p-4 bg-[#0d0d0d] border-t border-[#222] shrink-0">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">
              System Health
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
            <div className="text-gray-400">
              KOTAK: <span className="text-emerald-400 font-semibold">OK</span>
            </div>
            <div className="text-gray-400">
              FEED: <span className="text-emerald-400 font-semibold">LIVE</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

