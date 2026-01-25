import { useEffect, useState, useRef, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";

export default function RingTopology({ nodes, myIp }) {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const graphRef = useRef();

  useEffect(() => {
    if (!nodes || nodes.length === 0) {
      setGraphData({ nodes: [], links: [] });
      return;
    }

    // Process nodes for the graph
    const graphNodes = nodes.map((node) => ({
      id: node.ip,
      name: node.name || node.ip,
      val: node.is_leader ? 30 : 15,
      color: node.is_leader ? "#FAAD14" : (node.ip === myIp ? "#722ED1" : "#1890ff"),
      role: node.is_leader ? "Leader" : "Worker",
      is_me: node.ip === myIp,
      ip: node.ip,
      score: node.resource_score || 0,
    }));

    // Create ring links: each node connects to the next
    const graphLinks = nodes.map((node, index) => ({
      source: node.ip,
      target: nodes[(index + 1) % nodes.length].ip,
      color: '#d9d9d9',
      width: 2,
    }));

    // For 2 nodes, add curvature to show bidirectional ring
    if (nodes.length === 2) {
      graphLinks[0].curvature = 0.3;
      graphLinks[1] = {
        source: nodes[1].ip,
        target: nodes[0].ip,
        color: '#d9d9d9',
        width: 2,
        curvature: 0.3,
      };
    }

    setGraphData({
      nodes: graphNodes,
      links: graphLinks,
    });
  }, [nodes, myIp]);

  // Apply force settings after graph data updates
  useEffect(() => {
    if (graphRef.current && graphData.nodes.length > 0) {
      // Adjust link distance for better visualization
      if (graphRef.current.d3Force('link')) {
        graphRef.current.d3Force('link').distance(150);
      }
      
      // Reheat the simulation
      graphRef.current.d3ReheatSimulation();
      
      // Auto zoom to fit after a delay
      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.zoomToFit(400, 50);
        }
      }, 1000);
    }
  }, [graphData]);

  // Custom node rendering (same as your implementation)
  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
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
    ctx.fillRect(
      node.x - bckgDimensions[0] / 2, 
      node.y + 8, 
      bckgDimensions[0], 
      bckgDimensions[1]
    );

    // Draw Text
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#000';
    ctx.fillText(label, node.x, node.y + 8 + fontSize / 2);

    // Draw Crown for Leader
    if (node.role === 'Leader') {
      ctx.fillStyle = '#FAAD14';
      ctx.font = `${20 / globalScale}px serif`; 
      ctx.fillText('👑', node.x, node.y - (node.val / globalScale) - 2);
    }
  }, []);

  return (
    <div style={{ width: '100%', height: '400px', background: '#f5f7fa', borderRadius: 8 }}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={800}
        height={400}
        nodeRelSize={8}
        linkColor="color"
        linkDirectionalArrowLength={6}
        linkDirectionalArrowRelPos={1}
        linkCurvature="curvature"
        linkCurvatureRotation="rotation"
        d3VelocityDecay={0.1}
        cooldownTicks={100}
        enableNodeDrag={true}
        enableZoomInteraction={true}
        enablePanInteraction={true}
        nodeCanvasObject={nodeCanvasObject}
        onEngineStop={() => {
          // Auto-fit when simulation stops
          if (graphRef.current) {
            graphRef.current.zoomToFit(400, 50);
          }
        }}
      />
    </div>
  );
}