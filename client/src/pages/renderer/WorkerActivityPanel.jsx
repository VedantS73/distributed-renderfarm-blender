import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Table,
  Button,
  Card,
  Descriptions,
  Badge,
  Space,
  Row,
  Col,
  message,
  Typography,
  Tag,
  Statistic,
  Result,
} from "antd";
import {
  ReloadOutlined,
  WifiOutlined,
  ClusterOutlined,
  SyncOutlined
} from "@ant-design/icons";

const { Title, Text } = Typography;

const WorkerActivityPanel = ({ electionDetails }) => {
  return (
    <Card bordered={false} style={{ minHeight: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Result
                icon={<ClusterOutlined style={{ color: '#1890ff' }} />}
                title="Worker Node Active"
                subTitle="Waiting for Leader to initiate render job..."
                extra={[
                   <div key="info" style={{ textAlign: 'left', background: '#f5f5f5', padding: 20, borderRadius: 8 }}>
                       <Descriptions title="Cluster Details" column={1} size="small">
                            <Descriptions.Item label="My Role">
                                <Tag color="blue">Worker</Tag>
                            </Descriptions.Item>
                            <Descriptions.Item label="Current Leader">
                                <Text code>{electionDetails?.current_leader || "Determining..."}</Text>
                            </Descriptions.Item>
                            <Descriptions.Item label="Election Method">
                                {electionDetails?.election_results?.election_method || "LCR"}
                            </Descriptions.Item>
                       </Descriptions>
                   </div>
                ]}
            />
        </Card>
  );
};

export default WorkerActivityPanel;