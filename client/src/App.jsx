import React, { createContext, useContext, useState } from 'react';
import { Layout, Menu, Switch, Button, Card, theme, Tooltip } from 'antd';
import { 
  BulbOutlined, 
  BulbFilled, 
  LeftOutlined, 
  RightOutlined,
  DesktopOutlined,
  DeploymentUnitOutlined,
  ClusterOutlined,
  FileAddOutlined
} from '@ant-design/icons';
import DevicesSystemSidebar from './pages/components/DevicesSystemSidebar';
import { NetworkProvider } from './context/NetworkContext';

// --- Main Page Components ---
import DeviceCheckPage from './pages/DeviceCheckPage';
import ElectionPage from './pages/ElectionPage';
import JobPage from './pages/JobPage';

const { Header, Content, Sider } = Layout;

// --- Constants ---
const SIDER_WIDTH_PERCENT = 40;
const HEADER_HEIGHT = 64;

// --- Theme Context (Unchanged logic, cleaner implementation) ---
const ThemeContext = createContext();

const ThemeProvider = ({ children }) => {
  const [isDarkMode, setIsDarkMode] = useState(true); // Default to dark for "Pro" feel
  
  const toggleTheme = () => setIsDarkMode(!isDarkMode);

  return (
    <ThemeContext.Provider value={{ isDarkMode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

const useTheme = () => useContext(ThemeContext);

// --- Components ---

// Reusable Card for consistency
const DashboardCard = ({ title, children, bordered = true }) => {
    const { token } = theme.useToken();
    return (
        <Card 
            title={title} 
            bordered={bordered}
            style={{ 
                height: '100%', 
                borderRadius: '8px',
                boxShadow: token.boxShadowTertiary 
            }}
        >
            {children}
        </Card>
    );
}

const AppLayout = () => {
  const { isDarkMode, toggleTheme } = useTheme();
  const [siderCollapsed, setSiderCollapsed] = useState(false);
  const [currentPage, setCurrentPage] = useState('device');

  const {
    token: { colorBgContainer, colorBgLayout, colorText, colorBorder },
  } = theme.useToken();

  const menuItems = [
    { key: 'device', icon: <DesktopOutlined />, label: 'Device' },
    { key: 'leaderelection', icon: <ClusterOutlined />, label: 'Election' },
    { key: 'newjob', icon: <FileAddOutlined />, label: 'New Job' }
  ];

  const renderPage = () => {
    switch (currentPage) {
      case 'device': return <DeviceCheckPage />;
      case 'leaderelection': return <ElectionPage />;
      case 'newjob': return <JobPage />;
      default: return <DeviceCheckPage />;
    }
  };

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
      <Header
        style={{
          position: 'sticky',
          top: 0,
          height: HEADER_HEIGHT,
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          background: '#001529',
          boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
            <Menu
            theme="dark"
            mode="horizontal"
            selectedKeys={[currentPage]}
            items={menuItems}
            onClick={(e) => setCurrentPage(e.key)}
            style={{ minWidth: '400px', background: 'transparent', borderBottom: 'none' }}
            />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <span style={{ color: 'rgba(255,255,255,0.65)', fontSize: '12px' }}>
             {isDarkMode ? 'Dark' : 'Light'} Mode
          </span>
          <Switch
            checked={isDarkMode}
            onChange={toggleTheme}
            checkedChildren={<BulbFilled />}
            unCheckedChildren={<BulbOutlined />}
          />
        </div>
      </Header>

      {/* MAIN BODY */}
      <Layout
        style={{
          position: 'relative',
          height: `calc(100vh - ${HEADER_HEIGHT}px)`,
          overflow: 'hidden',
        }}
      >

        
        {/* CONTENT AREA */}
        <Content
          style={{
            background: colorBgContainer,
            overflowY: 'auto',
            height: '100%',
          }}
        >
          {renderPage()}
        </Content>

        {/* RIGHT SIDER */}
        <Sider
          width={`${SIDER_WIDTH_PERCENT}%`}
          collapsedWidth={0}
          collapsed={siderCollapsed}
          trigger={null} // We disable the default trigger to build our custom one
          style={{
            background: colorBgContainer,
            borderLeft: `1px solid ${colorBorder}`,
            position: 'relative',
            zIndex: 10,
            boxShadow: siderCollapsed ? 'none' : '-4px 0 24px rgba(0,0,0,0.05)'
          }}
        >
            <DevicesSystemSidebar collapsed={siderCollapsed} />
        </Sider>

        <div
            onClick={() => setSiderCollapsed(!siderCollapsed)}
            style={{
                position: 'absolute',
                top: '48px', // Distance from top of content area
                right: siderCollapsed ? 0 : `${SIDER_WIDTH_PERCENT}%`,
                transform: 'translateX(0)', 
                zIndex: 100,
                width: '24px',
                height: '48px',
                background: colorBgContainer,
                border: `1px solid ${colorBorder}`,
                borderRight: 'none',
                borderTopLeftRadius: '12px',
                borderBottomLeftRadius: '12px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                boxShadow: '-2px 0 8px rgba(0,0,0,0.05)',
                transition: 'right 0.2s, background 0.3s', // Transition matches Sider animation speed exactly (0.2s is AntD default)
            }}
            onMouseEnter={(e) => e.currentTarget.style.width = '28px'}
            onMouseLeave={(e) => e.currentTarget.style.width = '24px'}
        >
             {/* Icon Logic */}
             {siderCollapsed ? 
                <LeftOutlined style={{ fontSize: '10px', color: '#999' }} /> : 
                <RightOutlined style={{ fontSize: '10px', color: '#999' }} />
             }
        </div>

      </Layout>
    </Layout>
  );
};

// Main App Wrapper to provide Ant Design Theme Algorithm
import { ConfigProvider, theme as antTheme } from 'antd';

const App = () => {
  return (
    <ThemeProvider>
      <ThemeContext.Consumer>
        {({ isDarkMode }) => (
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
        )}
      </ThemeContext.Consumer>
    </ThemeProvider>
  );
};

export default App;