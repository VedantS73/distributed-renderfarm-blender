import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Card,
  Space,
  Row,
  Col,
  Typography,
  Tag,
  Statistic,
  Badge,
} from "antd";
import { ReloadOutlined, SyncOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;

const ClusterStatus = ({ localInfo, electionDetails, devices, isRunning, fetchDevices, fetchElectionStatus }) => {
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
        const isSelf =
          record.name === localInfo.pcName && record.ip === localInfo.ip;
        let role = "Worker";

        if (electionDetails) {
          if (electionDetails.current_leader === record.ip) {
            role = "Leader";
          } else if (isSelf && electionDetails.my_role) {
            role = electionDetails.my_role;
          } else if (electionDetails.election_results?.ring_topology) {
            const node = electionDetails.election_results.ring_topology.find(
              (n) => n.ip === record.ip
            );
            if (node) role = node.role;
          }
        }

        return (
          <Tag color={role === "Leader" ? "gold" : isSelf ? "purple" : "blue"}>
            {role} {isSelf ? "(Me)" : ""}
          </Tag>
        );
      },
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
      render: (score) => <Text strong>{score}</Text>,
    },
    {
      title: "Status",
      key: "status",
      render: (_, record) => {
        const isSelf =
          record.name === localInfo.pcName && record.ip === localInfo.ip;
        if (isSelf) return <Badge status="success" text="Ready" />;
        return isDeviceOnline(record) ? (
          <Badge status="success" text="Online" />
        ) : (
          <Badge status="error" text="Offline" />
        );
      },
    },
  ];

  return (
    <Col span={8}>
      <Row
        justify="space-between"
        align="middle"
        style={{ marginBottom: 8, marginTop: 8 }}
      >
        <Title level={4} style={{ margin: 0 }}>
          Cluster Status
        </Title>
        <Space>
          <Tag
            icon={<SyncOutlined spin={isRunning} />}
            color={isRunning ? "processing" : "default"}
          >
            {isRunning ? "Live" : "Stopped"}
          </Tag>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              fetchDevices();
              fetchElectionStatus();
            }}
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
        <div style={{ marginTop: 16, textAlign: "right" }}>
          <Space size="large">
            <Statistic
              title="Nodes in Ring"
              value={Math.max(0, devices.length)}
              valueStyle={{ fontSize: 16 }}
            />
            <Statistic
              title="Total Compute Score"
              value={devices.reduce(
                (acc, curr) => acc + (curr.resource_score || 0),
                0
              )}
              valueStyle={{ fontSize: 16 }}
            />
          </Space>
        </div>
      )}
    </Col>
  );
};

export default ClusterStatus;