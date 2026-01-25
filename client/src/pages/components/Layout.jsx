import React, { useState } from 'react';
import { Layout, Menu, Switch, theme } from 'antd';
import { 
  BulbOutlined, 
  BulbFilled, 
  LeftOutlined, 
  RightOutlined,
  DesktopOutlined,
  ClusterOutlined,
  FileAddOutlined
} from '@ant-design/icons';
import DevicesSystemSidebar from './DevicesSystemSidebar';
import { useTheme } from '../../context/ThemeContext';

import DeviceCheckPage from '../DeviceCheckPage';
import ElectionPage from '../ElectionPage';
import JobPage from '../JobPage';

const { Header, Content, Sider } = Layout;

const SIDER_WIDTH_PERCENT = 40;
const HEADER_HEIGHT = 64;

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

      <Layout style={{ flex: 1, minHeight: 0 }}>
        <Content
          style={{
            background: colorBgContainer,
            overflowY: 'auto',
            minHeight: 0,
          }}
        >
          {renderPage()}
        </Content>

        <Sider
          width={`${SIDER_WIDTH_PERCENT}%`}
          collapsedWidth={0}
          collapsed={siderCollapsed}
          trigger={null}
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
            top: '48px',
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
            transition: 'right 0.2s, background 0.3s',
          }}
          onMouseEnter={(e) => e.currentTarget.style.width = '28px'}
          onMouseLeave={(e) => e.currentTarget.style.width = '24px'}
        >
          {siderCollapsed ? 
            <LeftOutlined style={{ fontSize: '10px', color: '#999' }} /> : 
            <RightOutlined style={{ fontSize: '10px', color: '#999' }} />
          }
        </div>
      </Layout>
    </Layout>
  );
};

export default AppLayout;