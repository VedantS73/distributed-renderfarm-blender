import React from "react";
import { Card, Typography, Tag, Button, Progress, Upload } from "antd";
import { InboxOutlined, FileOutlined, EyeOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;
const { Dragger } = Upload;

const UploadPanel = ({ 
  uploadBlendFile, 
  uploading, 
  uploadProgress, 
  uploadedFile,
  onViewDetails 
}) => {
  return (
    <Card bordered={false} style={{ minHeight: 400, textAlign: 'center' }}>
      <Title level={4}>Upload Blender File</Title>
      <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
        Upload your .blend file to start distributed rendering
      </Text>
      
      <Dragger
        name="blend_file"
        accept=".blend"
        customRequest={({ file, onSuccess }) => {
          uploadBlendFile(file);
          onSuccess("ok");
        }}
        showUploadList={false}
        disabled={uploading}
        style={{ padding: 40, marginBottom: 24 }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text">
          Click or drag .blend file to this area to upload
        </p>
        <p className="ant-upload-hint">
          Supports single .blend file. Maximum file size: 2GB
        </p>
      </Dragger>
      
      {uploading && (
        <Progress
          percent={uploadProgress}
          status="active"
          style={{ maxWidth: 400, margin: '0 auto' }}
        />
      )}
      
      {uploadedFile && (
        <div style={{ marginTop: 24 }}>
          <Tag icon={<FileOutlined />} color="blue">
            {uploadedFile.name} ({(uploadedFile.size / (1024 * 1024)).toFixed(2)} MB)
          </Tag>
          <Button 
            type="link" 
            icon={<EyeOutlined />}
            onClick={onViewDetails}
          >
            View Scene Details
          </Button>
        </div>
      )}
    </Card>
  );
};

export default UploadPanel;