import React from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { DataClientProvider } from './api/context';
import { AppShell } from './components/layout/AppShell';
import { SenseEdgeShell } from './components/senseedge/SenseEdgeShell';
import { SenseEdgePages } from './components/senseedge/SenseEdgePages';
import { P1LifecyclePanel } from './components/production/P1LifecyclePanel';

// Routed Pages
import { DevHealthDashboardPage } from './pages/DevHealthDashboardPage';
import {
  ProductionIntelligencePage,
  ProductionLivePage,
  ProductionMarketWideWatchPage,
  ProductionRotationPage,
  ProductionStockDetailPage,
  ProductionStocksPage,
} from './pages/ProductionPages';

const AppContent: React.FC = () => {
  const { route, params } = useNavigation();

  const renderDevPage = () => {
    switch (route) {
      case 'dev-data-providers':
        return <DevHealthDashboardPage focus="data-providers" />;
      case 'dev-external-intelligence':
        return <DevHealthDashboardPage focus="external-intelligence" />;
      case 'dev-brain-inspector':
        return <DevHealthDashboardPage focus="brain-inspector" />;
      case 'dev-opportunity-setup':
        return <DevHealthDashboardPage focus="opportunity-setup" />;
      case 'dev-portfolio-runtime':
        return <DevHealthDashboardPage focus="portfolio-runtime" />;
      case 'dev-policies-audit':
        return <DevHealthDashboardPage focus="policies-audit" />;
      case 'dev-system-health':
        return <DevHealthDashboardPage focus="system-health" />;
      default:
        return <DevHealthDashboardPage />;
    }
  };

  const isDev = route.startsWith('dev-');
  if (isDev) return <AppShell>{renderDevPage()}</AppShell>;

  const renderProductionPage = () => {
    switch (route) {
      case 'opportunities': return <SenseEdgePages page="opportunities" />;
      case 'signals': return <SenseEdgePages page="signals" />;
      case 'market-wide-watch': return <ProductionMarketWideWatchPage />;
      case 'stocks': return <ProductionStocksPage />;
      case 'stock-detail': return (
        <div className="space-y-7">
          <ProductionStockDetailPage canonicalInstrumentId={params.canonicalInstrumentId || ''} />
          {params.canonicalInstrumentId && <P1LifecyclePanel key={params.canonicalInstrumentId} instrument={params.canonicalInstrumentId} />}
        </div>
      );
      case 'portfolio': return <SenseEdgePages page="portfolio" />;
      case 'rotation': return <ProductionRotationPage />;
      case 'live': return <ProductionLivePage />;
      case 'intelligence': return <ProductionIntelligencePage />;
      case 'home':
      default: return <SenseEdgePages page="home" />;
    }
  };

  const redesigned = ['home', 'opportunities', 'portfolio', 'signals'].includes(route);
  return <SenseEdgeShell>{redesigned ? renderProductionPage() : <div className="se-legacy">{renderProductionPage()}</div>}</SenseEdgeShell>;
};

export default function App() {
  return (
    <ThemeProvider>
      <NavigationProvider>
        <DataClientProvider>
          <AppContent />
        </DataClientProvider>
      </NavigationProvider>
    </ThemeProvider>
  );
}
