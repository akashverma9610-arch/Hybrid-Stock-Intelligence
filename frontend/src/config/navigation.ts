import { AppRoute } from '../context/NavigationContext';

export interface NavItemConfig {
  id: string;
  label: string;
  route: AppRoute;
  path: string;
  iconName: string;
  badge?: string;
  category?: 'MAIN' | 'SYSTEM';
}

export const NAVIGATION_ITEMS: NavItemConfig[] = [
  { id: 'nav-dashboard', label: 'Dashboard', route: 'dashboard', path: '/dashboard', iconName: 'LayoutDashboard', category: 'MAIN' },
  { id: 'nav-portfolio', label: 'Portfolio', route: 'portfolio', path: '/portfolio', iconName: 'Briefcase', category: 'MAIN' },
  { id: 'nav-rotation', label: 'Capital Rotation', route: 'rotation', path: '/rotation', iconName: 'ArrowLeftRight', badge: 'v2.1', category: 'MAIN' },
  { id: 'nav-stocks', label: 'Stocks Intelligence', route: 'stocks', path: '/stocks', iconName: 'Layers', category: 'MAIN' },
  { id: 'nav-signals', label: 'Signals & Rationale', route: 'signals', path: '/signals', iconName: 'Radio', category: 'MAIN' },
  { id: 'nav-paper-trading', label: 'Paper Trading', route: 'paper-trading', path: '/paper-trading', iconName: 'Target', category: 'MAIN' },
  { id: 'nav-performance', label: 'Performance & Alpha', route: 'performance', path: '/performance', iconName: 'LineChart', category: 'MAIN' },
  { id: 'nav-primary-market', label: 'Primary Market (IPO)', route: 'primary-market', path: '/primary-market', iconName: 'Sparkles', category: 'MAIN' },
  { id: 'nav-news', label: 'News & Catalysts', route: 'news', path: '/news', iconName: 'Newspaper', category: 'MAIN' },
  { id: 'nav-settings', label: 'Settings & Feeds', route: 'settings', path: '/settings', iconName: 'Sliders', category: 'SYSTEM' },
  { id: 'nav-system-health', label: 'System Health', route: 'system-health', path: '/system-health', iconName: 'Activity', category: 'SYSTEM' },
];
