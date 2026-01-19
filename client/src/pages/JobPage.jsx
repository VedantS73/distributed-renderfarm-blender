import React, { useEffect, useState, useCallback } from "react";
import {
  Card,
  Table,
  Typography,
  Button,
  Divider,
  message,
  Upload,
  Form,
  InputNumber,
  Select,
} from "antd";
import {
  ReloadOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import { useNetwork } from "../context/NetworkContext";

const { Dragger } = Upload;
const { Title, Text } = Typography;
const { Option } = Select;

export default function JobPage() {
  const { isRunning } = useNetwork();
  const API_BASE = "http://localhost:5050/api";
  const [loading, setLoading] = useState(true);
  const [leader, setLeader] = useState(null);
  const [myRole, setMyRole] = useState(null);
  const [jobDetails, setJobDetails] = useState(null); // metadata from mock backend
  const [uploading, setUploading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();

  /* ---------------- Election Status ---------------- */
  const checkElectionStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/election/status`);
      const data = await response.json();

      if (data.current_leader) {
        setLeader(data.current_leader);
        setMyRole(data.my_role);
        setLoading(false);
      } else {
        console.log("No leader elected yet.");
      }
    } catch (error) {
      console.error("Error checking election status:", error);
    }
  }, []);

  useEffect(() => {
    checkElectionStatus();
  }, []);

  /* ---------------- Upload Handler ---------------- */
  const handleUpload = async ({ file }) => {
    setUploading(true);

    // Mock backend request (replace with your actual API)
    setTimeout(() => {
      // Fake response data
      const mockResponse = {
        renderer: "Cycles",
        frame_start: 1,
        frame_end: 250,
        fps: 24,
      };

      setJobDetails(mockResponse);
      messageApi.success(`${file.name} uploaded successfully!`);
      setUploading(false);
    }, 1000);

    return false; // prevent default upload to server
  };

  /* ---------------- Submit Job ---------------- */
  const submitRenderJob = async () => {
    if (!jobDetails) {
      messageApi.warning("Upload a blend file first!");
      return;
    }

    console.log("Submitting render job to leader:", leader);
    console.log("Job Details:", jobDetails);
    messageApi.success("Job submitted successfully!");
  };

  /* ---------------- Render ---------------- */
  return (
    <Card
      title={<Title level={4}>Job Submission Page</Title>}
      extra={
        <Button
          icon={<ReloadOutlined />}
          onClick={checkElectionStatus}
          loading={loading}
        >
          Refresh
        </Button>
      }
      style={{ height: "100%" }}
    >
      {contextHolder}

      <Title level={5} style={{ marginTop: 12 }}>Leader Elected</Title>
      <Text strong>Leader IP:</Text> <Text>{leader || "N/A"}</Text>
      <br />
      <Text strong>Your Role:</Text> <Text>{myRole || "N/A"}</Text>
      <Divider />

      {/* ---------------- Upload ---------------- */}
      <Title level={5}>Upload your Blend File Here</Title>
      <Dragger
        name="file"
        beforeUpload={handleUpload}
        accept=".blend"
        maxCount={1}
        showUploadList={{ showRemoveIcon: true }}
        loading={uploading}
        style={{ marginTop: 16 }}
        >
        <p className="ant-upload-drag-icon">
            <InboxOutlined style={{ fontSize: 32, color: "#1890ff" }} />
        </p>
        <p className="ant-upload-text">
            Click or drag your .blend file here to upload
        </p>
        <p className="ant-upload-hint">
            Only one file is allowed. You can edit metadata after uploading.
        </p>
        </Dragger>

      {/* ---------------- Job Metadata ---------------- */}
      {jobDetails && (
        <Form
          form={form}
          layout="vertical"
          style={{ marginTop: 16 }}
          initialValues={jobDetails}
        >
          <Form.Item label="Renderer" name="renderer">
            <Select>
              <Option value="Cycles">Cycles</Option>
              <Option value="Eevee">Eevee</Option>
              <Option value="Workbench">Workbench</Option>
            </Select>
          </Form.Item>

          <Form.Item label="Frame Start" name="frame_start">
            <InputNumber min={1} />
          </Form.Item>

          <Form.Item label="Frame End" name="frame_end">
            <InputNumber min={1} />
          </Form.Item>

          <Form.Item label="FPS" name="fps">
            <InputNumber min={1} max={240} />
          </Form.Item>
        </Form>
      )}

      <Divider />

      {/* ---------------- Submit Button ---------------- */}
      <Button
        type="primary"
        size="large"
        onClick={submitRenderJob}
        block
        disabled={!leader || !jobDetails}
      >
        Submit Job to Leader
      </Button>
    </Card>
  );
}
