import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Badge,
  Space,
  Row,
  Col,
  message,
  Typography,
  Tag,
  Result,
} from "antd";
import {
  WifiOutlined,
} from "@ant-design/icons";
import WorkerActivityPanel from "./renderer/WorkerActivityPanel";
import ClusterStatus from "./components/ClusterStatus";

const { Title, Text } = Typography;

const StartRenderPage = () => {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: "", ip: "" });
  
  const [electionDetails, setElectionDetails] = useState(null);

  const [messageApi, contextHolder] = message.useMessage();
  const API_BASE = "http://localhost:5050/api";

  // --- Network & Election Logic ---

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
      console.error("Status check failed", error);
    }
  }, []);

  const fetchElectionStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/election/status`);
      const data = await response.json();
      setElectionDetails(data);
    } catch (error) {
      console.error("Election status fetch failed", error);
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/devices`);
      const data = await response.json();

      const rawDevices = Array.isArray(data) ? data : (data.devices || []);
      const devicesWithTimestamp = rawDevices.map((device) => {
        let timestamp = Date.now();
        if (device.last_seen) {
           if (typeof device.last_seen === 'number') {
             timestamp = device.last_seen * 1000; 
           } else if (typeof device.last_seen === 'string') {
             try {
                const [hours, minutes, seconds] = device.last_seen.split(":").map(Number);
                const now = new Date();
                const lastSeenDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours, minutes, seconds);
                if (lastSeenDate > now) lastSeenDate.setDate(lastSeenDate.getDate() - 1);
                timestamp = lastSeenDate.getTime();
             } catch (e) { console.error("Time parse error", e); }
           }
        }
        return { ...device, timestamp };
      });

      const sortedDevices = [...devicesWithTimestamp].sort((a, b) => {
        const aIsSelf = a.name === localInfo.pcName && a.ip === localInfo.ip;
        const bIsSelf = b.name === localInfo.pcName && b.ip === localInfo.ip;
        if (aIsSelf) return -1;
        if (bIsSelf) return 1;
        return (b.resource_score || 0) - (a.resource_score || 0);
      });

      setDevices(sortedDevices);
    } catch (error) {
      console.error("Error fetching devices:", error);
    }
  }, [localInfo]);

  // Initial Load
  useEffect(() => { 
    fetchStatus(); 
    fetchElectionStatus(); 
  }, [fetchStatus, fetchElectionStatus]);

  // Polling Interval
  useEffect(() => {
    if (isRunning) {
      fetchDevices();
      fetchElectionStatus();
      const interval = setInterval(() => {
          fetchDevices();
          fetchElectionStatus();
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [isRunning, fetchDevices, fetchElectionStatus]);

  const toggleNetwork = async () => {
    try {
      if (isRunning) {
        await fetch(`${API_BASE}/stop`, { method: "POST" });
        setIsRunning(false);
        setDevices([]);
        setElectionDetails(null); // Clear election data on stop
        messageApi.info("Left the network");
      } else {
        const response = await fetch(`${API_BASE}/start`, { method: "POST" });
        const data = await response.json();
        if (data.success) {
          setIsRunning(true);
          messageApi.success("Network discovery started");
          setTimeout(() => {
              fetchDevices();
              fetchElectionStatus();
          }, 1000);
        } else {
          messageApi.error(`Error: ${data.message}`);
        }
      }
    } catch (error) {
      messageApi.error(error.message);
    }
  };

  const proceedToRender = () => {
    if(!isRunning) {
        messageApi.warning("Please enter the network before proceeding.");
        return;
    }
    if(devices.length < 2) {
        messageApi.warning("No workers found. Wait for devices to connect.");
        return;
    }
    navigate('/leaderelection'); 
  };

  // --- Rendering Helpers ---

  const isDeviceOnline = (device) => {
    if (!device.timestamp) return false;
    const timeDiff = (Date.now() - device.timestamp) / 1000;
    return timeDiff < 15;
  };

  const columns = [
    {
      title: "Role",
      key: "role",
      width: 100,
      render: (_, record) => {
        const isSelf = record.name === localInfo.pcName && record.ip === localInfo.ip;
        let role = "Worker";

        if (electionDetails) {
            // 1. Direct IP Check: Does this record's IP match the elected leader's IP?
            if (electionDetails.current_leader === record.ip) {
                role = "Leader";
            } 
            // 2. Self Check: If this is me, trust the backend 'my_role' flag
            else if (isSelf && electionDetails.my_role) {
                role = electionDetails.my_role;
            }
            // 3. Fallback: Check topology array if the above didn't catch it
            else if (electionDetails.election_results?.ring_topology) {
                const node = electionDetails.election_results.ring_topology.find(n => n.ip === record.ip);
                if(node) role = node.role;
            }
        }

        return (
          <Tag color={role === "Leader" ? "gold" : (isSelf ? "purple" : "blue")}>
            {role} {isSelf ? "(Me)" : ""}
          </Tag>
        );
      }
    },
    {
      title: "Device",
      dataIndex: "name",
      key: "name",
      render: (text) => <strong>{text}</strong>,
    },
    {
      title: "Score",
      dataIndex: "resource_score",
      key: "resource_score",
      render: (score) => <Text strong>{score}</Text>
    },
    {
      title: "Status",
      key: "status",
      render: (_, record) => {
        const isSelf = record.name === localInfo.pcName && record.ip === localInfo.ip;
        if (isSelf) return <Badge status="success" text="Ready" />;
        return isDeviceOnline(record) ? <Badge status="success" text="Online" /> : <Badge status="error" text="Offline" />;
      },
    },
  ];

  const renderWorkerPanel = () => {
    return (
      <WorkerActivityPanel electionDetails={electionDetails} />
    );
  };

  return (
    <div style={{ padding: "24px" }}>
      {contextHolder}
      <Row gutter={24}>
        
        {/* --- LEFT COL: Conditional Interface based on Role --- */}
        <Col span={16}>
          <Title level={3} style={{ marginTop: 0 }}>Node Manager</Title>
          
          {/* Network Toggle */}
          <Card size="small" style={{ marginBottom: 16 }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Space>
                  <WifiOutlined style={{ color: isRunning ? '#52c41a' : '#ccc' }} /> 
                  <Text>{isRunning ? "Network Active" : "Network Inactive"}</Text>
                  {isRunning && electionDetails && (
                      <Tag color={electionDetails.my_role === 'Leader' ? 'gold' : 'blue'}>
                          {electionDetails.my_role}
                      </Tag>
                  )}
                </Space>
              </Col>
              <Col>
                <Button 
                    type={isRunning ? "default" : "primary"} 
                    danger={isRunning}
                    onClick={toggleNetwork}
                    size="small"
                >
                    {isRunning ? "Disconnect" : "Connect"}
                </Button>
              </Col>
            </Row>
          </Card>

          {/* Conditional Render Logic */}
          {isRunning && electionDetails ? (
              renderWorkerPanel()
          ) : (
               // Default empty state if network is off
               <Card bordered={false} style={{ minHeight: 400 }}>
                   <Result 
                       status="warning"
                       title="Network Disconnected"
                       subTitle="Connect to the network to participate in election and rendering."
                   />
               </Card>
          )}

        </Col>

        {/* --- RIGHT COL: Device List --- */}
        <ClusterStatus 
          localInfo={localInfo}
          electionDetails={electionDetails}
          devices={devices}
          isRunning={isRunning}
          fetchDevices={fetchDevices}
          fetchElectionStatus={fetchElectionStatus}
        />
      </Row>
    </div>
  );
};

export default StartRenderPage;