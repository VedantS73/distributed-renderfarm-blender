import React from 'react';
import { ConfigProvider, theme as antTheme } from 'antd';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { NetworkProvider } from './context/NetworkContext';
import AppLayout from './pages/components/Layout';

const App = () => {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
};

const AppContent = () => {
  const { isDarkMode } = useTheme();
  
  return (
    <NetworkProvider>
      <ConfigProvider
        theme={{
          algorithm: isDarkMode ? antTheme.darkAlgorithm : antTheme.defaultAlgorithm,
          token: {
            borderRadius: 6,
            colorPrimary: '#1890ff',
          },
        }}
      >
        <AppLayout />
      </ConfigProvider>
    </NetworkProvider>
  );
};

export default App;