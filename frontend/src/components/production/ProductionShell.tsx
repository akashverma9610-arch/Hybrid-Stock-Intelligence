import React, { useState } from 'react';
import { Activity, Bell, BriefcaseBusiness, ChevronRight, Compass, Menu, Newspaper, Radio, RefreshCw, ScanSearch, X } from 'lucide-react';
import { useDataClient } from '../../api/context';
import { AppRoute, useNavigation } from '../../context/NavigationContext';

const items: Array<{ label: string; route: AppRoute; path: string; icon: React.ReactNode }> = [
  { label: 'Home', route: 'home', path: '/', icon: <Compass className="h-4 w-4" /> },
  { label: 'Opportunities', route: 'opportunities', path: '/opportunities', icon: <ScanSearch className="h-4 w-4" /> },
  { label: 'Market-Wide Watch', route: 'market-wide-watch', path: '/market-wide-watch', icon: <Activity className="h-4 w-4" /> },
  { label: 'Stocks', route: 'stocks', path: '/stocks', icon: <Activity className="h-4 w-4" /> },
  { label: 'Portfolio', route: 'portfolio', path: '/portfolio', icon: <BriefcaseBusiness className="h-4 w-4" /> },
  { label: 'Rotation', route: 'rotation', path: '/rotation', icon: <RefreshCw className="h-4 w-4" /> },
  { label: 'Live', route: 'live', path: '/live', icon: <Radio className="h-4 w-4" /> },
  { label: 'Intelligence', route: 'intelligence', path: '/intelligence', icon: <Newspaper className="h-4 w-4" /> },
];

export const ProductionShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { route, navigate } = useNavigation();
  const { triggerRefresh, isMockMode } = useDataClient();
  const [open, setOpen] = useState(false);
  const isActive = (item: typeof items[number]) => route === item.route || (item.route === 'stocks' && route === 'stock-detail');

  return <div className="min-h-screen bg-[#f7f8f6] text-[#17201c]">
    <header className="sticky top-0 z-30 border-b border-[#dfe4de] bg-[#f7f8f6]/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8">
        <button onClick={() => navigate('/')} className="flex items-center gap-2.5 text-left" aria-label="HSI home"><span className="grid h-8 w-8 place-items-center rounded-lg bg-[#173c31] text-sm font-bold text-white">H</span><span><span className="block text-sm font-semibold tracking-tight">HSI</span><span className="block text-[10px] text-[#637068]">Hybrid Stock Intelligence</span></span></button>
        <nav className="hidden items-center gap-1 lg:flex">{items.map((item) => <button key={item.route} onClick={() => navigate(item.path)} className={`rounded-md px-3 py-2 text-sm transition-colors ${isActive(item) ? 'bg-[#dcebe3] text-[#173c31] font-semibold' : 'text-[#526058] hover:bg-[#e9eeea]'}`}>{item.label}</button>)}</nav>
        <div className="flex items-center gap-2"><button onClick={triggerRefresh} className="rounded-md border border-[#d5ddd7] p-2 text-[#526058] hover:bg-white" title="Refresh backend evidence"><RefreshCw className="h-4 w-4" /></button><button onClick={() => navigate('/dev')} className="hidden items-center gap-1 rounded-md border border-[#d5ddd7] px-2.5 py-2 text-xs font-medium text-[#526058] hover:bg-white sm:flex">Development Console <ChevronRight className="h-3.5 w-3.5" /></button><button onClick={() => setOpen((value) => !value)} className="rounded-md border border-[#d5ddd7] p-2 lg:hidden" aria-label="Open production navigation">{open ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}</button></div>
      </div>
      {isMockMode && <div className="border-t border-amber-200 bg-amber-50 px-4 py-1.5 text-center text-xs text-amber-800">Simulated frontend fixture mode — this is not backend production evidence.</div>}
      {open && <nav className="border-t border-[#dfe4de] bg-[#f7f8f6] p-3 lg:hidden">{items.map((item) => <button key={item.route} onClick={() => { navigate(item.path); setOpen(false); }} className={`flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm ${isActive(item) ? 'bg-[#dcebe3] font-semibold text-[#173c31]' : 'text-[#526058]'}`}>{item.icon}{item.label}</button>)}<button onClick={() => { navigate('/dev'); setOpen(false); }} className="mt-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm text-[#526058]"><Bell className="h-4 w-4" />Development Console</button></nav>}
    </header>
    <main className="mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">{children}</main>
    <footer className="border-t border-[#dfe4de] px-4 py-5 text-center text-xs text-[#637068]">HSI presents backend-governed evidence. It does not place orders or provide execution instructions.</footer>
  </div>;
};
