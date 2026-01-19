import React, { useEffect, useState, useCallback } from "react";
import {
  Card,
  Typography,
  Button,
  Empty,
  message,
} from "antd";
import {
  ReloadOutlined,
} from "@ant-design/icons";
import { useNetwork } from "../context/NetworkContext";
import RingTopology from "./RingTopology";

const { Title, Text } = Typography;

export default function ElectionPage() {
  const { enterNetwork, isRunning, leaveNetwork } = useNetwork();
  const API_BASE = "http://localhost:5050/api";
  const [loading, setLoading] = useState(true);
  const [electionActive, setElectionActive] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const [myRole, setMyRole] = useState(null);
  const [leader, setLeader] = useState(null);
const [consensus, setConsensus] = useState(null);
const [ring, setRing] = useState([]);

  const checkElectionStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/election/status`);
      const data = await response.json();

      if (data.election_active && data.election_results) {

        setElectionActive(true);
        setLeader(data.current_leader);
        setConsensus(data.leader_consensus);
        setRing(data.ring_topology);
        setMyRole(data.my_role);
      }
    } catch (error) {
      console.error("Error checking election status:", error);
    }
  }, []);


  const initialeLeaderElection = async () => {
    try {
      const response = await fetch(`${API_BASE}/election/start`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      setLoading(true);
      const data = await response.json();
      console.log("Election start response:", data);

    } catch (error) {
      console.error("Error starting election:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkElectionStatus();

    if (!isRunning || electionActive) return;

    const electionInterval = setInterval(() => {
      checkElectionStatus();
    }, 2000);

    return () => clearInterval(electionInterval);
  }, [isRunning, electionActive, checkElectionStatus]);

  return (
    <Card
      title={<Title level={4}>Leader Election</Title>}
      extra={
        <>
          <Button
            icon={<ReloadOutlined />}
            onClick={initialeLeaderElection}
            loading={loading}
            disabled={electionActive}
          >
            {electionActive ? "Election Completed" : "Start Election"}
          </Button>

          {electionActive && (
            <Button
              icon={<ReloadOutlined />}
              onClick={initialeLeaderElection}
              style={{ marginLeft: 8 }}
              type="warning"
            >
            </Button>
          )}
        </>
      }
      style={{ height: "100%" }}
    >
      {electionActive ? (
        <>
          <Title level={5}>Leader Elected</Title>
          <Text strong>Leader IP:</Text> <Text>{leader}</Text>
          <br />

          <Text strong>Your Role:</Text> <Text>{myRole}</Text>
          <br />

          {consensus?.consensus_reached && (
            <>
              <Text strong>Consensus:</Text>{" "}
              <Text>
                {consensus.total_nodes} nodes agreed on leader
              </Text>
            </>
          )}

          <RingTopology nodes={ring} />

          <Title level={5} style={{ marginTop: 16 }}>Ring Topology</Title>
          {ring.map((node) => (
            <Card
              key={node.ip}
              size="small"
              style={{ marginBottom: 8 }}
            >
              <Text strong>{node.name}</Text> — {node.ip}
              <br />
              Role: {node.is_leader ? "Leader" : "Worker"}
            </Card>
          ))}
        </>
      ) : (
        <Empty
          description="No leader has been elected yet."
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}
    </Card>
    
  );
}