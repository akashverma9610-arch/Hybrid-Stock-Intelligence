import React, { createContext, useContext, useEffect, useState } from 'react';

export type AppRoute =
  | 'dashboard'
  | 'portfolio'
  | 'rotation'
  | 'stocks'
  | 'stock-detail'
  | 'signals'
  | 'paper-trading'
  | 'performance'
  | 'primary-market'
  | 'news'
  | 'settings'
  | 'system-health';

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

  if (!clean || segments[0] === 'dashboard') {
    return { currentRoute: 'dashboard', params: {}, pathname: '/dashboard' };
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
        params: { symbol: segments[1].toUpperCase() },
        pathname: `/stocks/${segments[1].toUpperCase()}`,
      };
    }
    return { currentRoute: 'stocks', params: {}, pathname: '/stocks' };
  }

  if (segments[0] === 'signals') {
    return { currentRoute: 'signals', params: {}, pathname: '/signals' };
  }

  if (segments[0] === 'paper-trading') {
    return { currentRoute: 'paper-trading', params: {}, pathname: '/paper-trading' };
  }

  if (segments[0] === 'performance') {
    return { currentRoute: 'performance', params: {}, pathname: '/performance' };
  }

  if (segments[0] === 'primary-market' || segments[0] === 'ipo') {
    return { currentRoute: 'primary-market', params: {}, pathname: '/primary-market' };
  }

  if (segments[0] === 'news') {
    return { currentRoute: 'news', params: {}, pathname: '/news' };
  }

  if (segments[0] === 'settings') {
    return { currentRoute: 'settings', params: {}, pathname: '/settings' };
  }

  if (segments[0] === 'system-health' || segments[0] === 'health') {
    return { currentRoute: 'system-health', params: {}, pathname: '/system-health' };
  }

  return { currentRoute: 'dashboard', params: {}, pathname: '/dashboard' };
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
    navigate(`/stocks/${symbol.toUpperCase()}`);
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
