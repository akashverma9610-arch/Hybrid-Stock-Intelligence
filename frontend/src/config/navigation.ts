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
  { id: 'nav-system-health', label: 'System Health', route: 'dev-system-health', path: '/dev/system-health', iconName: 'Activity', category: 'MAIN' },
  { id: 'nav-data-providers', label: 'Data & Providers', route: 'dev-data-providers', path: '/dev/data-providers', iconName: 'Database', category: 'MAIN' },
  { id: 'nav-external-intelligence', label: 'External Intelligence', route: 'dev-external-intelligence', path: '/dev/external-intelligence', iconName: 'Radio', category: 'MAIN' },
  { id: 'nav-brain-inspector', label: 'Shared Brain Inspector', route: 'dev-brain-inspector', path: '/dev/brain-inspector', iconName: 'Brain', category: 'MAIN' },
  { id: 'nav-opportunity-setup', label: 'Opportunity / Setup', route: 'dev-opportunity-setup', path: '/dev/opportunity-setup', iconName: 'Target', category: 'MAIN' },
  { id: 'nav-portfolio-runtime', label: 'Portfolio Runtime', route: 'dev-portfolio-runtime', path: '/dev/portfolio-runtime', iconName: 'Briefcase', category: 'MAIN' },
  { id: 'nav-policies-audit', label: 'Policies & Audit', route: 'dev-policies-audit', path: '/dev/policies-audit', iconName: 'Shield', category: 'SYSTEM' },
];
