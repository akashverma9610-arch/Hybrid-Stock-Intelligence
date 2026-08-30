import React from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { NavigationProvider, useNavigation } from './context/NavigationContext';
import { DataClientProvider } from './api/context';
import { AppShell } from './components/layout/AppShell';

// Routed Pages
import { DashboardPage } from './pages/DashboardPage';
import { PortfolioPage } from './pages/PortfolioPage';
import { CapitalRotationPage } from './pages/CapitalRotationPage';
import { StocksPage } from './pages/StocksPage';
import { StockDetailPage } from './pages/StockDetailPage';
import { SignalsPage } from './pages/SignalsPage';
import { PaperTradingPage } from './pages/PaperTradingPage';
import { PerformancePage } from './pages/PerformancePage';
import { PrimaryMarketPage } from './pages/PrimaryMarketPage';
import { NewsPage } from './pages/NewsPage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemHealthPage } from './pages/SystemHealthPage';

const AppContent: React.FC = () => {
  const { route } = useNavigation();

  const renderActivePage = () => {
    switch (route) {
      case 'dashboard':
        return <DashboardPage />;
      case 'portfolio':
        return <PortfolioPage />;
      case 'rotation':
        return <CapitalRotationPage />;
      case 'stocks':
        return <StocksPage />;
      case 'stock-detail':
        return <StockDetailPage />;
      case 'signals':
        return <SignalsPage />;
      case 'paper-trading':
        return <PaperTradingPage />;
      case 'performance':
        return <PerformancePage />;
      case 'primary-market':
        return <PrimaryMarketPage />;
      case 'news':
        return <NewsPage />;
      case 'settings':
        return <SettingsPage />;
      case 'system-health':
        return <SystemHealthPage />;
      default:
        return <DashboardPage />;
    }
  };

  return <AppShell>{renderActivePage()}</AppShell>;
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
