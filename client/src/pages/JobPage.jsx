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
  Checkbox,
  Select,
  Alert,
} from "antd";
import {
  ReloadOutlined,
  InboxOutlined,
} from "@ant-design/icons";
import { useNetwork } from "../context/NetworkContext";
import LeaderControlPanel from "./components/LeaderControlPanel";

const { Dragger } = Upload;
const { Title, Text } = Typography;
const { Option } = Select;

export default function JobPage() {
  const { isRunning, localInfo } = useNetwork();
  const [showLeaderPanel, setShowLeaderPanel] = useState(false);
  const API_BASE = "http://localhost:5050/api";
  const [loading, setLoading] = useState(true);
  const [leader, setLeader] = useState(null);
  const [myRole, setMyRole] = useState(null);
  const [jobDetails, setJobDetails] = useState(null); // metadata from mock backend
  const [uploading, setUploading] = useState(false);
  const [messageApi, contextHolder] = message.useMessage();
  const [form] = Form.useForm();
  const [selectedFile, setSelectedFile] = useState(null);
  const [jobSubmitted, setJobSubmitted] = useState(false);

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
  const handleUpload = async (file) => {
    setUploading(true);
    setSelectedFile(file);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/jobs/analyze`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setJobDetails(data);
      messageApi.success(`${file.name} uploaded successfully!`);
    } catch (error) {
      console.error("Error uploading file:", error);
      messageApi.error("Upload failed.");
    } finally {
      setUploading(false);
    }

    return false;
  };

  /* ---------------- Submit Job ---------------- */
  const submitRenderJob = async () => {
    if (!jobDetails) {
      messageApi.warning("Upload a blend file first!");
      return;
    }

    const values = await form.validateFields();
    const formData = new FormData();

    formData.append("file", selectedFile);
    Object.entries(values).forEach(([key, value]) => {
      formData.append(key, value);
    });

    try {
      const res = await fetch(`${API_BASE}/jobs/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) throw new Error();

      messageApi.success("Job successfully submitted to leader 🚀");
      setJobSubmitted(true);
    } catch {
      messageApi.error("Failed to submit job");
    }
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

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="Leader Election Status"
        description={
          <>
            <Text strong>Leader IP:</Text> <Text>{leader || "N/A"}</Text>
            <br />
            <Text strong>Your Role:</Text> <Text>{myRole || "N/A"}</Text>
          </>
        }
        action={
          isRunning && localInfo?.ip === leader ? (
            <Button
              type="primary"
              size="small"
              onClick={() => setShowLeaderPanel(prev => !prev)}
            >
              {showLeaderPanel ? "Hide Leader Controls" : "Open Leader Controls"}
            </Button>
          ) : null
        }
      />

      {showLeaderPanel && (
        <>
          <LeaderControlPanel />
          <Divider />
        </>
      )}

      {!jobSubmitted && (
        <>
          {/* ---------------- Upload ---------------- */}
          <Title level={5}>Upload your Blend File Here</Title>
          <Dragger
            name="file"
            beforeUpload={handleUpload}
            onRemove={() => {
              setSelectedFile(null);
              setJobDetails(null);
            }}
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

              <Form.Item name="initiator_is_participant" valuePropName="checked" value={false} label="Job Preference">
                <Checkbox>Participate as Worker</Checkbox>
              </Form.Item>
            </Form>
          )}

          <Divider />

          <Button
            type="primary"
            size="large"
            onClick={submitRenderJob}
            block
            disabled={!leader || !jobDetails}
          >
            Submit Job to Leader
          </Button>
        </>
      )}
      {jobSubmitted && (
        <Alert
          type="success"
          showIcon
          message="Job Submitted Successfully"
          description="Your render job has been sent to the leader node and is now queued for processing."
        />
      )}

    </Card>
  );
}
