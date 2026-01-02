import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button,
  Card,
  Space,
  Row,
  Col,
  message,
  Typography,
  Tag,
  Result,
  Form,
} from "antd";
import {
  ReloadOutlined,
  WifiOutlined,
  SyncOutlined,
} from "@ant-design/icons";
import RenderWorkerPanel from "./components/RenderWorkerPanel";
import ClusterStatus from "./components/ClusterStatus";

const { Title, Text } = Typography;

const StartRenderPage = () => {
  const navigate = useNavigate();
  const [devices, setDevices] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: "", ip: "" });
  const [electionDetails, setElectionDetails] = useState(null);
  
  // Upload states
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // Rendering states
  const [currentStep, setCurrentStep] = useState(0);
  const [sceneInfo, setSceneInfo] = useState(null);
  const [renderConfig, setRenderConfig] = useState({
    startFrame: 1,
    endFrame: 1,
    samples: 128,
    resolutionX: 1920,
    resolutionY: 1080,
    engine: 'CYCLES',
    outputFormat: 'PNG'
  });
  const [renderProgress, setRenderProgress] = useState({
    isRendering: false,
    progress: 0,
    completedFrames: 0,
    totalFrames: 0,
    frameStatus: []
  });
  const [workerProgress, setWorkerProgress] = useState({});

  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();
  const API_BASE = "http://localhost:5050/api";

  // --- API Functions ---

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

  const fetchRenderProgress = async () => {
    try {
      const response = await fetch(`${API_BASE}/render/progress`);
      if (response.ok) {
        const data = await response.json();
        setRenderProgress(prev => ({
          ...prev,
          progress: data.overall_progress,
          completedFrames: data.completed_frames,
          frameStatus: data.frame_status || prev.frameStatus
        }));
      }
    } catch (error) {
      console.error('Failed to fetch progress:', error);
    }
  };

  const fetchWorkerProgress = async () => {
    try {
      const response = await fetch(`${API_BASE}/render/worker-progress`);
      if (response.ok) {
        const data = await response.json();
        setWorkerProgress(data);
      }
    } catch (error) {
      console.error('Failed to fetch worker progress:', error);
    }
  };

  // --- Effects ---

  useEffect(() => { 
    fetchStatus(); 
    fetchElectionStatus(); 
  }, [fetchStatus, fetchElectionStatus]);

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

  useEffect(() => {
    let interval;
    if (renderProgress.isRendering && currentStep === 2) {
      interval = setInterval(() => {
        fetchRenderProgress();
        fetchWorkerProgress();
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [renderProgress.isRendering, currentStep]);

  // --- Handlers ---

  const toggleNetwork = async () => {
    try {
      if (isRunning) {
        await fetch(`${API_BASE}/stop`, { method: "POST" });
        setIsRunning(false);
        setDevices([]);
        setElectionDetails(null);
        setCurrentStep(0);
        setSceneInfo(null);
        setRenderProgress({
          isRendering: false,
          progress: 0,
          completedFrames: 0,
          totalFrames: 0,
          frameStatus: []
        });
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

  const uploadBlendFile = async (file) => {
    setUploading(true);
    const formData = new FormData();
    formData.append('blend_file', file);
    
    try {
      const response = await fetch(`${API_BASE}/render/upload`, {
        method: 'POST',
        body: formData,
      });
      
      if (response.ok) {
        const data = await response.json();
        setUploadedFile(file);
        setSceneInfo({
          sceneName: data.scene_name,
          totalFrames: data.total_frames,
          frameRate: data.frame_rate,
          renderEngine: data.render_engine,
          duration: data.duration,
        });
        
        setRenderConfig(prev => ({
          ...prev,
          endFrame: data.total_frames || 1,
        }));
        
        setCurrentStep(1);
        messageApi.success('File uploaded successfully!');
      } else {
        throw new Error('Upload failed');
      }
    } catch (error) {
      messageApi.error('Failed to upload file');
    } finally {
      setUploading(false);
    }
  };

  const startRender = async () => {
    try {
      const payload = {
        ...renderConfig,
        scene_info: sceneInfo,
      };
      
      const response = await fetch(`${API_BASE}/render/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      
      if (response.ok) {
        setCurrentStep(2);
        setRenderProgress(prev => ({
          ...prev,
          isRendering: true,
          totalFrames: renderConfig.endFrame - renderConfig.startFrame + 1,
          frameStatus: Array.from({ length: renderConfig.endFrame - renderConfig.startFrame + 1 }, 
            (_, i) => ({ frame: i + renderConfig.startFrame, status: 'pending' }))
        }));
        messageApi.success('Render job started!');
      } else {
        throw new Error('Failed to start render');
      }
    } catch (error) {
      messageApi.error('Failed to start render job');
    }
  };

  return (
    <div style={{ padding: "24px" }}>
      {contextHolder}
      <Row gutter={24}>
        
        {/* LEFT COL: Worker Interface */}
        <Col span={16}>
          <Title level={3} style={{ marginTop: 0 }}>Job Runner</Title>
          
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

          {isRunning && electionDetails ? (
              <RenderWorkerPanel
                currentStep={currentStep}
                uploadBlendFile={uploadBlendFile}
                uploading={uploading}
                uploadProgress={uploadProgress}
                uploadedFile={uploadedFile}
                sceneInfo={sceneInfo}
                renderConfig={renderConfig}
                form={form}
                onStartRender={startRender}
                onStepChange={setCurrentStep}
                renderProgress={renderProgress}
                workerProgress={workerProgress}
              />
          ) : (
               <Card bordered={false} style={{ minHeight: 400 }}>
                   <Result 
                       status="warning"
                       title="Network Disconnected"
                       subTitle="Connect to the network to participate in election and rendering."
                   />
               </Card>
          )}

        </Col>

        {/* RIGHT COL: Cluster Status */}
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