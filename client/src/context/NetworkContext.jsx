import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { message } from "antd";

const NetworkContext = createContext(null);

const API_BASE = "http://localhost:5050/api";

export const NetworkProvider = ({ children }) => {
  const [devices, setDevices] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isElecRunning, setIsElecRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: "", ip: "" });
  const [loading, setLoading] = useState(false);
  const [currentLeader, setCurrentLeader] = useState(null);
  const [myRole, setMyRole] = useState(null);

  const [messageApi, contextHolder] = message.useMessage();

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      const data = await res.json();
      setIsRunning(data.running);
      setLocalInfo({
        pcName: data.local_pc_name,
        ip: data.local_ip,
      });
    } catch {
      messageApi.error("Failed to connect to network service");
    }
  }, [messageApi]);

  const fetchDevices = useCallback(async () => {
    if (!isRunning) return;

    try {
      const res = await fetch(`${API_BASE}/devices`);
      const data = await res.json();

      const enriched = (data || []).map(d => ({
        ...d,
        timestamp: d.last_seen ? d.last_seen * 1000 : Date.now(),
      }));

      setDevices(enriched);
    } catch {
      console.error("Device polling failed");
    }
  }, [isRunning]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (!isRunning) {
      setDevices([]);
      return;
    }

    fetchDevices();
    const interval = setInterval(fetchDevices, 2000);
    return () => clearInterval(interval);
  }, [isRunning, fetchDevices]);

  const fetchElectionStatus = useCallback(async () => {
    if (!isElecRunning) return;

    try {
      const res = await fetch(`${API_BASE}/election/status`);
      const data = await res.json();

      setCurrentLeader(data.election_active);
      setMyRole(data.my_role);
    } catch {
      console.error("Election status polling failed");
    }
  }, [isElecRunning]);

  const enterNetwork = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/start`, { method: "POST" });
      setIsRunning(true);
      messageApi.success("Entered network discovery");
    } finally {
      setLoading(false);
    }
  };

  const leaveNetwork = async () => {
    setLoading(true);
    try {
      await fetch(`${API_BASE}/stop`, { method: "POST" });
      setIsRunning(false);
      setDevices([]);
      messageApi.info("Left the network");
    } finally {
      setLoading(false);
    }
  };

  return (
    <NetworkContext.Provider
      value={{
        devices,
        isRunning,
        localInfo,
        loading,
        enterNetwork,
        leaveNetwork,
      }}
    >
      {contextHolder}
      {children}
    </NetworkContext.Provider>
  );
};

export const useNetwork = () => useContext(NetworkContext);
