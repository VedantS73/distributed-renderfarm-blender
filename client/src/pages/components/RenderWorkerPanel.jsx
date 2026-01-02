import React from "react";
import { Steps } from "antd";
import UploadPanel from "../renderer/UploadPanel";
import ConfigPanel from "../renderer/ConfigPanel";
import ProgressPanel from "../renderer/ProgressPanel";

const { Step } = Steps;

const RenderWorkerPanel = ({
  currentStep,
  uploadBlendFile,
  uploading,
  uploadProgress,
  uploadedFile,
  sceneInfo,
  renderConfig,
  form,
  onStartRender,
  onStepChange,
  renderProgress,
  workerProgress
}) => {
  const steps = [
    {
      title: 'Upload',
      description: 'Upload .blend file',
    },
    {
      title: 'Configure',
      description: 'Set render settings',
    },
    {
      title: 'Render',
      description: 'Monitor progress',
    },
  ];

  return (
    <>
      <Steps current={currentStep} style={{ marginBottom: 32 }}>
        {steps.map((item, index) => (
          <Step key={index} title={item.title} description={item.description} />
        ))}
      </Steps>
      
      {currentStep === 0 && (
        <UploadPanel
          uploadBlendFile={uploadBlendFile}
          uploading={uploading}
          uploadProgress={uploadProgress}
          uploadedFile={uploadedFile}
          onViewDetails={() => onStepChange(1)}
        />
      )}
      
      {currentStep === 1 && (
        <ConfigPanel
          sceneInfo={sceneInfo}
          renderConfig={renderConfig}
          form={form}
          onStartRender={onStartRender}
          onBack={() => onStepChange(0)}
        />
      )}
      
      {currentStep === 2 && (
        <ProgressPanel
          renderProgress={renderProgress}
          workerProgress={workerProgress}
        />
      )}
    </>
  );
};

export default RenderWorkerPanel;