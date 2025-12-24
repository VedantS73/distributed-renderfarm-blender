import React, { useState, useEffect, useRef } from "react";
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
  Space 
} from "antd";
import { 
  CrownOutlined, 
  UserOutlined, 
  ReloadOutlined, 
  ClusterOutlined 
} from "@ant-design/icons";
import ForceGraph2D from "react-force-graph-2d";
import { useNavigate } from "react-router-dom";

const { Title, Text } = Typography;

const ElectionResultPage = () => {
  const navigate = useNavigate();
  const graphRef = useRef();
  
  const [loading, setLoading] = useState(true);
  const [electionData, setElectionData] = useState(null);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [error, setError] = useState(null);

  // 1. Function to trigger election
  const startElection = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("http://localhost:5050/api/election/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) throw new Error("Failed to start election");

      const result = await response.json();
      
      // 2. Process data for the Graph
      // The API returns 'ring_topology'. We need to convert this to nodes/links.
      if (result.data && result.data.ring_topology) {
        const topology = result.data.ring_topology;

        const nodes = topology.map((node) => ({
          id: node.ip,
          name: node.name,
          val: node.role === "Leader" ? 20 : 10, // Leader is bigger
          color: node.role === "Leader" ? "#FFD700" : (node.is_me ? "#1890ff" : "#bfbfbf"),
          role: node.role,
          score: node.resource_score,
          is_me: node.is_me
        }));

        const links = topology.map((node) => ({
          source: node.ip,
          target: node.successor, // The ring connection
        }));

        setElectionData(result.data);
        setGraphData({ nodes, links });
      }
    } catch (err) {
      console.error(err);
      setError("Election failed. Ensure the Discovery Service is running.");
    } finally {
      setLoading(false);
    }
  };

  // Run on mount
  useEffect(() => {
    startElection();
  }, []);

  return (
    <div style={{ maxWidth: 1200, margin: "0 auto", padding: 24 }}>
      {error && <Alert message="Error" description={error} type="error" showIcon style={{ marginBottom: 24 }} />}

      {loading ? (
        <div style={{ textAlign: "center", padding: 100 }}>
          <Spin size="large" tip="Running Leader Election Algorithm..." />
        </div>
      ) : (
        <Row gutter={[24, 24]}>
          
          {/* LEFT: Stats & Leader Info */}
          <Col xs={24} md={8}>
            <Space direction="vertical" style={{ width: '100%' }} size="large">
              
              {/* Leader Card */}
              <Card 
                title={<Space><CrownOutlined style={{ color: '#FFD700' }}/> Elected Leader</Space>}
                bordered={false}
                style={{ borderTop: '4px solid #FFD700', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
              >
                <Statistic 
                  title="Leader IP" 
                  value={electionData?.leader_ip || "None"} 
                  valueStyle={{ color: '#cf1322' }}
                />
                <div style={{ marginTop: 16 }}>
                  <Text strong>Algorithm: </Text> <Tag>{electionData?.election_method}</Tag>
                </div>
              </Card>

              {/* My Status Card */}
              <Card title="Local Node Status" size="small">
                 <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text>Role:</Text>
                    <Tag color={electionData?.leader_ip === electionData?.initiator_ip ? "gold" : "default"}>
                        {electionData?.leader_ip === electionData?.initiator_ip ? "LEADER" : "WORKER"}
                    </Tag>
                 </div>
                 <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                    <Text>Initiator:</Text>
                    <Text code>{electionData?.initiator_ip}</Text>
                 </div>
              </Card>

              {/* Legend */}
              <Card title="Graph Legend" size="small">
                <Space direction="vertical">
                    <Space><div style={{width: 12, height: 12, borderRadius: '50%', background: '#FFD700'}}></div> Leader Node</Space>
                    <Space><div style={{width: 12, height: 12, borderRadius: '50%', background: '#1890ff'}}></div> My Machine</Space>
                    <Space><div style={{width: 12, height: 12, borderRadius: '50%', background: '#bfbfbf'}}></div> Worker Node</Space>
                </Space>
              </Card>

              <Card>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={startElection} 
                  loading={loading}
                >
                  Re-Run Election
                </Button>
                <Button 
                  icon={<ReloadOutlined />} 
                  onClick={() => navigate('/start-render')} 
                  loading={loading}
                >
                  Proceed
                </Button>
              </Card>

            </Space>
          </Col>

          {/* RIGHT: The Topology Graph */}
          <Col xs={24} md={16}>
            <Card 
                title="Ring Topology Visualization" 
                bordered={false}
                bodyStyle={{ padding: 0, height: 500, overflow: 'hidden', background: '#f0f2f5' }}
            >
              <ForceGraph2D
                ref={graphRef}
                graphData={graphData}
                width={800} // Adjust based on container or use a ResizeObserver wrapper
                height={500}
                nodeLabel={(node) => `${node.name} \nScore: ${node.score} \nIP: ${node.id}`}
                nodeRelSize={6}
                linkColor={() => "#999"}
                linkDirectionalArrowLength={3.5}
                linkDirectionalArrowRelPos={1}
                linkCurvature={0.2} // Makes links curved so ring is obvious
                cooldownTicks={100}
                onEngineStop={() => graphRef.current.zoomToFit(400)}
                nodeCanvasObject={(node, ctx, globalScale) => {
                  const label = node.name;
                  const fontSize = 12 / globalScale;
                  ctx.font = `${fontSize}px Sans-Serif`;
                  const textWidth = ctx.measureText(label).width;
                  const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); 

                  // Determine if node is both Leader and Self
                  const isLeaderAndSelf = node.role === 'Leader' && node.is_me;

                  // Draw Node Circle
                  ctx.beginPath();
                  ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
                  ctx.fillStyle = node.color;
                  ctx.fill();

                  // If both Leader and Self, draw outlined circles
                  if (isLeaderAndSelf) {
                    // Outer circle - Leader color
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 7, 0, 2 * Math.PI, false);
                    ctx.strokeStyle = '#FFD700';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                    
                    // Inner circle - Self color
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
                    ctx.fillStyle = '#1890ff';
                    ctx.fill();
                  }

                  // Draw Label
                  ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                  ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2 - 8, bckgDimensions[0], bckgDimensions[1]);
                  ctx.textAlign = 'center';
                  ctx.textBaseline = 'middle';
                  ctx.fillStyle = '#000';
                  ctx.fillText(label, node.x, node.y - 8);

                  // Draw Crown for Leader (moved down)
                  if (node.role === 'Leader') {
                     ctx.font = `${16/globalScale}px Sans-Serif`;
                     ctx.fillText('LEADER', node.x, node.y - 10); 
                  }
                  if (node.role === 'Worker') {
                     ctx.font = `${16/globalScale}px Sans-Serif`;
                     ctx.fillText('WORKER', node.x, node.y - 10); 
                  }
                }}
              />
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
};

export default ElectionResultPage;