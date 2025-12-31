import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Card,
  Descriptions,
  Badge,
  Row,
  Col,
  message,
  Typography,
} from "antd";
import {
  ReloadOutlined,
  WifiOutlined,
  DisconnectOutlined,
  SoundOutlined,
} from "@ant-design/icons";

const { Title } = Typography;

const NetworkDiscovery = () => {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [status, setStatus] = useState("Not connected");
  const [isRunning, setIsRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: "", ip: "" });
  const [stats, setStats] = useState({ local_ip: "", total_devices: 0 });
  const [loading, setLoading] = useState(false);

  // To handle global messages
  const [messageApi, contextHolder] = message.useMessage();

  const API_BASE = "http://localhost:5050/api";

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/status`);
      const data = await response.json();
      setIsRunning(data.running);
      setLocalInfo({
        pcName: data.local_pc_name,
        ip: data.local_ip,
      });
    } catch (error) {
      messageApi.error("Error connecting to server status");
      setStatus("Error connecting to server");
    }
  }, [messageApi]);

  // --- NEW: Poll Election Status ---
  const checkElectionStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/election/status`);
      const data = await response.json();

      // Check if election is done (has a leader) and we have an assigned role
      if (data.current_leader && data.my_role) {
        messageApi.success(`Election finished. Role: ${data.my_role}`);
        // Redirect to /Worker or /Leader based on response
        navigate(`/node-manager`); 
      }
    } catch (error) {
      console.error("Error checking election status:", error);
    }
  }, [navigate, messageApi]);

  const fetchStatusListener = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/status_listener`);
      const data = await response.json();
      return data;
    } catch (error) {
      console.error("Error fetching status listener:", error);
      return null;
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/devices`);
      const data = await response.json();

      const devicesWithTimestamp = (data || []).map((device) => ({
        ...device,
        timestamp: device.last_seen ? device.last_seen * 1000 : Date.now(),
      }));

      const sortedDevices = [...devicesWithTimestamp].sort((a, b) => {
        const aIsSelf = a.name === localInfo.pcName && a.ip === localInfo.ip;
        const bIsSelf = b.name === localInfo.pcName && b.ip === localInfo.ip;

        if (aIsSelf) return -1;
        if (bIsSelf) return 1;
        return (b.resource_score || 0) - (a.resource_score || 0);
      });

      setDevices(sortedDevices);
      setStats(data.stats || { local_ip: "", total_devices: 0 });

      if (isRunning) {
        setStatus(`Found ${sortedDevices.length} devices`);
      }
    } catch (error) {
      console.error("Error fetching devices:", error);
    }
  }, [isRunning, localInfo.pcName, localInfo.ip]);

  useEffect(() => {
    fetchStatus();
    fetchStatusListener();
  }, [fetchStatus]);

  useEffect(() => {
    if (isRunning) {
      fetchDevices();
      checkElectionStatus();

      const deviceInterval = setInterval(fetchDevices, 2000);
      const electionInterval = setInterval(checkElectionStatus, 2000);

      return () => {
        clearInterval(deviceInterval);
        clearInterval(electionInterval);
      };
    }
  }, [isRunning, fetchDevices, checkElectionStatus]);

  const toggleNetwork = async () => {
    setLoading(true);
    try {
      if (isRunning) {
        await fetch(`${API_BASE}/stop`, { method: "POST" });
        setIsRunning(false);
        setStatus("Not connected");
        setDevices([]);
        messageApi.info("Left the network");
      } else {
        const response = await fetch(`${API_BASE}/start`, { method: "POST" });
        const data = await response.json();

        if (data.success) {
          setIsRunning(true);
          setStatus("Discovering...");
          messageApi.success("Entered network discovery mode");
          setTimeout(fetchDevices, 1000);
        } else {
          messageApi.error(`Error: ${data.message}`);
          setStatus(`Error: ${data.message}`);
        }
      }
    } catch (error) {
      messageApi.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const testBroadcast = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/test-broadcast`, {
        method: "POST",
      });
      const data = await response.json();
      messageApi.info(data.message);
      setStatus(data.message);
    } catch (error) {
      messageApi.error(error.message);
    } finally {
      setLoading(false);
    }
  };

  const refreshDevices = () => {
    if (isRunning) {
      setStatus("Refreshing...");
      fetchDevices();
    }
  };

  const isDeviceOnline = (device) => {
    if (!device.timestamp) return false;
    const timeDiff = (Date.now() - device.timestamp) / 1000;
    return timeDiff < 15;
  };

  const getSecondsSinceLastSeen = (device) => {
    if (!device.timestamp) return 0;
    return Math.floor((Date.now() - device.timestamp) / 1000);
  };

  const columns = [
    {
      title: "PC Name",
      dataIndex: "name",
      key: "name",
      render: (text) => <strong>{text}</strong>,
    },
    {
      title: "IP Address",
      dataIndex: "ip",
      key: "ip",
      render: (text) => <Badge status="processing" text={text} />,
    },
    {
      title: "Resource Score",
      dataIndex: "resource_score",
      key: "resource_score",
    },
    {
      title: "Status",
      dataIndex: "last_seen",
      key: "status",
      render: (text, record) => {
        if (record.name === localInfo.pcName && record.ip === localInfo.ip) {
          return <Badge status="warning" text="Self" />;
        }
        const online = isDeviceOnline(record);
        const secondsAgo = getSecondsSinceLastSeen(record);
        const tooltipText = `Last seen ${secondsAgo} seconds ago`;
        return (
          <span title={tooltipText}>
            {online ? (
              <Badge status="success" text="Online" />
            ) : (
              <Badge status="error" text="Disconnected" />
            )}
          </span>
        );
      },
    },
  ];

  return (
    <div>
      {contextHolder}
      <Row gutter={16}>
        <Col span={12}>
          <Row gutter={16}>
            <Col span={24}>
              <Card title="Local Information" bordered={false}>
                <Descriptions column={1}>
                  <Descriptions.Item label="PC Name">
                    {localInfo.pcName || "Unknown"}
                  </Descriptions.Item>
                  <Descriptions.Item label="IP Address">
                    {localInfo.ip || "Unknown"}
                  </Descriptions.Item>
                  <Descriptions.Item label="Total Devices">
                    {stats.total_devices || "Unknown"}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
          </Row>

          <Card>
            <Row gutter={8}>
              <Col span={8}>
                <Button
                  type={isRunning ? "primary" : "default"}
                  danger={isRunning}
                  icon={isRunning ? <DisconnectOutlined /> : <WifiOutlined />}
                  onClick={toggleNetwork}
                  loading={loading}
                  size="large"
                  block
                >
                  {isRunning ? "Leave Network" : "Enter Network"}
                </Button>
              </Col>

              <Col span={8}>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={refreshDevices}
                  disabled={!isRunning || loading}
                  size="large"
                  block
                >
                  Refresh
                </Button>
              </Col>

              <Col span={8}>
                <Button
                  icon={<SoundOutlined />}
                  onClick={testBroadcast}
                  disabled={loading}
                  size="large"
                  block
                >
                  Test Broadcast
                </Button>
              </Col>
            </Row>
          </Card>
        </Col>

        <Col span={12}>
          <Card title="Discovered Devices" bordered={false}>
            <Table
              dataSource={devices}
              columns={columns}
              rowKey={(record) => `${record.name}-${record.ip}`}
              locale={{
                emptyText: isRunning
                  ? "Scanning for devices..."
                  : "Network discovery not active",
              }}
              pagination={false}
              scroll={{ y: 500 }}
              size="middle"
            />
          </Card>
          <Card>
            <Button
              type="primary"
              loading={loading}
              size="large"
              disabled={!isRunning || devices.length < 2}
              block
              onClick={() => navigate('/leaderelection')}
            >
              {!isRunning
                ? "Leader Election"
                : devices.length < 2
                ? "Waiting for more devices..."
                : "Manual Leader Election"}
            </Button>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default NetworkDiscovery;