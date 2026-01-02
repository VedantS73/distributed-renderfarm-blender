import React from "react";
import { Card, Typography, Progress, Spin, Tag, List, Avatar } from "antd";
import { LoadingOutlined, CheckCircleOutlined, DesktopOutlined } from "@ant-design/icons";

const { Title } = Typography;

const ProgressPanel = ({ renderProgress, workerProgress }) => {
  return (
    <Card bordered={false} style={{ minHeight: 400 }}>
      <Title level={4}>Render Progress</Title>
      
      {/* Overall Progress */}
      <div style={{ textAlign: 'center', marginBottom: 32 }}>
        <Progress
          type="circle"
          percent={renderProgress.progress}
          width={150}
          format={percent => (
            <div>
              <div style={{ fontSize: 24, fontWeight: 'bold' }}>{percent}%</div>
              <div style={{ fontSize: 12, color: '#999' }}>
                {renderProgress.completedFrames} / {renderProgress.totalFrames} frames
              </div>
            </div>
          )}
        />
        <div style={{ marginTop: 16 }}>
          {renderProgress.isRendering ? (
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
          ) : (
            <Tag icon={<CheckCircleOutlined />} color="success">
              Render Complete
            </Tag>
          )}
        </div>
      </div>
      
      {/* Frame Status Grid */}
      <div style={{ marginBottom: 32 }}>
        <Title level={5}>Frame Status</Title>
        <div style={{ 
          display: 'flex', 
          flexWrap: 'wrap', 
          gap: 8,
          maxHeight: 200,
          overflowY: 'auto',
          padding: 8,
          border: '1px solid #f0f0f0',
          borderRadius: 8
        }}>
          {renderProgress.frameStatus.map((frame, index) => (
            <div
              key={index}
              style={{
                width: 40,
                height: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 4,
                backgroundColor: 
                  frame.status === 'completed' ? '#52c41a' :
                  frame.status === 'processing' ? '#1890ff' :
                  frame.status === 'failed' ? '#ff4d4f' : '#f0f0f0',
                color: frame.status === 'pending' ? '#999' : 'white',
                fontWeight: 'bold',
                cursor: 'pointer'
              }}
              title={`Frame ${frame.frame}: ${frame.status}`}
            >
              {frame.frame}
            </div>
          ))}
        </div>
      </div>
      
      {/* Worker Progress */}
      <div>
        <Title level={5}>Worker Progress</Title>
        <List
          dataSource={Object.entries(workerProgress)}
          renderItem={([workerId, progress]) => (
            <List.Item>
              <List.Item.Meta
                avatar={<Avatar icon={<DesktopOutlined />} />}
                title={`Worker ${workerId}`}
                description={`Assigned Frames: ${progress.assignedFrames || 0} | Completed: ${progress.completedFrames || 0}`}
              />
              <Progress 
                percent={progress.percentage || 0} 
                size="small" 
                style={{ width: 200 }}
              />
            </List.Item>
          )}
          locale={{ emptyText: 'No worker progress data available' }}
        />
      </div>
    </Card>
  );
};

export default ProgressPanel;