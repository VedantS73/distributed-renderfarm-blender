import React, { useEffect, useState } from "react";
import {
  Card,
  Table,
  Typography,
  Checkbox,
  Button,
  Tag,
  Space,
  Divider,
  message,
} from "antd";
import {
  ReloadOutlined,
  GlobalOutlined,
} from "@ant-design/icons";
import { useNetwork } from "../context/NetworkContext";

const { Title, Text } = Typography;

export default function DeviceCheckPanel() {
  const { enterNetwork, isRunning, leaveNetwork } = useNetwork();

  const [loading, setLoading] = useState(true);
  const [override, setOverride] = useState(false);
  const [deviceData, setDeviceData] = useState(null);
  const [checks, setChecks] = useState({
    blender: false,
    ffmpeg: false,
    storage: false,
  });

  const fetchDeviceInfo = async () => {
    setLoading(true);
    try {
      const res = await fetch("http://localhost:5050/api/my_device");
      const data = await res.json();

      setDeviceData(data);
      setChecks({
        blender: data.checks.blender_installed,
        ffmpeg: data.checks.ffmpeg_installed,
        storage: data.checks.disk_sufficient,
      });

      message.success("System scan completed");
    } catch {
      message.error("Failed to fetch system data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeviceInfo();
  }, []);

  const allChecked = Object.values(checks).every(Boolean);

  const formatGB = (b) =>
    b ? `${(b / (1024 ** 3)).toFixed(1)} GB` : "0 GB";

  /* ---------------- Tables ---------------- */

  const systemInfo = deviceData
    ? [
        { key: "PC Name", value: deviceData.pc_name },
        { key: "IP Address", value: <Tag>{deviceData.local_ip}</Tag> },
        { key: "CPU Usage", value: `${Math.round(deviceData.cpu_usage)}%` },
        {
          key: "Memory Usage",
          value: `${formatGB(deviceData.memory_used)} / ${formatGB(
            deviceData.memory_total
          )}`,
        },
        { key: "Disk Usage", value: `${Math.round(deviceData.disk_usage)}%` },
      ]
    : [];

  const systemColumns = [
    {
      title: "System Property",
      dataIndex: "key",
      width: "45%",
      render: (t) => <Text strong>{t}</Text>,
    },
    {
      title: "Value",
      dataIndex: "value",
    },
  ];

  const checkData = [
    { key: "blender", name: "Blender Installed", status: checks.blender },
    { key: "ffmpeg", name: "FFmpeg Available", status: checks.ffmpeg },
    { key: "storage", name: "Sufficient Disk Space", status: checks.storage },
  ];

  const checkColumns = [
    {
      title: "Requirement",
      dataIndex: "name",
      render: (t) => <Text>{t}</Text>,
    },
    {
      title: "Status",
      dataIndex: "status",
      width: 180,
      render: (status, record) => (
        <Space>
          <Checkbox
            checked={status}
            onChange={() =>
              setChecks((p) => ({ ...p, [record.key]: !p[record.key] }))
            }
            disabled={loading}
          />
          <Tag color={status ? "green" : "red"}>
            {status ? "OK" : "Missing"}
          </Tag>
        </Space>
      ),
    },
  ];

  /* ---------------- Render ---------------- */

  return (
    <Card
      title={<Title level={4}>Device Readiness Check</Title>}
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchDeviceInfo}
          loading={loading}
        >
          Rescan
        </Button>
      }
      style={{ height: "100%" }}
    >
      {/* ---- System Info ---- */}
      <Divider orientation="left">System Overview</Divider>
      <Table
        dataSource={systemInfo}
        columns={systemColumns}
        pagination={false}
        size="small"
        bordered
        rowKey="key"
      />

      {/* ---- Requirements ---- */}
      <Divider orientation="left">Network Requirements</Divider>
      <Table
        dataSource={checkData}
        columns={checkColumns}
        pagination={false}
        size="small"
        bordered
        rowKey="key"
      />

      {/* ---- Action ---- */}
      <Divider />

      {!isRunning && (
        <>
          <Checkbox
            checked={override}
            onChange={(e) => setOverride(e.target.checked)}
            style={{ marginBottom: 12 }}
          >
            Override failed checks and continue
          </Checkbox>

          <Button
            type="primary"
            size="large"
            icon={<GlobalOutlined />}
            disabled={(!allChecked && !override) || loading}
            onClick={enterNetwork}
            block
          >
            Enter Network
          </Button>
        </>
      )}

      {isRunning && (
        <Button
          danger
          size="large"
          onClick={leaveNetwork}
          block
        >
          Disconnect from Network
        </Button>
      )}
      
    </Card>
    
  );
}
