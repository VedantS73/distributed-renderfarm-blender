import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Card,
  Descriptions,
  Badge,
  Space,
  Row,
  Col,
  message,
  Typography,
  Upload,
  Tag,
  Statistic,
  Divider,
  Result,
  Spin
} from "antd";
import {
  ReloadOutlined,
  WifiOutlined,
  DisconnectOutlined,
  SoundOutlined,
  InboxOutlined,
  FileOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  ClusterOutlined,
  SyncOutlined
} from "@ant-design/icons";

const { Title, Text } = Typography;
const { Dragger } = Upload;

const StartRenderPage = () => {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: "", ip: "" });
  
  // Election State
  const [electionDetails, setElectionDetails] = useState(null);
  
  // File Upload State
  const [fileDetails, setFileDetails] = useState(null);
  const [uploading, setUploading] = useState(false);

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

  // --- File Upload Logic ---

  const handleCustomUpload = async ({ file, onSuccess, onError }) => {
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/upload-blend`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");
      
      const data = await response.json();
      
      const processedDetails = {
        filename: file.name,
        size: (file.size / 1024 / 1024).toFixed(2) + " MB",
        objects: data.objects || 12, 
        vertices: data.vertices || "1.2M",
        frames: data.frames || "1 - 250",
        estimated_memory: "4.2 GB"
      };

      setFileDetails(processedDetails);
      messageApi.success(`${file.name} uploaded successfully`);
      onSuccess("ok");
    } catch (error) {
      console.error(error);
      messageApi.error(`${file.name} upload failed.`);
      onError(error);
    } finally {
      setUploading(false);
    }
  };

  const removeFile = () => {
    setFileDetails(null);
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
        // We can use the electionDetails to check true roles if IP matches
        let role = "Worker";
        if(electionDetails && electionDetails.election_results && electionDetails.election_results.ring_topology) {
            const node = electionDetails.election_results.ring_topology.find(n => n.ip === record.ip);
            if(node) role = node.role;
        }

        const isSelf = record.name === localInfo.pcName && record.ip === localInfo.ip;
        
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

  // --- Left Panel Content Generators ---

  const renderLeaderPanel = () => {
    return !fileDetails ? (
        <Card title="Upload Project File" bordered={false} style={{ minHeight: 400 }}>
          <Dragger 
            customRequest={handleCustomUpload} 
            showUploadList={false}
            accept=".blend"
            disabled={uploading}
            style={{ padding: '40px 0' }}
          >
            <p className="ant-upload-drag-icon">
              <InboxOutlined style={{ color: '#1890ff' }} />
            </p>
            <p className="ant-upload-text">Click or drag .blend file to this area</p>
            <p className="ant-upload-hint">
              You are the <strong>Leader</strong>. Upload the file to distribute tasks.
            </p>
          </Dragger>
        </Card>
      ) : (
        <Card 
            title={
                <Space>
                    <FileOutlined />
                    {fileDetails.filename}
                </Space>
            } 
            extra={
                <Button type="text" danger icon={<DeleteOutlined />} onClick={removeFile}>
                    Remove
                </Button>
            }
        >
            <Descriptions bordered column={1} size="small">
                <Descriptions.Item label="File Size">{fileDetails.size}</Descriptions.Item>
                <Descriptions.Item label="Total Objects">{fileDetails.objects}</Descriptions.Item>
                <Descriptions.Item label="Total Vertices">{fileDetails.vertices}</Descriptions.Item>
                <Descriptions.Item label="Frame Range">{fileDetails.frames}</Descriptions.Item>
                <Descriptions.Item label="Est. VRAM Req">{fileDetails.estimated_memory}</Descriptions.Item>
            </Descriptions>

            <Divider />

            <div style={{ textAlign: 'center', marginTop: 20 }}>
                <Button 
                    type="primary" 
                    size="large" 
                    icon={<PlayCircleOutlined />} 
                    onClick={proceedToRender}
                    block
                    style={{ height: '50px', fontSize: '18px' }}
                >
                    Distribute Tasks
                </Button>
            </div>
        </Card>
      );
  };

  const renderWorkerPanel = () => {
    return (
        <Card bordered={false} style={{ minHeight: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Result
                icon={<ClusterOutlined style={{ color: '#1890ff' }} />}
                title="Worker Node Active"
                subTitle="Waiting for Leader to initiate render job..."
                extra={[
                   <div key="info" style={{ textAlign: 'left', background: '#f5f5f5', padding: 20, borderRadius: 8 }}>
                       <Descriptions title="Cluster Details" column={1} size="small">
                            <Descriptions.Item label="My Role">
                                <Tag color="blue">Worker</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="Current Leader">
                                <Text code>{electionDetails?.current_leader || "Determining..."}</Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="Election Method">
                                {electionDetails?.election_results?.election_method || "LCR"}
                            </Descriptions.Item>
                       </Descriptions>
                   </div>
                ]}
            />
            <div style={{ textAlign: 'center', marginTop: 20 }}>
                 <Spin tip="Listening for tasks..." />
            </div>
        </Card>
    );
  };

  return (
    <div style={{ padding: "24px" }}>
      {contextHolder}
      <Row gutter={24}>
        
        {/* --- LEFT COL: Conditional Interface based on Role --- */}
        <Col span={16}>
          <Title level={3}>Project Setup</Title>
          
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
               electionDetails.my_role === 'Leader' ? renderLeaderPanel() : renderWorkerPanel()
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
        <Col span={8}>
           <Row justify="space-between" align="middle" style={{ marginBottom: 8, marginTop: 8 }}>
             <Title level={4} style={{ margin: 0 }}>Cluster Status</Title>
             <Space>
                <Tag icon={<SyncOutlined spin={isRunning} />} color={isRunning ? "processing" : "default"}>
                    {isRunning ? "Live" : "Stopped"}
                </Tag>
                <Button 
                    icon={<ReloadOutlined />} 
                    onClick={() => { fetchDevices(); fetchElectionStatus(); }} 
                    size="small" 
                    disabled={!isRunning}
                >
                    Refresh
                </Button>
             </Space>
           </Row>

          <Card bordered={false} bodyStyle={{ padding: 0 }}>
            <Table
              dataSource={devices}
              columns={columns}
              rowKey={(record) => `${record.name}-${record.ip}`}
              locale={{
                emptyText: isRunning
                  ? "Scanning for neighbors..."
                  : "Connect to network to find devices",
              }}
              pagination={false}
              scroll={{ y: 500 }}
            />
          </Card>
          
          {isRunning && (
              <div style={{ marginTop: 16, textAlign: 'right' }}>
                  <Space size="large">
                     <Statistic title="Nodes in Ring" value={Math.max(0, devices.length)} valueStyle={{ fontSize: 16 }} />
                     <Statistic title="Total Compute Score" value={devices.reduce((acc, curr) => acc + (curr.resource_score || 0), 0)} valueStyle={{ fontSize: 16 }} />
                  </Space>
              </div>
          )}
        </Col>
      </Row>
    </div>
  );
};

export default StartRenderPage;