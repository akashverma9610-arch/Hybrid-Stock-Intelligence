import React, { createContext, useContext, useEffect, useState } from 'react';

export type AppRoute =
  | 'home'
  | 'opportunities'
  | 'market-wide-watch'
  | 'stocks'
  | 'stock-detail'
  | 'portfolio'
  | 'rotation'
  | 'live'
  | 'intelligence'
  | 'dev-system-health'
  | 'dev-data-providers'
  | 'dev-external-intelligence'
  | 'dev-brain-inspector'
  | 'dev-opportunity-setup'
  | 'dev-portfolio-runtime'
  | 'dev-policies-audit';

interface RouteState {
  currentRoute: AppRoute;
  params: Record<string, string>;
  pathname: string;
}

interface NavigationContextType {
  route: AppRoute;
  params: Record<string, string>;
  pathname: string;
  navigate: (path: string) => void;
  navigateToStock: (symbol: string) => void;
}

const NavigationContext = createContext<NavigationContextType | null>(null);

function parsePath(path: string): RouteState {
  // Normalize path
  const clean = path.replace(/^[#/]+/, '').replace(/\/+$/, '');
  const segments = clean.split('/');

  if (!clean || segments[0] === 'home') {
    return { currentRoute: 'home', params: {}, pathname: '/' };
  }

  if (segments[0] === 'portfolio') {
    return { currentRoute: 'portfolio', params: {}, pathname: '/portfolio' };
  }

  if (segments[0] === 'rotation' || segments[0] === 'capital-rotation') {
    return { currentRoute: 'rotation', params: {}, pathname: '/rotation' };
  }

  if (segments[0] === 'stocks') {
    if (segments[1]) {
      return {
        currentRoute: 'stock-detail',
        params: { canonicalInstrumentId: decodeURIComponent(segments.slice(1).join('/')) },
        pathname: `/stocks/${segments.slice(1).join('/')}`,
      };
    }
    return { currentRoute: 'stocks', params: {}, pathname: '/stocks' };
  }

  if (segments[0] === 'opportunities') {
    return { currentRoute: 'opportunities', params: {}, pathname: '/opportunities' };
  }

  if (segments[0] === 'market-wide-watch') {
    return { currentRoute: 'market-wide-watch', params: {}, pathname: '/market-wide-watch' };
  }

  if (segments[0] === 'live') {
    return { currentRoute: 'live', params: {}, pathname: '/live' };
  }

  if (segments[0] === 'intelligence') {
    return { currentRoute: 'intelligence', params: {}, pathname: '/intelligence' };
  }

  const devRoute = segments[0] === 'dev' ? (segments[1] || 'system-health') : null;
  if (devRoute === 'system-health' || devRoute === 'health') return { currentRoute: 'dev-system-health', params: {}, pathname: '/dev/system-health' };
  if (devRoute === 'data-providers') return { currentRoute: 'dev-data-providers', params: {}, pathname: '/dev/data-providers' };
  if (devRoute === 'external-intelligence') return { currentRoute: 'dev-external-intelligence', params: {}, pathname: '/dev/external-intelligence' };
  if (devRoute === 'brain-inspector') return { currentRoute: 'dev-brain-inspector', params: {}, pathname: '/dev/brain-inspector' };
  if (devRoute === 'opportunity-setup') return { currentRoute: 'dev-opportunity-setup', params: {}, pathname: '/dev/opportunity-setup' };
  if (devRoute === 'portfolio-runtime') return { currentRoute: 'dev-portfolio-runtime', params: {}, pathname: '/dev/portfolio-runtime' };
  if (devRoute === 'policies-audit') return { currentRoute: 'dev-policies-audit', params: {}, pathname: '/dev/policies-audit' };

  // Preserve prior Development Console deep links without exposing them in production navigation.
  const legacyDevRoutes: Record<string, AppRoute> = {
    'system-health': 'dev-system-health',
    'data-providers': 'dev-data-providers',
    'external-intelligence': 'dev-external-intelligence',
    'brain-inspector': 'dev-brain-inspector',
    'opportunity-setup': 'dev-opportunity-setup',
    'portfolio-runtime': 'dev-portfolio-runtime',
    'policies-audit': 'dev-policies-audit',
  };
  if (legacyDevRoutes[segments[0]]) {
    const route = legacyDevRoutes[segments[0]];
    return { currentRoute: route, params: {}, pathname: `/dev/${segments[0]}` };
  }

  return { currentRoute: 'home', params: {}, pathname: '/' };
}

export const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [routeState, setRouteState] = useState<RouteState>(() => {
    const hash = window.location.hash.slice(1);
    const path = hash || window.location.pathname;
    return parsePath(path);
  });

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      setRouteState(parsePath(hash));
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (path: string) => {
    const next = parsePath(path);
    setRouteState(next);
    window.location.hash = next.pathname;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const navigateToStock = (symbol: string) => {
    navigate(`/stocks/${encodeURIComponent(symbol)}`);
  };

  return (
    <NavigationContext.Provider
      value={{
        route: routeState.currentRoute,
        params: routeState.params,
        pathname: routeState.pathname,
        navigate,
        navigateToStock,
      }}
    >
      {children}
    </NavigationContext.Provider>
  );
};

export function useNavigation() {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used within a NavigationProvider');
  }
  return context;
}
