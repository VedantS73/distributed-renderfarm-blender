import { Table, Badge, Empty, Typography, theme, Tooltip } from "antd";
import { useNetwork } from "../../context/NetworkContext";
import {
  WifiOutlined,
  DisconnectOutlined,
  CrownFilled,
  BorderInnerOutlined,
} from "@ant-design/icons";
import { Modal, Button } from "antd";
import { ExclamationCircleOutlined } from "@ant-design/icons";
import { useEffect, useState } from "react";
import axios from "axios";

const { Text } = Typography;

const DevicesSystemSidebar = ({ collapsed }) => {
  const API_BASE = "http://localhost:5050/api";
  const [leaderElected, setLeaderElected] = useState(false);
  const [showLeaderDownModal, setShowLeaderDownModal] = useState(false);
  const [leaderDevice, setLeaderDevice] = useState(null);
  const [previousDeviceStatus, setPreviousDeviceStatus] = useState({});
  const [fatalCrashDetected, setFatalCrashDetected] = useState(false);

  const {
    token: { colorText, colorBorder },
  } = theme.useToken();
  const { devices, isRunning, localInfo, stats } = useNetwork();

  const isOnline = (d) => d.timestamp && (Date.now() - d.timestamp) / 1000 < 15;

  const getSecondsSinceLastSeen = (device) => {
    if (!device.timestamp) return 0;
    return Math.floor((Date.now() - device.timestamp) / 1000);
  };

  const getDeviceStatus = (record) => {
    if (record.name === localInfo.pcName && record.ip === localInfo.ip) {
      return { status: "warning", text: "Self" };
    }

    const online = isOnline(record);
    if (online) {
      return { status: "success", text: "Online" };
    } else {
      return { status: "error", text: "Offline" };
    }
  };

  useEffect(() => {
    if (!leaderElected) return;
    console.log("Checking leader device status...");
    const leader = devices.find((d) => d.my_role === "Leader");
    if (!leader) return;
    console.log("Leader device found:", leader);

    const online = isOnline(leader);

    if (!online) {
      setLeaderDevice(leader);
      setShowLeaderDownModal(true);
      console.log("Leader device is offline:", leader);
      const notifyLeaderDown = async () => {
        try {
          console.log("Notifying backend of leader down...");
          // const response = await axios.post(
          //   `${API_BASE}/leader_is_down_flag`
          // );

          // if (response.data.leader_is_down) {
          //   setFatalCrashDetected(true);
          // }
        } catch (err) {
          console.error("Failed to hit leader_is_down_flag", err);
        }
      };

      notifyLeaderDown();
    }
  }, [devices, leaderElected]);

  useEffect(() => {
    if (devices.some((d) => d.my_role === "Leader")) {
      setLeaderElected(true);
    }
  }, [devices]);

  // Track device status and detect when non-leader devices go offline
  useEffect(() => {
    const currentStatus = {};

    devices.forEach((device) => {
      const deviceKey = `${device.name}-${device.ip}`;
      const isSelf =
        device.name === localInfo.pcName && device.ip === localInfo.ip;
      const online = isOnline(device);
      const isLeader = device.my_role === "Leader";

      currentStatus[deviceKey] = online;

      // Check if device just went offline (was online before, now offline)
      if (
        !isSelf &&
        !isLeader &&
        previousDeviceStatus[deviceKey] === true &&
        online === false
      ) {
        // Device just went offline, call the API
        handleNodeDisconnected(device.ip, device.name);
      }
    });

    setPreviousDeviceStatus(currentStatus);
  }, [devices, localInfo]);

  const handleNodeDisconnected = async (ip, name) => {
    try {
      // const response = await axios.post(`${API_BASE}/node_disconnected`, {
      //   ip: ip,
      // });

      if (response.data.success) {
        console.log(`Device ${name} (${ip}) removed from network`);
      }
    } catch (err) {
      console.error(
        `Failed to notify disconnection of device ${name} (${ip})`,
        err,
      );
    }
  };

  const reElectLeader = async () => {
    try {
      console.log("Re-electing leader, forcing removal of:", leaderDevice);
      // await axios.post(
      //   `${API_BASE}/election/start?force_remove=${leaderDevice.ip}`,
      // );

      // setShowLeaderDownModal(false);
      // setLeaderElected(false); // backend will broadcast new leader
    } catch (err) {
      console.error("Leader re-election failed", err);
    }
  };

  const columns = [
    {
      title: "#",
      width: 32,
      align: "center",
      render: (_, record) => {
        const role = record.my_role;

        let icon;
        let tooltipTitle = role || "Undefined";

        if (role === "Leader") {
          icon = <CrownFilled style={{ color: "#ffec3d", fontSize: 16 }} />;
        } else if (role === "Worker") {
          icon = (
            <div
              style={{
                width: 10,
                height: 10,
                backgroundColor: "#722ed1", // Purple
                borderRadius: "2px",
                margin: "0 auto",
              }}
            />
          );
        } else {
          // Default Undefined Yellow Dot
          icon = (
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: "#faad14", // Yellow
                margin: "0 auto",
              }}
            />
          );
        }

        return (
          <Tooltip title={tooltipTitle}>
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
              }}
            >
              {icon}
            </div>
          </Tooltip>
        );
      },
    },
    {
      title: "Device",
      dataIndex: "name",
      width: collapsed ? 100 : 150,
      render: (text, record) => {
        const isSelf =
          record.name === localInfo.pcName && record.ip === localInfo.ip;
        return isSelf ? (
          <Text strong style={{ fontSize: collapsed ? 12 : 14 }}>
            {text} (You)
          </Text>
        ) : (
          <Text style={{ fontSize: collapsed ? 12 : 14 }}>{text}</Text>
        );
      },
    },
    {
      title: "IP",
      dataIndex: "ip",
      width: collapsed ? 80 : 120,
      render: (text) => (
        <Text type="secondary" style={{ fontSize: collapsed ? 10 : 12 }}>
          {text}
        </Text>
      ),
    },
    {
      title: "Score",
      dataIndex: "resource_score",
      width: collapsed ? 60 : 80,
      align: "center",
      render: (score) => (
        <Text style={{ fontSize: collapsed ? 12 : 14 }}>
          {score !== undefined && score !== null ? score : 0}
        </Text>
      ),
    },
    {
      title: "Status",
      width: collapsed ? 70 : 90,
      render: (_, record) => {
        const status = getDeviceStatus(record);
        const secondsAgo = getSecondsSinceLastSeen(record);
        const tooltipText =
          record.name === localInfo.pcName
            ? "This device"
            : `Last seen ${secondsAgo} seconds ago`;

        return (
          <Tooltip title={tooltipText}>
            <Badge
              status={status.status}
              text={collapsed ? "" : status.text}
              style={{ fontSize: collapsed ? 10 : 12 }}
            />
          </Tooltip>
        );
      },
    },
  ];

  if (!isRunning) {
    return (
      <div style={{ padding: collapsed ? 8 : 16 }}>
        <Empty
          description={
            <Text type="secondary" style={{ fontSize: collapsed ? 12 : 14 }}>
              Device is not connected to the network
            </Text>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          imageStyle={{ height: collapsed ? 40 : 60 }}
        />
      </div>
    );
  }

  // Sort devices: self first, then by resource score
  const sortedDevices = [...devices].sort((a, b) => {
    const aIsSelf = a.name === localInfo.pcName && a.ip === localInfo.ip;
    const bIsSelf = b.name === localInfo.pcName && b.ip === localInfo.ip;

    if (aIsSelf) return -1;
    if (bIsSelf) return 1;
    return (b.resource_score || 0) - (a.resource_score || 0);
  });

  const onlineCount = sortedDevices.filter((d) => isOnline(d)).length;
  const offlineCount = sortedDevices.filter(
    (d) => !isOnline(d) && !(d.name === localInfo.pcName),
  ).length;

  return (
    <div
      style={{
        padding: collapsed ? 4 : 8,
        height: "100%",
      }}
    >
      {/* Stats Summary */}
      {!collapsed && (
        <div
          style={{
            marginBottom: 8,
            padding: 8,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Text style={{ fontSize: 12 }}>
              Devices: {stats?.total_devices || devices.length}
            </Text>
            <div style={{ display: "flex", gap: 12 }}>
              <Text type="success" style={{ fontSize: 12 }}>
                <WifiOutlined /> {onlineCount}
              </Text>
              <Text type="danger" style={{ fontSize: 12 }}>
                <DisconnectOutlined /> {offlineCount}
              </Text>
            </div>
          </div>
        </div>
      )}

      {/* Devices Table */}
      <Table
        size="small"
        pagination={false}
        rowKey={(r) => `${r.name}-${r.ip}`}
        columns={columns}
        dataSource={sortedDevices}
        scroll={{ y: collapsed ? 300 : 400 }}
        style={{ fontSize: collapsed ? 10 : 12 }}
        locale={{
          emptyText: (
            <Text type="secondary" style={{ fontSize: collapsed ? 10 : 12 }}>
              Scanning for devices...
            </Text>
          ),
        }}
      />

      {/* Leader Down Modal */}
      <Modal
        open={showLeaderDownModal}
        title={
          <span>
            <ExclamationCircleOutlined
              style={{ color: "#faad14", marginRight: 8 }}
            />
            Leader Offline
          </span>
        }
        footer={
          fatalCrashDetected ? (
            <Text type="danger" key="crash-warning">
              A fatal crash was detected on the leader device. Ongoing jobs may
              have been canceled.
            </Text>
          ) : (
            <>
              <Button
                key="cancel"
                onClick={() => setShowLeaderDownModal(false)}
              >
                Ignore
              </Button>
              <Button
                key="reelect"
                type="primary"
                danger
                onClick={reElectLeader}
              >
                Re-Elect Leader
              </Button>
            </>
          )
        }
        closable={false}
      >
        <Text>
          The leader device <Text strong>{leaderDevice?.name}</Text> is offline.
        </Text>
        <br />
        <Text type="secondary">
          Network stability requires a new leader election.
        </Text>
      </Modal>
    </div>
  );
};

export default DevicesSystemSidebar;
