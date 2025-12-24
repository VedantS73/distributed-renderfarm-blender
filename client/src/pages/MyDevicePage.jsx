import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Typography,
  Checkbox,
  Table,
  Button,
  Tag,
  Space,
  message,
} from "antd";
import {
  GlobalOutlined,
  ReloadOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;

const MyDevicePage = () => {
  const navigate = useNavigate();
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
      const response = await fetch("http://localhost:5050/api/my_device");
      const data = await response.json();

      setDeviceData(data);

      // Auto-set checkboxes based on system checks
      setChecks({
        blender: data.checks.blender_installed,
        ffmpeg: data.checks.ffmpeg_installed,
        storage: data.checks.disk_sufficient,
      });

      message.success("System scan complete");
    } catch (error) {
      console.error("Could not fetch device info", error);
      message.error("Failed to contact server");
    } finally {
      setLoading(false);
    }
  };

  // Fetch on mount
  useEffect(() => {
    fetchDeviceInfo();
  }, []);

  const handleCheck = (key) => {
    setChecks((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Helper to format bytes to GB
  const formatGB = (bytes) => {
    if (!bytes) return "0 GB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + " GB";
  };

  const allChecked = checks.blender && checks.ffmpeg && checks.storage;

  // Prepare data
  const devicePropertiesData = deviceData
    ? [
        { key: "PC Name", value: deviceData.pc_name },
        {
          key: "IP Address",
          value: <Tag color="blue">{deviceData.local_ip}</Tag>,
        },
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

  // Table columns
  const deviceColumns = [
    {
      title: "Property",
      dataIndex: "key",
      key: "key",
      width: "40%",
      render: (text) => <Text strong>{text}</Text>,
    },
    {
      title: "Value",
      dataIndex: "value",
      key: "value",
      width: "60%",
    },
  ];

  const requirementsData = [
    {
      key: "blender",
      name: "Blender Installed",
      status: checks.blender,
    },
    {
      key: "ffmpeg",
      name: "FFMPEG Ready",
      status: checks.ffmpeg,
    },
    {
      key: "storage",
      name: "Storage Sufficient",
      status: checks.storage,
    },
  ];

  const requirementsColumns = [
    {
      title: "Requirement",
      dataIndex: "name",
      key: "name",
    },
    {
      title: "Status",
      dataIndex: "status",
      key: "status",
      render: (status, record) => (
        <Space>
          <Checkbox
            checked={status}
            onChange={() => handleCheck(record.key)}
            disabled={loading}
          />
          <Tag color={status ? "green" : "red"}>
            {status ? "OK" : "Missing"}
          </Tag>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Page Header */}
      <div
        style={{
          marginBottom: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <Button
          icon={<ReloadOutlined />}
          onClick={fetchDeviceInfo}
          loading={loading}
        >
          Rescan System
        </Button>
      </div>

      <Row gutter={24}>
        <Col span={24} md={10}>
          <Table
            dataSource={devicePropertiesData}
            columns={deviceColumns}
            pagination={false}
            bordered
            size="middle"
          />
        </Col>

        {/* --- RIGHT COLUMN: Checklist & Action --- */}
        <Col span={24} md={10}>
          <Table
            dataSource={requirementsData}
            columns={requirementsColumns}
            pagination={false}
            bordered
            size="middle"
          />
          <Checkbox
            checked={override}
            onChange={(e) => setOverride(e.target.checked)}
            style={{ marginTop: 16 }}
          >
            Override & Continue
          </Checkbox>

          <Button
            type="primary"
            size="large"
            icon={<GlobalOutlined />}
            disabled={(!allChecked && !override) || loading}
            onClick={() => navigate("/discovery")}
            block
            style={{ height: 50, marginTop: 8 }}
          >
            Enter Network
          </Button>
        </Col>
      </Row>
    </div>
  );
};

// Helper component for icon alignment with status color
const SpaceIcon = ({ icon, label, status }) => (
  <span
    style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 10,
      fontSize: 15,
    }}
  >
    {icon}
    <span style={{ color: status ? "inherit" : "#999" }}>{label}</span>
  </span>
);

export default MyDevicePage;
