import React, { useState, useEffect, useRef, useCallback } from "react";
import { 
  Card, 
  Typography, 
  Row, 
  Col, 
  Statistic, 
  Tag, 
  Button, 
  Spin, 
  Alert, 
  Space,
  Divider,
  Steps
} from "antd";
import { 
  CrownOutlined, 
  UserOutlined, 
  ReloadOutlined, 
  ClusterOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  SyncOutlined
} from "@ant-design/icons";
import ForceGraph2D from "react-force-graph-2d";
import { useNavigate } from "react-router-dom";

const { Title, Text, Paragraph } = Typography;

const ElectionResultPage = () => {
  const navigate = useNavigate();
  const graphRef = useRef();
  
  const [loading, setLoading] = useState(true);
  const [electionData, setElectionData] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [error, setError] = useState(null);

  // --- Data Processing Helper ---
  const processTopologyToGraph = (topology) => {
    if (!topology) return { nodes: [], links: [] };

    const nodes = topology.map((node) => ({
      id: node.ip,
      name: node.name,
      val: node.role === "Leader" ? 30 : 15, // Leader is visually larger
      color: node.role === "Leader" ? "#FAAD14" : (node.is_me ? "#722ED1" : "#1890ff"), // Gold, Purple, Blue
      role: node.role,
      score: node.resource_score,
      is_me: node.is_me,
      ip: node.ip
    }));

    const links = topology.map((node) => ({
      source: node.ip,
      target: node.successor, // LCR Ring Connection
      color: '#d9d9d9'
    }));

    return { nodes, links };
  };

  // --- API Calls ---

  // 1. Check Status (Primary Load)
  const checkElectionStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("http://localhost:5050/api/election/status");
      if (!response.ok) throw new Error("Failed to fetch status");
      
      const data = await response.json();
      setElectionData(data);

      if (data.election_results && data.election_results.ring_topology) {
        const gData = processTopologyToGraph(data.election_results.ring_topology);
        setGraphData(gData);
      }
    } catch (err) {
      console.error(err);
      setError("Could not fetch election status. Is the service running?");
    } finally {
      setLoading(false);
    }
  }, []);

  // 2. Force Re-run Election (Manual Trigger)
  const forceReElection = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://localhost:5050/api/election/start", {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to restart election");
      
      // After starting, wait a moment then check status
      setTimeout(checkElectionStatus, 1000);
    } catch (err) {
      setError("Failed to trigger new election.");
      setLoading(false);
    }
  };

  // Initial Load
  useEffect(() => {
    checkElectionStatus();
  }, [checkElectionStatus]);

  // --- Render Helpers ---

  const renderLeaderSidebar = () => (
    <Card 
      title={<Space><CrownOutlined style={{ color: '#FAAD14' }}/> You are the Leader</Space>}
      style={{ borderTop: '4px solid #FAAD14' }}
      actions={[
        <Button 
            type="primary" 
            block 
            icon={<ArrowRightOutlined />}
            onClick={() => navigate('/node-manager')}
        >
            Proceed to Job Manager
        </Button>
      ]}
    >
        <Paragraph>
            As the elected leader (IP: <Text code>{electionData?.my_ip}</Text>), you are responsible for distributing render chunks to the worker nodes.
        </Paragraph>
        <Steps 
            direction="vertical" 
            size="small" 
            current={1}
            items={[
                { title: 'Discovery', status: 'finish' },
                { title: 'Leader Election', status: 'finish' },
                { title: 'Job Distribution', status: 'process' },
            ]}
        />
    </Card>
  );

  const renderWorkerSidebar = () => (
    <Card 
      title={<Space><UserOutlined style={{ color: '#1890ff' }}/> You are a Worker</Space>}
      style={{ borderTop: '4px solid #1890ff' }}
    >
        <Paragraph>
            Your node is in <strong>Standby Mode</strong>. You are connected to the ring and awaiting instructions from the Leader.
        </Paragraph>
        <Alert
            message="Waiting for Jobs"
            description={`Leader (${electionData?.current_leader}) will initiate tasks automatically.`}
            type="info"
            showIcon
            icon={<SyncOutlined spin />}
        />
        <div style={{ marginTop: 20 }}>
            <Text type="secondary">Do not close this window.</Text>
        </div>
    </Card>
  );

  return (
    <div style={{ maxWidth: 1400, margin: "0 auto", padding: 24 }}>
      
      {/* Header */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 24 }}>
        <Col>
           <Title level={2} style={{ margin: 0 }}>Cluster Topology</Title>
           <Text type="secondary">LCR Ring Consensus Visualization</Text>
        </Col>
        <Col>
            <Space>
                <Tag color={electionData?.election_active ? "green" : "red"}>
                    {electionData?.election_active ? "Election Active" : "Election Inactive"}
                </Tag>
                <Button icon={<ReloadOutlined />} onClick={checkElectionStatus}>Refresh</Button>
                <Button danger onClick={forceReElection}>Force Re-Election</Button>
            </Space>
        </Col>
      </Row>

      {error && <Alert message="Connection Error" description={error} type="error" showIcon style={{ marginBottom: 24 }} />}

      <Row gutter={[24, 24]}>
          
          {/* LEFT: Contextual Sidebar based on Role */}
          <Col xs={24} md={8} lg={6}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              
              {/* Role Specific Card */}
              {!loading && electionData && (
                  electionData.my_role === "Leader" ? renderLeaderSidebar() : renderWorkerSidebar()
              )}

              {/* Cluster Stats */}
              <Card title="Election Stats" size="small">
                <Statistic 
                  title="Current Leader IP" 
                  value={electionData?.current_leader || "Determining..."} 
                  valueStyle={{ color: '#cf1322', fontSize: 16 }}
                  prefix={<CrownOutlined />}
                />
                <Divider style={{ margin: '12px 0'}} />
                <Statistic 
                  title="Consensus Algorithm" 
                  value={electionData?.election_results?.election_method || "LCR"} 
                  valueStyle={{ fontSize: 14 }}
                />
                 <Divider style={{ margin: '12px 0'}} />
                 <Statistic 
                  title="My IP Address" 
                  value={electionData?.my_ip} 
                  valueStyle={{ fontSize: 14 }}
                />
              </Card>

              {/* Legend */}
              <Card size="small" title="Graph Legend">
                 <Space direction="vertical" size={0}>
                    <Space><Tag color="#FAAD14">●</Tag> Leader Node</Space>
                    <Space><Tag color="#722ED1">●</Tag> This Machine (Me)</Space>
                    <Space><Tag color="#1890ff">●</Tag> Worker Node</Space>
                 </Space>
              </Card>

            </Space>
          </Col>

          {/* RIGHT: The Topology Graph 

[Image of Network Topology Graph]
 */}
          <Col xs={24} md={16} lg={18}>
            <Card 
                bordered={false}
                bodyStyle={{ padding: 0, height: 600, overflow: 'hidden', background: '#f5f7fa', borderRadius: 8 }}
            >
              {loading ? (
                 <div style={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                    <Spin size="large" tip="Synchronizing Topology..." />
                 </div>
              ) : (
                  <ForceGraph2D
                    ref={graphRef}
                    graphData={graphData}
                    width={900} 
                    height={600}
                    nodeRelSize={8}
                    linkColor={() => "#b0b0b0"}
                    linkDirectionalArrowLength={6}
                    linkDirectionalArrowRelPos={1}
                    linkCurvature={0.3} // Distinctive ring shape
                    d3VelocityDecay={0.1} // Lower friction for smoother drift
                    cooldownTicks={100}
                    onEngineStop={() => graphRef.current?.zoomToFit(400, 50)}
                    nodeCanvasObject={(node, ctx, globalScale) => {
                        const label = node.name;
                        const fontSize = 14 / globalScale;
                        
                        // Draw Node
                        ctx.beginPath();
                        ctx.arc(node.x, node.y, node.val / globalScale, 0, 2 * Math.PI, false);
                        ctx.fillStyle = node.color;
                        ctx.fill();

                        // Draw Ring around 'Me'
                        if (node.is_me) {
                            ctx.beginPath();
                            ctx.arc(node.x, node.y, (node.val + 2) / globalScale, 0, 2 * Math.PI, false);
                            ctx.strokeStyle = '#722ED1';
                            ctx.lineWidth = 2 / globalScale;
                            ctx.stroke();
                        }

                        // Draw Label Background
                        ctx.font = `${fontSize}px Sans-Serif`;
                        const textWidth = ctx.measureText(label).width;
                        const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.5); 

                        ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
                        ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + 8, bckgDimensions[0], bckgDimensions[1]);

                        // Draw Text
                        ctx.textAlign = 'center';
                        ctx.textBaseline = 'middle';
                        ctx.fillStyle = '#000';
                        ctx.fillText(label, node.x, node.y + 8 + fontSize/2);

                        // Draw Icons (Crown for Leader)
                        if (node.role === 'Leader') {
                            ctx.fillStyle = '#FAAD14';
                            ctx.font = `${20 / globalScale}px serif`; 
                            ctx.fillText('👑', node.x, node.y - (node.val/globalScale) - 2);
                        }
                    }}
                  />
              )}
            </Card>
          </Col>
        </Row>
    </div>
  );
};

export default ElectionResultPage;