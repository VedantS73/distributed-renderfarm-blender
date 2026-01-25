import { Card, Typography, Progress } from "antd";

const { Title } = Typography;

const LeaderControlPanel = () => {
    return (
        <Card >
            <Title level={5} style={{ marginTop: 0 }}>Render Progress:</Title>
            <Progress
                // steps={100}
                percent={1}
                style={{ width: "100%" }}
            />
        </Card>
    )
}

export default LeaderControlPanel;