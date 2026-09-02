import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { MockModeBanner } from './MockModeBanner';
import { useDataClient } from '../../api/context';

interface AppShellProps {
  children: React.ReactNode;
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { isMockMode } = useDataClient();

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-gray-100 flex font-sans antialiased selection:bg-blue-500/30">
      {/* Sidebar for Desktop & Drawer for Mobile */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64 relative bg-[#0a0a0a]">
        {/* Top-Right Mock Data Mode corner badge (as shown in Design HTML) */}
        {isMockMode && (
          <div
            id="mock-mode-corner-tag"
            className="absolute top-0 right-0 px-3 py-1 bg-amber-500/20 text-amber-400 text-[10px] font-bold tracking-tighter z-40 border-b border-l border-amber-500/30 font-mono"
          >
            MOCK DATA MODE
          </div>
        )}

        {/* Top bar */}
        <TopBar onOpenSidebar={() => setSidebarOpen(true)} />

        {/* Mock Mode Banner */}
        <MockModeBanner />

        {/* Page Content Container */}
        <main
          id="main-page-container"
          className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6"
        >
          {children}
        </main>

        {/* Product context only.  Runtime status is rendered from backend read models. */}
        <footer
          id="app-status-footer"
          className="h-8 bg-[#111] border-t border-[#222] flex items-center px-4 sm:px-6 justify-between text-[10px] font-mono text-gray-500 uppercase shrink-0"
        >
          <div className="flex items-center gap-4">
            <span className="text-gray-400">HSI Development Console</span>
            <span className="hidden sm:inline text-gray-500">•</span>
            <span className="hidden sm:inline text-gray-400">Read-only observability</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-gray-400">Backend state is rendered where exposed</span>
            <span className="text-gray-500">NOT_EXPOSED otherwise</span>
          </div>
        </footer>
      </div>
    </div>
  );
};
