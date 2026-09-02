import React from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { DataClientProvider } from './api/context';
import { AppShell } from './components/layout/AppShell';
import { ProductionShell } from './components/production/ProductionShell';

// Routed Pages
import { DevHealthDashboardPage } from './pages/DevHealthDashboardPage';
import {
  ProductionHomePage,
  ProductionIntelligencePage,
  ProductionLivePage,
  ProductionMarketWideWatchPage,
  ProductionOpportunitiesPage,
  ProductionPortfolioPage,
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
      case 'opportunities': return <ProductionOpportunitiesPage />;
      case 'market-wide-watch': return <ProductionMarketWideWatchPage />;
      case 'stocks': return <ProductionStocksPage />;
      case 'stock-detail': return <ProductionStockDetailPage canonicalInstrumentId={params.canonicalInstrumentId || ''} />;
      case 'portfolio': return <ProductionPortfolioPage />;
      case 'rotation': return <ProductionRotationPage />;
      case 'live': return <ProductionLivePage />;
      case 'intelligence': return <ProductionIntelligencePage />;
      case 'home':
      default: return <ProductionHomePage />;
    }
  };

  return <ProductionShell>{renderProductionPage()}</ProductionShell>;
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
