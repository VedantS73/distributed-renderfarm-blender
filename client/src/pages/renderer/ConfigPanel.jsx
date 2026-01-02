import React from "react";
import { Card, Typography, Descriptions, Divider, Form, Row, Col, InputNumber, Select, Radio, Button, Space } from "antd";
import { PlayCircleOutlined } from "@ant-design/icons";

const { Title } = Typography;

const ConfigPanel = ({ 
  sceneInfo, 
  renderConfig, 
  onStartRender, 
  onBack,
  form 
}) => {
  return (
    <Card bordered={false} style={{ minHeight: 400 }}>
      <Title level={4}>Render Configuration</Title>
      <Divider />
      
      {sceneInfo && (
        <Descriptions 
          title="Scene Information" 
          bordered 
          column={2}
          style={{ marginBottom: 24 }}
        >
          <Descriptions.Item label="Scene Name">{sceneInfo.sceneName}</Descriptions.Item>
          <Descriptions.Item label="Total Frames">{sceneInfo.totalFrames}</Descriptions.Item>
          <Descriptions.Item label="Frame Rate">{sceneInfo.frameRate} fps</Descriptions.Item>
          <Descriptions.Item label="Render Engine">{sceneInfo.renderEngine}</Descriptions.Item>
          <Descriptions.Item label="Duration">
            {sceneInfo.duration ? `${sceneInfo.duration.toFixed(2)}s` : 'N/A'}
          </Descriptions.Item>
        </Descriptions>
      )}
      
      <Form
        form={form}
        layout="vertical"
        initialValues={renderConfig}
        onFinish={onStartRender}
      >
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              label="Start Frame"
              name="startFrame"
              rules={[{ required: true }]}
            >
              <InputNumber 
                min={1} 
                max={sceneInfo?.totalFrames || 1000}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              label="End Frame"
              name="endFrame"
              rules={[{ required: true }]}
            >
              <InputNumber 
                min={1} 
                max={sceneInfo?.totalFrames || 1000}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </Col>
        </Row>
        
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              label="Samples"
              name="samples"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value={64}>64 Samples</Select.Option>
                <Select.Option value={128}>128 Samples</Select.Option>
                <Select.Option value={256}>256 Samples</Select.Option>
                <Select.Option value={512}>512 Samples</Select.Option>
              </Select>
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              label="Render Engine"
              name="engine"
              rules={[{ required: true }]}
            >
              <Select>
                <Select.Option value="CYCLES">Cycles</Select.Option>
                <Select.Option value="BLENDER_EEVEE">Eevee</Select.Option>
              </Select>
            </Form.Item>
          </Col>
        </Row>
        
        <Row gutter={16}>
          <Col span={12}>
            <Form.Item
              label="Resolution X"
              name="resolutionX"
              rules={[{ required: true }]}
            >
              <InputNumber min={320} max={7680} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item
              label="Resolution Y"
              name="resolutionY"
              rules={[{ required: true }]}
            >
              <InputNumber min={240} max={4320} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>
        
        <Form.Item
          label="Output Format"
          name="outputFormat"
          rules={[{ required: true }]}
        >
          <Radio.Group>
            <Radio value="PNG">PNG</Radio>
            <Radio value="JPEG">JPEG</Radio>
            <Radio value="EXR">EXR</Radio>
          </Radio.Group>
        </Form.Item>
        
        <Form.Item style={{ textAlign: 'right', marginTop: 24 }}>
          <Space>
            <Button onClick={onBack}>
              Back
            </Button>
            <Button 
              type="primary" 
              htmlType="submit"
              icon={<PlayCircleOutlined />}
            >
              Start Render
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default ConfigPanel;