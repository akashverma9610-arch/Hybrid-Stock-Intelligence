import React, { useEffect, useRef, useState } from 'react';
import { Activity, Bell, BriefcaseBusiness, ChartNoAxesCombined, Download, House, Menu, MessageCircle, Radio, Search, Settings, ShieldCheck, UserRound, X } from 'lucide-react';
import { useNavigation } from '../../context/NavigationContext';
import { useDataClient } from '../../api/context';
import './senseedge.css';

const navigation = [
  { title: 'Home', path: '/', route: 'home', icon: House },
  { title: 'Opportunities', path: '/opportunities', route: 'opportunities', icon: ChartNoAxesCombined },
  { title: 'My Portfolio', path: '/portfolio', route: 'portfolio', icon: BriefcaseBusiness },
  { title: 'Signals', path: '/signals', route: 'signals', icon: Radio },
];
interface InstallPrompt extends Event { prompt(): Promise<void>; userChoice: Promise<{outcome: string}> }

export const SenseEdgeShell: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const { route, navigate } = useNavigation();
  const { isMockMode } = useDataClient();
  const [menu, setMenu] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [offline, setOffline] = useState(!navigator.onLine);
  const [install, setInstall] = useState<InstallPrompt | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const online = () => setOffline(!navigator.onLine);
    const prompt = (event: Event) => { event.preventDefault(); setInstall(event as InstallPrompt); };
    const keys = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); searchRef.current?.focus(); }
      if (event.key === 'Escape') { setNotice(null); setMenu(false); }
    };
    window.addEventListener('online', online); window.addEventListener('offline', online);
    window.addEventListener('beforeinstallprompt', prompt); window.addEventListener('keydown', keys);
    return () => { window.removeEventListener('online', online); window.removeEventListener('offline', online);
      window.removeEventListener('beforeinstallprompt', prompt); window.removeEventListener('keydown', keys); };
  }, []);
  const go = (path: string) => { navigate(path); setMenu(false); setNotice(null); };
  const installApp = async () => {
    if (!install) { setNotice('Install from your browser menu when offered. On iPhone: Share → Add to Home Screen. HTTPS is required outside localhost. This app does not store financial data for offline use.'); return; }
    try { await install.prompt(); await install.userChoice; }
    catch { setNotice('Installation was not completed. You can keep using the website.'); }
    finally { setInstall(null); }
  };
  return <div className="se-app">
    <a className="se-skip" href="#senseedge-main" onClick={event => { event.preventDefault(); document.getElementById('senseedge-main')?.focus(); }}>Skip to content</a>
    <header className="se-header">
      <button className="se-mobile-menu se-icon-button" aria-label="Toggle navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}>{menu ? <X/> : <Menu/>}</button>
      <button className="se-brand" onClick={() => go('/')} aria-label="SenseEdge home"><span className="se-logo"><Activity/></span><span><strong>Sense<span>Edge</span></strong><small>Powered by HSI Intelligence Engine</small></span></button>
      <form className="se-global-search" onSubmit={(event) => { event.preventDefault();
        if (/^NSE:[A-Za-z0-9._:-]+$/.test(search.trim())) go(`/stocks/${encodeURIComponent(search.trim())}`);
        else { go('/stocks'); setNotice('Use the canonical stock directory to resolve a company. No identity is guessed from search text.'); } }}>
        <Search size={17}/><input ref={searchRef} aria-label="Search canonical company" placeholder="Search companies or enter a canonical NSE ID…" value={search} onChange={(e) => setSearch(e.target.value)}/><kbd>⌘ K</kbd>
      </form>
      <span className="se-pilot"><i/> {isMockMode ? 'Demo' : 'Research'}</span>
      <button className="se-icon-button" aria-label="Notifications status" onClick={() => setNotice('Notification delivery is not connected. Material evidence is available in Intelligence; there is no unread-alert count to display.')}><Bell size={19}/></button>
      <button className="se-profile" onClick={() => setNotice('Local owner workspace. Online authentication is not configured; this badge is not a login or access-control guarantee.')}><span className="se-avatar"><UserRound size={19}/></span><span>Owner workspace<small>Private access pending</small></span></button>
    </header>
    <aside className={`se-sidebar ${menu ? 'is-open' : ''}`} aria-label="Main navigation">
      <nav>{navigation.map(({ title, route: itemRoute, path, icon: Icon }) => <button key={path} aria-current={route === itemRoute ? 'page' : undefined} className={route === itemRoute ? 'active' : ''} onClick={() => go(path)}><Icon size={21}/>{title}</button>)}
        <button onClick={() => setNotice('Ask HSI is not connected to an approved AI query workflow in this interface yet. AI cannot invent evidence, scores or trade authority.')}><MessageCircle size={21}/>Ask HSI<span className="se-soon">Soon</span></button>
      </nav>
      <div className="se-sidebar-bottom">
        <button onClick={installApp}><Download size={19}/>Install app</button>
        <button onClick={() => go('/dev/data-providers')}><Settings size={19}/>Settings / Dev Console</button>
        <button onClick={() => setNotice('Online account setup is pending. No identity or profile from the reference images has been copied.')}><UserRound size={19}/>Profile</button>
        <div className="se-brand-note">Build a Smarter<br/>Tomorrow<small>Intelligence · Discipline · Evidence</small></div>
      </div>
    </aside>
    <div className="se-workspace">
      {isMockMode && <div className="se-banner">DEMO MODE · Synthetic fixtures, not live financial evidence.</div>}
      {offline && <div role="alert" className="se-banner">OFFLINE · Financial evidence cannot be refreshed. Previously visible values are not live.</div>}
      {notice && <div className="se-notice" role="status"><ShieldCheck size={20}/><p>{notice}</p><button className="se-icon-button" aria-label="Dismiss notice" onClick={() => setNotice(null)}><X size={17}/></button></div>}
      <main id="senseedge-main" tabIndex={-1}>{children}</main>
      <footer className="se-footer"><ShieldCheck size={14}/> ONE HSI Brain · Evidence-only · No broker execution <span>WATCH_ONLY / NON_EXECUTABLE</span></footer>
    </div>
    <nav className="se-bottom-nav" aria-label="Mobile navigation">{navigation.map(({title,path,route:itemRoute,icon:Icon}) => <button key={path} aria-current={route === itemRoute ? 'page' : undefined} onClick={() => go(path)}><Icon size={20}/><span>{title === 'My Portfolio' ? 'Portfolio' : title}</span></button>)}</nav>
  </div>;
};
