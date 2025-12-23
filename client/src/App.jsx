import React, { useState, useEffect, useCallback } from 'react';
import './App.css';

const App = () => {
  const [devices, setDevices] = useState([]);
  const [status, setStatus] = useState('Not connected');
  const [isRunning, setIsRunning] = useState(false);
  const [localInfo, setLocalInfo] = useState({ pcName: '', ip: '' });
  const [stats, setStats] = useState({ totalDevices: 0, otherDevices: 0 });
  const [loading, setLoading] = useState(false);

  const API_BASE = 'http://localhost:5050/api';
  // const API_BASE = '/api';

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/status`);
      const data = await response.json();
      setIsRunning(data.running);
      setLocalInfo({
        pcName: data.local_pc_name,
        ip: data.local_ip
      });
    } catch (error) {
      console.error('Error fetching status:', error);
      setStatus('Error connecting to server');
    }
  }, []);

  const fetchDevices = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/devices`);
      const data = await response.json();
      setDevices(data.devices || []);
      setStats(data.stats || { totalDevices: 0, otherDevices: 0 });
      
      if (isRunning) {
        setStatus(`Found ${data.stats.other_devices} other devices`);
      }
    } catch (error) {
      console.error('Error fetching devices:', error);
    }
  }, [isRunning]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (isRunning) {
      fetchDevices();
      const interval = setInterval(fetchDevices, 2000);
      return () => clearInterval(interval);
    }
  }, [isRunning, fetchDevices]);

  const toggleNetwork = async () => {
    setLoading(true);
    try {
      if (isRunning) {
        await fetch(`${API_BASE}/stop`, { method: 'POST' });
        setIsRunning(false);
        setStatus('Not connected');
        setDevices([]);
      } else {
        const response = await fetch(`${API_BASE}/start`, { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
          setIsRunning(true);
          setStatus('Discovering...');
          setTimeout(fetchDevices, 1000);
        } else {
          setStatus(`Error: ${data.message}`);
        }
      }
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const testBroadcast = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/test-broadcast`, { method: 'POST' });
      const data = await response.json();
      setStatus(data.message);
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const clearList = async () => {
    try {
      await fetch(`${API_BASE}/clear-devices`, { method: 'POST' });
      fetchDevices();
      setStatus('Device list cleared');
    } catch (error) {
      setStatus(`Error: ${error.message}`);
    }
  };

  const refreshDevices = () => {
    if (isRunning) {
      setStatus('Refreshing...');
      fetchDevices();
    }
  };

  return (
    <div className="network-discovery">
      <div className="discovery-header">
        <h1>Network Discovery</h1>
      </div>

      <div className="network-info">
        <h2>Network Information</h2>
        <div className="info-grid">
          <div className="info-item">
            <span>PC Name:</span>
            <span>{localInfo.pcName || 'Unknown'}</span>
          </div>
          <div className="info-item">
            <span>IP Address:</span>
            <span>{localInfo.ip || 'Unknown'}</span>
          </div>
        </div>
      </div>

      <div className="control-section">
        <button 
          className="network-button"
          onClick={toggleNetwork}
          disabled={loading}
        >
          {isRunning ? 'Leave Network' : 'Enter Network'}
        </button>
      </div>

      <div className="devices-section">
        <div className="section-header">
          <h2>Discovered Devices</h2>
          <div className="device-count">
            Total: {stats.totalDevices} | Others: {stats.otherDevices}
          </div>
        </div>
        
        <div className="devices-table-container">
          <table className="devices-table">
            <thead>
              <tr>
                <th>PC Name</th>
                <th>IP Address</th>
                <th>Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {devices.length === 0 ? (
                <tr>
                  <td colSpan="3" className="no-devices">
                    {isRunning ? 'No devices discovered yet...' : 'Network discovery not active'}
                  </td>
                </tr>
              ) : (
                devices.map((device, index) => (
                  <tr key={index}>
                    <td>{device.name}</td>
                    <td>{device.ip}</td>
                    <td>{device.last_seen}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="control-buttons">
        <button 
          onClick={refreshDevices}
          disabled={!isRunning || loading}
          className="control-btn"
        >
          Refresh
        </button>
        <button 
          onClick={clearList}
          disabled={!isRunning || loading}
          className="control-btn"
        >
          Clear List
        </button>
        <button 
          onClick={testBroadcast}
          disabled={loading}
          className="control-btn"
        >
          Test Broadcast
        </button>
      </div>

      <div className="status-bar">
        <span>Status: {status}</span>
      </div>

      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
        </div>
      )}
    </div>
  );
};

export default App;