import React from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Switch, theme } from 'antd';
import { WifiOutlined, HomeOutlined, BulbOutlined, BulbFilled } from '@ant-design/icons';
import { ThemeProvider, useTheme } from './ThemeContext';
import NetworkDiscovery from './pages/NetworkDiscovery';
import MyDevicePage from './pages/MyDevicePage';
import LeaderElectionPage from './pages/LeaderElectionPage';
import NodeManager from './pages/NodeManager';
import NewJobPage from './pages/NewJobPage';

const { Header, Content, Footer } = Layout;

const AppLayout = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isDarkMode, toggleTheme } = useTheme();
  
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  const items = [
    {
      key: '/',
      label: 'Home',
    },
    {
      key: '/discovery',
      label: 'Network Discovery',
    },
    {
      key: '/leaderelection',
      label: 'Leader Election',
    },
    {
      key: '/node-manager',
      label: 'Node Manager',
    },
    {
      key: '/newjob',
      label: 'New Job',
    }
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 24px' }}>
        <div className="logo" style={{ color: 'white', fontWeight: 'bold', fontSize: '18px', marginRight: '24px' }}>
          Distributed Renderer
        </div>
        
        <Menu
          theme="dark"
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={items}
          onClick={(e) => navigate(e.key)}
          style={{ flex: 1, minWidth: 0 }}
        />

        <div style={{ marginLeft: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Switch
            checked={isDarkMode}
            onChange={toggleTheme}
            checkedChildren={<BulbFilled />}
            unCheckedChildren={<BulbOutlined />}
          />
        </div>
      </Header>
        <div style={{ background: colorBgContainer, minHeight: 280, padding: 24, borderRadius: 8 }}>
          <Routes>
            <Route path="/" element={<MyDevicePage />} />
            <Route path="/discovery" element={<NetworkDiscovery />} />
            <Route path="/leaderelection" element={<LeaderElectionPage />} />
            <Route path="/node-manager" element={<NodeManager />} />
            <Route path="/newjob" element={<NewJobPage />} />
          </Routes>
        </div>
    </Layout>
  );
};

const App = () => {
  return (
    <ThemeProvider>
      <Router>
        <AppLayout />
      </Router>
    </ThemeProvider>
  );
};

export default App;