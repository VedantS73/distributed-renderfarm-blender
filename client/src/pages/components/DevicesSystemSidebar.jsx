import { Table, Badge, Empty, Typography, theme, Tooltip } from "antd";
import { useNetwork } from "../../context/NetworkContext";
import { WifiOutlined, DisconnectOutlined } from "@ant-design/icons";

const { Text } = Typography;

const DevicesSystemSidebar = ({ collapsed }) => {
  const {
    token: { colorText, colorBorder },
  } = theme.useToken();
  const { devices, isRunning, localInfo, stats } = useNetwork();

  const isOnline = (d) =>
    d.timestamp && (Date.now() - d.timestamp) / 1000 < 15;

  const getSecondsSinceLastSeen = (device) => {
    if (!device.timestamp) return 0;
    return Math.floor((Date.now() - device.timestamp) / 1000);
  };

  const getDeviceStatus = (record) => {
    if (record.name === localInfo.pcName && record.ip === localInfo.ip) {
      return { status: "warning", text: "Self" };
    }
    
    const online = isOnline(record);
    if (online) {
      return { status: "success", text: "Online" };
    } else {
      return { status: "error", text: "Offline" };
    }
  };

  const columns = [
    {
      title: "#",
      width: 24,
      render: (_, record, index) => (
        <Tooltip title={`Device ${index + 1}`}>
          <div style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            backgroundColor: '#faad14',
            margin: '0 auto'
          }} />
        </Tooltip>
      ),
    },
    {
      title: "Device",
      dataIndex: "name",
      width: collapsed ? 100 : 150,
      render: (text, record) => {
        const isSelf = record.name === localInfo.pcName && record.ip === localInfo.ip;
        return (
          isSelf ? (
            <Text strong style={{ fontSize: collapsed ? 12 : 14 }}>{text} (You)</Text>
          ) : (
            <Text style={{ fontSize: collapsed ? 12 : 14 }}>{text}</Text>
          )
        );
      },
    },
    {
      title: "IP",
      dataIndex: "ip",
      width: collapsed ? 80 : 120,
      render: (text) => (
        <Text type="secondary" style={{ fontSize: collapsed ? 10 : 12 }}>
          {text}
        </Text>
      ),
    },
    {
      title: "Score",
      dataIndex: "resource_score",
      width: collapsed ? 60 : 80,
      align: 'center',
      render: (score) => (
        <Text style={{ fontSize: collapsed ? 12 : 14 }}>
          {score !== undefined && score !== null ? score : 0}
        </Text>
      ),
    },
    {
      title: "Status",
      width: collapsed ? 70 : 90,
      render: (_, record) => {
        const status = getDeviceStatus(record);
        const secondsAgo = getSecondsSinceLastSeen(record);
        const tooltipText = record.name === localInfo.pcName 
          ? "This device" 
          : `Last seen ${secondsAgo} seconds ago`;
        
        return (
          <Tooltip title={tooltipText}>
            <Badge 
              status={status.status} 
              text={collapsed ? "" : status.text}
              style={{ fontSize: collapsed ? 10 : 12 }}
            />
          </Tooltip>
        );
      },
    },
  ];

  if (!isRunning) {
    return (
      <div style={{ padding: collapsed ? 8 : 16 }}>
        <Empty
          description={
            <Text type="secondary" style={{ fontSize: collapsed ? 12 : 14 }}>
              Device is not connected to the network
            </Text>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          imageStyle={{ height: collapsed ? 40 : 60 }}
        />
      </div>
    );
  }

  // Sort devices: self first, then by resource score
  const sortedDevices = [...devices].sort((a, b) => {
    const aIsSelf = a.name === localInfo.pcName && a.ip === localInfo.ip;
    const bIsSelf = b.name === localInfo.pcName && b.ip === localInfo.ip;

    if (aIsSelf) return -1;
    if (bIsSelf) return 1;
    return (b.resource_score || 0) - (a.resource_score || 0);
  });

  const onlineCount = sortedDevices.filter(d => isOnline(d)).length;
  const offlineCount = sortedDevices.filter(d => !isOnline(d) && !(d.name === localInfo.pcName)).length;

  return (
    <div style={{ 
      padding: collapsed ? 4 : 8,
      height: '100%'
    }}>
      {/* Stats Summary */}
      {!collapsed && (
        <div style={{ 
          marginBottom: 8, 
          padding: 8
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Text style={{ fontSize: 12 }}>
              Devices: {stats?.total_devices || devices.length}
            </Text>
            <div style={{ display: 'flex', gap: 12 }}>
              <Text type="success" style={{ fontSize: 12 }}>
                <WifiOutlined /> {onlineCount}
              </Text>
              <Text type="danger" style={{ fontSize: 12 }}>
                <DisconnectOutlined /> {offlineCount}
              </Text>
            </div>
          </div>
        </div>
      )}
      
      {/* Devices Table */}
      <Table
        size="small"
        pagination={false}
        rowKey={(r) => `${r.name}-${r.ip}`}
        columns={columns}
        dataSource={sortedDevices}
        scroll={{ y: collapsed ? 300 : 400 }}
        style={{ fontSize: collapsed ? 10 : 12 }}
        locale={{
          emptyText: (
            <Text type="secondary" style={{ fontSize: collapsed ? 10 : 12 }}>
              Scanning for devices...
            </Text>
          )
        }}
      />
    </div>
  );
};

export default DevicesSystemSidebar;